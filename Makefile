# piper-voice-cloner - every step from a short recording to a Piper voice in Home Assistant.
#
#   make help                     the steps in order (Polish or English, from $LANG; HELP_LANG=en|pl)
#   make <target> VOICE=<name>    voice to work on (folder voices/<name> under ROOT)
#
# Targets that need the Python environment create it first, so any target can be the first one.
# On the GPU machine run `make setup-gpu` once (cloning model, quality checks and Piper training).

ROOT ?= $(or $(PVC_HOME),$(HOME)/home-assistant/voices-private)
VOICE ?=
PORT ?= 7860
# first choice for a new .venv; python3.11 and python3.12 are tried next
PYTHON ?= python3.11
UI_LANG ?= $(HELP_LANG)

VENV := .venv
VENV_TRAIN := .venv-train
PVC := $(VENV)/bin/pvc --root "$(ROOT)"
HELP_LANG ?= $(if $(filter pl%,$(LANG)),pl,en)
export PVC_TRAIN_PYTHON ?= $(abspath $(VENV_TRAIN)/bin/python)

.DEFAULT_GOAL := help
.PHONY: screenshots help setup setup-gpu setup-mac doctor init reference corpus audition synthesize filter import \
        train export tensorboard base-prepare base-train base-select remote-configure remote-check \
        remote-status remote-prepare remote-push remote-install remote-pull ui ui-remote service service-remove \
        service-logs test lint format docs clean

need-voice = @test -n "$(VOICE)" || { echo 'usage: make $@ VOICE=<name>   (voices: $(shell ls "$(ROOT)/voices" 2>/dev/null | tr '\n' ' '))'; exit 1; }

##@ Start | Start

help: ## This list | Ta lista
	@awk -v lang=$(HELP_LANG) 'BEGIN { FS = ":.*## " } \
	  /^##@ / { split(substr($$0, 5), t, " \\| "); printf "\n\033[1m%s\033[0m\n", (lang == "pl" && t[2] != "") ? t[2] : t[1]; next } \
	  /^[a-zA-Z0-9_-]+:.*## / { split($$2, d, " \\| "); printf "  \033[36m%-17s\033[0m %s\n", $$1, (lang == "pl" && d[2] != "") ? d[2] : d[1] }' \
	  $(MAKEFILE_LIST)
	@echo
	@if [ "$(HELP_LANG)" = "pl" ]; then \
	  echo "Prywatne dane: ROOT=$(ROOT)   (zmień: make <cel> ROOT=/inna/ścieżka albo PVC_HOME)"; \
	  echo "Środowisko: $(VENV) $$(test -x $(VENV)/bin/pvc && echo '- gotowe' || echo '- powstanie przy pierwszym poleceniu')"; \
	  echo "Trening: $(VENV_TRAIN) $$(test -x $(VENV_TRAIN)/bin/python && echo '- gotowe' || echo '- brak (make setup-gpu na komputerze z GPU)')"; \
	else \
	  echo "Private data: ROOT=$(ROOT)   (change: make <target> ROOT=/other/path or PVC_HOME)"; \
	  echo "Environment: $(VENV) $$(test -x $(VENV)/bin/pvc && echo '- ready' || echo '- created by the first command')"; \
	  echo "Training: $(VENV_TRAIN) $$(test -x $(VENV_TRAIN)/bin/python && echo '- ready' || echo '- missing (make setup-gpu on the GPU machine)')"; \
	fi

##@ 1. Setup | 1. Instalacja

# an existing .venv is only refreshed (its own Python); a new one needs Python 3.11 or 3.12
$(VENV)/bin/pvc: pyproject.toml
	@if [ ! -x $(VENV)/bin/python ]; then \
	  py=$$(for p in $(PYTHON) python3.11 python3.12; do command -v $$p >/dev/null && { echo $$p; break; }; done); \
	  [ -n "$$py" ] || { echo "Python 3.11 or 3.12 not found - macOS: brew install python@3.12, Ubuntu: uv python install 3.11"; exit 1; }; \
	  echo "==> Python environment in $(VENV) ($$py)"; $$py -m venv $(VENV); \
	else echo "==> Updating $(VENV) ($$($(VENV)/bin/python --version))"; fi
	@$(VENV)/bin/pip install -q --upgrade pip
	@$(VENV)/bin/pip install -q -e '.[ui,elevenlabs,dev]'
	@touch $@
	@echo "==> ready: $$($(VENV)/bin/pvc --help >/dev/null && echo pvc)"

