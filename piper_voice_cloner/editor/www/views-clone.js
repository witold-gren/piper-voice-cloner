// The cloning way: recording → sentences → audition → generating clips → filter.
import { css, html, nothing } from "./vendor/lit-all.min.js";
import { VIEWS } from "./editor-app.js";
import { StepView, clipStyles, clips } from "./parts.js";
import { call, get, post } from "./api.js";
import { duration, number } from "./format.js";

const voicePath = (view, part) => `/api/voices/${encodeURIComponent(view.voice.name)}/${part}`;

/** Upload files of an <input type=file multiple> to the voice; returns false when refused. */
async function upload(view, part, event) {
  // kept before any await: the browser clears event.target of shadow DOM events after dispatch
  const input = event.target;
  const files = [...(input.files ?? [])];
  if (!files.length) return false;
  const form = new FormData();
  for (const file of files) form.append("files", file);
  view.busy = true;
  try {
    await call(voicePath(view, part), { method: "POST", form });
    view.error = null;
    await view._reload();
    return true;
  } catch (err) {
    view.error = err.message;
    return false;
  } finally {
    view.busy = false;
    input.value = "";
  }
}

function fileList(view, names, part) {
  if (!names.length) return html`<p class="muted">${view._t("files_none")}</p>`;
  return html`<ul class="files" data-files>
    ${names.map(
      (name) => html`<li>
        <span class="mono">${name}</span>
        <button class="ghost danger" data-remove-file=${name} title=${view._t("file_remove")}
          @click=${async () => {
            await call(`${voicePath(view, part)}/${encodeURIComponent(name)}`, { method: "DELETE" });
            view._reload();
          }}><pvc-icon icon="mdi:close"></pvc-icon></button>
      </li>`,
    )}
  </ul>`;
}

const fileStyles = css`
  .files {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 4px;
  }
  .files li {
    display: flex;
    gap: 6px;
    align-items: center;
    justify-content: space-between;
    padding: 4px 4px 4px 10px;
    border-radius: 8px;
    background: var(--panel2);
  }
  .files button {
    padding: 4px;
  }
`;

// --- recording ---------------------------------------------------------------------------------------

class PvcStepReference extends StepView {
  load() {
    return get(voicePath(this, "reference"));
  }

  render() {
    const data = this.data;
    const info = data?.info ?? {};
    const elevenlabs = data?.backend === "elevenlabs";
    return html`
      ${this.head("mdi:microphone", this._t("step_reference"), this._t("reference_info"), "reference")}
      ${elevenlabs ? html`<p class="warn" data-reference-elevenlabs>${this._t("reference_elevenlabs")}</p>` : nothing}
      <section class="card">
        <h3>${this._t("reference_files")}</h3>
        ${fileList(this, data?.uploads ?? [], "reference/uploads")}
        <div class="row" style="margin-top: 10px">
          <input type="file" multiple accept="audio/*,.wav,.mp3,.m4a,.flac,.ogg" data-reference-upload ?disabled=${this.busy}
            @change=${(event) => upload(this, "reference/upload", event)} />
        </div>
        <div class="row" style="margin-top: 12px">
          <label class="check"><input type="checkbox" data-reference-embed checked />${this._t("reference_embed")}</label>
          <span class="grow"></span>
          <button class="primary" data-run-reference ?disabled=${this.busy || this.running || !data?.uploads?.length}
            @click=${() => this.run(voicePath(this, "reference"), { embed: this.renderRoot.querySelector("[data-reference-embed]").checked })}>
            <pvc-icon icon="mdi:play"></pvc-icon>${this._t("reference_run")}
          </button>
        </div>
      </section>
      ${info.seconds
        ? html`<section class="card" data-reference-result>
            <h3>${this._t("reference_result")}</h3>
            <p>${this._t("reference_done", {
              seconds: number(info.seconds, this.language, 1),
              prompts: info.prompts.length,
              threshold: data.min_similarity == null ? "—" : number(data.min_similarity, this.language, 2),
            })}</p>
            ${data.short ? html`<p class="warn" data-reference-short>${this._t("reference_short", { seconds: number(info.seconds, this.language, 1), prompts: info.prompts.length })}</p>` : nothing}
            ${clips(data.clips, this.language)}
          </section>`
        : nothing}
    `;
  }

