"""The editor in a real browser (Google Chrome through Playwright) on the demo data.

Run with `make test-browser`; skipped when Playwright or Chrome is missing. Each test gets a fresh
demo data folder and server; jobs run with dev/fake_pvc.py, quickly.
"""

from __future__ import annotations

import os
from pathlib import Path
import socket
import sys
import threading
import time

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "dev"))

playwright = pytest.importorskip("playwright.sync_api")
pytest.importorskip("fastapi")


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="session")
def browser():
    with playwright.sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome", headless=True)
        except Exception as err:  # no Google Chrome on this computer
            pytest.skip(f"Chrome not available: {err}")
        yield browser
        browser.close()


@pytest.fixture
def demo(tmp_path, monkeypatch):
    """A running demo editor: (base url, data folder, app)."""
    import demo as demo_mod
    import uvicorn

    from piper_voice_cloner.editor.server import create_app

    root = demo_mod.build(tmp_path / "data")
    monkeypatch.setenv("PATH", f"{demo_mod.fake_tools(tmp_path / 'bin')}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_PVC_SPEED", "20")
    app = create_app(root, pvc=[sys.executable, str(REPO / "dev" / "fake_pvc.py")], tensorboard_port=6006)
    port = free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.02)
    yield f"http://127.0.0.1:{port}", root, app
    for manager in app.state.jobs.values():
        manager.stop()
        manager.wait(10)
    server.should_exit = True
    thread.join(5)


@pytest.fixture
def page(browser, demo):
    """A page of the editor in Polish; fails the test on any error in the page."""
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    context.add_init_script("localStorage.getItem('pvc-lang') || localStorage.setItem('pvc-lang', 'pl')")
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda err: errors.append(str(err)))
    # a refusal of the API (400 bad input, 409 another job) is shown in the page, not an error of it
    handled = ("status of 400", "status of 409")
    page.on(
        "console",
        lambda msg: (
            msg.type == "error" and not any(code in msg.text for code in handled) and errors.append(msg.text)
        ),
    )
    page.errors = errors
    page.open = lambda hash="": (
        page.goto(f"{demo[0]}/{'#' + hash if hash else ''}"),
        page.wait_for_function("window.editorReady === true"),
    )
    yield page
    context.close()
    assert not errors, errors


def editor(page):
    """The editor's shadow root, for queries inside it (Playwright pierces open shadow roots)."""
    return page.locator("pvc-editor")
