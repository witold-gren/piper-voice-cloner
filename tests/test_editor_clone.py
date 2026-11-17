"""The cloning way through the editor's API: uploads, the commands it runs, ElevenLabs."""

from __future__ import annotations

import json
import sys

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from piper_voice_cloner import config as config_mod
from piper_voice_cloner.backends import elevenlabs
from piper_voice_cloner.editor.server import create_app

FAKE = """import json, sys
from pathlib import Path
root = Path(sys.argv[sys.argv.index("--root") + 1])
(root / "calls.json").write_text(json.dumps(sys.argv[sys.argv.index("--root") + 2:]))
"""


@pytest.fixture
def setup(tmp_path):
    root = tmp_path / "root"
    script = tmp_path / "fake.py"
    script.write_text(FAKE, encoding="utf-8")
    app = create_app(root, pvc=[sys.executable, str(script)], gpu=False)
    config_mod.save(root / "voices" / "ola", config_mod.VoiceConfig(name="ola", target_clips=100))
    return root, app, TestClient(app)


def last_call(root, app):
    app.state.jobs["current"].wait()
    return json.loads((root / "calls.json").read_text(encoding="utf-8"))


def test_recording_uploads_and_runs_as_a_job(setup):
    root, app, client = setup
    assert client.post("/api/voices/ola/reference", json={}).json()["error"] == "reference_no_files"
    sent = client.post(
        "/api/voices/ola/reference/upload",
        files=[("files", ("glos.m4a", b"x")), ("files", ("drugi.wav", b"y"))],
    )
    assert sent.json() == {"files": ["glos.m4a", "drugi.wav"]}
    refused = client.post("/api/voices/ola/reference/upload", files=[("files", ("notatki.txt", b"x"))])
    assert refused.status_code == 400 and refused.json()["error"] == "upload_kind"
    view = client.get("/api/voices/ola/reference").json()
    assert view["uploads"] == ["drugi.wav", "glos.m4a"] and view["info"] == {}
    client.post("/api/voices/ola/reference", json={"embed": False})
    uploads = root / "voices" / "ola" / "reference" / "uploads"
    assert last_call(root, app) == [
        "reference",
        "ola",
        str(uploads / "drugi.wav"),
        str(uploads / "glos.m4a"),
        "--no-embed",
    ]
    assert client.delete("/api/voices/ola/reference/uploads/glos.m4a").json() == {"ok": True}
    assert client.delete("/api/voices/ola/reference/uploads/../voice.yaml").status_code == 404
    assert (root / "voices" / "ola" / "voice.yaml").is_file()


def test_prepared_recording_shows_clips_and_the_short_warning(setup):
    root, _app, client = setup
    reference = root / "voices" / "ola" / "reference"
    (reference / "clean").mkdir(parents=True)
    (reference / "clean" / "ref_00.wav").write_bytes(b"RIFF")
    info = {"prompts": ["ref_00.wav"], "seconds": 9.5, "min_similarity": 0.5}
    (reference / "reference.json").write_text(json.dumps(info), encoding="utf-8")
    view = client.get("/api/voices/ola/reference").json()
    assert view["short"] is True and view["clips"] == [
        {"url": "voices/ola/reference/clean/ref_00.wav", "text": "ref_00.wav"}
    ]


def test_sentences_from_files_and_the_bundled_set(setup):
    root, app, client = setup
    client.post("/api/voices/ola/corpus/upload", files=[("files", ("bajki.txt", b"Ala ma kota.\n"))])
    view = client.get("/api/voices/ola/corpus").json()
    assert view["sources"] == ["bajki.txt"] and view["default_size"] == 130 and view["prompts"] == 0
    client.post("/api/voices/ola/corpus", json={"bundled": False, "size": 50})
    source = root / "voices" / "ola" / "sources" / "bajki.txt"
    assert last_call(root, app) == ["corpus", "ola", "--source", str(source), "--no-bundled", "--size", "50"]
    client.delete("/api/voices/ola/corpus/sources/bajki.txt")
    assert (
        client.post("/api/voices/ola/corpus", json={"bundled": False}).json()["error"] == "corpus_no_sources"
    )
    client.post("/api/voices/ola/corpus", json={"bundled": True})
    assert last_call(root, app) == ["corpus", "ola"]


def test_audition_needs_sentences_and_applies_a_result(setup):
    root, app, client = setup
    directory = root / "voices" / "ola"
    assert client.post("/api/voices/ola/audition", json={}).json()["error"] == "audition_no_sentences"
    (directory / "prompts.tsv").write_text("id\ttext\np1\tAla ma kota.\n", encoding="utf-8")
    client.post("/api/voices/ola/audition", json={"count": 5})
    assert last_call(root, app) == ["audition", "ola", "--count", "5"]
    (directory / "audition" / "a").mkdir(parents=True)
    (directory / "audition" / "a" / "p1.wav").write_bytes(b"RIFF")
    result = {
        "slug": "a",
        "options": {"cfg_weight": 0.3},
        "score": 0.5,
        "cer": 0.01,
        "similarity": 0.6,
        "mos": 3.2,
    }
    results = [{**result, "clips": [{"file": "a/p1.wav", "text": "Ala ma kota."}]}]
    (directory / "audition" / "results.json").write_text(json.dumps(results), encoding="utf-8")
    view = client.get("/api/voices/ola/audition").json()
    assert view["chosen"] == "a" and view["rows"][0][:2] == [1, "a"]
    assert view["clips"] == [{"url": "voices/ola/audition/a/p1.wav", "text": "Ala ma kota."}]
    assert client.post("/api/voices/ola/audition/apply", json={"value": "a"}).json() == {
        "options": {"cfg_weight": 0.3}
    }
    assert config_mod.load(directory).synthesis.options == {"cfg_weight": 0.3}
    assert client.post("/api/voices/ola/audition/apply", json={"value": "zz"}).status_code == 400


