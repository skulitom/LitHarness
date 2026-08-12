"""Domain-layer gates for Stage 0's exit criterion.

The exit sentence is "revisions, patches, events, and restore work end-to-end without a
model". This module covers revisions and patches; `test_store.py` covers events, jobs,
outbox and restore.
"""

from __future__ import annotations

import litharness_contracts as lc
import pytest
from hypothesis import given
from hypothesis import strategies as st

from litharness.domain.jobs import Job
from litharness.domain.nodes import BlockKind, LockKind, LockViolation, Node, NodeKind
from litharness.domain.patch import PatchPolicy, Veto, apply_patch
from litharness.domain.position import initial_keys, key_between, parse_key
from litharness.domain.revision import Revision, node_version_id
from litharness.domain.text import canonicalize, content_hash, is_canonical
from tests.conftest import BOOK_ID, BRANCH_ID, build_patch, make_revision, meta

# --- canonical text ---------------------------------------------------------------


@given(st.text())
def test_canonicalization_is_idempotent(text: str) -> None:
    once = canonicalize(text)
    assert canonicalize(once) == once
    assert is_canonical(once)


@pytest.mark.parametrize("variant", ["a\r\nb", "a\rb", "a\nb"])
def test_line_ending_variants_hash_identically(variant: str) -> None:
    """The property the sibling repo's `core.autocrlf=true` would otherwise have broken."""
    assert content_hash(variant) == content_hash("a\nb")


def test_crlf_does_not_become_two_newlines() -> None:
    assert canonicalize("a\r\nb") == "a\nb"


def test_node_rejects_non_canonical_content() -> None:
    with pytest.raises(ValueError, match="not canonical"):
        Node(logical_id="s", kind=NodeKind.SCENE, position_key="010", content="a\r\nb")


def test_node_rejects_a_hash_that_does_not_match_its_text() -> None:
    with pytest.raises(ValueError, match="content_sha256"):
        Node(
            logical_id="s",
            kind=NodeKind.SCENE,
            position_key="010",
            content="hello",
            content_sha256=content_hash("goodbye"),
        )


# --- position keys ----------------------------------------------------------------


def test_initial_keys_match_the_golden_fixture_format() -> None:
    assert initial_keys(6) == ["010", "020", "030", "040", "050", "060"]


def test_insertion_between_neighbours_needs_no_rebalance() -> None:
    keys = initial_keys(6)
    insertion = key_between("010", "020", keys)
    assert not insertion.is_rebalance
    assert "010" < insertion.key < "020"


def test_exhausted_gap_rebalances_the_whole_sibling_set() -> None:
    siblings = ["010", "011"]
    insertion = key_between("010", "011", siblings)
    assert insertion.is_rebalance
    assert set(insertion.rebalanced) == {"010", "011"}
    renumbered = sorted([*insertion.rebalanced.values(), insertion.key])
    assert renumbered == sorted(renumbered, key=parse_key)
    assert len({len(key) for key in renumbered}) == 1, "uniform width or string sort breaks"


@given(st.integers(min_value=1, max_value=200))
def test_generated_keys_sort_lexicographically_and_numerically_alike(count: int) -> None:
    keys = initial_keys(count)
    assert keys == sorted(keys)
    assert keys == sorted(keys, key=parse_key)


# --- revisions --------------------------------------------------------------------


def test_revision_ids_are_content_addressed(revision: Revision) -> None:
    twin = Revision(book_id=BOOK_ID, branch_id=BRANCH_ID, nodes=revision.nodes)
    assert twin.revision_id == revision.revision_id


def test_editing_one_node_leaves_every_other_node_version_untouched(revision: Revision) -> None:
    """The anti-fan-out decision: spans citing unedited nodes must stay resolvable."""
    before = revision.version_ids
    edited = revision.replacing([revision.node("scene-3").with_content("Rewritten.")])
    after = edited.version_ids
    assert [key for key in before if before[key] != after[key]] == ["scene-3"]
    assert edited.revision_id != revision.revision_id
    assert edited.parent_revision_id == revision.revision_id


