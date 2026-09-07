"""The dicts the operator's read verbs print, built once so two surfaces cannot disagree.

Lifted out of `cli.py` (stage-0 §241). Each function below returns exactly the object the
corresponding `--json` verb prints — `findings`, `events` and `plans` moved here with their
bytes unchanged — and `state`, `jobs`, `exceptions`, `directives`, `characters` and `verify`
gained their first machine-readable shape here, which the CLI now prints under `--json` and
the agent surface returns. The text renderings stay in `cli.py`; they read these dicts or the
same rows, never a second query.

**A shape is a decision.** The state row is the one an agent reads canon through, so its
columns are named here once: the story position, whether this system read the record out of
its own prose or was given it, the authority, the subject/predicate/said sentence, the note,
and who may know it. Nothing here ranks, scores or judges; every value is a column somebody
wrote.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any, Literal, Protocol, TypedDict

import litharness_contracts as lc

from litharness.application.dossier import finding_row
from litharness.application.ports import (
    DirectiveInbox,
    ExceptionRepository,
    FindingRepository,
    JobQueue,
    ProvenanceReader,
    StateRepository,
    StoredEvent,
)
from litharness.domain import characters as characters_mod
from litharness.domain import directors as directors_domain
from litharness.domain import extraction
from litharness.domain import state as state_mod
from litharness.domain.directives import DirectiveStatus
from litharness.domain.jobs import JobStatus
from litharness.domain.plan_refinement import PlanProposalStatus, StoredPlanProposal


class BadSince(ValueError):
    """`--since` was neither a sequence number nor an ISO-8601 instant.

    Until §241 a value that parsed as nothing matched nothing: the cursor compared as a
    string against every stamp, so `--since notanumber` printed an empty log at exit 0 and
    read as "nothing happened". A `ValueError`, so the CLI's fault path prints it at exit 2.
    """


#: An ISO-8601 instant or any prefix of one down to the year: `2026`, `2026-08-13`,
#: `2026-08-13T10:00:00Z`. The stamps are Z-normalised, so a prefix compares correctly.
_ISO_PREFIX = re.compile(r"^\d{4}(-\d{2}(-\d{2}([T ]\d{2}(:\d{2}(:\d{2}(\.\d+)?)?)?Z?)?)?)?$")


def parse_since(text: str | None) -> int | str:
    """The cursor `events` resumes from: a sequence number, or an ISO prefix. 0 for none."""
    if text is None or not text.strip():
        return 0
    text = text.strip()
    if text.isdigit():
        return int(text)
    if _ISO_PREFIX.match(text):
        return text
    raise BadSince(
        f"--since takes a sequence number from an earlier read's cursor line or an ISO-8601 "
        f"instant such as 2026-08-13; {text!r} is neither"
    )


def event_row(stored: StoredEvent) -> dict[str, Any]:
    return {
        "sequence": stored.sequence,
        "event_type": stored.event.event_type.value,
        "created_at": stored.event.created_at,
        "actor": stored.event.actor,
        "book_id": stored.event.book_id,
        "branch_id": stored.event.branch_id,
        "revision_id": stored.event.revision_id,
        "causation_id": stored.event.causation_id,
        "correlation_id": stored.event.correlation_id,
        "payload": stored.event.payload,
    }


class EventsView(TypedDict):
    events: list[dict[str, Any]]
    matched: int
    shown: int
    next_since: int


def events_view(
    store: ProvenanceReader,
    *,
    since: str | None,
    types: Sequence[str],
    book_id: str | None,
    limit: int,
) -> EventsView:
    """The event log in write order from a cursor, bounded, with where to resume.

    `since` is a sequence number or an ISO instant (see `parse_since`); a bad one raises
    rather than matching nothing. `limit <= 0` means all.
    """
    cursor = parse_since(since)
    stored = store.read_log(since=cursor if isinstance(cursor, int) else 0)
    if isinstance(cursor, str):
        stored = [item for item in stored if item.event.created_at >= cursor]
    wanted = set(types)
    if wanted:
        stored = [item for item in stored if item.event.event_type.value in wanted]
    if book_id:
        stored = [item for item in stored if item.event.book_id == book_id]
    matched = len(stored)
    shown = stored if limit <= 0 else stored[:limit]
    next_since = shown[-1].sequence if shown else (cursor if isinstance(cursor, int) else 0)
    return {
        "events": [event_row(item) for item in shown],
        "matched": matched,
        "shown": len(shown),
        "next_since": next_since,
    }


class FindingsView(TypedDict):
    book_id: str
    branch_id: str
    open_only: bool
    findings: list[dict[str, Any]]
    shown: int
    blocking: int


def findings_view(
    store: FindingRepository,
    book_id: str,
    branch_id: str,
    *,
    logical_id: str | None,
    open_only: bool,
) -> FindingsView:
    """What the evaluators say is wrong, worst first; `blocking` is what a gate would refuse on."""
    items = store.findings(book_id, branch_id, logical_id=logical_id, open_only=open_only)
    return {
        "book_id": book_id,
        "branch_id": branch_id,
        "open_only": open_only,
        "findings": [finding_row(item) for item in items],
        "shown": len(items),
        "blocking": sum(1 for item in items if item.blocks),
    }


def proposal_row(stored: StoredPlanProposal) -> dict[str, Any]:
    """The proposal behind one plan revision. A revision no proposal produced reads as null,
    which is the root of the lineage rather than a step whose proposal went missing."""
    return {
        "proposal_id": stored.proposal.proposal_id,
        "summary": stored.proposal.summary,
        "rollback_of": stored.proposal.rollback_of,
        "directives": [reading.directive_id for reading in stored.proposal.readings],
    }


class PlansView(TypedDict):
    book_id: str
    branch_id: str
    revisions: list[dict[str, Any]]
    conflicted: list[dict[str, Any]]


def plans_view(store: ProvenanceReader, book_id: str, branch_id: str) -> PlansView:
    """The plan's lineage, newest first, and the proposal that produced each step."""
    history = store.plan_history(book_id, branch_id)
    proposals = store.plan_proposals(book_id, branch_id)
    applied = {
        stored.resulting_plan_revision_id: stored
        for stored in proposals
        if stored.status is PlanProposalStatus.APPLIED
    }
    conflicted = [item for item in proposals if item.status is PlanProposalStatus.CONFLICTED]
    return {
        "book_id": book_id,
        "branch_id": branch_id,
        "revisions": [
            {
                "plan_revision_id": revision.plan_revision_id,
                "head": index == 0,
                "items": len(revision.items),
                "locked": sum(1 for item in revision.items if item.locked),
                "proposal": None
                if applied.get(revision.plan_revision_id) is None
                else proposal_row(applied[revision.plan_revision_id]),
            }
            for index, revision in enumerate(history)
        ],
        "conflicted": [
            {"proposal_id": item.proposal.proposal_id, "error": item.error or "conflicted"}
            for item in conflicted
        ],
    }


