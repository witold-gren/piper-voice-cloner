"""Base model, settings, the machine through Home Assistant and each voice's voice.yaml (API)."""

from __future__ import annotations

import json
import sys
import time

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from piper_voice_cloner import config as config_mod, ha, power
from piper_voice_cloner.editor import settings
from piper_voice_cloner.editor.server import create_app

TOKEN = "t" * 40  # what Home Assistant's long-lived tokens look like (length)
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
    config_mod.save(root / "voices" / "kasia", config_mod.VoiceConfig(name="kasia"))
    return root, app, TestClient(app)


def last_call(root, app, slot="current"):
    app.state.jobs[slot].wait()
    return json.loads((root / "calls.json").read_text(encoding="utf-8"))


def base_dataset(root):
    dataset = root / "bases" / "pl-scratch" / "dataset"
    dataset.mkdir(parents=True)
    (dataset / "metadata.csv").write_text("a|Ala.\n", encoding="utf-8")
    return dataset


def test_base_steps_run_their_commands(setup):
    root, app, client = setup
    view = client.get("/api/base").json()
    assert view["ready"] is False and view["dataset"] is False and view["runs"] == []
    assert client.post("/api/base/train", json={"epochs": 10}).json()["error"] == "base_no_dataset"
    assert client.post("/api/base/prepare", json={"folder": " "}).json()["error"] == "base_dir_missing"
    client.post("/api/base/prepare", json={"folder": "/data/voices/kasia/dataset", "audio_dir": "wav"})
    assert last_call(root, app) == ["base", "prepare", "/data/voices/kasia/dataset", "--audio-dir", "wav"]
    base_dataset(root)
    client.post("/api/base/train", json={"epochs": 3000, "quality": "high", "batch": 16, "poweroff": True})
    assert last_call(root, app) == [
        "base",
        "train",
        "--max-epochs",
        "3000",
        "--quality",
        "high",
        "--batch-size",
        "16",
    ]
    assert (
        client.post("/api/base/train", json={"epochs": 5, "quality": "huge"}).json()["error"]
        == "base_quality_unknown"
    )
    # the rating runs in the second slot, next to a training
    job = client.post("/api/base/score", json={"sample": 300}).json()
    assert job["kind"] == "base-score"
    assert last_call(root, app, "side") == ["base", "score", "--sample", "300"]


def test_base_choice_only_from_its_own_checkpoints(setup):
    root, app, client = setup
    ckpt = root / "bases" / "pl-scratch" / "train" / "lightning_logs" / "version_0" / "checkpoints"
    ckpt.mkdir(parents=True)
    best = ckpt / "epoch=1093-step=1-val_mos=3.7507.ckpt"
    best.write_bytes(b"")
    view = client.get("/api/base").json()
    (item,) = view["checkpoints"]
    assert item["label"] == f"medium · {best.name}" and item["path"] == str(best)
    assert item["quality"] == "medium" and item["epoch"] == 1093  # shown like a voice's export list
    assert item["metric"] == "val_mos" and item["value"] == 3.7507
    client.post("/api/base/select", json={"checkpoint": str(best)})
    assert last_call(root, app) == ["base", "select", str(best)]
    client.post("/api/base/export", json={"checkpoint": str(best)})
    assert last_call(root, app) == ["base", "export", "--checkpoint", str(best)]
    assert (
        client.post("/api/base/select", json={"checkpoint": "/etc/passwd"}).json()["error"]
        == "base_checkpoint"
    )


def test_base_score_report_with_clips(setup):
    root, _app, client = setup
    dataset = base_dataset(root)
    (dataset / "wav").mkdir()
    for clip in ("a", "b", "c"):
        (dataset / "wav" / f"{clip}.wav").write_bytes(b"RIFF")
    report = {
        "total": 100,
        "scores": {"a": 2.5, "b": 3.5, "c": 4.2},
        "texts": {"a": "Ala.", "b": "Kot.", "c": "Pies."},
    }
    (dataset / "utmos.json").write_text(json.dumps(report), encoding="utf-8")
    lines = "".join(f"{clip}|x\n" for clip in "abc") + "".join(f"z{i}|x\n" for i in range(97))
    (dataset / "metadata.csv").write_text(lines, encoding="utf-8")  # 100 clips, 3 of them scored
    score = client.get("/api/base").json()["score"]
    assert score["count"] == 3 and score["total"] == 100 and score["median"] == 3.5
    assert score["worst"][0] == {"url": "bases/pl-scratch/dataset/wav/a.wav", "text": "2.50 · Ala."}
    assert score["best"][0]["text"] == "4.20 · Pies."


