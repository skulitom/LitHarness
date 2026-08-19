"""The locus ladder's decomposition, and the exactness that makes it a measurement.

Stage-0 §89's E3 splits the answer distribution at the verdict position into the part that is a
slot preference and the part that is a report on the passages. Two properties make that split
meaningful rather than decorative, and both fail silently:

1. **A byte-identical pair must cancel to exactly zero.** Its two orientations are the same prompt,
   so the text component is `(c + -c)/2 = 0` by construction. Any other value would mean the
   decomposition is measuring floating-point noise rather than a difference, and every ratio in
   the report would be an artifact.
2. **The two components must be orthogonal in the sense the reading claims** — the half-difference
   is invariant to swapping the passages and the half-sum flips sign with them. If they were mixed
   the "4,676x more position than text" reading would be arithmetic rather than evidence.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RESEARCH = Path(__file__).parents[1] / "research" / "quality-measurement"
sys.path.insert(0, str(RESEARCH))

locus = pytest.importorskip(
    "verdict_locus",
    reason="research module; imported by path, skipped where research/ is unavailable",
)


def _raw(splits: dict[str, list[list[float]]]) -> dict:
    return {"families": {
        family: {f"gen:scene-{i}": {"orientation_split": pair, "logit_score": sum(pair) / 2,
                                    "sampled": ["A", "B"], "argmax_is_answer": [True, True]}
                 for i, pair in enumerate(pairs, start=1)}
        for family, pairs in splits.items()
    }}


def test_an_identical_pair_cancels_to_exactly_zero() -> None:
    """The floor that makes the decomposition a measurement rather than a noise estimate."""
    out = locus.decompose(_raw({"placebo_identical": [[0.9, -0.9], [0.4, -0.4], [-0.2, 0.2]]}))
    assert out["placebo_identical"]["mean_abs_text"] == 0.0
    assert out["placebo_identical"]["mean_abs_positional"] == pytest.approx(0.5)
    assert out["placebo_identical"]["ratio"] is None, "a zero denominator reports None, not inf"


def test_the_two_components_separate_position_from_text() -> None:
    """A pure slot preference lands wholly in one component and a pure text signal in the other."""
    pure_position = locus.decompose(_raw({"f": [[0.8, -0.8], [0.8, -0.8]]}))["f"]
    assert pure_position["mean_abs_text"] == 0.0
    assert pure_position["mean_abs_positional"] == pytest.approx(0.8)

    pure_text = locus.decompose(_raw({"f": [[0.3, 0.3], [0.5, 0.5]]}))["f"]
    assert pure_text["mean_abs_positional"] == 0.0
    assert pure_text["mean_abs_text"] == pytest.approx(0.4)


def test_the_pooled_row_is_present_and_carries_its_reading() -> None:
    """The headline number needs its own row; a reader should not have to average the families."""
    out = locus.decompose(_raw({"a": [[1.0, -1.0]], "b": [[0.5, 0.5]]}))
    pooled = out["__pooled__"]
    assert pooled["mean_abs_positional"] == pytest.approx(0.5)
    assert pooled["mean_abs_text"] == pytest.approx(0.25)
    assert pooled["ratio"] == pytest.approx(2.0)
    assert "slot preference" in pooled["reading"]


def test_the_ladder_is_declared_in_survival_order() -> None:
    """The first station at which k falls is a location, and only if the order was fixed first."""
    assert locus.PRE_REGISTRATION["ladder_order"] == [
        "text_mean", "judge_last", "answer_logits", "sampled",
    ]


def test_the_statistic_is_shared_with_the_api_protocols() -> None:
    """The four stations and E1-E6 must not disagree about what counts as a pass."""
    import elicitation_study

    assert locus.exact_two_sided is elicitation_study.exact_two_sided
    assert locus.FAMILY_ALPHA == elicitation_study.FAMILY_ALPHA
    assert locus.required_k(10) == 9
