"""VeriFix assurance probe: runs inside the sandbox, stdlib only, reads a JSON job on stdin.

Modes
-----
``tests``      run test targets with line tracing and decision instrumentation of one source file;
               reports per-test pass/fail, executed lines and decision outcomes (for coverage, SBFL).
``call``       call one function (or a declared driver) on a list of inputs; reports canonical
               outputs or exception types, per-call minimum time, return-annotation conformance and
               whether a second pass in reverse order reproduced the same outputs.
``relations``  execute metamorphic relations / contracts declared in a spec file.

The result is printed as one line prefixed with ``__VFX_RESULT__`` so test output cannot corrupt it.
"""

import ast
import importlib
import importlib.abc
import importlib.util
import json
import math
import os
import random
import signal
import sys
import time
import traceback
import typing

MARK = "__VFX_RESULT__"

# Network guard (the orchestrator also strips credentials from the environment).
import socket as _socket  # noqa: E402


def _blocked(*_a, **_k):
    raise PermissionError("VeriFix sandbox: network access is disabled for code under test")


for _n in ("connect", "connect_ex", "sendto"):
    setattr(_socket.socket, _n, _blocked)
_socket.create_connection = _blocked
_socket.getaddrinfo = _blocked


class CallTimeout(Exception):
    pass


def _alarm(_signum, _frame):
    raise CallTimeout()


def with_timeout(seconds, fn, *args, **kwargs):
    if hasattr(signal, "setitimer"):
        signal.signal(signal.SIGALRM, _alarm)
        signal.setitimer(signal.ITIMER_REAL, seconds)
        try:
            return fn(*args, **kwargs)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
    return fn(*args, **kwargs)


# ── canonical values ─────────────────────────────────────────────────────────────────────────
def canon(value, depth=0):
    if depth > 6:
        return {"t": "deep"}
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return {"t": "int", "v": str(value)} if abs(value) > 2 ** 53 else value
    if isinstance(value, float):
        if math.isnan(value):
            return {"t": "float", "v": "nan"}
        return {"t": "float", "v": repr(value)}
    if isinstance(value, (list, tuple)):
        return {"t": type(value).__name__, "v": [canon(v, depth + 1) for v in value]}
    if isinstance(value, dict):
        return {"t": "dict", "v": sorted([[repr(k), canon(v, depth + 1)] for k, v in value.items()])}
    if isinstance(value, (set, frozenset)):
        return {"t": "set", "v": sorted(repr(v) for v in value)}
    try:
        import decimal
        if isinstance(value, decimal.Decimal):
            return {"t": "Decimal", "v": str(value)}
    except ImportError:
        pass
    return {"t": type(value).__name__, "v": repr(value)[:200]}


# ── return-annotation conformance ────────────────────────────────────────────────────────────
def conforms(value, hint):
    if hint is typing.Any or hint is None and value is None:
        return True
    if hint is None or hint is type(None):
        return value is None
    origin = typing.get_origin(hint)
    args = typing.get_args(hint)
    if origin is typing.Union or (origin is not None and str(origin) == "<class 'types.UnionType'>"):
        return any(conforms(value, a) for a in args)
    try:
        import types as _types
        if isinstance(hint, _types.UnionType):
            return any(conforms(value, a) for a in typing.get_args(hint))
    except AttributeError:
        pass
    if hint is int:
        return isinstance(value, int) and not isinstance(value, bool)
    if hint is float:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if hint in (str, bool, bytes):
        return isinstance(value, hint)
    if origin in (list, tuple, dict, set, frozenset):
        if not isinstance(value, origin):
            return False
        if origin is list and args:
            return all(conforms(v, args[0]) for v in value)
        if origin is tuple and args:
            if len(args) == 2 and args[1] is Ellipsis:
                return all(conforms(v, args[0]) for v in value)
            return len(args) == len(value) and all(conforms(v, a) for v, a in zip(value, args))
        if origin is dict and args:
            return all(conforms(k, args[0]) and conforms(v, args[1]) for k, v in value.items())
        return True
    if hint in (list, tuple, dict, set):
        return isinstance(value, hint)
    if isinstance(hint, type):
        return isinstance(value, hint)
    return True  # unsupported hint form: not judged


# ── decision instrumentation ─────────────────────────────────────────────────────────────────
DECISIONS = {}      # id -> {"line": int, "kind": str}
OUTCOMES = {}       # id -> set of bools observed in the current test


