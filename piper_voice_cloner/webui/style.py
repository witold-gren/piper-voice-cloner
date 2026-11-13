"""Look of the web UI, shared with the wake word training panel (home-assistant-wakeword):
same palette, top bar, stepper pills, cards, GPU rings and terminal. Light and dark mode.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
import re

import gradio as gr

FONT = ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "sans-serif"]
FONT_MONO = ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"]

STATIC = Path(__file__).parent / "static"
# browser tab icon: SVG for current browsers, PNG for the rest, a full square for iOS home screens
ICON_LINKS = (
    '<link rel="icon" type="image/svg+xml" href="/favicon.svg">'
    '<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png">'
    '<link rel="apple-touch-icon" href="/apple-touch-icon.png">'
    '<meta name="theme-color" content="#f2733a">'
)


# the panel's own question window instead of the browser's confirm() (as in the wake word panel):
# window.pvcAsk(message, {danger}) -> Promise<bool>; OK = true, Cancel / Esc / a click outside = false
ASK_JS = """
window.pvcAsk = (message, { danger = false } = {}) => new Promise((resolve) => {
  let dialog = document.getElementById("pvc-ask");
  if (!dialog) {
    dialog = document.createElement("dialog");
    dialog.id = "pvc-ask";
    dialog.className = "pvc-ask";
    dialog.innerHTML = '<p class="pvc-ask-text"></p><div class="pvc-ask-actions">'
      + '<button type="button" class="pvc-ask-cancel"></button>'
      + '<button type="button" class="pvc-ask-ok">OK</button></div>';
    (document.querySelector("gradio-app") || document.body).append(dialog);
  }
  const ok = dialog.querySelector(".pvc-ask-ok");
  const cancel = dialog.querySelector(".pvc-ask-cancel");
  dialog.querySelector(".pvc-ask-text").textContent = message;
  cancel.textContent = __CANCEL__;
  ok.classList.toggle("danger", danger);
  const finish = (answer) => {
    dialog.onclose = null;
    if (dialog.open) dialog.close();
    resolve(answer);
  };
  // a late "close" of the previous question must not answer this one
  dialog.onclose = () => { if (!dialog.open) finish(false); };
  ok.onclick = () => finish(true);
  cancel.onclick = () => finish(false);
  dialog.onclick = (event) => { if (event.target === dialog) finish(false); };
  dialog.showModal();
  ok.focus();
});
"""


def head(cancel: str) -> str:
    """<head> of a language mount: the icons and pvcAsk with that language's Cancel."""
    return f"{ICON_LINKS}<script>{ASK_JS.replace('__CANCEL__', json.dumps(cancel))}</script>"


BOOK_SVG = (
    '<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 4h6a4 4 0 0 1 4 4v12a3 3 0 0 0-3-3H2z"/>'
    '<path d="M22 4h-6a4 4 0 0 0-4 4v12a3 3 0 0 1 3-3h7z"/></svg>'
)
# a voice wave and its fainter copy behind it - the cloned voice; warm amber -> coral, so it is never
# mistaken for the purple wake word panel (static/favicon.svg is the same drawing)
CLONE_WAVE = "M2 12c1.7-6 3.3-6 5 0s3.3 6 5 0 3.3-6 5 0 3.3 6 5 0"
CLONE_SVG = (
    f'<svg viewBox="0 0 24 24" fill="none"><path d="{CLONE_WAVE}" transform="translate(1.8 -2.6)" '
    f'stroke-opacity=".5"/><path d="{CLONE_WAVE}" transform="translate(-0.9 1.3)"/></svg>'
)


def theme() -> gr.themes.ThemeClass:
    # system fonts only (Inter if installed): nothing is fetched from Google Fonts
    return gr.themes.Soft(
        primary_hue="indigo",
        secondary_hue="violet",
        neutral_hue="slate",
        radius_size="lg",
        font=FONT,
        font_mono=FONT_MONO,
    ).set(
        body_background_fill="#f4f6fb",
        body_background_fill_dark="#0b0e17",
        background_fill_primary="#ffffff",
        background_fill_primary_dark="#141a29",
        background_fill_secondary="#eef1f8",
        background_fill_secondary_dark="#0f1320",
        block_background_fill="#ffffff",
        block_background_fill_dark="#141a29",
        block_border_color="#e5e7ef",
        block_border_color_dark="#232b3e",
        border_color_primary="#e5e7ef",
        border_color_primary_dark="#232b3e",
        input_background_fill="#eef1f8",
        input_background_fill_dark="#0f1320",
        block_radius="18px",
        block_shadow="0 1px 2px rgba(17, 24, 39, .04), 0 8px 24px rgba(17, 24, 39, .06)",
        block_shadow_dark="0 1px 2px rgba(0, 0, 0, .3), 0 8px 28px rgba(0, 0, 0, .35)",
        color_accent="#5b5bf0",
        color_accent_soft="#ecebff",
        color_accent_soft_dark="#1f2245",
        button_primary_background_fill="linear-gradient(135deg, #5b5bf0, #8b5cf6)",
        button_primary_background_fill_dark="linear-gradient(135deg, #8183ff, #b18cff)",
        button_primary_background_fill_hover="linear-gradient(135deg, #4f4fe0, #7c4dea)",
        button_primary_background_fill_hover_dark="linear-gradient(135deg, #7173f0, #a27cf0)",
        button_primary_text_color="#ffffff",
        button_secondary_background_fill="#ffffff",
        button_secondary_background_fill_dark="#141a29",
        button_secondary_background_fill_hover="#eef1f8",
        button_secondary_background_fill_hover_dark="#1a2133",
        button_secondary_border_color="#e5e7ef",
        button_secondary_border_color_dark="#232b3e",
        button_secondary_text_color="#111827",
        button_secondary_text_color_dark="#e8ecf5",
        button_cancel_background_fill="#fdecec",
        button_cancel_background_fill_dark="#321616",
        button_cancel_background_fill_hover="#fbdada",
        button_cancel_background_fill_hover_dark="#3d1b1b",
        button_cancel_border_color="#f5c2c2",
        button_cancel_border_color_dark="#5a2424",
        button_cancel_text_color="#ef4444",
        button_cancel_text_color_dark="#f87171",
        button_large_radius="11px",
        button_small_radius="11px",
    )


# colours and page background: the panel and the login page (which gets no app CSS, see LOGIN_HEAD)
BASE_CSS = """
:root {
  --pvc-bg: #f4f6fb; --pvc-bg-2: #eef1f8; --pvc-card: #ffffff; --pvc-text: #111827; --pvc-muted: #6b7280;
  --pvc-line: #e5e7ef; --pvc-accent: #5b5bf0; --pvc-accent-2: #8b5cf6; --pvc-accent-soft: #ecebff;
  --pvc-good: #10b981; --pvc-good-soft: #e7f8f1; --pvc-warn: #f59e0b; --pvc-warn-soft: #fff5e1;
  --pvc-bad: #ef4444; --pvc-bad-soft: #fdecec; --pvc-term-bg: #0d1117; --pvc-term-text: #d1d9e6;
}
.dark {
  --pvc-bg: #0b0e17; --pvc-bg-2: #0f1320; --pvc-card: #141a29; --pvc-text: #e8ecf5; --pvc-muted: #8b95ab;
  --pvc-line: #232b3e; --pvc-accent: #8183ff; --pvc-accent-2: #b18cff; --pvc-accent-soft: #1f2245;
  --pvc-good: #34d399; --pvc-good-soft: #0f2a22; --pvc-warn: #fbbf24; --pvc-warn-soft: #2d2410;
  --pvc-bad: #f87171; --pvc-bad-soft: #321616; --pvc-term-bg: #090c13;
}
body, gradio-app {
  background:
    radial-gradient(1200px 500px at 10% -10%, color-mix(in srgb, var(--pvc-accent) 14%, transparent), transparent 60%),
    radial-gradient(900px 400px at 100% 0%, color-mix(in srgb, var(--pvc-accent-2) 12%, transparent), transparent 60%),
    var(--pvc-bg) !important;
}
.gradio-container { max-width: 100% !important; width: 100% !important; margin: 0 !important; padding: 0 24px !important; background: transparent !important; }
"""

