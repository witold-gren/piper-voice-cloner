"""The editor's own files: icons it uses exist, both languages say the same things, Docker setup."""

from __future__ import annotations

from pathlib import Path
import re

import yaml

REPO = Path(__file__).resolve().parents[1]
WWW = REPO / "piper_voice_cloner" / "editor" / "www"
KEY = re.compile(r'^\s{4}"?([\w-]+)"?:', re.M)


def strings(language: str) -> set[str]:
    text = (WWW / "i18n.js").read_text(encoding="utf-8")
    start = text.index(f"\n  {language}: {{")
    end = text.index("\n  },", start)
    return set(KEY.findall(text[start:end]))


def test_both_languages_have_the_same_texts():
    english, polish = strings("en"), strings("pl")
    assert english and english == polish, sorted(english ^ polish)


def test_every_text_the_components_ask_for_exists():
    asked: set[str] = set()
    for path in WWW.glob("*.js"):
        asked.update(re.findall(r'_t\("([\w-]+)"', path.read_text(encoding="utf-8")))
    missing = sorted(asked - strings("en"))
    assert not missing, missing


def test_every_icon_the_editor_uses_is_bundled():
    import sys

    sys.path.insert(0, str(REPO / "dev"))
    from icons import used_icons

    bundled = (WWW / "vendor" / "mdi.js").read_text(encoding="utf-8")
    missing = sorted(name for name in used_icons(WWW) if f'"mdi:{name}"' not in bundled)
    assert not missing, f"run python dev/icons.py: {missing}"


def test_compose_starts_with_the_machine_and_reaches_the_gpu():
    compose = yaml.safe_load((REPO / "docker" / "compose.yaml").read_text(encoding="utf-8"))
    studio = compose["services"]["studio"]
    assert studio["restart"] == "unless-stopped"
    assert studio["deploy"]["resources"]["reservations"]["devices"][0]["capabilities"] == ["gpu"]
    assert studio["env_file"] == "config/env"  # the login lives in docker/config/env
    assert studio["user"].startswith("${UID") and studio["shm_size"]
    assert "7860" in studio["ports"][0]
    assert any(volume.endswith(":/data") for volume in studio["volumes"])
    assert "./config:/config" in studio["volumes"]
    tensorboard = compose["services"]["tensorboard"]
    assert tensorboard["restart"] == "unless-stopped" and "6006" in tensorboard["ports"][0]


def test_image_is_layered_pinned_and_checks_itself():
    dockerfile = (REPO / "docker" / "Dockerfile").read_text(encoding="utf-8")
    assert "ARG PIPER_REF=v1.8.0" in dockerfile
    assert 'TRAIN_TORCH="torch==2.14.1' in dockerfile  # driver 580 = CUDA 13.0
    assert "FROM python:3.12-slim AS docs" in dockerfile and "mkdocs build --strict" in dockerfile
    assert dockerfile.index("COPY pyproject.toml") < dockerfile.index("COPY piper_voice_cloner")  # code last
    assert "import piper.espeakbridge" in dockerfile and "PerthImplicitWatermarker" in dockerfile
    assert "/api/health" in dockerfile
    assert "poweroff" not in dockerfile  # the container never powers the host off itself
    ignored = (REPO / ".dockerignore").read_text(encoding="utf-8")
    assert ignored.splitlines()[1] == "*"  # only what is let in goes into the image


def test_install_script_keeps_secrets_and_data_out_of_git():
    script = (REPO / "docker" / "install-ubuntu.sh").read_text(encoding="utf-8")
    for option in ("--show-login", "--remove"):
        assert option in script
    assert "systemctl --user disable --now" in script  # the old panel used the same ports
    ignored = (REPO / ".gitignore").read_text(encoding="utf-8")
    for path in ("docker/.env", "docker/config/", "docker/data/", "Makefile.local"):
        assert path in ignored
