"""Dependency DAG state tracker for multi-step agent workflows."""


class ExecutionDAG:
    """Tracks node dependencies and readiness across retries.

    Downstream caller `PipelineRunner.run_until_complete` relies on:
    - `mark_failed(node_id: str)` recording failure
    - `mark_succeeded(node_id: str)` clearing any prior failure for `node_id`
    - `get_ready_nodes() -> list[str]` returning sorted node IDs whose dependencies
      have all succeeded and which have not yet succeeded themselves.
    """

    def __init__(self, edges: dict[str, list[str]]):
        # edges maps node_id -> list of prerequisite upstream node_ids
        self.edges = {k: list(v) for k, v in edges.items()}
        self.succeeded: set[str] = set()
        self.failed: set[str] = set()

    def mark_failed(self, node_id: str) -> None:
        self.failed.add(node_id)

    def mark_succeeded(self, node_id: str) -> None:
        self.succeeded.add(node_id)
        # BUG: Does not remove `node_id` from `self.failed` when a failed node
        # succeeds on retry, AND `get_ready_nodes` permanently skips any node
        # that ever entered `self.failed` or had a dependency in `self.failed`!

    def get_ready_nodes(self) -> list[str]:
        ready = []
        for node, deps in self.edges.items():
            if node in self.succeeded or node in self.failed:
                continue
            if any(d in self.failed for d in deps):
                continue
            if all(d in self.succeeded for d in deps):
                ready.append(node)
        return sorted(ready)
