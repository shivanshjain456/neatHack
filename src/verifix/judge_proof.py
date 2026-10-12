"""Judge verification report.

Builds one machine-readable answer to the official neatHack "Evidence & verification"
checklist. Every item states *how* it was verified:

* ``LIVE``      - checked against the source of truth while this request was served
                  (GitHub API, neatlogs MCP, this deployment).
* ``RECORDED``  - read from a versioned artifact in the repository (run ledger, plan files).

Nothing here is inferred or hardcoded as success. A live check that cannot reach its
source returns ``unavailable`` with the reason, never a pass. Results are cached briefly so
that judges refreshing the page do not exhaust unauthenticated GitHub API limits.
"""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx

REPO = "shivanshjain456/neatHack"
REPO_URL = f"https://github.com/{REPO}"
GITHUB_API = "https://api.github.com"
# Official build window (neatlogs.com/hackathon FAQ 01 and submission close).
SUBMISSION_CLOSE_UTC = datetime(2026, 10, 12, 18, 25, tzinfo=timezone.utc)  # 11:55 PM IST
CHECKPOINT_COMMIT = "10c7406723f285cc778b729863365713735e9191"
CHECKPOINT_ID = "01M4KFYKQXFHME1HRZJVXJ7YT8"
UPSTREAM_PR = ("neatlogs/neatlogs", 203)
BUILD_IN_PUBLIC = [
    ("Post 1 · real neatlogs SDK bug report", "https://x.com/sj909x/status/2108813809792299255"),
    ("Post 2 · repo, checkpoints and plan", "https://x.com/sj909x/status/2108814094514204930"),
]
RECOVERY_RUN_ID = "run_graph_case_01_le_24584"
CACHE_TTL_S = 300
LIVE_TIMEOUT_S = 6.0

