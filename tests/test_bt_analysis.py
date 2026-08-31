"""The registered arithmetic over stage-2 answers, checked without calls.

What this file pins: the three-way score (`correct`, both orders, neither never scored), the §6
aggregate's majority/tie/neither/restriction behaviour, the pair bootstrap's determinism,
sub-ten refusal, and both sides of 0.5, the positional rate on an orchestrated bias, the sham
floor's refusal to pool, the label shuffle's replay determinism and its near-alpha/2 behaviour
on a fair-coin null, the descriptive health signature's verdict-free shape, and one constructed
scenario per named outcome of the §9 rule including its documented precedence. Every expected
number is stated in the test and derived by hand before anything runs. What this does not
establish: anything about any model's answers — no vote here was produced by a call.

Added with PREREG's post-hoc amendment of 2026-08-31: the sham guard's boundary (a two-vote
sham excluded, a six-vote sham kept, the floor recomputed), the constant pinned to the
unanimity arithmetic that chose it, the guard's structural direction (it can only lower a
floor), the amended-only `void_sham_unmeasured` outcome and the registered rule's inability to
reach it, and the honesty check that the guard does **not** clear the pilot's own sham void.
"""

from __future__ import annotations

import sys
from pathlib import Path
from random import Random

sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "research" / "sim-readership-backtest")
)
import pytest

analysis = pytest.importorskip("analysis", reason="research module; imported by path")


def _vote(
    pair: str = "p1",
    persona: str = "r1",
    order: int = 1,
    choice: str = "A",
    high: str = "A",
    reason: str = "keeps_reading",
) -> analysis.Vote:
    """One hand-built stage-2 answer; defaults describe 'persona r1 continues slot A'."""
    return analysis.Vote(
        pair_id=pair,
        arm="C",
        persona_id=persona,
        order=order,
        choice=choice,
        reason=reason,
        high_was=high,
    )


def _clean_controls(largest_true_effect: float = 0.05) -> dict[str, object]:
    """Control records that fire nothing: no decided votes (rate None), no shams (floor 0.0),
    and a shuffle that never cleared."""
    return {
        "largest_true_effect": largest_true_effect,
        "positional": analysis.positional_rate([]),
        "sham": analysis.sham_floor({}),
        "shuffle": {"draws": 200, "clears": 0, "clear_share": 0.0},
    }


STRONG_PRIMARY = [1] * 200  # 200 decided pairs, every aggregate prediction right
WEAK_PRIMARY = [1, 0] * 100  # 200 decided pairs, chance-level
DAMAGE_OK = [1] * 20  # the panel sees gross damage everywhere
DAMAGE_BLIND = [1, 0] * 10  # the panel cannot see damage above chance


# ------------------------------------------------------------------------------- the score


def test_correct_is_true_when_the_choice_names_the_higher_slot_in_both_orders() -> None:
    assert analysis.correct(_vote(choice="A", high="A")) is True
    assert analysis.correct(_vote(order=2, choice="B", high="B")) is True


def test_correct_is_false_when_the_choice_names_the_lower_slot_in_both_orders() -> None:
    assert analysis.correct(_vote(choice="B", high="A")) is False
    assert analysis.correct(_vote(order=2, choice="A", high="B")) is False


def test_a_neither_choice_is_never_scored_whichever_slot_was_higher() -> None:
    assert analysis.correct(_vote(choice="neither", high="A")) is None
    assert analysis.correct(_vote(choice="neither", high="B")) is None


# ------------------------------------------------------------------------ PREREG §6 aggregate


def test_the_majority_side_is_predicted_with_its_unweighted_share() -> None:
    # Four decided votes on p1, three naming slot A: prediction A, shares 3/4 and 1/4.
    votes = [
        _vote(pair="p1", persona="r1", order=1, choice="A", high="A"),
        _vote(pair="p1", persona="r1", order=2, choice="A", high="B"),
        _vote(pair="p1", persona="r2", order=1, choice="A", high="A"),
        _vote(pair="p1", persona="r3", order=1, choice="B", high="B"),
    ]
    got = analysis.aggregate_by_pair(votes, {"r1", "r2", "r3"})
    pair = got["pairs"]["p1"]
    assert pair["predicted"] == "A"
    assert pair["decided"] is True
    assert pair["a_votes"] == 3 and pair["b_votes"] == 1
    assert pair["a_share"] == pytest.approx(0.75)
    assert pair["b_share"] == pytest.approx(0.25)
    assert pair["n_decided"] == 4
    assert got["n_pairs"] == 1
    assert got["n_decided_pairs"] == 1
    assert got["n_undecided_pairs"] == 0


