from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from piper_voice_cloner import synthesis
from piper_voice_cloner.backends.base import FatalSynthesisError


class FakeSynth:
    name = "fake"
    remote = False

    def __init__(self, fail_on=()):
        self.calls = []
        self.fail_on = set(fail_on)

    def synthesize(self, text, reference, seed):
        self.calls.append((text, Path(reference).name, seed))
        if text in self.fail_on:
            raise RuntimeError("model hiccup")
        return np.zeros(2400, dtype=np.float32), 24000


def prompts(n):
    return [(f"id{i}", f"Zdanie numer {['jeden', 'dwa', 'trzy'][i % 3]} tutaj.") for i in range(n)]


def test_plan_rotates_references_then_seeds():
    refs = [Path("ref_00.wav"), Path("ref_01.wav")]
    jobs = synthesis.plan(prompts(5), refs, [7, 8])
    assert [(j["reference"].name, j["seed"]) for j in jobs] == [
        ("ref_00.wav", 7),
        ("ref_01.wav", 7),
        ("ref_00.wav", 8),
        ("ref_01.wav", 8),
        ("ref_00.wav", 7),
    ]


def test_plan_requires_references_and_seeds():
    with pytest.raises(ValueError, match="pvc reference"):
        synthesis.plan(prompts(1), [], [1])
    with pytest.raises(ValueError, match="seeds"):
        synthesis.plan(prompts(1), [Path("r.wav")], [])


def test_run_resumes_and_skips_failures(tmp_path):
    jobs = synthesis.plan(prompts(4), [Path("ref_00.wav")], [1])
    failing = FakeSynth(fail_on={jobs[2]["text"]})
    assert synthesis.run(failing, jobs, tmp_path) == 3
    assert set(synthesis.read_manifest(tmp_path)) == {"id0", "id1", "id3"}

    again = FakeSynth()
    progress = []
    assert synthesis.run(again, jobs, tmp_path, progress=lambda i, n: progress.append(i)) == 1
    assert [c[0] for c in again.calls] == [jobs[2]["text"]]
    assert progress == [3]
    manifest = (tmp_path / synthesis.MANIFEST).read_text(encoding="utf-8").splitlines()
    assert manifest[0] == ",".join(synthesis.MANIFEST_FIELDS)
    assert len(manifest) == 5  # header once, 4 clips


def test_run_regenerates_when_audio_was_deleted(tmp_path):
    jobs = synthesis.plan(prompts(1), [Path("ref_00.wav")], [1])
    synthesis.run(FakeSynth(), jobs, tmp_path)
    (tmp_path / "id0.wav").unlink()
    assert synthesis.run(FakeSynth(), jobs, tmp_path) == 1


def test_run_records_how_fast_it_was(tmp_path):
    jobs = synthesis.plan(prompts(3), [Path("ref_00.wav")], [1])
    assert synthesis.read_timing(tmp_path) is None
    synth = FakeSynth(fail_on={jobs[1]["text"]})
    synth.device = "mps"
    synthesis.run(synth, jobs, tmp_path)
    timing = synthesis.read_timing(tmp_path)
    assert (timing.clips, timing.device) == (2, "mps")
    assert timing.audio_seconds == pytest.approx(0.2)  # 2 clips of 0.1 s
    assert timing.seconds >= 0 and "2 clips in" in timing.describe() and "on mps" in timing.describe()
    # a resumed run with nothing left keeps the last measurement
    synthesis.run(FakeSynth(), jobs[:1], tmp_path)
    assert synthesis.read_timing(tmp_path).clips == 2


def test_timing_numbers():
    timing = synthesis.Timing(clips=10, seconds=50.0, audio_seconds=40.0, device="cuda")
    assert timing.per_clip == 5.0 and timing.speed == 0.8
    assert timing.describe() == "10 clips in 0.8 min on cuda: 5.0 s per clip, 0.80x real time"
    assert synthesis.Timing(0, 0.0, 0.0, "cpu").per_clip == 0.0


class OutOfCredits(FakeSynth):
    def synthesize(self, text, reference, seed):
        if len(self.calls) == 2:
            raise FatalSynthesisError("quota_exceeded")
        return super().synthesize(text, reference, seed)


def test_fatal_error_stops_the_run_and_keeps_the_clips(tmp_path):
    jobs = synthesis.plan(prompts(5), [Path("-")], [1])
    with pytest.raises(FatalSynthesisError):
        synthesis.run(OutOfCredits(), jobs, tmp_path)
    assert sorted(synthesis.read_manifest(tmp_path)) == ["id0", "id1"]
    assert synthesis.read_timing(tmp_path).clips == 2
    assert synthesis.run(FakeSynth(), jobs, tmp_path) == 3


def test_clips_of_another_voice_are_not_mixed_in(tmp_path):
    jobs = synthesis.plan(prompts(2), [Path("-")], [1])
    first, second = FakeSynth(), FakeSynth()
    first.source, second.source = "elevenlabs:one", "elevenlabs:two"
    synthesis.run(first, jobs[:1], tmp_path)
    with pytest.raises(FatalSynthesisError, match="elevenlabs:one"):
        synthesis.run(second, jobs, tmp_path)
    assert second.calls == []
    assert synthesis.run(first, jobs, tmp_path) == 1
