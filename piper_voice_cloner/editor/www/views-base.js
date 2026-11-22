// The own Polish base (bazowy-pl): prepare its data, rate the recordings, train, compare, choose.
import { css, html, nothing } from "./vendor/lit-all.min.js";
import { VIEWS } from "./editor-app.js";
import { StepView, clipStyles, clips } from "./parts.js";
import { fileUrl, get } from "./api.js";
import { number } from "./format.js";
import "./chart.js";
import { ask } from "./confirm.js";

class BaseView extends StepView {
  load() {
    return get("/api/base");
  }

  readyNote() {
    const data = this.data;
    if (!data) return nothing;
    return data.ready
      ? html`<p class="ok" data-base-ready><pvc-icon icon="mdi:check-circle"></pvc-icon>${this._t("base_ready", { path: data.bases_dir })}</p>`
      : html`<p class="warn" data-base-missing-steps>${this._t("base_missing_steps")}</p>`;
  }

  static styles = [
    StepView.styles,
    clipStyles,
    css`
      .ok {
        margin: 0;
        display: flex;
        gap: 6px;
        align-items: center;
        color: var(--green);
      }
      .tiles {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 10px;
      }
      .tile {
        padding: 10px 12px;
        border-radius: 10px;
        background: var(--panel2);
      }
      .tile strong {
        display: block;
        font-size: 22px;
        font-variant-numeric: tabular-nums;
      }
    `,
  ];
}

class PvcBasePrepare extends BaseView {
  static properties = { ...BaseView.properties, _folder: { state: true } };

  render() {
    const sources = this.data?.sources ?? [];
    const folder = this._folder ?? sources[0]?.folder ?? "";
    return html`
      ${this.head("mdi:database-cog-outline", this._t("base_prepare"), this._t("base_prepare_info"), "base")}
      ${this.readyNote()}
      <section class="card">
        <div class="grid2">
          <label class="field"><span>${this._t("base_source")}</span>
            <select data-base-source @change=${(event) => (this._folder = event.target.value)}>
              ${sources.map((item) => html`<option value=${item.folder} ?selected=${item.folder === folder}>${this._t("base_source_item", { name: item.name, clips: number(item.clips, this.language) })}</option>`)}
            </select>
            <span class="hint">${this._t("base_source_hint")}</span></label>
          <label class="field"><span>${this._t("base_folder")}</span>
            <input data-base-folder .value=${folder} @change=${(event) => (this._folder = event.target.value)} />
            <span class="hint">${this._t("base_folder_hint")}</span></label>
          <label class="field"><span>${this._t("base_audio_dir")}</span>
            <input data-base-audio-dir placeholder="wav" /></label>
        </div>
        <div class="row" style="margin-top: 12px">
          <span class="grow"></span>
          <button class="primary" data-run-base-prepare ?disabled=${this.busy || this.running || !folder}
            @click=${() => this.run("/api/base/prepare", { folder, audio_dir: this.renderRoot.querySelector("[data-base-audio-dir]").value })}>
            <pvc-icon icon="mdi:play"></pvc-icon>${this._t("base_prepare_run")}
          </button>
        </div>
        ${this.data?.dataset ? html`<p class="hint" data-base-dataset>${this._t("base_dataset_ready")}</p>` : nothing}
      </section>
    `;
  }
}
customElements.define("pvc-base-prepare", PvcBasePrepare);

/** The numbers of a scoring: middle, spread, good share, clips under each level, worst and best clips. */
export function scoreResults(view, score, summaryKey = "score_summary") {
  if (!score) return nothing;
  const pct = (value) => `${Math.round(value * 100)}%`;
  const below = Object.entries(score.below ?? {});
  return html`<section class="card" data-score>
    <div class="tiles">
      <div class="tile"><span class="hint">${view._t("score_median")}</span><strong>${number(score.median, view.language, 2)}</strong></div>
      <div class="tile"><span class="hint">${view._t("score_p10")}</span><strong>${number(score.p10, view.language, 2)}</strong></div>
      <div class="tile"><span class="hint">${view._t("score_p90")}</span><strong>${number(score.p90, view.language, 2)}</strong></div>
      <div class="tile"><span class="hint">${view._t("score_good", { good: number(score.good_level, view.language, 1) })}</span><strong>${pct(score.good)}</strong></div>
    </div>
    <p>${view._t(summaryKey, { count: number(score.count, view.language), total: number(score.total, view.language), median: number(score.median, view.language, 2) })}</p>
    ${below.length
      ? html`<p data-score-below>${below.map(([level, count], index) => html`${index ? " · " : ""}${view._t("score_below", { level: number(Number(level), view.language, 1), count: number(count, view.language) })}`)}</p>`
      : nothing}
    <div class="grid2">
      <div><h3>${view._t("score_worst")}</h3>${clips(score.worst, view.language)}</div>
      <div><h3>${view._t("score_best")}</h3>${clips(score.best, view.language)}</div>
    </div>
  </section>`;
}

