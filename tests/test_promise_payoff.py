"""§94 W1 and W2: what kind of debt the ledger holds, and when the planner intends to pay it.

Two additions to §61 Add 2's ledger, and both inherit its whole safety argument rather than
extending it. A promise `kind` is reported by the summary call that already reports the
promise, and a payoff `window` is answered by the outline call that already holds the beat
sheet — §15's fold-asks rule twice, so neither feature adds a model invocation.

The properties this file exists to pin, each of which is a way the additions could quietly
break something already measured:

- **Convergence survives typing.** `promise_id` is sha256(book + subject) so a re-summarised
  scene converges on one row; a `kind` that could be updated would make "what does this book
  owe" depend on when it was asked, so the kind is fixed at insert and a re-report under a
  different kind changes nothing.
- **Nothing degrades to a failure.** An unrecognised kind is untyped, a book with no open
  promises is asked for no windows, and a non-chronological template gets neither — the same
  abstention `beats_for` and milestones already make.
- **Neither addition can refuse anything.** Windows are PROPOSED-grade, mint no finding, and
  leave `promise.overdue.v0` as the entire evaluator side. A "missed its window" finding is
  deliberately absent: a model-scheduled window missed by a model-reported payoff is two model
  claims disagreeing, and neither may raise a finding about the other.
- **The declared rules are attainable.** `schedule_fault` abstains below two windows and below
  three acts rather than firing on a book too short to have the structure it describes, which
  is the check seven prior declarations in this project failed.
"""

from __future__ import annotations

import litharness_contracts as lc
import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.outline import (
    OutlineOutputError,
    _payoff_windows,
    make_outline_handler,
    render_outline_request,
)
from litharness.application.summarize import (
    SUMMARY_SCHEMA,
    make_summary_handler,
    render_summary_prompt,
)
from litharness.domain.beats import BeatTemplate, arc_template, beats_for
from litharness.domain.findings import DetectorInput
from litharness.domain.generation import CompletionResult, Resolution, Usage
from litharness.domain.integrity import OVERDUE_RULE, run_detectors
from litharness.domain.jobs import Job
from litharness.domain.nodes import Node, NodeKind
from litharness.domain.promises import (
    PROMISE_KINDS,
    PROMISE_PAID,
    Promise,
    acts_for,
    describe_owed,
    kind_counts,
    normalise_kind,
    promise_id_for,
    schedule_fault,
    window_fault,
)
from litharness.domain.revision import Revision, build_revision, new_book
from litharness.domain.text import content_hash
from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID

START = 1_760_000_000.0
PREMISE = "A courier in a debt-ledger city must clear a guild debt before it compounds."
KEYS = tuple(f"s{index:02d}" for index in range(1, 13))


@pytest.fixture
def store(tmp_path) -> SqliteStore:  # type: ignore[no-untyped-def]
    return SqliteStore.open(tmp_path / "payoff.db")


def a_drafted_book(scenes: int = 12) -> Revision:
    """A book whose scenes carry prose, which `new_book` deliberately does not."""
    nodes = [Node(logical_id="book", kind=NodeKind.BOOK, position_key="010")]
    for index in range(1, scenes + 1):
        nodes.append(
            Node(
                logical_id=f"sc{index}",
                kind=NodeKind.SCENE,
                position_key=f"{index:03d}0",
                parent_logical_id="book",
                content=(
                    f"Scene {index}. Kestrel set the summons down and counted what the day "
                    "had cost her, and the ledger did not blink."
                ),
            )
        )
    return build_revision(BOOK_ID, BRANCH_ID, nodes)


def a_promise(
    subject: str = "sealed_crate",
    *,
    opened: str = "s01",
    due: str | None = "s12",
    kind: str | None = None,
    status: str = "open",
) -> Promise:
    return Promise(
        promise_id=promise_id_for(BOOK_ID, subject),
        subject=subject,
        description=f"the matter of the {subject.replace('_', ' ')} must be settled",
        opened_at_key=opened,
        due_key=due,
        opened_by_revision="rev-1",
        status=status,
        kind=kind,
        model="stub-v1",
    )


