"""The cloning way: recording → sentences → audition → generating clips → filter.

Every step that does real work is a `pvc` job (also the ones the old panel ran inside itself:
preparing the recording, choosing sentences, using another voice's sentences), so the page never
waits and the log shows what happened.
"""

from __future__ import annotations

from pathlib import Path
import shutil

from fastapi import FastAPI, UploadFile
from pydantic import BaseModel, Field

from .. import config as config_mod, reference as reference_mod
from ..synthesis import read_manifest, read_timing
from . import service
from .steps import clip_report, rel

BACKENDS = ("chatterbox", "xtts", "elevenlabs")
AUDIO_SUFFIXES = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".opus", ".aac", ".webm"}
SENTENCE_SUFFIXES = {".txt", ".tsv", ".csv"}


class ReferenceRun(BaseModel):
    embed: bool = True


class CorpusRun(BaseModel):
    bundled: bool = True
    size: int = Field(0, ge=0)


class AuditionRun(BaseModel):
    count: int = Field(12, ge=1, le=100)


class Pick(BaseModel):
    value: str


class SynthesizeRun(BaseModel):
    limit: int = Field(0, ge=0)


class FilterRun(BaseModel):
    target: int = Field(0, ge=0)
    asr: bool = True
    similarity: bool = True
    mos: bool = True


def save_upload(folder: Path, upload: UploadFile, allowed: set[str]) -> Path:
    name = Path(upload.filename or "").name
    if not name or Path(name).suffix.lower() not in allowed:
        raise ValueError(f"not a supported file: {name or '?'}")
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / name
    with target.open("wb") as out:
        shutil.copyfileobj(upload.file, out)
    return target


def files_in(folder: Path) -> list[str]:
    return sorted(p.name for p in folder.iterdir() if p.is_file()) if folder.is_dir() else []


def reference_view(root: Path, name: str) -> dict:
    directory = service.voice_dir(root, name)
    info = service.reference_info(directory)
    cfg = service.load_config(root, name)
    return {
        "uploads": files_in(directory / "reference" / "uploads"),
        "info": info,
        "short": bool(info) and reference_mod.is_short(info),
        "recommended": reference_mod.RECOMMENDED_SECONDS,
        "min_similarity": cfg.quality.min_similarity,
        "clips": [{"url": rel(root, p), "text": p.name} for p in service.reference_clips(root, name)],
        "backend": cfg.synthesis.backend,
    }


def corpus_view(root: Path, name: str) -> dict:
    directory = service.voice_dir(root, name)
    cfg = service.load_config(root, name)
    return {
        "sources": files_in(directory / "sources"),
        "prompts": service.prompt_count(root, name),
        "default_size": round(cfg.target_clips * cfg.synthesis.overgenerate),
        "target_clips": cfg.target_clips,
        "overgenerate": cfg.synthesis.overgenerate,
        "preview": [row[0] for row in service.corpus_preview(root, name)],
    }


def audition_view(root: Path, name: str, slug: str | None = None) -> dict:
    results = service.audition_results(root, name)
    slugs = [r["slug"] for r in results]
    chosen = slug if slug in slugs else (slugs[0] if slugs else None)
    clips = service.audition_clips(root, name, chosen) if chosen else []
    return {
        "rows": service.audition_table(results),
        "chosen": chosen,
        "clips": [{"url": rel(root, path), "text": text} for path, text in clips if path.is_file()],
        "options": service.load_config(root, name).synthesis.options,
        "prompts": service.prompt_count(root, name),
    }