def test_a_tied_pair_is_undecided_and_counted_as_such() -> None:
    # Two personas x two orders, split 2-2: no majority, so no prediction.
    votes = [
        _vote(persona="r1", order=1, choice="A", high="A"),
        _vote(persona="r1", order=2, choice="B", high="B"),
        _vote(persona="r2", order=1, choice="B", high="B"),
        _vote(persona="r2", order=2, choice="A", high="A"),
    ]
    got = analysis.aggregate_by_pair(votes, {"r1", "r2"})
    assert got["pairs"]["p1"]["predicted"] is None
    assert got["pairs"]["p1"]["decided"] is False
    assert got["pairs"]["p1"]["a_share"] == pytest.approx(0.5)
    assert got["n_decided_pairs"] == 0
    assert got["n_undecided_pairs"] == 1


def test_a_pair_with_no_decided_votes_is_undecided_but_counts_its_neithers() -> None:
    # Everyone abandons both books: undecided pair, four recorded neithers.
    votes = [_vote(choice="neither") for _ in range(4)]
    got = analysis.aggregate_by_pair(votes, {"r1"})
    assert got["pairs"]["p1"]["predicted"] is None
    assert got["pairs"]["p1"]["neither"] == 4
    assert got["n_undecided_pairs"] == 1


def test_neither_votes_are_excluded_from_the_side_counts_but_stay_in_the_tally() -> None:
    # Two continue-A votes and two abandon-both votes: A wins among the decided only.
    votes = [
        _vote(choice="A"),
        _vote(persona="r2", order=2, choice="A", high="B"),
        _vote(persona="r3", choice="neither"),
        _vote(persona="r4", choice="neither"),
    ]
    got = analysis.aggregate_by_pair(votes, {"r1", "r2", "r3", "r4"})
    pair = got["pairs"]["p1"]
    assert pair["predicted"] == "A"
    assert pair["a_share"] == 1.0
    assert pair["neither"] == 2
    assert pair["n_decided"] == 2


def test_a_holdout_personas_votes_do_not_move_the_reward_split_aggregate() -> None:
    # Reward personas r1-r3 vote 3-1 for A; holdout persona h votes B three times. Restricted
    # to the reward ids the prediction stays A; letting h in would flip it to B, which is
    # exactly what the restriction exists to prevent (PREREG §6: only the reward decides).
    reward = [
        _vote(persona="r1", order=1, choice="A"),
        _vote(persona="r1", order=2, choice="B", high="B"),
        _vote(persona="r2", order=1, choice="A"),
        _vote(persona="r3", order=1, choice="A"),
    ]
    holdout = [
        _vote(persona="h", order=1, choice="B"),
        _vote(persona="h", order=2, choice="B"),
        _vote(persona="h", order=1, choice="B"),
    ]
    restricted = analysis.aggregate_by_pair(reward + holdout, {"r1", "r2", "r3"})
    assert restricted["pairs"]["p1"]["predicted"] == "A"
    unrestricted = analysis.aggregate_by_pair(reward + holdout, {"r1", "r2", "r3", "h"})
    assert unrestricted["pairs"]["p1"]["predicted"] == "B"
    # The neither-rate table speaks only for the given personas; h is absent when uninvited.
    assert "h" not in restricted["neither_rate_by_persona"]
    assert set(restricted["neither_rate_by_persona"]) == {"r1", "r2", "r3"}


def test_the_per_persona_neither_rate_is_the_hand_computed_fraction() -> None:
    # r1 answers four times, once with neither: rate 0.25. r2 never abandons: 0.0.
    votes = [
        _vote(pair="p1", persona="r1", choice="neither"),
        _vote(pair="p2", persona="r1", choice="A"),
        _vote(pair="p3", persona="r1", choice="B", high="B"),
        _vote(pair="p4", persona="r1", choice="A"),
        _vote(pair="p1", persona="r2", choice="A"),
        _vote(pair="p2", persona="r2", choice="A"),
    ]
    rates = analysis.aggregate_by_pair(votes, {"r1", "r2"})["neither_rate_by_persona"]
    assert rates["r1"] == pytest.approx(0.25)
    assert rates["r2"] == 0.0


