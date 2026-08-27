"""Call-free ecological evidence admission and shortcut controls."""

from __future__ import annotations

import json
from dataclasses import replace

import litharness_contracts as lc

from litharness.domain.nodes import Node, NodeKind
from litharness.domain.promises import PROMISE_PAID, Promise
from litharness.domain.revision import build_revision, node_version_id
from litharness.domain.salience import (
    ContextRung,
    InterventionFamily,
    LocatedEvidence,
    build_state_continuity_items,
    context_rung_for,
    ecological_manifest,
    evidence_census,
    private_battery,
    public_battery,
)
from litharness.domain.serials import SerialShape
from litharness.domain.text import content_hash


def _revision():
    prose = {
        1: "The west gate was locked. Rook marked the debt in red ink.",
        2: (
            "Rook pulled the release lever. His debt forced the choice. "
            "The gate opened. The lever consumed one brass token. It produced safe passage."
        ),
        3: "Rain crossed the empty yard.",
        4: "At dusk, the west gate was still locked. Nobody had touched its chain.",
        5: "Rook counted the remaining tokens.",
        6: "The watch changed at midnight.",
        7: "A courier arrived without a seal.",
        8: "Rook burned the red debt mark, settling what he owed.",
    }
    nodes = [Node(logical_id="book", kind=NodeKind.BOOK, position_key="010")]
    nodes.extend(
        Node.text_node(
            f"scene-{index}",
            NodeKind.SCENE,
            f"{index + 1:03}0",
            text,
            parent_logical_id="book",
        )
        for index, text in prose.items()
    )
    return build_revision("book-salience", "main", tuple(nodes))


def _record(
    revision,
    *,
    record_id: str,
    logical_id: str,
    quote: str,
    subject: str,
    predicate: str,
    value: str | None = None,
    object_ref: str | None = None,
) -> lc.StateRecord:
    node = revision.node(logical_id)
    text = node.content or ""
    start = text.index(quote)
    return lc.StateRecord(
        record_id=record_id,
        kind=lc.StateRecordKind.EVENT,
        subject=subject,
        predicate=predicate,
        value=value,
        object_ref=object_ref,
        story_position=lc.StoryPosition(order_key=f"s{int(logical_id.split('-')[1]):06}"),
        authority=lc.StateAuthority.ACCEPTED_CANON,
        evidence=[
            lc.EvidenceSpan(
                source=lc.ResourceRef(
                    project_id="project-test",
                    book_id=revision.book_id,
                    branch_id=revision.branch_id,
                    logical_id=logical_id,
                    kind=lc.ResourceKind.MANUSCRIPT_SCENE,
                    version_id=node_version_id(node),
                ),
                start=start,
                end=start + len(quote),
                content_sha256=content_hash(quote),
            )
        ],
    )


def _records(revision) -> list[lc.StateRecord]:
    records = [
        _record(
            revision,
            record_id="state-a",
            logical_id="scene-1",
            quote="The west gate was locked.",
            subject="west-gate",
            predicate="access_state",
            value="locked",
        ),
        _record(
            revision,
            record_id="state-b",
            logical_id="scene-4",
            quote="At dusk, the west gate was still locked.",
            subject="west-gate",
            predicate="access_state",
            value="locked",
        ),
    ]
    roles = (
        ("actor", "Rook pulled the release lever.", "rook"),
        ("caused_by", "His debt forced the choice.", "goal-debt"),
        ("effect", "The gate opened.", "gate-opened"),
        ("consumes", "The lever consumed one brass token.", "brass-token"),
        ("produces", "It produced safe passage.", "safe-passage"),
    )
    records.extend(
        _record(
            revision,
            record_id=f"change-{role}",
            logical_id="scene-2",
            quote=quote,
            subject="change-open-gate",
            predicate=role,
            object_ref=target,
        )
        for role, quote, target in roles
    )
    return records


