"""SQLite persistence for revisions, events, the outbox and jobs.

SQLite is the plan's sanctioned single-node alpha store (§11), and it makes the hardest
Stage 0 property free: **everything a state change touches commits in one transaction.**
A revision, its node versions, its events and its outbox rows go in together or not at
all, so there is no window in which accepted prose exists without the event that records
it.

**Write-ordering rule, recorded now because it will matter later.** There is no separate
blob store at this stage — node content is a TEXT column, inside the same transaction.
When content does move to blobs, the order is: write the blob, fsync, *then* commit the
row that references it. An orphaned blob is garbage that a sweep reclaims; a row
referencing a missing blob is unrecoverable corruption. The asymmetry is the whole
argument, and it is the crash bug most likely to be gotten wrong by writing the cheap
one first.

**Restore is a rebuild, not a file copy.** `verify_integrity` re-reads every revision
through the domain constructors, which recompute every node's content hash and every
revision's content-addressed id. Corruption anywhere in storage surfaces as a mismatch
rather than as prose that is subtly not what was accepted.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from litharness.domain.directives import Directive, DirectiveKind, DirectiveStatus
from litharness.domain.events import Event, EventType, OutboxEntry, OutboxState
from litharness.domain.jobs import Job, JobStatus
from litharness.domain.nodes import BlockKind, LockKind, Node, NodeKind
from litharness.domain.patch import Veto
from litharness.domain.policy import (
    GateKind,
    GateOutcome,
    Outcome,
    PolicyDecision,
    VerdictSource,
)
from litharness.domain.revision import Revision, node_version_id

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"


class IntegrityFailure(Exception):
    """Storage returned something that does not rebuild. Never downgraded to a warning."""


def _split_statements(script: str) -> list[str]:
    """Split a migration into complete statements using SQLite's own parser.

    Naive splitting on ";" breaks the moment a statement contains a semicolon inside a
    string literal or a trigger body, so `sqlite3.complete_statement` decides.
    """
    statements: list[str] = []
    buffer = ""
    for line in script.splitlines(keepends=True):
        blank_or_comment = not line.strip() or line.lstrip().startswith("--")
        if blank_or_comment and not buffer:
            continue
        buffer += line
        if sqlite3.complete_statement(buffer):
            if buffer.strip():
                statements.append(buffer)
            buffer = ""
    if buffer.strip():
        raise ValueError(f"migration ends with an incomplete statement: {buffer[:80]!r}")
    return statements


def _directive_from_row(row: sqlite3.Row) -> Directive:
    return Directive(
        directive_id=row["directive_id"],
        kind=DirectiveKind(row["kind"]),
        body=row["body"],
        status=DirectiveStatus(row["status"]),
        book_id=row["book_id"],
        branch_id=row["branch_id"],
        target_logical_ids=tuple(json.loads(row["target_logical_ids"] or "[]")),
        interpretation=row["interpretation"],
        produced_constraint_ids=tuple(json.loads(row["produced_constraint_ids"] or "[]")),
        received_at=row["received_at"],
        interpreted_at=row["interpreted_at"],
        precedence=row["precedence"],
        superseded_by=row["superseded_by"],
        metadata=json.loads(row["metadata"]) if row["metadata"] else {},
    )


def _gate_to_row(gate: GateOutcome) -> dict[str, Any]:
    return {
        "gate": gate.gate.value,
        "rule_or_critic_id": gate.rule_or_critic_id,
        "passed": gate.passed,
        "verdict_source": gate.verdict_source.value,
        "blocking": gate.blocking,
        "vetoes": [veto.value for veto in gate.vetoes],
        "detail": gate.detail,
        "calibration_id": gate.calibration_id,
    }


def _gate_from_row(row: dict[str, Any]) -> GateOutcome:
    return GateOutcome(
        gate=GateKind(row["gate"]),
        rule_or_critic_id=row["rule_or_critic_id"],
        passed=bool(row["passed"]),
        verdict_source=VerdictSource(row["verdict_source"]),
        blocking=bool(row["blocking"]),
        vetoes=tuple(Veto(value) for value in row.get("vetoes", ())),
        detail=row.get("detail"),
        calibration_id=row.get("calibration_id"),
    )


def _decision_from_row(row: sqlite3.Row) -> PolicyDecision:
    return PolicyDecision(
        decision_id=row["decision_id"],
        outcome=Outcome(row["outcome"]),
        gates=tuple(_gate_from_row(item) for item in json.loads(row["gates"])),
        job_id=row["job_id"],
        logical_id=row["logical_id"],
        base_revision_id=row["base_revision_id"],
        resulting_revision_id=row["resulting_revision_id"],
        attempt=row["attempt"],
        provider=row["provider"],
        model=row["model"],
        profile=row["profile"],
        fell_back_from=tuple(json.loads(row["fell_back_from"] or "[]")),
        invocations=row["invocations"],
        total_tokens=row["total_tokens"],
        policy_config_digest=row["policy_config_digest"],
        reason=row["reason"],
    )


def _dump_payload(payload: dict[str, Any]) -> str | None:
    """Serialize a job payload, or NULL for an empty one.

    Empty maps to NULL rather than `"{}"` so that a job carrying no input is
    distinguishable in the table from one carrying an empty object, and so the column
    stays cheap for the no-op workload the endurance test runs.
    """
    if not payload:
        return None
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


@dataclass(frozen=True, slots=True)
class StoredEvent:
    sequence: int
    event: Event


class SqliteStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    # -- lifecycle ------------------------------------------------------------

    @classmethod
    def open(cls, path: str | Path, *, migrations: Path | None = None) -> SqliteStore:
        connection = sqlite3.connect(str(path), isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA synchronous=FULL")
        store = cls(connection)
        store.migrate(migrations or MIGRATIONS_DIR)
        return store

    def migrate(self, directory: Path) -> None:
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(name TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )
        applied = {
            row["name"] for row in self._connection.execute("SELECT name FROM schema_migrations")
        }
        for path in sorted(directory.glob("*.sql")):
            if path.name in applied:
                continue
            # Statements are executed individually rather than through `executescript`,
            # which issues its own COMMIT and would therefore split a migration from the
            # row recording it. SQLite DDL is transactional, so this way a failed
            # migration leaves no half-built schema and no bookkeeping row.
            with self.transaction() as connection:
                for statement in _split_statements(path.read_text(encoding="utf-8")):
                    connection.execute(statement)
                connection.execute(
                    "INSERT INTO schema_migrations (name) VALUES (?)", (path.name,)
                )

    def close(self) -> None:
        self._connection.close()

    class _Transaction:
        def __init__(self, connection: sqlite3.Connection) -> None:
            self._connection = connection

        def __enter__(self) -> sqlite3.Connection:
            self._connection.execute("BEGIN IMMEDIATE")
            return self._connection

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            if exc_type is None:
                self._connection.execute("COMMIT")
            else:
                self._connection.execute("ROLLBACK")

    def transaction(self) -> SqliteStore._Transaction:
        return SqliteStore._Transaction(self._connection)

    # -- revisions ------------------------------------------------------------

    def commit_revision(
        self, revision: Revision, *, created_at: str, events: Sequence[Event] = ()
    ) -> None:
        """Persist a revision and its events atomically.

        Idempotent: re-committing the same content-addressed revision is a no-op, which
        is what makes a retried tick safe.
        """
        with self.transaction() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO revisions "
                "(revision_id, book_id, branch_id, parent_revision_id, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    revision.revision_id,
                    revision.book_id,
                    revision.branch_id,
                    revision.parent_revision_id,
                    created_at,
                ),
            )
            for node in revision.nodes:
                version_id = node_version_id(node)
                connection.execute(
                    "INSERT OR IGNORE INTO node_versions (version_id, logical_id, kind, "
                    "position_key, parent_logical_id, title, content, content_sha256, "
                    "lock_kind, tombstoned, tombstone_reason, block_kind, block_payload) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        version_id,
                        node.logical_id,
                        node.kind.value,
                        node.position_key,
                        node.parent_logical_id,
                        node.title,
                        node.content,
                        node.content_sha256,
                        node.lock.value,
                        int(node.tombstoned),
                        node.tombstone_reason,
                        node.block_kind.value if node.block_kind else None,
                        json.dumps(node.block_payload, sort_keys=True)
                        if node.block_payload
                        else None,
                    ),
                )
                connection.execute(
                    "INSERT OR IGNORE INTO revision_nodes (revision_id, logical_id, version_id) "
                    "VALUES (?, ?, ?)",
                    (revision.revision_id, node.logical_id, version_id),
                )
            for event in events:
                self._insert_event(connection, event)

    def load_revision(self, revision_id: str) -> Revision:
        row = self._connection.execute(
            "SELECT * FROM revisions WHERE revision_id = ?", (revision_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"no revision {revision_id}")
        nodes = [
            self._node_from_row(node_row)
            for node_row in self._connection.execute(
                "SELECT node_versions.* FROM revision_nodes "
                "JOIN node_versions USING (version_id) WHERE revision_id = ? "
                "ORDER BY node_versions.position_key, node_versions.logical_id",
                (revision_id,),
            )
        ]
        restored = Revision(
            book_id=row["book_id"],
            branch_id=row["branch_id"],
            nodes=tuple(nodes),
            parent_revision_id=row["parent_revision_id"],
        )
        if restored.revision_id != revision_id:
            raise IntegrityFailure(
                f"revision {revision_id[:12]} rebuilt as {restored.revision_id[:12]}"
            )
        return restored

    def head(self, book_id: str, branch_id: str) -> Revision | None:
        row = self._connection.execute(
            "SELECT revision_id FROM revisions WHERE book_id = ? AND branch_id = ? "
            "ORDER BY created_at DESC, revision_id DESC LIMIT 1",
            (book_id, branch_id),
        ).fetchone()
        return None if row is None else self.load_revision(row["revision_id"])

    def lineage(self, revision_id: str) -> list[str]:
        """Ancestry from ``revision_id`` back to the root, newest first."""
        chain: list[str] = []
        current: str | None = revision_id
        while current is not None:
            chain.append(current)
            row = self._connection.execute(
                "SELECT parent_revision_id FROM revisions WHERE revision_id = ?", (current,)
            ).fetchone()
            if row is None:
                raise IntegrityFailure(f"lineage broken: {current[:12]} is missing")
            current = row["parent_revision_id"]
        return chain

    @staticmethod
    def _node_from_row(row: sqlite3.Row) -> Node:
        payload: dict[str, Any] = json.loads(row["block_payload"]) if row["block_payload"] else {}
        block_kind = BlockKind(row["block_kind"]) if row["block_kind"] else None
        return Node(
            logical_id=row["logical_id"],
            kind=NodeKind(row["kind"]),
            position_key=row["position_key"],
            parent_logical_id=row["parent_logical_id"],
            title=row["title"],
            content=row["content"],
            content_sha256=row["content_sha256"],
            lock=LockKind(row["lock_kind"]),
            tombstoned=bool(row["tombstoned"]),
            tombstone_reason=row["tombstone_reason"],
            block_kind=block_kind,
            block_payload=payload,
        )

    # -- events and outbox ----------------------------------------------------

    def append_events(self, events: Iterable[Event]) -> None:
        with self.transaction() as connection:
            for event in events:
                self._insert_event(connection, event)

    @staticmethod
    def _insert_event(connection: sqlite3.Connection, event: Event) -> None:
        envelope = event.to_contract()
        cursor = connection.execute(
            "INSERT OR IGNORE INTO events (idempotency_key, event_id, event_type, created_at, "
            "actor, project_id, book_id, branch_id, revision_id, causation_id, correlation_id, "
            "payload, payload_digest) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                envelope.idempotency_key,
                envelope.event_id,
                envelope.event_type.value,
                envelope.created_at,
                envelope.actor,
                envelope.project_id,
                envelope.book_id,
                envelope.branch_id,
                envelope.revision_id,
                envelope.causation_id,
                envelope.correlation_id,
                json.dumps(envelope.payload, sort_keys=True, ensure_ascii=False),
                envelope.payload_digest or "",
            ),
        )
        # Only enqueue an outbox row for a genuinely new event; a duplicate delivery must
        # not resurrect an already-dispatched one.
        if cursor.rowcount:
            connection.execute(
                "INSERT OR IGNORE INTO outbox (idempotency_key, state) VALUES (?, ?)",
                (envelope.idempotency_key, OutboxState.PENDING.value),
            )

    def read_log(self, *, since: int = 0) -> list[StoredEvent]:
        return [
            StoredEvent(sequence=row["sequence"], event=self._event_from_row(row))
            for row in self._connection.execute(
                "SELECT * FROM events WHERE sequence > ? ORDER BY sequence", (since,)
            )
        ]

    @staticmethod
    def _event_from_row(row: sqlite3.Row) -> Event:
        return Event(
            event_type=EventType(row["event_type"]),
            project_id=row["project_id"],
            created_at=row["created_at"],
            actor=row["actor"],
            book_id=row["book_id"],
            branch_id=row["branch_id"],
            revision_id=row["revision_id"],
            causation_id=row["causation_id"],
            correlation_id=row["correlation_id"],
            payload=json.loads(row["payload"]),
        )

    def pending_outbox(self, limit: int = 100) -> list[OutboxEntry]:
        rows = self._connection.execute(
            "SELECT outbox.idempotency_key, outbox.state, outbox.delivery_attempts, events.* "
            "FROM outbox JOIN events USING (idempotency_key) WHERE outbox.state = ? "
            "ORDER BY events.sequence LIMIT ?",
            (OutboxState.PENDING.value, limit),
        ).fetchall()
        return [
            OutboxEntry(
                idempotency_key=row["idempotency_key"],
                event=self._event_from_row(row),
                state=OutboxState(row["state"]),
                delivery_attempts=row["delivery_attempts"],
            )
            for row in rows
        ]

    def mark_sent(self, idempotency_key: str) -> None:
        """Called only after delivery succeeded — send-then-mark, never the reverse."""
        with self.transaction() as connection:
            connection.execute(
                "UPDATE outbox SET state = ?, delivery_attempts = delivery_attempts + 1 "
                "WHERE idempotency_key = ?",
                (OutboxState.SENT.value, idempotency_key),
            )

    def record_delivery_attempt(self, idempotency_key: str) -> None:
        with self.transaction() as connection:
            connection.execute(
                "UPDATE outbox SET delivery_attempts = delivery_attempts + 1 "
                "WHERE idempotency_key = ?",
                (idempotency_key,),
            )

    # -- jobs -----------------------------------------------------------------

    def enqueue(self, job: Job) -> None:
        with self.transaction() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO jobs (job_id, job_kind, status, attempts, max_attempts, "
                "idempotency_key, input_digest, error, lease_holder, lease_expires_at, "
                "payload, priority) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    job.job_id,
                    job.job_kind,
                    job.status.value,
                    job.attempts,
                    job.max_attempts,
                    job.idempotency_key,
                    job.input_digest,
                    job.error,
                    job.lease_holder,
                    job.lease_expires_at,
                    _dump_payload(job.payload),
                    job.priority,
                ),
            )

    def save_job(self, job: Job) -> None:
        with self.transaction() as connection:
            connection.execute(
                "UPDATE jobs SET status = ?, attempts = ?, error = ?, lease_holder = ?, "
                "lease_expires_at = ? WHERE job_id = ?",
                (
                    job.status.value,
                    job.attempts,
                    job.error,
                    job.lease_holder,
                    job.lease_expires_at,
                    job.job_id,
                ),
            )

    def load_job(self, job_id: str) -> Job:
        row = self._connection.execute(
            "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"no job {job_id}")
        return self._job_from_row(row)

    @staticmethod
    def _job_from_row(row: sqlite3.Row) -> Job:
        return Job(
            job_id=row["job_id"],
            job_kind=row["job_kind"],
            status=JobStatus(row["status"]),
            attempts=row["attempts"],
            max_attempts=row["max_attempts"],
            idempotency_key=row["idempotency_key"],
            input_digest=row["input_digest"],
            error=row["error"],
            lease_holder=row["lease_holder"],
            lease_expires_at=row["lease_expires_at"],
            payload=json.loads(row["payload"]) if row["payload"] else {},
            priority=row["priority"],
        )

    def claim_next(self, holder: str, now: float, duration: float) -> Job | None:
        """Claim one queued job whose lease is free or expired, atomically.

        The claim and the lease write happen in a single IMMEDIATE transaction, so two
        Conductor instances racing on the same tick cannot both win.

        Order is `(priority DESC, rowid)`. While every job sits at the default priority
        of 0 this is byte-identical to the FIFO it replaces — which is the point: it makes
        a non-FIFO policy *expressible* (§4.1) without inventing one. Before this, no
        ordering other than insertion order could be written at any layer, so
        `fifo_selector`'s docstring understated its own constraint.
        """
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE status = ? "
                "AND (lease_expires_at IS NULL OR lease_expires_at <= ?) "
                "ORDER BY priority DESC, rowid LIMIT 1",
                (JobStatus.QUEUED.value, now),
            ).fetchone()
            if row is None:
                return None
            job = self._job_from_row(row).claim(holder, now, duration)
            connection.execute(
                "UPDATE jobs SET lease_holder = ?, lease_expires_at = ? WHERE job_id = ?",
                (job.lease_holder, job.lease_expires_at, job.job_id),
            )
            return job

    def reclaim_expired(self, now: float) -> list[Job]:
        """Requeue jobs left RUNNING by a crashed holder whose lease has expired.

        This is crash recovery for the in-flight unit (§19): a process that died mid-job
        leaves the row RUNNING forever, and nothing else will ever pick it up because
        `claim_next` only looks at QUEUED. Attempts are already counted, so a job that has
        exhausted its budget poisons here rather than cycling.
        """
        rows = self._connection.execute(
            "SELECT * FROM jobs WHERE status = ? AND lease_expires_at IS NOT NULL "
            "AND lease_expires_at <= ? ORDER BY rowid",
            (JobStatus.RUNNING.value, now),
        ).fetchall()
        reclaimed: list[Job] = []
        for row in rows:
            job = self._job_from_row(row).released()
            if job.attempts >= job.max_attempts:
                recovered = job.transition_to(
                    JobStatus.POISONED, error="lease expired; attempt budget exhausted"
                )
            else:
                recovered = job.transition_to(JobStatus.QUEUED, error="lease expired; requeued")
            self.save_job(recovered)
            reclaimed.append(recovered)
        return reclaimed

    def requeue_failed(self) -> list[Job]:
        """Bounded retry: requeue FAILED jobs with budget left, poison the rest.

        Without this a FAILED job is inert — `claim_next` only sees QUEUED, so nothing ever
        retries it and nothing ever poisons it either. It simply sits at FAILED forever,
        which looks like a parked unit but is really a lost one: no retry, no escalation, no
        terminal state. §4.2's retry ladder needs this step to exist at all.

        Retries are immediate (next tick) rather than backed off. The attempt budget is what
        bounds them; a `next_attempt_at` column would add backoff and is deliberately not
        invented here, since nothing yet needs a specific delay.
        """
        rows = self._connection.execute(
            "SELECT * FROM jobs WHERE status = ? ORDER BY rowid", (JobStatus.FAILED.value,)
        ).fetchall()
        moved: list[Job] = []
        for row in rows:
            job = self._job_from_row(row).released()
            if job.attempts >= job.max_attempts:
                recovered = job.transition_to(
                    JobStatus.POISONED, error=job.error or "attempt budget exhausted"
                )
            else:
                recovered = job.transition_to(JobStatus.QUEUED, error=job.error)
            self.save_job(recovered)
            moved.append(recovered)
        return moved

    def queued_count(self) -> int:
        row = self._connection.execute(
            "SELECT COUNT(*) AS n FROM jobs WHERE status = ?", (JobStatus.QUEUED.value,)
        ).fetchone()
        return int(row["n"])

    # -- instance lease -------------------------------------------------------

    def acquire_instance_lease(
        self, scope: str, holder: str, now: float, duration: float
    ) -> bool:
        """Claim the Conductor role for ``scope``. False means someone else holds it.

        A single IMMEDIATE transaction, so two overlapping cron invocations cannot both
        win. Re-claiming while still holding is allowed and extends the lease, which is
        what makes a long tick able to renew rather than losing its own role.
        """
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT holder, expires_at FROM instance_leases WHERE scope = ?", (scope,)
            ).fetchone()
            if row is not None and row["expires_at"] > now and row["holder"] != holder:
                return False
            connection.execute(
                "INSERT INTO instance_leases (scope, holder, expires_at, acquired_at) "
                "VALUES (?, ?, ?, ?) ON CONFLICT (scope) DO UPDATE SET "
                "holder = excluded.holder, expires_at = excluded.expires_at, "
                "acquired_at = excluded.acquired_at",
                (scope, holder, now + duration, now),
            )
            return True

    def release_instance_lease(self, scope: str, holder: str) -> None:
        with self.transaction() as connection:
            connection.execute(
                "DELETE FROM instance_leases WHERE scope = ? AND holder = ?", (scope, holder)
            )

    def instance_lease_holder(self, scope: str, now: float) -> str | None:
        row = self._connection.execute(
            "SELECT holder FROM instance_leases WHERE scope = ? AND expires_at > ?",
            (scope, now),
        ).fetchone()
        return None if row is None else str(row["holder"])

    # -- digest and ticks -----------------------------------------------------

    # -- directives -----------------------------------------------------------

    def submit_directive(self, directive: Directive, *, received_at: str) -> bool:
        """Accept one directive into the inbox. False if it was already submitted.

        Deliberately separate from the tick: a director drops direction whenever they like,
        and the Conductor drains it when it next runs. Coupling the two would mean direction
        could only be given while the system was between ticks.
        """
        with self.transaction() as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO directives (directive_id, kind, body, status, "
                "book_id, branch_id, target_logical_ids, interpretation, "
                "produced_constraint_ids, received_at, ingested_at, interpreted_at, "
                "precedence, superseded_by, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?)",
                (
                    directive.directive_id,
                    directive.kind.value,
                    directive.body,
                    directive.status.value,
                    directive.book_id,
                    directive.branch_id,
                    json.dumps(list(directive.target_logical_ids)),
                    directive.interpretation,
                    json.dumps(list(directive.produced_constraint_ids)),
                    directive.received_at or received_at,
                    directive.interpreted_at,
                    directive.precedence,
                    directive.superseded_by,
                    json.dumps(directive.metadata) if directive.metadata else None,
                ),
            )
            return cursor.rowcount > 0

    def pending_directives(self, limit: int = 50) -> list[Directive]:
        """Directives the Conductor has not yet ingested, in the order §4.3 wants them.

        Precedence leads and arrival order breaks ties, so a veto issued Monday outranks a
        tone note issued Tuesday. Recency ordering would silently reverse that.
        """
        return [
            _directive_from_row(row)
            for row in self._connection.execute(
                "SELECT * FROM directives WHERE ingested_at IS NULL "
                "ORDER BY precedence DESC, rowid LIMIT ?",
                (limit,),
            )
        ]

    def mark_directive_ingested(self, directive_id: str, *, ingested_at: str) -> None:
        with self.transaction() as connection:
            connection.execute(
                "UPDATE directives SET ingested_at = ? WHERE directive_id = ? "
                "AND ingested_at IS NULL",
                (ingested_at, directive_id),
            )

    def load_directive(self, directive_id: str) -> Directive:
        row = self._connection.execute(
            "SELECT * FROM directives WHERE directive_id = ?", (directive_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"no directive {directive_id}")
        return _directive_from_row(row)

    def directives_by_status(self, status: DirectiveStatus) -> list[Directive]:
        return [
            _directive_from_row(row)
            for row in self._connection.execute(
                "SELECT * FROM directives WHERE status = ? ORDER BY precedence DESC, rowid",
                (status.value,),
            )
        ]

    # -- policy decisions -----------------------------------------------------

    def record_decision(self, decision: PolicyDecision, *, decided_at: str) -> bool:
        """Persist one acceptance decision. False if this ``decision_id`` already exists.

        Idempotent by content-derived id, for the same reason ticks are: a job replayed
        after a crash must not accumulate duplicate rows for one judgment.
        """
        with self.transaction() as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO policy_decisions (decision_id, outcome, job_id, "
                "logical_id, base_revision_id, resulting_revision_id, attempt, provider, "
                "model, profile, fell_back_from, invocations, total_tokens, "
                "policy_config_digest, reason, gates, decided_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    decision.decision_id,
                    decision.outcome.value,
                    decision.job_id,
                    decision.logical_id,
                    decision.base_revision_id,
                    decision.resulting_revision_id,
                    decision.attempt,
                    decision.provider,
                    decision.model,
                    decision.profile,
                    json.dumps(list(decision.fell_back_from)),
                    decision.invocations,
                    decision.total_tokens,
                    decision.policy_config_digest,
                    decision.reason,
                    json.dumps([_gate_to_row(gate) for gate in decision.gates]),
                    decided_at,
                ),
            )
            return cursor.rowcount > 0

    def load_decision(self, decision_id: str) -> PolicyDecision:
        row = self._connection.execute(
            "SELECT * FROM policy_decisions WHERE decision_id = ?", (decision_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"no policy decision {decision_id}")
        return _decision_from_row(row)

    def decisions_for_job(self, job_id: str) -> list[PolicyDecision]:
        return [
            _decision_from_row(row)
            for row in self._connection.execute(
                "SELECT * FROM policy_decisions WHERE job_id = ? ORDER BY attempt, rowid",
                (job_id,),
            )
        ]

    def decision_for_revision(self, revision_id: str) -> PolicyDecision | None:
        """The decision that accepted ``revision_id``, if one was recorded.

        §19's integrity clause — "every mutation is attributable to a recorded policy
        decision" — is only checkable if this lookup exists.
        """
        row = self._connection.execute(
            "SELECT * FROM policy_decisions WHERE resulting_revision_id = ? "
            "ORDER BY rowid LIMIT 1",
            (revision_id,),
        ).fetchone()
        return None if row is None else _decision_from_row(row)

    def bump_digest(self, day: str, metric: str, value: int = 1) -> None:
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO digest_entries (day, metric, value) VALUES (?, ?, ?) "
                "ON CONFLICT (day, metric) DO UPDATE SET value = value + excluded.value",
                (day, metric, value),
            )

    def digest(self, day: str) -> dict[str, int]:
        return {
            row["metric"]: int(row["value"])
            for row in self._connection.execute(
                "SELECT metric, value FROM digest_entries WHERE day = ? ORDER BY metric", (day,)
            )
        }

    def record_tick(
        self,
        *,
        tick_id: str,
        holder: str,
        started_at: float,
        outcome: str,
        job_id: str | None,
        reconciled: int,
        dispatched: int,
    ) -> bool:
        """Persist a tick. False if this ``tick_id`` was already recorded.

        Tick ids are derived from (holder, instant), so replaying the same tick is a no-op
        rather than a second row — the property the endurance run depends on.
        """
        with self.transaction() as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO tick_records (tick_id, holder, started_at, outcome, "
                "job_id, reconciled, dispatched) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (tick_id, holder, started_at, outcome, job_id, reconciled, dispatched),
            )
            return bool(cursor.rowcount)

    def tick_count(self) -> int:
        row = self._connection.execute("SELECT COUNT(*) AS n FROM tick_records").fetchone()
        return int(row["n"])

    # -- integrity ------------------------------------------------------------

    def verify_integrity(self) -> int:
        """Rebuild every revision from canonical records. Returns the count verified.

        This is §19's recovery clause as an assertion: node content hashes are recomputed
        by `Node.__post_init__` and revision ids by `Revision.__post_init__`, so a single
        altered character anywhere in storage fails here.
        """
        rows = self._connection.execute("SELECT revision_id FROM revisions").fetchall()
        for row in rows:
            self.load_revision(row["revision_id"])
        orphans = self._connection.execute(
            "SELECT COUNT(*) AS n FROM revision_nodes "
            "WHERE version_id NOT IN (SELECT version_id FROM node_versions)"
        ).fetchone()["n"]
        if orphans:
            raise IntegrityFailure(f"{orphans} revision_nodes rows reference missing versions")
        unlogged = self._connection.execute(
            "SELECT COUNT(*) AS n FROM outbox "
            "WHERE idempotency_key NOT IN (SELECT idempotency_key FROM events)"
        ).fetchone()["n"]
        if unlogged:
            raise IntegrityFailure(f"{unlogged} outbox rows have no event")
        return len(rows)
