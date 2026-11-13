from __future__ import annotations

import pytest

from piper_voice_cloner import text_filter
from piper_voice_cloner.languages import get_language


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        # real lines found in the old datasets
        ("00:08:05", "digits"),
        ("12.05.1991", "digits"),
        ("13 czerwca 2012", "digits"),
        ("1. Czy mogę w czymś pomóc? Z przyjemnością udzielę wsparcia", "list_numbering"),
        ("Spotkanie o godz. siódmej rano w kuchni.", "abbreviation"),
        ("Mieszkam przy ul. Kwiatowej w Krakowie.", "abbreviation"),
        ("Jest dwadzieścia stopni, czyli ok. tyle co wczoraj.", "abbreviation"),
        ("Temperatura wynosi dwadzieścia % wilgotności.", "symbols"),
        ("Napisz do mnie na adres piotr@example.com dzisiaj.", "url_or_email"),
        ("Zobacz stronę www.example.pl koniecznie dzisiaj.", "url_or_email"),
        ("Café au lait to kawa z mlekiem.", "foreign_characters"),
        ("Привет как дела друг", "foreign_characters"),
        ("Tak.", "too_short"),
        ("", "empty"),
        ("   ", "empty"),
    ],
)
def test_rejected(text, reason):
    verdict = text_filter.check(text, get_language("pl"))
    assert not verdict.ok
    assert verdict.reason == reason


@pytest.mark.parametrize(
    "text",
    [
        "Zasłoniła na chwilę oczy dłonią i parsknęła śmiechem.",
        'Powiedziała pani: "porywczy", nie: "złośnik".',
        "Patrzcie go: osioł, udaje mądrego.",
        "Więc pyta się: co to jest? i do czego służy?",
        "Czy „wygooglować” to już jest poprawne słowo czy nie?",
        "Raz, dwa, trzy, szukam!",
        "Jest dobrze, a nawet bardzo dobrze – powiedział.",
        "Wszystko jest ok, nie martw się wcale.",
    ],
)
def test_plain_prose_passes(text):
    verdict = text_filter.check(text, get_language("pl"))
    assert verdict.ok, verdict.reason


def test_too_long():
    text = " ".join(["słowo"] * 30) + "."
    assert text_filter.check(text, get_language("pl")).reason == "too_long"
    assert text_filter.check(text, get_language("pl"), max_words=40).ok


def test_abbreviation_needs_whole_word():
    # "bok." / "dom." end with letters of abbreviations but are ordinary words
    assert text_filter.check("Stanął z boku i patrzył na bok.", get_language("pl")).ok
    assert text_filter.check("Wieczorem wróciliśmy wszyscy do dom.", get_language("pl")).ok


def test_strip_list_numbering():
    assert text_filter.strip_list_numbering("1. Czy mogę pomóc?") == "Czy mogę pomóc?"
    assert text_filter.strip_list_numbering("12) Dobrze.") == "Dobrze."
    assert text_filter.strip_list_numbering("Czy mogę pomóc?") == "Czy mogę pomóc?"


def test_clean_normalizes_whitespace_and_unicode():
    # "ę" written as "e" + combining ogonek must count as the Polish letter
    decomposed = "Umyj zęby przed snem."
    assert text_filter.clean(f"  {decomposed}  \n") == "Umyj zęby przed snem."
    assert text_filter.check(decomposed, get_language("pl")).ok
    assert text_filter.check("Ala  ma\tkota i psa.", get_language("pl")).text == "Ala ma kota i psa."
