"""The provider seam: one request shape, one result shape, four implementations.

Design recorded in `plan/provider-adapters.md`; this is that contract in code. Two things
about it are load-bearing and easy to get wrong.

**`bills` is part of the provider's identity, not a config flag.** Whether an adapter
consumes paid quota decides whether a test run may touch it, and the registry enforces
that (`registry.py`). Making it a property of the adapter means a new provider cannot be
added without answering the question.

**Structured output is a per-adapter capability, not a shared one.** Ollama enforces a
JSON Schema natively; `codex exec` does too via `--output-schema`; `claude -p` does not —
it returns fenced markdown, so its adapter strips fences, parses, and reports failure as
`parsed is None` rather than raising. A parse failure is a *shape-gate* result (§4.2 ladder
step 1) that earns a bounded retry with structured feedback, not an exception that kills
the unit of work.

Every result carries the raw provider envelope, because §2 requires each generated claim to
be traceable to exact inputs and tool/model versions, and the envelope is where the version
actually lives.
"""

from __future__ import annotations

import enum
import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from litharness.domain.failures import OperationalFailure, ParkedFailure, TransientFailure

#: ```json ... ``` or bare ``` ... ``` — what `claude -p` wraps JSON in.
_FENCE = re.compile(r"^\s*```(?:json|JSON)?\s*\n(.*?)\n?\s*```\s*$", re.DOTALL)


class ProviderFailureKind(enum.StrEnum):
    """Provider-neutral causes with different recovery policies."""

    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    OVERLOADED = "overloaded"
    SERVER_ERROR = "server_error"
    AUTH = "auth"
    INVALID_REQUEST = "invalid_request"
    CONTEXT_OVERFLOW = "context_overflow"
    REFUSAL = "refusal"
    SAFETY = "safety"
    MALFORMED_RESPONSE = "malformed_response"
    ABORTED = "aborted"
    UNKNOWN = "unknown"

    @property
    def retry_later(self) -> bool:
        return self in {
            ProviderFailureKind.UNAVAILABLE,
            ProviderFailureKind.TIMEOUT,
            ProviderFailureKind.RATE_LIMIT,
            ProviderFailureKind.OVERLOADED,
            ProviderFailureKind.SERVER_ERROR,
            ProviderFailureKind.ABORTED,
        }

    @property
    def needs_intervention(self) -> bool:
        return self in {
            ProviderFailureKind.AUTH,
            ProviderFailureKind.INVALID_REQUEST,
            ProviderFailureKind.CONTEXT_OVERFLOW,
        }


_CONTEXT_OVERFLOW = (
    re.compile(r"prompt is too long", re.IGNORECASE),
    re.compile(r"request_too_large", re.IGNORECASE),
    re.compile(r"exceeds? the context window", re.IGNORECASE),
    re.compile(r"input token count.*exceeds the maximum", re.IGNORECASE),
    re.compile(r"maximum (?:prompt|context) length", re.IGNORECASE),
    re.compile(r"context[_ ](?:window|length).*exceed", re.IGNORECASE),
    re.compile(r"prompt too long", re.IGNORECASE),
    re.compile(r"token limit exceeded", re.IGNORECASE),
)


def classify_provider_failure(
    message: str, *, status: int | None = None, provider_error_type: str | None = None
) -> ProviderFailureKind:
    """Classify without erasing the provider's own diagnostic.

    Status and provider type lead; message matching is the fallback needed for CLI tools,
    which often expose no structured exception at all.
    """
    combined = f"{provider_error_type or ''} {message}".lower()
    if any(pattern.search(combined) for pattern in _CONTEXT_OVERFLOW):
        return ProviderFailureKind.CONTEXT_OVERFLOW
    if status == 429 or "rate_limit" in combined or "rate limit" in combined:
        return ProviderFailureKind.RATE_LIMIT
    if status == 529 or "overloaded" in combined:
        return ProviderFailureKind.OVERLOADED
    if status in {401, 403} or re.search(
        r"\b(auth(?:entication)?|unauthori[sz]ed|forbidden|credential|api.?key)\b", combined
    ):
        return ProviderFailureKind.AUTH
    if "safety" in combined or "content filter" in combined or "prohibited" in combined:
        return ProviderFailureKind.SAFETY
    if "refusal" in combined or "refused to respond" in combined:
        return ProviderFailureKind.REFUSAL
    if status in {400, 404, 413, 422} or "invalid_request" in combined or "not found" in combined:
        return ProviderFailureKind.INVALID_REQUEST
    if status is not None and status >= 500:
        return ProviderFailureKind.SERVER_ERROR
    if "server_error" in combined or "service unavailable" in combined:
        return ProviderFailureKind.SERVER_ERROR
    return ProviderFailureKind.UNKNOWN


class ProviderError(OperationalFailure):
    """The adapter could not complete a round trip. Distinct from a bad-shaped answer."""

    def __init__(
        self,
        message: str,
        *,
        kind: ProviderFailureKind = ProviderFailureKind.UNKNOWN,
        provider_error_type: str | None = None,
        status: int | None = None,
        request_id: str | None = None,
        retry_after_seconds: float | None = None,
        raw: str | None = None,
    ) -> None:
        self.kind = kind
        self.provider_error_type = provider_error_type
        self.status = status
        self.request_id = request_id
        self.retry_after_seconds = retry_after_seconds
        self.raw = raw[:2000] if raw else None
        super().__init__(
            message,
            classification=kind.value,
            details={
                "provider_error_type": provider_error_type,
                "status": status,
                "request_id": request_id,
                "retry_after_seconds": retry_after_seconds,
                "raw": self.raw,
            },
        )


