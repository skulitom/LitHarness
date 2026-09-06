"""Event dependencies may change; source coverage and immediate consequences remain guarded."""

import copy
import runpy
from pathlib import Path

import pytest

TRIAL = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "research/quality-measurement/prose_order.py")
)


def contract():
    return {
        "actions": [
            {"id": "a1", "text": "Notice arrives."},
            {"id": "a2", "text": "Gate opens."},
            {"id": "a3", "text": "Warning sounds."},
        ],
        "common_edges": [["a1", "a2"]],
        "conditions": {"full": [["a3", "a2"]], "focused": [["a2", "a3"]]},
    }


def plan(order):
    return {
        "objective": "Cross the enclosure.",
        "conflicts": [],
        "steps": [
            {
                "id": f"s{i}",
                "source_actions": [ref],
                "intention": "",
                "action": "Act.",
                "response": "",
                "consequence": "",
            }
            for i, ref in enumerate(order, 1)
        ],
    }


def test_order_conditions_allow_only_their_registered_dependency_direction():
    early = plan(["a1", "a2", "a3"])
    late = plan(["a1", "a3", "a2"])
    TRIAL["validate_plan"](early, contract(), "focused")
    TRIAL["validate_plan"](late, contract(), "full")
    for payload, condition in [(early, "full"), (late, "focused")]:
        with pytest.raises(ValueError, match="dependency"):
            TRIAL["validate_plan"](payload, contract(), condition)


@pytest.mark.parametrize("damage", ["cycle", "unknown", "missing", "conflict"])
def test_order_trial_refuses_invalid_contracts_and_unresolved_plans(damage):
    c, p = contract(), plan(["a1", "a2", "a3"])
    if damage == "cycle":
        c["common_edges"].append(["a2", "a1"])
    elif damage == "unknown":
        c["common_edges"].append(["a1", "a4"])
    elif damage == "missing":
        p["steps"].pop()
    else:
        p["conflicts"] = ["Gate must stay shut."]
    with pytest.raises(ValueError):
        TRIAL["validate_plan"](p, c, "focused")


def test_order_render_preserves_all_context_and_common_ending_outside_plan():
    base = {
        "system": "Rules.",
        "prompt": (
            "Private source.\nOrdered actions:\n- Old beat."
            "\nEnding state:\nAll outcomes complete."
        ),
    }
    original = copy.deepcopy(base)
    rendered = TRIAL["render"](base, plan(["a1", "a2", "a3"]), contract(), "focused")
    assert base == original
    assert rendered["system"] == base["system"]
    assert rendered["prompt"].startswith("Private source.\nAction plan:\n")
    assert rendered["prompt"].endswith("\nEnding state:\nAll outcomes complete.")
    assert "Old beat" not in rendered["prompt"]


def test_order_quota_rejects_unknown_usage_and_counts_reasoning(tmp_path):
    (tmp_path / "planner").mkdir()
    path = tmp_path / "planner/full-1.result.json"
    TRIAL["write_new"](
        path,
        {
            "status": "completed",
            "usage": {
                "input_tokens": 70000,
                "cached_input_tokens": 60000,
                "output_tokens": 60000,
                "reasoning_output_tokens": 10000,
            },
        },
    )
    with pytest.raises(RuntimeError, match="token stop"):
        TRIAL["quota"](tmp_path)
    path.write_text('{"status":"completed","usage":{}}', encoding="utf-8")
    with pytest.raises(ValueError, match="quota usage"):
        TRIAL["quota"](tmp_path)
