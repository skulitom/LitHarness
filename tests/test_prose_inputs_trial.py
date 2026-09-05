"""The isolated trial changes only its declared factors and cannot rewrite canon."""

import hashlib
import json
import runpy
from dataclasses import asdict
from pathlib import Path

import pytest

from litharness.domain import house
from litharness.domain.generation import CompletionRequest

TRIAL = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "research/quality-measurement/prose_inputs.py")
)


def test_factorial_requests_preserve_everything_outside_their_declared_slots():
    base = {
        "system": f"Writer dossier\n{house.HOUSE_RULES}\nRULES: three keys. AUTHOR LOCK.",
        "prompt": "Concept. Earlier prose. World facts. This scene: Original scene plan.",
    }
    for arm in TRIAL["ARMS"]:
        request = TRIAL["draft_request"](base, "Ordered actions: move the key.", arm)
        expected_system = base["system"]
        if arm.startswith("plain_"):
            expected_system = expected_system.replace(house.HOUSE_RULES, TRIAL["PLAIN_GUIDANCE"])
        expected_prompt = base["prompt"]
        if arm.endswith("_factual"):
            expected_prompt = expected_prompt.replace(
                "Original scene plan.", "Ordered actions: move the key."
            )
        assert request.system == expected_system
        assert request.prompt == expected_prompt
        assert request.allowed_tools == ()
        assert request.model == "claude-opus-5"


@pytest.mark.parametrize("bad", ["no marker", "This scene: one This scene: two"])
def test_ambiguous_plan_boundaries_refuse_before_a_call(bad):
    with pytest.raises(ValueError, match="boundaries"):
        TRIAL["draft_request"](
            {"system": house.HOUSE_RULES, "prompt": bad}, "facts", "plain_factual"
        )


def test_factual_source_quotes_are_checked_but_never_sent_to_drafting():
    source = "The key sulked in her pocket. She unlocked the door."
    payload = {
        key: [{"text": "She has a key.", "source_quote": "The key sulked in her pocket."}]
        for key in TRIAL["PLAN_SECTIONS"]
    }
    rendered = TRIAL["render_factual"](payload, source)
    assert "sulked" not in rendered
    assert "She has a key." in rendered
    payload["ordered_actions"][0]["source_quote"] = "A nonexistent source."
    with pytest.raises(ValueError, match="source quote"):
        TRIAL["render_factual"](payload, source)


def test_paragraph_patches_preserve_every_unedited_paragraph():
    source = "The key sulked.\n\nShe opened the door.\n\n[STATUS] Keys 0"
    edited = TRIAL["apply_edits"](
        source,
        {
            "edits": [
                {"paragraph": 1, "original": "The key sulked.", "replacement": "She held the key."}
            ]
        },
    )
    assert edited == "She held the key.\n\nShe opened the door.\n\n[STATUS] Keys 0"
    assert TRIAL["apply_edits"](source, {"edits": []}) == source
    request = TRIAL["edit_request"](source)
    assert source.split("\n\n")[-1] in request.prompt


@pytest.mark.parametrize(
    "edit",
    [
        {"paragraph": 7, "original": "Seven", "replacement": "Changed"},
        {"paragraph": True, "original": "One", "replacement": "Changed"},
        {"paragraph": 1, "original": "Wrong", "replacement": "Changed"},
        {"paragraph": 1, "original": "One", "replacement": "Two\n\nParagraphs"},
        {"paragraph": 1, "original": "One", "replacement": ""},
    ],
)
def test_out_of_scope_or_untraceable_edits_refuse(edit):
    source = "\n\n".join(["One", "Two", "Three", "Four", "Five", "Six", "Seven"])
    with pytest.raises(ValueError):
        TRIAL["apply_edits"](source, {"edits": [edit]})


def test_cached_calls_replay_but_uncertain_calls_and_changed_inputs_never_resend(tmp_path):
    request = CompletionRequest(prompt="Request", system="System")
    (tmp_path / "cached.request.json").write_text(json.dumps(asdict(request)), encoding="utf-8")
    (tmp_path / "cached.result.json").write_text('{"text":"Existing"}', encoding="utf-8")
    assert TRIAL["complete_once"](tmp_path, "cached", request) == {"text": "Existing"}
    with pytest.raises(ValueError, match="request changed"):
        TRIAL["complete_once"](tmp_path, "cached", CompletionRequest(prompt="Different"))
    (tmp_path / "uncertain.request.json").write_text(json.dumps(asdict(request)), encoding="utf-8")
    with pytest.raises(RuntimeError, match="no automatic retry"):
        TRIAL["complete_once"](tmp_path, "uncertain", request)
    with pytest.raises(RuntimeError, match="disabled in tests"):
        TRIAL["complete_once"](tmp_path, "new", request)


def test_output_directory_cannot_point_at_production(tmp_path):
    with pytest.raises(ValueError, match="beneath runs"):
        TRIAL["prepare"](tmp_path, Path("unused.json"), Path("unused.txt"))


def test_frozen_reviewed_plan_bypasses_conversion_and_refuses_changed_notes(tmp_path, capsys):
    payload = {
        key: [{"text": "She opens the door.", "source_quote": "She opens the door."}]
        for key in TRIAL["PLAN_SECTIONS"]
    }
    base = {"prompt": "This scene: She opens the door."}
    manifest = {
        "script_sha256": hashlib.sha256(Path(TRIAL["__file__"]).read_bytes()).hexdigest(),
        "registration_sha256": hashlib.sha256(TRIAL["REGISTRATION"].read_bytes()).hexdigest(),
        "base": base,
        "base_digest": TRIAL["digest"](base),
        "source_scene": "Scene",
        "source_scene_digest": TRIAL["digest"]("Scene"),
        "reviewed_plan": payload,
        "reviewed_plan_digest": TRIAL["digest"](payload),
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    # Tests disable fresh calls, so this succeeds only if supplied notes bypass conversion.
    TRIAL["run"](tmp_path, "plan")
    assert "She opens the door." in capsys.readouterr().out
    assert not list(tmp_path.glob("*.request.json"))
    payload["ordered_actions"][0]["text"] = "Changed after preparation."
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="reviewed plan changed"):
        TRIAL["run"](tmp_path, "plan")
