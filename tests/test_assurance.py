"""Patch-assurance engine: every blocking gate is exercised by a planted defect on a real case."""

from __future__ import annotations

import random
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from verifix.assurance import dynamic_gates as dg  # noqa: E402
from verifix.assurance import static_gates as sg  # noqa: E402
from verifix.assurance.engine import run_patch_assurance, summarize  # noqa: E402
from verifix.assurance.mutation import generate_mutants  # noqa: E402
from verifix.test_runner import SandboxedTestRunner  # noqa: E402

CASE = ROOT / "benchmarks" / "repos" / "case_01_ledger_rounding"
SPEC = ROOT / "benchmarks" / "assurance_specs" / "case_01_ledger_rounding.py"
TARGET = "ledger/fees.py"
TESTS = ["tests/test_fees.py", "tests/test_settlement.py"]

REFERENCE_FIX = '''"""Fee calculation engine for tiered merchant processing."""

from decimal import Decimal, ROUND_HALF_EVEN

from ledger.money import validate_cents


def calculate_tiered_fee(amount_cents: int, tier_bps: int, min_fee_cents: int = 50) -> int:
    """Calculate the processing fee in integer cents for a transaction."""
    validate_cents(amount_cents)
    if amount_cents == 0:
        return 0
    raw_fee = int((Decimal(amount_cents) * Decimal(tier_bps) / Decimal(10000)).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))
    return max(raw_fee, min_fee_cents)


def calculate_split_fees(total_amount_cents: int, splits_cents: list[int], tier_bps: int) -> dict:
    """Calculate fees across split sub-merchants and reconcile any rounding delta."""
    validate_cents(total_amount_cents)
    if sum(splits_cents) != total_amount_cents:
        raise ValueError("Sum of splits_cents must equal total_amount_cents")

    total_expected_fee = calculate_tiered_fee(total_amount_cents, tier_bps, min_fee_cents=0)
    allocated_fees = [calculate_tiered_fee(part, tier_bps, min_fee_cents=0) for part in splits_cents]
    residual = total_expected_fee - sum(allocated_fees)
    if residual and allocated_fees:
        largest = max(range(len(splits_cents)), key=lambda i: (splits_cents[i], i))
        allocated_fees[largest] += residual
    return {
        "total_fee_cents": sum(allocated_fees),
        "allocated_fees_cents": allocated_fees,
    }
'''


def make_worktree(tmp_path: Path, fees_source: str | None = None) -> Path:
    wt = tmp_path / "wt"
    shutil.copytree(CASE, wt, ignore=shutil.ignore_patterns("__pycache__"))
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base"]):
        subprocess.run(cmd, cwd=wt, check=True, capture_output=True)
    if fees_source is not None:
        (wt / TARGET).write_text(fees_source, encoding="utf-8")
    return wt


def assure(wt: Path, **kw):
    kw.setdefault("mutation", False)
    kw.setdefault("minimality", False)
    kw.setdefault("fuzz_inputs", 120)
    return run_patch_assurance(wt, TARGET, TESTS, SandboxedTestRunner, spec_file=SPEC, **kw)


def gate(report, name):
    return next(g for g in report["gates"] if g["gate"] == name)


# ── end-to-end verdicts ──────────────────────────────────────────────────────────────────────
def test_reference_fix_passes_every_gate_and_grades_strong(tmp_path):
    rep = assure(make_worktree(tmp_path, REFERENCE_FIX), mutation=True, minimality=True)
    assert rep["verdict"] == "PASSED", summarize(rep)
    statuses = {g["gate"]: g["status"] for g in rep["gates"]}
    for g in ("scope", "api", "sast", "secrets", "symbols", "differential", "contracts", "determinism", "flaky", "relations"):
        assert statuses[g] == "pass", (g, statuses)
    assert gate(rep, "relations")["metrics"]["relations"] and all(r["status"] == "pass" for r in gate(rep, "relations")["metrics"]["relations"])
    assert gate(rep, "mutation")["metrics"]["mutants_run"] >= 10
    assert rep["strength"]["grade"] in {"strong", "moderate"}


