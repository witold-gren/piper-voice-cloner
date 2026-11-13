from __future__ import annotations

import csv

from piper_voice_cloner.dataset import Utterance, read_metadata, summarize, write_metadata


def test_write_is_readable_by_piper_csv_reader(tmp_path):
    utts = [
        Utterance("a1", 'Powiedziała: "tak", a potem wyszła.'),
        Utterance("b2", "Zwykłe zdanie bez cudzysłowu."),
    ]
    path = tmp_path / "metadata.csv"
    write_metadata(path, utts)
    # exactly how piper1-gpl reads it
    with path.open(encoding="utf-8") as handle:
        rows = list(csv.reader(handle, delimiter="|"))
    assert rows == [["a1.wav", utts[0].text], ["b2.wav", utts[1].text]]
    assert read_metadata(path) == utts


def test_read_legacy_ljspeech_without_extension(tmp_path):
    path = tmp_path / "metadata.csv"
    path.write_text(
        'abc|Ala ma kota.\n"x"|y\n\ndef.wav|"Powiedziała pani: ""porywczy"", nie."\n|pusty\n',
        encoding="utf-8",
    )
    utts = read_metadata(path)
    assert utts[0] == Utterance("abc", "Ala ma kota.")
    assert utts[-1] == Utterance("def", 'Powiedziała pani: "porywczy", nie.')
    assert len(utts) == 3


def test_summarize():
    rows = [{"reason": ""}, {"reason": "digits"}, {"reason": "digits"}, {"reason": "symbols"}]
    text = summarize(rows)
    assert text.splitlines()[0] == "kept 1 of 4"
    assert "  digits: 2" in text
