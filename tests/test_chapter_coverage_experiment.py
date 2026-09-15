"""Offline containment for a comparison that reuses recorded generated worlds."""

from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import pytest

from litharness.application.chapter_layout import PLANNING_RULE
from litharness.application.outline import CHAPTER_OUTLINE_SCHEMA, CONCEPT_OUTLINE_SCHEMA

PATH = (Path(__file__).parents[1]
        / "research/quality-measurement/chapter-coverage-20260915/run.py")
spec = importlib.util.spec_from_file_location("coverage_experiment_test", PATH)
experiment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(experiment)


def requests():
    payload = {"scenes": [{"ordinal": i, "chapter": i} for i in range(1, 7)],
               "world": {"rules": ["An original rule."]}, "rules": ["Existing rule."],
               "book_concept": {"author_brief": "AUTHOR_MARKER"}}
    control = {"prompt": json.dumps(payload), "system": "PLANNER_SYSTEM",
               "schema": CONCEPT_OUTLINE_SCHEMA, "profile": "planner.outline.v4",
               "max_output_tokens": 8192, "allowed_tools": []}
    updated = deepcopy(payload)
    updated["writing_layout"] = {"chapters": [
        {"chapter": i, "scene_ordinals": [i], "target_words": 1400} for i in range(1, 7)
    ], "target_scene_words": 1400}
    updated["rules"].append(PLANNING_RULE)
    treatment = {**control, "prompt": json.dumps(updated), "schema": CHAPTER_OUTLINE_SCHEMA,
                 "profile": "planner.outline.v5"}
    return control, treatment


@pytest.mark.parametrize("fault", [None, "world", "original", "author", "budget", "schema", "rule"])
def test_frozen_input_control_accepts_only_the_registered_handoff_difference(fault):
    control, treatment = requests()
    original = deepcopy(control)
    payload = json.loads(treatment["prompt"])
    if fault == "world":
        payload["world"]["rules"] = ["Different world"]
    elif fault == "author":
        payload["book_concept"]["author_brief"] = "Different author"
    elif fault == "rule":
        payload["rules"].remove(PLANNING_RULE)
    elif fault == "original":
        original["system"] = "Different original"
    elif fault == "budget":
        treatment["max_output_tokens"] = 16384
    elif fault == "schema":
        treatment["schema"] = {**CHAPTER_OUTLINE_SCHEMA, "required": []}
    treatment["prompt"] = json.dumps(payload)
    if fault is None:
        assert experiment.request_control(control, treatment, original, PLANNING_RULE)
    else:
        with pytest.raises(ValueError):
            experiment.request_control(control, treatment, original, PLANNING_RULE)


def recorded(rows):
    return {"request": {"allowed_tools": [
        "Bash(litharness world declare-batch:*)", "Bash(litharness world summary)",
    ]},
            "result": {"raw": {"commands_jsonl": "\n".join(json.dumps(row) for row in rows)}}}


def test_replay_keeps_successful_declarations_and_excludes_nonexecuted_and_readonly_calls():
    arguments = ["world", "declare-batch", "--records", "[]"]
    rows = [
        {"phase": "result", "arguments": {"invalid_tool_request": "x"}, "argv": None},
        {"phase": "result", "arguments": ["world", "summary"], "argv": ["python"],
         "returncode": 0},
        {"phase": "result", "arguments": arguments, "argv": ["python"], "returncode": 0},
    ]
    assert experiment.replay_commands(recorded(rows)) == [arguments]
    rows[-1]["returncode"] = 1
    with pytest.raises(RuntimeError, match="failed declaration"):
        experiment.replay_commands(recorded(rows))


@pytest.mark.parametrize("arguments", [["world", "accept"], ["concept"], ["world", "seed"]])
def test_replay_cannot_invent_unrecorded_mutations_or_call_a_generator(arguments):
    with pytest.raises((ValueError, RuntimeError)):
        experiment.replay_commands(recorded([{
            "phase": "result", "arguments": arguments, "argv": ["python"], "returncode": 0,
        }]))


def test_world_growth_uses_a_logical_scene_id_and_order_is_counterbalanced():
    assert experiment.command("A2", "grow1") == ["architect", "grow", "--scene", "scene-1"]
    assert experiment.order("chapter1") == ("A2", "B2", "B4", "A4")
    assert experiment.order("drain1") == ("B2", "A2", "A4", "B4")
