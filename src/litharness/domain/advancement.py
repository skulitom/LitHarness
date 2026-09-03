"""Advancing a sheet: what a person may take next, what it costs, and the four moves that take it.

Split out of `domain/gamesystem.py` on 2026-09-03 (stage-0 §216) with every definition
byte-identical, and re-exported from there. `legal_moves` returns what is arithmetically
available, in declaration order, and ranks nothing (§61(5)); `gain`, `deepen`, `rise` and
`choose` run through one private builder so what the four write down cannot drift; the
`[OFFER]` line is the one printed form here and `offer_line` composes it from names the world
declared. The design's reasons live in `gamesystem`'s module docstring, which holds across
the three modules.
"""

from __future__ import annotations

from collections.abc import Sequence

import litharness_contracts as lc

from litharness.domain import worlds as worlds_mod
from litharness.domain.systems import (
    Ability,
    AdvanceKind,
    Advancement,
    CharacterSheet,
    Choice,
    IllegalAdvance,
    Move,
    Need,
    Option,
    SystemDef,
    _snapshot_record,
)

# --------------------------------------------------------------------------- advancing a sheet


def offered_options(sheet: CharacterSheet, choice: Choice) -> tuple[Option, ...]:
    """The ways of a fork this person may be offered: those whose needs the sheet meets
    (§207). A way with no needs is offered to everyone who reached the fork; a fork none
    of whose ways is offered is not open to this person yet."""
    return tuple(
        option for option in choice.options if not _unmet(sheet, option.option_id, option.needs)
    )

def _needs_met(sheet: CharacterSheet, ability: Ability) -> tuple[str, ...]:
    """Which of an ability's prerequisites this sheet does not meet, as reasons. Empty means met.

    **This is the arithmetic §114.6 asked for.** A threshold that nothing compared against was
    the "decoration" that entry refused; here the comparison is what decides whether a move is
    legal, so the number does work before it is ever printed.
    """
    return _unmet(sheet, ability.ability_id, ability.needs)

def _unmet(sheet: CharacterSheet, what: str, needs: Sequence[Need]) -> tuple[str, ...]:
    """The needs of `what` this sheet does not meet, as reasons; an ability's or a way's."""
    unmet: list[str] = []
    system = sheet.system
    for need in needs:
        if need.ref in set(system.rank_ids):
            if system.rank_index(sheet.rank_id) < system.rank_index(need.ref):
                unmet.append(
                    f"{what} needs the rung {need.ref}, and {sheet.character} "
                    f"stands at {sheet.rank_id}"
                )
            continue
        have = sheet.magnitude(need.ref)
        if have < need.threshold:
            unmet.append(
                f"{what} needs {need.ref} at {need.threshold}, and "
                f"{sheet.character} has it at {have}"
            )
    return tuple(unmet)

def _unpaid(sheet: CharacterSheet, ability: Ability) -> tuple[str, ...]:
    """What this sheet cannot pay of the grant's price, as reasons; empty means paid (§210).

    The same arithmetic as `_unmet`, on the other side of the move: a need is what must already
    be held, a price is what is taken. A move that cannot be paid is not offered, for the
    reason a gated one is not — a schedule built on a label names moves the book cannot make.
    """
    unpaid: list[str] = []
    for stock, amount in ability.price:
        have = sheet.magnitude(stock)
        if have < amount:
            unpaid.append(
                f"{ability.ability_id} costs {amount} {stock}, and {sheet.character} has {have}"
            )
    return tuple(unpaid)