# Gradio serves the CSS and head of an app only after the login, so the login form gets these rules
# through the page HTML itself (create_server); everything is scoped to the form with the password
LOGIN_CSS = """
/* login page: Gradio's own form (PVC_UI_AUTH), restyled as one card in the middle of the page */
.wrap.min-h-screen:has(input[type=password]) {
  background: transparent !important; margin: 0 !important; min-height: calc(100vh - 40px) !important;
  justify-content: center !important;
}
.wrap.min-h-screen:has(input[type=password]) > .column {
  flex: none !important; width: min(400px, 100%) !important; min-width: 0 !important; gap: 14px !important;
  padding: 28px 24px 24px !important; border-radius: 20px !important;
  background: var(--pvc-card) !important; border: 1px solid var(--pvc-line) !important;
  box-shadow: 0 1px 2px rgba(17, 24, 39, .04), 0 16px 40px rgba(17, 24, 39, .10) !important;
}
.wrap.min-h-screen:has(input[type=password]) > .column::before {
  content: "Piper Voice Cloner"; display: block; padding-top: 62px; text-align: center;
  background: url(/favicon.svg) center top / 52px no-repeat;
  font-size: 1.25rem; font-weight: 700; letter-spacing: -0.01em; color: var(--pvc-text);
}
.wrap.min-h-screen:has(input[type=password]) h2 {
  margin: -8px 0 6px !important; text-align: center; font-size: .95rem !important; font-weight: 500 !important;
  color: var(--pvc-muted) !important;
}
.wrap.min-h-screen:has(input[type=password]) .form {
  background: transparent !important; border: 0 !important; box-shadow: none !important; gap: 12px !important;
}
.wrap.min-h-screen:has(input[type=password]) .form > .block {
  background: transparent !important; border: 0 !important; box-shadow: none !important; padding: 0 !important;
}
.wrap.min-h-screen:has(input[type=password]) .form input { border-radius: 12px !important; }
"""

# what create_server puts into the page HTML, before Gradio knows whether the user is logged in
LOGIN_HEAD = f"{ICON_LINKS}<style>{BASE_CSS}{LOGIN_CSS}</style>"