class RetryableProviderError(ProviderError, TransientFailure):
    """No candidate was returned and the same call may work later."""


class BlockedProviderError(ProviderError, ParkedFailure):
    """Retrying unchanged cannot work; configuration or packet size must change."""


def provider_error(
    message: str,
    *,
    kind: ProviderFailureKind | None = None,
    provider_error_type: str | None = None,
    status: int | None = None,
    request_id: str | None = None,
    retry_after_seconds: float | None = None,
    raw: str | None = None,
) -> ProviderError:
    """Construct the subtype whose recovery semantics match the classified cause."""
    resolved = kind or classify_provider_failure(
        message, status=status, provider_error_type=provider_error_type
    )
    error_type: type[ProviderError]
    if resolved.retry_later:
        error_type = RetryableProviderError
    elif resolved.needs_intervention:
        error_type = BlockedProviderError
    else:
        error_type = ProviderError
    return error_type(
        message,
        kind=resolved,
        provider_error_type=provider_error_type,
        status=status,
        request_id=request_id,
        retry_after_seconds=retry_after_seconds,
        raw=raw,
    )


class ProviderUnavailable(RetryableProviderError):
    """The tool is absent, unauthenticated, or failing its health probe.

    Also a `TransientFailure`: this is raised *before* any work is attempted, so nothing
    about the unit of work is wrong and its attempt budget must not be charged. See
    `domain/failures.py` for why that distinction is load-bearing rather than tidy."""

    def __init__(self, message: str) -> None:
        super().__init__(message, kind=ProviderFailureKind.UNAVAILABLE)


@dataclass(frozen=True, slots=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    #: Reported separately by codex. Counted into the budget, because at its default
    #: reasoning effort it is not small.
    reasoning_tokens: int = 0

    @property
    def billable_input(self) -> int:
        """Full-price input: cache reads are ~0.1x and are excluded from this figure."""
        return self.input_tokens + self.cache_write_tokens

    @property
    def total(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_write_tokens
            + self.reasoning_tokens
        )


@dataclass(frozen=True, slots=True)
class CompletionRequest:
    prompt: str
    system: str | None = None
    #: JSON Schema. None means free text.
    schema: dict[str, Any] | None = None
    max_output_tokens: int = 4096
    #: Frozen generation profile name, recorded in provenance.
    profile: str = "default"
    timeout_seconds: float = 300.0
    #: Call class, used by the registry to route mechanical work to cheap providers even in
    #: production (see plan/provider-adapters.md §3).
    call_class: str = "generation"


@dataclass(frozen=True, slots=True)
class CompletionResult:
    text: str
    provider: str
    model: str
    usage: Usage = field(default_factory=Usage)
    #: Validated against the request's schema. None when there was no schema, or when the
    #: answer did not conform — callers distinguish via `schema_requested`.
    parsed: dict[str, Any] | None = None
    schema_requested: bool = False
    #: None when the provider cannot report cost (subscription quota rather than dollars).
    cost_usd: float | None = None
    wall_ms: int = 0
    #: Always 1 here; the budget governor sums these because the per-call harness tax
    #: scales with invocation count, not tokens (§15).
    invocations: int = 1
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def conforms(self) -> bool:
        """False only when a schema was requested and the answer failed to satisfy it."""
        return not self.schema_requested or self.parsed is not None


@runtime_checkable
class Provider(Protocol):
    name: str
    #: True if a call consumes paid quota or a paid subscription.
    bills: bool

    def health(self) -> bool:
        """A real round trip against the configured model. Not a version check.

        `codex` spent an entire CLI generation installed, authenticated, on PATH, and
        failing every call with an empty output file — a `--version` probe would have
        passed it and routed scene generation into a dead provider.
        """
        ...

    def complete(self, request: CompletionRequest) -> CompletionResult: ...


def strip_fences(text: str) -> str:
    """Unwrap a fenced code block if the whole answer is one. Otherwise return as-is."""
    match = _FENCE.match(text)
    return match.group(1) if match else text.strip()


def parse_schema_payload(text: str, schema: dict[str, Any] | None) -> dict[str, Any] | None:
    """Best-effort structured parse. Returns None on any failure — never raises.

    Validation is intentionally shallow: required keys and top-level types. A full JSON
    Schema validator belongs in the gate ladder, which already has one via the contracts
    package; duplicating it here would give two places for the shape rules to drift.
    """
    if schema is None:
        return None
    try:
        payload = json.loads(strip_fences(text))
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    for key in schema.get("required", []):
        if key not in payload:
            return None
    properties = schema.get("properties", {})
    for key, spec in properties.items():
        if key not in payload:
            continue
        expected = spec.get("type")
        if expected and not _type_matches(payload[key], expected):
            return None
    return payload


_JSON_TYPES: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
    "null": type(None),
}


def _type_matches(value: Any, expected: str) -> bool:
    kind = _JSON_TYPES.get(expected)
    if kind is None:
        return True
    if expected == "integer" and isinstance(value, bool):
        return False  # bool is an int subclass; a schema asking for integer means integer
    return isinstance(value, kind)
