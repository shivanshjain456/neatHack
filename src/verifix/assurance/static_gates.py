"""Static patch gates. Pure functions over (original, patched) source; no code is executed.

Every gate is *differential*: it reports what the patch introduced, not pre-existing debt, so a
legacy repository is not blocked for problems the agent did not create ("new-code" policy).
"""

from __future__ import annotations

import ast
import builtins
import difflib
import importlib.util
import logging
import math
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

HIGH, MEDIUM, LOW, INFO = "high", "medium", "low", "info"


@dataclass
class Finding:
    rule: str
    severity: str
    message: str
    line: int | None = None
    snippet: str = ""

    def key(self) -> tuple[str, str]:
        return (self.rule, re.sub(r"\s+", " ", self.snippet.strip()))


@dataclass
class GateResult:
    gate: str
    title: str
    terms: list[str]
    status: str                    # pass | fail | warn | skipped
    blocking: bool
    summary: str
    metrics: dict[str, Any] = field(default_factory=dict)
    findings: list[dict[str, Any]] = field(default_factory=list)
    duration_ms: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── diff helpers ─────────────────────────────────────────────────────────────────────────────
def changed_line_numbers(original: str, patched: str) -> set[int]:
    """1-based line numbers in ``patched`` that were inserted or replaced."""
    a, b = original.splitlines(), patched.splitlines()
    out: set[int] = set()
    for tag, _i1, _i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag in ("replace", "insert"):
            out.update(range(j1 + 1, j2 + 1))
    return out


def added_lines(original: str, patched: str) -> list[tuple[int, str]]:
    lines = patched.splitlines()
    return [(n, lines[n - 1]) for n in sorted(changed_line_numbers(original, patched)) if n - 1 < len(lines)]


def _safe_parse(src: str) -> ast.Module | None:
    try:
        return ast.parse(src)
    except SyntaxError:
        return None


def _snippet(src: str, line: int | None) -> str:
    if not line:
        return ""
    lines = src.splitlines()
    return lines[line - 1].strip()[:160] if 0 < line <= len(lines) else ""


def enclosing_functions(src: str, lines: set[int]) -> list[str]:
    """Qualified names of functions/methods whose body contains any of ``lines``."""
    tree = _safe_parse(src)
    if tree is None:
        return []
    names: list[str] = []

    def walk(node, prefix=""):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                q = f"{prefix}{child.name}"
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    span = set(range(child.lineno, (child.end_lineno or child.lineno) + 1))
                    if span & lines:
                        names.append(q)
                walk(child, q + ".")
    walk(tree)
    return names


# ── 1. scope / blast-radius containment ──────────────────────────────────────────────────────
TEST_PATH = re.compile(r"(^|/)(tests?|testing)/|(^|/)test_[^/]*\.py$|_test\.py$|(^|/)conftest\.py$")


def gate_scope(changed_files: list[str], allowed_files: list[str]) -> GateResult:
    allowed = set(allowed_files)
    findings: list[Finding] = []
    for f in changed_files:
        if TEST_PATH.search(f):
            findings.append(Finding("TEST_TAMPERING", HIGH, f"Patch modifies test file {f}; a fix must not edit its own oracle.", snippet=f))
        elif f not in allowed:
            findings.append(Finding("OUT_OF_SCOPE_FILE", HIGH, f"Patch modifies {f}, outside the declared target {sorted(allowed)}.", snippet=f))
    ok = not findings
    return GateResult("scope", "Patch scope and test tampering", ["blast-radius-containment", "excessive-agency-testing", "patch-overfitting-detection"],
                      "pass" if ok else "fail", not ok,
                      f"{len(changed_files)} file(s) changed; all inside the declared target." if ok else f"{len(findings)} out-of-scope change(s).",
                      {"changed_files": changed_files, "allowed_files": sorted(allowed)}, [asdict(f) for f in findings])


