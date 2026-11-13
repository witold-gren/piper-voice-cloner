"""Home Assistant through its REST API: states and services (the GPU machine's power, see power.py).

Connection: ``~/.config/piper-voice-cloner/home_assistant.json`` (mode 600: ``{"url", "token",
"power"}`` - a long-lived token of a Home Assistant administrator) or ``PVC_HA_URL`` /
``PVC_HA_TOKEN``. Outside the data folder on purpose: that folder is copied to the GPU machine and
into backups. The token is never printed nor sent back to the web page. ``PVC_HA_CONFIG`` points
at another file (tests, a second setup).

The same design as the wake word training panel (home-assistant-wakeword, ``wakeword/ha_sync.py``).
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import time
from urllib import error, parse, request

CONFIG_FILE = Path(
    os.environ.get("PVC_HA_CONFIG") or Path.home() / ".config" / "piper-voice-cloner" / "home_assistant.json"
)
TIMEOUT = 10
DNS_CACHE_SECONDS = 300
URL_PATTERN = re.compile(r"^https?://[^\s/]+(:\d+)?/?$")
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9._-]{20,}$")


class HaError(RuntimeError):
    """Home Assistant refused or could not be reached - said in plain words."""


class TokenRejected(HaError):
    """Home Assistant answered 401: the token is wrong or expired.

    Every 401 counts as a failed login for Home Assistant's ip_ban, so after the first one nothing asks
    again (``token_rejected`` in the connection file) until the connection is saved anew.
    """


REJECTED_KEY = "token_rejected"
REJECTED_MESSAGE = (
    "Home Assistant rejected the token - not asked again until the connection is saved anew (Tools)"
)


@dataclass
class Connection:
    url: str
    token: str

    @property
    def ready(self) -> bool:
        return bool(self.url and self.token)


def load_connection() -> Connection:
    saved = _read_config()
    url = os.environ.get("PVC_HA_URL") or saved.get("url", "")
    token = os.environ.get("PVC_HA_TOKEN") or saved.get("token", "")
    return Connection(url.rstrip("/"), token)


def save_connection(url: str, token: str | None) -> None:
    """``token`` None (or blank) keeps the saved one (the page never shows it back); both empty removes it."""
    url = (url or "").strip().rstrip("/")
    if url and not URL_PATTERN.match(url + "/"):
        raise ValueError("Home Assistant address: e.g. http://homeassistant.local:8123")
    token = (token or "").strip() or None
    if token is not None and not TOKEN_PATTERN.match(token):
        raise ValueError("this does not look like a Home Assistant long-lived token")  # never echoed
    kept = _read_config().get("token", "") if token is None else token
    if not url:
        remove_connection()
        return
    saved = {k: v for k, v in _read_config().items() if k != REJECTED_KEY}  # asked again
    _write_config({**saved, "url": url, "token": kept})  # other keys (e.g. "power") stay


def remove_connection() -> None:
    """Forget the address and the token; the power settings stay (they mean nothing without them)."""
    rest = {k: v for k, v in _read_config().items() if k not in ("url", "token", REJECTED_KEY)}
    if rest:
        _write_config(rest)
    else:
        CONFIG_FILE.unlink(missing_ok=True)


def token_saved() -> bool:
    return bool(load_connection().token)


def token_rejected() -> bool:
    """Home Assistant refused the saved token; nothing is asked until the connection is saved again."""
    return bool(_read_config().get(REJECTED_KEY))


def _mark_rejected() -> None:
    _write_config({**_read_config(), REJECTED_KEY: True})  # also for a token from PVC_HA_TOKEN


def _read_config() -> dict:
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_config(data: dict) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.touch(mode=0o600, exist_ok=True)
    CONFIG_FILE.chmod(0o600)
    CONFIG_FILE.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")


_resolved: dict[tuple[str, int], tuple[float, str]] = {}  # (host, port) -> (time, IPv4 address)


def _direct_url(url: str) -> tuple[str, dict]:
    """``http://homeassistant.local:8123/...`` -> the same URL with the IPv4 address, plus its Host header.

    macOS asks mDNS for IPv4 and IPv6 at once and waits 5 s for an IPv6 answer that never comes - on
    every request. The address is asked for once (IPv4 first) and kept a few minutes. HTTPS keeps the
    name (the certificate is for it); an address or a failed lookup leaves the URL as it is.
    """
    import ipaddress
    import socket

    parts = parse.urlsplit(url)
    host, port = parts.hostname or "", parts.port or 80
    if parts.scheme != "http" or not host:
        return url, {}
    try:
        ipaddress.ip_address(host)
        return url, {}
    except ValueError:
        pass
    cached = _resolved.get((host, port))
    if cached and time.time() - cached[0] < DNS_CACHE_SECONDS:
        address = cached[1]
    else:
        try:
            address = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)[0][4][0]
        except OSError:
            return url, {}
        _resolved[(host, port)] = (time.time(), address)
    netloc = f"{address}:{parts.port}" if parts.port else address
    return parse.urlunsplit(parts._replace(netloc=netloc)), {"Host": parts.netloc}


class Client:
    def __init__(self, connection: Connection | None = None):
        self.saved = connection is None  # the saved connection: its rejected token is remembered
        self.connection = connection or load_connection()
        if not self.connection.ready:
            raise HaError("no Home Assistant connection - set the address and token in the web UI (Tools)")
        if self.saved and token_rejected():
            raise TokenRejected(REJECTED_MESSAGE)

    def _open(self, path: str, data: bytes | None = None, method: str = "GET", api: str = "/api",
              timeout: float = TIMEOUT):  # fmt: skip
        url, host = _direct_url(f"{self.connection.url}{api}{path}")
        headers = {
            "Authorization": f"Bearer {self.connection.token}",
            "Content-Type": "application/json",
            **host,
        }
        try:
            return request.urlopen(
                request.Request(url, data=data, method=method, headers=headers), timeout=timeout
            )
        except error.HTTPError as err:
            if err.code == 401:  # a failed login for ip_ban - never asked again with this token
                if self.saved:
                    _mark_rejected()
                raise TokenRejected(explain(401, "")) from None
            raise HaError(explain(err.code, err.read().decode("utf-8", "replace"))) from None
        except (error.URLError, OSError) as err:
            reason = getattr(err, "reason", err)
            raise HaError(f"Home Assistant at {self.connection.url} cannot be reached: {reason}") from None

    def entity_state(self, entity_id: str, timeout: float = 5) -> dict:
        """{"state", "attributes", ...} of an entity."""
        with self._open(f"/states/{parse.quote(entity_id)}", timeout=timeout) as response:
            return json.load(response)

    def entities(self, timeout: float = 10) -> list[dict]:
        with self._open("/states", timeout=timeout) as response:
            return json.load(response)

    def call_service(self, domain: str, service: str, entity_id: str, timeout: float = 10) -> None:
        body = json.dumps({"entity_id": entity_id}).encode()
        with self._open(f"/services/{domain}/{service}", data=body, method="POST", timeout=timeout):
            pass


def explain(status: int, body: str) -> str:
    try:
        message = json.loads(body).get("message", "")
    except (ValueError, AttributeError):
        message = body.strip()[:200]
    if status == 401:
        return (
            "Home Assistant 401: the token is wrong or expired - "
            "make a new long-lived token (profile → Security)"
        )
    if status == 403:
        return "Home Assistant 403: the token belongs to a user who is not an administrator"
    if status == 404:
        return "Home Assistant 404: " + (message or "no such entity - check the entity ids (Tools)")
    return f"Home Assistant {status}: {message or 'refused'}"
