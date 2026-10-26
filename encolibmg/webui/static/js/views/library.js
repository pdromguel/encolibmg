// Biblioteca: virtualized track list with filters, multi-select bulk actions and a side panel per track.
import { icon } from "../fx/icons.js";
import { html } from "../../vendor/lit-html.js";
import { call, runJob, tryCall } from "../api.js";
import { go, refresh } from "../app.js";
import { player } from "../player.js";
import { schedule, setView, state, view } from "../store.js";
import { confirmDialog, promptDialog } from "../ui/overlay.js";
import { toast } from "../ui/toast.js";
import { pickVideo } from "./add.js";
import { badges, fmtSize, noLibrary, pageHead, plural } from "./common.js";

const ROW = 56;
const FILTERS = [
  ["all", "Todas", () => true],
  ["mp", "Multiplex", t => t.multiplexed],
  ["guide", "Com guia", t => t.has_guide],
  ["noguide", "Sem guia", t => t.kind === "multiplex_lrc" && !t.has_guide],
  ["mtv", "MTV", t => t.kind === "mtv"],
  ["midi", "MIDI", t => t.kind === "midi"],
  ["issues", "Invisíveis", t => t.kind === "orphan"],
];
const SORTS = [["artist", "Artista"], ["title", "Título"], ["recent", "Recentes"]];

const v = () => view("library", { q: "", filter: "all", sort: "artist", selected: null, checked: [], scroll: 0, vh: 700 });

function visibleTracks(tracks) {
  const s = v(), q = s.q.trim().toLowerCase(), pred = FILTERS.find(f => f[0] === s.filter)?.[2] || (() => true);
  const out = (tracks || []).filter(t => pred(t) && (!q || t.base.toLowerCase().includes(q)));
  const cmp = {
    artist: (a, b) => a.artist.localeCompare(b.artist, "pt") || a.title.localeCompare(b.title, "pt"),
    title: (a, b) => a.title.localeCompare(b.title, "pt"),
    recent: (a, b) => b.mtime - a.mtime,
  }[s.sort];
  return out.sort(cmp);
}

const track = base => (state.tracks || []).find(t => t.base === base);

/* --------------------------------------------------------------- actions --- */
async function play(t) {
  const url = await tryCall("media", t.base, "audio");
  if (!url) return;
  player.load({ base: t.base, title: `${t.artist} - ${t.title}`, url, multiplexed: t.multiplexed });
  player.play().catch(() => toast("Não consegui tocar este arquivo.", { kind: "bad" }));
}

async function makeGuides(bases) {
  if (state.job) return toast("Espere o trabalho atual terminar.", { kind: "warn" });
  try {
    const res = await runJob("track_guides", bases);
    await refresh();
    const ok = res.filter(r => r.stats), bad = res.filter(r => r.error);
    if (ok.length === 1 && !bad.length) {
      const st = ok[0].stats;
      toast(`Guia pronto: ${st.notes} notas, ${st.aligned} linhas alinhadas${st.fallback ? `, ${st.fallback} estimadas` : ""}.`, {
        kind: "ok", detail: ok[0].base, actions: [{ label: "Prévia do guia", primary: true, run: () => go("guide", ok[0].base) }] });
    } else toast(`${plural(ok.length, "guia gerado", "guias gerados")}${bad.length ? `, ${bad.length} com erro` : ""}.`,
                 { kind: bad.length ? "warn" : "ok", detail: bad.map(b => `${b.base}: ${b.error}`).join("\n") });
  } catch (e) { if (e.kind !== "Cancelled") toast(e.message, { kind: "bad" }); }
}

async function rename(t) {
  const res = await promptDialog("Editar faixa", [
    { name: "artist", label: "Artista", value: t.artist }, { name: "title", label: "Título", value: t.title }],
    { lead: "Renomeia todos os arquivos da faixa. O Encore dá um código novo para ela (o antigo deixa de valer)." });
  if (!res) return;
  const nt = await tryCall("track_rename", t.base, res.artist, res.title);
  if (nt) { setView("library", { selected: nt.base }); await refresh(); toast("Faixa renomeada.", { kind: "ok", detail: nt.base }); }
}

async function remove(bases) {
  const ok = await confirmDialog(`Remover ${plural(bases.length, "faixa", "faixas")}?`,
    `${bases.slice(0, 6).join(" · ")}${bases.length > 6 ? " …" : ""}. Os arquivos vão para a Lixeira do Windows.`,
    { ok: "Mandar para a Lixeira", danger: true });
  if (!ok) return;
  if (bases.includes(state.player?.base)) player.stop();
  const n = await tryCall("track_remove", bases);
  if (n != null) {
    setView("library", { selected: null, checked: [] });
    await refresh();
    toast(`${plural(n, "faixa foi", "faixas foram")} para a Lixeira.`, { kind: "ok" });
  }
}

