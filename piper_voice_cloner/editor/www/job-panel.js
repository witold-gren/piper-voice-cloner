// The right column: the job running now (or the last one), the GPU, the training queue and the log.
import { LitElement, css, html, nothing } from "./vendor/lit-all.min.js";
import { translate } from "./i18n.js";
import { base, dialogStyles } from "./styles.js";
import { copyText, duration, number } from "./format.js";
import "./icon.js";
import "./help.js";

const STATE_ICONS = {
  running: "mdi:progress-clock",
  ok: "mdi:check-circle",
  stopped: "mdi:stop-circle-outline",
  failed: "mdi:alert-circle",
  interrupted: "mdi:alert-circle-outline",
};

export class PvcJobPanel extends LitElement {
  static properties = {
    language: {},
    jobs: { attribute: false },
    gpu: { attribute: false },
    canPowerOff: { type: Boolean },
    tensorboard: {},
    _enlarged: { state: true },
    _copied: { state: true },
  };

  constructor() {
    super();
    this.jobs = {};
    this._enlarged = false;
    this._copied = false;
  }

  _t(key, values) {
    return translate(this.language, key, values);
  }

  _kind(job) {
    return this._t(`kind_${job.kind}`, {}, job.kind);
  }

  _emit(name, detail) {
    this.dispatchEvent(new CustomEvent(name, { detail, bubbles: true, composed: true }));
  }

  render() {
    const job = this.jobs?.current ?? { state: "idle" };
    const side = this.jobs?.side;
    return html`
      ${this._renderJob(job, "current")}
      ${side && side.state === "running" ? this._renderJob(side, "side") : nothing}
      ${this._renderGpu()} ${this._renderQueue(job)} ${this._renderLog(job)}
      ${this._enlarged ? this._renderEnlarged(job) : nothing}
    `;
  }

  _renderJob(job, slot) {
    if (job.state === "idle") {
      return html`<section class="card" data-job=${slot} data-state="idle">
        <div class="head">
          <h3>${this._t("job_title")}</h3>
          <pvc-help data-job-help .language=${this.language} .heading=${this._t("job_title")} .text=${this._t("job_help")}></pvc-help>
        </div>
        <p class="muted">${this._t("job_idle")}</p>
      </section>`;
    }
    const running = job.state === "running";
    const name = this._kind(job) + (job.voice ? ` · ${job.voice}` : "");
    return html`<section class="card" data-job=${slot} data-state=${job.state}>
      <div class="head">
        <h3>${slot === "side" ? this._t("job_side") : running ? this._t("job_title") : this._t("job_last")}</h3>
        <span class="grow"></span>
        ${slot === "current" ? html`<pvc-help data-job-help .language=${this.language} .heading=${this._t("job_title")} .text=${this._t("job_help")}></pvc-help>` : nothing}
        <span class="time" data-elapsed
          >${running ? this._t("job_elapsed") : this._t("job_took")} ${duration(job.elapsed)}</span
        >
      </div>
      <p class="name"><strong data-job-name>${name}</strong></p>
      <p class="state ${job.state}" data-job-state>
        <pvc-icon icon=${STATE_ICONS[job.state] ?? "mdi:information-outline"}></pvc-icon>
        ${this._t(`job_state_${job.state}`, { code: job.returncode })}
      </p>
      ${running && job.progress ? this._renderProgress(job.progress) : nothing}
      ${running
        ? html`<div class="row">
            <button class="danger" data-stop=${slot} @click=${() => this._emit("stop-job", { slot })}>
              <pvc-icon icon="mdi:stop"></pvc-icon>${this._t("job_stop")}
            </button>
            ${slot === "current" && this.canPowerOff
              ? html`<label class="check" data-poweroff>
                  <input
                    type="checkbox"
                    .checked=${Boolean(job.poweroff)}
                    @change=${(event) => this._emit("job-poweroff", { slot, value: event.target.checked })}
                  />${this._t("job_poweroff")}
                </label>`
              : nothing}
          </div>`
        : nothing}
    </section>`;
  }

