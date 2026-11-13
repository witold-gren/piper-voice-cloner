"""Screen raw synthetic clips and build the training dataset from the ones that pass.

Checks per clip: length vs. text (cut-off / hallucination), ASR character error rate,
speaker similarity to the reference, then the worst MOS fraction is dropped. If more
clips pass than needed, the most similar ones are kept.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import audio as audio_utils
from .config import QualityConfig
from .dataset import METADATA, WAV_DIR, Utterance, write_metadata, write_report
from .quality.mos import drop_threshold
from .quality.speaker import cosine
from .synthesis import read_manifest

REPORT_FIELDS = ["id", "text", "reference", "seed", "seconds", "cer", "similarity", "mos", "reason"]


@dataclass
class Checks:
    """Optional quality models; a missing one is simply not applied."""

    cer: Callable[[np.ndarray, str], float] | None = None
    embed: Callable[[np.ndarray], np.ndarray] | None = None
    reference_embedding: np.ndarray | None = None
    mos: Callable[[np.ndarray], float] | None = None
    skipped: list[str] = field(default_factory=list)


def letters(text: str) -> int:
    return sum(1 for char in text if char.isalpha())


def first_failure(row: dict, quality: QualityConfig, min_similarity: float | None) -> str:
    """Reason a measured clip fails (empty string = passes); MOS is decided later, globally."""
    chars = max(1, letters(row["text"]))
    per_char = row["seconds"] / chars
    if per_char < quality.min_seconds_per_char:
        return "too_fast_or_cut"
    if per_char > quality.max_seconds_per_char:
        return "too_slow_or_hallucinated"
    if row.get("cer") is not None and row["cer"] > quality.max_cer:
        return "asr_mismatch"
    if (
        min_similarity is not None
        and row.get("similarity") is not None
        and row["similarity"] < min_similarity
    ):
        return "speaker_mismatch"
    return ""


def measure(raw_dir: Path, checks: Checks, progress: Callable[[int, int], None] | None = None) -> list[dict]:
    rows = []
    manifest = read_manifest(raw_dir)
    for index, (utt_id, entry) in enumerate(manifest.items(), 1):
        if progress:
            progress(index, len(manifest))
        path = raw_dir / f"{utt_id}.wav"
        row = {
            "id": utt_id,
            "text": entry["text"],
            "reference": entry.get("reference", ""),
            "seed": entry.get("seed", ""),
            "seconds": 0.0,
            "cer": None,
            "similarity": None,
            "mos": None,
            "reason": "",
        }
        if not path.is_file():
            row["reason"] = "missing_audio"
            rows.append(row)
            continue
        wave = audio_utils.trim(audio_utils.load(path, audio_utils.PIPER_RATE), audio_utils.PIPER_RATE)
        row["seconds"] = audio_utils.duration(wave, audio_utils.PIPER_RATE)
        wave_16k = audio_utils.resample(wave, audio_utils.PIPER_RATE, audio_utils.EMBED_RATE)
        if checks.cer is not None:
            row["cer"] = checks.cer(wave_16k, row["text"])
        if checks.embed is not None and checks.reference_embedding is not None:
            row["similarity"] = cosine(checks.embed(wave_16k), checks.reference_embedding)
        if checks.mos is not None:
            row["mos"] = checks.mos(wave_16k)
        rows.append(row)
    return rows


def decide(rows: list[dict], quality: QualityConfig, target: int) -> list[dict]:
    """Fill row['reason'] for rejected clips and mark surplus; returns rows of kept clips."""
    for row in rows:
        if not row["reason"]:
            row["reason"] = first_failure(row, quality, quality.min_similarity)
    passing = [row for row in rows if not row["reason"]]
    scores = [row["mos"] for row in passing if row["mos"] is not None]
    limit = drop_threshold(scores, quality.mos_drop_fraction)
    for row in passing:
        if row["mos"] is not None and row["mos"] < limit:
            row["reason"] = "low_mos"
    passing = [row for row in passing if not row["reason"]]
    passing.sort(key=lambda r: (r["similarity"] is None, -(r["similarity"] or 0.0)))
    for row in passing[target:]:
        row["reason"] = "surplus"
    return passing[:target]


def build_dataset(raw_dir: Path, dataset_dir: Path, kept: list[dict]) -> None:
    """Final clips: 22050 Hz / mono / 16-bit WAV, trimmed, level-normalized."""
    wav_dir = dataset_dir / WAV_DIR
    wav_dir.mkdir(parents=True, exist_ok=True)
    for old in wav_dir.glob("*.wav"):
        old.unlink()
    for row in kept:
        wave = audio_utils.load(raw_dir / f"{row['id']}.wav", audio_utils.PIPER_RATE)
        wave = audio_utils.normalize_level(
            audio_utils.trim(wave, audio_utils.PIPER_RATE), audio_utils.PIPER_RATE
        )
        audio_utils.save_wav(wav_dir / f"{row['id']}.wav", wave)
    write_metadata(dataset_dir / METADATA, [Utterance(row["id"], row["text"]) for row in kept])


def report_rows(rows: list[dict]) -> list[dict]:
    def fmt(value, digits=3):
        return "" if value is None else f"{value:.{digits}f}"

    return [
        {
            **row,
            "seconds": fmt(row["seconds"], 2),
            "cer": fmt(row["cer"]),
            "similarity": fmt(row["similarity"]),
            "mos": fmt(row["mos"], 2),
        }
        for row in rows
    ]


def screen(
    raw_dir: Path,
    dataset_dir: Path,
    quality: QualityConfig,
    target: int,
    checks: Checks,
    progress: Callable[[int, int], None] | None = None,
) -> list[dict]:
    # building the dataset starts by removing the old clips: an imported voice has no raw/ and
    # its recordings exist only in dataset/
    if not read_manifest(raw_dir):
        raise ValueError(f"no generated clips in {raw_dir}: nothing to filter, dataset left as it is")
    rows = measure(raw_dir, checks, progress)
    kept = decide(rows, quality, target)
    write_report(dataset_dir / "filter_report.csv", report_rows(rows), REPORT_FIELDS)
    if not kept:
        raise ValueError(
            f"no clip passed the filter, dataset left as it is: see {dataset_dir}/filter_report.csv"
        )
    build_dataset(raw_dir, dataset_dir, kept)
    return rows
