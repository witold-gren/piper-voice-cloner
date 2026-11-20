"""Write TensorBoard event files the way piper's training does (only what train_monitor reads).

For the demo: a made-up training with quality, mel errors and test sentences per epoch.
"""

from __future__ import annotations

import io
import math
from pathlib import Path
import struct
import wave


def _varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        out.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(out)


def _field(number: int, wire: int, payload: bytes | int) -> bytes:
    key = _varint(number << 3 | wire)
    if wire == 0:
        return key + _varint(payload)
    if wire == 2:
        return key + _varint(len(payload)) + payload
    return key + payload


def tone(seconds: float = 1.0, freq: float = 220.0) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(22050)
        frames = bytearray()
        count = int(22050 * seconds)
        for i in range(count):
            fade = math.sin(math.pi * i / count)
            frames += struct.pack("<h", int(6000 * fade * math.sin(2 * math.pi * freq * i / 22050)))
        out.writeframes(bytes(frames))
    return buffer.getvalue()


def event(step: int, scalars=(), audio=(), tensor_scalars=()) -> bytes:
    values = b""
    for tag, value in scalars:
        values += _field(1, 2, _field(1, 2, tag.encode()) + _field(2, 5, struct.pack("<f", value)))
    for tag, value in tensor_scalars:
        tensor = _field(1, 0, 1) + _field(5, 2, struct.pack("<f", value))
        values += _field(1, 2, _field(1, 2, tag.encode()) + _field(8, 2, tensor))
    for tag, data in audio:
        clip = _field(1, 5, struct.pack("<f", 22050.0)) + _field(4, 2, data)
        values += _field(1, 2, _field(1, 2, tag.encode()) + _field(6, 2, clip))
    return _field(1, 1, struct.pack("<d", 1.0)) + _field(2, 0, step) + _field(5, 2, values)


def record(data: bytes) -> bytes:
    return struct.pack("<Q", len(data)) + b"\0" * 4 + data + b"\0" * 4  # crcs are not checked


def training(
    work: Path, first: int, last: int, sentences: list[str], *, every: int = 5, version: int = 0
) -> Path:
    """Epochs first..last: val_mos rises to ~3.6 and flattens, val_mel and train_mel fall."""
    path = work / "lightning_logs" / f"version_{version}" / "events.out.tfevents.1.demo"
    path.parent.mkdir(parents=True, exist_ok=True)
    clips = [tone(1.0, 180 + 30 * i) for i in range(len(sentences))]
    with path.open("wb") as out:
        for epoch in range(first, last + 1, every):
            progress = (epoch - first) / max(1, last - first)
            mos = 3.0 + 0.62 * (1 - math.exp(-5 * progress)) + 0.03 * math.sin(epoch / 7)
            val_mel = 0.62 + 0.25 * math.exp(-4 * progress) + 0.01 * math.sin(epoch / 5)
            train_mel = 0.55 + 0.3 * math.exp(-3 * progress)
            step = 100 * (epoch + 1)
            for data in (
                event(step - 20, scalars=[("train_mel", train_mel), ("epoch", epoch)]),
                event(2 * step, audio=list(zip(sentences, clips, strict=True))),
                event(
                    step,
                    scalars=[("val_mel", val_mel), ("epoch", epoch)],
                    tensor_scalars=[("val_mos", mos)],
                ),
            ):
                out.write(record(data))
    return path
