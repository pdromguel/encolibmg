// Visual e som: background videos by category, idle-screen images, boot video, score narrations, SoundFont.
import { icon } from "../fx/icons.js";
import { html } from "../../vendor/lit-html.js";
import { call, runJob, tryCall } from "../api.js";
import { setView, state, view } from "../store.js";
import { confirmDialog, modal, promptDialog } from "../ui/overlay.js";
import { toast } from "../ui/toast.js";
import { pickVideo } from "./add.js";
import { t, tt } from "../i18n.js";
import { fmtSize, noLibrary, pageHead } from "./common.js";

const TABS = ["bgv", "bumpers", "boot", "narr", "sf"];  // label: ui.vis.tab.<key>
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
  const r = await promptDialog(t("ui.vis.new_cat"), [{ name: "name", label: t("ui.vis.cat_name"), placeholder: t("ui.vis.cat_placeholder") }], { ok: t("ui.common.create") });
  if (!r?.name?.trim()) return;
  const data = await tryCall("bgv_category", "add", r.name);
  if (data) { apply(data); setView("visual", { cat: data.categories.at(-1).name }); }
}
async function renameCategory(name) {
  const r = await promptDialog(t("ui.vis.rename_cat"), [{ name: "name", label: t("ui.vis.new_name"), value: name }]);
  if (r?.name?.trim() && r.name !== name) { const d = await tryCall("bgv_category", "rename", name, r.name); if (d) { apply(d); setView("visual", { cat: r.name.trim() }); } }
}
async function removeCategory(name, n) {
  if (await confirmDialog(t("ui.vis.remove_q", { name }), t("ui.vis.videos_to_trash", { count: n }), { ok: t("ui.common.remove"), danger: true }))
    apply(await tryCall("bgv_category", "remove", name));
}
async function fromYoutube(cat) {
  const r = await promptDialog(t("ui.vis.yt_title"), [{ name: "q", label: t("ui.vis.yt_search"), value: t("ui.vis.yt_query", { cat }) }],
    { lead: t("ui.vis.yt_lead"), ok: t("ui.vis.yt_search") });
  if (!r?.q) return;
  const vid = await pickVideo(t("ui.vis.bgv_pick_title", { cat }), t("ui.vis.bgv_pick_lead"), () => call("bgv_search", r.q));
  if (vid) job("bgv_add_video", [cat, vid.id], t("ui.vis.video_added_to", { cat }));
}
async function fromPc(cat) {
  try { const res = await runJob("bgv_add_files", cat); if (res != null) { await load(); toast(t("ui.vis.videos_added", { count: res }), { kind: "ok" }); } }
  catch (e) { if (e.kind !== "Cancelled") toast(e.message, { kind: "bad" }); }
}

function bgvTab(d, s, busy) {
  const cat = d.categories.find(c => c.name === s.cat);
  return html`<div class="bgv">
    <aside class="cats">
      ${d.categories.map(c => html`<button class="catb ${c.name === s.cat ? "on brackets" : ""}" @click=${() => setView("visual", { cat: c.name })}>
        <span class="ellipsis">${c.name}</span><span class="muted">${c.videos.length}</span></button>`)}
      <button class="btn ghost sm" @click=${newCategory}>${t("ui.vis.new_cat_btn")}</button>
    </aside>
    <div class="grow">
      ${!cat ? html`<div class="empty"><h3>${t("ui.vis.no_cats")}</h3><p>${t("ui.vis.no_cats_text")}<br>${tt("ui.vis.no_cats_keys", { keys: html`<kbd>[</kbd> <kbd>]</kbd>` })}</p>
          <button class="btn" @click=${newCategory}>${t("ui.vis.new_cat_btn")}</button></div>` : html`
        <div class="row" style="margin-bottom:12px">
          <h3 class="grow">${cat.name}</h3>
          <button class="btn sm" ?disabled=${busy} @click=${() => fromPc(cat.name)}>${t("ui.vis.from_pc")}</button>
          <button class="btn sm ghost" ?disabled=${busy} @click=${() => fromYoutube(cat.name)}>${t("ui.vis.from_yt")}</button>
          <button class="btn quiet sm" @click=${() => renameCategory(cat.name)}>${t("ui.vis.rename")}</button>
          <button class="btn quiet sm danger" @click=${() => removeCategory(cat.name, cat.videos.length)}>${t("ui.common.remove")}</button>
        </div>
        ${cat.videos.length === 0 ? html`<div class="empty small"><p>${t("ui.vis.no_videos")}</p></div>` : html`
        <div class="mgrid">${cat.videos.map((x, i) => html`<figure class="mcard rise" style="--i:${i}">
          ${x.url ? html`<video muted loop playsinline preload="metadata" .src=${x.url + "#t=1"}
              @mouseenter=${e => e.target.play()} @mouseleave=${e => { e.target.pause(); }}></video>` : html`<div class="miss">${t("ui.vis.missing")}</div>`}
          <figcaption><span class="ellipsis" title=${x.name}>${x.name}</span><span class="muted">${fmtSize(x.size)}</span></figcaption>
          <button class="btn quiet sm icon rm" aria-label=${t("ui.common.remove")} @click=${async () => apply(await tryCall("bgv_remove", cat.name, x.rel))}>${icon("close")}</button>
        </figure>`)}</div>`}`}
    </div>
  </div>`;
}

