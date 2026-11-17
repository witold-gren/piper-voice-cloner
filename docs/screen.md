# The screen

The editor looks and works like the other studios (Home Dashboard editor, Assist Router editor, the wake
word studio).

![The editor](assets/screens/en/01-overview.png){ .shot }

## The top bar {#top-bar}

From the left:

1. **☰ menu** – the guide, who is logged in and how to change the password, <span class="ui">Log out</span>;
   the icon and the name.
2. **Job chip** – what runs, its percentage and the time left; a click opens <span class="ui">Current job</span>.
3. **Machine chip** – GPU load, temperature, memory, the plug's power; ⏻ switches the machine off (with
   Home Assistant, when nothing runs).
4. **Countdown** after a job with the wish: "Power-off in 1:45" with <span class="ui">Cancel</span>; when
   powering off fails, a red pill with the reason.
5. **Theme**, **?** (this guide – only this "?" opens the guide; the "?" of steps and cards show a small
   window), **⚙** (<span class="ui">Look and language</span>).

![The menu](assets/screens/en/14-menu.png){ .shot }

![The countdown before powering off](assets/screens/en/15-countdown.png){ .shot }

## The tree {#tree}

- <span class="ui">Voices</span> – each voice with the steps of its way; ✓ = done, the number = how much
  (e.g. clips). At the end <span class="ui">Voice settings</span>. "+" makes a new voice (it asks for the
  way first).
- <span class="ui">Base model</span> – everything about the `bazowy-pl` base.
- <span class="ui">Jobs</span> – <span class="ui">Current job</span>, <span class="ui">Training queue</span>,
  <span class="ui">Job history</span>.
- <span class="ui">Settings</span> – ElevenLabs, Home Assistant and the machine, look and language.

Search filters the tree; folds and column widths are remembered by the browser. The left and right
columns fold with ‹ / › at their top or Ctrl/⌘+B (left) and Ctrl/⌘+Alt+B (right): a narrow bar with the
unfold button stays and the middle gets wider. In a narrow window (below 900 px) the right column starts
folded. The page's address
(`#voice/kasia/train`) leads straight to a step – send it or bookmark it.

## The middle and the right column {#columns}

**The middle** is the chosen step: **?** with a short explanation in a small window (and a link to the chapter),
the settings, the button that runs it and the results.

**The right column** is the job live: stage, progress, the GPU, the queue, the log
(<span class="ui">Enlarge</span>, <span class="ui">Copy</span>), <span class="ui">Stop</span> and
<span class="ui">Power the machine off when it ends</span>.

## Voice settings: draft, save, history {#draft}

Every change in <span class="ui">Voice settings</span> goes at once to a **draft on the machine** (it
survives closing the browser); `voice.yaml` changes only on <span class="ui">Save</span>.

- Form or YAML; changing a field changes exactly one line of the file (comments and layout stay).
- <span class="ui">Undo</span> / <span class="ui">Redo</span> (Ctrl/⌘+Z, Shift+Ctrl/⌘+Z); typing in one
  field for 1.5 s is one step.
- <span class="ui">Save</span> (Ctrl/⌘+S) shows the changed lines and a note field. When someone changed the
  file meanwhile, it asks <span class="ui">Save anyway</span>.
- <span class="ui">History</span> keeps 30 earlier versions with their notes; <span class="ui">Bring back</span>
  puts one into the draft.

![Saving with the list of changes](assets/screens/en/16-save.png){ .shot }
