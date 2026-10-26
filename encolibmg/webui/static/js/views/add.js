// Add: search synced lyrics → download complete track (Multiplex + LRC + guide) or a karaoke MTV.
import { icon } from "../fx/icons.js";
import { html } from "../../vendor/lit-html.js";
import { call, runJob, tryCall } from "../api.js";
import { go, refresh } from "../app.js";
import { fmtTime } from "../fx/core.js";
import { confetti } from "../fx/effects.js";
import { setView, state, view } from "../store.js";
import { modal } from "../ui/dialogs.js";
import { toast } from "../ui/toast.js";
import { t } from "../i18n.js";
import { noLibrary, pageHead } from "./common.js";

const STEPS = () => [
  [t("ui.add.step.lyrics"), "LRCLIB"], [t("ui.add.step.audio"), "YouTube"], [t("ui.add.step.voice"), "Demucs"],
  ["Multiplex", t("ui.add.step.multiplex_sub")], [t("ui.add.step.guide"), t("ui.add.step.guide_sub")],
];
// job.key is the engine's progress key (step.*), so this works in any language
const STEP_OF = {
  "step.search_audio": 1, "step.download": 1, "step.separate": 2, "step.mix": 3, "step.save": 3,
  "step.read_audio": 4, "step.analyze_melody": 4, "step.align_lyrics": 4, "step.save_guide": 4,
};
function stepIndex(job) {
  if (!job || job.kind !== "add") return -1;
  return STEP_OF[job.key] ?? 0;
}

const v = () => view("add", { query: "", results: null, loading: false, guide: true });

async function search(q) {
  q = (q ?? v().query).trim();
  if (!q) return;
  setView("add", { query: q, loading: true, autorun: false });
  try {
    const results = await call("search_lyrics", q);
    setView("add", { results, loading: false });
  } catch (e) {
    setView("add", { loading: false });
    toast(e.message, { kind: "bad", detail: t("ui.add.search_failed") });
  }
}

async function download(r, ev) {
  if (state.job) return toast(t("ui.add.wait_job"), { kind: "warn" });
  const origin = ev?.currentTarget?.getBoundingClientRect?.();
  try {
    const track = await runJob("add_song", r.id, v().guide);
    await refresh();
    confetti(origin ? origin.left + origin.width / 2 : innerWidth / 2, origin ? origin.top : innerHeight / 2);
    toast(t("ui.add.done", { title: track.title }), {
      kind: "ok", detail: track.label,
      actions: [
        { label: t("ui.add.see_in_library"), primary: true, run: () => { setView("library", { selected: track.base }); go("library"); } },
        ...(track.has_guide ? [{ label: t("ui.add.guide_preview"), run: () => go("guide", track.base) }] : []),
      ],
    });
  } catch (e) {
    if (e.kind === "Cancelled") return;
    if (e.kind === "NoAudioMatch") {
      toast(e.message, { kind: "warn", detail: t("ui.add.want_mtv"),
        actions: [{ label: t("ui.add.find_mtv"), primary: true, run: () => findMtv(r.artist, r.title) }] });
    } else if (e.kind === "AlreadyExists") toast(e.message, { kind: "info" });
    else toast(e.message, { kind: "bad" });
  }
}

/* ---------------------------------------------------------- video picker --- */
export async function pickVideo(title, lead, loader) {
  let videos = null, sel = null, err = null;
  return modal((close, redraw) => {
    if (videos === null && !err) {
      videos = [];
      loader().then(list => { videos = list; sel = (list.find(x => x.match) || list[0])?.id; redraw(); })
              .catch(e => { err = e.message; redraw(); });
    }
    return html`
      <h2>${title}</h2><p class="lead">${lead}</p>
      ${err ? html`<p class="bad">${err}</p>` : videos.length === 0 ? html`<div class="vgrid">${[0, 1, 2, 3, 4, 5].map(i =>
        html`<div class="vcard skeleton" style="--i:${i}"><div class="thumb"></div><div class="vt"></div></div>`)}</div>` : html`
      <div class="vgrid">
        ${videos.map((x, i) => html`<button class="vcard rise brackets ${sel === x.id ? "on" : ""}" style="--i:${i}"
            @click=${() => { sel = x.id; redraw(); }} @dblclick=${() => close(x)}>
          <div class="thumb"><img src=${x.thumb} alt="" loading="lazy">
            <span class="dur">${fmtTime(x.duration)}</span>${x.match ? html`<span class="match">${t("ui.video.same_duration")}</span>` : ""}</div>
          <div class="vt" title=${x.title}>${x.title}</div><div class="vc">${x.channel}</div>
        </button>`)}
      </div>`}
      <div class="foot">
        ${sel ? html`<button class="btn quiet" @click=${() => tryCall("open_url", videos.find(x => x.id === sel)?.url)}>${icon("play")} ${t("ui.video.watch")}</button>` : ""}
        <span class="grow"></span>
        <button class="btn ghost" @click=${() => close()}>${t("ui.common.cancel")}</button>
        <button class="btn" ?disabled=${!sel} @click=${() => close(videos.find(x => x.id === sel))}>${icon("down")} ${t("ui.video.download_this")}</button>
      </div>`;
  }, { wide: true });
}

