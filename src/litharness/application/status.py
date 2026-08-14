"""What an operator needs to answer "is it alive, and is anything stuck".

§19 Autonomy requires that "parked units and exceptions are visible and bounded". Before
this module the only job query was `load_job(job_id)`, which requires already knowing the
id of the job you have not heard about — so the clause was unanswerable by construction,
and the only way to inspect a running system was to open the SQLite file by hand.

Two design notes.

**Liveness is derived from the last tick, not from a heartbeat table.** `tick_records`
already stores `started_at` and has an index on it, and nothing read either. A separate
heartbeat would be a second source of truth for the same fact, and the two would
eventually disagree.

**The instance lease is reported with its expiry rather than as a boolean.** A crashed
holder still owns its lease for the full duration, so "is someone leading" answers yes for
five minutes after the process died. Showing the expiry lets a human see that themselves;
collapsing it to a boolean would report a corpse as healthy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from litharness.application.conductor import DEFAULT_SCOPE
from litharness.application.ports import StatusStore
from litharness.domain.budget import BudgetPolicy, Spend
from litharness.domain.directives import DirectiveStatus
from litharness.domain.jobs import JobStatus


@dataclass(frozen=True, slots=True)
class Status:
    now: float
    paused: bool
    last_tick_at: float | None
    last_tick_outcome: str | None
    seconds_since_tick: float | None
    lease_holder: str | None
    lease_expires_in: float | None
    jobs: dict[str, int] = field(default_factory=dict)
    outbox: dict[str, int] = field(default_factory=dict)
    unread_directives: int = 0
    open_exceptions: int = 0
    #: Findings a blocking gate would refuse a candidate on. Counted rather than listed,
    #: because `litharness findings` is where they are read — but *counted here*, because a
    #: book that stopped advancing and a book that is blocked on one dismissable finding look
    #: identical on every other line of this report.
    blocking_findings: int = 0
    digest: dict[str, int] = field(default_factory=dict)
    #: §19 Economics: "the operator can see spend vs. plan at any tick".
    spend: Spend = field(default_factory=Spend)
    budget: BudgetPolicy = field(default_factory=BudgetPolicy)

    @property
    def needs_attention(self) -> int:
        """Units that stopped without doing the work. The number to watch."""
        return (
            self.jobs.get(JobStatus.POISONED.value, 0)
            + self.jobs.get(JobStatus.PARKED.value, 0)
            + self.open_exceptions
            # A blocking finding is a unit that will keep failing until a human closes it or
            # a repair clears it, so it belongs in the number an operator watches — not in a
            # separate one they have to remember to look at.
            + self.blocking_findings
        )

    @property
    def stalled(self) -> bool:
        """No tick within four cadences. Never ticked at all counts as stalled."""
        if self.seconds_since_tick is None:
            return True
        return self.seconds_since_tick > 4 * 300.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "paused": self.paused,
            "stalled": self.stalled,
            "last_tick_at": self.last_tick_at,
            "last_tick_outcome": self.last_tick_outcome,
            "seconds_since_tick": self.seconds_since_tick,
            "lease_holder": self.lease_holder,
            "lease_expires_in": self.lease_expires_in,
            "jobs": self.jobs,
            "needs_attention": self.needs_attention,
            "outbox": self.outbox,
            "unread_directives": self.unread_directives,
            "open_exceptions": self.open_exceptions,
            "blocking_findings": self.blocking_findings,
            "digest": self.digest,
            "spend": {
                "invocations": self.spend.invocations,
                "tokens": self.spend.tokens,
                "cost_usd": self.spend.cost_usd,
            },
            "budget": self.budget.digest_material(),
        }

    def _against_plan(self) -> str:
        """"Spend vs. plan" is the §19 Economics wording, so show the plan, not just the
        spend. A bare number cannot be read as close-to-the-limit or nowhere-near it."""
        parts = []
        if self.budget.max_invocations_per_day is not None:
            parts.append(f"{self.spend.invocations}/{self.budget.max_invocations_per_day} calls")
        if self.budget.max_tokens_per_day is not None:
            parts.append(f"{self.spend.tokens}/{self.budget.max_tokens_per_day} tokens")
        return f"  [{'; '.join(parts)}]" if parts else "  [unbounded]"

    def render(self) -> str:
        lines = [
            f"state           {'PAUSED' if self.paused else 'running'}"
            f"{'  STALLED' if self.stalled else ''}",
            f"last tick       {self.last_tick_outcome or 'never'}"
            + (
                f"  ({self.seconds_since_tick:.0f}s ago)"
                if self.seconds_since_tick is not None
                else ""
            ),
            f"leader          {self.lease_holder or 'none'}"
            + (
                f"  (expires in {self.lease_expires_in:.0f}s)"
                if self.lease_expires_in is not None
                else ""
            ),
            f"jobs            {self.jobs or '{}'}",
            f"needs attention {self.needs_attention}",
            f"outbox          {self.outbox or '{}'}",
            f"unread          {self.unread_directives} directive(s)",
            f"exceptions      {self.open_exceptions} open",
            f"findings        {self.blocking_findings} blocking",
            f"digest today    {self.digest or '{}'}",
            f"spend today     {self.spend.invocations} call(s), "
            f"{self.spend.tokens} tokens"
            + (f", ${self.spend.cost_usd:.2f}" if self.spend.cost_usd else "")
            + self._against_plan(),
        ]
        return "\n".join(lines)


def collect(
    store: StatusStore,
    now: float,
    *,
    scope: str = DEFAULT_SCOPE,
    budget: BudgetPolicy | None = None,
) -> Status:
    last = store.last_tick()
    holder, expires = store.instance_lease(scope)
    day = datetime.fromtimestamp(now, tz=UTC).date().isoformat()
    return Status(
        now=now,
        paused=store.is_paused(),
        last_tick_at=last["started_at"] if last else None,
        last_tick_outcome=last["outcome"] if last else None,
        seconds_since_tick=(now - last["started_at"]) if last else None,
        lease_holder=holder,
        lease_expires_in=(expires - now) if expires is not None else None,
        jobs=store.job_counts_by_status(),
        outbox=store.outbox_counts_by_state(),
        unread_directives=len(store.directives_by_status(DirectiveStatus.RECEIVED)),
        open_exceptions=len(store.open_exceptions()),
        blocking_findings=sum(
            1
            for book_id, branch_id, _ in store.branches()
            for item in store.findings(book_id, branch_id, open_only=True)
            if item.blocks
        ),
        digest=store.digest(day),
        spend=store.spend_on(day),
        budget=budget or BudgetPolicy(),
    )


__all__ = ["Status", "collect"]
