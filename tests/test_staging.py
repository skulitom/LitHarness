"""The opening's cast bound: how many people the first scenes may name.

`plan/serial-pilot-15b.md`'s read-10 section is why this file exists. The chapter the
coordinator's gate passed staged five named people and named four more offstage in 1,903
words, and nothing between the world and the page bounded any of it: the packet's cast
section is the one part with no scene scoping, so at a budget spending 2.5% of its ceiling
every declared person reached every scene, and the writer used all nine.

The pair that carries the argument is
`test_the_opening_carries_the_bound_and_the_scenes_after_it_do_not` against
`test_the_packet_still_carries_every_person_the_world_declares`. The first is the fix; the
second is the anti-scope made executable — the town is not forbidden, and a writer that
cannot see a person still cannot use a fact about them.
"""

from __future__ import annotations

import json

import litharness_contracts as lc
import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.outline import outline_proposal
from litharness.application.planner import make_plan_selector
from litharness.domain import genre, house, staging
from litharness.domain.beats import SIX_BEAT, beats_for
from litharness.domain.context import CAST, assemble
from litharness.domain.draft import DraftPolicy
from litharness.domain.generation import CompletionResult, Usage
from litharness.domain.plans import import_plan
from litharness.domain.revision import import_manuscript, new_book
from litharness.domain.state import import_state

START = 1_760_000_000.0


# --- the schedule ------------------------------------------------------------------------


def test_the_opening_is_the_first_scenes_and_nothing_later() -> None:
    assert staging.bounds_opening(1)
    assert staging.bounds_opening(staging.OPENING)
    assert not staging.bounds_opening(staging.OPENING + 1)
    # A book shorter than the opening is all opening; a zero-length one has no scenes to bound.
    assert staging.bounds_opening(1, opening=1)
    assert not staging.bounds_opening(1, opening=0)
    assert not staging.bounds_opening(0)
    with pytest.raises(ValueError):
        staging.bounds_opening(1, opening=-1)


def test_a_later_arc_does_not_open_the_book_again() -> None:
    """Beats are arc-scoped on an open-ended serial, so every arc has an ordinal 1.

    A bound keyed to the ordinal alone would hand arc five a fresh opening and tell a book
    two hundred scenes in that it may name three people.
    """
    assert staging.bounds_opening(1, arc_index=1)
    assert not staging.bounds_opening(1, arc_index=2)
    assert not staging.bounds_opening(1, arc_index=17)
    # A book with no arcs is opened by its own first scenes.
    assert staging.bounds_opening(1, arc_index=None)


def test_an_unbounded_scene_is_left_byte_identical() -> None:
    """The control this whole change is read against."""
    statement = "Corin counts the jars and finds one short."
    assert staging.with_bound(statement, staging.OPENING + 1) == statement
    assert staging.with_bound(statement, 1, arc_index=3) == statement
    assert staging.with_bound("", staging.OPENING + 1) == ""


def test_a_bounded_scene_gains_the_bound_after_its_own_statement() -> None:
    statement = "Corin counts the jars and finds one short."
    got = staging.with_bound(statement, 1)
    assert got.startswith(statement), "the scene's own statement must lead"
    assert got.endswith(staging.bound_text())
    # An unpunctuated statement is still joined into two readable sentences.
    assert staging.with_bound("Corin counts the jars", 1) == (
        f"Corin counts the jars. {staging.bound_text()}"
    )
    # An empty statement is a contract, not an edge case: the bare bound.
    assert staging.with_bound("   ", 1) == staging.bound_text()


def test_the_bound_lands_after_the_progression_beat_and_neither_loses_its_sentence() -> None:
    """Statement, then what else the scene contains, then what it may not also contain.

    Both folds are composed at both of their call sites, so an ordering that only held in
    one of them would be a book whose opening scenes read differently depending on whether
    it happened to take an outline.
    """
    statement = "Corin counts the jars and finds one short."
    got = staging.with_bound(genre.with_beat(statement, 1, 6), 1)
    assert got.startswith(statement)
    assert genre.BEAT in got
    assert got.endswith(staging.bound_text())
    assert got.index(genre.BEAT) < got.index(staging.bound_text())


