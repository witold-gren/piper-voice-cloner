from __future__ import annotations

import io
import json
import struct
import wave

import pytest

from piper_voice_cloner import train_monitor


def _varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        out.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(out)


def _field(number: int, wire: int, payload: bytes | int) -> bytes:
    key = _varint(number << 3 | wire)
    if wire == 0:
        return key + _varint(payload)
    if wire == 2:
        return key + _varint(len(payload)) + payload
    return key + payload  # fixed32 / fixed64 already packed


def _wav(seconds: float = 0.05) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(22050)
        out.writeframes(b"\0\0" * int(22050 * seconds))
    return buffer.getvalue()


def event(step: int, scalars=(), audio=(), tensor_scalars=()) -> bytes:
    """An Event the way TensorBoard's SummaryWriter writes it (only the fields we read)."""
    values = b""
    for tag, value in scalars:
        values += _field(1, 2, _field(1, 2, tag.encode()) + _field(2, 5, struct.pack("<f", value)))
    for tag, value in tensor_scalars:
        tensor = _field(1, 0, 1) + _field(5, 2, struct.pack("<f", value))
        values += _field(1, 2, _field(1, 2, tag.encode()) + _field(8, 2, tensor))
    for tag, wav in audio:
        clip = _field(1, 5, struct.pack("<f", 22050.0)) + _field(4, 2, wav)
        values += _field(1, 2, _field(1, 2, tag.encode()) + _field(6, 2, clip))
    return _field(1, 1, struct.pack("<d", 1.0)) + _field(2, 0, step) + _field(5, 2, values)


def record(data: bytes) -> bytes:
    return struct.pack("<Q", len(data)) + b"\0" * 4 + data + b"\0" * 4  # crcs are not checked


def write(path, *events: bytes, mode: str = "ab") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open(mode) as out:
        for data in events:
            out.write(record(data))


SENTENCES = ["Ala ma kota.", "Kot ma Alę."]


def validation(step: int, epoch: int, mos: float) -> list[bytes]:
    """What one validation writes: training logs earlier in the epoch, then audio, then the metrics
    with "epoch" at the same step (Lightning flushes them after on_validation_epoch_end)."""
    return [
        event(step - 20, scalars=[("train_mel", 2.0 + epoch), ("epoch", epoch)]),
        event(step - 10, scalars=[("loss_g", 30.0), ("train_mel", 4.0 + epoch), ("epoch", epoch)]),
        # piper has two optimizers: global_step (the audio) counts twice the logger step (the metrics)
        event(2 * step, audio=[(text, _wav()) for text in SENTENCES]),
        event(
            step,
            scalars=[("val_mel", 1.0 / (epoch + 1)), ("epoch", epoch)],
            tensor_scalars=[("val_mos", mos)],
        ),
    ]


def test_parse_event_reads_scalars_tensor_scalars_and_audio():
    wav = _wav()
    step, scalars, audio = train_monitor.parse_event(
        event(42, scalars=[("loss_d", 2.5)], tensor_scalars=[("val_mos", 3.25)], audio=[("Zdanie.", wav)])
    )
    assert step == 42 and scalars == [("loss_d", 2.5), ("val_mos", 3.25)] and audio == [("Zdanie.", wav)]


def test_samples_and_quality_per_epoch(tmp_path):
    work = tmp_path / "train"
    events = work / "lightning_logs" / "version_0" / "events.out.tfevents.1.host"
    write(events, *validation(100, 0, 2.0), *validation(200, 1, 2.5))
    run = train_monitor.update(work)
    assert run.epochs == [1, 0] and run.last_epoch == 1
    assert [s.text for s in run.samples[1]] == SENTENCES
    assert run.samples[1][0].path.read_bytes()[:4] == b"RIFF"
    assert run.value("val_mos", 1) == 2.5 and run.value("val_mel", 0) == 1.0

    # incremental: only the new part is read; a record still being written waits for the next look
    data = record(validation(300, 2, 3.0)[2])
    with events.open("ab") as out:
        for item in validation(300, 2, 3.0)[:2]:
            out.write(record(item))
        out.write(data[:20])
    run = train_monitor.update(work)
    assert 2 not in run.samples
    with events.open("ab") as out:
        out.write(data[20:])
        out.write(record(validation(300, 2, 3.0)[3]))
    run = train_monitor.update(work)
    assert run.epochs == [2, 1, 0] and run.value("val_mos", 2) == 3.0


def test_old_audio_is_thinned_out(tmp_path):
    work = tmp_path / "train"
    events = work / "lightning_logs" / "version_0" / "events.out.tfevents.1.host"
    for epoch in range(25):
        write(events, *validation(100 * (epoch + 1), epoch, 2.0 + epoch / 10))
    run = train_monitor.update(work)
    # the first, every 10th, the 3 newest and the 5 best (here 20-24: val_mos grows) stay
    assert run.epochs == [24, 23, 22, 21, 20, 10, 0]
    files = sorted((work / "monitor" / "audio").iterdir())
    assert len(files) == 7 * len(SENTENCES)
    assert run.value("val_mos", 5) is not None  # metrics of every epoch stay


def test_the_best_epochs_keep_their_audio(tmp_path):
    work = tmp_path / "train"
    events = work / "lightning_logs" / "version_0" / "events.out.tfevents.1.host"
    peaks = {7: 3.9, 13: 3.8}  # the best epochs are in the middle of the run, far from the newest
    for epoch in range(30):
        write(events, *validation(100 * (epoch + 1), epoch, peaks.get(epoch, 2.0 + epoch / 100)))
    run = train_monitor.update(work)
    assert 7 in run.samples and 13 in run.samples and 8 not in run.samples
    assert (work / "monitor" / "audio" / "epoch00007-00.wav").is_file()


