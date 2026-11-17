# The common standard

Piper Voice Cloner is one of several home applications that look, install and work the same way. The
others are the wake word studio, the Assist Router trainer, the Home Dashboard editor and the Assist
Router editor. The shared rules are the "gpu-studio" standard.

This page lists everything version 0.2.0 changed to follow that standard. The parts go in the order of
the standard's points.

## In short

| | Before (0.1.0) | Now (0.2.0) |
|---|---|---|
| Panel | Gradio on the Mac, the machine driven over SSH | Editor in the browser, runs on the machine itself |
| Running | systemd services on the machine, manual scripts | Docker, starts with the machine |
| Install and update | `scripts/*` | `make install`, `make deploy` |
| Trying it on a Mac | Python, brew and dependencies | Docker Desktop only: `make demo` |
| Powering off after training | `sudo poweroff` from the runner | The Home Assistant switch, 120 s countdown with Cancel |
| Guide | Two Markdown files | PL/EN site with screenshots, built into the editor |
| Tests | Logic and Gradio panel tests | 328 tests, 1 demo image test, 45 browser tests |

More than 13 thousand lines of old code are gone (the Gradio panel, SSH control, old scripts).

## 1. The main rule

- One application on the machine with the GPU, in Docker. Once the machine is on, the editor is there.
- The Mac is only for trying it (the demo) and for working on the code.
- Removed:
  - the Gradio panel (`webui/`);
  - `pvc ui` and `pvc remote`;
  - controlling the machine from the Mac over SSH and the machine checklist;
  - the power-on button (the editor runs only on a machine that is on);
  - the old systemd services (the installer switches them off).
- Every feature of the old panel is in the editor. Steps that held the panel up (preparing the
  recording, choosing sentences, "Use this set") are ordinary jobs with progress.

## 2. make commands

The same names as in the other applications; `make help` in Polish or English (from `$LANG`). Three
groups:

- **1. Start:** `help`, `demo`, `demo-clean`, `docs`, `docs-serve`, `doctor`. Docker Desktop is enough.
- **2. The GPU machine:** `install`, `deploy`, `login`, `logs`, `status`, `docker-up`, `docker-down`,
  `docker-logs`, `docker-shell`. Docker plus `ssh` and `rsync` from macOS are enough.
- **3. Development:** `setup`, `demo-local`, `test`, `test-browser`, `test-docker`, `test-all`, `lint`,
  `format`, `docs-build`, `screenshots`, `icons`, `clean`.

What else changed:

- The machine's address is shared by every application: `~/.config/gpu-studio/host.mk`. This
  application's exceptions go to `Makefile.local`, which is not in git.
- `make doctor` checks Docker, Chrome, uv and the connection to the machine. It installs nothing.
- `make setup` makes `.venv` with uv (Python 3.12). uv fetches the Python itself; no brew needed.
- `make test` never builds images. `make test-docker` checks the demo image, and `make test-all` runs
  everything.
- The guide builds in Docker: `make docs`, `make docs-build`; `make docs-serve` previews it on port 8861.
  The separate `.venv-docs` is gone.
- No aliases or old names. Every target has a description in both languages, checked by a test.

## 3. Docker

- `docker/Dockerfile` has stages ordered from the least often changed:
  - `base`: Ubuntu 24.04, ffmpeg, espeak-ng, uv, Python 3.11;
  - `train`: piper1-gpl training with torch pinned for driver 580;
  - `docs`: the guide;
  - `deps`: the editor's environment;
  - `app`: the code as the last layer, so a rebuild after a code change takes seconds;
  - `demo`: a separate small image without torch or CUDA.
- Every stage ends with a self-test of its imports.
- `docker/compose.yaml`:
  - services `studio` (the editor) and `tensorboard`;
  - `restart: unless-stopped`, the GPU through nvidia-container-toolkit;
  - data in the machine's folder, secrets in `docker/config/`.
- `docker/install-ubuntu.sh`:
  - checks Docker and the GPU in a container;
  - switches the old services off;
  - makes the password;
  - carries over the existing Home Assistant and ElevenLabs connections;
  - builds and starts the editor.
  - Options: `--show-login` and `--remove`.
- `GET /api/health` serves the container and `make status`.
- A container restart does not leave a job "running": a job without its process becomes "interrupted".

## 4. Login

- One password, a 30-day session in an HttpOnly cookie.
- Five wrong passwords mean a minute's wait.
- The session secret is in a file with mode 600. Changing the password logs everybody out.
- `make login` shows the user and password.
- Log out is in the ☰ menu.