def synthesize_view(root: Path, name: str) -> dict:
    from ..backends import elevenlabs

    directory = service.voice_dir(root, name)
    cfg = service.load_config(root, name)
    timing = read_timing(directory / "raw")
    prompts = service.prompt_count(root, name)
    sentences, characters = service.missing_sentences(root, name)
    return {
        "backend": cfg.synthesis.backend,
        "backends": list(BACKENDS),
        "prompts": prompts,
        "raw": len(read_manifest(directory / "raw")),
        "timing": (
            {
                "clips": timing.clips,
                "seconds": timing.seconds,
                "device": timing.device,
                "per_clip": timing.per_clip,
                "speed": timing.speed,
                "estimate": timing.per_clip * prompts,
            }
            if timing
            else None
        ),
        "elevenlabs": {
            "key": bool(elevenlabs.load_api_key()),
            "voice_id": cfg.synthesis.elevenlabs_voice_id,
            "voice_name": cfg.synthesis.elevenlabs_voice_name,
            "sets": [{"name": n, "count": c} for n, c in service.sentence_sets(root) if n != name],
            "missing_sentences": sentences,
            "missing_characters": characters,
        },
    }


def filter_view(root: Path, name: str) -> dict:
    directory = service.voice_dir(root, name)
    cfg = service.load_config(root, name)
    return {
        "target_clips": cfg.target_clips,
        "raw": len(read_manifest(directory / "raw")),
        "clips": service.dataset_size(root, name),
        "imported": (directory / "dataset" / "import_report.csv").is_file(),
        "report": clip_report(root, name),
    }


