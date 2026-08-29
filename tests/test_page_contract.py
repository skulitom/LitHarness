"""Stage-0 §161: everything between the sheet and the page.

Three things are asserted here and they fail for three different reasons, which is why they
are one file rather than three additions to three others.

**The furniture contract.** A book that clears the genre floor is asked to print its status
line at the moment one of its numbers moves, exactly once. The cardinality is not tidiness:
`extract_state` runs `sheet.pattern.finditer` and mints one canon record per match at
one `order_key`, so a scene printing the line twice with different numbers writes two canon
snapshots that disagree at one position — the shape `integrity.detect_contradictions` groups
on. `test_the_status_line_is_asked_for_exactly_once` is the assertion that keeps the
placement without buying a contradiction with it.

**The example is the book's own vocabulary.** `DEFAULT_SHEET` is `Level | HP | MP | Gold`,
which is the operator's explicit not-this, and `render_status_line` fills absent keys with
`?` — so a book seeding three quantities of its own and declaring no sheet was shown four
clichés and four question marks.
`test_a_book_that_declared_no_sheet_is_shown_the_columns_it_actually_counts` is that defect;
`test_a_book_whose_keys_are_the_defaults_keys_still_gets_the_default_object` is the
compatibility anchor that stops the fix rewriting every store on disk.

**The beats speak the sheet's vocabulary.** §157's beat named a category — "one of the
numbers this book counts" — and read 8 §4.2 measured both of pilot 14's scheduled beats
landing as promotions inside a guild, because a category is satisfied by whichever ladder the
world declared loudest. The beat now names the quantity.
`test_the_beat_rotates_by_schedule_position_and_not_by_scene_ordinal` is the one to read: the
obvious implementation is one line and it can never reach half the sheet.

No model reads, ranks or judges anything in this file, and no bar is declared anywhere in it.
"""

from __future__ import annotations

import litharness_contracts as lc
import pytest

from litharness.application import planner
from litharness.domain import genre, house, worlds
from litharness.domain.extraction import (
    DEFAULT_SHEET,
    STATUS_PREDICATE,
    counted_names,
    implied_sheet,
    label_for,
    render_status_line,
    sheet_for,
    state_as_it_stands,
    system_voice_example,
)


def _snapshot(subject: str, value: dict[str, object], *, order_key: str = "s1") -> lc.StateRecord:
    return worlds.world_record(
        subject,
        STATUS_PREDICATE,
        value=value,
        order_key=order_key,
        authority=lc.StateAuthority.ACCEPTED_CANON,
    )


#: The shape Track 4's manual probe drew when the render path was fed a world's own words:
#: three quantities, none of them a cliché, one of them paired.
_OWN_VOCABULARY = {"attunement": 1, "threads": 2, "threads_max": 3}

#: `DEFAULT_SHEET`'s own six value keys, which is what both golden fixtures hold and what
#: every store written before §161 holds.
_DEFAULT_SHAPED = {"level": 1, "hp": 10, "hp_max": 10, "mp": 4, "mp_max": 4, "gold": 11}


# --- the example is the book's own vocabulary ------------------------------------------


def test_a_book_that_declared_no_sheet_is_shown_the_columns_it_actually_counts() -> None:
    """The §161 defect, in the form it reached the writer's prompt.

    Before this, `sheet_for` fell back to `DEFAULT_SHEET` for any book that declared no
    sheet, and the declaring vocabulary was undocumented — so this was every book. The line
    below is what the writer was handed: the book's own three quantities gone, four clichés
    in their place, and a question mark where each number should have been.
    """
    records = [_snapshot("sera", dict(_OWN_VOCABULARY))]

    was = render_status_line("sera", _OWN_VOCABULARY, sheet=DEFAULT_SHEET)
    assert was == "[STATUS] sera — Level ? | HP ?/? | MP ?/? | Gold ?"

    line = system_voice_example(records)
    assert line == "[STATUS] sera — Attunement 1 | Threads 2/3"
    for cliche in ("Level", "HP", "MP", "Gold", "?"):
        assert cliche not in line


