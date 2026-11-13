"""Coqui XTTS-v2 through the Idiap fork (`coqui-tts`). Model license CPML: non-commercial."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from .base import pick_device, seed_everything

MODEL = "tts_models/multilingual/multi-dataset/xtts_v2"
RATE = 24000
DEFAULTS = {"temperature": 0.65, "repetition_penalty": 5.0, "speed": 1.0}


class XttsSynthesizer:
    name = "xtts"
    remote = False

    def __init__(self, language: str, options: dict[str, Any]) -> None:
        from TTS.api import TTS

        unknown = set(options) - {*DEFAULTS, "device"}
        if unknown:
            raise ValueError(f"unknown xtts options: {sorted(unknown)}")
        # not tried on the Apple GPU: the CPU there unless "device" says otherwise
        self.device = pick_device(options.get("device"), allow_mps=False)
        self.language = language
        self.options = {**DEFAULTS, **{k: v for k, v in options.items() if k != "device"}}
        self.model = TTS(MODEL).to(self.device)

    def synthesize(self, text: str, reference: Path, seed: int) -> tuple[np.ndarray, int]:
        seed_everything(seed)
        wav = self.model.tts(text=text, speaker_wav=str(reference), language=self.language, **self.options)
        return np.asarray(wav, dtype=np.float32), RATE