  static styles = [StepView.styles, clipStyles, fileStyles];
}
customElements.define("pvc-step-reference", PvcStepReference);

// --- sentences ---------------------------------------------------------------------------------------

class PvcStepCorpus extends StepView {
  load() {
    return get(voicePath(this, "corpus"));
  }

  render() {
    const data = this.data;
    return html`
      ${this.head("mdi:text-box-outline", this._t("step_corpus"), this._t("corpus_info"), "corpus")}
      <section class="card">
        <h3>${this._t("corpus_sources")}</h3>
        ${fileList(this, data?.sources ?? [], "corpus/sources")}
        <div class="row" style="margin-top: 10px">
          <input type="file" multiple accept=".txt,.tsv,.csv" data-corpus-upload ?disabled=${this.busy}
            @change=${(event) => upload(this, "corpus/upload", event)} />
        </div>
        <div class="grid2" style="margin-top: 12px">
          <label class="check"><input type="checkbox" data-corpus-bundled checked />${this._t("corpus_bundled")}</label>
          <label class="field"><span>${this._t("corpus_size")}</span>
            <input type="number" min="0" data-corpus-size placeholder=${String(data?.default_size ?? "")} />
            <span class="hint" data-corpus-size-hint>${this._t(Number(data?.overgenerate) > 1 ? "corpus_size_hint" : "corpus_size_hint_exact", {
              target: data?.target_clips ?? "", over: number(data?.overgenerate ?? 1, this.language, 1), size: data?.default_size ?? "" })}</span>
          </label>
        </div>
        <div class="row" style="margin-top: 12px">
          <span class="grow"></span>
          <button class="primary" data-run-corpus ?disabled=${this.busy || this.running}
            @click=${() => this.run(voicePath(this, "corpus"), {
              bundled: this.renderRoot.querySelector("[data-corpus-bundled]").checked,
              size: Number(this.renderRoot.querySelector("[data-corpus-size]").value) || 0,
            })}>
            <pvc-icon icon="mdi:play"></pvc-icon>${this._t("corpus_run")}
          </button>
        </div>
      </section>
      ${data?.prompts
        ? html`<section class="card" data-corpus-preview>
            <h3>${this._t("corpus_chosen", { count: number(data.prompts, this.language) })}</h3>
            <ol class="sentences">${data.preview.map((text) => html`<li>${text}</li>`)}</ol>
          </section>`
        : nothing}
    `;
  }

  static styles = [
    StepView.styles,
    fileStyles,
    css`
      .sentences {
        margin: 0;
        padding-left: 22px;
        max-height: 420px;
        overflow: auto;
        display: grid;
        gap: 2px;
      }
    `,
  ];
}
customElements.define("pvc-step-corpus", PvcStepCorpus);

// --- audition ----------------------------------------------------------------------------------------

class PvcStepAudition extends StepView {
  static properties = { ...StepView.properties, _slug: { state: true }, _applied: { state: true } };

  load() {
    return get(`${voicePath(this, "audition")}${this._slug ? `?slug=${encodeURIComponent(this._slug)}` : ""}`);
  }

  async _pick(slug) {
    this._slug = slug;
    this._applied = null;
    await this._reload();
  }

  async _apply() {
    try {
      const { options } = await post(voicePath(this, "audition/apply"), { value: this.data.chosen });
      this._applied = options;
    } catch (err) {
      this.error = err.message;
    }
  }

