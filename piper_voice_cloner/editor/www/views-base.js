// The own Polish base (bazowy-pl): prepare its data, rate the recordings, train, compare, choose.
import { css, html, nothing } from "./vendor/lit-all.min.js";
import { VIEWS } from "./editor-app.js";
import { StepView, clipStyles, clips } from "./parts.js";
import { fileUrl, get } from "./api.js";
import { number } from "./format.js";
import "./chart.js";

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

class PvcBaseScore extends BaseView {
  render() {
    const score = this.data?.score;
    const side = this.state?.jobs?.side ?? {};
    const pct = (value) => `${Math.round(value * 100)}%`;
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
      ${score
        ? html`<section class="card" data-score>
            <div class="tiles">
              <div class="tile"><span class="hint">${this._t("score_median")}</span><strong>${number(score.median, this.language, 2)}</strong></div>
              <div class="tile"><span class="hint">${this._t("score_p10")}</span><strong>${number(score.p10, this.language, 2)}</strong></div>
              <div class="tile"><span class="hint">${this._t("score_p90")}</span><strong>${number(score.p90, this.language, 2)}</strong></div>
              <div class="tile"><span class="hint">${this._t("score_good", { good: number(score.good_level, this.language, 1) })}</span><strong>${pct(score.good)}</strong></div>
            </div>
            <p>${this._t("score_summary", { count: number(score.count, this.language), total: number(score.total, this.language), median: number(score.median, this.language, 2) })}</p>
            <div class="grid2">
              <div><h3>${this._t("score_worst")}</h3>${clips(score.worst, this.language)}</div>
              <div><h3>${this._t("score_best")}</h3>${clips(score.best, this.language)}</div>
            </div>
          </section>`
        : nothing}
    `;
  }
}
customElements.define("pvc-base-score", PvcBaseScore);

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
VIEWS["base-score"] = (p) => html`<pvc-base-score .language=${p.language} .state=${p.state} .editor=${p.editor}></pvc-base-score>`;
VIEWS["base-train"] = (p) => html`<pvc-base-train .language=${p.language} .state=${p.state} .editor=${p.editor}></pvc-base-train>`;
VIEWS["base-compare"] = (p) => html`<pvc-base-compare .language=${p.language} .state=${p.state} .editor=${p.editor}></pvc-base-compare>`;
VIEWS["base-select"] = (p) => html`<pvc-base-select .language=${p.language} .state=${p.state} .editor=${p.editor}></pvc-base-select>`;
