"""The optional rewrite receives the same author locks as the frozen drafting job."""

from __future__ import annotations

import copy
from hashlib import sha256

import litharness_contracts as lc
import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.handlers import make_scene_draft_handler
from litharness.application.planner import make_plan_selector
from litharness.application.reviser import (
    render_revision_request,
    revision_author_locks,
    revision_system,
)
from litharness.domain import worlds
from litharness.domain.draft import DraftPolicy
from litharness.domain.jobs import input_digest_for
from litharness.providers.fake import FakeProvider
from litharness.providers.registry import ProviderRegistry
from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID
from tests.helpers import accepted
from tests.test_outline import START, a_book
from tests.test_reviser import DRAFT, REVISION


@pytest.fixture
def queued(tmp_path):
    repeated = "Keep the lantern intact.\nIts répaired handle remains attached."
    global_lock = lc.PlanItem(
        logical_id="global-lock",
        kind=lc.PlanKind.CONSTRAINT,
        text=repeated,
        authority=lc.PlanAuthority.INTENDED,
        locked=True,
    )
    promise = lc.PlanItem(
        logical_id="author-promise",
        kind=lc.PlanKind.PROMISE,
        text=repeated,
        authority=lc.PlanAuthority.INTENDED,
        locked=True,
    )
    local = lc.PlanItem(
        logical_id="local-lock",
        kind=lc.PlanKind.CONSTRAINT,
        text="The gatekeeper remains silent in this scene.",
        authority=lc.PlanAuthority.INTENDED,
        locked=True,
        scope=lc.ResourceRef(
            project_id=PROJECT_ID,
            book_id=BOOK_ID,
            branch_id=BRANCH_ID,
            logical_id="scene-1",
            kind=lc.ResourceKind.MANUSCRIPT_SCENE,
        ),
    )
    later = lc.PlanItem(
        logical_id="later-lock",
        kind=lc.PlanKind.CONSTRAINT,
        text="The gatekeeper speaks in the later scene.",
        authority=lc.PlanAuthority.INTENDED,
        locked=True,
        scope=lc.ResourceRef(
            project_id=PROJECT_ID,
            book_id=BOOK_ID,
            branch_id=BRANCH_ID,
            logical_id="scene-2",
            kind=lc.ResourceKind.MANUSCRIPT_SCENE,
        ),
    )
    rule = accepted(
        worlds.world_record(
            "lantern", worlds.WORLD_RULE_PREDICATE, value="The lantern's flame consumes oil."
        )
    )
    policy = DraftPolicy(require_starting_sheet=False)
    with SqliteStore.open(tmp_path / "locks.db") as store:
        a_book(store, scenes=6, sheet=False, extra_plan_items=(global_lock, promise, local, later))
        store.record_state_records(BOOK_ID, BRANCH_ID, [rule], created_at="2026-09-09T00:00:00Z")
        job = make_plan_selector(project_id=PROJECT_ID, outline=False, policy=policy)(
            store, "worker", START, 300
        )
        assert job is not None
        yield store, job, (global_lock, promise, local), later, rule, policy


