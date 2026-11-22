"""Base model, settings and the machine: the editor runs on the GPU machine itself.

- the own Polish base (bazowy-pl): prepare its data, rate the recordings, train, compare, choose;
- ElevenLabs key and the Home Assistant connection (both mode-600 files, never sent to the page);
- the machine's power through Home Assistant: read in the background, never holding up a page;
- each voice's settings (voice.yaml) with up to HISTORY earlier versions to bring back.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import threading
import time

from fastapi import FastAPI
from pydantic import BaseModel, Field, ValidationError
import yaml

from .. import config as config_mod, dataset_quality, ha, power, train as train_mod
from ..dataset import read_metadata
from ..jobs import JobManager
from . import api, service
from .steps import checkpoint_list, rel

HISTORY = 30
HISTORY_DIR = ".history"
DRAFT_FILE = ".draft.json"  # the voice.yaml being edited: survives closing the browser and a restart
MACHINE_EVERY = 30  # seconds between questions to Home Assistant about the machine


class BasePrepare(BaseModel):
    folder: str
    audio_dir: str = ""


class BaseScore(BaseModel):
    sample: int = Field(300, ge=0)


class Prune(BaseModel):
    below: float | None = Field(None, gt=0, lt=5)
    keep_best: int | None = Field(None, ge=1)


class BaseTrain(BaseModel):
    epochs: int = Field(ge=1)
    quality: str = "medium"
    batch: int = Field(0, ge=0)
    poweroff: bool = False


class Checkpoint(BaseModel):
    checkpoint: str


class Key(BaseModel):
    key: str = ""


class HaConnection(BaseModel):
    url: str
    token: str = ""


class PowerSettings(BaseModel):
    switch: str = ""
    sensor: str = ""
    off_watts: float = 5.0


class VoiceYaml(BaseModel):
    text: str
    note: str = ""
    base: str = ""  # the hash of voice.yaml the edit started from; another one = a conflict
    force: bool = False


class Rename(BaseModel):
    name: str
    piper_name: str = ""


class Version(BaseModel):
    file: str


# --- the machine (Home Assistant) -----------------------------------------------------------------


class Machine:
    """The machine's switch and plug as Home Assistant sees them; asked in a background thread."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: dict | None = None
        self._asked = 0.0
        self._busy = False

    @staticmethod
    def ready() -> bool:
        return ha.load_connection().ready and power.load_power().ready and not ha.token_rejected()

    def view(self) -> dict | None:
        """The last known state at once; a fresh answer is asked for when the last one is old."""
        if not self.ready():
            return None
        with self._lock:
            stale = time.time() - self._asked > MACHINE_EVERY and not self._busy
            if stale:
                self._busy = True
                self._asked = time.time()
        if stale:
            threading.Thread(target=self._ask, daemon=True).start()
        return self._state or {"machine": "checking", "watts": None}

    def _ask(self) -> None:
        try:
            # the editor answers, so the machine is up: "on", never "starting"
            state = power.machine_state(ha.Client(), power.load_power(), reachable=True)
        except Exception as err:  # Home Assistant away or refusing: said in the page, asked again later
            state = {"machine": "unknown", "watts": None, "error": str(err)}
        with self._lock:
            self._state, self._busy = state, False

    def forget(self) -> None:
        with self._lock:
            self._state, self._asked = None, 0.0


# --- voice.yaml with its history ------------------------------------------------------------------