def __vfx_dec__(did, value):
    OUTCOMES.setdefault(did, set()).add(bool(value))
    return value


def __vfx_for__(did, iterable):
    entered = False
    for item in iterable:
        entered = True
        OUTCOMES.setdefault(did, set()).add(True)
        yield item
    if not entered:
        OUTCOMES.setdefault(did, set()).add(False)


class Instrumenter(ast.NodeTransformer):
    def _new(self, node, kind):
        did = len(DECISIONS)
        DECISIONS[did] = {"line": node.lineno, "kind": kind}
        return did

    def _wrap(self, test, did):
        call = ast.Call(func=ast.Name(id="__vfx_dec__", ctx=ast.Load()),
                        args=[ast.Constant(did), test], keywords=[])
        return ast.copy_location(call, test)

    def visit_If(self, node):
        self.generic_visit(node)
        node.test = self._wrap(node.test, self._new(node, "if"))
        return node

    def visit_While(self, node):
        self.generic_visit(node)
        node.test = self._wrap(node.test, self._new(node, "while"))
        return node

    def visit_IfExp(self, node):
        self.generic_visit(node)
        node.test = self._wrap(node.test, self._new(node, "ifexp"))
        return node

    def visit_For(self, node):
        self.generic_visit(node)
        did = self._new(node, "for")
        call = ast.Call(func=ast.Name(id="__vfx_for__", ctx=ast.Load()),
                        args=[ast.Constant(did), node.iter], keywords=[])
        node.iter = ast.copy_location(call, node.iter)
        return node


def executable_lines(source, filename):
    code = compile(source, filename, "exec")
    lines = set()
    stack = [code]
    while stack:
        co = stack.pop()
        for _s, _e, ln in co.co_lines():
            if ln is not None:
                lines.add(ln)
        stack.extend(c for c in co.co_consts if hasattr(c, "co_lines"))
    # drop docstring-only and def/class header lines are kept (they execute at import)
    return sorted(lines)


class InstrumentingFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def __init__(self, fullname, path):
        self.fullname, self.path = fullname, path

    def find_spec(self, fullname, path=None, target=None):
        if fullname == self.fullname:
            return importlib.util.spec_from_file_location(fullname, self.path, loader=self)
        return None

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        src = open(self.path, encoding="utf-8").read()
        tree = Instrumenter().visit(ast.parse(src, self.path))
        ast.fix_missing_locations(tree)
        module.__dict__["__vfx_dec__"] = __vfx_dec__
        module.__dict__["__vfx_for__"] = __vfx_for__
        exec(compile(tree, self.path, "exec"), module.__dict__)


def module_name_for(root, path):
    rel = os.path.relpath(path, root)
    parts = rel[:-3].split(os.sep)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


# ── test discovery / execution ───────────────────────────────────────────────────────────────
def load_test_module(root, rel):
    path = os.path.join(root, rel)
    name = "vfx_test_" + rel.replace(os.sep, "_").replace(".", "_")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def iter_tests(root, targets):
    for raw in targets:
        rel, _, only = raw.partition("::")
        mod = load_test_module(root, rel)
        for attr in sorted(dir(mod)):
            fn = getattr(mod, attr)
            if attr.startswith("test_") and callable(fn) and (not only or attr == only):
                yield f"{rel}::{attr}", fn


def run_tests_mode(job):
    root = job["root"]
    target = os.path.abspath(os.path.join(root, job["source_file"]))
    sys.path.insert(0, root)
    fullname = module_name_for(root, target)
    sys.meta_path.insert(0, InstrumentingFinder(fullname, target))
    src = open(target, encoding="utf-8").read()
    exe = executable_lines(src, target)
    results = []
    current = set()

    def tracer(frame, event, arg):
        if frame.f_code.co_filename != target:
            return None

        def local(frame, event, arg):
            if event == "line":
                current.add(frame.f_lineno)
            return local
        current.add(frame.f_lineno)
        return local

    budget = float(job.get("per_test_timeout", 10))
    for test_id, fn in iter_tests(root, job["targets"]):
        current.clear()
        OUTCOMES.clear()
        sys.settrace(tracer)
        status, err = True, ""
        try:
            with_timeout(budget, fn)
        except CallTimeout:
            status, err = False, "timeout"
        except BaseException as exc:  # a failing test is data, not a probe failure
            status, err = False, f"{type(exc).__name__}: {str(exc)[:300]}"
        finally:
            sys.settrace(None)
        results.append({"id": test_id, "passed": status, "error": err, "lines": sorted(current),
                        "decisions": {str(k): sorted(v) for k, v in OUTCOMES.items()}})
    return {"tests": results, "executable_lines": exe,
            "decision_points": {str(k): v for k, v in DECISIONS.items()}, "module": fullname}