# --------------------------------------------------------------- the primary interval (§9)


def test_the_same_outcome_vector_yields_the_same_bound_bit_for_bit() -> None:
    outcomes = [1, 0, 1, 1, 0, 1, 1, 1, 0, 1, 1, 0]
    first = analysis.pair_bootstrap_lower_bound(outcomes)
    again = analysis.pair_bootstrap_lower_bound(outcomes)
    assert first == again
    assert 0.0 <= first <= 1.0


def test_fewer_than_ten_outcomes_is_refused_by_name_not_bounded() -> None:
    with pytest.raises(ValueError, match="below the registered minimum"):
        analysis.pair_bootstrap_lower_bound([1] * 9)
    with pytest.raises(ValueError, match="below the registered minimum"):
        analysis.pair_bootstrap_lower_bound([])


def test_exactly_ten_outcomes_sits_on_the_accepted_side_of_the_refusal() -> None:
    assert analysis.pair_bootstrap_lower_bound([1] * 10) == 1.0


def test_an_all_correct_vector_clears_half_at_the_top_of_the_scale() -> None:
    # Every resample of twenty ones has mean 1.0, so the 2.5th percentile is 1.0 exactly.
    assert analysis.pair_bootstrap_lower_bound([1] * 20) == 1.0 > 0.5


def test_an_alternating_chance_level_vector_does_not_clear_half() -> None:
    # Ten correct, ten wrong: resample means scatter around 0.5 and the alpha/2 percentile
    # lands at or below it — chance does not clear chance.
    assert analysis.pair_bootstrap_lower_bound([1, 0] * 10) <= 0.5


# ------------------------------------------------------------------------- control quantities


def test_the_first_position_rate_measures_an_orchestrated_slot_a_bias() -> None:
    # Ten decided votes, eight naming slot A: rate 0.8. Order 1 holds four votes (3 A -> 0.75),
    # order 2 six (5 A -> 5/6). Two abandon-both votes never enter any of it.
    votes = [
        _vote(persona="r1", order=1, choice="A"),
        _vote(persona="r2", order=1, choice="A"),
        _vote(persona="r3", order=1, choice="B"),
        _vote(persona="r4", order=1, choice="A"),
        _vote(persona="r1", order=2, choice="A"),
        _vote(persona="r2", order=2, choice="A"),
        _vote(persona="r3", order=2, choice="A"),
        _vote(persona="r4", order=2, choice="B"),
        _vote(persona="r5", order=2, choice="A"),
        _vote(persona="r6", order=2, choice="A"),
        _vote(persona="r3", order=1, choice="neither"),
        _vote(persona="r4", order=2, choice="neither"),
    ]
    got = analysis.positional_rate(votes)
    assert got["n"] == 10
    assert got["rate"] == pytest.approx(0.8)
    assert got["by_order"] == {
        1: {"rate": pytest.approx(0.75), "n": 4},
        2: {"rate": pytest.approx(5 / 6), "n": 6},
    }


def test_no_decided_votes_gives_a_null_positional_record_without_crashing() -> None:
    assert analysis.positional_rate([]) == {"rate": None, "n": 0, "by_order": {}}
    only_neither = [_vote(choice="neither"), _vote(persona="r2", choice="neither")]
    assert analysis.positional_rate(only_neither)["rate"] is None