def test_fork_shares_node_versions_rather_than_copying_them(revision: Revision) -> None:
    forked = revision.forked_to("44444444-4444-5444-8444-444444444444")
    assert forked.version_ids == revision.version_ids
    assert forked.revision_id != revision.revision_id


def test_revision_rejects_a_node_whose_parent_is_absent() -> None:
    orphan = Node(
        logical_id="scene-x", kind=NodeKind.SCENE, position_key="010", parent_logical_id="ghost"
    )
    with pytest.raises(ValueError, match="unknown parent"):
        Revision(book_id=BOOK_ID, branch_id=BRANCH_ID, nodes=(orphan,))


def test_tombstoned_nodes_leave_reading_order_but_stay_in_the_revision(
    revision: Revision,
) -> None:
    edited = revision.replacing([revision.node("scene-4").tombstone("cut in revision 2")])
    assert "scene-4" not in [node.logical_id for node in edited.in_reading_order()]
    assert edited.node("scene-4").tombstoned is True
    assert edited.node("scene-4").content is not None, "history must stay reconstructible"


def test_contract_round_trip_preserves_identity_and_extensions(revision: Revision) -> None:
    blocked = revision.replacing(
        [
            Node(
                logical_id="scene-2",
                kind=NodeKind.SCENE,
                position_key=revision.node("scene-2").position_key,
                parent_logical_id="book",
                content=revision.node("scene-2").content,
                lock=LockKind.PUBLISHED,
            )
        ]
    )
    restored = Revision.from_contract(blocked.to_contract(meta("manuscript_revision", "r")))
    assert restored.revision_id == blocked.revision_id
    assert restored.node("scene-2").lock is LockKind.PUBLISHED


def test_block_nodes_carry_a_kind_and_payload_through_the_contract() -> None:
    block = Node(
        logical_id="status-1",
        kind=NodeKind.BLOCK,
        position_key="010",
        content="[STATUS] Level 3  HP 24/30  Gold 45",
        block_kind=BlockKind.STATUS_WINDOW,
        block_payload={"level": 3, "hp": 24, "hp_max": 30, "gold": 45},
    )
    revision = Revision(book_id=BOOK_ID, branch_id=BRANCH_ID, nodes=(block,))
    restored = Revision.from_contract(revision.to_contract(meta("manuscript_revision", "r")))
    node = restored.node("status-1")
    assert node.block_kind is BlockKind.STATUS_WINDOW
    assert node.block_payload["gold"] == 45


# --- locks ------------------------------------------------------------------------


def test_content_lock_blocks_text_change_but_not_removal() -> None:
    node = Node.text_node("s", NodeKind.SCENE, "010", "text", lock=LockKind.CONTENT)
    with pytest.raises(LockViolation):
        node.with_content("other")
    assert node.tombstone("cut").tombstoned is True


def test_structure_lock_blocks_removal_but_not_text_change() -> None:
    node = Node.text_node("s", NodeKind.SCENE, "010", "text", lock=LockKind.STRUCTURE)
    assert node.with_content("other").content == "other"
    with pytest.raises(LockViolation):
        node.tombstone("cut")


def test_published_lock_freezes_both() -> None:
    node = Node.text_node("s", NodeKind.SCENE, "010", "text", lock=LockKind.PUBLISHED)
    with pytest.raises(LockViolation):
        node.with_content("other")
    with pytest.raises(LockViolation):
        node.tombstone("cut")


# --- bounded patches --------------------------------------------------------------


