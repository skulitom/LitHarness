"""Budget ceilings: §4.2's fourth gate, and the half of §19 Economics that was missing.

Metering was already real — every policy decision records invocations and tokens durably.
Enforcement was zero: `GateKind.BUDGET` and `EventType.BUDGET_EXHAUSTED` existed as
vocabulary with no producer anywhere, and a system that measures its spend and cannot stop
is not budgeted, it is instrumented. §18 keeps budget enforcement absolutely.

**Invocations are a first-class ceiling, not a proxy for tokens.** §15 measured a fixed
per-call harness tax before the prompt is even considered — ~24k input tokens for
`claude -p`, ~14.8k for `codex exec`, and the latter never caches. A budget expressed only
in tokens therefore hides a cost that scales with call *count*: a thousand tiny extraction
calls can cost more than a handful of long ones and look cheaper on every token report.
Both ceilings are enforced, and either one alone can refuse.

**Refusal happens before the money is spent.** A gate that runs after the provider call
records an overrun; it does not prevent one. `check` is called with the *projected* cost of
the call about to be made, using the measured tax as the floor for what that call will
cost even if it returns nothing. Post-hoc recording still happens — that is what makes the
next projection accurate — but the enforcement point is in front.

**Dollars are optional and never the only ceiling.** `claude -p` on a subscription reports
no cost at all (`cost_usd is None`) and Ollama's cost is hardware time, so a
dollars-only budget silently fails open on exactly the providers this system uses by
default. Tokens and invocations always apply; dollars apply when the provider reports them.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

#: Measured per-invocation harness tax, in input tokens, before the prompt is counted
#: (§15, plan/provider-adapters.md). Used as the floor when projecting a call's cost.
HARNESS_TAX_TOKENS: dict[str, int] = {
    "claude_code": 24_000,
    "codex": 14_800,
    "ollama": 0,
    "fake": 0,
}

#: What a call is assumed to cost when the provider is unknown. The maximum of the known
#: taxes rather than zero: an unrecognised provider should make the budget *more* cautious,
#: not less, because the failure of guessing low is spending money you had refused.
DEFAULT_TAX_TOKENS = 24_000


class BudgetExceeded(Exception):
    """A ceiling would be crossed. Raised before the call, never after."""


@dataclass(frozen=True, slots=True)
class BudgetPolicy:
    """Ceilings. `None` means unbounded on that axis, which must be chosen, not defaulted
    into — an unbounded budget is a decision an operator makes, not one a missing config
    makes for them."""

    #: Refuse a single operation projected to cost more than this.
    max_tokens_per_operation: int | None = 200_000
    #: Refuse once the day's recorded spend plus this call's projection would exceed.
    max_tokens_per_day: int | None = 5_000_000
    #: The ceiling token counts cannot express: the per-call harness tax (§15).
    max_invocations_per_day: int | None = 500
    #: Applies only when providers report dollars. Never the sole ceiling.
    max_cost_usd_per_day: float | None = None

    def digest_material(self) -> dict[str, object]:
        return {
            "max_tokens_per_operation": self.max_tokens_per_operation,
            "max_tokens_per_day": self.max_tokens_per_day,
            "max_invocations_per_day": self.max_invocations_per_day,
            "max_cost_usd_per_day": self.max_cost_usd_per_day,
        }


@dataclass(frozen=True, slots=True)
class Spend:
    """Recorded spend over some window. Built from policy decisions, which are the durable
    record of what was actually consumed."""

    invocations: int = 0
    tokens: int = 0
    cost_usd: float = 0.0

    def plus(self, *, invocations: int = 0, tokens: int = 0, cost_usd: float = 0.0) -> Spend:
        return replace(
            self,
            invocations=self.invocations + invocations,
            tokens=self.tokens + tokens,
            cost_usd=self.cost_usd + cost_usd,
        )


def projected_tokens(provider: str, prompt_chars: int, max_output_tokens: int) -> int:
    """Floor estimate of what one call will cost, in tokens.

    Deliberately an over-estimate: the harness tax plus a 4-chars-per-token reading of the
    prompt plus the full output allowance. A projection that guessed low would let the
    ceiling be crossed by the call it was asked to judge, which is the one failure mode
    that makes the whole gate pointless.
    """
    tax = HARNESS_TAX_TOKENS.get(provider, DEFAULT_TAX_TOKENS)
    return tax + (prompt_chars // 4) + max_output_tokens


@dataclass(frozen=True, slots=True)
class BudgetVerdict:
    allowed: bool
    reason: str | None = None
    #: Which ceiling refused, for the recorded gate result.
    ceiling: str | None = None
    projected_tokens: int = 0


def check(
    policy: BudgetPolicy,
    spent_today: Spend,
    *,
    provider: str,
    prompt_chars: int,
    max_output_tokens: int,
) -> BudgetVerdict:
    """Would this call cross a ceiling? Called before spending, not after."""
    projection = projected_tokens(provider, prompt_chars, max_output_tokens)

    if (
        policy.max_tokens_per_operation is not None
        and projection > policy.max_tokens_per_operation
    ):
        return BudgetVerdict(
            False,
            f"operation projected at {projection} tokens exceeds the per-operation ceiling "
            f"of {policy.max_tokens_per_operation}",
            "max_tokens_per_operation",
            projection,
        )

    if (
        policy.max_invocations_per_day is not None
        and spent_today.invocations + 1 > policy.max_invocations_per_day
    ):
        return BudgetVerdict(
            False,
            f"{spent_today.invocations} invocations today already meets the ceiling of "
            f"{policy.max_invocations_per_day}; the per-call harness tax is why this "
            "ceiling exists separately from tokens (§15)",
            "max_invocations_per_day",
            projection,
        )

    if (
        policy.max_tokens_per_day is not None
        and spent_today.tokens + projection > policy.max_tokens_per_day
    ):
        return BudgetVerdict(
            False,
            f"{spent_today.tokens} tokens spent today plus a projected {projection} would "
            f"exceed the daily ceiling of {policy.max_tokens_per_day}",
            "max_tokens_per_day",
            projection,
        )

    if (
        policy.max_cost_usd_per_day is not None
        and spent_today.cost_usd >= policy.max_cost_usd_per_day
    ):
        return BudgetVerdict(
            False,
            f"${spent_today.cost_usd:.2f} spent today meets the daily ceiling of "
            f"${policy.max_cost_usd_per_day:.2f}",
            "max_cost_usd_per_day",
            projection,
        )

    return BudgetVerdict(True, projected_tokens=projection)


__all__ = [
    "DEFAULT_TAX_TOKENS",
    "HARNESS_TAX_TOKENS",
    "BudgetExceeded",
    "BudgetPolicy",
    "BudgetVerdict",
    "Spend",
    "check",
    "projected_tokens",
]
