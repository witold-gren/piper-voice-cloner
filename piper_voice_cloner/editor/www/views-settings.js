// Settings: ElevenLabs, Home Assistant and the machine, look and language, and each voice's voice.yaml
// (form or YAML, undo/redo, save with history - the same model as the other editors).
import { css, html, nothing } from "./vendor/lit-all.min.js";
import { Document, isScalar, parseDocument } from "./vendor/yaml.js";
import { VIEWS } from "./editor-app.js";
import { StepView } from "./parts.js";
import { call, get, post } from "./api.js";
import { dialogStyles } from "./styles.js";

const UNDO_LIMIT = 200;
const COALESCE_MS = 1500; // typing in one field is one undo step
const DRAFT_SAVE_MS = 800; // the draft goes to the server this long after the last change

// the voice.yaml fields shown as a form: [path, kind, min, max, step]
export const VOICE_FIELDS = [
  ["general", [
    [["workflow"], "select", ["clone", "import"]],
    [["target_clips"], "number", 10, 100000, 1],
  ]],
  ["synthesis", [
    [["synthesis", "overgenerate"], "number", 1, 3, 0.05],
  ]],
  ["quality", [
    [["quality", "max_cer"], "number", 0, 1, 0.005],
    [["quality", "min_similarity"], "number", 0, 1, 0.01],
    [["quality", "mos_drop_fraction"], "number", 0, 0.5, 0.01],
    [["quality", "min_seconds_per_char"], "number", 0, 1, 0.005],
    [["quality", "max_seconds_per_char"], "number", 0, 1, 0.005],
  ]],
  ["train", [
    [["train", "max_epochs"], "number", 1, 100000, 1],
    [["train", "batch_size"], "number", 1, 256, 1],
    [["train", "num_workers"], "number", 0, 64, 1],
    [["train", "validation_split"], "number", 0, 0.5, 0.01],
  ]],
]; // prettier-ignore

/** The same text with one value changed (comments and order kept). */
/** The same text with one value changed. A value already in the file is replaced where it stands
 * (Scalar.range): comments, order and alignment stay and the diff shows exactly that one line. A new
 * or removed key goes through the document (the file is written again around it). */
export function setYamlValue(text, path, value) {
  const doc = parseDocument(text);
  const node = doc.getIn(path, true);
  if (value !== "" && value != null && isScalar(node) && node.range) {
    const [start, end] = node.range;
    const written = new Document(value).toString().trim();
    return text.slice(0, start) + written + text.slice(end);
  }
  if (value === "" || value == null) doc.deleteIn(path);
  else doc.setIn(path, value);
  return doc.toString();
}

/** The first error of the text as YAML, or null (the library collects errors instead of throwing). */
export function yamlError(text) {
  try {
    const doc = parseDocument(text);
    if (doc.errors.length) return doc.errors[0].message.split("\n")[0];
    const value = doc.toJS();
    return value && typeof value === "object" && !Array.isArray(value) ? null : "voice.yaml is a mapping";
  } catch (err) {
    return err.message;
  }
}

export function yamlValue(text, path) {
  try {
    return parseDocument(text).getIn(path);
  } catch {
    return undefined;
  }
}

/** Lines removed (-) and added (+) between two texts (a small LCS: voice.yaml has tens of lines). */
export function lineDiff(before, after) {
  const a = before.split("\n");
  const b = after.split("\n");
  const table = Array.from({ length: a.length + 1 }, () => new Array(b.length + 1).fill(0));
  for (let i = a.length - 1; i >= 0; i--)
    for (let j = b.length - 1; j >= 0; j--)
      table[i][j] = a[i] === b[j] ? table[i + 1][j + 1] + 1 : Math.max(table[i + 1][j], table[i][j + 1]);
  const out = [];
  let i = 0;
  let j = 0;
  while (i < a.length || j < b.length) {
    if (i < a.length && j < b.length && a[i] === b[j]) {
      i++;
      j++;
    } else if (i < a.length && (j >= b.length || table[i + 1][j] >= table[i][j + 1])) out.push(["-", a[i++]]);
    else out.push(["+", b[j++]]);
  }
  return out;
}

