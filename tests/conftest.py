from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import numpy as np
import pytest

from piper_voice_cloner.audio import save_wav
from piper_voice_cloner.languages import get_language

requires_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


@pytest.fixture
def pl():
    return get_language("pl")


def tone(seconds: float, rate: int, *, freq: float = 220.0, level: float = 0.3, silence: float = 0.0):
    """Sine 'speech' with optional silence around it."""
    t = np.arange(int(seconds * rate)) / rate
    wave = (level * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    pad = np.zeros(int(silence * rate), dtype=np.float32)
    return np.concatenate([pad, wave, pad])


def write_tone(path: Path, seconds: float, rate: int = 24000, **kwargs) -> Path:
    save_wav(path, tone(seconds, rate, **kwargs), rate)
    return path


def write_mp3_named_wav(path: Path, seconds: float) -> Path:
    """An MP3 file with a .wav name - what the old ElevenLabs datasets contain."""
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=300:duration={seconds}",
            "-ar",
            "44100",
            "-ac",
            "1",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "128k",
            "-f",
            "mp3",
            str(path),
        ],
        check=True,
    )
    return path


@pytest.fixture(autouse=True)
def ha_config(tmp_path, monkeypatch):
    """Never the real ~/.config/piper-voice-cloner/home_assistant.json nor PVC_HA_* of the shell."""
    from piper_voice_cloner import ha

    path = tmp_path / "ha-config" / "home_assistant.json"
    monkeypatch.setattr(ha, "CONFIG_FILE", path)
    for name in ("PVC_HA_URL", "PVC_HA_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    return path


@pytest.fixture(autouse=True)
def isolated_elevenlabs_key(tmp_path, monkeypatch):
    """A key saved on the developer's computer must not leak into the tests."""
    monkeypatch.setattr("piper_voice_cloner.backends.elevenlabs.CONFIG_FILE", tmp_path / "elevenlabs.json")
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)


@pytest.fixture(autouse=True)
def no_real_poweroff(monkeypatch):
    """Jobs started by the tests must never power the computer off (CI runners have sudo)."""
    from piper_voice_cloner.webui import runner

    monkeypatch.setenv(runner.POWEROFF_ENV, "true")
