"""Character error rate between the requested text and what Whisper hears."""

from __future__ import annotations

import numpy as np

from ..languages import LanguagePack


def edit_distance(a: str, b: str) -> int:
    """Levenshtein distance (characters)."""
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, 1):
        current = [i]
        for j, char_b in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (char_a != char_b)))
        previous = current
    return previous[-1]


def cer(expected: str, heard: str, lang: LanguagePack) -> float:
    reference = lang.normalize_for_cer(expected)
    hypothesis = lang.normalize_for_cer(heard)
    if not reference:
        return 0.0 if not hypothesis else 1.0
    return edit_distance(reference, hypothesis) / len(reference)


def compute_type(device: str, cuda_devices: int) -> str:
    """float16 on an NVIDIA GPU, int8 on the CPU (CTranslate2 cannot use the Apple GPU; float16 on
    a CPU fails)."""
    on_gpu = device == "cuda" or (device == "auto" and cuda_devices > 0)
    return "float16" if on_gpu else "int8"


class WhisperChecker:
    """faster-whisper model kept in memory; `__call__(audio_16k, text) -> CER`."""

    def __init__(self, lang: LanguagePack, model: str = "large-v3", device: str = "auto") -> None:
        import ctranslate2
        from faster_whisper import WhisperModel  # heavy import, quality environment only

        self.lang = lang
        compute = compute_type(device, ctranslate2.get_cuda_device_count())
        self.model = WhisperModel(model, device=device, compute_type=compute)

    def transcribe(self, audio_16k: np.ndarray) -> str:
        segments, _info = self.model.transcribe(
            audio_16k.astype(np.float32),
            language=self.lang.synth_language,
            beam_size=5,
            condition_on_previous_text=False,
            vad_filter=False,
        )
        return " ".join(segment.text.strip() for segment in segments)

    def __call__(self, audio_16k: np.ndarray, text: str) -> float:
        return cer(text, self.transcribe(audio_16k), self.lang)
