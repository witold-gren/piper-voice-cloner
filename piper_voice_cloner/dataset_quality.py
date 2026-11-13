"""How good the recordings of a dataset are: UTMOS for a random sample (or all of them).

A model learns to sound like its data, so the score of the recordings is the ceiling of the val_mos
it can reach. The scoring itself runs in the training environment (score_clips.py); this module picks
the clips, runs it and keeps the result in <dataset>/utmos.json for the CLI and the web UI.
"""

from __future__ import annotations

from collections.abc import Callable
import json
from pathlib import Path
import random
import statistics
import subprocess
import sys
import tempfile
import time

from .dataset import METADATA, WAV_DIR, read_metadata

REPORT_FILE = "utmos.json"
SCRIPT = Path(__file__).with_name("score_clips.py")
SEED = 0  # the same sample every time, so two scorings of one dataset compare
GOOD = 4.0  # about what clean studio speech gets
SHOWN = 5  # worst and best clips kept for listening


class ScoreError(RuntimeError):
    pass


def report_path(dataset: Path) -> Path:
    return dataset / REPORT_FILE


def pick(ids: list[str], sample: int, seed: int = SEED) -> list[str]:
    """`sample` ids at random (0 or more than there are: all of them)."""
    if sample <= 0 or sample >= len(ids):
        return list(ids)
    return random.Random(seed).sample(ids, sample)


def score_dataset(
    dataset: Path,
    sample: int,
    *,
    python: str = sys.executable,
    progress: Callable[[int, int], None] | None = None,
) -> dict:
    """Score `sample` clips (0 = all) with the training Python and save the report."""
    texts = {u.id: u.text for u in read_metadata(dataset / METADATA)}
    chosen = pick(sorted(texts), sample)
    if not chosen:
        raise ScoreError(f"{dataset / METADATA} has no clips")
    files = {str(dataset / WAV_DIR / f"{clip}.wav"): clip for clip in chosen}
    with tempfile.TemporaryDirectory() as tmp:
        list_file, out_file = Path(tmp) / "clips.txt", Path(tmp) / "scores.json"
        list_file.write_text("\n".join(files) + "\n", encoding="utf-8")
        # -I: the script's own folder (the package) must not shadow modules of the training environment
        cmd = [python, "-I", str(SCRIPT), str(list_file), str(out_file)]
        with subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True) as proc:
            for line in proc.stdout or []:
                if line.startswith("scored ") and progress is not None:
                    done, total = line.split()[1].split("/")
                    progress(int(done), int(total))
                else:
                    print(line, end="", flush=True)
        if proc.returncode != 0:
            raise ScoreError(
                f"scoring failed (exit code {proc.returncode}) - is {python} the training Python?"
            )
        scores = json.loads(out_file.read_text(encoding="utf-8"))
    report = {
        "created": time.time(),
        "total": len(texts),
        "scores": {files[path]: score for path, score in scores.items()},
        "texts": {clip: texts[clip] for clip in chosen},
    }
    report_path(dataset).write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    return report


def load(dataset: Path) -> dict | None:
    try:
        return json.loads(report_path(dataset).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def summary(report: dict) -> dict:
    """Numbers for people: middle, spread, share of good clips, the worst and best clips."""
    ranked = sorted(report["scores"].items(), key=lambda item: item[1])
    values = [score for _clip, score in ranked]
    deciles = statistics.quantiles(values, n=10) if len(values) > 1 else values * 9
    return {
        "count": len(values),
        "total": report.get("total", len(values)),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "p10": deciles[0],
        "p90": deciles[-1],
        "good": sum(v >= GOOD for v in values) / len(values),
        "worst": ranked[:SHOWN],
        "best": ranked[::-1][:SHOWN],
    }


def describe(report: dict) -> str:
    s = summary(report)
    lines = [
        f"UTMOS of {s['count']} of {s['total']} clips: median {s['median']:.2f}, mean {s['mean']:.2f}, "
        f"10% below {s['p10']:.2f}, 10% above {s['p90']:.2f}, {s['good']:.0%} at {GOOD:.0f} or more",
        "worst: " + ", ".join(f"{clip} {score:.2f}" for clip, score in s["worst"]),
    ]
    return "\n".join(lines)
