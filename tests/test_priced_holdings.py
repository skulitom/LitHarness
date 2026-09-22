"""A priced grant printed as its allowance binds as the purchases that bought it (§254).

The opening-consequence trial
(`research/quality-measurement/opening-consequence-20260914/REPORT.md`, "Numerical failure and
next scope") printed the interface's physical allowances in the columns its system counts as
one-Point purchases, and the status-line binding took each printed number as a magnitude: the
Chapter 5-to-6 purchase read as a Duration increase of 60 against a grant of one Point, and the
registered stock check reported `balanced_under_seed_model: false`. These tests replay that
book's own status lines on its declared price model and pin the exact one-Point purchase. The
retained book is not rewritten; the ids asserted absent are the ones it holds
(`runs/opening-consequence-20260914/book/checkpoint-6/world.json`).
"""

from __future__ import annotations

import litharness_contracts as lc

from litharness.domain import gamesystem as gs
from litharness.domain import state as state_mod
from litharness.domain import worlds
from litharness.domain.extraction import (
    STATUS_PREDICATE,
    Movable,
    extract_state,
    holding_record_id_for,
    movables,
)
from litharness.domain.progression import moved_example
from tests.helpers import accepted_all

#: Verbatim from the retained chapters (Chapter1.txt:141, Chapter3.txt:141 and :163,
#: Chapter6.txt:79 and :89).
OPENING = "[STATUS] Wren — Loadstitch 1 | Length 10 | Duration 60 | Load 100"
FIRST_RISE = "[STATUS] Wren — Rank 1 | Point 1"
LOAD_BOUGHT = "[STATUS] Wren — Load 200 | Point 0"
SECOND_RISE = "[STATUS] Wren — Rank 2 | Point 1"
DURATION_BOUGHT = "[STATUS] Wren — Duration 120 | Point 0"

#: The failing holdings the retained book holds, by the ids this reader mints for them.
STORED_FAILURES = {
    ("length", "s000001", 10): "rec-h92bf01ebafb63302549ecb11",
    ("duration", "s000001", 60): "rec-h874fe580c801c6f3d482ed89",
    ("load", "s000001", 100): "rec-h4d4fac4a49b6a080b3b569d4",
    ("load", "s000003", 200): "rec-h6f0f85165133369d556b1919",
    ("duration", "s000006", 120): "rec-h275f47abb73d8aa8f1034889",
}


def _engine() -> gs.SystemDef:
    """The trial's engine, cut to what the purchases touch: one Point per rung, and Length,
    Duration and Load each paid one Point per investment with open growth (§210, §252)."""
    needs = (gs.Need("loadstitch"),)
    price = (("point", 1),)
    return gs.SystemDef(
        system_id="engine",
        name="Engine",
        criterion="rank",
        rank_label="Rank",
        ranks=(gs.Rank("rank_1", "One"), gs.Rank("rank_2", "Two"), gs.Rank("rank_3", "Three")),
        abilities=(
            gs.Ability("loadstitch", "Loadstitch", growth_limit=1),
            gs.Ability("length", "Length", needs=needs, price=price, growth_limit="open"),
            gs.Ability("duration", "Duration", needs=needs, price=price, growth_limit="open"),
            gs.Ability("load", "Load", needs=needs, price=price, growth_limit="open"),
            gs.Ability("inspection", "Inspection", growth_limit="open"),
            gs.Ability("point", "Point", per_rung=1),
        ),
        scale=gs.Scale("Engine", 1),
    )


def _seed() -> list[lc.StateRecord]:
    """The accepted seed: the system, its protagonist, and rank zero, which records no rung,
    so there is no opening `stands_at` edge (the trial's `initial_state` claim)."""
    system = _engine()
    assert gs.check_draw(system) == ()
    return [
        *accepted_all(gs.records_for(system)),
        worlds.world_record(
            "wren",
            worlds.ENTITY_ROLE_PREDICATE,
            value="protagonist",
            authority=lc.StateAuthority.ACCEPTED_CANON,
        ),
        worlds.world_record(
            "wren",
            STATUS_PREDICATE,
            value={"rank": 0},
            authority=lc.StateAuthority.ACCEPTED_CANON,
        ),
    ]


def _scene(lines, known, chapter):  # type: ignore[no-untyped-def]
    return extract_state(
        f"She read the panel.\n\n{lines}\n",
        known=known,
        project_id="p",
        book_id="b",
        branch_id="br",
        logical_id=f"scene-{chapter}",
        version_id="v1",
        stated_order_key=f"s{chapter:06d}",
    )


def _read(*chapters):  # type: ignore[no-untyped-def]
    known = _seed()
    for chapter, lines in chapters:
        known = [*known, *_scene("\n\n".join(lines), known, chapter)]
    return known


