"""Declared mechanics survive budgeting and reach the writer as constraints, not plot."""

from dataclasses import replace
from pathlib import Path

import litharness_contracts as lc
import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import planner
from litharness.domain import context, worlds
from litharness.domain.beats import beats_for, template_for
from tests.conftest import PROJECT_ID, meta
from tests.helpers import accepted
from tests.test_outline import START, a_book
from tests.test_worlds import one_scene_book


def _rules() -> tuple[lc.StateRecord, ...]:
    return tuple(
        accepted(row)
        for row in (
            worlds.world_record(
                "gate", worlds.WORLD_RULE_PREDICATE, value="There are three sentries per bridge."
            ),
            worlds.world_record(
                "crossing", worlds.COSTS, value="Four tokens, paid at sunset before passage opens."
            ),
            worlds.world_record("crossing", worlds.REQUIRES, object_ref="seal"),
            worlds.world_record("courier", worlds.EDGE_PREDICATE, value="Can cross before sunset."),
            worlds.world_record("courier", worlds.EXCEPTION_PREDICATE, object_ref="gate"),
            worlds.world_record(
                "courier", worlds.PRICE_PREDICATE, value="Loses the seal when crossing early."
            ),
        )
    )


def test_rules_survive_a_budget_that_evicts_optional_facts_and_keep_provenance() -> None:
    rules = _rules()
    full = context.assemble(one_scene_book(), "scene-2", state_records=rules)
    required = sum(item.tokens for item in full.sections[context.RULES])
    noise = accepted(worlds.world_record("bridge", "history", value="old " * 200))
    packet = context.assemble(
        one_scene_book(),
        "scene-2",
        state_records=(*rules, noise),
        token_budget=required,
        reserved_output=0,
    )
    assert packet.used_tokens == required
    assert {item.source_logical_id for item in packet.sections[context.RULES]} == {
        row.record_id for row in rules
    }
    assert all(item.authority is lc.StateAuthority.ACCEPTED_CANON for item in packet.items)
    assert any(item.source_logical_id == noise.record_id for item in packet.omitted)
    assert packet.sections[context.FACTS] == ()
    rendered = packet.render()
    for item in packet.sections[context.RULES]:
        assert rendered.count(item.text) == 1
    artifact = packet.to_contract(
        meta("context_packet", "rules"), project_id=PROJECT_ID, packet_id="rules"
    )
    assert lc.from_jsonable(lc.ContextPacket, lc.to_jsonable(artifact)) == artifact
    with pytest.raises(context.ContextBudgetTooSmall, match="world rule"):
        context.assemble(
            one_scene_book(),
            "scene-2",
            state_records=rules,
            token_budget=required - 1,
            reserved_output=0,
        )


def test_author_constraints_cannot_be_dropped_to_fit_a_packet() -> None:
    lock = lc.PlanItem(
        logical_id="author-limit",
        kind=lc.PlanKind.CONSTRAINT,
        text="The bridge never opens.",
        authority=lc.PlanAuthority.INTENDED,
        locked=True,
    )
    with pytest.raises(context.ContextBudgetTooSmall, match=r"author constraint.*author-limit"):
        context.assemble(
            one_scene_book(), "scene-2", plan_items=[lock], token_budget=1, reserved_output=0
        )


def test_reified_limit_keeps_its_scope_and_exception_once() -> None:
    rows = tuple(
        accepted(worlds.world_record("capacity", predicate, value=value, object_ref=target))
        for predicate, value, target in (
            (worlds.TYPE_PREDICATE, worlds.CARDINALITY_CONSTRAINT, None),
            (worlds.PREDICATE_PREDICATE, "carries", None),
            (worlds.MAXIMUM_PREDICATE, 3, None),
            (worlds.SCOPE_PREDICATE, None, "ferry"),
            (worlds.GROUP_KEY_PREDICATE, "subject", None),
            (worlds.EXCEPTS_PREDICATE, None, "barge"),
        )
    )
    packet = context.assemble(one_scene_book(), "scene-2", state_records=rows)
    (item,) = packet.sections[context.RULES]
    assert (
        item.text == "at most 3 carries for anything that is a ferry at one time, except for barge"
    )
    assert packet.sections[context.FACTS] == ()
    assert packet.omitted == ()


