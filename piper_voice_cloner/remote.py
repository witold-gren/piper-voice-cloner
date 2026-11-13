"""The GPU machine reached over SSH: send the code and the voice data, install, bring results back.

The web UI and the CLI (`pvc remote ...`) run the commands built here. The settings live in
``<root>/server.json`` (no secrets - only the path of the SSH key). On the machine everything sits in
one folder inside the home directory::

    ~/<remote_dir>/repo   this repository (environments .venv*, third_party/ are created there)
    ~/<remote_dir>/data   the private data (PVC_HOME): voices, bases, jobs
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import json
from pathlib import Path
import re
import shlex

CONFIG_FILE = "server.json"
HOST_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
USER_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
REMOTE_DIR_PATTERN = re.compile(r"^[A-Za-z0-9._/-]+$")

# never sent: local environments and caches, private data inside the repo by mistake
CODE_EXCLUDES = [
    ".git/",
    ".venv*/",
    "third_party/",
    "__pycache__/",
    ".pytest_cache/",
    ".ruff_cache/",
    "*.egg-info/",
    "build/",
    "backup/",
    "voices/",
    "bases/",
    "lightning_logs/",
]
# data made on the machine stays there (checkpoints, exports, job logs) - and is never deleted
DATA_EXCLUDES = ["jobs/", "bases/", CONFIG_FILE, "voices/*/train/", "voices/*/export/"]

# tools scripts/setup.sh needs; the apt hint only when one is missing (no sudo over SSH)
SETUP_TOOLS = {
    "rsync": "rsync", "ffmpeg": "ffmpeg", "espeak-ng": "espeak-ng", "git": "git",
    "cmake": "cmake", "gcc": "build-essential",
}  # fmt: skip
CHECK_SCRIPT = (
    'export PATH="$HOME/.local/bin:$PATH"; missing=""; '
    'echo "host: $(hostname)"; '
    "(nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null"
    " | sed 's/^/gpu: /') || echo 'gpu: none (nvidia-smi not found)'; "
    'echo "free disk: $(df -h "$HOME" | awk \'NR==2{print $4}\')"; '
    + "".join(
        f'if command -v {tool} >/dev/null; then echo "{tool}: yes"; '
        f'else echo "{tool}: MISSING"; missing="$missing {package}"; fi; '
        for tool, package in SETUP_TOOLS.items()
    )
    + 'if command -v uv >/dev/null; then echo "uv: yes"; '
    'else echo "uv: MISSING - curl -LsSf https://astral.sh/uv/install.sh | sh"; fi; '
    'if [ -n "$missing" ]; then echo; echo "Install once on the machine: sudo apt install$missing"; fi'
)

# is a job of the web UI running on the machine? Reads <data>/jobs/current.json there (see webui/jobs.py)
# with the system python3 - no environment of ours needed; prints one JSON line
JOB_STATE_CODE = """
import json, os, sys
try:
    state = json.load(open(sys.argv[1]))
except Exception:
    state = {}
pid, alive = state.get("runner_pid"), False
if pid and "returncode" not in state:
    try:
        os.kill(pid, 0)
        alive = True
    except PermissionError:
        alive = True
    except OSError:
        pass
