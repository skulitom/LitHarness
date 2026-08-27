"""SQLite capability for versioned reader evidence and editorial interventions."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from typing import Protocol

from litharness.adapters.sqlite_jobs import TransactionFactory
from litharness.domain.directives import Directive
from litharness.domain.editorial import (
    EditorialDecision,
    EditorialIntervention,
    InterventionRealization,
    QualificationEvidence,
    ReaderMechanism,
    ReaderMechanismStatus,
    ReaderObservation,
)
from litharness.domain.events import payload_digest
from litharness.domain.policy import PolicyDecision


class DecisionInserter(Protocol):
    def __call__(
        self,
        connection: sqlite3.Connection,
        decision: PolicyDecision,
        *,
        decided_at: str,
    ) -> bool: ...


def _mechanism_from_row(row: sqlite3.Row) -> ReaderMechanism:
    return ReaderMechanism(
        mechanism_id=row["mechanism_id"],
        version_id=row["version_id"],
        status=ReaderMechanismStatus(row["status"]),
        spec_digest=row["spec_digest"],
        evidence_digest=row["evidence_digest"],
        registered_at=row["registered_at"],
    )


def _observation_from_row(row: sqlite3.Row) -> ReaderObservation:
    return ReaderObservation(
        observation_id=row["observation_id"],
        source_job_id=row["source_job_id"],
        checkpoint_id=row["checkpoint_id"],
        mechanism_version_id=row["mechanism_version_id"],
        book_id=row["book_id"],
        branch_id=row["branch_id"],
        revision_id=row["revision_id"],
        logical_id=row["logical_id"],
        reader_id=row["reader_id"],
        pool=row["pool"],
        panel_size=row["panel_size"],
        source_content_hash=row["source_content_hash"],
        persona_digest=row["persona_digest"],
        prompt_digest=row["prompt_digest"],
        system_digest=row["system_digest"],
        schema_digest=row["schema_digest"],
        context_digest=row["context_digest"],
        profile=row["profile"],
        provider=row["provider"],
        model=row["model"],
        response=json.loads(row["response_json"]),
        observed_at=row["observed_at"],
    )


def _intervention_from_row(row: sqlite3.Row) -> EditorialIntervention:
    return EditorialIntervention(
        intervention_id=row["intervention_id"],
        controller_job_id=row["controller_job_id"],
        checkpoint_id=row["checkpoint_id"],
        mechanism_version_id=row["mechanism_version_id"],
        book_id=row["book_id"],
        branch_id=row["branch_id"],
        source_revision_id=row["source_revision_id"],
        source_logical_id=row["source_logical_id"],
        decision=EditorialDecision(row["decision"]),
        need=row["need"],
        rationale=row["rationale"],
        evidence_observation_ids=tuple(json.loads(row["evidence_observation_ids"])),
        evidence_digest=row["evidence_digest"],
        target_logical_ids=tuple(json.loads(row["target_logical_ids"])),
        directive_id=row["directive_id"],
        created_at=row["created_at"],
        metadata=json.loads(row["metadata"]) if row["metadata"] else {},
    )


class SqliteAudienceRepository:
    def __init__(
        self,
        connection: sqlite3.Connection,
        transaction: TransactionFactory,
        *,
        insert_decision: DecisionInserter,
    ) -> None:
        self._connection = connection
        self._transaction = transaction
        self._insert_decision = insert_decision

    def register_reader_mechanism(
        self,
        mechanism: ReaderMechanism,
        *,
        evidence: Mapping[str, object] | None = None,
    ) -> bool:
        evidence_json: str | None = None
        qualification: QualificationEvidence | None = None
        if mechanism.status is ReaderMechanismStatus.QUALIFIED:
            if evidence is None:
                raise ValueError("a qualified mechanism needs its evidence artifact")
            qualification = QualificationEvidence.from_payload(evidence)
            qualification.validate_for(mechanism.mechanism_id, mechanism.spec_digest)
            if qualification.candidate_version_id == mechanism.version_id:
                raise ValueError("qualification evidence must address the evaluated version")
            if qualification.evidence_digest != mechanism.evidence_digest:
                raise ValueError("mechanism evidence digest does not match its artifact")
            evidence_json = json.dumps(evidence, sort_keys=True, ensure_ascii=False)
        elif evidence is not None:
            evidence_digest = payload_digest(dict(evidence))
            if mechanism.evidence_digest != evidence_digest:
                raise ValueError("mechanism evidence digest does not match its artifact")
            evidence_json = json.dumps(evidence, sort_keys=True, ensure_ascii=False)
        with self._transaction() as connection:
            if connection.execute(
                "SELECT 1 FROM reader_mechanism_versions WHERE version_id = ?",
                (mechanism.version_id,),
            ).fetchone() is not None:
                return False
            if qualification is not None:
                candidate = connection.execute(
                    "SELECT mechanism_id, status, spec_digest "
                    "FROM reader_mechanism_versions WHERE version_id = ?",
                    (qualification.candidate_version_id,),
                ).fetchone()
                if candidate is None:
                    raise ValueError("qualification evidence candidate is not registered")
                if (
                    candidate["mechanism_id"] != mechanism.mechanism_id
                    or candidate["status"] != ReaderMechanismStatus.EXPERIMENTAL.value
                    or candidate["spec_digest"] != mechanism.spec_digest
                ):
                    raise ValueError(
                        "qualification evidence candidate is not this experimental mechanism"
                    )
                current = connection.execute(
                    "SELECT version_id FROM reader_mechanism_versions "
                    "WHERE mechanism_id = ? ORDER BY registered_at DESC, rowid DESC LIMIT 1",
                    (mechanism.mechanism_id,),
                ).fetchone()
                if current is None or current["version_id"] != qualification.candidate_version_id:
                    raise ValueError("qualification evidence does not address the current version")
            cursor = connection.execute(
                "INSERT OR IGNORE INTO reader_mechanism_versions "
                "(version_id, mechanism_id, status, spec_digest, evidence_digest, registered_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    mechanism.version_id,
                    mechanism.mechanism_id,
                    mechanism.status.value,
                    mechanism.spec_digest,
                    mechanism.evidence_digest,
                    mechanism.registered_at,
                ),
            )
            if evidence_json is not None:
                connection.execute(
                    "INSERT OR IGNORE INTO reader_mechanism_evidence "
                    "(version_id, evidence_json, recorded_at) VALUES (?, ?, ?)",
                    (mechanism.version_id, evidence_json, mechanism.registered_at),
                )
            return cursor.rowcount > 0

    def reader_mechanism_evidence(self, version_id: str) -> dict[str, object] | None:
        row = self._connection.execute(
            "SELECT evidence_json FROM reader_mechanism_evidence WHERE version_id = ?",
            (version_id,),
        ).fetchone()
        if row is None:
            return None
        value = json.loads(row["evidence_json"])
        return dict(value) if isinstance(value, dict) else None

    def reader_mechanism(self, version_id: str) -> ReaderMechanism:
        row = self._connection.execute(
            "SELECT * FROM reader_mechanism_versions WHERE version_id = ?", (version_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"no reader mechanism version {version_id}")
        return _mechanism_from_row(row)

    def current_reader_mechanism(self, mechanism_id: str) -> ReaderMechanism | None:
        row = self._connection.execute(
            "SELECT * FROM reader_mechanism_versions WHERE mechanism_id = ? "
            "ORDER BY registered_at DESC, rowid DESC LIMIT 1",
            (mechanism_id,),
        ).fetchone()
        return _mechanism_from_row(row) if row is not None else None

    def reader_observation_for_job(self, source_job_id: str) -> ReaderObservation | None:
        row = self._connection.execute(
            "SELECT * FROM reader_observations WHERE source_job_id = ?", (source_job_id,)
        ).fetchone()
        return _observation_from_row(row) if row is not None else None

    def record_reader_observation(
        self,
        observation: ReaderObservation,
        *,
        decision: PolicyDecision,
        decided_at: str,
    ) -> bool:
        """Commit the evidence and the spend/acceptance record together."""
        with self._transaction() as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO reader_observations "
                "(observation_id, source_job_id, checkpoint_id, mechanism_version_id, "
                "book_id, branch_id, revision_id, logical_id, reader_id, pool, panel_size, "
                "source_content_hash, persona_digest, prompt_digest, system_digest, "
                "schema_digest, context_digest, profile, provider, model, response_json, "
                "observed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                "?, ?, ?, ?, ?, ?)",
                (
                    observation.observation_id,
                    observation.source_job_id,
                    observation.checkpoint_id,
                    observation.mechanism_version_id,
                    observation.book_id,
                    observation.branch_id,
                    observation.revision_id,
                    observation.logical_id,
                    observation.reader_id,
                    observation.pool,
                    observation.panel_size,
                    observation.source_content_hash,
                    observation.persona_digest,
                    observation.prompt_digest,
                    observation.system_digest,
                    observation.schema_digest,
                    observation.context_digest,
                    observation.profile,
                    observation.provider,
                    observation.model,
                    json.dumps(observation.response, sort_keys=True, ensure_ascii=False),
                    observation.observed_at,
                ),
            )
            self._insert_decision(connection, decision, decided_at=decided_at)
            return cursor.rowcount > 0

    def reader_observations(
        self,
        book_id: str,
        branch_id: str,
        *,
        checkpoint_id: str | None = None,
        mechanism_version_id: str | None = None,
    ) -> list[ReaderObservation]:
        sql = "SELECT * FROM reader_observations WHERE book_id = ? AND branch_id = ?"
        params: list[object] = [book_id, branch_id]
        if checkpoint_id is not None:
            sql += " AND checkpoint_id = ?"
            params.append(checkpoint_id)
        if mechanism_version_id is not None:
            sql += " AND mechanism_version_id = ?"
            params.append(mechanism_version_id)
        sql += " ORDER BY observed_at, reader_id"
        return [_observation_from_row(row) for row in self._connection.execute(sql, params)]

    def ready_reader_panels(self) -> list[dict[str, str]]:
        """Complete qualified panels that have not produced an intervention."""
        rows = self._connection.execute(
            "SELECT o.checkpoint_id, o.mechanism_version_id, o.book_id, o.branch_id, "
            "o.revision_id, o.logical_id "
            "FROM reader_observations o "
            "JOIN reader_mechanism_versions m ON m.version_id = o.mechanism_version_id "
            "JOIN reader_mechanism_evidence me ON me.version_id = m.version_id "
            "LEFT JOIN editorial_interventions i "
            "ON i.checkpoint_id = o.checkpoint_id "
            "AND i.mechanism_version_id = o.mechanism_version_id "
            "WHERE m.status = 'qualified' AND o.pool = 'steering' "
            "AND m.version_id = ("
            "SELECT newest.version_id FROM reader_mechanism_versions newest "
            "WHERE newest.mechanism_id = m.mechanism_id "
            "ORDER BY newest.registered_at DESC, newest.rowid DESC LIMIT 1"
            ") "
            "AND i.intervention_id IS NULL "
            "GROUP BY o.checkpoint_id, o.mechanism_version_id, o.book_id, o.branch_id, "
            "o.revision_id, o.logical_id "
            "HAVING COUNT(DISTINCT o.reader_id) >= MAX(o.panel_size) "
            "ORDER BY MIN(o.observed_at), o.checkpoint_id"
        )
        return [dict(row) for row in rows]

    def record_editorial_intervention(
        self,
        intervention: EditorialIntervention,
        *,
        directive: Directive | None,
        decision: PolicyDecision,
        decided_at: str,
    ) -> bool:
        """Commit the controller result, optional direction, and model spend atomically."""
        if bool(directive) != bool(intervention.directive_id):
            raise ValueError("intervention and directive disagree")
        if directive is not None and directive.directive_id != intervention.directive_id:
            raise ValueError("intervention points at a different directive")
        with self._transaction() as connection:
            if directive is not None:
                connection.execute(
                    "INSERT OR IGNORE INTO directives (directive_id, kind, body, status, "
                    "book_id, branch_id, target_logical_ids, interpretation, "
                    "produced_constraint_ids, received_at, ingested_at, interpreted_at, "
                    "precedence, superseded_by, author, metadata) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?)",
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
                        directive.received_at or intervention.created_at,
                        directive.interpreted_at,
                        directive.precedence,
                        directive.superseded_by,
                        directive.author,
                        json.dumps(directive.metadata, sort_keys=True, ensure_ascii=False),
                    ),
                )
            cursor = connection.execute(
                "INSERT OR IGNORE INTO editorial_interventions "
                "(intervention_id, controller_job_id, checkpoint_id, mechanism_version_id, "
                "book_id, branch_id, source_revision_id, source_logical_id, decision, need, "
                "rationale, evidence_observation_ids, evidence_digest, target_logical_ids, "
                "directive_id, created_at, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    intervention.intervention_id,
                    intervention.controller_job_id,
                    intervention.checkpoint_id,
                    intervention.mechanism_version_id,
                    intervention.book_id,
                    intervention.branch_id,
                    intervention.source_revision_id,
                    intervention.source_logical_id,
                    intervention.decision.value,
                    intervention.need,
                    intervention.rationale,
                    json.dumps(list(intervention.evidence_observation_ids)),
                    intervention.evidence_digest,
                    json.dumps(list(intervention.target_logical_ids)),
                    intervention.directive_id,
                    intervention.created_at,
                    json.dumps(intervention.metadata, sort_keys=True, ensure_ascii=False)
                    if intervention.metadata
                    else None,
                ),
            )
            self._insert_decision(connection, decision, decided_at=decided_at)
            return cursor.rowcount > 0

    def editorial_intervention_for_job(
        self, controller_job_id: str
    ) -> EditorialIntervention | None:
        row = self._connection.execute(
            "SELECT * FROM editorial_interventions WHERE controller_job_id = ?",
            (controller_job_id,),
        ).fetchone()
        return _intervention_from_row(row) if row is not None else None

    def editorial_interventions(self, book_id: str, branch_id: str) -> list[EditorialIntervention]:
        return [
            _intervention_from_row(row)
            for row in self._connection.execute(
                "SELECT * FROM editorial_interventions WHERE book_id = ? AND branch_id = ? "
                "ORDER BY created_at, rowid",
                (book_id, branch_id),
            )
        ]

    def editorial_interventions_targeting(
        self,
        book_id: str,
        branch_id: str,
        logical_id: str,
        plan_revision_id: str,
    ) -> list[EditorialIntervention]:
        """Interventions whose directive produced this exact applied plan revision.

        Targeting alone is insufficient evidence of realization: another plan may have been
        active when the scene was drafted. The proposal reading is the durable join between the
        controller's directive and the immutable plan snapshot supplied to that draft.
        """
        return [
            _intervention_from_row(row)
            for row in self._connection.execute(
                "SELECT i.* FROM editorial_interventions i "
                "JOIN json_each(i.target_logical_ids) target "
                "JOIN plan_revisions pr ON pr.plan_revision_id = ? "
                "JOIN plan_proposals pp ON pp.proposal_id = pr.proposal_id "
                "JOIN json_each(pp.proposal_json, '$.readings') reading "
                "WHERE i.book_id = ? AND i.branch_id = ? AND target.value = ? "
                "AND pp.status = 'applied' "
                "AND pp.resulting_plan_revision_id = pr.plan_revision_id "
                "AND json_extract(reading.value, '$.directive_id') = i.directive_id "
                "ORDER BY i.created_at, i.rowid",
                (plan_revision_id, book_id, branch_id, logical_id),
            )
        ]

    @staticmethod
    def insert_intervention_realization(
        connection: sqlite3.Connection, realization: InterventionRealization
    ) -> bool:
        cursor = connection.execute(
            "INSERT OR IGNORE INTO editorial_intervention_realizations "
            "(realization_id, intervention_id, directive_id, plan_revision_id, book_id, "
            "branch_id, logical_id, revision_id, content_hash, recorded_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                realization.realization_id,
                realization.intervention_id,
                realization.directive_id,
                realization.plan_revision_id,
                realization.book_id,
                realization.branch_id,
                realization.logical_id,
                realization.revision_id,
                realization.content_hash,
                realization.recorded_at,
            ),
        )
        return cursor.rowcount > 0

    def intervention_realizations(
        self, book_id: str, branch_id: str
    ) -> list[InterventionRealization]:
        return [
            InterventionRealization(
                realization_id=row["realization_id"],
                intervention_id=row["intervention_id"],
                directive_id=row["directive_id"],
                plan_revision_id=row["plan_revision_id"],
                book_id=row["book_id"],
                branch_id=row["branch_id"],
                logical_id=row["logical_id"],
                revision_id=row["revision_id"],
                content_hash=row["content_hash"],
                recorded_at=row["recorded_at"],
            )
            for row in self._connection.execute(
                "SELECT * FROM editorial_intervention_realizations "
                "WHERE book_id = ? AND branch_id = ? ORDER BY recorded_at, rowid",
                (book_id, branch_id),
            )
        ]


__all__ = ["SqliteAudienceRepository"]
