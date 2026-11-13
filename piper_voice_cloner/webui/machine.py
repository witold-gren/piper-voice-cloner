"""The GPU machine as the page sees it: its power (through Home Assistant) and the job running on it.

Nothing here may hold up the page. A machine that is switched off takes the SSH timeout to say so
and Home Assistant can be slow or away, so the page always gets the last known state at once
(``checking`` until the first answer) and the machine and Home Assistant are asked in a background
thread - one check at a time, outside the lock. An unexpected failure of the check is reported on
the page, never "checking" for ever.

The same design as the wake word training panel (home-assistant-wakeword, ``trainer/server.py``).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import socket
import subprocess
import threading
import time

from .. import ha, power, remote
from .jobs import JobManager

SSH_TIMEOUT = 20  # seconds for the whole job check (ssh itself gives up connecting after 10 s)


def run_ssh(command: list[str]) -> str:
    result = subprocess.run(command, capture_output=True, text=True, timeout=SSH_TIMEOUT, check=False)
    if result.returncode != 0:
        lines = [line for line in result.stderr.strip().splitlines() if line.strip()]
        raise RuntimeError(lines[-1] if lines else f"ssh exit code {result.returncode}")
    return result.stdout


class MachineMonitor:
    MACHINE_CACHE = 10.0  # seconds a power reading from Home Assistant is kept
    POLL_SECONDS = 10.0  # seconds between two job checks on the machine
    REACH_TIMEOUT = 1.5  # a TCP connect to the SSH port; a machine that is off never answers

    def __init__(self, root: Path, jobs: JobManager, run: Callable[[list[str]], str] = run_ssh) -> None:
        self.root = Path(root)
        self.jobs = jobs
        self.run = run
        self.lock = threading.Lock()
        self._machine_cache: tuple[float, dict] | None = (
            None  # (time, switch/watts/state) from Home Assistant
        )
        self._entities_cache: dict | None = None
        self._checked = False  # the machine answered (or failed to) at least once
        self._refreshing = False  # a background check is running
        self._polled = 0.0
        self.remote_job: dict | None = None  # {"running", "kind", "voice"} of the web UI on the machine
        self.reachable: bool | None = None
        self.remote_error: str | None = None
        self.answered_at: float | None = None  # last time the machine answered over SSH

    # --- where the machine is ---------------------------------------------------------------------
    def server(self) -> remote.ServerConfig | None:
        try:
            return remote.load_config(self.root)
        except (OSError, ValueError, TypeError):
            return None

    def machine_is_here(self) -> bool:
        """No server saved: this web UI runs on the GPU machine itself, its jobs are the machine's."""
        return self.server() is None

    def _reachable(self) -> bool:
        """The machine answers on its SSH port (a quick connect, no login)."""
        config = self.server()
        if config is None:
            return True
        try:
            with socket.create_connection((config.host, int(config.port)), timeout=self.REACH_TIMEOUT):
                return True
        except OSError:
            return False

    # --- the job on the machine -------------------------------------------------------------------
    def poll(self, force: bool = False) -> dict:
        """Ask the machine whether a job runs there (at most every POLL_SECONDS).

        The machine is asked outside the lock: a machine that is off would take the SSH timeout to
        say so, and nothing else waits for it. A closed SSH port (the machine is off) is not an error.
        """
        with self.lock:
            config = self.server()
            if config is None:  # nothing to ask: this computer is the machine, or no server yet
                self.remote_job, self.remote_error, self.reachable = None, None, None
                self._checked = True
                return self._status()
            if not force and time.time() - self._polled < self.POLL_SECONDS:
                return self._status()
            self._polled = time.time()
        reachable = self._reachable()
        job, failure = None, None
        if reachable:
            try:
                job = remote.parse_job_state(self.run(remote.Remote(config).job_state()))
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as err:
                failure = str(err) or type(err).__name__
        with self.lock:
            self.reachable, self.remote_job, self.remote_error = reachable, job, failure
            self._checked = True
            if reachable and failure is None and config is not None:
                self.answered_at = time.time()
            return self._status()

    def _status(self) -> dict:
        job = self.remote_job or {}
        return {
            "running": bool(job.get("running")),
            "kind": job.get("kind", ""),
            "voice": job.get("voice", ""),
            "reachable": self.reachable,
            "error": self.remote_error,
            "answered_at": self.answered_at,
            # no server saved = nothing to ask over SSH, so nothing to wait for
            "checking": not self._checked and self.server() is not None,
        }

    def status(self) -> dict:
        """The last known state of the machine's job, at once."""
        with self.lock:
            return self._status()

    # --- power through Home Assistant -------------------------------------------------------------
    @staticmethod
    def power_ready() -> bool:
        return power.load_power().ready and ha.load_connection().ready

    def machine(self) -> dict | None:
        """Switch, plug power and whether the machine is on (header button); None when not set up."""
        settings = power.load_power()
        if not settings.ready or not ha.load_connection().ready:
            return None
        if ha.token_rejected():  # never asked again with this token (ip_ban counts each 401)
            return {"machine": "rejected", "watts": None, "error": ha.REJECTED_MESSAGE}
        cached = self._machine_cache
        if cached and time.time() - cached[0] < self.MACHINE_CACHE:
            return cached[1]
        try:
            answer = power.machine_state(ha.Client(), settings, self._reachable())
        except ha.HaError as err:
            answer = {"machine": "unknown", "watts": None, "error": str(err)}
        self._machine_cache = (time.time(), answer)
        return answer

    def machine_cached(self) -> dict | None:
        """The last known machine state for the page ({"machine": "checking"} before the first answer)."""
        if not self.power_ready():
            return None
        if ha.token_rejected():
            return {"machine": "rejected", "watts": None, "error": ha.REJECTED_MESSAGE}
        cached = self._machine_cache
        return cached[1] if cached else {"machine": "checking", "watts": None}

    def busy_job(self) -> str | None:
        """What runs on the machine right now ("train (kuba)"), or None."""
        local = self.jobs.status()
        if local and local.running and (self.machine_is_here() or local.kind.startswith("remote-")):
            return local.kind + (f" ({local.voice})" if local.voice else "")
        state = self.poll(force=True)
        if state["running"]:
            return state["kind"] + (f" ({state['voice']})" if state["voice"] else "")
        return None

    def switch_machine(self, on: bool) -> None:
        """Flip the machine's switch in Home Assistant (it shuts the system down before cutting the plug)."""
        settings = power.load_power()
        if not settings.ready:
            raise ValueError("set the machine's switch and power sensor first (Tools → Home Assistant)")
        if not on:
            busy = self.busy_job()
            if busy:
                raise RuntimeError(
                    f"a job is running on the machine: {busy} - stop it first or wait until it ends"
                )
        try:
            power.switch_machine(ha.Client(), settings, on)
        except ha.HaError as err:
            raise RuntimeError(str(err)) from None
        self._machine_cache = None

    def forget(self) -> None:
        """Settings changed: the next look asks again."""
        self._machine_cache = None
        self._entities_cache = None

    def ha_entities(self) -> dict:
        """Candidates for the power settings: switches and power sensors (W), asked from Home Assistant."""
        entities = ha.Client().entities()

        def pick(test):
            return sorted(
                (
                    {"id": e["entity_id"], "name": (e.get("attributes") or {}).get("friendly_name") or ""}
                    for e in entities
                    if test(e)
                ),
                key=lambda e: e["id"],
            )

        found = {
            "switches": pick(lambda e: e["entity_id"].startswith(("switch.", "input_boolean."))),
            "sensors": pick(
                lambda e: (
                    e["entity_id"].startswith("sensor.")
                    and (e.get("attributes") or {}).get("unit_of_measurement") == "W"
                )
            ),
            "count": len(entities),
        }
        self._entities_cache = found
        return found

    def entities_cached(self) -> dict:
        return self._entities_cache or {"switches": [], "sensors": [], "count": 0}

    # --- in the background ------------------------------------------------------------------------
    def refresh_in_background(self) -> None:
        """Ask the machine and Home Assistant in a thread: the page gets the last known state at once."""
        with self.lock:
            if self._refreshing:
                return
            self._refreshing = True

        def work() -> None:
            try:
                try:
                    self.poll()
                except Exception as err:
                    with self.lock:
                        self.remote_error, self._checked = f"{type(err).__name__}: {err}", True
                try:
                    self.machine()
                except Exception as err:
                    failed = {"machine": "unknown", "watts": None, "error": f"{type(err).__name__}: {err}"}
                    self._machine_cache = (time.time(), failed)
            finally:
                self._refreshing = False

        threading.Thread(target=work, name="machine-check", daemon=True).start()