def test_selected_author_locks_reach_the_actual_revision_system(queued):
    store, job, locks, later, rule, policy = queued
    before_plan = store.plan_revision(BOOK_ID, BRANCH_ID)
    before_payload = copy.deepcopy(job.payload)
    block, reason = revision_author_locks(job.payload, recorded_input_digest=job.input_digest)
    assert block and reason is None
    assert block.count(locks[0].text) == 2  # Distinct locks with equal bodies are not deduplicated.
    for lock in locks:
        assert lock.text in block and lock.text not in job.payload["packet"]
    assert later.text not in block and later.text not in job.payload["packet"]
    assert rule.value in job.payload["packet"] and rule.value not in block

    requests = []

    class RecordingProvider(FakeProvider):
        def complete(self, request):
            requests.append(request)
            return super().complete(request)

    provider = RecordingProvider(responses=[DRAFT, REVISION])
    registry = ProviderRegistry(provider)
    handler = make_scene_draft_handler(registry, store, PROJECT_ID, policy=policy, revise=True)
    handler(job, START)
    assert provider.calls == 2
    writer, rewrite = requests
    assert writer.system == job.payload["system"]
    assert rewrite.system == revision_system() + block
    expected = render_revision_request(DRAFT, material=job.payload["packet"])
    assert rewrite.prompt == expected.prompt
    assert rewrite.input_chars == len(rewrite.prompt) + len(rewrite.system)
    head = store.head(BOOK_ID, BRANCH_ID)
    assert head is not None and head.node("scene-1").content == REVISION
    assert store.plan_revision(BOOK_ID, BRANCH_ID) == before_plan
    assert store.load_job(job.job_id).payload == before_payload
    handler(job, START + 1)  # Accepted replay neither revises nor revisits today's plan.
    assert provider.calls == 2


@pytest.mark.parametrize(
    "change",
    [
        "unknown_composition",
        "missing_scope",
        "nested_plan",
        "wrong_authority",
        "wrong_kind",
        "duplicate_renderer",
        "outside_renderer",
        "overlapping_items",
        "missing_renderer",
        "wrong_renderer",
    ],
)
def test_unresolvable_frozen_authority_is_not_interpreted_as_no_locks(queued, change):
    _, job, *_ = queued
    payload = copy.deepcopy(job.payload)
    sources = payload["prompt_sources"]
    block = next(entry for entry in sources["entries"] if entry["section"] == "locks")
    item = next(entry for entry in sources["entries"] if entry["section"] == "constraints")
    if change == "unknown_composition":
        sources["context"]["source"] = "unknown"
    elif change == "missing_scope":
        del sources["context"]["plan_revision_id"]
    elif change == "nested_plan":
        item["source"]["plan_revision_id"] = "different-plan"
    elif change == "wrong_authority":
        item["source"]["authority"] = "derived"
    elif change == "wrong_kind":
        item["source"]["source_kind"] = "unknown"
    elif change == "duplicate_renderer":
        sources["entries"].append(copy.deepcopy(block))
    elif change == "outside_renderer":
        block.update(
            start=item["end"],
            sha256=sha256(payload["system"][item["end"] : block["end"]].encode()).hexdigest(),
        )
    elif change == "overlapping_items":
        sources["entries"].append(copy.deepcopy(item))
    elif change == "missing_renderer":
        sources["entries"].remove(block)
    else:
        block["source"]["producer"] = "another-renderer"
    result, reason = revision_author_locks(payload, recorded_input_digest=input_digest_for(payload))
    assert result is None and reason


def test_equal_lower_authority_text_is_not_a_lock_locator(queued):
    _, job, *_ = queued
    payload = copy.deepcopy(job.payload)
    # The packet can contain an additional matching copy. The exact SYSTEM insertion wins.
    expected, _ = revision_author_locks(payload, recorded_input_digest=job.input_digest)
    payload["packet"] += expected
    assert revision_author_locks(payload, recorded_input_digest=input_digest_for(payload)) == (
        expected,
        None,
    )


def test_known_empty_composition_preserves_the_existing_request(tmp_path):
    with SqliteStore.open(tmp_path / "empty.db") as store:
        a_book(store, scenes=6, sheet=False)
        job = make_plan_selector(outline=False, policy=DraftPolicy(require_starting_sheet=False))(
            store, "worker", START, 300
        )
        assert job is not None
        assert revision_author_locks(job.payload, recorded_input_digest=job.input_digest) == (
            "",
            None,
        )
        # The author-locked premise belongs in material; it is not a relocated constraint.
        assert any(
            entry["source"].get("authority") == "author_locked"
            for entry in job.payload["prompt_sources"]["entries"]
        )
        request = render_revision_request(
            DRAFT, material=job.payload["packet"], author_lock_system=""
        )
        assert request == render_revision_request(DRAFT, material=job.payload["packet"])
