from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from piper_voice_cloner import audition, reference
from piper_voice_cloner.screening import Checks

from .conftest import requires_ffmpeg, tone, write_tone


class GridSynth:
    """Quality depends on cfg_weight so the ranking is predictable."""

    name = "fake"
    remote = False

    def __init__(self):
        self.options = {}

    def synthesize(self, text, reference, seed):
        return tone(1.0, 24000, level=0.1 + self.options["cfg_weight"]), 24000


def test_combinations_and_slug():
    combos = audition.combinations({"b": [1, 2], "a": ["x"]})
    assert combos == [{"a": "x", "b": 1}, {"a": "x", "b": 2}]
    assert audition.slug({"b": 1, "a": "x"}) == "a-x_b-1"
    assert audition.combinations({}) == [{}]
    assert audition.slug({}) == "default"


@requires_ffmpeg
def test_audition_ranks_and_writes_html(tmp_path):
    synth = GridSynth()
    level_to_cer = {}

    def fake_cer(audio_16k, text):
        level = float(np.max(np.abs(audio_16k)))
        level_to_cer[round(level, 1)] = text
        return 0.5 - level  # louder = "better" here

    checks = Checks(cer=fake_cer)
    results = audition.run(
        synth,
        {"exaggeration": 0.5},
        {"cfg_weight": [0.0, 0.3]},
        [("p1", "Ala ma kota."), ("p2", "Kot ma Alę.")],
        [Path("ref_00.wav")],
        tmp_path,
        checks,
    )
    assert [r.options for r in results] == [{"cfg_weight": 0.3}, {"cfg_weight": 0.0}]
    assert results[0].mean("similarity") is None
    page = (tmp_path / "audition.html").read_text(encoding="utf-8")
    assert "cfg_weight-0.3/p1.wav" in page and "Ala ma kota." in page
    assert (tmp_path / "cfg_weight-0.0" / "p2.wav").is_file()


def test_split():
    rate = 1000
    assert reference.split(np.zeros(2000), rate, 12, 3) == []
    pieces = reference.split(np.zeros(30_000), rate, 12, 3)
    assert len(pieces) == 3 and all(len(p) == 10_000 for p in pieces)


@requires_ffmpeg
def test_prepare_reference(tmp_path):
    clips = [write_tone(tmp_path / "a.wav", 20.0, 44100, silence=0.5), write_tone(tmp_path / "b.wav", 5.0)]
    embeds = []

    def embed(audio_16k):
        embeds.append(len(audio_16k))
        return np.array([1.0, 0.05 * len(embeds)])

    info = reference.prepare(clips, tmp_path / "ref", embed)
    assert info["prompts"] == ["ref_00.wav", "ref_01.wav", "ref_02.wav"]
    assert 24.5 < info["seconds"] < 26.5
    assert info["chunks"] == len(embeds) >= 5
    assert 0.35 <= info["min_similarity"] <= 1.0
    stored = json.loads((tmp_path / "ref" / "reference.json").read_text())
    assert stored == info
    assert sf.info(tmp_path / "ref" / "clean" / "ref_00.wav").samplerate == 24000
    assert reference.prompt_paths(tmp_path / "ref")[0].name == "ref_00.wav"
    assert reference.load_embedding(tmp_path / "ref").shape == (2,)


@requires_ffmpeg
def test_prepare_reference_too_short(tmp_path):
    clip = write_tone(tmp_path / "a.wav", 1.0)
    with pytest.raises(ValueError, match="no usable reference"):
        reference.prepare([clip], tmp_path / "ref", None)


@requires_ffmpeg
def test_prepare_reference_without_embedding(tmp_path):
    info = reference.prepare([write_tone(tmp_path / "a.wav", 8.0)], tmp_path / "ref", None)
    assert "min_similarity" not in info
    assert reference.load_embedding(tmp_path / "ref") is None
    assert reference.is_short(info)  # 8 s, one prompt


def test_short_reference_warning():
    assert reference.is_short({"seconds": 15.0, "prompts": ["ref_00.wav", "ref_01.wav"]})  # below 20 s
    assert reference.is_short({"seconds": 25.0, "prompts": ["ref_00.wav"]})  # one prompt only
    assert not reference.is_short({"seconds": 30.0, "prompts": ["ref_00.wav", "ref_01.wav", "ref_02.wav"]})
