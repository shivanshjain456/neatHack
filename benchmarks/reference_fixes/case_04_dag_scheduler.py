"""Dependency DAG state tracker for multi-step agent workflows."""


class ExecutionDAG:
    """Tracks node dependencies and readiness across retries."""

    def __init__(self, edges: dict[str, list[str]]):
        self.edges = {k: list(v) for k, v in edges.items()}
        self.succeeded: set[str] = set()
        self.failed: set[str] = set()

    def mark_failed(self, node_id: str) -> None:
        self.failed.add(node_id)

    def mark_succeeded(self, node_id: str) -> None:
        self.succeeded.add(node_id)
        self.failed.discard(node_id)

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
