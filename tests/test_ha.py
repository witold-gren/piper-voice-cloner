"""Home Assistant connection: kept for its owner only, refusals in plain words, the DNS fix."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

import pytest

from piper_voice_cloner import ha

TOKEN = "t" * 40


@pytest.fixture
def server():
    """A tiny Home Assistant: /api/states, /api/services; 401 for any other token."""
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _answer(self, code, body):
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())

        def _authorized(self):
            if self.headers.get("Authorization") != f"Bearer {TOKEN}":
                self._answer(401, {"message": "Invalid authentication"})
                return False
            return True

        def do_GET(self):
            seen.append(("GET", self.path, self.headers.get("Host")))
            if not self._authorized():
                return
            if self.path == "/api/states/switch.plug":
                self._answer(200, {"entity_id": "switch.plug", "state": "on"})
            elif self.path == "/api/states":
                self._answer(200, [{"entity_id": "sensor.p", "attributes": {"unit_of_measurement": "W"}}])
            else:
                self._answer(404, {"message": "Entity not found."})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.append(("POST", self.path, body))
            if self._authorized():
                self._answer(200, [])

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    httpd.url = f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.seen = seen
    yield httpd
    httpd.shutdown()


def test_connection_kept_outside_the_data_for_its_owner_only(monkeypatch):
    assert not ha.load_connection().ready
    ha.save_connection("http://homeassistant.local:8123/", TOKEN)
    assert ha.load_connection() == ha.Connection("http://homeassistant.local:8123", TOKEN)
    assert ha.CONFIG_FILE.stat().st_mode & 0o077 == 0
    ha.save_connection("http://10.0.0.2:8123", None)  # the address only: the token stays
    ha.save_connection("http://10.0.0.2:8123", "  ")  # an empty field on the page: the token stays too
    assert ha.load_connection() == ha.Connection("http://10.0.0.2:8123", TOKEN) and ha.token_saved()
    with pytest.raises(ValueError, match="token") as err:
        ha.save_connection("http://10.0.0.2:8123", "bad token!")
    assert "bad token" not in str(err.value)  # never echoed
    with pytest.raises(ValueError, match="address"):
        ha.save_connection("homeassistant.local", None)
    monkeypatch.setenv("PVC_HA_TOKEN", "b" * 40)
    monkeypatch.setenv("PVC_HA_URL", "http://ha.lan:8123/")
    assert ha.load_connection() == ha.Connection("http://ha.lan:8123", "b" * 40)
    monkeypatch.delenv("PVC_HA_TOKEN")
    monkeypatch.delenv("PVC_HA_URL")
    ha.save_connection("", "")
    assert not ha.CONFIG_FILE.exists() and not ha.token_saved()
    with pytest.raises(ha.HaError, match="no Home Assistant connection"):
        ha.Client()


def test_removing_the_connection_keeps_the_power_settings():
    from piper_voice_cloner import power

    ha.save_connection("http://homeassistant.local:8123", TOKEN)
    power.save_power(power.PowerSettings("switch.maszyna_gpu", "sensor.plug_power"))
    ha.remove_connection()
    assert not ha.load_connection().ready and power.load_power().switch == "switch.maszyna_gpu"
    assert "token" not in ha.CONFIG_FILE.read_text()


def test_broken_config_file_is_no_connection():
    ha.CONFIG_FILE.parent.mkdir(parents=True)
    ha.CONFIG_FILE.write_text("not json")
    assert not ha.load_connection().ready
    ha.CONFIG_FILE.write_text("[1, 2]")
    assert not ha.load_connection().ready


def test_states_and_services_over_http(server):
    client = ha.Client(ha.Connection(server.url, TOKEN))
    assert client.entity_state("switch.plug")["state"] == "on"
    assert client.entities()[0]["entity_id"] == "sensor.p"
    client.call_service("switch", "turn_off", "switch.plug")
    assert server.seen[-1] == ("POST", "/api/services/switch/turn_off", {"entity_id": "switch.plug"})


def test_refusals_said_in_plain_words(server):
    wrong = ha.Client(ha.Connection(server.url, "b" * 40))
    with pytest.raises(ha.HaError, match="401: the token is wrong") as err:
        wrong.entity_state("switch.plug")
    assert "b" * 40 not in str(err.value)
    assert "403" in ha.explain(403, "") and "administrator" in ha.explain(403, "")
    with pytest.raises(ha.HaError, match="404: Entity not found"):
        ha.Client(ha.Connection(server.url, TOKEN)).entity_state("switch.nope")
    assert "entity ids" in ha.explain(404, "")
    assert ha.explain(500, "boom") == "Home Assistant 500: boom"
    gone = ha.Client(ha.Connection("http://127.0.0.1:9", TOKEN))
    with pytest.raises(ha.HaError, match="cannot be reached"):
        gone.entities()


def test_home_assistant_name_looked_up_once_ipv4_first(monkeypatch):
    """macOS waits 5 s for an IPv6 answer of homeassistant.local on every request: asked once, IPv4."""
    import socket

    asked = []

    def getaddrinfo(host, port, family=0, kind=0):
        asked.append((host, family))
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.4", port))]

    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(ha, "_resolved", {})
    url, headers = ha._direct_url("http://homeassistant.local:8123/api/states/switch.x")
    assert url == "http://192.168.1.4:8123/api/states/switch.x"
    assert headers == {"Host": "homeassistant.local:8123"}
    ha._direct_url("http://homeassistant.local:8123/api/states/sensor.y")
    assert asked == [("homeassistant.local", socket.AF_INET)]  # kept
    assert ha._direct_url("https://ha.example.com/api") == (
        "https://ha.example.com/api",
        {},
    )  # the certificate
    assert ha._direct_url("http://10.0.0.2:8123/api") == ("http://10.0.0.2:8123/api", {})


def test_home_assistant_name_not_found_leaves_the_url(monkeypatch):
    import socket

    def fail(*args):
        raise socket.gaierror("no such host")

    monkeypatch.setattr(socket, "getaddrinfo", fail)
    monkeypatch.setattr(ha, "_resolved", {})
    assert ha._direct_url("http://nope.local:8123/api") == ("http://nope.local:8123/api", {})


def test_direct_url_used_with_the_original_host_header(server, monkeypatch):
    import socket

    monkeypatch.setattr(ha, "_resolved", {})
    port = server.server_address[1]
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *a: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))]
    )
    client = ha.Client(ha.Connection(f"http://homeassistant.local:{port}", TOKEN))
    assert client.entity_state("switch.plug")["state"] == "on"
    assert server.seen[-1] == ("GET", "/api/states/switch.plug", f"homeassistant.local:{port}")


def test_rejected_token_never_sent_again_until_saved_anew(server):
    # every 401 is a failed login for Home Assistant's ip_ban: one, then nothing until a new save
    ha.save_connection(server.url, "b" * 40)
    with pytest.raises(ha.TokenRejected, match="401: the token is wrong"):
        ha.Client().entities()
    assert ha.token_rejected()
    asked = len(server.seen)
    for call in (lambda: ha.Client().entities(), lambda: ha.Client().entity_state("switch.plug"),
                 lambda: ha.Client().call_service("switch", "turn_on", "switch.plug")):  # fmt: skip
        with pytest.raises(ha.TokenRejected, match="not asked again"):
            call()
    assert len(server.seen) == asked  # Home Assistant never asked
    ha.save_connection(server.url, None)  # "Save connection" with the same token: asked once more
    assert not ha.token_rejected()
    with pytest.raises(ha.TokenRejected):
        ha.Client().entities()
    assert len(server.seen) == asked + 1 and ha.token_rejected()
    ha.save_connection(server.url, TOKEN)  # the right token
    assert ha.Client().entities()[0]["entity_id"] == "sensor.p" and not ha.token_rejected()


def test_other_refusals_and_given_connections_do_not_stop_the_questions(server):
    ha.save_connection(server.url, TOKEN)
    with pytest.raises(ha.HaError, match="404") as err:
        ha.Client().entity_state("switch.nope")
    assert not isinstance(err.value, ha.TokenRejected) and not ha.token_rejected()
    with pytest.raises(ha.TokenRejected):  # a connection given by hand (not the saved one)
        ha.Client(ha.Connection(server.url, "b" * 40)).entities()
    assert not ha.token_rejected()


def test_removing_the_connection_forgets_the_rejection(server):
    ha.save_connection(server.url, "b" * 40)
    with pytest.raises(ha.TokenRejected):
        ha.Client().entities()
    ha.remove_connection()
    assert not ha.token_rejected()