# --- what the sentence may say -----------------------------------------------------------


def test_the_bound_is_a_count_and_carries_no_quality_word() -> None:
    """§154: a demand whose object is a reader's state names nothing a writer can emit.

    A count of names is the opposite — names on a page are countable by whoever put them
    there — so the sentence says how many, never how well.
    """
    text = staging.bound_text().lower()
    for word in (
        "interesting",
        "good",
        "compelling",
        "engaging",
        "focused",
        "tight",
        "clean",
        "memorable",
        "meaningful",
        "important",
        "clearly",
        "properly",
    ):
        assert word not in text, f"the bound reaches for a quality word: {word!r}"
    leaked = sorted(word for word in house.MACHINERY_WORDS if word in text)
    assert not leaked, f"the bound speaks this system's own vocabulary: {leaked}"


def test_the_bound_assumes_nothing_about_who_the_book_is_about() -> None:
    """It reaches the opening of every book, so it may not decide anybody's gender."""
    words = set(staging.bound_text().lower().replace(",", " ").replace(";", " ").split())
    assert not words & {"he", "him", "his", "she", "her", "hers", "himself", "herself"}


def test_the_bound_says_what_to_do_instead_of_the_thing_it_forbids() -> None:
    """A ceiling handed over alone is answered by emptying the room.

    The packet's hidden section carries the same two-clause shape for the same failure: told
    a prohibition and nothing else, a generator writes around the hole. The second clause is
    what keeps a large world cast available to a bounded scene — unnamed people are not
    bounded at all.
    """
    assert "unnamed" in staging.bound_text()
    # Semicolon-joined, so the pair costs one demand rather than two — and the ceiling and
    # its alternative cannot be separated by an edit that keeps only the half that forbids.
    assert len(house.demands(staging.bound_text())) == 1


def test_the_sentence_is_rendered_from_the_constant_rather_than_written_beside_it() -> None:
    """A number in prose and a number in code drift; this file is where that would show."""
    assert "three" in staging.bound_text()
    assert "two" in staging.bound_text(named=2)
    assert "no" in staging.bound_text(named=0)
    with pytest.raises(ValueError):
        staging.bound_text(named=99)
    with pytest.raises(ValueError):
        staging.bound_text(named=-1)


# --- the anti-scope ----------------------------------------------------------------------


def _person(record_id: str, subject: str, predicate: str, value: str) -> lc.StateRecord:
    return lc.StateRecord(
        record_id=record_id,
        kind=lc.StateRecordKind.RELATIONSHIP,
        subject=subject,
        predicate=predicate,
        value=value,
        authority=lc.StateAuthority.ACCEPTED_CANON,
    )


def test_the_packet_still_carries_every_person_the_world_declares() -> None:
    """**The town is not forbidden and the packet is not cut.**

    Two candidate orders to cut it by were checked against the book that produced the
    complaint and both failed: adjacency to the protagonist selects one person there, and
    glossing only the people the other sections name selects nine of nine. A selection rule
    with no honest order would withhold whichever person a scene actually needed, which is
    §112's four-of-five cast members who never reached either chapter. So the bound is on the
    page and the packet is unchanged, and this test is what would go red if a later track
    quietly cut the section instead.
    """
    revision = new_book("book-staging", "main", title="Staging", scenes=2)
    records = [
        _person("r1", "mira", "entity_role", "protagonist"),
        _person("r2", "mira", "manifests_as", "She asks what a thing is for."),
        _person("r3", "baz", "entity_role", "cast"),
        _person("r4", "baz", "manifests_as", "Brings the day's second loaf."),
        _person("r5", "teal", "entity_role", "cast"),
        _person("r6", "hesper", "entity_role", "cast"),
        _person("r7", "sabra", "entity_role", "cast"),
    ]
    packet = assemble(revision, "scene-1", state_records=records)
    subjects = {item.source_logical_id for item in packet.sections.get(CAST, ())}
    assert subjects == {"mira", "baz", "teal", "hesper", "sabra"}
    assert not [omission for omission in packet.omitted if "cast" in omission.reason]


