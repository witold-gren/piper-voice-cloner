#!/usr/bin/env bash
# The voice editor on the GPU machine: first install, or again to repair (run on the machine, or from
# the Mac with `make install`).
#
#   docker/install-ubuntu.sh                checks, login, folders, autostart, build, start
#   docker/install-ubuntu.sh --show-login   the editor's user and password
#   docker/install-ubuntu.sh --remove       stops and removes the containers (data and settings stay)
#
# PVC_DATA=<folder> keeps the data in an existing folder (default: ~/piper-voice-cloner/data when it
# exists, else docker/data). Nothing is copied: big data stays where it is.
set -euo pipefail

DOCKER_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DOCKER_DIR"
CONFIG="$DOCKER_DIR/config"
ENV_FILE="$DOCKER_DIR/.env"
OLD_CONFIG="$HOME/.config/piper-voice-cloner"

case "${1:-}" in
  --show-login)
    test -f "$CONFIG/env" || { echo "not installed yet: make install"; exit 1; }
    sed -n 's/^PVC_UI_AUTH=\([^:]*\):\(.*\)$/user: \1\npassword: \2/p' "$CONFIG/env"
    exit 0
    ;;
  --remove)
    docker compose down
    echo "Containers removed. Data ($(sed -n 's/^PVC_DATA=//p' "$ENV_FILE" 2>/dev/null)) and docker/config stay."
    exit 0
    ;;
  "") ;;
  *) echo "usage: $0 [--show-login | --remove]"; exit 2 ;;
esac

echo "== checks"
command -v nvidia-smi >/dev/null || { echo "no nvidia-smi: install the NVIDIA driver first"; exit 1; }
command -v docker >/dev/null || { echo "Docker is missing: sudo apt install -y docker.io docker-compose-v2"; exit 1; }
docker compose version >/dev/null || { echo "docker compose is missing: sudo apt install -y docker-compose-v2"; exit 1; }
docker info >/dev/null 2>&1 || { echo "no access to Docker: sudo usermod -aG docker $USER, then log in again"; exit 1; }
docker info 2>/dev/null | grep -qi nvidia || {
  echo "Docker does not know the NVIDIA runtime: install nvidia-container-toolkit, then"
  echo "  sudo nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker"
  exit 1
}
systemctl is-enabled docker >/dev/null 2>&1 || echo "WARNING: Docker does not start with the machine: sudo systemctl enable docker"
free_gb=$(df -BG --output=avail "$HOME" | tail -1 | tr -dc 0-9)
[ "${free_gb:-0}" -ge 60 ] || echo "WARNING: only ${free_gb} GB free (the image needs ~15 GB, a voice ~10 GB)"

# the old panel (systemd user services) used the same ports
for unit in piper-voice-cloner piper-voice-cloner-tensorboard; do
  if systemctl --user is-enabled "$unit" >/dev/null 2>&1 || systemctl --user is-active "$unit" >/dev/null 2>&1; then
    echo "== switching the old panel off: $unit"
    systemctl --user disable --now "$unit"
  fi
done

echo "== settings"
mkdir -p "$CONFIG"
chmod 700 "$CONFIG"
if [ ! -f "$CONFIG/env" ]; then
  password="$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 20 || true)"
  (umask 077 && printf 'PVC_UI_AUTH=admin:%s\n' "$password" >"$CONFIG/env")
  echo "login written to docker/config/env (make login shows it)"
fi
# the Home Assistant connection and the ElevenLabs key of the old panel come along (small files)
for file in home_assistant.json elevenlabs.json; do
  if [ -f "$OLD_CONFIG/$file" ] && [ ! -f "$CONFIG/$file" ]; then
    cp -p "$OLD_CONFIG/$file" "$CONFIG/$file"
    echo "taken over: $OLD_CONFIG/$file"
  fi
done
chmod 600 "$CONFIG"/* 2>/dev/null || true

if [ ! -f "$ENV_FILE" ]; then
  data="${PVC_DATA:-}"
  if [ -z "$data" ]; then
    if [ -d "$HOME/piper-voice-cloner/data" ]; then data="$HOME/piper-voice-cloner/data"; else data="$DOCKER_DIR/data"; fi
  fi
  mkdir -p "$data"
  cat >"$ENV_FILE" <<EOF
# docker compose settings of the voice editor (written by install-ubuntu.sh)
UID=$(id -u)
GID=$(id -g)
PVC_DATA=$data
PVC_UI_PORT=7860
PVC_TB_PORT=6006
EOF
  echo "data folder: $data"
fi

echo "== building and starting (the first time 15-30 min)"
docker compose up -d --build

echo "== waiting for the editor"
port="$(sed -n 's/^PVC_UI_PORT=//p' "$ENV_FILE")"
for _ in $(seq 1 60); do
  curl -sf "http://127.0.0.1:${port}/api/health" >/dev/null && break
  sleep 2
done
curl -sf "http://127.0.0.1:${port}/api/health" || { echo "the editor does not answer: docker compose logs studio"; exit 1; }
echo
echo "GPU in the container: $(docker compose exec -T studio nvidia-smi --query-gpu=name --format=csv,noheader 2>&1 | head -1)"
echo "The editor: http://$(hostname -I | awk '{print $1}'):${port}   (login: make login)"
