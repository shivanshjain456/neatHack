"""Evals-as-code for the agent itself: trajectory rules, hallucination rate, cost regression.

These run over durable records (the run store, the assurance corpus, the ablation file), not
over re-generated output, so every number they produce can be recomputed by anyone with the repo.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

TERMINAL_OK = {"VERIFIED_COMPLETE", "REPRO_PASSED_CALLERS_UNCHECKED"}


def _norm(phase: str) -> tuple[str, int | None]:
    m = re.match(r"^(.*)_(\d+)$", phase)
    return (m.group(1), int(m.group(2))) if m else (phase, None)


def evaluate_trajectory(steps: list[dict[str, Any]], run_status: str, mode: str) -> dict[str, Any]:
    """Check one run's recorded step sequence against the agent's required protocol.

    Rules (each violation is reported with the offending step):
      R1 localisation precedes reproduction, which precedes the first patch attempt
      R2 attempts are numbered 1..k with no gaps, and each has PLANNING then PATCHING
      R3 every attempt ends in exactly one verdict step: VERIFYING (accepted), RECOVERY_ROLLBACK,
         or a BLOCKED SECURITY step (rejected before the write)
      R4 an ASSURANCE step, when present for attempt k, sits between PATCHING_k and the verdict
      R5 a run marked verified has its last attempt accepted, and no attempt after it
      R6 no attempt is accepted after a rollback of the same attempt
      R7 graph_guarded runs that were accepted after C8 carry an ASSURANCE step for that attempt
    """
    seq = [(_norm(s["phase"]), s) for s in steps]
    names = [n for (n, _k), _s in seq]
    v: list[str] = []

    def first(name):
        return names.index(name) if name in names else None

    loc, rep = first("LOCALIZING"), first("REPRODUCING")
    first_patch = next((i for i, n in enumerate(names) if n in ("PLANNING_ATTEMPT", "PATCHING_ATTEMPT")), None)
    if loc is None or rep is None:
        v.append("R1: missing LOCALIZING or REPRODUCING step")
    elif not (loc < rep and (first_patch is None or rep < first_patch)):
        v.append("R1: LOCALIZING -> REPRODUCING -> PATCHING order violated")

    attempts: dict[int, list[str]] = {}
    for (n, k), st in seq:
        if n == "SECURITY_ATTEMPT" and st.get("status") == "BLOCKED":
            n = "SECURITY_BLOCKED"  # a pre-write security rejection is that attempt's verdict
        if k is not None and (n.endswith("ATTEMPT") or n in ("RECOVERY_ROLLBACK", "SECURITY_BLOCKED")):
            attempts.setdefault(k, []).append(n)
    ks = sorted(k for k in attempts if k is not None)
    if ks and ks != list(range(1, len(ks) + 1)):
        v.append(f"R2: attempt numbers {ks} are not 1..{len(ks)}")
    accepted = []
    for k in ks:
        a = attempts[k]
        if "PLANNING_ATTEMPT" in a and "PATCHING_ATTEMPT" in a and a.index("PLANNING_ATTEMPT") > a.index("PATCHING_ATTEMPT"):
            v.append(f"R2: attempt {k} patched before planning")
        verdicts = [x for x in a if x in ("VERIFYING_ATTEMPT", "RECOVERY_ROLLBACK", "SECURITY_BLOCKED")]
        if len(verdicts) != 1 and not (k == ks[-1] and run_status not in TERMINAL_OK and not verdicts):
            v.append(f"R3: attempt {k} has {len(verdicts)} verdict steps")
        if "ASSURANCE_ATTEMPT" in a:
            i_as, i_pa = a.index("ASSURANCE_ATTEMPT"), a.index("PATCHING_ATTEMPT") if "PATCHING_ATTEMPT" in a else -1
            i_v = next((a.index(x) for x in ("VERIFYING_ATTEMPT", "RECOVERY_ROLLBACK") if x in a), len(a))
            if not (i_pa < i_as < i_v):
                v.append(f"R4: ASSURANCE for attempt {k} out of order")
        if "VERIFYING_ATTEMPT" in a:
            accepted.append(k)
            if "RECOVERY_ROLLBACK" in a:
                v.append(f"R6: attempt {k} both accepted and rolled back")
    if run_status in TERMINAL_OK:
        if not accepted or accepted[-1] != (ks[-1] if ks else None):
            v.append("R5: run marked verified but its last attempt was not accepted")
    has_assurance = any(n == "ASSURANCE_ATTEMPT" for n in names)
    if mode == "graph_guarded" and run_status in TERMINAL_OK and has_assurance and accepted:
        if "ASSURANCE_ATTEMPT" not in attempts.get(accepted[-1], []):
            v.append("R7: accepted attempt lacks an ASSURANCE step")
    return {"ok": not v, "violations": v, "attempts": len(ks), "accepted_attempt": accepted[-1] if accepted else None,
            "rollbacks": names.count("RECOVERY_ROLLBACK"), "assurance_steps": names.count("ASSURANCE_ATTEMPT")}


def evaluate_run_store(db_path: str | Path) -> dict[str, Any]:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    runs = con.execute("SELECT run_id, status, mode FROM runs").fetchall()
    results = []
    for r in runs:
        steps = [dict(s) for s in con.execute("SELECT phase, span_kind, status FROM steps WHERE run_id=? ORDER BY seq_num", (r["run_id"],))]
        res = evaluate_trajectory(steps, r["status"], r["mode"])
        results.append({"run_id": r["run_id"], "status": r["status"], "mode": r["mode"], **res})
    ok = sum(x["ok"] for x in results)
    return {"runs": len(results), "trajectory_valid": ok, "trajectory_valid_rate": round(ok / len(results), 4) if results else None,
            "mean_attempts": round(sum(x["attempts"] for x in results) / len(results), 3) if results else None,
            "runs_with_rollback": sum(x["rollbacks"] > 0 for x in results),
            "invalid": [x for x in results if not x["ok"]]}


def hallucination_rate(corpus: dict[str, Any]) -> dict[str, Any]:
    """Share of replayed LLM patches with an unresolvable import, phantom symbol or undefined name."""
    recs = [r for r in corpus.get("records", []) if "assurance" in r]
    bad = [r for r in recs if r["assurance"]["gates"].get("symbols") == "fail"]
    return {"patches": len(recs), "with_hallucinated_reference": len(bad),
            "rate": round(len(bad) / len(recs), 4) if recs else None,
            "definition": "symbols gate failure: unresolvable import, phantom repository symbol, or undefined name"}


def cost_regression(ablation: dict[str, Any], budgets: dict[str, Any]) -> dict[str, Any]:
    """Compare measured per-arm means with committed budgets; any arm above budget is a regression."""
    arms = ablation["summary"]["arms"] if "arms" in ablation.get("summary", {}) else ablation["summary"]
    out, regressions = {}, []
    for arm, b in budgets["arms"].items():
        m = arms[arm]
        tokens = float(m["mean_total_tokens"])
        cost = float(m["mean_cost_usd"]) if "mean_cost_usd" in m else float(m["total_cost_usd"]) / max(1, int(m["runs"]))
        row = {"mean_total_tokens": tokens, "token_budget": b["max_mean_total_tokens"],
               "mean_cost_usd": cost, "cost_budget": b["max_mean_cost_usd"]}
        row["ok"] = tokens <= b["max_mean_total_tokens"] and cost <= b["max_mean_cost_usd"]
        if not row["ok"]:
            regressions.append(arm)
        out[arm] = row
    return {"arms": out, "regressions": regressions, "ok": not regressions}


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
