// EncoLibMG shell: header, routed screens with a pixel dissolve, dock (job progress + mini player), keys.
import { icon } from "./fx/icons.js";
import { html, render } from "../vendor/lit-html.js";
import { call, on, tryCall } from "./api.js";
import { loadBrand } from "./fx/elements.js";
import { fmtTime } from "./fx/core.js";
import { pixelWipe } from "./fx/overlay.js";
import { player } from "./player.js";
import { set, state, subscribe } from "./store.js";
import { closeMenu, menu, modal, modalOpen, promptDialog } from "./ui/overlay.js";
import { toast } from "./ui/toast.js";
import { screens, NAV } from "./views/index.js";

const root = document.getElementById("app");

/* ---------------------------------------------------------------- routing --- */
function parseHash() {
  const [name, ...rest] = location.hash.replace(/^#\/?/, "").split("/");
  return { name: screens[name] ? name : "home", param: rest.length ? decodeURIComponent(rest.join("/")) : null };
}

export function go(name, param = null) {
  const hash = "#/" + name + (param != null ? "/" + encodeURIComponent(param) : "");
  if (location.hash !== hash) location.hash = hash;
}

let leaving = null;
async function route() {
  const next = parseHash(), cur = state.route;
  if (cur.name === next.name && cur.param === next.param && leaving === null) return;
  closeMenu();
  screens[cur.name]?.leave?.();
  leaving = next;
  await pixelWipe(() => set({ route: next }));
  leaving = null;
  screens[next.name]?.enter?.(next.param);
}
addEventListener("hashchange", route);

/* ---------------------------------------------------------------- library --- */
export async function refresh({ tracks = true } = {}) {
  const app = await tryCall("state");
  if (app) set({ app, job: app.job || state.job });
  if (tracks && app?.library) {
    const list = await tryCall("tracks");
    if (list) set({ tracks: list });
  } else if (!app?.library) set({ tracks: null });
}

export async function chooseLibrary() {
  const picked = await tryCall("library_pick");
  if (!picked) return;
  if (picked.has_manifest) {
    const app = await tryCall("library_open", picked.path);
    if (app) { set({ app, view: {} }); await refresh(); toast(`Biblioteca “${app.library.title}” aberta.`, { kind: "ok" }); }
    return;
  }
  const res = await promptDialog("Criar biblioteca", [{ name: "title", label: "Nome (aparece no Encore)",
    value: "Minha Biblioteca" }], { lead: `Vou criar a pasta EncoreLibrary dentro de ${picked.path}, com o manifest.json que o Encore procura.`, ok: "Criar" });
  if (!res) return;
  const app = await tryCall("library_create", picked.path, res.title);
  if (app) { set({ app, view: {} }); await refresh(); toast(`Pronto: “${app.library.title}” criada.`, { kind: "ok", detail: app.library.path }); }
}

function libraryMenu(e) {
  const lib = state.app?.library;
  menu(e.currentTarget, [
    ...(lib ? [{ section: lib.path }, { label: "Abrir pasta no Explorer", run: () => tryCall("open_folder") },
               { label: "Configurar biblioteca…", run: openSettings }] : []),
    { section: "Biblioteca" },
    { label: "Abrir ou criar outra…", kbd: "Ctrl O", run: chooseLibrary },
  ]);
}

/* ---------------------------------------------------------------- settings --- */
export async function openSettings() {
  const s = await tryCall("settings_get");
  if (!s) return;
  const res = await modal(close => html`
    <h2>Configurar biblioteca</h2>
    <p class="lead">Como a biblioteca aparece no Encore. Reabra a biblioteca no Encore (F2) para aplicar.</p>
    <div class="col" style="gap:14px">
      <div><label class="lbl">Nome</label><input class="field" .value=${s.title} @input=${e => s.title = e.target.value}></div>
      <div><label class="lbl">Descrição</label><textarea class="field" rows="3" .value=${s.description}
           @input=${e => s.description = e.target.value}></textarea></div>
      <div class="col" style="gap:8px">
        <span class="lbl" style="margin:0">Opções do Encore</span>
        ${s.flags.map(f => html`<label class="check"><input type="checkbox" .checked=${f.value}
          @change=${e => f.value = e.target.checked}>${f.label}</label>`)}
      </div>
    </div>
    <div class="foot"><button class="btn ghost" @click=${() => close()}>Cancelar</button>
      <button class="btn" @click=${() => close(s)}>Salvar</button></div>`);
  if (!res) return;
  const app = await tryCall("settings_save", res);
  if (app) { set({ app }); toast("Configuração salva.", { kind: "ok", detail: "Reabra a biblioteca no Encore para aplicar." }); }
}

/* ---------------------------------------------------------------- help --- */
export function openHelp() {
  const k = (...keys) => html`<span class="k">${keys.map(x => html`<kbd>${x}</kbd>`)}</span>`;
  modal(() => html`
    <h2>Atalhos</h2>
    <p class="lead">Tudo no EncoLibMG funciona pelo teclado também.</p>
    <div class="keys">
      ${k("/")}<span>Buscar uma música</span>
      ${k("1", "–", "6")}<span>Trocar de tela (Início, Adicionar, Biblioteca, Verificar, Importar, Visual)</span>
      ${k("Espaço")}<span>Tocar / pausar · na Sincronia: marcar âncora</span>
      ${k("←", "→")}<span>Voltar / avançar 5 s no player</span>
      ${k("Esc")}<span>Fechar janela, painel ou voltar</span>
      ${k("Ctrl", "O")}<span>Abrir ou criar biblioteca</span>
      ${k("?")}<span>Esta ajuda</span>
    </div>`);
}

/* ---------------------------------------------------------------- shell --- */
const pct = f => (f == null ? "" : Math.round(f * 100) + "%");

function header(s) {
  const lib = s.app?.library;
  return html`
  <header class="hdr">
    <a class="brand" href="#/home" aria-label="EncoLibMG — início">
      <pixel-mark ?singing=${!!s.job}></pixel-mark>
      <span class="name">EncoLib<b>MG</b></span>
    </a>
    <nav class="nav">
      ${NAV.map((n, i) => html`<a href="#/${n.name}" class=${s.route.name === n.name || screens[s.route.name]?.parent === n.name ? "on" : ""}>
        <span class="n">${i + 1}</span>${n.label}</a>`)}
    </nav>
    <div class="right">
      <div class="libchip ${lib ? "" : "none"}" @click=${libraryMenu} title=${lib?.path || ""}>
        <span class="dot"></span><span class="ellipsis">${lib ? lib.title : "Nenhuma biblioteca"}</span><span class="muted">▾</span>
      </div>
      <button class="btn quiet icon" data-tip="Configurar" aria-label="Configurar" @click=${openSettings} ?disabled=${!lib}>${icon("gear")}</button>
      <button class="btn quiet icon" data-tip="Atalhos  ?" aria-label="Atalhos" @click=${openHelp}>?</button>
    </div>
  </header>`;
}

function dock(s) {
  const j = s.job, p = s.player;
  return html`
  <footer class="dock">
    ${j ? html`<div class="job">
        <pixel-progress value=${j.frac == null ? -1 : j.frac}></pixel-progress>
        <span class="step">${j.step || j.label}</span>
        <span class="pct">${pct(j.frac)}</span>
        <button class="btn ghost sm" @click=${() => tryCall("job_cancel")}>Cancelar</button>
      </div>`
      : html`<div class="job idle"><pixel-progress value=""></pixel-progress>
        <span class="step">${s.lastJob || "Pronto."}</span></div>`}
    ${p ? html`<div class="player">
        <pixel-identicon name=${p.base}></pixel-identicon>
        <span class="t ellipsis">${p.title}</span>
        <pixel-eq ?playing=${p.playing}></pixel-eq>
        <span class="time">${fmtTime(p.time)} / ${fmtTime(p.duration)}</span>
        ${p.multiplexed ? html`<div class="seg">${[["both", "Ambos"], ["left", "Instr."], ["right", "Voz"]].map(([v, l]) =>
          html`<button aria-pressed=${p.channel === v} @click=${() => player.setChannel(v)}>${l}</button>`)}</div>` : ""}
        <button class="btn quiet sm icon" aria-label=${p.playing ? "Pausar" : "Tocar"} @click=${() => player.toggle()}>${icon(p.playing ? "pause" : "play")}</button>
        <button class="btn quiet sm icon" aria-label="Fechar player" @click=${() => player.stop()}>${icon("close")}</button>
      </div>` : html`<span class="muted small">Pressione <kbd>?</kbd> para ver os atalhos</span>`}
  </footer>`;
}

function shell(s) {
  const scr = screens[s.route.name] || screens.home;
  return html`${header(s)}<main><div class="view" data-screen=${s.route.name}>${scr.render(s)}</div></main>${dock(s)}`;
}

subscribe(s => render(shell(s), root));

/* ---------------------------------------------------------------- events --- */
on("job", ev => {
  if (ev.type === "start") set({ job: { id: ev.id, label: ev.label, step: ev.step, frac: ev.frac, kind: ev.kind } });
  else if (ev.type === "progress") { if (state.job) set({ job: { ...state.job, step: ev.step, frac: ev.frac } }); }
  else {
    const label = state.job?.label || ev.label || "";
    set({ job: null, lastJob: ev.type === "done" ? `✓ ${label}` : ev.type === "cancelled" ? `Cancelado: ${label}` : `Falhou: ${label}` });
    if (ev.type === "error") toast(ev.error, { kind: "bad", detail: label });
    if (ev.type === "cancelled") toast("Cancelado.", { kind: "info", detail: label });
  }
});
on("library", () => refresh());

/* ---------------------------------------------------------------- keys --- */
addEventListener("keydown", e => {
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName) || e.target.isContentEditable;
  if (modalOpen()) return;
  if (e.ctrlKey && e.key.toLowerCase() === "o") { e.preventDefault(); chooseLibrary(); return; }
  if (typing) { if (e.key === "Escape") e.target.blur(); return; }
  if (screens[state.route.name]?.key?.(e)) { e.preventDefault(); return; }
  if (e.key === "/") { e.preventDefault(); go("add"); setTimeout(() => document.querySelector("[data-search]")?.focus(), 420); }
  else if (e.key === "?") openHelp();
  else if (/^[1-6]$/.test(e.key)) go(NAV[+e.key - 1].name);
  else if (e.key === " " && player.loaded) { e.preventDefault(); player.toggle(); }
  else if (e.key === "ArrowLeft" && player.loaded) player.seek(player.time() - 5);
  else if (e.key === "ArrowRight" && player.loaded) player.seek(player.time() + 5);
  else if (e.key === "Escape") screens[state.route.name]?.escape?.();
});

/* ---------------------------------------------------------------- boot --- */
(async () => {
  await loadBrand();
  await document.fonts.ready;
  set({ route: parseHash() });
  await refresh();
  render(shell(state), root);
  screens[state.route.name]?.enter?.(state.route.param);
  const boot = document.getElementById("boot");
  boot.classList.add("out");
  setTimeout(() => boot.remove(), 500);
})().catch(e => {
  console.error(e);
  toast("Não consegui iniciar a interface.", { kind: "bad", detail: String(e.message || e) });
});

// dev/test hook (used by scripts/snap_app.py to drive screens)
import * as storeModule from "./store.js";
window.__encolib = { store: storeModule, go, refresh, player };