print(json.dumps({"running": alive, "kind": state.get("kind", ""), "voice": state.get("voice", "")}))
"""


def parse_job_state(output: str) -> dict:
    """The last JSON line of the job check -> {"running", "kind", "voice"}."""
    for line in reversed(output.strip().splitlines()):
        try:
            data = json.loads(line)
        except ValueError:
            continue
        if isinstance(data, dict) and "running" in data:
            return {"running": bool(data["running"]), "kind": str(data.get("kind") or ""),
                    "voice": str(data.get("voice") or "")}  # fmt: skip
    raise RuntimeError(f"unexpected answer of the machine: {output.strip()[:200] or '(nothing)'}")


@dataclass
class ServerConfig:
    host: str = ""
    user: str = ""
    port: int = 22
    key: str = ""  # path of the private key, empty = ssh defaults / agent
    remote_dir: str = "piper-voice-cloner"
    ui_port: int = 7860

    def validate(self) -> None:
        if not HOST_PATTERN.match(self.host):
            raise ValueError("host: a name or IP address, e.g. ubuntu.local")
        if self.user and not USER_PATTERN.match(self.user):
            raise ValueError("user: letters, digits, . _ -")
        for name in ("port", "ui_port"):
            if not 0 < int(getattr(self, name)) < 65536:
                raise ValueError(f"{name}: 1-65535")
        if (
            not REMOTE_DIR_PATTERN.match(self.remote_dir)
            or self.remote_dir.startswith("/")
            or ".." in self.remote_dir.split("/")
        ):
            raise ValueError("remote folder: a path inside the home folder, e.g. piper-voice-cloner")
        if self.key and not Path(self.key).expanduser().is_file():
            raise ValueError(f"SSH key {self.key} not found")

    @property
    def target(self) -> str:
        return f"{self.user}@{self.host}" if self.user else self.host

    @property
    def ui_url(self) -> str:
        return f"http://{self.host}:{self.ui_port}/"


def config_path(root: Path) -> Path:
    return root / CONFIG_FILE


def load_config(root: Path) -> ServerConfig | None:
    path = config_path(root)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    known = {f.name for f in fields(ServerConfig)}
    return ServerConfig(**{k: v for k, v in data.items() if k in known})


def save_config(root: Path, config: ServerConfig) -> Path:
    config.port, config.ui_port = int(config.port), int(config.ui_port)
    config.validate()
    path = config_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(config), indent=2) + "\n", encoding="utf-8")
    return path


def ssh_keys(folder: Path | None = None) -> list[str]:
    """Private keys in ~/.ssh (files with a matching .pub)."""
    folder = folder or Path.home() / ".ssh"
    if not folder.is_dir():
        return []
    return sorted(str(p) for p in folder.iterdir() if p.is_file() and (p.parent / f"{p.name}.pub").exists())


def repo_dir() -> Path:
    """This repository (the package is installed editable from it)."""
    repo = Path(__file__).resolve().parent.parent
    if not (repo / "pyproject.toml").is_file():
        raise RuntimeError(
            f"{repo} is not the piper-voice-cloner repository (install it with pip install -e)"
        )
    return repo


class Remote:
    def __init__(self, config: ServerConfig) -> None:
        self.config = config
        self.repo = f"{config.remote_dir}/repo"
        self.data = f"{config.remote_dir}/data"

    def ssh_options(self) -> list[str]:
        options = [
            "-p", str(self.config.port),
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=10",
            "-o", "ControlMaster=auto",
            "-o", "ControlPersist=10m",
            "-o", f"ControlPath={Path.home() / '.ssh'}/pvc-%r@%h-%p",
        ]  # fmt: skip
        if self.config.key:
            options += ["-i", str(Path(self.config.key).expanduser()), "-o", "IdentitiesOnly=yes"]
        return options

    def ssh(self, script: str) -> list[str]:
        return ["ssh", *self.ssh_options(), self.config.target, script]

    def _rsync(self) -> list[str]:
        # plain options only: macOS ships an old rsync (no --mkpath, --info)
        return ["rsync", "-az", "--stats", "-e", shlex.join(["ssh", *self.ssh_options()])]

    def check(self) -> list[list[str]]:
        return [self.ssh(CHECK_SCRIPT)]

    def job_state(self) -> list[str]:
        """The command that tells whether a job of the web UI runs on the machine (see parse_job_state)."""
        state = f"{self.data}/jobs/current.json"
        return self.ssh(f"python3 -c {shlex.quote(JOB_STATE_CODE)} {shlex.quote(state)}")

    def push(self, local_root: Path) -> list[list[str]]:
        """Code (mirrored, remote environments kept) and the voice data (added/updated, never deleted)."""
        target = self.config.target
        code = [*self._rsync(), "--delete", *[f"--exclude={e}" for e in CODE_EXCLUDES]]
        data = [*self._rsync(), *[f"--exclude={e}" for e in DATA_EXCLUDES]]
        return [
            self.ssh(f"mkdir -p {shlex.quote(self.repo)} {shlex.quote(self.data)}"),
            [*code, f"{repo_dir()}/", f"{target}:{self.repo}/"],
            self.write_stamp(code_stamp()),
            [*data, f"{local_root}/", f"{target}:{self.data}/"],
        ]

    def install(self) -> list[list[str]]:
        """Environments (scripts/setup.sh) + the web UI service pointing at the synced data."""
        script = (
            'export PATH="$HOME/.local/bin:$PATH"; '
            f'export PVC_HOME="$HOME/{self.data}"; '
            f"cd {shlex.quote(self.repo)} && ./scripts/setup.sh && "
            f"PVC_UI_PORT={int(self.config.ui_port)} ./scripts/install-service.sh"
        )
        return [self.ssh(script)]

    def status(self) -> list[str]:
        """The one SSH call behind the checklist (see STATUS_CODE / parse_status)."""
        args = [self.config.remote_dir, str(int(self.config.ui_port)), json.dumps(list(SETUP_TOOLS))]
        return self.ssh(f"python3 -c {shlex.quote(STATUS_CODE)} {shlex.join(args)}")

    def write_stamp(self, stamp: str) -> list[str]:
        return self.ssh(f"printf %s {shlex.quote(stamp)} > {shlex.quote(self.repo)}/{STAMP_FILE}")

    def apt_install(self, packages: list[str]) -> list[str]:
        """Only with sudo that needs no password (sudo -n); otherwise the checklist shows the command."""
        names = shlex.join(packages)
        return self.ssh(f"sudo -n env DEBIAN_FRONTEND=noninteractive apt-get install -y {names}")

    def restart_ui(self) -> list[str]:
        """Only the web UI service (new code) - a running training survives (KillMode=process, the job
        runs in its own process group)."""
        return self.ssh("systemctl --user restart piper-voice-cloner")

    def install_uv(self) -> list[str]:
        return self.ssh("curl -LsSf https://astral.sh/uv/install.sh | sh")

    def pull(self, local_root: Path) -> list[list[str]]:
        """Exported voices (.onnx + .onnx.json + samples) back to this computer."""
        return [
            [
                *self._rsync(),
                "--include=*/",
                "--include=voices/*/export/**",
                "--exclude=*",
                "--prune-empty-dirs",
                f"{self.config.target}:{self.data}/",
                f"{local_root}/",
            ]
        ]


# --- readiness: what the machine has and what is still to do ----------------------------------------

STATUS_FILE = "server_status.json"  # inside <root>/jobs/ (never sent to the machine)
STAMP_FILE = ".pvc-stamp"  # in the repo on the machine: the code version sent last
# folders of the repository that never count for the code version (same idea as CODE_EXCLUDES)
STAMP_SKIP = {"third_party", "__pycache__", ".pytest_cache", ".ruff_cache", "build", "backup", "voices",
              "bases", "lightning_logs", ".git"}  # fmt: skip
TB_PORT = 6006  # TensorBoard on the machine (PVC_TB_PORT in its env file)
MIN_FREE_GB = 30  # a base training keeps ~10 GB of checkpoints plus the cache

# everything the machine knows about itself, in one SSH call, with the system python3; prints one
# "PVC-STATUS {json}" line. argv: <remote_dir> <ui port> <tools as JSON>
STATUS_CODE = """
import json, os, shutil, socket, subprocess, sys
home = os.path.expanduser("~")
base, port, tools = os.path.join(home, sys.argv[1]), int(sys.argv[2]), json.loads(sys.argv[3])
os.environ["PATH"] = home + "/.local/bin:" + os.environ.get("PATH", "")
repo, data = os.path.join(base, "repo"), os.path.join(base, "data")


