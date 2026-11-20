# Train a voice

Here you take a voice from an empty folder to a trained Piper model. First you build the **dataset**
(about 1500 clips with their text), then you **train**, listen and choose the best moment. Way B gets its
dataset from the import, way A from cloning.

You need a voice first: [Add a new voice](guide-new-voice.md).

## 1. The dataset, way B: import {#import}

![Import](assets/screens/en/guide-06-import.png){ .shot }

1. Prepare the folder: `metadata.csv` (`id|text`, one line per clip) and `wav/` with the clips. The format
   in detail: [Way B: own recordings](path-import.md).
2. Open the voice → <span class="ui">Import</span>.
3. Under **<span class="ui">Where the recordings are</span>** choose one of three:
    - <span class="ui">Folder in the import folder</span> – copy the folder to
      `~/piper-voice-cloner/data/import/` on the machine first; it shows up in the list;
    - <span class="ui">Or the path of the folder</span> – a path as the editor sees it (`/data/…`);
    - <span class="ui">Or send a ZIP</span> – an archive from your computer.
4. Optionally:
    - <span class="ui">Persona file (optional)</span> – when the text is written as a numbered list;
    - <span class="ui">Check every clip with Whisper (slow, uses the GPU)</span> – drops clips whose words
      differ from the text.
5. Click <span class="ui">Import</span>.
6. Read **<span class="ui">Import result</span>** (here 3796 of 3801 clips) and listen to a few
   <span class="ui">Kept clips</span> and <span class="ui">Rejected clips</span>. Lines with digits,
   abbreviations or symbols are always dropped – the voice would learn to read them wrongly.