def test_generating_switches_the_model_and_starts(setup):
    root, app, client = setup
    directory = root / "voices" / "ola"
    assert client.post("/api/voices/ola/synthesize", json={}).json()["error"] == "synthesize_no_sentences"
    (directory / "prompts.tsv").write_text("id\ttext\np1\tAla ma kota.\np2\tKot.\n", encoding="utf-8")
    view = client.post("/api/voices/ola/synthesize/backend", json={"value": "elevenlabs"}).json()
    assert view["backend"] == "elevenlabs" and view["elevenlabs"]["missing_sentences"] == 2
    assert view["elevenlabs"]["missing_characters"] == len("Ala ma kota.") + len("Kot.")
    assert client.post("/api/voices/ola/synthesize/backend", json={"value": "magic"}).status_code == 400
    client.post("/api/voices/ola/synthesize", json={"limit": 20})
    assert last_call(root, app) == ["synthesize", "ola", "--limit", "20"]
    (directory / "raw").mkdir()
    timing = {"clips": 10, "seconds": 40.0, "audio_seconds": 30.0, "device": "cuda"}
    (directory / "raw" / "timing.json").write_text(json.dumps(timing), encoding="utf-8")
    found = client.get("/api/voices/ola/synthesize").json()["timing"]
    assert found["per_clip"] == 4.0 and found["estimate"] == 8.0 and found["speed"] == 0.75


def test_an_imported_voice_keeps_its_model(setup):
    root, _app, client = setup
    dataset = root / "voices" / "ola" / "dataset"
    dataset.mkdir(parents=True)
    (dataset / "import_report.csv").write_text("id,text,reason\n", encoding="utf-8")
    answer = client.post("/api/voices/ola/synthesize/backend", json={"value": "elevenlabs"})
    assert answer.status_code == 400 and answer.json()["error"] == "backend_imported"


def test_elevenlabs_voices_credits_and_the_choice(setup, monkeypatch):
    root, _app, client = setup
    monkeypatch.setattr(
        elevenlabs, "list_voices", lambda: [{"id": "v1", "name": "Alicja", "category": "cloned"}]
    )
    monkeypatch.setattr(
        elevenlabs, "optional_credits", lambda: elevenlabs.Credits(used=10, limit=100, reset=0)
    )
    account = client.get("/api/elevenlabs/voices").json()
    assert account == {
        "voices": [{"id": "v1", "name": "Alicja", "category": "cloned"}],
        "credits": {"left": 90, "limit": 100, "reset": 0},
    }
    chosen = client.post("/api/voices/ola/synthesize/elevenlabs-voice", json={"value": "v1"}).json()
    assert chosen["elevenlabs"]["voice_name"] == "Alicja"
    assert config_mod.load(root / "voices" / "ola").synthesis.elevenlabs_voice_id == "v1"
    unknown = client.post("/api/voices/ola/synthesize/elevenlabs-voice", json={"value": "zz"})
    assert unknown.json()["error"] == "elevenlabs_unknown_voice"

    def broken():
        raise RuntimeError("401 wrong key")

    monkeypatch.setattr(elevenlabs, "list_voices", broken)
    failed = client.get("/api/elevenlabs/voices")
    assert failed.status_code == 502 and "401" in failed.json()["message"]


def test_sentence_set_of_another_voice_runs_as_a_job(setup):
    root, app, client = setup
    config_mod.save(root / "voices" / "kasia", config_mod.VoiceConfig(name="kasia"))
    client.post("/api/voices/ola/synthesize/sentences", json={"value": "kasia"})
    assert last_call(root, app) == ["sentences", "ola", "kasia"]
    assert client.post("/api/voices/ola/synthesize/sentences", json={"value": "nobody"}).status_code == 404


def test_filter_runs_with_the_chosen_checks(setup):
    root, app, client = setup
    assert client.post("/api/voices/ola/filter", json={}).json()["error"] == "filter_nothing"
    raw = root / "voices" / "ola" / "raw"
    raw.mkdir()
    (raw / "manifest.csv").write_text(
        "id,text,reference,seed,backend,rate\np1,Ala.,r,1,chatterbox,24000\n", encoding="utf-8"
    )
    assert client.get("/api/voices/ola/filter").json()["raw"] == 1
    client.post("/api/voices/ola/filter", json={"target": 80, "similarity": False, "mos": False})
    assert last_call(root, app) == ["filter", "ola", "--target", "80", "--no-similarity", "--no-mos"]
