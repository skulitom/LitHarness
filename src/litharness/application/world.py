"""The world, as an agent asks it questions rather than as a blob handed over.

**Why this exists, in the operator's words (2026-08-24):** *"in what world would a one-shot
structured call be a good idea for writing a book... The world would obviously evolve and grow
with every chapter"*, and *"all our agents should interact with each other through cli tools, as
it is native interface for them"*.

§132 named the gap and did not close it: raising the writer's packet from 6,000 tokens to 200,000
stops the eviction and does not make a writer that *understands* its world, because *"a
professional does not hold the two hundred pages, they consult them"*. This module is the
consulting surface. Every view below is a thin wrapper over a function `domain/worlds.py`
already had — `rules`, `criteria`, `rank_order`, `ladder_of`, `standing_of`, `capabilities_of`,
`questions`, `reveal_scenes`, `validate` — turned into something an agent can call and parse.
**No new world logic is written here**; if a view needs a rule the domain does not already
state, the rule belongs in `worlds.py` and not in a presentation layer.

**Why the writes are safe, and the rail is not this module's.** `worlds.world_record` mints at
`PROPOSED` and its own docstring says why: Architect output is a proposal and reaches canon only
through a recorded policy decision. So an agent holding these tools writes proposals, and canon
still costs a decision row — which is the substance of §5's "no subsystem mutates canon
directly", preserved *through* the tool surface rather than by denying one.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import litharness_contracts as lc

from litharness.domain import state as state_mod
from litharness.domain import worlds

#: Every view is addressable by name, so the CLI's subcommand table and this module cannot
#: drift apart, and an agent can be told the list of views without a second source for it.
VIEWS: tuple[str, ...] = (
    "rules",
    "ladders",
    "abilities",
    "cast",
    "threads",
    "check",
)


def _canon_only(records: Sequence[lc.StateRecord]) -> tuple[lc.StateRecord, ...]:
    return tuple(record for record in records if state_mod.is_canon(record))


def declarations(
    records: Sequence[lc.StateRecord], *, subject: str | None = None
) -> list[dict[str, Any]]:
    """Every declaration, in story order, with provenance on each line.

    Proposals are included and labelled rather than filtered. An Architect that cannot see what
    it proposed last chapter would propose it again, and the authority field is what tells the
    two apart — which is the same reason `cmd_state` prints provenance.
    """
    rows: list[dict[str, Any]] = []
    for record in state_mod.in_story_order(records):
        if subject is not None and record.subject != subject:
            continue
        position = record.story_position
        rows.append(
            {
                "record_id": record.record_id,
                "subject": record.subject,
                "predicate": record.predicate,
                "value": record.value,
                "object": record.object_ref,
                "order_key": position.order_key if position is not None else None,
                "authority": record.authority.value,
                "canon": state_mod.is_canon(record),
                "says": state_mod.describe(record),
            }
        )
    return rows


def rules(records: Sequence[lc.StateRecord]) -> list[dict[str, Any]]:
    """The world's declared rules, each with the domains of life its consequences reach."""
    by_rule = worlds.consequence_domains(records)
    return [
        {"rule": rule, "consequence_domains": list(by_rule.get(rule, ()))}
        for rule in worlds.rules(records)
    ]


def ladders(records: Sequence[lc.StateRecord]) -> list[dict[str, Any]]:
    """Every ordinal criterion, its rungs lowest-first, and who is standing on which.

    The rung's position from the bottom is the number this world counts (§113), so it is
    returned rather than left for a caller to derive and get off by one.
    """
    out: list[dict[str, Any]] = []
    people = sorted(worlds.entities_with_role(records, "cast"))
    for criterion, label in sorted(worlds.criteria(records).items()):
        chain = worlds.ladder_of(records, criterion)
        if not chain:
            continue
        grants = dict(worlds.rank_order(records, criterion=criterion))
        standing: list[dict[str, Any]] = []
        for subject in people:
            where = worlds.standing_of(records, subject)
            rung = where.get(criterion)
            if rung is None:
                continue
            standing.append(
                {
                    "subject": subject,
                    "rung": rung,
                    "position": worlds.rung_index(records, criterion, rung),
                }
            )
        out.append(
            {
                "criterion": criterion,
                "label": label,
                "rungs": [
                    {"rung": rung, "position": index + 1, "grants": grants.get(rung, "")}
                    for index, rung in enumerate(chain)
                ],
                "standing": standing,
            }
        )
    return out


