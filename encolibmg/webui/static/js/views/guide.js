// Guide preview: pixel piano roll of the MIDI guide + karaoke lyrics filling word by word (like Encore).
import { icon } from "../fx/icons.js";
import { html } from "../../vendor/lit-html.js";
import { call, runJob } from "../api.js";
import { go, refresh } from "../app.js";
import { clamp, fmtTime } from "../fx/core.js";
import { colors } from "../fx/elements.js";
import { player } from "../player.js";
import { setView, view } from "../store.js";
import { toast } from "../ui/toast.js";
// `t` is a time in this file, so the translator is imported as `tr`
import { t as tr, tt } from "../i18n.js";
import { noLibrary } from "./common.js";

const SPAN = 8, AHEAD = .25, NAMES = "C C# D D# E F F# G G# A A# B".split(" ");
const v = () => view("guide", { base: null, data: null, loading: false });

/** [[t, text], …] → lines of words: [{t, end, text, ruby}] ; '/' starts a line; "漢字[かんじ]" = ruby */
function toLines(lyrics) {
  const out = [];
  lyrics.forEach(([t, raw], k) => {
    const newLine = /^[\/\\]/.test(raw);
    let text = raw.replace(/^[\/\\]/, "");
    let ruby = null;
    const m = text.match(/^(.+?)\[(.+?)\]$/);
    if (m) { text = m[1]; ruby = m[2]; }
    if (newLine || !out.length) out.push([]);
    const next = lyrics[k + 1]?.[0] ?? t + 1.5;
    out.at(-1).push({ t, end: Math.min(next, t + 1.5), text, ruby });  // Encore highlights up to 1.5 s per word
  });
  return out;
}

class Base extends HTMLElement {
  connectedCallback() {
    this.canvas ||= Object.assign(document.createElement("canvas"), { style: "display:block;width:100%;height:100%" });
    if (!this.canvas.isConnected) this.appendChild(this.canvas);
    this.ctx = this.canvas.getContext("2d");
    this.ro = new ResizeObserver(() => { const r = this.getBoundingClientRect(), d = devicePixelRatio || 1;
      this.w = r.width; this.h = r.height; this.canvas.width = r.width * d; this.canvas.height = r.height * d; this.ctx.setTransform(d, 0, 0, d, 0, 0); });
    this.ro.observe(this);
    const loop = () => { if (this.w) this.draw(player.time()); this.raf = requestAnimationFrame(loop); };
    loop();
  }
  disconnectedCallback() { this.ro?.disconnect(); cancelAnimationFrame(this.raf); }
}

class GuideRoll extends Base {
  draw(now) {
    const d = this.data, ctx = this.ctx; if (!d) return;
    const P = colors(), W = this.w, H = this.h;
    ctx.clearRect(0, 0, W, H);
    const pitches = d.notes.map(n => n[2]);
    const lo = Math.min(...pitches) - 2, hi = Math.max(...pitches) + 2, rows = hi - lo + 1;
    const rh = Math.max(4, Math.floor((H - 20) / rows)), cell = rh;
    const t0 = now - SPAN * AHEAD, x = t => ((t - t0) / SPAN) * W, y = p => H - 10 - (p - lo + 1) * rh;
    ctx.font = "10px 'JetBrains Mono', monospace"; ctx.textBaseline = "middle";
    for (let p = lo; p <= hi; p++) {      // octave guides
      if (p % 12 !== 0) continue;
      ctx.fillStyle = P["field-dim"];
      for (let X = 0; X < W; X += 6) ctx.fillRect(X, y(p) + rh, 3, 1);
      ctx.fillStyle = P.muted; ctx.fillText(`C${p / 12 - 1}`, 4, y(p) + rh / 2);
    }
    let active = null;
    for (const [s, e, p] of d.notes) {
      if (e < t0 || s > t0 + SPAN) continue;
      const on = s <= now && now < e; if (on) active = p;
      const sung = e <= now;
      ctx.fillStyle = on ? P["field-crest"] : sung ? P["field-lit"] : P["field-hover"];
      for (let X = x(s); X < x(e) - 1; X += cell) ctx.fillRect(Math.round(X), y(p) + 1, Math.min(cell - 1, x(e) - X - 1), rh - 2);
    }
    const px = Math.round(x(now));
    ctx.fillStyle = P["field-crest"]; ctx.fillRect(px - 1, 0, 2, H);
    if (active != null) {
      ctx.fillStyle = P.text; ctx.font = "500 12px 'JetBrains Mono', monospace";
      ctx.fillText(`${NAMES[active % 12]}${Math.floor(active / 12) - 1}`, px + 8, y(active) - 8);
    }
  }
}

