# Piper Voice Cloner – guide

[Polski](../pl/instrukcja.md) · [HTML](guide.html)

Turn a short recording (10–60 s) into your own fast Piper voice. Example: a cartoon character for
a child's room in Home Assistant.

- [What it does](#what-it-does)
- [Installation](#installation)
- [Web interface](#web-interface)
- [Where the data lives](#where-the-data-lives)
- [1. Record the reference](#1-record-the-reference)
- [2. Sentences](#2-sentences)
- [3. Audition](#3-audition)
- [4. Generate and filter](#4-generate-and-filter)
- [5. Train](#5-train)
- [How long to train and what to watch](#how-long-to-train-and-what-to-watch)
- [6. Export and use](#6-export-and-use)
- [A new voice from a short recording](#a-new-voice-from-a-short-recording)
- [Retraining existing voices](#retraining-existing-voices)
- [Adding a language](#adding-a-language)
- [FAQ and troubleshooting](#faq-and-troubleshooting)
- [Privacy and law](#privacy-and-law)

## What it does

Piper is fast even on a Raspberry Pi or a Jetson, but it can only speak in voices trained for it.
Cloning models (Chatterbox, XTTS) imitate a voice from a few seconds of audio, but they are too
slow for a voice assistant. This tool bridges the two:

| Recording | Cloning | Filter | Training | Export |
|---|---|---|---|---|
| 10–60 s of clean speech | ~2600 clips (Chatterbox) | ~2000 clips (Whisper, timbre, MOS) | medium voice (piper1-gpl) | `.onnx` + `.json` for Home Assistant |

The whole run is a handful of commands:

```bash
pvc init kuba_bajka --piper-name pl_PL-kuba_bajka
pvc reference kuba_bajka recordings/*.m4a
pvc corpus kuba_bajka --source my_sentences.txt
pvc audition kuba_bajka --apply-best
pvc synthesize kuba_bajka
pvc filter kuba_bajka
pvc train kuba_bajka --base lessac
pvc export kuba_bajka
```

## Installation

You need:
- Ubuntu 24.04 with an NVIDIA GeForce RTX 4090 (24 GB). The scripts are prepared for this card only;
  other GPUs and machines are not supported (you may try, but support is up to you).
- `ffmpeg`, `espeak-ng`, `build-essential cmake ninja-build` and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/witold-gren/piper-voice-cloner.git
cd piper-voice-cloner
./scripts/setup.sh                         # .venv (cloning + checks) and .venv-train (piper1-gpl)
export PVC_HOME=$HOME/home-assistant/voices-private # private data lives OUTSIDE the repository
export PVC_TRAIN_PYTHON=$PWD/.venv-train/bin/python
source .venv/bin/activate
```

The script creates two environments, because Chatterbox and Piper training need different
PyTorch versions. `XTTS_ENV=1 ./scripts/setup.sh` also creates a third one for XTTS-v2.

### GPU machine over SSH (working from a Mac or laptop)

You can prepare the data on any computer (import, sentences) and send the code, the data and the
install to the GPU machine with one click: **⚒ Tools → GPU server (SSH)**. The same from a terminal:

```bash
make remote-configure HOST=ubuntu.local SSH_USER=me   # saves server.json in the data folder
make remote-status     # checklist: what the machine has and what is still to do
make remote-prepare    # do everything possible: packages, uv, code and data, environments, service
make remote-push       # rsync: code -> ~/piper-voice-cloner/repo, data -> ~/piper-voice-cloner/data
make remote-install    # setup.sh + the UI service; then http://ubuntu.local:7860
make remote-pull       # finished voices/*/export/ back here
```

- Login must work without a password (SSH key, `ssh-copy-id`). No password is stored anywhere.
- **Prepare machine** checks the machine first and then does what is missing, in order: system
  packages (only when `sudo` on the machine needs no password), `uv`, sending code and data, the
  environments (`setup.sh`) and the web UI service. At the end it checks the machine again.
- The **Machine** checklist below the buttons shows the state: ✓ done, → Prepare does it, ✋ only you
  can do it (e.g. `ssh -t … sudo apt install -y ffmpeg` in the Mac terminal, as it needs the sudo
  password; or the NVIDIA driver and a reboot), ! warning (little disk space, torch does not see the
  card). It also holds the login to the web UI on the machine (**show**).
- While a training runs on the machine, Prepare sends code and data but does not reinstall the
  environments (that would change them under the running training).
- Sending transfers only changes and never deletes anything on the machine: checkpoints, exports and bases stay.
- Then start the training in the web UI on the machine; the Mac can be switched off.

### Power of the GPU machine through Home Assistant

The GPU machine does not have to run all the time. When it sits on a smart plug in Home
Assistant, the web UI can switch it on and shut it down safely with a button in the top bar (the
same as the wake word training panel, home-assistant-wakeword).

1. **In Home Assistant** you need a switch for the machine that does the whole job: on = the plug
   on (the BIOS starts the computer when power comes back; the machine is on Wi-Fi, so no
   Wake-on-LAN), off = `sudo poweroff` over SSH, wait until the plug measures less than 5 W (up to
   5 minutes) and only then the plug off. A ready example:
   [`docs/home-assistant/maszyna_gpu.yaml`](../home-assistant/maszyna_gpu.yaml) (a package with
   `switch.maszyna_gpu` and a script; adapt `shell_command.turn_off_ubuntu` and the entity ids).
   Do not pick the plug itself: switching it off would cut a running system.
2. **In the web UI**: **⚒ Tools → Home Assistant** – the address (e.g.
   `http://homeassistant.local:8123`) and a long-lived token of an **administrator** (Home
   Assistant → your profile → Security → Long-lived access tokens → Create) → **Save connection**.
   The UI asks Home Assistant right away and says whether it answers.
3. Below, in **Power of the GPU machine**: **↻ Suggestions from HA** fills the lists; pick the
   machine's switch (`switch.maszyna_gpu`) and the plug's power sensor in W (e.g.
   `sensor.pokoj_kuby_komputer_moc_czynna`), keep the 5 W threshold → **Save power settings**.
   You can also type an entity id.

The top bar gets a button with the machine's state:

| State | Means | A click |
|---|---|---|
| Machine: off | switch off, the plug below the threshold | asks, switches on |
| Machine: starting | switch on, the SSH port not answering yet | asks, switches off |
| Machine: on · 212 W | switch on, SSH answers; the plug's power next to it | asks, switches off |
| Machine: shutting down | switch off, the plug still drawing more than the threshold | nothing (wait) |
| Machine: checking… | no first answer yet | nothing |
| Machine: no reading from HA | Home Assistant does not answer or refuses; the reason is in the tooltip | nothing |
| Machine: HA token rejected | Home Assistant rejected the token (401); the UI stopped asking HA until the connection is saved | **Save connection** in ⚒ Tools |

- Every click asks for a confirmation first.
- **Switching off is refused while a job runs on the machine** (training, generating, filter…):
  the UI checks it just before, over SSH (`<folder>/data/jobs/current.json` on the machine). Stop
  the job or wait until it ends.
- The address and the token are kept only on this computer, in
  `~/.config/piper-voice-cloner/home_assistant.json` (mode 600), not in the data folder (that one
  is copied to the machine and into backups). The token never comes back to the page; an empty
  token field keeps the saved one. `PVC_HA_URL` and `PVC_HA_TOKEN` override the file. The power
  settings live in the same file, key `"power"`.
- The UI never waits for the machine nor for Home Assistant: the page loads at once and the state
  shows up a moment later (asked in the background about every 10 s; a machine that is off costs
  a 1.5 s connect attempt to its SSH port instead of a 10 s SSH timeout).

## Web interface

Every step of this guide is also available without commands, in the browser:

```bash
pvc ui --lang en              # http://<machine>:7860
./scripts/install-service.sh  # permanently: systemd user service, starts at boot
```

- **Languages**: English at `/en/`, Polish at `/pl/`; the EN | PL switch in the top bar remembers the
  choice. `--lang` only sets the default for the first visit.
- **Live panel**: current stage, elapsed time and the GPU (load, memory, temperature, power), the
  same layout as the wake word training panel.
- **Step bar** at the top: steps 1–7 plus Settings (`voice.yaml`) and Tools (import, own base).
  It is both the progress (✓ = done, ringed number = next step) and the navigation: click a step
  to open it. Every step has a description and a "?" that explains what it does.
- **GPU machine in the top bar**: the power button (with a Home Assistant connection, see
  [Power of the GPU machine through Home Assistant](#power-of-the-gpu-machine-through-home-assistant))
  and the status. With a GPU server saved, the status also shows a job running on the machine
  ("On the machine: Training (kuba) is running…") and, right after the page opens, "Checking the
  machine…".
- **Background jobs**: generating, filtering, training, export and import run in the background.
  The top of the page shows the live log and a "Stop job" button (works like Ctrl+C). One job
  runs at a time, because there is one GPU. Closing the browser or restarting the service does
  not interrupt a job.
- **Remote access**: the service listens on your local network (`0.0.0.0:7860`). The login is in
  `~/.config/piper-voice-cloner/env` (`PVC_UI_AUTH`); the script generates it on first install.
  From outside your home, connect through a VPN such as WireGuard. Don't expose the port to the
  internet.
- **Managing the service**: logs with `journalctl --user -u piper-voice-cloner -f`, restart with
  `systemctl --user restart piper-voice-cloner`, remove with
  `./scripts/install-service.sh --remove`.

## Where the data lives

All private data lives under `$PVC_HOME` (`voices/<name>/`, `bases/`, `models/`). Keep it
outside the repository. If it ends up inside a git repository whose `.gitignore` does not exclude
`voices/`, `pvc` prints a warning.

```
voices/<name>/
  voice.yaml          settings (created by `pvc init`)
  reference/          cleaned reference clips, speaker embedding, calibrated threshold
  prompts.tsv         selected sentences
  audition/           settings comparison (audition.html)
  raw/                synthetic clips + manifest.csv
  dataset/            final training set: metadata.csv + wav/ (22,050 Hz, 16-bit) + reports
  train/              Piper training run (lightning_logs/, config.json, run.json)
  export/             <locale>-<name>-medium.onnx + .onnx.json
```

### Renaming a voice

**⚙ Settings** change the voice name and the Piper file name. The voice name is the folder name, so
the panel moves the whole folder with its clips and settings. It does not work while a job runs on
the voice. The GPU machine keeps the old folder and its training under the old name: after sending,
a new folder without training results appears there. So rename before training, or in the panel on
the machine. Exported files keep their names until the next export.

## 1. Record the reference

- 10–60 seconds of **clean** speech is enough: no music, no background TV, no other voices.
- Close to the microphone, in a quiet room, at normal talking volume. A phone voice memo is fine.
- Natural, varied speech beats reading a list. For a child: let them tell a short story or answer
  questions.
- For a cartoon character: cut lines where the character speaks alone, without music or effects.
  Music in the reference ends up in every generated clip.

```bash
pvc init kuba_bajka --piper-name pl_PL-kuba_bajka
pvc reference kuba_bajka clip1.m4a clip2.wav
```

`pvc reference` trims and level-normalizes the clips and cuts them into prompts of 3–12 s. It
also computes the speaker embedding and stores a **calibrated similarity threshold** in
`voice.yaml` (`quality.min_similarity`). The threshold comes from how much the reference itself
varies. Child voices naturally score lower, and the calibration adapts to that.

## 2. Sentences

```bash
pvc corpus kuba_bajka --source books.txt --source persona_lines.txt
```

- Sources are text files with one sentence per line, or TSV `id<TAB>text`.
- The language pack adds its own sentences: for Polish, simple child-friendly lines.
- Every sentence goes through the plain-text rules. Lines with digits, times, dates, list
  numbering, symbols, URLs or abbreviations are **rejected, not rewritten**. Your voice
  should only learn ordinary words; numbers are read correctly by the runtime text normalizer.
  Writing them out in the training text gives inconsistent pronunciations.
- 3–20 words per sentence, duplicates removed.
- The selection covers phonemes and diphones evenly. By default it picks
  `target_clips × overgenerate` (2000 × 1.3 = 2600) sentences.
- See `corpus_report.csv` for what was rejected and why.

## 3. Audition

```bash
pvc audition kuba_bajka --apply-best
```

- Generates 12 sentences for each combination of backend settings. For Chatterbox the grid is
  `cfg_weight` 0 / 0.3 / 0.5 × `exaggeration` 0.5 / 0.7.
- Writes `audition/audition.html`: listen to each combination and compare CER, similarity and
  MOS.
- `--apply-best` stores the best-scoring settings in `voice.yaml`. Trust your ears over the
  score.
- `cfg_weight` 0 reduces the accent carried over from the reference, which helps when the
  reference is in another language.
- If no combination sounds like the target, fix the reference (cleaner, longer, more varied)
  before generating 2600 clips. Small children's voices are the hardest case for every cloning
  model.

## 4. Generate and filter

```bash
pvc synthesize kuba_bajka            # resumable; reference clips and seeds rotate per sentence
pvc filter kuba_bajka                # Whisper large-v3 + CAM++ + UTMOS
```

A clip is rejected when:

| reason | rule (voice.yaml `quality`) |
|---|---|
| `too_fast_or_cut` / `too_slow_or_hallucinated` | seconds per letter outside 0.035–0.16 |
| `asr_mismatch` | Whisper CER above `max_cer` (0.04) |
| `speaker_mismatch` | similarity below `min_similarity` (calibrated) |
| `low_mos` | in the worst `mos_drop_fraction` (10%) by UTMOS |
| `surplus` | more clips passed than `target_clips`; the most similar ones are kept |

`dataset/filter_report.csv` lists every clip with its scores. If too few clips survive, generate
more by raising `overgenerate` and re-running `pvc corpus` and `pvc synthesize`. Already
generated clips are reused.

## A voice from ElevenLabs (no recording, no GPU)

When the voice already exists in your ElevenLabs account, there is nothing to clone locally.
ElevenLabs reads the sentences in its cloud and the clips land in `raw/` on the computer running
the panel. A Mac is enough for this step: the GPU is needed only for training.

1. **⚙ Settings:** save the API key once, for all voices (file
   `~/.config/piper-voice-cloner/elevenlabs.json`, outside the data folder, so it does not reach the
   GPU machine or backups). The key needs access to voices and text to speech. The `user_read` permission is optional: it shows the credits.
2. **New voice:** enter a name. The cloning model is chosen in Generate, the training start in Train.
3. **Step 4. Generate:** set **Cloning model** to `elevenlabs`, click **Load voices** and pick the
   voice: your voices come first in the list, which you can filter by typing. The panel shows the credits when the key has `user_read`. Do not reuse a voice that already has Chatterbox clips:
   generating refuses to mix two sources.
4. Choose a **Sentence set**, e.g. `marek (1496)`, and click **Use this set**. `marek`, `ewa` and
   `basia` hold the same sentences, so every new voice reads the same set and gets the same clip
   ids.
5. Make a test: enter 20 sentences and listen to the clips in `raw/`. Then set 0 and generate the
   rest. Finished clips are neither generated nor counted again.

The same from the terminal:

```bash
pvc init alicja --backend elevenlabs --base bazowy-pl
pvc elevenlabs voices                 # account voices and credits left
pvc elevenlabs pick alicja <voice_id>
pvc sentences alicja marek           # the sentences of voice marek
pvc synthesize alicja --limit 20     # test
pvc synthesize alicja                # the rest
```

The `marek` set costs about 78,000 characters. `eleven_multilingual_v2` counts about 1 credit per
character; check the current pricing in your ElevenLabs account.

Using a set sets `target_clips` to the number of sentences, `overgenerate` to 1 and
`mos_drop_fraction` to 0: the filter rejects only clips that fail a check, not the weakest 10%.
There is no recording, so the filter skips speaker similarity and prints
`skipped check: similarity`.

When the service is busy or the connection drops, each sentence is retried 5 times. A wrong key, no
credits or an unknown voice stop the whole job; finished clips stay.

## 5. Train

Pick the starting point in `voice.yaml` (`train.base`) or with `--base`:

| base | what it is | when |
|---|---|---|
| `bazowy-pl` | your own base, trained from random weights | no English knowledge inside the voice |
| `lessac` | English `en_US-lessac-medium` (downloaded once, ~850 MB) | fastest good result |
| `ckpt:<path>` | any Piper **medium** checkpoint | e.g. continue from an earlier voice |

```bash
pvc train kuba_bajka                 # resumes automatically from the last checkpoint
pvc train kuba_bajka --dry-run       # only print the piper1-gpl command
```

- `train.max_epochs` counts **on top of** the starting checkpoint. Lightning continues the
  epoch counter of the checkpoint (lessac starts at epoch 2164), and `pvc` accounts for that.
- piper1-gpl keeps the best checkpoints by `val_mel` and by `val_mos` (UTMOS), plus `last.ckpt`.
- Watch training with `tensorboard --logdir voices/<name>/train/lightning_logs`. Choose the final
  checkpoint by listening; `val_mos` is a good hint.

### Your own base without English (`bazowy-pl`)

2000 clips are not enough to train a voice from random weights; that takes roughly 13,000 or more
utterances. So the base is trained **once** on a large single-speaker dataset, and every voice is
then fine-tuned from it.

A good free choice for Polish is **MC Speech**: CC0, one female speaker, about 22,000 recordings
([Kaggle](https://www.kaggle.com/datasets/czyzi0/the-mc-speech-dataset)). Convert it to an
LJSpeech folder (`metadata.csv` with `file|text` plus the audio folder), then:

```bash
pvc base prepare /data/mc_speech --audio-dir /data/mc_speech/wavs   # same text rules as voices
pvc base train --max-epochs 3000                                     # days on a single GPU
pvc base select bases/pl-scratch/train/lightning_logs/version_0/checkpoints/<best>.ckpt
```

After `base select`, `train.base: bazowy-pl` uses it for every voice.

#### Rating the recordings: the quality ceiling of the base

A model learns to sound like its recordings, so the score of the recordings themselves is the
practical ceiling of `val_mos`. In the panel (Tools, own base) click **Rate recordings**. It takes a
random sample (300 recordings by default, `0` = all) and scores it with the same UTMOS that computes
`val_mos`. The panel shows the median, the 10% worst and best limits, the share at 4.0 or more,
and the three worst and best recordings to listen to. When a training run holds the GPU, the rating
runs on the CPU (about 7 recordings/s) next to the training without stopping it. The result is kept
in `bases/pl-scratch/dataset/utmos.json`.

```bash
pvc base score --sample 300      # from the command line; --sample 0 rates every recording
```

If the recordings have a median of e.g. 3.67 and the model is already at `val_mos` 3.55, training
the same base longer gives little. A larger model or cleaner recordings can sound clearly better.

#### Model size: medium or high

- **medium** - Piper's standard: quick to train (about 3 min per epoch with 18,000 recordings on an
  RTX 4090) and quick to speak.
- **high** - the decoder (the part that turns the spectrum into sound) is about 8 times larger:
  14 instead of 1.7 M parameters, as in the official Piper "high" voices. Cleaner sound, but
  training takes about 2-3 times longer and speech on the Jetson is slower. The default batch is 16
  to fit a 24 GB card.

Each size trains in its own folder (`bases/pl-scratch/train` and `bases/pl-scratch-high/train`)
from the **same** recordings with the same test sentences, so they compare fairly. A voice
fine-tuned from a base gets its size automatically (read from the checkpoint), and the export names
the file `…-medium.onnx` or `…-high.onnx`.

```bash
pvc base train --quality high --max-epochs 3000          # batch 16; --batch-size changes it
```

In the panel, **Compare base models** shows for each size the mean `val_mos` and `val_mel` of the
last 10 epochs up to the epoch both models have reached (one epoch is only 5 sentences, so its value
jumps), plus the best values. In **Listen to the training** the **Model** switch plays the same
epoch of both sizes. The medium training can be stopped at any time and resumed later from its
newest checkpoint.

## How long to train and what to watch

> **Estimates for:** RTX 4090 24 GB, Intel Core i9-14900K, 128 GB DDR5 RAM. They are not
> measured with `pvc`. They are based on earlier voices (about 10 h of training per voice on this
> card) and on an assumed 1.5–2 steps per second at `batch_size` 32. The Lightning progress bar
> shows the real speed (`it/s`) after a few minutes of training; recalculate the table with it.

The arithmetic: **steps per epoch = clips × 0.95 ÷ 32**, and **epoch time = steps ÷ steps per
second**. Think in steps rather than epochs: a large dataset needs fewer epochs.

| Job | Clips | Steps per epoch | Epoch time | How long | Total |
|---|---|---|---|---|---|
| New voice (from a base) | 2,000 | ~60 | 30–40 s | 300–1000 epochs (20–60k steps) | 3–11 h |
| Small existing voices | 1,500 | ~45 | 25–30 s | 400–1000 epochs | 3–8 h |
| Medium voice | 3,800 | ~115 | 1–1.3 min | 300–600 epochs | 5–13 h |
| Large voice | 18,400 | ~550 | 5–6 min | 100–250 epochs (55–140k steps) | 9 h – 1 day |
| Base from scratch (MC Speech) | ~22,000 | ~650 | 6–7 min | 500–1000+ epochs (300–600k steps) | 3–7 days |

Hardware notes:
- **The first run** prepares the data into `train/cache/` first: phonemes, silence trimming and
  spectrograms. This takes a few minutes for small voices and tens of minutes for large sets.
  Later runs reuse the cache.
- **`train.num_workers`** is the number of data loader processes, 8 by default. piper1-gpl itself
  defaults to 1, which leaves the GPU waiting for data. The i9-14900K has 8 performance cores, so
  8–12 is a sensible range. 128 GB of RAM is plenty.
- **`batch_size`**: keep 32. 24 GB of VRAM is enough. A larger batch makes epochs faster, but
  changes how fine-tuning behaves. For a base from scratch you can try 48–64 while watching VRAM
  in `nvidia-smi`.
- **Disk**: a checkpoint is about 800 MB. piper1-gpl keeps the 5 best by `val_mel`, the 5 best
  by `val_mos` and `last.ckpt`, so up to about 9 GB per voice, plus the cache (a few GB for
  large sets).
- **Power and heat**: at full load the card draws up to about 450 W, and a base from scratch runs
  for days. Make sure cooling is good. A power limit (`nvidia-smi -pl 350`, needs admin rights)
  lowers the draw at the cost of a few percent of speed.

### Progress in the panel

The **Progress** card on the right shows the running job: its name, time since the start and a bar.

- **Import, filter, generate, base prepare:** a file counter (e.g. `950 / 18400`), the percentage and
  `about … left`. The time left is based on the pace so far, so it is rough in the first minutes.
- **Training (a voice or the base):** the bar covers the **whole training**, not one epoch. For
  example `Epoch 2464 · 25/50 · 300 / 1000 epochs · about 11:40:00 left · 30%`:
  - `Epoch 2464` is Lightning's epoch counter. Starting from lessac or another checkpoint, it
    continues from that checkpoint's number, not from zero.
  - `25/50` are the steps of the current epoch.
  - `300 / 1000 epochs` are the epochs done in this training out of the planned ones
    (`train.max_epochs` in `voice.yaml`, 1000 by default; the base uses `--max-epochs`, 3000 by
    default).
  - **`about … left`** is the length of one epoch, taken from the Lightning bar, applied to the
    epochs still to go. It appears a few seconds into the first epoch. Validation after each epoch
    is not counted, so the real end can be a few percent later.
  - `30%` is the progress of the whole training.
- The first minutes of training prepare `train/cache/`; the bar stays at `0 / … epochs` meanwhile.
- Training does not have to reach 100%. When the TensorBoard samples (below) sound good, stop it
  with **Stop** and pick the best checkpoint. After a resume the bar continues where it stopped.
- Below the bar are the GPU rings (load, memory, temperature, power) from `nvidia-smi`. The panel on
  a Mac without an NVIDIA card does not show them.

### What to watch

**Listening in the panel.** The **Training** tab (for a voice) and **⚒ Tools → Own base** (for the
base) have a **Listen to the training** block: pick an epoch and listen to the test sentences the
trainer reads after every epoch. Every epoch shows its **quality** (val_mos, UTMOS 1–5: about 2 raw,
about 3 understandable, 3.5+ good; a model rarely beats its own recordings - see **Rating the
recordings**) and the best epoch so far. The panel keeps the samples of the first epoch, every 10th,
the 3 newest, the 5 with the best `val_mos` and **every epoch that has a checkpoint** (marked
`💾 checkpoint` in the list). The file `epoch=1273-val_mel=0.3614.ckpt` in **Base checkpoint** is
"epoch 1273 · 💾 checkpoint" in the listening block, so every checkpoint can be heard before choosing.
`last.ckpt` carries its run in front (`version_1/last.ckpt`), since every resume has its own;
**↻ Refresh** fetches new samples.

**Listening at leisure on your computer.** **⬇ Download samples (ZIP)** below the listening block
(of the base or a voice) packs the samples of every kept epoch into one file that the browser saves
on your computer (about 85 MB for the base from kasia). Inside: a folder per epoch with its quality in
the name (`epoch01273-mos3.71-checkpoint/00.wav`, Space in Finder plays it), `samples.csv` and
**`index.html`**: a table with players, sorting by `val_mos` and `val_mel` and a filter "only epochs
with a checkpoint", i.e. only the epochs that can be chosen. From the terminal:
`pvc base samples --quality medium` or `pvc samples <voice>` (file `train/monitor/samples.zip`).

**Chart in the panel.** Below the **Log** (right column) is a chart of the current training: the
upper one shows the quality `val_mos`, the lower one the errors `val_mel` and `train_mel`, sharing the
epoch axis. Hover for the values; click to open it full screen. There, dragging over a chart zooms
into those epochs (or type **From epoch / to**), a click picks an epoch and shows its values, and the
side panel explains the three values and lists the best epochs. The chart follows the training that
runs now (or ran last), otherwise the chosen voice or the base; it refreshes every 20 s.

- **val_mos** - predicted naturalness (UTMOS, 1–5) on the test sentences: **higher is better**.
- **val_mel** - sound error on sentences the model never trained on: **lower is better**.
- **train_mel** - the same error on the training sentences (mean of the epoch); it keeps falling slowly.
- **Best model:** `val_mos` has not risen for about 150–200 epochs, `val_mel` is not rising, the
  samples sound good - take the checkpoint with the highest `val_mos` from that stretch.
- **Overtraining:** `train_mel` keeps falling while `val_mel` rises - take a checkpoint from before.

**Charts in TensorBoard.** A TensorBoard service runs on the machine (installed by **Prepare
machine**, port 6006, setting `PVC_TB_PORT` in `~/.config/piper-voice-cloner/env`). The **Charts in
TensorBoard ↗** link is next to the listening block. TensorBoard has no login - it is reachable in the
local network only (from outside through a VPN). By hand:

```bash
tensorboard --logdir voices/kuba_bajka/train/lightning_logs --bind_all   # http://<machine>:6006
```

| Signal | Meaning | What to expect |
|---|---|---|
| **AUDIO** tab | test sentences rendered after every epoch | **most important**: listen to how the voice develops |
| `val_mos` | predicted naturalness (UTMOS, 1–5 scale) | rises and levels off; the ceiling is the MOS of your training clips (`mos` column in `filter_report.csv`) |
| `val_mel` | spectrogram reconstruction error on the validation set | drops fast and flattens; flattening does **not** mean done, audio quality keeps improving |
| `loss_g`, `loss_d` | generator and discriminator (GAN training) | they oscillate, which is normal; bad sign: `loss_d` falls to about zero while `loss_g` shoots up |

What you hear in the samples:
- **At the start of fine-tuning** you hear the base voice. With 2000 clips the voice usually turns
  into the new one after 50–100 epochs.
- **Metallic, noisy, hissing sound**: too early, keep training.
- **Swallowed or repeated words, wrong pronunciation of specific sounds**: usually a data problem,
  not a time problem. Check `filter_report.csv`, lower `max_cer` and filter again.
- **`val_mel` starts rising while samples sound flat or worse**: overfitting. Pick an earlier
  checkpoint.

When to stop:
- `val_mos` has not improved for about 100 epochs on small voices, or about 30 epochs on large
  sets and bases, **and** the samples sound good.
- You can stop at any time (Ctrl+C). `pvc train` resumes from the newest checkpoint
  (`last.ckpt` or a newer "best" one), so at most a few epochs are repeated.

Choosing the checkpoint:
1. Take the file with the best `val_mos` (`epoch=…-val_mos=….ckpt` in
   `train/lightning_logs/version_*/checkpoints/`).
2. Compare it by ear with `last.ckpt`.
3. Export the one you choose: `pvc export kuba_bajka --checkpoint <file>`.
4. Listen to a dozen sentences that are not in the training set, including numbers and dates
   (your runtime text normalizer reads those).

### Training queue

In the panel on the machine, in the **Train** step, set **Training start** and the epochs. In
**Training queue** pick the voices in the order they should train and click **Start the queue**.
The **Stage** card shows that order and the state of every voice. Every voice gets the same settings. A failed voice does not stop the next ones, and **Stop job** ends
the whole queue. A ticked power-off runs after the last voice. Filter is only needed for voices with
generated clips: imported ones have a ready `dataset/`.

From a terminal:

```bash
pvc train-queue alicja_nowa tomek marek --epochs 500 --base bazowy-pl
```

### Reading the training progress

Example: `557 / 1000 epochs · model epoch 1670 · step 17/112`.

- `557 / 1000 epochs`: the voice's epochs since the base and the limit from the epochs field.
- `model epoch 1670`: the counter including the base's epochs. Checkpoints and **Listen** use this
  number.
- `step 17/112`: the position inside the current epoch.

To train a finished voice further, raise the limit, because it counts from the base. A voice with
500 epochs gets about 500 more only with a limit of 1000. With a limit of 500 the training ends
almost at once.

### Powering the machine off after training

In the **Train** step of the panel on the machine, tick **Power the machine off when training ends**.
When training ends, Ubuntu shuts down with `sudo poweroff`, also after a failed training. The
**Stop job** button does not power it off. The automation in
`docs/home-assistant/maszyna_gpu.yaml` cuts the plug once it draws under 5 W, so in the morning you
only switch the machine on in Home Assistant.

You can change your mind while the job runs. A **Power the machine off when this job ends** box then
shows under the **Stage** card. Tick or untick it and the training carries on. In a training queue
it applies to the end of the whole queue, not to a single voice.

## 6. Export and use

Export turns a checkpoint into a Piper voice. It makes two files and both are needed: `.onnx` is the
model and `.onnx.json` holds its settings.

### Exporting a trained voice

In the panel where the training ran, open step **7. Export**. Choose the checkpoint that sounded best
when listening and run the export. Without a choice `pvc` uses the newest one:

```bash
pvc export kuba_bajka
```

The files land in `voices/kuba_bajka/export/`, e.g. `pl_PL-kuba_bajka-medium.onnx`. The name comes
from the **Piper file name** field.

### Exporting the base voice

Base models live on the GPU machine, so use the panel on that machine:

1. Open **⚒ Tools → Own base without English (bazowy-pl)**.
2. Choose a checkpoint in **Base checkpoint**.
3. Click **Export as a voice**.

The files land in `bases/export/pl_PL-bazowy-medium.onnx` and `.onnx.json`. The same export from a
terminal on the machine, with your own file name:

```bash
cd ~/piper-voice-cloner/repo
PVC_TRAIN_PYTHON=$PWD/.venv-train/bin/python .venv/bin/pvc --root ~/piper-voice-cloner/data \
  base export --name pl_PL-my_base
```

Without `--checkpoint` the export takes the model set as `bazowy-pl`.

### Adding the voice to Home Assistant

The examples are for Wyoming Piper on a separate server. Put in your addresses and the folder with
Piper's `*.onnx` files.

1. **Fetch the files from the GPU machine.** For a trained voice `make remote-pull` is enough. Fetch
   the base voice like this (zsh needs the quotes):

   ```bash
   scp '<user>@<machine>:piper-voice-cloner/data/bases/export/pl_PL-bazowy-medium.onnx*' .
   ```

2. **Copy both files to the Piper server.** Use a new voice name. The same name overwrites a working
   voice, so back it up first.

   ```bash
   scp pl_PL-bazowy-medium.onnx pl_PL-bazowy-medium.onnx.json <user>@<server>:/path/to/piper/models/
   ```

3. **Refresh the voice list in Home Assistant.** Open **Settings → Devices & services → Wyoming
   Protocol** and choose **⋮ → Reload** on the Piper entry. Older Wyoming Piper versions may need a
   restart of the Piper container.
4. **Choose the voice.** Open **Settings → Voice assistants**, choose an assistant and set the new
   voice in its text-to-speech section. This applies to that assistant only.
5. **Check it.** Save the assistant and listen to a reply, or use **Try voice** next to the voice.

To go back, choose the previous voice in the assistant. You can then delete the files on the server.

## A new voice from a short recording

You have one recording, e.g. 15 s, and want a Piper voice from it on about 1500 clips. It works,
but the result depends more on the **quality** of the recording than on its length. The numbers
in this chapter come from a real trial (a film character, two recordings) on a MacBook Pro M1 Max
64 GB.

### Are 15 seconds enough?

- **For cloning, yes.** Chatterbox clones from about 10 s. `pvc reference` cuts 15 s into 1–2
  prompts and warns that the recording is short (under 20 s or a single prompt).
- **A longer recording is better, not required.** 30–60 s of varied speech gives more prompts
  (synthesis rotates them, so the clips are less monotonous) and a steadier similarity threshold
  in the filter. If you can record more, do it before generating 2000 clips, not after.
- **The language of the recording matters.** A Polish recording gives clearly better results than
  an English one. In the trial 8.8 s of Polish speech beat the 33 s English original (table below):
  with a foreign language the Polish clips sound less like the original and the filter drops them
  as `speaker_mismatch`.
- **Sound effects do not carry over.** Reverb, a "robot" effect or background music are either
  lost or dirty every clip. A clean voice is best.
- **A clone of a synthetic voice** (e.g. from ElevenLabs) works technically, but it copies its
  flatness too: Piper trained on such a clone sounds like a clone of a clone.
- **Children's voices** are the hardest case for every cloning model. Here a longer recording
  (60 s) really pays off.

### Trial results

| | 33 s, English original | 8.8 s in Polish (ElevenLabs) |
|---|---|---|
| reference prompts | 3 | 1 |
| best audition settings | `cfg_weight` 0.3, `exaggeration` 0.7 | `cfg_weight` 0, `exaggeration` 0.7 |
| passed the filter (of 50) | **22 (44%)** | **38 (76%)** |
| dropped: other timbre / text error / low quality | 17 / 8 / 3 | 0 / 7 / 5 |
| median similarity, CER, UTMOS | 0.52 · 0.4% · 3.16 | 0.86 · 0.9% · 3.47 |
| sentences for 1500 clips | ~3400 (`overgenerate` 2.3) | ~1950 (default 1.3) |

So: with 76% of the clips passing, the default sentence margin is enough. At 44% raise
`overgenerate` or, better, improve the recording.

### Step by step (target 1500 clips)

1. **New voice**: `pvc init <name>` and set `target_clips: 1500` in `voice.yaml` (panel: New voice
   step).
2. **Recording**: `pvc reference <name> recording.wav`. The short-recording warning is a note, not
   an error.
3. **Sentences**: `pvc corpus <name>` picks `1500 × 1.3 ≈ 1950` sentences (about 2 min).
4. **Audition**: `pvc audition <name> --apply-best` (72 clips). Listen to
   `audition/audition.html`. If no combination sounds like the original, fix the recording now.
5. **Trial**: `pvc synthesize <name> --limit 50`, then `pvc filter <name>`. The end of the
   generation shows the speed (e.g. `50 clips in 19.4 min on mps: 23.2 s per clip`) and the filter
   shows the share that passes. From that you work out how many sentences you need.
6. **Everything**: `pvc synthesize <name>` (can be stopped and resumed) and `pvc filter <name>`.
7. **Training** from `bazowy-pl` on the machine with an NVIDIA card, then **export**.

### Mac or Ubuntu?

An Apple Silicon Mac generates and filters (`make setup-mac`, the Apple GPU through `mps`).
Training Piper needs an NVIDIA card, so it stays on Ubuntu.

| step (1950 sentences) | Mac M1 Max, measured | Ubuntu RTX 4090, estimate |
|---|---|---|
| recording + sentences | ~2 min | ~2 min |
| audition (72 clips) | 50–110 min | ~15 min |
| generation | 23 s per clip → **~12.5 h** | ~3 s per clip → ~1.5–2 h |
| filter (Whisper on the CPU on a Mac) | 7 s per clip → **~3.8 h** | ~1 s per clip → ~0.5 h |
| training from `bazowy-pl` (1500 clips) | not possible | 3–8 h |

The Ubuntu column is an estimate; it will be replaced by a measurement once the card is free from
the base training.

- **The Mac makes sense** when the card trains something else (e.g. a base for several days):
  generate on the Mac overnight and send the finished set to the machine (`pvc remote push`) only
  for training.
- **Ubuntu is several times faster** when the card is free.
- Do not run two cloning models at once on the Mac: memory runs out and the system kills the
  process (exit code 137). The generation can simply be resumed then.

### How long it takes in total

- **Your work**: preparing the recording and listening take 30–60 min. The rest runs by itself.
- **Mac + Ubuntu**: ~17 h of generation and filtering on the Mac, then 3–8 h of training, i.e.
  1–1.5 days.
- **Ubuntu alone**: ~2–3 h of generation and filtering plus 3–8 h of training, about a day with
  time to listen and pick a checkpoint.

### Limits and law

- Every Chatterbox clip carries the inaudible Resemble Perth watermark. It marks speech as
  generated; it does not change the sound and does not disturb training.
- A real person's voice only with their consent; a child's voice with a parent's or guardian's
  consent.
- Film and cartoon characters: private home use only. See [Privacy and law](#privacy-and-law).

## Retraining existing voices

Old datasets often contain lines with digits, dates or list numbering, and MP3 audio saved with a
`.wav` name. `pvc import` cleans them with the same rules:

```bash
pvc init kasia --piper-name pl_PL-kasia_glos     # keep the old file name
pvc import kasia /old/pl_PL-kasia_glos-medium \
  --metadata /old/pl_PL-kasia_glos-medium/metadata.csv \
  --persona /old/pl_PL-kasia_glos-medium/custom_metadata.csv   # numbered lists: "1. ..."
pvc train kasia --base bazowy-pl
pvc export kasia
```

- `--persona` files have their list numbering removed before the text check.
- Short replies ("Will you sit down?") are kept; long sentences are limited by the 20 s audio cap.
- `--verify` also runs every clip through Whisper (slow).
- Keep the old `.onnx` files as a backup before replacing them.

## Adding a language

Create `piper_voice_cloner/languages/<code>.py` with a `PACK = LanguagePack(...)`:
- `espeak_voice`: the espeak-ng voice Piper should use (e.g. `cs`);
- `locale`: the file name prefix (e.g. `cs_CZ`);
- `synth_language`: the language code for the cloning backend and Whisper;
- `extra_letters`: letters besides a–z (e.g. `áčďéěíňóřšťúůýž`);
- `abbreviations`: abbreviations to reject;
- `focus_phonemes`: sounds to cover generously;
- `prompt_files`: optional bundled sentences in `languages/data/`.

Then `pvc init <name> --language <code>`. Check that the cloning backend supports the language;
Chatterbox lists 23.

## FAQ and troubleshooting

Search for the message (Ctrl+F). The full job log is in the panel on the right and in
`<data>/jobs/*.log`.

### Filter: `no generated clips in …/raw: nothing to filter`

An imported voice has no generated clips and its `dataset/` is ready for training. Skip Filter. Older
versions emptied `dataset/` here. If that happened on the machine, **⚒ Tools → Prepare machine**
restores the set from the computer that sent it.

### Export: `No module named 'onnxscript'` or `GuardOnDataDependentSymNode`

The training environment lacked the ONNX packages, and PyTorch's new exporter does not handle this
model. Click **Prepare machine** and export again: the cloner uses the older exporter.

### Listening: `ElevenLabsFatalError: no API key` in the panel on the machine

The ElevenLabs key lives on the computer where it was entered. Generate clips on the Mac. Skip the
**Audition** step: for an ElevenLabs voice it uses credits and training does not need it.

### `'piotr' is an imported voice: create a new voice to generate clips`

An imported voice is a finished recording set and a source of sentences, so it does not generate new
clips. Create a new voice and choose the model and sentence set there. The message below the set
always names the selected voice.

### After restarting `make ui`: `An event handler (run_export) didn't receive enough input values`

A tab opened before the panel update sent its timer events in the old layout, and in the new one
those numbers belong to other functions. `Value: '…' is not in the list of choices: []` has the same
cause. The panel rejects these events and no job starts. Refresh the tab (Cmd+R). After updating the
code it is best to close old tabs before starting the panel.

### Generate: `Stopped: HTTP 401: …` (`quota_exceeded`, `invalid_api_key`)

Code 401 means a wrong key or no credits; the response says which. Save a new key in Settings
or buy credits, then run generating again. Finished clips stay.

### Load voices: `HTTP 401: … missing_permissions`

A restricted key has no access to voices. Enable this permission for the key in ElevenLabs or create
a new one. Missing `user_read` alone is not an error: the voices load, only without the credits.

### Generate: `Stopped: raw/ holds clips of another voice (…)`

`raw/` holds clips of another model or another ElevenLabs voice. Create a new voice in the panel or
move `raw/` out of the voice folder.

### Use this set: `raw/ already holds … clips of other sentences`

The voice already has clips of other sentences and the filter would use them with the new ones.
Create a new voice.

### `voice name: lowercase letters, digits and '_' only`

A voice name may only contain lowercase letters, digits and `_`. The web UI turns `Tomek` into
`tomek` and `Kuba Bajka` into `kuba_bajka` by itself; you only see this in an older version or
in `pvc init`. Type the name in lowercase.

### `make ui`: `python3.11 not found`

An older Makefile rebuilt the environment after every change of `pyproject.toml` and demanded
`python3.11` even when `.venv` already existed (e.g. on Python 3.12). Fixed: an existing `.venv`
is only refreshed with its own Python, a new one is made with `python3.11` or `python3.12`. If
neither exists: `brew install python@3.12` (macOS) or `uv python install 3.11` (Ubuntu).

### I can't see the Tools or Settings tabs

Every step is in the bar at the top; click **⚙ Settings** or **⚒ Tools** at its end. Older
versions hid them under "⋯" on the right of the tabs.

### What goes into "Persona metadata file"?

The name of an extra file with lines written as a numbered list ("1. …") that sits next to
`metadata.csv`, e.g. `custom_metadata.csv`. If there is no such file, leave it empty. Don't give
files with only times or dates (e.g. `ha_metadata.csv`): the filter drops every line with digits
anyway.

### The import dropped some clips

The reason for each one is in `voices/<voice>/dataset/import_report.csv`. `duration` is a clip
shorter than ~0.6 s or too long; `text:digits` / `text:abbreviation` / `text:foreign_characters`
is text that would spoil the pronunciation. A few per thousand is normal.

### The panel says "no NVIDIA card"

Normal on a Mac or a computer without an NVIDIA card: import, sentences and settings work, but
generating, the Whisper filter and training need the card. Use the [GPU machine over
SSH](#gpu-machine-over-ssh-working-from-a-mac-or-laptop).

### Ctrl+C does not stop `make ui`

Older versions waited for the browser to close its connection, i.e. forever. Update the code; it
now exits after 2–4 s. If an old version hangs: close the panel tab or `pkill -f "pvc.*ui"`.
Background jobs (training) are separate processes and survive the panel.

### Nothing happens after a click, no progress

Long steps run in the background. Progress (bar and counter) and the log are in the card on the
right; "Stop job" is only active while something runs. When it ends the card shows "Last job …
finished / failed" and the time it took. One job runs at a time.

### `Value: kasia is not in the list of choices: []` in the `make ui` terminal

The browser tab remembered the chosen voice from an earlier run of the panel (e.g. before restarting
`make ui` or changing the data folder) and the new session did not list it. Nothing broke: the data is
on the disk. Reload the page (Cmd+R) or click **↻ Refresh** next to the voice list. Newer versions no
longer print this error; a voice that is not on the disk counts as not chosen.

### "… is still running. Wait until it ends" (formerly `Another job is still running: … is still running`)

One job runs at a time and another was clicked before the first one ended, for example "Send code
and data" right after "Check". Wait until the **Progress** card shows "Last job …" or stop the job,
then click again. Older versions also printed a long `Traceback … JobBusy` in the `make ui`
terminal; it was this message, not a crash.

### Check connection: `ssh: connect to host … port 22: Network is unreachable` or `Operation timed out`

The GPU machine is off or the Mac has no route to it. Away from home, check the VPN (WireGuard); at
home, check that the machine is running (the machine button in the top bar, if Home Assistant is
set up). After switching it on wait 1–2 minutes and click **Check** again.

In the top bar this error shows as "Server: connection check failed (exit code 255)". It is the
result of the last job, not the current state. When the machine answers over SSH again (the panel
asks it about every 10 s), the bar changes by itself to "Server answers over SSH again". Other
failures, e.g. a failed install (exit code 1), stay visible until the next job.

### Training stops after the first epoch: `ModelCheckpoint(monitor='val_mos') could not find the monitored key`

The training environment lacks `torchaudio`, so piper does not compute the quality (`val_mos`) and
the checkpoint saving waits for it. The log shows `Could not load MOS predictor 'utmos' (No module
named 'torchaudio')` earlier. Click **Prepare machine** (the checklist shows "Training environment"
to do) or on the machine: `uv pip install --python .venv-train/bin/python torchaudio`. Then start the
training again - it resumes from the last checkpoint.

### Audition or generation: `TypeError: 'NoneType' object is not callable` (`perth.PerthImplicitWatermarker()`)

Chatterbox adds an inaudible watermark from the `resemble-perth` library to every clip. That library
imports `pkg_resources`, which `setuptools` no longer ships since version 81. When the import fails,
`perth` silently sets the watermarker to `None`, so the model fails as it starts. Since this version
the `chatterbox` extra pins `setuptools<81` and the setup checks the watermark. In an older
environment: `.venv/bin/pip install 'setuptools<81'` (on the machine: click **Prepare machine** while
nothing trains, or `uv pip install --python .venv/bin/python 'setuptools<81'`).

### The filter drops almost everything as `too_fast_or_cut`, the log says `forcing EOS token, … token_repetition=True`

Clips stop after a few words (e.g. 2 s instead of 11 s) and the generation log shows
`🚨 Detected 2x repetition of token …` and `forcing EOS token`. Chatterbox 0.1.7 ends the speech
when two equal speech tokens follow each other anywhere in the clip. Low, drawn-out voices (e.g. a
film character) hit it almost every time, and the 12-sentence audition may not show it. Since this
version the app checks for repetitions only after the whole text is spoken, so loops at the end are
still stopped. A bad batch from an older version: remove the voice's `raw/` and `dataset/` (or move
them aside) and generate the clips again.

### Training again after a finished run: `You restored a checkpoint with current_epoch=1273, but you have set Trainer(max_epochs=800)`

The base (or voice) training finished its planned epochs, then **Train base** was clicked again with
fewer epochs. Resuming starts from the newest checkpoint (here epoch 1273), and older versions
counted the epochs from the start of the first run (0 + 800 = 800). Lightning refuses to end below
the checkpoint's epoch. Since this version, when the plan is already done, the **Epochs** field
means "how many more": 800 epochs from 1273 to 2073 (the log says `The planned … epochs are done
…; training 800 more`). A stopped, unfinished training still resumes up to its original end.

Note: piper saves a checkpoint only when `val_mel`/`val_mos` improve, so the last epochs without an
improvement (e.g. 1274–1299) have no checkpoint and resuming starts from the last saved one. About
the size: **medium** continues the same model, **high** starts a separate training in
`bases/pl-scratch-high`.

### Training stops after many epochs: `torch.OutOfMemoryError: CUDA out of memory`

The GPU (24 GB) ran out of memory. A batch is padded to its longest clip, so memory use jumps from
batch to batch. A rare batch with several long clips (15-20 s) plus a fragmented CUDA cache goes over
the limit, sometimes only after hundreds of epochs. Nothing is lost: click **Train base** (or
**Train**) again. Training resumes from the newest checkpoint (`last.ckpt` or a newer
"best" one), so at most a few epochs are repeated. Since this version
training runs with `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`, which limits fragmentation
(after updating, click **Prepare machine**). If the error comes back, lower the batch:
`pvc base train --batch-size 24`.

### Check connection: `Permission denied (publickey)` or `Host key verification failed`

Login to the machine must work without a password. Once, in a terminal:

```bash
ssh-copy-id user@ubuntu.local   # copies your key to the machine
ssh user@ubuntu.local           # first connection: accept the host key (yes)
```

If you use a key other than the default one, pick it in **SSH key**.

### Check connection: `ffmpeg: MISSING` (or another tool)

System packages you install once yourself on the machine (they need sudo). The end of the output
has the command, e.g.:

```bash
ssh user@ubuntu.local
sudo apt install ffmpeg
```

Missing `uv`: `curl -LsSf https://astral.sh/uv/install.sh | sh`.

### Install: `ModuleNotFoundError: No module named 'Cython'` (`~/.local/bin/cythonize`)

An older `setup.sh` ran `cythonize` from another Python. Fixed: click **Send code and data**,
then **Install / update**. The second run takes minutes because the packages are already
downloaded.

### Install: `No module named 'skbuild'` or `cannot import name 'espeakbridge'`

The espeak-ng bridge was not compiled in the training environment. Fixed in `setup.sh` as above:
**Send code and data** → **Install / update**. At the end the install checks that both piper1-gpl
modules import.

### Red status "Server: installing (-) failed (exit code 1)"

The status at the top shows the **last** job, so it stays red until you start another one. Read
the end of the log (on the right or `<data>/jobs/*-remote-install.log`), find the message in this
FAQ, and after the fix run **Send code and data** and **Install / update** again. The install can
be repeated safely.

### I lost the login of the panel on the machine

It is in `~/.config/piper-voice-cloner/env` on the machine (`PVC_UI_AUTH=admin:password`). Change
it and restart the service:

```bash
nano ~/.config/piper-voice-cloner/env
systemctl --user restart piper-voice-cloner
```

### "Machine: no reading from HA"

**Symptom**: a red "Machine: no reading from HA" button in the top bar; its tooltip gives the
reason, e.g. `Home Assistant at http://homeassistant.local:8123 cannot be reached: timed out` or
`Home Assistant 404: Entity not found.`

**Cause**: the UI did not get the machine switch's state from Home Assistant: Home Assistant is
off or restarting, the address is wrong, the token expired (401/403, below) or an entity of the
settings does not exist (404, `unavailable`).

**Fix**: check the address in **⚒ Tools → Home Assistant** and click **Save connection** (it says
at once whether Home Assistant answers). On 404 click **↻ Suggestions from HA** and pick an
existing switch and sensor. The state refreshes by itself about every 10 s.

### "Machine: HA token rejected"

**Symptom**: a red "Machine: HA token rejected" button in the top bar, and "Home Assistant rejected
the token…" in the token field of **⚒ Tools → Home Assistant**.

**Cause**: Home Assistant answered 401 (a wrong, expired or deleted token). Each such answer is a
failed login for HA, and with `ip_ban` on HA blocks the address after a few of them (through a VPN
this may be the Jetson's address). So the UI **stops asking HA after the first rejection**: machine
state, entity suggestions and switching the machine.

**Fix**: paste a new long-lived token (profile → Security) and click **Save connection**. When the
token is fine and HA was e.g. restarting, **Save connection** alone is enough: the UI checks the
connection with one request.

### `Home Assistant 401: the token is wrong or expired` / `Home Assistant 403: the token belongs to a user who is not an administrator`

**Symptom**: the message after **Save connection**, **↻ Suggestions from HA** or a click on the
machine button.

**Cause**: 401 – the token is wrong, expired or was deleted in the profile. 403 – the token
belongs to a user who is not an administrator (switching needs that).

**Fix**: in Home Assistant log in as an administrator → profile → Security → Long-lived access
tokens → Create; paste the new token in **⚒ Tools → Home Assistant** and save.

### `this does not look like a Home Assistant long-lived token` / `Home Assistant address: e.g. http://homeassistant.local:8123`

**Cause**: the pasted token has spaces or quotes or is cut off (a token is a long string of
letters, digits, `.`, `_`, `-`); the address does not start with `http://` or `https://` or has
a path.

**Fix**: copy the token again in full; type the address as `http://<host>:8123` with nothing
after the port. The message deliberately never shows the typed token.

### `a job is running on the machine: … - stop it first or wait until it ends`

**Symptom**: after clicking "Machine: on" and confirming, this error shows and the machine stays
on.

**Cause**: a job of the web UI runs on the machine (e.g. `train (kuba)`) or the UI on this
computer is sending code to it or installing (`remote-push`, `remote-install`). Switching off
would break it.

**Fix**: wait until the job ends or stop it with **Stop job** (in the web UI on the machine when
the job runs there) and try again. Training resumes later from the newest checkpoint.

### The UI loads slowly or shows "Checking the machine…" for long

**Symptom**: after opening the UI the status "Checking the machine…" / "Machine: checking…" stays
for more than a few seconds.

**Cause**: the GPU machine is off or does not answer and Home Assistant answers slowly or not at
all. The page itself never waits for them (they are asked in the background): the first state
shows after about 1.5 s (a connect attempt to the SSH port), the Home Assistant state after a few
seconds at most (5 s limit per request). The slow `homeassistant.local` answers on a Mac (5 s
waiting for an IPv6 answer on every request) are avoided: the name is looked up once, IPv4 first,
and kept for 5 minutes.

**Fix**: usually nothing – the state shows up by itself. If "checking" never goes away, restart
the UI and read the tooltip of the status. When it says `The GPU machine did not answer over SSH:
…`, the machine is on but the SSH login fails – see
[Check connection: Permission denied (publickey)](#check-connection-permission-denied-publickey-or-host-key-verification-failed).

## Privacy and law

- **Children's voices**: record and use them only with a parent's or guardian's consent, and keep
  everything local. The default backend runs entirely on your machine. ElevenLabs sends text to
  the cloud and the tool says so whenever it is used.
- **Cartoon and film characters**: the recordings are copyrighted, and voice actors have rights to
  their voice and performance. Keep such voices for private use. Don't publish the model or its
  samples, and never use them commercially.
- **Model licenses**: Chatterbox is MIT. XTTS-v2 is CPML, which is non-commercial, so treat its
  outputs and voices trained on them as non-commercial too. Chatterbox adds an inaudible
  watermark (Resemble Perth) to everything it generates.
- If you ever publish synthetic speech, label it as AI-generated (EU AI Act, Art. 50).

This is not legal advice.
