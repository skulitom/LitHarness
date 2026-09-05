"""Subscription, no-retry and event containment for the isolated Codex diagnostic."""

import json
import runpy
from pathlib import Path

import pytest

TRIAL = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "research/quality-measurement/prose_codex.py")
)


def events():
    return [
        {"type": "thread.started", "thread_id": "test"},
        {"type": "turn.started"},
        {"type": "item.completed", "item": {"type": "agent_message", "text": "A scene."}},
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 100,
                "cached_input_tokens": 80,
                "output_tokens": 20,
            },
        },
    ]


def test_codex_subscription_configuration_does_not_inherit_api_credentials(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-sentinel")
    monkeypatch.setenv("CODEX_API_KEY", "test-only-sentinel")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://invalid.example")
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    env = TRIAL["subscription_env"]()
    assert not set(TRIAL["REMOVED_ENV"]) & env.keys()
    assert env["CODEX_HOME"] == str(tmp_path)
    args = TRIAL["argv"](["node", "codex.js"], tmp_path / "system.txt", tmp_path / "work")
    assert 'forced_login_method="chatgpt"' in args
    assert 'model_provider="openai"' in args
    assert "--ignore-user-config" in args and "--ephemeral" in args
    assert args[args.index("--sandbox") + 1] == "read-only"
    assert "project_doc_max_bytes=0" in args
    assert args[-1] == "-" and "--dangerously-bypass-approvals-and-sandbox" not in args


def test_codex_usage_preserves_cached_subset_without_double_counting():
    result = TRIAL["parse_events"]("\n".join(map(json.dumps, events())))
    assert result["text"] == "A scene."
    assert result["usage"]["input_tokens"] + result["usage"]["output_tokens"] == 120


@pytest.mark.parametrize(
    "damage", ["tool", "unfinished_tool", "error", "extra_message", "usage", "cache"]
)
def test_codex_refuses_tool_events_ambiguous_output_and_unknown_usage(damage):
    stream = events()
    if damage == "tool":
        stream.insert(2, {"type": "item.completed", "item": {"type": "command_execution"}})
    elif damage == "unfinished_tool":
        stream.insert(2, {"type": "item.started", "item": {"type": "mcp_tool_call"}})
    elif damage == "error":
        stream.insert(2, {"type": "error", "message": "request failed"})
    elif damage == "extra_message":
        stream.insert(2, stream[2])
    elif damage == "usage":
        del stream[-1]["usage"]["input_tokens"]
    else:
        stream[-1]["usage"]["cached_input_tokens"] = 101
    with pytest.raises(ValueError):
        TRIAL["parse_events"]("\n".join(map(json.dumps, stream)))


def test_codex_trial_blocks_fresh_billing_and_interrupted_or_changed_replay(tmp_path):
    manifest = {
        "prefix": ["node", "codex.js"],
        "requests": {
            "full": {"system": "Rules.", "prompt": "Scene."},
        },
    }
    with pytest.raises(RuntimeError, match="disabled in tests"):
        TRIAL["complete_once"](tmp_path, "full-1", manifest)
    assert not list(tmp_path.iterdir())
    request = {
        "system": "Rules.",
        "prompt": "Scene.",
        "argv": TRIAL["argv"](manifest["prefix"], tmp_path / "system.txt", tmp_path / "work"),
        "requested_model": TRIAL["MODEL"],
        "reasoning_effort": TRIAL["EFFORT"],
        "authentication": "chatgpt",
        "removed_environment_keys": list(TRIAL["REMOVED_ENV"]),
    }
    TRIAL["write_new"](tmp_path / "full-1.request.json", request)
    with pytest.raises(RuntimeError, match="no automatic retry"):
        TRIAL["complete_once"](tmp_path, "full-1", manifest)
    TRIAL["write_new"](tmp_path / "full-1.result.json", {"status": "completed", "text": "cached"})
    assert TRIAL["complete_once"](tmp_path, "full-1", manifest)["text"] == "cached"
    manifest["requests"]["full"]["prompt"] = "Changed."
    with pytest.raises(ValueError, match="identity changed"):
        TRIAL["complete_once"](tmp_path, "full-1", manifest)