def test_empty_patch_is_blocked(tmp_path):
    rep = assure(make_worktree(tmp_path))
    assert rep["verdict"] == "BLOCKED" and "scope" in rep["blocking_gates"]
    assert gate(rep, "scope")["findings"][0]["rule"] == "EMPTY_PATCH"


def test_test_tampering_is_blocked(tmp_path):
    wt = make_worktree(tmp_path, REFERENCE_FIX)
    (wt / "tests" / "test_fees.py").write_text("def test_nothing():\n    assert True\n", encoding="utf-8")
    rep = assure(wt)
    assert rep["verdict"] == "BLOCKED"
    assert any(f["rule"] == "TEST_TAMPERING" for f in gate(rep, "scope")["findings"])


def test_out_of_scope_file_is_blocked(tmp_path):
    wt = make_worktree(tmp_path, REFERENCE_FIX)
    (wt / "ledger" / "money.py").write_text((wt / "ledger" / "money.py").read_text() + "\nX = 1\n", encoding="utf-8")
    rep = assure(wt)
    assert any(f["rule"] == "OUT_OF_SCOPE_FILE" for f in gate(rep, "scope")["findings"])


def test_caller_trap_default_change_is_blocked_by_api_gate_and_declared_contract(tmp_path):
    rep = assure(make_worktree(tmp_path, REFERENCE_FIX.replace("min_fee_cents: int = 50", "min_fee_cents: int = 500")))
    assert rep["verdict"] == "BLOCKED"
    api = gate(rep, "api")
    assert api["status"] == "fail" and api["blocking"]                 # callers omit the argument -> breaking
    msg = " ".join(f["message"] for f in api["findings"])
    assert "default of 'min_fee_cents' changed 50 -> 500" in msg and "rely on the old default" in msg
    assert "ledger/settlement.py" in msg or "ledger/invoicing.py" in msg
    # a blocking static gate short-circuits the (slower) dynamic gates
    assert not any(g["gate"] in ("differential", "relations", "mutation") for g in rep["gates"])


def test_removed_parameter_is_breaking(tmp_path):
    src = REFERENCE_FIX.replace("tier_bps: int, min_fee_cents: int = 50) -> int:", "tier_bps: int) -> int:\n    min_fee_cents = 50")
    rep = assure(make_worktree(tmp_path, src))
    assert "api" in rep["blocking_gates"]
    assert gate(rep, "api")["metrics"]["breaking"] >= 1


def test_new_crash_found_by_differential_fuzzing_and_shrunk(tmp_path):
    src = REFERENCE_FIX.replace("    return max(raw_fee, min_fee_cents)",
                                "    scale = 10000 // tier_bps\n    return max(raw_fee, min_fee_cents) if scale else 0")
    rep = assure(make_worktree(tmp_path, src))
    d = gate(rep, "differential")
    assert d["status"] == "fail" and d["blocking"]
    assert d["findings"][0]["rule"] == "NEW_CRASH" and "ZeroDivisionError" in d["findings"][0]["message"]
    assert '"args": [' in d["findings"][0]["snippet"]                    # a concrete, replayable counterexample


def test_shrinker_reaches_small_counterexample():
    best = {"args": [987654, 0, 50]}
    cands = dg._shrink_candidates(best)
    assert {"args": [0, 0, 50], "kwargs": {}} in cands
    assert min(dg._size(c) for c in cands) < dg._size(best)


def test_nondeterminism_is_blocked(tmp_path):
    src = REFERENCE_FIX.replace('    return max(raw_fee, min_fee_cents)',
                                '    return max(raw_fee, min_fee_cents) + (hash("vfx") % 2 if amount_cents == 777 else 0)')
    src = src.replace("        return 0\n", "        return 0\n    if amount_cents == 777:\n        return hash(str(tier_bps)) % 3\n", 1)
    rep = assure(make_worktree(tmp_path, src), fuzz_inputs=400)
    det = gate(rep, "determinism")
    assert det["status"] == "fail", det["summary"]


