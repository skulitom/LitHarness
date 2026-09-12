"""Protect the active-seed contrast and its content-independent expansion lineage."""

import dataclasses
import importlib.util
import random
from pathlib import Path

import pytest

from litharness.application import discovery
from litharness.domain.generation import CompletionRequest

PATH = (
    Path(__file__).resolve().parents[1]
    / "research/quality-measurement/invention-active-seed-20260912/run.py"
)
SPEC = importlib.util.spec_from_file_location("invention_active_seed_experiment", PATH)
assert SPEC is not None and SPEC.loader is not None
experiment = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(experiment)


def test_active_differs_from_diversity_control_only_in_registered_seed_use_sentence():
    requests = {a: experiment.invention_request(a, "OPAQUE_PREFIX", CompletionRequest)
                for a in experiment.ARMS}
    assert requests["passive"].system == experiment.parent.parent.system_text(
        "OPAQUE_PREFIX", "batch"
    )
    active, diverse = requests["active"], requests["diverse"]
    assert dataclasses.replace(active, system=active.system.replace(
        experiment.SEED_USE, experiment.TASK_USE
    )) == diverse
    assert all(r.system.startswith("OPAQUE_PREFIX\n\n") for r in requests.values())
    assert all(r.schema == experiment.parent.parent.SCHEMA for r in requests.values())
    assert all(dataclasses.replace(r, system="") == dataclasses.replace(active, system="")
               for r in requests.values())
    with pytest.raises(ValueError):
        experiment.invention_request("unknown", "OPAQUE_PREFIX", CompletionRequest)


def test_seed_swap_changes_only_the_prefix_and_repeats_preserve_request_bytes():
    for arm in experiment.ARMS:
        first = experiment.invention_request(arm, "FIRST_PREFIX", CompletionRequest)
        second = experiment.invention_request(arm, "SECOND_PREFIX", CompletionRequest)
        assert dataclasses.replace(first, system=first.system.replace(
            "FIRST_PREFIX", "SECOND_PREFIX", 1
        )) == second
        assert experiment.invention_request(arm, "FIRST_PREFIX", CompletionRequest) == first


def test_expansion_gets_only_the_preselected_premise_and_unchanged_discovery():
    premise = "EXACT_SOURCE_STORY"
    result = experiment.expansion_request(premise, discovery)
    assert result == discovery.render_request(premise, person="third")
    assert experiment.SEED_USE not in result.system + result.prompt
    assert experiment.DIVERSITY not in result.system + result.prompt


def test_selection_is_independent_and_only_first_repeat_is_scheduled_for_expansion():
    state = random.getstate()
    assert experiment.selected_index("12345") == random.Random(
        "invention-active-seed.v1:12345"
    ).randrange(6)
    assert random.getstate() == state
    assert len(experiment.ORDER) == len(set(experiment.ORDER)) == 12
    assert {n.removeprefix("expand-") for n in experiment.EXPANSIONS} == set(experiment.ORDER[:6])
    for block in ("1", "2"):
        orders = [[n.split("-")[0] for n in experiment.ORDER if n.endswith(f"-{block}-{r}")]
                  for r in (1, 2)]
        assert sorted(orders[0]) == sorted(experiment.ARMS)
        assert orders[1] == orders[0][::-1]


def test_transport_control_detects_schema_instruction_and_extra_text_drift():
    request = experiment.invention_request("active", "OPAQUE_PREFIX", CompletionRequest)
    fields = {"transport.system": request.effective_system, "transport.prompt": request.prompt}
    assert all(experiment.transport_text_checks(request, fields).values())
    for wrong in (request.system, request.effective_system + "\nEXTRA_INSTRUCTION"):
        assert not experiment.transport_text_checks(request, {
            **fields, "transport.system": wrong,
        })["effective_system_equal"]
    assert not experiment.transport_text_checks(request, {
        **fields, "transport.prompt": "WRONG_TASK",
    })["prompt_equal"]
