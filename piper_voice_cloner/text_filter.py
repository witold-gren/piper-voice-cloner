"""Plain-read-text rules for training sentences.

Training text must be ordinary prose. Digits, times, dates, list numbering, symbols and
abbreviations are read inconsistently by cloning models and teach the voice garbage
pronunciations - numbers are a job for the runtime text normalizer, not for the voice.
Such lines are rejected (never rewritten), so the dataset only contains text the voice
was really asked to say.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from .languages import LanguagePack

LIST_NUMBERING = re.compile(r"^\s*(?:\d+|[a-zA-Z]|[IVXLC]+)[.)]\s+")
URL_OR_EMAIL = re.compile(r"(?:https?://|www\.|\S+@\S+\.\S+)", re.IGNORECASE)
DIGITS = re.compile(r"\d")
SYMBOLS = re.compile(r"[%°€$£=@#&/\\+*_^~<>|\[\]{}§¶©®™]")
ALLOWED_PUNCTUATION = ".,;:!?'\"„”“«»()-–— …"


@dataclass(frozen=True)
class Verdict:
    ok: bool
    text: str
    reason: str | None = None


def clean(text: str) -> str:
    """Unicode NFC and collapsed whitespace; content is not changed."""
    return " ".join(unicodedata.normalize("NFC", text).split())


def strip_list_numbering(text: str) -> str:
    """'1. Czy mogę pomóc?' -> 'Czy mogę pomóc?' (only for persona lines written as lists)."""
    return LIST_NUMBERING.sub("", text, count=1)


def check(
    text: str,
    lang: LanguagePack,
    *,
    min_words: int = 3,
    max_words: int = 25,
) -> Verdict:
    """Accept or reject one training sentence, with the reason for reports."""
    text = clean(text)
    if not text:
        return Verdict(False, text, "empty")
    if URL_OR_EMAIL.search(text):
        return Verdict(False, text, "url_or_email")
    if LIST_NUMBERING.match(text):
        return Verdict(False, text, "list_numbering")
    if DIGITS.search(text):
        return Verdict(False, text, "digits")
    if SYMBOLS.search(text):
        return Verdict(False, text, "symbols")
    if _has_abbreviation(text, lang):
        return Verdict(False, text, "abbreviation")
    if _has_foreign_characters(text, lang):
        return Verdict(False, text, "foreign_characters")
    words = len(re.findall(rf"[{lang.letters}]+", text, re.IGNORECASE))
    if words < min_words:
        return Verdict(False, text, "too_short")
    if words > max_words:
        return Verdict(False, text, "too_long")
    return Verdict(True, text)


def _has_abbreviation(text: str, lang: LanguagePack) -> bool:
    if not lang.abbreviations:
        return False
    pattern = r"(?<![^\W\d_])(?:" + "|".join(map(re.escape, lang.abbreviations)) + r")\."
    return re.search(pattern, text, re.IGNORECASE) is not None


def _has_foreign_characters(text: str, lang: LanguagePack) -> bool:
    letters = re.compile(rf"[{lang.letters}]", re.IGNORECASE)
    for char in text:
        if char.isalpha():
            if not letters.match(char):
                return True
        elif char not in ALLOWED_PUNCTUATION:
            return True
    return False
