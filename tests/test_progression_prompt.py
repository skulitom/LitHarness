"""Stage-0 §186: a scheduled scene is shown the line it leaves, not the one it entered.

§184 shipped the check and pilot 18 draw 3 was the first book to meet it: the plan read *Rating
moves here*, the furniture ask handed the writer `[STATUS] Ines — Rating 2 | …` and called it
*the state as it stands*, both attempts printed `Rating 2`, and the gate refused both. Two paid
attempts proving that the one concrete artifact in the prompt carried the entering values while
the plan asked for a move — and §169 had already measured that a model copies a filled example
character for character, which is the whole reason the example is filled rather than a template.
The ask and the check disagreed, and the writer obeyed the concrete half.

What this file pins, in five groups:

**The swap itself.** `test_the_writer_is_shown_the_line_the_scene_leaves` is the located defect,
and `test_the_shown_line_differs_from_the_entering_line_in_exactly_one_number` is the constraint
that keeps it a swap rather than a rewrite — the subject, the sheet, the labels and every other
column are the same string the scene would otherwise have been shown.

**One arithmetic.** `test_the_number_shown_is_the_one_the_system_itself_would_record` asserts the
value against `gamesystem.advance` on the same sheet, so the number a writer copies and the number
the book would write down come from the same function rather than from an increment reproduced at
the render site. A rise is the case that could not be got right by incrementing a label:
`test_a_rise_shows_the_rung_column_moving_and_never_a_column_named_after_the_rung`.

**The arm with no system to ask**, which is the located book: a sheet takes one step, and never
one past a ceiling it declared itself.

**The abstentions, which are the gate's own.** A scene that is shown the entering line is a scene
the gate does not refuse for failing to move it — except in the one case named as a residual, a
column at its own ceiling. `test_the_prompt_abstains_wherever_the_gate_abstains` holds the pairing
that matters, §184.4's imported book.

**The control and the cost.** An unscheduled scene renders the bytes it rendered before this
existed, one status line reaches the prompt rather than two, and the ask adds no demand.

No model reads, ranks or judges anything here, no bar is declared, and every assertion is an
equality between two integers or an identity of a rendered string.
"""

from __future__ import annotations

import litharness_contracts as lc

from litharness.application import planner
from litharness.domain import beats as beats_domain
from litharness.domain import context as context_domain
from litharness.domain import gamesystem, genre, house
from litharness.domain.extraction import (
    Movable,
    movables,
    moved_to,
    system_voice_example,
)
from litharness.domain.progression import gate_progression, moved_example, named_target
from tests.test_progression_gate import (
    _canon,
    _plan,
    _selected,
    _sheet_of,
    _snapshot,
    _standing,
    _system,
)

#: The §173 wording, pinned as a literal so the unscheduled arm cannot drift silently. This is
#: the string every book written before §186 was shown, and every book with no named move still
#: is.
ENTERING_ASK = (
    " The people in this book can read their own state, in this form, which is the state as "
    "it stands:\n"
)


_BEAT = beats_domain.Beat(
    logical_id="s1",
    ordinal=1,
    of_total=6,
    title=None,
    function="setup",
    template_id=beats_domain.SIX_BEAT.template_id,
)

_PACKET = context_domain.ContextPacket(
    query_id="progression-prompt",
    target_logical_id="s1",
    book_id="book",
    branch_id="main",
    base_revision_id="r0",
)


def _rendered(**conditionals: object) -> str:
    """The system message the planner assembles, through the live render."""
    system, _prompt = planner.render_prompt(
        _BEAT, book_title=None, packet=_PACKET, **conditionals  # type: ignore[arg-type]
    )
    return system


# ------------------------------------------------------------------------------ the swap