def abilities(
    records: Sequence[lc.StateRecord], *, holder: str | None = None
) -> dict[str, Any]:
    """What this world says a person can do, and who holds what.

    `declared` minus what anybody holds is the headroom a book has left to give away, which is
    the quantity the ability-inventory work (§114) exists to make visible — measured at zero in
    three of ten forged worlds, which is a protagonist who starts holding everything.
    """
    declared = list(worlds.capabilities(records))
    if holder is not None:
        return {
            "declared": declared,
            "holder": holder,
            "held": list(worlds.capabilities_of(records, holder)),
        }
    held: dict[str, list[str]] = {}
    for subject in sorted(worlds.entities_with_role(records, "cast")):
        owned = list(worlds.capabilities_of(records, subject))
        if owned:
            held[subject] = owned
    spoken_for = {name for owned in held.values() for name in owned}
    return {
        "declared": declared,
        "held": held,
        "unclaimed": [name for name in declared if name not in spoken_for],
    }


def cast(records: Sequence[lc.StateRecord]) -> dict[str, Any]:
    """Who is in this world, by the role the world gave them, and who the protagonist is."""
    protagonist = worlds.protagonist_brief(records)
    return {
        "protagonist": (
            protagonist.to_jsonable() if protagonist is not None else None
        ),
        "roles": {
            subject: list(roles)
            for subject, roles in sorted(worlds.entity_roles(records).items())
        },
    }


def threads(records: Sequence[lc.StateRecord], *, at: str | None = None) -> dict[str, Any]:
    """Open questions, where each is answered, and what the reader has not been told yet.

    `at` is a story position: what is still open *as of* that point, which is the question a
    writer drafting scene seven has and a writer drafting scene one does not.
    """
    reveals = worlds.reveal_scenes(records)
    return {
        "questions": [
            {"question": question, "asks": text, "answered_at_scene": reveals.get(question)}
            for question, text in sorted(worlds.questions(records).items())
        ],
        "undisclosed": [
            {"subject": record.subject, "says": state_mod.describe(record)}
            for record in worlds.undisclosed_claims(records, at=at)
        ],
        "open": [
            {"subject": record.subject, "says": state_mod.describe(record)}
            for record in state_mod.open_threads(records)
        ],
    }


def check(records: Sequence[lc.StateRecord]) -> dict[str, Any]:
    """What is wrong with this world by arithmetic, never by taste.

    `worlds.validate` is the whole of it, plus the manifestation count, and its own docstring
    states the boundary this inherits: every check is arithmetic or membership over the records
    and none is a judgment about whether the world is any good.
    """
    coverage = worlds.manifestation_coverage(records)
    complaints = list(worlds.validate(records))
    return {
        "complaints": complaints,
        "ok": not complaints,
        "manifested": len(coverage.covered),
        "needing_manifestation": len(coverage.features),
        "unmanifested": list(coverage.missing),
    }


def summary(records: Sequence[lc.StateRecord]) -> dict[str, Any]:
    """One call an agent can open with: how big this world is and where the holes are."""
    canon = _canon_only(records)
    return {
        "records": len(records),
        "canon": len(canon),
        "proposed": len(records) - len(canon),
        "rules": len(worlds.rules(records)),
        "criteria": len(worlds.criteria(records)),
        "capabilities": len(worlds.capabilities(records)),
        "cast": len(worlds.entities_with_role(records, "cast")),
        "open_questions": len(worlds.questions(records)),
        "check": check(records),
    }


__all__ = [
    "VIEWS",
    "abilities",
    "cast",
    "check",
    "declarations",
    "ladders",
    "rules",
    "summary",
    "threads",
]