def test_rule_protection_does_not_promote_proposals_future_state_or_another_pov() -> None:
    base = _rules()[0]
    rows = (
        replace(base, record_id="proposal", authority=lc.StateAuthority.PROPOSED),
        replace(base, record_id="future", story_position=lc.StoryPosition(order_key="s9")),
        replace(base, record_id="private", pov_visibility=["another-person"]),
    )
    packet = context.assemble(
        one_scene_book(), "scene-2", state_records=rows, story_time_cutoff="s2"
    )
    assert not packet.sections.get(context.RULES)
    assert base.value not in packet.render()
    assert not worlds.operating_rule_ids(rows[:1])


def test_superseded_prices_are_history_and_hidden_rules_stay_hidden() -> None:
    base = _rules()[1]
    older = replace(
        base,
        record_id="old",
        value="Two tokens per crossing.",
        story_position=lc.StoryPosition(order_key="s1"),
    )
    current = replace(base, record_id="current", story_position=lc.StoryPosition(order_key="s2"))
    secret = replace(
        _rules()[0],
        record_id="secret",
        subject="secret",
        predicate=worlds.CLAIM_CONTENT,
        value="The river accepts the seal.",
    )
    packet = context.assemble(
        one_scene_book(),
        "scene-2",
        state_records=[older, current, secret],
        story_time_cutoff="s3",
        project_state_changes=True,
    )
    assert {item.item_id for item in packet.sections[context.RULES]} == {"current"}
    assert {item.item_id for item in packet.sections[context.HISTORY]} == {"old"}
    assert {item.item_id for item in packet.sections[context.HIDDEN]} == {"secret"}
    assert secret.value not in packet.render_rules()
    assert secret.value in packet.render().split("True, and the reader has not been told")[1]
    with pytest.raises(context.ContextBudgetTooSmall, match="world rule"):
        context.assemble(
            one_scene_book(), "scene-2", state_records=[secret], token_budget=1, reserved_output=0
        )


def test_writer_gets_the_rule_block_above_guidance_and_below_author_locks(tmp_path: Path) -> None:
    lock = lc.PlanItem(
        logical_id="author-limit",
        kind=lc.PlanKind.CONSTRAINT,
        text="Nobody crosses in this chapter.",
        authority=lc.PlanAuthority.INTENDED,
        locked=True,
    )
    with SqliteStore.open(tmp_path / "book.db") as store:
        revision = a_book(store, scenes=6, extra_plan_items=[lock])
        store.record_state_records(
            revision.book_id, revision.branch_id, _rules(), created_at="2026-08-16T00:00:00Z"
        )
        job = planner.make_plan_selector(project_id=PROJECT_ID, outline=False)(
            store, "writer", START, 60.0
        )
        assert job is not None
        system, prompt = job.payload["system"], job.payload["prompt"]
        assert "World rules and limits" in system
        assert "before its dependent effect" in system
        assert "Preserve declared quantities and entity identities" in system
        assert system.index("World rules and limits") < system.index(
            "AUTHOR-LOCKED STORY DECISIONS"
        )
        assert "Four tokens" in system and "Four tokens" not in prompt
        assert job.payload["context"]["sections"][context.RULES] == len(_rules())
        beat = beats_for(revision, template_for(revision))[0]
        packet = planner.packet_for(store, revision, beat)
        assert all(packet.contains_ref(row.record_id) for row in _rules())


def test_undeclared_rules_add_nothing_to_context() -> None:
    packet = context.assemble(one_scene_book(), "scene-2")
    assert context.RULES not in packet.sections
    assert packet.render_rules() == ""
    assert packet.render() == packet.render(include_rules=False)


def test_pov_access_to_a_fact_does_not_claim_the_character_knows_it() -> None:
    fact = accepted(worlds.world_record("river", "depth", value="Nine fathoms."))
    packet = context.assemble(
        one_scene_book(), "scene-2", state_records=(*_rules(), fact), pov_character_id="courier"
    )
    rendered = packet.render()
    assert "Nine fathoms" in rendered
    assert "not automatically character knowledge" in rendered
    assert "does not mean a character knows them" in packet.render_rules()
    assert "known to courier" not in rendered
