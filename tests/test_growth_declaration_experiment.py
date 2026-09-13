"""Freeze meaningful controls before making the new Architect calls."""

import copy
import runpy
from dataclasses import replace
from pathlib import Path

import pytest

from litharness.domain import gamesystem as gs

HERE = (Path(__file__).resolve().parents[1]
        / "research/quality-measurement/growth-declarations-20260913")
RUN = runpy.run_path(str(HERE / "run.py"))
AUDIT = runpy.run_path(str(HERE / "audit.py"))


def _requests():
    return ({"prompt": "World source", "system": "Old seed", "profile": "old-seed"},
            {"prompt": "Opposing source", "system": "Old seed", "profile": "old-seed"},
            {"prompt": "Chapter: Conditional thought. End.", "system": "Old grow",
             "profile": "old-grow", "allowed_tools": ["world query"]})


def test_five_cells_preserve_sources_and_change_only_registered_contrasts():
    originals = _requests()
    before = copy.deepcopy(originals)
    inputs = {"before": "Conditional thought.", "after": "Adopted pursuit.", "cap": "Cap source"}
    cells = RUN["transform_requests"](*originals, "Seed v8", "Opposing v8", "Grow v5", inputs)
    assert tuple(cells) == RUN["ORDER"] and originals == before
    assert cells["wren-seed"]["prompt"] == originals[0]["prompt"]
    assert cells["opposing-seed"]["prompt"] == originals[1]["prompt"]
    assert cells["capped-seed"]["prompt"] == originals[0]["prompt"] + "\n\nCap source"
    assert cells["conditional-goal"]["prompt"] == originals[2]["prompt"]
    assert cells["adopted-goal"]["prompt"] == "Chapter: Adopted pursuit. End."
    assert cells["conditional-goal"]["system"] == cells["adopted-goal"]["system"] == "Grow v5"
    assert cells["adopted-goal"]["allowed_tools"] == originals[2]["allowed_tools"]


@pytest.mark.parametrize("source", ["No match", "Conditional thought. Conditional thought."])
def test_missing_or_ambiguous_goal_contrast_is_rejected(source):
    seed, opposing, grow = _requests()
    with pytest.raises(ValueError, match="uniquely located"):
        RUN["transform_requests"](seed, opposing, {**grow, "prompt": source}, "s", "s", "g",
            {"before": "Conditional thought.", "after": "Adopted pursuit.", "cap": "Cap"})


@pytest.mark.parametrize("counts", [(8, 0, 0), (0, 1_600_000, 0), (0, 0, 5400)])
def test_aggregate_caps_stop_before_starting_another_call(counts):
    with pytest.raises(RuntimeError, match="aggregate ceiling"):
        RUN["check_budget"](*counts)
    RUN["check_budget"](7, 1_599_999, 5399)


@pytest.mark.parametrize("limit, successes", [(None, 0), (1, 0), (2, 1), ("open", 2)])
def test_counterfactual_audit_distinguishes_repeatability_from_ownership_and_caps(limit, successes):
    system = gs.SystemDef("issuer", "Issuer", "ranks", "Rank",
        ranks=(gs.Rank("r1", "First"), gs.Rank("r2", "Second"), gs.Rank("r3", "Third")),
        abilities=(gs.Ability("load", "Load", price=(("point", 1),), growth_limit=limit),
                   gs.Ability("point", "Point", per_rung=1)), scale=gs.Scale("Issuer", 1))
    before = replace(system)
    result = AUDIT["investment_control"](system, system.ability("load"))
    assert system == before and result["counterfactual"]
    assert sum(s["direct_execution"] for s in result["steps"]) == successes
    assert all(s["offered"] == s["direct_execution"] for s in result["steps"])
    for index, step in enumerate(result["steps"], 1):
        if step["direct_execution"]:
            assert step["after"] == {"load": 1 + index, "point": 2 - index}
    stock = AUDIT["investment_control"](system, system.ability("point"))
    assert stock["steps"] == [{"offered": False, "direct_execution": False}]