// --- each voice's settings ---------------------------------------------------------------------------

class PvcVoiceSettings extends StepView {
  static properties = {
    ...StepView.properties,
    _text: { state: true },
    _tab: { state: true },
    _past: { state: true },
    _future: { state: true },
    _dialog: { state: true },
    _notice: { state: true },
    _draftState: { state: true },
    _draftError: { state: true },
    _saveError: { state: true },
  };

  constructor() {
    super();
    this._tab = "form";
    this._past = [];
    this._future = [];
    this._onKey = (event) => this._key(event);
  }

  connectedCallback() {
    super.connectedCallback();
    window.addEventListener("keydown", this._onKey);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    window.removeEventListener("keydown", this._onKey);
    clearTimeout(this._draftTimer);
  }

  _path() {
    return `/api/voices/${encodeURIComponent(this.voice.name)}/settings`;
  }

  async load() {
    const data = await get(this._path());
    if (this._forVoice !== this.voice.name) {
      this._forVoice = this.voice.name;
      // a draft left on the server (another browser, yesterday) comes back as it was
      this._text = data.draft?.text ?? data.yaml;
      this._base = data.draft?.base || data.hash;
      this._draftState = data.draft ? "saved" : null;
      this._past = [];
      this._future = [];
    }
    return data;
  }

  get changed() {
    return this.data && this._text !== this.data.yaml;
  }

  _edit(text, field) {
    const now = Date.now();
    const coalesce = field && field === this._lastField && now - this._lastAt < COALESCE_MS;
    if (!coalesce) this._past = [...this._past, this._text].slice(-UNDO_LIMIT);
    this._future = [];
    this._lastField = field;
    this._lastAt = now;
    this._setText(text);
  }

  _setText(text) {
    this._text = text;
    this._notice = null;
    clearTimeout(this._draftTimer);
    this._draftState = "saving";
    this._draftTimer = setTimeout(() => this._saveDraft(), DRAFT_SAVE_MS);
  }

  /** One draft save at a time: a change made while one is on its way goes in one save after it
   * (a slow server must not get saves that overtake each other). A failure says so and the next
   * change tries again - no loop. */
  _saveDraft() {
    if (this._draftSaving) {
      this._draftDirty = true;
      return this._draftSaving;
    }
    this._draftSaving = (async () => {
      try {
        do {
          this._draftDirty = false;
          const text = this._text;
          if (text === this.data.yaml) await call(`${this._path()}/draft`, { method: "DELETE" });
          else await call(`${this._path()}/draft`, { method: "PUT", body: { text, base: this._base } });
        } while (this._draftDirty);
        this._draftState = this._text === this.data.yaml ? null : "saved";
        this._draftError = null;
      } catch (err) {
        this._draftState = "error";
        this._draftError = err.message;
      } finally {
        this._draftSaving = null;
      }
    })();
    return this._draftSaving;
  }

  _undo() {
    if (!this._past.length) return;
    this._future = [this._text, ...this._future];
    this._setText(this._past.at(-1));
    this._past = this._past.slice(0, -1);
    this._lastField = null;
  }

  _redo() {
    if (!this._future.length) return;
    this._past = [...this._past, this._text];
    this._setText(this._future[0]);
    this._future = this._future.slice(1);
    this._lastField = null;
  }

  _key(event) {
    const mod = event.metaKey || event.ctrlKey;
    if (!mod) return;
    const key = event.key.toLowerCase();
    const inField = ["INPUT", "TEXTAREA", "SELECT"].includes(event.composedPath()[0]?.tagName);
    if (key === "s") {
      event.preventDefault();
      if (this.changed && !yamlError(this._text)) this._dialog = "save";
    } else if (key === "z" && !inField) {
      event.preventDefault();
      if (event.shiftKey) this._redo();
      else this._undo();
    } else if (key === "y" && !inField) {
      event.preventDefault();
      this._redo();
    }
  }

