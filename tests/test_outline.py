"""Narrative Planning v0: one statement per scene.

Book Zero's first taxonomy entry (§52): `arc_template(30)` yields 25 `rising` beats of 30, and
the beat's function word is the entire plan-side instruction — so twenty-five scenes are asked
an identical question, and the book answered by re-issuing its own errand five times. This
covers the producer, the selector branch that enqueues it, and the prompt line it feeds —
all three, because the first version of this file covered only the producer while claiming
in this docstring that `test_planner.py` covered the rest. It did not, and branch coverage
showed the selector's new lines never executed: §51.1's defect, on the same function, in
the commit that recorded §51.1.
"""

from __future__ import annotations

import litharness_contracts as lc
import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.outline import (
    BOOK_OUTLINE,
    OUTLINE_PRIORITY,
    OutlineOutputError,
    make_outline_handler,
    outline_job_id,
    outline_proposal,
    render_outline_request,
)
from litharness.domain.beats import arc_template, beats_for
from litharness.domain.generation import CompletionResult, Resolution, Usage
from litharness.domain.jobs import Job, input_digest_for
from litharness.domain.plan_refinement import PlanProposalError
from litharness.domain.plans import scene_plan_for, scene_plan_id_for
from litharness.domain.revision import new_book
from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID

START = 1_760_000_000.0
PREMISE = "A courier in a debt-ledger city must clear a guild debt before it compounds."


@pytest.fixture
def store(tmp_path) -> SqliteStore:
    return SqliteStore.open(tmp_path / "outline.db")


def a_book(store: SqliteStore, scenes: int = 12):  # type: ignore[no-untyped-def]
    revision = new_book(BOOK_ID, BRANCH_ID, title="Book", scenes=scenes)
    store.commit_revision(revision, created_at="2026-08-16T00:00:00Z")
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
        created_at="2026-08-16T00:00:00Z",
    )
    return revision


#: Statements that are genuinely different scenes, not one scene with the number changed.
#:
#: **The fixture is part of the test's claim and the first version of it was the defect.**
#: Every happy-path case used "Kestrel does thing 1." … "Kestrel does thing 30.", which the
#: distinctness check passes and a reader would call one scene written thirty times — so the
#: suite defined a correct outline as exactly the §52 failure the module exists to prevent.
#: A test whose fixture encodes the defect converts a bug into a requirement, which §19.1
#: names as worse than no test at all.
DISTINCT = [
    "Kestrel delivers a summons to the Guild counting-house and is made to wait.",
    "The ledger clerk names her debt aloud in front of the queue.",
    "She takes an off-books courier run to the dye works to cover the interest.",
    "A rival courier warns her the Guild is buying her debt from smaller holders.",
    "She petitions the archivist for her own ledger page and is refused.",
    "The System charges her for a skill she used to escape a collector.",
    "She trades a favour to a fence for the name of the debt's new holder.",
    "A collector breaks her lantern in the alley behind the tannery.",
    "She finds her ledger page has been altered in a second hand.",
    "The archivist admits under pressure that pages are sold, not kept.",
    "She confronts the holder and learns her debt was bought as leverage.",
    "The Guild offers to clear the debt if she carries one sealed packet.",
    "She opens the packet and finds a writ against her own mentor.",
    "She refuses the run and the interest compounds past her level cap.",
]


def payload_for(count: int, *, statements: list[str] | None = None) -> dict:
    if statements is None:
        assert count <= len(DISTINCT), "extend DISTINCT rather than templating a number"
        statements = DISTINCT[:count]
    return {
        "summary": "outline",
        "rationale": "every scene needs its own errand",
        "expected_outcome": "scenes differ",
        "scenes": [
            {"ordinal": index + 1, "statement": statements[index]}
            for index in range(count)
        ],
    }


