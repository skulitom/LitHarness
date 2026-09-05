"""Deletion containment, not judgments about prose quality or semantic preservation."""

import runpy
from pathlib import Path

import pytest

TRIAL = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "research/quality-measurement/prose_subtraction.py")
)


def cut(paragraph, quote):
    return {"paragraph": paragraph, "quote": quote, "reason": "Local test."}


def test_cuts_use_original_coordinates_and_preserve_other_paragraphs():
    source = "She moved slowly, like a cloud, towards the gate.\n\nAgain.\n\nThe gate closed."
    result = TRIAL["apply_cuts"](
        source,
        {"cuts": [cut(1, ", like a cloud,"), cut(1, " slowly"), cut(2, "Again.")]},
    )
    assert result == "She moved towards the gate.\n\nThe gate closed."
    assert TRIAL["apply_cuts"](source, {"cuts": []}) == source


@pytest.mark.parametrize(
    "cuts, error",
    [
        ([cut(1, "missing")], "missing"),
        ([cut(1, "the")], "ambiguous"),
        ([cut(1, "the door"), cut(1, "door")], "overlapping"),
        ([cut(2, "door")], "unknown paragraph"),
        ([cut(True, "door")], "unknown paragraph"),
        ([{**cut(1, "door"), "replacement": "gate"}], "malformed"),
    ],
)
def test_cuts_refuse_ambiguous_altered_and_overlapping_sources(cuts, error):
    with pytest.raises(ValueError, match=error):
        TRIAL["apply_cuts"]("the door and the lock", {"cuts": cuts})


def test_overlapping_occurrences_are_ambiguous():
    with pytest.raises(ValueError, match="ambiguous"):
        TRIAL["apply_cuts"]("banana", {"cuts": [cut(1, "ana")]})
