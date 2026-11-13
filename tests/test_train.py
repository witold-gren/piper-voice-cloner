from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from piper_voice_cloner import train
from piper_voice_cloner.config import TrainConfig


def paths(tmp_path):
    return train.TrainPaths(tmp_path / "dataset", tmp_path / "train")


def arg(cmd, name):
    return cmd[cmd.index(name) + 1]


def test_fit_command_from_scratch_has_no_ckpt(tmp_path, pl):
    cmd = train.fit_command("baza", paths(tmp_path), pl, TrainConfig(max_epochs=3000), None, python="py")
    assert cmd[:4] == ["py", "-m", "piper.train", "fit"]
    assert "--ckpt_path" not in cmd
    assert arg(cmd, "--data.espeak_voice") == "pl"
    assert arg(cmd, "--model.sample_rate") == "22050"
    assert arg(cmd, "--trainer.max_epochs") == "3000"
    assert arg(cmd, "--data.csv_path").endswith("dataset/metadata.csv")
    assert arg(cmd, "--data.audio_dir").endswith("dataset/wav")
    assert arg(cmd, "--data.config_path").endswith("train/config.json")
    assert arg(cmd, "--data.num_workers") == "8"


def test_fit_command_finetune_counts_epochs_on_top(tmp_path, pl):
    ckpt = tmp_path / "base.ckpt"
    cfg = TrainConfig(max_epochs=500, batch_size=16, extra_args=["--trainer.precision", "16-mixed"])
    cmd = train.fit_command("kuba", paths(tmp_path), pl, cfg, ckpt, start_epoch=2164)
    assert arg(cmd, "--ckpt_path") == str(ckpt)
    assert arg(cmd, "--trainer.max_epochs") == "2664"
    assert arg(cmd, "--data.batch_size") == "16"
    assert cmd[-2:] == ["--trainer.precision", "16-mixed"]


def _fake_python(tmp_path, script: str) -> str:
    fake = tmp_path / "python"
    fake.write_text("#!/bin/sh\n" + script)
    fake.chmod(0o755)
    return str(fake)


def test_checkpoint_info_reads_epoch_and_size(tmp_path):
    ckpt = tmp_path / "last.ckpt"
    ckpt.write_bytes(b"x")
    python = _fake_python(tmp_path, "echo 'some warning'\necho 4321 high\n")
    assert train.checkpoint_info(ckpt, python=python) == train.CheckpointInfo(4321, "high")
    python = _fake_python(tmp_path, "echo 2164\n")  # an old answer without the size
    assert train.checkpoint_info(ckpt, python=python) == train.CheckpointInfo(2164, "medium")


def test_checkpoint_info_name_epoch_wins(tmp_path):
    ckpt = tmp_path / "epoch=12-val_mel=0.3.ckpt"
    python = _fake_python(tmp_path, "echo 99 high\n")
    assert train.checkpoint_info(ckpt, python=python) == train.CheckpointInfo(12, "high")
    # torch missing (a dry run on a laptop): the name still gives the epoch
    broken = _fake_python(tmp_path, "exit 1\n")
    assert train.checkpoint_info(ckpt, python=broken) == train.CheckpointInfo(12, "medium")


def test_checkpoint_info_without_torch_fails_clearly(tmp_path):
    ckpt = tmp_path / "last.ckpt"
    ckpt.write_bytes(b"x")
    python = _fake_python(tmp_path, "echo 'No module named torch' >&2\nexit 1\n")
    with pytest.raises(train.TrainError, match="cannot read the epoch"):
        train.checkpoint_info(ckpt, python=python)


def test_high_model_arguments(tmp_path, pl):
    cfg = TrainConfig()
    medium = train.fit_command("kuba", paths(tmp_path), pl, cfg, None, python="py")
    high = train.fit_command("kuba", paths(tmp_path), pl, cfg, None, quality="high", python="py")
    assert "--model.upsample_initial_channel" not in medium
    added = high[len(medium) :]
    assert added == train.MODEL_ARGS["high"]
    assert added[added.index("--model.upsample_rates") + 1] == "[8, 8, 2, 2]"
    assert train.base_folder(tmp_path, "high").name == "pl-scratch-high"
    assert train.base_folder(tmp_path).name == "pl-scratch"
    with pytest.raises(train.TrainError, match="quality"):
        train.base_folder(tmp_path, "x-high")


def test_resolve_base_modes(tmp_path):
    bases = tmp_path / "bases"
    own = tmp_path / "own.ckpt"
    own.write_bytes(b"x")
    assert train.resolve_base(f"ckpt:{own}", bases) == own
    with pytest.raises(train.TrainError, match="not found"):
        train.resolve_base("ckpt:/nope.ckpt", bases)
    with pytest.raises(train.TrainError, match="create the bazowy-pl base first"):
        train.resolve_base("bazowy-pl", bases)
    (bases).mkdir()
    (bases / train.SCRATCH_BASE).write_bytes(b"x")
    assert train.resolve_base("bazowy-pl", bases) == bases / train.SCRATCH_BASE
    assert train.resolve_base("scratch-pl", bases) == bases / train.SCRATCH_BASE  # the old name
    with pytest.raises(train.TrainError, match="missing"):
        train.resolve_base("lessac", bases, download=False)
    (bases / "en_US-lessac-medium.ckpt").write_bytes(b"x")
    assert train.resolve_base("lessac", bases, download=False).name == "en_US-lessac-medium.ckpt"
    with pytest.raises(train.TrainError, match="unknown base"):
        train.resolve_base("gosia", bases)


