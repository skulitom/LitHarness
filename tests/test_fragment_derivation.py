"""A packed promise line follows back to its recorded inputs, and never to inferred ones (§257)."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable, Iterator
from dataclasses import asdict, replace
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import planner
from litharness.application.fragment_derivation import (
    CLAIM,
    DERIVATION_COVERAGE,
    PRODUCER_FINGERPRINT,
    PRODUCER_FUNCTION,
    position_relation,
    promise_line_derivation,
)
from litharness.application.handlers import SCENE_DRAFT, draft_sampler
from litharness.application.prompt_source_view import (
    COMPOSITION_COVERAGE,
    build_prompt_source_view,
)
from litharness.application.reviser import revision_author_locks
from litharness.application.scene_trace import build_scene_trace
from litharness.domain.beats import beats_for, template_for
from litharness.domain.draft import DraftPolicy
from litharness.domain.events import payload_digest
from litharness.domain.jobs import Job, JobStatus, input_digest_for
from litharness.domain.promises import Promise, describe_owed, promise_id_for
from tests.conftest import PROJECT_ID
from tests.test_planner import START, _fixture

OPENED_BY = "rev-opened"
PLAN = "plan-window"
SCENE_HASH = "c" * 64


def _hash(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _row(book_id: str = "book", **overrides: Any) -> Promise:
    """A fully evidenced, scheduled row: every upstream identity the ledger can hold."""
    fields: dict[str, Any] = {
        "subject": "the_tower_door",
        "description": "Who barred the tower door from the inside.",
        "opened_at_key": "s1",
        "due_key": "s4",
        "opened_by_revision": OPENED_BY,
        "model": "summary-model",
        "opened_logical_id": "scene-1",
        "opened_start": 10,
        "opened_end": 52,
        "opened_content_hash": SCENE_HASH,
        "window_start_key": "s3",
        "window_end_key": "s4",
        "scheduled_by_plan_revision": PLAN,
    }
    fields.update(overrides)
    return Promise(promise_id=promise_id_for(book_id, fields["subject"]), **fields)


_BARE = {
    "model": "",
    "opened_logical_id": None,
    "opened_start": None,
    "opened_end": None,
    "opened_content_hash": None,
    "window_start_key": None,
    "window_end_key": None,
    "scheduled_by_plan_revision": None,
}


def _derive(promise: Promise, at: str | None = "s2") -> dict[str, Any]:
    return promise_line_derivation(
        promise, packed_sha256=_hash(describe_owed(promise)), drafting_at=at
    )


def _edges(derivation: dict[str, Any]) -> set[tuple[str, str, str]]:
    return {(edge["from"], edge["relation"], edge["to"]) for edge in derivation["edges"]}


def test_a_packed_promise_line_names_each_stored_input_it_was_rendered_from() -> None:
    promise = _row()
    derivation = _derive(promise)
    row = f"promise:{promise.promise_id}"
    assert derivation["status"] == "recorded" and derivation["claim"] == CLAIM
    assert derivation["producer"] == {
        "function": PRODUCER_FUNCTION,
        "fingerprint_sha256": PRODUCER_FINGERPRINT,
    }
    assert _edges(derivation) == {
        ("fragment", "rendered_from", row),
        (row, "opened_under", f"manuscript_revision:{OPENED_BY}"),
        (row, "opening_quote_located_in", f"scene_text:scene-1@{SCENE_HASH}"),
        (row, "payoff_window_proposed_by", f"plan_revision:{PLAN}"),
    }
    [node] = [node for node in derivation["nodes"] if node["kind"] == "promise_ledger_row"]
    assert node["row_sha256"] == payload_digest(asdict(promise))
    assert node["asserting_model"] == "summary-model" and node["status_at_read"] == "open"
    [scene] = [node for node in derivation["nodes"] if node["kind"] == "scene_text_span"]
    assert scene["span"] == [10, 52] and scene["content_hash"] == SCENE_HASH
    assert derivation["rendered_inputs"] == {
        "description_sha256": _hash(promise.description),
        "due_key": "s4",
        "window_start_key": "s3",
        "window_end_key": "s4",
    }
    assert derivation["temporal"] == {
        "drafting_at": "s2",
        "opened_at_key": "s1",
        "due_key": "s4",
        "opened_relation": "before",
        "due_relation": "after",
    }
    # The one input no row can name: which call (summary or seed) opened it.
    assert [item["input"] for item in derivation["not_recorded"]] == ["opening_call_request"]
    assert promise.description not in json.dumps(derivation)


def test_missing_row_history_is_named_not_recorded_and_never_filled() -> None:
    bare = _row(**_BARE)
    derivation = _derive(bare)
    row = f"promise:{bare.promise_id}"
    assert _edges(derivation) == {
        ("fragment", "rendered_from", row),
        (row, "opened_under", f"manuscript_revision:{OPENED_BY}"),
    }
    assert {item["input"]: item["reason"] for item in derivation["not_recorded"]} == {
        "opening_call_request": "promise_rows_do_not_record_the_call_that_opened_them",
        "asserting_model": "promise_row_names_no_model",
        "opening_evidence": "promise_row_has_no_located_opening_quote",
    }
    # A window with no plan revision is a scheduled line whose source was not recorded; an
    # unscheduled line has no window source to miss.
    orphan = _derive(replace(bare, window_start_key="s3", window_end_key="s4"))
    assert "payoff_window_source" in {item["input"] for item in orphan["not_recorded"]}
    assert not any(node["kind"] == "plan_revision" for node in orphan["nodes"])


def test_a_superseded_row_is_a_different_recorded_input_not_an_update() -> None:
    open_row = _row(**{**_BARE, "model": "summary-model"})
    scheduled = replace(
        open_row, window_start_key="s3", window_end_key="s4", scheduled_by_plan_revision=PLAN
    )
    before, after = _derive(open_row), _derive(scheduled)
    assert before["nodes"][0]["row_sha256"] != after["nodes"][0]["row_sha256"]
    assert before["rendered_sha256"] != after["rendered_sha256"]
    assert ("plan_revision:" + PLAN) not in json.dumps(before)
    assert ("plan_revision:" + PLAN) in {edge["to"] for edge in after["edges"]}


@pytest.mark.parametrize(
    ("key", "at", "relation"),
    [
        ("s1", "s2", "before"),
        ("s2", "s2", "at"),
        ("s3", "s2", "after"),
        ("s000002", "s000010", "before"),
        # One order-key space, two widths: `s2` sorts after `s10`, so no order is claimed.
        ("s2", "s10", "ambiguous"),
        ("s2", "s000003", "ambiguous"),
        # A schedule key and a scene key measure different things (§165).
        ("0350", "s2", "ambiguous"),
        ("clearance", "s2", "ambiguous"),
        (None, "s2", "unpositioned"),
        ("s1", None, "drafting_position_not_recorded"),
    ],
)
def test_story_positions_compare_only_within_one_space_and_width(
    key: str | None, at: str | None, relation: str
) -> None:
    assert position_relation(key, at) == relation


def test_an_ambiguous_boundary_is_recorded_as_ambiguous_and_nothing_else_moves() -> None:
    serial = _derive(_row(opened_at_key="s000001", due_key="s000004"), at="s2")
    assert serial["temporal"]["opened_relation"] == "ambiguous"
    assert serial["temporal"]["due_relation"] == "ambiguous"
    assert serial["status"] == "recorded" and serial["rendered_inputs"]["due_key"] == "s000004"


def test_a_line_whose_row_does_not_render_it_is_not_recorded() -> None:
    derivation = promise_line_derivation(_row(), packed_sha256=_hash("other"), drafting_at="s2")
    assert derivation == {
        "schema": "litharness.fragment-derivation.v1",
        "fragment_type": "promise_line",
        "claim": CLAIM,
        "status": "not_recorded",
        "reason": "rendered_text_mismatch",
    }


# --- composition: what the planner records ---------------------------------------------


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SqliteStore]:
    with SqliteStore.open(tmp_path / "derivation.db") as opened:
        yield opened


def _draft(store: SqliteStore, *rows: Callable[[str], Promise]) -> Job:
    """Draft the mystery fixture's first scene with `rows` open on its ledger."""
    book_id, branch_id = _fixture(store, "mystery")
    for row in rows:
        promise = row(book_id)
        store.record_promise(book_id, branch_id, promise)
        if promise.scheduled:
            # A window reaches the ledger only as the outline writes it, never at insert.
            assert promise.window_start_key and promise.window_end_key
            assert promise.scheduled_by_plan_revision
            store.schedule_payoff_window(
                book_id,
                branch_id,
                promise.promise_id,
                window_start_key=promise.window_start_key,
                window_end_key=promise.window_end_key,
                plan_revision_id=promise.scheduled_by_plan_revision,
            )
    planner.make_plan_selector(
        project_id=PROJECT_ID, policy=DraftPolicy(require_starting_sheet=False)
    )(store, "worker-a", START, 300.0)
    [job] = [j for j in store.jobs_by_status(JobStatus.QUEUED) if j.job_kind == SCENE_DRAFT]
    return store.load_job(job.job_id)


