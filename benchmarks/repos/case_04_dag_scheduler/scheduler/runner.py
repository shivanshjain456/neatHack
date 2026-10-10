"""Downstream pipeline runner caller that executes an ExecutionDAG with retries."""

from scheduler.graph import ExecutionDAG


class PipelineRunner:
    def __init__(self, dag: ExecutionDAG):
        self.dag = dag
        self.execution_order: list[str] = []

    def run_step_with_retry(self, node_id: str, fail_first: bool = False) -> bool:
        if fail_first:
            self.dag.mark_failed(node_id)
            # Immediate retry succeeds
            self.dag.mark_succeeded(node_id)
        else:
            self.dag.mark_succeeded(node_id)
        self.execution_order.append(node_id)
        return True
