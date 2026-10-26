// Bridge to Python (window.pywebview.api) + events pushed from Python (window.encolib.emit).
import { toast } from "./ui/toast.js";

const ready = new Promise(resolve => {
  if (window.pywebview?.api) resolve();
  else window.addEventListener("pywebviewready", () => resolve(), { once: true });
});

export class ApiError extends Error {
  constructor(message, kind) { super(message); this.kind = kind; }
}

/** Calls a Python method; rejects with ApiError (message already in Portuguese). */
export async function call(name, ...args) {
  await ready;
  const fn = window.pywebview.api[name];
  if (!fn) throw new ApiError(`Função ${name} indisponível.`, "Missing");
  const res = await fn(...args);
  if (!res || !res.ok) throw new ApiError(res?.error || "Algo deu errado.", res?.kind || "Error");
  return res.data;
}

/** Same as call(), but shows the error as a toast and resolves to `fallback`. */
export async function tryCall(name, ...args) {
  try {
    return await call(name, ...args);
  } catch (e) {
    toast(e.message, { kind: e.kind === "NoLibrary" || e.kind === "Busy" ? "warn" : "bad" });
    return undefined;
  }
}

const listeners = new Map();
export function on(event, fn) {
  if (!listeners.has(event)) listeners.set(event, new Set());
  listeners.get(event).add(fn);
  return () => listeners.get(event).delete(fn);
}

window.encolib = {
  emit(event, data) {
    for (const fn of listeners.get(event) || []) {
      try { fn(data); } catch (e) { console.error(e); }
    }
  },
};

/** Starts a job-returning method and resolves with its result when the `job` event says done. */
export async function runJob(name, ...args) {
  const started = await call(name, ...args);
  if (!started || started.job == null) return started;
  return new Promise((resolve, reject) => {
    const off = on("job", ev => {
      if (ev.id !== started.job) return;
      if (ev.type === "done") { off(); resolve(ev.result); }
      else if (ev.type === "cancelled") { off(); reject(new ApiError("Cancelado.", "Cancelled")); }
      else if (ev.type === "error") { off(); reject(new ApiError(ev.error, ev.kind)); }
    });
  });
}
