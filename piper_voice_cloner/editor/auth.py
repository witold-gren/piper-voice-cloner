"""One user for the whole editor (PVC_UI_AUTH=user:password), kept in an HttpOnly cookie.

The cookie is an HMAC of the user with a secret kept next to the settings (docker/config) and the
password: changing the password logs everybody out, a restart does not. Five wrong passwords from one
address make it wait a minute.

STUDIO_TRUSTED_NETWORKS (e.g. ``192.168.1.0/24``, comma-separated, empty by default; the same name in every
studio of the GPU machine) lets a home skip the login on its own network: a connection from such a network
is logged in as the user. Only the address of the connection counts, never a header a client could fake.
A machine in the cloud leaves it empty and keeps the login.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import hashlib
import hmac
import ipaddress
import os
from pathlib import Path
import secrets
import threading
import time

COOKIE = "pvc_session"
SESSION_DAYS = 30
MAX_FAILURES = 5  # wrong passwords from one address before it waits
LOCKOUT_SECONDS = 60
TRUSTED_ENV = "STUDIO_TRUSTED_NETWORKS"

Network = ipaddress.IPv4Network | ipaddress.IPv6Network


def parse_networks(value: str | None) -> tuple[Network, ...]:
    """`192.168.1.0/24, 10.8.0.0/24` -> networks; empty -> none (the login is needed from everywhere)."""
    networks = []
    for part in (value or "").replace(";", ",").replace(" ", ",").split(","):
        if not part:
            continue
        try:
            networks.append(ipaddress.ip_network(part, strict=False))
        except ValueError:
            raise ValueError(f"{TRUSTED_ENV}: {part!r} is not a network like 192.168.1.0/24") from None
    return tuple(networks)


def trusted(address: str | None, networks: tuple[Network, ...]) -> bool:
    """The connection's own address is in a network that needs no login."""
    if not networks or not address:
        return False
    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:  # ::ffff:192.168.1.5 on a dual-stack socket
        ip = ip.ipv4_mapped
    return any(ip.version == net.version and ip in net for net in networks)


def secret_path() -> Path:
    return Path(
        os.environ.get("PVC_SESSION_SECRET_FILE")
        or Path.home() / ".config" / "piper-voice-cloner" / "session_secret"
    )


def load_secret(path: Path | None = None) -> str:
    """The session secret, made once (mode 600)."""
    path = path or secret_path()
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    value = secrets.token_hex(32)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(value)
    return value


@dataclass(frozen=True)
class Login:
    user: str
    password: str
    secret: str = ""

    @classmethod
    def parse(cls, value: str | None, secret: str = "") -> Login | None:
        """`user:password`; empty means no login (only for a computer nobody else reaches)."""
        if not value:
            return None
        user, sep, password = value.partition(":")
        if not sep or not user or not password:
            raise ValueError("PVC_UI_AUTH must look like user:password")
        return cls(user, password, secret)

    def check(self, user: str, password: str) -> bool:
        return hmac.compare_digest(user.encode(), self.user.encode()) and hmac.compare_digest(
            password.encode(), self.password.encode()
        )

    def token(self) -> str:
        key = f"{self.secret}:{self.password}".encode()
        return hmac.new(key, f"pvc-session:{self.user}".encode(), hashlib.sha256).hexdigest()

    def valid(self, cookie: str | None) -> bool:
        return bool(cookie) and hmac.compare_digest(cookie.encode(), self.token().encode())


@dataclass
class Guard:
    """Wrong passwords per address; after MAX_FAILURES the address waits LOCKOUT_SECONDS."""

    failures: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    lock: threading.Lock = field(default_factory=threading.Lock)

    def blocked(self, address: str, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        with self.lock:
            recent = [t for t in self.failures[address] if now - t < LOCKOUT_SECONDS]
            self.failures[address] = recent
            return len(recent) >= MAX_FAILURES

    def failed(self, address: str, now: float | None = None) -> None:
        with self.lock:
            self.failures[address].append(time.time() if now is None else now)

    def passed(self, address: str) -> None:
        with self.lock:
            self.failures.pop(address, None)
