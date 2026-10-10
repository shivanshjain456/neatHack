"""Live Neatlogs MCP Client (`https://ingest.neatlogs.com/mcp`) for trace inspection and triage."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
import neatlogs

from verifix.config import load_env_if_present


class NeatlogsMCPClient:
    """Streamable HTTP JSON-RPC 2.0 client for the official Neatlogs MCP server."""

    def __init__(self, api_key: str | None = None, endpoint: str | None = None):
        load_env_if_present()
        self.api_key = (api_key or os.environ.get("NEATLOGS_API_KEY") or "").strip()
        base = (endpoint or os.environ.get("NEATLOGS_ENDPOINT") or "https://ingest.neatlogs.com").rstrip("/")
        self.mcp_url = f"{base}/mcp"
        self.session_id: str | None = None
        self._req_id = 0

    def _headers(self) -> dict[str, str]:
        h = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            h["mcp-session-id"] = self.session_id
        return h

    def _parse_sse_or_json(self, raw_text: str) -> dict[str, Any]:
        for line in raw_text.splitlines():
            if line.startswith("data: "):
                return json.loads(line[6:])
        return json.loads(raw_text)

    def ensure_session(self) -> str:
        """Initialize the MCP Streamable HTTP session and obtain `mcp-session-id`."""
        if self.session_id:
            return self.session_id
        if not self.api_key:
            raise RuntimeError("NEATLOGS_API_KEY is required to connect to Neatlogs MCP server.")

        self._req_id += 1
        r = httpx.post(
            self.mcp_url,
            headers=self._headers(),
            json={
                "jsonrpc": "2.0",
                "id": self._req_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "verifix-mcp-client", "version": "0.2.0"},
                },
            },
            timeout=15.0,
        )
        r.raise_for_status()
        self.session_id = r.headers.get("mcp-session-id")
        httpx.post(
            self.mcp_url,
            headers=self._headers(),
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            timeout=10.0,
        )
        return self.session_id or ""

    @neatlogs.span(
        kind="MCP_TOOL",
        tool_name="neatlogs_mcp_call",
        description="Invoke a tool on the live Neatlogs MCP server (whoami, search_traces, get_trace_context, triage_list).",
    )
    def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Call an MCP tool on `https://ingest.neatlogs.com/mcp` and parse the inner JSON payload."""
        self.ensure_session()
        self._req_id += 1
        r = httpx.post(
            self.mcp_url,
            headers=self._headers(),
            json={
                "jsonrpc": "2.0",
                "id": self._req_id,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments or {}},
            },
            timeout=20.0,
        )
        r.raise_for_status()
        envelope = self._parse_sse_or_json(r.text)
        content = ((envelope.get("result") or {}).get("content") or [])
        if content and content[0].get("type") == "text":
            text_val = content[0].get("text", "{}")
            try:
                return json.loads(text_val)
            except Exception:
                return {"raw_text": text_val}
        return envelope

    def whoami(self) -> dict[str, Any]:
        return self.call_tool("whoami", {})

    def ping(self) -> dict[str, Any]:
        return self.call_tool("ping", {})

    def search_traces(self, query: str = "verifix", workflow_name: str | None = None, limit: int = 10) -> dict[str, Any]:
        args: dict[str, Any] = {"query": query or "verifix", "limit": limit}
        if workflow_name:
            args["workflow_name"] = workflow_name
        return self.call_tool("search_traces", args)

    def get_trace_context(self, trace_id: str) -> dict[str, Any]:
        return self.call_tool("get_trace_context", {"trace_id": trace_id})

    def list_detections(self) -> dict[str, Any]:
        return self.call_tool("list_detections", {})

    def triage_list(self) -> dict[str, Any]:
        return self.call_tool("triage_list", {})
