"""What a subject is called on the page, and the id a printed name reads back to.

Rendering prefers names that normalise back to their subjects. Status extraction also
recognises exact, unambiguous labels declared in accepted state, so a printed full name
does not lose an update stored under a shorter canonical id.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence

import litharness_contracts as lc

from litharness.domain import state as state_mod


def normalise_subject(name: str) -> str:
    """A subject id from a prose name. NFC, casefolded, whitespace collapsed to underscores."""
    folded = unicodedata.normalize("NFC", name).strip().casefold()
    return re.sub(r"\s+", "_", folded)

def humanise_subject(subject: str) -> str:
    """`normalise_subject`'s two moves undone: underscores back to spaces, words capitalised.

    Lossy in the direction that matters least. `mckay` comes back `Mckay`, because casefolding
    threw away the capital and nothing here can know it was there — which is exactly why
    `display_name` asks canon first and reaches this only when the book stated no name.
    """
    return " ".join(part.title() for part in subject.split("_") if part)


def status_subject_ids(records: Sequence[lc.StateRecord]) -> dict[str, str]:
    """Unambiguous status-subject labels, keyed by the normalised full printed label.

    Accept canonical ids and exact accepted `is_a` labels only. That predicate can also
    hold a kind, so this resolves an explicitly printed status owner, not names in prose
    or a preferred display name. No prefix, first-name or fuzzy matching is inferred.
    A label naming multiple subjects, including a collision with an id, is unresolved.
    """
    owners: dict[str, set[str]] = {}
    for record in records:
        if not state_mod.is_canon(record):
            continue
        labels = [record.subject]
        if record.predicate == "is_a" and isinstance(record.value, str):
            labels.append(record.value)
        for label in labels:
            normalised = normalise_subject(label)
            if normalised:
                owners.setdefault(normalised, set()).add(record.subject)
    return {label: next(iter(subjects)) for label, subjects in owners.items()
            if len(subjects) == 1}


def display_name(records: Sequence[lc.StateRecord], subject: str) -> str:
    """What a book prints where it names `subject` on the page — never the id itself.

    **The defect: a snake_case subject id reached a reader.** Pilot 15's draw 3 printed
    `[STATUS] tam_cawl — Keeping 1 | …` twice in one chapter while its column labels arrived
    display-formed, because the labels come off a declared `Sheet` and the subject was written
    out as the records hold it. Draw 2 of the same book printed `[STATUS] Mira Kell — …` from
    the *same* code and the same shape of prompt: the writer there substituted the name the
    instruction asks for ("write the character's name as your prose spells it") and draw 3's
    copied the example verbatim. So the raw id was in both prompts and both draws, and what
    stood between it and the page was a model choosing to paraphrase. That is the placement
    `system_voice_example` already refused to make for `{subject}`, arriving with an id in the
    slot instead of a brace.

    **Canon first.** `is_a` is where this vocabulary keeps names — `application/world.py`
    documents it to the Architect as *what a thing is called, in this world's own words*, and
    `gamesystem` already reads system, rung and ability names out of it. Both draws held one:
    `tam_cawl is_a Tam Cawl`, `mira_kell is_a Mira Kell`. Nothing was missing; nothing looked.

    **A name is used only when it normalises back to the subject.** This conservative
    rendering choice keeps a general `is_a` kind such as `mira_kell is_a mender` from
    replacing the person's name. Status extraction separately accepts unambiguous declared
    labels when the writer uses one; that does not change which name this renderer prints.

    A subject that is not already its own normalised form is a prose name a caller passed in
    (`Rook`, `Silas`), and it is returned untouched — title-casing it would damage a `McKay`
    that arrived spelled correctly.

    **What this cannot promise.** An id no display form normalises back to — a doubled or
    leading underscore — humanises to something that reads back as a different id. It is
    printed anyway: `humanise_subject` is not conditional, because a machine id on the page is
    the defect and there is no third form to fall to. Such an id is already unreachable from
    the Architect's vocabulary and `test_a_subject_id_that_cannot_round_trip_is_still_never_raw`
    pins the choice rather than hiding it.

    The first canon `is_a` that passes the guard wins. A book stating two names for one subject
    has contradicted itself somewhere this function has no standing to adjudicate.
    """
    if subject != normalise_subject(subject):
        return subject
    for record in records:
        if (
            record.subject == subject
            and record.predicate == "is_a"
            and state_mod.is_canon(record)
            and isinstance(record.value, str)
            and normalise_subject(record.value) == subject
        ):
            return record.value.strip()
    return humanise_subject(subject)