def test_accepted_patch_preserves_every_untouched_character(revision: Revision) -> None:
    node = revision.node("scene-1")
    assert node.content is not None
    original = node.content
    outcome = apply_patch(revision, build_patch(revision, "scene-1", [(0, 4, "Rooke")]))
    assert outcome.accepted, outcome.vetoes
    assert outcome.node_after is not None and outcome.node_after.content is not None
    assert outcome.node_after.content == "Rooke" + original[4:]
    assert outcome.node_after.content[5:] == original[4:]


def test_patch_against_a_stale_version_is_vetoed(revision: Revision) -> None:
    outcome = apply_patch(
        revision, build_patch(revision, "scene-1", [(0, 4, "X")], base_version_id="deadbeef" * 8)
    )
    assert not outcome.accepted
    assert Veto.STALE_BASE_VERSION in outcome.veto_kinds


def test_patch_citing_text_that_moved_is_vetoed_by_span_hash(revision: Revision) -> None:
    """The realistic staleness case: right offsets, different text."""
    patch = build_patch(revision, "scene-1", [(0, 4, "X")])
    moved = revision.replacing([revision.node("scene-1").with_content("Shifted. " + "x" * 60)])
    outcome = apply_patch(
        moved,
        lc.BoundedPatch(
            meta=patch.meta,
            target=patch.target,
            base_version_id=node_version_id(moved.node("scene-1")),
            base_content_sha256=moved.node("scene-1").content_sha256 or "",
            ops=patch.ops,
            idempotency_key=patch.idempotency_key,
        ),
    )
    assert not outcome.accepted
    assert Veto.SPAN_HASH_MISMATCH in outcome.veto_kinds


def test_overlapping_spans_are_vetoed(revision: Revision) -> None:
    outcome = apply_patch(revision, build_patch(revision, "scene-1", [(0, 10, "A"), (5, 15, "B")]))
    assert not outcome.accepted
    assert Veto.OVERLAPPING_SPANS in outcome.veto_kinds


def test_unlicensed_deletion_is_vetoed_and_a_licensed_one_is_not(revision: Revision) -> None:
    unlicensed = apply_patch(revision, build_patch(revision, "scene-2", [(0, 20, "")]))
    assert not unlicensed.accepted
    assert Veto.UNLICENSED_DELETION in unlicensed.veto_kinds

    licensed = apply_patch(
        revision, build_patch(revision, "scene-2", [(0, 20, "")], licensed_by="f-gold-ledger")
    )
    assert licensed.accepted, licensed.vetoes


def test_runaway_length_movement_is_vetoed(revision: Revision) -> None:
    node = revision.node("scene-1")
    assert node.content is not None
    outcome = apply_patch(
        revision, build_patch(revision, "scene-1", [(0, len(node.content), "x" * 5000)])
    )
    assert not outcome.accepted
    assert Veto.LENGTH_MOVEMENT in outcome.veto_kinds


def test_patch_against_locked_content_is_vetoed(revision: Revision) -> None:
    locked = revision.replacing(
        [
            Node(
                logical_id="scene-1",
                kind=NodeKind.SCENE,
                position_key=revision.node("scene-1").position_key,
                parent_logical_id="book",
                content=revision.node("scene-1").content,
                lock=LockKind.PUBLISHED,
            )
        ]
    )
    outcome = apply_patch(locked, build_patch(locked, "scene-1", [(0, 4, "X")]))
    assert not outcome.accepted
    assert Veto.CONTENT_LOCKED in outcome.veto_kinds


def test_span_outside_the_text_is_vetoed(revision: Revision) -> None:
    node = revision.node("scene-1")
    assert node.content is not None
    patch = build_patch(revision, "scene-1", [(0, 4, "X")])
    patch.ops[0].target_span.start = 9000
    patch.ops[0].target_span.end = 9010
    outcome = apply_patch(revision, patch)
    assert not outcome.accepted
    assert Veto.SPAN_OUT_OF_RANGE in outcome.veto_kinds


def test_a_vetoed_patch_does_not_advance_state(revision: Revision) -> None:
    outcome = apply_patch(revision, build_patch(revision, "scene-1", [(0, 10, "A"), (5, 15, "B")]))
    assert outcome.revision is None
    assert outcome.node_after is None


