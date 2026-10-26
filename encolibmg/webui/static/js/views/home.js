// Home: pixel field + assembling wordmark, big search, library numbers, recently added.
import { html } from "../../vendor/lit-html.js";
import { go } from "../app.js";
import { typePlaceholder } from "../fx/effects.js";
import { setView } from "../store.js";
import { t, tt } from "../i18n.js";
import { badgeText, noLibrary } from "./common.js";

const EXAMPLES = ["Queen - Bohemian Rhapsody", "Adele - Someone Like You", "Elis Regina - Águas de Março",
                  "RADWIMPS - Sparkle", "Tim Maia - Gostava Tanto de Você", "Journey - Don't Stop Believin'"];
let stopTyping = null;

function submit(e) {
  e.preventDefault();
  const q = new FormData(e.target).get("q")?.toString().trim();
  if (!q) return;
  setView("add", { query: q, autorun: true });
  go("add");
}

function stat(n, label, href, tone = "") {
  return html`<a class="stat rise brackets hoverable" href=${href}>
    <span class="num ${tone}">${n}</span><span class="lbl">${label}</span></a>`;
}

export const home = {
  enter() {
    requestAnimationFrame(() => {
      const input = document.querySelector(".hero-search input");
      if (input) { stopTyping?.(); stopTyping = typePlaceholder(input, EXAMPLES); }
    });
  },
  leave() { stopTyping?.(); stopTyping = null; },
  render(s) {
    const lib = s.app?.library, st = s.app?.stats || {};
    const recent = [...(s.tracks || [])].sort((a, b) => b.mtime - a.mtime).slice(0, 6);
    const pending = (st.orphans || 0) + (st.no_guide || 0);
    return html`
    <section class="hero">
      <pixel-field></pixel-field>
      <div class="hero-inner">
        <pixel-wordmark class="hero-word"></pixel-wordmark>
        <p class="hero-tag rise" style="--i:8">${t("ui.home.tag")}</p>
        ${lib ? html`
          <form class="hero-search rise brackets" style="--i:10" @submit=${submit}>
            <span class="prompt">›</span>
            <input name="q" data-search autocomplete="off" spellcheck="false" aria-label=${t("ui.home.search_aria")}
                   @focus=${e => e.target.closest("form").classList.add("on")}
                   @blur=${e => e.target.closest("form").classList.remove("on")}>
            <kbd>Enter</kbd>
          </form>
          <p class="hero-hint rise" style="--i:12">${tt("ui.home.hint", { key: html`<kbd>/</kbd>` })}</p>`
        : html`<div class="rise" style="--i:10">${noLibrary(t("ui.home.nolib"))}</div>`}
      </div>
    </section>
    ${lib ? html`
    <section class="page home-below">
      <div class="stats">
        ${stat(st.tracks ?? "–", t("ui.home.stat.tracks", { count: st.tracks }), "#/library")}
        ${stat(st.multiplex ?? "–", t("ui.home.stat.multiplex"), "#/library")}
        ${stat(st.guides ?? "–", t("ui.home.stat.guides"), "#/library")}
        ${stat(st.mtv ?? "–", t("ui.home.stat.mtv"), "#/library")}
        ${stat(pending, t("ui.home.stat.pending", { count: pending }), "#/check", pending ? "warn" : "ok")}
      </div>
      ${recent.length ? html`
        <h3 class="rise" style="margin:34px 0 12px">${t("ui.home.recent")}</h3>
        <div class="recent">
          ${recent.map((t, i) => html`<a class="rcard rise" style="--i:${i}" href="#/library"
              @click=${() => setView("library", { selected: t.base })}>
            <pixel-identicon name=${t.base}></pixel-identicon>
            <span class="t ellipsis">${t.title}</span><span class="a ellipsis">${t.artist}</span>
            <span class="badges">${t.badges.slice(0, 3).map(b => html`<span class="badge">${badgeText(b)}</span>`)}</span>
          </a>`)}
        </div>` : html`<p class="muted rise" style="margin-top:28px">${t("ui.home.empty")}</p>`}
    </section>` : ""}`;
  },
};