def _holdings(records, at):  # type: ignore[no-untyped-def]
    return {
        record.object_ref: record.value
        for record in records
        if record.predicate == worlds.CAN_DO
        and record.subject == "wren"
        and state_mod.order_key_of(record) == at
    }


def test_a_printed_allowance_its_price_could_not_buy_binds_no_holding() -> None:
    """Chapter 1 prints the starting allowances with no Point to buy them: only the unpriced
    Loadstitch binds, and the snapshot keeps the page's numbers verbatim."""
    read = _scene(OPENING, _seed(), 1)
    assert _holdings(read, "s000001") == {"loadstitch": 1}
    ids = {record.record_id for record in read}
    for (ability_id, at, printed), stored in STORED_FAILURES.items():
        assert holding_record_id_for("wren", ability_id, at, printed) == stored
        assert stored not in ids
    [snapshot] = [record for record in read if record.predicate == STATUS_PREDICATE]
    assert snapshot.value == {"rank": 0, "loadstitch": 1, "length": 10, "duration": 60, "load": 100}
    assert snapshot.record_id == "rec-xed26ad9cdaf20319b81d164a"


def test_the_first_load_purchase_before_any_rung_binds_one_investment() -> None:
    """Chapter 3: the first rise hands out one Point and `Load 200 | Point 0` spends it, before
    any typed sheet exists; the holding is one purchase, not two hundred."""
    known = _read((1, (OPENING,)))
    read = _scene(f"{FIRST_RISE}\n\n{LOAD_BOUGHT}", known, 3)
    assert _holdings(read, "s000003") == {"load": 1}
    [standing] = [record for record in read if record.predicate == worlds.STANDS_AT_PREDICATE]
    assert standing.object_ref == "rank_1"
    [snapshot] = [record for record in read if record.predicate == STATUS_PREDICATE]
    assert (snapshot.value["load"], snapshot.value["point"]) == (200, 0)


def test_the_one_point_duration_purchase_binds_one_investment_and_balances_the_stock() -> None:
    """The report's exact transition. Rank 1 to Rank 2 grants one Point and
    `Duration 120 | Point 0` spends it. The retained book read a Duration increase of 60, a
    purchase cost of 60 and `balanced_under_seed_model: false`; here the grant is 1, the cost
    1, and the stock 0 to 0."""
    system = _engine()
    book = _read(
        (1, (OPENING,)), (3, (FIRST_RISE, LOAD_BOUGHT)), (6, (SECOND_RISE, DURATION_BOUGHT))
    )
    canon = [record for record in book if state_mod.is_canon(record)]
    before = gs.sheet_of(canon, "wren", system=system, at="s000005")
    after = gs.sheet_of(canon, "wren", system=system, at="s000006")
    assert before is not None and after is not None
    assert (before.rank_id, after.rank_id) == ("rank_1", "rank_2")
    assert _holdings(book, "s000006") == {"duration": 1}
    climbed = system.rank_index(after.rank_id) - system.rank_index(before.rank_id)
    grant = climbed * system.ability("point").per_rung
    cost = sum(
        (after.magnitude(ability.ability_id) - before.magnitude(ability.ability_id))
        * dict(ability.price).get("point", 0)
        for ability in system.abilities
        if ability.price
    )
    assert (grant, cost) == (1, 1)
    assert before.magnitude("point") + grant - cost == after.magnitude("point") == 0
    assert (before.magnitude("duration"), after.magnitude("duration")) == (0, 1)
    assert (after.magnitude("load"), after.magnitude("length")) == (1, 0)
    [printed] = [
        record
        for record in book
        if record.predicate == STATUS_PREDICATE and state_mod.order_key_of(record) == "s000006"
    ]
    assert printed.value["duration"] == 120, "the page's allowance stays on the snapshot"
    assert not [
        move
        for move in gs.legal_moves(after)
        if move.ability_id is not None and system.ability(move.ability_id).price
    ], "the Point is spent, so no paid move is offered again"


def test_a_line_that_prints_purchases_as_counts_binds_exactly_as_before() -> None:
    """The sibling trials on the same world printed `Load 1 | Point 0` and
    `Duration 1 | Point 0`: a count its price could buy binds at the printed number under the
    §236 note."""
    book = _read(
        (1, ("[STATUS] Wren — Loadstitch 1",)),
        (3, (FIRST_RISE, "[STATUS] Wren — Load 1 | Point 0")),
        (6, (SECOND_RISE, "[STATUS] Wren — Duration 1 | Point 0")),
    )
    held = {
        (state_mod.order_key_of(record), record.object_ref): (record.value, record.note)
        for record in book
        if record.predicate == worlds.CAN_DO and record.subject == "wren"
    }
    assert {key: value for key, (value, _) in held.items()} == {
        ("s000001", "loadstitch"): 1,
        ("s000003", "load"): 1,
        ("s000006", "duration"): 1,
    }
    assert all(
        (note or "").startswith("read off the status line: a declared subject holding")
        for _, note in held.values()
    )


