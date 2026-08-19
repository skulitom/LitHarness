"""The director-distinctness harness: `research/quality-measurement/director_distinctness.py`.

The module's own `--selftest` is the substantive check; this suite exists so it runs in CI, and
adds the two properties it cannot assert about itself — that the pre-registration prices a pass
rather than only celebrating it, and that the rail is stated where a reader of the results will
meet it.
"""

from __future__ import annotations

import sys
from pathlib import Path

RESEARCH = Path(__file__).parents[1] / "research" / "quality-measurement"
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

import director_distinctness as harness  # noqa: E402


def test_the_distinctness_selftest_passes() -> None:
    assert harness.selftest() == 0


def test_running_n_directors_divides_the_superiority_claims_alpha_by_n() -> None:
    """§61 pre-registration (5): if more than one book could have been reported, the confidence
    level is divided by the candidate count. Picking the best of N directors and then measuring
    that book against matched published prose is precisely reporting one of N candidates, so the
    experiment is payable in the currency the project is shortest of."""
    assert harness.alpha_cost(1)["divided_alpha"] == 0.05
    assert harness.alpha_cost(3)["divided_alpha"] == 0.05 / 3
    assert "§61" in harness.alpha_cost(3)["note"]


def test_the_pre_registration_states_the_rail_and_the_price() -> None:
    registration = harness.PRE_REGISTRATION
    assert registration["written"].startswith("2026-08-19")
    assert "DISTINCT" in registration["rail"]
    assert "price_of_a_pass" in registration
    assert "not_claimed" in registration, (
        "a DISTINCT reading says two directors write differently and nothing about which "
        "writes a better book; a report that did not say so would read as evidence"
    )


def test_one_indistinct_pair_makes_the_whole_set_not_comparable() -> None:
    """The rail binds on the set rather than pair by pair: reporting "A beat B" out of a
    three-director run where B and C are one director in hats would be reporting the seed."""
    same = ["down", "deeper", "lower"]
    other = ["the creditor calls", "the creditor waits", "the creditor knocks"]
    assert harness.report({"a": same, "b": other})["verdict"] == "COMPARABLE"
    assert harness.report({"a": same, "b": list(same)})["verdict"] == "NOT_COMPARABLE"
