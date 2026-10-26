// EncoLibMG shell: header, routed screens with a pixel dissolve, dock (job progress + mini player), keys.
import { icon } from "./fx/icons.js";
import { html, render } from "../vendor/lit-html.js";
import { call, on, tryCall } from "./api.js";
import { loadBrand } from "./fx/elements.js";
import { fmtTime } from "./fx/core.js";
import { confetti, pixelWipe } from "./fx/effects.js";
import { player } from "./player.js";
import { set, setView, state, subscribe } from "./store.js";
import { closeMenu, menu, modal, modalOpen, promptDialog } from "./ui/dialogs.js";
import { toast } from "./ui/toast.js";
import { screens, NAV } from "./views/index.js";
import { openQueue, queueChip, queuePanel } from "./views/queue.js";
import { setCatalog, t, tt } from "./i18n.js";

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
  if (app?.library) {
    const q = await tryCall("queue_state");  // the queue belongs to the open library
    if (q) set({ queue: q });
  }
}

export async function chooseLibrary() {
  const picked = await tryCall("library_pick");
  if (!picked) return;
  if (picked.has_manifest) {
    const app = await tryCall("library_open", picked.path);
    if (app) { set({ app, view: {} }); await refresh(); toast(t("ui.lib.opened", { title: app.library.title }), { kind: "ok" }); }
    return;
  }
  const res = await promptDialog(t("ui.lib.create_title"), [{ name: "title", label: t("ui.lib.name_label"),
    value: t("name.default_library") }], { lead: t("ui.lib.create_lead", { path: picked.path }), ok: t("ui.common.create") });
  if (!res) return;
  const app = await tryCall("library_create", picked.path, res.title);
  if (app) { set({ app, view: {} }); await refresh(); toast(t("ui.lib.created", { title: app.library.title }), { kind: "ok", detail: app.library.path }); }
}

function libraryMenu(e) {
  const lib = state.app?.library;
  menu(e.currentTarget, [
    ...(lib ? [{ section: lib.path }, { label: t("ui.lib.open_folder"), run: () => tryCall("open_folder") },
               { label: t("ui.lib.settings_menu"), run: openSettings }] : []),
    { section: t("ui.nav.library") },
    { label: t("ui.lib.open_other"), kbd: "Ctrl O", run: chooseLibrary },
  ]);
}

/* ---------------------------------------------------------------- settings --- */
export async function openSettings() {
  const s = await tryCall("settings_get");
  if (!s) return;
  const res = await modal(close => html`
    <h2>${t("ui.settings.title")}</h2>
    <p class="lead">${t("ui.settings.lead")}</p>
    <div class="col" style="gap:14px">
      <div><label class="lbl">${t("ui.settings.name")}</label><input class="field" .value=${s.title} @input=${e => s.title = e.target.value}></div>
      <div><label class="lbl">${t("ui.settings.description")}</label><textarea class="field" rows="3" .value=${s.description}
           @input=${e => s.description = e.target.value}></textarea></div>
      <div class="col" style="gap:8px">
        <span class="lbl" style="margin:0">${t("ui.settings.options")}</span>
        ${s.flags.map(f => html`<label class="check"><input type="checkbox" .checked=${f.value}
          @change=${e => f.value = e.target.checked}>${f.label}</label>`)}
      </div>
    </div>
    <div class="foot"><button class="btn ghost" @click=${() => close()}>${t("ui.common.cancel")}</button>
      <button class="btn" @click=${() => close(s)}>${t("ui.common.save")}</button></div>`);
  if (!res) return;
  const app = await tryCall("settings_save", res);
  if (app) { set({ app }); toast(t("ui.settings.saved"), { kind: "ok", detail: t("ui.settings.saved_detail") }); }
}

/* ---------------------------------------------------------------- language --- */
const LANGS = [["auto", null], ["pt-BR", "Português (Brasil)"], ["en", "English"]];

