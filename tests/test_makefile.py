"""The Makefile of the gpu-studio standard (section 2): the same targets as every studio, in three groups,
help in both languages, Start needs only Docker."""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest

REPO = Path(__file__).resolve().parents[1]
MAKEFILE = (REPO / "Makefile").read_text(encoding="utf-8")
# the gpu-studio standard, section 2: the groups in this order with their targets
GROUPS = {
    "1. Start": "help demo demo-clean docs docs-serve doctor",
    "2. The GPU machine": "install deploy login logs status docker-up docker-down docker-logs docker-shell",
    "3. Development": "setup demo-local test test-browser test-docker test-all lint format docs-build"
    " screenshots icons clean",
}
STANDARD = " ".join(GROUPS.values()).split()
OLD_NAMES = ("ui", "studio", "studio-docker", "docs-site", "remote", "setup-mac", "check")


def targets() -> dict[str, str]:
    return dict(re.findall(r"^([a-z-]+):[^\n]*?## (.+)$", MAKEFILE, re.M))


def groups() -> dict[str, list[str]]:
    """Every documented target under the `##@` heading it stands below."""
    found: dict[str, list[str]] = {}
    current = None
    for line in MAKEFILE.splitlines():
        heading = re.match(r"^##@ (.+?) \| ", line)
        if heading:
            current = heading.group(1)
            found[current] = []
            continue
        target = re.match(r"^([a-z-]+):[^\n]*?## ", line)
        if target and current:
            found[current].append(target.group(1))
    return found


def recipe(name: str) -> str:
    return MAKEFILE.split(f"\n{name}:", 1)[1].split("\n\n", 1)[0]


def test_every_target_of_the_standard_is_there():
    missing = [name for name in STANDARD if name not in targets()]
    assert not missing, missing


def test_every_target_says_what_it_does_in_both_languages():
    for name, text in targets().items():
        english, sep, polish = text.partition(" | ")
        assert sep and english.strip() and polish.strip(), name
    for section in re.findall(r"^##@ (.+)$", MAKEFILE, re.M):
        assert " | " in section, section


def test_the_groups_come_in_the_order_of_the_standard_with_their_targets():
    found = groups()
    assert list(found) == list(GROUPS)
    for group, names in GROUPS.items():
        assert found[group] == names.split(), group


def test_start_and_the_machine_need_no_python():
    for name in GROUPS["1. Start"].split() + GROUPS["2. The GPU machine"].split():
        first = MAKEFILE.split(f"\n{name}:", 1)[1].split("\n", 1)[0].split("##")[0]
        assert "setup" not in first and "VENV" not in first, name
        body = recipe(name)
        assert "$(VENV)/bin/python" not in body and "$(VENV)/bin/ruff" not in body, name  # help only looks
    for name in ("demo", "demo-clean", "docs-serve", "docs-build"):
        assert "$(need-docker)" in recipe(name), name
    assert "docker build -f docker/Dockerfile --target docs" in recipe("docs-build").replace(" -q", "")
    assert "docker cp" in recipe("docs-build")
    assert "mkdocs serve --dev-addr 0.0.0.0:$(DOCS_PORT)" in recipe("docs-serve")
    assert re.search(r"^DOCS_PORT \?= 8861$", MAKEFILE, re.M)
    assert ".venv-docs/bin" not in MAKEFILE


def test_no_aliases_or_old_names():
    names = targets()
    assert not [name for name in OLD_NAMES if name in names]
    bodies = [recipe(name).split("\n", 1)[-1].strip() for name in names if name != "test-all"]
    assert all(
        not re.fullmatch(r"\$\(MAKE\) [a-z-]+", body) for body in bodies
    )  # a target only calling another


def test_tests_never_build_images_and_test_docker_does():
    assert '-m "not docker"' in recipe("test")
    assert "-m docker" in recipe("test-docker")
    first = MAKEFILE.split("\ntest-all:", 1)[1].split("##")[0]
    assert first.split() == ["lint", "test", "test-browser", "test-docker"]
    assert "docker:" in (REPO / "pyproject.toml").read_text()  # the marker is registered


def test_setup_uses_uv_with_one_python_version():
    assert re.search(r"^PYTHON_VERSION \?= 3\.12$", MAKEFILE, re.M)
    block = MAKEFILE.split("$(VENV)/bin/pvc: pyproject.toml", 1)[1].split("\n\n", 1)[0]
    assert "uv venv" in block and "--python $(PYTHON_VERSION)" in block and "uv pip install" in block
    assert "uv not found" in block and "astral.sh/uv/install.sh" in block
    assert "bin/pip install" not in MAKEFILE


def test_doctor_only_checks():
    body = recipe("doctor")
    for word in (
        "docker info",
        "Google Chrome",
        "uv --version",
        "GPU_HOST",
        "BatchMode=yes",
        "ConnectTimeout=3",
    ):
        assert word in body, word
    assert "uv pip" not in body and "brew install" not in body and "apt" not in body


def make(*args: str, path: str | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, **({"PATH": path} if path else {})}
    return subprocess.run(
        ["make", "-s", *args], cwd=REPO, capture_output=True, text=True, env=env, timeout=60
    )


HELP_SECTIONS = {
    "en": ["1. Start", "2. The GPU machine", "3. Development"],
    "pl": ["1. Start", "2. Maszyna z GPU", "3. Rozwój"],
}


@pytest.mark.skipif(not shutil.which("make"), reason="make not installed")
@pytest.mark.parametrize("language", HELP_SECTIONS)
def test_help_in_both_languages(language):
    out = make("help", f"HELP_LANG={language}", "GPU_HOST=user@gpu").stdout
    positions = [out.index(section) for section in HELP_SECTIONS[language]]
    assert positions == sorted(positions) and "deploy" in out


@pytest.mark.skipif(not shutil.which("make"), reason="make not installed")
@pytest.mark.parametrize("target", ["demo", "docs", "docs-serve", "docs-build"])
def test_without_docker_a_clear_message(target):
    out = make(target, "DOCKER=docker-that-is-not-there")  # also where docker sits in /usr/bin (CI)
    assert out.returncode != 0
    assert "install and start Docker Desktop" in out.stdout + out.stderr
    assert "Traceback" not in out.stdout + out.stderr


@pytest.mark.skipif(not shutil.which("make"), reason="make not installed")
def test_doctor_installs_nothing_and_reports_every_tool():
    out = make("doctor", "GPU_HOST=", path="/usr/bin:/bin")
    for name in ("Docker", "Google Chrome", "uv (make setup)", "GPU_HOST"):
        assert name in out.stdout, name
    assert "gpu-studio/host.mk" in out.stdout
