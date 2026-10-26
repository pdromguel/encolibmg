"""'Biblioteca' tab: what is already in the EncoreLibrary folder, and per-track actions."""

from __future__ import annotations

import os
import re
import tkinter as tk
from tkinter import messagebox, ttk

from encolibmg import pipeline
from encolibmg.audio.convert import duration
from encolibmg.errors import AlreadyExists
from encolibmg.gui.dialogs import EditTrackDialog, VideoPicker
from encolibmg.gui.worker import Worker
from encolibmg.library import AUDIO_EXTS, kind_label


class LibraryTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        self.tracks = []
        self.searcher = Worker(self)

        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text="Filtrar:").pack(side="left")
        self.filter = tk.StringVar()
        self.filter.trace_add("write", lambda *a: self._fill())
        ttk.Entry(top, textvariable=self.filter).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(top, text="Atualizar", command=self.refresh).pack(side="left")

        cols = ("artist", "title", "kind", "files")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="extended")
        for col, text, width in [("artist", "Artista", 190), ("title", "Título", 260),
                                 ("kind", "Tipo", 190), ("files", "Arquivos", 200)]:
            self.tree.heading(col, text=text, command=lambda c=col: self._sort(c))
            self.tree.column(col, width=width)
        self.tree.tag_configure("orphan", foreground="#c0392b")
        self.tree.pack(fill="both", expand=True, pady=6)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._update_buttons())
        self.tree.bind("<Double-1>", lambda e: self.sync())

        actions = ttk.Frame(self)
        actions.pack(fill="x")
        self.btn = {}
        for key, text, cmd in [("edit", "✏ Editar…", self.edit), ("sync", "⏱ Sincronia…", self.sync),
                               ("guide", "🎼 Gerar guia", self.make_guides),
                               ("preview", "👁 Prévia do guia…", self.preview_guide),
                               ("clip", "🎬 Adicionar clipe…", self.add_clip),
                               ("mux", "🎚 Converter p/ Multiplex", self.convert)]:
            self.btn[key] = ttk.Button(actions, text=text, command=cmd)
            self.btn[key].pack(side="left", padx=(0, 6))

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", pady=(6, 0))
        self.count = tk.StringVar()
        ttk.Label(bottom, textvariable=self.count).pack(side="left")
        ttk.Button(bottom, text="Abrir pasta", command=self.open_folder).pack(side="right")
        self.btn["remove"] = ttk.Button(bottom, text="Remover", command=self.remove)
        self.btn["remove"].pack(side="right", padx=6)
        self._sort_key = "artist"
        app.jobs.listeners.append(self._update_buttons)
        self._update_buttons()

    # --- list ---------------------------------------------------------------
    def refresh(self):
        lib = self.app.library
        self.tracks = lib.scan() if lib else []
        self._fill()

    def _sort(self, col):
        self._sort_key = col
        self._fill()

    def _fill(self):
        self.tree.delete(*self.tree.get_children())
        f = self.filter.get().strip().lower()
        shown = [t for t in self.tracks if f in t.base.lower()]
        key = {"artist": lambda t: (t.artist.lower(), t.title.lower()),
               "title": lambda t: t.title.lower(),
               "kind": lambda t: kind_label(t),
               "files": lambda t: len(t.files)}[self._sort_key]
        for t in sorted(shown, key=key):
            exts = " ".join(sorted("".join(p.suffixes[-2:]) if re.search(r"\.(multiplexed|guide|melody)\.", p.name, re.I)
                                   else p.suffix for p in t.files))
            self.tree.insert("", "end", iid=str(self.tracks.index(t)),
                             values=(t.artist, t.title, kind_label(t), exts), tags=(t.kind,))
        orphans = sum(1 for t in self.tracks if t.kind == "orphan")
        msg = f"{len(self.tracks)} faixa" + ("" if len(self.tracks) == 1 else "s")
        if orphans:
            msg += f" — {orphans} invisíveis no Encore (áudio sem letra)"
        self.count.set(msg)
        self._update_buttons()

    def selected(self):
        return [self.tracks[int(i)] for i in self.tree.selection()]

    def _update_buttons(self):
        sel = self.selected()
        one = sel[0] if len(sel) == 1 else None
        busy = self.app.jobs.busy
        rules = {
            "edit": one is not None,
            "sync": one is not None and one.file_with({".lrc"}) is not None,
            "guide": any(t.kind == "multiplex_lrc" for t in sel),
            "preview": one is not None and one.has_guide and one.multiplexed,
            "clip": one is not None and one.multiplexed and not one.has_video,
            "mux": one is not None and one.kind == "audio_lrc",
            "remove": bool(sel),
        }
        for key, ok in rules.items():
            heavy = key in ("guide", "clip", "mux", "remove")
            self.btn[key].config(state="normal" if ok and not (heavy and busy) else "disabled")

    # --- actions ------------------------------------------------------------
    def edit(self):
        sel = self.selected()
        if len(sel) != 1:
            return
        t = sel[0]
        res = EditTrackDialog(self, t.artist, t.title, note=(
            "Renomeia todos os arquivos da faixa. O Encore vai dar um código novo para ela "
            "(o código antigo deixa de funcionar).")).show()
        if not res:
            return
        try:
            self.app.library.rename_track(t, *res)
        except (AlreadyExists, OSError) as e:
            messagebox.showerror("Editar", str(e))
        self.refresh()

    def sync(self):
        sel = self.selected()
        if len(sel) != 1 or sel[0].file_with({".lrc"}) is None:
            return
        from encolibmg.gui.sync_window import SyncWindow

        track = sel[0]

        def saved():
            self.app.jobs.set_status(f"✔ Letra de {track.base} salva.")
            if track.has_guide and messagebox.askyesno(
                    "Guia MIDI", "Esta faixa tem guia MIDI, e o Encore mostra a letra do guia, não a do .lrc.\n\n"
                    "Regerar o guia com a letra nova agora?"):
                self._run_guides([track])

        try:
            SyncWindow(self, track, on_saved=saved)
        except Exception as e:
            messagebox.showerror("Sincronia", f"Não consegui abrir a faixa:\n{e}")

    def make_guides(self):
        todo = [t for t in self.selected() if t.kind == "multiplex_lrc"]
        if todo:
            self._run_guides(todo)

    def _run_guides(self, tracks):
        from encolibmg.errors import Cancelled
        from encolibmg.guide.build import build_guide

        lib = self.app.library

        def work(progress, cancel):
            out = []
            for n, t in enumerate(tracks):
                label = f"{n + 1}/{len(tracks)} {t.base}" if len(tracks) > 1 else t.base
                try:
                    _, stats = build_guide(lib, t, lambda s, f=None, l=label: progress(f"{l}: {s}", f), cancel)
                    out.append((t.base, stats))
                except Cancelled:
                    raise
                except Exception as e:
                    out.append((t.base, e))
            return out

        def done(out):
            ok = [(b, s) for b, s in out if isinstance(s, dict)]
            bad = [(b, s) for b, s in out if not isinstance(s, dict)]
            if len(out) == 1 and ok:
                s = ok[0][1]
                msg = (f"✔ Guia de {ok[0][0]}: {s['notes']} notas, {s['aligned']} linhas alinhadas"
                       + (f", {s['fallback']} estimadas" if s["fallback"] else "") + ".")
            else:
                msg = f"✔ {len(ok)} guia(s) gerado(s)" + (f", {len(bad)} com erro" if bad else "") + "."
            self._done(msg)
            if bad:
                messagebox.showerror("Guia MIDI", "\n".join(f"{b}: {e}" for b, e in bad[:10]))

        self.app.jobs.run(work, "Gerando guia MIDI… (a primeira vez carrega o modelo, ~20 s)", on_done=done)

    def preview_guide(self):
        sel = self.selected()
        if len(sel) != 1 or not sel[0].has_guide:
            return
        from encolibmg.gui.guide_preview import GuidePreview

        try:
            GuidePreview(self, sel[0])
        except Exception as e:
            messagebox.showerror("Prévia", f"Não consegui abrir o guia:\n{e}")

    def add_clip(self):
        sel = self.selected()
        if len(sel) != 1 or self.searcher.busy:
            return
        t = sel[0]
        audio = t.file_with(AUDIO_EXTS)
        self.app.jobs.set_status(f"Buscando clipes de {t.base}…")

        def work(p, c):
            return pipeline.find_clip(t.artist, t.title), duration(audio) if audio else None

        def show(res):
            videos, dur = res
            self.app.jobs.set_status("Escolha o clipe.")
            if not videos:
                messagebox.showinfo("Clipe", "Nenhum vídeo encontrado.")
                return
            VideoPicker(self, f"Clipe — {t.base}", videos, target=dur, on_pick=lambda v: self.app.jobs.run(
                lambda prog, cancel: pipeline.add_clip(self.app.library, t, v, prog, cancel),
                f"Baixando clipe de {t.base}…", on_done=lambda tr: self._done(f"✔ Clipe adicionado a {tr.base}.")))

        self.searcher.run(work, on_done=show,
                          on_error=lambda e: messagebox.showerror("Clipe", f"Falha na busca:\n{e}"))

    def convert(self):
        sel = self.selected()
        if len(sel) != 1 or sel[0].kind != "audio_lrc":
            return
        t = sel[0]
        self.app.jobs.run(lambda p, c: pipeline.convert_to_multiplex(self.app.library, t, p, c),
                          f"Convertendo {t.base} para Multiplex…",
                          on_done=lambda tr: self._done(f"✔ {tr.base} agora é Multiplex."))

    def _done(self, msg):
        self.app.jobs.set_status(msg)
        self.refresh()

    def remove(self):
        sel = self.selected()
        if not sel:
            return
        names = "\n".join(t.base for t in sel[:10]) + ("\n…" if len(sel) > 10 else "")
        if messagebox.askyesno("Remover", f"Mandar para a Lixeira {len(sel)} faixa(s)?\n\n{names}"):
            for t in sel:
                self.app.library.remove(t)
            self.refresh()

    def open_folder(self):
        if self.app.library:
            os.startfile(self.app.library.path)
