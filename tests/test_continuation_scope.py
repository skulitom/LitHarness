"""Historical output requests remain intact without becoming the next scene's task."""

from __future__ import annotations

from dataclasses import replace

import litharness_contracts as lc
import pytest

from litharness import cli
from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import concept, planner
from litharness.application.conductor import Conductor, TickOutcome
from litharness.application.handlers import make_scene_draft_handler
from litharness.domain.revision import new_book
from litharness.providers.fake import FakeProvider
from litharness.providers.registry import ProviderRegistry
from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID
from tests.test_concept import _example
from tests.test_outline import START, a_book


@pytest.mark.parametrize("outlined", [False, True])
@pytest.mark.parametrize("brief_kind", ["none", "empty", "original", "locked"])
def test_continuation_scopes_original_request_and_preserves_author_decisions(
    tmp_path, monkeypatch, outlined, brief_kind,
):
    brief = ("Write Chapter 1 in third-person past tense, about 2,000 words. "
             "The protagonist is Mira. Keep her companion alive throughout the story.")
    drawn = concept.Concept.from_payload({
        **_example(), "author_brief": "" if brief_kind == "empty" else brief,
    })
    source = replace(drawn.plan_item(), locked=brief_kind == "locked")
    chapter_three = lc.PlanItem(
        logical_id="chapter-three-length", kind=lc.PlanKind.CONSTRAINT,
        text="For Chapter 3, write approximately 2,300 words and keep the companion alive.",
        authority=lc.PlanAuthority.INTENDED, locked=True,
        scope=lc.ResourceRef(
            project_id=PROJECT_ID, book_id=BOOK_ID, branch_id=BRANCH_ID,
            logical_id="scene-3", kind=lc.ResourceKind.MANUSCRIPT_SCENE,
        ),
    )
    plans = tuple(lc.PlanItem(
        logical_id=f"scene-{index}-plan", kind=lc.PlanKind.SCENE_PLAN,
        text="Follow the companion along the path.", authority=lc.PlanAuthority.INTENDED,
    ) for index in range(1, 7)) if outlined else ()
    texts = [
        "Mira found the path beneath the fallen branches and called for her companion. "
        "Nothing answered from the trees. She waited until the wind dropped, listening for "
        "a voice beneath the leaves, then pushed through the gap. The torn cloth she had "
        "noticed caught against her sleeve. She freed it carefully and carried it with her.",
        "The tower stood beyond the clearing, close enough for her to see the broken door. "
        "Her companion was sitting on its steps. Mira hurried across the grass and stopped "
        "when he held up his hand. A broken branch pinned his leg against the stone. She "
        "knelt beside him and found where she could take its weight without making it worse.",
    ]
    provider = FakeProvider(responses=list(texts))
    registry = ProviderRegistry(provider)
    monkeypatch.setattr(cli, "build_default_registry", lambda: registry)
    with SqliteStore.open(tmp_path / "scope.db") as store:
        a_book(store, scenes=6, extra_plan_items=(
            chapter_three, *plans, *((source,) if brief_kind != "none" else ()),
        ))
        original_plan = store.plan_revision(BOOK_ID, BRANCH_ID)
        args = cli.build_parser().parse_args([
            "--project", PROJECT_ID, "--target-words", "1800", "--chapter-scenes", "1",
            "--arc-chapters", "6", *([] if outlined else ["--no-outline"]), "tick",
        ])
        conductor = Conductor(
            store=store, holder="writer", project_id=PROJECT_ID, registry=registry,
            select=cli._conductor(store, args).select,
            handlers={planner.SCENE_DRAFT: make_scene_draft_handler(
                registry, store, PROJECT_ID, policy=cli._draft_policy(args),
            )},
        )
        for index in range(2):
            result = conductor.tick(START + index)
            assert result.outcome is TickOutcome.RAN_JOB and result.job_id is not None
            job = store.load_job(result.job_id)
            decision = store.latest_decision_for(job.job_id)
            assert decision is not None and decision.accepted
            assert job.payload["logical_id"] == f"scene-{index + 1}"
            system, prompt = job.payload["system"], job.payload["prompt"]
            scoped = index > 0 and brief_kind in {"original", "locked"}
            assert ("continuation of accepted prose" in system) is scoped
            assert "1800 words" in system
            assert f"chapter {index + 1} ({index + 1} of this arc); scene 1 of 1" in prompt
            assert chapter_three.text not in system
            if brief_kind in {"original", "locked"}:
                assert brief in prompt
            if index:
                assert texts[0] in prompt
            entries = job.payload["prompt_sources"]["entries"]
            assert any(entry.get("section") == "continuation_scope" for entry in entries) is scoped
        third = conductor.select(store, "next-writer", START + 2, 60)
        assert third is not None and third.job_kind == planner.SCENE_DRAFT
        assert "chapter 3 (3 of this arc); scene 1 of 1" in third.payload["prompt"]
        assert chapter_three.text in third.payload["system"]
        if brief_kind in {"original", "locked"}:
            assert "follow applicable author locks within their stated scope" in (
                third.payload["system"]
            )
            assert brief in third.payload["prompt"]
        assert store.plan_revision(BOOK_ID, BRANCH_ID) == original_plan
        assert provider.calls == 2


def test_continuation_depends_on_reading_order_not_scene_number_or_future_prose():
    revision = new_book(BOOK_ID, BRANCH_ID, title="Book", scenes=6)
    future = revision.replacing([revision.node("scene-6").with_content("Later accepted prose.")])
    assert not planner._has_prior_prose(future, "scene-2")
    assert not planner._has_prior_prose(future, "missing-scene")
    prior = revision.replacing([revision.node("scene-1").with_content("Earlier accepted prose.")])
    assert not planner._has_prior_prose(prior, "scene-1")
    assert planner._has_prior_prose(prior, "scene-6")
    assert not planner._has_prior_prose(
        revision.replacing([revision.node("scene-1").with_content("  ")]), "scene-2",
    )