PANEL_CSS = """
footer { display: none !important; }

/* top bar */
.pvc-topbar { display: flex; justify-content: space-between; align-items: center; gap: 16px; flex-wrap: wrap; padding: 6px 2px 4px; }
.pvc-brand { display: flex; align-items: center; gap: 14px; }
.pvc-logo {
  width: 46px; height: 46px; border-radius: 50%; display: grid; place-items: center; flex: none;
  background: linear-gradient(135deg, #f59e0b, #ef4f3c);
  box-shadow: 0 6px 18px rgba(239, 79, 60, .35);
}
.pvc-logo svg { width: 30px; height: 30px; stroke: #fff; stroke-width: 2.4; stroke-linecap: round; }
.pvc-brand h1 { margin: 0; font-size: 1.35rem; font-weight: 700; letter-spacing: -0.01em; color: var(--pvc-text); }
.pvc-brand p { margin: 0; color: var(--pvc-muted); }
.pvc-top-right { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.pvc-guide {
  display: inline-flex; align-items: center; gap: 7px; padding: 7px 14px; border-radius: 999px;
  background: var(--pvc-card); border: 1px solid var(--pvc-line); color: var(--pvc-text) !important;
  font-weight: 600; font-size: .88rem; text-decoration: none !important; transition: border-color .15s, color .15s;
}
.pvc-guide:hover { border-color: var(--pvc-accent); color: var(--pvc-accent) !important; }
.pvc-guide svg { color: var(--pvc-accent); }
.pvc-lang { display: inline-flex; padding: 3px; border-radius: 999px; background: var(--pvc-card); border: 1px solid var(--pvc-line); }
.pvc-lang a {
  font-size: .78rem; font-weight: 700; letter-spacing: .04em; padding: 4px 10px; border-radius: 999px;
  color: var(--pvc-muted); text-decoration: none; text-transform: uppercase;
}
.pvc-lang a.on { background: linear-gradient(135deg, var(--pvc-accent), var(--pvc-accent-2)); color: #fff; }

/* status pill (job) */
.pvc-status {
  display: inline-flex; align-items: center; gap: 8px; padding: 6px 14px; border-radius: 999px;
  font-weight: 600; font-size: .85rem; background: var(--pvc-card); border: 1px solid var(--pvc-line); color: var(--pvc-muted);
}
.pvc-status .dot { width: 9px; height: 9px; border-radius: 50%; background: var(--pvc-muted); flex: none; }
.pvc-status.running { color: var(--pvc-good); border-color: color-mix(in srgb, var(--pvc-good) 40%, transparent); background: var(--pvc-good-soft); }
.pvc-status.running .dot { background: var(--pvc-good); animation: pvc-pulse 1.6s infinite; }
.pvc-status.ok { color: var(--pvc-good); }
.pvc-status.ok .dot { background: var(--pvc-good); }
.pvc-status.failed { color: var(--pvc-bad); background: var(--pvc-bad-soft); border-color: color-mix(in srgb, var(--pvc-bad) 35%, transparent); }
.pvc-status.failed .dot { background: var(--pvc-bad); }
.pvc-status.stopped { color: var(--pvc-warn); background: var(--pvc-warn-soft); }
.pvc-status.stopped .dot { background: var(--pvc-warn); }
@keyframes pvc-pulse {
  0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--pvc-good) 60%, transparent); }
  70% { box-shadow: 0 0 0 9px transparent; }
  100% { box-shadow: 0 0 0 0 transparent; }
}

/* GPU machine power (Home Assistant), in the top bar */
.pvc-machine {
  display: inline-flex; align-items: center; gap: 8px; padding: 6px 14px; border-radius: 999px; cursor: pointer;
  font: inherit; font-weight: 600; font-size: .85rem; background: var(--pvc-card); border: 1px solid var(--pvc-line);
  color: var(--pvc-muted); transition: border-color .15s, color .15s;
}
.pvc-machine svg { width: 15px; height: 15px; flex: none; }
.pvc-machine:hover { border-color: var(--pvc-accent); color: var(--pvc-accent); }
.pvc-listen-head { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px; }
.pvc-listen-head > div { color: var(--pvc-text); }
.pvc-chart, .pvc-chart-dialog {
  --c-mos: #1baf7a; --c-vmel: #2a78d6; --c-tmel: #eb6834;
}
.dark .pvc-chart, .dark .pvc-chart-dialog, .dark.pvc-chart-dialog { --c-mos: #199e70; --c-vmel: #3987e5; --c-tmel: #d95926; }
.pvc-chart { position: relative; cursor: zoom-in; padding: 12px 14px 8px; border: 1px solid var(--pvc-line);
  border-radius: 16px; background: var(--pvc-card); }
.pvc-chart:focus-visible { outline: 2px solid var(--pvc-accent); }
.pvc-chart-view, .pvc-chart-big { position: relative; }
.pvc-chart-legend { display: flex; flex-wrap: wrap; gap: 4px 14px; align-items: center; font-size: .82rem; color: var(--pvc-muted); margin-bottom: 4px; }
.pvc-chart-legend .hint { margin-left: auto; }
.pvc-chart .key, .pvc-chart-dialog .key { display: inline-flex; align-items: center; gap: 6px; }
.pvc-chart .key::before, .pvc-chart-dialog .key::before { content: ""; width: 14px; height: 2px; border-radius: 2px; background: currentColor; }
.key.mos::before { background: var(--c-mos) !important; } .key.vmel::before { background: var(--c-vmel) !important; }
.key.tmel::before { background: var(--c-tmel) !important; }
.pvc-chart-panel .title { font-size: .78rem; font-weight: 600; color: var(--pvc-text); margin-top: 4px; }
.pvc-chart-panel svg { display: block; overflow: visible; touch-action: none; }
.pvc-chart-panel .grid { stroke: var(--pvc-line); stroke-width: 1; }
.pvc-chart-panel .axis { fill: var(--pvc-muted); font-size: 10px; }
.pvc-chart-panel .line { fill: none; stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
.pvc-chart-panel .line.mos { stroke: var(--c-mos); } .pvc-chart-panel .line.vmel { stroke: var(--c-vmel); }
.pvc-chart-panel .line.tmel { stroke: var(--c-tmel); }
.pvc-chart-panel .best { stroke: var(--pvc-card); stroke-width: 2; }
.pvc-chart-panel .best.mos { fill: var(--c-mos); } .pvc-chart-panel .best.vmel { fill: var(--c-vmel); }
.pvc-chart-panel .cross { stroke: var(--pvc-muted); stroke-width: 1; stroke-dasharray: 3 3; }
.pvc-chart-panel .pin { stroke: var(--pvc-accent); stroke-width: 1.5; }
.pvc-chart-panel .select { fill: color-mix(in srgb, var(--pvc-accent) 18%, transparent); }
.pvc-chart-tip { display: none; position: absolute; z-index: 5; pointer-events: none; min-width: 150px;
  padding: 8px 10px; border-radius: 10px; background: var(--pvc-card); border: 1px solid var(--pvc-line);
  box-shadow: 0 8px 24px rgba(0, 0, 0, .18); font-size: .82rem; color: var(--pvc-text); }
.pvc-chart-tip .head { color: var(--pvc-muted); margin-bottom: 4px; }
.pvc-chart-tip .row, .pvc-chart-side .row { display: flex; align-items: center; gap: 8px; }
.pvc-chart-tip .row b, .pvc-chart-side .row b { min-width: 52px; font-variant-numeric: tabular-nums; }
.pvc-chart-tip .row span:last-child, .pvc-chart-side .row span:last-child { color: var(--pvc-muted); }
.pvc-chart-tip .row .key::before, .pvc-chart-side .row .key::before { width: 12px; }
.pvc-chart-empty { color: var(--pvc-muted); font-size: .9rem; padding: 6px 0; }
.pvc-chart-dialog { width: 96vw; height: 92vh; max-width: none; max-height: none; padding: 0; border: 1px solid var(--pvc-line);
  border-radius: 18px; background: var(--pvc-card); color: var(--pvc-text); overflow: hidden; }
.pvc-chart-dialog::backdrop { background: rgba(0, 0, 0, .55); }
.pvc-chart-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 16px; padding: 12px 18px; border-bottom: 1px solid var(--pvc-line); }
.pvc-chart-bar .name { font-size: 1.05rem; margin-right: auto; }
.pvc-chart-bar label { color: var(--pvc-muted); font-size: .88rem; }
.pvc-chart-bar input { width: 90px; padding: 5px 8px; border-radius: 8px; border: 1px solid var(--pvc-line); background: var(--pvc-bg-2); color: var(--pvc-text); font: inherit; }
.pvc-chart-bar button { font: inherit; font-weight: 600; padding: 6px 14px; border-radius: 10px; cursor: pointer;
  border: 1px solid var(--pvc-line); background: var(--pvc-card); color: var(--pvc-text); }
.pvc-chart-body { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 18px; padding: 14px 18px; height: calc(100% - 60px); }
.pvc-chart-big { height: 100%; cursor: crosshair; }
.pvc-chart-side { overflow-y: auto; font-size: .88rem; line-height: 1.5; }
.pvc-chart-side h4 { margin: 0 0 6px; }
.pvc-chart-side .muted { color: var(--pvc-muted); }
.pvc-chart-side .bests { margin: 12px 0; padding: 10px 12px; border-radius: 12px; background: var(--pvc-accent-soft); }
.pvc-chart-side .bests p, .pvc-chart-side .help p { margin: 0 0 8px; }
@media (max-width: 900px) { .pvc-chart-body { grid-template-columns: 1fr; overflow-y: auto; } .pvc-chart-big { height: 60vh; } }
.pvc-ready {
  border: 1px solid var(--pvc-line); border-radius: 16px; background: var(--pvc-card); padding: 14px 18px; margin: 8px 0;
}

/* rating of the recordings: four numbers and what they mean */
.pvc-score { border: 1px solid var(--pvc-line); border-radius: 16px; background: var(--pvc-card); padding: 14px 18px; margin: 8px 0; }
.pvc-score-tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 10px; margin-bottom: 10px; }
.pvc-score-tile { border-radius: 12px; background: var(--pvc-bg-2); padding: 10px 12px; }
.pvc-score-tile b { display: block; font-size: 1.35rem; font-weight: 700; color: var(--pvc-text); font-variant-numeric: tabular-nums; }
.pvc-score-tile span { font-size: .8rem; color: var(--pvc-muted); }
.pvc-score p { margin: 0; color: var(--pvc-text); }
.pvc-ready-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 12px; }
.pvc-ready-head b { font-size: 1rem; color: var(--pvc-text); }
.pvc-ready-head span { color: var(--pvc-text); }
.pvc-ready-head small { color: var(--pvc-muted); margin-left: auto; }
.pvc-ready.ready .pvc-ready-head span { color: var(--pvc-good); font-weight: 600; }
.pvc-ready.manual .pvc-ready-head span, .pvc-ready.failed .pvc-ready-head span { color: var(--pvc-bad); }
.pvc-ready ul { list-style: none; margin: 10px 0 0; padding: 0; display: grid; gap: 2px; }
.pvc-ready li {
  display: grid; grid-template-columns: 24px minmax(150px, 260px) 1fr; gap: 10px; align-items: baseline;
  padding: 5px 0; border-top: 1px solid var(--pvc-line);
}
.pvc-ready li .mark { font-weight: 800; text-align: center; }
.pvc-ready li.ok .mark { color: var(--pvc-good); }
.pvc-ready li.todo .mark { color: var(--pvc-accent); }
.pvc-ready li.manual .mark, .pvc-ready li.warn .mark { color: var(--pvc-warn); }
.pvc-ready li .name { font-weight: 600; color: var(--pvc-text); }
.pvc-ready li .text { color: var(--pvc-muted); overflow-wrap: anywhere; }
.pvc-ready li code, .pvc-ready-login code {
  display: block; margin-top: 4px; padding: 6px 10px; border-radius: 8px; background: var(--pvc-term-bg);
  color: var(--pvc-term-text); font-size: .85rem; user-select: all;
}
.pvc-ready-login { margin-top: 10px; color: var(--pvc-muted); }
.pvc-ready-login summary { cursor: pointer; }
@media (max-width: 720px) { .pvc-ready li { grid-template-columns: 24px 1fr; } .pvc-ready li .text { grid-column: 2; } }
.pvc-ask {
  width: min(480px, calc(100vw - 32px)); padding: 22px 24px 18px; border: 1px solid var(--pvc-line);
  border-radius: 18px; background: var(--pvc-card); color: var(--pvc-text); box-shadow: 0 24px 60px rgba(0, 0, 0, .25);
}
.pvc-ask::backdrop { background: rgba(0, 0, 0, .45); }
.pvc-ask-text { margin: 0 0 18px; line-height: 1.5; font-size: .95rem; white-space: pre-line; }
.pvc-ask-actions { display: flex; justify-content: flex-end; gap: 10px; }
.pvc-ask button {
  font: inherit; font-weight: 600; padding: 9px 18px; border-radius: 12px; cursor: pointer;
  border: 1px solid var(--pvc-line); background: var(--pvc-card); color: var(--pvc-text);
}
.pvc-ask button:hover { box-shadow: 0 4px 14px rgba(0, 0, 0, .12); }
.pvc-ask button.pvc-ask-ok { border: none; color: #fff; background: linear-gradient(135deg, var(--pvc-accent), var(--pvc-accent-2)); }
.pvc-ask button.pvc-ask-ok.danger {
  color: var(--pvc-bad); background: var(--pvc-bad-soft); border: 1px solid color-mix(in srgb, var(--pvc-bad) 35%, transparent);
}
.pvc-machine.wait { cursor: default; }
.pvc-machine.wait:hover { border-color: var(--pvc-line); color: var(--pvc-muted); }
.pvc-machine.on { color: var(--pvc-good); border-color: color-mix(in srgb, var(--pvc-good) 40%, transparent); background: var(--pvc-good-soft); }
.pvc-machine.pending { color: var(--pvc-warn); background: var(--pvc-warn-soft); }
.pvc-machine.pending svg { animation: pvc-blink 1.4s infinite; }
.pvc-machine.unknown { color: var(--pvc-bad); background: var(--pvc-bad-soft); }
.pvc-status.checking { color: var(--pvc-warn); background: var(--pvc-warn-soft); }
.pvc-status.checking .dot { background: var(--pvc-warn); animation: pvc-blink 1.4s infinite; }
@keyframes pvc-blink { 50% { opacity: .35; } }

/* stepper */
.pvc-steps { display: flex; flex-wrap: wrap; gap: 10px; padding: 2px 0 4px; }
.pvc-step {
  display: flex; align-items: center; gap: 10px; padding: 9px 16px 9px 9px; border-radius: 999px;
  background: var(--pvc-card); border: 1px solid var(--pvc-line); color: var(--pvc-muted);
  font: inherit; font-weight: 600; font-size: .9rem; white-space: nowrap; cursor: pointer;
  transition: border-color .15s, box-shadow .15s, transform .15s;
}
.pvc-step:hover { border-color: color-mix(in srgb, var(--pvc-accent) 45%, transparent); transform: translateY(-1px); }
.pvc-step b {
  width: 26px; height: 26px; border-radius: 50%; display: grid; place-items: center; flex: none;
  background: var(--pvc-bg-2); color: var(--pvc-muted); font-size: .8rem;
}
.pvc-step small { color: var(--pvc-muted); font-weight: 500; font-size: .78rem; }
.pvc-step.done { color: var(--pvc-good); }
.pvc-step.done b { background: var(--pvc-good); color: #fff; }
.pvc-step.next b { box-shadow: inset 0 0 0 2px var(--pvc-accent); color: var(--pvc-accent); }
.pvc-step.current {
  color: var(--pvc-accent); border-color: var(--pvc-accent);
  background: color-mix(in srgb, var(--pvc-accent) 10%, var(--pvc-card));
  box-shadow: 0 6px 18px color-mix(in srgb, var(--pvc-accent) 22%, transparent);
}
.pvc-step.current:not(.done) b { background: linear-gradient(135deg, var(--pvc-accent), var(--pvc-accent-2)); color: #fff; box-shadow: none; }
.pvc-steps-gap { flex: 0 0 8px; }
.pvc-step.tool b { font-size: 1.05rem; }
#pvc-tabs .tab-wrapper { display: none !important; }
/* "New voice" accordion: the bottom strip of the voice card, not a separate black box */
.gr-group .block.pvc-new {
  border: 0 !important; border-top: 1px solid var(--pvc-line) !important; border-radius: 0 0 18px 18px !important;
  box-shadow: none !important; padding: 0 !important; background: var(--pvc-card) !important;
}
.pvc-new > .label-wrap {
  padding: 13px 18px !important; margin: 0 !important; border-radius: 0 0 18px 18px;
  color: var(--pvc-accent) !important; font-weight: 600 !important; transition: background .15s;
}
.pvc-new > .label-wrap.open { border-radius: 0; border-bottom: 1px dashed var(--pvc-line); }
.pvc-new > .label-wrap:hover { background: color-mix(in srgb, var(--pvc-accent) 7%, var(--pvc-card)); }
.pvc-new > .label-wrap .icon { color: var(--pvc-accent) !important; }
.pvc-new > :not(.label-wrap) { padding: 4px 14px 14px; }
.pvc-empty { color: var(--pvc-muted); text-align: center; padding: 14px 8px; }

/* cards: Gradio groups look like the wake word panel cards (Gradio 6 drops elem_classes on
   groups, so the group classes are targeted directly) */
.gr-group {
  background: var(--pvc-card) !important; border: 1px solid var(--pvc-line) !important;
  border-radius: 18px !important; overflow: hidden;
  box-shadow: 0 1px 2px rgba(17, 24, 39, .04), 0 8px 24px rgba(17, 24, 39, .06) !important;
}
.gr-group .styler, .gr-group .block, .gr-group .html-container { background: var(--pvc-card) !important; }

/* live card */
.pvc-live-head { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }
.pvc-label { font-size: .78rem; text-transform: uppercase; letter-spacing: .06em; color: var(--pvc-muted); font-weight: 600; margin-bottom: 6px; }
.pvc-stage { font-size: 1.15rem; font-weight: 700; color: var(--pvc-text); }
.pvc-progress { margin: 14px 0 2px; }
.pvc-progress-bar { height: 8px; border-radius: 999px; background: var(--pvc-bg-2); overflow: hidden; }
.pvc-progress-bar span {
  display: block; height: 100%; border-radius: 999px; transition: width .6s ease;
  background: linear-gradient(90deg, var(--pvc-accent), var(--pvc-accent-2));
}
.pvc-progress-text {
  display: flex; justify-content: space-between; margin-top: 6px; font-size: .82rem;
  color: var(--pvc-muted); font-variant-numeric: tabular-nums;
}
.pvc-progress-text b { color: var(--pvc-accent); }
.pvc-elapsed { text-align: right; font-variant-numeric: tabular-nums; font-weight: 600; color: var(--pvc-text); }
.pvc-gpu { margin-top: 16px; padding-top: 14px; border-top: 1px solid var(--pvc-line); }
.pvc-gpu-name { color: var(--pvc-muted); font-size: .9rem; margin-bottom: 12px; }
.pvc-gpu-name strong { color: var(--pvc-text); }
.pvc-meters { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
.pvc-meter { display: flex; flex-direction: column; align-items: center; gap: 6px; font-size: .78rem; color: var(--pvc-muted); font-weight: 600; text-align: center; }
.pvc-ring {
  --value: 0; --color: var(--pvc-accent);
  width: 74px; height: 74px; border-radius: 50%; display: grid; place-items: center;
  background: conic-gradient(var(--color) calc(var(--value) * 1%), var(--pvc-bg-2) 0);
}
.pvc-ring span {
  width: 58px; height: 58px; border-radius: 50%; background: var(--pvc-card); display: grid; place-items: center;
  font-size: .8rem; font-weight: 700; color: var(--pvc-text); font-variant-numeric: tabular-nums;
}

/* terminal log */
.pvc-log textarea {
  font: 12px/1.55 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace !important;
  background: var(--pvc-term-bg) !important; color: var(--pvc-term-text) !important;
  border-radius: 12px !important; border: none !important;
}

/* the buttons share the row of the "Log" badge: their block takes no height of its own */
.gr-group:has(.pvc-log-tools), .styler:has(.pvc-log-tools) { position: relative; }
.block:has(.pvc-log-tools), .html-container:has(.pvc-log-tools) {
  height: 0 !important; min-height: 0 !important; padding: 0 !important; margin: 0; border: 0; overflow: visible;
}
.pvc-log-tools { position: absolute; top: 10px; right: 12px; z-index: 3; display: flex; align-items: center; gap: 8px; }
.pvc-queue { margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--pvc-line); }
.pvc-queue ol { list-style: none; margin: 8px 0 0; padding: 0; display: grid; gap: 4px; }
.pvc-queue li { display: flex; align-items: center; gap: 8px; margin: 0; color: var(--pvc-muted); font-size: .85rem; }
.pvc-queue li span { width: 1.1em; text-align: center; }
.pvc-queue li b { font-weight: 600; }
.pvc-queue li em { margin-left: auto; font-style: normal; font-size: .78rem; }
.pvc-queue li.now, .pvc-queue li.done { color: var(--pvc-text); }
.pvc-queue li.now span, .pvc-queue li.now em { color: var(--pvc-accent); }
.pvc-queue li.done span { color: var(--pvc-good); }
.pvc-queue li.failed, .pvc-queue li.stopped { color: var(--pvc-bad); }
.pvc-log-tools button { height: 30px; margin: 0; line-height: 1; display: inline-flex; align-items: center; }
.pvc-log label > span { margin-bottom: 6px; }
.pvc-log-tools button, .pvc-log-bar button {
  font: inherit; font-size: .82rem; font-weight: 600; padding: 4px 12px; border-radius: 10px; cursor: pointer;
  border: 1px solid var(--pvc-line); background: var(--pvc-card); color: var(--pvc-text);
}
.pvc-log-tools button:hover, .pvc-log-bar button:hover { border-color: color-mix(in srgb, var(--pvc-accent) 45%, transparent); }
.pvc-log-dialog { width: 94vw; height: 88vh; max-width: none; max-height: none; padding: 0; border: 1px solid var(--pvc-line);
  border-radius: 18px; background: var(--pvc-card); color: var(--pvc-text); overflow: hidden; }
.pvc-log-dialog[open] { display: flex; flex-direction: column; }
.pvc-log-dialog::backdrop { background: rgba(0, 0, 0, .55); }
.pvc-log-bar { display: flex; align-items: center; gap: 10px; padding: 12px 18px; border-bottom: 1px solid var(--pvc-line); }
.pvc-log-bar .name { font-size: 1.05rem; margin-right: auto; }
.pvc-log-bar .note { color: var(--pvc-good); font-size: .85rem; }
.pvc-log-bar .note.bad { color: var(--pvc-bad); }
.pvc-log-full { flex: 1; margin: 0; padding: 14px 18px; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere;
  font: 12.5px/1.55 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; background: var(--pvc-term-bg); color: var(--pvc-term-text); }
@media (max-width: 720px) { .pvc-log-dialog { width: calc(100vw - 16px); height: 90vh; } }

/* help text: Gradio puts elem_classes on the block and on the inner prose - style the block only */
.block.pvc-help {
  border: 1px solid color-mix(in srgb, var(--pvc-accent) 25%, transparent) !important;
  background: var(--pvc-accent-soft) !important; border-radius: 14px !important; padding: 10px 16px !important;
}
.prose.pvc-help { border: none !important; background: transparent !important; padding: 0 !important; }
.pvc-section-title { margin-top: 10px !important; }

/* step header with the "?" explanation */
.pvc-step-info { margin: 4px 0 2px; }
.pvc-step-info summary {
  list-style: none; cursor: pointer; display: flex; align-items: center; gap: 10px;
  font-size: 1.05rem; font-weight: 650; color: var(--pvc-text);
}
.pvc-step-info summary::-webkit-details-marker { display: none; }
.pvc-step-info .num {
  width: 26px; height: 26px; border-radius: 8px; display: grid; place-items: center; font-size: .8rem;
  background: var(--pvc-accent-soft); color: var(--pvc-accent); flex: none;
}
.pvc-step-info .q {
  width: 24px; height: 24px; border-radius: 50%; display: grid; place-items: center; flex: none;
  font-size: .82rem; font-weight: 800; color: var(--pvc-accent); background: var(--pvc-accent-soft);
  border: 1px solid color-mix(in srgb, var(--pvc-accent) 35%, transparent); transition: transform .15s, background .15s;
}
.pvc-step-info summary:hover .q { transform: scale(1.08); }
.pvc-step-info[open] .q { background: linear-gradient(135deg, var(--pvc-accent), var(--pvc-accent-2)); color: #fff; }
.pvc-step-info .body {
  margin-top: 10px; padding: 12px 16px; border-radius: 14px; background: var(--pvc-card);
  border: 1px solid var(--pvc-line); color: var(--pvc-text); font-size: .92rem;
}
.pvc-step-info .body b { display: block; margin-bottom: 6px; color: var(--pvc-accent); }
.pvc-step-info ul { margin: 0; padding-left: 18px; }
.pvc-step-info li { margin: 4px 0; line-height: 1.5; }
.pvc-step-info code { font-size: .85em; padding: 1px 5px; border-radius: 5px; background: var(--pvc-bg-2); }

/* tabs */
button[role="tab"] { font-weight: 600 !important; }
button[role="tab"][aria-selected="true"] { color: var(--pvc-accent) !important; }
"""
CSS = BASE_CSS + PANEL_CSS