export async function setLanguage(setting) {
  const res = await tryCall("set_language", setting);
  if (!res) return;
  setCatalog(res.catalog, res.lang);
  set({ lang: { lang: res.lang, setting: res.setting } });
  await refresh();  // labels that come translated from Python (kinds, issues, stats)
  screens[state.route.name]?.relang?.();
  toast(t("ui.lang.changed"), { kind: "ok" });
}

function languageMenu(e) {
  const cur = state.lang?.setting || "auto";
  menu(e.currentTarget, [
    { section: t("ui.lang.title") },
    ...LANGS.map(([v, name]) => ({ label: (cur === v ? "✓ " : " ") + (name || t("ui.lang.auto")), run: () => setLanguage(v) })),
  ]);
}

/* ---------------------------------------------------------------- help --- */
export function openHelp() {
  const k = (...keys) => html`<span class="k">${keys.map(x => html`<kbd>${x}</kbd>`)}</span>`;
  modal(() => html`
    <h2>${t("ui.help.title")}</h2>
    <p class="lead">${t("ui.help.lead")}</p>
    <div class="keys">
      ${k("/")}<span>${t("ui.help.search")}</span>
      ${k("1", "–", "6")}<span>${t("ui.help.screens")}</span>
      ${k(t("ui.help.space_key"))}<span>${t("ui.help.play")}</span>
      ${k("←", "→")}<span>${t("ui.help.seek")}</span>
      ${k("Esc")}<span>${t("ui.help.esc")}</span>
      ${k("Ctrl", "O")}<span>${t("ui.help.open")}</span>
      ${k("?")}<span>${t("ui.help.help")}</span>
    </div>`);
}

/* ---------------------------------------------------------------- shell --- */
const pct = f => (f == null ? "" : Math.round(f * 100) + "%");

