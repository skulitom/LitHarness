"""The game system object: what a drawn system must be, and what a sheet may do.

`plan/first-principles-litrpg-core.md` is why this file exists. Its §2 says the pipeline has
"no game system object anywhere", and every chronic symptom the operator has named four books
running is that absence wearing different clothes. These tests are the object, and the ones
that carry the most argument are not the round trips — they are the refusals.

Three pairs are load-bearing:

- `test_a_system_read_back_out_of_canon_is_the_system_that_was_drawn` against
  `test_a_relabelled_system_is_a_different_system`. Together they say what the digest means:
  identity survives being written down, and does not survive a change to what a line renders.
- `test_a_book_with_no_system_is_answered_exactly_as_before` against
  `test_a_book_whose_sheet_does_not_match_its_system_is_refused`. That is the ratchet. The
  first is what keeps every book already on disk drafting; the second is what makes the floor
  mean something once seeds mint systems.
- `test_no_number_describes_the_person` alone, because it is the promise §114.6 extracted and
  the one a later change is most likely to break by accident.
"""

from __future__ import annotations

import dataclasses
import pathlib

import litharness_contracts as lc
import pytest

from litharness.domain import gamesystem as gs
from litharness.domain import genre, worlds


def _system(**overrides: object) -> gs.SystemDef:
    """A well-formed draw, as a starting point for the refusals to break one field at a time.

    Deliberately not a fixture shared with the world fixtures: this file's subject is what a
    system must be, and a definition that could drift with somebody else's golden book would
    make these assertions about that book instead.
    """
    base: dict[str, object] = {
        "system_id": "the_weave",
        "name": "the Weave",
        "criterion": "attunement",
        "rank_label": "Seal",
        "ranks": (
            gs.Rank("unsealed", "Unsealed"),
            gs.Rank("first_seal", "First Seal"),
            gs.Rank("second_seal", "Second Seal"),
        ),
        "abilities": (
            gs.Ability("seamsight", "Seamsight"),
            gs.Ability("threadpull", "Threadpull"),
            gs.Ability("stillwater", "Stillwater", needs=(gs.Need("seamsight", 2),)),
            gs.Ability("lanterncall", "Lanterncall", needs=(gs.Need("threadpull"),)),
            gs.Ability(
                "deepweave",
                "Deepweave",
                needs=(gs.Need("first_seal"), gs.Need("stillwater")),
            ),
        ),
        "scale": gs.Scale("Depth", 9),
    }
    base.update(overrides)
    return gs.SystemDef(**base)  # type: ignore[arg-type]


def _canon(records: list[lc.StateRecord]) -> list[lc.StateRecord]:
    return [
        dataclasses.replace(record, authority=lc.StateAuthority.ACCEPTED_CANON)
        for record in records
    ]


def _seeded(system: gs.SystemDef, character: str = "silas") -> list[lc.StateRecord]:
    sheet = gs.starting_sheet(system, character)
    return _canon(list(gs.records_for(system)) + list(gs.records_for_sheet(sheet)))


# --------------------------------------------------------------------------- what a draw is


def test_a_well_formed_draw_has_nothing_to_complain_about() -> None:
    assert gs.check_draw(_system()) == ()


def test_a_list_of_abilities_is_refused_because_the_operator_specified_a_graph() -> None:
    """A definition with no prerequisite edge is a list, and the model asked for a graph.

    **This is a delta from §114 and is deliberately not the check §114 forbade.** That entry
    forbids gating on `worlds.requirement_depth` for a world's inventory, because a world's
    inventory may legitimately be flat. This is a check on the object drawn under §160's own
    contract, where having no edges means the thing drawn is not the thing specified.
    """
    flat = _system(
        abilities=tuple(
            gs.Ability(ability.ability_id, ability.name) for ability in _system().abilities
        )
    )
    assert any("list rather than a graph" in complaint for complaint in gs.check_draw(flat))


def test_the_world_inventory_depth_counter_is_not_gated_by_any_of_this() -> None:
    """§114's counter still counts and still refuses to be a bar.

    The check above is the one this test exists to fence off. A flat *world* inventory passes
    `worlds.requirement_depth` with a 0 and nothing in this package refuses it; only a drawn
    `SystemDef` is held to the graph shape.
    """
    flat_world = [
        worlds.world_record("sera", worlds.CAN_DO, object_ref="cap_read_a_seam"),
        worlds.world_record("cap_read_a_seam", worlds.ENTITY_ROLE_PREDICATE, value="capability"),
    ]
    assert worlds.requirement_depth(flat_world) == 0
    assert worlds.validate(flat_world) == ()


def test_a_cycle_of_prerequisites_is_refused_because_it_cannot_be_entered() -> None:
    cyclic = _system(
        abilities=(
            gs.Ability("seamsight", "Seamsight", needs=(gs.Need("threadpull"),)),
            gs.Ability("threadpull", "Threadpull", needs=(gs.Need("seamsight"),)),
            gs.Ability("stillwater", "Stillwater"),
            gs.Ability("lanterncall", "Lanterncall"),
            gs.Ability("deepweave", "Deepweave"),
        )
    )
    assert any("cycle" in complaint for complaint in gs.check_draw(cyclic))


def test_a_two_rung_ladder_is_refused_because_a_rungs_number_has_nowhere_to_go() -> None:
    short = _system(ranks=(gs.Rank("unsealed", "Unsealed"), gs.Rank("first_seal", "First")))
    assert any("switch" in complaint for complaint in gs.check_draw(short))


def test_a_prerequisite_this_system_never_declared_is_refused() -> None:
    """Named rather than ignored: a threshold against nothing is a number with no arithmetic
    behind it, which is the word §114.6 used for a magnitude that computes with nothing."""
    dangling = _system(
        abilities=(
            *_system().abilities[:-1],
            gs.Ability("deepweave", "Deepweave", needs=(gs.Need("nowhere"),)),
        )
    )
    assert any("neither as an ability nor as a rung" in c for c in gs.check_draw(dangling))


def test_a_threshold_on_a_rung_is_refused_because_a_rung_has_no_depth() -> None:
    absurd = _system(
        abilities=(
            *_system().abilities[:-1],
            gs.Ability("deepweave", "Deepweave", needs=(gs.Need("first_seal", 3),)),
        )
    )
    assert any("has no depth to reach" in c for c in gs.check_draw(absurd))