def test_one_loud_sham_sets_the_floor_over_quiet_ones_and_pooling_would_hide_it() -> None:
    # Hand-derived per-sham deviations: quiet 2A/2B -> |0.5-0.5| = 0.0; mild 6A/4B ->
    # |0.6-0.5| = 0.1; loud 9A/1B -> |0.9-0.5| = 0.4. The floor reads the loud sham alone.
    # Pooled across all twenty-four decided votes the deviation would be |17/24 - 0.5| ~= 0.21,
    # which would bury the loud sham — the K2 form forbids that pooling.
    by_sham = {
        "sham-quiet": [
            _vote(pair="q1"),
            _vote(pair="q2"),
            _vote(pair="q3", choice="B"),
            _vote(pair="q4", choice="B"),
        ],
        "sham-mild": [_vote(pair=f"m{i}") for i in range(6)]
        + [_vote(pair=f"m{i}", choice="B") for i in range(4)],
        "sham-loud": [_vote(pair=f"l{i}") for i in range(9)]
        + [_vote(pair="l0", choice="B")],
    }
    got = analysis.sham_floor(by_sham)
    assert got["per_sham"]["sham-quiet"]["deviation"] == pytest.approx(0.0)
    assert got["per_sham"]["sham-mild"]["deviation"] == pytest.approx(0.1)
    assert got["per_sham"]["sham-loud"]["deviation"] == pytest.approx(0.4)
    assert got["floor"] == pytest.approx(0.4)
    pooled = abs(17 / 24 - 0.5)
    assert pooled < got["floor"], "pooling would dilute the loud sham"


def test_shams_with_no_decided_votes_cannot_set_the_floor() -> None:
    # No shams at all: floor 0.0. A sham whose panel abandoned both windows has no defined
    # deviation (None) and raises no floor.
    empty = analysis.sham_floor({})
    assert empty == {"floor": 0.0, "min_decided": 0, "n_qualifying": 0, "per_sham": {}}
    abandoned = analysis.sham_floor(
        {"sham-silent": [_vote(choice="neither"), _vote(persona="r2", choice="neither")]}
    )
    assert abandoned["per_sham"]["sham-silent"]["deviation"] is None
    assert abandoned["per_sham"]["sham-silent"]["n_decided"] == 0
    assert abandoned["per_sham"]["sham-silent"]["counts_toward_floor"] is False
    assert abandoned["floor"] == 0.0
    assert abandoned["n_qualifying"] == 0


# ------------------------------------------------- the amended sham guard (post-hoc, 2026-08-31)


def _sham(votes_for_a: int, votes_for_b: int, *, neither: int = 0) -> list[analysis.Vote]:
    """One sham's votes with a hand-chosen decided split, plus optional abandonments."""
    return (
        [_vote(persona=f"a{i}") for i in range(votes_for_a)]
        + [_vote(persona=f"b{i}", choice="B") for i in range(votes_for_b)]
        + [_vote(persona=f"n{i}", choice="neither") for i in range(neither)]
    )


def test_the_minimum_decided_n_is_exactly_its_unanimity_arithmetic_and_not_a_round_number() -> (
    None
):
    """The constant is pinned to the argument that chose it, so it cannot drift into taste.

    Under the sham's own null the per-sham statistic reaches its maximum (0.5, unanimity) with
    probability 2**(1-n). The registered ALPHA is the line: the minimum is the smallest n whose
    unanimity probability sits at or under it, and the n below must fail.
    """
    n = analysis.SHAM_MIN_DECIDED
    assert 2 ** (1 - n) <= analysis.ALPHA, "the chosen minimum must clear alpha"
    assert 2 ** (1 - (n - 1)) > analysis.ALPHA, "one vote fewer must not clear it"
    assert (2 ** (1 - 5), 2 ** (1 - 6)) == (0.0625, 0.03125)
    assert n == 6


def test_a_two_vote_sham_is_kept_in_the_record_but_cannot_set_the_amended_floor() -> None:
    """The boundary, hand-derived: 2 decided votes attain only {0, 0.5} — resolution, not
    deviation — so a 2-0 sham reads 0.5 under the registered rule and is excluded from the
    amended one. The 6-vote sham at 5A/1B (deviation |5/6 - 1/2| = 0.3333) qualifies and
    becomes the amended floor. Nothing is deleted: the excluded sham keeps its deviation."""
    by_sham = {"sham-tiny": _sham(2, 0), "sham-six": _sham(5, 1)}

    registered = analysis.sham_floor(by_sham)
    assert registered["floor"] == pytest.approx(0.5)
    assert registered["min_decided"] == 0 and registered["n_qualifying"] == 2

    amended = analysis.sham_floor(by_sham, min_decided=analysis.SHAM_MIN_DECIDED)
    assert amended["floor"] == pytest.approx(1 / 3)
    assert amended["n_qualifying"] == 1
    assert amended["per_sham"]["sham-tiny"]["counts_toward_floor"] is False
    assert amended["per_sham"]["sham-tiny"]["deviation"] == pytest.approx(0.5), (
        "an excluded sham keeps its measured deviation on the record"
    )
    assert amended["per_sham"]["sham-six"]["counts_toward_floor"] is True


