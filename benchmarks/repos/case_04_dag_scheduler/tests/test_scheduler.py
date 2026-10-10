"""Tests for ExecutionDAG retry recovery and PipelineRunner caller."""

from scheduler.graph import ExecutionDAG
from scheduler.runner import PipelineRunner


def test_diamond_dag_recovers_after_upstream_retry():
    # Diamond DAG: ingest -> [parse_a, parse_b] -> merge
    dag = ExecutionDAG({
        "ingest": [],
        "parse_a": ["ingest"],
        "parse_b": ["ingest"],
        "merge": ["parse_a", "parse_b"],
    })
    runner = PipelineRunner(dag)
    assert dag.get_ready_nodes() == ["ingest"]
    runner.run_step_with_retry("ingest", fail_first=False)

    assert dag.get_ready_nodes() == ["parse_a", "parse_b"]
    # parse_a fails on attempt 1, then succeeds on retry!
    runner.run_step_with_retry("parse_a", fail_first=True)
    runner.run_step_with_retry("parse_b", fail_first=False)

    # Now merge MUST be ready because both parse_a and parse_b succeeded!
    assert dag.get_ready_nodes() == ["merge"]
    runner.run_step_with_retry("merge", fail_first=False)
    assert runner.execution_order == ["ingest", "parse_a", "parse_b", "merge"]