class PvcBaseScore extends BaseView {
  render() {
    const score = this.data?.score;
    const side = this.state?.jobs?.side ?? {};
    return html`
      ${this.head("mdi:star-check-outline", this._t("base_score"), this._t("score_info"), "base")}
      <section class="card">
        <div class="row">
          <label class="field"><span>${this._t("score_sample")}</span>
            <input type="number" min="0" value="300" data-score-sample style="width: 140px" />
            <span class="hint">${this._t("score_sample_hint")}</span></label>
          <span class="grow"></span>
          <button class="primary" data-run-score ?disabled=${this.busy || side.state === "running" || !this.data?.dataset}
            @click=${() => this.run("/api/base/score", { sample: Number(this.renderRoot.querySelector("[data-score-sample]").value) || 0 })}>
            <pvc-icon icon="mdi:play"></pvc-icon>${this._t("score_run")}
          </button>
        </div>
        ${this.data && !this.data.dataset ? html`<p class="warn">${this._t("base_no_dataset")}</p>` : nothing}
        ${side.state === "running" && side.kind === "base-score" ? html`<p class="hint" data-score-running>${this._t("score_running")}</p>` : nothing}
      </section>
      ${scoreResults(this, score)}
    `;
  }
}
customElements.define("pvc-base-score", PvcBaseScore);

/** The recordings of a voice rated with UTMOS; every score is kept, a later run rates only new clips.
 * Below the results: what a level would keep (live, from every score), taking weak clips out, and
 * every scored clip in a table (sorted, filtered by the level, one page at a time, each to listen to). */
const CLIPS_PAGE = 50;

class PvcStepScore extends BaseView {
  static properties = {
    ...BaseView.properties,
    _level: { state: true },
    _best: { state: true },
    _where: { state: true },
    _order: { state: true },
    _onlyBelow: { state: true },
    _offset: { state: true },
    _clips: { state: true },
    _playing: { state: true },
  };

  constructor() {
    super();
    this._level = "3.0";
    this._best = "";
    this._where = "dataset";
    this._order = "asc";
    this._onlyBelow = false;
    this._offset = 0;
  }

  async load() {
    const data = await get(`/api/voices/${encodeURIComponent(this.voice.name)}/score`);
    this._loadClips();
    return data;
  }

  async _loadClips() {
    const query = new URLSearchParams({ where: this._where, order: this._order, offset: this._offset, limit: CLIPS_PAGE });
    const level = Number(this._level);
    if (this._onlyBelow && level > 0) query.set("below", level);
    this._clips = await get(`/api/voices/${encodeURIComponent(this.voice.name)}/clips?${query}`).catch(() => null);
  }

  _setTable(change) {
    Object.assign(this, change);
    if (!("_offset" in change)) this._offset = 0;
    this._loadClips();
  }

  /** What taking out at the level (or keeping the best) leaves: kept, taken out, short of the target. */
  _preview() {
    const values = this.data?.values ?? [];
    const total = this.data?.clips ?? 0;
    const unscored = total - values.length;
    let kept;
    if (this._best) kept = Math.min(Number(this._best), values.length) + 0;
    else kept = values.filter((value) => value >= Number(this._level)).length + unscored;
    return { kept, removed: total - kept, short: Math.max((this.data?.target ?? 0) - kept, 0) };
  }

