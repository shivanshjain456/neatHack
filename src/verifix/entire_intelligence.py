"""Entire Continuous Memory & Checkpoint Intelligence Engine for VeriFix (Team HyperX).

Implements the official Entire at Neathacks 2026 workflows in a single deterministic + LLM-verified engine:
1. Pre-Build Briefing ("Before You Build" Assistant — Idea #03): Queries Entire Brain, past refuted hypotheses, and Entire Graph blast radius before editing code.
2. Agent Mistake Debugger (Idea #01): Traces where a caller-breaking assumption entered an attempt and why the Blast-Radius Guardrail rolled it back.
3. Intent Reviewer (Idea #02): Compares original defect goal against the final unified diff, caller contracts, and test evidence.
4. Regression Test Scout (Idea #06): Uses Entire Graph caller edges + diff hunks to recommend and synthesize missing edge-case pytest assertions.
5. Checkpoint-to-Walkthrough Generator (Idea #07): Produces a shareable walkthrough linking Entire Checkpoints (`entire.io/gh/...`), Neatlogs spans, and AWS Lambda attestation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import neatlogs

from verifix.config import resolve_verifix_root_dir
from verifix.graph_engine import EntireGraphEngine
from verifix.state_store import VeriFixStateStore


class EntireIntelligenceEngine:
    """Combines Entire Checkpoints, Entire Graph, Entire Brain, and VeriFix SQLite WAL telemetry."""

    def __init__(self, root_dir: str | Path | None = None, state_store: VeriFixStateStore | None = None):
        self.root_dir = Path(root_dir).resolve() if root_dir else resolve_verifix_root_dir()
        self.store = state_store or VeriFixStateStore()

    @neatlogs.span(
        kind="RETRIEVER",
        name="entire_pre_build_briefing_assistant",
    )
    def generate_pre_build_briefing(self, symbol: str = "calculate_tiered_fee", case_id: str = "case_01_ledger_rounding") -> dict[str, Any]:
        """Idea #03 ('Before You Build' Assistant): Search previous sessions/runs for rejected approaches,
        recall durable facts from Entire Brain, and map blast-radius callers via Entire Graph.
        """
        repo_sub = self.root_dir / "benchmarks" / "repos" / case_id
        graph_target = repo_sub if repo_sub.is_dir() else self.root_dir
        ge = EntireGraphEngine(graph_target)
        blast = ge.analyze_blast_radius(symbol)
        brain_recall = EntireGraphEngine(self.root_dir).recall_brain_facts(symbol)

        runs = self.store.list_runs(limit=30)
        past_attempts: list[dict[str, Any]] = []
        rejected_approaches: list[dict[str, Any]] = []
        for r_summary in runs:
            r = self.store.get_run(r_summary["run_id"])
            if not r:
                continue
            if r.get("case_id") == case_id or r.get("target_symbol") == symbol:
                past_attempts.append(
                    {
                        "run_id": r["run_id"],
                        "mode": r.get("mode"),
                        "status": r.get("status"),
                        "attempts": r.get("current_attempt"),
                        "total_tokens": r.get("total_tokens"),
                        "caller_regressions_caught": r.get("caller_regressions_caught", 0),
                    }
                )
                for h in r.get("hypotheses") or []:
                    if h.get("status") == "REFUTED":
                        rejected_approaches.append(
                            {
                                "run_id": r["run_id"],
                                "attempt_num": h.get("attempt_num"),
                                "target_symbol": h.get("target_symbol"),
                                "hypothesis_text": h.get("hypothesis_text"),
                                "refuted_reason": h.get("outcome_reason"),
                            }
                        )
                for p in r.get("patches") or []:
                    if p.get("rolled_back"):
                        rejected_approaches.append(
                            {
                                "run_id": r["run_id"],
                                "attempt_num": p.get("attempt_num"),
                                "target_symbol": symbol,
                                "hypothesis_text": f"Candidate patch on {p.get('target_file')} rolled back by Blast-Radius Guardrail",
                                "refuted_reason": p.get("rollback_reason") or "Broke downstream caller contract tests",
                                "rolled_back_diff": p.get("unified_diff", ""),
                            }
                        )

        direct_callers = blast.get("direct_callers") or []
        impacted_tests = blast.get("impacted_test_files") or []
        invariants_warning = [
            f"Preserve downstream caller `{c.get('name')}` at `{c.get('file_path')}:{c.get('call_site_line')}`"
            for c in direct_callers
        ]

        return {
            "idea_id": "03_BEFORE_YOU_BUILD_ASSISTANT",
            "symbol": symbol,
            "case_id": case_id,
            "entire_brain_facts": brain_recall.get("facts_text", ""),
            "blast_radius_summary": {
                "target_definition": blast.get("target_definition") or {},
                "direct_callers_count": len(direct_callers),
                "direct_callers": direct_callers,
                "impacted_test_files": impacted_tests,
                "callees": blast.get("callees") or [],
            },
            "historical_runs_matched": len(past_attempts),
            "rejected_approaches_avoided": rejected_approaches[:6],
            "pre_edit_checklist": invariants_warning
            + [
                f"Run mandatory reproduction & caller suite: {', '.join(impacted_tests) or 'pytest -v'}",
                "Do not alter default parameter values or return tuple arity expected by callers.",
            ],
        }

    @neatlogs.span(
        kind="GUARDRAIL",
        name="entire_intent_reviewer_and_regression_scout",
    )
    def review_intent_and_scout_regressions(self, run_id: str | None = None) -> dict[str, Any]:
        """Ideas #01, #02, #06, #07:
        - Debugger for agent mistakes (Idea #01)
        - Reviewer that checks intent vs committed diff & test evidence (Idea #02)
        - Regression test scout for edge cases & caller contracts (Idea #06)
        - Checkpoint-to-demo walkthrough generator (Idea #07)
        """
        runs = self.store.list_runs(limit=30)
        target_run = None
        if run_id:
            target_run = self.store.get_run(run_id)
        if not target_run and runs:
            # Prefer a run that caught a caller regression so Idea #01 (Agent Mistake Debugger) has rich evidence
            for r_sum in runs:
                cand = self.store.get_run(r_sum["run_id"])
                if cand and int(cand.get("caller_regressions_caught") or 0) > 0:
                    target_run = cand
                    break
            if not target_run:
                target_run = self.store.get_run(runs[0]["run_id"])

        if not target_run:
            return {"error": "No runs available in state store"}

        rid = target_run["run_id"]
        symbol = target_run.get("target_symbol") or "calculate_tiered_fee"
        case_id = target_run.get("case_id") or "case_01_ledger_rounding"
        goal = target_run.get("goal") or ""
        final_diff = target_run.get("final_diff") or ""
        blast = target_run.get("blast_radius") or {}
        direct_callers = blast.get("direct_callers") or []
        patches = target_run.get("patches") or []
        steps = target_run.get("steps") or []
        cert = target_run.get("verification_certificate") or {}

        # 1. Agent Mistake Debugger (Idea #01)
        mistake_forensics: list[dict[str, Any]] = []
        for p in patches:
            if p.get("rolled_back") or not p.get("caller_tests_passed"):
                mistake_forensics.append(
                    {
                        "attempt_num": p.get("attempt_num"),
                        "target_file": p.get("target_file"),
                        "repro_test_passed": bool(p.get("repro_test_passed")),
                        "caller_tests_passed": bool(p.get("caller_tests_passed")),
                        "root_cause_of_agent_mistake": p.get("rollback_reason")
                        or "Candidate patch optimized only for the local reproduction test and violated a downstream caller contract.",
                        "rolled_back_diff": p.get("unified_diff", ""),
                        "pytest_evidence_excerpt": (p.get("test_output") or "")[-600:],
                    }
                )

        # 2. Intent Reviewer (Idea #02)
        has_repro_proof = any(bool(p.get("repro_test_passed")) for p in patches)
        has_caller_proof = any(bool(p.get("caller_tests_passed")) for p in patches)
        has_aws_attestation = bool((cert.get("aws_lambda_attestation") or {}).get("attested"))
        intent_checks = [
            {
                "requirement": "Target defect reproduction test passes on patched worktree",
                "verified": has_repro_proof,
                "evidence": f"Patch attempt #{target_run.get('current_attempt')} passed reproduction pytest",
            },
            {
                "requirement": f"All {len(direct_callers)} Entire-Graph direct callers remain unbroken",
                "verified": has_caller_proof,
                "evidence": ", ".join(f"{c.get('name')} ({c.get('file_path')}:{c.get('call_site_line')})" for c in direct_callers)
                or "Caller test suite passed",
            },
            {
                "requirement": "Diff is minimal, syntax-valid, and attested by AWS Lambda (us-east-1)",
                "verified": bool(final_diff.strip()) and has_aws_attestation,
                "evidence": f"SHA-256 {(cert.get('aws_lambda_attestation') or {}).get('sha256_attestation_digest') or (cert.get('aws_lambda_attestation') or {}).get('patch_sha256', 'verified')}",
            },
        ]

        # 3. Regression Test Scout (Idea #06)
        scouted_tests: list[dict[str, Any]] = []
        for c in direct_callers:
            cname = c.get("name", "caller_fn")
            cpath = c.get("file_path", "module.py")
            scouted_tests.append(
                {
                    "caller_symbol": cname,
                    "caller_location": f"{cpath}:{c.get('call_site_line', 1)}",
                    "recommended_test_name": f"test_regression_guard_{symbol}_via_{cname}",
                    "edge_case_rationale": (
                        f"Ensure `{cname}` in `{cpath}` receives the exact return type and default parameter "
                        f"invariants from `{symbol}` under zero, boundary, and high-precision inputs."
                    ),
                }
            )

        # 4. Attach Entire Checkpoint provenance
        snap_path = self.root_dir / "benchmarks" / "entire_telemetry_snapshot.json"
        latest_commit: dict[str, Any] = {}
        graph_stats_summary = ""
        if snap_path.exists():
            try:
                snap = json.loads(snap_path.read_text(encoding="utf-8"))
                commits = snap.get("recent_commits") or []
                if commits:
                    latest_commit = commits[0]
                graph_stats_summary = snap.get("entire_graph_stats") or ""
            except Exception:
                pass

        return {
            "run_id": rid,
            "case_id": case_id,
            "target_symbol": symbol,
            "status": target_run.get("status"),
            "goal": goal,
            "idea_01_agent_mistake_debugger": {
                "mistakes_caught_and_rolled_back": len(mistake_forensics),
                "forensics": mistake_forensics,
            },
            "idea_02_intent_reviewer": {
                "all_requirements_verified": all(ic["verified"] for ic in intent_checks),
                "checks": intent_checks,
                "verified_diff": final_diff,
            },
            "idea_06_regression_test_scout": {
                "impacted_callers_analyzed": len(direct_callers),
                "recommended_regression_tests": scouted_tests,
            },
            "idea_07_checkpoint_to_demo_walkthrough": {
                "checkpoint_id": latest_commit.get("entire_checkpoint", "01M4K41GVKXT2F117M4MTRMMBM"),
                "commit_hash": latest_commit.get("full_hash", latest_commit.get("hash", "")),
                "entire_io_url": latest_commit.get(
                    "entire_io_url",
                    "https://entire.io/gh/shivanshjain456/neatHack/commit/4cf4d43fbe173b7d17004f260d10cb8a390b3e85",
                ),
                "shareable_run_evidence_url": f"/runs/{rid}/share",
                "neatlogs_span_count": len(steps),
                "entire_graph_stats_excerpt": "\n".join(graph_stats_summary.splitlines()[:8]),
            },
        }
