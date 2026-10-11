"""Dynamic patch gates: everything that executes code runs in the sandbox via ``probe.py``."""

from __future__ import annotations

import ast
import concurrent.futures as cf
import difflib
import importlib.util
import json
import math
import os
import random
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from verifix.assurance.mutation import generate_mutants
from verifix.assurance.static_gates import (
    HIGH, LOW, MEDIUM, Finding, GateResult, changed_line_numbers, enclosing_functions,
)
from verifix.sandbox import limits_preexec, sandbox_env

PROBE = Path(__file__).with_name("probe.py")
MARK = "__VFX_RESULT__"
ROBUSTNESS_EXCEPTIONS = {"NameError", "UnboundLocalError", "AttributeError", "ZeroDivisionError", "IndexError",
                         "KeyError", "RecursionError", "Timeout", "NotImplementedError", "SystemError", "OverflowError"}


# ── probe plumbing ───────────────────────────────────────────────────────────────────────────
def run_probe(job: dict[str, Any], timeout: float = 60.0, hash_seed: str = "0") -> dict[str, Any]:
    env = sandbox_env([job["root"]], hash_seed=hash_seed)
    try:
        proc = subprocess.run([sys.executable, "-B", str(PROBE)], input=json.dumps(job), cwd=job["root"], env=env,
                              capture_output=True, text=True, timeout=timeout, preexec_fn=limits_preexec())
    except subprocess.TimeoutExpired:
        return {"probe_ok": False, "error": f"probe timed out after {timeout}s"}
    for line in reversed(proc.stdout.splitlines()):
        if line.startswith(MARK):
            return json.loads(line[len(MARK):])
    return {"probe_ok": False, "error": f"no probe result (exit {proc.returncode})", "stderr": proc.stderr[-800:]}


def copy_tree(src: Path, dst: Path) -> Path:
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".pytest_cache"))
    return dst


def module_name(rel_file: str) -> str:
    parts = rel_file[:-3].split("/")
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


# ── input generation (boundary-value analysis + seeded random) ───────────────────────────────
def _int_constants(src: str) -> set[int]:
    out: set[int] = set()
    try:
        for n in ast.walk(ast.parse(src)):
            if isinstance(n, ast.Constant) and isinstance(n.value, int) and not isinstance(n.value, bool) and abs(n.value) < 10 ** 9:
                out.add(n.value)
    except SyntaxError:
        return out
    return out


def _annotation_kind(ann: ast.expr | None) -> tuple[str, Any] | None:
    if ann is None:
        return None
    txt = ast.unparse(ann).replace(" ", "")
    simple = {"int": "int", "float": "float", "bool": "bool", "str": "str"}
    if txt in simple:
        return (simple[txt], None)
    for opt in (f"{k}|None" for k in simple):
        if txt == opt or txt == f"Optional[{opt.split('|')[0]}]":
            return ("optional", simple[opt.split("|")[0]])
    if txt in ("list[int]", "List[int]"):
        return ("list", "int")
    if txt in ("list[str]", "List[str]"):
        return ("list", "str")
    return None


def _gen_value(kind: tuple[str, Any], rng: random.Random, consts: list[int]) -> Any:
    k, sub = kind
    if k == "int":
        r = rng.random()
        if r < 0.45 and consts:
            c = rng.choice(consts)
            return c + rng.choice((-1, 0, 1))
        if r < 0.6:
            return rng.choice((0, 1, -1, 2, 10, 100, 10 ** 6, 2 ** 31 - 1))
        return rng.randint(-1000, 10 ** 6) if rng.random() < 0.8 else rng.randint(-10 ** 9, 10 ** 9)
    if k == "float":
        return rng.choice((0.0, -0.0, 1.0, 0.5, 1e-9, 1e9, rng.uniform(-1e6, 1e6), rng.uniform(0, 1)))
    if k == "bool":
        return rng.random() < 0.5
    if k == "str":
        pool = ["", "0", "1", "-1", "abc", " ", "2026-10-11T08:00:00Z", "1760169600", "é✓", "a" * 64, "None", "{}", "x.y"]
        return rng.choice(pool) if rng.random() < 0.7 else "".join(rng.choice("abc019-_:.TZ ") for _ in range(rng.randint(0, 20)))
    if k == "optional":
        return None if rng.random() < 0.15 else _gen_value((sub, None), rng, consts)
    if k == "list":
        return [_gen_value((sub, None), rng, consts) for _ in range(rng.randint(0, 6))]
    raise ValueError(k)


