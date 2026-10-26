"""'Adicionar' tab: search synced lyrics, download Multiplex+LRC or a karaoke MTV."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from encolibmg import pipeline
from encolibmg.errors import AlreadyExists, NoAudioMatch
from encolibmg.gui.dialogs import VideoPicker, fmt_dur
from encolibmg.gui.worker import Worker
from encolibmg.lyrics import lrclib


class AddTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        self.results: list[lrclib.LyricsCandidate] = []
        self.searcher = Worker(self)

        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text="Música:").pack(side="left")
        self.query = tk.StringVar()
        entry = ttk.Entry(top, textvariable=self.query)
        entry.pack(side="left", fill="x", expand=True, padx=6)
        entry.bind("<Return>", lambda e: self.search())
        self.search_btn = ttk.Button(top, text="Buscar letra", command=self.search)
        self.search_btn.pack(side="left")
        self.hint = tk.StringVar(value='Dica: "Artista - Música" encontra mais rápido. ✓ = letra sincronizada.')
        ttk.Label(self, textvariable=self.hint, foreground="gray").pack(anchor="w", pady=(4, 6))

        cols = ("sync", "artist", "title", "album", "dur")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="browse", height=14)
        for col, text, width, anchor in [("sync", "✓", 30, "center"), ("artist", "Artista", 180, "w"),
                                         ("title", "Título", 240, "w"), ("album", "Álbum", 180, "w"),
                                         ("dur", "Duração", 70, "center")]:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor=anchor, stretch=col in ("artist", "title", "album"))
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._update_buttons())
        self.tree.bind("<Double-1>", lambda e: self.add_full())

        btns = ttk.Frame(self)
        btns.pack(fill="x", pady=(8, 0))
        self.full_btn = ttk.Button(btns, text="⬇ Baixar completa (Multiplex + LRC)", command=self.add_full)
        self.full_btn.pack(side="left")
        self.mtv_btn = ttk.Button(btns, text="🎬 Buscar vídeo de karaokê (MTV)", command=self.find_mtv)
        self.mtv_btn.pack(side="left", padx=6)
        self.make_guide = tk.BooleanVar(value=True)
        ttk.Checkbutton(btns, text="Gerar guia MIDI (notas e letra palavra a palavra)",
                        variable=self.make_guide).pack(side="right")
        app.jobs.listeners.append(self._update_buttons)
        self._update_buttons()

    # --- search -------------------------------------------------------------
    def search(self):
        q = self.query.get().strip()
        if not q or self.searcher.busy:
            return
        self.search_btn.config(state="disabled")
        self.hint.set(f"Buscando letras para “{q}”…")
        self.searcher.run(lambda p, c: lrclib.search(q), on_done=self._show_results, on_error=self._search_failed)

    def _show_results(self, results):
        self.search_btn.config(state="normal")
        self.results = results
        self.tree.delete(*self.tree.get_children())
        for i, c in enumerate(results):
            self.tree.insert("", "end", iid=str(i), values=(
                "✓" if c.synced else "", c.artist, c.title, c.album, fmt_dur(c.duration)))
        synced = sum(1 for c in results if c.synced)
        if results:
            self.tree.selection_set("0")
            self.hint.set(f"{len(results)} resultados, {synced} com letra sincronizada.")
        else:
            self.hint.set("Nenhuma letra encontrada. Tente outro nome ou busque o vídeo de karaokê.")
        self._update_buttons()

    def _search_failed(self, err):
        self.search_btn.config(state="normal")
        self.hint.set("Falha na busca.")
        messagebox.showerror("Busca", f"Não consegui buscar:\n{err}")

    def selected(self) -> lrclib.LyricsCandidate | None:
        sel = self.tree.selection()
        return self.results[int(sel[0])] if sel else None

    def _update_buttons(self):
        busy = self.app.jobs.busy
        c = self.selected()
        self.full_btn.config(state="normal" if (c and c.synced and not busy) else "disabled")
        self.mtv_btn.config(state="disabled" if busy else "normal")

    # --- downloads ----------------------------------------------------------
    def _start(self, fn, label):
        lib = self.app.require_library()
        if lib is None:
            return
        self.app.jobs.run(lambda p, c: fn(lib, p, c), label, on_done=self._done, on_error=self._failed)

    def add_full(self):
        c = self.selected()
        if not c or not c.synced or self.app.jobs.busy:
            return
        guide = self.make_guide.get()
        self._start(lambda lib, p, cancel: pipeline.add_song(lib, c, p, cancel, make_guide=guide),
                    f"Adicionando {c.artist} - {c.title}…")

    def _artist_title(self):
        c = self.selected()
        if c:
            return c.artist, c.title
        q = self.query.get().strip()
        if " - " in q:
            a, t = q.split(" - ", 1)
            return a.strip(), t.strip()
        messagebox.showinfo("MTV", 'Digite a busca no formato "Artista - Música" para nomear o vídeo.')
        return None

    def find_mtv(self):
        at = self._artist_title()
        if not at or self.searcher.busy:
            return
        artist, title = at
        self.hint.set(f"Buscando vídeos de karaokê de {artist} - {title}…")
        self.searcher.run(lambda p, c: pipeline.find_mtv(artist, title),
                          on_done=lambda vids: self._pick_video(artist, title, vids),
                          on_error=self._search_failed)

    def _pick_video(self, artist, title, videos):
        self.hint.set("Escolha o vídeo.")
        if not videos:
            messagebox.showinfo("MTV", "Nenhum vídeo encontrado.")
            return
        VideoPicker(self, f"MTV — {artist} - {title}", videos, on_pick=lambda v: self._start(
            lambda lib, p, cancel: pipeline.add_mtv(lib, artist, title, v, p, cancel),
            f"Baixando MTV {artist} - {title}…"))

    def _done(self, track):
        self.app.jobs.set_status(f"✔ {track.base} adicionada.")
        self.app.library_changed()

    def _failed(self, err):
        if isinstance(err, AlreadyExists):
            messagebox.showinfo("Já existe", str(err))
        elif isinstance(err, NoAudioMatch):
            if messagebox.askyesno("Áudio não encontrado", f"{err}\n\nBuscar um vídeo de karaokê (MTV)?"):
                self.find_mtv()
        else:
            messagebox.showerror("Erro", f"{type(err).__name__}: {err}\n\nDetalhes no log.")
