# piper-voice-cloner - the voice editor on the GPU machine (the gpu-studio standard).
#
#   make help        the targets (Polish or English, from $LANG; HELP_LANG=en|pl)
#   make demo        try the editor on made-up voices: only Docker needed (http://localhost:7861, demo / demo)
#   make install     from the Mac: first install on the GPU machine; later `make deploy`
#   make doctor      what is there and what is missing (Docker, Chrome, uv, the machine)
#
# Groups (the gpu-studio standard, section 2): 1. Start and 2. The GPU machine need only Docker Desktop
# (and git, make, ssh, rsync from macOS); Python, uv and Chrome are only for 3. Development.
#
# The GPU machine's address is shared by every studio: ~/.config/gpu-studio/host.mk (GPU_HOST = user@host).
# This application's own values (GPU_DIR, data folders) go to Makefile.local (not in git).

-include $(HOME)/.config/gpu-studio/host.mk
-include Makefile.local
GPU_DIR ?= piper-voice-cloner
DEMO_PORT ?= 7861
DOCS_PORT ?= 8861
DEMO_IMAGE ?= piper-voice-cloner-demo
DOCS_IMAGE ?= piper-voice-cloner-docs
# the docker command checked by need-docker (tests point it at a missing one)
DOCKER ?= docker
# the programmer's Python, fetched by uv (the image on the machine stays on 3.11 for torch)
PYTHON_VERSION ?= 3.12

VENV := .venv
HELP_LANG ?= $(if $(filter pl%,$(LANG)),pl,en)
COMPOSE := docker compose -f docker/compose.yaml
RSYNC_CODE := rsync -az --delete --exclude .git --exclude '.venv*' --exclude backup --exclude __pycache__ \
  --exclude .pytest_cache --exclude .ruff_cache --exclude '*.egg-info' --exclude .cache --exclude site \
  --exclude docker/config --exclude docker/data --exclude docker/.env --exclude Makefile.local \
  --exclude 'docs/changelog*.md'
need-host = @test -n "$(GPU_HOST)" || { echo 'save GPU_HOST in ~/.config/gpu-studio/host.mk (e.g. GPU_HOST = user@192.168.1.21)'; exit 1; }

.DEFAULT_GOAL := help
.PHONY: help demo demo-clean docs docs-serve doctor install deploy login logs status docker-up docker-down \
        docker-logs docker-shell setup demo-local test test-browser test-docker test-all lint format docs-build \
        screenshots icons clean

need-docker = @command -v $(DOCKER) >/dev/null 2>&1 || { echo 'Docker not found: install and start Docker Desktop | Brak Dockera: zainstaluj i uruchom Docker Desktop'; exit 1; }; \
  $(DOCKER) info >/dev/null 2>&1 || { echo 'Docker is not running: start Docker Desktop | Docker nie działa: uruchom Docker Desktop'; exit 1; }

##@ 1. Start | 1. Start


help: ## This list | Ta lista
	@awk -v lang=$(HELP_LANG) 'BEGIN { FS = ":.*## " } \
	  /^##@ / { split(substr($$0, 5), t, " \\| "); printf "\n\033[1m%s\033[0m\n", (lang == "pl" && t[2] != "") ? t[2] : t[1]; next } \
	  /^[a-zA-Z0-9_-]+:.*## / { split($$2, d, " \\| "); printf "  \033[36m%-14s\033[0m %s\n", $$1, (lang == "pl" && d[2] != "") ? d[2] : d[1] }' \
	  $(MAKEFILE_LIST)
	@echo
	@if [ "$(HELP_LANG)" = "pl" ]; then \
	  echo "Maszyna z GPU: $(or $(GPU_HOST),brak - zapisz GPU_HOST w ~/.config/gpu-studio/host.mk):~/$(GPU_DIR)"; \
	  echo "Środowisko programisty: $(VENV) $$(test -x $(VENV)/bin/pvc && echo '- gotowe' || echo '- powstanie przy make setup')"; \
	else \
	  echo "GPU machine: $(or $(GPU_HOST),none - save GPU_HOST in ~/.config/gpu-studio/host.mk):~/$(GPU_DIR)"; \
	  echo "Programmer's environment: $(VENV) $$(test -x $(VENV)/bin/pvc && echo '- ready' || echo '- made by make setup')"; \
	fi

demo: ## Try the editor on made-up voices in Docker (http://localhost:7861, demo / demo) | Wypróbuj edytor na wymyślonych głosach w Dockerze (http://localhost:7861, demo / demo)
	$(need-docker)
	docker build -f docker/Dockerfile --target demo -t $(DEMO_IMAGE) .
	@echo "==> http://localhost:$(DEMO_PORT)  (demo / demo, Ctrl+C stops | zatrzymuje)"
	docker run --rm --init -it -p 127.0.0.1:$(DEMO_PORT):$(DEMO_PORT) $(DEMO_IMAGE) --port $(DEMO_PORT)