def generic_inputs(src: str, qualname: str, n: int, seed: int) -> tuple[list[dict[str, Any]] | None, str]:
    """Inputs for a module-level function from its annotations, or (None, reason)."""
    tree = ast.parse(src)
    if "." in qualname:
        return None, "method: needs a declared driver"
    fn = next((x for x in tree.body if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef)) and x.name == qualname), None)
    if fn is None:
        return None, "not a module-level function"
    if isinstance(fn, ast.AsyncFunctionDef):
        return None, "async function"
    a = fn.args
    params = a.posonlyargs + a.args
    if a.kwonlyargs or a.vararg or a.kwarg:
        return None, "keyword-only or variadic parameters"
    kinds = []
    for p in params:
        k = _annotation_kind(p.annotation)
        if k is None:
            return None, f"parameter '{p.arg}' has no supported annotation"
        kinds.append(k)
    n_required = len(params) - len(a.defaults)
    consts = sorted(_int_constants(src))
    rng = random.Random(f"{seed}:{qualname}")
    out = []
    for _ in range(n):
        upto = len(params) if rng.random() < 0.7 else rng.randint(n_required, len(params))
        out.append({"args": [_gen_value(kinds[i], rng, consts) for i in range(upto)], "kwargs": {}})
    return out, "annotations"


