// Full-screen overlay effects: pixel dissolve between screens, pixel confetti, typed placeholder.
import { shuffledOrder } from "./core.js";
import { colors, reducedMotion } from "./elements.js";
import { t } from "../i18n.js";

let seed = 1;

/** Covers the content area with blocks in random order, runs `swap`, then reveals in another order. */
export function pixelWipe(swap) {
  if (reducedMotion()) { swap(); return Promise.resolve(); }
  const canvas = document.createElement("canvas");
  canvas.className = "wipe";
  document.body.appendChild(canvas);
  const r = canvas.getBoundingClientRect(), dpr = devicePixelRatio || 1;
  canvas.width = r.width * dpr; canvas.height = r.height * dpr;
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const C = 22, cols = Math.ceil(r.width / C), rows = Math.ceil(r.height / C), n = cols * rows;
  const P = colors(), order = shuffledOrder(n, seed++), back = shuffledOrder(n, seed++);
  const cover = 150, reveal = 190;
  return new Promise(resolve => {
    const t0 = performance.now();
    let swapped = false;
    const frame = now => {
      const t = now - t0;
      ctx.clearRect(0, 0, r.width, r.height);
      if (t < cover) {
        const k = Math.floor((t / cover) * n);
        for (let i = 0; i < k; i++) {
          const idx = order[i], x = idx % cols, y = (idx / cols) | 0;
          ctx.fillStyle = i > k - n * .08 ? P["field-mid"] : P["bg"];
          ctx.fillRect(x * C, y * C, C, C);
        }
      } else {
        if (!swapped) { swapped = true; swap(); }
        const k = Math.floor(Math.min(1, (t - cover) / reveal) * n);
        for (let i = k; i < n; i++) {
          const idx = back[i], x = idx % cols, y = (idx / cols) | 0;
          ctx.fillStyle = i < k + n * .06 ? P["field-dim"] : P["bg"];
          ctx.fillRect(x * C, y * C, C, C);
        }
        if (t >= cover + reveal) { canvas.remove(); resolve(); return; }
      }
      requestAnimationFrame(frame);
    };
    requestAnimationFrame(frame);
  });
}

/** Burst of square pixels from a point (song added, all fixed…). */
export function confetti(x, y, count = 70) {
  if (reducedMotion()) return;
  const canvas = document.createElement("canvas");
  canvas.style.cssText = "position:fixed;inset:0;width:100%;height:100%;pointer-events:none;z-index:80";
  document.body.appendChild(canvas);
  const dpr = devicePixelRatio || 1, W = innerWidth, H = innerHeight;
  canvas.width = W * dpr; canvas.height = H * dpr;
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const P = colors(), tones = [P.text, P["field-crest"], P["field-hover"], P["field-lit"], P.ok, P.info];
  const bits = Array.from({ length: count }, () => {
    const a = -Math.PI / 2 + (Math.random() - .5) * Math.PI * .9, s = 4 + Math.random() * 7;
    return { x, y, vx: Math.cos(a) * s, vy: Math.sin(a) * s, size: Math.random() < .3 ? 8 : 5,
             c: tones[(Math.random() * tones.length) | 0], life: 900 + Math.random() * 500 };
  });
  const t0 = performance.now();
  const frame = now => {
    const t = now - t0;
    ctx.clearRect(0, 0, W, H);
    let alive = 0;
    for (const b of bits) {
      if (t > b.life) continue;
      alive++;
      b.vy += .32; b.vx *= .985; b.x += b.vx; b.y += b.vy;
      ctx.globalAlpha = Math.max(0, 1 - t / b.life);
      ctx.fillStyle = b.c;
      ctx.fillRect(Math.round(b.x / 2) * 2, Math.round(b.y / 2) * 2, b.size, b.size);
    }
    if (alive) requestAnimationFrame(frame); else canvas.remove();
  };
  requestAnimationFrame(frame);
}

/** Types example queries into an input's placeholder until the user focuses it. */
export function typePlaceholder(input, lines) {
  if (reducedMotion()) { input.placeholder = lines[0]; return () => {}; }
  let li = 0, ci = 0, dir = 1, timer = 0, stopped = false;
  const tick = () => {
    if (stopped) return;
    const s = lines[li];
    ci += dir;
    input.placeholder = s.slice(0, ci) + "▌";
    let wait = dir > 0 ? 45 + Math.random() * 70 : 22;
    if (ci >= s.length && dir > 0) { dir = -1; wait = 1900; }
    else if (ci <= 0 && dir < 0) { dir = 1; li = (li + 1) % lines.length; wait = 380; }
    timer = setTimeout(tick, wait);
  };
  const stop = () => { stopped = true; clearTimeout(timer); input.placeholder = t("ui.add.placeholder"); };
  input.addEventListener("focus", stop, { once: true });
  tick();
  return stop;
}