class StubPlanner:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.requests: list[object] = []

    def resolve(self, call_class: str = "generation"):  # type: ignore[no-untyped-def]
        class _P:
            name = "stub"

        return _P(), Resolution("stub")

    def complete(self, request):  # type: ignore[no-untyped-def]
        self.requests.append(request)
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


# -- the request --------------------------------------------------------------------------


def test_the_whole_sheet_goes_into_one_request() -> None:
    """A per-scene call would ask a model to invent scene 11 without having seen what scene
    10 is for — which is the condition that produces the duplication in the first place. It
    is asked once, with every beat in view, because "make these differ from each other" is
    not answerable one scene at a time."""
    revision = new_book(BOOK_ID, BRANCH_ID, title="Book", scenes=30)
    beats = beats_for(revision, arc_template(30))

    class _Base:
        plan_revision_id = "planrev-1"
        items: tuple = ()

    request = render_outline_request(PREMISE, beats, base=_Base())  # type: ignore[arg-type]
    assert PREMISE in request.prompt
    for ordinal in (1, 15, 30):
        assert f'"ordinal": {ordinal}' in request.prompt
    assert request.schema is not None, "structured output, not a parsed paragraph"
    assert "different from every other" in request.prompt


# -- the validation that is about the defect ----------------------------------------------


def test_an_outline_that_repeats_itself_is_refused() -> None:
    """**The one validation that is about the defect rather than about the schema.**

    An outline whose statements repeat is the same failure this module exists to end,
    arriving one layer earlier — and one layer earlier is where it is cheap: a refused
    proposal costs one call, and a repeated scene costs a generation plus everything
    downstream of accepting it.
    """
    revision = new_book(BOOK_ID, BRANCH_ID, title="Book", scenes=8)
    beats = beats_for(revision, arc_template(8))
    repeated = list(DISTINCT[:8])
    repeated[5] = repeated[2]  # scene 6 restates scene 3

    with pytest.raises(OutlineOutputError, match="more than one scene"):
        outline_proposal(
            payload_for(8, statements=repeated),
            base=_base_for(revision),
            beats=beats,
            project_id=PROJECT_ID,
            book_id=BOOK_ID,
            branch_id=BRANCH_ID,
            result=_result(),
        )


def test_whitespace_and_case_do_not_disguise_a_repeat() -> None:
    """Otherwise the check is defeated by a capital letter, which is not a distinct scene."""
    revision = new_book(BOOK_ID, BRANCH_ID, title="Book", scenes=8)
    beats = beats_for(revision, arc_template(8))
    statements = list(DISTINCT[:8])
    statements[5] = f"  {DISTINCT[2].upper()}  "

    with pytest.raises(OutlineOutputError, match="more than one scene"):
        outline_proposal(
            payload_for(8, statements=statements),
            base=_base_for(revision),
            beats=beats,
            project_id=PROJECT_ID,
            book_id=BOOK_ID,
            branch_id=BRANCH_ID,
            result=_result(),
        )


@pytest.mark.parametrize(
    "payload,match",
    [
        ({"scenes": []}, "covers 0 scene"),
        ({"scenes": [{"ordinal": 1, "statement": ""}] * 8}, "has no statement"),
    ],
)
def test_a_malformed_outline_names_what_was_wrong(payload: dict, match: str) -> None:
    """A refusal that does not say what it refused is one that gets worked around."""
    revision = new_book(BOOK_ID, BRANCH_ID, title="Book", scenes=8)
    beats = beats_for(revision, arc_template(8))
    with pytest.raises(OutlineOutputError, match=match):
        outline_proposal(
            {"summary": "s", "rationale": "r", "expected_outcome": "e", **payload},
            base=_base_for(revision),
            beats=beats,
            project_id=PROJECT_ID,
            book_id=BOOK_ID,
            branch_id=BRANCH_ID,
            result=_result(),
        )


