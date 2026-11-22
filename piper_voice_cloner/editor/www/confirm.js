// A question before an action that cannot be undone, as a window of the editor (never window.confirm:
// that one has the browser's look, ignores the theme and blocks the whole page).
//
//   if (!(await ask({ language, text, ok: "Delete", danger: true }))) return;
import { LitElement, css, html, nothing } from "./vendor/lit-all.min.js";
import { translate } from "./i18n.js";
import { base, dialogStyles } from "./styles.js";
import "./icon.js";

/** Show the question over the editor; true when the action button is clicked. */
export function ask({ language = "en", title = "", text, ok, danger = false, icon = "" }) {
  // inside the editor, so the window has its colours and theme
  const host = document.querySelector("pvc-editor")?.shadowRoot ?? document.body;
  const box = document.createElement("pvc-confirm");
  Object.assign(box, { language, heading: title, text, ok, danger, icon });
  host.appendChild(box);
  return new Promise((resolve) => {
    box.addEventListener(
      "answer",
      (event) => {
        box.remove();
        resolve(event.detail);
      },
      { once: true },
    );
  });
}

export class PvcConfirm extends LitElement {
  static properties = {
    language: {},
    heading: {},
    text: {},
    ok: {},
    danger: { type: Boolean },
    icon: {},
  };

  connectedCallback() {
    super.connectedCallback();
    // the button that opened it, through the shadow roots: the focus goes back there on close
    let active = document.activeElement;
    while (active?.shadowRoot?.activeElement) active = active.shadowRoot.activeElement;
    this._before = active;
    this._keys = (event) => this._key(event);
    window.addEventListener("keydown", this._keys, true);
  }

  disconnectedCallback() {
    window.removeEventListener("keydown", this._keys, true);
    this._before?.focus?.();
    super.disconnectedCallback();
  }

  firstUpdated() {
    // a dangerous action starts on Cancel, so Enter alone never does it
    this.renderRoot.querySelector(this.danger ? "[data-confirm-cancel]" : "[data-confirm-ok]")?.focus();
  }

  _answer(value) {
    this.dispatchEvent(new CustomEvent("answer", { detail: value }));
  }

  _key(event) {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      this._answer(false);
    } else if (event.key === "Tab") {
      // the focus stays in the window
      const buttons = [...this.renderRoot.querySelectorAll("button")];
      const at = buttons.indexOf(this.renderRoot.activeElement);
      event.preventDefault();
      buttons[(at + (event.shiftKey ? -1 : 1) + buttons.length) % buttons.length]?.focus();
    }
  }

  render() {
    const t = (key) => translate(this.language, key);
    return html`<div class="scrim" @click=${(event) => event.target === event.currentTarget && this._answer(false)}>
      <div class="box" role="alertdialog" aria-modal="true" aria-labelledby="q" data-confirm>
        ${this.heading ? html`<h2 id="q">${this.heading}</h2>` : nothing}
        <p class="text" id=${this.heading ? "text" : "q"} data-confirm-text>${this.text}</p>
        <div class="actions">
          <button type="button" class="ghost" data-confirm-cancel @click=${() => this._answer(false)}>${t("cancel")}</button>
          <button type="button" class=${this.danger ? "solid-danger" : "primary"} data-confirm-ok @click=${() => this._answer(true)}>
            ${this.icon ? html`<pvc-icon icon=${this.icon}></pvc-icon>` : nothing}${this.ok || t("ok")}
          </button>
        </div>
      </div>
    </div>`;
  }

  static styles = [
    base,
    dialogStyles,
    css`
      .box {
        width: min(520px, calc(100vw - 32px));
      }
      .text {
        margin: 0;
        white-space: pre-line;
        line-height: 1.5;
      }
      button.solid-danger {
        background: var(--red);
        color: #fff;
        font-weight: 600;
      }
    `,
  ];
}
customElements.define("pvc-confirm", PvcConfirm);
