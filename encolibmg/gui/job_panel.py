"""Bottom progress panel shared by every tab: one heavy job at a time (GPU, disk)."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from encolibmg.errors import Cancelled
from encolibmg.gui.worker import Worker


class JobPanel(ttk.LabelFrame):
    def __init__(self, master):
        super().__init__(master, text="Progresso", padding=8)
        self.worker = Worker(self)
        self.listeners: list = []  # called with no args when busy state changes
        self.status = tk.StringVar(value="Pronto.")
        ttk.Label(self, textvariable=self.status).pack(anchor="w")
        row = ttk.Frame(self)
        row.pack(fill="x", pady=(4, 0))
        self.bar = ttk.Progressbar(row, mode="determinate", maximum=1.0)
        self.bar.pack(side="left", fill="x", expand=True)
        self.cancel_btn = ttk.Button(row, text="Cancelar", command=self.cancel, state="disabled")
        self.cancel_btn.pack(side="left", padx=(6, 0))

    @property
    def busy(self) -> bool:
        return self.worker.busy

    def set_status(self, text: str):
        self.status.set(text)

    def run(self, fn, label: str, on_done=None, on_error=None) -> bool:
        """`fn(on_progress, cancel)` in a thread. on_error gets every error except Cancelled."""
        if self.busy:
            messagebox.showinfo("Aguarde", "Já existe uma tarefa em andamento. Espere terminar ou cancele.")
            return False
        self.status.set(label)
        self._reset(0)
        self.worker.run(fn, on_progress=self._progress,
                        on_done=lambda r: self._finish(on_done, r),
                        on_error=lambda e: self._fail(on_error, e))
        self._notify()
        return True

    def cancel(self):
        self.worker.cancel.set()
        self.status.set("Cancelando…")

    def _notify(self):
        self.cancel_btn.config(state="normal" if self.busy else "disabled")
        for fn in self.listeners:
            fn()

    def _reset(self, value):
        self.bar.stop()
        self.bar.config(mode="determinate", value=value)

    def _progress(self, step, frac):
        text = step[:1].upper() + step[1:]
        if frac is None:
            self.status.set(f"{text}…")
            if str(self.bar.cget("mode")) != "indeterminate":
                self.bar.config(mode="indeterminate")
                self.bar.start(15)
        else:
            if str(self.bar.cget("mode")) != "determinate":
                self._reset(frac)
            self.bar.config(value=frac)
            self.status.set(f"{text}… {int(frac * 100)}%")

    def _finish(self, on_done, result):
        self._reset(1.0)
        self.status.set("Concluído.")
        self._notify()
        if on_done:
            on_done(result)

    def _fail(self, on_error, err):
        self._reset(0)
        self._notify()
        if isinstance(err, Cancelled):
            self.status.set("Cancelado.")
            return
        self.status.set("Falhou.")
        if on_error:
            on_error(err)
        else:
            messagebox.showerror("Erro", f"{type(err).__name__}: {err}\n\nDetalhes no log.")
