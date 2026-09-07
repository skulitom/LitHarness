"""Frozen source metadata is verified before paging and never reconstructed from state."""

from __future__ import annotations

import copy
import json
from hashlib import sha256
from typing import Any

import pytest

from litharness.application.prompt_source_view import SCHEMA, build_prompt_source_view
from litharness.domain.jobs import input_digest_for


def _view(payload: dict[str, Any], **options: Any) -> dict[str, Any]:
    """Bind a constructed fixture as enqueue would, unless a stale/missing digest is explicit."""
    options.setdefault("recorded_input_digest", input_digest_for(payload))
    return build_prompt_source_view(payload, **options)


def _hash(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


@pytest.fixture
def payload() -> dict[str, Any]:
    system = "A frozen system.\r\n"
    body = "αβ frozen packet text"
    prompt = f"Facts:\n{body}\n\nA separate scene requirement."
    start = prompt.index(body)
    return {
        "system": system,
        "prompt": prompt,
        "book_id": "book",
        "branch_id": "branch",
        "logical_id": "scene-1",
        "prompt_sources": {
            "schema": SCHEMA,
            "stages": {
                name: {"chars": len(text), "sha256": _hash(text)}
                for name, text in (("system", system), ("prompt", prompt))
            },
            "entries": [
                {
                    "stage": "prompt",
                    "start": 0,
                    "end": len(prompt),
                    "sha256": _hash(prompt),
                    "kind": "renderer",
                    "section": "packet",
                    "source": {"producer": "packet.render", "attribution": "renderer_fragment"},
                },
                {
                    "stage": "prompt",
                    "start": start,
                    "end": start + len(body),
                    "sha256": _hash(body),
                    "kind": "context_item",
                    "section": "facts",
                    "source": {
                        "item_id": "item-1",
                        "source_logical_id": "record-1",
                        "source_kind": "state_event",
                        "authority": "accepted_canon",
                        "pov_visibility": [],
                        "source_span": None,
                        "packed_text_sha256": _hash(body),
                    },
                },
                {
                    "stage": "system",
                    "start": 0,
                    "end": len(system),
                    "sha256": _hash(system),
                    "kind": "renderer",
                    "section": "writer",
                    "source": {
                        "producer": "writer.dossier",
                        "attribution": "renderer_fragment",
                        "writer_id": "writer-1",
                    },
                },
            ],
            "context": {
                "book_id": "book",
                "branch_id": "branch",
                "logical_id": "scene-1",
                "story_order_key": "s1",
                "coverage": (
                    "selected_packet_items_and_renderer_fragments; "
                    "upstream_inputs_of_derived_fragments_not_mapped"
                ),
            },
        },
    }


def test_default_is_a_verified_summary_with_overlapping_fragments_and_no_prose(
    payload: dict[str, Any],
) -> None:
    original = copy.deepcopy(payload)
    view = _view(payload)
    assert view["status"] == "available"
    assert view["count"] == view["matched_count"] == 3
    assert view["entries"] == []
    assert view["context"]["story_order_key"] == "s1"
    assert view["pagination"]["next_offset"] is None
    assert "αβ frozen packet text" not in json.dumps(view, ensure_ascii=False)
    assert payload == original


def test_pages_use_recorded_entry_indices_and_filter_exact_source_ids(
    payload: dict[str, Any],
) -> None:
    first = _view(payload, source_limit=2)
    assert [entry["entry_index"] for entry in first["entries"]] == [0, 1]
    assert first["pagination"] == {
        "offset": 0,
        "limit": 2,
        "shown": 2,
        "next_offset": 2,
        "truncated": True,
    }
    last = _view(payload, source_offset=2, source_limit=2)
    assert [entry["entry_index"] for entry in last["entries"]] == [2]
    assert last["pagination"]["next_offset"] is None
    for source_id in ("item-1", "record-1"):
        filtered = _view(payload, source_id=source_id, source_limit=1)
        assert filtered["count"] == 3 and filtered["matched_count"] == 1
        assert filtered["entries"][0]["entry_index"] == 1
    assert _view(payload, source_id="record", source_limit=100)["matched_count"] == 0
    assert _view(payload, source_offset=99, source_limit=100)["entries"] == []


@pytest.mark.parametrize("stage", ["system", "prompt"])
def test_stage_drift_with_unchanged_length_invalidates_the_whole_map(
    payload: dict[str, Any], stage: str
) -> None:
    payload[stage] = "X" + payload[stage][1:]
    view = _view(payload, source_limit=100)
    assert view["reason"] == "stage_identity_mismatch"
    assert view["status"] == "invalid_recorded_value"
    assert view["entries"] == [] and view["context"] is None


@pytest.mark.parametrize(
    "field,value", [("start", True), ("start", -1), ("end", 1000), ("end", 0), ("sha256", "0" * 64)]
)
def test_invalid_unselected_entry_cannot_be_hidden_by_filtering(
    payload: dict[str, Any], field: str, value: Any
) -> None:
    payload["prompt_sources"]["entries"][0][field] = value
    view = _view(payload, source_id="record-1", source_limit=1)
    assert view["status"] == "invalid_recorded_value"
    assert view["entries"] == [] and view["context"] is None


def test_item_hash_must_identify_its_exact_body_and_source_span_rejects_bools(
    payload: dict[str, Any],
) -> None:
    source = payload["prompt_sources"]["entries"][1]["source"]
    source["packed_text_sha256"] = "0" * 64
    assert _view(payload)["reason"] == "malformed_source_metadata"
    source["packed_text_sha256"] = payload["prompt_sources"]["entries"][1]["sha256"]
    source["source_span"] = [False, 10]
    assert _view(payload)["reason"] == "malformed_source_metadata"


@pytest.mark.parametrize("location", ["entry", "source", "context"])
def test_unrecognized_metadata_cannot_return_accidentally_stored_source_prose(
    payload: dict[str, Any], location: str
) -> None:
    entry = payload["prompt_sources"]["entries"][1]
    target = {
        "entry": entry,
        "source": entry["source"],
        "context": payload["prompt_sources"]["context"],
    }[location]
    target["text"] = "UNEXPECTED SOURCE PROSE MUST NOT ESCAPE"
    view = _view(payload, source_limit=100)
    assert view["status"] == "invalid_recorded_value"
    assert "UNEXPECTED SOURCE" not in json.dumps(view)
    assert view["entries"] == [] and view["context"] is None


def test_shelf_exposure_withholds_context_and_filter_presence(payload: dict[str, Any]) -> None:
    view = _view(payload, source_id="record-1", source_limit=100, shelf_exposure=True)
    assert view["status"] == "withheld"
    assert view["reason"] == "exemplar_shelf_exposure"
    assert view["count"] == 3 and view["matched_count"] is None
    assert view["entries"] == [] and view["context"] is None
    assert "record-1" not in json.dumps(view)
    assert view["stages"] == payload["prompt_sources"]["stages"]


def test_absent_map_stays_absent_and_revision_never_borrows_writer_map(
    payload: dict[str, Any],
) -> None:
    assert _view({"prompt": "old request"})["status"] == "not_recorded"
    view = _view(payload, source_limit=1, unavailable_reason="revision_request_not_recorded")
    assert view["status"] == "unavailable" and view["reason"] == "revision_request_not_recorded"
    assert view["entries"] == [] and view["stages"] == {} and view["context"] is None
    payload["prompt_sources"] = None
    assert _view(payload)["status"] == "invalid_recorded_value"


@pytest.mark.parametrize(
    "options",
    [
        {"source_offset": True},
        {"source_offset": -1},
        {"source_offset": 1.0},
        {"source_limit": True},
        {"source_limit": -1},
        {"source_limit": 101},
        {"source_limit": "1"},
        {"source_id": ""},
        {"source_id": False},
    ],
)
def test_invalid_queries_are_rejected_even_for_legacy_requests(options: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match=next(iter(options))):
        _view({}, **options)


def test_scope_mismatch_and_boolean_stage_length_fail_closed(payload: dict[str, Any]) -> None:
    payload["prompt_sources"]["context"]["book_id"] = "another-book"
    assert _view(payload)["reason"] == "source_context_scope_mismatch"
    payload["prompt_sources"]["context"]["book_id"] = "book"
    payload["prompt_sources"]["stages"]["system"]["chars"] = True
    assert _view(payload)["reason"] == "malformed_stage_identities"


def test_scene_plan_records_argument_identity_without_claiming_stored_text_equivalence(
    payload: dict[str, Any],
) -> None:
    argument = "A separate scene requirement."
    start = payload["prompt"].index(argument)
    payload["prompt_sources"]["entries"].append(
        {
            "stage": "prompt",
            "start": start,
            "end": start + len(argument),
            "sha256": _hash(argument),
            "kind": "scene_plan",
            "section": "scene_plan",
            "source": {
                "producer": "scene_plan_line",
                "rendered_argument_sha256": _hash(argument),
                "source_logical_id": "scene-1-plan",
                "plan_revision_id": "old-plan",
                "stored_text_sha256": _hash("different stored item"),
                "rendered_equals_stored": False,
            },
        }
    )
    view = _view(payload, source_id="scene-1-plan", source_limit=1)
    assert view["status"] == "available" and view["matched_count"] == 1
    assert view["entries"][0]["source"]["rendered_equals_stored"] is False
    assert argument not in json.dumps(view)


def test_empty_renderer_and_item_spans_keep_exact_empty_identity(payload: dict[str, Any]) -> None:
    entries = payload["prompt_sources"]["entries"]
    for entry in entries[:2]:
        entry["end"] = entry["start"]
        entry["sha256"] = _hash("")
    entries[1]["source"]["packed_text_sha256"] = _hash("")
    entries[1]["source"]["source_span"] = [0, 0]
    assert _view(payload, source_limit=100)["status"] == "available"


@pytest.mark.parametrize("case", ["full", "empty", "shelf"])
def test_current_producer_maps_are_readable_without_reconstructing_sources(case: str) -> None:
    from litharness.application import planner
    from tests import test_prompt_budget as examples
    from tests.test_prompt_sources import request_case

    mapping: dict[str, Any] = {}
    arguments = (
        {"book_title": None, "packet": examples._PACKET}
        if case == "empty"
        else request_case(shelf=case == "shelf")
    )
    system, prompt = planner.render_prompt(examples._BEAT, **arguments, source_map=mapping)
    view = _view(
        {"system": system, "prompt": prompt, "prompt_sources": mapping},
        source_limit=100,
        shelf_exposure=case == "shelf",
    )
    assert view["status"] == ("withheld" if case == "shelf" else "available")
    assert view["count"] == len(mapping["entries"])
    if case != "shelf":
        assert len(view["entries"]) == len(mapping["entries"])
        assert view["context"]["query_id"] == arguments["packet"].query_id


@pytest.mark.parametrize("changed", ["source_identity", "map_context", "other_payload_field"])
def test_full_input_digest_binds_metadata_even_when_all_text_hashes_still_match(
    payload: dict[str, Any], changed: str
) -> None:
    recorded = input_digest_for(payload)
    if changed == "source_identity":
        payload["prompt_sources"]["entries"][1]["source"]["source_logical_id"] = "forged-record"
    elif changed == "map_context":
        payload["prompt_sources"]["context"]["query_id"] = "forged-query"
    else:
        payload["context"] = {"items": 99}
    original = copy.deepcopy(payload)
    view = _view(payload, recorded_input_digest=recorded, source_limit=100)
    assert view["status"] == "invalid_recorded_value"
    assert view["reason"] == "input_digest_mismatch"
    assert view["entries"] == [] and view["context"] is None
    assert payload == original


@pytest.mark.parametrize(
    "recorded,status,reason",
    [
        (None, "unavailable", "input_digest_not_recorded"),
        ("invalid", "invalid_recorded_value", "invalid_recorded_input_digest"),
        (False, "invalid_recorded_value", "invalid_recorded_input_digest"),
    ],
)
def test_maps_without_a_valid_recorded_job_digest_do_not_expose_metadata(
    payload: dict[str, Any], recorded: Any, status: str, reason: str
) -> None:
    view = _view(payload, recorded_input_digest=recorded, source_limit=100)
    assert view["status"] == status and view["reason"] == reason
    assert view["entries"] == [] and view["context"] is None and view["stages"] == {}
    assert _view({}, recorded_input_digest=recorded)["status"] == "not_recorded"


@pytest.mark.parametrize("recorded_at", ["context", "payload", "both"])
def test_scene_plan_revision_must_match_each_recorded_job_plan_identity(
    payload: dict[str, Any], recorded_at: str
) -> None:
    entry = copy.deepcopy(payload["prompt_sources"]["entries"][0])
    entry["kind"] = "scene_plan"
    entry["source"] = {
        "producer": "scene_plan_line",
        "rendered_argument_sha256": entry["sha256"],
        "plan_revision_id": "wrong-plan",
    }
    payload["prompt_sources"]["entries"].append(entry)
    if recorded_at in ("context", "both"):
        payload["prompt_sources"]["context"]["plan_revision_id"] = "job-plan"
    if recorded_at in ("payload", "both"):
        payload["plan_revision_id"] = "job-plan"
    assert _view(payload, source_limit=100)["reason"] == "source_plan_revision_mismatch"
    entry["source"]["plan_revision_id"] = "job-plan"
    assert _view(payload, source_limit=100)["status"] == "available"
