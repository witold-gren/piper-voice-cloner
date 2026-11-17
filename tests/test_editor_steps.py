"""Import → training → export through the editor's API (jobs run a fake `pvc`)."""

from __future__ import annotations

import io
import json
import sys
import zipfile

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from piper_voice_cloner import config as config_mod
from piper_voice_cloner.editor import steps
from piper_voice_cloner.editor.server import create_app

# the fake `pvc` writes its arguments to calls.json, so a test sees the command the editor ran
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
    return root, app, TestClient(app)


def last_call(root, app):
    app.state.jobs["current"].wait()
    return json.loads((root / "calls.json").read_text(encoding="utf-8"))


def voice(root, name="kasia", clips=3, **values):
    directory = root / "voices" / name
    config_mod.save(directory, config_mod.VoiceConfig(name=name, **values))
    if clips:
        (directory / "dataset").mkdir(parents=True)
        lines = "".join(f"c{i}|Zdanie numer {i}.\n" for i in range(clips))
        (directory / "dataset" / "metadata.csv").write_text(lines, encoding="utf-8")
    return directory


def checkpoint(directory, name):
    path = directory / "train" / "lightning_logs" / "version_0" / "checkpoints" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


def test_import_folders_are_found_and_the_import_runs(setup):
    root, app, client = setup
    voice(root, "tomek", clips=0, workflow="import")
    folder = root / "import" / "nagrania"
    (folder / "wav").mkdir(parents=True)
    (folder / "metadata.csv").write_text("a|Ala ma kota.\n\nb|Kot.\n", encoding="utf-8")
    (folder / "custom_metadata.csv").write_text("c|1. Pies.\n", encoding="utf-8")
    view = client.get("/api/voices/tomek/import").json()
    assert view["folders"] == [
        {"path": str(folder), "name": "nagrania", "lines": 2, "personas": ["custom_metadata.csv"]}
    ]
    assert view["clips"] == 0 and view["report"]["rows"] == 0
    body = {"folder": str(folder), "persona": "custom_metadata.csv", "verify": True}
    assert client.post("/api/voices/tomek/import", json=body).json()["state"] == "running"
    assert last_call(root, app) == [
        "import",
        "tomek",
        str(folder),
        "--metadata",
        str(folder / "metadata.csv"),
        "--persona",
        str(folder / "custom_metadata.csv"),
        "--verify",
    ]


def test_import_refuses_a_folder_without_metadata(setup, tmp_path):
    root, _app, client = setup
    voice(root, "tomek", clips=0)
    missing = client.post("/api/voices/tomek/import", json={"folder": str(tmp_path)})
    assert missing.status_code == 400 and missing.json()["error"] == "import_no_metadata"
    assert (
        client.post("/api/voices/tomek/import", json={"folder": " "}).json()["error"]
        == "import_folder_missing"
    )