def test_return_contract_violation_is_blocked(tmp_path):
    src = REFERENCE_FIX.replace("    return max(raw_fee, min_fee_cents)", "    return float(max(raw_fee, min_fee_cents))")
    rep = assure(make_worktree(tmp_path, src))
    assert gate(rep, "contracts")["status"] == "fail"
    assert "contracts" in rep["blocking_gates"]


def test_security_regressions_are_blocked(tmp_path):
    src = REFERENCE_FIX.replace("from ledger.money import validate_cents",
                                "from ledger.money import validate_cents\nimport subprocess\nAPI_TOKEN = \"ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8\"")
    src = src.replace("    validate_cents(amount_cents)\n    if amount_cents == 0:",
                      "    validate_cents(amount_cents)\n    eval(str(tier_bps))\n    if amount_cents == 0:", 1)
    rep = assure(make_worktree(tmp_path, src))
    rules = {f["rule"] for f in gate(rep, "sast")["findings"]}
    assert {"PY-EVAL", "PY-PROCESS-IMPORT", "PY-HARDCODED-SECRET"} <= rules
    assert gate(rep, "secrets")["status"] == "fail"
    assert {"sast", "secrets"} <= set(rep["blocking_gates"])


def test_hallucinated_import_and_symbol_are_blocked(tmp_path):
    src = REFERENCE_FIX.replace("from decimal import Decimal, ROUND_HALF_EVEN",
                                "from decimal import Decimal, ROUND_HALF_EVEN\nimport jsonn\nfrom ledger.money import round_cents_bankers")
    src = src.replace("    return max(raw_fee, min_fee_cents)", "    return max(raw_fee, min_fee_cents, minimum_fee_floor)")
    rep = assure(make_worktree(tmp_path, src))
    rules = [f["rule"] for f in gate(rep, "symbols")["findings"]]
    assert "UNRESOLVABLE_IMPORT" in rules and "PHANTOM_SYMBOL" in rules and "UNDEFINED_NAME" in rules
    assert "closest known module 'json'" in " ".join(f["message"] for f in gate(rep, "symbols")["findings"])


def test_preexisting_findings_do_not_block(tmp_path):
    base = (CASE / TARGET).read_text()
    assert sg.gate_sast(base + "\nimport subprocess\n", base + "\nimport subprocess\n").status == "pass"


# ── algorithm unit tests against published reference values ──────────────────────────────────
def test_cognitive_complexity_matches_sonar_paper_examples():
    sum_of_primes = '''
def sum_of_primes(maximum):
    total = 0
    for i in range(1, maximum + 1):
        for j in range(2, i):
            if i % j == 0:
                break
        else:
            total += i
    return total
'''
    get_words = '''
def get_words(number):
    if number == 1:
        return "one"
    elif number == 2:
        return "a couple"
    elif number == 3:
        return "a few"
    else:
        return "lots"
'''
    # SonarSource white paper: sumOfPrimes = 7 (Java uses labelled continue; Python for-else adds no increment here),
    # getWords (switch) = 1; the if/elif chain form scores 1 + 1 + 1 + 1 = 4.
    m = sg.function_metrics(sum_of_primes)["sum_of_primes"]
    assert m["cognitive"] == 6 and m["cyclomatic"] == 4
    assert sg.function_metrics(get_words)["get_words"]["cognitive"] == 4


def test_mann_whitney_detects_shift_and_not_noise():
    rng = random.Random(3)
    a = [rng.gauss(100, 5) for _ in range(60)]
    assert dg.mann_whitney_u(a, [x + 20 for x in a]) < 1e-10
    assert dg.mann_whitney_u(a, [rng.gauss(100, 5) for _ in range(60)]) > 0.01