def bold_html(text: str) -> str:
    """Escaped text with **bold** parts (for the panel's own texts shown as HTML)."""
    return _bold(text)


def _bold(text: str) -> str:
    """The texts use **bold** markdown; render it inside small HTML snippets."""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html.escape(text))


def lang_switch(current: str, languages: list[str]) -> str:
    links = "".join(
        f'<a href="../{code}/" class="{"on" if code == current else ""}" '
        f"onclick=\"try{{localStorage.setItem('pvc-lang','{code}')}}catch(e){{}}\">{code}</a>"
        for code in languages
    )
    return f'<div class="pvc-lang" role="group" aria-label="Language">{links}</div>'


def guide_link(current: str, label: str) -> str:
    """Opens the step-by-step guide (with the FAQ) in a new tab."""
    return (
        f'<a class="pvc-guide" href="../guide/{html.escape(current)}" target="_blank" rel="noopener">'
        f"{BOOK_SVG}<span>{html.escape(label)}</span></a>"
    )


CHART_SVG = (
    '<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 3v18h18"/>'
    '<path d="m7 15 4-4 3 3 6-7"/></svg>'
)


def tensorboard_link(label: str, href: str = "", port: int = 6006) -> str:
    """TensorBoard in a new tab: a fixed address, or the host this page came from with ``port``
    (the panel on the machine does not know under which name or IP the browser reached it)."""
    if href:
        target = f'href="{html.escape(href)}"'
    else:
        target = f"href=\"#\" onclick=\"this.href=location.protocol+'//'+location.hostname+':{int(port)}/'\""
    return (
        f'<a class="pvc-guide pvc-tb" {target} target="_blank" rel="noopener">'
        f"{CHART_SVG}<span>{html.escape(label)} ↗</span></a>"
    )


