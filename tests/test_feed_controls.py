"""The feed controls' arithmetic and the patterned-reader attainability table, checked by hand.

Everything here is built from `FeedSession` records whose correct answer is stated before
anything runs, or from seeded simulation whose determinism is part of what is pinned. What
this file establishes: the scorable subset and its reporting, `fp5` reading the **slot**
share (zero and FAIL on fixed patterns, alive on varied ones, UNREADABLE thin), the structural
UNSIZED refusal while `feed_core.CONTROL_MIN_SESSIONS` is None with `bcr`'s own PASS / FAIL /
off_centre / imprecise kinds once a number is set, the positional control naming its worst
slot, the directional-only skim-price kill, and an attainability table simulated over
patterned session-level readers — where an unbiased reader cannot clear the band at a small
batch, which is §94.7's finding and the reason the table exists. No model call anywhere.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

feed_core = pytest.importorskip(
    "feed_core",
    reason="research module; imported by path, skipped where research/ is unavailable",
)
bcr = pytest.importorskip(
    "bcr",
    reason="research module; imported by path, skipped where research/ is unavailable",
)
feed_controls = pytest.importorskip(
    "feed_controls",
    reason="research module; imported by path, skipped where research/ is unavailable",
)

# ------------------------------------------------------------------------- local session builder


def _session(
    actions: list[tuple[str, str]], *, rotation: int = 0, unanswered: int = 0
) -> feed_core.FeedSession:
    return feed_core.FeedSession(
        feed_id="test-feed",
        arm="test-arm",
        model="scripted",
        rotation=rotation,
        replicate=0,
        dose=0.0,
        actions=tuple(actions),
        unanswered=unanswered,
    )


def _skim_session(skims: int, reads: int, *, slot: str = "A") -> feed_core.FeedSession:
    """One session whose skim rate is exactly skims / (skims + reads)."""
    return _session([("skim", slot)] * skims + [("read", slot)] * reads)


# ------------------------------------------------------------------------------ scorable / table


def test_scorable_keeps_only_fully_answered_nonempty_sessions() -> None:
    answered = _session([("read", "A")])
    partly_unanswered = _session([("read", "A")], unanswered=1)
    empty_but_answered = _session([])
    kept = feed_controls.scorable([answered, partly_unanswered, empty_but_answered])
    assert kept == [answered]


def test_slot_share_table_reports_hand_computed_shares_and_counts_drops() -> None:
    first = _session([("skim", "A"), ("read", "B")])  # shares A=0, B=1; skim rate 1/2
    second = _session([("read", "C")], rotation=1)  # rotation 1 puts the target on B
    dropped = _session([], unanswered=2)
    table = feed_controls.slot_share_table([first, second, dropped])
    assert table["sessions"] == 2
    assert table["unscorable"] == 1
    assert table["slots"]["B"]["per_session"] == [1.0, 0.0]
    assert table["slots"]["B"]["mean"] == 0.5
    assert table["slots"]["A"]["per_session"] == [0.0, 0.0]
    # Rotation 1 makes B the target: session one spent everything on C, so the datum is 0.
    assert table["target_read_share"] == [0.0, 0.0]
    assert table["skim_rate"] == [0.5, 0.0]
    # The target (slot B under rotation 1) was never fully read by either session.
    assert table["abandonment_step"] == [-1, -1]


def test_slot_share_table_of_nothing_is_empty_and_not_a_crash() -> None:
    table = feed_controls.slot_share_table([])
    assert table["sessions"] == 0
    assert table["unscorable"] == 0
    assert table["slots"]["C"]["per_session"] == []
    assert table["slots"]["C"]["mean"] is None


# ---------------------------------------------------------------------------------------- fp5


def test_fp5_scores_zero_and_fails_naming_the_rotator_on_all_round_robin_sessions() -> None:
    """Three identical strict rotators: constant slot vector, sd 0.0, switch rate 1.0."""
    rotator = [("read", feed_core.SLOTS[index % 4]) for index in range(8)]
    result = feed_controls.fp5_non_degenerate([_session(rotator) for _ in range(3)])
    assert result["statistic"] == 0.0
    assert result["verdict"] == "FAIL"
    assert result["mean_read_switch_rate"] == 1.0
    assert result["named_pattern"] == "rotating through the feed"


def test_fp5_scores_zero_and_fails_naming_the_monotone_reader_on_all_in_one_slot() -> None:
    """Three readers that never leave slot B: constant slot vector, switch rate 0.0."""
    result = feed_controls.fp5_non_degenerate(
        [_session([("read", "B")] * 8) for _ in range(3)]
    )
    assert result["statistic"] == 0.0
    assert result["verdict"] == "FAIL"
    assert result["mean_read_switch_rate"] == 0.0
    assert result["named_pattern"] == "never leaves one book"


def test_fp5_passes_on_a_set_whose_slot_shares_vary_by_sqrt_three_quarters() -> None:
    """Four sessions, one wholly on each slot: each slot's shares are (1, 0, 0, 0) up to order.

    Hand-derived: pstdev([1, 0, 0, 0]) = sqrt(3/16) = 0.43301..., far above the 0.05 floor.
    """
    varied = [_session([("read", slot)] * 8) for slot in feed_core.SLOTS]
    result = feed_controls.fp5_non_degenerate(varied)
    assert result["statistic"] == pytest.approx(math.sqrt(3 / 16))
    assert result["statistic"] > feed_core.DEGENERATE_SD
    assert result["verdict"] == "PASS"


def test_fp5_is_unreadable_below_two_scorable_sessions() -> None:
    lone = feed_controls.fp5_non_degenerate([_session([("read", "A")])])
    nothing = feed_controls.fp5_non_degenerate([])
    for result in (lone, nothing):
        assert result["verdict"] == "UNREADABLE"
        assert result["statistic"] is None


# ---------------------------------------------------------------------------------- equivalence


def test_equivalence_control_is_unsized_while_min_sessions_is_unset() -> None:
    result = feed_controls.equivalence_control("placebo", [0.25] * 12, centre=0.25)
    assert result["verdict"] == "UNSIZED"
    assert result["verdict"] not in ("PASS", "FAIL")
    assert "attainability" in result["why"]


def test_equivalence_control_passes_on_values_inside_the_band_once_sized() -> None:
    patch = pytest.MonkeyPatch()
    patch.setattr(feed_core, "CONTROL_MIN_SESSIONS", 8)
    try:
        result = feed_controls.equivalence_control("placebo", [0.25] * 8, centre=0.25)
    finally:
        patch.undo()
    assert result["verdict"] == "PASS"
    assert result["failure_kind"] is None


def test_equivalence_control_fails_off_centre_on_a_displaced_reader_once_sized() -> None:
    """Eight sessions all at 0.70: the interval is tight and entirely outside the band."""
    patch = pytest.MonkeyPatch()
    patch.setattr(feed_core, "CONTROL_MIN_SESSIONS", 8)
    try:
        result = feed_controls.equivalence_control("placebo", [0.70] * 8, centre=0.25)
    finally:
        patch.undo()
    assert result["verdict"] == "FAIL"
    assert result["failure_kind"] == "off_centre"


def test_equivalence_control_names_imprecision_when_wide_but_still_centred() -> None:
    """Half a session's reads on the target, half elsewhere: mean exactly 0.25, huge spread.

    Hand-derived shape: the interval spans roughly [0.125, 0.375], width 0.25 > 2 x 0.10,
    containing the centre — bcr's imprecise kind, an undersized batch and not a biased reader.
    """
    patch = pytest.MonkeyPatch()
    patch.setattr(feed_core, "CONTROL_MIN_SESSIONS", 8)
    try:
        result = feed_controls.equivalence_control("placebo", [0.0, 0.50] * 4, centre=0.25)
    finally:
        patch.undo()
    assert result["verdict"] == "FAIL"
    assert result["failure_kind"] == "imprecise"
    assert result["low"] <= 0.25 <= result["high"]
    assert result["high"] - result["low"] > 2 * feed_core.CONTROL_BAND


# ------------------------------------------------------- the positional control (fp2 reading)


def test_positional_control_names_the_over_read_slot_and_counts_rotations() -> None:
    """Slot B takes three of four reads in every session; A the rest; C and D nothing.

    Hand-derived points: A 0.25, B 0.75, C 0.0, D 0.0 against centre 0.25 — B is worst at a
    distance of 0.5, C and D fail at 0.25, A sits dead centre.
    """
    biased = [
        _session([("read", "B")] * 3 + [("read", "A")], rotation=index)
        for index in range(4)
    ]
    patch = pytest.MonkeyPatch()
    patch.setattr(feed_core, "CONTROL_MIN_SESSIONS", 4)
    try:
        result = feed_controls.positional_control(biased)
    finally:
        patch.undo()
    assert result["verdict"] == "FAIL"
    assert result["worst_slot"] == "B"
    assert result["rotations"] == {0: 1, 1: 1, 2: 1, 3: 1}
    assert result["slots"]["A"]["point"] == pytest.approx(0.25)
    assert result["slots"]["B"]["point"] == pytest.approx(0.75)


def test_positional_control_stays_unsized_without_a_registered_floor() -> None:
    biased = [
        _session([("read", "B")] * 3 + [("read", "A")], rotation=index) for index in range(4)
    ]
    result = feed_controls.positional_control(biased)
    assert result["verdict"] == "UNSIZED"
    assert result["worst_slot"] is None  # no interval was computed, so none is named


def test_positional_control_survives_an_empty_session_list() -> None:
    result = feed_controls.positional_control([])
    assert result["rotations"] == {}
    assert result["unscorable"] == 0


# ------------------------------------------------------------------------------ skim price (fp6)


def test_fp6_holds_when_skim_usage_collapses_under_the_flat_price() -> None:
    """Cheap-side rates near 0.86, flat-side near 0.11: the interval cannot reach zero.

    Hand-derived: mean difference 0.75 with per-session rates this far apart leaves a 90%
    percentile bootstrap lower bound far above zero — and the resample count is bcr's own.
    """
    cheap = [_skim_session(skims, 9 - skims) for skims in (8, 8, 8, 7)]
    flat = [_skim_session(skims, 9 - skims) for skims in (1, 1, 0, 2)]
    result = feed_controls.fp6_skim_price(cheap, flat)
    assert result["verdict"] == "direction_holds"
    assert result["difference"] == pytest.approx(0.75)
    assert result["interval"][0] > 0.0
    assert result["resamples"] == bcr._resamples()
    assert result["unscorable"] == 0


def test_fp6_fails_when_the_two_price_regimes_overlap() -> None:
    """The same multiset of rates on both sides: the difference is centred on zero.

    A directional kill must fire here — no bar below it, but also no direction above it.
    """
    cheap = [_skim_session(skims, 9 - skims) for skims in (5, 4, 5, 4)]
    flat = [_skim_session(skims, 9 - skims) for skims in (4, 5, 4, 5)]
    result = feed_controls.fp6_skim_price(cheap, flat)
    assert result["verdict"] == "direction_fails"
    assert result["difference"] == pytest.approx(0.0)
    assert result["interval"][0] <= 0.0


def test_fp6_is_unreadable_below_two_scorable_sessions_a_side() -> None:
    four = [_skim_session(8, 1) for _ in range(4)]
    one = [_skim_session(8, 1)]
    assert feed_controls.fp6_skim_price(one, four)["verdict"] == "UNREADABLE"
    assert feed_controls.fp6_skim_price(four, one)["verdict"] == "UNREADABLE"


# ----------------------------------------------------------------------------- simulate_share


def test_simulate_share_is_deterministic_in_pattern_session_index_and_seed() -> None:
    for pattern in ("sticky", "dirichlet", "hold_then_switch"):
        again = feed_controls.simulate_share(pattern, 3, 11)
        assert feed_controls.simulate_share(pattern, 3, 11) == again
        other_seed = feed_controls.simulate_share(pattern, 3, 12)
        other_index = feed_controls.simulate_share(pattern, 4, 11)
        # Stochastic patterns move with both inputs; only equality is pinned, never a value.
        if pattern in ("sticky", "dirichlet"):
            assert other_seed != again or other_index != again


def test_all_in_patterns_give_exactly_one_or_zero_by_target_slot() -> None:
    assert feed_controls.simulate_share("all_in_0", 5, 7, target_slot=0) == 1.0
    assert feed_controls.simulate_share("all_in_0", 5, 7, target_slot=1) == 0.0
    assert feed_controls.simulate_share("all_in_3", 2, 9, target_slot=3) == 1.0
    assert feed_controls.simulate_share("all_in_3", 2, 9, target_slot=0) == 0.0


def test_round_robin_gives_a_quarter_at_the_registered_count_and_a_third_at_nine() -> None:
    """The registered 8 reads divide the feed evenly; an uneven 9 is pinned beside it.

    Renamed from test_round_robin_gives_exactly_a_quarter_at_eight_reads_and_one_third_at_nine
    when the session was resized to the measured shelf: the registered count
    (`BUDGET_UNITS // READ_COST` = 8) now divides FEED_SIZE exactly, so a strict rotator's
    slot share is 0.25 from any phase; at 9 reads slot 0 takes the first, fifth and ninth of
    the cycle — exactly 3/9 — pinning that the arithmetic tracks the count, not the constant.
    """
    eight = [
        feed_controls.simulate_share(
            "round_robin", index, 7, target_slot=slot, reads=feed_controls.READS_PER_SESSION
        )
        for index in range(4)
        for slot in range(4)
    ]
    assert set(eight) == {0.25}
    nine = feed_controls.simulate_share("round_robin", 0, 7, target_slot=0, reads=9)
    assert nine == pytest.approx(1 / 3)


def test_full_bias_pulls_content_driven_patterns_to_the_target_and_fixed_ignore_it() -> None:
    """bias 1.0 sends every sticky and dirichlet read to the target; fixed rules do not move."""
    for pattern in ("sticky", "dirichlet"):
        assert feed_controls.simulate_share(pattern, 6, 13, bias=1.0) == 1.0
    assert feed_controls.simulate_share("all_in_1", 6, 13, target_slot=0, bias=1.0) == 0.0
    for pattern in ("round_robin", "hold_then_switch"):
        unbiased = feed_controls.simulate_share(pattern, 6, 13, bias=0.0)
        assert feed_controls.simulate_share(pattern, 6, 13, bias=1.0) == unbiased


def test_simulate_share_rejects_unknown_patterns_and_neutralises_an_empty_budget() -> None:
    with pytest.raises(ValueError, match="unknown pattern"):
        feed_controls.simulate_share("all_in_4", 0, 0)
    with pytest.raises(ValueError, match="unknown pattern"):
        feed_controls.simulate_share("uniform", 0, 0)
    for pattern in feed_controls.PATTERNS:
        feed_controls.simulate_share(pattern, 0, 0)  # every registered name answers
    assert feed_controls.simulate_share("sticky", 0, 0, reads=0) == 0.25


# ------------------------------------------------------------------------------ attainability

_SIZING_SEED = 11
_SIZING_TRIALS = 16


@pytest.fixture(scope="module")
def sized_table() -> dict[str, Any]:
    """One seeded attainability table shared by every sizing test (the bootstrap is the cost)."""
    return feed_controls.sessions_needed(seed=_SIZING_SEED, trials=_SIZING_TRIALS)


def test_sessions_needed_states_its_shape_and_repeats_exactly_under_a_seed() -> None:
    first = feed_controls.sessions_needed(seed=5_151, trials=2)
    second = feed_controls.sessions_needed(seed=5_151, trials=2)
    assert first == second
    assert first["trials"] == 2
    assert first["candidates"] == [16, 24, 32, 48, 64, 96]
    assert set(first["models"]) == {"mixture", "dirichlet"}


def test_sessions_needed_uniform_rates_never_fall_and_biased_045_never_leads(
    sized_table: dict[str, Any],
) -> None:
    """The §94.7 shape, at a stated seed and trial count: bigger batches never get worse, and
    the biased reader never passes more often than the unbiased one — strictly less wherever
    an unbiased reader can pass at all. In the mixture world *nothing* clears the band at 16
    sessions (both rates are legitimately zero): that unattainability is the finding, not a
    defect in the table.
    """
    table = sized_table
    sizes = [str(size) for size in table["candidates"]]
    for model, data in table["models"].items():
        rows = data["by_sessions"]
        uniform = {size: rows[size]["pass_at_uniform"] for size in sizes}
        biased = {size: rows[size]["pass_near_0.45"] for size in sizes}
        # Common random numbers plus narrowing intervals: more sessions never pass less often.
        assert uniform["96"] >= uniform["16"], model
        for size in sizes:
            assert biased[size] <= uniform[size], (model, size)
            if uniform[size] > 0:
                assert biased[size] < uniform[size], (model, size)
        # Where the band is reachable at all, the biased reader is strictly shut out.
        assert biased["96"] < uniform["96"], model
        # The labelled biases really do land where they say, reported beside each cell.
        means = rows["observed_mean_share"]
        assert abs(means["uniform"] - 0.25) < 0.05, model
        assert abs(means["near_0.35"] - 0.35) < 0.05, model
        assert abs(means["near_0.45"] - 0.45) < 0.05, model


def test_sessions_needed_mixture_world_is_unattainable_at_the_bcrs_declared_batch(
    sized_table: dict[str, Any],
) -> None:
    """The whole reason this module exists: §94.7's correlated world cannot meet the band small."""
    table = sized_table
    mixture = table["models"]["mixture"]["by_sessions"]
    dirichlet = table["models"]["dirichlet"]["by_sessions"]
    assert mixture["16"]["pass_at_uniform"] <= mixture["96"]["pass_at_uniform"]
    # The content-driven allocator closes its bands far sooner than the pattern mixture does.
    assert dirichlet["48"]["pass_at_uniform"] >= mixture["48"]["pass_at_uniform"]


# ------------------------------------------------------------------- fp5 operating characteristic


def test_fp5_operating_characteristic_pins_both_halves_as_documented() -> None:
    result = feed_controls.fp5_operating_characteristic(seed=94_607, trials=20)
    assert set(result["fixed_patterns"]) == set(feed_controls.FIXED_PATTERNS)
    for pattern, half in result["fixed_patterns"].items():
        assert half["statistic"] == 0.0, pattern
        assert half["verdict"] == "FAIL", pattern
    assert result["dirichlet_clear_rate"] >= result["required_clear_rate"] == 0.95
    assert result["trials"] == 20
    again = feed_controls.fp5_operating_characteristic(seed=94_607, trials=20)
    assert again == result  # deterministic under the seed, so a selftest can call it twice


def test_fp5_operating_characteristic_default_trial_count_is_stated() -> None:
    result = feed_controls.fp5_operating_characteristic()
    assert result["trials"] == 60
    assert result["dirichlet_clear_rate"] >= 0.95
