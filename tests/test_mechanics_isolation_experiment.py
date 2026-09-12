"""Contain goal context and preserve first-parent identity across the experiment."""

from __future__ import annotations

import dataclasses
import importlib.util
import json
from pathlib import Path

from litharness.application import discovery
from litharness.domain.invention import make_seed
from litharness.providers.codex_cli import CodexCliProvider


def module():
    path = Path(__file__).resolve().parents[1] / (
        "research/quality-measurement/mechanics-isolation-20260912/run.py"
    )
    spec = importlib.util.spec_from_file_location("mechanics_experiment", path)
    assert spec is not None and spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def test_blind_magic_never_receives_goal_and_pairs_differ_only_in_user_message():
    experiment = module()
    seed = make_seed("8765432109876543210")
    linked = experiment.magic_request(seed, "PRIVATE-GOAL-MARKER", "linked")
    blind = experiment.magic_request(seed, "PRIVATE-GOAL-MARKER", "blind")
    assert "PRIVATE-GOAL-MARKER" not in blind.prompt + blind.effective_system
    assert linked.prompt == "Story pursuit:\nPRIVATE-GOAL-MARKER"
    assert dataclasses.replace(linked, prompt=blind.prompt) == blind
    assert blind.system.startswith(seed.brief + "\n\n")


def test_direct_is_production_renderer_and_mechanics_are_exact_structured_input():
    experiment = module()
    seed = make_seed("8765432109876543210")
    goal = "Keep this exact goal.\nAnd its disagreement."
    mechanics = {key: key + ' literal "quote"' for key in experiment.MAGIC_FIELDS}
    direct = experiment.plan_request(seed, goal)
    staged = experiment.plan_request(seed, goal, mechanics)
    assert direct == discovery.render_request(
        json.dumps({"pursuit": goal}), person="third", seed=seed,
    )
    assert staged == discovery.render_request(
        json.dumps({"pursuit": goal, "magic": mechanics}), person="third", seed=seed,
    )
    assert dataclasses.replace(direct, prompt=staged.prompt) == staged


def test_descendant_uses_only_designated_first_parent_and_skips_invalid_parent(tmp_path):
    experiment = module()
    experiment.LOCAL = tmp_path
    seed = make_seed("8765432109876543210")
    experiment.write(tmp_path / "seeds/1.json", seed.to_jsonable())
    experiment.write(tmp_path / "goals/1.json", {"pursuit": "Fixed pursuit"})
    mechanics = {key: "First-parent " + key for key in experiment.MAGIC_FIELDS}
    parent = tmp_path / "calls/magic-blind-1.json"
    experiment.write(parent, {"status": "completed", "result": {"parsed": mechanics}})
    experiment.write(tmp_path / "calls/magic-linked-1.json", {
        "status": "completed", "result": {"parsed": dict.fromkeys(mechanics, "WRONG")},
    })
    request, lineage = experiment.slot_request("plan-blind-1")
    assert request == experiment.plan_request(seed, "Fixed pursuit", mechanics)
    assert lineage == {"slot": "magic-blind-1", "receipt_sha256": experiment.sha(parent)}
    experiment.write(parent, {"status": "completed", "result": {"parsed": {}}})
    request, lineage = experiment.slot_request("plan-blind-1")
    assert request is None
    assert lineage["receipt_sha256"] == experiment.sha(parent)
    assert experiment.slot_request("plan-direct-1")[0] is not None


def test_registered_slots_are_unique_and_real_provider_constructs_without_dispatch(tmp_path):
    experiment = module()
    experiment.LOCAL = tmp_path
    assert len(experiment.ORDER) == len(set(experiment.ORDER)) == 15
    assert set(experiment.ORDER) == {
        f"{stage}-{arm}-{i}" for i in (1, 2, 3)
        for stage, arms in (("magic", ("linked", "blind")),
                            ("plan", ("direct", "linked", "blind"))) for arm in arms
    }
    provider = experiment.provider_for("uninvoked-binary")
    assert isinstance(provider, CodexCliProvider)
    assert provider.binary == "uninvoked-binary"
    assert provider.trace_directory == tmp_path / "transport"
