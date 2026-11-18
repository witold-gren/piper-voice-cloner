"""STUDIO_TRUSTED_NETWORKS: no login from the home network, only by the address of the connection."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from piper_voice_cloner.cli import app as cli_app
from piper_voice_cloner.editor.auth import Login, parse_networks, trusted
from piper_voice_cloner.editor.server import create_app

HOME = parse_networks("192.168.1.0/24, fd00::/8")


def test_networks_are_read_from_a_comma_separated_list():
    assert parse_networks(None) == () and parse_networks("") == ()
    assert [str(n) for n in parse_networks("192.168.1.0/24;10.8.0.1/24  ")] == [
        "192.168.1.0/24",
        "10.8.0.0/24",
    ]
    with pytest.raises(ValueError, match="STUDIO_TRUSTED_NETWORKS"):
        parse_networks("home")


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("192.168.1.20", True),
        ("::ffff:192.168.1.20", True),  # IPv4 on a dual-stack socket
        ("fd00::5", True),
        ("192.168.2.20", False),
        ("172.17.0.1", False),  # the Docker gateway (localhost on the machine) keeps the login
        ("testclient", False),
        ("", False),
        (None, False),
    ],
)
def test_an_address_is_trusted_only_inside_the_networks(address, expected):
    assert trusted(address, HOME) is expected
    assert trusted(address, ()) is False  # empty: login from everywhere


def editor(tmp_path, address: str, networks=HOME) -> TestClient:
    app = create_app(
        tmp_path, login=Login("admin", "pass"), gpu=False, countdown=False, trusted_networks=networks
    )
    return TestClient(app, follow_redirects=False, client=(address, 50000))


def test_a_trusted_network_is_logged_in_without_a_password(tmp_path):
    client = editor(tmp_path, "192.168.1.20")
    assert client.get("/").status_code == 200
    state = client.get("/api/state").json()
    assert state["trusted"] is True and state["login"] is True and state["user"] == "admin"
    assert client.get("/login").headers["location"] == "/"


def test_another_network_still_needs_the_login(tmp_path):
    client = editor(tmp_path, "192.168.2.20")
    assert client.get("/").headers["location"] == "/login"
    assert client.get("/api/state").status_code == 401
    assert client.get("/login").status_code == 200


def test_a_faked_header_is_not_trusted(tmp_path):
    client = editor(tmp_path, "203.0.113.9")
    faked = {"X-Forwarded-For": "192.168.1.20", "X-Real-IP": "192.168.1.20", "Forwarded": "for=192.168.1.20"}
    assert client.get("/api/state", headers=faked).status_code == 401


def test_without_networks_the_login_is_always_needed(tmp_path):
    client = editor(tmp_path, "192.168.1.20", networks=())
    assert client.get("/api/state").status_code == 401


def test_a_logged_in_browser_elsewhere_is_not_trusted(tmp_path):
    client = editor(tmp_path, "192.168.2.20")
    client.post("/login", data={"user": "admin", "password": "pass"})
    state = client.get("/api/state").json()
    assert state["trusted"] is False and state["user"] == "admin"


def test_the_editor_command_refuses_a_wrong_network(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    monkeypatch.setenv("STUDIO_TRUSTED_NETWORKS", "home")
    result = CliRunner().invoke(cli_app, ["--root", str(tmp_path), "editor"])
    assert result.exit_code != 0 and "not a network" in result.output
