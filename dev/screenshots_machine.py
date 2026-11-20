"""Screenshots of the real editor on the GPU machine for the step-by-step guide:
docs/assets/screens/{en,pl}/guide-NN-name.png.

    .venv/bin/python dev/screenshots_machine.py [user@host] [--only NAME ...]

user@host defaults to GPU_HOST in ~/.config/gpu-studio/host.mk.

Logs in with the password from the machine (read over ssh, never printed), opens each view and dialog
the guide shows and never starts a job. Private things are replaced on the page before each picture:
the Home Assistant address and entity names of the house (MASKS).
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs" / "assets" / "screens"
CODE_DIR = os.environ.get("GPU_DIR", "piper-voice-cloner/repo")
# name -> (address in the editor, what to do there)
SHOTS = {
    "guide-01-start": ("voice/jan", None),
    "guide-02-gear": ("voice/jan", "gear"),
    "guide-03-menu": ("voice/jan", "menu"),
    "guide-04-new-voice": ("voice/jan", "new-voice"),
    "guide-05-new-voice-import": ("voice/jan", "new-voice-import"),
    "guide-06-import": ("voice/jan/import", None),
    "guide-07-reference": ("voice/optimus_prime/reference", None),
    "guide-08-corpus": ("voice/optimus_prime/corpus", None),
    "guide-09-audition": ("voice/optimus_prime/audition", None),
    "guide-10-synthesize": ("voice/optimus_prime/synthesize", None),
    "guide-11-filter": ("voice/optimus_prime/filter", None),
    "guide-12-train": ("voice/jan/train", None),
    "guide-13-chart": ("voice/jan/train", "chart"),
    "guide-14-export": ("voice/jan/export", None),
    "guide-15-voice-settings": ("voice/jan/settings", None),
    "guide-16-base-prepare": ("base/prepare", None),
    "guide-17-base-score": ("base/score", None),
    "guide-18-base-train": ("base/train", None),
    "guide-19-base-compare": ("base/compare", None),
    "guide-20-base-select": ("base/select", None),
    "guide-21-job": ("jobs/current", None),
    "guide-22-queue": ("jobs/queue", None),
    "guide-23-history": ("jobs/history", None),
    "guide-24-settings-ha": ("settings/home_assistant", None),
    "guide-25-settings-elevenlabs": ("settings/elevenlabs", None),
}
# what must never reach the public guide -> what the picture shows instead
MASKS = [
    # any address in a private network (the Home Assistant URL)
    (
        r"https?://(?:10|127|192\.168|172\.(?:1[6-9]|2\d|3[01]))(?:\.\d{1,3}){2,3}(?::\d+)?",
        "http://homeassistant.local:8123",
    ),
    # entities and devices named after a room of the house (Polish "pokój", maybe with a person's name)
    (r"sensor\.pokoj_\w+", "sensor.gpu_plug_power"),
    (r"pokoj_\w+", "gpu_plug"),
    (r"Pokój [^<\"]*", "GPU plug"),
]

MASK_JS = """(masks) => {
  const rules = masks.map(([p, r]) => [new RegExp(p, "g"), r]);
  const fix = (text) => rules.reduce((t, [p, r]) => t.replace(p, r), text);
  const walk = (root) => {
    for (const el of root.querySelectorAll("*")) {
      if (el.shadowRoot) walk(el.shadowRoot);
      if ((el.tagName === "INPUT" || el.tagName === "TEXTAREA") && el.value) el.value = fix(el.value);
      if (el.tagName === "OPTION") el.textContent = fix(el.textContent);
      for (const node of el.childNodes) {
        if (node.nodeType === 3 && node.textContent.trim()) node.textContent = fix(node.textContent);
      }
    }
  };
  walk(document);
}"""


def gpu_host() -> str:
    """GPU_HOST from the address shared by every studio (~/.config/gpu-studio/host.mk)."""
    host_mk = Path.home() / ".config" / "gpu-studio" / "host.mk"
    for line in host_mk.read_text(encoding="utf-8").splitlines() if host_mk.is_file() else []:
        name, sep, value = line.partition("=")
        if sep and name.strip() == "GPU_HOST" and value.strip():
            return value.strip()
    raise SystemExit("save GPU_HOST in ~/.config/gpu-studio/host.mk or give user@host")


def login(host: str) -> tuple[str, str]:
    env = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", host, f"cat ~/{CODE_DIR}/docker/config/env"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    value = next(line for line in env.splitlines() if line.startswith("PVC_UI_AUTH=")).split("=", 1)[1]
    user, _, password = value.partition(":")
    return user, password


def act(page, action: str | None) -> None:
    if action == "gear":
        page.locator("[data-editor-settings]").click()
    elif action == "menu":
        page.locator("[data-menu]").click()
    elif action in ("new-voice", "new-voice-import"):
        page.locator("[data-new-voice-button]").click()
        if action == "new-voice-import":
            page.locator("[data-new-voice] [data-workflow='import']").click()
            page.locator("[data-new-voice] [data-new-name]").fill("Kuba Bajka")
        else:
            page.locator("[data-new-voice] [data-new-name]").fill("Ola Bajka")
    elif action == "chart":
        page.locator("[data-train-chart] [data-chart]").click()
        page.wait_for_selector("[data-chart-dialog]")


def main(argv: list[str]) -> int:
    from playwright.sync_api import sync_playwright

    only = argv[argv.index("--only") + 1 :] if "--only" in argv else None
    args = [a for a in argv[: argv.index("--only")] if a] if only else argv
    host = args[0] if args else gpu_host()
    base = f"http://{host.split('@')[-1]}:7860"
    user, password = login(host)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        for language in ("pl", "en"):
            folder = OUT / language
            folder.mkdir(parents=True, exist_ok=True)
            context = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
            language_js = f"localStorage.setItem('pvc-lang', '{language}');"
            context.add_init_script(
                language_js + " localStorage.setItem('pvc-studio-theme', 'light');"
                " localStorage.setItem('pvc-studio-tour', 'done')"
            )
            page = context.new_page()
            page.goto(f"{base}/login")
            page.fill("input[name=user]", user)
            page.fill("input[name=password]", password)
            page.keyboard.press("Enter")
            page.wait_for_function("window.editorReady === true", timeout=30000)
            for name, (address, action) in SHOTS.items():
                if only and name not in only:
                    continue
                page.goto(f"{base}/#{address}")
                page.reload()
                page.wait_for_function("window.editorReady === true", timeout=30000)
                page.wait_for_timeout(1500)  # the view's data and the chart
                act(page, action)
                page.wait_for_timeout(700)
                page.evaluate(MASK_JS, MASKS)
                path = folder / f"{name}.png"
                page.screenshot(path=str(path))
                print(f"{language}/{path.name}")
            context.close()
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
