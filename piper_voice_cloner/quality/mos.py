"""Naturalness score with UTMOS22 (tarepan/SpeechMOS) - the predictor piper1-gpl logs as val_mos."""

from __future__ import annotations

import numpy as np

from ..backends.base import pick_device

UTMOS_REPO = "tarepan/SpeechMOS:v1.2.0"
UTMOS_MODEL = "utmos22_strong"


class MosPredictor:
    def __init__(self, device: str | None = None) -> None:
        import torch  # heavy import, quality environment only

        self._torch = torch
        self.device = pick_device(device)
        self.model = torch.hub.load(UTMOS_REPO, UTMOS_MODEL, trust_repo=True).to(self.device).eval()

    def score(self, audio_16k: np.ndarray) -> float:
        with self._torch.no_grad():
            wave = self._torch.from_numpy(audio_16k.astype(np.float32)).unsqueeze(0).to(self.device)
            return float(self.model(wave, 16000).item())


def drop_threshold(scores: list[float], fraction: float) -> float:
    """Score below which the worst `fraction` of clips are dropped (0 = keep everything)."""
    if not scores or fraction <= 0:
        return float("-inf")
    return float(np.quantile(np.asarray(scores), fraction))
