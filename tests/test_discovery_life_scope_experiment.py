"""Keep the single-sentence ablation isolated from source, schema and later writing."""

import dataclasses
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from litharness.application import discovery
from litharness.domain.generation import CompletionRequest

PATH = (
    Path(__file__).resolve().parents[1]
    / "research/quality-measurement/discovery-life-scope-20260912/run.py"
)
SPEC = importlib.util.spec_from_file_location("discovery_life_scope_experiment", PATH)
assert SPEC is not None and SPEC.loader is not None
experiment = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(experiment)


def renderer(system: str):
    def render_request(source, *, person):
        return CompletionRequest(
            system=system, prompt=f"Source: {source}\nPerson: {person}",
            schema=discovery.SCHEMA, profile="FROZEN_PROFILE", max_output_tokens=2400,
        )
    return SimpleNamespace(render_request=render_request)


def test_only_the_registered_sentence_changes_across_all_three_arms():
    module = renderer("Before. " + experiment.ORIGINAL + "After.")
    calls = {a: experiment.plan_request(a, "EXACT_SOURCE", module) for a in experiment.ARMS}
    full = calls["full"]
    assert full == module.render_request("EXACT_SOURCE", person="third")
    assert calls["omit"].system == "Before. After."
    assert calls["scoped"].system == "Before. " + experiment.SCOPED + "After."
    for request in calls.values():
        assert dataclasses.replace(request, system="") == dataclasses.replace(full, system="")
        assert request == experiment.plan_request(
            next(a for a, r in calls.items() if r == request), "EXACT_SOURCE", module
        )


def test_missing_duplicate_or_unknown_sentence_target_refuses_silent_drift():
    for system in ("CHANGED TASK", experiment.ORIGINAL * 2):
        for arm in experiment.ARMS:
            with pytest.raises(ValueError, match="exactly one"):
                experiment.plan_request(arm, "SOURCE", renderer(system))
    with pytest.raises(ValueError, match="Unknown arm"):
        experiment.plan_request("unknown", "SOURCE", renderer(experiment.ORIGINAL))


def test_source_change_changes_only_the_user_prompt():
    module = renderer(experiment.ORIGINAL)
    for arm in experiment.ARMS:
        first = experiment.plan_request(arm, "FIRST_SOURCE", module)
        second = experiment.plan_request(arm, "SECOND_SOURCE", module)
        assert dataclasses.replace(first, prompt=first.prompt.replace(
            "FIRST_SOURCE", "SECOND_SOURCE"
        )) == second


def test_draft_receives_exact_plan_without_any_ablation_wording_or_prior_source():
    payload = {"world": "WORLD", "opening": "OPENING", "growth": "GROWTH"}
    request = experiment.draft_request(payload, discovery, CompletionRequest)
    assert request == experiment.parent.dependent_request(
        "draft", payload, discovery, CompletionRequest
    )
    assert json.loads(request.prompt.removeprefix("Story proposal:\n")) == payload
    assert experiment.ORIGINAL not in request.system
    assert experiment.SCOPED not in request.system


def test_schedule_reverses_arm_order_and_drafting_is_fixed_before_outputs():
    assert len(experiment.ORDER) == len(set(experiment.ORDER)) == 12
    for source in ("1", "2"):
        first = [n.split("-")[0] for n in experiment.ORDER if n.endswith(f"-{source}-1")]
        second = [n.split("-")[0] for n in experiment.ORDER if n.endswith(f"-{source}-2")]
        assert sorted(first) == sorted(experiment.ARMS)
        assert second == first[::-1]
    assert {n.removeprefix("draft-") for n in experiment.DRAFTS} == {
        f"{arm}-{source}-1" for arm in ("full", "scoped") for source in ("1", "2")
    }
    assert experiment.SOURCES == {"1": "adapt-late-1-1", "2": "adapt-late-2-1"}