def _evidenced(book_id: str) -> Promise:
    return _row(book_id)


def _bare(book_id: str) -> Promise:
    return _row(book_id, subject="the_missing_key", description="Where the key went.", **_BARE)


def _view(payload: dict[str, Any], digest: str | None = None, **options: Any) -> dict[str, Any]:
    return build_prompt_source_view(
        payload,
        source_limit=100,
        recorded_input_digest=digest or input_digest_for(payload),
        **options,
    )


def _promise_entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        entry for entry in payload["prompt_sources"]["entries"] if "derivation" in entry["source"]
    ]


def test_recording_derivations_changes_no_request_byte_packet_or_sample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with SqliteStore.open(tmp_path / "recorded.db") as store:
        recorded = _draft(store, _evidenced, _bare)
    monkeypatch.setattr(planner, "attach_promise_derivations", lambda *args, **kwargs: None)
    with SqliteStore.open(tmp_path / "control.db") as store:
        control = _draft(store, _evidenced, _bare)

    assert recorded.job_id == control.job_id
    for stage in ("system", "prompt"):
        assert recorded.payload[stage].encode("utf-8") == control.payload[stage].encode("utf-8")
    for row in (_evidenced, _bare):
        assert describe_owed(row(recorded.payload["book_id"])) in recorded.payload["prompt"]

    def without_map(payload: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in payload.items() if key != "prompt_sources"}

    # Packet accounting, omissions, selection, plan identity: every other payload field.
    assert without_map(recorded.payload) == without_map(control.payload)
    bare_map = copy.deepcopy(recorded.payload["prompt_sources"])
    for entry in bare_map["entries"]:
        entry["source"].pop("derivation", None)
    bare_map["context"]["coverage"] = COMPOSITION_COVERAGE
    assert bare_map == control.payload["prompt_sources"]
    assert len(_promise_entries(recorded.payload)) == 2
    assert recorded.input_digest != control.input_digest
    assert draft_sampler(recorded, "default") == draft_sampler(control, "default")
    # The reviser recovers the same author-lock block from either map.
    assert revision_author_locks(
        recorded.payload, recorded_input_digest=recorded.input_digest
    ) == revision_author_locks(control.payload, recorded_input_digest=control.input_digest)