function header(s) {
  const lib = s.app?.library;
  return html`
  <header class="hdr">
    <a class="brand" href="#/home" aria-label=${t("ui.nav.home_aria")}>
      <pixel-mark ?singing=${!!s.job}></pixel-mark>
      <span class="name">EncoLib<b>MG</b></span>
    </a>
    <nav class="nav">
      ${NAV.map((n, i) => html`<a href="#/${n.name}" class=${s.route.name === n.name || screens[s.route.name]?.parent === n.name ? "on" : ""}>
        <span class="n">${i + 1}</span>${t(n.label)}</a>`)}
    </nav>
    <div class="right">
      <div class="libchip ${lib ? "" : "none"}" @click=${libraryMenu} title=${lib?.path || ""}>
        <span class="dot"></span><span class="ellipsis">${lib ? lib.title : t("ui.lib.none")}</span><span class="muted">▾</span>
      </div>
      <button class="btn quiet sm langchip" data-tip=${t("ui.lang.title")} aria-label=${t("ui.lang.title")} @click=${languageMenu}>${(s.lang?.lang || "en").slice(0, 2).toUpperCase()}</button>
      <button class="btn quiet icon" data-tip=${t("ui.common.settings")} aria-label=${t("ui.common.settings")} @click=${openSettings} ?disabled=${!lib}>${icon("gear")}</button>
      <button class="btn quiet icon" data-tip=${t("ui.help.title") + "  ?"} aria-label=${t("ui.help.title")} @click=${openHelp}>?</button>
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
        <button class="btn ghost sm" @click=${() => tryCall("job_cancel")}>${t("ui.common.cancel")}</button>
      </div>`
      : html`<div class="job idle"><pixel-progress value=""></pixel-progress>
        <span class="step">${s.lastJob || t("ui.dock.ready")}</span></div>`}
    ${queueChip(s)}
    ${p ? html`<div class="player">
        <pixel-identicon name=${p.base}></pixel-identicon>
        <span class="t ellipsis">${p.title}</span>
        <pixel-eq ?playing=${p.playing}></pixel-eq>
        <span class="time">${fmtTime(p.time)} / ${fmtTime(p.duration)}</span>
        ${p.multiplexed ? html`<div class="seg">${[["both", "ui.player.both"], ["left", "ui.player.instr"], ["right", "ui.player.voice"]].map(([v, l]) =>
          html`<button aria-pressed=${p.channel === v} @click=${() => player.setChannel(v)}>${t(l)}</button>`)}</div>` : ""}
        <button class="btn quiet sm icon" aria-label=${t(p.playing ? "ui.player.pause" : "ui.player.play")} @click=${() => player.toggle()}>${icon(p.playing ? "pause" : "play")}</button>
        <button class="btn quiet sm icon" aria-label=${t("ui.player.close")} @click=${() => player.stop()}>${icon("close")}</button>
      </div>` : html`<span class="muted small">${tt("ui.dock.press", { key: html`<kbd>?</kbd>` })}</span>`}
  </footer>`;
}

function shell(s) {
  const scr = screens[s.route.name] || screens.home;
  return html`${header(s)}<main><div class="view" data-screen=${s.route.name}>${scr.render(s)}</div></main>${queuePanel(s)}${dock(s)}`;
}

subscribe(s => render(shell(s), root));

/* ---------------------------------------------------------------- events --- */
on("job", ev => {
  if (ev.type === "start") set({ job: { id: ev.id, label: ev.label, step: ev.step, key: ev.key, frac: ev.frac, kind: ev.kind } });
  else if (ev.type === "progress") { if (state.job) set({ job: { ...state.job, step: ev.step, key: ev.key, frac: ev.frac } }); }
  else {
    const label = state.job?.label || ev.label || "";
    set({ job: null, lastJob: ev.type === "done" ? `✓ ${label}` : ev.type === "cancelled" ? t("ui.job.cancelled_label", { label }) : t("ui.job.failed_label", { label }) });
    if (ev.type === "error") toast(ev.error, { kind: "bad", detail: label });
    if (ev.kind === "queue") { if (ev.type === "done") queueFinished(ev.result); return; }  // pausing is not news
    if (ev.type === "cancelled") toast(t("ui.job.cancelled"), { kind: "info", detail: label });
  }
});

/** The summary when the queue runs out: what came in, at which level. */
function queueFinished(sum) {
  if (!sum) return;
  const parts = [["full", "ui.queue.sum.full"], ["no_guide", "ui.queue.sum.no_guide"], ["skipped", "ui.queue.sum.skipped"],
                 ["failed", "ui.queue.sum.failed"]].filter(([k]) => sum[k]).map(([k, key]) => t(key, { count: sum[k] }));
  if (!parts.length) return;
  toast(t("ui.queue.finished"), { kind: sum.failed ? "warn" : "ok", detail: parts.join(" · "),
    actions: [{ label: t("ui.queue.show"), run: openQueue }] });
}

// a song picked on the Add screen gets its own "ready" notice, like before the queue existed
on("queue", q => {
  const before = new Map((state.queue?.items || []).map(i => [i.id, i.state]));
  set({ queue: q });
  for (const it of q.items) {
    if (it.state !== "done" || before.get(it.id) === "done" || !before.has(it.id) || it.source !== "search") continue;
    confetti(innerWidth - 160, innerHeight - 60, 40);
    toast(t("ui.add.done", { title: it.title }), { kind: "ok", actions: [
      { label: t("ui.add.see_in_library"), primary: true, run: () => { setView("library", { selected: it.base }); go("library"); } },
      ...(it.level === "full" ? [{ label: t("ui.add.guide_preview"), run: () => go("guide", it.base) }] : []),
    ] });
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
  const lang = await call("i18n");
  setCatalog(lang.catalog, lang.lang);
  set({ lang: { lang: lang.lang, setting: lang.setting } });
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
  toast(t("ui.boot.failed"), { kind: "bad", detail: String(e.message || e) });
});

// dev/test hook (used by scripts/screenshots/ and tests/ui/ to drive screens)
import * as storeModule from "./store.js";
window.__encolib = { store: storeModule, go, refresh, player, setLanguage, t };
