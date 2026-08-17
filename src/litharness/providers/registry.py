"""Resolution for the one pinned provider: health verdicts and the test-mode guard.

One provider serves every call class. §1a.5 requires a frontier generator, and a silent
mid-book fallback to a weaker model is a quality defect, not resilience — so the fallback
chain, the call-class routing, and the operator's preference levers are gone, and an
unhealthy provider parks the unit rather than degrading the book. What survives of
`plan/provider-adapters.md` §5, adjusted to the pinned world:

1. **Health-probe with a real round trip, not a version check.** `codex` spent an entire
   CLI generation installed, authenticated, on PATH, and failing every call — a version
   check would have passed it. The verdict cache is asymmetric; see `reset_health`.
2. **`LITHARNESS_ENV=test` provably cannot reach a paid provider.** Enforced by refusal
   rather than filtering: with one provider there is nothing to substitute, and this
   project's recorded lesson is to never substitute silently. `resolve` raises
   `BillingGuardViolation` *before* any probe, because the probe itself is a billed call.
3. Route-by-call-class died with provider plurality. `CompletionRequest.call_class`
   stays as provenance: it records what kind of work a call was, not where it went.
4. **There is no fallback to record.** An unhealthy provider raises `ProviderUnavailable`,
   which the conductor's transient/parked branches turn into a requeue or a park. The
   book waits; it never degrades.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from litharness.domain.generation import CompletionRequest, CompletionResult, Resolution
from litharness.providers.base import Provider, ProviderUnavailable

TEST_ENV_VAR = "LITHARNESS_ENV"
TEST_ENV_VALUE = "test"


def in_test_mode(environ: dict[str, str] | None = None) -> bool:
    source = os.environ if environ is None else environ
    return source.get(TEST_ENV_VAR, "").strip().lower() == TEST_ENV_VALUE


class BillingGuardViolation(RuntimeError):
    """A test run reached for a provider that bills. Raised, never filtered.

    The plural registry *filtered* billing providers out of the candidate list under
    `LITHARNESS_ENV=test`, which preserved Stage 0's exit clause by substitution: the run
    quietly proceeded on whatever non-billing provider remained. With one pinned provider
    there is nothing to substitute, and substituting silently is the failure mode this
    project keeps refusing — so the guard is now a loud refusal. A suite that trips this
    has a wiring defect, and the defect surfaces as this error naming the guard.
    """


@dataclass
class ProviderRegistry:
    """The single pinned provider, plus its cached health verdict.

    Constructor takes exactly one `Provider`. `resolve` returns it when it is healthy,
    raises `ProviderUnavailable` when it is not, and raises `BillingGuardViolation`
    before either when `LITHARNESS_ENV=test` and the provider bills.
    """

    provider: Provider
    environ: dict[str, str] | None = None
    #: None = unprobed; True/False = the cached verdict. Asymmetric lifetime — see
    #: `reset_health`.
    _health: bool | None = field(default=None, repr=False)

    # -- selection ------------------------------------------------------------

    @property
    def test_mode(self) -> bool:
        return in_test_mode(self.environ)

    def reset_health(self) -> None:
        """Clear a cached *negative* verdict. A positive verdict lasts the process.

        Deliberately asymmetric, because two constraints pull in opposite directions:

        * **A billed probe must not be re-paid on every tick of a resident session.**
          The pinned provider's health check is a real, metered round trip that no
          budget ceiling sees (§56.2 measured it at $0.34 cold), so a positive verdict,
          once bought, is kept for the life of the process.
        * **One failed probe must not kill the provider for the life of the process**
          (§16's dead-forever bug). A negative verdict is cleared here, so the next tick
          re-probes and an outage can heal.

        Keeps its name and its `TextGenerator` port slot; the conductor still calls it
        once per tick.
        """
        if self._health is False:
            self._health = None

    def is_healthy(self) -> bool:
        if self._health is None:
            try:
                self._health = bool(self.provider.health())
            except Exception:
                # A probe that raises is a failed probe, not a crash of the caller.
                self._health = False
        return self._health

    def resolve(self, call_class: str = "generation") -> tuple[Provider, Resolution]:
        """The pinned provider, if this run may use it and it is healthy.

        The billing guard runs before the health probe on purpose: the probe is itself
        a billed invocation, so a test run must not even pay for the health check.
        """
        self._refuse_billing_in_test_mode()
        if self.is_healthy():
            return self.provider, Resolution(self.provider.name)
        raise ProviderUnavailable(
            f"provider {self.provider.name!r} is unhealthy and no fallback exists "
            f"(call_class={call_class!r}); the unit parks or requeues rather than "
            "degrading to a weaker generator"
        )

    def _refuse_billing_in_test_mode(self) -> None:
        if self.test_mode and self.provider.bills:
            raise BillingGuardViolation(
                f"{TEST_ENV_VAR}={TEST_ENV_VALUE} forbids reaching {self.provider.name!r}, "
                "which bills; a test run must wire FakeProvider, never a paid provider"
            )

    # -- use ------------------------------------------------------------------

    def complete(self, request: CompletionRequest) -> tuple[CompletionResult, Resolution]:
        """Complete against the pinned provider, with the resolution for the record.

        The `Resolution` is vestigial in the pinned world — `fell_back_from` is always
        empty — but it stays on the return so decision provenance keeps its schema.
        """
        provider, resolution = self.resolve(request.call_class)
        return provider.complete(request), resolution


def assert_no_billing_reachable(registry: ProviderRegistry) -> None:
    """Assertion form of §5 rule 2, for a test-suite guard.

    Stage 0's exit criterion says test mode must *provably* be unable to reach a paid
    provider. The plural registry proved it by filtering; the pinned one proves it by
    refusal, so this asserts the raise: a registry holding a billing provider must
    refuse to resolve it. A property nobody asserts is a property that regresses, so
    this is meant to be called from the suite rather than trusted.
    """
    if not registry.test_mode:
        raise AssertionError(f"{TEST_ENV_VAR} is not {TEST_ENV_VALUE!r}; guard is not active")
    if not registry.provider.bills:
        return
    try:
        registry.resolve()
    except BillingGuardViolation:
        return
    raise AssertionError(
        f"billing provider {registry.provider.name!r} is reachable in test mode"
    )
