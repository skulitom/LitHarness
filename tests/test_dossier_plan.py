"""Historical plan inspection never substitutes the current plan for a job's snapshot."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from typing import Any

import litharness_contracts as lc
import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.dossier import _job_plan, render_dossier, scene_dossier
from litharness.application.handlers import SCENE_DRAFT
from litharness.application.plan_refinement import accept_plan_proposal
from litharness.domain.jobs import Job, input_digest_for
from litharness.domain.plan_refinement import PlanEdit, PlanEditAction, PlanProposal
from litharness.domain.revision import new_book

BOOK = "dossier-plan-book"
BRANCH = "main"
SCENE = "scene-1"
STAMP = "2026-09-07T00:00:00Z"
ORIGINAL = "The witness gives an account."
CURRENT = "The witness refuses to answer."
_DEFAULT_ID = object()


def _item(text: str, logical_id: str = "scene-1-plan") -> lc.PlanItem:
    return lc.PlanItem(
        logical_id=logical_id,
        kind=lc.PlanKind.SCENE_PLAN,
        text=text,
        authority=lc.PlanAuthority.INTENDED,
    )


def _premise() -> lc.PlanItem:
    return lc.PlanItem(
        logical_id="premise",
        kind=lc.PlanKind.PREMISE,
        text="An investigator questions a witness.",
        authority=lc.PlanAuthority.INTENDED,
        locked=True,
    )


def _seed(store: SqliteStore, *, recorded: bool = True, value: Any = _DEFAULT_ID) -> Job:
    head = new_book(BOOK, BRANCH, title="Plan provenance", scenes=1)
    store.commit_revision(head, created_at=STAMP)
    store.record_plan_items(BOOK, BRANCH, [_premise(), _item(ORIGINAL)], created_at=STAMP)
    plan = store.plan_revision(BOOK, BRANCH)
    assert plan is not None
    payload = {
        "book_id": BOOK,
        "branch_id": BRANCH,
        "logical_id": SCENE,
        "prompt": "Frozen rendering, which need not equal the stored scene statement.",
    }
    if recorded:
        payload["plan_revision_id"] = plan.plan_revision_id if value is _DEFAULT_ID else value
    job = Job(job_id="plan-bound-job", job_kind=SCENE_DRAFT, payload=payload)
    job = replace(job, input_digest=input_digest_for(payload))
    store.enqueue(job)
    return job


def _read(store: SqliteStore) -> dict[str, Any]:
    head = store.head(BOOK, BRANCH)
    assert head is not None
    return scene_dossier(store, BOOK, BRANCH, head.node(SCENE), head)


def test_dossier_keeps_the_job_plan_when_the_current_plan_changes_without_mutating(
    tmp_path: Path,
) -> None:
    path = tmp_path / "historical-plan.db"
    with SqliteStore.open(path) as store:
        job = _seed(store)
        original_id = job.payload["plan_revision_id"]
        accept_plan_proposal(
            store,
            PlanProposal(
                base_plan_revision_id=original_id,
                summary="Change the witness's action",
                rationale="An authorized fixture edit.",
                expected_outcome="A new current plan.",
                edits=(
                    PlanEdit(PlanEditAction.UPDATE, "scene-1-plan", _item(CURRENT), "Fixture"),
                ),
                provider="fixture",
                model="none",
                profile="fixture",
            ),
            project_id="fixture-project",
            created_at=STAMP,
            actor="fixture",
        )
        current = store.plan_revision(BOOK, BRANCH)
        assert current is not None and current.plan_revision_id != original_id
        job_before_read = store.load_job(job.job_id)
    before = sha256(path.read_bytes()).hexdigest()

    with SqliteStore.open_read_only(path) as store:
        dossier = _read(store)
        assert dossier["plan_item"]["text"] == CURRENT
        assert dossier["plan_item_scope"] == "current_plan"
        historical = dossier["job_plan"]
        assert historical == {
            "source": "job_payload.plan_revision_id",
            "scope": "job_bound_plan_revision",
            "job_id": job.job_id,
            "plan_revision_id": original_id,
            "status": "available",
            "reason": None,
            "plan_item": {
                "plan_item_id": "scene-1-plan",
                "text": ORIGINAL,
                "locked": False,
                "authority": "intended",
            },
            "prompt_equivalence_verified": False,
        }
        assert ORIGINAL not in job.payload["prompt"]
        rendered = render_dossier(dossier)
        assert "CURRENT plan:" in rendered and "job-bound snapshot" in rendered
        assert ORIGINAL in rendered and CURRENT in rendered
        assert "Exact rendering is not verified here" in rendered
        assert store.load_job(job.job_id) == job_before_read
        assert store.plan_revision(BOOK, BRANCH) == current
    assert sha256(path.read_bytes()).hexdigest() == before


def test_legacy_job_with_no_plan_id_reports_a_gap_despite_a_current_scene_plan(
    tmp_path: Path,
) -> None:
    with SqliteStore.open(tmp_path / "legacy.db") as store:
        _seed(store, recorded=False)
        dossier = _read(store)
    assert dossier["plan_item"]["text"] == ORIGINAL
    assert dossier["job_plan"]["status"] == "not_recorded"
    assert dossier["job_plan"]["plan_revision_id"] is None
    assert dossier["job_plan"]["plan_item"] is None
    assert dossier["job_plan"]["reason"] == "plan_revision_id_not_recorded"


@pytest.mark.parametrize("value", [None, 17, True, "", "  ", {"id": "untyped"}])
def test_invalid_recorded_plan_id_is_retained_without_lookup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: Any
) -> None:
    with SqliteStore.open(tmp_path / "invalid.db") as store:
        _seed(store, value=value)

        def no_lookup(_: str) -> None:
            pytest.fail("An invalid recorded id must not trigger a historical lookup")

        monkeypatch.setattr(store, "plan_revision_for_id", no_lookup)
        result = _read(store)["job_plan"]
    assert result["plan_revision_id"] == value
    assert result["status"] == "invalid_recorded_value"
    assert result["reason"] == "invalid_plan_revision_id"
    assert result["plan_item"] is None


def test_unavailable_recorded_revision_does_not_fall_back_to_current_plan(tmp_path: Path) -> None:
    with SqliteStore.open(tmp_path / "missing.db") as store:
        _seed(store, value="missing-recorded-revision")
        dossier = _read(store)
    assert dossier["plan_item"]["text"] == ORIGINAL
    assert dossier["job_plan"]["plan_revision_id"] == "missing-recorded-revision"
    assert dossier["job_plan"]["status"] == "unavailable"
    assert dossier["job_plan"]["reason"] == "plan_revision_not_recorded"
    assert dossier["job_plan"]["plan_item"] is None


@pytest.mark.parametrize(("book", "branch"), [("other-book", BRANCH), (BOOK, "other-branch")])
def test_a_recorded_plan_from_another_scope_never_supplies_scene_text(
    tmp_path: Path, book: str, branch: str
) -> None:
    with SqliteStore.open(tmp_path / "scope.db") as store:
        store.commit_revision(new_book(book, branch, title="Other", scenes=1), created_at=STAMP)
        store.record_plan_items(
            book, branch, [_premise(), _item("Foreign scene text.")], created_at=STAMP
        )
        foreign = store.plan_revision(book, branch)
        assert foreign is not None
        _seed(store, value=foreign.plan_revision_id)
        result = _read(store)["job_plan"]
    assert result["plan_revision_id"] == foreign.plan_revision_id
    assert result["reason"] == "plan_revision_scope_mismatch"
    assert result["plan_item"] is None


def test_a_snapshot_without_this_scene_item_stays_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with SqliteStore.open(tmp_path / "no-scene.db") as store:
        job = _seed(store)
        plan = store.plan_revision(BOOK, BRANCH)
        assert plan is not None
        no_scene = replace(
            plan,
            items=(_premise(), _item("Another scene.", "scene-2-plan")),
            plan_revision_id="",
        )
        # The stored current plan still has the target scene; the recorded lookup does not.
        monkeypatch.setattr(store, "plan_revision_for_id", lambda _: no_scene)
        bound = replace(job, payload={**job.payload, "plan_revision_id": no_scene.plan_revision_id})
        result = _job_plan(store, bound, BOOK, BRANCH, SCENE)
    assert result["reason"] == "scene_plan_not_recorded"
    assert result["plan_item"] is None


def test_an_incorrect_revision_lookup_identity_is_not_reported_as_the_recorded_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with SqliteStore.open(tmp_path / "identity.db") as store:
        job = _seed(store, value="wrong-lookup-id")
        current = store.plan_revision(BOOK, BRANCH)
        assert current is not None
        monkeypatch.setattr(store, "plan_revision_for_id", lambda _: current)
        result = _read(store)["job_plan"]
    assert result["plan_revision_id"] == job.payload["plan_revision_id"]
    assert result["reason"] == "plan_revision_identity_mismatch"
    assert result["plan_item"] is None


@pytest.mark.parametrize(
    "problem", ["job_absent", "job_kind", "book_id", "branch_id", "logical_id"]
)
def test_unattributable_job_never_exposes_historical_plan_text(
    tmp_path: Path, problem: str
) -> None:
    with SqliteStore.open(tmp_path / "job-scope.db") as store:
        job = _seed(store)
        if problem == "job_absent":
            bound = None
            reason = "job_not_recorded"
        elif problem == "job_kind":
            bound = replace(job, job_kind="unsupported")
            reason = "unsupported_job_kind"
        else:
            bound = replace(job, payload={**job.payload, problem: "other"})
            reason = "job_scope_mismatch"
        result = _job_plan(store, bound, BOOK, BRANCH, SCENE)
    assert result["status"] == "unavailable"
    assert result["reason"] == reason
    assert result["plan_item"] is None
