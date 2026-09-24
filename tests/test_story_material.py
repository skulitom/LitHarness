"""The opt-in source has one event owner and withholds generated coordinates. No models."""

from __future__ import annotations

import copy
import json
from dataclasses import replace

import litharness_contracts as lc
import pytest

from litharness import cli
from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import (
    chapter_layout,
    concept,
    export,
    outline,
    planner,
    story_material,
    world_agent,
)
from litharness.domain.beats import arc_template, beats_for
from litharness.domain.plan_refinement import PlanRevision
from litharness.domain.promises import Promise
from litharness.domain.revision import new_book
from litharness.domain.serials import SerialShape
from litharness.providers.base import parse_schema_payload
from tests.test_concept import _example, _scripted

AUTHOR = "  Keep the teacher absent through chapter 2.\nPreserve this wording.  "


def material_payload():
    return {
        "version": story_material.VERSION,
        "world": "WORLD_PROPERTY Reefs carry living weather through mountain passes.",
        "experience_brief": "Desire: reach the reef. Use and consequence: D1. Next desire: D2.",
        "developments": [
            {
                "id": "D1",
                "statement": "OPENING_EVENT A climb reaches the reef but exhausts the seed.",
                "depends_on": [],
                "horizon": "first_arc",
            },
            {
                "id": "D2",
                "statement": "TURN_EVENT She chooses to shelter the stranded gardener.",
                "depends_on": ["D1"],
                "horizon": "first_arc",
            },
            {
                "id": "D3",
                "statement": "LATER_EVENT Cooperation opens a route across the reef.",
                "depends_on": ["D2"],
                "horizon": "later",
            },
            {
                "id": "D4",
                "statement": "OPEN_QUESTION The reef's origin remains unknown.",
                "depends_on": [],
                "horizon": "unresolved",
            },
        ],
        "first_use_id": "D1",
        "turn_id": "D2",
        "questions": [
            {"subject": "a route", "development_ids": ["D3"]},
            {"subject": "the origin", "development_ids": ["D4"]},
        ],
        "staging_options": [
            {
                "id": "S1",
                "statement": "STAGING_PROP Blue rope supports the climb.",
                "development_ids": ["D1"],
            },
        ],
        "placement_suggestions": [
            {"development_id": "D1", "chapter": 987654, "scene": 876543},
        ],
    }


def concept_payload():
    return {
        "person_before": "a gardener tending rooftop plants",
        "exception": "seeds grow bridges",
        "want": "to reach the living reef",
        "system": {
            "name": "Bloom",
            "manner": "petal marks",
            "look": "green veins on the wrist",
            "steps": 8,
            "strongest_known": "can shelter a town",
            "pays": "grow living shelter",
        },
        "threat": {"what": "cold winds wither unprotected growth"},
        "second_system": None,
        "story_material": material_payload(),
    }


def intended():
    return concept.Concept.from_payload({**concept_payload(), "author_brief": AUTHOR})


def test_one_owner_roundtrip_and_provenance_ignore_only_optional_coordinates():
    source = intended()
    restored = concept.Concept.from_text(source.to_text())
    assert source == restored
    assert restored.author_brief == AUTHOR
    payload = restored.to_jsonable()
    assert not {"discovery", "first_arc", "first_use", "turn", "debts"} & payload.keys()
    assert restored.first_arc is None and restored.turn is None
    assert restored.question_count == 2
    material = restored.story_material
    assert material is not None
    assert material.to_jsonable() == material_payload()
    active = material.for_planning()
    changed = copy.deepcopy(payload)
    changed["story_material"]["placement_suggestions"][0]["chapter"] = 2
    assert concept.Concept.from_payload(changed).for_outline() == restored.for_outline()
    changed["story_material"]["developments"][0]["statement"] += " Her hands hurt."
    revised = concept.Concept.from_payload(changed).story_material
    assert revised.for_planning()["source_id"] != active["source_id"]
    assert active["authority"] == "generated_proposal"
    assert restored.plan_item().authority is lc.PlanAuthority.INTENDED
    assert not restored.plan_item().locked