def test_epochs_with_a_checkpoint_keep_their_audio(tmp_path):
    work = tmp_path / "train"
    version = work / "lightning_logs" / "version_0"
    (version / "checkpoints").mkdir(parents=True)
    (version / "checkpoints" / "epoch=13-val_mel=0.3614.ckpt").write_bytes(b"x")
    (version / "checkpoints" / "last.ckpt").write_bytes(b"x")
    for epoch in range(30):
        write(
            version / "events.out.tfevents.1.host", *validation(100 * (epoch + 1), epoch, 2.0 + epoch / 100)
        )
    run = train_monitor.update(work)
    # 13 is not every 10th, not among the newest nor the best by val_mos, but its checkpoint is there
    assert 13 in run.samples and 14 not in run.samples
    assert run.saved == {13}


def test_an_old_state_is_read_again_and_dropped_audio_comes_back(tmp_path):
    work = tmp_path / "train"
    events = work / "lightning_logs" / "version_0" / "events.out.tfevents.1.host"
    for epoch in range(15):
        write(events, *validation(100 * (epoch + 1), epoch, 3.9 if epoch == 7 else 2.0))
    train_monitor.update(work)
    state_path = work / "monitor" / train_monitor.STATE_FILE
    state = json.loads(state_path.read_text())
    # what the old rules left: no epoch 7, offsets at the end of the file
    for _index, _text, name, _step in state["audio"].pop("7"):
        (work / "monitor" / "audio" / name).unlink()
    del state["version"]
    state_path.write_text(json.dumps(state))
    run = train_monitor.update(work)
    assert 7 in run.samples and run.samples[7][0].path.is_file()
    assert json.loads(state_path.read_text())["version"] == train_monitor.STATE_VERSION
    assert run.value("train_mel", 3) == 6.0  # the epoch means are not counted twice


def test_resume_replaces_the_epoch_and_reads_new_versions(tmp_path):
    work = tmp_path / "train"
    first = work / "lightning_logs" / "version_0" / "events.out.tfevents.1.host"
    write(first, *validation(100, 0, 2.0), *validation(200, 1, 2.2))
    train_monitor.update(work)
    # resumed: Lightning starts version_1 and validates epoch 1 again at another step
    second = work / "lightning_logs" / "version_1" / "events.out.tfevents.2.host"
    write(second, *validation(260, 1, 2.4), *validation(360, 2, 2.6))
    run = train_monitor.update(work)
    assert run.epochs == [2, 1, 0] and len(run.samples[1]) == len(SENTENCES)
    assert abs(run.value("val_mos", 1) - 2.4) < 1e-6  # float32 in the file


def test_no_logs_yet(tmp_path):
    run = train_monitor.update(tmp_path / "train")
    assert run.epochs == [] and run.last_epoch is None and run.metrics == {}
    assert not (tmp_path / "train" / "monitor").exists()  # nothing written while nothing happens


def test_chart_table_has_quality_and_both_mel_errors(tmp_path):
    work = tmp_path / "train"
    events = work / "lightning_logs" / "version_0" / "events.out.tfevents.1.host"
    write(events, *validation(100, 0, 2.0), *validation(200, 1, 2.5))
    run = train_monitor.update(work)
    assert run.value("train_mel", 0) == 3.0 and run.value("train_mel", 1) == 4.0  # mean of the epoch
    assert run.table() == [[0, 2.0, 1.0, 3.0], [1, 2.5, 0.5, 4.0]]
    # a reread from the saved state gives the same means
    assert train_monitor.update(work).table() == run.table()


def test_samples_are_exported_to_one_zip_with_an_index(tmp_path):
    import zipfile

    work = tmp_path / "train"
    version = work / "lightning_logs" / "version_0"
    (version / "checkpoints").mkdir(parents=True)
    (version / "checkpoints" / "epoch=13-val_mos=3.0000.ckpt").write_bytes(b"x")
    with pytest.raises(ValueError, match="no training samples"):
        train_monitor.export_samples(work, "base")
    for epoch in range(15):
        write(
            version / "events.out.tfevents.1.host", *validation(100 * (epoch + 1), epoch, 2.0 + epoch / 100)
        )
    path = train_monitor.export_samples(work, "pl-scratch medium/samples")
    assert path == work / "monitor" / train_monitor.SAMPLES_ZIP
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        page = archive.read("pl-scratch-medium-samples/index.html").decode()
        table = archive.read("pl-scratch-medium-samples/samples.csv").decode()
    # a folder per kept epoch, named with its quality; the epoch with a checkpoint says so
    assert "pl-scratch-medium-samples/epoch00013-mos2.13-checkpoint/00.wav" in names
    assert "pl-scratch-medium-samples/epoch00010-mos2.10/01.wav" in names
    assert (
        'data-epoch="13"' in page
        and 'data-ckpt="1"' in page
        and "epoch00013-mos2.13-checkpoint/00.wav" in page
    )
    assert table.splitlines()[0] == "epoch,val_mos,val_mel,checkpoint,file,sentence"
    assert SENTENCES[0] in table
    own = train_monitor.export_samples(work, "x", tmp_path / "out" / "x.zip")
    assert own.is_file() and not own.with_suffix(".tmp").exists()
