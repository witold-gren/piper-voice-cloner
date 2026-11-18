// Own recordings → training → export, plus the training queue and the job history.
import { css, html, nothing } from "./vendor/lit-all.min.js";
import { VIEWS } from "./editor-app.js";
import { StepView, clipStyles, clips } from "./parts.js";
import { call, fileUrl, get } from "./api.js";
import { duration, durationRange, number } from "./format.js";

const HISTORY_ICONS = {
  ok: "mdi:check-circle",
  failed: "mdi:alert-circle",
  stopped: "mdi:stop-circle-outline",
  running: "mdi:progress-clock",
  unknown: "mdi:help-circle-outline",
};
import "./chart.js";
import "./job-panel.js";

function bytes(size, language) {
  return size > 1e6 ? `${number(size / 1e6, language, 1)} MB` : `${number(size / 1e3, language, 0)} kB`;
}

// --- import ------------------------------------------------------------------------------------------

class PvcStepImport extends StepView {
  static properties = { ...StepView.properties, _folder: { state: true }, _persona: { state: true } };

  load() {
    return get(`/api/voices/${encodeURIComponent(this.voice.name)}/import`);
  }

  async _upload(event) {
    const input = event.target; // cleared by the browser after dispatch (shadow DOM)
    const file = input.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    this.busy = true;
    try {
      const { folder } = await call(`/api/voices/${encodeURIComponent(this.voice.name)}/import/upload`, { method: "POST", form });
      this._folder = folder;
      this.error = null;
      await this._reload();
    } catch (err) {
      this.error = err.message;
    } finally {
      this.busy = false;
      input.value = "";
    }
  }

  _run() {
    return this.run(`/api/voices/${encodeURIComponent(this.voice.name)}/import`, {
      folder: this._folder ?? "",
      persona: this._persona ?? "",
      verify: this.renderRoot.querySelector("[data-import-verify]").checked,
    });
  }

  render() {
    const data = this.data;
    const folders = data?.folders ?? [];
    const chosen = folders.find((item) => item.path === this._folder);
    const report = data?.report;
    return html`
      ${this.head("mdi:folder-download-outline", this._t("step_import"), this._t("import_info"), "import")}
      <section class="card">
        <h3>${this._t("import_source")}</h3>
        <div class="grid2">
          <label class="field">
            <span>${this._t("import_folder")}</span>
            <select data-import-folder @change=${(event) => ((this._folder = event.target.value), (this._persona = ""))}>
              <option value="" ?selected=${!this._folder}>${this._t("import_folder_pick")}</option>
              ${folders.map((item) => html`<option value=${item.path} ?selected=${item.path === this._folder}>${item.name} · ${this._t("import_lines", { count: item.lines })}</option>`)}
            </select>
            <span class="hint">${this._t("import_folder_hint", { folder: data?.import_dir ?? "" })}</span>
          </label>
          <label class="field">
            <span>${this._t("import_path")}</span>
            <input data-import-path placeholder="/data/import/…" .value=${this._folder ?? ""} @change=${(event) => (this._folder = event.target.value)} />
            <span class="hint">${this._t("import_path_hint")}</span>
          </label>
          <label class="field">
            <span>${this._t("import_zip")}</span>
            <input type="file" accept=".zip" data-import-zip ?disabled=${this.busy} @change=${this._upload} />
            <span class="hint">${this._t("import_zip_hint")}</span>
          </label>
          <label class="field">
            <span>${this._t("import_persona")}</span>
            <input data-import-persona list="personas" placeholder="custom_metadata.csv" .value=${this._persona ?? ""} @change=${(event) => (this._persona = event.target.value)} />
            <datalist id="personas">${(chosen?.personas ?? []).map((name) => html`<option value=${name}></option>`)}</datalist>
            <span class="hint">${this._t("import_persona_hint")}</span>
          </label>
        </div>
        <div class="row" style="margin-top: 12px">
          <label class="check"><input type="checkbox" data-import-verify />${this._t("import_verify")}</label>
          <span class="grow"></span>
          <button class="primary" data-run-import ?disabled=${this.busy || this.running || !this._folder} @click=${this._run}>
            <pvc-icon icon="mdi:play"></pvc-icon>${this._t("import_run")}
          </button>
        </div>
      </section>
      ${report?.rows
        ? html`<section class="card" data-import-report>
            <h3>${this._t("import_result")}</h3>
            <p>${this._t("import_result_text", { kept: report.kept, rows: report.rows })}</p>
            ${this._reasons(report.reasons)}
            <div class="grid2">
              <div><h3>${this._t("clips_kept")}</h3>${clips(report.kept_clips, this.language, this._t("clips_none"))}</div>
              <div><h3>${this._t("clips_rejected")}</h3>${clips(report.rejected_clips, this.language, this._t("clips_none"))}</div>
            </div>
          </section>`
        : nothing}
    `;
  }

