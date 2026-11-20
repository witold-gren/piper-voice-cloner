// The tour of the editor: one part of the screen at a time framed, the rest dimmed, and a bubble that says what it
// is and where it is set. It starts by itself the first time the editor opens in a browser and from ⚙ whenever
// asked; a step whose part is not on the screen is left out. The lessons (lessons.js) are tours of one task each:
// their steps first go where the task is done (`prepare`: a node of the tree) and may wait for the framed button
// to be clicked (`advance: "click"`), so the task is done while it is learnt. The same as the Home Dashboard editor.
import { LitElement, css, html, nothing } from "./vendor/lit-all.min.js";
import { translate } from "./i18n.js";

export const TOUR_KEY = "pvc-studio-tour";
export const LESSONS_KEY = "pvc-studio-lessons";
const BUBBLE_WIDTH = 360;
const GAP = 16;
const PAD = 8;

// Each step: its key (texts tour_<key>_title, _text and, with `where`, _where), the parts it frames (one frame
// round all of them) and the side of the bubble.
export const TOUR_STEPS = [
  { key: "welcome", targets: [] },
  { key: "tree", targets: ["[data-tree]"], side: "right", where: true },
  { key: "new_voice", targets: ["[data-new-voice-button]"], side: "right" },
  { key: "middle", targets: ["[data-middle]"], side: "inside", where: true },
  { key: "side", targets: ["[data-side]"], side: "left", where: true },
  { key: "top", targets: ["[data-top-job]", "[data-top-machine]", "[data-countdown]"], side: "below-end" },
  { key: "help", targets: ["[data-docs]", "[data-editor-settings]"], side: "below-end", where: true },
  { key: "menu", targets: ["[data-menu]"], side: "below" },
];

function readList(key) {
  try {
    const value = JSON.parse(window.localStorage.getItem(key) ?? "[]");
    return Array.isArray(value) ? value : [];
  } catch {
    return [];
  }
}

function store(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // a private window may refuse it: then nothing is remembered
  }
}

/** The keys of the lessons gone through in this browser. */
export function lessonsDone() {
  return readList(LESSONS_KEY);
}

export function markLessonDone(key) {
  const done = lessonsDone();
  if (!done.includes(key)) store(LESSONS_KEY, JSON.stringify([...done, key]));
}

/**
 * Whether the tour was seen (or skipped) in this browser. Without the storage of the browser it could not
 * remember being skipped and would come back every time, so it counts as seen; ⚙ still opens it.
 */
export function tourSeen() {
  try {
    return window.localStorage.getItem(TOUR_KEY) === "done";
  } catch {
    return true;
  }
}

// The first element for a selector in a root or any shadow root under it.
function deepFind(root, selector) {
  const found = root.querySelector?.(selector);
  if (found) return found;
  for (const element of root.querySelectorAll?.("*") ?? []) {
    if (!element.shadowRoot) continue;
    const inner = deepFind(element.shadowRoot, selector);
    if (inner) return inner;
  }
  return null;
}

/** The element a target names: a selector, or selectors joined by ">>>" for one inside another. */
export function findTarget(root, target) {
  let scope = root;
  for (const selector of target.split(">>>").map((part) => part.trim())) {
    if (!scope) return null;
    scope = deepFind(scope.shadowRoot ?? scope, selector) ?? (scope.shadowRoot ? deepFind(scope, selector) : null);
  }
  return scope && scope !== root ? scope : null;
}

/** The steps there is something on the screen for. */
export function shownSteps(root, steps = TOUR_STEPS) {
  return steps.filter((step) => !step.targets.length || step.targets.some((target) => findTarget(root, target)));
}

/** One rectangle round the parts of a step that are on the screen, a little larger; null for none. */
export function frameOf(root, targets, width = window.innerWidth, height = window.innerHeight) {
  const boxes = targets
    .map((target) => (root ? findTarget(root, target) : null)?.getBoundingClientRect())
    .filter((box) => box && box.width && box.height);
  if (!boxes.length) return null;
  const left = Math.max(4, Math.min(...boxes.map((box) => box.left)) - PAD);
  const top = Math.max(4, Math.min(...boxes.map((box) => box.top)) - PAD);
  const right = Math.min(width - 4, Math.max(...boxes.map((box) => box.right)) + PAD);
  const bottom = Math.min(height - 4, Math.max(...boxes.map((box) => box.bottom)) + PAD);
  return { left, top, width: right - left, height: bottom - top };
}

