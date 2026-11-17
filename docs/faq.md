# FAQ and troubleshooting

Every error met so far, with its exact message, the cause and the fix. The job's log is on the right
(<span class="ui">Enlarge</span>, <span class="ui">Copy</span>); older logs in <span class="ui">Job history</span>.

## Docker and the machine

### `could not select device driver "nvidia" with capabilities: [[gpu]]`

Docker does not see the card: `nvidia-container-toolkit` is missing or not set up for Docker. Do step 1
of the [installation](installation.md) (`nvidia-ctk runtime configure`, restart Docker). Check:
`docker run --rm --gpus all ubuntu nvidia-smi`.

### The GPU card says "no NVIDIA card"

The container runs without the GPU (e.g. a hand-made `docker run` without `--gpus`). Start the editor
with `make deploy` or `make docker-up` – compose reserves the card.

### `env file …/docker/config/env not found`

The editor is not installed yet (no password file): `make install` from the Mac or
`docker/install-ubuntu.sh` on the machine; later `make deploy`.

### Forgot the editor's password

`make login` on the Mac or `docker/install-ubuntu.sh --show-login` on the machine. It is in
`docker/config/env` (`PVC_UI_AUTH=admin:…`); put a new one there and
`docker compose -f docker/compose.yaml restart` – every browser is logged out.

### "Too many wrong passwords: wait a minute."

After 5 wrong passwords from one address the editor takes no more for a minute. Wait; `make login`
shows the password.

### `Permission denied` writing to `/data`

The data folder belongs to another user than the container. Set `UID`/`GID` in `docker/.env` to yours
(`id -u`, `id -g`) or fix the owner: `sudo chown -R $USER: <data folder>`; then `make deploy`.

### A job shows "Interrupted (the editor was restarted)"

The container restarted during the job (update, power off, crash), so the job's process is gone. Start
it again: a training resumes from its last checkpoint, generating skips finished clips.

### The editor does not answer after switching the machine on

Docker starts it some tens of seconds after boot. If not: `make status` and `make logs`;
and that Docker starts with the system (`sudo systemctl enable docker`).

## Training

### Resuming trains only a few epochs

The earlier plan was not finished and resuming only finishes it (see [Resuming](training.md#resume) –
the editor says so above the button). Enter more epochs.

### `torch.OutOfMemoryError: CUDA out of memory`

The card ran out of memory: a rare batch of long clips (15–20 s) can pass 24 GB, sometimes after hundreds
of epochs. Nothing is lost: start the training again – it resumes from the last checkpoint. If it comes
back, lower the **Batch** in <span class="ui">Voice settings</span> (e.g. 24) or at the base. Make sure
nothing else (Ollama…) shares the card.

### `You restored a checkpoint with current_epoch=…, but you have set Trainer(max_epochs=…)`

Older versions counted epochs from the first run's start. The editor counts them from the last
checkpoint once the plan was done (log: `The planned … epochs are done …; training … more`). Start
the training again.

### `ModelCheckpoint(monitor='val_mos') could not find the monitored key`

The training environment lacks `torchaudio`. The Docker image installs it – this means an old image:
update the editor (`git pull && make docker-up`).

### The finished voice hisses or is choppy

Data, not training: see [The data decides](training.md#data) – noise in the pauses, cut-off clips,
mixed rooms.

## Cloning and ElevenLabs

### The filter rejects almost everything as `too_fast_or_cut`

Chatterbox cut clips after a few words (log: `forcing EOS token`). The editor checks repetition only after
the whole text, so this should not happen any more; delete clips made by an older version (the voice's
`raw/`) and generate again.

### `TypeError: 'NoneType' object is not callable` (`perth.PerthImplicitWatermarker()`)

Chatterbox's watermark did not load (new `setuptools` lacks `pkg_resources`). The image pins
`setuptools<81` and checks it at build time – an old image: update the editor.

### `Stopped: HTTP 401: …` (`quota_exceeded`, `invalid_api_key`)

A wrong ElevenLabs key or no credits (the answer says which). Save a new key in
<span class="ui">Settings</span> → <span class="ui">ElevenLabs</span> or buy credits, then generate
again – finished clips stay.

### `HTTP 401: … missing_permissions` at <span class="ui">Load voices</span>

A restricted key without access to voices: allow it in ElevenLabs or make a new key. Without `user_read`
alone the voices still load, only without credits.

### `Stopped: raw/ holds clips of another voice (…)`

`raw/` holds clips of another model or another ElevenLabs voice. Make a new voice or move `raw/` out of
the voice's folder.

### `raw/ already holds … clips of other sentences` at <span class="ui">Use this set</span>

The voice already has clips of other sentences and the filter would mix them. Make a new voice.

### `'…' is an imported voice: create a new voice to generate clips`

An imported voice is a finished set of recordings; it makes no new clips. Make a new voice (way A) – it
can use the sentences of the imported one as its **Sentence set**.

## Home Assistant

### "Home Assistant rejected the token – save a new one"

Home Assistant answered 401 (wrong, expired or deleted token). Each such answer is a failed login for HA
and with `ip_ban` a few of them block the address – so the editor stops asking HA after the first one.
Paste a new token and <span class="ui">Save the connection</span>.

### `Home Assistant 403: the token belongs to a user who is not an administrator`

Switching the machine needs an admin: make the token on an admin account.

### `this does not look like a Home Assistant long-lived token`

The pasted token has spaces, quotes or is cut. Copy it again whole; the address as `http://<host>:8123`,
nothing after the port.

### `A job is running (…): stop it first or tick “Power the machine off when it ends”`

<span class="ui">Power off the machine</span> never cuts a running job. Stop it, or tick
<span class="ui">Power the machine off when it ends</span> on the job card.

### The machine did not power off after the training

The job's log says `Powering off failed: …` – usually no connection or switch in
<span class="ui">Home Assistant and machine</span>, or a rejected token. After <span class="ui">Stop</span>
it never powers off, on purpose.

## make on the Mac {#make}

### `Docker not found: install and start Docker Desktop` / `Docker is not running: start Docker Desktop`

`make demo`, `make docs`, `make docs-serve` and `make docs-build` run in Docker. Install Docker Desktop,
start it (the whale in the menu bar stops moving) and run the command again. `make doctor` shows what is
there and what is missing.

### `uv not found | brak uv: curl -LsSf https://astral.sh/uv/install.sh | sh`

Only the programmer's commands (`make setup`, `test`, `test-browser`, `lint`, `screenshots`) need uv.
Install it with the command from the message; uv fetches the Python itself (`PYTHON_VERSION` in the
`Makefile`), no brew needed. An old `.venv` of another Python version is made again.

### `make doctor`: `missing | brak  ssh user@host`

The machine is off or your SSH key is not on it. Switch the machine on in Home Assistant, or
`ssh-copy-id user@host` once. The demo and the guide do not need the machine.
