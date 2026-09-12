"""The blank-brief comparison removes one sentence and preserves the real seed."""

from __future__ import annotations

import dataclasses
import importlib.util
from pathlib import Path

from litharness.domain.invention import make_seed


def test_empty_brief_ablation_preserves_seed_and_every_other_request_field():
    path = Path(__file__).resolve().parents[1] / (
        "research/quality-measurement/empty-brief-life-20260912/run.py"
    )
    spec = importlib.util.spec_from_file_location("empty_brief_experiment", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    seed = make_seed("314159265358979323846")
    full = module.request_for(seed, "control")
    omit = module.request_for(seed, "omit")
    assert dataclasses.replace(full, system=full.system.replace(module.SENTENCE, "", 1)) == omit
    assert full.system.startswith(seed.brief + "\n\n")
    assert omit.system.startswith(seed.brief + "\n\n")
    assert full.prompt == (
        "Author's brief:\nInvent a new story within the intended experience.\n"
        "Narrative person: third."
    )
    assert set(module.ORDER) == {f"{arm}-{i}" for arm in ("control", "omit") for i in (1, 2, 3)}
