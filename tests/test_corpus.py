from __future__ import annotations

import pytest

from piper_voice_cloner import config, corpus


def letter_phonemizer(texts):
    """Fake phonemizer: letters as phonemes, spaces between words."""
    result = []
    for text in texts:
        phonemes = []
        for word in text.lower().split():
            phonemes += [c for c in word if c.isalpha()] + [" "]
        result.append(phonemes[:-1])
    return result


def test_units_include_diphones_within_words():
    assert corpus.units(["a", "b", " ", "c"]) == {"a", "b", "c", "a+b"}


def test_select_prefers_new_coverage():
    sentences = ["aaa aaa aaa", "aaa aaa", "xyz qwe", "aaa bbb"]
    chosen = corpus.select(sentences, letter_phonemizer(sentences), 2)
    assert chosen[0] == 2  # most new units
    assert 0 not in chosen[:1]
    assert len(chosen) == 2


def test_select_size_larger_than_pool():
    sentences = ["ala ma kota", "kot ma ale"]
    assert sorted(corpus.select(sentences, letter_phonemizer(sentences), 10)) == [0, 1]


def test_focus_bonus_changes_order():
    sentences = ["ab ab ab", "zz zz zz"]
    phonemes = letter_phonemizer(sentences)
    assert corpus.select(sentences, phonemes, 1, focus=["z"], focus_bonus=10.0) == [1]


def test_build_filters_and_deduplicates(tmp_path, pl):
    source = tmp_path / "transcripts.tsv"
    source.write_text(
        "id\ttranscript\n"
        "1\tZasłoniła na chwilę oczy dłonią.\n"
        "2\tzasłoniła na chwilę oczy dłonią!\n"
        "3\tSpotkanie zaczyna się o 12:30 w biurze.\n"
        "4\tWyciągnąłem rękę wzdłuż ściany.\n",
        encoding="utf-8",
    )
    extra = tmp_path / "extra.txt"
    extra.write_text("# comment\nKot śpi na ciepłej kanapie.\n\n", encoding="utf-8")
    prompts, report = corpus.build([source, extra], pl, 10, letter_phonemizer)
    texts = [text for _id, text in prompts]
    assert sorted(texts) == sorted(
        ["Zasłoniła na chwilę oczy dłonią.", "Wyciągnąłem rękę wzdłuż ściany.", "Kot śpi na ciepłej kanapie."]
    )
    reasons = sorted(row["reason"] for row in report if row["reason"])
    assert reasons == ["digits", "duplicate"]
    assert all(len(pid) == 16 for pid, _ in prompts)


def test_prompts_roundtrip(tmp_path):
    prompts = [("a1", 'Powiedział: "tak".'), ("b2", "Zdanie\tz tabulatorem nie występuje.")]
    path = tmp_path / "prompts.tsv"
    corpus.write_prompts(path, prompts)
    assert corpus.read_prompts(path) == prompts


def test_prompt_id_stable():
    assert corpus.prompt_id("Ala ma kota.") == corpus.prompt_id("Ala ma kota.")
    assert corpus.prompt_id("Ala ma kota.") != corpus.prompt_id("Ala ma psa.")


def test_bundled_kids_sentences_are_clean(pl):
    from piper_voice_cloner import text_filter

    paths = pl.prompt_paths()
    assert paths and all(p.is_file() for p in paths)
    sentences = [s for p in paths for s in corpus.read_sentences(p)]
    assert len(sentences) >= 60
    bad = [(s, text_filter.check(s, pl).reason) for s in sentences if not text_filter.check(s, pl).ok]
    assert bad == []


SENTENCES = (*(f"{n}.wav|Zdanie numer {n}." for n in range(11)), "x.wav|Zdanie numer 0.")


def imported_voice(root, name="marek", lines=SENTENCES):
    directory = root / name
    (directory / "dataset").mkdir(parents=True)
    (directory / "dataset" / "metadata.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return directory


def test_same_sentences_get_the_same_ids_in_every_voice(tmp_path):
    prompts = corpus.from_dataset(imported_voice(tmp_path) / "dataset" / "metadata.csv")
    assert len(prompts) == 11
    assert prompts[0] == (corpus.prompt_id("Zdanie numer 0."), "Zdanie numer 0.")


def test_use_dataset_sentences_keeps_every_sentence(tmp_path):
    source = imported_voice(tmp_path)
    directory = tmp_path / "alicja"
    config.save(directory, config.VoiceConfig(name="alicja", synthesis={"backend": "elevenlabs"}))
    assert corpus.use_dataset_sentences(directory, source) == 11
    assert len(corpus.read_prompts(directory / corpus.PROMPTS)) == 11
    cfg = config.load(directory)
    assert (cfg.target_clips, cfg.synthesis.overgenerate, cfg.quality.mos_drop_fraction) == (11, 1.0, 0.0)


def test_use_dataset_sentences_refuses_clips_of_other_sentences(tmp_path):
    source = imported_voice(tmp_path)
    directory = tmp_path / "alicja"
    config.save(directory, config.VoiceConfig(name="alicja"))
    (directory / "raw").mkdir()
    (directory / "raw" / "manifest.csv").write_text(
        "id,text,reference,seed,backend,rate\nold,Stare.,-,1,elevenlabs:v,24000\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="other sentences"):
        corpus.use_dataset_sentences(directory, source)
    assert not (directory / corpus.PROMPTS).exists()


def test_use_dataset_sentences_needs_enough_sentences(tmp_path):
    source = imported_voice(tmp_path, lines=SENTENCES[:9])
    with pytest.raises(ValueError, match="only 9 sentences"):
        corpus.use_dataset_sentences(tmp_path / "alicja", source)
