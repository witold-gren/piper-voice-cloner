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
import shutil
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
BELOW = (2.5, 3.0, 3.3)  # levels counted in the summary: the clips under each


class ScoreError(RuntimeError):
    pass


def report_path(dataset: Path) -> Path:
    return dataset / REPORT_FILE


def pick(ids: list[str], sample: int, seed: int = SEED) -> list[str]:
    """`sample` ids at random (0 or more than there are: all of them)."""
    if sample <= 0 or sample >= len(ids):
        return list(ids)
    return random.Random(seed).sample(ids, sample)


def stamp(path: Path) -> str:
    """What tells a clip changed: its size and time of change ("" when the file is not there)."""
    try:
        info = path.stat()
    except OSError:
        return ""
    return f"{info.st_size}:{info.st_mtime_ns}"


def score_dataset(
    dataset: Path,
    sample: int,
    *,
    python: str = sys.executable,
    progress: Callable[[int, int], None] | None = None,
) -> dict:
    """Score `sample` clips (0 = all) with the training Python and save the report.

    Every score is kept in <dataset>/utmos.json with the stamp of its file: a later scoring only rates
    the clips not scored yet or changed since, the rest comes from the file. The scores of clips taken
    out of metadata.csv stay while their files do (a dataset put back is not rated again); `current`
    gives the report of the clips in the dataset now."""
    texts = {u.id: u.text for u in read_metadata(dataset / METADATA)}
    chosen = pick(sorted(texts), sample)
    if not chosen:
        raise ScoreError(f"{dataset / METADATA} has no clips")
    before = load(dataset) or {}
    old_scores = before.get("scores", {})
    wav = {clip: dataset / WAV_DIR / f"{clip}.wav" for clip in {*texts, *old_scores}}
    stamps = {clip: stamp(path) for clip, path in wav.items()}
    # a report from before the stamps were kept: its scores count for the files as they are now
    old_stamps = before.get("stamps", stamps)
    # still right: scored before and the file the same (a clip out of the dataset: its file still there)
    kept = {
        clip: score
        for clip, score in old_scores.items()
        if clip in old_stamps and old_stamps[clip] == stamps[clip] and (clip in texts or stamps[clip])
    }
    todo = [clip for clip in chosen if clip not in kept]
    print(
        f"UTMOS: {len(chosen) - len(todo)} of {len(chosen)} clips already scored, scoring {len(todo)}",
        flush=True,
    )
    scores = dict(kept)
    failure: BaseException | None = None
    if todo:
        new, failure = _score_files({str(wav[clip]): clip for clip in todo}, python, progress)
        scores |= new
    elif progress is not None:
        progress(len(chosen), len(chosen))
    scored = len(scores) - len(kept)
    old_texts = before.get("texts", {})
    report = {
        "created": time.time(),
        "total": len(texts),
        "scores": scores,
        "stamps": {clip: stamps[clip] for clip in scores},
        "texts": {clip: texts.get(clip, old_texts.get(clip, "")) for clip in scores},
        "scored": scored,
        "reused": len(chosen) - len(todo),
    }
    if failure is not None and not scored:
        raise failure
    # saved also after a stop or a failure: the clips scored so far are not rated again
    report_path(dataset).write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    if failure is not None:
        print(f"UTMOS: {scored} new scores saved before the stop", flush=True)
        raise failure
    return current(report, dataset)


def current(report: dict | None, dataset: Path) -> dict | None:
    """The report of the clips in metadata.csv now (None when none of them is scored)."""
    if not report:
        return None
    try:
        ids = {u.id for u in read_metadata(dataset / METADATA)}
    except OSError:
        return None
    scores = {clip: score for clip, score in report.get("scores", {}).items() if clip in ids}
    if not scores:
        return None
    texts = report.get("texts", {})
    return report | {"total": len(ids), "scores": scores, "texts": {c: texts.get(c, "") for c in scores}}


