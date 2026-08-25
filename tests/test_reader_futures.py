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
3. the block the writer reads no longer claims those words outrank its craft rules.

Everything here is string and dictionary handling. No database, no model call, no network.
"""

from __future__ import annotations

import pytest

from litharness.application import overview, readers
from litharness.domain import rivals
from litharness.domain.text import STOP_FRACTION, stop_point

PASSAGE = "\n\n".join(f"Paragraph {index} carrying a few words of prose." for index in range(1, 9))


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
    """"there was no future to ask about" and "the reader saw it all" must not print the same."""
    with pytest.raises(ValueError):
        stop_point("One paragraph and nothing after it.")


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
        "want_next",
    }
    assert "dreading" not in readers.ANTICIPATION_SCHEMA["properties"]
    assert "hoping_for" not in readers.ANTICIPATION_SCHEMA["properties"]


def test_the_blurb_stage_asks_the_same_three_things_as_the_chapter_stage() -> None:
    """A listing is a prefix, so the reader in front of it is in the same position."""
    assert readers.APPETITE_SCHEMA is readers.ANTICIPATION_SCHEMA


def test_a_steering_reader_is_asked_where_it_got_to_and_not_what_it_thinks() -> None:
    reader = readers.pool(readers.STEERING)[0]
    prompt = readers.render_anticipation_request(reader, PASSAGE).prompt
    assert "That is as far as you have got" in prompt
    for banned in ("what would disappoint", "drop it by chapter", "hoping it turns out"):
        assert banned not in prompt


# --- what reaches the writer ------------------------------------------------------------


def test_the_direction_no_longer_claims_to_outrank_the_craft_rules() -> None:
    """§129's ordering is untouched; the claim that the *words* outrank it is what went.

    That sentence sat above a list of up to fifty reader items, which is the maximal permission
    §138 measured being recited maximally.
    """
    block = readers.Anticipation(
        felt=("uneasy",),
        expect_next=("he goes back down",),
        want_next=("a real cost",),
        answered=4,
    ).render()
    assert "outranks every craft rule" not in block
    assert "are not describing what you should write" in block
    assert "a real cost" in block


def test_a_book_nobody_read_gets_no_direction_at_all() -> None:
    assert readers.Anticipation(felt=(), expect_next=(), want_next=(), answered=0).render() == ""
    assert overview.render_appetite((), (), ()) == ""


def test_a_pre_migration_row_still_carries_its_direction() -> None:
    """A book part-drafted across 032 keeps steering. An old hope is a want by another name."""
    carried = readers.Anticipation.of(
        {readers.pool(readers.STEERING)[0].reader_id: {"hoping_for": ["a real cost"]}}
    )
    assert carried.want_next == ("a real cost",)
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
    admitted = rivals.admit(GOOD)
    assert admitted.rating == 4.36
    with pytest.raises(rivals.IllegalRival, match="not above"):
        rivals.admit(GOOD | {"rating": 4.0})
    with pytest.raises(rivals.IllegalRival, match="floor"):
        rivals.admit(GOOD | {"ratings": 3})


def test_a_round_rating_with_no_count_is_refused_and_an_imprecise_one_is_not() -> None:
    """The operator's proxy: *"4.36 stars implies a lot of views and ratings"*, and 4.5 does not.

    Only used where a count is absent, because it is a proxy and the count is the thing.
    """
    countless = {key: value for key, value in GOOD.items() if key != "ratings"}
    assert rivals.admit(countless).ratings is None
    with pytest.raises(rivals.IllegalRival, match="decimal"):
        rivals.admit(countless | {"rating": 4.5})


def test_a_rival_outside_this_readership_s_genres_is_refused() -> None:
    with pytest.raises(rivals.IllegalRival, match="not one of"):
        rivals.admit(GOOD | {"genre": "cosy mystery"})


def test_a_reader_is_never_told_what_the_rival_scored() -> None:
    """A reader told a book is rated 4.36 has been told the answer."""
    shown = rivals.admit(GOOD).render()
    assert "4.36" not in shown
    assert "812" not in shown
    assert shown.startswith("The Deep Ledger")


def test_the_draw_rotates_by_reader_and_replays_identically() -> None:
    """A different competitor per reader, so one screen samples the market rather than a book."""
    pool = rivals.admit_all(
        [GOOD | {"title": f"Book {index}", "listing": f"Blurb {index}"} for index in range(8)]
    )
    drawn = {rivals.draw(pool, f"scene-1|{reader}").title for reader in ("a", "b", "c", "d")}
    assert len(drawn) > 1
    assert rivals.draw(pool, "scene-1|a") is rivals.draw(pool, "scene-1|a")


def test_an_empty_pool_is_refused_rather_than_quietly_skipped() -> None:
    with pytest.raises(rivals.IllegalRival):
        rivals.draw((), "key")


# --- the two lanes show the rival differently -------------------------------------------


def test_the_browsing_reader_sees_both_blurbs_unlabelled_and_swapped() -> None:
    reader = readers.pool(readers.MEASUREMENT)[0]
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
    reader = readers.pool(readers.MEASUREMENT)[0]
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
    reader = readers.pool(readers.MEASUREMENT)[0]
    solo = readers.render_choice_request(reader, PASSAGE)
    assert solo.schema is readers.CHOICE_SCHEMA
    assert "cannot do both" not in solo.prompt


def test_a_steering_reader_may_not_be_shown_a_rival() -> None:
    """A rival is published prose and a steering reader's words reach a writer. RS1."""
    steering = readers.pool(readers.STEERING)[0]
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