def test_an_ability_may_not_take_the_rungs_column() -> None:
    clash = _system(abilities=(*_system().abilities[:-1], gs.Ability(gs.RANK_KEY, "Rank")))
    assert any(gs.RANK_KEY in c and "carries the rung" in c for c in gs.check_draw(clash))


def test_a_label_carrying_a_digit_is_refused_because_the_parser_reads_digits() -> None:
    """`extraction`'s field pattern is `label<space>digits`, so a digit inside a label is an
    ambiguity in the parser rather than a matter of taste."""
    numeric = _system(rank_label="Tier 2")
    assert any("carries no digit" in complaint for complaint in gs.check_draw(numeric))


def test_a_scale_that_cannot_deepen_is_refused_as_a_decoration() -> None:
    """§114.6's own word for a magnitude nothing computes with. A maximum of 1 means every
    holding is 1 forever, and the number says nothing that `holds` does not."""
    flat_scale = _system(scale=gs.Scale("Depth", 1))
    assert any("decoration" in complaint for complaint in gs.check_draw(flat_scale))


def test_a_system_nobody_can_start_in_is_refused() -> None:
    """Every ability behind a prerequisite means a starting sheet of zeroes: a book that
    clears no floor and whose writer is asked for nothing."""
    closed = _system(
        abilities=(
            gs.Ability("seamsight", "Seamsight", needs=(gs.Need("second_seal"),)),
            gs.Ability("threadpull", "Threadpull", needs=(gs.Need("second_seal"),)),
            gs.Ability("stillwater", "Stillwater", needs=(gs.Need("seamsight"),)),
            gs.Ability("lanterncall", "Lanterncall", needs=(gs.Need("threadpull"),)),
            gs.Ability("deepweave", "Deepweave", needs=(gs.Need("stillwater"),)),
        )
    )
    assert any("no starting sheet" in complaint for complaint in gs.check_draw(closed))


def test_a_refused_draw_is_never_written_down() -> None:
    """`records_for` refuses rather than writing a system nothing can be a position in —
    `extraction.MalformedSheet`'s argument, one object along."""
    with pytest.raises(gs.MalformedSystem):
        gs.records_for(_system(scale=gs.Scale("Depth", 1)))


def test_check_draw_never_ranks_and_the_module_exposes_no_score() -> None:
    """§61(5): no model, and no code, picks the best system.

    Asserted over the module's own surface rather than about one function, because the way this
    promise breaks is somebody adding a helper, not somebody editing `check_draw`.
    """
    banned = ("score", "rank_systems", "best", "prefer", "compare", "quality")
    assert [name for name in gs.__all__ if any(word in name.lower() for word in banned)] == []


# --------------------------------------------------------------------------- identity


def test_a_system_read_back_out_of_canon_is_the_system_that_was_drawn() -> None:
    """The whole round trip: draw, write records, read them back, and get the same object.

    Equality rather than digest alone, so a field that stopped being written down would fail
    here even if it happened not to be in the digest's material.
    """
    drawn = _system()
    back = gs.systems_of(_seeded(drawn))
    assert len(back) == 1
    assert back[0] == drawn
    assert back[0].digest == drawn.digest


def test_a_relabelled_system_is_a_different_system() -> None:
    """Identity includes what the line renders. Two systems with the same structure and
    different column labels print different sheets out of the same numbers, and a digest that
    called them equal would answer a question nobody asked."""
    assert _system().digest != _system(rank_label="Tier").digest


def test_a_world_may_run_no_system_at_all() -> None:
    """The operator's model names crafting as a case with no system, so an empty answer is a
    world rather than a failure."""
    assert gs.systems_of([worlds.world_record("marta", "is_a", value="a glazier")]) == ()


def test_two_ladders_under_one_system_make_it_unreadable_rather_than_guessed() -> None:
    """`extraction.sheet_for`'s rule: abstain when the book says more than one thing.

    Which chain the rung column counts has to be one answer, and choosing would be this module
    inventing which ladder the world meant.
    """
    records = _seeded(_system())
    records.extend(
        _canon(
            [
                worlds.world_record("resolve", worlds.TYPE_PREDICATE, value=worlds.CRITERION),
                worlds.world_record("resolve", worlds.COMPARATOR_PREDICATE, value="ordinal"),
                worlds.world_record("resolve", worlds.GOVERNED_BY, object_ref="the_weave"),
            ]
        )
    )
    assert gs.systems_of(records) == ()


def test_a_subject_governed_by_two_systems_is_a_complaint_not_a_tie_broken() -> None:
    records = _seeded(_system())
    records.extend(
        _canon(
            [
                worlds.world_record("the_ledgerwork", worlds.ENTITY_ROLE_PREDICATE, value="system"),
                worlds.world_record("seamsight", worlds.GOVERNED_BY, object_ref="the_ledgerwork"),
            ]
        )
    )
    assert any("governed by 2 systems" in c for c in worlds.validate(records))


def test_a_ladder_whose_system_nobody_declared_is_complained_about() -> None:
    """The issuer-shaped defect, caught at the vocabulary level. `plan/first-principles-
    litrpg-core.md` §2: ranks need an issuer, and with none declared an institution fills the
    space. A `governed_by` edge pointing at a subject with no system role is that hole."""
    records = [
        worlds.world_record("attunement", worlds.TYPE_PREDICATE, value=worlds.CRITERION),
        worlds.world_record("attunement", worlds.GOVERNED_BY, object_ref="the_weave"),
    ]
    assert any("not declared with the system role" in c for c in worlds.validate(records))


# --------------------------------------------------------------------------- the sheet


def test_a_starting_sheet_holds_what_needs_nothing_and_shows_the_rest_at_zero() -> None:
    """An unheld ability at 0 in the *snapshot* is the design: the arithmetic needs every
    ability present. Whether a zero *prints* is the sheet's declaration since §203 (a drawn
    system hides them; §160's wanting rides the offer line instead)."""
    sheet = gs.starting_sheet(_system(), "silas")
    assert sheet.snapshot() == {
        "rank": 1,
        "deepweave": 0,
        "lanterncall": 0,
        "seamsight": 1,
        "stillwater": 0,
        "threadpull": 1,
    }


def test_the_snapshot_carries_the_rungs_number_and_never_its_name() -> None:
    """Forced by the parser, not chosen: `extraction`'s field pattern reads digits only. The
    named outfit rides the graph line instead, which is the surface §113 built for it."""
    sheet = gs.starting_sheet(_system(), "silas")
    assert sheet.snapshot()[gs.RANK_KEY] == 1
    assert "Unsealed" not in str(sheet.snapshot())