def test_ddmin_finds_one_minimal_subset():
    items = list(range(10))
    minimal, calls, complete = dg.ddmin(items, lambda s: 3 in s and 7 in s)
    assert sorted(minimal) == [3, 7] and complete and calls < 40


def test_tce_drops_bytecode_identical_mutants():
    src = "def f(x):\n    y = x * 1\n    return y + 0\n"
    mutants, stats = generate_mutants(src, {2, 3})
    sources = [m.source for m in mutants]
    assert len(sources) == len(set(sources))
    assert stats["sites"] == len(mutants) + stats["tce_equivalent"] + stats["duplicates"] + stats["invalid"] + stats["sampled_out"]


def test_default_change_without_dependent_callers_stays_a_warning(tmp_path):
    (tmp_path / "m.py").write_text("def f(a, b=1):\n    return a + b\n", encoding="utf-8")
    (tmp_path / "use.py").write_text("from m import f\nf(1, 2)\nf(a=1, b=3)\n", encoding="utf-8")
    g = sg.gate_api("def f(a, b=1):\n    return a + b\n", "def f(a, b=2):\n    return a + b\n", tmp_path, "m.py")
    assert g.status == "warn" and not g.blocking
    (tmp_path / "use2.py").write_text("from m import f\nf(5)\n", encoding="utf-8")
    g = sg.gate_api("def f(a, b=1):\n    return a + b\n", "def f(a, b=2):\n    return a + b\n", tmp_path, "m.py")
    assert g.blocking and "use2.py:2" in g.findings[0]["message"]


def test_api_classification_rules():
    old = sg.public_api("def f(a, b, c=1):\n    pass\n")["f"]
    assert ("compatible", "new optional parameter 'd'") in sg.classify_api_change(old, sg.public_api("def f(a, b, c=1, d=2):\n    pass\n")["f"])
    assert any(s == "breaking" for s, _ in sg.classify_api_change(old, sg.public_api("def f(b, a, c=1):\n    pass\n")["f"]))
    assert any(s == "breaking" for s, _ in sg.classify_api_change(old, sg.public_api("def f(a, b, c):\n    pass\n")["f"]))
    assert any(s == "breaking" for s, _ in sg.classify_api_change(old, sg.public_api("def f(a, b, c=1, *, k):\n    pass\n")["f"]))


def test_secret_scanner_patterns_and_entropy():
    hits = sg.scan_text_for_secrets('aws = "AKIA' + 'ABCDEFGHIJKLMNOP"\npassword = "Zx9!qL2#vB7@nM4$wR8"\nname = "hello world example"')
    rules = {h.rule for h in hits}
    assert "SECRET-AWS_ACCESS_KEY_ID" in rules and "SECRET-HIGH-ENTROPY-ASSIGNMENT" in rules
    assert all(h.line != 3 for h in hits)


def test_taint_flags_parameter_to_sink_but_not_sanitised():
    bad = "import os\ndef run(cmd):\n    full = 'ls ' + cmd\n    os.system(full)\n"
    ok = "import os\ndef run(n):\n    os.system('ls ' + str(int(n)))\n"
    assert any(f.rule == "TAINT-FLOW" for f in sg.taint_findings(__import__("ast").parse(bad), bad))
    assert not any(f.rule == "TAINT-FLOW" for f in sg.taint_findings(__import__("ast").parse(ok), ok))


def test_sbfl_ranks_the_faulty_line_first_on_case_01():
    res = dg.sbfl_rank(CASE, [TARGET], TESTS)
    top_lines = [r["line"] for r in res["ranking"][:3]]
    src = (CASE / TARGET).read_text().splitlines()
    faulty = next(i for i, line in enumerate(src, 1) if "raw_fee = int(amount_cents" in line)
    assert faulty in top_lines, res["ranking"][:5]
