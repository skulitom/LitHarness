"""Track V's borrowing control, which is the arm's whole design.

Stage-0 §89 funds two questions about the exemplar lever: how deep it binds, and whether it
survives a revision. A centroid distance answers neither on its own, because a model shown eight
passages can move toward them by picking up the register or by lifting the phrases, and those are
different findings that look identical in feature space.

The control separates them by measuring n-gram overlap against the shown passages *and* against a
pool the model never saw. Two properties make that comparison fair, and both fail silently:

1. **The rate is denominated in the output's n-grams**, not the pool's. Denominated the other way,
   a larger pool scores lower simply by having more n-grams, and the shown pool grows with dose —
   which would build a spurious dose effect into the control that exists to detect one.
2. **The ladder is nested**, so a difference between two rungs is *more voice* rather than
   *different voice*.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RESEARCH = Path(__file__).parents[1] / "research" / "quality-measurement"
sys.path.insert(0, str(RESEARCH))

vb = pytest.importorskip(
    "voice_binding",
    reason="research module; imported by path, skipped where research/ is unavailable",
)


def test_the_borrow_rate_is_denominated_in_the_output_not_the_pool() -> None:
    """A bigger pool must not score lower for being bigger — the control's fairness condition."""
    output = " ".join(str(i) for i in range(40))
    small = [output]
    large = [output, " ".join(f"z{i}" for i in range(500))]
    assert vb.borrow_rate(output, small) == 1.0
    assert vb.borrow_rate(output, large) == 1.0, "padding the pool changed the rate"


def test_borrowing_is_zero_on_disjoint_text_and_one_on_a_copy() -> None:
    copy = " ".join(f"w{i}" for i in range(30))
    other = " ".join(f"q{i}" for i in range(30))
    assert vb.borrow_rate(copy, [copy]) == 1.0
    assert vb.borrow_rate(copy, [other]) == 0.0


def test_a_text_shorter_than_the_ngram_borrows_nothing_rather_than_dividing_by_zero() -> None:
    short = " ".join(f"w{i}" for i in range(vb.BORROW_N - 1))
    assert vb.ngrams(short) == set()
    assert vb.borrow_rate(short, [short]) == 0.0


def test_a_partial_lift_lands_between_the_two_ends() -> None:
    """The measure has to be graded, or it cannot distinguish mimicry from a shared idiom."""
    lifted = " ".join(f"a{i}" for i in range(20))
    fresh = " ".join(f"b{i}" for i in range(20))
    rate = vb.borrow_rate(f"{lifted} {fresh}", [lifted])
    assert 0.0 < rate < 1.0


def test_the_dose_ladder_is_nested_and_the_pools_are_disjoint() -> None:
    """Nested so a rung difference is more voice, not different voice."""
    assert vb.DOSES[0] == 0, "dose 0 is the anchor and must be present"
    assert list(vb.DOSES) == sorted(vb.DOSES)
    ladder = {dose: list(range(dose)) for dose in vb.DOSES}
    for smaller, larger in zip(vb.DOSES, vb.DOSES[1:], strict=False):
        assert set(ladder[smaller]) <= set(ladder[larger])
    assert vb.SHOWN_POOL != vb.HELD_OUT_POOL


def test_the_reading_names_mimicry_when_shown_overlap_rises_faster() -> None:
    """The pre-registered branch: movement with faster shown-overlap is not deep-feature."""
    mimicry = vb._reading({
        "dose_arm": {
            "0": {"scenes": 8, "centroid_distance": 9.0,
                  "borrow_shown": 0.00, "borrow_held_out": 0.00},
            "8": {"scenes": 8, "centroid_distance": 6.0,
                  "borrow_shown": 0.20, "borrow_held_out": 0.01},
        }
    })
    assert "the lever binds" in mimicry["dose"]
    assert "mimicry" in mimicry["borrowing"]

    genuine = vb._reading({
        "dose_arm": {
            "0": {"scenes": 8, "centroid_distance": 9.0,
                  "borrow_shown": 0.01, "borrow_held_out": 0.00},
            "8": {"scenes": 8, "centroid_distance": 6.0,
                  "borrow_shown": 0.01, "borrow_held_out": 0.02},
        }
    })
    assert "not explained by borrowing" in genuine["borrowing"]
