"""'Sincronia' window: play the track, watch the lyrics, shift/anchor and save the .lrc."""

from __future__ import annotations

import shutil
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from encolibmg.audio.player import Player
from encolibmg.library import AUDIO_EXTS, VIDEO_EXTS, Track
from encolibmg.lyrics.match import read_lrc
from encolibmg.lyrics.sync import Line, format_lrc, parse_lrc, retime, vocal_onset
from encolibmg.paths import backup_file, latest_backup

REACTION_MS = 150
TICK_MS = 50


def fmt_time(sec: float) -> str:
    sec = max(0.0, sec)
    return f"{int(sec // 60)}:{sec % 60:05.2f}"


class SyncWindow(tk.Toplevel):
    def __init__(self, master, track: Track, on_saved=None, player: Player | None = None):
        super().__init__(master)
        self.track, self.on_saved = track, on_saved
        self.lrc_path: Path = track.file_with({".lrc"})
        media = track.file_with(AUDIO_EXTS) or track.file_with(VIDEO_EXTS)
        if self.lrc_path is None or media is None:
            self.destroy()
            raise ValueError("A faixa precisa de áudio e .lrc.")
        self.title(f"Sincronia — {track.base}")
        self.geometry("820x600")
        self.minsize(640, 420)

        self.config(cursor="watch")
        self.update_idletasks()
        self.player = player or Player(media)
        self.config(cursor="")
        self.original: list[Line] = parse_lrc(read_lrc(self.lrc_path))
        self.offset_ms = 0
        self.anchors: dict[int, int] = {}
        self.dirty = False
        self._dragging = False

        self._build()
        self._refresh_lines()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<space>", self._space)
        self.bind("<BackSpace>", self._remove_anchor)
        self._tick_id = self.after(TICK_MS, self._tick)

    # --- layout -------------------------------------------------------------
    def _build(self):
        bar = ttk.Frame(self, padding=(10, 8))
        bar.pack(fill="x")
        self.play_btn = ttk.Button(bar, text="▶ Tocar", width=10, command=self.toggle)
        self.play_btn.pack(side="left")
        self.time_var = tk.StringVar()
        ttk.Label(bar, textvariable=self.time_var, width=18).pack(side="left", padx=8)
        self.seek_var = tk.DoubleVar()
        self.scale = ttk.Scale(bar, from_=0, to=self.player.duration, variable=self.seek_var)
        self.scale.pack(side="left", fill="x", expand=True)
        self.scale.bind("<ButtonPress-1>", lambda e: setattr(self, "_dragging", True))
        self.scale.bind("<ButtonRelease-1>", self._seek_release)
        if self.track.multiplexed:
            ttk.Label(bar, text="Ouvir:").pack(side="left", padx=(10, 2))
            self.channel = tk.StringVar(value="Ambos")
            box = ttk.Combobox(bar, textvariable=self.channel, values=["Ambos", "Instrumental", "Voz"],
                               state="readonly", width=12)
            box.pack(side="left")
            box.bind("<<ComboboxSelected>>", lambda e: setattr(
                self.player, "channel", {"Ambos": "both", "Instrumental": "left", "Voz": "right"}[self.channel.get()]))

        cols = ("anchor", "time", "text")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="browse")
        for col, text, width, anchor in [("anchor", "⚓", 34, "center"), ("time", "Tempo", 90, "center"),
                                         ("text", "Letra", 600, "w")]:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor=anchor, stretch=col == "text")
        self.tree.tag_configure("current", background="#ffe58a")
        self.tree.pack(fill="both", expand=True, padx=10)
        self.tree.bind("<Double-1>", self._jump_to_line)

        adj = ttk.Frame(self, padding=(10, 6))
        adj.pack(fill="x")
        ttk.Label(adj, text="Deslocar tudo:").pack(side="left")
        for label, ms in [("−1 s", -1000), ("−0,1 s", -100), ("+0,1 s", 100), ("+1 s", 1000)]:
            ttk.Button(adj, text=label, width=7, command=lambda ms=ms: self.nudge(ms)).pack(side="left", padx=1)
        self.offset_var = tk.StringVar()
        ttk.Label(adj, textvariable=self.offset_var, width=26).pack(side="left", padx=8)
        if self.track.multiplexed:
            ttk.Button(adj, text="✨ Sugerir automaticamente", command=self.suggest).pack(side="left")
        ttk.Button(adj, text="Limpar âncoras", command=self.clear_anchors).pack(side="right")

        ttk.Label(self, foreground="gray", padding=(10, 0), text=(
            "Enquanto toca, aperte Espaço quando a linha selecionada começar a ser cantada (vira âncora ⚓ e "
            "a seleção desce). Com 2+ âncoras a letra é esticada entre elas. Backspace remove. "
            "Duplo clique numa linha toca a partir dela."), wraplength=780).pack(anchor="w")

        bottom = ttk.Frame(self, padding=10)
        bottom.pack(fill="x")
        ttk.Button(bottom, text="Desfazer último salvamento", command=self.undo).pack(side="left")
        ttk.Button(bottom, text="Fechar", command=self.close).pack(side="right")
        ttk.Button(bottom, text="💾 Salvar", command=self.save).pack(side="right", padx=6)

    # --- state --------------------------------------------------------------
    def current_lines(self) -> list[Line]:
        return [l for _, l in retime(self.original, self.anchors, self.offset_ms)]

    def _refresh_lines(self, keep_selection=True):
        sel = self.tree.selection()
        pairs = retime(self.original, self.anchors, self.offset_ms)
        self.lines = [l for _, l in pairs]
        self.order = [i for i, _ in pairs]  # displayed row -> original line index
        self.tree.delete(*self.tree.get_children())
        for row, (orig, l) in enumerate(pairs):
            self.tree.insert("", "end", iid=str(row), values=("⚓" if orig in self.anchors else "",
                                                              fmt_time(l.ms / 1000), l.text))
        if keep_selection and sel and self.tree.exists(sel[0]):
            self.tree.selection_set(sel[0])
        elif self.lines and not sel:
            self.tree.selection_set("0")
        n = len(self.anchors)
        self.offset_var.set(f"Deslocamento: {self.offset_ms / 1000:+.2f} s" + (f" · {n} âncora(s)" if n else ""))
        self._current = None

    def _mark_dirty(self):
        self.dirty = True
        self.title(f"Sincronia — {self.track.base} *")

    def nudge(self, ms: int):
        self.offset_ms += ms
        self._mark_dirty()
        self._refresh_lines()

    def clear_anchors(self):
        self.anchors.clear()
        self._mark_dirty()
        self._refresh_lines()

    def suggest(self):
        onset = vocal_onset(self.player.data[:, 1], self.player.sr)
        if onset is None or not self.original:
            messagebox.showinfo("Sincronia", "Não consegui achar o início da voz.", parent=self)
            return
        self.anchors.clear()
        self.offset_ms = round(onset * 1000) - self.original[0].ms
        self._mark_dirty()
        self._refresh_lines()
        messagebox.showinfo("Sincronia", f"A voz começa em {fmt_time(onset)}. Primeira linha alinhada "
                            f"({self.offset_ms / 1000:+.2f} s). Toque para conferir.", parent=self)

    # --- playback -----------------------------------------------------------
    def toggle(self):
        if self.player.playing:
            self.player.pause()
        else:
            self.player.play()

    def _seek_release(self, _e):
        self.player.seek(self.seek_var.get())
        self._dragging = False

    def _jump_to_line(self, _e):
        sel = self.tree.selection()
        if sel:
            self.player.seek(max(0.0, self.lines[int(sel[0])].ms / 1000 - 1.0))
            self.player.play()

    def _space(self, _e):
        sel = self.tree.selection()
        if not self.player.playing or not sel:
            self.toggle()
            return "break"
        i = int(sel[0])
        tap_ms = round(self.player.position * 1000) - REACTION_MS
        # anchors are stored against the original line, before the global shift
        orig = self.order[i]
        self.anchors[orig] = tap_ms - self.offset_ms
        self._mark_dirty()
        self._refresh_lines(keep_selection=False)
        # select the line that originally followed the tapped one
        nxt = str(min(self.order.index(orig) + 1, len(self.lines) - 1))
        self.tree.selection_set(nxt)
        self.tree.see(nxt)
        return "break"

    def _remove_anchor(self, _e):
        sel = self.tree.selection()
        if sel:
            self.anchors.pop(self.order[int(sel[0])], None)
            self._mark_dirty()
            self._refresh_lines()
        return "break"

    def _tick(self):
        pos = self.player.position
        self.play_btn.config(text="⏸ Pausar" if self.player.playing else "▶ Tocar")
        self.time_var.set(f"{fmt_time(pos)} / {fmt_time(self.player.duration)}")
        if not self._dragging:
            self.seek_var.set(pos)
        ms = pos * 1000
        cur = None
        for i, l in enumerate(self.lines):
            if l.ms <= ms:
                cur = i
            else:
                break
        if cur != self._current:
            if self._current is not None and self.tree.exists(str(self._current)):
                self.tree.item(str(self._current), tags=())
            if cur is not None:
                self.tree.item(str(cur), tags=("current",))
                if self.player.playing:
                    self.tree.see(str(cur))
            self._current = cur
        self._tick_id = self.after(TICK_MS, self._tick)

    # --- files --------------------------------------------------------------
    def save(self):
        backup_file(self.lrc_path)
        self.lrc_path.write_text(format_lrc(self.current_lines()), encoding="utf-8", newline="\n")
        self.original = parse_lrc(read_lrc(self.lrc_path))
        self.offset_ms, self.anchors, self.dirty = 0, {}, False
        self.title(f"Sincronia — {self.track.base}")
        self._refresh_lines()
        if self.on_saved:
            self.on_saved()

    def undo(self):
        bak = latest_backup(self.lrc_path.name)
        if bak is None:
            messagebox.showinfo("Desfazer", "Não há backup desta letra.", parent=self)
            return
        if not messagebox.askyesno("Desfazer", f"Voltar para a versão salva em {bak.parent.name[:16]}?",
                                   parent=self):
            return
        shutil.copy2(bak, self.lrc_path)
        bak.unlink()
        self.original = parse_lrc(read_lrc(self.lrc_path))
        self.offset_ms, self.anchors, self.dirty = 0, {}, False
        self._refresh_lines()

    def close(self):
        if self.dirty and not messagebox.askyesno("Sincronia", "Sair sem salvar as mudanças?", parent=self):
            return
        self.after_cancel(self._tick_id)
        self.player.close()
        self.destroy()
