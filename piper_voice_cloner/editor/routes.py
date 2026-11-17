"""API of the steps: each GET gives what a view shows, each POST starts the same `pvc` command as the CLI."""

from __future__ import annotations

from pathlib import Path
import shutil
import tempfile

from fastapi import FastAPI, UploadFile
from pydantic import BaseModel, Field

from . import service, steps


class ImportRun(BaseModel):
    folder: str
    persona: str = ""
    verify: bool = False


class TrainRun(BaseModel):
    base: str
    epochs: int = Field(ge=1)
    poweroff: bool = False


class QueueRun(TrainRun):
    voices: list[str]


class ExportRun(BaseModel):
    checkpoint: str = ""


def add_step_routes(app: FastAPI, root: Path, need_voice, start, error) -> None:
    jobs = app.state.jobs

    # --- import -----------------------------------------------------------------------------------

    @app.get("/api/voices/{name}/import")
    def import_view(name: str):
        need_voice(name)
        return steps.import_view(root, name)

    @app.post("/api/voices/{name}/import/upload")
    def import_upload(name: str, file: UploadFile):
        """A ZIP with metadata.csv and wav/: unpacked to <data>/import/<voice> for the import."""
        need_voice(name)
        with tempfile.NamedTemporaryFile(suffix=".zip") as handle:
            shutil.copyfileobj(file.file, handle)
            handle.flush()
            try:
                folder = steps.unpack_dataset(root, name, Path(handle.name))
            except Exception as err:  # not a ZIP, no metadata.csv
                raise error("import_zip_failed", str(err)) from err
        return {"folder": str(folder)}

    @app.post("/api/voices/{name}/import")
    def import_run(name: str, run: ImportRun):
        need_voice(name)
        if not run.folder.strip():
            raise error("import_folder_missing")
        if not (Path(run.folder.strip()).expanduser() / "metadata.csv").is_file():
            raise error("import_no_metadata", folder=run.folder)
        return start("import", name, steps.import_args(name, run.folder, run.persona, run.verify))

    # --- training ---------------------------------------------------------------------------------

    @app.get("/api/voices/{name}/train")
    def train_view(name: str):
        need_voice(name)
        return steps.train_view(root, name)

    @app.post("/api/voices/{name}/train")
    def train_run(name: str, run: TrainRun):
        need_voice(name)
        if not service.dataset_size(root, name):
            raise error("train_no_dataset")
        service.set_max_epochs(root, name, run.epochs)
        return start("train", name, ["train", name, "--base", run.base], poweroff=run.poweroff)

    @app.post("/api/queue")
    def queue_run(run: QueueRun):
        if not run.voices:
            raise error("queue_empty")
        for name in run.voices:
            need_voice(name)
        args = ["train-queue", *run.voices, "--epochs", str(run.epochs), "--base", run.base]
        return start("train-queue", "", args, poweroff=run.poweroff)

    @app.get("/api/queue")
    def queue_view():
        choices, value, ready = service.base_options(root, None)
        return {
            "voices": service.trainable_voices(root),
            "base_choices": choices,
            "base": value,
            "base_ready": ready,
        }

    @app.get("/api/chart")
    def chart(voice: str = ""):
        target = steps.chart_target(root, jobs["current"], voice or None)
        return steps.chart_view(root, target) if target else {"target": None, "rows": []}

    @app.get("/api/listen")
    def listen(target: str, epoch: int | None = None):
        try:
            return steps.listen_view(root, steps.work_dir(root, target), epoch)
        except ValueError as err:
            raise error("unknown_run", str(err), status=404) from err

    @app.post("/api/listen/zip")
    def listen_zip(target: str):
        try:
            return {"url": steps.samples_zip(root, target)}
        except ValueError as err:
            raise error("samples_none", str(err)) from err

    # --- export -----------------------------------------------------------------------------------

    @app.get("/api/voices/{name}/export")
    def export_view(name: str):
        need_voice(name)
        return steps.export_view(root, name)

    @app.post("/api/voices/{name}/export")
    def export_run(name: str, run: ExportRun):
        need_voice(name)
        args = ["export", name] + (["--checkpoint", run.checkpoint] if run.checkpoint else [])
        return start("export", name, args)

    # --- history ----------------------------------------------------------------------------------

    @app.get("/api/history")
    def history():
        return steps.job_history(root)

    @app.get("/api/history/{file}")
    def history_log(file: str):
        try:
            return {"log": steps.job_log(root, file)}
        except ValueError as err:
            raise error("unknown_log", status=404) from err
