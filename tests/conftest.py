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
    """No test ever powers a computer off: switching the machine off through Home Assistant is
    replaced by a list of calls (a CI runner once really powered off). Returns that list."""
    from piper_voice_cloner import power

    calls: list[str] = []
    monkeypatch.setattr(power, "power_off", lambda: calls.append("power_off") or "switch.test")
    return calls


LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "testserver"}


class OutsideNetwork(RuntimeError):
    """A test tried to reach a computer other than this one (a real Home Assistant would ban us)."""


def _local(url: str) -> bool:
    from urllib.parse import urlsplit

    return (urlsplit(url).hostname or "") in LOCAL_HOSTS


@pytest.fixture(autouse=True)
def no_outside_network(monkeypatch):
    """Tests never leave 127.0.0.1: urllib and requests refuse any other address."""
    from urllib import request as urllib_request

    real_urlopen = urllib_request.urlopen

    def urlopen(url, *args, **kwargs):
        target = url if isinstance(url, str) else url.full_url
        if not _local(target):
            raise OutsideNetwork(target)
        return real_urlopen(url, *args, **kwargs)

    monkeypatch.setattr(urllib_request, "urlopen", urlopen)
    try:
        import requests
    except ImportError:
        return
    real_request = requests.Session.request

    def session_request(self, method, url, *args, **kwargs):
        if not _local(url):
            raise OutsideNetwork(url)
        return real_request(self, method, url, *args, **kwargs)

    monkeypatch.setattr(requests.Session, "request", session_request)
