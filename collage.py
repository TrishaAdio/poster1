"""Build a grid collage (default 3x3 = 9 images) from image files, using PIL."""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageOps

try:
    RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:  # older Pillow
    RESAMPLE = Image.LANCZOS


def _square(img: Image.Image, size: int) -> Image.Image:
    """Center-crop to a square and resize to size x size (respects EXIF orient)."""
    img = ImageOps.exif_transpose(img)
    w, h = img.size
    m = min(w, h)
    left = (w - m) // 2
    top = (h - m) // 2
    img = img.crop((left, top, left + m, top + m))
    return img.resize((size, size), RESAMPLE)


def make_collage(paths, out_path, cell: int = 512, cols: int = 3,
                 gap: int = 6, bg=(0, 0, 0)) -> bool:
    """Combine up to len(paths) images into one grid image. Returns True on success."""
    imgs = []
    for p in paths:
        try:
            with Image.open(p) as im:
                imgs.append(_square(im.convert("RGB"), cell))
        except Exception:
            continue  # skip unreadable/corrupt images
    if not imgs:
        return False

    n = len(imgs)
    cols = max(1, min(cols, n))
    rows = math.ceil(n / cols)
    width = cols * cell + (cols + 1) * gap
    height = rows * cell + (rows + 1) * gap

    canvas = Image.new("RGB", (width, height), bg)
    for i, img in enumerate(imgs):
        r, c = divmod(i, cols)
        x = gap + c * (cell + gap)
        y = gap + r * (cell + gap)
        canvas.paste(img, (x, y))

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, "JPEG", quality=88, optimize=True)
    return True
