// One audio player for the whole app (dock mini player, Sync, Guide preview).
// Web Audio routes Multiplex channels: "both", "left" (instrumental) or "right" (vocals) to both ears.
import { set, state } from "./store.js";

const audio = new Audio();
audio.preload = "auto";
let ctx = null, gains = null;

function graph() {
  if (ctx) return;
  ctx = new AudioContext();
  const src = ctx.createMediaElementSource(audio);
  const split = ctx.createChannelSplitter(2), merge = ctx.createChannelMerger(2);
  const g = () => ctx.createGain();
  gains = { LL: g(), LR: g(), RL: g(), RR: g() };
  src.connect(split);
  split.connect(gains.LL, 0).connect(merge, 0, 0);
  split.connect(gains.LR, 0).connect(merge, 0, 1);
  split.connect(gains.RL, 1).connect(merge, 0, 0);
  split.connect(gains.RR, 1).connect(merge, 0, 1);
  merge.connect(ctx.destination);
  applyChannel();
}

function applyChannel() {
  if (!gains) return;
  const ch = state.player?.channel || "both";
  const v = { both: [1, 0, 0, 1], left: [1, 1, 0, 0], right: [0, 0, 1, 1] }[ch];
  [gains.LL.gain.value, gains.LR.gain.value, gains.RL.gain.value, gains.RR.gain.value] = v;
}

// The store (and so the whole UI) updates ~8×/s for the clock; canvases that need 60 fps
// (waveform, piano roll) read player.time() in their own animation loop.
let raf = 0, lastPush = 0;
function tick(now) {
  raf = 0;
  if (!state.player) return;
  const playing = !audio.paused;
  if (now - lastPush > 120 || playing !== state.player.playing) {
    lastPush = now;
    set({ player: { ...state.player, time: audio.currentTime, duration: audio.duration || state.player.duration, playing } });
  }
  if (playing) raf = requestAnimationFrame(tick);
}
const kick = () => { lastPush = 0; if (!raf) raf = requestAnimationFrame(tick); };
audio.addEventListener("play", kick);
audio.addEventListener("pause", kick);
audio.addEventListener("seeked", kick);
audio.addEventListener("loadedmetadata", kick);
audio.addEventListener("ended", kick);

export const player = {
  audio,
  /** Loads a track (no-op if it's already loaded). */
  load({ base, title, url, multiplexed = false, channel }) {
    graph();
    if (state.player?.url !== url) {
      audio.src = url;
      audio.load();
    }
    set({ player: { base, title, url, multiplexed, channel: channel || state.player?.channel || "both",
                    time: audio.currentTime || 0, duration: null, playing: false } });
    applyChannel();
  },
  async play() {
    graph();
    if (ctx.state === "suspended") await ctx.resume();
    try { await audio.play(); }
    catch (e) { if (e.name !== "AbortError") throw e; }  // another track was loaded meanwhile: not an error
  },
  pause() { audio.pause(); },
  toggle() { audio.paused ? this.play() : this.pause(); },
  seek(t) { audio.currentTime = Math.max(0, Math.min(t, audio.duration || t)); kick(); },
  time() { return audio.currentTime; },
  setChannel(channel) { if (state.player) { set({ player: { ...state.player, channel } }); applyChannel(); } },
  stop() { audio.pause(); audio.removeAttribute("src"); audio.load(); set({ player: null }); },
  get loaded() { return !!state.player; },
};
