"""General genre appeals follow accepted reading history, never arc ordinals."""

from __future__ import annotations

import litharness_contracts as lc
import pytest

from litharness.application import planner, reviser, world_agent
from litharness.domain import context, house
from litharness.domain.beats import beats_for, template_for
from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID
from tests.test_outline import START, a_book


def test_continuing_house_block_keeps_comprehension_without_general_genre_appeals():
    complete = house.with_house_rules("Task.")
    assert complete == f"Task.\n\n{house.HOUSE_RULES}"
    assert complete == house.with_house_rules("Task.", opening=True)
    continuation = f"{house.CLARITY}\n\n{house._SCENE_ATTENTION}\n{house.QUANTITY_DETAIL}"
    assert house.with_house_rules("Task.", opening=False) == f"Task.\n\n{continuation}"
    assert house.with_house_rules("", opening=False) == continuation
    assert house.OPENING_OFFER in (world_agent.render_seed_request("A world.").system or "")
    assert house.OPENING_OFFER not in reviser.revision_system()


def test_later_arc_keeps_continuation_scope_when_prior_prose_is_evicted(tmp_path):
    from litharness.adapters.sqlite_store import SqliteStore

    with SqliteStore.open(tmp_path / "later-arc.db") as store:
        original = a_book(store, scenes=12)
        previous = "Earlier accepted history. " * 1000
        head = original.replacing([
            original.node(f"scene-{index}").with_content(previous)
            for index in range(1, 7)
        ])
        store.commit_revision(head, created_at="2026-09-09T00:00:00Z")
        selected = planner.make_plan_selector(
            project_id=PROJECT_ID, outline=False, token_budget=2500,
            scenes_per_chapter=1, chapters_per_arc=6, open_ended=True,
        )(store, "writer", START, 60)
        assert selected is not None and selected.payload["logical_id"] == "scene-7"
        assert selected.payload["selected_by"]["ordinal"] == 1
        assert selected.payload["context"]["sections"].get(context.PRIOR_PROSE, 0) == 0
        assert selected.payload["context"]["sections"].get(context.SUMMARIES, 0) == 0
        assert house.OPENING_OFFER not in selected.payload["system"]
        assert house.ACCUMULATION not in selected.payload["system"]
        assert house._MAGICAL_OFFER not in selected.payload["system"]
        assert house._SCENE_ATTENTION in selected.payload["system"]
        assert house.QUANTITY_DETAIL in selected.payload["system"]


@pytest.mark.parametrize("target", ["scene-1", "scene-2"])
def test_rebuilding_a_request_for_accepted_prose_keeps_its_original_opening_scope(
    tmp_path, target,
):
    from litharness.adapters.sqlite_store import SqliteStore

    with SqliteStore.open(tmp_path / "rebuild.db") as store:
        original = a_book(store, scenes=6)
        head = original.replacing([
            original.node("scene-1").with_content("The accepted opening."),
            original.node("scene-2").with_content("The accepted continuation."),
            original.node("scene-6").with_content("Accepted later material."),
        ])
        store.commit_revision(head, created_at="2026-09-09T00:00:00Z")
        beat = next(item for item in beats_for(head, template_for(head))
                    if item.logical_id == target)
        system, _ = planner.render_prompt(
            beat, book_title=None, packet=planner.packet_for(store, head, beat),
            has_prior_prose=planner._has_prior_prose(head, target),
        )
        assert (house.OPENING_OFFER in system) is (target == "scene-1")
        assert (house.ACCUMULATION in system) is (target == "scene-1")
        assert (house._MAGICAL_OFFER in system) is (target == "scene-1")
        assert house._SCENE_ATTENTION in system and house.QUANTITY_DETAIL in system


@pytest.mark.parametrize(
    "direction", [house.OPENING_OFFER, house._MAGICAL_OFFER, house.ACCUMULATION],
)
def test_an_explicit_author_lock_is_not_removed_by_house_scope(tmp_path, direction):
    from litharness.adapters.sqlite_store import SqliteStore

    locked = lc.PlanItem(
        logical_id="author-opening-offer", kind=lc.PlanKind.CONSTRAINT,
        text=direction, locked=True, authority=lc.PlanAuthority.INTENDED,
    )
    with SqliteStore.open(tmp_path / "locked.db") as store:
        original = a_book(store, scenes=6, extra_plan_items=(locked,))
        head = original.replacing([original.node("scene-1").with_content("Earlier prose.")])
        store.commit_revision(head, created_at="2026-09-09T00:00:00Z")
        selected = planner.make_plan_selector(project_id=PROJECT_ID, outline=False)(
            store, "writer", START, 60,
        )
        assert selected is not None and selected.payload["logical_id"] == "scene-2"
        system = selected.payload["system"]
        guidance, author_locks = system.split("AUTHOR-LOCKED STORY DECISIONS", 1)
        assert direction not in guidance
        assert direction in author_locks
        assert store.plan_items(BOOK_ID, BRANCH_ID, kind=lc.PlanKind.CONSTRAINT) == [locked]