# -- W1: the kind -------------------------------------------------------------------------


def test_the_kind_rides_the_summary_call_that_already_reports_the_promise() -> None:
    """§15's fold-asks rule, and the reason this feature costs no invocation.

    The schema gains a field on an existing object and the prompt gains a clause on an
    existing line. A separate "classify these promises" call would re-pay the per-invocation
    harness tax for a one-word answer, which is the arithmetic §15 settled.
    """
    item = SUMMARY_SCHEMA["properties"]["promises_opened"]["items"]  # type: ignore[index]
    assert "kind" in item["properties"], "the kind is asked for in the summary schema"
    assert "kind" not in item["required"], (
        "optional, so a model that cannot classify a debt still reports the debt; a required "
        "field would lose the promise to a missing annotation"
    )
    assert item["properties"]["kind"]["anyOf"][0]["enum"] == list(PROMISE_KINDS)
    system, _ = render_summary_prompt("prose")
    for kind in PROMISE_KINDS:
        assert kind in system, "the frozen set is named in the ask, not only in the schema"


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("plot", "plot"),
        ("  Mystery  ", "mystery"),
        ("MYSTERY", "mystery"),
        ("tone", None),
        ("worldbuilding", None),
        ("", None),
        (None, None),
        (7, None),
        (True, None),
    ],
)
def test_an_unrecognised_kind_is_untyped_and_never_an_error(
    answer: object, expected: str | None
) -> None:
    """Tolerant about case and space, closed about membership.

    An unregistered category is a *nomination*, and nominations are weighed by an operator over
    the derivation run's printed distribution — never mapped onto a near neighbour by a synonym
    table nobody registered. `domain/axes.py` puts the same rail in front of its registry.
    """
    assert normalise_kind(answer) == expected


def test_the_taxonomy_is_the_derived_one_and_not_the_guess() -> None:
    """`tone` was in the five-way guess and is out because nothing ever reported it.

    Two disjoint local families, 120 reported promises over the only own-generated book in this
    repository, zero `tone`. The other four each cleared the per-model rule on at least one
    family and the rule forbids pooling to break a disagreement, so four survive rather than
    two. Pinned here because the whole value of deriving a taxonomy is lost if a later edit can
    put a category back on plausibility — which is the door twenty-one refuted proxies came
    through. Re-admitting one takes the nomination path, not an edit.
    """
    assert PROMISE_KINDS == ("plot", "character", "progression", "mystery")
    assert "tone" not in PROMISE_KINDS
    assert normalise_kind("tone") is None, "a cut kind degrades to untyped like any other"


def test_a_re_reported_kind_under_the_same_subject_does_not_move_the_row(
    store: SqliteStore,
) -> None:
    """Convergence is the ledger's whole design and typing must not weaken it.

    `INSERT OR IGNORE` on the content-derived id is what makes a re-summarised scene converge
    on one row rather than stack a duplicate. That same statement is what fixes the kind, so a
    second answer calling the debt something else is a no-op — otherwise "what does this book
    owe" would depend on when it was asked.
    """
    assert store.record_promise(BOOK_ID, BRANCH_ID, a_promise(kind="mystery"))
    assert not store.record_promise(BOOK_ID, BRANCH_ID, a_promise(kind="tone"))
    (stored,) = store.promises(BOOK_ID, BRANCH_ID)
    assert stored.kind == "mystery"


def test_a_row_written_before_the_column_reads_back_untyped(store: SqliteStore) -> None:
    """NULL is "unrecorded", never an error and never a category with a population."""
    store.record_promise(BOOK_ID, BRANCH_ID, a_promise(kind=None))
    (stored,) = store.promises(BOOK_ID, BRANCH_ID)
    assert stored.kind is None
    assert stored.window_start_key is None and stored.scheduled_by_plan_revision is None


