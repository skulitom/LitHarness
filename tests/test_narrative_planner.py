"""Bounded model-produced plan proposals for interpretive director notes."""

from __future__ import annotations

import json

import litharness_contracts as lc
import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.conductor import Conductor, TickOutcome
from litharness.application.model_context import current as current_state_view
from litharness.application.narrative_planner import (
    NARRATIVE_PLAN,
    NarrativePlanOutputError,
    make_narrative_plan_handler,
    proposal_from_model,
    render_request,
)
from litharness.application.planner import make_plan_selector
from litharness.domain.budget import BudgetPolicy
from litharness.domain.directives import Directive, DirectiveKind, DirectiveStatus
from litharness.domain.events import EventType
from litharness.domain.jobs import Job, JobStatus
from litharness.domain.plan_refinement import PlanProposalError
from litharness.domain.policy import Outcome
from litharness.providers.base import CompletionResult
from litharness.providers.fake import FakeProvider
from litharness.providers.registry import ProviderRegistry
from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID, make_revision

START = 1_760_000_000.0
STAMP = "2026-08-14T12:00:00Z"


@pytest.fixture
def store(tmp_path) -> SqliteStore:
    opened = SqliteStore.open(tmp_path / "narrative-planner.db")
    opened.commit_revision(make_revision(), created_at=STAMP)
    opened.record_plan_items(
        BOOK_ID,
        BRANCH_ID,
        [
            lc.PlanItem(
                logical_id="premise",
                kind=lc.PlanKind.PREMISE,
                text="A thief must repay an impossible debt.",
                authority=lc.PlanAuthority.INTENDED,
                locked=True,
            ),
            lc.PlanItem(
                logical_id="arc-middle",
                kind=lc.PlanKind.BOOK_PLAN,
                text="The midpoint is a physical confrontation.",
                authority=lc.PlanAuthority.POSSIBLE,
            ),
        ],
        created_at=STAMP,
    )
    return opened


def directive(store: SqliteStore, *, directive_id: str = "dir-tone") -> Directive:
    item = Directive(
        directive_id=directive_id,
        kind=DirectiveKind.TONE_NOTE,
        body="Make the midpoint tense without another fight.",
        book_id=BOOK_ID,
        branch_id=BRANCH_ID,
    )
    assert store.submit_directive(item, received_at=STAMP)
    store.mark_directive_ingested(item.directive_id, ingested_at=STAMP)
    return item


def response(*, text: str = "The midpoint turns on a tense negotiation.") -> str:
    return json.dumps(
        {
            "summary": "Replace physical escalation with negotiation",
            "rationale": "The director asked for tension without another fight.",
            "expected_outcome": "The midpoint stays tense through a social cost.",
            "interpretation": "Use negotiation, not combat, for midpoint tension.",
            "edits": [
                {
                    "action": "create",
                    "logical_id": "constraint-midpoint-negotiation",
                    "kind": "constraint",
                    "text": text,
                    "authority": "intended",
                    "locked": True,
                    "reason": "preserve the requested tone as a drafting constraint",
                }
            ],
        }
    )


def conductor(
    store: SqliteStore,
    provider: FakeProvider,
    *,
    budget: BudgetPolicy | None = None,
) -> Conductor:
    registry = ProviderRegistry(provider)
    return Conductor(
        store=store,
        holder="narrative-test",
        project_id=PROJECT_ID,
        registry=registry,
        select=make_plan_selector(),
        handlers={
            NARRATIVE_PLAN: make_narrative_plan_handler(
                registry,
                store,
                PROJECT_ID,
                budget=budget,
                actor="narrative-test",
            )
        },
    )


