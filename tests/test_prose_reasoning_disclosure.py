"""Future-source containment and cross-directory quota controls, not literary measures."""

import copy
import json
import runpy
from pathlib import Path

import pytest

TRIAL = runpy.run_path(
    str(
        Path(__file__).resolve().parents[1]
        / "research/quality-measurement/prose_reasoning_disclosure.py"
    )
)


def source():
    facts = [
        {"id": f"F{i}", "paragraphs": [i], "text": word}
        for i, word in enumerate(["DOOR_ONLY", "FUTURE_BELL", "FUTURE_LETTER"], 1)
    ]
    return {
        "original": {
            "text": "ONE.\n\nTWO.\n\nTHREE.",
            "protected": facts,
            "verbatim": ["ONE.", "TWO.", "THREE."],
            "notes": "FUTURE_ORIGINAL_NOTE",
        },
        "reasoning_request": {"system": "Rules.", "prompt": "FUTURE_ORIGINAL_PROSE"},
        "parts": [
            {
                "facts": [{"id": f["id"], "text": f["text"]}],
                "literals": [literal],
                "notes": "Local uncertainty.",
                "break_after": i == 2,
            }
            for i, (f, literal) in enumerate(zip(facts, ["ONE.", "TWO.", "THREE."], strict=True), 1)
        ],
    }


def test_disclosure_future_is_only_in_control_until_released():
    s = source()
    staged = TRIAL["disclosure_request"](s, "focused", 1, "")
    ahead = TRIAL["disclosure_request"](s, "full", 1, "")
    assert ahead["system"] == staged["system"]
    assert ahead["prompt"].startswith(staged["prompt"] + "\n\nLater source")
    assert "DOOR_ONLY" in staged["prompt"]
    assert all(x not in staged["prompt"] for x in ["FUTURE_BELL", "FUTURE_LETTER", "THREE."])
    assert all(x not in ahead["prompt"] for x in ["FUTURE_ORIGINAL_NOTE", "FUTURE_ORIGINAL_PROSE"])
    assert "FUTURE_LETTER" in ahead["prompt"]
    second = TRIAL["disclosure_request"](s, "focused", 2, "Own earlier prose.")
    assert "FUTURE_BELL" in second["prompt"] and "FUTURE_LETTER" not in second["prompt"]
    payload = json.loads(second["prompt"].split("\n", 1)[1])
    assert payload["previous_prose"] == "Own earlier prose."
    assert payload["write_now"] == ["F2"] and payload["scene_division_after_installment"]
    assert TRIAL["disclosure_request"](s, "full", 3, "Same prefix.") == TRIAL["disclosure_request"](
        s, "focused", 3, "Same prefix."
    )


@pytest.mark.parametrize("damage", ["lost_fact", "duplicate_fact", "literal", "order", "prefix"])
def test_disclosure_refuses_missing_coverage_reordered_literals_and_wrong_prefix(damage):
    s = copy.deepcopy(source())
    if damage == "lost_fact":
        s["parts"][1]["facts"] = []
    elif damage == "duplicate_fact":
        s["parts"][1]["facts"] = s["parts"][0]["facts"]
    elif damage == "literal":
        s["parts"][1]["literals"] = []
    elif damage == "order":
        s["parts"].reverse()
    with pytest.raises(ValueError):
        TRIAL["disclosure_request"](s, "focused", 1, "Existing prose" if damage == "prefix" else "")


def test_disclosure_quota_counts_both_arms_and_separate_reasoning(tmp_path):
    for arm in ["reasoning", "disclosure"]:
        p = tmp_path / "calls" / arm / "cell"
        p.mkdir(parents=True)
        (p / "full-1.result.json").write_text(
            json.dumps(
                {
                    "status": "completed",
                    "usage": {
                        "input_tokens": 80000,
                        "cached_input_tokens": 70000,
                        "output_tokens": 5000,
                        "reasoning_output_tokens": 5000,
                    },
                }
            ),
            encoding="utf-8",
        )
    with pytest.raises(RuntimeError, match="combined"):
        TRIAL["quota"](tmp_path)
