"""Powering off after a job (the countdown), the login guard, and the test-safety fixtures themselves."""

from __future__ import annotations

import json
import sys

import pytest

from piper_voice_cloner import power
from piper_voice_cloner.editor import auth
from piper_voice_cloner.editor.poweroff import POWER_OFF_DELAY, PowerOffTimer
from piper_voice_cloner.jobs import JobManager


def finished(root, slot="current", code=0, poweroff=True, started=1.0, **extra):
    """A state file of a job that ended (the runner is gone)."""
    state = {"kind": "train", "voice": "kasia", "log": "", "started": started, "poweroff": poweroff,
             "runner_pid": 999999, "returncode": code, "finished": started + 10, **extra}  # fmt: skip
    (root / "jobs").mkdir(parents=True, exist_ok=True)
    (root / "jobs" / f"{slot}.json").write_text(json.dumps(state), encoding="utf-8")


def timer_for(root, calls):
    jobs = {slot: JobManager(root, slot=slot) for slot in ("current", "side")}
    return PowerOffTimer(jobs, lambda: calls.append("off"))


def test_a_job_with_the_wish_counts_down_then_powers_off(tmp_path):
    calls = []
    timer = timer_for(tmp_path, calls)
    finished(tmp_path, code=1)  # also after an error
    timer.check(now=100.0)
    assert timer.at == 100.0 + POWER_OFF_DELAY == 220.0
    assert timer.payload(now=145.0)["seconds_left"] == 75
    timer.check(now=219.0)
    assert calls == []
    timer.check(now=220.0)
    assert calls == ["off"] and timer.at is None and timer.payload()["done"] is True


def test_stop_never_powers_off_whatever_the_code(tmp_path):
    calls = []
    timer = timer_for(tmp_path, calls)
    finished(tmp_path, code=130)
    timer.check(now=0)
    assert timer.at is None
    finished(tmp_path, code=1, started=2.0, stop_requested=True)  # Ctrl+C during Python's start
    timer.check(now=0)
    assert timer.at is None and calls == []


def test_without_the_wish_nothing_happens(tmp_path):
    timer = timer_for(tmp_path, [])
    finished(tmp_path, poweroff=False)
    timer.check(now=0)
    assert timer.at is None and timer.payload()["after_training"] is False


def test_a_restart_drops_the_countdown(tmp_path):
    finished(tmp_path)  # ended before this editor started
    calls = []
    timer = timer_for(tmp_path, calls)
    timer.check(now=0)
    assert timer.at is None


def test_cancel_and_the_error_shown(tmp_path):
    timer = timer_for(tmp_path, [])
    finished(tmp_path)
    timer.check(now=0)
    assert timer.cancel() is True and timer.at is None and timer.cancel() is False

    def broken():
        raise RuntimeError("no Home Assistant connection or machine switch (editor: Settings)")

    timer.power_off = broken
    finished(tmp_path, started=5.0)
    timer.check(now=0)
    timer.check(now=POWER_OFF_DELAY)
    assert "no Home Assistant connection" in timer.payload()["error"]


def test_a_job_running_beside_is_waited_for_and_a_new_job_cancels(tmp_path):
    calls = []
    timer = timer_for(tmp_path, calls)
    side = timer.jobs["side"]
    script = tmp_path / "slow.py"
    script.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
    side.pvc = [sys.executable, str(script)]
    side.start("base-score", "", ["base", "score"])
    finished(tmp_path)  # the training with the wish ended, the rating still runs
    timer.check(now=0)
    assert timer.at is None and timer.payload()["after_training"] is True
    side.stop()
    side.wait()
    timer.check(now=10)
    assert timer.at == 10 + POWER_OFF_DELAY  # after the last job
    side.start("base-score", "", ["base", "score"])  # started by hand during the countdown
    timer.check(now=20)
    assert timer.at is None
    side.stop()
    side.wait()


def test_login_guard_waits_a_minute_after_five_wrong_passwords():
    guard = auth.Guard()
    for second in range(auth.MAX_FAILURES):
        assert not guard.blocked("10.0.0.5", now=float(second))
        guard.failed("10.0.0.5", now=float(second))
    assert guard.blocked("10.0.0.5", now=10.0)
    assert not guard.blocked("10.0.0.6", now=10.0)  # another address
    assert not guard.blocked("10.0.0.5", now=10.0 + auth.LOCKOUT_SECONDS)


def test_session_secret_is_made_once_and_kept_private(tmp_path):
    path = tmp_path / "config" / "session_secret"
    first = auth.load_secret(path)
    assert len(first) == 64 and auth.load_secret(path) == first
    assert path.stat().st_mode & 0o777 == 0o600
    login = auth.Login("admin", "pass", first)
    assert login.token() != auth.Login("admin", "pass", "other").token()


def test_tests_never_power_off_for_real(no_real_poweroff):
    assert power.power_off() == "switch.test" and no_real_poweroff == ["power_off"]
    assert power.power_off is not power.switch_off_machine


def test_tests_never_leave_this_computer():
    from urllib import request

    from tests.conftest import OutsideNetwork

    with pytest.raises(OutsideNetwork):
        request.urlopen("http://homeassistant.local:8123/api/")
    requests = pytest.importorskip("requests")
    with pytest.raises(OutsideNetwork):
        requests.get("https://api.elevenlabs.io/v1/voices", timeout=1)
