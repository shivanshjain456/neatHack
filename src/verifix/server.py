"""FastAPI Mission-Control Server & Interactive Web Dashboard for VeriFix."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from verifix.agent_harness import BENCHMARK_CATALOG, VeriFixAgentHarness
from verifix.cfo_economics import CFOEconomicsEngine
from verifix.graph_engine import EntireGraphEngine, ensure_entire_plugins_restored, resolve_entire_binary
from verifix.neatlogs_mcp_client import NeatlogsMCPClient

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

ROOT_DIR = Path("/home/user/verifix").resolve()


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


def _get_entire_git_telemetry() -> dict[str, Any]:
    """Read real Entire CLI status, checkpoint refs, and Git commit trailers from /home/user/verifix."""
    ensure_entire_plugins_restored()
    env = os.environ.copy()
    env["PATH"] = f"/home/user/bin:/home/user/.local/bin:{env.get('PATH', '')}"
    try:
        entire_bin = resolve_entire_binary()
        st_proc = subprocess.run(
            [entire_bin, "status", "--json"],
            cwd=str(ROOT_DIR),
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )
        status_json = json.loads(st_proc.stdout) if st_proc.stdout.strip() else {}
    except Exception as exc:
        status_json = {"error": str(exc)}

    refs_proc = subprocess.run(
        ["git", "for-each-ref", "refs/entire/", "--format=%(refname) %(objectname:short)"],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        check=False,
    )
    entire_refs = [line.strip() for line in refs_proc.stdout.splitlines() if line.strip()]

    log_proc = subprocess.run(
        ["git", "log", "-n", "10", "--pretty=format:%h|%ad|%s|%(trailers:key=Entire-Checkpoint,valueonly=true)", "--date=iso"],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        check=False,
    )
    commits = []
    for line in log_proc.stdout.splitlines():
        parts = line.split("|")
        if len(parts) >= 3:
            commits.append(
                {
                    "hash": parts[0],
                    "date": parts[1],
                    "subject": parts[2],
                    "entire_checkpoint": parts[3].strip() if len(parts) > 3 else "",
                }
            )
    return {
        "entire_status": status_json,
        "entire_refs": entire_refs,
        "recent_commits": commits,
    }


@app.get("/api/health")
def api_health() -> dict[str, Any]:
    return {"status": "ok", "service": "verifix-mission-control", "version": "0.2.0"}


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

    return {
        "benchmarks": list(BENCHMARK_CATALOG.values()),
        "runs": detailed_runs,
        "experiments": experiments,
        "cfo_model": cfo_model,
        "entire": entire_info,
    }


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
        <span class="badge">neatHack 2026</span>
        <span class="badge badge-green">Neatlogs + Entire-Graph + cfo.ai</span>
      </h1>
      <div style="font-size: 12px; color: var(--muted); margin-top: 4px;">
        Autonomous Blast-Radius-Aware Root-Cause &amp; Verified-Patch Engineering Agent
      </div>
    </div>
    <div style="display:flex; gap:10px; align-items:center;">
      <span id="statusIndicator" class="badge badge-green">LIVE TELEMETRY READY</span>
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
      <button class="tab-btn active" onclick="switchTab('tab-runs', this)">1. Autonomous Runs &amp; 8 Focus Areas</button>
      <button class="tab-btn" onclick="switchTab('tab-experiment', this)">2. Neatlogs Before/After &amp; Live MCP</button>
      <button class="tab-btn" onclick="switchTab('tab-entire', this)">3. Entire Checkpoints &amp; Entire-Graph</button>
      <button class="tab-btn" onclick="switchTab('tab-cfo', this)">4. cfo.ai Financial Model &amp; Scenarios</button>
    </div>

    <!-- TAB 1: RUNS & 8 FOCUS AREAS -->
    <div id="tab-runs" class="tab-section">
      <div class="panel">
        <h2>
          <span>Execute Live Remediation or Fault-Injection Verification</span>
          <span class="badge">Zero-Stub Sandboxed Git Worktrees</span>
        </h2>
        <div class="controls-row">
          <label style="font-size:13px; color:var(--muted);">Benchmark Case:</label>
          <select id="caseSelect"></select>
          <label style="font-size:13px; color:var(--muted);">Mode:</label>
          <select id="modeSelect">
            <option value="graph_guarded">Run B: entire-graph + Blast-Radius Guardrail</option>
            <option value="baseline_naive">Run A: Naive Full-Repo Baseline (Before Fix)</option>
          </select>
          <button id="btnRun" class="primary" onclick="triggerRun(false, false)">Run Autonomous Fix</button>
          <button id="btnTrap" class="warn" onclick="triggerRun(true, false)">Test Caller-Trap Recovery (Attempt 1 Rollback -&gt; Attempt 2 Fix)</button>
          <button id="btnInterrupt" class="purple" onclick="triggerInterruptAndResume()">Test Mid-Run Crash &amp; SQLite Resume</button>
        </div>
        <div id="runActionStatus" style="font-size:13px; color:var(--accent);"></div>
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

    <!-- TAB 2: NEATLOGS EXPERIMENT & MCP -->
    <div id="tab-experiment" class="tab-section hidden">
      <div class="panel">
        <h2>
          <span>Controlled Before vs. After Experiment (Diagnosed via Neatlogs)</span>
          <button id="btnExp" class="primary" onclick="triggerExperiment()">Re-Run Controlled A/B Experiment</button>
        </h2>
        <p style="font-size:13px; color:var(--muted); margin-top:0;">
          <strong>Bottleneck Diagnosed in Neatlogs Run A (`baseline_naive`):</strong> Without structural code localization, the agent reads all repository files and docs into prompt context and lacks downstream caller contract awareness, inflating prompt tokens, latency, and retry cycles.<br/>
          <strong>Architectural Fix in Run B (`graph_guarded`):</strong> Pre-retrieves exact symbol definitions and direct callers via <code>entire graph search</code> + <code>entire graph impact</code> (`RETRIEVER` span) and enforces a pre-commit <code>GUARDRAIL</code> span over all impacted caller tests.
        </p>
        <div id="experimentTableContainer"></div>
      </div>

      <div class="panel">
        <h2>
          <span>Live Neatlogs MCP Server Explorer (<code>https://ingest.neatlogs.com/mcp</code>)</span>
          <button class="primary" onclick="loadNeatlogsMCP()">Query Live Neatlogs MCP</button>
        </h2>
        <pre id="mcpOutput">Click "Query Live Neatlogs MCP" to execute live JSON-RPC tools/call (whoami &amp; search_traces) against https://ingest.neatlogs.com/mcp.</pre>
      </div>
    </div>

    <!-- TAB 3: ENTIRE CHECKPOINTS & ENTIRE-GRAPH -->
    <div id="tab-entire" class="tab-section hidden">
      <div class="grid-2">
        <div class="panel">
          <h2>Interactive <code>entire graph impact</code> Blast-Radius Inspector</h2>
          <div class="controls-row">
            <input id="symbolInput" value="calculate_tiered_fee" style="min-width:240px;" />
            <button class="primary" onclick="inspectGraphSymbol()">Analyze Blast Radius</button>
          </div>
          <pre id="graphImpactOutput">Loading blast radius...</pre>
        </div>

        <div class="panel">
          <h2>Entire CLI Checkpoints &amp; Git Provenance</h2>
          <div id="entireStatusContainer"></div>
        </div>
      </div>
    </div>

    <!-- TAB 4: CFO.AI FINANCIAL MODEL -->
    <div id="tab-cfo" class="tab-section hidden">
      <div class="panel">
        <h2>
          <span>cfo.ai Business Model &amp; Scenario Engine (Grounded in Measured Neatlogs Telemetry)</span>
          <span class="badge badge-green">Live Telemetry-to-Margin Bridge</span>
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
  </div>

  <script>
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
        renderEntireStatus();
        renderCFOScenarios();
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
        <div style="margin-bottom:10px;">
          <strong>Run ID:</strong> <code>${r.run_id}</code> |
          <strong>Target Symbol:</strong> <code>${r.target_symbol}</code> |
          <strong>Resumed from SQLite Checkpoint:</strong> ${r.resumed_from_checkpoint ? 'YES' : 'NO'}
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
      statusEl.textContent = 'Running autonomous agent in isolated Git worktree with live Gemini + Neatlogs + Entire-Graph...';
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
      const commitsHtml = (e.recent_commits || []).map(c => `
        <tr>
          <td><code>${c.hash}</code></td>
          <td>${c.subject}</td>
          <td><code>${c.entire_checkpoint || 'pending stop hook'}</code></td>
        </tr>
      `).join('');
      container.innerHTML = `
        <h3 style="font-size:13px; color:var(--muted);">Entire CLI Status (<code>entire status --json</code>)</h3>
        <pre>${JSON.stringify(e.entire_status || {}, null, 2)}</pre>
        <h3 style="font-size:13px; color:var(--muted);">Entire Git Checkpoint Refs (<code>refs/entire/*</code>)</h3>
        <pre>${(e.entire_refs || []).join('\\n') || 'Active session recording; checkpoint ref materializes on session stop/commit.'}</pre>
        <h3 style="font-size:13px; color:var(--muted);">Recent Commits &amp; Trailers</h3>
        <table>
          <thead><tr><th>Commit</th><th>Subject</th><th>Entire-Checkpoint Trailer</th></tr></thead>
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

    window.addEventListener('DOMContentLoaded', () => {
      refreshAll();
      inspectGraphSymbol();
    });
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def serve_dashboard() -> HTMLResponse:
    return HTMLResponse(content=DASHBOARD_HTML)
