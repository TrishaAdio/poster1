"""Video helpers via ffmpeg/ffprobe: thumbnail extraction + metadata.

Some videos have no embedded cover, so Telegram shows a black square. We grab a
representative (non-black) frame with ffmpeg's `thumbnail` filter and attach it,
plus real duration/size so the video shows a proper preview and seek bar.

All functions degrade gracefully to None/False if ffmpeg isn't installed.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess

HAVE_FFMPEG = shutil.which("ffmpeg") is not None
HAVE_FFPROBE = shutil.which("ffprobe") is not None


def make_thumbnail(video_path: str, out_path: str) -> bool:
    """Extract a representative frame to out_path (JPEG, <=320px). True on success."""
    if not HAVE_FFMPEG:
        return False
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", video_path,
             "-vf", "thumbnail,scale=320:-2", "-frames:v", "1", out_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=120, check=True,
        )
        return os.path.exists(out_path) and os.path.getsize(out_path) > 0
    except Exception:
        return False


def probe(video_path: str) -> dict | None:
    """Return {'w','h','duration'} (ints) for the video, or None."""
    if not HAVE_FFPROBE:
        return None
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height:format=duration",
             "-of", "json", video_path],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=60, check=True,
        ).stdout
        data = json.loads(out or b"{}")
        stream = (data.get("streams") or [{}])[0]
        duration = float((data.get("format") or {}).get("duration") or 0)
        return {
            "w": int(stream.get("width") or 0),
            "h": int(stream.get("height") or 0),
            "duration": int(duration),
        }
    except Exception:
        return None