def test_the_guard_counts_decided_votes_only_so_abandonments_never_buy_qualification() -> None:
    """Twenty votes of which five are decided is a five-vote sham: "neither" is undecided
    everywhere else in this module and cannot be spent here to reach the minimum."""
    by_sham = {"sham-loud-but-thin": _sham(5, 0, neither=15)}
    amended = analysis.sham_floor(by_sham, min_decided=analysis.SHAM_MIN_DECIDED)
    assert amended["per_sham"]["sham-loud-but-thin"]["n_decided"] == 5
    assert amended["per_sham"]["sham-loud-but-thin"]["counts_toward_floor"] is False
    assert amended["floor"] == 0.0 and amended["n_qualifying"] == 0


def test_the_amended_floor_can_only_be_lower_than_the_registered_one() -> None:
    """The amendment's structural bias, asserted rather than argued: removing cells from a
    maximum can only lower it. Stated in PREREG §A.4(3) so a reader discounts it; pinned here
    so no later edit can quietly make the guard raise a floor instead."""
    by_sham = {
        "s2": _sham(2, 0),  # 0.5, excluded
        "s5": _sham(4, 1),  # 0.3, excluded
        "s9": _sham(8, 1),  # 0.3889, kept
        "s12": _sham(6, 6),  # 0.0, kept
    }
    registered = analysis.sham_floor(by_sham)["floor"]
    amended = analysis.sham_floor(by_sham, min_decided=analysis.SHAM_MIN_DECIDED)["floor"]
    assert amended <= registered
    assert registered == pytest.approx(0.5)
    assert amended == pytest.approx(8 / 9 - 0.5)


# ------------------------------------------------------------------------- the C3 label shuffle


def test_label_shuffle_replays_identically_under_the_same_seed_material() -> None:
    outcomes = [1, 1, 0, 1, 0, 0, 1, 1, 0, 1, 1, 0]
    first = analysis.label_shuffle(outcomes, seed_material="bt-null", draws=5)
    again = analysis.label_shuffle(outcomes, seed_material="bt-null", draws=5)
    assert first == again
    assert set(first) == {"draws", "clears", "clear_share"}
    assert first["draws"] == 5
    assert 0 <= first["clears"] <= first["draws"]
    assert first["clear_share"] == pytest.approx(first["clears"] / first["draws"])


@pytest.mark.intensive
def test_a_fair_coin_null_vector_clears_half_rarely_well_under_three_alpha() -> None:
    # Two hundred fair-coin outcomes (deterministic coin, seed pinned): under the null the
    # bootstrap lower bound clears 0.5 about alpha/2 of the time, so the clear-share should sit
    # near 0.025 — asserted only as < 3 * alpha, never as an exact value.
    rng = Random(20260824)
    null_outcomes = [rng.choice((0, 1)) for _ in range(200)]
    got = analysis.label_shuffle(null_outcomes, seed_material="registered-null", draws=200)
    assert got["clear_share"] < 3 * analysis.ALPHA


def test_a_short_vector_is_refused_before_any_draw_of_the_shuffle() -> None:
    with pytest.raises(ValueError, match="below the registered minimum"):
        analysis.label_shuffle([1, 0] * 4, seed_material="too-short")


def test_a_non_binary_outcome_is_refused_by_name() -> None:
    with pytest.raises(ValueError, match="outcomes must be 0/1"):
        analysis.label_shuffle([2] * 12, seed_material="bad-bits")


# ------------------------------------------------------------------------- §120 health signature


