"""The arithmetic under stage-0 §87's Track P, checked rather than asserted.

Three claims in `research/quality-measurement/latent_fixtures.py` are load-bearing enough that
the ledger cites them, and all three are the kind that fail silently — they produce a number, not
an error:

1. The closed form is the leave-one-scene-out refit. `gram`/`signs_from_gram` replace a literal
   per-fold refit over 2,560 dimensions with a `G x G` matrix-vector product, and the whole
   exhaustive null is affordable only because of it. If the algebra were wrong, every p-value in
   `results/latent-taste-probe.json` would be wrong and nothing would raise.
2. The exact null's floor is `2 / 2**G`, not `1 / 2**G`. The statistic is invariant under a
   global sign flip, so the observed assignment always has a twin. The pre-registration written
   before the run declared `1 / 2**G` and was wrong by a factor of two, which made its
   family-wise alpha unattainable at eight scenes; §87 records that rather than repairing it, and
   this test is what makes the corrected figure checkable.
3. A byte-identical pair is unscoreable and must return `k = 0`. That is the floor the whole
   design rests on: a pipeline that separates a string from itself would separate anything.

These run on synthetic data and read nothing from `results/`, so they are hermetic and cost
nothing — the research modules themselves are not importable in CI's environment and are not
imported here.
"""

from __future__ import annotations

import random
import sys
from itertools import product
from pathlib import Path

import pytest

RESEARCH = Path(__file__).parents[1] / "research" / "quality-measurement"
sys.path.insert(0, str(RESEARCH))

latent_fixtures = pytest.importorskip(
    "latent_fixtures",
    reason="research module; imported by path, skipped where research/ is unavailable",
)


def _random_deltas(rng: random.Random, groups: int, width: int) -> list[list[float]]:
    """Paired difference vectors with a weak shared direction, so `k` is neither 0 nor G."""
    return [
        [rng.gauss(0.0, 1.0) + (0.35 if index == 0 else 0.0) for index in range(width)]
        for _ in range(groups)
    ]


def test_closed_form_matches_the_literal_leave_one_scene_out_refit() -> None:
    """`signs_from_gram` and `loso_signs` agree on every flip of every case."""
    rng = random.Random(20260819)
    for _ in range(25):
        groups = rng.choice([4, 5, 6])
        deltas = _random_deltas(rng, groups, rng.choice([3, 12, 40]))
        matrix = latent_fixtures.gram(deltas)
        for flips in product((1, -1), repeat=groups):
            assert latent_fixtures.signs_from_gram(matrix, flips) == latent_fixtures.loso_signs(
                deltas, flips
            )


def test_the_statistic_is_invariant_under_a_global_sign_flip() -> None:
    """Which side is called positive is a naming choice, so the null floor is 2/2**G."""
    rng = random.Random(11)
    for _ in range(50):
        groups = rng.choice([4, 5, 8])
        matrix = latent_fixtures.gram(_random_deltas(rng, groups, 20))
        assert latent_fixtures.signs_from_gram(
            matrix, (1,) * groups
        ) == latent_fixtures.signs_from_gram(matrix, (-1,) * groups)


def test_a_perfectly_separating_family_cannot_beat_the_null_floor() -> None:
    """Even a noiseless separation reports p = 2/2**G — the figure §87 corrects to."""
    groups = 6
    deltas = [[1.0, 0.0] for _ in range(groups)]
    row = latent_fixtures.exact_flip_null(deltas)
    assert row["k"] == groups
    assert row["p_exact"] == pytest.approx(2 / 2**groups)


def test_identical_pairs_are_unscoreable_and_score_zero() -> None:
    """The floor the design rests on: nothing separates a string from itself."""
    deltas = [[0.0, 0.0, 0.0] for _ in range(8)]
    assert latent_fixtures.unscoreable(deltas) == 8
    row = latent_fixtures.exact_flip_null(deltas)
    assert row["k"] == 0
    assert row["p_exact"] == pytest.approx(1.0)


def test_the_byte_identical_placebo_family_really_is_byte_identical() -> None:
    """§85 reported the typo-fix placebo returned unchanged text; the fixtures still say so."""
    families = latent_fixtures.build_families()
    placebo = families[latent_fixtures.IDENTITY_FAMILY]
    assert placebo, "the placebo family should not be empty"
    assert all(pair.positive == pair.negative for pair in placebo)


def test_clopper_pearson_matches_textbook_values() -> None:
    """The interval is bisected by hand, so it is checked against published figures.

    An earlier draft flipped the comparison for the upper bound and returned 0.0 — an interval
    whose top was below its bottom, reported as a number rather than raised as an error.
    """
    assert latent_fixtures.clopper_pearson(18, 25) == pytest.approx((0.5061, 0.8793), abs=5e-4)
    assert latent_fixtures.clopper_pearson(5, 10) == pytest.approx((0.1871, 0.8129), abs=5e-4)
    assert latent_fixtures.clopper_pearson(0, 10) == pytest.approx((0.0, 0.3085), abs=5e-4)
    assert latent_fixtures.clopper_pearson(10, 10) == pytest.approx((0.6915, 1.0), abs=5e-4)


def test_the_conversion_bar_is_attainable_and_the_interval_is_the_binding_half() -> None:
    """§79's 0.52 bar is reachable at both strata sizes; its interval condition is the real one.

    Pins the figures `PRE_REGISTRATION_B4["bar_attainability"]` states, so the claim that the arm
    can pass at all stays checkable — the failure mode stage-0 §87 recorded three times is a bar
    declared in a form its own design could never reach.
    """
    for groups, first_over_bar, first_ci_clear in ((25, 14, 18), (21, 11, 16)):
        assert min(k for k in range(groups + 1) if k / groups > 0.52) == first_over_bar
        assert min(
            k for k in range(groups + 1) if latent_fixtures.clopper_pearson(k, groups)[0] > 0.50
        ) == first_ci_clear
        assert first_ci_clear > first_over_bar, "the interval must be the binding condition"
