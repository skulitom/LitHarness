"""Stage-0 §165: the two order-key spaces, and the book that was handed its own last page.

Serial Pilot 15's Architect declared its protagonist's whole arc in advance — three
`status_snapshot`s at `0110`, `0250` and `0350` — and left the opening state un-keyed, which is
exactly what the `status_snapshot` line asks for. Scene one was then shown the `0350` snapshot:
rung 5 of 6 with the reach the book's own canon says the mill wheel takes, before the first
sentence. **The defect is nine characters wide: `'0350' <= 's1'` is `True`**, because digits sort
below letters, and the magnitude of the number is irrelevant — *any* numeric key an Architect
writes lands before *every* scene.

The scheduling was never the defect and is the thing to keep: a seed committing in advance to
where a character's numbers will stand is §110's promise-scheduling instinct applied to stats.
What failed is that the two vocabularies for "where in the book" had never been introduced to
each other. So this file pins the introduction: `state.key_space` names the space the pipeline
mints scene positions in and the space a declaration schedules positions in, `state.comparable`
refuses to compare across them, and the fold reads one of them plus the timeless.

`test_the_pilot_fifteen_key_set_folds_scene_one_to_the_opening_state` is the repro, at
serial15.db's exact keys and values. It is written against the seed as it stood when scene one
was drafted, because the `s1` and `s2` snapshots in that store were extracted *from* the prose
the defect caused, and asserting on them would be asserting on the damage rather than the cause.

No model reads, ranks or judges anything in this file, and no bar is declared anywhere in it.
"""

from __future__ import annotations

import litharness_contracts as lc
import pytest

from litharness.application import world as world_view
from litharness.domain import extraction, state, worlds

#: Serial Pilot 15's sheet, verbatim from `serial15.db`. `carried` is the paired column.
_SHEET = {
    "fields": [
        {"label": "Seamwork", "name": "rung", "paired": False},
        {"label": "Reach", "name": "reach", "paired": False},
        {"label": "Carried", "name": "carried", "paired": True},
        {"label": "Seams standing in Ashfen", "name": "standing", "paired": False},
    ]
}

#: The opening state, declared with no key — "the state the book opens in".
_OPENING = {"carried": 4, "carried_max": 5, "reach": 3, "rung": 2, "standing": 19}

#: The arc the Architect scheduled ahead of the writing, at its own three keys.
_SCHEDULE = {
    "0110": {"carried": 2, "carried_max": 6, "reach": 4, "rung": 3, "standing": 24},
    "0250": {"carried": 5, "carried_max": 8, "reach": 6, "rung": 4, "standing": 33},
    "0350": {"carried": 3, "carried_max": 9, "reach": 9, "rung": 5, "standing": 41},
}

#: What the extractor later read back off the printed line, at the scene keys.
_EXTRACTED = {"carried": 4, "carried_max": 9, "reach": 9, "rung": 5, "standing": 42}


def _record(
    value: object, *, predicate: str = extraction.STATUS_PREDICATE, order_key: str | None = None
) -> lc.StateRecord:
    return worlds.world_record(
        "mira",
        predicate,
        value=value,
        order_key=order_key,
        authority=lc.StateAuthority.ACCEPTED_CANON,
    )


def _seed() -> list[lc.StateRecord]:
    """The world as it stood when scene one was drafted: the seed, and nothing extracted yet."""
    return [
        _record(_SHEET, predicate=extraction.SHEET_PREDICATE),
        _record(_OPENING),
        *(_record(value, order_key=key) for key, value in _SCHEDULE.items()),
    ]


def test_the_defect_is_nine_characters_wide() -> None:
    """The comparison itself, pinned so nobody simplifies the fix back out.

    Both of these are facts about `str`, not about this repository, and the second is the whole
    reason the first cannot be allowed to decide anything: every schedule key sorts below every
    scene key, and a word in the slot sorts wherever its spelling puts it.
    """
    assert "0350" <= "s1"
    assert "clearance" < "s1"
    assert "zz_c" > "s1"
    assert not state.comparable("0350", "s1")
    assert not state.comparable("clearance", "s1")
    assert not state.comparable("zz_c", "s1")


def test_key_space_names_two_spaces_and_refuses_everything_else() -> None:
    """The scene keys both minters write, the schedule keys a declaration writes, and the rest.

    `s1` is `beats_for` at six scenes and `s000001` is `beats_for_arc`; the widths differ because
    `beats_for` derives its own from the book's length, which is why a hand-written scene key is
    a guess at a coordinate the writer does not own. The five refused keys are real: each one
    appears in a pilot database, in the `--order-key` slot, holding a criterion's name.
    """
    assert state.key_space("s1") == state.SCENE_KEYS
    assert state.key_space("s000001") == state.SCENE_KEYS
    assert state.key_space("0110") == state.SCHEDULE_KEYS
    assert state.key_space("010") == state.SCHEDULE_KEYS
    for word in ("clearance", "notches", "cuff", "grade", "rung-uncorded"):
        assert state.key_space(word) is None
    assert state.key_space(None) is None


