"""What a reader may be asked, what it may be shown, and what it may hand a writer.

**This file exists because the reader channel wrote six defects into a listing.** Measured
2026-08-25 on *Patch Notes For Earth*: four steering readers asked for *"a real changelog with
version numbers, nerfs"*, *"repro steps, edge cases"* and *"an interaction between two stated
rules"*; the revision put every one of those on the page; and the operator's read of the result
was 30/100 against 45-70 for the round before. The draft the readers had seen carried none of
them. So the defects did not come from the writer and they did not come from a craft rule —
they came from the one channel this project deliberately opened into generation (§128), and
they came as vocabulary.

The tests below pin the three properties that stop it happening again, and each one would have
caught it:

1. a reader is stopped part-way, so it has a future to talk about rather than a finished text
   to assess;
2. the schema has nowhere to put an instruction about the writing;
3. the observation type has no renderer capable of putting those words into a writer prompt.

Everything here is string and dictionary handling. No database, no model call, no network.
"""

from __future__ import annotations

import pytest

from litharness.application import readers
from litharness.domain import rivals
from litharness.domain.revision import new_book
from litharness.domain.serials import SerialShape
from litharness.domain.text import STOP_FRACTION, stop_point
from litharness.packs import litrpg

PASSAGE = "\n\n".join(f"Paragraph {index} carrying a few words of prose." for index in range(1, 9))

#: The house's readers, by the name they moved to (stage-0 §221). Every reader below is the
#: one the pipeline has rendered since 2026-08-25; the pack is where they live now.
MEASURING = litrpg.pool(readers.MEASUREMENT)
STEERING = litrpg.pool(readers.STEERING)


# --- the reader is stopped part-way ----------------------------------------------------


def test_a_reader_is_never_shown_the_end() -> None:
    """The whole point: a reader with the ending has nothing to predict."""
    seen = stop_point(PASSAGE)
    assert seen != PASSAGE
    assert PASSAGE.startswith(seen)
    assert seen.split("\n\n")[-1] in PASSAGE


def test_the_cut_falls_on_a_paragraph_and_near_the_registered_fraction() -> None:
    seen = stop_point(PASSAGE)
    assert not seen.endswith(" ")
    share = len(seen.split()) / len(PASSAGE.split())
    assert abs(share - STOP_FRACTION) < 0.15


def test_a_passage_with_no_future_raises_rather_than_returning_everything() -> None:
    """ "there was no future to ask about" and "the reader saw it all" must not print the same."""
    with pytest.raises(ValueError):
        stop_point("One paragraph and nothing after it.")


def test_a_continuing_reader_gets_bounded_history_and_no_future_prose() -> None:
    blank = new_book("book", "branch", title="Serial", scenes=32)
    revision = blank.replacing(
        node.with_content(f"PROSE-{index:02d}")
        for index, node in enumerate(
            (item for item in blank.in_reading_order() if item.logical_id.startswith("scene-")),
            start=1,
        )
    )
    summaries = {f"scene-{index}": f"SUMMARY-{index:02d}" for index in range(1, 33)}

    context = readers.accumulated_passage(
        revision,
        "scene-30",
        "PROSE-30-PARTIAL",
        summaries=summaries,
        shape=SerialShape(scenes_per_chapter=4, chapters_per_arc=6),
    )

    assert "earlier chapter(s) were read" in context
    assert "SUMMARY-05" in context, "older context in the current recall window is compact"
    assert "PROSE-21" in context, "the two preceding chapters remain verbatim"
    assert "PROSE-29" in context, "earlier scenes in the current chapter are present"
    assert "PROSE-30-PARTIAL" in context
    assert "PROSE-30\n" not in context
    assert "PROSE-31" not in context and "PROSE-32" not in context


def test_reader_memory_is_owned_by_one_reader_and_uses_its_newest_earlier_stop() -> None:
    rows = [
        {"reader_id": "r", "logical_id": "scene-3", "felt": "current"},
        {"reader_id": "r", "logical_id": "scene-4", "felt": "future"},
        {"reader_id": "other", "logical_id": "scene-2", "felt": "not mine"},
        {"reader_id": "r", "logical_id": "scene-2", "felt": "uneasy", "expect_next": "a toll"},
        {"reader_id": "r", "logical_id": "scene-1", "felt": "old"},
    ]
    memory = readers.prior_reading_memory(
        rows,
        "r",
        earlier_logical_ids=("scene-1", "scene-2"),
    )
    assert "uneasy" in memory and "a toll" in memory
    assert "not mine" not in memory and "old" not in memory and "current" not in memory
    assert "future" not in memory


