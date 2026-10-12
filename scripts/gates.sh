#!/usr/bin/env bash
# One-shot local gate runner: everything CI (.github/workflows/ui-quality.yml) checks,
# plus the linter and the zero-tolerance checks. Every README number must stay
# reproducible from a clean clone - run this before any push.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="src:.${PYTHONPATH:+:$PYTHONPATH}"

echo "[static] README/evidence claim verification"
python scripts/verify_claims.py

echo "[unit] offline release test-suite"
python -m pytest tests/ -q

echo "[lint] ruff correctness subset (syntax + undefined names) over src/ and tests/"
# E9,F63,F7,F82 is the version-stable correctness core; style rulesets drift
# between ruff releases and are deliberately not gated here.
python -m ruff check --select E9,F63,F7,F82 src tests

echo "[zero] zero-tolerance checks"
python scripts/verify_zero_tolerance.py

echo "[dyn] assurance-gate behaviour (tests/test_assurance.py exercises every gate)"
python -m pytest tests/test_assurance.py -q

echo "[gate] all gates passed"