def test_elevenlabs_key_is_saved_and_never_returned(setup):
    _root, _app, client = setup
    assert client.get("/api/settings").json()["elevenlabs"] == {"key": False}
    assert client.post("/api/settings/elevenlabs", json={"key": " sk_secret "}).json() == {"key": True}
    assert "sk_secret" not in client.get("/api/settings").text
    assert client.post("/api/settings/elevenlabs", json={"key": ""}).json() == {"key": False}


def test_home_assistant_connection_and_power_settings(setup, monkeypatch):
    _root, _app, client = setup
    assert client.get("/api/settings/ha/entities").json()["error"] == "ha_missing"
    bad_token = client.post("/api/settings/ha", json={"url": "http://ha.local:8123", "token": "short"})
    assert bad_token.status_code == 400 and bad_token.json()["error"] == "ha_invalid"
    saved = client.post("/api/settings/ha", json={"url": "http://ha.local:8123", "token": TOKEN}).json()
    assert saved["ha"] == {"url": "http://ha.local:8123", "token_saved": True, "token_rejected": False}
    assert TOKEN not in client.get("/api/settings").text
    entities = [
        {"entity_id": "switch.maszyna_gpu", "attributes": {"friendly_name": "Maszyna GPU"}},
        {"entity_id": "sensor.gniazdko_moc", "attributes": {"unit_of_measurement": "W"}},
        {"entity_id": "sensor.temperatura", "attributes": {"unit_of_measurement": "°C"}},
    ]
    monkeypatch.setattr(ha.Client, "entities", lambda self, timeout=10: entities)
    found = client.get("/api/settings/ha/entities").json()
    assert found["switches"] == [{"id": "switch.maszyna_gpu", "name": "Maszyna GPU"}]
    assert found["sensors"] == [{"id": "sensor.gniazdko_moc", "name": ""}] and found["count"] == 3
    body = {"switch": "switch.maszyna_gpu", "sensor": "sensor.gniazdko_moc", "off_watts": 5}
    assert client.post("/api/settings/power", json=body).json()["power"]["switch"] == "switch.maszyna_gpu"
    bad = client.post("/api/settings/power", json={**body, "switch": "light.lampa"})
    assert bad.status_code == 400 and bad.json()["error"] == "power_invalid"
    assert client.delete("/api/settings/ha").json()["ha"]["token_saved"] is False


def connect(monkeypatch, calls, state="on", watts="230"):
    ha.save_connection("http://ha.local:8123", TOKEN)
    power.save_power(power.PowerSettings("switch.maszyna_gpu", "sensor.gniazdko_moc", 5))
    states = {"switch.maszyna_gpu": {"state": state}, "sensor.gniazdko_moc": {"state": watts}}
    monkeypatch.setattr(ha.Client, "entity_state", lambda self, entity, timeout=5: states[entity])
    monkeypatch.setattr(ha.Client, "call_service", lambda self, *args, **kw: calls.append(args))


def test_machine_state_is_read_in_the_background(setup, monkeypatch):
    _root, app, client = setup
    assert client.get("/api/state").json()["machine"] is None  # not set up: nothing to show
    connect(monkeypatch, [])
    app.state.machine.forget()
    first = client.get("/api/state").json()
    assert first["can_power_off"] is True and first["machine"]["machine"] in ("checking", "on")
    for _ in range(50):
        machine = client.get("/api/state").json()["machine"]
        if machine["machine"] == "on":
            break
        time.sleep(0.02)
    assert machine == {"switch": "on", "watts": 230.0, "machine": "on"}


def test_machine_off_switches_through_home_assistant_unless_a_job_runs(setup, monkeypatch, no_real_poweroff):
    root, app, client = setup
    connect(monkeypatch, [])
    assert client.post("/api/machine/off").json() == {"ok": True}
    assert no_real_poweroff == ["power_off"]
    script = root.parent / "slow.py"
    script.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
    app.state.jobs["current"].pvc = [sys.executable, str(script)]
    app.state.start("train", "kasia", ["train", "kasia"])
    busy = client.post("/api/machine/off")
    assert busy.status_code == 409 and busy.json() | {"kind": "train"} == busy.json()
    app.state.jobs["current"].stop()
    app.state.jobs["current"].wait()


def test_power_off_command_for_the_container(monkeypatch, capsys):
    monkeypatch.setattr(power, "power_off", power.switch_off_machine)  # the real one, with a fake HA
    assert power.main(["on"]) == 2
    assert power.main(["off"]) == 1  # nothing set up
    assert "Home Assistant" in capsys.readouterr().err
    calls = []
    connect(monkeypatch, calls)
    assert power.main(["off"]) == 0
    assert calls == [("switch", "turn_off", "switch.maszyna_gpu")]


