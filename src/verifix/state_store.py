"""Durable SQLite WAL state store for VeriFix autonomous runs, checkpoints, and experiments."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any


class VeriFixStateStore:
    """Transactional SQLite WAL database preserving agent state across steps, failures, and resumptions."""

    def __init__(self, db_path: str | Path = "/home/user/verifix/.verifix_runtime/verifix_state.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    repo_path TEXT NOT NULL,
                    worktree_path TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_phase TEXT NOT NULL,
                    current_attempt INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 3,
                    max_cost_usd REAL NOT NULL DEFAULT 0.25,
                    accumulated_cost_usd REAL NOT NULL DEFAULT 0.0,
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    total_latency_ms REAL NOT NULL DEFAULT 0.0,
                    span_count INTEGER NOT NULL DEFAULT 0,
                    caller_regressions_caught INTEGER NOT NULL DEFAULT 0,
                    rollbacks_executed INTEGER NOT NULL DEFAULT 0,
                    resumed_from_checkpoint INTEGER NOT NULL DEFAULT 0,
                    target_symbol TEXT DEFAULT '',
                    blast_radius_json TEXT DEFAULT '{}',
                    final_diff TEXT DEFAULT '',
                    verification_certificate_json TEXT DEFAULT '{}',
                    error_reason TEXT DEFAULT '',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS steps (
                    step_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    seq_num INTEGER NOT NULL,
                    phase TEXT NOT NULL,
                    span_kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    input_json TEXT NOT NULL,
                    output_json TEXT NOT NULL,
                    tokens_used INTEGER NOT NULL DEFAULT 0,
                    cost_usd REAL NOT NULL DEFAULT 0.0,
                    latency_ms REAL NOT NULL DEFAULT 0.0,
                    created_at REAL NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES runs(run_id)
                );

                CREATE TABLE IF NOT EXISTS hypotheses (
                    hypothesis_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    attempt_num INTEGER NOT NULL,
                    target_symbol TEXT NOT NULL,
                    target_file TEXT NOT NULL,
                    hypothesis_text TEXT NOT NULL,
                    blast_radius_callers_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    outcome_reason TEXT DEFAULT '',
                    created_at REAL NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES runs(run_id)
                );

                CREATE TABLE IF NOT EXISTS patches (
                    patch_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    attempt_num INTEGER NOT NULL,
                    target_file TEXT NOT NULL,
                    unified_diff TEXT NOT NULL,
                    repro_test_passed INTEGER NOT NULL DEFAULT 0,
                    caller_tests_passed INTEGER NOT NULL DEFAULT 0,
                    rolled_back INTEGER NOT NULL DEFAULT 0,
                    rollback_reason TEXT DEFAULT '',
                    test_output TEXT DEFAULT '',
                    created_at REAL NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES runs(run_id)
                );

                CREATE TABLE IF NOT EXISTS experiments (
                    experiment_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    run_a_id TEXT NOT NULL,
                    run_b_id TEXT NOT NULL,
                    comparison_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                """
            )

    def create_run(
        self,
        case_id: str,
        goal: str,
        repo_path: str,
        worktree_path: str,
        mode: str = "graph_guarded",
        max_attempts: int = 3,
        max_cost_usd: float = 0.25,
        run_id: str | None = None,
    ) -> str:
        rid = run_id or f"run_{uuid.uuid4().hex[:12]}"
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    run_id, case_id, goal, repo_path, worktree_path, mode,
                    status, current_phase, current_attempt, max_attempts, max_cost_usd,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'RUNNING', 'INITIALIZED', 0, ?, ?, ?, ?)
                """,
                (rid, case_id, goal, repo_path, worktree_path, mode, max_attempts, max_cost_usd, now, now),
            )
        return rid

    def update_run(self, run_id: str, **fields: Any) -> None:
        if not fields:
            return
        fields["updated_at"] = time.time()
        cols = ", ".join(f"{k} = ?" for k in fields.keys())
        vals = list(fields.values()) + [run_id]
        with self._connect() as conn:
            conn.execute(f"UPDATE runs SET {cols} WHERE run_id = ?", vals)

    def record_step(
        self,
        run_id: str,
        phase: str,
        span_kind: str,
        title: str,
        status: str,
        input_data: Any,
        output_data: Any,
        tokens_used: int = 0,
        cost_usd: float = 0.0,
        latency_ms: float = 0.0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> str:
        step_id = f"step_{uuid.uuid4().hex[:10]}"
        now = time.time()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(seq_num), 0) AS max_seq FROM steps WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            seq_num = int(row["max_seq"]) + 1
            conn.execute(
                """
                INSERT INTO steps (
                    step_id, run_id, seq_num, phase, span_kind, title, status,
                    input_json, output_json, tokens_used, cost_usd, latency_ms, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    step_id,
                    run_id,
                    seq_num,
                    phase,
                    span_kind,
                    title,
                    status,
                    json.dumps(input_data, default=str),
                    json.dumps(output_data, default=str),
                    tokens_used,
                    cost_usd,
                    latency_ms,
                    now,
                ),
            )
            conn.execute(
                """
                UPDATE runs
                SET current_phase = ?,
                    accumulated_cost_usd = accumulated_cost_usd + ?,
                    prompt_tokens = prompt_tokens + ?,
                    completion_tokens = completion_tokens + ?,
                    total_tokens = total_tokens + ?,
                    total_latency_ms = total_latency_ms + ?,
                    span_count = span_count + 1,
                    updated_at = ?
                WHERE run_id = ?
                """,
                (phase, cost_usd, prompt_tokens, completion_tokens, tokens_used, latency_ms, now, run_id),
            )
        return step_id

    def record_hypothesis(
        self,
        run_id: str,
        attempt_num: int,
        target_symbol: str,
        target_file: str,
        hypothesis_text: str,
        blast_radius_callers: list[dict[str, Any]],
        status: str = "ACTIVE",
        outcome_reason: str = "",
    ) -> str:
        hid = f"hyp_{uuid.uuid4().hex[:10]}"
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO hypotheses (
                    hypothesis_id, run_id, attempt_num, target_symbol, target_file,
                    hypothesis_text, blast_radius_callers_json, status, outcome_reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    hid,
                    run_id,
                    attempt_num,
                    target_symbol,
                    target_file,
                    hypothesis_text,
                    json.dumps(blast_radius_callers, default=str),
                    status,
                    outcome_reason,
                    now,
                ),
            )
        return hid

    def record_patch(
        self,
        run_id: str,
        attempt_num: int,
        target_file: str,
        unified_diff: str,
        repro_test_passed: bool,
        caller_tests_passed: bool,
        rolled_back: bool,
        rollback_reason: str,
        test_output: str,
    ) -> str:
        pid = f"patch_{uuid.uuid4().hex[:10]}"
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO patches (
                    patch_id, run_id, attempt_num, target_file, unified_diff,
                    repro_test_passed, caller_tests_passed, rolled_back, rollback_reason,
                    test_output, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pid,
                    run_id,
                    attempt_num,
                    target_file,
                    unified_diff,
                    1 if repro_test_passed else 0,
                    1 if caller_tests_passed else 0,
                    1 if rolled_back else 0,
                    rollback_reason,
                    test_output,
                    now,
                ),
            )
            if rolled_back:
                conn.execute(
                    """
                    UPDATE runs
                    SET rollbacks_executed = rollbacks_executed + 1,
                        caller_regressions_caught = caller_regressions_caught + ?,
                        updated_at = ?
                    WHERE run_id = ?
                    """,
                    (1 if (repro_test_passed and not caller_tests_passed) else 0, now, run_id),
                )
        return pid

    def record_experiment(self, case_id: str, run_a_id: str, run_b_id: str, comparison: dict[str, Any]) -> str:
        eid = f"exp_{uuid.uuid4().hex[:10]}"
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO experiments (experiment_id, case_id, run_a_id, run_b_id, comparison_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (eid, case_id, run_a_id, run_b_id, json.dumps(comparison, default=str), now),
            )
        return eid

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if not row:
                return None
            run_dict = dict(row)
            run_dict["blast_radius"] = json.loads(run_dict.get("blast_radius_json") or "{}")
            run_dict["verification_certificate"] = json.loads(
                run_dict.get("verification_certificate_json") or "{}"
            )
            steps = conn.execute(
                "SELECT * FROM steps WHERE run_id = ? ORDER BY seq_num ASC", (run_id,)
            ).fetchall()
            run_dict["steps"] = [
                {
                    **dict(s),
                    "input": json.loads(s["input_json"] or "{}"),
                    "output": json.loads(s["output_json"] or "{}"),
                }
                for s in steps
            ]
            hyps = conn.execute(
                "SELECT * FROM hypotheses WHERE run_id = ? ORDER BY attempt_num ASC", (run_id,)
            ).fetchall()
            run_dict["hypotheses"] = [
                {
                    **dict(h),
                    "blast_radius_callers": json.loads(h["blast_radius_callers_json"] or "[]"),
                }
                for h in hyps
            ]
            patches = conn.execute(
                "SELECT * FROM patches WHERE run_id = ? ORDER BY attempt_num ASC", (run_id,)
            ).fetchall()
            run_dict["patches"] = [dict(p) for p in patches]
            return run_dict

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                d["blast_radius"] = json.loads(d.get("blast_radius_json") or "{}")
                d["verification_certificate"] = json.loads(d.get("verification_certificate_json") or "{}")
                out.append(d)
            return out

    def list_experiments(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM experiments ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [
                {**dict(r), "comparison": json.loads(r["comparison_json"] or "{}")}
                for r in rows
            ]