def test_per_kind_density_sees_what_raw_density_cannot() -> None:
    """The tripwire this column exists for.

    Five opened against five paid nets to zero however mismatched the kinds are, so a book
    opening cheap mystery hooks while paying only tone debts is invisible to raw density and
    visible per kind. That is the cheapest way to game any continuation metric, stated as a
    counter rather than as a worry.
    """
    ledger = [
        a_promise("m1", kind="mystery"),
        a_promise("m2", kind="mystery"),
        a_promise("t1", kind="tone", status=PROMISE_PAID),
        a_promise("t2", kind="tone", status=PROMISE_PAID),
        a_promise("u1", kind=None),
    ]
    counts = kind_counts(ledger)
    assert counts["mystery"] == (2, 0), "two mystery debts opened, none settled"
    assert counts["tone"] == (2, 2)
    assert counts[None] == (1, 0), "untyped rows are their own bucket, not folded into a kind"


def test_the_summary_handler_writes_the_kind_it_was_told(store: SqliteStore) -> None:
    revision = a_drafted_book(6)
    scene = next(node for node in revision.nodes if node.kind is NodeKind.SCENE)
    store.commit_revision(revision, created_at="2026-08-19T00:00:00Z")
    payload = {
        "setting": "the counting-house",
        "characters": "Kestrel",
        "events": "a summons was served",
        "open": "who sent it",
        "delta": None,
        "promises_opened": [
            {"subject": "sealed crate", "description": "the crate must be opened",
             "kind": "mystery", "due_hint": 4},
            {"subject": "tone", "description": "the register must stay dry",
             "kind": "worldbuilding", "due_hint": None},
        ],
        "promises_paid": [],
    }
    handler = make_summary_handler(_StubGenerator(payload), store, PROJECT_ID)
    handler(
        Job(
            job_id="sum-1",
            job_kind="scene_summary",
            idempotency_key="sum-1",
            payload={
                "book_id": BOOK_ID,
                "branch_id": BRANCH_ID,
                "revision_id": revision.revision_id,
                "logical_id": scene.logical_id,
                "content_hash": content_hash(scene.content or ""),
            },
        ),
        START,
    )
    by_subject = {promise.subject: promise for promise in store.promises(BOOK_ID, BRANCH_ID)}
    assert by_subject["sealed_crate"].kind == "mystery"
    assert by_subject["tone"].kind is None, (
        "an out-of-set kind degrades to untyped and the promise still lands"
    )


# -- W2: the payoff window ----------------------------------------------------------------


def test_open_promises_reach_the_outline_ask_as_debts_and_nothing_else() -> None:
    """Shown as owed, never as fact — `describe_owed`'s register rule, one call over.

    A model-reported promise rendered in the indicative would be laundered into premise by
    register alone, which is the same laundering `describe_owed` exists to prevent in the
    packet.
    """
    revision = new_book(BOOK_ID, BRANCH_ID, title="Book", scenes=12)
    beats = beats_for(revision, arc_template(12))

    class _Base:
        plan_revision_id = "planrev-1"
        items: tuple = ()

    empty = render_outline_request(PREMISE, beats, base=_Base())  # type: ignore[arg-type]
    assert "payoff_windows" not in empty.prompt, (
        "a book that owes nothing is asked for no schedule; an empty ask produces an empty "
        "answer to validate, which is worse than not asking"
    )
    with_debt = render_outline_request(
        PREMISE, beats, base=_Base(), promises=[a_promise()]  # type: ignore[arg-type]
    )
    assert "open_promises" in with_debt.prompt
    assert "sealed_crate" in with_debt.prompt
    assert "may not close after the scene it is due by" in with_debt.prompt
    assert "Spread the payments out" in with_debt.prompt


@pytest.mark.parametrize(
    ("start", "end", "fragment"),
    [
        ("s99", "s12", "does not have"),
        ("s09", "s03", "runs backwards"),
        ("s01", "s04", None),
    ],
)
def test_a_window_that_cannot_be_paid_is_refused(
    start: str, end: str, fragment: str | None
) -> None:
    promise = a_promise(opened="s01", due="s12")
    fault = window_fault(promise, start, end, keys=KEYS)
    if fragment is None:
        assert fault is None
    else:
        assert fault is not None and fragment in fault


