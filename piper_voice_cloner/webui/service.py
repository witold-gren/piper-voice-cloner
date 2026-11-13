"""Everything the web UI shows or changes, without Gradio (so it is testable)."""

from __future__ import annotations

from collections import Counter
import csv
from dataclasses import dataclass
import json
from pathlib import Path
import re
import shutil
import unicodedata

import yaml

from .. import (
    audition,
    config as config_mod,
    corpus as corpus_mod,
    dataset_quality,
    train as train_mod,
    train_monitor,
)
from ..dataset import METADATA, read_metadata
from ..languages import get_language
from ..synthesis import read_manifest
from .runner import STOPPED_CODES

# assumed Piper training speed (steps per second) at batch 32 on an RTX 4090 class GPU
STEPS_PER_SECOND = (1.5, 2.0)


def voices_dir(root: Path) -> Path:
    return root / "voices"


def voice_dir(root: Path, name: str) -> Path:
    return voices_dir(root) / name


LAST_VOICE = "last_voice.txt"
QUEUE_VOICES = re.compile(r"train-queue (.+?) --epochs")
QUEUE_TURN = re.compile(r"^queue \d+/\d+: \S+$", re.M)
QUEUE_FAILED = re.compile(r"^queue: (\S+) failed", re.M)
QUEUE_STATE = "train_queue.json"


def normalize_name(text: str) -> str:
    """Turn what people type ("Tomek", "Kuba Bajka", "Łucja-2") into a valid voice name."""
    text = text.strip().lower().replace("ł", "l")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def persona_path(folder: Path, persona: str) -> Path:
    """A bare file name ("custom_metadata.csv") means a file inside the old dataset folder."""
    path = Path(persona.strip()).expanduser()
    return path if path.is_absolute() else folder / path


def list_voices(root: Path) -> list[str]:
    directory = voices_dir(root)
    if not directory.is_dir():
        return []
    return sorted(p.name for p in directory.iterdir() if (p / config_mod.CONFIG_FILE).is_file())


def remember_voice(root: Path, name: str | None) -> None:
    """The voice to open after a restart; jobs/ stays on this computer."""
    if name:
        path = root / "jobs" / LAST_VOICE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name, encoding="utf-8")


def opening_voice(root: Path) -> str | None:
    """The voice worked on last, else the first one."""
    names = list_voices(root)
    try:
        saved = (root / "jobs" / LAST_VOICE).read_text(encoding="utf-8").strip()
    except OSError:
        saved = ""
    return saved if saved in names else (names[0] if names else None)


def create_voice(
    root: Path,
    name: str,
    *,
    language: str = "pl",
    backend: str = "chatterbox",
    base: str = config_mod.POLISH_BASE,
    piper_name: str | None = None,
) -> config_mod.VoiceConfig:
    get_language(language)
    name = normalize_name(name)
    if not name:
        raise ValueError("empty voice name")
    directory = voice_dir(root, name)
    if (directory / config_mod.CONFIG_FILE).exists():
        raise ValueError(f"voice '{name}' already exists")
    cfg = config_mod.VoiceConfig(
        name=name,
        language=language,
        piper_name=piper_name or None,
        synthesis=config_mod.SynthesisConfig(backend=backend),
        train=config_mod.TrainConfig(base=base),
    )
    config_mod.save(directory, cfg)
    return cfg


def rename_voice(root: Path, name: str, new_name: str, piper_name: str) -> config_mod.VoiceConfig:
    """Change the voice folder name and the Piper file name; files exported earlier keep theirs."""
    new_name = normalize_name(new_name)
    cfg = load_config(root, name).model_copy(update={"piper_name": piper_name.strip() or None})
    cfg.name = config_mod.VoiceConfig(name=new_name).name
    target = voice_dir(root, new_name)
    if new_name != name:
        if target.exists():
            raise ValueError(f"voice '{new_name}' already exists")
        voice_dir(root, name).rename(target)
    config_mod.save(target, cfg)
    return cfg