# ── function calls ───────────────────────────────────────────────────────────────────────────
def resolve(module, qualname):
    obj = module
    for part in qualname.split("."):
        obj = getattr(obj, part)
    return obj


def run_call_mode(job):
    root = job["root"]
    sys.path.insert(0, root)
    module = importlib.import_module(job["module"])
    driver = None
    if job.get("driver_source"):
        ns = {}
        exec(job["driver_source"], ns)
        driver = ns["drive"]
        fn = None
        hint = None
    else:
        fn = resolve(module, job["qualname"])
        try:
            hint = typing.get_type_hints(fn).get("return", None)
            has_hint = "return" in typing.get_type_hints(fn)
        except Exception:
            hint, has_hint = None, False
    repeat = int(job.get("repeat", 1))
    per_call = float(job.get("timeout_per_call", 2.0))

    def one(inp):
        args, kwargs = inp.get("args", []), inp.get("kwargs", {})
        best = None
        out = None
        for _ in range(repeat):
            t0 = time.perf_counter_ns()
            try:
                if driver is not None:
                    value = with_timeout(per_call, driver, module, inp)
                else:
                    value = with_timeout(per_call, fn, *args, **kwargs)
                out = {"ok": True, "value": canon(value), "type": type(value).__name__}
                if driver is None and has_hint:
                    out["conforms"] = bool(conforms(value, hint))
            except CallTimeout:
                out = {"ok": False, "exc": "Timeout", "msg": f">{per_call}s"}
                break
            except RecursionError:
                out = {"ok": False, "exc": "RecursionError", "msg": ""}
                break
            except Exception as exc:
                out = {"ok": False, "exc": type(exc).__name__, "msg": str(exc)[:160]}
            dt = time.perf_counter_ns() - t0
            best = dt if best is None else min(best, dt)
        out["ns"] = best
        return out

    inputs = job["inputs"]
    first = [one(i) for i in inputs]
    second = None
    if job.get("determinism_pass", True):
        rev = [one(i) for i in reversed(inputs)]
        rev.reverse()
        second = [
            (a.get("ok"), a.get("value"), a.get("exc")) == (b.get("ok"), b.get("value"), b.get("exc"))
            for a, b in zip(first, rev)
        ]
    return {"results": first, "same_on_second_pass": second,
            "return_hint": None if driver is not None or hint is None else repr(hint)}


# ── metamorphic relations / contracts ────────────────────────────────────────────────────────
def run_relations_mode(job):
    root = job["root"]
    sys.path.insert(0, root)
    ns = {"__name__": "vfx_relations"}
    exec(compile(open(job["spec_file"], encoding="utf-8").read(), job["spec_file"], "exec"), ns)
    out = []
    for name, fn in sorted(ns.items()):
        if not (name.startswith("mr_") or name.startswith("contract_")) or not callable(fn):
            continue
        rng = random.Random(f"{job.get('seed', 0)}:{name}")
        trials = int(job.get("trials", 200))
        doc = (fn.__doc__ or "").strip().splitlines()[0] if fn.__doc__ else ""
        rec = {"name": name, "doc": doc, "trials": 0, "status": "pass"}
        for i in range(trials):
            try:
                with_timeout(float(job.get("timeout_per_trial", 2.0)), fn, rng)
                rec["trials"] = i + 1
            except AssertionError as exc:
                rec.update(status="fail", trials=i + 1, counterexample=str(exc)[:400])
                break
            except CallTimeout:
                rec.update(status="fail", trials=i + 1, counterexample="timeout")
                break
            except Exception as exc:
                rec.update(status="error", trials=i + 1,
                           counterexample=f"{type(exc).__name__}: {str(exc)[:300]}")
                break
        out.append(rec)
    return {"relations": out}


def main():
    job = json.loads(sys.stdin.read())
    try:
        mode = job["mode"]
        result = {"tests": run_tests_mode, "call": run_call_mode, "relations": run_relations_mode}[mode](job)
        result["probe_ok"] = True
    except Exception as exc:
        result = {"probe_ok": False, "error": f"{type(exc).__name__}: {exc}",
                  "trace": traceback.format_exc()[-1500:]}
    sys.stdout.write("\n" + MARK + json.dumps(result) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