def test_the_package_and_the_registered_probe_cut_in_the_same_place() -> None:
    """One rule, two homes, and this is what keeps them one rule.

    `research/quality-measurement/anticipation.py` registered the stop point before any call was
    made (§124) and cannot be imported from inside the package — CONTRIBUTING's dependency
    direction — so the implementation is duplicated on purpose and pinned here.
    """
    anticipation = pytest.importorskip(
        "anticipation", reason="research module; needs the quality-measurement directory"
    )
    assert anticipation.STOP_FRACTION == STOP_FRACTION
    assert anticipation.stop_point(PASSAGE) == stop_point(PASSAGE)


# --- a reader has nowhere to put a critique --------------------------------------------


def test_the_steering_schema_has_no_slot_for_an_opinion_about_the_writing() -> None:
    """The three fields are the operator's three, and there is no fourth.

    A field a reader can fill with "this should have been shorter" is the field that put
    *repro steps* in a listing. `felt` is a state, `expect_next` is a guess, `want_next` is
    about the story — none of them is a specification.
    """
    assert set(readers.ANTICIPATION_SCHEMA["properties"]) == {
        "felt",
        "expect_next",
        "hoping_for",
        "dreading",
    }
    # Hope and dread are back (2026-08-26) and both are about **events**. What has no field is
    # an opinion about the writing, which is what the old questions invited.
    for field in ("hoping_for", "dreading"):
        described = readers.ANTICIPATION_SCHEMA["properties"][field]["description"]
        assert "never things the writing should do" in described


def test_the_blurb_stage_asks_the_same_three_things_as_the_chapter_stage() -> None:
    """A listing is a prefix, so the reader in front of it is in the same position."""
    assert readers.APPETITE_SCHEMA is readers.ANTICIPATION_SCHEMA


def test_a_steering_reader_is_asked_where_it_got_to_and_not_what_it_thinks() -> None:
    reader = STEERING[0]
    prompt = readers.render_anticipation_request(reader, PASSAGE).prompt
    assert "That is as far as you have got" in prompt
    assert "hoping for and dreading" in prompt
    # The questions that invited a specification of the artifact rather than of the story.
    for banned in ("what would disappoint", "drop it by chapter", "hoping it turns out"):
        assert banned not in prompt


# --- raw answers cannot reach the writer ------------------------------------------------


def test_raw_anticipation_has_no_renderer_back_into_a_writer_prompt() -> None:
    observation = readers.Anticipation(
        felt=("uneasy",),
        expect_next=("he goes back down",),
        hoping_for=("a real cost",),
        dreading=("it was a dream",),
        answered=4,
    )
    assert not hasattr(observation, "render")
    assert observation.to_jsonable()["hoping_for"] == ["a real cost"]


def test_a_book_nobody_read_records_an_empty_observation() -> None:
    empty = readers.Anticipation(felt=(), expect_next=(), hoping_for=(), dreading=(), answered=0)
    assert empty.to_jsonable() == {
        "answered": 0,
        "felt": [],
        "expect_next": [],
        "hoping_for": [],
        "dreading": [],
    }


def test_a_pre_migration_row_still_round_trips_as_observation() -> None:
    carried = readers.Anticipation.of(
        {STEERING[0].reader_id: {"hoping_for": ["a real cost"]}}, roster=STEERING
    )
    assert carried.hoping_for == ("a real cost",)
    assert carried.answered == 1


# --- the rival, and what makes it provable ----------------------------------------------


GOOD = {
    "title": "The Deep Ledger",
    "listing": "A courier finds the stairs under the city.",
    "rating": 4.36,
    "ratings": 812,
    "genre": "progression fantasy",
    "source": "https://example.invalid/1",
}


def test_a_rival_must_be_rated_above_four_by_more_than_a_handful() -> None:
    admitted = litrpg.LITRPG.admit_rival(GOOD)
    assert admitted.rating == 4.36
    with pytest.raises(rivals.IllegalRival, match="not above"):
        litrpg.LITRPG.admit_rival(GOOD | {"rating": 4.0})
    with pytest.raises(rivals.IllegalRival, match="floor"):
        litrpg.LITRPG.admit_rival(GOOD | {"ratings": 3})


def test_a_round_rating_with_no_count_is_refused_and_an_imprecise_one_is_not() -> None:
    """The operator's proxy: *"4.36 stars implies a lot of views and ratings"*, and 4.5 does not.

    Only used where a count is absent, because it is a proxy and the count is the thing.
    """
    countless = {key: value for key, value in GOOD.items() if key != "ratings"}
    assert litrpg.LITRPG.admit_rival(countless).ratings is None
    with pytest.raises(rivals.IllegalRival, match="decimal"):
        litrpg.LITRPG.admit_rival(countless | {"rating": 4.5})


