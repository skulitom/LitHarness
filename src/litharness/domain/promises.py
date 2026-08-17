"""The promise/payoff ledger's vocabulary, and the overdue arithmetic over it.

§61 Add 2: the first metric aimed at PLAN §1a.3 item 3 — promises the book opens and does
not pay. `domain/state.py`'s `open_threads` was always "the exact seed" of this ledger, and
it is deliberately **not** the implementation: `open_threads` tests `record.value == "open"`
by exact equality, both golden fixtures author that value, and folding a payoff-due position
into the value would silently empty the packet's THREADS section, the summarizer's ground
truth, and the status thread counts in one edit. So a promise is its own row in its own
table (migration 023), written by the summary handler from the extended summary call, and
this module is the pure vocabulary both sides share.

**Everything here is arithmetic over model-sourced rows.** The rows come from a model's
`promises_opened`/`promises_paid` answer, so nothing built on them may block or park:
`promise.overdue.v0` (domain/integrity.py) mints MINOR findings only, and §10.4's promotion
rules are untouched. The refutation shaping this is scene_change_profile's: LEDGER delta is
not DRAMATIC delta — the confession scene carried zero records — so the promise question
takes a model leg, and a model leg stays advisory until calibrated.

**Story keys are `beats_for`'s, never minted here.** `overdue_promises` compares order keys
as strings, which is only correct because `beats_for` zero-pads them to the book's own width
(`s10 < s2` unpadded is the recorded bug). The summary handler derives every promise key by
indexing into the beats `beats_for` returned rather than formatting its own, so there is one
padding implementation in the project, not two that must agree. A template that is not
chronological mints no keys at all, and this ledger abstains there exactly as milestones do:
no promise rows, no overdue findings — no key rather than a guessed one.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256

#: A promise the book has opened and not yet paid. The vocabulary deliberately mirrors
#: `state.THREAD_OPEN`'s single-word values rather than inventing richer states: write-once
#: open, one transition to paid, nothing else to be in.
PROMISE_OPEN = "open"
PROMISE_PAID = "paid"


@dataclass(frozen=True, slots=True)
class Promise:
    """One thing the book owes, with the story position it is owed by.

    A projection of a `promises` table row (migration 023), not a state record: keeping it
    off `lc.StateRecord` is what keeps `open_threads`, `detect_contradictions` and
    `has_story_vocabulary` blind to it — each of which the extraction-state map records as
    breaking if a promise were folded into their vocabulary.
    """

    promise_id: str
    subject: str
    description: str
    #: Story order key of the scene whose summary opened this, in `beats_for`'s padding.
    opened_at_key: str
    #: When the book owes payment, at the latest. `None` never occurs on rows the summary
    #: handler writes (absent hints default to the final scene key), and `overdue_promises`
    #: abstains on it rather than treating "no due date" as "always due".
    due_key: str | None
    opened_by_revision: str
    status: str = PROMISE_OPEN
    paid_at_key: str | None = None
    paid_by_revision: str | None = None
    #: The model whose summary call asserted this promise. Provenance, and the reason the
    #: overdue finding's confidence basis is `heuristic` rather than `deterministic`.
    model: str = ""


def promise_id_for(book_id: str, subject: str) -> str:
    """Content-derived from the book and the normalised subject, and from nothing else.

    Deliberately value-insensitive, which is the opposite discipline from
    `extraction.record_id_for` because the failure modes are opposite: a contradiction
    detector needs two disagreeing readings to be two rows, while a promise ledger needs
    the same subject re-reported by a re-summarised scene to be **one** row — `INSERT OR
    IGNORE` on this id is what makes re-extraction converge instead of stacking a duplicate
    promise per replay. A changed description under the same subject is the same promise
    described differently, not a new debt.
    """
    return "prm-" + sha256((book_id + subject).encode("utf-8")).hexdigest()[:24]


def parse_due_hint(hint: object) -> int | None:
    """The scene number a model's ``due_hint`` names, or None when it names none.

    The model is asked for a story position by scene number and models answer in shapes:
    ``12``, ``"12"``, ``"scene 12"``, ``"by s12"``. The first integer in the answer is the
    reading; anything else — null, prose with no digits, a bool — is "unparseable", and the
    caller defaults the due key to the book's final scene rather than guessing, so a
    promise with an unreadable due date is at latest overdue when the book ends unpaid.
    """
    if isinstance(hint, bool):
        return None
    if isinstance(hint, int):
        return hint if hint > 0 else None
    if isinstance(hint, str):
        match = re.search(r"\d+", hint)
        if match is None:
            return None
        number = int(match.group())
        return number if number > 0 else None
    return None


def overdue_promises(
    open_promises: Sequence[Promise], current_key: str | None
) -> tuple[Promise, ...]:
    """Open promises whose due position is strictly before the position being drafted.

    Pure arithmetic, in the order the ledger supplied. String comparison is correct only
    because both keys come from `beats_for`'s zero-padded minting — see the module
    docstring — and the comparison is strict (`<`): a scene *at* the due position is the
    scene still entitled to pay.

    Abstains, returning nothing, when `current_key` is None — a template that is not
    chronological minted no position for this beat, and comparing against a guessed one
    would be this module inventing the exact thing `beats_for` refused to. A promise whose
    own `due_key` is None is skipped for the same reason.
    """
    if current_key is None:
        return ()
    return tuple(
        promise
        for promise in open_promises
        if promise.status == PROMISE_OPEN
        and promise.due_key is not None
        and promise.due_key < current_key
    )


def describe_owed(promise: Promise) -> str:
    """The packed-item line for one open promise: what is owed, and by when.

    Deliberately prefixed "owes:" and phrased as a debt rather than as a fact — this line
    rides in the packet's THREADS section beside canon-backed open threads, and a rendering
    that read as an established event would launder a model's proposal into canon by
    register alone.
    """
    if promise.due_key is None:
        return f"owes: {promise.description}"
    return f"owes: {promise.description} (due by {promise.due_key})"


__all__ = [
    "PROMISE_OPEN",
    "PROMISE_PAID",
    "Promise",
    "describe_owed",
    "overdue_promises",
    "parse_due_hint",
    "promise_id_for",
]
