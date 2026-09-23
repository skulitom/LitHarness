"""The concept listing names the genre's furniture (§261).

Draw 1 of the restored-directions draw failed its listing gate: the prompt asked for "ordinary
language before special terminology", and the listing translated the book's Slot into "room" and
left its ranks unnamed, so nothing told a LitRPG reader the book was for them.
"""

from __future__ import annotations

from litharness.application import overview


def test_the_concept_listing_asks_for_the_system_skills_and_ranks_by_the_books_names() -> None:
    task = overview._system(None, supplied_concept=True)
    assert "Name the game system, its skills and the ranks or levels it counts" in task
    assert "a rank the system counts is not incidental" in task
    assert "Use ordinary language before special terminology" not in task
    assert overview.CONCEPT_OVERVIEW_PROFILE == "writer.overview.concept.v4"


def test_the_brief_only_listing_task_is_unchanged() -> None:
    """Only the supplied-concept route changes; a listing from a brief alone keeps its task."""
    assert "Name the game system, its skills" not in overview._system(None)