async function addClip(t) {
  const video = await pickVideo(`Clipe · ${t.base}`, "Vídeo de fundo para a faixa Multiplex. O Encore toca mudo; ✓ = mesma duração do áudio (mais chance de ficar no tempo).",
                                async () => (await call("find_clip", t.base)).videos);
  if (!video) return;
  try { await runJob("add_clip", t.base, video.id); await refresh(); toast("Clipe adicionado.", { kind: "ok", detail: t.base }); }
  catch (e) { if (e.kind !== "Cancelled") toast(e.message, { kind: "bad" }); }
}

async function convert(t) {
  try { await runJob("track_convert", t.base); await refresh(); toast("Agora é Multiplex (com guia).", { kind: "ok", detail: t.base }); }
  catch (e) { if (e.kind !== "Cancelled") toast(e.message, { kind: "bad" }); }
}

/* ---------------------------------------------------------------- pieces --- */
function onScroll(e) {
  const el = e.currentTarget;
  setView("library", { scroll: el.scrollTop, vh: el.clientHeight });
}

function row(t, i, s) {
  const checked = s.checked.includes(t.base), sel = s.selected === t.base, playing = state.player?.base === t.base && state.player?.playing;
  return html`<div class="trow ${sel ? "sel brackets on" : ""} ${checked ? "checked" : ""}" style="top:${i * ROW}px"
      @click=${() => setView("library", { selected: sel ? null : t.base })}>
    <label class="check" @click=${e => e.stopPropagation()}><input type="checkbox" .checked=${checked}
      @change=${e => setView("library", { checked: e.target.checked ? [...s.checked, t.base] : s.checked.filter(b => b !== t.base) })}></label>
    <pixel-identicon name=${t.base}></pixel-identicon>
    <div class="grow tt"><div class="t ellipsis">${t.title}</div><div class="a ellipsis">${t.artist}</div></div>
    ${badges(t.badges)}
    <div class="racts" @click=${e => e.stopPropagation()}>
      <button class="btn quiet sm icon" data-tip=${playing ? "Pausar" : "Ouvir"} @click=${() => playing ? player.pause() : play(t)}>${icon(playing ? "pause" : "play")}</button>
      ${t.has_lrc ? html`<button class="btn quiet sm icon" data-tip="Sincronia" @click=${() => go("sync", t.base)}>${icon("clock")}</button>` : ""}
      ${t.has_guide ? html`<button class="btn quiet sm icon" data-tip="Prévia do guia" @click=${() => go("guide", t.base)}>${icon("note")}</button>` : ""}
    </div>
  </div>`;
}

const clipUrls = new Map();  // base → media URL of its video (fetched once)
function clipPreview(t) {
  if (!clipUrls.has(t.base)) {
    clipUrls.set(t.base, null);
    call("media", t.base, "video").then(u => { clipUrls.set(t.base, u); schedule(); }).catch(() => {});
  }
  const url = clipUrls.get(t.base);
  return url ? html`<video class="dclip" muted loop autoplay playsinline preload="metadata" .src=${url}></video>`
             : html`<div class="dclip"></div>`;
}

function drawer(t) {
  if (!t) return html`<aside class="drawer"></aside>`;
  const p = state.player, isThis = p?.base === t.base;
  const act = (label, fn, opts = {}) => html`<button class="btn ghost ${opts.danger ? "danger" : ""}" ?disabled=${opts.disabled}
    @click=${fn}>${label}</button>`;
  return html`<aside class="drawer open">
    <div class="dhead">
      <pixel-identicon name=${t.base}></pixel-identicon>
      <div class="grow"><h3 class="selectable">${t.title}</h3><div class="dim selectable">${t.artist}</div>
        <div style="margin-top:8px">${badges(t.badges)}</div></div>
      <button class="btn quiet sm icon" aria-label="Fechar painel" @click=${() => setView("library", { selected: null })}>${icon("close")}</button>
    </div>
    ${t.has_video ? clipPreview(t) : ""}
    <div class="dplay">
      <button class="btn" @click=${() => isThis && p.playing ? player.pause() : play(t)}>${icon(isThis && p.playing ? "pause" : "play")} ${isThis && p.playing ? "Pausar" : "Ouvir"}</button>
      <span class="muted small">${t.multiplexed ? "No rodapé: Ambos · Instr. · Voz" : t.label}</span>
    </div>
    <div class="dgrid">
      ${act(html`${icon("clock")} Sincronia`, () => go("sync", t.base), { disabled: !t.has_lrc })}
      ${act(html`${icon("note")} Prévia do guia`, () => go("guide", t.base), { disabled: !t.has_guide })}
      ${act(html`${icon("guide")} ${t.has_guide ? "Regerar guia" : "Gerar guia"}`, () => makeGuides([t.base]), { disabled: t.kind !== "multiplex_lrc" || !!state.job })}
      ${act(html`${icon("edit")} Editar`, () => rename(t))}
      ${act(html`${icon("film")} Adicionar clipe`, () => addClip(t), { disabled: !t.multiplexed || t.has_video || !!state.job })}
      ${act(html`${icon("levels")} Converter p/ Multiplex`, () => convert(t), { disabled: t.kind !== "audio_lrc" || !!state.job })}
    </div>
    <h4 class="dsec">Arquivos</h4>
    <ul class="files">${t.files.map(f => html`<li><span class="ellipsis selectable">${f.name}</span><span class="muted">${fmtSize(f.size)}</span></li>`)}</ul>
    <div class="row" style="margin-top:16px">
      <button class="btn quiet sm" @click=${() => tryCall("open_folder")}>Abrir pasta</button><span class="grow"></span>
      <button class="btn ghost sm danger" @click=${() => remove([t.base])}>Remover</button>
    </div>
  </aside>`;
}