demo-clean: ## Remove the demo's container and image | Usuń kontener i obraz demo
	$(need-docker)
	@ids=$$(docker ps -aq --filter ancestor=$(DEMO_IMAGE)); [ -z "$$ids" ] || docker rm -f $$ids
	-docker image rm $(DEMO_IMAGE)

docs: docs-build ## Build the guide in Docker and open it | Zbuduj instrukcję w Dockerze i ją otwórz
	@if [ "$(HELP_LANG)" = "pl" ]; then f=site/pl/index.html; else f=site/index.html; fi; \
	  open $$f 2>/dev/null || xdg-open $$f

docs-serve: ## Preview the guide live in Docker (http://127.0.0.1:8861/piper-voice-cloner/) | Podgląd instrukcji na żywo w Dockerze (http://127.0.0.1:8861/piper-voice-cloner/)
	$(need-docker)
	docker build -q -f docker/Dockerfile --target docs -t $(DOCS_IMAGE) . >/dev/null
	@echo "==> http://127.0.0.1:$(DOCS_PORT)/piper-voice-cloner/  (Ctrl+C stops | zatrzymuje)"
	docker run --rm --init -it -p 127.0.0.1:$(DOCS_PORT):$(DOCS_PORT) --user $$(id -u):$$(id -g) -e HOME=/tmp \
	  -e NO_MKDOCS_2_WARNING=1 -v "$(CURDIR)/docs:/src/docs" -v "$(CURDIR)/mkdocs.yml:/src/mkdocs.yml:ro" \
	  -v "$(CURDIR)/CHANGELOG.md:/src/CHANGELOG.md:ro" -v "$(CURDIR)/dev/docs_site.py:/src/dev/docs_site.py:ro" \
	  $(DOCS_IMAGE) mkdocs serve --dev-addr 0.0.0.0:$(DOCS_PORT)

doctor: ## What is there and what is missing (Docker, Chrome, uv, the machine); installs nothing | Co jest, a czego brak (Docker, Chrome, uv, maszyna); niczego nie instaluje
	@ok() { printf '  \033[32mOK\033[0m     %s\n' "$$1"; }; \
	no() { printf '  \033[31mmissing | brak\033[0m  %s\n         -> %s\n' "$$1" "$$2"; }; \
	if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then ok "Docker $$(docker version -f '{{.Server.Version}}' 2>/dev/null)"; \
	else no "Docker (make demo, docs, docs-serve)" "install and start Docker Desktop | zainstaluj i uruchom Docker Desktop"; fi; \
	if [ -d "/Applications/Google Chrome.app" ] || command -v google-chrome >/dev/null 2>&1; then ok "Google Chrome"; \
	else no "Google Chrome (make test-browser, screenshots)" "https://www.google.com/chrome/"; fi; \
	if command -v uv >/dev/null 2>&1; then ok "$$(uv --version)"; \
	else no "uv (make setup)" "curl -LsSf https://astral.sh/uv/install.sh | sh"; fi; \
	if [ -z "$(GPU_HOST)" ]; then no "GPU_HOST (install, deploy, login, logs, status)" "save GPU_HOST in ~/.config/gpu-studio/host.mk | zapisz GPU_HOST w ~/.config/gpu-studio/host.mk"; \
	elif ssh -o BatchMode=yes -o ConnectTimeout=3 $(GPU_HOST) true 2>/dev/null; then ok "ssh $(GPU_HOST)"; \
	else no "ssh $(GPU_HOST)" "the machine is off or has no SSH key | maszyna wyłączona albo brak klucza SSH (ssh-copy-id $(GPU_HOST))"; fi

##@ 2. The GPU machine | 2. Maszyna z GPU

install: ## First install on GPU_HOST: code, checks, login, start with the machine | Pierwsza instalacja na GPU_HOST: kod, kontrole, login, start z maszyną
	$(need-host)
	$(RSYNC_CODE) ./ $(GPU_HOST):$(GPU_DIR)/
	ssh -t $(GPU_HOST) 'cd $(GPU_DIR) && docker/install-ubuntu.sh'

deploy: ## Every update: send the code to GPU_HOST and rebuild the editor there | Każda aktualizacja: wyślij kod na GPU_HOST i przebuduj tam edytor
	$(need-host)
	$(RSYNC_CODE) ./ $(GPU_HOST):$(GPU_DIR)/
	ssh $(GPU_HOST) 'cd $(GPU_DIR) && test -f docker/config/env || { echo "first time: make install"; exit 1; } && $(COMPOSE) up -d --build'

login: ## The editor's user and password | Użytkownik i hasło edytora
	$(need-host)
	@ssh $(GPU_HOST) 'cd $(GPU_DIR) && docker/install-ubuntu.sh --show-login'

logs: ## The editor's log on GPU_HOST | Log edytora na GPU_HOST
	$(need-host)
	ssh -t $(GPU_HOST) 'cd $(GPU_DIR) && $(COMPOSE) logs -f --tail 200 studio'

