"""Immutable plan revisions and atomic plan-proposal persistence."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Sequence
from typing import Any, Protocol

import litharness_contracts as lc

from litharness.adapters.sqlite_errors import IntegrityFailure
from litharness.adapters.sqlite_jobs import SqliteJobRepository, TransactionFactory
from litharness.domain.directives import Directive, DirectiveStatus
from litharness.domain.events import Event, EventType
from litharness.domain.plan_refinement import (
    PlanApplication,
    PlanConflict,
    PlanProposalError,
    PlanProposalStatus,
    PlanRevision,
    StoredPlanProposal,
    apply_plan_proposal,
    proposal_from_dict,
    proposal_to_dict,
)
from litharness.domain.policy import Outcome, PolicyDecision

EventInserter = Callable[[sqlite3.Connection, Event], None]
DirectiveDecoder = Callable[[sqlite3.Row], Directive]


class DecisionInserter(Protocol):
    def __call__(
        self,
        connection: sqlite3.Connection,
        decision: PolicyDecision,
        *,
        decided_at: str,
    ) -> bool: ...


def _plan_revision_from_row(row: sqlite3.Row) -> PlanRevision:
    payload = json.loads(row["items_json"])
    if not isinstance(payload, list):
        raise IntegrityFailure("plan revision items_json is not a list")
    return PlanRevision(
        book_id=row["book_id"],
        branch_id=row["branch_id"],
        items=tuple(lc.from_jsonable(lc.PlanItem, item) for item in payload),
        parent_plan_revision_id=row["parent_plan_revision_id"],
        source_snapshot_id=row["source_snapshot_id"],
        plan_revision_id=row["plan_revision_id"],
    )


class SqlitePlanRepository:
    """Persistence capability for plans, proposals, and their atomic side effects."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        transaction: TransactionFactory,
        *,
        insert_event: EventInserter,
        insert_decision: DecisionInserter,
        decode_directive: DirectiveDecoder,
        jobs: SqliteJobRepository,
    ) -> None:
        self._connection = connection
        self._transaction = transaction
        self._insert_event = insert_event
        self._insert_decision = insert_decision
        self._decode_directive = decode_directive
        self._jobs = jobs

    def record_plan_items(
        self,
        book_id: str,
        branch_id: str,
        items: Sequence[lc.PlanItem],
        *,
        created_at: str,
        source_revision_id: str | None = None,
        events: Sequence[Event] = (),
    ) -> int:
        """Store imported plan statements and bootstrap a complete immutable root."""
        inserted = 0
        with self._transaction() as connection:
            for item in items:
                scope = item.scope.logical_id if item.scope else None
                cursor = connection.execute(
                    "INSERT OR IGNORE INTO plan_items (book_id, branch_id, logical_id, "
                    "kind, text, scope_logical_id, item_json, source_revision_id, "
                    "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        book_id,
                        branch_id,
                        item.logical_id,
                        item.kind.value,
                        item.text,
                        scope,
                        json.dumps(lc.to_jsonable(item), sort_keys=True, ensure_ascii=False),
                        source_revision_id,
                        created_at,
                    ),
                )
                inserted += cursor.rowcount
            for event in events:
                self._insert_event(connection, event)
            if self.plan_head(connection, book_id, branch_id) is None:
                try:
                    root = self.legacy_plan_revision(connection, book_id, branch_id)
                except PlanProposalError:
                    root = None
                if root is not None:
                    self.insert_plan_revision(connection, root, created_at=created_at)
                    connection.execute(
                        "INSERT INTO plan_heads (book_id, branch_id, plan_revision_id) "
                        "VALUES (?, ?, ?)",
                        (book_id, branch_id, root.plan_revision_id),
                    )
        return inserted

    def plan_items(
        self,
        book_id: str,
        branch_id: str,
        *,
        kind: lc.PlanKind | None = None,
    ) -> list[lc.PlanItem]:
        head = self.plan_head(self._connection, book_id, branch_id)
        if head is not None:
            return [item for item in head.items if kind is None or item.kind is kind]
        sql = "SELECT item_json FROM plan_items WHERE book_id = ? AND branch_id = ?"
        params: list[Any] = [book_id, branch_id]
        if kind is not None:
            sql += " AND kind = ?"
            params.append(kind.value)
        sql += " ORDER BY logical_id"
        return [
            lc.from_jsonable(lc.PlanItem, json.loads(row["item_json"]))
            for row in self._connection.execute(sql, params)
        ]

    @staticmethod
    def legacy_plan_revision(
        connection: sqlite3.Connection,
        book_id: str,
        branch_id: str,
    ) -> PlanRevision | None:
        rows = connection.execute(
            "SELECT item_json, source_revision_id FROM plan_items "
            "WHERE book_id = ? AND branch_id = ? ORDER BY logical_id",
            (book_id, branch_id),
        ).fetchall()
        if not rows:
            return None
        source_snapshot_id = next(
            (row["source_revision_id"] for row in rows if row["source_revision_id"]),
            None,
        )
        return PlanRevision(
            book_id=book_id,
            branch_id=branch_id,
            items=tuple(
                lc.from_jsonable(lc.PlanItem, json.loads(row["item_json"])) for row in rows
            ),
            source_snapshot_id=source_snapshot_id,
        )

    @staticmethod
    def plan_head(
        connection: sqlite3.Connection,
        book_id: str,
        branch_id: str,
    ) -> PlanRevision | None:
        row = connection.execute(
            "SELECT revisions.* FROM plan_heads AS heads "
            "JOIN plan_revisions AS revisions "
            "ON revisions.plan_revision_id = heads.plan_revision_id "
            "WHERE heads.book_id = ? AND heads.branch_id = ?",
            (book_id, branch_id),
        ).fetchone()
        return None if row is None else _plan_revision_from_row(row)

    @staticmethod
    def insert_plan_revision(
        connection: sqlite3.Connection,
        revision: PlanRevision,
        *,
        created_at: str,
        proposal_id: str | None = None,
    ) -> None:
        connection.execute(
            "INSERT OR IGNORE INTO plan_revisions "
            "(plan_revision_id, book_id, branch_id, parent_plan_revision_id, items_json, "
            "source_snapshot_id, proposal_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                revision.plan_revision_id,
                revision.book_id,
                revision.branch_id,
                revision.parent_plan_revision_id,
                json.dumps(
                    [lc.to_jsonable(item) for item in revision.items],
                    sort_keys=True,
                    ensure_ascii=False,
                ),
                revision.source_snapshot_id,
                proposal_id,
                created_at,
            ),
        )

    def plan_revision(self, book_id: str, branch_id: str) -> PlanRevision | None:
        return self.plan_head(self._connection, book_id, branch_id) or self.legacy_plan_revision(
            self._connection, book_id, branch_id
        )

    def load_plan_revision(self, plan_revision_id: str) -> PlanRevision:
        row = self._connection.execute(
            "SELECT * FROM plan_revisions WHERE plan_revision_id = ?",
            (plan_revision_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"no plan revision {plan_revision_id}")
        return _plan_revision_from_row(row)

    def plan_revision_for_id(self, plan_revision_id: str) -> PlanRevision:
        row = self._connection.execute(
            "SELECT * FROM plan_revisions WHERE plan_revision_id = ?",
            (plan_revision_id,),
        ).fetchone()
        if row is not None:
            return _plan_revision_from_row(row)
        legacy_rows = self._connection.execute(
            "SELECT DISTINCT book_id, branch_id FROM plan_items"
        ).fetchall()
        for legacy_row in legacy_rows:
            try:
                revision = self.legacy_plan_revision(
                    self._connection,
                    legacy_row["book_id"],
                    legacy_row["branch_id"],
                )
            except PlanProposalError:
                continue
            if revision is not None and revision.plan_revision_id == plan_revision_id:
                return revision
        raise KeyError(f"no plan revision {plan_revision_id}")

    def plan_history(self, book_id: str, branch_id: str) -> list[PlanRevision]:
        current = self.plan_revision(book_id, branch_id)
        history: list[PlanRevision] = []
        seen: set[str] = set()
        while current is not None:
            if current.plan_revision_id in seen:
                raise IntegrityFailure("cycle in plan revision lineage")
            seen.add(current.plan_revision_id)
            history.append(current)
            parent_id = current.parent_plan_revision_id
            current = self.load_plan_revision(parent_id) if parent_id else None
        return history

    def load_plan_proposal(self, proposal_id: str) -> StoredPlanProposal:
        row = self._connection.execute(
            "SELECT * FROM plan_proposals WHERE proposal_id = ?", (proposal_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"no plan proposal {proposal_id}")
        payload = json.loads(row["proposal_json"])
        if not isinstance(payload, dict):
            raise IntegrityFailure("plan proposal JSON is not an object")
        return StoredPlanProposal(
            proposal=proposal_from_dict(payload),
            status=PlanProposalStatus(row["status"]),
            resulting_plan_revision_id=row["resulting_plan_revision_id"],
            error=row["error"],
            created_at=row["created_at"],
            applied_at=row["applied_at"],
        )

    def commit_plan_application(
        self,
        application: PlanApplication,
        *,
        created_at: str,
        interpreted_at: str,
        events: Sequence[Event],
        decision: PolicyDecision,
    ) -> None:
        """Commit plan movement, its decision, directive readings, and events atomically."""
        proposal = application.proposal
        book_id = application.before.book_id
        branch_id = application.before.branch_id
        if application.before.plan_revision_id != proposal.base_plan_revision_id:
            raise PlanProposalError("application baseline does not match its proposal")
        plan_events = [event for event in events if event.event_type is EventType.PLAN_CHANGED]
        if not plan_events or any(
            event.book_id != book_id
            or event.branch_id != branch_id
            or event.revision_id != application.after.plan_revision_id
            for event in plan_events
        ):
            raise ValueError("plan application requires a matching PlanChanged event")
        if (
            decision.outcome is not Outcome.ACCEPT
            or decision.base_revision_id != application.before.plan_revision_id
            or decision.resulting_revision_id != application.after.plan_revision_id
        ):
            raise ValueError("plan acceptance decision does not match the application")
        decision_events = [
            event
            for event in events
            if event.event_type is EventType.POLICY_DECISION_RECORDED
            and event.payload.get("decision_id") == decision.decision_id
        ]
        if not decision_events:
            raise ValueError("plan acceptance decision requires its recorded event")

        conflict: PlanConflict | None = None
        with self._transaction() as connection:
            stored = connection.execute(
                "SELECT status, resulting_plan_revision_id, error FROM plan_proposals "
                "WHERE proposal_id = ?",
                (proposal.proposal_id,),
            ).fetchone()
            if stored is not None:
                if (
                    stored["status"] == PlanProposalStatus.APPLIED.value
                    and stored["resulting_plan_revision_id"] == application.after.plan_revision_id
                ):
                    return
                conflict = PlanConflict(
                    stored["error"] or f"proposal {proposal.proposal_id} already recorded"
                )
            else:
                current = self.plan_head(connection, book_id, branch_id)
                if current is None:
                    current = self.legacy_plan_revision(connection, book_id, branch_id)
                if current is None or current.plan_revision_id != proposal.base_plan_revision_id:
                    actual = current.plan_revision_id[:12] if current else "no plan"
                    message = (
                        f"proposal planned against {proposal.base_plan_revision_id[:12]}, "
                        f"but plan head is {actual}"
                    )
                    connection.execute(
                        "INSERT INTO plan_proposals "
                        "(proposal_id, book_id, branch_id, base_plan_revision_id, "
                        "proposal_json, status, resulting_plan_revision_id, error, "
                        "created_at, applied_at) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, NULL)",
                        (
                            proposal.proposal_id,
                            book_id,
                            branch_id,
                            proposal.base_plan_revision_id,
                            json.dumps(
                                proposal_to_dict(proposal),
                                sort_keys=True,
                                ensure_ascii=False,
                            ),
                            PlanProposalStatus.CONFLICTED.value,
                            message,
                            created_at,
                        ),
                    )
                    conflict = PlanConflict(message)
                else:
                    validated = apply_plan_proposal(current, proposal)
                    if validated.after.plan_revision_id != application.after.plan_revision_id:
                        raise PlanProposalError(
                            "application result does not match its proposal and current head"
                        )
                    self.insert_plan_revision(connection, current, created_at=created_at)
                    for reading in proposal.readings:
                        row = connection.execute(
                            "SELECT * FROM directives WHERE directive_id = ?",
                            (reading.directive_id,),
                        ).fetchone()
                        if row is None:
                            raise KeyError(f"no directive {reading.directive_id}")
                        directive = self._decode_directive(row)
                        if directive.book_id not in {None, book_id} or directive.branch_id not in {
                            None,
                            branch_id,
                        }:
                            raise PlanProposalError(
                                f"directive {directive.directive_id} belongs to another branch"
                            )
                        interpreted = directive.interpret(
                            reading.interpretation,
                            at=interpreted_at,
                            constraint_ids=reading.produced_constraint_ids,
                        ).transition_to(DirectiveStatus.APPLIED)
                        connection.execute(
                            "UPDATE directives SET status = ?, interpretation = ?, "
                            "produced_constraint_ids = ?, interpreted_at = ? "
                            "WHERE directive_id = ?",
                            (
                                interpreted.status.value,
                                interpreted.interpretation,
                                json.dumps(list(interpreted.produced_constraint_ids)),
                                interpreted.interpreted_at,
                                interpreted.directive_id,
                            ),
                        )
                    self.insert_plan_revision(
                        connection,
                        validated.after,
                        created_at=created_at,
                        proposal_id=proposal.proposal_id,
                    )
                    connection.execute(
                        "INSERT INTO plan_proposals "
                        "(proposal_id, book_id, branch_id, base_plan_revision_id, "
                        "proposal_json, status, resulting_plan_revision_id, error, "
                        "created_at, applied_at) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)",
                        (
                            proposal.proposal_id,
                            book_id,
                            branch_id,
                            proposal.base_plan_revision_id,
                            json.dumps(
                                proposal_to_dict(proposal),
                                sort_keys=True,
                                ensure_ascii=False,
                            ),
                            PlanProposalStatus.APPLIED.value,
                            validated.after.plan_revision_id,
                            created_at,
                            interpreted_at,
                        ),
                    )
                    connection.execute(
                        "INSERT INTO plan_heads (book_id, branch_id, plan_revision_id) "
                        "VALUES (?, ?, ?) ON CONFLICT (book_id, branch_id) DO UPDATE SET "
                        "plan_revision_id = excluded.plan_revision_id",
                        (book_id, branch_id, validated.after.plan_revision_id),
                    )
                    self._jobs.advance_plan_epoch(
                        connection,
                        book_id,
                        branch_id,
                        at=interpreted_at,
                        reason=f"plan changed to {validated.after.plan_revision_id[:12]}",
                    )
                    self._jobs.cancel_queued_scene_jobs(
                        connection,
                        book_id,
                        branch_id,
                        reason=(
                            f"superseded by plan revision {validated.after.plan_revision_id[:12]}"
                        ),
                    )
                    self._insert_decision(
                        connection,
                        decision,
                        decided_at=interpreted_at,
                    )
                    for event in events:
                        self._insert_event(connection, event)
        if conflict is not None:
            raise conflict

    def verify_integrity(self) -> None:
        """Rebuild all persisted plans and validate head ownership."""
        for row in self._connection.execute("SELECT * FROM plan_revisions"):
            _plan_revision_from_row(row)
        for row in self._connection.execute("SELECT proposal_json FROM plan_proposals"):
            payload = json.loads(row["proposal_json"])
            if not isinstance(payload, dict):
                raise IntegrityFailure("plan proposal JSON is not an object")
            proposal_from_dict(payload)
        mismatched_heads = self._connection.execute(
            "SELECT COUNT(*) AS n FROM plan_heads AS heads "
            "JOIN plan_revisions AS revisions "
            "ON revisions.plan_revision_id = heads.plan_revision_id "
            "WHERE revisions.book_id != heads.book_id "
            "OR revisions.branch_id != heads.branch_id"
        ).fetchone()["n"]
        if mismatched_heads:
            raise IntegrityFailure(
                f"{mismatched_heads} plan heads reference another book or branch"
            )
