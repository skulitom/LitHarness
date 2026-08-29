"""Stage-0 §169: the subject on a printed line is a name, never a machine id.

**The defect, from the page.** Pilot 15's draw 3 printed `[STATUS] tam_cawl — Keeping 1 |
Reach 0 | Marks holding 1 | Work in hand 0/1` twice in one chapter. Every column label beside
it arrived display-formed, because labels come off a declared `Sheet`; the subject was written
out as the records hold it, which is what `render_status_line` documented itself as doing.

**What made it look intermittent.** Draw 2 of the same book, same code, same shape of prompt,
printed `[STATUS] Mira Kell — …`. The example line handed to the writer carried the raw id in
*both* runs — `serial15b.db` and `serial15c.db` both show it in the stored system message — and
what differed was only whether the model took up the instruction to write the character's name
as its prose spells it. So the code path was defective in both draws and one writer happened to
cover for it. No test can hold a model to that, which is why the fix is on this side.

**And nothing was missing.** Both books held the name in canon: `tam_cawl is_a Tam Cawl`,
`mira_kell is_a Mira Kell`. `is_a` is where this vocabulary keeps names — `application/world.py`
documents it to the Architect in those words, and `gamesystem` already reads system, rung and
ability names out of it. The status line was the one printed surface that never asked.

The load-bearing test here is `test_the_printed_name_reads_back_as_the_subject_it_stands_for`.
The rest protect properties; that one is why `display_name` refuses a name at all rather than
printing whatever `is_a` holds — a printed name that normalises to a different id is not read
back under a second subject, it is *dropped*, and the book quietly stops recording its own
state while every line still looks right.

No model reads, ranks or judges anything in this file, and no bar is declared anywhere in it.
"""

from __future__ import annotations

import litharness_contracts as lc
import pytest

from litharness.domain import worlds
from litharness.domain.extraction import (
    STATUS_PREDICATE,
    Sheet,
    SheetField,
    display_name,
    extract_state,
    humanise_subject,
    render_status_line,
    sheet_for,
    system_voice_example,
)

#: Draw 3's own sheet, in draw 3's own words, so the shapes under test are the shapes that
#: reached the reader rather than the default LitRPG line.
_SHEET = Sheet(
    (
        SheetField("keeping", "Keeping"),
        SheetField("reach", "Reach"),
        SheetField("marks", "Marks holding"),
        SheetField("work", "Work in hand", paired=True),
    )
)

_VALUE: dict[str, object] = {"keeping": 1, "reach": 0, "marks": 1, "work": 0, "work_max": 1}


def _canon(subject: str, predicate: str, value: object, **kwargs: object) -> lc.StateRecord:
    return worlds.world_record(
        subject,
        predicate,
        value=value,
        authority=lc.StateAuthority.ACCEPTED_CANON,
        **kwargs,  # type: ignore[arg-type]
    )


def _named(subject: str, name: str) -> list[lc.StateRecord]:
    """A book that holds one subject, its name, and a snapshot of it — draw 3's minimum."""
    return [
        _canon(subject, "is_a", name),
        worlds.world_record(
            subject,
            STATUS_PREDICATE,
            value=dict(_VALUE),
            order_key="s1",
            authority=lc.StateAuthority.ACCEPTED_CANON,
        ),
    ]


# --- the defect ----------------------------------------------------------------------------


def test_the_status_line_never_prints_a_raw_subject_id() -> None:
    """Draw 3's line, rendered by the fixed path.

    The assertion is on the *absence* of the id as much as on the presence of the name: a
    renderer that printed `Tam Cawl (tam_cawl)` would satisfy the second half and still put
    the machine id in front of a reader.
    """
    records = _named("tam_cawl", "Tam Cawl")

    line = render_status_line("tam_cawl", _VALUE, sheet=_SHEET, records=records)

    assert line == "[STATUS] Tam Cawl — Keeping 1 | Reach 0 | Marks holding 1 | Work in hand 0/1"
    assert "tam_cawl" not in line


def test_the_example_the_writer_is_shown_carries_the_name_and_not_the_id() -> None:
    """The surface the defect actually travelled on.

    `system_voice_example` is what the drafting prompt carries, and draw 3's writer copied it
    verbatim into the chapter. Fixing `render_status_line` without this call site passing its
    records would have left the prompt — and therefore the page — exactly as it was.
    """
    records = _named("tam_cawl", "Tam Cawl")

    line = system_voice_example(records)

    assert line is not None
    assert line.startswith("[STATUS] Tam Cawl — ")
    assert "tam_cawl" not in line


