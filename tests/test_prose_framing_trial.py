"""Source and transport containment for the isolated framing diagnostic."""

import json
import runpy
from pathlib import Path

import pytest

from litharness.domain.generation import CompletionRequest
from litharness.providers.cli import ClaudeCodeProvider

TRIAL = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "research/quality-measurement/prose_framing.py")
)
PROMPT = (
    "Premise: A journey.\n\nPlanned story — intentions:\nCurrent river crossing.\nFuture siege."
    "\n\nWho is in this story:\nmira\n  is: Mira\n  carries: 2 keys"
    "\n\nEstablished facts (POV: mira) — world truth:\nThe ferry is shut.\nA distant city."
    "\n\nTrue, and the reader has not been told — keep private:\nThe ferryman is missing."
    "\n\nNow write Chapter 1. This scene: Mira reaches the ferry.\n\nEnd at the closed gate."
)


def payload(blocks):
    return {
        "decisions": [
            {"id": u["id"], "keep": True, "reason": "Needed here."}
            for b in blocks
            for u in b["units"]
            if not u["mandatory"]
        ]
    }


def test_selection_copies_original_units_with_authority_and_owned_cast():
    blocks = TRIAL["source_blocks"](PROMPT)
    choices = payload(blocks)
    assert TRIAL["selected_prompt"](blocks, choices) == PROMPT
    for row in choices["decisions"]:
        row["keep"] = False
    result = TRIAL["selected_prompt"](blocks, choices)
    assert "ferryman is missing" in result
    assert "keep private" in result and "Now write Chapter 1" in result
    assert "End at the closed gate." in result
    assert "Future siege" not in result and "Needed here" not in result
    cast = [u for b in blocks for u in b["units"] if "carries: 2 keys" in u["text"]]
    assert len(cast) == 1 and "mira\n  is: Mira" in cast[0]["text"]


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "protected", "nonboolean"])
def test_selection_refuses_incomplete_ambiguous_or_protected_ids(mutation):
    blocks = TRIAL["source_blocks"](PROMPT)
    choices = payload(blocks)
    rows = choices["decisions"]
    if mutation == "missing":
        rows.pop()
    elif mutation == "duplicate":
        rows[1] = rows[0].copy()
    elif mutation == "protected":
        rows[0]["id"] = next(u["id"] for b in blocks for u in b["units"] if u["mandatory"])
    else:
        rows[0]["keep"] = 1
    with pytest.raises(ValueError):
        TRIAL["selected_prompt"](blocks, choices)


def test_persona_change_preserves_rules_locks_length_and_plan():
    system = (
        "Writer persona.\n\nYou are drafting one scene of a novel. Write 900 words.\n"
        "World rules: toll is 2 keys.\nAUTHOR-LOCKED STORY DECISIONS:\nUse third person."
    )
    base = {"system": system, "prompt": PROMPT}
    requests = {a: TRIAL["draft_request"](base, "focused packet", a) for a in TRIAL["ARMS"]}
    assert requests["control"].system == requests["isolated"].system == system
    assert requests["neutral"].system == requests["focused"].system == system.split("\n\n", 1)[1]
    assert requests["neutral"].prompt == PROMPT
    assert requests["focused"].prompt == "focused packet"


def test_isolated_transport_keeps_permission_and_mcp_controls_without_appending_twice():
    request = CompletionRequest(prompt="x", system="Write prose.")
    argv = ClaudeCodeProvider()._argv(request)
    assert TRIAL["transport_argv"](argv, False) == argv
    result = TRIAL["transport_argv"](argv, True)
    assert "--append-system-prompt" not in result
    assert result[result.index("--system-prompt") + 1] == "Write prose."
    assert "--safe-mode" in result and "--bare" not in result
    assert result[result.index("--permission-mode") + 1] == "manual"
    assert result[result.index("--tools") + 1] == ""
    assert "--strict-mcp-config" in result and "--no-session-persistence" in result
    assert "--append-system-prompt" in argv  # no mutation of the original argv


def test_framing_cache_binds_transport_and_never_retries_missing_results(tmp_path):
    request = CompletionRequest(prompt="x", system="Write prose.")
    with pytest.raises(RuntimeError, match="disabled in tests"):
        TRIAL["complete_once"](tmp_path, "draft", request, True)
    from dataclasses import asdict

    frozen = {
        "request": asdict(request),
        "isolated": True,
        "argv": TRIAL["transport_argv"](ClaudeCodeProvider()._argv(request), True),
    }
    (tmp_path / "draft.request.json").write_text(json.dumps(frozen), encoding="utf-8")
    with pytest.raises(RuntimeError, match="no automatic retry"):
        TRIAL["complete_once"](tmp_path, "draft", request, True)
    (tmp_path / "draft.result.json").write_text('{"text":"cached"}', encoding="utf-8")
    assert TRIAL["complete_once"](tmp_path, "draft", request, True)["text"] == "cached"
    with pytest.raises(ValueError, match="transport changed"):
        TRIAL["complete_once"](tmp_path, "draft", request, False)
