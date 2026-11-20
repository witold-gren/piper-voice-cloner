"""Screenshots of the editor for the documentation: docs/assets/screens/{en,pl}/NN-name.png.

    make screenshots          (Google Chrome through Playwright; the demo data, no GPU)
    .venv/bin/python dev/screenshots.py --only 17-tour 18-lessons   (only these pictures)

Runs the demo editor in this process on made-up voices and opens each part the guide shows, in both
languages, in the light theme at 1440×900.
"""

from __future__ import annotations

import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "dev"))

OUT = REPO / "docs" / "assets" / "screens"
# name -> (address in the editor, what to do there)
SHOTS = {
    "01-overview": ("voice/kasia", None),
    "03-import": ("voice/tomek/import", None),
    "04-train": ("voice/kasia/train", None),
    "05-chart": ("voice/kasia/train", "chart"),
    "06-reference": ("voice/ola_bajka/reference", None),
    "07-audition": ("voice/ola_bajka/audition", None),
    "08-synthesize": ("voice/alicja/synthesize", None),
    "09-filter": ("voice/alicja/filter", None),
    "10-export": ("voice/kasia/export", None),
    "11-queue": ("jobs/queue", "queue"),
    "12-base-score": ("base/score", None),
    "13-settings-ha": ("settings/home_assistant", None),
    "14-menu": ("voice/kasia", "menu"),
    "15-countdown": ("voice/kasia/train", "countdown"),
    "16-save": ("voice/kasia/settings", "save"),
    "17-tour": ("voice/kasia", "tour"),
    "18-lessons": ("voice/kasia", "lessons"),
    "19-lesson": ("voice/kasia/train", "lesson"),
    "20-help-lesson": ("voice/kasia/train", "help-lesson"),
}
# what stays over the editor after its picture: the page is loaded again for the next one
OVERLAYS = {"tour", "lessons", "lesson", "help-lesson"}


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def start_demo(folder: Path):
    """The demo in `folder`, with relative paths and the command named `pvc`: the logs in the
    pictures show `$ pvc --root data …`, never a path of this computer."""
    import demo
    import uvicorn

    os.chdir(folder)
    root = Path("data")
    demo.build(root)
    tools = demo.fake_tools(folder / ".bin")
    (tools / "pvc").write_text(f'#!/bin/sh\nexec "{sys.executable}" "{REPO / "dev" / "fake_pvc.py"}" "$@"\n')
    (tools / "pvc").chmod(0o755)
    os.environ["PATH"] = f"{tools}{os.pathsep}{os.environ['PATH']}"
    os.environ["PVC_HA_CONFIG"] = str(root / ".config" / "home_assistant.json")
    os.environ["PVC_ELEVENLABS_CONFIG"] = str(root / ".config" / "elevenlabs.json")
    from piper_voice_cloner import power
    from piper_voice_cloner.editor.server import create_app

    power.power_off = lambda: None  # the countdown shown here never switches anything off
    app = create_app(root, pvc=["pvc"], tensorboard_port=6006, countdown=False)
    port = free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.02)
    return f"http://127.0.0.1:{port}", app


def act(page, action: str | None, app) -> None:
    if action != "countdown" and app.state.power_timer.cancel():
        page.reload()  # the countdown of an earlier picture is gone
        page.wait_for_function("window.editorReady === true")
    if action == "menu":
        page.locator("[data-menu]").click()
    elif action == "countdown":
        app.state.machine.ready = lambda: True  # as with Home Assistant connected
        os.environ["FAKE_PVC_SPEED"] = "50"
        app.state.start("filter", "alicja", ["filter", "alicja"], poweroff=True)
        app.state.jobs["current"].wait(30)
        app.state.power_timer.check()
        page.reload()
        page.wait_for_function("window.editorReady === true")
        page.wait_for_selector("pvc-editor >> [data-countdown]")
    elif action == "save":
        page.locator("[data-field='quality.max_cer'] input").fill("0.05")
        page.wait_for_timeout(1000)
        page.locator("[data-save]").click()
        page.locator("[data-save-note]").fill("ostrzejszy filtr dla zaszumionych nagrań")
    elif action == "chart":
        page.locator("[data-train-chart] [data-chart]").click()
        page.wait_for_selector("[data-chart-dialog]")
    elif action == "tour":
        page.evaluate("document.querySelector('pvc-editor')._tour = true")
        page.locator("[data-tour-next]").click()  # the tree, after the welcome
        page.wait_for_timeout(500)
    elif action == "lessons":
        page.locator("[data-editor-settings]").click()
        page.locator("[data-gear-lessons]").click()
    elif action == "lesson":
        page.evaluate("document.querySelector('pvc-editor')._startLesson('train')")
        for _ in range(2):
            page.locator("[data-tour-next]").click()  # Epochs and time
        page.wait_for_timeout(500)
    elif action == "help-lesson":
        page.locator("[data-step-help] [data-help-button]").first.click()
    elif action == "queue":
        for name in ("tomek", "kasia"):
            page.locator(f"[data-queue-voice='{name}']").check()


def main(argv: list[str]) -> int:
    from playwright.sync_api import sync_playwright

    only = set(argv[argv.index("--only") + 1 :]) if "--only" in argv else None

    with tempfile.TemporaryDirectory() as tmp:
        base, app = start_demo(Path(tmp))
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            for language in ("pl", "en"):
                folder = OUT / language
                folder.mkdir(parents=True, exist_ok=True)
                context = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
                app.state.power_timer.cancel()
                seen = "localStorage.setItem('pvc-studio-tour', 'done')"  # the tour has its own pictures
                context.add_init_script(f"localStorage.setItem('pvc-lang', '{language}'); {seen}")
                page = context.new_page()
                for name, (address, action) in SHOTS.items():
                    if only and name not in only:
                        continue
                    page.goto(f"{base}/#{address}")
                    page.wait_for_function("window.editorReady === true")
                    page.wait_for_timeout(700)  # the view's data and the chart
                    act(page, action, app)
                    page.wait_for_timeout(300)
                    page.screenshot(path=str(folder / f"{name}.png"))
                    print(f"{language}/{name}.png")
                    if action in OVERLAYS:
                        page.reload()
                        page.wait_for_function("window.editorReady === true")
                context.close()
            browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
