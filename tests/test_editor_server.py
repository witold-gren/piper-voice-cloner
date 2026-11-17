"""The editor's HTTP side: login, page, state, voices, jobs and files (no browser)."""

from __future__ import annotations

import json
import sys

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from piper_voice_cloner import config as config_mod
from piper_voice_cloner.editor import api
from piper_voice_cloner.editor.auth import COOKIE, Login
from piper_voice_cloner.editor.server import create_app
from piper_voice_cloner.jobs import JobManager


def fake_pvc(tmp_path, body: str) -> list[str]:
    script = tmp_path / "fake_pvc.py"
    script.write_text(body, encoding="utf-8")
    return [sys.executable, str(script)]


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / "root", pvc=fake_pvc(tmp_path, "print('progress job 1/2')\n"), gpu=False)
    return TestClient(app)


def make_voice(root, name, **values):
    cfg = config_mod.VoiceConfig(name=name, **values)
    config_mod.save(root / "voices" / name, cfg)
    return root / "voices" / name


def test_login_parses_user_and_password():
    assert Login.parse(None) is None
    assert Login.parse("") is None
    login = Login.parse("admin:se:cret")
    assert (login.user, login.password) == ("admin", "se:cret")
    with pytest.raises(ValueError):
        Login.parse("nopassword")
    assert login.check("admin", "se:cret") and not login.check("admin", "x")
    assert login.valid(login.token()) and not login.valid("x") and not login.valid(None)
    assert Login("admin", "other").token() != login.token()  # a new password logs everybody out


def test_pages_and_api_need_the_login(tmp_path):
    login = Login("admin", "pass")
    client = TestClient(create_app(tmp_path, login=login, gpu=False), follow_redirects=False)
    health = client.get("/api/health")  # the container's health check, without login
    assert health.status_code == 200 and health.json()["ok"] is True and health.json()["version"]
    assert client.get("/").headers["location"] == "/login"
    assert client.get("/api/state").status_code == 401
    assert client.get("/static/icon.svg").status_code == 200  # the login page shows the logo
    assert "Hasło" in client.get("/login", headers={"accept-language": "pl-PL"}).text
    wrong = client.post("/login", data={"user": "admin", "password": "no"})
    assert wrong.headers["location"] == "/login?failed=1"
    assert "data-login-error" in client.get("/login?failed=1").text
    right = client.post("/login", data={"user": "admin", "password": "pass"})
    assert right.status_code == 303 and right.headers["location"] == "/"
    cookie = right.cookies[COOKIE]
    assert "httponly" in right.headers["set-cookie"].lower()
    client.cookies.set(COOKIE, cookie)
    assert client.get("/api/state").status_code == 200
    assert client.get("/").status_code == 200


def test_page_and_its_files_are_served(client):
    page = client.get("/")
    assert "<pvc-editor>" in page.text and "/static/editor-app.js" in page.text
    assert client.get("/static/editor-app.js").status_code == 200
    assert client.get("/static/vendor/lit-all.min.js").status_code == 200
    assert client.get("/static/../server.py").status_code == 404
    assert client.get("/static/nothing.js").status_code == 404


def test_state_lists_voices_with_the_steps_of_their_way(tmp_path):
    root = tmp_path / "root"
    make_voice(root, "kasia", workflow="import")
    make_voice(root, "alicja")
    old = make_voice(root, "tomek")  # imported by an older version: no workflow in voice.yaml
    (old / "dataset").mkdir()
    (old / "dataset" / api.IMPORT_REPORT).write_text("id\n", encoding="utf-8")
    (old / "dataset" / "metadata.csv").write_text("a|Ala ma kota.\nb|Kot ma Alę.\n", encoding="utf-8")
    state = TestClient(create_app(root, gpu=False)).get("/api/state").json()
    voices = {voice["name"]: voice for voice in state["voices"]}
    assert [step["key"] for step in voices["alicja"]["steps"]] == list(api.CLONE_STEPS)
    assert [step["key"] for step in voices["kasia"]["steps"]] == list(api.IMPORT_STEPS)
    assert voices["tomek"]["workflow"] == "import"
    assert voices["tomek"]["steps"][0] == {"key": "import", "done": True, "detail": "2"}
    assert state["jobs"] == {"current": {"state": "idle"}, "side": {"state": "idle"}}
    assert state["base_ready"] is False


def test_a_broken_voice_does_not_hide_the_others(tmp_path):
    root = tmp_path / "root"
    make_voice(root, "kasia")
    broken = root / "voices" / "zle"
    broken.mkdir(parents=True)
    (broken / config_mod.CONFIG_FILE).write_text("name: zle\nunknown: 1\n", encoding="utf-8")
    voices = TestClient(create_app(root, gpu=False)).get("/api/state").json()["voices"]
    assert [voice["name"] for voice in voices] == ["kasia", "zle"]
    assert voices[1]["error"] and voices[1]["steps"] == []


