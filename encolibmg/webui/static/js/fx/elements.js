// Canvas-based pixel elements. Each one sizes itself to its CSS box, honours devicePixelRatio,
// pauses when off-screen or when the window is hidden, and respects prefers-reduced-motion.
import { cells, clamp, easeOut, gridSize, identicon, textGrid } from "./core.js";

export let BRAND = null;
export async function loadBrand() {
  BRAND = await (await fetch("brand/brand.json")).json();
  return BRAND;
}
const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
export const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
let palette = null;
export function colors() {
  if (!palette) {
    palette = {};
    for (const k of ["bg", "bg-deep", "text", "text-2", "muted", "brand", "field-bg", "field-dim", "field-mid",
                     "field-lit", "field-hover", "field-crest", "ok", "warn", "bad", "info"]) palette[k] = css("--" + k);
  }
  return palette;
}

/** Base class: a canvas filling the element, an animation loop that only runs while visible. */
class PixelCanvas extends HTMLElement {
  connectedCallback() {
    if (!this.canvas) {
      this.style.display ||= "block";
      this.canvas = document.createElement("canvas");
      this.canvas.style.cssText = "width:100%;height:100%;display:block;image-rendering:pixelated";
      this.appendChild(this.canvas);
      this.ctx = this.canvas.getContext("2d");
    }
    this._visible = true;
    this._ro = new ResizeObserver(() => { this.resize(); this.draw(performance.now()); });
    this._ro.observe(this);
    this._io = new IntersectionObserver(([e]) => { this._visible = e.isIntersecting; this.kick(); });
    this._io.observe(this);
    this._onVis = () => this.kick();
    document.addEventListener("visibilitychange", this._onVis);
    this.resize();
    this.setup?.();
    this.kick();
  }
  disconnectedCallback() {
    this._ro?.disconnect(); this._io?.disconnect();
    document.removeEventListener("visibilitychange", this._onVis);
    cancelAnimationFrame(this._raf); this._raf = 0;
    this.teardown?.();
  }
  resize() {
    const r = this.getBoundingClientRect(), dpr = devicePixelRatio || 1;
    this.w = Math.max(1, r.width); this.h = Math.max(1, r.height);
    this.canvas.width = Math.round(this.w * dpr); this.canvas.height = Math.round(this.h * dpr);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  get animating() { return true; }
  kick() {
    if (this._raf || !this.isConnected) return;
    const loop = now => {
      this._raf = 0;
      if (!this.isConnected) return;
      this.draw(now);
      if (this._visible && !document.hidden && this.animating && !reducedMotion()) this._raf = requestAnimationFrame(loop);
    };
    this._raf = requestAnimationFrame(loop);
  }
}

/* ------------------------------------------------------------------ field --- */
// Background pixel field: dense at the sides/bottom fading to nothing in the middle, slow crests,
// a diamond trail under the cursor, and a ring when you click.
class PixelField extends PixelCanvas {
  static C = 10;
  setup() {
    this.mouse = null; this.ripples = [];
    this._move = e => {
      const r = this.getBoundingClientRect();
      const x = e.clientX - r.left, y = e.clientY - r.top;
      this.mouse = x >= 0 && y >= 0 && x <= r.width && y <= r.height ? { x: x / PixelField.C | 0, y: y / PixelField.C | 0 } : null;
      this.kick();
    };
    this._down = e => {
      const r = this.getBoundingClientRect();
      const x = e.clientX - r.left, y = e.clientY - r.top;
      if (x >= 0 && y >= 0 && x <= r.width && y <= r.height) this.ripples.push({ x: x / PixelField.C, y: y / PixelField.C, t: performance.now() });
    };
    addEventListener("pointermove", this._move);
    addEventListener("pointerdown", this._down);
    this.build();
  }
  teardown() { removeEventListener("pointermove", this._move); removeEventListener("pointerdown", this._down); }
  resize() { super.resize(); this.build(); }
  build() {
    const C = PixelField.C;
    this.cols = Math.ceil(this.w / C); this.rows = Math.ceil(this.h / C);
    const n = this.cols * this.rows;
    this.heat = new Float32Array(n); this.base = new Float32Array(n);
    const density = parseFloat(this.getAttribute("density") || "1");
    const sides = parseFloat(this.getAttribute("sides") || ".24");
    for (let y = 0; y < this.rows; y++) for (let x = 0; x < this.cols; x++) {
      const edge = Math.min(x, this.cols - 1 - x) / this.cols;
      const side = Math.pow(Math.max(0, 1 - edge / sides), 2);
      const bottom = Math.pow(Math.max(0, (y / this.rows - .55) / .45), 2);
      this.base[y * this.cols + x] = Math.min(1, (Math.max(side * .95, bottom * .85) + side * bottom * .3) * density);
    }
  }
  draw(now) {
    const { ctx, cols, rows, heat, base } = this, C = PixelField.C, P = colors();
    const ramp = [P["field-dim"], P["field-dim"], P["field-mid"], P["field-lit"], P["field-hover"], P["field-crest"]];
    ctx.clearRect(0, 0, this.w, this.h);
    const crest = ((now / 9000) % 1) * (cols + rows) * 1.4 - rows;
    const still = reducedMotion();
    const m = this.mouse;
    for (let y = 0; y < rows; y++) for (let x = 0; x < cols; x++) {
      const i = y * cols + x, b = base[i];
      let v = heat[i] * .93;
      if (!still && b > .01 && Math.random() < b * .035) v = Math.max(v, (.25 + Math.random() * .55) * (.5 + b * .5));
      if (still && b > .35 && ((x * 7 + y * 13) % 11 === 0)) v = Math.max(v, b * .6);
      if (m) { const d = Math.abs(x - m.x) + Math.abs(y - m.y); if (d < 4) v = Math.max(v, (4 - d) / 4 * .95); }
      for (const r of this.ripples) {
        const age = (now - r.t) / 1000, d = Math.abs(Math.hypot(x - r.x, y - r.y) - age * 32);
        if (age < 1.1 && d < .8) v = Math.max(v, 1 - age / 1.1);
      }
      heat[i] = v;
      const level = Math.max(v, Math.max(0, 1 - Math.abs((x + y) - crest) / 2) * .7 * b);
      if (level < .1) continue;
      ctx.fillStyle = ramp[Math.min(5, 1 + (level * 5) | 0)];
      ctx.fillRect(x * C, y * C, C - 1, C - 1);
    }
    this.ripples = this.ripples.filter(r => now - r.t < 1100);
  }
}

/* ------------------------------------------------------------------ mark --- */
// The brand mark ("Letra cantada"). With [singing] the upper lyric line fills like karaoke,
// then the lines move up and the next one starts — used as the app's loading/working indicator.
class PixelMark extends PixelCanvas {
  static get observedAttributes() { return ["singing"]; }
  attributeChangedCallback() { this.t0 = performance.now(); this.kick(); }
  get animating() { return this.hasAttribute("singing"); }
  setup() { this.t0 = performance.now(); this.lines = [12, 10]; }
  draw(now) {
    const grid = BRAND?.mark; if (!grid) return;
    const { ctx } = this, P = colors(), cell = Math.min(this.w, this.h) / 16;
    const gap = cell >= 4 ? Math.max(1, cell * .1) : 0;
    ctx.clearRect(0, 0, this.w, this.h);
    const px = (x, y, color) => { ctx.fillStyle = color; ctx.fillRect(x * cell, y * cell, cell - gap, cell - gap); };
    if (!this.hasAttribute("singing")) {
      for (const c of cells(grid)) px(c.x, c.y, c.c === "#" ? P.text : P["field-mid"]);
      return;
    }
    // brackets stay; lines animate
    for (const c of cells(grid)) if (c.y < 3 || c.y > 12) px(c.x, c.y, P.text);
    const period = 1700, t = (now - this.t0) / period, k = t % 1, cycle = Math.floor(t);
    if (cycle !== this._cycle) { this._cycle = cycle; this.lines = [this.lines[1], 6 + ((cycle * 7) % 7)]; }
    const [a, b] = this.lines;
    const shift = k > .82 ? easeOut((k - .82) / .18) * 4 : 0;
    const fill = clamp(k / .78, 0, 1) * a;
    for (let x = 0; x < a; x++) for (const dy of [0, 1]) {
      const y = 5 + dy - shift;
      if (y >= 3 && y <= 12) px(2 + x, y, x < fill ? P.text : P["field-mid"]);
    }
    for (let x = 0; x < b; x++) for (const dy of [0, 1]) px(2 + x, 9 + dy - shift, P["field-mid"]);
  }
}

/* -------------------------------------------------------------- wordmark --- */
// ENCOLIBMG assembling from scattered pixels; jitters near the cursor; a sweep of light every ~8s.
class PixelWordmark extends PixelCanvas {
  setup() {
    this.grid = BRAND ? textGrid("ENCOLIBMG", BRAND.font, { bold: true, accentFrom: 7 }) : [];
    this.mouse = null;
    this._move = e => { const r = this.getBoundingClientRect(); this.mouse = { x: e.clientX - r.left, y: e.clientY - r.top }; this.kick(); };
    this._leave = () => this.mouse = null;
    this.addEventListener("pointermove", this._move);
    this.addEventListener("pointerleave", this._leave);
    this.replay();
  }
  replay() {
    const { w, h } = gridSize(this.grid);
    this.t0 = performance.now();
    this.px = cells(this.grid).map(c => {
      const a = Math.random() * Math.PI * 2, r = (.5 + Math.random()) * Math.max(w, h) * .9;
      return { ...c, ox: Math.cos(a) * r, oy: Math.sin(a) * r * .5, d: Math.random() * 600 + (c.x / w) * 350 };
    });
    this.kick();
  }
  draw(now) {
    const { ctx } = this, P = colors();
    const { w: gw, h: gh } = gridSize(this.grid);
    const cell = Math.min(this.w / gw, this.h / gh);
    const ox0 = (this.w - gw * cell) / 2, oy0 = (this.h - gh * cell) / 2;
    ctx.clearRect(0, 0, this.w, this.h);
    const sweep = ((now / 8000) % 1) * (gw + 30) - 15;
    const still = reducedMotion();
    for (const p of this.px || []) {
      const k = still ? 1 : clamp((now - this.t0 - p.d) / 900, 0, 1), e = easeOut(k);
      let x = ox0 + (p.x + p.ox * (1 - e)) * cell, y = oy0 + (p.y + p.oy * (1 - e)) * cell;
      if (this.mouse && k === 1) {
        const d = Math.hypot(x - this.mouse.x, y - this.mouse.y);
        if (d < cell * 5) { const s = (1 - d / (cell * 5)) * cell * .4; x += (Math.random() - .5) * s; y += (Math.random() - .5) * s; }
      }
      const lit = Math.abs(p.x - sweep) < 1.5 && k === 1;
      ctx.globalAlpha = .2 + .8 * e;
      ctx.fillStyle = p.c === "#" ? (lit ? P["field-crest"] : P.text) : (lit ? P["field-hover"] : P["field-mid"]);
      ctx.fillRect(x, y, cell - 1, cell - 1);
    }
    ctx.globalAlpha = 1;
  }
}

/* -------------------------------------------------------------- progress --- */
// Karaoke-fill progress: lit cells over dim ones, a glint running across the filled part.
// value: 0..1, or "-1" for indeterminate (a block of pixels marching).
class PixelProgress extends PixelCanvas {
  static get observedAttributes() { return ["value"]; }
  attributeChangedCallback() { this.kick(); }
  get animating() { return this.hasAttribute("value") && this.getAttribute("value") !== ""; }
  draw(now) {
    const { ctx } = this, P = colors();
    const cell = 6, rows = Math.max(1, Math.floor(this.h / cell)), cols = Math.floor(this.w / cell);
    const raw = this.getAttribute("value");
    const v = raw === null || raw === "" ? null : parseFloat(raw);
    ctx.clearRect(0, 0, this.w, this.h);
    const glint = ((now / 1400) % 1) * (cols + 10) - 5;
    for (let x = 0; x < cols; x++) for (let y = 0; y < rows; y++) {
      let color = P["field-dim"];
      if (v != null && v < 0) {
        const pos = ((now / 900) % 2) < 1 ? ((now / 900) % 1) : 2 - ((now / 900) % 2);
        const head = pos * (cols - 8);
        if (x >= head && x < head + 8) color = x > head + 5 ? P["field-crest"] : P.text;
      } else if (v != null) {
        const fill = v * cols;
        if (x < fill) color = Math.abs(x - glint) < 1.5 ? P["field-crest"] : P.text;
        else if (x < fill + 1) color = P["field-lit"];
      }
      ctx.fillStyle = color;
      ctx.fillRect(x * cell, y * cell, cell - 1, cell - 1);
    }
  }
}

/* ------------------------------------------------------------- identicon --- */
class PixelIdenticon extends PixelCanvas {
  static get observedAttributes() { return ["name"]; }
  attributeChangedCallback() { if (this.ctx) this.draw(); }
  get animating() { return false; }
  draw() {
    const { ctx } = this, P = colors(), grid = identicon(this.getAttribute("name") || "");
    const cell = Math.min(this.w, this.h) / 7, off = cell;
    ctx.clearRect(0, 0, this.w, this.h);
    ctx.fillStyle = P["field-bg"]; ctx.fillRect(0, 0, this.w, this.h);
    const gap = cell >= 6 ? 1 : 0;
    for (const c of cells(grid)) {
      ctx.fillStyle = c.c === "#" ? P["field-hover"] : P["field-mid"];
      ctx.fillRect(off + c.x * cell, off + c.y * cell, cell - gap, cell - gap);
    }
  }
}

/* ------------------------------------------------------------ equalizer --- */
class PixelEq extends PixelCanvas {
  static get observedAttributes() { return ["playing"]; }
  attributeChangedCallback() { this.kick(); }
  get animating() { return this.hasAttribute("playing"); }
  draw(now) {
    const { ctx } = this, P = colors(), cols = 4, rows = 5;
    const cw = this.w / cols, ch = this.h / rows;
    ctx.clearRect(0, 0, this.w, this.h);
    const step = Math.floor(now / 90);
    for (let x = 0; x < cols; x++) {
      const level = this.hasAttribute("playing") ? 1 + ((Math.sin(step * (0.7 + x * .37) + x * 2) + 1) * 2) | 0 : 1;
      for (let y = 0; y < rows; y++) {
        ctx.fillStyle = rows - y <= level ? (rows - y === level ? P["field-crest"] : P.text) : P["field-dim"];
        ctx.fillRect(x * cw, y * ch, cw - 1, ch - 1);
      }
    }
  }
}

customElements.define("pixel-field", PixelField);
customElements.define("pixel-mark", PixelMark);
customElements.define("pixel-wordmark", PixelWordmark);
customElements.define("pixel-progress", PixelProgress);
customElements.define("pixel-identicon", PixelIdenticon);
customElements.define("pixel-eq", PixelEq);