setup: $(VENV)/bin/pvc ## Light environment: web UI, import, tests (any computer) | Lekkie środowisko: interfejs, import, testy (dowolny komputer)

setup-gpu: ## Full setup on the GPU machine: Chatterbox, Whisper, piper1-gpl | Pełna instalacja na komputerze z GPU: Chatterbox, Whisper, piper1-gpl
	./scripts/setup.sh

# macOS: generating and checking clips on the Apple GPU (mps); Piper training stays on the GPU machine
setup-mac: $(VENV)/bin/pvc ## macOS (Apple Silicon): Chatterbox on the Apple GPU + quality checks, no training | macOS (Apple Silicon): Chatterbox na karcie Apple + kontrola jakości, bez treningu
	@[ "$$(uname)" = Darwin ] || { echo "macOS only - on Linux with an NVIDIA GPU: make setup-gpu"; exit 1; }
	@missing=""; for tool in ffmpeg espeak-ng; do command -v $$tool >/dev/null || missing="$$missing $$tool"; done; \
	  [ -z "$$missing" ] || { echo "missing:$$missing - install: brew install$$missing"; exit 1; }
	@echo "==> Chatterbox, Whisper, CAM++ and UTMOS in $(VENV) (a few GB, the models download on first use)"
	@$(VENV)/bin/pip install -q -e '.[chatterbox,quality,ui,elevenlabs,dev]'
	@$(VENV)/bin/python -c "import torch; print('==> torch', torch.__version__, '- Apple GPU (mps):', torch.backends.mps.is_available())"
	@$(VENV)/bin/python -c "import perth, sys; sys.exit(perth.PerthImplicitWatermarker is None)" \
	  || { echo "perth watermark does not load (Chatterbox needs it) - $(VENV)/bin/pip install 'setuptools<81'"; exit 1; }

doctor: setup ## Check tools, GPU and folders | Sprawdź narzędzia, kartę i foldery
	@for tool in ffmpeg espeak-ng uv rsync; do \
	  if command -v $$tool >/dev/null; then echo "ok       $$tool"; else echo "MISSING  $$tool"; fi; done
	@if command -v nvidia-smi >/dev/null; then echo "ok       GPU: $$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader)"; \
	  else echo "-        no NVIDIA GPU (fine for the UI and import; cloning and training need one)"; fi
	@if [ -x "$(PVC_TRAIN_PYTHON)" ]; then echo "ok       training: $(PVC_TRAIN_PYTHON)"; else echo "-        training environment missing (make setup-gpu)"; fi
	@if [ -d "$(ROOT)" ]; then echo "ok       data: $(ROOT) ($$(ls "$(ROOT)/voices" 2>/dev/null | wc -l | tr -d ' ') voices)"; \
	  else echo "-        $(ROOT) does not exist yet (make init creates it)"; fi

##@ 2. Voice data | 2. Dane głosu

init: setup ## New voice (VOICE=… PIPER_NAME=pl_PL-… BASE=bazowy-pl|lessac) | Nowy głos (VOICE=… PIPER_NAME=pl_PL-… BASE=…)
	$(need-voice)
	$(PVC) init $(VOICE) $(if $(PIPER_NAME),--piper-name $(PIPER_NAME)) $(if $(BASE),--base $(BASE)) $(if $(BACKEND),--backend $(BACKEND))

reference: setup ## Prepare the recording (FILES="a.m4a b.wav") | Przygotuj nagranie (FILES="a.m4a b.wav")
	$(need-voice)
	@test -n "$(FILES)" || { echo 'usage: make reference VOICE=kuba FILES="~/Downloads/kuba*.m4a"'; exit 1; }
	$(PVC) reference $(VOICE) $(FILES)