Done? Go to [step 3: Training](#train).

## 2. The dataset, way A: cloning {#clone}

Five steps, each in the tree under the voice. Details of every step: [Way A: cloning](path-clone.md).

### Recording {#recording}

![Recording](assets/screens/en/guide-07-reference.png){ .shot }

1. Open <span class="ui">Recording</span> and send 10–60 s of clean speech (wav, mp3, m4a). No music, no
   TV, no other people.
2. Leave <span class="ui">Compute the speaker embedding (recommended – the filter compares every clip with it)</span>
   ticked.
3. Click <span class="ui">Prepare the recording</span>.

The voice in the picture (`optimus_prime`) is read by ElevenLabs, so the editor says no recording is
needed – the step counts as done.

### Sentences {#sentences}

![Sentences](assets/screens/en/guide-08-corpus.png){ .shot }

1. Open <span class="ui">Sentences</span>.
2. Send your own text files (one sentence per line) and/or keep
   <span class="ui">Add the bundled sentences (child-friendly, plain Polish)</span>.
3. **<span class="ui">How many sentences</span>** – empty means the target × 1.3 (the filter drops some).
4. Click <span class="ui">Choose the sentences</span>. The first 50 chosen sentences show below.

### Audition {#audition}

Try the settings of the cloning model on a few sentences and pick the best by ear. Step by step:
[Rate recordings → Audition](guide-rate.md#audition). Not needed with ElevenLabs.

### Generate {#generate}

![Generate](assets/screens/en/guide-10-synthesize.png){ .shot }

1. Open <span class="ui">Generate</span>.
2. Choose the **<span class="ui">Cloning model</span>**: <span class="ui">Chatterbox</span> (local, free),
   <span class="ui">XTTS-v2</span> or <span class="ui">ElevenLabs</span> (no GPU, costs credits).
3. With ElevenLabs: <span class="ui">Load voices</span>, choose the <span class="ui">Voice of the account</span>.
   Optionally pick a <span class="ui">Sentence set</span> of an imported voice and click
   <span class="ui">Use this set</span>. The editor shows how many characters (credits) are left to read.
4. **Test first:** type 20 in <span class="ui">Only the first</span> and click
   <span class="ui">Generate clips</span>. Listen to a few clips.
5. Then type 0 (all) and <span class="ui">Generate clips</span> again. Finished clips stay, so you can
   stop and continue whenever you like. The editor shows the pace of the last run and estimates the
   rest.

### Filter {#filter}

Check every clip and keep the good ones. Step by step:
[Rate recordings → Filter](guide-rate.md#filter).

With about 1500 clips in the dataset, go on.

## 3. Training {#train}

![Training](assets/screens/en/guide-12-train.png){ .shot }

1. Open the voice → <span class="ui">Training</span>.
2. **<span class="ui">Start from</span>** – the model the training starts from:
    - `bazowy-pl` – your Polish base. The best choice once you have it ([Train the base voice](guide-base.md));
    - `lessac` – the English Piper voice. Works without a base, learns Polish more slowly;
    - `ckpt:…` – any checkpoint (for experiments).
3. **<span class="ui">Epochs</span>** – for about 1500 clips from `bazowy-pl`: 500–1000. The epochs count
   from the starting checkpoint.
4. Read the estimate below: clips → steps per epoch → seconds per epoch → the whole time on an RTX 4090
   (e.g. “15–21 h”).
5. Tick <span class="ui">Power the machine off when it ends</span> if you train overnight. (Without the
   Home Assistant connection the editor says the box needs it.)
6. Click <span class="ui">Train</span>. A voice that has trained before shows
   <span class="ui">Resume training</span> instead.

The progress is in the job chip at the top and on the right: epochs, the time left, the log. The very
first run prepares its cache for a few minutes before epoch 1.

!!! warning "Resuming or starting over"
    <span class="ui">Resume training</span> continues the voice's own last checkpoint – the
    <span class="ui">Start from</span> field does not matter then (the hint under it says so). The yellow
    note says exactly what happens. Here: the earlier training reached epoch 2111 and the plan ended at
    2113, so only 2 epochs are left. Want more? Enter more epochs. Details:
    [Training → Resuming](training.md#resume).

    Want to train the voice again, e.g. from a new `bazowy-pl`? Choose it in
    <span class="ui">Start from</span> and click <span class="ui">Start over</span>. The editor asks
    first. The earlier checkpoints stay on disk and in the checkpoint list.

### Start over without losing the earlier training {#start-over}

Start over deletes and overwrites nothing.

1. **The checkpoints stay.** The new training goes into a new folder (`lightning_logs/version_1`,
   `_2`…). The old checkpoints (`version_0`) stay in the list in Training and in Export.
2. **The chart and the samples stay.** The chart and the listening of the old training go whole to
   `train/runs/` and are never thinned again. Above the chart the <span class="ui">Training</span> field
   chooses which one to show: <span class="ui">Current training</span> or an earlier one, with its base,
   epochs and best `val_mos`. This works even when both have the same epoch numbers (two starts from the
   same base).
3. **An export never overwrites.** When `pl_PL-meski-medium.onnx` is already there, the next export
   writes `pl_PL-meski_2-medium.onnx`, then `_3`. The hint under <span class="ui">Export</span> shows the
   name the next file gets.
4. Choose the base in <span class="ui">Start from</span> and the epochs. They count from the base (lessac
   starts at about epoch 2164).
5. Click <span class="ui">Start over</span>. From now on <span class="ui">Resume training</span> continues
   only the new training, even when it stopped before its first checkpoint.
6. Liked the old one more? Export its checkpoint from the list (`version_0`). Nothing has to be trained
   again.

The lesson **Start over, keep the old training** (⚙ → <span class="ui">Lessons</span>) shows the same.

<span class="ui">Stop</span> (on the right) ends a training at any time. Resuming later loses a few
epochs at most.

## 4. The chart {#chart}

Below the settings is the **training chart**. It refreshes every 20 s.

- **val_mos** (top, blue): the predicted naturalness of the test sentences, 1–5. **Higher is better.**
  About 3 is understandable, 3.5+ good.
- **val_mel** (bottom, orange): how far the sound is from the real one. **Lower is better.** It falls
  fast at the start, then hardly moves.
- **train_mel** (dashed): the same on the training sentences.
- The green circles mark the best `val_mos` and the lowest `val_mel`.

Click the chart to open it big:

![The chart enlarged](assets/screens/en/guide-13-chart.png){ .shot }

- type the range in <span class="ui">From epoch</span> and <span class="ui">to</span>, or drag over the
  chart to zoom into those epochs; <span class="ui">Whole training</span> zooms out;
- click to pin one epoch and read its values;
- the line at the bottom names the best moments, e.g. "Best quality: 3.93 (epoch 1828)".

How to read it in depth: [Training](training.md).

## 5. Listen and choose the checkpoint {#listen}

Under the chart is **<span class="ui">Listen to the training</span>**.

1. Choose an epoch from the list. At first you hear noise and a robot, later a clearer voice.
2. Epochs marked <span class="ui">💾 checkpoint</span> have a saved model – only those can be exported.
3. <span class="ui">Samples (ZIP)</span> saves all samples to your computer, with a table to sort.
4. **<span class="ui">Checkpoints</span>** below says why each file was kept: the best `val_mos`, the
   lowest `val_mel` or <span class="ui">the newest</span>.

**When to stop:**

- `val_mos` has not risen for about 150–200 epochs, `val_mel` does not rise and the samples sound good;
- `train_mel` keeps falling while `val_mel` rises – overtraining; take a checkpoint from before.

!!! tip "Choose by ear"
    The best `val_mos` does not always sound best. Listen to two or three candidate epochs with the same
    sentences and take the one you like. You can export several and compare them in Home Assistant.

## 6. Several voices overnight: the queue {#queue}

![Training queue](assets/screens/en/guide-22-queue.png){ .shot }

1. Open <span class="ui">Jobs</span> → <span class="ui">Training queue</span>.
2. Under **<span class="ui">Voices with a dataset</span>** tick the voices in the order they should train.
3. Choose <span class="ui">Start from</span> and <span class="ui">Epochs</span> – the same for every voice.
4. Optionally tick <span class="ui">Power the machine off after the last voice</span>.
5. Click <span class="ui">Start the queue</span>.

A failed voice does not stop the next one. <span class="ui">Stop</span> ends the whole queue. In the
morning, <span class="ui">Job history</span> has the log of every voice.

Next: [Export to Home Assistant](guide-export.md).
