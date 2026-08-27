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
from contextlib import suppress
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256

import litharness_contracts as lc

from litharness.application.conductor import JobHandler
from litharness.application.policy_events import policy_decision_event
from litharness.application.ports import DraftStore, TextGenerator
from litharness.application.repair import evaluation_job_for, summary_job_for
from litharness.domain.budget import BudgetPolicy, BudgetVerdict
from litharness.domain.budget import check as budget_check
from litharness.domain.draft import DraftPolicy, gate_draft
from litharness.domain.events import Event, EventType
from litharness.domain.extraction import extract_state
from litharness.domain.findings import DetectorInput
from litharness.domain.findings import Finding as DomainFinding
from litharness.domain.generation import PROFILES, CompletionRequest, Sampler
from litharness.domain.integrity import gate_integrity, gate_standing
from litharness.domain.jobs import Job
from litharness.domain.nodes import NodeKind
from litharness.domain.patch import Veto
from litharness.domain.policy import (
    GateKind,
    GateOutcome,
    Outcome,
    PolicyDecision,
    decide,
    decision_id_for,
    gates_for_draft,
    policy_digest,
)
from litharness.domain.revision import Revision, node_version_id
from litharness.domain.text import content_hash

#: Job kind this handler answers to.
SCENE_DRAFT = "scene_draft"


class HandlerInputError(Exception):
    """The job payload does not describe work this handler can do.

    Distinct from a gate refusal: a refusal is data (a veto the retry ladder can act on),
    while this is a malformed unit of work, which fails the job.
    """


def _timestamp(now: float) -> str:
    return datetime.fromtimestamp(now, tz=UTC).isoformat().replace("+00:00", "Z")


def _stale_base(
    store: DraftStore,
    job: Job,
    revision: Revision,
    project_id: str,
    logical_id: str,
    head_revision_id: str,
    now: float,
) -> Sequence[Event]:
    """Refuse a candidate planned against a base that is no longer the head.

    ESCALATE rather than RETRY: the payload's base is frozen and `save_job` never rewrites
    a payload, so retrying would re-read the same stale id forever. Clearing it is an
    operator act — `replan` mints fresh work against the current head.
    """
    gate = GateOutcome(
        gate=GateKind.SHAPE,
        rule_or_critic_id="shape.stale_base.v0",
        passed=False,
        vetoes=(Veto.STALE_BASE_VERSION,),
        detail=(
            f"planned against {revision.revision_id[:12]} but the head is now "
            f"{head_revision_id[:12]}; drafting would fork the branch"
        ),
    )
    decision = PolicyDecision(
        decision_id=decision_id_for(job.job_id, job.attempts, (gate,)),
        outcome=Outcome.ESCALATE,
        gates=(gate,),
        job_id=job.job_id,
        logical_id=logical_id,
        base_revision_id=revision.revision_id,
        attempt=job.attempts,
        reason=gate.detail,
    )
    store.record_decision(decision, decided_at=_timestamp(now))
    return [
        policy_decision_event(
            decision,
            project_id=project_id,
            created_at=_timestamp(now),
            book_id=revision.book_id,
            branch_id=revision.branch_id,
            revision_id=revision.revision_id,
            details={"head_revision_id": head_revision_id},
        )
    ]


def budget_gate(verdict: BudgetVerdict) -> GateOutcome:
    """Project a budget verdict into §4.2's ladder as a recorded gate result.

    A budget refusal is auditable through the same path as a shape refusal rather than
    being a special case an operator has to know to look for.
    """
    return GateOutcome(
        gate=GateKind.BUDGET,
        rule_or_critic_id=f"budget.{verdict.ceiling}.v0",
        passed=verdict.allowed,
        vetoes=(),
        detail=verdict.reason,
    )


#: Ceiling for the derived seed. Ollama takes a 32-bit signed seed; a Python `int` from a
#: sha256 does not fit and is not rejected — it is silently reinterpreted, which would make
#: "the same job replays to the same prose" false in a way nothing would report.
_SEED_MODULUS = 2**31 - 1


