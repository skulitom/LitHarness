"""The watchdog's kill decision, checked without touching the card it guards.

`thermal_watch.TripJudge` is the piece that used to be inlined in `main`'s loop: given one
sampled row it updates the two streak counters and says whether a hard limit is crossed.
Every rule here encodes a run that ended badly one way or the other:

1. **A hot core kills on the first sample that shows it.** No streak softens this — the
   2026-08-20 shutdown happened under a core reading that never looked dangerous, so when
   the core does read hot there is nothing left to wait for.
2. **One throttling sample is weather; a run of them is the card doing our job for us.**
   `HARD_THROTTLE_SAMPLES` consecutive samples must pass before throttling may kill.
3. **The tlimit margin needs `HARD_MARGIN_SAMPLES` consecutive samples**, because its dips
   are transient (the trace quoted in the module docstring) and killing on a single low
   reading has already ended healthy runs once.
4. **Streaks reset on anything that is not a confirming sample** — including samples where
   the sensor is missing or unparseable, which must neither crash nor count as evidence.

Precedence is fixed and tested: core, then margin streak, then throttle streak.

Hermetic: no subprocess, no GPU, no sleeping. Everything here is dicts and arithmetic.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RESEARCH = Path(__file__).resolve().parents[1] / "research" / "quality-measurement"
sys.path.insert(0, str(RESEARCH))

thermal_watch = pytest.importorskip(
    "thermal_watch",
    reason="research module; needs the quality-measurement directory on the path",
)

HARD_CORE = 70.0
HARD_MARGIN = 6.0


def make_row(**overrides: str) -> dict[str, str]:
    """A plausible healthy sample, with named fields overridden."""
    values = dict.fromkeys(thermal_watch.FIELDS, "")
    values.update(
        {
            "temperature.gpu": "45",
            "temperature.gpu.tlimit": "25",
            "power.draw": "150",
            "utilization.gpu": "30",
            "memory.used": "1024",
        }
    )
    values.update(overrides)
    return values


def observe(judge: thermal_watch.TripJudge, **overrides: str) -> str | None:
    return judge.observe(make_row(**overrides), HARD_CORE, HARD_MARGIN)


def test_a_core_at_the_limit_trips_immediately_on_a_clean_first_sample():
    judge = thermal_watch.TripJudge()
    assert observe(judge, **{"temperature.gpu": "70"}) == f"core 70.0C >= {HARD_CORE}C"
    assert observe(judge, **{"temperature.gpu": "71.5"}) == f"core 71.5C >= {HARD_CORE}C"


def test_a_core_below_the_limit_does_not_trip():
    assert observe(thermal_watch.TripJudge(), **{"temperature.gpu": "69.9"}) is None


def test_the_core_trip_wins_no_matter_what_the_streaks_are_doing():
    judge = thermal_watch.TripJudge()
    # Two low-margin, throttling samples: both streaks are live but not yet fatal...
    low_and_throttling = {
        "temperature.gpu.tlimit": "4",
        "clocks_event_reasons.hw_thermal_slowdown": "Active",
    }
    for _ in range(2):
        assert observe(judge, **low_and_throttling) is None
    # ...and the hot core ends the run before either streak can.
    assert observe(judge, **{"temperature.gpu": "72"}).startswith("core ")


def test_one_throttling_sample_is_transient_but_a_full_streak_trips():
    judge = thermal_watch.TripJudge()
    active = {"clocks_event_reasons.sw_thermal_slowdown": "Active"}
    for _ in range(thermal_watch.HARD_THROTTLE_SAMPLES - 1):
        assert observe(judge, **active) is None
    assert observe(judge, **active) == (
        f"card throttling for {thermal_watch.HARD_THROTTLE_SAMPLES} consecutive samples"
    )


def test_any_slowdown_reason_counts_as_throttling():
    # hw_thermal, sw_thermal and hw_power_brake are all the card saying the same thing,
    # matched case-insensitively exactly as main's loop used to match them.
    for flag in ("active", "True", "TRUE"):
        single = thermal_watch.TripJudge()
        assert observe(
            single, **{"clocks_event_reasons.hw_power_brake_slowdown": flag}
        ) is None
        assert single.throttled_streak == 1


def test_a_low_tlimit_margin_needs_a_full_streak_to_trip():
    judge = thermal_watch.TripJudge()
    at_margin = {"temperature.gpu.tlimit": "6"}
    for _ in range(thermal_watch.HARD_MARGIN_SAMPLES - 1):
        assert observe(judge, **at_margin) is None
    assert observe(judge, **at_margin) == (
        f"tlimit margin <= {HARD_MARGIN}C "
        f"for {thermal_watch.HARD_MARGIN_SAMPLES} consecutive samples"
    )


def test_the_margin_counts_only_at_or_below_the_threshold():
    judge = thermal_watch.TripJudge()
    just_above = {"temperature.gpu.tlimit": "6.01"}
    for _ in range(thermal_watch.HARD_MARGIN_SAMPLES):
        assert observe(judge, **just_above) is None
    assert judge.margin_streak == 0


def test_a_clean_sample_resets_both_streaks():
    judge = thermal_watch.TripJudge()
    low_margin = {"temperature.gpu.tlimit": "4"}
    throttling = {"clocks_event_reasons.hw_thermal_slowdown": "Active"}
    for _ in range(thermal_watch.HARD_MARGIN_SAMPLES - 1):
        assert observe(judge, **low_margin) is None
    for _ in range(thermal_watch.HARD_THROTTLE_SAMPLES - 1):
        assert observe(judge, **throttling) is None
    assert judge.throttled_streak == thermal_watch.HARD_THROTTLE_SAMPLES - 1
    # The throttling rows carry a healthy margin, so that streak was reset along the way;
    # what matters is that the low-margin run did not survive the healthy rows either.
    assert judge.margin_streak == 0
    # One healthy sample wipes both runs...
    assert observe(judge) is None
    assert judge.throttled_streak == 0
    assert judge.margin_streak == 0
    # ...so a later low-margin run must start over from scratch.
    for _ in range(thermal_watch.HARD_MARGIN_SAMPLES - 1):
        assert observe(judge, **low_margin) is None
    assert observe(judge, **low_margin) is not None


def test_missing_or_unparseable_fields_neither_crash_nor_trip():
    empty_judge = thermal_watch.TripJudge()
    assert empty_judge.observe({}, HARD_CORE, HARD_MARGIN) is None
    garbage_judge = thermal_watch.TripJudge()
    assert garbage_judge.observe(
        {
            "temperature.gpu": "N/A",
            "temperature.gpu.tlimit": "",
            "clocks_event_reasons.hw_thermal_slowdown": "N/A",
        },
        HARD_CORE,
        HARD_MARGIN,
    ) is None
    # A sensor that cannot be read is evidence in neither direction: no streak builds.
    assert garbage_judge.throttled_streak == 0
    assert garbage_judge.margin_streak == 0


def test_precedence_is_core_then_margin_then_throttle():
    everything_bad = {
        "temperature.gpu": "80",
        "temperature.gpu.tlimit": "1",
        "clocks_event_reasons.hw_thermal_slowdown": "Active",
    }
    saturated = max(thermal_watch.HARD_MARGIN_SAMPLES, thermal_watch.HARD_THROTTLE_SAMPLES)

    # Core beats both fully-built streaks.
    core_first = thermal_watch.TripJudge()
    reason: str | None = None
    for _ in range(saturated):
        reason = core_first.observe(make_row(**everything_bad), HARD_CORE, HARD_MARGIN)
    assert reason is not None and reason.startswith("core ")

    # With the core sensor unreadable, the margin streak outranks the throttle streak.
    margin_and_throttle = {
        k: v for k, v in everything_bad.items() if k != "temperature.gpu"
    }
    no_core_judge = thermal_watch.TripJudge()
    reason = None
    for _ in range(saturated):
        reason = no_core_judge.observe(
            make_row(**margin_and_throttle), HARD_CORE, HARD_MARGIN
        )
    assert reason is not None and reason.startswith("tlimit margin"), reason
    # The margin reason names its streak, and it is the reason returned, not throttling's.
    assert "consecutive samples" in reason and "throttling" not in reason

    # And with the margin sensor healthy, sustained throttling is what trips.
    throttle_only = thermal_watch.TripJudge()
    reason = None
    for _ in range(thermal_watch.HARD_THROTTLE_SAMPLES):
        reason = throttle_only.observe(
            make_row(**{"clocks_event_reasons.hw_thermal_slowdown": "Active"}),
            HARD_CORE,
            HARD_MARGIN,
        )
    assert reason == (
        f"card throttling for {thermal_watch.HARD_THROTTLE_SAMPLES} consecutive samples"
    )


def test_the_thresholds_are_ordered_the_way_the_docstrings_claim():
    assert thermal_watch.HARD_TLIMIT_MARGIN_C < thermal_watch.HARD_CORE_C
    assert 0 < thermal_watch.HARD_MARGIN_SAMPLES < thermal_watch.HARD_THROTTLE_SAMPLES