def set_backend(root: Path, name: str, backend: str) -> None:
    """The options of one model mean nothing to another, so they are not carried over."""
    cfg = load_config(root, name)
    if cfg.synthesis.backend != backend:
        corpus_mod.refuse_imported(voice_dir(root, name))
        cfg.synthesis.backend = backend
        cfg.synthesis.options = {}
        config_mod.save(voice_dir(root, name), cfg)


def load_config(root: Path, name: str) -> config_mod.VoiceConfig:
    return config_mod.load(voice_dir(root, name))


def config_yaml(root: Path, name: str) -> str:
    return (voice_dir(root, name) / config_mod.CONFIG_FILE).read_text(encoding="utf-8")


def save_config_yaml(root: Path, name: str, text: str) -> config_mod.VoiceConfig:
    """Validate edited YAML; the file is only replaced when it is valid."""
    data = yaml.safe_load(text) or {}
    cfg = config_mod.VoiceConfig.model_validate(data)
    if cfg.name != name:
        raise ValueError("the name in voice.yaml must stay the same")
    config_mod.save(voice_dir(root, name), cfg)
    return cfg


def save_uploads(target_dir: Path, files: list[str | Path]) -> list[Path]:
    """Copy uploaded files (Gradio temp paths) into the voice folder, keeping their names."""
    target_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for file in files:
        source = Path(file)
        target = target_dir / source.name
        shutil.copyfile(source, target)
        saved.append(target)
    return saved


# --- status ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Step:
    key: str
    done: bool
    detail: str


def _count_lines(path: Path) -> int:
    return len(corpus_mod.read_prompts(path)) if path.is_file() else 0


def reference_info(directory: Path) -> dict:
    path = directory / "reference" / "reference.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def checkpoints(work_dir: Path) -> list[Path]:
    """All checkpoints of a training run, newest first."""
    found = list(work_dir.glob("lightning_logs/version_*/checkpoints/*.ckpt"))
    return sorted(found, key=lambda p: p.stat().st_mtime, reverse=True)


def exports(directory: Path) -> list[Path]:
    export_dir = directory / "export"
    return sorted(export_dir.glob("*.onnx*")) if export_dir.is_dir() else []


def steps(root: Path, name: str) -> list[Step]:
    directory = voice_dir(root, name)
    cfg = load_config(root, name)
    ref = reference_info(directory)
    prompts = _count_lines(directory / corpus_mod.PROMPTS)
    raw = len(read_manifest(directory / "raw"))
    dataset = (
        len(read_metadata(directory / "dataset" / METADATA))
        if (directory / "dataset" / METADATA).is_file()
        else 0
    )
    ckpts = checkpoints(directory / "train")
    out = exports(directory)
    return [
        Step(
            "reference",
            bool(ref) or cfg.synthesis.backend == "elevenlabs",
            f"{ref.get('seconds', 0)} s" if ref else "",
        ),
        Step("corpus", prompts > 0, str(prompts) if prompts else ""),
        Step("audition", (directory / "audition" / audition.RESULTS).is_file(), ""),
        Step("synthesize", raw > 0, f"{raw} / {prompts}" if raw else ""),
        Step("filter", dataset > 0, f"{dataset} / {cfg.target_clips}" if dataset else ""),
        Step("train", bool(ckpts), str(len(ckpts)) if ckpts else ""),
        Step(
            "export",
            any(p.suffix == ".onnx" for p in out),
            ", ".join(p.name for p in out if p.suffix == ".onnx"),
        ),
    ]


# --- results ----------------------------------------------------------------------------------


def prompt_count(root: Path, name: str) -> int:
    """Sentences chosen for the voice (prompts.tsv): what a full `synthesize` run reads."""
    return _count_lines(voice_dir(root, name) / corpus_mod.PROMPTS)


def sentence_sets(root: Path) -> list[tuple[str, int]]:
    """Imported voices (name, sentences): their datasets are the sets a new voice can read."""
    found = []
    for name in list_voices(root):
        dataset = voice_dir(root, name) / "dataset"
        if (dataset / "import_report.csv").is_file() and (dataset / METADATA).is_file():
            found.append((name, len(corpus_mod.from_dataset(dataset / METADATA))))
    return found


