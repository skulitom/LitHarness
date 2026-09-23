"""Declared repeatable growth must coexist with ownership and bounded advancement."""

from dataclasses import replace

import pytest

from litharness.application import world as world_view
from litharness.application import world_agent
from litharness.domain import gamesystem as gs
from litharness.domain import worlds
from tests.helpers import accepted_all


def _system(limit: worlds.GrowthLimit | None = "open") -> gs.SystemDef:
    return gs.SystemDef(
        system_id="forge", name="Forge", criterion="rank", rank_label="Rank",
        ranks=tuple(gs.Rank(f"r{i}", f"Rank {i}") for i in range(5)),
        abilities=(
            gs.Ability("weld", "Weld", growth_limit=1),
            gs.Ability("load", "Load", needs=(gs.Need("weld"),),
                       price=(("point", 1),), growth_limit=limit),
            gs.Ability("duration", "Duration", needs=(gs.Need("weld"),),
                       price=(("point", 1),), growth_limit="open"),
            gs.Ability("brace", "Brace", needs=(gs.Need("r3"),), growth_limit=1),
            gs.Ability("point", "Point", per_rung=1),
        ),
        scale=gs.Scale("Forge", 1),
    )


def _with_ability(system: gs.SystemDef, ability_id: str, **changes: object) -> gs.SystemDef:
    return replace(system, abilities=tuple(
        replace(ability, **changes) if ability.ability_id == ability_id else ability
        for ability in system.abilities
    ))


def test_repeatable_purchase_spends_each_point_and_replays_at_the_right_position() -> None:
    system = _system()
    assert gs.check_draw(system) == ()
    sheet = gs.starting_sheet(system, "smith")
    records = [*gs.records_for(system), *gs.records_for_sheet(sheet)]
    gain = gs.Move(gs.AdvanceKind.GAIN, ability_id="load")
    deepen = gs.Move(gs.AdvanceKind.DEEPEN, ability_id="load")
    assert gain not in gs.legal_moves(sheet)
    with pytest.raises(gs.IllegalAdvance, match="costs 1 point"):
        gs.gain(sheet, "load", at="s1")
    for index, move in enumerate((
        gs.Move(gs.AdvanceKind.RISE, rank_id="r1"), gain,
        gs.Move(gs.AdvanceKind.RISE, rank_id="r2"), deepen,
        gs.Move(gs.AdvanceKind.RISE, rank_id="r3"), deepen,
    ), 1):
        assert move in gs.legal_moves(sheet)
        advanced = gs.advance(sheet, move, at=f"s{index}")
        assert advanced == gs.advance(sheet, move, at=f"s{index}")
        records.extend(advanced.records)
        sheet = advanced.sheet
        if move.kind != gs.AdvanceKind.RISE:
            assert sheet.magnitude("point") == 0
            assert deepen not in gs.legal_moves(sheet)
            with pytest.raises(gs.IllegalAdvance, match="costs 1 point"):
                gs.deepen(sheet, "load", at=f"s{index}")
        assert all(m.ability_id != "point" for m in gs.legal_moves(sheet))
    assert sheet.magnitude("load") == 3 and sheet.magnitude("weld") == 1
    canon = accepted_all(records)
    assert gs.sheet_of(canon, "smith", at="s2").magnitude("load") == 1
    assert gs.sheet_of(canon, "smith", at="s4").magnitude("load") == 2
    assert gs.sheet_of(canon, "smith", at="s6") == sheet


@pytest.mark.parametrize("limit, expected", [(None, 1), (1, 1), (2, 2)])
def test_ownership_and_explicit_caps_stop_both_offers_and_direct_moves(limit, expected) -> None:
    system = _system(limit)
    sheet = replace(gs.starting_sheet(system, "smith"), magnitudes=(
        ("brace", 0), ("duration", 0), ("load", expected), ("point", 10), ("weld", 1),
    ))
    assert gs.Move(gs.AdvanceKind.DEEPEN, ability_id="load") not in gs.legal_moves(sheet)
    with pytest.raises(gs.IllegalAdvance, match="maximum"):
        gs.deepen(sheet, "load", at="s1")
    assert gs.Move(gs.AdvanceKind.GAIN, ability_id="duration") in gs.legal_moves(sheet)
    assert gs.Move(gs.AdvanceKind.GAIN, ability_id="brace") not in gs.legal_moves(sheet)
    with pytest.raises(gs.IllegalAdvance, match="rung r3"):
        gs.gain(sheet, "brace", at="s1")
    assert system.scale.maximum == 1
    assert system.depth_limit("weld") == 1


def test_open_growth_does_not_acquire_an_arbitrary_numeric_ceiling() -> None:
    sheet = replace(gs.starting_sheet(_system(), "smith"), magnitudes=(
        ("brace", 0), ("duration", 0), ("load", 99), ("point", 1), ("weld", 1),
    ))
    assert gs.Move(gs.AdvanceKind.DEEPEN, ability_id="load") in gs.legal_moves(sheet)
    advanced = gs.deepen(sheet, "load", at="s1")
    assert advanced.sheet.magnitude("load") == 100
    assert advanced.sheet.magnitude("point") == 0


