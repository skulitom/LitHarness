"""Track E's arithmetic, checked before it is pointed at anything that spends.

Stage-0 §89's statistic is a two-sided exact binomial sign test with its attainable floor declared
beside it. Three of this project's recorded failures were bars written in a form their own design
could never reach (§81's point estimate, §85's zero-width band, §87's sign-flip floor), so the
floor is pinned here rather than asserted in prose:

1. The floor is `2 / 2**G` and alpha 0.05 is unreachable below six pairs. B6's three families
   need k = 9 of 10, 8 of 9 and 7 of 7, and the last has no margin at all.
2. The Fisher exact used for E6 matches `scipy.stats.fisher_exact(alternative="greater")`. The
   values are pinned rather than bounded; scipy is not a dependency of this suite, so they were
   taken under the MirrorBench interpreter and are recorded as constants here.
3. E6 is not scored by the shared sign test, and the reason is a property of the statistic: a
   two-sided test rewards consistent silence exactly as much as consistent naming, so a matcher
   that never fires would read `k = G` and pass.
"""

from __future__ import annotations

import pytest

study = pytest.importorskip(
    "elicitation_study",
    reason="research module; imported by path, skipped where research/ is unavailable",
)


def test_the_attainable_floor_is_declared_and_reachable_for_every_b6_family() -> None:
    """§87's rule, applied before the run instead of after it."""
    for groups, needed in ((10, 9), (9, 8), (7, 7)):
        assert study.required_k(groups) == needed
        assert study.attainable_p(groups) <= study.FAMILY_ALPHA
    assert study.required_k(5) is None, "alpha 0.05 is unreachable at five pairs"
    assert study.required_k(6) == 6, "six pairs clear only on a perfect six"
    # `repair_emdash` sits one pair above the cliff and clears only on a perfect seven.
    assert study.attainable_p(7) == pytest.approx(0.015625)
    assert study.exact_two_sided(6, 7) > study.FAMILY_ALPHA


def test_the_sign_test_is_two_sided_and_symmetric() -> None:
    """B6 certifies that a difference exists, never which side of it is better."""
    for groups in range(6, 12):
        for k in range(groups + 1):
            assert study.exact_two_sided(k, groups) == study.exact_two_sided(groups - k, groups)
    assert study.exact_two_sided(5, 10) == 1.0
    assert study.attainable_p(8) == 2 / 2**8


def test_fisher_exact_matches_scipy_on_pinned_tables() -> None:
    """E6's null is measured, so its test has to be the exact one it claims to be.

    Checked against `scipy.stats.fisher_exact(..., alternative="greater")` under the MirrorBench
    interpreter, which has scipy; this suite does not, so the reference values are constants.
    """
    for table, expected in (
        ((5, 5, 5, 5), 0.6718591007),
        ((10, 0, 0, 10), 0.0000054125),
        ((8, 2, 3, 17), 0.0009742382),
        ((7, 1, 2, 20), 0.0001307039),
        ((12, 4, 5, 30), 0.0000420380),
        ((0, 10, 10, 0), 1.0),
    ):
        assert study.fisher_exact_greater(*table) == pytest.approx(expected, abs=1e-9)


def test_a_matcher_that_never_fires_would_pass_the_shared_sign_test() -> None:
    """Why E6 is scored by Fisher and not by the sign test the other five protocols share.

    This is the defect the dry run surfaced before any response existed. Scoring a pair by whether
    its matcher fired and testing that count two-sided credits a protocol that names the axis on
    no pair at all, because `k` is the larger of the two counts by construction.
    """
    silent = {f"gen:scene-{i}": -1 for i in range(1, 11)}
    reading = study.family_reading("stat_flatten", silent)
    assert reading["verdict"] == "CLEARS", "the shared statistic really would pass total silence"
    assert reading["direction"] == "negative_side"


def test_a_tie_leaves_the_denominator_rather_than_counting_as_a_miss() -> None:
    """An undecided pair is not a failed pair. §87's structural-tie rule, in the scorer."""
    signs = {f"gen:scene-{i}": 1 for i in range(1, 9)}
    signs["gen:scene-9"] = 0
    signs["gen:scene-10"] = 0
    reading = study.family_reading("stat_flatten", signs)
    assert reading["decided_pairs"] == 8
    assert reading["undecided_pairs"] == ["gen:scene-10", "gen:scene-9"]
    assert reading["aligned"] == 8


def test_a_family_below_the_floor_reports_not_attainable_and_not_fails() -> None:
    """§87.3's `NOT_SCREENABLE` distinction, declared in advance this time."""
    signs = {f"gen:scene-{i}": (1 if i <= 5 else 0) for i in range(1, 11)}
    reading = study.family_reading("stat_flatten", signs)
    assert reading["decided_pairs"] == 5
    assert reading["verdict"] == "NOT_ATTAINABLE"


def test_the_decided_floor_blocks_a_band_being_read_off_too_few_decisions() -> None:
    """§86.7's floor. §87.3 read 1.000 off eleven decisions and had to say so beside the number."""
    thin = [
        _comparison(pair=f"p{i}", choice="A", orientation=i % 2) for i in range(11)
    ]
    reading = study.bias_reading(thin, has_slot=True)
    assert reading["precondition"] == "INSUFFICIENT_DECIDED"
    assert reading["decided"] == 11
    wide = [_comparison(pair=f"p{i}", choice="AB"[i % 2], orientation=i % 2) for i in range(40)]
    assert study.bias_reading(wide, has_slot=True)["precondition"] == "IN_BAND"


def test_a_protocol_with_no_slot_says_so_rather_than_passing_vacuously() -> None:
    """E4 shows one passage at a time. A precondition it cannot fail is not a precondition."""
    reading = study.bias_reading([], has_slot=False)
    assert reading["precondition"] == "NO_SLOT"
    assert "chose_A_rate" not in reading


def test_a_separating_control_voids_the_protocol_before_any_family_is_read() -> None:
    """Order matters: a protocol that separates a string from itself has no readable families."""
    clears = [study.family_reading("stat_flatten", {f"s{i}": 1 for i in range(10)})]
    broken = [study.control_reading("placebo_identical", {f"s{i}": 1 for i in range(8)})]
    verdict = study.protocol_verdict(clears, broken, {"precondition": "IN_BAND"})
    assert verdict["verdict"] == "VOID"
    assert "placebo_identical" in verdict["because"]


def _comparison(*, pair: str, choice: str, orientation: int) -> object:
    from elicit import Comparison

    return Comparison(
        pair_id=pair, persona_id="grinder", sample=0, model="test",
        orientation=orientation, choice=choice, reason_code="curious", refused=False, usage={},
    )
