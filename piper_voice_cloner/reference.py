"""Reference recordings: cleaned clips for cloning + speaker embedding for checks."""

from __future__ import annotations

from collections.abc import Callable
import json
from pathlib import Path

import numpy as np

from . import audio as audio_utils
from .quality.speaker import calibrate_threshold, centroid

CLONE_RATE = 24000
# cloning models work best with ~5-12 s prompts
MAX_PROMPT_SECONDS = 12.0
MIN_PROMPT_SECONDS = 3.0
CHUNK_SECONDS = 4.0
# below this (or with a single prompt) cloning still works, but the voice is less steady and the
# similarity threshold rests on a few chunks: 30-60 s of varied speech is better
RECOMMENDED_SECONDS = 20.0

Embed = Callable[[np.ndarray], np.ndarray]


def split(audio: np.ndarray, rate: int, max_seconds: float, min_seconds: float) -> list[np.ndarray]:
    """Equal pieces not longer than max_seconds; a tail shorter than min_seconds is dropped."""
    total = len(audio) / rate
    if total < min_seconds:
        return []
    pieces = max(1, int(np.ceil(total / max_seconds)))
    size = len(audio) // pieces
    chunks = [audio[i * size : (i + 1) * size] for i in range(pieces)]
    return [c for c in chunks if len(c) / rate >= min_seconds]


def prepare(clips: list[Path], out_dir: Path, embed: Embed | None) -> dict:
    """Write out_dir/clean/ref_NN.wav (24 kHz) and out_dir/reference.json (+ embedding.npy)."""
    clean_dir = out_dir / "clean"
    clean_dir.mkdir(parents=True, exist_ok=True)
    for old in clean_dir.glob("ref_*.wav"):
        old.unlink()
    prompts: list[str] = []
    vectors: list[np.ndarray] = []
    seconds = 0.0
    for clip in clips:
        wave = audio_utils.trim(audio_utils.load(clip, CLONE_RATE), CLONE_RATE)
        wave = audio_utils.normalize_level(wave, CLONE_RATE)
        seconds += audio_utils.duration(wave, CLONE_RATE)
        for piece in split(wave, CLONE_RATE, MAX_PROMPT_SECONDS, MIN_PROMPT_SECONDS):
            path = clean_dir / f"ref_{len(prompts):02d}.wav"
            audio_utils.save_wav(path, piece, CLONE_RATE)
            prompts.append(path.name)
        if embed is not None:
            wave_16k = audio_utils.resample(wave, CLONE_RATE, audio_utils.EMBED_RATE)
            for chunk in split(wave_16k, audio_utils.EMBED_RATE, CHUNK_SECONDS, 1.5):
                vectors.append(embed(chunk))
    if not prompts:
        raise ValueError(f"no usable reference audio (need at least {MIN_PROMPT_SECONDS:.0f} s of speech)")
    info: dict = {"prompts": prompts, "seconds": round(seconds, 1)}
    if vectors:
        np.save(out_dir / "embedding.npy", centroid(vectors))
        info["min_similarity"] = calibrate_threshold(vectors)
        info["chunks"] = len(vectors)
    (out_dir / "reference.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    return info


def is_short(info: dict) -> bool:
    return info["seconds"] < RECOMMENDED_SECONDS or len(info["prompts"]) < 2


def prompt_paths(ref_dir: Path) -> list[Path]:
    info = json.loads((ref_dir / "reference.json").read_text(encoding="utf-8"))
    return [ref_dir / "clean" / name for name in info["prompts"]]


def load_embedding(ref_dir: Path) -> np.ndarray | None:
    path = ref_dir / "embedding.npy"
    return np.load(path) if path.is_file() else None