def draft_sampler(job: Job, profile: str) -> Sampler:
    """The decoding settings for one attempt at one job.

    **Derived from the job's own content, so it is reproducible without being constant.** A
    pinned `seed=7` gives every scene in the book the same sample path; a random seed gives a
    run nobody can replay. `input_digest` is already a content address over the job's inputs,
    so seeding from it means the same job re-run draws the same prose and two different
    scenes draw differently — which is the property a fixed constant was reaching for and
    the wrong way round.

    **`attempts` is in the seed on purpose, and it is the half that matters.** The prompt is
    frozen onto the payload at plan time and re-read verbatim on every attempt, so with a
    seed that did not move, a refused draft was regenerated byte-identically and met the
    identical refusal until the attempt budget poisoned the unit — three model calls to
    receive one answer three times. Attempt *n* now draws a different sample of the same
    request, which is what makes the retry ladder a ladder. The cost is that a crash-replay
    of one attempt reproduces that attempt and not its predecessor, which is the correct
    trade: replay fidelity is per-attempt, and an attempt is what the job records.

    A job with no `input_digest` — one enqueued by hand — falls back to its id, which is
    still stable per job and per attempt.
    """
    sampler = PROFILES.get(profile, PROFILES["default"])
    if sampler.temperature == 0.0:
        # Greedy decoding samples nothing, so a seed here would be a number in a record that
        # changed no output. Measured: three distinct seeds returned byte-identical text.
        return sampler
    material = f"{job.input_digest or job.job_id}:{job.attempts}"
    return replace(
        sampler, seed=int(sha256(material.encode()).hexdigest()[:16], 16) % _SEED_MODULUS
    )


