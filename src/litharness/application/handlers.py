"""Job handlers: the seam where a provider call becomes an accepted revision.

Until this module existed, `providers/registry.py` had no consumer anywhere outside its
own package — four working adapters, a conformance suite, a billing guard, and nothing
that ever called them. PLAN.md §20.4 attributed that to missing subsystems ("the first
real handler is a Stage 1 concern: a scene draft needs a plan and a context packet").
Half true. A *planned* scene draft does need those. Wiring did not: what it needed was
for a job to carry its input, which migration 003 added.

**What a handler may and may not do.** `JobHandler` returns events; it must not write to
the store. The Conductor commits the events with the job's status change, and that is the
only ordering under which "no accepted artifact without the event recording it" survives
a crash mid-handler (`plan/stage-0-decisions.md` §6). The one thing this handler *does*
write directly is the revision, via `commit_revision`, which takes its events in the same
transaction — so the revision and its `ManuscriptRevisionAccepted` event are atomic with
each other even though the job row is not atomic with them. That residual gap is real and
is handled by making the work idempotent rather than by pretending otherwise: revisions
are content-addressed and committed with `INSERT OR IGNORE`, and event idempotency keys
are derived from content, so a replayed job converges instead of duplicating.

**Every candidate produces a decision, accepted or not.** A candidate that fails its gate
emits `MANUSCRIPT_CANDIDATE_CREATED` with the veto list; one that passes emits
`MANUSCRIPT_REVISION_ACCEPTED`; both are accompanied by a `POLICY_DECISION_RECORDED` and a
row in `policy_decisions`. That is §19's integrity clause — "every mutation is attributable
to a recorded policy decision" — made checkable via `store.decision_for_revision`.

Slice 4 approximated this by putting gate results into the event payload, because contracts
had no policy decision record. It has one as of 1.1.0, and the shape it has is the one this
handler was already writing — which is what §20.3's consumer-first sequencing bought.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.conductor import JobHandler
from litharness.domain.draft import DraftPolicy, gate_draft
from litharness.domain.events import Event, EventType
from litharness.domain.jobs import Job
from litharness.domain.policy import (
    PolicyDecision,
    decide,
    decision_id_for,
    gates_for_draft,
    policy_digest,
)
from litharness.providers.base import CompletionRequest
from litharness.providers.registry import ProviderRegistry

#: Job kind this handler answers to.
SCENE_DRAFT = "scene_draft"


class HandlerInputError(Exception):
    """The job payload does not describe work this handler can do.

    Distinct from a gate refusal: a refusal is data (a veto the retry ladder can act on),
    while this is a malformed unit of work, which fails the job.
    """


def _timestamp(now: float) -> str:
    return datetime.fromtimestamp(now, tz=UTC).isoformat().replace("+00:00", "Z")


def make_scene_draft_handler(
    registry: ProviderRegistry,
    store: SqliteStore,
    project_id: str,
    *,
    policy: DraftPolicy | None = None,
    call_class: str = "generation",
) -> JobHandler:
    """Build a `JobHandler` that drafts one node's prose and gates the result.

    A closure rather than a class because `JobHandler` is a bare callable protocol and the
    Conductor needs no more than that — `handlers[SCENE_DRAFT] = make_scene_draft_handler(...)`
    is the whole wiring story, with no changes to the Conductor itself.
    """

    def handle(job: Job, now: float) -> Sequence[Event]:
        payload = job.payload
        try:
            revision_id = str(payload["revision_id"])
            logical_id = str(payload["logical_id"])
            prompt = str(payload["prompt"])
        except (KeyError, TypeError) as error:
            raise HandlerInputError(
                f"job {job.job_id} payload lacks revision_id/logical_id/prompt: {error}"
            ) from error

        revision = store.load_revision(revision_id)

        result, resolution = registry.complete(
            CompletionRequest(
                prompt=prompt,
                system=payload.get("system"),
                profile=str(payload.get("profile", "default")),
                call_class=call_class,
            )
        )

        outcome = gate_draft(
            revision,
            logical_id,
            result.text,
            conforms=result.conforms,
            policy=policy,
        )

        # §4.2's ladder produces a *decision*, not a boolean. Slice 4 approximated this
        # with a payload dict; contracts 1.1.0 made it an artifact, so the gate results,
        # the outcome, the provenance and the frozen policy digest now travel together and
        # can be queried later by job or by resulting revision.
        gates = gates_for_draft(outcome)
        verdict, reason = decide(
            gates,
            job_id=job.job_id,
            attempt=job.attempts,
            max_attempts=job.max_attempts,
        )
        decision = PolicyDecision(
            decision_id=decision_id_for(job.job_id, job.attempts, gates),
            outcome=verdict,
            gates=gates,
            job_id=job.job_id,
            logical_id=logical_id,
            base_revision_id=revision_id,
            resulting_revision_id=(
                outcome.revision.revision_id if outcome.accepted and outcome.revision else None
            ),
            attempt=job.attempts,
            # §5 rule 4 forbids a silent provider switch, so the fallback chain is recorded
            # even on refusal — a gate failure from a degraded fallback is a different
            # diagnosis from one from the primary.
            provider=result.provider,
            model=result.model,
            profile=str(payload.get("profile", "default")),
            fell_back_from=tuple(resolution.fell_back_from),
            invocations=result.invocations,
            total_tokens=result.usage.total,
            policy_config_digest=policy_digest(policy or DraftPolicy()),
            reason=reason,
        )
        store.record_decision(decision, decided_at=_timestamp(now))

        decision_event = Event(
            event_type=EventType.POLICY_DECISION_RECORDED,
            project_id=project_id,
            created_at=_timestamp(now),
            actor=result.provider,
            book_id=revision.book_id,
            branch_id=revision.branch_id,
            revision_id=decision.resulting_revision_id or revision_id,
            payload={
                "decision_id": decision.decision_id,
                "outcome": decision.outcome.value,
                "job_id": job.job_id,
                "attempt": job.attempts,
                "reason": reason,
                "gates": [
                    {"id": gate.rule_or_critic_id, "passed": gate.passed} for gate in gates
                ],
            },
        )

        if not outcome.accepted:
            return [
                Event(
                    event_type=EventType.MANUSCRIPT_CANDIDATE_CREATED,
                    project_id=project_id,
                    created_at=_timestamp(now),
                    actor=result.provider,
                    book_id=revision.book_id,
                    branch_id=revision.branch_id,
                    revision_id=revision_id,
                    payload={
                        "decision_id": decision.decision_id,
                        "job_id": job.job_id,
                        "logical_id": logical_id,
                        "accepted": False,
                        "vetoes": [veto.value for veto in outcome.veto_kinds],
                        "veto_details": [record.detail for record in outcome.vetoes],
                    },
                ),
                decision_event,
            ]

        assert outcome.revision is not None  # accepted implies a revision
        accepted = Event(
            event_type=EventType.MANUSCRIPT_REVISION_ACCEPTED,
            project_id=project_id,
            created_at=_timestamp(now),
            actor=result.provider,
            book_id=revision.book_id,
            branch_id=revision.branch_id,
            revision_id=outcome.revision.revision_id,
            payload={
                "decision_id": decision.decision_id,
                "job_id": job.job_id,
                "logical_id": logical_id,
                "accepted": True,
                "chars": outcome.chars,
                "parent_revision_id": revision_id,
            },
        )
        store.commit_revision(outcome.revision, created_at=_timestamp(now), events=[accepted])
        return [decision_event]
        # Returned empty: `commit_revision` already persisted the event in the same
        # transaction as the revision. Returning it as well would ask the Conductor to
        # append it a second time — harmless, because idempotency keys are content-derived
        # and collapse on insert, but it would misreport the tick's event count.
        return []

    return handle


__all__ = ["SCENE_DRAFT", "HandlerInputError", "make_scene_draft_handler"]
