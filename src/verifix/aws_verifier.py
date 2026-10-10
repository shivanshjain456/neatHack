"""Live AWS Lambda (`us-east-1`) cryptographic & AST patch attestation client for Team HyperX."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import time
from pathlib import Path
from typing import Any

import neatlogs

from verifix.config import load_env_if_present

_ATTESTATION_MEM_CACHE: dict[str, dict[str, Any]] = {}
_ATTESTATION_DISK_CACHE = Path("/tmp/verifix_aws_attestation_cache.json")
_HTTP_CLIENT: Any = None


def _get_pooled_http_client() -> Any:
    global _HTTP_CLIENT
    if _HTTP_CLIENT is None:
        import httpx

        _HTTP_CLIENT = httpx.Client(timeout=12.0)
    return _HTTP_CLIENT


class AWSLambdaPatchVerifier:
    """Invokes Team HyperX's live AWS Lambda function (`verifix-hyperx-patch-verifier` in `us-east-1`)
    to produce an independent cloud AST and SHA-256 attestation receipt for every verified patch.
    Uses content-addressed SHA-256 caching and pooled HTTPS keep-alive to eliminate redundant RTTs.
    """

    FUNCTION_NAME = "verifix-hyperx-patch-verifier"
    REGION = "us-east-1"
    PUBLIC_FUNCTION_URL = "https://kmljtgaph5gaato6sysdjypw3a0vctrh.lambda-url.us-east-1.on.aws/"

    def __init__(self) -> None:
        load_env_if_present()
        if not _ATTESTATION_MEM_CACHE and _ATTESTATION_DISK_CACHE.is_file():
            try:
                _ATTESTATION_MEM_CACHE.update(json.loads(_ATTESTATION_DISK_CACHE.read_text(encoding="utf-8")))
            except Exception:
                pass

    @neatlogs.span(
        kind="TOOL",
        tool_name="aws_lambda_patch_attestation",
        description="Invoke Team HyperX AWS Lambda verifier in us-east-1 to attest AST validity and SHA-256 patch digest.",
    )
    def attest_patch(
        self,
        case_id: str,
        target_file: str,
        patched_source: str,
        unified_diff: str,
        repro_passed: bool,
        callers_passed: bool,
    ) -> dict[str, Any]:
        """Call `verifix-hyperx-patch-verifier` on AWS Lambda (`us-east-1`) and return the signed attestation."""
        t0 = time.perf_counter()
        cache_key = hashlib.sha256(
            f"{case_id}|{target_file}|{unified_diff}|{repro_passed}|{callers_passed}".encode("utf-8")
        ).hexdigest()
        if cache_key in _ATTESTATION_MEM_CACHE:
            cached = dict(_ATTESTATION_MEM_CACHE[cache_key])
            cached["latency_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
            cached["cache_hit"] = True
            return cached

        payload = {
            "case_id": case_id,
            "target_file": target_file,
            "patched_source": patched_source,
            "unified_diff": unified_diff,
            "repro_passed": repro_passed,
            "callers_passed": callers_passed,
        }
        parsed: dict[str, Any] = {}
        has_boto3 = importlib.util.find_spec("boto3") is not None
        if os.environ.get("AWS_ACCESS_KEY_ID") and has_boto3:
            try:
                import boto3

                lam = boto3.client("lambda", region_name=self.REGION)
                resp = lam.invoke(
                    FunctionName=self.FUNCTION_NAME,
                    InvocationType="RequestResponse",
                    Payload=json.dumps(payload).encode("utf-8"),
                )
                raw_body = resp["Payload"].read().decode("utf-8")
                parsed = json.loads(raw_body)
            except Exception:
                parsed = {}

        if not parsed:
            client = _get_pooled_http_client()
            http_resp = client.post(self.PUBLIC_FUNCTION_URL, json=payload)
            http_resp.raise_for_status()
            parsed = http_resp.json()

        parsed["latency_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
        parsed["attested"] = parsed.get("verdict") == "VERIFIED_ATTESTED"
        parsed["cache_hit"] = False
        if parsed["attested"]:
            _ATTESTATION_MEM_CACHE[cache_key] = dict(parsed)
            try:
                _ATTESTATION_DISK_CACHE.write_text(json.dumps(_ATTESTATION_MEM_CACHE, indent=2), encoding="utf-8")
            except Exception:
                pass
        return parsed
