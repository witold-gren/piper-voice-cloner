"""The "Try it on a Mac" section and `make demo` in Docker (the gpu-studio standard, §8b)."""

from __future__ import annotations

import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import urllib.request

import pytest

REPO = Path(__file__).resolve().parents[1]
PAGES = {
    "README.md": "## Try it on a Mac",
    "README.pl.md": "## Wypróbuj na Macu",
    "docs/installation.md": "## Try it on a Mac {#try-on-a-mac}",
    "docs/installation.pl.md": "## Wypróbuj na Macu {#try-on-a-mac}",
}


def demo_port() -> str:
    return re.search(r"^DEMO_PORT \?= (\d+)", (REPO / "Makefile").read_text(), re.M).group(1)


def section(text: str, heading: str) -> str:
    rest = text.split(heading, 1)[1]
    return rest.split("\n## ", 1)[0]


@pytest.mark.parametrize("path", PAGES)
def test_the_section_says_how_to_try_it(path):
    text = (REPO / path).read_text()
    assert PAGES[path] in text
    body = section(text, PAGES[path])
    assert "`make demo`" in body
    assert f"http://localhost:{demo_port()}" in body
    assert "`demo` / `demo`" in body
    assert "Docker Desktop" in body and "brew" not in body
    assert "`make demo-clean`" in body and "`make setup`" in body
    for target in ("make test`", "make test-browser", "make docs"):
        assert target in body
    assert len(body.strip().splitlines()) <= 14  # short


@pytest.mark.parametrize("path", ["README.md", "README.pl.md"])
def test_the_section_comes_before_the_install(path):
    text = (REPO / path).read_text()
    install = "## Install" if path == "README.md" else "## Instalacja"
    assert text.index(PAGES[path]) < text.index(install)


def free_port() -> int:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_ctrl_c_on_the_local_demo_leaves_nothing_behind(tmp_path):
    port = free_port()
    env = {**os.environ, "TMPDIR": str(tmp_path)}
    demo = subprocess.Popen(
        [sys.executable, str(REPO / "dev" / "demo.py"), "--port", str(port)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1)
                break
            except OSError:
                time.sleep(0.2)
        else:
            pytest.fail("the demo did not start")
        assert list(tmp_path.glob("pvc-demo-*"))
    finally:
        demo.send_signal(signal.SIGINT)
        demo.wait(timeout=20)
    assert not list(tmp_path.glob("pvc-demo-*"))


def test_make_demo_builds_and_runs_the_demo_image():
    makefile = (REPO / "Makefile").read_text()
    recipe = makefile.split("\ndemo:", 1)[1].split("\n\n", 1)[0]
    assert "docker build -f docker/Dockerfile --target demo" in recipe
    assert "docker run --rm --init -it -p 127.0.0.1:$(DEMO_PORT):$(DEMO_PORT)" in recipe
    assert "setup" not in recipe.splitlines()[0]  # no Python on the computer for the demo
    assert "Docker Desktop" in makefile  # a clear message without Docker
    dockerfile = (REPO / "docker" / "Dockerfile").read_text()
    demo = dockerfile.split("AS demo", 1)[1]
    assert "torch" not in demo.split("ENTRYPOINT")[0].replace("no torch", "")
    assert "FROM train" not in demo and "FROM deps" not in demo
    ignored = (REPO / ".dockerignore").read_text()
    for name in ("demo.py", "fake_pvc.py", "tfevents.py"):
        assert f"!dev/{name}" in ignored


def docker_works() -> bool:
    import shutil

    if not shutil.which("docker"):
        return False
    return subprocess.run(["docker", "info"], capture_output=True).returncode == 0


@pytest.mark.docker
@pytest.mark.skipif(not docker_works(), reason="Docker is not running")
def test_the_demo_image_answers_logs_in_and_leaves_no_container():
    import uuid

    import httpx

    image = "piper-voice-cloner-demo"
    subprocess.run(
        ["docker", "build", "-q", "-f", "docker/Dockerfile", "--target", "demo", "-t", image, "."],
        cwd=REPO, check=True, capture_output=True, timeout=1200,
    )  # fmt: skip
    port, name = free_port(), f"pvc-demo-test-{uuid.uuid4().hex[:8]}"
    run = subprocess.Popen(
        ["docker", "run", "--rm", "--init", "--name", name, "-p", f"127.0.0.1:{port}:{port}", image,
         "--port", str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )  # fmt: skip
    try:
        base = f"http://127.0.0.1:{port}"
        for _ in range(150):
            try:
                if httpx.get(f"{base}/api/health", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.2)
        else:
            pytest.fail("the demo container did not answer")
        with httpx.Client(base_url=base, follow_redirects=False) as client:
            assert client.get("/").headers["location"] == "/login"
            assert client.post("/login", data={"user": "demo", "password": "no"}).status_code == 303
            right = client.post("/login", data={"user": "demo", "password": "demo"})
            assert right.headers["location"] == "/"
            state = client.get("/api/state")
            assert state.status_code == 200 and "kasia" in state.text  # the made-up voices
    finally:
        run.send_signal(signal.SIGINT)  # Ctrl+C
        run.wait(timeout=30)
    left = subprocess.run(
        ["docker", "ps", "-aq", "--filter", f"name={name}"], capture_output=True, text=True
    ).stdout
    assert left.strip() == ""
