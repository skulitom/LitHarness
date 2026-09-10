"""An unscheduled result on the page must survive into the next writer's current state."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256

import pytest

from litharness import cli
from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import concept, planner
from litharness.application.conductor import Conductor, TickOutcome
from litharness.application.handlers import make_scene_draft_handler
from litharness.domain import gamesystem, house, worlds
from litharness.domain.beats import SIX_BEAT, beats_for
from litharness.domain.extraction import STATUS_PREDICATE, system_voice_example
from litharness.domain.moves import status_update_syntax
from litharness.domain.sheet import sheet_for, state_as_it_stands
from litharness.domain.text import content_hash
from litharness.providers.fake import FakeProvider
from litharness.providers.registry import ProviderRegistry
from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID
from tests.helpers import accepted, accepted_all
from tests.test_concept import _example
from tests.test_extraction import _ordinal_line_world
from tests.test_outline import START, a_book
from tests.test_progression_gate import _system


def _world(initial_rank):
    system = _system(rank_label="Circle", ranks=(
        gamesystem.Rank("rung_hand", "Copper"),
        gamesystem.Rank("rung_fitter", "Ash"),
        gamesystem.Rank("rung_shaper", "Glass"),
    ))
    holdings = [
        accepted(worlds.world_record("mira", worlds.CAN_DO, object_ref="read_the_grain", value=2)),
        accepted(worlds.world_record("mira", worlds.STANDS_AT_PREDICATE,
                                    object_ref="rung_hand", value=system.criterion)),
    ] if initial_rank else []
    return [
        *accepted_all(gamesystem.records_for(system)),
        accepted(worlds.world_record("mira", "is_a", value="Mira Vale")),
        accepted(worlds.world_record("mira", worlds.ENTITY_ROLE_PREDICATE, value="protagonist")),
        *holdings,
        accepted(worlds.world_record("mira", STATUS_PREDICATE,
                                    value={"rank": initial_rank,
                                           **({"read_the_grain": 2} if initial_rank else {})})),
    ]


@pytest.mark.parametrize("changed", [False, True])
@pytest.mark.parametrize("concept_backed", [False, True])
@pytest.mark.parametrize("initial_rank", [0, 1])
@pytest.mark.parametrize("separator", [" ", ": ", ":", " : "])
def test_unscheduled_result_survives_acceptance_and_next_writer_request(
    tmp_path, monkeypatch, changed, concept_backed, initial_rank, separator,
):
    held = f" | read the grain{separator}2" if initial_rank else ""
    acquired = "" if initial_rank else f" | read the grain{separator}2"
    opening = f"[STATUS] Mira Vale — Circle{separator}{initial_rank}{held}"
    outcome = (
        f"[STATUS] Mira Vale — Circle{separator}{initial_rank + 1}{acquired}\n"
        f"[STATUS] Mira Vale — stand the frame{separator}1"
    )
    text = (
        "Mira lifted the latch and stopped when the wood split beside her thumb. She slid "
        "her hand clear, waiting for the loose door to settle. The passage beyond it was "
        "empty. She listened for her companion before trying the latch from the other side.\n"
        + opening + "\n"
        + ("She steadied the frame until it held her weight.\n" + outcome + "\n" if changed else
           "The door opened. She went through without trying another pattern.\n")
    )
    provider = FakeProvider(responses=[text])
    registry = ProviderRegistry(provider)
    monkeypatch.setattr(cli, "build_default_registry", lambda: registry)
    source = concept.Concept.from_payload(_example()).plan_item()
    with SqliteStore.open(tmp_path / "round-trip.db") as store:
        a_book(store, scenes=6, sheet=False,
               extra_plan_items=(source,) if concept_backed else ())
        known = _world(initial_rank)
        retention = accepted(worlds.world_record(
            "patterns", worlds.WORLD_RULE_PREDICATE,
            value="An acquired pattern remains available after its teaching tool is lost.",
        ))
        known.append(retention)
        store.record_state_records(BOOK_ID, BRANCH_ID, known, created_at="2026-09-09T00:00:00Z")
        args = cli.build_parser().parse_args([
            "--project", PROJECT_ID, "--no-outline", "--chapter-scenes", "1",
            "--arc-chapters", "6", "tick",
        ])
        conductor = Conductor(
            store=store, holder="writer", project_id=PROJECT_ID, registry=registry,
            select=cli._conductor(store, args).select,
            # Follow-up evaluations/summaries are independent of this state handoff.
            # Keep the ordinary draft handler and all its acceptance gates.
            handlers={planner.SCENE_DRAFT: make_scene_draft_handler(
                registry, store, PROJECT_ID, policy=cli._draft_policy(args),
            )},
        )
        result = conductor.tick(START)
        assert result.outcome is TickOutcome.RAN_JOB
        assert result.job_id is not None
        first = store.load_job(result.job_id)
        assert first.job_kind == planner.SCENE_DRAFT
        system = first.payload["system"]
        assert house.with_house_rules("", limited_viewpoint=True) in system
        entering_line = system_voice_example(known)
        assert entering_line is not None and entering_line in system
        assert "stand the frame 0" not in system
        assert ("Print that line exactly once" in system) is not concept_backed
        assert ("available update columns" in system) is concept_backed
        if concept_backed:
            assert "1 = Copper; 2 = Ash; 3 = Glass" in system
            assert "no update is required" in system
        decision = store.latest_decision_for(first.job_id)
        assert decision is not None and decision.accepted
        assert decision.resulting_revision_id is not None
        head = store.load_revision(decision.resulting_revision_id)
        assert head.node("scene-1").content == text
        records = store.state_records(BOOK_ID, BRANCH_ID)
        expected = {"rank": initial_rank + int(changed)}
        if initial_rank or changed:
            expected["read_the_grain"] = 2
        if changed:
            expected["stand_the_frame"] = 1
        assert state_as_it_stands(records, at="s2") == ("mira", expected)
        extracted = [record for record in records if record.evidence]
        new_standings = [record for record in extracted
                         if record.predicate == worlds.STANDS_AT_PREDICATE]
        new_holdings = [record for record in extracted if record.predicate == worlds.CAN_DO]
        attained = "rung_fitter" if initial_rank else "rung_hand"
        assert [record.object_ref for record in new_standings] == ([attained] if changed else [])
        expected_holdings = {("stand_the_frame", 1)} if changed else set()
        if changed and not initial_rank:
            expected_holdings.add(("read_the_grain", 2))
        assert {(record.object_ref, record.value) for record in new_holdings} == expected_holdings
        if changed:
            for record in [*new_standings, *new_holdings]:
                [span] = record.evidence
                accepted_text = head.node("scene-1").content
                evidence_text = accepted_text[span.start:span.end]
                assert evidence_text.endswith(outcome)
                assert span.start == accepted_text.index(opening if initial_rank else outcome)
                assert span.content_sha256 == content_hash(evidence_text)
                assert span.source.logical_id == "scene-1"
        second = conductor.select(store, "next-writer", START + 1, 60)
        assert second is not None and second.job_kind == planner.SCENE_DRAFT
        next_line = system_voice_example(records, at="s2")
        assert next_line is not None and next_line in second.payload["system"]
        assert (entering_line not in second.payload["system"]) is changed
        assert text.rstrip() in second.payload["prompt"], "the earlier display stays in history"
        assert ("stand the frame 1" in second.payload["system"]) is changed
        assert house.ACCUMULATION not in second.payload["system"]
        assert house._MAGICAL_OFFER not in second.payload["system"]
        assert house._SCENE_ATTENTION in second.payload["system"]
        assert house.SCENE_CLARITY in second.payload["system"]
        if concept_backed:
            syntax = status_update_syntax(records)
            assert syntax is not None and syntax in second.payload["system"]
        for job in (first, second):
            entries = job.payload["prompt_sources"]["entries"]
            [rule] = [entry for entry in entries if entry["source"].get(
                "source_logical_id"
            ) == retention.record_id]
            assert rule["stage"] == "system" and rule["section"] == "rules"
            assert rule["source"]["authority"] == retention.authority.value
            assert retention.value in job.payload["system"][rule["start"]:rule["end"]]
            for entry in entries:
                fragment = job.payload[entry["stage"]][entry["start"]:entry["end"]]
                assert sha256(fragment.encode("utf-8")).hexdigest() == entry["sha256"]
        assert next(record for record in records if record.record_id == retention.record_id) == (
            retention
        )
        assert provider.calls == 1, "no model stage was added to record the change"


def test_update_syntax_preserves_typed_columns_and_does_not_guess_a_numeric_ladder():
    records = _ordinal_line_world()
    declaration = next(record for record in records if record.predicate == "status_sheet")
    fields = [*declaration.value["fields"],
              {"name": "stamina", "label": "Breath", "paired": True},
              {"name": "title", "label": "Title", "kind": "name"},
              {"name": "motto", "label": "Motto", "kind": "text"},
              {"name": "skills", "label": "Patterns", "kind": "set"}]
    records = [replace(record, value={"fields": fields, "show_unheld": False})
               if record is declaration else record for record in records]
    syntax = status_update_syntax(records)
    assert syntax is not None
    assert "Grade: declared rung name" in syntax and "numeric mapping" not in syntax
    assert "Breath: current/maximum integers" in syntax
    assert "Title: declared entity name" in syntax and "Motto: text on this line" in syntax
    assert "complete comma-separated list" in syntax and "replaces its whole list" in syntax
    sheet = sheet_for(records)
    assert sheet is not None
    [(_, values, _)] = sheet.read(
        "[STATUS] Silas — Grade Second Seal | Breath 3/5 | Title Warden | "
        "Motto Keep going | Patterns Cold seal 2, Frame 1",
        ids={"second seal": "second_seal", "warden": "warden",
             "cold seal": "seal", "frame": "frame"},
    )
    assert values == {"rank": "second_seal", "stamina": 3, "stamina_max": 5,
                      "title": "warden", "motto": "Keep going",
                      "skills": [["seal", 2], ["frame", 1]]}
    assert status_update_syntax([]) is None


def test_declared_update_grammar_does_not_require_a_prior_snapshot(tmp_path):
    with SqliteStore.open(tmp_path / "no-snapshot.db") as store:
        revision = a_book(store, scenes=6, sheet=False)
        records = [record for record in _world(0) if record.predicate != STATUS_PREDICATE]
        assert system_voice_example(records) is None
        syntax = status_update_syntax(records)
        assert syntax is not None
        beat = beats_for(revision, SIX_BEAT)[0]
        system, _ = planner.render_prompt(
            beat, book_title="Book", packet=planner.packet_for(store, revision, beat),
            status_syntax=syntax, require_status=False,
            notices=("[BELL] The warning bell has sounded.",),
        )
        assert syntax in system
        assert "state as it stands" not in system
        assert "Use the compact update as the result announcement" in system
        assert "warnings, choices, explicitly required notices and author locks" in system
        assert "[BELL] The warning bell has sounded." in system and "exactly once" in system


def test_ambiguous_printing_systems_keep_grammar_without_guessing_rung_numbers():
    records = _world(0)
    other = _system(system_id="other", criterion="other_rank", ranks=(
        gamesystem.Rank("other_first", "First"),
        gamesystem.Rank("other_second", "Second"),
        gamesystem.Rank("other_third", "Third"),
    ), abilities=tuple(
        replace(ability, ability_id=f"other_{ability.ability_id}", name=f"other {ability.name}",
                needs=tuple(replace(need, ref=f"other_{need.ref}") for need in ability.needs))
        for ability in _system().abilities
    ))
    declaration = next(record for record in records if record.predicate == "status_sheet")
    fields = [*declaration.value["fields"], *(
        {"name": ability.ability_id, "label": ability.name} for ability in other.abilities
    )]
    records = [replace(record, value={**record.value, "fields": fields})
               if record is declaration else record for record in records]
    # The sheet covers both systems' columns, so neither owns its numeric rung mapping.
    records.extend(record for record in accepted_all(gamesystem.records_for(other))
                   if record.predicate != "status_sheet")
    syntax = status_update_syntax(records)
    assert syntax is not None and "numeric mapping" not in syntax