@pytest.mark.parametrize("field", ["discovery", "first_arc", "first_use", "turn", "debts"])
def test_mixed_formats_refuse_a_second_owner(field):
    with pytest.raises(concept.MalformedConcept, match="parallel story sources"):
        concept.Concept.from_payload({**concept_payload(), field: _example().get(field, {})})


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda p: p.pop("second_system"),
        lambda p: p.update(growth="A second story source"),
        lambda p: p["system"].update(due_scene=2),
        lambda p: p["threat"].update(first_reach="chapter 2"),
        lambda p: p.update(
            second_system={"name": "Echo", "manner": "music", "kept": "seeds", "due_scene": 3}
        ),
    ],
)
def test_structured_core_refuses_missing_fields_and_extra_calendar_slots(corrupt):
    payload = concept_payload()
    corrupt(payload)
    with pytest.raises(concept.MalformedConcept):
        concept.Concept.from_payload(payload)


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda p: p.update(version="unknown"),
        lambda p: p.update(world=" "),
        lambda p: p.update(experience_brief=None),
        lambda p: p.update(developments=[]),
        lambda p: p.update(developments="prose"),
        lambda p: p["developments"][1].update(id="D1"),
        lambda p: p["developments"][0].update(depends_on=["missing"]),
        lambda p: p["developments"][0].update(depends_on=["D1"]),
        lambda p: p["developments"][0].update(depends_on=["D2"]),
        lambda p: p["developments"][1].update(depends_on=["D1", "D1"]),
        lambda p: p["developments"][0].update(horizon="chapter 1"),
        lambda p: p["developments"][0].update(due_scene=1),
        lambda p: p.update(first_use_id="missing"),
        lambda p: p.update(turn_id="missing"),
        lambda p: p["questions"][0].update(development_ids=[]),
        lambda p: p["questions"][0].update(development_ids=["missing"]),
        lambda p: p["questions"][0].update(subject="the origin"),
        lambda p: p.update(questions=[]),
        lambda p: p["staging_options"][0].update(id="D1"),
        lambda p: p["staging_options"].append(copy.deepcopy(p["staging_options"][0])),
        lambda p: p["placement_suggestions"][0].update(development_id="missing"),
        lambda p: p["placement_suggestions"].append(copy.deepcopy(p["placement_suggestions"][0])),
        lambda p: p["placement_suggestions"][0].update(chapter=True),
        lambda p: p["placement_suggestions"][0].update(scene=0),
        lambda p: p["placement_suggestions"][0].update(chapter=None, scene=None),
    ],
)
def test_broken_graphs_and_coordinates_fail_before_persistence(corrupt):
    source = material_payload()
    corrupt(source)
    with pytest.raises(ValueError):
        story_material.StoryMaterial.from_payload(source)


def test_empty_optional_lists_and_a_partial_coordinate_are_valid():
    source = material_payload()
    source["staging_options"] = []
    source["placement_suggestions"] = []
    assert story_material.StoryMaterial.from_payload(source).to_jsonable() == source
    source["placement_suggestions"] = [{"development_id": "D2", "chapter": 3, "scene": None}]
    assert story_material.StoryMaterial.from_payload(source).to_jsonable() == source


def test_all_active_projections_omit_coordinates_without_rewriting_author_text():
    source = intended()
    active = [
        source.render(),
        source.render_for_listing(),
        source.render_for_world(),
        json.dumps(source.for_outline()),
        world_agent.render_seed_request("Reef", concept=source).prompt,
        world_agent.render_grow_request(
            "Accepted chapter.", logical_id="scene-1", concept=source
        ).prompt,
    ]
    for view in active:
        assert "987654" not in view and "876543" not in view
        assert "placement_suggestions" not in view
    assert source.for_outline()["author_brief"] == AUTHOR
    assert AUTHOR in world_agent.render_seed_request("Reef", concept=source).prompt
    assert "LATER_EVENT" not in source.render_for_listing()
    assert "OPENING_EVENT" not in source.render_for_world()
    assert "WORLD_PROPERTY" in source.render_for_world()
    seeded = world_agent.render_seed_request("Reef", concept=source).prompt
    assert seeded.count("WORLD_PROPERTY") == 1
    assert source.story_material.experience_brief not in seeded