def test_prerequisite_depth_is_checked_against_the_required_capability() -> None:
    for limit in ("open", 4):
        system = _with_ability(_system(limit), "brace", needs=(gs.Need("load", 3),))
        assert gs.check_draw(system) == ()
    blocked = _with_ability(_system(2), "brace", needs=(gs.Need("load", 3),))
    assert any("needs load at 3" in reason for reason in gs.check_draw(blocked))
    negative = _with_ability(_system(), "brace", needs=(gs.Need("load", 0),))
    assert any("needs load at 0" in reason for reason in gs.check_draw(negative))


@pytest.mark.parametrize("limit", ["open", 1, 2, 100, None])
def test_declarations_round_trip_and_complete_without_raising_other_caps(limit) -> None:
    system = _system(limit)
    records = gs.records_for(system)
    assert gs.systems_of(records) == (system,)
    assert worlds.validate(records) == ()
    drawn = [r for r in records if r.predicate not in gs.CONFIGURATION_PREDICATES]
    before = tuple(drawn)
    minted, reasons = gs.completion_records(drawn)
    assert reasons == () and tuple(drawn) == before
    assert {r.predicate for r in minted} == gs.CONFIGURATION_PREDICATES
    [back] = gs.systems_of([*drawn, *minted])
    assert back == system
    assert gs.completion_records([*drawn, *minted]) == ((), ())
    assert back.depth_limit("load") == (None if limit == "open" else limit or 1)


def test_absent_growth_declarations_preserve_the_legacy_digest_and_moves() -> None:
    system = _system(None)
    system = replace(system, abilities=tuple(
        replace(ability, growth_limit=None) for ability in system.abilities
    ), scale=gs.Scale("Depth", 3))
    assert not any(r.predicate == worlds.GROWTH_LIMIT for r in gs.records_for(system))
    # Computed from the committed pre-change implementation, not from the new serializer.
    assert system.digest == "sys-6953f2eb2b6966c0456de1c6"
    assert gs.systems_of(gs.records_for(system)) == (system,)
    assert system.depth_limit("weld") == 3
    assert gs.Move(gs.AdvanceKind.DEEPEN, ability_id="weld") in gs.legal_moves(
        gs.starting_sheet(system, "smith")
    )
    changed = _with_ability(system, "weld", growth_limit=1)
    assert changed.digest != system.digest
    assert gs.Move(gs.AdvanceKind.DEEPEN, ability_id="weld") not in gs.legal_moves(
        gs.starting_sheet(changed, "smith")
    )


def test_open_depth_does_not_raise_unrelated_ownership_or_break_completion() -> None:
    system = _with_ability(_system(), "brace", needs=(gs.Need("load", 101),))
    system = _with_ability(system, "weld", growth_limit=None)
    records = [r for r in gs.records_for(system) if r.predicate not in gs.CONFIGURATION_PREDICATES]
    records.append(worlds.world_record("smith", worlds.CAN_DO, object_ref="load", value=100))
    minted, reasons = gs.completion_records(records)
    assert reasons == ()
    [back] = gs.systems_of([*records, *minted])
    assert back.scale.maximum == 1 and back.depth_limit("weld") == 1
    assert back.depth_limit("load") is None


@pytest.mark.parametrize("value", [0, -1, True, False, 1.5, "2", "unlimited", {}, None])
def test_malformed_growth_declarations_are_not_accepted_as_legacy_absence(value) -> None:
    records = [r for r in gs.records_for(_system()) if r.predicate != worlds.GROWTH_LIMIT]
    records.append(worlds.world_record("load", worlds.GROWTH_LIMIT, value=value))
    assert any("growth_limit" in reason for reason in worlds.validate(records))
    assert not world_view.check(records)["ok"]
    if value is not None:
        with pytest.raises(gs.MalformedSystem, match="growth_limit"):
            gs.records_for(_with_ability(_system(), "load", growth_limit=value))


@pytest.mark.parametrize("subject, fields", [
    ("load", {"object_ref": "point"}), ("load", {"order_key": "s1"}),
    ("point", {}), ("forge", {}),
])
def test_growth_declarations_require_a_timeless_capability_value(subject, fields) -> None:
    records = list(gs.records_for(_system()))
    records.append(worlds.world_record(subject, worlds.GROWTH_LIMIT, value="open", **fields))
    assert any("growth_limit" in reason for reason in worlds.validate(records))


def test_a_stock_cannot_declare_repeatable_advancement() -> None:
    with pytest.raises(gs.MalformedSystem, match="stock is never gained or deepened"):
        gs.records_for(_with_ability(_system(), "point", growth_limit="open"))


@pytest.mark.parametrize("value, sentence", [
    (1, "load is held or unheld; it does not deepen"),
    (2, "load can be gained or deepened up to 2"),
    ("open", "load can be gained or deepened repeatedly; no cap is declared"),
])
def test_growth_reaches_context_as_a_scoped_operating_rule(value, sentence) -> None:
    [record] = accepted_all([worlds.world_record("load", worlds.GROWTH_LIMIT, value=value)])
    assert record.record_id in worlds.operating_rule_ids([record])
    assert sentence in worlds.project([record]).values()


def test_seed_and_grow_expose_growth_without_inferring_it_from_a_price() -> None:
    seed = world_agent.render_seed_request("Supplied mechanics")
    grow = world_agent.render_grow_request("Established changes", logical_id="s1")
    for request in (seed, grow):
        assert "use growth_limit when supplied mechanics establish its growth" in request.system
        assert "explicit positive maximum when given" in request.system
        assert "A requirement alone does not establish repeatability" in request.system
        assert "Leave unspecified growth undeclared" in request.system