def test_interpretive_direction_becomes_an_audited_plan_revision_before_prose(
    store: SqliteStore,
) -> None:
    note = directive(store)
    provider = FakeProvider(responses=[response()])
    store.enqueue(
        Job(
            job_id="stale-scene-prompt",
            job_kind="scene_draft",
            payload={"book_id": BOOK_ID, "branch_id": BRANCH_ID},
        )
    )

    result = conductor(store, provider).tick(START)

    assert result.outcome is TickOutcome.RAN_JOB
    assert result.job_id is not None and result.job_id.startswith("narrative-")
    assert provider.calls == 1
    applied = store.load_directive(note.directive_id)
    assert applied.status is DirectiveStatus.APPLIED
    [constraint_id] = applied.produced_constraint_ids
    constraint = store.plan_revision(BOOK_ID, BRANCH_ID).item(constraint_id)  # type: ignore[union-attr]
    assert constraint.text == "The midpoint turns on a tense negotiation."
    assert constraint.locked
    decision = store.latest_decision_for(result.job_id)
    assert decision is not None and decision.outcome is Outcome.ACCEPT
    assert decision.provider == "fake" and decision.total_tokens > 0
    head = store.plan_revision(BOOK_ID, BRANCH_ID)
    assert head is not None
    assert decision.resulting_revision_id == head.plan_revision_id
    assert store.spend_on("2025-10-09").invocations == 1
    assert store.load_job("stale-scene-prompt").status is JobStatus.CANCELLED
    assert store.plan_epoch(BOOK_ID, BRANCH_ID) == 1
    event_types = [entry.event.event_type for entry in store.read_log()]
    assert EventType.PLAN_CHANGED in event_types
    assert EventType.POLICY_DECISION_RECORDED in event_types


def test_malformed_model_output_is_metered_and_bounded_as_a_candidate_failure(
    store: SqliteStore,
) -> None:
    note = directive(store, directive_id="dir-malformed")
    malformed = json.dumps(
        {
            "summary": "No edits",
            "rationale": "Bad output",
            "expected_outcome": "Nothing",
            "interpretation": "Unusable",
            "edits": [],
        }
    )
    provider = FakeProvider(responses=[malformed])

    result = conductor(store, provider).tick(START)

    assert result.outcome is TickOutcome.JOB_FAILED
    assert result.job_id is not None
    assert store.load_job(result.job_id).status is JobStatus.FAILED
    decision = store.latest_decision_for(result.job_id)
    assert decision is not None and decision.outcome is Outcome.RETRY
    assert decision.failed_vetoes
    assert decision.invocations == 1
    assert store.spend_on("2025-10-09").invocations == 1
    assert store.load_directive(note.directive_id).status is DirectiveStatus.RECEIVED
    assert len(store.plan_history(BOOK_ID, BRANCH_ID)) == 1


def test_budget_refusal_happens_before_the_planner_call_and_is_revivable(
    store: SqliteStore,
) -> None:
    note = directive(store, directive_id="dir-budget")
    provider = FakeProvider(responses=[response()])

    result = conductor(
        store,
        provider,
        budget=BudgetPolicy(max_invocations_per_day=0),
    ).tick(START)

    assert result.outcome is TickOutcome.JOB_PARKED
    assert result.job_id is not None
    parked = store.load_job(result.job_id)
    assert parked.status is JobStatus.PARKED and parked.attempts == 0
    assert provider.calls == 0
    assert store.load_directive(note.directive_id).status is DirectiveStatus.RECEIVED
    assert len(store.open_exceptions()) == 1


def test_parser_refuses_a_model_attempt_to_rewrite_a_locked_item(
    store: SqliteStore,
) -> None:
    note = directive(store, directive_id="dir-locked")
    base = store.plan_revision(BOOK_ID, BRANCH_ID)
    assert base is not None
    payload = json.loads(response())
    payload["edits"] = [
        {
            "action": "update",
            "logical_id": "premise",
            "kind": "premise",
            "text": "A completely different book.",
            "authority": "intended",
            "locked": True,
            "reason": "ignore the lock",
        }
    ]
    result = CompletionResult(text="", provider="fake", model="fake-v1")

    with pytest.raises((NarrativePlanOutputError, PlanProposalError), match="locked"):
        proposal_from_model(payload, base=base, directive=note, result=result)


