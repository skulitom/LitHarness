"""The concept listing names the game system once and opens on a hook (§261, corrected by §262).

Draw 1 of the restored-directions draw failed its listing gate: the prompt asked for "ordinary
language before special terminology", and the listing translated the book's Slot into "room" and
left its ranks unnamed, so nothing told a LitRPG reader the book was for them. §261 answered with
a clause naming the system, its skills and its ranks, and draw 2's listing named all of them in a
run of short fact sentences the operator would stop at (read 20: "a list of facts instead of an
overview which should grab attention with a hook"). v4 keeps the system's name and drops the
inventory: one power shown by what it lets the person do, the want and the obstacle, and an ending
that points forward, with `_TASK`'s measured numbers and paragraph sentences restored word for word.
"""

from __future__ import annotations

from litharness.application import overview

#: The two sentences both listing tasks carry byte-identical: §138's numbers prohibition and the
#: paragraph clause restored for "sentences don't have relations to each other".
SHARED = (
    "Exactness spent on floors, ranks, counts and lengths of time is space the hook needed.",
    "A paragraph holds together or it is not a paragraph: a sentence that could be lifted out "
    "and dropped anywhere in the listing has failed.",
)


def test_the_concept_listing_names_the_game_system_once_and_asks_for_a_hook() -> None:
    task = overview._system(None, supplied_concept=True)
    assert "Name the game system once as the book names it" in task
    # The operator's standing direction, in the sentence that shows the power: it puts this
    # person on a faster climb than anyone else's (§262, after §261's draw 1 showed none).
    assert "by what it lets them do and how it lets them climb past everyone else." in task
    assert "Its first sentence already holds the change" in task
    assert "End on what they are about to try or what could go wrong." in task
    assert "its skills and the ranks" not in task
    assert "a rank the system counts is not incidental" not in task
    assert "Use ordinary language before special terminology" not in task
    assert overview.CONCEPT_OVERVIEW_PROFILE == "writer.overview.concept.v4"


def test_the_numbers_and_paragraph_sentences_are_the_brief_only_task_s_own() -> None:
    for sentence in SHARED:
        assert sentence in overview._system(None, supplied_concept=True)
        assert sentence in overview._system(None)


def test_the_brief_only_listing_task_is_unchanged() -> None:
    """Only the supplied-concept route changes; a listing from a brief alone keeps its task."""
    assert "Name the game system once" not in overview._system(None)
    assert overview.OVERVIEW_PROFILE == "writer.overview.v0"
