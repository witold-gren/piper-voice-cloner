// Parts every step view uses: the base class (loads its data, reloads after a job), the step head
// with its "?" into the guide, a list of players and listening to a training.
import { LitElement, css, html, nothing } from "./vendor/lit-all.min.js";
import { translate } from "./i18n.js";
import { base } from "./styles.js";
import { fileUrl, get, post } from "./api.js";
import { number } from "./format.js";
import "./icon.js";
import "./help.js";
import { lessonFor } from "./lessons.js";

// the guide's chapter for each part of the editor (docs/<lang>/...#anchor)
export const DOCS = {
  reference: "path-clone#recording",
  corpus: "path-clone#sentences",
  audition: "path-clone#audition",
  synthesize: "path-clone#generate",
  filter: "path-clone#filter",
  import: "path-import",
  train: "training",
  export: "export",
  base: "base-model",
  queue: "training#queue",
  settings: "installation#home-assistant",
};

export function docsUrl(language, key) {
  const [page, anchor] = (DOCS[key] ?? "").split("#");
  return `/docs/${language === "pl" ? "pl/" : ""}${page ? `${page}/` : ""}${anchor ? `#${anchor}` : ""}`;
}

/** A view of the middle column: `load()` fills `data`; it runs again when the voice changes and
 * when a job ends (so results show without a click). */
export class StepView extends LitElement {
  static properties = {
    voice: { attribute: false },
    language: {},
    state: { attribute: false },
    editor: { attribute: false },
    data: { state: true },
    error: { state: true },
    busy: { state: true },
  };

  _t(key, values, fallback) {
    return translate(this.language, key, values, fallback);
  }

  _jobKey() {
    const job = this.state?.jobs?.current ?? {};
    const side = this.state?.jobs?.side ?? {};
    return `${job.state}|${job.kind}|${job.started}|${side.state}|${side.started}`;
  }

  willUpdate(changed) {
    const voice = this.voice?.name;
    const key = this._jobKey();
    // views without a voice (base, jobs, settings) load once too
    if (!this._started || voice !== this._loadedVoice || key !== this._loadedKey) {
      const first = !this._started || voice !== this._loadedVoice;
      this._started = true;
      this._loadedVoice = voice;
      this._loadedKey = key;
      if (first) this.data = null;
      this._reload();
    }
  }

  async _reload() {
    try {
      this.data = await this.load();
      this.error = null;
    } catch (err) {
      this.error = err.message;
    }
  }

  load() {
    return null;
  }

  /** Start a job through the editor (it shows refusals, e.g. another job running). */
  async run(path, body) {
    this.busy = true;
    try {
      return await this.editor.run(path, body);
    } catch {
      return null;
    } finally {
      this.busy = false;
    }
  }

  get running() {
    return this.state?.jobs?.current?.state === "running";
  }

  /** The lesson of the place this view is (lessons.js), for "Show me step by step" in its "?". */
  _lesson() {
    const lesson = lessonFor(this.editor?._selected);
    return lesson ? { key: lesson.key, name: translate(this.language, `lesson_${lesson.key}_name`) } : null;
  }

  head(icon, title, info, docs) {
    return html`<div class="phead">
        <pvc-icon icon=${icon}></pvc-icon>
        <div class="grow">
          <strong>${title}</strong>
          ${this.voice ? html`<div class="path">${this.voice.name}</div>` : nothing}
        </div>
        <pvc-help data-step-help .language=${this.language} .heading=${title} .text=${info} .link=${docsUrl(this.language, docs)}
          .lesson=${this._lesson()}></pvc-help>
      </div>
      ${this.error ? html`<p class="bad" data-step-error>${this._t("error", { message: this.error })}</p>` : nothing}`;
  }

  static styles = [
    base,
    css`
      :host {
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
      .grow {
        flex: 1;
      }
      .docs {
        display: inline-flex;
        gap: 6px;
        align-items: center;
        color: var(--link);
        text-decoration: none;
        font-size: 13px;
        --icon-size: 16px;
      }
      .info {
        margin: 0;
        padding: 10px 14px;
        border-radius: 10px;
        background: rgba(79, 140, 255, 0.1);
        border: 1px solid rgba(79, 140, 255, 0.25);
      }
      .bad {
        margin: 0;
        color: var(--red);
      }
      .warn {
        margin: 0;
        padding: 10px 14px;
        border-radius: 10px;
        color: var(--warn-text);
        background: rgba(255, 179, 64, 0.12);
        border: 1px solid rgba(255, 179, 64, 0.3);
      }
      .grid2 {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 12px;
      }
      .row {
        display: flex;
        gap: 10px;
        align-items: center;
        flex-wrap: wrap;
      }
      .check {
        display: inline-flex;
        gap: 6px;
        align-items: center;
      }
      table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
      }
      th,
      td {
        text-align: left;
        padding: 6px 8px;
        border-bottom: 1px solid var(--line);
      }
      th {
        color: var(--muted);
        font-weight: 600;
        font-size: 12px;
      }
      td.num {
        text-align: right;
        font-variant-numeric: tabular-nums;
      }
      .mono {
        font: 12px ui-monospace, SFMono-Regular, Menlo, monospace;
      }
      a.file {
        color: var(--link);
      }
      @media (max-width: 700px) {
        :host {
          padding: 12px;
        }
      }
    `,
  ];
}

