"""Background jobs for the web UI: one `pvc` command at a time (there is one GPU).

State lives in <root>/jobs/current.json, so the UI can be restarted while a job runs. A second slot
(e.g. "side": rating recordings on the CPU) runs next to it with its own state file.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

from piper_voice_cloner.webui.runner import update_state

TAIL_LINES = 120  # enough for a whole Python traceback in the log window
# printed once per training: hours later it is far above the tail, but the progress bar needs it
PLAN_LINE = re.compile(rb"training epochs \d+-\d+")


@dataclass(frozen=True)
class JobStatus:
    kind: str
    voice: str
    running: bool
    returncode: int | None
    started: float | None
    log_tail: str
    finished: float | None = None
    queue_log: str = ""  # the training queue's command and its "queue ..." lines, whole job
    poweroff: bool = False

    def elapsed(self, now: float | None = None) -> float | None:
        if self.started is None:
            return None
        end = self.finished if (self.finished and not self.running) else (now or time.time())
        return end - self.started

    @property
    def finished_ok(self) -> bool:
        return not self.running and self.returncode == 0


class JobBusy(RuntimeError):
    def __init__(self, kind: str, voice: str) -> None:
        super().__init__(f"{kind} ({voice or '-'}) is still running")
        self.kind, self.voice = kind, voice


def pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def tail(path: Path, lines: int = TAIL_LINES) -> str:
    if not path.is_file():
        return ""
    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        size = handle.tell()
        handle.seek(max(0, size - 64 * 1024))
        text = handle.read().decode("utf-8", errors="replace")
    # progress bars rewrite the line with \r; keep only the last state of each line
    # split on \n only: splitlines() would also break at \r and lose the latest progress state
    cleaned = [line.rsplit("\r", 1)[-1] for line in text.rstrip("\n").split("\n")]
    return "\n".join(cleaned[-lines:])


class JobManager:
    def __init__(self, root: Path, pvc: list[str] | None = None, slot: str = "current") -> None:
        self.root = root
        self.dir = root / "jobs"
        self.state_path = self.dir / f"{slot}.json"
        # the CLI itself, so the UI and the command line do exactly the same thing
        self.pvc = pvc or [sys.executable, "-m", "piper_voice_cloner.cli"]
        self._processes: list[subprocess.Popen] = []
        # log -> (bytes read, last plan line, queue lines)
        self._scans: dict[Path, tuple[int, str, str]] = {}

    def _scan(self, path: Path) -> tuple[str, str]:
        """(last training plan, queue lines) of the log; every call reads only what was added since."""
        offset, plan, queue = self._scans.get(path, (0, "", ""))
        if not path.is_file():
            return plan, queue
        with path.open("rb") as handle:
            handle.seek(offset)
            data = handle.read()
        end = data.rfind(b"\n") + 1  # a line still being written is read next time
        found = PLAN_LINE.findall(data[:end])
        if found:
            plan = found[-1].decode()
        for line in data[:end].split(b"\n"):
            line = line.rsplit(b"\r", 1)[-1]
            if line.startswith(b"queue ") or (line.startswith(b"$ ") and b" train-queue " in line):
                queue += line.decode("utf-8", errors="replace") + "\n"
        self._scans[path] = (offset + end, plan, queue)
        return plan, queue

    def _log_tail(self, path: Path) -> str:
        text = tail(path)
        plan = self._scan(path)[0]
        return text if not plan or plan in text else f"{plan}\n{text}"

    def _state(self) -> dict:
        if not self.state_path.is_file():
            return {}
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _reap(self) -> None:
        # finished runners started by this process would otherwise stay as zombies (pid "alive")
        self._processes = [p for p in self._processes if p.poll() is None]

    def running(self) -> bool:
        self._reap()
        state = self._state()
        return bool(state) and "returncode" not in state and pid_alive(state.get("runner_pid"))

    def start(self, kind: str, voice: str, args: list[str], *, poweroff: bool = False) -> JobStatus:
        if self.running():
            state = self._state()
            raise JobBusy(state.get("kind", ""), state.get("voice", ""))
        self.dir.mkdir(parents=True, exist_ok=True)
        log_path = self.dir / f"{time.strftime('%Y%m%d-%H%M%S')}-{kind}{'-' + voice if voice else ''}.log"
        cmd = [*self.pvc, "--root", str(self.root), *args]
        self.state_path.write_text(
            json.dumps(
                {
                    "kind": kind,
                    "voice": voice,
                    "log": str(log_path),
                    "started": time.time(),
                    "poweroff": poweroff,
                }
            ),
            encoding="utf-8",
        )
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "piper_voice_cloner.webui.runner",
                str(self.state_path),
                str(log_path),
                "--",
                *cmd,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,  # own process group, survives the UI process
        )
        self._processes.append(process)
        # the runner records its pid itself; wait briefly so status() is right immediately
        deadline = time.time() + 5
        while "runner_pid" not in self._state() and process.poll() is None and time.time() < deadline:
            time.sleep(0.02)
        return self.status()

    def set_poweroff(self, poweroff: bool) -> bool:
        """Change the wish of the running job (the runner reads it when the job ends)."""
        if not self.running():
            return False
        update_state(self.state_path, poweroff=poweroff)
        return True

    def stop(self) -> bool:
        """Ctrl+C for the whole job (training stops at once; `pvc train` resumes from last.ckpt)."""
        if not self.running():
            return False
        try:
            os.killpg(self._state()["runner_pid"], signal.SIGINT)
        except ProcessLookupError:
            return False
        return True

    def status(self) -> JobStatus | None:
        self._reap()
        state = self._state()
        if not state:
            return None
        running = "returncode" not in state and pid_alive(state.get("runner_pid"))
        returncode = state.get("returncode")
        if not running and returncode is None:
            returncode = -1  # runner died without recording a result
        return JobStatus(
            kind=state.get("kind", ""),
            voice=state.get("voice", ""),
            running=running,
            returncode=returncode,
            started=state.get("started"),
            log_tail=self._log_tail(Path(state.get("log", ""))),
            finished=state.get("finished"),
            queue_log=self._scan(Path(state.get("log", "")))[1],
            poweroff=bool(state.get("poweroff")),
        )

    def wait(self, timeout: float = 30.0) -> JobStatus | None:
        """Block until the current job ends (tests and scripts)."""
        deadline = time.time() + timeout
        while self.running() and time.time() < deadline:
            time.sleep(0.1)
        return self.status()
