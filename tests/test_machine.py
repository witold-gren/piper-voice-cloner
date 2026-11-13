"""The GPU machine for the page: power through Home Assistant, its job over SSH, never waited for."""

from __future__ import annotations

import json
import sys
import threading
import time

import pytest

from piper_voice_cloner import ha, power, remote
from piper_voice_cloner.webui import machine as machine_mod
from piper_voice_cloner.webui.jobs import JobManager, JobStatus
from piper_voice_cloner.webui.machine import MachineMonitor

from .test_power import FakeHa


def wait(check, seconds=5.0):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if check():
            return True
        time.sleep(0.02)
    return False


def answer(running=False, kind="", voice=""):
    return lambda command: json.dumps({"running": running, "kind": kind, "voice": voice}) + "\n"


@pytest.fixture
def root(tmp_path):
    remote.save_config(tmp_path, remote.ServerConfig(host="gpu.lan", user="u"))
    return tmp_path


def set_up_power():
    ha.save_connection("http://homeassistant.local:8123", "t" * 40)
    power.save_power(power.PowerSettings(switch="switch.maszyna_gpu", sensor="sensor.plug_power"))


def test_machine_power_through_home_assistant(root, monkeypatch):
    monitor = MachineMonitor(root, JobManager(root), run=answer())
    assert monitor.machine() is None and monitor.machine_cached() is None  # not set up: no header button
    ha.save_connection("http://homeassistant.local:8123", "t" * 40)
    fake = FakeHa()
    monkeypatch.setattr(ha, "Client", lambda *args: fake)
    fake.entities = lambda timeout=10: [
        {"entity_id": "switch.maszyna_gpu", "attributes": {"friendly_name": "Maszyna GPU"}},
        {"entity_id": "sensor.plug_power", "attributes": {"unit_of_measurement": "W"}},
        {"entity_id": "sensor.temperature", "attributes": {"unit_of_measurement": "°C"}},
    ]
    found = monitor.ha_entities()
    assert [e["id"] for e in found["sensors"]] == ["sensor.plug_power"]  # only power sensors (W)
    assert found["switches"] == [{"id": "switch.maszyna_gpu", "name": "Maszyna GPU"}] and found["count"] == 3
    assert monitor.entities_cached() == found
    with pytest.raises(ValueError, match="switch and power sensor"):
        monitor.switch_machine(True)
    power.save_power(power.PowerSettings(switch="switch.maszyna_gpu", sensor="sensor.plug_power"))
    assert monitor.machine_cached() == {"machine": "checking", "watts": None}  # before the first answer
    monkeypatch.setattr(monitor, "_reachable", lambda: True)
    assert monitor.machine() == {"switch": "on", "watts": 54.3, "machine": "on"}
    assert monitor.machine_cached()["machine"] == "on"

    monitor.run = answer(running=True, kind="train", voice="kuba")
    with pytest.raises(
        RuntimeError, match=r"a job is running on the machine: train \(kuba\) - stop it first"
    ):
        monitor.switch_machine(False)  # never cut a training
    monitor.switch_machine(True)  # switching on is always fine
    monitor.run = answer(running=False)
    monitor.switch_machine(False)
    assert fake.calls == ["switch.turn_on switch.maszyna_gpu", "switch.turn_off switch.maszyna_gpu"]


def test_home_assistant_failure_is_said_not_raised(root, monkeypatch):
    set_up_power()
    monitor = MachineMonitor(root, JobManager(root), run=answer())

    class Refusing:
        def entity_state(self, entity_id, timeout=5):
            raise ha.HaError("Home Assistant 401: the token is wrong or expired")

        def call_service(self, *args, **kwargs):
            raise ha.HaError("Home Assistant 403: the token belongs to a user who is not an administrator")

    monkeypatch.setattr(ha, "Client", lambda *args: Refusing())
    monkeypatch.setattr(monitor, "_reachable", lambda: False)
    state = monitor.machine()
    assert state["machine"] == "unknown" and "401" in state["error"]
    with pytest.raises(RuntimeError, match="403"):
        monitor.switch_machine(True)


def test_local_jobs_that_use_the_machine_block_switching_off(tmp_path, monkeypatch):
    set_up_power()
    fake = FakeHa()
    monkeypatch.setattr(ha, "Client", lambda *args: fake)
    jobs = JobManager(tmp_path)
    monitor = MachineMonitor(tmp_path, jobs, run=answer())
    monkeypatch.setattr(monitor, "_reachable", lambda: False)  # the machine is off
    running = JobStatus(kind="train", voice="kuba", running=True, returncode=None, started=1.0, log_tail="")
    monkeypatch.setattr(jobs, "status", lambda: running)
    # no server saved: this web UI runs on the GPU machine, so its own training is the machine's
    with pytest.raises(RuntimeError, match="train"):
        monitor.switch_machine(False)
    # with a server saved, a job here (e.g. on a Mac) is not on the machine ...
    remote.save_config(tmp_path, remote.ServerConfig(host="gpu.lan"))
    monitor.switch_machine(False)
    # ... unless it talks to the machine (sending code and data, installing)
    sending = JobStatus(kind="remote-push", voice="", running=True, returncode=None, started=1.0, log_tail="")
    monkeypatch.setattr(jobs, "status", lambda: sending)
    with pytest.raises(RuntimeError, match="remote-push"):
        monitor.switch_machine(False)
    assert fake.calls == ["switch.turn_off switch.maszyna_gpu"]


