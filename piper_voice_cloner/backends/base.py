"""Common interface of cloning backends."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import numpy as np


class FatalSynthesisError(RuntimeError):
    """No later sentence can succeed either (wrong key, no credits): the whole run stops."""


class Synthesizer(Protocol):
    name: str
    # True when audio (and the reference) leave this machine
    remote: bool

    def synthesize(self, text: str, reference: Path, seed: int) -> tuple[np.ndarray, int]:
        """Mono float32 audio and its sample rate for `text` spoken in the reference voice."""
        ...


def pick_device(requested: str | None = None, *, allow_mps: bool = True) -> str:
    """The device asked for, else the NVIDIA GPU, else the Apple GPU (mps, macOS), else the CPU."""
    if requested:
        return requested
    import torch

    if torch.cuda.is_available():
        return "cuda"
    mps = getattr(torch.backends, "mps", None)
    if allow_mps and mps is not None and mps.is_available():
        return "mps"
    return "cpu"


def seed_everything(seed: int) -> None:
    import random

    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch
    except ImportError:
        return
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        torch.mps.manual_seed(seed)
