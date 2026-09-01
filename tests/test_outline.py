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

import json
from dataclasses import replace

import litharness_contracts as lc
import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.model_context import at_scene
from litharness.application.outline import (
    BOOK_OUTLINE,
    OUTLINE_PRIORITY,
    PROTAGONIST_RULES,
    OutlineOutputError,
    _milestones,
    _standing_milestones,
    make_outline_handler,
    milestone_records,
    outline_job_id,
    outline_proposal,
    render_outline_request,
    standing_milestone_records,
)
from litharness.domain import genre, staging, world_brief, worlds
from litharness.domain import state as state_mod
from litharness.domain.beats import TemplateMismatch, arc_template, beats_for
from litharness.domain.extraction import standing_target
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


#: The starting sheet `a_book` seeds and the schedule tests write milestones against. One
#: dict, both places: a second sheet with different keys would let `at_scene` hand the
#: handler whichever record it read last, and a milestone keyed to the other one would be
#: refused for inventing statistics.
SEED = {"level": 1, "hp": 18, "hp_max": 18, "mp": 4, "mp_max": 4, "gold": 12}


def a_book(store: SqliteStore, scenes: int = 12, *, sheet: bool = True):  # type: ignore[no-untyped-def]
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
    # The house genre floor (`domain/genre.py`) refuses to draft a book whose canon cannot
    # speak system voice, so the fixture seeds a starting sheet. A mapping since §158: the
    # floor asks for a sheet the status-line machinery can render numbers from, and the
    # prose value this fixture carried before — the pilot 14 loophole — no longer counts.
    # That also means a seeded book's outline is *asked* for a milestone schedule and its
    # stub reply must carry one; `sheet=False` is the book that genuinely does not speak,
    # which the selector floors and only a directly-handed job can reach.
    if sheet:
        store.record_state_records(
            BOOK_ID,
            BRANCH_ID,
            [
                lc.StateRecord(
                    record_id="seed-status",
                    kind=lc.StateRecordKind.ASSERTION,
                    subject="kestrel",
                    predicate="status_snapshot",
                    value=dict(SEED),
                    authority=lc.StateAuthority.ACCEPTED_CANON,
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
    "Her mentor closes the courier office and burns the route ledgers in the yard.",
    "Kestrel maps the untaxed rooftop routes by night to run mail the Guild cannot price.",
    "The collector who broke her lantern defects and hands her his collection book.",
    "The Guild posts her name on the defaulters' board at every gate in the city.",
    "She undercuts the Guild's couriers openly and the queue at her door says it worked.",
    "The holder calls the whole debt due at once before the magistrate.",
    "The magistrate rules the altered ledger page inadmissible and voids the compounding.",
    "The Guild's charter is read aloud and the clause about sold pages ruins them.",
    "Kestrel pays the original principal in coin earned off the books.",
    "She posts her own ledger page on the counting-house door, cleared in her own hand.",
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


def test_the_outline_sees_state_at_the_arc_entry_not_later_state() -> None:
    revision = new_book(BOOK_ID, BRANCH_ID, title="Book", scenes=8)
    beats = beats_for(revision, arc_template(8))
    records = tuple(
        lc.StateRecord(
            record_id=f"want-{ordinal}",
            kind=lc.StateRecordKind.ASSERTION,
            subject="silas",
            predicate="wants",
            value=value,
            story_position=lc.StoryPosition(order_key=f"s{ordinal}"),
            authority=lc.StateAuthority.ACCEPTED_CANON,
        )
        for ordinal, value in ((1, "recognition"), (8, "retirement"))
    )
    entry = at_scene(
        revision,
        records,
        beats[0].logical_id,
        moment=state_mod.StateMoment.ENTERING,
    )

    body = json.loads(
        render_outline_request(
            PREMISE,
            beats,
            base=_bare_base(),
            arc_entry_state=entry,
        ).prompt
    )

    assert body["story_state_at_arc_entry"]["established_facts"] == ["silas wants recognition"]
    assert "retirement" not in json.dumps(body["story_state_at_arc_entry"])


# -- the world's people, and whose book it is ---------------------------------------------
#
# `plan/reader-read-3.md` notes 1 and 3. Until 2026-08-22 this call was handed the premise, the
# beat sheet, the status seed and the open promises, and **not one record of canon** — so on
# Serial Pilot 3 it invented a protagonist who occurs nowhere in the forged world (0 hits for
# "Kell" in `pilot3/direct1/forge.json`), and none of that world's five declared cast members
# appears in either chapter. The writer had them all along: 328 established facts,
# `context_omitted = 0`.


def _bare_base():  # type: ignore[no-untyped-def]
    class _Base:
        plan_revision_id = "planrev-1"
        items: tuple = ()

    return _Base()


def _eight_beats():  # type: ignore[no-untyped-def]
    return beats_for(new_book(BOOK_ID, BRANCH_ID, title="Book", scenes=8), arc_template(8))


PROTAGONIST = worlds.Protagonist(
    "silas",
    "provenance",
    "he prices a thing the assay has not seen",
    "to be read once by someone who matters",
    "every reading he signs is checked twice",
)


def test_a_book_whose_canon_declares_nobody_renders_the_bytes_it_always_did() -> None:
    """**The control, and it is a byte comparison rather than a substring one.**

    Every book written before a world could declare a protagonist passes nothing here, and
    `json.dumps` writes `null` for a key whose value is `None` — so a key that is always
    present is a payload that always changed. `jobs.input_digest_for` covers the prompt and
    that digest is the sampler seed, so a silent payload change silently re-decodes every job
    a book mints. The empty case must produce exactly the bytes that omitting the parameters
    produces.
    """
    beats = _eight_beats()
    absent = render_outline_request(PREMISE, beats, base=_bare_base())
    empty = render_outline_request(
        PREMISE, beats, base=_bare_base(), world=None, protagonist=None
    )
    assert empty == absent
    assert "protagonist" not in json.loads(absent.prompt)


def test_the_protagonist_reaches_the_request_as_canon_declared_them() -> None:
    """**The one thing the world brief cannot say.** `world_brief.brief_for` renders every
    declared person under `cast`, in the packet's own phrasing (§107.3); what a flat list of
    people cannot carry is which of them the book is about."""
    request = render_outline_request(
        PREMISE, _eight_beats(), base=_bare_base(), protagonist=PROTAGONIST
    )
    body = json.loads(request.prompt)
    assert body["protagonist"] == {
        "id": "silas",
        "exception": "provenance",
        "edge": "he prices a thing the assay has not seen",
        "wants": "to be read once by someone who matters",
        "price": "every reading he signs is checked twice",
    }


def test_the_rules_arrive_only_with_the_thing_they_are_about() -> None:
    """A rule about a protagonist in a request with none is an instruction to obey nothing."""
    beats = _eight_beats()
    bare = json.loads(render_outline_request(PREMISE, beats, base=_bare_base()).prompt)
    assert not any("protagonist is" in rule for rule in bare["rules"])

    named = json.loads(
        render_outline_request(
            PREMISE, beats, base=_bare_base(), protagonist=PROTAGONIST
        ).prompt
    )
    assert any("The protagonist is silas." in rule for rule in named["rules"])
    assert any("what silas does in that scene" in rule for rule in named["rules"])


def test_the_protagonist_rules_name_a_person_and_never_an_outcome() -> None:
    """**The §112 protagonist boundary, asserted rather than trusted.**

    A protagonist is a declared fact of the world and a position — the same class as "scene 3
    of 8" and the chapter cue. No default instruction about how to *handle* one may enter any
    prompt this system renders: open on the hero, make them likeable, show them winning,
    have them progress faster than anyone. That direction is the operator's, and the operator's
    own words for the hook use exactly those verbs — which is why the rules that came out of
    them must not. Written in the shape of
    `test_the_chapter_cue_carries_no_verb_and_no_adjective`.
    """
    rendered = " ".join(
        rule.format(subject="silas") for rule in PROTAGONIST_RULES
    ).lower()
    for forbidden in (
        "win", "hero", "likeable", "likable", "sympathetic", "root for", "faster",
        "fastest", "strongest", "best", "succeed", "success", "triumph", "interesting",
        "compelling", "unique", "special", "open on", "first",
    ):
        assert forbidden not in rendered, forbidden


def test_the_handler_reads_the_protagonist_off_the_canon_it_already_read(
    store: SqliteStore,
) -> None:
    """One query, not two. The drafting side's habit of calling `state_records` three times in
    one render is the pattern this deliberately does not copy — and a second read is a second
    answer to one question. The same `canon` feeds `world_brief.brief_for`."""
    a_book(store, scenes=12)
    store.record_state_records(
        BOOK_ID,
        BRANCH_ID,
        [
            replace(built, authority=lc.StateAuthority.ACCEPTED_CANON)
            for built in (
                worlds.world_record("silas", worlds.ENTITY_ROLE_PREDICATE, value="cast"),
                worlds.world_record(
                    "silas", worlds.ENTITY_ROLE_PREDICATE, value="protagonist"
                ),
                worlds.world_record("silas", "is_a", value="a junior clerk"),
                worlds.world_record(
                    "silas", worlds.EDGE_PREDICATE, value="he prices what the assay has not"
                ),
                worlds.world_record("silas", worlds.EXCEPTION_PREDICATE,
                                    object_ref="provenance"),
            )
        ],
        created_at="2026-08-16T00:00:00Z",
    )
    planner = StubPlanner(payload_for(12))
    make_outline_handler(planner, store, PROJECT_ID)(_job(store), START)

    [request] = planner.requests
    body = json.loads(request.prompt)
    assert body["protagonist"]["id"] == "silas"
    # And the same canon reached the world brief, which is where the people are now rendered.
    assert "silas" in json.dumps(body["world"], ensure_ascii=False)


def test_a_tick_over_an_already_outlined_book_mints_no_second_job(
    store: SqliteStore,
) -> None:
    """`outline_job_id` is epoch-keyed and excludes the prompt, so telling the planner about
    the world does not burn a new id for work already done.

    The exclusion is deliberate and `planner.py`'s module docstring states it: editing a
    template must not mint a second job for a book that has already been outlined.
    """
    a_book(store, scenes=12)
    before = outline_job_id(BOOK_ID, BRANCH_ID, store.plan_epoch(BOOK_ID, BRANCH_ID))
    store.record_state_records(
        BOOK_ID,
        BRANCH_ID,
        [
            replace(
                worlds.world_record("silas", worlds.ENTITY_ROLE_PREDICATE, value="cast"),
                authority=lc.StateAuthority.ACCEPTED_CANON,
            )
        ],
        created_at="2026-08-16T00:00:00Z",
    )
    after = outline_job_id(BOOK_ID, BRANCH_ID, store.plan_epoch(BOOK_ID, BRANCH_ID))
    assert after == before


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
    planner = StubPlanner(with_schedule(12))
    handle = make_outline_handler(planner, store, PROJECT_ID)
    handle(_job(store), START)

    items = store.plan_items(BOOK_ID, BRANCH_ID)
    beats = beats_for(revision, arc_template(12))
    for index, beat in enumerate(beats, start=1):
        item = scene_plan_for(items, beat.logical_id)
        assert item is not None, f"{beat.logical_id} has no statement"
        # The outline's own statement always leads; a scheduled scene then carries the house
        # progression beat, folded in by `genre.with_beat` rather than asked of the model.
        assert item.text.startswith(DISTINCT[index - 1])
        scheduled = index in genre.beat_ordinals(len(beats))
        # `BEAT_TAIL`, not `BEAT`: §161 gave the beat a second form that names the quantity
        # that moves, and this book's fixture sheet has one. The question here is whether
        # the SCHEDULE fired, which is the tail either form ends with.
        assert (genre.BEAT_TAIL in item.text) is scheduled, (
            f"scene {index} {'should' if scheduled else 'should not'} carry the beat"
        )
        # **The second scheduled fold, added 2026-08-30 (§175).** This assertion used to read
        # `item.text == DISTINCT[index - 1]` and meant "nothing is appended off-schedule"; the
        # opening's cast bound is a second thing that is appended *on* one, so the property it
        # was protecting is restated against both schedules rather than against the beat alone.
        bounded = staging.bounds_opening(index)
        assert (staging.bound_text() in item.text) is bounded, (
            f"scene {index} {'should' if bounded else 'should not'} carry the cast bound"
        )
        if not scheduled and not bounded:
            assert item.text == DISTINCT[index - 1]


def test_running_the_outline_twice_is_a_no_op(store: SqliteStore) -> None:
    """An outline is a whole-book model call; a replayed job must converge rather than pay
    for it again."""
    a_book(store, scenes=12)
    planner = StubPlanner(with_schedule(12))
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
    handle = make_outline_handler(StubPlanner(with_schedule(12)), store, PROJECT_ID)
    handle(_job(store), START)
    assert scene_plan_for(store.plan_items(BOOK_ID, BRANCH_ID), "scene-12") is not None

    # The manuscript gains a scene; the plan keeps the statements it had.
    grown = new_book(BOOK_ID, BRANCH_ID, title="Book", scenes=13)
    store.commit_revision(grown, created_at="2026-08-16T01:00:00Z")

    planner = StubPlanner(with_schedule(13))
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
    handle = make_outline_handler(StubPlanner(with_schedule(12)), store, PROJECT_ID)
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
    make_outline_handler(StubPlanner(with_schedule(12)), store, PROJECT_ID)(_job(store), START)

    draft_job = make_plan_selector(project_id=PROJECT_ID)(store, "worker-a", START + 1, 60.0)
    assert draft_job is not None
    assert draft_job.job_kind != BOOK_OUTLINE, "the book is outlined; draft it"
    prompt = str(draft_job.payload["prompt"])
    ordinal = int((draft_job.payload.get("selected_by") or {}).get("ordinal") or 1)
    assert DISTINCT[ordinal - 1] in prompt, "the scene was drafted knowing what it is for"
    # Still rendered LAST, which is the property this line has always been about. What ends
    # the prompt is the scene's stored plan — its own statement, plus the house progression
    # beat where the cadence schedules one.
    #
    # **§173 wraps the stored text rather than replacing it, and the wrapping is deliberately
    # not stored.** The interaction beat is read out of canon at the position being drafted; a
    # statement written when the outline ran was written before the book reached the rung a fork
    # opens at, so folding one into it would state a schedule (§110.3's measurement). So the
    # stored text still ends the prompt, or ends it followed by a beat this scene earned.
    stored = scene_plan_for(store.plan_items(BOOK_ID, BRANCH_ID), f"scene-{ordinal}")
    assert stored is not None
    tail = prompt.rstrip()
    assert stored.text.strip() in tail
    after = tail[tail.index(stored.text.strip()) + len(stored.text.strip()) :].strip()
    # **2026-09-01 (§195): the opening's beats fold after the interaction beat on the first
    # chapter's scenes**, by the same render-time rule and for the same reason — read out of
    # the position being drafted, never stored. What may follow the stored text is therefore
    # a composition of the scheduled render-time folds and nothing else.
    scheduled = (
        "",
        genre.INTERACTION_BEAT,
        genre.OPENING_FIRST,
        genre.OPENING_HOOK,
        f"{genre.INTERACTION_BEAT} {genre.OPENING_FIRST}",
        f"{genre.INTERACTION_BEAT} {genre.OPENING_HOOK}",
    )
    assert after in scheduled, after


def test_the_control_arm_is_reachable_through_the_operator_surface(
    store: SqliteStore,
) -> None:
    """§54's comparison needs a control, and a control that required editing the code would
    be one nobody could reproduce. `outline=False` is that arm, and it is the same flag a
    book planned by hand wants — the drafting path already treats a scene with no statement
    as ordinary."""
    from litharness.application.planner import make_plan_selector

    a_book(store, scenes=12)
    selected = make_plan_selector(project_id=PROJECT_ID, outline=False)(
        store, "worker-a", START, 60.0
    )
    assert selected is not None
    assert selected.job_kind != BOOK_OUTLINE, "no statement is planned"
    # And the book still drafts: the control arm is a degraded book, never a stalled one.
    assert "This scene:" not in str(selected.payload["prompt"])


# -- the cadence schedule reaching books the outline never touches (pilot 14 §3) -----------


@pytest.mark.parametrize("drafted", range(6))
def test_the_beat_fires_at_six_scenes_where_no_outline_ever_runs(
    store: SqliteStore, drafted: int
) -> None:
    """Pilot 14 §3's dead spot, closed: the whole six-scene schedule, at the selector.

    §155.3 schedules scene 1 always, "however short the book" — but the beat's only fold
    lived in `outline_proposal`, and a six-scene book has six distinct dramatic functions,
    so `needs_outline` never holds, no `SCENE_PLAN` is ever written, and the fold was
    unreachable at exactly the standard pilot length. Pilot 14 measured it live and redrew
    at eight scenes; this walks all six selections on a fresh store each and pins that the
    prompt carries the beat exactly on `beat_ordinals(6)` — scheduled scenes gain it,
    inside the scene plan, which renders last, and unscheduled scenes keep the bare prompt,
    which is the byte-identical control §155.3 says the schedule is read against.

    **Corrected in place on 2026-08-30 (§173), name kept.** This asserted the prompt *ended* with
    `BEAT_TAIL`, which was true while the progression beat was the only thing appended to a scene
    plan. §173 appends a second scheduled item after it — the interaction beat — on `with_beat`'s
    own stated rule that each is one more thing that happens in the scene and that leading with
    one would make every scheduled scene read as that kind of scene first. What this test is for
    is that the schedule fires where it should and nowhere else; that is what is asserted below.
    """
    from litharness.application.planner import make_plan_selector

    revision = a_book(store, scenes=6)
    if drafted:
        filled = revision.replacing(
            revision.node(f"scene-{index}").with_content("Drafted scene. " * 40)
            for index in range(1, drafted + 1)
        )
        store.commit_revision(filled, created_at="2026-08-16T01:00:00Z")

    job = make_plan_selector(project_id=PROJECT_ID)(store, "worker-a", START, 60.0)
    assert job is not None
    assert job.job_kind != BOOK_OUTLINE, "six distinct functions leave nothing to outline"
    ordinal = drafted + 1
    assert job.payload["logical_id"] == f"scene-{ordinal}"
    prompt = str(job.payload["prompt"])
    # **A second schedule folds into the same line, added 2026-08-30 (§175).** The opening's
    # cast bound rides after the beat, so on scenes 1 and 2 the last thing in the prompt is
    # the bound and not the beat's tail. Both halves below are restated against the pair
    # rather than against the beat alone; what they still pin is that nothing is appended off
    # either schedule, which is the byte-identical control §155.3 is read against.
    bounded = staging.bounds_opening(ordinal)
    assert (staging.bound_text() in prompt) is bounded
    if ordinal in genre.beat_ordinals(6):
        assert genre.BEAT_TAIL in prompt
        tail = prompt.rstrip()[prompt.rstrip().index(genre.BEAT_TAIL) :]
        last = staging.bound_text() if bounded else genre.BEAT_TAIL
        # 2026-09-01 (§195): the opening's two beats are the last render-time fold on the
        # first chapter's scenes, after the interaction beat; still nothing off a schedule.
        assert tail.endswith(
            (genre.INTERACTION_BEAT, last, genre.OPENING_FIRST, genre.OPENING_HOOK)
        ), (
            "the scheduled folds render last and in composition order - beat, then the "
            "opening's bound, then the interaction beat where one fires - and nothing "
            "off either schedule follows them"
        )
    else:
        assert genre.BEAT_TAIL not in prompt
        if not bounded:
            assert "This scene:" not in prompt, "an unscheduled scene keeps the bare prompt"


@pytest.mark.parametrize("scenes", range(4, 25))
def test_the_schedule_is_reachable_at_every_length_the_pipeline_takes(
    store: SqliteStore, scenes: int
) -> None:
    """No length may be a dead spot again — the flag-mismatch shape, swept rather than spotted.

    Pilot 14 §3 classes the six-scene gap with pilot 12 §5's silent failures: a feature keyed
    to a condition the standard recipe never meets. A point regression at six would only pin
    the length that has already bitten, so this sweeps every count from below the template
    floor to the serial-arc default. Below six, `arc_template` refuses — a book that cannot
    carry the named beats has no schedule to miss, and the refusal is the documented behaviour.
    From six up, whatever path the book takes to a draftable scene — no outline at exactly
    six, an outline everywhere `rising` repeats — scene 1's prompt carries the beat, because
    `beat_ordinals` schedules scene 1 always.
    """
    from litharness.application.planner import make_plan_selector

    if scenes < 6:
        with pytest.raises(TemplateMismatch):
            arc_template(scenes)
        return

    a_book(store, scenes=scenes)
    functions = arc_template(scenes).functions
    if len(set(functions)) < len(functions):
        # `with_schedule`, not `payload_for` (§158): a floor-clearing book's outline must
        # answer the milestone ask, or the refusal re-enqueues the outline this asserts gone.
        make_outline_handler(StubPlanner(with_schedule(scenes)), store, PROJECT_ID)(
            _job(store), START
        )
    else:
        assert scenes == 6, "six is the one all-distinct length — the dead spot was here"

    job = make_plan_selector(project_id=PROJECT_ID)(store, "worker-a", START + 1, 60.0)
    assert job is not None
    assert job.job_kind != BOOK_OUTLINE
    assert job.payload["logical_id"] == "scene-1"
    assert genre.BEAT_TAIL in str(job.payload["prompt"])


def test_the_control_arm_holds_back_the_scheduled_beat_too(store: SqliteStore) -> None:
    """`outline=False` keeps the bare pre-plan prompt reproducible — beat included.

    The beat costs no model call, but it rides the plan line, and a no-plan-side-text arm
    that could only be produced by editing code is exactly the control the flag exists to
    prevent needing. Asserted at six scenes, where the beat arrives with no outline at all,
    so the flag is shown to gate the derived fold and not just the statements.
    """
    from litharness.application.planner import make_plan_selector

    a_book(store, scenes=6)
    job = make_plan_selector(project_id=PROJECT_ID, outline=False)(
        store, "worker-a", START, 60.0
    )
    assert job is not None
    assert job.job_kind != BOOK_OUTLINE
    prompt = str(job.payload["prompt"])
    assert genre.BEAT_TAIL not in prompt
    assert "This scene:" not in prompt


# -- the progression schedule (§52's third taxonomy entry) ---------------------------------
# `SEED` lives beside `a_book` now (§158): the fixture's own sheet and the schedule tests
# must agree on one set of keys.


def seeded_book(store: SqliteStore, scenes: int = 12):  # type: ignore[no-untyped-def]
    revision = a_book(store, scenes=scenes)
    store.record_state_records(
        BOOK_ID,
        BRANCH_ID,
        [
            lc.StateRecord(
                record_id="rec-seed",
                kind=lc.StateRecordKind.ASSERTION,
                subject="kestrel",
                predicate="status_snapshot",
                value=dict(SEED),
                authority=lc.StateAuthority.ACCEPTED_CANON,
            )
        ],
        created_at="2026-08-16T00:00:00Z",
    )
    return revision


def with_schedule(count: int, milestones: list[dict] | None = None) -> dict:
    # The default schedule keeps only the ordinals the book has: a milestone naming a scene
    # that does not exist is one of `_milestones`' refusals, and the length sweep runs this
    # from seven scenes up.
    payload = payload_for(count)
    payload["milestones"] = milestones if milestones is not None else [
        entry
        for entry in (
            {"ordinal": 3, "state": {"gold": 4}},
            {"ordinal": 7, "state": {"level": 2, "hp_max": 24, "gold": 9}},
            {"ordinal": 11, "state": {"level": 3, "hp": 12, "gold": 2}},
        )
        if entry["ordinal"] <= count
    ]
    return payload


def test_a_schedule_that_schedules_stasis_is_refused() -> None:
    """The check that is about §52's third entry rather than about the schema.

    Thirty scenes produced 31 status records holding **two** distinct ledger states: gold
    moved once in scene 1 and nothing moved again. A schedule whose milestones all restate
    the starting sheet would reproduce exactly that while looking like a fix — so it is
    refused, for the same reason an outline that repeats itself is.
    """
    revision = new_book(BOOK_ID, BRANCH_ID, title="Book", scenes=12)
    beats = beats_for(revision, arc_template(12))
    flat = [{"ordinal": n, "state": {"gold": SEED["gold"]}} for n in (3, 7, 11)]

    with pytest.raises(OutlineOutputError, match="stasis"):
        _milestones(with_schedule(12, flat), beats, SEED)


def test_a_flat_stretch_between_milestones_is_refused() -> None:
    """Two consecutive milestones that are identical tell the scenes between them to change
    nothing, which is the frozen ledger at a smaller scale."""
    revision = new_book(BOOK_ID, BRANCH_ID, title="Book", scenes=12)
    beats = beats_for(revision, arc_template(12))
    repeated = [
        {"ordinal": 3, "state": {"gold": 4}},
        {"ordinal": 7, "state": {"gold": 4}},
        {"ordinal": 11, "state": {"level": 3}},
    ]
    with pytest.raises(OutlineOutputError, match="consecutive"):
        _milestones(with_schedule(12, repeated), beats, SEED)


def test_a_schedule_may_not_invent_a_statistic() -> None:
    """A model free to add an `xp` the book's canon has never held would have
    `render_status_line` asking every scene for a field the extractor cannot read back —
    inventing a game system rather than scheduling the one the book has."""
    revision = new_book(BOOK_ID, BRANCH_ID, title="Book", scenes=12)
    beats = beats_for(revision, arc_template(12))
    invented = [{"ordinal": 5, "state": {"xp": 400, "stamina": 3}}]
    with pytest.raises(OutlineOutputError, match="invents"):
        _milestones(with_schedule(12, invented), beats, SEED)


def test_a_schedule_may_not_schedule_an_impossible_state() -> None:
    """The check the other three did not make, and §56.5 measured what it costs.

    A live outline placed `mp 6` against the seed's `mp_max 4`. It passed every existing
    rule — the field is not invented, the schedule is not flat, the state is not stasis — so
    `milestone_records` wrote it `PROPOSED`, and from then on `progression_target` handed
    every earlier scene an impossible line as the state to move toward. `MP 6/4` then reached
    accepted canon twice across twelve ACCEPT decisions and zero findings, because
    `detect_contradictions` compares records against each other and cannot see one record
    that is incoherent by itself.

    The milestone need only name `mp`: the merge against the seed supplies `mp_max`, which is
    what makes the proposed state checkable rather than the fragment checkable.
    """
    revision = new_book(BOOK_ID, BRANCH_ID, title="Book", scenes=12)
    beats = beats_for(revision, arc_template(12))
    over_ceiling = [
        {"ordinal": 4, "state": {"gold": 20}},
        {"ordinal": 9, "state": {"mp": 6}},
    ]
    with pytest.raises(OutlineOutputError, match="a ceiling is not a target"):
        _milestones(with_schedule(12, over_ceiling), beats, SEED)


def test_a_milestone_may_raise_a_ceiling_it_also_fills() -> None:
    """The negative control for the rule above: levelling up raises `mp_max` and refills
    `mp`, which is the genre's most ordinary progression beat. A check that only compared
    against the *seed's* ceiling would refuse it, so the comparison is within the milestone's
    own proposed state."""
    revision = new_book(BOOK_ID, BRANCH_ID, title="Book", scenes=12)
    beats = beats_for(revision, arc_template(12))
    levelled = [{"ordinal": 6, "state": {"level": 2, "mp": 8, "mp_max": 8}}]
    schedule = _milestones(with_schedule(12, levelled), beats, SEED)
    assert [beat.ordinal for beat, _ in schedule] == [6]


def test_costs_count_as_progression() -> None:
    """A number that falls is still a milestone: a price paid is progression on the page.

    **Reworded 2026-08-24; the assertion is unchanged.** It read "a debt story progresses by
    spending as well as by gaining ... the book this system is being built for", which is the
    genre frame the operator refused three times out of three (stage-0 §116) stated as this
    project's own purpose. What the check is actually protecting is general and survives the
    frame: a milestone written as "the numbers go up" cannot see a scene whose whole content is
    what something cost, and `plan/clarity-audit-2026-08-24.md` C6 deleted the debt-story
    assertion from the milestone rule for the same reason.
    """
    revision = new_book(BOOK_ID, BRANCH_ID, title="Book", scenes=12)
    beats = beats_for(revision, arc_template(12))
    spending = [
        {"ordinal": 4, "state": {"gold": 6}},
        {"ordinal": 9, "state": {"gold": 0, "hp": 11}},
    ]
    schedule = _milestones(with_schedule(12, spending), beats, SEED)
    assert [beat.ordinal for beat, _ in schedule] == [4, 9]


def test_milestones_are_proposed_and_therefore_cannot_reach_a_packet() -> None:
    """The property that makes a schedule safe and the reason it needed no new storage.

    `is_canon` excludes `PROPOSED`, so the context packet never hands a milestone to a scene
    as established fact and `detect_contradictions` never weighs one against the prose. It
    informs generation and contaminates nothing.
    """
    from litharness.domain import state as state_mod

    revision = new_book(BOOK_ID, BRANCH_ID, title="Book", scenes=12)
    beats = beats_for(revision, arc_template(12))
    schedule = _milestones(with_schedule(12), beats, SEED)
    records = milestone_records(schedule, subject="kestrel", seed=SEED)

    assert records
    for record in records:
        assert record.authority is lc.StateAuthority.PROPOSED
        assert not state_mod.is_canon(record)
        assert record.story_position is not None
        # The seed's keys carried forward, so a milestone is a whole sheet rather than a diff
        # the extractor would have to merge.
        assert set(record.value) == set(SEED)


def test_a_milestone_is_placed_where_the_sheet_says_the_scene_sits() -> None:
    """Never at an invented position. `story_order_key` is `None` exactly when the template
    is not entitled to say, and a schedule refuses rather than guessing."""
    from dataclasses import replace as dc_replace

    revision = new_book(BOOK_ID, BRANCH_ID, title="Book", scenes=12)
    beats = beats_for(revision, arc_template(12))
    schedule = _milestones(with_schedule(12), beats, SEED)
    records = milestone_records(schedule, subject="kestrel", seed=SEED)
    assert [r.story_position.order_key for r in records] == [
        beat.story_order_key for beat, _ in schedule
    ]

    unplaced = [dc_replace(beat, story_order_key=None) for beat in beats]
    with pytest.raises(OutlineOutputError, match="no story position"):
        _milestones(with_schedule(12), unplaced, SEED)


def test_the_handler_writes_a_schedule_the_planner_can_already_read(
    store: SqliteStore,
) -> None:
    """End to end into the function that had no producer.

    `progression_target` has been able to read a schedule since §46 and nothing anywhere
    wrote one — a complete measuring instrument with nothing to measure, which §19.1 names as
    the shape to search for. This is the producer.
    """
    from litharness.domain.extraction import progression_target

    seeded_book(store, scenes=12)
    planner = StubPlanner(with_schedule(12))
    make_outline_handler(planner, store, PROJECT_ID)(_job(store), START)

    records = store.state_records(BOOK_ID, BRANCH_ID)
    milestones = [r for r in records if r.record_id.startswith("milestone-")]
    assert len(milestones) == 3

    # And the loop can read it: a scene early in the book aims at the next milestone.
    target = progression_target(records, at="s01")
    assert target is not None
    # Integers, not floats: the status line is what the generator writes and the extractor
    # reads back, and a canon ledger of integers must not be scheduled in decimals.
    assert "Gold 4" in target and "4.0" not in target


def test_a_book_that_does_not_speak_system_voice_gets_no_schedule(
    store: SqliteStore,
) -> None:
    """A stat block in a locked-room mystery is not a smaller error than a missing one, so
    the schedule is asked for only where the book already states its state on the page — the
    same question `render_prompt` asks before requesting a status line."""
    # `sheet=False` since §158: a prose-valued snapshot used to stand in for "does not
    # speak" here, and a prose sheet now floors the book instead of half-counting. A job can
    # still reach the handler for such a book — enqueued before the sheet existed, or under
    # `DraftPolicy(require_starting_sheet=False)` — and the handler must still not schedule.
    a_book(store, scenes=12, sheet=False)
    planner = StubPlanner(payload_for(12))  # and no milestones in the answer
    make_outline_handler(planner, store, PROJECT_ID)(_job(store), START)

    records = store.state_records(BOOK_ID, BRANCH_ID)
    assert [r for r in records if r.record_id.startswith("milestone-")] == []
    assert "starting_state" in str(planner.requests[0].prompt)  # type: ignore[attr-defined]
    assert "milestones" not in str(planner.requests[0].prompt).split("rules")[-1]


def test_a_refused_outline_writes_no_schedule(store: SqliteStore) -> None:
    """A schedule without the statements it was written against is a book planned twice over
    by two different answers, so the milestones land after the plan or not at all."""
    seeded_book(store, scenes=12)
    repeated = list(DISTINCT[:12])
    repeated[4] = repeated[1]
    payload = with_schedule(12)
    payload["scenes"] = payload_for(12, statements=repeated)["scenes"]

    make_outline_handler(StubPlanner(payload), store, PROJECT_ID)(_job(store), START)

    records = store.state_records(BOOK_ID, BRANCH_ID)
    assert [r for r in records if r.record_id.startswith("milestone-")] == []


def test_running_the_outline_twice_writes_one_schedule(store: SqliteStore) -> None:
    """Derived record ids, so a replayed job converges rather than accumulating a second
    schedule beside the first."""
    seeded_book(store, scenes=12)
    handle = make_outline_handler(StubPlanner(with_schedule(12)), store, PROJECT_ID)
    handle(_job(store), START)
    handle(_job(store), START + 1)
    records = store.state_records(BOOK_ID, BRANCH_ID)
    assert len([r for r in records if r.record_id.startswith("milestone-")]) == 3


def test_volunteered_payoff_windows_are_ignored_when_the_book_owes_nothing(
    store: SqliteStore,
) -> None:
    """An answer to a question that was not put must not refuse the outline.

    The prompt asks for payoff windows **only** when the ledger has open rows, and the ledger
    is empty at every book's *first* outline, because promises are written by the summary
    handler after a scene is accepted. Measured on Serial Pilot 1: the model volunteered a
    window naming a promise the book had never opened, and validating it burned two of the
    outline's three attempts on a good outline. §19.1 — a refusal reached before the work
    costs time, never the unit.
    """
    from litharness.domain.policy import Outcome

    a_book(store, scenes=12)
    payload = with_schedule(12)
    payload["payoff_windows"] = [
        {"subject": "a debt this book never opened", "first_scene": 3, "last_scene": 9}
    ]
    handle = make_outline_handler(StubPlanner(payload), store, PROJECT_ID)

    handle(_job(store), START)

    [decision] = store.decisions_for_job("outline-job")
    assert decision.outcome is Outcome.ACCEPT, decision.reason


# -- the rung schedule (plan/stage-0-decisions.md §113) -------------------------------------

LADDER = world_brief.Ladder(
    protagonist="silas",
    criterion="assay_grade",
    rungs=(
        ("third_seal", "a lead seal that greens in a week", "a year of unpaid readings"),
        ("second_seal", "a brass seal worn at the throat", "a ruined reputation elsewhere"),
        ("first_seal", "a silver seal nobody hands back", "the name of whoever held it"),
    ),
    opening_rung="third_seal",
)


def _rising(*pairs: tuple[int, str]) -> dict:
    # On `with_schedule` rather than `payload_for` since §158: `a_book` now seeds a real
    # sheet, so a handler run on it is asked for a progression schedule too, and a stub
    # reply without one refuses the whole outline before the rung schedule is reached.
    payload = with_schedule(12)
    payload["standing_milestones"] = [
        {"ordinal": ordinal, "rung": rung} for ordinal, rung in pairs
    ]
    return payload


def _twelve_beats():  # type: ignore[no-untyped-def]
    return beats_for(new_book(BOOK_ID, BRANCH_ID, title="Book", scenes=12), arc_template(12))


def test_a_book_with_no_ladder_is_asked_nothing_about_one() -> None:
    """The control: a world brief without a ladder renders the request it rendered before.

    Both golden fixtures and every world forged before 2026-08-22 are in this state, and the
    request has to be byte-identical for `input_digest_for`'s reason.
    """
    beats = _eight_beats()
    world = world_brief.WorldBrief(
        groups=(("rules", ("Rule — history fixes price",)),), criteria=None, reveals=()
    )
    withoutled = render_outline_request(PREMISE, beats, base=_bare_base(), world=world)
    body = json.loads(withoutled.prompt)
    assert "ladder" not in body["world"]
    assert not any("standing_milestones" in rule for rule in body["rules"])

    withled = render_outline_request(
        PREMISE, beats, base=_bare_base(), world=replace(world, ladder=LADDER)
    )
    ladder_body = json.loads(withled.prompt)
    assert ladder_body["world"]["ladder"]["opening_rung"] == "third_seal"
    assert [entry["id"] for entry in ladder_body["world"]["ladder"]["rungs"]] == [
        "third_seal",
        "second_seal",
        "first_seal",
    ]
    assert ladder_body["world"]["ladder"]["rungs"][0]["cost_to_reach"]
    assert any("standing_milestones" in rule for rule in ladder_body["rules"])
    assert any("silas" in rule for rule in ladder_body["rules"])


def test_the_ladder_rules_ask_for_a_schedule_and_never_for_a_feeling() -> None:
    """**The §113 standing boundary, asserted rather than trusted.**

    A rung and its price are declared facts of the world, the same class as the numbers the
    milestone rules beside these already schedule. How a scene handles reaching one is the
    writer's and the operator's, and a rule here that reached for a verb about it would be this
    system's own taste arriving in every outline it renders.
    """
    for rule in world_brief.LADDER_RULES:
        lowered = rule.lower()
        for forbidden in (
            "earn", "deserve", "triumph", "victory", "feel", "felt", "emotion",
            "satisfying", "reward", "celebrate", "climax", "payoff", "pay it off",
            "exciting", "epic", "hard-won", "struggle", "hero",
        ):
            assert forbidden not in lowered, (forbidden, rule)
    joined = " ".join(world_brief.LADDER_RULES).lower()
    assert "must actually move" in joined
    assert "never moves down" in joined


def test_a_schedule_that_never_rises_is_refused() -> None:
    """Stasis, a flat stretch, a fall, and a rung the world never declared — four refusals.

    The first is the defect this whole slice exists for, arriving as a schedule: two chapters
    of a forged serial in which the protagonist's standing was never declared, never scheduled
    and never moved.
    """
    beats = _twelve_beats()

    with pytest.raises(OutlineOutputError, match="repeats the opening rung"):
        _standing_milestones(_rising((3, "third_seal"), (7, "third_seal")), beats, LADDER)

    with pytest.raises(OutlineOutputError, match="flat stretch"):
        _standing_milestones(
            _rising((3, "second_seal"), (7, "second_seal"), (11, "first_seal")),
            beats,
            LADDER,
        )

    with pytest.raises(OutlineOutputError, match="goes down"):
        _standing_milestones(
            _rising((3, "second_seal"), (7, "third_seal"), (11, "first_seal")),
            beats,
            LADDER,
        )

    with pytest.raises(OutlineOutputError, match="the ladder holds"):
        _standing_milestones(_rising((3, "platinum_seal")), beats, LADDER)

    with pytest.raises(OutlineOutputError, match="which does not exist"):
        _standing_milestones(_rising((99, "second_seal")), beats, LADDER)

    with pytest.raises(OutlineOutputError, match="more than one standing milestone"):
        _standing_milestones(
            _rising((3, "second_seal"), (3, "first_seal")), beats, LADDER
        )


def test_a_rising_schedule_becomes_proposed_edges_the_page_never_sees_as_fact() -> None:
    """`milestone_records`' argument exactly: PROPOSED informs generation and contaminates
    nothing, and the criterion rides on the edge so two ladders cannot be spliced."""
    beats = _twelve_beats()
    schedule = _standing_milestones(
        _rising((3, "second_seal"), (7, "first_seal")), beats, LADDER
    )
    assert [beat.ordinal for beat, _ in schedule] == [3, 7]

    records = standing_milestone_records(
        schedule, subject=LADDER.protagonist, criterion=LADDER.criterion
    )
    assert [record.record_id for record in records] == ["standing-s03", "standing-s07"]
    assert {record.authority for record in records} == {lc.StateAuthority.PROPOSED}
    assert [record.object_ref for record in records] == ["second_seal", "first_seal"]
    assert {record.value for record in records} == {"assay_grade"}
    assert {record.predicate for record in records} == {worlds.STANDS_AT_PREDICATE}
    # Derived from the position, so a replayed outline converges rather than accumulating a
    # second schedule beside the first.
    again = standing_milestone_records(
        schedule, subject=LADDER.protagonist, criterion=LADDER.criterion
    )
    assert [r.record_id for r in again] == [r.record_id for r in records]


def test_the_handler_writes_the_rung_schedule_only_for_a_book_that_has_a_ladder(
    store: SqliteStore,
) -> None:
    """End to end, both directions: a book with a chain gets PROPOSED standings on the record,
    and a book without one is asked nothing and gets none — the same guard the milestone
    schedule runs under."""
    a_book(store, scenes=12)
    store.record_state_records(
        BOOK_ID, BRANCH_ID, _canon_ladder(), created_at="2026-08-22T00:00:00Z"
    )
    planner = StubPlanner(_rising((3, "second_seal"), (7, "first_seal")))
    make_outline_handler(planner, store, PROJECT_ID)(_job(store), START)

    written = [
        record
        for record in store.state_records(BOOK_ID, BRANCH_ID)
        if record.record_id.startswith("standing-")
    ]
    assert [record.object_ref for record in written] == ["second_seal", "first_seal"]
    assert {record.authority for record in written} == {lc.StateAuthority.PROPOSED}
    body = json.loads(str(planner.requests[0].prompt))  # type: ignore[attr-defined]
    assert body["world"]["ladder"]["protagonist"] == "silas"

    # The schedule aims at the next rung from where the book is, which is the whole point of
    # placing the opening standing rather than leaving it unplaced.
    records = store.state_records(BOOK_ID, BRANCH_ID)
    assert "second_seal (2 of 3)" in (standing_target(records, at="s01") or "")


def test_a_book_with_no_ladder_gets_no_standing_schedule(store: SqliteStore) -> None:
    """A book whose canon declares no chain is asked no standing question, so a volunteered
    answer refuses nothing — the failure `_payoff_windows` records for its own first outline."""
    a_book(store, scenes=12)
    planner = StubPlanner(_rising((3, "second_seal")))
    make_outline_handler(planner, store, PROJECT_ID)(_job(store), START)

    records = store.state_records(BOOK_ID, BRANCH_ID)
    assert [r for r in records if r.record_id.startswith("standing-")] == []
    body = json.loads(str(planner.requests[0].prompt))  # type: ignore[attr-defined]
    assert not any("standing_milestones" in rule for rule in body["rules"])
    # And the outline still landed: an unasked question's answer refuses nothing.
    plan = store.plan_revision(BOOK_ID, BRANCH_ID)
    assert plan is not None
    assert scene_plan_for(plan.items, "scene-1") is not None


def _canon_ladder() -> list[lc.StateRecord]:
    """A three-rung ordinal chain with silas standing on its bottom rung, as canon."""
    out = [
        worlds.world_record(
            "assay_grade",
            worlds.TYPE_PREDICATE,
            value=worlds.CRITERION,
            authority=lc.StateAuthority.ACCEPTED_CANON,
        ),
        worlds.world_record(
            "assay_grade",
            worlds.COMPARATOR_PREDICATE,
            value="ordinal",
            authority=lc.StateAuthority.ACCEPTED_CANON,
        ),
        worlds.world_record(
            "silas",
            worlds.ENTITY_ROLE_PREDICATE,
            value="protagonist",
            authority=lc.StateAuthority.ACCEPTED_CANON,
        ),
        worlds.world_record(
            "silas",
            worlds.STANDS_AT_PREDICATE,
            object_ref="third_seal",
            value="assay_grade",
            order_key="s01",
            authority=lc.StateAuthority.ACCEPTED_CANON,
        ),
    ]
    for rung, form, cost in LADDER.rungs:
        out.append(
            worlds.world_record(
                rung,
                worlds.MANIFESTS_PREDICATE,
                value=form,
                authority=lc.StateAuthority.ACCEPTED_CANON,
            )
        )
        out.append(
            worlds.world_record(
                rung, "costs", value=cost, authority=lc.StateAuthority.ACCEPTED_CANON
            )
        )
    for lower, higher in (("third_seal", "second_seal"), ("second_seal", "first_seal")):
        out.append(
            worlds.world_record(
                lower,
                worlds.PRECEDES_PREDICATE,
                object_ref=higher,
                value="assay_grade",
                authority=lc.StateAuthority.ACCEPTED_CANON,
            )
        )
    return out
