"""Containment of reconciled source and replacement plans in the isolated diagnostic."""

import copy
import runpy
from pathlib import Path

import pytest

TRIAL = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "research/quality-measurement/prose_actions.py")
)
BASE = {
    "system": "Rules.",
    "prompt": (
        "Private facts.\nOrdered actions:\n- Read notice.\n- Shut gate.\nEnding state:\nGate shut."
    ),
}


def proposal():
    return {
        "objective": "Secure the enclosure.",
        "conflicts": [],
        "steps": [
            {
                "id": "s1",
                "source_actions": ["a1", "a2"],
                "intention": "Secure it.",
                "action": "Read, then close the gate.",
                "response": "Latch engages.",
                "consequence": "",
            }
        ],
    }


def test_action_plan_replaces_only_action_section_and_keeps_source_unchanged():
    before = copy.deepcopy(BASE)
    rendered = TRIAL["render"](BASE, proposal())
    assert before == BASE
    assert rendered["system"] == BASE["system"]
    assert rendered["prompt"].startswith("Private facts.\nAction plan:\n")
    assert rendered["prompt"].endswith("\nEnding state:\nGate shut.")
    assert "Ordered actions" not in rendered["prompt"]
    assert "source_actions" not in rendered["prompt"]


def test_action_plan_can_use_a_frozen_outcome_contract_instead_of_old_intermediate_beats():
    plan = proposal()
    plan["steps"][0]["source_actions"] = ["a1"]
    outcomes = [{"id": "a1", "text": "End at the closed gate."}]
    rendered = TRIAL["render"](BASE, plan, outcomes)
    assert rendered["prompt"].endswith("\nEnding state:\nGate shut.")
    with pytest.raises(ValueError, match="missing or reordered"):
        TRIAL["render"](BASE, plan)


@pytest.mark.parametrize("damage", ["missing", "reordered", "unknown", "conflict"])
def test_action_plan_refuses_lost_requirements_or_unresolved_conflicts(damage):
    plan = proposal()
    if damage == "conflict":
        plan["conflicts"] = ["Gate must remain open."]
    else:
        plan["steps"][0]["source_actions"] = {
            "missing": ["a1"],
            "reordered": ["a2", "a1"],
            "unknown": ["a1", "a2", "a3"],
        }[damage]
    with pytest.raises(ValueError):
        TRIAL["render"](BASE, plan)


def test_source_amendment_refuses_stale_match_and_does_not_change_original():
    amendment = {
        "edits": [
            {
                "field": "system",
                "old": "Rules.",
                "new": "Reconciled rules.",
                "count": 1,
                "reason": "Resolve source ambiguity.",
            }
        ],
        "clarifications": "Initial equipment is already owned.",
        "rationale": "Test fixture only.",
    }
    result = TRIAL["reconcile"](BASE, amendment)
    assert BASE["system"] == "Rules."
    assert result["system"].startswith("Reconciled rules.")
    amendment["edits"][0]["count"] = 2
    with pytest.raises(ValueError, match="occurrence"):
        TRIAL["reconcile"](BASE, amendment)


def test_action_quota_includes_separate_reasoning_without_double_counting_cached_input(tmp_path):
    (tmp_path / "planner").mkdir()
    path = tmp_path / "planner/full-1.result.json"
    TRIAL["write_new"](
        path,
        {
            "status": "completed",
            "usage": {
                "input_tokens": 60000,
                "cached_input_tokens": 50000,
                "output_tokens": 50000,
                "reasoning_output_tokens": 9999,
            },
        },
    )
    TRIAL["quota"](tmp_path)
    result = TRIAL["read"](path)
    result["usage"]["reasoning_output_tokens"] += 1
    path.write_text(__import__("json").dumps(result), encoding="utf-8")
    with pytest.raises(RuntimeError, match="token stop"):
        TRIAL["quota"](tmp_path)