def legal_moves(sheet: CharacterSheet) -> tuple[Move, ...]:
    """Every advancement arithmetically available to this sheet, in declaration order.

    **Declaration order, and no ordering of any other kind** (§61(5)). This returns what is
    possible; it does not say which is best, most dramatic or most earned, and there is no
    function in this module that does. A caller that wants one of them chooses by its own rule —
    a schedule, a plan, a beat — and never by asking this module to rank.

    **A gated ability is not offered until its fork has been taken.** That is the same class of
    knowledge as an unmet prerequisite, which §161.4 records as the reason the system arm of the
    beat vocabulary is strictly better than a column label: a label cannot know that a move is
    unavailable, so a schedule built on one names moves the book cannot make. A fork is one more
    thing a label cannot know.

    Order is abilities, then forks, then the rise: a fork is a thing that happens *to* the
    inventory, so it reads beside it, and the rise stays last where it has always been.
    """
    moves: list[Move] = []
    system = sheet.system
    for ability in system.abilities:
        if ability.is_stock:
            # A stock moves with the rungs and with what is paid in it, never by a move of
            # its own (§210); a beat can therefore never name one.
            continue
        held = sheet.magnitude(ability.ability_id)
        if held == 0:
            if (
                sheet.unlocked(ability.ability_id)
                and not _needs_met(sheet, ability)
                and not _unpaid(sheet, ability)
            ):
                moves.append(Move(AdvanceKind.GAIN, ability_id=ability.ability_id))
        elif held < system.scale.maximum and not _unpaid(sheet, ability):
            # **Deepening a held ability is never re-gated**, on `deepen`'s own rule: the gate is
            # the condition for having it at all, and re-asking would make a sheet's past illegal
            # whenever the world's declaration moved underneath it.
            moves.append(Move(AdvanceKind.DEEPEN, ability_id=ability.ability_id))
    for choice in _open_choices(sheet):
        moves.append(Move(AdvanceKind.CHOOSE, choice_id=choice.choice_id))
    index = system.rank_index(sheet.rank_id)
    if index < len(system.ranks):
        moves.append(Move(AdvanceKind.RISE, rank_id=system.rank_ids[index]))
    return tuple(moves)

def _open_choices(sheet: CharacterSheet) -> tuple[Choice, ...]:
    """The forks this person has reached and not yet taken, in declaration order."""
    system = sheet.system
    standing = system.rank_index(sheet.rank_id)
    return tuple(
        choice
        for choice in system.choices
        if sheet.took(choice.choice_id) is None
        and (
            choice.opens_at is None
            or (
                choice.opens_at in set(system.rank_ids)
                and system.rank_index(choice.opens_at) <= standing
            )
        )
        # A fork none of whose ways this person may be offered is not open to them (§207).
        and offered_options(sheet, choice)
    )

#: The line the book prints where a fork is put in front of a person. Bracketed like the
#: status line so `draft`'s em-dash strip and the reviser's containment both read it as the
#: book speaking as a machine (`_MACHINE_LINE`'s shape), and tagged differently so
#: `extraction` never parses it: the status line is the one parsed surface (§160.3) and this
#: is furniture the reader watches, never a record.
OFFER_TAG = "[OFFER]"

def offer_line(system: SystemDef, choice: Choice, *, sheet: CharacterSheet | None = None) -> str:
    """The fork as the book prints it: the fork's name, then each way and what it opens.

    **Every word on the line is the book's own** — the fork's name, the ways' names, the
    abilities' names, and a way's price where the system declared one — joined by grammar and
    nothing else. Nothing here says which way; the ways come in the fork's own order, which is
    id order, the same order `Choice.options` holds them in (§61(5): no ordering of any other
    kind). An ability an option grants that the system does not declare is a defect
    `check_draw` refuses, so it is named here by id rather than swallowed.
    """
    by_id = {ability.ability_id: ability.name for ability in system.abilities}
    ways = []
    # With a sheet, only the ways offered to that person print (§207); without one, all.
    options = offered_options(sheet, choice) if sheet is not None else choice.options
    for option in options:
        opens = ", ".join(by_id.get(ability_id, ability_id) for ability_id in option.grants)
        way = f"{option.name}: opens {opens}" if opens else option.name
        if option.costs:
            way = f"{way}, costs {option.costs}"
        if option.manifests_as:
            way = f"{way}; {option.manifests_as}"
        ways.append(way)
    return f"{OFFER_TAG} {choice.name} — " + " | ".join(ways)

