"""The house genre floor: a book with no starting sheet is refused before it is drafted.

`plan/serial-pilot-13.md` §8.2 is the reason this file exists. The pipeline printed *"no state
seeded — a LitRPG book needs a starting sheet to speak system voice"* on two separate databases
and drafted the book anyway, because a message is not a gate. These tests are what the message
was missing: the assertion that the run stops.

The pair that carries the argument is `test_the_litrpg_fixture_clears_the_floor` against
`test_the_mystery_fixture_is_refused_by_the_floor`. Both are golden books, both are complete
and well-formed, and the only difference between them is whether canon holds a status snapshot.
A floor that refused both would be a broken import; one that passed both would be the state
pilot 13 shipped in.
"""

from __future__ import annotations

import json

import litharness_contracts as lc
import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.planner import make_plan_selector, plan_progress
from litharness.domain import genre
from litharness.domain.draft import DraftPolicy
from litharness.domain.extraction import STATUS_PREDICATE
from litharness.domain.plans import import_plan
from litharness.domain.revision import import_manuscript
from litharness.domain.state import import_state

START = 1_760_000_000.0


@pytest.fixture
def store(tmp_path) -> SqliteStore:
    return SqliteStore.open(tmp_path / "floor.db")


def _fixture(store: SqliteStore, name: str) -> tuple[str, str]:
    """Import a golden book, its plan and its state, exactly as `cli import` does.

    Written out here rather than imported from `tests/test_planner.py`: this file's whole
    subject is what the golden state snapshot does or does not carry, and reaching into
    another test module for the loader would put that subject somewhere it can move without
    these tests noticing.
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


# --- the predicate ---------------------------------------------------------------------


def test_a_canon_status_snapshot_is_what_the_floor_asks_for() -> None:
    sheet = lc.StateRecord(
        record_id="seed",
        kind=lc.StateRecordKind.ASSERTION,
        subject="rook",
        predicate=STATUS_PREDICATE,
        value="Level 1",
        authority=lc.StateAuthority.ACCEPTED_CANON,
    )
    assert genre.has_starting_sheet([sheet])
    assert genre.genre_block([sheet]) is None


def test_a_proposed_status_snapshot_does_not_satisfy_the_floor() -> None:
    """The outline's milestone schedule mints `PROPOSED` status records.

    Counting them would let a book clear the floor with its own plan for later instead of with
    a sheet that is true now — and the plan is written by the same run that would then be
    allowed to proceed on the strength of it.
    """
    planned = lc.StateRecord(
        record_id="standing-s3",
        kind=lc.StateRecordKind.ASSERTION,
        subject="rook",
        predicate=STATUS_PREDICATE,
        value="Level 4",
        authority=lc.StateAuthority.PROPOSED,
    )
    assert not genre.has_starting_sheet([planned])
    assert genre.genre_block([planned]) is not None


def test_the_refusal_says_how_much_canon_the_book_does_have() -> None:
    """A book with plenty of canon and no sheet must not read as a book with nothing."""
    other = lc.StateRecord(
        record_id="fact",
        kind=lc.StateRecordKind.ASSERTION,
        subject="rook",
        predicate="carries",
        value="a lantern",
        authority=lc.StateAuthority.ACCEPTED_CANON,
    )
    populated = genre.genre_block([other]) or ""
    empty = genre.genre_block([]) or ""
    assert "1 state record(s)" in populated
    assert "no state records on this branch at all" in empty
    assert genre.NO_SHEET in populated and genre.NO_SHEET in empty


# --- the two golden books --------------------------------------------------------------


def test_the_litrpg_fixture_clears_the_floor(store: SqliteStore) -> None:
    book_id, branch_id = _fixture(store, "litrpg")
    records = store.state_records(book_id, branch_id)
    assert genre.has_starting_sheet(records)
    assert plan_progress(store, book_id, branch_id).blocked_reason is None


def test_the_mystery_fixture_is_refused_by_the_floor(store: SqliteStore) -> None:
    """The golden mystery is a complete, well-formed book this house would not publish."""
    book_id, branch_id = _fixture(store, "mystery")
    assert not genre.has_starting_sheet(store.state_records(book_id, branch_id))
    progress = plan_progress(store, book_id, branch_id)
    assert progress.blocked_reason is not None
    assert genre.NO_SHEET in progress.blocked_reason


def test_a_refused_book_does_not_look_finished(store: SqliteStore) -> None:
    """§ the no-premise block's argument: a blocked book reports its reason.

    `complete` reading True over a book the floor stopped is the failure that would let a
    board go green on a book that never wrote a line.
    """
    book_id, branch_id = _fixture(store, "mystery")
    progress = plan_progress(store, book_id, branch_id)
    assert not progress.complete
    # It still reports how far it actually got rather than claiming zero.
    assert progress.total > 0


def test_the_floor_refuses_in_front_of_the_spend(store: SqliteStore) -> None:
    """No job is enqueued, so no provider call is ever made for a book with no sheet.

    This is the budget gate's argument applied one step earlier. A floor that refused after
    the call would record a book that should not have been drafted; it would not prevent one.
    """
    _fixture(store, "mystery")
    assert make_plan_selector(outline=False)(store, "worker-a", START, 300.0) is None


def test_a_seeded_book_still_reaches_the_selector(store: SqliteStore) -> None:
    """The floor must refuse the unseeded book without refusing every book."""
    _fixture(store, "litrpg")
    assert make_plan_selector(outline=False)(store, "worker-a", START, 300.0) is not None


# --- the opt-out -----------------------------------------------------------------------


def test_the_floor_is_on_by_default_and_off_only_when_said_so(store: SqliteStore) -> None:
    """Default True is the fail-closed direction: a caller that forgets gets the floor."""
    assert DraftPolicy().require_starting_sheet is True

    book_id, branch_id = _fixture(store, "mystery")
    off = DraftPolicy(require_starting_sheet=False)
    assert plan_progress(store, book_id, branch_id, policy=off).blocked_reason is None
    assert make_plan_selector(outline=False, policy=off)(store, "w", START, 300.0) is not None


# --- the timing half: scheduled progression beats ---------------------------------------


def test_scene_one_always_carries_a_beat() -> None:
    """The operator's complaint and the census's strongest support are the same scene.

    Only 22.5% of market LitRPG chapters put a located progression event in their first 500
    words. Whatever the cadence is, and however short the book, scene 1 is scheduled.
    """
    for total in range(1, 13):
        assert 1 in genre.beat_ordinals(total), f"scene 1 unscheduled at total={total}"
    assert genre.beat_ordinals(0) == frozenset()


def test_the_cadence_is_regular_after_the_opening() -> None:
    assert genre.beat_ordinals(6, every=2) == frozenset({1, 3, 5})
    assert genre.beat_ordinals(8, every=3) == frozenset({1, 4, 7})
    # every=1 is every scene, and scene 1 is not double-counted into a different answer.
    assert genre.beat_ordinals(4, every=1) == frozenset({1, 2, 3, 4})
    with pytest.raises(ValueError):
        genre.beat_ordinals(6, every=0)


def test_an_unscheduled_scene_is_left_byte_identical() -> None:
    """The control this whole change is read against: a scene not on the schedule is unchanged."""
    statement = "Corin counts the jars and finds one short."
    assert genre.with_beat(statement, 2, 6, every=2) == statement


def test_a_scheduled_scene_gains_the_beat_after_its_own_statement() -> None:
    statement = "Corin counts the jars and finds one short."
    got = genre.with_beat(statement, 1, 6, every=2)
    assert got.startswith(statement), "the scene's own statement must lead"
    assert got.endswith(genre.BEAT)
    # An unpunctuated statement is still joined into two readable sentences.
    assert genre.with_beat("Corin counts the jars", 1, 6) == f"Corin counts the jars. {genre.BEAT}"
    assert genre.with_beat("   ", 1, 6) == genre.BEAT


def test_the_beat_is_material_and_carries_no_quality_word() -> None:
    """`plan/house-genre-constraint.md` named the hazard: *"show progress immediately" as
    prompt text is a §138 formula waiting to happen*.

    So the scheduled sentence says what happens, not how well it should go.
    """
    from litharness.domain import house

    text = genre.BEAT.lower()
    for word in ("progress", "progression", "exciting", "interesting", "good", "compelling",
                 "satisfying", "dopamine", "reward", "quickly", "immediately", "clearly"):
        assert word not in text, f"the beat reaches for a quality word: {word!r}"
    leaked = sorted(word for word in house.MACHINERY_WORDS if word in text)
    assert not leaked, f"the beat speaks this system's own vocabulary: {leaked}"


def test_the_beat_assumes_nothing_about_who_the_book_is_about() -> None:
    """It is scheduled into every book, so it may not decide the protagonist's gender.

    The first draft said "something he has been counting", which would have put a male
    protagonist in the plan of every scheduled scene of every book this house drafts.
    """
    words = set(genre.BEAT.lower().replace(",", " ").replace(".", " ").split())
    assert not words & {"he", "him", "his", "she", "her", "hers", "himself", "herself"}


def test_the_report_and_the_gate_say_the_same_words() -> None:
    """One string, two surfaces.

    `cmd_new` prints the report at creation and the floor refuses with it later. Two
    hand-maintained sentences would drift, and an operator who ignored the first would then
    fail to recognise the second as the same condition.
    """
    from pathlib import Path

    cli = Path(__file__).resolve().parents[1] / "src" / "litharness" / "cli.py"
    source = cli.read_text(encoding="utf-8")
    assert "genre.NO_SHEET" in source, (
        "cmd_new must print the shared constant rather than its own copy of the sentence"
    )
    assert genre.NO_SHEET not in source, (
        "the sentence is hard-coded in cli.py again; it belongs to domain/genre.py alone"
    )


# --- the operator surface --------------------------------------------------------------


def test_a_floored_book_says_why_on_the_operator_surface(tmp_path, capsys) -> None:
    """The refusal must reach a command an operator actually runs, not just the domain object.

    Pilot 14 §7 watched the gap live: `plan_progress` computed the reason and the selector
    honoured it, but no command printed it, so a floored book returned `no_work` under a
    `status` reading `jobs {}` / `needs attention 0` — a stopped board and a board at rest
    were the same screen. This pins `litharness status` to the planner's own sentence, so
    the surface cannot silently regress to that state (§159).
    """
    from litharness.cli import EXIT_OK, main

    db = tmp_path / "surface.db"
    seeding = SqliteStore.open(db)
    try:
        _fixture(seeding, "mystery")
    finally:
        seeding.close()

    assert main(["--database", str(db), "status"]) == EXIT_OK
    out = capsys.readouterr().out
    assert genre.NO_SHEET in out, "the floor's own sentence must reach the status report"
    assert "blocked" in out
    assert "needs attention 1" in out, (
        "a blocked book must count in the number the operator watches; it appears in no "
        "other count"
    )


def test_a_seeded_book_is_not_reported_blocked(tmp_path, capsys) -> None:
    """The negative control: a book past the floor puts no blocked line on the report."""
    from litharness.cli import EXIT_OK, main

    db = tmp_path / "surface.db"
    seeding = SqliteStore.open(db)
    try:
        _fixture(seeding, "litrpg")
    finally:
        seeding.close()

    assert main(["--database", str(db), "status"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "blocked" not in out
    assert "needs attention 0" in out
