// "New voice": first the way (cloning or own recordings), then only the names.
import { LitElement, css, html, nothing } from "./vendor/lit-all.min.js";
import { translate } from "./i18n.js";
import { base, dialogStyles } from "./styles.js";
import "./icon.js";

export class PvcNewVoice extends LitElement {
  static properties = {
    language: {},
    error: {},
    busy: { type: Boolean },
    _workflow: { state: true },
  };

  constructor() {
    super();
    this._workflow = "clone";
  }

  _t(key, values) {
    return translate(this.language, key, values);
  }

  _submit(event) {
    event.preventDefault();
    const form = new FormData(event.target);
    this.dispatchEvent(
      new CustomEvent("create", {
        detail: { name: form.get("name"), piper_name: form.get("piper_name") || "", workflow: this._workflow },
      }),
    );
  }

  _close() {
    this.dispatchEvent(new CustomEvent("close"));
  }

  render() {
    const choice = (workflow, icon) => html`<button
      type="button"
      class="choice ${this._workflow === workflow ? "on" : ""}"
      data-workflow=${workflow}
      aria-pressed=${this._workflow === workflow}
      @click=${() => (this._workflow = workflow)}
    >
      <pvc-icon icon=${icon}></pvc-icon>
      <span class="text">
        <strong>${this._t(`new_voice_${workflow}`)}</strong>
        <span class="hint">${this._t(`new_voice_${workflow}_hint`)}</span>
      </span>
    </button>`;
    return html`<div class="scrim" @click=${(event) => event.target === event.currentTarget && this._close()}>
      <form class="box" data-new-voice @submit=${this._submit}>
        <h2>${this._t("new_voice_title")}</h2>
        <h3>${this._t("new_voice_how")}</h3>
        <div class="choices">${choice("clone", "mdi:account-voice")} ${choice("import", "mdi:folder-music")}</div>
        <label class="field">
          <span>${this._t("new_voice_name")}</span>
          <input name="name" required autofocus data-new-name />
          <span class="hint">${this._t("new_voice_name_hint")}</span>
        </label>
        <label class="field">
          <span>${this._t("new_voice_piper")}</span>
          <input name="piper_name" data-new-piper placeholder="pl_PL-…" />
          <span class="hint">${this._t("new_voice_piper_hint")}</span>
        </label>
        ${this.error ? html`<p class="error" data-new-error>${this.error}</p>` : nothing}
        <div class="actions">
          <button type="button" class="ghost" @click=${this._close}>${this._t("cancel")}</button>
          <button type="submit" class="primary" data-new-create ?disabled=${this.busy}>
            <pvc-icon icon="mdi:plus"></pvc-icon>${this._t("new_voice_create")}
          </button>
        </div>
      </form>
    </div>`;
  }

  static styles = [
    base,
    dialogStyles,
    css`
      .box {
        width: min(640px, calc(100vw - 48px));
      }
      .box h3 {
        margin: 0;
      }
      .choices {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 10px;
      }
      .choice {
        align-items: flex-start;
        text-align: left;
        gap: 10px;
        padding: 12px 14px;
        border: 1px solid var(--line);
        background: var(--panel2);
        --icon-size: 26px;
      }
      .choice.on {
        border-color: var(--accent);
        background: rgba(79, 140, 255, 0.15);
      }
      .choice .text {
        display: grid;
        gap: 4px;
      }
      .error {
        margin: 0;
        color: var(--red);
      }
      @media (max-width: 560px) {
        .choices {
          grid-template-columns: 1fr;
        }
      }
    `,
  ];
}

customElements.define("pvc-new-voice", PvcNewVoice);