def _shrink_candidates(inp: dict[str, Any]) -> list[dict[str, Any]]:
    cands = []
    args = inp.get("args", [])
    for i, v in enumerate(args):
        repl: list[Any] = []
        if isinstance(v, bool):
            pass
        elif isinstance(v, int) and v != 0:
            repl = [0, v // 2, v - (1 if v > 0 else -1)]
        elif isinstance(v, float) and v != 0:
            repl = [0.0, round(v / 2, 6), float(int(v))]
        elif isinstance(v, str) and v:
            repl = ["", v[: len(v) // 2], v[1:]]
        elif isinstance(v, list) and v:
            repl = [[], v[: len(v) // 2], v[1:]]
        for r in repl:
            if r != v:
                cands.append({"args": args[:i] + [r] + args[i + 1:], "kwargs": inp.get("kwargs", {})})
    return cands


def _size(inp: dict[str, Any]) -> float:
    total = 0.0
    for v in inp.get("args", []):
        if isinstance(v, bool):
            total += 1
        elif isinstance(v, (int, float)):
            total += math.log2(abs(v) + 1)
        elif isinstance(v, (str, list)):
            total += len(v)
    return total


def mann_whitney_u(x: list[float], y: list[float]) -> float:
    """Two-sided p-value, normal approximation with tie correction (fine for n >= 20)."""
    n1, n2 = len(x), len(y)
    if n1 < 3 or n2 < 3:
        return 1.0
    allv = sorted([(v, 0) for v in x] + [(v, 1) for v in y])
    ranks = [0.0] * len(allv)
    i = 0
    ties = 0.0
    while i < len(allv):
        j = i
        while j + 1 < len(allv) and allv[j + 1][0] == allv[i][0]:
            j += 1
        r = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[k] = r
        t = j - i + 1
        ties += t ** 3 - t
        i = j + 1
    r1 = sum(r for r, (_v, g) in zip(ranks, allv) if g == 0)
    u = r1 - n1 * (n1 + 1) / 2
    mu = n1 * n2 / 2
    n = n1 + n2
    sigma = math.sqrt(n1 * n2 / 12 * ((n + 1) - ties / (n * (n - 1))))
    if sigma == 0:
        return 1.0
    z = abs(u - mu) / sigma
    return math.erfc(z / math.sqrt(2))


# ── differential fuzzing, contracts, determinism, performance ────────────────────────────────
def gate_differential(baseline_root: Path, patched_root: Path, target_file: str, functions: list[str],
                      spec: Any = None, n_inputs: int = 300, seed: int = 20261011) -> list[GateResult]:
    t0 = time.perf_counter()
    src = (patched_root / target_file).read_text(encoding="utf-8")
    mod = module_name(target_file)
    per_fn: list[dict[str, Any]] = []
    new_crashes: list[Finding] = []
    contract: list[Finding] = []
    nondet: list[Finding] = []
    perf_rows: list[dict[str, Any]] = []
    skipped: list[str] = []
    total_inputs = 0
    conform_checked = 0
    drivers_run: dict[str, str] = {}
    for q in functions:
        driver_src = None
        gen = getattr(spec, "INPUT_GENERATORS", {}).get(q) if spec else None
        shared = getattr(spec, "DRIVERS", {}).get(q) if spec else None
        if shared is not None and shared in drivers_run:
            skipped.append(f"{q} (exercised by the shared driver of {drivers_run[shared]})")
            continue
        if shared is not None:
            drivers_run[shared] = q
        if gen is not None:
            rng = random.Random(f"{seed}:{q}")
            inputs = [gen(rng) for _ in range(n_inputs)]
            driver_src = getattr(spec, "DRIVERS", {}).get(q)
            source = "declared generator"
        else:
            inputs, source = generic_inputs(src, q, n_inputs, seed)
            if inputs is None:
                skipped.append(f"{q} ({source})")
                continue
        job = {"mode": "call", "module": mod, "qualname": q, "inputs": inputs, "repeat": 3, "timeout_per_call": 1.0}
        if driver_src:
            job["driver_source"] = driver_src
        base = run_probe({**job, "root": str(baseline_root), "determinism_pass": False}, timeout=120)
        pat = run_probe({**job, "root": str(patched_root)}, timeout=120)
        pat_seed = run_probe({**job, "root": str(patched_root), "determinism_pass": False}, timeout=120, hash_seed="1")
        if not (base.get("probe_ok") and pat.get("probe_ok") and pat_seed.get("probe_ok")):
            skipped.append(f"{q} (probe error: {base.get('error') or pat.get('error') or pat_seed.get('error')})")
            continue
        total_inputs += len(inputs)
        same = changed = crash_new = crash_fixed = 0
        crash_examples: list[tuple[dict, dict]] = []
        for i, (b, p) in enumerate(zip(base["results"], pat["results"])):
            if p.get("ok") and "conforms" in p:
                conform_checked += 1
            if b.get("ok") and p.get("ok"):
                if b["value"] == p["value"]:
                    same += 1
                else:
                    changed += 1
                if p.get("conforms") is False and b.get("conforms") is not False:
                    contract.append(Finding("RETURN_CONTRACT", HIGH, f"{q} returns {p['type']}, violating its annotation {pat.get('return_hint')}",
                                            snippet=json.dumps(inputs[i])[:200]))
                if b.get("ns") and p.get("ns"):
                    perf_rows.append({"fn": q, "base": b["ns"], "patched": p["ns"]})
            elif b.get("ok") and not p.get("ok"):
                crash_new += 1
                crash_examples.append((inputs[i], p))
            elif not b.get("ok") and p.get("ok"):
                crash_fixed += 1
            else:
                same += 1 if b.get("exc") == p.get("exc") else 0
                changed += 0 if b.get("exc") == p.get("exc") else 1
        flips = [i for i, ok in enumerate(pat.get("same_on_second_pass") or []) if not ok]
        seed_flips = [i for i, (a, c) in enumerate(zip(pat["results"], pat_seed["results"]))
                      if (a.get("ok"), a.get("value"), a.get("exc")) != (c.get("ok"), c.get("value"), c.get("exc"))]
        if flips or seed_flips:
            idx = (flips or seed_flips)[0]
            nondet.append(Finding("NONDETERMINISTIC_OUTPUT", HIGH,
                                  f"{q}: same input gave different results ({len(flips)} on repeat, {len(seed_flips)} under another hash seed)",
                                  snippet=json.dumps(inputs[idx])[:200]))
        # shrink the first robustness crash to a minimal counterexample
        for inp, p in crash_examples:
            if p.get("exc") not in ROBUSTNESS_EXCEPTIONS:
                continue
            minimal = inp
            if gen is None:
                minimal = _shrink(baseline_root, patched_root, job, inp, p["exc"])
            new_crashes.append(Finding("NEW_CRASH", HIGH, f"{q} now raises {p['exc']} where the original returned a value",
                                       snippet=json.dumps(minimal)[:240]))
            break
        validation = [p.get("exc") for _i, p in crash_examples if p.get("exc") not in ROBUSTNESS_EXCEPTIONS]
        per_fn.append({"function": q, "inputs": len(inputs), "input_source": source, "same": same, "changed": changed,
                       "new_exceptions": crash_new, "fixed_exceptions": crash_fixed,
                       "new_validation_exceptions": sorted(set(validation)),
                       "behaviour_change_ratio": round(changed / max(1, len(inputs)), 4)})
    dur = round((time.perf_counter() - t0) * 1000, 1)
    tested = [r["function"] for r in per_fn]
    na = not per_fn
    diff = GateResult(
        "differential", "Differential fuzzing: original vs patched",
        ["differential-testing", "fuzz-testing", "property-based-testing", "counterexample-shrinking"],
        "skipped" if na else ("fail" if new_crashes else "pass"), bool(new_crashes),
        ("Not applicable: " + "; ".join(skipped)) if na else
        (f"{total_inputs} generated inputs over {len(tested)} function(s): {sum(r['new_exceptions'] for r in per_fn)} new exception(s), "
         f"{sum(r['fixed_exceptions'] for r in per_fn)} fixed, behaviour changed on {sum(r['changed'] for r in per_fn)}."),
        {"functions": per_fn, "skipped": skipped, "inputs_total": total_inputs, "seed": seed}, [asdict(f) for f in new_crashes], dur)
    no_hint = conform_checked == 0
    con = GateResult("contracts", "Runtime type contracts", ["design-by-contract", "runtime-verification"],
                     "skipped" if (na or no_hint) else ("fail" if contract else "pass"), bool(contract),
                     "Not applicable." if na else ("No return annotations to check (stateful driver)." if no_hint else
                                                   (f"{len(contract)} return-annotation violation(s) in {conform_checked} checked calls." if contract else
                                                    f"All {conform_checked} returned values conformed to their declared return types.")),
                     {"calls_checked": conform_checked}, [asdict(f) for f in contract[:5]])
    det = GateResult("determinism", "Nondeterminism audit", ["nondeterminism-auditing", "test-isolation"],
                     "skipped" if na else ("fail" if nondet else "pass"), bool(nondet),
                     "Not applicable." if na else (nondet[0].message if nondet else
                                                   f"Identical outputs on a reversed-order rerun and under a different PYTHONHASHSEED ({total_inputs} inputs)."),
                     {"inputs": total_inputs}, [asdict(f) for f in nondet])
    perf = gate_performance(perf_rows)
    return [diff, con, det, perf]


def _shrink(baseline_root: Path, patched_root: Path, job: dict, inp: dict, exc: str, rounds: int = 8) -> dict:
    best = inp
    for _ in range(rounds):
        cands = sorted(_shrink_candidates(best), key=_size)
        if not cands:
            break
        b = run_probe({**job, "root": str(baseline_root), "inputs": cands, "repeat": 1, "determinism_pass": False}, timeout=60)
        p = run_probe({**job, "root": str(patched_root), "inputs": cands, "repeat": 1, "determinism_pass": False}, timeout=60)
        if not (b.get("probe_ok") and p.get("probe_ok")):
            break
        hit = next((c for c, rb, rp in zip(cands, b["results"], p["results"])
                    if rb.get("ok") and not rp.get("ok") and rp.get("exc") == exc), None)
        if hit is None or _size(hit) >= _size(best):
            break
        best = hit
    return best


def gate_performance(rows: list[dict[str, Any]]) -> GateResult:
    if len(rows) < 20:
        return GateResult("performance", "Performance regression", ["performance-regression-detection", "continuous-benchmarking"],
                          "skipped", False, "Fewer than 20 comparable calls; no statistical comparison made.", {"samples": len(rows)})
    base = [r["base"] for r in rows]
    pat = [r["patched"] for r in rows]
    ratio = statistics.median(pat) / max(1, statistics.median(base))
    p = mann_whitney_u(base, pat)
    severe = ratio > 5 and p < 0.001 and statistics.median(pat) > 20_000
    slower = ratio > 1.5 and p < 0.01
    status = "fail" if severe else ("warn" if slower else "pass")
    f = [asdict(Finding("PERF_REGRESSION", HIGH if severe else MEDIUM, f"median call time ×{ratio:.2f} (Mann-Whitney p={p:.2g})"))] if status != "pass" else []
    return GateResult("performance", "Performance regression", ["performance-regression-detection", "continuous-benchmarking"],
                      status, severe,
                      f"Median call time ×{ratio:.2f} versus the original over {len(rows)} calls (Mann-Whitney U p={p:.2g}).",
                      {"samples": len(rows), "median_ratio": round(ratio, 3), "p_value": p,
                       "median_ns_original": statistics.median(base), "median_ns_patched": statistics.median(pat)}, f)


# ── coverage of changed lines + decision coverage ────────────────────────────────────────────
def gate_coverage(patched_root: Path, target_file: str, tests: list[str], changed: set[int],
                  block_below: float = 0.5, warn_below: float = 0.8) -> tuple[GateResult, dict[str, Any]]:
    t0 = time.perf_counter()
    res = run_probe({"mode": "tests", "root": str(patched_root), "source_file": target_file, "targets": tests}, timeout=120)
    if not res.get("probe_ok"):
        return GateResult("coverage", "Diff coverage and decision coverage", ["diff-patch-coverage", "branch-decision-coverage"],
                          "skipped", False, f"Coverage probe failed: {res.get('error')}", {}), res
    exe = set(res["executable_lines"])
    executed = set().union(*[set(t["lines"]) for t in res["tests"]]) if res["tests"] else set()
    changed_exe = sorted(changed & exe)
    covered = [ln for ln in changed_exe if ln in executed]
    ratio = len(covered) / len(changed_exe) if changed_exe else 1.0
    src = (patched_root / target_file).read_text(encoding="utf-8")
    fn_lines: set[int] = set()
    tree = ast.parse(src)
    for q in enclosing_functions(src, changed):
        node = _find_fn(tree, q)
        if node is not None:
            fn_lines.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
    observed: dict[str, set[bool]] = {}
    for t in res["tests"]:
        for k, v in t["decisions"].items():
            observed.setdefault(k, set()).update(v)
    decisions = {k: d for k, d in res["decision_points"].items() if d["line"] in fn_lines}
    outcomes_total = 2 * len(decisions)
    outcomes_seen = sum(len(observed.get(k, set())) for k in decisions)
    dec_ratio = outcomes_seen / outcomes_total if outcomes_total else None
    passed = all(t["passed"] for t in res["tests"])
    findings = []
    uncovered = [ln for ln in changed_exe if ln not in executed]
    if uncovered:
        findings.append(asdict(Finding("UNCOVERED_CHANGED_LINES", MEDIUM, f"changed lines never executed by the verifying tests: {uncovered[:12]}")))
    partial = [f"line {d['line']} ({d['kind']}): only {sorted(observed.get(k, set()))}" for k, d in decisions.items() if len(observed.get(k, set())) < 2]
    if partial:
        findings.append(asdict(Finding("PARTIAL_DECISIONS", LOW, "decisions not exercised both ways: " + "; ".join(partial[:6]))))
    blocking = ratio < block_below
    status = "fail" if blocking else ("warn" if ratio < warn_below or (dec_ratio is not None and dec_ratio < 1) else "pass")
    summary = (f"{len(covered)}/{len(changed_exe)} changed executable lines ran under the verifying tests ({ratio:.0%}); "
               + (f"decision coverage of changed functions {outcomes_seen}/{outcomes_total} outcomes ({dec_ratio:.0%})." if dec_ratio is not None
                  else "no decisions in changed functions."))
    metrics = {"changed_executable_lines": len(changed_exe), "covered_changed_lines": len(covered), "diff_coverage": round(ratio, 4),
               "decision_outcomes_total": outcomes_total, "decision_outcomes_seen": outcomes_seen,
               "decision_coverage": round(dec_ratio, 4) if dec_ratio is not None else None,
               "tests_run": len(res["tests"]), "tests_passed_in_probe": passed}
    return GateResult("coverage", "Diff coverage and decision coverage", ["diff-patch-coverage", "branch-decision-coverage"],
                      status, blocking, summary, metrics, findings, round((time.perf_counter() - t0) * 1000, 1)), res


def _find_fn(tree: ast.Module, qualname: str):
    node: Any = tree
    for part in qualname.split("."):
        node = next((c for c in ast.iter_child_nodes(node) if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and c.name == part), None)
        if node is None:
            return None
    return node


# ── mutation testing of the changed lines ────────────────────────────────────────────────────
def gate_mutation(patched_root: Path, target_file: str, tests: list[str], changed: set[int],
                  run_tests: Callable[[Path, list[str], float], dict], limit: int = 40,
                  budget_s: float = 45.0, workers: int | None = None) -> GateResult:
    t0 = time.perf_counter()
    path = patched_root / target_file
    src = path.read_text(encoding="utf-8")
    mutants, stats = generate_mutants(src, changed, filename=str(path), limit=limit)
    if not mutants:
        return GateResult("mutation", "Mutation testing of changed lines",
                          ["mutation-testing", "mutation-score-mutation-adequacy", "equivalent-mutant-problem"],
                          "skipped", False, "No mutable operations on the changed lines.", {"generation": stats})
    base = run_tests(patched_root, tests, 30.0)
    per_timeout = max(3.0, 10 * base.get("latency_ms", 300) / 1000)
    workers = workers or max(1, min(4, os.cpu_count() or 1))
    tmp = Path(tempfile.mkdtemp(prefix="vfx_mut_"))
    copies = [copy_tree(patched_root, tmp / f"w{i}") for i in range(workers)]
    results: list[dict[str, Any]] = []

    def work(args):
        idx, m = args
        root = copies[idx % workers]
        target = root / target_file
        if time.perf_counter() - t0 > budget_s:
            return {"id": m.mid, "status": "not_run"}
        target.write_text(m.source, encoding="utf-8")
        try:
            r = run_tests(root, tests, per_timeout)
        finally:
            target.write_text(src, encoding="utf-8")
        status = "killed" if not r["passed"] else "survived"
        if r.get("exit_code") == -1:
            status = "killed"  # timeout counts as detected (infinite loop)
        return {"id": m.mid, "operator": m.operator, "line": m.line, "description": m.description, "status": status}

    try:
        # one worker per copy: group mutants by copy so a copy is never shared concurrently
        groups = [[(i, m) for i, m in enumerate(mutants) if i % workers == w] for w in range(workers)]
        with cf.ThreadPoolExecutor(max_workers=workers) as pool:
            for out in pool.map(lambda g: [work(a) for a in g], groups):
                results.extend(out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    run = [r for r in results if r["status"] != "not_run"]
    killed = sum(r["status"] == "killed" for r in run)
    score = killed / len(run) if run else 0.0
    survivors = sorted([r for r in run if r["status"] == "survived"], key=lambda r: (r["line"], r["id"]))
    status = "pass" if score >= 0.8 else "warn"
    findings = [asdict(Finding("SURVIVING_MUTANT", LOW, f"line {r['line']} {r['operator']} ({r['description']}) survived; equivalence not excluded"))
                for r in survivors[:8]]
    by_op: dict[str, list[int]] = {}
    for r in run:
        by_op.setdefault(r["operator"], [0, 0])
        by_op[r["operator"]][1] += 1
        by_op[r["operator"]][0] += r["status"] == "killed"
    return GateResult("mutation", "Mutation testing of changed lines",
                      ["mutation-testing", "mutation-score-mutation-adequacy", "equivalent-mutant-problem"],
                      status, False,
                      f"The verifying tests killed {killed} of {len(run)} mutants of the changed lines (score {score:.0%}); "
                      f"{stats['tce_equivalent']} equivalent and {stats['duplicates']} duplicate mutant(s) excluded before running.",
                      {"mutants_run": len(run), "killed": killed, "survived": len(run) - killed, "score": round(score, 4),
                       "not_run_budget": len(results) - len(run), "generation": stats, "by_operator": by_op,
                       "survivors": survivors[:20], "workers": workers},
                      findings, round((time.perf_counter() - t0) * 1000, 1))


# ── flaky detection (rerun, reversed order, other hash seed) ─────────────────────────────────
def gate_flaky(patched_root: Path, tests: list[str], run_tests: Callable[..., dict]) -> GateResult:
    t0 = time.perf_counter()
    runs = [run_tests(patched_root, tests, 30.0), run_tests(patched_root, list(reversed(tests)), 30.0),
            run_tests(patched_root, tests, 30.0, "1")]
    outcomes = [r["passed"] for r in runs]
    flaky = len(set(outcomes)) > 1
    return GateResult("flaky", "Flaky-test check", ["flaky-test-detection-and-quarantine", "flaky-test-rate", "test-isolation"],
                      "fail" if flaky else "pass", flaky,
                      ("Verifying tests disagreed across reruns: " + ", ".join(f"{n}={'pass' if o else 'fail'}" for n, o in zip(["normal", "reversed", "hashseed=1"], outcomes)))
                      if flaky else "Verifying tests gave the same result on a plain rerun, in reversed order and under PYTHONHASHSEED=1.",
                      {"runs": 3, "outcomes": outcomes, "tests": tests}, [], round((time.perf_counter() - t0) * 1000, 1))


# ── delta debugging: smallest subset of the patch the tests require ──────────────────────────
def patch_chunks(original: str, patched: str) -> list[tuple[int, int, list[str]]]:
    a, b = original.splitlines(keepends=True), patched.splitlines(keepends=True)
    return [(i1, i2, b[j1:j2]) for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes() if tag != "equal"]


def apply_chunks(original: str, chunks: list[tuple[int, int, list[str]]]) -> str:
    a = original.splitlines(keepends=True)
    out, pos = [], 0
    for i1, i2, new in sorted(chunks, key=lambda c: c[0]):
        out.extend(a[pos:i1])
        out.extend(new)
        pos = i2
    out.extend(a[pos:])
    return "".join(out)


def ddmin(items: list[Any], test: Callable[[list[Any]], bool], budget_s: float = 20.0) -> tuple[list[Any], int, bool]:
    """Zeller & Hildebrandt ddmin: return a 1-minimal subset for which ``test`` holds."""
    t0, n = time.perf_counter(), 2
    cur = list(items)
    cache: dict[tuple[int, ...], bool] = {}
    raw_test = test

    def test(subset):  # memoised: identical subsets are never re-run
        key = tuple(sorted(items.index(x) for x in subset))
        if key not in cache:
            cache[key] = bool(raw_test(subset))
        return cache[key]
    while len(cur) >= 2:
        if time.perf_counter() - t0 > budget_s:
            return cur, len(cache), False
        size = math.ceil(len(cur) / n)
        subsets = [cur[i:i + size] for i in range(0, len(cur), size)]
        reduced = False
        for s in subsets:
            if test(s):
                cur, n, reduced = s, 2, True
                break
        if not reduced:
            for s in subsets:
                comp = [x for x in cur if x not in s]
                if comp and test(comp):
                    cur, n, reduced = comp, max(n - 1, 2), True
                    break
        if not reduced:
            if n >= len(cur):
                break
            n = min(len(cur), n * 2)
    return cur, len(cache), True


def gate_minimality(patched_root: Path, target_file: str, original: str, tests: list[str],
                    run_tests: Callable[..., dict], budget_s: float = 20.0) -> GateResult:
    t0 = time.perf_counter()
    patched = (patched_root / target_file).read_text(encoding="utf-8")
    chunks = patch_chunks(original, patched)
    terms = ["delta-debugging", "patch-overfitting-detection"]
    if len(chunks) <= 1:
        return GateResult("minimality", "Patch minimality (delta debugging)", terms, "pass", False,
                          f"{len(chunks)} change hunk; already minimal.", {"hunks": len(chunks), "necessary": len(chunks)})
    tmp = Path(tempfile.mkdtemp(prefix="vfx_dd_"))
    root = copy_tree(patched_root, tmp / "w")
    target = root / target_file

    def passes(subset) -> bool:
        cand = apply_chunks(original, subset)
        try:
            compile(cand, target_file, "exec")
        except SyntaxError:
            return False
        target.write_text(cand, encoding="utf-8")
        return bool(run_tests(root, tests, 20.0)["passed"])

    try:
        minimal, calls, complete = ddmin(chunks, passes, budget_s)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    extra = [c for c in chunks if c not in minimal]
    cosmetic = [c for c in extra if _is_cosmetic(original, minimal, c)]
    semantic = [c for c in extra if c not in cosmetic]
    findings = []
    if semantic:
        findings.append(asdict(Finding("UNTESTED_SEMANTIC_HUNKS", MEDIUM,
                                       f"{len(semantic)} code-changing hunk(s) are not required by the verifying tests: unnecessary edits or behaviour the tests do not check",
                                       snippet=" | ".join("".join(c[2]).strip()[:60] or "(deletion)" for c in semantic)[:240])))
    return GateResult("minimality", "Patch minimality (delta debugging)", terms, "warn" if semantic else "pass", False,
                      (f"The verifying tests need {len(minimal)} of {len(chunks)} change hunks ({calls} test runs); "
                       f"{len(cosmetic)} cosmetic (comments, docstrings, layout), {len(semantic)} untested code change(s)."
                       + ("" if complete else " Search stopped at the time budget; result may not be 1-minimal.")),
                      {"hunks": len(chunks), "necessary": len(minimal), "cosmetic": len(cosmetic), "untested_semantic": len(semantic),
                       "test_runs": calls, "complete": complete},
                      findings, round((time.perf_counter() - t0) * 1000, 1))


def _normalized_ast(src: str) -> str | None:
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                and isinstance(body[0].value.value, str):
            node.body = body[1:] or [ast.Pass()]
    return ast.dump(tree, annotate_fields=False)


def _is_cosmetic(original: str, base_subset: list, chunk) -> bool:
    """A hunk is cosmetic if adding it to the necessary subset leaves the docstring-free AST unchanged."""
    without = _normalized_ast(apply_chunks(original, base_subset))
    with_it = _normalized_ast(apply_chunks(original, base_subset + [chunk]))
    return without is not None and without == with_it


# ── spectrum-based fault localisation (Ochiai) on the unpatched code ─────────────────────────
def sbfl_rank(root: Path, source_files: list[str], tests: list[str], top: int = 10) -> dict[str, Any]:
    t0 = time.perf_counter()
    scored: list[dict[str, Any]] = []
    failing_total = None
    errors = []
    for rel in source_files:
        res = run_probe({"mode": "tests", "root": str(root), "source_file": rel, "targets": tests}, timeout=120)
        if not res.get("probe_ok"):
            errors.append(f"{rel}: {res.get('error')}")
            continue
        fails = [t for t in res["tests"] if not t["passed"]]
        passes = [t for t in res["tests"] if t["passed"]]
        failing_total = len(fails)
        if not fails:
            continue
        lines_src = (root / rel).read_text(encoding="utf-8").splitlines()
        defs = {n.lineno for n in ast.walk(ast.parse("\n".join(lines_src))) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom))}
        for ln in set(res["executable_lines"]) - defs:
            ef = sum(ln in t["lines"] for t in fails)
            ep = sum(ln in t["lines"] for t in passes)
            if ef == 0:
                continue
            ochiai = ef / math.sqrt(len(fails) * (ef + ep))
            scored.append({"file": rel, "line": ln, "ochiai": round(ochiai, 4), "ef": ef, "ep": ep,
                           "code": lines_src[ln - 1].strip()[:120] if ln - 1 < len(lines_src) else ""})
    scored.sort(key=lambda r: (-r["ochiai"], r["file"], r["line"]))
    return {"ranking": scored[:top], "lines_ranked": len(scored), "failing_tests": failing_total, "errors": errors,
            "duration_ms": round((time.perf_counter() - t0) * 1000, 1)}


def exam_score(ranking: list[dict[str, Any]], total_lines: int, faulty: set[tuple[str, int]]) -> float | None:
    """EXAM: fraction of lines inspected before the first faulty line (ties: average rank)."""
    for i, r in enumerate(ranking):
        if (r["file"], r["line"]) in faulty:
            tied = [j for j, x in enumerate(ranking) if x["ochiai"] == r["ochiai"]]
            avg_rank = (tied[0] + tied[-1]) / 2 + 1
            return round(avg_rank / max(1, total_lines), 4)
    return None