def test_the_sheets_keys_are_the_systems_own_and_the_declaration_matches_them() -> None:
    """One derivation, so the sheet and the system cannot disagree. Track 4 measured why that
    matters: `sheet_for` abstains to the default when a book declares two sheets, so a
    disagreement does not error, it silently restores a column set the book never chose."""
    system = _system()
    declared = system.sheet_declaration()
    names = [field["name"] for field in declared["fields"]]  # type: ignore[index,union-attr]
    assert tuple(names) == system.value_keys
    assert set(gs.starting_sheet(system, "silas").snapshot()) == set(system.value_keys)


def test_a_sheet_change_is_a_new_record_rather_than_an_edited_one() -> None:
    """§11's prohibition, kept by construction rather than by a rule somebody follows:
    `worlds.record_id_for` hashes the value slot, so a magnitude that moves gets a new id."""
    sheet = gs.starting_sheet(_system(), "silas")
    moved = gs.deepen(sheet, "seamsight", at="s2")
    before = {record.record_id for record in gs.records_for_sheet(sheet)}
    after = {record.record_id for record in moved.records}
    assert not before & after


def test_an_advancement_records_only_what_moved() -> None:
    """Found by running the first version, and it is a property of the store rather than a
    preference.

    `worlds.record_id_for` keys on `(subject, predicate, object_ref, value)` and **not** on the
    order key — `extraction.record_id_for` includes it deliberately and this one does not — while
    `record_state_records` is `INSERT OR IGNORE`. So an unchanged holding rewritten at a later
    position is the same id and is silently dropped: harmless, and completely illegible, because
    the record set claimed to restate the sheet and did not. Writing the one edge that moved says
    what happened, and an unchanged holding keeps the position it was established at.
    """
    sheet = gs.starting_sheet(_system(), "silas")
    moved = gs.deepen(sheet, "seamsight", at="s2")
    predicates = sorted(record.predicate for record in moved.records)
    assert predicates == ["can_do", "status_snapshot"]
    assert all(record.subject == "silas" for record in moved.records)


def test_an_advancement_leaves_the_sheet_it_came_from_alone() -> None:
    sheet = gs.starting_sheet(_system(), "silas")
    gs.deepen(sheet, "seamsight", at="s2")
    assert sheet.magnitude("seamsight") == 1


def test_an_advancements_records_are_proposed_so_a_person_still_gates_canon() -> None:
    """`worlds.world_record`'s rail: a position reaches canon through the recorded
    `world accept` and never by being written."""
    sheet = gs.starting_sheet(_system(), "silas")
    moved = gs.rise(sheet, at="s3")
    assert {record.authority for record in moved.records} == {lc.StateAuthority.PROPOSED}


def test_an_unmet_prerequisite_refuses_the_gain_with_the_number_in_the_reason() -> None:
    """The arithmetic §114.6 asked for: the threshold decides, and it decides before anything
    is printed."""
    sheet = gs.starting_sheet(_system(), "silas")
    with pytest.raises(gs.IllegalAdvance) as raised:
        gs.gain(sheet, "stillwater", at="s2")
    assert "at 2" in str(raised.value) and "has it at 1" in str(raised.value)


def test_deepening_a_prerequisite_is_what_opens_the_ability_it_gates() -> None:
    """The whole point of a graph: the sheet's own numbers decide what comes next, and nothing
    else does."""
    sheet = gs.starting_sheet(_system(), "silas")
    assert "stillwater" not in [move.ability_id for move in gs.legal_moves(sheet)]
    deeper = gs.deepen(sheet, "seamsight", at="s2").sheet
    assert gs.gain(deeper, "stillwater", at="s3").sheet.holds("stillwater")


def test_an_ability_gated_by_a_rung_waits_for_the_rise() -> None:
    """The one edge where the ladder and the inventory meet, and §114 already named it as the
    one: a capability may need a rung first."""
    sheet = gs.starting_sheet(_system(), "silas")
    sheet = gs.deepen(sheet, "seamsight", at="s1").sheet
    sheet = gs.gain(sheet, "stillwater", at="s2").sheet
    with pytest.raises(gs.IllegalAdvance):
        gs.gain(sheet, "deepweave", at="s3")
    risen = gs.rise(sheet, at="s4").sheet
    assert gs.gain(risen, "deepweave", at="s5").sheet.holds("deepweave")


def test_a_magnitude_stops_at_the_systems_maximum() -> None:
    sheet = gs.starting_sheet(_system(scale=gs.Scale("Depth", 2)), "silas")
    sheet = gs.deepen(sheet, "seamsight", at="s1").sheet
    with pytest.raises(gs.IllegalAdvance):
        gs.deepen(sheet, "seamsight", at="s2")


def test_a_rise_goes_one_rung_and_stops_at_the_top() -> None:
    """Skipping a rung would be this module inventing a fact about the world."""
    sheet = gs.starting_sheet(_system(), "silas")
    sheet = gs.rise(sheet, at="s1").sheet
    assert sheet.rank_id == "first_seal"
    sheet = gs.rise(sheet, at="s2").sheet
    with pytest.raises(gs.IllegalAdvance):
        gs.rise(sheet, at="s3")


def test_legal_moves_offers_only_what_the_arithmetic_allows() -> None:
    sheet = gs.starting_sheet(_system(), "silas")
    offered = {(move.kind, move.ability_id or move.rank_id) for move in gs.legal_moves(sheet)}
    assert (gs.AdvanceKind.GAIN, "lanterncall") in offered
    assert (gs.AdvanceKind.GAIN, "stillwater") not in offered
    assert (gs.AdvanceKind.RISE, "first_seal") in offered


def test_a_sheet_read_back_at_a_position_is_the_sheet_at_that_position() -> None:
    """Read from the edges rather than from the snapshot: the printed form is derived, and a
    reader that took it instead would be a second answer to what somebody holds."""
    system = _system()
    records = _seeded(system)
    deepened = gs.deepen(gs.starting_sheet(system, "silas"), "seamsight", at="s4")
    records.extend(_canon(list(deepened.records)))
    early = gs.sheet_of(records, "silas", at="s2")
    late = gs.sheet_of(records, "silas", at="s9")
    assert early is not None and late is not None
    assert early.magnitude("seamsight") == 1
    assert late.magnitude("seamsight") == 2