async function findMtv(artist, title) {
  if (!artist || !title) {
    const q = v().query;
    if (!q.includes(" - ")) return toast(t("ui.add.need_artist_title"), { kind: "warn" });
    [artist, title] = q.split(" - ").map(x => x.trim());
  }
  const video = await pickVideo(`MTV · ${artist} - ${title}`, t("ui.add.mtv_lead"),
                                () => call("find_mtv", artist, title));
  if (!video) return;
  try {
    const track = await runJob("add_mtv", artist, title, video.id);
    await refresh();
    confetti(innerWidth / 2, innerHeight / 2);
    toast(t("ui.add.done_mtv", { title: track.title }), { kind: "ok" });
  } catch (e) {
    if (e.kind !== "Cancelled") toast(e.message, { kind: e.kind === "AlreadyExists" ? "info" : "bad" });
  }
}

/* ---------------------------------------------------------------- screen --- */
export const add = {
  enter() {
    const s = v();
    requestAnimationFrame(() => document.querySelector("[data-search]")?.focus());
    if (s.autorun) search(s.query);
  },
  render(st) {
    if (!st.app?.library) return html`<div class="page">${pageHead(t("ui.nav.add"), "")}${noLibrary()}</div>`;
    const s = v(), active = stepIndex(st.job);
    return html`<div class="page add">
      ${pageHead(t("ui.nav.add"), t("ui.add.sub"))}
      <form class="searchbar rise" style="--i:1" @submit=${e => { e.preventDefault(); search(); }}>
        <input class="field big" data-search placeholder=${t("ui.add.placeholder")} .value=${s.query} autocomplete="off" spellcheck="false"
               @input=${e => setView("add", { query: e.target.value })}>
        <button class="btn lg" ?disabled=${s.loading}>${t(s.loading ? "ui.add.searching" : "ui.add.search")}</button>
      </form>
      <div class="pipeline rise" style="--i:2">
        ${STEPS().map(([name, sub], i) => html`<div class="pstep ${i < active ? "done" : i === active ? "now" : ""} ${i === 4 && !s.guide ? "off" : ""}">
          <span class="sq">${i < active ? "✓" : i + 1}</span><span class="nm">${name}</span><span class="sb">${sub}</span></div>
          ${i < 4 ? html`<span class="arrow">→</span>` : ""}`)}
        <label class="check" style="margin-left:auto"><input type="checkbox" .checked=${s.guide}
          @change=${e => setView("add", { guide: e.target.checked })}>${t("ui.add.make_guide")}</label>
      </div>
      ${s.loading ? html`<div class="results">${[0, 1, 2, 3, 4].map(i => html`<div class="res skeleton" style="--i:${i}"></div>`)}</div>`
      : s.results === null ? html`
        <div class="hintbox rise" style="--i:3">
          <p><b>${t("ui.add.how_title")}</b> ${t("ui.add.how")}</p>
        </div>`
      : s.results.length === 0 ? html`
        <div class="empty rise"><h3>${t("ui.add.none_title")}</h3><p>${t("ui.add.none_text")}</p>
          <button class="btn ghost" @click=${() => findMtv()}>${icon("film")} ${t("ui.add.find_mtv_long")}</button></div>`
      : html`
        <div class="results">
          ${s.results.map((r, i) => html`<div class="res rise ${r.synced ? "" : "nosync"}" style="--i:${Math.min(i, 12)}"
              @dblclick=${e => r.synced && download(r, e)}>
            <span class="sync ${r.synced ? "ok" : "muted"}" title=${t(r.synced ? "ui.add.synced" : "ui.add.plain")}>${r.synced ? "✓" : "–"}</span>
            <div class="grow"><div class="t ellipsis">${r.title}</div><div class="a ellipsis">${r.artist}${r.album ? html` <span class="muted">· ${r.album}</span>` : ""}</div></div>
            <span class="dur mono-num">${fmtTime(r.duration)}</span>
            <div class="acts">
              ${r.synced ? html`<button class="btn sm" ?disabled=${!!st.job} @click=${e => download(r, e)}>${icon("down")} ${t("ui.add.download_full")}</button>`
                         : html`<button class="btn sm ghost" @click=${() => findMtv(r.artist, r.title)}>${icon("film")} MTV</button>`}
            </div>
          </div>`)}
        </div>
        <p class="muted small rise" style="margin-top:14px">${t("ui.add.not_these")}
          <a class="link" href="javascript:void 0" @click=${() => findMtv()}>${t("ui.add.find_mtv_long")}</a></p>`}
    </div>`;
  },
};