def run(command, timeout=20):
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        return done.returncode, done.stdout.strip(), done.stderr.strip()
    except (OSError, subprocess.TimeoutExpired) as err:
        return -1, "", str(err)


out = {"host": socket.gethostname()}
code, text, _ = run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
                     "--format=csv,noheader,nounits"])
out["gpu"] = text.splitlines()[0] if code == 0 and text else ""
out["tools"] = {tool: bool(shutil.which(tool)) for tool in tools}
out["uv"] = bool(shutil.which("uv"))
out["sudo"] = run(["sudo", "-n", "true"], 5)[0] == 0
disk = os.statvfs(home)
out["free_gb"] = round(disk.f_bavail * disk.f_frsize / 1e9, 1)
try:
    out["stamp"] = open(os.path.join(repo, ".pvc-stamp")).read().strip()
except OSError:
    out["stamp"] = ""
out["venv"] = os.access(os.path.join(repo, ".venv/bin/pvc"), os.X_OK)
python = os.path.join(repo, ".venv-train/bin/python")
out["train"], out["train_error"] = "missing", ""
if os.access(python, os.X_OK):
    code, text, err = run([python, "-c", "import torch, torchaudio, piper.espeakbridge, "
                           "piper.train.vits.monotonic_align; print(torch.cuda.is_available())"], 180)
    out["train"] = "broken" if code else ("cuda" if text.endswith("True") else "cpu")
    out["train_error"] = (err.splitlines() or [""])[-1][:300] if code else ""