def test_the_packet_is_the_same_whether_the_ledger_is_read_inside_or_passed_in(
    store: SqliteStore,
) -> None:
    job = _draft(store, _evidenced, _bare)
    book_id, branch_id = job.payload["book_id"], job.payload["branch_id"]
    head = store.head(book_id, branch_id)
    assert head is not None
    beat = next(b for b in beats_for(head, template_for(head)) if b.logical_id == "scene-1")
    ledger = tuple(store.promises(book_id, branch_id, open_only=True))
    read_inside = planner.packet_for(store, head, beat)
    passed_in = planner.packet_for(store, head, beat, ledger=ledger)
    assert read_inside == passed_in
    assert read_inside.render() == passed_in.render()


def test_a_composed_map_exposes_the_derivation_through_the_source_view(
    store: SqliteStore,
) -> None:
    job = _draft(store, _evidenced, _bare)
    view = _view(job.payload, job.input_digest)
    assert view["status"] == "available"
    assert view["context"]["coverage"] == DERIVATION_COVERAGE
    assert view["derivations"] == {
        "fragment_types": ["promise_line"],
        "status": "recorded",
        "reason": None,
        "recorded": 2,
        "not_recorded": 0,
        "claim": CLAIM,
    }
    evidenced = _evidenced(job.payload["book_id"])
    [entry] = _view(job.payload, job.input_digest, source_id=evidenced.promise_id)["entries"]
    derivation = entry["source"]["derivation"]
    assert job.payload["prompt"][entry["start"] : entry["end"]] == describe_owed(evidenced)
    assert derivation["temporal"]["drafting_at"] == job.payload["selected_by"]["story_order_key"]
    assert derivation["temporal"]["opened_relation"] == "at"
    assert _edges(derivation) == _edges(_derive(evidenced, at="s1"))
    stored = {
        promise.promise_id: promise
        for promise in store.promises(job.payload["book_id"], job.payload["branch_id"])
    }
    row_digest = payload_digest(asdict(stored[evidenced.promise_id]))
    assert derivation["nodes"][0]["row_sha256"] == row_digest
    assert evidenced.description not in json.dumps(view)


