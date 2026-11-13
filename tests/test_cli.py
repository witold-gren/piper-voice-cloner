from __future__ import annotations

import json

import numpy as np
from typer.testing import CliRunner

from piper_voice_cloner import config
from piper_voice_cloner.cli import app, privacy_warning

from .conftest import requires_ffmpeg, write_mp3_named_wav

runner = CliRunner()


def invoke(tmp_path, *args):
    result = runner.invoke(app, ["--root", str(tmp_path), *args])
    assert result.exit_code == 0, result.output
    return result.output


def test_init_creates_config(tmp_path):
    invoke(tmp_path, "init", "kuba", "--backend", "xtts", "--base", "lessac", "--piper-name", "pl_PL-kuba")
    cfg = config.load(tmp_path / "voices" / "kuba")
    assert (cfg.synthesis.backend, cfg.train.base, cfg.piper_name) == ("xtts", "lessac", "pl_PL-kuba")
    again = runner.invoke(app, ["--root", str(tmp_path), "init", "kuba"])
    assert again.exit_code != 0


def test_init_unknown_language(tmp_path):
    result = runner.invoke(app, ["--root", str(tmp_path), "init", "kuba", "--language", "xx"])
    assert result.exit_code != 0


def test_train_dry_run_for_each_base(tmp_path):
    invoke(tmp_path, "init", "kuba")
    voice = tmp_path / "voices" / "kuba"

    result = runner.invoke(
        app, ["--root", str(tmp_path), "train", "kuba", "--base", "bazowy-pl", "--dry-run"]
    )
    assert result.exit_code != 0
    assert "create the bazowy-pl base first" in str(result.exception)

    own = tmp_path / "epoch=100-step=5.ckpt"
    own.write_bytes(b"x")
    out = invoke(tmp_path, "train", "kuba", "--base", f"ckpt:{own}", "--dry-run")
    assert f"--ckpt_path {own}" in out
    assert "--trainer.max_epochs 1100" in out
    assert not (voice / "train" / "run.json").exists()

    (tmp_path / "bases").mkdir()
    (tmp_path / "bases" / "en_US-lessac-medium.ckpt").write_bytes(b"x")
    # lessac file name has no epoch -> read by the training python; use a fake one
    fake_python = tmp_path / "py"
    fake_python.write_text("#!/bin/sh\necho 2164\n")
    fake_python.chmod(0o755)
    out = invoke(tmp_path, "train", "kuba", "--base", "lessac", "--dry-run", "--python", str(fake_python))
    assert "--trainer.max_epochs 3164" in out


def test_train_requires_dataset(tmp_path):
    invoke(tmp_path, "init", "kuba")
    own = tmp_path / "epoch=1.ckpt"
    own.write_bytes(b"x")
    result = runner.invoke(app, ["--root", str(tmp_path), "train", "kuba", "--base", f"ckpt:{own}"])
    assert result.exit_code != 0
    assert "pvc filter" in result.output


def test_base_train_dry_run_from_random_weights(tmp_path):
    out = invoke(tmp_path, "base", "train", "--dry-run", "--max-epochs", "4000")
    assert "--ckpt_path" not in out
    assert "--trainer.max_epochs 4000" in out
    assert "bases/pl-scratch/dataset/metadata.csv" in out


def test_base_train_high_uses_its_own_folder_and_the_same_recordings(tmp_path):
    out = invoke(tmp_path, "base", "train", "--dry-run", "--quality", "high")
    assert "bases/pl-scratch/dataset/metadata.csv" in out  # one dataset for both sizes
    assert "bases/pl-scratch-high/train" in out and "--model.upsample_initial_channel 512" in out
    assert "--data.batch_size 16" in out
    out = invoke(tmp_path, "base", "train", "--dry-run", "--quality", "high", "--batch-size", "12")
    assert "--data.batch_size 12" in out
    out = invoke(tmp_path, "base", "train", "--dry-run")
    assert "--data.batch_size 32" in out and "upsample_initial_channel" not in out
    result = runner.invoke(app, ["--root", str(tmp_path), "base", "train", "--dry-run", "--quality", "x"])
    assert result.exit_code != 0