def pending_choices(sheet: CharacterSheet) -> tuple[Choice, ...]:
    """The forks standing open in front of this person, in declaration order.

    **This is the deliberation surface, and it is deliberately a list of forks rather than a
    recommendation.** Read 10's direction is that weighing what to take next is a large part of
    the story; what a story needs for that is the fork and its ways on the page, which is what
    this returns. Nothing here says which way, and nothing in this module can be asked (§61(5)).

    **A fork opens because the person got to the rung, never because the book got to a scene.**
    §110.3 measured position-implies-settlement failing in both directions inside one run, and
    §167 settled the same question for disclosure: a schedule is a statement of intent, and intent
    is not an event. Here the event is the standing the sheet already carries, so this needs no
    story position at all and cannot leak one.
    """
    return _open_choices(sheet)

def _advanced(
    sheet: CharacterSheet,
    kind: AdvanceKind,
    *,
    at: str,
    rank_id: str | None = None,
    ability_id: str | None = None,
    magnitude: int | None = None,
    choice_id: str | None = None,
    option_id: str | None = None,
) -> Advancement:
    """The one place a new sheet, its moved keys and its records are built together.

    Four entry points share it so the four moves cannot drift in what they write down — the
    defect `genre.with_beat` avoids by the same means, one function two call sites.
    """
    before = sheet.snapshot()
    if kind is AdvanceKind.RISE:
        assert rank_id is not None
        after_sheet = CharacterSheet(
            system=sheet.system,
            character=sheet.character,
            rank_id=rank_id,
            magnitudes=_credited(sheet),
            visible_to=sheet.visible_to,
            picks=sheet.picks,
        )
    elif kind is AdvanceKind.CHOOSE:
        assert choice_id is not None and option_id is not None
        after_sheet = CharacterSheet(
            system=sheet.system,
            character=sheet.character,
            rank_id=sheet.rank_id,
            magnitudes=sheet.magnitudes,
            visible_to=sheet.visible_to,
            picks=(*sheet.picks, (choice_id, option_id)),
        )
    else:
        assert ability_id is not None and magnitude is not None
        after_sheet = CharacterSheet(
            system=sheet.system,
            character=sheet.character,
            rank_id=sheet.rank_id,
            magnitudes=_paid(sheet, ability_id, magnitude),
            visible_to=sheet.visible_to,
            picks=sheet.picks,
        )
    after = after_sheet.snapshot()
    moved = tuple(key for key in after if after[key] != before.get(key))

    records: list[lc.StateRecord] = []
    if kind is AdvanceKind.RISE:
        records.append(
            worlds_mod.world_record(
                sheet.character,
                worlds_mod.STANDS_AT_PREDICATE,
                value=sheet.system.criterion,
                object_ref=rank_id,
                order_key=at,
                pov_visibility=sheet.visible_to,
            )
        )
    elif kind is AdvanceKind.CHOOSE:
        # **The pick, and no snapshot beside it.** Every other move writes the edge that changed
        # plus the line it renders; a choice changes no number, so the snapshot would restate a
        # value already on record — and `worlds.record_id_for` is position-blind under an
        # `INSERT OR IGNORE` store, so the restatement would be silently dropped anyway. §160
        # found that the hard way when the first `_advanced` rewrote the whole sheet at every
        # advancement and was discarding most of what it claimed to write. Writing the one thing
        # that happened says what happened.
        records.append(
            worlds_mod.world_record(
                sheet.character,
                worlds_mod.CHOSE,
                value=choice_id,
                object_ref=option_id,
                order_key=at,
                pov_visibility=sheet.visible_to,
            )
        )
        return Advancement(
            kind=kind,
            sheet=after_sheet,
            moved=moved,
            before=before,
            after=after,
            records=tuple(records),
        )
    else:
        records.append(
            worlds_mod.world_record(
                sheet.character,
                worlds_mod.CAN_DO,
                value=magnitude,
                object_ref=ability_id,
                order_key=at,
                pov_visibility=sheet.visible_to,
            )
        )
    # **Only what changed, plus the line it renders.** The first version rewrote the whole
    # sheet at every advancement, and running it showed why that is wrong: `worlds.record_id_for`
    # keys on `(subject, predicate, object_ref, value)` and **not** on the order key — unlike
    # `extraction.record_id_for`, which includes it deliberately — so an unchanged holding
    # rewritten at a later position is the *same record id*, and `record_state_records` is
    # `INSERT OR IGNORE`. The rewrite was therefore silently dropped, which is harmless and
    # completely illegible: the record set claimed to restate the sheet and did not. Writing the
    # one edge that moved says what actually happened, and the unchanged holdings keep the
    # position they were established at, which is what they mean.
    # **Every stock the move changed is written down beside it** (§210): what a rise handed
    # out and what a paid move took, one `can_do` edge each, for `sheet_of`'s reason — the
    # snapshot is the printed form and the edges are what the world knows. A stock spent to
    # nothing is written at 0, which `sheet_of` reads as held at nothing.
    for stock in sheet.system.stocks:
        if stock in moved:
            records.append(
                worlds_mod.world_record(
                    sheet.character,
                    worlds_mod.CAN_DO,
                    value=after_sheet.magnitude(stock),
                    object_ref=stock,
                    order_key=at,
                    pov_visibility=sheet.visible_to,
                )
            )
    records.append(_snapshot_record(after_sheet, at=at))
    return Advancement(
        kind=kind,
        sheet=after_sheet,
        moved=moved,
        before=before,
        after=after,
        records=tuple(records),
    )

