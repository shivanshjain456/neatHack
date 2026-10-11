"""Assurance spec for case_04 (execution DAG); derived from the ExecutionDAG docstring and catalog goal."""


def _dag(rng):
    n = rng.randint(2, 8)
    nodes = [f"n{i}" for i in range(n)]
    edges = {node: sorted(rng.sample(nodes[:i], rng.randint(0, min(i, 3)))) for i, node in enumerate(nodes)}
    return nodes, edges


def _topo_run(rng, dag, nodes, edges, retry_p, retry_rng=None):
    """Execute the DAG in readiness order; each step may fail once then succeed (a retry).

    Node choices use ``rng``; retry decisions use a separate ``retry_rng`` so that runs with and
    without retries pick the same nodes.
    """
    import random as _r
    retry_rng = retry_rng or _r.Random(rng.random())
    seen = []
    for _ in range(len(nodes) + 1):
        ready = dag.get_ready_nodes()
        seen.append(list(ready))
        if not ready:
            break
        node = rng.choice(ready)
        if retry_rng.random() < retry_p:
            dag.mark_failed(node)
        dag.mark_succeeded(node)
    return seen


def mr_retry_is_invisible_after_success(rng):
    """Failing a node and then succeeding gives the same readiness sequence as succeeding first time."""
    from scheduler.graph import ExecutionDAG
    nodes, edges = _dag(rng)
    seed = rng.random()
    import random as _r
    a = _topo_run(_r.Random(seed), ExecutionDAG(edges), nodes, edges, retry_p=0.0, retry_rng=_r.Random(1))
    b = _topo_run(_r.Random(seed), ExecutionDAG(edges), nodes, edges, retry_p=0.6, retry_rng=_r.Random(2))
    assert a == b, f"edges={edges}: without retries {a}, with retries {b}"


def contract_ready_nodes_definition(rng):
    """Ready = sorted nodes not yet succeeded whose deps all succeeded; a completed run reaches every node."""
    from scheduler.graph import ExecutionDAG
    nodes, edges = _dag(rng)
    dag = ExecutionDAG(edges)
    steps = _topo_run(rng, dag, nodes, edges, retry_p=0.5)
    assert dag.succeeded == set(nodes), f"edges={edges}: run stalled with succeeded={sorted(dag.succeeded)}"
    ready = dag.get_ready_nodes()
    assert ready == [], f"after completion get_ready_nodes() = {ready}"
    for s in steps:
        assert s == sorted(s), f"not sorted: {s}"


def contract_failed_then_succeeded_counts_as_succeeded(rng):
    """After mark_failed(x); mark_succeeded(x), x's dependants become ready exactly as if x never failed."""
    from scheduler.graph import ExecutionDAG
    nodes, edges = _dag(rng)
    dag = ExecutionDAG(edges)
    for node in nodes:
        if rng.random() < 0.5:
            dag.mark_failed(node)
        dag.mark_succeeded(node)
        assert node not in dag.failed, f"{node} still recorded as failed after succeeding"


DRIVE = '''
def drive(module, inp):
    dag = module.ExecutionDAG(inp["edges"])
    out = []
    for op, node in inp["ops"]:
        if op == "fail":
            dag.mark_failed(node)
        elif op == "ok":
            dag.mark_succeeded(node)
        out.append(dag.get_ready_nodes())
    return out
'''


def _drive_input(rng):
    nodes, edges = _dag(rng)
    ops = [[rng.choice(["fail", "ok", "ok"]), rng.choice(nodes)] for _ in range(rng.randint(1, 12))]
    return {"edges": edges, "ops": ops}


INPUT_GENERATORS = {q: _drive_input for q in ("ExecutionDAG.mark_succeeded", "ExecutionDAG.mark_failed", "ExecutionDAG.get_ready_nodes", "ExecutionDAG.__init__")}
DRIVERS = {q: DRIVE for q in INPUT_GENERATORS}
