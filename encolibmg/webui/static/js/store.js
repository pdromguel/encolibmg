// Tiny global store: one state object, shallow patches, one re-render per animation frame.

const subs = new Set();
let scheduled = false;

export const state = {
  route: { name: "home", param: null },
  app: null,          // {version, library, stats, job}
  tracks: null,       // cached library list
  job: null,          // {id, label, step, frac, kind}
  player: null,       // {base, title, url, playing, ...}
  queue: null,        // {items, running, paused} for the open library
  queueOpen: false,   // the queue panel above the footer
  view: {},           // per-screen state, keyed by screen name
};

export function set(patch) {
  Object.assign(state, patch);
  schedule();
}

/** Patch the per-screen state of `name` (creates it on first use). */
export function setView(name, patch) {
  state.view[name] = { ...(state.view[name] || {}), ...patch };
  schedule();
}

/** Per-screen state; keys missing from it get their defaults from `init` (a screen may be
 *  pre-filled by another one, e.g. Home → Adicionar with only {query}). */
export function view(name, init = {}) {
  const cur = state.view[name] || {};
  for (const k of Object.keys(init)) if (!(k in cur)) cur[k] = init[k];
  state.view[name] = cur;
  return cur;
}

export function schedule() {
  if (scheduled) return;
  scheduled = true;
  // next frame; the timer covers a hidden or covered window, where the browser pauses animation frames
  let timer = 0;
  const flush = () => {
    if (!scheduled) return;
    scheduled = false;
    clearTimeout(timer);
    for (const fn of subs) fn(state);
  };
  requestAnimationFrame(flush);
  timer = setTimeout(flush, 120);
}

export function subscribe(fn) {
  subs.add(fn);
  return () => subs.delete(fn);
}
