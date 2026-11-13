"""Listening to a training run in the web UI: the audio samples and the quality per epoch.

piper1-gpl (Lightning + TensorBoard logger) writes, after every validation, the test sentences as audio
(``add_audio``) and the metrics (``val_mos``, ``val_mel``, ...) into ``lightning_logs/version_*/
events.out.tfevents.*``. This module reads those files without TensorBoard: a TFRecord is
``length (u64) | crc (u32) | data | crc (u32)`` and the data is a small protobuf ``Event``, so a few
lines of varint parsing are enough.

The files grow to hundreds of MB (audio every epoch), so they are read incrementally: the offset
reached is kept in ``<work_dir>/monitor/state.json`` together with the metrics, and the audio of the
kept epochs is written to ``<work_dir>/monitor/audio/`` as WAV files.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
import html
import io
import json
import math
from pathlib import Path
import re
import struct
import threading
import zipfile

STATE_FILE = "state.json"
# 2: the best epochs keep their audio; 3: so do the epochs with a checkpoint. An older state is read
# again from the start of the files (the audio of all epochs is still in them), so audio dropped by
# the old rules comes back
STATE_VERSION = 3
# audio kept: every KEEP_EVERY-th epoch, the first one, the newest KEEP_NEWEST, the KEEP_BEST with
# the highest val_mos and every epoch with a checkpoint file, so each checkpoint can be heard first
KEEP_EVERY = 10
KEEP_NEWEST = 3
KEEP_BEST = 5
# training metrics kept as the mean of each epoch (logged every 50 steps); val_* are kept as they are
TRAIN_TAGS = ("train_mel",)
MAX_READ = 64 * 1024 * 1024  # bytes parsed per refresh, so one click never takes long
# the listening block and the chart may read the same run at once; one reader at a time
_LOCK = threading.Lock()


def _varint(buf: bytes, pos: int) -> tuple[int, int]:
    result = shift = 0
    while True:
        byte = buf[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, pos
        shift += 7


def _fields(buf: bytes):
    """(field number, wire type, value) of a protobuf message; value is int, float bytes or bytes."""
    pos = 0
    while pos < len(buf):
        key, pos = _varint(buf, pos)
        number, wire = key >> 3, key & 7
        if wire == 0:
            value, pos = _varint(buf, pos)
        elif wire == 1:
            value, pos = buf[pos : pos + 8], pos + 8
        elif wire == 2:
            length, pos = _varint(buf, pos)
            value, pos = buf[pos : pos + length], pos + length
        elif wire == 5:
            value, pos = buf[pos : pos + 4], pos + 4
        else:  # groups (3, 4) are never used by TensorBoard
            raise ValueError(f"unsupported wire type {wire}")
        yield number, wire, value


def _tensor_float(buf: bytes) -> float | None:
    """The first float of a TensorProto (new-style scalars): float_val (5) or tensor_content (4)."""
    for number, wire, value in _fields(buf):
        if number == 5 and wire == 5:
            return struct.unpack("<f", value)[0]
        if number == 5 and wire == 2 and len(value) >= 4:
            return struct.unpack("<f", value[:4])[0]
        if number == 4 and wire == 2 and len(value) >= 4:
            return struct.unpack("<f", value[:4])[0]
    return None


def parse_event(data: bytes) -> tuple[int, list[tuple[str, float]], list[tuple[str, bytes]]]:
    """(step, [(tag, scalar)], [(tag, encoded WAV)]) of one Event record."""
    step, scalars, audio = 0, [], []
    for number, wire, value in _fields(data):
        if number == 2 and wire == 0:
            step = value
        elif number == 5 and wire == 2:  # Summary
            for vnum, vwire, entry in _fields(value):
                if vnum != 1 or vwire != 2:
                    continue
                tag, scalar, encoded = "", None, None
                for fnum, fwire, field in _fields(entry):
                    if fnum == 1 and fwire == 2:
                        tag = field.decode("utf-8", "replace")
                    elif fnum == 2 and fwire == 5:
                        scalar = struct.unpack("<f", field)[0]
                    elif fnum == 6 and fwire == 2:  # Summary.Audio
                        for anum, awire, part in _fields(field):
                            if anum == 4 and awire == 2:
                                encoded = part
                    elif fnum == 8 and fwire == 2:  # TensorProto
                        scalar = _tensor_float(field)
                if encoded is not None:
                    audio.append((tag, encoded))
                elif scalar is not None:
                    scalars.append((tag, scalar))
    return step, scalars, audio


def read_records(path: Path, offset: int, limit: int = MAX_READ) -> list[tuple[int, bytes]]:
    """(start offset, data) of the complete TFRecords from ``offset`` on (a record still being written
    is left for later)."""
    records = []
    with path.open("rb") as handle:
        handle.seek(offset)
        read = 0
        while read < limit:
            header = handle.read(12)
            if len(header) < 12:
                break
            (length,) = struct.unpack("<Q", header[:8])
            body = handle.read(length + 4)
            if len(body) < length + 4:
                break
            records.append((offset, body[:length]))
            offset += 12 + length + 4
            read += 12 + length + 4
    records.append((offset, b""))  # the end: where the next look starts when nothing waits
    return records


@dataclass
class Sample:
    epoch: int
    index: int
    text: str
    path: Path


@dataclass
class Run:
    """What the panel shows of one training run."""

    metrics: dict[str, dict[int, float]]  # metric -> {epoch: value} (val_* metrics, last per epoch)
    samples: dict[int, list[Sample]]  # epoch -> the test sentences of that epoch
    last_epoch: int | None
    saved: frozenset[int] = frozenset()  # epochs with a checkpoint file (epoch=N-….ckpt)

    @property
    def epochs(self) -> list[int]:
        """Epochs with audio, newest first."""
        return sorted(self.samples, reverse=True)

    def value(self, metric: str, epoch: int) -> float | None:
        return self.metrics.get(metric, {}).get(epoch)

    def table(self, names: tuple[str, ...] = ("val_mos", "val_mel", "train_mel")) -> list[list]:
        """[[epoch, value of each name or None], ...] for the chart, oldest epoch first."""
        epochs = sorted({e for name in names for e in self.metrics.get(name, {})})
        return [[e, *(self.value(name, e) for name in names)] for e in epochs]


def event_files(work_dir: Path) -> list[Path]:
    return sorted(work_dir.glob("lightning_logs/version_*/events.out.tfevents.*"))


def _tracked(tag: str) -> bool:
    return tag.startswith("val_") or tag in TRAIN_TAGS


_CKPT_EPOCH = re.compile(r"epoch=(\d+)")


def checkpoint_epochs(work_dir: Path) -> frozenset[int]:
    """Epochs that have a checkpoint (piper names them epoch=N-val_mos=….ckpt; last.ckpt has none)."""
    found = (_CKPT_EPOCH.search(p.name) for p in work_dir.glob("lightning_logs/version_*/checkpoints/*.ckpt"))
    return frozenset(int(m.group(1)) for m in found if m)


def _keep(epoch: int, first: int, newest: list[int], best: set[int], saved: frozenset[int]) -> bool:
    return epoch == first or epoch % KEEP_EVERY == 0 or epoch in newest or epoch in best or epoch in saved


def update(work_dir: Path) -> Run:
    """Read what is new in the event files and return the run (cheap when nothing changed)."""
    with _LOCK:
        return _update(work_dir)


def _update(work_dir: Path) -> Run:
    monitor = work_dir / "monitor"
    audio_dir = monitor / "audio"
    state_path = monitor / STATE_FILE
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    if state.get("version") != STATE_VERSION:
        state = {}  # read everything again (the audio files get the same names, nothing is left over)
    offsets: dict[str, int] = state.get("offsets", {})
    metrics: dict[str, dict[str, float]] = state.get("metrics", {})
    sums: dict[str, dict[str, list[float]]] = state.get("sums", {})  # TRAIN_TAGS: epoch -> [sum, count]
    audio: dict[str, list[list]] = state.get("audio", {})  # epoch -> [[index, text, file, step]]
    last_epoch = state.get("last_epoch")
    changed = False

    def store(epoch: int, clips: list[tuple[int, str, bytes]]) -> None:
        entries = audio.setdefault(str(epoch), [])
        if entries and entries[0][3] != clips[0][0]:  # the same epoch validated again (after a resume)
            for _index, _text, old, _step in entries:
                (audio_dir / old).unlink(missing_ok=True)
            entries.clear()
        audio_dir.mkdir(parents=True, exist_ok=True)
        for step, tag, wav in clips:
            name = f"epoch{epoch:05d}-{len(entries):02d}.wav"
            (audio_dir / name).write_bytes(wav)
            entries.append([len(entries), tag, name, step])

    for path in event_files(work_dir):
        key = str(path.relative_to(work_dir))
        records = read_records(path, offsets.get(key, 0))
        end = records[-1][0]
        # The audio and the val_* metrics of a validation come before Lightning writes "epoch" for
        # them (and the audio carries another step: two optimizers count twice), so they wait for the
        # next "epoch" value in the file. Not there yet: the next look starts again at them.
        waiting_from: int | None = None
        clips: list[tuple[int, str, bytes]] = []
        values: list[tuple[str, float]] = []
        for start, record in records[:-1]:
            try:
                step, scalars, found = parse_event(record)
            except (ValueError, IndexError, struct.error):
                continue  # a record we do not understand is skipped, never fatal
            kept = [(tag, v) for tag, v in scalars if _tracked(tag) and math.isfinite(v)]
            if (found or kept) and waiting_from is None:
                waiting_from = start
            clips += [(step, tag, wav) for tag, wav in found]
            values += kept
            epochs = [int(v) for tag, v in scalars if tag == "epoch"]
            if epochs:
                last_epoch = max(last_epoch or 0, epochs[-1])
                if waiting_from is not None:
                    for tag, value in values:
                        if tag in TRAIN_TAGS:
                            total = sums.setdefault(tag, {}).setdefault(str(epochs[-1]), [0.0, 0])
                            total[0], total[1] = total[0] + value, total[1] + 1
                        else:
                            metrics.setdefault(tag, {})[str(epochs[-1])] = value
                    if clips:
                        store(epochs[-1], clips)
                    waiting_from, clips, values = None, [], []
        new_offset = waiting_from if waiting_from is not None else end
        if new_offset != offsets.get(key, 0):
            offsets[key], changed = new_offset, True

    saved = checkpoint_epochs(work_dir)
    if changed:
        # thin out the audio: the first epoch, every KEEP_EVERY-th, the newest, the best ones and the
        # ones with a checkpoint stay
        epochs = sorted(int(e) for e in audio)
        if epochs:
            newest = epochs[-KEEP_NEWEST:]
            mos = metrics.get("val_mos", {})
            best = {int(e) for e in sorted(mos, key=mos.get, reverse=True)[:KEEP_BEST]}
            for epoch in epochs:
                if not _keep(epoch, epochs[0], newest, best, saved):
                    for _index, _text, name, _step in audio.pop(str(epoch)):
                        (audio_dir / name).unlink(missing_ok=True)
        monitor.mkdir(parents=True, exist_ok=True)
        state = {
            "version": STATE_VERSION,
            "offsets": offsets,
            "metrics": metrics,
            "sums": sums,
            "audio": audio,
            "last_epoch": last_epoch,
        }
        tmp = state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state), encoding="utf-8")
        tmp.replace(state_path)

    means = {tag: {int(e): total / count for e, (total, count) in epochs.items() if count}
             for tag, epochs in sums.items()}  # fmt: skip
    return Run(
        metrics={tag: {int(e): v for e, v in values.items()} for tag, values in metrics.items()} | means,
        samples={
            int(epoch): [Sample(int(epoch), i, text, audio_dir / name) for i, text, name, _step in clips]
            for epoch, clips in audio.items()
        },
        last_epoch=last_epoch,
        saved=saved,
    )


SAMPLES_ZIP = "samples.zip"

_INDEX_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root {
  color-scheme: light dark; --bg: #f6f7fb; --card: #fff; --text: #1d2130; --muted: #6b7280;
  --line: #e3e6ef; --accent: #ef6c3a;
}
@media (prefers-color-scheme: dark) {
  :root { --bg: #11131a; --card: #1a1d27; --text: #e8eaf2; --muted: #9aa1b2; --line: #2a2f3d; }
}
body {
  margin: 0; padding: 24px 16px; background: var(--bg); color: var(--text);
  font: 15px/1.5 system-ui, sans-serif;
}
main { max-width: 1100px; margin: 0 auto; }
h1 { font-size: 1.4rem; margin: 0 0 4px; }
p { color: var(--muted); margin: 0 0 16px; }
.bar { display: flex; flex-wrap: wrap; gap: 10px 18px; align-items: center; margin-bottom: 14px; }
button {
  font: inherit; padding: 5px 12px; border-radius: 10px; border: 1px solid var(--line);
  background: var(--card); color: var(--text); cursor: pointer;
}
button.on { border-color: var(--accent); color: var(--accent); }
table {
  width: 100%; border-collapse: collapse; background: var(--card); border-radius: 14px; overflow: hidden;
}
th, td { padding: 8px 10px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }
th { color: var(--muted); font-weight: 600; white-space: nowrap; }
td.num { font-variant-numeric: tabular-nums; white-space: nowrap; }
.clips { display: flex; flex-wrap: wrap; gap: 6px; }
figure { margin: 0; max-width: 260px; }
audio { height: 32px; width: 260px; }
figcaption { color: var(--muted); font-size: .8rem; }
.ckpt { color: var(--accent); font-weight: 600; white-space: nowrap; }
</style></head><body><main>
<h1>__TITLE__</h1>
<p>__INTRO__</p>
<div class="bar">
  <span>Sort:</span>
  <button type="button" data-sort="epoch" class="on">epoch</button>
  <button type="button" data-sort="mos">val_mos (best first)</button>
  <button type="button" data-sort="mel">val_mel (best first)</button>
  <label><input type="checkbox" id="ckpt"> only epochs with a checkpoint</label>
</div>
<table><thead><tr><th>epoch</th><th>val_mos</th><th>val_mel</th><th>checkpoint</th><th>samples</th></tr></thead>
<tbody id="rows">__ROWS__</tbody></table>
</main>
<script>
const body = document.getElementById("rows");
const rows = [...body.rows];
const key = {
  epoch: (r) => -r.dataset.epoch, mos: (r) => -(r.dataset.mos || -9), mel: (r) => +(r.dataset.mel || 9),
};
document.querySelectorAll("[data-sort]").forEach((button) => button.onclick = () => {
  document.querySelectorAll("[data-sort]").forEach((b) => b.classList.toggle("on", b === button));
  const by = key[button.dataset.sort];
  rows.sort((a, b) => by(a) - by(b)).forEach((r) => body.append(r));
});
document.getElementById("ckpt").onchange = (event) =>
  rows.forEach((r) => { r.hidden = event.target.checked && !r.dataset.ckpt; });
</script></body></html>
"""