def test_a_book_with_no_name_on_record_still_never_shows_the_id() -> None:
    """The fallback half. A book that stated no `is_a` is not a book that may print a machine
    id; it is a book whose name has to be derived from the id, which is what the id was made
    out of in the first place."""
    records = [
        worlds.world_record(
            "tam_cawl",
            STATUS_PREDICATE,
            value=dict(_VALUE),
            order_key="s1",
            authority=lc.StateAuthority.ACCEPTED_CANON,
        )
    ]

    assert display_name(records, "tam_cawl") == "Tam Cawl"
    assert display_name((), "mira_kell") == "Mira Kell"


# --- which name wins, and why ----------------------------------------------------------------


def test_the_books_own_spelling_beats_the_humanised_id() -> None:
    """Why canon is asked first. Casefolding threw the capital away and nothing downstream can
    put it back; the book still knows, and `is_a` is where it wrote it down."""
    assert humanise_subject("mckay") == "Mckay"
    assert display_name(_named("mckay", "McKay"), "mckay") == "McKay"


def test_a_name_that_does_not_normalise_back_to_the_subject_is_refused() -> None:
    """`is_a` is a general predicate and a book may file a kind in it rather than a name —
    `mira_kell is_a mender` is a legitimate sentence in this vocabulary. The round-trip guard
    tells the two apart without this module having to decide what a name looks like."""
    records = _named("mira_kell", "mender")

    assert display_name(records, "mira_kell") == "Mira Kell"


def test_a_proposed_name_is_not_a_name_yet() -> None:
    """Draw 3 left seven records unaccepted as contradiction slots. A proposal is a claim the
    book has not adopted, `is_canon` is the line between the two everywhere else in this
    package, and printing off one would put an unadopted fact on the page."""
    records = [
        worlds.world_record("tam_cawl", "is_a", value="Tam Cawl"),  # PROPOSED by default
        worlds.world_record(
            "tam_cawl",
            STATUS_PREDICATE,
            value=dict(_VALUE),
            order_key="s1",
            authority=lc.StateAuthority.ACCEPTED_CANON,
        ),
    ]

    assert display_name(records, "tam_cawl") == "Tam Cawl"  # humanised, not read off the proposal
    assert display_name([records[0]], "tam_cawl") == humanise_subject("tam_cawl")


@pytest.mark.parametrize("name", ["Rook", "Silas", "McKay", "Mira Kell"])
def test_a_prose_name_a_caller_passed_is_printed_unchanged(name: str) -> None:
    """A subject that is not its own normalised form was never an id. Title-casing it would
    damage a `McKay` that arrived spelled correctly, which is the failure the humanising
    fallback exists to avoid rather than to cause."""
    assert display_name((), name) == name
    assert render_status_line(name, _VALUE, sheet=_SHEET).startswith(f"[STATUS] {name} — ")


# --- the property the guard protects ---------------------------------------------------------


def test_the_printed_name_reads_back_as_the_subject_it_stands_for() -> None:
    """The whole loop: canon names a subject, the line prints its name, extraction reads the
    line and lands on that same subject.

    `extract_state` skips any subject canon has not already used, so a printed name that
    normalised elsewhere would not be mis-filed — it would extract nothing at all, scene after
    scene, with the page still looking correct. That is the failure mode this module says no
    gate catches, and it is why the name is guarded rather than trusted.
    """
    records = _named("tam_cawl", "Tam Cawl")
    line = render_status_line("tam_cawl", _VALUE, sheet=sheet_for(records), records=records)

    [extracted] = extract_state(
        f"He struck it.\n\n{line}\n",
        known=records,
        project_id="p",
        book_id="b",
        branch_id="br",
        logical_id="s2",
        version_id="v",
        stated_order_key="s2",
    )

    assert extracted.subject == "tam_cawl"
    assert extracted.predicate == STATUS_PREDICATE
    assert extracted.value == _VALUE


def test_a_subject_id_that_cannot_round_trip_is_still_never_raw() -> None:
    """The residual, pinned rather than hidden.

    An id with a doubled or leading underscore has no display form that normalises back to it,
    so its printed line will not read back. It is printed humanised anyway: a machine id on the
    page is the defect this exists to end, and there is no third form to fall to. Such an id is
    unreachable from the Architect's declared vocabulary, and stating the choice here is worth
    more than a branch nobody can reach.
    """
    assert humanise_subject("tam__cawl") == "Tam Cawl"
    assert display_name((), "_tam") == "Tam"
    assert "_" not in render_status_line("tam__cawl", _VALUE, sheet=_SHEET)
