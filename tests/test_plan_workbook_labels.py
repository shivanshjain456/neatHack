"""plan.xlsx must not present retired or historical figures as current measurements."""
import re
import subprocess
import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
RETIRED = ("79.83", "97.76", "97.58", "96.96", "99.80", "488x", "Infinite", "298,050")


def text_cells():
    wb = openpyxl.load_workbook(ROOT / "plan.xlsx")
    for ws in wb:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and not cell.value.startswith("="):
                    yield f"{ws.title}!{cell.coordinate}", cell.value


def test_no_retired_figures_in_workbook_text():
    hits = [(ref, v) for ref, v in text_cells() if any(r in v for r in RETIRED)]
    assert not hits, hits


def test_historical_run_is_always_labelled_historical():
    for ref, value in text_cells():
        if "exp_24aa3f2776" in value:
            assert re.search(r"historical", value, re.I), (ref, value)


def test_workbook_states_projections_and_controlled_result():
    text = " ".join(v for _, v in text_cells())
    assert "projections, not realised results" in text
    assert "62% fewer tokens than whole-repository context" in text


def test_archived_generator_refuses_to_overwrite_committed_workbook():
    script = ROOT / "scripts/archive/generate_cfo_ai_workbook.py"
    result = subprocess.run([sys.executable, str(script), "--output", str(ROOT / "plan.xlsx")],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode != 0
    assert "Refusing to overwrite" in result.stderr
