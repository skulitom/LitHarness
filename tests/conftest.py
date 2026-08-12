from __future__ import annotations

import os

import litharness_contracts as lc
import pytest

# Set before anything imports the provider registry. Stage 0's exit criterion requires that
# a test run *provably* cannot reach a paid provider, and a guard the suite only honours in
# the tests that remember to opt in is not a guard. Setting it here makes it structural:
# every test in this package runs with billing providers filtered out of resolution.
os.environ.setdefault("LITHARNESS_ENV", "test")

from litharness.domain.nodes import Node, NodeKind
from litharness.domain.position import initial_keys
from litharness.domain.revision import Revision, build_revision, node_version_id
from litharness.domain.text import content_hash

PROJECT_ID = "11111111-1111-5111-8111-111111111111"
BOOK_ID = "22222222-2222-5222-8222-222222222222"
BRANCH_ID = "33333333-3333-5333-8333-333333333333"

SCENES = [
    "Rook counted the coins twice. Forty-five, and the lantern cost twenty.",
    "The gatekeeper wanted five more. Rook paid without looking up.",
    "Shadowstep took him through the wicket before the hounds turned.",
    "The silver key fit a lock he had never seen.",
    "He let his ribs knit while the System tallied what he had spent.",
    "The debt to Marrow closed at fifteen gold, and the gate stood open.",
]


def meta(kind: str, artifact_id: str) -> lc.ArtifactMeta:
    return lc.ArtifactMeta(
        schema_version="1.0.0",
        artifact_id=artifact_id,
        artifact_kind=kind,
        created_at="2026-08-12T00:00:00Z",
        actor="litharness-tests",
        tool=lc.ToolIdentity(name="litharness", version="0.1.0"),
    )


def make_revision() -> Revision:
    """Build the sample book. A plain function as well as a fixture so property tests
    can construct their own instance instead of sharing a function-scoped fixture."""
    keys = initial_keys(len(SCENES))
    nodes = [Node(logical_id="book", kind=NodeKind.BOOK, position_key="010")]
    nodes += [
        Node.text_node(
            f"scene-{index + 1}", NodeKind.SCENE, keys[index], text, parent_logical_id="book"
        )
        for index, text in enumerate(SCENES)
    ]
    return build_revision(BOOK_ID, BRANCH_ID, nodes)


@pytest.fixture
def revision() -> Revision:
    return make_revision()


def resource_ref(logical_id: str, version_id: str | None = None) -> lc.ResourceRef:
    return lc.ResourceRef(
        project_id=PROJECT_ID,
        book_id=BOOK_ID,
        branch_id=BRANCH_ID,
        logical_id=logical_id,
        kind=lc.ResourceKind.MANUSCRIPT_SCENE,
        version_id=version_id,
    )


def span_for(node: Node, start: int, end: int, version_id: str) -> lc.EvidenceSpan:
    assert node.content is not None
    return lc.EvidenceSpan(
        source=resource_ref(node.logical_id, version_id),
        start=start,
        end=end,
        content_sha256=content_hash(node.content[start:end]),
    )


def build_patch(
    revision: Revision,
    logical_id: str,
    ops: list[tuple[int, int, str | None]],
    *,
    licensed_by: str | None = None,
    kind: lc.PatchOpKind = lc.PatchOpKind.REPLACE_SPAN,
    base_version_id: str | None = None,
    base_content_sha256: str | None = None,
) -> lc.BoundedPatch:
    node = revision.node(logical_id)
    version_id = node_version_id(node)
    return lc.BoundedPatch(
        meta=meta("bounded_patch", f"patch-{logical_id}"),
        target=resource_ref(logical_id, version_id),
        base_version_id=base_version_id or version_id,
        base_content_sha256=base_content_sha256 or (node.content_sha256 or ""),
        ops=[
            lc.PatchOp(
                kind=kind,
                target_span=span_for(node, start, end, version_id),
                new_text=new_text,
            )
            for start, end, new_text in ops
        ],
        idempotency_key=f"idem-{logical_id}-{len(ops)}",
        licensed_by_finding_id=licensed_by,
    )
