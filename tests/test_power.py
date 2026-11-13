"""The GPU machine switched on and off through its switch in Home Assistant."""

from __future__ import annotations

import pytest

from piper_voice_cloner import ha, power


class FakeHa:
    """States and service calls of Home Assistant, as Client answers them."""

    def __init__(self, switch="on", watts="54.3"):
        self.states = {"switch.maszyna_gpu": switch, "sensor.plug_power": watts}
        self.calls = []

    def entity_state(self, entity_id, timeout=5):
        return {"state": self.states[entity_id], "attributes": {}}

    def call_service(self, domain, service, entity_id, timeout=10):
        self.calls.append(f"{domain}.{service} {entity_id}")


SETTINGS = power.PowerSettings(switch="switch.maszyna_gpu", sensor="sensor.plug_power", off_watts=5)


def test_settings_kept_next_to_the_connection():
    assert not power.load_power().ready and power.load_power().off_watts == 5.0
    ha.save_connection("http://homeassistant.local:8123", "t" * 40)
    power.save_power(
        power.PowerSettings(switch=" switch.maszyna_gpu", sensor="sensor.plug_power", off_watts="7")
    )
    assert power.load_power() == power.PowerSettings("switch.maszyna_gpu", "sensor.plug_power", 7.0)
    ha.save_connection("http://10.0.0.2:8123", None)  # the connection changed: the power settings stay
    assert power.load_power().switch == "switch.maszyna_gpu" and ha.load_connection().token == "t" * 40
    assert ha.CONFIG_FILE.stat().st_mode & 0o077 == 0
    bad_settings = (
        (power.PowerSettings(switch="sensor.plug", sensor="sensor.x"), "switch"),
        (power.PowerSettings(switch="switch.plug", sensor="switch.x"), "sensor"),
        (power.PowerSettings(switch="switch.Bad Name", sensor="sensor.x"), "switch"),
        (power.PowerSettings(switch="switch.plug", sensor="sensor.x", off_watts=0), "threshold"),
        (power.PowerSettings(switch="switch.plug", sensor="sensor.x", off_watts="abc"), "threshold"),
    )
    for bad, match in bad_settings:
        with pytest.raises(ValueError, match=match):
            power.save_power(bad)
    power.save_power(power.PowerSettings(switch="input_boolean.machine", sensor="sensor.x"))  # also fine


def test_state_for_the_header():
    def state(fake, reachable=False):
        return power.machine_state(fake, SETTINGS, reachable)

    assert state(FakeHa(), reachable=True) == {"switch": "on", "watts": 54.3, "machine": "on"}
    assert state(FakeHa())["machine"] == "starting"  # on, the SSH port not answering yet
    assert state(FakeHa(switch="off", watts="48"))["machine"] == "stopping"  # Home Assistant shutting it down
    assert state(FakeHa(switch="off", watts="0.4"))["machine"] == "off"
    assert state(FakeHa(switch="off", watts="unavailable")) == {
        "switch": "off",
        "watts": None,
        "machine": "off",
    }
    assert state(FakeHa(switch="unavailable", watts="unavailable")) == {
        "switch": "unavailable",
        "watts": None,
        "machine": "unknown",
    }


def test_switch_flipped_in_home_assistant():
    fake = FakeHa()
    power.switch_machine(fake, SETTINGS, on=False)
    power.switch_machine(fake, SETTINGS, on=True)
    assert fake.calls == ["switch.turn_off switch.maszyna_gpu", "switch.turn_on switch.maszyna_gpu"]
