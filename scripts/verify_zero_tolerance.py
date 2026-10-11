"""Automated Zero-Tolerance Policy Verifier for VeriFix."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_PATTERNS = [
    (re.compile(r"AIza[0-9A-Za-z\-_]{20,}"), "Hardcoded Google/Gemini API key"),
    (re.compile(r"AQ\.[0-9A-Za-z\-_]{20,}"), "Hardcoded Neatlogs API key"),
    (re.compile(r"raise\s+NotImplementedError"), "Stubbed NotImplementedError"),
    (re.compile(r"\bTODO\b|\bFIXME\b"), "Unresolved TODO/FIXME placeholder"),
    (re.compile(r"coming soon", re.IGNORECASE), "'Coming soon' placeholder"),
    (re.compile(r"except\s*:\s*pass"), "Silent bare except: pass"),
]


def main() -> int:
    violations: list[str] = []
    scan_files = list((ROOT / "src").rglob("*.py")) + list((ROOT / "benchmarks").rglob("*.py"))

    for fpath in scan_files:
        text = fpath.read_text(encoding="utf-8")
        for pat, desc in FORBIDDEN_PATTERNS:
            if pat.search(text):
                violations.append(f"{fpath.relative_to(ROOT)}: {desc}")

    # Check browser-facing HTML/JS in server.py for forbidden localhost/127.0.0.1 calls
    server_text = (ROOT / "src/verifix/server.py").read_text(encoding="utf-8")
    if "fetch('http://localhost" in server_text or "fetch('http://127.0.0.1" in server_text:
        violations.append("src/verifix/server.py: Browser JS calls localhost/127.0.0.1 instead of relative URLs")

    if violations:
        print("ZERO-TOLERANCE AUDIT FAILED:")
        for v in violations:
            print(f"  - {v}")
        return 1

    print(f"ZERO-TOLERANCE AUDIT PASSED: {len(scan_files)} source files verified with 0 violations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
