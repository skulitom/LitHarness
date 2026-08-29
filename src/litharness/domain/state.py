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

**The live loop's half of that paragraph stopped being the whole story, in two ways.** It is
true of records *extracted* from accepted prose and false of **seeded** ones: a want or a fear
that changes across a book is future-dated by construction, so with no cutoff scene one is told
what the character will want in chapter two. And it is not quite true of extracted records
either, because §4.1 skips a blocked beat rather than waiting on it — a beat that parks leaves
a hole, `replan` plans the hole afresh, and canon by then holds what the *later* scenes
established. `application/planner.py::packet_for` now supplies a cutoff — the beat's own
`story_order_key`, passed through `extraction.stated_position`, so it abstains for exactly the
books extraction abstains for and an imported book's packet is unchanged. This module still
refuses to derive the key; it is handed one or it is not.

**That paragraph described something that did not exist until `domain/extraction.py`, and
what it now describes is narrower than it reads.** Extraction does not *mint* an order key
either: it reads back the one the book's own imported evidence already attests for a scene,
and abstains where the book is silent or ambiguous. So a book with no imported snapshot —
Book Zero, §17 Stage 3 — has nothing to read back and extracts nothing. The price of
refusing to fabricate is real and is paid there, not here.
"""

from __future__ import annotations

import enum
import re
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
_SCENE_KEY = re.compile(r"s(?P<number>\d+)$")
_SCHEDULE_KEY = re.compile(r"\d+$")

#: Order keys the pipeline mints for a position the book **reaches**: `beats.beats_for` writes
#: `s1`…`s6` at book width and `serials.beats_for_arc` writes `s000001` at serial width. Every
#: cutoff on the live drafting path is one of these.
SCENE_KEYS = "scene"

#: Order keys a *declaration* states a position in: zero-padded digits, `domain/position.py`'s
#: own gap-10 format, which is what an Architect reaches for when it schedules an arc ahead of
#: the writing. A schedule is a position the book has **not** reached.
SCHEDULE_KEYS = "schedule"


def key_space(key: str | None) -> str | None:
    """Which of the two order-key spaces `key` states a position in, or `None` for neither.

    **The two spaces were never introduced to each other, and string comparison married them
    silently** (§165). Scene keys begin with a letter and schedule keys are digits, so every
    schedule key sorts *below* every scene key: `'0350' <= 's1'` is `True`. Serial Pilot 15's
    Architect declared its protagonist's whole arc as three scheduled snapshots and left the
    opening state un-keyed — exactly what the `status_snapshot` line asks for — and the fold
    then handed scene one the last of the three. Nine characters wide, and the magnitude of the
    number is irrelevant: *any* schedule key lands before *every* scene.

    **A key in neither space is the case that does not even fail consistently.** Across the
    pilot databases 127 records carry a word in this slot — `clearance`, `grade`, `cuff`,
    `reckoning`, `zz_c` — §152's `--order-key`/`--value` trap, where a criterion name was typed
    into the position slot. Those sort against scene keys by spelling: `'clearance' < 's1'` and
    `'zz_c' > 's1'`, so one is permanently past and the other permanently future, on the same
    book, for the same reason. `None` is returned for both, and nothing comparable to anything
    is the only honest answer about a coordinate nobody can place. `world check` reports them.

    An **absent** key is not in this vocabulary at all: it is the timeless declaration, and
    every reader here already carries it through every cutoff.
    """
    if key is None:
        return None
    if _SCENE_KEY.fullmatch(key):
        return SCENE_KEYS
    if _SCHEDULE_KEY.fullmatch(key):
        return SCHEDULE_KEYS
    return None


def comparable(key: str | None, cutoff: str | None) -> bool:
    """Whether two order keys state positions in one space, and so may be compared at all.

    **This is the whole of the fix, and it is deliberately not a normaliser.** Nothing here
    converts a schedule key into a scene key or guesses which scene an Architect meant: a
    record cannot be taken back (`record_id_for` is position-blind and the store is
    `INSERT OR IGNORE`, so a corrected position does not even land), and a projection would put
    this module in the business of authoring positions the world never declared. What it does
    is refuse to compare two coordinates that do not measure the same thing.

    A key in neither space compares with nothing, **including another key in neither space**.
    Two words in the position slot are two unplaceable records, not two records at a shared
    position, and treating them as ordered would re-enter the defect one address along.
    """
    space = key_space(key)
    return space is not None and space == key_space(cutoff)


@dataclass(frozen=True, slots=True)
class ImportedState:
    """A state snapshot authored elsewhere, re-anchored on a local book and branch."""

    book_id: str
    branch_id: str
    records: tuple[lc.StateRecord, ...]
    #: The upstream snapshot's `revision_id`, kept as provenance. See the module docstring.
    source_revision_id: str | None = None


def import_state(source: lc.StateSnapshot, *, book_id: str, branch_id: str) -> ImportedState:
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


def scene_cutoff(records: Sequence[lc.StateRecord], scene_ordinal: int) -> str | None:
    """Project a reading-order scene ordinal into the records' declared ``sN`` width.

    This is deliberately an entitlement check, not a universal conversion.  It returns no
    coordinate when positioned records use a different vocabulary or disagree about width.
    New serials use the fixed six-digit form; imported legacy fixtures consistently use one.
    """
    if scene_ordinal < 1:
        return None
    positioned = [key for record in records if (key := order_key_of(record)) is not None]
    if not positioned:
        return None
    matches = [_SCENE_KEY.fullmatch(key) for key in positioned]
    if any(match is None for match in matches):
        return None
    widths = {len(match.group("number")) for match in matches if match is not None}
    if len(widths) != 1:
        return None
    width = next(iter(widths))
    return f"s{scene_ordinal:0{width}d}"


def records_before(
    records: Sequence[lc.StateRecord], cutoff: str | None
) -> tuple[lc.StateRecord, ...]:
    """Records established at or before ``cutoff`` in story time.

    ``None`` means no cutoff and returns everything — the live loop's case, where the only
    records that exist are about scenes already accepted. A record with no `story_position`
    survives a cutoff rather than being dropped: it asserts no narrative position, and
    treating "unplaced" as "later than everything" would silently discard world rules and
    standing relationships from every packet.

    **A record that asserts a position in the other space does not survive, and that is a
    different case from asserting none** (§166). `'0350' <= 's1'` is `True`, so before this
    every scheduled declaration in the book passed every scene's cutoff: on serial15.db this
    admitted 18 records — three scheduled snapshots, four `stands_at`, three `can_do` and eight
    `disclosed_to` — into a packet built at `s1`. Un-keyed means *true of the book*, so it
    belongs at every position; a schedule key means *true at a position this book has not
    reached*, so it belongs at none of them yet. The two must not collapse into each other, and
    string comparison collapsed them silently in the leaking direction.
    """
    if cutoff is None:
        return tuple(records)
    return tuple(
        record
        for record in records
        if (key := order_key_of(record)) is None or (comparable(key, cutoff) and key <= cutoff)
    )


class StateMoment(enum.StrEnum):
    """Which side of a story coordinate a model is asking from."""

    ENTERING = "entering"
    WITHIN = "within"
    THROUGH = "through"


@dataclass(frozen=True, slots=True)
class StoryBoundary:
    """A precise point from which story state is viewed.

    A scene key is the stable persistence coordinate.  ``WITHIN`` adds the evidence boundary
    needed when a caller is stopped part-way through that scene: only facts whose cited span
    has ended by ``offset`` are established.  Chapter and volume state remain cheap derived
    views of the latest scene boundary they contain; they are not competing sources of truth.
    """

    cutoff: str | None
    moment: StateMoment = StateMoment.THROUGH
    logical_id: str | None = None
    offset: int | None = None

    def __post_init__(self) -> None:
        if self.moment is StateMoment.WITHIN:
            if self.cutoff is None or not self.logical_id or self.offset is None:
                raise ValueError("within-scene state needs a cutoff, logical id, and offset")
            if self.offset < 0:
                raise ValueError("within-scene state offset cannot be negative")
        elif self.offset is not None:
            raise ValueError("an offset is only meaningful within a scene")
        elif self.moment is StateMoment.THROUGH and self.logical_id is not None:
            raise ValueError("a logical id is not needed after a complete scene boundary")


def reached_boundary(record: lc.StateRecord, boundary: StoryBoundary) -> bool:
    """Whether ``record`` is established on the caller's side of ``boundary``.

    **This is the gate `eligible_records` runs, so it is the one the live packet passes
    through, and it carried `records_before`'s defect with it** (§166). A key that states a
    position in the other space is not before this boundary and is not at it: it is
    unplaceable relative to it, and the honest answer to "has the book reached this yet" is
    *no*. The equality branches below are safe to leave keyed on the raw string because two
    keys that are equal are in the same space by construction — `key_space` partitions on
    shape, and one string has one shape.
    """
    key = order_key_of(record)
    if boundary.cutoff is None or key is None:
        return True
    if not comparable(key, boundary.cutoff):
        return False
    if key < boundary.cutoff:
        return True
    if key > boundary.cutoff:
        return False
    if boundary.moment is StateMoment.ENTERING:
        # A seed or schedule dated at this scene is effective as the scene begins.  An
        # extracted fact cited to this very scene is different: its evidence says the prose
        # establishes it somewhere inside, so showing it at entry would reveal its own future.
        # When no target id was supplied, abstain on evidence-backed same-scene records.
        if not record.evidence:
            return True
        if boundary.logical_id is None:
            return False
        return not any(span.source.logical_id == boundary.logical_id for span in record.evidence)
    if boundary.moment is StateMoment.THROUGH:
        return True
    assert boundary.logical_id is not None and boundary.offset is not None
    # A same-scene assertion without located evidence cannot honestly be placed before this
    # stop point.  Abstention here is safer than leaking the end of the scene into its middle.
    return any(
        span.source.logical_id == boundary.logical_id and span.end <= boundary.offset
        for span in record.evidence
    )


def eligible_records(
    records: Sequence[lc.StateRecord],
    *,
    cutoff: str | None = None,
    pov_character_id: str | None = None,
    excluded_predicates: Sequence[str] = (),
    moment: StateMoment = StateMoment.THROUGH,
    logical_id: str | None = None,
    offset: int | None = None,
) -> tuple[lc.StateRecord, ...]:
    """Canon a model may see at ``cutoff`` from ``pov_character_id``.

    This is the shared gate for model-facing state.  A character sheet, a compact state view,
    and an individual fact must not answer time and visibility three different ways: doing so
    lets a fact rejected from one section reappear through another.  Configuration predicates
    are supplied by the caller because the state vocabulary deliberately does not depend on
    the extraction vocabulary that declares them.
    """
    excluded = frozenset(excluded_predicates)
    boundary = StoryBoundary(cutoff, moment, logical_id, offset)
    return tuple(
        record
        for record in records
        if is_canon(record)
        and record.predicate not in excluded
        and visible_to(record, pov_character_id)
        and reached_boundary(record, boundary)
    )


def active_projection(
    records: Sequence[lc.StateRecord],
    *,
    changing_edge_predicates: Sequence[str] = (),
    multi_valued_predicates: Sequence[str] = (),
) -> tuple[tuple[lc.StateRecord, ...], tuple[lc.StateRecord, ...]]:
    """Return ``(current, superseded_history)`` without erasing genuine events.

    Assertions such as a want or status snapshot can change over story time.  Presenting every
    earlier value under *Established facts* tells a model that all values hold simultaneously.
    For each changing slot this keeps every record at the latest reached position current and
    returns older values separately, where a caller can label them as history.

    Events, threads and world rules accumulate and are therefore never collapsed.  Ordinary
    relationships are cumulative too because their target is part of the slot; callers name
    the small set of relationship predicates (currently standing) whose target itself changes.
    Conflicting records at the same latest position are all retained so the projection cannot
    hide a contradiction from a model or a diagnostic.
    """
    changing_edges = frozenset(changing_edge_predicates)
    multi_valued = frozenset(multi_valued_predicates)
    groups: dict[tuple[str, str, str], list[lc.StateRecord]] = {}
    passthrough: list[lc.StateRecord] = []
    for record in records:
        if (
            record.kind
            in {
                lc.StateRecordKind.EVENT,
                lc.StateRecordKind.THREAD,
                lc.StateRecordKind.WORLD_RULE,
            }
            or record.predicate in multi_valued
        ):
            passthrough.append(record)
            continue
        if record.object_ref and record.predicate not in changing_edges:
            edge = record.object_ref
        else:
            edge = str(record.value or "") if record.predicate in changing_edges else ""
        groups.setdefault((record.subject, record.predicate, edge), []).append(record)

    current = list(passthrough)
    history: list[lc.StateRecord] = []
    for members in groups.values():
        positioned = [record for record in members if order_key_of(record) is not None]
        if not positioned:
            current.extend(members)
            continue
        latest_key = max(order_key_of(record) or "" for record in positioned)
        for record in members:
            if order_key_of(record) == latest_key:
                current.append(record)
            else:
                history.append(record)
    return in_story_order(current), in_story_order(history)


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
    "StateMoment",
    "StoryBoundary",
    "active_projection",
    "describe",
    "eligible_records",
    "import_state",
    "in_story_order",
    "is_canon",
    "open_threads",
    "order_key_of",
    "reached_boundary",
    "records_before",
    "resource_kind",
    "scene_cutoff",
    "visible_to",
]
