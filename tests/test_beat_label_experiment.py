"""The smaller follow-up changes only role labels and cannot dispatch world growth."""

from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import pytest

PATH = Path(__file__).parents[1] / "research/quality-measurement/beat-labels-20260915/run.py"
spec = importlib.util.spec_from_file_location("beat_label_experiment_test", PATH)
experiment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(experiment)


def requests():
    prompt = {
        "scenes": [{"ordinal": i, "chapter": i, "dramatic_function": role}
                   for i, role in enumerate(experiment.ROLES, 1)],
        "rules": ["Existing rule", experiment.ROLE_RULE],
        "book_concept": {"author_brief": "Author requires setup in chapter one."},
        "world": {"rule": "Original rule"}, "writing_layout": {"target_scene_words": 1400},
    }
    control = {"prompt": json.dumps(prompt), "system": "SYSTEM", "profile": "planner.outline.v5",
               "schema": {"type": "object"}, "max_output_tokens": 8192, "allowed_tools": []}
    for scene in prompt["scenes"]:
        del scene["dramatic_function"]
    prompt["rules"].remove(experiment.ROLE_RULE)
    treatment = {**control, "prompt": json.dumps(prompt), "profile": "planner.outline.v6"}
    return control, treatment


@pytest.mark.parametrize("fault", [None, "world", "author", "chapter", "budget", "schema",
                                   "rule", "role", "original"])
def test_only_role_labels_their_instruction_and_profile_can_change(fault):
    control, treatment = requests()
    original = deepcopy(control)
    prompt = json.loads(treatment["prompt"])
    if fault == "world":
        prompt["world"]["rule"] = "Different rule"
    elif fault == "author":
        prompt["book_concept"]["author_brief"] = "Changed author instruction"
    elif fault == "chapter":
        prompt["scenes"][0]["chapter"] = 2
    elif fault == "budget":
        treatment["max_output_tokens"] = 16384
    elif fault == "schema":
        treatment["schema"] = {"type": "array"}
    elif fault == "rule":
        prompt["rules"].append(experiment.ROLE_RULE)
    elif fault == "role":
        prompt["scenes"][0]["dramatic_function"] = "setup"
    elif fault == "original":
        original["system"] = "OTHER_SYSTEM"
    treatment["prompt"] = json.dumps(prompt)
    if fault is None:
        assert experiment.request_control(control, treatment, original)
    else:
        with pytest.raises(ValueError):
            experiment.request_control(control, treatment, original)


@pytest.mark.parametrize("phase", ["grow1", "chapter2", "concept", "seed", "accept-grow1"])
def test_unregistered_phases_cannot_make_a_command(phase):
    with pytest.raises(ValueError):
        experiment.command("A2", phase)


def test_only_the_opening_and_its_queued_work_are_scheduled():
    assert experiment.PHASES == ("chapter1", "drain1")
    assert experiment.command("A2", "chapter1") == ["tick"]
    assert experiment.command("B4", "drain1") == ["tick"]
    assert experiment.order("chapter1") == ("A2", "B2", "B4", "A4")
    assert experiment.order("drain1") == ("B2", "A2", "A4", "B4")


@pytest.mark.parametrize("fault", [None, "no_chapter", "second_chapter", "pending", "terminal",
                                   "stopped", "global_stop"])
def test_completion_requires_exactly_one_chapter_and_drained_success(fault):
    state = {"status": "partial", "books": {"A2": {
        "status": "running", "accepted": 1, "pending": 0, "terminal": 0,
    }}}
    item = state["books"]["A2"]
    if fault == "no_chapter":
        item["accepted"] = 0
    elif fault == "second_chapter":
        item["accepted"] = 2
    elif fault in {"pending", "terminal"}:
        item[fault] = 1
    elif fault == "stopped":
        item["status"] = "stopped"
    elif fault == "global_stop":
        state["stop"] = "provider failure"
    assert experiment.finalize(state)["status"] == ("complete" if fault is None else "partial")
