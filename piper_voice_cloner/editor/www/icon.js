// <pvc-icon icon="mdi:<name>">: Material Design Icons drawn from the paths in vendor/mdi.js
// (only the icons the editor uses, so it works without the internet).
import { ICONS } from "./vendor/mdi.js";

class PvcIcon extends HTMLElement {
  static get observedAttributes() {
    return ["icon"];
  }

  set icon(value) {
    this.setAttribute("icon", value);
  }

  get icon() {
    return this.getAttribute("icon");
  }

  connectedCallback() {
    this._draw();
  }

  attributeChangedCallback() {
    this._draw();
  }

  // drawn in its own shadow root: children added to the element itself would shift the nodes
  // Lit counts in a cloned template (the icon is upgraded, with its attribute, before Lit walks it)
  _draw() {
    const path = ICONS[this.getAttribute("icon")] ?? "";
    const root = this.shadowRoot ?? this.attachShadow({ mode: "open" });
    root.innerHTML = `<style>:host{display:inline-flex;width:var(--icon-size,18px);height:var(--icon-size,18px)}svg{width:100%;height:100%}</style><svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="${path}"/></svg>`;
  }
}

if (!customElements.get("pvc-icon")) customElements.define("pvc-icon", PvcIcon);
