// The voice editor: top bar · tree of voices and steps · the chosen step · the live job on the right.
// The same shell as the Home Dashboard and Assist Router editors (columns, tree, search, theme).
import { LitElement, css, html, nothing } from "./vendor/lit-all.min.js";
import { pickLanguage, translate } from "./i18n.js";
import { base, tokens } from "./styles.js";
import { ApiError, get, post } from "./api.js";
import { duration } from "./format.js";
import "./icon.js";
import "./job-panel.js";
import "./new-voice.js";
import "./tour.js";
import { tourSeen } from "./tour.js";
import { LESSONS } from "./lessons.js";

const THEMES = ["auto", "light", "dark"];
// steps a voice can skip: not counted in "6/7" until done, never the next step
const OPTIONAL_STEPS = new Set(["audition"]);
const counted = (steps) => steps.filter((step) => step.done || !OPTIONAL_STEPS.has(step.key));
const THEME_ICONS = { auto: "mdi:theme-light-dark", light: "mdi:weather-sunny", dark: "mdi:weather-night" };
// remembered per browser (<app>-studio-*); a private window may refuse it: then nothing is kept
const THEME_KEY = "pvc-studio-theme";
const LANG_KEY = "pvc-lang";
const COLLAPSED_KEY = "pvc-studio-collapsed";
const EXPANDED_KEY = "pvc-studio-expanded";
const WIDTHS_KEY = "pvc-studio-widths";
const FOLDED_KEY = "pvc-studio-folded";
const FOLDED_WIDTH = 28; // a folded column stays as a narrow bar with its "unfold" button
const NARROW = 900; // below: the right column starts folded
const COLUMNS = { left: { start: 290, min: 220, max: 520 }, right: { start: 380, min: 300, max: 680 } };
const REFRESH_MS = 2000;

export const STEP_ICONS = {
  reference: "mdi:microphone",
  corpus: "mdi:text-box-outline",
  audition: "mdi:headphones",
  synthesize: "mdi:waveform",
  filter: "mdi:filter-outline",
  import: "mdi:folder-download-outline",
  train: "mdi:school-outline",
  export: "mdi:export",
};
const BASE_NODES = [
  ["prepare", "mdi:database-cog-outline"],
  ["score", "mdi:star-check-outline"],
  ["train", "mdi:school-outline"],
  ["compare", "mdi:compare-horizontal"],
  ["select", "mdi:check-decagram-outline"],
];
const JOB_NODES = [
  ["current", "mdi:progress-clock"],
  ["queue", "mdi:format-list-numbered"],
  ["history", "mdi:history"],
];
const SETTING_NODES = [
  ["elevenlabs", "mdi:account-voice"],
  ["home_assistant", "mdi:home-assistant"],
  ["editor", "mdi:palette-outline"],
];

function readJson(key, fallback) {
  try {
    return JSON.parse(localStorage.getItem(key)) ?? fallback;
  } catch {
    return fallback;
  }
}

function remember(key, value) {
  try {
    localStorage.setItem(key, typeof value === "string" ? value : JSON.stringify(value));
  } catch {
    // no storage (private window): the choice lasts until the page is reloaded
  }
}