def test_the_writer_is_shown_the_line_the_scene_leaves() -> None:
    """Serial pilot 18 draw 3, scene 1, as the writer would now be handed it.

    The beat named `cold seal`; the entering line printed `cold seal 2`; both drafts printed
    `cold seal 2` and the gate refused both. The example is now the line after the move, and
    the entering value survives as a fact stated in words — a number a writer cannot tell has
    changed is one they may quietly change back.
    """
    records = _canon()
    target = named_target(_plan("cold seal"), records, character="ines_barrow", at="s1")
    assert target == Movable("cold seal", "cold_seal")

    moved = moved_example(records, target, character="ines_barrow", at="s1")

    assert moved is not None
    assert moved.name == "cold seal"
    assert (moved.was, moved.now) == (2, 3)
    assert "cold seal 3" in moved.line
    assert "cold seal 2" not in moved.line

    system = _rendered(
        status_example=system_voice_example(records, at="s1"), status_moved=moved
    )
    assert (
        " The people in this book can read their own state, in this form, which is the state "
        "this scene leaves once cold seal has moved from the 2 it stood at:\n"
        f"{moved.line}\n"
    ) in system
    assert ENTERING_ASK not in system


def test_the_shown_line_differs_from_the_entering_line_in_exactly_one_number() -> None:
    """A swap and not a rewrite. Everything the writer was going to be shown — the subject as
    this book spells it, the sheet, the labels, the order, every other column — is the same
    string; one number is different, and it is the one the plan named."""
    records = _canon()
    entering = system_voice_example(records, at="s1")
    moved = moved_example(
        records,
        Movable("cold seal", "cold_seal"),
        character="ines_barrow",
        at="s1",
    )

    assert entering is not None and moved is not None
    before = entering.split(" | ")
    after = moved.line.split(" | ")
    assert len(before) == len(after)
    assert [
        index for index, (was, now) in enumerate(zip(before, after, strict=True)) if was != now
    ] == [before.index("cold seal 2")]


# --------------------------------------------------------------------------- one arithmetic


def test_the_number_shown_is_the_one_the_system_itself_would_record() -> None:
    """The value comes from the advancement, never from an increment written here.

    `gamesystem.advance` takes the move `legal_moves` offered and returns the sheet it would
    leave; `moved_to` reads the named column off `after`. So a system that ever declares a
    different step is authoritative for free, and there is no second place to update.
    """
    system = _system()
    sheet = _sheet_of(system)
    deepen = next(
        move
        for move in gamesystem.legal_moves(sheet)
        if move.ability_id == "cold_seal"
    )

    would_record = gamesystem.advance(sheet, deepen, at="s1").after["cold_seal"]

    assert moved_to(
        _canon(system), Movable("cold seal", "cold_seal"), character="ines_barrow", at="s1"
    ) == would_record


def test_a_rise_shows_the_rung_column_moving_and_never_a_column_named_after_the_rung() -> None:
    """The case a label could not have got right.

    A rise is named by the rung it reaches — `fitter` — and moves `RANK_KEY`, which this book
    prints as `Ticket`. An after-line built by incrementing the column that shares the beat's
    word would have moved nothing, because no column is called `fitter`.
    """
    records = _canon()
    rise = Movable("fitter", gamesystem.RANK_KEY)
    assert rise in movables(records, character="ines_barrow", at="s1")

    moved = moved_example(records, rise, character="ines_barrow", at="s1")

    assert moved is not None
    assert (moved.name, moved.was, moved.now) == ("fitter", 1, 2)
    assert "Ticket 2" in moved.line
    assert "fitter" not in moved.line


# ------------------------------------------------------------------ the arm with no system


def _sheet_book(**values: int) -> list[lc.StateRecord]:
    """A book that prints a line and declares no system: the located pilot's own shape."""
    return [_snapshot("ines", dict(values))]


def test_a_book_with_no_system_takes_one_step() -> None:
    """Serial pilot 18 draw 3 is this arm — `systems_of` reads nothing, so the beat's
    vocabulary is the columns the line prints and there is no advancement to ask. One is the
    smallest change an integer column can make, and the beat's whole sentence is *moves here*.
    """
    records = _sheet_book(rating=2, graded=9)

    moved = moved_example(records, Movable("Rating", "rating"), at="s1")

    assert moved is not None
    assert (moved.was, moved.now) == (2, 3)
    assert "Rating 3" in moved.line
    assert "Graded 9" in moved.line


