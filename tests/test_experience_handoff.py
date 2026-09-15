"""Shared-parent research cannot leak its specification or silently substitute drafts."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from litharness.application.outline import CONCEPT_OUTLINE_SCHEMA
from litharness.domain.invention import make_seed
from litharness.providers.codex_schema import prepare_codex_schema

RUNNER = (Path(__file__).resolve().parents[1]
          / "research/quality-measurement/experience-handoff-20260915/run.py")


@pytest.fixture
def pilot(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("experience_handoff_test", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "LOCAL", tmp_path)
    for index in module.BRIEFS:
        module.write(tmp_path / f"seeds/{index}.json", make_seed(index).to_jsonable())
    return module


def receipt(pilot, name, payload):
    path = pilot.LOCAL / f"calls/{name}.json"
    pilot.write(path, {"name": name, "status": "completed", "result": {"parsed": payload}})
    return path


def parents(pilot, index="1"):
    receipt(pilot, f"discovery-S-{index}", {
        "world": "COMMON-WORLD", "opening": "OMITTED-OPENING", "growth": "COMMON-GROWTH"})
    receipt(pilot, f"concept-S-{index}", {
        "person_before": "A learner.", "exception": "An affinity.", "first_use": "OMITTED-USE",
        "want": "COMMON-WANT", "system": {"name": "Affinity", "manner": "Silent",
        "look": "Light", "steps": 12, "strongest_known": "A master.", "pays": "Control."},
        "threat": {"what": "Uncertainty.", "first_reach": "OMITTED-REACH"},
        "turn": {"event": "An opportunity.", "when": "before chapter one"},
        "second_system": None,
        "first_arc": {"opens": "REPLACED-OPENING", "middle": "An attempt.", "closes": "A use."},
        "debts": [{"subject": "One", "owed": "A result.", "due_scene": 1},
                  {"subject": "Two", "owed": "Another use.", "due_scene": 2}],
    })


def outline():
    return {
        "summary": "An episode.", "rationale": "Connected events.", "expected_outcome": "A use.",
        "scenes": [{"ordinal": i, "brief": {"situation": f"Situation {i}",
                   "pursuit": f"Pursuit {i}", "changes": [f"CHAPTER-{i}-ONLY"],
                   "future_dependencies": ["PROPOSED-FUTURE"]}} for i in (1, 2)],
        "milestones": [], "payoff_windows": [],
    }


def test_outline_pair_has_same_parents_and_exactly_one_added_input_field(pilot):
    parents(pilot)
    a, la = pilot.slot_request("outline-A-1")
    b, lb = pilot.slot_request("outline-B-1")
    assert la == lb
    assert [p["slot"] for p in la] == ["discovery-S-1", "concept-S-1"]
    ra, rb = pilot.serial(a), pilot.serial(b)
    pa, pb = json.loads(ra.pop("prompt")), json.loads(rb.pop("prompt"))
    assert ra == rb
    assert pb.pop("original_episode_specification") == pilot.specification("1")
    assert pa == pb
    assert "COMMON-WORLD" in a.prompt and "COMMON-WANT" in a.prompt
    for marker in ("OMITTED-OPENING", "OMITTED-USE", "OMITTED-REACH", "REPLACED-OPENING"):
        assert marker not in a.prompt and marker not in b.prompt
    assert len(pa["scenes"]) == 2


def test_writers_only_receive_current_scene_and_exact_own_previous_chapter(pilot):
    receipt(pilot, "outline-B-2", outline())
    receipt(pilot, "chapter1-A-2", {"story": "WRONG-ARM-STORY"})
    first, first_lineage = pilot.slot_request("chapter1-B-2")
    assert [p["slot"] for p in first_lineage] == ["outline-B-2"]
    fp = json.loads(first.prompt)
    assert fp["prior_narrative"] is None
    assert "CHAPTER-1-ONLY" in first.prompt and "CHAPTER-2-ONLY" not in first.prompt
    own = "Prior narrative with quotation marks: \"mine\".\n\nAnd a second paragraph."
    path = receipt(pilot, "chapter1-B-2", {"story": own})
    second, lineage = pilot.slot_request("chapter2-B-2")
    assert lineage[-1] == {"slot": "chapter1-B-2", "receipt_sha256": pilot.sha(path)}
    sp = json.loads(second.prompt)
    assert sp["prior_narrative"] == own
    assert "CHAPTER-2-ONLY" in second.prompt and "CHAPTER-1-ONLY" not in second.prompt
    for request in (first, second):
        assert set(json.loads(request.prompt)) == {
            "original_premise", "chapter", "current_scene", "prior_narrative"}
        assert "WRONG-ARM-STORY" not in request.prompt
        assert "original_episode_specification" not in request.prompt
        assert pilot.INPUTS["2"]["experience"]["concrete_use"] not in request.prompt


def test_invalid_shared_parent_skips_both_arms_without_substitution(pilot):
    parents(pilot)
    receipt(pilot, "concept-S-1", {})
    for arm in "AB":
        assert pilot.slot_request(f"outline-{arm}-1")[0] is None
        pilot.write(pilot.LOCAL / f"calls/outline-{arm}-1.json", {"status": "skipped"})
        assert pilot.slot_request(f"chapter1-{arm}-1")[0] is None


def test_invalid_first_chapter_or_outline_cannot_advance(pilot):
    payload = outline()
    payload["scenes"][1]["ordinal"] = 1
    receipt(pilot, "outline-A-3", payload)
    assert pilot.slot_request("chapter1-A-3")[0] is None
    receipt(pilot, "outline-A-3", outline())
    receipt(pilot, "chapter1-A-3", {"story": ""})
    assert pilot.slot_request("chapter2-A-3")[0] is None


def test_native_schema_fallback_is_checked_instead_of_assumed(pilot):
    with pytest.raises(ValueError) as failure:
        prepare_codex_schema(CONCEPT_OUTLINE_SCHEMA)
    raw = {"schema": CONCEPT_OUTLINE_SCHEMA, "native_schema": None,
           "native_schema_omission_reason": str(failure.value),
           "schema_variant": "prompt-only-original.v1", "argv": []}
    assert all(pilot.schema_controls(raw, CONCEPT_OUTLINE_SCHEMA).values())
    raw["argv"] = ["--output-schema", "unexpected.json"]
    assert not pilot.schema_controls(raw, CONCEPT_OUTLINE_SCHEMA)["native_schema_argument"]


def test_all_dependencies_precede_children_and_arm_order_reverses(pilot):
    assert len(pilot.ORDER) == len(set(pilot.ORDER)) == 32
    positions = {name: i for i, name in enumerate(pilot.ORDER)}
    for name in pilot.ORDER:
        assert all(positions[p] < positions[name] for p in pilot.parent_slots(name))
    for stage in ("outline", "chapter1", "chapter2"):
        orders = [positions[f"{stage}-A-{i}"] < positions[f"{stage}-B-{i}"]
                  for i in pilot.BRIEFS]
        assert sum(orders) == 2
    for i in pilot.BRIEFS:
        assert (positions[f"outline-A-{i}"] < positions[f"outline-B-{i}"]) != (
            positions[f"chapter1-A-{i}"] < positions[f"chapter1-B-{i}"])


def test_existing_dispatch_and_test_environment_refuse_provider_construction(pilot, monkeypatch):
    monkeypatch.setattr(pilot, "lock", lambda: None)
    with pytest.raises(RuntimeError, match="disabled in tests"):
        pilot.run()
    pilot.write(pilot.LOCAL / "progress.json", {"status": "stopped"})
    with pytest.raises(RuntimeError, match="no implicit resume"):
        pilot.run()


def test_original_specification_only_enters_shared_discovery_before_the_concept(pilot):
    request, lineage = pilot.slot_request("discovery-S-4")
    assert not lineage
    assert pilot.INPUTS["4"]["experience"]["concrete_use"] in request.prompt
    assert "not accepted past events" in request.prompt
    parents(pilot, "4")
    request, lineage = pilot.slot_request("concept-S-4")
    assert [p["slot"] for p in lineage] == ["discovery-S-4"]
    assert "COMMON-WORLD" in request.prompt
    assert pilot.INPUTS["4"]["experience"]["concrete_use"] not in request.prompt


def test_audit_counts_all_usage_and_detects_captured_prompt_corruption(pilot, monkeypatch):
    monkeypatch.setattr(pilot, "HERE", pilot.LOCAL / "tracked")
    monkeypatch.setattr(pilot, "verify_frozen", lambda: None)
    monkeypatch.setattr(pilot, "use_source", lambda: None)
    pilot.write(pilot.HERE / "registration.json", {"test": True})
    for i in pilot.BRIEFS:
        parents(pilot, i)
        for arm in "AB":
            receipt(pilot, f"outline-{arm}-{i}", outline())
            for chapter in ("chapter1", "chapter2"):
                receipt(pilot, f"{chapter}-{arm}-{i}", {"story": "Some research fixture prose."})
    for name in pilot.ORDER:
        request, lineage = pilot.slot_request(name)
        prepared = pilot.serial(request)
        path = pilot.LOCAL / f"calls/{name}.json"
        row = pilot.read(path)
        request_path = pilot.LOCAL / f"requests/{name}.json"
        pilot.write(request_path, prepared)
        try:
            native, reason = prepare_codex_schema(request.schema), None
        except ValueError as error:
            native, reason = None, str(error)
        raw = {
            "prompt": request.prompt, "system": request.effective_system,
            "returncode": 0, "requested_model": "gpt-6-astra", "mode": "completion",
            "settings": {"model_reasoning_effort": "medium"},
            "argv": ["--ephemeral", "--ignore-user-config", "--ignore-rules",
                     "project_doc_max_bytes=0", "features.memories=false"] + (
                         ["--output-schema", "test.json"] if native is not None else []),
            "schema": request.schema, "native_schema": native,
            "native_schema_omission_reason": reason,
            "schema_variant": ("strict-nullable-optionals.v1" if native is not None
                               else "prompt-only-original.v1"),
            "events": [{"type": "thread.started", "thread_id": name}],
        }
        row.update(lineage=lineage, request=prepared, request_sha256=pilot.sha(request_path),
                   started_at="fixture", finished_at="fixture")
        row["result"].update(raw=raw, usage={"input_tokens": 1, "output_tokens": 2,
            "cache_read_tokens": 3, "cache_write_tokens": 4, "reasoning_tokens": 5})
        pilot.write(path, row)
    pilot.write(pilot.LOCAL / "progress.json", {"status": "complete", "attempts": 32,
                                               "tokens": 32 * 15})
    pilot.audit()
    assert pilot.read(pilot.HERE / "evidence.json")["all_controls_pass"]
    path = pilot.LOCAL / "calls/chapter2-A-4.json"
    row = pilot.read(path)
    row["result"]["raw"]["prompt"] += "CORRUPTION"
    pilot.write(path, row)
    with pytest.raises(RuntimeError, match="Audit failed"):
        pilot.audit()