class GuideLyrics extends Base {
  draw(now) {
    const L = this.lines, ctx = this.ctx; if (!L) return;
    const P = colors(), W = this.w, H = this.h;
    ctx.clearRect(0, 0, W, H);
    let cur = 0;
    L.forEach((line, i) => { if (line[0] && line[0].t <= now + .4) cur = i; });
    const drawLine = (line, yBase, size, isCur) => {
      ctx.font = `600 ${size}px 'JetBrains Mono', monospace`; ctx.textBaseline = "alphabetic";
      const widths = line.map(w => ctx.measureText(w.text).width), total = widths.reduce((a, b) => a + b, 0);
      let X = Math.max(16, (W - total) / 2);
      line.forEach((w, k) => {
        const ww = widths[k];
        const prog = isCur ? clamp((now - w.t) / Math.max(.05, w.end - w.t), 0, 1) : 0;
        ctx.fillStyle = isCur ? P["text-2"] : P.muted; ctx.fillText(w.text, X, yBase);
        if (prog > 0) {
          ctx.save(); ctx.beginPath(); ctx.rect(X, yBase - size, ww * prog, size * 1.4); ctx.clip();
          ctx.fillStyle = P["field-crest"]; ctx.fillText(w.text, X, yBase);
          ctx.restore();
        }
        if (w.ruby) {
          ctx.save(); ctx.font = `500 ${Math.round(size * .42)}px 'JetBrains Mono', monospace`;
          const rw = ctx.measureText(w.ruby).width;
          ctx.fillStyle = prog > 0 ? P.text : P.muted; ctx.fillText(w.ruby, X + (ww - rw) / 2, yBase - size * .95);
          ctx.restore();
        }
        X += ww;
      });
    };
    if (L[cur]) drawLine(L[cur], H * .48, 30, true);
    if (L[cur + 1]) drawLine(L[cur + 1], H * .86, 20, false);
  }
}
customElements.define("guide-roll", GuideRoll);
customElements.define("guide-lyrics", GuideLyrics);

async function load(base) {
  if (v().base === base && v().data) return;
  setView("guide", { base, data: null, loading: true });
  try {
    const data = await call("guide_load", base);
    setView("guide", { data: { ...data, lines: toLines(data.lyrics) }, loading: false });
    player.load({ base, title: `${data.artist} - ${data.title}`, url: data.audio, multiplexed: data.multiplexed });
  } catch (e) {
    setView("guide", { loading: false });
    toast(e.message, { kind: "bad" });
  }
}

async function regenerate(base) {
  try {
    await runJob("track_guides", [base]);
    setView("guide", { data: null, base: null });
    await refresh();
    load(base);
    toast(tr("ui.guide.regenerated"), { kind: "ok" });
  } catch (e) { if (e.kind !== "Cancelled") toast(e.message, { kind: "bad" }); }
}

export const guide = {
  parent: "library",
  enter(base) { if (base) load(base); },
  escape() { go("library"); },
  key(e) {
    if (e.key === " ") { player.toggle(); return true; }
    if (e.key === "ArrowLeft") { player.seek(player.time() - 5); return true; }
    if (e.key === "ArrowRight") { player.seek(player.time() + 5); return true; }
    return false;
  },
  render(st) {
    if (!st.app?.library) return html`<div class="page">${noLibrary()}</div>`;
    const s = v(), d = s.data;
    if (!d) return html`<div class="page"><div class="empty">${s.loading
      ? html`<pixel-mark singing style="width:56px;height:56px"></pixel-mark><p>${tr("ui.guide.loading")}</p>`
      : html`<p>${tt("ui.guide.pick", { link: html`<a class="link" href="#/library">${tr("ui.nav.library")}</a>` })}</p>`}</div></div>`;
    const t = st.player?.base === s.base ? st.player.time : 0;
    return html`<div class="page guidep">
      <div class="page-head rise">
        <a class="btn quiet sm" href="#/library">${icon("back")} ${tr("ui.nav.library")}</a>
        <div class="grow"><h2 class="ellipsis">${tr("ui.add.guide_preview")} <span class="muted">·</span> ${d.title}</h2>
          <p class="sub">${d.artist} · ${tr("ui.guide.counts", { notes: d.notes.length, words: d.lyrics.length })}</p></div>
        <button class="btn ghost" ?disabled=${!!st.job} @click=${() => regenerate(s.base)}>${icon("guide")} ${tr("ui.lib.rebuild_guide")}</button>
        <a class="btn ghost" href=${"#/sync/" + encodeURIComponent(s.base)}>${icon("clock")} ${tr("ui.lib.sync")}</a>
      </div>
      <div class="stage rise" style="--i:1">
        <guide-roll .data=${d}></guide-roll>
        <guide-lyrics .lines=${d.lines}></guide-lyrics>
      </div>
      <div class="sctl rise" style="--i:2">
        <button class="btn icon" @click=${() => player.toggle()} aria-label=${tr("ui.player.play")}>${icon(st.player?.playing ? "pause" : "play")}</button>
        <span class="mono-num time">${fmtTime(t)} <span class="muted">/ ${fmtTime(d.duration)}</span></span>
        <input type="range" class="scrub" min="0" max=${d.duration || 1} step="0.1" .value=${String(t)}
               @input=${e => player.seek(+e.target.value)}>
        ${d.multiplexed ? html`<div class="seg">${[["both", "ui.player.both"], ["left", "ui.player.instr"], ["right", "ui.player.voice"]].map(([k, l]) =>
          html`<button aria-pressed=${(st.player?.channel || "both") === k} @click=${() => player.setChannel(k)}>${tr(l)}</button>`)}</div>` : ""}
      </div>
      <p class="muted small">${tt("ui.guide.help", { voice: html`<b>${tr("ui.player.voice")}</b>`, key: html`<kbd>M</kbd>` })}</p>
    </div>`;
  },
};
