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
            gs.Ability(ability.ability_id, ability.name)
            for ability in _system().abilities
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
        worlds.world_record(
            "cap_read_a_seam", worlds.ENTITY_ROLE_PREDICATE, value="capability"
        ),
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
    clash = _system(
        abilities=(*_system().abilities[:-1], gs.Ability(gs.RANK_KEY, "Rank"))
    )
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
    """An unheld ability at 0 is the design, not a gap: it is the operator's "I wonder what I
    would pick" expressed as a number rather than as an adjective, and it keeps the line's
    shape constant for a whole book, which a single declared `status_sheet` requires."""
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
    legacy = _canon(
        [worlds.world_record("sera", "status_snapshot", value={"level": 1, "hp": 3})]
    )
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
    records.extend(
        _canon([worlds.world_record("silas", "status_snapshot", value={"level": 1})])
    )
    assert not genre.has_starting_sheet(records)
    block = genre.genre_block(records)
    assert block is not None and "different books" in block


def test_a_proposed_system_does_not_tighten_the_floor() -> None:
    """The Architect builds a system before `world accept`, and refusing a book for a draw
    nobody accepted would gate on a proposal."""
    records = list(gs.records_for(_system()))
    records.extend(
        _canon([worlds.world_record("silas", "status_snapshot", value={"level": 1})])
    )
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
    `systems_of` requires a magnitude scale, the Architect has no documented way to write one,
    and so the book is told it declares no game system at all.
    """
    world = _drawn_world(_system())
    assert gs.systems_of(world) == ()
    gap = genre.system_gap(world)
    assert gap is not None and "declares no game system" in gap


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
