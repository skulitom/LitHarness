"""The direction inbox: durable capture of what the director says (§4.3).

Capture and interpretation remain deliberately separate. §4.3 wants directives converted
into versioned plan changes by the Narrative Planner. Explicit constraints and vetoes use a
narrow deterministic lane: their words are preserved in a locked constraint (with an
explicit veto label where needed). Premise, arc, tone, and chapter notes use a bounded
model-backed proposal whose edits still pass the same immutable-plan validation.

So a directive lands in `RECEIVED` and stays there until an accepted plan proposal calls
`interpret()`. A directive not yet included in a proposal remains visible as queued and
unread, rather than being silently treated as handled.

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


#: Kinds whose safe plan form is mechanical and preserves the original words. All others
#: need the Narrative Planner rather than a deterministic paraphrase pretending to understand.
VERBATIM_KINDS = frozenset({DirectiveKind.CONSTRAINT, DirectiveKind.VETO})

#: Direction that needs a model to turn its meaning into concrete plan edits. Controls are
#: intentionally absent: pause/resume/kill are operator state, not narrative plan changes.
INTERPRETIVE_KINDS = frozenset(
    {
        DirectiveKind.PREMISE,
        DirectiveKind.ARC_NOTE,
        DirectiveKind.TONE_NOTE,
        DirectiveKind.CHAPTER_NOTE,
    }
)


#: The only transitions the inbox permits. `RECEIVED -> INTERPRETED` is the seam the
#: Narrative Planner uses; everything downstream of it is planner business.
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
    #: Who wrote this. **Recorded because the property it carries was enforced by nothing.**
    #: A directive's words become a locked plan constraint sitting in every subsequent context
    #: packet with the director's authority; until this column existed, "the director's word"
    #: meant "only a human can write one", which stops being true the moment a machine
    #: Director runs (`plan/director-role.md` §1). `None` is "unrecorded" for rows written
    #: before the column and is never read as "human".
    author: str | None = None
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

        The seam an accepted Narrative Planner proposal uses in the same transaction as
        its new plan revision.
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


def directive_id_for(
    kind: DirectiveKind, body: str, received_at: str, author: str | None = None
) -> str:
    """Content-derived, so submitting the same directive twice at the same instant
    collapses instead of queueing two readings of one instruction.

    `received_at` is deliberately part of the material: a director who says "more dungeon
    crawling" again next week means it again, and that is a second directive rather than a
    duplicate of the first.

    **`author` is in the material too, and that is what stops a machine row being silently
    reattributed.** The same words from a person and from a Director are two directives with two
    ids, so an instruction cannot be quietly relabelled and a machine's cannot collapse onto a
    human's. It is keyed in only when present, so every id minted before the column existed
    addresses exactly what it always did — a migration that changed existing ids would break
    every `produced_constraint_ids` reference pointing at one.
    """
    material = payload_digest(
        {"kind": kind.value, "body": body, "received_at": received_at}
        if author is None
        else {
            "kind": kind.value,
            "body": body,
            "received_at": received_at,
            "author": author,
        }
    )
    return f"dir-{sha256(material.encode()).hexdigest()[:24]}"


__all__ = [
    "INTERPRETIVE_KINDS",
    "TRANSITIONS",
    "VERBATIM_KINDS",
    "Directive",
    "DirectiveKind",
    "DirectiveStatus",
    "IllegalTransition",
    "directive_id_for",
]