def test_resume_keeps_the_model_size_of_the_run(tmp_path):
    work = tmp_path / "bases" / "pl-scratch-high" / "train"
    (work / "lightning_logs" / "version_0" / "checkpoints").mkdir(parents=True)
    (work / "lightning_logs" / "version_0" / "checkpoints" / "last.ckpt").write_bytes(b"x")
    (work / "run.json").write_text(json.dumps({"start_epoch": 0, "base": "random", "quality": "high"}))
    out = invoke(tmp_path, "base", "train", "--dry-run", "--quality", "high")
    assert "Resuming from" in out and "--model.upsample_initial_channel 512" in out


def test_resume_after_a_finished_run_trains_more_epochs(tmp_path, monkeypatch):
    from piper_voice_cloner import train

    work = tmp_path / "bases" / "pl-scratch" / "train"
    checkpoints = work / "lightning_logs" / "version_1" / "checkpoints"
    checkpoints.mkdir(parents=True)
    (checkpoints / "epoch=1273-val_mel=0.3614.ckpt").write_bytes(b"x")
    (work / "run.json").write_text(json.dumps({"start_epoch": 0, "base": "random", "quality": "medium"}))
    dataset = tmp_path / "bases" / "pl-scratch" / "dataset"
    dataset.mkdir(parents=True)
    (dataset / "metadata.csv").write_text("a.wav|Tekst.\n")
    fake_python = tmp_path / "py"
    fake_python.write_text("#!/bin/sh\necho 1273 medium\n")
    fake_python.chmod(0o755)
    calls = []
    monkeypatch.setattr(train, "run", lambda cmd: calls.append(cmd))
    # 1300 epochs are done; Lightning would refuse max_epochs=800 below the checkpoint's epoch 1273
    out = invoke(tmp_path, "base", "train", "--max-epochs", "800", "--python", str(fake_python))
    assert "training 800 more" in out and "training epochs 1273-2073" in out
    assert calls[-1][calls[-1].index("--trainer.max_epochs") + 1] == "2073"
    assert json.loads((work / "run.json").read_text())["start_epoch"] == 1273
    # a stopped, unfinished run still keeps its plan
    out = invoke(tmp_path, "base", "train", "--max-epochs", "1300", "--python", str(fake_python))
    assert "more" not in out and "training epochs 1273-2573" in out


def test_fine_tuning_takes_the_size_of_the_base(tmp_path):
    invoke(tmp_path, "init", "kuba")
    own = tmp_path / "epoch=300-val_mos=3.6.ckpt"
    own.write_bytes(b"x")
    fake_python = tmp_path / "py"
    fake_python.write_text("#!/bin/sh\necho 300 high\n")
    fake_python.chmod(0o755)
    out = invoke(
        tmp_path, "train", "kuba", "--base", f"ckpt:{own}", "--dry-run", "--python", str(fake_python)
    )
    assert "--model.upsample_initial_channel 512" in out and "--trainer.max_epochs 1300" in out


def test_base_score(tmp_path):
    from piper_voice_cloner.dataset import Utterance, write_metadata

    from .test_dataset_quality import fake_scorer

    result = runner.invoke(app, ["--root", str(tmp_path), "base", "score"])
    assert result.exit_code != 0 and "base prepare" in result.output
    folder = tmp_path / "bases" / "pl-scratch" / "dataset"
    write_metadata(folder / "metadata.csv", [Utterance(f"c{i}", "Zdanie.") for i in range(4)])
    python = fake_scorer(tmp_path, {"c0": 3.1, "c1": 3.5, "c2": 3.7, "c3": 4.2})
    out = invoke(tmp_path, "base", "score", "--sample", "0", "--python", python)
    assert "progress base-score 4/4" in out and "median 3.60" in out
    assert (folder / "utmos.json").is_file()


def test_base_select(tmp_path):
    ckpt = tmp_path / "epoch=3000-val_mel=0.2.ckpt"
    ckpt.write_bytes(b"model")
    invoke(tmp_path, "base", "select", str(ckpt))
    assert (tmp_path / "bases" / "pl-scratch.ckpt").read_bytes() == b"model"


def test_export_without_checkpoint(tmp_path):
    invoke(tmp_path, "init", "kuba")
    result = runner.invoke(app, ["--root", str(tmp_path), "export", "kuba"])
    assert result.exit_code != 0