  async _discard() {
    clearTimeout(this._draftTimer);
    await call(`${this._path()}/draft`, { method: "DELETE" });
    this._past = [...this._past, this._text];
    this._text = this.data.yaml;
    this._base = this.data.hash;
    this._draftState = null;
  }

  async _save(force = false) {
    this.busy = true;
    this._saveError = null;
    clearTimeout(this._draftTimer);
    await this._draftSaving;
    const note = this.renderRoot.querySelector("[data-save-note]")?.value ?? "";
    try {
      this.data = await post(this._path(), { text: this._text, note, base: this._base, force });
      this._text = this.data.yaml;
      this._base = this.data.hash;
      this._draftState = null;
      this._dialog = null;
      this.error = null;
      this._notice = this._t("settings_saved");
      this.editor?._poll();
    } catch (err) {
      this._saveError = { code: err.code, message: err.message };
    } finally {
      this.busy = false;
    }
  }

  async _rename() {
    const name = this.renderRoot.querySelector("[data-rename-name]").value;
    const piper = this.renderRoot.querySelector("[data-rename-piper]").value;
    try {
      const { name: renamed } = await post(`/api/voices/${encodeURIComponent(this.voice.name)}/rename`, { name, piper_name: piper });
      this.editor._select(`voice/${renamed}/settings`);
      await this.editor._poll();
    } catch (err) {
      this.error = this._t(err.code ?? "", {}, err.message);
    }
  }

  render() {
    if (!this.data) return this.head("mdi:cog-outline", this._t("voice_settings"), this._t("voice_settings_info"), "settings");
    const parsed = yamlError(this._text);
    const state = ["saving", "error"].includes(this._draftState) ? this._draftState : this.changed ? "draft" : "clean";
    return html`
      ${this.head("mdi:cog-outline", this._t("voice_settings"), this._t("voice_settings_info"), "settings")}
      <div class="bar">
        <span class="pill ${state === "clean" ? "" : state === "error" ? "failed" : "draft"}"
          data-settings-state=${state === "clean" ? "clean" : state === "error" ? "error" : "draft"}
          title=${this._draftError ?? ""}>
          <pvc-icon icon=${state === "clean" ? "mdi:check" : state === "error" ? "mdi:alert-circle" : "mdi:pencil"}></pvc-icon>${this._t(`state_${state}`)}
        </span>
        <button class="ghost" data-undo title=${this._t("undo")} ?disabled=${!this._past.length} @click=${this._undo}><pvc-icon icon="mdi:undo"></pvc-icon></button>
        <button class="ghost" data-redo title=${this._t("redo")} ?disabled=${!this._future.length} @click=${this._redo}><pvc-icon icon="mdi:redo"></pvc-icon></button>
        ${this.changed ? html`<button class="ghost" data-discard @click=${this._discard}>${this._t("discard")}</button>` : nothing}
        <span class="grow"></span>
        <button class="ghost" data-history @click=${() => (this._dialog = "history")}><pvc-icon icon="mdi:history"></pvc-icon>${this._t("history")}</button>
        <button class="primary" data-save ?disabled=${!this.changed || this.busy || parsed} @click=${() => ((this._saveError = null), (this._dialog = "save"))}>
          <pvc-icon icon="mdi:content-save"></pvc-icon>${this._t("save")}</button>
      </div>
      ${this._notice && !this.changed ? html`<p class="ok" data-settings-notice>${this._notice}</p>` : nothing}
      <div class="tabs">
        <button class=${this._tab === "form" ? "on" : ""} data-tab="form" @click=${() => (this._tab = "form")}>${this._t("tab_form")}</button>
        <button class=${this._tab === "yaml" ? "on" : ""} data-tab="yaml" @click=${() => (this._tab = "yaml")}>YAML</button>
      </div>
      ${this._tab === "form" ? this._renderForm(parsed) : this._renderYaml(parsed)}
      <section class="card" data-rename>
        <h3>${this._t("rename_title")}</h3>
        <div class="grid2">
          <label class="field"><span>${this._t("new_voice_name")}</span><input data-rename-name .value=${this.voice.name} /></label>
          <label class="field"><span>${this._t("new_voice_piper")}</span><input data-rename-piper .value=${this.voice.piper_name ?? ""} placeholder="pl_PL-…" /></label>
        </div>
        <div class="row" style="margin-top: 10px"><span class="hint grow">${this._t("rename_hint")}</span>
          <button data-rename-run ?disabled=${this.running} @click=${this._rename}>${this._t("rename_run")}</button></div>
      </section>
      ${this._dialog === "history" ? this._renderHistory() : nothing}
      ${this._dialog === "save" ? this._renderSave() : nothing}
    `;
  }