def history_dir(root: Path, name: str) -> Path:
    return service.voice_dir(root, name) / HISTORY_DIR


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def save_voice_yaml(root: Path, name: str, text: str, note: str = "") -> config_mod.VoiceConfig:
    """Validate, keep the old file in the history (newest HISTORY), then write the text as it is:
    comments and layout stay, a changed field is one changed line."""
    old = service.config_yaml(root, name)
    data = yaml.safe_load(text) or {}
    cfg = config_mod.VoiceConfig.model_validate(data)  # raises on invalid values
    if cfg.name != name:
        raise ValueError("the name in voice.yaml must stay the same")
    folder = history_dir(root, name)
    folder.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    (folder / f"voice-{stamp}.yaml").write_text(old, encoding="utf-8")
    if note.strip():
        (folder / f"voice-{stamp}.note").write_text(note.strip(), encoding="utf-8")
    for extra in sorted(folder.glob("voice-*.yaml"))[:-HISTORY]:
        extra.unlink()
        extra.with_suffix(".note").unlink(missing_ok=True)
    path = service.voice_dir(root, name) / config_mod.CONFIG_FILE
    path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    return cfg


def with_workflow(text: str, workflow: str) -> str:
    """The text of voice.yaml with `workflow:` set: the one line changed, or added after `name:`."""
    line = f"workflow: {workflow}"
    if re.search(r"^workflow:.*$", text, re.M):
        return re.sub(r"^workflow:.*$", line, text, count=1, flags=re.M)
    match = re.search(r"^name:.*$", text, re.M)
    if not match:
        return f"{line}\n{text}"
    return f"{text[: match.end()]}\n{line}{text[match.end() :]}"


def match_workflow(root: Path, name: str) -> None:
    """An older imported voice has no `workflow: import` in voice.yaml, so the settings form showed
    "Cloning" while the tree showed "Own recordings"; the import report decides, once, in the file."""
    cfg = service.load_config(root, name)
    found = api.workflow(root, name, cfg)
    if found != cfg.workflow:
        text = with_workflow(service.config_yaml(root, name), found)
        save_voice_yaml(root, name, text, f"workflow: {found} (the voice has an import report)")


def voice_history(root: Path, name: str) -> list[dict]:
    folder = history_dir(root, name)
    found = sorted(folder.glob("voice-*.yaml"), reverse=True) if folder.is_dir() else []
    return [
        {
            "file": path.name,
            "saved": datetime.strptime(path.stem[6:21], "%Y%m%d-%H%M%S").strftime("%Y-%m-%d %H:%M:%S"),
            "text": path.read_text(encoding="utf-8"),
            "note": path.with_suffix(".note").read_text(encoding="utf-8")
            if path.with_suffix(".note").is_file()
            else "",
        }
        for path in found
    ]


def draft_path(root: Path, name: str) -> Path:
    return service.voice_dir(root, name) / DRAFT_FILE