def test_a_window_may_not_open_before_the_debt_exists() -> None:
    """Payment scheduled before the promise is bookkeeping about the past."""
    promise = a_promise(opened="s05", due="s12")
    fault = window_fault(promise, "s02", "s06", keys=KEYS)
    assert fault is not None and "before" in fault


def test_a_window_may_not_plan_its_own_overdue_finding() -> None:
    """A schedule closing after `due_key` agrees in advance to fire `promise.overdue.v0`."""
    promise = a_promise(opened="s01", due="s06")
    fault = window_fault(promise, "s02", "s09", keys=KEYS)
    assert fault is not None and "after" in fault


def test_everything_resolving_at_the_end_is_refused() -> None:
    """The one rule here that is about the reader rather than about coherence.

    PLAN.md §1a.3 item 3 asks for promises paid *on a cadence a reader can feel*, and a
    schedule that pays every debt in the final act is the defect that goal names. This is
    `_milestones`' anti-stasis rule with the same shape and the same reason.
    """
    fault = schedule_fault([("s10", "s11"), ("s11", "s12"), ("s09", "s12")], keys=KEYS)
    assert fault is not None and "final act" in fault


def test_one_window_wearing_a_schedule_is_refused() -> None:
    fault = schedule_fault([("s02", "s04"), ("s02", "s04")], keys=KEYS)
    assert fault is not None and "same range" in fault


def test_a_spread_schedule_passes() -> None:
    assert schedule_fault([("s02", "s04"), ("s05", "s07"), ("s09", "s11")], keys=KEYS) is None


def test_the_schedule_rule_abstains_where_it_could_not_mean_anything() -> None:
    """I7's check: a rule that fires on material it cannot describe is a bar that cannot be met.

    With one window there is no distinction between "everything resolves at the end" and "the
    one thing resolves at the end"; on a book too short for three acts there is no final act to
    be in. Both abstain, and the abstention is declared rather than emergent.
    """
    assert schedule_fault([("s11", "s12")], keys=KEYS) is None
    assert schedule_fault([("s01", "s02"), ("s02", "s02")], keys=("s01", "s02")) is None
    assert acts_for(("s01", "s02")) == (("s01", "s02"),)
    assert len(acts_for(KEYS)) == 3


def test_a_schedule_may_not_invent_a_debt() -> None:
    revision = new_book(BOOK_ID, BRANCH_ID, title="Book", scenes=12)
    beats = beats_for(revision, arc_template(12))
    with pytest.raises(OutlineOutputError, match="has not opened"):
        _payoff_windows(
            {"payoff_windows": [{"subject": "a_debt_nobody_recorded",
                                 "first_scene": 2, "last_scene": 4}]},
            beats,
            [a_promise()],
        )


def test_one_promise_carries_one_window() -> None:
    revision = new_book(BOOK_ID, BRANCH_ID, title="Book", scenes=12)
    beats = beats_for(revision, arc_template(12))
    with pytest.raises(OutlineOutputError, match="more than one window"):
        _payoff_windows(
            {
                "payoff_windows": [
                    {"subject": "sealed_crate", "first_scene": 2, "last_scene": 4},
                    {"subject": "sealed_crate", "first_scene": 5, "last_scene": 7},
                ]
            },
            beats,
            [a_promise()],
        )


def test_a_non_chronological_template_schedules_nothing() -> None:
    """`beats_for` mints no story position there, so neither does this.

    The same abstention milestones make and the ledger itself makes — no key rather than a
    guessed one. It arrives as a refused window rather than as a silently misplaced one.
    """
    revision = new_book(BOOK_ID, BRANCH_ID, title="Book", scenes=12)
    unordered = BeatTemplate(
        "template.unordered.v0",
        tuple("rising" for _ in range(12)),
        chronological=False,
    )
    beats = beats_for(revision, unordered)
    assert all(beat.story_order_key is None for beat in beats)
    with pytest.raises(OutlineOutputError, match="no story position"):
        _payoff_windows(
            {"payoff_windows": [{"subject": "sealed_crate",
                                 "first_scene": 2, "last_scene": 4}]},
            beats,
            [a_promise()],
        )


