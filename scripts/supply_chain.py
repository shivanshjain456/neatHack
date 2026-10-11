#!/usr/bin/env python3
"""VeriFix supply-chain CLI: lock, verify-lock, sca, bundle, reproduce, sbom, provenance, verify-provenance, pins."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from verifix import supply_chain as sc  # noqa: E402

LOCK = ROOT / "requirements-runtime.lock"
HASHED = ROOT / "requirements-runtime.hashes.lock"
META = ROOT / "quality" / "supply-chain" / "dependency_meta.json"
ALLOW = ROOT / "quality" / "supply-chain" / "vuln_allowlist.json"
OUT = ROOT / "artifacts" / "supply-chain"
BUNDLE_DIRS = ["src/verifix", "scripts", "benchmarks", "docs", "quality"]
BUNDLE_FILES = ["README.md", "pyproject.toml", "requirements-runtime.lock", "requirements-runtime.hashes.lock", "BUSINESS_PLAN.md", "QUALITY_REPORT.md"]
REPO_URL = "https://github.com/shivanshjain456/neatHack"


def bundle_entries(root: Path = ROOT) -> list[tuple[str, bytes]]:
    entries = []
    for d in BUNDLE_DIRS:
        for f in sorted((root / d).rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts and f.suffix not in {".pyc", ".pyo"} and not f.name.startswith(".DS_"):
                entries.append((f.relative_to(root).as_posix(), f.read_bytes()))
    for name in BUNDLE_FILES:
        if (root / name).is_file():
            entries.append((name, (root / name).read_bytes()))
    return entries


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"cannot determine commit (pass --commit): {exc}") from exc


def cmd_lock(_a) -> int:
    import httpx

    with httpx.Client(timeout=30) as c:
        text, meta = sc.hashed_lock(sc.parse_lock(LOCK), c)
    HASHED.write_text(text, encoding="utf-8")
    META.parent.mkdir(parents=True, exist_ok=True)
    META.write_text(json.dumps(meta, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"hashed {len(meta)} packages, {sum(len(m['sha256']) for m in meta.values())} file digests")
    return 0


def cmd_verify_lock(_a) -> int:
    plain = sc.parse_lock(LOCK)
    text = HASHED.read_text(encoding="utf-8")
    hashed = re.findall(r"^([A-Za-z0-9_.\-]+)==(\S+) \\$", text, re.M)
    blocks = re.split(r"^(?=[A-Za-z0-9_.\-]+==)", text, flags=re.M)[1:]
    problems = []
    if sorted(map(tuple, plain)) != sorted(hashed):
        problems.append(f"pins differ: {sorted(set(plain) ^ set(hashed))[:5]}")
    for b in blocks:
        if not re.search(r"--hash=sha256:[0-9a-f]{64}", b):
            problems.append(f"no digest for {b.split()[0]}")
    meta = json.loads(META.read_text(encoding="utf-8"))
    if sorted(meta) != sorted(sc.normalize(n) for n, _ in plain):
        problems.append("dependency_meta.json is stale")
    print(json.dumps({"ok": not problems, "packages": len(plain), "problems": problems}))
    return 1 if problems else 0


def cmd_sca(a) -> int:
    import httpx

    pins = sc.parse_lock(a.lock or LOCK)
    with httpx.Client(timeout=30) as c:
        findings = sc.osv_scan(pins, c)
    allow = json.loads(ALLOW.read_text(encoding="utf-8")) if ALLOW.exists() else {"entries": []}
    verdict = sc.vuln_policy(findings, allow)
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"scanned_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "database": "https://osv.dev (querybatch)",
              "packages": len(pins), "findings": findings, **verdict}
    (OUT / "osv_report.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("packages", "total_findings", "ok")} | {"blocking": len(verdict["blocking"])}))
    return 0 if verdict["ok"] else 1


def cmd_bundle(a) -> int:
    print(sc.deterministic_zip(a.out, bundle_entries()))
    return 0


def cmd_reproduce(_a) -> int:
    with tempfile.TemporaryDirectory() as td:
        d1 = sc.deterministic_zip(Path(td) / "a.zip", bundle_entries())
        d2 = sc.deterministic_zip(Path(td) / "b.zip", list(reversed(bundle_entries())))
    print(json.dumps({"build_1": d1, "build_2": d2, "reproducible": d1 == d2}))
    return 0 if d1 == d2 else 1


def cmd_sbom(a) -> int:
    meta = json.loads(META.read_text(encoding="utf-8"))
    digest = sc.sha256_file(a.artifact) if a.artifact else None
    bom = sc.cyclonedx_sbom(meta, Path(a.artifact).name if a.artifact else "verifix-runtime", digest, a.version)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "sbom.cdx.json").write_text(json.dumps(bom, indent=1) + "\n", encoding="utf-8")
    print(f"{len(bom['components'])} components -> artifacts/supply-chain/sbom.cdx.json")
    return 0


def _materials() -> dict[str, str]:
    return {f"file:{p.relative_to(ROOT).as_posix()}": sc.sha256_file(p) for p in (LOCK, HASHED)}


def cmd_provenance(a) -> int:
    commit = a.commit or git_commit()
    st = sc.provenance_statement(Path(a.artifact).name, sc.sha256_file(a.artifact), commit, REPO_URL, _materials(),
                                 a.builder, a.invocation)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "provenance.intoto.json").write_text(json.dumps(st, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(st["subject"]))
    return 0


def cmd_verify_provenance(a) -> int:
    st = json.loads(Path(a.statement).read_text(encoding="utf-8"))
    problems = sc.verify_provenance(st, a.artifact, a.commit or git_commit(), _materials())
    print(json.dumps({"verified": not problems, "problems": problems}))
    return 1 if problems else 0


def cmd_pins(_a) -> int:
    """Every third-party GitHub Action must be pinned to a full 40-hex commit SHA."""
    bad = []
    for wf in (ROOT / ".github" / "workflows").glob("*.y*ml"):
        for n, line in enumerate(wf.read_text(encoding="utf-8").splitlines(), 1):
            m = re.search(r"uses:\s*([^\s#]+)", line)
            if m and not m.group(1).startswith("./") and not re.search(r"@[0-9a-f]{40}$", m.group(1)):
                bad.append(f"{wf.name}:{n} {m.group(1)}")
    print(json.dumps({"ok": not bad, "unpinned": bad}))
    return 1 if bad else 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("lock").set_defaults(f=cmd_lock)
    sub.add_parser("verify-lock").set_defaults(f=cmd_verify_lock)
    s = sub.add_parser("sca"); s.add_argument("--lock"); s.set_defaults(f=cmd_sca)
    s = sub.add_parser("bundle"); s.add_argument("--out", required=True); s.set_defaults(f=cmd_bundle)
    sub.add_parser("reproduce").set_defaults(f=cmd_reproduce)
    s = sub.add_parser("sbom"); s.add_argument("--artifact"); s.add_argument("--version", default="4.0.0"); s.set_defaults(f=cmd_sbom)
    s = sub.add_parser("provenance"); s.add_argument("--artifact", required=True); s.add_argument("--commit")
    s.add_argument("--builder", default="https://github.com/shivanshjain456/neatHack/local-operator")
    s.add_argument("--invocation", default="local"); s.set_defaults(f=cmd_provenance)
    s = sub.add_parser("verify-provenance"); s.add_argument("--statement", required=True); s.add_argument("--artifact", required=True)
    s.add_argument("--commit"); s.set_defaults(f=cmd_verify_provenance)
    sub.add_parser("pins").set_defaults(f=cmd_pins)
    a = p.parse_args()
    return a.f(a)


if __name__ == "__main__":
    raise SystemExit(main())
