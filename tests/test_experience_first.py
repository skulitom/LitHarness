"""The isolated pilot cannot reroute descendants or bypass its planning handoff."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from litharness.application import discovery
from litharness.domain.invention import make_seed

RUNNER = (Path(__file__).resolve().parents[1]
          / "research/quality-measurement/experience-first-20260914/run.py")


@pytest.fixture
def pilot(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("experience_first_test", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "LOCAL", tmp_path)
    for index in module.BRIEFS:
        module.write(tmp_path / f"seeds/{index}.json", make_seed(index).to_jsonable())
    return module


def receipt(pilot, slot, payload):
    path = pilot.LOCAL / f"calls/{slot}.json"
    pilot.write(path, {"name": slot, "status": "completed", "result": {"parsed": payload}})
    return path


def outline_payload():
    return {
        "summary": "A proposed arc.", "rationale": "Connected events.",
        "expected_outcome": "An opening for later action.",
        "scenes": [{"ordinal": i, "brief": {
            "situation": f"Situation {i}", "pursuit": f"Pursuit {i}",
            "changes": [f"Change {i}"], "future_dependencies": ["UNREALIZED-FUTURE"],
        }} for i in range(1, 7)], "milestones": [], "payoff_windows": [],
    }


def test_control_is_unchanged_and_extra_steps_differ_only_in_representation(pilot):
    brief, seed = pilot.inputs("1")
    control, lineage = pilot.slot_request("discovery-A-1")
    assert not lineage
    assert control == discovery.render_request(brief, person="third", seed=seed)
    planning = pilot.serial(pilot.pre_request("1", "B"))
    scene = pilot.serial(pilot.pre_request("1", "C"))
    assert planning.pop("system").endswith(pilot.COMMON + pilot.REPRESENTATION["B"])
    assert scene.pop("system").endswith(pilot.COMMON + pilot.REPRESENTATION["C"])
    assert planning == scene


def test_discovery_reads_only_its_designated_first_proposal_as_future_material(pilot):
    path = receipt(pilot, "pre-C-1", {"artifact": "DESIGNATED-PROSPECTIVE-SCENE"})
    receipt(pilot, "pre-B-1", {"artifact": "UNRELATED-PLANNING-PROPOSAL"})
    request, lineage = pilot.slot_request("discovery-C-1")
    assert lineage == [{"slot": path.stem, "receipt_sha256": pilot.sha(path)}]
    assert request.prompt.count("DESIGNATED-PROSPECTIVE-SCENE") == 1
    assert "UNRELATED-PLANNING-PROPOSAL" not in request.prompt
    assert "events have not happened" in request.prompt
    assert "creates no author locks" in request.prompt
    assert request.schema == discovery.SCHEMA


def test_malformed_parent_skips_descendants_without_substituting_other_arm(pilot):
    receipt(pilot, "pre-C-1", {"artifact": ""})
    receipt(pilot, "pre-B-1", {"artifact": "AVAILABLE-ALTERNATIVE"})
    request, lineage = pilot.slot_request("discovery-C-1")
    assert request is None
    assert lineage[0]["slot"] == "pre-C-1"
    pilot.write(pilot.LOCAL / "calls/discovery-C-1.json", {"status": "skipped"})
    assert pilot.slot_request("concept-C-1")[0] is None


def test_draft_cannot_receive_prototype_or_later_scene_as_a_second_channel(pilot):
    receipt(pilot, "pre-C-1", {"artifact": "PROTOTYPE-MUST-NOT-REACH-DRAFT"})
    payload = outline_payload()
    payload["scenes"][1]["brief"]["changes"] = ["LATER-SCENE-MUST-NOT-REACH-DRAFT"]
    receipt(pilot, "outline-C-1", payload)
    request, lineage = pilot.slot_request("draft-C-1")
    assert [x["slot"] for x in lineage] == ["outline-C-1"]
    assert "Change 1" in request.prompt
    assert "PROTOTYPE-MUST-NOT-REACH-DRAFT" not in request.prompt
    assert "LATER-SCENE-MUST-NOT-REACH-DRAFT" not in request.prompt
    assert "UNREALIZED-FUTURE" in request.prompt
    assert "not events or explanations to insert now" in request.prompt


def test_duplicate_or_missing_outline_scene_refuses_draft(pilot):
    payload = outline_payload()
    payload["scenes"][5]["ordinal"] = 1
    assert not pilot.conforms("outline", payload)
    receipt(pilot, "outline-B-2", payload)
    assert pilot.slot_request("draft-B-2")[0] is None


def test_concept_and_outline_keep_the_discovery_lineage_without_reopening_prototype(pilot):
    treatment = {"world": "WORLD-MARKER", "opening": "FUTURE-OPENING-MARKER",
                 "growth": "LATER-GROWTH-MARKER"}
    receipt(pilot, "discovery-C-1", treatment)
    receipt(pilot, "pre-C-1", {"artifact": "UNHANDED-PROTOTYPE-MARKER"})
    concept_request, _ = pilot.slot_request("concept-C-1")
    assert "FUTURE-OPENING-MARKER" in concept_request.prompt
    assert "UNHANDED-PROTOTYPE-MARKER" not in concept_request.prompt
    concept = {
        "person_before": "A learner.", "exception": "A magical affinity.",
        "first_use": "A proposed attempt.", "want": "To learn.",
        "system": {"name": "Affinity", "manner": "Silent", "look": "Light", "steps": 12,
                   "strongest_known": "A practiced master.", "pays": "Greater control."},
        "threat": {"what": "Uncertainty.", "first_reach": "An unfamiliar task."},
        "turn": {"event": "A further possibility.", "when": "before chapter one"},
        "second_system": None,
        "first_arc": {"opens": "MECHANICAL-REPLACEMENT", "middle": "Practice.",
                      "closes": "A usable result."},
        "debts": [{"subject": "One", "owed": "A result.", "due_scene": 3},
                  {"subject": "Two", "owed": "A direction.", "due_scene": 6}],
    }
    receipt(pilot, "concept-C-1", concept)
    request, lineage = pilot.slot_request("outline-C-1")
    assert request is not None
    assert [p["slot"] for p in lineage] == ["discovery-C-1", "concept-C-1"]
    assert "FUTURE-OPENING-MARKER" not in request.prompt
    assert "WORLD-MARKER" in request.prompt
    assert "LATER-GROWTH-MARKER" in request.prompt
    assert "MECHANICAL-REPLACEMENT" not in request.prompt
    assert "UNHANDED-PROTOTYPE-MARKER" not in request.prompt
    payload = json.loads(request.prompt)
    assert len(payload["scenes"]) == 6
    assert payload["starting_state"] is None


def test_registered_order_is_balanced_and_every_parent_precedes_child(pilot):
    assert len(pilot.ORDER) == len(set(pilot.ORDER)) == 84
    positions = {name: i for i, name in enumerate(pilot.ORDER)}
    for index in pilot.BRIEFS:
        for arm in "ABC":
            stages = ["discovery", "concept", "outline", "draft"]
            if arm != "A":
                stages.insert(0, "pre")
            order = [positions[f"{stage}-{arm}-{index}"] for stage in stages]
            assert order == sorted(order)
    assert len({tuple(arms) for _, arms in pilot.BLOCKS}) == 6


def test_runtime_refuses_existing_dispatch_before_constructing_provider(pilot, monkeypatch):
    monkeypatch.setattr(pilot, "lock", lambda: None)
    pilot.write(pilot.LOCAL / "progress.json", {"status": "stopped"})
    with pytest.raises(RuntimeError, match="no implicit resume"):
        pilot.run()


def test_serialized_request_round_trip_preserves_exact_prompt(pilot):
    request = pilot.pre_request("3", "C")
    pilot.write(pilot.LOCAL / "request.json", pilot.serial(request))
    assert json.loads((pilot.LOCAL / "request.json").read_text())["prompt"] == request.prompt
