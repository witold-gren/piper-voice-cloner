// <pvc-help>: the "?" of a view or a card. It never leaves the page: a small window next to the button
// says what this one thing does (a title and a few sentences); ✕, Esc, a click beside it or "?" again
// close it. A quiet "More in the guide" link at the bottom is only an extra.
import { LitElement, css, html, nothing } from "./vendor/lit-all.min.js";
import { translate } from "./i18n.js";
import "./icon.js";

export class PvcHelp extends LitElement {
  static properties = {
    language: {},
    heading: {},
    text: {},
    link: {},
    open: { type: Boolean, reflect: true },
  };

  constructor() {
    super();
    this.open = false;
    this._onKey = (event) => event.key === "Escape" && this._close();
    this._onPointer = (event) => !event.composedPath().includes(this) && this._close();
  }

  _t(key) {
    return translate(this.language, key);
  }

  _toggle() {
    if (this.open) this._close();
    else {
      this.open = true;
      window.addEventListener("keydown", this._onKey);
      window.addEventListener("pointerdown", this._onPointer, true);
    }
  }

  _close() {
    this.open = false;
    window.removeEventListener("keydown", this._onKey);
    window.removeEventListener("pointerdown", this._onPointer, true);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this._close();
  }

  render() {
    return html`<button class="q" data-help-button aria-expanded=${this.open} aria-label=${this._t("help")} title=${this._t("help")} @click=${this._toggle}>
        <pvc-icon icon="mdi:help-circle-outline"></pvc-icon>
      </button>
      ${this.open
        ? html`<div class="pop" role="dialog" data-help-pop>
            <div class="head">
              <strong>${this.heading}</strong>
              <button class="x" data-help-close aria-label=${this._t("close")} @click=${this._close}><pvc-icon icon="mdi:close"></pvc-icon></button>
            </div>
            <p>${this.text}</p>
            ${this.link
              ? html`<a class="more" data-help-more href=${this.link} target="_blank" rel="noopener">${this._t("help_more")}</a>`
              : nothing}
          </div>`
        : nothing}`;
  }

  static styles = css`
    :host {
      position: relative;
      display: inline-flex;
    }
    button {
      font: inherit;
      border: 0;
      cursor: pointer;
      background: transparent;
      color: var(--muted);
      display: inline-flex;
      padding: 4px;
      border-radius: 999px;
    }
    .q {
      color: var(--link);
      --icon-size: 18px;
    }
    :host([open]) .q {
      background: rgba(79, 140, 255, 0.15);
    }
    .pop {
      position: absolute;
      top: calc(100% + 6px);
      right: 0;
      z-index: 25;
      width: min(340px, 80vw);
      padding: 12px 14px;
      border-radius: 12px;
      background: var(--panel);
      color: var(--text);
      border: 1px solid var(--line);
      box-shadow: 0 18px 40px var(--shadow);
      font-size: 13px;
      line-height: 1.45;
    }
    .head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
    }
    p {
      margin: 6px 0 0;
    }
    .more {
      display: inline-block;
      margin-top: 8px;
      font-size: 12px;
      color: var(--muted);
    }
    .x {
      --icon-size: 16px;
    }
  `;
}

customElements.define("pvc-help", PvcHelp);