class StateRow(TypedDict):
    order_key: str | None
    provenance: Literal["read", "given"]
    authority: str
    canon: bool
    subject: str
    predicate: str
    says: str
    note: str | None
    pov_visibility: list[str]


class StateView(TypedDict):
    book_id: str
    branch_id: str
    records: list[StateRow]
    read_from_own_prose: int
    unplaced: int


def state_row(record: lc.StateRecord) -> StateRow:
    """One canon record as the text view prints it: position, provenance, authority, and the
    sentence `state.describe` writes. `read` means this system extracted it from prose it
    generated; `given` means it was imported or declared."""
    extracted = record.predicate_registry_version == extraction.REGISTRY_VERSION
    return {
        "order_key": state_mod.order_key_of(record),
        "provenance": "read" if extracted else "given",
        "authority": record.authority.value,
        "canon": state_mod.is_canon(record),
        "subject": record.subject,
        "predicate": record.predicate,
        "says": state_mod.describe(record),
        "note": record.note or None,
        "pov_visibility": list(record.pov_visibility or ()),
    }


def state_view(
    store: StateRepository,
    book_id: str,
    branch_id: str,
    *,
    subject: str | None,
    predicate: str | None,
) -> StateView:
    """What this book holds as true, in story order (§11's objective story state)."""
    records = store.state_records(book_id, branch_id, subject=subject)
    if predicate:
        records = [item for item in records if item.predicate == predicate]
    ordered = state_mod.in_story_order(records)
    rows = [state_row(record) for record in ordered]
    return {
        "book_id": book_id,
        "branch_id": branch_id,
        "records": rows,
        "read_from_own_prose": sum(1 for row in rows if row["provenance"] == "read"),
        "unplaced": sum(1 for row in rows if row["order_key"] is None),
    }


