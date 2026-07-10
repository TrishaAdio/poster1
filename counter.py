"""Persistent sequential id: #1, #2, #3 ... survives restarts."""
from __future__ import annotations

import json

import config


def _read() -> int:
    if config.COUNTER_FILE.exists():
        try:
            return int(json.loads(config.COUNTER_FILE.read_text()).get("last", 0))
        except (ValueError, OSError):
            return 0
    return 0


def next_id() -> int:
    n = _read() + 1
    config.COUNTER_FILE.write_text(json.dumps({"last": n}))
    return n


def current() -> int:
    return _read()
