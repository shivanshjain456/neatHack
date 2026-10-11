import json

from verifix.state_store import VeriFixStateStore, merge_ledgers


def test_merge_keeps_rows_recorded_elsewhere_and_updates_matching_rows():
    existing = {"runs": [{"run_id": "lambda_only", "created_at": 1.0}, {"run_id": "shared", "created_at": 2.0, "status": "RUNNING"}]}
    current = {"runs": [{"run_id": "shared", "created_at": 2.0, "status": "VERIFIED_COMPLETE"}, {"run_id": "new", "created_at": 3.0}]}
    merged = merge_ledgers(existing, current)
    assert [r["run_id"] for r in merged["runs"]] == ["lambda_only", "shared", "new"]
    assert merged["runs"][1]["status"] == "VERIFIED_COMPLETE"
    assert merged["steps"] == [] and merged["experiments"] == []


def test_merge_tolerates_missing_or_odd_timestamps():
    merged = merge_ledgers({"runs": [{"run_id": "a", "created_at": "x"}, {"run_id": "b"}]}, {})
    assert {r["run_id"] for r in merged["runs"]} == {"a", "b"}


def test_export_does_not_drop_runs_missing_from_the_local_database(tmp_path, monkeypatch):
    store = VeriFixStateStore(tmp_path / "db" / "state.db")
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps({"runs": [{"run_id": "recorded_on_lambda", "created_at": 1.0}]}))
    monkeypatch.setattr(store, "ledger_snapshot_path", ledger)
    run_id = store.create_run("case_01_ledger_rounding", "goal", str(tmp_path / "repo"), str(tmp_path / "wt"))
    store.export_ledger_snapshot()
    ids = {r["run_id"] for r in json.loads(ledger.read_text())["runs"]}
    assert "recorded_on_lambda" in ids and run_id in ids
