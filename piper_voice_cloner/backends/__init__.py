"""Voice cloning backends. Heavy libraries are imported only when a backend is created."""

from __future__ import annotations

from typing import Any

from .base import Synthesizer


def create(name: str, language: str, options: dict[str, Any], **kwargs: Any) -> Synthesizer:
    if name == "chatterbox":
        from .chatterbox import ChatterboxSynthesizer

        return ChatterboxSynthesizer(language, options)
    if name == "xtts":
        from .xtts import XttsSynthesizer

        return XttsSynthesizer(language, options)
    if name == "elevenlabs":
        from .elevenlabs import ElevenLabsSynthesizer

        return ElevenLabsSynthesizer(language, options, **kwargs)
    raise ValueError(f"unknown backend '{name}'")