  _reasons(reasons) {
    return html`<table data-reasons>
      <tr><th>${this._t("reason")}</th><th>${this._t("reason_count")}</th><th>${this._t("reason_means")}</th></tr>
      ${reasons.map(
        ([reason, count]) => html`<tr data-reason=${reason}>
          <td class="mono">${reason}</td><td class="num">${count}</td>
          <td class="hint">${this._t(`reason_${reason.replace(":", "_")}`, {}, "")}</td>
        </tr>`,
      )}
    </table>`;
  }

  static styles = [StepView.styles, clipStyles];
}
customElements.define("pvc-step-import", PvcStepImport);

// --- training ----------------------------------------------------------------------------------------

class PvcStepTrain extends StepView {
  static properties = { ...StepView.properties, _epochs: { state: true }, _base: { state: true }, _chart: { state: true } };

  async load() {
    const name = encodeURIComponent(this.voice.name);
    const [view, chart] = await Promise.all([get(`/api/voices/${name}/train`), get(`/api/chart?voice=${name}`)]);
    this._chart = chart;
    if (this._epochs == null || this._loadedFor !== this.voice.name) {
      this._epochs = view.max_epochs;
      this._base = view.base;
      this._loadedFor = this.voice.name;
    }
    return view;
  }

  updated() {
    // the chart follows a running training: fresh points every 20 s
    clearTimeout(this._chartTimer);
    if (this.running) this._chartTimer = setTimeout(() => this._refreshChart(), 20000);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    clearTimeout(this._chartTimer);
  }

  async _refreshChart() {
    this._chart = await get(`/api/chart?voice=${encodeURIComponent(this.voice.name)}`).catch(() => this._chart);
  }

  /** A new run from the chosen base; the earlier checkpoints stay on disk (and in the list). */
  _startOver() {
    if (!window.confirm(this._t("train_start_over_confirm", { base: this._base }))) return;
    return this._run(true);
  }

  _run(fresh = false) {
    return this.run(`/api/voices/${encodeURIComponent(this.voice.name)}/train`, {
      base: this._base,
      epochs: Number(this._epochs),
      fresh,
      poweroff: Boolean(this.renderRoot.querySelector("[data-train-poweroff]")?.checked),
    });
  }

  // the head (and its "?" window) stays the same element before and after the data comes
  render() {
    return html`${this.head("mdi:school-outline", this._t("step_train"), this._t("train_info"), "train")}${this.data ? this._renderLoaded() : nothing}`;
  }

