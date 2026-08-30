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

import json
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
class Sampler:
    """How the model decodes. Per-request, because it is not one setting for all work.

    **Every field is `None` by default and `None` means "the adapter's own default".** That
    is what lets a request carry no opinion at all, which every mechanical call should: an
    adapter that reads `None` as "0" would silently make a schema-shaped call creative.

    **Why this exists at all, measured rather than argued.** The sampler used to be
    constructor state on `OllamaProvider` — `temperature=0.0, seed=7` for every call of every
    kind in the process — and three things follow from that which the code did not say:

    - **The seed is inert at `temperature=0.0`.** Greedy decoding has nothing to sample, so
      the seed selects nothing. Measured: three seeds (7, 101, 202) against one unchanged
      request returned byte-identical text on both `llama3.2` and `phi4`. The fixed seed was
      never buying the determinism `plan/provider-adapters.md` §4.3 credits it with; the
      `temperature=0.0` beside it was doing all of the work.
    - **And `temperature=0.0` does not buy it either.** The same request sent twice is *not*
      byte-identical: `llama3.2` returned 245 then 279 words, a 12% swing, with every later
      draw of that same request landing on 279. The first draw against a prompt comes from a
      different state than the rest. So "the closest thing to determinism a model offers" is
      a claim this project has now measured and it is false at the only precision that would
      matter — which is why the `@live` tests that compare one draw per arm compare warm-up.
    - **Greedy decoding made the retry ladder a no-op.** The prompt is frozen onto the job
      payload at plan time and re-read verbatim on every attempt, so a refused draft was
      regenerated from byte-identical inputs and met the identical refusal until the attempt
      budget poisoned the unit. Three model calls to receive one answer three times.
    """

    #: Above zero, the seed starts selecting; at zero it selects nothing. Move them together.
    temperature: float | None = None
    top_p: float | None = None
    #: Deterministic **given** a temperature. Derive it from content rather than pinning a
    #: constant, so the same job replays to the same prose and two different scenes do not
    #: draw the same sample path. See `application/handlers.py`.
    seed: int | None = None
    repeat_penalty: float | None = None

    def merged_over(self, **defaults: float | int | None) -> dict[str, float | int]:
        """This sampler's opinions on top of an adapter's defaults, `None` dropped.

        Returns only keys with a value, so an adapter can splat it into a wire payload
        without asserting a default it does not hold.
        """
        merged = dict(defaults)
        for name in ("temperature", "top_p", "seed", "repeat_penalty"):
            value = getattr(self, name)
            if value is not None:
                merged[name] = value
        return {key: value for key, value in merged.items() if value is not None}


#: The prose sampler. **Not measured, and the constant says so** — this project has measured
#: what `temperature=0.0` costs (above) and not what any positive value buys. It is set where
#: it is because the retry ladder needs *some* headroom to produce a second answer and because
#: `repeated_span` exists to catch a run that emitted a 28-word paragraph byte-identical in
#: two scenes under greedy decoding. Whether raising it reduces that is the first question
#: Book Zero can answer, and `craft.repeated_span.v0` is the instrument that answers it.
PROSE = Sampler(temperature=0.7, top_p=0.9, repeat_penalty=1.05)

#: Schema-shaped work stays greedy. Conformance is the point of an extraction call and
#: creativity is the failure mode, so the one place the old global was right keeps it.
MECHANICAL = Sampler(temperature=0.0)

#: Resolution from the frozen profile name a request already carries. A profile was a string
#: recorded in provenance that no adapter read; making it *mean* the sampler is what stops
#: decoding settings from being scattered at call sites where no decision record can see them.
PROFILES: dict[str, Sampler] = {"default": PROSE, "prose": PROSE, "mechanical": MECHANICAL}


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
    #: Which model to ask the resolved provider for. **`None` means the adapter's own**, which
    #: is `Sampler`'s rule at a second address and for the same reason: a request that has no
    #: opinion must not assert one, and every call that existed before this field carries none.
    #:
    #: **It is a model and not a provider, and that is the whole of what it can do.** §5's
    #: pinned registry serves one provider for every call class on §1a's grounds — a silent
    #: mid-book fallback to a weaker generator is a quality defect, not resilience — and this
    #: does not reopen that: it names a model *on* the resolved provider, so a role wanting a
    #: stronger one gets it without the call-class routing the registry deleted coming back.
    #: `CompletionResult.model` still reports what actually wrote the text, which is
    #: `_resolved_model`'s job and is not this field's word for it.
    model: str | None = None
    #: How to decode. `None` leaves it to the adapter, which is what every call site that
    #: has no opinion should do — including every existing one, so this field is additive.
    sampler: Sampler | None = None

    #: Tools this call may use, in the transport's own permission vocabulary. **Empty is the
    #: default and empty means a single-shot completion**, which is what every call in this
    #: system was and what `providers/cli.py` spells `--allowed-tools ''` for a stated
    #: reason: without it the transport is an agent that can read and write files outside
    #: the revision store (§5).
    #:
    #: **A non-empty allowance is that rule kept rather than dropped.** §5 says no subsystem
    #: mutates canon *directly*; a named command that goes through the store, validates, and
    #: mints at PROPOSED is the sanctioned path rather than an exception to it. So the
    #: allowance is per-request and written narrowly — a drafting call still passes nothing,
    #: and only a role that manages the world asks for the world's own commands.
    allowed_tools: tuple[str, ...] = ()

    @property
    def schema_instruction(self) -> str:
        """The exact schema instruction added by the CLI transport."""
        if self.schema is None:
            return ""
        return (
            "Reply with a single JSON object conforming to this schema and nothing "
            "else — no prose, no code fence:\n" + json.dumps(self.schema, sort_keys=True)
        )

    @property
    def effective_system(self) -> str:
        """Role framing plus transport-added instructions the model actually receives."""
        return "\n\n".join(part for part in (self.system or "", self.schema_instruction) if part)

    @property
    def input_chars(self) -> int:
        """Auditable input size used by the budget governor.

        Tool names are included because enabling one changes the transport input.  Providers
        may attach their own tool descriptions, so this is a lower bound for tool-using calls;
        every current prose and reader request has an empty allowance.
        """
        return len(self.prompt) + len(self.effective_system) + len(",".join(self.allowed_tools))


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
    "MECHANICAL",
    "PROFILES",
    "PROSE",
    "CompletionRequest",
    "CompletionResult",
    "Resolution",
    "Sampler",
    "Usage",
]