def test_explicit_whole_concept_lock_retains_coordinates_in_authoritative_context(tmp_path):
    from tests.conftest import BOOK_ID, BRANCH_ID
    from tests.test_outline import a_book

    source = intended()
    locked = replace(source.plan_item(), locked=True)
    with SqliteStore.open(tmp_path / "locked.db") as store:
        head = a_book(store, scenes=6, extra_plan_items=(locked,))
        beats = beats_for(head, arc_template(6))
        packet = planner.packet_for(store, head, beats[0])
        assert "987654" in packet.render()
        assert json.loads(source.render(include_placements=True))["author_brief"] == AUTHOR
        request = outline.render_outline_request(
            "Reef",
            beats,
            base=store.plan_revision(BOOK_ID, BRANCH_ID),
            concept=source,
        )
        payload = json.loads(request.prompt)
        assert (
            next(x for x in payload["author_locks"] if x["logical_id"] == locked.logical_id)["text"]
            == source.to_text()
        )
        assert "placement_suggestions" not in payload["book_concept"]["story_material"]


def test_precision_can_edit_a_statement_but_cannot_rewrite_structure_or_authority():
    payload = concept_payload()
    payload["story_material"]["developments"][0]["statement"] += " She rests nineteen minutes."
    source = concept.Concept.from_payload({**payload, "author_brief": AUTHOR})
    fields, protected = source.precision_material()
    assert protected["author_brief"] == AUTHOR
    for field in (
        "version",
        "first_use_id",
        "turn_id",
        "developments.0.id",
        "developments.0.horizon",
        "developments.1.depends_on.0",
        "questions.0.development_ids.0",
        "staging_options.0.id",
        "staging_options.0.development_ids.0",
        "placement_suggestions.0.development_id",
        "placement_suggestions.0.chapter",
    ):
        assert f"story_material.{field}" in protected
        assert f"story_material.{field}" not in fields
    fixed = source.with_precision_edits(
        {
            "edits": [
                {
                    "field": "story_material.developments.0.statement",
                    "before": "nineteen minutes",
                    "after": "a while",
                }
            ]
        }
    )
    assert fixed.author_brief == AUTHOR
    assert fixed.story_material.developments[0].id == "D1"
    assert fixed.story_material.placement_suggestions == source.story_material.placement_suggestions
    assert "nineteen" not in fixed.story_material.developments[0].statement
    with pytest.raises(ValueError):
        source.with_precision_edits(
            {
                "edits": [
                    {
                        "field": "story_material.developments.0.id",
                        "before": "D1",
                        "after": "changed",
                    }
                ]
            }
        )


@pytest.mark.parametrize("arc", [1, 2])
def test_outline_uses_same_references_with_history_locks_and_actual_promise_dates(arc):
    source = intended()
    revision = new_book("b", "main", title="Reef", scenes=6)
    beats = beats_for(revision, arc_template(6))
    lock = lc.PlanItem(
        logical_id="author-lock",
        kind=lc.PlanKind.CONSTRAINT,
        text="Keep the seed alive.",
        authority=lc.PlanAuthority.INTENDED,
        locked=True,
    )
    premise = lc.PlanItem(
        logical_id="premise",
        kind=lc.PlanKind.PREMISE,
        text="Explore the reef.",
        authority=lc.PlanAuthority.INTENDED,
    )
    base = PlanRevision("b", "main", (premise, source.plan_item(), lock))
    promise = Promise(
        promise_id="actual",
        subject="courier",
        description="Return the borrowed seed.",
        opened_at_key=beats[0].story_order_key,
        due_key=beats[-1].story_order_key,
        opened_by_revision=revision.revision_id,
    )
    request = outline.render_outline_request(
        "Reef",
        beats,
        base=base,
        concept=source,
        serial_arc_index=arc,
        promises=[promise],
        prior_summaries=[("scene-1", "The seed was used and exhausted.")],
        chapter_by_scene={b.logical_id: b.ordinal for b in beats},
        target_scene_words=1400,
    )
    body = json.loads(request.prompt)
    assert request.profile == "planner.outline.structured.v5"
    assert "chapters" in request.schema["properties"]
    assert "development_coverage" in request.schema["required"]
    assert len(body["writing_layout"]["chapters"]) == 6
    assert body["book_concept"]["story_material"] == source.story_material.for_planning()
    assert body["book_concept"]["author_brief"] == AUTHOR
    assert body["author_locks"][0]["text"] == lock.text
    assert body["open_promises"][0]["due_by_scene"] == 6
    assert body["earlier_accepted_scenes"][0]["summary"] == "The seed was used and exhausted."
    assert story_material.PLANNING_RULE in body["rules"]
    assert concept.LATER_ARC_RULE not in body["rules"]
    assert concept.FIRST_ARC_RULE not in body["rules"]
    assert concept.TURN_RULE not in body["rules"]
    assert (concept.MATERIAL_FIRST_USE_RULE in body["rules"]) is (arc == 1)
    assert concept.FIRST_USE_RULE not in body["rules"]
    assert "987654" not in request.prompt


