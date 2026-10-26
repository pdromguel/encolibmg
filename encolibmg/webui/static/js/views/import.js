// Importar: pick a folder (CDs, CDG packs, .zip, .kar), preview with inline-editable names, import.
import { icon } from "../fx/icons.js";
import { html } from "../../vendor/lit-html.js";
import { call, runJob, tryCall } from "../api.js";
import { refresh } from "../app.js";
import { confetti } from "../fx/overlay.js";
import { setView, state, view } from "../store.js";
import { toast } from "../ui/toast.js";
import { noLibrary, pageHead, plural } from "./common.js";

const OPTS = [
  ["find_lyrics", "Buscar letra para áudios sem letra", true],
  ["make_multiplex", "Gerar Multiplex + guia (lento, usa a GPU)", false],
  ["normalize", "Ajustar volume", true],
  ["move", "Mover (os originais vão para a Lixeira)", false],
];
const v = () => view("import", { folder: "", items: null, scanning: false,
  opts: Object.fromEntries(OPTS.map(([k, , d]) => [k, d])) });

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
    const ok = Object.values(res.results).filter(r => r.startsWith("importada")).length;
    toast(`${plural(ok, "faixa importada", "faixas importadas")} de ${n}.`, { kind: ok === n ? "ok" : "warn",
      detail: ok < n ? "Veja a coluna Situação para o motivo das outras." : "" });
    if (ok) confetti(innerWidth / 2, innerHeight - 120);
  } catch (e) { if (e.kind !== "Cancelled") toast(e.message, { kind: "bad" }); }
}

function statusClass(st) {
  if (!st) return "";
  if (st.startsWith("importada")) return "ok";
  if (st.startsWith("✖")) return "bad";
  return "warn";
}

export const importer = {
  render(st) {
    if (!st.app?.library) return html`<div class="page">${pageHead("Importar", "")}${noLibrary()}</div>`;
    const s = v(), sel = s.items ? s.items.filter(i => i.selected).length : 0;
    return html`<div class="page imp">
      ${pageHead("Importar", "Traga músicas que você já tem: CDs, coleções de karaokê em CDG, .zip, .kar.")}
      <div class="srcrow rise" style="--i:1">
        <button class="srcbox brackets hoverable ${s.folder ? "" : "on"}" @click=${pick}>
          <span class="big">${icon("folder")}</span>
          <span class="grow"><b>${s.folder ? "Pasta de origem" : "Escolher uma pasta"}</b>
            <span class="dim ellipsis">${s.folder || "Subpastas e arquivos .zip entram também. Nada é alterado até você importar."}</span></span>
          <span class="btn ghost sm">${s.folder ? "Trocar…" : "Escolher…"}</span>
        </button>
        ${s.folder ? html`<button class="btn ghost" ?disabled=${s.scanning} @click=${() => scan()}>Analisar de novo</button>` : ""}
      </div>
      <div class="opts rise" style="--i:2">${OPTS.map(([k, label]) => html`<label class="check"><input type="checkbox" .checked=${s.opts[k]}
        @change=${e => setView("import", { opts: { ...s.opts, [k]: e.target.checked } })}>${label}</label>`)}</div>
      ${s.scanning ? html`<div class="results">${[0, 1, 2, 3].map(i => html`<div class="res skeleton" style="--i:${i}"></div>`)}</div>`
      : s.items === null ? "" : s.items.length === 0 ? html`<div class="empty"><h3>Nada para importar</h3><p>Não achei áudio, vídeo, CDG ou MIDI nessa pasta.</p></div>`
      : html`
        <div class="itable rise" style="--i:3">
          <div class="ihead"><span></span><span>Artista</span><span>Título</span><span>Tipo</span><span>Origem</span><span>Situação</span></div>
          ${s.items.map((it, i) => html`<div class="irow2 ${it.selected ? "" : "off"}" style="--i:${Math.min(i, 14)}">
            <label class="check"><input type="checkbox" .checked=${it.selected} @change=${e => edit(it.id, { selected: e.target.checked })}></label>
            <input class="field inline" .value=${it.artist} @change=${e => edit(it.id, { artist: e.target.value })}>
            <input class="field inline" .value=${it.title} @change=${e => edit(it.id, { title: e.target.value })}>
            <span class="badge">${it.kind_label}</span>
            <span class="src ellipsis dim" title=${[it.source, ...it.companions].join(" + ")}>${it.source}${it.companions.length ? html` <span class="muted">+${it.companions.length}</span>` : ""}</span>
            <span class="st ${statusClass(it.status)} ellipsis" title=${it.status}>${it.status || "—"}</span>
          </div>`)}
        </div>
        <div class="impbar">
          <span><b>${sel}</b> de ${s.items.length} marcadas</span>
          <button class="btn quiet sm" @click=${() => s.items.forEach(i => !i.selected && !i.status && edit(i.id, { selected: true }))}>Marcar todas</button>
          <button class="btn quiet sm" @click=${() => s.items.forEach(i => i.selected && edit(i.id, { selected: false }))}>Desmarcar</button>
          <span class="grow"></span>
          <button class="btn lg" ?disabled=${!sel || !!st.job} @click=${run}>${icon("down")} Importar ${sel || ""}</button>
        </div>`}
    </div>`;
  },
};
