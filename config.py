"""Central config for the ZIP -> channel userbot. Reads .env (see .env.example)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- Credentials ----------------------------------------------------------
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")

# --- Destination + access -------------------------------------------------
POST_CHANNEL_RAW = os.getenv("POST_CHANNEL", "")
OWNERS = [
    int(x) for x in os.getenv("OWNERS", "").replace(" ", "").split(",")
    if x.strip().lstrip("-").isdigit()
]

# --- Album / pacing -------------------------------------------------------
# Images per native Telegram album. Telegram allows at most 10 per group.
ALBUM_SIZE = max(1, min(int(os.getenv("ALBUM_SIZE", "9")), 10))
SEND_DELAY = float(os.getenv("SEND_DELAY", "2"))

# --- Paths ----------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
WORK_DIR = BASE_DIR / "work"
WORK_DIR.mkdir(exist_ok=True)
COUNTER_FILE = DATA_DIR / "counter.json"
SESSION = str(BASE_DIR / "userbot")


def post_channel():
    """POST_CHANNEL as an int id when numeric, else the raw string."""
    s = POST_CHANNEL_RAW.strip()
    if not s:
        return s
    body = s[1:] if s.startswith("-") else s
    return int(s) if body.isdigit() else s


def require(*names: str) -> None:
    missing = [n for n in names if not globals().get(n)]
    if missing:
        raise SystemExit(
            "Missing config: " + ", ".join(missing) + "\nRun:  python setup.py"
        )
