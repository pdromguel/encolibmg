// Pure pixel helpers (no DOM): used by the canvas elements and by the Node tests.

/** Grid rows ('#' lit, '+' mid, '.' empty) → [{x, y, c}] */
export function cells(grid) {
  const out = [];
  grid.forEach((row, y) => {
    for (let x = 0; x < row.length; x++) {
      const c = row[x];
      if (c === "#" || c === "+") out.push({ x, y, c });
    }
  });
  return out;
}

export function gridSize(grid) {
  return { w: Math.max(0, ...grid.map(r => r.length)), h: grid.length };
}

/** Text in the brand's 5×7 font; letters from `accentFrom` on use '+'; `bold` doubles every pixel. */
export function textGrid(text, font, { bold = false, accentFrom = Infinity } = {}) {
  const rows = Array(7).fill("");
  [...text.toUpperCase()].forEach((ch, i, all) => {
    const glyph = font[ch] || (ch === " " ? Array(7).fill("...") : Array(7).fill("....."));
    for (let r = 0; r < 7; r++) {
      const px = i >= accentFrom ? glyph[r].replaceAll("#", "+") : glyph[r];
      rows[r] += px + (i < all.length - 1 ? "." : "");
    }
  });
  if (!bold) return rows;
  const out = [];
  for (const row of rows) {
    const wide = [...row].map(c => c + c).join("");
    out.push(wide, wide);
  }
  return out;
}

/** FNV-1a 32-bit — stable across sessions and machines. */
export function hash(str) {
  let h = 0x811c9dc5;
  for (const ch of String(str)) {
    h ^= ch.codePointAt(0);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h >>> 0;
}

/** 5×5 mirrored identicon from a name: '#' lit, '+' mid. Always has a few lit cells. */
export function identicon(name) {
  let h = hash(name);
  const next = () => { h = Math.imul(h ^ (h >>> 15), 0x2c1b3c6d) >>> 0; h ^= h >>> 12; return h; };
  const rows = [];
  let lit = 0;
  for (let y = 0; y < 5; y++) {
    const half = [];
    for (let x = 0; x < 3; x++) {
      const r = next() % 100;
      const c = r < 42 ? "#" : r < 58 ? "+" : ".";
      if (c === "#") lit++;
      half.push(c);
    }
    rows.push([half[0], half[1], half[2], half[1], half[0]].join(""));
  }
  if (lit < 3) rows[2] = ".###.";
  return rows;
}

/** Deterministic-for-a-seed shuffled order of n indexes (used by the dissolve transition). */
export function shuffledOrder(n, seed = 1) {
  const a = Array.from({ length: n }, (_, i) => i);
  let s = seed >>> 0 || 1;
  for (let i = n - 1; i > 0; i--) {
    s = Math.imul(s ^ (s >>> 13), 0x5bd1e995) >>> 0;
    const j = s % (i + 1);
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export const easeOut = t => 1 - Math.pow(1 - t, 3);
export const clamp = (v, a, b) => Math.min(b, Math.max(a, v));

export function fmtTime(sec) {
  if (sec == null || !isFinite(sec)) return "–:––";
  sec = Math.max(0, sec);
  const m = Math.floor(sec / 60), s = Math.floor(sec % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function fmtTimePrecise(sec) {
  sec = Math.max(0, sec || 0);
  const m = Math.floor(sec / 60), s = sec - m * 60;
  return `${m}:${s.toFixed(2).padStart(5, "0")}`;
}

/**
 * Same as Python lyrics.sync.retime: lines [{ms,text}], anchors {index: ms}, global offset ms.
 * One anchor shifts everything; more anchors give a piecewise-linear map, extrapolated at the ends.
 * Returns [{i, ms, text}] sorted by time (i = original index).
 */
export function retime(lines, anchors, offset = 0) {
  const pts = new Map();
  Object.entries(anchors).map(([i, ms]) => [lines[+i].ms, ms]).sort((a, b) => a[0] - b[0]).forEach(([o, n]) => pts.set(o, n));
  const olds = [...pts.keys()].sort((a, b) => a - b);
  const remap = t => {
    if (!olds.length) return t;
    if (olds.length === 1) return t + pts.get(olds[0]) - olds[0];
    let k = olds.findIndex(o => o > t);
    if (k === -1) k = olds.length;
    k = Math.min(Math.max(k, 1), olds.length - 1);
    const o0 = olds[k - 1], o1 = olds[k], n0 = pts.get(o0), n1 = pts.get(o1);
    return Math.round(n0 + (t - o0) * (n1 - n0) / (o1 - o0));
  };
  return lines.map((l, i) => ({ i, ms: Math.max(0, remap(l.ms) + offset), text: l.text }))
              .sort((a, b) => a.ms - b.ms || a.i - b.i);
}
