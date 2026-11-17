# The voice editor and everything it runs, for the GPU machine (Ubuntu 24.04 + NVIDIA driver 580).
#
#   make install   (from the Mac, first time)   ·   make deploy   (every update)
#   docker/install-ubuntu.sh                     (on the machine itself)
#   make demo      (any computer with Docker: the `demo` stage below, no GPU, no training libraries)
#
# Layers that change least first (the gpu-studio standard): the environments in /opt depend only on
# their package lists, the guide is its own stage, the code is the last layer (a rebuild after a code
# change takes seconds). Every stage ends with a self-test of its imports.
#   /opt/train   OHF-Voice/piper1-gpl training with its own torch/lightning (Python 3.11)
#   /opt/venv    pvc, the editor, Chatterbox, quality checks (Python 3.11: Chatterbox pins torch 2.6)
# The NVIDIA driver and nvidia-smi come from the host (nvidia-container-toolkit); torch brings CUDA.

FROM ubuntu:24.04 AS base
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_INSTALL_DIR=/opt/python \
    UV_CACHE_DIR=/tmp/uv-cache
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl git ffmpeg espeak-ng libsndfile1 build-essential cmake ninja-build \
 && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.9.7 /uv /usr/local/bin/uv
RUN uv python install 3.11

# --- piper1-gpl training environment ------------------------------------------------------------
FROM base AS train
ARG PIPER_REF=v1.8.0
# the torch that runs on the machine (driver 580 = CUDA 13.0); unpinned, pip takes a newer CUDA that does not
ARG TRAIN_TORCH="torch==2.14.1 torchaudio==2.11.1"
WORKDIR /opt/train
RUN git clone --depth 1 --branch "$PIPER_REF" https://github.com/OHF-Voice/piper1-gpl.git piper1-gpl \
 && uv venv --python 3.11 venv \
 && uv pip install --python venv/bin/python -e "piper1-gpl[train]" $TRAIN_TORCH \
 # val_mos (UTMOS after every epoch) needs torchaudio; without it training stops after epoch 1
 && uv pip install --python venv/bin/python $TRAIN_TORCH onnx onnxscript scikit-build cmake ninja tensorboard \
 # the editable install builds neither C extension (monotonic_align, espeakbridge)
 && cd piper1-gpl \
 && PATH="/opt/train/venv/bin:$PATH" ./build_monotonic_align.sh \
 && PATH="/opt/train/venv/bin:$PATH" python setup.py build_ext --inplace \
 && /opt/train/venv/bin/python -c "import piper.espeakbridge, piper.train.vits.monotonic_align, torchaudio" \
 && rm -rf /tmp/uv-cache

# --- the guide (the editor's "?" opens it at /docs/, also without the internet) -----------------
FROM python:3.12-slim AS docs
WORKDIR /src
COPY requirements_docs.txt mkdocs.yml CHANGELOG.md ./
COPY dev/docs_site.py dev/docs_site.py
COPY docs docs
RUN pip install --no-cache-dir -r requirements_docs.txt \
 && NO_MKDOCS_2_WARNING=1 mkdocs build --strict --site-dir /site

# --- the editor's environment (depends only on pyproject.toml) -----------------------------------
FROM train AS deps
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
RUN mkdir -p piper_voice_cloner && touch piper_voice_cloner/__init__.py \
 && uv venv --python 3.11 /opt/venv \
 && uv pip install --python /opt/venv/bin/python -e ".[chatterbox,quality,elevenlabs,editor]" \
 # Chatterbox loads only when its watermark (resemble-perth) imports: it needs setuptools<81
 && /opt/venv/bin/python -c "import perth, sys, fastapi, uvicorn; sys.exit(perth.PerthImplicitWatermarker is None)" \
 && rm -rf /tmp/uv-cache

# --- the code ---------------------------------------------------------------------------------------
FROM deps AS app
COPY --from=docs /site /app/site
COPY piper_voice_cloner ./piper_voice_cloner
RUN uv pip install --python /opt/venv/bin/python --no-deps -e . \
 && /opt/venv/bin/pvc --help >/dev/null \
 && /opt/venv/bin/python -c "import piper_voice_cloner.editor.server" \
 && rm -rf /tmp/uv-cache

ENV PATH="/opt/venv/bin:$PATH" \
    PVC_HOME=/data \
    PVC_TRAIN_PYTHON=/opt/train/venv/bin/python \
    PVC_UI_PORT=7860 \
    PVC_TB_PORT=6006 \
    PVC_DOCS_DIR=/app/site \
    PVC_HA_CONFIG=/config/home_assistant.json \
    PVC_ELEVENLABS_CONFIG=/config/elevenlabs.json \
    PVC_SESSION_SECRET_FILE=/config/session_secret \
    HOME=/home/pvc \
    HF_HOME=/data/cache/huggingface \
    TORCH_HOME=/data/cache/torch \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility
# any user id may run the container (compose: user: ${UID}:${GID}); HOME must be writable
RUN mkdir -p /home/pvc /data /config && chmod -R 0777 /home/pvc /data /config
EXPOSE 7860 6006
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/api/health', timeout=4)"
CMD ["pvc", "--root", "/data", "editor", "--host", "0.0.0.0", "--port", "7860"]

# --- the demo: the editor on made-up voices, without a GPU (`make demo`, linux/arm64 and amd64) ------
# Only the editor and its fake jobs (dev/fake_pvc.py); no torch, no CUDA, no piper1-gpl. Built from the
# small docs stage, so `docker build --target demo` never builds the training environment.
FROM python:3.12-slim AS demo
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
RUN mkdir -p piper_voice_cloner && touch piper_voice_cloner/__init__.py \
 && pip install --no-cache-dir -e ".[editor,elevenlabs]"
COPY --from=docs /site /app/site
COPY piper_voice_cloner ./piper_voice_cloner
COPY dev/demo.py dev/fake_pvc.py dev/tfevents.py ./dev/
RUN python -c "import piper_voice_cloner.editor.server"
ENV PVC_DOCS_DIR=/app/site PYTHONUNBUFFERED=1
EXPOSE 7861
HEALTHCHECK --interval=10s --timeout=4s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7861/api/health', timeout=3)"
ENTRYPOINT ["python", "/app/dev/demo.py", "--host", "0.0.0.0", "--auth", "demo:demo"]
CMD ["--port", "7861"]
