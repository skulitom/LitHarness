"""Stage-0 §180, half removed by §187: the chained-sentence prohibition, and the em dash strip.

**Two items from read 11 and they are answered in two different ways, which is the finding this
file holds.** One is a shape a writer produces and only a writer can not produce; the other is a
character, and a character does not need to be asked for. **§187 removed the first and left the
second exactly as it is**: the strip is mechanical, it is in the audit's own column of things
that worked, and nothing below the `--- the strip ---` rule changed.

**The clause was removed from `house.CLARITY` on 2026-08-30, and it is the one removal in §187
that needed no port.** `application/reviser.py` already carried a prohibition on the same shape —
a sentence hanging one happening on the next with nothing between them saying which — and it
carried it before §180's clause was written, so the floor's copy was the second home and §152's
two-homes defect was live for as long as both stood. The audit supplies the measured half:
`plan/agent-impact/` reports the chain share falling by two thirds at the reviser and no clause
on this floor moving a sentence metric across ten chapters. The operator's word at that report is
the other half of §127's brake. `test_the_clause_fails_a_chain_and_not_a_long_sentence` now reads
the surviving prohibition at the surviving address.

**The subtraction §180 made to pay for the clause is not reversed, and that is a decision.**
`test_the_clause_was_paid_for_by_the_restatement_it_replaced` holds it: the sentence removed then
was a restatement of a standard the rule's opening already sets, §176.1 had classified it as the
half a writer cannot act on, and putting an unaddressable sentence back on every prose call
because its purchase was returned would be the worst trade in the file.

**The hazard the clause was shaped around still governs its surviving form.** It runs both ways:
a cap on sentence length would delete the elaborated sentence a genre opening lives on, and §163
is the standing record of what a filter keyed one notch wider costs. The object is therefore what
happens in a sentence and never how long it is.

**The strip.** The em dash is read 1's own axis returning at read 11 with no drafting rule ever
written against it, and it is a character. A clause would have cost a demand at every role that
stands on the floor and would have been the project instructing about a **registered prose axis**
in the one text that reaches every prose call — the act `directors.legal_brief` and
`writers.legal_dossier` refuse a brief and a dossier for. `domain.draft.strip_em_dash` asserts
nothing in any prompt. It runs before the gate so one text carries one hash and one offset space,
and `test_a_status_line_still_parses_after_the_strip` is the assertion that matters most: the
canon parser's own separator is an em dash, and rewriting it would have produced a scene that
renders a status panel and extracts no state, which is indistinguishable from a scene that
established nothing.

No model reads, ranks or judges anything here. No bar is declared. The census that placed the
clause's bound is at §180 and no number of it is in this file or in any prompt.
"""

from __future__ import annotations

import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import reviser
from litharness.domain import house, voice
from litharness.domain.directors import prose_axes_named
from litharness.domain.draft import strip_em_dash
from litharness.domain.events import EventType
from litharness.domain.extraction import STATUS_PATTERN, STATUS_TEMPLATE
from tests.test_draft import START, conductor_for, registry_with, seeded

#: The registered mark, read from its one home for `strip_em_dash`'s own reason.
MARK = voice.EXHIBITION_MARKERS["em_dash"]

#: The demand §180 added to `house.CLARITY` and §187 removed from it. Held by its operative words
#: so the absence is asserted against the same phrase the presence used to be.
_CHAIN = "a fourth thing happens after three already have"

#: The prohibition that survives, at the address that had it first. `application/reviser.py` was
#: written before §180's clause and carried this shape from the start, which is why §187 removed
#: the floor's copy without porting anything: there was nowhere to port it to that did not have
#: it already.
_REVISER_CHAIN = "hanging one happening on the next"

#: The sentence §180 removed to pay for its clause. **§187 did not put it back**, and
#: `test_the_clause_was_paid_for_by_the_restatement_it_replaced` is where that decision lives.
_RESTATEMENT = "A thing the reader cannot follow is a thing that did not happen"


