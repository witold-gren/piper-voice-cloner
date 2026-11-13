"""The step-by-step guide as one HTML page: served by the web UI (/guide/<lang>) and written to docs/.

The Markdown files in docs/ are the only source; the HTML gets a table of contents and the colours
of the web UI (light and dark).
"""

from __future__ import annotations

import base64
import html
from pathlib import Path
import re
import unicodedata

from markdown_it import MarkdownIt

DOCS = Path(__file__).resolve().parents[2] / "docs"
GUIDES = {"en": DOCS / "en" / "guide.md", "pl": DOCS / "pl" / "instrukcja.md"}
TITLES = {"en": "Piper Voice Cloner – guide", "pl": "Piper Voice Cloner – instrukcja"}
TOC_LABEL = {"en": "Contents", "pl": "Spis treści"}
# inline, so the page has its icon also when opened from the disk
ICON = (
    "data:image/svg+xml;base64,"
    + base64.b64encode((Path(__file__).parent / "static" / "favicon.svg").read_bytes()).decode()
)


def slug(text: str) -> str:
    """GitHub-style anchor, so links like #komputer-z-gpu-przez-ssh work on GitHub and here."""
    text = unicodedata.normalize("NFC", text.strip().lower())
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def render(markdown: str) -> tuple[str, list[tuple[int, str, str]]]:
    """(body html, [(level, anchor, title)]) with ids on h2/h3."""
    md = MarkdownIt("commonmark", {"html": False}).enable("table")
    tokens = md.parse(markdown)
    toc: list[tuple[int, str, str]] = []
    seen: dict[str, int] = {}
    for index, token in enumerate(tokens):
        if token.type != "heading_open" or token.tag not in ("h2", "h3"):
            continue
        title = tokens[index + 1].content
        anchor = slug(re.sub(r"`", "", title))
        if anchor in seen:  # same rule as GitHub: -1, -2 ...
            seen[anchor] += 1
            anchor = f"{anchor}-{seen[anchor]}"
        else:
            seen[anchor] = 0
        token.attrSet("id", anchor)
        plain = re.sub(r"`([^`]*)`", r"\1", title)
        toc.append((int(token.tag[1]), anchor, plain))
    return md.renderer.render(tokens, md.options, {}), toc


def page(lang: str) -> str:
    path = GUIDES.get(lang, GUIDES["en"])
    lang = lang if lang in GUIDES else "en"
    if not path.is_file():
        return f"<!doctype html><title>Guide</title><p>{html.escape(str(path))} not found.</p>"
    body, toc = render(path.read_text(encoding="utf-8"))
    links = "".join(
        f'<a href="#{anchor}" class="l{level}">{html.escape(title)}</a>' for level, anchor, title in toc
    )
    return TEMPLATE.format(
        icon=ICON,
        lang=lang,
        title=html.escape(TITLES[lang]),
        toc_label=html.escape(TOC_LABEL[lang]),
        links=links,
        body=body,
    )


def write_all(out_dir: Path = DOCS) -> list[Path]:
    """docs/en/guide.html and docs/pl/instrukcja.html for reading straight from the disk."""
    written = []
    for lang, source in GUIDES.items():
        target = out_dir / lang / source.with_suffix(".html").name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page(lang), encoding="utf-8")
        written.append(target)
    return written


TEMPLATE = """<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="icon" type="image/svg+xml" href="{icon}">
<style>
  :root {{
    --bg: #f4f6fb; --card: #ffffff; --line: #e5e7ef; --text: #111827; --muted: #6b7280;
    --accent: #5b5bf0; --accent-2: #8b5cf6; --code: #eef0f7; --pre: #0d1117; --pre-text: #e6edf3;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #0b0e17; --card: #141a29; --line: #232b3e; --text: #e5e7eb; --muted: #9aa3b5;
      --accent: #8183ff; --accent-2: #b18cff; --code: #1d2436;
    }}
  }}
  * {{ box-sizing: border-box; }}
  html {{ scroll-behavior: smooth; scroll-padding-top: 16px; }}
  body {{
    margin: 0; background: var(--bg); color: var(--text);
    font: 16px/1.65 -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, sans-serif;
  }}
  .layout {{ display: grid; grid-template-columns: 270px minmax(0, 1fr); gap: 32px; max-width: 1180px; margin: 0 auto; padding: 0 16px; }}
  nav {{ position: sticky; top: 0; align-self: start; max-height: 100vh; overflow-y: auto; padding: 28px 0; }}
  nav .brand {{ font-weight: 800; margin: 0 8px 4px; }}
  nav .label {{ color: var(--muted); font-size: .78rem; text-transform: uppercase; letter-spacing: .06em; margin: 0 8px 10px; }}
  nav a {{ display: block; color: var(--muted); text-decoration: none; padding: 4px 8px; border-left: 2px solid transparent; font-size: .92rem; }}
  nav a.l3 {{ padding-left: 20px; font-size: .86rem; }}
  nav a:hover, nav a.active {{ color: var(--accent); border-left-color: var(--accent); }}
  main {{ padding: 28px 0 80px; min-width: 0; }}
  article {{ background: var(--card); border: 1px solid var(--line); border-radius: 18px; padding: 28px 36px; }}
  h1 {{ font-size: 1.9rem; margin: 0 0 12px; }}
  h2 {{ margin-top: 2.2em; padding-top: .4em; border-top: 1px solid var(--line); }}
  h3 {{ margin-top: 1.6em; }}
  a {{ color: var(--accent); }}
  code {{ background: var(--code); padding: 1px 6px; border-radius: 6px; font-size: .88em; }}
  pre {{ background: var(--pre); color: var(--pre-text); padding: 14px 16px; border-radius: 12px; overflow-x: auto; }}
  pre code {{ background: none; padding: 0; color: inherit; }}
  table {{ border-collapse: collapse; width: 100%; display: block; overflow-x: auto; margin: 1em 0; }}
  th, td {{ border: 1px solid var(--line); padding: 7px 10px; text-align: left; vertical-align: top; }}
  th {{ background: var(--code); }}
  blockquote {{ margin: 1em 0; padding: 10px 16px; border-left: 4px solid var(--accent); background: var(--code); border-radius: 0 10px 10px 0; }}
  blockquote p {{ margin: .3em 0; }}
  @media (max-width: 860px) {{
    .layout {{ grid-template-columns: 1fr; gap: 0; }}
    nav {{ position: static; max-height: none; padding-bottom: 0; }}
    nav a {{ display: inline-block; border-left: 0; padding: 2px 6px; }}
    nav a.l3 {{ display: none; }}
    article {{ padding: 20px 18px; }}
  }}
</style>
</head>
<body>
<div class="layout">
<nav id="toc"><div class="brand">Piper Voice Cloner</div><div class="label">{toc_label}</div>{links}</nav>
<main><article>
{body}
</article></main>
</div>
<script>
  const links = [...document.querySelectorAll("#toc a")];
  const heads = links.map((a) => document.getElementById(a.getAttribute("href").slice(1))).filter(Boolean);
  const mark = () => {{
    let current = heads[0];
    for (const h of heads) if (h.getBoundingClientRect().top < 120) current = h;
    links.forEach((a) => a.classList.toggle("active", current && a.getAttribute("href") === "#" + current.id));
  }};
  addEventListener("scroll", mark, {{ passive: true }});
  mark();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    for written in write_all():
        print(written)
