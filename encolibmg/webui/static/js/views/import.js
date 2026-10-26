// Import: pick a folder (CDs, CDG packs, .zip, .kar), preview with inline-editable names, import.
import { icon } from "../fx/icons.js";
import { html } from "../../vendor/lit-html.js";
import { call, runJob, tryCall } from "../api.js";
import { refresh } from "../app.js";
import { confetti } from "../fx/effects.js";
import { setView, state, view } from "../store.js";
import { toast } from "../ui/toast.js";
import { t, tt } from "../i18n.js";
import { noLibrary, pageHead } from "./common.js";

const OPTS = [["find_lyrics", true], ["make_multiplex", false], ["normalize", true], ["move", false]];  // label: ui.import.opt.<key>
const v = () => view("import", { folder: "", items: null, scanning: false,
  opts: Object.fromEntries(OPTS) });

async function pick() {
  const folder = await tryCall("import_pick");
  if (folder) { setView("import", { folder }); scan(folder); }
}

async function scan(folder = v().folder) {
  if (!folder) return;
  setView("import", { scanning: true, items: null });
  try {
    const items = await call("import_scan", folder);
    setView("import", { items, scanning: false });
  } catch (e) {
    setView("import", { scanning: false });
    toast(e.message, { kind: "bad" });
  }
}

async function edit(id, patch) {
  const items = await tryCall("import_edit", id, patch.artist ?? null, patch.title ?? null, patch.selected ?? null);
  if (items) setView("import", { items });
}

async function run() {
  const s = v(), n = s.items.filter(i => i.selected).length;
  if (!n) return;
  try {
    const res = await runJob("import_run", s.opts);
    setView("import", { items: res.items });
    await refresh();
    const ok = Object.values(res.results).filter(r => r.startsWith("imported")).length;
    toast(t("ui.import.done", { count: ok, total: n }), { kind: ok === n ? "ok" : "warn",
      detail: ok < n ? t("ui.import.see_status") : "" });
    if (ok) confetti(innerWidth / 2, innerHeight - 120);
  } catch (e) { if (e.kind !== "Cancelled") toast(e.message, { kind: "bad" }); }
}

// status codes from Python ("imported:<kind>", "error:<msg>", "exists"…); the text comes as status_text
function statusClass(st) {
  if (!st) return "";
  if (st.startsWith("imported")) return "ok";
  if (st.startsWith("error")) return "bad";
  return "warn";
}

export const importer = {
  render(st) {
    if (!st.app?.library) return html`<div class="page">${pageHead(t("ui.nav.import"), "")}${noLibrary()}</div>`;
    const s = v(), sel = s.items ? s.items.filter(i => i.selected).length : 0;
    return html`<div class="page imp">
      ${pageHead(t("ui.nav.import"), t("ui.import.sub"))}
      <div class="srcrow rise" style="--i:1">
        <button class="srcbox brackets hoverable ${s.folder ? "" : "on"}" @click=${pick}>
          <span class="big">${icon("folder")}</span>
          <span class="grow"><b>${t(s.folder ? "ui.import.source" : "ui.import.choose_folder")}</b>
            <span class="dim ellipsis">${s.folder || t("ui.import.hint")}</span></span>
          <span class="btn ghost sm">${t(s.folder ? "ui.import.change" : "ui.import.choose")}</span>
        </button>
        ${s.folder ? html`<button class="btn ghost" ?disabled=${s.scanning} @click=${() => scan()}>${t("ui.import.rescan")}</button>` : ""}
      </div>
      <div class="opts rise" style="--i:2">${OPTS.map(([k]) => html`<label class="check"><input type="checkbox" .checked=${s.opts[k]}
        @change=${e => setView("import", { opts: { ...s.opts, [k]: e.target.checked } })}>${t("ui.import.opt." + k)}</label>`)}</div>
      ${s.scanning ? html`<div class="results">${[0, 1, 2, 3].map(i => html`<div class="res skeleton" style="--i:${i}"></div>`)}</div>`
      : s.items === null ? "" : s.items.length === 0 ? html`<div class="empty"><h3>${t("ui.import.nothing")}</h3><p>${t("ui.import.nothing_text")}</p></div>`
      : html`
        <div class="itable rise" style="--i:3">
          <div class="ihead"><span></span><span>${t("ui.lib.artist")}</span><span>${t("ui.lib.title")}</span><span>${t("ui.import.col.type")}</span><span>${t("ui.import.col.source")}</span><span>${t("ui.import.col.status")}</span></div>
          ${s.items.map((it, i) => html`<div class="irow2 ${it.selected ? "" : "off"}" style="--i:${Math.min(i, 14)}">
            <label class="check"><input type="checkbox" .checked=${it.selected} @change=${e => edit(it.id, { selected: e.target.checked })}></label>
            <input class="field inline" .value=${it.artist} @change=${e => edit(it.id, { artist: e.target.value })}>
            <input class="field inline" .value=${it.title} @change=${e => edit(it.id, { title: e.target.value })}>
            <span class="badge">${it.kind_label}</span>
            <span class="src ellipsis dim" title=${[it.source, ...it.companions].join(" + ")}>${it.source}${it.companions.length ? html` <span class="muted">+${it.companions.length}</span>` : ""}</span>
            <span class="st ${statusClass(it.status)} ellipsis" title=${it.status_text}>${it.status_text || "—"}</span>
          </div>`)}
        </div>
        <div class="impbar">
          <span>${tt("ui.import.marked", { n: html`<b>${sel}</b>`, total: s.items.length })}</span>
          <button class="btn quiet sm" @click=${() => s.items.forEach(i => !i.selected && !i.status && edit(i.id, { selected: true }))}>${t("ui.import.select_all")}</button>
          <button class="btn quiet sm" @click=${() => s.items.forEach(i => i.selected && edit(i.id, { selected: false }))}>${t("ui.import.deselect")}</button>
          <span class="grow"></span>
          <button class="btn lg" ?disabled=${!sel || !!st.job} @click=${run}>${icon("down")} ${t("ui.nav.import")} ${sel || ""}</button>
        </div>`}
    </div>`;
  },
};
