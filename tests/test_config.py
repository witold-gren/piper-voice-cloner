from __future__ import annotations

from pydantic import ValidationError
import pytest

from piper_voice_cloner import config


def test_defaults_roundtrip(tmp_path):
    cfg = config.VoiceConfig(name="kuba_bajka")
    config.save(tmp_path, cfg)
    loaded = config.load(tmp_path)
    assert loaded == cfg
    assert loaded.synthesis.backend == "chatterbox"
    assert loaded.train.base == "bazowy-pl"
    assert loaded.target_clips == 2000


def test_file_stem():
    assert config.VoiceConfig(name="kuba").file_stem("pl_PL") == "pl_PL-kuba-medium"
    cfg = config.VoiceConfig(name="kasia", piper_name="pl_PL-kasia_glos")
    assert cfg.file_stem("pl_PL") == "pl_PL-kasia_glos-medium"


@pytest.mark.parametrize("name", ["Kuba", "kuba-bajka", "", "_x", "żaba"])
def test_invalid_voice_name(name):
    with pytest.raises(ValidationError):
        config.VoiceConfig(name=name)


@pytest.mark.parametrize("base", ["bazowy-pl", "lessac", "ckpt:/x/y.ckpt"])
def test_valid_bases(base):
    assert config.TrainConfig(base=base).base == base


@pytest.mark.parametrize("base", ["gosia", "ckpt:", "scratch"])
def test_invalid_bases(base):
    with pytest.raises(ValidationError):
        config.TrainConfig(base=base)


def test_unknown_keys_rejected(tmp_path):
    (tmp_path / config.CONFIG_FILE).write_text("name: kuba\nsynthesis:\n  bakend: xtts\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        config.load(tmp_path)


def test_missing_config(tmp_path):
    with pytest.raises(FileNotFoundError, match="pvc init"):
        config.load(tmp_path)


def test_old_base_name_still_read():
    """voice.yaml files from before the rename keep working."""
    assert config.TrainConfig(base="scratch-pl").base == "bazowy-pl"
    with pytest.raises(ValueError, match="bazowy-pl"):
        config.TrainConfig(base="scratch")
