"""Chatterbox Multilingual (Resemble AI, MIT): zero-shot cloning from ~10 s, Polish supported.

Outputs carry Resemble's inaudible Perth watermark.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from .base import pick_device, seed_everything

DEFAULTS = {
    "exaggeration": 0.5,
    "cfg_weight": 0.3,
    "temperature": 0.8,
    "repetition_penalty": 1.2,
    "min_p": 0.05,
    "top_p": 1.0,
}


def relax_repetition_check(analyzer_class: type) -> None:
    """Let two equal speech tokens end a clip only after the whole text is spoken.

    chatterbox-tts 0.1.7 forces the end of speech as soon as two equal speech tokens follow each
    other, anywhere in the clip; low, drawn-out voices hit it all the time and most clips stop
    after a few words. The check stays for the tail after the text, where it catches loops.
    """
    if getattr(analyzer_class, "_pvc_relaxed", False):
        return
    step = analyzer_class.step

    def relaxed_step(self, logits, next_token=None):
        if not self.complete:
            self.generated_tokens = []
        return step(self, logits, next_token)

    analyzer_class.step = relaxed_step
    analyzer_class._pvc_relaxed = True


class ChatterboxSynthesizer:
    name = "chatterbox"
    remote = False

    def __init__(self, language: str, options: dict[str, Any]) -> None:
        from chatterbox.models.t3.inference.alignment_stream_analyzer import AlignmentStreamAnalyzer
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS

        unknown = set(options) - {*DEFAULTS, "device"}
        if unknown:
            raise ValueError(f"unknown chatterbox options: {sorted(unknown)}")
        # mps: the model loads its weights on the CPU and moves them to the Apple GPU itself
        self.device = pick_device(options.get("device"))
        self.language = language
        self.options = {**DEFAULTS, **{k: v for k, v in options.items() if k != "device"}}
        relax_repetition_check(AlignmentStreamAnalyzer)
        self.model = ChatterboxMultilingualTTS.from_pretrained(device=self.device)

    def synthesize(self, text: str, reference: Path, seed: int) -> tuple[np.ndarray, int]:
        seed_everything(seed)
        wav = self.model.generate(
            text,
            language_id=self.language,
            audio_prompt_path=str(reference),
            **self.options,
        )
        return wav.squeeze().detach().cpu().numpy().astype(np.float32), int(self.model.sr)
