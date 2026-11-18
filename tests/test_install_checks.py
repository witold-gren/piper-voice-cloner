"""docker/install-ubuntu.sh on a pretend machine: every missing piece (driver, Docker, compose, access,
the NVIDIA toolkit) stops it before anything is written, with the command that fixes it."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import stat
import subprocess

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "docker" / "install-ubuntu.sh"
# the ordinary tools the script uses; the machine-specific ones are fakes below
TOOLS = [
    *("bash", "sh", "sed", "grep", "head", "tail", "tr", "mkdir"),
    *("chmod", "cat", "id", "cp", "seq", "dirname", "awk", "env", "rm"),
]

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash not installed")

FAKES = {
    "nvidia-smi": """
case "$*" in
  *driver_version*) [ -n "$FAKE_DRIVER" ] && echo "$FAKE_DRIVER" \
    || { echo "NVIDIA-SMI has failed" >&2; exit 9; } ;;
esac
""",
    "docker": """
echo "docker $*" >> "$FAKE_LOG"
case "$1 $2" in
  "compose version") [ -z "$FAKE_NO_COMPOSE" ] || exit 1 ;;
  "compose exec") echo "NVIDIA GeForce RTX 4090" ;;
  "compose up") [ -z "$FAKE_BUILD_FAILS" ] \
    || { echo "E: Unable to locate package espeak-ng" >&2; exit 17; } ;;
  info*) [ -z "$FAKE_NO_ACCESS" ] || exit 1; echo " Runtimes: io.containerd.runc.v2 $FAKE_RUNTIMES runc" ;;
esac
""",
    "systemctl": 'case "$*" in *docker*) exit 0 ;; esac; exit 1\n',
    "df": 'echo " Avail"; echo " ${FAKE_FREE_GB:-500}G"\n',
    "curl": 'echo \'{"status": "ok"}\'\n',
    "hostname": "echo 10.0.0.2\n",
    "sleep": "exit 0\n",
}


def fake_machine(tmp_path: Path, missing: tuple[str, ...] = ()) -> None:
    """The code folder (repo/) with docker/, its own HOME and a PATH holding only the tools and fakes."""
    repo = tmp_path / "repo"
    if not repo.exists():
        (repo / "docker").mkdir(parents=True)
        shutil.copy(SCRIPT, repo / "docker" / SCRIPT.name)
        (repo / "pyproject.toml").write_text('[project]\nname = "piper-voice-cloner"\n')
    bin_dir = tmp_path / "bin"
    if bin_dir.exists():
        return
    bin_dir.mkdir()
    for tool in TOOLS:
        found = shutil.which(tool)
        if found:
            (bin_dir / tool).symlink_to(found)
    for name, body in FAKES.items():
        if name in missing:
            continue
        fake = bin_dir / name
        fake.write_text("#!/bin/sh\n" + body)
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    (tmp_path / "home").mkdir()
    (tmp_path / "docker.log").touch()


def run(tmp_path: Path, *args: str, stdin: str = "", **env: str):
    base = {
        "PATH": str(tmp_path / "bin"),
        "HOME": str(tmp_path / "home"),
        "FAKE_LOG": str(tmp_path / "docker.log"),
        "FAKE_DRIVER": "580.178.04",
        "FAKE_RUNTIMES": "nvidia",
        "LANG": "C",
    }
    out = subprocess.run(
        [str(tmp_path / "bin" / "bash"), str(tmp_path / "repo" / "docker" / SCRIPT.name), *args],
        input=stdin,
        capture_output=True,
        text=True,
        env={**base, **env},
        timeout=60,
    )
    return out, (tmp_path / "docker.log").read_text()


def machine(tmp_path: Path, missing: tuple[str, ...] = (), **env: str):
    """Install on a fresh pretend machine."""
    fake_machine(tmp_path, missing)
    out, log = run(tmp_path, **env)
    return out, tmp_path / "repo" / "docker", log


@pytest.mark.parametrize(
    ("missing", "env", "message"),
    [
        (("nvidia-smi",), {}, "install the NVIDIA driver first"),
        ((), {"FAKE_DRIVER": ""}, "nvidia-smi does not see the card"),
        ((), {"FAKE_DRIVER": "535.309.01"}, "NVIDIA driver 535.309.01 is too old"),
        (("docker",), {}, "sudo apt install -y docker.io docker-compose-v2"),
        ((), {"FAKE_NO_COMPOSE": "1"}, "docker compose is missing"),
        ((), {"FAKE_NO_ACCESS": "1"}, "sudo usermod -aG docker"),
        ((), {"FAKE_RUNTIMES": ""}, "install nvidia-container-toolkit"),
    ],
    ids=[
        "no-driver",
        "driver-not-loaded",
        "old-driver",
        "no-docker",
        "no-compose",
        "no-access",
        "no-toolkit",
    ],
)
def test_a_missing_piece_stops_before_anything_is_written(tmp_path, missing, env, message):
    out, docker_dir, log = machine(tmp_path, missing, **env)
    assert out.returncode == 1, out.stdout + out.stderr
    assert message in out.stdout
    assert not (docker_dir / "config").exists() and not (docker_dir / ".env").exists()
    assert "compose up" not in log  # nothing built


def test_a_complete_machine_installs_and_starts(tmp_path):
    out, docker_dir, log = machine(tmp_path)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "NVIDIA driver 580.178.04" in out.stdout
    assert "docker compose up -d --build" in log
    env_file = docker_dir / "config" / "env"
    assert stat.S_IMODE(env_file.stat().st_mode) == 0o600
    assert stat.S_IMODE((docker_dir / "config").stat().st_mode) == 0o700
    user, _, password = env_file.read_text().strip().removeprefix("PVC_UI_AUTH=").partition(":")
    assert user == "admin" and len(password) == 20 and password not in out.stdout
    settings = (docker_dir / ".env").read_text()
    assert f"UID={os.getuid()}" in settings and "PVC_UI_PORT=7860" in settings
    assert "GPU in the container: NVIDIA GeForce RTX 4090" in out.stdout


def test_a_newer_driver_is_fine_and_little_space_only_warns(tmp_path):
    out, _, _ = machine(tmp_path, FAKE_DRIVER="590.10", FAKE_FREE_GB="20")
    assert out.returncode == 0, out.stdout + out.stderr
    assert "WARNING: only 20 GB free" in out.stdout


def test_a_failed_image_build_stops_with_its_error(tmp_path):
    """A package that does not install inside the image: the build's own message, no "waiting"."""
    out, _, _ = machine(tmp_path, FAKE_BUILD_FAILS="1")
    assert out.returncode == 17
    assert "Unable to locate package espeak-ng" in out.stderr
    assert "waiting for the editor" not in out.stdout