def _clause() -> str:
    """The surviving prohibition, read from `reviser._TASK` since §187."""
    (found,) = [item for item in house.demands(reviser._TASK) if _REVISER_CHAIN in item]
    return found


@pytest.fixture
def store(tmp_path) -> SqliteStore:
    return SqliteStore.open(tmp_path / "sentence-structure.db")


# --- the clause ----------------------------------------------------------------------


def test_the_floor_no_longer_carries_the_chain_clause_and_the_reviser_always_did() -> None:
    """§187's removal, and the pair is the whole argument for making it without a port.

    A rule with two homes drifts in one of them (§152). This one had two from the moment §180
    shipped, because `application/reviser.py` had been written first and already forbade the same
    shape at the stage the audit measured actually moving it. So the floor's copy comes out and
    nothing moves anywhere: the second assertion is what makes the first safe, and a later track
    reading only the first would conclude the prohibition was abandoned.
    """
    assert _CHAIN not in house.CLARITY
    assert _CHAIN not in house.HOUSE_RULES
    assert _REVISER_CHAIN in reviser._TASK


def test_the_clause_fails_a_chain_and_not_a_long_sentence() -> None:
    """The object that keeps §163's failure mode out of a clause aimed at sentence structure.

    **Repointed by §187 to the surviving prohibition**, which is the reviser's own and predates
    §180's. The name is kept because `tests/test_architecture.py` holds every ledger citation to
    an existing test and §180 cites this file; the property asserted is the same property, at the
    address that still asserts it.

    A rule that failed a sentence for its *length* would delete elaboration — one thing
    happening, described at whatever length it takes — which is not what any read has named. This
    prohibition's object is a sentence that hangs one happening on the next while never saying
    which is the reason for which, so it reaches chaining and cannot reach an elaborated sentence
    about one thing: nothing in it counts words.
    """
    clause = _clause()
    assert clause.startswith("What fails is"), (
        "§138 measured a permission returning more than six times what a prohibition did, and "
        "worse than silence. This demand is signed as a prohibition and stays that way."
    )
    assert "a sentence hanging" in clause, "the object is a sentence, which a writer emits"
    assert "the reason, the moment or the condition" in clause, (
        "the clause reaches a chain by what it leaves unsaid between two happenings; strip this "
        "and it becomes a rule about conjunctions"
    )
    for length in ("long", "words", "short", "brief", "length"):
        assert length not in clause.lower(), (
            "without this the clause reaches elaboration, and §163 is the record of what a "
            "filter keyed one notch wider than its defect costs"
        )


def test_the_concession_sits_inside_the_demand_it_bounds() -> None:
    """§161.5's pattern, and the reason it is not decoration.

    A concession written as its own sentence is a permission, and `house.demands` would count it
    as a second demand at every role that reads it. Hung off a semicolon inside the sentence it
    delimits, it costs nothing and cannot be obeyed on its own.

    **Repointed by §187, and the count moved from the floor to the reviser** because that is
    where the concession-bearing clauses now are. `house.CLARITY` carried two and carries none:
    §176's comparison clause and §180's chain clause both ended this way and both left. The
    reviser carries four — its own perception clause, plus §171's, §179's and §176's, each of
    which arrived with its concession attached because they moved byte-identical. The exact
    count is what would catch a later edit letting one out into a sentence of its own.
    """
    assert len([item for item in house.demands(house.CLARITY) if "not that" in item]) == 0
    bounded = [item for item in house.demands(reviser._TASK) if "not that" in item]
    assert len(bounded) == 4, (
        "four clauses at this role carry their concession inside their own sentence; a fifth "
        "demand ending this way means one was let out into a permission of its own"
    )
    for clause in bounded:
        prohibition, semicolon, concession = clause.partition(";")
        assert semicolon, f"the concession in {clause!r} must share the prohibition's sentence"
        assert "What fails" in prohibition
        assert "not that" in concession


