"""Language packs: everything language-specific lives here, the rest of the code is neutral.

Adding a language = a new module `languages/<code>.py` exposing `PACK` (see `pl.py`) and,
optionally, prompt sentences in `languages/data/<code>_*.txt`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import importlib
from pathlib import Path
import re
import unicodedata

DATA_DIR = Path(__file__).parent / "data"


@dataclass(frozen=True)
class LanguagePack:
    code: str
    # espeak-ng voice used by Piper for phonemization
    espeak_voice: str
    # Piper file name prefix, e.g. "pl_PL" -> pl_PL-<name>-medium.onnx
    locale: str
    # language code passed to cloning backends / Whisper
    synth_language: str
    # letters allowed in training text (besides ASCII a-z)
    extra_letters: str = ""
    # abbreviations that would be read letter by letter or expanded unpredictably
    abbreviations: tuple[str, ...] = ()
    # phoneme clusters worth covering explicitly in the corpus selection
    focus_phonemes: tuple[str, ...] = ()
    # sentence files bundled with the pack (relative to DATA_DIR)
    prompt_files: tuple[str, ...] = field(default_factory=tuple)

    @property
    def letters(self) -> str:
        return "a-z" + self.extra_letters

    def prompt_paths(self) -> list[Path]:
        return [DATA_DIR / name for name in self.prompt_files]

    def normalize_for_cer(self, text: str) -> str:
        """Lowercase, no punctuation, single spaces - used to compare text with ASR output."""
        text = unicodedata.normalize("NFC", text).lower()
        text = re.sub(rf"[^{self.letters}\s]", " ", text)
        return " ".join(text.split())


def get_language(code: str) -> LanguagePack:
    try:
        module = importlib.import_module(f"{__name__}.{code}")
    except ModuleNotFoundError as err:
        raise ValueError(f"No language pack for '{code}'") from err
    return module.PACK