def chart_html(payload: dict) -> str:
    """The training chart (CHART_JS draws it from the JSON in data-chart); empty payload = nothing."""
    if not payload:
        return ""
    data = html.escape(json.dumps(payload, ensure_ascii=False), quote=True)
    label = html.escape(payload["t"]["open"])
    return (
        f'<div class="pvc-chart" data-chart="{data}" role="button" tabindex="0" title="{label}" '
        f'aria-label="{label}"><div class="pvc-chart-view"></div></div>'
    )


# js_on_load of the chart gr.HTML: draws two small multiples sharing the epoch axis (quality; both
# mel errors - two scales are never put on one axis), a crosshair with one tooltip for every series,
# and on click a full-screen window: drag over a chart to zoom into those epochs, click to pick an
# epoch, "from/to" fields, the meaning of the three values. Re-drawn when the data-chart changes.
CHART_JS = r"""
const NS = "http://www.w3.org/2000/svg";
let last = "", payload = null, dialog = null, range = null, pinned = null;
const node = (tag, attrs = {}, parent = null, svg = true) => {
  const n = svg ? document.createElementNS(NS, tag) : document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (parent) parent.appendChild(n);
  return n;
};
const text = (tag, value, cls, parent) => { const n = node(tag, cls ? {class: cls} : {}, parent, false); n.textContent = value; return n; };
const fmt = (v, digits) => (v === null || v === undefined ? "—" : v.toFixed(digits));
const SERIES = [
  {idx: 1, key: "val_mos", cls: "mos", digits: 2, panel: 0},
  {idx: 2, key: "val_mel", cls: "vmel", digits: 3, panel: 1},
  {idx: 3, key: "train_mel", cls: "tmel", digits: 3, panel: 1},
];
function ticks(lo, hi, count) {
  const span = hi - lo || 1, raw = span / count, mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => span / s <= count) || mag * 10;
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(10));
  return out;
}
function draw(container, big) {
  container.textContent = "";
  const t = payload.t, rows = payload.rows;
  if (!rows.length) { text("div", t.none, "pvc-chart-empty", container); return; }
  const lo = range ? range[0] : rows[0][0], hi = range ? range[1] : rows[rows.length - 1][0];
  const shown = rows.filter((r) => r[0] >= lo && r[0] <= hi);
  const legend = node("div", {class: "pvc-chart-legend"}, container, false);
  for (const s of SERIES) { const item = node("span", {class: "key " + s.cls}, legend, false); item.textContent = t[s.key]; }
  if (!big) text("span", t.open, "hint", legend);
  const tip = node("div", {class: "pvc-chart-tip"}, container, false);
  const panels = [];
  const width = Math.max(260, container.clientWidth || 600);
  const heights = big ? [Math.max(160, (container.clientHeight - 90) * 0.42), Math.max(180, (container.clientHeight - 90) * 0.58)] : [92, 112];
  [[t.title_mos, 0], [t.title_mel, 1]].forEach(([title, which]) => {
    const series = SERIES.filter((s) => s.panel === which);
    const wrap = node("div", {class: "pvc-chart-panel"}, container, false);
    text("div", title, "title", wrap);
    const h = heights[which], m = {l: 46, r: 14, t: 6, b: which === 1 ? 22 : 8};
    const svg = node("svg", {width, height: h, viewBox: `0 0 ${width} ${h}`}, wrap);
    const values = shown.flatMap((r) => series.map((s) => r[s.idx])).filter((v) => v !== null);
    let ylo = Math.min(...values), yhi = Math.max(...values);
    if (!values.length) { ylo = 0; yhi = 1; }
    const pad = (yhi - ylo) * 0.08 || 0.1; ylo -= pad; yhi += pad;
    const x = (e) => m.l + ((e - lo) / ((hi - lo) || 1)) * (width - m.l - m.r);
    const y = (v) => m.t + (1 - (v - ylo) / ((yhi - ylo) || 1)) * (h - m.t - m.b);
    const ex = (px) => lo + ((px - m.l) / (width - m.l - m.r)) * ((hi - lo) || 1);
    for (const v of ticks(ylo, yhi, big ? 6 : 3)) {
      node("line", {x1: m.l, x2: width - m.r, y1: y(v), y2: y(v), class: "grid"}, svg);
      const label = node("text", {x: m.l - 6, y: y(v) + 4, class: "axis", "text-anchor": "end"}, svg);
      label.textContent = which === 0 ? v.toFixed(1) : String(+v.toFixed(3));
    }
    if (which === 1) {
      for (const v of ticks(lo, hi, big ? 10 : 5)) {
        if (v !== Math.round(v)) continue;
        const label = node("text", {x: x(v), y: h - 6, class: "axis", "text-anchor": "middle"}, svg);
        label.textContent = String(v);
      }
    }
    for (const s of series) {
      let d = "", open = false;
      for (const r of shown) {
        if (r[s.idx] === null) { open = false; continue; }
        d += (open ? "L" : "M") + x(r[0]).toFixed(1) + "," + y(r[s.idx]).toFixed(1);
        open = true;
      }
      node("path", {d, class: "line " + s.cls}, svg);
    }
    const best = which === 0 ? payload.best.mos : payload.best.mel;
    if (best && best[0] >= lo && best[0] <= hi) {
      node("circle", {cx: x(best[0]), cy: y(best[1]), r: 5, class: "best " + (which === 0 ? "mos" : "vmel")}, svg);
    }
    if (pinned !== null && pinned >= lo && pinned <= hi) node("line", {x1: x(pinned), x2: x(pinned), y1: m.t, y2: h - m.b, class: "pin"}, svg);
    const cross = node("line", {x1: 0, x2: 0, y1: m.t, y2: h - m.b, class: "cross", visibility: "hidden"}, svg);
    const select = node("rect", {y: m.t, height: h - m.t - m.b, class: "select", visibility: "hidden"}, svg);
    panels.push({svg, x, ex, cross, select, m});
  });
  const nearest = (e) => shown.reduce((a, r) => (Math.abs(r[0] - e) < Math.abs(a[0] - e) ? r : a), shown[0]);
  const show = (row, clientX, clientY) => {
    for (const p of panels) { p.cross.setAttribute("x1", p.x(row[0])); p.cross.setAttribute("x2", p.x(row[0])); p.cross.setAttribute("visibility", "visible"); }
    tip.textContent = "";
    text("div", `${t.epoch} ${row[0]}`, "head", tip);
    for (const s of SERIES) {
      const line = node("div", {class: "row"}, tip, false);
      node("span", {class: "key " + s.cls}, line, false);
      text("b", fmt(row[s.idx], s.digits), "", line);
      text("span", t[s.key], "", line);
    }
    const box = container.getBoundingClientRect();
    tip.style.display = "block";
    const left = clientX - box.left + 14;
    tip.style.left = Math.min(left, box.width - tip.offsetWidth - 4) + "px";
    tip.style.top = Math.max(0, clientY - box.top - tip.offsetHeight - 10) + "px";
  };
  const hide = () => { tip.style.display = "none"; for (const p of panels) p.cross.setAttribute("visibility", "hidden"); };
  for (const p of panels) {
    let start = null;
    p.svg.addEventListener("pointermove", (ev) => {
      const px = ev.offsetX;
      show(nearest(p.ex(px)), ev.clientX, ev.clientY);
      if (big && start !== null) {
        p.select.setAttribute("x", Math.min(start, px)); p.select.setAttribute("width", Math.abs(px - start));
        p.select.setAttribute("visibility", "visible");
      }
    });
    p.svg.addEventListener("pointerleave", () => { hide(); if (start !== null) { start = null; p.select.setAttribute("visibility", "hidden"); } });
    if (!big) continue;
    p.svg.addEventListener("pointerdown", (ev) => { start = ev.offsetX; p.svg.setPointerCapture(ev.pointerId); });
    p.svg.addEventListener("pointerup", (ev) => {
      if (start === null) return;
      const a = p.ex(Math.min(start, ev.offsetX)), b = p.ex(Math.max(start, ev.offsetX));
      start = null;
      if (Math.abs(p.x(b) - p.x(a)) > 8) {
        const inside = shown.filter((r) => r[0] >= a && r[0] <= b);
        if (inside.length >= 2) range = [inside[0][0], inside[inside.length - 1][0]];
      } else {
        pinned = nearest(a)[0];
      }
      renderDialog();
    });
  }
}
function makeDialog() {
  dialog = node("dialog", {class: "pvc-chart-dialog"}, null, false);
  dialog.innerHTML = '<div class="pvc-chart-bar"><b class="name"></b><label><span class="from-label"></span> <input type="number" class="from" min="0"></label><label><span class="to-label"></span> <input type="number" class="to" min="0"></label><button type="button" class="all"></button><button type="button" class="close" aria-label="close">✕</button></div><div class="pvc-chart-body"><div class="pvc-chart-big"></div><aside class="pvc-chart-side"><div class="picked"></div><div class="bests"></div><div class="help"></div></aside></div>';
  (document.querySelector("gradio-app") || document.body).append(dialog);
  dialog.querySelector(".close").onclick = () => dialog.close();
  dialog.querySelector(".all").onclick = () => { range = null; renderDialog(); };
  const typed = () => {
    const a = +dialog.querySelector(".from").value, b = +dialog.querySelector(".to").value;
    if (Number.isFinite(a) && Number.isFinite(b) && b > a) { range = [a, b]; renderDialog(); }
  };
  dialog.querySelector(".from").onchange = typed;
  dialog.querySelector(".to").onchange = typed;
  dialog.addEventListener("click", (ev) => { if (ev.target === dialog) dialog.close(); });
  new ResizeObserver(() => { if (dialog.open) draw(dialog.querySelector(".pvc-chart-big"), true); }).observe(dialog);
}
function renderDialog() {
  const t = payload.t, rows = payload.rows;
  dialog.querySelector(".name").textContent = t.name;
  dialog.querySelector(".from-label").textContent = t.from;
  dialog.querySelector(".to-label").textContent = t.to;
  dialog.querySelector(".all").textContent = t.all;
  if (rows.length) {
    dialog.querySelector(".from").value = range ? range[0] : rows[0][0];
    dialog.querySelector(".to").value = range ? range[1] : rows[rows.length - 1][0];
  }
  const picked = dialog.querySelector(".picked");
  picked.textContent = "";
  const row = pinned === null ? null : rows.find((r) => r[0] === pinned);
  if (row) {
    text("h4", `${t.pinned}: ${row[0]}`, "", picked);
    for (const s of SERIES) {
      const line = node("div", {class: "row"}, picked, false);
      node("span", {class: "key " + s.cls}, line, false);
      text("b", fmt(row[s.idx], s.digits), "", line);
      text("span", t[s.key], "", line);
    }
  } else text("p", t.pick, "muted", picked);
  const bests = dialog.querySelector(".bests");
  bests.textContent = "";
  if (payload.best.mos) text("p", t.best_mos.replace("{value}", payload.best.mos[1].toFixed(2)).replace("{epoch}", payload.best.mos[0]), "", bests);
  if (payload.best.mel) text("p", t.best_mel.replace("{value}", payload.best.mel[1].toFixed(3)).replace("{epoch}", payload.best.mel[0]), "", bests);
  dialog.querySelector(".help").innerHTML = payload.help;  // the panel's own text
  if (!dialog.open) dialog.showModal();
  draw(dialog.querySelector(".pvc-chart-big"), true);
}
function refresh() {
  const host = element.querySelector(".pvc-chart");
  if (!host) return;
  const view = host.querySelector(".pvc-chart-view");
  if (host.dataset.chart === last && view.firstChild) return;
  last = host.dataset.chart;
  payload = JSON.parse(last);
  draw(view, false);
  if (dialog && dialog.open) renderDialog();
}
new MutationObserver(refresh).observe(element, {childList: true, subtree: true, attributes: true, attributeFilter: ["data-chart"]});
new ResizeObserver(() => { const host = element.querySelector(".pvc-chart-view"); if (host && payload) draw(host, false); }).observe(element);
element.addEventListener("click", (ev) => {
  if (!ev.target.closest(".pvc-chart") || !payload) return;
  if (!dialog) makeDialog();
  range = null; pinned = null;
  renderDialog();
});
element.addEventListener("keydown", (ev) => { if ((ev.key === "Enter" || ev.key === " ") && ev.target.closest(".pvc-chart")) { ev.preventDefault(); ev.target.click(); } });
refresh();
"""


