"""Configuration, secret masking, Neatlogs SDK initialization, and multi-provider LLM client with cascade failover."""

from __future__ import annotations

import logging
import os
import re
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import neatlogs

_SDK_INITIALIZED = False

SECRET_PATTERNS = [
    re.compile(r"(AIza[0-9A-Za-z\-_]{20,})"),
    re.compile(r"(AQ\.[0-9A-Za-z\-_]{20,})"),
    re.compile(r"(sk-[0-9A-Za-z\-_]{20,})"),
    re.compile(r"(gsk_[0-9A-Za-z\-_]{20,})"),
    re.compile(r"(Bearer\s+[0-9A-Za-z\-_\.]{16,})"),
]


def redact_secrets(value: Any) -> Any:
    """Recursively scrub API keys or bearer tokens from span payloads before export."""
    if isinstance(value, str):
        out = value
        for pat in SECRET_PATTERNS:
            out = pat.sub("[REDACTED_SECRET]", out)
        return out
    if isinstance(value, dict):
        return {k: redact_secrets(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_secrets(v) for v in value]
    return value


def load_env_if_present() -> None:
    """Load environment variables from /home/user/.verifix_secrets.env or local .env if present."""
    for candidate in [
        Path("/home/user/.verifix_secrets.env"),
        Path.cwd() / ".env",
    ]:
        if candidate.is_file():
            for line in candidate.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[len("export ") :].strip()
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and k not in os.environ:
                        os.environ[k] = v


def ensure_neatlogs_initialized(default_workflow: str = "defect-remediation") -> bool:
    """Initialize Neatlogs once per process using the regional ingest endpoint."""
    global _SDK_INITIALIZED
    load_env_if_present()
    if _SDK_INITIALIZED:
        return True
    api_key = os.environ.get("NEATLOGS_API_KEY", "").strip()
    if not api_key:
        return False
    endpoint = os.environ.get("NEATLOGS_ENDPOINT", "https://ingest.neatlogs.com").strip()
    # Prevent noisy BrokenPipe/closed-stream logging at interpreter shutdown
    logging.raiseExceptions = False
    neatlogs.init(
        api_key=api_key,
        endpoint=endpoint,
        workflow_name=default_workflow,
        capture_logs=True,
        tags=["neathack-2026", "verifix"],
    )
    _SDK_INITIALIZED = True
    return True


@contextmanager
def workflow_root(workflow_name: str, trace_title: str | None = None):
    """Open a named WORKFLOW root span and stamp neatlogs.workflow_name per Neatlogs multi-workflow guide."""
    ensure_neatlogs_initialized(default_workflow=workflow_name)
    span_title = trace_title or workflow_name
    with neatlogs.trace(span_title, kind="WORKFLOW") as root:
        if root is not None:
            root.set_attribute("neatlogs.workflow_name", workflow_name)
        yield root


@dataclass
class LLMCallResult:
    content: str
    model: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    estimated_cost_usd: float
    failover_count: int = 0


class TracedLLMClient:
    """Wraps Google GenAI (Gemini) or OpenAI-compatible clients with Neatlogs tracing,
    fast HTTP retry bounds, and automatic multi-model cascade failover on 429/503/504 errors.
    """

    PRICING_PER_1M = {
        "gemini-3.1-flash-lite-preview": (0.10, 0.40),
        "gemini-3-flash-preview": (0.15, 0.60),
        "gemini-3.6-flash": (0.15, 0.60),
        "gemini-3.8-flash": (0.15, 0.60),
        "gemini-3.5-flash-lite": (0.10, 0.40),
        "gemini-3.7-flash": (0.15, 0.60),
        "gemma-4-26b-a4b-it": (0.10, 0.40),
        "gemini-2.5-flash-lite": (0.10, 0.40),
        "gemini-2.5-flash": (0.30, 2.50),
        "gpt-4o": (2.50, 10.00),
        "gpt-4o-mini": (0.15, 0.60),
    }

    GEMINI_MODEL_CASCADE = [
        "gemini-3.1-flash-lite-preview",
        "gemini-3-flash-preview",
        "gemini-3.6-flash",
        "gemma-4-26b-a4b-it",
        "gemini-3.8-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.7-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash",
    ]

    ACTIVE_MODEL_CACHE = Path("/home/user/verifix/.verifix_runtime/active_model.txt")

    def __init__(self, model: str | None = None):
        load_env_if_present()
        ensure_neatlogs_initialized()
        self.gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self.openai_key = os.environ.get("OPENAI_API_KEY")
        self.groq_key = os.environ.get("GROQ_API_KEY")

        if self.gemini_key:
            from google import genai
            from google.genai import types

            self.provider = "google_genai"
            cached_model = None
            if self.ACTIVE_MODEL_CACHE.is_file():
                cached_model = self.ACTIVE_MODEL_CACHE.read_text(encoding="utf-8").strip()
            preferred = (
                model
                or os.environ.get("VERIFIX_MODEL")
                or cached_model
                or "gemini-3.1-flash-lite-preview"
            )
            self.cascade = [preferred] + [m for m in self.GEMINI_MODEL_CASCADE if m != preferred]
            self.model = self.cascade[0]
            raw_client = genai.Client(
                api_key=self.gemini_key,
                http_options=types.HttpOptions(
                    timeout=15000,
                    retry_options=types.HttpRetryOptions(attempts=1),
                ),
            )
            self.client = neatlogs.wrap(raw_client)
        elif self.openai_key:
            from openai import OpenAI

            self.provider = "openai"
            self.model = model or os.environ.get("VERIFIX_MODEL", "gpt-4o")
            self.cascade = [self.model]
            self.client = neatlogs.wrap(OpenAI(api_key=self.openai_key))
        elif self.groq_key:
            from openai import OpenAI

            self.provider = "groq"
            self.model = model or os.environ.get("VERIFIX_MODEL", "llama-3.3-70b-versatile")
            self.cascade = [self.model]
            self.client = neatlogs.wrap(
                OpenAI(api_key=self.groq_key, base_url="https://api.groq.com/openai/v1")
            )
        else:
            raise RuntimeError(
                "No LLM API key found in environment (expected GEMINI_API_KEY, OPENAI_API_KEY, or GROQ_API_KEY)."
            )

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        template_name: str = "verifix_prompt",
    ) -> LLMCallResult:
        """Execute a traced LLM call with automatic multi-model cascade failover and cost accounting."""
        from neatlogs import SystemPromptTemplate, UserPromptTemplate

        sys_tmpl = SystemPromptTemplate([{"role": "system", "content": "{{system_instructions}}"}])
        usr_tmpl = UserPromptTemplate([{"role": "user", "content": "{{task_context}}"}])

        t0 = time.perf_counter()
        with neatlogs.trace(
            f"llm_{template_name}",
            kind="LLM",
            system_prompt_template=sys_tmpl,
            user_prompt_template=usr_tmpl,
            version="v2.1",
        ) as span:
            sys_tmpl.compile(system_instructions=system_prompt)
            usr_tmpl.compile(task_context=user_prompt)

            failover_count = 0
            last_exc: Exception | None = None
            used_model = self.model

            if self.provider == "google_genai":
                from google.genai import types

                for candidate_model in list(self.cascade):
                    try:
                        used_model = candidate_model
                        if candidate_model.startswith("gemma-"):
                            combined_prompt = f"{system_prompt}\n\n{user_prompt}"
                            resp = self.client.models.generate_content(
                                model=candidate_model,
                                contents=combined_prompt,
                                config=types.GenerateContentConfig(temperature=temperature),
                            )
                        else:
                            resp = self.client.models.generate_content(
                                model=candidate_model,
                                contents=user_prompt,
                                config=types.GenerateContentConfig(
                                    system_instruction=system_prompt,
                                    temperature=temperature,
                                ),
                            )
                        text = resp.text or ""
                        usage = getattr(resp, "usage_metadata", None)
                        prompt_tok = int(
                            getattr(usage, "prompt_token_count", 0)
                            or max(1, len(system_prompt + user_prompt) // 4)
                        )
                        comp_tok = int(
                            getattr(usage, "candidates_token_count", 0)
                            or max(1, len(text) // 4)
                        )
                        total_tok = int(
                            getattr(usage, "total_token_count", 0) or (prompt_tok + comp_tok)
                        )
                        # Promote working model to front of cascade for subsequent calls & processes
                        if candidate_model != self.cascade[0]:
                            self.cascade.remove(candidate_model)
                            self.cascade.insert(0, candidate_model)
                            self.model = candidate_model
                        self.ACTIVE_MODEL_CACHE.parent.mkdir(parents=True, exist_ok=True)
                        self.ACTIVE_MODEL_CACHE.write_text(candidate_model, encoding="utf-8")
                        last_exc = None
                        break
                    except Exception as exc:
                        last_exc = exc
                        failover_count += 1
                        neatlogs.log(
                            "LLM cascade failover from model={model} error={error}",
                            level="warning",
                            model=candidate_model,
                            error=str(exc)[:180],
                        )
                        continue
                if last_exc is not None:
                    raise last_exc
            else:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temperature,
                )
                text = resp.choices[0].message.content or ""
                usage = getattr(resp, "usage", None)
                prompt_tok = int(
                    getattr(usage, "prompt_tokens", 0)
                    or max(1, len(system_prompt + user_prompt) // 4)
                )
                comp_tok = int(
                    getattr(usage, "completion_tokens", 0) or max(1, len(text) // 4)
                )
                total_tok = prompt_tok + comp_tok

            latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            in_rate, out_rate = self.PRICING_PER_1M.get(used_model, (0.15, 0.60))
            cost_usd = round((prompt_tok * in_rate + comp_tok * out_rate) / 1_000_000.0, 6)

            if span is not None:
                span.set_attribute("neatlogs.llm.model", used_model)
                span.set_attribute("neatlogs.llm.provider", self.provider)
                span.set_attribute("neatlogs.llm.prompt_tokens", prompt_tok)
                span.set_attribute("neatlogs.llm.completion_tokens", comp_tok)
                span.set_attribute("neatlogs.llm.total_tokens", total_tok)
                span.set_attribute("neatlogs.llm.cost_usd", cost_usd)
                span.set_attribute("neatlogs.llm.failover_count", failover_count)

            neatlogs.log(
                "llm_call completed model={model} prompt_tokens={prompt_tokens} completion_tokens={completion_tokens} cost_usd={cost_usd} failovers={failovers}",
                model=used_model,
                prompt_tokens=prompt_tok,
                completion_tokens=comp_tok,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                failovers=failover_count,
            )

            return LLMCallResult(
                content=text,
                model=used_model,
                provider=self.provider,
                prompt_tokens=prompt_tok,
                completion_tokens=comp_tok,
                total_tokens=total_tok,
                latency_ms=latency_ms,
                estimated_cost_usd=cost_usd,
                failover_count=failover_count,
            )