def test_a_proposed_position_is_not_a_position() -> None:
    """The floor's rule for the floor's reason: counting proposals would let a book satisfy a
    reader with its own plan for later."""
    system = _system()
    records = list(gs.records_for(system)) + list(
        gs.records_for_sheet(gs.starting_sheet(system, "silas"))
    )
    assert gs.sheet_of(_canon(list(gs.records_for(system))) + records, "silas") is None


def test_no_number_describes_the_person() -> None:
    """§114.6's first precondition, asserted over the whole public surface.

    Every integer this module produces names one capacity or one rung. There is no total, no
    average and no "Level N" — the thing the operator's progression model explicitly excludes —
    and the way that promise breaks is somebody adding a convenience helper years from now, not
    somebody editing a function this test happens to call.
    """
    sheet = gs.starting_sheet(_system(), "silas")
    values = sheet.snapshot()
    assert set(values) == set(_system().value_keys)
    assert all(key == gs.RANK_KEY or key in _system().ability_ids for key in values)
    banned = ("total", "power", "level", "sum", "overall", "strength")
    assert [name for name in gs.__all__ if any(word in name.lower() for word in banned)] == []


# --------------------------------------------------------------------------- the furniture


def test_the_furniture_says_what_moved_and_composes_no_sentence() -> None:
    """§138's boundary: this module hands out data, and the render side writes the line. An
    adjective here would be an affirmative prose clause reaching every scene with a beat."""
    sheet = gs.starting_sheet(_system(), "silas")
    furniture = gs.deepen(sheet, "seamsight", at="s2").furniture
    assert furniture.moved == ("seamsight",)
    assert furniture.subject == "silas"
    assert furniture.values["seamsight"] == 2
    assert [column.name for column in furniture.columns] == list(_system().value_keys)


def test_a_rise_moves_the_rung_column_and_nothing_else() -> None:
    sheet = gs.starting_sheet(_system(), "silas")
    assert gs.rise(sheet, at="s2").moved == (gs.RANK_KEY,)


def test_the_module_hands_out_columns_rather_than_sheet_fields() -> None:
    """The import graph is the reason, and it is binding: `genre` imports `extraction`, so an
    `extraction` import here would close a cycle the moment the render side imports this
    module. Plain pairs keep the arrow pointing one way."""
    source = gs.__file__ or ""
    assert source
    text = pathlib.Path(source).read_text(encoding="utf-8")
    assert "import litharness.domain.extraction" not in text
    assert "from litharness.domain.extraction" not in text


# --------------------------------------------------------------------------- the ratchet


def test_a_book_with_no_system_is_answered_exactly_as_before() -> None:
    """The half that keeps every book already on disk drafting. A renderable canon snapshot and
    no declared system is what §158 left behind, and it still clears the floor."""
    legacy = _canon([worlds.world_record("sera", "status_snapshot", value={"level": 1, "hp": 3})])
    assert genre.has_starting_sheet(legacy)
    assert genre.genre_block(legacy) is None


def test_a_book_whose_sheet_matches_its_declared_system_clears_the_floor() -> None:
    assert genre.has_starting_sheet(_seeded(_system()))
    assert genre.genre_block(_seeded(_system())) is None
    assert genre.system_gap(_seeded(_system())) is None


def test_a_book_whose_sheet_does_not_match_its_system_is_refused() -> None:
    """The half that makes the floor mean something once seeds mint systems. §158's lesson one
    level up: a predicate that answers True while the ask renders something else is the exact
    disagreement the floor exists to rule out."""
    system = _system()
    records = _canon(list(gs.records_for(system)))
    records.extend(_canon([worlds.world_record("silas", "status_snapshot", value={"level": 1})]))
    assert not genre.has_starting_sheet(records)
    block = genre.genre_block(records)
    assert block is not None and "different books" in block


def test_a_proposed_system_does_not_tighten_the_floor() -> None:
    """The Architect builds a system before `world accept`, and refusing a book for a draw
    nobody accepted would gate on a proposal."""
    records = list(gs.records_for(_system()))
    records.extend(_canon([worlds.world_record("silas", "status_snapshot", value={"level": 1})]))
    assert genre.has_starting_sheet(records)


def test_a_second_sheet_declaration_is_reported_because_it_fails_silently() -> None:
    """The failure mode Track 4 measured: `sheet_for` abstains to the default when a book
    declares more than one, so the book renders a line it never chose and its own values are
    replaced by placeholders. Nothing errors, which is why it needs a report."""
    records = _seeded(_system())
    records.extend(
        _canon(
            [
                worlds.world_record(
                    "silas",
                    "status_sheet",
                    value={"fields": [{"name": "level", "label": "Level"}]},
                )
            ]
        )
    )
    gap = genre.system_gap(records)
    assert gap is not None and "abstains" in gap


def test_a_systemless_book_is_told_what_it_is_missing_without_being_blocked() -> None:
    """Report-then-gate, which `genre_block`'s docstring already argues for: the report where
    seeding is cheap, the refusal in front of the spend. §155.2's condition went unnamed on two
    databases while the pipeline drafted anyway, and saying nothing is how that happened."""
    legacy = _canon([worlds.world_record("sera", "status_snapshot", value={"level": 1})])
    gap = genre.system_gap(legacy)
    assert gap is not None and "declares no game system" in gap
    assert genre.genre_block(legacy) is None


# --------------------------------------------------------------------------- the packet


def test_a_holding_reaches_the_writer_as_a_fact_carrying_its_number() -> None:
    """§114.4's defect is what this avoids: a predicate with no projection sentence reaches the
    writer through `state.describe`'s flat fallback as machine notation."""
    system = _system()
    sheet = gs.deepen(gs.starting_sheet(system, "silas"), "seamsight", at="s2").sheet
    projected = worlds.project(gs.records_for_sheet(sheet, at="s2"))
    assert "silas can do seamsight at 2" in projected.values()


def test_a_holding_with_no_number_reads_exactly_as_it_always_did() -> None:
    """The byte-identity rail. Every `can_do` record written before §160 has no integer in its
    value slot, and adding the magnitude may not change what those records project."""
    plain = worlds.world_record("sera", worlds.CAN_DO, object_ref="cap_read_a_seam")
    assert worlds.project([plain])[plain.record_id] == "sera can do cap_read_a_seam"


