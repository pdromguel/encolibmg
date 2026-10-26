// Notifications, top-right. kind: ok | bad | warn | info. Optional action buttons.

import { t } from "../i18n.js";

const LIFE = { ok: 3800, info: 4200, warn: 6000, bad: 8000 };

export function toast(message, { kind = "info", detail = "", actions = [], life } = {}) {
  const host = document.getElementById("toasts");
  if (!host) return;
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.setAttribute("role", kind === "bad" ? "alert" : "status");
  el.innerHTML = `<span class="sq"></span><div class="msg"></div><button class="btn quiet sm icon" aria-label="">✕</button>`;
  el.querySelector("button").setAttribute("aria-label", t("ui.common.close"));
  el.querySelector(".msg").textContent = message;
  if (detail) {
    const small = document.createElement("small");
    small.textContent = detail;
    el.querySelector(".msg").appendChild(small);
  }
  if (actions.length) {
    const row = document.createElement("div");
    row.className = "actions";
    for (const a of actions) {
      const b = document.createElement("button");
      b.className = "btn sm " + (a.primary ? "" : "ghost");
      b.textContent = a.label;
      b.onclick = () => { close(); a.run(); };
      row.appendChild(b);
    }
    el.querySelector(".msg").appendChild(row);
  }
  const close = () => {
    if (!el.isConnected) return;
    el.classList.add("out");
    setTimeout(() => el.remove(), 260);
  };
  el.querySelector("button[aria-label]").onclick = close;
  host.prepend(el);
  while (host.children.length > 4) host.lastElementChild.remove();
  let timer = setTimeout(close, life ?? (LIFE[kind] + (actions.length ? 4000 : 0)));
  el.addEventListener("mouseenter", () => clearTimeout(timer));
  el.addEventListener("mouseleave", () => { timer = setTimeout(close, 2000); });
  return close;
}
