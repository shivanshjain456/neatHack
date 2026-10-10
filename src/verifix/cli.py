"""Command-line interface for VeriFix (`verifix`)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from verifix.agent_harness import BENCHMARK_CATALOG, VeriFixAgentHarness
from verifix.cfo_economics import CFOEconomicsEngine
from verifix.entire_intelligence import EntireIntelligenceEngine
from verifix.incident_dispatcher import NeatlogsIncidentDispatcher
from verifix.neatlogs_mcp_client import NeatlogsMCPClient


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="verifix",
        description="VeriFix: Autonomous Blast-Radius-Aware Root-Cause & Verified-Patch Engineering Agent",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # `verifix run`
    p_run = sub.add_parser("run", help="Execute a defect remediation run on a benchmark case")
    p_run.add_argument("--case", default="case_01_ledger_rounding", choices=list(BENCHMARK_CATALOG.keys()))
    p_run.add_argument("--mode", default="graph_guarded", choices=["graph_guarded", "baseline_naive"])
    p_run.add_argument("--inject-caller-trap", action="store_true", help="Inject caller-breaking Attempt #1 to test guardrail rollback & recovery")
    p_run.add_argument("--interrupt-after", default=None, choices=["REPRODUCING"], help="Simulate process interruption after phase")
    p_run.add_argument("--json", action="store_true", help="Emit JSON output")

    # `verifix resume`
    p_res = sub.add_parser("resume", help="Resume an interrupted run from its SQLite WAL checkpoint")
    p_res.add_argument("--run-id", required=True, help="Run ID to resume")
    p_res.add_argument("--json", action="store_true", help="Emit JSON output")

    # `verifix experiment`
    p_exp = sub.add_parser("experiment", help="Run controlled Before (Run A) vs. After (Run B) Neatlogs optimization experiment")
    p_exp.add_argument("--case", default="case_01_ledger_rounding", choices=list(BENCHMARK_CATALOG.keys()))
    p_exp.add_argument("--json", action="store_true", help="Emit JSON output")

    # `verifix mcp-traces`
    p_mcp = sub.add_parser("mcp-traces", help="Query live traces from https://ingest.neatlogs.com/mcp")
    p_mcp.add_argument("--limit", type=int, default=10)

    # `verifix cfo-model`
    p_cfo = sub.add_parser("cfo-model", help="Generate cfo.ai financial model from measured run telemetry")
    p_cfo.add_argument("--output", default=None, help="Optional JSON file path to save model")

    # `verifix serve`
    p_srv = sub.add_parser("serve", help="Start the VeriFix Mission-Control FastAPI server")
    p_srv.add_argument("--host", default="0.0.0.0")
    p_srv.add_argument("--port", type=int, default=8000)

    # `verifix selftest`
    sub.add_parser("selftest", help="Run the 6-point Jury Self-Test across Entire, Neatlogs, cfo.ai, and AWS Lambda")

    # `verifix fix-custom`
    p_cust = sub.add_parser("fix-custom", help="Run VeriFix autonomous remediation on any arbitrary local Python repository")
    p_cust.add_argument("--repo-path", required=True, help="Path to the target Python repository")
    p_cust.add_argument("--target-file", required=True, help="Relative path to target Python file inside repo")
    p_cust.add_argument("--target-symbol", required=True, help="Target function or method symbol")
    p_cust.add_argument("--repro-test", required=True, help="Relative pytest target for reproducing the defect")
    p_cust.add_argument("--caller-tests", nargs="*", default=None, help="Downstream caller pytest targets for blast-radius guardrail")
    p_cust.add_argument("--goal", default="Localize and remediate the failing test while preserving all downstream caller contracts.")
    p_cust.add_argument("--json", action="store_true", help="Emit JSON output")

    # `verifix auto-fix`
    p_auto = sub.add_parser(
        "auto-fix",
        help="Zero-config autonomous remediation: auto-discover failing pytest, root-cause symbol & caller suite via entire-graph, then heal",
    )
    p_auto.add_argument("--repo-path", required=True, help="Path to any local Python repository with a failing pytest test")
    p_auto.add_argument("--goal", default="", help="Optional natural-language goal or bug description")
    p_auto.add_argument("--json", action="store_true", help="Emit JSON output")

    # `verifix entire-intelligence`
    p_ent = sub.add_parser(
        "entire-intelligence",
        help="Run Entire Continuous Memory Intelligence Suite (Pre-Build Briefing, Agent Mistake Debugger, Intent Reviewer, Regression Scout, Checkpoint Walkthrough)",
    )
    p_ent.add_argument("--symbol", default="calculate_tiered_fee")
    p_ent.add_argument("--case", default="case_01_ledger_rounding")
    p_ent.add_argument("--run-id", default=None)

    # `verifix dispatch-incident`
    p_disp = sub.add_parser(
        "dispatch-incident",
        help="Dispatch a Neatlogs Detection / Incident into a verified GitHub PR bundle (bypassing ingest.neatlogs.com OAuth redirect failure)",
    )
    p_disp.add_argument("--detection", default="Downstream Caller Contract Regression Blocked")
    p_disp.add_argument("--live", action="store_true", help="Execute a fresh live remediation run before generating the PR bundle")

    args = parser.parse_args(argv)
    console = Console()

    if args.command == "entire-intelligence":
        eng = EntireIntelligenceEngine()
        briefing = eng.generate_pre_build_briefing(symbol=args.symbol, case_id=args.case)
        review = eng.review_intent_and_scout_regressions(run_id=args.run_id)
        print(json.dumps({"pre_build_briefing": briefing, "intent_and_regression_review": review}, indent=2, default=str))
        return 0

    if args.command == "dispatch-incident":
        disp = NeatlogsIncidentDispatcher()
        res = disp.dispatch_incident(detection_name=args.detection, execute_live=args.live)
        print(json.dumps(res, indent=2, default=str))
        return 0

    if args.command == "auto-fix":
        harness = VeriFixAgentHarness()
        res = harness.auto_discover_and_execute(repo_path=args.repo_path, goal=args.goal)
        disc = res.get("auto_discovery") or {}
        if args.json:
            print(json.dumps(res, indent=2, default=str))
        else:
            console.print(
                Panel(
                    f"[bold green]Run ID:[/bold green] {res['run_id']}\n"
                    f"[bold cyan]Auto-Discovered Target:[/bold cyan] {disc.get('target_file')} :: {disc.get('target_symbol')}\n"
                    f"[bold cyan]Auto-Discovered Repro Test:[/bold cyan] {disc.get('repro_test')} | Caller Tests: {disc.get('caller_tests')}\n"
                    f"[bold yellow]Status:[/bold yellow] {res['status']} (Attempts: {res['current_attempt']})\n"
                    f"[bold magenta]Tokens:[/bold magenta] {res['total_tokens']} (Prompt: {res['prompt_tokens']}, Completion: {res['completion_tokens']})\n"
                    f"[bold red]Caller Regressions Caught & Rolled Back:[/bold red] {res['caller_regressions_caught']}",
                    title="VeriFix Zero-Config Autonomous Remediation Summary",
                    expand=False,
                )
            )
        return 0 if res["status"] == "VERIFIED_COMPLETE" else 1


    if args.command == "fix-custom":
        harness = VeriFixAgentHarness()
        res = harness.execute_custom_target(
            repo_path=args.repo_path,
            target_file=args.target_file,
            target_symbol=args.target_symbol,
            repro_test=args.repro_test,
            caller_tests=args.caller_tests,
            goal=args.goal,
        )
        if args.json:
            print(json.dumps(res, indent=2, default=str))
        else:
            console.print(
                Panel(
                    f"[bold green]Run ID:[/bold green] {res['run_id']}\n"
                    f"[bold cyan]Custom Target:[/bold cyan] {res['case_id']} ({res['target_symbol']})\n"
                    f"[bold yellow]Status:[/bold yellow] {res['status']} (Attempts: {res['current_attempt']})\n"
                    f"[bold magenta]Tokens:[/bold magenta] {res['total_tokens']}\n"
                    f"[bold blue]Caller Regressions Caught:[/bold blue] {res['caller_regressions_caught']}",
                    title="VeriFix Custom Repository Remediation Summary",
                )
            )
        return 0

    if args.command == "run":
        harness = VeriFixAgentHarness()
        res = harness.execute_case(
            case_id=args.case,
            mode=args.mode,
            inject_caller_regression_on_attempt_1=args.inject_caller_trap,
            simulate_interrupt_after_phase=args.interrupt_after,
        )
        if args.json:
            print(json.dumps(res, indent=2, default=str))
        else:
            console.print(
                Panel(
                    f"[bold green]Run ID:[/bold green] {res['run_id']}\n"
                    f"[bold cyan]Case:[/bold cyan] {res['case_id']} ({res['mode']})\n"
                    f"[bold yellow]Status:[/bold yellow] {res['status']} (Attempts: {res['current_attempt']})\n"
                    f"[bold magenta]Tokens:[/bold magenta] {res['total_tokens']} (Prompt: {res['prompt_tokens']}, Completion: {res['completion_tokens']})\n"
                    f"[bold blue]Caller Regressions Caught & Rolled Back:[/bold blue] {res['caller_regressions_caught']}",
                    title="VeriFix Autonomous Remediation Summary",
                )
            )
        return 0

    if args.command == "resume":
        harness = VeriFixAgentHarness()
        existing = harness.store.get_run(args.run_id)
        if not existing:
            console.print(f"[red]Run ID not found: {args.run_id}[/red]")
            return 1
        res = harness.execute_case(
            case_id=existing["case_id"],
            mode=existing["mode"],
            resume_run_id=args.run_id,
        )
        if args.json:
            print(json.dumps(res, indent=2, default=str))
        else:
            console.print(f"[bold green]Resumed & Completed Run:[/bold green] {res['run_id']} -> {res['status']}")
        return 0

    if args.command == "experiment":
        harness = VeriFixAgentHarness()
        comp = harness.run_before_after_experiment(case_id=args.case)
        if args.json:
            print(json.dumps(comp, indent=2, default=str))
        else:
            t = Table(title=f"VeriFix Controlled Experiment: {comp['workload_title']}")
            t.add_column("Metric", style="bold")
            t.add_column("Run A (Before: Naive Baseline)", style="yellow")
            t.add_column("Run B (After: Entire-Graph + Guardrail)", style="green")
            t.add_column("Measured Delta", style="cyan")
            ra = comp["run_a_before"]
            rb = comp["run_b_after"]
            d = comp["measured_delta"]
            t.add_row("Run ID", str(ra["run_id"]), str(rb["run_id"]), comp["experiment_id"])
            t.add_row("Prompt Tokens", str(ra["prompt_tokens"]), str(rb["prompt_tokens"]), f"-{d['prompt_token_reduction_pct']}%")
            t.add_row("Total Tokens", str(ra["total_tokens"]), str(rb["total_tokens"]), f"-{d['total_token_reduction_pct']}%")
            t.add_row("Latency (ms)", str(ra["total_latency_ms"]), str(rb["total_latency_ms"]), f"-{d['latency_reduction_pct']}%")
            t.add_row("Attempts", str(ra["attempts"]), str(rb["attempts"]), f"-{d['attempts_saved']} retry")
            t.add_row("Caller Regressions Caught", str(ra["caller_regressions_caught"]), str(rb["caller_regressions_caught"]), "100% Guarded")
            console.print(t)
        return 0

    if args.command == "mcp-traces":
        mcp = NeatlogsMCPClient()
        who = mcp.whoami()
        traces = mcp.search_traces(limit=args.limit)
        print(json.dumps({"whoami": who, "traces": traces}, indent=2))
        return 0

    if args.command == "cfo-model":
        harness = VeriFixAgentHarness()
        exps = harness.store.list_experiments(limit=1)
        if not exps:
            print("No recorded before/after experiment yet. Run `verifix experiment` first; "
                  "the cost model is only built from measured runs.", file=sys.stderr)
            return 2
        c = exps[0]["comparison"]
        ra, rb = c["run_a_before"], c["run_b_after"]
        eng = CFOEconomicsEngine()
        model = eng.build_model_from_telemetry(ra, rb)
        if args.output:
            Path(args.output).write_text(json.dumps(model, indent=2), encoding="utf-8")
        print(json.dumps(model, indent=2))
        return 0

    if args.command == "serve":
        import uvicorn

        uvicorn.run("verifix.server:app", host=args.host, port=args.port, reload=False)
        return 0

    if args.command == "selftest":
        import importlib.util

        selftest_path = Path(__file__).resolve().parents[2] / "scripts" / "jury_selftest.py"
        spec = importlib.util.spec_from_file_location("jury_selftest", selftest_path)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            rep = mod.run_jury_selftest(Path(__file__).resolve().parents[2])
            return 0 if rep.get("all_passed") else 1
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
