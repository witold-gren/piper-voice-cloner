#!/usr/bin/env bash
# Runs the web UI as a systemd *user* service (no root needed), started at boot.
#   ./scripts/install-service.sh            install / update and start
#   ./scripts/install-service.sh --remove   stop and remove
# Settings live in ~/.config/piper-voice-cloner/env (created on first run, chmod 600).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NAME=piper-voice-cloner
UNIT_DIR="$HOME/.config/systemd/user"
CONF_DIR="$HOME/.config/$NAME"
ENV_FILE="$CONF_DIR/env"

TB_NAME="$NAME-tensorboard"

if [ "${1:-}" = "--remove" ]; then
  for unit in "$NAME" "$TB_NAME"; do
    systemctl --user disable --now "$unit.service" 2>/dev/null || true
    rm -f "$UNIT_DIR/$unit.service"
  done
  systemctl --user daemon-reload
  echo "Removed $NAME.service and $TB_NAME.service (settings kept in $ENV_FILE)"
  exit 0
fi

[ -x "$ROOT/.venv/bin/pvc" ] || { echo "run ./scripts/setup.sh first"; exit 1; }

mkdir -p "$UNIT_DIR" "$CONF_DIR"
if [ ! -f "$ENV_FILE" ]; then
  password="$(head -c 18 /dev/urandom | base64 | tr -d '/+=' | head -c 20)"
  umask 077
  cat > "$ENV_FILE" <<EOF
# Private voice data (outside the repository)
PVC_HOME=${PVC_HOME:-$HOME/home-assistant/voices-private}
PVC_TRAIN_PYTHON=$ROOT/.venv-train/bin/python
# Login for the web page: user:password
PVC_UI_AUTH=admin:$password
# UI language (en / pl) and port
PVC_UI_LANG=pl
PVC_UI_PORT=${PVC_UI_PORT:-7860}
# TensorBoard (training charts; the panel links to it)
PVC_TB_PORT=${PVC_TB_PORT:-6006}
# ElevenLabs backend only:
# ELEVENLABS_API_KEY=
EOF
  echo "Created $ENV_FILE - login: admin / $password"
fi
chmod 600 "$ENV_FILE"
# shellcheck disable=SC1090
. "$ENV_FILE"
mkdir -p "$PVC_HOME"

cat > "$UNIT_DIR/$NAME.service" <<EOF
[Unit]
Description=Piper Voice Cloner web UI
After=network-online.target

[Service]
EnvironmentFile=$ENV_FILE
WorkingDirectory=$ROOT
ExecStart=/bin/sh -c 'exec "$ROOT/.venv/bin/pvc" --root "\$PVC_HOME" ui --host 0.0.0.0 --port "\${PVC_UI_PORT:-7860}" --lang "\${PVC_UI_LANG:-en}"'
Restart=on-failure
RestartSec=5
# stopping or restarting the UI must not kill a running training job
KillMode=process

[Install]
WantedBy=default.target
EOF

# TensorBoard over all training runs of the data folder (bases and voices): the charts; the audio
# samples are also in the panel. No login: reachable in the local network only.
if [ -x "$ROOT/.venv-train/bin/tensorboard" ]; then
  cat > "$UNIT_DIR/$TB_NAME.service" <<EOF
[Unit]
Description=Piper Voice Cloner TensorBoard (training charts)
After=network-online.target

[Service]
EnvironmentFile=$ENV_FILE
ExecStart=/bin/sh -c 'exec "$ROOT/.venv-train/bin/tensorboard" --logdir "\$PVC_HOME" --bind_all --port "\${PVC_TB_PORT:-6006}" --reload_interval 60'
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
EOF
fi

systemctl --user daemon-reload
systemctl --user enable --now "$NAME.service"
systemctl --user restart "$NAME.service"
if [ -f "$UNIT_DIR/$TB_NAME.service" ]; then
  systemctl --user enable --now "$TB_NAME.service"
  systemctl --user restart "$TB_NAME.service"
fi

# start at boot without logging in (allowed for your own user on most systems)
if ! loginctl show-user "$USER" -p Linger 2>/dev/null | grep -q yes; then
  loginctl enable-linger "$USER" 2>/dev/null \
    || echo "NOTE: could not enable lingering; the UI starts when you log in (ask an admin: loginctl enable-linger $USER)"
fi

echo
echo "Web UI: http://$(hostname -I 2>/dev/null | awk '{print $1}'):${PVC_UI_PORT:-7860}  (login from $ENV_FILE)"
echo "TensorBoard: http://$(hostname -I 2>/dev/null | awk '{print $1}'):${PVC_TB_PORT:-6006}"
echo "Logs:   journalctl --user -u $NAME -f"
