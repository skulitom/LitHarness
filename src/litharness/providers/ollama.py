"""Ollama: the local daemon, for iterative testing and all mechanical calls.

Two properties make this the right home for the bulk of the work, and both were measured:

**Native JSON-Schema structured output** via the `format` field: a schema in, conforming
JSON out, no fences and no preamble. `claude -p` has no equivalent.

**No per-call harness tax and no cost.** The CLI adapters carry 15-24k input tokens of
their own scaffolding per invocation; this carries the prompt and nothing else. That is why
`plan/provider-adapters.md` §3 routes extraction, gate feedback, summaries and status-block
rendering here *even in production*, not only in tests — at ~1,000 invocations for a draft
the scaffolding would otherwise be several times the actual payload.

`temperature: 0` with a fixed `seed` is the closest thing to determinism a model offers,
which is what the Stage 1 fixture-regeneration tests need.

Reasoning models are a poor fit for the schema-shaped calls: they emit preamble that fights
schema conformance. `qwen3:4b` and `deepseek-r1:8b` are the local examples.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from litharness.providers.base import (
    CompletionRequest,
    CompletionResult,
    ProviderError,
    ProviderFailureKind,
    Usage,
    parse_schema_payload,
    provider_error,
)

#: (url, body, timeout) -> decoded JSON. Injected so the adapter is testable offline.
Transport = Callable[[str, dict[str, Any], float], dict[str, Any]]


def urllib_transport(url: str, body: dict[str, Any], timeout: float) -> dict[str, Any]:
    payload = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        decoded = json.loads(response.read().decode("utf-8"))
    if not isinstance(decoded, dict):
        raise provider_error(
            f"ollama returned a non-object response: {type(decoded).__name__}",
            kind=ProviderFailureKind.MALFORMED_RESPONSE,
            raw=repr(decoded),
        )
    return decoded


@dataclass
class OllamaProvider:
    name: str = "ollama"
    bills: bool = False
    model: str = "qwen3:4b"
    base_url: str = "http://localhost:11434"
    transport: Transport = urllib_transport
    seed: int = 7
    temperature: float = 0.0

    def health(self) -> bool:
        """A real generation round trip, not `GET /api/version`.

        The version endpoint answers "is the daemon up", which is not the question. A model
        that is listed but not pulled, or too large to load, fails only on generate.
        """
        try:
            result = self.complete(
                CompletionRequest(
                    prompt="Reply with the single word OK.",
                    max_output_tokens=16,
                    timeout_seconds=120.0,
                )
            )
        except ProviderError:
            return False
        return bool(result.text.strip())

    def complete(self, request: CompletionRequest) -> CompletionResult:
        messages: list[dict[str, str]] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.prompt})

        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "seed": self.seed,
                "num_predict": request.max_output_tokens,
            },
        }
        if request.schema is not None:
            body["format"] = request.schema

        started = time.monotonic()
        try:
            envelope = self.transport(
                f"{self.base_url}/api/chat", body, request.timeout_seconds
            )
        except urllib.error.HTTPError as error:
            try:
                raw = error.read().decode("utf-8", errors="replace")
            except OSError:
                raw = str(error)
            request_id = error.headers.get("x-request-id") if error.headers else None
            raise provider_error(
                f"{self.name} HTTP {error.code}: {raw[:200]}",
                status=error.code,
                request_id=request_id,
                raw=raw,
            ) from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            kind = (
                ProviderFailureKind.TIMEOUT
                if isinstance(error, TimeoutError)
                else ProviderFailureKind.UNAVAILABLE
            )
            raise provider_error(
                f"{self.name} is unreachable at {self.base_url}: {error}", kind=kind
            ) from error
        except json.JSONDecodeError as error:
            raise provider_error(
                f"{self.name} returned unparseable JSON",
                kind=ProviderFailureKind.MALFORMED_RESPONSE,
            ) from error
        wall_ms = int((time.monotonic() - started) * 1000)

        if "error" in envelope:
            message = f"{self.name} reported: {envelope['error']}"
            raise provider_error(
                message,
                provider_error_type=str(envelope.get("error_type") or "") or None,
                raw=json.dumps(envelope, ensure_ascii=False),
            )

        text = str((envelope.get("message") or {}).get("content", "")).strip()
        return CompletionResult(
            text=text,
            provider=self.name,
            model=str(envelope.get("model", self.model)),
            usage=Usage(
                input_tokens=int(envelope.get("prompt_eval_count", 0)),
                output_tokens=int(envelope.get("eval_count", 0)),
            ),
            parsed=parse_schema_payload(text, request.schema),
            schema_requested=request.schema is not None,
            cost_usd=0.0,  # hardware time only (§15)
            wall_ms=wall_ms,
            raw=envelope,
        )
