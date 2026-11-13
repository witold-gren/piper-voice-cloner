"""UI texts. Every key must exist in every language (checked by tests)."""

from __future__ import annotations

TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "title": "Piper Voice Cloner",
        "guide": "Guide",
        "subtitle": "From a short recording to your own Piper voice",
        "stage": "Stage",
        "stage_idle": "Nothing running",
        "elapsed": "Elapsed",
        "stage_last": "Last job",
        "elapsed_took": "Took",
        "epochs": "epochs",
        "train_position": "model epoch {epoch} · step {step}/{steps}",
        "time_left": "about {time} left",
        "result_ok": "finished",
        "result_failed": "failed, see the log",
        "result_stopped": "stopped",
        "gpu": "GPU",
        "no_gpu": "no NVIDIA card",
        "utilization": "Load",
        "memory": "Memory",
        "temperature": "Temperature",
        "power": "Power",
        "kind_reference": "Recording",
        "kind_audition": "Audition",
        "kind_synthesize": "Generating clips",
        "kind_filter": "Filtering",
        "kind_import": "Import",
        "kind_train": "Training",
        "kind_train-queue": "Training queue",
        "kind_export": "Export",
        "kind_base-prepare": "Base: preparing data",
        "kind_base-train": "Base: training",
        "kind_base-select": "Base: selecting",
        "kind_base-score": "Base: rating recordings",
        "kind_remote-check": "Server: connection check",
        "kind_remote-push": "Server: sending code and data",
        "kind_remote-install": "Server: installing",
        "kind_remote-pull": "Server: bringing voices back",
        "intro": (
            "Turn a short recording into your own Piper voice. Go through the tabs from left to right. "
            "Long steps (generating, filtering, training) run in the background: you can close the "
            "browser and come back. One job runs at a time."
        ),
        "voice": "Voice",
        "refresh": "Refresh",
        "new_voice": "New voice",
        "new_voice_help": (
            "Name: lowercase letters, digits and `_` (e.g. `kuba_bajka`); `Kuba Bajka` becomes `kuba_bajka` by itself. "
            "The Piper file name is optional, "
            "e.g. `pl_PL-kuba_bajka`; by default `<locale>-<name>`."
        ),
        "name": "Name",
        "piper_name": "Piper file name (optional)",
        "backend": "Cloning model",
        "base": "Training start",
        "create": "Create",
        "created": "Created voice **{name}**.",
        "no_voice": "Create or choose a voice first.",
        "progress": "Progress",
        "step_reference": "Recording",
        "step_corpus": "Sentences",
        "step_audition": "Audition",
        "step_synthesize": "Generate",
        "step_filter": "Filter",
        "step_train": "Training",
        "step_export": "Export",
        "job": "Background job",
        "job_none": "No job has been started yet.",
        "job_running": "**{kind}**{voice} is running…",
        "job_ok": "**{kind}**{voice} finished.",
        "server_answers": "**Server** answers over SSH again.",
        "job_failed": "**{kind}**{voice} failed (exit code {code}). See the log and the FAQ in the guide.",
        "job_stopped": "**{kind}**{voice} was stopped. Start it again to continue.",
        "job_busy": "{job} is still running. Wait until it ends (the Progress card) or stop it, then click again.",
        "job_started": "Started **{kind}**. Progress is shown in the panel on the right.",
        "stop": "Stop job",
        "stopped": "Stop requested.",
        "log": "Log (last lines)",
        "log_expand": "Enlarge",
        "log_copy": "Copy",
        "log_copied": "Copied",
        "log_copy_failed": "Could not copy - select the text in the big window",
        "log_close": "Close",
        "tab_reference": "1. Recording",
        "reference_help": (
            "Upload 10–60 seconds of **clean** speech of the target voice: no music, no TV in the "
            "background, no other people. Any format (wav, mp3, m4a). Natural, varied speech works "
            "better than reading a list. The recordings are trimmed, leveled and cut into 3–12 s "
            "prompts; the similarity threshold for the filter is calibrated from them."
        ),
        "reference_files": "Recordings",
        "reference_embed": "Compute speaker embedding (recommended)",
        "prepare": "Prepare recording",
        "reference_done": "Reference: {seconds} s of speech, {prompts} prompts. Similarity threshold: {threshold}.",
        "reference_short": "**Short recording** ({seconds} s, {prompts} prompt(s)): cloning works, but 30-60 s of varied speech gives a steadier voice and a surer similarity threshold.",
        "reference_clips": "Prepared prompts",
        "tab_corpus": "2. Sentences",
        "corpus_help": (
            "Sentences the cloning model will read. Upload text files (one sentence per line, or "
            "`id<TAB>text`). Only **plain text** is used: lines with digits, times, dates, list numbering, "
            "symbols or abbreviations are rejected, not rewritten; numbers are read by the runtime text "
            "normalizer. The selection covers all sounds evenly."
        ),
        "corpus_files": "Sentence files",
        "corpus_bundled": "Add the language pack's sentences (child-friendly lines)",
        "corpus_size": "Number of sentences (0 = target × overgenerate)",
        "build": "Select sentences",
        "corpus_done": "Selected {count} sentences.",
        "corpus_preview": "First sentences",
        "tab_audition": "3. Audition",
        "audition_help": (
            "Tries several settings of the cloning model on a few sentences. Listen and pick the "
            "combination that sounds most like the original; the score (similarity − 2 × CER + 0.05 × MOS) "
            "is only a hint. If nothing sounds right, improve the recording before generating thousands of clips."
        ),
        "audition_count": "Sentences per combination",
        "audition_run": "Run audition",
        "audition_table": "Results (best first)",
        "audition_pick": "Combination to listen to",
        "audition_apply": "Use these settings",
        "audition_applied": "Saved settings: {options}",
        "tab_synthesize": "4. Generate",
        "synthesize_help": (
            "Reads every selected sentence in the cloned voice. Takes a while (thousands of clips); "
            "you can stop and start again, finished clips are kept. Reference prompts and seeds rotate, "
            "so the voice does not get monotone."
        ),
        "synthesize_limit": "Only the first N sentences (0 = all, use e.g. 50 for a test)",
        "el_help": (
            "ElevenLabs reads the sentences in its cloud with a voice of your account: no recording, no "
            "GPU, the clips are saved on this computer. The text is sent to ElevenLabs and uses your credits."
        ),
        "el_key": "ElevenLabs API key",
        "el_key_save": "Save key",
        "el_key_ready": "The ElevenLabs key is saved on this computer, for all voices.",
        "el_key_missing": "No ElevenLabs key yet. It is saved once, for all voices.",
        "el_no_key": "No API key yet: save it in Settings.",
        "rename_help": (
            "The name is the voice folder. Clips and settings stay. A training on the GPU machine stays "
            "under the old name. Files already exported keep their names until the next export."
        ),
        "rename_name": "Voice name",
        "rename_save": "Save names",
        "renamed": "Saved the names of voice **{name}**.",
        "rename_busy": "A job is running on this voice: wait for it to finish or stop it.",
        "el_voice": "ElevenLabs voice",
        "el_no_voice": "Choose a voice: click Load voices, then pick one.",
        "el_refresh": "Load voices",
        "el_credits": "Credits left: **{left}** of {limit}.",
        "el_no_credits": "Voices loaded. The key may not read the credits (`user_read`); generating still works.",
        "el_sentences": "Sentence set (taken from an imported voice)",
        "el_sentences_use": "Use this set",
        "el_sentences_done": "**{count}** sentences of {source} will be read.",
        "el_cost": "Voice **{voice}**: **{sentences}** sentences to generate, about **{characters}** characters.",
        "synthesize_run": "Generate clips",
        "synthesize_timing": "Last run: **{clips}** clips in {minutes} min on **{device}** - {per_clip} s per clip, {speed}x real time. All {total} sentences at this pace: about **{estimate}**.",
        "tab_filter": "5. Filter",
        "filter_help": (
            "Checks every clip and builds the training set: Whisper must hear the right text (CER), the "
            "voice must match the recording (similarity), the worst 10% by naturalness (MOS) are dropped, "
            "and the length must fit the text (cut-offs, hallucinations). Thresholds are in Settings."
        ),
        "filter_target": "Clips to keep (0 = target from settings)",
        "filter_asr": "Whisper check",
        "filter_similarity": "Voice similarity",
        "filter_mos": "Naturalness (MOS)",
        "filter_run": "Filter and build dataset",
        "filter_reasons": "Result",
        "filter_kept": "Kept clips (sample)",
        "filter_rejected": "Rejected clips (sample)",
        "tab_train": "6. Training",
        "train_help": (
            "Trains the Piper voice. **Training start:** `bazowy-pl` = your own base without English "
            "(create it in Tools → Base), `lessac` = English lessac checkpoint (fastest), `ckpt:<path>` = any "
            "Piper medium checkpoint. Training resumes automatically. Listen below (**Listen to the training**): "
            "the quality should rise and level off. Stop when it has not improved for ~100 epochs (small "
            "voices) and the samples sound good."
        ),
        "train_estimate": (
            "Dataset: **{clips}** clips → ~{steps} steps per epoch → about {low:.0f}–{high:.0f} s per epoch "
            "(estimate for an RTX 4090 at 1.5–2 steps/s). {epochs} epochs ≈ **{hours_low:.1f}–{hours_high:.1f} h**."
        ),
        "train_no_dataset": "No dataset yet – run the filter (or Tools → Import) first.",
        "max_epochs": "Epochs (on top of the starting checkpoint)",
        "train_run": "Start / resume training",
        "train_poweroff": "Power the machine off when training ends (not after Stop)",
        "job_poweroff": "Power the machine off when this job ends (not after Stop)",
        "job_poweroff_late": "The job has already ended, so nothing was changed.",
        "train_queue": "Training queue",
        "train_queue_info": "Voices train in the order you pick them, each with the epochs and start above.",
        "train_queue_run": "Start the queue",
        "queue_title": "Training queue: voice {current} of {total}",
        "queue_done": "trained",
        "queue_now": "training now",
        "queue_waiting": "waiting",
        "queue_failed": "failed",
        "queue_stopped": "stopped",
        "checkpoints": "Checkpoints (newest first)",
        "tab_export": "7. Export",
        "export_help": (
            "Creates the `.onnx` voice and its `.onnx.json`. Choose the checkpoint with the best `val_mos` "
            "or the one that sounded best. Copy both files into the Piper data folder of Home Assistant "
            "(Wyoming Piper), restart Piper and pick the voice in the Assist pipeline."
        ),
        "checkpoint": "Checkpoint",
        "export_run": "Export",
        "export_files": "Exported files",
        "tab_settings": "Settings",
        "settings_help": (
            "All settings of this voice (`voice.yaml`). The file is saved only when it is valid. Main keys: "
            "`target_clips`, `synthesis.options` (e.g. `cfg_weight`, `exaggeration`), "
            "`quality.max_cer`, `quality.min_similarity`, `train.base`, `train.max_epochs`, `train.num_workers`."
        ),
        "save": "Save",
        "saved": "Saved.",
        "tab_tools": "Tools",
        "server_title": "GPU server (SSH)",
        "server_help": (
            "Training needs an NVIDIA card. Save the machine once and click **Prepare machine**: the panel "
            "checks what is missing and does it (packages when sudo needs no password, uv, code and data, "
            "environments, the web UI service). The checklist below shows what is done, what Prepare does and "
            "what only you can do. Then open the web UI on the machine and train there. "
            "**Bring voices back** copies the exported `.onnx` files here."
        ),
        "server_host": "Address",
        "server_user": "User",
        "server_port": "Port",
        "server_key": "SSH key",
        "server_key_default": "Default (ssh-agent, ~/.ssh/config)",
        "server_dir": "Folder on the machine",
        "server_ui_port": "Web UI port there",
        "server_save": "Save",
        "server_check": "Check connection",
        "server_status": "Check machine",
        "server_prepare": "Prepare machine",
        "kind_remote-status": "Server: machine check",
        "kind_remote-prepare": "Server: preparing the machine",
        "ready_title": "Machine",
        "ready_never": "Not checked yet - click **Check machine** or **Prepare machine**.",
        "ready_error": "The machine did not answer: {error}",
        "ready_ready": "Ready for training.",
        "ready_todo": "{n} to do - **Prepare machine** does it by itself.",
        "ready_manual": "First do yourself what is marked ✋, then click **Prepare machine**.",
        "ready_checked": "checked {time}",
        "ready_gpu": "NVIDIA card and driver",
        "ready_tools": "System packages",
        "ready_uv": "uv (Python installer)",
        "ready_disk": "Free disk",
        "ready_code": "Panel code",
        "ready_data": "Voice recordings",
        "ready_venv": "Panel environment (.venv)",
        "ready_train": "Training environment (.venv-train)",
        "ready_service": "Web UI service",
        "ready_tensorboard": "TensorBoard (training charts)",
        "ready_hint_todo": "Prepare does it",
        "ready_hint_manual": "run it yourself in the Mac terminal (asks for the sudo password):",
        "ready_hint_gpu": "install the NVIDIA driver on the machine, then reboot:",
        "ready_hint_disk": "little space left (30 GB or more recommended)",
        "ready_hint_train": "torch does not see the card - check the driver (nvidia-smi)",
        "ready_hint_code": "the machine has another version",
        "ready_hint_data": "differ from this computer:",
        "ready_login": "Login to the web UI on the machine",
        "ready_show": "show",
        "server_push": "Send code and data",
        "server_install": "Install / update",
        "server_pull": "Bring voices back",
        "server_saved": "Saved. Web UI on the server (after the install): {url}",
        "server_missing": "Save the server first.",
        "import_title": "Import an existing dataset",
        "import_help": (
            "Cleans an old LJSpeech folder (`metadata.csv` + `wav/`) into this voice's dataset: the same "
            "plain-text rules, real 22,050 Hz WAV (also MP3 files named .wav). Persona files written as "
            "numbered lists (`1. …`) have the numbering removed; a bare file name is looked up in that folder."
        ),
        "import_dir": "Folder of the old dataset (on this machine)",
        "import_persona": "Persona metadata file (optional, e.g. custom_metadata.csv)",
        "import_verify": "Check every clip with Whisper (slow)",
        "import_run": "Import",
        "base_title": "Own base without English (bazowy-pl)",
        "base_help": (
            "Trained once from random weights on a large single-speaker dataset (e.g. MC Speech, CC0, "
            "~22,000 recordings), then every voice is fine-tuned from it. Takes days on one GPU."
        ),
        "base_dir": "Recordings for the base",
        "base_dir_info": "Pick the voice whose recordings the base is trained on - the largest one (e.g. kasia); one speaker, the more clips the better. Or type the path of your own LJSpeech folder (metadata.csv + wav/).",
        "base_source": "{name} - {clips} clips",
        "base_advanced": "Advanced",
        "base_dir_missing": "Choose the recordings for the base first (or type a folder).",
        "base_audio_info": "Leave empty. Only for your own dataset whose audio files are not in <folder>/wav.",
        "base_epochs_info": "How long the base trains. With ~18,000 clips one epoch is ~3 min (medium) or ~2-3x longer (high) on an RTX 4090; the Progress card shows the time left. You can stop and resume any time.",
        "base_checkpoint_info": "Appears while the base trains. Pick the one that sounds best (listen below), then “Use as bazowy-pl”; the size (medium/high) goes with it.",
        "base_on_machine": "This panel drives the GPU machine: **prepare and train the base in the panel on the machine** ({url}) - base data is not sent from here.",
        "base_audio_dir": "Audio folder (empty = <folder>/wav)",
        "base_prepare": "Prepare base dataset",
        "base_epochs": "Epochs",
        "base_train": "Train base",
        "base_checkpoint": "Base checkpoint",
        "base_select": "Use as bazowy-pl",
        "base_export": "Export as a voice",
        "base_create": "Create the bazowy-pl base",
        "base_quality": "Model size",
        "base_quality_info": "medium: Piper's standard, quick to train and to speak. high: 8x larger decoder (the part that makes the sound): cleaner audio, about 2-3x slower training and slower speech on the Jetson. Each size trains in its own folder from the same recordings, so both can be compared below.",
        "base_quality_medium": "medium (standard)",
        "base_quality_high": "high (cleaner sound)",
        "base_batch": "Batch",
        "base_batch_info": "Clips per training step: 32 for medium, 16 for high fit a 24 GB card. Lower it if training stops with “CUDA out of memory”.",
        "score_title": "Rate the recordings (UTMOS)",
        "score_help": "A model learns to sound like its recordings, so their score is the ceiling of val_mos. This rates a random sample with the same UTMOS that computes val_mos. When the training holds the GPU it runs on the CPU (about 7 clips/s), next to the training.",
        "score_sample": "Clips to rate",
        "score_sample_info": "300 is enough for the median. 0 = all (18,000 clips: about 45 min on the CPU, a few minutes on a free GPU).",
        "score_run": "Rate recordings",
        "score_none": "Not rated yet.",
        "score_starting": "Rating: loading UTMOS…",
        "score_running": "Rating recordings",
        "score_failed": "Rating failed:",
        "score_median": "Median",
        "score_p10": "10% worst below",
        "score_p90": "10% best above",
        "score_good": "At {good} or more",
        "score_summary": "**{count}** of {total} recordings rated. A trained model rarely sounds better than its recordings: **{median}** is the val_mos ceiling of this base. Best val_mos so far: {best}.",
        "score_worst": "Worst recordings",
        "score_best": "Best recordings",
        "score_clip": "{score} · {text}",
        "compare_title": "Compare base models",
        "compare_help": "Same recordings, same test sentences - compare at the same epoch. val_mos of a single epoch is noisy (5 sentences), so the table shows the mean of the last {window} epochs up to the epoch every run has reached. Listen too: choose the model under “Listen to the training”.",
        "compare_none": "No base training yet.",
        "compare_model": "Model",
        "compare_epochs": "Epochs done",
        "compare_mos_at": "val_mos, epochs {start}-{end}",
        "compare_mel_at": "val_mel, epochs {start}-{end}",
        "compare_best_mos": "Best val_mos",
        "compare_best_mel": "Lowest val_mel",
        "compare_ceiling": "Recordings (median UTMOS): **{median}**",
        "listen_model": "Model",
        "listen_title": "Listen to the training",
        "listen_help": "After every epoch the trainer reads a few test sentences in the new voice. Pick an epoch and listen: noise and a robot at first, clearer later. **Quality** is the predicted naturalness (UTMOS, 1-5): about 2 raw, about 3 understandable, 3.5 and more good; a model rarely beats its own recordings (rate them in Tools, own base). Kept: the first epoch, every 10th, the 3 newest, the 5 with the best quality and every epoch with a checkpoint (marked 💾 checkpoint: the same epoch as epoch=N in Base checkpoint).",
        "listen_epoch": "Epoch",
        "listen_item": "epoch {epoch} · quality {mos}",
        "listen_saved": " · 💾 checkpoint",
        "listen_refresh": "↻ Refresh",
        "listen_download": "⬇ Download samples (ZIP)",
        "listen_download_file": "Samples of every kept epoch: unzip and open index.html (sorting, only epochs with a checkpoint)",
        "listen_download_none": "No training samples to download yet.",
        "listen_none": "No samples yet: the training has not finished its first epoch (it prepares the cache first).",
        "listen_summary": "Last epoch: **{last}** · quality: **{mos}** · best: **{best}** in epoch {best_epoch}",
        "listen_elsewhere": "The training runs on the GPU machine - listen in the panel there ({url}).",
        "tensorboard_link": "Charts in TensorBoard",
        "chart_base": "Base bazowy-pl ({quality})",
        "chart_voice": "Voice {voice}",
        "chart_title_mos": "Quality (val_mos, higher is better)",
        "chart_title_mel": "Mel error (lower is better)",
        "chart_epoch": "Epoch",
        "chart_open": "Click to enlarge",
        "chart_none": "The chart appears after the first training epoch.",
        "chart_from": "From epoch",
        "chart_to": "to",
        "chart_all": "Whole run",
        "chart_pinned": "Chosen epoch",
        "chart_pick": "Click a chart to choose an epoch; drag over a chart to zoom into those epochs.",
        "chart_best_mos": "Best quality: {value} (epoch {epoch})",
        "chart_best_mel": "Lowest val_mel: {value} (epoch {epoch})",
        "chart_help": "**val_mos** - predicted naturalness of the voice (UTMOS, 1-5) on the test sentences after every epoch. About 2 raw, about 3 understandable, 3.5+ good; a model rarely beats its own recordings (“Rate recordings” in Tools). **Higher is better.**\n**val_mel** - how far the generated sound (mel spectrogram) is from the real one on sentences the model never trained on. **Lower is better**; it falls fast at first, then hardly moves - that alone does not mean the end.\n**train_mel** - the same error on the training sentences (mean of the epoch). It keeps falling slowly.\n**When the model is best:** val_mos has stopped rising (flat for about 150-200 epochs), val_mel is not rising, and the samples in “Listen to the training” sound good. Take the checkpoint with the highest val_mos from that stretch.\n**Overtraining:** train_mel keeps falling while val_mel starts to rise - the model memorises the sentences instead of speaking. Take a checkpoint from before val_mel rose.",
        "base_not_ready": "**bazowy-pl does not exist on this computer yet**, so lessac is chosen. Create it with **Create the bazowy-pl base** (Tools, own base) or train on the machine where it is.",
        "base_selected": "Base ready: {path}",
        "base_missing": "bazowy-pl does not exist yet. Steps: 1. **Prepare base dataset**, 2. **Train base**, 3. pick a checkpoint and **Use as bazowy-pl**.",
        "error": "Error: {error}",
        "status_checking": "Checking the machine…",
        "job_remote_running": "On the machine: **{kind}**{voice} is running…",
        "machine_ssh_error": "The GPU machine did not answer over SSH: {error}",
        "machine_on": "Machine: on",
        "machine_off": "Machine: off",
        "machine_starting": "Machine: starting",
        "machine_stopping": "Machine: shutting down",
        "machine_checking": "Machine: checking…",
        "machine_unknown": "Machine: no reading from HA",
        "machine_rejected": "Machine: HA token rejected",
        "ha_token_rejected": "Home Assistant rejected the token, so nothing asks HA any more (each rejection is a failed login for IP_BAN). Paste a correct token or click “Save connection” to check it again.",
        "ask_cancel": "Cancel",
        "machine_on_hint": "Click to switch the GPU machine on (its switch in Home Assistant).",
        "machine_off_hint": "Click to switch the machine off safely: Home Assistant shuts the system down, then the plug.",
        "machine_wait_hint": "Wait until the machine has finished starting or shutting down.",
        "machine_on_confirm": "Switch the GPU machine on? Home Assistant switches its plug on and the computer starts by itself (1–2 min).",
        "machine_off_confirm": "Switch the GPU machine off? Home Assistant shuts the system down over SSH, waits until the plug shows the power dropped and only then cuts the power. When the machine does not go down in 5 minutes, the plug stays on.",
        "machine_switched_on": "Home Assistant is switching the GPU machine on - it starts in 1–2 minutes.",
        "machine_switched_off": "Home Assistant is shutting the GPU machine down - the plug goes off when the power has dropped.",
        "ha_title": "Home Assistant",
        "ha_help": (
            "Optional. With the address and a long-lived token of a Home Assistant **administrator** the "
            "top bar gets a button that switches the GPU machine on and off and shows its state. The token "
            "is kept only on this computer in `~/.config/piper-voice-cloner/home_assistant.json` (mode 600), "
            "not in the data folder, and never comes back to this page."
        ),
        "ha_url": "Home Assistant address",
        "ha_token": "Token (long-lived, of an administrator)",
        "ha_token_placeholder": "paste the token",
        "ha_token_saved": "saved - type a new one to change it",
        "ha_save": "Save connection",
        "ha_remove": "Remove connection",
        "ha_saved": "Saved. Home Assistant answers ({count} entities).",
        "ha_saved_failed": "Saved, but Home Assistant does not answer: {error}",
        "ha_remove_confirm": "Remove the Home Assistant address and token from this computer?",
        "ha_removed": "The Home Assistant address and token were removed from this computer.",
        "ha_missing": "Set the Home Assistant address and token first.",
        "power_title": "Power of the GPU machine",
        "power_help": (
            "The machine's switch in Home Assistant that does the whole job: on = the plug (the BIOS starts the "
            "computer), off = the system over SSH, waiting for the power to drop, then the plug (example: "
            "`docs/home-assistant/maszyna_gpu.yaml`). Not the plug itself, so switching off never cuts a running "
            "system. The top bar gets a button with the machine's state."
        ),
        "power_switch": "Machine switch (e.g. switch.maszyna_gpu)",
        "power_sensor": "Plug power in W (e.g. sensor.…_moc_czynna)",
        "power_watts": "Off threshold (W)",
        "power_suggest": "↻ Suggestions from HA",
        "power_suggested": "Home Assistant has {switches} switches and {sensors} power sensors (W) - pick them in the lists.",
        "power_save": "Save power settings",
        "power_saved": "Saved. The machine button is in the top bar.",
    },
    "pl": {
        "title": "Piper Voice Cloner",
        "guide": "Instrukcja",
        "subtitle": "Z krótkiego nagrania własny głos Piper",
        "stage": "Etap",
        "stage_idle": "Nic nie działa",
        "elapsed": "Trwa od",
        "stage_last": "Ostatnie zadanie",
        "elapsed_took": "Trwało",
        "epochs": "epok",
        "train_position": "epoka modelu {epoch} · krok {step}/{steps}",
        "time_left": "zostało ok. {time}",
        "result_ok": "zakończone",
        "result_failed": "błąd, zobacz log",
        "result_stopped": "zatrzymane",
        "gpu": "Karta",
        "no_gpu": "brak karty NVIDIA",
        "utilization": "Obciążenie",
        "memory": "Pamięć",
        "temperature": "Temperatura",
        "power": "Moc",
        "kind_reference": "Nagranie",
        "kind_audition": "Odsłuch",
        "kind_synthesize": "Generowanie klipów",
        "kind_filter": "Filtrowanie",
        "kind_import": "Import",
        "kind_train": "Trening",
        "kind_train-queue": "Kolejka treningów",
        "kind_export": "Eksport",
        "kind_base-prepare": "Baza: przygotowanie danych",
        "kind_base-train": "Baza: trening",
        "kind_base-select": "Baza: wybór",
        "kind_base-score": "Baza: ocena nagrań",
        "kind_remote-check": "Serwer: sprawdzanie połączenia",
        "kind_remote-push": "Serwer: wysyłanie kodu i danych",
        "kind_remote-install": "Serwer: instalacja",
        "kind_remote-pull": "Serwer: pobieranie głosów",
        "intro": (
            "Z krótkiego nagrania powstaje własny głos Piper. Przechodź przez zakładki od lewej do prawej. "
            "Długie kroki (generowanie, filtr, trening) działają w tle: możesz zamknąć przeglądarkę i wrócić. "
            "Naraz działa jedno zadanie."
        ),
        "voice": "Głos",
        "refresh": "Odśwież",
        "new_voice": "Nowy głos",
        "new_voice_help": (
            "Nazwa: małe litery, cyfry i `_` (np. `kuba_bajka`); `Kuba Bajka` sama zmieni się w `kuba_bajka`. "
            "Nazwa pliku Piper jest opcjonalna, "
            "np. `pl_PL-kuba_bajka`; domyślnie `<locale>-<nazwa>`."
        ),
        "name": "Nazwa",
        "piper_name": "Nazwa pliku Piper (opcjonalnie)",
        "backend": "Model klonujący",
        "base": "Start treningu",
        "create": "Utwórz",
        "created": "Utworzono głos **{name}**.",
        "no_voice": "Najpierw utwórz albo wybierz głos.",
        "progress": "Postęp",
        "step_reference": "Nagranie",
        "step_corpus": "Zdania",
        "step_audition": "Odsłuch",
        "step_synthesize": "Generowanie",
        "step_filter": "Filtr",
        "step_train": "Trening",
        "step_export": "Eksport",
        "job": "Zadanie w tle",
        "job_none": "Nie uruchomiono jeszcze żadnego zadania.",
        "job_running": "Trwa **{kind}**{voice}…",
        "job_ok": "**{kind}**{voice} zakończone.",
        "server_answers": "**Serwer** znów odpowiada przez SSH.",
        "job_failed": "**{kind}**{voice} nie powiodło się (kod {code}). Zobacz log i FAQ w instrukcji.",
        "job_stopped": "**{kind}**{voice} zatrzymane. Uruchom ponownie, aby kontynuować.",
        "job_busy": "Trwa jeszcze zadanie: {job}. Poczekaj, aż się skończy (karta Postęp), albo je zatrzymaj i kliknij ponownie.",
        "job_started": "Uruchomiono **{kind}**. Postęp widać w panelu po prawej.",
        "stop": "Zatrzymaj zadanie",
        "stopped": "Wysłano polecenie zatrzymania.",
        "log": "Log (ostatnie linie)",
        "log_expand": "Powiększ",
        "log_copy": "Kopiuj",
        "log_copied": "Skopiowano",
        "log_copy_failed": "Nie udało się skopiować - zaznacz tekst w dużym oknie",
        "log_close": "Zamknij",
        "tab_reference": "1. Nagranie",
        "reference_help": (
            "Wgraj 10–60 sekund **czystej** mowy docelowego głosu: bez muzyki, telewizora w tle i innych osób. "
            "Dowolny format (wav, mp3, m4a). Naturalna, zróżnicowana mowa działa lepiej niż czytanie listy. "
            "Nagrania są przycinane, wyrównywane i cięte na fragmenty 3–12 s; na ich podstawie kalibrowany "
            "jest próg podobieństwa dla filtra."
        ),
        "reference_files": "Nagrania",
        "reference_embed": "Policz embedding mówcy (zalecane)",
        "prepare": "Przygotuj nagranie",
        "reference_done": "Referencja: {seconds} s mowy, {prompts} fragmentów. Próg podobieństwa: {threshold}.",
        "reference_short": "**Krótkie nagranie** ({seconds} s, fragmentów: {prompts}): klonowanie zadziała, ale 30-60 s różnorodnej mowy daje stabilniejszą barwę i pewniejszy próg podobieństwa.",
        "reference_clips": "Przygotowane fragmenty",
        "tab_corpus": "2. Zdania",
        "corpus_help": (
            "Zdania, które przeczyta model klonujący. Wgraj pliki tekstowe (jedno zdanie w linii albo "
            "`id<TAB>tekst`). Używany jest tylko **zwykły tekst**: linie z cyframi, godzinami, datami, numeracją, "
            "symbolami albo skrótami są odrzucane, a nie przerabiane; liczby czyta normalizacja tekstu w czasie "
            "działania. Wybór równomiernie pokrywa wszystkie głoski."
        ),
        "corpus_files": "Pliki ze zdaniami",
        "corpus_bundled": "Dodaj zdania z pakietu językowego (kwestie dla dzieci)",
        "corpus_size": "Liczba zdań (0 = cel × overgenerate)",
        "build": "Wybierz zdania",
        "corpus_done": "Wybrano {count} zdań.",
        "corpus_preview": "Pierwsze zdania",
        "tab_audition": "3. Odsłuch",
        "audition_help": (
            "Sprawdza kilka ustawień modelu klonującego na kilku zdaniach. Posłuchaj i wybierz kombinację, "
            "która najbardziej przypomina oryginał; wynik (podobieństwo − 2 × CER + 0,05 × MOS) to tylko "
            "wskazówka. Jeśli nic nie brzmi dobrze, popraw nagranie, zanim wygenerujesz tysiące klipów."
        ),
        "audition_count": "Zdań na kombinację",
        "audition_run": "Uruchom odsłuch",
        "audition_table": "Wyniki (najlepsze na górze)",
        "audition_pick": "Kombinacja do odsłuchu",
        "audition_apply": "Użyj tych ustawień",
        "audition_applied": "Zapisano ustawienia: {options}",
        "tab_synthesize": "4. Generowanie",
        "synthesize_help": (
            "Czyta każde wybrane zdanie sklonowanym głosem. Trwa to dłużej (tysiące klipów); można przerwać "
            "i uruchomić ponownie, gotowe klipy zostają. Fragmenty referencji i seedy się zmieniają, żeby głos "
            "nie był monotonny."
        ),
        "synthesize_limit": "Tylko pierwsze N zdań (0 = wszystkie, na próbę np. 50)",
        "el_help": (
            "ElevenLabs czyta zdania w swojej chmurze głosem z Twojego konta: bez nagrania i bez karty "
            "graficznej, klipy zapisują się na tym komputerze. Tekst trafia do ElevenLabs i zużywa kredyty."
        ),
        "el_key": "Klucz API ElevenLabs",
        "el_key_save": "Zapisz klucz",
        "el_key_ready": "Klucz ElevenLabs jest zapisany na tym komputerze, dla wszystkich głosów.",
        "el_key_missing": "Brak klucza ElevenLabs. Zapisujesz go raz, dla wszystkich głosów.",
        "el_no_key": "Brak klucza API: zapisz go w Ustawieniach.",
        "rename_help": (
            "Nazwa to folder głosu. Klipy i ustawienia zostają. Trening na maszynie z GPU zostaje pod "
            "starą nazwą. Wyeksportowane pliki zachowają nazwy do następnego eksportu."
        ),
        "rename_name": "Nazwa głosu",
        "rename_save": "Zapisz nazwy",
        "renamed": "Zapisano nazwy głosu **{name}**.",
        "rename_busy": "Na tym głosie trwa zadanie: poczekaj na koniec albo je zatrzymaj.",
        "el_voice": "Głos ElevenLabs",
        "el_no_voice": "Wybierz głos: kliknij Wczytaj głosy, a potem wybierz z listy.",
        "el_refresh": "Wczytaj głosy",
        "el_credits": "Pozostało kredytów: **{left}** z {limit}.",
        "el_no_credits": "Głosy wczytane. Klucz nie może odczytać kredytów (`user_read`), ale generowanie działa.",
        "el_sentences": "Zestaw zdań (z zaimportowanego głosu)",
        "el_sentences_use": "Użyj zestawu",
        "el_sentences_done": "Głos przeczyta **{count}** zdań z zestawu {source}.",
        "el_cost": "Głos **{voice}**: do wygenerowania **{sentences}** zdań, około **{characters}** znaków.",
        "synthesize_run": "Generuj klipy",
        "synthesize_timing": "Ostatnie generowanie: **{clips}** klipów w {minutes} min na **{device}** - {per_clip} s na klip, {speed}x czasu rzeczywistego. Wszystkie zdania ({total}) w tym tempie: ok. **{estimate}**.",
        "tab_filter": "5. Filtr",
        "filter_help": (
            "Sprawdza każdy klip i buduje zbiór treningowy: Whisper musi usłyszeć właściwy tekst (CER), głos "
            "musi pasować do nagrania (podobieństwo), 10% najgorszych według naturalności (MOS) odpada, a długość "
            "musi pasować do tekstu (ucięcia, halucynacje). Progi są w Ustawieniach."
        ),
        "filter_target": "Ile klipów zostawić (0 = cel z ustawień)",
        "filter_asr": "Kontrola Whisperem",
        "filter_similarity": "Podobieństwo głosu",
        "filter_mos": "Naturalność (MOS)",
        "filter_run": "Filtruj i zbuduj dataset",
        "filter_reasons": "Wynik",
        "filter_kept": "Zostawione klipy (próbka)",
        "filter_rejected": "Odrzucone klipy (próbka)",
        "tab_train": "6. Trening",
        "train_help": (
            "Trenuje głos Piper. **Start treningu:** `bazowy-pl` = własna baza bez angielskiego (utworzysz ją "
            "w Narzędzia → Baza), `lessac` = angielski checkpoint lessac (najszybciej), `ckpt:<ścieżka>` = dowolny "
            "checkpoint Piper medium. Trening sam się wznawia. Słuchaj niżej (**Odsłuch z treningu**): jakość "
            "powinna rosnąć i się wypłaszczyć. Przerwij, gdy nie rośnie od ~100 epok (małe głosy), a próbki "
            "brzmią dobrze."
        ),
        "train_estimate": (
            "Dataset: **{clips}** klipów → ~{steps} kroków na epokę → około {low:.0f}–{high:.0f} s na epokę "
            "(szacunek dla RTX 4090 przy 1,5–2 krokach/s). {epochs} epok ≈ **{hours_low:.1f}–{hours_high:.1f} h**."
        ),
        "train_no_dataset": "Nie ma jeszcze datasetu – najpierw uruchom filtr (albo Narzędzia → Import).",
        "max_epochs": "Epoki (ponad checkpointem startowym)",
        "train_run": "Rozpocznij / wznów trening",
        "train_poweroff": "Wyłącz maszynę po zakończeniu treningu (nie po Zatrzymaj)",
        "job_poweroff": "Wyłącz maszynę po zakończeniu tego zadania (nie po Zatrzymaj)",
        "job_poweroff_late": "Zadanie już się skończyło, więc nic nie zmieniono.",
        "train_queue": "Kolejka treningów",
        "train_queue_info": "Głosy trenują się w kolejności wyboru, każdy z ustawionymi wyżej epokami i startem.",
        "train_queue_run": "Uruchom kolejkę",
        "queue_title": "Kolejka treningów: głos {current} z {total}",
        "queue_done": "wytrenowany",
        "queue_now": "trenuje teraz",
        "queue_waiting": "czeka",
        "queue_failed": "błąd",
        "queue_stopped": "zatrzymany",
        "checkpoints": "Checkpointy (najnowsze na górze)",
        "tab_export": "7. Eksport",
        "export_help": (
            "Tworzy głos `.onnx` i plik `.onnx.json`. Wybierz checkpoint z najlepszym `val_mos` albo ten, który "
            "brzmiał najlepiej. Skopiuj oba pliki do katalogu danych Pipera w Home Assistant (Wyoming Piper), "
            "zrestartuj Pipera i wybierz głos w pipeline Assist."
        ),
        "checkpoint": "Checkpoint",
        "export_run": "Eksportuj",
        "export_files": "Wyeksportowane pliki",
        "tab_settings": "Ustawienia",
        "settings_help": (
            "Wszystkie ustawienia tego głosu (`voice.yaml`). Plik zapisuje się tylko wtedy, gdy jest poprawny. "
            "Najważniejsze klucze: `target_clips`, `synthesis.options` (np. `cfg_weight`, `exaggeration`), "
            "`quality.max_cer`, `quality.min_similarity`, `train.base`, `train.max_epochs`, `train.num_workers`."
        ),
        "save": "Zapisz",
        "saved": "Zapisano.",
        "tab_tools": "Narzędzia",
        "server_title": "Serwer z GPU (SSH)",
        "server_help": (
            "Trening wymaga karty NVIDIA. Zapisz maszynę raz i kliknij **Przygotuj maszynę**: panel sprawdzi, "
            "czego brakuje, i zrobi to sam (pakiety, gdy sudo nie pyta o hasło, uv, kod i dane, środowiska, "
            "usługę panelu). Lista poniżej pokazuje, co jest gotowe, co zrobi Przygotuj, a co musisz zrobić "
            "sam. Potem otwórz panel na maszynie i trenuj tam. **Pobierz gotowe głosy** kopiuje "
            "wyeksportowane pliki `.onnx` tutaj."
        ),
        "server_host": "Adres",
        "server_user": "Użytkownik",
        "server_port": "Port",
        "server_key": "Klucz SSH",
        "server_key_default": "Domyślny (ssh-agent, ~/.ssh/config)",
        "server_dir": "Folder na maszynie",
        "server_ui_port": "Port panelu na serwerze",
        "server_save": "Zapisz",
        "server_check": "Sprawdź połączenie",
        "server_status": "Sprawdź maszynę",
        "server_prepare": "Przygotuj maszynę",
        "kind_remote-status": "Serwer: sprawdzanie maszyny",
        "kind_remote-prepare": "Serwer: przygotowanie maszyny",
        "ready_title": "Maszyna",
        "ready_never": "Jeszcze nie sprawdzona - kliknij **Sprawdź maszynę** albo **Przygotuj maszynę**.",
        "ready_error": "Maszyna nie odpowiedziała: {error}",
        "ready_ready": "Gotowa do treningu.",
        "ready_todo": "Do zrobienia: {n} - **Przygotuj maszynę** zrobi to sam.",
        "ready_manual": "Najpierw zrób sam to, co oznaczone ✋, potem kliknij **Przygotuj maszynę**.",
        "ready_checked": "sprawdzono {time}",
        "ready_gpu": "Karta NVIDIA i sterownik",
        "ready_tools": "Pakiety systemowe",
        "ready_uv": "uv (instalator Pythona)",
        "ready_disk": "Wolne miejsce",
        "ready_code": "Kod panelu",
        "ready_data": "Nagrania głosów",
        "ready_venv": "Środowisko panelu (.venv)",
        "ready_train": "Środowisko treningu (.venv-train)",
        "ready_service": "Panel jako usługa",
        "ready_tensorboard": "TensorBoard (wykresy treningu)",
        "ready_hint_todo": "zrobi Przygotuj",
        "ready_hint_manual": "uruchom sam w terminalu na Macu (zapyta o hasło sudo):",
        "ready_hint_gpu": "zainstaluj sterownik NVIDIA na maszynie i uruchom ją ponownie:",
        "ready_hint_disk": "mało miejsca (zalecane co najmniej 30 GB)",
        "ready_hint_train": "torch nie widzi karty - sprawdź sterownik (nvidia-smi)",
        "ready_hint_code": "na maszynie jest inna wersja",
        "ready_hint_data": "różnią się od tego komputera:",
        "ready_login": "Logowanie do panelu na maszynie",
        "ready_show": "pokaż",
        "server_push": "Wyślij kod i dane",
        "server_install": "Zainstaluj / aktualizuj",
        "server_pull": "Pobierz gotowe głosy",
        "server_saved": "Zapisano. Panel na serwerze (po instalacji): {url}",
        "server_missing": "Najpierw zapisz serwer.",
        "import_title": "Import istniejącego datasetu",
        "import_help": (
            "Czyści stary katalog LJSpeech (`metadata.csv` + `wav/`) do datasetu tego głosu: te same reguły "
            "zwykłego tekstu, prawdziwe WAV 22 050 Hz (także pliki MP3 nazwane .wav). W plikach persony "
            "zapisanych jako numerowana lista (`1. …`) numeracja jest usuwana; samą nazwę pliku szukam w tym katalogu."
        ),
        "import_dir": "Katalog starego datasetu (na tym komputerze)",
        "import_persona": "Plik metadanych persony (opcjonalnie, np. custom_metadata.csv)",
        "import_verify": "Sprawdź każdy klip Whisperem (wolne)",
        "import_run": "Importuj",
        "base_title": "Własna baza bez angielskiego (bazowy-pl)",
        "base_help": (
            "Trenowana raz, od losowych wag, na dużym zbiorze jednego mówcy (np. MC Speech, CC0, ~22 000 nagrań); "
            "potem każdy głos doszkala się od niej. Trwa kilka dni na jednej karcie."
        ),
        "base_dir": "Nagrania do bazy",
        "base_dir_info": "Wybierz głos, na którego nagraniach wytrenuje się baza - najlepiej największy (np. kasia); jeden mówca, im więcej klipów, tym lepiej. Albo wpisz ścieżkę własnego zbioru LJSpeech (folder z metadata.csv i wav/).",
        "base_source": "{name} - {clips} klipów",
        "base_advanced": "Zaawansowane",
        "base_dir_missing": "Najpierw wybierz nagrania do bazy (albo wpisz folder).",
        "base_audio_info": "Zostaw puste. Tylko dla własnego zbioru, którego pliki audio nie leżą w <folder>/wav.",
        "base_epochs_info": "Jak długo trenuje się baza. Przy ~18 000 klipów jedna epoka to ~3 min (medium) albo ~2-3x dłużej (high) na RTX 4090; karta Postęp pokaże czas do końca. Można przerwać i wznowić w dowolnej chwili.",
        "base_checkpoint_info": "Pojawią się w trakcie treningu bazy. Wybierz ten, który najlepiej brzmi (odsłuch niżej), i kliknij „Użyj jako bazowy-pl”; wielkość (medium/high) idzie razem z nim.",
        "base_on_machine": "Ten panel steruje maszyną z GPU: **dataset bazy przygotuj i trenuj w panelu na maszynie** ({url}) - dane bazy nie są stąd wysyłane.",
        "base_audio_dir": "Katalog audio (puste = <katalog>/wav)",
        "base_prepare": "Przygotuj dataset bazy",
        "base_epochs": "Epoki",
        "base_train": "Trenuj bazę",
        "base_checkpoint": "Checkpoint bazy",
        "base_select": "Użyj jako bazowy-pl",
        "base_export": "Eksportuj jako głos",
        "base_create": "Utwórz model bazowy-pl",
        "base_quality": "Wielkość modelu",
        "base_quality_info": "medium: standard Pipera, szybki trening i szybkie mówienie. high: 8x większy dekoder (część, która tworzy dźwięk): czystszy dźwięk, ok. 2-3x dłuższy trening i wolniejsze mówienie na Jetsonie. Każda wielkość trenuje się we własnym folderze z tych samych nagrań, więc obie można porównać niżej.",
        "base_quality_medium": "medium (standard)",
        "base_quality_high": "high (czystszy dźwięk)",
        "base_batch": "Batch",
        "base_batch_info": "Ile nagrań na jeden krok treningu: 32 dla medium, 16 dla high mieszczą się na karcie 24 GB. Zmniejsz, jeśli trening przerwie się z „CUDA out of memory”.",
        "score_title": "Ocena nagrań (UTMOS)",
        "score_help": "Model uczy się brzmieć jak jego nagrania, więc ich ocena to sufit val_mos. Ta ocena bierze losową próbkę i liczy ją tym samym UTMOS, który liczy val_mos. Gdy kartę zajmuje trening, działa na CPU (ok. 7 nagrań/s), obok treningu.",
        "score_sample": "Ile nagrań ocenić",
        "score_sample_info": "300 wystarcza do mediany. 0 = wszystkie (18 000 nagrań: ok. 45 min na CPU, kilka minut na wolnej karcie).",
        "score_run": "Oceń nagrania",
        "score_none": "Jeszcze nie oceniono.",
        "score_starting": "Ocena: wczytuję UTMOS…",
        "score_running": "Ocena nagrań",
        "score_failed": "Ocena nie powiodła się:",
        "score_median": "Mediana",
        "score_p10": "10% najsłabszych poniżej",
        "score_p90": "10% najlepszych powyżej",
        "score_good": "Co najmniej {good}",
        "score_summary": "Ocenione nagrania: **{count}** z {total}. Wytrenowany model rzadko brzmi lepiej niż jego nagrania: **{median}** to sufit val_mos tej bazy. Najlepszy val_mos do tej pory: {best}.",
        "score_worst": "Najsłabsze nagrania",
        "score_best": "Najlepsze nagrania",
        "score_clip": "{score} · {text}",
        "compare_title": "Porównanie modeli bazowych",
        "compare_help": "Te same nagrania i te same zdania testowe - porównuj w tej samej epoce. val_mos jednej epoki skacze (5 zdań), dlatego tabela pokazuje średnią z ostatnich {window} epok do epoki, do której doszły wszystkie modele. Posłuchaj też: wybierz model w „Odsłuch z treningu”.",
        "compare_none": "Nie ma jeszcze żadnego treningu bazy.",
        "compare_model": "Model",
        "compare_epochs": "Epoki",
        "compare_mos_at": "val_mos, epoki {start}-{end}",
        "compare_mel_at": "val_mel, epoki {start}-{end}",
        "compare_best_mos": "Najlepszy val_mos",
        "compare_best_mel": "Najniższy val_mel",
        "compare_ceiling": "Nagrania (mediana UTMOS): **{median}**",
        "listen_model": "Model",
        "listen_title": "Odsłuch z treningu",
        "listen_help": "Po każdej epoce trener czyta kilka zdań testowych nowym głosem. Wybierz epokę i posłuchaj: na początku szum i „robot”, potem coraz wyraźniej. **Jakość** to przewidywana naturalność (UTMOS, 1-5): ok. 2 surowy, ok. 3 zrozumiały, 3,5 i więcej dobry; model rzadko przebija własne nagrania (oceń je w Narzędziach, własna baza). Zachowane są: pierwsza epoka, co 10., 3 najnowsze, 5 z najlepszą jakością i każda epoka z checkpointem (oznaczona 💾 checkpoint: to ta sama epoka co epoch=N w polu Checkpoint bazy).",
        "listen_epoch": "Epoka",
        "listen_item": "epoka {epoch} · jakość {mos}",
        "listen_saved": " · 💾 checkpoint",
        "listen_refresh": "↻ Odśwież",
        "listen_download": "⬇ Pobierz próbki (ZIP)",
        "listen_download_file": "Próbki wszystkich zachowanych epok: rozpakuj i otwórz index.html (sortowanie, tylko epoki z checkpointem)",
        "listen_download_none": "Nie ma jeszcze próbek z treningu do pobrania.",
        "listen_none": "Brak próbek: trening nie skończył jeszcze pierwszej epoki (najpierw przygotowuje cache).",
        "listen_summary": "Ostatnia epoka: **{last}** · jakość: **{mos}** · najlepsza: **{best}** w epoce {best_epoch}",
        "listen_elsewhere": "Trening trwa na maszynie z GPU - odsłuch jest w panelu na maszynie ({url}).",
        "tensorboard_link": "Wykresy w TensorBoard",
        "chart_base": "Baza bazowy-pl ({quality})",
        "chart_voice": "Głos {voice}",
        "chart_title_mos": "Jakość (val_mos, wyżej = lepiej)",
        "chart_title_mel": "Błąd mel (niżej = lepiej)",
        "chart_epoch": "Epoka",
        "chart_open": "Kliknij, aby powiększyć",
        "chart_none": "Wykres pojawi się po pierwszej epoce treningu.",
        "chart_from": "Od epoki",
        "chart_to": "do",
        "chart_all": "Cały trening",
        "chart_pinned": "Wybrana epoka",
        "chart_pick": "Kliknij wykres, aby wybrać epokę; przeciągnij po wykresie, aby powiększyć ten zakres epok.",
        "chart_best_mos": "Najlepsza jakość: {value} (epoka {epoch})",
        "chart_best_mel": "Najniższy val_mel: {value} (epoka {epoch})",
        "chart_help": "**val_mos** - przewidywana naturalność głosu (UTMOS, 1-5) na zdaniach testowych po każdej epoce. Ok. 2 surowy, ok. 3 zrozumiały, 3,5+ dobry; model rzadko przebija własne nagrania („Oceń nagrania” w Narzędziach). **Im wyżej, tym lepiej.**\n**val_mel** - jak bardzo wygenerowany dźwięk (spektrogram mel) różni się od prawdziwego na zdaniach, których model nie widział w treningu. **Im niżej, tym lepiej**; na początku szybko spada, potem prawie stoi - to samo w sobie nie oznacza końca.\n**train_mel** - ten sam błąd na zdaniach treningowych (średnia z epoki). Spada powoli przez cały trening.\n**Kiedy model jest najlepszy:** val_mos przestał rosnąć (płasko przez ok. 150-200 epok), val_mel nie rośnie, a próbki w „Odsłuchu z treningu” brzmią dobrze. Weź checkpoint z najwyższym val_mos z tego okresu.\n**Przetrenowanie:** train_mel dalej spada, a val_mel zaczyna rosnąć - model zapamiętuje zdania zamiast mówić. Weź checkpoint sprzed wzrostu val_mel.",
        "base_not_ready": "**Model bazowy-pl jeszcze nie istnieje na tym komputerze**, więc wybrany jest lessac. Utwórz go przyciskiem **Utwórz model bazowy-pl** (Narzędzia, własna baza) albo trenuj na maszynie, na której już jest.",
        "base_selected": "Baza gotowa: {path}",
        "base_missing": "Model bazowy-pl jeszcze nie istnieje. Kroki: 1. **Przygotuj dataset bazy**, 2. **Trenuj bazę**, 3. wybierz checkpoint i **Użyj jako bazowy-pl**.",
        "error": "Błąd: {error}",
        "status_checking": "Sprawdzam maszynę…",
        "job_remote_running": "Na maszynie trwa **{kind}**{voice}…",
        "machine_ssh_error": "Maszyna z GPU nie odpowiedziała przez SSH: {error}",
        "machine_on": "Maszyna: włączona",
        "machine_off": "Maszyna: wyłączona",
        "machine_starting": "Maszyna: uruchamia się",
        "machine_stopping": "Maszyna: wyłącza się",
        "machine_checking": "Maszyna: sprawdzam…",
        "machine_unknown": "Maszyna: brak odczytu z HA",
        "machine_rejected": "Maszyna: token HA odrzucony",
        "ha_token_rejected": "Home Assistant odrzucił token, więc nic już nie pyta HA (każde odrzucenie to nieudane logowanie dla IP_BAN). Wklej poprawny token albo kliknij „Zapisz połączenie”, aby sprawdzić je jeszcze raz.",
        "ask_cancel": "Anuluj",
        "machine_on_hint": "Kliknij, aby włączyć maszynę z GPU (przełącznik w Home Assistant).",
        "machine_off_hint": "Kliknij, aby bezpiecznie wyłączyć maszynę: Home Assistant wyłączy system, potem gniazdko.",
        "machine_wait_hint": "Poczekaj, aż maszyna skończy się uruchamiać albo wyłączać.",
        "machine_on_confirm": "Włączyć maszynę z GPU? Home Assistant włączy gniazdko, a komputer uruchomi się sam (1–2 min).",
        "machine_off_confirm": "Wyłączyć maszynę z GPU? Home Assistant wyłączy system przez SSH, poczeka, aż gniazdko pokaże spadek mocy, i dopiero wtedy odetnie zasilanie. Gdy maszyna nie wyłączy się w 5 minut, gniazdko zostaje włączone.",
        "machine_switched_on": "Home Assistant włącza maszynę z GPU - uruchomi się w 1–2 minuty.",
        "machine_switched_off": "Home Assistant wyłącza maszynę z GPU - gniazdko wyłączy się, gdy moc spadnie.",
        "ha_title": "Home Assistant",
        "ha_help": (
            "Opcjonalne. Z adresem i tokenem długoterminowym **administratora** Home Assistant na górnym pasku "
            "pojawi się przycisk, który włącza i wyłącza maszynę z GPU i pokazuje jej stan. Token jest tylko na "
            "tym komputerze w `~/.config/piper-voice-cloner/home_assistant.json` (prawa 600), nie w folderze "
            "danych, i nigdy nie wraca na tę stronę."
        ),
        "ha_url": "Adres Home Assistant",
        "ha_token": "Token (długoterminowy, administratora)",
        "ha_token_placeholder": "wklej token",
        "ha_token_saved": "zapisany - wpisz nowy, aby zmienić",
        "ha_save": "Zapisz połączenie",
        "ha_remove": "Usuń połączenie",
        "ha_saved": "Zapisano. Home Assistant odpowiada (encji: {count}).",
        "ha_saved_failed": "Zapisano, ale Home Assistant nie odpowiada: {error}",
        "ha_remove_confirm": "Usunąć adres i token Home Assistant z tego komputera?",
        "ha_removed": "Adres i token Home Assistant usunięte z tego komputera.",
        "ha_missing": "Najpierw ustaw adres i token Home Assistant.",
        "power_title": "Zasilanie maszyny z GPU",
        "power_help": (
            "Przełącznik maszyny w Home Assistant, który sam robi całą pracę: włączenie = gniazdko (BIOS "
            "uruchamia komputer), wyłączenie = system przez SSH, czekanie aż moc spadnie, potem gniazdko "
            "(przykład: `docs/home-assistant/maszyna_gpu.yaml`). Nie samo gniazdko, żeby wyłączenie nie odcięło "
            "prądu działającemu systemowi. Na górnym pasku pojawi się przycisk ze stanem maszyny."
        ),
        "power_switch": "Przełącznik maszyny (np. switch.maszyna_gpu)",
        "power_sensor": "Moc gniazdka w W (np. sensor.…_moc_czynna)",
        "power_watts": "Próg wyłączenia (W)",
        "power_suggest": "↻ Podpowiedzi z HA",
        "power_suggested": "Home Assistant ma przełączników: {switches}, czujników mocy (W): {sensors} - wybierz je z list.",
        "power_save": "Zapisz zasilanie",
        "power_saved": "Zapisano. Przycisk maszyny jest na górnym pasku.",
    },
}


