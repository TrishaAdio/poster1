"""Scan an extracted folder for images and videos, sorted naturally."""
from __future__ import annotations

import re
from pathlib import Path

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff", ".heic"}
VIDEO_EXT = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".flv", ".3gp",
             ".mpg", ".mpeg", ".ts", ".wmv"}

# Junk that some archives include; ignore it.
_SKIP_PARTS = {"__MACOSX"}
_SKIP_NAMES = {".DS_Store", "Thumbs.db"}


def _natural_key(name: str):
    """'img2' < 'img10' ordering."""
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", name)]


def scan(root) -> tuple[list[Path], list[Path]]:
    """Return (images, videos) as sorted lists of Paths."""
    images, videos = [], []
    for p in Path(root).rglob("*"):
        if not p.is_file():
            continue
        if any(part in _SKIP_PARTS for part in p.parts) or p.name in _SKIP_NAMES:
            continue
        ext = p.suffix.lower()
        if ext in IMAGE_EXT:
            images.append(p)
        elif ext in VIDEO_EXT:
            videos.append(p)
    images.sort(key=lambda p: _natural_key(str(p.relative_to(root))))
    videos.sort(key=lambda p: _natural_key(str(p.relative_to(root))))
    return images, videos


def chunk(items: list, size: int):
    """Yield successive `size`-length chunks."""
    for i in range(0, len(items), size):
        yield items[i:i + size]
