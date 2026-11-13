# Changelog

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