def test_the_signature_reports_per_persona_accuracy_and_deviation_and_no_verdict() -> None:
    # Damage pairs D1/D2: p1 scores both (accuracy 1.0 over 2), p2 scores one of two
    # (convergence vs scatter is for the reader to see; nothing here judges it). Sham S1:
    # p1 picks A in three of four decided votes (deviation |0.75-0.5| = 0.25), p2 splits
    # 1-1 (deviation 0.0). A third persona's neither on a damage pair is unscored, so p3
    # appears nowhere. The record carries exactly the two descriptive tables.
    votes = [
        _vote(pair="D1", persona="p1", choice="A", high="A"),
        _vote(pair="D2", persona="p1", choice="B", high="B"),
        _vote(pair="D1", persona="p2", choice="B", high="A"),
        _vote(pair="D2", persona="p2", choice="B", high="B"),
        _vote(pair="D1", persona="p3", choice="neither"),
        _vote(pair="S1", persona="p1", choice="A"),
        _vote(pair="S1", persona="p1", order=2, choice="A", high="B"),
        _vote(pair="S1", persona="p1", choice="A", high="B"),
        _vote(pair="S1", persona="p1", order=3, choice="B"),
        _vote(pair="S1", persona="p2", choice="A"),
        _vote(pair="S1", persona="p2", order=2, choice="B", high="B"),
    ]
    got = analysis.health_signature(votes, {"D1", "D2"}, {"S1"})
    assert set(got) == {"damage", "sham"}
    assert got["damage"]["p1"] == {"accuracy": pytest.approx(1.0), "n_decided": 2}
    assert got["damage"]["p2"] == {"accuracy": pytest.approx(0.5), "n_decided": 2}
    assert "p3" not in got["damage"]
    assert got["sham"]["p1"] == {"deviation": pytest.approx(0.25), "n_decided": 4}
    assert got["sham"]["p2"] == {"deviation": pytest.approx(0.0), "n_decided": 2}
    assert "verdict" not in str(sorted(got))


def test_an_empty_vote_set_gives_an_empty_signature_without_crashing() -> None:
    assert analysis.health_signature([], {"D1"}, {"S1"}) == {"damage": {}, "sham": {}}


# ------------------------------------------------------------------------- §9 decision rule


def test_insufficient_n_fires_before_any_void_when_the_primary_is_under_target() -> None:
    # 150 all-correct pairs would qualify on its bound if it were confirmatory — it is not,
    # because 150 < n_target. Precedence rule one: an arm below target has no look to void.
    controls = _clean_controls()
    got = analysis.verdicts(
        [1] * 150,
        largest_true_effect=0.05,
        positional=controls["positional"],
        sham=controls["sham"],
        shuffle=controls["shuffle"],
        damage_outcomes=DAMAGE_OK,
        n_target=200,
    )
    assert got["verdict"] == "insufficient_n"
    assert got["fired"] == ["insufficient_n"]
    assert got["primary_lower_bound"] == 1.0  # still computed and recorded beside the verdict


def test_void_positional_fires_despite_a_perfect_primary_bound() -> None:
    # Ten decided votes with eight naming slot A: deviation 0.3 >= effect 0.25, so the panel's
    # slot preference alone could explain the result — the arm is void even at bound 1.0.
    biased = [_vote(pair=f"b{i}", choice="A") for i in range(8)] + [
        _vote(pair="b8", choice="B"),
        _vote(pair="b9", choice="B"),
    ]
    controls = _clean_controls()
    got = analysis.verdicts(
        STRONG_PRIMARY,
        largest_true_effect=0.25,
        positional=analysis.positional_rate(biased),
        sham=controls["sham"],
        shuffle=controls["shuffle"],
        damage_outcomes=DAMAGE_OK,
    )
    assert got["verdict"] == "void_positional"
    assert got["fired"] == ["void_positional"]
    assert got["positional_deviation"] == pytest.approx(0.3)
    assert got["primary_lower_bound"] == 1.0


def test_void_sham_fires_when_the_floor_reaches_larger_than_the_true_effect() -> None:
    # One sham with nine A picks and one B: floor |0.9 - 0.5| = 0.4 >= effect 0.3.
    loud = {"sham-loud": [_vote(choice="A") for _ in range(9)] + [_vote(choice="B")]}
    controls = _clean_controls()
    got = analysis.verdicts(
        STRONG_PRIMARY,
        positional=controls["positional"],
        sham=analysis.sham_floor(loud),
        shuffle=controls["shuffle"],
        largest_true_effect=0.3,
        damage_outcomes=DAMAGE_OK,
    )
    assert got["verdict"] == "void_sham"
    assert got["sham_floor"] == pytest.approx(0.4)