@given(
    start=st.integers(min_value=0, max_value=40),
    length=st.integers(min_value=0, max_value=20),
    replacement=st.text(max_size=30),
)
def test_preservation_holds_for_arbitrary_single_span_edits(
    start: int, length: int, replacement: str
) -> None:
    """Property form of the guarantee: everything outside the cited span survives."""
    revision = make_revision()
    node = revision.node("scene-5")
    assert node.content is not None
    original = node.content
    end = min(start + length, len(original))
    if start > len(original):
        return
    outcome = apply_patch(
        revision,
        build_patch(revision, "scene-5", [(start, end, canonicalize(replacement))],
                    licensed_by="f-license"),
        PatchPolicy(min_length_ratio=0.0, max_length_ratio=100.0),
    )
    assert outcome.accepted, outcome.vetoes
    assert outcome.node_after is not None and outcome.node_after.content is not None
    result = outcome.node_after.content
    assert result.startswith(original[:start])
    assert result.endswith(original[end:])


# --- contracts 1.1 projection ------------------------------------------------------


def test_a_job_round_trips_its_lease_and_payload_through_the_contract() -> None:
    """Lossless as of contracts 1.1.0. Before it, a job crossing this boundary silently
    lost its lease and its input, because JobRecord had nowhere to put either."""
    job = Job(
        job_id="draft-1",
        job_kind="scene_draft",
        lease_holder="worker-a",
        lease_expires_at=1_760_000_600.0,
        payload={"logical_id": "scene-1", "prompt": "Draft it."},
        priority=7,
    )
    record = job.to_contract(meta("job_record", "job-draft-1"))
    assert record.lease_holder == "worker-a"
    assert record.lease_expires_at == 1_760_000_600.0
    assert record.payload == {"logical_id": "scene-1", "prompt": "Draft it."}
    assert record.priority == 7


def test_an_unset_job_field_stays_absent_from_the_wire() -> None:
    """Contracts 1.1 omits None and only None, so an unset addition must be None rather
    than an empty dict or a zero — otherwise every job payload grows two keys."""
    record = Job(job_id="noop-1", job_kind="noop").to_contract(meta("job_record", "job-noop"))
    rendered = lc.to_jsonable(record)
    for absent in ("payload", "priority", "lease_holder", "lease_expires_at"):
        assert absent not in rendered


def test_a_block_node_projects_onto_real_contract_fields_not_metadata() -> None:
    node = Node(
        logical_id="status-1",
        kind=NodeKind.BLOCK,
        position_key="010",
        block_kind=BlockKind.STATUS_WINDOW,
        block_payload={"hp": 24, "level": 3},
        lock=LockKind.PUBLISHED,
    )
    record = node.to_contract("v-1")

    assert record.block_kind is lc.BlockKind.STATUS_WINDOW
    assert record.block_payload == {"hp": 24, "level": 3}
    assert record.lock_kind is lc.LockKind.PUBLISHED
    # `locked` must agree, so a reader that only understands the boolean still sees it.
    assert record.locked is True
    assert Node.from_contract(record) == node


def test_a_node_written_before_1_1_still_reads_from_metadata() -> None:
    """Revisions are immutable and content-addressed, so 1.0-era nodes stay readable
    forever by design. The fallback is not dead code."""
    legacy = lc.ManuscriptNode(
        logical_id="status-1",
        kind=lc.NodeKind.BLOCK,
        position_key="010",
        locked=True,
        metadata={
            "lock_kind": "published",
            "block_kind": "status_window",
            "block_payload": {"hp": 24},
        },
    )
    node = Node.from_contract(legacy)
    assert node.lock is LockKind.PUBLISHED
    assert node.block_kind is BlockKind.STATUS_WINDOW
    assert node.block_payload == {"hp": 24}