def test_a_gap_in_the_ordinals_is_refused_rather_than_filled() -> None:
    """Eight statements that cover seven scenes twice leave one beat with no errand, which is
    the state this module exists to end. Refused rather than interpolated."""
    revision = new_book(BOOK_ID, BRANCH_ID, title="Book", scenes=8)
    beats = beats_for(revision, arc_template(8))
    payload = payload_for(8)
    payload["scenes"][7]["ordinal"] = 7  # two 7s, no 8

    with pytest.raises(OutlineOutputError, match="described more than once"):
        outline_proposal(
            payload,
            base=_base_for(revision),
            beats=beats,
            project_id=PROJECT_ID,
            book_id=BOOK_ID,
            branch_id=BRANCH_ID,
            result=_result(),
        )


# -- what it writes -------------------------------------------------------------------------


def test_each_statement_is_scoped_to_its_own_scene(store: SqliteStore) -> None:
    """Scoped, so it reaches one scene and not the book.

    A packet carrying the whole outline would hand every scene every other scene's errand,
    which is a more expensive way to cause the failure the outline exists to fix.
    """
    revision = a_book(store, scenes=12)
    beats = beats_for(revision, arc_template(12))
    proposal = outline_proposal(
        payload_for(12),
        base=_base_for(revision),
        beats=beats,
        project_id=PROJECT_ID,
        book_id=BOOK_ID,
        branch_id=BRANCH_ID,
        result=_result(),
    )
    assert len(proposal.edits) == 12
    for beat, edit in zip(beats, proposal.edits, strict=True):
        assert edit.item is not None
        assert edit.item.kind is lc.PlanKind.SCENE_PLAN
        assert edit.item.scope is not None
        assert edit.item.scope.logical_id == beat.logical_id
        # A model wrote it: `INTENDED`, never the director's own standing. Locking it would
        # make a wrong outline unfixable by the machinery that produced it.
        assert edit.item.authority is lc.PlanAuthority.INTENDED
        assert not edit.item.locked


def test_the_outline_becomes_readable_plan_items_through_the_handler(
    store: SqliteStore,
) -> None:
    revision = a_book(store, scenes=12)
    planner = StubPlanner(payload_for(12))
    handle = make_outline_handler(planner, store, PROJECT_ID)
    handle(_job(store), START)

    items = store.plan_items(BOOK_ID, BRANCH_ID)
    beats = beats_for(revision, arc_template(12))
    for index, beat in enumerate(beats, start=1):
        item = scene_plan_for(items, beat.logical_id)
        assert item is not None, f"{beat.logical_id} has no statement"
        assert item.text == DISTINCT[index - 1]


def test_running_the_outline_twice_is_a_no_op(store: SqliteStore) -> None:
    """An outline is a whole-book model call; a replayed job must converge rather than pay
    for it again."""
    a_book(store, scenes=12)
    planner = StubPlanner(payload_for(12))
    handle = make_outline_handler(planner, store, PROJECT_ID)
    handle(_job(store), START)
    handle(_job(store), START + 1)
    assert len(planner.requests) == 1


def test_a_refused_outline_is_recorded_and_retried_not_escalated(store: SqliteStore) -> None:
    """The request is unchanged and a second draw of a structured answer is a fair second
    try, exactly as a malformed scene draft is."""
    from litharness.domain.policy import Outcome

    a_book(store, scenes=12)
    repeated = list(DISTINCT[:12])
    repeated[4] = repeated[1]
    planner = StubPlanner(payload_for(12, statements=repeated))
    handle = make_outline_handler(planner, store, PROJECT_ID)
    handle(_job(store), START)

    [decision] = store.decisions_for_job("outline-job")
    assert decision.outcome is Outcome.RETRY
    assert decision.gates[0].rule_or_critic_id == "shape.outline.v0"
    assert not decision.gates[0].passed
    assert "more than one scene" in (decision.reason or "")
    assert scene_plan_for(store.plan_items(BOOK_ID, BRANCH_ID), "scene-1") is None


