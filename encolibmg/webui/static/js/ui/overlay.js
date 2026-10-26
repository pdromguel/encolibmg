// Modal dialogs and small popup menus, rendered with lit-html into their own containers.
import { icon } from "../fx/icons.js";
import { html, render } from "../../vendor/lit-html.js";

let openModals = 0;
export const modalOpen = () => openModals > 0;

/**
 * Opens a modal. `content(close)` returns a lit template; `close(value)` resolves the promise.
 * Esc and clicking the backdrop resolve with `undefined`.
 */
export function modal(content, { wide = false } = {}) {
  return new Promise(resolve => {
    const scrim = document.createElement("div");
    scrim.className = "scrim";
    document.body.appendChild(scrim);
    openModals++;
    const prevFocus = document.activeElement;
    const close = value => {
      if (!scrim.isConnected) return;
      openModals--;
      document.removeEventListener("keydown", onKey, true);
      scrim.classList.add("out");
      setTimeout(() => scrim.remove(), 220);
      prevFocus?.focus?.();
      resolve(value);
    };
    const onKey = e => {
      if (e.key === "Escape") { e.stopPropagation(); close(undefined); }
    };
    document.addEventListener("keydown", onKey, true);
    scrim.addEventListener("pointerdown", e => { if (e.target === scrim) close(undefined); });
    const draw = () => render(html`
      <div class="modal-wrap brackets on ${wide ? "wide" : ""}">
        <div class="modal" role="dialog" aria-modal="true">
          <button class="btn quiet sm icon x" aria-label="Fechar" @click=${() => close(undefined)}>${icon("close")}</button>
          ${content(close, draw)}
        </div>
      </div>`, scrim);
    draw();
    requestAnimationFrame(() => scrim.querySelector("[autofocus], input, button.btn:not(.x)")?.focus());
  });
}

/** Simple confirm dialog. Resolves true/false. */
export function confirmDialog(title, text, { ok = "Confirmar", danger = false } = {}) {
  return modal(close => html`
    <h2>${title}</h2>
    <p class="lead">${text}</p>
    <div class="foot">
      <button class="btn ghost" @click=${() => close(false)}>Cancelar</button>
      <button class="btn ${danger ? "danger" : ""}" autofocus @click=${() => close(true)}>${ok}</button>
    </div>`).then(v => !!v);
}

/** Prompt with one or more text fields. Resolves {name: value} or undefined. */
export function promptDialog(title, fields, { lead = "", ok = "Salvar" } = {}) {
  const values = Object.fromEntries(fields.map(f => [f.name, f.value ?? ""]));
  return modal(close => html`
    <h2>${title}</h2>
    ${lead ? html`<p class="lead">${lead}</p>` : ""}
    <form class="col" @submit=${e => { e.preventDefault(); close(values); }}>
      ${fields.map((f, i) => html`
        <div><label class="lbl">${f.label}</label>
        <input class="field" ?autofocus=${i === 0} .value=${values[f.name]} placeholder=${f.placeholder || ""}
               @input=${e => values[f.name] = e.target.value}></div>`)}
      <div class="foot">
        <button type="button" class="btn ghost" @click=${() => close(undefined)}>Cancelar</button>
        <button type="submit" class="btn">${ok}</button>
      </div>
    </form>`);
}

let menuEl = null;
/** Popup menu next to `anchor`. items: [{label, run, kbd?}] or {section: "título"}. */
export function menu(anchor, items) {
  closeMenu();
  menuEl = document.createElement("div");
  menuEl.className = "menu";
  document.body.appendChild(menuEl);
  render(html`${items.map(it => it.section
    ? html`<div class="lbl">${it.section}</div>`
    : html`<button @click=${() => { closeMenu(); it.run(); }}>${it.label}<span class="grow"></span>${it.kbd ? html`<kbd>${it.kbd}</kbd>` : ""}</button>`)}`, menuEl);
  const r = anchor.getBoundingClientRect(), m = menuEl.getBoundingClientRect();
  menuEl.style.left = Math.max(8, Math.min(innerWidth - m.width - 8, r.right - m.width)) + "px";
  menuEl.style.top = Math.min(innerHeight - m.height - 8, r.bottom + 6) + "px";
  setTimeout(() => document.addEventListener("pointerdown", outside, true));
}
function outside(e) { if (menuEl && !menuEl.contains(e.target)) closeMenu(); }
export function closeMenu() {
  document.removeEventListener("pointerdown", outside, true);
  menuEl?.remove();
  menuEl = null;
}
