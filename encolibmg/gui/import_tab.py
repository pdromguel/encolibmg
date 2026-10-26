"""'Importar' tab: preview and import files you already have."""

from __future__ import annotations

import shutil
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from encolibmg import importer
from encolibmg.errors import Cancelled
from encolibmg.gui.dialogs import EditTrackDialog
from encolibmg.gui.worker import Worker


class ImportTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        self.items: list[importer.ImportItem] = []
        self.tmp: Path | None = None
        self.scanner = Worker(self)

        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text="Origem:").pack(side="left")
        self.source = tk.StringVar()
        ttk.Entry(top, textvariable=self.source).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(top, text="Escolher…", command=self.choose).pack(side="left")
        self.scan_btn = ttk.Button(top, text="Analisar", command=self.scan)
        self.scan_btn.pack(side="left", padx=(6, 0))

        opts = ttk.Frame(self)
        opts.pack(fill="x", pady=6)
        self.move = tk.BooleanVar(value=False)
        self.find_lyrics = tk.BooleanVar(value=True)
        self.multiplex = tk.BooleanVar(value=False)
        self.normalize = tk.BooleanVar(value=True)
        for text, var in [("Mover (manda os originais para a Lixeira)", self.move),
                          ("Buscar letra para áudios sem letra", self.find_lyrics),
                          ("Converter para Multiplex (lento)", self.multiplex),
                          ("Ajustar volume", self.normalize)]:
            ttk.Checkbutton(opts, text=text, variable=var).pack(side="left", padx=(0, 12))

        cols = ("sel", "artist", "title", "kind", "source", "status")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="extended")
        for col, text, width in [("sel", "☑", 30), ("artist", "Artista", 150), ("title", "Título", 200),
                                 ("kind", "Tipo", 150), ("source", "Arquivo de origem", 220),
                                 ("status", "Situação", 160)]:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, stretch=col not in ("sel",),
                             anchor="center" if col == "sel" else "w")
        self.tree.tag_configure("off", foreground="gray")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self._edit)
        self.tree.bind("<space>", lambda e: self.toggle())
        self.tree.bind("<Button-1>", self._click)

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", pady=(6, 0))
        self.count = tk.StringVar(value="Escolha uma pasta com músicas, CDGs, vídeos ou .zip e clique em Analisar.")
        ttk.Label(bottom, textvariable=self.count).pack(side="left")
        self.import_btn = ttk.Button(bottom, text="⬇ Importar marcados", command=self.run_import)
        self.import_btn.pack(side="right")
        ttk.Button(bottom, text="Desmarcar todos", command=lambda: self.set_all(False)).pack(side="right", padx=6)
        ttk.Button(bottom, text="Marcar todos", command=lambda: self.set_all(True)).pack(side="right")
        ttk.Label(self, foreground="gray", text="Duplo clique corrige artista/título. Clique em ☑ ou Espaço "
                  "marca/desmarca.").pack(anchor="w", pady=(4, 0))
        app.jobs.listeners.append(self._update_buttons)
        self._update_buttons()

    def _update_buttons(self):
        self.import_btn.config(state="disabled" if self.app.jobs.busy else "normal")

    def choose(self):
        folder = filedialog.askdirectory(title="Pasta com as músicas para importar")
        if folder:
            self.source.set(folder)
            self.scan()

    def _new_tmp(self) -> Path:
        if self.tmp:
            shutil.rmtree(self.tmp, ignore_errors=True)
        self.tmp = Path(tempfile.mkdtemp(prefix="encore-import-"))
        return self.tmp

    def scan(self):
        src = Path(self.source.get().strip())
        if not src.is_dir() or self.scanner.busy:
            if not src.is_dir():
                messagebox.showinfo("Importar", "Escolha uma pasta que exista.")
            return
        lib = self.app.require_library()
        if lib is None:
            return
        tmp = self._new_tmp()
        self.scan_btn.config(state="disabled")
        self.count.set("Analisando…")

        def work(p, c):
            items = importer.scan_source(src, tmp)
            importer.mark_existing(lib, items)
            return items

        self.scanner.run(work, on_done=self._show, on_error=self._scan_failed)

    def _scan_failed(self, err):
        self.scan_btn.config(state="normal")
        messagebox.showerror("Importar", f"Falha ao analisar:\n{err}")

    def _show(self, items):
        self.scan_btn.config(state="normal")
        self.items = items
        self._fill()

    def _fill(self):
        self.tree.delete(*self.tree.get_children())
        for i, it in enumerate(self.items):
            self.tree.insert("", "end", iid=str(i), tags=() if it.selected else ("off",), values=(
                "☑" if it.selected else "☐", it.artist, it.title, importer.KIND_LABEL.get(it.kind, it.kind),
                it.main.name, it.status))
        sel = sum(1 for it in self.items if it.selected)
        self.count.set(f"{len(self.items)} encontrada(s), {sel} marcada(s) para importar.")

    def _click(self, e):
        if self.tree.identify_column(e.x) == "#1" and self.tree.identify_row(e.y):
            row = self.tree.identify_row(e.y)
            self.items[int(row)].selected ^= True
            self._fill()
            return "break"

    def toggle(self):
        for i in self.tree.selection():
            self.items[int(i)].selected ^= True
        sel = self.tree.selection()
        self._fill()
        self.tree.selection_set(sel)

    def set_all(self, value: bool):
        for it in self.items:
            if value and it.status in ("já existe", "repetida na origem"):
                continue
            it.selected = value
        self._fill()

    def _edit(self, e):
        row = self.tree.identify_row(e.y)
        if not row:
            return
        it = self.items[int(row)]
        res = EditTrackDialog(self, it.artist, it.title).show()
        if res:
            it.artist, it.title = res
            it.status = ""
            it.selected = True
            if self.app.library:
                importer.mark_existing(self.app.library, self.items)
            self._fill()

    def run_import(self):
        lib = self.app.require_library()
        chosen = [it for it in self.items if it.selected]
        if lib is None or not chosen:
            return
        if self.move.get() and not messagebox.askyesno(
                "Mover", f"Os {len(chosen)} arquivo(s) de origem vão para a Lixeira depois de importados. Continuar?"):
            return
        opts = dict(move=self.move.get(), find_lyrics=self.find_lyrics.get(),
                    make_multiplex=self.multiplex.get(), normalize=self.normalize.get())

        def work(progress, cancel):
            out = {}
            for n, it in enumerate(chosen):
                if cancel.is_set():
                    raise Cancelled()
                label = f"{n + 1}/{len(chosen)} {it.base}"
                progress(label, n / len(chosen))
                try:
                    out[id(it)] = importer.import_item(
                        lib, it, cancel=cancel, on_progress=lambda s, f=None, l=label: progress(f"{l}: {s}", f),
                        **opts)
                except Cancelled:
                    raise
                except Exception as e:  # keep going with the rest
                    out[id(it)] = f"✖ {e}"
            return out

        self.app.jobs.run(work, "Importando…", on_done=lambda out: self._imported(chosen, out))

    def _imported(self, chosen, out):
        for it in chosen:
            it.status = out.get(id(it), it.status)
            it.selected = False
        self._fill()
        ok = sum(1 for s in out.values() if s.startswith("importada"))
        self.app.jobs.set_status(f"Importação concluída: {ok} de {len(out)} importada(s).")
        self.app.library_changed()

    def destroy(self):
        if self.tmp:
            shutil.rmtree(self.tmp, ignore_errors=True)
        super().destroy()
