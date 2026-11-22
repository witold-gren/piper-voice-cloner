from __future__ import annotations

import json
from pathlib import Path
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


def wav_files(folder, ids):
    (folder / "wav").mkdir(exist_ok=True)
    for clip in ids:
        (folder / "wav" / f"{clip}.wav").write_bytes(b"RIFF" + clip.encode())


def counting_scorer(tmp_path, scores):
    """Like fake_scorer, and writes down which clips it was asked to rate."""
    python = fake_scorer(tmp_path, scores)
    log = tmp_path / "asked.txt"
    wrapper = tmp_path / "counting"
    wrapper.write_text(f'#!/bin/sh\ncat "$3" >> "{log}"\nexec "{python}" "$@"\n')
    wrapper.chmod(0o755)
    return str(wrapper), log


def test_a_scored_clip_is_never_rated_again_unless_its_file_changed(tmp_path):
    folder = dataset(tmp_path, 6)
    wav_files(folder, [f"c{i}" for i in range(6)])
    scores = {f"c{i}": 3.0 + i / 10 for i in range(6)}
    python, log = counting_scorer(tmp_path, scores)
    first = dataset_quality.score_dataset(folder, 3, python=python)  # a sample of 3
    assert len(first["scores"]) == 3 and first["scored"] == 3
    log.write_text("")
    every = dataset_quality.score_dataset(folder, 0, python=python)  # then all: only the 3 others
    assert every["scores"] == scores and every["reused"] == 3 and every["scored"] == 3
    assert len(log.read_text().split()) == 3
    log.write_text("")
    again = dataset_quality.score_dataset(folder, 0, python=python)  # nothing new: the scorer does not run
    assert again["scores"] == scores and again["scored"] == 0 and log.read_text() == ""
    (folder / "wav" / "c2.wav").write_bytes(b"RIFF other recording")
    dataset_quality.score_dataset(folder, 0, python=python)
    assert log.read_text().split() == [str(folder / "wav" / "c2.wav")]  # only the changed clip


def test_a_clip_gone_from_the_dataset_drops_out_of_the_report(tmp_path):
    folder = dataset(tmp_path, 4)
    scores = {f"c{i}": 3.5 for i in range(4)}
    dataset_quality.score_dataset(folder, 0, python=fake_scorer(tmp_path, scores))
    write_metadata(folder / "metadata.csv", [Utterance(f"c{i}", f"Zdanie {i}.") for i in range(3)])
    report = dataset_quality.score_dataset(folder, 0, python=fake_scorer(tmp_path, scores))
    assert sorted(report["scores"]) == ["c0", "c1", "c2"] and report["scored"] == 0 and report["total"] == 3


def test_a_stopped_scoring_keeps_what_it_scored(tmp_path):
    folder = dataset(tmp_path, 5)
    helper = tmp_path / "half.py"
    # rates two clips, saves them (as score_clips.py does every 100) and fails
    helper.write_text(
        "import json, sys, pathlib\n"
        "files = pathlib.Path(sys.argv[3]).read_text().split()\n"
        "pathlib.Path(sys.argv[4]).write_text(json.dumps({f: 3.3 for f in files[:2]}))\n"
        "sys.exit(130)\n"
    )
    script = tmp_path / "half-python"
    script.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{helper}" "$@"\n')
    script.chmod(0o755)
    with pytest.raises(dataset_quality.ScoreError, match="exit code 130"):
        dataset_quality.score_dataset(folder, 0, python=str(script))
    assert dataset_quality.load(folder)["scores"] == {"c0": 3.3, "c1": 3.3}
    scores = {f"c{i}": 4.0 for i in range(5)}
    report = dataset_quality.score_dataset(folder, 0, python=fake_scorer(tmp_path, scores))
    assert report["reused"] == 2 and report["scores"]["c0"] == 3.3 and report["scores"]["c4"] == 4.0


