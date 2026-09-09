"""Drafting and revision share clarity guidance without sharing their full tasks."""

from __future__ import annotations

from litharness.application import planner, reviser
from litharness.domain import beats as beats_domain
from litharness.domain import context as context_domain
from litharness.domain import house


def test_both_edits_ride_the_scene_writers_live_assembled_prompt() -> None:
    system, _prompt = planner.render_prompt(
        beats_domain.Beat(
            logical_id="s1", ordinal=1, of_total=1, title=None,
            function="setup", template_id=beats_domain.SIX_BEAT.template_id,
        ),
        book_title=None,
        packet=context_domain.ContextPacket(
            query_id="prompt-scope", target_logical_id="s1", book_id="book",
            branch_id="main", base_revision_id="r0",
        ),
    )
    assert house.CLARITY in system
    assert reviser._TASK not in system
    revising = reviser.revision_system()
    assert revising.count(house.CLARITY) == 1
    assert house.READER not in revising
