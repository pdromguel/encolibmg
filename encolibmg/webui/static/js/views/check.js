// Verificar: finds what Encore would ignore or show wrong; groups by problem; fixes selected or everything.
import { icon } from "../fx/icons.js";
import { html } from "../../vendor/lit-html.js";
import { runJob } from "../api.js";
import { refresh } from "../app.js";
import { confetti } from "../fx/overlay.js";
import { setView, state, view } from "../store.js";
import { toast } from "../ui/toast.js";
import { t, tt } from "../i18n.js";
import { noLibrary, pageHead } from "./common.js";

const WHAT = [1, 2, 3, 4, 5, 6, 7, 8];  // ui.check.what.N (title) + ui.check.what.Nd (what the fix does)

const v = () => view("check", { issues: null, results: {}, checked: [], loudness: false, running: false });

async function run() {
  const s = v();
  setView("check", { running: true, results: {}, checked: [] });
  try {
    const issues = await runJob("check", s.loudness);
    setView("check", { issues, running: false, checked: issues.filter(i => i.fixable).map(i => i.id) });
    if (!issues.length) {
      confetti(innerWidth / 2, innerHeight / 3);
      toast(t("ui.check.clean"), { kind: "ok" });
    }
  } catch (e) {
    setView("check", { running: false });
    if (e.kind !== "Cancelled") toast(e.message, { kind: "bad" });
  }
}

async function fix(ids) {
  if (!ids.length) return;
  try {
    const out = await runJob("fix", ids);
    const results = { ...v().results, ...out };
    setView("check", { results, checked: v().checked.filter(i => !(i in out)) });
    await refresh();
    const ok = Object.values(out).filter(r => r.ok).length, bad = Object.values(out).length - ok;
    toast(t("ui.check.fixed", { count: ok }) + (bad ? t("ui.check.not_fixed", { count: bad }) : "") + ".", { kind: bad ? "warn" : "ok" });
    if (ok && !bad) confetti(innerWidth / 2, innerHeight / 3, 50);
  } catch (e) { if (e.kind !== "Cancelled") toast(e.message, { kind: "bad" }); }
}

function groups(issues) {
  const map = new Map();
  for (const i of issues) {
    if (!map.has(i.kind)) map.set(i.kind, { kind: i.kind, label: i.label, items: [] });
    map.get(i.kind).items.push(i);
  }
  return [...map.values()];
}

export const check = {
  render(st) {
    if (!st.app?.library) return html`<div class="page">${pageHead(t("ui.nav.check"), "")}${noLibrary()}</div>`;
    const s = v(), busy = !!st.job;
    const pending = s.issues ? s.issues.filter(i => i.fixable && !s.results[i.id]?.ok) : [];
    return html`<div class="page chk">
      ${pageHead(t("ui.nav.check"), t("ui.check.sub"), html`
        <label class="check"><input type="checkbox" .checked=${s.loudness} @change=${e => setView("check", { loudness: e.target.checked })}>
          ${t("ui.check.loudness")} <span class="muted">${t("ui.check.loudness_cost")}</span></label>
        <button class="btn lg" ?disabled=${busy} @click=${run}>${icon("search")} ${t(s.issues ? "ui.check.again" : "ui.check.run")}</button>`)}
      ${s.issues === null ? html`
        <div class="whatgrid">${WHAT.map((n, i) => html`<div class="what rise" style="--i:${i}"><b>${t(`ui.check.what.${n}`)}</b><span>${t(`ui.check.what.${n}d`)}</span></div>`)}</div>`
      : s.issues.length === 0 ? html`
        <div class="empty rise"><div class="box brackets on"><pixel-mark style="width:56px;height:56px;margin:0 auto 14px"></pixel-mark>
          <h3>${t("ui.check.ok_title")}</h3><p>${t("ui.check.ok_text")}</p></div></div>`
      : html`
        <div class="checkbar rise">
          <span>${tt("ui.check.summary", { count: s.issues.length, n: html`<b>${s.issues.length}</b>`, m: html`<b>${pending.length}</b>` })}</span>
          <span class="grow"></span>
          <button class="btn ghost" ?disabled=${busy || !s.checked.length} @click=${() => fix(s.checked)}>${t("ui.check.fix_selected", { count: s.checked.length })}</button>
          <button class="btn" ?disabled=${busy || !pending.length} @click=${() => fix(pending.map(i => i.id))}>${t("ui.check.fix_all", { count: pending.length })}</button>
        </div>
        ${groups(s.issues).map((g, gi) => html`
          <section class="igroup rise" style="--i:${gi + 1}">
            <h4><span>${g.label}</span><span class="muted">${g.items.length}</span></h4>
            ${g.items.map(i => {
              const r = s.results[i.id];
              return html`<div class="irow ${r ? (r.ok ? "fixed" : "failed") : ""} ${i.fixable ? "" : "manual"}">
                ${i.fixable && !r?.ok ? html`<label class="check"><input type="checkbox" .checked=${s.checked.includes(i.id)}
                  @change=${e => setView("check", { checked: e.target.checked ? [...s.checked, i.id] : s.checked.filter(x => x !== i.id) })}></label>`
                  : html`<span class="ist">${r ? (r.ok ? "✓" : "✕") : "·"}</span>`}
                <div class="grow"><div class="f ellipsis selectable">${i.file}</div>
                  <div class="m">${r ? r.message : i.message}</div></div>
                ${!i.fixable ? html`<span class="badge">${t("ui.check.manual")}</span>` : ""}
              </div>`;
            })}
          </section>`)}`}
    </div>`;
  },
};
