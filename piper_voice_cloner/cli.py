"""`pvc` command line: init -> reference -> corpus -> audition -> synthesize -> filter -> train -> export."""

from __future__ import annotations

import json
import logging
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
        list[Path] | None,
        typer.Option("--source", help="Sentence file (txt or id<TAB>text), repeatable."),
    ] = None,
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
    sources = list(source or []) + (lang.prompt_paths() if bundled else [])
    if not sources:
        raise typer.BadParameter("no sentences: give --source files or keep the bundled ones")
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
    # only a checkpoint of the current run: never one of a run before a "start over"
    last = train_mod.resume_checkpoint(paths.work_dir, current_run=True) if resume else None
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
    if not (last is not None and info):  # a new run (also "start over"): its own start, not the last one's
        from . import train_monitor

        # the new run is the next lightning_logs/version_N; the samples and the chart of the run before
        # go whole to runs/ (nothing of it is deleted), its checkpoints stay where they are
        new = {
            "start_epoch": start_epoch,
            "base": str(ckpt) if ckpt else "random",
            "quality": quality,
            "first_version": train_monitor.next_version(paths.work_dir),
        }
        (paths.work_dir / "run.json").write_text(json.dumps(new), encoding="utf-8")
        if info:
            kept = train_monitor.archive_monitor(paths.work_dir, info)
            if kept:
                typer.echo(f"The earlier run is kept in {kept}")
    # the web UI reads this line for the whole-run progress bar and the time left
    typer.echo(f"training epochs {start_epoch}-{start_epoch + train_cfg.max_epochs}")
    if ckpt is not None:
        train_mod.make_loadable(ckpt, python=python)
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
    # a file exported before is never overwritten: the new one gets the next number
    onnx_file = train_mod.free_export_path(directory / "export", cfg.file_stem(lang.locale, quality))
    onnx_file.parent.mkdir(parents=True, exist_ok=True)
    train_mod.run(train_mod.export_command(checkpoint, onnx_file, python=python))
    typer.echo(f"Exported {onnx_file} and {train_mod.finish_export(paths, onnx_file, quality)}")


@app.command()
def editor(
    host: Annotated[
        str, typer.Option(help="0.0.0.0 = reachable from other computers in the LAN.")
    ] = "0.0.0.0",
    port: Annotated[int, typer.Option(envvar="PVC_UI_PORT")] = 7860,
    auth: Annotated[
        str | None, typer.Option(envvar="PVC_UI_AUTH", help="user:password to protect the page.")
    ] = None,
    tensorboard_port: Annotated[
        int | None,
        typer.Option(envvar="PVC_TB_PORT", help="Port of TensorBoard, for the link in the editor."),
    ] = None,
    trusted_networks: Annotated[
        str | None,
        typer.Option(
            envvar="STUDIO_TRUSTED_NETWORKS",
            help="Networks that need no login, e.g. 192.168.1.0/24 (comma-separated; empty: login always).",
        ),
    ] = None,
) -> None:
    """The voice editor in the browser (needs: pip install -e '.[editor]')."""
    import uvicorn

    from .editor.auth import Login, load_secret, parse_networks
    from .editor.server import create_app

    root = _state["root"]
    try:
        login = Login.parse(auth, load_secret() if auth else "")
        networks = parse_networks(trusted_networks)
    except ValueError as err:
        raise typer.BadParameter(str(err)) from err
    app_ = create_app(root, login=login, tensorboard_port=tensorboard_port, trusted_networks=networks)
    shown = "localhost" if host in ("127.0.0.1", "0.0.0.0") else host
    typer.echo(f"Piper Voice Cloner editor: http://{shown}:{port}/   data: {root}   (Ctrl+C stops)")
    uvicorn.run(app_, host=host, port=port, log_level="warning", timeout_graceful_shutdown=2)


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
    if target.is_file():
        # the base before stays, numbered (usable again as ckpt:<path>): nothing is overwritten
        kept, n = target.with_name(f"{target.stem}-1{target.suffix}"), 2
        while kept.exists():
            kept, n = target.with_name(f"{target.stem}-{n}{target.suffix}"), n + 1
        target.rename(kept)
        typer.echo(f"The base before is kept as {kept}")
    shutil.copyfile(checkpoint, target)
    typer.echo(f"{checkpoint} -> {target}")


if __name__ == "__main__":  # the editor runs every job as `python -m piper_voice_cloner.cli`
    app()
