"""Powering the machine off after a job: a countdown in the top bar, then Home Assistant does it.

The wish belongs to one job (its `poweroff` in the state file, changeable while it runs). When that
job ends - well or with an error, never after Stop - POWER_OFF_DELAY seconds are counted down where
everybody sees them, with Cancel. A job started by hand meanwhile cancels the countdown. Nothing of it
is kept on disk: a restart of the editor during the countdown never powers the machine off.
"""

from __future__ import annotations

from collections.abc import Callable
import threading
import time

from ..jobs import JobManager
from ..runner import STOPPED_CODES

POWER_OFF_DELAY = 120  # seconds between the end of the job and switching the machine off
TICK = 2.0


class PowerOffTimer:
    def __init__(self, jobs: dict[str, JobManager], power_off: Callable[[], object]) -> None:
        self.jobs = jobs
        self.power_off = power_off
        self._lock = threading.Lock()
        self.at: float | None = None  # when the machine is switched off
        self.pending = False  # the job with the wish ended while another one still runs: wait for it
        self.error: str | None = None
        self.done = False
        # a job that ended before this editor started never counts down (a restart drops the countdown)
        self._seen = {self._key(m) for m in jobs.values() if m.status() and not m.running()}

    @staticmethod
    def _key(manager: JobManager) -> tuple | None:
        status = manager.status()
        return (manager.state_path.name, status.started) if status else None

    def check(self, now: float | None = None) -> None:
        """Start, cancel or finish the countdown; called on every look at the state and by a thread."""
        now = time.time() if now is None else now
        with self._lock:
            running = [m for m in self.jobs.values() if m.running()]
            if self.at is not None and running:
                self.at = None  # a job started by hand during the countdown: the machine stays on
                return
            for manager in self.jobs.values():
                key = self._key(manager)
                if key is None or key in self._seen or manager.running():
                    continue
                self._seen.add(key)
                status = manager.status()
                # only the job with the wish counts; its Stop means somebody is there: never power off
                stopped = status.stop_requested or status.returncode in STOPPED_CODES
                if status.poweroff and not stopped:
                    self.pending, self.error, self.done = True, None, False
            if self.pending and not running:
                self.pending, self.at = False, now + POWER_OFF_DELAY
            if self.at is not None and now >= self.at:
                self.at = None
                try:
                    self.power_off()
                    self.done = True
                except Exception as err:  # no token, switch unavailable: shown in the top bar
                    self.error = str(err) or type(err).__name__

    def cancel(self) -> bool:
        with self._lock:
            cancelled = self.at is not None or self.pending
            self.at, self.pending, self.error = None, False, None
            return cancelled

    def payload(self, now: float | None = None) -> dict:
        now = time.time() if now is None else now
        current = self.jobs["current"].status()
        wish = bool(current and current.running and current.poweroff) or self.pending
        return {
            "after_training": wish,
            "at": self.at,
            "seconds_left": max(0, round(self.at - now)) if self.at is not None else None,
            "error": self.error,
            "done": self.done,
        }

    def start(self) -> None:
        """Count down even when no page is open (a night training)."""

        def loop() -> None:
            while True:
                time.sleep(TICK)
                try:
                    self.check()
                except Exception:
                    continue

        threading.Thread(target=loop, daemon=True, name="power-off").start()
