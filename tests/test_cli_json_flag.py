"""The agent docs promise --json on the scripting commands; the parser must accept it."""
from __future__ import annotations

import importlib


def test_json_flag_accepted_on_documented_commands():
    cli = importlib.import_module("verifix.cli")
    parser = cli.build_parser() if hasattr(cli, "build_parser") else None
    if parser is None:
        # fall back: the module builds its parser inside main(); replicate via --help-free parse
        import argparse  # noqa: F401
        raise AssertionError("cli module must expose build_parser() for gate tests")
    for argv in (
        ["run", "--case", "case_01_ledger_rounding", "--json"],
        ["resume", "--run-id", "x", "--json"],
        ["experiment", "--case", "case_01_ledger_rounding", "--json"],
        ["mcp-traces", "--limit", "3", "--json"],
        ["cfo-model", "--json"],
        ["fix-custom", "--repo-path", "r", "--target-file", "t", "--target-symbol", "s", "--repro-test", "x", "--json"],
        ["auto-fix", "--repo-path", "r", "--json"],
    ):
        parser.parse_args(argv)
