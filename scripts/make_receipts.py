"""Deterministic per-run receipts and measured cost caps from the versioned ledger.

Every recorded run becomes a priced receipt with a sha256 over its canonical
payload, mirroring the project's rule that a claim ships with checkable
evidence. The cost-cap file states how the configured public cap relates to
the measured distribution of run costs. Re-running this script must reproduce
the committed artifacts byte-for-byte.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "benchmarks" / "verified_runs_ledger.json"
RECEIPTS_DIR = ROOT / "benchmarks" / "receipts"
CAPS_FILE = ROOT / "benchmarks" / "cost_caps.json"


def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def sha_obj(obj) -> str:
    return hashlib.sha256(canon(obj).encode("utf-8")).hexdigest()


def percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * p
    f, c = math.floor(k), math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def receipt_for(run: dict) -> dict:
    ts = datetime.fromtimestamp(float(run["created_at"]), tz=timezone.utc)
    payload = {
        "receipt_id": "VF-" + ts.strftime("%Y%m%d-%H%M%S") + "-" + run["case_id"].replace("case_", "")[:14],
        "run_id": run["run_id"],
        "case_id": run["case_id"],
        "mode": run["mode"],
        "status": run["status"],
        "attempts": run["current_attempt"],
        "rollbacks": run["rollbacks_executed"],
        "total_tokens": run["total_tokens"],
        "latency_ms": run["total_latency_ms"],
        "priced_usd": run["accumulated_cost_usd"],
        "cap_usd": run["max_cost_usd"],
        "cap_used_pct": round(run["accumulated_cost_usd"] / run["max_cost_usd"] * 100, 1),
        "created_at_utc": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    payload["sha256"] = sha_obj({k: v for k, v in payload.items() if k != "sha256"})
    return payload


def build_caps(runs: list[dict]) -> dict:
    priced = sorted(float(r["accumulated_cost_usd"]) for r in runs if r.get("accumulated_cost_usd") is not None)
    per_mode: dict[str, list[float]] = {}
    for r in runs:
        per_mode.setdefault(r["mode"], []).append(float(r["accumulated_cost_usd"]))
    cap = float(runs[0]["max_cost_usd"])
    p90 = percentile(priced, 0.90)
    return {
        "artifact": "measured cost caps",
        "source": "benchmarks/verified_runs_ledger.json",
        "n_priced_runs": len(priced),
        "configured_public_cap_usd": cap,
        "measured_usd": {
            "mean": round(sum(priced) / len(priced), 6),
            "p50": round(percentile(priced, 0.50), 6),
            "p90": round(p90, 6),
            "max": round(priced[-1], 6),
        },
        "p90_headroom_under_cap_pct": round((1 - p90 / cap) * 100, 1),
        "per_mode_usd": {
            m: {"n": len(v), "p50": round(percentile(sorted(v), 0.50), 6), "max": round(max(v), 6)}
            for m, v in sorted(per_mode.items())
        },
        "rule": "A public run is refused past its configured model budget; every run ends with a receipt stating priced, cap, cap used and proof status.",
    }


def build() -> dict[str, str]:
    raw = LEDGER.read_bytes()
    ledger = json.loads(raw.decode("utf-8"))
    runs = ledger["runs"]
    receipts = [receipt_for(r) for r in runs]
    out: dict[str, str] = {}
    for rec in receipts:
        out[f"benchmarks/receipts/{rec['run_id']}.json"] = json.dumps(rec, indent=1, sort_keys=True) + "\n"
    index = {
        "artifact": "receipt index",
        "ledger_sha256": hashlib.sha256(raw).hexdigest(),
        "count": len(receipts),
        "rows": [
            {k: rec[k] for k in ("receipt_id", "run_id", "case_id", "mode", "status", "priced_usd", "cap_usd", "cap_used_pct", "sha256")}
            for rec in receipts
        ],
    }
    out["benchmarks/receipts/index.json"] = json.dumps(index, indent=1, sort_keys=True) + "\n"
    out["benchmarks/cost_caps.json"] = json.dumps(build_caps(runs), indent=1, sort_keys=True) + "\n"
    return out


def main() -> int:
    for rel, text in build().items():
        path = ROOT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    print(f"wrote {len(build())} receipt/cap artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
