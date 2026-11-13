"""UTMOS scores of WAV files, run by the training Python (it has torch and torchaudio).

    python -I score_clips.py <list.txt> <scores.json>

The list holds one WAV path per line; the result maps each path to its score (about 1-5). UTMOS22
(tarepan/SpeechMOS) is the predictor piper1-gpl logs as val_mos, so the scores of the recordings are
directly comparable with the quality of the trained model. The file imports nothing from the package:
the training environment does not have it installed.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import wave

import numpy as np
import torch

UTMOS_REPO = "tarepan/SpeechMOS:v1.2.0"
UTMOS_MODEL = "utmos22_strong"
REPORT_EVERY = 10
MIN_FREE_GPU = 2 * 1024**3  # bytes; a training run may hold almost all of the card


def pick_device() -> str:
    """The GPU when it has room, else the CPU (slower, but never takes memory from a training run)."""
    if not torch.cuda.is_available():
        return "cpu"
    free, _total = torch.cuda.mem_get_info()
    return "cuda" if free >= MIN_FREE_GPU else "cpu"


def read_wav(path: str) -> tuple[np.ndarray, int]:
    """16-bit PCM WAV (what the dataset writer produces) as mono float32 in -1..1."""
    with wave.open(path, "rb") as handle:
        rate, channels = handle.getframerate(), handle.getnchannels()
        if handle.getsampwidth() != 2:
            raise ValueError(f"{path}: only 16-bit PCM is supported")
        frames = np.frombuffer(handle.readframes(handle.getnframes()), dtype="<i2")
    audio = frames.astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    return audio, rate


def main(list_file: str, out_file: str) -> None:
    files = [line for line in Path(list_file).read_text(encoding="utf-8").splitlines() if line]
    device = pick_device()
    print(f"UTMOS on {device}", flush=True)
    model = torch.hub.load(UTMOS_REPO, UTMOS_MODEL, trust_repo=True).to(device).eval()
    scores: dict[str, float] = {}
    for done, path in enumerate(files, 1):
        audio, rate = read_wav(path)
        with torch.inference_mode():
            wave_in = torch.from_numpy(audio).unsqueeze(0).to(device)
            scores[path] = round(float(model(wave_in, rate).item()), 4)
        if done % REPORT_EVERY == 0 or done == len(files):
            print(f"scored {done}/{len(files)}", flush=True)
    Path(out_file).write_text(json.dumps(scores), encoding="utf-8")


if __name__ == "__main__":
    main(*sys.argv[1:3])