  _renderProgress(progress) {
    const share = progress.total ? Math.min(1, progress.done / progress.total) : 0;
    const unit = progress.unit === "epochs" ? ` ${this._t("epochs")}` : "";
    const done = number(Math.floor(progress.done), this.language);
    return html`<div class="progress" data-progress>
      <div class="bar"><span style="width: ${(share * 100).toFixed(1)}%"></span></div>
      <div class="numbers">
        <span>${progress.label ? `${progress.label} · ` : ""}${done} / ${number(progress.total, this.language)}${unit}</span>
        <span>${Math.round(share * 100)}%</span>
      </div>
      ${progress.epoch != null
        ? html`<div class="hint" data-position>
            ${this._t("train_position", { epoch: progress.epoch, step: progress.step, steps: progress.steps })}
          </div>`
        : nothing}
      ${progress.left ? html`<div class="hint" data-left>${this._t("time_left", { time: duration(progress.left) })}</div>` : nothing}
    </div>`;
  }

  _renderGpu() {
    const gpu = this.gpu;
    const ring = (key, value, max, text) => {
      const share = value == null || !max ? 0 : Math.max(0, Math.min(1, value / max));
      const hot = key === "temp" && value >= 83 ? "hot" : key === "temp" && value >= 75 ? "warm" : "";
      return html`<div class="ring ${hot}" data-ring=${key}>
        <svg viewBox="0 0 36 36">
          <circle cx="18" cy="18" r="15.5" class="track"></circle>
          <circle cx="18" cy="18" r="15.5" class="fill" style="stroke-dasharray: ${(share * 97.4).toFixed(1)} 97.4"></circle>
        </svg>
        <span class="value">${value == null ? "—" : text}</span>
        <span class="label">${this._t(`gpu_${key}`)}</span>
      </div>`;
    };
    return html`<section class="card" data-gpu>
      <div class="head">
        <h3>${this._t("gpu")}</h3>
        <span class="hint">${gpu?.name ?? this._t("gpu_none")}</span>
      </div>
      <div class="rings">
        ${ring("load", gpu?.utilization, 100, `${Math.round(gpu?.utilization ?? 0)}%`)}
        ${ring("memory", gpu?.memory_percent, 100, `${Math.round((gpu?.memory_used ?? 0) / 1024)} GB`)}
        ${ring("temp", gpu?.temperature, 100, `${Math.round(gpu?.temperature ?? 0)}°`)}
        ${ring("power", gpu?.power_percent, 100, `${Math.round(gpu?.power ?? 0)} W`)}
      </div>
      ${this.tensorboard
        ? html`<a class="link" data-tensorboard href=${this.tensorboard} target="_blank" rel="noopener"
            ><pvc-icon icon="mdi:chart-line"></pvc-icon>${this._t("tensorboard")}</a
          >`
        : nothing}
    </section>`;
  }

  _renderQueue(job) {
    if (!job.queue?.length) return nothing;
    return html`<section class="card" data-queue>
      <h3>${this._t("queue")}</h3>
      <ol class="queue">
        ${job.queue.map(
          ([voice, state]) => html`<li class=${state} data-queue-item=${voice}>
            <span>${voice}</span><span class="hint">${this._t(`queue_${state}`)}</span>
          </li>`,
        )}
      </ol>
    </section>`;
  }

  _renderLog(job) {
    return html`<section class="card log-card">
      <div class="head">
        <h3>${this._t("log")}</h3>
        <span class="tools">
          <button class="ghost" data-log-enlarge ?disabled=${!job.log} @click=${() => (this._enlarged = true)}>
            <pvc-icon icon="mdi:arrow-expand"></pvc-icon>${this._t("log_enlarge")}
          </button>
          <button class="ghost" data-log-copy ?disabled=${!job.log} @click=${() => this._copy(job.log)}>
            <pvc-icon icon=${this._copied ? "mdi:check" : "mdi:content-copy"}></pvc-icon>
            ${this._copied ? this._t("log_copied") : this._t("log_copy")}
          </button>
        </span>
      </div>
      <pre class="log" data-log>${job.log ?? ""}</pre>
    </section>`;
  }

  _renderEnlarged(job) {
    return html`<div class="scrim" @click=${(event) => event.target === event.currentTarget && (this._enlarged = false)}>
      <div class="box wide" data-log-dialog>
        <div class="head">
          <h2>${job.kind ? this._kind(job) : this._t("log")}</h2>
          <button class="ghost" aria-label=${this._t("close")} @click=${() => (this._enlarged = false)}>
            <pvc-icon icon="mdi:close"></pvc-icon>
          </button>
        </div>
        <pre class="log big">${job.log ?? ""}</pre>
      </div>
    </div>`;
  }

