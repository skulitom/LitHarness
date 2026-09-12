"""Protect the genre-cue contrast and content-independent, single-source story chains."""

import dataclasses
import importlib.util
import json
import random
from pathlib import Path

import pytest

from litharness.application import discovery
from litharness.domain.generation import CompletionRequest

PATH = (
    Path(__file__).resolve().parents[1]
    / "research/quality-measurement/invention-genre-deferral-20260912/run.py"
)
SPEC = importlib.util.spec_from_file_location("invention_genre_deferral_experiment", PATH)
assert SPEC is not None and SPEC.loader is not None
experiment = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(experiment)


def test_genre_cue_is_the_only_between_arm_request_difference():
    early = experiment.invention_request("early", "OPAQUE_PREFIX", CompletionRequest)
    late = experiment.invention_request("late", "OPAQUE_PREFIX", CompletionRequest)
    assert dataclasses.replace(early, system=early.system.replace(
        experiment.EARLY, experiment.LATE
    )) == late
    assert late.system == "OPAQUE_PREFIX\n\n" + experiment.LATE + "\n\n" + experiment.TASK
    with pytest.raises(ValueError):
        experiment.invention_request("unknown", "OPAQUE_PREFIX", CompletionRequest)
    for arm in experiment.ARMS:
        first = experiment.invention_request(arm, "ONE", CompletionRequest)
        assert first == experiment.invention_request(arm, "ONE", CompletionRequest)
        assert dataclasses.replace(first, system=first.system.replace("ONE", "TWO", 1)) == (
            experiment.invention_request(arm, "TWO", CompletionRequest)
        )


def test_each_stage_receives_only_its_exact_immediate_source():
    batch = {"result": {"parsed": {"premises": [f"SOURCE_{i}" for i in range(6)]}}}
    source = experiment.source_for("adapt", batch, 4)
    adapt = experiment.dependent_request("adapt", source, discovery, CompletionRequest)
    assert adapt.prompt == "Story premise:\nSOURCE_4"
    assert "SOURCE_0" not in adapt.effective_system + adapt.prompt
    adapted = {"result": {"parsed": {"story": "ADAPTED_SOURCE"}}}
    source = experiment.source_for("plan", adapted, 4)
    assert experiment.dependent_request("plan", source, discovery, CompletionRequest) == (
        discovery.render_request("ADAPTED_SOURCE", person="third")
    )
    plan = {"world": "WORLD", "opening": "OPENING", "growth": "GROWTH"}
    draft = experiment.dependent_request("draft", plan, discovery, CompletionRequest)
    assert json.loads(draft.prompt.removeprefix("Story proposal:\n")) == plan
    assert "SOURCE_4" not in draft.effective_system + draft.prompt
    assert "ADAPTED_SOURCE" not in draft.effective_system + draft.prompt
    assert draft.schema == adapt.schema == experiment.TEXT_SCHEMA
    with pytest.raises(ValueError):
        experiment.dependent_request("unknown", source, discovery, CompletionRequest)


def test_invalid_or_augmented_source_is_not_silently_substituted():
    for bad in ({}, {"story": ""}, {"story": 5}, {"story": "TEXT", "rating": 1}):
        with pytest.raises(ValueError):
            experiment.parse_story(bad)
    with pytest.raises(ValueError):
        experiment.source_for("adapt", {"result": {"parsed": {"premises": ["SHORT"]}}}, 0)
    with pytest.raises(TypeError):
        experiment.dependent_request("adapt", {"story": "TEXT"}, discovery, CompletionRequest)
    with pytest.raises(TypeError):
        experiment.dependent_request("plan", {"story": "TEXT"}, discovery, CompletionRequest)


def test_selection_and_schedule_do_not_depend_on_output_contents():
    state = random.getstate()
    assert experiment.selected_index("12345") == random.Random(
        "invention-genre-deferral.v1:12345"
    ).randrange(6)
    assert random.getstate() == state
    assert len(experiment.ORDER) == len(set(experiment.ORDER)) == 8
    assert tuple(reversed(experiment.ORDER[:4])) == experiment.CHAINS
    assert experiment.STAGES == ("adapt", "plan", "draft")
    for block in ("1", "2"):
        orders = [[n.split("-")[0] for n in experiment.ORDER if n.endswith(f"-{block}-{r}")]
                  for r in (1, 2)]
        assert sorted(orders[0]) == sorted(experiment.ARMS)
        assert orders[1] == orders[0][::-1]