# --- the two call sites ------------------------------------------------------------------


def _fixture(store: SqliteStore, name: str) -> tuple[str, str]:
    """Import a golden book, its plan and its state, exactly as `cli import` does.

    Written out here rather than imported from another test module, on
    `tests/test_genre_floor.py`'s recorded reason: this file's subject is what the live
    drafting path composes for a real book, and reaching into another module for the loader
    would put that subject somewhere it can move without these tests noticing.
    """
    from litharness.adapters.contracts_fixtures import (
        fixture_manuscript,
        fixture_plans,
        fixture_state,
    )

    manuscript = lc.parse_artifact(
        lc.ManuscriptRevision,
        json.loads(fixture_manuscript(name).read_text(encoding="utf-8")),
    )
    revision = import_manuscript(manuscript).revision
    store.commit_revision(revision, created_at="2026-08-13T00:00:00Z")

    plan = import_plan(
        lc.parse_artifact(
            lc.PlanSnapshot, json.loads(fixture_plans(name).read_text(encoding="utf-8"))
        ),
        book_id=revision.book_id,
        branch_id=revision.branch_id,
    )
    store.record_plan_items(
        revision.book_id,
        revision.branch_id,
        plan.items,
        created_at="2026-08-13T00:00:00Z",
        source_revision_id=plan.source_revision_id,
    )

    state = import_state(
        lc.parse_artifact(
            lc.StateSnapshot, json.loads(fixture_state(name).read_text(encoding="utf-8"))
        ),
        book_id=revision.book_id,
        branch_id=revision.branch_id,
    )
    store.record_state_records(
        revision.book_id,
        revision.branch_id,
        state.records,
        created_at="2026-08-13T00:00:00Z",
        source_revision_id=state.source_revision_id,
    )
    return revision.book_id, revision.branch_id


@pytest.fixture
def store(tmp_path) -> SqliteStore:
    return SqliteStore.open(tmp_path / "staging.db")


def _six_scene_book(store: SqliteStore, *, drafted: int) -> tuple[str, str]:
    """A six-scene book with its first `drafted` scenes already written.

    `cli new` commits exactly this shape minus the drafting, and the parameter is what lets
    one test ask the selector about a chosen ordinal: a scene is draftable when it exists and
    says nothing, so filling the ones before it is how the next one is chosen.
    """
    revision = new_book("book-sweep", "main", title="The Sweep", scenes=6)
    store.commit_revision(revision, created_at="2026-08-13T00:00:00Z")
    if drafted:
        # A second commit, because a derived revision names the root as its parent and the
        # root has to exist for that key to resolve.
        store.commit_revision(
            revision.replacing(
                node.with_content("Drafted scene. " * 40)
                for node in revision.nodes
                if node.logical_id in {f"scene-{index}" for index in range(1, drafted + 1)}
            ),
            created_at="2026-08-13T01:00:00Z",
        )
    store.record_plan_items(
        revision.book_id,
        revision.branch_id,
        (
            lc.PlanItem(
                logical_id="plan-premise",
                kind=lc.PlanKind.PREMISE,
                text="A mender learns the town through what it brings her to fix.",
                authority=lc.PlanAuthority.INTENDED,
                locked=True,
            ),
        ),
        created_at="2026-08-13T00:00:00Z",
        source_revision_id=revision.revision_id,
    )
    return revision.book_id, revision.branch_id


