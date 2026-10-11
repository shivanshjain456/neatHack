"""Durable quality registries backed by SQLite.

FlakyRegistry
    Records, per test id, whether each observation was flaky (outcomes disagreed across reruns
    in the same environment). A test is quarantined after ``quarantine_after`` flaky observations
    (consecutive or not) and released after ``release_after`` consecutive stable observations.
    Quarantined tests stay visible in reports and stop blocking the gate, so one known-flaky test
    cannot hold every patch hostage. Patches verified by a quarantined test are graded weaker.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any


class FlakyRegistry:
    def __init__(self, db_path: str | Path, quarantine_after: int = 2, release_after: int = 5):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.quarantine_after = quarantine_after
        self.release_after = release_after
        self._lock = threading.Lock()
        with self._conn() as c:
            c.execute(
                """CREATE TABLE IF NOT EXISTS flaky_tests (
                       test_id TEXT PRIMARY KEY,
                       observations INTEGER NOT NULL DEFAULT 0,
                       flaky_observations INTEGER NOT NULL DEFAULT 0,
                       flaky_since_release INTEGER NOT NULL DEFAULT 0,
                       consecutive_stable INTEGER NOT NULL DEFAULT 0,
                       quarantined INTEGER NOT NULL DEFAULT 0,
                       quarantined_at REAL, released_at REAL, updated_at REAL NOT NULL)"""
            )
            c.execute(
                """CREATE TABLE IF NOT EXISTS flaky_events (
                       id INTEGER PRIMARY KEY AUTOINCREMENT, test_id TEXT NOT NULL, flaky INTEGER NOT NULL,
                       outcomes TEXT NOT NULL, context TEXT, at REAL NOT NULL)"""
            )

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.db_path, timeout=10)
        c.row_factory = sqlite3.Row
        return c

    def record(self, test_id: str, outcomes: list[bool], context: str = "") -> dict[str, Any]:
        """Record one multi-run observation; returns the updated state for the test."""
        flaky = len(set(outcomes)) > 1
        now = time.time()
        with self._lock, self._conn() as c:
            row = c.execute("SELECT * FROM flaky_tests WHERE test_id=?", (test_id,)).fetchone()
            st = dict(row) if row else {"test_id": test_id, "observations": 0, "flaky_observations": 0, "flaky_since_release": 0,
                                        "consecutive_stable": 0, "quarantined": 0, "quarantined_at": None, "released_at": None}
            st["observations"] += 1
            transition = None
            if flaky:
                st["flaky_observations"] += 1
                st["flaky_since_release"] += 1
                st["consecutive_stable"] = 0
                if not st["quarantined"] and st["flaky_since_release"] >= self.quarantine_after:
                    st["quarantined"], st["quarantined_at"], transition = 1, now, "quarantined"
            else:
                st["consecutive_stable"] += 1
                if st["quarantined"] and st["consecutive_stable"] >= self.release_after:
                    st["quarantined"], st["released_at"], st["flaky_since_release"], transition = 0, now, 0, "released"
            c.execute(
                """INSERT INTO flaky_tests(test_id, observations, flaky_observations, flaky_since_release, consecutive_stable,
                                          quarantined, quarantined_at, released_at, updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(test_id) DO UPDATE SET observations=excluded.observations,
                     flaky_observations=excluded.flaky_observations, flaky_since_release=excluded.flaky_since_release,
                     consecutive_stable=excluded.consecutive_stable, quarantined=excluded.quarantined,
                     quarantined_at=excluded.quarantined_at, released_at=excluded.released_at, updated_at=excluded.updated_at""",
                (test_id, st["observations"], st["flaky_observations"], st["flaky_since_release"], st["consecutive_stable"],
                 st["quarantined"], st["quarantined_at"], st["released_at"], now),
            )
            c.execute("INSERT INTO flaky_events(test_id, flaky, outcomes, context, at) VALUES(?,?,?,?,?)",
                      (test_id, int(flaky), ",".join("P" if o else "F" for o in outcomes), context[:200], now))
        return {"test_id": test_id, "flaky": flaky, "quarantined": bool(st["quarantined"]), "transition": transition,
                "observations": st["observations"], "flaky_observations": st["flaky_observations"]}

    def is_quarantined(self, test_id: str) -> bool:
        with self._conn() as c:
            row = c.execute("SELECT quarantined FROM flaky_tests WHERE test_id=?", (test_id,)).fetchone()
        return bool(row and row["quarantined"])

    def flaky_rate(self) -> dict[str, Any]:
        """Flaky-test rate = flaky observations / all observations (and per-test share)."""
        with self._conn() as c:
            agg = c.execute("SELECT COALESCE(SUM(observations),0) n, COALESCE(SUM(flaky_observations),0) f, COUNT(*) t, "
                            "COALESCE(SUM(flaky_observations > 0),0) tf, COALESCE(SUM(quarantined),0) q FROM flaky_tests").fetchone()
        n, f = agg["n"], agg["f"]
        return {"observations": n, "flaky_observations": f, "flaky_rate": round(f / n, 4) if n else 0.0,
                "tests": agg["t"], "tests_ever_flaky": agg["tf"], "quarantined": agg["q"]}