def test_new_voice_remembers_its_way_and_is_opened_next_time(client, tmp_path):
    created = client.post("/api/voices", json={"name": "Kuba Bajka", "workflow": "import"}).json()
    assert created["name"] == "kuba_bajka" and created["workflow"] == "import"
    cfg = config_mod.load(tmp_path / "root" / "voices" / "kuba_bajka")
    assert cfg.workflow == "import"
    assert client.get("/api/state").json()["opening_voice"] == "kuba_bajka"
    again = client.post("/api/voices", json={"name": "kuba bajka"})
    assert again.status_code == 400 and again.json()["error"] == "voice_create"
    assert client.post("/api/voices", json={"name": "x", "workflow": "magic"}).status_code == 400
    piper = client.post("/api/voices", json={"name": "ola", "piper_name": " pl_PL-ola_bajka "}).json()
    assert piper["piper_name"] == "pl_PL-ola_bajka" and piper["workflow"] == "clone"


def test_voice_details_and_opening(client, tmp_path):
    make_voice(tmp_path / "root", "kasia")
    voice = client.get("/api/voices/kasia").json()
    assert "name: kasia" in voice["yaml"]
    assert client.get("/api/voices/nobody").status_code == 404
    client.post("/api/voices/kasia/open")
    assert (tmp_path / "root" / "jobs" / "last_voice.txt").read_text(encoding="utf-8") == "kasia"


def test_jobs_report_progress_stop_and_poweroff(tmp_path):
    root = tmp_path / "root"
    pvc = fake_pvc(tmp_path, "import time\nprint('progress synthesize 5/20', flush=True)\ntime.sleep(30)\n")
    app = create_app(root, pvc=pvc, gpu=False)
    client = TestClient(app)
    job = app.state.start("synthesize", "kasia", ["synthesize", "kasia"], poweroff=True)
    assert job["state"] == "running" and job["poweroff"] is True
    for _ in range(100):
        payload = client.get("/api/jobs/current").json()
        if payload.get("progress"):
            break
        import time

        time.sleep(0.05)
    assert payload["progress"]["done"] == 5 and payload["progress"]["total"] == 20
    assert payload["kind"] == "synthesize" and payload["voice"] == "kasia"
    busy = TestClient(app).get("/api/state").json()["jobs"]["current"]
    assert busy["state"] == "running"
    try:
        app.state.start("filter", "kasia", ["filter", "kasia"])
    except Exception as err:
        assert err.code == "job_busy" and err.values == {"kind": "synthesize", "voice": "kasia"}
    else:
        raise AssertionError("a second job must wait")
    assert client.post("/api/jobs/current/poweroff", json={"value": False}).json() == {"poweroff": False}
    assert client.post("/api/jobs/current/stop").json() == {"stopped": True}
    app.state.jobs["current"].wait()
    assert client.get("/api/jobs/current").json()["state"] == "stopped"
    late = client.post("/api/jobs/current/poweroff", json={"value": True})
    assert late.status_code == 409 and late.json()["error"] == "job_poweroff_late"
    assert client.get("/api/jobs/elsewhere").status_code == 404


def test_a_job_whose_runner_died_counts_as_interrupted(tmp_path):
    root = tmp_path / "root"
    (root / "jobs").mkdir(parents=True)
    # a container restart kills the runner: the state file still says nothing about the end
    state = {"kind": "train", "voice": "kasia", "log": "", "started": 1.0, "runner_pid": 999999}
    (root / "jobs" / "current.json").write_text(json.dumps(state), encoding="utf-8")
    assert api.job_payload(JobManager(root))["state"] == "interrupted"


def test_files_come_only_from_the_data_folder(client, tmp_path):
    root = tmp_path / "root"
    voice = make_voice(root, "kasia")
    (voice / "export").mkdir()
    (voice / "export" / "a.onnx.json").write_text("{}", encoding="utf-8")
    assert client.get("/api/files/voices/kasia/export/a.onnx.json").status_code == 200
    assert client.get("/api/files/voices/kasia/voice.yaml").status_code == 404  # not a served kind
    (tmp_path / "secret.json").write_text("{}", encoding="utf-8")
    assert client.get("/api/files/../secret.json").status_code == 404
    assert client.get("/api/files/voices/kasia/nothing.wav").status_code == 404


def test_the_guide_is_served_when_built_else_the_published_one(tmp_path):
    site = tmp_path / "site"
    (site / "pl" / "training").mkdir(parents=True)
    (site / "index.html").write_text("<h1>Start</h1>", encoding="utf-8")
    (site / "pl" / "training" / "index.html").write_text("<h1>Trening</h1>", encoding="utf-8")
    login = Login("admin", "pass")
    built = TestClient(create_app(tmp_path / "root", login=login, gpu=False, docs_dir=site))
    assert built.get("/docs/pl/training/").status_code == 401  # the guide is behind the login
    built.cookies.set(COOKIE, login.token())
    assert "Trening" in built.get("/docs/pl/training/").text
    import piper_voice_cloner.editor.server as server_mod

    original = server_mod.find_docs
    server_mod.find_docs = lambda: None
    try:
        online = TestClient(create_app(tmp_path / "root", gpu=False), follow_redirects=False)
        answer = online.get("/docs/pl/training/")
    finally:
        server_mod.find_docs = original
    assert answer.status_code == 307
    assert answer.headers["location"] == "https://witold-gren.github.io/piper-voice-cloner/pl/training/"