def zip_bytes(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def test_a_zip_is_unpacked_into_the_import_folder(setup):
    root, _app, client = setup
    voice(root, "tomek", clips=0)
    data = zip_bytes({"moje/metadata.csv": b"a|Ala.\n", "moje/wav/a.wav": b"RIFF", "__MACOSX/x": b""})
    answer = client.post("/api/voices/tomek/import/upload", files={"file": ("moje.zip", data)}).json()
    target = root / "import" / "tomek"
    assert answer == {"folder": str(target)}
    assert (target / "metadata.csv").is_file() and (target / "wav" / "a.wav").is_file()
    assert not (target / "__MACOSX").exists()
    bad = client.post(
        "/api/voices/tomek/import/upload", files={"file": ("x.zip", zip_bytes({"a.txt": b"x"}))}
    )
    assert bad.status_code == 400 and bad.json()["error"] == "import_zip_failed"
    assert not target.exists()
    escape = zip_bytes({"metadata.csv": b"a|A.\n", "../../evil.txt": b"x"})
    client.post("/api/voices/tomek/import/upload", files={"file": ("e.zip", escape)})
    assert not (root / "evil.txt").exists() and not (root.parent / "evil.txt").exists()


def test_report_counts_reasons_and_offers_clips(setup):
    root, _app, client = setup
    directory = voice(root, "tomek", clips=2)
    (directory / "dataset" / "wav").mkdir()
    (directory / "dataset" / "wav" / "c0.wav").write_bytes(b"RIFF")
    report = "id,text,reason\nc0,Zdanie.,\nc1,Inne.,\nx,Mam 2 koty.,text:digits\n"
    (directory / "dataset" / "import_report.csv").write_text(report, encoding="utf-8")
    found = client.get("/api/voices/tomek/import").json()["report"]
    assert found["rows"] == 3 and found["kept"] == 2
    assert found["reasons"] == [["ok", 2], ["text:digits", 1]]
    assert found["kept_clips"] == [{"url": "voices/tomek/dataset/wav/c0.wav", "text": "Zdanie."}]
    assert client.get("/api/files/" + found["kept_clips"][0]["url"]).status_code == 200


def test_training_view_estimates_and_starts_with_the_chosen_epochs(setup):
    root, app, client = setup
    voice(root, "kasia", clips=1500)
    view = client.get("/api/voices/kasia/train").json()
    assert view["clips"] == 1500 and view["estimate"]["steps"] == 45
    assert view["base_choices"] == ["lessac"] and view["base_ready"] is False  # no bazowy-pl yet
    assert view["wanted_base"] == "bazowy-pl" and view["resume"] is None
    body = {"base": "lessac", "epochs": 700, "poweroff": True}
    job = client.post("/api/voices/kasia/train", json=body).json()
    assert job["poweroff"] is True
    assert last_call(root, app) == ["train", "kasia", "--base", "lessac"]
    assert config_mod.load(root / "voices" / "kasia").train.max_epochs == 700


def test_training_without_a_dataset_is_refused(setup):
    root, _app, client = setup
    voice(root, "pusty", clips=0)
    answer = client.post("/api/voices/pusty/train", json={"base": "lessac", "epochs": 10})
    assert answer.status_code == 400 and answer.json()["error"] == "train_no_dataset"


def test_resume_plan_explains_what_resuming_does(tmp_path):
    root = tmp_path
    directory = voice(root, "kasia")
    (directory / "train").mkdir()
    (directory / "train" / "run.json").write_text('{"start_epoch": 1113}', encoding="utf-8")
    checkpoint(directory, "epoch=1605-step=9000-val_mos=3.6123.ckpt")
    checkpoint(directory, "last.ckpt")
    # the plan was 1113 + 500 = 1613: resuming only finishes it
    assert steps.resume_plan(root, "kasia", 500) == {
        "reached": 1605,
        "run_start": 1113,
        "start": 1113,
        "end": 1613,
        "left": 8,
        "done": False,
    }
    # with the plan done the epochs count on top of the checkpoint
    assert steps.resume_plan(root, "kasia", 400) == {
        "reached": 1605,
        "run_start": 1113,
        "start": 1605,
        "end": 2005,
        "done": True,
    }
    listed = steps.checkpoint_list(root, "kasia")
    assert {item["name"]: (item["epoch"], item["metric"], item["value"]) for item in listed} == {
        "epoch=1605-step=9000-val_mos=3.6123.ckpt": (1605, "val_mos", 3.6123),
        "last.ckpt": (None, None, None),
    }


def test_queue_runs_the_picked_voices_in_order(setup):
    root, app, client = setup
    voice(root, "kasia")
    voice(root, "tomek")
    assert client.get("/api/queue").json()["voices"] == ["kasia", "tomek"]
    body = {"voices": ["tomek", "kasia"], "epochs": 500, "base": "lessac"}
    client.post("/api/queue", json=body)
    assert last_call(root, app) == ["train-queue", "tomek", "kasia", "--epochs", "500", "--base", "lessac"]
    assert client.post("/api/queue", json={**body, "voices": []}).json()["error"] == "queue_empty"
    assert client.post("/api/queue", json={**body, "voices": ["nobody"]}).status_code == 404


def test_chart_and_listening_follow_the_training(setup):
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "dev"))
    import tfevents

    root, _app, client = setup
    directory = voice(root, "kasia")
    assert client.get("/api/chart?voice=kasia").json() == {"target": None, "rows": []}
    tfevents.training(directory / "train", 100, 140, ["Ala ma kota.", "Kot ma Alę."], every=10)
    chart = client.get("/api/chart?voice=kasia").json()
    assert chart["target"] == "voice:kasia" and [row[0] for row in chart["rows"]] == [100, 110, 120, 130, 140]
    assert chart["best"]["mos"][0] in (120, 130, 140)
    heard = client.get("/api/listen?target=voice:kasia").json()
    assert heard["chosen"] == 140 and [s["text"] for s in heard["samples"]] == ["Ala ma kota.", "Kot ma Alę."]
    assert client.get("/api/files/" + heard["samples"][0]["url"]).status_code == 200
    assert client.get("/api/listen?target=voice:kasia&epoch=100").json()["chosen"] == 100
    assert client.get("/api/listen?target=voice:nobody").status_code == 404
    url = client.post("/api/listen/zip?target=voice:kasia").json()["url"]
    assert url.endswith(".zip") and client.get(f"/api/files/{url}").status_code == 200


def test_export_lists_checkpoints_and_files_and_runs(setup):
    root, app, client = setup
    directory = voice(root, "kasia", piper_name="pl_PL-kasia_glos")
    best = checkpoint(directory, "epoch=1574-step=1-val_mos=3.6000.ckpt")
    (directory / "export").mkdir()
    (directory / "export" / "pl_PL-kasia_glos-medium.onnx").write_bytes(b"x" * 2000)
    view = client.get("/api/voices/kasia/export").json()
    assert view["stem"] == "pl_PL-kasia_glos-medium"
    assert [c["path"] for c in view["checkpoints"]] == [str(best)]
    assert view["files"] == [
        {
            "name": "pl_PL-kasia_glos-medium.onnx",
            "url": "voices/kasia/export/pl_PL-kasia_glos-medium.onnx",
            "size": 2000,
        }
    ]
    client.post("/api/voices/kasia/export", json={"checkpoint": str(best)})
    assert last_call(root, app) == ["export", "kasia", "--checkpoint", str(best)]


def test_history_lists_logs_with_their_kind_and_voice(setup):
    root, _app, client = setup
    jobs = root / "jobs"
    jobs.mkdir(parents=True)
    (jobs / "20261116-101500-train-queue.log").write_text("queue 1/2: kasia\n", encoding="utf-8")
    (jobs / "20261116-091500-train-kuba_bajka.log").write_text("x\n", encoding="utf-8")
    (jobs / "20261115-080000-base-train.log").write_text("Epoch 1\n", encoding="utf-8")
    (jobs / "notes.log").write_text("", encoding="utf-8")
    history = client.get("/api/history").json()
    assert [(h["kind"], h["voice"], h["started"]) for h in history] == [
        ("train-queue", "", "2026-11-16 10:15:00"),
        ("train", "kuba_bajka", "2026-11-16 09:15:00"),
        ("base-train", "", "2026-11-15 08:00:00"),
    ]
    assert "queue 1/2" in client.get("/api/history/20261116-101500-train-queue.log").json()["log"]
    assert client.get("/api/history/..%2Fcalls.json").status_code == 404
