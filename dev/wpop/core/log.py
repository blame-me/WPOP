"""Audit log. Every applied / undone fix is appended to a JSONL file so the
history and the resulting system changes are fully traceable."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

_LOG_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "wpop", "logs"
)


class AuditLog:
    def __init__(self, path: Optional[str] = None) -> None:
        if path is None:
            os.makedirs(_LOG_DIR, exist_ok=True)
            path = os.path.join(_LOG_DIR, "audit.jsonl")
        self.path = path

    def write(self, entry: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        entry.setdefault("ts", datetime.now(timezone.utc).isoformat())
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=True) + "\n")

    def applied(self, keys: list[str], description: str, risk: str) -> None:
        self.write({"event": "applied", "keys": keys, "description": description, "risk": risk})

    def undone(self, keys: list[str], description: str) -> None:
        self.write({"event": "undone", "keys": keys, "description": description})


def current_unix() -> float:
    return time.time()