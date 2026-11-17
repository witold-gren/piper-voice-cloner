"""MkDocs hook of the documentation site (mkdocs.yml).

The changelog lives at the top of the repository, where GitHub shows it; the site needs it in docs/.
Before each build it is copied there (only when it changed, so `mkdocs serve` does not rebuild in a
loop). The copy is not kept in git (.gitignore).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GENERATED = {"changelog.md": "CHANGELOG.md", "changelog.pl.md": "CHANGELOG.md"}


def on_pre_build(config, **kwargs) -> None:
    for target, source in GENERATED.items():
        text = (ROOT / source).read_text(encoding="utf-8")
        path = ROOT / "docs" / target
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8")