def test_two_unplaceable_keys_are_not_at_a_shared_position() -> None:
    """A key in neither space compares with nothing, including another key in neither space.

    Two words in the position slot are two records nobody can place, not two records at one
    position. Letting them compare with each other would re-enter the defect one address along,
    with `'clearance' < 'cuff'` deciding a story order.
    """
    assert not state.comparable("clearance", "cuff")
    assert not state.comparable("cuff", "cuff")


def test_the_pilot_fifteen_key_set_folds_scene_one_to_the_opening_state() -> None:
    """The repro. Scene one is shown the state the book opens in, not the end of the schedule.

    Before §165 this returned the `0350` snapshot — rung 5, reach 9 — because all three schedule
    keys sorted before `s1`, the ceiling was `0350`, and the fold returned the end of the book.

    The subject stayed `mira` on the state side and reads `Mira` on the rendered side after
    §169 moved the printed name off the raw id. Which snapshot the fold lands on is what this
    test is about, and the pair below is the point: the record keeps the id, the line prints
    the name.
    """
    records = _seed()
    standing = extraction.state_as_it_stands(records, at="s1")
    assert standing == ("mira", _OPENING)
    assert extraction.system_voice_example(records, at="s1") == (
        "[STATUS] Mira — Seamwork 2 | Reach 3 | Carried 4/5 | Seams standing in Ashfen 19"
    )


@pytest.mark.parametrize("at", ["s1", "s2", "s3", "s4", "s5", "s6"])
def test_no_scene_of_that_book_is_shown_a_scheduled_snapshot(at: str) -> None:
    """Not scene one by luck of the sort: the schedule is unreachable from every scene.

    The magnitude of the number is what makes this a class rather than an instance, so the
    assertion is over the whole six-scene book the pilot ran at.
    """
    assert extraction.state_as_it_stands(_seed(), at=at) == ("mira", _OPENING)


def test_the_schedule_stays_canon_and_stays_readable() -> None:
    """Never folded as past is not the same as discarded, and the difference is the whole design.

    The Architect did the good thing by declaring where the numbers will stand; a fix that
    dropped those records would have taught the next seed to stop. They remain canon, in story
    order, at their own keys, and `snapshot_at` finds one when asked in its own space.
    """
    records = _seed()
    scheduled = [
        record
        for record in records
        if state.key_space(state.order_key_of(record)) == state.SCHEDULE_KEYS
    ]
    assert len(scheduled) == 3
    standing = extraction.state_as_it_stands(records, at="0250")
    assert standing == ("mira", _SCHEDULE["0250"])


def test_the_scene_the_extractor_wrote_back_is_still_the_one_that_stands() -> None:
    """With the whole key set present, a scene reads its own space and the schedule is inert.

    `include_at=False` is the drafting question — the state this scene continues *from* — and
    before §165 it answered `0350` for scene one. It now answers the opening state, and at scene
    two it answers scene one's own extracted snapshot.
    """
    records = [*_seed(), _record(_EXTRACTED, order_key="s1"), _record(_EXTRACTED, order_key="s2")]
    assert extraction.snapshot_at(records, at="s1", include_at=False).value == _OPENING
    assert extraction.snapshot_at(records, at="s1").value == _EXTRACTED
    assert extraction.snapshot_at(records, at="s2", include_at=False).value == _EXTRACTED


def test_a_partial_scene_snapshot_folds_over_the_opening_and_not_over_the_schedule() -> None:
    """The fold still folds, and what it folds over is the timeless state rather than a schedule.

    §161's rule is that a snapshot need not restate the sheet, so a scene that moved one number
    writes one key. That partial record must land on the opening state — the schedule sitting
    between them in string order must contribute nothing, which is invisible unless the values
    differ, so `standing` is the column checked.
    """
    records = [*_seed(), _record({"rung": 3}, order_key="s1")]
    standing = extraction.state_as_it_stands(records, at="s1")
    assert standing == ("mira", {**_OPENING, "rung": 3})
    assert standing[1]["standing"] == 19


def test_world_check_reports_a_key_in_neither_space() -> None:
    """The half a fold cannot fix: the record is canon, unplaceable, and cannot be withdrawn.

    `will_not_resolve` is §152's channel for a mistake no later declaration undoes, and it does
    not move `ok` — a world is not refused for it, it is told. A scheduled key is legal and draws
    no warning, which is what keeps the good behaviour good.
    """
    stray = _record(_OPENING, order_key="clearance")
    warnings = worlds.slot_warnings(stray)
    assert len(warnings) == 1
    assert "clearance" in warnings[0]
    assert "neither a scene position" in warnings[0]

    assert worlds.slot_warnings(_record(_OPENING, order_key="0350")) == ()
    assert worlds.slot_warnings(_record(_OPENING, order_key="s1")) == ()

    payload = world_view.check([*_seed(), stray])
    assert any("clearance" in line for line in payload["will_not_resolve"])
    assert payload["ok"] is True
