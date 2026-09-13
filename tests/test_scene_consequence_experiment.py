"""The trial keeps its own paths, bounds and explicit source overlay."""

import runpy
from pathlib import Path


def test_scene_consequence_trial_rebinds_helpers_without_widening_the_source_overlay():
    root = Path(__file__).resolve().parents[1]
    runner = runpy.run_path(
        str(root / "research/quality-measurement/scene-consequence-20260913/run.py")
    )
    base, driver = runner["BASE"], runner["DRIVER"]
    assert driver.RUN == base.RUN == root / "runs/scene-consequence-20260913"
    assert driver.BOOK == driver.RUN / "book"
    assert base.OWNER == "scene-consequence-20260913:"
    assert (driver.CHAPTERS, base.MAX_CALLS, base.MAX_TOKENS, base.MAX_SECONDS) == (
        6,
        32,
        2_200_000,
        5400,
    )
    assert runner["SOURCE_OVERRIDES"] == (
        "src/litharness/application/outline.py",
        "src/litharness/domain/house.py",
    )
    assert runner["PREVIOUS"].parent.name == "growth-continuation-20260913"
