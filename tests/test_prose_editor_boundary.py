"""Source containment and subscription accounting, not literary validation."""

import copy
import json
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TRIAL = runpy.run_path(str(ROOT / "research/quality-measurement/prose_editor_boundary.py"))
FIXTURE = runpy.run_path(str(ROOT / "tests/test_prose_narration_obligations.py"))


def fixture():
    chapter = FIXTURE["source"]()
    chapter["scene_break_after"] = ["F1a"]
    return {"chapter_source": chapter, "scenes": {"mechanical": {}, "social": {}}}


def test_editor_boundary_removes_actual_optional_bytes_and_preserves_required_literals():
    source = fixture()
    before = copy.deepcopy(source)
    full = TRIAL["request_for"]("codex-full-1", source, {})
    static = TRIAL["request_for"]("codex-static-1", source, {})
    assert full["system"] == static["system"]
    assert "She understands." in full["prompt"] and "She understands." not in static["prompt"]
    assert "Incidental original wording" not in full["prompt"]
    data = json.loads(static["prompt"].split("\n", 1)[1])
    assert data["required_narration"] == ["F1a"]
    assert data["literal_sequence"] == ["ONE.", "ONE."]
    assert source == before
    claude = TRIAL["request_for"]("claude-static-1", source, {})
    assert {k: v for k, v in claude.items() if k != "provider"} == {
        k: v for k, v in static.items() if k != "provider"
    }


def test_editor_boundary_selector_cannot_rewrite_or_pass_reasons_to_writer():
    source = fixture()
    answer = json.dumps({"decisions": [{"id": "F1b", "keep": False, "reason": "SECRET"}]})
    request = TRIAL["request_for"]("codex-editor-1", source, {"selector": {"text": answer}})
    assert "SECRET" not in request["prompt"] and "She understands." not in request["prompt"]
    for rows in [
        [],
        [{"id": "F1a", "keep": False, "reason": "x"}],
        [{"id": "F1b", "keep": "false", "reason": "x"}],
        [{"id": "F1b", "keep": True, "reason": "x", "text": "rewrite"}],
    ]:
        with pytest.raises(ValueError):
            TRIAL["selected_ids"](source["chapter_source"], json.dumps({"decisions": rows}))
    with pytest.raises(ValueError, match="mandatory"):
        TRIAL["package"](source["chapter_source"], ["F1b"])


def test_editor_boundary_render_only_sees_own_intermediate_and_common_literals():
    source = fixture()
    prior = {"russian-source-1": {"text": "OWN"}, "english-source-1": {"text": "SIBLING"}}
    r = TRIAL["request_for"]("russian-render-1", source, prior)
    assert json.loads(r["prompt"]) == {
        "passage": "OWN",
        "protected_literal_sequence": ["ONE.", "ONE."],
    }
    e = TRIAL["request_for"]("english-render-1", source, prior)
    assert e["system"] == r["system"]


def claude_events():
    return [
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "x"}]}},
        {
            "type": "result",
            "subtype": "success",
            "num_turns": 1,
            "result": "x",
            "usage": {
                "input_tokens": 3,
                "cache_read_input_tokens": 7,
                "cache_creation_input_tokens": 11,
                "output_tokens": 13,
            },
            "modelUsage": {TRIAL["CLAUDE_MODEL"]: {}},
        },
    ]


def test_editor_boundary_claude_counts_cache_read_and_creation_as_input():
    parsed = TRIAL["parse_claude"]("\n".join(map(json.dumps, claude_events())))
    assert parsed["usage"] == {"input_tokens": 21, "cached_input_tokens": 7, "output_tokens": 13}
    assert TRIAL["quota"]([{"status": "completed", **parsed}]) == 34


@pytest.mark.parametrize("mutation", ["tool", "model", "usage", "turn", "failure"])
def test_editor_boundary_rejects_claude_tools_fallback_and_unknown_accounting(mutation):
    events = claude_events()
    if mutation == "tool":
        events[0]["message"]["content"] = [{"type": "tool_use"}]
    elif mutation == "model":
        events[-1]["modelUsage"] = {"other": {}}
    elif mutation == "usage":
        events[-1]["usage"].pop("cache_read_input_tokens")
    elif mutation == "turn":
        events[-1]["num_turns"] = 2
    else:
        events[-1]["is_error"] = True
    with pytest.raises(ValueError):
        TRIAL["parse_claude"]("\n".join(map(json.dumps, events)))


def test_editor_boundary_no_billing_routes_and_separate_reasoning_counts(monkeypatch):
    for key in [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_BASE_URL",
        "CLAUDE_CODE_USE_VERTEX",
        "CLAUDE_CODE_USE_BEDROCK",
    ]:
        monkeypatch.setenv(key, "test-value")
        assert key not in TRIAL["claude_env"]()
    with pytest.raises(RuntimeError, match="dispatch stop"):
        TRIAL["quota"](
            [
                {
                    "status": "completed",
                    "usage": {
                        "input_tokens": 1,
                        "output_tokens": 1,
                        "reasoning_output_tokens": 300_000,
                    },
                }
            ]
        )
    with pytest.raises(RuntimeError, match="failure"):
        TRIAL["quota"]([{"status": "failed"}])


def test_editor_boundary_live_guard_precedes_request_and_subprocess(tmp_path):
    manifest = {
        "source": fixture(),
        "prefix": ["node", "codex"],
        "authentication": {"codex": "chatgpt"},
    }
    with pytest.raises(RuntimeError, match="disabled in tests"):
        TRIAL["complete"](tmp_path, "codex-static-1", manifest, {})
    assert not list(tmp_path.glob("*/request.json"))


def test_editor_boundary_replay_refuses_changed_identity_without_dispatch(tmp_path):
    manifest = {
        "source": fixture(),
        "prefix": ["node", "codex"],
        "authentication": {"codex": "chatgpt"},
    }
    folder = tmp_path / "codex-static-1"
    folder.mkdir()
    TRIAL["write_new"](folder / "request.json", {"prompt": "different"})
    with pytest.raises(ValueError, match="identity"):
        TRIAL["complete"](tmp_path, "codex-static-1", manifest, {})