def test_the_clause_was_paid_for_by_the_restatement_it_replaced() -> None:
    """The subtraction §176 looked for and could not make, made here — and not undone by §187.

    §176.1 ruled the sentences opening and closing `CLARITY` the half a writer cannot act on, and
    §176.5 refused to cut the *opening* one because its second half carries the
    following-rather-than-explaining correction the constant was corrected twice in one day to
    get. The closing one carries no measurement, has no entry in the ledger and restates a
    standard the opening already sets, so it was the candidate §127's brake does not protect.

    **§187 removed the clause that sentence paid for and deliberately did not bring the sentence
    back.** A subtraction is not a deposit to be reclaimed when the purchase is returned: what
    went was unaddressable by §154 and restated a standard the floor still sets in its opening
    line, so restoring it would put a demand that lands with its sign multiplied by zero onto
    every prose call in the pipeline. The floor now closes on the paragraph clause, which is a
    rule about a thing a writer can see.
    """
    assert _RESTATEMENT not in house.CLARITY
    assert _CHAIN not in house.CLARITY
    assert house.CLARITY.rstrip().endswith("and the sentences were all fine."), (
        "the floor closes on the paragraph clause; if this moved, say which clause is last and "
        "why, because the closing sentence has been a subject of three entries"
    )
    assert "Every sentence can be followed the first time it is read." in house.CLARITY


def test_the_clause_names_no_registered_prose_axis() -> None:
    """The rail this track had to stay clear of, asserted rather than assumed.

    `directors._CRAFT_INSTRUCTION` refuses a brief or a dossier that instructs about an axis
    under measurement, and its `em_dash` pattern fires on the word *punctuation* alone. Read 11's
    own words for this family are "punctuation and sentence structure", and none of them are in
    the floor: its clauses are about what happens in a sentence, not how a sentence is pointed.
    Still asserted over the floor after §187, because the floor is what reaches every prose role
    and a later clause added there is the thing this guards against.
    """
    assert prose_axes_named(house.CLARITY) == ()
    assert prose_axes_named(house.HOUSE_RULES) == ()


def test_no_word_of_the_read_11_chapter_became_prompt_text() -> None:
    """§97.1, mechanically. The operator's read is a defect harvest and never prompt material."""
    for word in ("towel", "bench", "drawer", "glanced", "polite", "queue"):
        assert word not in house.HOUSE_RULES.lower(), (
            f"{word!r} is from the chapter under read; a noun harvested from the book that "
            "prompted a clause is §97.1 laundering with the noun left in"
        )
    for word in ("comma", "punctuat"):
        assert word not in house.HOUSE_RULES.lower()


# --- the strip -----------------------------------------------------------------------


def test_the_spaced_habit_becomes_a_comma() -> None:
    """Five sixths of every em dash in this project's own prose is this one form."""
    text, removed = strip_em_dash(f"He set it down {MARK} the wrong hand {MARK} and waited.")
    assert text == "He set it down, the wrong hand, and waited."
    assert removed == 2


def test_the_mark_survives_where_it_is_a_device_and_not_a_habit() -> None:
    """Speech cut off mid-word, which no substitution preserves.

    A comma makes an interruption into a clause and an ellipsis makes it into a trailing-off,
    which is a different thing happening to a different character. Refused deliberately and
    named as a residual at §180; the census that sized it is there too.
    """
    for line in (f'"You have no business {MARK}"', f'"Dan{MARK}"', f"He turned{MARK}"):
        text, removed = strip_em_dash(line)
        assert text == line
        assert removed == 0


def test_immediacy_is_what_separates_the_device_from_the_habit() -> None:
    """A space between the quote and the mark makes it the habit again."""
    text, removed = strip_em_dash(f'He shrugged {MARK} "fine" {MARK} and left.')
    assert MARK not in text
    assert removed == 2


