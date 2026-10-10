"""Recalculate every formula in plan.xlsx and write the computed figures to a JSON snapshot.

plan.xlsx is formula-driven and saved without cached values, so a plain reader sees blanks.
This script evaluates the workbook with the open-source `formulas` engine (no Excel needed)
and records the values BUSINESS_PLAN.md quotes, so the document can be checked against the
workbook by an automated test instead of by eye.

Usage:  pip install formulas && python scripts/compute_plan_values.py
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROWS = {
    3: "solo_customers", 4: "team_customers", 5: "enterprise_customers", 6: "total_customers",
    7: "verified_runs", 8: "subscription_mrr", 9: "usage_revenue", 10: "total_monthly_revenue",
    11: "arr", 15: "total_cogs", 16: "gross_profit", 17: "gross_margin", 21: "total_opex",
    22: "ebitda", 23: "ending_cash",
}


def column_letter(index: int) -> str:
    letters = ""
    while index:
        index, rem = divmod(index - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def main() -> int:
    try:
        import formulas  # type: ignore
    except ImportError:
        print("Install the evaluator first: pip install formulas", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "plan.xlsx"
        shutil.copy2(ROOT / "plan.xlsx", copy)
        solution = formulas.ExcelModel().loads(str(copy)).finish().calculate()
    cells: dict[tuple[int, str], float] = {}
    for key, value in solution.items():
        match = re.search(r"24M_MAIN_MODEL'?!([A-Z]+)(\d+)$", str(key).upper())
        if not match:
            continue
        raw = getattr(value, "value", value)
        try:
            number = float(raw.tolist()[0][0] if hasattr(raw, "tolist") else raw)
        except (TypeError, ValueError, IndexError):
            continue
        cells[(int(match.group(2)), match.group(1))] = number
    months = []
    for month in range(1, 25):
        col = column_letter(month + 1)
        row = {"month": month}
        for r, name in ROWS.items():
            if (r, col) not in cells:
                print(f"Missing computed cell {col}{r}", file=sys.stderr)
                return 1
            row[name] = round(cells[(r, col)], 4)
        months.append(row)
    break_even = next((m["month"] for m in months if m["ebitda"] > 0), None)
    low = min(months, key=lambda m: m["ending_cash"])
    snapshot = {
        "source": "plan.xlsx sheet 24M_Main_Model, recalculated with the `formulas` engine",
        "label": "Projection from the cfo.ai planning model; not realised results.",
        "months": months,
        "first_positive_ebitda_month": break_even,
        "lowest_cash": {"month": low["month"], "ending_cash": low["ending_cash"]},
    }
    out = ROOT / "benchmarks" / "plan_xlsx_computed.json"
    out.write_text(json.dumps(snapshot, indent=1) + "\n", encoding="utf-8")
    print(f"Wrote {out.relative_to(ROOT)}: break-even month {break_even}, lowest cash month {low['month']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
