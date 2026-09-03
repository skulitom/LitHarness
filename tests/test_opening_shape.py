"""The opening's shape, the fork as furniture, and grammatical person as a position.

Three things the opening-parity track (2026-09-01) put into the pipeline, each measured against
the market's summit openings rather than asked for as taste (`research/opening-parity/PREREG.md`
§2): the first chapter's two beats — who the person was before, then the first printed line
inside that; and the chapter ending on something read or offered and unanswered — the `[OFFER]`
line the book prints where a fork is put in front of a person, and `--person first` as a locked
constraint seeded at creation. Every one is a ratchet: a book that prints no line, offers no
fork, or was created without `--person` renders byte-identically to what it did before.

No model call, no network. The CLI test opens a store under `tmp_path` and nothing else.
"""

from __future__ import annotations

import litharness_contracts as lc
import pytest
from test_choice_points import _accepted, _system

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import overview, planner
from litharness.application.planner import render_prompt
from litharness.cli import EXIT_OK, main
from litharness.domain import beats as beats_domain
from litharness.domain import context as context_domain
from litharness.domain import extraction, gamesystem, genre, house, plans, reviser
from tests.conftest import FIXTURE_SHEET

# ------------------------------------------------------------------------- the opening beats


def test_the_first_scene_carries_the_days_before_and_the_first_printed_line() -> None:
    assert genre.opening_text(1, reads=True) == genre.OPENING_FIRST
    assert genre.with_opening("The seam.", 1, reads=True) == f"The seam. {genre.OPENING_FIRST}"
    assert genre.with_opening("", 1, reads=True) == genre.OPENING_FIRST


def test_the_hook_lands_on_the_first_chapter_s_last_scene_whatever_its_length() -> None:
    two = {"chapter_scene": 2, "scenes_in_chapter": 2}
    assert genre.opening_text(2, reads=True, **two) == genre.OPENING_HOOK
    four_mid = {"chapter_scene": 2, "scenes_in_chapter": 4}
    assert genre.opening_text(2, reads=True, **four_mid) is None
    four_end = {"chapter_scene": 4, "scenes_in_chapter": 4}
    assert genre.opening_text(4, reads=True, **four_end) == genre.OPENING_HOOK
    # Chapter two's last scene has the same in-chapter position and is not the opening.
    assert genre.opening_text(8, reads=True, **four_end) is None
    # A caller with no chapter shape falls back to the placed span `staging.OPENING` carries.
    assert genre.opening_text(2, reads=True) == genre.OPENING_HOOK
    assert genre.opening_text(3, reads=True) is None


def test_a_book_that_prints_no_line_and_a_later_arc_compose_what_they_composed_before() -> None:
    statement = "Rate moves here, and the person it belongs to is there when it does."
    assert genre.with_opening(statement, 1, reads=False) == statement
    assert genre.with_opening(statement, 1, reads=True, arc_index=2) == statement
    assert genre.with_opening(statement, 1, reads=True, arc_index=1) != statement


def test_the_opening_beats_are_material_and_name_what_the_writer_can_put_on_the_page() -> None:
    """§154: a demand names a token the writer can emit. Both beats name the first printed line
    or the unanswered thing, and neither is an adjective about the scene or reaches the house
    floor, which sits at its ceiling (`tests/test_prompt_budget.py`)."""
    for beat in (genre.OPENING_FIRST, genre.OPENING_HOOK):
        assert len(house.demands(beat)) == 1
        assert beat not in house.HOUSE_RULES
    assert "first line the book prints" in genre.OPENING_FIRST
    assert "has not yet answered" in genre.OPENING_HOOK


# ------------------------------------------------------------------------- the offer line


def test_the_offer_line_is_the_book_s_own_words_in_the_fork_s_own_order() -> None:
    system = _system()
    (choice,) = system.choices
    line = gamesystem.offer_line(system, choice)
    assert line == "[OFFER] Hand — Kiln: opens Kiln Hand | Reed: opens Reed Hand"
    assert reviser.machine_lines(f"Prose.\n{line}\nMore prose.") == (line,)
    priced = gamesystem.Choice(
        "fork_hand",
        "Hand",
        options=(
            gamesystem.Option("opt_kiln", "Kiln", grants=("cap_kiln",), costs="a winter"),
            gamesystem.Option("opt_reed", "Reed", grants=("cap_reed",)),
        ),
        opens_at="r_second",
    )
    assert gamesystem.offer_line(system, priced) == (
        "[OFFER] Hand — Kiln: opens Kiln Hand, costs a winter | Reed: opens Reed Hand"
    )


