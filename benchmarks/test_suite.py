"""Automated Verification, Fault-Injection, and Integration Test Suite for VeriFix."""

from __future__ import annotations

from pathlib import Path
import pytest

from verifix.agent_harness import VeriFixAgentHarness
from verifix.aws_verifier import AWSLambdaPatchVerifier
from verifix.cfo_economics import CFOEconomicsEngine
from verifix.config import redact_secrets
from verifix.graph_engine import EntireGraphEngine
from verifix.neatlogs_mcp_client import NeatlogsMCPClient
from verifix.state_store import VeriFixStateStore
from verifix.worktree_manager import WorktreeManager


ROOT_DIR = Path("/home/user/verifix")


def test_secret_redaction_mask():
    sample = {
        "api_key": "AIza" + "SyD1234567890abcdefghijklmnop",
        "neatlogs": "AQ." + "Ab8RN6L1234567890abcdefghijklmnop",
        "nested": ["Bearer " + "secret_token_1234567890abcdef"],
    }
    scrubbed = redact_secrets(sample)
    assert scrubbed["api_key"] == "[REDACTED_SECRET]"
    assert scrubbed["neatlogs"] == "[REDACTED_SECRET]"
    assert scrubbed["nested"][0] == "[REDACTED_SECRET]"


def test_entire_graph_blast_radius_localization():
    engine = EntireGraphEngine(ROOT_DIR)
    blast = engine.analyze_blast_radius("calculate_tiered_fee")
    assert blast["symbol"] == "calculate_tiered_fee"
    caller_names = {c["name"] for c in blast["direct_callers"]}
    assert "calculate_split_fees" in caller_names
    assert "build_settlement_batch" in caller_names
    assert "render_tax_invoice" in caller_names
    assert any("test_settlement.py" in f for f in blast["impacted_test_files"])


def test_worktree_security_and_atomic_rollback(tmp_path: Path):
    source_repo = ROOT_DIR / "benchmarks/repos/case_01_ledger_rounding"
    wt = WorktreeManager(source_repo, run_id="test_wt_security", base_dir=tmp_path)
    wt_path = wt.prepare()
    assert (wt_path / ".git").is_dir()

    # Path traversal outside worktree must raise PermissionError
    with pytest.raises(PermissionError):
        wt.resolve_safe_path("../../etc/passwd")
    with pytest.raises(PermissionError):
        wt.resolve_safe_path(".env")

    # Syntax-invalid Python patch must be rejected cleanly without corrupting file
    bad_res = wt.apply_file_content("ledger/fees.py", "def broken_syntax(:\n    pass\n")
    assert bad_res["applied"] is False
    assert bad_res["syntax_valid"] is False

    # Valid modification followed by atomic rollback restores clean git diff
    orig_text = (wt_path / "ledger/fees.py").read_text(encoding="utf-8")
    mod_res = wt.apply_file_content("ledger/fees.py", orig_text + "\n# temporary comment\n")
    assert mod_res["applied"] is True
    assert wt.get_full_diff() != ""

    wt.rollback_to_baseline(reason="unit_test_rollback")
    assert wt.get_full_diff() == ""
    assert (wt_path / "ledger/fees.py").read_text(encoding="utf-8") == orig_text


def test_cfo_economics_deterministic_model():
    eng = CFOEconomicsEngine()
    model = eng.build_model_from_telemetry(
        measured_run_a={"prompt_tokens": 3600, "completion_tokens": 900, "attempts": 2, "total_latency_ms": 6000},
        measured_run_b={"prompt_tokens": 1150, "completion_tokens": 420, "attempts": 1, "total_latency_ms": 2200},
    )
    assert model["telemetry_provenance"]["measured_improvements"]["token_reduction_pct"] > 50.0
    main_q4 = model["scenarios"]["Main (Graph-Optimized Base Plan)"][-1]
    down_q4 = model["scenarios"]["Downside (Unoptimized Grep + High Retry Burn)"][-1]
    assert main_q4["gross_margin_pct"] > 80.0
    assert main_q4["gross_margin_pct"] > down_q4["gross_margin_pct"]
    assert len(model["cfo_ai_mcp_payloads"]) == 2


def test_live_neatlogs_mcp_whoami():
    client = NeatlogsMCPClient()
    info = client.whoami()
    assert "project_id" in info
    assert info["project_id"] == "00201e50-a8c9-42cf-84bf-116568a49cd5"


def test_stateful_interruption_and_checkpoint_resumption(tmp_path: Path):
    store = VeriFixStateStore(tmp_path / "test_resume.db")
    harness = VeriFixAgentHarness(root_dir=ROOT_DIR, state_store=store)

    # 1. Start run and simulate process interruption after REPRODUCING
    interrupted = harness.execute_case(
        case_id="case_04_dag_scheduler",
        mode="graph_guarded",
        simulate_interrupt_after_phase="REPRODUCING",
    )
    assert interrupted["status"] == "INTERRUPTED_CHECKPOINTED"
    assert interrupted["current_phase"] == "REPRODUCING"
    run_id = interrupted["run_id"]

    # 2. Resume from SQLite WAL state without re-running completed steps
    resumed = harness.execute_case(
        case_id="case_04_dag_scheduler",
        mode="graph_guarded",
        resume_run_id=run_id,
    )
    assert resumed["status"] == "VERIFIED_COMPLETE"
    assert resumed["resumed_from_checkpoint"] == 1
    assert resumed["final_diff"] != ""


def test_caller_trap_guardrail_rollback_and_recovery(tmp_path: Path):
    store = VeriFixStateStore(tmp_path / "test_trap.db")
    harness = VeriFixAgentHarness(root_dir=ROOT_DIR, state_store=store)
    res = harness.execute_case(
        case_id="case_01_ledger_rounding",
        mode="graph_guarded",
        inject_caller_regression_on_attempt_1=True,
    )
    assert res["status"] == "VERIFIED_COMPLETE"
    assert res["caller_regressions_caught"] == 1
    assert res["rollbacks_executed"] >= 1
    assert res["current_attempt"] == 2
    cert = res.get("verification_certificate", {})
    assert cert.get("aws_lambda_attestation", {}).get("attested") is True


def test_entire_brain_and_aws_lambda_attestation():
    engine = EntireGraphEngine(ROOT_DIR)
    brain_res = engine.recall_brain_facts("calculate_tiered_fee")
    assert brain_res["exit_code"] == 0
    assert "calculate_tiered_fee" in brain_res["facts_text"]

    verifier = AWSLambdaPatchVerifier()
    att = verifier.attest_patch(
        case_id="case_01_ledger_rounding",
        target_file="ledger/fees.py",
        patched_source="def calculate_tiered_fee(amount_cents: int, tier_bps: int, min_fee_cents: int = 50) -> int:\n    return 584\n",
        unified_diff="+ return 584",
        repro_passed=True,
        callers_passed=True,
    )
    assert att["attested"] is True
    assert att["team"] == "HyperX"
    assert att["aws_region"] == "us-east-1"


