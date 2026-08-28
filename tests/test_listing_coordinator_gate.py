"""The listing loop's first refusing gate: a chained listing is redrawn, a clean one is not.

The operator named this defect in the fifth operator read — a listing that reads *"like a list
with constant 'and then', 'and then'"* — and `plan/reader-read-5.md` §4.1 measured it: pilot 11
sat at 6.48 coordinator tokens per hundred words against a market maximum of 5.8823, with three
of this project's twenty-one listings above anything the market publishes. Stage-0 §147 is the
decision to refuse above that ceiling.

**The ceiling is the market's own maximum on purpose**, and the test at the bottom of this file
is the attainability check made durable: at the shipped value, nothing the market publishes
would be refused. A p90 ceiling would refuse a tenth of it, and a recall-tuned refusal gate has
inverted error costs — the lesson this project has now narrowed a word guard on three times.

No model appears anywhere in this mechanism: a counter decides, and the comparison is against a
frozen scalar rather than against another candidate.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from litharness.application import overview
from litharness.cli import LISTING_COORDINATOR_CEILING, LISTING_DRAW_ATTEMPTS

#: Pilot 11's listing entire — the artifact the operator read. Its density is the 6.48 that
#: `plan/reader-read-5.md` §4.1 reports, so this fixture is the cross-check between the
#: research statistic and the production counter.
CHAINED = (
    """
Every screen on Earth lit with the same message in the same second, and the message said
that killing the things now coming through would make a person stronger. Then the doors
opened, in car parks and stairwells and drained swimming pools, and the monsters climbed
out.

Ravi maintained inventory software before any of this, so he reads a magic system the way
he reads any bad interface, hunting for what it never checks. The system pays for kills.
He finds ways to get paid that involve no killing at all, and he means to be strong enough
to matter by the time somebody notices and shuts them.
    """
)
CLEAN = (
    "Nella Scur takes on any ladder, three ring-patterns on one shoulder, which every matcher's "
    "chart says is a body that should have died at four years old."
)


def test_the_counter_agrees_with_the_research_side_on_the_listing_that_was_read() -> None:
    """Production and research must count the same thing or the ceiling means nothing.

    6.48 is the value `plan/reader-read-5.md` §4.1 reports for pilot 11's listing, and this
    fixture is that listing. A production counter disagreeing with the research one would
    put the ceiling on a different scale from the distribution it was derived from.
    """
    assert overview.coordinator_density(CHAINED) == pytest.approx(6.48, abs=0.01)


def test_the_counter_respects_word_boundaries() -> None:
    """`hand` and `thenceforth` are not coordinators, and a substring match would say they are."""
    assert overview.coordinator_density("hand thenceforth band withstand") == 0.0


def test_an_empty_listing_divides_by_one_rather_than_raising() -> None:
    assert overview.coordinator_density("") == 0.0


def test_the_ceiling_is_a_parameter_with_no_default_in_the_pure_layer() -> None:
    """Where the number came from is a composition-root decision, never a domain fact."""
    with pytest.raises(TypeError):
        overview.chains_too_hard(CHAINED)  # type: ignore[call-arg]


def test_a_chained_listing_is_over_the_shipped_ceiling_and_a_clean_one_is_not() -> None:
    assert overview.chains_too_hard(CHAINED, ceiling=LISTING_COORDINATOR_CEILING)
    assert not overview.chains_too_hard(CLEAN, ceiling=LISTING_COORDINATOR_CEILING)


def test_the_loop_keeps_the_least_chained_draw_and_the_earliest_on_a_tie() -> None:
    assert overview.keep_least_chained([CHAINED, CLEAN]) == CLEAN
    assert overview.keep_least_chained([CLEAN, CHAINED]) == CLEAN
    first, second = "a and b", "c and d"  # identical density, different text
    assert overview.coordinator_density(first) == overview.coordinator_density(second)
    assert overview.keep_least_chained([first, second]) == first


def test_a_loop_that_drew_nothing_refuses_rather_than_returning_a_default() -> None:
    with pytest.raises(ValueError, match="drew nothing"):
        overview.keep_least_chained([])


def test_the_redraw_budget_is_bounded_so_a_locked_writer_cannot_spin_the_loop() -> None:
    assert LISTING_DRAW_ATTEMPTS >= 2  # a gate that never redraws is only a report
    assert LISTING_DRAW_ATTEMPTS <= 4  # and every redraw is a paid call


def test_the_shipped_ceiling_refuses_nothing_this_market_publishes() -> None:
    """The attainability check made durable: 0 of the admitted pool would be refused.

    The pool lives under the gitignored `derived/` sidecar by design (RS1 keeps third-party
    prose out of the repository), so this skips where it is absent rather than failing — and
    where it is present it is the check that must not quietly rot.
    """
    pool_path = (
        Path(__file__).resolve().parents[1]
        / "research"
        / "quality-measurement"
        / "derived"
        / "rivals.json"
    )
    if not pool_path.is_file():
        pytest.skip("the admitted market pool is a gitignored derived artifact")
    pool = json.loads(pool_path.read_text(encoding="utf-8"))
    refused = [
        row
        for row in pool
        if overview.chains_too_hard(str(row["listing"]), ceiling=LISTING_COORDINATOR_CEILING)
    ]
    assert refused == [], (
        f"{len(refused)} of {len(pool)} published listings would be refused at "
        f"{LISTING_COORDINATOR_CEILING}; the ceiling is meant to sit at the market's maximum"
    )
