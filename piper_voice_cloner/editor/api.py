"""What the editor page reads: plain dicts built from the data folder and the job state files.

The page does all wording itself (i18n.js); here only facts: names, counts, states, numbers.
"""

from __future__ import annotations

import time

from .. import config as config_mod
from ..dataset import METADATA, read_metadata
from ..jobs import JobManager, JobStatus
from ..runner import STOPPED_CODES
from . import service

# the steps of each way to a voice, in order (keys match service.steps and the CLI commands)
CLONE_STEPS = ("reference", "corpus", "audition", "synthesize", "filter", "score", "train", "export")
IMPORT_STEPS = ("import", "score", "train", "export")
IMPORT_REPORT = "import_report.csv"


def workflow(root, name: str, cfg: config_mod.VoiceConfig | None = None) -> str:
    """A voice with an import report is an imported one, whatever an older voice.yaml says."""
    directory = service.voice_dir(root, name)
    if (directory / "dataset" / IMPORT_REPORT).is_file():
        return "import"
    return (cfg or service.load_config(root, name)).workflow


def voice_steps(root, name: str) -> list[dict]:
    cfg = service.load_config(root, name)
    found = {step.key: step for step in service.steps(root, name)}
    if workflow(root, name, cfg) == "import":
        metadata = service.voice_dir(root, name) / "dataset" / METADATA
        clips = len(read_metadata(metadata)) if metadata.is_file() else 0
        found["import"] = service.Step("import", clips > 0, str(clips) if clips else "")
        keys = IMPORT_STEPS
    else:
        keys = CLONE_STEPS
    return [{"key": key, "done": found[key].done, "detail": found[key].detail} for key in keys]


def voice_summary(root, name: str) -> dict:
    try:
        cfg = service.load_config(root, name)
    except Exception as err:  # a broken voice.yaml must not hide the other voices
        return {"name": name, "error": str(err), "steps": [], "workflow": "clone"}
    return {
        "name": name,
        "piper_name": cfg.piper_name or "",
        "workflow": workflow(root, name, cfg),
        "backend": cfg.synthesis.backend,
        "steps": voice_steps(root, name),
    }


def job_state(status: JobStatus | None) -> str:
    """idle | running | ok | stopped | failed | interrupted (the runner died, e.g. a container restart)."""
    if status is None:
        return "idle"
    if status.running:
        return "running"
    if status.finished_ok:
        return "ok"
    if status.returncode in STOPPED_CODES or status.stop_requested:
        return "stopped"
    if status.returncode == -1 and not status.finished:
        return "interrupted"
    return "failed"


def progress(status: JobStatus) -> dict | None:
    """Training: epochs of the whole run and time left; other jobs: their own `progress` counter."""
    found = service.training_progress(status.log_tail)
    if found:
        done, total, position, left = found
        epoch, step, steps = position or (None, None, None)
        return {
            "done": done,
            "total": total,
            "unit": "epochs",
            "label": "",
            "epoch": epoch,
            "step": step,
            "steps": steps,
            "left": left,
        }
    found = service.parse_progress(status.log_tail)
    if not found:
        return None
    done, total, label = found
    left = service.time_left(status.elapsed(), done, total)
    return {"done": done, "total": total, "unit": "", "label": label, "left": left}


def job_payload(jobs: JobManager, now: float | None = None) -> dict:
    status = jobs.status()
    state = job_state(status)
    if status is None:
        return {"state": state}
    return {
        "state": state,
        "kind": status.kind,
        "voice": status.voice,
        "returncode": status.returncode,
        "started": status.started,
        "finished": status.finished,
        "elapsed": status.elapsed(now or time.time()),
        "poweroff": status.poweroff,
        "progress": progress(status) if status.running else None,
        "queue": [list(step) for step in service.queue_steps(status)],
        "log": service.compact_log(status.log_tail),
    }


def state_payload(root, jobs: dict[str, JobManager], *, gpu: bool = True) -> dict:
    """Everything the page needs on its regular refresh."""
    names = service.list_voices(root)
    return {
        "voices": [voice_summary(root, name) for name in names],
        "opening_voice": service.opening_voice(root),
        "base_ready": service.base_ready(root),
        "jobs": {slot: job_payload(manager) for slot, manager in jobs.items()},
        "gpu": service.gpu_stats() if gpu else None,
    }
