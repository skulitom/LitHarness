"""Verify information equality and obligation containment, not literary effects."""

import copy
import json
import runpy
from pathlib import Path

import pytest

TRIAL = runpy.run_path(
    str(
        Path(__file__).resolve().parents[1]
        / "research/quality-measurement/prose_narration_obligations.py"
    )
)


def source():
    return {
        "chapter": {
            "text": "Incidental original wording.\n\nONE. ONE.",
            "protected": [{"id": "F1", "paragraphs": [2], "text": "The event and knowledge."}],
            "verbatim": ["ONE."],
            "notes": "No invented rules.",
        },
        "facts": [
            {"id": "F1a", "source_id": "F1", "kind": "event", "when": "now", "text": "Two awards."},
            {
                "id": "F1b",
                "source_id": "F1",
                "kind": "knowledge",
                "when": "after",
                "text": "She understands.",
            },
        ],
        "implicit_ids": ["F1b"],
        "scene_break_after": ["F1b"],
        "notes": "Shared constraints.",
    }


def test_narration_obligations_change_only_required_ids_not_facts_or_knowledge():
    s = source()
    before = copy.deepcopy(s)
    requests = TRIAL["compose"](s)
    full, focused = (
        json.loads(requests[c]["prompt"].split("\n", 1)[1]) for c in ("full", "focused")
    )
    assert requests["full"]["system"] == requests["focused"]["system"]
    assert full.pop("required_narration") == ["F1a", "F1b"]
    assert focused.pop("required_narration") == ["F1a"]
    assert full == focused
    assert focused["source_units"] == s["facts"]
    assert focused["literal_sequence"] == ["ONE.", "ONE."]
    assert all("Incidental original wording" not in r["prompt"] for r in requests.values())
    assert s == before


@pytest.mark.parametrize("implicit", [["F1a"], ["missing"], ["F1b", "F1b"], [], [True]])
def test_narration_obligations_refuse_event_demotion_or_invalid_permission(implicit):
    s = source()
    s["implicit_ids"] = implicit
    with pytest.raises(ValueError, match="implicit"):
        TRIAL["compose"](s)


def test_narration_obligations_refuse_lost_source_group_and_duplicate_unit():
    for field, value in [("source_id", "missing"), ("id", "F1a")]:
        s = source()
        s["facts"][1][field] = value
        with pytest.raises(ValueError, match="coverage"):
            TRIAL["compose"](s)
