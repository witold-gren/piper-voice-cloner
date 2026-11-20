// The lessons of the editor: every task of the step-by-step guide as a short tour (tour.js) that goes where the
// task is done and frames one part at a time. A step can choose a node of the tree first (`prepare`) and wait
// for the framed button to be clicked (`advance: "click"`). Buttons that start a long job (a training, the
// clips) are framed and explained, never waited for: the lesson ends there and the person starts it when ready.
// The list (⚙ → Lessons) marks the ones gone through; a lesson that needs a voice of a kind says which.
import { LitElement, css, html, nothing } from "./vendor/lit-all.min.js";
import { translate } from "./i18n.js";
import { dialogStyles } from "./styles.js";
import { lessonsDone } from "./tour.js";
import "./icon.js";

/** The voice a lesson of a step works on: the open one when it has that step, else the first that has. */
export function voiceFor(app, step) {
  const voices = app?._state?.voices ?? [];
  const has = (voice) => voice.steps?.some((item) => item.key === step);
  const open = voices.find((voice) => voice.name === app?._currentVoice?.());
  return open && has(open) ? open : voices.find(has) ?? null;
}

const chooseStep = (step) => (app) => {
  const voice = voiceFor(app, step);
  if (voice) app._select(`voice/${voice.name}/${step}`);
};
const choose = (key) => (app) => app?._select?.(key);
const chooseSettings = (app) => {
  const voice = voiceFor(app, "train");
  if (voice) app._select(`voice/${voice.name}/settings`);
};
// a cloned voice's settings (the lesson of the clone and the filter settings)
const chooseCloneSettings = (app) => {
  const voice = voiceFor(app, "reference");
  if (voice) app._select(`voice/${voice.name}/settings`);
};
const field = (key) => `[data-field='${key}']`;
// the voice itself in the tree (its steps say how far its data got)
const voiceNode = (step) => (app) => {
  const voice = voiceFor(app, step);
  return voice ? [`[data-node='voice/${voice.name}']`] : [];
};
const node = (step) => (app) => {
  const voice = voiceFor(app, step);
  return voice ? [`[data-node='voice/${voice.name}/${step}']`] : [];
};

// what a lesson needs, and whether the editor has it
const NEEDS = {
  clone: (app) => Boolean(voiceFor(app, "reference")),
  import: (app) => Boolean(voiceFor(app, "import")),
  voice: (app) => Boolean(voiceFor(app, "train")),
};

export const lessonReady = (lesson, app) => !lesson.needs || NEEDS[lesson.needs](app);

// the first steps of making a voice, the same for both ways
const newVoice = (workflow) => [
  { key: "button", targets: ["[data-new-voice-button]"], side: "right", advance: "click" },
  { key: "way", targets: [`pvc-new-voice >>> [data-workflow='${workflow}']`], side: "right", advance: "click" },
  { key: "name", targets: ["pvc-new-voice >>> [data-new-name]", "pvc-new-voice >>> [data-new-piper]"], side: "right", interact: true },
  { key: "create", targets: ["pvc-new-voice >>> [data-new-create]"], side: "right", advance: "click" },
  { key: "steps", targets: ["[data-tree]"], side: "right" },
];