def missing_sentences(root: Path, name: str) -> tuple[int, int]:
    """Sentences without a clip yet and their characters: what generating them costs in ElevenLabs."""
    directory = voice_dir(root, name)
    path = directory / corpus_mod.PROMPTS
    done = read_manifest(directory / "raw")
    texts = (
        [text for utt_id, text in corpus_mod.read_prompts(path) if utt_id not in done]
        if path.is_file()
        else []
    )
    return len(texts), sum(len(text) for text in texts)


def corpus_preview(root: Path, name: str, limit: int = 50) -> list[list[str]]:
    path = voice_dir(root, name) / corpus_mod.PROMPTS
    return [[text] for _id, text in corpus_mod.read_prompts(path)[:limit]] if path.is_file() else []


def reference_clips(root: Path, name: str) -> list[Path]:
    clean = voice_dir(root, name) / "reference" / "clean"
    return sorted(clean.glob("ref_*.wav")) if clean.is_dir() else []


def audition_results(root: Path, name: str) -> list[dict]:
    return audition.read_json(voice_dir(root, name) / "audition" / audition.RESULTS)


def audition_table(results: list[dict]) -> list[list]:
    def fmt(value, digits=3):
        return "" if value is None else round(value, digits)

    return [
        [rank, r["slug"], fmt(r["score"]), fmt(r["cer"]), fmt(r["similarity"]), fmt(r["mos"], 2)]
        for rank, r in enumerate(results, 1)
    ]


def audition_clips(root: Path, name: str, slug: str) -> list[tuple[Path, str]]:
    base = voice_dir(root, name) / "audition"
    for result in audition_results(root, name):
        if result["slug"] == slug:
            return [(base / clip["file"], clip["text"]) for clip in result["clips"]]
    return []


def apply_audition(root: Path, name: str, slug: str) -> dict:
    """Store the options of one audition combination in voice.yaml."""
    for result in audition_results(root, name):
        if result["slug"] == slug:
            cfg = load_config(root, name)
            cfg.synthesis.options = {**cfg.synthesis.options, **result["options"]}
            config_mod.save(voice_dir(root, name), cfg)
            return cfg.synthesis.options
    raise ValueError(f"no audition result '{slug}'")


def filter_report(root: Path, name: str) -> list[dict]:
    path = voice_dir(root, name) / "dataset" / "filter_report.csv"
    if not path.is_file():
        path = voice_dir(root, name) / "dataset" / "import_report.csv"
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def reason_counts(rows: list[dict]) -> list[list]:
    counts = Counter(row.get("reason") or "ok" for row in rows)
    return [[reason, count] for reason, count in counts.most_common()]


def sample_clips(
    root: Path, name: str, rows: list[dict], *, kept: bool, limit: int = 4
) -> list[tuple[Path, str]]:
    """Kept clips come from dataset/wav, rejected ones from raw/ (where they still exist)."""
    directory = voice_dir(root, name)
    picked = []
    for row in rows:
        if bool(row.get("reason")) == kept:
            continue
        folder = directory / "dataset" / "wav" if kept else directory / "raw"
        path = folder / f"{row['id']}.wav"
        if path.is_file():
            label = row["text"] if kept else f"[{row['reason']}] {row['text']}"
            picked.append((path, label))
        if len(picked) >= limit:
            break
    return picked


# --- training -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Estimate:
    clips: int
    steps_per_epoch: int
    epoch_seconds: tuple[float, float]

    def hours(self, epochs: int) -> tuple[float, float]:
        low, high = self.epoch_seconds
        return low * epochs / 3600, high * epochs / 3600


def estimate(clips: int, batch_size: int = 32, validation_split: float = 0.05) -> Estimate:
    steps = max(1, round(clips * (1 - validation_split) / batch_size))
    fast, slow = STEPS_PER_SECOND[1], STEPS_PER_SECOND[0]
    return Estimate(clips, steps, (steps / fast, steps / slow))


