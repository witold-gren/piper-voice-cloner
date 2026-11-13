#!/usr/bin/env bash
# Sets up the two environments on an Ubuntu machine with an NVIDIA GPU:
#   .venv        - pvc + Chatterbox + quality checks (faster-whisper, sherpa-onnx, UTMOS)
#   .venv-train  - OHF-Voice/piper1-gpl training (its own torch/lightning versions)
# Optional: XTTS_ENV=1 also creates .venv-xtts for the XTTS-v2 backend.
set -euo pipefail

PIPER_REF="${PIPER_REF:-v1.8.0}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

need() { command -v "$1" >/dev/null || { echo "missing: $1 ($2)"; exit 1; }; }
need uv "curl -LsSf https://astral.sh/uv/install.sh | sh"
need ffmpeg "sudo apt install ffmpeg"
need espeak-ng "sudo apt install espeak-ng"
need cmake "sudo apt install build-essential cmake ninja-build"

echo "== .venv (pvc, Chatterbox, quality checks)"
uv venv --allow-existing --python 3.11 .venv
uv pip install --python .venv/bin/python -e ".[chatterbox,quality,elevenlabs,ui,dev]"
# Chatterbox loads only when its watermark (resemble-perth) imports: it needs setuptools<81
.venv/bin/python -c "import perth, sys; sys.exit(perth.PerthImplicitWatermarker is None)" \
  || { echo "perth watermark does not load - uv pip install --python .venv/bin/python 'setuptools<81'"; exit 1; }

echo "== .venv-train (piper1-gpl ${PIPER_REF})"
if [ ! -d third_party/piper1-gpl ]; then
  git clone --depth 1 --branch "$PIPER_REF" https://github.com/OHF-Voice/piper1-gpl.git third_party/piper1-gpl
fi
uv venv --allow-existing --python 3.11 .venv-train
uv pip install --python .venv-train/bin/python -e "third_party/piper1-gpl[train]"
# val_mos (UTMOS quality after every epoch) needs torchaudio, which piper1-gpl does not pull in;
# without it training stops after the first epoch (ModelCheckpoint(monitor='val_mos') finds nothing)
uv pip install --python .venv-train/bin/python torchaudio
# exporting to ONNX imports these; piper1-gpl does not pull them in either
uv pip install --python .venv-train/bin/python onnx onnxscript
# the editable install builds neither C extension: monotonic_align (Cython) and espeakbridge
# (scikit-build); tools come from .venv-train, not older ones on PATH (e.g. ~/.local/bin without Cython)
uv pip install --python .venv-train/bin/python scikit-build cmake ninja
(cd third_party/piper1-gpl && export PATH="$ROOT/.venv-train/bin:$PATH" && ./build_monotonic_align.sh \
  && python setup.py build_ext --inplace)
.venv-train/bin/python -c "import piper.espeakbridge, piper.train.vits.monotonic_align, torchaudio" \
  || { echo "piper1-gpl C extensions did not build"; exit 1; }

if [ "${XTTS_ENV:-0}" = "1" ]; then
  echo "== .venv-xtts"
  uv venv --allow-existing --python 3.11 .venv-xtts
  uv pip install --python .venv-xtts/bin/python -e ".[xtts,quality]"
fi

cat <<EOF

Done. Use:
  export PVC_HOME=\$HOME/home-assistant/voices-private          # private data, outside this repository
  export PVC_TRAIN_PYTHON=$ROOT/.venv-train/bin/python
  source $ROOT/.venv/bin/activate
  pvc --help
EOF