/* ---------------------------------------------------------------- screen --- */
export const library = {
  enter() { setView("library", { scroll: 0 }); requestAnimationFrame(() => {
    const el = document.querySelector(".tlist"); if (el) setView("library", { vh: el.clientHeight }); }); },
  escape() {
    const s = v();
    if (s.selected) setView("library", { selected: null });
    else if (s.checked.length) setView("library", { checked: [] });
  },
  key(e) {
    if (e.key === "f" && !e.ctrlKey) { document.querySelector("[data-filter]")?.focus(); return true; }
    return false;
  },
  render(st) {
    if (!st.app?.library) return html`<div class="page">${pageHead("Biblioteca", "")}${noLibrary()}</div>`;
    const s = v(), list = visibleTracks(st.tracks);
    const first = Math.max(0, Math.floor(s.scroll / ROW) - 6), last = Math.min(list.length, Math.ceil((s.scroll + s.vh) / ROW) + 6);
    const sel = s.selected ? track(s.selected) : null;
    return html`<div class="page lib">
      ${pageHead("Biblioteca", `${plural(st.tracks?.length || 0, "faixa", "faixas")} em ${st.app.library.title}`,
        html`<button class="btn ghost" @click=${() => tryCall("open_folder")}>${icon("folder")} Abrir pasta</button>`)}
      <div class="ltools rise" style="--i:1">
        <input class="field" data-filter placeholder="Filtrar…  (F)" .value=${s.q} @input=${e => setView("library", { q: e.target.value, scroll: 0 })}>
        <div class="seg">${FILTERS.map(([k, label]) => html`<button aria-pressed=${s.filter === k}
          @click=${() => setView("library", { filter: k, scroll: 0 })}>${label}</button>`)}</div>
        <div class="seg">${SORTS.map(([k, label]) => html`<button aria-pressed=${s.sort === k}
          @click=${() => setView("library", { sort: k })}>${label}</button>`)}</div>
      </div>
      ${s.checked.length ? html`<div class="bulk rise">
        <span><b>${s.checked.length}</b> selecionada${s.checked.length > 1 ? "s" : ""}</span>
        <button class="btn sm" ?disabled=${!!st.job || !s.checked.some(b => track(b)?.kind === "multiplex_lrc")}
          @click=${() => makeGuides(s.checked.filter(b => track(b)?.kind === "multiplex_lrc"))}>${icon("guide")} Gerar guia</button>
        <button class="btn ghost sm danger" @click=${() => remove(s.checked)}>Remover</button>
        <span class="grow"></span>
        <button class="btn quiet sm" @click=${() => setView("library", { checked: list.map(t => t.base) })}>Selecionar ${list.length}</button>
        <button class="btn quiet sm" @click=${() => setView("library", { checked: [] })}>Limpar</button>
      </div>` : ""}
      <div class="lbody ${sel ? "with-drawer" : ""}">
        <div class="tlist" @scroll=${onScroll}>
          ${list.length === 0 ? html`<div class="empty"><h3>Nada por aqui</h3><p>${st.tracks?.length ? "Nenhuma faixa com esse filtro." : "Sua biblioteca está vazia: adicione ou importe músicas."}</p>
            ${st.tracks?.length ? "" : html`<div class="row"><a class="btn" href="#/add">Adicionar</a><a class="btn ghost" href="#/import">Importar</a></div>`}</div>`
          : html`<div class="tspace" style="height:${list.length * ROW}px">${list.slice(first, last).map((t, k) => row(t, first + k, s))}</div>`}
        </div>
        ${drawer(sel)}
      </div>
    </div>`;
  },
};
addEventListener("resize", () => { const el = document.querySelector(".tlist"); if (el) { setView("library", { vh: el.clientHeight }); schedule(); } });