/** Where the bubble stands: on the chosen side of the frame, kept inside the window. */
export function bubbleAt(frame, side, bubbleHeight, width = window.innerWidth, height = window.innerHeight) {
  const bubble = { width: Math.min(BUBBLE_WIDTH, width - 2 * GAP), height: bubbleHeight ?? 220 };
  const clampX = (x) => Math.max(GAP, Math.min(width - bubble.width - GAP, x));
  const clampY = (y) => Math.max(GAP, Math.min(height - bubble.height - GAP, y));
  if (!frame) return { left: clampX((width - bubble.width) / 2), top: clampY(height * 0.28), width: bubble.width };
  const below = frame.top + frame.height + GAP;
  const places = {
    right: { left: frame.left + frame.width + GAP, top: frame.top + 40 },
    left: { left: frame.left - bubble.width - GAP, top: frame.top + 40 },
    below: { left: frame.left, top: below },
    "below-end": { left: frame.left + frame.width - bubble.width, top: below },
    inside: { left: frame.left + 24, top: frame.top + frame.height - bubble.height - 24 },
  };
  places.above = { left: frame.left, top: frame.top - bubble.height - GAP };
  // the chosen side first; when the bubble would cover the frame there, the next side that leaves it free
  const order = [side ?? "below", "right", "left", "below", "above"];
  const covers = (at) =>
    at.left < frame.left + frame.width && at.left + bubble.width > frame.left &&
    at.top < frame.top + frame.height && at.top + bubble.height > frame.top;
  const fits = order
    .map((name) => places[name])
    .filter(Boolean)
    .map((place) => ({ left: clampX(place.left), top: clampY(place.top), width: bubble.width }));
  return side === "inside" ? fits[0] : fits.find((at) => !covers(at)) ?? fits[0];
}

export class PvcTour extends LitElement {
  static properties = {
    root: { attribute: false },
    language: {},
    // a lesson instead of the tour: { key, steps } and the editor its steps prepare (choose a node)
    lesson: { attribute: false },
    host: { attribute: false },
    _index: { state: true },
  };

  constructor() {
    super();
    this._index = 0;
    this._onResize = () => this.requestUpdate();
    // a click on the framed part of a step that waits for it moves on, once what it opens is there
    this._onClick = (event) => {
      const step = this._steps?.[this._index];
      if (step?.advance !== "click" || !this._frame) return;
      const { left, top, width, height } = this._frame;
      if (event.clientX < left || event.clientX > left + width || event.clientY < top || event.clientY > top + height) return;
      const at = this._index;
      setTimeout(() => this._index === at && this._go(1), 400);
    };
    this._onKey = (event) => {
      // arrows and Enter in a field (a name typed in a lesson) belong to the field
      const field = event.composedPath()[0];
      if (event.key !== "Escape" && ["INPUT", "TEXTAREA", "SELECT"].includes(field?.tagName)) return;
      if (event.key === "Escape") this._finish();
      else if (event.key === "ArrowRight") this._next();
      else if (event.key === "ArrowLeft") this._go(-1);
      else return;
      event.preventDefault();
      event.stopPropagation();
    };
  }

  _t(key, values) {
    return translate(this.language, key, values);
  }

  connectedCallback() {
    super.connectedCallback();
    window.addEventListener("resize", this._onResize);
    window.addEventListener("keydown", this._onKey, true);
    window.addEventListener("click", this._onClick, true);
    // what a step frames can move or appear (a window opening, a view loading): the frame follows it
    this._follow = setInterval(() => this.requestUpdate(), 400);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    window.removeEventListener("resize", this._onResize);
    window.removeEventListener("keydown", this._onKey, true);
    window.removeEventListener("click", this._onClick, true);
    clearInterval(this._follow);
  }

  get _prefix() {
    return this.lesson ? `lesson_${this.lesson.key}` : "tour";
  }

  willUpdate(changed) {
    // the tour leaves out what is not on the screen; a lesson goes where its steps are, so all of them stay
    if (changed.has("root") || changed.has("lesson") || !this._steps) {
      this._steps = this.lesson ? this.lesson.steps : shownSteps(this.root);
      this._prepared = null;
    }
    const step = this._steps?.[this._index];
    if (step && this._prepared !== this._index) {
      this._prepared = this._index;
      step.prepare?.(this.host);
    }
  }

