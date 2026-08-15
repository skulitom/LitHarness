"""The generation vocabulary: what a model call asks for, and what came back.

**Value objects only — no I/O, no provider, no transport.** They live in `domain` for the
same reason `domain/failures.py` does, and CONTRIBUTING already stated the principle before
this module existed: providers "may use only its own package plus the domain failure
vocabulary". This is the request/result half of that vocabulary, moved to sit beside it.

**Why they moved, which is the whole point of the module.** `application` used to import
`CompletionRequest` and `ProviderRegistry` from `providers` in three handlers, while
`conductor.py` typed the very same registry *structurally* to avoid exactly that import. The
direction was decided and enforced in one place out of four. With the vocabulary here,
`application` states what it needs as `ports.TextGenerator` and imports no provider at all,
so `tests/test_architecture.py` can drop `providers` from the application row and the
inversion becomes a rule rather than an intention.

Nothing here knows a provider exists. `providers/base.py` re-exports these names so provider
authors still have one import site, and `Provider` itself stays there — it is the
implementer's contract, and implementers are what `providers` is for.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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


@dataclass(frozen=True, slots=True)
class Resolution:
    """Which provider served a call, and whether that was the first choice.

    Returned alongside every result rather than logged inside the registry, because §5 rule 4
    forbids a silent switch: the caller records the fallback as an event, so it cannot happen
    without appearing on the record.
    """

    provider: str
    fell_back_from: tuple[str, ...] = ()

    @property
    def is_fallback(self) -> bool:
        return bool(self.fell_back_from)


__all__ = [
    "CompletionRequest",
    "CompletionResult",
    "Resolution",
    "Usage",
]
