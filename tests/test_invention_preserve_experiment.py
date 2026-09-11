"""Protect the ablation's prompt boundary and its reversed-order repeats."""

import importlib.util
from collections import Counter
from itertools import combinations
from pathlib import Path

import pytest

from litharness.application import discovery

PATH = (
    Path(__file__).resolve().parents[1]
    / "research/quality-measurement/invention-preserve-20260911/run.py"
)
SPEC = importlib.util.spec_from_file_location("invention_preserve_experiment", PATH)
assert SPEC is not None and SPEC.loader is not None
experiment = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(experiment)


def test_preservation_ablation_keeps_premise_and_excludes_history():
    premise = "SELECTED_PREMISE_MARKER"
    history = ["HISTORY_BOUNDARY_MARKER"]
    clean = experiment.expansion_request("clean", premise, history, discovery)
    preserve = experiment.expansion_request("preserve", premise, history, discovery)
    combined = experiment.expansion_request("combined", premise, history, discovery)
    assert clean == discovery.render_request(premise, person="third")
    assert preserve.prompt == experiment.PRESERVE + "\n\n" + clean.prompt
    assert history[0] not in preserve.prompt and history[0] not in preserve.system
    assert history[0] in combined.prompt
    assert combined == experiment.parent.expansion_request(
        "retain-structure-1", premise, history, discovery
    )
    assert clean.system == preserve.system == combined.system
    assert clean.schema == preserve.schema == combined.schema
    with pytest.raises(ValueError):
        experiment.expansion_request("unregistered", premise, history, discovery)


def test_each_premise_repeats_every_arm_with_pairwise_precedence_reversed():
    slots = [name.split("-") for name in experiment.ORDER]
    assert len(slots) == len(set(experiment.ORDER)) == 12
    assert Counter((a, p) for a, p, _ in slots) == {
        (arm, premise): 2 for arm in ("clean", "preserve", "combined") for premise in ("1", "2")
    }
    for premise in ("1", "2"):
        first = [a for a, p, r in slots if (p, r) == (premise, "1")]
        second = [a for a, p, r in slots if (p, r) == (premise, "2")]
        for a, b in combinations(first, 2):
            assert second.index(a) > second.index(b)