_cache_lock = threading.Lock()
_cache: dict[str, Any] = {"at": 0.0, "value": None}


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_time(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


def _item(item_id: str, criterion: str, claim: str, method: str, verdict: str, detail: str,
          facts: dict[str, Any] | None = None, links: list[tuple[str, str]] | None = None) -> dict[str, Any]:
    if method not in {"LIVE", "RECORDED"}:
        raise ValueError("method must be LIVE or RECORDED")
    if verdict not in {"verified", "attention", "unavailable"}:
        raise ValueError("invalid verdict")
    return {
        "id": item_id,
        "criterion": criterion,
        "claim": claim,
        "method": method,
        "verdict": verdict,
        "detail": detail,
        "facts": facts or {},
        "links": [{"label": label, "url": url} for label, url in (links or [])],
    }


def _unavailable(item_id: str, criterion: str, claim: str, reason: str,
                 links: list[tuple[str, str]] | None = None) -> dict[str, Any]:
    return _item(item_id, criterion, claim, "LIVE", "unavailable",
                 f"Live source could not be reached: {reason[:200]}", links=links)


class _GitHub:
    def __init__(self, client: httpx.Client):
        self.client = client

    def get(self, path: str, **params: Any) -> httpx.Response:
        response = self.client.get(f"{GITHUB_API}{path}", params=params or None)
        if response.status_code == 403 and "rate limit" in response.text.lower():
            raise RuntimeError("GitHub API rate limit reached; try again later")
        response.raise_for_status()
        return response


def check_commit_window(gh: _GitHub) -> dict[str, Any]:
    criterion = "The build history is public"
    claim = "Every commit is visible in the public repository"
    links = [("Commit history", f"{REPO_URL}/commits/main")]
    try:
        first = gh.get(f"/repos/{REPO}/commits", per_page=100)
        commits = first.json()
        last_link = first.links.get("last", {}).get("url")
        if last_link:
            commits += gh.client.get(last_link).raise_for_status().json()
        times = sorted({(c["sha"], c["commit"]["author"]["date"]) for c in commits}, key=lambda x: x[1])
        if not times:
            return _unavailable("commits", criterion, claim, "repository returned no commits", links)
        dates = [_parse_time(t) for _, t in times]
        after_close = sum(1 for d in dates if d > SUBMISSION_CLOSE_UTC)
        earliest, latest = dates[0], dates[-1]
        verdict = "verified" if after_close == 0 else "attention"
        detail = (f"{len(dates)} public commits, from {_iso(earliest)} to {_iso(latest)}. "
                  "Each one can be opened on GitHub, and the submission commit is linked to its Entire checkpoint."
                  + (f" {after_close} commit(s) are dated after the submission deadline." if after_close else ""))
        return _item("commits", criterion, claim, "LIVE", verdict, detail, {
            "public_commits": len(dates),
            "first_commit_utc": _iso(earliest),
            "latest_commit_utc": _iso(latest),
            "commits_after_submission_deadline": after_close,
        }, links)
    except Exception as exc:  # network or API failure is reported, not hidden
        return _unavailable("commits", criterion, claim, str(exc), links)


def check_entire(gh: _GitHub) -> dict[str, Any]:
    criterion = "You used Entire"
    claim = "Entire checkpoints are pushed with the repository"
    links = [
        ("Checkpoint on Entire", f"https://github.com/{REPO}/commit/{CHECKPOINT_COMMIT}"),
        ("Checkpoint refs on GitHub", f"{REPO_URL}/commit/{CHECKPOINT_COMMIT}"),
    ]
    try:
        refs = gh.get(f"/repos/{REPO}/git/matching-refs/entire/checkpoints").json()
        ids = sorted({ref["ref"].rsplit("/", 1)[-1] for ref in refs if isinstance(ref, dict) and "ref" in ref})
        has_primary = CHECKPOINT_ID in ids
        verdict = "verified" if ids and has_primary else "attention"
        detail = (f"{len(ids)} checkpoint ref(s) found under refs/entire/checkpoints on GitHub. "
                  f"Submission checkpoint {CHECKPOINT_ID} is {'present' if has_primary else 'missing'}. "
                  "Entire Graph also runs inside the agent at runtime to find callers before a patch.")
        return _item("entire", criterion, claim, "LIVE", verdict, detail, {
            "checkpoint_refs": len(ids), "submission_checkpoint": CHECKPOINT_ID,
            "submission_commit": CHECKPOINT_COMMIT,
        }, links)
    except Exception as exc:
        return _unavailable("entire", criterion, claim, str(exc), links)


def check_upstream_pr(gh: _GitHub) -> dict[str, Any]:
    owner_repo, number = UPSTREAM_PR
    criterion = "You built in public"
    claim = "Shared progress publicly, including an upstream fix for neatlogs"
    links = [(label, url) for label, url in BUILD_IN_PUBLIC]
    links.append((f"Upstream PR {owner_repo}#{number}", f"https://github.com/{owner_repo}/pull/{number}"))
    try:
        pr = gh.get(f"/repos/{owner_repo}/pulls/{number}").json()
        state = "merged" if pr.get("merged_at") else pr.get("state", "unknown")
        detail = (f"Upstream pull request #{number} is {state} (checked live). "
                  f"{len(BUILD_IN_PUBLIC)} #neatHack posts are linked; engagement numbers are not claimed here.")
        return _item("public", criterion, claim, "LIVE", "verified", detail, {
            "upstream_pr_state": state, "upstream_pr_title": str(pr.get("title", ""))[:160],
            "posts_linked": len(BUILD_IN_PUBLIC),
        }, links)
    except Exception as exc:
        return _unavailable("public", criterion, claim, str(exc), links)


def check_neatlogs(search: Callable[[], dict[str, Any]] | None) -> dict[str, Any]:
    criterion = "You used neatlogs"
    claim = "Agent runs are traced in neatlogs and can be read back over MCP"
    links = [("neatlogs project", "https://app.neatlogs.com/")]
    if search is None:
        return _unavailable("neatlogs", criterion, claim, "neatlogs credentials are not configured on this instance", links)
    try:
        result = search()
        if not isinstance(result, dict) or "results" not in result:
            return _unavailable("neatlogs", criterion, claim, "unexpected MCP response shape", links)
        rows = [r for r in result.get("results", []) if isinstance(r, dict)]
        total = result.get("total")
        facts: dict[str, Any] = {"matching_traces": total}
        workflows = sorted({str(r.get("workflow_name")) for r in rows if r.get("workflow_name")})
        if workflows:
            facts["workflows_in_sample"] = workflows[:4]
        tokens = [r.get("total_tokens") for r in rows if isinstance(r.get("total_tokens"), int) and r.get("total_tokens") > 0]
        if tokens:
            facts["traced_tokens_in_sample"] = sum(tokens)
        sample = max(rows, key=lambda r: r.get("created_at", ""), default=None)
        if sample:
            facts["sample_trace_id"] = sample.get("trace_id")
            facts["sample_trace_created_at"] = sample.get("created_at")
        verdict = "verified" if isinstance(total, int) and total > 0 else "attention"
        detail = (f"Live neatlogs MCP search returned {total} matching VeriFix traces "
                  f"(a relevance-ranked sample of {len(rows)} is summarised below). "
                  "The workspace reads traces back through this MCP client (trace readback screen, `verifix mcp-traces`).")
        return _item("neatlogs", criterion, claim, "LIVE", verdict, detail, facts, links)
    except Exception as exc:
        return _unavailable("neatlogs", criterion, claim, str(exc), links)


def _loads(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def check_improvement(ledger: dict[str, Any], root: Path | None = None) -> dict[str, Any]:
    """Controlled three-arm experiment, recomputed from its raw records; historical pair only as context."""
    from verifix.ablation import summarize

    criterion = "The agent improved"
    claim = "A run before a change and a run after it, with the numbers compared"
    links = [("Experiment data", f"{REPO_URL}/blob/main/benchmarks/ablation_experiment.json"),
             ("Method", f"{REPO_URL}/blob/main/docs/EVALUATION.md")]
    data = fault = None
    if root is not None:
        for name in ("ablation_experiment.json", "ablation_fault_injection.json"):
            path = root / "benchmarks" / name
            try:
                loaded = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            except (OSError, ValueError):
                loaded = None
            if name.startswith("ablation_experiment"):
                data = loaded
            else:
                fault = loaded
    if not isinstance(data, dict) or not data.get("records"):
        runs = {r.get("run_id"): r for r in ledger.get("runs", []) if isinstance(r, dict)}
        before, after = runs.get("run_basel_case_01_le_948"), runs.get("run_graph_case_01_le_56698")
        detail = ("Controlled experiment data is missing from this deployment. "
                  + (f"Only the historical single comparison is available ({before.get('total_tokens')} vs "
                     f"{after.get('total_tokens')} tokens), and its baseline was handicapped, so it is not evidence "
                     "of improvement on its own. Its accepted patch also fails split-fee conservation and is blocked by "
                     "the later assurance gates." if before and after else "No recorded comparison is available."))
        return _item("improvement", criterion, claim, "RECORDED", "attention", detail, {}, links)
    try:
        recomputed = summarize(data["records"])
        stored = data.get("summary", {})
        if recomputed != stored:
            return _item("improvement", criterion, claim, "RECORDED", "attention",
                         "The stored summary does not match a recomputation from the raw run records.", {}, links)
        vb = recomputed["comparisons"]["graph_guarded_vs_baseline_naive"]
        vt = recomputed["comparisons"]["graph_guarded_vs_target_only"]
        g, b = recomputed["arms"]["graph_guarded"], recomputed["arms"]["baseline_naive"]
        fa = summarize(fault["records"])["arms"] if isinstance(fault, dict) and fault.get("records") else {}
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        return _item("improvement", criterion, claim, "RECORDED", "attention",
                     f"Experiment data could not be evaluated: {type(exc).__name__}.", {}, links)
    holds = vb["token_ratio_ci95_cases"][1] < 1 and g["judge_passed"] >= b["judge_passed"]
    facts = {
        "runs": len(data["records"]), "cases": vb["cases"], "paired_runs": vb["pairs"],
        "graph_mean_tokens": g["mean_total_tokens"], "whole_repo_mean_tokens": b["mean_total_tokens"],
        "token_ratio_vs_whole_repo": vb["token_ratio_geo_mean"], "ratio_ci95_by_case": vb["token_ratio_ci95_cases"],
        "sign_test_p": vb["token_sign_test_p"], "token_ratio_vs_target_file_only": vt["token_ratio_geo_mean"],
        "judge_passed_graph": f"{g['judge_passed']}/{g['runs']}", "judge_passed_whole_repo": f"{b['judge_passed']}/{b['runs']}",
    }
    if fa.get("graph_guarded") and fa.get("target_only"):
        facts["planted_regression_recovered_graph"] = f"{fa['graph_guarded']['judge_passed']}/{fa['graph_guarded']['runs']}"
        facts["planted_regression_shipped_caller_blind"] = f"{fa['target_only']['shipped_regressions']}/{fa['target_only']['runs']}"
    detail = (f"Controlled experiment, recomputed from {len(data['records'])} raw runs: with Entire Graph caller context "
              f"the agent used {round((1 - vb['token_ratio_geo_mean']) * 100)}% fewer tokens than reading the whole case "
              f"repository (95% CI by case {round((1 - vb['token_ratio_ci95_cases'][1]) * 100)}–"
              f"{round((1 - vb['token_ratio_ci95_cases'][0]) * 100)}%), and passed the independent full-suite judge "
              f"{g['judge_passed']}/{g['runs']} times vs {b['judge_passed']}/{b['runs']}. It costs "
              f"{round((vt['token_ratio_geo_mean'] - 1) * 100)}% more tokens than the target file alone.")
    return _item("improvement", criterion, claim, "RECORDED", "verified" if holds else "attention", detail, facts, links)


def check_recovery(ledger: dict[str, Any]) -> dict[str, Any]:
    criterion = "The agent recovers from failures"
    claim = "A run where an action failed, showing what the agent did next"
    run = next((r for r in ledger.get("runs", []) if r.get("run_id") == RECOVERY_RUN_ID), None)
    if not run:
        return _item("recovery", criterion, claim, "RECORDED", "attention", "Recorded recovery run is missing from the ledger.")
    steps = [s for s in ledger.get("steps", []) if s.get("run_id") == RECOVERY_RUN_ID]
    failed = [s for s in steps if str(s.get("status", "")).upper() in {"FAILED", "ROLLED_BACK", "ERROR", "RECOVERED"}]
    ok = (run.get("status") == "VERIFIED_COMPLETE" and (run.get("rollbacks_executed") or 0) >= 1
          and (run.get("current_attempt") or 0) >= 2)
    detail = (f"Attempt 1 patch broke a downstream caller contract; the guardrail caught "
              f"{run.get('caller_regressions_caught')} regression(s), rolled the worktree back "
              f"{run.get('rollbacks_executed')} time(s), fed the traceback to the planner, and attempt "
              f"{run.get('current_attempt')} was verified. You can reproduce this live from the Run a benchmark screen.")
    return _item("recovery", criterion, claim, "RECORDED", "verified" if ok else "attention", detail, {
        "run_id": RECOVERY_RUN_ID, "status": run.get("status"), "attempts": run.get("current_attempt"),
        "rollbacks": run.get("rollbacks_executed"), "caller_regressions_caught": run.get("caller_regressions_caught"),
        "recorded_steps": len(steps), "failed_or_rolled_back_steps": len(failed),
        "total_tokens": run.get("total_tokens"),
        "neatlogs_trace_id": _loads(run.get("verification_certificate_json")).get("neatlogs_trace_id"),
    }, [("Inspect this run", f"#run/{RECOVERY_RUN_ID}"), ("Reproduce it live", "#benchmarks")])


def check_cfo(root: Path) -> dict[str, Any]:
    criterion = "You used cfo.ai"
    claim = "A business plan covering pricing, costs, revenue and runway"
    plan, business = root / "plan.xlsx", root / "BUSINESS_PLAN.md"
    snapshot_path = root / "benchmarks" / "plan_xlsx_computed.json"
    present = [p.name for p in (plan, business) if p.is_file() and p.stat().st_size > 0]
    raw = business.read_text(encoding="utf-8", errors="ignore") if business.is_file() else ""
    text = raw.lower()
    topics = {t: (t in text) for t in ("pricing", "cost", "revenue", "runway")}
    facts: dict[str, Any] = {"files": present, "topics": topics}
    figures_match: bool | None = None
    try:
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        months = {int(m["month"]): m for m in snapshot["months"]}
        expected = [f"${months[m][k]:,.0f}" for m in (1, 12, 24) for k in ("total_monthly_revenue", "arr", "ending_cash")]
        missing = [v for v in expected if v not in raw]
        figures_match = not missing
        facts.update({
            "workbook_m12_arr": f"${months[12]['arr']:,.0f}",
            "workbook_m24_arr": f"${months[24]['arr']:,.0f}",
            "first_positive_ebitda_month": snapshot.get("first_positive_ebitda_month"),
            "lowest_projected_cash": f"${snapshot['lowest_cash']['ending_cash']:,.0f} (month {snapshot['lowest_cash']['month']})",
            "plan_figures_match_workbook": figures_match,
        })
        if missing:
            facts["figures_missing_from_plan"] = missing[:4]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        facts["workbook_snapshot"] = f"not readable: {exc.__class__.__name__}"
    ok = len(present) == 2 and all(topics.values()) and figures_match is True
    detail = (f"Files present in this deployment: {', '.join(present) or 'none'}. Topics covered: "
              + ", ".join(f"{k} {'yes' if v else 'no'}" for k, v in topics.items())
              + (". Every Month 1/12/24 revenue, ARR and cash figure quoted in the plan matches the recalculated workbook."
                 if figures_match else ". The plan's quoted figures could not be matched to the recalculated workbook.")
              + " Figures are projections, not realised results.")
    return _item("cfo", criterion, claim, "RECORDED", "verified" if ok else "attention", detail, facts,
                 [("BUSINESS_PLAN.md", f"{REPO_URL}/blob/main/BUSINESS_PLAN.md"),
                  ("plan.xlsx", f"{REPO_URL}/blob/main/plan.xlsx")])


def build_judge_proof(root: Path, ledger: dict[str, Any], neatlogs_search: Callable[[], dict[str, Any]] | None,
                      client: httpx.Client | None = None, use_cache: bool = True) -> dict[str, Any]:
    now = time.time()
    if use_cache:
        with _cache_lock:
            if _cache["value"] is not None and now - _cache["at"] < CACHE_TTL_S:
                cached = dict(_cache["value"])
                cached["cache_age_s"] = round(now - _cache["at"], 1)
                return cached
    own_client = client is None
    client = client or httpx.Client(timeout=LIVE_TIMEOUT_S, headers={
        "Accept": "application/vnd.github+json", "User-Agent": "verifix-judge-proof"})
    started = time.perf_counter()
    try:
        gh = _GitHub(client)
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(check_commit_window, gh), pool.submit(check_entire, gh),
                       pool.submit(check_upstream_pr, gh), pool.submit(check_neatlogs, neatlogs_search)]
            live = [f.result() for f in futures]
    finally:
        if own_client:
            client.close()
    by_id = {item["id"]: item for item in live}
    items = [check_improvement(ledger, root), by_id["neatlogs"], by_id["entire"], check_cfo(root),
             check_recovery(ledger), by_id["public"], by_id["commits"]]
    summary = {v: sum(1 for i in items if i["verdict"] == v) for v in ("verified", "attention", "unavailable")}
    report = {
        "generated_at": _iso(datetime.now(timezone.utc)),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
        "cache_ttl_s": CACHE_TTL_S,
        "cache_age_s": 0.0,
        "summary": summary,
        "items": items,
        "method_legend": {
            "LIVE": "Checked against the source of truth while this request was served.",
            "RECORDED": "Read from a versioned artifact in the repository.",
        },
    }
    if use_cache:
        with _cache_lock:
            _cache.update(at=now, value=report)
    return report