def test_a_book_whose_keys_are_the_defaults_keys_still_gets_the_default_object() -> None:
    """The compatibility anchor, and it is identity rather than equality on purpose.

    Deriving a sheet from a mapping takes the column order from that mapping's iteration
    order, and the default's canonical order is a fact about the default rather than about
    any one record that happens to hold its keys. Returning the object itself is what keeps
    a store written before §161 parsing exactly as it did.
    """
    assert sheet_for([_snapshot("rook", dict(_DEFAULT_SHAPED))]) is DEFAULT_SHEET
    # Order deliberately scrambled: the answer is the same object either way.
    scrambled = {key: _DEFAULT_SHAPED[key] for key in reversed(list(_DEFAULT_SHAPED))}
    assert sheet_for([_snapshot("rook", scrambled)]) is DEFAULT_SHEET


def test_a_book_with_no_readable_snapshot_falls_back_and_is_never_asked_to_print() -> None:
    """The one remaining fallback, and the reason it is harmless.

    `implied_sheet` abstains where nothing is readable, and `sheet_for` then answers with the
    default — but `speaks_system_voice` refuses such a book, so no example is ever rendered
    from it and the genre floor blocks it before a packet is built.
    """
    assert implied_sheet([]) is None
    assert sheet_for([]) is DEFAULT_SHEET
    assert system_voice_example([]) is None
    assert genre.genre_block([]) is not None


def test_a_key_the_parser_could_not_use_is_dropped_rather_than_guessed_at() -> None:
    """A regex group needs an identifier and `\\d+` needs a plain integer.

    Booleans are excluded explicitly: `isinstance(True, int)` is True in Python, and a sheet
    with a `True` column would compile a pattern that can never match the value it came from.
    """
    sheet = implied_sheet(
        [_snapshot("sera", {"attunement": 1, "not an identifier": 2, "flag": True, "note": "x"})]
    )
    assert sheet is not None
    assert sheet.value_keys == ("attunement",)


def test_the_implied_sheet_only_ever_grows() -> None:
    """A granted quantity adds a column; nothing removes one.

    Monotone on purpose: a sheet that could lose a column would stop parsing lines the book
    had already printed, which is the failure mode a parser cannot recover from.
    """
    records = [
        _snapshot("sera", {"attunement": 1}, order_key="s1"),
        _snapshot("sera", {"attunement": 2, "ember_grasp": 1}, order_key="s2"),
        _snapshot("sera", {"attunement": 3}, order_key="s3"),
    ]
    sheet = implied_sheet(records)
    assert sheet is not None
    assert sheet.value_keys == ("attunement", "ember_grasp")


def test_an_advancement_that_restates_nothing_still_renders_a_whole_sheet() -> None:
    """The exposure Track 1's store caution named, closed on the render side.

    World-vocabulary record ids are position-blind and the store is `INSERT OR IGNORE`, so an
    unchanged holding keeps the position where it was established rather than being rewritten
    at the new one — an advancement records the edge that moved plus its snapshot, and nothing
    guarantees that snapshot restates the sheet. Reading the standing record alone would put a
    question mark on every column the scene did not touch, which is the same defect
    `implied_sheet` was written against arriving by a different door.
    """
    records = [
        _snapshot("sera", {"attunement": 1, "threads": 2, "threads_max": 3}, order_key="s1"),
        # Scene 2 moved one number and restated nothing else.
        _snapshot("sera", {"attunement": 2}, order_key="s2"),
    ]
    assert system_voice_example(records, at="s2") == (
        "[STATUS] sera — Attunement 2 | Threads 2/3"
    )
    assert counted_names(records, at="s2") == ("Attunement", "Threads")