def make_scene_draft_handler(
    registry: TextGenerator,
    store: DraftStore,
    project_id: str,
    *,
    policy: DraftPolicy | None = None,
    budget: BudgetPolicy | None = None,
    call_class: str = "generation",
    schedule_evaluation: bool = False,
    schedule_summary: bool = False,
) -> JobHandler:
    """Build a `JobHandler` that drafts one node's prose and gates the result.

    A closure rather than a class because `JobHandler` is a bare callable protocol and the
    Conductor needs no more than that — `handlers[SCENE_DRAFT] = make_scene_draft_handler(...)`
    is the whole wiring story, with no changes to the Conductor itself.
    """
    budget_policy = budget or BudgetPolicy()

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

        # Resolved up here rather than beside the provider call, because every decision this
        # handler can record — including the two refusals in front of the spend — has to
        # cite the configuration the attempt would have run under. A refusal recorded with
        # a digest that omits the sampler is a record of a different run.
        profile = str(payload.get("profile", "default"))
        sampler = draft_sampler(job, profile)
        config_digest = policy_digest(policy or DraftPolicy(), sampler)

        revision = store.load_revision(revision_id)

        # **Crash-after-commit must not file a false exception.** This handler commits the
        # revision itself (only `commit_revision` puts a revision and its event in one
        # transaction), while the job's SUCCEEDED write happens later in `_settle`, in a
        # different one. A crash between them leaves the row RUNNING; `reclaim_expired`
        # requeues it; the re-run finds the node now has content and `gate_draft` returns
        # TARGET_HAS_NO_CONTENT, which `decide` escalates on the first attempt — parking a
        # unit and filing an exception for work that *succeeded*. Safe because the decision
        # is recorded before the commit, so "content present and an ACCEPT decision for
        # this job" is only reachable after the commit landed.
        prior = store.latest_decision_for(job.job_id)
        if prior is not None and prior.outcome is Outcome.ACCEPT:
            with suppress(KeyError):
                if revision.node(logical_id).content is not None:
                    return []
            if prior.resulting_revision_id is not None:
                return []

        # **A stale base silently forks the book.** The payload freezes a base revision at
        # enqueue time, and every acceptance writes `branch_heads` unconditionally. Six jobs
        # planned against one base therefore produce six *sibling* revisions, each holding
        # one drafted scene and five empty ones, each overwriting the head — final head with
        # one scene of prose, six accepted decisions, and no error anywhere. Refusing here
        # costs no tokens because it runs before the provider call. Only planner-minted work
        # carries book/branch, so a hand `enqueue` is unaffected.
        book_id, branch_id = payload.get("book_id"), payload.get("branch_id")
        selected = payload.get("selected_by") or {}
        if book_id and branch_id:
            head = store.head(str(book_id), str(branch_id))
            if head is not None and head.revision_id != revision_id:
                return _stale_base(
                    store, job, revision, project_id, logical_id, head.revision_id, now
                )

        # **§4.2 ladder step 3's pre-flight half, in front of the spend.** A finding already
        # on record against this node cannot be caused or cleared by the candidate, so
        # generating one to discover a refusal that was knowable beforehand costs three model
        # calls and then poisons the unit — leaving nothing to resume when the operator does
        # the right thing and dismisses the finding. `refused_before_work` names this gate so
        # the Conductor gives the attempt back; see §19.1's rule, this being its third
        # instance.
        standing = (
            store.findings(str(book_id), str(branch_id), logical_id=logical_id, open_only=True)
            if book_id and branch_id
            else []
        )
        standing_gate = gate_standing(standing)
        if not standing_gate.passed:
            refusal = PolicyDecision(
                decision_id=decision_id_for(job.job_id, job.attempts, (standing_gate,)),
                outcome=Outcome.PARK,
                gates=(standing_gate,),
                job_id=job.job_id,
                logical_id=logical_id,
                base_revision_id=revision_id,
                attempt=job.attempts,
                policy_config_digest=config_digest,
                reason=standing_gate.detail,
            )
            store.record_decision(refusal, decided_at=_timestamp(now))
            return [
                policy_decision_event(
                    refusal,
                    project_id=project_id,
                    created_at=_timestamp(now),
                    book_id=revision.book_id,
                    branch_id=revision.branch_id,
                    revision_id=revision_id,
                    details={"findings": [item.finding_id for item in standing if item.blocks]},
                )
            ]

        request = CompletionRequest(
            prompt=prompt,
            system=payload.get("system"),
            profile=profile,
            call_class=call_class,
            sampler=sampler,
        )

        # **§4.2 gate 4, in front of the spend rather than behind it.** A budget check that
        # runs after the provider call records an overrun; it does not prevent one. The
        # provider is resolved first only to know whose harness tax to project against —
        # resolution costs nothing but a cached health verdict.
        day = _timestamp(now)[:10]
        provider_name, _ = registry.resolve(call_class)
        budget_verdict = budget_check(
            budget_policy,
            store.spend_on(day),
            provider=provider_name.name,
            prompt_chars=request.input_chars,
            max_output_tokens=request.max_output_tokens,
        )
        if not budget_verdict.allowed:
            # Nothing was spent, so `invocations` and `total_tokens` stay zero — that is
            # the point of refusing in front. The outcome is PARK rather than RETRY: the
            # daily ceiling will still be there next tick, so retrying would burn the
            # attempt budget rediscovering a fact that does not change until the day does.
            gate = budget_gate(budget_verdict)
            refusal = PolicyDecision(
                decision_id=decision_id_for(job.job_id, job.attempts, (gate,)),
                outcome=Outcome.PARK,
                gates=(gate,),
                job_id=job.job_id,
                logical_id=logical_id,
                base_revision_id=revision_id,
                attempt=job.attempts,
                policy_config_digest=config_digest,
                reason=budget_verdict.reason,
            )
            store.record_decision(refusal, decided_at=_timestamp(now))
            return [
                Event(
                    event_type=EventType.BUDGET_EXHAUSTED,
                    project_id=project_id,
                    created_at=_timestamp(now),
                    book_id=revision.book_id,
                    branch_id=revision.branch_id,
                    revision_id=revision_id,
                    payload={
                        "decision_id": refusal.decision_id,
                        "job_id": job.job_id,
                        "ceiling": budget_verdict.ceiling,
                        "reason": budget_verdict.reason,
                        "projected_tokens": budget_verdict.projected_tokens,
                        "spent_today": store.spend_on(day).tokens,
                    },
                )
            ]

        result, resolution = registry.complete(request)

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

        # §4.2 ladder step 3, and the first gate in the wired path that is about the *book*
        # rather than about the string. It runs only on a candidate that cleared shape:
        # integrity over text the shape gate refused would be a second opinion on a draft
        # that is already going back, and it would cost a store read per refusal.
        findings: list[DomainFinding] = []
        # §12 step 5's output. Empty when the job carries no book scope — a hand `enqueue`
        # against a bare revision. Bound here rather than inside the branch because the
        # acceptance path below reads it unconditionally, and an unbound name there would
        # turn a scene with no system voice into a failed job.
        extracted: tuple[lc.StateRecord, ...] = ()
        if outcome.accepted and book_id and branch_id:
            stored_records = tuple(store.state_records(str(book_id), str(branch_id)))
            # **Before the gate, not after acceptance**, which is the whole point. Extracting
            # afterwards would make the detector a report on canon already written; extracting
            # here means the facts this scene asserts are judged against established canon
            # while refusing is still free — the node stays empty, nothing commits, and the
            # finding drives the ladder. `node_after.content` rather than `result.text`
            # because `gate_draft` canonicalizes, and a span measured against the raw provider
            # string points at the wrong characters once NFC and line endings are applied.
            if outcome.node_after is not None:
                extracted = extract_state(
                    outcome.node_after.content or "",
                    known=stored_records,
                    project_id=project_id,
                    book_id=str(book_id),
                    branch_id=str(branch_id),
                    logical_id=logical_id,
                    version_id=node_version_id(outcome.node_after),
                    # A book with no imported snapshot has no story-time vocabulary, so every
                    # scene it writes is unplaceable and §12 step 5 extracts nothing from it
                    # forever — which is Book Zero. A chronological template is entitled to
                    # say where its beats sit; `stated_position` accepts that answer only
                    # when the book itself is silent.
                    stated_order_key=(
                        str(selected["story_order_key"])
                        if selected.get("story_order_key")
                        else None
                    ),
                )
            subject = DetectorInput(
                book_id=str(book_id),
                branch_id=str(branch_id),
                logical_id=logical_id,
                candidate=result.text,
                records=stored_records + extracted,
                plan_items=tuple(store.plan_items(str(book_id), str(branch_id))),
                # **The rest of the book, so a scene can be compared against it.** Read off
                # the base revision rather than the candidate's, because the candidate's does
                # not exist yet — and taken in reading order and excluding this node, so a
                # scene is never compared against itself. Without this
                # `detect_duplicate_scene` runs on every draft and finds nothing, which is a
                # detector that is present and inert: the shape §19.1 spends a paragraph on.
                prior_prose=tuple(
                    (node.logical_id, node.content)
                    for node in revision.in_reading_order()
                    if node.kind is NodeKind.SCENE
                    and node.content
                    and node.logical_id != logical_id
                ),
                ordinal=int(selected.get("ordinal", 0) or 0),
                of_total=int(selected.get("of_total", 0) or 0),
                # The promise ledger's open rows, for `promise.overdue.v0` — supplied the
                # way `prior_prose` is, so the detector stays a pure function of its input.
                # Model-sourced rows; the detector can only annotate (MINOR, heuristic).
                open_promises=tuple(store.promises(str(book_id), str(branch_id), open_only=True)),
                # The template's coordinate for this beat, same payload slot extraction
                # reads as `stated_order_key`. None when the sheet is not chronological,
                # and None makes the overdue check abstain exactly as milestones do.
                story_order_key=(
                    str(selected["story_order_key"]) if selected.get("story_order_key") else None
                ),
            )
            # `standing` was read and cleared before the generation, so this pass judges
            # only what the in-process detectors say about *this* candidate — which is why
            # its refusal costs an attempt where the pre-flight one does not.
            integrity, findings = gate_integrity(subject)
            gates = (*gates, standing_gate, integrity)

        # **`accepted` is the whole ladder's verdict, not the shape gate's.** Kept as its own
        # name rather than by rewriting `outcome`, because `outcome.vetoes` is what the
        # refusal event reports and a rewritten outcome would report a candidate refused with
        # no reason attached — the shape gate passed, so it has none to give. The integrity
        # gate's veto lives on its own `GateOutcome`, which `decide` and the decision record
        # already read.
        accepted = outcome.accepted and all(gate.passed for gate in gates if gate.blocking)

        if findings:
            # Recorded whether or not they block. A minor finding dropped because it was not
            # fatal is exactly the annotation §10.2 wants instrumented from Book Zero onward,
            # and a queue that only remembers the fatal ones cannot show a trend.
            #
            # **Recorded whether or not the candidate was accepted, too, and that is
            # deliberate rather than incidental** — checked when a duplicate-scene refusal
            # made it visible for the first time. A finding a refused candidate produced
            # becomes *standing* against the beat, so the next attempt parks pre-flight and
            # free instead of spending a second generation to rediscover it. Slice 9 measured
            # that trade at 12 calls and 8,599 tokens before against 3 and 1,912 after, and
            # `test_a_scene_contradicting_established_canon_is_refused_and_writes_nothing`
            # pins the resulting tick sequence. The finding is node-scoped — "attempts at
            # this beat keep producing this defect" — rather than a claim that the book
            # contains the refused prose, and the operator's route past it is the one that
            # already exists: dismiss, then revive.
            store.record_findings(
                str(book_id),
                str(branch_id),
                findings,
                created_at=_timestamp(now),
                revision_id=revision_id,
            )

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
                outcome.revision.revision_id if accepted and outcome.revision else None
            ),
            attempt=job.attempts,
            # §5 rule 4 forbids a silent provider switch, so the fallback chain is recorded
            # even on refusal — a gate failure from a degraded fallback is a different
            # diagnosis from one from the primary.
            provider=result.provider,
            model=result.model,
            profile=profile,
            fell_back_from=tuple(resolution.fell_back_from),
            invocations=result.invocations,
            total_tokens=result.usage.total,
            cost_usd=result.cost_usd,
            policy_config_digest=config_digest,
            reason=reason,
        )
        decision_event = policy_decision_event(
            decision,
            project_id=project_id,
            created_at=_timestamp(now),
            actor=result.provider,
            book_id=revision.book_id,
            branch_id=revision.branch_id,
            revision_id=decision.resulting_revision_id or revision_id,
        )

        if not accepted:
            store.record_decision(decision, decided_at=_timestamp(now))
            failed = [gate for gate in gates if gate.blocking and not gate.passed]
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
                        # Read off the failing gates rather than off `outcome`, so an
                        # integrity refusal reports its own veto instead of an empty list —
                        # the shape gate passed and has nothing to say about it.
                        "vetoes": [veto.value for gate in failed for veto in gate.vetoes],
                        "veto_details": [gate.detail for gate in failed if gate.detail],
                        "findings": [item.finding_id for item in findings if item.blocks],
                    },
                ),
                decision_event,
            ]

        assert outcome.revision is not None  # accepted implies a revision
        acceptance = Event(
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
        # The revision, its acceptance event and the state read out of it, in one
        # transaction — §12 step 8 literally. `StateCandidatesExtracted` rides along only
        # when something was extracted: an event per empty extraction would be one per
        # accepted scene forever, and its payload carries no insert count because that
        # differs between a run and its replay while the idempotency key does not.
        commit_events = [acceptance]
        if extracted:
            commit_events.append(
                Event(
                    event_type=EventType.STATE_CANDIDATES_EXTRACTED,
                    project_id=project_id,
                    created_at=_timestamp(now),
                    book_id=revision.book_id,
                    branch_id=revision.branch_id,
                    revision_id=outcome.revision.revision_id,
                    payload={
                        "decision_id": decision.decision_id,
                        "logical_id": logical_id,
                        "count": len(extracted),
                        "order_key": next(
                            (
                                record.story_position.order_key
                                for record in extracted
                                if record.story_position
                            ),
                            None,
                        ),
                        "record_ids": sorted(record.record_id for record in extracted),
                    },
                )
            )
        follow_up_jobs = (
            (
                evaluation_job_for(
                    book_id=revision.book_id,
                    branch_id=revision.branch_id,
                    revision_id=outcome.revision.revision_id,
                    logical_id=logical_id,
                ),
            )
            if schedule_evaluation
            else ()
        )
        # **Summarise the scene that was just accepted, at the lowest priority in the system.**
        # Its value is entirely in the future — the summary is read once the budget stops
        # holding this scene's prose, dozens of scenes later — so it must never outrank
        # writing the next one. Minted with the accepted text's own content hash, so an
        # untouched scene is summarised once for the life of the book and a repaired one
        # earns exactly one more.
        if schedule_summary and outcome.revision is not None:
            follow_up_jobs = (
                *follow_up_jobs,
                summary_job_for(
                    book_id=revision.book_id,
                    branch_id=revision.branch_id,
                    revision_id=outcome.revision.revision_id,
                    logical_id=logical_id,
                    content_hash=content_hash(result.text),
                ),
            )
        store.commit_revision(
            outcome.revision,
            created_at=_timestamp(now),
            events=commit_events,
            state_records=extracted,
            jobs=follow_up_jobs,
            decision=decision,
        )

        # `acceptance` is deliberately **not** returned: `commit_revision` already persisted it
        # in the same transaction as the revision, and returning it as well would ask the
        # Conductor to append it a second time — harmless, because idempotency keys are
        # content-derived and collapse on insert, but it would misreport the tick's event
        # count. The decision event retains the established Conductor-owned write path and
        # is returned here; only the decision record itself must share the revision commit.
        return [decision_event]

    return handle


__all__ = ["SCENE_DRAFT", "HandlerInputError", "make_scene_draft_handler"]