  _play(url) {
    const audio = this.renderRoot.querySelector("audio[data-clip-player]");
    if (!audio) return;
    if (this._playing === url && !audio.paused) {
      audio.pause();
      this._playing = null;
      return;
    }
    audio.src = fileUrl(url);
    audio.play().catch(() => {});
    this._playing = url;
  }

  render() {
    const side = this.state?.jobs?.side ?? {};
    const running = side.state === "running" && side.kind === "score";
    const name = encodeURIComponent(this.voice.name);
    return html`
      ${this.head("mdi:star-check-outline", this._t("step_score"), this._t("voice_score_info"), "score")}
      <section class="card">
        <div class="row">
          <label class="field"><span>${this._t("score_sample")}</span>
            <input type="number" min="0" value="0" data-score-sample style="width: 140px" />
            <span class="hint">${this._t("voice_score_sample_hint")}</span></label>
          <span class="grow"></span>
          <button class="primary" data-run-score ?disabled=${this.busy || side.state === "running" || !this.data?.dataset}
            @click=${() => this.run(`/api/voices/${name}/score`, { sample: Number(this.renderRoot.querySelector("[data-score-sample]").value) || 0 })}>
            <pvc-icon icon="mdi:play"></pvc-icon>${this._t("score_run")}
          </button>
        </div>
        <p class="hint" data-score-kept>${this._t("voice_score_kept")}</p>
        ${this.data && !this.data.dataset ? html`<p class="warn">${this._t("train_no_dataset")}</p>` : nothing}
        ${running ? html`<p class="hint" data-score-running>${this._t("score_running")}</p>` : nothing}
      </section>
      ${scoreResults(this, this.data?.score, "voice_score_summary")}
      ${this.data?.score ? this._renderPrune() : nothing}
      ${this._clips && (this._clips.total || this._where === "out" || this._onlyBelow) ? this._renderClips() : nothing}
      <audio data-clip-player @ended=${() => (this._playing = null)}></audio>
    `;
  }

  /** Weak clips out of the dataset (kept on disk, metadata.csv before kept next to it). */
  _renderPrune() {
    const data = this.data;
    const short = Math.max(data.target - data.clips, 0);
    const preview = this._preview();
    const send = async () => {
      const body = this._best ? { keep_best: Number(this._best) } : { below: Number(this._level) };
      const text = this._best ? this._t("prune_confirm_best", { count: this._best }) : this._t("prune_confirm_below", { level: this._level });
      const sure = await ask({ language: this.language, title: this._t("prune_title"), text, ok: this._t("prune_run"), danger: true });
      if (sure) this.run(`/api/voices/${encodeURIComponent(this.voice.name)}/prune`, body);
    };
    return html`<section class="card" data-prune>
      <h3>${this._t("prune_title")}</h3>
      <p class="hint">${this._t("prune_info")}</p>
      <div class="row">
        <label class="field"><span>${this._t("prune_below")}</span>
          <input type="number" min="0" max="5" step="0.1" .value=${this._level} data-prune-below style="width: 110px"
            @input=${(event) => { this._level = event.target.value; if (this._onlyBelow) this._setTable({}); }} /></label>
        <label class="field"><span>${this._t("prune_best")}</span>
          <input type="number" min="1" placeholder="—" .value=${this._best} data-prune-best style="width: 130px"
            @input=${(event) => (this._best = event.target.value)} /></label>
        <span class="grow"></span>
        <button data-run-prune ?disabled=${this.busy || this.running || data.score.count < data.clips || !preview.removed} @click=${send}>
          <pvc-icon icon="mdi:filter-remove-outline"></pvc-icon>${this._t("prune_run")}
        </button>
      </div>
      <p data-prune-preview class=${preview.short ? "warn" : ""}>
        ${this._t(this._best ? "prune_preview_best" : "prune_preview_below", {
          level: number(Number(this._level), this.language, 1),
          count: this._best,
          kept: number(preview.kept, this.language),
          removed: number(preview.removed, this.language),
        })}
        ${preview.short ? html` <strong data-prune-preview-short>${this._t("prune_preview_short", { count: number(preview.short, this.language), target: number(data.target, this.language) })}</strong>` : nothing}
      </p>
      ${data.score.count < data.clips ? html`<p class="warn" data-prune-unscored>${this._t("prune_unscored")}</p>` : nothing}
      <p data-prune-clips>${this._t("prune_clips", { clips: number(data.clips, this.language), target: number(data.target, this.language) })}
        ${short ? html`<strong data-prune-short>${this._t("prune_short", { count: number(short, this.language) })}</strong>` : nothing}</p>
      ${data.pruned.length ? html`<p class="hint" data-prune-files>${this._t("prune_files", { files: data.pruned.join(", ") })}</p>` : nothing}
    </section>`;
  }