  _renderForm(parsed) {
    if (parsed) return html`<p class="bad" data-yaml-error>${this._t("yaml_broken", { error: parsed })}</p>`;
    return html`${VOICE_FIELDS.map(
      ([section, fields]) => html`<section class="card" data-form-section=${section}>
        <h3>${this._t(`field_section_${section}`)}</h3>
        <div class="grid2">
          ${fields.map(([path, kind, ...limits]) => {
            const key = path.join(".");
            const value = yamlValue(this._text, path);
            const change = (event) => {
              const raw = event.target.value;
              const typed = kind === "number" ? (raw === "" ? "" : Number(raw)) : raw;
              this._edit(setYamlValue(this._text, path, typed), key);
            };
            return html`<label class="field" data-field=${key}>
              <span>${this._t(`field_${key.replace(".", "_")}`)}</span>
              ${kind === "select"
                ? html`<select @change=${change}>${limits[0].map((option) => html`<option value=${option} ?selected=${option === value}>${this._t(`workflow_${option}`, {}, option)}</option>`)}</select>`
                : html`<input type="number" min=${limits[0]} max=${limits[1]} step=${limits[2]} .value=${value == null ? "" : String(value)} @input=${change} />`}
              <span class="hint">${this._t(`field_${key.replace(".", "_")}_hint`, {}, "")}</span>
            </label>`;
          })}
        </div>
      </section>`,
    )}`;
  }

  _renderYaml(parsed) {
    return html`<section class="card">
      <textarea data-yaml spellcheck="false" .value=${this._text} @input=${(event) => this._edit(event.target.value, "yaml")}></textarea>
      ${parsed ? html`<p class="bad" data-yaml-error>${this._t("yaml_broken", { error: parsed })}</p>` : html`<p class="hint">${this._t("yaml_hint")}</p>`}
    </section>`;
  }

  _renderSave() {
    const diff = lineDiff(this.data.yaml, this._text);
    const conflict = this._saveError?.code === "conflict";
    return html`<div class="scrim" @click=${(event) => event.target === event.currentTarget && (this._dialog = null)}>
      <div class="box" data-save-dialog>
        <h2>${this._t("save_title")}</h2>
        <h3>${this._t("save_changes", { count: diff.filter(([sign]) => sign === "+").length })}</h3>
        <pre class="diff" data-diff>${diff.map(([sign, line]) => html`<span class=${sign === "+" ? "added" : "removed"} data-diff-line=${sign}>${sign} ${line}\n</span>`)}</pre>
        <label class="field"><span>${this._t("save_note")}</span><input data-save-note placeholder=${this._t("save_note_hint")} /></label>
        ${this._saveError ? html`<p class="bad" data-save-error>${conflict ? this._t("conflict") : this._t("error", { message: this._t(this._saveError.code ?? "", {}, this._saveError.message) })}</p>` : nothing}
        <div class="actions">
          <button class="ghost" @click=${() => (this._dialog = null)}>${this._t("cancel")}</button>
          ${conflict
            ? html`<button class="danger" data-save-force ?disabled=${this.busy} @click=${() => this._save(true)}>${this._t("save_anyway")}</button>`
            : html`<button class="primary" data-save-confirm ?disabled=${this.busy} @click=${() => this._save(false)}><pvc-icon icon="mdi:content-save"></pvc-icon>${this._t("save")}</button>`}
        </div>
      </div>
    </div>`;
  }