def test_a_frozen_derivation_keeps_the_row_it_read_after_the_ledger_moves(
    store: SqliteStore,
) -> None:
    job = _draft(store, _bare)
    book_id, branch_id = job.payload["book_id"], job.payload["branch_id"]
    promise_id = _bare(book_id).promise_id
    [before] = _view(job.payload, job.input_digest, source_id=promise_id)["entries"]

    store.schedule_payoff_window(
        book_id,
        branch_id,
        promise_id,
        window_start_key="s3",
        window_end_key="s4",
        plan_revision_id=PLAN,
    )
    store.pay_promise(book_id, branch_id, promise_id, paid_at_key="s4", paid_by_revision="r4")
    frozen = store.load_job(job.job_id)
    [after] = _view(frozen.payload, frozen.input_digest, source_id=promise_id)["entries"]
    assert after == before
    row = after["source"]["derivation"]["nodes"][0]
    [current] = store.promises(book_id, branch_id)
    assert current.status == "paid" and row["status_at_read"] == "open"
    assert row["row_sha256"] != payload_digest(asdict(current))
    assert PLAN not in json.dumps(after)


def _derivation(payload: dict[str, Any]) -> dict[str, Any]:
    derivation: dict[str, Any] = _promise_entries(payload)[0]["source"]["derivation"]
    return derivation


def _set_opened_relation(payload: dict[str, Any]) -> None:
    _derivation(payload)["temporal"]["opened_relation"] = "before"


def _orphan_edge(payload: dict[str, Any]) -> None:
    _derivation(payload)["edges"][1]["to"] = "manuscript_revision:elsewhere"


def _relabel_node(payload: dict[str, Any]) -> None:
    _derivation(payload)["nodes"][1]["id"] = "manuscript_revision:elsewhere"


def _drop_not_recorded(payload: dict[str, Any]) -> None:
    _derivation(payload)["not_recorded"].pop()


def _smuggle_text(payload: dict[str, Any]) -> None:
    _derivation(payload)["description"] = "UNEXPECTED SOURCE PROSE MUST NOT ESCAPE"


def _smuggle_node_text(payload: dict[str, Any]) -> None:
    _derivation(payload)["nodes"][0]["text"] = "UNEXPECTED SOURCE PROSE MUST NOT ESCAPE"


def _change_rendered_digest(payload: dict[str, Any]) -> None:
    _derivation(payload)["rendered_sha256"] = "0" * 64


def _unhashable_node_kind(payload: dict[str, Any]) -> None:
    _derivation(payload)["nodes"][1]["kind"] = ["manuscript_revision"]


def _unhashable_missing_input(payload: dict[str, Any]) -> None:
    _derivation(payload)["not_recorded"][0]["input"] = ["opening_call_request"]


def _unhashable_reason(payload: dict[str, Any]) -> None:
    entry = _promise_entries(payload)[0]
    entry["source"]["derivation"] = {
        key: entry["source"]["derivation"][key] for key in ("schema", "fragment_type", "claim")
    } | {"status": "not_recorded", "reason": ["rendered_text_mismatch"]}


def _legacy_coverage(payload: dict[str, Any]) -> None:
    payload["prompt_sources"]["context"]["coverage"] = COMPOSITION_COVERAGE


@pytest.mark.parametrize(
    "tamper",
    [
        _set_opened_relation,
        _orphan_edge,
        _relabel_node,
        _drop_not_recorded,
        _smuggle_text,
        _smuggle_node_text,
        _change_rendered_digest,
        _unhashable_node_kind,
        _unhashable_missing_input,
        _unhashable_reason,
        _legacy_coverage,
    ],
)
def test_an_inconsistent_derivation_closes_the_map_even_when_rebound(
    store: SqliteStore, tamper: Callable[[dict[str, Any]], None]
) -> None:
    job = _draft(store, _evidenced)
    payload = copy.deepcopy(job.payload)
    tamper(payload)
    # Re-digested, so only the derivation's own consistency can refuse it.
    view = _view(payload)
    assert view["status"] == "invalid_recorded_value"
    assert view["reason"] == "malformed_source_metadata"
    assert view["entries"] == [] and view["context"] is None and view["derivations"] is None
    assert "UNEXPECTED SOURCE" not in json.dumps(view)


