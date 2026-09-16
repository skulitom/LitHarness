"""Material provenance and scope must survive before any literary reading can be useful."""

from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import pytest

from litharness.application import concept, outline
from litharness.domain.generation import CompletionRequest

HERE = Path(__file__).parents[1] / "research/quality-measurement/planning-material-20260916"
spec = importlib.util.spec_from_file_location("planning_material_experiment_test", HERE / "run.py")
experiment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(experiment)
material = experiment.material


def fixture():
    source = {
        "author_brief": "The teacher stays absent through chapter 2.",
        "first_arc": {
            "middle": "Scene 3: borrow grip; lose hearing.\n\nRescue the rival.",
            "closes": "Scene 6: settle the loan. The old debt remains open.",
        },
        "debts": [{"subject": "Loan", "owed": "Return the faculty.", "due_scene": 6}],
        "turn": {"event": "Choose a destination", "when": "after the first arc"},
        "discovery": {"experience_brief": "Use and repay the first loan in chapter one."},
    }
    units = list(material.source_units(source))
    value = {
        "developments": [
            {
                "id": "D1",
                "statement": "Borrow grip, lose hearing and rescue the rival.",
                "source_ids": units[:2],
                "depends_on": [],
                "horizon": "first_arc",
            },
            {
                "id": "D2",
                "statement": "Settle the loan; leave the old debt open.",
                "source_ids": units[2:],
                "depends_on": ["D1"],
                "horizon": "first_arc",
            },
        ],
        "staging_options": [],
        "placement_suggestions": [
            {"target_ids": ["D2"], "suggestion": "Scene 6", "source_ids": units[2:]}
        ],
    }
    payload = {
        "book_concept": source,
        "author_locks": [{"text": "No teacher in chapter 2"}],
        "world": {"adhesion_is_not_strength": True},
        "earlier_accepted_scenes": ["Debt opened"],
        "open_promises": [{"subject": "Prior promise", "due_by_scene": 2}],
        "writing_layout": {"target_scene_words": 1400},
        "rules": [concept.FIRST_ARC_RULE, "Another rule"],
    }
    artifact = {"source_concept_sha256": material.digest(source), "material": value}
    return payload, artifact


def test_projection_preserves_author_world_actual_promises_and_generated_debt_content():
    payload, artifact = fixture()
    original = deepcopy(payload)
    received = json.loads(
        material.transform_prompt(json.dumps(payload), artifact, concept.FIRST_ARC_RULE)
    )
    expected = deepcopy(payload)
    del expected["book_concept"]["first_arc"]
    del expected["book_concept"]["debts"][0]["due_scene"]
    expected["rules"][0] = material.PLANNING_RULE
    expected["planning_material"] = {
        "version": material.VERSION,
        "source_concept_sha256": artifact["source_concept_sha256"],
        **artifact["material"],
        "generated_debt_placements": [
            {"debt_index": 0, "subject": "Loan", "suggested_scene": 6},
        ],
    }
    assert received == expected
    assert payload == original


@pytest.mark.parametrize(
    "fault",
    [
        "source",
        "uncovered",
        "duplicate",
        "empty",
        "missing_parent",
        "self_dependency",
        "cycle",
        "placement",
        "unknown_field",
    ],
)
def test_material_rejects_broken_provenance_or_dependencies(fault):
    payload, artifact = fixture()
    value = artifact["material"]
    if fault == "source":
        value["developments"][0]["source_ids"] = ["invented-source"]
    elif fault == "uncovered":
        value["developments"][0]["source_ids"].pop()
    elif fault == "duplicate":
        value["developments"][1]["id"] = "D1"
    elif fault == "empty":
        value["developments"][0]["statement"] = " "
    elif fault in {"missing_parent", "self_dependency", "cycle"}:
        value["developments"][0]["depends_on"] = [
            {
                "missing_parent": "D3",
                "self_dependency": "D1",
                "cycle": "D2",
            }[fault]
        ]
    elif fault == "placement":
        value["placement_suggestions"][0]["target_ids"] = ["absent"]
    else:
        value["author_override"] = "Teacher arrives"
    # jsonschema's validation error and the explicit graph/source errors both refuse input.
    import jsonschema

    with pytest.raises((ValueError, jsonschema.ValidationError)):
        material.validate(value, payload["book_concept"])


