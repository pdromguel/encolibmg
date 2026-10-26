import { test } from "node:test";
import assert from "node:assert/strict";

// lit-html (imported by i18n.js for tt) touches the DOM when it loads: a tiny stub is enough here
globalThis.document ??= { documentElement: {}, createTreeWalker: () => ({}), createComment: () => ({}) };
const { setCatalog, t, fixed, currentLang } = await import("../../encolibmg/webui/static/js/i18n.js");

test("t: params, plurals and fallback", () => {
  setCatalog({ "a.hi": "Hi {name}", "a.n": { one: "{count} track", other: "{count} tracks" } }, "en");
  assert.equal(currentLang(), "en");
  assert.equal(document.documentElement.lang, "en");
  assert.equal(t("a.hi", { name: "Ana" }), "Hi Ana");
  assert.equal(t("a.hi"), "Hi {name}");
  assert.equal(t("a.n", { count: 1 }), "1 track");
  assert.equal(t("a.n", { count: 0 }), "0 tracks");
  assert.equal(t("nope.key"), "nope.key");
});

test("fixed follows the language", () => {
  setCatalog({}, "pt-BR");
  assert.equal(fixed(0.25), "0,25");
  setCatalog({}, "en");
  assert.equal(fixed(0.25), "0.25");
});