def test_a_changed_source_digest_after_enqueue_fails_the_job_binding(store: SqliteStore) -> None:
    job = _draft(store, _evidenced)
    payload = copy.deepcopy(job.payload)
    _derivation(payload)["nodes"][0]["row_sha256"] = "0" * 64
    view = _view(payload, job.input_digest)
    assert view["reason"] == "input_digest_mismatch"
    assert view["entries"] == [] and view["derivations"] is None


def test_a_map_from_before_the_extension_reports_derivation_not_recorded(
    store: SqliteStore,
) -> None:
    job = _draft(store, _evidenced)
    legacy = copy.deepcopy(job.payload)
    for entry in legacy["prompt_sources"]["entries"]:
        entry["source"].pop("derivation", None)
    _legacy_coverage(legacy)
    view = _view(legacy)
    assert view["status"] == "available"
    assert view["derivations"]["status"] == "not_recorded"
    assert view["derivations"]["reason"] == "composition_predates_fragment_derivation"
    promise_id = _evidenced(job.payload["book_id"]).promise_id
    [entry] = _view(legacy, source_id=promise_id)["entries"]
    assert "derivation" not in entry["source"]
    assert OPENED_BY not in json.dumps(view)


def test_shelf_exposure_withholds_every_upstream_identity(store: SqliteStore) -> None:
    job = _draft(store, _evidenced)
    promise = _evidenced(job.payload["book_id"])
    view = _view(job.payload, job.input_digest, source_id=promise.promise_id, shelf_exposure=True)
    assert view["status"] == "withheld" and view["derivations"] is None
    rendered = json.dumps(view)
    for identity in (promise.promise_id, OPENED_BY, PLAN, SCENE_HASH, "summary-model"):
        assert identity not in rendered


def test_scene_trace_follows_the_line_and_withholds_it_under_shelf_provenance(
    store: SqliteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = _draft(store, _evidenced)
    book_id, branch_id = job.payload["book_id"], job.payload["branch_id"]
    promise = _evidenced(book_id)
    head = store.head(book_id, branch_id)
    assert head is not None

    def trace() -> dict[str, Any]:
        return build_scene_trace(
            store,
            book_id,
            branch_id,
            head.node("scene-1"),
            head,
            source_id=promise.promise_id,
            source_limit=10,
        )

    [entry] = trace()["source_map"]["entries"]
    assert f"manuscript_revision:{OPENED_BY}" in {
        edge["to"] for edge in entry["source"]["derivation"]["edges"]
    }
    original_load = store.load_job

    def shelf_load(job_id: str) -> Job:
        recorded = original_load(job_id)
        payload = {**recorded.payload, "exemplars": {"captured": True}}
        return replace(recorded, payload=payload, input_digest=input_digest_for(payload))

    monkeypatch.setattr(store, "load_job", shelf_load)
    withheld = trace()
    assert withheld["source_map"]["status"] == "withheld"
    assert promise.promise_id not in json.dumps(withheld["source_map"])
    assert OPENED_BY not in json.dumps(withheld)


def test_the_mcp_scene_trace_returns_the_recorded_derivation(tmp_path: Path) -> None:
    from litharness.mcp_server import Binding, make_tools

    path = tmp_path / "mcp.db"
    with SqliteStore.open(path) as opened:
        job = _draft(opened, _evidenced, _bare)
    promise = _evidenced(job.payload["book_id"])
    trace = make_tools(Binding(database=path, roster_database=path, profile="read", client="t"))[
        "scene_trace"
    ]
    result = trace(scene="scene-1", source_id=promise.promise_id, source_limit=5)
    source_map = result["source_map"]
    assert source_map["derivations"]["recorded"] == 2
    [entry] = source_map["entries"]
    assert entry["source"]["derivation"]["temporal"]["opened_relation"] == "at"
    assert promise.description not in json.dumps(result)
