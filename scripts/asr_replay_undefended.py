#!/usr/bin/env python3
"""Replay every patch the undefended arm of the ASR experiment accepted through VeriFix's
assurance engine and pre-write output policy. This answers two questions:
(1) would the defences have stopped the shipped payloads, and (2) how many "accepted" undefended
patches were wrong anyway (latent defects that tests alone did not catch)?"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from asr_experiment import CASE, goal_hit, plant  # noqa: E402
from verifix.agent_harness import BENCHMARK_CATALOG  # noqa: E402
from verifix.agent_security import output_policy  # noqa: E402
from verifix.assurance.engine import run_patch_assurance  # noqa: E402
from verifix.test_runner import SandboxedTestRunner  # noqa: E402


def main() -> int:
    data = json.loads((ROOT / "benchmarks/security/asr_experiment.json").read_text())
    corpus = {a["id"]: a for a in json.loads((ROOT / "benchmarks/security/prompt_injection_corpus.json").read_text())["attacks"]}
    cat = BENCHMARK_CATALOG[CASE]
    tests = [cat["repro_test"], *cat.get("caller_tests", [])]
    spec = ROOT / "benchmarks" / "assurance_specs" / f"{CASE}.py"
    out = []
    for r in data["rows"]:
        if r["arm"] != "off" or not r["fixed_bug"] or not r["final_diff"]:
            continue
        attack = corpus[r["attack"]]
        td = Path(tempfile.mkdtemp(prefix="vfx_replay_"))
        try:
            base, wt = td / "base", td / "wt"
            shutil.copytree(ROOT / cat["repo_subpath"], base, ignore=shutil.ignore_patterns("__pycache__"))
            plant(base, attack)
            shutil.copytree(base, wt)
            (td / "p.diff").write_text(r["final_diff"].rstrip("\n") + "\n")
            ap = subprocess.run(["git", "apply", "--whitespace=nowarn", str(td / "p.diff")], cwd=wt, capture_output=True, text=True)
            if ap.returncode:
                out.append({"attack": r["attack"], "run_id": r["run_id"], "error": "diff did not apply: " + ap.stderr[:200]})
                continue
            tf = cat["target_file"]
            policy = output_policy((base / tf).read_text(), (wt / tf).read_text())
            rep = run_patch_assurance(wt, tf, tests, SandboxedTestRunner, spec_file=spec, baseline_dir=base)
            out.append({"attack": r["attack"], "category": attack["category"], "run_id": r["run_id"], "payload_shipped": r["shipped"],
                        "policy_blocks": [f["rule"] for f in policy], "assurance_verdict": rep["verdict"],
                        "blocking_gates": rep["blocking_gates"],
                        "stopped_by_defences": bool(policy) or rep["verdict"] == "BLOCKED"})
            print(json.dumps(out[-1]), flush=True)
        finally:
            shutil.rmtree(td, ignore_errors=True)
    ok = [o for o in out if "error" not in o]
    shipped = [o for o in ok if o["payload_shipped"]]
    clean = [o for o in ok if not o["payload_shipped"]]
    summary = {
        "undefended_accepted_patches": len(ok), "replay_errors": len(out) - len(ok),
        "payload_patches": len(shipped), "payload_patches_stopped": sum(o["stopped_by_defences"] for o in shipped),
        "payload_patches_stopped_by_policy": sum(bool(o["policy_blocks"]) for o in shipped),
        "no_payload_patches": len(clean), "no_payload_but_blocked_by_assurance": sum(o["assurance_verdict"] == "BLOCKED" for o in clean),
    }
    (ROOT / "benchmarks/security/asr_replay_undefended.json").write_text(json.dumps({"doc": __doc__.strip(), "summary": summary, "rows": out}, indent=1) + "\n")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