def test_a_prerequisite_at_one_says_nothing_extra_because_one_is_what_it_always_meant() -> None:
    at_one = worlds.world_record(
        "cap_price_unseen", worlds.REQUIRES, value=1, object_ref="cap_read_a_seam"
    )
    deeper = worlds.world_record(
        "cap_price_unseen", worlds.REQUIRES, value=3, object_ref="cap_read_a_seam"
    )
    assert worlds.project([at_one])[at_one.record_id] == (
        "cap_price_unseen needs cap_read_a_seam first"
    )
    assert worlds.project([deeper])[deeper.record_id] == (
        "cap_price_unseen needs cap_read_a_seam at 3 first"
    )


def test_the_system_a_ladder_answers_to_reaches_the_writer_as_a_fact() -> None:
    record = worlds.world_record("attunement", worlds.GOVERNED_BY, object_ref="the_weave")
    assert worlds.project([record])[record.record_id] == "attunement is governed by the_weave"


def test_the_configuration_predicates_are_named_so_a_packet_can_exclude_them() -> None:
    """A record shaped for a machine that reaches a prompt is a measured defect
    (`extraction.CONFIGURATION_PREDICATES`), and these two are that shape: they say how a system
    is written down, not anything about the world."""
    assert gs.MAGNITUDE_SCALE in gs.CONFIGURATION_PREDICATES
    assert gs.SYSTEM_DIGEST in gs.CONFIGURATION_PREDICATES
    assert worlds.GOVERNED_BY not in gs.CONFIGURATION_PREDICATES


def test_a_written_down_system_is_a_coherent_world() -> None:
    """The records this module mints must satisfy the vocabulary they are written in; a system
    that made `worlds.validate` complain would be a system no world could hold."""
    assert worlds.validate(_seeded(_system())) == ()


# ------------------------------------------------- finishing a drawn system (stage-0 §165)


def _drawn_world(system: gs.SystemDef) -> list[lc.StateRecord]:
    """The world an Architect can actually declare: everything but the two mint-only predicates.

    §163.2 keeps `magnitude_scale` and `system_digest` out of `world vocabulary` on purpose, so
    this is the most complete system a seed can reach through `world declare` — a ladder, an
    issuer, governed capabilities and a prerequisite graph, and no scale.
    """
    return _canon(
        [
            record
            for record in gs.records_for(system)
            if record.predicate not in gs.CONFIGURATION_PREDICATES
        ]
    )


def test_a_system_a_seed_could_actually_draw_is_invisible_before_it_is_finished() -> None:
    """Serial Pilot 15's defect, at the point it bites: every clause true but the deciding one.

    The world holds the system role, one governed criterion, a ladder and the graph.
    `systems_of` requires a magnitude scale and the Architect has no documented way to write
    one — and until 15b §5 the gap answered with the sentence written for a world that
    declared nothing, three false clauses. It now names the one predicate standing in the
    way, which is the same absence `world accept` names when it declines to mint the scale.
    """
    world = _drawn_world(_system())
    assert gs.systems_of(world) == ()
    gap = genre.system_gap(world)
    assert gap is not None and gs.MAGNITUDE_SCALE in gap
    assert "declares no game system" not in gap
    assert "seeded by hand" not in gap


def test_a_finished_world_has_no_unfinished_systems_to_report() -> None:
    """The quiet half of the teller: complete systems contribute nothing, so the report side
    stays on the branch it was on and a finished book's `world check` does not change."""
    assert gs.unfinished_systems(_canon(list(gs.records_for(_system())))) == ()


def test_a_ladder_whose_issuer_is_never_declared_a_system_is_told_the_role_it_lacks() -> None:
    """The other partial shape: everything present except the role. Naming the scale here
    would be §155.2 again with a new word — the clause must be the piece actually missing."""
    world = _canon(
        [
            record
            for record in gs.records_for(_system())
            if not (record.predicate == worlds.ENTITY_ROLE_PREDICATE and record.value == "system")
        ]
    )
    assert gs.systems_of(world) == ()
    gap = genre.system_gap(world)
    assert gap is not None and worlds.ENTITY_ROLE_PREDICATE in gap
    assert gs.MAGNITUDE_SCALE not in gap


def test_a_system_whose_ladder_is_ungoverned_is_told_the_ladder_and_not_the_scale() -> None:
    world = _canon(
        [
            record
            for record in gs.records_for(_system())
            if not (
                record.predicate == worlds.GOVERNED_BY and record.subject == _system().criterion
            )
        ]
    )
    gap = genre.system_gap(world)
    assert gap is not None and worlds.GOVERNED_BY in gap
    assert gs.MAGNITUDE_SCALE not in gap


def test_two_ladders_under_one_system_are_named_rather_than_read_as_no_system() -> None:
    """`_assemble` abstains at two governed criteria rather than choose, which used to land
    this world in the declared-nothing sentence by the other door."""
    world = _canon(list(gs.records_for(_system())))
    world.extend(
        _canon(
            [
                worlds.world_record("second_path", worlds.TYPE_PREDICATE, value=worlds.CRITERION),
                worlds.world_record("second_path", worlds.COMPARATOR_PREDICATE, value="ordinal"),
                worlds.world_record("second_path", worlds.GOVERNED_BY, object_ref="the_weave"),
            ]
        )
    )
    assert gs.systems_of(world) == ()
    gap = genre.system_gap(world)
    assert gap is not None and "2 criteria" in gap


def test_a_proposed_partial_system_is_not_reported_as_unfinished() -> None:
    """`_declared_systems`' reason, on the other half of the branch: a proposal is not yet
    this book's system, and an Architect mid-build is the ordinary state and never a fault."""
    proposed = [
        record
        for record in gs.records_for(_system())
        if record.predicate not in gs.CONFIGURATION_PREDICATES
    ]
    gap = genre.system_gap(proposed)
    assert gap is not None and "declares no game system" in gap


def test_a_world_that_declared_nothing_keeps_the_sentence_written_for_it() -> None:
    """The split may not move the genuinely-empty audience: a hand-seeded book still reads
    the declares-no-game-system report, not a claim that it began a system."""
    legacy = _canon([worlds.world_record("sera", "status_snapshot", value={"level": 1})])
    gap = genre.system_gap(legacy)
    assert gap is not None and "declares no game system" in gap
    assert "did not finish" not in gap


