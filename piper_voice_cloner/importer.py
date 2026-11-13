"""Import an existing LJSpeech-style dataset (e.g. older ElevenLabs runs) into a clean one.

- text goes through `text_filter` (rejected lines are reported, never rewritten),
- persona files written as numbered lists get the numbering stripped first,
- audio is decoded whatever it really is (MP3 files named .wav included) and saved as real
  22050 Hz / mono / 16-bit WAV, trimmed and level-normalized,
- optional `verify` callback (ASR) rejects clips whose audio does not match the text.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import logging
import os
from pathlib import Path

import numpy as np

from . import audio as audio_utils, text_filter
from .dataset import METADATA, WAV_DIR, Utterance, read_metadata, write_metadata, write_report
from .languages import LanguagePack

_LOGGER = logging.getLogger(__name__)

MIN_SECONDS = 0.6
MAX_SECONDS = 20.0
REPORT_FIELDS = ["id", "source", "text", "seconds", "cer", "reason"]

# (audio at 16 kHz, expected text) -> character error rate
Verifier = Callable[[np.ndarray, str], float]


@dataclass(frozen=True)
class Source:
    metadata: Path
    persona: bool = False


def find_audio(audio_dir: Path, utt_id: str) -> Path | None:
    for candidate in (audio_dir / f"{utt_id}.wav", audio_dir / utt_id):
        if candidate.is_file():
            return candidate
    return None


def import_dataset(
    sources: list[Source],
    audio_dir: Path,
    out_dir: Path,
    lang: LanguagePack,
    *,
    verify: Verifier | None = None,
    max_cer: float = 0.04,
    workers: int | None = None,
    min_words: int = 1,
    max_words: int = 60,
    progress: Callable[[int, int], None] | None = None,
) -> list[dict]:
    """Build out_dir/metadata.csv + out_dir/wav/*.wav; returns one report row per input line."""
    candidates: list[tuple[Utterance, str, bool]] = []
    seen: set[str] = set()
    for source in sources:
        for utt in read_metadata(source.metadata):
            if utt.id in seen:
                continue
            seen.add(utt.id)
            candidates.append((utt, source.metadata.name, source.persona))

    def process(item: tuple[Utterance, str, bool]) -> dict:
        utt, source_name, persona = item
        text = text_filter.strip_list_numbering(utt.text) if persona else utt.text
        row = {"id": utt.id, "source": source_name, "text": text, "seconds": "", "cer": "", "reason": ""}
        # recorded data: short replies are valuable, long ones are limited by MAX_SECONDS
        verdict = text_filter.check(text, lang, min_words=min_words, max_words=max_words)
        row["text"] = verdict.text
        if not verdict.ok:
            row["reason"] = f"text:{verdict.reason}"
            return row
        src = find_audio(audio_dir, utt.id)
        if src is None:
            row["reason"] = "missing_audio"
            return row
        target = out_dir / WAV_DIR / f"{utt.id}.wav"
        try:
            wave = audio_utils.load(src, audio_utils.PIPER_RATE)
        except audio_utils.AudioError as err:
            _LOGGER.warning("%s", err)
            row["reason"] = "decode_error"
            return row
        wave = audio_utils.normalize_level(
            audio_utils.trim(wave, audio_utils.PIPER_RATE), audio_utils.PIPER_RATE
        )
        seconds = audio_utils.duration(wave, audio_utils.PIPER_RATE)
        row["seconds"] = f"{seconds:.2f}"
        if not MIN_SECONDS <= seconds <= MAX_SECONDS:
            row["reason"] = "duration"
            return row
        if verify is not None:
            cer = verify(
                audio_utils.resample(wave, audio_utils.PIPER_RATE, audio_utils.EMBED_RATE), verdict.text
            )
            row["cer"] = f"{cer:.3f}"
            if cer > max_cer:
                row["reason"] = "asr_mismatch"
                return row
        audio_utils.save_wav(target, wave)
        return row

    # ASR verification uses one GPU model - keep it sequential then
    pool = 1 if verify is not None else (workers or min(8, os.cpu_count() or 1))
    with ThreadPoolExecutor(max_workers=pool) as executor:
        rows = []
        for row in executor.map(process, candidates):
            rows.append(row)
            if progress:
                progress(len(rows), len(candidates))

    kept = [Utterance(row["id"], row["text"]) for row in rows if not row["reason"]]
    write_metadata(out_dir / METADATA, kept)
    write_report(out_dir / "import_report.csv", rows, REPORT_FIELDS)
    return rows
