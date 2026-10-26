"""Small modal dialogs: edit artist/title, library settings (manifest), video picker."""

from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

from encolibmg.manifest import FLAGS, ensure_additional, flag_value, read_manifest, set_flag, write_manifest


def fmt_dur(seconds) -> str:
    if not seconds:
        return "?"
    s = int(round(seconds))
    return f"{s // 60}:{s % 60:02d}"


class _Modal(tk.Toplevel):
    def __init__(self, master, title):
        super().__init__(master)
        self.title(title)
        self.transient(master.winfo_toplevel())
        self.resizable(False, False)
        self.result = None
        self.bind("<Escape>", lambda e: self.destroy())

    def show(self):
        self.grab_set()
        self.wait_window()
        return self.result


class EditTrackDialog(_Modal):
    """Returns (artist, title) or None."""

    def __init__(self, master, artist: str, title: str, note: str = ""):
        super().__init__(master, "Editar faixa")
        f = ttk.Frame(self, padding=12)
        f.pack(fill="both")
        self.artist, self.title_var = tk.StringVar(value=artist), tk.StringVar(value=title)
        ttk.Label(f, text="Artista:").grid(row=0, column=0, sticky="w")
        a = ttk.Entry(f, textvariable=self.artist, width=48)
        a.grid(row=0, column=1, pady=3)
        ttk.Label(f, text="Título:").grid(row=1, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.title_var, width=48).grid(row=1, column=1, pady=3)
        if note:
            ttk.Label(f, text=note, foreground="gray", wraplength=380).grid(row=2, column=0, columnspan=2,
                                                                          sticky="w", pady=(6, 0))
        b = ttk.Frame(f)
        b.grid(row=3, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(b, text="Cancelar", command=self.destroy).pack(side="right")
        ttk.Button(b, text="Salvar", command=self.ok).pack(side="right", padx=6)
        self.bind("<Return>", lambda e: self.ok())
        a.focus_set()
        a.select_range(0, "end")

    def ok(self):
        artist, title = self.artist.get().strip(), self.title_var.get().strip()
        if not artist or not title:
            messagebox.showwarning("Editar", "Preencha artista e título.", parent=self)
            return
        self.result = (artist, title)
        self.destroy()


class ManifestDialog(_Modal):
    """Edits manifest.json in place; unknown keys are kept."""

    def __init__(self, master, lib_path):
        super().__init__(master, "Configurar biblioteca")
        self.lib_path = lib_path
        self.data = read_manifest(lib_path)
        f = ttk.Frame(self, padding=12)
        f.pack(fill="both")
        self.name = tk.StringVar(value=self.data.get("title", ""))
        ttk.Label(f, text="Nome (aparece no Encore):").pack(anchor="w")
        ttk.Entry(f, textvariable=self.name, width=50).pack(fill="x", pady=(2, 8))
        ttk.Label(f, text="Descrição:").pack(anchor="w")
        self.desc = tk.Text(f, width=50, height=3, font=("Segoe UI", 9))
        self.desc.insert("1.0", self.data.get("description", ""))
        self.desc.pack(fill="x", pady=(2, 8))
        ttk.Label(f, text="Opções do Encore:").pack(anchor="w")
        self.flag_vars = {}
        for key, label, _ in FLAGS:
            v = tk.BooleanVar(value=flag_value(self.data, key))
            self.flag_vars[key] = v
            ttk.Checkbutton(f, text=label, variable=v).pack(anchor="w")
        b = ttk.Frame(f)
        b.pack(fill="x", pady=(10, 0))
        ttk.Button(b, text="Cancelar", command=self.destroy).pack(side="right")
        ttk.Button(b, text="Salvar", command=self.ok).pack(side="right", padx=6)

    def ok(self):
        if not self.name.get().strip():
            messagebox.showwarning("Biblioteca", "O nome não pode ficar vazio.", parent=self)
            return
        self.data["title"] = self.name.get().strip()
        self.data["description"] = self.desc.get("1.0", "end").strip()
        for key, v in self.flag_vars.items():
            set_flag(self.data, key, v.get())
        ensure_additional(self.data)
        write_manifest(self.lib_path, self.data)
        self.result = True
        self.destroy()


class VideoPicker(tk.Toplevel):
    """Pick one YouTube video; ✓ marks durations within `tolerance` s of `target`."""

    def __init__(self, master, heading, videos, on_pick, target: float | None = None, tolerance: float = 2.0):
        super().__init__(master)
        self.title(heading)
        self.geometry("760x400")
        self.transient(master.winfo_toplevel())
        self.videos, self.on_pick = videos, on_pick

        if target:
            ttk.Label(self, text=f"✓ = mesma duração do áudio ({fmt_dur(target)}), mais chance de ficar no tempo.",
                      foreground="gray").pack(anchor="w", padx=10, pady=(10, 0))
        cols = ("ok", "title", "channel", "dur")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="browse")
        for col, text, width in [("ok", "✓", 30), ("title", "Vídeo", 420), ("channel", "Canal", 180),
                                 ("dur", "Duração", 70)]:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, stretch=col in ("title", "channel"),
                             anchor="center" if col in ("ok", "dur") else "w")
        first_ok = None
        for i, v in enumerate(videos):
            ok = bool(target and v.duration and abs(v.duration - target) <= tolerance)
            if ok and first_ok is None:
                first_ok = i
            self.tree.insert("", "end", iid=str(i), values=("✓" if ok else "", v.title, v.channel,
                                                            fmt_dur(v.duration)))
        if videos:
            self.tree.selection_set(str(first_ok or 0))
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)
        self.tree.bind("<Double-1>", lambda e: self.pick())

        row = ttk.Frame(self)
        row.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(row, text="▶ Ver no navegador", command=self.preview).pack(side="left")
        ttk.Button(row, text="⬇ Baixar este", command=self.pick).pack(side="right")
        ttk.Button(row, text="Fechar", command=self.destroy).pack(side="right", padx=6)

    def _current(self):
        sel = self.tree.selection()
        return self.videos[int(sel[0])] if sel else None

    def preview(self):
        v = self._current()
        if v:
            webbrowser.open(v.url)

    def pick(self):
        v = self._current()
        if v:
            self.destroy()
            self.on_pick(v)