/* ------------------------------------------------------------- others --- */
function bumpersTab(d) {
  return html`<div>
    <div class="row" style="margin-bottom:12px"><p class="dim grow">${t("ui.vis.bumpers_lead")}</p>
      <button class="btn sm" @click=${async () => apply(await tryCall("bumper_add"))}>${t("ui.vis.add_images")}</button></div>
    ${d.bumpers.length === 0 ? html`<div class="empty small"><p>${t("ui.vis.no_images")}</p></div>` : html`
    <div class="mgrid">${d.bumpers.map((b, i) => html`<figure class="mcard rise" style="--i:${i}">
      <img src=${b.url} alt="" loading="lazy">
      <figcaption><span class="ellipsis">${b.name}</span><span class="muted">${fmtSize(b.size)}</span></figcaption>
      <button class="btn quiet sm icon rm" aria-label=${t("ui.common.remove")} @click=${async () => apply(await tryCall("bumper_remove", b.rel))}>${icon("close")}</button>
    </figure>`)}</div>`}
  </div>`;
}

function bootTab(d, busy) {
  return html`<div class="boottab">
    <p class="dim" style="margin-bottom:12px">${t("ui.vis.boot_lead")}</p>
    ${d.boot ? html`<video class="bootv" controls preload="metadata" .src=${d.boot.url}></video>
      <div class="row" style="margin-top:12px"><span class="dim grow">${d.boot.rel} · ${fmtSize(d.boot.size)}</span>
        <button class="btn ghost sm" ?disabled=${busy} @click=${() => job("boot_set", [], t("ui.vis.boot_changed"))}>${t("ui.vis.change")}</button>
        <button class="btn quiet sm danger" @click=${async () => apply(await tryCall("boot_clear"))}>${t("ui.common.remove")}</button></div>`
    : html`<div class="empty small"><p>${t("ui.vis.no_boot")}</p>
        <button class="btn" ?disabled=${busy} @click=${() => job("boot_set", [], t("ui.vis.boot_set"))}>${t("ui.vis.choose_video")}</button></div>`}
  </div>`;
}

async function addNarration() {
  const r = await promptDialog(t("ui.vis.tab.narr"), [{ name: "lo", label: t("ui.vis.narr_from"), value: "90" }, { name: "hi", label: t("ui.vis.narr_to"), value: "100" }],
    { lead: t("ui.vis.narr_lead"), ok: t("ui.vis.choose_audio") });
  if (!r) return;
  apply(await tryCall("narration_set", parseInt(r.lo, 10), parseInt(r.hi, 10)));
}

function narrTab(d) {
  return html`<div>
    <div class="row" style="margin-bottom:12px"><p class="dim grow">${t("ui.vis.narr_text")}</p>
      <button class="btn sm" @click=${addNarration}>${t("ui.vis.add")}</button></div>
    ${d.narrations.length === 0 ? html`<div class="empty small"><p>${t("ui.vis.no_narr")}</p></div>` : html`
    <div class="nlist">${d.narrations.map(n => html`<div class="nrow">
      <span class="range mono-num">${n.min}–${n.max}</span>
      <div class="bar"><span style="left:${n.min}%;width:${n.max - n.min + 1}%"></span></div>
      <audio controls preload="none" .src=${n.url}></audio>
      <button class="btn quiet sm danger" @click=${async () => apply(await tryCall("narration_remove", n.min, n.max))}>${t("ui.common.remove")}</button>
    </div>`)}</div>`}
  </div>`;
}

function sfTab(d, busy) {
  return html`<div class="sftab">
    <p class="dim">${t("ui.vis.sf_text")}</p>
    <div class="sfcard brackets ${d.soundfont ? "on" : ""}">
      <span class="big">${icon("sound")}</span>
      <div class="grow"><b>${d.soundfont ? d.soundfont.split("/").pop() : t("ui.vis.sf_default")}</b>
        <span class="dim small">${d.soundfont || t("ui.vis.sf_none")}</span></div>
    </div>
    <div class="row">
      <button class="btn" ?disabled=${busy} @click=${() => job("soundfont_download", [], t("ui.vis.sf_installed"))}>${icon("down")} ${t("ui.vis.sf_download")} <span class="k">${t("ui.vis.sf_size")}</span></button>
      <button class="btn ghost" @click=${async () => apply(await tryCall("soundfont_pick"))}>${t("ui.vis.choose_file")}</button>
      ${d.soundfont ? html`<button class="btn quiet danger" @click=${async () => apply(await tryCall("soundfont_remove"))}>${t("ui.common.remove")}</button>` : ""}
    </div>
  </div>`;
}

export const visual = {
  enter() { load(); },
  render(st) {
    if (!st.app?.library) return html`<div class="page">${pageHead(t("ui.nav.visual"), "")}${noLibrary()}</div>`;
    const s = v(), d = s.data, busy = !!st.job;
    return html`<div class="page vis">
      ${pageHead(t("ui.nav.visual"), t("ui.vis.sub"))}
      <div class="seg tabs rise" style="--i:1">${TABS.map(k => html`<button aria-pressed=${s.tab === k}
        @click=${() => setView("visual", { tab: k })}>${t("ui.vis.tab." + k)}</button>`)}</div>
      <div class="tabbody rise" style="--i:2">
        ${!d ? html`<div class="results">${[0, 1, 2].map(i => html`<div class="res skeleton" style="--i:${i}"></div>`)}</div>`
        : { bgv: () => bgvTab(d, s, busy), bumpers: () => bumpersTab(d), boot: () => bootTab(d, busy), narr: () => narrTab(d), sf: () => sfTab(d, busy) }[s.tab]()}
      </div>
    </div>`;
  },
};
