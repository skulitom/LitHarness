"""The watchdog's trip decision, checked without a card.

`thermal_watch.main` samples `nvidia-smi`, sleeps between samples and SIGTERMs the guarded job;
none of that runs here. `TripState` is the part that decides, and every test below hands it rows
by hand: the dict `sample()` would have built from one line of `--query-gpu` output, every value
a string, the way the card reports them. Three things are pinned. The thresholds (the core limit
kills on its own; the margin and throttle sensors kill only on a streak, because the module
docstring records healthy runs killed by a single `tlimit` dip), the resets, and the precedence
among the three reasons when more than one holds on the same sample.

Hermetic: no subprocess, no GPU, no sleeping.
"""

from __future__ import annotations

import pytest

thermal_watch = pytest.importorskip(
    "thermal_watch",
    reason="research module; needs the quality-measurement directory on the path",
)

HARD_CORE_C = thermal_watch.HARD_CORE_C
HARD_TLIMIT_MARGIN_C = thermal_watch.HARD_TLIMIT_MARGIN_C
HARD_MARGIN_SAMPLES = thermal_watch.HARD_MARGIN_SAMPLES
HARD_THROTTLE_SAMPLES = thermal_watch.HARD_THROTTLE_SAMPLES

#: At the limit on each sensor: the core trips on `>=`, the margin counts on `<=`.
HOT_CORE = str(HARD_CORE_C)
LOW_MARGIN = str(HARD_TLIMIT_MARGIN_C)

SLOWDOWN_FIELDS = (
    "clocks_event_reasons.hw_thermal_slowdown",
    "clocks_event_reasons.sw_thermal_slowdown",
    "clocks_event_reasons.hw_power_brake_slowdown",
)


def row(core: str = "55", margin: str = "20", throttling: bool = False) -> dict[str, str]:
    """One sampled row as `sample()` builds it: every field present, every value a string."""
    return {
        "temperature.gpu": core,
        "temperature.gpu.tlimit": margin,
        "power.draw": "250.00",
        "utilization.gpu": "97",
        "memory.used": "20480",
        "clocks_event_reasons.hw_thermal_slowdown": "Active" if throttling else "Not Active",
        "clocks_event_reasons.sw_thermal_slowdown": "Not Active",
        "clocks_event_reasons.hw_power_brake_slowdown": "Not Active",
    }


def one_short_on_both_streaks() -> thermal_watch.TripState:
    """A state one sample away from tripping on the margin and on the throttle at once."""
    return thermal_watch.TripState(
        throttled_streak=HARD_THROTTLE_SAMPLES - 1,
        margin_streak=HARD_MARGIN_SAMPLES - 1,
    )


# --- the core limit: immediate, no streak ------------------------------------------------------


def test_a_healthy_sample_trips_nothing_and_starts_no_streak():
    state = thermal_watch.TripState()
    assert state.observe(row()) is None
    assert state.observe(row()) is None
    assert (state.throttled_streak, state.margin_streak) == (0, 0)


def test_core_at_the_limit_trips_on_the_first_sample_with_no_streak_behind_it():
    state = thermal_watch.TripState()
    assert state.observe(row(core=HOT_CORE)) == f"core {float(HOT_CORE)}C >= {HARD_CORE_C}C"


def test_core_over_the_limit_trips_and_core_below_it_does_not():
    assert thermal_watch.TripState().observe(row(core="71.5")) == f"core 71.5C >= {HARD_CORE_C}C"
    assert thermal_watch.TripState().observe(row(core="69.9")) is None


# --- throttling: a streak, not a sample --------------------------------------------------------


def test_one_throttling_sample_is_a_transient():
    state = thermal_watch.TripState()
    assert state.observe(row(throttling=True)) is None
    assert state.throttled_streak == 1


def test_throttling_trips_at_the_configured_run_of_consecutive_samples():
    state = thermal_watch.TripState()
    for _ in range(HARD_THROTTLE_SAMPLES - 1):
        assert state.observe(row(throttling=True)) is None
    assert state.observe(row(throttling=True)) == (
        f"card throttling for {HARD_THROTTLE_SAMPLES} consecutive samples"
    )


def test_any_of_the_three_slowdown_flags_counts_as_throttling():
    for field in SLOWDOWN_FIELDS:
        state = thermal_watch.TripState()
        sample = row()
        sample[field] = "Active"
        assert state.observe(sample) is None
        assert state.throttled_streak == 1, field


def test_a_clean_sample_resets_the_throttle_streak():
    state = thermal_watch.TripState()
    for _ in range(HARD_THROTTLE_SAMPLES - 1):
        state.observe(row(throttling=True))
    assert state.observe(row()) is None
    assert state.throttled_streak == 0
    for _ in range(HARD_THROTTLE_SAMPLES - 1):
        assert state.observe(row(throttling=True)) is None
    assert state.observe(row(throttling=True)) is not None


