import queue
import threading
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk
from tkinterdnd2 import DND_FILES, TkinterDnD

from app import config
from app.converter import FORMATS, PRESETS, VIDEO_EXTS, Cancelled, Converter, is_video


class App(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        self.TkdndVersion = TkinterDnD._require(self)
        self.title("Format Convert")
        self.geometry("720x560")
        self.minsize(620, 480)

        self.cfg = config.load()
        self.converter = Converter()
        self.events = queue.Queue()
        self.rows = {}  # chemin -> (label statut, barre)
        self.worker = None

        self._build()
        self.after(100, self._poll)
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        drop = ctk.CTkLabel(self, text="Dépose tes vidéos ici ou clique pour ajouter", height=90,
                            fg_color=("gray85", "gray20"), corner_radius=8)
        drop.grid(row=0, column=0, padx=16, pady=(16, 8), sticky="ew")
        drop.bind("<Button-1>", lambda e: self._browse_files())
        drop.drop_target_register(DND_FILES)
        drop.dnd_bind("<<Drop>>", self._on_drop)

        self.list = ctk.CTkScrollableFrame(self)
        self.list.grid(row=1, column=0, padx=16, pady=8, sticky="nsew")
        self.list.grid_columnconfigure(0, weight=1)

        opts = ctk.CTkFrame(self, fg_color="transparent")
        opts.grid(row=2, column=0, padx=16, pady=4, sticky="ew")
        opts.grid_columnconfigure(3, weight=1)
        self.fmt = ctk.CTkSegmentedButton(opts, values=[f.upper() for f in FORMATS])
        self.fmt.set(self.cfg["format"].upper())
        self.fmt.grid(row=0, column=0, padx=(0, 12))
        self.preset = ctk.CTkOptionMenu(opts, values=[f"{k} ({v[0]} kbps)" for k, v in PRESETS.items()])
        self.preset.set(self._preset_label(self.cfg["preset"]))
        self.preset.grid(row=0, column=1)
        ctk.CTkButton(opts, text="Vider la liste", width=110, fg_color="gray40",
                      command=self._clear).grid(row=0, column=4, sticky="e")

        out = ctk.CTkFrame(self, fg_color="transparent")
        out.grid(row=3, column=0, padx=16, pady=4, sticky="ew")
        out.grid_columnconfigure(0, weight=1)
        self.out_var = ctk.StringVar(value=self.cfg["output_dir"])
        ctk.CTkEntry(out, textvariable=self.out_var).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkButton(out, text="Parcourir", width=100, command=self._browse_out).grid(row=0, column=1)

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=4, column=0, padx=16, pady=(8, 16), sticky="ew")
        bottom.grid_columnconfigure(0, weight=1)
        self.total_bar = ctk.CTkProgressBar(bottom)
        self.total_bar.set(0)
        self.total_bar.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.go = ctk.CTkButton(bottom, text="Convertir", width=110, command=self._start)
        self.go.grid(row=0, column=1, padx=(0, 8))
        self.cancel = ctk.CTkButton(bottom, text="Annuler", width=90, fg_color="gray40",
                                    state="disabled", command=self.converter.cancel)
        self.cancel.grid(row=0, column=2)

    @staticmethod
    def _preset_label(name):
        name = name if name in PRESETS else "Standard"
        return f"{name} ({PRESETS[name][0]} kbps)"

    def _on_drop(self, event):
        self._add(self.tk.splitlist(event.data))

    def _browse_files(self):
        exts = " ".join(f"*{e}" for e in VIDEO_EXTS)
        self._add(filedialog.askopenfilenames(filetypes=[("Vidéos", exts), ("Tous", "*.*")]))

    def _browse_out(self):
        d = filedialog.askdirectory(initialdir=self.out_var.get())
        if d:
            self.out_var.set(d)

    def _add(self, paths):
        for p in paths:
            if p in self.rows or not is_video(p):
                continue
            row = ctk.CTkFrame(self.list, fg_color="transparent")
            row.grid(sticky="ew", pady=2)
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(row, text=Path(p).name, anchor="w").grid(row=0, column=0, sticky="ew")
            status = ctk.CTkLabel(row, text="En attente", width=90, anchor="e")
            status.grid(row=0, column=1)
            bar = ctk.CTkProgressBar(row, height=6)
            bar.set(0)
            bar.grid(row=1, column=0, columnspan=2, sticky="ew")
            self.rows[p] = (row, status, bar)

    def _clear(self):
        if self.worker and self.worker.is_alive():
            return
        for row, _, _ in self.rows.values():
            row.destroy()
        self.rows.clear()
        self.total_bar.set(0)

    def _start(self):
        if not self.rows or (self.worker and self.worker.is_alive()):
            return
        fmt = self.fmt.get().lower()
        preset = self.preset.get().split(" ")[0]
        out_dir = Path(self.out_var.get())
        self.cfg.update(output_dir=str(out_dir), format=fmt, preset=preset)
        config.save(self.cfg)
        self.converter.reset()
        self.go.configure(state="disabled")
        self.cancel.configure(state="normal")
        files = list(self.rows)
        self.worker = threading.Thread(target=self._run, args=(files, out_dir, fmt, preset), daemon=True)
        self.worker.start()

    def _run(self, files, out_dir, fmt, preset):
        n = len(files)
        for i, p in enumerate(files):
            self.events.put(("status", p, "En cours", i, n))
            try:
                self.converter.convert(Path(p), out_dir, fmt, preset,
                                       lambda f, p=p, i=i: self.events.put(("progress", p, f, i, n)))
                self.events.put(("status", p, "Terminé", i + 1, n))
            except Cancelled:
                self.events.put(("status", p, "Annulé", i, n))
                break
            except Exception as e:
                self.events.put(("status", p, f"Erreur: {e}"[:60], i + 1, n))
        self.events.put(("done",))

    def _poll(self):
        try:
            while True:
                ev = self.events.get_nowait()
                if ev[0] == "done":
                    self.go.configure(state="normal")
                    self.cancel.configure(state="disabled")
                    continue
                kind, p, val, i, n = ev
                _, status, bar = self.rows[p]
                if kind == "status":
                    status.configure(text=val)
                    if val == "Terminé":
                        bar.set(1)
                    self.total_bar.set(i / n)
                else:
                    bar.set(val)
                    self.total_bar.set((i + val) / n)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _close(self):
        self.converter.cancel()
        self.destroy()
