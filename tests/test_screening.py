from __future__ import annotations

import numpy as np
import pytest
import soundfile as sf

from piper_voice_cloner.config import QualityConfig
from piper_voice_cloner.dataset import read_metadata
from piper_voice_cloner.screening import Checks, decide, first_failure, screen
from piper_voice_cloner.synthesis import MANIFEST

from .conftest import requires_ffmpeg, write_tone

TEXT = "Ala ma kota a kot ma Alę."  # 18 letters


def row(**kw):
    base = {"id": "x", "text": TEXT, "seconds": 1.8, "cer": 0.0, "similarity": 0.8, "mos": 3.5, "reason": ""}
    return {**base, **kw}


def test_first_failure_reasons():
    q = QualityConfig(min_similarity=0.5)
    assert first_failure(row(), q, 0.5) == ""
    assert first_failure(row(seconds=0.3), q, 0.5) == "too_fast_or_cut"
    assert first_failure(row(seconds=6.0), q, 0.5) == "too_slow_or_hallucinated"
    assert first_failure(row(cer=0.2), q, 0.5) == "asr_mismatch"
    assert first_failure(row(similarity=0.3), q, 0.5) == "speaker_mismatch"
    assert first_failure(row(similarity=None, cer=None), q, 0.5) == ""
    assert first_failure(row(similarity=0.3), q, None) == ""


def test_decide_mos_and_surplus():
    q = QualityConfig(min_similarity=0.5, mos_drop_fraction=0.25)
    rows = [row(id=f"c{i}", similarity=0.6 + i / 100, mos=1.0 + i) for i in range(8)]
    rows.append(row(id="bad", cer=0.9))
    kept = decide(rows, q, target=4)
    reasons = {r["id"]: r["reason"] for r in rows}
    assert reasons["bad"] == "asr_mismatch"
    assert reasons["c0"] == reasons["c1"] == "low_mos"
    assert [r["id"] for r in kept] == ["c7", "c6", "c5", "c4"]  # most similar first
    assert reasons["c2"] == reasons["c3"] == "surplus"


def write_raw(raw_dir, clips):
    raw_dir.mkdir(parents=True)
    lines = ["id,text,reference,seed,backend,rate"]
    for utt_id, text, seconds in clips:
        write_tone(raw_dir / f"{utt_id}.wav", seconds, 24000, silence=0.3)
        lines.append(f'{utt_id},"{text}",ref_00.wav,1,fake,24000')
    (raw_dir / MANIFEST).write_text("\n".join(lines) + "\n", encoding="utf-8")


@requires_ffmpeg
def test_screen_end_to_end(tmp_path):
    raw = tmp_path / "raw"
    write_raw(raw, [("ok1", TEXT, 1.8), ("ok2", TEXT, 1.6), ("cut", TEXT, 0.2), ("halluc", TEXT, 5.0)])
    reference = np.array([1.0, 0.0])
    checks = Checks(
        cer=lambda audio, text: 0.0,
        embed=lambda audio: np.array([1.0, 0.1]),
        reference_embedding=reference,
        mos=lambda audio: 3.0,
    )
    rows = screen(
        raw, tmp_path / "dataset", QualityConfig(min_similarity=0.5, mos_drop_fraction=0), 10, checks
    )
    reasons = {r["id"]: r["reason"] for r in rows}
    assert reasons == {"ok1": "", "ok2": "", "cut": "too_fast_or_cut", "halluc": "too_slow_or_hallucinated"}
    kept = read_metadata(tmp_path / "dataset" / "metadata.csv")
    assert {u.id for u in kept} == {"ok1", "ok2"}
    info = sf.info(tmp_path / "dataset" / "wav" / "ok1.wav")
    assert (info.samplerate, info.subtype) == (22050, "PCM_16")
    assert (tmp_path / "dataset" / "filter_report.csv").is_file()


@requires_ffmpeg
def test_screen_without_models_uses_length_rules_only(tmp_path):
    raw = tmp_path / "raw"
    write_raw(raw, [("ok1", TEXT, 1.8)])
    rows = screen(raw, tmp_path / "dataset", QualityConfig(), 10, Checks())
    assert rows[0]["reason"] == ""
    assert rows[0]["cer"] is None and rows[0]["similarity"] is None


def test_filter_without_generated_clips_keeps_an_imported_dataset(tmp_path):
    dataset_dir = tmp_path / "dataset"
    (dataset_dir / "wav").mkdir(parents=True)
    clip = dataset_dir / "wav" / "a.wav"
    clip.write_bytes(b"x")
    (dataset_dir / "metadata.csv").write_text("a|Zdanie.\n", encoding="utf-8")
    with pytest.raises(ValueError, match="nothing to filter"):
        screen(tmp_path / "raw", dataset_dir, QualityConfig(), 10, Checks())
    assert clip.is_file()
    assert (dataset_dir / "metadata.csv").read_text(encoding="utf-8") == "a|Zdanie.\n"
