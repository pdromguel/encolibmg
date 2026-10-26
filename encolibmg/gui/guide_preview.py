"""'Prévia do guia': piano roll + word-by-word lyrics playing along with the track."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from encolibmg.audio.player import Player
from encolibmg.guide.midi import read_guide
from encolibmg.library import Track

VISIBLE = 8.0     # seconds on screen
PLAYHEAD = 0.25   # playhead position (fraction of width)
TICK_MS = 33
NAMES = "C C# D D# E F F# G G# A A# B".split()


def fmt(sec: float) -> str:
    return f"{int(sec // 60)}:{int(sec % 60):02d}"


class GuidePreview(tk.Toplevel):
    def __init__(self, master, track: Track, player: Player | None = None):
        super().__init__(master)
        guide = next(f for f in track.files if ".guide." in f.name.lower())
        mp3 = next(f for f in track.files if ".multiplexed." in f.name.lower())
        self.title(f"Prévia do guia — {track.base}")
        self.geometry("900x520")
        self.info = read_guide(guide)
        self.player = player or Player(mp3)
        self.words = self.info.lyrics
        # group words into display lines ('/' starts a new line)
        self.lines: list[list[tuple[float, str]]] = []
        for t, text in self.words:
            if text.startswith("/") or not self.lines:
                self.lines.append([])
            self.lines[-1].append((t, text.lstrip("/")))
        pitches = [n.pitch for n in self.info.notes] or [60]
        self.lo, self.hi = min(pitches) - 2, max(pitches) + 2

        bar = ttk.Frame(self, padding=(10, 8))
        bar.pack(fill="x")
        self.play_btn = ttk.Button(bar, text="▶ Tocar", width=10, command=self.toggle)
        self.play_btn.pack(side="left")
        self.time_var = tk.StringVar()
        ttk.Label(bar, textvariable=self.time_var, width=12).pack(side="left", padx=8)
        self.seek = tk.DoubleVar()
        scale = ttk.Scale(bar, from_=0, to=self.player.duration, variable=self.seek)
        scale.pack(side="left", fill="x", expand=True)
        self._dragging = False
        scale.bind("<ButtonPress-1>", lambda e: setattr(self, "_dragging", True))
        scale.bind("<ButtonRelease-1>", self._seek_release)
        ttk.Label(bar, text="Ouvir:").pack(side="left", padx=(10, 2))
        self.channel = tk.StringVar(value="Ambos")
        box = ttk.Combobox(bar, textvariable=self.channel, values=["Ambos", "Instrumental", "Voz"],
                           state="readonly", width=12)
        box.pack(side="left")
        box.bind("<<ComboboxSelected>>", lambda e: setattr(
            self.player, "channel", {"Ambos": "both", "Instrumental": "left", "Voz": "right"}[self.channel.get()]))

        self.canvas = tk.Canvas(self, bg="#14161f", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=10)
        self.lyric = tk.Canvas(self, bg="#14161f", height=90, highlightthickness=0)
        self.lyric.pack(fill="x", padx=10, pady=(0, 6))
        ttk.Label(self, foreground="gray", padding=(10, 0, 10, 8), text=(
            f"{len(self.info.notes)} notas · {len(self.words)} palavras. As barras são as notas que o Encore vai "
            "usar no guia e na pontuação; a letra acende palavra por palavra como no Encore. "
            "Dica: ouça só a Voz para conferir.")).pack(anchor="w")

        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<space>", lambda e: (self.toggle(), "break")[1])
        self._tick_id = self.after(TICK_MS, self._tick)

    def toggle(self):
        self.player.pause() if self.player.playing else self.player.play()

    def _seek_release(self, _e):
        self.player.seek(self.seek.get())
        self._dragging = False

    def _draw_roll(self, pos: float):
        c = self.canvas
        c.delete("all")
        w, h = max(c.winfo_width(), 100), max(c.winfo_height(), 100)
        t0 = pos - VISIBLE * PLAYHEAD
        sx = w / VISIBLE
        rows = self.hi - self.lo + 1
        rh = h / rows
        for p in range(self.lo, self.hi + 1):
            y = h - (p - self.lo + 1) * rh
            if NAMES[p % 12] == "C":
                c.create_line(0, y + rh, w, y + rh, fill="#2a2e3d")
                c.create_text(4, y + rh / 2, text=f"C{p // 12 - 1}", fill="#555b70", anchor="w", font=("Segoe UI", 8))
        for n in self.info.notes:
            if n.end < t0 or n.start > t0 + VISIBLE:
                continue
            x1, x2 = (n.start - t0) * sx, (n.end - t0) * sx
            y = h - (n.pitch - self.lo + 1) * rh
            active = n.start <= pos < n.end
            c.create_rectangle(x1, y + 1, x2, y + rh - 1, fill="#ffd166" if active else "#4cc9f0",
                               outline="")
        for t, text in self.words:
            if t0 <= t <= t0 + VISIBLE:
                c.create_text((t - t0) * sx + 2, h - 4, text=text.lstrip("/").strip(), anchor="sw",
                              fill="#8d93a8", font=("Segoe UI", 8))
        px = VISIBLE * PLAYHEAD * sx
        c.create_line(px, 0, px, h, fill="#ef476f", width=2)

    def _draw_lyric(self, pos: float):
        c = self.lyric
        c.delete("all")
        w = max(c.winfo_width(), 100)
        cur = 0
        for i, line in enumerate(self.lines):
            if line and line[0][0] <= pos + 0.3:
                cur = i
        for row, idx in enumerate((cur, cur + 1)):
            if idx >= len(self.lines):
                continue
            x, y = 12, 28 + row * 40
            for t, text in self.lines[idx]:
                sung = idx == cur and t <= pos
                item = c.create_text(x, y, text=text, anchor="w", font=("Segoe UI", 18 if row == 0 else 13, "bold"),
                                     fill="#ffd166" if sung else ("#ffffff" if row == 0 else "#8d93a8"))
                x = c.bbox(item)[2]
                if x > w - 20:
                    break

    def _tick(self):
        pos = self.player.position
        self.play_btn.config(text="⏸ Pausar" if self.player.playing else "▶ Tocar")
        self.time_var.set(f"{fmt(pos)} / {fmt(self.player.duration)}")
        if not self._dragging:
            self.seek.set(pos)
        self._draw_roll(pos)
        self._draw_lyric(pos)
        self._tick_id = self.after(TICK_MS, self._tick)

    def close(self):
        self.after_cancel(self._tick_id)
        self.player.close()
        self.destroy()