  _renderHistory() {
    const history = this.data.history ?? [];
    return html`<div class="scrim" @click=${(event) => event.target === event.currentTarget && (this._dialog = null)}>
      <div class="box" data-history-dialog>
        <h2>${this._t("history_title")}</h2>
        ${history.length
          ? html`<ul class="versions">${history.map(
              (item) => html`<li>
                <span><span class="mono">${item.saved}</span>${item.note ? html` · <span class="hint">${item.note}</span>` : nothing}</span>
                <button data-restore=${item.file} @click=${() => {
                  this._edit(item.text);
                  this._dialog = null;
                }}>${this._t("history_restore")}</button>
              </li>`,
            )}</ul>
            <p class="hint">${this._t("history_restore_hint")}</p>`
          : html`<p class="muted">${this._t("history_empty")}</p>`}
        <div class="actions"><button class="ghost" @click=${() => (this._dialog = null)}>${this._t("close")}</button></div>
      </div>
    </div>`;
  }

  static styles = [
    StepView.styles,
    dialogStyles,
    css`
      .bar {
        display: flex;
        gap: 8px;
        align-items: center;
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
      }
      .pill.draft {
        color: var(--amber);
        background: rgba(255, 179, 64, 0.15);
      }
      .pill.failed {
        color: var(--red);
        background: rgba(255, 69, 58, 0.15);
      }
      .tabs {
        display: flex;
        gap: 4px;
        border-bottom: 1px solid var(--line);
      }
      .tabs button {
        border-radius: 0;
        background: transparent;
        color: var(--muted);
        border-bottom: 2px solid transparent;
      }
      .tabs button.on {
        color: var(--text);
        border-bottom-color: var(--accent);
      }
      textarea {
        width: 100%;
        min-height: 420px;
        font: 13px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace;
        resize: vertical;
      }
      .ok {
        margin: 0;
        color: var(--green);
      }
      .versions {
        list-style: none;
        margin: 0;
        padding: 0;
        display: grid;
        gap: 6px;
      }
      .versions li {
        display: flex;
        justify-content: space-between;
        align-items: center;
      }
      .diff {
        margin: 0;
        max-height: 300px;
        overflow: auto;
        padding: 10px 12px;
        border-radius: 8px;
        background: var(--field);
        font: 12px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace;
      }
      .diff .added {
        color: var(--green);
      }
      .diff .removed {
        color: var(--red);
      }
    `,
  ];
}

customElements.define("pvc-voice-settings", PvcVoiceSettings);

// --- ElevenLabs ------------------------------------------------------------------------------------

class PvcSettingsElevenlabs extends StepView {
  static properties = { ...StepView.properties, _notice: { state: true } };

  load() {
    return get("/api/settings");
  }

  async _save(key) {
    try {
      const answer = await post("/api/settings/elevenlabs", { key });
      this.data = { ...this.data, elevenlabs: answer };
      this._notice = answer.key ? this._t("el_key_saved") : this._t("el_key_removed");
      this.renderRoot.querySelector("[data-el-key]").value = "";
    } catch (err) {
      this.error = err.message;
    }
  }

  render() {
    const saved = this.data?.elevenlabs?.key;
    return html`
      ${this.head("mdi:account-voice", this._t("settings_elevenlabs"), this._t("el_settings_info"), "synthesize")}
      <section class="card">
        <p data-el-key-state>${saved ? this._t("el_key_ready") : this._t("el_key_missing")}</p>
        <div class="row">
          <input class="grow" type="password" autocomplete="off" data-el-key placeholder=${saved ? "••••••••" : "sk_…"} />
          <button class="primary" data-el-key-save @click=${() => this._save(this.renderRoot.querySelector("[data-el-key]").value)}>${this._t("save")}</button>
          ${saved ? html`<button class="ghost danger" data-el-key-remove @click=${() => this._save("")}>${this._t("remove")}</button>` : nothing}
        </div>
        <p class="hint">${this._t("el_key_hint")}</p>
        ${this._notice ? html`<p class="hint" data-el-notice>${this._notice}</p>` : nothing}
      </section>
    `;
  }
}
customElements.define("pvc-settings-elevenlabs", PvcSettingsElevenlabs);