def test_a_column_at_its_own_declared_ceiling_is_shown_no_move() -> None:
    """`Warmth 6/6` has no next value that is not `impossible_fields`' own defect, so this
    abstains and the writer is shown the entering line. **A named residual**: the gate still
    fires on such a beat, so the scene is asked for a move it cannot be shown. Closing it means
    the beat vocabulary declining to name a maxed column, which re-rotates `beat_text` for every
    scheduled scene on the shelf — a second finding, not this one's."""
    records = _sheet_book(rating=2, warmth=6, warmth_max=6)

    assert moved_example(records, Movable("Warmth", "warmth"), at="s1") is None
    assert moved_example(records, Movable("Rating", "rating"), at="s1") is not None


def test_a_paired_column_below_its_ceiling_still_moves() -> None:
    """The guard is the ceiling and not the pairing: `Written 1/12` has room."""
    moved = moved_example(
        _sheet_book(written=1, written_max=12), Movable("Written", "written"), at="s1"
    )

    assert moved is not None
    assert "Written 2/12" in moved.line


# ---------------------------------------------------------------------------- abstentions


def test_the_prompt_abstains_wherever_the_gate_abstains() -> None:
    """§184.4's imported book, read from the other end, and this is the pairing that matters.

    A book that arrives holding a snapshot at every position has already stated the numbers its
    scene at `s1` prints, so that scene has no delta to produce — the gate says so and passes.
    Handing such a writer a moved line would ask for a second canon snapshot at one key, which
    is exactly the shape `integrity.detect_contradictions` groups on: the scene would be asked
    for a contradiction and refused for writing it. Both golden fixtures are that book.
    """
    records = [*_canon(), _snapshot("ines_barrow", _standing(), order_key="s1")]

    gate = gate_progression(
        "cold seal",
        "cold_seal",
        before=records,
        extracted=[],
        at="s1",
    )
    assert gate is not None and gate.passed is True
    assert "is not the record of it" in (gate.detail or "")

    assert (
        moved_example(records, Movable("cold seal", "cold_seal"), character="ines_barrow", at="s1")
        is None
    )


def test_a_scene_with_no_position_and_a_plan_with_no_name_are_both_shown_the_old_line() -> None:
    """The two cheapest abstentions, and both are the gate's: a scene entitled to no story
    position has nowhere to place a state, and a plan naming no quantity asked for no move."""
    records = _canon()

    cold_seal = Movable("cold seal", "cold_seal")
    assert moved_example(records, cold_seal, character="ines_barrow") is None
    assert moved_example(records, None, character="ines_barrow", at="s1") is None


def test_a_name_this_book_no_longer_offers_is_shown_no_moved_line() -> None:
    """`named_target` abstains on a word this book's vocabulary does not offer here, and an
    abstention there is an abstention in the example: there is no target to move."""
    records = _canon()
    target = named_target(_plan("Windread"), records, character="ines_barrow", at="s1")

    assert target is None
    assert moved_example(records, target, character="ines_barrow", at="s1") is None


# ------------------------------------------------------------------- the control and the cost


def test_an_unscheduled_scene_is_shown_the_bytes_it_was_shown_before() -> None:
    """The control arm, pinned as a literal. Every book with no named move — every unscheduled
    scene, every book with no sheet, every case the composer abstains on — renders the §173
    wording and the entering line, byte for byte."""
    records = _canon()
    entering = system_voice_example(records, at="s1")
    assert entering is not None

    system = _rendered(status_example=entering)

    assert f"{ENTERING_ASK}{entering}\n" in system
    assert "this scene leaves" not in system


def test_one_status_line_reaches_the_prompt_and_never_two() -> None:
    """§161.3's cardinality, which is why the entering line is replaced rather than joined.

    `extract_state` mints one canon record per match at one order key, so a scene printing two
    lines writes the shape the contradiction detector refuses — and a prompt holding two
    printable lines, shown to a model measured to copy them verbatim (§169), is how that gets
    printed. One artifact in, one line out.
    """
    records = _canon()
    moved = moved_example(
        records, Movable("cold seal", "cold_seal"), character="ines_barrow", at="s1"
    )
    assert moved is not None

    system = _rendered(
        status_example=system_voice_example(records, at="s1"), status_moved=moved
    )

    assert system.count("[STATUS]") == 1
    assert "exactly once" in system