def _fmt(value: float | None, digits: int) -> str:
    return f"{value:.{digits}f}" if value is not None else ""


def export_samples(work_dir: Path, title: str, out: Path | None = None) -> Path:
    """One ZIP of every kept sample to listen to offline: a folder per epoch named with its quality
    (``epoch01273-mos3.71-checkpoint/00.wav``), ``samples.csv`` and an ``index.html`` with players,
    sorting by val_mos/val_mel and a filter for the epochs that have a checkpoint."""
    run = update(work_dir)
    if not run.epochs:
        raise ValueError(f"no training samples in {work_dir} yet")
    out = out or work_dir / "monitor" / SAMPLES_ZIP
    folder = re.sub(r"[^\w.-]+", "-", title).strip("-") or "samples"
    table = io.StringIO()
    writer = csv.writer(table)
    writer.writerow(["epoch", "val_mos", "val_mel", "checkpoint", "file", "sentence"])
    rows = []
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_STORED) as archive:  # WAV does not compress
        for epoch in sorted(run.samples):
            mos, mel = run.value("val_mos", epoch), run.value("val_mel", epoch)
            saved = epoch in run.saved
            name = f"epoch{epoch:05d}" + (f"-mos{mos:.2f}" if mos is not None else "")
            name += "-checkpoint" if saved else ""
            players = []
            for sample in run.samples[epoch]:
                if not sample.path.is_file():
                    continue
                inner = f"{name}/{sample.index:02d}.wav"
                archive.write(sample.path, f"{folder}/{inner}")
                writer.writerow(
                    [epoch, _fmt(mos, 3), _fmt(mel, 4), "yes" if saved else "", inner, sample.text]
                )
                players.append(
                    f'<figure><audio controls preload="none" src="{html.escape(inner)}"></audio>'
                    f"<figcaption>{html.escape(sample.text)}</figcaption></figure>"
                )
            rows.append(
                f'<tr data-epoch="{epoch}" data-mos="{_fmt(mos, 3)}" data-mel="{_fmt(mel, 4)}"'
                + (' data-ckpt="1"' if saved else "")
                + f'><td class="num">{epoch}</td><td class="num">{_fmt(mos, 2)}</td>'
                f'<td class="num">{_fmt(mel, 3)}</td><td class="ckpt">{"💾" if saved else ""}</td>'
                f'<td><div class="clips">{"".join(players)}</div></td></tr>'
            )
        intro = (
            f"{len(rows)} epochs. 💾 = this epoch has a checkpoint file (epoch=N-….ckpt) and can be "
            "chosen. val_mos: predicted naturalness (higher is better); val_mel: error of the "
            "spectrogram (lower is better). Trust your ears more than the numbers."
        )
        page = (
            _INDEX_HTML.replace("__TITLE__", html.escape(title))
            .replace("__INTRO__", html.escape(intro))
            .replace("__ROWS__", "\n".join(rows))
        )
        archive.writestr(f"{folder}/index.html", page)
        archive.writestr(f"{folder}/samples.csv", table.getvalue())
    tmp.replace(out)
    return out