def test_the_fold_never_crosses_from_one_character_to_another() -> None:
    """Two characters holding sheets must not be shown each other's numbers.

    The fold takes the subject of the record that stands at the position and merges only that
    subject's snapshots; `snapshot_at` still decides which record stands.
    """
    records = [
        _snapshot("sera", {"attunement": 1}, order_key="s1"),
        _snapshot("rook", {"gold": 99}, order_key="s2"),
    ]
    standing = state_as_it_stands(records, at="s2")
    assert standing == ("rook", {"gold": 99})


def test_a_book_that_restates_everything_folds_to_exactly_its_latest_snapshot() -> None:
    """The control: every store written before §161, and both golden fixtures."""
    records = [
        _snapshot("rook", dict(_DEFAULT_SHAPED), order_key="s1"),
        _snapshot("rook", {**_DEFAULT_SHAPED, "level": 2}, order_key="s2"),
    ]
    subject, values = state_as_it_stands(records, at="s2")  # type: ignore[misc]
    assert (subject, values) == ("rook", {**_DEFAULT_SHAPED, "level": 2})


def test_a_label_is_derived_by_a_rule_and_the_rule_is_the_genres_own() -> None:
    """Short keys are initialisms and longer ones are words.

    The rule has to reproduce `DEFAULT_SHEET`'s four labels from its four keys, because that
    is what lets a derived sheet and the default be the same statement for a book that used
    it — and it happens to be right for the stat abbreviations the genre actually writes.
    """
    assert [label_for(key) for key in ("level", "hp", "mp", "gold")] == [
        "Level",
        "HP",
        "MP",
        "Gold",
    ]
    assert [label_for(key) for key in ("str", "dex", "attunement", "soul_thread")] == [
        "STR",
        "DEX",
        "Attunement",
        "Soul Thread",
    ]


# --- the furniture contract ------------------------------------------------------------


def _scene_system(**kwargs: object) -> str:
    """The scene writer's system message for one representative beat.

    An empty packet: every assertion here is about the conditional blocks `render_prompt`
    appends to the system message, and packet material rides in the user prompt.
    """
    from litharness.domain.context import ContextPacket

    beat = planner.Beat(
        logical_id="scene-1",
        title="The Deep Ledger",
        function="setup",
        ordinal=1,
        of_total=8,
        template_id="t",
        story_order_key="s1",
    )
    system, _ = planner.render_prompt(
        beat,
        book_title="A Book",
        packet=ContextPacket(
            query_id="q",
            target_logical_id="scene-1",
            book_id="b",
            branch_id="br",
            base_revision_id="rev",
        ),
        **kwargs,  # type: ignore[arg-type]
    )
    return system


def test_the_status_line_is_asked_for_exactly_once() -> None:
    """The cardinality is what keeps the placement from manufacturing a contradiction.

    `extract_state` mints one canon record per pattern match, all at one `order_key`.
    A scene printing the line before and after a change would write two snapshots that
    disagree at one position — which `integrity.detect_contradictions` groups on exactly.
    """
    system = _scene_system(status_example="[STATUS] sera — Attunement 1 | Threads 2/3")
    assert "exactly once" in system
    assert "where one of its numbers changes" in system
    # The footer form this replaced. It is gone, and its guarantee is not: the scene's end is
    # still where the line goes when nothing moves.
    assert "End the scene with a status line" not in system
    assert "at the scene's end if none of them does" in system


def test_the_furniture_ask_costs_the_same_four_demands_it_did_before() -> None:
    """§135's rule: a clause is paid for or it is not added.

    The furniture contract moved the line onto the change and did not buy a demand to do it.
    Four before, four after — the old form spent two sentences saying what shape to print and
    where, and the new one spends two saying what shape and where, in the other order.
    """
    example = "[STATUS] sera — Attunement 1 | Threads 2/3"
    floor = _scene_system()
    with_furniture = _scene_system(status_example=example)
    added = len(house.demands(with_furniture)) - len(house.demands(floor))
    assert added == 4


