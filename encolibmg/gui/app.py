"""Main window."""

from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from encolibmg import __version__
from encolibmg.gui.add_tab import AddTab
from encolibmg.gui.check_tab import CheckTab
from encolibmg.gui.dialogs import ManifestDialog
from encolibmg.gui.import_tab import ImportTab
from encolibmg.gui.job_panel import JobPanel
from encolibmg.gui.library_tab import LibraryTab
from encolibmg.gui.visual_tab import VisualTab
from encolibmg.library import Library, LibraryError
from encolibmg.paths import load_config, save_config

log = logging.getLogger(__name__)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"EncoLibMG {__version__}")
        self.geometry("980x700")
        self.minsize(760, 540)
        try:
            ttk.Style(self).theme_use("vista")
        except tk.TclError:
            pass
        self.library: Library | None = None
        self.cfg = load_config()

        bar = ttk.Frame(self, padding=(10, 8))
        bar.pack(fill="x")
        ttk.Label(bar, text="Biblioteca:").pack(side="left")
        self.lib_label = tk.StringVar(value="nenhuma")
        ttk.Label(bar, textvariable=self.lib_label, font=("Segoe UI", 9, "bold")).pack(side="left", padx=6)
        ttk.Button(bar, text="Criar nova…", command=self.create_library).pack(side="right")
        ttk.Button(bar, text="Abrir…", command=self.open_library).pack(side="right", padx=6)
        ttk.Button(bar, text="⚙ Configurar…", command=self.configure_library).pack(side="right")

        # bottom panel first so it keeps its space when the window shrinks
        self.jobs = JobPanel(self)
        self.jobs.pack(side="bottom", fill="x", padx=8, pady=(0, 8))

        self.notebook = nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.add_tab = AddTab(nb, self)
        self.library_tab = LibraryTab(nb, self)
        self.check_tab = CheckTab(nb, self)
        self.import_tab = ImportTab(nb, self)
        self.visual_tab = VisualTab(nb, self)
        nb.add(self.add_tab, text="  Adicionar  ")
        nb.add(self.library_tab, text="  Biblioteca  ")
        nb.add(self.check_tab, text="  Verificar  ")
        nb.add(self.import_tab, text="  Importar  ")
        nb.add(self.visual_tab, text="  Visual e som  ")

        last = self.cfg.get("library")
        if last:
            try:
                self.set_library(Library.open(Path(last)))
            except LibraryError:
                log.warning("last library missing: %s", last)

    def report_callback_exception(self, exc, val, tb):
        log.error("UI error", exc_info=(exc, val, tb))
        messagebox.showerror("Erro", f"{exc.__name__}: {val}")

    def set_library(self, lib: Library):
        self.library = lib
        self._show_library_name()
        self.cfg["library"] = str(lib.path)
        save_config(self.cfg)
        self.library_changed()

    def _show_library_name(self):
        if self.library:
            self.lib_label.set(f"{self.library.title}  —  {self.library.path}")

    def configure_library(self):
        lib = self.require_library()
        if lib and ManifestDialog(self, lib.path).show():
            self._show_library_name()
            self.jobs.set_status("✔ Configuração da biblioteca salva. Reabra a biblioteca no Encore para aplicar.")

    def library_changed(self):
        self.library_tab.refresh()
        self.visual_tab.refresh()

    def require_library(self) -> Library | None:
        if self.library is None:
            messagebox.showinfo("Biblioteca", "Abra ou crie uma biblioteca primeiro (botões no topo).")
        return self.library

    def open_library(self):
        folder = filedialog.askdirectory(title="Pasta da EncoreLibrary (com manifest.json)")
        if not folder:
            return
        try:
            self.set_library(Library.open(Path(folder)))
        except LibraryError as e:
            if messagebox.askyesno("Biblioteca", f"{e}\n\nTransformar esta pasta numa biblioteca?"):
                self.set_library(Library.create(Path(folder), Path(folder).name))

    def create_library(self):
        parent = filedialog.askdirectory(title="Onde criar a pasta EncoreLibrary?")
        if not parent:
            return
        title = simpledialog.askstring("Nome", "Nome da biblioteca (aparece no Encore):",
                                       initialvalue="Minha Biblioteca", parent=self)
        if not title:
            return
        folder = Path(parent)
        if folder.name.lower() != "encorelibrary":
            folder = folder / "EncoreLibrary"
        self.set_library(Library.create(folder, title))
