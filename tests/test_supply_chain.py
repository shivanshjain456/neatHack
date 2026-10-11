"""Supply chain: hashed lock, SBOM, OSV policy, reproducible bundle, SLSA provenance, action pinning, audit ledger."""

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import pytest

from verifix import supply_chain as sc
from verifix.audit_ledger import AuditLedger

ROOT = Path(__file__).resolve().parents[1]
CLI = [sys.executable, str(ROOT / "scripts" / "supply_chain.py")]


def run_cli(*args):
    return subprocess.run(CLI + list(args), cwd=ROOT, capture_output=True, text=True, timeout=120)


def test_hashed_lock_matches_plain_lock_and_every_pin_has_digests():
    r = run_cli("verify-lock")
    assert r.returncode == 0, r.stdout + r.stderr
    assert json.loads(r.stdout)["packages"] == len(sc.parse_lock(ROOT / "requirements-runtime.lock"))


def test_parse_lock_rejects_unpinned(tmp_path):
    p = tmp_path / "l.txt"
    p.write_text("fastapi>=0.1\n")
    with pytest.raises(ValueError):
        sc.parse_lock(p)


def test_deterministic_zip_is_order_and_time_independent(tmp_path):
    entries = [("b.txt", b"2"), ("a/x.py", b"print(1)\n"), ("c", b"")]
    d1 = sc.deterministic_zip(tmp_path / "1.zip", entries)
    d2 = sc.deterministic_zip(tmp_path / "2.zip", list(reversed(entries)))
    assert d1 == d2
    assert sc.deterministic_zip(tmp_path / "3.zip", entries + [("d", b"x")]) != d1
    with pytest.raises(ValueError):
        sc.deterministic_zip(tmp_path / "4.zip", entries + [("c", b"dup")])


def test_release_bundle_is_reproducible():
    r = run_cli("reproduce")
    assert r.returncode == 0 and json.loads(r.stdout)["reproducible"], r.stdout


def test_sbom_is_valid_cyclonedx_and_deterministic():
    meta = json.loads((ROOT / "quality/supply-chain/dependency_meta.json").read_text())
    a = sc.cyclonedx_sbom(meta, "x.zip", "ab" * 32, "4.0.0")
    b = sc.cyclonedx_sbom(meta, "x.zip", "ab" * 32, "4.0.0")
    assert a == b and a["bomFormat"] == "CycloneDX" and a["specVersion"] == "1.5"
    assert a["serialNumber"].startswith("urn:uuid:")
    assert len(a["components"]) == len(meta)
    for c in a["components"]:
        assert c["purl"].startswith("pkg:pypi/") and c["hashes"] and all(len(h["content"]) == 64 for h in c["hashes"])
    assert {d["ref"] for d in a["dependencies"]} == {"verifix"}


def test_vuln_policy_blocks_high_unknown_and_respects_expiring_allowlist():
    f = [{"id": "GHSA-1", "severity": "HIGH"}, {"id": "GHSA-2", "severity": "MODERATE"}, {"id": "PYSEC-3", "severity": "UNKNOWN"}]
    v = sc.vuln_policy(f, {"entries": []}, dt.date(2026, 10, 11))
    assert not v["ok"] and {x["id"] for x in v["blocking"]} == {"GHSA-1", "PYSEC-3"}
    allow = {"entries": [{"id": "GHSA-1", "justification": "not reachable: parser unused", "expires": "2026-12-31"},
                         {"id": "PYSEC-3", "justification": "x", "expires": "2026-01-01"}]}
    v = sc.vuln_policy(f, allow, dt.date(2026, 10, 11))
    assert [x["id"] for x in v["blocking"]] == ["PYSEC-3"] and v["accepted_risk"][0]["id"] == "GHSA-1"
    assert sc.vuln_policy([], {"entries": []})["ok"]


def _statement(tmp_path):
    art = tmp_path / "a.zip"
    sc.deterministic_zip(art, [("x", b"1")])
    mats = {"file:requirements-runtime.lock": "cd" * 32}
    st = sc.provenance_statement("a.zip", sc.sha256_file(art), "f" * 40, "https://github.com/o/r", mats, "builder", "inv")
    return art, mats, st


def test_provenance_verifies_and_detects_each_tamper(tmp_path):
    art, mats, st = _statement(tmp_path)
    assert st["_type"] == "https://in-toto.io/Statement/v1" and st["predicateType"] == "https://slsa.dev/provenance/v1"
    assert sc.verify_provenance(st, art, "f" * 40, mats) == []
    assert any("commit" in p for p in sc.verify_provenance(st, art, "e" * 40, mats))
    assert any("material" in p for p in sc.verify_provenance(st, art, "f" * 40, {"file:requirements-runtime.lock": "00" * 32}))
    art.write_bytes(art.read_bytes() + b"\0")
    assert any("matches no subject" in p for p in sc.verify_provenance(st, art, "f" * 40, mats))


def test_every_github_action_is_pinned_to_a_commit_sha():
    r = run_cli("pins")
    assert r.returncode == 0, r.stdout


def test_audit_ledger_chain_verifies_and_detects_tampering(tmp_path):
    led = AuditLedger(tmp_path / "ledger.jsonl")
    for i in range(5):
        led.append("PATCH_ACCEPTED", {"run_id": f"r{i}", "sha": str(i)})
    v = led.verify()
    assert v["ok"] and v["entries"] == 5
    head = v["head"]
    lines = led.path.read_text().splitlines()
    edited = json.loads(lines[2]); edited["data"]["sha"] = "evil"
    led.path.write_text("\n".join(lines[:2] + [json.dumps(edited)] + lines[3:]) + "\n")
    assert led.verify() == {"ok": False, "entries": 5, "first_broken": 2}
    led.path.write_text("\n".join(lines[:2] + lines[3:]) + "\n")          # deletion
    assert led.verify()["first_broken"] == 2
    led.path.write_text("\n".join(lines[:4]) + "\n")                      # truncation
    assert led.verify()["ok"] and not led.verify(expected_head=head)["ok"]