// --- Home Assistant and the machine -----------------------------------------------------------------

class PvcSettingsHomeAssistant extends StepView {
  static properties = { ...StepView.properties, _entities: { state: true }, _notice: { state: true } };

  load() {
    return get("/api/settings");
  }

  async _saveConnection() {
    const url = this.renderRoot.querySelector("[data-ha-url]").value;
    const token = this.renderRoot.querySelector("[data-ha-token]").value;
    try {
      this.data = await post("/api/settings/ha", { url, token });
      this.renderRoot.querySelector("[data-ha-token]").value = "";
      this._notice = this._t("ha_saved");
      this.error = null;
    } catch (err) {
      this.error = err.message;
    }
  }

  async _remove() {
    if (!window.confirm(this._t("ha_remove_confirm"))) return;
    this.data = await call("/api/settings/ha", { method: "DELETE" });
    this._notice = this._t("ha_removed");
  }

  async _suggest() {
    this._entities = { loading: true };
    try {
      this._entities = await get("/api/settings/ha/entities");
    } catch (err) {
      this._entities = { error: err.message };
    }
  }

  async _savePower() {
    const value = (name) => this.renderRoot.querySelector(`[data-power-${name}]`).value;
    try {
      this.data = await post("/api/settings/power", { switch: value("switch"), sensor: value("sensor"), off_watts: Number(value("watts")) || 5 });
      this._notice = this._t("power_saved");
      this.error = null;
    } catch (err) {
      this.error = err.message;
    }
  }

  render() {
    const ha = this.data?.ha ?? {};
    const powerSettings = this.data?.power ?? {};
    const entities = this._entities;
    const options = (list, current) => html`${current ? html`<option value=${current} selected>${current}</option>` : html`<option value="" selected>—</option>`}
      ${(list ?? []).filter((e) => e.id !== current).map((e) => html`<option value=${e.id}>${e.name ? `${e.name} (${e.id})` : e.id}</option>`)}`;
    const machine = this.state?.machine;
    return html`
      ${this.head("mdi:home-assistant", this._t("settings_home_assistant"), this._t("ha_info"), "settings")}
      <section class="card" data-ha>
        <h3>${this._t("ha_connection")}</h3>
        <div class="grid2">
          <label class="field"><span>${this._t("ha_url")}</span>
            <input data-ha-url .value=${ha.url ?? ""} placeholder="http://homeassistant.local:8123" /></label>
          <label class="field"><span>${this._t("ha_token")}</span>
            <input type="password" autocomplete="off" data-ha-token placeholder=${ha.token_rejected ? this._t("ha_token_rejected") : ha.token_saved ? this._t("ha_token_saved") : this._t("ha_token_placeholder")} />
            <span class="hint">${this._t("ha_token_hint")}</span></label>
        </div>
        <div class="row" style="margin-top: 10px">
          ${ha.token_rejected ? html`<span class="bad" data-ha-rejected>${this._t("ha_token_rejected")}</span>` : nothing}
          <span class="grow"></span>
          ${ha.token_saved ? html`<button class="ghost danger" data-ha-remove @click=${this._remove}>${this._t("remove")}</button>` : nothing}
          <button class="primary" data-ha-save @click=${this._saveConnection}>${this._t("ha_save")}</button>
        </div>
      </section>
      <section class="card" data-power>
        <h3>${this._t("power_title")}</h3>
        <p class="hint">${this._t("power_info")}</p>
        <div class="grid2">
          <label class="field"><span>${this._t("power_switch")}</span>
            <select data-power-switch>${options(entities?.switches, powerSettings.switch)}</select></label>
          <label class="field"><span>${this._t("power_sensor")}</span>
            <select data-power-sensor>${options(entities?.sensors, powerSettings.sensor)}</select></label>
          <label class="field"><span>${this._t("power_watts")}</span>
            <input type="number" min="1" max="100" step="0.5" data-power-watts .value=${String(powerSettings.off_watts ?? 5)} /></label>
        </div>
        <div class="row" style="margin-top: 10px">
          ${entities?.error ? html`<span class="bad">${entities.error}</span>` : nothing}
          ${entities?.count ? html`<span class="hint" data-power-found>${this._t("power_found", { switches: entities.switches.length, sensors: entities.sensors.length })}</span>` : nothing}
          <span class="grow"></span>
          <button data-power-suggest ?disabled=${!ha.token_saved || entities?.loading} @click=${this._suggest}><pvc-icon icon="mdi:magnify"></pvc-icon>${this._t("power_suggest")}</button>
          <button class="primary" data-power-save @click=${this._savePower}>${this._t("save")}</button>
        </div>
      </section>
      <section class="card" data-machine>
        <h3>${this._t("machine_title")}</h3>
        ${machine
          ? html`<p data-machine-state>${this._t(`machine_${machine.machine}`, {}, machine.machine)}${machine.watts != null ? ` · ${Math.round(machine.watts)} W` : ""}</p>
              ${machine.error ? html`<p class="bad">${machine.error}</p>` : nothing}`
          : html`<p class="muted">${this._t("machine_not_set")}</p>`}
        <p class="hint">${this._t("machine_off_hint")}</p>
        <div class="row"><span class="grow"></span>
          <button class="danger" data-machine-off ?disabled=${!this.state?.can_power_off || this.running}
            @click=${async () => {
              if (!window.confirm(this._t("machine_off_confirm"))) return;
              await this.run("/api/machine/off", {});
            }}><pvc-icon icon="mdi:power"></pvc-icon>${this._t("machine_power_off")}</button>
        </div>
      </section>
      ${this._notice ? html`<p class="hint" data-ha-notice>${this._notice}</p>` : nothing}
    `;
  }

