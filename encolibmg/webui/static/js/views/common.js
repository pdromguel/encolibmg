// Shared bits for screens.
import { html } from "../../vendor/lit-html.js";
import { chooseLibrary } from "../app.js";
import { t, tt } from "../i18n.js";

// badge codes come from Python (views.badges); only some are words that need translating
const BADGE_TEXT = { ORPHAN: "ui.badge.orphan", AUDIO: "ui.badge.audio", GUIDE: "ui.badge.guide", CLIP: "ui.badge.clip" };
export const badgeText = b => (BADGE_TEXT[b] ? t(BADGE_TEXT[b]) : b);
export const badgeClass = b => "k-" + b;

export const badges = list => html`<span class="badges">${(list || []).map(b =>
  html`<span class="badge ${badgeClass(b)}">${badgeText(b)}</span>`)}</span>`;

export function pageHead(title, sub, actions = "") {
  return html`<div class="page-head rise">
    <div class="grow"><h2>${title}</h2>${sub ? html`<p class="sub">${sub}</p>` : ""}</div>
    ${actions}
  </div>`;
}

export function noLibrary(what = t("ui.nolib.default")) {
  return html`<div class="empty rise">
    <div class="box brackets on">
      <pixel-mark style="width:48px;height:48px;margin:0 auto 18px"></pixel-mark>
      <h3>${t("ui.nolib.title")}</h3>
      <p style="margin:8px 0 18px">${what}<br>${tt("ui.nolib.hint", { folder: html`<b>EncoreLibrary</b>` })}</p>
      <div class="row" style="justify-content:center">
        <button class="btn" @click=${chooseLibrary}>${t("ui.nolib.button")} <span class="k">Ctrl O</span></button>
      </div>
    </div>
  </div>`;
}

export function fmtSize(n) {
  if (!n) return "0 B";
  const u = ["B", "KB", "MB", "GB"];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return (i ? n.toFixed(1) : n) + " " + u[i];
}