def test_machine_that_is_off_is_not_asked_over_ssh(root, monkeypatch):
    asked = []
    monitor = MachineMonitor(root, JobManager(root), run=lambda command: asked.append(command) or "")
    monkeypatch.setattr(monitor, "_reachable", lambda: False)
    state = monitor.poll()
    assert asked == [] and state == {
        "running": False,
        "kind": "",
        "voice": "",
        "reachable": False,
        "error": None,
        "checking": False,
        "answered_at": None,  # never answered
    }


def test_job_on_the_machine_read_over_ssh(root, monkeypatch):
    commands = []

    def run(command):
        commands.append(command)
        return "welcome banner\n" + answer(True, "filter", "kuba")(command)

    monitor = MachineMonitor(root, JobManager(root), run=run)
    monkeypatch.setattr(monitor, "_reachable", lambda: True)
    assert monitor.status()["checking"]
    state = monitor.poll()
    assert (
        state["running"] and state["kind"] == "filter" and state["voice"] == "kuba" and not state["checking"]
    )
    assert commands[0][0] == "ssh" and "u@gpu.lan" in commands[0]
    assert monitor.poll() == state and len(commands) == 1  # asked at most every POLL_SECONDS
    monitor.run = lambda command: (_ for _ in ()).throw(RuntimeError("Permission denied (publickey)."))
    assert monitor.poll(force=True)["error"] == "Permission denied (publickey)."


def test_without_a_server_nothing_is_checked(tmp_path):
    monitor = MachineMonitor(tmp_path, JobManager(tmp_path), run=answer())
    assert not monitor.status()["checking"]  # nothing to wait for
    assert monitor.poll()["running"] is False and monitor.machine_is_here()


def test_reachable_is_a_quick_tcp_connect(tmp_path):
    import socket

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    port = listener.getsockname()[1]
    remote.save_config(tmp_path, remote.ServerConfig(host="127.0.0.1", port=port))
    monitor = MachineMonitor(tmp_path, JobManager(tmp_path))
    assert monitor._reachable()
    listener.close()
    assert not monitor._reachable()


def test_page_answered_at_once_while_a_machine_that_is_off_is_checked(root, monkeypatch):
    """A switched-off machine takes the SSH timeout to answer: the page must not wait for it."""
    import subprocess

    release = threading.Event()

    def slow_ssh(command):
        release.wait(5)  # like ssh -o ConnectTimeout=10 to a machine that is off
        raise subprocess.TimeoutExpired("ssh", 10)

    set_up_power()
    monitor = MachineMonitor(root, JobManager(root), run=slow_ssh)
    monkeypatch.setattr(monitor, "_reachable", lambda: True)
    monkeypatch.setattr(monitor, "machine", lambda: release.wait(5))
    started = time.time()
    monitor.refresh_in_background()
    monitor.refresh_in_background()  # one check at a time
    assert monitor.status()["checking"] and monitor.machine_cached() == {"machine": "checking", "watts": None}
    assert time.time() - started < 1
    assert monitor.lock.acquire(timeout=0.5)  # the lock is free while the machine is asked
    monitor.lock.release()
    release.set()
    assert wait(lambda: not monitor.status()["checking"])
    assert "timed out" in monitor.status()["error"]

    # an unexpected failure of the check is said too - never "checking" for ever
    monitor._checked, monitor._polled = False, 0.0
    monitor.run = lambda command: 1 / 0
    assert wait(lambda: not monitor._refreshing)
    monitor.refresh_in_background()
    assert wait(lambda: not monitor.status()["checking"])
    assert "ZeroDivisionError" in monitor.status()["error"]


def test_unexpected_failure_of_the_power_reading_is_said(root, monkeypatch):
    set_up_power()
    monitor = MachineMonitor(root, JobManager(root), run=answer())
    monkeypatch.setattr(monitor, "_reachable", lambda: False)

    def broken(*args):
        raise KeyError("state")

    monkeypatch.setattr(power, "machine_state", broken)
    monitor.refresh_in_background()
    assert wait(lambda: monitor.machine_cached()["machine"] != "checking")
    assert (
        monitor.machine_cached()["machine"] == "unknown" and "KeyError" in monitor.machine_cached()["error"]
    )


def test_ssh_runner_reports_the_last_error_line(monkeypatch):
    ok = machine_mod.run_ssh([sys.executable, "-c", "print('hi')"])
    assert ok.strip() == "hi"
    with pytest.raises(RuntimeError, match="no route"):
        machine_mod.run_ssh(
            [sys.executable, "-c", "import sys; sys.stderr.write('x\\nno route\\n'); sys.exit(255)"]
        )
    with pytest.raises(RuntimeError, match="exit code 3"):
        machine_mod.run_ssh([sys.executable, "-c", "raise SystemExit(3)"])


def test_rejected_token_stops_every_question_until_saved_again(root, monkeypatch):
    """Each 401 is a failed login for Home Assistant's ip_ban: the header says so and asks nothing."""
    set_up_power()
    monitor = MachineMonitor(root, JobManager(root), run=answer())
    monkeypatch.setattr(monitor, "_reachable", lambda: True)
    asked = []
    monkeypatch.setattr(power, "machine_state", lambda *args: asked.append(args) or {"machine": "on"})
    ha._mark_rejected()
    for _ in range(3):
        assert (
            monitor.machine()["machine"] == "rejected" and monitor.machine_cached()["machine"] == "rejected"
        )
    assert asked == []
    with pytest.raises(ha.TokenRejected):
        monitor.ha_entities()
    with pytest.raises(RuntimeError, match="not asked again"):
        monitor.switch_machine(True)
    ha.save_connection("http://homeassistant.local:8123", None)  # "Save connection": asked again
    monitor.forget()
    assert monitor.machine() == {"machine": "on"} and len(asked) == 1