def _promise(revision) -> Promise:
    opening = revision.node("scene-1").content or ""
    payment = revision.node("scene-8").content or ""
    opening_quote = "Rook marked the debt in red ink."
    payment_quote = "Rook burned the red debt mark, settling what he owed."
    return Promise(
        promise_id="promise-red-debt",
        subject="red debt mark",
        description="Rook must erase the debt mark",
        opened_at_key="s000001",
        due_key="s000008",
        opened_by_revision=revision.revision_id,
        status=PROMISE_PAID,
        paid_at_key="s000008",
        paid_by_revision=revision.revision_id,
        opened_logical_id="scene-1",
        opened_start=opening.index(opening_quote),
        opened_end=opening.index(opening_quote) + len(opening_quote),
        opened_content_hash=content_hash(opening),
        paid_logical_id="scene-8",
        paid_start=payment.index(payment_quote),
        paid_end=payment.index(payment_quote) + len(payment_quote),
        paid_content_hash=content_hash(payment),
    )


def test_the_census_admits_only_complete_current_span_backed_relations() -> None:
    revision = _revision()
    census = evidence_census(
        revision,
        _records(revision),
        (_promise(revision),),
        shape=SerialShape(2, 3),
    )
    counts = census.to_payload()["candidate_counts"]

    assert counts == {
        InterventionFamily.STATE_CONTINUITY.value: 1,
        InterventionFamily.EVENT_CONSEQUENCE.value: 1,
        InterventionFamily.PROGRESSION_COST.value: 1,
        InterventionFamily.CHARACTER_CAUSE.value: 1,
        InterventionFamily.PROMISE_PAYOFF.value: 1,
    }
    assert census.digest


def test_state_siblings_match_shallow_fingerprints_and_keep_hidden_text_private() -> None:
    revision = _revision()
    census = evidence_census(
        revision,
        _records(revision),
        (),
        shape=SerialShape(2, 3),
    )
    items = build_state_continuity_items(census, revision)

    assert len(items) == 1
    item = items[0]
    assert "unlocked" in item.damaged_text
    assert "LOCKED" in item.sham_text
    assert item.damage_fingerprint == item.sham_fingerprint
    manifest = ecological_manifest(census, items)
    rendered_manifest = json.dumps(manifest)
    assert item.clean_text not in rendered_manifest
    assert item.expected_value not in rendered_manifest
    assert "anchor_record_id" not in rendered_manifest
    assert manifest["promotion_bar"] is None
    public = public_battery(items)
    rendered_public = json.dumps(public)
    assert item.clean_text in rendered_public
    assert "damaged_text" not in rendered_public
    assert '"clean"' not in rendered_public
    private = private_battery(census, items)
    assert private["items"][0]["variant_keys"]
    assert private["census"]["candidates"]


def test_stale_or_ambiguous_evidence_is_counted_as_unavailable() -> None:
    revision = _revision()
    records = _records(revision)
    stale_span = replace(records[1].evidence[0], content_sha256="stale")
    records[1] = replace(records[1], evidence=[stale_span])

    census = evidence_census(
        revision,
        records,
        (),
        shape=SerialShape(2, 3),
    )

    assert census.to_payload()["candidate_counts"]["state_continuity"] == 0
    assert census.rejected["state_continuity:missing_unique_evidence"] == 1


def test_long_context_rungs_are_distance_based_not_context_window_claims() -> None:
    nodes = [Node(logical_id="book", kind=NodeKind.BOOK, position_key="000")]
    nodes.extend(
        Node.text_node(
            f"scene-{index}",
            NodeKind.SCENE,
            f"{index:04}",
            f"Scene {index}.",
            parent_logical_id="book",
        )
        for index in range(1, 121)
    )
    revision = build_revision("long-book", "main", tuple(nodes))
    evidence = (
        LocatedEvidence("a", "scene-1", 0, 5, "hash-a", "Scene", "s000001"),
        LocatedEvidence("b", "scene-120", 0, 5, "hash-b", "Scene", "s000120"),
    )

    assert context_rung_for(evidence, revision, SerialShape(2, 6)) is ContextRung.CROSS_VOLUME
