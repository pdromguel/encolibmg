"""'Verificar' tab: list library problems and fix them."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from encolibmg import checker
from encolibmg.errors import Cancelled


class CheckTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        self.issues: list[checker.Issue] = []
        self.results: dict[int, str] = {}

        top = ttk.Frame(self)
        top.pack(fill="x")
        self.check_btn = ttk.Button(top, text="🔎 Verificar biblioteca", command=self.run_check)
        self.check_btn.pack(side="left")
        self.loud = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="incluir volume (lento, ~1 s por faixa)", variable=self.loud).pack(
            side="left", padx=10)

        cols = ("result", "kind", "file", "msg")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="extended")
        for col, text, width in [("result", "", 30), ("kind", "Problema", 150), ("file", "Arquivo", 260),
                                 ("msg", "Detalhe", 360)]:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, stretch=col in ("file", "msg"),
                             anchor="center" if col == "result" else "w")
        self.tree.tag_configure("manual", foreground="gray")
        self.tree.tag_configure("ok", foreground="#1e8449")
        self.tree.tag_configure("fail", foreground="#c0392b")
        self.tree.pack(fill="both", expand=True, pady=6)

        bottom = ttk.Frame(self)
        bottom.pack(fill="x")
        self.count = tk.StringVar(value="Clique em Verificar.")
        ttk.Label(bottom, textvariable=self.count).pack(side="left")
        self.fix_all_btn = ttk.Button(bottom, text="Corrigir tudo que for automático",
                                      command=lambda: self.fix(all_=True))
        self.fix_all_btn.pack(side="right")
        self.fix_sel_btn = ttk.Button(bottom, text="Corrigir selecionados", command=self.fix)
        self.fix_sel_btn.pack(side="right", padx=6)
        app.jobs.listeners.append(self._update_buttons)
        self._update_buttons()

    def _update_buttons(self):
        state = "disabled" if self.app.jobs.busy else "normal"
        for b in (self.check_btn, self.fix_all_btn, self.fix_sel_btn):
            b.config(state=state)

    def run_check(self):
        lib = self.app.require_library()
        if lib is None:
            return
        loud = self.loud.get()
        self.app.jobs.run(lambda p, c: checker.check(lib, include_loudness=loud, cancel=c, on_progress=p),
                          "Verificando a biblioteca…", on_done=self._show)

    def _show(self, issues):
        self.issues, self.results = issues, {}
        self._fill()
        self.app.jobs.set_status(f"Verificação concluída: {len(issues)} problema(s).")

    def _fill(self):
        self.tree.delete(*self.tree.get_children())
        lib = self.app.library
        for i, issue in enumerate(self.issues):
            try:
                rel = str(issue.path.relative_to(lib.path))
            except ValueError:
                rel = issue.path.name
            res = self.results.get(i, "")
            tag = ("ok" if res.startswith("✔") else "fail" if res.startswith("✖")
                   else "" if issue.fixable else "manual")
            self.tree.insert("", "end", iid=str(i), tags=(tag,), values=(
                res[:1], checker.KIND_LABEL.get(issue.kind, issue.kind), rel, res[2:] or issue.message))
        fixable = sum(1 for i, x in enumerate(self.issues) if x.fixable and i not in self.results)
        self.count.set(f"{len(self.issues)} problema(s), {fixable} com correção automática."
                       if self.issues else "Nenhum problema encontrado. 🎉")

    def fix(self, all_=False):
        lib = self.app.library
        if lib is None:
            return
        idx = [i for i, x in enumerate(self.issues) if x.fixable and i not in self.results] if all_ \
            else [int(i) for i in self.tree.selection() if self.issues[int(i)].fixable]
        if not idx:
            messagebox.showinfo("Corrigir", "Nada com correção automática selecionado.")
            return
        issues = self.issues

        def work(progress, cancel):
            out = {}
            for n, i in enumerate(idx):
                if cancel.is_set():
                    raise Cancelled()
                progress(f"corrigindo {n + 1}/{len(idx)}", n / len(idx))
                try:
                    out[i] = "✔ " + checker.fix(lib, issues[i])
                except Exception as e:  # one failure never stops the others
                    out[i] = f"✖ {e}"
            return out

        self.app.jobs.run(work, "Corrigindo…", on_done=self._fixed)

    def _fixed(self, out):
        self.results.update(out)
        self._fill()
        ok = sum(1 for r in out.values() if r.startswith("✔"))
        self.app.jobs.set_status(f"{ok} de {len(out)} corrigido(s).")
        self.app.library_changed()
