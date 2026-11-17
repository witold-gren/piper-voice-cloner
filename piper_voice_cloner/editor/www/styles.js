// The look shared with the Home Dashboard and Assist Router editors: the same colours, radii and parts.
import { css } from "./vendor/lit-all.min.js";

// Colours of the dark look; the light one (data-theme="light") changes the same names.
export const tokens = css`
  :host {
    color-scheme: dark;
    --bg: #111318;
    --panel: #1b1e24;
    --panel2: #23272e;
    --line: #2f343c;
    --text: #e8eaed;
    --muted: #9aa0a6;
    --accent: #4f8cff;
    --accent-text: #cfe0ff;
    --link: #7fb2ff;
    --amber: #ffb340;
    --warn-text: #ffd99a;
    --red: #ff453a;
    --green: #30d158;
    --field: #0d0f13;
    --on: #3a3f48;
    --hover: rgba(255, 255, 255, 0.04);
    --faint: #5f6670;
    --scrim: rgba(0, 0, 0, 0.55);
    --shadow: rgba(0, 0, 0, 0.6);
    --terminal: #0d1117;
    --terminal-text: #c9d1d9;
  }
  :host([data-theme="light"]) {
    color-scheme: light;
    --bg: #f2f3f7;
    --panel: #ffffff;
    --panel2: #eceef3;
    --line: #d5d9e0;
    --text: #1d2026;
    --muted: #5f6670;
    --accent: #2f6fe4;
    --accent-text: #1f4fb0;
    --link: #2f6fe4;
    --amber: #a15c00;
    --warn-text: #8a5a00;
    --red: #d0021b;
    --green: #1c7f37;
    --field: #ffffff;
    --on: #ffffff;
    --hover: rgba(0, 0, 0, 0.04);
    --faint: #8a9099;
    --scrim: rgba(0, 0, 0, 0.3);
    --shadow: rgba(0, 0, 0, 0.18);
    --terminal: #0d1117;
    --terminal-text: #c9d1d9;
  }
`;

// Buttons, segmented controls, cards, fields: every component of the editor uses these.
export const base = css`
  * {
    box-sizing: border-box;
  }
  button {
    font: inherit;
    color: inherit;
    border: 0;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 7px 12px;
    border-radius: 9px;
    background: var(--panel2);
  }
  button:disabled {
    opacity: 0.4;
    cursor: default;
  }
  button.primary {
    background: var(--accent);
    color: #fff;
    font-weight: 600;
  }
  button.ghost {
    background: transparent;
    color: var(--muted);
  }
  button.danger {
    color: var(--red);
  }
  .seg {
    display: inline-flex;
    padding: 3px;
    gap: 2px;
    border-radius: 9px;
    background: var(--panel2);
  }
  .seg button {
    padding: 5px 12px;
    background: transparent;
    color: var(--muted);
  }
  .seg button.on {
    background: var(--on);
    color: var(--text);
  }
  .card {
    padding: 14px 16px;
    border-radius: 12px;
    background: var(--panel);
    border: 1px solid var(--line);
  }
  h3 {
    margin: 0 0 8px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--muted);
  }
  .muted {
    color: var(--muted);
  }
  .hint {
    font-size: 12px;
    color: var(--muted);
  }
  label.field {
    display: grid;
    gap: 4px;
  }
  label.field > span {
    font-weight: 600;
  }
  input,
  select,
  textarea {
    font: inherit;
    color: var(--text);
    padding: 7px 10px;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--field);
    min-width: 0;
  }
  input:focus,
  select:focus,
  textarea:focus {
    outline: none;
    border-color: rgba(79, 140, 255, 0.6);
  }
  pvc-icon {
    flex: none;
  }
`;

// A window over the editor (new voice, history, enlarged log).
export const dialogStyles = css`
  .scrim {
    position: fixed;
    inset: 0;
    z-index: 20;
    display: grid;
    place-items: center;
    background: var(--scrim);
  }
  .box {
    width: min(880px, calc(100vw - 48px));
    max-height: calc(100vh - 48px);
    overflow: auto;
    display: grid;
    gap: 14px;
    padding: 18px 20px;
    border-radius: 14px;
    background: var(--panel);
    border: 1px solid var(--line);
    box-shadow: 0 30px 80px var(--shadow);
  }
  .box h2 {
    margin: 0;
    font-size: 17px;
  }
  .box .actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
  }
`;