function recall(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function columnWidth(side, width) {
  const { min, max } = COLUMNS[side];
  return Math.round(Math.max(min, Math.min(max, width)));
}

export function systemTheme(chosen, prefersDark = matchMedia("(prefers-color-scheme: dark)").matches) {
  if (chosen === "light" || chosen === "dark") return chosen;
  return prefersDark ? "dark" : "light";
}

/** Keep the nodes whose label (or a child's) contains the search text; groups stay when anything is left. */
export function filterOutline(groups, search) {
  const needle = search.trim().toLowerCase();
  if (!needle) return groups;
  const keep = (item) => {
    const children = item.children.map(keep).filter(Boolean);
    return item.label.toLowerCase().includes(needle) || children.length ? { ...item, children } : null;
  };
  return groups.map((group) => ({ ...group, children: group.children.map(keep).filter(Boolean) }));
}

export class PvcEditor extends LitElement {
  static properties = {
    _state: { state: true },
    _selected: { state: true },
    _search: { state: true },
    _collapsed: { state: true },
    _expanded: { state: true },
    _widths: { state: true },
    _theme: { state: true },
    _language: { state: true },
    _dialog: { state: true },
    _dialogError: { state: true },
    _busy: { state: true },
    _notice: { state: true },
    _menu: { state: true },
    _gear: { state: true },
    _folded: { state: true },
    // the tour of the editor (tour.js) over everything, or one of its lessons (lessons.js)
    _tour: { state: true },
    _lesson: { state: true },
  };

  constructor() {
    super();
    this._state = null;
    this._selected = decodeURIComponent(location.hash.slice(1)) || null;
    this._search = "";
    this._collapsed = new Set(readJson(COLLAPSED_KEY, []));
    // voices are folded unless opened by hand or chosen: a long list stays short
    this._expanded = new Set(readJson(EXPANDED_KEY, []));
    this._widths = { left: COLUMNS.left.start, right: COLUMNS.right.start, ...readJson(WIDTHS_KEY, {}) };
    this._folded = { left: false, right: window.innerWidth < NARROW, ...readJson(FOLDED_KEY, {}) };
    this._onKeys = (event) => {
      if (event.key === "Escape" && (this._menu || this._gear)) {
        this._menu = false;
        this._gear = false;
        return;
      }
      this._foldKeys(event);
    };
    // a click anywhere outside the ☰ or ⚙ box closes it
    this._onOutside = (event) => {
      if (!this._menu && !this._gear) return;
      const path = event.composedPath();
      // the bubble of a lesson that shows the box is not "beside" it
      if (path.some((el) => el.classList?.contains("menu-wrap") || el.tagName === "PVC-TOUR")) return;
      this._menu = false;
      this._gear = false;
    };
    this._theme = THEMES.includes(recall(THEME_KEY)) ? recall(THEME_KEY) : "auto";
    this._language = pickLanguage(recall(LANG_KEY));
    this._dialog = null;
    this._notice = null;
    this._onHash = () => (this._selected = decodeURIComponent(location.hash.slice(1)) || null);
    // the "?" of a view offers the lesson of what it is about
    this.addEventListener("help-lesson", (event) => this._startLesson(event.detail.key));
  }

  _startLesson(key) {
    this._dialog = null;
    this._gear = false;
    this._tour = false;
    this._lesson = LESSONS.find((lesson) => lesson.key === key) ?? null;
  }

  connectedCallback() {
    super.connectedCallback();
    window.addEventListener("hashchange", this._onHash);
    this._media = matchMedia("(prefers-color-scheme: dark)");
    this._onMedia = () => this.requestUpdate();
    this._media.addEventListener("change", this._onMedia);
    // a tab in the background asks nothing; back in front it asks at once
    this._onVisible = () => {
      if (!document.hidden) this._poll();
    };
    document.addEventListener("visibilitychange", this._onVisible);
    window.addEventListener("keydown", this._onKeys);
    window.addEventListener("click", this._onOutside);
    this._alive = true;
    this._poll();
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this._alive = false;
    window.removeEventListener("hashchange", this._onHash);
    this._media.removeEventListener("change", this._onMedia);
    document.removeEventListener("visibilitychange", this._onVisible);
    window.removeEventListener("keydown", this._onKeys);
    window.removeEventListener("click", this._onOutside);
    clearTimeout(this._timer);
  }

  /** Fold or unfold a side column; its width before folding comes back. */
  _fold(side, folded = !this._folded[side]) {
    this._folded = { ...this._folded, [side]: folded };
    remember(FOLDED_KEY, this._folded);
  }

  // Ctrl/⌘+B folds the left column, Ctrl/⌘+Alt+B the right one (event.code: the same key on every layout)
  _foldKeys(event) {
    if (!(event.ctrlKey || event.metaKey) || event.code !== "KeyB") return;
    event.preventDefault();
    this._fold(event.altKey ? "right" : "left");
  }

  _renderFoldBar(side) {
    const label = this._t(`unfold_${side}`);
    return html`<div class="fold-bar" data-fold-bar=${side}>
      <button class="ghost" data-unfold=${side} title=${label} aria-label=${label} @click=${() => this._fold(side, false)}>
        <pvc-icon icon=${side === "left" ? "mdi:chevron-right" : "mdi:chevron-left"}></pvc-icon>
      </button>
    </div>`;
  }

  /** One question about the state at a time: the next one is planned only after the answer. */
  async _poll() {
    if (this._polling) {
      // an answer is on its way but may be older than what just happened: ask once more after it
      this._again = true;
      return this._polling;
    }
    clearTimeout(this._timer);
    if (!this._alive || document.hidden) return;
    this._polling = (async () => {
      try {
        do {
          this._again = false;
          await this._refresh();
        } while (this._again && this._alive);
      } finally {
        this._polling = null;
        if (this._alive && !document.hidden) this._timer = setTimeout(() => this._poll(), REFRESH_MS);
      }
    })();
    return this._polling;
  }

  _t(key, values, fallback) {
    return translate(this._language, key, values, fallback);
  }

  updated() {
    this.dataset.theme = systemTheme(this._theme);
    document.documentElement.lang = this._language;
    document.title = this._t("title");
  }

  async _refresh() {
    try {
      const fresh = await get("/api/state");
      // the page is drawn again only when what it shows changed
      const text = JSON.stringify(fresh);
      if (text !== this._stateText) {
        this._stateText = text;
        this._state = fresh;
      }
      if (this._notice?.offline) this._notice = null;
      if (!this._selected && this._state.opening_voice) this._select(`voice/${this._state.opening_voice}`);
      // the first time the editor opens in this browser its parts are shown one at a time
      if (!this._tourChecked) {
        this._tourChecked = true;
        if (!tourSeen() && !this._dialog) this._tour = true;
      }
      window.editorReady = true;
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) return;
      const text = err.code === "timeout" ? this._t("timeout", { seconds: err.values.seconds }) : this._t("error", { message: err.message });
      this._notice = { kind: "error", text, offline: true };
    }
  }

  _select(key) {
    this._selected = key;
    if (location.hash.slice(1) !== encodeURIComponent(key)) history.replaceState(null, "", `#${encodeURIComponent(key)}`);
    const voice = key.startsWith("voice/") ? key.split("/")[1] : null;
    if (voice) post(`/api/voices/${encodeURIComponent(voice)}/open`).catch(() => {});
  }

  _setTheme(theme) {
    this._theme = theme;
    remember(THEME_KEY, theme);
  }

  _nextTheme() {
    this._setTheme(THEMES[(THEMES.indexOf(this._theme) + 1) % THEMES.length]);
  }

  _setLanguage(language) {
    this._language = language;
    remember(LANG_KEY, language);
  }

  _nextLanguage() {
    this._setLanguage(this._language === "pl" ? "en" : "pl");
  }

  _docsUrl() {
    return this._language === "pl" ? "/docs/pl/" : "/docs/";
  }

  // The tree -----------------------------------------------------------------------------------------

  _outline() {
    const voices = (this._state?.voices ?? []).map((voice) => {
      const needed = counted(voice.steps);
      const done = needed.filter((step) => step.done).length;
      return {
        key: `voice/${voice.name}`,
        label: voice.name,
        icon: voice.workflow === "import" ? "mdi:folder-music" : "mdi:account-voice",
        count: needed.length ? `${done}/${needed.length}` : "",
        warn: voice.error,
        children: [
          ...voice.steps.map((step) => ({
            key: `voice/${voice.name}/${step.key}`,
            label: this._t(`step_${step.key}`),
            icon: STEP_ICONS[step.key],
            done: step.done,
            optional: !step.done && OPTIONAL_STEPS.has(step.key),
            count: step.detail,
            children: [],
          })),
          { key: `voice/${voice.name}/settings`, label: this._t("voice_settings"), icon: "mdi:cog-outline", children: [] },
        ],
      };
    });
    const simple = (prefix, nodes, labelPrefix) =>
      nodes.map(([key, icon]) => ({ key: `${prefix}/${key}`, label: this._t(`${labelPrefix}_${key}`), icon, children: [] }));
    return [
      { key: "voices", label: this._t("group_voices"), add: true, children: voices },
      { key: "base", label: this._t("group_base"), children: simple("base", BASE_NODES, "base") },
      { key: "jobs", label: this._t("group_jobs"), children: simple("jobs", JOB_NODES, "jobs") },
      { key: "settings", label: this._t("group_settings"), children: simple("settings", SETTING_NODES, "settings") },
    ];
  }

  _isOpen(key) {
    if (this._collapsed.has(key)) return false;
    if (!key.startsWith("voice/")) return true;
    return this._expanded.has(key) || (this._selected ?? "").split("/").slice(0, 2).join("/") === key;
  }

  _toggle(key) {
    const open = this._isOpen(key);
    const collapsed = new Set(this._collapsed);
    const expanded = new Set(this._expanded);
    if (open) {
      collapsed.add(key);
      expanded.delete(key);
    } else {
      collapsed.delete(key);
      if (key.startsWith("voice/")) expanded.add(key);
    }
    this._collapsed = collapsed;
    this._expanded = expanded;
    remember(COLLAPSED_KEY, [...collapsed]);
    remember(EXPANDED_KEY, [...expanded]);
  }

  _foldAll(fold) {
    const keys = this._outline().flatMap((group) => group.children.filter((item) => item.children.length).map((item) => item.key));
    this._collapsed = new Set(fold ? keys : []);
    this._expanded = new Set(fold ? [] : keys);
    remember(COLLAPSED_KEY, [...this._collapsed]);
    remember(EXPANDED_KEY, [...this._expanded]);
  }

  // New voice ---------------------------------------------------------------------------------------

  async _createVoice({ name, piper_name, workflow }) {
    this._busy = true;
    this._dialogError = null;
    try {
      const voice = await post("/api/voices", { name, piper_name, workflow });
      this._dialog = null;
      await this._poll();
      this._select(`voice/${voice.name}/${voice.steps[0].key}`);
    } catch (err) {
      this._dialogError = err.message;
    } finally {
      this._busy = false;
    }
  }

  // Jobs --------------------------------------------------------------------------------------------

  async _stopJob({ slot }) {
    await post(`/api/jobs/${slot}/stop`).catch((err) => (this._notice = { kind: "error", text: err.message }));
    this._poll();
  }

  async _jobPoweroff({ slot, value }) {
    try {
      await post(`/api/jobs/${slot}/poweroff`, { value });
    } catch (err) {
      this._notice = { kind: "error", text: this._t(err.code ?? "error", { message: err.message }) };
    }
    this._poll();
  }

  /** Start a job from a step (the step components call this through a "run" event). */
  async run(path, body) {
    try {
      const job = await post(path, body);
      this._notice = null;
      await this._poll();
      return job;
    } catch (err) {
      const values = err.values ?? {};
      const text =
        err.code === "job_busy"
          ? this._t("job_busy", { kind: this._t(`kind_${values.kind}`, {}, values.kind), voice: values.voice ? ` (${values.voice})` : "" })
          : this._t("error", { message: this._t(err.code ?? "", values, err.message) });
      this._notice = { kind: "error", text };
      throw err;
    }
  }

  // Rendering ---------------------------------------------------------------------------------------

  render() {
    if (!this._state) return html`<p class="empty">${this._t("loading")}</p>`;
    return html`
      ${this._renderTop()} ${this._renderNotice()}
      <div
        class="cols"
        style="--left: ${this._folded.left ? FOLDED_WIDTH : this._widths.left}px; --right: ${this._folded.right ? FOLDED_WIDTH : this._widths.right}px"
      >
        ${this._folded.left ? this._renderFoldBar("left") : this._renderTree()} ${this._renderSplitter("left")}
        <main class="middle" data-middle>${this._renderMiddle()}</main>
        ${this._renderSplitter("right")}
        ${this._folded.right ? this._renderFoldBar("right") : this._renderSide()}
      </div>
      ${this._dialog === "new-voice"
        ? html`<pvc-new-voice
            .language=${this._language}
            .error=${this._dialogError}
            ?busy=${this._busy}
            @close=${() => ((this._dialog = null), (this._dialogError = null))}
            @create=${(event) => this._createVoice(event.detail)}
          ></pvc-new-voice>`
        : nothing}
      ${this._dialog === "lessons"
        ? html`<pvc-lessons .language=${this._language} .app=${this}
            @close=${() => (this._dialog = null)}
            @lesson-start=${(event) => this._startLesson(event.detail.key)}></pvc-lessons>`
        : nothing}
      ${this._tour || this._lesson
        ? html`<pvc-tour .root=${this} .host=${this} .language=${this._language} .lesson=${this._lesson}
            @tour-close=${() => {
              this._gear = false; // the ⚙ box a lesson opened does not stay over the editor after it
              this._tour = false;
              this._lesson = null;
            }}></pvc-tour>`
        : nothing}
    `;
  }

  _renderSide() {
    const fold = this._t("fold_right");
    return html`<aside class="side" data-side>
      <div class="col-tools right"><button class="ghost" data-fold-column="right" title=${fold} aria-label=${fold} @click=${() => this._fold("right", true)}>
        <pvc-icon icon="mdi:chevron-right"></pvc-icon></button></div>
      <pvc-job-panel
        .language=${this._language}
        .jobs=${this._state.jobs}
        .gpu=${this._state.gpu}
        .canPowerOff=${Boolean(this._state.can_power_off)}
        .tensorboard=${this._state.tensorboard_port ? `${location.protocol}//${location.hostname}:${this._state.tensorboard_port}` : ""}
        @stop-job=${(event) => this._stopJob(event.detail)}
        @job-poweroff=${(event) => this._jobPoweroff(event.detail)}
      ></pvc-job-panel>
    </aside>`;
  }

  _currentVoice() {
    const parts = (this._selected ?? "").split("/");
    return parts[0] === "voice" ? parts[1] : null;
  }

  _renderTop() {
    return html`<header class="top">
      ${this._renderMenu()}
      <img class="logo" src="/static/icon.svg" alt="" />
      <h1>${this._t("title")}</h1>
      <span class="board" data-voice-name>${this._currentVoice() ?? ""}</span>
      <span class="grow"></span>
      ${this._renderJobChip()} ${this._renderMachine()} ${this._renderCountdown()}
      <button class="ghost" data-theme-button=${this._theme} title=${this._t(`theme_${this._theme}`)} aria-label=${this._t(`theme_${this._theme}`)} @click=${this._nextTheme}>
        <pvc-icon icon=${THEME_ICONS[this._theme]}></pvc-icon>
      </button>
      <button class="ghost" data-docs title=${this._t("docs")} aria-label=${this._t("docs")} @click=${() => window.open(this._docsUrl(), "_blank", "noopener")}>
        <pvc-icon icon="mdi:help-circle-outline"></pvc-icon>
      </button>
      ${this._renderGear()}
    </header>`;
  }

  /** ⚙: the look and the language right there, in a box under the button. */
  _renderGear() {
    return html`<div class="menu-wrap">
      <button class="ghost" data-editor-settings title=${this._t("settings_editor")} aria-label=${this._t("settings_editor")}
        aria-expanded=${this._gear ? "true" : "false"} @click=${() => { this._gear = !this._gear; this._menu = false; }}>
        <pvc-icon icon="mdi:cog-outline"></pvc-icon>
      </button>
      ${this._gear
        ? html`<div class="menu-box gear-box" data-gear-box>
            <strong>${this._t("settings_editor")}</strong>
            <span class="hint">${this._t("theme")}</span>
            <div class="seg" data-gear-theme>
              ${THEMES.map((theme) => html`<button class=${this._theme === theme ? "on" : ""} data-theme-option=${theme}
                @click=${() => this._setTheme(theme)}>${this._t(`theme_short_${theme}`)}</button>`)}
            </div>
            <span class="hint">${this._t("language_choice")}</span>
            <div class="seg" data-gear-language>
              ${[["pl", "Polski"], ["en", "English"]].map(([code, name]) => html`<button class=${this._language === code ? "on" : ""}
                data-language-option=${code} @click=${() => this._setLanguage(code)}>${name}</button>`)}
            </div>
            <button class="ghost" data-gear-tour @click=${() => { this._gear = false; this._lesson = null; this._tour = true; }}>
              <pvc-icon icon="mdi:map-marker-path"></pvc-icon>${this._t("tour_open")}
            </button>
            <button class="ghost" data-gear-lessons @click=${() => { this._gear = false; this._dialog = "lessons"; }}>
              <pvc-icon icon="mdi:school-outline"></pvc-icon>${this._t("lessons_title")}
            </button>
            <button class="ghost" data-gear-more @click=${() => { this._gear = false; this._select("settings/editor"); }}>
              <pvc-icon icon="mdi:palette-outline"></pvc-icon>${this._t("gear_more")}
            </button>
          </div>`
        : nothing}
    </div>`;
  }

  /** ☰: the guide, who is logged in and how to change the password, log out. */
  _renderMenu() {
    return html`<div class="menu-wrap">
      <button class="ghost menu" data-menu aria-label=${this._t("menu")} title=${this._t("menu")} @click=${() => { this._menu = !this._menu; this._gear = false; }}>
        <pvc-icon icon="mdi:menu"></pvc-icon>
      </button>
      ${this._menu
        ? html`<div class="menu-box" data-menu-box @click=${() => (this._menu = false)}>
            <button class="ghost" data-menu-docs @click=${() => window.open(this._docsUrl(), "_blank", "noopener")}>
              <pvc-icon icon="mdi:book-open-variant"></pvc-icon>${this._t("docs")}
            </button>
            ${this._state.trusted
              ? html`<div class="menu-user" data-menu-trusted>
                    <pvc-icon icon="mdi:shield-home"></pvc-icon>${this._t("trusted_network")}
                  </div>`
              : this._state.login
              ? html`<div class="menu-user" data-menu-user>
                    <pvc-icon icon="mdi:account"></pvc-icon>${this._t("logged_in_as", { user: this._state.user })}
                  </div>
                  <p class="hint">${this._t("password_change")}</p>
                  <button class="ghost" data-logout @click=${this._logout}><pvc-icon icon="mdi:logout"></pvc-icon>${this._t("logout")}</button>`
              : nothing}
            <span class="hint">v${this._state.version}</span>
          </div>`
        : nothing}
    </div>`;
  }

  /** The job now: its stage, progress and time left (the card on the right has the rest). */
  _renderJobChip() {
    const job = this._state.jobs?.current ?? {};
    if (job.state !== "running") return nothing;
    const progress = job.progress;
    const share = progress?.total ? Math.round((100 * progress.done) / progress.total) : null;
    return html`<button class="pill running" data-top-job @click=${() => this._select("jobs/current")}>
      <pvc-icon icon="mdi:progress-clock"></pvc-icon>${this._t(`kind_${job.kind}`, {}, job.kind)}${job.voice ? ` · ${job.voice}` : ""}${share != null ? ` · ${share}%` : ""}${progress?.left ? ` · ${duration(progress.left)}` : ""}
    </button>`;
  }

  /** The machine: GPU load, temperature, memory, the plug's power; and switching it off. */
  _renderMachine() {
    const gpu = this._state.gpu;
    const machine = this._state.machine;
    if (!gpu && !machine) return nothing;
    const parts = [];
    if (gpu) parts.push(`${Math.round(gpu.utilization)}%`, `${Math.round(gpu.temperature)}°`, `${Math.round(gpu.memory_used / 1024)} GB`);
    if (machine?.watts != null) parts.push(`${Math.round(machine.watts)} W`);
    return html`<span class="pill machine ${machine?.machine ?? ""}" data-top-machine=${machine?.machine ?? "gpu"} title=${machine?.error ?? this._t("machine_title")}>
      <pvc-icon icon="mdi:expansion-card"></pvc-icon>${parts.join(" · ")}
      ${this._state.can_power_off
        ? html`<button class="ghost danger off" data-machine-off-top title=${this._t("machine_power_off")} aria-label=${this._t("machine_power_off")}
            ?disabled=${this._state.jobs?.current?.state === "running"} @click=${this._machineOff}><pvc-icon icon="mdi:power"></pvc-icon></button>`
        : nothing}
    </span>`;
  }

  /** "Power-off in 1:45 · Cancel" after a job with the wish; an error of switching it off. */
  _renderCountdown() {
    const power = this._state.power_off ?? {};
    if (power.seconds_left != null) {
      const left = power.seconds_left;
      const clock = `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`;
      return html`<span class="pill countdown" data-countdown>
        <pvc-icon icon="mdi:power"></pvc-icon>${this._t("power_off_in", { time: clock })}
        <button class="ghost" data-countdown-cancel @click=${this._cancelPowerOff}>${this._t("cancel")}</button>
      </span>`;
    }
    if (power.error) return html`<span class="pill error" data-power-error title=${power.error}><pvc-icon icon="mdi:alert-circle"></pvc-icon>${this._t("power_off_failed")}</span>`;
    return nothing;
  }

  async _logout() {
    await fetch("/logout", { method: "POST", credentials: "same-origin" }).catch(() => {});
    window.location.href = "/login";
  }

  async _cancelPowerOff() {
    await post("/api/power-off/cancel").catch(() => {});
    this._poll();
  }

  async _machineOff() {
    if (!window.confirm(this._t("machine_off_confirm"))) return;
    try {
      await post("/api/machine/off");
      this._notice = { kind: "ok", text: this._t("machine_off_sent") };
    } catch (err) {
      this._notice = { kind: "error", text: this._t(err.code ?? "error", { ...err.values, message: err.message }) };
    }
  }

  _renderNotice() {
    if (!this._notice) return nothing;
    return html`<div class="notice ${this._notice.kind}" data-notice=${this._notice.kind}>
      <span>${this._notice.text}</span>
      <button class="ghost" aria-label=${this._t("close")} @click=${() => (this._notice = null)}>
        <pvc-icon icon="mdi:close"></pvc-icon>
      </button>
    </div>`;
  }

  _renderTree() {
    const searching = Boolean(this._search.trim());
    const groups = filterOutline(this._outline(), this._search);
    const node = (item, depth) => {
      const open = searching || this._isOpen(item.key);
      return html`
        <div
          class="node ${this._selected === item.key ? "sel" : ""} ${item.warn ? "warn" : ""}"
          style="padding-left: ${8 + depth * 16}px"
          data-node=${item.key}
          title=${item.warn ?? ""}
          @click=${() => this._select(item.key)}
        >
          ${item.children.length
            ? html`<button
                class="fold"
                aria-label=${this._t("fold")}
                data-fold=${item.key}
                @click=${(event) => {
                  event.stopPropagation();
                  this._toggle(item.key);
                }}
              >
                <pvc-icon icon=${open ? "mdi:chevron-down" : "mdi:chevron-right"}></pvc-icon>
              </button>`
            : html`<span class="fold"></span>`}
          <pvc-icon class="icon" icon=${item.warn ? "mdi:alert-outline" : item.icon}></pvc-icon>
          <span class="label">${item.label}</span>
          ${item.done !== undefined
            ? html`<pvc-icon class="mark ${item.done ? "done" : ""}" data-optional=${item.optional ? "true" : "false"} title=${item.optional ? this._t("step_optional") : ""}
                icon=${item.done ? "mdi:check-circle" : item.optional ? "mdi:circle-small" : "mdi:circle-outline"}></pvc-icon>`
            : nothing}
          ${item.count ? html`<span class="count">${item.count}</span>` : nothing}
        </div>
        ${open ? item.children.map((child) => node(child, depth + 1)) : nothing}
      `;
    };
    const fold = this._t("fold_left");
    return html`<nav class="tree" data-tree>
      <div class="tree-tools">
        <button class="ghost fold-column" data-fold-column="left" title=${fold} aria-label=${fold} @click=${() => this._fold("left", true)}>
          <pvc-icon icon="mdi:chevron-left"></pvc-icon>
        </button>
        <button class="ghost" data-fold-all title=${this._t("fold_all")} aria-label=${this._t("fold_all")} @click=${() => this._foldAll(true)}>
          <pvc-icon icon="mdi:unfold-less-horizontal"></pvc-icon>${this._t("fold_all_short")}
        </button>
        <button class="ghost" data-unfold-all title=${this._t("unfold_all")} aria-label=${this._t("unfold_all")} @click=${() => this._foldAll(false)}>
          <pvc-icon icon="mdi:unfold-more-horizontal"></pvc-icon>${this._t("unfold_all_short")}
        </button>
      </div>
      <label class="search">
        <pvc-icon icon="mdi:magnify"></pvc-icon>
        <input data-search placeholder=${this._t("search")} .value=${this._search} @input=${(event) => (this._search = event.target.value)} />
      </label>
      ${groups.map((group) => {
        const open = searching || this._isOpen(group.key);
        return html`<div class="group" data-group=${group.key}>
            <button class="fold" data-fold=${group.key} @click=${() => this._toggle(group.key)}>
              <pvc-icon icon=${open ? "mdi:chevron-down" : "mdi:chevron-right"}></pvc-icon>
            </button>
            <span class="group-name" @click=${() => this._toggle(group.key)}>${group.label}</span>
            ${group.add
              ? html`<button class="ghost add" data-new-voice-button title=${this._t("new_voice")} aria-label=${this._t("new_voice")} @click=${() => (this._dialog = "new-voice")}>
                  <pvc-icon icon="mdi:plus"></pvc-icon>
                </button>`
              : nothing}
          </div>
          ${open
            ? group.key === "voices" && !group.children.length && !searching
              ? html`<p class="hint empty-group" data-no-voices>${this._t("no_voices")}</p>`
              : group.children.map((item) => node(item, 0))
            : nothing}`;
      })}
    </nav>`;
  }

  _renderSplitter(side) {
    const move = (event) => {
      const box = this.getBoundingClientRect();
      const width = side === "left" ? event.clientX - box.left : box.right - event.clientX;
      this._widths = { ...this._widths, [side]: columnWidth(side, width) };
    };
    const start = (event) => {
      event.preventDefault();
      const bar = event.currentTarget;
      bar.setPointerCapture?.(event.pointerId);
      bar.classList.add("dragging");
      const stop = () => {
        bar.classList.remove("dragging");
        bar.removeEventListener("pointermove", move);
        bar.removeEventListener("pointerup", stop);
        bar.removeEventListener("pointercancel", stop);
        remember(WIDTHS_KEY, this._widths);
      };
      bar.addEventListener("pointermove", move);
      bar.addEventListener("pointerup", stop);
      bar.addEventListener("pointercancel", stop);
    };
    const reset = () => {
      this._widths = { ...this._widths, [side]: COLUMNS[side].start };
      remember(WIDTHS_KEY, this._widths);
    };
    if (this._folded[side]) return html`<div class="splitter folded" data-splitter=${side} data-splitter-folded></div>`;
    return html`<div class="splitter" role="separator" aria-orientation="vertical" title=${this._t("resize")} data-splitter=${side} @pointerdown=${start} @dblclick=${reset}></div>`;
  }

  _renderMiddle() {
    const [kind, name, step] = (this._selected ?? "").split("/");
    if (kind === "voice") {
      const voice = this._state.voices.find((item) => item.name === name);
      if (!voice) return html`<p class="empty">${this._t("pick_node")}</p>`;
      if (!step) return this._renderVoiceOverview(voice);
      return this._renderView(`step-${step}`, { voice });
    }
    if (["base", "jobs", "settings"].includes(kind)) return this._renderView(`${kind}-${name}`, {});
    return html`<p class="empty">${this._t("pick_node")}</p>`;
  }

  /** A part of the editor: the components register themselves in VIEWS (later stages add more). */
  _renderView(name, props) {
    const view = VIEWS[name];
    if (!view) return html`<div class="pane"><p class="empty" data-coming-soon>${this._t("coming_soon")}</p></div>`;
    return view({ ...props, editor: this, language: this._language, state: this._state });
  }

  _renderVoiceOverview(voice) {
    // the first step not done yet (audition is a check that may be skipped)
    const next = voice.steps.find((step) => !step.done && !OPTIONAL_STEPS.has(step.key));
    return html`<div class="pane" data-voice-overview=${voice.name}>
      <div class="phead">
        <pvc-icon icon=${voice.workflow === "import" ? "mdi:folder-music" : "mdi:account-voice"}></pvc-icon>
        <div>
          <strong>${voice.name}</strong>
          <div class="path">${voice.piper_name || `pl_PL-${voice.name}`} · ${this._t(`workflow_${voice.workflow}`)}</div>
        </div>
      </div>
      <h3>${this._t("voice_overview")}</h3>
      ${next
        ? html`<button class="primary next-step" data-next-step=${next.key} @click=${() => this._select(`voice/${voice.name}/${next.key}`)}>
            <pvc-icon icon=${STEP_ICONS[next.key]}></pvc-icon>${this._t("step_next", { step: this._t(`step_${next.key}`) })}
          </button>`
        : html`<p class="hint" data-voice-ready>${this._t("voice_ready")}</p>`}
      <ol class="overview">
        ${voice.steps.map(
          (step) => html`<li class="${step.done ? "done" : ""} ${step === next ? "next" : ""}" data-overview-step=${step.key} @click=${() => this._select(`voice/${voice.name}/${step.key}`)}>
            <pvc-icon icon=${STEP_ICONS[step.key]}></pvc-icon>
            <span class="label">${this._t(`step_${step.key}`)}</span>
            <span class="hint">${step.detail}</span>
            <span class="state">${step.done ? this._t("step_done") : step === next ? this._t("step_now") : OPTIONAL_STEPS.has(step.key) ? this._t("step_optional") : this._t("step_todo")}</span>
          </li>`,
        )}
      </ol>
    </div>`;
  }

  static styles = [
    tokens,
    base,
    css`
      :host {
        display: flex;
        flex-direction: column;
        height: 100vh;
        color: var(--text);
        background: var(--bg);
        font: 14px/1.4 -apple-system, "SF Pro Text", Roboto, system-ui, sans-serif;
      }
      .empty {
        margin: 40px auto;
        color: var(--muted);
        text-align: center;
      }
      .top {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 10px 16px;
        background: var(--panel);
        border-bottom: 1px solid var(--line);
      }
      .logo {
        width: 26px;
        height: 26px;
      }
      h1 {
        margin: 0 8px 0 0;
        font-size: 16px;
      }
      .board {
        overflow: hidden;
        color: var(--muted);
        font: 12px ui-monospace, SFMono-Regular, Menlo, monospace;
        white-space: nowrap;
        text-overflow: ellipsis;
      }
      .grow {
        flex: 1;
      }
      .pill {
        display: inline-flex;
        gap: 6px;
        align-items: center;
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 12px;
        color: var(--muted);
        background: var(--panel2);
        white-space: nowrap;
      }
      .pill.running {
        color: var(--accent-text);
        background: rgba(79, 140, 255, 0.18);
      }
      button.pill {
        border: 0;
        cursor: pointer;
      }
      .pill.machine.on {
        color: var(--green);
        background: rgba(48, 209, 88, 0.12);
      }
      .pill.machine.unknown {
        color: var(--amber);
      }
      .pill .off {
        padding: 0 0 0 4px;
        --icon-size: 16px;
      }
      .pill.countdown {
        color: var(--warn-text);
        background: rgba(255, 179, 64, 0.18);
      }
      .pill.countdown button {
        padding: 0 4px;
        color: var(--accent-text);
        font-size: 12px;
      }
      .pill.error {
        color: var(--red);
        background: rgba(255, 69, 58, 0.15);
      }
      .menu-wrap {
        position: relative;
      }
      button.menu {
        padding: 6px;
        --icon-size: 22px;
      }
      .menu-box {
        position: absolute;
        top: 40px;
        left: 0;
        z-index: 30;
        display: grid;
        gap: 6px;
        min-width: 260px;
        padding: 10px;
        border-radius: 12px;
        background: var(--panel);
        border: 1px solid var(--line);
        box-shadow: 0 20px 50px var(--shadow);
      }
      .gear-box {
        left: auto;
        right: 0;
        min-width: 280px;
      }
      .gear-box .seg {
        width: 100%;
      }
      .gear-box .seg button {
        flex: 1;
        white-space: nowrap;
      }
      .menu-box .hint {
        margin: 0;
      }
      .menu-user {
        display: flex;
        gap: 6px;
        align-items: center;
        font-weight: 600;
      }
      .logout {
        margin: 0;
      }
      .notice {
        display: flex;
        gap: 10px;
        align-items: center;
        padding: 8px 16px;
        background: rgba(79, 140, 255, 0.15);
      }
      .notice.error {
        background: rgba(255, 69, 58, 0.15);
      }
      .notice.ok {
        background: rgba(48, 209, 88, 0.15);
      }
      .notice span {
        flex: 1;
      }
      .cols {
        flex: 1;
        display: grid;
        grid-template-columns: var(--left) 6px minmax(0, 1fr) 6px var(--right);
        min-height: 0;
      }
      .tree,
      .side {
        overflow: auto;
        background: var(--panel);
        display: flex;
        flex-direction: column;
      }
      /* the job panel fills the column, so its log can take the rest of the height */
      .side pvc-job-panel {
        flex: 1 0 auto;
      }
      .middle {
        overflow: auto;
        min-width: 0;
      }
      .tree {
        padding: 10px 8px;
      }
      .search {
        display: flex;
        gap: 8px;
        align-items: center;
        margin: 6px 4px;
        padding: 6px 10px;
        border-radius: 9px;
        color: var(--muted);
        background: var(--panel2);
      }
      .search input {
        flex: 1;
        border: 0;
        padding: 0;
        background: transparent;
      }
      .tree-tools {
        display: flex;
        gap: 2px;
      }
      .tree-tools button {
        padding: 4px 8px;
        font-size: 12px;
        white-space: nowrap; /* "Zwiń wszystko" broke onto two lines */
      }
      .group {
        display: flex;
        gap: 4px;
        align-items: center;
        min-height: 28px;
        margin: 12px 8px 4px 0;
        font-size: 11px;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: var(--muted);
      }
      .group .add {
        padding: 4px;
      }
      .group-name {
        flex: 1;
        cursor: pointer;
        user-select: none;
      }
      .empty-group {
        margin: 4px 12px;
      }
      .fold {
        width: 20px;
        height: 20px;
        padding: 0;
        justify-content: center;
        background: transparent;
        color: var(--muted);
        flex: none;
      }
      .node {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 5px 8px;
        border-radius: 8px;
        cursor: pointer;
      }
      .node:hover {
        background: var(--hover);
      }
      .node.sel {
        background: rgba(79, 140, 255, 0.18);
        outline: 1px solid rgba(79, 140, 255, 0.5);
      }
      .node.warn .icon {
        color: var(--amber);
      }
      .node .label {
        flex: 1;
        overflow: hidden;
        white-space: nowrap;
        text-overflow: ellipsis;
      }
      .node .count {
        color: var(--muted);
        font-size: 12px;
        font-variant-numeric: tabular-nums;
        max-width: 90px;
        overflow: hidden;
        white-space: nowrap;
        text-overflow: ellipsis;
      }
      .mark {
        --icon-size: 14px;
        color: var(--faint);
      }
      .mark.done {
        color: var(--green);
      }
      .splitter {
        cursor: col-resize;
        background: var(--line);
        background-clip: content-box;
        padding: 0 2.5px;
      }
      .splitter.folded {
        cursor: default;
      }
      .fold-bar {
        display: flex;
        justify-content: center;
        padding-top: 8px;
        background: var(--panel);
      }
      .fold-bar button {
        padding: 4px;
      }
      .col-tools.right {
        display: flex;
        justify-content: flex-start;
        padding: 8px 8px 0;
      }
      .col-tools button,
      .fold-column {
        padding: 4px;
      }
      .tree-tools .fold-column {
        margin-right: auto;
      }
      .splitter:not(.folded):hover,
      .splitter.dragging {
        background-color: var(--accent);
        padding: 0 1.5px;
      }
      .pane {
        display: grid;
        gap: 14px;
        padding: 16px 20px 40px;
        align-content: start;
      }
      .phead {
        display: flex;
        gap: 10px;
        align-items: center;
        --icon-size: 22px;
      }
      .phead .path {
        font-size: 12px;
        color: var(--muted);
      }
      .overview {
        list-style: none;
        margin: 0;
        padding: 0;
        display: grid;
        gap: 6px;
      }
      .overview li {
        display: flex;
        gap: 10px;
        align-items: center;
        padding: 10px 12px;
        border-radius: 10px;
        background: var(--panel);
        border: 1px solid var(--line);
        cursor: pointer;
      }
      .overview li:hover {
        background: var(--hover);
      }
      .overview .label {
        flex: 1;
        font-weight: 600;
      }
      .overview .state {
        font-size: 12px;
        color: var(--muted);
      }
      .overview li.done .state {
        color: var(--green);
      }
      .overview li.next {
        border-color: var(--accent);
      }
      .overview li.next .state {
        color: var(--accent-text);
      }
      .next-step {
        justify-self: start;
      }
      @media (max-width: 900px) {
        .cols {
          grid-template-columns: 1fr;
          overflow: auto;
        }
        .splitter {
          display: none;
        }
      }
    `,
  ];
}

// name -> (props) => template; the step and settings components add themselves here
export const VIEWS = {};

customElements.define("pvc-editor", PvcEditor);