def _score_files(
    files: dict[str, str], python: str, progress
) -> tuple[dict[str, float], BaseException | None]:
    """{path: clip} → ({clip: score}, what stopped it): rated by score_clips.py in the training
    Python, which saves the scores so far every 100 clips and on a stop."""
    failure: BaseException | None = None
    with tempfile.TemporaryDirectory() as tmp:
        list_file, out_file = Path(tmp) / "clips.txt", Path(tmp) / "scores.json"
        list_file.write_text("\n".join(files) + "\n", encoding="utf-8")
        # -I: the script's own folder (the package) must not shadow modules of the training environment
        cmd = [python, "-I", str(SCRIPT), str(list_file), str(out_file)]
        with subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True) as proc:
            try:
                for line in proc.stdout or []:
                    if line.startswith("scored ") and progress is not None:
                        done, total = line.split()[1].split("/")
                        progress(int(done), int(total))
                    else:
                        print(line, end="", flush=True)
            except KeyboardInterrupt as err:  # Stop: the scorer gets it too and saves what it has
                failure = err
            proc.wait()
        if failure is None and proc.returncode != 0:
            failure = ScoreError(
                f"scoring failed (exit code {proc.returncode}) - is {python} the training Python?"
            )
        try:
            scores = json.loads(out_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            scores = {}
    return {files[path]: score for path, score in scores.items() if path in files}, failure


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
        # how many clips a cleaning at each level would take out
        "below": {f"{level:.1f}": sum(v < level for v in values) for level in BELOW},
        "worst": ranked[:SHOWN],
        "best": ranked[::-1][:SHOWN],
    }


def describe(report: dict) -> str:
    s = summary(report)
    lines = [
        f"UTMOS of {s['count']} of {s['total']} clips: median {s['median']:.2f}, mean {s['mean']:.2f}, "
        f"10% below {s['p10']:.2f}, 10% above {s['p90']:.2f}, {s['good']:.0%} at {GOOD:.0f} or more",
        "below: " + ", ".join(f"{level} {count}" for level, count in s["below"].items()),
        "worst: " + ", ".join(f"{clip} {score:.2f}" for clip, score in s["worst"]),
    ]
    return "\n".join(lines)


# --- taking weak clips out of a dataset --------------------------------------------------------------

TARGET = 1500  # clips a voice wants (about what a good fine-tune needs)


def prune(dataset: Path, *, below: float | None = None, keep_best: int | None = None) -> dict:
    """Take the clips under `below` (or all but the `keep_best` best ones) out of metadata.csv.

    Nothing is deleted: the WAV files stay, metadata.csv before goes to metadata.before-prune-<time>.csv
    and the clips taken out to pruned-<time>.csv (id|score|text), so the dataset can be put back.
    Every clip must be scored first (`pvc score`)."""
    if (below is None) == (keep_best is None):
        raise ScoreError("give either a level (below) or a number of clips to keep (keep_best)")
    metadata = dataset / METADATA
    texts = {u.id: u.text for u in read_metadata(metadata)}
    scores = (load(dataset) or {}).get("scores", {})
    missing = [clip for clip in texts if clip not in scores]
    if missing:
        raise ScoreError(f"{len(missing)} of {len(texts)} clips are not scored yet - rate them first")
    if below is not None:
        removed = {clip for clip in texts if scores[clip] < below}
    else:
        ranked = sorted(texts, key=lambda clip: scores[clip], reverse=True)
        removed = set(ranked[max(keep_best, 0) :])
    kept = len(texts) - len(removed)
    result = {"total": len(texts), "kept": kept, "removed": len(removed), "short": max(TARGET - kept, 0)}
    if not removed:
        return result | {"backup": None}
    stamp_now = time.strftime("%Y%m%d-%H%M%S")
    backup = dataset / f"metadata.before-prune-{stamp_now}.csv"
    shutil.copy2(metadata, backup)
    with (dataset / f"pruned-{stamp_now}.csv").open("w", encoding="utf-8") as handle:
        for clip in sorted(removed, key=lambda c: scores[c]):
            handle.write(f"{clip}|{scores[clip]:.3f}|{texts[clip]}\n")
    # the lines as they were (format, extension, extra columns), only the weak ones left out
    lines = metadata.read_text(encoding="utf-8").splitlines(keepends=True)
    kept_lines = [line for line in lines if _line_id(line) not in removed]
    part = metadata.with_suffix(".csv.part")
    part.write_text("".join(kept_lines), encoding="utf-8")
    part.replace(metadata)
    return result | {"backup": str(backup)}


def _line_id(line: str) -> str:
    first = line.split("|", 1)[0].strip()
    return first[:-4] if first.lower().endswith(".wav") else first


def describe_prune(result: dict) -> str:
    text = f"kept {result['kept']} of {result['total']} clips, took out {result['removed']}"
    if result["backup"]:
        text += f" (metadata.csv before: {result['backup']})"
    if result["short"]:
        text += f"; {result['short']} short of {TARGET} - generate that many more sentences"
    return text
