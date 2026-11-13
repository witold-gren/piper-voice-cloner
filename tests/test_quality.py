from __future__ import annotations

import numpy as np
import pytest

from piper_voice_cloner.quality.asr import cer, compute_type, edit_distance
from piper_voice_cloner.quality.mos import drop_threshold
from piper_voice_cloner.quality.speaker import calibrate_threshold, centroid, cosine, normalize


@pytest.mark.parametrize(("a", "b", "d"), [("", "", 0), ("kot", "kot", 0), ("kot", "kat", 1), ("", "abc", 3)])
def test_edit_distance(a, b, d):
    assert edit_distance(a, b) == d
    assert edit_distance(b, a) == d


def test_cer_ignores_case_and_punctuation(pl):
    assert cer("Ala ma kota.", "ala ma kota", pl) == 0.0
    assert cer("Zażółć gęślą jaźń!", "zażółć gęślą jaźń", pl) == 0.0
    assert cer("ala ma kota", "ala ma psa", pl) == pytest.approx(3 / 11)
    assert cer("", "", pl) == 0.0
    assert cer("...", "coś", pl) == 1.0


def test_cosine_and_centroid():
    a = np.array([1.0, 0.0])
    b = np.array([0.0, 2.0])
    assert cosine(a, a) == pytest.approx(1.0)
    assert cosine(a, b) == pytest.approx(0.0)
    assert np.linalg.norm(centroid([a, b])) == pytest.approx(1.0)
    assert np.allclose(normalize(np.zeros(2)), 0)
    with pytest.raises(ValueError):
        centroid([])


def test_calibrate_threshold_follows_reference_spread():
    rng = np.random.default_rng(0)
    base = rng.normal(size=192)
    tight = [base + rng.normal(scale=0.1, size=192) for _ in range(8)]
    loose = [base + rng.normal(scale=1.5, size=192) for _ in range(8)]
    assert calibrate_threshold(tight) > calibrate_threshold(loose)
    assert calibrate_threshold(loose, floor=0.35) >= 0.35
    assert calibrate_threshold([base]) == 0.35


def test_drop_threshold():
    scores = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    assert drop_threshold(scores, 0.1) == pytest.approx(1.9)
    assert drop_threshold(scores, 0) == float("-inf")
    assert drop_threshold([], 0.1) == float("-inf")


def test_whisper_compute_type():
    assert compute_type("auto", 1) == "float16" and compute_type("cuda", 0) == "float16"
    assert compute_type("auto", 0) == "int8"  # a Mac or a computer without NVIDIA: float16 fails on the CPU
    assert compute_type("cpu", 2) == "int8"
