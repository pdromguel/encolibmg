// Início: pixel field + assembling wordmark, big search, library numbers, recently added.
import { html } from "../../vendor/lit-html.js";
import { go } from "../app.js";
import { typePlaceholder } from "../fx/overlay.js";
import { setView } from "../store.js";
import { noLibrary } from "./common.js";

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
        <p class="hero-tag rise" style="--i:8">Sua biblioteca de karaokê, afinada.</p>
        ${lib ? html`
          <form class="hero-search rise brackets" style="--i:10" @submit=${submit}>
            <span class="prompt">›</span>
            <input name="q" data-search autocomplete="off" spellcheck="false" aria-label="Buscar música"
                   @focus=${e => e.target.closest("form").classList.add("on")}
                   @blur=${e => e.target.closest("form").classList.remove("on")}>
            <kbd>Enter</kbd>
          </form>
          <p class="hero-hint rise" style="--i:12">Busca a letra sincronizada, baixa o áudio, separa a voz e gera o guia. <kbd>/</kbd> em qualquer tela.</p>`
        : html`<div class="rise" style="--i:10">${noLibrary("Abra ou crie uma biblioteca para começar a montar seu karaokê.")}</div>`}
      </div>
    </section>
    ${lib ? html`
    <section class="page home-below">
      <div class="stats">
        ${stat(st.tracks ?? "–", "faixas", "#/library")}
        ${stat(st.multiplex ?? "–", "com voz-guia (Multiplex)", "#/library")}
        ${stat(st.guides ?? "–", "com guia MIDI", "#/library")}
        ${stat(st.mtv ?? "–", "vídeos de karaokê", "#/library")}
        ${stat(pending, pending === 1 ? "pendência" : "pendências", "#/check", pending ? "warn" : "ok")}
      </div>
      ${recent.length ? html`
        <h3 class="rise" style="margin:34px 0 12px">Adicionadas recentemente</h3>
        <div class="recent">
          ${recent.map((t, i) => html`<a class="rcard rise" style="--i:${i}" href="#/library"
              @click=${() => setView("library", { selected: t.base })}>
            <pixel-identicon name=${t.base}></pixel-identicon>
            <span class="t ellipsis">${t.title}</span><span class="a ellipsis">${t.artist}</span>
            <span class="badges">${t.badges.slice(0, 3).map(b => html`<span class="badge">${b}</span>`)}</span>
          </a>`)}
        </div>` : html`<p class="muted rise" style="margin-top:28px">Sua biblioteca ainda está vazia. Busque uma música acima para começar.</p>`}
    </section>` : ""}`;
  },
};
