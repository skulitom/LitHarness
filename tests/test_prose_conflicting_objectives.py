"""Check that a motivational comparison preserves the common writer burden."""

import copy
import json
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TRIAL = runpy.run_path(str(ROOT / "research/quality-measurement/prose_conflicting_objectives.py"))
FIXTURE = runpy.run_path(str(ROOT / "tests/test_prose_narration_obligations.py"))


def source():
    return {
        "chapter_source": FIXTURE["source"](),
        "interaction": {
            "scope": ["F1a"],
            "shared": "Same action constraints.",
            "objectives": {"full": "Wants to proceed.", "focused": "Wants to remain."},
        },
    }


def test_objective_comparison_changes_only_one_assignment_and_preserves_all_obligations():
    s = source()
    before = copy.deepcopy(s)
    requests = TRIAL["compose"](s)
    left, right = (json.loads(requests[c]["prompt"].split("\n", 1)[1]) for c in ("full", "focused"))
    assert left["local_interaction"].pop("objective") == "Wants to proceed."
    assert right["local_interaction"].pop("objective") == "Wants to remain."
    assert left == right
    assert left["source_units"] == s["chapter_source"]["facts"]
    assert left["required_narration"] == ["F1a", "F1b"]
    assert left["literal_sequence"] == ["ONE.", "ONE."]
    assert requests["full"]["system"] == requests["focused"]["system"]
    assert all("Incidental original wording" not in r["prompt"] for r in requests.values())
    assert s == before


@pytest.mark.parametrize("scope", [[], ["missing"], ["F1a", "F1a"]])
def test_objective_comparison_refuses_invalid_scope(scope):
    s = source()
    s["interaction"]["scope"] = scope
    with pytest.raises(ValueError, match=r"scope|assignment"):
        TRIAL["compose"](s)


def test_objective_comparison_refuses_missing_or_duplicate_conditions():
    for objectives in ({"full": "One"}, {"full": "One", "focused": "One"}):
        s = source()
        s["interaction"]["objectives"] = objectives
        with pytest.raises(ValueError, match="assignment"):
            TRIAL["compose"](s)
