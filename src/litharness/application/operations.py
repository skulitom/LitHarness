"""The one write an agent surface holds: offer a world a record, as a proposal, on the record.

Lifted out of `cmd_world`'s `declare` branch (stage-0 §241) so the CLI's `world declare`, its
`world declare-batch`, and the server's `world_declare` tools all run one function and report
one dict. What it keeps from the CLI is the doctrine: **warned, never refused** — a world is
built one record at a time and is transiently incoherent by nature, so a complaint here is a
report and the gate is `world accept`, which is a person's act and is not in this module.
What it adds is provenance: every proposal now lands with an event in the same transaction
naming who proposed it (`actor`) and through what (`payload.via`), because a proposal a
server wrote and a proposal the Architect wrote were otherwise indistinguishable rows.

Nothing here ranks, chooses or judges: `worlds.world_record` mints at PROPOSED, the checks
are `worlds.validate`, `worlds.slot_warnings` and `extraction.unreadable_sheets` exactly as
`declare` ran them, and `supersedes` is `integrity.disagreement_key` — the same slot rule
`world accept` will apply — reported early so an agent can see what its own redeclaration
replaces before acceptance quietly leaves the first one behind.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, TypedDict

import litharness_contracts as lc

from litharness.application.ports import WorldProposalStore
from litharness.domain import extraction, integrity
from litharness.domain import state as state_mod
from litharness.domain import worlds as worlds_domain
from litharness.domain.events import Event, EventType

#: What `payload.via` says on the event a declaration writes. One string per surface, so the
#: log can be read by who typed the record.
VIA_CLI = "world declare"
VIA_BATCH = "world declare-batch"
VIA_SERVER = "mcp world_declare"

_DECLARATION_KEYS = frozenset({"subject", "predicate", "value", "object", "order_key", "note"})


@dataclass(frozen=True, slots=True)
class WorldDeclaration:
    """One record as an agent offers it: the slots `world declare` takes, typed."""

    subject: str
    predicate: str
    value: object = None
    object: str | None = None
    order_key: str | None = None
    note: str | None = None

    @classmethod
    def from_mapping(cls, item: Mapping[str, Any]) -> WorldDeclaration:
        """A declaration from a JSON object; an unknown key is refused by name rather than
        dropped, because a misspelt `order-key` that silently became prose is the class of
        defect `world vocabulary` exists to stop."""
        unknown = sorted(set(item) - _DECLARATION_KEYS)
        if unknown:
            raise ValueError(
                f"unknown key(s) {', '.join(unknown)}; a declaration takes "
                f"{', '.join(sorted(_DECLARATION_KEYS))}"
            )
        subject = item.get("subject")
        predicate = item.get("predicate")
        if not isinstance(subject, str) or not subject.strip():
            raise ValueError("a declaration needs a subject")
        if not isinstance(predicate, str) or not predicate.strip():
            raise ValueError("a declaration needs a predicate")
        for key in ("object", "order_key", "note"):
            if item.get(key) is not None and not isinstance(item[key], str):
                raise ValueError(f"{key} must be a string when given")
        return cls(
            subject=subject,
            predicate=predicate,
            value=item.get("value"),
            object=item.get("object"),
            order_key=item.get("order_key"),
            note=item.get("note"),
        )


class DeclareResult(TypedDict):
    record_id: str
    authority: str
    new: bool
    supersedes: list[str]
    says: str
    not_yet_coherent: list[str]
    will_not_resolve: list[str]
    cannot_be_read: list[str]


class BatchResult(TypedDict):
    results: list[dict[str, Any]]
    declared: int
    refused: int
    not_attempted: int


def declare_world_record(
    store: WorldProposalStore,
    book_id: str,
    branch_id: str,
    item: WorldDeclaration,
    *,
    stamp: str,
    actor: str,
    project_id: str,
    via: str = VIA_CLI,
) -> DeclareResult:
    """Offer the world one record. PROPOSED, never canon; warned, never refused.

    The three report lists are the CLI's, unchanged in meaning: `not_yet_coherent` is what
    the rest of the world may still settle (a question awaiting its answer, a rung awaiting
    its chain); `will_not_resolve` is a record in a slot nothing will ever settle, because
    there is no retraction and a correction fills a different slot; `cannot_be_read` is a
    sheet the parser refuses, which a declaration in the same slot replaces. `supersedes`
    names the earlier proposals in this record's slot that `world accept` will leave behind.
    """
    record = worlds_domain.world_record(
        worlds_domain.normalise_id(item.subject),
        item.predicate,
        value=item.value,
        object_ref=(worlds_domain.normalise_id(item.object) if item.object else None),
        order_key=item.order_key,
        note=item.note,
    )
    existing = store.state_records(book_id, branch_id)
    slot = integrity.disagreement_key(record)
    supersedes = [
        earlier.record_id
        for earlier in existing
        if earlier.authority is lc.StateAuthority.PROPOSED
        and earlier.record_id != record.record_id
        and integrity.disagreement_key(earlier) == slot
    ]
    complaints = worlds_domain.validate([*existing, record])
    fresh = worlds_domain.validate(existing)
    new_complaints = [complaint for complaint in complaints if complaint not in fresh]
    warnings = worlds_domain.slot_warnings(record)
    unreadable = list(extraction.unreadable_sheets([record]).values())
    written = store.record_state_records(
        book_id,
        branch_id,
        [record],
        created_at=stamp,
        events=[
            Event(
                event_type=EventType.STATE_CANDIDATES_EXTRACTED,
                project_id=project_id,
                created_at=stamp,
                actor=actor,
                book_id=book_id,
                branch_id=branch_id,
                payload={
                    "via": via,
                    "record_id": record.record_id,
                    "subject": record.subject,
                    "predicate": record.predicate,
                    "authority": record.authority.value,
                },
            )
        ],
    )
    return {
        "record_id": record.record_id,
        "authority": record.authority.value,
        "new": bool(written),
        "supersedes": supersedes,
        "says": state_mod.describe(record),
        "not_yet_coherent": new_complaints,
        "will_not_resolve": list(warnings),
        "cannot_be_read": unreadable,
    }


def declare_world_records(
    store: WorldProposalStore,
    book_id: str,
    branch_id: str,
    items: Sequence[WorldDeclaration | Mapping[str, Any]],
    *,
    stamp: str,
    actor: str,
    project_id: str,
    via: str = VIA_BATCH,
    stop_on_incoherent: bool = False,
) -> BatchResult:
    """Several records in one call, each reported as `declare_world_record` reports one.

    **Not atomic, by design** (§139.3's shape): a record is a proposal and a proposal that
    landed is not undone by a neighbour that could not be built. A declaration that cannot be
    built at all — an unknown key, a missing subject, a value the domain refuses — is
    recorded under its index as `refused` and the loop continues. `stop_on_incoherent` stops
    after the first record whose report carries `will_not_resolve` or `cannot_be_read`, for
    an agent that would rather fix a slot than pile on it; the rest are counted as
    `not_attempted`. A locked store stops the batch at the first locked record — the
    `sqlite3.OperationalError` propagates and is never retried here — and the caller reports
    the remainder as not attempted.
    """
    results: list[dict[str, Any]] = []
    declared = refused = 0
    index = 0
    for index, raw in enumerate(items):
        try:
            item = (
                raw if isinstance(raw, WorldDeclaration) else WorldDeclaration.from_mapping(raw)
            )
            result = declare_world_record(
                store,
                book_id,
                branch_id,
                item,
                stamp=stamp,
                actor=actor,
                project_id=project_id,
                via=via,
            )
        except sqlite3.OperationalError:
            raise
        except ValueError as error:
            refused += 1
            results.append({"index": index, "refused": str(error)})
            continue
        declared += 1
        results.append({"index": index, **result})
        if stop_on_incoherent and (result["will_not_resolve"] or result["cannot_be_read"]):
            index += 1
            break
    else:
        index = len(items)
    return {
        "results": results,
        "declared": declared,
        "refused": refused,
        "not_attempted": len(items) - index,
    }


__all__ = [
    "VIA_BATCH",
    "VIA_CLI",
    "VIA_SERVER",
    "BatchResult",
    "DeclareResult",
    "WorldDeclaration",
    "declare_world_record",
    "declare_world_records",
]