def test_an_amended_floor_with_no_qualifying_sham_voids_instead_of_passing() -> None:
    """A floor of 0.0 has two meanings and only one of them is a pass.

    Every sham under the minimum: the amended floor is 0.0, which would sail past a
    `floor >= effect` comparison as though twelve shams had all sat at chance. The record
    says `n_qualifying: 0`, and the rule reads it — a control that did not measure cannot
    certify. This outcome is reachable only on the amended path.
    """
    thin = {f"sham-{i}": _sham(2, 0) for i in range(3)}
    amended = analysis.sham_floor(thin, min_decided=analysis.SHAM_MIN_DECIDED)
    assert amended["floor"] == 0.0 and amended["n_qualifying"] == 0
    controls = _clean_controls()
    got = analysis.verdicts(
        STRONG_PRIMARY,
        positional=controls["positional"],
        sham=amended,
        shuffle=controls["shuffle"],
        largest_true_effect=0.3,
        damage_outcomes=DAMAGE_OK,
    )
    assert got["verdict"] == "void_sham_unmeasured"
    assert got["sham_min_decided"] == analysis.SHAM_MIN_DECIDED
    assert got["sham_n_qualifying"] == 0


def test_the_registered_rule_cannot_reach_the_amended_void_at_all() -> None:
    """The registration set no minimum, so `void_sham_unmeasured` is unreachable from it:
    the same thin shams, read under the default, set a floor of 0.5 and void the ordinary
    way. The amendment adds an outcome to one path without touching the other."""
    thin = {f"sham-{i}": _sham(2, 0) for i in range(3)}
    registered = analysis.sham_floor(thin)
    assert registered["min_decided"] == 0 and registered["n_qualifying"] == 3
    controls = _clean_controls()
    got = analysis.verdicts(
        STRONG_PRIMARY,
        positional=controls["positional"],
        sham=registered,
        shuffle=controls["shuffle"],
        largest_true_effect=0.3,
        damage_outcomes=DAMAGE_OK,
    )
    assert got["verdict"] == "void_sham"
    assert got["sham_floor"] == pytest.approx(0.5)


def test_the_guard_does_not_clear_the_pilots_sham_void_on_the_pilots_own_table() -> None:
    """PREREG §A.4(1)'s honesty check, in code, on the re-pilot's twelve shams.

    The votes are reconstructed from `result-pilot.json`'s per-sham (n_decided, share) table —
    2/5/5/6/7/8/9/9/12/12/13/14 decided — so the arithmetic is the pilot's, not an invention.
    The registered floor is 0.5 off the two-vote sham; the amended floor is 0.3889 off the
    nine-vote one; the pilot's primary effect was 0.2895. **Both floors exceed it**, so the
    guard is not what would clear anything, and a test fails if anyone later writes that it is.
    """
    pilot = {  # (votes for A, votes for B) per sham, ordered by decided n
        "sham-103284": (2, 0), "sham-111442": (4, 1), "sham-113516": (4, 1),
        "sham-100771": (4, 2), "sham-102074": (4, 3), "sham-103379": (4, 4),
        "sham-103788": (8, 1), "sham-112338": (5, 4), "sham-102842": (6, 6),
        "sham-114617": (4, 8), "sham-108845": (10, 3), "sham-103872": (10, 4),
    }
    by_sham = {sham_id: _sham(a, b) for sham_id, (a, b) in pilot.items()}
    assert sum(a + b for a, b in pilot.values()) == 102, "the pilot's decided sham votes"

    registered = analysis.sham_floor(by_sham)
    amended = analysis.sham_floor(by_sham, min_decided=analysis.SHAM_MIN_DECIDED)
    pilot_primary_effect = abs(15 / 19 - 0.5)  # 15 of 19 decided pairs, |acc - 0.5|

    assert registered["floor"] == pytest.approx(0.5)
    assert registered["n_qualifying"] == 12
    assert amended["floor"] == pytest.approx(8 / 9 - 0.5)  # 0.3889, sham-103788 at n=9
    assert amended["n_qualifying"] == 9, "three shams fall under the minimum: n = 2, 5, 5"
    assert pilot_primary_effect == pytest.approx(0.2894736842105263)
    assert amended["floor"] > pilot_primary_effect, (
        "the amended floor still voids the pilot's sham arm; fresh draws at stage (c), not "
        "this guard, are what could change the corner"
    )


