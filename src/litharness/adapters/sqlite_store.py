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
import weakref
from collections.abc import Collection, Iterable, Sequence
from contextlib import suppress
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

import litharness_contracts as lc

from litharness.adapters.sqlite_errors import (
    IntegrityFailure as IntegrityFailure,
)
from litharness.adapters.sqlite_errors import (
    MigrationsMissing as MigrationsMissing,
)
from litharness.adapters.sqlite_jobs import SqliteJobRepository
from litharness.adapters.sqlite_plans import SqlitePlanRepository
from litharness.domain.audit import AuditSample, Verdict
from litharness.domain.budget import Spend
from litharness.domain.calibration import (
    Calibration,
    Direction,
    EvidenceClass,
    Grain,
    Population,
)
from litharness.domain.craft import CraftMetric
from litharness.domain.directives import Directive, DirectiveKind, DirectiveStatus
from litharness.domain.events import (
    MAX_DELIVERY_ATTEMPTS,
    Event,
    EventType,
    OutboxEntry,
    OutboxState,
    delivery_backoff,
)
from litharness.domain.exceptions import ExceptionKind, ExceptionRecord, ExceptionStatus
from litharness.domain.findings import UNRESOLVED_STATUSES
from litharness.domain.findings import Finding as DomainFinding
from litharness.domain.findings import Severity as DomainSeverity
from litharness.domain.findings import Status as FindingStatus
from litharness.domain.jobs import Job, JobStatus
from litharness.domain.nodes import BlockKind, LockKind, Node, NodeKind
from litharness.domain.patch import Veto
from litharness.domain.plan_refinement import (
    PlanApplication,
    PlanRevision,
    StoredPlanProposal,
)
from litharness.domain.policy import (
    GateKind,
    GateOutcome,
    Outcome,
    PolicyDecision,
    VerdictSource,
)
from litharness.domain.revision import Revision, node_version_id

#: How long a writer waits for a contended database before reporting it locked. Two
#: overlapping cron ticks contend on `BEGIN IMMEDIATE` by design (§4.1), so this is the
#: scheduler's tolerance, not a library default.
BUSY_TIMEOUT_MS = 5000


def migrations_dir() -> Path:
    """Locate the migration set for whichever install layout is in play.

    Two layouts, and only one of them was handled. Under an editable install the SQL sits
    at the repo root, three parents up from this module. In a wheel, `pyproject.toml`'s
    `force-include` places it at `litharness/migrations` — one parent up. The hardcoded
    repo-root path therefore resolved to nothing at all once installed, and because
    `migrate` globbed an empty directory and returned cleanly, the result was a store with
    no tables rather than an error. Prefer the packaged location, fall back to the repo.
    """
    packaged = Path(__file__).resolve().parents[1] / "migrations"
    if any(packaged.glob("*.sql")):
        return packaged
    return Path(__file__).resolve().parents[3] / "migrations"


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


def _exception_from_row(row: sqlite3.Row) -> ExceptionRecord:
    return ExceptionRecord(
        exception_id=row["exception_id"],
        kind=ExceptionKind(row["kind"]),
        summary=row["summary"],
        status=ExceptionStatus(row["status"]),
        job_id=row["job_id"],
        logical_id=row["logical_id"],
        decision_id=row["decision_id"],
        raised_at=row["raised_at"],
        resolved_at=row["resolved_at"],
        resolution=row["resolution"],
        attempts=row["attempts"],
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
        cost_usd=row["cost_usd"],
        policy_config_digest=row["policy_config_digest"],
        reason=row["reason"],
    )


@dataclass(frozen=True, slots=True)
class StoredEvent:
    sequence: int
    event: Event


class SqliteStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        # The finalizer owns the native handle without retaining this store. Explicit
        # context management calls it early; legacy short-lived call sites still close as
        # soon as the wrapper becomes unreachable, including through reference cycles.
        self._finalizer = weakref.finalize(self, connection.close)
        transaction = partial(SqliteStore._Transaction, connection)
        self._jobs = SqliteJobRepository(connection, transaction)
        self._plans = SqlitePlanRepository(
            connection,
            transaction,
            insert_event=SqliteStore._insert_event,
            insert_decision=SqliteStore._insert_decision,
            decode_directive=_directive_from_row,
            jobs=self._jobs,
        )

    # -- lifecycle ------------------------------------------------------------

    @classmethod
    def open(cls, path: str | Path, *, migrations: Path | None = None) -> SqliteStore:
        connection = sqlite3.connect(str(path), isolation_level=None)
        try:
            connection.row_factory = sqlite3.Row
            # `journal_mode=WAL` is the first statement that touches the file's header, so
            # it is where a corrupted database announces itself — before `migrate` runs.
            # That is why the guard starts here and not around the migration alone.
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA synchronous=FULL")
            # Explicit rather than inherited. Python's default is 5s, which is fine, but a
            # scheduler's tolerance for a busy database is a decision the scheduler should
            # own: two overlapping cron ticks contend on `BEGIN IMMEDIATE` by design, and
            # how long the loser waits before reporting it locked belongs here, in writing.
            connection.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
            store = cls(connection)
            store.migrate(migrations or migrations_dir())
        except BaseException:
            # A failed open must not leave the file handle behind, and it matters most in
            # exactly the case that matters most: opening a corrupted database to diagnose
            # it, where a leaked handle blocks the operator from replacing the file with a
            # backup — on Windows, actively so.
            connection.close()
            raise
        return store

    def migrate(self, directory: Path) -> None:
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(name TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )
        applied = {
            row["name"] for row in self._connection.execute("SELECT name FROM schema_migrations")
        }
        available = sorted(directory.glob("*.sql"))
        if not available:
            # An empty migration set is never legitimate, and silence here is the worst
            # available failure: `migrate` would return cleanly, `open` would hand back a
            # store with no tables, and the first write would fail with "no such table"
            # somewhere far from the cause. On a restored host it would look like data loss.
            raise MigrationsMissing(
                f"no .sql migrations found in {directory}; the store cannot be opened "
                "against an empty schema. Check the package layout — under an editable "
                "install the migrations sit beside the repo root, and in a wheel they are "
                "force-included at litharness/migrations."
            )
        for path in available:
            if path.name in applied:
                continue
            # Statements are executed individually rather than through `executescript`,
            # which issues its own COMMIT and would therefore split a migration from the
            # row recording it. SQLite DDL is transactional, so this way a failed
            # migration leaves no half-built schema and no bookkeeping row.
            with self.transaction() as connection:
                for statement in _split_statements(path.read_text(encoding="utf-8")):
                    connection.execute(statement)
                connection.execute("INSERT INTO schema_migrations (name) VALUES (?)", (path.name,))

    def backup_to(self, destination: str | Path) -> None:
        """Take an online, consistent backup. §18 keeps backups absolutely.

        **This must use SQLite's backup API, not a file copy**, and the reason is specific
        to this store: it runs in WAL mode, so committed data lives partly in the `-wal`
        sidecar until a checkpoint. Copying the main database file — the obvious thing an
        operator reaches for, and what a naive `shutil.copy` in a cron job would do —
        silently omits everything committed since the last checkpoint. The backup API
        walks the pages under a read lock and produces a file that is a database.

        Safe against the two mistakes that make a backup worthless: backing up onto the
        live database, and overwriting a previous backup that was the only good copy.
        """
        target = Path(destination)
        if target.resolve() == Path(self.path).resolve():
            raise ValueError("backup destination must differ from the active database")
        if target.exists():
            raise FileExistsError(f"backup destination already exists: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        backup = sqlite3.connect(str(target))
        try:
            self._connection.backup(backup)
        finally:
            backup.close()

    @property
    def path(self) -> str:
        """Filesystem path of the open database, or ':memory:'."""
        row = self._connection.execute("PRAGMA database_list").fetchone()
        return str(row["file"] or ":memory:")

    def close(self) -> None:
        self._finalizer()

    def __enter__(self) -> SqliteStore:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    class _Transaction:
        def __init__(self, connection: sqlite3.Connection) -> None:
            self._connection = connection

        def __enter__(self) -> sqlite3.Connection:
            self._connection.execute("BEGIN IMMEDIATE")
            return self._connection

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            if exc_type is None:
                self._connection.execute("COMMIT")
                return
            # SQLite auto-rolls-back on some errors — a full disk is the realistic one —
            # and the explicit ROLLBACK then raises "cannot rollback - no transaction is
            # active", *replacing* the real exception on its way out. The operator was told
            # the rollback failed and never told the disk was full. Suppressing this one
            # lets the original error propagate intact; the transaction is already undone.
            with suppress(sqlite3.Error):
                self._connection.execute("ROLLBACK")

    def transaction(self) -> SqliteStore._Transaction:
        return SqliteStore._Transaction(self._connection)

    # -- revisions ------------------------------------------------------------

    def commit_revision(
        self,
        revision: Revision,
        *,
        created_at: str,
        events: Sequence[Event] = (),
        state_records: Sequence[lc.StateRecord] = (),
        retract_state_from: Collection[str] = (),
        retract_state_for_nodes: Collection[str] = (),
        jobs: Sequence[Job] = (),
        decision: PolicyDecision | None = None,
    ) -> None:
        """Persist a revision, its events and the state read out of it, atomically.

        Idempotent: re-committing the same content-addressed revision is a no-op, which
        is what makes a retried tick safe.

        `state_records` is §12 step 5's output arriving through step 8's transaction. It
        defaults to empty so `revert` and every existing caller are unchanged, and it is a
        parameter here rather than a second store call in the handler for the reason
        `plan/stage-0-decisions.md` §6 gives: a handler must not write to the store, and the
        one carve-out is this method, which takes its events in the same transaction. Widening
        the carve-out would put records for prose that may never commit into the store with no
        way to recall them under `INSERT OR IGNORE`; writing *after* the commit instead is
        unreachable on replay, because the handler returns early when a prior ACCEPT decision
        exists. Records therefore inherit the revision's crash semantics exactly: **they
        cannot exist for a revision that does not.**
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
            # Atomic with the head move, for the reason the head move is atomic with the
            # revision: a crash between them would leave canon read out of prose the book no
            # longer contains, which is exactly the orphan retraction exists to prevent.
            for source_revision_id in sorted(retract_state_from):
                connection.execute(
                    "UPDATE state_records SET retracted_by_revision_id = ?, retracted_at = ? "
                    "WHERE book_id = ? AND branch_id = ? AND source_revision_id = ? "
                    "AND retracted_by_revision_id IS NULL",
                    (
                        revision.revision_id,
                        created_at,
                        revision.book_id,
                        revision.branch_id,
                        source_revision_id,
                    ),
                )
            for logical_id in sorted(retract_state_for_nodes):
                connection.execute(
                    "UPDATE state_records SET retracted_by_revision_id = ?, retracted_at = ? "
                    "WHERE book_id = ? AND branch_id = ? "
                    "AND retracted_by_revision_id IS NULL AND EXISTS ("
                    "SELECT 1 FROM json_each(state_records.record_json, '$.evidence') "
                    "AS evidence WHERE json_extract("
                    "evidence.value, '$.source.logical_id') = ?)",
                    (
                        revision.revision_id,
                        created_at,
                        revision.book_id,
                        revision.branch_id,
                        logical_id,
                    ),
                )
            for record in state_records:
                self._insert_state_record(
                    connection,
                    revision.book_id,
                    revision.branch_id,
                    record,
                    source_revision_id=revision.revision_id,
                    created_at=created_at,
                    restore_retracted=bool(retract_state_for_nodes),
                )
            for event in events:
                self._insert_event(connection, event)
            if decision is not None:
                self._insert_decision(connection, decision, decided_at=created_at)
            for job in jobs:
                self._jobs.insert_job(connection, job)
            # The head moves in the same transaction as the revision it points at, so a
            # crash cannot leave a revision that exists but is not the head, or a head
            # pointing at nothing. `revert` relies on this: it commits a revision whose
            # content is older than the one it replaces, and only an explicit pointer can
            # express that.
            connection.execute(
                "INSERT INTO branch_heads (book_id, branch_id, revision_id, updated_at) "
                "VALUES (?, ?, ?, ?) ON CONFLICT (book_id, branch_id) DO UPDATE SET "
                "revision_id = excluded.revision_id, updated_at = excluded.updated_at",
                (revision.book_id, revision.branch_id, revision.revision_id, created_at),
            )

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
        """The current head of a branch.

        A stored pointer, updated on every commit, rather than the newest `created_at`.
        Inferring it by timestamp made "make revision R the head again" inexpressible —
        §19's Integrity clause says every mutation is attributable *and reversible*, and
        the second half needs somewhere for the answer to live. It also made the head
        depend on a clock: two commits in the same second resolved by lexical id.
        """
        row = self._connection.execute(
            "SELECT revision_id FROM branch_heads WHERE book_id = ? AND branch_id = ?",
            (book_id, branch_id),
        ).fetchone()
        return None if row is None else self.load_revision(row["revision_id"])

    def revert(
        self,
        book_id: str,
        branch_id: str,
        target_revision_id: str,
        *,
        created_at: str,
        project_id: str,
        actor: str = "litharness",
        events: Sequence[Event] = (),
    ) -> Revision:
        """Restore ``target_revision_id``'s content as a new head. §19's reversibility.

        Forward, never backward: the mistake and the correction both stay in the record.
        Committing and moving the head happen in one transaction, so a crash cannot leave
        a revision that exists but is not the head, or a head pointing at nothing.

        **The decision is minted here rather than asked of the caller, because attribution
        must not be optional.** §19's Integrity clause is one sentence — every mutation is
        attributable to a recorded policy decision *and reversible* — and the reversibility
        half shipped violating the attribution half: this method took `events` with a
        default of `()`, wrote no decision, and `cmd_revert` passed neither. A revert
        therefore committed a revision, moved `branch_heads`, and left
        `decision_for_revision` answering `None`. "Zero silent mutation" is a literal Stage
        1 exit criterion in §17, and this was the one silent mutation in the shipped system.

        Nothing here is a policy judgment — the outcome, the base, the result and the reason
        are all determined by the arguments — so there was no reason to make the caller
        supply what only they could get wrong or forget. The caller's `events` are still
        appended, for anything it wants to say beyond the acceptance.
        """
        current = self.head(book_id, branch_id)
        if current is None:
            raise KeyError(f"no head for {book_id}/{branch_id}")
        reverted = current.reverting_to(self.load_revision(target_revision_id))

        decision = PolicyDecision(
            # Derived, so re-reverting to the same target from the same head collapses onto
            # one decision rather than accumulating duplicates of one judgment.
            decision_id=f"dec-revert-{reverted.revision_id[:20]}",
            outcome=Outcome.ACCEPT,
            base_revision_id=current.revision_id,
            resulting_revision_id=reverted.revision_id,
            reason=(
                f"reverted to {target_revision_id[:12]}, replacing head {current.revision_id[:12]}"
            ),
        )
        accepted = Event(
            event_type=EventType.MANUSCRIPT_REVISION_ACCEPTED,
            project_id=project_id,
            created_at=created_at,
            actor=actor,
            book_id=book_id,
            branch_id=branch_id,
            revision_id=reverted.revision_id,
            payload={
                "decision_id": decision.decision_id,
                "reverted_to": target_revision_id,
                "parent_revision_id": current.revision_id,
                "accepted": True,
            },
        )
        # Decision first, then the revision — the order the draft handler and the importer
        # both use. A crash between them leaves a decision pointing at a revision that does
        # not exist, which is detectable and harmless; the other order leaves a revision no
        # decision explains, which is the thing this method exists to stop producing.
        self.record_decision(decision, decided_at=created_at)
        # The revisions this revert discards, computed *before* the head moves — afterwards
        # they are ancestors of the new head and indistinguishable from kept history, because
        # `reverting_to` parents on the current head. Any state record read out of prose in
        # that segment leaves the book with it.
        discarded = set(self.lineage(current.revision_id)) - set(self.lineage(target_revision_id))
        self.commit_revision(
            reverted,
            created_at=created_at,
            events=[accepted, *events],
            retract_state_from=discarded,
        )
        return reverted

    def unattributed_revisions(self) -> list[str]:
        """Revisions that no policy decision explains — §19's Integrity clause, as a query.

        The clause was asserted rather than checked, and it was false: `revert` produced
        unattributed revisions for as long as it existed, and nothing anywhere would have
        said so. A structural constraint on one method only guards that method; this guards
        every path, including ones not written yet.
        """
        return [
            row["revision_id"]
            for row in self._connection.execute(
                "SELECT revision_id FROM revisions WHERE revision_id NOT IN "
                "(SELECT resulting_revision_id FROM policy_decisions "
                "WHERE resulting_revision_id IS NOT NULL) ORDER BY rowid"
            )
        ]

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

    def pending_outbox(self, limit: int = 100, *, now: float | None = None) -> list[OutboxEntry]:
        """Entries due for delivery, oldest first.

        `now` filters out entries still inside their backoff window. It defaults to None —
        meaning "everything pending, ignore backoff" — because that is what an operator
        inspecting the queue wants and what most tests assert against. The Conductor always
        passes it; a drain that ignored backoff would reintroduce the spin.
        """
        if now is None:
            rows = self._connection.execute(
                "SELECT outbox.idempotency_key, outbox.state, outbox.delivery_attempts, "
                "events.* FROM outbox JOIN events USING (idempotency_key) "
                "WHERE outbox.state = ? ORDER BY events.sequence LIMIT ?",
                (OutboxState.PENDING.value, limit),
            ).fetchall()
        else:
            rows = self._connection.execute(
                "SELECT outbox.idempotency_key, outbox.state, outbox.delivery_attempts, "
                "events.* FROM outbox JOIN events USING (idempotency_key) "
                "WHERE outbox.state = ? "
                "AND (outbox.next_attempt_at IS NULL OR outbox.next_attempt_at <= ?) "
                "ORDER BY events.sequence LIMIT ?",
                (OutboxState.PENDING.value, now, limit),
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

    def record_delivery_attempt(self, idempotency_key: str, *, now: float) -> bool:
        """Record a refused delivery, back it off, and park it once the budget is spent.

        Returns True if the entry is now terminal. The event itself is never lost — it
        stays in `events`, which is the durable log. What stops is the *delivery*, which is
        the right thing to bound: a sink that has refused eleven times across an hour of
        backoff will not accept the twelfth, and continuing to ask costs a synchronous
        write per entry per tick, forever.
        """
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT delivery_attempts FROM outbox WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if row is None:
                return False
            attempts = int(row["delivery_attempts"]) + 1
            if attempts >= MAX_DELIVERY_ATTEMPTS:
                connection.execute(
                    "UPDATE outbox SET delivery_attempts = ?, state = ?, next_attempt_at = NULL "
                    "WHERE idempotency_key = ?",
                    (attempts, OutboxState.FAILED.value, idempotency_key),
                )
                return True
            connection.execute(
                "UPDATE outbox SET delivery_attempts = ?, next_attempt_at = ? "
                "WHERE idempotency_key = ?",
                (attempts, now + delivery_backoff(attempts), idempotency_key),
            )
            return False

    def outbox_counts_by_state(self) -> dict[str, int]:
        return {
            row["state"]: int(row["n"])
            for row in self._connection.execute(
                "SELECT state, COUNT(*) AS n FROM outbox GROUP BY state ORDER BY state"
            )
        }

    # -- jobs -----------------------------------------------------------------

    def enqueue(self, job: Job) -> bool:
        """Queue a unit of work. False if this `job_id` or idempotency key already existed.

        The return value is not decoration. `INSERT OR IGNORE` means a planner that mints a
        derived job id gets silence when the id was already used — including when the work
        it names was poisoned and its key burned. Reporting "planned" for a write that did
        nothing is how a loop convinces itself it is making progress while the queue stays
        empty, so callers that plan must branch on this.
        """
        return self._jobs.enqueue(job)

    def save_job(self, job: Job) -> None:
        self._jobs.save_job(job)

    def load_job(self, job_id: str) -> Job:
        return self._jobs.load_job(job_id)

    def claim_next(self, holder: str, now: float, duration: float) -> Job | None:
        """Claim one queued job whose lease is free or expired, atomically.

        The claim and the lease write happen in a single IMMEDIATE transaction, so two
        Conductor instances racing on the same tick cannot both win.

        Order is `(priority DESC, rowid)`. It shipped byte-identical to the FIFO it replaced,
        because every job then sat at the default of 0 — the point being to make a non-FIFO
        policy *expressible* (§4.1) without inventing one, since before this no ordering other
        than insertion order could be written at any layer. **Four bands now use it**:
        explicit direction at 1000 + precedence, interpretive direction at 500 + precedence,
        repair at 100, evaluation at 80, and scene drafts at the default. So this is no longer
        FIFO in practice, and a reader reasoning about claim order from the old sentence would
        get the answer wrong for every book with direction or repairs in flight.
        """
        return self._jobs.claim_next(holder, now, duration)

    def reclaim_expired(self, now: float) -> list[Job]:
        """Requeue jobs left RUNNING by a crashed holder whose lease has expired.

        This is crash recovery for the in-flight unit (§19): a process that died mid-job
        leaves the row RUNNING forever, and nothing else will ever pick it up because
        `claim_next` only looks at QUEUED. Attempts are already counted, so a job that has
        exhausted its budget poisons here rather than cycling.
        """
        return self._jobs.reclaim_expired(now)

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
        return self._jobs.requeue_failed()

    def queued_count(self) -> int:
        return self._jobs.queued_count()

    # -- plan ------------------------------------------------------------------

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
        """Store plan statements. Returns how many rows were new.

        `INSERT OR IGNORE` keyed on (book, branch, logical_id), so re-importing the same
        fixture is a no-op rather than a duplicate — the same idempotency every other write
        in this store has. A complete imported plan also becomes the immutable root
        revision. Incomplete legacy imports remain readable but cannot be refined.
        """
        return self._plans.record_plan_items(
            book_id,
            branch_id,
            items,
            created_at=created_at,
            source_revision_id=source_revision_id,
            events=events,
        )

    def plan_items(
        self, book_id: str, branch_id: str, *, kind: lc.PlanKind | None = None
    ) -> list[lc.PlanItem]:
        return self._plans.plan_items(book_id, branch_id, kind=kind)

    @staticmethod
    def _legacy_plan_revision(
        connection: sqlite3.Connection, book_id: str, branch_id: str
    ) -> PlanRevision | None:
        return SqlitePlanRepository.legacy_plan_revision(connection, book_id, branch_id)

    @staticmethod
    def _plan_head(
        connection: sqlite3.Connection, book_id: str, branch_id: str
    ) -> PlanRevision | None:
        return SqlitePlanRepository.plan_head(connection, book_id, branch_id)

    @staticmethod
    def _insert_plan_revision(
        connection: sqlite3.Connection,
        revision: PlanRevision,
        *,
        created_at: str,
        proposal_id: str | None = None,
    ) -> None:
        SqlitePlanRepository.insert_plan_revision(
            connection,
            revision,
            created_at=created_at,
            proposal_id=proposal_id,
        )

    def plan_revision(self, book_id: str, branch_id: str) -> PlanRevision | None:
        """Current immutable plan snapshot, bootstrapped from a legacy import if needed."""
        return self._plans.plan_revision(book_id, branch_id)

    def load_plan_revision(self, plan_revision_id: str) -> PlanRevision:
        return self._plans.load_plan_revision(plan_revision_id)

    def plan_revision_for_id(self, plan_revision_id: str) -> PlanRevision:
        """Load a persisted revision or the matching not-yet-bootstrapped legacy root."""
        return self._plans.plan_revision_for_id(plan_revision_id)

    def plan_history(self, book_id: str, branch_id: str) -> list[PlanRevision]:
        """Return head-first lineage; a rollback is another child, never deletion."""
        return self._plans.plan_history(book_id, branch_id)

    def load_plan_proposal(self, proposal_id: str) -> StoredPlanProposal:
        return self._plans.load_plan_proposal(proposal_id)

    def plan_proposals(self, book_id: str, branch_id: str) -> list[StoredPlanProposal]:
        """Every proposal against this branch, oldest first — what `plan_history` omits.

        A lineage says which snapshots existed; this says what was proposed and whether it
        landed. `litharness plans` reads them together, which is the only way "why is the
        plan like this" is answerable without opening the database.
        """
        return self._plans.plan_proposals(book_id, branch_id)

    def commit_plan_application(
        self,
        application: PlanApplication,
        *,
        created_at: str,
        interpreted_at: str,
        events: Sequence[Event],
        decision: PolicyDecision,
    ) -> None:
        """Commit plan movement, its decision, directive readings, and events as one unit."""
        self._plans.commit_plan_application(
            application,
            created_at=created_at,
            interpreted_at=interpreted_at,
            events=events,
            decision=decision,
        )

    # -- objective story state -------------------------------------------------

    def record_state_records(
        self,
        book_id: str,
        branch_id: str,
        records: Sequence[lc.StateRecord],
        *,
        created_at: str,
        source_revision_id: str | None = None,
        events: Sequence[Event] = (),
    ) -> int:
        """Store state records. Returns how many rows were new.

        `INSERT OR IGNORE` keyed on (book, branch, record_id), so re-importing the same
        snapshot is a no-op — the same idempotency every other write in this store has. A
        record whose *content* changed under an unchanged id is therefore not an update, and
        that is correct: §11 forbids canon being rewritten in place, and a fact that changed
        is a new record with new evidence, not the old one edited.
        """
        inserted = 0
        with self.transaction() as connection:
            for record in records:
                inserted += self._insert_state_record(
                    connection,
                    book_id,
                    branch_id,
                    record,
                    source_revision_id=source_revision_id,
                    created_at=created_at,
                )
            for event in events:
                self._insert_event(connection, event)
        return inserted

    @staticmethod
    def _insert_state_record(
        connection: sqlite3.Connection,
        book_id: str,
        branch_id: str,
        record: lc.StateRecord,
        *,
        source_revision_id: str | None,
        created_at: str,
        restore_retracted: bool = False,
    ) -> int:
        """One row, on a caller-supplied connection. Factored out so `commit_revision` can
        write extracted records **inside the revision's own transaction** rather than in a
        second one — §12 step 8 says the revision, its events and its records commit
        atomically, and two transactions is the gap where a crash leaves a drafted book with
        no record of what it established."""
        position = record.story_position.order_key if record.story_position else None
        conflict = (
            "ON CONFLICT (book_id, branch_id, record_id) DO UPDATE SET "
            "kind = excluded.kind, subject = excluded.subject, "
            "predicate = excluded.predicate, value_json = excluded.value_json, "
            "order_key = excluded.order_key, authority = excluded.authority, "
            "record_json = excluded.record_json, "
            "source_revision_id = excluded.source_revision_id, "
            "created_at = excluded.created_at, retracted_by_revision_id = NULL, "
            "retracted_at = NULL WHERE state_records.retracted_by_revision_id IS NOT NULL"
            if restore_retracted
            else "ON CONFLICT (book_id, branch_id, record_id) DO NOTHING"
        )
        cursor = connection.execute(
            "INSERT INTO state_records (book_id, branch_id, record_id, "
            "kind, subject, predicate, value_json, order_key, authority, "
            "record_json, source_revision_id, created_at) "
            f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) {conflict}",
            (
                book_id,
                branch_id,
                record.record_id,
                record.kind.value,
                record.subject,
                record.predicate,
                None
                if record.value is None
                else json.dumps(record.value, sort_keys=True, ensure_ascii=False),
                position,
                record.authority.value,
                json.dumps(lc.to_jsonable(record), sort_keys=True, ensure_ascii=False),
                source_revision_id,
                created_at,
            ),
        )
        return int(cursor.rowcount)

    def state_records(
        self,
        book_id: str,
        branch_id: str,
        *,
        subject: str | None = None,
        before: str | None = None,
    ) -> list[lc.StateRecord]:
        """Canon and proposals alike, in story order. Filtering to canon is the caller's.

        `before` slices on `order_key` and **keeps records with none**: an unplaced record
        asserts no narrative position, and treating that as "later than everything" would
        drop every standing world rule from every packet. `domain/state.py::records_before`
        applies the identical rule in memory, and the two are tested against each other —
        one query, two implementations is how a selector drifts from its gate.
        """
        # Retracted records are excluded everywhere by default, so a caller cannot forget:
        # a record read out of prose a `revert` removed from the book is not canon any more,
        # and leaving it visible makes a redraft of that scene contradict a ghost. Migration
        # 016 records the retraction rather than deleting the row — the mistake and the
        # correction both stay, which is the rule `revert` itself follows.
        sql = (
            "SELECT record_json FROM state_records WHERE book_id = ? AND branch_id = ? "
            "AND retracted_by_revision_id IS NULL"
        )
        params: list[Any] = [book_id, branch_id]
        if subject is not None:
            sql += " AND subject = ?"
            params.append(subject)
        if before is not None:
            sql += " AND (order_key IS NULL OR order_key <= ?)"
            params.append(before)
        # NULLs last, matching `in_story_order`. SQLite sorts NULL first by default, which
        # would put unplaced records ahead of scene one.
        sql += " ORDER BY order_key IS NULL, order_key, record_id"
        return [
            lc.from_jsonable(lc.StateRecord, json.loads(row["record_json"]))
            for row in self._connection.execute(sql, params)
        ]

    # -- findings --------------------------------------------------------------

    @staticmethod
    def _insert_finding(
        connection: sqlite3.Connection,
        book_id: str,
        branch_id: str,
        finding: DomainFinding,
        *,
        revision_id: str | None,
        created_at: str,
    ) -> int:
        cursor = connection.execute(
            "INSERT OR IGNORE INTO findings (finding_id, book_id, branch_id, "
            "revision_id, category, subtype, severity, status, rule_or_critic_id, "
            "logical_id, message, finding_json, run_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                finding.finding_id,
                book_id,
                branch_id,
                revision_id,
                finding.category,
                finding.subtype,
                finding.severity.value,
                finding.status.value,
                finding.rule_or_critic_id,
                finding.logical_id,
                finding.message,
                json.dumps(
                    {
                        "projection": {
                            "confidence_basis": finding.confidence_basis,
                            "run_id": finding.run_id,
                        },
                        "source": finding.source,
                    },
                    sort_keys=True,
                    ensure_ascii=False,
                ),
                finding.run_id,
                created_at,
            ),
        )
        return int(cursor.rowcount)

    def record_findings(
        self,
        book_id: str,
        branch_id: str,
        findings: Sequence[DomainFinding],
        *,
        created_at: str,
        revision_id: str | None = None,
        events: Sequence[Event] = (),
    ) -> int:
        """Store findings. Returns how many rows were new.

        `INSERT OR IGNORE` on the content-derived `finding_id`, so a detector re-run over an
        unchanged revision converges on one row instead of growing the queue every tick —
        the spin migration 006 had to fix in the outbox, refused here in advance.

        **A re-run does not reopen a finding a human closed.** `INSERT OR IGNORE` is what
        gives that for free: the existing row, with its `accepted_intentional` status, wins.
        An upsert would re-raise every negative control on every evaluation, which is the
        fastest way to make an operator stop reading the queue.
        """
        inserted = 0
        with self.transaction() as connection:
            for finding in findings:
                inserted += self._insert_finding(
                    connection,
                    book_id,
                    branch_id,
                    finding,
                    revision_id=revision_id,
                    created_at=created_at,
                )
            for event in events:
                self._insert_event(connection, event)
        return inserted

    def load_finding(self, finding_id: str) -> DomainFinding:
        row = self._connection.execute(
            "SELECT * FROM findings WHERE finding_id = ?", (finding_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"no finding {finding_id}")
        return self._finding_from_row(row)

    def commit_evaluation(
        self,
        book_id: str,
        branch_id: str,
        revision_id: str,
        findings: Sequence[DomainFinding],
        *,
        created_at: str,
        events: Sequence[Event],
        jobs: Sequence[Job] = (),
        fixed_finding_id: str | None = None,
    ) -> None:
        """Commit one evaluation's findings, verification result, events, and follow-ups."""
        with self.transaction() as connection:
            for finding in findings:
                self._insert_finding(
                    connection,
                    book_id,
                    branch_id,
                    finding,
                    revision_id=revision_id,
                    created_at=created_at,
                )
            if fixed_finding_id is not None:
                connection.execute(
                    "UPDATE findings SET status = ? WHERE finding_id = ? "
                    "AND book_id = ? AND branch_id = ? AND status IN (?, ?)",
                    (
                        FindingStatus.FIXED.value,
                        fixed_finding_id,
                        book_id,
                        branch_id,
                        FindingStatus.OPEN.value,
                        FindingStatus.CONFIRMED.value,
                    ),
                )
            for event in events:
                self._insert_event(connection, event)
            for job in jobs:
                self._jobs.insert_job(connection, job)

    def findings(
        self,
        book_id: str,
        branch_id: str,
        *,
        logical_id: str | None = None,
        status: FindingStatus | None = None,
        open_only: bool = False,
    ) -> list[DomainFinding]:
        """Findings for a book, worst severity first.

        `open_only` is the gate's filter and is *not* `status = 'open'`: `CONFIRMED` is also
        unresolved, and a gate that only looked at `OPEN` would wave through every defect a
        human had confirmed — the one status that means "yes, this is really wrong".
        """
        sql = "SELECT * FROM findings WHERE book_id = ? AND branch_id = ?"
        params: list[Any] = [book_id, branch_id]
        if logical_id is not None:
            sql += " AND logical_id = ?"
            params.append(logical_id)
        if status is not None:
            sql += " AND status = ?"
            params.append(status.value)
        if open_only:
            placeholders = ",".join("?" for _ in UNRESOLVED_STATUSES)
            sql += f" AND status IN ({placeholders})"
            params.extend(item.value for item in UNRESOLVED_STATUSES)
        sql += " ORDER BY created_at, finding_id"
        rows = [self._finding_from_row(row) for row in self._connection.execute(sql, params)]
        return sorted(rows, key=lambda item: (-item.severity.rank, item.finding_id))

    @staticmethod
    def _finding_from_row(row: sqlite3.Row) -> DomainFinding:
        stored = json.loads(row["finding_json"])
        projection = stored.get("projection", {})
        return DomainFinding(
            finding_id=row["finding_id"],
            category=row["category"],
            severity=DomainSeverity(row["severity"]),
            message=row["message"],
            status=FindingStatus(row["status"]),
            subtype=row["subtype"],
            rule_or_critic_id=row["rule_or_critic_id"],
            logical_id=row["logical_id"],
            confidence_basis=projection.get("confidence_basis", "unknown"),
            run_id=row["run_id"],
            source=stored.get("source", {}),
        )

    def set_finding_status(
        self, finding_id: str, status: FindingStatus, *, events: Sequence[Event] = ()
    ) -> bool:
        """Close a finding, or mark it intentional. False if no such finding.

        The operator verb behind a negative control: both fixtures ship deliberate devices a
        correct detector flags, and without this the only way past one would be to weaken the
        detector — trading a true positive for a quiet queue, which is the trade §10.6 spends
        a section refusing.
        """
        with self.transaction() as connection:
            cursor = connection.execute(
                "UPDATE findings SET status = ? WHERE finding_id = ?",
                (status.value, finding_id),
            )
            if cursor.rowcount == 0:
                return False
            for event in events:
                self._insert_event(connection, event)
        return True

    def finding_counts(self, book_id: str, branch_id: str) -> dict[str, int]:
        return {
            row["status"]: int(row["n"])
            for row in self._connection.execute(
                "SELECT status, COUNT(*) AS n FROM findings WHERE book_id = ? AND "
                "branch_id = ? GROUP BY status",
                (book_id, branch_id),
            )
        }

    # -- craft instrumentation, audit and calibration (§10.2-§10.5) -------------

    def record_scene_summary(
        self,
        book_id: str,
        branch_id: str,
        logical_id: str,
        *,
        content_hash: str,
        summary: str,
        model: str,
        profile: str,
        created_at: str,
    ) -> bool:
        """Store what one accepted scene contained, addressed by that scene's own text.

        `INSERT OR IGNORE` on the content hash, so re-summarising unchanged prose is a no-op
        rather than a second row: the key is the scene's text, and the same text has the same
        summary as far as the packet is concerned. A *repair* changes the text, mints a new
        hash, and gets its own row — which is the behaviour that keeps a summary from
        outliving the prose it describes.
        """
        with self.transaction() as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO scene_summaries (book_id, branch_id, logical_id, "
                "content_hash, summary, model, profile, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    book_id,
                    branch_id,
                    logical_id,
                    content_hash,
                    summary,
                    model,
                    profile,
                    created_at,
                ),
            )
            return cursor.rowcount > 0

    def scene_summaries(self, book_id: str, branch_id: str) -> dict[str, dict[str, str]]:
        """`{logical_id: {content_hash: summary}}` for one book.

        Returned keyed by content hash rather than flattened to one summary per scene, so the
        caller can check the summary it holds is a summary of the prose it has. A scene whose
        text has moved on has a row here and no *matching* row, and those are different
        answers: the first is "summarised, under an older draft", the second is "never
        summarised", and only the caller with the revision in hand can tell them apart.
        """
        rows = self._connection.execute(
            "SELECT logical_id, content_hash, summary FROM scene_summaries "
            "WHERE book_id = ? AND branch_id = ? ORDER BY logical_id, created_at",
            (book_id, branch_id),
        )
        out: dict[str, dict[str, str]] = {}
        for row in rows:
            out.setdefault(row["logical_id"], {})[row["content_hash"]] = row["summary"]
        return out

    def record_craft_metrics(
        self,
        revision_id: str,
        logical_id: str,
        metrics: Sequence[CraftMetric],
        *,
        measured_at: str,
    ) -> int:
        """Log advisory craft measurements for one accepted scene.

        `INSERT OR IGNORE` on (revision, node, metric): a revision is immutable and content
        addressed, so re-measuring one can only produce the same numbers. A row that differed
        would mean the metric changed, and that is a new metric id, not an update.
        """
        inserted = 0
        with self.transaction() as connection:
            for metric in metrics:
                cursor = connection.execute(
                    "INSERT OR IGNORE INTO craft_metrics (revision_id, logical_id, "
                    "metric_id, value, detail, measured_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        revision_id,
                        logical_id,
                        metric.metric_id,
                        float(metric.value),
                        metric.detail,
                        measured_at,
                    ),
                )
                inserted += cursor.rowcount
        return inserted

    def craft_metrics(
        self, *, metric_id: str | None = None, revision_id: str | None = None
    ) -> list[tuple[str, str, str, float]]:
        """(revision_id, logical_id, metric_id, value), oldest first.

        The distribution a calibration would be measured against. Returned as tuples rather
        than as `CraftMetric` because the caveat is a property of the *metric definition* and
        re-attaching it from a row would let a stale caveat outlive the code that earned it.
        """
        sql = "SELECT revision_id, logical_id, metric_id, value FROM craft_metrics WHERE 1=1"
        params: list[Any] = []
        if metric_id is not None:
            sql += " AND metric_id = ?"
            params.append(metric_id)
        if revision_id is not None:
            sql += " AND revision_id = ?"
            params.append(revision_id)
        sql += " ORDER BY measured_at, revision_id, logical_id, metric_id"
        return [
            (row["revision_id"], row["logical_id"], row["metric_id"], float(row["value"]))
            for row in self._connection.execute(sql, params)
        ]

    def record_audit_sample(self, sample: AuditSample, *, events: Sequence[Event] = ()) -> bool:
        """Queue one accepted scene for human reading. False if it was already drawn.

        Idempotent on the derived `sample_id`, so a replayed tick re-draws the same scene onto
        the same row rather than asking a human to read it twice.
        """
        with self.transaction() as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO audit_samples (sample_id, book_id, branch_id, "
                "revision_id, logical_id, sampled_at, rate, bucket) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    sample.sample_id,
                    sample.book_id,
                    sample.branch_id,
                    sample.revision_id,
                    sample.logical_id,
                    sample.sampled_at,
                    sample.rate,
                    sample.bucket,
                ),
            )
            inserted = cursor.rowcount > 0
            for event in events:
                self._insert_event(connection, event)
        return inserted

    def audit_samples(self, *, pending_only: bool = False) -> list[AuditSample]:
        sql = "SELECT * FROM audit_samples"
        if pending_only:
            sql += " WHERE verdict IS NULL"
        sql += " ORDER BY sampled_at, sample_id"
        return [self._audit_from_row(row) for row in self._connection.execute(sql)]

    @staticmethod
    def _audit_from_row(row: sqlite3.Row) -> AuditSample:
        return AuditSample(
            sample_id=row["sample_id"],
            book_id=row["book_id"],
            branch_id=row["branch_id"],
            revision_id=row["revision_id"],
            logical_id=row["logical_id"],
            sampled_at=row["sampled_at"],
            rate=float(row["rate"]),
            bucket=int(row["bucket"]),
            verdict=Verdict(row["verdict"]) if row["verdict"] else None,
            note=row["note"],
            judged_at=row["judged_at"],
            judged_by=row["judged_by"],
        )

    def record_verdict(
        self,
        sample_id: str,
        verdict: Verdict,
        *,
        at: str,
        by: str,
        note: str | None = None,
        events: Sequence[Event] = (),
    ) -> bool:
        """Store one human judgment. False if there is no such sample.

        **A verdict is never overwritten.** `WHERE verdict IS NULL` makes a second answer a
        no-op rather than a replacement, because the first reading is the blind one — §10.3
        wants blinded, order-randomized judgments, and a reader who has since seen the
        provenance is a different instrument. Changing a mind is a new sample, not an edit.
        """
        with self.transaction() as connection:
            cursor = connection.execute(
                "UPDATE audit_samples SET verdict = ?, note = ?, judged_at = ?, "
                "judged_by = ? WHERE sample_id = ? AND verdict IS NULL",
                (verdict.value, note, at, by, sample_id),
            )
            if cursor.rowcount == 0:
                return False
            for event in events:
                self._insert_event(connection, event)
        return True

    def audit_counts(self) -> dict[str, int]:
        counts = {
            row["verdict"] or "pending": int(row["n"])
            for row in self._connection.execute(
                "SELECT verdict, COUNT(*) AS n FROM audit_samples GROUP BY verdict"
            )
        }
        return counts

    def record_calibration(self, calibration: Calibration, *, events: Sequence[Event] = ()) -> bool:
        """Store measured evidence that a metric predicts human judgment.

        Not an upsert: a calibration is a record of a measurement that happened, so a second
        measurement is a second row with its own id and its own `verdicts_digest`. Overwriting
        would delete the evidence trail that makes "why did this threshold change" answerable.
        """
        with self.transaction() as connection:
            population = calibration.population
            cursor = connection.execute(
                "INSERT OR IGNORE INTO calibrations (calibration_id, metric_id, "
                "holdout_size, precision, recall, flagged, threshold, direction, "
                "verdicts_digest, measured_at, expires_at, note, evidence_class, grain, "
                "population_cohort, population_band, population_quantile, "
                "population_reference_n, population_tail_support, "
                "population_control_cohort, population_control_n, "
                "population_reference_exceedance, population_control_exceedance, "
                "population_profile_digest) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    calibration.calibration_id,
                    calibration.metric_id,
                    calibration.holdout_size,
                    calibration.precision,
                    calibration.recall,
                    calibration.flagged,
                    calibration.threshold,
                    calibration.direction.value,
                    calibration.verdicts_digest,
                    calibration.measured_at,
                    calibration.expires_at,
                    calibration.note,
                    calibration.evidence_class.value,
                    calibration.grain.value,
                    None if population is None else population.cohort,
                    None if population is None else population.band,
                    None if population is None else population.quantile,
                    None if population is None else population.reference_n,
                    None if population is None else population.tail_support,
                    None if population is None else population.control_cohort,
                    None if population is None else population.control_n,
                    None if population is None else population.reference_exceedance,
                    None if population is None else population.control_exceedance,
                    None if population is None else population.profile_digest,
                ),
            )
            inserted = cursor.rowcount > 0
            for event in events:
                self._insert_event(connection, event)
        return inserted

    def calibrations(self, *, metric_id: str | None = None) -> list[Calibration]:
        """Newest measurement first, so "the current evidence" is the first row."""
        sql = "SELECT * FROM calibrations"
        params: list[Any] = []
        if metric_id is not None:
            sql += " WHERE metric_id = ?"
            params.append(metric_id)
        sql += " ORDER BY measured_at DESC, calibration_id"
        return [
            Calibration(
                calibration_id=row["calibration_id"],
                metric_id=row["metric_id"],
                holdout_size=int(row["holdout_size"]),
                precision=float(row["precision"]),
                threshold=float(row["threshold"]),
                direction=Direction(row["direction"]),
                verdicts_digest=row["verdicts_digest"],
                measured_at=row["measured_at"],
                expires_at=row["expires_at"],
                recall=None if row["recall"] is None else float(row["recall"]),
                flagged=None if row["flagged"] is None else int(row["flagged"]),
                note=row["note"],
                evidence_class=EvidenceClass(row["evidence_class"]),
                grain=Grain(row["grain"]),
                population=_population_of(row),
            )
            for row in self._connection.execute(sql, params)
        ]

    def plan_epoch(self, book_id: str, branch_id: str) -> int:
        return self._jobs.plan_epoch(book_id, branch_id)

    def bump_plan_epoch(self, book_id: str, branch_id: str, *, at: str, reason: str) -> int:
        """Reissue every derived job id for this book. See migration 011's comment.

        A poisoned beat burns its idempotency key permanently, so without a version in the
        derivation "try scene 3 again" would be inexpressible.
        """
        return self._jobs.bump_plan_epoch(book_id, branch_id, at=at, reason=reason)

    def has_job(self, job_id: str) -> bool:
        """Cheap existence check. `load_job` would raise, and an exception is not a query."""
        return self._jobs.has_job(job_id)

    def any_unfinished(self, job_ids: Sequence[str]) -> bool:
        """Is any of these jobs still queued or running?

        The planner asks this before planning a book, because "one draft in flight per
        book" is what keeps revisions in a linear chain. Drain-first *usually* enforces it —
        a queued job is claimed before planning happens — but not when the job is leased by
        another holder, and an incidental guarantee is one that breaks quietly.
        """
        return self._jobs.any_unfinished(job_ids)

    def branches(self) -> list[tuple[str, str, str]]:
        """Every (book_id, branch_id, head revision_id) the store knows about."""
        return [
            (row["book_id"], row["branch_id"], row["revision_id"])
            for row in self._connection.execute(
                "SELECT book_id, branch_id, revision_id FROM branch_heads "
                "ORDER BY book_id, branch_id"
            )
        ]

    # -- exception queue ------------------------------------------------------

    def raise_exception(self, record: ExceptionRecord) -> bool:
        """Open an exception. False if this escalation was already recorded.

        Idempotent by content-derived id, so a replayed tick raises one exception rather
        than a queue of identical ones — which would be the fastest way to make the queue
        useless.
        """
        with self.transaction() as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO exceptions (exception_id, kind, summary, status, "
                "job_id, logical_id, decision_id, raised_at, resolved_at, resolution, "
                "attempts) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.exception_id,
                    record.kind.value,
                    record.summary,
                    record.status.value,
                    record.job_id,
                    record.logical_id,
                    record.decision_id,
                    record.raised_at,
                    record.resolved_at,
                    record.resolution,
                    record.attempts,
                ),
            )
            return cursor.rowcount > 0

    def open_exceptions(self, limit: int = 50) -> list[ExceptionRecord]:
        return [
            _exception_from_row(row)
            for row in self._connection.execute(
                "SELECT * FROM exceptions WHERE status IN (?, ?) ORDER BY raised_at, rowid LIMIT ?",
                (ExceptionStatus.OPEN.value, ExceptionStatus.ACKNOWLEDGED.value, limit),
            )
        ]

    def load_exception(self, exception_id: str) -> ExceptionRecord:
        row = self._connection.execute(
            "SELECT * FROM exceptions WHERE exception_id = ?", (exception_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"no exception {exception_id}")
        return _exception_from_row(row)

    def resolve_exception(
        self,
        exception_id: str,
        resolution: str,
        *,
        at: str,
        status: ExceptionStatus = ExceptionStatus.RESOLVED,
    ) -> ExceptionRecord:
        """Close the human's side. Deliberately does not restart the work.

        `revive` is the separate act that requeues the unit, because a director may decide
        the escalation was correct and the unit should stay stopped. Collapsing the two
        would make "I have seen this and it should not run" inexpressible.
        """
        closed = self.load_exception(exception_id).close(resolution, at=at, status=status)
        with self.transaction() as connection:
            connection.execute(
                "UPDATE exceptions SET status = ?, resolution = ?, resolved_at = ? "
                "WHERE exception_id = ?",
                (closed.status.value, closed.resolution, closed.resolved_at, exception_id),
            )
        return closed

    def exceptions_for_job(self, job_id: str) -> list[ExceptionRecord]:
        return [
            _exception_from_row(row)
            for row in self._connection.execute(
                "SELECT * FROM exceptions WHERE job_id = ? ORDER BY raised_at, rowid",
                (job_id,),
            )
        ]

    # -- operator controls ----------------------------------------------------

    def set_control(self, key: str, value: str, *, at: str, by: str | None = None) -> None:
        self._jobs.set_control(key, value, at=at, by=by)

    def control(self, key: str) -> str | None:
        return self._jobs.control(key)

    def is_paused(self) -> bool:
        return self._jobs.is_paused()

    def job_counts_by_status(self) -> dict[str, int]:
        """Queue depth per status — the operator's first question.

        Until this existed there was no way to ask "is anything stuck": the only job query
        was `load_job(job_id)`, which requires already knowing the id of the job you have
        not heard about. §19's "parked units and exceptions are visible" was unanswerable
        by construction.
        """
        return self._jobs.job_counts_by_status()

    def jobs_by_status(self, status: JobStatus, limit: int = 50) -> list[Job]:
        return self._jobs.jobs_by_status(status, limit)

    def revive(self, job_id: str) -> Job:
        """Return a parked unit to the queue after a human resolved what parked it.

        Parked is terminal *by policy*, not by exhaustion, so the resolution is a decision
        rather than another attempt — and without this method there was no way to act on
        one. Attempts reset because the blocker was external: a unit parked on a locked
        node has not consumed its budget on failures of its own.

        Deliberately refuses a poisoned job. Poisoning means the attempt budget really was
        spent, and reviving it without changing anything would just spend it again.
        """
        return self._jobs.revive(job_id)

    # -- instance lease -------------------------------------------------------

    def acquire_instance_lease(self, scope: str, holder: str, now: float, duration: float) -> bool:
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

    def instance_lease(self, scope: str) -> tuple[str | None, float | None]:
        """Holder and expiry, unfiltered by time.

        Deliberately not the boolean `instance_lease_holder` answers. A crashed holder
        still owns its lease for the full duration, so "is someone leading" says yes for
        five minutes after the process died. Returning the expiry lets a caller show that
        to a human instead of reporting a corpse as healthy.
        """
        row = self._connection.execute(
            "SELECT holder, expires_at FROM instance_leases WHERE scope = ?", (scope,)
        ).fetchone()
        if row is None:
            return None, None
        return str(row["holder"]), float(row["expires_at"])

    def last_tick(self) -> dict[str, Any] | None:
        """The most recent tick — the system's liveness signal.

        `tick_records.started_at` has been stored and indexed since migration 002 and read
        by nothing, which is why "when did it last run" had no answer.
        """
        row = self._connection.execute(
            "SELECT tick_id, holder, started_at, outcome, job_id FROM tick_records "
            "ORDER BY started_at DESC, rowid DESC LIMIT 1"
        ).fetchone()
        return None if row is None else dict(row)

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

    def ingested_directives_by_status(self, status: DirectiveStatus) -> list[Directive]:
        """Direction visible to work selection, after its arrival event was committed."""
        return [
            _directive_from_row(row)
            for row in self._connection.execute(
                "SELECT * FROM directives WHERE status = ? AND ingested_at IS NOT NULL "
                "ORDER BY precedence DESC, rowid",
                (status.value,),
            )
        ]

    # -- policy decisions -----------------------------------------------------

    @staticmethod
    def _insert_decision(
        connection: sqlite3.Connection,
        decision: PolicyDecision,
        *,
        decided_at: str,
    ) -> bool:
        cursor = connection.execute(
            "INSERT OR IGNORE INTO policy_decisions (decision_id, outcome, job_id, "
            "logical_id, base_revision_id, resulting_revision_id, attempt, provider, "
            "model, profile, fell_back_from, invocations, total_tokens, "
            "policy_config_digest, reason, gates, decided_at, cost_usd) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                decision.cost_usd,
            ),
        )
        return cursor.rowcount > 0

    def record_decision(self, decision: PolicyDecision, *, decided_at: str) -> bool:
        """Persist one acceptance decision. False if this ``decision_id`` already exists.

        Idempotent by content-derived id, for the same reason ticks are: a job replayed
        after a crash must not accumulate duplicate rows for one judgment.
        """
        with self.transaction() as connection:
            return self._insert_decision(connection, decision, decided_at=decided_at)

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

    def spend_on(self, day: str) -> Spend:
        """What one day cost, from the durable record of what was actually consumed.

        Derived from `policy_decisions` rather than kept as a running counter, because a
        counter and the decisions it summarises can disagree after a crash and there would
        be no way to tell which was right. The decisions are the record; this is a view of
        them. `decided_at` is an ISO-8601 stamp, so a date prefix is the day.
        """
        row = self._connection.execute(
            "SELECT COALESCE(SUM(invocations), 0) AS invocations, "
            "COALESCE(SUM(total_tokens), 0) AS tokens, "
            "COALESCE(SUM(cost_usd), 0.0) AS cost "
            "FROM policy_decisions WHERE decided_at LIKE ?",
            (f"{day}%",),
        ).fetchone()
        return Spend(
            invocations=int(row["invocations"]),
            tokens=int(row["tokens"]),
            cost_usd=float(row["cost"]),
        )

    def latest_decision_for(self, job_id: str) -> PolicyDecision | None:
        """The most recent decision for a job — what the Conductor settles the row against.

        Read back rather than returned by the handler, because `JobHandler` returns events
        by contract and widening that signature for one handler's benefit would make every
        future handler carry it.
        """
        row = self._connection.execute(
            "SELECT * FROM policy_decisions WHERE job_id = ? ORDER BY attempt DESC, rowid "
            "DESC LIMIT 1",
            (job_id,),
        ).fetchone()
        return None if row is None else _decision_from_row(row)

    def decision_for_revision(self, revision_id: str) -> PolicyDecision | None:
        """The decision that accepted ``revision_id``, if one was recorded.

        §19's integrity clause — "every mutation is attributable to a recorded policy
        decision" — is only checkable if this lookup exists.
        """
        row = self._connection.execute(
            "SELECT * FROM policy_decisions WHERE resulting_revision_id = ? ORDER BY rowid LIMIT 1",
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
        """Rebuild every manuscript and plan revision; return the manuscript count.

        This is §19's recovery clause as an assertion: node content hashes are recomputed
        by `Node.__post_init__` and revision ids by `Revision.__post_init__`, so a single
        altered character anywhere in storage fails here.
        """
        rows = self._connection.execute("SELECT revision_id FROM revisions").fetchall()
        for row in rows:
            self.load_revision(row["revision_id"])
        self._plans.verify_integrity()
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


def _population_of(row: Any) -> Population | None:
    """Rebuild the population block, or None for a row that carries none.

    Keyed on the cohort rather than on `evidence_class`, so a row that claims to be a
    population calibration and stored no population comes back with `population=None` and is
    refused by name in `why_not_promotable` — rather than being reconstructed out of NULLs
    into an object that looks complete.
    """
    if row["population_cohort"] is None:
        return None
    return Population(
        metric_id=row["metric_id"],
        cohort=row["population_cohort"],
        band=row["population_band"],
        quantile=row["population_quantile"],
        reference_n=int(row["population_reference_n"]),
        tail_support=int(row["population_tail_support"]),
        control_cohort=row["population_control_cohort"],
        control_n=int(row["population_control_n"]),
        reference_exceedance=float(row["population_reference_exceedance"]),
        control_exceedance=float(row["population_control_exceedance"]),
        profile_digest=row["population_profile_digest"],
    )