def test_voice_yaml_saves_with_history_and_refuses_bad_values(setup):
    root, _app, client = setup
    view = client.get("/api/voices/kasia/settings").json()
    assert view["config"]["target_clips"] == 2000 and view["history"] == []
    text = view["yaml"].replace("target_clips: 2000", "target_clips: 1500")
    saved = client.post("/api/voices/kasia/settings", json={"text": text}).json()
    assert saved["config"]["target_clips"] == 1500
    assert len(saved["history"]) == 1 and "target_clips: 2000" in saved["history"][0]["text"]
    bad = client.post("/api/voices/kasia/settings", json={"text": text.replace("1500", "5")})
    assert (
        bad.status_code == 400
        and bad.json()["error"] == "yaml_invalid"
        and "target_clips" in bad.json()["message"]
    )
    renamed = client.post(
        "/api/voices/kasia/settings", json={"text": text.replace("name: kasia", "name: inna")}
    )
    assert renamed.json()["error"] == "yaml_invalid"
    broken = client.post("/api/voices/kasia/settings", json={"text": "name: [kasia"})
    assert broken.json()["error"] == "yaml_invalid"
    assert config_mod.load(root / "voices" / "kasia").target_clips == 1500


def test_history_keeps_the_newest_versions(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "HISTORY", 3)
    config_mod.save(tmp_path / "voices" / "kasia", config_mod.VoiceConfig(name="kasia"))
    for clips in range(100, 106):
        text = (tmp_path / "voices" / "kasia" / "voice.yaml").read_text(encoding="utf-8")
        settings.save_voice_yaml(
            tmp_path, "kasia", text.replace(str(clips - 1) if clips > 100 else "2000", str(clips))
        )
    history = settings.voice_history(tmp_path, "kasia")
    assert len(history) == 3 and "target_clips: 104" in history[0]["text"]


def test_rename_moves_the_voice_but_not_while_it_trains(setup):
    root, app, client = setup
    assert client.post(
        "/api/voices/kasia/rename", json={"name": "Kasia Nowa", "piper_name": "pl_PL-kasia"}
    ).json() == {"name": "kasia_nowa"}
    assert config_mod.load(root / "voices" / "kasia_nowa").piper_name == "pl_PL-kasia"
    script = root.parent / "slow.py"
    script.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
    app.state.jobs["current"].pvc = [sys.executable, str(script)]
    app.state.start("train", "kasia_nowa", ["train", "kasia_nowa"])
    busy = client.post("/api/voices/kasia_nowa/rename", json={"name": "x"})
    assert busy.status_code == 409 and busy.json()["error"] == "rename_busy"
    app.state.jobs["current"].stop()
    app.state.jobs["current"].wait()


def test_an_older_imported_voice_gets_its_way_in_voice_yaml_once(setup):
    """The tree said "Own recordings" (import report), the form said "Cloning" (voice.yaml without
    `workflow`); saving the form could keep the wrong way. Opening the settings fixes the one line."""
    root, _, client = setup
    voice = root / "voices" / "kasia"
    path = voice / config_mod.CONFIG_FILE
    text = "# Kasia, imported from the old set\n" + path.read_text(encoding="utf-8").replace(
        "workflow: clone\n", ""
    )
    path.write_text(text, encoding="utf-8")
    (voice / "dataset").mkdir()
    (voice / "dataset" / "import_report.csv").write_text("id,status\n", encoding="utf-8")
    view = client.get("/api/voices/kasia/settings").json()
    assert view["config"]["workflow"] == "import"
    saved = path.read_text(encoding="utf-8")
    assert "workflow: import" in saved and saved.startswith("# Kasia, imported from the old set\n")
    assert saved.replace("workflow: import\n", "") == text  # only that line
    history = view["history"]
    assert len(history) == 1 and "import report" in json.dumps(history)
    client.get("/api/voices/kasia/settings")
    assert len(client.get("/api/voices/kasia/settings").json()["history"]) == 1  # once


def test_with_workflow_changes_or_adds_one_line():
    assert settings.with_workflow("name: a\nworkflow: clone\n", "import") == "name: a\nworkflow: import\n"
    assert settings.with_workflow("# c\nname: a\nlanguage: pl\n", "import") == (
        "# c\nname: a\nworkflow: import\nlanguage: pl\n"
    )