def load_draft(root: Path, name: str) -> dict | None:
    try:
        return json.loads(draft_path(root, name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def validation_message(err: Exception) -> str:
    if isinstance(err, ValidationError):  # only the rules, not pydantic's wrapper
        return "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in err.errors())
    return str(err)


def base_checkpoints(root: Path) -> list[dict]:
    """Every base checkpoint with its size, epoch and metric (like a voice's export list)."""
    details = {
        item["path"]: item
        for quality in train_mod.QUALITIES
        for item in checkpoint_list(root, service.base_work_dir(root, quality))
    }
    return [
        {**details.get(path, {}), "label": label, "path": path, "quality": label.split(" · ")[0]}
        for label, path in service.base_checkpoint_choices(root)
    ]


def add_settings_routes(app: FastAPI, root: Path, need_voice, start, error) -> Machine:
    jobs: dict[str, JobManager] = app.state.jobs
    machine = Machine()

    # --- base model -------------------------------------------------------------------------------

    @app.get("/api/base")
    def base_view():
        report = service.base_score(root)
        common, results = service.compare_bases(root)
        return {
            "ready": service.base_ready(root),
            "bases_dir": str(service.bases_dir(root)),
            "dataset": (service.base_dataset_dir(root) / "metadata.csv").is_file(),
            "sources": [{"name": n, "clips": c, "folder": str(f)} for n, c, f in service.base_sources(root)],
            "runs": service.base_runs(root),
            "latest": service.latest_base_run(root),
            "checkpoints": base_checkpoints(root),
            "score": score_payload(root, report),
            "compare": {
                "common": common,
                "results": [
                    {
                        "quality": r.quality,
                        "last_epoch": r.last_epoch,
                        "mos_at": r.mos_at,
                        "mel_at": r.mel_at,
                        "best_mos": r.best_mos,
                        "best_mel": r.best_mel,
                    }
                    for r in results
                ],
            },
            "exports": [
                {"name": p.name, "url": rel(root, p), "size": p.stat().st_size}
                for p in sorted((service.bases_dir(root) / "export").glob("*.onnx*"))
            ],
        }

    @app.post("/api/base/prepare")
    def base_prepare(run: BasePrepare):
        if not run.folder.strip():
            raise error("base_dir_missing")
        args = ["base", "prepare", str(Path(run.folder.strip()).expanduser())]
        if run.audio_dir.strip():
            args += ["--audio-dir", run.audio_dir.strip()]
        return start("base-prepare", "", args)

    @app.post("/api/base/score")
    def base_score(run: BaseScore):
        if not (service.base_dataset_dir(root) / "metadata.csv").is_file():
            raise error("base_no_dataset")
        return start("base-score", "", ["base", "score", "--sample", str(run.sample)], slot="side")

    # --- recordings of a voice: their UTMOS, kept in dataset/utmos.json ---------------------------

    @app.get("/api/voices/{name}/score")
    def voice_score(name: str):
        need_voice(name)
        dataset = service.voice_dir(root, name) / "dataset"
        report = dataset_quality.current(dataset_quality.load(dataset), dataset)
        summary = None
        if report and report.get("scores"):
            summary = dataset_quality.summary(report) | {"texts": report.get("texts", {})}
            summary["created"] = report.get("created")
        has_dataset = (dataset / "metadata.csv").is_file()
        return {
            "dataset": has_dataset,
            "clips": len(read_metadata(dataset / "metadata.csv")) if has_dataset else 0,
            "target": dataset_quality.TARGET,
            "pruned": sorted(p.name for p in dataset.glob("pruned-*.csv")),
            "score": score_payload(root, summary, dataset / "wav"),
            # every score of the clips in the dataset, low to high: the page works out what a level keeps
            "values": sorted(round(v, 3) for v in (report or {}).get("scores", {}).values()),
        }

    @app.get("/api/voices/{name}/clips")
    def voice_clips(
        name: str,
        where: str = "dataset",
        below: float | None = None,
        order: str = "asc",
        offset: int = 0,
        limit: int = 100,
    ):
        """The scored clips one page at a time: in the dataset now or taken out of it (where=out)."""
        need_voice(name)
        if where not in ("dataset", "out") or order not in ("asc", "desc"):
            raise error("clips_bad_query")
        dataset = service.voice_dir(root, name) / "dataset"
        report = dataset_quality.load(dataset) or {}
        lines = read_metadata(dataset / "metadata.csv") if (dataset / "metadata.csv").is_file() else []
        ids = {u.id for u in lines}
        scores = report.get("scores", {})
        # the text as metadata.csv has it now, else as it was when scored (a clip taken out)
        texts = report.get("texts", {}) | {u.id: u.text for u in lines}
        found = [
            (clip, score)
            for clip, score in scores.items()
            if (clip in ids) == (where == "dataset") and (below is None or score < below)
        ]
        found.sort(key=lambda item: (item[1], item[0]), reverse=order == "desc")
        page = found[max(offset, 0) : max(offset, 0) + min(max(limit, 1), 500)]
        wav = dataset / "wav"
        return {
            "total": len(found),
            "unscored": len(ids - scores.keys()) if where == "dataset" else 0,
            "clips": [
                {
                    "id": clip,
                    "score": score,
                    "text": texts.get(clip, ""),
                    "url": rel(root, wav / f"{clip}.wav") if (wav / f"{clip}.wav").is_file() else None,
                }
                for clip, score in page
            ],
        }

    @app.post("/api/voices/{name}/score")
    def voice_score_run(name: str, run: BaseScore):
        need_voice(name)
        if not (service.voice_dir(root, name) / "dataset" / "metadata.csv").is_file():
            raise error("train_no_dataset")
        return start("score", name, ["score", name, "--sample", str(run.sample)], slot="side")

    @app.post("/api/voices/{name}/prune")
    def voice_prune(name: str, run: Prune):
        need_voice(name)
        if (run.below is None) == (run.keep_best is None):
            raise error("prune_choose")
        args = ["prune", name] + (
            ["--below", str(run.below)] if run.below is not None else ["--keep-best", str(run.keep_best)]
        )
        return start("prune", name, args)

    @app.post("/api/base/train")
    def base_train(run: BaseTrain):
        if run.quality not in ("medium", "high"):
            raise error("base_quality_unknown")
        if not (service.base_dataset_dir(root) / "metadata.csv").is_file():
            raise error("base_no_dataset")
        args = ["base", "train", "--max-epochs", str(run.epochs), "--quality", run.quality]
        if run.batch:
            args += ["--batch-size", str(run.batch)]
        return start("base-train", "", args, poweroff=run.poweroff)

    @app.post("/api/base/select")
    def base_select(run: Checkpoint):
        return start("base-select", "", ["base", "select", known_checkpoint(run.checkpoint)])

    @app.post("/api/base/export")
    def base_export(run: Checkpoint):
        return start("base-export", "", ["base", "export", "--checkpoint", known_checkpoint(run.checkpoint)])

    def known_checkpoint(path: str) -> str:
        if path not in {p for _label, p in service.base_checkpoint_choices(root)}:
            raise error("base_checkpoint")
        return path

    # --- ElevenLabs and Home Assistant ------------------------------------------------------------

    @app.get("/api/settings")
    def settings_view():
        from ..backends import elevenlabs

        connection = ha.load_connection()
        saved = power.load_power()
        return {
            "elevenlabs": {"key": bool(elevenlabs.load_api_key())},
            "ha": {
                "url": connection.url,
                "token_saved": ha.token_saved(),
                "token_rejected": ha.token_rejected(),
            },
            "power": {"switch": saved.switch, "sensor": saved.sensor, "off_watts": saved.off_watts},
        }

    @app.post("/api/settings/elevenlabs")
    def elevenlabs_key(key: Key):
        from ..backends import elevenlabs

        elevenlabs.save_api_key(key.key.strip())  # empty removes it
        return {"key": bool(elevenlabs.load_api_key())}

    @app.post("/api/settings/ha")
    def ha_save(connection: HaConnection):
        try:
            ha.save_connection(connection.url, connection.token.strip() or None)
        except ValueError as err:
            raise error("ha_invalid", str(err)) from err
        machine.forget()
        return settings_view()

    @app.delete("/api/settings/ha")
    def ha_remove():
        ha.remove_connection()
        machine.forget()
        return settings_view()

    @app.get("/api/settings/ha/entities")
    def ha_entities():
        if not ha.load_connection().ready:
            raise error("ha_missing")
        try:
            entities = ha.Client().entities()
        except ha.HaError as err:
            raise error("ha_failed", str(err), status=502) from err

        def pick(test):
            return sorted(
                (
                    {"id": e["entity_id"], "name": (e.get("attributes") or {}).get("friendly_name") or ""}
                    for e in entities
                    if test(e)
                ),
                key=lambda e: e["id"],
            )

        return {
            "switches": pick(lambda e: e["entity_id"].startswith(("switch.", "input_boolean."))),
            "sensors": pick(
                lambda e: (
                    e["entity_id"].startswith("sensor.")
                    and (e.get("attributes") or {}).get("unit_of_measurement") == "W"
                )
            ),
            "count": len(entities),
        }

    @app.post("/api/settings/power")
    def power_save(settings: PowerSettings):
        try:
            power.save_power(power.PowerSettings(settings.switch, settings.sensor, settings.off_watts))
        except ValueError as err:
            raise error("power_invalid", str(err)) from err
        machine.forget()
        return settings_view()

    @app.post("/api/machine/off")
    def machine_off():
        busy = [m.status() for m in jobs.values() if m.running()]
        if busy:
            raise error("machine_busy", status=409, kind=busy[0].kind, voice=busy[0].voice)
        try:
            power.power_off()
        except (RuntimeError, ha.HaError) as err:
            raise error("machine_off_failed", str(err), status=502) from err
        machine.forget()
        return {"ok": True}

    # --- each voice's settings --------------------------------------------------------------------

    @app.get("/api/voices/{name}/settings")
    def voice_settings(name: str):
        need_voice(name)
        match_workflow(root, name)
        cfg = service.load_config(root, name)
        saved = service.config_yaml(root, name)
        return {
            "yaml": saved,
            "hash": text_hash(saved),
            "draft": load_draft(root, name),
            "config": cfg.model_dump(mode="json"),
            "history": voice_history(root, name),
        }

    @app.put("/api/voices/{name}/settings/draft")
    def voice_draft_save(name: str, body: VoiceYaml):
        """Every change goes to the draft at once; voice.yaml changes only on Save."""
        need_voice(name)
        draft = {"text": body.text, "base": body.base, "at": datetime.now().isoformat(timespec="seconds")}
        draft_path(root, name).write_text(json.dumps(draft), encoding="utf-8")
        return draft

    @app.delete("/api/voices/{name}/settings/draft")
    def voice_draft_discard(name: str):
        need_voice(name)
        draft_path(root, name).unlink(missing_ok=True)
        return {"ok": True}

    @app.post("/api/voices/{name}/settings")
    def voice_settings_save(name: str, body: VoiceYaml):
        need_voice(name)
        current = service.config_yaml(root, name)
        if body.base and body.base != text_hash(current) and not body.force:
            raise error("conflict", status=409)  # voice.yaml changed since the edit began
        try:
            save_voice_yaml(root, name, body.text, body.note)
        except (ValueError, ValidationError, yaml.YAMLError) as err:
            raise error("yaml_invalid", validation_message(err)) from err
        draft_path(root, name).unlink(missing_ok=True)
        return voice_settings(name)

    @app.post("/api/voices/{name}/rename")
    def voice_rename(name: str, body: Rename):
        need_voice(name)
        for manager in jobs.values():
            status = manager.status()
            if status and status.running and (status.voice == name or status.kind == "train-queue"):
                raise error("rename_busy", status=409)
        try:
            cfg = service.rename_voice(root, name, body.name, body.piper_name)
        except (ValueError, ValidationError) as err:
            raise error("rename_failed", validation_message(err)) from err
        service.remember_voice(root, cfg.name)
        return {"name": cfg.name}

    return machine


def score_payload(root: Path, report: dict | None, wav: Path | None = None) -> dict | None:
    """The numbers of a scoring for the page (the base's clips, or the clips in `wav` of a voice)."""
    if report is None:
        return None
    wav = wav or service.base_dataset_dir(root) / "wav"

    def clips(items):
        return [
            {
                "url": rel(root, wav / f"{clip}.wav"),
                "text": f"{score:.2f} · {report['texts'].get(clip, clip)}",
            }
            for clip, score in items[:6]
            if (wav / f"{clip}.wav").is_file()
        ]

    return {
        "count": report["count"],
        "total": report["total"],
        "median": report["median"],
        "p10": report["p10"],
        "p90": report["p90"],
        "good": report["good"],
        "good_level": dataset_quality.GOOD,
        "below": report.get("below", {}),
        "created": report.get("created"),
        "worst": clips(report["worst"]),
        "best": clips(report["best"]),
    }