# ── 2. API breaking-change detection ─────────────────────────────────────────────────────────
def public_api(src: str) -> dict[str, dict[str, Any]]:
    tree = _safe_parse(src)
    api: dict[str, dict[str, Any]] = {}
    if tree is None:
        return api

    def sig(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, Any]:
        a = fn.args
        pos = a.posonlyargs + a.args
        defaults = [None] * (len(pos) - len(a.defaults)) + [ast.unparse(d) for d in a.defaults]
        return {
            "params": [{"name": p.arg, "default": d, "annotation": ast.unparse(p.annotation) if p.annotation else None}
                       for p, d in zip(pos, defaults)],
            "kwonly": [{"name": p.arg, "default": (ast.unparse(d) if d is not None else None)}
                       for p, d in zip(a.kwonlyargs, a.kw_defaults)],
            "vararg": bool(a.vararg), "kwarg": bool(a.kwarg),
            "returns": ast.unparse(fn.returns) if fn.returns else None,
        }

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            api[node.name] = sig(node)
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            api[node.name] = {"class": True}
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and (not item.name.startswith("_") or item.name == "__init__"):
                    api[f"{node.name}.{item.name}"] = sig(item)
    return api


def classify_api_change(old: dict[str, Any], new: dict[str, Any]) -> list[tuple[str, str]]:
    """Return [(severity, message)] with severity breaking|dangerous|compatible."""
    out: list[tuple[str, str]] = []
    if old.get("class") or new.get("class"):
        return out
    op, np_ = old["params"], new["params"]
    names_old = [p["name"] for p in op]
    names_new = [p["name"] for p in np_]
    for i, p in enumerate(op):
        if p["name"] not in names_new and not new["kwarg"]:
            out.append(("breaking", f"parameter '{p['name']}' removed or renamed"))
        elif p["name"] in names_new and names_new.index(p["name"]) != i and p["name"] not in ("self", "cls"):
            out.append(("breaking", f"parameter '{p['name']}' moved from position {i} to {names_new.index(p['name'])}"))
    for p in np_:
        if p["name"] not in names_old and p["default"] is None and not old["vararg"]:
            out.append(("breaking", f"new required parameter '{p['name']}'"))
        elif p["name"] not in names_old:
            out.append(("compatible", f"new optional parameter '{p['name']}'"))
    for p in op:
        q = next((x for x in np_ if x["name"] == p["name"]), None)
        if q is None:
            continue
        if p["default"] is not None and q["default"] is None:
            out.append(("breaking", f"default removed from '{p['name']}' (callers omitting it now fail)"))
        elif p["default"] != q["default"] and p["default"] is not None:
            out.append(("dangerous", f"default of '{p['name']}' changed {p['default']} -> {q['default']}"))
        if p["annotation"] != q["annotation"] and p["annotation"] is not None:
            out.append(("dangerous", f"annotation of '{p['name']}' changed {p['annotation']} -> {q['annotation']}"))
    for p in old["kwonly"]:
        if p["name"] not in [x["name"] for x in new["kwonly"]] and not new["kwarg"]:
            out.append(("breaking", f"keyword-only parameter '{p['name']}' removed"))
    for p in new["kwonly"]:
        if p["name"] not in [x["name"] for x in old["kwonly"]] and p["default"] is None:
            out.append(("breaking", f"new required keyword-only parameter '{p['name']}'"))
    if old["vararg"] and not new["vararg"]:
        out.append(("breaking", "*args removed"))
    if old["kwarg"] and not new["kwarg"]:
        out.append(("breaking", "**kwargs removed"))
    if old["returns"] != new["returns"]:
        out.append(("dangerous", f"return annotation changed {old['returns']} -> {new['returns']}"))
    return out


def gate_api(original: str, patched: str) -> GateResult:
    old, new = public_api(original), public_api(patched)
    findings: list[Finding] = []
    counts = {"breaking": 0, "dangerous": 0, "compatible": 0}
    for name, o in old.items():
        if name not in new:
            findings.append(Finding("API_REMOVED", HIGH, f"public symbol '{name}' removed", snippet=name))
            counts["breaking"] += 1
            continue
        for sev, msg in classify_api_change(o, new[name]):
            counts[sev] += 1
            if sev != "compatible":
                findings.append(Finding("API_BREAKING" if sev == "breaking" else "API_DANGEROUS",
                                        HIGH if sev == "breaking" else MEDIUM, f"{name}: {msg}", snippet=f"{name}:{msg}"))
    added = sorted(set(new) - set(old))
    counts["compatible"] += len(added)
    blocking = counts["breaking"] > 0
    status = "fail" if blocking else ("warn" if counts["dangerous"] else "pass")
    return GateResult("api", "Public API compatibility", ["breaking-change-detection", "regression-testing"], status, blocking,
                      f"{counts['breaking']} breaking, {counts['dangerous']} dangerous, {counts['compatible']} compatible change(s) to the public API.",
                      {**counts, "public_symbols_before": len(old), "public_symbols_after": len(new), "added": added},
                      [asdict(f) for f in findings])