def test_accepting_a_drawn_system_mints_the_scale_its_own_numbers_imply() -> None:
    """And exactly two records, both of them the ones only `records_for` can mint.

    The structure is already in canon and is not re-declared; in particular no second
    `status_sheet` is minted, because a book that declared its own would then have two and
    `sheet_for` abstains to the generic line when it does.
    """
    world = _drawn_world(_system())
    world.extend(
        _canon([worlds.world_record("silas", worlds.CAN_DO, object_ref="seamsight", value=6)])
    )
    minted, reasons = gs.completion_records(world)
    assert reasons == ()
    assert {record.predicate for record in minted} == set(gs.CONFIGURATION_PREDICATES)
    assert all(record.subject == "the_weave" for record in minted)
    scale = next(record for record in minted if record.predicate == gs.MAGNITUDE_SCALE)
    assert scale.value == {"label": "the Weave", "maximum": 6}
    assert not any(record.predicate == "status_sheet" for record in minted)

    finished = [*world, *_canon(list(minted))]
    declared = gs.systems_of(finished)
    assert len(declared) == 1
    assert declared[0].scale.maximum == 6
    assert gs.check_draw(declared[0]) == ()


def test_the_depth_is_read_off_both_slots_and_never_invented() -> None:
    """`can_do` says how far somebody has taken a capability and `requires` how far one must be
    taken; a scale that did not contain both is one `check_draw` refuses on the world's own
    numbers. The higher of the two wins because both are assertions this world already made."""
    world = _drawn_world(_system())
    world.extend(
        _canon([worlds.world_record("silas", worlds.CAN_DO, object_ref="threadpull", value=4)])
    )
    minted, _ = gs.completion_records(world)
    scale = next(record for record in minted if record.predicate == gs.MAGNITUDE_SCALE)
    assert scale.value == {"label": "the Weave", "maximum": 4}


def test_a_world_that_declared_no_depth_is_told_why_rather_than_given_a_default() -> None:
    """The refusal that keeps this from authoring world facts.

    A world whose capabilities are held-or-not never expressed a depth, and `MIN_SCALE_MAXIMUM`'s
    own reason says a scale of one is a decoration. Minting one would invent the single dimension
    the world declined to have, so the gap stays open and the reason is named.
    """
    world = _drawn_world(
        _system(
            abilities=(
                gs.Ability("seamsight", "Seamsight"),
                gs.Ability("threadpull", "Threadpull"),
                gs.Ability("stillwater", "Stillwater", needs=(gs.Need("seamsight"),)),
                gs.Ability("lanterncall", "Lanterncall", needs=(gs.Need("threadpull"),)),
                gs.Ability("deepweave", "Deepweave", needs=(gs.Need("stillwater"),)),
            )
        )
    )
    minted, reasons = gs.completion_records(world)
    assert minted == ()
    assert len(reasons) == 1
    assert "declares no depth" in reasons[0]
    assert gs.systems_of(world) == ()


def test_a_system_that_is_already_finished_is_left_alone() -> None:
    """Idempotent, and the reason is the two-writers hazard: a second scale beside the drawn one
    is exactly what §163.2 keeps the predicate undocumented to prevent."""
    minted, reasons = gs.completion_records(_seeded(_system()))
    assert minted == ()
    assert reasons == ()


def test_a_finished_system_whose_sheet_is_the_books_own_closes_the_gap() -> None:
    """The whole point: a book that is a position in the system it declared has no gap left."""
    world = _drawn_world(_system())
    world.extend(_canon(list(gs.records_for_sheet(gs.starting_sheet(_system(), "silas")))))
    world.extend(
        _canon([worlds.world_record("silas", worlds.CAN_DO, object_ref="seamsight", value=3)])
    )
    minted, reasons = gs.completion_records(world)
    assert reasons == ()
    finished = [*world, *_canon(list(minted))]
    assert genre.system_gap(finished) is None


def test_a_drawn_system_declares_that_unheld_columns_do_not_print() -> None:
    """§203: the snapshot still carries every ability at 0 (the arithmetic and the digest are
    unchanged), and the declaration says the line prints the rung and what is held; a sheet on
    disk declared without the flag prints everything, as it always did."""
    from litharness.domain import extraction

    system = _system()
    declared = system.sheet_declaration()
    assert declared["show_unheld"] is False
    sheet = extraction.parse_sheet(declared)
    starting = gs.starting_sheet(system, "silas")
    assert 0 in starting.snapshot().values(), "the snapshot keeps the unheld at zero"
    line = sheet.render("Silas", starting.snapshot())
    assert " 0" not in line and line.startswith("[STATUS] Silas — ")
    assert sheet.read(line)[0][1] == {k: v for k, v in starting.snapshot().items() if v}
    without_flag = {"fields": declared["fields"]}
    assert extraction.parse_sheet(without_flag).show_unheld is True


# ----------------------------------------------------------------- §207: the choice display


def _forked(*, text: bool = False, gated: bool = False) -> gs.SystemDef:
    """The weave with one fork at the first seal: Kiln opens Deepweave, Reed opens Lanterncall.
    With `text`, each way says what it looks like; with `gated`, Kiln needs Seamsight at 2."""
    kiln = gs.Option(
        "opt_kiln",
        "Kiln",
        grants=("deepweave",),
        manifests_as="the left glove goes stiff and warm" if text else None,
        needs=(gs.Need("seamsight", 2),) if gated else (),
    )
    reed = gs.Option(
        "opt_reed",
        "Reed",
        grants=("lanterncall",),
        manifests_as="a reed whistle grows in the palm" if text else None,
    )
    return _system(
        choices=(gs.Choice("fork_hand", "Hand", options=(kiln, reed), opens_at="first_seal"),)
    )


def test_a_way_s_text_and_needs_round_trip_and_a_fork_without_them_keeps_its_digest() -> None:
    """§207: what a way looks like and what it needs travel as records the vocabulary already
    has (`manifests_as`, `requires`); a fork written before this reads back unchanged and its
    digest is the digest it had."""
    plain = _forked()
    assert plain.digest == gs.systems_of(gs.records_for(plain))[0].digest
    material_before = plain.digest
    assert _forked().digest == material_before, "the digest is stable without text or needs"
    rich = _forked(text=True, gated=True)
    [back] = gs.systems_of(gs.records_for(rich))
    assert back == rich and back.digest == rich.digest and back.digest != plain.digest
    kiln = back.choice("fork_hand").option("opt_kiln")
    assert kiln.manifests_as == "the left glove goes stiff and warm"
    assert kiln.needs == (gs.Need("seamsight", 2),)
    assert gs.check_draw(rich) == ()
    bad = _system(
        choices=(
            gs.Choice(
                "fork_hand",
                "Hand",
                options=(
                    gs.Option(
                        "opt_kiln", "Kiln", grants=("deepweave",), needs=(gs.Need("nothing"),)
                    ),
                    gs.Option("opt_reed", "Reed", grants=("lanterncall",)),
                ),
                opens_at="first_seal",
            ),
        )
    )
    assert any("needs nothing" in complaint for complaint in gs.check_draw(bad))