@pytest.mark.parametrize("horizon", ["later", "unresolved"])
def test_a_first_use_outside_the_opening_horizons_is_never_placed_in_chapter_one(horizon):
    """first_use_id is checked only for existence, so its horizon gates the placement."""
    payload = concept_payload()
    payload["story_material"]["developments"][0]["horizon"] = horizon
    source = concept.Concept.from_payload(payload)
    assert not source.places_first_use
    revision = new_book("b", "main", title="Reef", scenes=6)
    beats = beats_for(revision, arc_template(6))
    premise = lc.PlanItem(
        logical_id="premise",
        kind=lc.PlanKind.PREMISE,
        text="Explore the reef.",
        authority=lc.PlanAuthority.INTENDED,
    )
    base = PlanRevision("b", "main", (premise, source.plan_item()))
    body = json.loads(
        outline.render_outline_request(
            "Reef",
            beats,
            base=base,
            concept=source,
            serial_arc_index=1,
        ).prompt
    )
    assert story_material.PLANNING_RULE in body["rules"]
    assert concept.MATERIAL_FIRST_USE_RULE not in body["rules"]
    assert intended().places_first_use


def test_material_invention_asks_for_one_person_s_exception_and_counted_ranks():
    """Delivery of the restored directions (stage-0 §255), not evidence of compliance."""
    from litharness.application import discovery

    request = concept.render_material_request(
        AUTHOR,
        layout=chapter_layout.WritingLayout.opening(6, SerialShape(1, 6), 1400),
    )
    for asked in (
        "nobody else in the world has",
        "even where the system itself is shared",
        "start_rank",
        "0 when they start unranked",
        "the first time the exception works for them",
        "colour, place, light, type",
    ):
        assert asked in request.system, asked
    assert request.system.count(discovery.DIRECTION) == 1
    assert request.system.count(discovery.WORLD_DIRECTION) == 1
    assert "need not be unique" not in request.system
    assert request.profile == "writer.concept.material.v5"
    system = request.schema["properties"]["system"]
    assert system is concept.COUNTED_SYSTEM_SCHEMA
    assert list(request.schema["properties"])[:5] == [
        "person_before",
        "exception",
        "want",
        "system",
        "second_system",
    ]


def test_stored_material_concepts_without_a_start_rank_still_read():
    """The 2026-09-19 trial's concept has the six legacy system keys and must keep reading."""
    assert "start_rank" not in intended().to_jsonable()["system"]
    counted = concept_payload()
    counted["system"]["start_rank"] = 1
    drawn = concept.Concept.from_payload(counted)
    assert drawn.system.start_rank == 1
    assert concept.Concept.from_text(drawn.to_text()) == drawn
    assert drawn.for_outline()["system"]["start_rank"] == f"rank 1 of {drawn.system.steps}"
    counted["system"]["due_scene"] = 2
    with pytest.raises(concept.MalformedConcept, match="unexpected structured system fields"):
        concept.Concept.from_payload(counted)


