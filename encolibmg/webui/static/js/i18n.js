// UI translations. The catalog comes from Python (encolibmg/locales/*.json) so both sides share one source.
import { html } from "../vendor/lit-html.js";

let catalog = {}, lang = "en";

export function setCatalog(c, l) {
  catalog = c || {};
  lang = l || "en";
  document.documentElement.lang = lang;
}

export const currentLang = () => lang;

function lookup(key, p) {
  let s = catalog[key];
  if (s == null) return key;
  if (typeof s === "object") s = p.count === 1 ? s.one : s.other;
  return s;
}

/** Translated text; {name} is replaced by p.name (missing params stay visible). Plurals pick by p.count. */
export function t(key, p = {}) {
  return lookup(key, p).replace(/\{(\w+)\}/g, (m, k) => (k in p ? String(p[k]) : m));
}

/** Like t(), but params may be lit templates (e.g. <kbd>, <b>): returns a template. */
export function tt(key, p = {}) {
  const parts = lookup(key, p).split(/\{(\w+)\}/);
  return html`${parts.map((x, i) => (i % 2 ? (x in p ? p[x] : `{${x}}`) : x))}`;
}

/** Numbers in the current language (1.234 vs 1,234). */
export const num = n => (typeof n === "number" ? n.toLocaleString(lang) : n);

/** Fixed decimals in the current language (0,25 vs 0.25). */
export const fixed = (n, d = 2) => n.toLocaleString(lang, { minimumFractionDigits: d, maximumFractionDigits: d });