def dataset_size(root: Path, name: str) -> int:
    path = voice_dir(root, name) / "dataset" / METADATA
    return len(read_metadata(path)) if path.is_file() else 0


def trainable_voices(root: Path) -> list[str]:
    return [name for name in list_voices(root) if dataset_size(root, name)]


def queue_voice(root: Path) -> str | None:
    """The voice a training queue works on now."""
    try:
        return json.loads((root / "jobs" / QUEUE_STATE).read_text(encoding="utf-8"))["voice"]
    except (OSError, ValueError, KeyError):
        return None


def queue_steps(status) -> list[tuple[str, str]]:
    """(voice, done | now | waiting | failed | stopped) of a training queue, in training order."""
    found = QUEUE_VOICES.search(status.queue_log)
    if not found:
        return []
    reached = len(QUEUE_TURN.findall(status.queue_log))
    failed = set(QUEUE_FAILED.findall(status.queue_log))
    steps = []
    for index, name in enumerate(found.group(1).split()):
        if name in failed:
            state = "failed"
        elif index >= reached:
            state = "waiting"
        elif index < reached - 1:
            state = "done"
        elif status.running:
            state = "now"
        else:
            state = "stopped" if status.returncode in STOPPED_CODES else "done"
        steps.append((name, state))
    return steps


def job_label(root: Path, status, name: str) -> str:
    """The job's name; a running training queue adds the voice it works on now."""
    voice = queue_voice(root) if status.kind == "train-queue" and status.running else None
    return f"{name} - {voice}" if voice else name


def set_max_epochs(root: Path, name: str, max_epochs: int) -> None:
    cfg = load_config(root, name)
    cfg.train.max_epochs = max_epochs
    config_mod.save(voice_dir(root, name), cfg)


def checkpoint_choices(root: Path, name: str) -> list[str]:
    return [str(p) for p in checkpoints(voice_dir(root, name) / "train")]


def bases_dir(root: Path) -> Path:
    return root / "bases"


def base_work_dir(root: Path, quality: str = "medium") -> Path:
    """Where `pvc base train --quality <quality>` trains."""
    return train_mod.base_folder(bases_dir(root), quality) / "train"


def base_dataset_dir(root: Path) -> Path:
    return train_mod.base_dataset(bases_dir(root))


def base_runs(root: Path) -> list[str]:
    """Model sizes with a base training run (logs written), medium first."""
    return [q for q in train_mod.QUALITIES if train_monitor.event_files(base_work_dir(root, q))]


def latest_base_run(root: Path) -> str | None:
    """The base run written to last (the one training now, or the last one trained)."""
    newest = {
        q: max(p.stat().st_mtime for p in train_monitor.event_files(base_work_dir(root, q)))
        for q in base_runs(root)
    }
    return max(newest, key=newest.get) if newest else None


def base_checkpoint_choices(root: Path) -> list[tuple[str, str]]:
    """(label, path) of every base checkpoint, newest first per model size: "high · epoch=…";
    last.ckpt names its run, since every resumed run (version_N) has its own."""
    return [
        (
            f"{quality} · {path.name if 'epoch=' in path.name else f'{path.parent.parent.name}/{path.name}'}",
            str(path),
        )
        for quality in train_mod.QUALITIES
        for path in checkpoints(base_work_dir(root, quality))
    ]


def base_score(root: Path) -> dict | None:
    """Summary of the last UTMOS rating of the base recordings, or None."""
    report = dataset_quality.load(base_dataset_dir(root))
    return dataset_quality.summary(report) | {"texts": report.get("texts", {})} if report else None


@dataclass(frozen=True)
class BaseResult:
    quality: str
    last_epoch: int
    best_mos: tuple[int, float] | None  # (epoch, value)
    best_mel: tuple[int, float] | None
    mos_at: float | None  # mean val_mos of the window up to the common epoch
    mel_at: float | None