  // the bubble's own height is known once it is drawn: it is placed again with it
  updated() {
    const height = this.renderRoot.querySelector("[data-tour-bubble]")?.offsetHeight;
    if (height && height !== this._height) {
      this._height = height;
      this.requestUpdate();
    }
  }

  /** "Next" on a step that waits for a click does that click: the steps after it need what it opens. */
  _next() {
    const step = this._steps?.[this._index];
    if (this._clicking === this._index) return; // a second "Next" while the first click opens its part
    if (step?.advance === "click") {
      const part = this._targets(step).map((target) => findTarget(this.root, target)).find(Boolean);
      if (part) {
        const at = this._index;
        this._clicking = at;
        part.click();
        setTimeout(() => this._index === at && this._go(1), 400);
        return;
      }
    }
    this._go(1);
  }

  _go(by) {
    this._clicking = null;
    const next = this._index + by;
    if (next < 0) return;
    if (next >= this._steps.length) return this._finish();
    this._index = next;
  }

  _finish() {
    if (this.lesson) {
      // a lesson counts as done once it was gone through to its last step
      if (this._index === this._steps.length - 1) markLessonDone(this.lesson.key);
    } else store(TOUR_KEY, "done");
    this.dispatchEvent(new CustomEvent("tour-close", { bubbles: true, composed: true }));
  }

  _targets(step) {
    const targets = typeof step.targets === "function" ? step.targets(this.host) : step.targets;
    return targets ?? [];
  }

  render() {
    const steps = this._steps ?? [];
    const step = steps[this._index];
    if (!step) return nothing;
    const targets = this._targets(step);
    // what comes only after an earlier click is framed by the part it belongs to until then
    const frame = frameOf(this.root, targets) ?? (step.fallback ? frameOf(this.root, step.fallback) : null);
    this._frame = frame;
    // a part below or above the window is scrolled to, once a step (by the part itself: its frame is cut to
    // the window and would look like nothing)
    const part = [...targets, ...(step.fallback ?? [])].map((target) => findTarget(this.root, target)).find(Boolean);
    const box = part?.getBoundingClientRect();
    // once a step, always: a part inside the window can still be cut by its scrolling column ("nearest"
    // does nothing to a part fully shown)
    if (box && this._scrolled !== this._index) {
      this._scrolled = this._index;
      const below = box.bottom > window.innerHeight || box.top < 0;
      part.scrollIntoView({ block: !below ? "nearest" : box.height > window.innerHeight * 0.6 ? "start" : "center" });
      requestAnimationFrame(() => this.requestUpdate());
    }
    const at = bubbleAt(frame, step.side, this._height);
    const last = this._index === steps.length - 1;
    const base = `${this._prefix}_${step.key}`;
    const waits = step.advance === "click" && frame;
    // a step that waits for a click, or lets the framed part be used (a name typed in), keeps it open
    const open = (waits || step.interact) && frame;
    return html`
      ${open ? this._renderBlockers(frame) : html`<div class="block" data-tour-block></div>`}
      ${frame
        ? html`<div class="frame" data-tour-frame=${step.key}
            style="left:${frame.left}px;top:${frame.top}px;width:${frame.width}px;height:${frame.height}px"></div>`
        : html`<div class="dim"></div>`}
      <section class="bubble" role="dialog" aria-label=${this._t(`${base}_title`)} data-tour-bubble=${step.key}
        style="left:${at.left}px;top:${at.top}px;width:${at.width}px">
        <div class="top">
          <span data-tour-count>${this.lesson
            ? this._t("lesson_step", { name: this._t(`lesson_${this.lesson.key}_name`), step: this._index + 1, count: steps.length })
            : this._t("tour_step", { step: this._index + 1, count: steps.length })}</span>
          <button class="close" data-tour-close aria-label=${this._t("close")} @click=${this._finish}>×</button>
        </div>
        <h3>${this._t(`${base}_title`)}</h3>
        <p>${this._t(`${base}_text`)}</p>
        ${step.where ? html`<div class="where"><strong>${this._t("tour_where")}</strong> ${this._t(`${base}_where`)}</div>` : nothing}
        ${waits ? html`<p class="try" data-tour-try>${this._t("lesson_try")}</p>` : nothing}
        <div class="bottom">
          <div class="dots" aria-hidden="true">${steps.map((_, index) => html`<i class=${index === this._index ? "on" : ""}></i>`)}</div>
          ${this._index
            ? html`<button class="ghost" data-tour-back @click=${() => this._go(-1)}>${this._t("tour_back")}</button>`
            : html`<button class="link" data-tour-skip @click=${this._finish}>${this._t("tour_skip")}</button>`}
          <button class="primary" data-tour-next @click=${() => this._next()}>${last ? this._t("tour_done") : this._t("tour_next")}</button>
        </div>
      </section>
    `;
  }

