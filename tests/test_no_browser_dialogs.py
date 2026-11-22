"""Questions are windows of the editor (confirm.js), never window.confirm / alert / prompt."""

from __future__ import annotations

from pathlib import Path
import re

WWW = Path(__file__).resolve().parents[1] / "piper_voice_cloner" / "editor" / "www"
NATIVE = re.compile(r"\b(?:window\.)?(confirm|alert|prompt)\s*\(")


def test_no_native_browser_dialogs():
    found = []
    for path in sorted(WWW.glob("*.js")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("//", 1)[0]
            if NATIVE.search(code):
                found.append(f"{path.name}:{number}: {line.strip()}")
    assert found == [], "use ask() from confirm.js:\n" + "\n".join(found)