def test_a_premise_less_plan_can_be_written_and_not_read(store: SqliteStore) -> None:
    """Where the premise guarantee actually lives — and a store asymmetry found looking for it.

    The outline handler refuses a book whose plan has no single premise. Trying to reach that
    branch turned up something else: `record_plan_items` **accepts** a premise-less plan and
    `plan_revision` then **refuses to reconstruct it**, raising `PlanProposalError` on read.
    So the branch is unreachable through the store — the handler's `store.plan_revision(...)`
    raises first — and the check stays as a boundary guard rather than a path.

    The asymmetry is pre-existing and is not this module's to fix; it is recorded here and in
    §54 because a book in that state is one nothing can plan, draft or report on, and the
    write that created it succeeded.
    """
    revision = new_book(BOOK_ID, BRANCH_ID, title="Book", scenes=12)
    store.commit_revision(revision, created_at="2026-08-16T00:00:00Z")
    store.record_plan_items(
        BOOK_ID,
        BRANCH_ID,
        [
            lc.PlanItem(
                logical_id="c-1",
                kind=lc.PlanKind.CONSTRAINT,
                text="The city is never named.",
                authority=lc.PlanAuthority.INTENDED,
                locked=True,
            )
        ],
        created_at="2026-08-16T00:00:00Z",
    )
    with pytest.raises(PlanProposalError, match="exactly one premise"):
        store.plan_revision(BOOK_ID, BRANCH_ID)


def test_a_book_with_no_plan_is_refused_rather_than_outlined(store: SqliteStore) -> None:
    """An outline of nothing is thirty scenes of plausible prose about nothing, which is the
    failure `plans.py` refuses to let a default cause."""
    revision = new_book(BOOK_ID, BRANCH_ID, title="Book", scenes=12)
    store.commit_revision(revision, created_at="2026-08-16T00:00:00Z")
    handle = make_outline_handler(StubPlanner(payload_for(12)), store, PROJECT_ID)
    with pytest.raises(OutlineOutputError, match="no plan"):
        handle(_job(store), START)


def test_a_partially_outlined_book_is_completed_rather_than_refused(
    store: SqliteStore,
) -> None:
    """The defect four independent reviewers reproduced, as a regression guard.

    A book gains a scene — `new` or `import` on the same book and branch moves the head — and
    the twelve statements it already had survive. The selector fires on the one beat without
    one. With create-only edits the handler then proposed a CREATE for all thirteen,
    `apply_plan_proposal` raised `plan item 'scene-1-plan' already exists`, and the whole-book
    call had already been paid for: three generations per plan epoch, a poisoned job, an empty
    exception queue, and scene 13 with no statement forever.

    Now the twelve are updated and the thirteenth created, in one proposal.
    """
    a_book(store, scenes=12)
    handle = make_outline_handler(StubPlanner(payload_for(12)), store, PROJECT_ID)
    handle(_job(store), START)
    assert scene_plan_for(store.plan_items(BOOK_ID, BRANCH_ID), "scene-12") is not None

    # The manuscript gains a scene; the plan keeps the statements it had.
    grown = new_book(BOOK_ID, BRANCH_ID, title="Book", scenes=13)
    store.commit_revision(grown, created_at="2026-08-16T01:00:00Z")

    planner = StubPlanner(payload_for(13))
    make_outline_handler(planner, store, PROJECT_ID)(_job(store, "outline-2"), START + 1)

    items = store.plan_items(BOOK_ID, BRANCH_ID)
    for ordinal in range(1, 14):
        assert scene_plan_for(items, f"scene-{ordinal}") is not None, (
            f"scene-{ordinal} has no statement"
        )
    assert len(planner.requests) == 1
    # And exactly one statement per scene: an UPDATE, not a second item beside the first.
    scene_plans = [i for i in items if i.kind is lc.PlanKind.SCENE_PLAN]
    assert len(scene_plans) == 13


