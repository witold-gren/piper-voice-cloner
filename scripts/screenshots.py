#!/usr/bin/env python3
"""Screenshots of the web UI for the README and the guide (docs/assets/screens/<lang>/*.png).

Runs the real `pvc ui` on a made-up data folder (two example voices, no recordings, no private
data) and photographs the page with Playwright in the installed Google Chrome. Run again after
changing the UI:

    make screenshots          # = .venv/bin/python scripts/screenshots.py

Needs: pip install -e '.[ui,docs]' and Google Chrome.
"""

from __future__ import annotations

from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "assets" / "screens"
PVC = Path(sys.executable).with_name("pvc")
VOICES = (("ola_bajka", "elevenlabs"), ("robot", "chatterbox"))


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for(url: str, seconds: float = 60) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            urllib.request.urlopen(url, timeout=2).close()
            return
        except OSError:
            time.sleep(0.5)
    raise SystemExit(f"the UI did not start: {url}")


def main() -> None:
    from playwright.sync_api import sync_playwright

    with tempfile.TemporaryDirectory() as tmp:
        data = Path(tmp) / "voices-demo"
        for name, backend in VOICES:
            subprocess.run(
                [PVC, "--root", data, "init", name, "--backend", backend, "--base", "lessac"],
                check=True,
                stdout=subprocess.DEVNULL,
            )
        port = free_port()
        server = subprocess.Popen(
            [PVC, "--root", data, "ui", "--host", "127.0.0.1", "--port", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            wait_for(f"http://127.0.0.1:{port}/en/")
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel="chrome")
                for lang in ("en", "pl"):
                    # Gradio's own widgets (file upload) follow the browser language
                    page = browser.new_page(
                        viewport={"width": 1440, "height": 900},
                        device_scale_factor=2,
                        locale="en-US" if lang == "en" else "pl-PL",
                    )
                    page.goto(f"http://127.0.0.1:{port}/{lang}/")
                    # Gradio keeps a stream open, so "network idle" never comes
                    page.wait_for_selector(".gradio-container", timeout=60_000)
                    page.wait_for_timeout(2500)
                    target = OUT / lang / "overview.png"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=target)
                    print(f"{lang}: {target.relative_to(ROOT)}")
                    page.close()
                browser.close()
        finally:
            server.terminate()
            server.wait(timeout=10)


if __name__ == "__main__":
    main()
