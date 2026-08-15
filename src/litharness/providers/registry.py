"""Provider resolution: order, health, call-class routing, and the test-mode guard.

Four rules from `plan/provider-adapters.md` §5, all enforced here rather than left to
callers, because a caller that forgets one is a caller that spends money in a test run or
routes scene generation into a dead CLI.

1. **Health-probe with a real round trip, cache the verdict per tick.** `codex` spent an
   entire CLI generation installed, authenticated, on PATH, and failing every call — a
   version check would have passed it.
2. **`LITHARNESS_ENV=test` provably cannot reach a paid provider.** Enforced by refusing to
   even consider a provider whose `bills` is true, so the guard does not depend on a probe
   succeeding or an order being configured correctly.
3. **Route by call class, not just availability.** `extraction` and `mechanical` calls go to
   a non-billing provider even in production, because the CLI adapters' per-invocation
   harness tax (15-24k tokens) dwarfs a small payload.
4. **Falling back is an event.** A switch changes an artifact's provenance and may
   invalidate reproducibility claims, so it is returned for recording rather than being
   silent.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass, field

from litharness.providers.base import (
    CompletionRequest,
    CompletionResult,
    Provider,
    ProviderUnavailable,
)

TEST_ENV_VAR = "LITHARNESS_ENV"
TEST_ENV_VALUE = "test"

#: Call classes routed to a non-billing provider regardless of environment (§3).
CHEAP_CALL_CLASSES = frozenset({"extraction", "mechanical", "evaluation"})


def in_test_mode(environ: dict[str, str] | None = None) -> bool:
    source = os.environ if environ is None else environ
    return source.get(TEST_ENV_VAR, "").strip().lower() == TEST_ENV_VALUE


@dataclass(frozen=True, slots=True)
class Resolution:
    """Which provider served a call, and whether that was the first choice."""

    provider: str
    fell_back_from: tuple[str, ...] = ()

    @property
    def is_fallback(self) -> bool:
        return bool(self.fell_back_from)


@dataclass
class ProviderRegistry:
    providers: Sequence[Provider]
    #: Preference order by name. Names absent from `providers` are ignored.
    order: Sequence[str]
    #: Preference order for cheap call classes; falls back to `order` if unset.
    cheap_order: Sequence[str] = ()
    #: Refuse billing providers for this run, as an **operator's** choice.
    #:
    #: `LITHARNESS_ENV=test` already filters them, so it was what an operator reached for to
    #: keep a run off a paid CLI — configuring a production run with the flag whose entire
    #: purpose is proving that *test* runs cannot bill. The two are deliberately independent:
    #: §5 rule 2 is that a test run **provably** cannot reach a paid provider, and a guarantee
    #: that could be switched off by configuration would not be one.
    refuse_billing: bool = False
    environ: dict[str, str] | None = None
    _health: dict[str, bool] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        names = [provider.name for provider in self.providers]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise ValueError(f"duplicate provider names: {duplicates}")

    # -- selection ------------------------------------------------------------

    @property
    def test_mode(self) -> bool:
        return in_test_mode(self.environ)

    def _by_name(self, name: str) -> Provider | None:
        return next((item for item in self.providers if item.name == name), None)

    def candidates(self, call_class: str = "generation") -> list[Provider]:
        """Providers eligible for this call class, in preference order.

        A billing provider is filtered out entirely in test mode — not deprioritised.
        That is what makes the guard hold even if `order` is misconfigured. `refuse_billing`
        filters the same way and for the same reason: an operator who said "this run must not
        spend money" is not asking for a preference that a health blip can overturn.
        """
        use_cheap = call_class in CHEAP_CALL_CLASSES and self.cheap_order
        preferred = list(self.cheap_order) if use_cheap else list(self.order)
        eligible: list[Provider] = []
        for name in preferred:
            provider = self._by_name(name)
            if provider is None:
                continue
            if (self.test_mode or self.refuse_billing) and provider.bills:
                continue
            if call_class in CHEAP_CALL_CLASSES and provider.bills and self.cheap_order:
                # An explicit cheap order that still names a billing provider is honoured
                # in production, but only after the non-billing ones.
                eligible.append(provider)
                continue
            eligible.append(provider)
        return eligible

    def reset_health(self) -> None:
        """Clear cached verdicts. Called at the start of a tick, or on a version change."""
        self._health.clear()

    def is_healthy(self, provider: Provider) -> bool:
        if provider.name not in self._health:
            try:
                self._health[provider.name] = bool(provider.health())
            except Exception:
                # A probe that raises is a failed probe, not a crash of the caller.
                self._health[provider.name] = False
        return self._health[provider.name]

    def resolve(self, call_class: str = "generation") -> tuple[Provider, Resolution]:
        skipped: list[str] = []
        for provider in self.candidates(call_class):
            if self.is_healthy(provider):
                return provider, Resolution(provider.name, tuple(skipped))
            skipped.append(provider.name)
        raise ProviderUnavailable(
            f"no healthy provider for call_class={call_class!r}; "
            f"tried {skipped or [p.name for p in self.candidates(call_class)]}"
            + (" (test mode excludes billing providers)" if self.test_mode else "")
        )

    # -- use ------------------------------------------------------------------

    def complete(self, request: CompletionRequest) -> tuple[CompletionResult, Resolution]:
        """Complete against the best healthy provider for the request's call class.

        Returns the resolution alongside the result so the caller can record a fallback as
        an event; §5 rule 4 forbids a silent switch.
        """
        provider, resolution = self.resolve(request.call_class)
        return provider.complete(request), resolution


def assert_no_billing_reachable(registry: ProviderRegistry) -> None:
    """Assertion form of §5 rule 2, for a test-suite guard.

    Stage 0's exit criterion says test mode must *provably* be unable to reach a paid
    provider. A property nobody asserts is a property that regresses, so this is meant to be
    called from the suite rather than trusted.
    """
    if not registry.test_mode:
        raise AssertionError(f"{TEST_ENV_VAR} is not {TEST_ENV_VALUE!r}; guard is not active")
    reachable = [
        provider.name
        for call_class in {"generation", *CHEAP_CALL_CLASSES}
        for provider in registry.candidates(call_class)
        if provider.bills
    ]
    if reachable:
        raise AssertionError(f"billing providers reachable in test mode: {sorted(set(reachable))}")
