"""Future exclusion and review/dispatch guards for prefix-only attention proposals."""

import copy
import json
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
T = runpy.run_path(str(ROOT / "research/quality-measurement/prose_prospective_attention.py"))
F = runpy.run_path(str(ROOT / "tests/test_prose_persistent_concern.py"))


def source():
    s = F["source"]()
    s["chapter_source"]["facts"].append(
        {
            "id": "F6",
            "source_id": "F1",
            "kind": "context",
            "when": "known at opening",
            "text": "ALREADY_KNOWN",
        }
    )
    s["initial_ids"].append("F6")
    planner = [{k: u[k] for k in ("id", "kind", "text")} for u in s["chapter_source"]["facts"]]
    # Earlier facts may have editorial hints about later events. The reviewed view
    # excludes them; changing canonical source is neither necessary nor acceptable.
    s["chapter_source"]["facts"][0]["when"] = "before INCOMING_SECRET"
    s["chapter_source"]["facts"][-1]["text"] += "; not something learned after LATE_SECRET"
    return {"source": s, "before_ids": ["F1b", "F2", "F4"], "planner_units": planner}


def expectations():
    return [
        {
            "anticipation": "An ordinary continuation",
            "watch_for": "The available detail",
            "basis": ["F1a"],
        }
        for _ in range(3)
    ]


def test_prospective_prefix_excludes_incoming_later_prose_and_metadata():
    s = source()
    before = copy.deepcopy(s)
    requests = T["expectation_requests"](s)
    first, middle, last = [json.loads(r["prompt"]) for r in requests]
    assert set(first) == {"source_units", "initial_ids"}
    assert [u["id"] for u in first["source_units"]] == ["F1a", "F6"]
    assert [u["id"] for u in middle["source_units"]] == ["F1a", "F1b", "F1c", "F6"]
    assert [u["id"] for u in last["source_units"]] == ["F1a", "F1b", "F1c", "F2", "F3", "F6"]
    assert all(
        set(u) == {"id", "kind", "text"} for r in (first, middle, last) for u in r["source_units"]
    )
    for forbidden in (
        "INCOMING_SECRET",
        "LATE_SECRET",
        "EVENT_",
        "Incidental original wording",
        "ONE",
    ):
        assert forbidden not in requests[0]["prompt"]
    assert "EVENT_2" not in requests[1]["prompt"]
    assert "EVENT_4" not in requests[2]["prompt"]
    assert s == before


@pytest.mark.parametrize("bad", ["metadata", "reorder", "missing"])
def test_prospective_requires_complete_reviewed_view_without_timing_metadata(bad):
    s = source()
    if bad == "metadata":
        s["planner_units"][0]["when"] = "before INCOMING_SECRET"
    elif bad == "reorder":
        s["planner_units"].reverse()
    else:
        s["planner_units"].pop()
    with pytest.raises(ValueError, match="planner"):
        T["expectation_requests"](s)


@pytest.mark.parametrize(
    "bad", ["incoming", "future", "group", "move", "meaning", "missing", "long"]
)
def test_prospective_rejects_unavailable_references_and_changed_schema(bad):
    s, e = source(), expectations()[0]
    if bad in ("incoming", "future", "group"):
        e["basis"] = [{"incoming": "F1b", "future": "F5", "group": "F1"}[bad]]
    elif bad == "move":
        e["before"] = "F5"
    elif bad == "meaning":
        e["meaning"] = "An outcome to explain"
    elif bad == "missing":
        e = {"unavailable": True}
    else:
        e["watch_for"] = "word " * 21
    with pytest.raises(ValueError):
        T["validate_expectation"](s, "F1b", e)


def test_prospective_writers_differ_only_by_cards_with_orchestrated_boundaries():
    s, e = source(), expectations()
    r = T["writer_requests"](s, e)
    a, b = [json.loads(r[k]["prompt"]) for k in ("source", "prospective")]
    cards = b.pop("prospective_attention")
    assert cards == [{"before": i, **c} for i, c in zip(s["before_ids"], e, strict=True)]
    assert a == b and r["source"]["system"] == r["prospective"]["system"]
    assert len(a["source_units"]) == 8 and len(a["required_narration"]) == 7
    assert a["display_templates"] == ["ONE", "ONE"]
    assert all("Incidental original wording" not in q["prompt"] for q in r.values())


@pytest.mark.parametrize("bad", ["cutoff", "hash", "read", "canon"])
def test_prospective_freeze_requires_review_of_every_input_and_proposal(tmp_path, monkeypatch, bad):
    s, e = source(), expectations()
    monkeypatch.setitem(T["CODEX"], "validate", lambda _: {"source": s})
    for name, value in zip(T["ORDER"][:3], e, strict=True):
        folder = tmp_path / name
        folder.mkdir()
        (folder / "full-1.txt").write_text(json.dumps(value))
        T["write_new"](folder / "full-1.result.json", {"text": json.dumps(value)})
    review = {
        "text_sha256": {n: T["sha"](tmp_path / n / "full-1.txt") for n in T["ORDER"][:3]},
        "reviewed_before_ids": s["before_ids"],
        "source_compatible": True,
        "knowledge_timing": True,
        "no_new_canon": True,
        "all_prefix_inputs_read": True,
    }
    if bad == "cutoff":
        review["reviewed_before_ids"] = s["before_ids"][:2]
    elif bad == "hash":
        review["text_sha256"].pop("expectation-2")
    else:
        review["all_prefix_inputs_read" if bad == "read" else "no_new_canon"] = False
    path = tmp_path / "review.json"
    T["write_new"](path, review)
    with pytest.raises(ValueError, match="semantic review"):
        T["freeze"](tmp_path, path)
    assert not (tmp_path / "draft-manifest.json").exists()


def test_prospective_quota_includes_all_prepasses_reasoning_and_stops(tmp_path):
    r = {
        "status": "completed",
        "usage": {
            "input_tokens": 7,
            "cached_input_tokens": 7,
            "output_tokens": 3,
            "reasoning_output_tokens": 2,
        },
    }
    for name in T["ORDER"][:3]:
        folder = tmp_path / name
        folder.mkdir()
        T["write_new"](folder / "full-1.result.json", r)
    assert T["quota"](tmp_path) == 36
    p = tmp_path / "expectation-3/full-1.result.json"
    r["usage"]["reasoning_output_tokens"] = T["TOKEN_STOP"]
    p.write_text(json.dumps(r))
    with pytest.raises(RuntimeError, match="token stop"):
        T["quota"](tmp_path)
    p.write_text(json.dumps({"status": "failed"}))
    with pytest.raises(RuntimeError, match="failure"):
        T["quota"](tmp_path)


@pytest.mark.parametrize("name", T["ORDER"])
def test_prospective_test_guard_blocks_every_call(tmp_path, name):
    with pytest.raises(RuntimeError, match="disabled in tests"):
        T["call"](tmp_path, name, {"system": "test", "prompt": "test"}, {"prefix": []})
    assert not list(tmp_path.glob("*/full-1.request.json"))