  render() {
    const data = this.data;
    const fmt = (value, digits) => (value === "" || value == null ? "—" : number(value, this.language, digits));
    return html`
      ${this.head("mdi:headphones", this._t("step_audition"), this._t("audition_info"), "audition")}
      <section class="card">
        <div class="row">
          <label class="field"><span>${this._t("audition_count")}</span>
            <input type="number" min="1" max="100" value="12" data-audition-count style="width: 120px" /></label>
          <span class="grow"></span>
          <button class="primary" data-run-audition ?disabled=${this.busy || this.running || !data?.prompts}
            @click=${() => this.run(voicePath(this, "audition"), { count: Number(this.renderRoot.querySelector("[data-audition-count]").value) || 12 })}>
            <pvc-icon icon="mdi:play"></pvc-icon>${this._t("audition_run")}
          </button>
        </div>
        ${data && !data.prompts ? html`<p class="warn">${this._t("audition_no_sentences")}</p>` : nothing}
      </section>
      ${data?.rows?.length
        ? html`<section class="card" data-audition-results>
            <h3>${this._t("audition_results")}</h3>
            <table>
              <tr><th>#</th><th>${this._t("audition_combo")}</th><th>${this._t("audition_score")}</th><th>CER</th><th>${this._t("audition_similarity")}</th><th>MOS</th></tr>
              ${data.rows.map(
                ([rank, slug, score, cer, similarity, mos]) => html`<tr class=${slug === data.chosen ? "sel" : ""} data-audition-row=${slug} @click=${() => this._pick(slug)}>
                  <td class="num">${rank}</td><td class="mono">${slug}</td><td class="num">${fmt(score, 3)}</td>
                  <td class="num">${fmt(cer, 3)}</td><td class="num">${fmt(similarity, 3)}</td><td class="num">${fmt(mos, 2)}</td>
                </tr>`,
              )}
            </table>
            <p class="hint">${this._t("audition_pick_hint")}</p>
            ${clips(data.clips, this.language)}
            <div class="row">
              <span class="hint">${this._t("audition_current", { options: JSON.stringify(data.options) })}</span>
              <span class="grow"></span>
              <button data-audition-apply @click=${this._apply}><pvc-icon icon="mdi:check"></pvc-icon>${this._t("audition_apply")}</button>
            </div>
            ${this._applied ? html`<p class="ok" data-audition-applied>${this._t("audition_applied", { options: JSON.stringify(this._applied) })}</p>` : nothing}
          </section>`
        : nothing}
    `;
  }

  static styles = [
    StepView.styles,
    clipStyles,
    css`
      tr[data-audition-row] {
        cursor: pointer;
      }
      tr.sel td {
        background: rgba(79, 140, 255, 0.12);
      }
      .ok {
        margin: 0;
        color: var(--green);
      }
    `,
  ];
}
customElements.define("pvc-step-audition", PvcStepAudition);

// --- generating --------------------------------------------------------------------------------------

class PvcStepSynthesize extends StepView {
  static properties = { ...StepView.properties, _account: { state: true } };

  load() {
    return get(voicePath(this, "synthesize"));
  }

  async _backend(value) {
    try {
      this.data = await post(voicePath(this, "synthesize/backend"), { value });
      this.error = null;
    } catch (err) {
      this.error = err.message;
    }
  }

  async _loadAccount() {
    this._account = { loading: true };
    try {
      this._account = await get("/api/elevenlabs/voices");
    } catch (err) {
      this._account = { error: err.message };
    }
  }

  async _pickVoice(value) {
    try {
      this.data = await post(voicePath(this, "synthesize/elevenlabs-voice"), { value });
    } catch (err) {
      this.error = err.message;
    }
  }

