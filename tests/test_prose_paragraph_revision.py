"""Patch containment and an explicit counterexample to lexical semantic certification."""

import runpy
from pathlib import Path

import pytest

TRIAL = runpy.run_path(
    str(
        Path(__file__).resolve().parents[1]
        / "research/quality-measurement/prose_paragraph_revision.py"
    )
)


def patch(first, last, paragraphs):
    return {
        "first": first,
        "last": last,
        "paragraphs": paragraphs,
        "reason": "Rearrange this passage.",
        "omitted_or_deferred": [],
    }


def test_paragraph_patches_preserve_untouched_source_and_original_coordinates():
    source = "First.\n\nSecond.\n\nThird.\n\nFourth."
    applied = TRIAL["apply_patches"](
        source, {"patches": [patch(1, 2, ["Combined.", "Another.", "More."]), patch(4, 4, [])]}
    )
    assert applied == "Combined.\n\nAnother.\n\nMore.\n\nThird."
    assert TRIAL["apply_patches"](source, {"patches": []}) == source


@pytest.mark.parametrize(
    "patches",
    [
        [patch(True, 1, ["Wrong."])],
        [patch(0, 1, [])],
        [patch(1, 3, [])],
        [patch(1, 2, ["Whole."]), patch(2, 2, ["Overlap."])],
        [patch(2, 2, ["Later."]), patch(1, 1, ["Earlier."])],
        [patch(1, 1, ["Two.\n\nParagraphs."])],
        [patch(1, 2, [])],
    ],
)
def test_paragraph_patches_refuse_invalid_coordinates_and_ambiguous_paragraphs(patches):
    with pytest.raises(ValueError):
        TRIAL["apply_patches"]("First.\n\nSecond.", {"patches": patches})


def test_information_conditions_share_source_protections_and_editor_role():
    source = {
        "text": "A followed B.\n\nONE.",
        "notes": "No source changes.",
        "protected": [{"id": "F1", "paragraphs": [1], "text": "A follows B."}],
        "verbatim": ["ONE."],
    }
    requests = TRIAL["requests"](source)
    assert requests["full"]["system"] == requests["focused"]["system"]
    assert (
        requests["full"]["prompt"].split("\n\n", 1)[1]
        == requests["focused"]["prompt"].split("\n\n", 1)[1]
    )
    source["protected"][0]["paragraphs"] = [3]
    with pytest.raises(ValueError, match="unknown source"):
        TRIAL["requests"](source)


def test_literal_sequence_checks_order_and_multiplicity_but_not_meaning():
    spans = ["ONE.", "TWO."]
    original = "A followed B today. ONE. TWO. ONE."
    inverted = "B followed A today. ONE. TWO. ONE."
    sequence = TRIAL["literal_sequence"]
    assert sequence(original, spans) == sequence(inverted, spans)
    assert sequence(original, spans) != sequence("ONE. TWO.", spans)
    assert sequence(original, spans) != sequence("TWO. ONE. ONE.", spans)
    assert sorted(original.split()) == sorted(inverted.split())
