"""Exposure and transport-budget controls, not literary outcome tests."""

import json
import runpy
from pathlib import Path

import pytest

TRIAL = runpy.run_path(
    str(
        Path(__file__).resolve().parents[1]
        / "research/quality-measurement/prose_protected_reconstruction.py"
    )
)


def source():
    return {
        "chapter": {
            "text": "An incidental weather comparison.\n\nONE. ONE.",
            "protected": [{"id": "F1", "paragraphs": [2], "text": "Two awards."}],
            "verbatim": ["ONE."],
            "notes": "No invented rules.",
        },
        "scene_break_after": ["F1"],
    }


def test_protected_reconstruction_withholds_only_reference_and_paragraph_coordinates():
    s = source()
    r = TRIAL["compose"](s)
    assert r["full"]["system"] == r["focused"]["system"]
    assert (
        r["full"]["prompt"]
        == r["focused"]["prompt"] + "\n\nOptional reference prose:\n" + s["chapter"]["text"]
    )
    assert "incidental weather comparison" not in r["focused"]["prompt"]
    record = json.loads(r["focused"]["prompt"].split("\n", 1)[1])
    assert record["required_facts"] == [{"id": "F1", "text": "Two awards."}]
    assert record["literal_sequence"] == ["ONE.", "ONE."]
    assert record["scene_break_after_fact"] == ["F1"]


@pytest.mark.parametrize("division", [["missing"], ["F1", "F1"], [True], "F1"])
def test_protected_reconstruction_refuses_invalid_scene_divisions(division):
    s = source()
    s["scene_break_after"] = division
    with pytest.raises(ValueError, match="scene division"):
        TRIAL["compose"](s)


@pytest.mark.parametrize(
    "usage",
    [
        {"input_tokens": 80000, "output_tokens": 5000, "reasoning_output_tokens": 5000},
        {"input_tokens": -1, "output_tokens": 0},
    ],
)
def test_protected_reconstruction_quota_includes_reasoning_and_refuses_invalid_usage(
    tmp_path, usage
):
    (tmp_path / "full-1.result.json").write_text(
        json.dumps({"status": "completed", "usage": usage}), encoding="utf-8"
    )
    with pytest.raises((ValueError, RuntimeError)):
        TRIAL["quota"](tmp_path)
