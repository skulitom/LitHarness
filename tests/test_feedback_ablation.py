"""The ablation's arithmetic, offline: `research/quality-measurement/feedback_ablation.py`.

The module's own `--selftest` is the substantive check — ten claims over constructed profiles,
each able to fail — and this suite exists so it runs in CI rather than only when somebody
remembers. What it adds on top is the two properties the selftest cannot assert about itself:
that the pre-registration is committed as a literal rather than computed, and that the four
arms are still four.
"""

from __future__ import annotations

import sys
from pathlib import Path

RESEARCH = Path(__file__).parents[1] / "research" / "quality-measurement"
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

import feedback_ablation as ablation  # noqa: E402


def test_the_ablation_selftest_passes() -> None:
    """Every research module here that skipped a selftest shipped a defect its dry run would
    have caught, so the scorer is exercised on constructed inputs before it sees prose."""
    assert ablation.selftest() == 0


def test_the_two_sources_are_ablated_separately() -> None:
    """I6, and it is not a formality: with only `off` against `both` a separation says the loop
    does something and nothing about which half, and the halves have very different prices — a
    reader verdict is bought and a judge call is not."""
    assert set(ablation.ARMS) == {"off", "reader_only", "judge_only", "both"}


def test_the_pre_registration_states_the_comparison_before_it_runs() -> None:
    """The comparison, the expected direction, and the conditions under which the whole thing
    is reported dead are written down first. Choosing the reading after seeing the numbers is
    the failure `plan/stage-0-decisions.md` catalogues more often than any other."""
    registration = ablation.PRE_REGISTRATION
    assert registration["written"].startswith("2026-08-19")
    assert registration["kill_conditions"], "a pre-registration with no kill is a plan"
    assert any(
        "judge_only" in condition for condition in registration["kill_conditions"]
    ), "the judge half needs a kill condition of its own, or a null cannot be attributed"
    assert "not_claimed" in registration, (
        "the counters are surface proxies; a run that did not say so would read as evidence "
        "about prose"
    )


def test_the_reader_side_is_undecidable_at_the_n_that_exists() -> None:
    """Not sized for a hoped-for n. `audit_samples` is at 0 rows and no reader has been paid,
    so this reports the floors it has not met and the sample size it would need, rather than a
    number computed from four judgments."""
    blocked = ablation.reader_side(0, 0, 0)
    assert blocked["verdict"] == "UNDECIDABLE"
    assert len(blocked["unmet"]) == 3
    sizing = blocked["attainability"]["cells_for_power"]
    assert sizing, "an operator sizing a batch needs the last column, not just the floor"


def test_a_flat_run_is_reported_as_an_inert_generator_not_as_a_null() -> None:
    """§57's lesson in one read. A generator that answers every prompt identically has said
    nothing about the loop, and a bare NULL would let that be quoted as "feedback does not
    work"."""
    base = {
        "scenes": 1, "words": 100, "layout": [1, 1, 0],
        "counters": {"stat_flatten": 0.0, "interiority": 0.0, "em_dash": 0.0},
    }
    flat = ablation.compare({"off": base, "both": dict(base)}, "interiority", "high")
    assert flat["read"] == "INERT_GENERATOR"
