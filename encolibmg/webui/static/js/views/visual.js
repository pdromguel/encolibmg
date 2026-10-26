// Visual e som: background videos by category, idle-screen images, boot video, score narrations, SoundFont.
import { icon } from "../fx/icons.js";
import { html } from "../../vendor/lit-html.js";
import { call, runJob, tryCall } from "../api.js";
import { setView, state, view } from "../store.js";
import { confirmDialog, modal, promptDialog } from "../ui/overlay.js";
import { toast } from "../ui/toast.js";
import { pickVideo } from "./add.js";
import { fmtSize, noLibrary, pageHead, plural } from "./common.js";

const TABS = [["bgv", "Vídeos de fundo"], ["bumpers", "Imagens de espera"], ["boot", "Vídeo de abertura"],
              ["narr", "Narração da nota"], ["sf", "SoundFont"]];
const v = () => view("visual", { tab: "bgv", data: null, cat: null });

async function load() {
  const data = await tryCall("visual_state");
  if (data) setView("visual", { data, cat: v().cat && data.categories.some(c => c.name === v().cat) ? v().cat : data.categories[0]?.name || null });
}
const apply = data => data && setView("visual", { data });

async function job(name, args, done) {
  try { await runJob(name, ...args); await load(); toast(done, { kind: "ok" }); }
  catch (e) { if (e.kind !== "Cancelled") toast(e.message, { kind: "bad" }); }
}

/* ------------------------------------------------------------------ BGV --- */
async function newCategory() {
  const r = await promptDialog("Nova categoria", [{ name: "name", label: "Nome (aparece no Encore)", placeholder: "Praias, Cidade, Anime…" }], { ok: "Criar" });
  if (!r?.name?.trim()) return;
  const data = await tryCall("bgv_category", "add", r.name);
  if (data) { apply(data); setView("visual", { cat: data.categories.at(-1).name }); }
}
async function renameCategory(name) {
  const r = await promptDialog("Renomear categoria", [{ name: "name", label: "Novo nome", value: name }]);
  if (r?.name?.trim() && r.name !== name) { const d = await tryCall("bgv_category", "rename", name, r.name); if (d) { apply(d); setView("visual", { cat: r.name.trim() }); } }
}
async function removeCategory(name, n) {
  if (await confirmDialog(`Remover “${name}”?`, `${plural(n, "vídeo vai", "vídeos vão")} para a Lixeira.`, { ok: "Remover", danger: true }))
    apply(await tryCall("bgv_category", "remove", name));
}
async function fromYoutube(cat) {
  const r = await promptDialog("Vídeo do YouTube", [{ name: "q", label: "Buscar", value: `${cat} 4k sem narração` }],
    { lead: "Vídeos de paisagem costumam ter horas: baixo só um trecho de até 5 minutos (o Encore repete em loop).", ok: "Buscar" });
  if (!r?.q) return;
  const vid = await pickVideo(`Vídeo de fundo · ${cat}`, "Escolha um vídeo. Ele entra sem áudio, em H.264 até 1080p.", () => call("bgv_search", r.q));
  if (vid) job("bgv_add_video", [cat, vid.id], `Vídeo adicionado a “${cat}”.`);
}
async function fromPc(cat) {
  try { const res = await runJob("bgv_add_files", cat); if (res != null) { await load(); toast(`${plural(res, "vídeo adicionado", "vídeos adicionados")}.`, { kind: "ok" }); } }
  catch (e) { if (e.kind !== "Cancelled") toast(e.message, { kind: "bad" }); }
}

