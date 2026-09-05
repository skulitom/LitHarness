"""Containment controls for the isolated full-context/reconstruction diagnostic."""

import json
import runpy
from pathlib import Path

import pytest

TRIAL = runpy.run_path(
    str(
        Path(__file__).resolve().parents[1] / "research/quality-measurement/prose_reconstruction.py"
    )
)
LENGTH = (
    " Write approximately 400 words. A scene of that length has room to play out in real time "
    "without a summary; give the scene enough events to fill it."
)


def test_context_treatment_protects_locks_displays_roles_and_visibility():
    base = {
        "system": "Use concrete prose." + LENGTH + "\n[STATUS] Mira | KEYS 2\n"
        "AUTHOR-LOCKED STORY DECISIONS — these outrank all other guidance:\nKeep the 3 keys.",
        "prompt": "The grey gate sulked.\n- mira is_a Mira\n"
        "True, and the reader has not been told — keep private.\nThe gate has 2 exits.",
    }
    units, length = TRIAL["source_units"](base)
    payload = {
        "units": [
            {"id": u["id"], "text": u["text"].replace("sulked", "was closed")}
            for u in units
            if not u["protected"]
        ]
    }
    literal = TRIAL["compiled_context"](units, payload)
    assert "The grey gate was closed." in literal["prompt"]
    assert "Keep the 3 keys." in literal["system"]
    assert "Keep the 3 keys." not in literal["prompt"]
    assert "[STATUS] Mira | KEYS 2" in literal["system"]
    assert "True, and the reader has not been told — keep private." in literal["prompt"]
    assert "Keep the 3 keys." not in TRIAL["compile_request"](units).prompt
    control = TRIAL["draft_request"](base, literal, length, "control")
    fixed = TRIAL["draft_request"](base, literal, length, "literal")
    free = TRIAL["draft_request"](base, literal, length, "literal_unbounded")
    assert control.system == base["system"] and control.prompt == base["prompt"]
    assert fixed.prompt == free.prompt
    assert free.system == fixed.system.replace(length, TRIAL["NATURAL_LENGTH"])


@pytest.mark.parametrize("change", ["missing", "duplicate", "protected", "number"])
def test_compilation_refuses_coverage_identity_and_number_changes(change):
    units = [
        {"id": "prompt:0000", "role": "prompt", "text": "Gate 4 is shut.", "protected": False},
        {"id": "system:0000", "role": "system", "text": "LOCK", "protected": True},
    ]
    row = {"id": "prompt:0000", "text": "Gate 4 is closed."}
    rows = [row]
    if change == "missing":
        rows = []
    elif change == "duplicate":
        rows = [row, row]
    elif change == "protected":
        row["id"] = "system:0000"
    else:
        row["text"] = "Gate 5 is closed."
    with pytest.raises(ValueError):
        TRIAL["compiled_context"](units, {"units": rows})


def test_reconstruction_receives_facts_and_displays_without_original_prose():
    source = "The gate sulked behind 2 locks.\n\nTHE CANDIDATE IS AWARDED ONE."
    payload = {
        "paragraphs": [
            {"id": 1, "facts": ["The gate is closed by 2 locks."]},
            {"id": 2, "facts": ["THE CANDIDATE IS AWARDED ONE."]},
        ]
    }
    ledger = TRIAL["meaning_ledger"](source, payload)
    request = TRIAL["rewrite_request"](ledger, TRIAL["displays"](source))
    assert "sulked" not in request.prompt
    assert "2 locks" in request.prompt
    assert "THE CANDIDATE IS AWARDED ONE." in request.prompt
    TRIAL["check_rewrite"](
        source, "There were 2 locks on the closed gate.\n\nTHE CANDIDATE IS AWARDED ONE."
    )
    with pytest.raises(ValueError, match="display sequence"):
        TRIAL["check_rewrite"](source, "There were 2 locks.\n\nTHE CANDIDATE IS AWARDED TWO.")
    payload["paragraphs"].reverse()
    with pytest.raises(ValueError, match="reordered"):
        TRIAL["meaning_ledger"](source, payload)


def test_review_preserves_raw_result_and_blocks_post_generation_corrections(tmp_path):
    result = {"parsed": {"units": []}}
    (tmp_path / "context.result.json").write_text(json.dumps(result), encoding="utf-8")
    payload = tmp_path / "correction.json"
    payload.write_text('{"units":[]}', encoding="utf-8")
    note = tmp_path / "note.md"
    note.write_text("Restored a quantity from source unit 1.", encoding="utf-8")
    TRIAL["freeze_review"](tmp_path, "context", payload, note)
    assert TRIAL["reviewed_payload"](tmp_path, "context") == {"units": []}
    assert json.loads((tmp_path / "context.result.json").read_text()) == result
    (tmp_path / "literal-1.request.json").touch()
    with pytest.raises(ValueError, match="dependent generation"):
        TRIAL["freeze_review"](tmp_path, "context", payload, note)
