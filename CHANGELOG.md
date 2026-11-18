# Changelog

## 0.2.1 (2026-11-18)

The first run on the real GPU machine: install, deploy, a training, the export and Home Assistant were
checked there, and what failed is fixed. Plus a step-by-step guide with pictures of the real editor.

Added:
- The guide has a "Step by step" section in Polish and English: first steps (every part of the screen),
  a new voice, rating recordings, training a voice, training the base voice and the export to Home
  Assistant, with pictures of the real editor (`dev/screenshots_machine.py`: never starts a job and
  replaces the Home Assistant address and room names before each picture).
- `make stop`: stops the editor and TensorBoard on the machine; they stay off after a reboot until
  `make deploy`.
- `make uninstall`: removes the containers, the image, the login, the settings and the code folder from
  the machine after typing `yes` (`CONFIRM=yes`); the voices stay. Both also as
  `docker/install-ubuntu.sh --stop` / `--uninstall`.

Changed:
- Training: "Start over" next to "Resume training" trains the voice again from the base chosen in
  "Start from" (it asks first; the earlier checkpoints stay). A hint says that "Resume training" ignores
  "Start from".
- The training time reads as a duration ("16–21 h", "25–40 min", "3.1–4.2 days"), not like a clock.
- Job history: a Result column (finished, failed with its code, stopped, running) and how long each
  job took; the runner keeps `<job>.exit` next to the log. A training queue lists its voices.
- Audition is an optional step: it counts in "6/6" only once done and is never the next step.
- The base's checkpoint list shows the size, epoch and val_mos, like a voice's export list.
- The Sentences hint no longer says "more than needed" when "Generate ×" is 1.
- The tree's buttons are "Fold" / "Unfold" (the full text on hover), so they fit the column; fields in a
  row keep their own height.
- ⚙ in the top bar opens a box under it with the theme and the language (it opened a view in the
  middle); Esc, a click beside it or ⚙ again close it, and the ☰ menu closes the same way.

Fixed:
- The "?" window of Training and Voice settings closed by itself when it was opened before the step's
  data came (the head was drawn twice).