def compare_bases(root: Path, window: int = 10) -> tuple[int | None, list[BaseResult]]:
    """Base runs side by side: their best values and the mean of the `window` epochs up to the last
    epoch every run has reached (val_mos of one epoch is noisy: 5 sentences)."""
    runs = {q: train_monitor.update(base_work_dir(root, q)) for q in base_runs(root)}
    runs = {q: run for q, run in runs.items() if run.metrics.get("val_mos")}
    if not runs:
        return None, []
    common = min(max(run.metrics["val_mos"]) for run in runs.values())

    def mean_up_to(values: dict[int, float]) -> float | None:
        picked = [v for e, v in values.items() if common - window < e <= common]
        return sum(picked) / len(picked) if picked else None

    results = []
    for quality, run in runs.items():
        mos, mel = run.metrics.get("val_mos", {}), run.metrics.get("val_mel", {})
        results.append(
            BaseResult(
                quality=quality,
                last_epoch=max(mos),
                best_mos=max(mos.items(), key=lambda item: item[1]) if mos else None,
                best_mel=min(mel.items(), key=lambda item: item[1]) if mel else None,
                mos_at=mean_up_to(mos),
                mel_at=mean_up_to(mel),
            )
        )
    return common, results


def base_sources(root: Path) -> list[tuple[str, int, Path]]:
    """(voice, clips, dataset folder) of the voices with a cleaned dataset, the largest first: the
    base needs one speaker and many clips."""
    found = []
    for name in list_voices(root):
        folder = voice_dir(root, name) / "dataset"
        if (folder / "metadata.csv").is_file():
            found.append((name, dataset_size(root, name), folder))
    return sorted(found, key=lambda item: (-item[1], item[0]))


def base_ready(root: Path) -> bool:
    return (bases_dir(root) / train_mod.SCRATCH_BASE).is_file()


def base_options(root: Path, current: str | None = None) -> tuple[list[str], str, bool]:
    """(choices, value, ready) for a base dropdown: bazowy-pl only once it exists; a voice set to a
    missing bazowy-pl shows lessac (the caller says why)."""
    ready = base_ready(root)
    choices = ([config_mod.POLISH_BASE] if ready else []) + ["lessac"]
    current = config_mod.OLD_BASE_NAMES.get(current or "", current or "")
    if current in choices:
        return choices, current, ready
    if current.startswith("ckpt:"):
        return [*choices, current], current, ready
    return choices, choices[0], ready


# --- live panel ---------------------------------------------------------------------------------

GPU_QUERY = "name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,power.limit"


def parse_gpu(line: str) -> dict | None:
    """One line of `nvidia-smi --query-gpu=... --format=csv,noheader,nounits`."""
    parts = [p.strip() for p in line.split(",")]
    if len(parts) != 7:
        return None

    def number(value: str) -> float:
        try:
            return float(value)
        except ValueError:  # "[N/A]" on some cards
            return 0.0

    name, util, used, total, temp, power, limit = parts
    used_mb, total_mb, watts, limit_w = number(used), number(total), number(power), number(limit)
    return {
        "name": name,
        "utilization": number(util),
        "memory_used": used_mb,
        "memory_total": total_mb,
        "memory_percent": 100 * used_mb / total_mb if total_mb else 0.0,
        "temperature": number(temp),
        "power": watts,
        "power_percent": 100 * watts / limit_w if limit_w else 0.0,
    }


