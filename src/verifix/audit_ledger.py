"""Append-only, hash-chained audit ledger (tamper-evident record of agent decisions).

Each entry stores ``prev`` (the previous entry's hash) and ``hash = sha256(prev || canonical_json(body))``.
Editing, deleting or reordering any entry breaks every later link, and ``verify`` reports the first
broken index. The head hash can be published (e.g. in a release note) as a checkpoint, so that even
a rewrite of the whole file is detectable against it.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GENESIS = "0" * 64
_LOCK = threading.Lock()


def _canonical(body: dict[str, Any]) -> bytes:
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def entry_hash(prev: str, body: dict[str, Any]) -> str:
    return hashlib.sha256(prev.encode("ascii") + _canonical(body)).hexdigest()


class AuditLedger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def entries(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(l) for l in self.path.read_text(encoding="utf-8").splitlines() if l.strip()]

    def head(self) -> str:
        e = self.entries()
        return e[-1]["hash"] if e else GENESIS

    def append(self, event: str, data: dict[str, Any]) -> dict[str, Any]:
        with _LOCK:
            prev = self.head()
            body = {"seq": len(self.entries()), "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                    "event": event, "data": data}
            rec = {**body, "prev": prev, "hash": entry_hash(prev, body)}
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, sort_keys=True, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
            return rec

    def verify(self, expected_head: str | None = None) -> dict[str, Any]:
        prev = GENESIS
        entries = self.entries()
        for i, rec in enumerate(entries):
            body = {k: rec[k] for k in ("seq", "ts", "event", "data") if k in rec}
            if rec.get("prev") != prev or rec.get("seq") != i or entry_hash(prev, body) != rec.get("hash"):
                return {"ok": False, "entries": len(entries), "first_broken": i}
            prev = rec["hash"]
        if expected_head and prev != expected_head:
            return {"ok": False, "entries": len(entries), "first_broken": None, "reason": "head does not match published checkpoint"}
        return {"ok": True, "entries": len(entries), "head": prev}
