// Download queue: the button in the footer, the panel above it and the "Add a list" dialog.
import { icon } from "../fx/icons.js";
import { html } from "../../vendor/lit-html.js";
import { tryCall } from "../api.js";
import { t } from "../i18n.js";
import { set, state } from "../store.js";
import { modal } from "../ui/dialogs.js";
import { toast } from "../ui/toast.js";
import { findMtv } from "./add.js";

const ACTIVE = new Set(["finding", "downloading", "processing"]);
const PENDING = new Set(["waiting", "downloaded", ...ACTIVE]);
const GLYPH = { waiting: "·", finding: "…", downloading: "↓", downloaded: "↓", processing: "◐", done: "✓",
                skipped: "=", failed: "✕" };

export function queueCounts(q) {
  const items = q?.items || [];
  return {
    total: items.length,
    done: items.filter(i => i.state === "done" || i.state === "skipped").length,
    pending: items.filter(i => PENDING.has(i.state)).length,
    failed: items.filter(i => i.state === "failed").length,
  };
}

export const openQueue = () => set({ queueOpen: true });
const toggleQueue = () => set({ queueOpen: !state.queueOpen });

async function act(method, ...args) {
  const res = await tryCall(method, ...args);
  if (res) set({ queue: res });
  return res;
}

/** Calls one of the queue_add_* methods and says what happened. Resolves to the API answer (or null). */
export async function addToQueue(method, ...args) {
  const res = await act(method, ...args);
  if (!res) return null;
  if (res.found === 0) toast(t("ui.queue.found_none"), { kind: "warn" });
  else if (res.added === 0) toast(t("ui.queue.already"), { kind: "info" });
  else toast(t("ui.queue.added", { count: res.added }), { kind: "ok", actions: [{ label: t("ui.queue.show"), run: openQueue }] });
  return res;
}

function status(it) {
  if (it.state === "failed") return t("ui.queue.reason." + it.reason, { error: it.error });
  if (it.state === "done") return t(it.level === "no_guide" ? "ui.queue.state.done_no_guide" : "ui.queue.state.done");
  if (ACTIVE.has(it.state) && it.step && it.step !== "step.find_lyrics")
    return t(it.step) + (it.frac != null ? ` ${Math.round(it.frac * 100)}%` : "");
  return t("ui.queue.state." + it.state);
}

export function queueChip(s) {
  const q = s.queue;
  if (!q?.items?.length) return "";
  const c = queueCounts(q);
  return html`<button class="qchip ${q.running ? "on" : ""} ${s.queueOpen ? "open" : ""}" aria-expanded=${!!s.queueOpen}
      @click=${toggleQueue}>${icon("down")} ${t("ui.queue.chip", { done: c.done, total: c.total })}${c.failed
      ? html` <span class="bad">✕ ${c.failed}</span>` : ""}</button>`;
}

export function queuePanel(s) {
  if (!s.queueOpen) return "";
  const q = s.queue || { items: [] }, c = queueCounts(q);
  const note = q.paused && c.pending ? t("ui.queue.paused")
    : !q.running && c.pending && s.job ? t("ui.queue.waiting_job")
    : q.items.length === 0 ? t("ui.queue.empty") : "";
  return html`<section class="qpanel" role="dialog" aria-label=${t("ui.queue.title")}>
    <header class="qhead">
      <h3 class="grow">${t("ui.queue.title")}</h3>
      ${c.pending ? (q.paused
        ? html`<button class="btn sm" @click=${() => act("queue_resume")}>${icon("play")} ${t("ui.queue.resume")}</button>`
        : html`<button class="btn sm ghost" @click=${() => act("queue_pause")}>${icon("pause")} ${t("ui.queue.pause")}</button>`) : ""}
      ${c.done ? html`<button class="btn quiet sm" @click=${() => act("queue_clear")}>${t("ui.queue.clear")}</button>` : ""}
      <button class="btn quiet sm" @click=${addListDialog}>${t("ui.queue.add_list")}</button>
      <button class="btn quiet sm icon" aria-label=${t("ui.common.close")} @click=${() => set({ queueOpen: false })}>${icon("close")}</button>
    </header>
    ${note ? html`<p class="qnote">${note}</p>` : ""}
    <ol class="qlist">${q.items.map(it => html`<li class="qrow s-${it.state}">
      <span class="g" aria-hidden="true">${GLYPH[it.state] || "·"}</span>
      <div class="grow">
        <div class="t ellipsis" title=${it.base}>${it.base}</div>
        <div class="st ellipsis" title=${status(it)}>${status(it)}</div>
        ${ACTIVE.has(it.state) && it.state !== "finding"
          ? html`<pixel-progress value=${it.frac == null ? -1 : it.frac}></pixel-progress>` : ""}
      </div>
      <div class="qacts">
        ${it.state === "failed" && (it.reason === "no_lyrics" || it.reason === "no_audio")
          ? html`<button class="btn quiet sm" @click=${() => findMtv(it.artist, it.title)}>${icon("film")} MTV</button>` : ""}
        ${it.state === "failed" ? html`<button class="btn quiet sm" @click=${() => act("queue_retry", it.id)}>${t("ui.queue.retry")}</button>` : ""}
        ${ACTIVE.has(it.state) ? "" : html`<button class="btn quiet sm icon" aria-label=${t("ui.common.remove")}
          @click=${() => act("queue_remove", it.id)}>${icon("close")}</button>`}
      </div>
    </li>`)}</ol>
  </section>`;
}

/* ------------------------------------------------------------------ add a list --- */
const TABS = [["text", "ui.list.tab.text"], ["playlist", "ui.list.tab.playlist"], ["csv", "ui.list.tab.csv"]];

export function addListDialog() {
  let tab = "text", text = "", url = "", busy = false;
  const guide = () => state.view.add?.guide ?? true;
  return modal((close, redraw) => {
    const send = async (method, ...args) => {
      busy = true; redraw();
      const res = await addToQueue(method, ...args, guide());
      busy = false;
      if (res?.added) { close(); openQueue(); } else redraw();
    };
    const foot = (label, run, disabled = false) => html`<div class="foot">
      <button class="btn ghost" @click=${() => close()}>${t("ui.common.cancel")}</button>
      <button class="btn" ?disabled=${busy || disabled} @click=${run}>${busy ? t("ui.list.reading") : label}</button></div>`;
    return html`
      <h2>${t("ui.list.title")}</h2>
      <div class="seg tabs" style="margin:4px 0 14px">${TABS.map(([k, l]) => html`<button aria-pressed=${tab === k}
        @click=${() => { tab = k; redraw(); }}>${t(l)}</button>`)}</div>
      ${tab === "text" ? html`<p class="lead">${t("ui.list.text_lead")}</p>
          <textarea class="field" rows="9" data-list placeholder=${t("ui.list.text_placeholder")} .value=${text}
            @input=${e => { text = e.target.value; redraw(); }}></textarea>
          ${foot(t("ui.list.add"), () => send("queue_add_text", text), !text.trim())}`
      : tab === "playlist" ? html`<p class="lead">${t("ui.list.playlist_lead")}</p>
          <input class="field" data-playlist placeholder="https://www.youtube.com/playlist?list=…" .value=${url}
            @input=${e => { url = e.target.value; redraw(); }}>
          ${foot(t("ui.list.add"), () => send("queue_add_playlist", url), !url.trim())}`
      : html`<p class="lead">${t("ui.list.csv_lead")}</p>
          ${foot(t("ui.list.choose_csv"), () => send("queue_add_csv"))}`}`;
  });
}
