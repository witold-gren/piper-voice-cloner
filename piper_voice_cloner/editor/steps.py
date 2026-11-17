"""Facts for the step views: import, training (with the queue, chart and listening), export, job history.

Plain dicts again; the page words them. Paths for players and downloads are relative to the data
folder (served by /api/files).
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
import shutil
import zipfile

from .. import config as config_mod, train_monitor
from ..jobs import JobManager
from . import service

EPOCH_IN_NAME = re.compile(r"epoch=(\d+)")
METRIC_IN_NAME = re.compile(r"(val_mos|val_mel)=(\d+(?:\.\d+)?)")
IMPORT_DIR = "import"  # <root>/import/<folder>: where own recordings are put for the import
LOG_NAME = re.compile(r"^(\d{8}-\d{6})-(.+)\.log$")
# job kinds as the job manager names logs (<stamp>-<kind>[-<voice>].log), longest first
JOB_KINDS = "reference corpus sentences audition synthesize filter import train train-queue export"
BASE_KINDS = "base-prepare base-train base-select base-export base-score"
KINDS = sorted(f"{JOB_KINDS} {BASE_KINDS}".split(), key=len, reverse=True)
SAMPLE_PLAYERS = 6


def rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


# --- import -------------------------------------------------------------------------------------


def import_folders(root: Path) -> list[dict]:
    """Folders under <root>/import with a metadata.csv: what can be imported without typing a path."""
    base = root / IMPORT_DIR
    if not base.is_dir():
        return []
    found = []
    for folder in sorted(p for p in base.iterdir() if p.is_dir()):
        metadata = folder / "metadata.csv"
        if metadata.is_file():
            lines = sum(
                1
                for line in metadata.read_text(encoding="utf-8", errors="replace").splitlines()
                if line.strip()
            )
            personas = sorted(p.name for p in folder.glob("*.csv") if p.name != "metadata.csv")
            found.append({"path": str(folder), "name": folder.name, "lines": lines, "personas": personas})
    return found


def unpack_dataset(root: Path, voice: str, upload: Path) -> Path:
    """A ZIP of metadata.csv + wav/ goes to <root>/import/<voice>; a single top folder is skipped."""
    target = root / IMPORT_DIR / voice
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    with zipfile.ZipFile(upload) as archive:
        names = [n for n in archive.namelist() if not n.startswith("__MACOSX/") and not n.endswith("/")]
        tops = {n.split("/", 1)[0] for n in names}
        strip = len(tops) == 1 and all("/" in n for n in names)
        for name in names:
            relative = name.split("/", 1)[1] if strip else name
            path = (target / relative).resolve()
            if target.resolve() not in path.parents:  # no ../ out of the folder
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(name) as source, path.open("wb") as out:
                shutil.copyfileobj(source, out)
    if not (target / "metadata.csv").is_file():
        shutil.rmtree(target)
        raise ValueError("metadata.csv not found in the ZIP")
    return target


def import_args(voice: str, folder: str, persona: str, verify: bool) -> list[str]:
    path = Path(folder.strip()).expanduser()
    args = ["import", voice, str(path)]
    if persona.strip():
        args += [
            "--metadata",
            str(path / "metadata.csv"),
            "--persona",
            str(service.persona_path(path, persona)),
        ]
    if verify:
        args.append("--verify")
    return args


def clip_report(root: Path, name: str) -> dict:
    """Reasons of rejection and a few kept / rejected clips to listen to (import or filter report)."""
    rows = service.filter_report(root, name)
    kept = service.sample_clips(root, name, rows, kept=True, limit=SAMPLE_PLAYERS)
    rejected = service.sample_clips(root, name, rows, kept=False, limit=SAMPLE_PLAYERS)

    def clips(found):
        return [{"url": rel(root, Path(path)), "text": text} for path, text in found[:SAMPLE_PLAYERS]]

    return {
        "rows": len(rows),
        "kept": sum(1 for row in rows if not row.get("reason")),
        "reasons": service.reason_counts(rows),
        "kept_clips": clips(kept),
        "rejected_clips": clips(rejected),
    }


def import_view(root: Path, name: str) -> dict:
    return {
        "clips": service.dataset_size(root, name),
        "folders": import_folders(root),
        "import_dir": str(root / IMPORT_DIR),
        "report": clip_report(root, name),
    }


# --- training ------------------------------------------------------------------------------------


def checkpoint_list(root: Path, name_or_dir: str | Path) -> list[dict]:
    work = (
        Path(name_or_dir) if isinstance(name_or_dir, Path) else service.voice_dir(root, name_or_dir) / "train"
    )
    found = []
    for path in service.checkpoints(work):
        epoch = EPOCH_IN_NAME.search(path.name)
        metric = METRIC_IN_NAME.search(path.name)
        found.append(
            {
                "path": str(path),
                "name": path.name,
                "run": path.parents[1].name,
                "epoch": int(epoch.group(1)) if epoch else None,
                "metric": metric.group(1) if metric else None,
                "value": float(metric.group(2)) if metric else None,
            }
        )
    return found


def resume_plan(root: Path, name: str, max_epochs: int) -> dict | None:
    """What "Train" does with an earlier run: finish the planned epochs or add max_epochs more.

    Same rule as `pvc train`: planned = start_epoch (run.json) + max_epochs; a checkpoint at or past
    it means the run is done and the epochs count on top of the checkpoint.
    """
    work = service.voice_dir(root, name) / "train"
    info_path = work / "run.json"
    if not info_path.is_file():
        return None
    start = int(json.loads(info_path.read_text(encoding="utf-8")).get("start_epoch", 0))
    epochs = [c["epoch"] for c in checkpoint_list(root, name) if c["epoch"] is not None]
    if not epochs:
        return None
    reached = max(epochs)
    planned = start + max_epochs
    # run_start lets the page work it out again for the epochs typed in
    if reached >= planned:
        return {
            "reached": reached,
            "run_start": start,
            "start": reached,
            "end": reached + max_epochs,
            "done": True,
        }
    return {
        "reached": reached,
        "run_start": start,
        "start": start,
        "end": planned,
        "left": planned - reached,
        "done": False,
    }


def train_view(root: Path, name: str) -> dict:
    cfg = service.load_config(root, name)
    clips = service.dataset_size(root, name)
    estimate = None
    if clips:
        found = service.estimate(clips, cfg.train.batch_size, cfg.train.validation_split)
        low, high = found.epoch_seconds
        hours_low, hours_high = found.hours(cfg.train.max_epochs)
        estimate = {
            "steps": found.steps_per_epoch,
            "low": low,
            "high": high,
            "hours_low": hours_low,
            "hours_high": hours_high,
        }
    choices, value, ready = service.base_options(root, cfg.train.base)
    return {
        "clips": clips,
        "estimate": estimate,
        "max_epochs": cfg.train.max_epochs,
        "batch_size": cfg.train.batch_size,
        "base": value,
        "base_choices": choices,
        "base_ready": ready,
        "wanted_base": cfg.train.base,
        "checkpoints": checkpoint_list(root, name),
        "resume": resume_plan(root, name, cfg.train.max_epochs),
        "queue_voices": service.trainable_voices(root),
    }


def listen_view(root: Path, work: Path, epoch: int | None = None) -> dict:
    """Epochs with samples, their quality and the clips of one epoch (the chosen or the newest)."""
    run = train_monitor.update(work) if train_monitor.event_files(work) else None
    if run is None or not run.epochs:
        return {"epochs": [], "samples": [], "chosen": None, "summary": None}
    scores = run.metrics.get("val_mos", {})
    best = max(scores, key=scores.get) if scores else None
    last = max(scores) if scores else run.epochs[0]
    chosen = epoch if epoch in run.samples else run.epochs[0]
    return {
        "epochs": [{"epoch": e, "mos": run.value("val_mos", e), "saved": e in run.saved} for e in run.epochs],
        "chosen": chosen,
        "samples": [{"text": s.text, "url": rel(root, s.path)} for s in run.samples[chosen][:SAMPLE_PLAYERS]],
        "summary": {"last": last, "mos": scores.get(last), "best": scores.get(best), "best_epoch": best},
    }


def work_dir(root: Path, target: str) -> Path:
    """voice:<name> or base:<medium|high>."""
    kind, _, value = target.partition(":")
    if kind == "voice" and value in service.list_voices(root):
        return service.voice_dir(root, value) / "train"
    if kind == "base" and value in ("medium", "high"):
        return service.base_work_dir(root, value)
    raise ValueError(f"unknown training run: {target}")


def samples_zip(root: Path, target: str) -> str:
    work = work_dir(root, target)
    title = (
        f"{target.split(':', 1)[1]}-samples"
        if target.startswith("voice:")
        else f"bazowy-pl-{target[5:]}-samples"
    )
    return rel(root, train_monitor.export_samples(work, title))


def chart_target(root: Path, jobs: JobManager, voice: str | None) -> str | None:
    """The run the chart follows: the training running (or last run), else the voice, else the base."""
    status = jobs.status()
    quality = service.latest_base_run(root) or "medium"
    candidates = []
    if status and status.kind == "base-train":
        candidates.append(f"base:{quality}")
    elif status and status.kind in ("train", "train-queue"):
        trained = status.voice or service.queue_voice(root)
        if trained:
            candidates.append(f"voice:{trained}")
    if voice:
        candidates.append(f"voice:{voice}")
    candidates.append(f"base:{quality}")
    for target in candidates:
        try:
            if train_monitor.event_files(work_dir(root, target)):
                return target
        except ValueError:
            continue
    return None


def chart_view(root: Path, target: str) -> dict:
    run = train_monitor.update(work_dir(root, target))
    rows = run.table()
    mos = [(r[0], r[1]) for r in rows if r[1] is not None]
    mel = [(r[0], r[2]) for r in rows if r[2] is not None]
    return {
        "target": target,
        "rows": rows,
        "best": {
            "mos": max(mos, key=lambda item: item[1]) if mos else None,
            "mel": min(mel, key=lambda item: item[1]) if mel else None,
        },
        "last_epoch": run.last_epoch,
    }


# --- export --------------------------------------------------------------------------------------


def export_view(root: Path, name: str) -> dict:
    cfg = service.load_config(root, name)
    files = service.exports(service.voice_dir(root, name))
    return {
        "checkpoints": checkpoint_list(root, name),
        "files": [{"name": p.name, "url": rel(root, p), "size": p.stat().st_size} for p in files],
        "stem": cfg.file_stem(cfg.language),
    }


# --- job history ---------------------------------------------------------------------------------


def job_history(root: Path, limit: int = 100) -> list[dict]:
    """Logs of earlier jobs, newest first: kind, voice, start time (from the file name)."""
    folder = root / "jobs"
    if not folder.is_dir():
        return []
    found = []
    for path in sorted(folder.glob("*.log"), reverse=True)[:limit]:
        match = LOG_NAME.match(path.name)
        if not match:
            continue
        stamp, rest = match.groups()
        kind = next((k for k in KINDS if rest == k or rest.startswith(f"{k}-")), None)
        if kind is None:
            continue
        voice = rest[len(kind) + 1 :]
        found.append(
            {
                "file": path.name,
                "kind": kind,
                "voice": voice or "",
                "started": datetime.strptime(stamp, "%Y%m%d-%H%M%S").strftime("%Y-%m-%d %H:%M:%S"),
                "size": path.stat().st_size,
            }
        )
    return found


def job_log(root: Path, file: str) -> str:
    path = (root / "jobs" / file).resolve()
    if path.parent != (root / "jobs").resolve() or path.suffix != ".log" or not path.is_file():
        raise ValueError("unknown log")
    from ..jobs import tail

    return service.compact_log(tail(path, 400))


def known_voice(root: Path, name: str) -> config_mod.VoiceConfig:
    return service.load_config(root, name)