def test_running_it_again_keeps_the_password(tmp_path):
    machine(tmp_path)
    env_file = tmp_path / "repo" / "docker" / "config" / "env"
    first = env_file.read_text()
    out, _ = run(tmp_path)
    assert out.returncode == 0, out.stdout + out.stderr
    assert env_file.read_text() == first and "login written" not in out.stdout


def test_stop_only_stops_the_containers(tmp_path):
    machine(tmp_path)
    out, log = run(tmp_path, "--stop")
    assert out.returncode == 0, out.stdout + out.stderr
    assert log.splitlines()[-1] == "docker compose stop"
    assert "stays off after a reboot" in out.stdout
    assert (tmp_path / "repo" / "docker" / "config" / "env").exists()


@pytest.fixture
def installed(tmp_path):
    """Installed with the voices in their own folder outside the code, as on the real machine."""
    data = tmp_path / "home" / "voices"
    fake_machine(tmp_path)
    data.mkdir()
    (data / "kasia.txt").write_text("a voice")
    out, _ = run(tmp_path, PVC_DATA=str(data))
    assert out.returncode == 0, out.stdout + out.stderr
    return data


def test_uninstall_asks_first_and_removes_nothing_without_yes(tmp_path, installed):
    out, log = run(tmp_path, "--uninstall", stdin="no\n")
    assert out.returncode == 1 and "Nothing removed." in out.stdout
    assert "down" not in log
    assert (tmp_path / "repo" / "docker" / "config" / "env").exists()


@pytest.mark.parametrize("how", [{"stdin": "yes\n"}, {"args": ("--yes",)}], ids=["typed-yes", "flag"])
def test_uninstall_removes_everything_but_the_voices(tmp_path, installed, how):
    out, log = run(tmp_path, "--uninstall", *how.get("args", ()), stdin=how.get("stdin", ""))
    assert out.returncode == 0, out.stdout + out.stderr
    assert "docker compose down --rmi all --remove-orphans" in log
    assert not (tmp_path / "repo").exists()
    assert (installed / "kasia.txt").read_text() == "a voice"
    assert f"The voices stay: {installed}" in out.stdout


def test_uninstall_keeps_the_code_folder_when_the_voices_are_inside(tmp_path):
    machine(tmp_path)  # no PVC_DATA and no ~/piper-voice-cloner/data: the voices go to docker/data
    data = tmp_path / "repo" / "docker" / "data"
    (data / "kasia.txt").write_text("a voice")
    out, _ = run(tmp_path, "--uninstall", "--yes")
    assert out.returncode == 0, out.stdout + out.stderr
    assert (data / "kasia.txt").exists() and "the code folder stays" in out.stdout
    assert not (tmp_path / "repo" / "docker" / "config").exists()
    assert not (tmp_path / "repo" / "docker" / ".env").exists()


def test_uninstall_never_removes_a_folder_that_is_not_the_editor(tmp_path, installed):
    (tmp_path / "repo" / "pyproject.toml").write_text('[project]\nname = "something-else"\n')
    out, _ = run(tmp_path, "--uninstall", "--yes")
    assert out.returncode == 0, out.stdout + out.stderr
    assert (tmp_path / "repo" / "pyproject.toml").exists() and "left as it is" in out.stdout