def test_an_absent_schedule_is_not_a_refusal() -> None:
    """A book with no open promises was asked for no windows, so an empty answer is correct."""
    revision = new_book(BOOK_ID, BRANCH_ID, title="Book", scenes=12)
    beats = beats_for(revision, arc_template(12))
    assert _payoff_windows({}, beats, []) == []
    assert _payoff_windows({"payoff_windows": []}, beats, [a_promise()]) == []


def test_the_window_rides_the_debt_line_and_reads_as_owed() -> None:
    """One line, one register. A schedule with a packet heading of its own would give a
    PROPOSED-grade model answer a section beside canon."""
    plain = a_promise()
    assert describe_owed(plain).startswith("owes:")
    assert "pay within" not in describe_owed(plain), (
        "an unscheduled promise renders exactly as it did before this existed"
    )
    scheduled = Promise(
        promise_id=plain.promise_id,
        subject=plain.subject,
        description=plain.description,
        opened_at_key=plain.opened_at_key,
        due_key=plain.due_key,
        opened_by_revision=plain.opened_by_revision,
        window_start_key="s07",
        window_end_key="s09",
    )
    rendered = describe_owed(scheduled)
    assert rendered.startswith("owes:") and "pay within s07-s09" in rendered
    assert "due by s12" in rendered


def test_a_window_mints_no_finding(store: SqliteStore) -> None:
    """PROMOTED nowhere. `promise.overdue.v0` remains the entire evaluator side.

    A "missed its window" sibling is deliberately absent: a model-scheduled window missed by a
    model-reported payoff is two model claims disagreeing, and neither is entitled to raise a
    finding about the other.
    """
    scheduled = Promise(
        promise_id=promise_id_for(BOOK_ID, "sealed_crate"),
        subject="sealed_crate",
        description="the crate must be opened",
        opened_at_key="s01",
        due_key="s12",
        opened_by_revision="rev-1",
        window_start_key="s02",
        window_end_key="s03",
    )
    findings = run_detectors(
        DetectorInput(
            book_id=BOOK_ID,
            branch_id=BRANCH_ID,
            logical_id="sc9",
            story_order_key="s09",
            open_promises=(scheduled,),
        )
    )
    assert [finding.rule_or_critic_id for finding in findings] == [], (
        "the window is behind the book and still fires nothing; only the due date can"
    )
    overdue = run_detectors(
        DetectorInput(
            book_id=BOOK_ID,
            branch_id=BRANCH_ID,
            logical_id="sc9",
            story_order_key="s09",
            open_promises=(
                Promise(
                    promise_id=scheduled.promise_id,
                    subject=scheduled.subject,
                    description=scheduled.description,
                    opened_at_key="s01",
                    due_key="s03",
                    opened_by_revision="rev-1",
                    window_start_key="s02",
                    window_end_key="s03",
                ),
            ),
        )
    )
    assert [finding.rule_or_critic_id for finding in overdue] == [OVERDUE_RULE]