  /** Every scored clip, a page at a time. */
  _renderClips() {
    const clips = this._clips;
    const last = Math.min(this._offset + CLIPS_PAGE, clips.total);
    return html`<section class="card" data-clips>
      <h3>${this._t("clips_title")}</h3>
      <div class="row">
        <div class="seg" role="group">
          ${["dataset", "out"].map((where) => html`<button class=${this._where === where ? "on" : ""} data-clips-where=${where}
            @click=${() => this._setTable({ _where: where })}>${this._t(`clips_where_${where}`)}</button>`)}
        </div>
        <label class="check"><input type="checkbox" data-clips-below .checked=${this._onlyBelow}
          @change=${(event) => this._setTable({ _onlyBelow: event.target.checked })} />${this._t("clips_only_below", { level: number(Number(this._level), this.language, 1) })}</label>
        <span class="grow"></span>
        <button data-clips-order @click=${() => this._setTable({ _order: this._order === "asc" ? "desc" : "asc" })}>
          <pvc-icon icon=${this._order === "asc" ? "mdi:sort-ascending" : "mdi:sort-descending"}></pvc-icon>${this._t(`clips_order_${this._order}`)}
        </button>
      </div>
      ${clips.total
        ? html`<table data-clips-table>
            <thead><tr><th></th><th>${this._t("clips_score")}</th><th>${this._t("clips_text")}</th><th>${this._t("clips_id")}</th></tr></thead>
            <tbody>
              ${clips.clips.map((clip) => html`<tr data-clip=${clip.id} class=${clip.score < Number(this._level) ? "low" : ""}>
                <td>${clip.url
                  ? html`<button class="icon" data-clip-play=${clip.id} title=${this._t("clips_play")} @click=${() => this._play(clip.url)}>
                      <pvc-icon icon=${this._playing === clip.url ? "mdi:pause" : "mdi:play"}></pvc-icon></button>`
                  : nothing}</td>
                <td class="mono">${number(clip.score, this.language, 2)}</td>
                <td>${clip.text}</td>
                <td class="mono hint">${clip.id}</td>
              </tr>`)}
            </tbody>
          </table>
          <div class="row">
            <span class="hint" data-clips-range>${this._t("clips_range", { first: number(this._offset + 1, this.language), last: number(last, this.language), total: number(clips.total, this.language) })}</span>
            <span class="grow"></span>
            <button data-clips-prev ?disabled=${this._offset === 0} @click=${() => this._setTable({ _offset: Math.max(this._offset - CLIPS_PAGE, 0) })}>
              <pvc-icon icon="mdi:chevron-left"></pvc-icon>${this._t("clips_prev")}</button>
            <button data-clips-next ?disabled=${last >= clips.total} @click=${() => this._setTable({ _offset: this._offset + CLIPS_PAGE })}>
              ${this._t("clips_next")}<pvc-icon icon="mdi:chevron-right"></pvc-icon></button>
          </div>`
        : html`<p class="hint" data-clips-none>${this._t("clips_list_none")}</p>`}
    </section>`;
  }

  static styles = [
    BaseView.styles,
    css`
      tr.low td:nth-child(2) {
        color: var(--warn-text);
        font-weight: 600;
      }
      button.icon {
        padding: 4px;
        min-width: 0;
      }
    `,
  ];
}
customElements.define("pvc-step-score", PvcStepScore);

class PvcBaseTrain extends BaseView {
  static properties = { ...BaseView.properties, _quality: { state: true }, _chart: { state: true }, _model: { state: true } };

  constructor() {
    super();
    this._quality = "medium";
  }

  async load() {
    const data = await get("/api/base");
    this._model ??= data.latest ?? "medium";
    this._chart = await get("/api/chart").catch(() => null);
    return data;
  }

