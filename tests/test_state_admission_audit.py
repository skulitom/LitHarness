"""Counterexamples to treating ecological construction as semantic admission."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from litharness.domain.salience import ecological_manifest, public_battery

_PATH = (Path(__file__).resolve().parents[1] / "research/quality-measurement"
         / "state-admission-audit-20260927/audit.py")
_SPEC = importlib.util.spec_from_file_location("state_admission_audit", _PATH)
assert _SPEC and _SPEC.loader
audit = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = audit
_SPEC.loader.exec_module(audit)


def test_two_equal_state_records_do_not_imply_persistence() -> None:
    assert audit.state_paths(changed_target=False, require_persistence=False)
    assert audit.state_paths(changed_target=True, require_persistence=False)
    assert audit.state_paths(changed_target=False, require_persistence=True) == ((0, 0, 0),)
    assert not audit.state_paths(changed_target=True, require_persistence=True)


def test_cross_scene_packets_omit_the_keyed_anchor_and_interval() -> None:
    source = audit.fixture()
    packets = public_battery((source.item,))["items"][0]["variants"]
    assert all(source.anchor not in packet["text"] for packet in packets)
    assert all(source.bridge not in packet["text"] for packet in packets)
    # Positive control: searching for these strings succeeds when their context is present.
    local = audit.fixture(same_scene=True)
    local_packets = public_battery((local.item,))["items"][0]["variants"]
    assert all(local.anchor in packet["text"] for packet in local_packets)
    assert all(local.bridge in packet["text"] for packet in local_packets)


@pytest.mark.parametrize("value", sorted(audit.OPPOSITES))
@pytest.mark.parametrize("renderer", (0, 1))
def test_equal_existing_fingerprints_leave_a_case_and_length_shortcut(value, renderer) -> None:
    item = audit.fixture(value, renderer=renderer).item
    assert item.damage_fingerprint == item.sham_fingerprint
    assert len(item.damaged_text) != len(item.sham_text)
    assert audit.case_only_prediction(item.damaged_text) == "damaged"
    assert audit.case_only_prediction(item.sham_text) == "sham"


def test_shortcut_is_a_construction_counterexample_not_a_general_reader() -> None:
    item = audit.fixture(uppercase=True).item
    # Swapcase makes an uppercase-source sham lowercase: the rule then mislabels it.
    assert audit.case_only_prediction(item.sham_text) != "sham"


@pytest.mark.parametrize("same_scene", (False, True))
def test_constructed_packets_are_not_admitted_even_with_anchor_context(same_scene) -> None:
    source = audit.fixture(same_scene=same_scene)
    manifest = ecological_manifest(source.census, (source.item,))
    assert manifest["eligible_for_model_run"] is False
    assert manifest["construction_ready"] is True
    assert manifest["admission_status"] == "construction_only_semantic_admission_required"
    assert manifest["admission_gaps"]


def test_empty_construction_also_reports_no_admission() -> None:
    source = audit.fixture()
    manifest = ecological_manifest(source.census, ())
    assert manifest["construction_ready"] is False
    assert manifest["eligible_for_model_run"] is False
    assert manifest["admission_status"] == "no_constructed_items"


def test_report_contains_no_fixture_prose_and_carries_the_destructive_controls() -> None:
    import json

    result = audit.report()
    encoded = json.dumps(result)
    source = audit.fixture()
    assert source.anchor not in encoded and source.bridge not in encoded
    assert result["model_calls"] == result["database_reads"] == 0
    assert result["same_scene_context_positive_control"]["packets_with_anchor"] == 3
    assert result["uppercase_source_shortcut_destructive_control"]["case_shortcut_correct"] == 1
