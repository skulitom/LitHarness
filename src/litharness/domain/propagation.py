"""The propagation engine: given a change, which other nodes does it reach?

§17 Stage 2's remaining work, and the half of it that had a measuring instrument and no
subject. `domain/impact.py` scores a blast-radius prediction against the gold suites and
ships three baselines for it to beat — `predict_nothing`, `predict_everything` (precision
**0.481**, the base rate), and `predict_downstream_scenes` (0.333, refuted before anything was
built). Nothing produced a prediction for it to score. The clause was executable and had
nothing to execute on.

**What the gold actually grades, restated because it shapes every rule below.**
`GoldImpactExpectation` carries no character offsets, so this is blast radius at *node*
granularity: given this change, which other nodes must move, which must not. And the suite
labels state records and findings alongside scenes, so "node" means any addressable thing the
book holds — `scene-3` and `rec-s3-status` are both answers.

Four rules, one per semantic change kind the contract names and this engine can honestly
read. Each is grounded in a different kind of evidence, which is the point: the heuristic
anyone reaches for first — everything positioned after the edit — scores *worse* than guessing
everything, and `tests/test_impact.py` refutes it by measurement rather than by argument.

* **`surface_only` reaches nothing.** A curly apostrophe changes a content hash and no
  referent. This is `e3-typography-only`, the case §17 names: eight `safe_preserve` targets,
  no `must_update` at all, and the one an engine optimised for recall fails.
* **`entity_renamed` reaches wherever the old name is spelled** — in prose on a word boundary,
  and in records whose subject or value is the entity. It reaches **backwards as well as
  forwards**, because a name is not carried forward, it is simply written, and every place it
  is written is wrong the moment it changes. Occurrences inside a preserved alias do not
  count; that is what the change set's `preserve_aliases` is for.
* **`fact_changed` reaches forward only**, to what states the fact after the change: later
  scenes carrying both the subject and the predicate, and records asserting that predicate of
  that subject from the change's position onward. A balance before the purchase was true
  before and stays true; a balance after it is wrong whether or not it repeats the number that
  changed, which is why the anchor is the predicate rather than the value.
* **`event_moved` reaches the window between where it was and where it goes** — the scenes
  strictly between the two edited nodes, plus the records at the origin sharing the moved
  event's subject, which is knowledge acquired at the event travelling with it. Before the
  origin the event had not happened either way; after the destination it has.

**Anything else abstains, and says so.** `event_added`, `event_removed`, `plan_changed`,
`pov_changed`, `rule_changed` and `unknown` are in the contract's vocabulary and have no rule
here. They come back in `Propagation.unhandled` and leave `complete` false, because a caller
told "nothing propagates" cannot otherwise distinguish *analysed and clear* from *skipped* —
the same defect as an evaluation that errored on every detector reporting a clean book. A
propagation engine that guesses at a change it cannot read rewrites conforming prose, and
§1a's whole position is that damaged prose is the expensive error.

**Node space and record space are never mixed.** Manuscript order is `position_key`
(`"010".."060"`, string-comparable within one sibling set by construction); story order is
`StoryPosition.order_key` (`"s1".."s6"`), and **nothing anywhere defines a mapping between
them** — `domain/extraction.attested_position` reads one out of the book's own evidence spans
and abstains where the book is ambiguous, which it is for two of the mystery fixture's six
scenes. So node rules compare `position_key` against the *edited nodes*, record rules compare
`order_key` against other records, and the one place they must meet goes through
`attested_position`. Where it abstains the record filter widens rather than emptying, and the
widening is written on the target's reason instead of being left for a reader to infer.

**What this is not.** Four cases and 37 expectations, in-sample, against this project's own
`MIN_HOLDOUT = 50` — so every number from here is a dev-set number and `ImpactScore.caveat`
says so at every call site. `tests/test_propagation.py` exists because a rule tested only
against the material it was written from is a rule fitted to it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

import litharness_contracts as lc

from litharness.domain import state as state_mod
from litharness.domain.extraction import attested_position
from litharness.domain.revision import Revision

#: Rule ids, carried on every target. Versioned like the gates in `domain/policy.py`, so a
#: recorded analysis says which rule reached a node and a later change to that rule is
#: distinguishable from the node having stopped being reached.
ENTITY_RENAMED = "propagation.entity_renamed.v0"
FACT_CHANGED = "propagation.fact_changed.v0"
EVENT_MOVED = "propagation.event_moved.v0"

#: Change kinds a rule below understands. Everything else in `ExtractedChangeKind` abstains.
HANDLED = frozenset(
    {
        lc.ExtractedChangeKind.SURFACE_ONLY,
        lc.ExtractedChangeKind.ENTITY_RENAMED,
        lc.ExtractedChangeKind.FACT_CHANGED,
        lc.ExtractedChangeKind.EVENT_MOVED,
    }
)


@dataclass(frozen=True, slots=True)
class ProseNode:
    """One addressable piece of prose, with its place in reading order."""

    logical_id: str
    position_key: str
    content: str


@dataclass(frozen=True, slots=True)
class Book:
    """What a propagation rule may read.

    Deliberately narrow. A rule that could reach the store could reach anything, and the
    reason these rules are checkable at all is that their whole input is prose in reading
    order plus the records that state facts about it.
    """

    nodes: tuple[ProseNode, ...] = ()
    records: tuple[lc.StateRecord, ...] = ()

    def node(self, logical_id: str) -> ProseNode | None:
        return next((node for node in self.nodes if node.logical_id == logical_id), None)


def book_from(
    revision: Revision, records: Iterable[lc.StateRecord] = ()
) -> Book:
    """The `Book` view of a stored revision. Text nodes only — a node with no content is a
    structural container, and searching it for a name would find nothing while making the
    position filters count places the prose does not occupy."""
    return Book(
        nodes=tuple(
            ProseNode(node.logical_id, node.position_key, node.content)
            for node in revision.nodes
            if node.content
        ),
        records=tuple(records),
    )


@dataclass(frozen=True, slots=True)
class PropagationTarget:
    """One node this change reaches, with the rule that reached it and why.

    The reason is not decoration: the output is read by an operator deciding whether to spend
    model calls re-checking their book, and a bare list of ids asks them to take it on trust.
    """

    logical_id: str
    rule: str
    reason: str


@dataclass(frozen=True, slots=True)
class Propagation:
    targets: tuple[PropagationTarget, ...] = ()
    #: Change kinds no rule understands, in the order they appeared. Not an error — an
    #: abstention, and the difference between "nothing propagates" and "nobody looked".
    unhandled: tuple[str, ...] = ()

    @property
    def logical_ids(self) -> set[str]:
        return {target.logical_id for target in self.targets}

    @property
    def complete(self) -> bool:
        """Every extracted change was read by a rule. False means the answer is partial, and
        a caller acting on it is acting on less than the change set said."""
        return not self.unhandled

    def by_rule(self, rule: str) -> tuple[PropagationTarget, ...]:
        return tuple(target for target in self.targets if target.rule == rule)


@dataclass
class _Collector:
    """Accumulates targets, deduplicated per (node, rule).

    Per rule rather than per node: two independent reasons to re-check a scene is a stronger
    signal than one, and collapsing them to a single row loses the one an operator would have
    acted on. `logical_ids` deduplicates for callers that only want the set.
    """

    targets: list[PropagationTarget] = field(default_factory=list)
    unhandled: list[str] = field(default_factory=list)
    _seen: set[tuple[str, str]] = field(default_factory=set)

    def reach(self, logical_id: str, rule: str, reason: str) -> None:
        if (logical_id, rule) in self._seen:
            return
        self._seen.add((logical_id, rule))
        self.targets.append(PropagationTarget(logical_id, rule, reason))

    def abstain(self, kind: lc.ExtractedChangeKind) -> None:
        if kind.value not in self.unhandled:
            self.unhandled.append(kind.value)

    def result(self) -> Propagation:
        return Propagation(tuple(self.targets), tuple(self.unhandled))


def _mentions(text: str, term: str) -> bool:
    """Word-boundary, case-insensitive. Boundaries are the whole of the rule's precision:
    without them "Vane" matches "Vanessa" and a short name reaches the entire book."""
    if not term:
        return False
    return re.search(rf"\b{re.escape(term)}\b", text, re.IGNORECASE) is not None


def _without_aliases(text: str, aliases: Iterable[str]) -> str:
    """Blank out preserved aliases before searching for the old name.

    An alias that *contains* the name is the case that needs this — renaming Julian while
    preserving "Julian's man" must not reach a scene that says only the alias. Replaced with a
    space rather than removed so the surrounding words keep their boundaries.
    """
    stripped = text
    for alias in aliases:
        if alias:
            stripped = re.sub(re.escape(alias), " ", stripped, flags=re.IGNORECASE)
    return stripped


def _terms_of(predicate: str) -> tuple[str, ...]:
    """A predicate as the words prose would use. `status_snapshot` is never written in a
    book; "status" and "snapshot" might be."""
    return tuple(part for part in re.split(r"[^A-Za-z0-9]+", predicate) if part)


def _identifier_words(value: object) -> str:
    """A record's value as separate words, because its keys are identifiers and not prose.

    `_` is a word character to `\\b`, so a boundary search for "gold" does not match
    `cost_gold` — and `rec-ev-buy-lantern` states the lantern's price under exactly that key.
    Splitting on non-alphanumerics is right for structured data and wrong for prose, where an
    underscore is rare and a boundary is what stops "Vane" matching "Vanessa". Hence two
    treatments rather than one.
    """
    return re.sub(r"[^A-Za-z0-9]+", " ", str(value))


def _states(record: lc.StateRecord, predicate: str) -> bool:
    """Whether this record asserts the changed predicate — by its own predicate or by naming
    it in the value. `rec-ev-buy-lantern` is `purchased`, and its value is
    `{"item": ..., "cost_gold": 20}`: a gold fact stated under another name."""
    if record.predicate == predicate:
        return True
    haystack = _identifier_words(f"{record.predicate} {record.value}")
    return all(_mentions(haystack, term) for term in _terms_of(predicate))


def _edited(change_set: lc.ChangeSet) -> tuple[str, ...]:
    """The logical ids the change itself touches, in the order the operations name them."""
    seen: list[str] = []
    for operation in change_set.operations:
        if operation.logical_source_id not in seen:
            seen.append(operation.logical_source_id)
    return tuple(seen)


def _preserved_aliases(change_set: lc.ChangeSet) -> tuple[str, ...]:
    aliases: list[str] = []
    for operation in change_set.operations:
        raw = operation.detail.get("preserve_aliases")
        if isinstance(raw, list):
            aliases.extend(str(item) for item in raw)
    return tuple(aliases)


def _edited_positions(book: Book, edited: Sequence[str]) -> tuple[str, ...]:
    """Position keys of the edited nodes that are prose in this book.

    A rename's `logical_source_id` is `entity:julian`, which is not a node at all — so an
    empty result means "this change has no place in the manuscript", and the position-aware
    rules say so rather than treating position zero as the answer.
    """
    return tuple(
        sorted(node.position_key for name in edited if (node := book.node(name)) is not None)
    )


def _change_order_key(book: Book, edited: Sequence[str]) -> str | None:
    """The story position the *records* attest for the edited prose, or None.

    Goes through `attested_position` rather than deriving `s2` from `scene-2`: that mapping
    does not exist, and the mystery fixture is the proof — its scene 2 is cited by records at
    two different positions and its scene 5 by a record at `s1`. None means the book has not
    said, and the caller widens rather than guesses.
    """
    keys = {
        key
        for name in edited
        if (key := attested_position(book.records, name)) is not None
    }
    return min(keys) if len(keys) == 1 else None


# -- the rules -------------------------------------------------------------------------


def _apply_rename(
    change: lc.ExtractedChange,
    aliases: Sequence[str],
    book: Book,
    edited: Sequence[str],
    into: _Collector,
) -> None:
    old = str(change.before) if change.before is not None else ""
    if not old:
        # Nothing to search for. Predicting the whole book is the recall-optimal answer and
        # the one that rewrites it, so this abstains and is reported as unread.
        into.abstain(change.kind)
        return
    for node in book.nodes:
        if node.logical_id in edited:
            continue
        if _mentions(_without_aliases(node.content, aliases), old):
            into.reach(
                node.logical_id,
                ENTITY_RENAMED,
                f"the prose spells {old!r}, which this change renames",
            )
    subject = change.subject or ""
    for record in book.records:
        if record.record_id in edited:
            continue
        stated = _identifier_words(f"{record.value} {record.object_ref or ''}")
        names_it = subject and (record.subject == subject or _mentions(stated, subject))
        if names_it or _mentions(stated, old):
            into.reach(
                record.record_id,
                ENTITY_RENAMED,
                f"the record names {subject or old!r}, whose display name changes",
            )


def _apply_fact_change(
    change: lc.ExtractedChange,
    book: Book,
    edited: Sequence[str],
    into: _Collector,
) -> None:
    subject = change.subject or ""
    predicate = change.predicate or ""
    if not subject or not predicate:
        into.abstain(change.kind)
        return

    # Nodes: forward only, and both terms required. A scene about somebody else's gold is not
    # about Rook's, and a scene before the purchase was true before it and stays true.
    positions = _edited_positions(book, edited)
    floor = positions[0] if positions else None
    terms = _terms_of(predicate)
    for node in book.nodes:
        if node.logical_id in edited:
            continue
        if floor is not None and node.position_key < floor:
            continue
        if _mentions(node.content, subject) and all(
            _mentions(node.content, term) for term in terms
        ):
            into.reach(
                node.logical_id,
                FACT_CHANGED,
                f"states {subject}'s {predicate} at or after the change",
            )

    # Records: same predicate, same subject, from the change's story position onward — and
    # where the book has not said where that is, everything, said out loud.
    since = _change_order_key(book, edited)
    for record in book.records:
        if record.record_id in edited or record.subject != subject:
            continue
        if not _states(record, predicate):
            continue
        key = state_mod.order_key_of(record)
        if since is not None and key is not None and key < since:
            continue
        placed = (
            f"from {since} onward"
            if since is not None
            else "at an unplaced position: the book's own evidence does not say where the "
            "edited prose sits in story time, so the filter widens"
        )
        into.reach(
            record.record_id,
            FACT_CHANGED,
            f"states {subject}'s {predicate} {placed}",
        )


def _apply_event_move(
    change: lc.ExtractedChange,
    book: Book,
    edited: Sequence[str],
    into: _Collector,
) -> None:
    # Nodes: strictly between the two edited nodes. Written as a window rather than "after the
    # origin" because a move can run backwards, and the window is the same either way.
    positions = _edited_positions(book, edited)
    if len(positions) >= 2:
        low, high = positions[0], positions[-1]
        for node in book.nodes:
            if node.logical_id in edited:
                continue
            if low < node.position_key < high:
                into.reach(
                    node.logical_id,
                    EVENT_MOVED,
                    "sits between where the event was and where it goes",
                )

    # Records: the moved record, and what was acquired at the same position by the same
    # subject. `subject` on an `event_moved` is the moved *record's* id, not a story subject.
    moved = next(
        (record for record in book.records if record.record_id == change.subject), None
    )
    if moved is None:
        return
    origin = state_mod.order_key_of(moved)
    into.reach(
        moved.record_id,
        EVENT_MOVED,
        f"is the moved event: {change.before} to {change.after}",
    )
    if origin is None:
        return
    for record in book.records:
        if record.record_id == moved.record_id or record.subject != moved.subject:
            continue
        if state_mod.order_key_of(record) == origin:
            into.reach(
                record.record_id,
                EVENT_MOVED,
                f"is {record.subject}'s at {origin}, where the moved event was",
            )


def changes_between(
    known: Sequence[lc.StateRecord], extracted: Sequence[lc.StateRecord]
) -> tuple[lc.ExtractedChange, ...]:
    """The semantic changes between the canon a node used to state and the canon it now does.

    **The producer this project can honestly build in-repo.** §13 puts a general change
    extractor in a sibling, and nothing here reads prose for renames or moved events. But a
    repair that rewrites a span *already* runs `extract_state` over the result, and comparing
    those records against the ones being retracted is a deterministic reading of what the
    repair changed — mints nothing, invents nothing, and is exactly §27's rule applied one
    layer up.

    **Matched on `(subject, predicate, order_key)`, and the order key is the whole of the
    correctness.** A running balance differs at every position by design, so comparing
    `rook/gold` at s3 against `rook/gold` at s2 would report the ledger advancing as a
    contradiction. Only a disagreement at *one* position is a change.

    **A mapping value is diffed to the field, because the field is the predicate prose uses.**
    A status snapshot is one record under `status_snapshot`, and no book contains that word —
    while `gold` is both the changed field and the token the prose carries. Diffing to the
    field is what makes a produced change the same shape as the hand-authored gold, and what
    lets the node rule fire at all rather than reaching records only.

    A newly stated fact with no predecessor is **not** a change and is skipped: it invalidates
    no earlier prose, and a candidate contradicting standing canon is refused by the integrity
    gate before it can commit.
    """
    index: dict[tuple[str, str, str], lc.StateRecord] = {}
    for record in known:
        key = state_mod.order_key_of(record)
        if state_mod.is_canon(record) and key is not None:
            index[(record.subject, record.predicate, key)] = record

    changes: list[lc.ExtractedChange] = []
    for record in extracted:
        key = state_mod.order_key_of(record)
        if key is None:
            continue
        previous = index.get((record.subject, record.predicate, key))
        if previous is None or previous.value == record.value:
            continue
        changes.extend(_field_changes(previous, record))
    return tuple(changes)


def _field_changes(
    before: lc.StateRecord, after: lc.StateRecord
) -> Iterable[lc.ExtractedChange]:
    if isinstance(before.value, Mapping) and isinstance(after.value, Mapping):
        return [
            lc.ExtractedChange(
                kind=lc.ExtractedChangeKind.FACT_CHANGED,
                subject=before.subject,
                predicate=str(name),
                before=before.value.get(name),
                after=after.value.get(name),
                confidence=1.0,
            )
            for name in sorted(set(before.value) | set(after.value))
            if before.value.get(name) != after.value.get(name)
        ]
    return [
        lc.ExtractedChange(
            kind=lc.ExtractedChangeKind.FACT_CHANGED,
            subject=before.subject,
            predicate=before.predicate,
            before=before.value,
            after=after.value,
            confidence=1.0,
        )
    ]


def propagate(change_set: lc.ChangeSet, book: Book) -> Propagation:
    """What this change set reaches, beyond what it edits.

    The `ChangeSet` form of `propagate_changes`, for the callers that hold a shared-contract
    artifact: `litharness propagate` and the gold suites.
    """
    return propagate_changes(
        change_set.extracted_changes,
        edited=_edited(change_set),
        book=book,
        aliases=_preserved_aliases(change_set),
    )


def propagate_changes(
    changes: Sequence[lc.ExtractedChange],
    *,
    edited: Sequence[str],
    book: Book,
    aliases: Sequence[str] = (),
) -> Propagation:
    """What these changes reach, beyond the nodes they edit.

    The edited nodes are never targets: an engine gets no credit for the node it was told to
    change, and enqueueing work to re-check prose that was just written is how a repair loop
    cycles.

    No changes at all is **incomplete, not clear** — nobody produced a semantic reading, which
    is a statement about the producer and not about the book.
    """
    into = _Collector()
    if not changes:
        into.abstain(lc.ExtractedChangeKind.UNKNOWN)
        return into.result()

    for change in changes:
        if change.kind is lc.ExtractedChangeKind.SURFACE_ONLY:
            # Understood, and reaches nothing. Deliberately not a veto over the rest of the
            # set: `surface_only` says *this* change carries no meaning, and treating it as
            # set-wide would let one reformatted sentence hide a rename beside it.
            continue
        if change.kind is lc.ExtractedChangeKind.ENTITY_RENAMED:
            _apply_rename(change, aliases, book, edited, into)
        elif change.kind is lc.ExtractedChangeKind.FACT_CHANGED:
            _apply_fact_change(change, book, edited, into)
        elif change.kind is lc.ExtractedChangeKind.EVENT_MOVED:
            _apply_event_move(change, book, edited, into)
        else:
            into.abstain(change.kind)
    return into.result()


__all__ = [
    "ENTITY_RENAMED",
    "EVENT_MOVED",
    "FACT_CHANGED",
    "HANDLED",
    "Book",
    "Propagation",
    "PropagationTarget",
    "ProseNode",
    "book_from",
    "changes_between",
    "propagate",
    "propagate_changes",
]