def test_void_shuffle_fires_when_the_clear_share_exceeds_three_alpha_halves() -> None:
    # A null that clears 0.5 on 10% of draws (> 3 * alpha/2 = 7.5%) means the analysis path
    # leaks the label; everything downstream is void regardless of the primary.
    controls = _clean_controls()
    got = analysis.verdicts(
        STRONG_PRIMARY,
        positional=controls["positional"],
        sham=controls["sham"],
        shuffle={"draws": 200, "clears": 20, "clear_share": 0.1},
        largest_true_effect=0.05,
        damage_outcomes=DAMAGE_OK,
    )
    assert got["verdict"] == "void_shuffle"
    assert got["shuffle_clear_share"] == pytest.approx(0.1)


def test_a_clear_share_exactly_at_three_alpha_halves_is_not_a_shuffle_void() -> None:
    # The registered comparison is strict: AT the limit nothing fires, so a clean strong
    # primary qualifies.
    controls = _clean_controls()
    got = analysis.verdicts(
        STRONG_PRIMARY,
        positional=controls["positional"],
        sham=controls["sham"],
        shuffle={
            "draws": 200,
            "clears": 15,
            "clear_share": analysis.SHUFFLE_CLEAR_LIMIT,
        },
        largest_true_effect=0.05,
        damage_outcomes=DAMAGE_OK,
    )
    assert got["verdict"] == "qualified"


def test_damage_failed_fires_when_the_panel_cannot_see_gross_damage() -> None:
    # A damage arm at chance (alternating outcomes, bound <= 0.5) fails the qualification on
    # its own, even with a perfect primary and every other control quiet.
    controls = _clean_controls()
    got = analysis.verdicts(
        STRONG_PRIMARY,
        largest_true_effect=0.05,
        positional=controls["positional"],
        sham=controls["sham"],
        shuffle=controls["shuffle"],
        damage_outcomes=DAMAGE_BLIND,
    )
    assert got["verdict"] == "damage_failed"
    assert got["fired"] == ["damage_failed"]
    assert got["damage_lower_bound"] <= 0.5


def test_a_clean_strong_primary_qualifies_with_an_auditable_record() -> None:
    controls = _clean_controls(largest_true_effect=0.05)
    got = analysis.verdicts(
        STRONG_PRIMARY,
        largest_true_effect=0.05,
        positional=controls["positional"],
        sham=controls["sham"],
        shuffle=controls["shuffle"],
        damage_outcomes=DAMAGE_OK,
    )
    assert got["verdict"] == "qualified"
    assert got["fired"] == []
    assert got["primary_lower_bound"] == 1.0
    assert got["n_primary"] == 200
    assert got["n_target"] == 200
    # Every input number travels beside the verdict: the record audits itself.
    assert set(got) == {
        "verdict",
        "fired",
        "n_primary",
        "n_target",
        "primary_lower_bound",
        "largest_true_effect",
        "positional_deviation",
        "sham_floor",
        "sham_min_decided",
        "sham_n_qualifying",
        "shuffle_clear_share",
        "damage_lower_bound",
    }
    # The registered rule's own record says which sham rule produced its floor, so a file
    # holding both verdicts can never be read as two copies of one rule.
    assert got["sham_min_decided"] == 0


def test_a_clean_chance_level_primary_does_not_qualify() -> None:
    # No control fired and the arm is still under target — but the bound does not clear 0.5.
    # A documented failure to qualify: a finding, not a shortfall to argue around.
    controls = _clean_controls()
    got = analysis.verdicts(
        WEAK_PRIMARY,
        largest_true_effect=0.05,
        positional=controls["positional"],
        sham=controls["sham"],
        shuffle=controls["shuffle"],
        damage_outcomes=DAMAGE_OK,
    )
    assert got["verdict"] == "not_qualified"
    assert got["fired"] == []
    assert got["primary_lower_bound"] <= 0.5