def test_the_moved_ask_costs_no_demand_and_names_no_machinery_word() -> None:
    """One sentence swapped for one sentence and one line for one line, so the count cannot
    move; `tests/test_prompt_budget.py` holds the same number as a ceiling. And the sentence
    states what the numbers are and nothing about how to write — §138's boundary, and §154's:
    the line is the exact string to emit."""
    records = _canon()
    entering = system_voice_example(records, at="s1")
    moved = moved_example(
        records, Movable("cold seal", "cold_seal"), character="ines_barrow", at="s1"
    )
    assert entering is not None and moved is not None

    plain = _rendered(status_example=entering)
    swapped = _rendered(status_example=entering, status_moved=moved)

    assert len(house.demands(swapped)) == len(house.demands(plain))

    sentence = next(
        item for item in house.demands(swapped) if "this scene leaves" in item
    )
    assert not any(word in sentence.casefold() for word in house.MACHINERY_WORDS)


def test_the_live_drafting_path_hands_a_scheduled_scene_the_moved_line(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """End to end, through `make_plan_selector`, on the shape every serial pilot runs in.

    The frozen system message carries the moved line and the frozen prompt carries the beat that
    named it, and the payload's `progression_column` is the column that moved — the ask, the
    example and the check reading one answer. Scene 2 is the control: no beat, and the §173
    wording unchanged.
    """
    job = _selected(tmp_path / "shown.db", drafted=0)
    selected = job.payload["selected_by"]
    system = str(job.payload["system"])
    named = str(selected["progression_beat"])

    assert genre.NAMED_BEAT.format(name=named) in str(job.payload["prompt"])
    assert f"once {named} has moved from the " in system
    assert system.count("[STATUS]") == 1

    line = next(part for part in system.splitlines() if part.startswith("[STATUS]"))
    entering = system_voice_example(_canon(), at="s1")
    assert entering is not None and line != entering

    second = _selected(tmp_path / "second.db", drafted=1)
    assert "progression_beat" not in second.payload["selected_by"]
    assert ENTERING_ASK in str(second.payload["system"])


def test_no_refusal_of_the_gate_reaches_the_prompt_that_shows_the_moved_line() -> None:
    """§184.3's rule, re-checked at the surface that changed. The example is composed from the
    book's own records at selection time and carries no word of what any gate found; the retry
    re-sends it unchanged. The correction §186 records is to the *citation* — §97.1 governs the
    operator's diagnostics and the reader channel, not a deterministic comparison — and not to
    the outcome, which the retry's own classification holds."""
    records = _canon()
    moved = moved_example(
        records, Movable("cold seal", "cold_seal"), character="ines_barrow", at="s1"
    )
    assert moved is not None
    system = _rendered(
        status_example=system_voice_example(records, at="s1"), status_moved=moved
    )

    refusal = gate_progression(
        "cold seal", "cold_seal", before=records, extracted=[], at="s1"
    )
    assert refusal is not None and refusal.detail is not None
    for word in ("was named as moving", "before and after", "wrote down no state"):
        assert word not in system


def test_the_ask_is_a_fact_about_numbers_and_never_an_instruction_about_prose() -> None:
    """§138. The swapped clause says what the line reads and what it read before; it carries no
    verb about writing, no adjective, and no claim about what a good scene does with it."""
    records = _canon()
    moved = moved_example(
        records, Movable("cold seal", "cold_seal"), character="ines_barrow", at="s1"
    )
    assert moved is not None

    sentence = (
        "The people in this book can read their own state, in this form, which is the state "
        f"this scene leaves once {moved.name} has moved from the {moved.was} it stood at:"
    )
    for banned in ("vivid", "compelling", "show", "dramatise", "make sure", "must", "should"):
        assert banned not in sentence.casefold()


def test_composing_the_example_performs_no_advancement() -> None:
    """`gamesystem.advance` returns the sheet a move *would* leave and the records that would
    say so; reading a number off it moves nobody. The records handed in come back unchanged, and
    the book still stands where it stood — a writer shown a moved line has not been advanced."""
    records = _canon()
    before = list(records)

    moved = moved_example(
        records, Movable("cold seal", "cold_seal"), character="ines_barrow", at="s1"
    )

    assert moved is not None and moved.now == 3
    assert records == before
    assert _sheet_of(_system()).magnitude("cold_seal") == 2
