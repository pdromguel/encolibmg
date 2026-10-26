// Sync: vocal waveform in pixels (overview + 12 s zoom) with the lyric lines on top, shift/anchors, save.
import { icon } from "../fx/icons.js";
import { html } from "../../vendor/lit-html.js";
import { call, runJob, tryCall } from "../api.js";
import { go, refresh } from "../app.js";
import { clamp, fmtTime, fmtTimePrecise, retime } from "../fx/core.js";
import { colors, reducedMotion } from "../fx/elements.js";
import { player } from "../player.js";
import { setView, state, view } from "../store.js";
import { confirmDialog } from "../ui/dialogs.js";
import { toast } from "../ui/toast.js";
// `t` is a time in this file, so the translator is imported as `tr`
import { fixed, t as tr, tt } from "../i18n.js";
import { noLibrary } from "./common.js";

const REACTION_MS = 150;
const ZOOM = 12;     // seconds visible in the detail lane
const AHEAD = .28;   // playhead position in the detail lane

const v = () => view("sync", { base: null, data: null, offset: 0, anchors: {}, sel: 0, dirty: false, loading: false });
const lines = () => { const s = v(); return s.data ? retime(s.data.lines, s.anchors, s.offset) : []; };

/* ------------------------------------------------------------- waveform --- */
class SyncWave extends HTMLElement {
  connectedCallback() {
    this.canvas ||= Object.assign(document.createElement("canvas"), { style: "display:block;width:100%;height:100%" });
    if (!this.canvas.isConnected) this.appendChild(this.canvas);
    this.ctx = this.canvas.getContext("2d");
    this.ro = new ResizeObserver(() => this.size()); this.ro.observe(this);
    this.addEventListener("pointerdown", this.down);
    this.size(); this.loop();
  }
  disconnectedCallback() { this.ro?.disconnect(); cancelAnimationFrame(this.raf); this.removeEventListener("pointerdown", this.down); }
  size() {
    const r = this.getBoundingClientRect(), dpr = devicePixelRatio || 1;
    this.w = r.width; this.h = r.height;
    this.canvas.width = r.width * dpr; this.canvas.height = r.height * dpr;
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  loop = () => { this.draw(); this.raf = requestAnimationFrame(this.loop); };
  timeAt(x) {
    const d = this.data;
    if (this.getAttribute("mode") === "overview") return clamp(x / this.w, 0, 1) * d.duration;
    return player.time() - ZOOM * AHEAD + (x / this.w) * ZOOM;
  }
  down = e => {
    if (!this.data) return;
    const r = this.getBoundingClientRect();
    const seek = ev => player.seek(clamp(this.timeAt(ev.clientX - r.left), 0, this.data.duration));
    if (this.getAttribute("mode") === "overview") {
      seek(e);
      const move = ev => seek(ev), up = () => { removeEventListener("pointermove", move); removeEventListener("pointerup", up); };
      addEventListener("pointermove", move); addEventListener("pointerup", up);
    } else {
      // drag the zoom lane like a tape
      const x0 = e.clientX, t0 = player.time();
      const move = ev => player.seek(clamp(t0 - (ev.clientX - x0) / this.w * ZOOM, 0, this.data.duration));
      const up = ev => { removeEventListener("pointermove", move); removeEventListener("pointerup", up); if (Math.abs(ev.clientX - x0) < 3) seek(ev); };
      addEventListener("pointermove", move); addEventListener("pointerup", up);
    }
  };
  draw() {
    const d = this.data, ctx = this.ctx; if (!d || !ctx) return;
    const P = colors(), W = this.w, H = this.h, now = player.time();
    ctx.clearRect(0, 0, W, H);
    const overview = this.getAttribute("mode") === "overview";
    const cell = overview ? 3 : 4, cols = Math.floor(W / cell), rowsMax = Math.floor(H / cell / (overview ? 1 : 2)) - (overview ? 0 : 3);
    const t0 = overview ? 0 : now - ZOOM * AHEAD, span = overview ? d.duration : ZOOM;
    const mid = overview ? H : Math.floor(H / 2 / cell) * cell + 6;
    for (let c = 0; c < cols; c++) {
      const a = t0 + (c / cols) * span, b = t0 + ((c + 1) / cols) * span;
      if (b < 0 || a > d.duration) continue;
      let peak = 0;
      for (let k = Math.max(0, Math.floor(a * d.rate)); k <= Math.min(d.peaks.length - 1, Math.floor(b * d.rate)); k++) peak = Math.max(peak, d.peaks[k]);
      const n = Math.max(1, Math.round(Math.pow(peak, .85) * rowsMax));
      ctx.fillStyle = a < now ? P.text : P["field-mid"];
      for (let r = 0; r < n; r++) {
        if (overview) ctx.fillRect(c * cell, H - (r + 1) * cell, cell - 1, cell - 1);
        else { ctx.fillRect(c * cell, mid - (r + 1) * cell, cell - 1, cell - 1); ctx.fillRect(c * cell, mid + r * cell, cell - 1, cell - 1); }
      }
    }
    const L = this.lines || [], x = t => ((t - t0) / span) * W;
    ctx.font = "11px 'JetBrains Mono', monospace"; ctx.textBaseline = "top";
    L.forEach((l, k) => {
      const t = l.ms / 1000, X = x(t);
      if (X < -400 || X > W + 4) return;
      const anchored = this.anchors?.has(l.i), sel = k === this.sel;
      ctx.fillStyle = anchored ? P["field-crest"] : sel ? P.text : P["field-hover"];
      if (overview) { ctx.fillRect(Math.round(X), 0, 1, 6); return; }
      for (let y = 18; y < H - 2; y += 4) ctx.fillRect(Math.round(X), y, sel || anchored ? 2 : 1, 2);
      const label = (anchored ? "⚓ " : "") + l.text;
      const next = L[k + 1] ? x(L[k + 1].ms / 1000) : W;
      const room = Math.max(0, next - X - 10);
      ctx.save(); ctx.beginPath(); ctx.rect(X + 4, 0, room, 16); ctx.clip();
      ctx.fillStyle = sel ? P.text : P["text-2"]; ctx.fillText(label, X + 5, 2);
      ctx.restore();
    });
    if (overview) {  // zoom window
      ctx.strokeStyle = P["border-strong"] || P["field-lit"]; ctx.lineWidth = 1;
      ctx.strokeRect(x(now - ZOOM * AHEAD) + .5, .5, (ZOOM / span) * W, H - 1);
    }
    const px = x(now);
    ctx.fillStyle = P["field-crest"];
    ctx.fillRect(Math.round(px) - 1, 0, 2, H);
    if (!overview) { ctx.fillRect(Math.round(px) - 4, 0, 8, 3); ctx.fillRect(Math.round(px) - 4, H - 3, 8, 3); }
    if (reducedMotion() && !player.audio.paused) {} // canvas still follows the audio; nothing decorative to skip
  }
}
customElements.define("sync-wave", SyncWave);

/* ---------------------------------------------------------------- actions --- */
async function load(base) {
  const s = v();
  if (s.base === base && s.data) return;           // keep unsaved edits when coming back
  setView("sync", { base, data: null, loading: true, offset: 0, anchors: {}, sel: 0, dirty: false });
  try {
    const data = await call("sync_load", base);
    setView("sync", { data, loading: false });
    player.load({ base, title: `${data.artist} - ${data.title}`, url: data.audio, multiplexed: data.multiplexed });
  } catch (e) {
    setView("sync", { loading: false });
    toast(e.message, { kind: "bad" });
  }
}

function edit(patch) { setView("sync", { ...patch, dirty: true }); }

function nudge(ms) { edit({ offset: v().offset + ms }); }

function tapAnchor() {
  const s = v(), L = lines(), row = L[s.sel];
  if (!row) return;
  const tap = Math.round(player.time() * 1000) - REACTION_MS;
  const anchors = { ...s.anchors, [row.i]: tap - s.offset };
  const next = retime(s.data.lines, anchors, s.offset);
  const pos = next.findIndex(r => r.i === row.i);
  edit({ anchors, sel: Math.min(pos + 1, next.length - 1) });
}

function suggest() {
  const s = v();
  if (s.data?.onset == null) return toast(tr("ui.sync.no_onset"), { kind: "warn" });
  const off = Math.round(s.data.onset * 1000) - s.data.lines[0].ms;
  edit({ offset: off, anchors: {} });
  toast(tr("ui.sync.onset", { time: fmtTimePrecise(s.data.onset), offset: fixed(off / 1000) }), {
    kind: "info", detail: tr("ui.sync.onset_detail"),
    actions: [{ label: tr("ui.sync.check"), primary: true, run: () => { player.seek(Math.max(0, s.data.onset - 1.5)); player.play(); } }] });
}

async function save() {
  const s = v();
  const out = lines().map(l => ({ ms: l.ms, text: l.text }));
  const res = await tryCall("sync_save", s.base, out);
  if (!res) return;
  setView("sync", { data: { ...s.data, lines: res.lines, has_backup: true }, offset: 0, anchors: {}, dirty: false });
  refresh();
  if (res.has_guide && await confirmDialog(tr("ui.sync.regen_q"), tr("ui.sync.regen_text"), { ok: tr("ui.lib.rebuild_guide") })) {
    try { await runJob("track_guides", [s.base]); toast(tr("ui.sync.regen_done"), { kind: "ok" }); }
    catch (e) { if (e.kind !== "Cancelled") toast(e.message, { kind: "bad" }); }
  } else toast(tr("ui.sync.saved"), { kind: "ok", detail: tr("ui.sync.saved_detail") });
}

async function undo() {
  const s = v();
  if (!await confirmDialog(tr("ui.sync.undo_q"), tr("ui.sync.undo_text"))) return;
  const res = await tryCall("sync_undo", s.base);
  if (res) { setView("sync", { data: { ...s.data, lines: res.lines, has_backup: res.has_backup }, offset: 0, anchors: {}, dirty: false }); toast(tr("ui.sync.undone"), { kind: "ok" }); }
}

/* ---------------------------------------------------------------- screen --- */
export const sync = {
  parent: "library",
  enter(base) { if (base) load(base); },
  escape() { go("library"); },
  key(e) {
    const s = v(); if (!s.data) return false;
    const L = lines();
    if (e.key === " ") { if (!player.audio.paused && !e.shiftKey) tapAnchor(); else player.toggle(); return true; }
    if (e.key === "ArrowDown") { setView("sync", { sel: Math.min(L.length - 1, s.sel + 1) }); scrollSel(); return true; }
    if (e.key === "ArrowUp") { setView("sync", { sel: Math.max(0, s.sel - 1) }); scrollSel(); return true; }
    if (e.key === "Enter") { player.seek(Math.max(0, L[s.sel].ms / 1000 - 1)); player.play(); return true; }
    if (e.key === "Backspace") { const a = { ...s.anchors }; delete a[L[s.sel]?.i]; edit({ anchors: a }); return true; }
    if (e.key === "[") { nudge(-100); return true; }
    if (e.key === "]") { nudge(100); return true; }
    if (e.ctrlKey && e.key === "s") { save(); return true; }
    return false;
  },
  render(st) {
    if (!st.app?.library) return html`<div class="page">${noLibrary()}</div>`;
    const s = v();
    if (s.loading || !s.data) return html`<div class="page"><div class="empty">${s.loading
      ? html`<pixel-mark singing style="width:56px;height:56px"></pixel-mark><p>${tr("ui.sync.loading")}</p>`
      : html`<p>${tt("ui.sync.pick", { link: html`<a class="link" href="#/library">${tr("ui.nav.library")}</a>` })}</p>`}</div></div>`;
    const L = lines(), d = s.data, t = (st.player?.base === s.base ? st.player.time : 0) * 1000;
    let cur = -1; L.forEach((l, k) => { if (l.ms <= t) cur = k; });
    const anchorSet = new Set(Object.keys(s.anchors).map(Number));
    const nAnch = anchorSet.size;
    return html`<div class="page sync">
      <div class="page-head rise">
        <a class="btn quiet sm" href="#/library">${icon("back")} ${tr("ui.nav.library")}</a>
        <div class="grow"><h2 class="ellipsis">${tr("ui.sync.title")} <span class="muted">·</span> ${d.title}</h2><p class="sub">${d.artist}${d.has_guide ? tr("ui.sync.has_guide") : ""}</p></div>
        <button class="btn ghost" ?disabled=${!d.has_backup} @click=${undo}>${icon("undo")} ${tr("ui.sync.undo")}</button>
        <button class="btn" ?disabled=${!s.dirty} @click=${save}>${tr("ui.common.save")} <span class="k">Ctrl S</span></button>
      </div>
      <div class="waves rise" style="--i:1">
        <sync-wave mode="detail" .data=${d} .lines=${L} .anchors=${anchorSet} .sel=${s.sel}></sync-wave>
        <sync-wave mode="overview" .data=${d} .lines=${L} .anchors=${anchorSet} .sel=${s.sel}></sync-wave>
      </div>
      <div class="sctl rise" style="--i:2">
        <button class="btn icon" @click=${() => player.toggle()} aria-label=${tr("ui.player.play")}>${icon(st.player?.playing ? "pause" : "play")}</button>
        <span class="mono-num time">${fmtTimePrecise(t / 1000)} <span class="muted">/ ${fmtTime(d.duration)}</span></span>
        ${d.multiplexed ? html`<div class="seg">${[["both", "ui.player.both"], ["left", "ui.player.instr"], ["right", "ui.player.voice"]].map(([k, l]) =>
          html`<button aria-pressed=${(st.player?.channel || "both") === k} @click=${() => player.setChannel(k)}>${tr(l)}</button>`)}</div>` : ""}
        <span class="grow"></span>
        <span class="small dim">${tr("ui.sync.shift")}</span>
        <div class="seg">${[[-1000, "−1 s"], [-100, "−" + fixed(.1, 1)], [100, "+" + fixed(.1, 1)], [1000, "+1 s"]].map(([ms, l]) =>
          html`<button @click=${() => nudge(ms)}>${l}</button>`)}</div>
        <span class="mono-num offset ${s.offset ? "" : "muted"}">${s.offset >= 0 ? "+" : ""}${fixed(s.offset / 1000)} s</span>
        ${d.multiplexed ? html`<button class="btn ghost sm" @click=${suggest}>${icon("spark")} ${tr("ui.sync.suggest")}</button>` : ""}
        <button class="btn quiet sm" ?disabled=${!nAnch} @click=${() => edit({ anchors: {} })}>${nAnch ? tr("ui.sync.clear_anchors", { count: nAnch }) : tr("ui.sync.clear_anchors_none")}</button>
      </div>
      <div class="slines rise" style="--i:3">
        ${L.map((l, k) => {
          const next = L[k + 1]?.ms ?? l.ms + 4000, prog = k === cur ? clamp((t - l.ms) / Math.max(1, next - l.ms), 0, 1) : k < cur ? 1 : 0;
          return html`<div class="sline ${k === s.sel ? "sel brackets on" : ""} ${k === cur ? "cur" : ""} ${k < cur ? "past" : ""}" data-k=${k}
              @click=${() => setView("sync", { sel: k })}
              @dblclick=${() => { player.seek(Math.max(0, l.ms / 1000 - 1)); player.play(); }}>
            <span class="an">${anchorSet.has(l.i) ? "⚓" : ""}</span>
            <span class="tm mono-num">${fmtTimePrecise(l.ms / 1000)}</span>
            <span class="tx" style="--p:${prog}">${l.text}</span>
          </div>`;
        })}
      </div>
      <p class="keyhint muted small">
        <kbd>${tr("ui.help.space_key")}</kbd> ${tr("ui.sync.hint_space")}
        · <kbd>↑</kbd><kbd>↓</kbd> ${tr("ui.sync.hint_pick")} · <kbd>Enter</kbd> ${tr("ui.sync.hint_enter")} · <kbd>[</kbd><kbd>]</kbd> ±${fixed(.1, 1)} s
        · <kbd>⌫</kbd> ${tr("ui.sync.hint_anchor")} · ${tr("ui.sync.hint_drag")}</p>
    </div>`;
  },
};

function scrollSel() {
  requestAnimationFrame(() => document.querySelector(`.sline[data-k="${v().sel}"]`)?.scrollIntoView({ block: "nearest" }));
}
