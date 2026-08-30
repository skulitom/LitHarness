"""Everything canon holds about one person, in one addressable object.

The operator's directive, 2026-08-24: *"Writers need to understand the world they build.
Dungeon crawler carl author says he keeps 200page excel sheet for some individual characters
in his world … we can't expect our writers to write in the dark."*

The facts were already there. World records carry a character's role, what they are, what
they want, how they sound, what they look like, what they can do, where they stand, what
they are the exception to, what they owe and who owes them — as `(subject, predicate, value)`
rows. Nothing gathered them. `worlds.protagonist_brief` does it for exactly one person and
stops.

**Inbound ties are half the sheet.** What a character *is* in a story is largely what other
people do about them: who employs, shelters, refuses, rivals or is paired with them. Those rows
name the character in `object_ref`, so a subject-only read misses them entirely.

Aggregation only. Nothing here judges a character, orders them, or decides who matters.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import litharness_contracts as lc

from litharness.domain import worlds as worlds_mod

#: Read off the subject rather than listed as ties. Everything else a character's rows say
#: about another declared id is a relationship.
_SELF = frozenset(
    {
        worlds_mod.ENTITY_ROLE_PREDICATE,
        worlds_mod.EDGE_PREDICATE,
        worlds_mod.PRICE_PREDICATE,
        worlds_mod.EXCEPTION_PREDICATE,
        worlds_mod.STANDS_AT_PREDICATE,
        worlds_mod.MANIFESTS_PREDICATE,
        worlds_mod.TYPE_PREDICATE,
        "is_a",
        "wants",
        "voice_tag",
        "can_do",
    }
)


@dataclass(frozen=True, slots=True)
class CharacterCause:
    """One explicitly reified action and its declared causal/effect roles."""

    change_id: str
    role: str
    motives: tuple[str, ...]
    effects: tuple[str, ...]
    evidence_complete: bool


@dataclass(frozen=True, slots=True)
class Character:
    """One person, as canon declares them. Every field is empty rather than guessed."""

    subject: str
    roles: tuple[str, ...]
    is_a: str
    wants: str
    voice: str
    manifests_as: str
    edge: str
    price: str
    exception: str
    #: criterion id -> rung id, and the rung's 1-based place on its chain when it has one.
    standing: tuple[tuple[str, str, int | None], ...]
    capabilities: tuple[str, ...]
    #: (predicate, other id) — what this character does about other people.
    ties: tuple[tuple[str, str], ...]
    #: (other id, predicate) — what other people do about this character.
    named_by: tuple[tuple[str, str], ...]
    #: Anything else stated about them, as (predicate, value).
    also: tuple[tuple[str, str], ...]
    #: Only explicit reified changes; free-text wants are never promoted into causes.
    causes: tuple[CharacterCause, ...] = ()

    @property
    def is_protagonist(self) -> bool:
        return "protagonist" in self.roles

    def to_jsonable(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"id": self.subject, "roles": list(self.roles)}
        for name in ("is_a", "wants", "voice", "manifests_as", "edge", "price", "exception"):
            value = getattr(self, name)
            if value:
                payload[name] = value
        if self.standing:
            payload["standing"] = [
                {"criterion": c, "rung": r, **({"number": n} if n is not None else {})}
                for c, r, n in self.standing
            ]
        if self.capabilities:
            payload["can_do"] = list(self.capabilities)
        if self.ties:
            payload["ties"] = [{"how": p, "who": o} for p, o in self.ties]
        if self.named_by:
            payload["named_by"] = [{"who": o, "how": p} for o, p in self.named_by]
        if self.also:
            payload["also"] = dict(self.also)
        if self.causes:
            payload["causes"] = [
                {
                    "change_id": cause.change_id,
                    "role": cause.role,
                    "motives": list(cause.motives),
                    "effects": list(cause.effects),
                    "evidence_complete": cause.evidence_complete,
                }
                for cause in self.causes
            ]
        return payload

    def render(self) -> str:
        """The sheet as the writer reads it. One character, plain lines, no JSON."""
        head = self.subject + (" (the protagonist)" if self.is_protagonist else "")
        lines = [head]
        for label, value in (
            ("is", self.is_a),
            ("wants", self.wants),
            ("sounds", self.voice),
            # **The same field and the same correction as `worlds._record_sentence`** (§182).
            # Every other label here names something the person *is* — is, wants, sounds, can
            # do, costs — and this one named the writer's output. `looks like` puts it back in
            # the series it belongs to; the value is unchanged and no line is added or dropped.
            ("looks like", self.manifests_as),
            ("can do what nobody else can", self.edge),
            ("and it costs", self.price),
        ):
            if value:
                lines.append(f"  {label}: {value}")
        if self.exception:
            lines.append(f"  the rule that does not hold for them: {self.exception}")
        for criterion, rung, number in self.standing:
            place = f" (rung {number})" if number is not None else ""
            lines.append(f"  stands at: {rung} on {criterion}{place}")
        if self.capabilities:
            lines.append(f"  can do: {', '.join(self.capabilities)}")
        for predicate, other in self.ties:
            lines.append(f"  {predicate.replace('_', ' ')}: {other}")
        for other, predicate in self.named_by:
            lines.append(f"  {other} {predicate.replace('_', ' ')} them")
        for predicate, value in self.also:
            lines.append(f"  {predicate.replace('_', ' ')}: {value}")
        for cause in self.causes:
            motive = ", ".join(cause.motives) or "no explicit cause"
            effect = ", ".join(cause.effects) or "no explicit effect"
            evidenced = "span-backed" if cause.evidence_complete else "unlocated"
            lines.append(
                f"  {cause.role.replace('_', ' ')} {cause.change_id}: "
                f"because {motive}; resulting in {effect} ({evidenced})"
            )
        return "\n".join(lines)


def sheet(records: Sequence[lc.StateRecord], subject: str) -> Character:
    """Everything canon says about `subject`, gathered. Empty fields for a stranger."""
    canon = [r for r in records if r.authority is lc.StateAuthority.ACCEPTED_CANON]
    values: dict[str, str] = {}
    roles: list[str] = []
    ties: list[tuple[str, str]] = []
    named_by: list[tuple[str, str]] = []
    also: list[tuple[str, str]] = []
    exception = ""

    for record in canon:
        if record.object_ref == subject and record.subject != subject:
            named_by.append((record.subject, record.predicate))
        if record.subject != subject:
            continue
        if record.predicate == worlds_mod.ENTITY_ROLE_PREDICATE:
            roles.append(str(record.value or "").strip())
        elif record.predicate == worlds_mod.EXCEPTION_PREDICATE and record.object_ref:
            exception = record.object_ref
        elif record.predicate in ("can_do", worlds_mod.STANDS_AT_PREDICATE):
            continue  # read through the world vocabulary below
        elif record.object_ref:
            ties.append((record.predicate, record.object_ref))
        elif record.predicate in _SELF:
            values[record.predicate] = str(record.value or "").strip()
        else:
            text = str(record.value or "").strip()
            if text:
                also.append((record.predicate, text))

    standing: list[tuple[str, str, int | None]] = []
    for criterion, rung in sorted(worlds_mod.standing_of(canon, subject).items()):
        standing.append((criterion, rung, worlds_mod.rung_index(canon, criterion, rung)))

    causes: list[CharacterCause] = []
    for actor in canon:
        if actor.predicate not in {"actor", "performed_by"} or actor.object_ref != subject:
            continue
        members = [record for record in canon if record.subject == actor.subject]
        motives = tuple(
            dict.fromkeys(
                record.object_ref or str(record.value or "").strip()
                for record in members
                if record.predicate == "caused_by"
                and (record.object_ref or str(record.value or "").strip())
            )
        )
        effects = tuple(
            dict.fromkeys(
                record.object_ref or str(record.value or "").strip()
                for record in members
                if record.predicate == "effect"
                and (record.object_ref or str(record.value or "").strip())
            )
        )
        causal_rows = [
            record
            for record in members
            if record.predicate in {"caused_by", "effect"}
        ]
        causes.append(
            CharacterCause(
                change_id=actor.subject,
                role=actor.predicate,
                motives=motives,
                effects=effects,
                evidence_complete=bool(motives and effects)
                and bool(actor.evidence)
                and all(record.evidence for record in causal_rows),
            )
        )

    return Character(
        subject=subject,
        roles=tuple(dict.fromkeys(roles)),
        is_a=values.get("is_a", ""),
        wants=values.get("wants", ""),
        voice=values.get("voice_tag", ""),
        manifests_as=values.get(worlds_mod.MANIFESTS_PREDICATE, ""),
        edge=values.get(worlds_mod.EDGE_PREDICATE, ""),
        price=values.get(worlds_mod.PRICE_PREDICATE, ""),
        exception=exception,
        standing=tuple(standing),
        capabilities=worlds_mod.capabilities_of(canon, subject),
        ties=tuple(sorted(set(ties))),
        named_by=tuple(sorted(set(named_by))),
        also=tuple(sorted(set(also))),
        causes=tuple(sorted(causes, key=lambda cause: (cause.change_id, cause.role))),
    )


def cast(records: Sequence[lc.StateRecord]) -> tuple[Character, ...]:
    """Every declared person, protagonist first, then by id.

    Roles that are people: cast, protagonist. A place or an institution has a role too and is
    not a character, so it is not here — `worlds.entity_roles` is where those live.
    """
    canon = [r for r in records if r.authority is lc.StateAuthority.ACCEPTED_CANON]
    people: set[str] = set()
    for role in ("cast", "protagonist"):
        people.update(worlds_mod.entities_with_role(canon, role))
    sheets = [sheet(canon, subject) for subject in sorted(people)]
    return tuple(sorted(sheets, key=lambda c: (not c.is_protagonist, c.subject)))


def render(characters: Sequence[Character]) -> str:
    """The cast as the writer reads it."""
    return "\n\n".join(character.render() for character in characters)


def rows(characters: Sequence[Character]) -> list[dict[str, str]]:
    """One flat row per character, for a spreadsheet.

    The operator's own framing for what a writer needs to consult; `litharness characters
    --csv` writes these. Lists are joined rather than nested because a cell holds a string.
    """
    return [
        {
            "id": c.subject,
            "roles": " ".join(c.roles),
            "is_a": c.is_a,
            "wants": c.wants,
            "voice": c.voice,
            "manifests_as": c.manifests_as,
            "edge": c.edge,
            "price": c.price,
            "exception": c.exception,
            "standing": "; ".join(
                f"{rung} on {criterion}" + (f" (rung {n})" if n is not None else "")
                for criterion, rung, n in c.standing
            ),
            "can_do": " ".join(c.capabilities),
            "ties": "; ".join(f"{p} {o}" for p, o in c.ties),
            "named_by": "; ".join(f"{o} {p}" for o, p in c.named_by),
            "causes": "; ".join(
                f"{cause.role} {cause.change_id}: {','.join(cause.motives)} -> "
                f"{','.join(cause.effects)}"
                for cause in c.causes
            ),
        }
        for c in characters
    ]


__all__ = ["Character", "CharacterCause", "cast", "render", "rows", "sheet"]
