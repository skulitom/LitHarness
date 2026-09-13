"""Superseded seed proposals stay proposed; missing active canon still fails."""

import runpy
from dataclasses import replace
from pathlib import Path

import litharness_contracts as lc
import pytest

from litharness.domain import worlds

HERE = (
    Path(__file__).resolve().parents[1]
    / "research/quality-measurement/growth-continuation-20260913"
)
READOUT = runpy.run_path(str(HERE / "readout.py"))


def test_seed_audit_keeps_superseded_proposals_without_hiding_loss_or_promotion():
    old = worlds.world_record("engine", worlds.WORLD_RULE_PREDICATE, value="Earlier rule")
    current = worlds.world_record("engine", worlds.WORLD_RULE_PREDICATE, value="Later rule")
    original = [old, current]
    times = {old.record_id: "2026-09-13T10:00:00Z", current.record_id: "2026-09-13T10:01:00Z"}
    accepted = replace(current, authority=lc.StateAuthority.ACCEPTED_CANON)
    check = READOUT["seed_preservation"]
    result = check(original, [old, accepted], times)
    assert result["all_preserved_with_expected_authority"]
    assert result["superseded_ids"] == [old.record_id]
    assert result["expected_accepted_count"] == 1
    for bad in (
        [old],
        [old, current],
        [accepted],
        [replace(old, authority=lc.StateAuthority.ACCEPTED_CANON), accepted],
        [old, replace(accepted, value="Changed rule")],
    ):
        assert not check(original, bad, times)["all_preserved_with_expected_authority"]


def test_snapshot_readout_uses_attested_scene_and_keeps_partial_values_and_proposals():
    def snapshot(value, key=None, authority=lc.StateAuthority.ACCEPTED_CANON):
        return worlds.world_record(
            "wren", "status_snapshot", value=value, order_key=key, authority=authority
        )

    records = [
        snapshot({"rank": 0}),
        snapshot({"rank": 1, "mana": 25}, "s000004"),
        snapshot({"mana": 20}, "s000005"),
        snapshot({"point": 0}, "s000005", lc.StateAuthority.PROPOSED),
    ]
    result = READOUT["snapshot_readout"](records)
    assert result["at"] == "s000005"
    assert result["values"] == {"rank": 1, "mana": 20}
    assert len(result["snapshots"]) == 4
    with pytest.raises(RuntimeError, match="coordinate space"):
        READOUT["snapshot_readout"]([*records, snapshot({"rank": 2}, "0350")])
