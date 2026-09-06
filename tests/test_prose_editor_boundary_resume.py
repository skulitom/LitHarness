"""Offline recovery keeps auxiliary accounting explicit and refuses other failures."""

import json
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TRIAL = runpy.run_path(str(ROOT / "research/quality-measurement/prose_editor_boundary_resume.py"))


def raw():
    main = {
        "inputTokens": 2,
        "cacheReadInputTokens": 3,
        "cacheCreationInputTokens": 5,
        "outputTokens": 7,
    }
    extra = {
        "inputTokens": 11,
        "cacheReadInputTokens": 13,
        "cacheCreationInputTokens": 17,
        "outputTokens": 19,
    }
    events = [
        {
            "type": "assistant",
            "message": {"model": "claude-opus-5", "content": [{"type": "text", "text": "x"}]},
        },
        {
            "type": "result",
            "subtype": "success",
            "num_turns": 1,
            "result": "x",
            "usage": {
                "input_tokens": 2,
                "cache_read_input_tokens": 3,
                "cache_creation_input_tokens": 5,
                "output_tokens": 7,
            },
            "modelUsage": {"claude-opus-5": main, "claude-haiku-4-5-20251001": extra},
        },
    ]
    return {"exit_code": 0, "stdout": "\n".join(map(json.dumps, events))}


def test_editor_boundary_recovery_counts_all_models_without_double_counting_main():
    result = TRIAL["recover"](raw())
    assert result["usage"] == {"input_tokens": 51, "cached_input_tokens": 16, "output_tokens": 26}
    assert result["original_result_status"] == "failed"
    assert result["containment"].startswith("failed")


@pytest.mark.parametrize("mutation", ["writer", "accounting", "transport", "tool"])
def test_editor_boundary_recovery_refuses_other_transport_or_containment_failures(mutation):
    value = raw()
    events = [json.loads(line) for line in value["stdout"].splitlines()]
    if mutation == "writer":
        events[0]["message"]["model"] = "other"
    elif mutation == "accounting":
        events[-1]["modelUsage"]["claude-opus-5"]["inputTokens"] = 999
    elif mutation == "transport":
        value["exit_code"] = 1
    else:
        events[0]["message"]["content"] = [{"type": "tool_use"}]
    value["stdout"] = "\n".join(map(json.dumps, events))
    with pytest.raises(ValueError):
        TRIAL["recover"](value)
