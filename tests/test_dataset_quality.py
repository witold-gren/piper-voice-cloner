from __future__ import annotations

import json
import sys

import pytest

from piper_voice_cloner import dataset_quality
from piper_voice_cloner.dataset import Utterance, write_metadata


def fake_scorer(tmp_path, scores: dict[str, float]) -> str:
    """A "training Python" that answers like score_clips.py: progress lines and a JSON of scores."""
    helper = tmp_path / "scorer.py"
    helper.write_text(
        "import json, sys, pathlib\n"
        "files = pathlib.Path(sys.argv[3]).read_text().split()\n"
        f"scores = {scores!r}\n"
        "for i, f in enumerate(files, 1):\n"
        "    print(f'scored {i}/{len(files)}', flush=True)\n"
        "pathlib.Path(sys.argv[4]).write_text(json.dumps({f: scores[pathlib.Path(f).stem] for f in files}))\n"
    )
    # argv as the real one gets it: -I score_clips.py <list> <out> (a shell script: paths may have spaces)
    script = tmp_path / "train-python"
    script.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{helper}" "$@"\n')
    script.chmod(0o755)
    return str(script)


def dataset(tmp_path, n: int):
    folder = tmp_path / "dataset"
    write_metadata(folder / "metadata.csv", [Utterance(f"c{i}", f"Zdanie {i}.") for i in range(n)])
    return folder


def test_pick_is_repeatable_and_takes_all_when_asked():
    ids = [f"c{i}" for i in range(100)]
    assert (
        dataset_quality.pick(ids, 10) == dataset_quality.pick(ids, 10)
        and len(dataset_quality.pick(ids, 10)) == 10
    )
    assert dataset_quality.pick(ids, 0) == ids and dataset_quality.pick(ids, 500) == ids


def test_score_dataset_runs_the_training_python_and_saves_the_report(tmp_path):
    folder = dataset(tmp_path, 12)
    scores = {f"c{i}": 3.0 + i / 10 for i in range(12)}
    seen = []
    report = dataset_quality.score_dataset(
        folder, 0, python=fake_scorer(tmp_path, scores), progress=lambda d, t: seen.append((d, t))
    )
    assert report["scores"] == scores and report["total"] == 12 and report["texts"]["c3"] == "Zdanie 3."
    assert seen[-1] == (12, 12)
    assert dataset_quality.load(folder)["scores"] == scores  # kept in <dataset>/utmos.json
    s = dataset_quality.summary(report)
    assert s["count"] == 12 and s["median"] == pytest.approx(3.55) and s["good"] == pytest.approx(2 / 12)
    assert s["worst"][0] == ("c0", 3.0) and s["best"][0] == ("c11", 4.1) and len(s["worst"]) == 5
    assert s["p10"] < s["median"] < s["p90"]
    assert "median 3.55" in dataset_quality.describe(report)


def test_score_dataset_reports_a_broken_training_python(tmp_path):
    folder = dataset(tmp_path, 3)
    broken = tmp_path / "py"
    broken.write_text("#!/bin/sh\nexit 2\n")
    broken.chmod(0o755)
    with pytest.raises(dataset_quality.ScoreError, match="exit code 2"):
        dataset_quality.score_dataset(folder, 0, python=str(broken))
    assert dataset_quality.load(folder) is None


def test_scoring_script_reads_16_bit_wav(tmp_path):
    pytest.importorskip("torch")  # the training environment only
    from piper_voice_cloner import score_clips
    from tests.test_train_monitor import _wav

    path = tmp_path / "a.wav"
    path.write_bytes(_wav(0.1))
    audio, rate = score_clips.read_wav(str(path))
    assert rate == 22050 and len(audio) == 2205 and json.dumps(float(audio.max())) == "0.0"
