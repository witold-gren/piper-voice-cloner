from __future__ import annotations

import csv

import soundfile as sf

from piper_voice_cloner.dataset import read_metadata
from piper_voice_cloner.importer import Source, import_dataset

from .conftest import requires_ffmpeg, write_mp3_named_wav


def legacy_dataset(root):
    """Shape of the old ElevenLabs folders: metadata.csv + wav/ with MP3s named .wav."""
    wav = root / "wav"
    root.mkdir(parents=True, exist_ok=True)
    (root / "metadata.csv").write_text(
        "good1|Zasłoniła na chwilę oczy dłonią i parsknęła śmiechem.\n"
        "time|00:08:05\n"
        "date|12.05.1991\n"
        "nofile|To zdanie nie ma pliku z nagraniem.\n"
        'quote|"Powiedziała pani: ""porywczy"", nie: ""złośnik""."\n',
        encoding="utf-8",
    )
    (root / "custom_metadata.csv").write_text(
        "persona1|1. Czy mogę w czymś pomóc? Z przyjemnością udzielę wsparcia\n", encoding="utf-8"
    )
    for name in ("good1", "time", "date", "quote", "persona1"):
        write_mp3_named_wav(wav / f"{name}.wav", 1.5)
    return wav


@requires_ffmpeg
def test_import_cleans_text_and_converts_audio(tmp_path, pl):
    src = tmp_path / "legacy"
    wav = legacy_dataset(src)
    out = tmp_path / "out"
    rows = import_dataset(
        [Source(src / "metadata.csv"), Source(src / "custom_metadata.csv", persona=True)], wav, out, pl
    )
    reasons = {row["id"]: row["reason"] for row in rows}
    assert reasons == {
        "good1": "",
        "time": "text:digits",
        "date": "text:digits",
        "nofile": "missing_audio",
        "quote": "",
        "persona1": "",
    }
    kept = {utt.id: utt.text for utt in read_metadata(out / "metadata.csv")}
    assert kept["persona1"] == "Czy mogę w czymś pomóc? Z przyjemnością udzielę wsparcia"
    assert kept["quote"] == 'Powiedziała pani: "porywczy", nie: "złośnik".'
    assert set(kept) == {"good1", "quote", "persona1"}
    for utt_id in kept:
        info = sf.info(out / "wav" / f"{utt_id}.wav")
        assert (info.format, info.subtype, info.samplerate, info.channels) == ("WAV", "PCM_16", 22050, 1)
    assert not (out / "wav" / "time.wav").exists()
    with (out / "import_report.csv").open(encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == 6


@requires_ffmpeg
def test_import_verify_rejects_mismatch(tmp_path, pl):
    src = tmp_path / "legacy"
    wav = legacy_dataset(src)
    seen = []

    def verify(audio_16k, text):
        seen.append((len(audio_16k), text))
        return 0.5 if "parsknęła" in text else 0.0

    calls = []
    rows = import_dataset(
        [Source(src / "metadata.csv")],
        wav,
        tmp_path / "out",
        pl,
        verify=verify,
        progress=lambda done, total: calls.append((done, total)),
    )
    assert calls == [(n, len(rows)) for n in range(1, len(rows) + 1)]
    reasons = {row["id"]: row["reason"] for row in rows}
    assert reasons["good1"] == "asr_mismatch"
    assert reasons["quote"] == ""
    assert all(15000 < n < 30000 for n, _ in seen)  # 16 kHz audio of ~1.5 s


@requires_ffmpeg
def test_import_duplicate_ids_first_wins(tmp_path, pl):
    src = tmp_path / "legacy"
    write_mp3_named_wav(src / "wav" / "a.wav", 1.0)
    (src / "one.csv").write_text("a|Pierwsza wersja tego zdania.\n", encoding="utf-8")
    (src / "two.csv").write_text("a|Druga wersja tego zdania.\n", encoding="utf-8")
    import_dataset([Source(src / "one.csv"), Source(src / "two.csv")], src / "wav", tmp_path / "o", pl)
    assert read_metadata(tmp_path / "o" / "metadata.csv")[0].text == "Pierwsza wersja tego zdania."


@requires_ffmpeg
def test_import_rejects_too_short_audio(tmp_path, pl):
    src = tmp_path / "legacy"
    write_mp3_named_wav(src / "wav" / "a.wav", 0.3)
    (src / "metadata.csv").write_text("a|Bardzo krótkie nagranie tutaj.\n", encoding="utf-8")
    rows = import_dataset([Source(src / "metadata.csv")], src / "wav", tmp_path / "o", pl)
    assert rows[0]["reason"] == "duration"


@requires_ffmpeg
def test_import_keeps_short_replies(tmp_path, pl):
    src = tmp_path / "legacy"
    write_mp3_named_wav(src / "wav" / "a.wav", 1.0)
    (src / "metadata.csv").write_text("a|Usiądziesz?\n", encoding="utf-8")
    rows = import_dataset([Source(src / "metadata.csv")], src / "wav", tmp_path / "o", pl)
    assert rows[0]["reason"] == ""