  render() {
    const data = this.data;
    const el = data?.elevenlabs;
    const timing = data?.timing;
    return html`
      ${this.head("mdi:waveform", this._t("step_synthesize"), this._t("synthesize_info"), "synthesize")}
      <section class="card">
        <h3>${this._t("synthesize_model")}</h3>
        <div class="seg" data-backend>
          ${(data?.backends ?? []).map(
            (name) => html`<button class=${name === data.backend ? "on" : ""} data-backend-option=${name} @click=${() => this._backend(name)}>${this._t(`backend_${name}`)}</button>`,
          )}
        </div>
        <p class="hint">${data ? this._t(`backend_${data.backend}_hint`) : ""}</p>
      </section>
      ${data?.backend === "elevenlabs" ? this._renderElevenLabs(el) : nothing}
      <section class="card">
        <h3>${this._t("synthesize_run_title")}</h3>
        <p data-synthesize-count>${this._t("synthesize_count", { raw: number(data?.raw ?? 0, this.language), prompts: number(data?.prompts ?? 0, this.language) })}</p>
        ${timing
          ? html`<p data-synthesize-timing>${this._t("synthesize_timing", {
              clips: timing.clips,
              minutes: number(timing.seconds / 60, this.language, 1),
              device: timing.device,
              per_clip: number(timing.per_clip, this.language, 1),
              speed: number(timing.speed, this.language, 2),
              total: number(data.prompts, this.language),
              estimate: duration(timing.estimate),
            })}</p>`
          : nothing}
        ${data && !data.prompts ? html`<p class="warn">${this._t("synthesize_no_sentences")}</p>` : nothing}
        <div class="row">
          <label class="field"><span>${this._t("synthesize_limit")}</span>
            <input type="number" min="0" data-synthesize-limit placeholder="0" style="width: 140px" />
            <span class="hint">${this._t("synthesize_limit_hint")}</span></label>
          <span class="grow"></span>
          <button class="primary" data-run-synthesize ?disabled=${this.busy || this.running || !data?.prompts}
            @click=${() => this.run(voicePath(this, "synthesize"), { limit: Number(this.renderRoot.querySelector("[data-synthesize-limit]").value) || 0 })}>
            <pvc-icon icon="mdi:play"></pvc-icon>${this._t("synthesize_run")}
          </button>
        </div>
      </section>
    `;
  }

  _renderElevenLabs(el) {
    const account = this._account;
    const credits = account?.credits;
    return html`<section class="card" data-elevenlabs>
      <h3>ElevenLabs</h3>
      ${el.key ? nothing : html`<p class="warn" data-el-no-key>${this._t("el_no_key")}</p>`}
      <div class="grid2">
        <label class="field"><span>${this._t("el_voice")}</span>
          <div class="row">
            <select class="grow" data-el-voice @change=${(event) => this._pickVoice(event.target.value)}>
              ${el.voice_id ? html`<option value=${el.voice_id} selected>${el.voice_name ?? el.voice_id}</option>` : html`<option value="" selected>${this._t("el_voice_pick")}</option>`}
              ${(account?.voices ?? []).filter((v) => v.id !== el.voice_id).map((v) => html`<option value=${v.id}>${v.name} (${v.category})</option>`)}
            </select>
            <button data-el-load ?disabled=${!el.key || account?.loading} @click=${this._loadAccount} title=${this._t("el_load")}>
              <pvc-icon icon="mdi:refresh"></pvc-icon>${this._t("el_load")}
            </button>
          </div>
          ${account?.error ? html`<span class="bad">${account.error}</span>` : nothing}
          ${credits ? html`<span class="hint" data-el-credits>${this._t("el_credits", { left: number(credits.left, this.language), limit: number(credits.limit, this.language) })}</span>` : nothing}
        </label>
        <label class="field"><span>${this._t("el_sentences")}</span>
          <div class="row">
            <select class="grow" data-el-set>
              ${el.sets.map((set) => html`<option value=${set.name}>${set.name} (${set.count})</option>`)}
            </select>
            <button data-el-use ?disabled=${!el.sets.length || this.running}
              @click=${() => this.run(voicePath(this, "synthesize/sentences"), { value: this.renderRoot.querySelector("[data-el-set]").value })}>
              ${this._t("el_use")}
            </button>
          </div>
          <span class="hint">${el.sets.length ? this._t("el_sentences_hint") : this._t("el_sets_none")}</span>
        </label>
      </div>
      <p data-el-cost>${this._t("el_cost", { sentences: number(el.missing_sentences, this.language), characters: number(el.missing_characters, this.language) })}</p>
    </section>`;
  }