LANGUAGES = list(TEXTS)


def texts(lang: str) -> dict[str, str]:
    return TEXTS.get(lang, TEXTS["en"])


# "?" next to every step: what exactly happens, one bullet per line.
INFO: dict[str, dict[str, str]] = {
    "en": {
        "info_title": "What happens in this step?",
        "info_reference": (
            "The uploaded files are copied to `voices/<voice>/reference/uploads`; your originals are not touched.\n"
            "ffmpeg decodes any format, converts it to mono 24 kHz, trims silence at both ends and levels the volume.\n"
            "The recording is cut into 3–12 s prompts; the cloning model uses them in turn while generating.\n"
            "The CAM++ model computes a voice fingerprint (embedding) from 4 s pieces and stores the average.\n"
            "A similarity threshold is derived from how much the recording itself varies and saved as `quality.min_similarity`; the filter later drops clips below it.\n"
            "Takes a few seconds. Listen to the prompts below: there must be no music or other voices in them."
        ),
        "info_corpus": (
            "Uploaded sentence files are kept in `voices/<voice>/sources`; later runs use every file uploaded so far.\n"
            "Every sentence goes through the plain-text rules: lines with digits, dates, times, list numbering, symbols, abbreviations or addresses are dropped, and so are duplicates.\n"
            "espeak-ng (the same phonemizer Piper uses) turns the sentences into sounds.\n"
            "The selection makes every sound and pair of sounds appear many times, with extra weight on the hard ones.\n"
            "Writes `prompts.tsv` (selected sentences) and `corpus_report.csv` (what was rejected and why).\n"
            "Takes from a few seconds to a minute for large files."
        ),
        "info_audition": (
            "Runs as a background job (see the panel on the right).\n"
            "The cloning model (Chatterbox) is loaded onto the GPU; the first run downloads it (a few GB).\n"
            "For every combination of settings it reads the first sentences, each with a different prompt of your recording.\n"
            "Each clip is checked by Whisper (right text?), CAM++ (same voice?) and UTMOS (natural?).\n"
            "Results appear in the table: pick a combination, listen, then click “Use these settings” to store them in voice.yaml.\n"
            "Takes a few minutes."
        ),
        "info_synthesize": (
            "A background job: the cloning model reads every sentence from prompts.tsv (about 2600 by default).\n"
            "Recording prompts and seeds change from sentence to sentence, so the voice does not get monotone.\n"
            "Every clip is written at once to `raw/` and `manifest.csv`: stopping breaks nothing, running again finishes the missing ones.\n"
            "A failure on one sentence does not stop the run; it is shown in the log.\n"
            "Takes hours for a full set; progress is visible in the log."
        ),
        "info_filter": (
            "A background job: every clip in `raw/` is trimmed, measured and checked.\n"
            "Length vs. text: too fast means cut off, too slow means the model made things up.\n"
            "Whisper large-v3 transcribes the clip; a character error rate above `max_cer` rejects it.\n"
            "CAM++ compares the voice with your recording; below the threshold it is rejected.\n"
            "UTMOS rates naturalness; the worst 10% are dropped. If more clips pass than needed, the most similar ones stay.\n"
            "Writes `dataset/metadata.csv`, `dataset/wav/` (real 22,050 Hz 16-bit WAV) and `filter_report.csv`; the table and samples below show the result.\n"
            "Takes tens of minutes for about 2600 clips."
        ),
        "info_train": (
            "A background job runs Piper training (piper1-gpl) in its own environment.\n"
            "The first start prepares a cache: sounds, silence trimming, spectrograms (a few minutes, longer for large sets).\n"
            "It starts from the chosen base (bazowy-pl, lessac or a checkpoint) and trains the given number of epochs on top of it.\n"
            "Every epoch: validation, `val_mel`, `val_mos` and audio samples in TensorBoard; the best checkpoints are kept automatically (up to about 9 GB per voice).\n"
            "You can stop at any time; the next start resumes from last.ckpt.\n"
            "Duration: see the estimate above the button; usually several hours."
        ),
        "info_export": (
            "A background job turns the chosen checkpoint into an ONNX model: `export/<locale>-<name>-medium.onnx`.\n"
            "Next to it, the training configuration is copied as `.onnx.json` (sample rate, sounds, speaker).\n"
            "Takes under a minute.\n"
            "Then copy both files into the Piper data folder in Home Assistant (Wyoming Piper), restart Piper and pick the voice in the Assist pipeline. Back up an older voice before replacing it."
        ),
        "info_settings": (
            "Saves the ElevenLabs key for all voices, changes the names of this voice and shows its whole voice.yaml.\n"
            "“Save” validates first (types, ranges, known keys); an invalid file is not saved and the message says what is wrong.\n"
            "Changes apply to the next step or job; a job that is already running keeps the old settings."
        ),
        "info_server": (
            "Settings are saved in server.json in your data folder; no password, only the path of the SSH key (login must work without a password: ssh-copy-id).\n"
            "“Prepare machine” checks the machine and does what is missing by itself: packages (when sudo needs no password), uv, sending, install; the Machine checklist shows ✓ done, → Prepare does it, ✋ do it yourself (with the command). “Check machine” only refreshes the list.\n"
            "“Send code and data” uses rsync: the code into ~/<folder>/repo, your voices into ~/<folder>/data. Only changes travel; nothing on the machine is deleted (checkpoints, exports and bases stay).\n"
            "“Install / update” runs scripts/setup.sh there (PyTorch, Chatterbox, Whisper, piper1-gpl, ~15–30 min the first time, minutes later) and the web UI service that starts at boot; the first time the log shows its login.\n"
            "“Bring voices back” copies voices/*/export/ (.onnx + .onnx.json + samples) from the machine to this computer."
        ),
        "info_import": (
            "A background job reads metadata.csv of the old dataset (and the persona file, if given).\n"
            "Persona lines lose their “1. ” numbering, then every sentence goes through the plain-text rules.\n"
            "Audio (MP3 files named .wav too) is decoded into real 22,050 Hz WAV, trimmed and leveled; clips that are too short or too long are dropped.\n"
            "Optionally Whisper checks that the audio matches the text.\n"
            "Writes this voice's dataset and import_report.csv; the old files are not changed."
        ),
        "info_ha": (
            "Address and token go to ~/.config/piper-voice-cloner/home_assistant.json (mode 600) on this computer; PVC_HA_URL / PVC_HA_TOKEN override them. An empty token field keeps the saved token.\n"
            "“Save connection” asks Home Assistant for its entities right away and says whether it answers (401 = wrong token, 403 = not an administrator).\n"
            "“Suggestions from HA” fills the lists with switches and power sensors (W); you can also type an entity id.\n"
            "The top bar asks Home Assistant every ~10 s in the background (never while the page loads): off, starting (on, SSH not answering yet), on · W, shutting down (off, the plug still drawing more than the threshold).\n"
            "Switching off is refused while a job runs on the machine (checked over SSH just before)."
        ),
        "info_base": (
            "“Prepare base dataset”: the same cleaning as the import, for a large single-speaker set, into bases/pl-scratch/dataset.\n"
            "“Train base”: training from random weights, without any checkpoint, so nothing English is inside. Takes days. Model size medium or high (high in bases/pl-scratch-high).\n"
            "“Rate recordings”: UTMOS of a sample of the base recordings - the ceiling of val_mos.\n"
            "“Use as bazowy-pl”: copies the chosen checkpoint to bases/pl-scratch.ckpt; from then on every voice with base bazowy-pl starts from it."
        ),
    },
    "pl": {
        "info_title": "Co się stanie w tym kroku?",
        "info_reference": (
            "Wgrane pliki są kopiowane do `voices/<głos>/reference/uploads`; Twoje oryginały zostają nietknięte.\n"
            "ffmpeg dekoduje dowolny format, zamienia na mono 24 kHz, przycina ciszę na początku i końcu i wyrównuje głośność.\n"
            "Nagranie jest cięte na fragmenty 3–12 s; model klonujący używa ich na zmianę przy generowaniu.\n"
            "Model CAM++ liczy „odcisk głosu” (embedding) z kawałków po 4 s i zapisuje średni wzorzec.\n"
            "Z rozrzutu samego nagrania liczony jest próg podobieństwa i zapisywany jako `quality.min_similarity`; filtr odrzuci później klipy poniżej niego.\n"
            "Trwa kilka sekund. Posłuchaj fragmentów poniżej: nie może w nich być muzyki ani innych głosów."
        ),
        "info_corpus": (
            "Wgrane pliki ze zdaniami zapisują się w `voices/<głos>/sources`; kolejne uruchomienia biorą wszystkie dotychczasowe pliki.\n"
            "Każde zdanie przechodzi reguły zwykłego tekstu: odpadają linie z cyframi, datami, godzinami, numeracją, symbolami, skrótami i adresami, a także duplikaty.\n"
            "espeak-ng (ten sam co w Piperze) zamienia zdania na głoski.\n"
            "Wybór sprawia, że każda głoska i para głosek pojawia się wiele razy, z naciskiem na trudne (sz, cz, rz, ś, ć, ą, ę…).\n"
            "Zapisuje `prompts.tsv` (wybrane zdania) i `corpus_report.csv` (co odrzucono i dlaczego).\n"
            "Trwa od kilku sekund do minuty przy dużych plikach."
        ),
        "info_audition": (
            "Działa jako zadanie w tle (widać je w panelu po prawej).\n"
            "Model klonujący (Chatterbox) ładuje się na kartę graficzną; przy pierwszym uruchomieniu jest pobierany (kilka GB).\n"
            "Dla każdej kombinacji ustawień czyta pierwsze zdania, każde innym fragmentem Twojego nagrania.\n"
            "Każdy klip sprawdza Whisper (czy słychać właściwy tekst), CAM++ (czy to ten sam głos) i UTMOS (czy brzmi naturalnie).\n"
            "Wyniki pojawiają się w tabeli: wybierz kombinację, posłuchaj i kliknij „Użyj tych ustawień”, a trafią do voice.yaml.\n"
            "Trwa kilka minut."
        ),
        "info_synthesize": (
            "Zadanie w tle: model klonujący czyta po kolei wszystkie zdania z prompts.tsv (domyślnie około 2600).\n"
            "Fragmenty nagrania i seedy zmieniają się co zdanie, żeby głos nie był monotonny.\n"
            "Każdy klip od razu zapisuje się do `raw/` i `manifest.csv`: przerwanie niczego nie psuje, ponowne uruchomienie dokończy brakujące.\n"
            "Błąd jednego zdania nie zatrzymuje całości; widać go w logu.\n"
            "Pełny zestaw trwa kilka godzin; postęp widać w logu."
        ),
        "info_filter": (
            "Zadanie w tle: każdy klip z `raw/` jest przycinany, mierzony i sprawdzany.\n"
            "Długość a tekst: za szybko znaczy ucięty, za wolno znaczy, że model coś „dopowiadał”.\n"
            "Whisper large-v3 przepisuje klip; błąd znakowy powyżej `max_cer` go odrzuca.\n"
            "CAM++ porównuje barwę z Twoim nagraniem; poniżej progu klip odpada.\n"
            "UTMOS ocenia naturalność; najgorsze 10% odpada. Jeśli przeszło więcej niż trzeba, zostają najbardziej podobne.\n"
            "Zapisuje `dataset/metadata.csv`, `dataset/wav/` (prawdziwe WAV 22 050 Hz, 16 bit) i `filter_report.csv`; wynik widać w tabeli i próbkach poniżej.\n"
            "Trwa kilkadziesiąt minut dla około 2600 klipów."
        ),
        "info_train": (
            "Zadanie w tle uruchamia trening Piper (piper1-gpl) w osobnym środowisku.\n"
            "Przy pierwszym starcie przygotowuje cache: głoski, przycięcie ciszy, spektrogramy (kilka minut, dłużej przy dużych zbiorach).\n"
            "Startuje od wybranej bazy (bazowy-pl, lessac albo checkpoint) i trenuje podaną liczbę epok ponad nią.\n"
            "Co epokę: walidacja, `val_mel`, `val_mos` i próbki audio w TensorBoard; najlepsze checkpointy zapisują się same (do około 9 GB na głos).\n"
            "Można przerwać w każdej chwili; kolejne uruchomienie wznowi od last.ckpt.\n"
            "Czas: patrz szacunek nad przyciskiem; zwykle kilka–kilkanaście godzin."
        ),
        "info_export": (
            "Zadanie w tle zamienia wybrany checkpoint na model ONNX: `export/<locale>-<nazwa>-medium.onnx`.\n"
            "Obok kopiuje konfigurację z treningu jako `.onnx.json` (częstotliwość, głoski, mówca).\n"
            "Trwa poniżej minuty.\n"
            "Potem skopiuj oba pliki do katalogu danych Pipera w Home Assistant (Wyoming Piper), zrestartuj Pipera i wybierz głos w pipeline Assist. Przed podmianą starego głosu zrób kopię."
        ),
        "info_settings": (
            "Zapisuje klucz ElevenLabs dla wszystkich głosów, zmienia nazwy tego głosu i pokazuje cały plik voice.yaml.\n"
            "„Zapisz” najpierw sprawdza poprawność (typy, zakresy, znane klucze); błędny plik nie zostanie zapisany, a komunikat powie, co jest nie tak.\n"
            "Zmiany działają od następnego kroku lub zadania; już trwające zadanie używa starych ustawień."
        ),
        "info_server": (
            "Ustawienia zapisują się w server.json w Twoim folderze danych; bez hasła, tylko ścieżka klucza SSH (logowanie musi działać bez hasła: ssh-copy-id).\n"
            "„Przygotuj maszynę” sprawdza maszynę i sam robi to, czego brakuje: pakiety (gdy sudo nie pyta o hasło), uv, wysyłkę, instalację; lista Maszyna pokazuje ✓ gotowe, → zrobi Przygotuj, ✋ zrób sam (z gotowym poleceniem). „Sprawdź maszynę” tylko odświeża listę.\n"
            "„Wyślij kod i dane” używa rsync: kod do ~/<folder>/repo, Twoje głosy do ~/<folder>/data. Przesyłane są tylko zmiany; na maszynie nic nie jest usuwane (checkpointy, eksporty i bazy zostają).\n"
            "„Zainstaluj / aktualizuj” uruchamia tam scripts/setup.sh (PyTorch, Chatterbox, Whisper, piper1-gpl; za pierwszym razem ~15–30 min, potem kilka minut) i usługę panelu startującą z systemem; za pierwszym razem log pokaże login.\n"
            "„Pobierz gotowe głosy” kopiuje voices/*/export/ (.onnx + .onnx.json + próbki) z maszyny na ten komputer."
        ),
        "info_import": (
            "Zadanie w tle czyta metadata.csv starego datasetu (i plik persony, jeśli go podasz).\n"
            "W liniach persony usuwana jest numeracja „1. ”, potem każde zdanie przechodzi reguły zwykłego tekstu.\n"
            "Audio (także MP3 nazwane .wav) jest dekodowane do prawdziwego WAV 22 050 Hz, przycinane i wyrównywane; za krótkie i za długie klipy odpadają.\n"
            "Opcjonalnie Whisper sprawdza, czy audio pasuje do tekstu.\n"
            "Zapisuje dataset tego głosu i import_report.csv; stare pliki nie są zmieniane."
        ),
        "info_ha": (
            "Adres i token trafiają do ~/.config/piper-voice-cloner/home_assistant.json (prawa 600) na tym komputerze; PVC_HA_URL / PVC_HA_TOKEN mają pierwszeństwo. Puste pole tokenu zostawia zapisany token.\n"
            "„Zapisz połączenie” od razu pyta Home Assistant o encje i mówi, czy odpowiada (401 = zły token, 403 = to nie administrator).\n"
            "„Podpowiedzi z HA” wypełnia listy przełącznikami i czujnikami mocy (W); identyfikator encji można też wpisać.\n"
            "Górny pasek pyta Home Assistant co ~10 s w tle (nigdy podczas ładowania strony): wyłączona, uruchamia się (włączona, SSH jeszcze nie odpowiada), włączona · W, wyłącza się (wyłączona, a gniazdko wciąż pobiera więcej niż próg).\n"
            "Wyłączenie jest odrzucane, gdy na maszynie trwa zadanie (sprawdzane przez SSH tuż przed)."
        ),
        "info_base": (
            "„Przygotuj dataset bazy”: to samo czyszczenie co przy imporcie, dla dużego zbioru jednego mówcy, do bases/pl-scratch/dataset.\n"
            "„Trenuj bazę”: trening od losowych wag, bez żadnego checkpointu, więc w środku nie ma nic z angielskiego. Trwa kilka dni. Wielkość modelu medium albo high (high w bases/pl-scratch-high).\n"
            "„Oceń nagrania”: UTMOS próbki nagrań bazy - sufit val_mos.\n"
            "„Użyj jako bazowy-pl”: kopiuje wybrany checkpoint do bases/pl-scratch.ckpt; od tej chwili każdy głos z bazą bazowy-pl startuje od niego."
        ),
    },
}
for _code, _values in INFO.items():
    TEXTS[_code].update(_values)