def add_clone_routes(app: FastAPI, root: Path, need_voice, start, error) -> None:
    def folder(name: str, part: str) -> Path:
        return service.voice_dir(root, name) / part

    def upload(name: str, part: str, files: list[UploadFile], allowed: set[str]) -> dict:
        need_voice(name)
        try:
            saved = [save_upload(folder(name, part), item, allowed).name for item in files]
        except ValueError as err:
            raise error("upload_kind", str(err)) from err
        return {"files": saved}

    def remove(name: str, part: str, file: str) -> dict:
        need_voice(name)
        path = folder(name, part) / Path(file).name
        if not path.is_file():
            raise error("unknown_file", status=404)
        path.unlink()
        return {"ok": True}

    # --- recording --------------------------------------------------------------------------------

    @app.get("/api/voices/{name}/reference")
    def reference_get(name: str):
        need_voice(name)
        return reference_view(root, name)

    @app.post("/api/voices/{name}/reference/upload")
    def reference_upload(name: str, files: list[UploadFile]):
        return upload(name, "reference/uploads", files, AUDIO_SUFFIXES)

    @app.delete("/api/voices/{name}/reference/uploads/{file}")
    def reference_remove(name: str, file: str):
        return remove(name, "reference/uploads", file)

    @app.post("/api/voices/{name}/reference")
    def reference_run(name: str, run: ReferenceRun):
        need_voice(name)
        uploads = sorted(p for p in folder(name, "reference/uploads").glob("*") if p.is_file())
        if not uploads:
            raise error("reference_no_files")
        args = ["reference", name, *map(str, uploads)] + ([] if run.embed else ["--no-embed"])
        return start("reference", name, args)

    # --- sentences --------------------------------------------------------------------------------

    @app.get("/api/voices/{name}/corpus")
    def corpus_get(name: str):
        need_voice(name)
        return corpus_view(root, name)

    @app.post("/api/voices/{name}/corpus/upload")
    def corpus_upload(name: str, files: list[UploadFile]):
        return upload(name, "sources", files, SENTENCE_SUFFIXES)

    @app.delete("/api/voices/{name}/corpus/sources/{file}")
    def corpus_remove(name: str, file: str):
        return remove(name, "sources", file)

    @app.post("/api/voices/{name}/corpus")
    def corpus_run(name: str, run: CorpusRun):
        need_voice(name)
        sources = sorted(p for p in folder(name, "sources").glob("*") if p.is_file())
        if not sources and not run.bundled:
            raise error("corpus_no_sources")
        args = ["corpus", name]
        for path in sources:
            args += ["--source", str(path)]
        if not run.bundled:
            args.append("--no-bundled")
        if run.size:
            args += ["--size", str(run.size)]
        return start("corpus", name, args)

    # --- audition ---------------------------------------------------------------------------------

    @app.get("/api/voices/{name}/audition")
    def audition_get(name: str, slug: str = ""):
        need_voice(name)
        return audition_view(root, name, slug or None)

    @app.post("/api/voices/{name}/audition")
    def audition_run(name: str, run: AuditionRun):
        need_voice(name)
        if not service.prompt_count(root, name):
            raise error("audition_no_sentences")
        return start("audition", name, ["audition", name, "--count", str(run.count)])

    @app.post("/api/voices/{name}/audition/apply")
    def audition_apply(name: str, pick: Pick):
        need_voice(name)
        try:
            return {"options": service.apply_audition(root, name, pick.value)}
        except ValueError as err:
            raise error("audition_pick_failed", str(err)) from err

    # --- generating -------------------------------------------------------------------------------

    @app.get("/api/voices/{name}/synthesize")
    def synthesize_get(name: str):
        need_voice(name)
        return synthesize_view(root, name)

    @app.post("/api/voices/{name}/synthesize/backend")
    def synthesize_backend(name: str, pick: Pick):
        need_voice(name)
        if pick.value not in BACKENDS:
            raise error("unknown_backend")
        try:
            service.set_backend(root, name, pick.value)
        except ValueError as err:  # an imported voice keeps its model
            raise error("backend_imported", str(err)) from err
        return synthesize_view(root, name)

    @app.get("/api/elevenlabs/voices")
    def elevenlabs_voices():
        from ..backends import elevenlabs

        try:
            found = elevenlabs.list_voices()
        except Exception as err:  # no key, wrong key, no connection: said in the page
            raise error("elevenlabs_failed", str(err), status=502) from err
        credits = elevenlabs.optional_credits()
        return {
            "voices": [{"id": v["id"], "name": v["name"], "category": v["category"]} for v in found],
            "credits": {"left": credits.left, "limit": credits.limit, "reset": credits.reset}
            if credits
            else None,
        }

    @app.post("/api/voices/{name}/synthesize/elevenlabs-voice")
    def synthesize_elevenlabs_voice(name: str, pick: Pick):
        from ..backends import elevenlabs

        need_voice(name)
        try:
            found = {v["id"]: v["name"] for v in elevenlabs.list_voices()}
        except Exception as err:
            raise error("elevenlabs_failed", str(err), status=502) from err
        if pick.value not in found:
            raise error("elevenlabs_unknown_voice")
        cfg = service.load_config(root, name)
        cfg.synthesis.elevenlabs_voice_id = pick.value
        cfg.synthesis.elevenlabs_voice_name = found[pick.value]
        config_mod.save(service.voice_dir(root, name), cfg)
        return synthesize_view(root, name)

    @app.post("/api/voices/{name}/synthesize/sentences")
    def synthesize_sentences(name: str, pick: Pick):
        need_voice(name)
        need_voice(pick.value)
        return start("sentences", name, ["sentences", name, pick.value])

    @app.post("/api/voices/{name}/synthesize")
    def synthesize_run(name: str, run: SynthesizeRun):
        need_voice(name)
        if not service.prompt_count(root, name):
            raise error("synthesize_no_sentences")
        args = ["synthesize", name] + (["--limit", str(run.limit)] if run.limit else [])
        return start("synthesize", name, args)

    # --- filter -----------------------------------------------------------------------------------

    @app.get("/api/voices/{name}/filter")
    def filter_get(name: str):
        need_voice(name)
        return filter_view(root, name)

    @app.post("/api/voices/{name}/filter")
    def filter_run(name: str, run: FilterRun):
        need_voice(name)
        if not read_manifest(folder(name, "raw")):
            raise error("filter_nothing")
        args = ["filter", name]
        if run.target:
            args += ["--target", str(run.target)]
        for check in ("asr", "similarity", "mos"):
            if not getattr(run, check):
                args.append(f"--no-{check}")
        return start("filter", name, args)
