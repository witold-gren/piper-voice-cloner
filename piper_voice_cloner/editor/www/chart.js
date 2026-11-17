// Training chart: quality (val_mos, higher is better) and mel error (val_mel and train_mel, lower is
// better) per epoch, as two small charts on one epoch axis (never two scales on one chart).
// Hover shows the values of an epoch; a click opens it full screen, where dragging zooms into a
// range of epochs and a click pins one epoch.
import { LitElement, css, html, nothing, svg } from "./vendor/lit-all.min.js";
import { translate } from "./i18n.js";
import { base, dialogStyles } from "./styles.js";
import { number } from "./format.js";
import "./icon.js";

const SERIES = {
  val_mos: { column: 1, colour: "var(--series-1)" },
  val_mel: { column: 2, colour: "var(--series-2)" },
  train_mel: { column: 3, colour: "var(--series-3)", dashed: true },
};
const PANELS = [
  { key: "mos", series: ["val_mos"], digits: 2 },
  { key: "mel", series: ["val_mel", "train_mel"], digits: 3 },
];
const PAD = { left: 48, right: 12, top: 10, bottom: 22 };

/** Nice round ticks between low and high. */
export function ticks(low, high, count = 4) {
  if (!(high > low)) return [low];
  const raw = (high - low) / count;
  const power = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * power).find((s) => s >= raw) ?? raw;
  const out = [];
  for (let value = Math.ceil(low / step) * step; value <= high + step / 1e6; value += step) out.push(Number(value.toFixed(6)));
  return out;
}

export class PvcChart extends LitElement {
  static properties = {
    language: {},
    data: { attribute: false },
    title: {},
    big: { type: Boolean, reflect: true },
    _hover: { state: true },
    _range: { state: true },
    _pinned: { state: true },
    _drag: { state: true },
    _open: { state: true },
  };

  constructor() {
    super();
    this._range = null;
    this._pinned = null;
    this._open = false;
  }

  _t(key, values) {
    return translate(this.language, key, values);
  }

  _rows() {
    const rows = this.data?.rows ?? [];
    if (!this._range) return rows;
    return rows.filter(([epoch]) => epoch >= this._range[0] && epoch <= this._range[1]);
  }

  render() {
    const rows = this.data?.rows ?? [];
    if (!rows.length) return html`<p class="muted" data-chart-empty>${this._t("chart_none")}</p>`;
    return html`
      <div class="chart" data-chart @click=${() => !this.big && (this._open = true)} title=${this.big ? "" : this._t("chart_open")}>
        ${this._renderPanels(this._rows(), this.big ? 760 : 520, this.big ? 220 : 120)}
        <div class="legend">
          ${Object.entries(SERIES).map(([name, s]) => html`<span><i class=${s.dashed ? "dashed" : ""} style="--c: ${s.colour}"></i>${name}</span>`)}
        </div>
      </div>
      ${this._open ? this._renderDialog() : nothing}
    `;
  }

