"""Character declarations use ordinary state without weakening explicit mechanics."""

from __future__ import annotations

import json
from pathlib import Path

import litharness_contracts as lc
import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import planner, world_agent
from litharness.application.model_context import at_scene
from litharness.cli import EXIT_OK, main
from litharness.domain import characters, context, state, world_brief, worlds
from litharness.domain.beats import arc_template, beats_for


@pytest.mark.parametrize("rule", [
    "Rook cannot speak a sentence he believes to be false.",
    "Rook distrusts strangers, and iron burns his skin.",
])
def test_declared_character_changes_reach_writer_without_reclassifying_rules(
    tmp_path: Path, rule: str,
) -> None:
    db = tmp_path / "book.db"
    base = ["--database", str(db)]
    assert main([
        *base, "new", "Book", "--premise", "Rook seeks his missing sister.",
        "--scenes", "6", "--person", "first",
    ]) == EXIT_OK
    opening = [
        {"subject": "rook", "predicate": "entity_role", "value": "protagonist"},
        {"subject": "rook", "predicate": "entity_role", "value": "cast"},
        {"subject": "rook", "predicate": "wants", "value": "find his sister"},
        {"subject": "rook", "predicate": "voice_tag", "value": "quiet and direct"},
        {"subject": "rook", "predicate": "disposition", "value": "suspicious of strangers"},
        {"subject": "rook", "predicate": "world_rule", "value": rule},
    ]
    assert main([
        *base, "world", "declare-batch", "--records", json.dumps(opening),
    ]) == EXIT_OK
    with SqliteStore.open_read_only(db) as store:
        book_id, branch_id, _ = store.branches()[0]
        proposals = store.state_records(book_id, branch_id)
        assert proposals and all(
            row.authority is lc.StateAuthority.PROPOSED for row in proposals
        )
        assert characters.cast(proposals) == ()
    assert main([*base, "world", "accept"]) == EXIT_OK
    changed = [
        {"subject": "rook", "predicate": "disposition", "value": "trusts his companions",
         "order_key": "s2"},
        {"subject": "rook", "predicate": "wants", "value": "bring his sister home",
         "order_key": "s2"},
    ]
    assert main([
        *base, "world", "declare-batch", "--records", json.dumps(changed),
    ]) == EXIT_OK
    assert main([*base, "world", "accept"]) == EXIT_OK

    with SqliteStore.open_read_only(db) as store:
        revision = store.head(book_id, branch_id)
        records = store.state_records(book_id, branch_id)
        original_records = tuple(records)
        beats = beats_for(revision, arc_template(6))
        rule_record = next(row for row in records if row.predicate == "world_rule")
        assertions = [
            row for row in records if row.predicate in {"wants", "voice_tag", "disposition"}
        ]
        assert len(assertions) == 5
        assert all(row.kind is lc.StateRecordKind.ASSERTION for row in assertions)
        assert worlds.operating_rule_ids(records) == {rule_record.record_id}
        for beat, disposition, want in (
            (beats[0], "suspicious of strangers", "find his sister"),
            (beats[1], "trusts his companions", "bring his sister home"),
        ):
            packet = planner.packet_for(store, revision, beat)
            system, prompt = planner.render_prompt(beat, book_title="Book", packet=packet)
            assert rule in system and f"Rule — {rule}" in packet.render_rules()
            assert "AUTHOR-LOCKED STORY DECISIONS" in system
            assert "first person" in system
            assert {item.item_id for item in packet.sections[context.RULES]} == {
                rule_record.record_id,
            }
            cast_text = "\n".join(item.text for item in packet.sections[context.CAST])
            assert f"disposition: {disposition}" in cast_text
            assert f"wants: {want}" in cast_text
            assert "sounds: quiet and direct" in cast_text
            assert disposition in prompt and disposition not in system
            view = at_scene(
                revision, records, beat.logical_id, moment=state.StateMoment.ENTERING,
                story_order_key=beat.story_order_key,
            )
            character = characters.sheet(view.active_records, "rook")
            assert character.disposition == disposition
            assert character.to_jsonable()["disposition"] == disposition
            assert characters.rows([character])[0]["disposition"] == disposition
            assert character.causes == ()
            brief = world_brief.brief_for(view.active_records)
            assert brief is not None
            groups = dict(brief.groups)
            assert groups["rules"] == (f"Rule — {rule}",)
            assert any(disposition in line for line in groups["cast"])
        current = planner.packet_for(store, revision, beats[1])
        assert any("suspicious of strangers" in item.text
                   for item in current.sections[context.HISTORY])
        assert "suspicious of strangers" not in "\n".join(
            item.text for item in current.sections[context.CAST]
        )
        assert tuple(store.state_records(book_id, branch_id)) == original_records

    # A later story position can change a trait; another proposal at the same
    # position cannot overwrite the accepted value.
    assert main([
        *base, "world", "declare", "rook", "disposition", "--value", "quietly reckless",
        "--order-key", "s2",
    ]) == EXIT_OK
    assert main([*base, "world", "accept"]) == EXIT_OK
    with SqliteStore.open_read_only(db) as store:
        records = store.state_records(book_id, branch_id)
        stray = next(row for row in records if row.value == "quietly reckless")
        assert stray.authority is lc.StateAuthority.PROPOSED
        assert tuple(row for row in records if state.is_canon(row)) == original_records
        packet = planner.packet_for(store, revision, beats[1])
        assert "quietly reckless" not in packet.render()


def test_seed_and_grow_expose_character_assertions_and_preserve_character_mechanics() -> None:
    for request in (
        world_agent.render_seed_request("A stranger reaches a magical world."),
        world_agent.render_grow_request("Rook trusted her.", logical_id="scene-2"),
    ):
        assert "Use wants for current desires, voice_tag for speaking manner" in request.system
        assert "disposition for ordinary temperament or habits" in request.system
        assert "Beliefs use believes edges to claims" in request.system
        assert "physiology or curses remain world rules" in request.system
        assert "separate these from personality" in request.system


def test_absent_disposition_adds_no_invented_trait_to_existing_characters() -> None:
    character = characters.sheet((), "stranger")
    assert character.disposition == ""
    assert "disposition" not in character.to_jsonable()
    assert character.render() == "stranger"
