# Add a new voice

Here you make a new, empty voice. At the end it is in the tree with the steps of its way, and you know
where its settings are. Before you start, decide where the recordings come from – that decides the way.

## 1. Choose the way {#way}

| Way | Choose it when | Steps in the tree |
|---|---|---|
| **A – cloning** | you have 10–60 s of the voice, **or** the voice is in your ElevenLabs account | Recording, Sentences, Audition, Generate, Filter, Training, Export |
| **B – own recordings** | you have about 1500 clips with their text (`metadata.csv`) | Import, Training, Export |

Not sure? Thousands of clean clips of one speaker are better than any clone – take way B when you have
them.

## 2. Open the "New voice" window {#open}

1. In the tree, click **+** next to <span class="ui">Voices</span>.
2. The <span class="ui">New voice</span> window asks <span class="ui">How do you want to make it?</span>

![New voice – way A, cloning](assets/screens/en/guide-04-new-voice.png){ .shot }

3. Click one of the two cards:
    - <span class="ui">I clone a voice</span> – way A. The editor chooses sentences, makes about
      1500–2000 clips in the voice and checks them.
    - <span class="ui">I already have recordings</span> – way B. Cloning and sentences are skipped:
      import, train, export.

![New voice – way B, own recordings](assets/screens/en/guide-05-new-voice-import.png){ .shot }

The chosen card turns blue.

## 3. Give it a name {#name}

1. **<span class="ui">Name</span>** – type it the way you say it, e.g. `Kuba Bajka`. The editor makes it
   a safe name: lowercase letters, digits and `_`, so it becomes `kuba_bajka`. That is the folder name
   and the name in the tree.
2. **<span class="ui">Piper file name (optional)</span>** – the name of the file Home Assistant will see,
   e.g. `pl_PL-kuba_bajka`. Leave it empty and it becomes `pl_PL-<name>`.
3. Click <span class="ui">Create</span>.

!!! tip "A name you will recognise in Home Assistant"
    The Piper file name is what you will pick from the voice list in Home Assistant. A clear name
    (`pl_PL-kuba_bajka`, not `pl_PL-test3`) saves guessing later.

## 4. What appears in the tree {#tree}

The new voice is in the tree under <span class="ui">Voices</span>, unfolded, with its steps:

- way A: <span class="ui">Recording</span>, <span class="ui">Sentences</span>,
  <span class="ui">Audition</span>, <span class="ui">Generate</span>, <span class="ui">Filter</span>,
  <span class="ui">Training</span>, <span class="ui">Export</span>;
- way B: <span class="ui">Import</span>, <span class="ui">Training</span>, <span class="ui">Export</span>;
- at the end always <span class="ui">Voice settings</span>.

A click on the voice's name shows <span class="ui">The way to a Piper voice</span>: every step, how far
it is and which one is next. A green ✓ next to a step means done; the number next to it says how much
(clips, epochs) or the exported file name.

Go through the steps from the top. How: [Train a voice](guide-train.md).

## 5. Voice settings {#settings}

Every voice has its own settings file (`voice.yaml`). You do not have to touch it – the defaults are
good. Open it when you want a stricter filter, a different number of epochs or a smaller batch.

![Voice settings](assets/screens/en/guide-15-voice-settings.png){ .shot }

1. Click <span class="ui">Voice settings</span> under the voice.
2. Change a field in the <span class="ui">Form</span> tab (or edit the text in the
   **YAML** tab). The sections:
    - <span class="ui">General</span> – <span class="ui">Way</span> and <span class="ui">Target clips</span>;
    - <span class="ui">Generating</span> – <span class="ui">Generate ×</span> (way A);
    - <span class="ui">Filter</span> – <span class="ui">Max CER</span>, <span class="ui">Min similarity</span>,
      <span class="ui">Drop worst MOS</span>, <span class="ui">Min s per character</span>,
      <span class="ui">Max s per character</span> (way A);
    - <span class="ui">Training</span> – <span class="ui">Epochs</span>, <span class="ui">Batch</span>,
      <span class="ui">Data loader processes</span>, <span class="ui">Validation share</span>;
    - <span class="ui">Name and Piper file</span> – <span class="ui">Rename</span> the voice or change its
      Piper file name.
3. Every change goes to a **draft** at once. The status at the top changes from
   <span class="ui">No changes</span> to <span class="ui">Draft saved</span>. The arrows next to it are
   <span class="ui">Undo</span> and <span class="ui">Redo</span>.
4. <span class="ui">Save</span> writes `voice.yaml`. It shows the changed lines first and lets you add a
   note.
5. <span class="ui">History</span> keeps 30 earlier versions. <span class="ui">Bring back</span> puts one
   into the draft; <span class="ui">Save</span> then writes it.

What each field does: [Training → Parameters](training.md#parameters). The draft in detail:
[The screen](screen.md#draft).

!!! warning "Renaming"
    A voice cannot be renamed while it trains. Files exported earlier keep their old names – export
    again after a rename.

!!! note "An imported voice stays imported"
    A way B voice keeps its recordings: it cannot generate new clips. For cloned clips make a new way A
    voice – it can read exactly the sentences of the imported voice (the **Sentence set** in
    <span class="ui">Generate</span>).

Next: [Rate recordings](guide-rate.md) or straight to [Train a voice](guide-train.md).