export const LESSONS = [
  // to start with
  { key: "new_clone", icon: "mdi:account-voice", group: "start", steps: newVoice("clone") },
  { key: "new_import", icon: "mdi:folder-music", group: "start", steps: newVoice("import") },
  {
    key: "reference",
    icon: "mdi:microphone",
    group: "start",
    needs: "clone",
    steps: [
      { key: "node", targets: node("reference"), side: "right", prepare: chooseStep("reference") },
      { key: "upload", targets: ["[data-reference-upload]"], side: "left" },
      { key: "elevenlabs", targets: ["[data-reference-elevenlabs]"], fallback: ["[data-middle]"], side: "left" },
      { key: "run", targets: ["[data-run-reference]"], side: "left" },
      { key: "result", targets: ["[data-reference-result]"], fallback: ["[data-middle]"], side: "left" },
    ],
  },
  {
    key: "corpus",
    icon: "mdi:text-box-outline",
    group: "start",
    needs: "clone",
    steps: [
      { key: "node", targets: node("corpus"), side: "right", prepare: chooseStep("corpus") },
      { key: "size", targets: ["[data-corpus-size]"], side: "left" },
      { key: "own", targets: ["[data-corpus-upload]"], fallback: ["[data-middle]"], side: "left" },
      { key: "run", targets: ["[data-run-corpus]"], side: "left" },
      { key: "preview", targets: ["[data-corpus-preview]"], fallback: ["[data-middle]"], side: "left" },
    ],
  },
  {
    key: "audition",
    icon: "mdi:headphones",
    group: "start",
    needs: "clone",
    steps: [
      { key: "node", targets: node("audition"), side: "right", prepare: chooseStep("audition") },
      { key: "run", targets: ["[data-run-audition]"], side: "left" },
      { key: "results", targets: ["[data-audition-results]"], fallback: ["[data-middle]"], side: "left" },
      { key: "apply", targets: ["[data-audition-apply]"], fallback: ["[data-middle]"], side: "left" },
    ],
  },
  {
    key: "synthesize",
    icon: "mdi:waveform",
    group: "start",
    needs: "clone",
    steps: [
      { key: "node", targets: node("synthesize"), side: "right", prepare: chooseStep("synthesize") },
      { key: "backend", targets: ["[data-backend]"], side: "left" },
      { key: "count", targets: ["[data-synthesize-count]", "[data-synthesize-limit]"], fallback: ["[data-middle]"], side: "left" },
      { key: "timing", targets: ["[data-synthesize-timing]"], fallback: ["[data-middle]"], side: "left" },
      { key: "run", targets: ["[data-run-synthesize]"], side: "left" },
    ],
  },
  {
    key: "filter",
    icon: "mdi:filter-outline",
    group: "start",
    needs: "clone",
    steps: [
      { key: "node", targets: node("filter"), side: "right", prepare: chooseStep("filter") },
      { key: "checks", targets: ["[data-filter-target]", "[data-filter-check]"], fallback: ["[data-middle]"], side: "left" },
      { key: "run", targets: ["[data-run-filter]"], side: "left" },
      { key: "report", targets: ["[data-filter-report]", "[data-reasons]"], fallback: ["[data-middle]"], side: "left" },
      { key: "listen", targets: ["[data-clips]"], fallback: ["[data-middle]"], side: "left" },
    ],
  },
  {
    key: "import",
    icon: "mdi:folder-download-outline",
    group: "start",
    needs: "import",
    steps: [
      { key: "node", targets: node("import"), side: "right", prepare: chooseStep("import") },
      { key: "folder", targets: ["[data-import-folder]", "[data-import-path]", "[data-import-zip]"], fallback: ["[data-middle]"], side: "left" },
      { key: "persona", targets: ["[data-import-persona]", "[data-import-verify]"], fallback: ["[data-middle]"], side: "left" },
      { key: "run", targets: ["[data-run-import]"], side: "left" },
      { key: "report", targets: ["[data-import-report]"], fallback: ["[data-middle]"], side: "left" },
    ],
  },
  // next steps
  {
    key: "train",
    icon: "mdi:school-outline",
    group: "more",
    needs: "voice",
    steps: [
      { key: "node", targets: node("train"), side: "right", prepare: chooseStep("train") },
      { key: "base", targets: ["[data-train-base]"], side: "left" },
      { key: "epochs", targets: ["[data-train-epochs]", "[data-train-estimate]"], side: "left" },
      { key: "resume", targets: ["[data-train-resume]", "[data-train-fresh]"], fallback: ["[data-run-train]"], side: "left" },
      { key: "poweroff", targets: ["label:has(> [data-train-poweroff])", "[data-poweroff-off]"], fallback: ["[data-run-train]"], side: "left" },
      { key: "run", targets: ["[data-run-train]"], side: "left" },
      { key: "job", targets: ["[data-side]"], side: "left" },
    ],
  },
  {
    key: "start_over",
    icon: "mdi:restart",
    group: "more",
    needs: "voice",
    steps: [
      { key: "keep", targets: ["[data-checkpoints]"], fallback: ["[data-middle]"], side: "left", prepare: chooseStep("train") },
      { key: "export", targets: node("export"), side: "right" },
      { key: "base", targets: ["[data-train-base]"], side: "left" },
      { key: "epochs", targets: ["[data-train-epochs]"], side: "left" },
      { key: "fresh", targets: ["[data-train-fresh]"], fallback: ["[data-run-train]"], side: "left" },
      { key: "runs", targets: ["[data-train-run]"], fallback: ["[data-train-chart]"], side: "left" },
      { key: "back", targets: ["[data-checkpoints]"], fallback: ["[data-middle]"], side: "left" },
    ],
  },
  {
    key: "chart",
    icon: "mdi:chart-line",
    group: "more",
    needs: "voice",
    steps: [
      { key: "chart", targets: ["[data-train-chart]"], fallback: ["[data-middle]"], side: "left", prepare: chooseStep("train") },
      { key: "checkpoints", targets: ["[data-checkpoints]"], fallback: ["[data-middle]"], side: "left" },
      { key: "listen", targets: ["[data-listen-epoch]", "[data-listen-zip]"], fallback: ["[data-middle]"], side: "left" },
      { key: "best", targets: ["[data-train-chart]"], fallback: ["[data-middle]"], side: "left" },
    ],
  },
  {
    key: "queue",
    icon: "mdi:playlist-play",
    group: "more",
    needs: "voice",
    steps: [
      { key: "node", targets: ["[data-node='jobs/queue']"], side: "right", prepare: choose("jobs/queue") },
      { key: "voices", targets: ["[data-queue-voice]", "[data-queue-voices]"], fallback: ["[data-middle]"], side: "left" },
      { key: "epochs", targets: ["[data-queue-epochs]", "[data-queue-base]"], fallback: ["[data-middle]"], side: "left" },
      { key: "poweroff", targets: ["label:has(> [data-queue-poweroff])"], fallback: ["[data-run-queue]", "[data-middle]"], side: "left" },
      { key: "run", targets: ["[data-run-queue]"], fallback: ["[data-middle]"], side: "left" },
    ],
  },
  {
    key: "export",
    icon: "mdi:export",
    group: "more",
    needs: "voice",
    steps: [
      { key: "node", targets: node("export"), side: "right", prepare: chooseStep("export") },
      { key: "checkpoint", targets: ["[data-export-checkpoint]"], fallback: ["[data-middle]"], side: "left" },
      { key: "run", targets: ["[data-run-export]"], side: "left" },
      { key: "files", targets: ["[data-export-files]"], fallback: ["[data-middle]"], side: "left" },
      { key: "home_assistant", targets: ["[data-export-files]"], fallback: ["[data-middle]"], side: "left" },
    ],
  },
  {
    key: "voice_settings",
    icon: "mdi:tune-variant",
    group: "more",
    needs: "voice",
    steps: [
      { key: "form", targets: ["[data-tab]"], fallback: ["[data-middle]"], side: "left", prepare: chooseSettings },
      { key: "field", targets: ["[data-field]"], fallback: ["[data-middle]"], side: "left" },
      { key: "draft", targets: ["[data-settings-state]", "[data-undo]", "[data-redo]"], fallback: ["[data-middle]"], side: "left" },
      { key: "save", targets: ["[data-save]"], fallback: ["[data-middle]"], side: "left" },
      { key: "history", targets: ["[data-history]"], fallback: ["[data-middle]"], side: "left" },
      { key: "rename", targets: ["[data-rename]"], fallback: ["[data-middle]"], side: "left" },
    ],
  },
  {
    key: "tune_train",
    icon: "mdi:tune-vertical",
    group: "more",
    needs: "voice",
    steps: [
      { key: "data", targets: voiceNode("train"), side: "right", prepare: chooseStep("train") },
      { key: "base", targets: ["[data-train-base]"], side: "left" },
      { key: "section", targets: ["[data-form-section='train']"], side: "left", prepare: chooseSettings },
      { key: "epochs", targets: [field("train.max_epochs")], side: "left" },
      { key: "batch", targets: [field("train.batch_size")], side: "left" },
      { key: "workers", targets: [field("train.num_workers")], side: "left" },
      { key: "validation", targets: [field("train.validation_split")], side: "left" },
      { key: "tests", targets: [field("train.num_test_examples")], side: "left" },
      { key: "advanced", targets: ["[data-tab='yaml']"], side: "left" },
      { key: "save", targets: ["[data-save]"], side: "left" },
    ],
  },
  {
    key: "tune_clone",
    icon: "mdi:tune",
    group: "more",
    needs: "clone",
    steps: [
      { key: "target", targets: [field("target_clips")], side: "left", prepare: chooseCloneSettings },
      { key: "overgenerate", targets: [field("synthesis.overgenerate")], side: "left" },
      { key: "voice", targets: ["[data-tab='yaml']"], side: "left" },
      { key: "cer", targets: [field("quality.max_cer")], side: "left" },
      { key: "similarity", targets: [field("quality.min_similarity")], side: "left" },
      { key: "mos", targets: [field("quality.mos_drop_fraction")], side: "left" },
      { key: "speed", targets: [field("quality.min_seconds_per_char"), field("quality.max_seconds_per_char")], side: "left" },
      { key: "save", targets: ["[data-save]"], side: "left" },
    ],
  },
  {
    key: "jobs",
    icon: "mdi:progress-clock",
    group: "more",
    steps: [
      { key: "panel", targets: ["[data-side]"], side: "left" },
      { key: "log", targets: ["[data-log]", "[data-log-enlarge]", "[data-log-copy]"], fallback: ["[data-side]"], side: "left" },
      { key: "stop", targets: ["[data-stop]", "[data-poweroff]"], fallback: ["[data-side]"], side: "left" },
      { key: "history", targets: ["[data-history]"], fallback: ["[data-middle]"], side: "left", prepare: choose("jobs/history") },
    ],
  },
  // set up once
  {
    key: "base",
    icon: "mdi:database-cog-outline",
    group: "once",
    steps: [
      { key: "prepare", targets: ["[data-run-base-prepare]"], fallback: ["[data-middle]"], side: "left", prepare: choose("base/prepare") },
      { key: "score", targets: ["[data-run-score]"], fallback: ["[data-middle]"], side: "left", prepare: choose("base/score") },
      { key: "train", targets: ["[data-base-quality]", "[data-run-base-train]"], fallback: ["[data-middle]"], side: "left", prepare: choose("base/train") },
      { key: "compare", targets: ["[data-compare]"], fallback: ["[data-middle]"], side: "left", prepare: choose("base/compare") },
      { key: "select", targets: ["[data-base-checkpoint]", "[data-run-base-select]"], fallback: ["[data-middle]"], side: "left", prepare: choose("base/select") },
    ],
  },
  {
    key: "home_assistant",
    icon: "mdi:home-assistant",
    group: "once",
    steps: [
      { key: "connect", targets: ["[data-ha-url]", "[data-ha-token]", "[data-ha-save]"], fallback: ["[data-middle]"], side: "left", prepare: choose("settings/home_assistant") },
      { key: "power", targets: ["[data-power]"], fallback: ["[data-middle]"], side: "left" },
      { key: "machine", targets: ["[data-machine]"], fallback: ["[data-middle]"], side: "left" },
      { key: "countdown", targets: ["[data-side]"], side: "left" },
    ],
  },
  {
    key: "elevenlabs",
    icon: "mdi:key-outline",
    group: "once",
    steps: [
      { key: "key", targets: ["[data-el-key]"], fallback: ["[data-middle]"], side: "left", prepare: choose("settings/elevenlabs") },
      { key: "save", targets: ["[data-el-key-save]", "[data-el-key-state]"], fallback: ["[data-middle]"], side: "left" },
    ],
  },
  {
    key: "look",
    icon: "mdi:palette-outline",
    group: "once",
    steps: [
      { key: "gear", targets: ["[data-editor-settings]"], side: "below-end", advance: "click" },
      { key: "theme", targets: ["[data-gear-theme]"], side: "left", interact: true },
      { key: "language", targets: ["[data-gear-language]"], side: "left", interact: true },
      { key: "more", targets: ["[data-gear-more]"], side: "left" },
    ],
  },
];