/** Audio players with the sentence each one reads. */
export function clips(list, language, empty) {
  if (!list?.length) return html`<p class="muted">${empty ?? ""}</p>`;
  return html`<ul class="clips" data-clips>
    ${list.map(
      (clip) => html`<li>
        <span class="text">${clip.text}</span>
        <audio controls preload="none" src=${fileUrl(clip.url)}></audio>
      </li>`,
    )}
  </ul>`;
}

export const clipStyles = css`
  .clips {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 8px;
  }
  .clips li {
    display: grid;
    gap: 4px;
  }
  .clips .text {
    font-size: 13px;
  }
  .clips audio {
    width: 100%;
    height: 32px;
  }
`;

/** Listening to a training: epochs with their quality, the test sentences of one epoch, a ZIP. */
export class PvcListen extends LitElement {
  static properties = {
    language: {},
    target: {},
    // "" = the current training, else an earlier one kept in train/runs/ (read only, no ZIP)
    run: {},
    refresh: {},
    _data: { state: true },
    _epoch: { state: true },
    _zip: { state: true },
    _busy: { state: true },
  };

  _t(key, values) {
    return translate(this.language, key, values);
  }

  willUpdate(changed) {
    if (changed.has("target") || changed.has("run")) this._epoch = null;
    if (changed.has("target") || changed.has("run") || changed.has("refresh")) this._load();
  }

  async _load() {
    if (!this.target) return;
    const query = new URLSearchParams({ target: this.target });
    if (this._epoch != null) query.set("epoch", this._epoch);
    if (this.run) query.set("run", this.run);
    this._data = await get(`/api/listen?${query}`).catch(() => null);
  }

  async _downloadZip() {
    this._busy = true;
    try {
      const { url } = await post(`/api/listen/zip?target=${encodeURIComponent(this.target)}`);
      this._zip = fileUrl(url);
      window.location.href = this._zip;
    } catch (err) {
      this._zip = null;
    } finally {
      this._busy = false;
    }
  }

  render() {
    const data = this._data;
    if (!data?.epochs?.length) return html`<p class="muted" data-listen-none>${this._t("listen_none")}</p>`;
    const mos = (value) => (value == null ? "—" : number(value, this.language, 2));
    const s = data.summary;
    return html`
      ${s
        ? html`<p data-listen-summary>
            ${this._t("listen_summary", { last: s.last, mos: mos(s.mos), best: mos(s.best), best_epoch: s.best_epoch ?? "—" })}
          </p>`
        : nothing}
      <div class="row">
        <label class="field grow">
          <span>${this._t("listen_epoch")}</span>
          <select data-listen-epoch @change=${(event) => ((this._epoch = Number(event.target.value)), this._load())}>
            ${data.epochs.map(
              (item) => html`<option value=${item.epoch} ?selected=${item.epoch === data.chosen}>
                ${this._t("listen_item", { epoch: item.epoch, mos: mos(item.mos) })}${item.saved ? ` · ${this._t("listen_saved")}` : ""}
              </option>`,
            )}
          </select>
        </label>
        ${this.run
          ? nothing
          : html`<button data-listen-zip ?disabled=${this._busy} @click=${this._downloadZip}>
              <pvc-icon icon="mdi:download"></pvc-icon>${this._t("listen_download")}
            </button>`}
      </div>
      ${clips(data.samples, this.language)}
      <p class="hint">${this._t("listen_help")}</p>
    `;
  }

  static styles = [
    base,
    clipStyles,
    css`
      :host {
        display: grid;
        gap: 10px;
      }
      p {
        margin: 0;
      }
      .row {
        display: flex;
        gap: 10px;
        align-items: end;
      }
      .grow {
        flex: 1;
      }
    `,
  ];
}

customElements.define("pvc-listen", PvcListen);