# ── 3. SAST (differential) + intra-procedural taint ──────────────────────────────────────────
SECRETISH = re.compile(r"(signature|digest|hmac|mac|token|secret|password|passwd|api_?key)", re.I)
NETWORK_MODULES = {"socket", "urllib", "urllib3", "requests", "httpx", "http", "aiohttp", "ftplib", "smtplib", "telnetlib", "paramiko"}
PROCESS_MODULES = {"subprocess", "ctypes", "multiprocessing", "pty"}


def _call_name(node: ast.Call) -> str:
    f = node.func
    parts = []
    while isinstance(f, ast.Attribute):
        parts.append(f.attr)
        f = f.value
    if isinstance(f, ast.Name):
        parts.append(f.id)
    return ".".join(reversed(parts))


def sast_findings(src: str) -> list[Finding]:
    tree = _safe_parse(src)
    if tree is None:
        return [Finding("SYNTAX_ERROR", HIGH, "patched file does not parse")]
    out: list[Finding] = []
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imports.add(node.module.split(".")[0])
    for node in ast.walk(tree):
        line = getattr(node, "lineno", None)
        if isinstance(node, ast.Call):
            name = _call_name(node)
            kw = {k.arg: k.value for k in node.keywords if k.arg}
            if name in ("eval", "exec", "compile", "builtins.eval", "builtins.exec"):
                out.append(Finding("PY-EVAL", HIGH, f"dynamic code execution via {name}()", line))
            elif name in ("os.system", "os.popen", "os.execv", "os.execl", "os.spawnl") or \
                    (name.startswith("subprocess.") and isinstance(kw.get("shell"), ast.Constant) and kw["shell"].value is True):
                out.append(Finding("PY-SHELL", HIGH, f"shell command execution via {name}", line))
            elif name in ("pickle.loads", "pickle.load", "marshal.loads", "shelve.open", "dill.loads"):
                out.append(Finding("PY-DESERIALIZE", HIGH, f"unsafe deserialisation via {name}", line))
            elif name == "yaml.load" and "Loader" not in kw:
                out.append(Finding("PY-YAML-LOAD", HIGH, "yaml.load without an explicit safe Loader", line))
            elif name in ("hashlib.md5", "hashlib.sha1"):
                out.append(Finding("PY-WEAK-HASH", MEDIUM, f"weak hash {name} (collision-prone)", line))
            elif name == "tempfile.mktemp":
                out.append(Finding("PY-MKTEMP", MEDIUM, "tempfile.mktemp is race-prone; use mkstemp", line))
            elif isinstance(kw.get("verify"), ast.Constant) and kw["verify"].value is False:
                out.append(Finding("PY-TLS-VERIFY-OFF", HIGH, "TLS certificate verification disabled", line))
            elif name in ("__import__", "importlib.import_module") and node.args and not isinstance(node.args[0], ast.Constant):
                out.append(Finding("PY-DYNAMIC-IMPORT", MEDIUM, "import of a computed module name", line))
            elif name.startswith("random.") and ({"hmac", "secrets", "hashlib"} & imports):
                out.append(Finding("PY-INSECURE-RANDOM", MEDIUM, f"{name} in a module doing cryptography; use secrets", line))
        elif isinstance(node, ast.Compare) and any(isinstance(op, (ast.Eq, ast.NotEq)) for op in node.ops):
            names = [ast.unparse(x) for x in [node.left, *node.comparators]]
            if any(SECRETISH.search(n) for n in names) and not any(isinstance(x, ast.Constant) and x.value in (None, "", 0) for x in [node.left, *node.comparators]):
                out.append(Finding("PY-TIMING-COMPARE", HIGH, "secret compared with ==; use hmac.compare_digest (timing side channel)", line))
        elif isinstance(node, ast.ExceptHandler):
            body = node.body
            broad = node.type is None or (isinstance(node.type, ast.Name) and node.type.id in ("Exception", "BaseException"))
            if broad and len(body) == 1 and isinstance(body[0], (ast.Pass, ast.Continue)) or \
                    broad and len(body) == 1 and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                out.append(Finding("PY-SILENT-EXCEPT", HIGH, "broad exception silently suppressed", line))
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and SECRETISH.search(t.id) and isinstance(node.value, ast.Constant) \
                        and isinstance(node.value.value, str) and len(node.value.value) >= 8:
                    out.append(Finding("PY-HARDCODED-SECRET", HIGH, f"string literal assigned to {t.id}", line))
        elif isinstance(node, ast.Assert):
            out.append(Finding("PY-ASSERT-VALIDATION", LOW, "assert is stripped under python -O; do not use it for validation", line))
    for mod in sorted(imports & NETWORK_MODULES):
        out.append(Finding("PY-NETWORK-IMPORT", HIGH, f"imports network module '{mod}'", snippet=f"import {mod}"))
    for mod in sorted(imports & PROCESS_MODULES):
        out.append(Finding("PY-PROCESS-IMPORT", HIGH, f"imports process-control module '{mod}'", snippet=f"import {mod}"))
    for f in out:
        if not f.snippet:
            f.snippet = _snippet(src, f.line)
    out.extend(taint_findings(tree, src))
    return out