@requires_ffmpeg
def test_import_command(tmp_path):
    invoke(tmp_path, "init", "kasia", "--piper-name", "pl_PL-kasia_glos")
    legacy = tmp_path / "legacy"
    write_mp3_named_wav(legacy / "wav" / "a.wav", 1.2)
    write_mp3_named_wav(legacy / "wav" / "b.wav", 1.2)
    (legacy / "metadata.csv").write_text("a|Kot śpi na ciepłej kanapie.\nb|00:30:00\n", encoding="utf-8")
    out = invoke(tmp_path, "import", "kasia", str(legacy))
    assert "kept 1 of 2" in out
    assert "text:digits: 1" in out
    assert (tmp_path / "voices" / "kasia" / "dataset" / "wav" / "a.wav").is_file()


def test_privacy_warning(tmp_path):
    assert privacy_warning(tmp_path) is None or "voices/" in privacy_warning(tmp_path)
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    assert "not in .gitignore" in privacy_warning(repo)
    (repo / ".gitignore").write_text("voices/\n")
    assert privacy_warning(repo) is None


def test_run_json_written_once(tmp_path, monkeypatch):
    from piper_voice_cloner import cli, train

    invoke(tmp_path, "init", "kuba")
    voice = tmp_path / "voices" / "kuba"
    (voice / "dataset").mkdir()
    (voice / "dataset" / "metadata.csv").write_text("a.wav|Tekst.\n")
    own = tmp_path / "epoch=10.ckpt"
    own.write_bytes(b"x")
    calls = []
    monkeypatch.setattr(train, "run", lambda cmd: calls.append(cmd))
    output = invoke(tmp_path, "train", "kuba", "--base", f"ckpt:{own}")
    assert "training epochs 10-1010" in output  # read by the web UI progress bar
    info = json.loads((voice / "train" / "run.json").read_text())
    assert info["start_epoch"] == 10

    # resume: last.ckpt exists -> continue from it with the original epoch budget
    last = voice / "train" / "lightning_logs" / "version_0" / "checkpoints" / "last.ckpt"
    last.parent.mkdir(parents=True)
    last.write_bytes(b"x")
    invoke(tmp_path, "train", "kuba", "--base", f"ckpt:{own}")
    second = calls[-1]
    assert second[second.index("--ckpt_path") + 1] == str(last)
    assert second[second.index("--trainer.max_epochs") + 1] == "1010"
    assert cli is not None


def test_progress_printer_reports_about_every_percent(capsys):
    from piper_voice_cloner.cli import _progress

    report = _progress("import")
    for done in range(1, 1001):
        report(done, 1000)
    lines = capsys.readouterr().out.splitlines()
    assert lines[-1] == "progress import 1000/1000"
    assert 95 <= len(lines) <= 101
    report = _progress("filter")
    for done in range(1, 4):
        report(done, 3)
    assert capsys.readouterr().out.splitlines() == [f"progress filter {n}/3" for n in (1, 2, 3)]


def test_remote_configure_and_short_command(tmp_path):
    from typer.testing import CliRunner

    from piper_voice_cloner.cli import _short_command, app

    runner = CliRunner()
    result = runner.invoke(app, ["--root", str(tmp_path), "remote", "check"])
    assert result.exit_code != 0 and "no server yet" in result.output
    result = runner.invoke(
        app, ["--root", str(tmp_path), "remote", "configure", "ubuntu.local", "--user", "u"]
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "server.json").is_file()
    result = runner.invoke(app, ["--root", str(tmp_path), "remote", "configure", "bad host"])
    assert result.exit_code != 0
    shown = _short_command(["ssh", "-p", "22", "-o", "BatchMode=yes", "u@h", "x" * 200])
    assert shown.startswith("ssh u@h ") and "BatchMode" not in shown and len(shown) < 140


def test_init_picks_bazowy_pl_only_once_it_exists(tmp_path):
    from piper_voice_cloner import train

    invoke(tmp_path, "init", "kuba")
    assert config.load(tmp_path / "voices" / "kuba").train.base == "lessac"
    (tmp_path / "bases").mkdir()
    (tmp_path / "bases" / train.SCRATCH_BASE).write_bytes(b"x")
    invoke(tmp_path, "init", "ola")
    assert config.load(tmp_path / "voices" / "ola").train.base == "bazowy-pl"


