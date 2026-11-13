"""LJSpeech-style datasets as read by Piper (`csv` module, '|' delimiter) and CSV reports."""

from __future__ import annotations

from collections import Counter
import csv
from dataclasses import dataclass
from pathlib import Path

METADATA = "metadata.csv"
WAV_DIR = "wav"


@dataclass(frozen=True)
class Utterance:
    id: str
    text: str


def read_metadata(path: Path) -> list[Utterance]:
    """Read `id|text` rows the same way Piper does (csv quoting understood, extension optional)."""
    rows: list[Utterance] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.reader(handle, delimiter="|"):
            if len(row) < 2 or not row[0].strip():
                continue
            utt_id = row[0].strip()
            if utt_id.lower().endswith(".wav"):
                utt_id = utt_id[:-4]
            rows.append(Utterance(utt_id, row[-1]))
    return rows


def write_metadata(path: Path, utterances: list[Utterance]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="|", lineterminator="\n")
        for utt in utterances:
            writer.writerow([f"{utt.id}.wav", utt.text])


def write_report(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows: list[dict], key: str = "reason") -> str:
    total = len(rows)
    kept = sum(1 for row in rows if not row.get(key))
    reasons = Counter(row[key] for row in rows if row.get(key))
    lines = [f"kept {kept} of {total}"]
    lines += [f"  {reason}: {count}" for reason, count in reasons.most_common()]
    return "\n".join(lines)