  _renderPanels(rows, width, height) {
    const epochs = rows.map((row) => row[0]);
    const lowE = Math.min(...epochs);
    const highE = Math.max(...epochs);
    const x = (epoch) => PAD.left + ((epoch - lowE) / Math.max(1, highE - lowE)) * (width - PAD.left - PAD.right);
    const toEpoch = (px) => Math.round(lowE + ((px - PAD.left) / (width - PAD.left - PAD.right)) * Math.max(1, highE - lowE));
    const nearest = (epoch) => rows.reduce((best, row) => (Math.abs(row[0] - epoch) < Math.abs(best[0] - epoch) ? row : best), rows[0]);
    const pointer = (event) => {
      const box = event.currentTarget.getBoundingClientRect();
      return ((event.clientX - box.left) / box.width) * width;
    };
    const move = (event) => {
      const row = nearest(toEpoch(pointer(event)));
      this._hover = row;
      if (this._drag) this._drag = { ...this._drag, to: toEpoch(pointer(event)) };
    };
    const down = (event) => this.big && (this._drag = { from: toEpoch(pointer(event)), to: toEpoch(pointer(event)) });
    const up = (event) => {
      if (!this.big || !this._drag) return;
      const { from, to } = this._drag;
      this._drag = null;
      // the window around the big chart keeps the range and the pinned epoch (its inputs show them)
      if (Math.abs(to - from) >= 3) this._emit("zoom", [Math.min(from, to), Math.max(from, to)]);
      else {
        this._pinned = nearest(toEpoch(pointer(event)));
        this._emit("pin", this._pinned);
      }
      event.stopPropagation();
    };
    return PANELS.map((panel) => {
      const values = rows.flatMap((row) => panel.series.map((name) => row[SERIES[name].column])).filter((v) => v != null);
      if (!values.length) return nothing;
      let low = Math.min(...values);
      let high = Math.max(...values);
      const margin = (high - low) * 0.08 || 0.05;
      low -= margin;
      high += margin;
      const y = (value) => PAD.top + (1 - (value - low) / (high - low)) * (height - PAD.top - PAD.bottom);
      const best = this.data.best?.[panel.key];
      const hover = this._hover;
      return html`<figure class="panel" data-panel=${panel.key}>
        <figcaption>${this._t(`chart_title_${panel.key}`)}</figcaption>
        <svg
          viewBox="0 0 ${width} ${height}"
          preserveAspectRatio="none"
          @pointermove=${move}
          @pointerleave=${() => (this._hover = null)}
          @pointerdown=${down}
          @pointerup=${up}
        >
          ${ticks(low, high).map(
            (tick) => svg`<line class="grid" x1=${PAD.left} x2=${width - PAD.right} y1=${y(tick)} y2=${y(tick)}></line>
              <text class="axis" x=${PAD.left - 6} y=${y(tick) + 4} text-anchor="end">${number(tick, this.language, panel.digits)}</text>`,
          )}
          ${ticks(lowE, highE, 6)
            .filter((tick) => Number.isInteger(tick))
            .map((tick) => svg`<text class="axis" x=${x(tick)} y=${height - 6} text-anchor="middle">${tick}</text>`)}
          ${panel.series.map((name) => {
            const points = rows.filter((row) => row[SERIES[name].column] != null).map((row) => `${x(row[0])},${y(row[SERIES[name].column])}`);
            return svg`<polyline class=${SERIES[name].dashed ? "line dashed" : "line"} style="stroke: ${SERIES[name].colour}" points=${points.join(" ")}></polyline>`;
          })}
          ${best && best[0] >= lowE && best[0] <= highE
            ? svg`<circle class="best" cx=${x(best[0])} cy=${y(best[1])} r="4"></circle>`
            : nothing}
          ${this._drag
            ? svg`<rect class="zoom" x=${Math.min(x(this._drag.from), x(this._drag.to))} y=${PAD.top} width=${Math.abs(x(this._drag.to) - x(this._drag.from))} height=${height - PAD.top - PAD.bottom}></rect>`
            : nothing}
          ${this._pinned ? svg`<line class="pin" x1=${x(this._pinned[0])} x2=${x(this._pinned[0])} y1=${PAD.top} y2=${height - PAD.bottom}></line>` : nothing}
          ${hover
            ? svg`<line class="cross" x1=${x(hover[0])} x2=${x(hover[0])} y1=${PAD.top} y2=${height - PAD.bottom}></line>
              ${panel.series
                .filter((name) => hover[SERIES[name].column] != null)
                .map((name) => svg`<circle class="dot" style="fill: ${SERIES[name].colour}" cx=${x(hover[0])} cy=${y(hover[SERIES[name].column])} r="3.5"></circle>`)}`
            : nothing}
        </svg>
        ${hover
          ? html`<div class="tip" data-tip style="left: ${(x(hover[0]) / width) * 100}%">
              <strong>${this._t("chart_epoch")} ${hover[0]}</strong>
              ${panel.series.map((name) => html`<span>${name}: ${hover[SERIES[name].column] == null ? "—" : number(hover[SERIES[name].column], this.language, panel.digits)}</span>`)}
            </div>`
          : nothing}
      </figure>`;
    });
  }