def test_prepare_while_training_sends_code_and_restarts_only_the_ui(tmp_path, monkeypatch):
    import subprocess

    from piper_voice_cloner import remote

    remote.save_config(tmp_path, remote.ServerConfig(host="gpu.lan", user="tomek"))
    status = {
        "gpu": "RTX 4090, 24564, 580", "tools": dict.fromkeys(remote.SETUP_TOOLS, True), "uv": True,
        "free_gb": 900, "stamp": "old", "venv": True, "train": "cuda", "voices": {}, "service": "active",
        "ui": True, "tensorboard": 6006,
    }  # fmt: skip
    ran = []

    def fake_run(command, **kwargs):
        script = command[-1]
        ran.append(script)
        if "PVC-STATUS" in script:
            out = "PVC-STATUS " + json.dumps(status)
        elif "current.json" in script:
            out = json.dumps({"running": True, "kind": "base-train", "voice": ""})
        else:
            out = ""
        return subprocess.CompletedProcess(command, 0, stdout=out, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    output = invoke(tmp_path, "remote", "prepare")
    assert "a job is running on the machine: base-train" in output
    assert any(script == "systemctl --user restart piper-voice-cloner" for script in ran)
    assert not any("setup.sh" in script for script in ran)  # the environments stay as they are
    assert any(script.endswith("pvc/repo/") or "repo/" in script for script in ran)  # the code went over


def test_samples_zip_of_the_base_and_of_a_voice(tmp_path):
    from tests.test_train_monitor import validation, write

    result = runner.invoke(app, ["--root", str(tmp_path), "base", "samples"])
    assert result.exit_code != 0 and "no training samples" in result.output
    events = (
        tmp_path / "bases" / "pl-scratch" / "train" / "lightning_logs" / "version_0" / "events.out.tfevents.1"
    )
    for epoch in range(3):
        write(events, *validation(100 * (epoch + 1), epoch, 3.0))
    out = invoke(tmp_path, "base", "samples")
    assert "samples.zip" in out and "index.html" in out

    invoke(tmp_path, "init", "kuba")
    events = tmp_path / "voices" / "kuba" / "train" / "lightning_logs" / "version_0" / "events.out.tfevents.1"
    write(events, *validation(100, 0, 3.0))
    zip_path = tmp_path / "kuba.zip"
    invoke(tmp_path, "samples", "kuba", "--out", str(zip_path))
    assert zip_path.is_file()


def elevenlabs_voice(root, name="alicja"):
    invoke(root, "init", name, "--backend", "elevenlabs", "--base", "lessac")
    dataset = root / "voices" / "marek" / "dataset"
    dataset.mkdir(parents=True)
    lines = "".join(f"{n}.wav|Zdanie numer {n}.\n" for n in range(10))
    (dataset / "metadata.csv").write_text(lines, encoding="utf-8")
    invoke(root, "sentences", name, "marek")


class ElevenLabsAccount:
    def __init__(self, monkeypatch):
        from piper_voice_cloner.backends import elevenlabs

        voices = [{"id": "o", "name": "Alicja Lektorka", "category": "cloned"}]
        monkeypatch.setattr(elevenlabs, "list_voices", lambda: voices)
        monkeypatch.setattr(elevenlabs, "optional_credits", lambda: elevenlabs.Credits(10, 100, 0))


def test_elevenlabs_voices_and_pick(tmp_path, monkeypatch):
    ElevenLabsAccount(monkeypatch)
    invoke(tmp_path, "init", "alicja", "--base", "lessac")
    output = invoke(tmp_path, "elevenlabs", "voices")
    assert "Alicja Lektorka" in output and "Credits left: 90 of 100" in output
    invoke(tmp_path, "elevenlabs", "pick", "alicja", "o")
    synth = config.load(tmp_path / "voices" / "alicja").synthesis
    assert (synth.backend, synth.elevenlabs_voice_id, synth.elevenlabs_voice_name) == (
        "elevenlabs",
        "o",
        "Alicja Lektorka",
    )
    unknown = runner.invoke(app, ["--root", str(tmp_path), "elevenlabs", "pick", "alicja", "x"])
    assert unknown.exit_code != 0


def test_synthesize_elevenlabs_needs_no_recording(tmp_path, monkeypatch):
    from piper_voice_cloner import backends
    from piper_voice_cloner.synthesis import read_manifest

    class Fake:
        name, remote, source = "elevenlabs", True, "elevenlabs:o"

        def synthesize(self, text, reference, seed):
            return np.zeros(2400, dtype=np.float32), 24000

    elevenlabs_voice(tmp_path)
    monkeypatch.setattr(backends, "create", lambda *args, **kwargs: Fake())
    output = invoke(tmp_path, "synthesize", "alicja", "--limit", "1")
    assert "Generated 1 new clips" in output
    invoke(tmp_path, "synthesize", "alicja")
    manifest = read_manifest(tmp_path / "voices" / "alicja" / "raw")
    assert len(manifest) == 10
    assert {row["backend"] for row in manifest.values()} == {"elevenlabs:o"}


def test_synthesize_says_why_it_stopped(tmp_path):
    elevenlabs_voice(tmp_path)
    result = runner.invoke(app, ["--root", str(tmp_path), "synthesize", "alicja"])
    assert result.exit_code == 1
    assert "Stopped: no API key" in result.output


def test_base_export_writes_a_voice_from_the_chosen_base(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from piper_voice_cloner import train

    monkeypatch.setattr(train, "checkpoint_info", lambda path, python: SimpleNamespace(quality="medium"))
    monkeypatch.setattr(train, "run", lambda cmd: None)
    bases = tmp_path / "bases"
    paths = train.TrainPaths(train.base_dataset(bases), train.base_folder(bases) / "train")
    paths.config_json.parent.mkdir(parents=True)
    paths.config_json.write_text('{"audio": {"sample_rate": 22050}}', encoding="utf-8")
    (bases / train.SCRATCH_BASE).write_bytes(b"x")
    output = invoke(tmp_path, "base", "export", "--name", "pl_PL-kasia_bazowy")
    target = bases / "export" / "pl_PL-kasia_bazowy-medium.onnx.json"
    assert "pl_PL-kasia_bazowy-medium.onnx" in output
    assert json.loads(target.read_text(encoding="utf-8"))["audio"]["quality"] == "medium"


def test_base_export_needs_a_checkpoint(tmp_path):
    result = runner.invoke(app, ["--root", str(tmp_path), "base", "export"])
    assert result.exit_code != 0


def test_train_queue_keeps_order_and_survives_a_failed_voice(tmp_path, monkeypatch):
    from piper_voice_cloner import cli, train

    trained = []

    def fake_train(name, paths, lang, train_cfg, ckpt, python, **_kw):
        trained.append((name, train_cfg.max_epochs, train_cfg.base))
        if name == "bad":
            raise train.TrainError("command failed with exit code 1")

    monkeypatch.setattr(cli, "_train", fake_train)
    monkeypatch.setattr(train, "resolve_base", lambda *args, **kwargs: None)
    for name in ("opt", "bad", "piotr"):
        invoke(tmp_path, "init", name, "--base", "lessac")
    result = runner.invoke(
        app,
        [
            "--root",
            str(tmp_path),
            "train-queue",
            "opt",
            "bad",
            "gone",
            "piotr",
            "--epochs",
            "500",
            "--base",
            "bazowy-pl",
        ],
    )
    assert result.exit_code == 1
    assert trained == [("opt", 500, "bazowy-pl"), ("bad", 500, "bazowy-pl"), ("piotr", 500, "bazowy-pl")]
    assert "queue 4/4: piotr" in result.output
    assert "queue finished: 2 of 4 voices trained" in result.output
    assert config.load(tmp_path / "voices" / "piotr").train.max_epochs == 500
    assert json.loads((tmp_path / "jobs" / "train_queue.json").read_text(encoding="utf-8")) == {
        "voice": "piotr"
    }


def test_train_queue_ctrl_c_stops_the_rest(tmp_path, monkeypatch):
    from piper_voice_cloner import cli, train

    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "_train", interrupted)
    monkeypatch.setattr(train, "resolve_base", lambda *args, **kwargs: None)
    invoke(tmp_path, "init", "opt", "--base", "lessac")
    result = runner.invoke(app, ["--root", str(tmp_path), "train-queue", "opt", "next"])
    assert result.exit_code != 0
    assert "queue 2/2" not in result.output
