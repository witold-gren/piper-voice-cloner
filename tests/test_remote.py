from __future__ import annotations

import json
import shlex
import sys

import pytest

from piper_voice_cloner import remote
from piper_voice_cloner.remote import Remote, ServerConfig


def test_config_validation():
    ServerConfig("ubuntu.local", "user").validate()
    for bad in (
        ServerConfig(""),
        ServerConfig("host;rm"),
        ServerConfig("h", "us er"),
        ServerConfig("h", port=0),
        ServerConfig("h", ui_port=70000),
        ServerConfig("h", remote_dir="/abs"),
        ServerConfig("h", remote_dir="a/../b"),
        ServerConfig("h", key="/no/such/key"),
    ):
        with pytest.raises(ValueError):
            bad.validate()


def test_save_and_load_roundtrip(tmp_path):
    assert remote.load_config(tmp_path) is None
    path = remote.save_config(tmp_path, ServerConfig("ubuntu.local", "user", "2222", ui_port="7861"))
    assert json.loads(path.read_text())["port"] == 2222
    loaded = remote.load_config(tmp_path)
    assert loaded == ServerConfig("ubuntu.local", "user", 2222, ui_port=7861)
    assert loaded.target == "user@ubuntu.local" and loaded.ui_url == "http://ubuntu.local:7861/"
    assert ServerConfig("h").target == "h"


def test_ssh_keys_need_a_public_half(tmp_path):
    (tmp_path / "id_a").write_text("x")
    (tmp_path / "id_a.pub").write_text("x")
    (tmp_path / "id_b").write_text("x")
    assert remote.ssh_keys(tmp_path) == [str(tmp_path / "id_a")]
    assert remote.ssh_keys(tmp_path / "missing") == []


def test_ssh_options_with_key(tmp_path):
    key = tmp_path / "id"
    key.write_text("x")
    options = Remote(ServerConfig("h", key=str(key), port=2222)).ssh_options()
    assert options[:2] == ["-p", "2222"] and "BatchMode=yes" in options
    assert options[-4:] == ["-i", str(key), "-o", "IdentitiesOnly=yes"]
    assert "-i" not in Remote(ServerConfig("h")).ssh_options()


def test_push_mirrors_code_but_never_deletes_data(tmp_path):
    server = Remote(ServerConfig("ubuntu.local", "user", remote_dir="pvc"))
    mkdir, code, stamp, data = server.push(tmp_path)
    # the code version goes over right after the code (the checklist compares it)
    assert stamp[-1] == f"printf %s {remote.code_stamp()} > pvc/repo/.pvc-stamp"
    assert mkdir[-1] == "mkdir -p pvc/repo pvc/data"
    assert "--delete" in code and code[-1] == "user@ubuntu.local:pvc/repo/"
    assert code[-2] == f"{remote.repo_dir()}/"
    for pattern in (".venv*/", "third_party/", "voices/", ".git/"):
        assert f"--exclude={pattern}" in code
    assert "--delete" not in data and data[-2:] == [f"{tmp_path}/", "user@ubuntu.local:pvc/data/"]
    for pattern in ("voices/*/train/", "voices/*/export/", "bases/", "jobs/", "server.json"):
        assert f"--exclude={pattern}" in data
    # the ssh used by rsync carries the same options
    assert shlex.split(data[data.index("-e") + 1])[:3] == ["ssh", "-p", "22"]


def test_install_and_pull_commands(tmp_path):
    server = Remote(ServerConfig("h", "u", remote_dir="pvc", ui_port=7861))
    (install,) = server.install()
    script = install[-1]
    assert 'PVC_HOME="$HOME/pvc/data"' in script and "cd pvc/repo" in script
    assert "./scripts/setup.sh && PVC_UI_PORT=7861 ./scripts/install-service.sh" in script
    (pull,) = server.pull(tmp_path)
    assert pull[-2:] == ["u@h:pvc/data/", f"{tmp_path}/"]
    assert pull.index("--include=voices/*/export/**") < pull.index("--exclude=*")


def test_check_script_lists_missing_tools_with_the_apt_hint():
    script = remote.CHECK_SCRIPT
    for tool in ("ffmpeg", "espeak-ng", "cmake", "uv", "nvidia-smi"):
        assert tool in script
    assert "sudo apt install$missing" in script


def test_job_state_read_on_the_machine_with_the_system_python(tmp_path):
    import os
    import subprocess
    import sys

    server = remote.Remote(remote.ServerConfig(host="gpu.lan", user="u", remote_dir="pvc"))
    command = server.job_state()
    assert command[0] == "ssh" and command[-2] == "u@gpu.lan" and "pvc/data/jobs/current.json" in command[-1]

    def check(state: dict | None) -> dict:
        path = tmp_path / "current.json"
        path.unlink(missing_ok=True)
        if state is not None:
            path.write_text(json.dumps(state))
        result = subprocess.run(
            [sys.executable, "-c", remote.JOB_STATE_CODE, str(path)],
            capture_output=True,
            text=True,
            check=True,
        )
        return remote.parse_job_state(result.stdout)

    assert check(None) == {"running": False, "kind": "", "voice": ""}
    running = {"kind": "train", "voice": "kuba", "runner_pid": os.getpid()}
    assert check(running) == {"running": True, "kind": "train", "voice": "kuba"}
    assert check({**running, "returncode": 0})["running"] is False  # finished
    assert check({**running, "runner_pid": 2**22 + 12345})["running"] is False  # the runner died


def test_job_state_answer_must_be_json():
    assert remote.parse_job_state('motd\n{"running": true, "kind": "x"}\n')["running"] is True
    with pytest.raises(RuntimeError, match="unexpected answer"):
        remote.parse_job_state("bash: python3: command not found")


