"""Audio helpers built on ffmpeg (decoding any format, resampling, loudness) and numpy."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import numpy as np
import soundfile as sf

PIPER_RATE = 22050
EMBED_RATE = 16000
LOUDNESS_LUFS = -23.0
TRUE_PEAK_DB = -1.0


class AudioError(RuntimeError):
    pass


def ffmpeg_binary() -> str:
    binary = shutil.which("ffmpeg")
    if not binary:
        raise AudioError("ffmpeg not found - install it (apt install ffmpeg / brew install ffmpeg)")
    return binary


def load(path: Path, rate: int, *, loudnorm: bool = False) -> np.ndarray:
    """Decode any file ffmpeg understands (wav, mp3 posing as wav, m4a...) to mono float32."""
    filters = [f"loudnorm=I={LOUDNESS_LUFS}:TP={TRUE_PEAK_DB}:LRA=11"] if loudnorm else []
    cmd = [ffmpeg_binary(), "-v", "error", "-nostdin", "-i", str(path), "-ac", "1"]
    if filters:
        cmd += ["-af", ",".join(filters)]
    cmd += ["-ar", str(rate), "-f", "f32le", "-"]
    result = subprocess.run(cmd, capture_output=True, check=False)
    if result.returncode != 0:
        raise AudioError(f"ffmpeg failed for {path}: {result.stderr.decode(errors='replace').strip()}")
    return np.frombuffer(result.stdout, dtype=np.float32).copy()


def trim(audio: np.ndarray, rate: int, *, threshold_db: float = -40.0, pad: float = 0.15) -> np.ndarray:
    """Cut leading/trailing silence (frames below threshold relative to the peak), keep padding."""
    if audio.size == 0:
        return audio
    frame = max(1, int(rate * 0.01))
    usable = audio[: len(audio) // frame * frame]
    if usable.size == 0:
        return audio
    rms = np.sqrt(np.mean(usable.reshape(-1, frame) ** 2, axis=1) + 1e-12)
    peak = rms.max()
    if peak <= 1e-6:
        return audio[:0]
    loud = np.flatnonzero(20 * np.log10(rms / peak) > threshold_db)
    keep = int(rate * pad)
    start = max(0, loud[0] * frame - keep)
    end = min(len(audio), (loud[-1] + 1) * frame + keep)
    return audio[start:end]


def normalize_level(audio: np.ndarray, rate: int, target_db: float = LOUDNESS_LUFS) -> np.ndarray:
    """Gain so the speech (frames above -40 dB of the peak) sits at target_db RMS, peak-limited.

    A static gain per clip: ffmpeg's single-pass loudnorm is dynamic on short clips and pumps.
    """
    frame = max(1, int(rate * 0.02))
    usable = audio[: len(audio) // frame * frame]
    if usable.size == 0:
        return audio
    rms = np.sqrt(np.mean(usable.reshape(-1, frame) ** 2, axis=1) + 1e-12)
    voiced = rms[20 * np.log10(rms / rms.max()) > -40.0]
    level = float(np.sqrt(np.mean(voiced**2)))
    if level <= 1e-6:
        return audio
    gain = 10 ** (target_db / 20) / level
    return peak_limit(audio * gain)


def peak_limit(audio: np.ndarray, peak_db: float = TRUE_PEAK_DB) -> np.ndarray:
    limit = 10 ** (peak_db / 20)
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    return audio * (limit / peak) if peak > limit else audio


def save_wav(path: Path, audio: np.ndarray, rate: int = PIPER_RATE) -> None:
    """Real PCM WAV, 16-bit mono - what Piper training expects."""
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, np.clip(audio, -1.0, 1.0), rate, subtype="PCM_16", format="WAV")


def resample(audio: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    """Resample through ffmpeg (soxr quality) without touching disk."""
    if src_rate == dst_rate:
        return audio.astype(np.float32)
    cmd = [
        ffmpeg_binary(),
        "-v",
        "error",
        "-nostdin",
        "-f",
        "f32le",
        "-ar",
        str(src_rate),
        "-ac",
        "1",
        "-i",
        "-",
        "-ar",
        str(dst_rate),
        "-f",
        "f32le",
        "-",
    ]
    result = subprocess.run(cmd, input=audio.astype(np.float32).tobytes(), capture_output=True, check=False)
    if result.returncode != 0:
        raise AudioError(result.stderr.decode(errors="replace").strip())
    return np.frombuffer(result.stdout, dtype=np.float32).copy()


def duration(audio: np.ndarray, rate: int) -> float:
    return len(audio) / rate if rate else 0.0
