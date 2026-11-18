# Rate recordings

A Piper voice is never better than its recordings. That is why the editor lets you listen and rate at
several moments. This page shows where, what the numbers mean and what to do with them:

- **before generating** (way A): <span class="ui">Audition</span> – choose the settings of the cloning model;
- **after generating** (way A): <span class="ui">Filter</span> – keep the good clips, drop the bad ones;
- **before the base:** <span class="ui">Rate recordings</span> – how good the base can get at most.

Own recordings (way B) are checked by the import; its result looks like the filter's (see
[Train a voice](guide-train.md#import)).

!!! tip "Your ears decide"
    Every number here is a hint. UTMOS rates how *pleasant* a clip sounds, not whether it sounds like the
    original nor whether the words are right. Always listen to a few clips before you go on.

## 1. Audition: choose the settings (way A) {#audition}

The cloning model (Chatterbox, XTTS-v2) can read with different settings. The audition tries several of
them on a few sentences, so you can pick the best before generating thousands of clips.

![Audition](assets/screens/en/guide-09-audition.png){ .shot }

1. Open the voice → <span class="ui">Audition</span>. The steps <span class="ui">Recording</span> and
   <span class="ui">Sentences</span> must be done.
2. **<span class="ui">Sentences</span>** – how many sentences to try. 12 is enough.
3. Click <span class="ui">Try the settings</span>. It takes a few minutes on the GPU.
4. A table appears: <span class="ui">Settings</span>, <span class="ui">Score</span>, CER,
   <span class="ui">Similarity</span>, MOS. The best score is on top.
5. Click a row and listen. Pick what sounds **most like the original** – not just the top row.
6. Click <span class="ui">Use these settings</span>. They go to `voice.yaml` and the next step uses them.

Nothing sounds right? Improve the recording (a longer, cleaner one) and try again. Bad settings make
thousands of bad clips.

With an ElevenLabs voice the audition is not needed: ElevenLabs reads with its own settings.

## 2. Filter: keep the good clips (way A) {#filter}

After <span class="ui">Generate</span>, every clip is checked. Only the good ones go into the training
set.

![Filter](assets/screens/en/guide-11-filter.png){ .shot }

1. Open the voice → <span class="ui">Filter</span>.
2. **<span class="ui">Clips to keep</span>** – empty means the target of the voice. The hint says how many
   clips were generated.
3. Choose the checks (all three are on by default):
    - <span class="ui">Text (Whisper, CER)</span> – Whisper must hear the right words. Drops garbled and
      cut clips.
    - <span class="ui">Similarity to the recording</span> – drops clips where the model drifted to another
      voice. Needs the speaker embedding from <span class="ui">Recording</span>; with ElevenLabs it has
      nothing to compare with.
    - <span class="ui">Naturalness (UTMOS)</span> – drops the worst-sounding 10%.
4. Click <span class="ui">Filter</span>.
5. Read **<span class="ui">Filter result</span>**: how many clips went into the dataset (here 1449 of
   1496) and a table <span class="ui">Reason</span> – <span class="ui">Clips</span> –
   <span class="ui">What it means</span>. Common reasons:
    - `ok` – kept;
    - `asr_mismatch` – Whisper heard other words;
    - `speaker_mismatch` – it does not sound like the recording;
    - `too_fast_or_cut` / `too_slow_or_hallucinated` – the length does not fit the text;
    - `low_mos` – among the worst sounding;
    - `surplus` – good, but more than needed.
6. Listen to both lists: <span class="ui">Kept clips</span> on the left,
   <span class="ui">Rejected clips</span> on the right (with the reason in brackets).

What to look for:

- **A rejected clip sounds fine** – the filter is too strict for this voice. Example: Whisper writes a
  time like "szósta czterdzieści" differently and counts it as `asr_mismatch`. A few such clips do not
  matter.
- **A kept clip sounds bad** – make the filter stricter in <span class="ui">Voice settings</span>
  (<span class="ui">Max CER</span>, <span class="ui">Drop worst MOS</span>) and filter again. Filtering
  again is quick; the clips stay.

!!! warning "More than about 30% rejected"
    Look for the cause before training: a noisy or short recording, bad audition settings, or sentences
    that are hard to read. Training on what is left gives a weak voice.

## 3. Rate the base recordings {#score}

Before you train the base `bazowy-pl` (see [Train the base voice](guide-base.md)), rate its recordings.
It tells you how good the base can get.

![Rate recordings](assets/screens/en/guide-17-base-score.png){ .shot }

1. First <span class="ui">Base model</span> → <span class="ui">Prepare data</span>.
2. Open <span class="ui">Base model</span> → <span class="ui">Rate recordings</span>.
3. **<span class="ui">Recordings to rate</span>** – 300 is enough for the median; 0 rates all (slow).
4. Click <span class="ui">Rate recordings</span>. It runs on the CPU, about 7 recordings per second,
   so it can run next to a training.
5. Read the four tiles:
    - <span class="ui">Median</span> – the typical recording (here 3.63);
    - <span class="ui">10% weakest below</span> and <span class="ui">10% best above</span> – the spread;
    - **At least 4.0** – the share of very good recordings.
6. Listen to <span class="ui">Weakest recordings</span> and <span class="ui">Best recordings</span>.

**The median is the ceiling.** A trained model rarely sounds better than its recordings. With a median of
3.63, a `val_mos` of about 3.6 in training is already very good – more epochs will not lift it.

The weakest recordings are often short exclamations ("He, he, he!") or single words. When many of them
are noisy or cut off, leave them out of the dataset and prepare the data again.

More: [Base model → Rating the recordings](base-model.md#score).

## 4. Listening during the training {#listening}

The training reads a few test sentences after every epoch. You will find them under
**<span class="ui">Listen to the training</span>** in the training step. How to use them:
[Train a voice](guide-train.md#listen).

Next: [Train a voice](guide-train.md).
