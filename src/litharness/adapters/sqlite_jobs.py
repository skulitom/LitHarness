"""Durable job queue, operator controls, and plan-epoch persistence."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import replace
from typing import Any, Protocol

from litharness.domain.jobs import IllegalTransition, Job, JobStatus


class TransactionContext(Protocol):
    """The small context-manager surface repositories need from the store."""

    def __enter__(self) -> sqlite3.Connection: ...

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None: ...


TransactionFactory = Callable[[], TransactionContext]


def _dump_payload(payload: dict[str, Any]) -> str | None:
    """Serialize a job payload, or NULL for an empty one."""
    if not payload:
        return None
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


class SqliteJobRepository:
    """Persistence capability for durable work and its operational controls."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        transaction: TransactionFactory,
    ) -> None:
        self._connection = connection
        self._transaction = transaction

    def enqueue(self, job: Job) -> bool:
        """Queue work, returning false when its id or idempotency key already exists."""
        with self._transaction() as connection:
            return self.insert_job(connection, job)

    @staticmethod
    def insert_job(connection: sqlite3.Connection, job: Job) -> bool:
        """Insert on a caller-owned transaction so follow-up work is crash-atomic."""
        cursor = connection.execute(
            "INSERT OR IGNORE INTO jobs (job_id, job_kind, status, attempts, max_attempts, "
            "idempotency_key, input_digest, error, lease_holder, lease_expires_at, "
            "payload, priority) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
        return cursor.rowcount > 0

    def save_job(self, job: Job) -> None:
        with self._transaction() as connection:
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
        row = self._connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(f"no job {job_id}")
        return self.job_from_row(row)

    @staticmethod
    def job_from_row(row: sqlite3.Row) -> Job:
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
        """Claim one queued job and write its lease in the same transaction."""
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE status = ? "
                "AND (lease_expires_at IS NULL OR lease_expires_at <= ?) "
                "ORDER BY priority DESC, rowid LIMIT 1",
                (JobStatus.QUEUED.value, now),
            ).fetchone()
            if row is None:
                return None
            job = self.job_from_row(row).claim(holder, now, duration)
            connection.execute(
                "UPDATE jobs SET lease_holder = ?, lease_expires_at = ? WHERE job_id = ?",
                (job.lease_holder, job.lease_expires_at, job.job_id),
            )
            return job

    def reclaim_expired(self, now: float) -> list[Job]:
        """Requeue work abandoned by a crashed lease holder, within its attempt budget."""
        rows = self._connection.execute(
            "SELECT * FROM jobs WHERE status = ? AND lease_expires_at IS NOT NULL "
            "AND lease_expires_at <= ? ORDER BY rowid",
            (JobStatus.RUNNING.value, now),
        ).fetchall()
        reclaimed: list[Job] = []
        for row in rows:
            job = self.job_from_row(row).released()
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
        """Requeue failed work with budget left, poisoning exhausted work."""
        rows = self._connection.execute(
            "SELECT * FROM jobs WHERE status = ? ORDER BY rowid", (JobStatus.FAILED.value,)
        ).fetchall()
        moved: list[Job] = []
        for row in rows:
            job = self.job_from_row(row).released()
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

    def plan_epoch(self, book_id: str, branch_id: str) -> int:
        row = self._connection.execute(
            "SELECT epoch FROM plan_epochs WHERE book_id = ? AND branch_id = ?",
            (book_id, branch_id),
        ).fetchone()
        return 0 if row is None else int(row["epoch"])

    @staticmethod
    def advance_plan_epoch(
        connection: sqlite3.Connection,
        book_id: str,
        branch_id: str,
        *,
        at: str,
        reason: str,
    ) -> None:
        connection.execute(
            "INSERT INTO plan_epochs (book_id, branch_id, epoch, bumped_at, reason) "
            "VALUES (?, ?, 1, ?, ?) ON CONFLICT (book_id, branch_id) DO UPDATE SET "
            "epoch = epoch + 1, bumped_at = excluded.bumped_at, reason = excluded.reason",
            (book_id, branch_id, at, reason),
        )

    @staticmethod
    def cancel_queued_scene_jobs(
        connection: sqlite3.Connection,
        book_id: str,
        branch_id: str,
        *,
        reason: str,
    ) -> int:
        """Cancel frozen prompts invalidated by a plan change before claim."""
        cursor = connection.execute(
            "UPDATE jobs SET status = ?, error = ?, lease_holder = NULL, "
            "lease_expires_at = NULL WHERE status = ? AND job_kind = ? "
            "AND json_extract(payload, '$.book_id') = ? "
            "AND json_extract(payload, '$.branch_id') = ?",
            (
                JobStatus.CANCELLED.value,
                reason,
                JobStatus.QUEUED.value,
                "scene_draft",
                book_id,
                branch_id,
            ),
        )
        return cursor.rowcount

    def bump_plan_epoch(self, book_id: str, branch_id: str, *, at: str, reason: str) -> int:
        """Reissue derived job ids and cancel scene prompts based on the old plan."""
        with self._transaction() as connection:
            self.advance_plan_epoch(connection, book_id, branch_id, at=at, reason=reason)
            self.cancel_queued_scene_jobs(
                connection,
                book_id,
                branch_id,
                reason=f"superseded by plan epoch: {reason}",
            )
        return self.plan_epoch(book_id, branch_id)

    def has_job(self, job_id: str) -> bool:
        row = self._connection.execute("SELECT 1 FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return row is not None

    def any_unfinished(self, job_ids: Sequence[str]) -> bool:
        if not job_ids:
            return False
        placeholders = ",".join("?" for _ in job_ids)
        row = self._connection.execute(
            f"SELECT 1 FROM jobs WHERE job_id IN ({placeholders}) AND status IN (?, ?) LIMIT 1",
            (*job_ids, JobStatus.QUEUED.value, JobStatus.RUNNING.value),
        ).fetchone()
        return row is not None

    def set_control(self, key: str, value: str, *, at: str, by: str | None = None) -> None:
        with self._transaction() as connection:
            connection.execute(
                "INSERT INTO control (key, value, set_at, set_by) VALUES (?, ?, ?, ?) "
                "ON CONFLICT (key) DO UPDATE SET value = excluded.value, "
                "set_at = excluded.set_at, set_by = excluded.set_by",
                (key, value, at, by),
            )

    def control(self, key: str) -> str | None:
        row = self._connection.execute("SELECT value FROM control WHERE key = ?", (key,)).fetchone()
        return None if row is None else str(row["value"])

    def is_paused(self) -> bool:
        return self.control("paused") == "true"

    def job_counts_by_status(self) -> dict[str, int]:
        return {
            row["status"]: int(row["n"])
            for row in self._connection.execute(
                "SELECT status, COUNT(*) AS n FROM jobs GROUP BY status ORDER BY status"
            )
        }

    def jobs_by_status(self, status: JobStatus, limit: int = 50) -> list[Job]:
        return [
            self.job_from_row(row)
            for row in self._connection.execute(
                "SELECT * FROM jobs WHERE status = ? ORDER BY rowid LIMIT ?",
                (status.value, limit),
            )
        ]

    def revive(self, job_id: str) -> Job:
        """Return human-unblocked parked work to the queue."""
        job = self.load_job(job_id)
        if job.status is not JobStatus.PARKED:
            raise IllegalTransition(
                f"job {job_id} is {job.status.value}, not parked; only a parked unit can be "
                "revived, because only a parked unit stopped for a reason a human can clear"
            )
        revived = replace(job.transition_to(JobStatus.QUEUED), attempts=0, error=None).released()
        self.save_job(revived)
        return revived