voices, folder = {}, os.path.join(data, "voices")
for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
    meta = os.path.join(folder, name, "dataset", "metadata.csv")
    if os.path.isfile(meta):
        with open(meta, encoding="utf-8", errors="replace") as lines:
            voices[name] = sum(1 for line in lines if line.strip())
out["voices"] = voices
out["service"] = run(["systemctl", "--user", "is-active", "piper-voice-cloner"], 5)[1] or "unknown"
try:
    socket.create_connection(("127.0.0.1", port), 2).close()
    out["ui"] = True
except OSError:
    out["ui"] = False
out["login"], tb_port = "", 6006
try:
    for line in open(os.path.join(home, ".config/piper-voice-cloner/env")):
        if line.startswith("PVC_UI_AUTH="):
            out["login"] = line.split("=", 1)[1].strip()
        elif line.startswith("PVC_TB_PORT=") and line.split("=", 1)[1].strip().isdigit():
            tb_port = int(line.split("=", 1)[1])
except OSError:
    pass
try:
    socket.create_connection(("127.0.0.1", tb_port), 2).close()
    out["tensorboard"] = tb_port
except OSError:
    out["tensorboard"] = 0
print("PVC-STATUS " + json.dumps(out))
"""


def parse_status(output: str) -> dict:
    """The "PVC-STATUS {json}" line of the status check."""
    for line in reversed(output.strip().splitlines()):
        if line.startswith("PVC-STATUS "):
            return json.loads(line[len("PVC-STATUS ") :])
    raise RuntimeError(f"unexpected answer of the machine: {output.strip()[-200:] or '(nothing)'}")


def code_stamp(repo: Path | None = None) -> str:
    """A short hash of the code that push sends: equal on both sides = the machine runs this code."""
    import hashlib
    import os

    repo = repo or repo_dir()
    digest = hashlib.sha1()
    for folder, dirs, files in os.walk(repo):
        dirs[:] = sorted(
            d
            for d in dirs
            if d not in STAMP_SKIP and not d.startswith(".venv") and not d.endswith(".egg-info")
        )
        for name in sorted(files):
            if name == STAMP_FILE or name.endswith(".pyc"):
                continue
            path = Path(folder) / name
            digest.update(str(path.relative_to(repo)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def local_voices(root: Path) -> dict[str, int]:
    """Clips per voice dataset on this computer (the lines of dataset/metadata.csv)."""
    counts = {}
    folder = root / "voices"
    for meta in sorted(folder.glob("*/dataset/metadata.csv")) if folder.is_dir() else []:
        with meta.open(encoding="utf-8", errors="replace") as lines:
            counts[meta.parent.parent.name] = sum(1 for line in lines if line.strip())
    return counts


def status_path(root: Path) -> Path:
    return root / "jobs" / STATUS_FILE


def save_status(root: Path, status: dict | None, error: str = "") -> dict:
    import time

    saved = {"checked": time.time(), "status": status, "error": error}
    path = status_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(saved, indent=1) + "\n", encoding="utf-8")
    return saved


def load_status(root: Path) -> dict | None:
    try:
        return json.loads(status_path(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


@dataclass
class Item:
    """One line of the checklist: ``state`` is ok / todo (Prepare does it) / manual (you do it) / warn."""

    key: str
    state: str
    detail: str = ""
    command: str = ""  # what to run yourself (manual items)


def apt_packages(status: dict) -> list[str]:
    return sorted({SETUP_TOOLS[tool] for tool, found in status.get("tools", {}).items() if not found})


def evaluate(status: dict, config: ServerConfig, local: dict[str, int], stamp: str) -> list[Item]:
    """The checklist for the panel and `pvc remote status`, in the order Prepare works through it."""
    items = []
    gpu = status.get("gpu", "")
    if gpu:
        name, memory, driver = ([*(p.strip() for p in gpu.split(",")), "", ""])[:3]
        size = f"{float(memory) / 1024:.0f} GB" if memory.replace(".", "").isdigit() else memory
        items.append(Item("gpu", "ok", f"{name} · {size} · driver {driver}"))
    else:
        items.append(Item("gpu", "manual", command="sudo ubuntu-drivers install && sudo reboot"))
    packages = apt_packages(status)
    if not packages:
        items.append(Item("tools", "ok", ", ".join(SETUP_TOOLS)))
    elif status.get("sudo"):
        items.append(Item("tools", "todo", " ".join(packages)))
    else:
        port = f" -p {config.port}" if int(config.port) != 22 else ""
        command = f"ssh -t{port} {config.target} sudo apt install -y {' '.join(packages)}"
        items.append(Item("tools", "manual", " ".join(packages), command))
    items.append(Item("uv", "ok" if status.get("uv") else "todo"))
    free = float(status.get("free_gb") or 0)
    items.append(Item("disk", "ok" if free >= MIN_FREE_GB else "warn", f"{free:.0f} GB"))
    remote_stamp = status.get("stamp", "")
    items.append(Item("code", "ok" if remote_stamp == stamp else "todo", remote_stamp or "-"))
    remote = status.get("voices", {})
    stale = [name for name, count in local.items() if remote.get(name) != count]
    detail = ", ".join(f"{name} {count}" for name, count in remote.items() if name not in stale)
    items.append(Item("data", "todo" if stale else "ok", ", ".join(stale) if stale else detail or "-"))
    items.append(Item("venv", "ok" if status.get("venv") else "todo"))
    train = status.get("train", "missing")
    if train == "cuda":
        items.append(Item("train", "ok", "torch + CUDA"))
    elif train == "cpu":
        items.append(Item("train", "warn", "torch without CUDA"))
    else:
        items.append(Item("train", "todo", status.get("train_error", "") if train == "broken" else ""))
    active = status.get("service") == "active" and status.get("ui")
    items.append(Item("service", "ok" if active else "todo", config.ui_url))
    port = status.get("tensorboard")
    items.append(Item("tensorboard", "ok" if port else "todo", f"http://{config.host}:{port or TB_PORT}/"))
    return items


def summary(items: list[Item]) -> str:
    """ready / todo (Prepare can do the rest) / manual (something only you can do first)."""
    states = {item.state for item in items}
    if "manual" in states:
        return "manual"
    return "todo" if "todo" in states else "ready"
