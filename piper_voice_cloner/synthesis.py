"""Generate raw clips for all prompts: resumable, rotating reference clips and seeds."""

from __future__ import annotations

from collections.abc import Callable
import csv
from dataclasses import asdict, dataclass
import json
import logging
from pathlib import Path
import time

from . import audio as audio_utils
from .backends.base import FatalSynthesisError, Synthesizer

_LOGGER = logging.getLogger(__name__)

MANIFEST = "manifest.csv"
MANIFEST_FIELDS = ["id", "text", "reference", "seed", "backend", "rate"]
TIMING = "timing.json"


@dataclass(frozen=True)
class Timing:
    """How fast the last `synthesize` run was: to plan the full run (and compare computers)."""

    clips: int
    seconds: float  # time spent generating (failed prompts included)
    audio_seconds: float  # length of the generated audio
    device: str  # cuda / mps / cpu / remote

    @property
    def per_clip(self) -> float:
        return self.seconds / self.clips if self.clips else 0.0

    @property
    def speed(self) -> float:
        """Seconds of audio per second of work (above 1 = faster than real time)."""
        return self.audio_seconds / self.seconds if self.seconds else 0.0

    def describe(self) -> str:
        return (
            f"{self.clips} clips in {self.seconds / 60:.1f} min on {self.device}: "
            f"{self.per_clip:.1f} s per clip, {self.speed:.2f}x real time"
        )


def read_timing(raw_dir: Path) -> Timing | None:
    try:
        return Timing(**json.loads((raw_dir / TIMING).read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return None


def read_manifest(raw_dir: Path) -> dict[str, dict]:
    path = raw_dir / MANIFEST
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["id"]: row for row in csv.DictReader(handle)}


def plan(prompts: list[tuple[str, str]], references: list[Path], seeds: list[int]) -> list[dict]:
    """Deterministic assignment: prompt i gets reference i % R and seed (i // R) % S."""
    if not references:
        raise ValueError("no reference clips - run `pvc reference` first")
    if not seeds:
        raise ValueError("synthesis.seeds is empty")
    jobs = []
    for index, (utt_id, text) in enumerate(prompts):
        jobs.append(
            {
                "id": utt_id,
                "text": text,
                "reference": references[index % len(references)],
                "seed": seeds[(index // len(references)) % len(seeds)],
            }
        )
    return jobs


def run(
    synth: Synthesizer,
    jobs: list[dict],
    raw_dir: Path,
    *,
    progress: Callable[[int, int], None] | None = None,
) -> int:
    """Synthesize missing clips into raw_dir/<id>.wav; returns how many were generated now."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    done = read_manifest(raw_dir)
    source = getattr(synth, "source", synth.name)
    other = sorted({row["backend"] for row in done.values()} - {source})
    if other:
        raise FatalSynthesisError(
            f"raw/ holds clips of another voice ({', '.join(other)}), this run would make {source}: "
            "use a new voice or move raw/ away"
        )
    manifest = raw_dir / MANIFEST
    new_file = not manifest.is_file()
    generated = 0
    spent = audio_seconds = 0.0
    device = getattr(synth, "device", "") or ("remote" if synth.remote else "cpu")
    try:
        with manifest.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
            if new_file:
                writer.writeheader()
            for index, job in enumerate(jobs, 1):
                target = raw_dir / f"{job['id']}.wav"
                if job["id"] in done and target.is_file():
                    continue
                started = time.monotonic()
                try:
                    wave, rate = synth.synthesize(job["text"], Path(job["reference"]), int(job["seed"]))
                except FatalSynthesisError:
                    raise
                except Exception:  # one bad prompt must not stop a 2000-clip run
                    _LOGGER.exception("synthesis failed for %s: %s", job["id"], job["text"])
                    spent += time.monotonic() - started
                    continue
                spent += time.monotonic() - started
                audio_seconds += len(wave) / rate
                audio_utils.save_wav(target, audio_utils.peak_limit(wave), rate)
                writer.writerow(
                    {
                        "id": job["id"],
                        "text": job["text"],
                        "reference": Path(job["reference"]).name,
                        "seed": job["seed"],
                        "backend": source,
                        "rate": rate,
                    }
                )
                handle.flush()
                generated += 1
                if progress:
                    progress(index, len(jobs))
    finally:  # also after Ctrl+C: a stopped test run still tells the speed
        if generated:
            timing = Timing(generated, round(spent, 2), round(audio_seconds, 2), device)
            (raw_dir / TIMING).write_text(json.dumps(asdict(timing)), encoding="utf-8")
    return generated
