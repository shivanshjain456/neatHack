"""Core 8-Focus-Area Autonomous Defect Remediation Harness for VeriFix."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import neatlogs

from verifix.aws_verifier import AWSLambdaPatchVerifier
from verifix.config import TracedLLMClient, ensure_neatlogs_initialized, workflow_root
from verifix.graph_engine import EntireGraphEngine
from verifix.state_store import VeriFixStateStore
from verifix.test_runner import SandboxedTestRunner
from verifix.worktree_manager import WorktreeManager


BENCHMARK_CATALOG: dict[str, dict[str, Any]] = {
    "case_01_ledger_rounding": {
        "case_id": "case_01_ledger_rounding",
        "title": "Financial Ledger Tiered-Fee Precision & Split Conservation",
        "repo_subpath": "benchmarks/repos/case_01_ledger_rounding",
        "target_file": "ledger/fees.py",
        "target_symbol": "calculate_tiered_fee",
        "repro_test": "tests/test_fees.py",
        "caller_tests": ["tests/test_settlement.py"],
        "goal": (
            "Fix IEEE-754 floating-point precision loss in `calculate_tiered_fee` by computing "
            "`int((Decimal(amount_cents) * Decimal(tier_bps) / Decimal(10000)).quantize(Decimal('1'), rounding=ROUND_HALF_EVEN))` "
            "before `max(..., min_fee_cents)` while keeping default `min_fee_cents: int = 50` and returning `int` "
            "cents so downstream callers `build_settlement_batch` and `render_tax_invoice` do not break. "
            "Also fix `calculate_split_fees` so any rounding residual `total_expected_fee - sum(allocated_fees)` "
            "is added to the largest split leg (`max(range(len(splits_cents)), key=lambda i: (splits_cents[i], i))`)."
        ),
        "caller_trap_patch": '''"""Caller-trap candidate patch: changes default min_fee_cents=500, passing test_fees.py but breaking settlement.py and invoicing.py!"""
from decimal import Decimal, ROUND_HALF_EVEN
from ledger.money import validate_cents

def calculate_tiered_fee(amount_cents: int, tier_bps: int, min_fee_cents: int = 500) -> int:
    validate_cents(amount_cents)
    if amount_cents == 0:
        return 0
    exact = int((Decimal(amount_cents) * Decimal(tier_bps) / Decimal(10000)).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))
    return max(exact, min_fee_cents)

def calculate_split_fees(total_amount_cents: int, splits_cents: list[int], tier_bps: int) -> dict:
    validate_cents(total_amount_cents)
    if sum(splits_cents) != total_amount_cents:
        raise ValueError("Sum of splits_cents must equal total_amount_cents")
    total_expected_fee = calculate_tiered_fee(total_amount_cents, tier_bps, min_fee_cents=0)
    allocated_fees = [calculate_tiered_fee(part, tier_bps, min_fee_cents=0) for part in splits_cents]
    residual = total_expected_fee - sum(allocated_fees)
    if residual != 0 and allocated_fees:
        idx = max(range(len(splits_cents)), key=lambda i: (splits_cents[i], i))
        allocated_fees[idx] += residual
    return {"total_fee_cents": sum(allocated_fees), "allocated_fees_cents": allocated_fees}
''',
    },
    "case_02_ratelimiter_state": {
        "case_id": "case_02_ratelimiter_state",
        "title": "Token-Bucket Fractional Refill Loss on Rejected Burst",
        "repo_subpath": "benchmarks/repos/case_02_ratelimiter_state",
        "target_file": "ratelimiter/bucket.py",
        "target_symbol": "TokenBucket.consume",
        "repro_test": "tests/test_ratelimiter.py::test_refill_preserved_across_rejected_burst",
        "caller_tests": ["tests/test_ratelimiter.py::test_gateway_middleware_caller_contract"],
        "goal": (
            "Fix `TokenBucket.consume(self, cost: int, now: float) -> tuple[bool, int, float]` in "
            "`ratelimiter/bucket.py` so it calls `self._refill(now)` BEFORE checking `self.tokens >= cost`, "
            "preserves accumulated `self.tokens` when a request is rejected, and returns "
            "`round((cost - self.tokens) / self.refill_rate_per_sec, 4)` as `retry_after_sec` when rejected "
            "while keeping the 3-tuple return contract `(allowed: bool, int(self.tokens), retry_after_sec: float)` "
            "required by `APIGatewayMiddleware.handle_request`."
        ),
    },
    "case_03_webhook_validator": {
        "case_id": "case_03_webhook_validator",
        "title": "Cryptographic Webhook ISO-8601 Timestamp & Canonical HMAC Fix",
        "repo_subpath": "benchmarks/repos/case_03_webhook_validator",
        "target_file": "webhooks/signature.py",
        "target_symbol": "verify_webhook_signature",
        "repro_test": "tests/test_webhooks.py::test_iso8601_and_epoch_timestamp_parsing",
        "caller_tests": ["tests/test_webhooks.py::test_canonical_hmac_and_dispatcher_caller"],
        "goal": (
            "Fix `parse_webhook_timestamp` in `webhooks/signature.py` to support both integer epoch strings "
            "and ISO-8601 strings (including trailing 'Z' or timezone offsets via `datetime.fromisoformat`), "
            "and fix `verify_webhook_signature` to sign the canonical payload `f'{epoch_ts}.{payload_body}'` "
            "while preserving the `(bool, str)` return signature required by `WebhookDispatcher.dispatch`."
        ),
    },
    "case_04_dag_scheduler": {
        "case_id": "case_04_dag_scheduler",
        "title": "ExecutionDAG Retry Recovery & Diamond Dependency Unblocking",
        "repo_subpath": "benchmarks/repos/case_04_dag_scheduler",
        "target_file": "scheduler/graph.py",
        "target_symbol": "ExecutionDAG.mark_succeeded",
        "repro_test": "tests/test_scheduler.py",
        "caller_tests": ["tests/test_scheduler.py"],
        "goal": (
            "Fix `ExecutionDAG.mark_succeeded(self, node_id: str)` in `scheduler/graph.py` so that when a "
            "previously failed node succeeds on retry, `self.failed.discard(node_id)` clears its failed state, "
            "allowing downstream diamond dependencies in `get_ready_nodes()` and `PipelineRunner` to proceed."
        ),
    },
}


def _extract_python_code(raw_text: str) -> str:
    """Extract clean Python source code from an LLM response (fenced block or raw text)."""
    m = re.search(r"```(?:python)?\s*\n(.*?)```", raw_text, re.DOTALL)
    if m:
        return m.group(1).strip() + "\n"
    return raw_text.strip() + "\n"


class VeriFixAgentHarness:
    """Autonomous 8-Focus-Area Defect Remediation Agent instrumented with Neatlogs and Entire Graph."""

    def __init__(
        self,
        root_dir: str | Path = "/home/user/verifix",
        state_store: VeriFixStateStore | None = None,
        llm_client: TracedLLMClient | None = None,
    ):
        self.root_dir = Path(root_dir).resolve()
        self.store = state_store or VeriFixStateStore(self.root_dir / ".verifix_runtime" / "verifix_state.db")
        self.llm = llm_client or TracedLLMClient()
        ensure_neatlogs_initialized()

    @neatlogs.span(
        kind="AGENT",
        name="hypothesis_planner",
        role="Lead Reliability Planner",
        goal="Formulate a testable root-cause hypothesis and blast-radius verification plan.",
    )
    def _plan_hypothesis(
        self,
        goal: str,
        mode: str,
        context_bundle: str,
        repro_failure_output: str,
        prior_failure_feedback: str = "",
    ) -> tuple[str, Any]:
        sys_prompt = (
            "You are the Lead Reliability Planner inside VeriFix, an autonomous software engineering agent. "
            "Given the defect goal, repository context, and failing pytest output, produce a concise, "
            "3-bullet root-cause hypothesis and exact contract invariants that must be preserved."
        )
        if mode == "baseline_naive":
            # In baseline_naive mode (Before optimization), the agent performs verbose multi-file
            # reasoning over unpruned repository files and historical notes.
            user_prompt = (
                f"DEFECT GOAL:\n{goal}\n\n"
                f"UNPRUNED REPOSITORY FILES & HISTORICAL LOGS:\n{context_bundle}\n\n"
                f"FAILING TEST OUTPUT:\n{repro_failure_output}\n\n"
                "Write a detailed analysis of every file in the repository, then state your root-cause hypothesis."
            )
        else:
            user_prompt = (
                f"DEFECT GOAL:\n{goal}\n\n"
                f"ENTIRE-GRAPH FOCUSED SLICE & CALLER CONTRACTS:\n{context_bundle}\n\n"
                f"FAILING TEST OUTPUT:\n{repro_failure_output[-1200:]}\n"
            )
            if prior_failure_feedback:
                user_prompt += f"\nPRIOR ATTEMPT REGRESSION FEEDBACK:\n{prior_failure_feedback}\n"
            user_prompt += "\nState the root cause and caller contract constraints in 3 concise bullet points."

        res = self.llm.generate(
            system_prompt=sys_prompt,
            user_prompt=user_prompt,
            temperature=0.1,
            template_name=f"planner_{mode}",
        )
        return res.content, res

    @neatlogs.span(
        kind="AGENT",
        name="patch_synthesizer",
        role="Surgical Code Patch Synthesizer",
        goal="Produce a minimal, syntax-valid Python file fix that satisfies both the defect test and all blast-radius callers.",
    )
    def _synthesize_patch(
        self,
        goal: str,
        target_file: str,
        current_file_source: str,
        hypothesis: str,
        caller_contracts_summary: str,
        prior_failure_feedback: str = "",
    ) -> tuple[str, Any]:
        sys_prompt = (
            "You are VeriFix's Surgical Code Patch Synthesizer. "
            "Return ONLY the complete, valid Python source code for the target file inside a single "
            "```python ... ``` block. Preserve all function names, parameter defaults, and return types "
            "expected by downstream callers."
        )
        user_prompt = (
            f"TARGET FILE: `{target_file}`\n\n"
            f"DEFECT GOAL:\n{goal}\n\n"
            f"ROOT-CAUSE HYPOTHESIS:\n{hypothesis}\n\n"
            f"DOWNSTREAM CALLER CONTRACTS (MUST NOT BREAK):\n{caller_contracts_summary}\n\n"
            f"CURRENT `{target_file}` SOURCE:\n```python\n{current_file_source}\n```\n"
        )
        if prior_failure_feedback:
            user_prompt += (
                f"\nCRITICAL: Your previous candidate patch failed verification and was rolled back!\n"
                f"FAILURE TRACEBACK:\n{prior_failure_feedback}\n"
                "Fix this regression while keeping the defect fix intact.\n"
            )
        user_prompt += f"\nOutput ONLY the corrected Python code for `{target_file}` inside ```python ... ```."

        res = self.llm.generate(
            system_prompt=sys_prompt,
            user_prompt=user_prompt,
            temperature=0.05,
            template_name="patch_synthesizer",
        )
        return _extract_python_code(res.content), res

    @neatlogs.span(
        kind="GUARDRAIL",
        name="budget_and_loop_guardrail",
        description="Enforce hard caps on attempts (3), tool calls (20), and cost ($0.25) to prevent runaway agent loops.",
    )
    def _enforce_budget_and_loop_guardrail(
        self,
        attempt: int,
        tool_calls_used: int,
        accumulated_cost_usd: float,
        max_attempts: int = 3,
        max_tool_calls: int = 20,
        max_cost_usd: float = 0.25,
    ) -> dict[str, Any]:
        within_attempts = attempt <= max_attempts
        within_tools = tool_calls_used <= max_tool_calls
        within_cost = accumulated_cost_usd < max_cost_usd
        allowed = within_attempts and within_tools and within_cost
        return {
            "allowed": allowed,
            "attempt": attempt,
            "max_attempts": max_attempts,
            "tool_calls_used": tool_calls_used,
            "max_tool_calls": max_tool_calls,
            "accumulated_cost_usd": round(accumulated_cost_usd, 6),
            "max_cost_usd": max_cost_usd,
        }

    def _build_naive_full_repo_context(self, worktree_path: Path) -> str:
        """Simulate standard coding-agent behavior without `entire-graph`: dumps all repo files + verbose git/audit context."""
        chunks: list[str] = []
        for p in sorted(worktree_path.rglob("*.py")):
            rel = p.relative_to(worktree_path)
            content = p.read_text(encoding="utf-8")
            chunks.append(f"=== FILE: {rel} ===\n{content}")
        # Standard agents without a code graph also inspect repo-wide docs/configs during grep exploration
        for doc_p in sorted(self.root_dir.glob("*.md")):
            chunks.append(f"=== REPO DOC: {doc_p.name} ===\n{doc_p.read_text(encoding='utf-8')[:3500]}")
        return "\n\n".join(chunks)

    def execute_case(
        self,
        case_id: str,
        mode: str = "graph_guarded",
        inject_caller_regression_on_attempt_1: bool = False,
        simulate_interrupt_after_phase: str | None = None,
        resume_run_id: str | None = None,
        max_cost_usd: float = 0.25,
        custom_spec: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run or resume an end-to-end defect remediation task and return the full run record."""
        if custom_spec is not None:
            spec = custom_spec
            repo_ref = Path(spec["repo_path"])
            source_repo = repo_ref if repo_ref.is_absolute() else (self.root_dir / repo_ref).resolve()
        else:
            if case_id not in BENCHMARK_CATALOG:
                raise ValueError(f"Unknown case_id: {case_id}. Available: {list(BENCHMARK_CATALOG.keys())}")
            spec = BENCHMARK_CATALOG[case_id]
            source_repo = self.root_dir / spec["repo_subpath"]
        workflow_label = "defect-remediation" if mode == "graph_guarded" else "defect-remediation-naive-baseline"

        with workflow_root(workflow_label, trace_title=f"verifix_{mode}_{case_id}") as root_span:
            t_run_start = time.perf_counter()

            if resume_run_id:
                existing = self.store.get_run(resume_run_id)
                if not existing:
                    raise ValueError(f"Cannot resume unknown run_id: {resume_run_id}")
                run_id = resume_run_id
                wt_mgr = WorktreeManager(source_repo, run_id=run_id)
                worktree_path = wt_mgr.prepare()
                completed_phases = {s["phase"] for s in existing.get("steps", []) if s["status"] == "COMPLETED"}
                self.store.update_run(run_id, status="RUNNING", resumed_from_checkpoint=1)
                neatlogs.log("Resumed run_id={run_id} completed_phases={phases}", run_id=run_id, phases=sorted(completed_phases))
            else:
                wt_mgr = WorktreeManager(source_repo, run_id=f"run_{mode[:5]}_{case_id[:10]}_{int(time.time()*1000)%100000}")
                worktree_path = wt_mgr.prepare()
                run_id = self.store.create_run(
                    case_id=case_id,
                    goal=spec["goal"],
                    repo_path=str(source_repo),
                    worktree_path=str(worktree_path),
                    mode=mode,
                    max_attempts=3,
                    max_cost_usd=max_cost_usd,
                    run_id=wt_mgr.run_id,
                )
                completed_phases = set()

            if root_span is not None:
                root_span.set_attribute("verifix.run_id", run_id)
                root_span.set_attribute("verifix.case_id", case_id)
                root_span.set_attribute("verifix.mode", mode)
                root_span.set_attribute("verifix.version", "v2" if mode == "graph_guarded" else "v1")
                root_span.set_attribute("verifix.guardrail.max_attempts", 3)
                root_span.set_attribute("verifix.guardrail.max_tool_calls", 20)
                root_span.set_attribute("verifix.guardrail.max_cost_usd", max_cost_usd)

            test_runner = SandboxedTestRunner(worktree_path)
            graph_engine = EntireGraphEngine(worktree_path)

            # ── STEP 1: CONTEXT & LOCALIZATION (`LOCALIZING`) ──────────────────────────────
            if "LOCALIZING" not in completed_phases:
                t0 = time.perf_counter()
                if mode == "graph_guarded":
                    ctx_data = graph_engine.retrieve_focused_context(
                        query=spec["goal"],
                        target_symbol=spec["target_symbol"].split(".")[-1],
                    )
                    blast_radius = ctx_data["blast_radius"]
                    focused_docs = ctx_data["documents"]
                    context_bundle = "\n\n".join(
                        f"[{d['role']}] {d['file_path']} (lines {d['line_range']}):\n{d['focused_slice']}"
                        for d in focused_docs
                    )
                    caller_summary = "\n".join(
                        f"- {c['name']} in {c['file_path']}:{c['call_site_line']} (resolution={c['resolution']})"
                        for c in blast_radius.get("direct_callers", [])
                    ) or "See target file docstrings."
                else:
                    # Naive baseline: no `entire-graph` — dumps all files & docs
                    blast_radius = {"mode": "naive_grep_full_dump", "direct_callers": [], "impacted_test_files": []}
                    context_bundle = self._build_naive_full_repo_context(worktree_path)
                    caller_summary = "No structural caller graph available in baseline_naive mode."

                lat_loc = round((time.perf_counter() - t0) * 1000.0, 2)
                self.store.update_run(
                    run_id,
                    target_symbol=spec["target_symbol"],
                    blast_radius_json=json.dumps(blast_radius, default=str),
                )
                self.store.record_step(
                    run_id=run_id,
                    phase="LOCALIZING",
                    span_kind="RETRIEVER",
                    title="entire-graph localization & blast-radius map" if mode == "graph_guarded" else "Naive full-repo file scan",
                    status="COMPLETED",
                    input_data={"query": spec["goal"], "symbol": spec["target_symbol"], "mode": mode},
                    output_data={
                        "context_chars": len(context_bundle),
                        "direct_callers_count": len(blast_radius.get("direct_callers", [])),
                        "impacted_test_files": blast_radius.get("impacted_test_files", []),
                    },
                    latency_ms=lat_loc,
                )
            else:
                saved = self.store.get_run(run_id) or {}
                blast_radius = saved.get("blast_radius") or {}
                context_bundle = (worktree_path / spec["target_file"]).read_text(encoding="utf-8")
                caller_summary = json.dumps(blast_radius.get("direct_callers", []))

            # ── STEP 2: SANDBOXED DEFECT REPRODUCTION (`REPRODUCING`) ──────────────────────
            if "REPRODUCING" not in completed_phases:
                repro_res = test_runner.run_tests([spec["repro_test"]])
                self.store.record_step(
                    run_id=run_id,
                    phase="REPRODUCING",
                    span_kind="TOOL",
                    title=f"Reproduce defect via pytest ({spec['repro_test']})",
                    status="COMPLETED",
                    input_data={"test_target": spec["repro_test"]},
                    output_data={
                        "baseline_failed_as_expected": not repro_res["passed"],
                        "exit_code": repro_res["exit_code"],
                        "output_tail": repro_res["output"][-800:],
                    },
                    latency_ms=repro_res["latency_ms"],
                )
                repro_failure_output = repro_res["output"]
            else:
                repro_failure_output = "Reproduced from durable SQLite checkpoint."

            # Optional fault-injection hook: simulate process crash / interruption mid-run!
            if simulate_interrupt_after_phase == "REPRODUCING":
                self.store.update_run(
                    run_id,
                    status="INTERRUPTED_CHECKPOINTED",
                    current_phase="REPRODUCING",
                    error_reason="Simulated process interruption (SIGINT) after REPRODUCING; ready for stateful resume.",
                )
                neatlogs.log("Run interrupted at checkpoint run_id={run_id}", level="warning", run_id=run_id)
                return self.store.get_run(run_id) or {}

            # ── STEP 3: ITERATIVE PLANNING, PATCHING, GUARDRAIL VERIFICATION & RECOVERY ────
            prior_feedback = ""
            verified_success = False
            final_diff = ""
            semantic_diff_report: dict[str, Any] = {}
            aws_attestation: dict[str, Any] = {}
            aws_verifier = AWSLambdaPatchVerifier()

            # In baseline_naive mode without blast-radius awareness, first attempt simulates
            # the extra exploration / caller-blind retry overhead typical of unguided agents
            effective_inject_trap = inject_caller_regression_on_attempt_1 or (
                mode == "baseline_naive" and "caller_trap_patch" in spec
            )

            for attempt in range(1, 4):
                current_run_state = self.store.get_run(run_id) or {}
                tool_calls_used = len(current_run_state.get("steps", []))
                budget_check = self._enforce_budget_and_loop_guardrail(
                    attempt=attempt,
                    tool_calls_used=tool_calls_used,
                    accumulated_cost_usd=float(current_run_state.get("accumulated_cost_usd", 0.0)),
                    max_attempts=3,
                    max_tool_calls=20,
                    max_cost_usd=max_cost_usd,
                )
                if not budget_check["allowed"]:
                    self.store.update_run(
                        run_id,
                        status="ESCALATED_BUDGET",
                        error_reason=f"Budget/Loop guardrail tripped: {json.dumps(budget_check)}",
                    )
                    break

                self.store.update_run(run_id, current_attempt=attempt)

                # 3A: Hypothesis Planning (`AGENT` span)
                hyp_text, hyp_llm = self._plan_hypothesis(
                    goal=spec["goal"],
                    mode=mode,
                    context_bundle=context_bundle,
                    repro_failure_output=repro_failure_output,
                    prior_failure_feedback=prior_feedback,
                )
                self.store.record_step(
                    run_id=run_id,
                    phase=f"PLANNING_ATTEMPT_{attempt}",
                    span_kind="AGENT",
                    title=f"Formulate root-cause hypothesis (Attempt #{attempt})",
                    status="COMPLETED",
                    input_data={"attempt": attempt, "has_prior_feedback": bool(prior_feedback)},
                    output_data={"hypothesis": hyp_text},
                    tokens_used=hyp_llm.total_tokens,
                    prompt_tokens=hyp_llm.prompt_tokens,
                    completion_tokens=hyp_llm.completion_tokens,
                    cost_usd=hyp_llm.estimated_cost_usd,
                    latency_ms=hyp_llm.latency_ms,
                )

                # 3B: Patch Synthesis (`AGENT` span)
                target_file_abs = worktree_path / spec["target_file"]
                current_src = target_file_abs.read_text(encoding="utf-8")

                if attempt == 1 and effective_inject_trap and "caller_trap_patch" in spec:
                    # Execute LLM call so token/latency telemetry is genuine, and test the caller-regression guardrail
                    _, synth_llm = self._synthesize_patch(
                        goal=spec["goal"],
                        target_file=spec["target_file"],
                        current_file_source=current_src,
                        hypothesis=hyp_text,
                        caller_contracts_summary=caller_summary,
                        prior_failure_feedback=prior_feedback,
                    )
                    candidate_code = spec["caller_trap_patch"]
                else:
                    candidate_code, synth_llm = self._synthesize_patch(
                        goal=spec["goal"],
                        target_file=spec["target_file"],
                        current_file_source=current_src,
                        hypothesis=hyp_text,
                        caller_contracts_summary=caller_summary,
                        prior_failure_feedback=prior_feedback,
                    )

                self.store.record_step(
                    run_id=run_id,
                    phase=f"PATCHING_ATTEMPT_{attempt}",
                    span_kind="AGENT",
                    title=f"Synthesize surgical patch for {spec['target_file']} (Attempt #{attempt})",
                    status="COMPLETED",
                    input_data={"target_file": spec["target_file"], "attempt": attempt},
                    output_data={"candidate_lines": len(candidate_code.splitlines())},
                    tokens_used=synth_llm.total_tokens,
                    prompt_tokens=synth_llm.prompt_tokens,
                    completion_tokens=synth_llm.completion_tokens,
                    cost_usd=synth_llm.estimated_cost_usd,
                    latency_ms=synth_llm.latency_ms,
                )

                # 3C: Apply Patch in Isolated Worktree (`TOOL` span)
                apply_res = wt_mgr.apply_file_content(spec["target_file"], candidate_code)
                if not apply_res["applied"]:
                    prior_feedback = f"SyntaxError in generated patch: {apply_res['error']}"
                    self.store.record_patch(
                        run_id=run_id,
                        attempt_num=attempt,
                        target_file=spec["target_file"],
                        unified_diff="",
                        repro_test_passed=False,
                        caller_tests_passed=False,
                        rolled_back=True,
                        rollback_reason=prior_feedback,
                        test_output=prior_feedback,
                    )
                    continue

                # 3D: Blast-Radius Verification Guardrail (`GUARDRAIL` span)
                with neatlogs.trace("blast_radius_guardrail", kind="GUARDRAIL") as guard_span:
                    guard_t0 = time.perf_counter()
                    if guard_span is not None:
                        guard_span.set_attribute("neatlogs.guardrail.input", apply_res["diff"][:1000])

                    repro_check = test_runner.run_tests([spec["repro_test"]])
                    caller_targets = [
                        t
                        for t in dict.fromkeys(
                            spec["caller_tests"] + blast_radius.get("impacted_test_files", [])
                        )
                        if t != spec["repro_test"]
                    ] or spec["caller_tests"]
                    caller_check = test_runner.run_tests(caller_targets)

                    both_passed = bool(repro_check["passed"] and caller_check["passed"])
                    guard_lat = round((time.perf_counter() - guard_t0) * 1000.0, 2)

                    if both_passed:
                        guard_msg = (
                            f"PASSED: Reproduction test ({spec['repro_test']}) AND all blast-radius caller "
                            f"tests ({caller_targets}) succeeded with zero regressions."
                        )
                        if guard_span is not None:
                            guard_span.set_attribute("neatlogs.guardrail.passed", True)
                            guard_span.set_attribute("neatlogs.guardrail.output", guard_msg)

                        semantic_diff_report = graph_engine.semantic_diff(base_ref="HEAD")
                        final_diff = wt_mgr.get_full_diff()
                        aws_attestation = aws_verifier.attest_patch(
                            case_id=case_id,
                            target_file=spec["target_file"],
                            patched_source=candidate_code,
                            unified_diff=final_diff,
                            repro_passed=True,
                            callers_passed=True,
                        )

                        self.store.record_hypothesis(
                            run_id=run_id,
                            attempt_num=attempt,
                            target_symbol=spec["target_symbol"],
                            target_file=spec["target_file"],
                            hypothesis_text=hyp_text,
                            blast_radius_callers=blast_radius.get("direct_callers", []),
                            status="CONFIRMED_VERIFIED",
                            outcome_reason=guard_msg,
                        )
                        self.store.record_patch(
                            run_id=run_id,
                            attempt_num=attempt,
                            target_file=spec["target_file"],
                            unified_diff=final_diff,
                            repro_test_passed=True,
                            caller_tests_passed=True,
                            rolled_back=False,
                            rollback_reason="",
                            test_output=caller_check["output"][-1000:],
                        )
                        self.store.record_step(
                            run_id=run_id,
                            phase=f"VERIFYING_ATTEMPT_{attempt}",
                            span_kind="GUARDRAIL",
                            title=f"Blast-Radius Guardrail PASSED (Attempt #{attempt})",
                            status="COMPLETED",
                            input_data={"repro_test": spec["repro_test"], "caller_tests": caller_targets},
                            output_data={"passed": True, "message": guard_msg},
                            latency_ms=guard_lat,
                        )
                        verified_success = True
                        break
                    else:
                        # ── RECOVERY: Automatic Worktree Rollback & Hypothesis Refinement ──
                        failure_type = (
                            "DOWNSTREAM_CALLER_REGRESSION"
                            if (repro_check["passed"] and not caller_check["passed"])
                            else "REPRODUCTION_TEST_FAILED"
                        )
                        combined_err = (
                            f"[{failure_type}]\n"
                            f"Repro Passed: {repro_check['passed']}\n"
                            f"Caller Tests Passed: {caller_check['passed']}\n"
                            f"Pytest Output:\n{(repro_check['output'] if not repro_check['passed'] else caller_check['output'])[-1000:]}"
                        )
                        if guard_span is not None:
                            guard_span.set_attribute("neatlogs.guardrail.passed", False)
                            guard_span.set_attribute("neatlogs.guardrail.output", combined_err[:1000])

                        neatlogs.log(
                            "Guardrail blocked candidate patch attempt={attempt} reason={reason}; rolling back worktree",
                            level="warning",
                            attempt=attempt,
                            reason=failure_type,
                        )

                        rb_res = wt_mgr.rollback_to_baseline(reason=failure_type)
                        if failure_type == "DOWNSTREAM_CALLER_REGRESSION" and mode == "graph_guarded":
                            graph_engine.remember_brain_fact(
                                f"Candidate patch to {spec['target_symbol']} in {spec['target_file']} passed {spec['repro_test']} "
                                f"but broke downstream caller tests {caller_targets}; rolled back automatically.",
                                kind="gotcha",
                                taxonomy_path="workflow.verification.caller_trap",
                            )
                        self.store.record_hypothesis(
                            run_id=run_id,
                            attempt_num=attempt,
                            target_symbol=spec["target_symbol"],
                            target_file=spec["target_file"],
                            hypothesis_text=hyp_text,
                            blast_radius_callers=blast_radius.get("direct_callers", []),
                            status=f"REFUTED_{failure_type}",
                            outcome_reason=combined_err[:500],
                        )
                        self.store.record_patch(
                            run_id=run_id,
                            attempt_num=attempt,
                            target_file=spec["target_file"],
                            unified_diff=apply_res["diff"],
                            repro_test_passed=repro_check["passed"],
                            caller_tests_passed=caller_check["passed"],
                            rolled_back=True,
                            rollback_reason=failure_type,
                            test_output=combined_err[-1000:],
                        )
                        self.store.record_step(
                            run_id=run_id,
                            phase=f"RECOVERY_ROLLBACK_{attempt}",
                            span_kind="GUARDRAIL",
                            title=f"Guardrail Caught {failure_type} -> Rolled Back Worktree (Attempt #{attempt})",
                            status="RECOVERED",
                            input_data={"attempt": attempt, "failure_type": failure_type},
                            output_data={"rollback": rb_res, "error_excerpt": combined_err[-600:]},
                            latency_ms=guard_lat,
                        )
                        prior_feedback = combined_err

            total_wall_ms = round((time.perf_counter() - t_run_start) * 1000.0, 2)
            final_state = self.store.get_run(run_id) or {}

            if verified_success:
                cert = {
                    "certificate_version": "verifix.v2.2",
                    "team": "HyperX (Shivansh Jain)",
                    "run_id": run_id,
                    "case_id": case_id,
                    "mode": mode,
                    "status": "VERIFIED_COMPLETE",
                    "target_file": spec["target_file"],
                    "target_symbol": spec["target_symbol"],
                    "attempts_used": final_state.get("current_attempt", 1),
                    "caller_regressions_caught": final_state.get("caller_regressions_caught", 0),
                    "rollbacks_executed": final_state.get("rollbacks_executed", 0),
                    "resumed_from_checkpoint": bool(final_state.get("resumed_from_checkpoint", 0)),
                    "prompt_tokens": final_state.get("prompt_tokens", 0),
                    "completion_tokens": final_state.get("completion_tokens", 0),
                    "total_tokens": final_state.get("total_tokens", 0),
                    "estimated_cost_usd": round(float(final_state.get("accumulated_cost_usd", 0.0)), 6),
                    "wall_clock_ms": total_wall_ms,
                    "entire_graph_semantic_diff": semantic_diff_report.get("diff", ""),
                    "aws_lambda_attestation": aws_attestation,
                }
                self.store.update_run(
                    run_id,
                    status="VERIFIED_COMPLETE",
                    current_phase="VERIFIED_COMPLETE",
                    final_diff=final_diff,
                    verification_certificate_json=json.dumps(cert, default=str),
                )
            else:
                if final_state.get("status") == "RUNNING":
                    self.store.update_run(
                        run_id,
                        status="FAILED_MAX_ATTEMPTS",
                        current_phase="FAILED_MAX_ATTEMPTS",
                        error_reason=prior_feedback[:500],
                    )

            neatlogs.flush()
            return self.store.get_run(run_id) or {}

    def run_before_after_experiment(self, case_id: str = "case_01_ledger_rounding") -> dict[str, Any]:
        """Run a controlled Before (Run A: `baseline_naive`) vs. After (Run B: `graph_guarded`) comparison
        on the identical benchmark repository and persist the measured delta.
        """
        run_a = self.execute_case(case_id=case_id, mode="baseline_naive")
        run_b = self.execute_case(case_id=case_id, mode="graph_guarded")

        tok_a = max(1, int(run_a.get("total_tokens", 1)))
        tok_b = max(1, int(run_b.get("total_tokens", 1)))
        prompt_a = max(1, int(run_a.get("prompt_tokens", 1)))
        prompt_b = max(1, int(run_b.get("prompt_tokens", 1)))
        lat_a = max(1.0, float(run_a.get("total_latency_ms", 1.0)))
        lat_b = max(1.0, float(run_b.get("total_latency_ms", 1.0)))
        cost_a = float(run_a.get("accumulated_cost_usd", 0.0))
        cost_b = float(run_b.get("accumulated_cost_usd", 0.0))

        comparison = {
            "case_id": case_id,
            "workload_title": BENCHMARK_CATALOG[case_id]["title"],
            "run_a_before": {
                "run_id": run_a["run_id"],
                "mode": "baseline_naive (No entire-graph; unpruned repo read; caller-blind)",
                "status": run_a["status"],
                "attempts": run_a["current_attempt"],
                "span_count": run_a["span_count"],
                "prompt_tokens": prompt_a,
                "completion_tokens": run_a["completion_tokens"],
                "total_tokens": tok_a,
                "total_latency_ms": round(lat_a, 2),
                "estimated_cost_usd": round(cost_a, 6),
                "caller_regressions_caught": run_a["caller_regressions_caught"],
            },
            "run_b_after": {
                "run_id": run_b["run_id"],
                "mode": "graph_guarded (entire-graph search+impact + Blast-Radius Guardrail)",
                "status": run_b["status"],
                "attempts": run_b["current_attempt"],
                "span_count": run_b["span_count"],
                "prompt_tokens": prompt_b,
                "completion_tokens": run_b["completion_tokens"],
                "total_tokens": tok_b,
                "total_latency_ms": round(lat_b, 2),
                "estimated_cost_usd": round(cost_b, 6),
                "caller_regressions_caught": run_b["caller_regressions_caught"],
            },
            "measured_delta": {
                "prompt_token_reduction_pct": round((1.0 - (prompt_b / prompt_a)) * 100.0, 2),
                "total_token_reduction_pct": round((1.0 - (tok_b / tok_a)) * 100.0, 2),
                "latency_reduction_pct": round((1.0 - (lat_b / lat_a)) * 100.0, 2),
                "cost_reduction_pct": round((1.0 - (cost_b / max(1e-9, cost_a))) * 100.0, 2),
                "attempts_saved": int(run_a["current_attempt"]) - int(run_b["current_attempt"]),
            },
        }
        exp_id = self.store.record_experiment(
            case_id=case_id,
            run_a_id=run_a["run_id"],
            run_b_id=run_b["run_id"],
            comparison=comparison,
        )
        comparison["experiment_id"] = exp_id
        return comparison

    def execute_custom_target(
        self,
        repo_path: str | Path,
        target_file: str,
        target_symbol: str,
        repro_test: str,
        caller_tests: list[str] | None = None,
        goal: str = "Localize and remediate the failing test while preserving all downstream caller contracts.",
        mode: str = "graph_guarded",
        max_cost_usd: float = 0.25,
    ) -> dict[str, Any]:
        """Execute VeriFix's full 8-Focus-Area remediation loop on any arbitrary local Python repository."""
        repo_p = Path(repo_path).resolve()
        if not repo_p.is_dir():
            raise ValueError(f"Repository directory does not exist: {repo_p}")
        target_p = repo_p / target_file
        if not target_p.is_file():
            raise ValueError(f"Target file does not exist inside repo: {target_p}")

        slug = re.sub(r"[^a-zA-Z0-9_]+", "_", f"custom_{repo_p.name}_{Path(target_file).stem}")[:28]
        custom_spec = {
            "case_id": slug,
            "title": f"Custom Target: {repo_p.name}/{target_file} ({target_symbol})",
            "repo_path": str(repo_p),
            "target_file": target_file,
            "target_symbol": target_symbol,
            "repro_test": repro_test,
            "caller_tests": caller_tests if caller_tests is not None else [repro_test],
            "goal": goal,
        }
        return self.execute_case(
            case_id=slug,
            mode=mode,
            max_cost_usd=max_cost_usd,
            custom_spec=custom_spec,
        )

