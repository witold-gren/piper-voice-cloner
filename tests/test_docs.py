"""The guide (docs/, MkDocs): both languages alike, pictures there, and every button it names exists."""

from __future__ import annotations

from pathlib import Path
import re

import yaml

REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "docs"
I18N = REPO / "piper_voice_cloner" / "editor" / "www" / "i18n.js"
UI = re.compile(r'<span class="ui">(.+?)</span>')
PICTURE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)")
ANCHOR = re.compile(r"\{#([a-z0-9-]+)\}")
TEXT = re.compile(r'^\s{4}"?[\w-]+"?:\s*\n?\s*"((?:[^"\\]|\\.)*)"', re.M)


def nav_pages() -> list[str]:
    config = yaml.load((REPO / "mkdocs.yml").read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    return [next(iter(item.values())) for item in config["nav"]]


def pages(language: str) -> dict[str, str]:
    found = {}
    for name in nav_pages():
        if name.startswith("changelog"):
            continue  # made from CHANGELOG.md on every build
        path = DOCS / (name if language == "en" else name.replace(".md", ".pl.md"))
        found[name] = path.read_text(encoding="utf-8")
    return found


def strings(language: str) -> set[str]:
    text = I18N.read_text(encoding="utf-8")
    start = text.index(f"\n  {language}: {{")
    end = text.index("\n  },", start)
    return {value.replace('\\"', '"') for value in TEXT.findall(text[start:end])}


def test_every_page_of_the_menu_exists_in_both_languages():
    assert set(pages("en")) == set(pages("pl"))


def test_both_languages_show_the_same_pictures_and_anchors():
    english, polish = pages("en"), pages("pl")
    for name in english:
        en_pictures = [p.replace("/en/", "/") for p in PICTURE.findall(english[name])]
        pl_pictures = [p.replace("/pl/", "/") for p in PICTURE.findall(polish[name])]
        assert en_pictures == pl_pictures, name
        assert ANCHOR.findall(english[name]) == ANCHOR.findall(polish[name]), name


def test_every_picture_is_there():
    for language in ("en", "pl"):
        for name, text in pages(language).items():
            for picture in PICTURE.findall(text):
                assert (DOCS / picture).is_file(), f"{language}/{name}: {picture} (make screenshots)"


def test_every_button_the_guide_names_is_in_the_editor():
    for language in ("en", "pl"):
        known = strings(language)
        for name, text in pages(language).items():
            missing = [label for label in UI.findall(text) if label not in known]
            assert not missing, f"{language}/{name}: {missing}"


def test_the_editors_help_links_reach_a_page_and_its_anchor():
    parts = (I18N.parent / "parts.js").read_text(encoding="utf-8")
    table = parts[parts.index("export const DOCS") :]
    links = re.findall(r'^\s+\w+: "([\w-]+)(?:#([\w-]+))?",$', table, re.M)
    assert links
    for page, anchor in links:
        for language in ("en", "pl"):
            text = pages(language)[f"{page}.md"]
            assert not anchor or f"{{#{anchor}}}" in text, f"{language}/{page}.md has no #{anchor}"


ROW = re.compile(r"^\| `([\w.]+)` \| ([^|]+) \|", re.M)


def test_the_parameter_table_is_the_code():
    from piper_voice_cloner import config as config_mod

    defaults = config_mod.VoiceConfig(name="x").model_dump(mode="json")
    for language in ("en", "pl"):
        rows = ROW.findall(pages(language)["training.md"])
        assert len(rows) >= 15, language
        for path, shown in rows:
            value = defaults
            for part in path.split("."):
                value = value[part]
            expected = (
                "null"
                if value is None
                else ", ".join(map(str, value)).join("[]")
                if isinstance(value, list)
                else str(value)
            )
            assert shown.strip() == expected, (
                f"{language}: {path} is {expected} in the code, {shown.strip()} in the guide"
            )
