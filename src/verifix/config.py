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
    re.compile(r"(sk-[0-9A-Za-z\-_]{16,})"),
    re.compile(r"(gsk_[0-9A-Za-z\-_]{20,})"),
    re.compile(r"(thk_live_[0-9A-Za-z\-_]{20,})"),
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


def resolve_verifix_root_dir() -> Path:
    """Resolve the VeriFix repository root across local (/home/user/verifix) and AWS Lambda (/var/task) environments."""
    if "VERIFIX_ROOT_DIR" in os.environ:
        return Path(os.environ["VERIFIX_ROOT_DIR"]).resolve()
    if (Path("/var/task") / "benchmarks").exists():
        return Path("/var/task").resolve()
    return Path("/home/user/verifix").resolve()


def load_env_if_present() -> None:
    """Load environment variables from private .verifix_secrets.env or local .env if present."""
    is_lambda = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
    for candidate in [
        Path("/home/user/.verifix_secrets.env"),
        Path("/var/task/.verifix_secrets.env"),
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
                    if is_lambda and k.startswith("AWS_"):
                        continue
                    if k and k not in os.environ:
                        os.environ[k] = v


def get_litellm_base_url() -> str:
    """Return the configured neatHack LiteLLM base URL."""
    load_env_if_present()
    return os.environ.get("LITELLM_BASE_URL", "https://litellm.vision.aivar.app/v1").strip()


def get_litellm_api_key() -> str:
    """Return the configured neatHack LiteLLM API key from environment / untracked .env."""
    load_env_if_present()
    return os.environ.get("LITELLM_API_KEY", "").strip()



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
        "claude-opus-4.6": (5.00, 25.00),
        "claude-sonnet-4.6": (3.00, 15.00),
        "claude-haiku": (0.80, 4.00),
        "nova-pro": (0.80, 3.20),
        "nova-2-lite": (0.15, 0.60),
        "nova-lite": (0.06, 0.24),
        "nova-micro": (0.035, 0.14),
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

    LITELLM_MODEL_CASCADE = [
        "claude-sonnet-4.6",
        "claude-haiku",
        "nova-pro",
        "nova-2-lite",
        "nova-lite",
    ]

    GEMINI_MODEL_CASCADE = [
        "gemma-4-26b-a4b-it",
        "gemini-3-flash-preview",
        "gemini-3.1-flash-lite-preview",
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash",
    ]

    TOKENHARBOR_FREE_CASCADE = [
        "claude-haiku-5.5:free",
        "deepseek-v4.1-flash:free",
        "mimo-v2.5:free",
    ]

    OPENROUTER_FREE_CASCADE = [
        "cohere/north-mini-code:free",
        "nvidia/nemotron-3.5-lightning:free",
        "apodex/apodex-1.1-mini:free",
        "liquid/lfm-2.5-2.6b:free",
    ]

    ACTIVE_MODEL_CACHE = (
        Path("/tmp/verifix_runtime/active_model.txt")
        if os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
        else Path("/home/user/verifix/.verifix_runtime/active_model.txt")
    )

    def __init__(self, model: str | None = None):
        load_env_if_present()
        ensure_neatlogs_initialized()
        self.litellm_key = os.environ.get("LITELLM_API_KEY", "").strip()
        self.litellm_base_url = os.environ.get("LITELLM_BASE_URL", "https://litellm.vision.aivar.app/v1").strip()
        self.gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self.tokenharbor_key = os.environ.get("TOKENHARBOR_API_KEY")
        self.openrouter_key = os.environ.get("OPENROUTER_API_KEY")
        self.tokenrouter_key = os.environ.get("TOKENROUTER_API_KEY")
        self.openai_key = os.environ.get("OPENAI_API_KEY")
        self.groq_key = os.environ.get("GROQ_API_KEY")

        if self.litellm_key:
            from openai import OpenAI

            self.provider = "neathack_litellm"
            self.model = model or os.environ.get("VERIFIX_MODEL") or "claude-sonnet-4.6"
            self.cascade = [self.model] + [m for m in self.LITELLM_MODEL_CASCADE if m != self.model]
            self.client = neatlogs.wrap(
                OpenAI(api_key=self.litellm_key, base_url=self.litellm_base_url, timeout=25.0, max_retries=1)
            )
        elif self.gemini_key:
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
            text = ""
            prompt_tok = 0
            comp_tok = 0
            total_tok = 0
            succeeded = False

            if self.litellm_key:
                import httpx

                for ll_model in self.LITELLM_MODEL_CASCADE:
                    try:
                        used_model = ll_model
                        ll_resp = httpx.post(
                            f"{self.litellm_base_url.rstrip('/')}/chat/completions",
                            headers={"Authorization": f"Bearer {self.litellm_key}"},
                            json={
                                "model": ll_model,
                                "messages": [
                                    {"role": "system", "content": system_prompt},
                                    {"role": "user", "content": user_prompt},
                                ],
                                "temperature": temperature,
                            },
                            timeout=25.0,
                        )
                        if ll_resp.status_code == 200:
                            ll_data = ll_resp.json()
                            text = (ll_data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
                            ll_usage = ll_data.get("usage") or {}
                            prompt_tok = int(ll_usage.get("prompt_tokens") or max(1, len(system_prompt + user_prompt) // 4))
                            comp_tok = int(ll_usage.get("completion_tokens") or max(1, len(text) // 4))
                            total_tok = prompt_tok + comp_tok
                            self.provider = "neathack_litellm"
                            self.ACTIVE_MODEL_CACHE.parent.mkdir(parents=True, exist_ok=True)
                            self.ACTIVE_MODEL_CACHE.write_text(f"litellm:{ll_model}", encoding="utf-8")
                            last_exc = None
                            succeeded = True
                            break
                        raise RuntimeError(f"LiteLLM HTTP {ll_resp.status_code}: {ll_resp.text[:160]}")
                    except Exception as ll_exc:
                        last_exc = ll_exc
                        failover_count += 1
                        continue

            if not succeeded and self.tokenharbor_key:
                import httpx

                for th_model in self.TOKENHARBOR_FREE_CASCADE:
                    try:
                        used_model = th_model
                        th_resp = httpx.post(
                            "https://tokenharbor.ai/v1/chat/completions",
                            headers={"Authorization": f"Bearer {self.tokenharbor_key}"},
                            json={
                                "model": th_model,
                                "messages": [
                                    {"role": "system", "content": system_prompt},
                                    {"role": "user", "content": user_prompt},
                                ],
                                "temperature": temperature,
                            },
                            timeout=20.0,
                        )
                        if th_resp.status_code == 200:
                            th_data = th_resp.json()
                            text = (th_data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
                            th_usage = th_data.get("usage") or {}
                            prompt_tok = int(th_usage.get("prompt_tokens") or max(1, len(system_prompt + user_prompt) // 4))
                            comp_tok = int(th_usage.get("completion_tokens") or max(1, len(text) // 4))
                            total_tok = prompt_tok + comp_tok
                            last_exc = None
                            succeeded = True
                            break
                        raise RuntimeError(f"TokenHarbor HTTP {th_resp.status_code}: {th_resp.text[:160]}")
                    except Exception as th_exc:
                        last_exc = th_exc
                        failover_count += 1
                        continue

            if not succeeded and self.provider == "google_genai":
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
                if last_exc is not None and self.openrouter_key:
                    import httpx

                    for or_model in self.OPENROUTER_FREE_CASCADE:
                        try:
                            used_model = or_model
                            or_resp = httpx.post(
                                "https://openrouter.ai/api/v1/chat/completions",
                                headers={"Authorization": f"Bearer {self.openrouter_key}"},
                                json={
                                    "model": or_model,
                                    "messages": [
                                        {"role": "system", "content": system_prompt},
                                        {"role": "user", "content": user_prompt},
                                    ],
                                    "temperature": temperature,
                                },
                                timeout=20.0,
                            )
                            if or_resp.status_code == 200:
                                or_data = or_resp.json()
                                text = (or_data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
                                or_usage = or_data.get("usage") or {}
                                prompt_tok = int(or_usage.get("prompt_tokens") or max(1, len(system_prompt + user_prompt) // 4))
                                comp_tok = int(or_usage.get("completion_tokens") or max(1, len(text) // 4))
                                total_tok = prompt_tok + comp_tok
                                last_exc = None
                                break
                        except Exception as or_exc:
                            last_exc = or_exc
                            failover_count += 1
                            continue
                if last_exc is not None:
                    raise last_exc
            elif not succeeded:
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
