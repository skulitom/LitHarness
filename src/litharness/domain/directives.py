"""The direction inbox: durable capture of what the director says (§4.3).

**Only the capture half is built here, and that is the point of the module.** §4.3 wants
directives converted into versioned locked plan constraints via the Narrative Planner,
which does not exist (§9). Capture needs nothing that is missing; interpretation needs a
subsystem that has not been written. Building both would mean inventing an interpreter,
and building neither would mean losing direction the director gives today because the
thing that reads it ships later.

So a directive lands in `RECEIVED` and stays there. `interpret()` exists and is the only
transition out, so when the planner arrives it has one seam to attach to rather than a
schema to negotiate. A directive that is never interpreted is visible as a growing count
of `RECEIVED` rows, which is the honest failure mode: work queued and unread, not work
silently dropped.

Two things worth stating because they are easy to get wrong later.

**The director's words are immutable and stored separately from what the system decided
they meant.** `body` is never rewritten; `interpretation` records the reading. Collapsing
them would make a misinterpretation invisible after the fact, and "the system quietly
understood 'less combat' as 'no combat'" is precisely the failure this separation exists
to catch.

**Precedence is explicit, not arrival order.** A veto issued on Monday must outrank a tone
note issued on Tuesday, and a queue that resolved conflicts by recency would silently
reverse that. `VETO` therefore defaults to a higher precedence than everything else, and
conflict resolution is left to the planner with the ordering already recorded.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field, replace
from hashlib import sha256

import litharness_contracts as lc

from litharness.domain.events import payload_digest


class DirectiveKind(enum.StrEnum):
    PREMISE = "premise"
    CONSTRAINT = "constraint"
    ARC_NOTE = "arc_note"
    TONE_NOTE = "tone_note"
    CHAPTER_NOTE = "chapter_note"
    VETO = "veto"
    CONTROL = "control"

    def to_contract(self) -> lc.DirectiveKind:
        return lc.DirectiveKind(self.value)

    @property
    def default_precedence(self) -> int:
        """A refusal outranks a suggestion regardless of when each arrived."""
        if self is DirectiveKind.VETO:
            return 100
        if self is DirectiveKind.CONTROL:
            return 90
        if self is DirectiveKind.CONSTRAINT:
            return 50
        return 10


class DirectiveStatus(enum.StrEnum):
    RECEIVED = "received"
    INTERPRETED = "interpreted"
    APPLIED = "applied"
    CONFLICTED = "conflicted"
    SUPERSEDED = "superseded"

    def to_contract(self) -> lc.DirectiveStatus:
        return lc.DirectiveStatus(self.value)


#: The only transitions the inbox permits. `RECEIVED -> INTERPRETED` is the seam the
#: Narrative Planner will attach to; everything downstream of it is planner business.
TRANSITIONS: dict[DirectiveStatus, frozenset[DirectiveStatus]] = {
    DirectiveStatus.RECEIVED: frozenset(
        {DirectiveStatus.INTERPRETED, DirectiveStatus.CONFLICTED, DirectiveStatus.SUPERSEDED}
    ),
    DirectiveStatus.INTERPRETED: frozenset(
        {DirectiveStatus.APPLIED, DirectiveStatus.CONFLICTED, DirectiveStatus.SUPERSEDED}
    ),
    DirectiveStatus.APPLIED: frozenset({DirectiveStatus.SUPERSEDED}),
    DirectiveStatus.CONFLICTED: frozenset(
        {DirectiveStatus.INTERPRETED, DirectiveStatus.SUPERSEDED}
    ),
    DirectiveStatus.SUPERSEDED: frozenset(),
}


class IllegalTransition(Exception):
    pass


@dataclass(frozen=True, slots=True)
class Directive:
    directive_id: str
    kind: DirectiveKind
    body: str
    status: DirectiveStatus = DirectiveStatus.RECEIVED
    book_id: str | None = None
    branch_id: str | None = None
    target_logical_ids: tuple[str, ...] = ()
    #: What the system decided `body` means. Never overwrites `body`.
    interpretation: str | None = None
    produced_constraint_ids: tuple[str, ...] = ()
    received_at: str | None = None
    interpreted_at: str | None = None
    precedence: int = -1
    superseded_by: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.body.strip():
            raise ValueError(f"directive {self.directive_id} has an empty body")
        if self.precedence < 0:
            object.__setattr__(self, "precedence", self.kind.default_precedence)

    def transition_to(self, status: DirectiveStatus) -> Directive:
        if status not in TRANSITIONS[self.status]:
            raise IllegalTransition(f"{self.status.value} -> {status.value} is not allowed")
        return replace(self, status=status)

    def interpret(
        self, reading: str, *, at: str, constraint_ids: tuple[str, ...] = ()
    ) -> Directive:
        """Record what the system decided this directive means.

        The seam the Narrative Planner attaches to. Nothing calls it yet, and that is
        stated rather than hidden: §9 does not exist, so every directive currently stops at
        RECEIVED and is visible as such.
        """
        return replace(
            self.transition_to(DirectiveStatus.INTERPRETED),
            interpretation=reading,
            interpreted_at=at,
            produced_constraint_ids=constraint_ids,
        )

    def to_contract(self, meta: lc.ArtifactMeta) -> lc.Directive:
        return lc.Directive(
            meta=meta,
            directive_id=self.directive_id,
            kind=self.kind.to_contract(),
            body=self.body,
            status=self.status.to_contract(),
            book_id=self.book_id,
            branch_id=self.branch_id,
            interpretation=self.interpretation,
            produced_constraint_ids=list(self.produced_constraint_ids),
            received_at=self.received_at,
            interpreted_at=self.interpreted_at,
            precedence=self.precedence,
            superseded_by=self.superseded_by,
        )


def directive_id_for(kind: DirectiveKind, body: str, received_at: str) -> str:
    """Content-derived, so submitting the same directive twice at the same instant
    collapses instead of queueing two readings of one instruction.

    `received_at` is deliberately part of the material: a director who says "more dungeon
    crawling" again next week means it again, and that is a second directive rather than a
    duplicate of the first.
    """
    material = payload_digest({"kind": kind.value, "body": body, "received_at": received_at})
    return f"dir-{sha256(material.encode()).hexdigest()[:24]}"


__all__ = [
    "TRANSITIONS",
    "Directive",
    "DirectiveKind",
    "DirectiveStatus",
    "IllegalTransition",
    "directive_id_for",
]