// "2 kroki" but "5 kroków" (Polish; English has one form for both)
const stepsKey = (count) => ([2, 3, 4].includes(count % 10) && ![12, 13, 14].includes(count % 100) ? "lessons_steps_few" : "lessons_steps");

export const LESSON_GROUPS = ["start", "more", "once"];

/** The lesson of a node of the tree: its step, or the part of the settings or the base model it is in. */
export function lessonFor(key) {
  const parts = (key ?? "").split("/");
  let name = null;
  if (parts[0] === "voice") name = parts[2] === "settings" ? "voice_settings" : parts[2] ?? null;
  else if (parts[0] === "base") name = "base";
  else if (parts[0] === "jobs") name = parts[1] === "queue" ? "queue" : "jobs";
  else if (parts[0] === "settings") name = parts[1] === "editor" ? "look" : parts[1];
  return LESSONS.find((lesson) => lesson.key === name) ?? null;
}

export class PvcLessons extends LitElement {
  static properties = {
    language: {},
    app: { attribute: false },
  };

  _t(key, values) {
    return translate(this.language, key, values);
  }

  _close() {
    this.dispatchEvent(new CustomEvent("close"));
  }

  render() {
    const done = lessonsDone();
    return html`<div class="scrim" @click=${(event) => event.target === event.currentTarget && this._close()}>
      <section class="box" role="dialog" data-lessons>
        <div class="head">
          <h2><pvc-icon icon="mdi:school-outline"></pvc-icon> ${this._t("lessons_title")}</h2>
          <button class="ghost x" data-lessons-close aria-label=${this._t("close")} @click=${this._close}><pvc-icon icon="mdi:close"></pvc-icon></button>
        </div>
        <p class="lead">${this._t("lessons_lead")}</p>
        ${LESSON_GROUPS.map(
          (group) => html`<h3 class="group" data-lessons-group=${group}>${this._t(`lessons_${group}`)}</h3>
            <div class="grid">
              ${LESSONS.filter((lesson) => lesson.group === group).map((lesson) => {
                const ready = lessonReady(lesson, this.app);
                const finished = done.includes(lesson.key);
                return html`<button class="lesson ${finished ? "done" : ""}" data-lesson=${lesson.key} ?disabled=${!ready}
                  @click=${() => this.dispatchEvent(new CustomEvent("lesson-start", { detail: { key: lesson.key } }))}>
                  <pvc-icon icon=${lesson.icon}></pvc-icon>
                  <span class="text">
                    <strong>${this._t(`lesson_${lesson.key}_name`)}</strong>
                    <small>${ready ? this._t(`lesson_${lesson.key}_about`) : this._t(`lessons_needs_${lesson.needs}`)}</small>
                  </span>
                  <span class="meta">${finished
                    ? html`<pvc-icon class="tick" icon="mdi:check-circle" data-lesson-done></pvc-icon>`
                    : this._t(stepsKey(lesson.steps.length), { count: lesson.steps.length })}</span>
                </button>`;
              })}
            </div>`,
        )}
        <p class="hint">${this._t("lessons_hint")}</p>
      </section>
    </div>`;
  }

