"""What an operator needs to answer "is anything stuck".

§19 Autonomy requires that "parked units and exceptions are visible and bounded". Before
this module the only job query was `load_job(job_id)`, which requires already knowing the
id of the job you have not heard about — so the clause was unanswerable by construction,
and the only way to inspect a running system was to open the SQLite file by hand.

This report is what the operator driving the foreground session reads between ticks; it is
not an external monitor. Liveness is the session itself, so nothing here derives "alive"
from a heartbeat or a cadence.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from litharness.application.ports import StatusStore
from litharness.domain.budget import BudgetPolicy, Spend
from litharness.domain.directives import DirectiveStatus
from litharness.domain.extraction import speaks_system_voice
from litharness.domain.jobs import JobStatus


@dataclass(frozen=True, slots=True)
class BlockedBook:
    """One book the planner refuses to advance, and the sentence it refuses with.

    The reason is `plan_progress`'s own `blocked_reason`, carried verbatim rather than
    recomputed: §155.2's report-then-gate shape holds only if the report and the gate say
    the same words, and a second computation here is a second answer that can drift.
    """

    book_id: str
    branch_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class Status:
    now: float
    jobs: dict[str, int] = field(default_factory=dict)
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
    #: Books whose canon states game state on the page while no continuity evaluator is
    #: configured — so the six-rule LitRPG pack is not running on them.
    #:
    #: **Reported rather than defaulted, which is §30's decision.** Inventing a value nobody
    #: agreed to is worse than a visible silence. And there is nowhere to default *to*: the
    #: pack lives in a sibling checkout whose path is this machine's, not this package's,
    #: so a hardcoded default would be wrong everywhere but one desk.
    #:
    #: What was not acceptable is the silence. `stats.ceiling.v0` and its five siblings are
    #: built and green, `--continuity-evaluator-command` defaults to unset, and §52, §54.1,
    #: §55.1 and §56 all drafted without them — §56.5 measured the cost, an `MP 6/4` reaching
    #: accepted canon across twelve ACCEPT decisions and zero findings. A run missing the
    #: genre's best deterministic quality claim now says so on the line an operator reads.
    unchecked_system_voice_books: int = 0
    #: Books the planner refuses to advance — no head revision, no premise, a template
    #: mismatch, or the genre floor — each with `plan_progress`'s own reason. Listed rather
    #: than counted, unlike `blocking_findings`: no other command reads a blocked reason
    #: (`litharness findings` is where findings are read), so a count with no sentence
    #: behind it would leave the operator exactly where pilot 14 §7 found them — a floored
    #: book returning `no_work` under a report reading `jobs {}` / `needs attention 0`,
    #: indistinguishable from a board at rest. A blocked book enqueues no job, opens no
    #: exception and raises no finding, so it is invisible to every other line here (§159).
    blocked: tuple[BlockedBook, ...] = ()

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
            # The same argument one door along: a blocked book is refused by the selector
            # every tick until somebody seeds or imports what it is missing, and it appears
            # in no other count — which is how pilot 14 §7 read `needs attention 0` off a
            # board that had stopped.
            + len(self.blocked)
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "jobs": self.jobs,
            "needs_attention": self.needs_attention,
            "unread_directives": self.unread_directives,
            "open_exceptions": self.open_exceptions,
            "blocking_findings": self.blocking_findings,
            "blocked": [
                {"book_id": item.book_id, "branch_id": item.branch_id, "reason": item.reason}
                for item in self.blocked
            ],
            "unchecked_system_voice_books": self.unchecked_system_voice_books,
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
            f"jobs            {self.jobs or '{}'}",
            f"needs attention {self.needs_attention}",
            f"unread          {self.unread_directives} directive(s)",
            f"exceptions      {self.open_exceptions} open",
            f"findings        {self.blocking_findings} blocking",
            # One line per blocked book and none when nothing is blocked, the rules-pack
            # line's argument: a line that is always there is a line nobody reads.
            *(
                f"blocked         {item.book_id}/{item.branch_id}: {item.reason}"
                for item in self.blocked
            ),
            f"digest today    {self.digest or '{}'}",
            *(
                [
                    f"rules pack      NOT RUNNING on "
                    f"{self.unchecked_system_voice_books} book(s) that state game state on "
                    "the page; set --continuity-evaluator-command"
                ]
                if self.unchecked_system_voice_books
                else []
            ),
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
    budget: BudgetPolicy | None = None,
    continuity_evaluator: bool = True,
    blocked: Sequence[BlockedBook] = (),
) -> Status:
    """`continuity_evaluator` defaults to True so this reports nothing unless a caller
    states otherwise — an operator surface that accused every embedding of a missing
    evaluator would be noise, and the CLI is the only caller that knows.

    `blocked` is handed in rather than computed here, under the same rule: the refusal is
    `plan_progress`'s, and its answer depends on the draft policy and serial shape the tick
    actually runs under — flags only the CLI holds. A `StatusStore` cannot ask the planner's
    question (no manuscript or plan access, on purpose), and widening it so this module
    could re-derive the reason would buy a second computation that can disagree with the
    selector's. Defaulting empty means an embedding that does not pass it reports no blocked
    books rather than wrong ones."""
    day = datetime.fromtimestamp(now, tz=UTC).date().isoformat()
    return Status(
        now=now,
        jobs=store.job_counts_by_status(),
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
        blocked=tuple(blocked),
        # Read off canon rather than declared by a genre flag, for the reason
        # `speaks_system_voice` reads it that way: a flag is a second source of truth for
        # something the records already answer, and the two eventually disagree. A mystery
        # is not accused of missing a LitRPG evaluator.
        unchecked_system_voice_books=(
            0
            if continuity_evaluator
            else sum(
                1
                for book_id, branch_id, _ in store.branches()
                if speaks_system_voice(store.state_records(book_id, branch_id))
            )
        ),
    )


__all__ = ["BlockedBook", "Status", "collect"]