def test_a_rival_outside_this_readership_s_genres_is_refused() -> None:
    with pytest.raises(rivals.IllegalRival, match="not one of"):
        litrpg.LITRPG.admit_rival(GOOD | {"genre": "cosy mystery"})


def test_a_reader_is_never_told_what_the_rival_scored() -> None:
    """A reader told a book is rated 4.36 has been told the answer."""
    shown = litrpg.LITRPG.admit_rival(GOOD).render()
    assert "4.36" not in shown
    assert "812" not in shown
    assert shown.startswith("The Deep Ledger")


def test_the_draw_rotates_by_reader_and_replays_identically() -> None:
    """A different competitor per reader, so one screen samples the market rather than a book."""
    pool = rivals.admit_all(
        [GOOD | {"title": f"Book {index}", "listing": f"Blurb {index}"} for index in range(8)],
        genres=litrpg.GENRES,
    )
    drawn = {rivals.draw(pool, f"scene-1|{reader}").title for reader in ("a", "b", "c", "d")}
    assert len(drawn) > 1
    assert rivals.draw(pool, "scene-1|a") is rivals.draw(pool, "scene-1|a")


def test_an_empty_pool_is_refused_rather_than_quietly_skipped() -> None:
    with pytest.raises(rivals.IllegalRival):
        rivals.draw((), "key")


# --- the two lanes show the rival differently -------------------------------------------


def test_the_browsing_reader_sees_both_blurbs_unlabelled_and_swapped() -> None:
    reader = MEASURING[0]
    mine, other = "a locksmith and a locked door", "a courier and a deep stair"
    leading = readers.render_pick_request(reader, mine, other, True).prompt
    trailing = readers.render_pick_request(reader, mine, other, False).prompt
    assert leading.index(mine) < leading.index(other)
    assert trailing.index(other) < trailing.index(mine)
    # Neither rendering says which side is the house's own; a reader told that is not
    # choosing between books (§89's position effect).
    for prompt in (leading, trailing):
        for tell in ("our ", "ours", "yours", "mine", "we wrote", "this system"):
            assert tell not in prompt.lower()


def test_the_continuation_names_the_other_book_and_does_not_show_it() -> None:
    """The operator's correction: a blurb on the page has already been read for free."""
    reader = MEASURING[0]
    prompt = readers.render_choice_request(reader, PASSAGE, "The Deep Ledger").prompt
    assert "The Deep Ledger" in prompt
    assert "A courier finds the stairs" not in prompt
    assert "cannot do both" in prompt


def test_leaving_for_the_other_book_is_an_act_the_reader_can_name() -> None:
    assert readers.LEAVE_SCHEMA["properties"]["next"]["enum"] == [
        "carry_on",
        "go_and_look",
        "put_it_down",
    ]
    assert "come_back_later" not in readers.LEAVE_SCHEMA["properties"]["next"]["enum"]


def test_the_no_rival_arm_is_what_it_always_was() -> None:
    """The control has to be the same code path, or the comparison is between two scripts."""
    reader = MEASURING[0]
    solo = readers.render_choice_request(reader, PASSAGE)
    assert solo.schema is readers.CHOICE_SCHEMA
    assert "cannot do both" not in solo.prompt


def test_a_steering_reader_may_not_be_shown_a_rival() -> None:
    """A rival is published prose and a steering reader's words reach a writer. RS1."""
    steering = STEERING[0]
    with pytest.raises(ValueError):
        readers.render_choice_request(steering, PASSAGE, "The Deep Ledger")
    with pytest.raises(ValueError):
        readers.render_pick_request(steering, "OURS", "THEIRS", True)


# --- un-blinding happens in code ---------------------------------------------------------


@pytest.mark.parametrize(
    ("choice", "ours_first", "expected"),
    [
        ("the_first", True, "ours"),
        ("the_first", False, "theirs"),
        ("the_second", True, "theirs"),
        ("the_second", False, "ours"),
        ("neither", True, "neither"),
        ("", True, "neither"),
        ("nonsense", False, "neither"),
    ],
)
def test_a_positional_answer_is_resolved_against_the_recorded_order(
    choice: str, ours_first: bool, expected: str
) -> None:
    assert readers.side_of(choice, ours_first) == expected


def test_the_pairing_reports_the_position_covariate_beside_the_result() -> None:
    """A pairing whose order never varied is one whose result is a position effect."""
    paired = readers.Pairing.of(
        [
            {"reader": "power_m", "chose": "ours", "ours_first": True, "rival": {"title": "A"}},
            {"reader": "magic_m", "chose": "theirs", "ours_first": False, "rival": {"title": "B"}},
        ]
    )
    assert (paired.ours, paired.theirs, paired.neither) == (1, 1, 0)
    assert paired.ours_first_share == 0.5
    assert readers.Pairing.of([]).ours_first_share is None
