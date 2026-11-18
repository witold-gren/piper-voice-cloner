"""dev/screenshots_machine.py takes pictures of the real editor for a public guide: what is private in
the house must be replaced on the page before each picture."""

from __future__ import annotations

from pathlib import Path
import re
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "dev"))

import screenshots_machine  # noqa: E402


def masked(text: str) -> str:
    for pattern, replacement in screenshots_machine.MASKS:
        text = re.sub(pattern, replacement, text)
    return text


def test_the_home_assistant_address_and_room_names_never_reach_a_picture():
    page = (
        "http://192.168.50.4:8123 http://10.1.2.3:8123 sensor.pokoj_kuby_komputer_moc "
        "sensor.pokoj_oli_biurko_led_moc Pokój Kuby Komputer Moc"
    )
    out = masked(page)
    assert "192.168" not in out and "10.1.2.3" not in out
    assert "kuby" not in out.lower() and "oli" not in out.lower()
    assert "http://homeassistant.local:8123" in out and "sensor.gpu_plug_power" in out


def test_it_only_opens_views_and_never_starts_a_job():
    source = (REPO / "dev" / "screenshots_machine.py").read_text(encoding="utf-8")
    for start in ("[data-run]", "data-start", "/api/voices", "post(", "[data-create"):
        assert start not in source, start
    assert "print(password" not in source and "print(user" not in source
    assert not re.search(r"\d+\.\d+\.\d+\.\d+", source.split("MASKS = [")[0])  # no address of the house
    assert "@1" not in source


def test_the_machine_comes_from_the_shared_host_file(tmp_path, monkeypatch):
    (tmp_path / ".config" / "gpu-studio").mkdir(parents=True)
    (tmp_path / ".config" / "gpu-studio" / "host.mk").write_text("# comment\nGPU_HOST = user@gpu\n")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert screenshots_machine.gpu_host() == "user@gpu"
