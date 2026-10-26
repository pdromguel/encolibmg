"""'Visual e som' tab: background videos, idle images, boot video, score narrations, SoundFont."""

from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from encolibmg import soundfont, visual
from encolibmg.errors import Cancelled
from encolibmg.gui.dialogs import VideoPicker, _Modal
from encolibmg.gui.worker import Worker

VIDEO_TYPES = [("Vídeos", "*.mp4 *.mkv *.webm *.avi *.mov *.wmv *.m4v *.mpg *.mpeg"), ("Todos", "*.*")]
IMAGE_TYPES = [("Imagens", "*.png *.jpg *.jpeg *.webp *.gif")]
AUDIO_TYPES = [("Áudio", "*.mp3 *.wav *.ogg *.m4a *.flac *.aac *.wma"), ("Todos", "*.*")]
SF_TYPES = [("SoundFont", "*.sf2 *.sf3 *.dls")]


def _hint(parent, text):
    ttk.Label(parent, text=text, foreground="gray", wraplength=860, justify="left").pack(anchor="w", pady=(0, 8))


class NarrationDialog(_Modal):
    def __init__(self, master):
        super().__init__(master, "Narração da nota")
        f = ttk.Frame(self, padding=12)
        f.pack()
        self.lo, self.hi, self.file = tk.IntVar(value=90), tk.IntVar(value=100), tk.StringVar()
        ttk.Label(f, text="Nota de").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(f, from_=0, to=100, textvariable=self.lo, width=5).grid(row=0, column=1, padx=4)
        ttk.Label(f, text="até").grid(row=0, column=2)
        ttk.Spinbox(f, from_=0, to=100, textvariable=self.hi, width=5).grid(row=0, column=3, padx=4)
        ttk.Label(f, text="Áudio:").grid(row=1, column=0, sticky="w", pady=8)
        ttk.Entry(f, textvariable=self.file, width=36).grid(row=1, column=1, columnspan=3, pady=8)
        ttk.Button(f, text="…", width=3, command=self.choose).grid(row=1, column=4)
        b = ttk.Frame(f)
        b.grid(row=2, column=0, columnspan=5, sticky="e")
        ttk.Button(b, text="Cancelar", command=self.destroy).pack(side="right")
        ttk.Button(b, text="Salvar", command=self.ok).pack(side="right", padx=6)

    def choose(self):
        p = filedialog.askopenfilename(parent=self, filetypes=AUDIO_TYPES)
        if p:
            self.file.set(p)

    def ok(self):
        try:
            lo, hi = self.lo.get(), self.hi.get()
        except tk.TclError:
            messagebox.showwarning("Narração", "Use números de 0 a 100.", parent=self)
            return
        if not self.file.get():
            messagebox.showwarning("Narração", "Escolha um arquivo de áudio.", parent=self)
            return
        self.result = (lo, hi, Path(self.file.get()))
        self.destroy()


class VisualTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        self.searcher = Worker(self)
        self._thumb = None
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)
        self._build_bgv(nb)
        self._build_bumpers(nb)
        self._build_boot(nb)
        self._build_narrations(nb)
        self._build_soundfont(nb)
        app.jobs.listeners.append(self._update_buttons)

    # --- helpers --------------------------------------------------------------
    def _lib(self):
        return self.app.require_library()

    def _job(self, fn, label, done_msg):
        lib = self._lib()
        if lib is None:
            return
        self.app.jobs.run(lambda p, c: fn(lib, p, c), label,
                          on_done=lambda r: (self.app.jobs.set_status(done_msg), self.refresh()))

    def _quick(self, fn):
        """Small manifest edits: run now, show errors politely."""
        lib = self._lib()
        if lib is None:
            return
        try:
            fn(lib)
        except (ValueError, KeyError) as e:
            messagebox.showwarning("Visual", str(e).strip("'\""))
        self.refresh()

    def _update_buttons(self):
        state = "disabled" if self.app.jobs.busy else "normal"
        for b in self.heavy_buttons + self.heavy_buttons_extra:
            b.config(state=state)

    def refresh(self):
        lib = self.app.library
        if lib is None:
            return
        self._fill_categories(lib)
        self._fill_bumpers(lib)
        self.boot_var.set(visual.boot_video(lib) or "nenhum (o Encore usa o padrão)")
        self.narr.delete(*self.narr.get_children())
        for n in visual.narrations(lib):
            self.narr.insert("", "end", iid=f"{n['min']}-{n['max']}", values=(n["min"], n["max"], n["file"]))
        self.sf_var.set(soundfont.current_soundfont(lib) or "nenhum (o Encore usa o SoundFont padrão dele)")

    # --- background videos ------------------------------------------------------
    def _build_bgv(self, nb):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text=" Vídeos de fundo ")
        _hint(f, "Vídeos que tocam atrás da letra. No Encore, troque de categoria/vídeo com as teclas [ e ]. "
                 "Os vídeos são guardados sem áudio, em H.264 até 1080p, para o player do Encore.")
        body = ttk.Frame(f)
        body.pack(fill="both", expand=True)
        left = ttk.Frame(body)
        left.pack(side="left", fill="y")
        ttk.Label(left, text="Categorias").pack(anchor="w")
        self.cats = tk.Listbox(left, width=26, exportselection=False)
        self.cats.pack(fill="y", expand=True)
        self.cats.bind("<<ListboxSelect>>", lambda e: self._fill_videos())
        row = ttk.Frame(left)
        row.pack(fill="x", pady=4)
        ttk.Button(row, text="Nova", command=self.new_category).pack(side="left")
        ttk.Button(row, text="Renomear", command=self.rename_category).pack(side="left", padx=4)
        ttk.Button(row, text="Remover", command=self.remove_category).pack(side="left")

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True, padx=(10, 0))
        ttk.Label(right, text="Vídeos da categoria").pack(anchor="w")
        self.videos = ttk.Treeview(right, columns=("file", "size"), show="headings", selectmode="extended")
        self.videos.heading("file", text="Arquivo")
        self.videos.heading("size", text="Tamanho")
        self.videos.column("size", width=90, anchor="e", stretch=False)
        self.videos.pack(fill="both", expand=True)
        self.videos.bind("<Double-1>", lambda e: self._open_selected_video())
        row = ttk.Frame(right)
        row.pack(fill="x", pady=4)
        b1 = ttk.Button(row, text="➕ Do PC…", command=self.add_videos_pc)
        b2 = ttk.Button(row, text="➕ Do YouTube…", command=self.add_video_yt)
        b1.pack(side="left")
        b2.pack(side="left", padx=4)
        ttk.Button(row, text="Remover", command=self.remove_videos).pack(side="right")
        self.heavy_buttons = [b1, b2]

    def _fill_categories(self, lib):
        keep = self._category()
        self.categories = visual.bgv_categories(lib)
        self.cats.delete(0, "end")
        for c in self.categories:
            self.cats.insert("end", f"{c['BGV_CATEGORY']}  ({len(c.get('BGV_LIST', []))})")
        names = [c["BGV_CATEGORY"] for c in self.categories]
        if names:
            i = names.index(keep) if keep in names else 0
            self.cats.selection_set(i)
        self._fill_videos()

    def _category(self) -> str | None:
        sel = self.cats.curselection() if hasattr(self, "categories") else ()
        return self.categories[sel[0]]["BGV_CATEGORY"] if sel else None

    def _fill_videos(self):
        self.videos.delete(*self.videos.get_children())
        name, lib = self._category(), self.app.library
        if not name or lib is None:
            return
        cat = next(c for c in self.categories if c["BGV_CATEGORY"] == name)
        for v in cat.get("BGV_LIST", []):
            p = lib.path / v
            size = f"{p.stat().st_size / 1e6:.1f} MB" if p.exists() else "faltando"
            self.videos.insert("", "end", iid=v, values=(v, size))

    def new_category(self):
        name = simpledialog.askstring("Nova categoria", "Nome (aparece no Encore):", parent=self)
        if name:
            self._quick(lambda lib: visual.add_category(lib, name))

    def rename_category(self):
        old = self._category()
        if not old:
            return
        new = simpledialog.askstring("Renomear", "Novo nome:", initialvalue=old, parent=self)
        if new and new != old:
            self._quick(lambda lib: visual.rename_category(lib, old, new))

    def remove_category(self):
        name = self._category()
        if name and messagebox.askyesno("Remover", f"Remover a categoria '{name}'? Os vídeos dela vão para a Lixeira."):
            self._quick(lambda lib: visual.remove_category(lib, name))

    def add_videos_pc(self):
        name = self._category()
        if not name:
            messagebox.showinfo("Vídeos", "Crie ou escolha uma categoria primeiro.")
            return
        files = filedialog.askopenfilenames(title="Vídeos de fundo", filetypes=VIDEO_TYPES)
        if not files:
            return

        def work(lib, progress, cancel):
            for n, f in enumerate(files):
                if cancel.is_set():
                    raise Cancelled()
                progress(f"preparando {Path(f).name}", n / len(files))
                visual.add_bgv_file(lib, name, Path(f))

        self._job(work, "Adicionando vídeos de fundo…", f"✔ {len(files)} vídeo(s) em '{name}'.")

    def add_video_yt(self):
        name = self._category()
        if not name or self.searcher.busy:
            if not name:
                messagebox.showinfo("Vídeos", "Crie ou escolha uma categoria primeiro.")
            return
        q = simpledialog.askstring("YouTube", "Buscar vídeos de fundo:", initialvalue=f"{name} 4k sem narração",
                                   parent=self)
        if not q:
            return
        self.app.jobs.set_status(f"Buscando “{q}”…")
        from encolibmg import youtube

        self.searcher.run(lambda p, c: youtube.search(q, n=15), on_done=lambda vids: VideoPicker(
            self, f"Vídeo de fundo — {name}", vids, on_pick=lambda v: self._job(
                lambda lib, p, c: visual.add_bgv_video(lib, name, v, p, c),
                f"Baixando “{v.title}”…", f"✔ Vídeo adicionado a '{name}'.")),
            on_error=lambda e: messagebox.showerror("YouTube", f"Falha na busca:\n{e}"))

    def remove_videos(self):
        name, sel = self._category(), self.videos.selection()
        if name and sel and messagebox.askyesno("Remover", f"Mandar {len(sel)} vídeo(s) para a Lixeira?"):
            self._quick(lambda lib: [visual.remove_bgv(lib, name, v) for v in sel])

    def _open_selected_video(self):
        sel = self.videos.selection()
        if sel and self.app.library:
            os.startfile(self.app.library.path / sel[0])

    # --- idle images ---------------------------------------------------------------
    def _build_bumpers(self, nb):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text=" Imagens de espera ")
        _hint(f, "Imagens que o Encore mostra na tela de espera, entre as músicas (logo do karaokê, avisos, "
                 "fotos da festa…).")
        body = ttk.Frame(f)
        body.pack(fill="both", expand=True)
        left = ttk.Frame(body)
        left.pack(side="left", fill="y")
        self.bump = tk.Listbox(left, width=40, exportselection=False)
        self.bump.pack(fill="y", expand=True)
        self.bump.bind("<<ListboxSelect>>", lambda e: self._show_thumb())
        row = ttk.Frame(left)
        row.pack(fill="x", pady=4)
        ttk.Button(row, text="➕ Adicionar…", command=self.add_bumpers).pack(side="left")
        ttk.Button(row, text="Remover", command=self.remove_bumper).pack(side="left", padx=4)
        self.thumb = ttk.Label(body, text="(prévia)", anchor="center")
        self.thumb.pack(side="left", fill="both", expand=True, padx=10)

    def _fill_bumpers(self, lib):
        self.bumper_list = visual.bumpers(lib)
        self.bump.delete(0, "end")
        for b in self.bumper_list:
            self.bump.insert("end", b)
        self._show_thumb()

    def _show_thumb(self):
        sel = self.bump.curselection()
        if not sel or self.app.library is None:
            self.thumb.config(image="", text="(prévia)")
            return
        try:
            from PIL import Image, ImageTk

            img = Image.open(self.app.library.path / self.bumper_list[sel[0]])
            img.thumbnail((480, 300))
            self._thumb = ImageTk.PhotoImage(img)
            self.thumb.config(image=self._thumb, text="")
        except Exception:
            self.thumb.config(image="", text="(sem prévia)")

    def add_bumpers(self):
        files = filedialog.askopenfilenames(title="Imagens de espera", filetypes=IMAGE_TYPES)
        if files:
            self._quick(lambda lib: [visual.add_bumper(lib, Path(f)) for f in files])

    def remove_bumper(self):
        sel = self.bump.curselection()
        if sel:
            b = self.bumper_list[sel[0]]
            self._quick(lambda lib: visual.remove_bumper(lib, b))

    # --- boot video ----------------------------------------------------------------
    def _build_boot(self, nb):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text=" Vídeo de abertura ")
        _hint(f, "Vídeo que toca quando o Encore carrega esta biblioteca (uma vinheta, por exemplo). "
                 "É convertido para H.264 + AAC.")
        self.boot_var = tk.StringVar()
        ttk.Label(f, text="Atual:").pack(anchor="w")
        ttk.Label(f, textvariable=self.boot_var, font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 8))
        row = ttk.Frame(f)
        row.pack(anchor="w")
        b = ttk.Button(row, text="Escolher…", command=self.choose_boot)
        b.pack(side="left")
        ttk.Button(row, text="▶ Abrir", command=lambda: self._open(visual.boot_video)).pack(side="left", padx=4)
        ttk.Button(row, text="Remover", command=lambda: self._quick(visual.clear_boot_video)).pack(side="left")
        self.heavy_buttons_extra = [b]

    def choose_boot(self):
        f = filedialog.askopenfilename(title="Vídeo de abertura", filetypes=VIDEO_TYPES)
        if f:
            self._job(lambda lib, p, c: visual.set_boot_video(lib, Path(f)), "Convertendo vídeo de abertura…",
                      "✔ Vídeo de abertura definido.")

    def _open(self, getter):
        lib = self.app.library
        if lib and getter(lib):
            os.startfile(lib.path / getter(lib))

    # --- score narrations -----------------------------------------------------------
    def _build_narrations(self, nb):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text=" Narração da nota ")
        _hint(f, "Áudio que o Encore toca junto com a nota final, conforme a faixa da pontuação "
                 "(ex.: 0–69 'pode melhorar!', 90–100 aplausos). Sem configuração, ele usa as narrações padrão.")
        self.narr = ttk.Treeview(f, columns=("min", "max", "file"), show="headings", height=8)
        for col, text, w in [("min", "De", 60), ("max", "Até", 60), ("file", "Arquivo", 400)]:
            self.narr.heading(col, text=text)
            self.narr.column(col, width=w, stretch=col == "file")
        self.narr.pack(fill="both", expand=True)
        row = ttk.Frame(f)
        row.pack(fill="x", pady=4)
        ttk.Button(row, text="➕ Adicionar…", command=self.add_narration).pack(side="left")
        ttk.Button(row, text="▶ Ouvir", command=self.play_narration).pack(side="left", padx=4)
        ttk.Button(row, text="Remover", command=self.remove_narration).pack(side="left")

    def add_narration(self):
        if self._lib() is None:
            return
        res = NarrationDialog(self).show()
        if res:
            lo, hi, src = res
            self._quick(lambda lib: visual.set_narration(lib, lo, hi, src))

    def _narr_sel(self):
        sel = self.narr.selection()
        return tuple(int(x) for x in sel[0].split("-")) if sel else None

    def play_narration(self):
        sel = self._narr_sel()
        lib = self.app.library
        if sel and lib:
            n = next(n for n in visual.narrations(lib) if (n["min"], n["max"]) == sel)
            os.startfile(lib.path / n["file"])

    def remove_narration(self):
        sel = self._narr_sel()
        if sel:
            self._quick(lambda lib: visual.remove_narration(lib, *sel))

    # --- SoundFont --------------------------------------------------------------------
    def _build_soundfont(self, nb):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text=" SoundFont ")
        _hint(f, "Os instrumentos que o Encore usa para tocar karaokês MIDI (.kar/.mid) e a melodia do guia. "
                 "Um bom SoundFont deixa os MIDIs muito mais bonitos. O GeneralUser GS é gratuito "
                 "(licença livre, 32 MB).")
        self.sf_var = tk.StringVar()
        ttk.Label(f, text="Atual:").pack(anchor="w")
        ttk.Label(f, textvariable=self.sf_var, font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 8))
        row = ttk.Frame(f)
        row.pack(anchor="w")
        b1 = ttk.Button(row, text="⬇ Baixar GeneralUser GS", command=self.download_sf)
        b1.pack(side="left")
        ttk.Button(row, text="Escolher arquivo…", command=self.choose_sf).pack(side="left", padx=4)
        ttk.Button(row, text="Remover", command=lambda: self._quick(soundfont.remove_soundfont)).pack(side="left")
        self.heavy_buttons_extra.append(b1)

    def download_sf(self):
        self._job(lambda lib, p, c: soundfont.download_generaluser(lib, lambda f: p("baixando SoundFont", f), c),
                  "Baixando GeneralUser GS…", "✔ SoundFont GeneralUser GS instalado. Reabra a biblioteca no Encore.")

    def choose_sf(self):
        f = filedialog.askopenfilename(title="SoundFont", filetypes=SF_TYPES)
        if f:
            self._quick(lambda lib: soundfont.install_soundfont(lib, Path(f)))