def test_a_purchase_the_line_cannot_attribute_binds_nothing_for_its_priced_columns() -> None:
    """One Point and two moved allowances, or a moved allowance with no stock column printed:
    choosing a purchase would be the reader inventing it, so neither binds."""
    known = _read((1, (OPENING,)))
    both = _scene(f"{FIRST_RISE}\n\n[STATUS] Wren — Length 20 | Load 200 | Point 0", known, 3)
    assert _holdings(both, "s000003") == {}
    unpaid = _scene("[STATUS] Wren — Rank 1\n\n[STATUS] Wren — Load 200", known, 3)
    assert _holdings(unpaid, "s000003") == {}


def test_the_moved_line_abstains_where_a_priced_column_prints_an_allowance() -> None:
    """With a Point in hand the beat may name Duration, and the arithmetic's next count is 1
    against a line that prints 60; the writer is shown the entering line instead. A rise still
    shows its moved line."""
    known = _read((1, (OPENING,)), (3, (FIRST_RISE,)))
    duration = Movable("Duration", "duration")
    assert duration in movables(known, character="wren", at="s000004")
    assert moved_example(known, duration, character="wren", at="s000004") is None
    shown = moved_example(known, Movable("Two", gs.RANK_KEY), character="wren", at="s000004")
    assert shown is not None
    assert "Rank 2" in shown.line and "Duration 60" in shown.line


def test_a_mixed_line_charges_the_paid_count_only_the_stock_the_bought_counts_left() -> None:
    """An affordable purchase and an allowance on one stock: `Length 1` binds as printed and
    costs one of the two Points, so the allowance binds at the one purchase the rest paid for,
    and the stock balances."""
    system = _engine()
    book = _read(
        (1, ("[STATUS] Wren — Loadstitch 1",)),
        (2, (FIRST_RISE,)),
        (
            3,
            (
                "[STATUS] Wren — Rank 2 | Point 2",
                "[STATUS] Wren — Length 1 | Duration 120 | Point 0",
            ),
        ),
    )
    assert _holdings(book, "s000003") == {"length": 1, "duration": 1, "point": 0}
    canon = [record for record in book if state_mod.is_canon(record)]
    before = gs.sheet_of(canon, "wren", system=system, at="s000002")
    after = gs.sheet_of(canon, "wren", system=system, at="s000003")
    assert before is not None and after is not None
    grant = (system.rank_index(after.rank_id) - system.rank_index(before.rank_id)) * system.ability(
        "point"
    ).per_rung
    cost = sum(
        (after.magnitude(ability.ability_id) - before.magnitude(ability.ability_id))
        * dict(ability.price).get("point", 0)
        for ability in system.abilities
        if ability.price
    )
    assert (grant, cost) == (1, 2)
    assert before.magnitude("point") + grant - cost == after.magnitude("point") == 0


def test_a_mixed_line_whose_bought_counts_spend_the_whole_stock_pays_for_no_allowance() -> None:
    """Two bought Lengths spend both Points, so nothing is left for the Duration the line
    prints as an allowance, and it binds nothing rather than a purchase no Point paid for."""
    book = _read(
        (1, ("[STATUS] Wren — Loadstitch 1",)),
        (
            3,
            (
                "[STATUS] Wren — Rank 2 | Point 2",
                "[STATUS] Wren — Length 2 | Duration 120 | Point 0",
            ),
        ),
    )
    assert _holdings(book, "s000003") == {"length": 2}


def test_an_opening_count_the_seed_did_not_declare_binds_nothing_and_its_line_abstains() -> None:
    """A named residual of §254, pinned as it behaves: an opening line printing a priced grant
    the seed did not declare, with no stock to have bought it, reads the same as the trial's
    opening allowance, so `Duration 1` binds nothing (it bound as printed before §254), the
    edges count 0 against the page's 1, and the moved-line example abstains on that column."""
    known = _read((1, ("[STATUS] Wren — Loadstitch 1 | Duration 1",)), (3, (FIRST_RISE,)))
    assert _holdings(known, "s000001") == {"loadstitch": 1}
    duration = Movable("Duration", "duration")
    assert duration in movables(known, character="wren", at="s000004")
    assert moved_example(known, duration, character="wren", at="s000004") is None