def test_the_ask_is_the_same_sentence_for_a_system_book_and_a_default_shaped_one() -> None:
    """The ratchet is the mode, so the clause carries no mode flag.

    Both arms clear `speaks_system_voice`; only the rendered line differs. A clause that
    branched on which kind of book it was would be a second answer to a question canon
    already answers.
    """
    own = _scene_system(
        status_example=system_voice_example([_snapshot("s", dict(_OWN_VOCABULARY))])
    )
    default = _scene_system(
        status_example=system_voice_example([_snapshot("r", dict(_DEFAULT_SHAPED))])
    )
    assert "Threads 2/3" in own and "Gold 11" in default
    assert len(house.demands(own)) == len(house.demands(default))


# --- suppressor 2, re-aimed ------------------------------------------------------------


def test_the_criteria_clause_no_longer_forbids_the_book_printing_its_own_line() -> None:
    """Read 4's suppressor 2, at the address read 4 named.

    It read *"a rank is something a reader sees, never something a narrator reports"*, which
    read 4 called a standing prohibition on printing the ladder. The object is now narrowed
    to the failure §5 item 11 actually named — a narrator reporting a change the reader never
    saw — and the furniture is named inside the same sentence, so the exemption costs nothing.
    """
    system = _scene_system(criteria="assay_grade: ordinal — third_seal then first_seal")
    assert "never something a narrator reports" not in system
    assert "a narrator reporting a rank whose change the reader was never shown" in system
    assert "the line the book itself prints is not that" in system


def test_narrowing_that_clause_did_not_cost_a_demand() -> None:
    """The exemption rides on a semicolon, and `demands` splits on terminators and newlines.

    Naming the furniture as its own sentence would have been a permission, and §138 measured
    a permission-only clause returning more than six times what a prohibition-only one did,
    worse than silence. Inside the sentence it delimits instead of permitting, at no cost.
    """
    system = _scene_system(criteria="assay_grade: ordinal — third_seal then first_seal")
    # The claim is about the CLAUSE, not about the block: the criterion brief itself is a
    # line and `demands` counts a line, so the block has always cost two and still does.
    # What matters is that the sentence carrying both the prohibition and the exemption is
    # one demand — naming the furniture as a second sentence is what would have cost.
    clause = [item for item in house.demands(system) if "what fails is a narrator" in item]
    assert len(clause) == 1
    assert clause[0].endswith("the line the book itself prints is not that:")


# --- the beats speak the sheet's vocabulary --------------------------------------------


def test_a_book_that_counts_nothing_gets_the_beat_it_always_got() -> None:
    """The control, and it is every book written before a sheet existed."""
    assert genre.beat_text(1, 8) == genre.BEAT
    assert genre.with_beat("Rook pays a cost.", 1, 8) == f"Rook pays a cost. {genre.BEAT}"
    assert counted_names([]) == ()


def test_the_beat_names_a_quantity_the_book_actually_counts() -> None:
    """Read 8 §4.2's defect: a beat naming a category is satisfied by a guild promotion.

    Both of pilot 14's scheduled beats fired and both landed as advancement inside a
    bureaucracy, because *"one of the numbers this book counts"* is satisfied by whichever
    ladder the world declared loudest. A named quantity is satisfied by one thing.
    """
    records = [_snapshot("sera", dict(_OWN_VOCABULARY))]
    assert counted_names(records) == ("Attunement", "Threads")
    assert genre.beat_text(1, 8, counts=counted_names(records)) == (
        "Attunement moves here, and the person it belongs to is there when it does."
    )


def test_the_beat_rotates_by_schedule_position_and_not_by_scene_ordinal() -> None:
    """The obvious implementation is one line and it can never reach half the sheet.

    At `EVERY = 2` the scheduled ordinals are 1, 3, 5, 7, so indexing a four-column sheet by
    ordinal reaches columns 0 and 2 and never names the other two. Indexing by position in
    the schedule cycles all of them. This is arithmetic and not a preference: nothing here
    decides which quantity matters, which is what keeps §61(5) clear of it.
    """
    counts = ("Attunement", "Threads", "Ember Grasp", "Weave")
    named = [genre.beat_text(ordinal, 8, counts=counts) for ordinal in (1, 3, 5, 7)]
    assert [text.split(" moves here")[0] for text in named] == list(counts)