def listen_head(summary: str, link: str) -> str:
    return f'<div class="pvc-listen-head"><div>{_bold(summary)}</div>{link}</div>'


def topbar(title: str, subtitle: str, current: str, languages: list[str], guide: str = "") -> str:
    link = guide_link(current, guide) if guide else ""
    return (
        '<div class="pvc-topbar"><div class="pvc-brand">'
        f'<div class="pvc-logo" aria-hidden="true">{CLONE_SVG}</div>'
        f"<div><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p></div></div>"
        f'<div class="pvc-top-right">{link}{lang_switch(current, languages)}</div></div>'
    )


def status_pill(state: str, text: str, title: str = "") -> str:
    """state: idle | running | ok | failed | stopped | checking"""
    tip = f' title="{html.escape(title)}"' if title else ""
    return f'<span class="pvc-status {state}"{tip}><span class="dot"></span><span>{_bold(text)}</span></span>'


READY_MARKS = {"ok": "✓", "todo": "→", "manual": "✋", "warn": "!"}


def checklist_html(
    title: str,
    state: str,
    headline: str,
    rows: list[tuple[str, str, str, str]] = (),
    *,
    checked: str = "",
    login: tuple[str, str, str] | None = None,
) -> str:
    """The machine checklist: state = ready | todo | manual | idle | failed; rows (state, name, text,
    command to run yourself); login = (label, "show", "user:password") folded away."""
    items = "".join(
        f'<li class="{html.escape(row_state)}"><span class="mark">{READY_MARKS.get(row_state, "·")}</span>'
        f'<span class="name">{html.escape(name)}</span><span class="text">{html.escape(text)}'
        + (f"<code>{html.escape(command)}</code>" if command else "")
        + "</span></li>"
        for row_state, name, text, command in rows
    )
    when = f"<small>{html.escape(checked)}</small>" if checked else ""
    secret = ""
    if login and login[2]:
        secret = (
            f'<details class="pvc-ready-login"><summary>{html.escape(login[0])} · {html.escape(login[1])}'
            f"</summary><code>{html.escape(login[2].replace(':', ' / ', 1))}</code></details>"
        )
    return (
        f'<div class="pvc-ready {html.escape(state)}"><div class="pvc-ready-head"><b>{html.escape(title)}</b>'
        f"<span>{_bold(headline)}</span>{when}</div>"
        + (f"<ul>{items}</ul>" if items else "")
        + secret
        + "</div>"
    )


