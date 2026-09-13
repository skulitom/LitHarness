"""The continuation has fixed bounds and keeps failed stock arithmetic visible."""

import runpy
from dataclasses import replace
from pathlib import Path

import pytest

from litharness.domain import gamesystem as gs
from tests.test_growth_limits import _system

HERE = (
    Path(__file__).resolve().parents[1]
    / "research/quality-measurement/growth-continuation-20260913"
)
RUN = runpy.run_path(str(HERE / "run.py"))
AUDIT = runpy.run_path(str(HERE / "audit.py"))


def test_growth_continuation_is_bounded_and_uses_its_own_frozen_runtime():
    base = RUN["BASE"]
    assert base.HERE == HERE and base.RUN.name == "growth-continuation-20260913"
    assert base.REVISION == "23243c3" and base.OWNER == "growth-continuation-20260913:"
    for calls, tokens, seconds in ((32, 0, 0), (0, 2_200_000, 0), (0, 0, 5400)):
        with pytest.raises(RuntimeError, match="ceiling"):
            base.check_budget(calls, tokens, seconds)
    assert RUN["check_chapter_count"](6, 6)
    assert not RUN["check_chapter_count"](5, 6)
    for count, target in ((7, 6), (6, 5), (7, 7), (-1, 1), (None, 1), (True, 1)):
        with pytest.raises(RuntimeError, match="chapter count"):
            RUN["check_chapter_count"](count, target)


def test_stock_audit_distinguishes_a_paid_repeat_from_an_unfunded_increase():
    system = _system()
    before = replace(
        gs.starting_sheet(system, "smith"),
        rank_id="r2",
        magnitudes=(("load", 1), ("point", 1), ("weld", 1)),
    )
    paid = gs.deepen(before, "load", at="s1").sheet
    transition = AUDIT["stock_transition"](before, paid)
    assert transition["paid_capability_increases"]["load"] == 1
    assert transition["stocks"] == [
        {
            "stock": "point",
            "before": 1,
            "after": 0,
            "rank_grant": 0,
            "purchase_cost": 1,
            "balanced_under_seed_model": True,
        }
    ]
    unfunded = replace(
        paid, magnitudes=tuple((k, 1 if k == "point" else v) for k, v in paid.magnitudes)
    )
    assert not AUDIT["stock_transition"](before, unfunded)["stocks"][0]["balanced_under_seed_model"]
    risen = gs.rise(before, at="s1").sheet
    assert AUDIT["stock_transition"](before, risen)["stocks"][0]["rank_grant"] == 1