def test_the_offer_line_is_read_off_canon_with_every_guard_the_offer_beat_has() -> None:
    system = _system()
    risen = gamesystem.rise(gamesystem.starting_sheet(system, "mira"), at="s2").sheet
    canon = [
        _accepted(record)
        for record in (
            *gamesystem.records_for(system),
            *gamesystem.records_for_sheet(risen, at="s2"),
        )
    ]
    assert extraction.offered_line(canon, character="mira", at="s3") == (
        "[OFFER] Hand — Kiln: opens Kiln Hand | Reed: opens Reed Hand"
    )
    assert extraction.offered_line(canon, character=None, at="s3") is None
    assert extraction.offered_line(canon, character="nobody", at="s3") is None
    opening = gamesystem.starting_sheet(system, "mira")
    unreached = [
        _accepted(record)
        for record in (*gamesystem.records_for(system), *gamesystem.records_for_sheet(opening))
    ]
    assert extraction.offered_line(unreached, character="mira", at="s1") is None
    # The status line is the one parsed surface: an offer line mints no record.
    assert FIXTURE_SHEET.pattern.search("[OFFER] Hand — Kiln: opens Kiln Hand") is None


_BEAT = beats_domain.Beat(
    logical_id="s1",
    ordinal=1,
    of_total=1,
    title=None,
    function="setup",
    template_id=beats_domain.SIX_BEAT.template_id,
)
_PACKET = context_domain.ContextPacket(
    query_id="opening-shape",
    target_logical_id="s1",
    book_id="book",
    branch_id="main",
    base_revision_id="r0",
)
_STATUS = extraction.render_status_line(
    "Mira", {"level": 2, "hp": 10, "hp_max": 10, "mp": 4, "mp_max": 4, "gold": 1}
)
_OFFER = "[OFFER] Hand — Kiln: opens Kiln Hand | Reed: opens Reed Hand"


def test_the_scene_system_prints_the_fork_beside_the_sheet_and_nowhere_without_one() -> None:
    with_offer, _ = render_prompt(
        _BEAT, book_title=None, packet=_PACKET, status_example=_STATUS, offer_line=_OFFER
    )
    without, _ = render_prompt(_BEAT, book_title=None, packet=_PACKET, status_example=_STATUS)
    assert _OFFER in with_offer
    assert "prints this line, exactly once" in with_offer
    assert with_offer.index(_STATUS) < with_offer.index(_OFFER)
    assert _OFFER not in without
    # A fork needs the sheet it is a fork in: no status example, no offer, byte-identical.
    bare, _ = render_prompt(_BEAT, book_title=None, packet=_PACKET, offer_line=_OFFER)
    plain, _ = render_prompt(_BEAT, book_title=None, packet=_PACKET)
    assert bare == plain
    assert planner is not None


# ------------------------------------------------------------------------- grammatical person


def test_a_first_person_listing_is_asked_for_under_the_brief_and_nowhere_else() -> None:
    first = overview.render_overview_request("A cook on a hauler.", None, person="first")
    third = overview.render_overview_request("A cook on a hauler.", None)
    assert first.prompt.endswith(overview.FIRST_PERSON_ASK)
    assert overview.FIRST_PERSON_ASK not in third.prompt
    assert first.system == third.system
    assert overview.FIRST_PERSON_ASK not in overview._TASK


@pytest.mark.parametrize("person", [None, "third"])
def test_a_book_created_without_first_person_seeds_only_its_premise(
    tmp_path, person: str | None
) -> None:
    db = tmp_path / "book.db"
    assert main(["--database", str(db), "init"]) == EXIT_OK
    args = [
        "new",
        "Plain",
        "--premise",
        "A cook reads her own sheet.",
        "--scenes",
        "6",
        "--book",
        "b",
        "--branch",
        "main",
    ]
    if person is not None:
        args += ["--person", person]
    assert main(["--database", str(db), *args]) == EXIT_OK
    with SqliteStore.open(db) as store:
        items = {item.logical_id: item for item in store.plan_items("b", "main")}
    assert set(items) == {"plan-premise"}


def test_a_first_person_book_carries_the_constraint_as_a_locked_plan_item(tmp_path) -> None:
    db = tmp_path / "book.db"
    assert main(["--database", str(db), "init"]) == EXIT_OK
    assert (
        main(
            [
                "--database",
                str(db),
                "new",
                "Mine",
                "--premise",
                "A cook reads her own sheet.",
                "--scenes",
                "6",
                "--book",
                "b",
                "--branch",
                "main",
                "--person",
                "first",
            ]
        )
        == EXIT_OK
    )
    with SqliteStore.open(db) as store:
        items = {item.logical_id: item for item in store.plan_items("b", "main")}
    person = items[plans.FIRST_PERSON_PLAN_ID]
    assert person.kind is lc.PlanKind.CONSTRAINT
    assert person.locked is True
    assert person.text == plans.FIRST_PERSON_CONSTRAINT
    # A position, not a handling instruction: one clause, no adverb about how to write it.
    assert len(house.demands(plans.FIRST_PERSON_CONSTRAINT)) == 1
    assert "first person" in plans.FIRST_PERSON_CONSTRAINT
    assert plans.FIRST_PERSON_CONSTRAINT not in house.HOUSE_RULES