  render() {
    const data = this.data;
    const runs = data?.runs ?? [];
    const chartIsBase = this._chart?.target?.startsWith("base:");
    return html`
      ${this.head("mdi:school-outline", this._t("base_train"), this._t("base_train_info"), "base")}
      ${this.readyNote()}
      <section class="card">
        <div class="grid2">
          <div class="field"><span>${this._t("base_quality")}</span>
            <div class="seg" data-base-quality>
              ${["medium", "high"].map((q) => html`<button class=${q === this._quality ? "on" : ""} data-quality=${q} @click=${() => (this._quality = q)}>${q}</button>`)}
            </div>
            <span class="hint">${this._t(`base_quality_${this._quality}`)}</span></div>
          <label class="field"><span>${this._t("train_epochs")}</span>
            <input type="number" min="1" value="3000" data-base-epochs /></label>
          <label class="field"><span>${this._t("base_batch")}</span>
            <input type="number" min="0" data-base-batch placeholder=${this._quality === "high" ? "16" : "32"} />
            <span class="hint">${this._t("base_batch_hint")}</span></label>
        </div>
        <div class="row" style="margin-top: 12px">
          ${this.state?.can_power_off ? html`<label class="check"><input type="checkbox" data-base-poweroff />${this._t("job_poweroff")}</label>` : nothing}
          <span class="grow"></span>
          <button class="primary" data-run-base-train ?disabled=${this.busy || this.running || !data?.dataset}
            @click=${() => this.run("/api/base/train", {
              epochs: Number(this.renderRoot.querySelector("[data-base-epochs]").value) || 1,
              quality: this._quality,
              batch: Number(this.renderRoot.querySelector("[data-base-batch]").value) || 0,
              poweroff: Boolean(this.renderRoot.querySelector("[data-base-poweroff]")?.checked),
            })}>
            <pvc-icon icon="mdi:play"></pvc-icon>${this._t("base_train_run")}
          </button>
        </div>
        ${data && !data.dataset ? html`<p class="warn">${this._t("base_no_dataset")}</p>` : nothing}
      </section>
      ${chartIsBase
        ? html`<section class="card" data-base-chart><h3>${this._t("chart_title")} · ${this._t("chart_base")}</h3>
            <pvc-chart .language=${this.language} .data=${this._chart} .title=${this._t("chart_base")}></pvc-chart></section>`
        : nothing}
      ${runs.length
        ? html`<section class="card">
            <div class="row"><h3 class="grow">${this._t("listen_title")}</h3>
              ${runs.length > 1
                ? html`<div class="seg" data-base-model>${runs.map((q) => html`<button class=${q === this._model ? "on" : ""} @click=${() => (this._model = q)}>${q}</button>`)}</div>`
                : nothing}</div>
            <pvc-listen .language=${this.language} .target=${`base:${this._model}`} .refresh=${this._jobKey()}></pvc-listen>
          </section>`
        : nothing}
    `;
  }
}
customElements.define("pvc-base-train", PvcBaseTrain);

class PvcBaseCompare extends BaseView {
  render() {
    const compare = this.data?.compare;
    const value = (v, digits) => (v == null ? "—" : number(v, this.language, digits));
    const best = (pair, digits) => (pair ? `${number(pair[1], this.language, digits)} (${this._t("chart_epoch").toLowerCase()} ${pair[0]})` : "—");
    const start = compare?.common != null ? Math.max(0, compare.common - 9) : 0;
    return html`
      ${this.head("mdi:compare-horizontal", this._t("base_compare"), this._t("compare_info"), "base")}
      <section class="card">
        ${compare?.results?.length
          ? html`<table data-compare>
              <tr><th>${this._t("compare_model")}</th><th>${this._t("compare_epochs")}</th>
                <th>${this._t("compare_mos_at", { start, end: compare.common })}</th><th>${this._t("compare_mel_at", { start, end: compare.common })}</th>
                <th>${this._t("compare_best_mos")}</th><th>${this._t("compare_best_mel")}</th></tr>
              ${compare.results.map((r) => html`<tr><td>${r.quality}</td><td class="num">${r.last_epoch}</td><td class="num">${value(r.mos_at, 2)}</td>
                <td class="num">${value(r.mel_at, 3)}</td><td>${best(r.best_mos, 2)}</td><td>${best(r.best_mel, 3)}</td></tr>`)}
            </table>
            ${this.data.score ? html`<p class="hint">${this._t("compare_ceiling", { median: number(this.data.score.median, this.language, 2) })}</p>` : nothing}`
          : html`<p class="muted">${this._t("compare_none")}</p>`}
      </section>
    `;
  }
}
customElements.define("pvc-base-compare", PvcBaseCompare);

