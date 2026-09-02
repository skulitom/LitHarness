"""Job handlers: the seam where a provider call becomes an accepted revision.

Until this module existed, `providers/registry.py` had no consumer anywhere outside its
own package — four working adapters, a conformance suite, a billing guard, and nothing
that ever called them. PLAN.md §20.4 attributed that to missing subsystems ("the first
real handler is a Stage 1 concern: a scene draft needs a plan and a context packet").
Half true. A *planned* scene draft does need those. Wiring did not: what it needed was
for a job to carry its input, which migration 003 added.

**Who commits what.** This handler writes the revision through `commit_revision`, which puts
the artifact, its acceptance event, and its policy decision in one transaction. The
Conductor commits the later job-status transition and any events returned here. That residual
gap is real and is handled by replay checks plus content-derived ids: a crash after the
artifact commit converges instead of duplicating or falsely refusing completed work.

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

from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

import litharness_contracts as lc

from litharness.application import tells_pass
from litharness.application.conductor import JobHandler
from litharness.application.editorial import reader_jobs_for_checkpoint
from litharness.application.exemplars import Shelf, gate_exemplar_leak
from litharness.application.policy_events import policy_decision_event
from litharness.application.ports import DraftStore, TextGenerator
from litharness.application.repair import evaluation_job_for, summary_job_for
from litharness.application.reviser import (
    REVISION_MODEL,
    REVISION_PROFILE,
    render_revision_request,
)
from litharness.domain import tells
from litharness.domain.budget import BudgetPolicy, BudgetVerdict
from litharness.domain.budget import check as budget_check
from litharness.domain.draft import (
    DraftOutcome,
    DraftPolicy,
    gate_draft,
    strip_em_dash,
    strip_markup,
)
from litharness.domain.editorial import (
    InterventionRealization,
    ReaderMechanism,
    realization_id_for,
)
from litharness.domain.events import Event, EventType
from litharness.domain.extraction import extract_state
from litharness.domain.failures import OperationalFailure
from litharness.domain.findings import DetectorInput
from litharness.domain.findings import Finding as DomainFinding
from litharness.domain.generation import (
    PROFILES,
    CompletionRequest,
    CompletionResult,
    Sampler,
)
from litharness.domain.integrity import gate_integrity, gate_standing
from litharness.domain.jobs import Job
from litharness.domain.nodes import NodeKind
from litharness.domain.patch import Veto
from litharness.domain.policy import (
    GateKind,
    GateOutcome,
    Outcome,
    PolicyDecision,
    VerdictSource,
    decide,
    decision_id_for,
    gates_for_draft,
    policy_digest,
)
from litharness.domain.progression import gate_progression
from litharness.domain.reviser import (
    Breach,
    PreRevisionDraft,
    ReviserPolicy,
    contain,
    pre_revision_draft_id,
)
from litharness.domain.revision import Revision, node_version_id
from litharness.domain.serials import SerialShape
from litharness.domain.text import content_hash

#: Job kind this handler answers to.
SCENE_DRAFT = "scene_draft"
#: The tells pass's recorded verdict on the decision row (stage-0 §199).
TELLS_GATE = "tells.v0"


class HandlerInputError(Exception):
    """The job payload does not describe work this handler can do.

    Distinct from a gate refusal: a refusal is data (a veto the retry ladder can act on),
    while this is a malformed unit of work, which fails the job.
    """


def _timestamp(now: float) -> str:
    return datetime.fromtimestamp(now, tz=UTC).isoformat().replace("+00:00", "Z")


def _text(value: object) -> str | None:
    """A payload slot read as a string, or `None` for anything that is not one.

    A payload is JSON somebody wrote, so a reader that assumed a type would turn a malformed
    row into a crash in the middle of an accepted draft. Absent, null and wrong-typed all mean
    the same thing to every caller here: this payload does not carry that fact.
    """
    return value if isinstance(value, str) and value else None


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


#: The reviser's own gate id, in the family every deterministic gate on this ladder belongs to.
REVISION_GATE = "revision.containment.v0"


@dataclass(frozen=True, slots=True)
class _Ladder:
    """What one run of the deterministic ladder found, over one text (§187).

    **A value rather than a mutation, because the ladder now runs more than once.** §185 put
    the reviser in front of the gates so the revision would be judged by them; §187 puts the
    *draft* through them first so a doomed draft is never rewritten. That means two runs per
    revised scene, and a sequence of rebindings in one scope could not express which run the
    decision cites. Everything here is derived from the text in the `text` field and from
    store reads; nothing in it is persisted by the run that produced it.

    **There is nowhere in this to put a preference between two texts.** It carries a verdict
    about *one* candidate, exactly as `DraftOutcome` does, and the caller keeps the second run
    because it is the one over the adopted text — not because it scored better. §61(5) and
    §105.1 at a third address.
    """

    #: The candidate after §180's strip, which is the string `result.text` is rebound to.
    text: str
    #: How many em dashes the strip took out of *this* text.
    marks_removed: int
    outcome: DraftOutcome
    gates: tuple[GateOutcome, ...]
    extracted: tuple[lc.StateRecord, ...]
    findings: list[DomainFinding]
    accepted: bool
    #: Markdown markers the strip removed before the gates (`draft.strip_markup`); `0` for
    #: every text that carried none, and defaulted so the ladder's callers need no change.
    markup_removed: int = 0
    #: What the tells pass did to this text (`tells_pass.apply`), or `None` without a shelf,
    #: which is every book drafted before stage-0 §199 and every book with no ceiling.
    tells: tells_pass.TellsResult | None = None


def _revision_gate(passed: bool, detail: str | None) -> GateOutcome:
    """The reviser call's own recorded verdict. **Deliberately non-blocking, and it is not a
    craft gate.**

    `blocking` in this repository means *`decide` refuses the candidate when this fails*, and
    `decide` is never called on the reviser's decision: the consequence of a failed containment
    check is that one string is discarded before any ladder exists, which the handler does and
    the detail records. Marking it blocking would put a failed blocking gate on an `ACCEPT`
    decision, which is a decision record contradicting itself.

    `GateKind.SHAPE` rather than `CRAFT` for the reason `PolicyDecision.__post_init__` enforces
    one line away: a craft gate is a calibrated judgment about how good prose is, and nothing
    here judges prose. It compares two strings.
    """
    return GateOutcome(
        gate=GateKind.SHAPE,
        rule_or_critic_id=REVISION_GATE,
        passed=passed,
        verdict_source=VerdictSource.DETERMINISTIC,
        blocking=False,
        detail=detail,
    )


def revise_draft(
    registry: TextGenerator,
    store: DraftStore,
    job: Job,
    *,
    drafted: str,
    already_spent: CompletionResult,
    material: str | None,
    project_id: str,
    logical_id: str,
    revision_id: str,
    revision: Revision,
    budget_policy: BudgetPolicy,
    call_class: str,
    policy: ReviserPolicy,
    model: str | None,
    now: float,
) -> tuple[str, str | None, Sequence[Event]]:
    """One rewrite of one drafted scene: the text to carry forward, and what it cost.

    Returns `(text, reviser_model, events)`. `text` is the revision when containment held and
    the **draft unchanged** when it did not — every refusal path returns the draft, because the
    book must never be hostage to this stage. `reviser_model` is `None` when nothing was
    adopted, so the caller can attribute the accepted prose without inferring it from a
    comparison.

    **Where this sits is the whole design and it was read off the code rather than chosen.**
    It runs on an unaccepted string and in front of the ladder that judges what it returns, so
    the revision goes down the identical ladder the draft would have — shape, integrity and
    §184's beat comparison all read the revised prose. **§187 moved one thing and left that
    invariant standing**: the ladder now runs on the draft first and this call is made only if
    the draft cleared it, so `drafted` is the gated text (canonicalized, after `strip_em_dash`)
    rather than the provider's raw string, and the strip runs again on whatever comes back.
    The three alternatives were each refused by something already written down:

    * **A follow-on job rewriting accepted prose through `apply_patch`.** §184's gate could not
      re-run there. §184.4 abstains on *a position the book already wrote down*, and a scene
      that has committed has written its own snapshot at its own position — so the gate the
      directive requires to pass on the revision would abstain on every one of them. `patch`
      would also need a *located complaint* to license the rewrite (`Veto.UNLICENSED_DELETION`),
      and a register complaint located nowhere is exactly the licence this project refuses to
      manufacture. §180.7 records that the repair path is the one seam the em-dash strip does
      not reach, so the book's final prose would ship down it unstripped.
    * **A second accepted revision per scene.** The head would move twice, two
      `MANUSCRIPT_REVISION_ACCEPTED` events would name one scene, and a re-printed status line
      at an already-written position is the second canon snapshot at one key that
      `integrity.detect_contradictions` groups on and refuses.
    * **Leaving the revision unstripped.** The strip has to be the last rewrite before the gate
      on whichever text is adopted, or the mark read 1 and read 11 both named comes back
      through a door §180 had closed. It runs once per ladder pass rather than once per call,
      which keeps §180.4's third load-bearing detail — one text, one hash, one offset space —
      true of both passes, and makes the count on each pass a fact about that pass's author:
      the draft's marks are the writer's and the revision's are the reviser's.

    None of this makes `draft.py`'s rule false. *A draft may only fill emptiness; rewriting
    existing prose must route through `apply_patch`* is about prose the store holds, and
    `allow_overwrite` stays `False`: the node is empty when `gate_draft` runs and is filled
    exactly once. What that docstring warns against — *have it improve the scene it just
    wrote*, the open-ended loop RevisionBench's ~80% is the evidence against — is a loop that
    re-reads its own committed output. This is one bounded transformation of a string nothing
    has accepted, gated identically, with no second pass and no way to ask for one.
    """
    request = render_revision_request(drafted, material=material, model=model)
    stamp = _timestamp(now)

    def settle(gate: GateOutcome, result: object | None) -> Sequence[Event]:
        """Record the reviser's own decision, whatever became of its text.

        **Every provider call reaches `policy_decisions`, because nothing else is visible to
        the budget gate** (§105.3). A stage making one call per scene whose calls never landed
        there would spend them while the day's governor reported the day untouched — so this
        runs on the refusal paths too, where it meters zero and says why.

        The outcome is `ACCEPT` on every path, and that is a safety property rather than a
        verdict about the prose. `latest_decision_for` settles the *job* against `ORDER BY
        attempt DESC, rowid DESC`, and this row is written before the scene's own; a row that
        could carry `PARK` would poison a unit that drafted perfectly well if it ever came
        last. What this decision says is *a revision call was settled here and schedules
        nothing*; whether its text was adopted is on the gate and in the event's details.
        """
        spent = result if isinstance(result, CompletionResult) else None
        decision = PolicyDecision(
            decision_id=decision_id_for(job.job_id, job.attempts, (gate,)),
            outcome=Outcome.ACCEPT,
            gates=(gate,),
            job_id=job.job_id,
            logical_id=logical_id,
            base_revision_id=revision_id,
            attempt=job.attempts,
            provider=spent.provider if spent else None,
            model=spent.model if spent else None,
            profile=REVISION_PROFILE,
            invocations=spent.invocations if spent else 0,
            total_tokens=spent.usage.total if spent else 0,
            cost_usd=spent.cost_usd if spent else None,
            reason=gate.detail,
        )
        store.record_decision(decision, decided_at=stamp)
        return [
            policy_decision_event(
                decision,
                project_id=project_id,
                created_at=stamp,
                book_id=revision.book_id,
                branch_id=revision.branch_id,
                revision_id=revision_id,
                details={"adopted": gate.passed, "stage": "revision"},
            )
        ]

    # **In front of the spend, exactly as the drafting call's own check is.** A ceiling reached
    # here refuses the *revision* and never the scene: the draft is already paid for and
    # already good, and parking it because a second call could not be afforded would throw away
    # the thing the budget was spent on.
    #
    # **The drafting call this one follows is added by hand, and without that the ceiling is
    # under-counted by exactly one call per scene.** `spend_on` is a view over
    # `policy_decisions`, and the drafting call's decision is not written until the end of this
    # handler — inside `commit_revision` on the accepting path — so a second call *within the
    # same tick* reads a day that does not yet contain the first. A ceiling of one invocation
    # would admit two. `Spend.plus` exists for exactly this and is what §105.3's rule needs
    # here: the governor has to see the money before the row does.
    day = stamp[:10]
    provider, _ = registry.resolve(call_class)
    verdict = budget_check(
        budget_policy,
        store.spend_on(day).plus(
            invocations=already_spent.invocations,
            tokens=already_spent.usage.total,
            cost_usd=already_spent.cost_usd or 0.0,
        ),
        provider=provider.name,
        prompt_chars=request.input_chars,
        max_output_tokens=request.max_output_tokens,
    )
    if not verdict.allowed:
        return drafted, None, settle(budget_gate(verdict), None)

    try:
        result, _ = registry.complete(request)
    except OperationalFailure as error:
        # **A transport failure here leaves the draft standing rather than failing the job.**
        # `claude -p` fails under box load and the drafting call has already been paid for, so
        # letting this propagate would spend the scene's attempt budget on the second call's
        # weather and eventually poison a unit whose first call succeeded. The domain failure
        # vocabulary is what is caught, so nothing about a provider is imported here.
        gate = _revision_gate(False, f"the revision call failed: {error}")
        return drafted, None, settle(gate, None)

    held = contain(drafted, result.text, policy=policy)
    if not held.held:
        detail = held.detail
        if held.breach is not Breach.UNCHANGED:
            detail = f"{held.breach}: {detail}"
        return drafted, None, settle(_revision_gate(False, detail), result)

    return result.text, result.model, settle(_revision_gate(True, None), result)


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
    reader_mechanism: ReaderMechanism | None = None,
    reader_shape: SerialShape | None = None,
    revise: bool = False,
    reviser_policy: ReviserPolicy | None = None,
    reviser_model: str | None = REVISION_MODEL,
    shelf: Shelf | None = None,
) -> JobHandler:
    """Build a `JobHandler` that drafts one node's prose and gates the result.

    `shelf` is the exemplar shelf the selector showed the writer (stage-0 §196); the ladder
    also holds every draft to the shelf's own rate of the regular tells (`domain/tells.py`)
    and says the sentences over it again (`tells_pass`), stage-0 §199; without a shelf
    there is no ceiling, no call, and no change.
    then carries `gate_exemplar_leak`, which refuses a draft sharing a run of consecutive words
    with any exemplar. `None` — every book drafted without `--exemplars` — adds no gate row.

    A closure rather than a class because `JobHandler` is a bare callable protocol and the
    Conductor needs no more than that — `handlers[SCENE_DRAFT] = make_scene_draft_handler(...)`
    is the whole wiring story, with no changes to the Conductor itself.

    **`revise` turns on the reviser (§185), and it is a flag because §54's control arm has to
    stay reachable without editing code.** With it off, every line below is byte-identical to
    what it was: no second request is built, no second call is made, no second decision is
    written, and `policy_config_digest` omits the reviser key entirely — so a held-back run
    hashes the same as every scene drafted before the stage existed, which is what makes it a
    control rather than something that resembles one. §155.3's precedent at this address: a
    feature no flag can hold back is a control arm that needs a code edit.

    **It defaults off here and is turned on by `cli.py`, which is where the operator
    commissioned it.** `schedule_evaluation` and `schedule_summary` sit two arguments up with
    the same default for the same reason, and the reason is about which direction fails safe.
    A floor defaults on so a path that forgets it fails closed (`require_starting_sheet` says
    so in as many words); a **spend** defaults off, because a call site that forgot to think
    about a second model call per scene should get the book it already had rather than a bill
    it did not ask for. `litharness run` passes `revise=not args.no_revise`, so production has
    the stage and `--no-revise` is the control.
    """
    # **The shelf's own rate of each regular tell, read once** (stage-0 §199): the highest
    # density any placed opening reaches, family by family, is what a draft is held to.
    tells_limits = (
        tells.ceilings(exemplar.chapter for exemplar in shelf.exemplars)
        if shelf is not None
        else None
    )

    # **Every call the pass makes, kept so the spend reaches a decision row** (§199.1): pilot
    # 24's redraw counted forty-five rewrite calls on its acceptance events and none on the
    # spend ledger, so the arm's cost was a floor. Cleared before each ladder run.
    tells_calls: list[CompletionResult] = []

    def _say_again(request: CompletionRequest) -> Mapping[str, Any] | None:
        """One family's located sentences, said again in a batch (§199.3); a failed call, or
        an answer that is not the labelled object the schema asks for, leaves every sentence
        in the batch as drafted."""
        try:
            answer, _resolution = registry.complete(request)
        except OperationalFailure:
            return None
        tells_calls.append(answer)
        return answer.parsed if isinstance(answer.parsed, Mapping) else None

    budget_policy = budget or BudgetPolicy()
    revision_policy = reviser_policy or ReviserPolicy()
    #: Absent rather than null when the stage is off; see `policy_digest`.
    reviser_config = (
        {
            "model": reviser_model,
            "profile": REVISION_PROFILE,
            **revision_policy.digest_material(),
        }
        if revise
        else None
    )

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
        config_digest = policy_digest(policy or DraftPolicy(), sampler, reviser_config)

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

        # Captured before anything rebinds `result`: the ladder below runs twice and both runs
        # judge the same provider answer's schema conformance, which is a property of the call
        # rather than of either text.
        conforms = result.conforms

        def run_ladder(candidate: str) -> _Ladder:
            """§180's strip, then shape, then integrity, then §184's beat, over one text.

            **Minting nothing.** Everything here is a pure function or a store *read*:
            `gate_draft` returns a revision without persisting it, `extract_state` returns
            records, `gate_integrity` returns findings. Which is what makes it safe to run
            twice — the caller decides which run is the verdict of record and only that run's
            findings are written.
            """
            # **The one punctuation rewrite this system performs, and it happens here rather
            # than anywhere later for a reason that is about hashes and not about prose**
            # (§180). Three sites below still read `result.text` — the duplicate-scene
            # detector's `candidate`, and two `content_hash` calls — so a rewrite applied
            # inside `gate_draft` would leave them describing a string that was never stored.
            # Stripping before the gate keeps one text, one hash and one offset space, which is
            # also why it cannot be done as a migration over prose already in the store: every
            # open finding's span is measured against the text as committed. **It therefore
            # runs once per ladder run rather than once per handler call** (§187): each run
            # judges its own text, and the strip is still the last rewrite before the gate on
            # whichever text is adopted, which is all §185.2's argument ever required.
            stripped, marks = strip_em_dash(candidate)
            # The markup strip rides the em-dash strip's seat and its rules: after the model,
            # before the gate, machine lines untouched, the count on the record.
            stripped, markup = strip_markup(stripped)
            # **The tells pass rides the same seat** (stage-0 §199): after the model, before
            # the gate, one text and one hash. Each sentence of a regular family over the
            # shelf's own rate is said again by a model and verified by the locator; with no
            # shelf there is no ceiling and no call, and the ladder is the ladder it was.
            tells_result: tells_pass.TellsResult | None = None
            if tells_limits is not None:
                tells_result = tells_pass.apply(
                    stripped, limits=tells_limits, complete=_say_again
                )
                stripped = tells_result.text
            outcome = gate_draft(
                revision,
                logical_id,
                stripped,
                conforms=conforms,
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
                    candidate=stripped,
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
                    open_promises=tuple(
                        store.promises(str(book_id), str(branch_id), open_only=True)
                    ),
                    # The template's coordinate for this beat, same payload slot extraction
                    # reads as `stated_order_key`. None when the sheet is not chronological,
                    # and None makes the overdue check abstain exactly as milestones do.
                    story_order_key=(
                        str(selected["story_order_key"])
                        if selected.get("story_order_key")
                        else None
                    ),
                )
                # `standing` was read and cleared before the generation, so this pass judges
                # only what the in-process detectors say about *this* candidate — which is why
                # its refusal costs an attempt where the pre-flight one does not.
                integrity, findings = gate_integrity(subject)
                gates = (*gates, standing_gate, integrity)

                # **§4.2's ladder, one rung further: did the scheduled beat land?** (§184) The
                # plan told this scene which of the book's quantities moves in it, and until now
                # nothing compared that ask against the state the scene wrote down — so the beat
                # rode the prompt, extraction read a snapshot off the prose, and the two never
                # met. Both halves of the ask were recorded on the payload when the work was
                # selected, so nothing is re-derived here: the gate reads two frozen strings and
                # compares two integers out of `stored_records` and `extracted`, which are the
                # same two values the integrity gate was handed above. `None` on every scene whose
                # plan named no quantity, and the ladder is then byte-identical to what it was.
                beat_gate = gate_progression(
                    _text(selected.get("progression_beat")),
                    _text(selected.get("progression_column")),
                    before=stored_records,
                    extracted=extracted,
                    at=(
                        str(selected["story_order_key"])
                        if selected.get("story_order_key")
                        else None
                    ),
                )
                if beat_gate is not None:
                    gates = (*gates, beat_gate)

            # **`accepted` is the whole ladder's verdict, not the shape gate's.** Kept as its
            # own name rather than by rewriting `outcome`, because `outcome.vetoes` is what
            # the refusal event reports and a rewritten outcome would report a candidate
            # refused with no reason attached — the shape gate passed, so it has none to give.
            # The integrity gate's veto lives on its own `GateOutcome`, which `decide` and the
            # decision record already read.
            #
            # **Nothing shown as register may reach the page as text** (§196). Runs over the
            # stripped candidate whatever the shape gate said, so a lifted run is refused on
            # the same attempt that would otherwise have been accepted; `None` without a
            # shelf, which keeps every other book's ladder the ladder it was.
            leak_gate = gate_exemplar_leak(stripped, shelf)
            if leak_gate is not None:
                gates = (*gates, leak_gate)
            # The pass's own recorded verdict: a report, never blocking, so the decision row
            # carries the rates before and after and what was left as drafted.
            if tells_result is not None:
                gates = (
                    *gates,
                    GateOutcome(
                        gate=GateKind.SHAPE,
                        rule_or_critic_id=TELLS_GATE,
                        passed=not tells.over(stripped, tells_limits),
                        blocking=False,
                        detail=tells_result.detail,
                    ),
                )
            return _Ladder(
                text=stripped,
                marks_removed=marks,
                markup_removed=markup,
                tells=tells_result,
                outcome=outcome,
                gates=gates,
                extracted=extracted,
                findings=findings,
                accepted=outcome.accepted
                and all(gate.passed for gate in gates if gate.blocking),
            )

        # **The deterministic ladder runs on the draft, and the reviser is only paid for a
        # draft that cleared it** (§187; recommendation 1b of `plan/agent-impact/REPORT.md`).
        # §185 put the second call in front of the ladder so the revision would be judged by
        # it, and that half is unchanged — what moved is that the *draft* is judged first.
        # `plan/agent-impact/reviser-impact.md` §2 measured why: three of five reviser calls on
        # the audited chapter bought text `integrity.progression.v0` then refused, and §185.3's
        # own containment argument is that the machine lines are byte-identical **so that
        # gate's verdict cannot change** — so those rewrites were incapable of altering the
        # outcome they were paid for, by the design's own reasoning. A refused draft now costs
        # the writer's call and nothing else.
        tells_calls.clear()
        ladder = run_ladder(result.text)

        # **One draft in, one revision out: no second candidate, no scoring, nothing choosing
        # between two texts** (§185; the operator's read-12 directive). `revise_draft` returns
        # the draft untouched on every refusal path, so a failed containment check, an
        # exhausted ceiling and a dead transport all leave the scene exactly where it was.
        revised_by: str | None = None
        revision_events: Sequence[Event] = ()
        #: The prose this attempt would have committed under `--no-revise`, kept only when a
        #: revision was adopted over it (§187). Canonicalized and stripped, so a later diff
        #: against the accepted node compares prose against prose.
        superseded: tuple[str, int] | None = None
        if revise and ladder.accepted:
            assert ladder.outcome.node_after is not None  # accepted implies a filled node
            gated_draft = ladder.outcome.node_after.content or ""
            revised, revised_by, revision_events = revise_draft(
                registry,
                store,
                job,
                # **The text the reviser rewrites is the text the ladder passed**, which is
                # the gated draft rather than the provider's raw string. Handing it the raw
                # one would mean the ladder approved a text and a different text was rewritten
                # — and a diff of the kept draft against the accepted prose would then
                # attribute NFC normalisation, line-ending unification and every §180 em-dash
                # rewrite to the reviser. One text, one offset space (§180.4), now on both
                # sides of the call.
                drafted=gated_draft,
                already_spent=result,
                material=_text(payload.get("packet")),
                project_id=project_id,
                logical_id=logical_id,
                revision_id=revision_id,
                revision=revision,
                budget_policy=budget_policy,
                call_class=call_class,
                policy=revision_policy,
                model=reviser_model,
                now=now,
            )
            if revised_by is not None:
                # **The ladder re-runs, on the adopted text, and this run is the verdict of
                # record.** §185's invariant is that the accepted text passed the gates, and
                # it survives the reorder intact: the shape gate is the one that can change
                # its verdict here (§185.3), and it does so on the revision.
                superseded = (gated_draft, ladder.marks_removed)
                ladder = run_ladder(revised)
            # Nothing is re-run when containment refused: `revise_draft` returned the draft
            # unchanged, so a second pass over the identical string would spend two store
            # reads to reproduce a verdict already in hand.

        outcome = ladder.outcome
        gates = ladder.gates
        extracted = ladder.extracted
        findings = ladder.findings
        accepted = ladder.accepted
        marks_removed = ladder.marks_removed
        markup_removed = ladder.markup_removed
        tells_record = ladder.tells.to_jsonable() if ladder.tells is not None else None
        if tells_calls and ladder.tells is not None:
            # **The pass's spend, on a row of its own** (§199.1), the reviser's shape: the
            # drafting call's row names the drafting call, and forty-five rewrites are not
            # that call. One row per ladder run, `ACCEPT` because a rewrite refused by the
            # locator is a sentence left as drafted and not a refusal of the draft.
            costs = [call.cost_usd for call in tells_calls if call.cost_usd is not None]
            store.record_decision(
                PolicyDecision(
                    decision_id=decision_id_for(f"tells:{job.job_id}", job.attempts, ()),
                    outcome=Outcome.ACCEPT,
                    gates=(),
                    job_id=job.job_id,
                    logical_id=logical_id,
                    base_revision_id=revision_id,
                    attempt=job.attempts,
                    provider=tells_calls[0].provider,
                    model=tells_calls[0].model,
                    profile=tells_pass.REWRITE_PROFILE,
                    invocations=sum(call.invocations for call in tells_calls),
                    total_tokens=sum(call.usage.total for call in tells_calls),
                    cost_usd=sum(costs) if costs else None,
                    reason=ladder.tells.detail,
                ),
                decided_at=_timestamp(now),
            )
        result = replace(result, text=ladder.text)

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
                # The reviser's own decision event first, because its call happened first.
                # **Empty whenever the draft is what was refused** (§187): the second call is
                # not made at all on that path, so a candidate refused here was paid for twice
                # only when the revision is the text that failed.
                *revision_events,
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
                # **Removing the mark from the prose would otherwise remove the only way to
                # see how often the model reached for it** (§180). The rate is the quantity
                # read 1 and read 11 both named, and a census over published books after this
                # ships would read zero and mean nothing; this is where it stays visible.
                "em_dashes_removed": marks_removed,
                "markup_removed": markup_removed,
                # What the tells pass did (stage-0 §199), or `None` for a book with no shelf:
                # the rates per family before and after, and the sentences left as drafted.
                "tells": tells_record,
                # **Which model's sentences these are, when they are not the writer's** (§185).
                # The decision this event names attributes the *candidate* to the drafting
                # call, and that stays true — but the accepted prose came out of a second call
                # when this field is set, and a provenance record that named only the writer
                # would be §56.2's defect at a second address: confidently naming a model that
                # did not write what is on the page. `None` when nothing was adopted, so the
                # absence is the fact rather than a value to be interpreted, and the reviser's
                # own decision row carries the spend that goes with it.
                "revised_by": revised_by,
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
        if (
            reader_mechanism is not None
            and reader_shape is not None
            and outcome.revision is not None
            and selected.get("chapter_end") is True
        ):
            chapter_index = selected.get("chapter_index")
            if isinstance(chapter_index, int) and not isinstance(chapter_index, bool):
                follow_up_jobs = (
                    *follow_up_jobs,
                    *reader_jobs_for_checkpoint(
                        outcome.revision,
                        logical_id,
                        chapter_index=chapter_index,
                        summaries=store.scene_summaries(revision.book_id, revision.branch_id),
                        prior_observations=store.reader_observations(
                            revision.book_id, revision.branch_id
                        ),
                        mechanism=reader_mechanism,
                        shape=reader_shape,
                    ),
                )
        realizations: tuple[InterventionRealization, ...] = ()
        plan_revision_id = job.payload.get("plan_revision_id")
        if isinstance(plan_revision_id, str) and plan_revision_id:
            realized: list[InterventionRealization] = []
            for intervention in store.editorial_interventions_targeting(
                revision.book_id,
                revision.branch_id,
                logical_id,
                plan_revision_id,
            ):
                if intervention.directive_id is None:
                    continue
                realized.append(
                    InterventionRealization(
                        realization_id=realization_id_for(
                            intervention.intervention_id,
                            outcome.revision.revision_id,
                            logical_id,
                        ),
                        intervention_id=intervention.intervention_id,
                        directive_id=intervention.directive_id,
                        plan_revision_id=plan_revision_id,
                        book_id=revision.book_id,
                        branch_id=revision.branch_id,
                        logical_id=logical_id,
                        revision_id=outcome.revision.revision_id,
                        content_hash=content_hash(result.text),
                        recorded_at=_timestamp(now),
                    )
                )
            realizations = tuple(realized)
        # **The one text nothing kept** (§187; recommendation 2 of the attribution report).
        # `plan/agent-impact/reviser-impact.md` §1 established by three reads of the code that
        # no draft/revision pair exists anywhere and none can be built later — the reviser's
        # decision row carries cost and a containment verdict and no text, the acceptance event
        # carries `chars` and `revised_by` and no text, and `--no-session-persistence` leaves
        # no transcript. So the stage that now writes every sentence the book ships was the one
        # stage whose input was not recorded. It is recorded here, in the transaction that
        # keeps the prose that replaced it, and only when a revision was actually adopted: when
        # containment refused, the draft *is* the accepted prose and a second copy of it would
        # be a row saying nothing.
        #
        # **Nothing about this row compares the two texts.** It says what the stage was handed.
        # The comparison is a reader's, later, outside the loop — `litharness why --json` is
        # where it surfaces, on the operator's side of §97.1.
        kept: tuple[PreRevisionDraft, ...] = ()
        if superseded is not None and revised_by is not None:
            content, draft_marks = superseded
            kept = (
                PreRevisionDraft(
                    draft_id=pre_revision_draft_id(
                        outcome.revision.revision_id, logical_id, content
                    ),
                    book_id=revision.book_id,
                    branch_id=revision.branch_id,
                    logical_id=logical_id,
                    revision_id=outcome.revision.revision_id,
                    job_id=job.job_id,
                    attempt=job.attempts,
                    # The writer's model, not the reviser's: `result` was rebound on `text`
                    # alone, so its provenance is still the drafting call's.
                    drafted_by=result.model or "(unnamed)",
                    revised_by=revised_by,
                    content=content,
                    em_dashes_removed=draft_marks,
                    recorded_at=_timestamp(now),
                ),
            )
        store.commit_revision(
            outcome.revision,
            created_at=_timestamp(now),
            events=commit_events,
            state_records=extracted,
            jobs=follow_up_jobs,
            intervention_realizations=realizations,
            pre_revision_drafts=kept,
            decision=decision,
        )

        # `acceptance` is deliberately **not** returned: `commit_revision` already persisted it
        # in the same transaction as the revision, and returning it as well would ask the
        # Conductor to append it a second time — harmless, because idempotency keys are
        # content-derived and collapse on insert, but it would misreport the tick's event
        # count. The decision event retains the established Conductor-owned write path and
        # is returned here; only the decision record itself must share the revision commit.
        return [*revision_events, decision_event]

    return handle


__all__ = ["SCENE_DRAFT", "HandlerInputError", "make_scene_draft_handler"]