@pytest.mark.parametrize("fault", ["author", "arc", "missing_rule", "duplicate_rule"])
def test_projection_refuses_wrong_source_and_rule(fault):
    payload, artifact = fixture()
    if fault == "author":
        payload["book_concept"]["author_brief"] = "A different author"
    elif fault == "arc":
        payload["book_concept"]["first_arc"]["middle"] += "New event"
    elif fault == "missing_rule":
        payload["rules"].remove(concept.FIRST_ARC_RULE)
    else:
        payload["rules"].append(concept.FIRST_ARC_RULE)
    with pytest.raises(ValueError):
        material.transform_prompt(json.dumps(payload), artifact, concept.FIRST_ARC_RULE)


def test_renderer_records_actual_transformation_and_control_is_unchanged(monkeypatch):
    payload, artifact = fixture()
    request = CompletionRequest(
        prompt=json.dumps(payload), system="System", profile="planner.outline.v6", allowed_tools=()
    )
    monkeypatch.setattr(outline, "render_outline_request", lambda: request)
    monkeypatch.setattr(experiment, "verify_pairs", lambda: None)
    monkeypatch.setattr(experiment, "load_material", lambda case: artifact)
    monkeypatch.setattr(experiment.base, "read", lambda path: experiment.base.serial(request))
    experiment.install_transform("A1")
    assert outline.render_outline_request() == request
    # Start from the original renderer, not a nested treatment/control wrapper.
    monkeypatch.setattr(outline, "render_outline_request", lambda: request)
    experiment.install_transform("B1")
    result = outline.render_outline_request()
    assert result.profile == material.PROFILE
    assert result.prompt == material.transform_prompt(
        request.prompt, artifact, concept.FIRST_ARC_RULE
    )
    assert result.system == request.system
    assert result.schema == request.schema
    assert result.allowed_tools == ()


def test_dispatch_keeps_sources_shared_and_limits_continuation_to_fresh_cases():
    assert experiment.order("concept") == ("A1", "A3")
    assert experiment.order("material") == ("B1", "B2", "B3", "B4")
    assert set(experiment.order("chapter1")) == set(experiment.all_books())
    for phase in ("grow1", "accept-grow1", "chapter2", "drain2"):
        assert set(experiment.order(phase)) == {"A1", "B1", "A3", "B3"}
    assert experiment.command("A1", "grow1") == ["architect", "grow", "--scene", "scene-1"]
    with pytest.raises(ValueError, match="Unregistered"):
        experiment.command("A1", "chapter3")


def test_material_cannot_be_replaced_after_its_first_receipt(monkeypatch):
    payload, artifact = fixture()
    artifact["source_units"] = material.source_units(payload["book_concept"])
    state = {
        "calls": [
            {"book": "B1", "profile": "research.planning-material.v1", "path": "calls/1.json"}
        ]
    }
    call = {"status": "completed", "result": {"text": json.dumps(artifact["material"])}}
    files = {
        "materials/1.json": artifact,
        "progress.json": state,
        "calls/1.json": call,
        "preflight/B1-request.json": {"prompt": json.dumps(payload)},
    }
    monkeypatch.setattr(
        experiment.base, "read", lambda path: files[path.relative_to(experiment.LOCAL).as_posix()]
    )
    assert experiment.load_material("1") == artifact
    artifact["material"]["developments"][0]["statement"] = "Replacement story"
    with pytest.raises(ValueError, match="first recorded output"):
        experiment.load_material("1")
