"""Normalize only visible source groups without exposing hidden members or editing text."""

import copy
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
A = runpy.run_path(str(ROOT / "research/quality-measurement/prose_attention_event_ids.py"))
F = runpy.run_path(str(ROOT / "tests/test_prose_attention_events.py"))


def test_attention_id_expansion_uses_actual_visible_members_and_preserves_state_words():
    known = [
        {"id": "F1a", "source_id": "F1"},
        {"id": "F1b", "source_id": "F1"},
        {"id": "F3b", "source_id": "F3"},
    ]
    s = F["state"]("F1")
    s["peripheral"] = ["F3"]
    before = copy.deepcopy((s, known))
    result = A["normalize_visible_refs"](s, known)
    assert result["foreground"] == result["basis"] == ["F1a", "F1b"]
    assert result["peripheral"] == ["F3b"]
    assert "F3a" not in str(result)
    assert result["concern"] == s["concern"] and result["unresolved"] == s["unresolved"]
    assert (s, known) == before


@pytest.mark.parametrize("bad", ["unknown", "collision", "overlap", "too_many"])
def test_attention_id_expansion_fails_closed_for_unsupported_or_ambiguous_cases(bad):
    known = [{"id": "F1a", "source_id": "F1"}]
    s = F["state"]("F1")
    if bad == "unknown":
        s["basis"] = ["F9"]
    elif bad == "collision":
        known.append({"id": "F1", "source_id": "F1"})
    elif bad == "overlap":
        s["peripheral"] = ["F1a"]
    else:
        known += [{"id": f"F1{x}", "source_id": "F1"} for x in ("b", "c", "d")]
    with pytest.raises(ValueError):
        A["normalize_visible_refs"](s, known)
