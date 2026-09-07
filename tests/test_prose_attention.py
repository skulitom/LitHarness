"""Validate matched attention exposure, source containment and dispatch guards."""

import copy
import json
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TRIAL = runpy.run_path(str(ROOT / "research/quality-measurement/prose_attention.py"))
FIXTURE = runpy.run_path(str(ROOT / "tests/test_prose_narration_obligations.py"))


def source():
    return {
        "chapter_source": FIXTURE["source"](),
        "phases": [{"id": "P1", "first": "F1a", "last": "F1b"}],
    }


def trace():
    return {
        "phases": [
            {
                "id": "P1",
                "concern": "A provisional concern.",
                "foreground": ["F1a"],
                "peripheral": ["F1b"],
                "shift": {"at": "F1a", "pressure": "An existing event."},
                "unresolved": "An open question.",
                "basis": ["F1a"],
            }
        ]
    }


def test_attention_conditions_change_only_trace_use_not_source_or_trace_exposure():
    s, t = source(), trace()
    original = copy.deepcopy((s, t))
    requests = TRIAL["writer_requests"](s, t)
    background, operative = (json.loads(requests[k]["prompt"]) for k in ("background", "operative"))
    assert background.pop("rendering_mode") != operative.pop("rendering_mode")
    assert background == operative
    assert background["attention_trace"] == t
    assert background["source_units"] == s["chapter_source"]["facts"]
    assert background["required_narration"] == ["F1a"]
    assert background["display_templates"] == ["ONE", "ONE"]
    assert requests["background"]["system"] == requests["operative"]["system"]
    assert all("Incidental original wording" not in r["prompt"] for r in requests.values())
    assert "Incidental original wording" not in TRIAL["trace_request"](s)["prompt"]
    assert (s, t) == original


@pytest.mark.parametrize("kind", ["future", "overlap", "shift", "duplicate", "long", "extra"])
def test_attention_trace_rejects_invalid_references_or_unbounded_content(kind):
    s, t = source(), trace()
    row = t["phases"][0]
    if kind == "future":
        s["chapter_source"]["facts"].append(
            {
                "id": "F1c",
                "source_id": "F1",
                "kind": "event",
                "when": "later",
                "text": "Later event.",
            }
        )
        s["phases"].append({"id": "P2", "first": "F1c", "last": "F1c"})
        t["phases"].append({**copy.deepcopy(row), "id": "P2"})
        row["basis"] = ["F1c"]
    elif kind == "overlap":
        row["peripheral"] = row["foreground"]
    elif kind == "shift":
        row["shift"]["at"] = "missing"
    elif kind == "duplicate":
        row["foreground"] *= 2
    elif kind == "long":
        row["concern"] = "word " * 36
    else:
        row["sample_prose"] = "Disallowed output."
    with pytest.raises(ValueError):
        TRIAL["validate_trace"](s, t)


def test_attention_phases_cannot_omit_or_reorder_source():
    for first, last in [("F1b", "F1b"), ("F1a", "F1a"), ("F1b", "F1a")]:
        s = source()
        s["phases"][0].update(first=first, last=last)
        with pytest.raises(ValueError):
            TRIAL["source_payload"](s)


def test_attention_freeze_requires_hash_bound_complete_source_review(tmp_path):
    s = source()
    TRIAL["write_new"](tmp_path / "manifest.json", {"files": {}, "source": s})
    folder = tmp_path / "trace-1"
    folder.mkdir()
    (folder / "full-1.txt").write_text(json.dumps(trace()), encoding="utf-8")
    TRIAL["write_new"](
        folder / "full-1.result.json", {"status": "completed", "text": json.dumps(trace())}
    )
    review = tmp_path / "review.json"
    TRIAL["write_new"](
        review,
        {
            "trace_sha256": TRIAL["sha"](folder / "full-1.txt"),
            "source_compatible": True,
            "future_knowledge_absent": False,
            "no_new_canon": True,
            "reviewed_phases": ["P1"],
        },
    )
    with pytest.raises(ValueError, match="complete source review"):
        TRIAL["freeze"](tmp_path, review)
    assert not (tmp_path / "draft-manifest.json").exists()


def test_attention_quota_includes_trace_reasoning_and_failed_calls(tmp_path):
    folder = tmp_path / "trace-1"
    folder.mkdir()
    path = folder / "full-1.result.json"
    value = {
        "status": "completed",
        "usage": {
            "input_tokens": 5,
            "cached_input_tokens": 5,
            "output_tokens": 7,
            "reasoning_output_tokens": 11,
        },
    }
    TRIAL["write_new"](path, value)
    assert TRIAL["quota"](tmp_path) == 23
    value["usage"]["reasoning_output_tokens"] = 95_000
    path.write_text(json.dumps(value))
    with pytest.raises(RuntimeError, match="token stop"):
        TRIAL["quota"](tmp_path)
    path.write_text(json.dumps({"status": "failed"}))
    with pytest.raises(RuntimeError, match="failure"):
        TRIAL["quota"](tmp_path)


def test_attention_test_guard_prevents_trace_dispatch(tmp_path):
    s = source()
    TRIAL["write_new"](
        tmp_path / "manifest.json",
        {
            "files": {},
            "source": s,
            "trace_request": TRIAL["trace_request"](s),
            "prefix": ["node", "codex"],
        },
    )
    (tmp_path / "trace-1").mkdir()
    with pytest.raises(RuntimeError, match="disabled in tests"):
        TRIAL["trace_phase"](tmp_path)
    assert not list(tmp_path.glob("*/full-1.request.json"))