corpus: setup ## Select sentences (SOURCES="books.txt lines.txt") | Wybierz zdania (SOURCES="ksiazki.txt kwestie.txt")
	$(need-voice)
	@test -n "$(SOURCES)" || { echo 'usage: make corpus VOICE=kuba SOURCES="books.txt"'; exit 1; }
	$(PVC) corpus $(VOICE) $(foreach s,$(SOURCES),--source $(s))

audition: setup ## Compare cloning settings (writes audition.html) | Porównaj ustawienia klonowania (audition.html)
	$(need-voice)
	$(PVC) audition $(VOICE) --apply-best

synthesize: setup ## Generate clips (LIMIT=50 for a test) | Generuj klipy (LIMIT=50 na próbę)
	$(need-voice)
	$(PVC) synthesize $(VOICE) $(if $(LIMIT),--limit $(LIMIT))

filter: setup ## Check clips and build the dataset | Sprawdź klipy i zbuduj dataset
	$(need-voice)
	$(PVC) filter $(VOICE) $(if $(TARGET),--target $(TARGET))

import: setup ## Clean an old dataset (DIR=… PERSONA=custom_metadata.csv) | Wyczyść stary dataset (DIR=… PERSONA=…)
	$(need-voice)
	@test -n "$(DIR)" || { echo 'usage: make import VOICE=kasia DIR=/old/pl_PL-kasia-medium [PERSONA=…]'; exit 1; }
	$(PVC) import $(VOICE) "$(DIR)" $(if $(PERSONA),--metadata "$(DIR)/metadata.csv" --persona "$(PERSONA)")

##@ 3. Training | 3. Trening

train: setup ## Train / resume (BASE=bazowy-pl|lessac|ckpt:…) | Trenuj / wznów (BASE=bazowy-pl|lessac|ckpt:…)
	$(need-voice)
	$(PVC) train $(VOICE) $(if $(BASE),--base $(BASE))

export: setup ## Export .onnx + .onnx.json (CKPT=… optional) | Eksportuj .onnx + .onnx.json (CKPT=… opcjonalnie)
	$(need-voice)
	$(PVC) export $(VOICE) $(if $(CKPT),--checkpoint "$(CKPT)")

tensorboard: ## Training charts and audio samples (http://<machine>:6006) | Wykresy i próbki audio treningu (http://<komputer>:6006)
	$(need-voice)
	$(VENV_TRAIN)/bin/tensorboard --logdir "$(ROOT)/voices/$(VOICE)/train/lightning_logs" --bind_all

base-prepare: setup ## Own base: clean a large dataset (DIR=…) | Własna baza: wyczyść duży zbiór (DIR=…)
	@test -n "$(DIR)" || { echo 'usage: make base-prepare DIR=/data/mc_speech [AUDIO_DIR=…]'; exit 1; }
	$(PVC) base prepare "$(DIR)" $(if $(AUDIO_DIR),--audio-dir "$(AUDIO_DIR)")

base-train: setup ## Own base: train from scratch (EPOCHS=3000 QUALITY=medium|high BATCH=…) | Własna baza: trening od zera (EPOCHS=3000 QUALITY=medium|high BATCH=…)
	$(PVC) base train --max-epochs $(or $(EPOCHS),3000) --quality $(or $(QUALITY),medium) $(if $(BATCH),--batch-size $(BATCH))

base-score: setup ## Own base: rate the recordings with UTMOS (SAMPLE=300, 0 = all) | Własna baza: oceń nagrania UTMOS (SAMPLE=300, 0 = wszystkie)
	$(PVC) base score --sample $(or $(SAMPLE),300)

base-select: setup ## Own base: use this checkpoint as bazowy-pl (CKPT=…) | Własna baza: użyj checkpointu jako bazowy-pl (CKPT=…)
	@test -n "$(CKPT)" || { echo 'usage: make base-select CKPT=…/epoch=…-val_mos=….ckpt'; exit 1; }
	$(PVC) base select "$(CKPT)"