def test_a_status_line_still_parses_after_the_strip() -> None:
    """The failure this would have caused is silent, which is why it is asserted here.

    `extraction`'s canon parser keys on a bare U+2014 as the `[STATUS]` line's own separator,
    with no alternation. A scene whose panel renders and whose state does not extract is
    indistinguishable from a scene that established nothing.
    """
    line = STATUS_TEMPLATE.format(subject="Theo", level=3, hp=10, hp_max=12, mp=1, mp_max=4, gold=7)
    scene = f"He put it down {MARK} and looked.\n\n{line}\n\nThe room went quiet."
    stripped, removed = strip_em_dash(scene)

    assert removed == 1, "the prose mark goes and the machine's separator does not"
    match = STATUS_PATTERN.search(stripped)
    assert match is not None
    assert match.group("subject") == "Theo"
    assert match.group("level") == "3"


def test_a_stop_does_not_collect_a_second_comma() -> None:
    """A mechanical rewrite that can produce ungrammatical prose is worse than the mark."""
    text, removed = strip_em_dash(f"He stopped, {MARK} then went on.")
    assert text == "He stopped, then went on."
    assert removed == 1


def test_the_strip_is_idempotent_and_leaves_clean_prose_alone() -> None:
    """It runs on every draft forever, so running twice has to mean running once."""
    original = f"She waited {MARK} counting {MARK} and the door opened."
    once, first = strip_em_dash(original)
    twice, second = strip_em_dash(once)
    assert twice == once
    assert second == 0
    assert first == 2

    clean = "She waited, counting, and the door opened."
    assert strip_em_dash(clean) == (clean, 0)


def test_the_mark_comes_from_its_one_registered_home() -> None:
    """The character a dossier is refused for carrying and the one a draft has removed.

    `voice.EXHIBITION_MARKERS` is where the mark lives, and `strip_em_dash` reads it rather than
    spelling it again, so the two cannot diverge into a gate that refuses one character and a
    rewrite that removes another.
    """
    assert MARK == "\u2014"
    assert strip_em_dash(f"a {MARK} b")[1] == 1
    assert strip_em_dash("a \u2013 b") == ("a \u2013 b", 0), (
        "the en dash is a different character and a different question; `statusline` accepts "
        "it where `extraction` does not, and that divergence is not this track's to settle"
    )


def test_the_floor_still_carries_the_mark_it_now_strips() -> None:
    """The residual §180 names before the fact, kept visible rather than written down once.

    `voice.axes_exhibited` exists because a text carrying a mark demonstrates it in every prompt
    it reaches — which is why a dossier written with an em dash is refused. The house floor is
    written with them and no rail has ever been pointed at it, so the drafting call exhibits the
    mark in the very rules the draft is written against. The strip makes that harmless rather
    than absent. **If a later track de-marks the floor, delete this test and correct §180 in
    place** — it asserts a gap, not a guarantee.
    """
    assert voice.axes_exhibited(house.HOUSE_RULES) == ("em_dash",)


# --- end to end ----------------------------------------------------------------------


def test_a_drafted_scene_reaches_the_store_without_the_mark(store: SqliteStore) -> None:
    """The seam, proven where it counts: what is committed is what was rewritten.

    The count rides on the acceptance event because removing the mark from the prose would
    otherwise remove the only way to see how often the model reached for it — the quantity read 1
    and read 11 both named.
    """
    prose = (
        f"Rook set the lantern on the ledger stone {MARK} the one that had not cracked {MARK} "
        "and counted what the night had cost him. Forty-five gold in, twenty gone to the flame, "
        "five more to the gatekeeper who had not looked up. He wrote none of it down. The tally "
        f"lived where it always had {MARK} behind his teeth, where no clerk could reach it, and "
        "he had never once been wrong about it before tonight."
    )
    registry, _ = registry_with(prose)
    seeded(store)

    conductor_for(store, registry).tick(START)

    accepted = [
        entry.event
        for entry in store.read_log()
        if entry.event.event_type is EventType.MANUSCRIPT_REVISION_ACCEPTED
    ]
    assert len(accepted) == 1
    assert accepted[0].payload["em_dashes_removed"] == 3

    committed = store.load_revision(accepted[0].revision_id or "")
    content = committed.node("scene-1").content or ""
    assert MARK not in content
    assert "ledger stone, the one that had not cracked, and counted" in content