- Starting a voice over kept the earlier run's start epoch in run.json, so the progress bar was wrong.
- An older imported voice showed "Cloning" as its way in Voice settings (the tree said "Own
  recordings"), and saving the form could keep it. Opening the settings writes `workflow: import` into
  voice.yaml once; the previous file stays in History.
- On the machine no job did anything: the editor runs them as `python -m piper_voice_cloner.cli`,
  which lacked its `__main__` block, so each one ended in a moment with success and an empty log.
- Training from the lessac base stopped at once with `Weights only load failed … pathlib.PosixPath`:
  Lightning 2.6 opens checkpoints with `weights_only=True`, and the downloaded lessac checkpoint keeps
  paths in its settings. Before training, the starting checkpoint is turned into one that opens (once,
  in place).
- `make install` and `make deploy` built the demo image on the machine (the last stage of the
  Dockerfile): the editor did not answer on 7860 and TensorBoard restarted forever. `compose.yaml`
  builds the `app` stage.
- The installer checks the NVIDIA driver: it must answer and be 580 or newer (the torch of the image);
  before, an old driver showed only when training started.
- The installer's hint for missing Docker access no longer breaks when `$USER` is not set.

Tests:
- The installer runs on a pretend machine: no driver, driver not loaded, old driver, no Docker, no
  compose, no access, no NVIDIA toolkit, a failed image build, a second run, stop and uninstall.
- A test runs the real CLI the way jobs do (not the fake one); a test with real torch checks that an
  old checkpoint opens after the change.

## 0.2.0 (2026-11-17)

The voice editor replaces the Gradio panel. It runs only on the GPU machine, in Docker, and starts with
it; it follows the gpu-studio standard shared with the wake word studio and the Assist Router trainer.

Added:
- The voice editor (`pvc editor`): the look of the Home Dashboard and Assist Router editors (tree,
  search, columns, light/dark, PL/EN, icons offline), a login with one password (30-day session, five
  wrong passwords wait a minute), the guide built in at `/docs/`.
- Two ways to a voice, chosen when it is made: cloning (recording or ElevenLabs → sentences → audition
  → generating → filter) or own recordings (import from the import folder, a ZIP or a path); then
  training and export. The tree shows only the steps of the way, with their state.
- Every step runs as a job, also preparing the recording, choosing the sentences and using another
  voice's sentences (they held the old panel up). Job history with every log.
- Training says exactly what resuming will do (finish the plan or train more epochs) and shows the
  chart (zoom, pinned epoch, how to read it), listening to epochs and the checkpoints.
- Voice settings as a form or YAML: a draft kept on the machine, undo/redo, Save with the changed lines,
  a note and a conflict check, 30 earlier versions. Changing a field changes exactly one line.
- Top bar: menu (guide, who is logged in, log out), job chip, machine chip (GPU, temperature, memory,
  plug power) with power-off, the countdown before powering off with Cancel.
- Powering off when a job ends goes through Home Assistant after 120 s that can be cancelled; never
  after Stop (also when Stop came during Python's start), waits for a job running beside, a job started
  meanwhile or a restart of the editor drops it.
- Docker (`docker/`): Dockerfile with the environments in `/opt`, the guide built in its own stage and
  the code as the last layer; torch pinned for driver 580; `docker/compose.yaml` (`studio` +
  `tensorboard`); `docker/install-ubuntu.sh` (checks, login, the old panel's services off,
  `--show-login`, `--remove`); `GET /api/health`.
- Try it on a Mac with only Docker Desktop: `make demo` builds a small demo image (no torch, no CUDA;
  arm64 and amd64) and runs it at http://localhost:7861 (`demo` / `demo`); Ctrl+C removes the container,
  `make demo-clean` the image. The demo from `.venv` is now `make demo-local` and removes its temporary
  folder on Ctrl+C. README and guide: "Try it on a Mac".
- `make help` in the three groups of the gpu-studio standard. 1. Start (`help`, `demo`, `demo-clean`,
  `docs`, `docs-serve`, `doctor`) and 2. The GPU machine (`install`, `deploy`, `login`, `logs`, `status`,
  `docker-*`) need only Docker Desktop. 3. Development (`setup`, `demo-local`, `test`, `test-browser`,
  `test-docker`, `test-all`, `lint`, `format`, `docs-build`, `screenshots`, `icons`, `clean`). The GPU
  machine shared in `~/.config/gpu-studio/host.mk`.
- The guide builds in the `docs` stage of the Dockerfile: `make docs` / `docs-build` copy `site/` out of
  it, `make docs-serve` previews it live at http://127.0.0.1:8861/piper-voice-cloner/ (no `.venv-docs`).
- `make doctor` says what is there and what is missing (Docker, Chrome, uv, `GPU_HOST` and SSH) and
  installs nothing. `make setup` makes `.venv` with uv (`PYTHON_VERSION = 3.12`, uv fetches it).
- `make test` never builds images; `make test-docker` (marker `docker`) builds and runs the demo image;
  `make test-all` = lint + test + test-browser + test-docker. CI tests 3.11 (the image) and 3.12.
- The guide: MkDocs Material site in Polish and English with screenshots (installation, the screen,
  both ways, training well with every parameter, the base model, export to Home Assistant, law, FAQ),
  also on GitHub Pages.
- `voice.yaml` has `workflow: clone | import`.

Removed:
- The Gradio panel (`pvc ui`), driving the GPU machine from the Mac over SSH (`pvc remote …`, the
  machine checklist), the systemd services (`scripts/install-service.sh`), `scripts/setup.sh`,
  `make setup-mac` and the old HTML guides. The runner no longer powers anything off.

Fixes:
- Tests can never power a computer off and never reach a computer other than this one.

## 0.1.0 (2026-11-13)

Added:
- Training progress reads `557 / 1000 epochs · model epoch 1670 · step 17/112`: the voice's epochs
  first, then the model's counter used by checkpoints and Listen.
- Powering the machine off can be switched on or off while a job runs (panel: under the Stage
  card); a training queue is not interrupted.
- Base model size `high` (`pvc base train --quality high`, panel: Model size): the decoder of the
  original Piper high voices, trained in `bases/pl-scratch-high` from the same recordings. Voices
  fine-tuned from a base keep its size; the export writes `…-high.onnx` and `audio.quality`.
- Rating the base recordings with UTMOS (`pvc base score`, panel: Rate recordings): median, spread,
  worst/best recordings to listen to - the val_mos ceiling of the base. Runs on the CPU next to a
  training (second job slot).
- Compare base models: mean val_mos/val_mel of the last 10 common epochs and the best values per
  size, and a model switch in the base listening block.
- The chosen base is stored as `bases/pl-scratch.ckpt` (the size is read from the checkpoint).

- Generating on a Mac (Apple Silicon): Chatterbox and UTMOS use the Apple GPU (`mps`), Whisper
  runs on the CPU in `int8`; `make setup-mac` installs the cloning side (training stays on Linux).
- Generation speed: `pvc synthesize` and the panel show clips, time, seconds per clip and the real
  time factor (`raw/timing.json`).
- `pvc reference` and the panel warn when the recording is shorter than 20 s or gives one prompt
  only: cloning works, 30-60 s of varied speech gives a steadier voice and similarity threshold.
- A voice from ElevenLabs: the key is saved once in Settings; the Generate step chooses the cloning
  model, lists the account voices and credits, and shows what is left to generate;
  `pvc elevenlabs voices|pick`. No recording or GPU needed.
- A new voice asks only for its names: the cloning model is chosen in Generate, the training start
  in Train.
- Settings rename a voice and its Piper file.
- Training queue: voices train one after another (`pvc train-queue`, panel in the Train step).
- Power the GPU machine off when training ends (panel checkbox on Linux; not after Stop).
- Export a base checkpoint as a voice: `pvc base export`, panel button in the base section.
- The panel opens the voice worked on last (`jobs/last_voice.txt`), also after a restart.
- An imported voice keeps its model and sentences: new clips belong in a new voice.
- A fixed sentence set: `pvc sentences <voice> <source>` and the panel read exactly the sentences of
  an imported voice, with the same clip ids in every voice.
- ElevenLabs requests are retried when the service is busy; a wrong key, no credits or an unknown
  voice stop the run. Clips of two models or two ElevenLabs voices are no longer mixed in `raw/`.

Fixes:
- The tests no longer power the computer off: their background jobs ran the real
  `sudo -n /usr/sbin/poweroff` (a CI runner with sudo shut down mid-run). The command can be
  replaced with `PVC_POWEROFF_COMMAND`; the tests set it to `true`.
- Changing the poweroff wish while the runner writes the job state is no longer lost: both
  update the state file under a lock.
- The filter no longer empties `dataset/` of a voice without generated clips (imported voices).
- Listening to the training keeps the samples of the 5 epochs with the best `val_mos` (their
  checkpoints are kept too); before, the best epoch could be thinned out and not heard. The
  monitor reads the training logs once more after the update, so the dropped samples come back.
- Training runs with `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` (unless set): a rare
  batch of long clips no longer runs out of GPU memory because of a fragmented cache.
- Resuming a stopped training starts from the newest checkpoint of any kind: piper does not refresh
  `last.ckpt` after every epoch, so a newer best-`val_mos`/`val_mel` checkpoint saves repeated epochs.
- The login page (`PVC_UI_AUTH`) has the panel's look: one card with the logo in the middle of
  the page, light and dark, instead of Gradio's bare form on a white block.

- Chatterbox no longer cuts clips after a few words: chatterbox-tts 0.1.7 ends the speech on any
  two equal speech tokens in a row, which low voices hit almost every time (`too_fast_or_cut` for
  most clips); the check now runs only after the whole text is spoken.
- The `chatterbox` extra pins `setuptools<81`: the Perth watermark needs `pkg_resources`, without
  it the model failed to start (`'NoneType' object is not callable`); the setup checks it.

- Training again after a finished run no longer fails with `You restored a checkpoint with
  current_epoch=…, but you have set Trainer(max_epochs=…)`: once the planned epochs are done, the
  epochs count on top of the checkpoint ("800 more").
- Every checkpoint can be heard: listening to the training keeps the samples of every epoch with a
  checkpoint file and marks them `💾 checkpoint` (before, e.g. `epoch=1273-val_mel=….ckpt` had no
  samples: neither every 10th nor among the best by `val_mos`); `last.ckpt` shows its run
  (`version_1/last.ckpt`).
- Download the training samples (panel: **⬇ Download samples (ZIP)**, `pvc base samples`,
  `pvc samples <voice>`): every kept epoch in one ZIP with an `index.html` (players, sorting by
  val_mos/val_mel, only epochs with a checkpoint), to pick the base epoch by ear at leisure.
- The job log has **Enlarge** (a big window that follows the job) and **Copy** (also over plain
  http on the LAN, where the browser has no clipboard API); it keeps the last 120 lines, enough for
  a whole Python traceback.

First version:
- `pvc` CLI covering every step: init, reference, corpus, audition, synthesize, filter, import, train,
  export, plus `base prepare/train/select`.
- Backends: Chatterbox Multilingual (default), XTTS-v2, ElevenLabs.
- Plain-text rules for training sentences, phoneme/diphone coverage selection.
- Quality filter: Whisper CER, CAM++ similarity (calibrated threshold), UTMOS, length checks.
- Training via piper1-gpl from `bazowy-pl`, `lessac` or any checkpoint; epoch budget on top of
  the starting checkpoint; automatic resume.
- Polish language pack with bundled child-friendly sentences.
- Web UI (`pvc ui`, EN/PL): clickable step bar with progress, live job card with progress bar and
  GPU, "?" explanations for every step, systemd user service for the GPU machine.
- GPU server over SSH (`pvc remote configure/check/push/install/pull`, Tools tab, `make remote-*`):
  rsync of code and data, remote install, bringing exported voices back.
- Makefile with a bilingual `make help`.
- Training progress over the whole run (epochs done of planned) with the estimated time left.
- Own icon: a white voice wave with its fainter copy (the cloned voice) on an amber → coral circle
  (favicon, 32 px PNG, 180 px apple-touch-icon, the logo in the top bar) - no longer the purple
  square of the wake word panel.
- Home Assistant connection (⚒ Tools → Home Assistant): address + long-lived admin token in
  `~/.config/piper-voice-cloner/home_assistant.json` (mode 600, `PVC_HA_URL`/`PVC_HA_TOKEN`
  override it), the token never sent back to the page; plain-word 401/403/404 errors; the
  `homeassistant.local` lookup done once, IPv4 first (macOS waited 5 s on every request).
- GPU machine power, the same as the wake word panel: the machine's switch, the plug's power
  sensor and the off threshold (suggestions from Home Assistant); a button in the top bar
  (off / starting / on · W / shutting down / checking… / no reading from HA) switches it through
  `switch.turn_on/turn_off` after a confirmation and never switches off while a job runs on the
  machine. Example package `docs/home-assistant/maszyna_gpu.yaml`.
- The status shows a job running on the GPU machine (read over SSH). The page never waits for the
  machine nor for Home Assistant: the last known state at once ("Checking the machine…" until the
  first answer), both asked in a background thread, a machine that is off costs a 1.5 s port check
  instead of the SSH timeout, unexpected failures are shown (never "checking" for ever).
- Default data folder `~/home-assistant/voices-private`.
- The own Polish base is called `bazowy-pl` (old `scratch-pl` in voice.yaml still works); it can be chosen only once it exists, otherwise the panel offers to create it.
- Training chart below the log (val_mos, val_mel, train_mel per epoch), full screen on click with zoom by dragging, epoch picking and the meaning of the values.
- Listen to the training in the panel (samples and quality per epoch, read from the event files) and a TensorBoard service on the machine with a link in the panel.
- `torchaudio` in the training environment: without it piper stops after the first epoch (no `val_mos`).
- Machine checklist and **Prepare machine** (`pvc remote status|prepare`): the panel checks the GPU machine and installs what is missing by itself.
- A token Home Assistant rejects (401) is sent once only: every 401 is a failed login for HA's ip_ban,
  so the UI stops asking HA (machine state, suggestions, switching) and says “Machine: HA token rejected”;
  **Save connection** checks it again.
- Questions (switching the GPU machine, removing the Home Assistant connection) open the panel's own window instead of the browser's `confirm()`.