## 5. Look and use

**Look.** The same look as the Home Dashboard editor and the Assist Router editor:

- the same colours (light, dark and auto theme), the tree with search, three columns with splitters;
- icons bundled with the application, so they work offline;
- everything in Polish and English.

**The top bar**, from the left:

- the ☰ menu (guide, who is logged in, log out);
- the job chip and the machine chip (GPU load, temperature, memory, plug power, ⏻);
- the countdown before powering off;
- theme, "?" and ⚙.

**Help.** Only the "?" in the top bar opens the guide. The "?" of steps and cards shows a small window.
Esc, a click beside it, ✕ or "?" again close it.

**Columns.** The side columns fold with a button or Ctrl/⌘+B and Ctrl/⌘+Alt+B. The browser remembers
their state, and in a narrow window the right column starts folded.

**Voice settings:**

- a draft saved at once on the machine;
- changing a field changes exactly one line of `voice.yaml`, and comments stay;
- undo and redo;
- save with the changed lines, a note and a conflict check;
- history of 30 versions.

**Addresses.** The page address (`#voice/kasia/train`) leads straight to a step.

## 6. Home Assistant and powering off

- The machine is always switched off by the switch in Home Assistant. The container never calls
  `sudo poweroff`.
- After a job with the wish ticked, the editor counts down 120 s, and the countdown can be cancelled.
- Never after Stop, also when Stop came while Python was starting.
- A job running beside is finished first. A new job or a restart of the editor drops the countdown.
- ⏻ in the bar works only when nothing runs and Home Assistant is connected.
- When powering off fails, a red pill with the reason appears in the bar.

## 7. Backend

- FastAPI with REST. The standard allows keeping an existing REST API.
- Jobs run in a detached process. Their state is in a locked file, so two writes never overlap.
- A second slot for a side job (scoring recordings) next to training.
- The settings draft, the version history and the conflict check live on the server.

## 8. Documentation

- A MkDocs Material guide in Polish and English, with screenshots from the demo (`make screenshots`).
- Chapters: installation, the screen, both ways, training well, the base model, export, law and the FAQ.
- The guide is on GitHub Pages and in the editor at `/docs/`, also offline.
- Every error met so far has an entry in the [FAQ](faq.md): the exact message, the cause and the fix.
- A test checks that the guide's table of training parameters matches the code.

## 8b. Try it on a Mac

- `make demo` builds a small demo image and runs it at http://localhost:7861 (`demo` / `demo`). Docker
  Desktop is all it needs.
- Everything in the demo is made up: the voices, the GPU and jobs that only pretend to work. Nothing
  goes to Home Assistant, ElevenLabs or the machine.
- Ctrl+C removes the container; `make demo-clean` removes the image.
- The same section is in both READMEs and in the [installation](installation.md#try-on-a-mac).

## 9. Tests and safety

- Tests cannot power off a real machine: powering off is replaced in them. Earlier, one test switched
  off a CI server.
- Tests cannot reach the internet: connections outside localhost are blocked.
- The demo and the screenshots have their own empty settings, so they never see the real Home
  Assistant connection or ElevenLabs key.
- 45 tests in Chrome walk both ways, the settings, the top bar, folding columns, the help windows and
  saving the draft.
- CI checks Python 3.11 (the image's version) and 3.12.

## 9a. Performance

- The editor asks the server for the state one question at a time. The next one goes out only after
  the answer.
- A browser tab in the background asks nothing. Back in front, it asks at once.
- Every request has a time limit (15 s), and no answer ends with a message instead of a hang.
- The view redraws only when the state changed.
- A test on big data (40 voices, 1000 epochs, 120 jobs in the history) checks that no view blocks the
  page for longer than 0.5 s.

## Deliberate differences

- The API stays REST, which the standard allows.
- The image on the machine uses Python 3.11, because Chatterbox and piper1-gpl need that torch. Only
  the programmer uses Python 3.12.
- The YAML, History and Save buttons are in the "Voice settings" view, not in the top bar, because every
  voice has its own settings file.
- No `migrate` and `migrate-finish` (optional in the standard). The installer switches the old services
  off and the data stays in its folder.

## Still to do

A check on the real machine:

- `make install`;
- the GPU in a container;
- a test training of two epochs on a copy of a voice;
- export;
- powering off through Home Assistant with the countdown.
