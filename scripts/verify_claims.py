"""Recompute every published experiment figure from raw run records and check the docs quote them exactly.

    python3 scripts/verify_claims.py          # exit 1 on any mismatch

Checks:
1. The stored summaries in benchmarks/ablation_*.json equal a recomputation from their records.
2. Every claim string rendered from the recomputed numbers appears verbatim in the file that makes it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from verifix.ablation import summarize  # noqa: E402


def pct_fewer(r: float) -> int:
    return round((1 - r) * 100)


def claims(main: dict, fault: dict) -> list[tuple[str, str]]:
    s, f = summarize(main["records"]), summarize(fault["records"])
    a, vb, vt = s["arms"], s["comparisons"]["graph_guarded_vs_baseline_naive"], s["comparisons"]["graph_guarded_vs_target_only"]
    fa = f["arms"]
    g, b, t = a["graph_guarded"], a["baseline_naive"], a["target_only"]
    lo, hi = vb["token_ratio_ci95_cases"]
    plo, phi = vb["token_ratio_ci95_pairs"]
    n = len(main["records"])
    ev = "docs/EVALUATION.md"
    tok = lambda x: f"{round(x):,}"  # noqa: E731
    out = [
        (ev, f"## Results ({n} runs"),
        (ev, f"| `target_only` | {t['judge_passed']}/{t['runs']} | {t['shipped_regressions']} | {tok(t['mean_total_tokens'])} |"),
        (ev, f"| `baseline_naive` | {b['judge_passed']}/{b['runs']} | {b['shipped_regressions']} | {tok(b['mean_total_tokens'])} |"),
        (ev, f"| `graph_guarded` | {g['judge_passed']}/{g['runs']} | {g['shipped_regressions']} | {tok(g['mean_total_tokens'])} |"),
        (ev, f"Token ratio: {vb['token_ratio_geo_mean']:.3f}, i.e. {pct_fewer(vb['token_ratio_geo_mean'])}% fewer tokens "
             f"(95% CI by case {pct_fewer(hi)}–{pct_fewer(lo)}%; by pair {pct_fewer(phi)}–{pct_fewer(plo)}%)."),
        (ev, f"cheaper in {vb['graph_fewer_tokens_pairs']} of {vb['pairs']} pairs (sign test p = {vb['token_sign_test_p']:.5f})"),
        (ev, f"in all {vb['cases_graph_cheaper']} cases" if vb["cases_graph_cheaper"] == vb["cases"] else "MISMATCH: not all cases cheaper"),
        (ev, f"costs {round((vt['token_ratio_geo_mean'] - 1) * 100)}% more tokens (ratio {vt['token_ratio_geo_mean']:.3f}; "
             f"95% CI by case {vt['token_ratio_ci95_cases'][0]:.3f}–{vt['token_ratio_ci95_cases'][1]:.3f})"),
        (ev, f"more expensive in {vt['graph_more_tokens_pairs']} of {vt['pairs']} pairs (p = {vt['token_sign_test_p']:.3f})"),
        (ev, f"| `target_only` | Accepted the bad patch {fa['target_only']['shipped_regressions']}/{fa['target_only']['runs']} | "
             f"Failed {fa['target_only']['runs'] - fa['target_only']['judge_passed']}/{fa['target_only']['runs']}"),
        (ev, f"| `baseline_naive` | Rolled back, then fixed {fa['baseline_naive']['judge_passed']}/{fa['baseline_naive']['runs']} | "
             f"Passed {fa['baseline_naive']['judge_passed']}/{fa['baseline_naive']['runs']} | {tok(fa['baseline_naive']['mean_total_tokens'])} |"),
        (ev, f"| `graph_guarded` | Rolled back, then fixed {fa['graph_guarded']['judge_passed']}/{fa['graph_guarded']['runs']} | "
             f"Passed {fa['graph_guarded']['judge_passed']}/{fa['graph_guarded']['runs']} | {tok(fa['graph_guarded']['mean_total_tokens'])} |"),
        ("README.md", f"{pct_fewer(vb['token_ratio_geo_mean'])}% fewer tokens"),
        ("README.md", f"{tok(g['mean_total_tokens'])} vs {tok(b['mean_total_tokens'])}"),
        ("README.md", f"{pct_fewer(hi)}–{pct_fewer(lo)}%"),
        ("README.md", f"{g['judge_passed']}/{g['runs']}"),
        ("README.md", f"{round((vt['token_ratio_geo_mean'] - 1) * 100)}% more"),
        ("README.md", f"shipped it {fa['target_only']['shipped_regressions']}/{fa['target_only']['runs']}"),
    ]
    restated = (f"{pct_fewer(vb['token_ratio_geo_mean'])}% fewer tokens than whole-repository context "
                f"(95% CI by case {pct_fewer(hi)}{{dash}}{pct_fewer(lo)}%)")
    for rel in ("BUSINESS_PLAN.md", "docs/TECHNICAL_REFERENCE.md"):
        out.append((rel, restated.format(dash="–") + f" and {round((vt['token_ratio_geo_mean'] - 1) * 100)}% more"))
    out.append(("src/verifix/neatlogs_mcp_client.py", restated.format(dash="-")))
    out.append(("hackathon.md", f"{pct_fewer(vb['token_ratio_geo_mean'])}% fewer tokens than whole-repo context"))
    words = {58: "fifty-eight", 60: "sixty", 61: "sixty-one", 62: "sixty-two", 63: "sixty-three", 64: "sixty-four"}
    spoken = words.get(pct_fewer(vb["token_ratio_geo_mean"]), "UNMAPPED")
    out.append(("video/v2/narration.json", f"Entire Graph context used {spoken} percent fewer tokens than reading the whole repository"))
    out.append(("video/v2/make_cards.py", f"Entire Graph context: {pct_fewer(vb['token_ratio_geo_mean'])}% fewer tokens than the whole repo "
                                         f"(95% CI {pct_fewer(hi)}&ndash;{pct_fewer(lo)}%)"))
    for case, ratio in vb["token_ratio_by_case"].items():
        out.append((ev, f"| {ratio:.3f} |"))
    return out


def main() -> int:
    failures: list[str] = []
    data = {}
    for name in ("ablation_experiment.json", "ablation_fault_injection.json"):
        doc = json.loads((ROOT / "benchmarks" / name).read_text(encoding="utf-8"))
        if summarize(doc["records"]) != doc.get("summary"):
            failures.append(f"{name}: stored summary differs from recomputation")
        data[name] = doc
    checked = 0
    for rel, text in claims(data["ablation_experiment.json"], data["ablation_fault_injection.json"]):
        checked += 1
        body = (ROOT / rel).read_text(encoding="utf-8")
        if text not in body:
            failures.append(f"{rel}: missing or stale claim: {text}")
    for f in failures:
        print("FAIL", f)
    print(f"{checked} claims checked, {len(failures)} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
