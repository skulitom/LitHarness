"""Listing requests keep their own task rather than inheriting drafting guidance."""

from __future__ import annotations

from litharness.application import overview, reviser
from litharness.domain import house
from litharness.domain import writers as writers_domain


def test_the_clause_rides_the_listing_call_which_carries_no_floor_under_it() -> None:
    request = overview.render_overview_request("", writers_domain.CAST["ferreira"])
    system = request.system or ""
    assert overview._TASK in system
    assert house.HOUSE_RULES not in system
    assert house.CLARITY not in system
    assert reviser._TASK not in system
