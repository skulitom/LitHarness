"""The authoring ablation changes only its registered instruction."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def experiment():
    path = Path(__file__).resolve().parents[1] / (
        "research/quality-measurement/past-action-continuity-20260912/run.py"
    )
    spec = importlib.util.spec_from_file_location("past_action_experiment", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_continuity_ablation_preserves_the_entire_source_system():
    module = experiment()
    system = "Source task.\n\nRules and author locks.\n\nMore rules."
    assert module.system_for(system, "control") == system
    changed = module.system_for(system, "treatment")
    assert changed.replace(module.RULE + "\n\n", "", 1) == system
    assert changed.count(module.RULE) == 1
    with pytest.raises(ValueError):
        module.system_for(system, "unknown")


def test_continuity_slots_include_unchanged_repeats_and_secret_boundary():
    module = experiment()
    assert set(module.ORDER) == {
        "actual-control-1", "actual-control-2", "actual-treatment-1",
        "actual-treatment-2", "secret-control-1", "secret-treatment-1",
    }
    assert len(module.ORDER) == 6
    assert "Iona disabled the signal" in module.SECRET
    assert "conceal that fact" in module.SECRET
    assert "Do not make Vey complicit" in module.SECRET
