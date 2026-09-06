"""The crossed input exposure must not leak a plan or background into a free compact cell."""

import runpy
from pathlib import Path

import pytest

TRIAL = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "research/quality-measurement/prose_scene_brief.py")
)


def source():
    return {
        "system": "Write a scene.",
        "scene": "Free the trapped worker.",
        "background": "reference " * 600,
    }


def test_scene_brief_crosses_exposures_without_leaking_or_changing_core():
    s, p = source(), {"steps": ["Lift the gate."], "conflicts": []}
    r = TRIAL["compose"](s, p)
    assert r["free"]["focused"] == {"system": s["system"], "prompt": s["scene"]}
    for mode in ("free", "planned"):
        for condition in ("full", "focused"):
            cell = r[mode][condition]
            assert cell["system"] == s["system"]
            assert cell["prompt"].startswith(s["scene"])
            assert (s["background"] in cell["prompt"]) == (condition == "full")
            assert ("Lift the gate." in cell["prompt"]) == (mode == "planned")
    assert (
        r["planned"]["full"]["prompt"].split("Follow this action plan:\n")[1]
        == r["planned"]["focused"]["prompt"].split("Follow this action plan:\n")[1]
    )


@pytest.mark.parametrize("damage", ["large_core", "empty_background", "conflict", "empty_step"])
def test_scene_brief_rejects_failed_manipulation_or_unresolved_plan(damage):
    s, p = source(), {"steps": ["Lift the gate."], "conflicts": []}
    if damage == "large_core":
        s["scene"] = "word " * 450
    elif damage == "empty_background":
        s["background"] = ""
    elif damage == "conflict":
        p["conflicts"] = ["The gate cannot move."]
    else:
        p["steps"] = [""]
    with pytest.raises(ValueError):
        TRIAL["compose"](s, p)


def test_scene_brief_quota_counts_planning_and_both_drafting_modes(tmp_path):
    for mode in ("planner", "free", "planned"):
        (tmp_path / mode).mkdir()
        TRIAL["write_new"](
            tmp_path / mode / "full-1.result.json",
            {
                "status": "completed",
                "usage": {
                    "input_tokens": 23000,
                    "output_tokens": 1000,
                    "reasoning_output_tokens": 1000,
                },
            },
        )
    with pytest.raises(RuntimeError, match="token stop"):
        TRIAL["quota"](tmp_path)