function bgvTab(d, s, busy) {
  const cat = d.categories.find(c => c.name === s.cat);
  return html`<div class="bgv">
    <aside class="cats">
      ${d.categories.map(c => html`<button class="catb ${c.name === s.cat ? "on brackets" : ""}" @click=${() => setView("visual", { cat: c.name })}>
        <span class="ellipsis">${c.name}</span><span class="muted">${c.videos.length}</span></button>`)}
      <button class="btn ghost sm" @click=${newCategory}>+ Nova categoria</button>
    </aside>
    <div class="grow">
      ${!cat ? html`<div class="empty"><h3>Sem categorias ainda</h3><p>Crie uma (ex.: Praias) e adicione vídeos do PC ou do YouTube.<br>No Encore, <kbd>[</kbd> <kbd>]</kbd> trocam o vídeo de fundo.</p>
          <button class="btn" @click=${newCategory}>+ Nova categoria</button></div>` : html`
        <div class="row" style="margin-bottom:12px">
          <h3 class="grow">${cat.name}</h3>
          <button class="btn sm" ?disabled=${busy} @click=${() => fromPc(cat.name)}>+ Do PC…</button>
          <button class="btn sm ghost" ?disabled=${busy} @click=${() => fromYoutube(cat.name)}>+ Do YouTube…</button>
          <button class="btn quiet sm" @click=${() => renameCategory(cat.name)}>Renomear</button>
          <button class="btn quiet sm danger" @click=${() => removeCategory(cat.name, cat.videos.length)}>Remover</button>
        </div>
        ${cat.videos.length === 0 ? html`<div class="empty small"><p>Nenhum vídeo nesta categoria.</p></div>` : html`
        <div class="mgrid">${cat.videos.map((x, i) => html`<figure class="mcard rise" style="--i:${i}">
          ${x.url ? html`<video muted loop playsinline preload="metadata" .src=${x.url + "#t=1"}
              @mouseenter=${e => e.target.play()} @mouseleave=${e => { e.target.pause(); }}></video>` : html`<div class="miss">arquivo faltando</div>`}
          <figcaption><span class="ellipsis" title=${x.name}>${x.name}</span><span class="muted">${fmtSize(x.size)}</span></figcaption>
          <button class="btn quiet sm icon rm" aria-label="Remover" @click=${async () => apply(await tryCall("bgv_remove", cat.name, x.rel))}>${icon("close")}</button>
        </figure>`)}</div>`}`}
    </div>
  </div>`;
}

/* ------------------------------------------------------------- others --- */
function bumpersTab(d) {
  return html`<div>
    <div class="row" style="margin-bottom:12px"><p class="dim grow">Aparecem na tela de espera do Encore, entre as músicas: logo do karaokê, avisos, fotos da festa.</p>
      <button class="btn sm" @click=${async () => apply(await tryCall("bumper_add"))}>+ Adicionar imagens…</button></div>
    ${d.bumpers.length === 0 ? html`<div class="empty small"><p>Nenhuma imagem.</p></div>` : html`
    <div class="mgrid">${d.bumpers.map((b, i) => html`<figure class="mcard rise" style="--i:${i}">
      <img src=${b.url} alt="" loading="lazy">
      <figcaption><span class="ellipsis">${b.name}</span><span class="muted">${fmtSize(b.size)}</span></figcaption>
      <button class="btn quiet sm icon rm" aria-label="Remover" @click=${async () => apply(await tryCall("bumper_remove", b.rel))}>${icon("close")}</button>
    </figure>`)}</div>`}
  </div>`;
}

function bootTab(d, busy) {
  return html`<div class="boottab">
    <p class="dim" style="margin-bottom:12px">Toca quando o Encore carrega esta biblioteca, como uma vinheta de abertura. É convertido para H.264 + AAC.</p>
    ${d.boot ? html`<video class="bootv" controls preload="metadata" .src=${d.boot.url}></video>
      <div class="row" style="margin-top:12px"><span class="dim grow">${d.boot.rel} · ${fmtSize(d.boot.size)}</span>
        <button class="btn ghost sm" ?disabled=${busy} @click=${() => job("boot_set", [], "Vídeo de abertura trocado.")}>Trocar…</button>
        <button class="btn quiet sm danger" @click=${async () => apply(await tryCall("boot_clear"))}>Remover</button></div>`
    : html`<div class="empty small"><p>Nenhum vídeo de abertura: o Encore usa o padrão dele.</p>
        <button class="btn" ?disabled=${busy} @click=${() => job("boot_set", [], "Vídeo de abertura definido.")}>Escolher vídeo…</button></div>`}
  </div>`;
}