def test_the_outline_handler_schedules_and_a_replay_converges(store: SqliteStore) -> None:
    """The whole W2 path, and the property a replayed job owes: the same answer, no movement.

    The window write is an UPDATE restricted to open rows and idempotent in its values, so a
    second run of the same job writes the same window rather than accumulating anything —
    there is nothing here to accumulate, which is the point of storing it on the row.
    """
    revision = new_book(BOOK_ID, BRANCH_ID, title="Book", scenes=12)
    store.commit_revision(revision, created_at="2026-08-19T00:00:00Z")
    store.record_plan_items(
        BOOK_ID,
        BRANCH_ID,
        [
            lc.PlanItem(
                logical_id="premise",
                kind=lc.PlanKind.PREMISE,
                text=PREMISE,
                authority=lc.PlanAuthority.CANONICAL_IN_PROSE,
                locked=True,
            )
        ],
        created_at="2026-08-19T00:00:00Z",
    )
    store.record_promise(BOOK_ID, BRANCH_ID, a_promise("sealed_crate", opened="s01"))
    store.record_promise(BOOK_ID, BRANCH_ID, a_promise("guild_ledger", opened="s02"))

    payload = {
        "summary": "outline",
        "rationale": "every scene needs its own errand",
        "expected_outcome": "scenes differ",
        "scenes": [
            {"ordinal": index, "statement": f"Kestrel does a distinct thing number {index}."}
            for index in range(1, 13)
        ],
        "milestones": [],
        "payoff_windows": [
            {"subject": "sealed_crate", "first_scene": 3, "last_scene": 5},
            {"subject": "guild_ledger", "first_scene": 8, "last_scene": 10},
        ],
    }
    handler = make_outline_handler(_StubGenerator(payload), store, PROJECT_ID)
    job = Job(
        job_id="outline-1",
        job_kind="book_outline",
        idempotency_key="outline-1",
        payload={"book_id": BOOK_ID, "branch_id": BRANCH_ID, "plan_epoch": 0},
    )
    handler(job, START)
    scheduled = {p.subject: p for p in store.promises(BOOK_ID, BRANCH_ID)}
    assert scheduled["sealed_crate"].window_start_key == "s03"
    assert scheduled["sealed_crate"].window_end_key == "s05"
    assert scheduled["guild_ledger"].window_start_key == "s08"
    assert scheduled["sealed_crate"].scheduled_by_plan_revision, "provenance is recorded"

    before = [(p.subject, p.window_start_key, p.window_end_key)
              for p in store.promises(BOOK_ID, BRANCH_ID)]
    handler(job, START + 1)
    after = [(p.subject, p.window_start_key, p.window_end_key)
             for p in store.promises(BOOK_ID, BRANCH_ID)]
    assert before == after, "a replayed outline job converges rather than moving the schedule"


def test_a_paid_promise_cannot_be_scheduled(store: SqliteStore) -> None:
    """Scheduling payment for a settled debt is bookkeeping about the past.

    Unlike payment, a window is re-schedulable — plans in this system are versioned and
    re-proposable — so the restriction is on the row's status rather than on the write.
    """
    store.record_promise(BOOK_ID, BRANCH_ID, a_promise("sealed_crate"))
    assert store.schedule_payoff_window(
        BOOK_ID, BRANCH_ID, promise_id_for(BOOK_ID, "sealed_crate"),
        window_start_key="s03", window_end_key="s05", plan_revision_id="planrev-1",
    )
    assert store.schedule_payoff_window(
        BOOK_ID, BRANCH_ID, promise_id_for(BOOK_ID, "sealed_crate"),
        window_start_key="s04", window_end_key="s06", plan_revision_id="planrev-2",
    ), "a replan may move a window; that is what makes it a plan rather than a verdict"
    store.pay_promise(
        BOOK_ID, BRANCH_ID, promise_id_for(BOOK_ID, "sealed_crate"),
        paid_at_key="s05", paid_by_revision="rev-2",
    )
    assert not store.schedule_payoff_window(
        BOOK_ID, BRANCH_ID, promise_id_for(BOOK_ID, "sealed_crate"),
        window_start_key="s07", window_end_key="s09", plan_revision_id="planrev-3",
    )


class _StubGenerator:
    """A provider that answers with a fixed structured payload."""

    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls = 0

    def resolve(self, call_class: str = "generation"):  # type: ignore[no-untyped-def]
        class _P:
            name = "stub"

        return _P(), Resolution("stub")

    def complete(self, request):  # type: ignore[no-untyped-def]
        self.calls += 1
        return (
            CompletionResult(
                text="{}",
                provider="stub",
                model="stub-v1",
                usage=Usage(100, 400),
                parsed=self.payload,
                schema_requested=True,
            ),
            Resolution("stub"),
        )