class JobsStore(JobQueue, ProvenanceReader, Protocol):
    """Counts from the queue, rows by status from the reader."""


class JobsView(TypedDict):
    counts: dict[str, int]
    status: str | None
    jobs: list[dict[str, Any]]


def jobs_view(store: JobsStore, *, status: JobStatus | None) -> JobsView:
    """Queue depth by status, and the units in one status when asked. `counts` is always
    present: an empty queue and a failed query used to print the same nothing."""
    jobs = store.jobs_by_status(status) if status is not None else []
    return {
        "counts": dict(store.job_counts_by_status()),
        "status": status.value if status is not None else None,
        "jobs": [
            {
                "job_id": job.job_id,
                "job_kind": job.job_kind,
                "status": job.status.value,
                "attempts": job.attempts,
                "priority": job.priority,
                "error": job.error,
            }
            for job in jobs
        ],
    }


class ExceptionsView(TypedDict):
    exceptions: list[dict[str, Any]]
    open: int


def exceptions_view(store: ExceptionRepository) -> ExceptionsView:
    """What policy could not resolve and is waiting on a person."""
    items = store.open_exceptions()
    return {
        "exceptions": [
            {
                "exception_id": item.exception_id,
                "kind": item.kind.value,
                "status": item.status.value,
                "job_id": item.job_id,
                "logical_id": item.logical_id,
                "summary": item.summary,
                "raised_at": item.raised_at,
                "attempts": item.attempts,
            }
            for item in items
        ],
        "open": len(items),
    }


class DirectivesView(TypedDict):
    status: str
    directives: list[dict[str, Any]]
    machine_written: int


def directives_view(store: DirectiveInbox, *, status: DirectiveStatus) -> DirectivesView:
    """Captured direction in one status, with who wrote each line — a machine-authored
    directive that read exactly like a person's was the laundering path the author column
    closed (`plan/director-role.md` §1)."""
    items = store.directives_by_status(status)
    return {
        "status": status.value,
        "directives": [
            {
                "directive_id": item.directive_id,
                "kind": item.kind.value,
                "precedence": item.precedence,
                "author": item.author or "human",
                "body": item.body,
                "book_id": item.book_id,
                "branch_id": item.branch_id,
                "received_at": item.received_at,
            }
            for item in items
        ],
        "machine_written": sum(
            1 for item in items if directors_domain.is_machine_author(item.author)
        ),
    }


#: What an empty cast means and what fills it. The seed is a paid, operator-run step, and
#: the sentence says so where an agent reads it rather than leaving it to guess.
NO_CAST_HINT = (
    "no cast on record for this branch; `architect seed` is a paid operator step at the CLI, "
    "then `world check`, then `world accept`"
)


class CharactersView(TypedDict):
    book_id: str
    branch_id: str
    characters: list[dict[str, Any]]
    hint: str | None


def characters_view(
    store: StateRepository, book_id: str, branch_id: str, *, subject: str | None
) -> CharactersView:
    """Everything canon holds about each person, one sheet each; an object in both cases,
    where the CLI used to print prose for an empty cast under `--json`."""
    people = characters_mod.cast(store.state_records(book_id, branch_id))
    if subject:
        people = tuple(person for person in people if person.subject == subject)
    return {
        "book_id": book_id,
        "branch_id": branch_id,
        "characters": [person.to_jsonable() for person in people],
        "hint": None if people else NO_CAST_HINT,
    }


class VerifyView(TypedDict):
    rebuilt: int
    unattributed: list[str]


def verify_view(store: ProvenanceReader) -> VerifyView:
    """Rebuild every revision from canonical records, and name the ones no decision explains."""
    return {
        "rebuilt": store.verify_integrity(),
        "unattributed": list(store.unattributed_revisions()),
    }


__all__ = [
    "NO_CAST_HINT",
    "BadSince",
    "CharactersView",
    "DirectivesView",
    "EventsView",
    "ExceptionsView",
    "FindingsView",
    "JobsView",
    "PlansView",
    "StateRow",
    "StateView",
    "VerifyView",
    "characters_view",
    "directives_view",
    "event_row",
    "events_view",
    "exceptions_view",
    "findings_view",
    "jobs_view",
    "parse_since",
    "plans_view",
    "proposal_row",
    "state_row",
    "state_view",
    "verify_view",
]
