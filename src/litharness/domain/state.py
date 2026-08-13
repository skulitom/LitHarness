"""Objective story state: what the book has established, and who is allowed to know it.

The fixtures' `state.json` carries what `cli import` was throwing away — sixteen records per
book, each with an evidence span into the prose that established it. `plans.py` stores
*statements* and `beats.py` derives the *work*; this module stores *facts* and
`domain/context.py` decides which of them a generator gets to see.

Like `plans.py`, this operates on the contract's `StateRecord` directly rather than
mirroring it into a local dataclass. There is nothing here the contract cannot say — no lock
taxonomy to add, no block payload to invent — so a parallel type would be a second answer to
"what is a state record" with no question only it could answer.

**Visibility is a whitelist, and an absent POV excludes rather than admits.** `pov_visibility`
empty means the fact is objective — anyone may be told it. Non-empty means only those
characters know it, so a packet built for anyone else must not carry it. The case that fixes
the rule is the golden suite's: `rec-brandt-knows-letter` is visible to `brandt` alone, and
drafting scene 6 from Mara's POV must not leak it. The suite forbids that record again in a
case with **no POV at all** (`q3-repair-bruno`), which settles the open question in the safe
direction: with no POV named, visibility cannot be established, so a restricted record is
excluded. Defaulting the other way would make "forgot to pass the POV" mean "leak everything
private", and nothing downstream could tell that had happened.

**Only canon enters a packet.** `PROPOSED` is a candidate no policy decision has accepted, and
feeding one back to the generator as established fact would launder a guess into canon inside
one loop iteration — the same failure §11 names when it says no proposal becomes canon
merely because a model returned it.

**Story-time slicing is honoured, never fabricated.** `order_key` is an opaque lexicographic
string the snapshot's author chose (`"s1"`…`"s4"` in both fixtures), and *nothing anywhere
defines a mapping from a manuscript scene to one*. Deriving `f"s{beat.ordinal}"` would work
on exactly these two books and silently mis-slice any other, so `records_before` takes a
cutoff and the caller supplies it or does not. In the live loop the question does not arise:
records are extracted from accepted prose, so the only records that exist are about scenes
already written. It arises for an imported book, whose records describe scenes not yet
drafted — which is exactly when a guess would be invisible and wrong.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import litharness_contracts as lc

#: Authorities whose records are established fact rather than proposals awaiting a decision.
CANON: frozenset[lc.StateAuthority] = frozenset(
    {lc.StateAuthority.AUTHOR_LOCKED, lc.StateAuthority.ACCEPTED_CANON}
)

#: `StateRecordKind` and `ResourceKind` are *not* the same vocabulary, and the one place they
#: differ is the one a golden target names: an `event` record is referenced as a
#: `state_event` resource. Mapped explicitly rather than by `ResourceKind(record.kind.value)`,
#: which would raise on that member and pass on every other — a bug that looks like it works.
RESOURCE_KIND: dict[lc.StateRecordKind, lc.ResourceKind] = {
    lc.StateRecordKind.ASSERTION: lc.ResourceKind.ASSERTION,
    lc.StateRecordKind.EVENT: lc.ResourceKind.STATE_EVENT,
    lc.StateRecordKind.RELATIONSHIP: lc.ResourceKind.RELATIONSHIP,
    lc.StateRecordKind.KNOWLEDGE: lc.ResourceKind.KNOWLEDGE,
    lc.StateRecordKind.THREAD: lc.ResourceKind.THREAD,
    lc.StateRecordKind.WORLD_RULE: lc.ResourceKind.WORLD_RULE,
    lc.StateRecordKind.UNKNOWN: lc.ResourceKind.UNKNOWN,
}

#: A thread record whose value is this is still owed a payoff. §10.2's "overdue payoff" and
#: §9.1's foreshadow ledger both start here.
THREAD_OPEN = "open"


@dataclass(frozen=True, slots=True)
class ImportedState:
    """A state snapshot authored elsewhere, re-anchored on a local book and branch."""

    book_id: str
    branch_id: str
    records: tuple[lc.StateRecord, ...]
    #: The upstream snapshot's `revision_id`, kept as provenance. See the module docstring.
    source_revision_id: str | None = None


def import_state(
    source: lc.StateSnapshot, *, book_id: str, branch_id: str
) -> ImportedState:
    """Adopt a foreign state snapshot against a local book and branch."""
    return ImportedState(
        book_id=book_id,
        branch_id=branch_id,
        records=tuple(source.records),
        source_revision_id=source.revision_id,
    )


def resource_kind(record: lc.StateRecord) -> lc.ResourceKind:
    """The `ResourceKind` a reference to this record carries. See `RESOURCE_KIND`."""
    return RESOURCE_KIND.get(record.kind, lc.ResourceKind.UNKNOWN)


def visible_to(record: lc.StateRecord, pov_character_id: str | None) -> bool:
    """Whether a packet built for this POV may carry this record.

    Empty `pov_visibility` is objective. Non-empty restricts, and `None` for the POV does not
    satisfy a restriction — see the module docstring for why that direction is the safe one.
    """
    if not record.pov_visibility:
        return True
    return pov_character_id is not None and pov_character_id in record.pov_visibility


def is_canon(record: lc.StateRecord) -> bool:
    return record.authority in CANON


def order_key_of(record: lc.StateRecord) -> str | None:
    return record.story_position.order_key if record.story_position else None


def records_before(
    records: Sequence[lc.StateRecord], cutoff: str | None
) -> tuple[lc.StateRecord, ...]:
    """Records established at or before ``cutoff`` in story time.

    ``None`` means no cutoff and returns everything — the live loop's case, where the only
    records that exist are about scenes already accepted. A record with no `story_position`
    survives a cutoff rather than being dropped: it asserts no narrative position, and
    treating "unplaced" as "later than everything" would silently discard world rules and
    standing relationships from every packet.
    """
    if cutoff is None:
        return tuple(records)
    return tuple(
        record
        for record in records
        if (key := order_key_of(record)) is None or key <= cutoff
    )


def open_threads(records: Sequence[lc.StateRecord]) -> tuple[lc.StateRecord, ...]:
    """Thread records still awaiting a payoff, in story order.

    The promise the mystery fixture makes — "the sealed letter must be read aloud at the will
    reading before the book ends" — is one of these, and it is the item the golden suite makes
    mandatory for the scene that has to pay it off.
    """
    return in_story_order(
        record
        for record in records
        if record.kind is lc.StateRecordKind.THREAD and record.value == THREAD_OPEN
    )


def in_story_order(records: Iterable[lc.StateRecord]) -> tuple[lc.StateRecord, ...]:
    """Sort by story position, then record id. Unplaced records sort last.

    The tiebreak on `record_id` is not cosmetic: two records at `"s1"` must pack in the same
    order on every run or the packet is not reproducible, and §13's reproducibility levels
    are what let a decision record mean anything later.
    """
    return tuple(
        sorted(
            records,
            key=lambda record: (
                order_key_of(record) is None,
                order_key_of(record) or "",
                record.record_id,
            ),
        )
    )


def describe(record: lc.StateRecord) -> str:
    """One line of prose-adjacent text for a packet item.

    Deliberately flat — `subject predicate value` — rather than a sentence. A renderer that
    wrote "Mara knows that the key is hidden under the floorboard" would be inventing prose
    the record does not contain, and the generator would then be free to reproduce that
    phrasing as though it were the book's.
    """
    value = record.value
    if isinstance(value, dict):
        rendered = ", ".join(f"{key}={value[key]}" for key in sorted(value))
    elif isinstance(value, list):
        rendered = ", ".join(str(item) for item in value)
    elif value is None:
        rendered = ""
    else:
        rendered = str(value)
    parts = [record.subject, record.predicate, rendered]
    if record.object_ref:
        parts.append(f"({record.object_ref})")
    return " ".join(part for part in parts if part)


__all__ = [
    "CANON",
    "RESOURCE_KIND",
    "THREAD_OPEN",
    "ImportedState",
    "describe",
    "import_state",
    "in_story_order",
    "is_canon",
    "open_threads",
    "order_key_of",
    "records_before",
    "resource_kind",
    "visible_to",
]