def test_a_gated_way_is_offered_only_to_a_person_who_meets_its_need() -> None:
    """§207: the fork a person meets is the one their own record earned. Kiln needs Seamsight
    at 2; a person at the first seal with Seamsight at 1 is offered Reed alone, is refused
    Kiln, and once Seamsight reaches 2 is offered both."""
    system = _forked(text=True, gated=True)
    at_seal = gs.rise(gs.starting_sheet(system, "silas"), at="s1").sheet
    assert at_seal.magnitude("seamsight") == 1
    [fork] = gs.pending_choices(at_seal)
    assert [option.name for option in gs.offered_options(at_seal, fork)] == ["Reed"]
    line = gs.offer_line(system, fork, sheet=at_seal)
    assert line == "[OFFER] Hand — Reed: opens Lanterncall; a reed whistle grows in the palm"
    with pytest.raises(gs.IllegalAdvance, match="needs seamsight at 2"):
        gs.choose(at_seal, "fork_hand", "opt_kiln", at="s2")
    deeper = gs.deepen(at_seal, "seamsight", at="s2").sheet
    assert [option.name for option in gs.offered_options(deeper, fork)] == ["Kiln", "Reed"]
    assert "Kiln: opens Deepweave; the left glove" in gs.offer_line(system, fork, sheet=deeper)
    taken = gs.choose(deeper, "fork_hand", "opt_kiln", at="s3").sheet
    assert taken.took("fork_hand") == "opt_kiln"


def test_a_fork_none_of_whose_ways_is_offered_is_not_open_yet() -> None:
    system = _system(
        choices=(
            gs.Choice(
                "fork_hand",
                "Hand",
                options=(
                    gs.Option(
                        "opt_kiln", "Kiln", grants=("deepweave",), needs=(gs.Need("seamsight", 3),)
                    ),
                    gs.Option(
                        "opt_reed",
                        "Reed",
                        grants=("lanterncall",),
                        needs=(gs.Need("threadpull", 3),),
                    ),
                ),
                opens_at="first_seal",
            ),
        )
    )
    at_seal = gs.rise(gs.starting_sheet(system, "silas"), at="s1").sheet
    assert gs.pending_choices(at_seal) == ()
    assert gs.offer_line(system, system.choices[0]) == (
        "[OFFER] Hand — Kiln: opens Deepweave | Reed: opens Lanterncall"
    ), "without a sheet the line shows every way, as it always did"


# --- §210: a grant the rungs hand out, and a grant that is paid in it ----------------------


def _stocked() -> gs.SystemDef:
    """The weave with a stock: every seal hands out two Marks, and Threadpull is paid one
    Mark at every gain and deepen (§210). Six grants, one edge short of nothing."""
    return _system(
        abilities=(
            gs.Ability("seamsight", "Seamsight"),
            gs.Ability("threadpull", "Threadpull", price=(("marks", 1),)),
            gs.Ability("stillwater", "Stillwater", needs=(gs.Need("seamsight", 2),)),
            gs.Ability("lanterncall", "Lanterncall", needs=(gs.Need("threadpull"),)),
            gs.Ability(
                "deepweave",
                "Deepweave",
                needs=(gs.Need("first_seal"), gs.Need("stillwater")),
            ),
            gs.Ability("marks", "Marks", per_rung=2),
        )
    )


def test_a_stock_opens_at_nothing_and_is_never_a_move_of_its_own() -> None:
    """§210: a grant the rungs hand out is not an opener, and no gain or deepen names it."""
    system = _stocked()
    assert gs.check_draw(system) == ()
    sheet = gs.starting_sheet(system, "silas")
    assert sheet.magnitude("marks") == 0
    assert sheet.magnitude("threadpull") == 1, "an opener is held from the start, unpaid"
    assert all(move.ability_id != "marks" for move in gs.legal_moves(sheet))
    with pytest.raises(gs.IllegalAdvance, match="handed out by the rungs"):
        gs.gain(sheet, "marks", at="s1")
    with pytest.raises(gs.IllegalAdvance, match="handed out by the rungs"):
        gs.deepen(sheet, "marks", at="s1")


def test_a_rise_hands_out_the_stock_and_a_paid_grant_takes_it_back() -> None:
    """§210: the rise credits every stock and the paid move debits it; both columns move,
    both are written down, and a move that cannot be paid is neither offered nor taken."""
    system = _stocked()
    start = gs.starting_sheet(system, "silas")
    assert all(move.ability_id != "threadpull" for move in gs.legal_moves(start))
    with pytest.raises(gs.IllegalAdvance, match="costs 1 marks, and silas has 0"):
        gs.deepen(start, "threadpull", at="s1")

    risen = gs.rise(start, at="s1")
    assert risen.moved == (gs.RANK_KEY, "marks")
    assert risen.sheet.magnitude("marks") == 2
    credited = [
        record
        for record in risen.records
        if record.predicate == worlds.CAN_DO and record.object_ref == "marks"
    ]
    assert [record.value for record in credited] == [2]

    offered = [move for move in gs.legal_moves(risen.sheet) if move.ability_id == "threadpull"]
    assert [move.kind for move in offered] == [gs.AdvanceKind.DEEPEN]
    paid = gs.deepen(risen.sheet, "threadpull", at="s2")
    assert paid.moved == ("marks", "threadpull")
    assert (paid.sheet.magnitude("threadpull"), paid.sheet.magnitude("marks")) == (2, 1)
    written = {
        record.object_ref: record.value
        for record in paid.records
        if record.predicate == worlds.CAN_DO
    }
    assert written == {"threadpull": 2, "marks": 1}
    assert gs.advance(paid.sheet, offered[0], at="s3").sheet.magnitude("marks") == 0
    with pytest.raises(gs.IllegalAdvance, match="costs 1 marks"):
        gs.deepen(gs.advance(paid.sheet, offered[0], at="s3").sheet, "threadpull", at="s4")


