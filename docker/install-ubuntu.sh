#!/usr/bin/env bash
# The voice editor on the GPU machine: first install, or again to repair (run on the machine, or from
# the Mac with `make install`).
#
#   docker/install-ubuntu.sh                checks, login, folders, autostart, build, start
#   STUDIO_TRUSTED_NETWORKS=192.168.1.0/24 docker/install-ubuntu.sh   ... and no login from that network
#   docker/install-ubuntu.sh --show-login   the editor's user and password
#   docker/install-ubuntu.sh --remove       stops and removes the containers (data and settings stay)
#   docker/install-ubuntu.sh --stop         stops the containers; they stay off after a reboot
#                                           (make deploy or docker compose up -d starts them again)
#   docker/install-ubuntu.sh --uninstall [--yes]
#                                           removes the containers, the image, the login, the settings
#                                           and the code folder; the voices (PVC_DATA) stay
#
# PVC_DATA=<folder> keeps the data in an existing folder (default: ~/piper-voice-cloner/data when it
# exists, else docker/data). Nothing is copied: big data stays where it is.
set -euo pipefail

DOCKER_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$DOCKER_DIR")"
cd "$DOCKER_DIR"
CONFIG="$DOCKER_DIR/config"
ENV_FILE="$DOCKER_DIR/.env"
OLD_CONFIG="$HOME/.config/piper-voice-cloner"

uninstall() {
  local data
  data="$(sed -n 's/^PVC_DATA=//p' "$ENV_FILE" 2>/dev/null || true)"
  echo "This removes from $(hostname):"
  echo "  the editor's and TensorBoard's containers and the image piper-voice-cloner"
  echo "  the login and the settings: $CONFIG, $ENV_FILE (Home Assistant connection, ElevenLabs key)"
  echo "  the code folder: $REPO_DIR"
  echo "The voices stay: ${data:-$DOCKER_DIR/data}"
  if [ "${1:-}" != "--yes" ]; then
    read -r -p "Type yes to remove: " answer || answer=""
    [ "$answer" = "yes" ] || { echo "Nothing removed."; exit 1; }
  fi
  if command -v docker >/dev/null; then
    docker compose down --rmi all --remove-orphans || echo "WARNING: docker compose down failed (already removed?)"
  fi
  rm -rf -- "$CONFIG" "$ENV_FILE"
  echo "Login and settings removed."
  case "${data:-$DOCKER_DIR/data}/" in
    "$REPO_DIR"/*)
      echo "The voices are inside the code folder, so the code folder stays: $REPO_DIR"
      echo "Move them out (PVC_DATA) or remove the folder by hand."
      exit 0
      ;;
  esac
  # only a folder that really is this application's code, never HOME or /
  if [ -f "$REPO_DIR/pyproject.toml" ] && grep -q '^name = "piper-voice-cloner"' "$REPO_DIR/pyproject.toml" \
    && [ "$REPO_DIR" != "$HOME" ] && [ "$REPO_DIR" != "/" ]; then
    cd /
    rm -rf -- "$REPO_DIR"
    echo "Code folder removed: $REPO_DIR"
  else
    echo "WARNING: $REPO_DIR does not look like the editor's code, left as it is"
  fi
  echo "Done. Install again: make install"
  exit 0
}

case "${1:-}" in
  --stop)
    docker compose stop
    echo "Stopped; stays off after a reboot. Start again: make deploy (or docker compose up -d here)."
    exit 0
    ;;
  --uninstall)
    uninstall "${2:-}"
    ;;
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
  *) echo "usage: $0 [--show-login | --stop | --remove | --uninstall [--yes]]"; exit 2 ;;
esac

echo "== checks"
MIN_DRIVER=580  # the torch in the image is built for CUDA 13.0 (docker/Dockerfile, TRAIN_TORCH)
command -v nvidia-smi >/dev/null || { echo "no nvidia-smi: install the NVIDIA driver first (sudo ubuntu-drivers install), then reboot"; exit 1; }
driver="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -1 | tr -d ' ' || true)"
[ -n "$driver" ] || { echo "nvidia-smi does not see the card: reboot after installing the driver (nvidia-smi shows why)"; exit 1; }
[ "${driver%%.*}" -ge "$MIN_DRIVER" ] 2>/dev/null || {
  echo "NVIDIA driver $driver is too old: the image needs $MIN_DRIVER or newer: sudo apt install -y nvidia-driver-$MIN_DRIVER, then reboot"
  exit 1
}
echo "NVIDIA driver $driver"
command -v docker >/dev/null || { echo "Docker is missing: sudo apt install -y docker.io docker-compose-v2"; exit 1; }
docker compose version >/dev/null || { echo "docker compose is missing: sudo apt install -y docker-compose-v2"; exit 1; }
docker info >/dev/null 2>&1 || { echo "no access to Docker: sudo usermod -aG docker $(id -un), then log in again"; exit 1; }
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
# STUDIO_TRUSTED_NETWORKS=192.168.1.0/24 (the same name in every studio): no login from these networks;
# set: written or replaced in config/env, set but empty: removed (login always), not set: left as it is
if [ -n "${STUDIO_TRUSTED_NETWORKS+set}" ]; then
  (umask 077 && grep -v '^STUDIO_TRUSTED_NETWORKS=' "$CONFIG/env" >"$CONFIG/env.new" || true)
  [ -z "$STUDIO_TRUSTED_NETWORKS" ] || printf 'STUDIO_TRUSTED_NETWORKS=%s\n' "$STUDIO_TRUSTED_NETWORKS" >>"$CONFIG/env.new"
  mv "$CONFIG/env.new" "$CONFIG/env"
  echo "no login from: ${STUDIO_TRUSTED_NETWORKS:-nowhere (login always)}"
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
