"""Try a grid of backend settings on a few sentences and compare them by ear and by numbers."""

from __future__ import annotations

from dataclasses import dataclass
import html
import itertools
import json
from pathlib import Path
import statistics
from typing import Any

from . import audio as audio_utils
from .backends.base import Synthesizer
from .quality.speaker import cosine
from .screening import Checks

DEFAULT_GRIDS: dict[str, dict[str, list[Any]]] = {
    "chatterbox": {"cfg_weight": [0.0, 0.3, 0.5], "exaggeration": [0.5, 0.7]},
    "xtts": {"temperature": [0.5, 0.65, 0.8]},
    "elevenlabs": {"stability": [0.35, 0.5, 0.7]},
}


@dataclass
class ComboResult:
    options: dict[str, Any]
    slug: str
    clips: list[dict]

    def mean(self, key: str) -> float | None:
        values = [c[key] for c in self.clips if c.get(key) is not None]
        return statistics.fmean(values) if values else None

    @property
    def score(self) -> float:
        """Higher is better: similarity minus a CER penalty, plus a little MOS."""
        similarity = self.mean("similarity") or 0.0
        cer = self.mean("cer") or 0.0
        mos = self.mean("mos") or 0.0
        return similarity - 2.0 * cer + 0.05 * mos


def combinations(grid: dict[str, list[Any]]) -> list[dict[str, Any]]:
    keys = sorted(grid)
    return [dict(zip(keys, values, strict=False)) for values in itertools.product(*(grid[k] for k in keys))]


def slug(options: dict[str, Any]) -> str:
    return "_".join(f"{k}-{v}" for k, v in sorted(options.items())) or "default"


def run(
    synth: Synthesizer,
    base_options: dict[str, Any],
    grid: dict[str, list[Any]],
    prompts: list[tuple[str, str]],
    references: list[Path],
    out_dir: Path,
    checks: Checks,
    seed: int = 1,
) -> list[ComboResult]:
    results = []
    for options in combinations(grid):
        synth.options = {**base_options, **options}  # backends keep their knobs in .options
        combo = ComboResult(options, slug(options), [])
        for index, (utt_id, text) in enumerate(prompts):
            reference = references[index % len(references)]
            wave, rate = synth.synthesize(text, reference, seed)
            path = out_dir / combo.slug / f"{utt_id}.wav"
            audio_utils.save_wav(path, audio_utils.peak_limit(wave), rate)
            wave_16k = audio_utils.resample(wave, rate, audio_utils.EMBED_RATE)
            clip = {
                "id": utt_id,
                "text": text,
                "file": f"{combo.slug}/{utt_id}.wav",
                "cer": None,
                "similarity": None,
                "mos": None,
            }
            if checks.cer:
                clip["cer"] = checks.cer(wave_16k, text)
            if checks.embed and checks.reference_embedding is not None:
                clip["similarity"] = cosine(checks.embed(wave_16k), checks.reference_embedding)
            if checks.mos:
                clip["mos"] = checks.mos(wave_16k)
            combo.clips.append(clip)
        results.append(combo)
    results.sort(key=lambda r: r.score, reverse=True)
    write_html(out_dir / "audition.html", results)
    write_json(out_dir / RESULTS, results)
    return results


RESULTS = "results.json"


def write_json(path: Path, results: list[ComboResult]) -> None:
    """Machine-readable results (best first) for the web UI."""
    data = [
        {
            "slug": combo.slug,
            "options": combo.options,
            "score": combo.score,
            "cer": combo.mean("cer"),
            "similarity": combo.mean("similarity"),
            "mos": combo.mean("mos"),
            "clips": combo.clips,
        }
        for combo in results
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []


def _fmt(value: float | None, digits: int = 3) -> str:
    return "–" if value is None else f"{value:.{digits}f}"


def write_html(path: Path, results: list[ComboResult]) -> None:
    rows = []
    for rank, combo in enumerate(results, 1):
        players = "".join(
            f'<div class="clip"><div class="t">{html.escape(c["text"])}</div>'
            f'<audio controls preload="none" src="{html.escape(c["file"])}"></audio>'
            f'<div class="m">CER {_fmt(c["cer"])} · sim {_fmt(c["similarity"])} · '
            f"MOS {_fmt(c['mos'], 2)}</div></div>"
            for c in combo.clips
        )
        rows.append(
            f"<section><h2>#{rank} {html.escape(combo.slug)}</h2>"
            f"<p>score {combo.score:.3f} · CER {_fmt(combo.mean('cer'))} · "
            f"similarity {_fmt(combo.mean('similarity'))} · MOS {_fmt(combo.mean('mos'), 2)}</p>"
            f'<div class="grid">{players}</div></section>'
        )
    page = (
        "<!doctype html><meta charset=utf-8><title>Audition</title>"
        "<style>body{font:14px system-ui;margin:16px;max-width:1100px}"
        ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:8px}"
        ".clip{border:1px solid #ccc;border-radius:6px;padding:6px}.t{margin-bottom:4px}"
        ".m{color:#666;font-size:12px}audio{width:100%}</style>"
        "<h1>Audition</h1>" + "".join(rows)
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")
