"""
Coverflow-style template carousel.

Layout: smaller items on sides, selected item large and centered.
Navigation: arrow buttons, left/right keys, click on side items.
Animation: smooth eased interpolation at 30 fps.
"""
import tkinter as tk
from typing import Callable

from PIL import Image, ImageEnhance, ImageTk

from frontend.thumbnail import load_or_generate

_BG     = "#12121f"
_ACCENT = "#6c63ff"

# (abs_distance_from_center, scale, brightness)
# More entries → smoother visual transition between positions
_CURVE = [
    (0.00, 1.000, 1.00),
    (0.15, 0.975, 0.98),
    (0.30, 0.935, 0.94),
    (0.50, 0.870, 0.86),
    (0.70, 0.795, 0.76),
    (0.90, 0.720, 0.66),
    (1.10, 0.648, 0.56),
    (1.30, 0.582, 0.47),
    (1.50, 0.522, 0.39),
    (1.70, 0.468, 0.32),
    (1.90, 0.420, 0.26),
    (2.10, 0.378, 0.20),
    (2.35, 0.335, 0.15),
    (2.60, 0.300, 0.11),
]
_MAX_DIST = 2.7


class TemplateCarousel(tk.Frame):
    CENTER_W = 272   # width  of center card in px
    CENTER_H = 192   # max height of center card in px
    SPACING  = 208   # distance between item centers (allows overlap on sides)
    FPS      = 30
    EASE     = 0.22  # interpolation factor per tick (higher = snappier)

    def __init__(
        self,
        parent: tk.Widget,
        templates: list[dict],
        on_select: Callable[[dict], None],
        **kwargs,
    ):
        bg = kwargs.pop("bg", _BG)
        super().__init__(parent, bg=bg, **kwargs)

        self.templates = templates
        self.on_select = on_select
        self.position  = 0.0   # current animated float position
        self.target    = 0     # target integer index
        self._anim_id  = None

        # {(tmpl_idx, level_idx): ImageTk.PhotoImage}
        self._photos: dict = {}
        # {tmpl_idx: (rendered_w, rendered_h)}
        self._src_sz: dict = {}

        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Arrow overlays positioned via place() after first Configure
        _akw = dict(bg=bg, fg="#2e2e50", font=("Segoe UI", 40, "bold"),
                    cursor="hand2", bd=0)
        self._larr = tk.Label(self, text="❮", **_akw)
        self._rarr = tk.Label(self, text="❯", **_akw)
        for btn, d in ((self._larr, -1), (self._rarr, +1)):
            btn.bind("<Button-1>", lambda e, _d=d: self.go(_d))
            btn.bind("<Enter>",    lambda e, b=btn: b.config(fg=_ACCENT))
            btn.bind("<Leave>",    lambda e, b=btn: b.config(fg="#2e2e50"))

        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Button-1>",  self._on_click)
        self.bind_all("<Left>",  lambda e: self._safe_go(-1))
        self.bind_all("<Right>", lambda e: self._safe_go(+1))

        # Pre-generate all thumbnail PhotoImages (done in main thread, fast)
        self._pregenerate()

        if templates:
            on_select(templates[0])

    # ── Startup ───────────────────────────────────────────────────────────────

    def _pregenerate(self):
        """
        For each template × each curve level, create a pre-scaled and
        pre-dimmed ImageTk.PhotoImage. Stored in self._photos.
        This avoids any PIL work during the animation loop.
        """
        for idx, t in enumerate(self.templates):
            tw, th = t.get("width", 1200), t.get("height", 630)
            ratio  = tw / th if th else 1.75
            src_w  = self.CENTER_W
            src_h  = min(self.CENTER_H, int(src_w / ratio))
            self._src_sz[idx] = (src_w, src_h)

            src = load_or_generate(t, src_w, src_h)

            for li, (_, scale, brightness) in enumerate(_CURVE):
                w = max(4, int(src_w * scale))
                h = max(3, int(src_h * scale))
                img = src.resize((w, h), Image.LANCZOS)
                if brightness < 0.985:
                    img = ImageEnhance.Brightness(img).enhance(brightness)
                self._photos[(idx, li)] = ImageTk.PhotoImage(img)

        self.after(20, self._draw)

    # ── Public API ────────────────────────────────────────────────────────────

    def go(self, direction: int):
        if not self.templates:
            return
        self.target = (self.target + direction) % len(self.templates)
        self.on_select(self.templates[self.target])
        self._start_anim()

    def _safe_go(self, direction: int):
        """Navigate only when the focused widget is not a text input."""
        focused = self.focus_get()
        if isinstance(focused, (tk.Entry, tk.Text)):
            return
        self.go(direction)

    # ── Animation ─────────────────────────────────────────────────────────────

    def _start_anim(self):
        if self._anim_id:
            self.after_cancel(self._anim_id)
        self._tick()

    def _tick(self):
        n    = len(self.templates)
        diff = self.target - self.position
        # Take the shortest path around the wheel
        while diff >  n / 2: diff -= n
        while diff < -n / 2: diff += n

        if abs(diff) < 0.006:
            self.position = float(self.target)
            self._draw()
            self._anim_id = None
            return

        self.position += diff * self.EASE
        self._draw()
        self._anim_id = self.after(1000 // self.FPS, self._tick)

    # ── Events ────────────────────────────────────────────────────────────────

    def _on_resize(self, event):
        cw, ch = event.width, event.height
        self._larr.place(x=18,      y=ch // 2 - 30)
        self._rarr.place(x=cw - 38, y=ch // 2 - 30)
        self._draw()

    def _on_click(self, event):
        cx   = self.canvas.winfo_width() // 2
        dead = self.CENTER_W // 2  # dead zone = center card width
        if event.x < cx - dead:
            self.go(-1)
        elif event.x > cx + dead:
            self.go(+1)

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _dist(self, idx: int) -> float:
        """Signed distance from current animated position, shortest-path wrapped."""
        n = len(self.templates)
        d = idx - self.position
        while d >  n / 2: d -= n
        while d < -n / 2: d += n
        return d

    def _level(self, abs_dist: float) -> int:
        """Map a continuous abs distance to the nearest pre-generated level index."""
        best, best_diff = 0, float("inf")
        for li, (d_ref, _, _) in enumerate(_CURVE):
            diff = abs(d_ref - abs_dist)
            if diff < best_diff:
                best, best_diff = li, diff
        return best

    def _draw(self):
        c = self.canvas
        c.delete("all")
        cw, ch = c.winfo_width(), c.winfo_height()
        if cw <= 1 or ch <= 1 or not self.templates:
            return

        cx = cw // 2
        # Vertical center shifted up slightly to leave room for name + dots below
        cy = (ch - 56) // 2 + 8

        n = len(self.templates)

        # Draw farthest items first so closer ones paint over them
        draw_order = sorted(range(n), key=lambda i: -abs(self._dist(i)))

        for idx in draw_order:
            dist  = self._dist(idx)
            abs_d = abs(dist)
            if abs_d > _MAX_DIST:
                continue

            photo = self._photos.get((idx, self._level(abs_d)))
            if photo is None:
                continue

            x = cx + int(dist * self.SPACING)
            c.create_image(x, cy, image=photo, anchor="center")

            # Accent border only on the exact center card
            if abs_d < 0.09:
                sw, sh = self._src_sz.get(idx, (self.CENTER_W, self.CENTER_H))
                pad = 3
                c.create_rectangle(
                    x - sw//2 - pad, cy - sh//2 - pad,
                    x + sw//2 + pad, cy + sh//2 + pad,
                    outline=_ACCENT, width=2,
                )

        # ── Template name + description centered below ─────────────────────
        t      = self.templates[self.target]
        _, sh  = self._src_sz.get(self.target, (self.CENTER_W, self.CENTER_H))
        name_y = cy + sh // 2 + 18

        c.create_text(cx, name_y,
                      text=t["name"],
                      fill="white", font=("Segoe UI", 11, "bold"))
        c.create_text(cx, name_y + 20,
                      text=t.get("description", ""),
                      fill="#4a4a6a", font=("Segoe UI", 8))

        # ── Navigation dots ────────────────────────────────────────────────
        dot_y    = ch - 10
        dot_step = 15
        total_w  = (n - 1) * dot_step
        for i in range(n):
            dx  = cx - total_w // 2 + i * dot_step
            sel = (i == self.target)
            r   = 4 if sel else 3
            c.create_oval(dx - r, dot_y - r, dx + r, dot_y + r,
                          fill=_ACCENT if sel else "#252540", outline="")
