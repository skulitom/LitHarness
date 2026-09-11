"""Keep generated history inert, selection fixed, and carry-through restricted to its arm."""

import importlib.util
import json
import random
from pathlib import Path

import pytest

from litharness.application import discovery

PATH = (
    Path(__file__).resolve().parents[1]
    / "research/quality-measurement/invention-memory-20260911/run.py"
)
SPEC = importlib.util.spec_from_file_location("invention_memory_experiment", PATH)
assert SPEC is not None and SPEC.loader is not None
experiment = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(experiment)


def test_memory_conditions_keep_same_complete_history_in_original_order():
    history = ['Old premise.\n"quoted"', "Another previous premise."]
    serialized = json.dumps(history, ensure_ascii=False)
    baseline = experiment.generation_prompt("baseline", history)
    identity = experiment.generation_prompt("identity", history)
    structure = experiment.generation_prompt("structure", history)
    assert serialized not in baseline
    assert serialized in identity and serialized in structure
    assert experiment.STRUCTURE not in identity
    assert experiment.STRUCTURE in structure
    assert structure.replace(" " + experiment.STRUCTURE, "") == identity
    with pytest.raises(ValueError):
        experiment.generation_prompt("unregistered", history)


def test_only_retained_expansion_contains_history_and_both_keep_selected_brief():
    history = ["HISTORY_BOUNDARY_MARKER"]
    premise = "SELECTED_PREMISE_BOUNDARY_MARKER"
    original = discovery.render_request(premise, person="third")
    clean = experiment.expansion_request("expand-structure-1", premise, history, discovery)
    carry = experiment.expansion_request("retain-structure-1", premise, history, discovery)
    assert clean == original
    assert carry.system == clean.system
    assert carry.schema == clean.schema
    assert carry.prompt.endswith(clean.prompt)
    assert history[0] not in clean.prompt and history[0] in carry.prompt
    assert history[0] not in carry.system
    assert experiment.CARRY in carry.prompt
    with pytest.raises(ValueError):
        experiment.expansion_request("retain-baseline-1", premise, history, discovery)


def test_history_experiment_selection_is_independent_of_response_content():
    state = random.getstate()
    number = "123456789"
    assert experiment.selected_index(number) == random.Random(
        "invention-memory.v1:" + number
    ).randrange(6)
    assert random.getstate() == state
    assert len(experiment.ORDER) + len(experiment.EXPANSIONS) == 14
    for name in experiment.EXPANSIONS:
        assert name.split("-", 1)[1] in experiment.ORDER
