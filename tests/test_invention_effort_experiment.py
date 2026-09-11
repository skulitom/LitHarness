"""Protect the changed effort control and independent selection without provider calls."""

import importlib.util
import random
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

from litharness.domain.generation import CompletionRequest

PATH = (
    Path(__file__).resolve().parents[1]
    / "research/quality-measurement/invention-effort-20260911/run.py"
)
SPEC = importlib.util.spec_from_file_location("invention_effort_experiment", PATH)
assert SPEC is not None and SPEC.loader is not None
experiment = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(experiment)


def test_low_premises_expand_at_medium_without_changing_selection():
    state = random.getstate()
    number = "123456789"
    index = experiment.selected_index(number)
    assert index == random.Random("invention-effort.v1:" + number).randrange(6)
    assert random.getstate() == state
    for name in experiment.ORDER:
        assert experiment.effort_for(name) == name.split("-")[0]
        assert experiment.effort_for("expand-" + name) == "medium"
    with pytest.raises(ValueError):
        experiment.effort_for("expand-low-unknown")


def test_effort_audit_removes_only_effort_and_preserves_input_checks(monkeypatch):
    monkeypatch.setitem(sys.modules, "run", experiment)
    monkeypatch.setattr(sys, "path", sys.path.copy())
    spec = importlib.util.spec_from_file_location(
        "invention_effort_audit", PATH.with_name("audit.py")
    )
    assert spec is not None and spec.loader is not None
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    low = {"requested_model": "gpt-6-astra", "settings": {
        "model_reasoning_effort": "low", "project_doc_max_bytes": 0,
    }}
    medium = {**low, "settings": {**low["settings"], "model_reasoning_effort": "medium"}}
    assert audit.without_effort(low) == audit.without_effort(medium)
    assert low["settings"]["model_reasoning_effort"] == "low"
    drift = {**medium, "settings": {**medium["settings"], "project_doc_max_bytes": 1000}}
    assert audit.without_effort(low) != audit.without_effort(drift)
    request = CompletionRequest(prompt="Selected premise")
    saved = {**asdict(request), "allowed_tools": []}
    assert experiment.request_matches(saved, request)
    assert not experiment.request_matches({**saved, "prompt": "Replacement"}, request)
