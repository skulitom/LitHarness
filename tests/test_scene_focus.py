"""Scene treatment reaches drafting without changing stored events or other roles."""

import runpy
from pathlib import Path

import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.planner import packet_for, render_prompt
from litharness.domain import house
from litharness.domain.beats import beats_for
from litharness.domain.scene_brief import TREATMENT, SceneBrief, render_plan
from tests.test_planner import SIX_BEAT, _fixture


@pytest.fixture
def store(tmp_path):
    with SqliteStore.open(tmp_path / "scene-focus.db") as value:
        yield value


@pytest.mark.parametrize("has_prior_prose", [False, True])
def test_scene_opening_guidance_is_scoped_in_the_actual_writer_request(store, has_prior_prose):
    book, branch = _fixture(store, "mystery")
    head = store.head(book, branch)
    beat = beats_for(head, SIX_BEAT)[0]
    system, _ = render_prompt(
        beat, book_title=None, packet=packet_for(store, head, beat),
        point_of_view="silas", has_prior_prose=has_prior_prose,
    )
    assert (house.SCENE_MAGICAL_OFFER in system) is (not has_prior_prose)
    assert house._MAGICAL_OFFER not in system
    assert house.SCENE_CLARITY in system
    # Other house consumers and content-preserving revision keep their role contracts.
    assert house.READER in house.with_house_rules("Another role")
    assert house.SCENE_MAGICAL_OFFER not in house.with_house_rules("Another role")
    assert house.with_clarity_floor("Revise") == "Revise\n\n" + house.CLARITY


def test_treatment_is_rendering_guidance_and_does_not_rewrite_planned_events():
    brief = SceneBrief("The captain is waiting.", "Ask for help.",
                       ("She discloses the loss.", "The captain agrees to search."),
                       ("The missing person's whereabouts remain unknown.",))
    stored = brief.to_text()
    assert TREATMENT not in stored
    assert TREATMENT in render_plan(stored)
    assert SceneBrief.from_text(stored) == brief
    assert render_plan(stored).index(brief.changes[0]) < render_plan(stored).index(brief.changes[1])
    assert brief.future_dependencies[0] in render_plan(stored)
    assert render_plan("An unchanged author plan.") == "An unchanged author plan."


def test_scene_focus_trial_keeps_the_registered_bounds_and_source_scope():
    root = Path(__file__).resolve().parents[1]
    runner = runpy.run_path(str(root / "research/quality-measurement/scene-focus-20260913/run.py"))
    base, driver = runner["BASE"], runner["DRIVER"]
    assert driver.RUN == base.RUN == root / "runs/scene-focus-20260913"
    assert driver.BOOK == driver.RUN / "book"
    assert base.OWNER == "scene-focus-20260913:"
    assert (driver.CHAPTERS, base.MAX_CALLS, base.MAX_TOKENS, base.MAX_SECONDS) == (
        6, 32, 2_200_000, 5400,
    )
    assert set(runner["SOURCE_OVERRIDES"]) == {
        "src/litharness/application/outline.py", "src/litharness/application/planner.py",
        "src/litharness/domain/house.py", "src/litharness/domain/scene_brief.py",
    }