  // around a frame that waits for a click: the rest is blocked, the framed part takes the click
  _renderBlockers(frame) {
    const right = frame.left + frame.width;
    const bottom = frame.top + frame.height;
    const box = (left, top, width, height) =>
      html`<div class="blocker" style="left:${left}px;top:${top}px;width:${Math.max(0, width)}px;height:${Math.max(0, height)}px"></div>`;
    return html`<div data-tour-block="open">
      ${box(0, 0, window.innerWidth, frame.top)} ${box(0, bottom, window.innerWidth, window.innerHeight - bottom)}
      ${box(0, frame.top, frame.left, frame.height)} ${box(right, frame.top, window.innerWidth - right, frame.height)}
    </div>`;
  }

  static styles = css`
    :host {
      position: fixed;
      inset: 0;
      z-index: 40;
      pointer-events: none;
      font: 14px/1.45 -apple-system, "SF Pro Text", Roboto, system-ui, sans-serif;
    }
    .block {
      position: absolute;
      inset: 0;
    }
    .blocker {
      position: absolute;
    }
    .block,
    .blocker,
    .bubble {
      pointer-events: auto;
    }
    .dim {
      position: absolute;
      inset: 0;
      background: rgba(8, 14, 24, 0.58);
    }
    .frame {
      position: absolute;
      border-radius: 12px;
      pointer-events: none;
      box-shadow: 0 0 0 3px #fff, 0 0 0 7px rgba(79, 140, 255, 0.55), 0 0 0 9999px rgba(8, 14, 24, 0.58);
      transition: left 0.25s, top 0.25s, width 0.25s, height 0.25s;
    }
    .bubble {
      position: absolute;
      box-sizing: border-box;
      padding: 16px;
      border-radius: 14px;
      color: var(--text);
      background: var(--panel);
      border: 1px solid var(--line);
      box-shadow: 0 20px 50px rgba(0, 0, 0, 0.35);
      transition: left 0.25s, top 0.25s;
    }
    .top {
      display: flex;
      justify-content: space-between;
      align-items: center;
      color: var(--muted);
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }
    h3 {
      margin: 6px 0;
      font-size: 17px;
    }
    p {
      margin: 0 0 10px;
    }
    .where {
      padding: 8px 10px;
      border-radius: 10px;
      color: var(--accent-text);
      background: rgba(79, 140, 255, 0.12);
      font-size: 13px;
    }
    .try {
      margin: 10px 0 0;
      color: var(--link);
      font-weight: 600;
      font-size: 13px;
    }
    .bottom {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-top: 14px;
    }
    .dots {
      display: flex;
      flex: 1;
      flex-wrap: wrap;
      gap: 4px;
    }
    .dots i {
      width: 6px;
      height: 6px;
      border-radius: 3px;
      background: var(--line);
    }
    .dots i.on {
      width: 18px;
      background: var(--accent);
    }
    button {
      font: inherit;
      cursor: pointer;
    }
    .close {
      border: 0;
      background: none;
      color: inherit;
      font-size: 20px;
      line-height: 1;
    }
    .ghost {
      padding: 7px 14px;
      border: 1px solid var(--line);
      border-radius: 10px;
      color: var(--text);
      background: transparent;
    }
    .link {
      border: 0;
      background: none;
      color: var(--muted);
    }
    .primary {
      padding: 7px 16px;
      border: 0;
      border-radius: 10px;
      color: #fff;
      background: var(--accent);
      font-weight: 600;
    }
  `;
}

customElements.define("pvc-tour", PvcTour);