@pytest.mark.parametrize("ordinal", [1, 2, 3, 4])
def test_the_opening_carries_the_bound_and_the_scenes_after_it_do_not(
    tmp_path, ordinal: int
) -> None:
    """The live drafting path, on a book that never takes an outline.

    **A fresh six-scene book rather than a golden fixture, and the difference is the sweep.**
    Six distinct dramatic functions means `needs_outline` never holds, so this is the shape
    every pilot runs in — the one where a participant list written by an outline could never
    have reached the page. A golden fixture arrives with its scenes already drafted and a
    node's content cannot be cleared, so it could only ever be asked about the one scene it
    has left, while an empty book can be asked about any ordinal and the parameters cross the
    boundary this schedule draws.

    One store per case rather than one queue drained four times: the selector keeps one draft
    in flight per book, so the second call on a store whose first job is still queued reports
    no work rather than the next scene.
    """
    store = SqliteStore.open(tmp_path / f"sweep-{ordinal}.db")
    _six_scene_book(store, drafted=ordinal - 1)
    job = make_plan_selector(
        outline=True, policy=DraftPolicy(require_starting_sheet=False)
    )(store, "worker-a", START, 300.0)
    assert job is not None, f"no work selected with {ordinal - 1} scene(s) drafted"
    assert job.payload["selected_by"]["ordinal"] == ordinal
    carried = staging.bound_text() in str(job.payload["prompt"])
    assert carried is staging.bounds_opening(ordinal), (
        f"scene {ordinal} {'carries' if carried else 'lacks'} the opening's cast bound and "
        "the schedule says otherwise"
    )


#: The outline handler's own inputs, in `tests/test_outline.py`'s shapes: a duck-typed base
#: with no items, and a result whose text nothing here reads. Statements are distinct because
#: `outline_proposal` refuses a repeat, which is the defect it was built for.
def _payload(beats) -> dict:  # type: ignore[no-untyped-def]
    return {
        "scenes": [
            {"ordinal": beat.ordinal, "statement": f"Statement {beat.ordinal}."}
            for beat in beats
        ]
    }


def _base():  # type: ignore[no-untyped-def]
    class _Base:
        plan_revision_id = "planrev-1"
        items: tuple = ()

    return _Base()


def _result() -> CompletionResult:
    return CompletionResult(text="{}", provider="stub", model="stub-v1", usage=Usage(10, 10))


def test_an_outlined_book_gets_the_bound_from_the_other_call_site() -> None:
    """Two call sites for one fold, and the un-outlined path is tested above.

    A book whose sheet cannot tell its scenes apart takes an outline, and its statements are
    stored with the bound already folded in — so the selector passes `plan_item.text`
    verbatim and must not fold a second one.
    """
    revision = new_book("book-outlined", "main", title="Outlined", scenes=6)
    beats = beats_for(revision, SIX_BEAT)
    proposal = outline_proposal(
        _payload(beats),
        base=_base(),
        beats=beats,
        project_id="project-test",
        book_id="book-outlined",
        branch_id="main",
        result=_result(),
    )
    texts = {edit.item.text for edit in proposal.edits}
    bounded = [text for text in texts if staging.bound_text() in text]
    assert len(bounded) == staging.OPENING, (
        f"{len(bounded)} of {len(texts)} outlined statements carry the bound, expected "
        f"{staging.OPENING}"
    )
    # The scene's own statement survives the fold, and the bound is last.
    for text in bounded:
        assert text.startswith("Statement ")
        assert text.endswith(staging.bound_text())


def test_a_later_arcs_outline_is_not_handed_a_fresh_opening() -> None:
    """The serial case, at the outline call site rather than the selector's."""
    revision = new_book("book-arc", "main", title="Arc", scenes=6)
    beats = beats_for(revision, SIX_BEAT)
    proposal = outline_proposal(
        _payload(beats),
        base=_base(),
        beats=beats,
        project_id="project-test",
        book_id="book-arc",
        branch_id="main",
        result=_result(),
        arc_index=4,
    )
    assert not [
        edit for edit in proposal.edits if staging.bound_text() in edit.item.text
    ]