def gpu_stats(run=None) -> dict | None:
    """First NVIDIA GPU, or None without nvidia-smi (e.g. on a laptop)."""
    import shutil
    import subprocess

    if run is None:
        if not shutil.which("nvidia-smi"):
            return None

        def run():
            result = subprocess.run(
                ["nvidia-smi", f"--query-gpu={GPU_QUERY}", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            return result.stdout if result.returncode == 0 else ""

    try:
        output = run()
    except Exception:  # a stuck driver must not break the page
        return None
    lines = [line for line in output.splitlines() if line.strip()]
    return parse_gpu(lines[0]) if lines else None


PROGRESS_LINE = re.compile(r"progress \S+ (\d+)/(\d+)")
ANSI_CODE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
# validation bars and UTMOS loading, printed again after every training epoch
LOG_NOISE = re.compile(r"^Validation|^Using cache found in|weight_norm|WeightNorm\.apply")
# Lightning bar inside the piper training log: "Epoch 2170: 37%|███   | 21/56 [00:10<00:17, ...]"
EPOCH_BAR = re.compile(r"(Epoch \d+)[^|\n]*\|[^|\n]*\|\s*(\d+)/(\d+)")


def parse_progress(log: str) -> tuple[int, int, str] | None:
    """Latest (done, total, label) in a job log: our "progress" lines or the training epoch bar."""
    found = None
    for match in PROGRESS_LINE.finditer(log):
        found = (match.start(), int(match.group(1)), int(match.group(2)), "")
    for match in EPOCH_BAR.finditer(log):
        if found is None or match.start() > found[0]:
            found = (match.start(), int(match.group(2)), int(match.group(3)), match.group(1))
    if found is None or found[2] <= 0:
        return None
    return found[1], found[2], found[3]


# printed by `pvc train` / `pvc base train` before piper starts: "training epochs 2164-5164"
TRAIN_PLAN = re.compile(r"training epochs (\d+)-(\d+)")
# the same bar with its times: "... | 21/56 [00:10<00:17" (spent < left in this epoch)
EPOCH_TIMES = re.compile(r"Epoch (\d+)[^|\n]*\|[^|\n]*\|\s*(\d+)/(\d+)\s*\[([\d:]+)<([\d:]+)")


def _seconds(clock: str) -> int:
    total = 0
    for part in clock.split(":"):
        total = total * 60 + int(part)
    return total


def training_progress(log: str) -> tuple[float, int, tuple[int, int, int] | None, float | None] | None:
    """(epochs done, epochs planned, (model epoch, step, steps), seconds left) of a training job,
    else None. Done and planned count from the base, the model epoch includes the base's epochs.

    The time left is the length of the current epoch (from the bar) times the epochs still to go,
    so it stays right after a resume and does not count the preprocessing at the start.
    """
    plans = TRAIN_PLAN.findall(log)
    if not plans:
        return None
    start, end = (int(v) for v in plans[-1])
    total = end - start
    if total <= 0:
        return None
    bars = EPOCH_BAR.findall(log)
    if not bars:
        return 0.0, total, None, None
    label, step, steps = bars[-1][0], int(bars[-1][1]), int(bars[-1][2])
    epoch = int(label.split()[1])
    done = min(float(total), max(0.0, epoch - start + (step / steps if steps else 0.0)))
    left = None
    times = EPOCH_TIMES.findall(log)
    if times:
        t_epoch, _, _, spent, rest = times[-1]
        per_epoch = _seconds(spent) + _seconds(rest)
        if per_epoch > 0:
            left = _seconds(rest) + max(0, end - int(t_epoch) - 1) * per_epoch
    return done, total, (epoch, step, steps), left


def time_left(elapsed: float | None, done: float, total: float) -> float | None:
    """Straight-line estimate for the other jobs: the same pace until the end."""
    if not elapsed or done <= 0 or total <= done:
        return None
    return elapsed * (total - done) / done


def compact_log(log: str) -> str:
    """Drop all but the latest progress or epoch line and what training repeats after every epoch,
    so the log view keeps the real messages; the log file stays complete."""
    lines = [line for line in ANSI_CODE.sub("", log).split("\n") if not LOG_NOISE.search(line)]
    progress = [i for i, line in enumerate(lines) if PROGRESS_LINE.match(line)]
    epochs = [i for i, line in enumerate(lines) if EPOCH_BAR.match(line)]
    drop = set(progress[:-1] + epochs[:-1])
    return "\n".join(line for i, line in enumerate(lines) if i not in drop)


def format_elapsed(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "—"
    seconds = int(seconds)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours >= 24:
        days, hours = divmod(hours, 24)
        return f"{days} d {hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