TAINT_SINKS = {"eval", "exec", "os.system", "os.popen", "subprocess.run", "subprocess.call", "subprocess.Popen",
               "subprocess.check_output", "pickle.loads", "open", "cursor.execute", "execute", "executescript"}
SANITIZERS = {"int", "float", "bool", "shlex.quote", "os.path.basename", "len", "hmac.compare_digest", "abs", "round"}


def taint_findings(tree: ast.Module, src: str) -> list[Finding]:
    """Intra-procedural taint: parameters are sources; flag flows into dangerous sinks.

    Assignments propagate taint; calls to a sanitiser launder it. No inter-procedural or
    alias analysis, so absence of a finding is not proof of safety.
    """
    out: list[Finding] = []
    for fn in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        tainted = {a.arg for a in fn.args.args + fn.args.kwonlyargs + fn.args.posonlyargs if a.arg not in ("self", "cls")}

        def is_tainted(expr) -> bool:
            if isinstance(expr, ast.Call) and _call_name(expr) in SANITIZERS:
                return False
            if isinstance(expr, ast.Name):
                return expr.id in tainted
            return any(is_tainted(child) for child in ast.iter_child_nodes(expr))

        for node in ast.walk(fn):
            if isinstance(node, ast.Assign) and is_tainted(node.value):
                for t in node.targets:
                    for n in ast.walk(t):
                        if isinstance(n, ast.Name):
                            tainted.add(n.id)
            elif isinstance(node, ast.Call):
                name = _call_name(node)
                short = name.split(".")[-1]
                if name in TAINT_SINKS or (short in ("execute", "executescript") and "." in name):
                    args = list(node.args) + [k.value for k in node.keywords]
                    if name == "open" and args:
                        args = args[:1]
                    if any(is_tainted(a) for a in args):
                        out.append(Finding("TAINT-FLOW", HIGH, f"parameter data reaches sink {name}() in {fn.name}", node.lineno,
                                           _snippet(src, node.lineno)))
    return out


def gate_sast(original: str, patched: str) -> GateResult:
    before = {f.key() for f in sast_findings(original)}
    after = sast_findings(patched)
    new = [f for f in after if f.key() not in before]
    high = [f for f in new if f.severity == HIGH]
    status = "fail" if high else ("warn" if new else "pass")
    return GateResult("sast", "Static security analysis (new findings only)",
                      ["sast-static-application-security-testing", "taint-analysis", "excessive-agency-testing"],
                      status, bool(high),
                      f"{len(new)} new finding(s) introduced by the patch ({len(high)} high)." if new else "No new security findings introduced by the patch.",
                      {"new_findings": len(new), "new_high": len(high), "preexisting": len(before), "rules": 17},
                      [asdict(f) for f in new])


