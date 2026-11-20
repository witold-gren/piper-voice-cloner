"""Piper (OHF-Voice/piper1-gpl) training and export command builders.

The commands run in the separate training environment (`.venv-train`), so this module only
builds argument lists and resolves the starting checkpoint; `run` executes them.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.parse
import urllib.request

from .config import OLD_BASE_NAMES, POLISH_BASE, TrainConfig
from .languages import LanguagePack

_LOGGER = logging.getLogger(__name__)

LESSAC_URL = (
    "https://huggingface.co/datasets/rhasspy/piper-checkpoints/resolve/main/en/en_US/lessac/medium/"
    + urllib.parse.quote("epoch=2164-step=1355540.ckpt")
)
SCRATCH_BASE = "pl-scratch.ckpt"  # the chosen bazowy-pl checkpoint (medium or high)
BASE_FOLDER = "pl-scratch"  # bases/<folder>: the base dataset and the medium run; high runs next to it
SAMPLE_RATE = 22050

# Model size. piper1-gpl builds "medium" unless told otherwise; "high" is the decoder of the original
# Piper high voices (HiFi-GAN V1): about 8x the decoder of medium (14 vs 1.7 M parameters), cleaner
# audio, slower to train and to speak. A voice fine-tuned from a checkpoint must keep its size.
QUALITIES = ("medium", "high")
MODEL_ARGS = {
    "medium": [],
    "high": [
        "--model.resblock",
        "1",
        "--model.resblock_kernel_sizes",
        "[3, 7, 11]",
        "--model.resblock_dilation_sizes",
        "[[1, 3, 5], [1, 3, 5], [1, 3, 5]]",
        "--model.upsample_rates",
        "[8, 8, 2, 2]",
        "--model.upsample_initial_channel",
        "512",
        "--model.upsample_kernel_sizes",
        "[16, 16, 4, 4]",
    ],
}
# batch that fits a 24 GB GPU with room for a batch of long clips
DEFAULT_BATCH = {"medium": 32, "high": 16}


class TrainError(RuntimeError):
    pass


def base_folder(bases_dir: Path, quality: str = "medium") -> Path:
    """Folder of one base run: medium in bases/pl-scratch (with the dataset), high in pl-scratch-high."""
    if quality not in QUALITIES:
        raise TrainError(f"quality must be one of {', '.join(QUALITIES)}")
    return bases_dir / (BASE_FOLDER if quality == "medium" else f"{BASE_FOLDER}-{quality}")


def base_dataset(bases_dir: Path) -> Path:
    """One cleaned dataset for every base size, so their results can be compared."""
    return bases_dir / BASE_FOLDER / "dataset"


@dataclass(frozen=True)
class TrainPaths:
    dataset_dir: Path
    work_dir: Path

    @property
    def metadata(self) -> Path:
        return self.dataset_dir / "metadata.csv"

    @property
    def audio_dir(self) -> Path:
        return self.dataset_dir / "wav"

    @property
    def cache_dir(self) -> Path:
        return self.work_dir / "cache"

    @property
    def config_json(self) -> Path:
        return self.work_dir / "config.json"


def resolve_base(base: str, bases_dir: Path, *, download: bool = True) -> Path | None:
    """Starting checkpoint for fine-tuning; None = random weights (training from scratch)."""
    if base.startswith("ckpt:"):
        path = Path(base[5:]).expanduser()
        if not path.is_file():
            raise TrainError(f"checkpoint {path} not found")
        return path
    if base == "lessac":
        target = bases_dir / "en_US-lessac-medium.ckpt"
        if not target.is_file():
            if not download:
                raise TrainError(f"{target} missing")
            bases_dir.mkdir(parents=True, exist_ok=True)
            _LOGGER.info("Downloading lessac medium checkpoint (~850 MB)")
            part = target.with_suffix(".part")
            urllib.request.urlretrieve(LESSAC_URL, part)
            part.rename(target)
        return target
    if OLD_BASE_NAMES.get(base, base) == POLISH_BASE:
        target = bases_dir / SCRATCH_BASE
        if not target.is_file():
            raise TrainError(
                f"{target} missing - create the {POLISH_BASE} base first (web UI: Tools, own base; CLI: "
                "pvc base prepare, base train, base select) or choose base: lessac / ckpt:<path>"
            )
        return target
    raise TrainError(f"unknown base '{base}'")


EPOCH_IN_NAME = re.compile(r"epoch=(\d+)")


@dataclass(frozen=True)
class CheckpointInfo:
    epoch: int
    quality: str  # "medium" or "high"


_INFO_CODE = (
    "import sys, torch; c = torch.load(sys.argv[1], map_location='cpu', weights_only=False); "
    "h = c.get('hyper_parameters') or {}; "
    "size = 'high' if int(h.get('upsample_initial_channel', 256)) >= 512 else 'medium'; "
    "print(int(c.get('epoch', 0)), size)"
)


# Lightning 2.6 opens the starting checkpoint with torch.load(weights_only=True), which refuses
# pathlib paths, and passes its hyper_parameters to the model as options. Older checkpoints (the lessac
# base from Hugging Face) keep paths and options of the old trainer (sample_bytes, gpus, ...) there.
_LOADABLE_CODE = """
import inspect, os, pathlib, sys, torch
path = sys.argv[1]
try:
    from piper.train.vits.lightning import VitsModel
    # only named options: LightningCLI refuses others although VitsModel takes **kwargs
    params = inspect.signature(VitsModel.__init__).parameters.values()
    allowed = {p.name for p in params if p.kind not in (p.VAR_KEYWORD, p.VAR_POSITIONAL)} - {"self"}
