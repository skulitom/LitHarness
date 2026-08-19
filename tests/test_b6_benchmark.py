"""The B6 admission, checked against the proposal it admits and against the fixtures it names.

Stage-0 §88 admits three fixture families on the operator's decision. The failure modes here are
all silent — an admission that says one thing while the artifact says another still prints a
table, and a counter that stops ordering its family still returns a number:

1. The admitted membership is the proposed membership. `latent_probe.propose_b6` derived B6 from
   §87's run; if the two drift, an experiment selects instruments on fixtures nobody admitted.
2. Every admitted counter still orders its family in one direction. That is the membership rule,
   and it is a property of the fixtures rather than of the decision — a regenerated fixture could
   break it without touching this module.
3. The positive control is *not* counter-unanimous, and that is recorded rather than repaired.
   `interior_per_1k` falls on one scene of `repair_interiority` because the repair lengthens the
   text; the test pins the exception so a later reader cannot mistake it for a fixture bug.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RESEARCH = Path(__file__).parents[1] / "research" / "quality-measurement"
sys.path.insert(0, str(RESEARCH))

b6 = pytest.importorskip(
    "b6_benchmark",
    reason="research module; imported by path, skipped where research/ is unavailable",
)


def test_the_admission_still_matches_the_proposal_it_admits() -> None:
    """§88 admits §87's artifact, not a name that resembles it."""
    verification = b6.verify_against_proposal()
    if verification["status"] == "ARTIFACT_ABSENT":
        pytest.skip("results/latent-taste-probe.json is not present in this checkout")
    assert verification["status"] == "MATCHES_PROPOSAL", verification["problems"]


def test_every_admitted_counter_orders_its_family_in_one_direction() -> None:
    """The membership rule, re-checked against the fixtures rather than against the decision."""
    for family in b6.MEMBERS:
        signs = {row["sign"] for row in b6.counter_deltas(family) if row["sign"] != 0}
        assert signs == {-1}, f"{family}: counter moves both ways ({signs})"
        assert len(b6.decidable(family)) >= 6, f"{family}: too few decidable pairs to test"


def test_the_structural_tie_is_the_only_undecidable_pair_and_it_is_named() -> None:
    """An unscoreable pair is listed as a scene id, never counted as a miss (§87)."""
    for family in b6.MEMBERS:
        ties = tuple(row["scene"] for row in b6.counter_deltas(family) if row["sign"] == 0)
        assert ties == b6.STRUCTURAL_TIES.get(family, ()), f"{family}: undeclared tie {ties}"


def test_the_positive_control_counter_disagrees_on_exactly_one_scene() -> None:
    """`repair_interiority` is 7 of 8 on its counter and 0.95-1.00 on three judges.

    A per-1k density can fall while the absolute count rises, because §85's repair adds words
    (+11.8%, §87.1) along with the interiority. That is why :data:`b6_benchmark.POSITIVE_CONTROL`
    is scored as a preference and never as a counter alignment — scoring it against its counter
    would import the length confound into the one control that exists to be clean.
    """
    rows = b6.counter_deltas(b6.POSITIVE_CONTROL)
    disagreeing = [row["scene"] for row in rows if row["sign"] < 0]
    assert disagreeing == ["gen:scene-5"], disagreeing
    assert sum(1 for row in rows if row["sign"] > 0) == len(rows) - 1


def test_the_controls_are_not_members_and_the_floor_keeps_its_identical_pairs() -> None:
    """B6 requires a panel failure, so a family the panel decides cannot be a member."""
    assert b6.POSITIVE_CONTROL not in b6.MEMBERS
    assert not set(b6.CONTROLS) & set(b6.MEMBERS)
    identical = b6.control_families()["placebo_identical"]
    assert identical, "the floor must survive drop_degenerate — its identity is the fixture"
    assert all(pair.positive == pair.negative for pair in identical)
