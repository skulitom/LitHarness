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

import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

#: ```json ... ``` or bare ``` ... ``` — what `claude -p` wraps JSON in.
_FENCE = re.compile(r"^\s*```(?:json|JSON)?\s*\n(.*?)\n?\s*```\s*$", re.DOTALL)


class ProviderError(Exception):
    """The adapter could not complete a round trip. Distinct from a bad-shaped answer."""


class ProviderUnavailable(ProviderError):
    """The tool is absent, unauthenticated, or failing its health probe."""


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