def _credited(sheet: CharacterSheet) -> tuple[tuple[str, int], ...]:
    """The magnitudes after a rise: every stock up by what a rung hands out (§210)."""
    per_rung = {
        ability.ability_id: ability.per_rung
        for ability in sheet.system.abilities
        if ability.is_stock
    }
    return tuple((held_id, value + per_rung.get(held_id, 0)) for held_id, value in sheet.magnitudes)

def _paid(sheet: CharacterSheet, ability_id: str, magnitude: int) -> tuple[tuple[str, int], ...]:
    """The magnitudes after a gain or a deepen: the grant at its new depth, and every stock it
    is paid in down by its price (§210). `_unpaid` has already said the price can be met."""
    debit = dict(sheet.system.ability(ability_id).price)
    return tuple(
        (held_id, magnitude if held_id == ability_id else value - debit.get(held_id, 0))
        for held_id, value in sheet.magnitudes
    )

def _never_a_move(sheet: CharacterSheet, ability: Ability) -> None:
    """A stock is handed out by the rungs and is never gained or deepened (§210)."""
    if ability.is_stock:
        raise IllegalAdvance(
            f"{ability.ability_id} is handed out by the rungs, {ability.per_rung} at each, "
            f"and is never gained or deepened; {sheet.character} has "
            f"{sheet.magnitude(ability.ability_id)}"
        )

def gain(sheet: CharacterSheet, ability_id: str, *, at: str) -> Advancement:
    """Take an ability from 0 to 1. Raises `IllegalAdvance` when a prerequisite is unmet."""
    ability = sheet.system.ability(ability_id)
    _never_a_move(sheet, ability)
    if sheet.holds(ability_id):
        raise IllegalAdvance(
            f"{sheet.character} already holds {ability_id} at {sheet.magnitude(ability_id)}"
        )
    unmet = _needs_met(sheet, ability)
    if unmet:
        raise IllegalAdvance("; ".join(unmet))
    if unpaid := _unpaid(sheet, ability):
        raise IllegalAdvance("; ".join(unpaid))
    return _advanced(sheet, AdvanceKind.GAIN, at=at, ability_id=ability_id, magnitude=1)

def deepen(sheet: CharacterSheet, ability_id: str, *, at: str) -> Advancement:
    """Take a held ability one step further. Raises `IllegalAdvance` at 0 or at the maximum.

    Prerequisites are checked at `gain` and not re-checked here: they are the condition for
    having the ability at all, and re-asking would make a sheet's own past illegal whenever a
    world's declaration changed underneath it.
    """
    ability = sheet.system.ability(ability_id)
    _never_a_move(sheet, ability)
    held = sheet.magnitude(ability_id)
    if held < 1:
        raise IllegalAdvance(
            f"{sheet.character} does not hold {ability_id}, so there is nothing to deepen"
        )
    if held >= sheet.system.scale.maximum:
        raise IllegalAdvance(
            f"{sheet.character} holds {ability_id} at {held}, which is this system's maximum"
        )
    if unpaid := _unpaid(sheet, ability):
        raise IllegalAdvance("; ".join(unpaid))
    return _advanced(sheet, AdvanceKind.DEEPEN, at=at, ability_id=ability_id, magnitude=held + 1)