async function addNarration() {
  const r = await promptDialog("Narração da nota", [{ name: "lo", label: "Nota de", value: "90" }, { name: "hi", label: "até", value: "100" }],
    { lead: "Escolha a faixa de pontuação; em seguida, o arquivo de áudio (mp3, wav, ogg…).", ok: "Escolher áudio…" });
  if (!r) return;
  apply(await tryCall("narration_set", parseInt(r.lo, 10), parseInt(r.hi, 10)));
}

function narrTab(d) {
  return html`<div>
    <div class="row" style="margin-bottom:12px"><p class="dim grow">Áudio tocado junto com a nota final, conforme a pontuação. Sem configuração, o Encore usa as narrações padrão dele.</p>
      <button class="btn sm" @click=${addNarration}>+ Adicionar…</button></div>
    ${d.narrations.length === 0 ? html`<div class="empty small"><p>Nenhuma narração. Ex.: 0–69 “pode melhorar!”, 90–100 aplausos.</p></div>` : html`
    <div class="nlist">${d.narrations.map(n => html`<div class="nrow">
      <span class="range mono-num">${n.min}–${n.max}</span>
      <div class="bar"><span style="left:${n.min}%;width:${n.max - n.min + 1}%"></span></div>
      <audio controls preload="none" .src=${n.url}></audio>
      <button class="btn quiet sm danger" @click=${async () => apply(await tryCall("narration_remove", n.min, n.max))}>Remover</button>
    </div>`)}</div>`}
  </div>`;
}

function sfTab(d, busy) {
  return html`<div class="sftab">
    <p class="dim">Os instrumentos que o Encore usa para tocar karaokês MIDI (.kar/.mid) e a melodia do guia. Um bom SoundFont deixa os MIDIs muito mais bonitos.</p>
    <div class="sfcard brackets ${d.soundfont ? "on" : ""}">
      <span class="big">${icon("sound")}</span>
      <div class="grow"><b>${d.soundfont ? d.soundfont.split("/").pop() : "SoundFont padrão do Encore"}</b>
        <span class="dim small">${d.soundfont || "Nenhum SoundFont próprio nesta biblioteca."}</span></div>
    </div>
    <div class="row">
      <button class="btn" ?disabled=${busy} @click=${() => job("soundfont_download", [], "GeneralUser GS instalado. Reabra a biblioteca no Encore.")}>${icon("down")} Baixar GeneralUser GS <span class="k">32 MB, grátis</span></button>
      <button class="btn ghost" @click=${async () => apply(await tryCall("soundfont_pick"))}>Escolher arquivo…</button>
      ${d.soundfont ? html`<button class="btn quiet danger" @click=${async () => apply(await tryCall("soundfont_remove"))}>Remover</button>` : ""}
    </div>
  </div>`;
}

export const visual = {
  enter() { load(); },
  render(st) {
    if (!st.app?.library) return html`<div class="page">${pageHead("Visual e som", "")}${noLibrary()}</div>`;
    const s = v(), d = s.data, busy = !!st.job;
    return html`<div class="page vis">
      ${pageHead("Visual e som", "Como a sua biblioteca aparece e soa no Encore.")}
      <div class="seg tabs rise" style="--i:1">${TABS.map(([k, label]) => html`<button aria-pressed=${s.tab === k}
        @click=${() => setView("visual", { tab: k })}>${label}</button>`)}</div>
      <div class="tabbody rise" style="--i:2">
        ${!d ? html`<div class="results">${[0, 1, 2].map(i => html`<div class="res skeleton" style="--i:${i}"></div>`)}</div>`
        : { bgv: () => bgvTab(d, s, busy), bumpers: () => bumpersTab(d), boot: () => bootTab(d, busy), narr: () => narrTab(d), sf: () => sfTab(d, busy) }[s.tab]()}
      </div>
    </div>`;
  },
};
