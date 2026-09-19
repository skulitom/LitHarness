"""Promise controls must prove their edits without claiming an unproved semantic oracle."""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import replace
from pathlib import Path

import litharness_contracts as lc
import pytest

from litharness.adapters.sqlite_store import MigrationsPending, SqliteStore
from litharness.domain.nodes import Node, NodeKind
from litharness.domain.promises import PROMISE_OPEN, PROMISE_PAID, Promise
from litharness.domain.revision import build_revision, node_version_id
from litharness.domain.serials import SerialShape
from litharness.domain.text import content_hash

PATH = Path(__file__).resolve().parents[1] / (
    "research/quality-measurement/promise_payoff_builder.py"
)
OPENING = "Rook promised to return the key."
PAYMENT = "Rook returned the bronze key."
DONOR = "Snow covered the narrow road."
OTHER_DONOR = "Rain crossed the silent yard."


@pytest.fixture(scope="module")
def builder():
    spec = importlib.util.spec_from_file_location("promise_payoff_builder_test", PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def fixture_book(*, payment_scene=None, middle=None, opening_scene=None, payment_quote=PAYMENT):
    prose = [
        opening_scene or OPENING + "\n\n" + "The road lay silent. " * 100,
        "The journey continued." if middle is None else middle,
        payment_scene or PAYMENT + "\n\n" + DONOR + "\n\n" + OTHER_DONOR,
    ]
    nodes = [Node(logical_id="book", kind=NodeKind.BOOK, position_key="000010")]
    nodes.extend(Node.text_node(
        f"scene-{i}", NodeKind.SCENE, f"{i:05}0", text, parent_logical_id="book",
    ) for i, text in enumerate(prose, 1))
    revision = build_revision("book-test", "main", tuple(nodes))
    start = prose[2].index(payment_quote)
    promise = Promise(
        promise_id="promise-key", subject="key", description="Return the key",
        opened_at_key="s000001", due_key="s000003", opened_by_revision=revision.revision_id,
        status=PROMISE_PAID, paid_at_key="s000003", paid_by_revision=revision.revision_id,
        opened_logical_id="scene-1", opened_start=prose[0].index(OPENING),
        opened_end=prose[0].index(OPENING) + len(OPENING),
        opened_content_hash=content_hash(prose[0]),
        paid_logical_id="scene-3", paid_start=start, paid_end=start + len(payment_quote),
        paid_content_hash=content_hash(prose[2]),
    )
    return revision, promise


def build(builder, revision, promises, records=(), **kwargs):
    return builder.build_battery(
        revision, records, promises, source_group="world-test", shape=SerialShape(1, 6), **kwargs,
    )


def test_real_context_and_reference_withdrawal_are_verified_without_semantic_promotion(builder):
    revision, promise = fixture_book()
    before = revision.revision_id, revision.rendered_text()
    report, public, private = build(builder, revision, [promise])
    assert report["constructed_items"] == 1
    assert report["construction_ready"]
    assert not report["eligible_for_model_run"]
    assert not report["production_authority"]
    assert report["model_calls"] == 0
    assert report["packets"] == 4
    item = private["items"][0]
    variants = {v["role"]: v for v in item["variants"]}
    texts = {role: v["packet"]["passage"] for role, v in variants.items()}
    clean = texts["clean"]
    assert "The journey continued." in clean  # no anchor/target-only context shortcut
    assert item["scene_count"] == 3
    for role, variant in variants.items():
        text = variant["packet"]["passage"]
        assert text.count(OPENING) == 1
        assert (PAYMENT in text) == variant["registered_payment_visible"]
        assert variant["registered_payment_visible"] == (role != "payment_evidence_withheld")
    target = builder.Span(**item["target_context_span"])
    control = builder.Span(**item["control_context_span"])
    assert builder.remove(clean, target) == texts["payment_evidence_withheld"]
    assert builder.remove(clean, control) == texts["other_paragraph_withheld"]
    assert not target.overlaps(control)
    for span, role in (
        (target, "payment_evidence_withheld"), (control, "other_paragraph_withheld"),
    ):
        assert builder.deletion_fingerprint(clean, span, 2) == builder._fingerprint(
            clean, texts[role], position=span.start, anchor_distance=2,
        )
    assert DONOR not in texts["other_paragraph_withheld"]  # nearest deterministic donor
    assert clean.split() == texts["whitespace_only"].split()
    assert (revision.revision_id, revision.rendered_text()) == before
    assert build(builder, revision, [promise]) == (report, public, private)


def test_public_packets_never_contain_private_metadata_or_sibling_groupings(builder):
    revision, promise = fixture_book()
    report, public, private = build(builder, revision, [promise])
    assert set(public) == {"version", "packets"}
    assert len({packet["presentation_id"] for packet in public["packets"]}) == 4
    for packet in public["packets"]:
        assert set(packet) == {"presentation_id", "promise_opening", "passage"}
        assert packet["promise_opening"] == OPENING
    serialized = json.dumps(report)
    assert OPENING not in serialized and PAYMENT not in serialized and DONOR not in serialized
    assert "registered_payment_visible" not in json.dumps(public)
    assert private["items"][0]["opening"]["quote"] == OPENING


@pytest.mark.parametrize(("change", "reason"), [
    ({"status": PROMISE_OPEN}, "not_paid"),
    ({"paid_content_hash": "stale"}, "missing_current_unique_evidence"),
    ({"opened_content_hash": "stale"}, "missing_current_unique_evidence"),
    ({"paid_at_key": "s000000"}, "payment_not_after_opening"),
    ({"paid_at_key": None}, "payment_not_after_opening"),
    ({"paid_at_key": "s000001"}, "story_position_disagrees_with_scene"),
])
def test_ledger_and_anchor_faults_never_enter_construction(builder, change, reason):
    revision, promise = fixture_book()
    report, public, private = build(builder, revision, [replace(promise, **change)])
    assert report["reason_counts"] == {reason: 1}
    assert not report["construction_ready"]
    assert not public["packets"] and not private["items"]


@pytest.mark.parametrize(("options", "reason"), [
    ({"middle": PAYMENT}, "ambiguous_context_evidence"),
    ({"middle": ""}, "incomplete_context"),
    ({"payment_scene": PAYMENT + "\n\nOnly snow."}, "no_matched_unprotected_paragraph"),
    ({"payment_scene": PAYMENT + "\n\n" + PAYMENT}, "missing_current_unique_evidence"),
    ({"payment_quote": PAYMENT + "\n\n" + DONOR}, "payment_crosses_paragraphs"),
])
def test_ambiguous_contexts_and_unmatched_controls_are_rejected(builder, options, reason):
    revision, promise = fixture_book(**options)
    report, _, _ = build(builder, revision, [promise])
    assert report["reason_counts"] == {reason: 1}


def test_context_limits_refuse_instead_of_truncating(builder):
    revision, promise = fixture_book()
    report, public, _ = build(builder, revision, [promise], max_chars=100)
    assert report["reason_counts"] == {"context_exceeds_limit": 1}
    assert not public["packets"]


def test_single_anchor_of_an_unpaid_promise_is_protected_from_deletion(builder):
    revision, promise = fixture_book()
    shared = replace(
        promise, promise_id="promise-later", status=PROMISE_OPEN,
        opened_logical_id=promise.paid_logical_id,
        opened_start=promise.paid_start, opened_end=promise.paid_end,
        opened_content_hash=promise.paid_content_hash,
        paid_logical_id=None, paid_start=None, paid_end=None, paid_content_hash=None,
        paid_at_key=None, paid_by_revision=None,
    )
    report, _, _ = build(builder, revision, [promise, shared])
    assert report["reason_counts"] == {"not_paid": 1, "target_overlaps_other_evidence": 1}


def test_all_located_state_spans_are_protected_even_when_a_record_has_several(builder):
    revision, promise = fixture_book()
    node = revision.node("scene-3")
    text = node.content
    evidence = [lc.EvidenceSpan(
        source=lc.ResourceRef(
            project_id="project-test", book_id=revision.book_id, branch_id=revision.branch_id,
            logical_id=node.logical_id, kind=lc.ResourceKind.MANUSCRIPT_SCENE,
            version_id=node_version_id(node),
        ),
        start=text.index(quote), end=text.index(quote) + len(quote),
        content_sha256=content_hash(quote),
    ) for quote in (DONOR, OTHER_DONOR)]
    record = lc.StateRecord(
        record_id="weather", kind=lc.StateRecordKind.EVENT, subject="weather",
        predicate="observed", value="snow and rain", authority=lc.StateAuthority.ACCEPTED_CANON,
        evidence=evidence,
    )
    report, _, _ = build(builder, revision, [promise], [record])
    assert report["reason_counts"] == {"no_matched_unprotected_paragraph": 1}


def test_paragraph_boundaries_preserve_unicode_crlf_and_source_offsets(builder):
    text = "  Élise paid.\r\n \r\n\tSnow fell.  \r\n\r\n"
    spans = builder.paragraphs(text)
    assert [text[s.start:s.end] for s in spans] == ["Élise paid.", "Snow fell."]
    assert builder.paragraphs(" \n\n\t") == ()
    with pytest.raises(ValueError, match="bounded by whitespace"):
        builder.deletion_fingerprint("part of a word", builder.Span(1, 3), 1)


def test_invalid_configuration_and_duplicate_identity_fail_closed(builder):
    revision, promise = fixture_book()
    with pytest.raises(ValueError, match="Duplicate"):
        build(builder, revision, [promise, promise])
    with pytest.raises(ValueError, match="positive context"):
        build(builder, revision, [promise], max_chars=0)
    with pytest.raises(ValueError, match="source group"):
        builder.build_battery(revision, [], [promise], source_group="", shape=SerialShape(1, 6))


def test_missing_source_is_not_created_and_existing_artifacts_are_not_overwritten(
    builder, tmp_path,
):
    source, out = tmp_path / "absent.db", tmp_path / "out"
    with pytest.raises(FileNotFoundError):
        builder.build_from_database(source, out, source_group="world-test")
    assert not source.exists() and not out.exists()
    out.mkdir()
    sentinel = out / "report.json"
    sentinel.write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        builder.build_from_database(source, out, source_group="world-test")
    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_read_only_snapshot_includes_wal_and_refuses_pending_migrations(builder, tmp_path):
    revision, promise = fixture_book()
    database = tmp_path / "book.db"
    with SqliteStore.open(database) as writer:
        writer.commit_revision(revision, created_at="2026-09-19T00:00:00Z")
        writer.record_promise(revision.book_id, revision.branch_id, promise)
        before = writer.head(revision.book_id, revision.branch_id).revision_id
        report = builder.build_from_database(database, tmp_path / "out", source_group="world-test")
        assert report["revision_id"] == before
        assert report["constructed_items"] == 1
        assert writer.head(revision.book_id, revision.branch_id).revision_id == before
        with SqliteStore.open_read_only(tmp_path / "out/source.db") as snapshot:
            assert snapshot.head(revision.book_id, revision.branch_id) == revision
        assert report["provenance"]["source_access"].startswith("SQLite mode=ro")
        assert b"\r" not in (tmp_path / "out/report.json").read_bytes()
        # A schema lag must be diagnosed, never silently repaired by construction.
        writer._connection.execute(
            "DELETE FROM schema_migrations WHERE name = (SELECT MAX(name) FROM schema_migrations)"
        )
        with pytest.raises(MigrationsPending):
            builder.build_from_database(database, tmp_path / "pending", source_group="world-test")
        assert not (tmp_path / "pending").exists()
