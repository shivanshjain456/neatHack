"""Live AWS Lambda (`us-east-1`) cryptographic & AST patch attestation client for Team HyperX."""

from __future__ import annotations

import json
import os
import time
from typing import Any

import neatlogs

from verifix.config import load_env_if_present


class AWSLambdaPatchVerifier:
    """Invokes Team HyperX's live AWS Lambda function (`verifix-hyperx-patch-verifier` in `us-east-1`)
    to produce an independent cloud AST and SHA-256 attestation receipt for every verified patch.
    """

    FUNCTION_NAME = "verifix-hyperx-patch-verifier"
    REGION = "us-east-1"

    def __init__(self) -> None:
        load_env_if_present()

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
        if not os.environ.get("AWS_ACCESS_KEY_ID"):
            return {"attested": False, "reason": "AWS_ACCESS_KEY_ID not configured"}

        import boto3

        t0 = time.perf_counter()
        lam = boto3.client("lambda", region_name=self.REGION)
        payload = {
            "case_id": case_id,
            "target_file": target_file,
            "patched_source": patched_source,
            "unified_diff": unified_diff,
            "repro_passed": repro_passed,
            "callers_passed": callers_passed,
        }
        resp = lam.invoke(
            FunctionName=self.FUNCTION_NAME,
            InvocationType="RequestResponse",
            Payload=json.dumps(payload).encode("utf-8"),
        )
        raw_body = resp["Payload"].read().decode("utf-8")
        parsed = json.loads(raw_body)
        parsed["latency_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
        parsed["attested"] = parsed.get("verdict") == "VERIFIED_ATTESTED"
        return parsed