  _renderLoaded() {
    const data = this.data;
    const epochs = Number(this._epochs) || 0;
    const est = data.estimate;
    const resume = data.resume;
    const chartName = this._chart?.target?.startsWith("voice:") ? this._t("chart_voice", { voice: this._chart.target.slice(6) }) : this._t("chart_base");
    return html`
      ${data.clips ? nothing : html`<p class="warn" data-train-no-dataset>${this._t("train_no_dataset")}</p>`}
      ${data.wanted_base === "bazowy-pl" && !data.base_ready ? html`<p class="warn" data-base-missing>${this._t("base_not_ready")}</p>` : nothing}
      <section class="card">
        <h3>${this._t("train_settings")}</h3>
        <div class="grid2">
          <label class="field">
            <span>${this._t("train_base")}</span>
            <select data-train-base @change=${(event) => (this._base = event.target.value)}>
              ${data.base_choices.map((choice) => html`<option value=${choice} ?selected=${choice === this._base}>${choice}</option>`)}
            </select>
            <span class="hint">${this._t("train_base_hint")}</span>
            ${data.checkpoints.length ? html`<span class="hint" data-train-base-resume>${this._t("train_base_resume_hint")}</span>` : nothing}
          </label>
          <label class="field">
            <span>${this._t("train_epochs")}</span>
            <input type="number" min="1" data-train-epochs .value=${String(this._epochs)} @input=${(event) => (this._epochs = event.target.value)} />
            <span class="hint">${this._t("train_epochs_hint")}</span>
          </label>
        </div>
        ${est
          ? html`<p data-train-estimate>
              ${this._t("train_estimate", {
                clips: number(data.clips, this.language),
                steps: est.steps,
                low: Math.round(est.low),
                high: Math.round(est.high),
                epochs,
                time: durationRange(est.low * epochs, est.high * epochs, this.language),
              })}
            </p>`
          : nothing}
        ${resume ? html`<p class="warn" data-train-resume>${this._resumeText(resume, epochs)}</p>` : nothing}
        <div class="row">
          ${this.state?.can_power_off
            ? html`<label class="check"><input type="checkbox" data-train-poweroff />${this._t("job_poweroff")}</label>`
            : html`<span class="hint" data-poweroff-off>${this._t("poweroff_needs_ha")}</span>`}
          <span class="grow"></span>
          ${data.checkpoints.length
            ? html`<button data-train-fresh ?disabled=${this.busy || this.running || !data.clips} @click=${this._startOver}>
                <pvc-icon icon="mdi:restart"></pvc-icon>${this._t("train_start_over")}
              </button>`
            : nothing}
          <button class="primary" data-run-train ?disabled=${this.busy || this.running || !data.clips} @click=${() => this._run()}>
            <pvc-icon icon="mdi:play"></pvc-icon>${data.checkpoints.length ? this._t("train_resume") : this._t("train_run")}
          </button>
        </div>
      </section>
      <section class="card" data-train-chart>
        <h3>${this._t("chart_title")} · ${chartName}</h3>
        <pvc-chart .language=${this.language} .data=${this._chart} .title=${chartName}></pvc-chart>
      </section>
      <section class="card">
        <h3>${this._t("listen_title")}</h3>
        <pvc-listen .language=${this.language} .target=${`voice:${this.voice.name}`} .refresh=${this._jobKey()}></pvc-listen>
      </section>
      <section class="card" data-checkpoints>
        <h3>${this._t("checkpoints")}</h3>
        ${data.checkpoints.length
          ? html`<table>
              <tr><th>${this._t("chart_epoch")}</th><th>${this._t("checkpoint_kind")}</th><th>${this._t("checkpoint_file")}</th></tr>
              ${data.checkpoints.map(
                (item) => html`<tr>
                  <td class="num">${item.epoch ?? "—"}</td>
                  <td>${item.metric ? `${item.metric} ${number(item.value, this.language, 3)}` : item.name === "last.ckpt" ? this._t("checkpoint_last") : ""}</td>
                  <td class="mono">${item.run}/${item.name}</td>
                </tr>`,
              )}
            </table>`
          : html`<p class="muted">${this._t("checkpoints_none")}</p>`}
      </section>
    `;
  }

  // the same rule as `pvc train`: the plan is run start + epochs; a checkpoint past it means "more"
  _resumeText(resume, epochs) {
    const planned = resume.run_start + epochs;
    if (resume.reached >= planned) return this._t("train_resume_done", { reached: resume.reached, epochs, end: resume.reached + epochs });
    return this._t("train_resume_left", { reached: resume.reached, end: planned, left: planned - resume.reached });
  }
}
customElements.define("pvc-step-train", PvcStepTrain);

// --- export ------------------------------------------------------------------------------------------

class PvcStepExport extends StepView {
  static properties = { ...StepView.properties, _checkpoint: { state: true } };

  load() {
    return get(`/api/voices/${encodeURIComponent(this.voice.name)}/export`);
  }