class PvcBaseSelect extends BaseView {
  static properties = { ...BaseView.properties, _checkpoint: { state: true } };

  /** "medium · Epoch 735 · val_mos 3.770 · version_1/epoch=735-val_mos=3.7698.ckpt", as in a voice's export. */
  _label(item) {
    const parts = [item.quality];
    if (item.epoch != null) parts.push(`${this._t("chart_epoch")} ${item.epoch}`);
    if (item.metric) parts.push(`${item.metric} ${number(item.value, this.language, 3)}`);
    else if (item.name === "last.ckpt") parts.push(this._t("checkpoint_last"));
    parts.push(item.run && item.name ? `${item.run}/${item.name}` : item.label);
    return parts.join(" · ");
  }

  render() {
    const data = this.data;
    const checkpoints = data?.checkpoints ?? [];
    const chosen = this._checkpoint ?? checkpoints[0]?.path ?? "";
    return html`
      ${this.head("mdi:check-decagram-outline", this._t("base_select"), this._t("base_select_info"), "base")}
      ${this.readyNote()}
      <section class="card">
        <label class="field"><span>${this._t("export_checkpoint")}</span>
          <select data-base-checkpoint @change=${(event) => (this._checkpoint = event.target.value)}>
            ${checkpoints.map((item) => html`<option value=${item.path} ?selected=${item.path === chosen}>${this._label(item)}</option>`)}
          </select></label>
        ${checkpoints.length ? nothing : html`<p class="muted">${this._t("checkpoints_none")}</p>`}
        <div class="row" style="margin-top: 12px">
          <span class="grow"></span>
          <button data-run-base-export ?disabled=${this.busy || this.running || !chosen} @click=${() => this.run("/api/base/export", { checkpoint: chosen })}>
            <pvc-icon icon="mdi:export"></pvc-icon>${this._t("base_export_run")}</button>
          <button class="primary" data-run-base-select ?disabled=${this.busy || this.running || !chosen} @click=${() => this.run("/api/base/select", { checkpoint: chosen })}>
            <pvc-icon icon="mdi:check"></pvc-icon>${this._t("base_select_run")}</button>
        </div>
      </section>
      <section class="card" data-base-exports>
        <h3>${this._t("export_files")}</h3>
        ${data?.exports?.length
          ? html`<ul>${data.exports.map((file) => html`<li><a class="file" href=${fileUrl(file.url)} download>${file.name}</a></li>`)}</ul>`
          : html`<p class="muted">${this._t("export_none")}</p>`}
      </section>
    `;
  }
}
customElements.define("pvc-base-select", PvcBaseSelect);

VIEWS["base-prepare"] = (p) => html`<pvc-base-prepare .language=${p.language} .state=${p.state} .editor=${p.editor}></pvc-base-prepare>`;
VIEWS["step-score"] = (p) => html`<pvc-step-score .voice=${p.voice} .language=${p.language} .state=${p.state} .editor=${p.editor}></pvc-step-score>`;
VIEWS["base-score"] = (p) => html`<pvc-base-score .language=${p.language} .state=${p.state} .editor=${p.editor}></pvc-base-score>`;
VIEWS["base-train"] = (p) => html`<pvc-base-train .language=${p.language} .state=${p.state} .editor=${p.editor}></pvc-base-train>`;
VIEWS["base-compare"] = (p) => html`<pvc-base-compare .language=${p.language} .state=${p.state} .editor=${p.editor}></pvc-base-compare>`;
VIEWS["base-select"] = (p) => html`<pvc-base-select .language=${p.language} .state=${p.state} .editor=${p.editor}></pvc-base-select>`;