def test_cli_invents_once_retains_exact_brief_and_reopens_as_one_intended_source(
    tmp_path,
    monkeypatch,
):
    call = _scripted(concept_payload(), {"edits": []})
    monkeypatch.setattr(cli, "_completion_call", call)
    brief = tmp_path / "brief.txt"
    brief.write_text(AUTHOR, encoding="utf-8")
    db, out = tmp_path / "book.db", tmp_path / "concept"
    common = ["--database", str(db), "--chapter-scenes", "1", "--arc-chapters", "6"]
    assert (
        cli.main(
            [
                *common,
                "concept",
                "--planning-material",
                "--brief-file",
                str(brief),
                "--no-seed",
                "--scenes",
                "6",
                "--out",
                str(out),
            ]
        )
        == cli.EXIT_OK
    )
    assert [r.profile for r in call.seen] == [concept.MATERIAL_CONCEPT_PROFILE]
    request = call.seen[0]
    assert json.loads(request.prompt)["author_brief"] == AUTHOR
    assert request.allowed_tools == ()
    assert parse_schema_payload(json.dumps(concept_payload()), request.schema) == concept_payload()
    # New requests ask for the counted start; the stored shape without it still reads below.
    assert "start_rank" in request.schema["properties"]["system"]["required"]
    assert parse_schema_payload(json.dumps(_example()), request.schema) is None
    assert not (out / "discovery-trace.json").exists()
    assert (out / "concept-trace-1.json").exists()
    source = concept.Concept.from_text((out / "concept.json").read_text(encoding="utf-8"))
    assert source == intended()
    assert (
        cli.main(
            [
                *common,
                "new",
                "Reef",
                "--premise",
                "Explore the reef.",
                "--scenes",
                "6",
                "--concept",
                str(out / "concept.json"),
            ]
        )
        == cli.EXIT_OK
    )
    with SqliteStore.open(db) as store:
        book, branch = export.resolve_branch(store, None, None)
        assert concept.concept_of(store.plan_items(book, branch)) == source
        assert store.promises(book, branch) == []
        head = store.head(book, branch)
        packet = planner.packet_for(store, head, beats_for(head, arc_template(6))[0])
        assert AUTHOR in packet.render()
        assert "987654" not in packet.render()


def test_cli_invalid_graph_is_recorded_but_not_repaired_or_persisted(tmp_path, monkeypatch):
    payload = concept_payload()
    payload["story_material"]["developments"][0]["depends_on"] = ["D2"]
    call = _scripted(payload)
    monkeypatch.setattr(cli, "_completion_call", call)
    out = tmp_path / "concept"
    assert (
        cli.main(
            [
                "--database",
                str(tmp_path / "book.db"),
                "concept",
                "--planning-material",
                "--out",
                str(out),
                "--no-seed",
            ]
        )
        == cli.EXIT_FAULT
    )
    assert len(call.seen) == 1
    assert (out / "concept-trace-1.json").exists()
    assert not (out / "concept.json").exists()


def test_structured_mode_refuses_exemplars_before_loading_or_spending(
    tmp_path, monkeypatch, capsys
):
    call = _scripted(concept_payload())
    monkeypatch.setattr(cli, "_completion_call", call)
    db = tmp_path / "book.db"
    assert (
        cli.main(
            [
                "--database",
                str(db),
                "--exemplars",
                str(tmp_path / "absent-shelf"),
                "concept",
                "--planning-material",
            ]
        )
        == cli.EXIT_FAULT
    )
    assert "cannot be combined with --exemplars" in capsys.readouterr().err
    assert not call.seen
    assert not db.exists()


def test_legacy_concept_roundtrip_and_invention_default_are_unchanged():
    source = concept.Concept.from_payload(_example())
    assert source.to_jsonable() == _example()
    assert source.story_material is None
    assert not cli.build_parser().parse_args(["concept"]).planning_material
    assert concept.FIRST_ARC_RULE in concept.outline_rules(1)
    assert concept.LATER_ARC_RULE in concept.outline_rules(2)


def test_request_respects_person_seed_and_distinct_source_without_another_story_calendar():
    from litharness.domain.invention import make_seed

    layout = chapter_layout.WritingLayout.opening(6, SerialShape(1, 6), 1400)
    for seed in (None, make_seed("example"), make_seed("example", version="invention-seed.v2")):
        request = concept.render_material_request(
            AUTHOR,
            layout=layout,
            person="third",
            seed=seed,
            distinct_from=["Old world"],
        )
        data = json.loads(request.prompt)
        assert data["author_brief"] == AUTHOR
        assert data["narrative_person"] == "third"
        assert data["previous_concepts_to_differ_from"] == ["Old world"]
        assert data["writing_layout"] == layout.to_jsonable()
        assert "The author's supplied brief takes priority" in request.system
        assert "scene assignments belong ONLY" in request.system