  static styles = [StepView.styles, css`.bad { color: var(--red); }`];
}
customElements.define("pvc-step-synthesize", PvcStepSynthesize);

// --- filter ------------------------------------------------------------------------------------------

class PvcStepFilter extends StepView {
  load() {
    return get(voicePath(this, "filter"));
  }

  render() {
    const data = this.data;
    const report = data?.report;
    const check = (key) => html`<label class="check"><input type="checkbox" checked data-filter-check=${key} />${this._t(`filter_${key}`)}</label>`;
    return html`
      ${this.head("mdi:filter-outline", this._t("step_filter"), this._t("filter_info"), "filter")}
      ${data?.imported ? html`<p class="warn">${this._t("filter_imported")}</p>` : nothing}
      <section class="card">
        <div class="grid2">
          <label class="field"><span>${this._t("filter_target")}</span>
            <input type="number" min="0" data-filter-target placeholder=${String(data?.target_clips ?? "")} />
            <span class="hint">${this._t("filter_target_hint", { raw: number(data?.raw ?? 0, this.language) })}</span></label>
          <div class="checks">${check("asr")} ${check("similarity")} ${check("mos")}</div>
        </div>
        <div class="row" style="margin-top: 12px">
          <span class="grow"></span>
          <button class="primary" data-run-filter ?disabled=${this.busy || this.running || !data?.raw || data?.imported}
            @click=${() => {
              const on = (key) => this.renderRoot.querySelector(`[data-filter-check='${key}']`).checked;
              return this.run(voicePath(this, "filter"), {
                target: Number(this.renderRoot.querySelector("[data-filter-target]").value) || 0,
                asr: on("asr"),
                similarity: on("similarity"),
                mos: on("mos"),
              });
            }}>
            <pvc-icon icon="mdi:play"></pvc-icon>${this._t("filter_run")}
          </button>
        </div>
      </section>
      ${report?.rows
        ? html`<section class="card" data-filter-report>
            <h3>${this._t("filter_result")}</h3>
            <p>${this._t("import_result_text", { kept: report.kept, rows: report.rows })}</p>
            <table data-reasons>
              <tr><th>${this._t("reason")}</th><th>${this._t("reason_count")}</th><th>${this._t("reason_means")}</th></tr>
              ${report.reasons.map(([reason, count]) => html`<tr data-reason=${reason}><td class="mono">${reason}</td><td class="num">${count}</td><td class="hint">${this._t(`reason_${reason.replace(":", "_")}`, {}, "")}</td></tr>`)}
            </table>
            <div class="grid2">
              <div><h3>${this._t("clips_kept")}</h3>${clips(report.kept_clips, this.language, this._t("clips_none"))}</div>
              <div><h3>${this._t("clips_rejected")}</h3>${clips(report.rejected_clips, this.language, this._t("clips_none"))}</div>
            </div>
          </section>`
        : nothing}
    `;
  }

  static styles = [StepView.styles, clipStyles, css`.checks { display: grid; gap: 6px; align-content: start; padding-top: 22px; }`];
}
customElements.define("pvc-step-filter", PvcStepFilter);

VIEWS["step-reference"] = (p) => html`<pvc-step-reference .voice=${p.voice} .language=${p.language} .state=${p.state} .editor=${p.editor}></pvc-step-reference>`;
VIEWS["step-corpus"] = (p) => html`<pvc-step-corpus .voice=${p.voice} .language=${p.language} .state=${p.state} .editor=${p.editor}></pvc-step-corpus>`;
VIEWS["step-audition"] = (p) => html`<pvc-step-audition .voice=${p.voice} .language=${p.language} .state=${p.state} .editor=${p.editor}></pvc-step-audition>`;
VIEWS["step-synthesize"] = (p) => html`<pvc-step-synthesize .voice=${p.voice} .language=${p.language} .state=${p.state} .editor=${p.editor}></pvc-step-synthesize>`;
VIEWS["step-filter"] = (p) => html`<pvc-step-filter .voice=${p.voice} .language=${p.language} .state=${p.state} .editor=${p.editor}></pvc-step-filter>`;
