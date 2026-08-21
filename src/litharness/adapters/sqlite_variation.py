"""Durable variation sessions, their attempts, and the knowledge those attempts support.

A capability repository in the shape `sqlite_jobs.py` and `sqlite_plans.py` established: it
receives the raw connection and the store's transaction factory, and the cross-cutting writers
it needs — events, decisions, jobs, gate serialisation — arrive as callables rather than as
imports, so nothing here has to reach back into `SqliteStore` and no cycle exists to break.

**Gate serialisation is injected for a sharper reason than tidiness.** The gate vector on an
attempt row and the gate vector on a policy decision are the same object and must round-trip
identically, or the diagnostics an audit reads off an attempt would stop matching the decision
recorded beside it. Passing the store's own `_gate_to_row` and `_gate_from_row` in means there
is exactly one projection of a gate into JSON in this package, which is the property that keeps
them honest — a second implementation here would drift the first time a field was added.

**One commit seam, and it is the whole module's point.** `commit_step` writes everything one
mediated action produces — the session row, the attempt, the patch artifact, derived knowledge,
consultation counters, the follow-up job, the events and the settling decision — inside a single
transaction. A crashed session therefore replays into convergence rather than into half a step,
and the Conductor, which settles on `latest_decision_for`, can never read a step's decision
before the attempt it settles exists.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Sequence
from typing import Any, Protocol

from litharness.adapters.sqlite_errors import IntegrityFailure
from litharness.adapters.sqlite_jobs import SqliteJobRepository, TransactionFactory
from litharness.domain.events import Event
from litharness.domain.jobs import Job
from litharness.domain.policy import GateOutcome, PolicyDecision
from litharness.domain.variation import (
    AttemptOutcome,
    KnowledgeItem,
    SessionLimits,
    SessionOutcome,
    SessionStatus,
    VariationAttempt,
    VariationObjective,
    VariationSession,
    decode_ids,
    encode_ids,
)

EventInserter = Callable[[sqlite3.Connection, Event], None]
GateEncoder = Callable[[GateOutcome], dict[str, Any]]
GateDecoder = Callable[[dict[str, Any]], GateOutcome]


class DecisionInserter(Protocol):
    def __call__(
        self,
        connection: sqlite3.Connection,
        decision: PolicyDecision,
        *,
        decided_at: str,
    ) -> bool: ...


class SqliteVariationRepository:
    """Persistence capability for the bounded variation loop."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        transaction: TransactionFactory,
        *,
        insert_event: EventInserter,
        insert_decision: DecisionInserter,
        encode_gate: GateEncoder,
        decode_gate: GateDecoder,
        jobs: SqliteJobRepository,
    ) -> None:
        self._connection = connection
        self._transaction = transaction
        self._insert_event = insert_event
        self._insert_decision = insert_decision
        self._encode_gate = encode_gate
        self._decode_gate = decode_gate
        self._jobs = jobs

    # -- reads ----------------------------------------------------------------

    def variation_session(self, session_id: str) -> VariationSession | None:
        row = self._connection.execute(
            "SELECT * FROM variation_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        return None if row is None else self._session_from_row(row)

    def open_variation_sessions(self) -> list[VariationSession]:
        return [
            self._session_from_row(row)
            for row in self._connection.execute(
                "SELECT * FROM variation_sessions WHERE status = ? ORDER BY rowid",
                (SessionStatus.OPEN.value,),
            )
        ]

    def variation_attempts(self, session_id: str) -> list[VariationAttempt]:
        return [
            self._attempt_from_row(row)
            for row in self._connection.execute(
                "SELECT * FROM variation_attempts WHERE session_id = ? ORDER BY ordinal",
                (session_id,),
            )
        ]

    def variation_patch(self, patch_digest: str) -> dict[str, Any] | None:
        row = self._connection.execute(
            "SELECT patch_json FROM variation_patches WHERE patch_digest = ?",
            (patch_digest,),
        ).fetchone()
        if row is None:
            return None
        payload = json.loads(row["patch_json"])
        if not isinstance(payload, dict):
            raise IntegrityFailure(f"variation patch {patch_digest} is not an object")
        return payload

    def knowledge_items(
        self, *, objective: VariationObjective, target_key: str | None = None
    ) -> list[KnowledgeItem]:
        sql = "SELECT * FROM knowledge_items WHERE objective = ?"
        params: list[Any] = [objective.value]
        if target_key is not None:
            sql += " AND target_key = ?"
            params.append(target_key)
        sql += " ORDER BY gate_rule_id, veto"
        return [
            self._knowledge_from_row(row)
            for row in self._connection.execute(sql, tuple(params))
        ]

    # -- the commit seam ------------------------------------------------------

    def commit_step(
        self,
        session: VariationSession,
        *,
        at: str,
        attempts: Sequence[VariationAttempt] = (),
        patches: Sequence[tuple[str, str]] = (),
        knowledge: Sequence[KnowledgeItem] = (),
        consulted: Sequence[str] = (),
        decision: PolicyDecision | None = None,
        events: Sequence[Event] = (),
        jobs: Sequence[Job] = (),
        write_revision: Callable[[sqlite3.Connection], None] | None = None,
    ) -> None:
        """Persist one mediated action's whole outcome atomically.

        `write_revision` is the accepted-commit case and nothing else: it is the store's own
        revision writer, already bound to the revision, the extracted state and the follow-up
        evaluations, handed in as a callable so the manuscript write and the session write share
        one transaction. The alternative — commit the revision, then update the session — has a
        crash window in which the book has moved and the session that moved it still reads
        open, which is exactly the split `commit_revision` refuses for state records one layer
        down.
        """
        with self._transaction() as connection:
            if write_revision is not None:
                write_revision(connection)
            for digest, payload in patches:
                connection.execute(
                    "INSERT OR IGNORE INTO variation_patches "
                    "(patch_digest, patch_json, created_at) VALUES (?, ?, ?)",
                    (digest, payload, at),
                )
            self._upsert_session(connection, session)
            for attempt in attempts:
                self._upsert_attempt(connection, attempt)
            for item in knowledge:
                self._upsert_knowledge(connection, item, at=at)
            for item_id in consulted:
                connection.execute(
                    "UPDATE knowledge_items SET consultations = consultations + 1 "
                    "WHERE item_id = ?",
                    (item_id,),
                )
            for job in jobs:
                self._jobs.insert_job(connection, job)
            for event in events:
                self._insert_event(connection, event)
            if decision is not None:
                self._insert_decision(connection, decision, decided_at=at)

    # -- row writers ----------------------------------------------------------

    def _upsert_session(
        self, connection: sqlite3.Connection, session: VariationSession
    ) -> None:
        """Insert the session, or advance the mutable half of an existing row.

        The immutable half — target, objective, limits, opening provenance — is written once
        and never touched again, so a conflicting update cannot rewrite what a session was for
        or what it was allowed to spend. What moves is the counters, the consultation list and
        the ending, which is the whole of what one step can change.
        """
        limits = session.limits
        connection.execute(
            "INSERT INTO variation_sessions (session_id, objective, book_id, branch_id, "
            "logical_id, finding_id, base_revision_id, opened_by_job_id, status, "
            "max_steps, max_provider_calls, max_evaluations, max_tokens, max_wall_seconds, "
            "max_cost_usd, steps, provider_calls, evaluations, tokens, cost_usd, malformed, "
            "lineage_inspections, consulted_item_ids, outcome, outcome_detail, opened_at, "
            "opened_at_epoch, closed_at) VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
            "?, ?) ON CONFLICT (session_id) DO UPDATE SET "
            "status = excluded.status, steps = excluded.steps, "
            "provider_calls = excluded.provider_calls, evaluations = excluded.evaluations, "
            "tokens = excluded.tokens, cost_usd = excluded.cost_usd, "
            "malformed = excluded.malformed, "
            "lineage_inspections = excluded.lineage_inspections, "
            "consulted_item_ids = excluded.consulted_item_ids, outcome = excluded.outcome, "
            "outcome_detail = excluded.outcome_detail, closed_at = excluded.closed_at",
            (
                session.session_id,
                session.objective.value,
                session.book_id,
                session.branch_id,
                session.logical_id,
                session.finding_id,
                session.base_revision_id,
                session.opened_by_job_id,
                session.status.value,
                limits.max_steps,
                limits.max_provider_calls,
                limits.max_evaluations,
                limits.max_tokens,
                limits.max_wall_seconds,
                limits.max_cost_usd,
                session.steps,
                session.provider_calls,
                session.evaluations,
                session.tokens,
                session.cost_usd,
                session.malformed,
                session.lineage_inspections,
                encode_ids(session.consulted_item_ids),
                None if session.outcome is None else session.outcome.value,
                session.outcome_detail,
                session.opened_at,
                session.opened_at_epoch,
                session.closed_at,
            ),
        )

    def _upsert_attempt(
        self, connection: sqlite3.Connection, attempt: VariationAttempt
    ) -> None:
        """Insert an attempt, or advance the one already at this address.

        An attempt is content-addressed over its session, ordinal and patch, so re-writing one
        is always the same attempt learning its verdict — proposed, then evaluated, then
        settled. Nothing here can change what was proposed; the patch digest is in the id.
        """
        connection.execute(
            "INSERT INTO variation_attempts (attempt_id, session_id, ordinal, "
            "parent_attempt_id, base_revision_id, patch_digest, strategy, evaluation, "
            "diagnostics, provider, model, tokens, cost_usd, evaluations, wall_ms, outcome, "
            "abandon_reason, created_at) VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (attempt_id) DO UPDATE SET evaluation = excluded.evaluation, "
            "diagnostics = excluded.diagnostics, tokens = excluded.tokens, "
            "cost_usd = excluded.cost_usd, evaluations = excluded.evaluations, "
            "wall_ms = excluded.wall_ms, outcome = excluded.outcome, "
            "abandon_reason = excluded.abandon_reason",
            (
                attempt.attempt_id,
                attempt.session_id,
                attempt.ordinal,
                attempt.parent_attempt_id,
                attempt.base_revision_id,
                attempt.patch_digest,
                attempt.strategy,
                json.dumps([self._encode_gate(gate) for gate in attempt.evaluation]),
                attempt.diagnostics,
                attempt.provider,
                attempt.model,
                attempt.tokens,
                attempt.cost_usd,
                attempt.evaluations,
                attempt.wall_ms,
                attempt.outcome.value,
                attempt.abandon_reason,
                attempt.created_at,
            ),
        )

    def _upsert_knowledge(
        self, connection: sqlite3.Connection, item: KnowledgeItem, *, at: str
    ) -> None:
        """Insert a knowledge claim, or extend the evidence under the one already recorded.

        The id addresses the claim and never the evidence, so a second session meeting the same
        wall extends the record rather than minting a near-duplicate row nobody would join. The
        evidence union is computed here rather than in the domain because it is a merge against
        what is already stored, and `consultations` is untouched on conflict: reading an item is
        a different event from observing it again.
        """
        row = connection.execute(
            "SELECT evidence FROM knowledge_items WHERE item_id = ?", (item.item_id,)
        ).fetchone()
        merged = (
            tuple(sorted(set(item.evidence) | set(decode_ids(row["evidence"]))))
            if row is not None
            else item.evidence
        )
        connection.execute(
            "INSERT INTO knowledge_items (item_id, objective, target_key, gate_rule_id, "
            "veto, statement, evidence, observations, consultations, first_seen_at, "
            "last_seen_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (item_id) DO UPDATE SET statement = excluded.statement, "
            "evidence = excluded.evidence, observations = excluded.observations, "
            "last_seen_at = excluded.last_seen_at",
            (
                item.item_id,
                item.objective.value,
                item.target_key,
                item.gate_rule_id,
                item.veto,
                item.statement,
                encode_ids(merged),
                len(merged),
                item.consultations,
                item.first_seen_at or at,
                at,
            ),
        )

    # -- row readers ----------------------------------------------------------

    def _session_from_row(self, row: sqlite3.Row) -> VariationSession:
        return VariationSession(
            session_id=row["session_id"],
            objective=VariationObjective(row["objective"]),
            book_id=row["book_id"],
            branch_id=row["branch_id"],
            logical_id=row["logical_id"],
            base_revision_id=row["base_revision_id"],
            opened_by_job_id=row["opened_by_job_id"],
            opened_at=row["opened_at"],
            opened_at_epoch=row["opened_at_epoch"],
            limits=SessionLimits(
                max_steps=row["max_steps"],
                max_provider_calls=row["max_provider_calls"],
                max_evaluations=row["max_evaluations"],
                max_tokens=row["max_tokens"],
                max_wall_seconds=row["max_wall_seconds"],
                max_cost_usd=row["max_cost_usd"],
            ),
            finding_id=row["finding_id"],
            status=SessionStatus(row["status"]),
            steps=row["steps"],
            provider_calls=row["provider_calls"],
            evaluations=row["evaluations"],
            tokens=row["tokens"],
            cost_usd=row["cost_usd"],
            malformed=row["malformed"],
            lineage_inspections=row["lineage_inspections"],
            consulted_item_ids=decode_ids(row["consulted_item_ids"]),
            outcome=None if row["outcome"] is None else SessionOutcome(row["outcome"]),
            outcome_detail=row["outcome_detail"],
            closed_at=row["closed_at"],
        )

    def _attempt_from_row(self, row: sqlite3.Row) -> VariationAttempt:
        gates = json.loads(row["evaluation"])
        if not isinstance(gates, list):
            raise IntegrityFailure(
                f"variation attempt {row['attempt_id']} evaluation is not a list"
            )
        return VariationAttempt(
            attempt_id=row["attempt_id"],
            session_id=row["session_id"],
            ordinal=row["ordinal"],
            base_revision_id=row["base_revision_id"],
            patch_digest=row["patch_digest"],
            outcome=AttemptOutcome(row["outcome"]),
            created_at=row["created_at"],
            parent_attempt_id=row["parent_attempt_id"],
            strategy=row["strategy"],
            evaluation=tuple(self._decode_gate(gate) for gate in gates),
            diagnostics=row["diagnostics"],
            provider=row["provider"],
            model=row["model"],
            tokens=row["tokens"],
            cost_usd=row["cost_usd"],
            evaluations=row["evaluations"],
            wall_ms=row["wall_ms"],
            abandon_reason=row["abandon_reason"],
        )

    @staticmethod
    def _knowledge_from_row(row: sqlite3.Row) -> KnowledgeItem:
        return KnowledgeItem(
            item_id=row["item_id"],
            objective=VariationObjective(row["objective"]),
            target_key=row["target_key"],
            gate_rule_id=row["gate_rule_id"],
            veto=row["veto"],
            statement=row["statement"],
            evidence=decode_ids(row["evidence"]),
            observations=row["observations"],
            consultations=row["consultations"],
            first_seen_at=row["first_seen_at"],
            last_seen_at=row["last_seen_at"],
        )


__all__ = ["SqliteVariationRepository"]