GOOD = {
    "host": "gpu-box", "gpu": "NVIDIA GeForce RTX 4090, 24564, 580.95", "sudo": False,
    "tools": dict.fromkeys(remote.SETUP_TOOLS, True), "uv": True, "free_gb": 1800.0, "stamp": "abc",
    "venv": True, "train": "cuda", "voices": {"kasia": 18395, "piotr": 400}, "service": "active", "ui": True,
    "tensorboard": 6006,
}  # fmt: skip


def _states(items):
    return {item.key: item.state for item in items}


def test_status_command_and_answer():
    server = Remote(ServerConfig("h", "u", remote_dir="pvc", ui_port=7861))
    command = server.status()[-1]
    assert command.startswith("python3 -c ") and "pvc 7861" in command and '"ffmpeg"' in command
    out = remote.parse_status("noise\nPVC-STATUS " + json.dumps(GOOD) + "\n")
    assert out["gpu"].startswith("NVIDIA")
    with pytest.raises(RuntimeError, match="unexpected answer"):
        remote.parse_status("Permission denied")


def test_status_code_runs_against_an_empty_home(tmp_path):
    """The script really runs (system python3, nothing installed): everything is reported missing."""
    import os
    import subprocess

    env = {**os.environ, "HOME": str(tmp_path)}
    done = subprocess.run(
        [sys.executable, "-c", remote.STATUS_CODE, "pvc", "1", json.dumps(["ffmpeg"])],
        capture_output=True, text=True, env=env, timeout=60, check=True,
    )  # fmt: skip
    out = remote.parse_status(done.stdout)
    assert out["venv"] is False and out["train"] == "missing" and out["voices"] == {} and out["stamp"] == ""
    assert out["ui"] is False and out["login"] == "" and set(out["tools"]) == {"ffmpeg"}
    assert out["tensorboard"] == 0


def test_ready_machine_is_all_green():
    config = ServerConfig("ubuntu.local", "tomek")
    items = remote.evaluate(GOOD, config, {"kasia": 18395, "piotr": 400}, "abc")
    assert set(_states(items).values()) == {"ok"} and remote.summary(items) == "ready"
    gpu = next(i for i in items if i.key == "gpu")
    assert gpu.detail == "NVIDIA GeForce RTX 4090 · 24 GB · driver 580.95"


def test_checklist_says_what_prepare_does_and_what_you_do():
    config = ServerConfig("ubuntu.local", "tomek", port=2222)
    status = {**GOOD, "tools": {**GOOD["tools"], "ffmpeg": False, "gcc": False}, "uv": False,
              "stamp": "old", "voices": {"kasia": 18000}, "train": "broken",
              "train_error": "No module named x", "service": "inactive", "ui": False,
              "free_gb": 12}  # fmt: skip
    items = remote.evaluate(status, config, {"kasia": 18395, "piotr": 400}, "new")
    states = _states(items)
    assert states == {"gpu": "ok", "tools": "manual", "uv": "todo", "disk": "warn", "code": "todo",
                      "data": "todo", "venv": "ok", "train": "todo", "service": "todo",
                      "tensorboard": "ok"}  # fmt: skip
    tools = next(i for i in items if i.key == "tools")
    assert tools.command == "ssh -t -p 2222 tomek@ubuntu.local sudo apt install -y build-essential ffmpeg"
    assert next(i for i in items if i.key == "data").detail == "kasia, piotr"
    assert next(i for i in items if i.key == "train").detail == "No module named x"
    assert remote.summary(items) == "manual"
    # with sudo without a password Prepare installs the packages itself
    items = remote.evaluate({**status, "sudo": True}, config, {}, "new")
    assert _states(items)["tools"] == "todo" and remote.summary(items) == "todo"
    assert remote.apt_packages(status) == ["build-essential", "ffmpeg"]
    assert Remote(config).apt_install(["ffmpeg"])[-1] == (
        "sudo -n env DEBIAN_FRONTEND=noninteractive apt-get install -y ffmpeg"
    )
    # no NVIDIA driver: only you can do it (reboot)
    assert _states(remote.evaluate({**GOOD, "gpu": ""}, config, {}, "abc"))["gpu"] == "manual"


def test_code_stamp_and_local_voices(tmp_path):
    repo = tmp_path / "repo"
    (repo / "pkg").mkdir(parents=True)
    (repo / "pkg" / "a.py").write_text("x = 1\n")
    (repo / ".venv" / "lib").mkdir(parents=True)
    first = remote.code_stamp(repo)
    (repo / ".venv" / "lib" / "big.py").write_text("ignored")
    (repo / remote.STAMP_FILE).write_text("old")
    assert remote.code_stamp(repo) == first and len(first) == 12
    (repo / "pkg" / "a.py").write_text("x = 2\n")
    assert remote.code_stamp(repo) != first
    meta = tmp_path / "root" / "voices" / "kasia" / "dataset" / "metadata.csv"
    meta.parent.mkdir(parents=True)
    meta.write_text("a|Tekst.\nb|Drugi.\n\n")
    assert remote.local_voices(tmp_path / "root") == {"kasia": 2}
    saved = remote.save_status(tmp_path / "root", GOOD)
    assert remote.load_status(tmp_path / "root")["status"] == GOOD and saved["error"] == ""
    assert remote.status_path(tmp_path / "root").parent.name == "jobs"  # never pushed (DATA_EXCLUDES)


def test_restart_ui_touches_only_the_web_ui_service():
    command = Remote(ServerConfig("h", "u")).restart_ui()[-1]
    assert command == "systemctl --user restart piper-voice-cloner"