# ── 4. secret scanning ───────────────────────────────────────────────────────────────────────
SECRET_PATTERNS = [
    ("AWS_ACCESS_KEY_ID", re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("GITHUB_TOKEN", re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b|\bgithub_pat_[A-Za-z0-9_]{60,}\b")),
    ("SLACK_TOKEN", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("GOOGLE_API_KEY", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("OPENAI_STYLE_KEY", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{20,}\b")),
    ("PRIVATE_KEY", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b")),
]
ASSIGNED_LITERAL = re.compile(r"""(?i)(secret|token|passw(or)?d|api_?key|access_?key|credential)\w*\s*[:=]\s*['"]([^'"]{16,})['"]""")


def shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = {c: s.count(c) for c in set(s)}
    return -sum(n / len(s) * math.log2(n / len(s)) for n in counts.values())


def scan_text_for_secrets(text: str) -> list[Finding]:
    out: list[Finding] = []
    for n, line in enumerate(text.splitlines(), 1):
        for rule, rx in SECRET_PATTERNS:
            for m in rx.finditer(line):
                out.append(Finding(f"SECRET-{rule}", HIGH, f"{rule.replace('_', ' ').lower()} pattern", n, m.group(0)[:6] + "…"))
        m = ASSIGNED_LITERAL.search(line)
        if m and shannon_entropy(m.group(3)) >= 3.5:
            out.append(Finding("SECRET-HIGH-ENTROPY-ASSIGNMENT", HIGH,
                               f"high-entropy literal ({shannon_entropy(m.group(3)):.2f} bits/char) assigned to a credential-like name",
                               n, m.group(3)[:4] + "…"))
    return out


def gate_secrets(original: str, patched: str) -> GateResult:
    new_text = "\n".join(t for _n, t in added_lines(original, patched))
    findings = scan_text_for_secrets(new_text)
    return GateResult("secrets", "Secret scanning of added lines", ["secret-scanning"],
                      "fail" if findings else "pass", bool(findings),
                      f"{len(findings)} credential-like value(s) in added lines." if findings else "No credential patterns in added lines.",
                      {"patterns": len(SECRET_PATTERNS) + 1, "lines_scanned": len(new_text.splitlines())},
                      [asdict(f) for f in findings])


# ── 5. imports + undefined names (hallucination) ─────────────────────────────────────────────
def _imported_modules(tree: ast.Module) -> set[str]:
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            mods.add(node.module)
    return mods


def _levenshtein(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def resolve_module(name: str, repo_root: Path) -> str | None:
    top = name.split(".")[0]
    if top in sys.stdlib_module_names:
        return "stdlib"
    rel = Path(*name.split("."))
    if (repo_root / rel).with_suffix(".py").is_file() or (repo_root / rel / "__init__.py").is_file():
        return "repository"
    if (repo_root / top).is_dir() or (repo_root / f"{top}.py").is_file():
        return "repository"
    try:
        if importlib.util.find_spec(top) is not None:
            return "installed"
    except (ImportError, ValueError):
        return None
    return None


def _installed_top_level() -> set[str]:
    try:
        from importlib import metadata
        names = set()
        for dist in metadata.distributions():
            top = dist.read_text("top_level.txt")
            names.update((top or "").split() or [str(dist.metadata.get("Name", "")).replace("-", "_").lower()])
        return {n for n in names if n and not n.startswith("_")}
    except (OSError, ValueError, ImportError) as exc:
        logging.getLogger(__name__).warning("installed-package metadata unavailable for typo hints: %s", exc)
        return set()


def defined_names(tree: ast.Module) -> set[str]:
    names: set[str] = set(dir(builtins)) | {"__name__", "__file__", "__doc__", "__spec__", "__package__", "__builtins__", "__loader__"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
            if not isinstance(node, ast.ClassDef):
                a = node.args
                names.update(x.arg for x in a.posonlyargs + a.args + a.kwonlyargs)
                if a.vararg:
                    names.add(a.vararg.arg)
                if a.kwarg:
                    names.add(a.kwarg.arg)
        elif isinstance(node, ast.Lambda):
            a = node.args
            names.update(x.arg for x in a.posonlyargs + a.args + a.kwonlyargs)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for al in node.names:
                names.add((al.asname or al.name).split(".")[0])
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            names.add(node.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            names.update(node.names)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.MatchAs) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.MatchStar) and node.name:
            names.add(node.name)
    return names


def gate_symbols(original: str, patched: str, repo_root: Path) -> GateResult:
    """Unresolvable imports (hallucinated / typosquatted packages) and undefined names."""
    t_new, t_old = _safe_parse(patched), _safe_parse(original)
    if t_new is None:
        return GateResult("symbols", "Symbol and dependency resolution", ["hallucination-rate-measurement", "typosquatting-slopsquatting-detection"],
                          "fail", True, "Patched file does not parse.", {}, [])
    findings: list[Finding] = []
    old_mods = _imported_modules(t_old) if t_old else set()
    new_mods = _imported_modules(t_new) - old_mods
    referenced = 0
    known = set(sys.stdlib_module_names) | _installed_top_level()
    for mod in sorted(new_mods):
        referenced += 1
        where = resolve_module(mod, repo_root)
        if where is None:
            near = sorted((d, k) for k in known if (d := _levenshtein(mod.split(".")[0], k)) <= 2)
            hint = f"; closest known module '{near[0][1]}'" if near else ""
            findings.append(Finding("UNRESOLVABLE_IMPORT", HIGH, f"import '{mod}' resolves to nothing (possible hallucinated or typosquatted package{hint})",
                                    snippet=f"import {mod}"))
    # names imported from repository modules must exist there
    for node in ast.walk(t_new):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0 and resolve_module(node.module, repo_root) == "repository":
            path = (repo_root / Path(*node.module.split("."))).with_suffix(".py")
            if not path.is_file():
                path = repo_root / Path(*node.module.split(".")) / "__init__.py"
            target = _safe_parse(path.read_text(encoding="utf-8")) if path.is_file() else None
            if target is not None:
                available = defined_names(target)
                for al in node.names:
                    referenced += 1
                    if al.name != "*" and al.name not in available:
                        findings.append(Finding("PHANTOM_SYMBOL", HIGH, f"'{al.name}' is not defined in {node.module}", node.lineno, f"from {node.module} import {al.name}"))
    defined = defined_names(t_new)
    old_undefined = set()
    if t_old is not None:
        old_defined = defined_names(t_old)
        old_undefined = {n.id for n in ast.walk(t_old) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id not in old_defined}
    seen: set[str] = set()
    for n in ast.walk(t_new):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
            referenced += 1
            if n.id not in defined and n.id not in old_undefined and n.id not in seen:
                seen.add(n.id)
                findings.append(Finding("UNDEFINED_NAME", HIGH, f"name '{n.id}' is used but never defined or imported", n.lineno, _snippet(patched, n.lineno)))
    supported = referenced - len(findings)
    ratio = round(supported / referenced, 4) if referenced else 1.0
    return GateResult("symbols", "Symbol and dependency resolution", ["hallucination-rate-measurement", "typosquatting-slopsquatting-detection"],
                      "fail" if findings else "pass", bool(findings),
                      f"{len(findings)} unresolved reference(s) out of {referenced}." if findings else f"All {referenced} referenced names and imports resolve.",
                      {"references_checked": referenced, "unresolved": len(findings), "supported_reference_ratio": ratio, "new_imports": sorted(new_mods)},
                      [asdict(f) for f in findings])


# ── 6. complexity ────────────────────────────────────────────────────────────────────────────
def cyclomatic(fn: ast.AST) -> int:
    c = 1
    for n in ast.walk(fn):
        if isinstance(n, (ast.If, ast.For, ast.While, ast.IfExp, ast.ExceptHandler, ast.AsyncFor, ast.With, ast.Assert)) and not isinstance(n, ast.With):
            c += 1
        elif isinstance(n, ast.BoolOp):
            c += len(n.values) - 1
        elif isinstance(n, ast.comprehension):
            c += 1 + len(n.ifs)
        elif isinstance(n, ast.match_case):
            c += 1
    return c


def cognitive(fn: ast.AST) -> int:
    """SonarSource cognitive complexity (2017 white paper), Python adaptation."""
    total = 0

    def visit(node, nesting):
        nonlocal total
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.If,)):
                total += 1 + nesting
                visit_test(child.test)
                for s in child.body:
                    visit_stmt(s, nesting + 1)
                orelse = child.orelse
                while len(orelse) == 1 and isinstance(orelse[0], ast.If):  # elif
                    total += 1
                    visit_test(orelse[0].test)
                    for s in orelse[0].body:
                        visit_stmt(s, nesting + 1)
                    orelse = orelse[0].orelse
                if orelse:
                    total += 1
                    for s in orelse:
                        visit_stmt(s, nesting + 1)
            elif isinstance(child, (ast.For, ast.While, ast.AsyncFor)):
                total += 1 + nesting
                if isinstance(child, ast.While):
                    visit_test(child.test)
                for s in child.body + child.orelse:
                    visit_stmt(s, nesting + 1)
            elif isinstance(child, ast.Try):
                for s in child.body + child.finalbody + child.orelse:
                    visit_stmt(s, nesting)
                for h in child.handlers:
                    total += 1 + nesting
                    for s in h.body:
                        visit_stmt(s, nesting + 1)
            elif isinstance(child, ast.IfExp):
                total += 1 + nesting
                visit(child, nesting + 1)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                visit(child, nesting + 1)
            elif isinstance(child, ast.BoolOp):
                visit_test(child)
            else:
                visit(child, nesting)

    def visit_stmt(s, nesting):
        wrapper = ast.Module(body=[s], type_ignores=[])
        visit(wrapper, nesting)

    def visit_test(expr):
        nonlocal total
        # each run of identical boolean operators counts once
        def ops(e, parent=None):
            nonlocal total
            if isinstance(e, ast.BoolOp):
                if not isinstance(parent, ast.BoolOp) or type(parent.op) is not type(e.op):
                    total += 1
                for v in e.values:
                    ops(v, e)
            else:
                for c in ast.iter_child_nodes(e):
                    ops(c, None)
        ops(expr)

    for stmt in getattr(fn, "body", []):
        visit_stmt(stmt, 0)
    return total


def function_metrics(src: str) -> dict[str, dict[str, int]]:
    tree = _safe_parse(src)
    out: dict[str, dict[str, int]] = {}
    if tree is None:
        return out

    def walk(node, prefix=""):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                q = prefix + child.name
                out[q] = {"cyclomatic": cyclomatic(child), "cognitive": cognitive(child),
                          "lines": (child.end_lineno or child.lineno) - child.lineno + 1}
                walk(child, q + ".")
            elif isinstance(child, ast.ClassDef):
                walk(child, prefix + child.name + ".")
    walk(tree)
    return out


def gate_complexity(original: str, patched: str) -> GateResult:
    before, after = function_metrics(original), function_metrics(patched)
    changed = enclosing_functions(patched, changed_line_numbers(original, patched))
    rows = []
    findings: list[Finding] = []
    for q in changed:
        b, a = before.get(q, {"cyclomatic": 0, "cognitive": 0}), after.get(q, {})
        rows.append({"function": q, "cyclomatic_before": b["cyclomatic"], "cyclomatic_after": a.get("cyclomatic"),
                     "cognitive_before": b["cognitive"], "cognitive_after": a.get("cognitive")})
        if a.get("cyclomatic", 0) > 10 and a.get("cyclomatic", 0) > b["cyclomatic"]:
            findings.append(Finding("COMPLEXITY_CYCLOMATIC", LOW, f"{q}: cyclomatic complexity {a['cyclomatic']} exceeds 10", snippet=q))
        if a.get("cognitive", 0) > 15 and a.get("cognitive", 0) > b["cognitive"]:
            findings.append(Finding("COMPLEXITY_COGNITIVE", LOW, f"{q}: cognitive complexity {a['cognitive']} exceeds 15", snippet=q))
    return GateResult("complexity", "Complexity of changed functions", ["cyclomatic-complexity", "cognitive-complexity"],
                      "warn" if findings else "pass", False,
                      "; ".join(f"{r['function']}: cyclomatic {r['cyclomatic_before']}→{r['cyclomatic_after']}, cognitive {r['cognitive_before']}→{r['cognitive_after']}" for r in rows) or "No function bodies changed.",
                      {"functions": rows}, [asdict(f) for f in findings])
