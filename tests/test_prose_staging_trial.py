"""Containment of source requirements, staging order and subscription-only calls."""

import runpy
from pathlib import Path

import pytest

TRIAL = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "research/quality-measurement/prose_staging.py")
)
PROMPT = (
    "Private facts stay private.\nOrdered actions:\n- Read the notice.\n- Close the gate."
    "\n\nEnding state:\nStop at the shut gate."
)


def proposal():
    return {
        "steps": [
            {
                "id": "s1",
                "source_actions": ["a1", "a2"],
                "action": "Read, then close the gate.",
                "response": "",
                "consequence": "The gate is shut.",
                "new_information": "",
            }
        ],
        "conflicts": [],
    }


def test_staging_adds_notes_without_removing_private_facts_requirements_or_endpoint():
    rendered = TRIAL["staged_prompt"](PROMPT, proposal())
    before, after = PROMPT.split("\nEnding state:\n")
    assert rendered.startswith(before)
    assert rendered.endswith("\nEnding state:\n" + after)
    assert "The gate is shut." in rendered
    assert "source_actions" not in rendered


@pytest.mark.parametrize("damage", ["missing", "reordered", "unknown", "conflict"])
def test_staging_rejects_missing_reordered_unknown_requirements_and_source_conflicts(damage):
    plan = proposal()
    if damage == "missing":
        plan["steps"][0]["source_actions"] = ["a1"]
    elif damage == "reordered":
        plan["steps"][0]["source_actions"] = ["a2", "a1"]
    elif damage == "unknown":
        plan["steps"][0]["source_actions"] = ["a1", "a2", "a3"]
    else:
        plan["conflicts"] = ["The source forbids shutting the gate."]
    with pytest.raises(ValueError):
        TRIAL["staged_prompt"](PROMPT, plan)


def test_staging_removes_api_overrides_and_blocks_fresh_drafts(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-only-sentinel")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "test-only-sentinel")
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-sentinel")
    assert (
        not {"ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "OPENAI_API_KEY"}
        & TRIAL["child_env"]().keys()
    )
    TRIAL["write_new"](tmp_path / "manifest.json", {})
    TRIAL["write_new"](
        tmp_path / "staging.reviewed.json",
        {
            "source_sha256": TRIAL["sha"](tmp_path / "manifest.json"),
            "payload": proposal(),
        },
    )
    with pytest.raises(RuntimeError, match="disabled in tests"):
        TRIAL["draft_once"](tmp_path, "control-1", {"base": {"system": "Rules.", "prompt": PROMPT}})
    assert not list(tmp_path.glob("*.request.json"))
