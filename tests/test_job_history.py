"""The job history says how every job ended (the runner keeps `<job>.exit` next to the log), how long
it took, and which voices a training queue had."""

from __future__ import annotations

from datetime import datetime
import json
import sys

from piper_voice_cloner import runner
from piper_voice_cloner.editor import steps


def log(folder, name, first="$ pvc train kasia\n", end=None):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(first + "work\n", encoding="utf-8")
    if end is not None:
        started = datetime.strptime(name[:15], "%Y%m%d-%H%M%S").timestamp()
        path.with_suffix(".exit").write_text(
            json.dumps({"returncode": end, "finished": started + 3725}), encoding="utf-8"
        )
    return path


def test_every_job_shows_how_it_ended_and_how_long_it_took(tmp_path):
    jobs = tmp_path / "jobs"
    log(jobs, "20261118-010000-train-kasia.log", end=0)
    log(jobs, "20261118-020000-export-kasia.log", end=1)
    log(jobs, "20261118-030000-filter-ola.log", end=130)
    log(jobs, "20261117-230000-import-tomek.log")  # before the exit files
    running = log(jobs, "20261118-040000-train-ola.log")
    (jobs / "current.json").write_text(json.dumps({"log": f"/data/jobs/{running.name}", "returncode": None}))
    found = {item["file"][:15]: item for item in steps.job_history(tmp_path)}
    assert found["20261118-010000"]["status"] == "ok" and found["20261118-010000"]["took"] == 3725
    assert found["20261118-020000"]["status"] == "failed" and found["20261118-020000"]["code"] == 1
    assert found["20261118-030000"]["status"] == "stopped"
    assert found["20261117-230000"]["status"] == "unknown" and found["20261117-230000"]["took"] is None
    assert found["20261118-040000"]["status"] == "running"


def test_a_training_queue_names_its_voices(tmp_path):
    jobs = tmp_path / "jobs"
    log(
        jobs,
        "20261118-010000-train-queue.log",
        first="$ pvc --root /data train-queue kasia ola --epochs 500 --base lessac\n",
        end=0,
    )
    (item,) = steps.job_history(tmp_path)
    assert item["kind"] == "train-queue" and item["voice"] == "kasia, ola"


def test_the_runner_keeps_the_exit_code_next_to_the_log(tmp_path):
    state = tmp_path / "jobs" / "current.json"
    log_path = tmp_path / "jobs" / "20261118-010000-train-kasia.log"
    code = runner.run(state, log_path, [sys.executable, "-c", "import sys; print('hi'); sys.exit(3)"])
    end = json.loads(runner.exit_path(log_path).read_text(encoding="utf-8"))
    assert code == 3 and end["returncode"] == 3 and end["finished"] > 0
    assert runner.exit_path(log_path).name == "20261118-010000-train-kasia.exit"
