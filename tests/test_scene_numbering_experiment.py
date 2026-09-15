"""Registered coordinate edits must not reach author timing or unrelated story inputs."""

from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from litharness.application import outline
from litharness.domain.generation import CompletionRequest

PATH = Path(__file__).parents[1] / "research/quality-measurement/scene-numbering-20260916/run.py"
spec = importlib.util.spec_from_file_location("scene_numbering_experiment_test", PATH)
experiment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(experiment)


def fixture():
    payload = {
        "book_concept": {
            "author_brief": "Scene 3 must keep the door shut; chapter 4 opens it.",
            "first_arc": {"opens": "Scene 1 belongs to the supplied opening.",
                          "middle": "Scene 3 begins the repair. It costs three coins.",
                          "closes": "Scene 6 settles the job. The debt remains unpaid."},
            "debts": [{"subject": f"debt-{i}", "owed": "Keep the third promise.", "due_scene": i}
                      for i in (3, 4, 5, 6)],
            "discovery": {"experience_brief": "Repair and payment in the opening chapter."},
        },
        "author_locks": [{"text": "Reveal only after scene 6.", "locked": True}],
        "world": {"quantity": 3, "history": "A prior scene 3 is established."},
        "scenes": [{"ordinal": i} for i in range(1, 7)],
        "rules": ["Author instructions take priority."],
        "writing_layout": {"target_scene_words": 1400},
    }
    prompt = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)
    recipe = {
        "source_prompt_sha256": experiment.digest(prompt), "due_scenes": [3, 4, 5, 6],
        "edits": [{"field": "middle", "before": "Scene 3 begins the repair.",
                   "after": "The repair begins."},
                  {"field": "closes", "before": "Scene 6 settles the job.",
                   "after": "The job is settled."}],
    }
    control = {"prompt": prompt, "profile": "planner.outline.v6", "system": "System",
               "schema": {"type": "object"}, "allowed_tools": [], "max_output_tokens": 8192}
    return control, recipe


def test_exact_scoped_edits_preserve_author_timing_and_all_other_fields():
    control, recipe = fixture()
    original = deepcopy(control)
    treatment = {**control, "prompt": experiment.transform_prompt(control["prompt"], recipe)}
    actual, expected = json.loads(treatment["prompt"]), json.loads(control["prompt"])
    expected["book_concept"]["first_arc"]["middle"] = "The repair begins. It costs three coins."
    expected["book_concept"]["first_arc"]["closes"] = "The job is settled. The debt remains unpaid."
    for debt in expected["book_concept"]["debts"]:
        debt["due_scene"] = None
    assert actual == expected
    assert control == original
    assert experiment.request_control(control, treatment, original, {"2": recipe})


@pytest.mark.parametrize("fault", ["source", "field", "missing", "duplicate", "empty", "due"])
def test_transform_refuses_unregistered_input_or_edits(fault):
    control, recipe = fixture()
    if fault == "source":
        control["prompt"] += " "
    elif fault == "field":
        recipe["edits"][0]["field"] = "author_brief"
    elif fault == "missing":
        recipe["edits"][0]["before"] = "Absent source text"
    elif fault == "duplicate":
        recipe["edits"][0]["before"] = "e"
    elif fault == "empty":
        recipe["edits"][0]["before"] = ""
    elif fault == "due":
        recipe["due_scenes"][0] = 2
    with pytest.raises(ValueError):
        experiment.transform_prompt(control["prompt"], recipe)


@pytest.mark.parametrize("fault", ["author", "world", "layout", "rule", "schema", "profile",
                                   "owed", "original", "no_recipe", "duplicate_recipe"])
def test_pair_control_rejects_unregistered_differences(fault):
    control, recipe = fixture()
    original = deepcopy(control)
    treatment = {**control, "prompt": experiment.transform_prompt(control["prompt"], recipe)}
    payload = json.loads(treatment["prompt"])
    recipes = {"2": recipe}
    if fault == "author":
        payload["book_concept"]["author_brief"] = "Different author deadline"
    elif fault == "world":
        payload["world"]["quantity"] = 4
    elif fault == "layout":
        payload["writing_layout"]["target_scene_words"] = 2800
    elif fault == "rule":
        payload["rules"].append("Finish faster.")
    elif fault == "owed":
        payload["book_concept"]["debts"][0]["owed"] = "Different event"
    elif fault in {"schema", "profile"}:
        treatment[fault] = "different"
    elif fault == "original":
        original["system"] = "Different system"
    elif fault == "no_recipe":
        recipes = {}
    elif fault == "duplicate_recipe":
        recipes["4"] = recipe
    treatment["prompt"] = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)
    with pytest.raises(ValueError):
        experiment.request_control(control, treatment, original, recipes)


def test_transform_runs_at_application_boundary_only_in_treatment(monkeypatch):
    control, recipe = fixture()
    request = CompletionRequest(prompt=control["prompt"], system="System",
                                profile="planner.outline.v6", allowed_tools=())
    def original(*args, **kwargs):
        return request

    monkeypatch.setattr(outline, "render_outline_request", original)
    monkeypatch.setattr(experiment.base, "read", lambda path: {"2": recipe})
    experiment.install_transform("A2")
    assert outline.render_outline_request is original
    experiment.install_transform("B2")
    received = outline.render_outline_request()
    assert received.prompt == experiment.transform_prompt(request.prompt, recipe)
    assert replace(received, prompt=request.prompt) == request


def test_unregistered_books_refuse_transform():
    with pytest.raises(ValueError):
        experiment.install_transform("B3")