def test_a_dead_outline_escalates_instead_of_poisoning_quietly(store: SqliteStore) -> None:
    """`decide` rather than a hand-written RETRY, and the ceiling is where it shows.

    A model that keeps returning a repeated outline — the exact failure `_statements` exists
    to catch — is refused on every attempt. Hard-coding RETRY requeues a job the queue then
    poisons, and the POISONED path files no exception, so an outline that could never conform
    went quiet and the book drafted every scene with no statement. `decide` escalates on
    exhaustion, which is what puts it in front of a human.
    """
    from litharness.domain.policy import Outcome

    a_book(store, scenes=12)
    repeated = list(DISTINCT[:12])
    repeated[4] = repeated[1]
    planner = StubPlanner(payload_for(12, statements=repeated))
    handle = make_outline_handler(planner, store, PROJECT_ID)

    outcomes = []
    for attempt in range(1, 4):
        handle(_job(store, attempts=attempt), START + attempt)
        outcomes.append(store.decisions_for_job("outline-job")[-1].outcome)

    assert outcomes[0] is Outcome.RETRY
    # PARK rather than ESCALATE, because `SHAPE_NOT_CONFORMING` is retryable and `decide`
    # parks a retryable veto at the ceiling — revivably, and `_settle` files an exception for
    # PARK. That is the property under test: the unit ends up in the operator's queue with
    # its reason attached, instead of poisoning with an empty one. Which of the two
    # human-facing outcomes it is, is `decide`'s call and not this handler's.
    assert outcomes[-1] is Outcome.PARK, (
        "an outline that can never conform must reach a human, not poison silently"
    )


def test_the_outline_outranks_scene_work_and_not_direction() -> None:
    """One call for the whole book, claimed before the first scene and after any directive:
    a scene drafted first would be drafted against the empty plan this fills."""
    from litharness.application.narrative_planner import NARRATIVE_PLAN  # noqa: F401
    from litharness.application.repair import EVALUATION_PRIORITY, REPAIR_PRIORITY

    assert OUTLINE_PRIORITY > REPAIR_PRIORITY > EVALUATION_PRIORITY > 0
    assert OUTLINE_PRIORITY < 500, "director direction still precedes it"


def test_the_job_id_follows_the_plan_epoch() -> None:
    """`idempotency_key` is UNIQUE, so a poisoned outline would burn its id forever and
    "plan this book again" would be inexpressible. `replan` bumps the epoch."""
    first = outline_job_id(BOOK_ID, BRANCH_ID, 0)
    assert first == outline_job_id(BOOK_ID, BRANCH_ID, 0)
    assert first != outline_job_id(BOOK_ID, BRANCH_ID, 1)


# -- helpers --------------------------------------------------------------------------------


def _base_for(revision):  # type: ignore[no-untyped-def]
    class _Base:
        plan_revision_id = "planrev-1"
        items: tuple = ()

    return _Base()


def _result() -> CompletionResult:
    return CompletionResult(
        text="{}", provider="stub", model="stub-v1", usage=Usage(10, 10)
    )


def _job(store: SqliteStore, job_id: str = "outline-job", *, attempts: int = 0) -> Job:
    payload = {"book_id": BOOK_ID, "branch_id": BRANCH_ID, "plan_epoch": 0}
    return Job(
        job_id=job_id,
        attempts=attempts,
        job_kind=BOOK_OUTLINE,
        payload=payload,
        input_digest=input_digest_for(payload),
        priority=OUTLINE_PRIORITY,
    )


def test_the_derived_plan_id_is_stable() -> None:
    assert scene_plan_id_for("scene-3") == "scene-3-plan"


# -- the consumer side: the selector branch, and the prompt line ---------------------------