  render() {
    const data = this.data;
    return html`
      ${this.head("mdi:export", this._t("step_export"), this._t("export_info"), "export")}
      <section class="card">
        <h3>${this._t("export_checkpoint")}</h3>
        <div class="row">
          <select class="grow" data-export-checkpoint @change=${(event) => (this._checkpoint = event.target.value)}>
            ${(data?.checkpoints ?? []).map(
              (item, index) => html`<option value=${item.path} ?selected=${this._checkpoint ? item.path === this._checkpoint : index === 0}>
                ${item.epoch != null ? `${this._t("chart_epoch")} ${item.epoch} · ` : ""}${item.metric ? `${item.metric} ${number(item.value, this.language, 3)} · ` : ""}${item.run}/${item.name}
              </option>`,
            )}
          </select>
          <button class="primary" data-run-export ?disabled=${this.busy || this.running || !data?.checkpoints?.length}
            @click=${() => this.run(`/api/voices/${encodeURIComponent(this.voice.name)}/export`, { checkpoint: this._checkpoint ?? data.checkpoints[0].path })}>
            <pvc-icon icon="mdi:export"></pvc-icon>${this._t("export_run")}
          </button>
        </div>
        ${data && !data.checkpoints.length ? html`<p class="muted">${this._t("checkpoints_none")}</p>` : nothing}
        <p class="hint">${this._t("export_hint", { stem: data?.stem ?? "" })}</p>
      </section>
      <section class="card" data-export-files>
        <h3>${this._t("export_files")}</h3>
        ${data?.files?.length
          ? html`<ul>${data.files.map((file) => html`<li><a class="file" href=${fileUrl(file.url)} download>${file.name}</a> · ${bytes(file.size, this.language)}</li>`)}</ul>`
          : html`<p class="muted">${this._t("export_none")}</p>`}
      </section>
    `;
  }
}
customElements.define("pvc-step-export", PvcStepExport);

// --- training queue ----------------------------------------------------------------------------------

class PvcJobsQueue extends StepView {
  static properties = { ...StepView.properties, _picked: { state: true }, _epochs: { state: true }, _base: { state: true } };

  constructor() {
    super();
    this._picked = [];
    this._epochs = 500;
  }

  async load() {
    const data = await get("/api/queue");
    this._base ??= data.base;
    return data;
  }

  _toggle(name) {
    this._picked = this._picked.includes(name) ? this._picked.filter((item) => item !== name) : [...this._picked, name];
  }

  render() {
    const data = this.data;
    const queue = this.state?.jobs?.current?.queue ?? [];
    return html`
      ${this.head("mdi:format-list-numbered", this._t("jobs_queue"), this._t("queue_info"), "queue")}
      <section class="card">
        <h3>${this._t("queue_voices")}</h3>
        <ul class="pick" data-queue-voices>
          ${(data?.voices ?? []).map((name) => {
            const index = this._picked.indexOf(name);
            return html`<li>
              <label class="check"><input type="checkbox" data-queue-voice=${name} .checked=${index >= 0} @change=${() => this._toggle(name)} />
                ${index >= 0 ? html`<b class="order">${index + 1}</b>` : nothing}${name}</label>
            </li>`;
          })}
        </ul>
        <div class="grid2">
          <label class="field"><span>${this._t("train_base")}</span>
            <select data-queue-base @change=${(event) => (this._base = event.target.value)}>
              ${(data?.base_choices ?? []).map((choice) => html`<option value=${choice} ?selected=${choice === this._base}>${choice}</option>`)}
            </select></label>
          <label class="field"><span>${this._t("train_epochs")}</span>
            <input type="number" min="1" data-queue-epochs .value=${String(this._epochs)} @input=${(event) => (this._epochs = event.target.value)} /></label>
        </div>
        <div class="row" style="margin-top: 12px">
          ${this.state?.can_power_off ? html`<label class="check"><input type="checkbox" data-queue-poweroff />${this._t("queue_poweroff")}</label>` : nothing}
          <span class="grow"></span>
          <button class="primary" data-run-queue ?disabled=${this.busy || this.running || !this._picked.length}
            @click=${() => this.run("/api/queue", { voices: this._picked, epochs: Number(this._epochs), base: this._base, poweroff: Boolean(this.renderRoot.querySelector("[data-queue-poweroff]")?.checked) })}>
            <pvc-icon icon="mdi:play"></pvc-icon>${this._t("queue_run")}
          </button>
        </div>
      </section>
      ${queue.length ? html`<section class="card"><h3>${this._t("queue")}</h3>
        <ol>${queue.map(([voice, state]) => html`<li>${voice} – ${this._t(`queue_${state}`)}</li>`)}</ol></section>` : nothing}
    `;
  }

  static styles = [
    StepView.styles,
    css`
      .pick {
        list-style: none;
        margin: 0 0 12px;
        padding: 0;
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
        gap: 6px;
      }
      .order {
        display: inline-grid;
        place-items: center;
        width: 18px;
        height: 18px;
        border-radius: 999px;
        font-size: 11px;
        color: #fff;
        background: var(--accent);
      }
    `,
  ];
}
customElements.define("pvc-jobs-queue", PvcJobsQueue);

// --- job history and the job now --------------------------------------------------------------------

class PvcJobsHistory extends StepView {
  static properties = { ...StepView.properties, _log: { state: true }, _file: { state: true } };

