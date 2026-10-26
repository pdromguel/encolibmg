import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { cells, fmtTime, hash, identicon, shuffledOrder, textGrid } from "../../encolibmg/webui/static/js/fx/core.js";

const brand = JSON.parse(readFileSync(new URL("../../encolibmg/webui/static/brand/brand.json", import.meta.url)));

test("textGrid matches the Python wordmark", () => {
  assert.deepEqual(textGrid("ENCOLIBMG", brand.font, { bold: true, accentFrom: 7 }), brand.wordmark);
});

test("cells lists lit and mid pixels", () => {
  assert.deepEqual(cells(["#.+", "..."]), [{ x: 0, y: 0, c: "#" }, { x: 2, y: 0, c: "+" }]);
});

test("identicon is stable, mirrored and never empty", () => {
  const a = identicon("Queen - Bohemian Rhapsody");
  assert.deepEqual(a, identicon("Queen - Bohemian Rhapsody"));
  assert.notDeepEqual(a, identicon("Adele - Hello"));
  for (const name of ["", "x", "Adele - Hello", "宇多田ヒカル - First Love"]) {
    const g = identicon(name);
    assert.equal(g.length, 5);
    for (const row of g) assert.equal(row, [...row].reverse().join(""));
    assert.ok(g.join("").split("#").length - 1 >= 3);
  }
});

test("hash is FNV-1a", () => {
  assert.equal(hash(""), 0x811c9dc5);
  assert.equal(hash("a"), 0xe40c292c);
});

test("shuffledOrder is a permutation and repeatable", () => {
  const o = shuffledOrder(500, 7);
  assert.deepEqual([...o].sort((a, b) => a - b), Array.from({ length: 500 }, (_, i) => i));
  assert.deepEqual(o, shuffledOrder(500, 7));
  assert.notDeepEqual(o, shuffledOrder(500, 8));
});

test("fmtTime", () => {
  assert.equal(fmtTime(0), "0:00");
  assert.equal(fmtTime(295.7), "4:55");
  assert.equal(fmtTime(null), "–:––");
});

import { retime } from "../../encolibmg/webui/static/js/fx/core.js";
const L = [{ ms: 1000, text: "a" }, { ms: 5000, text: "b" }, { ms: 9000, text: "c" }, { ms: 13000, text: "d" }];
const ms = r => r.map(x => x.ms);

test("retime matches Python apply_anchors", () => {
  assert.deepEqual(ms(retime(L, {})), [1000, 5000, 9000, 13000]);
  assert.deepEqual(ms(retime(L, { 1: 5600 })), [1600, 5600, 9600, 13600]);
  assert.deepEqual(ms(retime(L, { 1: 5500, 2: 10300 })), [700, 5500, 10300, 15100]);
  assert.deepEqual(ms(retime(L, { 0: 1000, 1: 6000, 3: 14000 })), [1000, 6000, 10000, 14000]);
  assert.deepEqual(ms(retime(L, {}, -1500)), [0, 3500, 7500, 11500]);
  const same = [{ ms: 1000, text: "a" }, { ms: 1000, text: "a2" }, { ms: 4000, text: "b" }];
  assert.deepEqual(ms(retime(same, { 0: 1500, 1: 1500 })), [1500, 1500, 4500]);
  assert.deepEqual(retime(L, { 2: 9500 }, -200).map(r => r.i), [0, 1, 2, 3]);
});