def test_lessac_url_is_escaped():
    assert train.LESSAC_URL.endswith("epoch%3D2164-step%3D1355540.ckpt")
    assert "/en/en_US/lessac/medium/" in train.LESSAC_URL


def test_latest_checkpoint_picks_newest_last(tmp_path):
    assert train.latest_checkpoint(tmp_path) is None
    old = tmp_path / "lightning_logs/version_0/checkpoints/last.ckpt"
    new = tmp_path / "lightning_logs/version_1/checkpoints/last.ckpt"
    for path, mtime in ((old, 1000), (new, 2000)):
        path.parent.mkdir(parents=True)
        path.write_bytes(b"x")
        import os

        os.utime(path, (mtime, mtime))
    (tmp_path / "lightning_logs/version_1/checkpoints/epoch=3-val_mel=0.1.ckpt").write_bytes(b"x")
    assert train.latest_checkpoint(tmp_path) == new


def test_resume_takes_the_newest_checkpoint_of_any_kind(tmp_path):
    import os

    assert train.resume_checkpoint(tmp_path) is None
    folder = tmp_path / "lightning_logs/version_0/checkpoints"
    folder.mkdir(parents=True)
    # the run crashed after epoch 202: last.ckpt is still from epoch 197, a best-val_mos one from 201
    for name, mtime in (
        ("epoch=197-val_mel=0.38.ckpt", 1000),
        ("last.ckpt", 1000),
        ("epoch=201-val_mos=3.5.ckpt", 2000),
    ):
        (folder / name).write_bytes(b"x")
        os.utime(folder / name, (mtime, mtime))
    assert train.resume_checkpoint(tmp_path) == folder / "epoch=201-val_mos=3.5.ckpt"
    assert train.latest_checkpoint(tmp_path) == folder / "last.ckpt"  # export keeps its default


def test_export_and_finish(tmp_path):
    p = paths(tmp_path)
    onnx = tmp_path / "export" / "pl_PL-kuba-medium.onnx"
    cmd = train.export_command(Path("x.ckpt"), onnx, python="py")
    assert cmd == ["py", "-c", train.EXPORT_CODE, "--checkpoint", "x.ckpt", "--output-file", str(onnx)]
    with pytest.raises(train.TrainError, match=r"config\.json"):
        train.finish_export(p, onnx)
    p.work_dir.mkdir(parents=True)
    p.config_json.write_text('{"audio": {"sample_rate": 22050}}')
    onnx.parent.mkdir(parents=True)
    target = train.finish_export(p, onnx)
    assert target.name == "pl_PL-kuba-medium.onnx.json"
    assert json.loads(target.read_text())["audio"] == {"sample_rate": 22050, "quality": "medium"}
    high = train.finish_export(p, onnx.with_name("pl_PL-kuba-high.onnx"), "high")
    assert json.loads(high.read_text())["audio"]["quality"] == "high"


def test_run_raises_on_failure():
    with pytest.raises(train.TrainError, match="exit code 3"):
        train.run([sys.executable, "-c", "raise SystemExit(3)"])
    train.run([sys.executable, "-c", "pass"])


def test_run_limits_gpu_memory_fragmentation(monkeypatch):
    check = "import os; assert os.environ['PYTORCH_CUDA_ALLOC_CONF'] == {!r}"
    monkeypatch.delenv("PYTORCH_CUDA_ALLOC_CONF", raising=False)
    train.run([sys.executable, "-c", check.format("expandable_segments:True")])
    monkeypatch.setenv("PYTORCH_CUDA_ALLOC_CONF", "max_split_size_mb:128")  # the user's own setting wins
    train.run([sys.executable, "-c", check.format("max_split_size_mb:128")])


def test_export_uses_the_exporter_that_handles_vits(tmp_path):
    command = train.export_command(tmp_path / "a.ckpt", tmp_path / "a.onnx", python="py")
    assert command[:2] == ["py", "-c"]
    assert "dynamo=False" in command[2]
    assert command[3:] == [
        "--checkpoint",
        str(tmp_path / "a.ckpt"),
        "--output-file",
        str(tmp_path / "a.onnx"),
    ]


def test_exported_config_names_the_language_for_wyoming_piper(tmp_path):
    p = train.TrainPaths(tmp_path / "dataset", tmp_path / "train")
    p.config_json.parent.mkdir()
    p.config_json.write_text("{}", encoding="utf-8")
    target = train.finish_export(p, tmp_path / "pl_PL-kuba-medium.onnx")
    config = json.loads(target.read_text(encoding="utf-8"))
    assert config["language"] == {"code": "pl_PL", "family": "pl", "region": "PL"}
    assert config["dataset"] == "pl_PL-kuba-medium"
