// Shared bits for screens.
import { html } from "../../vendor/lit-html.js";
import { chooseLibrary } from "../app.js";

export const badgeClass = b => "k-" + ({ "⚠": "orphan", "ÁUDIO": "AUDIO" }[b] || b);

export const badges = list => html`<span class="badges">${(list || []).map(b =>
  html`<span class="badge ${badgeClass(b)}">${b === "⚠" ? "⚠ INVISÍVEL" : b}</span>`)}</span>`;

export function pageHead(title, sub, actions = "") {
  return html`<div class="page-head rise">
    <div class="grow"><h2>${title}</h2>${sub ? html`<p class="sub">${sub}</p>` : ""}</div>
    ${actions}
  </div>`;
}

export function noLibrary(what = "Abra uma biblioteca para começar.") {
  return html`<div class="empty rise">
    <div class="box brackets on">
      <pixel-mark style="width:48px;height:48px;margin:0 auto 18px"></pixel-mark>
      <h3>Nenhuma biblioteca aberta</h3>
      <p style="margin:8px 0 18px">${what}<br>O Encore procura uma pasta chamada <b>EncoreLibrary</b>.</p>
      <div class="row" style="justify-content:center">
        <button class="btn" @click=${chooseLibrary}>Abrir ou criar biblioteca <span class="k">Ctrl O</span></button>
      </div>
    </div>
  </div>`;
}

export const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;

export function fmtSize(n) {
  if (!n) return "0 B";
  const u = ["B", "KB", "MB", "GB"];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return (i ? n.toFixed(1) : n) + " " + u[i];
}