POWER_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" '
    'aria-hidden="true"><path d="M12 3v8"/><path d="M6.3 7.2a8 8 0 1 0 11.4 0"/></svg>'
)
# css look of each machine state (power.machine_state, "checking" before the first answer)
MACHINE_LOOK = {"on": "on", "off": "", "starting": "pending", "stopping": "pending", "checking": "pending",
                "unknown": "unknown", "rejected": "unknown"}  # fmt: skip


def machine_button(kind: str, text: str, title: str, action: str = "", confirm: str = "") -> str:
    """The machine's state; with an action ("on"/"off") a click asks ``confirm`` and switches it (MACHINE_JS)."""
    css = ["pvc-machine", MACHINE_LOOK.get(kind, "unknown")] + ([] if action else ["wait"])
    data = (
        f' data-pvc-machine="{html.escape(action)}" data-confirm="{html.escape(confirm)}"' if action else ""
    )
    return (
        f'<button type="button" class="{" ".join(c for c in css if c)}" title="{html.escape(title)}"{data}>'
        f"{POWER_SVG}<span>{html.escape(text)}</span></button>"
    )


# js_on_load of the top bar gr.HTML: a click on the machine button asks first (pvcAsk), then sends the wanted
# state to Python (the top bar's click event); the listener survives the bar's updates every 2 s
MACHINE_JS = """
element.addEventListener("click", (event) => {
  const button = event.target.closest("[data-pvc-machine]");
  if (!button || !button.dataset.pvcMachine) return;
  const action = button.dataset.pvcMachine;
  window.pvcAsk(button.dataset.confirm, { danger: action === "off" }).then((ok) => {
    if (ok) trigger("click", { machine: action });
  });
});
"""


def log_tools(t: dict) -> str:
    """Buttons above the job log; LOG_JS opens the log in a big window and copies it."""
    labels = {
        k: t[k] for k in ("log", "log_expand", "log_copy", "log_copied", "log_copy_failed", "log_close")
    }
    return (
        f'<div class="pvc-log-tools" data-labels="{html.escape(json.dumps(labels))}">'
        f'<button type="button" class="expand">⤢ {html.escape(t["log_expand"])}</button>'
        f'<button type="button" class="copy">⧉ {html.escape(t["log_copy"])}</button></div>'
    )


# js_on_load of log_tools: "expand" opens a window with the whole log that
# follows the job, "copy" puts it on the clipboard. The panel often runs over plain http on the LAN,
# where navigator.clipboard does not exist, so copying falls back to a selected textarea.
LOG_JS = """
const source = () => document.querySelector(".pvc-log textarea");
const labels = () => JSON.parse(element.querySelector(".pvc-log-tools").dataset.labels);
let dialog = null, timer = null;
async function copyText(value) {
  try {
    if (window.isSecureContext && navigator.clipboard) { await navigator.clipboard.writeText(value); return true; }
  } catch (error) { /* fall back below */ }
  const area = document.createElement("textarea");
  area.value = value;
  area.setAttribute("readonly", "");
  area.style.cssText = "position:fixed;top:0;left:0;opacity:0";
  (dialog && dialog.open ? dialog : document.body).append(area);  // a modal makes the rest inert
  area.select();
  let ok = false;
  try { ok = document.execCommand("copy"); } catch (error) { ok = false; }
  area.remove();
  return ok;
}
function note(target, ok) {
  const t = labels();
  const old = target.textContent;
  target.textContent = ok ? "✓ " + t.log_copied : t.log_copy_failed;
  target.classList.toggle("bad", !ok);
  setTimeout(() => { target.textContent = old; target.classList.remove("bad"); }, 2000);
}
function refresh() {
  const pre = dialog.querySelector(".pvc-log-full");
  const value = (source() || {}).value || "";
  if (pre.textContent === value) return;
  const atEnd = pre.scrollTop + pre.clientHeight >= pre.scrollHeight - 30;
  pre.textContent = value;
  if (atEnd) pre.scrollTop = pre.scrollHeight;
}
function openLog() {
  const t = labels();
  if (!dialog) {
    dialog = document.createElement("dialog");
    dialog.className = "pvc-log-dialog";
    dialog.innerHTML = '<div class="pvc-log-bar"><b class="name"></b><span class="note"></span>'
      + '<button type="button" class="copy"></button><button type="button" class="close"></button></div>'
      + '<pre class="pvc-log-full"></pre>';
    (document.querySelector("gradio-app") || document.body).append(dialog);
    dialog.querySelector(".close").onclick = () => dialog.close();
    dialog.querySelector(".copy").onclick = async () =>
      note(dialog.querySelector(".note"), await copyText(dialog.querySelector(".pvc-log-full").textContent));
    dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });
    dialog.addEventListener("close", () => { clearInterval(timer); timer = null; });
  }
  dialog.querySelector(".name").textContent = t.log;
  dialog.querySelector(".copy").textContent = "⧉ " + t.log_copy;
  dialog.querySelector(".close").textContent = "✕ " + t.log_close;
  dialog.querySelector(".pvc-log-full").textContent = "";
  refresh();
  dialog.showModal();
  const pre = dialog.querySelector(".pvc-log-full");
  pre.scrollTop = pre.scrollHeight;
  timer = setInterval(refresh, 1500);
}
element.addEventListener("click", async (event) => {
  const button = event.target.closest("button");
  if (!button) return;
  if (button.classList.contains("expand")) openLog();
  if (button.classList.contains("copy")) {
    const label = button.textContent;
    const ok = await copyText((source() || {}).value || "");
    const t = labels();
    button.textContent = ok ? "✓ " + t.log_copied : t.log_copy_failed;
    setTimeout(() => { button.textContent = label; }, 2000);
  }
});
"""