##@ 4. GPU server over SSH | 4. Serwer z GPU przez SSH

remote-configure: setup ## Save the server (HOST=ubuntu.local SSH_USER=… KEY=…) | Zapisz serwer (HOST=ubuntu.local SSH_USER=… KEY=…)
	@test -n "$(HOST)" || { echo 'usage: make remote-configure HOST=ubuntu.local SSH_USER=me [KEY=~/.ssh/id_ed25519] [REMOTE_DIR=…]'; exit 1; }
	$(PVC) remote configure $(HOST) $(if $(SSH_USER),--user $(SSH_USER)) $(if $(KEY),--key $(KEY)) $(if $(REMOTE_DIR),--remote-dir $(REMOTE_DIR))

remote-status: setup ## Checklist: what the machine has, what is to do | Lista kontrolna: co maszyna ma, co zostało do zrobienia
	$(PVC) remote status

remote-prepare: setup ## Do everything possible: packages, uv, push, install | Zrób wszystko, co się da: pakiety, uv, wysyłka, instalacja
	$(PVC) remote prepare

remote-check: setup ## Check the connection, GPU and tools | Sprawdź połączenie, kartę i narzędzia
	$(PVC) remote check

remote-push: setup ## Send the code and the voice data (rsync) | Wyślij kod i dane głosów (rsync)
	$(PVC) remote push

remote-install: setup ## Install / update there (environments + UI service) | Zainstaluj / zaktualizuj tam (środowiska + usługa panelu)
	$(PVC) remote install

remote-pull: setup ## Bring the exported voices back | Pobierz wyeksportowane głosy
	$(PVC) remote pull

##@ 5. Web interface | 5. Interfejs w przeglądarce

ui: setup ## Web UI on this computer (http://localhost:7860) | Interfejs na tym komputerze (http://localhost:7860)
	$(PVC) ui --host 127.0.0.1 --port $(PORT) --lang $(UI_LANG)

ui-remote: setup ## Web UI reachable from the network (set PVC_UI_AUTH=user:password) | Interfejs dostępny z sieci (ustaw PVC_UI_AUTH=uzytkownik:haslo)
	$(PVC) ui --host 0.0.0.0 --port $(PORT) --lang $(UI_LANG)

service: ## Install the UI as a service that starts at boot (Linux) | Zainstaluj interfejs jako usługę startującą z systemem (Linux)
	./scripts/install-service.sh

service-remove: ## Remove the service (settings stay) | Usuń usługę (ustawienia zostają)
	./scripts/install-service.sh --remove

service-logs: ## Follow the service logs | Podgląd logów usługi
	journalctl --user -u piper-voice-cloner -f

##@ 6. Development | 6. Rozwój

test: setup ## Tests | Testy
	$(VENV)/bin/python -m pytest -q

lint: setup ## Ruff checks | Kontrola ruff
	$(VENV)/bin/ruff check . && $(VENV)/bin/ruff format --check .

format: setup ## Format the code | Sformatuj kod
	$(VENV)/bin/ruff format . && $(VENV)/bin/ruff check --fix .

screenshots: setup ## UI screenshots for the README (example voices, Google Chrome) | Zrzuty interfejsu do README (przykładowe głosy, Google Chrome)
	$(VENV)/bin/pip install -q -e '.[ui,docs]'
	$(VENV)/bin/python scripts/screenshots.py

docs: setup ## Build the HTML guides from Markdown and open one | Zbuduj instrukcje HTML z Markdown i otwórz
	$(VENV)/bin/python -m piper_voice_cloner.webui.guide
	@if [ "$(HELP_LANG)" = "pl" ]; then f=docs/pl/instrukcja.html; else f=docs/en/guide.html; fi; \
	  open $$f 2>/dev/null || xdg-open $$f

clean: ## Remove caches (keeps environments and voices) | Usuń pliki tymczasowe (środowiska i głosy zostają)
	find . -name __pycache__ -type d -prune -not -path "./.venv*" -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache build *.egg-info
