"""Historical scene records retain their identity without reconstructing missing evidence."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path
from typing import Any

import litharness_contracts as lc
import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import exemplars
from litharness.application.handlers import SCENE_DRAFT
from litharness.application.policy_events import policy_decision_event
from litharness.application.reviser import REVISION_PROFILE
from litharness.application.scene_trace import build_scene_trace
from litharness.domain.events import Event, EventType
from litharness.domain.jobs import Job, JobStatus, input_digest_for
from litharness.domain.policy import GateKind, GateOutcome, Outcome, PolicyDecision
from litharness.domain.reviser import PreRevisionDraft, pre_revision_draft_id
from litharness.domain.revision import Revision, new_book

BOOK = "trace-book"
BRANCH = "main"
SCENE = "scene-1"
STAMP = "2026-09-07T00:00:00Z"
RAW = "Cafe\u0301—**raw-only-marker**.\r\nSecond line.\r\n"
ACCEPTED = "Café: accepted-only-marker.\nSecond line.\n"
FROZEN_SYSTEM = "Frozen system at enqueue.\r\nKeep its line endings."
FROZEN_PROMPT = "Frozen prompt at enqueue.\r\nWrite the recorded scene."


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SqliteStore]:
    with SqliteStore.open(tmp_path / "scene-trace.db") as opened:
        yield opened


@dataclass(frozen=True)
class History:
    base: Revision
    job: Job
    accepted: Revision
    decision: PolicyDecision
    event: Event


def _seed(
    store: SqliteStore,
    *,
    payload_extra: dict[str, Any] | None = None,
    base_text: str | None = None,
) -> tuple[Revision, Job]:
    base = new_book(BOOK, BRANCH, title="Trace fixture", scenes=2)
    if base_text is not None:
        base = replace(
            base,
            revision_id="",
            nodes=tuple(
                n.with_content(base_text) if n.logical_id == SCENE else n for n in base.nodes
            ),
        )
    store.commit_revision(base, created_at=STAMP)
    payload = {
        "revision_id": base.revision_id,
        "book_id": BOOK,
        "branch_id": BRANCH,
        "logical_id": SCENE,
        "system": FROZEN_SYSTEM,
        "prompt": FROZEN_PROMPT,
        "context": {"frozen_section": "enqueue-context-marker"},
        **(payload_extra or {}),
    }
    job = Job(
        job_id="trace-draft",
        job_kind=SCENE_DRAFT,
        payload=payload,
        input_digest=input_digest_for(payload),
    )
    store.enqueue(job)
    return base, job


def _output_event(
    base: Revision,
    job: Job,
    decision: PolicyDecision,
    *,
    raw: str | None,
    raw_hash: str | None = None,
) -> Event:
    accepted = decision.resulting_revision_id is not None
    payload: dict[str, Any] = {
        "decision_id": decision.decision_id,
        "job_id": job.job_id,
        "logical_id": SCENE,
        "accepted": accepted,
    }
    if raw is not None:
        payload["raw_draft"] = {
            "text": raw,
            "sha256": raw_hash or sha256(raw.encode("utf-8")).hexdigest(),
            "provider": "fixture-provider",
            "model": "fixture-writer",
        }
    return Event(
        event_type=(
            EventType.MANUSCRIPT_REVISION_ACCEPTED
            if accepted
            else EventType.MANUSCRIPT_CANDIDATE_CREATED
        ),
        project_id="trace-project",
        created_at=STAMP,
        book_id=BOOK,
        branch_id=BRANCH,
        revision_id=decision.resulting_revision_id or base.revision_id,
        payload=payload,
    )


def _policy_event(decision: PolicyDecision, **details: Any) -> Event:
    return policy_decision_event(
        decision,
        project_id="trace-project",
        created_at=STAMP,
        book_id=BOOK,
        branch_id=BRANCH,
        revision_id=decision.resulting_revision_id or decision.base_revision_id,
        details=details,
    )


def _accept(
    store: SqliteStore,
    base: Revision,
    job: Job,
    *,
    raw: str | None = RAW,
    raw_hash: str | None = None,
    text: str = ACCEPTED,
    attempt: int = 2,
    kept_text: str | None = None,
) -> History:
    accepted = replace(
        base,
        revision_id="",
        parent_revision_id=base.revision_id,
        nodes=tuple(n.with_content(text) if n.logical_id == SCENE else n for n in base.nodes),
    )
    decision = PolicyDecision(
        decision_id="trace-accepted",
        outcome=Outcome.ACCEPT,
        job_id=job.job_id,
        logical_id=SCENE,
        base_revision_id=base.revision_id,
        resulting_revision_id=accepted.revision_id,
        attempt=attempt,
        provider="fixture-provider",
        model="fixture-writer",
        invocations=1,
    )
    event = _output_event(base, job, decision, raw=raw, raw_hash=raw_hash)
    kept = (
        ()
        if kept_text is None
        else (
            PreRevisionDraft(
                draft_id=pre_revision_draft_id(accepted.revision_id, SCENE, kept_text),
                book_id=BOOK,
                branch_id=BRANCH,
                logical_id=SCENE,
                revision_id=accepted.revision_id,
                job_id=job.job_id,
                attempt=attempt,
                drafted_by="fixture-writer",
                revised_by="fixture-reviser",
                content=kept_text,
                em_dashes_removed=1,
                recorded_at=STAMP,
            ),
        )
    )
    store.commit_revision(
        accepted,
        created_at=STAMP,
        events=(event, _policy_event(decision)),
        decision=decision,
        pre_revision_drafts=kept,
    )
    store.save_job(replace(job, status=JobStatus.SUCCEEDED, attempts=attempt))
    return History(base, job, accepted, decision, event)


def _refuse(
    store: SqliteStore,
    base: Revision,
    job: Job,
    *,
    attempt: int = 1,
    raw: str | None = "Refused raw-only-marker.",
) -> PolicyDecision:
    decision = PolicyDecision(
        decision_id="trace-refused",
        outcome=Outcome.RETRY,
        job_id=job.job_id,
        logical_id=SCENE,
        base_revision_id=base.revision_id,
        attempt=attempt,
        invocations=1,
    )
    store.record_decision(decision, decided_at=STAMP)
    store.append_events((_output_event(base, job, decision, raw=raw), _policy_event(decision)))
    return decision


def _trace(store: SqliteStore, **options: Any) -> dict[str, Any]:
    head = store.head(BOOK, BRANCH)
    assert head is not None
    return build_scene_trace(store, BOOK, BRANCH, head.node(SCENE), head, **options)


@pytest.mark.parametrize(
    ("selected", "status", "key"),
    [
        ({"story_order_key": "s17"}, "recorded", "s17"),
        ({"story_order_key": None}, "unpositioned", None),
        ({}, "not_recorded", None),
        (None, "not_recorded", None),
        ({"story_order_key": 17}, "invalid_recorded_value", None),
    ],
)
def test_story_cutoff_comes_from_the_frozen_job_not_reading_order(
    store: SqliteStore, selected: Any, status: str, key: str | None
) -> None:
    base, job = _seed(store, payload_extra={"selected_by": selected})
    _accept(store, base, job)
    assert base.node(SCENE).position_key != "s17"
    assert _trace(store)["request"]["story_order"] == {
        "source": "job_payload.selected_by.story_order_key",
        "status": status,
        "key": key,
    }


def test_frozen_input_does_not_become_the_current_plan(store: SqliteStore) -> None:
    base, job = _seed(store)
    _accept(store, base, job)
    store.record_plan_items(
        BOOK,
        BRANCH,
        [
            lc.PlanItem(
                logical_id="new-live-plan",
                kind=lc.PlanKind.PREMISE,
                text="Live-plan-only-marker added after generation.",
                authority=lc.PlanAuthority.INTENDED,
            )
        ],
        created_at="2026-09-07T01:00:00Z",
    )
    for stage, expected in (("system", FROZEN_SYSTEM), ("prompt", FROZEN_PROMPT)):
        result = _trace(store, stage=stage)
        assert result["excerpt"]["text"] == expected
        assert result["stages"][stage]["original_sha256"] == sha256(expected.encode()).hexdigest()
        assert result["request"]["source"] == "job_payload"
        assert result["request"]["provider_transport_captured"] is False
        assert "Live-plan-only-marker" not in json.dumps(result)


def test_raw_output_pages_reconstruct_its_exact_noncanonical_text(store: SqliteStore) -> None:
    base, job = _seed(store)
    history = _accept(store, base, job)
    summary = _trace(store)
    assert summary["excerpt"] is None
    assert "raw-only-marker" not in json.dumps(summary)
    assert "accepted-only-marker" not in json.dumps(summary)
    assert summary["decision"]["decision_id"] == history.decision.decision_id
    raw = summary["stages"]["raw_draft"]
    assert raw["original_chars"] == len(RAW)
    assert raw["original_sha256"] == sha256(RAW.encode()).hexdigest()
    assert raw["recorded_hash_matches"] is True
    offset, parts = 0, []
    while True:
        page = _trace(store, stage="raw_draft", offset=offset, max_chars=7)["excerpt"]
        assert page["offset"] == offset and page["total_chars"] == len(RAW)
        assert page["text"] == RAW[offset : offset + 7]
        assert len(page["text"]) <= 7
        parts.append(page["text"])
        if page["next_offset"] is None:
            assert page["truncated"] is False
            break
        assert page["truncated"] is True and page["next_offset"] > offset
        offset = page["next_offset"]
    assert "".join(parts) == RAW
    assert _trace(store, stage="accepted")["excerpt"]["text"] == ACCEPTED
    assert _trace(store, stage="raw_draft", offset=len(RAW) + 10)["excerpt"]["text"] == ""


def test_legacy_generation_does_not_invent_a_raw_output(store: SqliteStore) -> None:
    base, job = _seed(store)
    _accept(store, base, job, raw=None)
    result = _trace(store, stage="raw_draft")
    assert result["stages"]["raw_draft"]["available"] is False
    assert result["stages"]["raw_draft"]["absent_reason"] == "raw_draft_not_recorded"
    assert result["excerpt"]["text"] is None
    assert _trace(store, stage="accepted")["excerpt"]["text"] == ACCEPTED


def test_missing_frozen_prompt_is_not_rebuilt_from_other_stored_material(
    store: SqliteStore,
) -> None:
    base, job = _seed(store, payload_extra={"prompt": None})
    _accept(store, base, job)
    result = _trace(store, stage="prompt")
    assert result["request"]["available"] is False
    assert result["stages"]["prompt"]["absent_reason"] == "prompt_not_recorded"
    assert result["excerpt"]["text"] is None
    assert "enqueue-context-marker" not in json.dumps(result)


def test_refused_output_is_not_paired_with_base_or_later_accepted_prose(store: SqliteStore) -> None:
    base, job = _seed(store, base_text="Base-prose-only-marker.")
    refused = _refuse(store, base, job)
    _accept(store, base, job)
    raw = _trace(store, decision_id=refused.decision_id, stage="raw_draft")
    assert raw["excerpt"]["text"] == "Refused raw-only-marker."
    accepted = _trace(store, decision_id=refused.decision_id, stage="accepted")
    assert accepted["stages"]["accepted"]["available"] is False
    assert accepted["stages"]["accepted"]["absent_reason"] == "no_resulting_revision"
    assert accepted["excerpt"]["text"] is None
    assert "Base-prose-only-marker" not in json.dumps(accepted)
    assert "accepted-only-marker" not in json.dumps(accepted)


def test_unrelated_later_scene_does_not_replace_the_attributed_revision(store: SqliteStore) -> None:
    base, job = _seed(store)
    history = _accept(store, base, job)
    later = replace(
        history.accepted,
        revision_id="",
        parent_revision_id=history.accepted.revision_id,
        nodes=tuple(
            n.with_content("Other-scene-only-marker.") if n.logical_id == "scene-2" else n
            for n in history.accepted.nodes
        ),
    )
    store.commit_revision(later, created_at="2026-09-07T01:00:00Z")
    result = _trace(store, stage="accepted")
    assert result["head_revision_id"] == later.revision_id
    assert result["decision"]["resulting_revision_id"] == history.accepted.revision_id
    assert result["excerpt"]["text"] == ACCEPTED


@pytest.mark.parametrize(
    "wrong_field",
    ["book_id", "branch_id", "logical_id", "job_id", "decision_id", "event_type", "revision_id"],
)
@pytest.mark.parametrize("accepted", [True, False])
def test_raw_event_join_rejects_each_foreign_identity(
    store: SqliteStore,
    wrong_field: str,
    accepted: bool,
) -> None:
    base, job = _seed(store)
    refused = None if accepted else _refuse(store, base, job, raw=RAW)
    history = _accept(store, base, job)
    selected = history.decision if refused is None else refused
    event = history.event if refused is None else _output_event(base, job, refused, raw=RAW)
    payload = {
        **event.payload,
        "raw_draft": {
            "text": "Wrong-event-only-marker.",
            "sha256": sha256(b"Wrong-event-only-marker.").hexdigest(),
        },
    }
    foreign = replace(event, payload=payload)
    if wrong_field in {"logical_id", "job_id", "decision_id"}:
        foreign = replace(foreign, payload={**payload, wrong_field: "other-identity"})
    elif wrong_field == "event_type":
        foreign = replace(
            foreign,
            event_type=(
                EventType.MANUSCRIPT_CANDIDATE_CREATED
                if accepted
                else EventType.MANUSCRIPT_REVISION_ACCEPTED
            ),
        )
    else:
        foreign = replace(foreign, **{wrong_field: "other-identity"})
    store.append_events((foreign,))
    result = _trace(store, decision_id=selected.decision_id, stage="raw_draft")
    assert result["excerpt"]["text"] == RAW
    assert "Wrong-event-only-marker" not in json.dumps(result)


def test_two_matching_events_are_ambiguous_instead_of_first_or_last_wins(
    store: SqliteStore,
) -> None:
    base, job = _seed(store)
    history = _accept(store, base, job)
    store.append_events(
        (
            replace(
                history.event,
                payload={**history.event.payload, "extra_record": True},
            ),
        )
    )
    result = _trace(store, stage="raw_draft")
    assert result["stages"]["raw_draft"]["available"] is False
    assert result["stages"]["raw_draft"]["absent_reason"] == "ambiguous_event"
    assert result["excerpt"]["text"] is None


def test_a_mismatched_raw_hash_withholds_the_conflicting_text(store: SqliteStore) -> None:
    base, job = _seed(store)
    _accept(store, base, job, raw_hash="0" * 64)
    result = _trace(store, stage="raw_draft")
    raw = result["stages"]["raw_draft"]
    assert raw["available"] is True and raw["withheld"] is True
    assert raw["recorded_hash_matches"] is False
    assert raw["recorded_sha256"] == "0" * 64
    assert raw["original_sha256"] == sha256(RAW.encode()).hexdigest()
    assert raw["withholding_reason"] == "recorded_hash_mismatch"
    assert result["excerpt"]["text"] is None


def test_pre_revision_is_the_kept_stage_and_not_the_raw_writer_answer(store: SqliteStore) -> None:
    base, job = _seed(store)
    kept = "Canonical pre-revision-only-marker."
    _accept(store, base, job, kept_text=kept)
    assert _trace(store, stage="pre_revision_draft")["excerpt"]["text"] == kept
    assert _trace(store, stage="raw_draft")["excerpt"]["text"] == RAW
    assert _trace(store, stage="accepted")["excerpt"]["text"] == ACCEPTED


@pytest.mark.parametrize("stage", ["raw_draft", "pre_revision_draft"])
def test_shelf_provenance_withholds_output_even_without_a_shelf_heading(
    store: SqliteStore,
    stage: str,
) -> None:
    marker = "Synthetic shelf marker repeated without any heading."
    base, job = _seed(store, payload_extra={"exemplars": {"count": 1, "sha256": "fixture"}})
    _accept(store, base, job, raw=marker, kept_text=marker)
    result = _trace(store, stage=stage, offset=10, max_chars=5)
    descriptor = result["stages"][stage]
    assert descriptor["available"] is True and descriptor["withheld"] is True
    assert descriptor["withholding_reason"] == "exemplar_shelf_exposure"
    assert descriptor["original_chars"] == len(marker)
    assert descriptor["original_sha256"] == sha256(marker.encode()).hexdigest()
    assert result["excerpt"]["text"] is None
    assert marker not in json.dumps(result)


@pytest.mark.parametrize("misleading_packet_opener", [False, True])
def test_a_shelf_prompt_is_withheld_before_paging_but_keeps_original_identity(
    store: SqliteStore,
    misleading_packet_opener: bool,
) -> None:
    marker = "Synthetic source text must not leave the diagnostic tool."
    remaining_marker = "Synthetic shelf remainder after a misleading packet opener."
    shelf_body = marker
    if misleading_packet_opener:
        shelf_body += f"\n\nPremise: this paragraph is still shelf text.\n\n{remaining_marker}"
    prompt = f"{exemplars.OPENINGS_HEADING}\n\n{shelf_body}\n\nPremise: own context."
    base, job = _seed(store, payload_extra={"prompt": prompt})
    _accept(store, base, job)
    result = _trace(store, stage="prompt")
    assert marker not in json.dumps(result)
    assert remaining_marker not in json.dumps(result)
    assert result["excerpt"]["text"] is None
    assert result["excerpt"]["withheld"] is True
    descriptor = result["stages"]["prompt"]
    assert descriptor["redacted"] is True
    assert descriptor["withheld"] is True
    assert descriptor["original_chars"] == len(prompt)
    assert descriptor["original_sha256"] == sha256(prompt.encode()).hexdigest()
    assert descriptor["delivered_sha256"] is None


def test_revision_decision_does_not_borrow_writer_input_or_accepted_text(
    store: SqliteStore,
) -> None:
    base, job = _seed(store)
    revision_decision = PolicyDecision(
        decision_id="trace-reviser",
        outcome=Outcome.ACCEPT,
        job_id=job.job_id,
        logical_id=SCENE,
        base_revision_id=base.revision_id,
        attempt=2,
        profile="revision",
        model="fixture-reviser",
        invocations=1,
    )
    store.record_decision(revision_decision, decided_at=STAMP)
    store.append_events((_policy_event(revision_decision, stage="revision", adopted=True),))
    _accept(store, base, job, attempt=2)
    for stage, reason in (
        ("system", "revision_request_not_recorded"),
        ("prompt", "revision_request_not_recorded"),
        ("raw_draft", "revision_output_not_recorded"),
        ("accepted", "no_resulting_revision"),
    ):
        result = _trace(store, decision_id=revision_decision.decision_id, stage=stage)
        assert result["decision"]["stage"] == "revision"
        assert result["stages"][stage]["absent_reason"] == reason
        assert result["excerpt"]["text"] is None
    assert len(_trace(store)["attempts"]) == 2


def test_revision_budget_refusal_without_an_event_does_not_borrow_the_writer_request(
    store: SqliteStore,
) -> None:
    base, job = _seed(store)
    revision_decision = PolicyDecision(
        decision_id="trace-reviser-budget",
        outcome=Outcome.ACCEPT,
        job_id=job.job_id,
        logical_id=SCENE,
        base_revision_id=base.revision_id,
        attempt=2,
        profile=REVISION_PROFILE,
        gates=(GateOutcome(gate=GateKind.BUDGET, rule_or_critic_id="budget.v0", passed=False),),
        invocations=0,
    )
    store.record_decision(revision_decision, decided_at=STAMP)
    _accept(store, base, job, attempt=2)
    assert not any(
        item.event.payload.get("decision_id") == revision_decision.decision_id
        for item in store.read_job_log(BOOK, BRANCH, job.job_id)
    )
    for stage in ("system", "prompt"):
        result = _trace(store, decision_id=revision_decision.decision_id, stage=stage)
        assert result["decision"]["stage"] == "revision"
        assert result["decision"]["invocations"] == 0
        assert result["stages"][stage]["absent_reason"] == "revision_request_not_recorded"
        assert result["excerpt"]["text"] is None
        assert result["request"]["available"] is False
        assert result["request"]["story_order"]["status"] == "unavailable"


def test_later_acceptance_at_a_lower_attempt_remains_the_default(store: SqliteStore) -> None:
    base, job = _seed(store)
    refused = _refuse(store, base, job, attempt=3)
    history = _accept(store, base, job, attempt=1)
    assert store.decisions_for_job(job.job_id)[-1].decision_id == refused.decision_id
    result = _trace(store)
    assert result["decision"]["decision_id"] == history.decision.decision_id
    assert result["decision"]["attempt"] == 1
    assert [item["decision_id"] for item in result["attempts"]] == [
        refused.decision_id,
        history.decision.decision_id,
    ]
    assert _trace(store, decision_id=refused.decision_id)["decision"]["attempt"] == 3


def test_unfinished_revived_job_defaults_to_the_newest_recorded_refusal(
    store: SqliteStore,
) -> None:
    base, job = _seed(store)
    earlier = _refuse(store, base, job, attempt=3, raw="Earlier refusal-only-marker.")
    store.save_job(replace(job, status=JobStatus.PARKED, attempts=3))
    revived = store.revive(job.job_id)
    assert revived.attempts == 0
    latest = replace(earlier, decision_id="trace-refused-after-revival", attempt=1)
    store.record_decision(latest, decided_at="2026-09-07T01:00:00Z")
    store.append_events(
        (
            _output_event(base, job, latest, raw="Latest refusal-only-marker."),
            _policy_event(latest),
        )
    )
    store.save_job(replace(revived, status=JobStatus.PARKED, attempts=1))
    stale = store.latest_decision_for(job.job_id)
    assert stale is not None and stale.decision_id == earlier.decision_id
    result = _trace(store, stage="raw_draft")
    assert result["decision"]["decision_id"] == latest.decision_id
    assert result["decision"]["attempt"] == 1
    assert result["excerpt"]["text"] == "Latest refusal-only-marker."
    assert result["stages"]["accepted"]["available"] is False
    assert [item["decision_id"] for item in result["attempts"]] == [
        earlier.decision_id,
        latest.decision_id,
    ]
    explicit = _trace(store, decision_id=earlier.decision_id, stage="raw_draft")
    assert explicit["excerpt"]["text"] == "Earlier refusal-only-marker."


def test_an_unfinished_scene_exposes_its_frozen_input_and_recorded_refusal(
    store: SqliteStore,
) -> None:
    base, job = _seed(store)
    refused = _refuse(store, base, job)
    store.save_job(replace(job, status=JobStatus.PARKED, attempts=1))
    result = _trace(store, stage="prompt")
    assert result["job_id"] == job.job_id
    assert result["decision"]["decision_id"] == refused.decision_id
    assert result["excerpt"]["text"] == FROZEN_PROMPT
    assert result["stages"]["accepted"]["available"] is False


def test_a_decision_from_another_job_cannot_be_selected(store: SqliteStore) -> None:
    base, job = _seed(store)
    _accept(store, base, job)
    other = PolicyDecision(decision_id="other-decision", outcome=Outcome.ACCEPT, job_id="other-job")
    store.record_decision(other, decided_at=STAMP)
    with pytest.raises(ValueError):
        _trace(store, decision_id=other.decision_id)


def test_scoped_store_events_exclude_interleaved_other_books_branches_and_jobs(
    store: SqliteStore,
) -> None:
    base, job = _seed(store)
    history = _accept(store, base, job)
    original = store.read_job_log(BOOK, BRANCH, job.job_id)
    assert len(original) == 2
    foreign_scopes = (
        ("other-book", BRANCH, job.job_id),
        (BOOK, "other-branch", job.job_id),
        (BOOK, BRANCH, "other-job"),
        (BOOK, BRANCH, None),
    )
    for index, (book, branch, job_id) in enumerate(foreign_scopes):
        store.append_events(
            (
                replace(
                    history.event,
                    book_id=book,
                    branch_id=branch,
                    payload={**history.event.payload, "job_id": job_id, "scope_probe": index},
                ),
            )
        )
        store.append_events(
            (
                replace(
                    history.event,
                    payload={**history.event.payload, "own_probe": index},
                ),
            )
        )
    matched = store.read_job_log(BOOK, BRANCH, job.job_id)
    assert len(matched) == 2 + len(foreign_scopes)
    assert matched[:2] == original
    assert [item.sequence for item in matched] == sorted(item.sequence for item in matched)
    assert all("scope_probe" not in item.event.payload for item in matched)
    assert [item.event.payload["own_probe"] for item in matched[2:]] == [0, 1, 2, 3]
    assert store.read_job_log(BOOK, BRANCH, "missing-job") == []


@pytest.mark.parametrize(
    "options",
    [
        {"stage": "current_plan"},
        {"offset": -1},
        {"offset": True},
        {"offset": 1.5},
        {"max_chars": 0},
        {"max_chars": -1},
        {"max_chars": True},
        {"max_chars": 20001},
        {"max_chars": 1.5},
    ],
)
def test_invalid_excerpt_boundaries_do_not_trigger_an_unbounded_read(
    store: SqliteStore,
    options: dict[str, Any],
) -> None:
    base, job = _seed(store)
    _accept(store, base, job)
    with pytest.raises(ValueError):
        _trace(store, **options)