  load() {
    return get("/api/history");
  }
  _historyStatus(item) {
    if (item.status === "ok") return this._t("job_state_ok");
    if (item.status === "failed") return this._t("job_state_failed", { code: item.code });
    if (item.status === "stopped") return this._t("job_state_stopped");
    if (item.status === "running") return this._t("job_state_running");
    return "—"; // an older log or a restart: the title says so
  }


  async _open(file) {
    this._file = file;
    this._log = (await get(`/api/history/${encodeURIComponent(file)}`)).log;
  }

  render() {
    return html`
      ${this.head("mdi:history", this._t("jobs_history"), this._t("history_info"), "train")}
      <section class="card">
        ${this.data?.length
          ? html`<table data-history>
              <tr><th>${this._t("history_started")}</th><th>${this._t("history_job")}</th><th>${this._t("history_voice")}</th><th>${this._t("history_status")}</th><th>${this._t("history_took")}</th><th></th></tr>
              ${this.data.map(
                (item) => html`<tr class=${item.file === this._file ? "sel" : ""}>
                  <td class="mono nowrap">${item.started}</td><td>${this._t(`kind_${item.kind}`, {}, item.kind)}</td><td>${item.voice}</td>
                  <td class="status ${item.status}" data-history-status=${item.status} title=${item.status === "unknown" ? this._t("history_unknown") : ""}>
                    <pvc-icon icon=${HISTORY_ICONS[item.status] ?? "mdi:help-circle-outline"}></pvc-icon>${this._historyStatus(item)}
                  </td>
                  <td class="mono">${item.took != null ? duration(item.took) : "—"}</td>
                  <td><button class="ghost" data-history-open=${item.file} @click=${() => this._open(item.file)}>${this._t("history_log")}</button></td>
                </tr>`,
              )}
            </table>`
          : html`<p class="muted">${this._t("history_none")}</p>`}
      </section>
      ${this._log != null ? html`<section class="card"><h3>${this._file}</h3><pre class="log" data-history-log>${this._log}</pre></section>` : nothing}
    `;
  }

  static styles = [
    StepView.styles,
    css`
      td.nowrap,
      td.status {
        white-space: nowrap;
        --icon-size: 16px;
      }
      td.status pvc-icon {
        vertical-align: -3px;
        margin-right: 4px;
      }
      td.status.ok {
        color: var(--green);
      }
      td.status.failed {
        color: var(--red);
        font-weight: 600;
      }
      td.status.stopped,
      td.status.unknown {
        color: var(--muted);
      }
      tr.sel td {
        background: rgba(79, 140, 255, 0.12);
      }
      .log {
        margin: 0;
        max-height: 60vh;
        overflow: auto;
        padding: 10px 12px;
        border-radius: 8px;
        background: var(--terminal);
        color: var(--terminal-text);
        font: 12px/1.45 ui-monospace, SFMono-Regular, Menlo, monospace;
        white-space: pre-wrap;
      }
    `,
  ];
}
customElements.define("pvc-jobs-history", PvcJobsHistory);

VIEWS["step-import"] = (p) => html`<pvc-step-import .voice=${p.voice} .language=${p.language} .state=${p.state} .editor=${p.editor}></pvc-step-import>`;
VIEWS["step-train"] = (p) => html`<pvc-step-train .voice=${p.voice} .language=${p.language} .state=${p.state} .editor=${p.editor}></pvc-step-train>`;
VIEWS["step-export"] = (p) => html`<pvc-step-export .voice=${p.voice} .language=${p.language} .state=${p.state} .editor=${p.editor}></pvc-step-export>`;
VIEWS["jobs-queue"] = (p) => html`<pvc-jobs-queue .language=${p.language} .state=${p.state} .editor=${p.editor}></pvc-jobs-queue>`;
VIEWS["jobs-history"] = (p) => html`<pvc-jobs-history .language=${p.language} .state=${p.state} .editor=${p.editor}></pvc-jobs-history>`;
VIEWS["jobs-current"] = (p) => html`<div class="pane wide-job">
  <pvc-job-panel .language=${p.language} .jobs=${p.state.jobs} .gpu=${p.state.gpu} .canPowerOff=${Boolean(p.state.can_power_off)}
    @stop-job=${(event) => p.editor._stopJob(event.detail)} @job-poweroff=${(event) => p.editor._jobPoweroff(event.detail)}></pvc-job-panel>
</div>`;
