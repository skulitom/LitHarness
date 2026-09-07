"""Guard source exposure, persistent carry, and subscription dispatch boundaries."""

import copy
import json
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
T = runpy.run_path(str(ROOT / "research/quality-measurement/prose_persistent_concern.py"))
F = runpy.run_path(str(ROOT / "tests/test_prose_attention_events.py"))


def source():
    s = F["source"]()
    s["chapter_source"]["facts"] += [
        {"id": f"F{i}", "source_id": "F1", "kind": "event", "when": "later", "text": f"EVENT_{i}"}
        for i in range(2, 6)
    ]
    return s


def schedule():
    return {
        "question": "What remains uncertain?",
        "opens_after": "F1b",
        "basis": ["F1a", "F1b"],
        "checkpoints": [
            {"after": "F1c", "mode": "background", "notice": []},
            {"after": "F3", "mode": "foreground", "notice": ["F1b", "F3"]},
            {"after": "F5", "mode": "release", "notice": []},
        ],
    }


def test_persistent_concern_carries_same_question_across_unmentioned_events():
    s, c = source(), schedule()
    before = copy.deepcopy((s, c))
    timeline = T["validate_schedule"](s, c)
    assert timeline == {
        "opening": "unavailable",
        "F1a": "unavailable",
        "F1b": "foreground",
        "F1c": "background",
        "F2": "background",
        "F3": "foreground",
        "F4": "foreground",
        "F5": "release",
    }
    assert (s, c) == before


@pytest.mark.parametrize(
    "bad",
    [
        "future_basis",
        "future_notice",
        "order",
        "early",
        "no_return",
        "release",
        "summary",
        "missing",
        "group",
        "context",
    ],
)
def test_persistent_concern_rejects_invalid_knowledge_and_lifecycle(bad):
    s, c = source(), schedule()
    if bad == "future_basis":
        c["basis"] = ["F5"]
    elif bad == "future_notice":
        c["checkpoints"][1]["notice"] = ["F5"]
    elif bad == "order":
        c["checkpoints"].reverse()
    elif bad == "early":
        c["checkpoints"][0]["after"] = "F1b"
    elif bad == "no_return":
        c["checkpoints"][1].update(mode="background", notice=[])
    elif bad == "release":
        c["checkpoints"][0]["mode"] = "release"
    elif bad == "summary":
        c["checkpoints"][1]["meaning"] = "An interpretation to narrate."
    elif bad == "missing":
        c = {"unavailable": True}
    elif bad == "group":
        c["basis"] = ["F1"]
    else:
        c["opens_after"] = "F1a"
    with pytest.raises(ValueError):
        T["validate_schedule"](s, c)


def test_persistent_concern_writers_differ_only_by_schedule_and_exclude_original():
    s, c = source(), schedule()
    r = T["writer_requests"](s, c)
    a, b = [json.loads(r[k]["prompt"]) for k in ("source", "persistent")]
    assert b.pop("concern_schedule") == c
    assert a == b
    assert r["source"]["system"] == r["persistent"]["system"]
    assert a["required_narration"] == ["F1a", "F1b", "F2", "F3", "F4", "F5"]
    assert a["display_templates"] == ["ONE", "ONE"]
    assert all("source_id" not in u for u in a["source_units"])
    assert all("Incidental original wording" not in x["prompt"] for x in r.values())
    q = T["concern_request"](s)
    assert "Incidental original wording" not in q["prompt"]
    assert "literal_sequence" not in q["prompt"]
    assert json.loads(q["prompt"])["allowed_ids_after"]["F1b"] == ["F1a", "F1b"]


def test_persistent_concern_freeze_requires_all_semantic_review_activations(tmp_path, monkeypatch):
    s, c = source(), schedule()
    monkeypatch.setitem(T["CODEX"], "validate", lambda _: {"source": s})
    folder = tmp_path / "concern-1"
    folder.mkdir()
    (folder / "full-1.txt").write_text(json.dumps(c))
    T["write_new"](folder / "full-1.result.json", {"text": json.dumps(c)})
    p = tmp_path / "review.json"
    T["write_new"](
        p,
        {
            "text_sha256": T["sha"](folder / "full-1.txt"),
            "source_compatible": True,
            "knowledge_timing": True,
            "no_new_canon": True,
            "reviewed_activations": ["F1b", "F1c"],
        },
    )
    with pytest.raises(ValueError, match="semantic review"):
        T["freeze"](tmp_path, p)
    assert not (tmp_path / "draft-manifest.json").exists()


def test_persistent_concern_quota_includes_prepass_reasoning_and_stops(tmp_path):
    folder = tmp_path / "concern-1"
    folder.mkdir()
    p = folder / "full-1.result.json"
    r = {
        "status": "completed",
        "usage": {
            "input_tokens": 7,
            "cached_input_tokens": 7,
            "output_tokens": 3,
            "reasoning_output_tokens": 2,
        },
    }
    T["write_new"](p, r)
    assert T["quota"](tmp_path) == 12
    r["usage"]["reasoning_output_tokens"] = T["TOKEN_STOP"]
    p.write_text(json.dumps(r))
    with pytest.raises(RuntimeError, match="token stop"):
        T["quota"](tmp_path)
    p.write_text(json.dumps({"status": "failed"}))
    with pytest.raises(RuntimeError, match="failure"):
        T["quota"](tmp_path)


@pytest.mark.parametrize("name", ["concern-1", "source-1", "persistent-1"])
def test_persistent_concern_test_guard_prevents_every_generation_role(tmp_path, name):
    (tmp_path / name).mkdir()
    with pytest.raises(RuntimeError, match="disabled in tests"):
        T["call"](
            tmp_path, name, {"system": "test", "prompt": "test"}, {"prefix": ["node", "codex"]}
        )
    assert not list(tmp_path.glob("*/full-1.request.json"))
