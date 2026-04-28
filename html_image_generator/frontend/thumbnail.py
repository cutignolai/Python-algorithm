"""
Generates PIL placeholder thumbnails for each template.
If a template folder contains preview.png, that file is used instead.
"""
from pathlib import Path
from PIL import Image, ImageDraw


def load_or_generate(template: dict, width: int, height: int) -> Image.Image:
    preview = template["_path"] / "preview.png"
    if preview.exists():
        try:
            img = Image.open(preview).convert("RGB")
            img.thumbnail((width, height), Image.LANCZOS)
            return img
        except Exception:
            pass
    return _generate(template, width, height)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hex(hex_str: str) -> tuple:
    s = hex_str.strip().lstrip("#")
    if len(s) == 3:
        s = s[0]*2 + s[1]*2 + s[2]*2
    try:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except (ValueError, IndexError):
        return (18, 18, 31)


def _light(c: tuple, n: int) -> tuple:
    return tuple(min(255, x + n) for x in c)


def _dark(c: tuple, n: int) -> tuple:
    return tuple(max(0, x - n) for x in c)


# ── Generator ─────────────────────────────────────────────────────────────────

def _generate(template: dict, width: int, height: int) -> Image.Image:
    fields = {f["id"]: f.get("default", "") for f in template.get("fields", [])}
    bg  = _hex(fields.get("bg_color",     "#12121f"))
    acc = _hex(fields.get("accent_color",  "#6c63ff"))

    # Work at 2× for antialiasing, downsample at end
    W, H = width * 2, height * 2
    img  = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)

    # Soft background blob (top-right)
    r = int(H * 0.95)
    draw.ellipse([W - r//2, -r//3, W + r//3, r], fill=_light(bg, 16))

    # Top accent bar
    bar = max(6, H // 9)
    draw.rectangle([0, 0, W, bar], fill=acc)

    # Left vertical accent strip
    strip = max(4, W // 16)
    draw.rectangle([0, bar, strip, H], fill=_dark(acc, 28))

    # Content lines (simulate template body)
    x0 = strip + W // 7
    specs = [(0.64, 88), (0.45, 55), (0.32, 36)]
    for i, (frac, delta) in enumerate(specs):
        y  = bar + int(H * 0.22) + i * int(H * 0.185)
        lw = int(W * frac)
        lh = max(3, H // 17)
        draw.rounded_rectangle([x0, y, x0 + lw, y + lh],
                               radius=lh // 2, fill=_light(bg, delta))

    # Small accent circle (bottom-right detail)
    cr = H // 5
    draw.ellipse([W - cr - 8, H - cr - 8, W - 8, H - 8],
                 outline=acc, width=max(2, W // 50))

    return img.resize((width, height), Image.LANCZOS)