def steps_html(
    items: list[tuple[str, str, bool, str]],
    *,
    current: str = "",
    extra: list[tuple[str, str, str]] = (),
    empty: str | None = None,
) -> str:
    """Stepper that is also the navigation: (key, label, done, detail) pills plus extra (key, label, icon)
    pills such as settings; clicking a pill opens its tab (see NAV_JS)."""
    first_open = next((i for i, (_key, _label, done, _detail) in enumerate(items) if not done), None)
    cells = []
    for index, (key, label, done, detail) in enumerate(items):
        css = ["pvc-step"]
        if done:
            css.append("done")
        elif index == first_open and empty is None:
            css.append("next")
        if key == current:
            css.append("current")
        mark = "✓" if done else str(index + 1)
        small = f" <small>{html.escape(detail)}</small>" if detail else ""
        cells.append(
            f'<button type="button" class="{" ".join(css)}" data-pvc-tab="{html.escape(key)}">'
            f"<b>{mark}</b><span>{html.escape(label)}{small}</span></button>"
        )
    if extra:
        cells.append('<span class="pvc-steps-gap"></span>')
    for key, label, icon in extra:
        css = "pvc-step tool current" if key == current else "pvc-step tool"
        cells.append(
            f'<button type="button" class="{css}" data-pvc-tab="{html.escape(key)}">'
            f"<b>{icon}</b><span>{html.escape(label)}</span></button>"
        )
    hint = f'<div class="pvc-empty">{_bold(empty)}</div>' if empty is not None else ""
    return f'<div class="pvc-steps">{"".join(cells)}</div>{hint}'


# js_on_load of the stepper gr.HTML: a click on a pill sends its tab key to Python (its click event),
# which switches the tabs; the listener sits on the component, so it survives value updates
NAV_JS = """
element.addEventListener("click", (event) => {
  const pill = event.target.closest("[data-pvc-tab]");
  if (pill) trigger("click", { tab: pill.dataset.pvcTab });
});
"""


def _inline(text: str) -> str:
    """**bold** and `code` from the texts, everything else escaped."""
    escaped = _bold(text)
    return re.sub(r"`(.+?)`", r"<code>\1</code>", escaped)


def step_info(number: str, title: str, info_title: str, info: str) -> str:
    """Step title with a "?" icon; clicking it unfolds what the step does (no JavaScript)."""
    items = "".join(f"<li>{_inline(line)}</li>" for line in info.splitlines() if line.strip())
    num = f'<span class="num">{html.escape(number)}</span>' if number else ""
    return (
        f'<details class="pvc-step-info"><summary title="{html.escape(info_title)}">'
        f'{num}<span>{html.escape(title)}</span><span class="q" aria-label="{html.escape(info_title)}">?</span>'
        f'</summary><div class="body"><b>{html.escape(info_title)}</b><ul>{items}</ul></div></details>'
    )


def _ring(value: float | None, text: str, label: str, color: str = "var(--pvc-accent)") -> str:
    percent = 0 if value is None else max(0.0, min(100.0, value))
    return (
        f'<div class="pvc-meter"><div class="pvc-ring" style="--value:{percent:.0f};--color:{color}">'
        f"<span>{html.escape(text)}</span></div>{html.escape(label)}</div>"
    )


def temperature_color(celsius: float) -> str:
    if celsius >= 83:
        return "var(--pvc-bad)"
    return "var(--pvc-warn)" if celsius >= 75 else "var(--pvc-good)"


def score_html(tiles: list[tuple[str, str]], text: str) -> str:
    """Rating of the recordings: [(label, value)] as tiles and one explaining sentence (**bold**)."""
    cells = "".join(
        f'<div class="pvc-score-tile"><b>{html.escape(value)}</b><span>{html.escape(label)}</span></div>'
        for label, value in tiles
    )
    return f'<div class="pvc-score"><div class="pvc-score-tiles">{cells}</div><p>{_bold(text)}</p></div>'


def progress_html(
    done: float, total: int, label: str = "", *, unit: str = "", detail: str = "", remaining: str = ""
) -> str:
    percent = min(100.0, 100.0 * done / total) if total else 0.0
    caption = f"{html.escape(label)} · " if label else ""
    counted = f"{int(done)} / {total}" + (f" {html.escape(unit)}" if unit else "")
    more = f" · {html.escape(detail)}" if detail else ""
    left = f" · {html.escape(remaining)}" if remaining else ""
    return (
        f'<div class="pvc-progress"><div class="pvc-progress-bar"><span style="width:{percent:.1f}%"></span></div>'
        f'<div class="pvc-progress-text"><span>{caption}{counted}{more}{left}</span><b>{percent:.0f}%</b></div></div>'
    )


def live_html(
    labels: dict[str, str],
    stage: str,
    elapsed: str,
    gpu: dict | None,
    *,
    stage_label: str | None = None,
    elapsed_label: str | None = None,
    progress: str = "",
    queue: str = "",
) -> str:
    """Stage + elapsed time (+ progress bar), four GPU rings like the wake word panel (+ queue)."""
    if gpu:
        temp = gpu["temperature"]
        rings = "".join(
            [
                _ring(gpu["utilization"], f"{gpu['utilization']:.0f}%", labels["utilization"]),
                _ring(gpu["memory_percent"], f"{gpu['memory_used'] / 1024:.1f} GB", labels["memory"]),
                _ring(temp, f"{temp:.0f}°C", labels["temperature"], temperature_color(temp)),
                _ring(gpu["power_percent"], f"{gpu['power']:.0f} W", labels["power"], "var(--pvc-accent-2)"),
            ]
        )
        name = html.escape(gpu["name"])
    else:
        keys = ("utilization", "memory", "temperature", "power")
        rings = "".join(_ring(None, "—", labels[key]) for key in keys)
        name = html.escape(labels["no_gpu"])
    return (
        '<div class="pvc-live-head">'
        f'<div><div class="pvc-label">{html.escape(stage_label or labels["stage"])}</div>'
        f'<div class="pvc-stage">{_bold(stage)}</div></div>'
        f'<div class="pvc-elapsed"><div class="pvc-label">{html.escape(elapsed_label or labels["elapsed"])}</div>'
        f"{html.escape(elapsed)}</div></div>{progress}"
        f'<div class="pvc-gpu"><div class="pvc-gpu-name">{html.escape(labels["gpu"])} <strong>{name}</strong></div>'
        f'<div class="pvc-meters">{rings}</div></div>{queue}'
    )


QUEUE_ICONS = {"done": "✓", "now": "●", "waiting": "○", "failed": "✕", "stopped": "■"}


def queue_html(labels: dict[str, str], steps: list[tuple[str, str]]) -> str:
    """Where a training queue is: every voice in order with its state, in words and by icon."""
    if not steps:
        return ""
    reached = sum(state != "waiting" for _name, state in steps)
    rows = "".join(
        f'<li class="{state}"><span aria-hidden="true">{QUEUE_ICONS[state]}</span>'
        f"<b>{html.escape(name)}</b><em>{html.escape(labels['queue_' + state])}</em></li>"
        for name, state in steps
    )
    title = labels["queue_title"].format(current=reached, total=len(steps))
    return f'<div class="pvc-queue"><div class="pvc-label">{html.escape(title)}</div><ol>{rows}</ol></div>'