  static styles = [
    dialogStyles,
    css`
      :host {
        color: var(--text);
        font-size: 14px;
      }
      .box {
        width: min(880px, calc(100vw - 48px));
        gap: 8px;
      }
      .head {
        display: flex;
        justify-content: space-between;
        align-items: center;
      }
      h2 {
        display: flex;
        gap: 8px;
        align-items: center;
      }
      .lead,
      .hint {
        margin: 0;
        color: var(--muted);
      }
      .group {
        margin: 8px 0 0;
        font-size: 12px;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        color: var(--muted);
      }
      .grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
        gap: 8px;
      }
      button {
        font: inherit;
        cursor: pointer;
      }
      .x {
        border: 0;
        background: none;
        color: var(--muted);
      }
      .lesson {
        all: unset;
        box-sizing: border-box;
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 10px 12px;
        border: 1px solid var(--line);
        border-radius: 12px;
        cursor: pointer;
      }
      .lesson:hover:not([disabled]) {
        border-color: var(--accent);
      }
      .lesson[disabled] {
        opacity: 0.55;
        cursor: default;
      }
      .lesson > pvc-icon {
        --icon-size: 22px;
        flex: none;
        color: var(--accent);
      }
      .lesson.done > pvc-icon {
        color: var(--green);
      }
      .text {
        flex: 1;
        min-width: 0;
      }
      .text strong,
      .text small {
        display: block;
      }
      .text small {
        color: var(--muted);
      }
      .meta {
        flex: none;
        color: var(--muted);
        font-size: 12px;
      }
      .tick {
        color: var(--green);
      }
    `,
  ];
}

customElements.define("pvc-lessons", PvcLessons);