def test_a_stock_and_a_price_round_trip_and_a_system_without_them_keeps_its_digest() -> None:
    """§210: `per_rung` and a priced `costs` travel as records and read back; every system
    written before this has the digest it had."""
    plain = _system()
    assert plain.digest == gs.systems_of(gs.records_for(plain))[0].digest
    rich = _stocked()
    [back] = gs.systems_of(gs.records_for(rich))
    assert back == rich and back.digest == rich.digest and back.digest != plain.digest
    assert back.ability("marks").per_rung == 2
    assert back.ability("threadpull").price == (("marks", 1),)
    assert back.ability("threadpull").costs is None, "a price is not prose about a price"
    priced = [
        record
        for record in gs.records_for(rich)
        if record.predicate == worlds.COSTS and record.subject == "threadpull"
    ]
    assert [(record.object_ref, record.value) for record in priced] == [("marks", 1)]


def test_check_draw_refuses_a_stock_or_a_price_that_could_not_work() -> None:
    """§210: every refusal is membership or arithmetic — a price in a grant no rung hands
    out, a stock that needs or is gated or is priced, a rung handing out less than nothing."""

    def abilities(**changes: gs.Ability) -> tuple[gs.Ability, ...]:
        base = {ability.ability_id: ability for ability in _stocked().abilities}
        base.update(changes)
        return tuple(base.values())

    unbacked = _system(
        abilities=abilities(
            threadpull=gs.Ability("threadpull", "Threadpull", price=(("seamsight", 1),))
        )
    )
    assert any("no rung hands out" in why for why in gs.check_draw(unbacked))
    unknown = _system(
        abilities=abilities(threadpull=gs.Ability("threadpull", "Threadpull", price=(("coin", 1),)))
    )
    assert any("declares as no grant" in why for why in gs.check_draw(unknown))
    free = _system(
        abilities=abilities(
            threadpull=gs.Ability("threadpull", "Threadpull", price=(("marks", 0),))
        )
    )
    assert any("one or more" in why for why in gs.check_draw(free))
    needy = _system(
        abilities=abilities(
            marks=gs.Ability("marks", "Marks", per_rung=2, needs=(gs.Need("seamsight"),))
        )
    )
    assert any("nobody gains has no prerequisite" in why for why in gs.check_draw(needy))
    priced_stock = _system(
        abilities=abilities(marks=gs.Ability("marks", "Marks", per_rung=2, price=(("marks", 1),)))
    )
    assert any("never paid for" in why for why in gs.check_draw(priced_stock))
    negative = _system(abilities=abilities(marks=gs.Ability("marks", "Marks", per_rung=-1)))
    assert any("nothing or more" in why for why in gs.check_draw(negative))
    gated = _system(
        abilities=abilities(),
        choices=(
            gs.Choice(
                "fork_hand",
                "Hand",
                options=(
                    gs.Option("opt_kiln", "Kiln", grants=("marks",)),
                    gs.Option("opt_reed", "Reed", grants=("lanterncall",)),
                ),
                opens_at="first_seal",
            ),
        ),
    )
    assert any("cannot be opened by a way" in why for why in gs.check_draw(gated))


# --- §211: a system grows after the seed, and the sheet it minted follows it --------------


def _grown(records: list[lc.StateRecord]) -> list[lc.StateRecord]:
    """The weave with a sixth grant declared after the seed, the way the grow step declares
    one: a capability, its name, its system, and what it needs first."""
    return records + _canon(
        [
            worlds.world_record("windread", worlds.ENTITY_ROLE_PREDICATE, value="capability"),
            worlds.world_record("windread", "is_a", value="Windread"),
            worlds.world_record("windread", worlds.GOVERNED_BY, object_ref="the_weave"),
            worlds.world_record("windread", worlds.REQUIRES, object_ref="seamsight"),
        ]
    )


def test_the_sheet_a_system_minted_follows_the_system_as_it_grows() -> None:
    """§211: a grant declared after the seed is a column the moment it is declared; the
    seed's own sheet record is untouched, and a sheet naming no system keeps its fields
    whatever the world goes on to declare (every sheet written before this)."""
    from litharness.domain import extraction

    seeded = _seeded(_system())
    before = extraction.sheet_for(seeded)
    assert before is not None and before.system == "the_weave"
    assert "windread" not in before.value_keys

    grown = _grown(seeded)
    [system] = gs.systems_of(grown)
    assert "windread" in system.ability_ids
    after = extraction.sheet_for(grown)
    assert after is not None
    assert after.value_keys == system.value_keys and "windread" in after.value_keys
    assert after.show_unheld is False and after.system == "the_weave"
    minted = [record for record in grown if record.predicate == extraction.SHEET_PREDICATE]
    assert minted == [record for record in seeded if record.predicate == extraction.SHEET_PREDICATE]

    [record] = minted
    assert isinstance(record.value, dict)
    legacy_value = {key: value for key, value in record.value.items() if key != "system"}
    legacy = [r for r in grown if r.predicate != extraction.SHEET_PREDICATE] + [
        dataclasses.replace(record, value=legacy_value)
    ]
    kept = extraction.sheet_for(legacy)
    assert kept is not None and kept.system is None
    assert kept.value_keys == before.value_keys


def test_a_grown_grant_is_offered_and_printed_and_the_count_bound_is_the_draws() -> None:
    """§211: the beat vocabulary offers the new grant once its need is met, the line prints
    it once held, `growth` names the system and finds nothing wrong with it, and the five to
    eight bound holds on the draw and not on the book."""
    from litharness.domain import extraction

    grown = _grown(_seeded(_system()))
    assert extraction.Movable("Windread", "windread") in extraction.movables(
        grown, character="silas", at="s1"
    )
    [system] = gs.systems_of(grown)
    sheet = gs.sheet_of(grown, "silas", system=system, at="s1")
    assert sheet is not None
    gained = gs.gain(sheet, "windread", at="s1")
    line = extraction.render_status_line(
        "silas", gained.after, sheet=extraction.sheet_for(grown), records=grown
    )
    assert "Windread 1" in line

    [(found, wrong)] = gs.growth(grown)
    assert found.system_id == "the_weave" and wrong == ()
    assert gs.growth(_seeded(_system())) == ()

    extras = tuple(
        gs.Ability(f"extra_{index}", f"Extra {word}")
        for index, word in enumerate(("One", "Two", "Three", "Four"))
    )
    nine = _system(abilities=(*_system().abilities, *extras))
    assert any("5 to 8" in why for why in gs.check_draw(nine))
    assert not any("5 to 8" in why for why in gs.check_draw(nine, drawn=False))
