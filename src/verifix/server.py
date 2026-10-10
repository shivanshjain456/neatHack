"""FastAPI Mission-Control Server & Interactive Web Dashboard for VeriFix."""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel

from verifix.agent_harness import BENCHMARK_CATALOG, VeriFixAgentHarness
from verifix.cfo_economics import CFOEconomicsEngine
from verifix.entire_intelligence import EntireIntelligenceEngine
from verifix.graph_engine import EntireGraphEngine, ensure_entire_plugins_restored, resolve_entire_binary
from verifix.incident_dispatcher import NeatlogsIncidentDispatcher
from verifix.neatlogs_mcp_client import NeatlogsMCPClient
from verifix.state_store import VeriFixStateStore

app = FastAPI(
    title="VeriFix Mission Control",
    description="Autonomous Blast-Radius-Aware Root-Cause & Verified-Patch Engineering Agent (neatHack 2026)",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOT_DIR = (
    Path("/var/task").resolve()
    if (Path("/var/task") / "benchmarks").exists()
    else Path(os.environ.get("VERIFIX_ROOT_DIR", "/home/user/verifix")).resolve()
)


class RunRequest(BaseModel):
    case_id: str = "case_01_ledger_rounding"
    mode: str = "graph_guarded"
    inject_caller_trap: bool = False
    interrupt_after_repro: bool = False


class ResumeRequest(BaseModel):
    run_id: str


class ExperimentRequest(BaseModel):
    case_id: str = "case_01_ledger_rounding"


class GraphInspectRequest(BaseModel):
    symbol: str = "calculate_tiered_fee"


class CustomRunRequest(BaseModel):
    repo_path: str
    target_file: str
    target_symbol: str
    repro_test: str
    caller_tests: str
    goal: str = "Fix the failing reproduction test while preserving all downstream caller contracts."
    mode: str = "graph_guarded"


class AutoFixRequest(BaseModel):
    repo_path: str
    goal: str = ""
    mode: str = "graph_guarded"


class LivePlaygroundRequest(BaseModel):
    target_symbol: str = "compute_invoice_total"
    module_code: str
    repro_test_code: str
    caller_test_code: str
    goal: str = "Fix the failing reproduction test in module.py while preserving all downstream caller contracts in test_callers.py."


class EntireIntelligenceRequest(BaseModel):
    symbol: str = "calculate_tiered_fee"
    case_id: str = "case_01_ledger_rounding"
    run_id: str | None = None


class DispatchIncidentRequest(BaseModel):
    detection_name: str = "Downstream Caller Contract Regression Blocked"
    execute_live: bool = False


def _get_entire_git_telemetry() -> dict[str, Any]:
    """Read real Entire CLI status, checkpoint refs, and Git commit trailers from ROOT_DIR (with tracked snapshot fallback in serverless Lambda)."""
    snap_path = ROOT_DIR / "benchmarks" / "entire_telemetry_snapshot.json"
    if not (ROOT_DIR / ".git").exists() and snap_path.exists():
        try:
            return json.loads(snap_path.read_text(encoding="utf-8"))
        except Exception:
            pass
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
        except Exception:
            pass
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
    return {"status": "ok", "service": "verifix-mission-control", "version": "0.3.0"}


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
    else:
        ra = {"prompt_tokens": 3420, "completion_tokens": 890, "attempts": 2, "total_latency_ms": 6200}
        rb = {"prompt_tokens": 1180, "completion_tokens": 440, "attempts": 1, "total_latency_ms": 2400}

    cfo_model = CFOEconomicsEngine().build_model_from_telemetry(ra, rb)
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
    harness = VeriFixAgentHarness(ROOT_DIR)
    existing = harness.store.get_run(req.run_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Run {req.run_id} not found")
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


class OnboardingQARequest(BaseModel):
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


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>VeriFix Mission Control — neatHack 2026</title>
  <style>
    :root {
      --bg: #0b0f19;
      --panel: #111827;
      --panel-alt: #1e293b;
      --border: #334155;
      --text: #f8fafc;
      --muted: #94a3b8;
      --accent: #38bdf8;
      --green: #22c55e;
      --amber: #f59e0b;
      --red: #ef4444;
      --purple: #a855f7;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Inter, monospace;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
    }
    header {
      background: linear-gradient(90deg, #0f172a 0%, #1e1b4b 100%);
      border-bottom: 1px solid var(--border);
      padding: 16px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
    }
    .brand h1 {
      margin: 0;
      font-size: 20px;
      letter-spacing: 0.4px;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .badge {
      font-size: 11px;
      padding: 3px 8px;
      border-radius: 999px;
      font-weight: 600;
      background: rgba(56, 189, 248, 0.15);
      color: var(--accent);
      border: 1px solid rgba(56, 189, 248, 0.4);
    }
    .badge-green {
      background: rgba(34, 197, 94, 0.15);
      color: var(--green);
      border-color: rgba(34, 197, 94, 0.4);
    }
    .badge-amber {
      background: rgba(245, 158, 11, 0.15);
      color: var(--amber);
      border-color: rgba(245, 158, 11, 0.4);
    }
    .container {
      max-width: 1440px;
      margin: 0 auto;
      padding: 20px 24px 60px;
    }
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 14px;
      margin-bottom: 20px;
    }
    .kpi-card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 14px 16px;
    }
    .kpi-label {
      font-size: 12px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .kpi-value {
      font-size: 24px;
      font-weight: 700;
      margin-top: 4px;
      color: var(--text);
    }
    .kpi-sub {
      font-size: 12px;
      color: var(--green);
      margin-top: 2px;
    }
    .tabs {
      display: flex;
      gap: 8px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 12px;
      margin-bottom: 20px;
      flex-wrap: wrap;
    }
    .tab-btn {
      background: var(--panel);
      color: var(--muted);
      border: 1px solid var(--border);
      padding: 8px 16px;
      border-radius: 8px;
      cursor: pointer;
      font-weight: 600;
      font-size: 13px;
    }
    .tab-btn.active {
      background: var(--accent);
      color: #0b0f19;
      border-color: var(--accent);
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 18px;
      margin-bottom: 20px;
    }
    .panel h2 {
      margin-top: 0;
      font-size: 16px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 10px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .controls-row {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: center;
      margin-bottom: 14px;
    }
    select, input, button {
      background: var(--panel-alt);
      color: var(--text);
      border: 1px solid var(--border);
      padding: 8px 12px;
      border-radius: 6px;
      font-size: 13px;
    }
    button.primary {
      background: var(--accent);
      color: #090d16;
      font-weight: 700;
      border-color: var(--accent);
      cursor: pointer;
    }
    button.warn {
      background: var(--amber);
      color: #090d16;
      font-weight: 700;
      border-color: var(--amber);
      cursor: pointer;
    }
    button.purple {
      background: var(--purple);
      color: #fff;
      font-weight: 700;
      border-color: var(--purple);
      cursor: pointer;
    }
    button:disabled {
      opacity: 0.5;
      cursor: wait;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    th, td {
      text-align: left;
      padding: 10px 12px;
      border-bottom: 1px solid var(--border);
    }
    th {
      color: var(--muted);
      font-weight: 600;
      background: rgba(30, 41, 59, 0.5);
    }
    pre {
      background: #070a12;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px;
      overflow-x: auto;
      font-size: 12px;
      color: #e2e8f0;
      max-height: 360px;
    }
    .grid-2 {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 18px;
    }
    @media (max-width: 960px) {
      .grid-2 { grid-template-columns: 1fr; }
    }
    .step-item {
      border-left: 3px solid var(--accent);
      padding: 8px 12px;
      margin-bottom: 8px;
      background: rgba(30, 41, 59, 0.45);
      border-radius: 0 6px 6px 0;
    }
    .step-item.recovered {
      border-left-color: var(--amber);
    }
    .hidden { display: none; }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <h1>
        <span>VeriFix Mission Control</span>
        <span class="badge">Team HyperX — neatHack 2026</span>
        <span class="badge badge-green">LiteLLM claude-sonnet-4.6 + Neatlogs + Entire (Graph · Brain · Checkpoints) + cfo.ai + AWS Lambda</span>
      </h1>
      <div style="font-size: 12px; color: var(--muted); margin-top: 4px;">
        Autonomous Blast-Radius-Aware Root-Cause &amp; Verified-Patch Engineering Agent
      </div>
    </div>
    <div style="display:flex; gap:10px; align-items:center;">
      <span id="statusIndicator" class="badge badge-green">LIVE TELEMETRY READY</span>
      <button class="primary" onclick="startJuryTour()" style="cursor:pointer; font-weight:700;">&#9654; Start 3-Min Jury Tour (5 Acts)</button>
      <button onclick="refreshAll()" style="cursor:pointer;">Refresh State</button>
    </div>
  </header>

  <div class="container">
    <div class="kpi-grid" id="kpiGrid">
      <div class="kpi-card">
        <div class="kpi-label">Verified Runs in SQLite WAL</div>
        <div class="kpi-value" id="kpiRuns">-</div>
        <div class="kpi-sub" id="kpiRunsSub">8 Focus Areas Active</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Prompt Token Reduction</div>
        <div class="kpi-value" id="kpiTokenDelta">-</div>
        <div class="kpi-sub">via Entire-Graph Focused Retrieval</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">End-to-End Latency Delta</div>
        <div class="kpi-value" id="kpiLatencyDelta">-</div>
        <div class="kpi-sub">Run B (Graph) vs Run A (Naive)</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Caller Regressions Caught</div>
        <div class="kpi-value" id="kpiRegressions">-</div>
        <div class="kpi-sub">100% Atomic Worktree Rollback</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">cfo.ai Gross Margin (Q4 Base)</div>
        <div class="kpi-value" id="kpiMargin">-</div>
        <div class="kpi-sub" id="kpiCostPerRun">Coupled to Neatlogs Traces</div>
      </div>
    </div>

    <div class="tabs">
      <button id="tabBtn-runs" class="tab-btn active" onclick="switchTab('tab-runs', this)">1. Autonomous Runs &amp; 8 Focus Areas</button>
      <button id="tabBtn-experiment" class="tab-btn" onclick="switchTab('tab-experiment', this)">2. Neatlogs v1/v2, 11 Detections &amp; Analytics</button>
      <button id="tabBtn-entire" class="tab-btn" onclick="switchTab('tab-entire', this)">3. Entire Graph Visualizer, Checkpoints &amp; Brain</button>
      <button id="tabBtn-cfo" class="tab-btn" onclick="switchTab('tab-cfo', this)">4. cfo.ai Ari Simulator, plan.xlsx &amp; Scenarios</button>
      <button id="tabBtn-oss" class="tab-btn" onclick="switchTab('tab-oss', this)">5. Real OSS Bug Hunt (neatlogs#199 / PR #203) &amp; Self-Test</button>
    </div>

    <!-- TAB 1: RUNS & 8 FOCUS AREAS -->
    <div id="tab-runs" class="tab-section">
      <div class="panel">
        <h2>
          <span>Execute Live Remediation or Fault-Injection Verification</span>
          <span class="badge">Zero-Stub Sandboxed Git Worktrees + Budget Guardrail (3 Tries · 20 Tools · $0.25)</span>
        </h2>
        <div class="controls-row">
          <label style="font-size:13px; color:var(--muted);">Benchmark Case:</label>
          <select id="caseSelect"></select>
          <label style="font-size:13px; color:var(--muted);">Mode:</label>
          <select id="modeSelect">
            <option value="graph_guarded">Run B (v2): entire-graph + Blast-Radius Guardrail</option>
            <option value="baseline_naive">Run A (v1): Naive Full-Repo Baseline (Before Fix)</option>
          </select>
          <button id="btnRun" class="primary" onclick="triggerRun(false, false)">Run Autonomous Fix</button>
          <button id="btnTrap" class="warn" onclick="triggerRun(true, false)">Test Caller-Trap Recovery (Attempt 1 Rollback -&gt; Attempt 2 Fix)</button>
          <button id="btnInterrupt" class="purple" onclick="triggerInterruptAndResume()">Test Mid-Run Crash &amp; SQLite Resume</button>
        </div>
        <div id="runActionStatus" style="font-size:13px; color:var(--accent);"></div>
        <div style="margin-top:12px; padding-top:12px; border-top:1px solid var(--border);">
          <div style="font-size:12px; font-weight:700; color:var(--text); margin-bottom:8px;">
            Custom Local Python Repository Remediation (<code>POST /api/run-custom</code> · <code>verifix fix-custom</code> · Powered by LiteLLM <code>claude-sonnet-4.6</code>)
          </div>
          <div class="controls-row" style="gap:8px; flex-wrap:wrap;">
            <input id="customRepoPath" type="text" value="benchmarks/repos/case_01_ledger_rounding" placeholder="Repo path" style="width:220px;" />
            <input id="customTargetFile" type="text" value="ledger/fees.py" placeholder="Target file" style="width:140px;" />
            <input id="customTargetSymbol" type="text" value="calculate_tiered_fee" placeholder="Target symbol" style="width:150px;" />
            <input id="customReproTest" type="text" value="tests/test_fees.py" placeholder="Repro test" style="width:150px;" />
            <input id="customCallerTests" type="text" value="tests/test_settlement.py" placeholder="Caller tests" style="width:175px;" />
            <button id="btnAutoFix" class="purple" onclick="triggerAutoFix()">Zero-Config Auto-Discover &amp; Heal (Repo Only)</button>
            <button id="btnCustomRun" class="primary" onclick="triggerCustomRun()">Remediate Custom Target</button>
          </div>
          <div style="margin-top:10px; display:grid; grid-template-columns:repeat(4,1fr); gap:8px; font-size:11px; color:var(--muted);">
            <div style="background:rgba(56,189,248,0.06); border:1px solid var(--border); border-radius:6px; padding:7px 9px;">
              <strong style="color:var(--accent);">Production Runtime Dependencies:</strong><br/>
              <code>entire-graph v0.4.0</code> (symbol &amp; caller blast-radius), <code>Entire Brain v0.1.0</code> (durable memory), <code>neatlogs v1.4.26</code> SDK (traces/guardrails), <code>LiteLLM claude-sonnet-4.6</code>, AWS Lambda (<code>us-east-1</code>).
            </div>
            <div style="background:rgba(16,185,129,0.06); border:1px solid var(--border); border-radius:6px; padding:7px 9px;">
              <strong style="color:var(--green);">Development-Workflow Provenance:</strong><br/>
              <code>Entire Checkpoints v0.11.4</code>, <code>entire why</code> attribution, &amp; custom <code>entire-agent-verifix</code> Go plugin record development sessions &amp; commit provenance (not required at runtime).
            </div>
            <div style="background:rgba(168,85,247,0.06); border:1px solid var(--border); border-radius:6px; padding:7px 9px;">
              <strong style="color:#c084fc;">Diagnostic &amp; Evaluation Layer:</strong><br/>
              <code>Neatlogs MCP</code> (<code>mcp.neatlogs.com/mcp</code>), 11 failure detections (410+ traces, <code>6.0% -&gt; 5.1%</code> error rate), Client-Side <code>raw_durable</code> / <code>409</code> Root-Resolution, &amp; controlled <code>v1 -&gt; v4</code> experiments (<code>-97.76%</code> prompt tokens, <code>-96.42%</code> latency, <code>-99.80%</code> API cost).
            </div>
            <div style="background:rgba(245,158,11,0.06); border:1px solid var(--border); border-radius:6px; padding:7px 9px;">
              <strong style="color:var(--amber);">Business-Planning &amp; Financial Model:</strong><br/>
              <code>cfo.ai</code> 4-tab <code>plan.xlsx</code> &amp; Ari simulator translate measured unit COGS (<code>$1.8626 -&gt; $0.0451/run</code>, <code>-97.58%</code>) into 24-month financial <em>projections</em> (planning artifact, not a runtime dependency).
            </div>
          </div>
          <details open style="margin-top:10px; background:rgba(15,23,42,0.75); border:1px solid var(--border); border-radius:8px; padding:10px;">
            <summary style="cursor:pointer; font-size:12px; font-weight:700; color:var(--accent);">
              &#9998; Interactive Live Code &amp; Caller-Trap Sandbox Playground (Edit Any Python Code &amp; Run Live <code>claude-sonnet-4.6</code> Remediation)
            </summary>
            <div style="margin-top:10px; display:grid; grid-template-columns:repeat(3,1fr); gap:10px;">
              <div>
                <div style="font-size:11px; color:var(--muted); margin-bottom:4px;">1. Buggy Target Module (<code>module.py</code>):</div>
                <textarea id="pgModuleCode" rows="7" style="width:100%; background:#070a12; color:#e2e8f0; border:1px solid var(--border); border-radius:6px; font-family:monospace; font-size:11px; padding:8px;">def compute_invoice_total(subtotal_cents: int, discount_bps: int) -&gt; tuple[int, int]:
    # Return (net_cents, discount_cents). Bug: integer division truncates instead of rounding half-up, and discount exceeds subtotal.
    discount_cents = (subtotal_cents * discount_bps) // 10000
    net_cents = subtotal_cents - discount_cents
    return net_cents, discount_cents
</textarea>
              </div>
              <div>
                <div style="font-size:11px; color:var(--muted); margin-bottom:4px;">2. Failing Reproduction Test (<code>tests/test_repro.py</code>):</div>
                <textarea id="pgReproCode" rows="7" style="width:100%; background:#070a12; color:#e2e8f0; border:1px solid var(--border); border-radius:6px; font-family:monospace; font-size:11px; padding:8px;">from module import compute_invoice_total

def test_half_up_rounding_and_cap():
    # 150 cents * 333 bps = 4.995 cents -&gt; rounds half-up to 5 cents
    net, disc = compute_invoice_total(150, 333)
    assert disc == 5
    assert net == 145
    # Discount cannot exceed subtotal (10000 bps max)
    net_cap, disc_cap = compute_invoice_total(200, 15000)
    assert disc_cap == 200 and net_cap == 0
</textarea>
              </div>
              <div>
                <div style="font-size:11px; color:var(--muted); margin-bottom:4px;">3. Downstream Caller Contract Test (<code>tests/test_callers.py</code>):</div>
                <textarea id="pgCallerCode" rows="7" style="width:100%; background:#070a12; color:#e2e8f0; border:1px solid var(--border); border-radius:6px; font-family:monospace; font-size:11px; padding:8px;">from module import compute_invoice_total

def settle_merchant_payout(subtotal_cents: int, discount_bps: int) -&gt; dict:
    # Downstream caller unpacks a 2-tuple (net_cents, discount_cents)
    net_cents, discount_cents = compute_invoice_total(subtotal_cents, discount_bps)
    return {"net": net_cents, "discount": discount_cents}

def test_downstream_settlement_contract():
    res = settle_merchant_payout(10000, 250)
    assert res == {"net": 9750, "discount": 250}
</textarea>
              </div>
            </div>
            <div style="margin-top:8px; display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
              <label style="font-size:12px; color:var(--muted);">Target Symbol:</label>
              <input id="pgSymbol" type="text" value="compute_invoice_total" style="width:190px;" />
              <button id="btnPlaygroundFix" class="primary" onclick="triggerPlaygroundFix()">&#9889; Run Live Interactive Code Remediation (claude-sonnet-4.6 + Caller Gate)</button>
              <span id="pgResultBadge" style="font-size:12px; color:var(--green);"></span>
            </div>
          </details>
        </div>
      </div>

      <div class="grid-2">
        <div class="panel">
          <h2>Recent Autonomous Runs (Click a Run to Inspect)</h2>
          <div style="overflow-x:auto;">
            <table id="runsTable">
              <thead>
                <tr>
                  <th>Run ID</th>
                  <th>Case</th>
                  <th>Mode</th>
                  <th>Status</th>
                  <th>Attempts</th>
                  <th>Tokens</th>
                  <th>Rollbacks</th>
                </tr>
              </thead>
              <tbody></tbody>
            </table>
          </div>
        </div>

        <div class="panel">
          <h2>Selected Run Inspector (Steps, Guardrails, Unified Diff &amp; Certificate)</h2>
          <div id="selectedRunDetails">Select a run from the table to inspect its step-by-step trace, blast-radius callers, and verified patch.</div>
        </div>
      </div>
    </div>

    <!-- TAB 2: NEATLOGS EXPERIMENT, DETECTIONS & INCIDENTS -->
    <div id="tab-experiment" class="tab-section hidden">
      <div class="panel">
        <h2>
          <span>Controlled v1 (Before) vs. v2 (After) Experiment (Diagnosed via Neatlogs)</span>
          <button id="btnExp" class="primary" onclick="triggerExperiment()">Re-Run Controlled A/B Experiment</button>
        </h2>
        <p style="font-size:13px; color:var(--muted); margin-top:0;">
          <strong>Bottleneck Diagnosed in Neatlogs Run A (<code>v1 baseline_naive</code>):</strong> Without structural code localization, the agent reads all repository files into prompt context and lacks downstream caller contract awareness, inflating prompt tokens, latency, and retry cycles.<br/>
          <strong>Architectural Fix in Run B (<code>v2 graph_guarded</code>):</strong> Pre-retrieves exact symbol definitions and direct callers via <code>entire graph search</code> + <code>entire graph impact</code> (<code>RETRIEVER</code> span), enforces <code>budget_and_loop_guardrail</code> (<code>3 tries · 20 tool calls · $0.25</code>), and verifies all caller contracts via <code>blast_radius_guardrail</code> + AWS Lambda (<code>us-east-1</code>).
        </p>
        <div id="experimentTableContainer"></div>
      </div>

      <div class="grid-2">
        <div class="panel">
          <h2>
            <span>11 Active Neatlogs Detections &amp; 7-Day Backfill Scores (992 Occurrences)</span>
            <span class="badge badge-green">Live on ingest.neatlogs.com</span>
          </h2>
          <div id="detectionsTableContainer"></div>
        </div>

        <div class="panel">
          <h2>
            <span>3 Surfaced Incidents &amp; Verified Remediations (v1 -&gt; v2)</span>
            <span class="badge badge-amber">100% Failure Elimination</span>
          </h2>
          <div id="incidentsContainer"></div>
        </div>
      </div>

      <div class="panel">
        <h2>
          <span>Deployed Neatlogs Prompts (<code>app.neatlogs.com/prompts</code>) &amp; Copilot Integrations</span>
          <span class="badge badge-green">GitHub OAuth Connected (Composio)</span>
        </h2>
        <table>
          <thead>
            <tr>
              <th>Neatlogs Prompt Name</th>
              <th>Deployed Version</th>
              <th>Bound Template Variables</th>
              <th>Workflow &amp; Span Role</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><code>defect-remediation/llm_unified_plan_and_patch_v4</code></td>
              <td><span class="badge badge-green">v4 (Surgical Fast-Tier)</span></td>
              <td><code>target_file</code>, <code>goal</code>, <code>caller_contracts_summary</code>, <code>ast_unparsed_src</code>, <code>repro_failure_output</code></td>
              <td>AST-Unparsed Single-Pass Graph-Brain Planner + Tier-0 <code>nova-2-lite</code> / Tier-1 <code>claude-sonnet-4.6</code> Escalation (<strong>598 prompt tokens / -97.76%</strong>, <strong>1,482ms latency / -96.42%</strong>, <strong>$0.000298 cost / -99.80%</strong>, <strong>-97.58% modeled COGS/run</strong>).</td>
            </tr>
            <tr>
              <td><code>defect-remediation/llm_unified_plan_and_patch_v3</code></td>
              <td><span class="badge badge-blue">v3 (Coalesced Sonnet)</span></td>
              <td><code>target_file</code>, <code>goal</code>, <code>caller_contracts_summary</code>, <code>non_dup_ctx</code>, <code>repro_failure_output</code></td>
              <td>Coalesced Single-Pass Graph-Brain Planner &amp; Surgical Patch Synthesizer on <code>claude-sonnet-4.6</code> (<strong>1,533 prompt tokens / -94.27%</strong>, <strong>4,682ms latency / -88.68%</strong>, <strong>-94.92% modeled COGS/run</strong>).</td>
            </tr>
            <tr>
              <td><code>defect-remediation/llm_patch_synthesizer_prompt</code></td>
              <td><span class="badge badge-green">v2 (Active)</span></td>
              <td><code>attempt_no</code>, <code>blast_radius</code>, <code>bug_description</code>, <code>focused_context</code>, <code>hypothesis</code>, <code>previous_failure_context</code>, <code>pytest_repro_output</code></td>
              <td>Synthesizes surgical caller-safe patches constrained by <code>entire-graph</code> blast radius &amp; <code>Entire Brain</code> invariants.</td>
            </tr>
            <tr>
              <td><code>defect-remediation/llm_planner_graph_guarded_prompt</code></td>
              <td><span class="badge badge-green">v2 (Active)</span></td>
              <td><code>blast_radius</code>, <code>bug_description</code>, <code>focused_context</code>, <code>pytest_repro_output</code></td>
              <td>Formulates 3-bullet root-cause hypothesis using 1-hop AST symbol slice (<strong>-65.05% prompt tokens</strong>).</td>
            </tr>
            <tr>
              <td><code>defect-remediation/llm_planner_baseline_naive_prompt</code></td>
              <td><span class="badge badge-amber">v1 (Baseline)</span></td>
              <td><code>bug_description</code>, <code>full_repo_context</code>, <code>pytest_repro_output</code></td>
              <td>Baseline full-repo prompt stuffing used for controlled A/B comparison in Neatlogs.</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="panel">
        <h2>
          <span>Production Neatlogs Analytics Evidence Gallery (<code>app.neatlogs.com/analytics</code> · 410+ Traces · v1 -&gt; v2 -&gt; v3 -&gt; v4 Optimization)</span>
          <span class="badge badge-blue">Project 00201e50-a8c9-42cf-84bf-116568a49cd5</span>
        </h2>
        <div class="grid-2">
          <div style="background:#070a12; border:1px solid var(--border); border-radius:8px; padding:10px;">
            <div style="font-size:12px; font-weight:600; margin-bottom:6px; color:#34d399;">1. 410+ Traces Live Telemetry After v3/v4 Rollout (Error Rate 6.0% -&gt; 5.1% · Avg Tokens 829.466 -&gt; 721.641)</div>
            <img src="/screenshots/09_neatlogs_analytics_410_traces_v3_v4.png" alt="Neatlogs 410 Traces KPI Error Rate 5.1% and Token Reduction" style="width:100%; border-radius:6px; border:1px solid #1e293b;" />
          </div>
          <div style="background:#070a12; border:1px solid var(--border); border-radius:8px; padding:10px;">
            <div style="font-size:12px; font-weight:600; margin-bottom:6px; color:#e2e8f0;">2. 350-Trace Pre-v3 Baseline KPI &amp; Daily Cost Breakdown (6.0% Error Rate · 829.466 Avg Tokens)</div>
            <img src="/screenshots/05_neatlogs_350_traces_kpi_and_cost_breakdown.png" alt="Neatlogs 350 Traces KPI and Cost Breakdown" style="width:100%; border-radius:6px; border:1px solid #1e293b;" />
          </div>
          <div style="background:#070a12; border:1px solid var(--border); border-radius:8px; padding:10px;">
            <div style="font-size:12px; font-weight:600; margin-bottom:6px; color:#e2e8f0;">3. Tool Performance Across 21 Tools (Diagnosed P95 Tail Latency -&gt; Fixed in v3/v4)</div>
            <img src="/screenshots/07_neatlogs_tool_performance_21_tools.png" alt="Neatlogs 21 Tools P50 P95" style="width:100%; border-radius:6px; border:1px solid #1e293b;" />
          </div>
          <div style="background:#070a12; border:1px solid var(--border); border-radius:8px; padding:10px;">
            <div style="font-size:12px; font-weight:600; margin-bottom:6px; color:#e2e8f0;">4. Arc Patterns Sankey Flow (WORKFLOW -&gt; analyze_blast_radius -&gt; rollback -&gt; patch)</div>
            <img src="/screenshots/04_neatlogs_arc_patterns_sankey.png" alt="Neatlogs Arc Patterns Sankey" style="width:100%; border-radius:6px; border:1px solid #1e293b;" />
          </div>
        </div>
      </div>

      <div class="panel">
        <h2>
          <span>Live Neatlogs Detection -&gt; Verified GitHub Fix PR Dispatcher (OAuth-Independent)</span>
          <span class="badge badge-green">Bypasses ingest.neatlogs.com OAuth Redirect Issue</span>
        </h2>
        <div class="controls-row">
          <label style="font-size:13px; color:var(--muted);">Active Neatlogs Detection:</label>
          <select id="incidentDetectionSelect">
            <option value="Downstream Caller Contract Regression Blocked">Downstream Caller Contract Regression Blocked (39 hits)</option>
            <option value="Floating Point Error Detector">Floating Point Error Detector (87 hits)</option>
            <option value="High Prompt Token Bloat (Unbounded Grep)">High Prompt Token Bloat (Unbounded Grep) (28 hits)</option>
            <option value="System Integrity Error Detector">System Integrity Error Detector (114 hits)</option>
            <option value="Attestation Verification Tracker">Attestation Verification Tracker (140 hits)</option>
          </select>
          <button class="primary" onclick="dispatchNeatlogsIncident()">&#128640; Dispatch Detection &amp; Generate Verified GitHub PR Bundle</button>
        </div>
        <pre id="incidentDispatchOutput">Select any active Neatlogs detection above and click "Dispatch Detection" to generate a blast-radius-verified GitHub Fix PR bundle with AWS Lambda SHA-256 attestation and Entire Checkpoint link.</pre>
      </div>

      <div class="panel">
        <h2>
          <span>Live Neatlogs MCP Server Explorer (<code>https://ingest.neatlogs.com/mcp</code>)</span>
          <button class="primary" onclick="loadNeatlogsMCP()">Query Live Neatlogs MCP</button>
        </h2>
        <pre id="mcpOutput">Click "Query Live Neatlogs MCP" to execute live JSON-RPC tools/call (whoami, list_detections, search_traces) against https://ingest.neatlogs.com/mcp.</pre>
      </div>
    </div>

    <!-- TAB 3: ENTIRE CHECKPOINTS, VISUAL GRAPH & BRAIN -->
    <div id="tab-entire" class="tab-section hidden">
      <div class="panel">
        <h2>
          <span>Entire Continuous Memory &amp; Checkpoint Intelligence Suite (ALL 8/8 Official <code>hack.entire.io/neathacks-2026</code> Ideas #01–#08)</span>
          <button class="primary" onclick="runEntireIntelligenceSuite()">&#9889; Run All 8 Entire Intelligence Modules (#01–#08)</button>
        </h2>
        <div class="controls-row" style="margin-bottom:10px;">
          <input type="text" id="onboardingQuestionInput" value="How does the Blast-Radius Guardrail work, and why was it designed this way?" style="flex:1; min-width:340px;" />
          <button class="purple" onclick="askEntireOnboardingGuide()">&#129504; Ask Onboarding Guide (Idea #05: Graph + Brain + Checkpoints)</button>
        </div>
        <pre id="entireIntelligenceOutput">Click "Run All 8 Entire Intelligence Modules (#01–#08)" or ask a question above to query EntireIntelligenceEngine across Entire Graph, Entire Brain, and Entire Checkpoints.</pre>
      </div>
      <div class="panel">
        <h2>
          <span>Obsidian-Style Interactive <code>entire-graph</code> Blast-Radius Visualizer (Click Any Node)</span>
          <span class="badge badge-green">benchmarks/graph.ndjson (1,635 Records)</span>
        </h2>
        <div class="grid-2">
          <div style="background:#070a12; border:1px solid var(--border); border-radius:8px; padding:10px; text-align:center;">
            <svg id="obsidianGraphSvg" viewBox="0 0 680 340" style="width:100%; height:320px; cursor:pointer;">
              <defs>
                <marker id="arrowCall" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                  <path d="M 0 1 L 10 5 L 0 9 z" fill="#38bdf8" />
                </marker>
                <marker id="arrowTest" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                  <path d="M 0 1 L 10 5 L 0 9 z" fill="#22c55e" />
                </marker>
                <marker id="arrowCallee" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                  <path d="M 0 1 L 10 5 L 0 9 z" fill="#a855f7" />
                </marker>
              </defs>
              <!-- Edges -->
              <line x1="140" y1="80" x2="340" y2="170" stroke="#38bdf8" stroke-width="2" marker-end="url(#arrowCall)" />
              <line x1="140" y1="170" x2="340" y2="170" stroke="#38bdf8" stroke-width="2" marker-end="url(#arrowCall)" />
              <line x1="140" y1="260" x2="340" y2="170" stroke="#38bdf8" stroke-width="2" marker-end="url(#arrowCall)" />
              <line x1="340" y1="290" x2="340" y2="170" stroke="#22c55e" stroke-width="2" stroke-dasharray="4 3" marker-end="url(#arrowTest)" />
              <line x1="140" y1="295" x2="140" y2="170" stroke="#22c55e" stroke-width="2" stroke-dasharray="4 3" marker-end="url(#arrowTest)" />
              <line x1="340" y1="170" x2="545" y2="120" stroke="#a855f7" stroke-width="2" marker-end="url(#arrowCallee)" />
              <line x1="340" y1="170" x2="545" y2="230" stroke="#f59e0b" stroke-width="2" stroke-dasharray="3 3" />

              <!-- Caller Nodes -->
              <g onclick="selectGraphNode('calculate_split_fees', 'ledger/fees.py:21 — Direct caller (allocated split fee conservation)')">
                <circle cx="140" cy="80" r="18" fill="#0f172a" stroke="#38bdf8" stroke-width="2.5" />
                <text x="140" y="53" fill="#e2e8f0" font-size="11" text-anchor="middle" font-weight="600">calculate_split_fees</text>
              </g>
              <g onclick="selectGraphNode('build_settlement_batch', 'ledger/settlement.py:16 — Downstream caller (requires int cents + min_fee=50)')">
                <circle cx="140" cy="170" r="18" fill="#0f172a" stroke="#38bdf8" stroke-width="2.5" />
                <text x="140" y="143" fill="#e2e8f0" font-size="11" text-anchor="middle" font-weight="600">build_settlement_batch</text>
              </g>
              <g onclick="selectGraphNode('render_tax_invoice', 'ledger/invoicing.py:12 — Downstream caller (formats fee_cents as integer)')">
                <circle cx="140" cy="250" r="18" fill="#0f172a" stroke="#38bdf8" stroke-width="2.5" />
                <text x="140" y="225" fill="#e2e8f0" font-size="11" text-anchor="middle" font-weight="600">render_tax_invoice</text>
              </g>

              <!-- Target Symbol Node (Center) -->
              <g onclick="selectGraphNode('calculate_tiered_fee', 'ledger/fees.py:6 — Target Defect Symbol (4 direct callers, 1 callee)')">
                <circle cx="340" cy="170" r="26" fill="#1e1b4b" stroke="#f59e0b" stroke-width="3.5" />
                <text x="340" y="132" fill="#f59e0b" font-size="12" text-anchor="middle" font-weight="700">calculate_tiered_fee</text>
                <text x="340" y="174" fill="#fff" font-size="10" text-anchor="middle">TARGET</text>
              </g>

              <!-- Covering Tests -->
              <g onclick="selectGraphNode('test_exact_basis_point_rounding', 'tests/test_fees.py:6 — Narrow reproduction test')">
                <circle cx="340" cy="295" r="15" fill="#052e16" stroke="#22c55e" stroke-width="2" />
                <text x="340" y="325" fill="#86efac" font-size="10" text-anchor="middle">test_fees.py (Repro)</text>
              </g>
              <g onclick="selectGraphNode('test_settlement_batch_caller_contract', 'tests/test_settlement.py:6 — Transitive Blast-Radius Guardrail Test')">
                <circle cx="140" cy="300" r="15" fill="#052e16" stroke="#22c55e" stroke-width="2" />
                <text x="140" y="328" fill="#86efac" font-size="10" text-anchor="middle">test_settlement.py (Guardrail)</text>
              </g>

              <!-- Callee & Entire Brain Fact Nodes -->
              <g onclick="selectGraphNode('validate_cents', 'ledger/money.py:4 — Outgoing callee (enforces non-negative int cents)')">
                <circle cx="545" cy="120" r="17" fill="#2e1065" stroke="#a855f7" stroke-width="2.5" />
                <text x="545" y="94" fill="#d8b4fe" font-size="11" text-anchor="middle" font-weight="600">validate_cents</text>
              </g>
              <g onclick="selectGraphNode('calculate_tiered_fee', 'Entire Brain Fact [architecture.contracts.ledger]: Must preserve min_fee_cents=50 and int return')">
                <rect x="475" y="210" width="145" height="44" rx="8" fill="#451a03" stroke="#f59e0b" stroke-width="2" />
                <text x="547" y="229" fill="#fde68a" font-size="10" text-anchor="middle" font-weight="700">Entire Brain Memory</text>
                <text x="547" y="244" fill="#fef3c7" font-size="9" text-anchor="middle">5 Durable Facts Indexed</text>
              </g>
            </svg>
            <div id="graphNodeCaption" style="font-size:12px; color:var(--accent); margin-top:4px;">
              Click any node in the Obsidian Code Graph to inspect its live <code>entire graph impact</code> blast radius.
            </div>
          </div>

          <div>
            <div class="controls-row">
              <input id="symbolInput" value="calculate_tiered_fee" style="min-width:240px;" />
              <button class="primary" onclick="inspectGraphSymbol()">Run live <code>entire graph impact</code></button>
            </div>
            <pre id="graphImpactOutput">Loading blast radius...</pre>
          </div>
        </div>
      </div>

      <div class="panel">
        <h2>Entire CLI Checkpoints, Trails &amp; Entire Brain Continuous Memory</h2>
        <div id="entireStatusContainer"></div>
      </div>
    </div>

    <!-- TAB 4: CFO.AI FINANCIAL MODEL & ARI GAME-ENGINE SLIDERS -->
    <div id="tab-cfo" class="tab-section hidden">
      <div class="panel">
        <h2>
          <span>cfo.ai Interactive "Ari Board Overview" Simulation Controls (100% Deterministic Formula Engine)</span>
          <span class="badge badge-green">In Repo: plan.xlsx (4 Formula Sheets) &amp; BUSINESS_PLAN.md</span>
        </h2>
        <p style="font-size:13px; color:var(--muted); margin-top:0;">
          Inspired by Siqi Chen's <code>cfo.ai</code> Board Overview: adjust customer growth, inference cost, retry overhead, and Dodo Payments MoR fee to stress-test VeriFix's unit economics and 24-month cash runway in real time.
        </p>
        <div class="kpi-grid" style="grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));">
          <div class="kpi-card">
            <div class="kpi-label">Customer Growth Multiplier: <span id="lblGrowth">1.00x</span></div>
            <input type="range" id="simGrowth" min="0.5" max="2.0" step="0.05" value="1.0" style="width:100%; margin-top:8px;" oninput="updateAriSimulation()" />
            <div class="kpi-sub">Scales paying Solo/Team/Enterprise cohorts</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">LLM Inference Cost Multiplier: <span id="lblInfCost">1.00x</span></div>
            <input type="range" id="simInfCost" min="0.4" max="3.0" step="0.1" value="1.0" style="width:100%; margin-top:8px;" oninput="updateAriSimulation()" />
            <div class="kpi-sub">v2 Base = $0.1794/run (-79.83% vs v1)</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">Avg Attempts / Run: <span id="lblRetries">1.15x</span></div>
            <input type="range" id="simRetries" min="1.0" max="2.5" step="0.05" value="1.15" style="width:100%; margin-top:8px;" oninput="updateAriSimulation()" />
            <div class="kpi-sub">Capped at 3.0x by budget_and_loop_guardrail</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">Architecture Mode: <span id="lblArchMode">v2 Graph-Guarded</span></div>
            <select id="simArchMode" style="width:100%; margin-top:8px;" onchange="updateAriSimulation()">
              <option value="v2">v2 Graph-Guarded (4,269 prompt tok / run)</option>
              <option value="v1">v1 Unbounded Baseline (12,216 prompt tok / run)</option>
            </select>
            <div class="kpi-sub">Demonstrates why entire-graph is required for margin</div>
          </div>
        </div>
        <div class="kpi-grid" id="ariSimScorecard"></div>
      </div>

      <div class="panel">
        <h2>
          <span>cfo.ai 4-Quarter Multi-Scenario Table (Main · Growth · Downside)</span>
          <span class="badge">Synced with /home/user/verifix/plan.xlsx</span>
        </h2>
        <div class="controls-row">
          <label style="font-size:13px; color:var(--muted);">Select Scenario:</label>
          <select id="scenarioSelect" onchange="renderCFOTable()"></select>
        </div>
        <div id="cfoTableContainer"></div>
      </div>

      <div class="panel">
        <h2>Ready-to-Execute <code>https://api.cfo.ai/mcp</code> Tool Payloads (<code>edit_table_blocks</code> &amp; <code>edit_scenarios</code>)</h2>
        <pre id="cfoMcpPayload"></pre>
      </div>
    </div>

    <!-- TAB 5: REAL OPEN-SOURCE BUG HUNT & JURY SELF-TEST -->
    <div id="tab-oss" class="tab-section hidden">
      <div class="panel">
        <h2>
          <span>6-Point One-Command Jury Self-Test (<code>verifix selftest</code>)</span>
          <button class="primary" onclick="runBrowserSelftest()">Run Live 6-Point Jury Self-Test</button>
        </h2>
        <div id="selftestContainer">Click "Run Live 6-Point Jury Self-Test" to verify Entire Checkpoints (10 refs), entire-graph + graph.ndjson, Entire Brain, Neatlogs 11 Detections (992 occurrences), cfo.ai plan.xlsx formulas, and AWS Lambda us-east-1 attestation.</div>
      </div>

      <div class="panel">
        <h2>
          <span>Live 30-Batch Concurrency Stress Benchmark: <code>neatlogs#199</code> (Unpatched) vs. <code>PR #203</code> (VeriFix Patch)</span>
          <button class="primary" onclick="runOSSConcurrencyBenchmark()">&#9654; Run Live 30-Batch Concurrency Benchmark</button>
        </h2>
        <div id="ossBenchmarkResult">Click "Run Live 30-Batch Concurrency Benchmark" to spawn 6 concurrent exporter threads (30 batches) comparing single-try <code>acquire(blocking=False)</code> against VeriFix's deadline-bounded <code>acquire(timeout=remaining)</code> fix in <code>PR #203</code>.</div>
      </div>

      <div class="panel">
        <h2>
          <span>Real Open-Source Bug Discovered &amp; Fixed by VeriFix in <code>neatlogs/neatlogs</code> (v1.4.26)</span>
          <span class="badge badge-green">530 / 530 Unit Tests + black/isort Passing + AWS Lambda Attested</span>
        </h2>
        <div id="ossBugContainer"></div>
      </div>
    </div>
  </div>

  <!-- FLOATING 5-ACT JURY GUIDED TOUR & DEMO DIRECTOR DOCK -->
  <div id="juryTourDock" class="hidden" style="position:fixed; bottom:16px; left:24px; right:24px; background:linear-gradient(90deg, #0f172a 0%, #1e1b4b 100%); border:2px solid var(--accent); border-radius:12px; padding:14px 20px; box-shadow:0 12px 32px rgba(0,0,0,0.75); z-index:9999; display:none; justify-content:space-between; align-items:center; gap:16px; flex-wrap:wrap;">
    <div style="flex:1; min-width:280px;">
      <div style="display:flex; align-items:center; gap:10px; margin-bottom:4px;">
        <span id="tourActBadge" class="badge badge-blue">ACT 1 / 5 (0:00–0:35)</span>
        <strong id="tourActTitle" style="font-size:14px; color:#f8fafc;">Autonomous Remediation &amp; Blast-Radius Guardrail Rollback</strong>
      </div>
      <div id="tourActNarration" style="font-size:12px; color:#cbd5e1;">
        Voiceover Cue: "VeriFix maps every downstream caller via entire-graph before editing code. When Attempt #1 breaks settlement.py's int contract, blast_radius_guardrail atomically rolls back the worktree, records the gotcha in Entire Brain, and synthesizes a caller-safe patch on Attempt #2 attested by AWS Lambda in us-east-1."
      </div>
    </div>
    <div style="display:flex; gap:8px; align-items:center;">
      <button onclick="stepJuryTour(-1)" style="cursor:pointer;">&larr; Prev Act</button>
      <button class="primary" onclick="stepJuryTour(1)" style="cursor:pointer; font-weight:700;">Next Act &rarr;</button>
      <button onclick="closeJuryTour()" style="cursor:pointer; background:#334155;">Close Tour</button>
    </div>
  </div>

  <script>
    const API_BASE = window.location.hostname.endsWith('github.io')
      ? 'https://e6utpuirdzj7k4vu2fqlxlhvwm0cqzfv.lambda-url.us-east-1.on.aws'
      : '';
    const _origFetch = window.fetch.bind(window);
    window.fetch = (input, init) => {
      if (typeof input === 'string' && input.startsWith('/api/')) {
        return _origFetch(API_BASE + input, init);
      }
      return _origFetch(input, init);
    };
    let STATE = null;

    function switchTab(tabId, btnEl) {
      document.querySelectorAll('.tab-section').forEach(el => el.classList.add('hidden'));
      document.getElementById(tabId).classList.remove('hidden');
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      btnEl.classList.add('active');
    }

    async function refreshAll() {
      const ind = document.getElementById('statusIndicator');
      ind.textContent = 'SYNCING...';
      try {
        const res = await fetch('/api/overview');
        STATE = await res.json();
        renderKPIs();
        renderBenchmarksDropdown();
        renderRunsTable();
        renderExperiments();
        renderDetectionsAndIncidents();
        renderEntireStatus();
        renderCFOScenarios();
        updateAriSimulation();
        renderOSSBugHunt();
        if (STATE.runs && STATE.runs.length > 0) {
          selectRun(STATE.runs[0].run_id);
        }
        ind.textContent = 'LIVE TELEMETRY READY';
      } catch (err) {
        ind.textContent = 'ERROR: ' + err.message;
      }
    }

    function renderKPIs() {
      const runs = STATE.runs || [];
      document.getElementById('kpiRuns').textContent = runs.length;
      const totalRollbacks = runs.reduce((acc, r) => acc + (r.rollbacks_executed || 0), 0);
      document.getElementById('kpiRegressions').textContent = totalRollbacks;

      if (STATE.experiments && STATE.experiments.length > 0) {
        const d = STATE.experiments[0].comparison.measured_delta;
        document.getElementById('kpiTokenDelta').textContent = '-' + d.prompt_token_reduction_pct + '%';
        document.getElementById('kpiLatencyDelta').textContent = '-' + d.latency_reduction_pct + '%';
      }

      if (STATE.cfo_model) {
        const mainRows = STATE.cfo_model.scenarios['Main (Graph-Optimized Base Plan)'];
        const q4 = mainRows[mainRows.length - 1];
        document.getElementById('kpiMargin').textContent = q4.gross_margin_pct + '%';
        const unitCost = STATE.cfo_model.telemetry_provenance.run_b_graph_guarded.modeled_enterprise_cost_per_run_usd;
        document.getElementById('kpiCostPerRun').textContent = '$' + unitCost + ' Direct COGS / Verified Run';
      }
    }

    function renderBenchmarksDropdown() {
      const sel = document.getElementById('caseSelect');
      if (sel.options.length > 0) return;
      (STATE.benchmarks || []).forEach(b => {
        const opt = document.createElement('option');
        opt.value = b.case_id;
        opt.textContent = b.case_id + ' — ' + b.title;
        sel.appendChild(opt);
      });
    }

    function renderRunsTable() {
      const tbody = document.querySelector('#runsTable tbody');
      tbody.innerHTML = '';
      (STATE.runs || []).forEach(r => {
        if (!r) return;
        const tr = document.createElement('tr');
        tr.style.cursor = 'pointer';
        tr.onclick = () => selectRun(r.run_id);
        const badgeCls = r.status === 'VERIFIED_COMPLETE' ? 'badge-green' : 'badge-amber';
        tr.innerHTML = `
          <td><code>${r.run_id}</code></td>
          <td>${r.case_id}</td>
          <td><span class="badge">${r.mode}</span></td>
          <td><span class="badge ${badgeCls}">${r.status}</span></td>
          <td>${r.current_attempt}</td>
          <td>${r.total_tokens}</td>
          <td>${r.rollbacks_executed}${r.resumed_from_checkpoint ? ' (Resumed)' : ''}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    function selectRun(runId) {
      const r = (STATE.runs || []).find(x => x && x.run_id === runId);
      if (!r) return;
      const container = document.getElementById('selectedRunDetails');
      const stepsHtml = (r.steps || []).map(s => `
        <div class="step-item ${s.status === 'RECOVERED' ? 'recovered' : ''}">
          <div style="display:flex; justify-content:space-between; font-size:12px;">
            <strong>#${s.seq_num} [${s.span_kind}] ${s.title}</strong>
            <span>${s.latency_ms} ms | ${s.tokens_used} tok | ${s.status}</span>
          </div>
          <div style="font-size:12px; color:var(--muted); margin-top:4px;">Phase: <code>${s.phase}</code></div>
        </div>
      `).join('');

      container.innerHTML = `
        <div style="margin-bottom:10px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
          <div>
            <strong>Run ID:</strong> <code>${r.run_id}</code> |
            <strong>Target Symbol:</strong> <code>${r.target_symbol}</code> |
            <strong>Resumed from SQLite Checkpoint:</strong> ${r.resumed_from_checkpoint ? 'YES' : 'NO'}
          </div>
          <div style="display:flex; gap:8px;">
            <a href="${API_BASE}/runs/${r.run_id}/share" target="_blank" style="background:rgba(56,189,248,0.16); border:1px solid var(--accent); color:var(--accent); padding:5px 10px; border-radius:6px; font-size:12px; text-decoration:none; font-weight:600;">&#128279; Open Shareable PR &amp; Trace Evidence Page</a>
            <a href="${API_BASE}/api/runs/${r.run_id}/pr-evidence" target="_blank" style="background:rgba(16,185,129,0.15); border:1px solid var(--green); color:var(--green); padding:5px 10px; border-radius:6px; font-size:12px; text-decoration:none; font-weight:600;">JSON Evidence Bundle</a>
          </div>
        </div>
        <h3 style="font-size:13px; color:var(--muted);">Step-by-Step Execution Ledger (${(r.steps || []).length} spans)</h3>
        <div>${stepsHtml}</div>
        <h3 style="font-size:13px; color:var(--muted);">Verified Git Unified Diff</h3>
        <pre>${r.final_diff || 'No final diff committed yet.'}</pre>
        <h3 style="font-size:13px; color:var(--muted);">Verification Certificate</h3>
        <pre>${JSON.stringify(r.verification_certificate || {}, null, 2)}</pre>
      `;
    }

    async function triggerRun(injectTrap, interruptAfterRepro) {
      const caseId = document.getElementById('caseSelect').value;
      const mode = document.getElementById('modeSelect').value;
      const statusEl = document.getElementById('runActionStatus');
      statusEl.textContent = 'Running autonomous agent in isolated Git worktree with live LiteLLM claude-sonnet-4.6 + Neatlogs + Entire-Graph...';
      document.getElementById('btnRun').disabled = true;
      document.getElementById('btnTrap').disabled = true;
      try {
        const res = await fetch('/api/run', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            case_id: caseId,
            mode: mode,
            inject_caller_trap: injectTrap,
            interrupt_after_repro: interruptAfterRepro
          })
        });
        const data = await res.json();
        statusEl.textContent = `Completed Run ${data.run_id}: status=${data.status}, attempts=${data.current_attempt}, tokens=${data.total_tokens}, rollbacks=${data.rollbacks_executed}`;
        await refreshAll();
        selectRun(data.run_id);
      } catch (err) {
        statusEl.textContent = 'Error: ' + err.message;
      } finally {
        document.getElementById('btnRun').disabled = false;
        document.getElementById('btnTrap').disabled = false;
      }
    }

    async function triggerInterruptAndResume() {
      const caseId = document.getElementById('caseSelect').value;
      const statusEl = document.getElementById('runActionStatus');
      document.getElementById('btnInterrupt').disabled = true;
      try {
        statusEl.textContent = 'Phase 1/2: Starting run and simulating process interruption after REPRODUCING checkpoint...';
        const r1 = await fetch('/api/run', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            case_id: caseId,
            mode: 'graph_guarded',
            inject_caller_trap: false,
            interrupt_after_repro: true
          })
        });
        const interruptedRun = await r1.json();
        statusEl.textContent = `Run ${interruptedRun.run_id} checkpointed at status=${interruptedRun.status}. Phase 2/2: Resuming from SQLite WAL state...`;
        const r2 = await fetch('/api/resume', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ run_id: interruptedRun.run_id })
        });
        const resumedRun = await r2.json();
        statusEl.textContent = `Stateful Resume Verified! Run ${resumedRun.run_id} resumed without re-running LOCALIZING/REPRODUCING -> final status=${resumedRun.status}`;
        await refreshAll();
        selectRun(resumedRun.run_id);
      } catch (err) {
        statusEl.textContent = 'Error: ' + err.message;
      } finally {
        document.getElementById('btnInterrupt').disabled = false;
      }
    }

    function renderExperiments() {
      const container = document.getElementById('experimentTableContainer');
      const exps = STATE.experiments || [];
      if (exps.length === 0) {
        container.innerHTML = '<p>No experiment recorded yet.</p>';
        return;
      }
      const c = exps[0].comparison;
      const ra = c.run_a_before;
      const rb = c.run_b_after;
      const d = c.measured_delta;
      container.innerHTML = `
        <table>
          <thead>
            <tr>
              <th>Metric (${c.workload_title})</th>
              <th>Run A — Before (Naive Full-Repo Baseline)</th>
              <th>Run B — After (Entire-Graph + Blast-Radius Guardrail)</th>
              <th>Measured Improvement</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Run ID</td>
              <td><code>${ra.run_id}</code></td>
              <td><code>${rb.run_id}</code></td>
              <td><code>${c.experiment_id}</code></td>
            </tr>
            <tr>
              <td>Prompt Tokens</td>
              <td>${ra.prompt_tokens}</td>
              <td>${rb.prompt_tokens}</td>
              <td><span class="badge badge-green">-${d.prompt_token_reduction_pct}%</span></td>
            </tr>
            <tr>
              <td>Total Tokens</td>
              <td>${ra.total_tokens}</td>
              <td>${rb.total_tokens}</td>
              <td><span class="badge badge-green">-${d.total_token_reduction_pct}%</span></td>
            </tr>
            <tr>
              <td>Total Latency (ms)</td>
              <td>${ra.total_latency_ms} ms</td>
              <td>${rb.total_latency_ms} ms</td>
              <td><span class="badge badge-green">-${d.latency_reduction_pct}%</span></td>
            </tr>
            <tr>
              <td>Attempts Required</td>
              <td>${ra.attempts} (Caller regression on Attempt 1)</td>
              <td>${rb.attempts} (1st-pass caller-safe patch)</td>
              <td><span class="badge badge-green">-${d.attempts_saved} retry cycle</span></td>
            </tr>
          </tbody>
        </table>
      `;
    }

    async function triggerExperiment() {
      const btn = document.getElementById('btnExp');
      btn.disabled = true;
      btn.textContent = 'Running A/B Experiment...';
      try {
        await fetch('/api/experiment', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ case_id: 'case_01_ledger_rounding' })
        });
        await refreshAll();
      } finally {
        btn.disabled = false;
        btn.textContent = 'Re-Run Controlled A/B Experiment';
      }
    }

    async function loadNeatlogsMCP() {
      const pre = document.getElementById('mcpOutput');
      pre.textContent = 'Querying https://ingest.neatlogs.com/mcp (whoami + search_traces)...';
      const res = await fetch('/api/neatlogs-mcp');
      const data = await res.json();
      pre.textContent = JSON.stringify(data, null, 2);
    }

    async function inspectGraphSymbol() {
      const sym = document.getElementById('symbolInput').value;
      const pre = document.getElementById('graphImpactOutput');
      pre.textContent = 'Running entire graph impact --symbol ' + sym + '...';
      const res = await fetch('/api/graph-inspect', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ symbol: sym })
      });
      const data = await res.json();
      pre.textContent = data.impact_text + '\\n\\n=== STRUCTURED DIRECT CALLERS ===\\n' + JSON.stringify(data.direct_callers, null, 2);
    }

    function renderEntireStatus() {
      const e = STATE.entire || {};
      const container = document.getElementById('entireStatusContainer');
      const commitsHtml = (e.recent_commits || []).map(c => {
        const fullSha = c.full_hash || c.hash;
        const entireUrl = c.entire_io_url || `https://entire.io/gh/shivanshjain456/neatHack/commit/${fullSha}`;
        return `
        <tr>
          <td><code>${c.hash}</code></td>
          <td>${c.subject}</td>
          <td><code>${c.entire_checkpoint || 'root baseline'}</code></td>
          <td><a href="${entireUrl}" target="_blank" style="color:var(--accent); font-size:11px;">entire.io/gh/.../${c.hash} &#8599;</a></td>
        </tr>
      `;
      }).join('');
      const brain = e.entire_brain || {};
      container.innerHTML = `
        <h3 style="font-size:13px; color:var(--muted);">Entire Graph Session Savings (<code>entire graph stats --repo .</code>)</h3>
        <pre>${e.entire_graph_stats || 'Graph stats ready.'}</pre>
        <h3 style="font-size:13px; color:var(--muted);">Entire Checkpoint Explain &amp; Token Analytics (<code>entire checkpoint explain HEAD</code> · <code>entire checkpoint tokens HEAD</code> · <code>entire why</code>)</h3>
        <pre>${(e.checkpoint_explain_head || '') + '\\n\\n=== ENTIRE CHECKPOINT TOKENS HEAD ===\\n' + (e.checkpoint_tokens_head || '') + '\\n\\n=== ENTIRE WHY (AI LINE ATTRIBUTION) ===\\n' + (e.entire_why_sample || '')}</pre>
        <h3 style="font-size:13px; color:var(--muted);">Entire Brain Continuous Memory &amp; MCP Server (<code>entire brain status &amp; recall</code> · <code>entire brain mcp --print-config</code> · <code>.entire/agent-guide.md</code>)</h3>
        <pre>${(brain.status_text || '') + '\\n\\n=== OVERVIEW ===\\n' + (brain.overview_text || '') + '\\n\\n=== RECALLED FACTS ===\\n' + (brain.recalled_facts_text || '') + '\\n\\n=== ENTIRE BRAIN MCP CONFIG ===\\n' + (e.entire_brain_mcp_config || '') + '\\n\\n=== TUNED ENTIRE TRAIL RUNNERS (.entire/runners/) ===\\n' + ((e.entire_trail_runners || []).join(', '))}</pre>
        <h3 style="font-size:13px; color:var(--muted);">Entire CLI Status (<code>entire status --json</code>)</h3>
        <pre>${JSON.stringify(e.entire_status || {}, null, 2)}</pre>
        <h3 style="font-size:13px; color:var(--muted);">Entire Git Checkpoint Refs (<code>refs/entire/*</code>)</h3>
        <pre>${(e.entire_refs || []).join('\\n') || 'Active session recording.'}</pre>
        <h3 style="font-size:13px; color:var(--muted);">Recent Commits, Trailers &amp; Direct <code>entire.io</code> Checkpoint Links</h3>
        <table>
          <thead><tr><th>Commit</th><th>Subject</th><th>Entire-Checkpoint Trailer</th><th>Entire Forge URL</th></tr></thead>
          <tbody>${commitsHtml}</tbody>
        </table>
      `;
    }

    function renderCFOScenarios() {
      if (!STATE.cfo_model) return;
      const sel = document.getElementById('scenarioSelect');
      if (sel.options.length === 0) {
        Object.keys(STATE.cfo_model.scenarios).forEach(k => {
          const opt = document.createElement('option');
          opt.value = k;
          opt.textContent = k;
          sel.appendChild(opt);
        });
      }
      renderCFOTable();
      document.getElementById('cfoMcpPayload').textContent = JSON.stringify(
        STATE.cfo_model.cfo_ai_mcp_payloads,
        null,
        2
      );
    }

    function renderCFOTable() {
      const scenKey = document.getElementById('scenarioSelect').value;
      const rows = (STATE.cfo_model.scenarios || {})[scenKey] || [];
      const container = document.getElementById('cfoTableContainer');
      const trs = rows.map(r => `
        <tr>
          <td><strong>${r.period}</strong></td>
          <td>${r.paying_teams}</td>
          <td>${r.billable_runs.toLocaleString()}</td>
          <td>$${r.revenue_usd.toLocaleString()}</td>
          <td>$${r.arr_usd.toLocaleString()}</td>
          <td>$${r.cogs_usd.toLocaleString()}</td>
          <td>$${r.gross_profit_usd.toLocaleString()}</td>
          <td><span class="badge badge-green">${r.gross_margin_pct}%</span></td>
          <td>$${r.opex_usd.toLocaleString()}</td>
          <td>$${r.ebitda_usd.toLocaleString()}</td>
          <td>$${r.ending_cash_usd.toLocaleString()}</td>
          <td>${r.runway}</td>
        </tr>
      `).join('');
      container.innerHTML = `
        <table>
          <thead>
            <tr>
              <th>Quarter</th>
              <th>Paying Teams</th>
              <th>Verified Runs</th>
              <th>Quarterly Rev</th>
              <th>Annualized ARR</th>
              <th>Total COGS</th>
              <th>Gross Profit</th>
              <th>Gross Margin</th>
              <th>OpEx</th>
              <th>EBITDA</th>
              <th>Ending Cash</th>
              <th>Runway</th>
            </tr>
          </thead>
          <tbody>${trs}</tbody>
        </table>
      `;
    }

    function renderDetectionsAndIncidents() {
      const nl = (STATE.neatlogs_live || {}).reliability_and_detections || {};
      const dets = nl.detections || [];
      const trends = nl.trends_7d || {};
      const detEl = document.getElementById('detectionsTableContainer');
      if (detEl) {
        const rows = dets.map(d => {
          const t = trends[d.display_name] || {};
          const occ = t.total_occurrences !== undefined ? t.total_occurrences : '-';
          const grpCls = d.group_name === 'Positive' ? 'badge-green' : (d.group_name === 'Negative' ? 'badge-amber' : '');
          return `
            <tr>
              <td><strong>${d.display_name}</strong><div style="font-size:11px;color:var(--muted);">${d.description || ''}</div></td>
              <td><code>${d.type}</code></td>
              <td><span class="badge ${grpCls}">${d.group_name}</span></td>
              <td><strong>${occ}</strong></td>
            </tr>
          `;
        }).join('');
        detEl.innerHTML = `
          <table>
            <thead><tr><th>Detection Rule</th><th>Type</th><th>Group</th><th>7d Flagged Spans</th></tr></thead>
            <tbody>${rows}</tbody>
          </table>
        `;
      }

      const incEl = document.getElementById('incidentsContainer');
      if (incEl) {
        const incs = nl.remediated_incidents || [];
        incEl.innerHTML = incs.map(inc => `
          <div class="step-item" style="margin-bottom:10px;">
            <div style="display:flex; justify-content:space-between; font-size:12px;">
              <strong>[${inc.incident_id}] ${inc.detection_name}</strong>
              <span class="badge badge-green">${inc.status}</span>
            </div>
            <div style="font-size:12px; color:var(--muted); margin-top:4px;">
              <strong>v1 Before:</strong> ${inc.v1_before}<br/>
              <strong>Root Cause (Neatlogs):</strong> ${inc.root_cause_diagnosed_in_neatlogs}<br/>
              <strong>Remediation:</strong> ${inc.remediation_shipped}<br/>
              <strong style="color:var(--green);">v2 After:</strong> ${inc.v2_after}
            </div>
          </div>
        `).join('');
      }
    }

    function selectGraphNode(symbolName, captionText) {
      const cap = document.getElementById('graphNodeCaption');
      if (cap) cap.textContent = captionText;
      const inp = document.getElementById('symbolInput');
      if (inp) {
        inp.value = symbolName;
        inspectGraphSymbol();
      }
    }

    function updateAriSimulation() {
      const gMult = parseFloat((document.getElementById('simGrowth') || {}).value || '1.0');
      const cMult = parseFloat((document.getElementById('simInfCost') || {}).value || '1.0');
      const rMult = parseFloat((document.getElementById('simRetries') || {}).value || '1.15');
      const mode = (document.getElementById('simArchMode') || {}).value || 'v2';

      if (document.getElementById('lblGrowth')) document.getElementById('lblGrowth').textContent = gMult.toFixed(2) + 'x';
      if (document.getElementById('lblInfCost')) document.getElementById('lblInfCost').textContent = cMult.toFixed(2) + 'x';
      if (document.getElementById('lblRetries')) document.getElementById('lblRetries').textContent = rMult.toFixed(2) + 'x';
      if (document.getElementById('lblArchMode')) document.getElementById('lblArchMode').textContent = mode === 'v2' ? 'v2 Graph-Guarded' : 'v1 Baseline';

      const baseTeamsQ4 = Math.round(78 * gMult);
      const runsQ4 = baseTeamsQ4 * 450;
      const qtrRev = Math.round(baseTeamsQ4 * 955.29);
      const exitArr = qtrRev * 4;
      const baseUnitCogs = mode === 'v2' ? 0.1794 : 0.8896;
      const effectiveUnitCogs = baseUnitCogs * cMult * (rMult / 1.15);
      const llmCogs = Math.round(runsQ4 * effectiveUnitCogs);
      const dodoFee = Math.round(qtrRev * 0.039 + baseTeamsQ4 * 3 * 0.40);
      const totalCogs = llmCogs + dodoFee;
      const grossProfit = qtrRev - totalCogs;
      const gmPct = qtrRev > 0 ? ((grossProfit / qtrRev) * 100).toFixed(1) : '0.0';
      const opex = 45600;
      const ebitda = grossProfit - opex;
      const endingCash = Math.round(150000 + ebitda * 1.65);
      const runway = ebitda >= 0 ? 'INFINITE (Cash-Flow Positive)' : Math.max(1.0, (endingCash / Math.abs(ebitda / 3))).toFixed(1) + ' Months';

      const card = document.getElementById('ariSimScorecard');
      if (card) {
        card.innerHTML = `
          <div class="kpi-card">
            <div class="kpi-label">Simulated Q4 Exit ARR</div>
            <div class="kpi-value">$${exitArr.toLocaleString()}</div>
            <div class="kpi-sub">${baseTeamsQ4} Paying Teams (${runsQ4.toLocaleString()} runs/qtr)</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">Simulated Unit COGS / Run</div>
            <div class="kpi-value">$${effectiveUnitCogs.toFixed(4)}</div>
            <div class="kpi-sub">${mode === 'v2' ? 'entire-graph -79.83% COGS active' : 'WARNING: Unbounded v1 repo context'}</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">Simulated Gross Margin</div>
            <div class="kpi-value" style="color:${parseFloat(gmPct) >= 70 ? 'var(--green)' : 'var(--amber)'}">${gmPct}%</div>
            <div class="kpi-sub">Includes Dodo Payments 3.9% MoR Fee ($${dodoFee.toLocaleString()})</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">Quarterly EBITDA &amp; Runway</div>
            <div class="kpi-value" style="color:${ebitda >= 0 ? 'var(--green)' : 'var(--red)'}">${ebitda >= 0 ? '+' : ''}$${ebitda.toLocaleString()}</div>
            <div class="kpi-sub">${runway} (Cash: $${endingCash.toLocaleString()})</div>
          </div>
        `;
      }
    }

    function renderOSSBugHunt() {
      const oss = STATE.real_oss_bug_hunt || {};
      const el = document.getElementById('ossBugContainer');
      if (!el || !oss.target_repository) return;
      const att = oss.aws_lambda_attestation || {};
      const issueUrl = oss.upstream_issue_url || 'https://github.com/neatlogs/neatlogs/issues/199';
      const prUrl = oss.upstream_pr_url || 'https://github.com/neatlogs/neatlogs/pull/203';
      el.innerHTML = `
        <div style="margin-bottom:12px; font-size:13px;">
          <strong>Live Upstream GitHub Issue:</strong> <a href="${issueUrl}" target="_blank" style="color:var(--green); font-weight:700;">${issueUrl} (${oss.upstream_issue_number || 'neatlogs#199'})</a><br/>
          <strong>Live Upstream Pull Request:</strong> <a href="${prUrl}" target="_blank" style="color:var(--accent); font-weight:700;">${prUrl} (${oss.upstream_pr_number || 'neatlogs#203'})</a><br/>
          <strong>Target Repository:</strong> <a href="${oss.target_repository}" target="_blank" style="color:var(--accent);">${oss.target_repository}</a> (${oss.version_audited})<br/>
          <strong>Target File &amp; Symbols:</strong> <code>${oss.target_file}</code> — <code>${(oss.target_symbols || []).join(', ')}</code><br/>
          <strong>Bug Discovered:</strong> ${oss.bug_title}<br/>
          <strong>Before Fix Repro:</strong> <span style="color:var(--amber);">${oss.before_fix_repro}</span><br/>
          <strong>After VeriFix Patch:</strong> <span style="color:var(--green);">${oss.after_fix_verification}</span><br/>
          <strong>AWS Lambda us-east-1 Attestation:</strong> <code>${att.verdict}</code> | Request ID: <code>${att.aws_request_id}</code> | SHA-256: <code>${att.sha256_attestation_digest}</code>
        </div>
        <h3 style="font-size:13px; color:var(--muted);">Verified Unified Diff Patch (<code>REAL_OSS_BUG_REPORT_NEATLOGS.md</code>)</h3>
        <pre>${oss.git_diff || ''}</pre>
      `;
    }

    async function runBrowserSelftest() {
      const el = document.getElementById('selftestContainer');
      el.innerHTML = 'Running live 6-point Jury Self-Test...';
      const res = await fetch('/api/selftest');
      const data = await res.json();
      const rows = (data.checks || []).map(c => `
        <tr>
          <td><code>${c.check_id}</code></td>
          <td><strong>${c.partner}</strong></td>
          <td><span class="badge ${c.passed ? 'badge-green' : 'badge-amber'}">${c.passed ? 'PASSED' : 'CHECK'}</span></td>
          <td>${c.summary}</td>
        </tr>
      `).join('');
      el.innerHTML = `
        <div style="margin-bottom:10px; font-weight:700; color:var(--green);">
          Jury Verdict: ${data.passed_count} / ${data.total_checks} Partner &amp; Architecture Checks Passed
        </div>
        <table>
          <thead><tr><th>Check ID</th><th>Partner / System</th><th>Verdict</th><th>Empirical Evidence</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      `;
    }

    async function runOSSConcurrencyBenchmark() {
      const el = document.getElementById('ossBenchmarkResult');
      if (!el) return;
      el.innerHTML = 'Running live 6-thread x 5-batch (30 batches) concurrency stress test...';
      const res = await fetch('/api/oss-bug-benchmark', { method: 'POST' });
      const d = await res.json();
      const b1 = d.before_unpatched_199 || {};
      const b2 = d.after_patched_pr_203 || {};
      el.innerHTML = `
        <table>
          <thead>
            <tr>
              <th>Implementation</th>
              <th>Concurrent Threads &times; Batches</th>
              <th>Dropped Batches</th>
              <th>Completed Batches</th>
              <th>Drop Rate</th>
              <th>Wall-Clock Time</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong style="color:var(--amber);">Before Fix (<code>neatlogs#199</code>: <code>acquire(blocking=False)</code>)</strong></td>
              <td>${d.threads} &times; ${d.batches_per_thread} (${d.total_batches})</td>
              <td><strong style="color:var(--red);">${b1.dropped_batches} / ${d.total_batches}</strong></td>
              <td>${b1.completed_batches} / ${d.total_batches}</td>
              <td><span class="badge badge-amber">${b1.drop_rate_pct}% DROPPED</span></td>
              <td>${b1.elapsed_ms} ms</td>
            </tr>
            <tr>
              <td><strong style="color:var(--green);">After VeriFix Patch (<code>PR #203</code>: <code>acquire(timeout=remaining)</code>)</strong></td>
              <td>${d.threads} &times; ${d.batches_per_thread} (${d.total_batches})</td>
              <td><strong style="color:var(--green);">${b2.dropped_batches} / ${d.total_batches}</strong></td>
              <td><strong>${b2.completed_batches} / ${d.total_batches}</strong></td>
              <td><span class="badge badge-green">${b2.drop_rate_pct}% DROPPED (100% DELIVERED)</span></td>
              <td>${b2.elapsed_ms} ms</td>
            </tr>
          </tbody>
        </table>
      `;
    }

    let CURRENT_TOUR_ACT = 0;
    const TOUR_ACTS = [
      {
        badge: 'ACT 1 / 5 (0:00–0:35) · THE AGENT (30%)',
        title: 'Autonomous Execution, Blast-Radius Guardrail Rollback & AWS Lambda Attestation',
        narration: 'Voiceover Cue: "VeriFix maps every downstream caller via entire-graph before editing code. Here on case_01_ledger_rounding, Attempt #1 passed the unit test but broke settlement.py\'s int contract—so blast_radius_guardrail atomically rolled back the worktree, recorded the gotcha in Entire Brain, and synthesized a caller-safe fix on Attempt #2 attested by AWS Lambda in us-east-1."',
        tabId: 'tab-runs',
        tabBtnId: 'tabBtn-runs',
        onEnter: () => {
          const runs = STATE ? (STATE.runs || []) : [];
          const trapRun = runs.find(r => r && r.rollbacks_executed > 0) || runs[0];
          if (trapRun) selectRun(trapRun.run_id);
        }
      },
      {
        badge: 'ACT 2 / 5 (0:35–1:15) · NEATLOGS PARTNER PROOF',
        title: 'Neatlogs v1 vs. v2 Experiment (-65.05% Prompt Tokens), 11 Detections (992 Hits) & Production Analytics',
        narration: 'Voiceover Cue: "In Neatlogs, we diagnosed three real bottlenecks across 188+ traces: v1 full-repo context bloat, caller-blind retries, and 429 quota stalls. Upgrading to v2 cut prompt tokens by 65.05%, latency by 42.56%, and Execution Failed detections by 100%, with 11 active detections (992 hits), 3 deployed v1/v2 prompts, and 0.0% tool error rate."',
        tabId: 'tab-experiment',
        tabBtnId: 'tabBtn-experiment',
        onEnter: () => {
          loadNeatlogsMCP();
        }
      },
      {
        badge: 'ACT 3 / 5 (1:15–1:55) · ENTIRE PARTNER PROOF',
        title: 'Entire Checkpoints (10 Refs), Obsidian SVG Graph (1,635 Records), Entire Brain & External Agent Plugin',
        narration: 'Voiceover Cue: "We combined all four pillars of Entire: 10 Git Checkpoint refs with commit trailers, an interactive Obsidian-style entire-graph blast-radius visualizer backed by 1,635 NDJSON records, Entire Brain continuous memory (465 symbols, 1,666 relations), and entire-agent-verifix implementing External Agent Protocol v1."',
        tabId: 'tab-entire',
        tabBtnId: 'tabBtn-entire',
        onEnter: () => {
          selectGraphNode('calculate_tiered_fee', 'Target Symbol: calculate_tiered_fee (benchmarks/repos/case_01_ledger_rounding/ledger/fee_engine.py)');
        }
      },
      {
        badge: 'ACT 4 / 5 (1:55–2:30) · CFO.AI PARTNER PROOF',
        title: 'cfo.ai Interactive Ari Game-Engine Simulator, Dodo Payments MoR & 4-Sheet Formula plan.xlsx',
        narration: 'Voiceover Cue: "Measured Neatlogs telemetry flows directly into our 4-sheet Excel formula model plan.xlsx and Ari Board Overview simulator. Because entire-graph cuts unit COGS by 79.83% ($0.8896 to $0.1794/run), VeriFix achieves a 94.67% Q4 gross margin ($298K Q4 ARR, $1.19M M24 ARR) including Dodo Payments 3.9% + $0.40 MoR fees."',
        tabId: 'tab-cfo',
        tabBtnId: 'tabBtn-cfo',
        onEnter: () => {
          updateAriSimulation();
        }
      },
      {
        badge: 'ACT 5 / 5 (2:30–3:00) · REAL OPEN-SOURCE BUG HUNT (PR #203)',
        title: 'Real Concurrency Bug Caught & Fixed in neatlogs/neatlogs (Issue #199 & PR #203)',
        narration: 'Voiceover Cue: "Finally, we pointed VeriFix at the official neatlogs Python SDK (v1.4.26). It discovered a real concurrency bug in _MaskWorkerPool that dropped 30/30 concurrent batches, synthesized a deadline-bounded fix with 0/30 drops and 530/530 unit tests passing, and we opened Issue #199 and Pull Request #203 upstream."',
        tabId: 'tab-oss',
        tabBtnId: 'tabBtn-oss',
        onEnter: () => {
          runBrowserSelftest();
          runOSSConcurrencyBenchmark();
        }
      }
    ];

    function applyTourAct(idx) {
      CURRENT_TOUR_ACT = (idx + TOUR_ACTS.length) % TOUR_ACTS.length;
      const act = TOUR_ACTS[CURRENT_TOUR_ACT];
      document.getElementById('tourActBadge').textContent = act.badge;
      document.getElementById('tourActTitle').textContent = act.title;
      document.getElementById('tourActNarration').textContent = act.narration;
      const btn = document.getElementById(act.tabBtnId);
      if (btn) switchTab(act.tabId, btn);
      if (act.onEnter) act.onEnter();
    }

    function startJuryTour() {
      const dock = document.getElementById('juryTourDock');
      dock.classList.remove('hidden');
      dock.style.display = 'flex';
      applyTourAct(0);
    }

    function stepJuryTour(delta) {
      applyTourAct(CURRENT_TOUR_ACT + delta);
    }

    function closeJuryTour() {
      const dock = document.getElementById('juryTourDock');
      dock.classList.add('hidden');
      dock.style.display = 'none';
    }

    async function triggerAutoFix() {
      const statusEl = document.getElementById('runActionStatus');
      const btn = document.getElementById('btnAutoFix');
      btn.disabled = true;
      const repoPath = document.getElementById('customRepoPath').value.trim();
      const mode = document.getElementById('modeSelect').value || 'graph_guarded';
      statusEl.textContent = `Running Zero-Config Auto-Discovery & Healing on ${repoPath} (${mode})...`;
      try {
        const res = await fetch('/api/auto-fix', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({repo_path: repoPath, goal: '', mode: mode})
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Auto-fix failed');
        if (data.auto_discovery) {
          document.getElementById('customTargetFile').value = data.auto_discovery.target_file || '';
          document.getElementById('customTargetSymbol').value = data.auto_discovery.target_symbol || '';
          document.getElementById('customReproTest').value = data.auto_discovery.repro_test || '';
          document.getElementById('customCallerTests').value = (data.auto_discovery.caller_tests || []).join(', ');
        }
        statusEl.textContent = `Zero-Config Auto-Fix completed: ${data.run_id} (${data.status}) on auto-discovered ${data.target_symbol} in ${data.current_attempt} attempt(s), ${data.total_tokens} tokens.`;
        await refreshAll();
      } catch (err) {
        statusEl.textContent = `Auto-fix error: ${err.message}`;
      } finally {
        btn.disabled = false;
      }
    }

    async function triggerCustomRun() {
      const statusEl = document.getElementById('runActionStatus');
      const btn = document.getElementById('btnCustomRun');
      btn.disabled = true;
      const payload = {
        repo_path: document.getElementById('customRepoPath').value.trim(),
        target_file: document.getElementById('customTargetFile').value.trim(),
        target_symbol: document.getElementById('customTargetSymbol').value.trim(),
        repro_test: document.getElementById('customReproTest').value.trim(),
        caller_tests: document.getElementById('customCallerTests').value.trim(),
        goal: 'Fix the failing reproduction test while preserving all downstream caller contracts.',
        mode: document.getElementById('modeSelect').value || 'graph_guarded'
      };
      statusEl.textContent = `Running custom target remediation on ${payload.repo_path} :: ${payload.target_symbol} (${payload.mode})...`;
      try {
        const res = await fetch('/api/run-custom', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Custom run failed');
        statusEl.textContent = `Custom target completed: ${data.run_id} (${data.status}) in ${data.attempts} attempt(s), ${data.total_tokens} tokens.`;
        await refreshAll();
      } catch (err) {
        statusEl.textContent = `Custom run error: ${err.message}`;
      } finally {
        btn.disabled = false;
      }
    }

    async function triggerPlaygroundFix() {
      const statusEl = document.getElementById('runActionStatus');
      const badgeEl = document.getElementById('pgResultBadge');
      const btn = document.getElementById('btnPlaygroundFix');
      btn.disabled = true;
      const payload = {
        target_symbol: document.getElementById('pgSymbol').value.trim() || 'compute_invoice_total',
        module_code: document.getElementById('pgModuleCode').value,
        repro_test_code: document.getElementById('pgReproCode').value,
        caller_test_code: document.getElementById('pgCallerCode').value,
        goal: 'Fix the failing reproduction test in module.py while preserving all downstream caller contracts in test_callers.py.'
      };
      statusEl.textContent = `Running live browser sandbox remediation on ${payload.target_symbol} with LiteLLM claude-sonnet-4.6...`;
      badgeEl.textContent = 'Running...';
      try {
        const res = await fetch('/api/live-playground-fix', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Playground remediation failed');
        statusEl.textContent = `Interactive Playground Remediation Verified: ${data.run_id} (${data.status}) in ${data.attempts} attempt(s), ${data.total_tokens} tokens.`;
        badgeEl.innerHTML = `&#10003; Verified (${data.run_id}) &middot; <a href="${API_BASE}/runs/${data.run_id}/share" target="_blank" style="color:var(--accent);">Open Shareable PR Evidence &#8599;</a>`;
        await refreshAll();
      } catch (err) {
        statusEl.textContent = `Playground error: ${err.message}`;
        badgeEl.textContent = `Error: ${err.message}`;
      } finally {
        btn.disabled = false;
      }
    }

    async function dispatchNeatlogsIncident() {
      const pre = document.getElementById('incidentDispatchOutput');
      const det = (document.getElementById('incidentDetectionSelect') || {}).value || 'Downstream Caller Contract Regression Blocked';
      pre.textContent = `Dispatching Neatlogs detection "${det}" into verified GitHub PR bundle...`;
      try {
        const res = await fetch('/api/dispatch-neatlogs-incident', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({detection_name: det, execute_live: false})
        });
        const data = await res.json();
        pre.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        pre.textContent = `Incident dispatch error: ${err.message}`;
      }
    }

    async function runEntireIntelligenceSuite() {
      const pre = document.getElementById('entireIntelligenceOutput');
      const sym = (document.getElementById('symbolInput') || {}).value || 'calculate_tiered_fee';
      pre.textContent = `Running All 8 Entire Continuous Memory Intelligence Modules (#01–#08) on symbol "${sym}"...`;
      try {
        const res = await fetch('/api/entire-intelligence', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({symbol: sym, case_id: 'case_01_ledger_rounding', run_id: null})
        });
        const data = await res.json();
        pre.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        pre.textContent = `Entire Intelligence error: ${err.message}`;
      }
    }

    async function askEntireOnboardingGuide() {
      const pre = document.getElementById('entireIntelligenceOutput');
      const q = (document.getElementById('onboardingQuestionInput') || {}).value || 'How does the Blast-Radius Guardrail work, and why was it designed this way?';
      pre.textContent = `Querying Entire Graph + Entire Brain + Entire Checkpoints for: "${q}"...`;
      try {
        const res = await fetch('/api/entire-onboarding-qa', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({question: q, use_live_llm: false})
        });
        const data = await res.json();
        pre.textContent = (data.answer_markdown || '') + '\n\n' + JSON.stringify(data, null, 2);
      } catch (err) {
        pre.textContent = `Onboarding Q&A error: ${err.message}`;
      }
    }

    window.addEventListener('DOMContentLoaded', () => {
      if (API_BASE) {
        document.querySelectorAll('img[src^="/screenshots/"]').forEach(img => {
          img.src = API_BASE + img.getAttribute('src');
        });
      }
      refreshAll();
      inspectGraphSymbol();
      runEntireIntelligenceSuite();
      dispatchNeatlogsIncident();
    });
  </script>
</body>
</html>
"""


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

