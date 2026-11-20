"""Nothing earlier is lost: a training started over keeps the run before it whole (its samples, chart and
checkpoints), an export never overwrites a file, a new bazowy-pl keeps the base before it and a ZIP
uploaded again keeps the earlier upload."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import zipfile

import pytest

from piper_voice_cloner import train as train_mod, train_monitor

sys.path.insert(0, str(Path(__file__).parent))
from test_train_monitor import validation, write


def events(work: Path, version: int) -> Path:
    return work / "lightning_logs" / f"version_{version}" / "events.out.tfevents.1.host"


def start_run(work: Path, first_version: int, start: int) -> None:
    """What `pvc train --no-resume` does before Lightning starts (cli._train)."""
    before = train_monitor.run_info(work)
    plan = {"start_epoch": start, "base": "lessac", "quality": "medium", "first_version": first_version}
    (work / "run.json").write_text(json.dumps(plan))
    if before:
        train_monitor.archive_monitor(work, before)


def test_a_new_run_keeps_the_one_before_whole_even_with_the_same_epochs(tmp_path):
    work = tmp_path / "train"
    work.mkdir()
    (work / "run.json").write_text(json.dumps({"start_epoch": 0, "base": "bazowy-pl"}))
    write(
        events(work, 0),
        *(item for epoch in range(6) for item in validation(100 * (epoch + 1), epoch, 2.0 + epoch / 10)),
    )
    old = train_monitor.update(work)
    old_files = {s.path.name: s.path.read_bytes() for clips in old.samples.values() for s in clips}
    assert old.epochs

    # started over from the same base: the same epoch numbers again, in version_1
    start_run(work, train_monitor.next_version(work), 0)
    assert json.loads((work / "run.json").read_text())["first_version"] == 1
    write(
        events(work, 1), *(item for epoch in range(3) for item in validation(1000 + 100 * epoch, epoch, 3.0))
    )
    new = train_monitor.update(work)
    assert sorted(new.samples) == [0, 1, 2] and all(new.value("val_mos", e) == 3.0 for e in range(3))

    # the run before: in runs/0, every sample file as it was, its chart, never thinned again
    kept = train_monitor.load_run(work, "0")
    assert {s.path.name: s.path.read_bytes() for clips in kept.samples.values() for s in clips} == old_files
    assert abs(kept.value("val_mos", 5) - 2.5) < 1e-6
    listed = train_monitor.runs(work)
    assert [r["id"] for r in listed] == ["0"] and listed[0]["base"] == "bazowy-pl"
    assert listed[0]["last_version"] == 0 and abs(listed[0]["best_mos"] - 2.5) < 1e-6


def test_a_start_that_did_not_move_the_monitor_is_moved_by_the_monitor(tmp_path):
    work = tmp_path / "train"
    work.mkdir()
    write(events(work, 0), *validation(100, 0, 2.0))
    train_monitor.update(work)
    # run.json of a new run written, the move did not happen (the job stopped right there)
    (work / "run.json").write_text(json.dumps({"start_epoch": 0, "first_version": 1}))
    write(events(work, 1), *validation(500, 0, 3.0))
    run = train_monitor.update(work)
    assert run.value("val_mos", 0) == 3.0
    assert (work / "runs" / "0" / "monitor" / "state.json").is_file()
    assert train_monitor.load_run(work, "0").value("val_mos", 0) == 2.0


def test_the_command_never_moves_the_monitor_of_another_run(tmp_path):
    work = tmp_path / "train"
    work.mkdir()
    (work / "run.json").write_text(json.dumps({"start_epoch": 0, "first_version": 1}))
    write(events(work, 1), *validation(100, 0, 3.0))
    train_monitor.update(work)  # the monitor of run 1
    assert train_monitor.archive_monitor(work, {"first_version": 0}) is None
    assert (work / "monitor" / "state.json").is_file()


def test_an_unknown_earlier_run_is_refused(tmp_path):
    for bad in ("../x", "nope"):
        with pytest.raises(ValueError):
            train_monitor.load_run(tmp_path, bad)


def test_resume_only_goes_on_from_the_current_run(tmp_path):
    work = tmp_path / "train"
    old = work / "lightning_logs" / "version_0" / "checkpoints" / "epoch=1600-step=1.ckpt"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"x")
    (work / "run.json").write_text(json.dumps({"start_epoch": 2164, "first_version": 1}))
    # the new run stopped before its first checkpoint: nothing of the run before is taken
    assert train_mod.resume_checkpoint(work, current_run=True) is None
    new = work / "lightning_logs" / "version_1" / "checkpoints" / "last.ckpt"
    new.parent.mkdir(parents=True)
    new.write_bytes(b"x")
    assert train_mod.resume_checkpoint(work, current_run=True) == new


def test_an_export_never_overwrites_one_made_before(tmp_path):
    folder = tmp_path / "export"
    assert train_mod.free_export_path(folder, "pl_PL-meski-medium").name == "pl_PL-meski-medium.onnx"
    folder.mkdir()
    (folder / "pl_PL-meski-medium.onnx").write_bytes(b"old")
    assert train_mod.free_export_path(folder, "pl_PL-meski-medium").name == "pl_PL-meski_2-medium.onnx"
    (folder / "pl_PL-meski_2-medium.onnx.json").write_text("{}")  # a half export counts too
    assert train_mod.free_export_path(folder, "pl_PL-meski-medium").name == "pl_PL-meski_3-medium.onnx"


def test_a_new_base_keeps_the_base_before(tmp_path):
    from typer.testing import CliRunner

    from piper_voice_cloner.cli import app

    bases = tmp_path / "bases"
    bases.mkdir()
    (bases / "pl-scratch.ckpt").write_bytes(b"old base")
    for content in (b"new base", b"newer base"):
        chosen = tmp_path / "chosen.ckpt"
        chosen.write_bytes(content)
        result = CliRunner().invoke(app, ["--root", str(tmp_path), "base", "select", str(chosen)])
        assert result.exit_code == 0, result.output
    assert (bases / "pl-scratch.ckpt").read_bytes() == b"newer base"
    assert (bases / "pl-scratch-1.ckpt").read_bytes() == b"old base"
    assert (bases / "pl-scratch-2.ckpt").read_bytes() == b"new base"


def _zip(path: Path, with_metadata: bool) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        if with_metadata:
            archive.writestr("metadata.csv", "a|Ala ma kota.\n")
        archive.writestr("wav/a.wav", b"RIFF")
    return path


def test_a_zip_sent_again_keeps_the_earlier_upload(tmp_path):
    from piper_voice_cloner.editor import steps

    first = steps.unpack_dataset(tmp_path, "kuba", _zip(tmp_path / "1.zip", True))
    (first / "note.txt").write_text("earlier")
    second = steps.unpack_dataset(tmp_path, "kuba", _zip(tmp_path / "2.zip", True))
    assert second == first and (first.with_name("kuba_2") / "note.txt").read_text() == "earlier"
    # a ZIP without metadata.csv: refused, the earlier upload back under its name
    (second / "note.txt").write_text("second")
    with pytest.raises(ValueError):
        steps.unpack_dataset(tmp_path, "kuba", _zip(tmp_path / "3.zip", False))
    assert (first / "note.txt").read_text() == "second"
    assert not first.with_name("kuba_3").exists()