def test_the_selector_enqueues_an_outline_when_the_sheet_repeats_a_function(
    store: SqliteStore,
) -> None:
    """The branch that makes any of this run, which nothing executed until this test.

    A thirty-scene arc has 25 `rising` beats, so its own sheet cannot tell those scenes apart
    and the outline has something to disambiguate.
    """
    from litharness.application.planner import make_plan_selector

    a_book(store, scenes=12)
    selected = make_plan_selector(project_id=PROJECT_ID)(store, "worker-a", START, 60.0)
    assert selected is not None
    assert selected.job_kind == BOOK_OUTLINE
    assert selected.priority == OUTLINE_PRIORITY, "claimed before any scene draft"


def test_a_six_scene_book_is_never_outlined(store: SqliteStore) -> None:
    """The condition is the defect, not the book. At six scenes every dramatic function is
    distinct, so there is nothing for an outline to disambiguate and both golden fixtures are
    untouched by this — no model call, no plan movement, no behaviour change."""
    from litharness.application.planner import make_plan_selector

    a_book(store, scenes=6)
    selected = make_plan_selector(project_id=PROJECT_ID)(store, "worker-a", START, 60.0)
    assert selected is None or selected.job_kind != BOOK_OUTLINE


def test_an_outlined_book_stops_enqueueing_outlines(store: SqliteStore) -> None:
    """Otherwise every tick mints a whole-book generation for a book that has one."""
    from litharness.application.planner import make_plan_selector

    a_book(store, scenes=12)
    handle = make_outline_handler(StubPlanner(payload_for(12)), store, PROJECT_ID)
    handle(_job(store), START)

    selected = make_plan_selector(project_id=PROJECT_ID)(store, "worker-a", START + 1, 60.0)
    assert selected is None or selected.job_kind != BOOK_OUTLINE


def test_the_statement_reaches_the_prompt_and_its_absence_changes_nothing(
    store: SqliteStore,
) -> None:
    """The consumer half, and both directions of it.

    A scene with a statement is told what it is for; a scene without one gets exactly the
    prompt that shipped before this existed — which is what makes the whole slice additive
    rather than a new hard dependency on a model call.
    """
    from litharness.application.planner import packet_for, render_prompt

    revision = a_book(store, scenes=12)
    beats = beats_for(revision, arc_template(12))
    beat = beats[4]
    packet = packet_for(store, revision, beat)

    _, bare_prompt = render_prompt(beat, book_title=None, packet=packet)
    assert "This scene:" not in bare_prompt

    _, planned = render_prompt(
        beat, book_title=None, packet=packet, scene_plan=DISTINCT[4]
    )
    assert DISTINCT[4] in planned
    assert planned.rstrip().endswith(DISTINCT[4]), (
        "the statement is the last thing in the prompt, which is the thing a model acts on"
    )
    # An empty statement is "no statement", not an empty instruction.
    _, empty = render_prompt(beat, book_title=None, packet=packet, scene_plan="   ")
    assert empty == bare_prompt


def test_the_drafting_lane_reads_the_statement_the_outline_wrote(store: SqliteStore) -> None:
    """End to end: once the book is outlined, the beat the selector materialises carries its
    own errand in the prompt the drafting handler will read.

    Driven by outlining first and selecting second, rather than by settling a job by hand —
    the selector's own `needs_outline` is then False and it materialises a beat, which is the
    sequence a real tick produces.
    """
    from litharness.application.planner import make_plan_selector

    a_book(store, scenes=12)
    make_outline_handler(StubPlanner(payload_for(12)), store, PROJECT_ID)(_job(store), START)

    draft_job = make_plan_selector(project_id=PROJECT_ID)(store, "worker-a", START + 1, 60.0)
    assert draft_job is not None
    assert draft_job.job_kind != BOOK_OUTLINE, "the book is outlined; draft it"
    prompt = str(draft_job.payload["prompt"])
    ordinal = int((draft_job.payload.get("selected_by") or {}).get("ordinal") or 1)
    assert DISTINCT[ordinal - 1] in prompt, "the scene was drafted knowing what it is for"
    assert prompt.rstrip().endswith(DISTINCT[ordinal - 1])
