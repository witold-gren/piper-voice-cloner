"""Run one command, stream its output to a log file and record the exit code.

Started detached by the job manager, so a job keeps running when the browser or the UI server
is closed: `python -m piper_voice_cloner.webui.runner <state.json> <log> -- <cmd...>`.
"""

from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import time

# Ctrl+C from the "Stop" button: 130 from Python CLIs, -2 when the process died of SIGINT
STOPPED_CODES = (130, -2)
# allowed without a password on the GPU machine; Home Assistant then cuts its plug
POWEROFF = ["sudo", "-n", "/usr/sbin/poweroff"]
# replaces POWEROFF; the tests set it, because their jobs run in a separate process where
# patching POWEROFF does not reach (a CI runner with sudo really powered off)
POWEROFF_ENV = "PVC_POWEROFF_COMMAND"


def poweroff_command() -> list[str]:
    override = os.environ.get(POWEROFF_ENV)
    return shlex.split(override) if override else POWEROFF


def run(state_path: Path, log_path: Path, cmd: list[str]) -> int:
    # "Stop" sends Ctrl+C to the whole process group: the command handles it, the runner must
    # survive to record the exit code (a Python handler, unlike SIG_IGN, is not inherited)
    signal.signal(signal.SIGINT, lambda *_: None)
    update_state(state_path, runner_pid=os.getpid())
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as log:
        log.write(f"$ {' '.join(cmd)}\n".encode())
        log.flush()
        # unbuffered, so the UI shows progress lines as they happen
        env = {**os.environ, "PYTHONUNBUFFERED": "1"}
        process = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env)
        update_state(state_path, child_pid=process.pid)
        returncode = process.wait()
    update_state(state_path, returncode=returncode, finished=time.time())
    # a failed night still ends with the machine off; only "Stop" means somebody is at the panel
    # read only now: the panel can change the wish while the job runs
    if returncode not in STOPPED_CODES and json.loads(state_path.read_text(encoding="utf-8")).get("poweroff"):
        with log_path.open("ab") as log:
            log.write(b"Powering the machine off\n")
            log.flush()
            subprocess.run(poweroff_command(), stdout=log, stderr=subprocess.STDOUT, check=False)
    return returncode


def update_state(path: Path, **values) -> None:
    # the runner and the panel both change the file (child_pid vs the poweroff wish): without the
    # lock one of them writes back an old copy and the other's change is lost
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        state.update(values)
        tmp = path.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(state), encoding="utf-8")
        tmp.replace(path)


def main(argv: list[str]) -> int:
    if len(argv) < 4 or argv[2] != "--":
        print("usage: runner <state.json> <log> -- <cmd...>", file=sys.stderr)
        return 2
    return run(Path(argv[0]), Path(argv[1]), argv[3:])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