  async _copy(text) {
    await copyText(text ?? "");
    this._copied = true;
    setTimeout(() => (this._copied = false), 1500);
  }

  updated() {
    // the log follows the newest lines
    for (const log of this.renderRoot.querySelectorAll("pre.log")) log.scrollTop = log.scrollHeight;
  }

  static styles = [
    base,
    dialogStyles,
    css`
      /* a column: the log takes all the height the cards above leave (at least LOG_MIN) */
      :host {
        display: flex;
        flex-direction: column;
        gap: 12px;
        padding: 12px;
        box-sizing: border-box;
      }
      .log-card {
        flex: 1 1 auto;
        display: flex;
        flex-direction: column;
      }
      .head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
      }
      .head h3 {
        margin: 0;
      }
      .grow {
        flex: 1;
      }
      .time {
        font-size: 12px;
        color: var(--muted);
        font-variant-numeric: tabular-nums;
      }
      .name {
        margin: 8px 0 4px;
      }
      .state {
        display: flex;
        gap: 6px;
        align-items: center;
        margin: 0 0 8px;
        color: var(--muted);
      }
      .state.ok {
        color: var(--green);
      }
      .state.failed,
      .state.interrupted {
        color: var(--red);
      }
      .state.running {
        color: var(--accent);
      }
      .row {
        display: flex;
        gap: 12px;
        align-items: center;
        flex-wrap: wrap;
        margin-top: 10px;
      }
      .check {
        display: inline-flex;
        gap: 6px;
        align-items: center;
        font-size: 13px;
      }
      .progress {
        display: grid;
        gap: 4px;
      }
      .bar {
        height: 8px;
        border-radius: 999px;
        background: var(--panel2);
        overflow: hidden;
      }
      .bar span {
        display: block;
        height: 100%;
        border-radius: 999px;
        background: var(--accent);
        transition: width 0.4s;
      }
      .numbers {
        display: flex;
        justify-content: space-between;
        font-size: 12px;
        font-variant-numeric: tabular-nums;
      }
      .rings {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 6px;
        margin-top: 10px;
      }
      .ring {
        display: grid;
        justify-items: center;
        position: relative;
      }
      .ring svg {
        width: 64px;
        height: 64px;
        transform: rotate(-90deg);
      }
      .ring circle {
        fill: none;
        stroke-width: 3.5;
      }
      .ring .track {
        stroke: var(--panel2);
      }
      .ring .fill {
        stroke: var(--accent);
        stroke-linecap: round;
      }
      .ring.warm .fill {
        stroke: var(--amber);
      }
      .ring.hot .fill {
        stroke: var(--red);
      }
      .ring .value {
        position: absolute;
        top: 23px;
        font-size: 11px;
        font-weight: 600;
        font-variant-numeric: tabular-nums;
      }
      .ring .label {
        font-size: 11px;
        color: var(--muted);
      }
      .link {
        display: inline-flex;
        gap: 6px;
        align-items: center;
        margin-top: 10px;
        color: var(--link);
        text-decoration: none;
      }
      .queue {
        margin: 0;
        padding-left: 18px;
        display: grid;
        gap: 2px;
      }
      .queue li span:first-child {
        margin-right: 8px;
      }
      .queue li.now {
        font-weight: 600;
        color: var(--accent);
      }
      .queue li.failed {
        color: var(--red);
      }
      .tools {
        display: flex;
      }
      .tools button {
        padding: 4px 8px;
        font-size: 12px;
      }
      .log {
        margin: 8px 0 0;
        flex: 1 1 0;
        min-height: 240px;
        overflow: auto;
        padding: 10px 12px;
        border-radius: 8px;
        background: var(--terminal);
        color: var(--terminal-text);
        font: 12px/1.45 ui-monospace, SFMono-Regular, Menlo, monospace;
        white-space: pre-wrap;
        word-break: break-word;
      }
      .log.big {
        flex: none;
        height: min(70vh, 900px);
      }
      .box.wide {
        width: min(1200px, calc(100vw - 48px));
      }
    `,
  ];
}

customElements.define("pvc-job-panel", PvcJobPanel);