def test_the_beat_still_assumes_nothing_about_who_the_book_is_about() -> None:
    """§155.3's pinned constraint, extended to the named form.

    The first draft of `BEAT` read *"something he has been counting"*, which would have
    written a male protagonist into the plan of every scheduled scene of every book. The
    named form inherits that constraint rather than restating it.
    """
    for text in (genre.BEAT, genre.beat_text(1, 8, counts=("Attunement",))):
        words = text.lower().replace(",", " ").replace(".", " ").split()
        assert not ({"he", "she", "his", "her", "him", "hers"} & set(words))


def test_the_beat_never_carries_this_systems_own_vocabulary() -> None:
    """§155.3's other pinned constraint, and the named form is where it could have broken.

    The beat reaches the writer inside a scene plan and therefore shapes prose a reader
    reads; §120 measured `standing` reaching a chapter when repo vocabulary got that far.
    `BEAT` is house text and a ceiling test covers it — a column label is book data and no
    ceiling test can, so `counted_names` drops the collisions and a book whose every label
    collides falls back to the unnamed form, which is the correct failure.
    """
    assert not [word for word in house.MACHINERY_WORDS if word in genre.BEAT.lower()]
    records = [_snapshot("sera", {"standing": 1, "criteria": 2, "attunement": 3})]
    assert counted_names(records) == ("Attunement",)
    all_machinery = [_snapshot("sera", {"standing": 1, "criteria": 2})]
    assert counted_names(all_machinery) == ()
    assert genre.beat_text(1, 8, counts=counted_names(all_machinery)) == genre.BEAT


def test_an_unscheduled_scene_is_left_byte_identical() -> None:
    """The control §155.3 is read against, and naming the quantity did not disturb it."""
    counts = ("Attunement", "Threads")
    for ordinal in (2, 4, 6):
        assert genre.with_beat("Rook waits.", ordinal, 8, counts=counts) == "Rook waits."


# --- the house numbers clause ----------------------------------------------------------


def test_exactness_is_licensed_to_the_systems_own_count_and_not_the_worlds() -> None:
    """§161's re-scope, and read 8 §4.2 is why the three middle words mattered.

    *"What this world counts"* licensed a guild's glasses, a ledger's entries and a tax roll,
    which are all things a world counts and all things the operator has now objected to four
    books running. The scope is the world's own SYSTEM, which is a strictly smaller set — so
    this is a narrowing and not a new permission, and §138's direction is preserved.
    """
    assert "what this world's own system counts and to nothing else" in house.READER
    assert "belongs to what this world counts" not in house.READER


def test_the_numbers_clause_names_the_classes_that_actually_leaked() -> None:
    """A tally replaced a habit, because a jar count is what read 8 measured and a habit is
    not. The instances are invented rather than lifted: §97.1 forbids an operator's read from
    becoming prompt text, and a numeral harvested from the book under read is that laundering
    with the evidence left in."""
    assert "tallies" in house.READER
    assert "eleven repetitions" not in house.READER


def test_the_house_floor_did_not_grow_for_any_of_this() -> None:
    """Every §161 edit to `house` is a re-scope of text that was already there.

    `tests/test_prompt_budget.py` owns the ceiling; this asserts the shape the ceiling exists
    to protect — that the numbers clause is still two sentences and bought nothing.
    """
    clause = [item for item in house.demands(house.READER) if "exact number" in item]
    assert len(clause) == 1


@pytest.mark.parametrize("word", sorted(house.MACHINERY_WORDS))
def test_no_edited_clause_speaks_this_systems_own_vocabulary(word: str) -> None:
    """The rail every reader-facing edit is held to, applied to §161's four clauses at once."""
    for text in (house.READER, genre.BEAT, genre.NAMED_BEAT):
        assert word not in text.lower()