  static styles = [StepView.styles, css`.bad { color: var(--red); }`];
}
customElements.define("pvc-settings-home-assistant", PvcSettingsHomeAssistant);

// --- look and language --------------------------------------------------------------------------------

class PvcSettingsEditor extends StepView {
  render() {
    const editor = this.editor;
    return html`
      ${this.head("mdi:palette-outline", this._t("settings_editor"), this._t("editor_settings_info"), "settings")}
      <section class="card">
        <div class="grid2">
          <div class="field"><span>${this._t("theme")}</span>
            <div class="seg" data-theme-choice>
              ${["auto", "light", "dark"].map((theme) => html`<button class=${editor._theme === theme ? "on" : ""} data-theme-option=${theme}
                @click=${() => editor._setTheme(theme)}>${this._t(`theme_${theme}`)}</button>`)}
            </div></div>
          <div class="field"><span>${this._t("language_choice")}</span>
            <div class="seg" data-language-choice>
              ${[["pl", "Polski"], ["en", "English"]].map(([code, name]) => html`<button class=${this.language === code ? "on" : ""} data-language-option=${code}
                @click=${() => editor._setLanguage(code)}>${name}</button>`)}
            </div></div>
        </div>
      </section>
      ${this.state?.login
        ? html`<section class="card"><div class="row"><span class="hint grow">${this._t("logout_hint")}</span>
            <button data-logout-settings @click=${() => this.editor._logout()}><pvc-icon icon="mdi:logout"></pvc-icon>${this._t("logout")}</button></div></section>`
        : nothing}
    `;
  }
}
customElements.define("pvc-settings-editor", PvcSettingsEditor);

VIEWS["step-settings"] = (p) => html`<pvc-voice-settings .voice=${p.voice} .language=${p.language} .state=${p.state} .editor=${p.editor}></pvc-voice-settings>`;
VIEWS["settings-elevenlabs"] = (p) => html`<pvc-settings-elevenlabs .language=${p.language} .state=${p.state} .editor=${p.editor}></pvc-settings-elevenlabs>`;
VIEWS["settings-home_assistant"] = (p) => html`<pvc-settings-home-assistant .language=${p.language} .state=${p.state} .editor=${p.editor}></pvc-settings-home-assistant>`;
VIEWS["settings-editor"] = (p) => html`<pvc-settings-editor .language=${p.language} .state=${p.state} .editor=${p.editor}></pvc-settings-editor>`;
