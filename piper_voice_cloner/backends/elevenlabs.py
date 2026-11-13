"""ElevenLabs (cloud). Text leaves the house; the voice must already exist in your account.

API key: ``ELEVENLABS_API_KEY`` or ``~/.config/piper-voice-cloner/elevenlabs.json`` (mode 600, saved
from the panel). Outside the data folder on purpose: that folder is copied to the GPU machine and
into backups. ``PVC_ELEVENLABS_CONFIG`` points at another file (tests, a second setup).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
import os
from pathlib import Path
import time
from typing import Any

import numpy as np

from .base import FatalSynthesisError

BASE_URL = "https://api.elevenlabs.io/v1"
API = BASE_URL + "/text-to-speech/{voice_id}"
RATE = 24000
DEFAULTS = {
    "model_id": "eleven_multilingual_v2",
    "stability": 0.5,
    "similarity_boost": 0.75,
    "style": 0.0,
    "use_speaker_boost": True,
}
CONFIG_FILE = Path(
    os.environ.get("PVC_ELEVENLABS_CONFIG")
    or Path.home() / ".config" / "piper-voice-cloner" / "elevenlabs.json"
)
# wrong key, no credits, no such voice: the next sentence would fail the same way
FATAL_STATUS = {401, 402, 403, 404}
# too many requests, service hiccups: worth another try
RETRY_STATUS = {429, 500, 502, 503, 504}
RETRIES = 5
# made in this account; "professional" and "premade" come from the public voice library
OWN_CATEGORIES = {"cloned", "generated"}


class ElevenLabsError(RuntimeError):
    pass


class ElevenLabsFatalError(ElevenLabsError, FatalSynthesisError):
    pass


@dataclass(frozen=True)
class Credits:
    used: int
    limit: int
    reset: int  # unix time of the next credit reset, 0 = unknown

    @property
    def left(self) -> int:
        return max(0, self.limit - self.used)


def load_api_key() -> str:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if key:
        return key
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8")).get("api_key", "")
    except (OSError, ValueError):
        return ""


def save_api_key(key: str) -> None:
    """Stored readable by this user only; an empty key removes the file."""
    key = key.strip()
    if not key:
        CONFIG_FILE.unlink(missing_ok=True)
        return
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(CONFIG_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump({"api_key": key}, handle)
    CONFIG_FILE.chmod(0o600)


def _get(path: str, session: Any, api_key: str | None) -> dict:
    key = api_key or load_api_key()
    if not key:
        raise ElevenLabsError("no API key: save it in the panel or set ELEVENLABS_API_KEY")
    if session is None:
        import requests

        session = requests.Session()
    response = session.get(f"{BASE_URL}{path}", headers={"xi-api-key": key}, timeout=30)
    if response.status_code != 200:
        raise ElevenLabsError(f"HTTP {response.status_code}: {response.text[:200]}")
    return response.json()


def list_voices(session: Any = None, api_key: str | None = None) -> list[dict]:
    """Voices of the account as {"id", "name", "category"}: own ones first, the voice library last."""
    voices = [
        {"id": v["voice_id"], "name": v["name"], "category": v.get("category", "")}
        for v in _get("/voices", session, api_key)["voices"]
    ]
    return sorted(voices, key=lambda v: (v["category"] not in OWN_CATEGORIES, v["name"].lower()))


def read_credits(session: Any = None, api_key: str | None = None) -> Credits:
    data = _get("/user/subscription", session, api_key)
    return Credits(
        data["character_count"], data["character_limit"], data.get("next_character_count_reset_unix") or 0
    )


def optional_credits(session: Any = None, api_key: str | None = None) -> Credits | None:
    """None when the key may not read the account (no user_read): generating does not need it."""
    try:
        return read_credits(session, api_key)
    except ElevenLabsError:
        return None


class ElevenLabsSynthesizer:
    name = "elevenlabs"
    remote = True

    def __init__(
        self,
        language: str,
        options: dict[str, Any],
        *,
        voice_id: str | None = None,
        session: Any = None,
        api_key: str | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        unknown = set(options) - set(DEFAULTS)
        if unknown:
            raise ValueError(f"unknown elevenlabs options: {sorted(unknown)}")
        self.api_key = api_key or load_api_key()
        if not self.api_key:
            raise ElevenLabsFatalError("no API key: save it in the panel or set ELEVENLABS_API_KEY")
        if not voice_id:
            raise ElevenLabsFatalError("synthesis.elevenlabs_voice_id is not set in voice.yaml")
        if session is None:
            import requests

            session = requests.Session()
        self.session = session
        self.sleep = sleep
        self.language = language
        self.voice_id = voice_id
        # clips of two ElevenLabs voices must not end up in one dataset
        self.source = f"{self.name}:{voice_id}"
        self.options = {**DEFAULTS, **options}

    def _post(self, text: str, seed: int) -> Any:
        settings = {
            k: self.options[k] for k in ("stability", "similarity_boost", "style", "use_speaker_boost")
        }
        return self.session.post(
            API.format(voice_id=self.voice_id),
            params={"output_format": f"pcm_{RATE}"},
            headers={"xi-api-key": self.api_key, "accept": "audio/pcm"},
            json={
                "text": text,
                "model_id": self.options["model_id"],
                # no language_code: eleven_multilingual_v2 detects the language from the text
                "seed": seed,
                "voice_settings": settings,
            },
            timeout=120,
        )

    def synthesize(self, text: str, reference: Path, seed: int) -> tuple[np.ndarray, int]:
        # the reference is not uploaded: the cloned voice lives in the ElevenLabs account
        for attempt in range(RETRIES + 1):
            try:
                response = self._post(text, seed)
            except OSError as err:  # requests' connection errors are OSErrors
                failure = f"connection failed: {type(err).__name__}"
            else:
                if response.status_code == 200:
                    pcm = np.frombuffer(response.content, dtype="<i2").astype(np.float32) / 32768.0
                    return pcm, RATE
                failure = f"HTTP {response.status_code}: {response.text[:200]}"
                if response.status_code in FATAL_STATUS:
                    raise ElevenLabsFatalError(failure)
                if response.status_code not in RETRY_STATUS:
                    raise ElevenLabsError(failure)
            if attempt < RETRIES:
                self.sleep(2**attempt)
        # the service is down or the connection is gone: skipping sentences would only waste hours
        raise ElevenLabsFatalError(f"gave up after {RETRIES} retries, run again later: {failure}")
