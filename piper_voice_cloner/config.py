"""Per-voice configuration: voices/<name>/voice.yaml."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
import yaml

VOICE_NAME = re.compile(r"^[a-z0-9][a-z0-9_]*$")
CONFIG_FILE = "voice.yaml"


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SynthesisConfig(_Section):
    backend: Literal["chatterbox", "xtts", "elevenlabs"] = "chatterbox"
    # backend specific knobs, e.g. chatterbox: cfg_weight, exaggeration, temperature
    options: dict[str, Any] = Field(default_factory=dict)
    # generate this many times the target so filtering can be strict
    overgenerate: float = Field(1.3, ge=1.0, le=3.0)
    seeds: list[int] = Field(default_factory=lambda: [1, 2, 3, 4])
    # ElevenLabs only: id of the voice in your ElevenLabs account
    elevenlabs_voice_id: str | None = None
    # its name, only to show it without asking ElevenLabs
    elevenlabs_voice_name: str | None = None


class QualityConfig(_Section):
    asr_model: str = "large-v3"
    max_cer: float = Field(0.04, ge=0, le=1)
    # None = calibrated from the reference clips by `pvc reference`
    min_similarity: float | None = None
    mos_drop_fraction: float = Field(0.10, ge=0, le=0.5)
    # seconds per character outside this band = cut off or hallucinated
    min_seconds_per_char: float = 0.035
    max_seconds_per_char: float = 0.16


# the own Polish base trained from scratch (no English); the name is shown to the user as it is
POLISH_BASE = "bazowy-pl"
# names of the same base written by older versions into voice.yaml
OLD_BASE_NAMES = {"scratch-pl": POLISH_BASE}


class TrainConfig(_Section):
    # bazowy-pl: own base trained from scratch (no English), lessac: English lessac medium,
    # ckpt:<path>: any Piper checkpoint (medium or high: the model size follows the checkpoint)
    base: str = POLISH_BASE
    batch_size: int = Field(32, ge=1)
    # epochs on top of the starting checkpoint
    max_epochs: int = Field(1000, ge=1)
    # data loader processes; piper1-gpl defaults to 1, which starves a fast GPU
    num_workers: int = Field(8, ge=0)
    validation_split: float = Field(0.05, ge=0, le=0.5)
    num_test_examples: int = Field(5, ge=0)
    extra_args: list[str] = Field(default_factory=list)

    @field_validator("base")
    @classmethod
    def _known_base(cls, value: str) -> str:
        value = OLD_BASE_NAMES.get(value, value)
        if value in (POLISH_BASE, "lessac") or (value.startswith("ckpt:") and len(value) > 5):
            return value
        raise ValueError(f"base must be '{POLISH_BASE}', 'lessac' or 'ckpt:<path>'")


class VoiceConfig(_Section):
    name: str
    language: str = "pl"
    # file name in Piper style without quality, e.g. pl_PL-kuba_bajka -> pl_PL-kuba_bajka-medium (or -high)
    piper_name: str | None = None
    target_clips: int = Field(2000, ge=10)
    synthesis: SynthesisConfig = Field(default_factory=SynthesisConfig)
    quality: QualityConfig = Field(default_factory=QualityConfig)
    train: TrainConfig = Field(default_factory=TrainConfig)

    @field_validator("name")
    @classmethod
    def _valid_name(cls, value: str) -> str:
        if not VOICE_NAME.match(value):
            raise ValueError("voice name: lowercase letters, digits and '_' only")
        return value

    def file_stem(self, locale: str, quality: str = "medium") -> str:
        return f"{self.piper_name or f'{locale}-{self.name}'}-{quality}"


def load(voice_dir: Path) -> VoiceConfig:
    path = voice_dir / CONFIG_FILE
    if not path.is_file():
        raise FileNotFoundError(f"{path} not found - run `pvc init` first")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return VoiceConfig.model_validate(data)


def save(voice_dir: Path, config: VoiceConfig) -> Path:
    voice_dir.mkdir(parents=True, exist_ok=True)
    path = voice_dir / CONFIG_FILE
    data = config.model_dump(mode="json", exclude_none=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path
