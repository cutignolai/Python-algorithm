import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
import json
import base64
import threading
from pathlib import Path

from renderer import render_html_to_image

TEMPLATES_DIR = Path(__file__).parent / "templates"
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

BG_DARK    = "#12121f"
BG_SIDEBAR = "#1a1a2e"
BG_INPUT   = "#1e1e32"
ACCENT     = "#6c63ff"
TEXT_MAIN  = "#ffffff"
TEXT_DIM   = "#888888"
TEXT_MID   = "#bbbbbb"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("HTML Image Generator")
        self.geometry("1050x700")
        self.minsize(800, 560)
        self.configure(bg=BG_DARK)

        self.templates: list[dict] = _load_templates()
        self.selected: dict | None = None
        self.field_widgets: dict = {}
        self.image_paths: dict = {}

        _configure_styles()
        self._build_ui()

    def _build_ui(self):
        # ── Sidebar ──────────────────────────────────────────────────────
        sidebar = tk.Frame(self, bg=BG_SIDEBAR, width=230)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        header = tk.Frame(sidebar, bg=ACCENT, height=52)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="Templates", bg=ACCENT, fg=TEXT_MAIN,
                 font=("Segoe UI", 13, "bold")).pack(expand=True)

        self.listbox = tk.Listbox(
            sidebar, bg=BG_SIDEBAR, fg=TEXT_MID,
            selectbackground=ACCENT, selectforeground=TEXT_MAIN,
            font=("Segoe UI", 11), relief=tk.FLAT, bd=0,
            activestyle="none", cursor="hand2",
        )
        self.listbox.pack(fill=tk.BOTH, expand=True, pady=6)
        for t in self.templates:
            self.listbox.insert(tk.END, f"  {t['name']}")
        self.listbox.bind("<<ListboxSelect>>", self._on_select)

        # ── Main area ─────────────────────────────────────────────────────
        main = tk.Frame(self, bg=BG_DARK)
        main.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Scrollable editor
        self.canvas = tk.Canvas(main, bg=BG_DARK, highlightthickness=0)
        vscroll = ttk.Scrollbar(main, orient="vertical", command=self.canvas.yview)
        self.scroll_frame = tk.Frame(self.canvas, bg=BG_DARK)

        self.scroll_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self._cw = self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=vscroll.set)
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self._cw, width=e.width)
        )
        self.canvas.bind_all("<MouseWheel>", self._mousewheel)
        self.canvas.bind_all("<Button-4>",   lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind_all("<Button-5>",   lambda e: self.canvas.yview_scroll(1,  "units"))

        # Bottom bar
        bottom = tk.Frame(main, bg=BG_SIDEBAR, height=58)
        bottom.pack(side=tk.BOTTOM, fill=tk.X)
        bottom.pack_propagate(False)

        self.status_var = tk.StringVar(value="Selecciona un template para comenzar")
        tk.Label(bottom, textvariable=self.status_var,
                 bg=BG_SIDEBAR, fg=TEXT_DIM, font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=16)

        self.fmt_var = tk.StringVar(value="png")
        fmt_frame = tk.Frame(bottom, bg=BG_SIDEBAR)
        fmt_frame.pack(side=tk.RIGHT, padx=(0, 8))
        tk.Label(fmt_frame, text="Formato:", bg=BG_SIDEBAR, fg=TEXT_DIM,
                 font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=4)
        for fmt in ("png", "jpg"):
            tk.Radiobutton(
                fmt_frame, text=fmt.upper(), variable=self.fmt_var, value=fmt,
                bg=BG_SIDEBAR, fg=TEXT_DIM, selectcolor=BG_SIDEBAR,
                activebackground=BG_SIDEBAR, activeforeground=TEXT_MID,
                font=("Segoe UI", 9),
            ).pack(side=tk.LEFT)

        self.gen_btn = tk.Button(
            bottom, text="⚡  Generar Imagen",
            bg=ACCENT, fg=TEXT_MAIN, font=("Segoe UI", 11, "bold"),
            padx=20, pady=6, relief=tk.FLAT, cursor="hand2",
            state=tk.DISABLED, command=self._generate,
            activebackground="#8a84ff", activeforeground=TEXT_MAIN,
        )
        self.gen_btn.pack(side=tk.RIGHT, padx=16, pady=10)

        vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self._show_placeholder()

    # ── Events ────────────────────────────────────────────────────────────

    def _mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_select(self, event):
        sel = self.listbox.curselection()
        if not sel:
            return
        self.selected = self.templates[sel[0]]
        self._build_editor()
        self.gen_btn.config(state=tk.NORMAL)

    # ── Editor ────────────────────────────────────────────────────────────

    def _show_placeholder(self):
        for w in self.scroll_frame.winfo_children():
            w.destroy()
        tk.Label(
            self.scroll_frame,
            text="← Selecciona un template para comenzar",
            bg=BG_DARK, fg="#444", font=("Segoe UI", 14),
        ).pack(expand=True, pady=120)

    def _build_editor(self):
        for w in self.scroll_frame.winfo_children():
            w.destroy()
        self.field_widgets = {}
        self.image_paths = {}
        self.canvas.yview_moveto(0)

        t = self.selected
        pad = tk.Frame(self.scroll_frame, bg=BG_DARK)
        pad.pack(fill=tk.BOTH, expand=True, padx=32, pady=28)

        tk.Label(pad, text=t["name"], bg=BG_DARK, fg=TEXT_MAIN,
                 font=("Segoe UI", 17, "bold")).pack(anchor="w")
        tk.Label(pad, text=t.get("description", ""), bg=BG_DARK, fg=TEXT_DIM,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(3, 20))

        tk.Frame(pad, bg="#2a2a40", height=1).pack(fill=tk.X, pady=(0, 16))

        size_lbl = f"Tamaño: {t.get('width', '?')} × {t.get('height', '?')} px"
        tk.Label(pad, text=size_lbl, bg=BG_DARK, fg="#555",
                 font=("Segoe UI", 8)).pack(anchor="w", pady=(0, 18))

        for field in t.get("fields", []):
            self._add_field(pad, field)

        tk.Frame(pad, bg=BG_DARK, height=20).pack()

    def _add_field(self, parent, field):
        fid   = field["id"]
        ftype = field.get("type", "text")
        dflt  = field.get("default", "")

        row = tk.Frame(parent, bg=BG_DARK)
        row.pack(fill=tk.X, pady=9)

        tk.Label(row, text=field["label"], bg=BG_DARK, fg=TEXT_MID,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 5))

        if ftype == "text":
            var = tk.StringVar(value=dflt)
            self.field_widgets[fid] = var
            e = tk.Entry(row, textvariable=var, bg=BG_INPUT, fg=TEXT_MAIN,
                         insertbackground=TEXT_MAIN, font=("Segoe UI", 11),
                         relief=tk.FLAT, bd=0)
            e.pack(fill=tk.X, ipady=8, ipadx=10)
            tk.Frame(row, bg=ACCENT, height=1).pack(fill=tk.X)

        elif ftype == "textarea":
            txt = tk.Text(row, height=4, bg=BG_INPUT, fg=TEXT_MAIN,
                          insertbackground=TEXT_MAIN, font=("Segoe UI", 11),
                          relief=tk.FLAT, bd=0, padx=10, pady=8, wrap=tk.WORD)
            txt.insert("1.0", dflt)
            txt.pack(fill=tk.X)
            tk.Frame(row, bg=ACCENT, height=1).pack(fill=tk.X)
            self.field_widgets[fid] = txt

        elif ftype == "color":
            var = tk.StringVar(value=dflt)
            self.field_widgets[fid] = var

            cf = tk.Frame(row, bg=BG_DARK)
            cf.pack(fill=tk.X)

            e = tk.Entry(cf, textvariable=var, bg=BG_INPUT, fg=TEXT_MAIN,
                         insertbackground=TEXT_MAIN, font=("Segoe UI", 11),
                         relief=tk.FLAT, bd=0, width=14)
            e.pack(side=tk.LEFT, ipady=8, ipadx=10)

            swatch = tk.Button(cf, bg=dflt, width=4, relief=tk.FLAT,
                               cursor="hand2", bd=0)
            swatch.pack(side=tk.LEFT, padx=8, ipady=4)
            swatch.config(command=lambda v=var, b=swatch: self._pick_color(v, b))

            var.trace_add("write", lambda *a, v=var, b=swatch: _safe_swatch(v, b))
            tk.Frame(row, bg=ACCENT, height=1).pack(fill=tk.X)

        elif ftype == "image":
            pvar = tk.StringVar(value="")
            self.image_paths[fid] = pvar

            img_row = tk.Frame(row, bg=BG_INPUT)
            img_row.pack(fill=tk.X)

            lbl = tk.Label(img_row, text="Sin imagen seleccionada",
                           bg=BG_INPUT, fg="#555", font=("Segoe UI", 10),
                           anchor="w")
            lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10, pady=7)

            tk.Button(img_row, text="Buscar...", bg="#2a2a48", fg=TEXT_MID,
                      font=("Segoe UI", 9), relief=tk.FLAT, cursor="hand2", bd=0,
                      command=lambda v=pvar, l=lbl: self._pick_image(v, l),
                      ).pack(side=tk.RIGHT, padx=6, pady=5)

            tk.Frame(row, bg=ACCENT, height=1).pack(fill=tk.X)

    # ── Pickers ───────────────────────────────────────────────────────────

    def _pick_color(self, var: tk.StringVar, btn: tk.Button):
        current = var.get()
        result = colorchooser.askcolor(
            color=current if _valid_color(self, current) else "#ffffff",
            title="Elegir color",
        )
        if result[1]:
            var.set(result[1])
            btn.config(bg=result[1])

    def _pick_image(self, var: tk.StringVar, label: tk.Label):
        path = filedialog.askopenfilename(
            title="Seleccionar imagen",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.gif *.webp *.bmp *.svg")],
        )
        if path:
            var.set(path)
            label.config(text=Path(path).name, fg=TEXT_MID)

    # ── Generate ──────────────────────────────────────────────────────────

    def _collect_values(self) -> dict:
        values = {}
        for field in self.selected.get("fields", []):
            fid   = field["id"]
            ftype = field.get("type", "text")

            if ftype == "image":
                path = self.image_paths.get(fid, tk.StringVar()).get()
                if path and Path(path).exists():
                    data = Path(path).read_bytes()
                    b64  = base64.b64encode(data).decode()
                    ext  = Path(path).suffix.lower().lstrip(".")
                    if ext in ("jpg", "jpeg"):
                        ext = "jpeg"
                    elif ext == "svg":
                        ext = "svg+xml"
                    values[fid] = f"data:image/{ext};base64,{b64}"
                else:
                    values[fid] = field.get("default", "")

            elif ftype == "textarea":
                widget = self.field_widgets.get(fid)
                values[fid] = widget.get("1.0", tk.END).strip() if widget else field.get("default", "")

            else:
                widget = self.field_widgets.get(fid)
                values[fid] = widget.get() if widget else field.get("default", "")

        return values

    def _generate(self):
        t         = self.selected
        html_path = t["_path"] / "template.html"

        if not html_path.exists():
            messagebox.showerror("Error", f"No se encontró template.html en:\n{t['_path']}")
            return

        fmt          = self.fmt_var.get()
        default_name = f"{t.get('id', 'output')}_output.{fmt}"
        save_path    = filedialog.asksaveasfilename(
            title="Guardar imagen como",
            defaultextension=f".{fmt}",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg *.jpeg"), ("Todos", "*.*")],
            initialfile=default_name,
            initialdir=str(OUTPUT_DIR),
        )
        if not save_path:
            return

        values = self._collect_values()
        self.gen_btn.config(state=tk.DISABLED, text="Generando…")
        self.status_var.set("Renderizando con Playwright…")

        def worker():
            try:
                html    = html_path.read_text(encoding="utf-8")
                width   = t.get("width", 1200)
                height  = t.get("height", 630)
                render_html_to_image(html, values, save_path, width, height)
                self.after(0, lambda: self._done(save_path))
            except Exception as exc:
                self.after(0, lambda: self._error(str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _done(self, path: str):
        self.gen_btn.config(state=tk.NORMAL, text="⚡  Generar Imagen")
        self.status_var.set(f"✓  Guardado: {Path(path).name}")
        messagebox.showinfo("¡Listo!", f"Imagen guardada en:\n{path}")

    def _error(self, msg: str):
        self.gen_btn.config(state=tk.NORMAL, text="⚡  Generar Imagen")
        self.status_var.set("✗  Error al generar")
        messagebox.showerror("Error al generar", f"{msg}")


# ── Helpers ───────────────────────────────────────────────────────────────


def _load_templates() -> list[dict]:
    templates = []
    if TEMPLATES_DIR.exists():
        for folder in sorted(TEMPLATES_DIR.iterdir()):
            if folder.is_dir():
                cfg_path = folder / "config.json"
                if cfg_path.exists():
                    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
                    cfg["_path"] = folder
                    templates.append(cfg)
    return templates


def _configure_styles():
    style = ttk.Style()
    style.theme_use("default")
    style.configure(
        "Vertical.TScrollbar",
        background=BG_SIDEBAR,
        troughcolor=BG_DARK,
        bordercolor=BG_DARK,
        arrowcolor="#444",
        relief=tk.FLAT,
    )


def _valid_color(widget: tk.Widget, color: str) -> bool:
    try:
        widget.winfo_rgb(color)
        return True
    except tk.TclError:
        return False


def _safe_swatch(var: tk.StringVar, btn: tk.Button):
    try:
        color = var.get()
        btn.winfo_rgb(color)
        btn.config(bg=color)
    except tk.TclError:
        pass


if __name__ == "__main__":
    app = App()
    app.mainloop()
