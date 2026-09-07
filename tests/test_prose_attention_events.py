"""Contain initial knowledge and enforce event activation before matched drafting."""

import copy
import json
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
T = runpy.run_path(str(ROOT / "research/quality-measurement/prose_attention_events.py"))
FIXTURE = runpy.run_path(str(ROOT / "tests/test_prose_narration_obligations.py"))


def source():
    chapter = FIXTURE["source"]()
    chapter["facts"] = [
        {
            "id": "F1a",
            "source_id": "F1",
            "kind": "context",
            "when": "opening",
            "text": "OPENING_FACT",
        },
        {
            "id": "F1b",
            "source_id": "F1",
            "kind": "event",
            "when": "next",
            "text": "INCOMING_SECRET",
        },
        {
            "id": "F1c",
            "source_id": "F1",
            "kind": "knowledge",
            "when": "later",
            "text": "LATE_SECRET",
        },
    ]
    chapter["implicit_ids"] = ["F1c"]
    return {"chapter_source": chapter, "initial_ids": ["F1a"], "activation_ids": ["F1b", "F1c"]}


def state(id="F1a"):
    return {
        "concern": "Attend to the available detail.",
        "foreground": [id],
        "peripheral": [],
        "basis": [id],
        "unresolved": "What happens next?",
    }


def updates():
    return {"updates": [{"after": i, "state": state(i)} for i in ("F1b", "F1c")]}


def test_attention_initial_request_excludes_future_story_literals_and_original():
    request = T["initial_request"](source())
    assert "OPENING_FACT" in request["prompt"]
    assert not any(
        s in request["prompt"]
        for s in ("INCOMING_SECRET", "LATE_SECRET", "ONE", "Incidental original wording")
    )
    assert list(json.loads(request["prompt"])) == ["known_facts"]


def test_attention_transition_before_states_are_code_carried_and_activation_is_after_event():
    s, initial, u = source(), state(), updates()
    before = copy.deepcopy((s, initial, u))
    result = T["trajectory"](s, initial, u)
    assert [r["active_after"] for r in result["states"]] == ["opening", "F1b", "F1c"]
    assert result["transitions"] == [
        {"before_state": "S0", "incoming_source": "F1b", "after_state": "S1"},
        {"before_state": "S1", "incoming_source": "F1c", "after_state": "S2"},
    ]
    assert result["states"][0]["state"] == initial
    assert (s, initial, u) == before
    assert T["available"](s, "F1b") == ["F1a", "F1b"]


@pytest.mark.parametrize("bad", ["future", "before", "order", "missing", "overlap", "long"])
def test_attention_events_reject_early_knowledge_and_changed_trajectory(bad):
    s, u = source(), updates()
    row = u["updates"][0]
    if bad == "future":
        row["state"]["basis"] = ["F1c"]
    elif bad == "before":
        row["before_state"] = state("F1c")
    elif bad == "order":
        u["updates"].reverse()
    elif bad == "missing":
        u["updates"].pop()
    elif bad == "overlap":
        row["state"]["peripheral"] = row["state"]["foreground"]
    else:
        row["state"]["concern"] = "word " * 31
    with pytest.raises(ValueError):
        T["trajectory"](s, state(), u)


def test_attention_event_writer_conditions_have_identical_material_and_trajectory():
    s = source()
    requests = T["writer_requests"](s, state(), updates())
    a, b = [json.loads(requests[k]["prompt"]) for k in ("background", "operative")]
    assert a.pop("rendering_mode") != b.pop("rendering_mode")
    assert a == b
    assert a["source_units"] == s["chapter_source"]["facts"]
    assert a["required_narration"] == ["F1a", "F1b"]
    assert a["display_templates"] == ["ONE", "ONE"]
    assert requests["background"]["system"] == requests["operative"]["system"]
    assert all("Incidental original wording" not in r["prompt"] for r in requests.values())


def test_attention_event_source_rejects_reordered_or_initial_activations():
    for ids in (["F1c", "F1b"], ["F1a", "F1b"], ["F1b", "F1b"]):
        s = source()
        s["activation_ids"] = ids
        with pytest.raises(ValueError):
            T["payload"](s)


def test_attention_event_freeze_requires_review_of_both_texts_and_all_activations(tmp_path):
    s = source()
    T["write_new"](tmp_path / "manifest.json", {"source": s, "files": {}})
    T["write_new"](tmp_path / "updates-manifest.json", {"initial": state(), "files": {}})
    for name, text in (("initial-1", state()), ("updates-1", updates())):
        folder = tmp_path / name
        folder.mkdir()
        (folder / "full-1.txt").write_text(json.dumps(text))
        T["write_new"](folder / "full-1.result.json", {"text": json.dumps(text)})
    path = tmp_path / "review.json"
    T["write_new"](
        path,
        {
            "text_sha256": {
                n: T["sha"](tmp_path / n / "full-1.txt") for n in ("initial-1", "updates-1")
            },
            "source_compatible": True,
            "knowledge_timing": True,
            "no_new_canon": True,
            "reviewed_activations": ["opening", "F1b"],
        },
    )
    with pytest.raises(ValueError, match="complete temporal review"):
        T["freeze"](tmp_path, path)
    assert not (tmp_path / "draft-manifest.json").exists()


def test_attention_event_quota_counts_both_prepasses_and_stops_on_failures(tmp_path):
    for name in ("initial-1", "updates-1"):
        folder = tmp_path / name
        folder.mkdir()
        T["write_new"](
            folder / "full-1.result.json",
            {
                "status": "completed",
                "usage": {
                    "input_tokens": 5,
                    "cached_input_tokens": 5,
                    "output_tokens": 7,
                    "reasoning_output_tokens": 11,
                },
            },
        )
    assert T["quota"](tmp_path) == 46
    path = tmp_path / "updates-1/full-1.result.json"
    path.write_text(
        json.dumps(
            {
                "status": "completed",
                "usage": {
                    "input_tokens": 1,
                    "output_tokens": 1,
                    "reasoning_output_tokens": 125_000,
                },
            }
        )
    )
    with pytest.raises(RuntimeError, match="token stop"):
        T["quota"](tmp_path)
    path.write_text(json.dumps({"status": "failed"}))
    with pytest.raises(RuntimeError, match="failure"):
        T["quota"](tmp_path)


@pytest.mark.parametrize("name", ["initial-1", "updates-1", "operative-1"])
def test_attention_event_test_guard_blocks_every_model_role(tmp_path, name):
    (tmp_path / name).mkdir()
    with pytest.raises(RuntimeError, match="disabled in tests"):
        T["call"](
            tmp_path, name, {"system": "test", "prompt": "test"}, {"prefix": ["node", "codex"]}
        )
    assert not list(tmp_path.glob("*/full-1.request.json"))