  _renderDialog() {
    const best = this.data.best ?? {};
    const pinned = this._pinned;
    return html`<div class="scrim" @click=${(event) => event.target === event.currentTarget && (this._open = false)}>
      <div class="box wide" data-chart-dialog>
        <div class="head">
          <h2>${this.title ?? ""}</h2>
          <button class="ghost" aria-label=${this._t("close")} @click=${() => (this._open = false)}><pvc-icon icon="mdi:close"></pvc-icon></button>
        </div>
        <div class="tools">
          <label>${this._t("chart_from")}
            <input type="number" data-range-from .value=${String(this._range?.[0] ?? "")} @change=${(event) => this._setRange(0, event.target.value)} /></label>
          <label>${this._t("chart_to")}
            <input type="number" data-range-to .value=${String(this._range?.[1] ?? "")} @change=${(event) => this._setRange(1, event.target.value)} /></label>
          <button data-range-all @click=${() => (this._range = null)}>${this._t("chart_all")}</button>
          <span class="hint">${this._t("chart_pick")}</span>
        </div>
        <pvc-chart big .language=${this.language} .data=${{ ...this.data, rows: this._rows() }} .title=${this.title}
          @pin=${(event) => (this._pinned = event.detail)} @zoom=${(event) => (this._range = event.detail)}></pvc-chart>
        <div class="facts">
          ${best.mos ? html`<span data-best-mos>${this._t("chart_best_mos", { value: number(best.mos[1], this.language, 2), epoch: best.mos[0] })}</span>` : nothing}
          ${best.mel ? html`<span data-best-mel>${this._t("chart_best_mel", { value: number(best.mel[1], this.language, 3), epoch: best.mel[0] })}</span>` : nothing}
          ${pinned ? html`<span data-pinned>${this._t("chart_pinned")}: ${pinned[0]}</span>` : nothing}
        </div>
        <details class="help">
          <summary>${this._t("chart_help_title")}</summary>
          ${["mos", "mel", "train", "best", "over"].map((key) => html`<p>${this._t(`chart_help_${key}`)}</p>`)}
        </details>
      </div>
    </div>`;
  }

  _emit(name, detail) {
    this.dispatchEvent(new CustomEvent(name, { detail }));
  }

  _setRange(index, value) {
    const rows = this.data?.rows ?? [];
    const range = this._range ? [...this._range] : [rows[0]?.[0] ?? 0, rows.at(-1)?.[0] ?? 0];
    range[index] = Number(value);
    this._range = range[0] < range[1] ? range : null;
  }

  static styles = [
    base,
    dialogStyles,
    css`
      :host {
        display: block;
        --series-1: #4f8cff;
        --series-2: #ff9f43;
        --series-3: #2dd4bf;
      }
      .chart {
        cursor: zoom-in;
      }
      :host([big]) .chart {
        cursor: crosshair;
      }
      .panel {
        position: relative;
        margin: 0 0 10px;
      }
      figcaption {
        font-size: 12px;
        color: var(--muted);
        margin-bottom: 2px;
      }
      svg {
        width: 100%;
        height: auto;
        display: block;
        touch-action: none;
      }
      .grid {
        stroke: var(--line);
        stroke-width: 1;
      }
      .axis {
        fill: var(--muted);
        font-size: 10px;
      }
      .line {
        fill: none;
        stroke-width: 2;
        vector-effect: non-scaling-stroke;
      }
      .line.dashed {
        stroke-dasharray: 5 4;
      }
      .best {
        fill: var(--panel);
        stroke: var(--green);
        stroke-width: 2;
      }
      .cross,
      .pin {
        stroke: var(--muted);
        stroke-width: 1;
      }
      .pin {
        stroke: var(--amber);
        stroke-dasharray: 3 3;
      }
      .dot {
        stroke: var(--panel);
        stroke-width: 2;
      }
      .zoom {
        fill: rgba(79, 140, 255, 0.15);
        stroke: var(--accent);
      }
      .tip {
        position: absolute;
        top: 18px;
        transform: translateX(8px);
        display: grid;
        gap: 2px;
        padding: 6px 8px;
        border-radius: 8px;
        font-size: 12px;
        background: var(--panel2);
        border: 1px solid var(--line);
        pointer-events: none;
        white-space: nowrap;
        z-index: 2;
      }
      .legend {
        display: flex;
        gap: 14px;
        font-size: 12px;
        color: var(--muted);
      }
      .legend span {
        display: inline-flex;
        gap: 6px;
        align-items: center;
      }
      .legend i {
        width: 18px;
        border-top: 2px solid var(--c);
      }
      .legend i.dashed {
        border-top-style: dashed;
      }
      .head {
        display: flex;
        justify-content: space-between;
        align-items: center;
      }
      .box.wide {
        width: min(1100px, calc(100vw - 48px));
      }
      .tools {
        display: flex;
        gap: 10px;
        align-items: center;
        flex-wrap: wrap;
      }
      .tools label {
        display: inline-flex;
        gap: 6px;
        align-items: center;
      }
      .tools input {
        width: 90px;
      }
      .facts {
        display: flex;
        gap: 16px;
        flex-wrap: wrap;
      }
      .help p {
        margin: 6px 0;
        color: var(--muted);
      }
    `,
  ];
}

customElements.define("pvc-chart", PvcChart);
