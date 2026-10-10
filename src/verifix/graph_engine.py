"""Entire Graph (`entire graph`) structural code localization and blast-radius engine."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import neatlogs


def resolve_entire_binary() -> str:
    """Locate the installed `entire` CLI binary across standard and snapshot-persisted paths."""
    for candidate in [
        "/home/user/bin/entire",
        "/home/user/.local/bin/entire",
        shutil.which("entire"),
    ]:
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    raise FileNotFoundError("Entire CLI binary not found in /home/user/bin/entire or PATH")


def ensure_entire_plugins_restored() -> None:
    """Restore ~/.local/share/entire from /home/user/entire_share/entire if cleared across snapshot."""
    target = Path("/home/user/.local/share/entire")
    backup = Path("/home/user/entire_share/entire")
    if not target.exists() and backup.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(backup, target, dirs_exist_ok=True)


class EntireGraphEngine:
    """Deterministic local code graph driver using `entire graph` (`search`, `def`, `neighbors`, `impact`, `diff`)."""

    def __init__(self, repo_path: str | Path):
        self.repo_path = Path(repo_path).resolve()
        ensure_entire_plugins_restored()
        self.entire_bin = resolve_entire_binary()

    def _run_graph_cmd(self, args: list[str], timeout: float = 30.0) -> tuple[int, str, str, float]:
        env = os.environ.copy()
        env["PATH"] = f"/home/user/bin:/home/user/.local/bin:{env.get('PATH', '')}"
        cmd = [self.entire_bin, "graph"] + args
        t0 = time.perf_counter()
        proc = subprocess.run(
            cmd,
            cwd=str(self.repo_path),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        return proc.returncode, proc.stdout, proc.stderr, latency_ms

    @neatlogs.span(
        kind="TOOL",
        tool_name="entire_graph_search",
        description="Run `entire graph search --profile full` to locate ranked code symbols from a defect description.",
    )
    def search(self, query: str, limit: int = 5) -> dict[str, Any]:
        """Run `entire graph search --repo . --profile full --query <query>`."""
        rc, stdout, stderr, latency_ms = self._run_graph_cmd(
            ["search", "--repo", str(self.repo_path), "--profile", "full", "--query", query]
        )
        parsed: dict[str, Any] = {}
        try:
            parsed = json.loads(stdout)
        except Exception:
            parsed = {"raw_stdout": stdout, "stderr": stderr, "exit_code": rc}

        results = parsed.get("results") or parsed.get("hits") or parsed.get("matches") or []
        return {
            "command": f"entire graph search --repo . --profile full --query {query!r}",
            "exit_code": rc,
            "latency_ms": latency_ms,
            "hit_count": len(results),
            "top_hits": results[:limit],
            "raw": parsed,
        }

    @neatlogs.span(
        kind="TOOL",
        tool_name="entire_graph_impact",
        description="Run `entire graph impact` and `neighbors` to compute direct & transitive callers and blast radius.",
    )
    def analyze_blast_radius(self, symbol: str) -> dict[str, Any]:
        """Compute one-shot blast radius (`impact`) and structured caller graph (`neighbors`) for `symbol`."""
        rc_imp, out_imp, err_imp, lat_imp = self._run_graph_cmd(
            ["impact", "--repo", str(self.repo_path), "--symbol", symbol]
        )
        rc_nb, out_nb, err_nb, lat_nb = self._run_graph_cmd(
            ["neighbors", "--repo", str(self.repo_path), "--symbol", symbol, "--relation", "CALLS", "--direction", "both"]
        )

        nb_json: dict[str, Any] = {}
        try:
            nb_json = json.loads(out_nb)
        except Exception:
            nb_json = {"raw_stdout": out_nb, "stderr": err_nb}

        direct_callers: list[dict[str, Any]] = []
        callees: list[dict[str, Any]] = []
        target_def: dict[str, Any] = {}

        matches = nb_json.get("matches") or []
        if matches:
            primary = matches[0]
            target_def = primary.get("symbol") or {}
            for edge in primary.get("incoming") or []:
                ep = edge.get("endpoint") or {}
                direct_callers.append(
                    {
                        "name": ep.get("name", ""),
                        "file_path": ep.get("file_path", ""),
                        "start_line": ep.get("start_line", 1),
                        "end_line": ep.get("end_line", 1),
                        "call_site_line": (edge.get("call_site") or {}).get("line", ep.get("start_line", 1)),
                        "resolution": edge.get("resolution", ""),
                        "confidence": edge.get("confidence", 0.0),
                    }
                )
            for edge in primary.get("outgoing") or []:
                ep = edge.get("endpoint") or {}
                callees.append(
                    {
                        "name": ep.get("name", ""),
                        "file_path": ep.get("file_path", ""),
                        "start_line": ep.get("start_line", 1),
                        "end_line": ep.get("end_line", 1),
                    }
                )

        # Parse transitive callers & test files from `entire graph impact` text output
        transitive_callers: list[dict[str, Any]] = []
        impacted_test_files: list[str] = []
        for line in out_imp.splitlines():
            m = re.match(r"^\s*-\s+([A-Za-z0-9_]+)\s+\(([^:]+):(\d+)(?:,\s*def\s*:(\d+))?\)(?:\s*\[via\s+([^\]]+)\])?", line)
            if m:
                fn_name, fpath, call_line, def_line, via_sym = m.groups()
                if "test_" in Path(fpath).name or "/tests/" in fpath or fpath.startswith("tests/"):
                    if fpath not in impacted_test_files:
                        impacted_test_files.append(fpath)
                if via_sym:
                    transitive_callers.append(
                        {
                            "name": fn_name,
                            "file_path": fpath,
                            "call_line": int(call_line),
                            "def_line": int(def_line or call_line),
                            "via": via_sym,
                        }
                    )

        return {
            "symbol": symbol,
            "target_definition": target_def,
            "impact_command": f"entire graph impact --repo . --symbol {symbol}",
            "neighbors_command": f"entire graph neighbors --repo . --symbol {symbol} --relation CALLS --direction both",
            "latency_ms": round(lat_imp + lat_nb, 2),
            "impact_text": out_imp.strip(),
            "direct_callers": direct_callers,
            "transitive_callers": transitive_callers,
            "callees": callees,
            "impacted_test_files": impacted_test_files,
            "stats": nb_json.get("stats", {}),
        }

    @neatlogs.span(
        kind="TOOL",
        tool_name="entire_graph_diff",
        description="Run `entire graph diff --base HEAD` to inspect entity-level semantic changes in the working tree.",
    )
    def semantic_diff(self, base_ref: str = "HEAD") -> dict[str, Any]:
        """Run `entire graph diff --repo . --base <base_ref>` to inspect modified symbols."""
        rc, stdout, stderr, latency_ms = self._run_graph_cmd(
            ["diff", "--repo", str(self.repo_path), "--base", base_ref]
        )
        parsed: Any = stdout.strip()
        try:
            parsed = json.loads(stdout)
        except Exception:
            pass
        return {
            "command": f"entire graph diff --repo . --base {base_ref}",
            "exit_code": rc,
            "latency_ms": latency_ms,
            "diff": parsed,
        }

    def retrieve_focused_context(self, query: str, target_symbol: str) -> dict[str, Any]:
        """Execute a Neatlogs RETRIEVER span that combines `entire graph search` + `impact` and reads only focused line slices."""
        with neatlogs.trace("entire_graph_retriever", kind="RETRIEVER") as span:
            if span is not None:
                span.set_attribute("neatlogs.retriever.query", f"{query} | symbol={target_symbol}")
                span.set_attribute("neatlogs.retriever.top_k", 5)

            search_res = self.search(query=query, limit=5)
            blast = self.analyze_blast_radius(symbol=target_symbol)

            # Build focused source snippets around target symbol + direct non-test callers
            documents: list[dict[str, Any]] = []
            tdef = blast.get("target_definition") or {}
            if tdef.get("file_path"):
                fpath = self.repo_path / tdef["file_path"]
                if fpath.is_file():
                    lines = fpath.read_text(encoding="utf-8").splitlines()
                    s_line = max(1, int(tdef.get("start_line", 1)) - 10)
                    e_line = min(len(lines), int(tdef.get("end_line", len(lines))) + 20)
                    snippet = "\n".join(f"{i}: {lines[i-1]}" for i in range(s_line, e_line + 1))
                    documents.append(
                        {
                            "role": "target_symbol_definition",
                            "symbol": target_symbol,
                            "file_path": tdef["file_path"],
                            "line_range": f"{s_line}-{e_line}",
                            "content": fpath.read_text(encoding="utf-8"),
                            "focused_slice": snippet,
                        }
                    )

            seen_caller_files: set[str] = set()
            for callee in blast.get("callees", []):
                cfile = callee.get("file_path", "")
                if not cfile or cfile == tdef.get("file_path") or cfile in seen_caller_files:
                    continue
                seen_caller_files.add(cfile)
                fpath = self.repo_path / cfile
                if fpath.is_file():
                    content_text = fpath.read_text(encoding="utf-8")
                    documents.append(
                        {
                            "role": "callee_dependency_contract",
                            "symbol": callee.get("name"),
                            "file_path": cfile,
                            "line_range": f"1-{len(content_text.splitlines())}",
                            "focused_slice": content_text,
                        }
                    )

            for caller in blast.get("direct_callers", []):
                cfile = caller.get("file_path", "")
                if not cfile or cfile == tdef.get("file_path") or cfile in seen_caller_files:
                    continue
                seen_caller_files.add(cfile)
                fpath = self.repo_path / cfile
                if fpath.is_file():
                    lines = fpath.read_text(encoding="utf-8").splitlines()
                    s_line = max(1, int(caller.get("start_line", 1)) - 3)
                    e_line = min(len(lines), int(caller.get("end_line", len(lines))) + 3)
                    snippet = "\n".join(f"{i}: {lines[i-1]}" for i in range(s_line, e_line + 1))
                    documents.append(
                        {
                            "role": "direct_caller_contract",
                            "symbol": caller.get("name"),
                            "file_path": cfile,
                            "line_range": f"{s_line}-{e_line}",
                            "focused_slice": snippet,
                        }
                    )

            if span is not None:
                for idx, doc in enumerate(documents):
                    span.set_attribute(
                        f"neatlogs.retriever.documents.{idx}",
                        json.dumps(
                            {
                                "role": doc["role"],
                                "symbol": doc["symbol"],
                                "file_path": doc["file_path"],
                                "line_range": doc["line_range"],
                            }
                        ),
                    )

            return {
                "search": search_res,
                "blast_radius": blast,
                "documents": documents,
            }