except ImportError:
    allowed = None
found = []
def clean(value, where):
    if isinstance(value, pathlib.PurePath):
        found.append(where)
        return str(value)
    if isinstance(value, dict):
        return type(value)((k, clean(v, f"{where}.{k}")) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return type(value)(clean(v, f"{where}[{i}]") for i, v in enumerate(value))
    return value
data = torch.load(path, map_location="cpu", weights_only=False)
data = {k: v if k in ("state_dict", "optimizer_states") else clean(v, k) for k, v in data.items()}
hparams = data.get("hyper_parameters") or {}
dropped = sorted(set(hparams) - allowed) if allowed is not None else []
if not found and not dropped:
    print("ok")
    sys.exit(0)
data["hyper_parameters"] = {k: v for k, v in hparams.items() if k not in dropped}
tmp = path + ".loadable"
torch.save(data, tmp)
torch.load(tmp, map_location="cpu", weights_only=True)
os.replace(tmp, path)
print("cleaned " + " ".join(found) + (" dropped " + " ".join(dropped) if dropped else ""))
"""


def make_loadable(path: Path, *, python: str = sys.executable) -> str:
    """Make a starting checkpoint open in Lightning 2.6, in place and once per file: paths become text
    and options the current VitsModel does not take leave hyper_parameters.

    Only for checkpoints we trust: our own runs and the bases this tool downloads.
    """
    result = subprocess.run(
        [python, "-c", _LOADABLE_CODE, str(path)], capture_output=True, text=True, check=False
    )
    lines = result.stdout.strip().splitlines()
    if result.returncode != 0 or not lines:
        raise TrainError(f"cannot prepare {path} for training: {result.stderr.strip()[-400:]}")
    if lines[-1] != "ok":
        _LOGGER.info("%s: %s (now opens with weights_only=True)", path.name, lines[-1])
    return lines[-1]


def checkpoint_info(path: Path, *, python: str = sys.executable) -> CheckpointInfo:
    """Epoch and model size of a Lightning checkpoint, read by the training Python (it has torch).

    An epoch in the file name wins (Lightning names them so); when torch cannot read the file and the
    name has the epoch, the size is taken as medium (a dry run on a computer without torch).
    """
    match = EPOCH_IN_NAME.search(path.name)
    result = subprocess.run(
        [python, "-c", _INFO_CODE, str(path)], capture_output=True, text=True, check=False
    )
    lines = result.stdout.strip().splitlines()
    if result.returncode != 0 or not lines:
        if match:
            _LOGGER.warning("cannot read %s, assuming a medium model", path)
            return CheckpointInfo(int(match.group(1)), "medium")
        raise TrainError(f"cannot read the epoch of {path} with {python}: {result.stderr.strip()[-300:]}")
    epoch, *size = lines[-1].split()
    quality = size[0] if size and size[0] in QUALITIES else "medium"
    return CheckpointInfo(int(match.group(1)) if match else int(epoch), quality)


def latest_checkpoint(work_dir: Path) -> Path | None:
    """Newest Lightning checkpoint under work_dir (to resume an interrupted run)."""
    last = sorted(
        work_dir.glob("lightning_logs/version_*/checkpoints/last.ckpt"), key=lambda p: p.stat().st_mtime
    )
    return last[-1] if last else None


def resume_checkpoint(work_dir: Path, *, current_run: bool = False) -> Path | None:
    """The newest checkpoint of any kind, to continue a stopped run with as little lost as possible.

    piper1-gpl does not refresh last.ckpt after every epoch, while a new best val_mos/val_mel
    checkpoint is a full one too (weights and optimizers), so after a crash it is often newer.
    `current_run`: only the run in run.json (a start over that stopped before its first checkpoint
    must not go on from the run before it).
    """
    from . import train_monitor

    candidates = (
        train_monitor.run_checkpoints(work_dir)
        if current_run
        else work_dir.glob("lightning_logs/version_*/checkpoints/*.ckpt")
    )
    found = sorted(candidates, key=lambda p: p.stat().st_mtime)
    return found[-1] if found else None


def fit_command(
    voice_name: str,
    paths: TrainPaths,
    lang: LanguagePack,
    train: TrainConfig,
    ckpt: Path | None,
    *,
    start_epoch: int = 0,
    quality: str = "medium",
    python: str = sys.executable,
) -> list[str]:
    """`python -m piper.train fit ...`; ckpt None trains from random weights.

    piper1-gpl keeps the best checkpoints by val_mel and val_mos plus last.ckpt by itself.
    """
    cmd = [
        python,
        "-m",
        "piper.train",
        "fit",
        "--data.voice_name",
        voice_name,
        "--data.csv_path",
        str(paths.metadata),
        "--data.audio_dir",
        str(paths.audio_dir),
        "--model.sample_rate",
        str(SAMPLE_RATE),
        "--data.espeak_voice",
        lang.espeak_voice,
        "--data.cache_dir",
        str(paths.cache_dir),
        "--data.config_path",
        str(paths.config_json),
        "--data.batch_size",
        str(train.batch_size),
        "--data.num_workers",
        str(train.num_workers),
        "--data.validation_split",
        str(train.validation_split),
        "--data.num_test_examples",
        str(train.num_test_examples),
        # Lightning continues the epoch counter of --ckpt_path, so the limit is relative to it
        "--trainer.max_epochs",
        str(start_epoch + train.max_epochs),
        "--trainer.default_root_dir",
        str(paths.work_dir),
    ]
    cmd += MODEL_ARGS[quality]
    if ckpt is not None:
        cmd += ["--ckpt_path", str(ckpt)]
    return cmd + list(train.extra_args)


# torch's newer exporter (dynamo) stops at an assert inside the VITS spline; the older one exports
# the same file size as the Piper voices made so far
EXPORT_CODE = """
import functools, runpy, sys, torch
torch.onnx.export = functools.partial(torch.onnx.export, dynamo=False)
sys.argv = ["export_onnx", *sys.argv[1:]]
runpy.run_module("piper.train.export_onnx", run_name="__main__")
"""


def export_command(checkpoint: Path, onnx_file: Path, *, python: str = sys.executable) -> list[str]:
    return [
        python,
        "-c",
        EXPORT_CODE,
        "--checkpoint",
        str(checkpoint),
        "--output-file",
        str(onnx_file),
    ]


def free_export_path(folder: Path, stem: str) -> Path:
    """<stem>.onnx, or with the next number when that name is taken: an export never overwrites one
    made before (pl_PL-meski-medium.onnx -> pl_PL-meski_2-medium.onnx). The number goes into the name,
    before the size, so the name keeps Piper's <language>-<name>-<size> form."""
    name, dash, quality = stem.rpartition("-")
    candidate, n = folder / f"{stem}.onnx", 2
    while candidate.exists() or candidate.with_name(candidate.name + ".json").exists():
        candidate = folder / (f"{name}_{n}{dash}{quality}.onnx" if dash else f"{stem}_{n}.onnx")
        n += 1
    return candidate


def finish_export(paths: TrainPaths, onnx_file: Path, quality: str = "medium") -> Path:
    """The training config next to the model as <name>.onnx.json (Piper convention), with the model
    size in audio.quality like the official voices."""
    if not paths.config_json.is_file():
        raise TrainError(f"{paths.config_json} missing - was the voice trained in {paths.work_dir}?")
    config = json.loads(paths.config_json.read_text(encoding="utf-8"))
    config.setdefault("audio", {})["quality"] = quality
    # read by wyoming-piper to list the voice under its language
    locale = onnx_file.name.split("-")[0]
    family, _, region = locale.partition("_")
    config.setdefault("language", {"code": locale, "family": family, "region": region})
    config.setdefault("dataset", onnx_file.name.removesuffix(".onnx"))
    target = onnx_file.with_name(onnx_file.name + ".json")
    target.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def run(cmd: list[str]) -> None:
    _LOGGER.info("Running: %s", " ".join(cmd))
    # Batches are padded to their longest clip, so the GPU memory jumps from batch to batch; without
    # expandable segments the cache fragments and a rare batch of long clips runs out of memory after
    # hundreds of epochs. A value set by the user wins.
    env = {**os.environ}
    env.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    result = subprocess.run(cmd, check=False, env=env)
    if result.returncode != 0:
        raise TrainError(f"command failed with exit code {result.returncode}")