def test_the_scores_of_a_report_from_before_the_stamps_are_kept(tmp_path):
    folder = dataset(tmp_path, 3)
    old = {"total": 3, "scores": {"c0": 3.2, "c1": 3.6}, "texts": {"c0": "Zdanie 0.", "c1": "Zdanie 1."}}
    dataset_quality.report_path(folder).write_text(json.dumps(old))
    python, log = counting_scorer(tmp_path, {"c0": 1.0, "c1": 1.0, "c2": 4.0})
    report = dataset_quality.score_dataset(folder, 0, python=python)
    assert report["scores"] == {"c0": 3.2, "c1": 3.6, "c2": 4.0} and report["reused"] == 2
    assert log.read_text().split() == [str(folder / "wav" / "c2.wav")]


def scored_dataset(tmp_path, scores):
    folder = tmp_path / "dataset"
    folder.mkdir()
    # an imported dataset: "<id>.wav|text" lines, kept as they are
    lines = "".join(f"{clip}.wav|Zdanie {clip}.\n" for clip in scores)
    (folder / "metadata.csv").write_text(lines, encoding="utf-8")
    report = {"total": len(scores), "scores": scores, "texts": {c: f"Zdanie {c}." for c in scores}}
    dataset_quality.report_path(folder).write_text(json.dumps(report))
    return folder


def test_prune_takes_weak_clips_out_and_keeps_everything_to_put_back(tmp_path):
    folder = scored_dataset(tmp_path, {"a": 2.4, "b": 3.6, "c": 2.9, "d": 4.1})
    before = (folder / "metadata.csv").read_text()
    result = dataset_quality.prune(folder, below=3.0)
    assert result["kept"] == 2 and result["removed"] == 2 and result["short"] == 1498
    assert (folder / "metadata.csv").read_text() == "b.wav|Zdanie b.\nd.wav|Zdanie d.\n"
    assert Path(result["backup"]).read_text() == before
    pruned = next(folder.glob("pruned-*.csv")).read_text().splitlines()
    assert pruned == ["a|2.400|Zdanie a.", "c|2.900|Zdanie c."]  # weakest first
    assert "1498 short of 1500" in dataset_quality.describe_prune(result)
    # the report follows the dataset: the clips taken out are gone from it on the next rating
    assert dataset_quality.prune(folder, below=3.0)["removed"] == 0


def test_prune_keeps_the_best(tmp_path):
    folder = scored_dataset(tmp_path, {"a": 2.4, "b": 3.6, "c": 2.9, "d": 4.1})
    result = dataset_quality.prune(folder, keep_best=3)
    assert result["kept"] == 3
    assert (folder / "metadata.csv").read_text() == "b.wav|Zdanie b.\nc.wav|Zdanie c.\nd.wav|Zdanie d.\n"


def test_prune_needs_every_clip_scored_and_one_rule(tmp_path):
    folder = scored_dataset(tmp_path, {"a": 2.4, "b": 3.6})
    with (folder / "metadata.csv").open("a") as handle:
        handle.write("x.wav|Nowe.\n")
    with pytest.raises(dataset_quality.ScoreError, match="1 of 3 clips are not scored"):
        dataset_quality.prune(folder, below=3.0)
    with pytest.raises(dataset_quality.ScoreError, match="either"):
        dataset_quality.prune(folder)


def test_a_clip_taken_out_keeps_its_score_while_its_file_is_there(tmp_path):
    folder = dataset(tmp_path, 3)
    wav_files(folder, ["c0", "c1", "c2"])
    python, log = counting_scorer(tmp_path, {"c0": 2.0, "c1": 3.5, "c2": 3.9})
    dataset_quality.score_dataset(folder, 0, python=python)
    before = (folder / "metadata.csv").read_text()
    dataset_quality.prune(folder, below=3.0)
    shown = dataset_quality.current(dataset_quality.load(folder), folder)
    assert sorted(shown["scores"]) == ["c1", "c2"] and shown["total"] == 2  # the summary: the dataset now
    log.write_text("")
    dataset_quality.score_dataset(folder, 0, python=python)  # the file keeps the score of c0
    (folder / "metadata.csv").write_text(before)  # the dataset put back
    report = dataset_quality.score_dataset(folder, 0, python=python)
    assert report["scores"]["c0"] == 2.0 and report["scored"] == 0 and log.read_text() == ""
