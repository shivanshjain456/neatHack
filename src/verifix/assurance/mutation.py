"""First-order AST mutation operators restricted to the lines a patch changed.

Operators (classic names): AOR arithmetic operator replacement, ROR relational operator replacement,
LCR logical connector replacement, UOI/UOD unary ``not`` insertion/deletion, CRP constant
replacement, RVR return-value replacement, SDL statement deletion, BCR break/continue replacement.

Equivalent mutants (a mutant that no test can kill) are the main source of error in mutation scores.
Two cheap, sound filters are applied before any test runs:

* syntactic duplicates (identical normalised AST) are dropped;
* Trivial Compiler Equivalence (TCE, Papadakis et al., ICSE 2015): a mutant whose compiled bytecode
  and constants are identical to the original's, or to an earlier mutant's, is equivalent and dropped.

Mutants that survive the tests may still be equivalent; reports label survivors as "survived
(equivalence not excluded)" rather than claiming they prove a test gap.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import marshal
import random
from dataclasses import dataclass

AOR = {ast.Add: [ast.Sub, ast.Mult], ast.Sub: [ast.Add], ast.Mult: [ast.Div, ast.FloorDiv, ast.Add],
       ast.Div: [ast.Mult, ast.FloorDiv], ast.FloorDiv: [ast.Div, ast.Mult], ast.Mod: [ast.FloorDiv],
       ast.Pow: [ast.Mult]}
ROR = {ast.Lt: [ast.LtE, ast.Gt], ast.LtE: [ast.Lt, ast.GtE], ast.Gt: [ast.GtE, ast.Lt],
       ast.GtE: [ast.Gt, ast.LtE], ast.Eq: [ast.NotEq], ast.NotEq: [ast.Eq],
       ast.Is: [ast.IsNot], ast.IsNot: [ast.Is], ast.In: [ast.NotIn], ast.NotIn: [ast.In]}


@dataclass
class Mutant:
    mid: str
    operator: str
    line: int
    description: str
    source: str


def _code_fingerprint(source: str, filename: str) -> str | None:
    try:
        code = compile(source, filename, "exec")
    except (SyntaxError, ValueError):
        return None

    def strip(co):
        consts = tuple(strip(c) if hasattr(c, "co_code") else c for c in co.co_consts)
        return (co.co_code, consts, co.co_names, co.co_varnames)
    return hashlib.sha256(marshal.dumps(_flatten(strip(code)))).hexdigest()


def _flatten(obj):
    if isinstance(obj, tuple):
        return tuple(_flatten(o) for o in obj)
    if isinstance(obj, (bytes, str, int, float, complex, bool, type(None), frozenset)):
        return obj
    return repr(obj)


class _Collector(ast.NodeVisitor):
    """Collect (node path, operator, description) mutation sites on the selected lines."""

    def __init__(self, lines: set[int]):
        self.lines = lines
        self.sites: list[tuple[int, str, str, object]] = []
        self._docstrings: set[int] = set()

    def _on(self, node) -> bool:
        return getattr(node, "lineno", -1) in self.lines

    def visit_Module(self, node):
        self._mark_docstring(node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self._mark_docstring(node)
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        self._mark_docstring(node)
        self.generic_visit(node)

    def _mark_docstring(self, node):
        body = getattr(node, "body", [])
        if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                and isinstance(body[0].value.value, str):
            self._docstrings.add(id(body[0].value))

    def visit_BinOp(self, node):
        if self._on(node):
            for repl in AOR.get(type(node.op), []):
                self.sites.append((node.lineno, "AOR", f"{type(node.op).__name__}->{repl.__name__}", (node, "op", repl)))
        self.generic_visit(node)

    def visit_AugAssign(self, node):
        if self._on(node):
            for repl in AOR.get(type(node.op), []):
                self.sites.append((node.lineno, "AOR", f"{type(node.op).__name__}=->{repl.__name__}=", (node, "op", repl)))
        self.generic_visit(node)

    def visit_Compare(self, node):
        if self._on(node):
            for i, op in enumerate(node.ops):
                for repl in ROR.get(type(op), []):
                    self.sites.append((node.lineno, "ROR", f"{type(op).__name__}->{repl.__name__}", (node, ("ops", i), repl)))
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        if self._on(node):
            repl = ast.Or if isinstance(node.op, ast.And) else ast.And
            self.sites.append((node.lineno, "LCR", f"{type(node.op).__name__}->{repl.__name__}", (node, "op", repl)))
        self.generic_visit(node)

    def visit_UnaryOp(self, node):
        if self._on(node) and isinstance(node.op, ast.Not):
            self.sites.append((node.lineno, "UOD", "remove not", (node, "unnot", None)))
        if self._on(node) and isinstance(node.op, ast.USub):
            self.sites.append((node.lineno, "UOD", "remove unary minus", (node, "unnot", None)))
        self.generic_visit(node)

    def visit_If(self, node):
        if self._on(node):
            self.sites.append((node.lineno, "UOI", "negate if-condition", (node, "negate_test", None)))
        self.generic_visit(node)

    def visit_While(self, node):
        if self._on(node):
            self.sites.append((node.lineno, "UOI", "negate while-condition", (node, "negate_test", None)))
        self.generic_visit(node)

    def visit_Constant(self, node):
        if self._on(node) and id(node) not in self._docstrings:
            v = node.value
            if isinstance(v, bool):
                self.sites.append((node.lineno, "CRP", f"{v}->{not v}", (node, "value", not v)))
            elif isinstance(v, int):
                for nv in ({v + 1, v - 1, 0} - {v}):
                    self.sites.append((node.lineno, "CRP", f"{v}->{nv}", (node, "value", nv)))
            elif isinstance(v, float):
                for nv in ({v + 1.0, 0.0} - {v}):
                    self.sites.append((node.lineno, "CRP", f"{v}->{nv}", (node, "value", nv)))
            elif isinstance(v, str) and v:
                self.sites.append((node.lineno, "CRP", "string->empty", (node, "value", "")))
        self.generic_visit(node)

    def visit_Return(self, node):
        if self._on(node) and node.value is not None:
            self.sites.append((node.lineno, "RVR", "return None", (node, "return_none", None)))
        self.generic_visit(node)

    def visit_Break(self, node):
        if self._on(node):
            self.sites.append((node.lineno, "BCR", "break->continue", (node, "swap_loop", ast.Continue)))

    def visit_Continue(self, node):
        if self._on(node):
            self.sites.append((node.lineno, "BCR", "continue->break", (node, "swap_loop", ast.Break)))

    def generic_visit(self, node):
        for field in ("body", "orelse", "finalbody"):
            stmts = getattr(node, field, None)
            if isinstance(stmts, list) and len(stmts) > 1:
                for st in stmts:
                    if self._on(st) and not isinstance(st, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                        self.sites.append((st.lineno, "SDL", f"delete {type(st).__name__}", (node, ("delete", field), st)))
        super().generic_visit(node)


class _Apply(ast.NodeTransformer):
    def __init__(self, target_index: int, sites_in_order):
        self.target = sites_in_order[target_index]

    def apply(self, tree):
        node, how, payload = self.target
        if how == "op":
            node.op = payload()
        elif isinstance(how, tuple) and how[0] == "ops":
            node.ops[how[1]] = payload()
        elif how == "value":
            node.value = payload
        elif how == "negate_test":
            node.test = ast.UnaryOp(op=ast.Not(), operand=node.test)
        elif how == "return_none":
            node.value = ast.Constant(None)
        elif how == "unnot":
            return ("replace_unary", node)
        elif how == "swap_loop":
            return ("replace_stmt", node, payload())
        elif isinstance(how, tuple) and how[0] == "delete":
            stmts = getattr(node, how[1])
            idx = stmts.index(payload)
            stmts[idx] = ast.copy_location(ast.Pass(), payload)
        return None


class _ReplaceNode(ast.NodeTransformer):
    def __init__(self, old, new):
        self.old, self.new = old, new

    def visit(self, node):
        if node is self.old:
            return ast.copy_location(self.new, node)
        return super().visit(node)


def generate_mutants(source: str, lines: set[int], filename: str = "<patched>", limit: int = 60,
                     seed: int = 20261011) -> tuple[list[Mutant], dict]:
    """Return non-equivalent (by TCE) first-order mutants of ``source`` on ``lines``."""
    base_tree = ast.parse(source)
    collector = _Collector(lines)
    collector.visit(base_tree)
    n_sites = len(collector.sites)
    original_fp = _code_fingerprint(ast.unparse(base_tree), filename)
    seen_fp = {original_fp}
    seen_src: set[str] = set()
    mutants: list[Mutant] = []
    stats = {"sites": n_sites, "duplicates": 0, "tce_equivalent": 0, "invalid": 0, "sampled_out": 0}
    order = list(range(n_sites))
    if n_sites > limit * 3:
        rng = random.Random(seed)
        rng.shuffle(order)
    for idx in order:
        tree = copy.deepcopy(base_tree)
        coll = _Collector(lines)
        coll.visit(tree)
        if idx >= len(coll.sites):
            continue
        line, op, desc, target = coll.sites[idx]
        result = _Apply(idx, [s[3] for s in coll.sites]).apply(tree)
        if result is not None:
            if result[0] == "replace_unary":
                tree = _ReplaceNode(result[1], result[1].operand).visit(tree)
            elif result[0] == "replace_stmt":
                tree = _ReplaceNode(result[1], result[2]).visit(tree)
        ast.fix_missing_locations(tree)
        try:
            mutated = ast.unparse(tree)
        except (ValueError, AttributeError):
            stats["invalid"] += 1
            continue
        if mutated in seen_src:
            stats["duplicates"] += 1
            continue
        seen_src.add(mutated)
        fp = _code_fingerprint(mutated, filename)
        if fp is None:
            stats["invalid"] += 1
            continue
        if fp in seen_fp:
            stats["tce_equivalent"] += 1
            continue
        seen_fp.add(fp)
        if len(mutants) >= limit:
            stats["sampled_out"] += 1
            continue
        mutants.append(Mutant(mid=f"M{len(mutants)+1:03d}", operator=op, line=line, description=desc, source=mutated))
    return mutants, stats