def test_voice_recordings_are_rated_and_the_kept_scores_shown(setup):
    root, app, client = setup
    assert client.post("/api/voices/kasia/score", json={"sample": 0}).json()["error"] == "train_no_dataset"
    dataset = root / "voices" / "kasia" / "dataset"
    (dataset / "wav").mkdir(parents=True)
    (dataset / "metadata.csv").write_text("a|Ala.\nb|Kot.\nc|Pies.\n", encoding="utf-8")
    view = client.get("/api/voices/kasia/score").json()
    assert view["dataset"] is True and view["score"] is None and view["clips"] == 3
    job = client.post("/api/voices/kasia/score", json={"sample": 0}).json()
    assert job["kind"] == "score"
    assert last_call(root, app, "side") == ["score", "kasia", "--sample", "0"]
    for clip in ("a", "b", "c"):
        (dataset / "wav" / f"{clip}.wav").write_bytes(b"RIFF")
    report = {
        "total": 3,
        "scores": {"a": 2.4, "b": 3.1, "c": 4.2},
        "texts": {"a": "Ala.", "b": "Kot.", "c": "Pies."},
    }
    (dataset / "utmos.json").write_text(json.dumps(report), encoding="utf-8")
    score = client.get("/api/voices/kasia/score").json()["score"]
    assert score["median"] == 3.1 and score["below"] == {"2.5": 1, "3.0": 1, "3.3": 2}
    assert score["worst"][0] == {"url": "voices/kasia/dataset/wav/a.wav", "text": "2.40 · Ala."}


def test_weak_recordings_are_taken_out_by_a_job(setup):
    root, app, client = setup
    dataset = root / "voices" / "kasia" / "dataset"
    dataset.mkdir(parents=True)
    (dataset / "metadata.csv").write_text("a|Ala.\nb|Kot.\n", encoding="utf-8")
    view = client.get("/api/voices/kasia/score").json()
    assert view["clips"] == 2 and view["target"] == 1500 and view["pruned"] == []
    assert client.post("/api/voices/kasia/prune", json={}).json()["error"] == "prune_choose"
    both = {"below": 3.0, "keep_best": 2}
    assert client.post("/api/voices/kasia/prune", json=both).json()["error"] == "prune_choose"
    job = client.post("/api/voices/kasia/prune", json={"below": 3.0}).json()
    assert job["kind"] == "prune" and last_call(root, app) == ["prune", "kasia", "--below", "3.0"]
    client.post("/api/voices/kasia/prune", json={"keep_best": 3000})
    assert last_call(root, app) == ["prune", "kasia", "--keep-best", "3000"]


def test_every_scored_clip_one_page_at_a_time(setup):
    root, _app, client = setup
    dataset = root / "voices" / "kasia" / "dataset"
    (dataset / "wav").mkdir(parents=True)
    (dataset / "metadata.csv").write_text("a|Ala.\nb|Kot.\nc|Pies.\nn|Nowe.\n", encoding="utf-8")
    for clip in ("a", "b", "x"):
        (dataset / "wav" / f"{clip}.wav").write_bytes(b"RIFF")
    report = {
        "scores": {"a": 2.4, "b": 3.6, "c": 2.9, "x": 1.5},  # x was taken out of the dataset
        "texts": {"b": "Kot.", "x": "Stare."},  # a and c: their text comes from metadata.csv
    }
    (dataset / "utmos.json").write_text(json.dumps(report), encoding="utf-8")
    view = client.get("/api/voices/kasia/score").json()
    assert view["values"] == [2.4, 2.9, 3.6] and view["clips"] == 4  # n is not scored yet
    page = client.get("/api/voices/kasia/clips").json()
    assert (
        [c["id"] for c in page["clips"]] == ["a", "c", "b"] and page["total"] == 3 and page["unscored"] == 1
    )
    assert page["clips"][0] == {
        "id": "a",
        "score": 2.4,
        "text": "Ala.",
        "url": "voices/kasia/dataset/wav/a.wav",
    }
    assert page["clips"][1]["url"] is None  # no file to listen to
    best = client.get("/api/voices/kasia/clips?order=desc&limit=1&offset=1").json()
    assert [c["id"] for c in best["clips"]] == ["c"] and best["total"] == 3
    assert [c["id"] for c in client.get("/api/voices/kasia/clips?below=3.0").json()["clips"]] == ["a", "c"]
    out = client.get("/api/voices/kasia/clips?where=out").json()
    assert [c["id"] for c in out["clips"]] == ["x"] and out["clips"][0]["text"] == "Stare."
    assert client.get("/api/voices/kasia/clips?where=nowhere").json()["error"] == "clips_bad_query"
