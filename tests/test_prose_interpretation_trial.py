"""A brief ablation cannot silently alter actions, swap systems or exceed its quota stop."""

import runpy
from pathlib import Path

import pytest

TRIAL = runpy.run_path(
    str(
        Path(__file__).resolve().parents[1] / "research/quality-measurement/prose_interpretation.py"
    )
)


def pair():
    return (
        {
            "system": "Rules. Lesson.",
            "prompt": "Context.\nAction plan:\naction: Open gate.\nEnding state:\nInside.",
        },
        {
            "edits": [
                {
                    "field": "system",
                    "old": " Lesson.",
                    "new": "",
                    "count": 1,
                    "reason": "Remove interpretation.",
                }
            ],
            "clarifications": "",
            "rationale": "Diagnostic.",
        },
    )


def test_interpretation_pair_retains_control_and_refuses_changed_actions():
    source, amendment = pair()
    requests = TRIAL["paired_requests"](source, amendment)
    assert requests["full"] == source
    assert requests["focused"]["system"] == "Rules."
    assert requests["focused"]["prompt"] == source["prompt"]
    amendment["edits"] = [
        {
            "field": "prompt",
            "old": "Open gate.",
            "new": "Close gate.",
            "count": 1,
            "reason": "Invalid action edit.",
        }
    ]
    with pytest.raises(ValueError, match="actions changed"):
        TRIAL["paired_requests"](source, amendment)


def test_interpretation_draft_uses_condition_system_and_fixed_order(tmp_path, monkeypatch):
    seen = []
    manifest = {"requests": {"full": {"system": "Control"}, "focused": {"system": "Treatment"}}}
    monkeypatch.setitem(TRIAL["CODEX"], "validate", lambda out: manifest)
    monkeypatch.setitem(
        TRIAL["CODEX"],
        "complete_once",
        lambda folder, name, m: seen.append(
            (folder.name, name, m["requests"][folder.name]["system"])
        ),
    )
    TRIAL["draft"](tmp_path)
    assert seen == [
        ("full", "full-1", "Control"),
        ("focused", "focused-1", "Treatment"),
        ("focused", "focused-2", "Treatment"),
        ("full", "full-2", "Control"),
    ]


@pytest.mark.parametrize(
    "usage,error",
    [
        (
            {
                "input_tokens": 80000,
                "cached_input_tokens": 70000,
                "output_tokens": 9000,
                "reasoning_output_tokens": 1000,
            },
            RuntimeError,
        ),
        ({"input_tokens": 1}, ValueError),
    ],
)
def test_interpretation_quota_counts_reasoning_and_refuses_missing_usage(tmp_path, usage, error):
    (tmp_path / "full").mkdir()
    TRIAL["write_new"](
        tmp_path / "full/full-1.result.json", {"status": "completed", "usage": usage}
    )
    with pytest.raises(error):
        TRIAL["quota"](tmp_path)
