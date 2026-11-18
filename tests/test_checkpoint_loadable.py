"""Checkpoints with pathlib paths inside (the lessac base) must open with weights_only=True, which
Lightning 2.6 uses; make_loadable turns the paths into text once, in place."""

from __future__ import annotations

from pathlib import Path, PosixPath
import sys

import pytest

from piper_voice_cloner import train

torch = pytest.importorskip("torch")


def old_checkpoint(path: Path) -> Path:
    torch.save(
        {
            "epoch": 2164,
            "state_dict": {"layer.weight": torch.ones(2, 2)},
            "hyper_parameters": {
                "dataset": [PosixPath("/old/dataset.jsonl")],
                "dataset_dir": PosixPath("/old"),
                "sample_rate": 22050,
            },
        },
        path,
    )
    return path


def test_an_old_checkpoint_is_refused_by_lightning_and_then_opens(tmp_path):
    ckpt = old_checkpoint(tmp_path / "lessac.ckpt")
    with pytest.raises(Exception, match="PosixPath"):
        torch.load(ckpt, map_location="cpu", weights_only=True)
    said = train.make_loadable(ckpt, python=sys.executable)
    assert said.startswith("cleaned") and "hyper_parameters.dataset_dir" in said
    data = torch.load(ckpt, map_location="cpu", weights_only=True)
    assert data["hyper_parameters"]["dataset"] == ["/old/dataset.jsonl"]
    assert data["epoch"] == 2164 and torch.equal(data["state_dict"]["layer.weight"], torch.ones(2, 2))
    assert not (tmp_path / "lessac.ckpt.loadable").exists()


def test_a_good_checkpoint_is_left_as_it_is(tmp_path):
    ckpt = tmp_path / "own.ckpt"
    torch.save({"epoch": 3, "state_dict": {}, "hyper_parameters": {"dataset_dir": "/data"}}, ckpt)
    before = ckpt.stat().st_mtime_ns
    assert train.make_loadable(ckpt, python=sys.executable) == "ok"
    assert ckpt.stat().st_mtime_ns == before


def test_options_the_model_does_not_take_leave(tmp_path, monkeypatch):
    """Lightning 2.6 passes hyper_parameters to VitsModel; the old trainer's options broke the start
    (`fit does not accept option 'model.sample_bytes'`)."""
    fake = tmp_path / "fake" / "piper" / "train" / "vits"
    fake.mkdir(parents=True)
    for folder in (fake.parent.parent, fake.parent, fake):
        (folder / "__init__.py").write_text("")
    (fake / "lightning.py").write_text(
        "class VitsModel:\n    def __init__(self, sample_rate=22050, dataset=None, **kwargs): ...\n"
    )
    monkeypatch.setenv("PYTHONPATH", str(tmp_path / "fake"))
    ckpt = old_checkpoint(tmp_path / "lessac.ckpt")
    data = torch.load(ckpt, map_location="cpu", weights_only=False)
    data["hyper_parameters"].update(sample_bytes=2, gpus=1)
    torch.save(data, ckpt)
    said = train.make_loadable(ckpt, python=sys.executable)
    assert "dropped dataset_dir gpus sample_bytes" in said
    kept = torch.load(ckpt, map_location="cpu", weights_only=True)["hyper_parameters"]
    assert kept == {"dataset": ["/old/dataset.jsonl"], "sample_rate": 22050}
    assert train.make_loadable(ckpt, python=sys.executable) == "ok"  # once


def test_a_broken_file_says_so(tmp_path):
    broken = tmp_path / "broken.ckpt"
    broken.write_bytes(b"not a checkpoint")
    with pytest.raises(train.TrainError, match="cannot prepare"):
        train.make_loadable(broken, python=sys.executable)