status: ## Does the editor answer, the GPU in the container, the version | Czy edytor odpowiada, karta w kontenerze, wersja
	$(need-host)
	@ssh $(GPU_HOST) 'cd $(GPU_DIR) && port=$$(sed -n "s/^PVC_UI_PORT=//p" docker/.env 2>/dev/null); \
	  echo "health:  $$(curl -sf http://127.0.0.1:$${port:-7860}/api/health || echo "no answer")"; \
	  echo "GPU:     $$($(COMPOSE) exec -T studio nvidia-smi --query-gpu=name,memory.used,temperature.gpu --format=csv,noheader 2>&1 | head -1)"; \
	  $(COMPOSE) ps --format "table {{.Service}}\t{{.State}}\t{{.Status}}"'

# on the machine itself (a clone there, without the Mac)
docker-up: ## Build and start the editor and TensorBoard (first time: docker/install-ubuntu.sh) | Zbuduj i uruchom edytor i TensorBoard (za pierwszym razem: docker/install-ubuntu.sh)
	$(COMPOSE) up -d --build

docker-down: ## Stop the editor (data stays) | Zatrzymaj edytor (dane zostają)
	$(COMPOSE) down

docker-logs: ## The editor's log | Log edytora
	$(COMPOSE) logs -f --tail 200 studio

docker-shell: ## A shell in the editor's container | Powłoka w kontenerze edytora
	$(COMPOSE) exec studio bash

##@ 3. Development | 3. Rozwój

# uv fetches the Python itself (no brew); a .venv of another Python version is made again
$(VENV)/bin/pvc: pyproject.toml
	@command -v uv >/dev/null 2>&1 || { echo 'uv not found | brak uv: curl -LsSf https://astral.sh/uv/install.sh | sh'; exit 1; }
	@if ! $(VENV)/bin/python -c 'import sys; sys.exit("%d.%d" % sys.version_info[:2] != "$(PYTHON_VERSION)")' 2>/dev/null; then \
	  echo "==> Python $(PYTHON_VERSION) environment in $(VENV) (uv)"; uv venv -q --clear --python $(PYTHON_VERSION) $(VENV); \
	else echo "==> Updating $(VENV) ($$($(VENV)/bin/python --version))"; fi
	@uv pip install -q --python $(VENV)/bin/python -e '.[editor,elevenlabs,dev,docs]'
	@touch $@

setup: $(VENV)/bin/pvc ## The programmer's environment .venv (uv, Python from PYTHON_VERSION) | Środowisko programisty .venv (uv, Python z PYTHON_VERSION)

demo-local: setup ## The same demo from .venv, without Docker (tests, screenshots) | To samo demo z .venv, bez Dockera (testy, zrzuty)
	$(VENV)/bin/python dev/demo.py --port $(DEMO_PORT) --auth demo:demo

test: setup ## Tests without building images | Testy bez budowy obrazów
	$(VENV)/bin/python -m pytest -q --ignore=tests/browser -m "not docker"

test-browser: setup ## The editor in Google Chrome (Playwright, demo data) | Edytor w Google Chrome (Playwright, dane demo)
	$(VENV)/bin/python -m pytest -q tests/browser

test-docker: setup ## Build and run the demo image: HTTP, login, no container left | Zbuduj i uruchom obraz demo: HTTP, login, żaden kontener nie zostaje
	$(need-docker)
	$(VENV)/bin/python -m pytest -q --ignore=tests/browser -m docker

test-all: lint test test-browser test-docker ## lint + test + test-browser + test-docker | lint + test + test-browser + test-docker

lint: setup ## Ruff checks | Kontrola ruff
	$(VENV)/bin/ruff check . && $(VENV)/bin/ruff format --check .

format: setup ## Format the code | Sformatuj kod
	$(VENV)/bin/ruff check --fix . && $(VENV)/bin/ruff format .

docs-build: ## Build the guide into site/ in Docker (docs-hub uses it) | Zbuduj instrukcję do site/ w Dockerze (korzysta z tego docs-hub)
	$(need-docker)
	docker build -q -f docker/Dockerfile --target docs -t $(DOCS_IMAGE) . >/dev/null
	@id=$$(docker create $(DOCS_IMAGE)) && rm -rf ./site && docker cp -q $$id:/site ./site; s=$$?; docker rm $$id >/dev/null; exit $$s
	@echo "==> site/"

screenshots: setup ## Screenshots for the guide from the demo (PL and EN) | Zrzuty do instrukcji z demo (PL i EN)
	$(VENV)/bin/python dev/screenshots.py

icons: setup ## Bundle the mdi: icons the editor uses (after adding one) | Dołącz ikony mdi: używane przez edytor (po dodaniu nowej)
	$(VENV)/bin/python dev/icons.py

clean: ## Remove .venv*, site/ and caches | Usuń .venv*, site/ i pliki tymczasowe
	find . -name __pycache__ -type d -prune -not -path "./.venv*" -exec rm -rf {} +
	rm -rf ./.venv ./.venv-docs .pytest_cache .ruff_cache build *.egg-info ./site
