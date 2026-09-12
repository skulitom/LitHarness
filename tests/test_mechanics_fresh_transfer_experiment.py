"""Check fresh inputs, first-parent containment and preassigned chapter lineage."""

from __future__ import annotations

import dataclasses
import importlib.util
import json
from pathlib import Path

import pytest

from litharness.application import discovery
from litharness.domain.invention import make_seed
from litharness.providers.codex_cli import CodexCliProvider


def module(name="mechanics-fresh-transfer-20260912"):
    path = Path(__file__).resolve().parents[1] / "research/quality-measurement" / name / "run.py"
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    assert spec is not None and spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def test_fresh_baseline_is_empty_production_brief_and_magic_prompt_is_unchanged():
    experiment = module()
    previous = module("mechanics-isolation-20260912")
    seed = make_seed("8765432109876543210")
    assert experiment.magic_request(seed) == previous.magic_request(seed, "", "blind")
    direct = experiment.plan_request(seed)
    assert direct == discovery.render_request("", person="third", seed=seed)
    mechanics = {key: key + ' literal "quote"\nline' for key in experiment.MAGIC_FIELDS}
    staged = experiment.plan_request(seed, mechanics)
    assert staged == discovery.render_request(
        json.dumps({"magic": mechanics}), person="third", seed=seed,
    )
    assert dataclasses.replace(direct, prompt=staged.prompt) == staged


def test_plan_uses_own_first_mechanics_and_invalid_parent_never_substitutes(tmp_path):
    experiment = module()
    experiment.LOCAL = tmp_path
    seed = make_seed("8765432109876543210")
    experiment.write(tmp_path / "seeds/1.json", seed.to_jsonable())
    mechanics = {key: "First " + key for key in experiment.MAGIC_FIELDS}
    parent = tmp_path / "calls/magic-staged-1.json"
    experiment.write(parent, {"status": "completed", "result": {"parsed": mechanics}})
    experiment.write(tmp_path / "calls/magic-staged-2.json", {
        "status": "completed", "result": {"parsed": dict.fromkeys(mechanics, "WRONG")},
    })
    request, lineage = experiment.slot_request("plan-staged-1")
    assert request == experiment.plan_request(seed, mechanics)
    assert lineage == {"slot": parent.stem, "receipt_sha256": experiment.sha(parent)}
    experiment.write(parent, {"status": "completed", "result": {"parsed": {}}})
    assert experiment.slot_request("plan-staged-1")[0] is None
    assert experiment.slot_request("plan-direct-1")[0] is not None


def test_chapter_receives_exact_designated_plan_without_extra_magic_or_other_arm(tmp_path):
    experiment = module()
    experiment.LOCAL = tmp_path
    seed = make_seed("8765432109876543210")
    experiment.write(tmp_path / "seeds/1.json", seed.to_jsonable())
    plan = {"world": "An unfamiliar plateau.", "opening": "A disputed departure.",
            "growth": "A chosen investigation."}
    parent = tmp_path / "calls/plan-staged-1.json"
    experiment.write(parent, {"status": "completed", "result": {"parsed": plan}})
    experiment.write(tmp_path / "calls/plan-direct-1.json", {
        "status": "completed", "result": {"parsed": dict.fromkeys(plan, "WRONG ARM")},
    })
    experiment.write(tmp_path / "calls/magic-staged-1.json", {
        "status": "completed", "result": {"parsed": {"extra": "NO EXTRA REMINDER"}},
    })
    request, lineage = experiment.slot_request("draft-staged-1")
    assert request.prompt == "Story proposal:\n" + json.dumps(plan, sort_keys=True)
    assert request.system == seed.brief + "\n\n" + experiment.DRAFT_TASK
    assert lineage == {"slot": parent.stem, "receipt_sha256": experiment.sha(parent)}
    experiment.write(parent, {"status": "skipped"})
    assert experiment.slot_request("draft-staged-1")[0] is None
    assert experiment.slot_request("draft-direct-1")[0] is not None
    with pytest.raises(ValueError):
        experiment.slot_request("draft-staged-2")


def test_invalid_discovery_skips_chapter_and_provider_constructs_without_dispatch(tmp_path):
    experiment = module()
    experiment.LOCAL = tmp_path
    experiment.write(tmp_path / "seeds/1.json", make_seed("876543210").to_jsonable())
    experiment.write(tmp_path / "calls/plan-staged-1.json", {
        "status": "completed", "result": {"parsed": {"world": "Only world"}},
    })
    assert experiment.slot_request("draft-staged-1")[0] is None
    assert len(experiment.ORDER) == len(set(experiment.ORDER)) == 11
    assert [n for n in experiment.ORDER if n.startswith("draft")] == [
        "draft-staged-1", "draft-direct-1",
    ]
    provider = experiment.provider_for("uninvoked-binary")
    assert isinstance(provider, CodexCliProvider)
    assert provider.trace_directory == tmp_path / "transport"
