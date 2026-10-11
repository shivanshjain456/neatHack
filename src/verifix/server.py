"""FastAPI Mission-Control Server & Interactive Web Dashboard for VeriFix."""

from __future__ import annotations
import logging

import base64
import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from verifix.agent_harness import BENCHMARK_CATALOG, VeriFixAgentHarness
from verifix.cfo_economics import CFOEconomicsEngine
from verifix.config import resolve_verifix_root_dir
from verifix.entire_intelligence import EntireIntelligenceEngine
from verifix.graph_engine import EntireGraphEngine, ensure_entire_plugins_restored, resolve_entire_binary
from verifix.incident_dispatcher import NeatlogsIncidentDispatcher
from verifix.neatlogs_mcp_client import NeatlogsMCPClient
from verifix.state_store import VeriFixStateStore
from verifix.config import load_env_if_present

_log = logging.getLogger(__name__)

load_env_if_present()

app = FastAPI(
    title="VeriFix Mission Control",
    description="Autonomous Blast-Radius-Aware Root-Cause & Verified-Patch Engineering Agent (neatHack 2026)",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://shivanshjain456.github.io"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOT_DIR = resolve_verifix_root_dir()


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunRequest(StrictRequest):
    case_id: str = Field(default="case_01_ledger_rounding", max_length=100)
    mode: Literal["graph_guarded", "baseline_naive"] = "graph_guarded"
    inject_caller_trap: bool = False
    interrupt_after_repro: bool = False


class ResumeRequest(StrictRequest):
    run_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")


class ExperimentRequest(StrictRequest):
    case_id: str = Field(default="case_01_ledger_rounding", max_length=100)


class GraphInspectRequest(StrictRequest):
    symbol: str = Field(default="calculate_tiered_fee", min_length=1, max_length=128, pattern=r"^[A-Za-z_][A-Za-z0-9_.]*$")


class CustomRunRequest(StrictRequest):
    repo_path: str
    target_file: str
    target_symbol: str
    repro_test: str
    caller_tests: str
    goal: str = "Fix the failing reproduction test while preserving all downstream caller contracts."
    mode: Literal["graph_guarded", "baseline_naive"] = "graph_guarded"


class AutoFixRequest(StrictRequest):
    repo_path: str
    goal: str = ""
    mode: Literal["graph_guarded", "baseline_naive"] = "graph_guarded"


class LivePlaygroundRequest(StrictRequest):
    target_symbol: str = "compute_invoice_total"
    module_code: str
    repro_test_code: str
    caller_test_code: str
    goal: str = "Fix the failing reproduction test in module.py while preserving all downstream caller contracts in test_callers.py."


class EntireIntelligenceRequest(StrictRequest):
    symbol: str = Field(default="calculate_tiered_fee", min_length=1, max_length=128, pattern=r"^[A-Za-z_][A-Za-z0-9_.]*$")
    case_id: str = Field(default="case_01_ledger_rounding", max_length=100)
    run_id: str | None = None


class DispatchIncidentRequest(StrictRequest):
    detection_name: str = "Downstream Caller Contract Regression Blocked"
    execute_live: bool = False


def _get_entire_git_telemetry() -> dict[str, Any]:
    """Read real Entire CLI status, checkpoint refs, and Git commit trailers from ROOT_DIR (with tracked snapshot fallback in serverless Lambda)."""
    snap_path = ROOT_DIR / "benchmarks" / "entire_telemetry_snapshot.json"
    if not (ROOT_DIR / ".git").exists() and snap_path.exists():
        try:
            return json.loads(snap_path.read_text(encoding="utf-8"))
        except Exception as exc:  # best-effort step; failure is logged, not hidden
            _log.warning("server.py:115 best-effort step failed: %s", exc)
    ensure_entire_plugins_restored()
    env = os.environ.copy()
    env["PATH"] = f"/home/user/bin:/home/user/.local/bin:{env.get('PATH', '')}"
    try:
        entire_bin = resolve_entire_binary()
        if entire_bin:
            st_proc = subprocess.run(
                [entire_bin, "status", "--json"],
                cwd=str(ROOT_DIR),
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            status_json = json.loads(st_proc.stdout) if st_proc.stdout.strip() else {}
        else:
            status_json = {}
    except Exception as exc:
        status_json = {"error": str(exc)}

    refs_proc = subprocess.run(
        ["git", "for-each-ref", "refs/entire/", "--format=%(refname) %(objectname:short)"],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        check=False,
    ) if shutil.which("git") else None
    entire_refs = [line.strip() for line in refs_proc.stdout.splitlines() if line.strip()] if refs_proc else []

    log_proc = subprocess.run(
        ["git", "log", "-n", "12", "--pretty=format:%h|%H|%ad|%s|%(trailers:key=Entire-Checkpoint,valueonly=true)", "--date=iso"],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        check=False,
    ) if shutil.which("git") else None
    commits = []
    for line in (log_proc.stdout.splitlines() if log_proc else []):
        parts = line.split("|")
        if len(parts) >= 4:
            commits.append(
                {
                    "hash": parts[0],
                    "full_hash": parts[1],
                    "date": parts[2],
                    "subject": parts[3],
                    "entire_checkpoint": parts[4].strip() if len(parts) > 4 else "",
                    "entire_io_url": f"https://entire.io/gh/shivanshjain456/neatHack/commit/{parts[1]}",
                }
            )
    if not commits and snap_path.exists():
        try:
            return json.loads(snap_path.read_text(encoding="utf-8"))
        except Exception as exc:  # best-effort step; failure is logged, not hidden
            _log.warning("server.py:170 best-effort step failed: %s", exc)
    brain_summary = EntireGraphEngine(ROOT_DIR).get_brain_summary()
    explain_text = ""
    tokens_text = ""
    why_text = ""
    graph_stats_text = ""
    brain_mcp_config = ""
    try:
        entire_bin = resolve_entire_binary()
        if entire_bin:
            exp_p = subprocess.run([entire_bin, "checkpoint", "explain", "HEAD"], cwd=str(ROOT_DIR), env=env, capture_output=True, text=True, timeout=10)
            explain_text = exp_p.stdout.strip()
            tok_p = subprocess.run([entire_bin, "checkpoint", "tokens", "HEAD"], cwd=str(ROOT_DIR), env=env, capture_output=True, text=True, timeout=10)
            tokens_text = tok_p.stdout.strip()
            why_p = subprocess.run([entire_bin, "why", "src/verifix/aws_verifier.py"], cwd=str(ROOT_DIR), env=env, capture_output=True, text=True, timeout=10)
            why_text = why_p.stdout.strip()
            gs_p = subprocess.run([entire_bin, "graph", "stats", "--repo", "."], cwd=str(ROOT_DIR), env=env, capture_output=True, text=True, timeout=10)
            graph_stats_text = gs_p.stdout.strip()
            mcp_p = subprocess.run([entire_bin, "brain", "mcp", "--print-config"], cwd=str(ROOT_DIR), env=env, capture_output=True, text=True, timeout=10)
            brain_mcp_config = mcp_p.stdout.strip()
    except Exception as exc:
        explain_text = f"explain note: {exc}"

    runners_dir = ROOT_DIR / ".entire" / "runners"
    runners_list = sorted(p.name for p in runners_dir.glob("*.json")) if runners_dir.is_dir() else []

    return {
        "entire_status": status_json,
        "entire_refs": entire_refs,
        "recent_commits": commits,
        "entire_brain": brain_summary,
        "checkpoint_explain_head": explain_text,
        "checkpoint_tokens_head": tokens_text,
        "entire_why_sample": why_text,
        "entire_graph_stats": graph_stats_text,
        "entire_brain_mcp_config": brain_mcp_config,
        "entire_trail_runners": runners_list,
    }


@app.get("/api/health")
def api_health() -> dict[str, Any]:
    return {"status": "ok", "service": "verifix-mission-control", "version": "0.4.1"}


def _build_pr_evidence_markdown(run: dict[str, Any]) -> str:
    cert = run.get("verification_certificate") or {}
    aws_att = cert.get("aws_lambda_attestation") or {}
    blast = run.get("blast_radius") or {}
    callers = blast.get("direct_callers") or []
    caller_lines = "\n".join(
        f"  - `{c.get('name')}` (`{c.get('file_path')}:{c.get('call_site_line')}`)"
        for c in callers
    ) or "  - Verified via repository test suite"
    steps_lines = "\n".join(
        f"| `{s.get('seq_num')}` | `{s.get('span_kind')}` | `{s.get('phase')}` | {s.get('title')} | `{s.get('latency_ms')} ms` | `{s.get('tokens_used')} tok` | `{s.get('status')}` |"
        for s in (run.get("steps") or [])
    )
    return (
        f"## VeriFix Verified Patch & Trace Evidence (`{run.get('run_id')}`)\n\n"
        f"- **Status**: `{run.get('status')}` (Attempts: `{run.get('current_attempt')}`, Rollbacks: `{run.get('rollbacks_executed')}`)\n"
        f"- **Target Symbol**: `{run.get('target_symbol')}` (`{run.get('case_id')}`, Mode: `{run.get('mode')}`)\n"
        f"- **Tokens & Cost**: `{run.get('total_tokens')} tokens` (Prompt: `{run.get('prompt_tokens')}`, Completion: `{run.get('completion_tokens')}`, Cost: `${run.get('accumulated_cost_usd', 0.0):.5f}`)\n"
        f"- **Neatlogs Project ID**: `00201e50-a8c9-42cf-84bf-116568a49cd5` (`workflow: defect-remediation`)\n"
        f"- **AWS Lambda (`us-east-1`) Patch Attestation**: `attested={aws_att.get('attested')}` · SHA-256 `{aws_att.get('sha256_attestation_digest') or aws_att.get('patch_sha256', 'N/A')}` · Request ID `{aws_att.get('aws_request_id') or aws_att.get('lambda_request_id', 'N/A')}`\n\n"
        f"### 1. Entire-Graph Blast-Radius Callers Verified (`entire graph impact`)\n"
        f"{caller_lines}\n\n"
        f"### 2. Neatlogs Span Execution Ledger\n"
        f"| # | Span Kind | Phase | Step Title | Latency | Tokens | Status |\n"
        f"| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
        f"{steps_lines}\n\n"
        f"### 3. Verified Unified Git Diff\n"
        f"```diff\n{run.get('final_diff') or ''}\n```\n"
    )


@app.get("/api/runs/{run_id}/pr-evidence")
def api_run_pr_evidence(run_id: str) -> dict[str, Any]:
    store = VeriFixStateStore()
    run = store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return {
        "run_id": run_id,
        "status": run.get("status"),
        "target_symbol": run.get("target_symbol"),
        "neatlogs_project_id": "00201e50-a8c9-42cf-84bf-116568a49cd5",
        "pr_markdown": _build_pr_evidence_markdown(run),
        "verification_certificate": run.get("verification_certificate"),
        "steps": run.get("steps"),
        "final_diff": run.get("final_diff"),
    }


@app.get("/runs/{run_id}/share", response_class=HTMLResponse)
def shareable_run_evidence_page(run_id: str) -> HTMLResponse:
    import html as _html

    store = VeriFixStateStore()
    run = store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    md_text = _build_pr_evidence_markdown(run)
    cert_json = json.dumps(run.get("verification_certificate") or {}, indent=2)
    steps_rows = "".join(
        f"<tr><td>{s.get('seq_num')}</td><td><code>{_html.escape(str(s.get('span_kind')))}</code></td>"
        f"<td><code>{_html.escape(str(s.get('phase')))}</code></td><td>{_html.escape(str(s.get('title')))}</td>"
        f"<td>{s.get('latency_ms')} ms</td><td>{s.get('tokens_used')}</td><td><code>{_html.escape(str(s.get('status')))}</code></td></tr>"
        for s in (run.get("steps") or [])
    )
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>VeriFix Shareable Trace &amp; PR Evidence — {_html.escape(run_id)}</title>
  <style>
    body {{ background:#0b0f19; color:#f8fafc; font-family:Inter,system-ui,sans-serif; margin:0; padding:28px; }}
    .wrap {{ max-width:1080px; margin:0 auto; }}
    .card {{ background:#111827; border:1px solid #1e293b; border-radius:10px; padding:18px; margin-bottom:18px; }}
    h1, h2, h3 {{ margin-top:0; color:#38bdf8; }}
    table {{ width:100%; border-collapse:collapse; font-size:13px; }}
    th, td {{ border-bottom:1px solid #1e293b; padding:8px; text-align:left; }}
    pre {{ background:#070a12; border:1px solid #1e293b; border-radius:8px; padding:12px; overflow-x:auto; color:#e2e8f0; font-size:12px; }}
    code {{ color:#38bdf8; }}
    .badge {{ display:inline-block; padding:4px 10px; border-radius:999px; background:rgba(16,185,129,0.18); color:#34d399; font-weight:700; font-size:12px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <h1>VeriFix Shareable PR &amp; Trace Evidence Bundle</h1>
        <span class="badge">{_html.escape(str(run.get('status')))}</span>
      </div>
      <p style="color:#94a3b8; font-size:13px;">
        <strong>Run ID:</strong> <code>{_html.escape(run_id)}</code> &nbsp;|&nbsp;
        <strong>Target Symbol:</strong> <code>{_html.escape(str(run.get('target_symbol')))}</code> &nbsp;|&nbsp;
        <strong>Neatlogs Project:</strong> <code>00201e50-a8c9-42cf-84bf-116568a49cd5</code> &nbsp;|&nbsp;
        <strong>Total Tokens:</strong> <code>{run.get('total_tokens')}</code> &nbsp;|&nbsp;
        <strong>Caller Regressions Caught:</strong> <code>{run.get('caller_regressions_caught')}</code>
      </p>
    </div>
    <div class="card">
      <h2>1. Neatlogs Span Execution Ledger ({len(run.get('steps') or [])} Spans)</h2>
      <table>
        <thead><tr><th>#</th><th>Span Kind</th><th>Phase</th><th>Step</th><th>Latency</th><th>Tokens</th><th>Status</th></tr></thead>
        <tbody>{steps_rows}</tbody>
      </table>
    </div>
    <div class="card">
      <h2>2. Verified Unified Git Diff</h2>
      <pre>{_html.escape(run.get('final_diff') or '')}</pre>
    </div>
    <div class="card">
      <h2>3. AWS Lambda (us-east-1) Cryptographic Certificate &amp; Guardrail Proof</h2>
      <pre>{_html.escape(cert_json)}</pre>
    </div>
    <div class="card">
      <h2>4. Ready-to-Paste GitHub Pull Request Evidence Markdown</h2>
      <pre>{_html.escape(md_text)}</pre>
    </div>
  </div>
</body>
</html>"""
    return HTMLResponse(content=page)



@app.get("/screenshots/{filename}")
def get_screenshot(filename: str) -> FileResponse:
    safe_name = Path(filename).name
    target = (ROOT_DIR / "docs" / "screenshots" / safe_name).resolve()
    if not target.exists() or target.parent != (ROOT_DIR / "docs" / "screenshots").resolve():
        raise HTTPException(status_code=404, detail="Screenshot not found")
    return FileResponse(str(target), media_type="image/png")


@app.get("/api/overview")
def api_overview() -> dict[str, Any]:
    harness = VeriFixAgentHarness(ROOT_DIR)
    runs = harness.store.list_runs(limit=30)
    detailed_runs = [harness.store.get_run(r["run_id"]) for r in runs[:12]]
    experiments = harness.store.list_experiments(limit=10)

    # Compute CFO model from latest experiment or latest runs
    if experiments:
        comp = experiments[0]["comparison"]
        ra, rb = comp["run_a_before"], comp["run_b_after"]
    cfo_model = CFOEconomicsEngine().build_model_from_telemetry(ra, rb) if experiments else None
    entire_info = _get_entire_git_telemetry()

    nl_traces_path = ROOT_DIR / "benchmarks" / "neatlogs_live_traces.json"
    nl_live = json.loads(nl_traces_path.read_text(encoding="utf-8")) if nl_traces_path.exists() else {}

    oss_bug_path = ROOT_DIR / "benchmarks" / "real_oss_bug_hunt_neatlogs_sdk.json"
    oss_bug = json.loads(oss_bug_path.read_text(encoding="utf-8")) if oss_bug_path.exists() else {}

    return {
        "benchmarks": list(BENCHMARK_CATALOG.values()),
        "runs": detailed_runs,
        "experiments": experiments,
        "cfo_model": cfo_model,
        "entire": entire_info,
        "neatlogs_live": nl_live,
        "real_oss_bug_hunt": oss_bug,
    }


PLAN_MILESTONE_MONTHS = (1, 6, 12, 24)
PLAN_FIELDS = ("total_customers", "total_monthly_revenue", "arr", "ebitda", "ending_cash")


def plan_projection(snapshot: Any) -> dict[str, Any] | None:
    """Milestones from the recalculated plan.xlsx snapshot, or None when it is missing or malformed."""
    try:
        months = {int(m["month"]): m for m in snapshot["months"]}
        rows = []
        for month in PLAN_MILESTONE_MONTHS:
            row = {"month": month}
            for key in PLAN_FIELDS:
                value = float(months[month][key])
                if value != value or value in (float("inf"), float("-inf")):
                    raise ValueError(f"non-finite {key} in month {month}")
                row[key] = value
            rows.append(row)
        lowest = snapshot["lowest_cash"]
        return {
            "source": str(snapshot["source"]),
            "label": str(snapshot["label"]),
            "milestones": rows,
            "first_positive_ebitda_month": int(snapshot["first_positive_ebitda_month"]),
            "lowest_cash": {"month": int(lowest["month"]), "ending_cash": float(lowest["ending_cash"])},
        }
    except (KeyError, TypeError, ValueError):
        return None


def controlled_experiment(main: Any, fault: Any) -> dict[str, Any] | None:
    """Compact, validated view of the controlled ablation (benchmarks/ablation_*.json); None if unusable."""
    try:
        summ = main["summary"]
        arms = {a: {k: summ["arms"][a][k] for k in ("runs", "judge_passed", "shipped_regressions", "mean_total_tokens",
                                                    "mean_latency_ms", "mean_attempts", "total_cost_usd")}
                for a in ("target_only", "baseline_naive", "graph_guarded")}
        comps = {}
        for name in ("graph_guarded_vs_baseline_naive", "graph_guarded_vs_target_only"):
            c = summ["comparisons"][name]
            comps[name] = {k: c[k] for k in ("pairs", "cases", "token_ratio_geo_mean", "token_ratio_ci95_cases",
                                             "token_ratio_ci95_pairs", "token_sign_test_p", "token_ratio_by_case",
                                             "judge_pass_only_graph", "judge_pass_only_other")}
            for key in ("token_ratio_geo_mean",):
                v = float(comps[name][key])
                if not (0 < v < 100):
                    raise ValueError("ratio out of range")
        records = main["records"]
        out = {"records": len(records), "design": main["design"], "arms": arms, "comparisons": comps,
               "first_recorded_at": min(r["recorded_at"] for r in records),
               "last_recorded_at": max(r["recorded_at"] for r in records),
               "models": sorted({m for r in records for m in r["models"]}), "fault_injection": None}
        if isinstance(fault, dict) and fault.get("summary"):
            fa = fault["summary"]["arms"]
            out["fault_injection"] = {
                "case_id": fault["records"][0]["case_id"], "design": fault["design"],
                "arms": {a: {k: fa[a][k] for k in ("runs", "judge_passed", "shipped_regressions", "mean_total_tokens")}
                         for a in ("target_only", "baseline_naive", "graph_guarded") if a in fa}}
        return out
    except (KeyError, TypeError, ValueError, IndexError):
        return None


RUN_SUMMARY_FIELDS = ("run_id", "case_id", "mode", "status", "target_symbol", "created_at", "updated_at", "current_attempt", "total_tokens", "prompt_tokens", "total_latency_ms", "accumulated_cost_usd", "rollbacks_executed")


@app.get("/api/workspace")
def api_workspace() -> dict[str, Any]:
    """Lightweight read-only first paint: actual records and labeled release snapshots."""
    store = VeriFixStateStore()
    experiments = [{k: v for k, v in e.items() if not k.endswith("_json")} for e in store.list_experiments(limit=10)]
    def snapshot(name: str):
        path = ROOT_DIR / "benchmarks" / name
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return None
    return {
        "schema_version": 1,
        "source": "instance SQLite records + release-time partner snapshots",
        "runs": [{k: r.get(k) for k in RUN_SUMMARY_FIELDS} for r in store.list_runs(limit=100)],
        "benchmarks": [{k: c.get(k) for k in ("case_id", "title", "target_symbol")} for c in BENCHMARK_CATALOG.values()],
        "experiments": experiments,
        "entire": snapshot("entire_telemetry_snapshot.json"),
        "cfo_model": CFOEconomicsEngine().build_model_from_telemetry(experiments[0]["comparison"]["run_a_before"], experiments[0]["comparison"]["run_b_after"]) if experiments else None,
        "plan_projection": plan_projection(snapshot("plan_xlsx_computed.json")),
        "controlled_experiment": controlled_experiment(snapshot("ablation_experiment.json"), snapshot("ablation_fault_injection.json")),
        "limitations": ["Run storage and rate limits are instance-local, not globally durable."],
    }


@app.get("/api/judge-proof")
def api_judge_proof() -> dict[str, Any]:
    """Official neatHack evidence checklist, each item checked LIVE or read from a RECORDED artifact."""
    from verifix.judge_proof import build_judge_proof

    ledger_path = ROOT_DIR / "benchmarks" / "verified_runs_ledger.json"
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.exists() else {}
    except (ValueError, OSError):
        ledger = {}
    search = None
    if os.environ.get("NEATLOGS_API_KEY", "").strip():
        search = lambda: NeatlogsMCPClient().search_traces(query="verifix", limit=10)  # noqa: E731
    return build_judge_proof(ROOT_DIR, ledger if isinstance(ledger, dict) else {}, search)


@app.get("/api/runs/{run_id}")
def api_run_detail(run_id: str) -> dict[str, Any]:
    import re
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", run_id):
        raise HTTPException(status_code=422, detail="Invalid run identifier")
    run = VeriFixStateStore().get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found in this instance or release ledger")
    from verifix.config import redact_secrets
    def clean(obj):
        if isinstance(obj, dict):
            return {k: clean(v) for k, v in obj.items() if not k.endswith("_json")}
        if isinstance(obj, list):
            return [clean(v) for v in obj]
        return obj
    return redact_secrets(clean(run))


@app.get("/api/selftest")
def api_selftest() -> dict[str, Any]:
    import importlib.util

    selftest_path = ROOT_DIR / "scripts" / "jury_selftest.py"
    spec = importlib.util.spec_from_file_location("jury_selftest", selftest_path)
    if spec and spec.loader:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.run_jury_selftest(ROOT_DIR)
    return {"all_passed": False, "error": "jury_selftest.py not found"}


@app.post("/api/run")
def api_trigger_run(req: RunRequest) -> dict[str, Any]:
    if req.case_id not in BENCHMARK_CATALOG:
        raise HTTPException(status_code=400, detail=f"Unknown case_id: {req.case_id}")
    harness = VeriFixAgentHarness(ROOT_DIR)
    result = harness.execute_case(
        case_id=req.case_id,
        mode=req.mode,
        inject_caller_regression_on_attempt_1=req.inject_caller_trap,
        simulate_interrupt_after_phase="REPRODUCING" if req.interrupt_after_repro else None,
    )
    return result


@app.post("/api/run-custom")
def api_trigger_custom_run(req: CustomRunRequest) -> dict[str, Any]:
    harness = VeriFixAgentHarness(ROOT_DIR)
    try:
        return harness.execute_custom_target(
            repo_path=req.repo_path,
            target_file=req.target_file,
            target_symbol=req.target_symbol,
            repro_test=req.repro_test,
            caller_tests=[c.strip() for c in req.caller_tests.split(",") if c.strip()] or [req.repro_test],
            goal=req.goal,
            mode=req.mode,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/auto-fix")
def api_trigger_auto_fix(req: AutoFixRequest) -> dict[str, Any]:
    harness = VeriFixAgentHarness(ROOT_DIR)
    try:
        return harness.auto_discover_and_execute(
            repo_path=req.repo_path,
            goal=req.goal,
            mode=req.mode,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/live-playground-fix")
def api_live_playground_fix(req: LivePlaygroundRequest) -> dict[str, Any]:
    """Create an isolated temporary Python repository from browser-submitted code & tests, and execute full VeriFix remediation."""
    playground_id = f"live_pg_{uuid.uuid4().hex[:8]}"
    pg_dir = Path("/tmp/verifix_live_playground") / playground_id
    if pg_dir.exists():
        shutil.rmtree(pg_dir)
    (pg_dir / "tests").mkdir(parents=True, exist_ok=True)
    (pg_dir / "module.py").write_text(req.module_code, encoding="utf-8")
    (pg_dir / "tests" / "test_repro.py").write_text(req.repro_test_code, encoding="utf-8")
    (pg_dir / "tests" / "test_callers.py").write_text(req.caller_test_code, encoding="utf-8")

    harness = VeriFixAgentHarness(ROOT_DIR)
    try:
        return harness.execute_custom_target(
            repo_path=pg_dir,
            target_file="module.py",
            target_symbol=req.target_symbol.strip() or "compute_invoice_total",
            repro_test="tests/test_repro.py",
            caller_tests=["tests/test_callers.py"],
            goal=req.goal,
            mode="graph_guarded",
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/resume")
def api_resume_run(req: ResumeRequest) -> dict[str, Any]:
    # Validate state before touching provider configuration: invalid resumes are
    # read-only errors and must work even if inference credentials are absent.
    store = VeriFixStateStore()
    existing = store.get_run(req.run_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Run {req.run_id} not found")
    if existing["case_id"] not in BENCHMARK_CATALOG or existing["status"] != "INTERRUPTED_CHECKPOINTED":
        raise HTTPException(status_code=409, detail="Only checkpointed catalog benchmarks can be resumed publicly")
    harness = VeriFixAgentHarness(ROOT_DIR, state_store=store)
    result = harness.execute_case(
        case_id=existing["case_id"],
        mode=existing["mode"],
        resume_run_id=req.run_id,
    )
    return result


@app.post("/api/experiment")
def api_trigger_experiment(req: ExperimentRequest) -> dict[str, Any]:
    harness = VeriFixAgentHarness(ROOT_DIR)
    return harness.run_before_after_experiment(case_id=req.case_id)


@app.post("/api/graph-inspect")
def api_graph_inspect(req: GraphInspectRequest) -> dict[str, Any]:
    engine = EntireGraphEngine(ROOT_DIR)
    return engine.analyze_blast_radius(req.symbol)


@app.get("/api/neatlogs-mcp")
def api_neatlogs_mcp() -> dict[str, Any]:
    client = NeatlogsMCPClient()
    whoami = client.whoami()
    traces = client.search_traces(limit=12)
    return {"whoami": whoami, "traces": traces}


@app.get("/api/neatlogs-trace-readback")
def api_neatlogs_trace_readback(trace_id: str | None = None) -> dict[str, Any]:
    """Client-side root-resolution fallback when Neatlogs remote traces are in `raw_durable` / `409 TRACE_PROCESSING`."""
    client = NeatlogsMCPClient()
    return client.resolve_raw_durable_trace(trace_or_run_id=trace_id)


class OnboardingQARequest(StrictRequest):
    question: str = "How does the Blast-Radius Guardrail work, and why was it designed this way?"
    use_live_llm: bool = False


@app.post("/api/entire-intelligence")
def api_entire_intelligence(req: EntireIntelligenceRequest) -> dict[str, Any]:
    eng = EntireIntelligenceEngine(ROOT_DIR)
    return {
        "ideas_covered": [
            "01_AGENT_MISTAKE_DEBUGGER",
            "02_INTENT_REVIEWER",
            "03_BEFORE_YOU_BUILD_ASSISTANT",
            "04_ARCHITECTURE_DRIFT_DETECTOR",
            "05_ONBOARDING_GUIDE_YOU_CAN_QUESTION",
            "06_REGRESSION_TEST_SCOUT",
            "07_CHECKPOINT_TO_DEMO_WALKTHROUGH",
            "08_EXTERNAL_AGENT_INTEGRATION_PROTOCOL_V1",
        ],
        "pre_build_briefing": eng.generate_pre_build_briefing(symbol=req.symbol, case_id=req.case_id),
        "intent_and_regression_review": eng.review_intent_and_scout_regressions(run_id=req.run_id),
    }


@app.post("/api/entire-onboarding-qa")
def api_entire_onboarding_qa(req: OnboardingQARequest) -> dict[str, Any]:
    eng = EntireIntelligenceEngine(ROOT_DIR)
    return eng.answer_onboarding_question(question=req.question, use_live_llm=req.use_live_llm)


@app.post("/api/dispatch-neatlogs-incident")
def api_dispatch_neatlogs_incident(req: DispatchIncidentRequest) -> dict[str, Any]:
    disp = NeatlogsIncidentDispatcher(ROOT_DIR)
    try:
        return disp.dispatch_incident(detection_name=req.detection_name, execute_live=req.execute_live)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/oss-bug-benchmark")
def api_oss_bug_benchmark() -> dict[str, Any]:
    """Execute a live 30-batch (6 threads x 5 batches) concurrency benchmark comparing neatlogs#199 vs PR #203."""
    import concurrent.futures
    import threading
    import time

    threads_count = 6
    batches_per_thread = 5
    total_batches = threads_count * batches_per_thread
    budget_sec = 0.080
    work_sec = 0.004

    # 1. Unpatched neatlogs#199 behavior: single non-blocking acquire(blocking=False) on 2-slot semaphore
    sem_v1 = threading.BoundedSemaphore(2)
    pool_v1 = concurrent.futures.ThreadPoolExecutor(max_workers=2)
    barrier_v1 = threading.Barrier(threads_count)
    dropped_v1 = 0
    lock_v1 = threading.Lock()
    t0_v1 = time.perf_counter()

    def worker_v1() -> None:
        nonlocal dropped_v1
        barrier_v1.wait()
        for _ in range(batches_per_thread):
            if not sem_v1.acquire(blocking=False):
                with lock_v1:
                    dropped_v1 += 1
                continue
            fut = pool_v1.submit(time.sleep, work_sec)
            fut.add_done_callback(lambda _f: sem_v1.release())
            fut.result(timeout=budget_sec)

    with concurrent.futures.ThreadPoolExecutor(max_workers=threads_count) as callers:
        list(callers.map(lambda _: worker_v1(), range(threads_count)))
    pool_v1.shutdown(wait=True)
    elapsed_v1_ms = round((time.perf_counter() - t0_v1) * 1000.0, 2)

    # 2. Patched neatlogs#203 behavior: deadline-bounded acquire(timeout=remaining) across shared _mask_pool
    sem_v2 = threading.BoundedSemaphore(2)
    pool_v2 = concurrent.futures.ThreadPoolExecutor(max_workers=2)
    barrier_v2 = threading.Barrier(threads_count)
    dropped_v2 = 0
    lock_v2 = threading.Lock()
    t0_v2 = time.perf_counter()

    def worker_v2() -> None:
        nonlocal dropped_v2
        barrier_v2.wait()
        for _ in range(batches_per_thread):
            deadline = time.monotonic() + budget_sec
            rem = max(0.0, deadline - time.monotonic())
            if not sem_v2.acquire(timeout=rem):
                with lock_v2:
                    dropped_v2 += 1
                continue
            fut = pool_v2.submit(time.sleep, work_sec)
            fut.add_done_callback(lambda _f: sem_v2.release())
            rem_exec = max(0.0, deadline - time.monotonic())
            fut.result(timeout=rem_exec)

    with concurrent.futures.ThreadPoolExecutor(max_workers=threads_count) as callers:
        list(callers.map(lambda _: worker_v2(), range(threads_count)))
    pool_v2.shutdown(wait=True)
    elapsed_v2_ms = round((time.perf_counter() - t0_v2) * 1000.0, 2)

    return {
        "issue": "https://github.com/neatlogs/neatlogs/issues/199",
        "pull_request": "https://github.com/neatlogs/neatlogs/pull/203",
        "threads": threads_count,
        "batches_per_thread": batches_per_thread,
        "total_batches": total_batches,
        "before_unpatched_199": {
            "dropped_batches": dropped_v1,
            "completed_batches": total_batches - dropped_v1,
            "drop_rate_pct": round((dropped_v1 / total_batches) * 100.0, 1),
            "elapsed_ms": elapsed_v1_ms,
        },
        "after_patched_pr_203": {
            "dropped_batches": dropped_v2,
            "completed_batches": total_batches - dropped_v2,
            "drop_rate_pct": round((dropped_v2 / total_batches) * 100.0, 1),
            "elapsed_ms": elapsed_v2_ms,
        },
        "aws_lambda_sha256": "58857f2d68ce1d5dfb40ac9dbe069772475bcb4880e24cc1ea24805d26d7523b",
    }


from verifix.dashboard import build_dashboard

DASHBOARD_HTML = build_dashboard()

from verifix.http_boundary import HTTPBoundary
app.add_middleware(HTTPBoundary, dashboard_html=DASHBOARD_HTML)


@app.get("/", response_class=HTMLResponse)
def serve_dashboard() -> HTMLResponse:
    return HTMLResponse(content=DASHBOARD_HTML)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Pure-Python ASGI-to-AWS-Lambda-Function-URL (payload v2.0 & v1.0) adapter for VeriFix Mission Control."""
    import asyncio
    from urllib.parse import urlencode

    http_ctx = (event.get("requestContext") or {}).get("http") or {}
    method = (http_ctx.get("method") or event.get("httpMethod") or "GET").upper()
    raw_path = event.get("rawPath") or event.get("path") or "/"
    raw_query = event.get("rawQueryString") or ""
    if not raw_query and event.get("queryStringParameters"):
        raw_query = urlencode(event["queryStringParameters"])

    headers_in = event.get("headers") or {}
    asgi_headers = [(k.lower().encode("latin-1"), str(v).encode("latin-1")) for k, v in headers_in.items() if v is not None]

    body_raw = event.get("body") or ""
    if event.get("isBase64Encoded") and body_raw:
        body_bytes = base64.b64decode(body_raw)
    elif isinstance(body_raw, bytes):
        body_bytes = body_raw
    else:
        body_bytes = str(body_raw).encode("utf-8")

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "https",
        "path": raw_path,
        "raw_path": raw_path.encode("latin-1"),
        "query_string": raw_query.encode("latin-1"),
        "root_path": "",
        "headers": asgi_headers,
        "client": (http_ctx.get("sourceIp") or "127.0.0.1", 443),
        "server": ((event.get("requestContext") or {}).get("domainName") or "lambda", 443),
    }

    response_status = 200
    response_headers: dict[str, str] = {}
    response_body_chunks: list[bytes] = []
    request_sent = False

    async def receive() -> dict[str, Any]:
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {"type": "http.request", "body": body_bytes, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        nonlocal response_status, response_headers
        if message["type"] == "http.response.start":
            response_status = int(message.get("status", 200))
            for hk, hv in message.get("headers", []):
                k_lower = hk.decode("latin-1").lower()
                if k_lower.startswith("access-control-"):
                    continue
                response_headers[k_lower] = hv.decode("latin-1")
        elif message["type"] == "http.response.body":
            chunk = message.get("body", b"")
            if chunk:
                response_body_chunks.append(chunk)

    asyncio.run(app(scope, receive, send))
    full_body = b"".join(response_body_chunks)
    ctype = response_headers.get("content-type", "application/json")
    is_binary = any(
        btype in ctype.lower()
        for btype in ("image/", "application/octet-stream", "application/zip", "video/", "audio/", "spreadsheetml")
    )
    if is_binary:
        return {
            "statusCode": response_status,
            "headers": response_headers,
            "body": base64.b64encode(full_body).decode("ascii"),
            "isBase64Encoded": True,
        }
    return {
        "statusCode": response_status,
        "headers": response_headers,
        "body": full_body.decode("utf-8", errors="replace"),
        "isBase64Encoded": False,
    }