def rise(sheet: CharacterSheet, *, at: str) -> Advancement:
    """Move to the next rung up. Raises `IllegalAdvance` at the top of the ladder.

    One rung, never two: which rung somebody reaches is the ladder's business and skipping is a
    fact about the world that nothing here is entitled to invent.
    """
    system = sheet.system
    index = system.rank_index(sheet.rank_id)
    if index >= len(system.ranks):
        raise IllegalAdvance(
            f"{sheet.character} stands at {sheet.rank_id}, the top rung of {system.criterion}"
        )
    return _advanced(sheet, AdvanceKind.RISE, at=at, rank_id=system.rank_ids[index])

def choose(sheet: CharacterSheet, choice_id: str, option_id: str, *, at: str) -> Advancement:
    """Take one way at a fork this person has reached. Raises `IllegalAdvance` otherwise.

    **No number moves and that is the design.** Taking a way opens what it grants — those
    abilities stop being refused by `legal_moves` — and gaining any of them is still an
    advancement with its own position and its own beat. Granting three columns in one act would
    collapse the progression the schedule exists to spread out, which is the `progression` block's
    own recorded argument one object along.

    **Irrevocable.** A fork already taken raises, because foreclosure is the whole of what
    separates a choice from a checklist, and because there is no `world retract` to undo a `chose`
    edge with (§160.5, still owed from serial pilot 14 §10).

    **This function takes the way it is told and never picks one** (§61(5)). The caller supplies
    `option_id`; there is no default, no first-is-best, and no path here that consults anything
    about which way would be better.
    """
    choice = sheet.system.choice(choice_id)
    option = choice.option(option_id)
    taken = sheet.took(choice_id)
    if taken is not None:
        raise IllegalAdvance(
            f"{sheet.character} already took {taken} at {choice_id}, and a fork is taken once"
        )
    if choice not in _open_choices(sheet):
        raise IllegalAdvance(
            f"{choice_id} opens at {choice.opens_at}, and {sheet.character} stands at "
            f"{sheet.rank_id}"
        )
    if unmet := _unmet(sheet, option_id, option.needs):
        raise IllegalAdvance("; ".join(unmet))
    return _advanced(
        sheet,
        AdvanceKind.CHOOSE,
        at=at,
        choice_id=choice_id,
        option_id=option.option_id,
    )

def advance(sheet: CharacterSheet, move: Move, *, at: str) -> Advancement:
    """Take a move `legal_moves` offered. Raises `IllegalAdvance` where it cannot be taken.

    **The half of `legal_moves` that was missing.** That function offers `Move`s and nothing
    here took one: every caller unpacked the kind itself and called `gain`, `deepen` or `rise`
    by hand, so the mapping from an offered move to the arithmetic that performs it lived at
    each call site rather than beside the moves. A second unpacking is a second answer to
    "what does this move do", which is the defect `Movable` exists to prevent one object along.

    **A `CHOOSE` raises rather than defaulting**, and that is §61(5) rather than an omission: a
    fork carries the ways and not a way of taking one, so a function that took a `CHOOSE`
    without an `option_id` would have to pick, and picking is the one thing this module may
    never do. `choose` is the entry point, and it is told which way.

    Nothing here writes: an `Advancement` is a value carrying the sheet the move would leave,
    the keys it moves and the records that would say so. A caller reading `after` to *show*
    somebody what a moved line reads has performed no advancement — which is what
    `progression.moved_example` does, so the number a writer is shown and the number the book
    would record come from one arithmetic.
    """
    if move.kind is AdvanceKind.RISE:
        return rise(sheet, at=at)
    if move.kind is AdvanceKind.CHOOSE:
        raise IllegalAdvance(
            f"{move.choice_id} is a fork, and taking one needs the way it is taken; call choose()"
        )
    if move.ability_id is None:
        raise IllegalAdvance(f"a {move.kind.value} names no ability")
    if move.kind is AdvanceKind.GAIN:
        return gain(sheet, move.ability_id, at=at)
    return deepen(sheet, move.ability_id, at=at)
