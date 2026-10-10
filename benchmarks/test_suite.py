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


def test_09_jury_selftest_detections_and_cfo_workbook():
    import importlib.util

    root_dir = Path(__file__).resolve().parents[1]
    selftest_path = root_dir / "scripts" / "jury_selftest.py"
    spec = importlib.util.spec_from_file_location("jury_selftest", selftest_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rep = mod.run_jury_selftest(root_dir)
    assert rep["all_passed"] is True
    assert rep["passed_count"] == 6


def test_10_entire_external_agent_plugin_and_live_oss_issue():
    import json
    import subprocess
    import sys

    root_dir = Path(__file__).resolve().parents[1]
    plugin = root_dir / "src" / "verifix" / "entire_agent_plugin.py"
    info_res = subprocess.run(
        [sys.executable, str(plugin), "info"],
        capture_output=True,
        text=True,
        check=True,
    )
    info = json.loads(info_res.stdout)
    assert info["protocol_version"] == 1
    assert info["name"] == "verifix"
    assert info["capabilities"]["hooks"] is True
    assert info["capabilities"]["transcript_analyzer"] is True

    oss_json = json.loads((root_dir / "benchmarks" / "real_oss_bug_hunt_neatlogs_sdk.json").read_text())
    assert oss_json["upstream_issue_url"] == "https://github.com/neatlogs/neatlogs/issues/199"
    assert oss_json["upstream_issue_number"] == "neatlogs#199"


def test_11_litellm_gateway_and_custom_repository_remediation(tmp_path: Path):
    from verifix.config import TracedLLMClient, get_litellm_base_url

    assert TracedLLMClient.LITELLM_MODEL_CASCADE[0] == "claude-sonnet-4.6"
    assert "litellm.vision.aivar.app/v1" in get_litellm_base_url()
    assert redact_secrets("sk-" + "IOxSrGkt5CHwoSmOD77IHQ") == "[REDACTED_SECRET]"

    # Create a brand-new arbitrary custom repository in tmp_path with a real bug
    custom_repo = tmp_path / "custom_discount_repo"
    (custom_repo / "billing").mkdir(parents=True)
    (custom_repo / "tests").mkdir(parents=True)
    (custom_repo / "billing" / "__init__.py").write_text("", encoding="utf-8")
    (custom_repo / "billing" / "discount.py").write_text(
        '''"""Custom billing discount engine with a subtle truncation bug."""

def compute_loyalty_discount_cents(subtotal_cents: int, discount_bps: int, cap_cents: int = 5000) -> int:
    if subtotal_cents <= 0 or discount_bps <= 0:
        return 0
    # BUG: floor division truncates fractional cents instead of half-to-even round()
    raw_discount = (subtotal_cents * discount_bps) // 10_000
    return min(raw_discount, cap_cents)
''',
        encoding="utf-8",
    )
    (custom_repo / "billing" / "invoice.py").write_text(
        '''"""Downstream caller of compute_loyalty_discount_cents."""
from billing.discount import compute_loyalty_discount_cents

def generate_net_invoice_cents(subtotal_cents: int, discount_bps: int, cap_cents: int = 5000) -> dict:
    disc = compute_loyalty_discount_cents(subtotal_cents, discount_bps, cap_cents=cap_cents)
    return {"subtotal_cents": subtotal_cents, "discount_cents": disc, "net_cents": subtotal_cents - disc}
''',
        encoding="utf-8",
    )
    (custom_repo / "tests" / "test_discount.py").write_text(
        '''from billing.discount import compute_loyalty_discount_cents

def test_half_to_even_rounding_on_discount():
    # 1999 * 175 / 10000 = 34.9825 -> rounds to 35 cents (floor division gives 34)
    assert compute_loyalty_discount_cents(1999, 175) == 35
''',
        encoding="utf-8",
    )
    (custom_repo / "tests" / "test_invoice_callers.py").write_text(
        '''from billing.invoice import generate_net_invoice_cents

def test_downstream_invoice_caller_contract():
    res = generate_net_invoice_cents(1999, 175, cap_cents=5000)
    assert res == {"subtotal_cents": 1999, "discount_cents": 35, "net_cents": 1964}
    capped = generate_net_invoice_cents(100_000, 1000, cap_cents=5000)
    assert capped["discount_cents"] == 5000
''',
        encoding="utf-8",
    )

    store = VeriFixStateStore(tmp_path / "test_custom_target.db")
    harness = VeriFixAgentHarness(root_dir=ROOT_DIR, state_store=store)
    result = harness.execute_custom_target(
        repo_path=custom_repo,
        target_file="billing/discount.py",
        target_symbol="compute_loyalty_discount_cents",
        repro_test="tests/test_discount.py",
        caller_tests=["tests/test_invoice_callers.py"],
        goal="Use Python round((subtotal_cents * discount_bps) / 10_000) instead of integer floor division // while preserving the cap_cents keyword argument and return type.",
        mode="graph_guarded",
    )
    assert result["status"] == "VERIFIED_COMPLETE"
    assert "round(" in result["final_diff"]
    assert result["verification_certificate"]["aws_lambda_attestation"]["attested"] is True


def test_12_zero_config_auto_discover_and_heal_repository(tmp_path: Path):
    # Create an unfamiliar Python repo with a failing test and a passing downstream caller test,
    # then pass ONLY repo_path to auto_discover_and_execute (zero manual target/symbol/test flags).
    auto_repo = tmp_path / "unfamiliar_inventory_repo"
    (auto_repo / "inventory").mkdir(parents=True)
    (auto_repo / "tests").mkdir(parents=True)
    (auto_repo / "inventory" / "__init__.py").write_text("", encoding="utf-8")
    (auto_repo / "inventory" / "reorder.py").write_text(
        '''"""Inventory reorder quantity calculator with an off-by-one safety stock bug."""

def compute_reorder_units(current_stock: int, target_stock: int, min_batch: int = 10) -> int:
    if current_stock >= target_stock:
        return 0
    # BUG: subtracts 1 from needed units instead of exact target_stock - current_stock
    needed = (target_stock - current_stock) - 1
    return max(needed, min_batch)
''',
        encoding="utf-8",
    )
    (auto_repo / "inventory" / "purchasing.py").write_text(
        '''"""Downstream caller of compute_reorder_units."""
from inventory.reorder import compute_reorder_units

def build_purchase_order(sku: str, current_stock: int, target_stock: int, min_batch: int = 10) -> dict:
    qty = compute_reorder_units(current_stock, target_stock, min_batch=min_batch)
    return {"sku": sku, "order_qty": qty, "needs_order": qty > 0}
''',
        encoding="utf-8",
    )
    (auto_repo / "tests" / "test_reorder.py").write_text(
        '''from inventory.reorder import compute_reorder_units

def test_exact_reorder_deficit():
    assert compute_reorder_units(25, 50, min_batch=10) == 25
''',
        encoding="utf-8",
    )
    (auto_repo / "tests" / "test_purchasing_callers.py").write_text(
        '''from inventory.purchasing import build_purchase_order

def test_purchase_order_contract():
    po = build_purchase_order("SKU-9", 45, 50, min_batch=10)
    assert po == {"sku": "SKU-9", "order_qty": 10, "needs_order": True}
    no_po = build_purchase_order("SKU-9", 60, 50, min_batch=10)
    assert no_po == {"sku": "SKU-9", "order_qty": 0, "needs_order": False}
''',
        encoding="utf-8",
    )

    store = VeriFixStateStore(tmp_path / "test_auto_discover.db")
    harness = VeriFixAgentHarness(root_dir=ROOT_DIR, state_store=store)
    res = harness.auto_discover_and_execute(repo_path=auto_repo)
    assert res["status"] == "VERIFIED_COMPLETE"
    disc = res["auto_discovery"]
    assert disc["target_file"] == "inventory/reorder.py"
    assert disc["target_symbol"] == "compute_reorder_units"
    assert disc["repro_test"] == "tests/test_reorder.py"
    assert "tests/test_purchasing_callers.py" in disc["caller_tests"]
    assert res["verification_certificate"]["aws_lambda_attestation"]["attested"] is True


def test_13_shareable_pr_and_trace_evidence_endpoints():
    from verifix.server import api_run_pr_evidence, shareable_run_evidence_page

    ev = api_run_pr_evidence("run_graph_case_01_le_3061")
    assert ev["run_id"] == "run_graph_case_01_le_3061"
    assert ev["status"] == "VERIFIED_COMPLETE"
    assert "Neatlogs Span Execution Ledger" in ev["pr_markdown"]
    assert "Verified Unified Git Diff" in ev["pr_markdown"]

    html_resp = shareable_run_evidence_page("run_graph_case_01_le_3061")
    assert html_resp.status_code == 200
    assert "VeriFix Shareable PR &amp; Trace Evidence Bundle" in html_resp.body.decode("utf-8")


def test_14_live_playground_fix_and_lambda_asgi_handler():
    import json
    from verifix.server import lambda_handler

    health = lambda_handler({"rawPath": "/api/health", "requestContext": {"http": {"method": "GET"}}}, None)
    assert health["statusCode"] == 200
    assert '"status":"ok"' in health["body"]

    pg_payload = {
        "target_symbol": "compute_invoice_total",
        "module_code": (
            "def compute_invoice_total(subtotal_cents: int, discount_bps: int) -> tuple[int, int]:\n"
            "    discount_cents = (subtotal_cents * discount_bps) // 10000\n"
            "    net_cents = subtotal_cents - discount_cents\n"
            "    return net_cents, discount_cents\n"
        ),
        "repro_test_code": (
            "from module import compute_invoice_total\n"
            "def test_half_up_rounding_and_cap():\n"
            "    net, disc = compute_invoice_total(150, 333)\n"
            "    assert disc == 5 and net == 145\n"
            "    net_cap, disc_cap = compute_invoice_total(200, 15000)\n"
            "    assert disc_cap == 200 and net_cap == 0\n"
        ),
        "caller_test_code": (
            "from module import compute_invoice_total\n"
            "def settle_merchant_payout(subtotal_cents: int, discount_bps: int) -> dict:\n"
            "    net_cents, discount_cents = compute_invoice_total(subtotal_cents, discount_bps)\n"
            "    return {'net': net_cents, 'discount': discount_cents}\n"
            "def test_downstream_settlement_contract():\n"
            "    assert settle_merchant_payout(10000, 250) == {'net': 9750, 'discount': 250}\n"
        ),
    }
    resp = lambda_handler(
        {
            "rawPath": "/api/live-playground-fix",
            "headers": {"content-type": "application/json"},
            "body": json.dumps(pg_payload),
            "requestContext": {"http": {"method": "POST"}},
        },
        None,
    )
    assert resp["statusCode"] == 200
    parsed = json.loads(resp["body"])
    assert parsed["status"] == "VERIFIED_COMPLETE"
    assert "module.py" in (parsed.get("final_diff") or "")