def test_parser_enforces_explicit_directive_targets(store: SqliteStore) -> None:
    note = Directive(
        directive_id="dir-targeted",
        kind=DirectiveKind.ARC_NOTE,
        body="Make only the ending quieter.",
        book_id=BOOK_ID,
        branch_id=BRANCH_ID,
        target_logical_ids=("arc-ending",),
    )
    base = store.plan_revision(BOOK_ID, BRANCH_ID)
    assert base is not None
    payload = json.loads(response())
    payload["edits"] = [
        {
            "action": "delete",
            "logical_id": "arc-middle",
            "kind": "none",
            "text": "",
            "authority": "none",
            "locked": False,
            "reason": "change an unrelated beat",
        }
    ]
    result = CompletionResult(text="", provider="fake", model="fake-v1")

    with pytest.raises(NarrativePlanOutputError, match="outside the directive's targets"):
        proposal_from_model(payload, base=base, directive=note, result=result)


def _scene_plan_edit(scope: str) -> dict:
    return {
        "action": "create",
        "logical_id": "scene-plan-from-a-chapter-note",
        "kind": "scene_plan",
        "text": "Silas condemns the forgery; the Advent sirens end the scene.",
        "authority": "intended",
        "locked": False,
        "scope": scope,
        "reason": "the chapter note says what scene one is for",
    }


def test_a_directive_scene_plan_is_scoped_and_therefore_reaches_its_scene(
    store: SqliteStore,
) -> None:
    """The defect this closes had no symptom.

    `plans.scene_plan_for` matches on scope first and a derived id second, and a
    directive-minted item could satisfy neither — so a chapter note's scene plans sat in the
    plan, were reported by `litharness plans`, and reached no draft. Measured on Serial Pilot
    1: eight correct scene plans, none of them addressable, and the drafts silently used an
    outline written from the premise alone instead.
    """
    from litharness.domain.plans import scene_plan_for

    note = directive(store, directive_id="dir-scoped")
    base = store.plan_revision(BOOK_ID, BRANCH_ID)
    assert base is not None
    scenes = [
        node.logical_id for node in make_revision().in_reading_order() if node.kind.value == "scene"
    ]
    payload = json.loads(response())
    payload["edits"] = [_scene_plan_edit(scenes[0])]
    result = CompletionResult(text="", provider="fake", model="fake-v1")

    proposal = proposal_from_model(
        payload,
        base=base,
        directive=note,
        result=result,
        scene_ids=scenes,
        project_id=PROJECT_ID,
    )

    [edit] = [item for item in proposal.edits if item.item is not None]
    assert edit.item is not None and edit.item.scope is not None
    assert edit.item.scope.logical_id == scenes[0]
    assert scene_plan_for([edit.item], scenes[0]) is edit.item


def test_a_scope_naming_no_scene_of_this_book_is_refused(store: SqliteStore) -> None:
    """A plan item addressed to a node that does not exist fails the same silent way the
    missing scope did, so it is refused rather than coerced or dropped."""
    note = directive(store, directive_id="dir-bad-scope")
    base = store.plan_revision(BOOK_ID, BRANCH_ID)
    assert base is not None
    payload = json.loads(response())
    payload["edits"] = [_scene_plan_edit("scene-does-not-exist")]
    result = CompletionResult(text="", provider="fake", model="fake-v1")

    with pytest.raises(NarrativePlanOutputError, match="not a scene in this book"):
        proposal_from_model(
            payload,
            base=base,
            directive=note,
            result=result,
            scene_ids=["scene-1"],
            project_id=PROJECT_ID,
        )