# --- the tlimit margin: a streak, not a sample -------------------------------------------------


def test_a_low_margin_needs_the_configured_run_of_consecutive_samples():
    state = thermal_watch.TripState()
    for _ in range(HARD_MARGIN_SAMPLES - 1):
        assert state.observe(row(margin=LOW_MARGIN)) is None
    assert state.observe(row(margin=LOW_MARGIN)) == (
        f"tlimit margin <= {HARD_TLIMIT_MARGIN_C}C for {HARD_MARGIN_SAMPLES} consecutive samples"
    )


def test_a_margin_above_the_limit_does_not_count_toward_the_streak():
    state = thermal_watch.TripState()
    for _ in range(HARD_MARGIN_SAMPLES + 1):
        assert state.observe(row(margin=str(HARD_TLIMIT_MARGIN_C + 1))) is None
    assert state.margin_streak == 0


def test_a_clean_sample_resets_the_margin_streak():
    state = thermal_watch.TripState()
    for _ in range(HARD_MARGIN_SAMPLES - 1):
        state.observe(row(margin=LOW_MARGIN))
    assert state.observe(row()) is None
    assert state.margin_streak == 0
    for _ in range(HARD_MARGIN_SAMPLES - 1):
        assert state.observe(row(margin=LOW_MARGIN)) is None
    assert state.observe(row(margin=LOW_MARGIN)) is not None


# --- rows the card did not fill in -------------------------------------------------------------


def test_missing_fields_neither_crash_nor_trip():
    state = thermal_watch.TripState()
    assert state.observe({}) is None
    assert state.observe({"temperature.gpu": "55"}) is None
    assert (state.throttled_streak, state.margin_streak) == (0, 0)


def test_non_numeric_fields_neither_crash_nor_trip():
    state = thermal_watch.TripState()
    unreadable = row(core="[N/A]", margin="N/A")
    unreadable["power.draw"] = ""
    unreadable["clocks_event_reasons.hw_thermal_slowdown"] = "[N/A]"
    for _ in range(HARD_THROTTLE_SAMPLES):
        assert state.observe(unreadable) is None
    assert (state.throttled_streak, state.margin_streak) == (0, 0)


# --- precedence: core, then margin, then throttle ----------------------------------------------


def test_the_core_limit_outranks_both_streaks():
    state = one_short_on_both_streaks()
    reason = state.observe(row(core=HOT_CORE, margin=LOW_MARGIN, throttling=True))
    assert reason is not None and reason.startswith("core ")
    # The core reason won the sample; it did not skip the streak bookkeeping.
    assert (state.throttled_streak, state.margin_streak) == (
        HARD_THROTTLE_SAMPLES,
        HARD_MARGIN_SAMPLES,
    )


def test_the_margin_streak_outranks_the_throttle_streak():
    state = one_short_on_both_streaks()
    reason = state.observe(row(margin=LOW_MARGIN, throttling=True))
    assert reason is not None and reason.startswith("tlimit margin ")


def test_the_throttle_streak_is_the_reason_of_last_resort():
    state = one_short_on_both_streaks()
    reason = state.observe(row(throttling=True))
    assert reason == f"card throttling for {HARD_THROTTLE_SAMPLES} consecutive samples"
    assert state.margin_streak == 0


def test_precedence_holds_when_the_streaks_are_built_sample_by_sample():
    state = thermal_watch.TripState()
    reasons = [
        state.observe(row(margin=LOW_MARGIN, throttling=True))
        for _ in range(HARD_THROTTLE_SAMPLES)
    ]
    quiet, speaking = reasons[: HARD_MARGIN_SAMPLES - 1], reasons[HARD_MARGIN_SAMPLES - 1 :]
    assert quiet == [None] * (HARD_MARGIN_SAMPLES - 1)
    assert all(r is not None and r.startswith("tlimit margin ") for r in speaking)
    reason = state.observe(row(core=HOT_CORE, margin=LOW_MARGIN, throttling=True))
    assert reason is not None and reason.startswith("core ")


# --- the CLI thresholds reach the decision -----------------------------------------------------


def test_the_hard_core_and_hard_margin_flags_are_the_thresholds_the_decision_uses():
    state = thermal_watch.TripState(hard_core=60.0, hard_margin=10.0)
    assert state.observe(row(core="60")) == "core 60.0C >= 60.0C"
    tight = thermal_watch.TripState(hard_core=60.0, hard_margin=10.0)
    for _ in range(HARD_MARGIN_SAMPLES - 1):
        assert tight.observe(row(margin="10")) is None
    assert tight.observe(row(margin="10")) == (
        f"tlimit margin <= 10.0C for {HARD_MARGIN_SAMPLES} consecutive samples"
    )
