"""`pvc` command line: init -> reference -> corpus -> audition -> synthesize -> filter -> train -> export."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import sys
from typing import Annotated

import typer

from . import config as config_mod, train as train_mod
from .dataset import summarize
from .languages import get_language

app = typer.Typer(no_args_is_help=True, add_completion=False, help=__doc__)
base_app = typer.Typer(no_args_is_help=True, help="Own base model trained from scratch (no English).")
app.add_typer(base_app, name="base")
remote_app = typer.Typer(no_args_is_help=True, help="The GPU machine over SSH: send, install, bring back.")
app.add_typer(remote_app, name="remote")
elevenlabs_app = typer.Typer(no_args_is_help=True, help="Voices of your ElevenLabs account.")
app.add_typer(elevenlabs_app, name="elevenlabs")

QUEUE_STATE = "train_queue.json"  # the voice training now, for the panel's chart

RootOption = Annotated[
    Path,
    typer.Option("--root", envvar="PVC_HOME", help="Directory holding voices/ and bases/ (private data)."),
]
TrainPython = Annotated[
    str,
    typer.Option(
        "--python", envvar="PVC_TRAIN_PYTHON", help="Python of the piper1-gpl training environment."
    ),
]


def _setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def voice_dir(root: Path, name: str) -> Path:
    return root / "voices" / name


def bases_dir(root: Path) -> Path:
    return root / "bases"


def privacy_warning(root: Path) -> str | None:
    """Warn when private voice data could end up in a git repository."""
    for parent in [root, *root.resolve().parents]:
        if (parent / ".git").exists():
            ignore = parent / ".gitignore"
            text = ignore.read_text(encoding="utf-8") if ignore.is_file() else ""
            if "voices/" not in text:
                return f"{root} is inside the git repository {parent} and voices/ is not in .gitignore"
            return None
    return None


def _load(root: Path, name: str):
    directory = voice_dir(root, name)
    cfg = config_mod.load(directory)
    return directory, cfg, get_language(cfg.language)


_state = {"root": Path(".")}


def _progress(label: str):
    """Print "progress <label> <done>/<total>" about every percent; the web UI turns it into a bar."""
    last = [-1]

    def report(done: int, total: int) -> None:
        step = max(1, total // 100)
        if done == total or done - last[0] >= step:
            last[0] = done
            typer.echo(f"progress {label} {done}/{total}")

    return report


@app.callback()
def main(root: RootOption = Path(".")) -> None:
    _setup_logging()
    _state["root"] = root
    warning = privacy_warning(root)
    if warning:
        typer.secho(f"WARNING: {warning}", fg=typer.colors.YELLOW, err=True)


@app.command()
def init(
    name: str,
    language: str = "pl",
    backend: str = "chatterbox",
    base: Annotated[
        str | None,
        typer.Option(help="bazowy-pl | lessac | ckpt:<path>; default: bazowy-pl once it exists, else lessac"),
    ] = None,
    piper_name: Annotated[str | None, typer.Option(help="Output file stem, e.g. pl_PL-kuba_bajka")] = None,
) -> None:
    """Create voices/<name>/voice.yaml."""
    root = _state["root"]
    if base is None:
        ready = (bases_dir(root) / train_mod.SCRATCH_BASE).is_file()
        base = config_mod.POLISH_BASE if ready else "lessac"
    get_language(language)
    directory = voice_dir(root, name)
    if (directory / config_mod.CONFIG_FILE).exists():
        raise typer.BadParameter(f"{directory} already exists")
    cfg = config_mod.VoiceConfig(
        name=name,
        language=language,
        piper_name=piper_name,
        synthesis=config_mod.SynthesisConfig(backend=backend),
        train=config_mod.TrainConfig(base=base),
    )
    typer.echo(f"Created {config_mod.save(directory, cfg)}")


@app.command()
def reference(
    name: str,
    clips: list[Path],
    embed: Annotated[bool, typer.Option(help="Compute speaker embedding (needs sherpa-onnx).")] = True,
) -> None:
    """Clean reference recordings and calibrate the similarity threshold."""
    root = _state["root"]
    from . import reference as reference_mod

    directory, cfg, _lang = _load(root, name)
    embedder = None
    if embed:
        from .quality.speaker import DEFAULT_MODEL, SpeakerEmbedder, ensure_model

        embedder = SpeakerEmbedder(ensure_model(DEFAULT_MODEL, root / "models")).embed
    info = reference_mod.prepare(clips, directory / "reference", embedder)
    if "min_similarity" in info:
        cfg.quality.min_similarity = info["min_similarity"]
        config_mod.save(directory, cfg)
    typer.echo(json.dumps(info, indent=2))
    if reference_mod.is_short(info):
        typer.secho(
            f"Short reference ({info['seconds']} s, {len(info['prompts'])} prompt(s)): cloning works, but "
            "30-60 s of varied speech gives a steadier voice and a surer similarity threshold.",
            fg=typer.colors.YELLOW,
        )


@app.command()
def corpus(
    name: str,
    source: Annotated[
        list[Path], typer.Option("--source", help="Sentence file (txt or id<TAB>text), repeatable.")
    ],
    size: Annotated[
        int | None, typer.Option(help="Prompts to select (default target * overgenerate).")
    ] = None,
    bundled: Annotated[bool, typer.Option(help="Add the language pack's own sentences.")] = True,
) -> None:
    """Select plain-text prompts with good phoneme coverage."""
    root = _state["root"]
    from . import corpus as corpus_mod
    from .dataset import write_report

    directory, cfg, lang = _load(root, name)
    sources = list(source) + (lang.prompt_paths() if bundled else [])
    size = size or round(cfg.target_clips * cfg.synthesis.overgenerate)
    prompts, report = corpus_mod.build(sources, lang, size, corpus_mod.espeak_phonemizer(lang))
    corpus_mod.write_prompts(directory / corpus_mod.PROMPTS, prompts)
    write_report(directory / "corpus_report.csv", report, ["source", "text", "reason"])
    typer.echo(summarize(report))
    typer.echo(f"Selected {len(prompts)} prompts -> {directory / corpus_mod.PROMPTS}")


@app.command()
def sentences(
    name: str,
    source: Annotated[str, typer.Argument(help="Voice whose dataset sentences to read, e.g. marek.")],
) -> None:
    """Use exactly the sentences of another voice, so that every voice reads the same set."""
    root = _state["root"]
    from . import corpus as corpus_mod

    directory, _cfg, _lang = _load(root, name)
    count = corpus_mod.use_dataset_sentences(directory, voice_dir(root, source))
    typer.echo(f"{count} sentences of {source} -> {directory / corpus_mod.PROMPTS}")


@elevenlabs_app.command("voices")
def elevenlabs_voices() -> None:
    """List the voices of the account and the credits left."""
    from .backends import elevenlabs

    for item in elevenlabs.list_voices():
        typer.echo(f"{item['id']}  {item['name']} ({item['category']})")
    credits = elevenlabs.optional_credits()
    typer.echo(f"Credits left: {credits.left} of {credits.limit}" if credits else "Credits: unknown")


@elevenlabs_app.command("pick")
def elevenlabs_pick(name: str, voice_id: str) -> None:
    """Make an ElevenLabs voice the one that reads the sentences of this voice."""
    from .backends import elevenlabs

    directory, cfg, _lang = _load(_state["root"], name)
    found = {item["id"]: item["name"] for item in elevenlabs.list_voices()}
    if voice_id not in found:
        raise typer.BadParameter(f"no voice {voice_id} in the account (`pvc elevenlabs voices`)")
    cfg.synthesis.backend = "elevenlabs"
    cfg.synthesis.options = {}
    cfg.synthesis.elevenlabs_voice_id = voice_id
    cfg.synthesis.elevenlabs_voice_name = found[voice_id]
    config_mod.save(directory, cfg)
    typer.echo(f"{name} is read by {found[voice_id]}")


def _synthesizer(cfg, lang):
    from . import backends

    synth = backends.create(
        cfg.synthesis.backend,
        lang.synth_language,
        cfg.synthesis.options,
        **({"voice_id": cfg.synthesis.elevenlabs_voice_id} if cfg.synthesis.backend == "elevenlabs" else {}),
    )
    if synth.remote:
        typer.secho("NOTE: this backend sends the text to a cloud service.", fg=typer.colors.YELLOW, err=True)
    return synth


def _references(directory: Path, cfg) -> list[Path]:
    """Recordings to clone from; an ElevenLabs voice lives in the account and needs none."""
    from .reference import prompt_paths

    if cfg.synthesis.backend == "elevenlabs":
        return [Path("-")]
    return prompt_paths(directory / "reference")


def _checks(root: Path, directory: Path, cfg, lang, *, asr: bool, similarity: bool, mos: bool):
    from .reference import load_embedding
    from .screening import Checks

    checks = Checks()
    if asr:
        from .quality.asr import WhisperChecker

        checks.cer = WhisperChecker(lang, cfg.quality.asr_model)
    if similarity:
        embedding = load_embedding(directory / "reference")
        if embedding is None:
            checks.skipped.append("similarity (no reference embedding)")
        else:
            from .quality.speaker import DEFAULT_MODEL, SpeakerEmbedder, ensure_model

            checks.embed = SpeakerEmbedder(ensure_model(DEFAULT_MODEL, root / "models")).embed
            checks.reference_embedding = embedding
    if mos:
        from .quality.mos import MosPredictor

        checks.mos = MosPredictor().score
    return checks


@app.command()
def audition(
    name: str,
    count: int = 12,
    apply_best: Annotated[bool, typer.Option(help="Store the best settings in voice.yaml.")] = False,
    mos: bool = True,
) -> None:
    """Compare backend settings on a few prompts (audition/audition.html)."""
    root = _state["root"]
    from . import audition as audition_mod, corpus as corpus_mod

    directory, cfg, lang = _load(root, name)
    prompts = corpus_mod.read_prompts(directory / corpus_mod.PROMPTS)[:count]
    synth = _synthesizer(cfg, lang)
    checks = _checks(root, directory, cfg, lang, asr=True, similarity=True, mos=mos)
    grid = audition_mod.DEFAULT_GRIDS.get(cfg.synthesis.backend, {})
    results = audition_mod.run(
        synth,
        dict(cfg.synthesis.options),
        grid,
        prompts,
        _references(directory, cfg),
        directory / "audition",
        checks,
    )
    for combo in results:
        typer.echo(f"{combo.score:7.3f}  {combo.slug}")
    typer.echo(f"Listen: {directory / 'audition' / 'audition.html'}")
    if apply_best and results:
        cfg.synthesis.options = {**cfg.synthesis.options, **results[0].options}
        config_mod.save(directory, cfg)
        typer.echo(f"Saved best settings: {results[0].options}")


@app.command()
def synthesize(
    name: str,
    limit: Annotated[int | None, typer.Option(help="Only the first N prompts (test run).")] = None,
) -> None:
    """Generate raw clips for all prompts (resumable)."""
    root = _state["root"]
    from . import corpus as corpus_mod, synthesis
    from .backends.base import FatalSynthesisError

    directory, cfg, lang = _load(root, name)
    prompts = corpus_mod.read_prompts(directory / corpus_mod.PROMPTS)
    if limit:
        prompts = prompts[:limit]
    jobs = synthesis.plan(prompts, _references(directory, cfg), cfg.synthesis.seeds)
    try:
        synth = _synthesizer(cfg, lang)
        made = synthesis.run(synth, jobs, directory / "raw", progress=_progress("synthesize"))
    except FatalSynthesisError as err:
        typer.secho(f"Stopped: {err}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from err
    typer.echo(f"Generated {made} new clips in {directory / 'raw'}")
    timing = synthesis.read_timing(directory / "raw")
    if made and timing:
        typer.echo(timing.describe())


@app.command("filter")
def filter_(
    name: str,
    target: Annotated[int | None, typer.Option(help="Clips to keep (default target_clips).")] = None,
    asr: bool = True,
    similarity: bool = True,
    mos: bool = True,
) -> None:
    """Check raw clips and build dataset/ (metadata.csv + 22050 Hz WAV)."""
    root = _state["root"]
    from .screening import screen

    directory, cfg, lang = _load(root, name)
    checks = _checks(root, directory, cfg, lang, asr=asr, similarity=similarity, mos=mos)
    for skipped in checks.skipped:
        typer.secho(f"skipped check: {skipped}", fg=typer.colors.YELLOW, err=True)
    try:
        rows = screen(
            directory / "raw",
            directory / "dataset",
            cfg.quality,
            target or cfg.target_clips,
            checks,
            progress=_progress("filter"),
        )
    except ValueError as err:
        typer.secho(f"Stopped: {err}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from err
    typer.echo(summarize(rows))


@app.command("import")
def import_(
    name: str,
    legacy_dir: Path,
    metadata: Annotated[
        list[Path] | None, typer.Option(help="Metadata files (default metadata.csv).")
    ] = None,
    persona: Annotated[list[Path] | None, typer.Option(help="Metadata written as numbered lists.")] = None,
    audio_dir: Annotated[Path | None, typer.Option(help="Audio folder (default <legacy_dir>/wav).")] = None,
    verify: Annotated[bool, typer.Option(help="Check every clip with Whisper (slow, needs GPU).")] = False,
) -> None:
    """Clean an existing LJSpeech dataset into voices/<name>/dataset/ (text rules + real WAV)."""
    root = _state["root"]
    from .importer import Source, import_dataset

    directory, cfg, lang = _load(root, name)
    sources = [Source(p) for p in (metadata or [legacy_dir / "metadata.csv"])]
    sources += [Source(p, persona=True) for p in (persona or [])]
    verifier = None
    if verify:
        from .quality.asr import WhisperChecker

        verifier = WhisperChecker(lang, cfg.quality.asr_model)
    rows = import_dataset(
        sources,
        audio_dir or legacy_dir / "wav",
        directory / "dataset",
        lang,
        verify=verifier,
        max_cer=cfg.quality.max_cer,
        progress=_progress("import"),
    )
    typer.echo(summarize(rows))


def _run_info(work_dir: Path) -> dict:
    path = work_dir / "run.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _train(
    voice_name: str,
    paths: train_mod.TrainPaths,
    lang,
    train_cfg,
    ckpt: Path | None,
    python: str,
    *,
    dry_run: bool,
    resume: bool,
    quality: str = "medium",
) -> None:
    info = _run_info(paths.work_dir)
    last = train_mod.resume_checkpoint(paths.work_dir) if resume else None
    if last is not None and info:
        start_epoch, quality = int(info["start_epoch"]), info.get("quality", "medium")
        ckpt = last
        typer.echo(f"Resuming from {last}")
        try:
            reached = train_mod.checkpoint_info(last, python=python).epoch
        except train_mod.TrainError:
            reached = None
        planned = start_epoch + train_cfg.max_epochs
        if reached is not None and reached >= planned:
            # the earlier run is done: Lightning refuses max_epochs below the checkpoint's epoch,
            # so the epochs now count on top of the checkpoint
            typer.echo(
                f"The planned {planned} epochs are done (checkpoint at epoch {reached}); "
                f"training {train_cfg.max_epochs} more"
            )
            start_epoch = reached
            info["start_epoch"] = start_epoch
            if not dry_run:
                (paths.work_dir / "run.json").write_text(json.dumps(info), encoding="utf-8")
    elif ckpt is not None:
        # fine-tuning keeps the model size of the starting checkpoint
        found = train_mod.checkpoint_info(ckpt, python=python)
        start_epoch, quality = found.epoch, found.quality
    else:
        start_epoch = 0
    cmd = train_mod.fit_command(
        voice_name, paths, lang, train_cfg, ckpt, start_epoch=start_epoch, quality=quality, python=python
    )
    if dry_run:
        typer.echo(" ".join(cmd))
        return
    if not paths.metadata.is_file():
        raise typer.BadParameter(f"{paths.metadata} missing - run `pvc filter` or `pvc import` first")
    paths.work_dir.mkdir(parents=True, exist_ok=True)
    if not info:
        (paths.work_dir / "run.json").write_text(
            json.dumps(
                {"start_epoch": start_epoch, "base": str(ckpt) if ckpt else "random", "quality": quality}
            ),
            encoding="utf-8",
        )
    # the web UI reads this line for the whole-run progress bar and the time left
    typer.echo(f"training epochs {start_epoch}-{start_epoch + train_cfg.max_epochs}")
    train_mod.run(cmd)


def _samples(work_dir: Path, title: str, out: Path | None) -> None:
    from . import train_monitor

    try:
        path = train_monitor.export_samples(work_dir, title, out)
    except ValueError as err:
        raise typer.BadParameter(str(err)) from err
    typer.echo(f"{path} ({path.stat().st_size / 1e6:.0f} MB) - open index.html inside to listen")


@app.command()
def samples(
    name: str,
    out: Annotated[Path | None, typer.Option(help="ZIP file (default <run>/monitor/samples.zip).")] = None,
) -> None:
    """ZIP of the training samples of every kept epoch (all epochs with a checkpoint) to listen offline."""
    directory, _cfg, _lang = _load(_state["root"], name)
    _samples(directory / "train", f"{name}-samples", out)


@app.command()
def train(
    name: str,
    base: Annotated[
        str | None, typer.Option(help="bazowy-pl | lessac | ckpt:<path> (overrides voice.yaml)")
    ] = None,
    python: TrainPython = sys.executable,
    resume: bool = True,
    dry_run: bool = False,
) -> None:
    """Fine-tune a Piper voice on dataset/ (medium or high, like the starting checkpoint)."""
    root = _state["root"]
    directory, cfg, lang = _load(root, name)
    train_cfg = cfg.train.model_copy(update={"base": base}) if base else cfg.train
    config_mod.TrainConfig.model_validate(train_cfg.model_dump())
    ckpt = train_mod.resolve_base(train_cfg.base, bases_dir(root), download=not dry_run)
    paths = train_mod.TrainPaths(directory / "dataset", directory / "train")
    _train(cfg.name, paths, lang, train_cfg, ckpt, python, dry_run=dry_run, resume=resume)


@app.command("train-queue")
def train_queue(
    names: Annotated[list[str], typer.Argument(help="Voices in training order.")],
    epochs: Annotated[int, typer.Option(help="Epochs for every voice.")] = 500,
    base: Annotated[str | None, typer.Option(help="bazowy-pl | lessac | ckpt:<path>")] = None,
    python: TrainPython = sys.executable,
) -> None:
    """Train voices one after another; a failed voice does not stop the next one, Ctrl+C stops all."""
    root = _state["root"]
    failed = []
    for index, name in enumerate(names, 1):
        (root / "jobs").mkdir(exist_ok=True)
        (root / "jobs" / QUEUE_STATE).write_text(json.dumps({"voice": name}), encoding="utf-8")
        typer.echo(f"queue {index}/{len(names)}: {name}")
        try:
            directory, cfg, _lang = _load(root, name)
            cfg.train.max_epochs = epochs
            config_mod.save(directory, cfg)
            train(name, base=base, python=python, resume=True, dry_run=False)
        except (train_mod.TrainError, typer.BadParameter, FileNotFoundError) as err:
            typer.secho(f"queue: {name} failed: {err}", fg=typer.colors.RED, err=True)
            failed.append(name)
    typer.echo(f"queue finished: {len(names) - len(failed)} of {len(names)} voices trained")
    if failed:
        raise typer.Exit(1)


@app.command()
def export(
    name: str,
    checkpoint: Annotated[Path | None, typer.Option(help="Default: newest last.ckpt.")] = None,
    python: TrainPython = sys.executable,
) -> None:
    """Export the trained voice to export/<locale>-<name>-<medium|high>.onnx (+ .onnx.json)."""
    root = _state["root"]
    directory, cfg, lang = _load(root, name)
    paths = train_mod.TrainPaths(directory / "dataset", directory / "train")
    checkpoint = checkpoint or train_mod.latest_checkpoint(paths.work_dir)
    if checkpoint is None:
        raise typer.BadParameter("no checkpoint found - train first or pass --checkpoint")
    quality = train_mod.checkpoint_info(checkpoint, python=python).quality
    onnx_file = directory / "export" / f"{cfg.file_stem(lang.locale, quality)}.onnx"
    onnx_file.parent.mkdir(parents=True, exist_ok=True)
    train_mod.run(train_mod.export_command(checkpoint, onnx_file, python=python))
    typer.echo(f"Exported {onnx_file} and {train_mod.finish_export(paths, onnx_file, quality)}")


@app.command()
def ui(
    host: Annotated[
        str, typer.Option(help="0.0.0.0 = reachable from other computers in the LAN.")
    ] = "0.0.0.0",
    port: int = 7860,
    lang: Annotated[str, typer.Option(help="UI language: en or pl.")] = "en",
    auth: Annotated[
        str | None, typer.Option(envvar="PVC_UI_AUTH", help="user:password to protect the page.")
    ] = None,
) -> None:
    """Web interface for all steps (needs gradio: pip install -e '.[ui]')."""
    root = _state["root"]
    from .webui.app import launch

    credentials = tuple(auth.split(":", 1)) if auth else None
    if credentials is not None and len(credentials) != 2:
        raise typer.BadParameter("--auth must be user:password")
    shown = "localhost" if host in ("127.0.0.1", "0.0.0.0") else host
    typer.echo(f"Piper Voice Cloner: http://{shown}:{port}/{lang}/   data: {root}   (Ctrl+C stops)")
    launch(root, lang, host, port, credentials)


# --- own base model -------------------------------------------------------------------------

BASE_NAME = train_mod.BASE_FOLDER
Quality = Annotated[
    str, typer.Option(help="Model size: medium (Piper default) or high (8x larger decoder, cleaner audio).")
]


def base_work(root: Path, quality: str = "medium") -> Path:
    try:
        return train_mod.base_folder(bases_dir(root), quality)
    except train_mod.TrainError as err:
        raise typer.BadParameter(str(err)) from err


def base_dataset(root: Path) -> Path:
    return train_mod.base_dataset(bases_dir(root))


@base_app.command("prepare")
def base_prepare(
    source_dir: Path,
    language: str = "pl",
    metadata: Annotated[
        list[Path] | None, typer.Option(help="Metadata files (default metadata.csv).")
    ] = None,
    audio_dir: Annotated[Path | None, typer.Option(help="Audio folder (default <source_dir>/wav).")] = None,
) -> None:
    """Clean a large single-speaker dataset (e.g. MC Speech, CC0) for the base model."""
    root = _state["root"]
    from .importer import Source, import_dataset

    lang = get_language(language)
    out_dir = base_dataset(root)
    rows = import_dataset(
        [Source(p) for p in (metadata or [source_dir / "metadata.csv"])],
        audio_dir or source_dir / "wav",
        out_dir,
        lang,
        progress=_progress("base-prepare"),
    )
    typer.echo(summarize(rows))


@base_app.command("train")
def base_train(
    language: str = "pl",
    max_epochs: int = 3000,
    quality: Quality = "medium",
    batch_size: Annotated[int | None, typer.Option(help="Default: 32 for medium, 16 for high.")] = None,
    python: TrainPython = sys.executable,
    resume: bool = True,
    dry_run: bool = False,
) -> None:
    """Train the base voice from random weights - nothing English inside."""
    root = _state["root"]
    lang = get_language(language)
    paths = train_mod.TrainPaths(base_dataset(root), base_work(root, quality) / "train")
    train_cfg = config_mod.TrainConfig(
        max_epochs=max_epochs, batch_size=batch_size or train_mod.DEFAULT_BATCH[quality]
    )
    _train(BASE_NAME, paths, lang, train_cfg, None, python, dry_run=dry_run, resume=resume, quality=quality)


@base_app.command("score")
def base_score(
    sample: Annotated[int, typer.Option(help="Clips to score at random; 0 = all of them.")] = 300,
    python: TrainPython = sys.executable,
) -> None:
    """Rate the base recordings with UTMOS (the val_mos predictor): the quality ceiling of the base."""
    root = _state["root"]
    from . import dataset_quality

    dataset = base_dataset(root)
    if not (dataset / "metadata.csv").is_file():
        raise typer.BadParameter(f"{dataset / 'metadata.csv'} missing - run `pvc base prepare` first")
    report = dataset_quality.score_dataset(dataset, sample, python=python, progress=_progress("base-score"))
    typer.echo(dataset_quality.describe(report))


@base_app.command("samples")
def base_samples(
    quality: Quality = "medium",
    out: Annotated[Path | None, typer.Option(help="ZIP file (default <run>/monitor/samples.zip).")] = None,
) -> None:
    """ZIP of the training samples of every kept epoch (all epochs with a checkpoint) to listen offline."""
    _samples(base_work(_state["root"], quality) / "train", f"{BASE_NAME}-{quality}-samples", out)


@base_app.command("export")
def base_export(
    checkpoint: Annotated[Path | None, typer.Option(help="Default: the chosen bazowy-pl.")] = None,
    name: Annotated[str | None, typer.Option(help="File stem, default <locale>-bazowy.")] = None,
    language: str = "pl",
    python: TrainPython = sys.executable,
) -> None:
    """Export a base checkpoint as a voice to bases/export/<name>-<medium|high>.onnx (+ .onnx.json)."""
    root = _state["root"]
    checkpoint = checkpoint or bases_dir(root) / train_mod.SCRATCH_BASE
    if not checkpoint.is_file():
        raise typer.BadParameter(f"{checkpoint} not found - train a base first")
    quality = train_mod.checkpoint_info(checkpoint, python=python).quality
    stem = name or f"{get_language(language).locale}-bazowy"
    onnx_file = bases_dir(root) / "export" / f"{stem}-{quality}.onnx"
    onnx_file.parent.mkdir(parents=True, exist_ok=True)
    paths = train_mod.TrainPaths(base_dataset(root), base_work(root, quality) / "train")
    train_mod.run(train_mod.export_command(checkpoint, onnx_file, python=python))
    typer.echo(f"Exported {onnx_file} and {train_mod.finish_export(paths, onnx_file, quality)}")


@base_app.command("select")
def base_select(checkpoint: Path) -> None:
    """Use this checkpoint as the `bazowy-pl` base of every voice (bases/pl-scratch.ckpt)."""
    root = _state["root"]
    import shutil

    if not checkpoint.is_file():
        raise typer.BadParameter(f"{checkpoint} not found")
    target = bases_dir(root) / train_mod.SCRATCH_BASE
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(checkpoint, target)
    typer.echo(f"{checkpoint} -> {target}")


# --- GPU machine over SSH -------------------------------------------------------------------------


def _remote():
    from . import remote

    config = remote.load_config(_state["root"])
    if config is None:
        raise typer.BadParameter("no server yet: pvc remote configure <host> (or the web UI, Tools)")
    return remote, remote.Remote(config)


def _short_command(command: list[str]) -> str:
    """The command for the log: without the long SSH options, and the remote script shortened."""
    import shlex

    shown, skip = [], False
    for part in command:
        if skip:
            skip = False
            continue
        if part in ("-o", "-p", "-i", "-e"):
            skip = True
            continue
        part = " ".join(part.split()) if "\n" in part else part  # a remote script on one line
        shown.append(part if len(part) <= 120 else part[:117] + "...")
    return shlex.join(shown)


def _run_all(commands: list[list[str]]) -> None:
    """Run one after another with the output in this terminal (or the job log); stop at the first error."""
    import subprocess

    for command in commands:
        typer.echo("$ " + _short_command(command))
        code = subprocess.run(command, check=False).returncode
        if code != 0:
            typer.secho(f"failed (exit code {code})", fg=typer.colors.RED, err=True)
            raise typer.Exit(code)


@remote_app.command("configure")
def remote_configure(
    host: str,
    user: str = "",
    port: int = 22,
    key: Annotated[str, typer.Option(help="Private key file (default: ssh-agent, ~/.ssh/config).")] = "",
    remote_dir: Annotated[str, typer.Option(help="Folder in the home directory on the machine.")] = (
        "piper-voice-cloner"
    ),
    ui_port: int = 7860,
) -> None:
    """Save the GPU machine (server.json in the data folder, no secrets)."""
    from . import remote

    config = remote.ServerConfig(host, user, port, key, remote_dir, ui_port)
    try:
        typer.echo(f"Saved {remote.save_config(_state['root'], config)}")
    except ValueError as err:
        raise typer.BadParameter(str(err)) from err


@remote_app.command("check")
def remote_check() -> None:
    """Connect and list the GPU, free disk and the tools the setup needs."""
    _remote_mod, server = _remote()
    _run_all(server.check())


def _check_status(remote, server, *, echo: bool = True) -> list | None:
    """Ask the machine, save the answer for the web UI checklist and print the checklist."""
    import subprocess

    root = _state["root"]
    if echo:
        typer.echo("$ " + _short_command(server.status()))
    done = subprocess.run(server.status(), capture_output=True, text=True, check=False)
    try:
        status = remote.parse_status(done.stdout)
    except RuntimeError as err:
        error = (done.stderr.strip().splitlines() or [str(err)])[-1]
        remote.save_status(root, None, error)
        typer.secho(f"no answer from the machine: {error}", fg=typer.colors.RED, err=True)
        return None
    remote.save_status(root, status)
    items = remote.evaluate(status, server.config, remote.local_voices(root), remote.code_stamp())
    if echo:
        for item in items:
            line = f"[{item.state:>6}] {item.key}" + (f": {item.detail}" if item.detail else "")
            typer.echo(line + (f"\n         run yourself: {item.command}" if item.command else ""))
        typer.echo(f"=> {remote.summary(items)}")
    return items


def _refresh_status(remote, server) -> None:
    """After push/install: the checklist shows the new state (a failure here changes nothing)."""
    import contextlib

    with contextlib.suppress(OSError):
        _check_status(remote, server, echo=False)


@remote_app.command("status")
def remote_status() -> None:
    """The checklist: what the machine has and what is still to do (also shown in the web UI)."""
    remote, server = _remote()
    if _check_status(remote, server) is None:
        raise typer.Exit(255)


@remote_app.command("prepare")
def remote_prepare() -> None:
    """Do everything the checklist allows: packages (sudo without password), uv, push, install."""
    import subprocess

    remote, server = _remote()
    items = _check_status(remote, server)
    if items is None:
        raise typer.Exit(255)
    by_key = {item.key: item for item in items}
    manual = [item for item in items if item.state == "manual"]
    for item in manual:
        typer.secho(f"do this yourself first ({item.key}): {item.command}", fg=typer.colors.YELLOW)
    if by_key["tools"].state == "manual":
        raise typer.Exit(1)  # setup.sh cannot build without them
    status = remote.load_status(_state["root"])["status"]
    commands = []
    if by_key["tools"].state == "todo":
        commands.append(server.apt_install(remote.apt_packages(status)))
    if by_key["uv"].state == "todo":
        commands.append(server.install_uv())
    commands += server.push(_state["root"])
    needs_install = any(
        by_key[key].state != "ok" for key in ("code", "venv", "train", "service", "tensorboard")
    )
    if needs_install:
        job = remote.parse_job_state(
            subprocess.run(server.job_state(), capture_output=True, text=True, check=False).stdout
        )
        if job["running"]:
            typer.secho(
                f"a job is running on the machine: {job['kind']} - the install waits until it ends "
                "(it would change the environment under it); code and data are sent now and the web "
                "UI restarts with the new code (the job keeps running)",
                fg=typer.colors.YELLOW,
            )
            needs_install = False
            if status.get("service") == "active":
                commands.append(server.restart_ui())
    if needs_install:
        commands += server.install()
    try:
        _run_all(commands)
    finally:
        typer.echo("")
        _check_status(remote, server)
    typer.echo(f"Web UI on the machine: {server.config.ui_url}")


@remote_app.command("push")
def remote_push() -> None:
    """Send the code and the voice data (only changes; nothing is deleted on the machine)."""
    remote, server = _remote()
    _run_all(server.push(_state["root"]))
    _refresh_status(remote, server)
    typer.echo("progress push 1/1")


@remote_app.command("install")
def remote_install() -> None:
    """Install or update the environments and the web UI service on the machine (after push)."""
    remote, server = _remote()
    _run_all(server.install())
    _refresh_status(remote, server)
    typer.echo(f"Web UI on the machine: {server.config.ui_url}")


@remote_app.command("pull")
def remote_pull() -> None:
    """Bring the exported voices (voices/*/export/) back to this computer."""
    _remote_mod, server = _remote()
    _run_all(server.pull(_state["root"]))


if __name__ == "__main__":
    app(prog_name=os.path.basename(sys.argv[0]))