def test_the_planner_sees_scene_statuses_summaries_and_current_state(
    store: SqliteStore,
) -> None:
    note = directive(store, directive_id="dir-context")
    base = store.plan_revision(BOOK_ID, BRANCH_ID)
    head = store.head(BOOK_ID, BRANCH_ID)
    assert base is not None and head is not None
    records = (
        lc.StateRecord(
            record_id="rook-wants",
            kind=lc.StateRecordKind.ASSERTION,
            subject="rook",
            predicate="wants",
            value="freedom",
            authority=lc.StateAuthority.ACCEPTED_CANON,
        ),
    )

    request = render_request(
        base,
        note,
        ("scene-1", "scene-2"),
        current_state=current_state_view(head, records),
        accepted_summaries=(("scene-1", "Rook counts the debt."),),
        accepted_scene_ids=("scene-1",),
    )
    manuscript = json.loads(request.prompt)["manuscript_context"]

    assert manuscript["scenes"] == [
        {
            "scene": "scene-1",
            "status": "accepted",
            "accepted_summary": "Rook counts the debt.",
        },
        {"scene": "scene-2", "status": "draftable"},
    ]
    assert manuscript["current_story_state"]["established_facts"] == ["rook wants freedom"]


def test_the_planning_lane_cannot_replan_an_accepted_scene(store: SqliteStore) -> None:
    note = directive(store, directive_id="dir-past")
    base = store.plan_revision(BOOK_ID, BRANCH_ID)
    assert base is not None
    payload = json.loads(response())
    payload["edits"] = [_scene_plan_edit("scene-1")]

    with pytest.raises(NarrativePlanOutputError, match="cannot revise accepted manuscript"):
        proposal_from_model(
            payload,
            base=base,
            directive=note,
            result=CompletionResult(text="", provider="fake", model="fake-v1"),
            scene_ids=("scene-1", "scene-2"),
            accepted_scene_ids=("scene-1",),
            project_id=PROJECT_ID,
        )

    payload = json.loads(response())
    derived = _scene_plan_edit("none")
    derived["logical_id"] = "scene-1-plan"
    payload["edits"] = [derived]
    with pytest.raises(NarrativePlanOutputError, match="cannot revise accepted manuscript"):
        proposal_from_model(
            payload,
            base=base,
            directive=note,
            result=CompletionResult(text="", provider="fake", model="fake-v1"),
            scene_ids=("scene-1", "scene-2"),
            accepted_scene_ids=("scene-1",),
            project_id=PROJECT_ID,
        )


def test_a_constraint_a_person_directed_is_locked_and_therefore_reaches_a_scene(
    store: SqliteStore,
) -> None:
    """`locked` is not a style preference: `plans.constraints_of` selects on it, so an unlocked
    constraint reaches no context packet at all.

    The model was never told that and duly returned `locked: false` for every constraint it
    minted from Serial Pilot 1's tone note. Measured on both runs, the drafting prompt carried
    only the verbatim-lane constraints — not one word of "close third person", "dry, exact",
    "dramatize rather than summarize" or "avoid rule-of-three flourishes" ever reached a scene.
    The plan showed them. `litharness plans` reported them. They shaped nothing.
    """
    from litharness.domain.plans import constraints_of

    note = directive(store, directive_id="dir-tone-lock")
    base = store.plan_revision(BOOK_ID, BRANCH_ID)
    assert base is not None
    payload = json.loads(response())
    payload["edits"] = [
        {
            "action": "create",
            "logical_id": "constraint-voice-dry-exact",
            "kind": "constraint",
            "text": "Voice: dry, exact, quietly funny. Avoid rule-of-three flourishes.",
            "authority": "intended",
            "locked": False,
            "scope": "none",
            "reason": "the tone note says so",
        }
    ]
    result = CompletionResult(text="", provider="fake", model="fake-v1")

    proposal = proposal_from_model(payload, base=base, directive=note, result=result)

    [edit] = [item for item in proposal.edits if item.item is not None]
    assert edit.item is not None and edit.item.locked, "a person's constraint carries authority"
    assert constraints_of([edit.item]), "and is therefore visible to context assembly"
