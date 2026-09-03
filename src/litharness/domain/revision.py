"""Immutable revisions: content-addressed snapshots of the manuscript tree.

Four decisions the plan left open, settled here with their reasons.

**Revision ids are content-addressed.** A revision's id is a hash over its book, branch,
parent and full node set. Committing byte-identical content twice therefore yields the
same id and the second commit is a no-op — idempotency comes from the identity scheme
rather than from a dedup table that could drift out of sync with it.

**Node version ids are content-addressed over the node alone, not Merkle-chained through
its ancestors.** This is the "node-version fan-out" question, and the answer matters more
than it looks. Under a Merkle scheme, editing one scene changes its chapter's version id,
its part's, and the book's — so every evidence span citing any ancestor goes stale on
every edit. Under per-node addressing, editing scene 3 changes scene 3's version id and
nothing else, and every span citing scenes 1, 2 and 4-6 stays resolvable. That is what
makes §12's "unchanged text is structurally ineligible for revision" mechanically true
rather than aspirational, and it is why a revision id covers the whole set while node
ids do not.

**Branch forks share nodes; they do not copy them.** Nodes are immutable and
content-addressed, so a fork is a new revision row with a new `branch_id` pointing at the
same node versions. Copy-on-write would double storage and, worse, produce two distinct
version ids for identical text — which would make a span citing one branch silently
unresolvable on the other.

**Lineage is single-parent, and that is a known ceiling.** `litharness-contracts` pins
`parent_revision_id` as a single value, so this model cannot express a merge. §4.7's
branch-merge story needs a contract change before it can be built; nothing here should
pretend otherwise, and `parents` is deliberately not a list.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from hashlib import sha256
from typing import Any

import litharness_contracts as lc

from litharness.domain.nodes import Node, NodeKind
from litharness.domain.position import initial_keys, key_between, parse_key


def _digest(payload: Any) -> str:
    rendered = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return sha256(rendered.encode("utf-8")).hexdigest()


def node_version_id(node: Node) -> str:
    """Content address of one node version.

    Covers every field that distinguishes one version of a node from another, and
    deliberately excludes the node's ancestors — see the module docstring.
    """
    return _digest(
        {
            "logical_id": node.logical_id,
            "kind": node.kind.value,
            "position_key": node.position_key,
            "parent_logical_id": node.parent_logical_id,
            "title": node.title,
            "content_sha256": node.content_sha256,
            "lock": node.lock.value,
            "tombstoned": node.tombstoned,
            "tombstone_reason": node.tombstone_reason,
            "block_kind": node.block_kind.value if node.block_kind else None,
            "block_payload": node.block_payload,
        }
    )


@dataclass(frozen=True, slots=True)
class Revision:
    book_id: str
    branch_id: str
    nodes: tuple[Node, ...]
    parent_revision_id: str | None = None
    revision_id: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        ids = [node.logical_id for node in self.nodes]
        duplicates = sorted({item for item in ids if ids.count(item) > 1})
        if duplicates:
            raise ValueError(f"revision contains duplicate logical ids: {duplicates}")
        known = set(ids)
        for node in self.nodes:
            parent = node.parent_logical_id
            if parent is not None and parent not in known:
                raise ValueError(f"node {node.logical_id} references unknown parent {parent}")
        if not self.revision_id:
            object.__setattr__(self, "revision_id", self._compute_id())

    def _compute_id(self) -> str:
        return _digest(
            {
                "book_id": self.book_id,
                "branch_id": self.branch_id,
                "parent_revision_id": self.parent_revision_id,
                "nodes": sorted((node.logical_id, node_version_id(node)) for node in self.nodes),
            }
        )

    # -- access ---------------------------------------------------------------

    @property
    def version_ids(self) -> dict[str, str]:
        return {node.logical_id: node_version_id(node) for node in self.nodes}

    def node(self, logical_id: str) -> Node:
        for candidate in self.nodes:
            if candidate.logical_id == logical_id:
                return candidate
        raise KeyError(f"no node {logical_id} in revision {self.revision_id[:12]}")

    def reverting_to(self, target: Revision) -> Revision:
        """A new revision restoring ``target``'s node set, parented on ``self``.

        **Reverting goes forward, never backward.** History is immutable and
        content-addressed, so "undo" cannot mean deleting or rewriting a revision — every
        evidence span citing it would become unresolvable, and the audit trail would lose
        the fact that the bad revision ever existed, which is the fact an operator most
        needs afterwards. Instead this produces a *new* revision whose content equals the
        target's, leaving both the mistake and the correction in the record.

        Free in storage: node versions are content addresses inserted with
        `INSERT OR IGNORE`, so restoring old content stores no new node rows.

        Nodes present now but absent from the target are carried forward tombstoned rather
        than dropped, because a revision that dropped a node would make its predecessor
        unreconstructible and break the restore guarantee (§19).
        """
        restored = {node.logical_id: node for node in target.nodes}
        nodes: list[Node] = list(target.nodes)
        for node in self.nodes:
            if node.logical_id not in restored and not node.tombstoned:
                nodes.append(
                    node.tombstone(f"absent from reverted-to revision {target.revision_id[:12]}")
                )
        return Revision(
            book_id=self.book_id,
            branch_id=self.branch_id,
            nodes=tuple(nodes),
            parent_revision_id=self.revision_id,
        )

    def children_of(self, logical_id: str | None) -> list[Node]:
        """Live children in position order. Tombstoned nodes are excluded."""
        children = [
            node
            for node in self.nodes
            if node.parent_logical_id == logical_id and not node.tombstoned
        ]
        children.sort(key=lambda node: (parse_key(node.position_key), node.logical_id))
        return children

    def in_reading_order(self) -> list[Node]:
        """Depth-first traversal from the roots, position-ordered, live nodes only."""
        ordered: list[Node] = []

        def walk(parent: str | None) -> None:
            for child in self.children_of(parent):
                ordered.append(child)
                walk(child.logical_id)

        walk(None)
        return ordered

    def rendered_text(self) -> str:
        return "\n\n".join(
            node.content for node in self.in_reading_order() if node.content is not None
        )

    # -- evolution ------------------------------------------------------------

    def replacing(self, nodes: Iterable[Node]) -> Revision:
        """A child revision with ``nodes`` substituted by logical id.

        Unchanged nodes are carried through by reference, so their version ids — and
        therefore every evidence span citing them — survive.
        """
        overrides = {node.logical_id: node for node in nodes}
        unknown = sorted(set(overrides) - {node.logical_id for node in self.nodes})
        if unknown:
            raise ValueError(f"cannot replace nodes absent from the revision: {unknown}")
        return Revision(
            book_id=self.book_id,
            branch_id=self.branch_id,
            nodes=tuple(overrides.get(node.logical_id, node) for node in self.nodes),
            parent_revision_id=self.revision_id,
        )

    def forked_to(self, branch_id: str) -> Revision:
        """A revision on a new branch sharing this one's node versions."""
        return Revision(
            book_id=self.book_id,
            branch_id=branch_id,
            nodes=self.nodes,
            parent_revision_id=self.revision_id,
        )

    # -- contract projection --------------------------------------------------

    def to_contract(self, meta: lc.ArtifactMeta) -> lc.ManuscriptRevision:
        versions = self.version_ids
        return lc.ManuscriptRevision(
            meta=meta,
            book_id=self.book_id,
            branch_id=self.branch_id,
            revision_id=self.revision_id,
            nodes=[node.to_contract(versions[node.logical_id]) for node in self.nodes],
            parent_revision_id=self.parent_revision_id,
        )

    @classmethod
    def from_contract(cls, revision: lc.ManuscriptRevision) -> Revision:
        restored = cls(
            book_id=revision.book_id,
            branch_id=revision.branch_id,
            nodes=tuple(Node.from_contract(node) for node in revision.nodes),
            parent_revision_id=revision.parent_revision_id,
        )
        if restored.revision_id != revision.revision_id:
            raise ValueError(
                "restored revision id does not match the serialized one: "
                f"{restored.revision_id[:12]} != {revision.revision_id[:12]}"
            )
        return restored


@dataclass(frozen=True, slots=True)
class ImportedManuscript:
    """A foreign manuscript rebuilt as a local revision, with what changed named."""

    revision: Revision
    #: The id the source artifact carried. Kept because it is the only link back to where
    #: this book came from, and it is *not* the local revision id — see `import_manuscript`.
    source_revision_id: str
    #: Scenes whose prose was cleared so a draft job can fill them.
    cleared: tuple[str, ...] = ()
    #: Scenes whose prose was *not* cleared because a content lock forbids it. Reported
    #: rather than silently skipped: these are the nodes the importer could not make
    #: draftable, and an operator who does not know that sees an import that "worked" and a
    #: book with fewer draftable scenes than it has scenes.
    kept_locked: tuple[str, ...] = ()


def import_manuscript(
    source: lc.ManuscriptRevision, *, preserve_content: bool = False
) -> ImportedManuscript:
    """Adopt a manuscript authored elsewhere as a root revision of this store.

    **Why this is not `from_contract`.** That classmethod asserts the rebuilt id equals the
    serialized one, which is the round-trip guarantee of a content-addressed store: an
    artifact *this* system wrote must rebuild to the same address, and a mismatch means
    corruption. A foreign artifact fails that assertion for a reason that is not corruption
    at all — `litharness-contracts` mints revision ids as UUID5 while this package computes
    a sha256 over content, so every contracts-authored manuscript mismatches by
    construction. Relaxing the assertion to admit them would delete the corruption check for
    the artifacts it exists to protect. So the id is *rebuilt* here and the source id is
    carried as provenance instead. The per-node `content_sha256` check in
    `Node.from_contract` is untouched and does the real integrity work — it is what catches
    a manuscript decoded with the wrong codec.

    **Only a root can be imported.** A source carrying a `parent_revision_id` names an
    ancestor that is not in this store, and `lineage` walks parents until it reaches one:
    importing it would produce a revision that breaks `verify` the first time anyone asked
    for its history. Refused rather than silently re-parented.

    **Scene prose is cleared unless `preserve_content`.** `gate_draft` refuses any node that
    already carries content, so a manuscript imported with its prose intact is a book with
    zero draftable scenes — it looks like a book and can do nothing. Clearing is what "the
    fixture books regenerate from premise" (§17 Stage 1) means mechanically. Nothing is
    lost: the source artifact is untouched on disk and its id is recorded. Only `SCENE`
    nodes are cleared, because a scene is the unit a `scene_draft` job fills; titles and
    structure are the frame the generation happens inside, not output to be reproduced.
    """
    if source.parent_revision_id is not None:
        raise ValueError(
            f"cannot import revision {source.revision_id[:12]}: it is parented on "
            f"{source.parent_revision_id[:12]}, which is not in this store, and a revision "
            "whose lineage is broken fails verification"
        )

    nodes: list[Node] = []
    cleared: list[str] = []
    kept_locked: list[str] = []
    for contract_node in source.nodes:
        node = Node.from_contract(contract_node)
        if not preserve_content and node.kind is NodeKind.SCENE and node.content is not None:
            # `replace` bypasses `with_content`'s lock check, so the lock is honoured here
            # explicitly. A silent bypass would make a content lock mean nothing on the one
            # path that erases content wholesale.
            if node.lock.freezes_content:
                kept_locked.append(node.logical_id)
            else:
                node = replace(node, content=None, content_sha256=None)
                cleared.append(node.logical_id)
        nodes.append(node)

    return ImportedManuscript(
        revision=Revision(
            book_id=source.book_id,
            branch_id=source.branch_id,
            nodes=tuple(nodes),
            parent_revision_id=None,
        ),
        source_revision_id=source.revision_id,
        cleared=tuple(cleared),
        kept_locked=tuple(kept_locked),
    )


def build_revision(
    book_id: str, branch_id: str, nodes: Iterable[Node], parent: str | None = None
) -> Revision:
    return Revision(
        book_id=book_id, branch_id=branch_id, nodes=tuple(nodes), parent_revision_id=parent
    )


def new_book(
    book_id: str,
    branch_id: str,
    *,
    title: str,
    scenes: int,
    position_capacity: int | None = None,
) -> Revision:
    """An empty book of `scenes` draftable scenes — the entry point Stage 3 needs.

    **Every revision in this system came from `import`, and `import` needs a manuscript
    file.** So a book could only exist if someone had already written one, which is the wall
    Book Zero meets before its first tick: §17 Stage 3 wants 50-80k words produced from a
    premise, and there was no way to make a book with more than the six scenes a fixture
    happens to carry.

    Nodes are empty rather than absent, because that is what "draftable" means here:
    `gate_draft` refuses to overwrite content and fills only an empty node, so a scene the
    planner can work on is one that exists and says nothing. Position keys come from
    `initial_keys`, which leaves gap-10 room to insert between them later — a capability
    nothing uses yet and the one this book's structure would need first.
    """
    if scenes < 1:
        raise ValueError(f"a book needs at least one scene; asked for {scenes}")
    capacity = max(scenes, position_capacity or scenes)
    keys = initial_keys(capacity)[:scenes]
    nodes = [Node(logical_id="book", kind=NodeKind.BOOK, position_key="010", title=title)]
    nodes += [
        Node(
            logical_id=f"scene-{index + 1}",
            kind=NodeKind.SCENE,
            position_key=keys[index],
            parent_logical_id="book",
            title=f"Scene {index + 1}",
        )
        for index in range(scenes)
    ]
    return build_revision(book_id, branch_id, nodes)


def append_scenes(revision: Revision, count: int) -> Revision:
    """Append empty serial scenes without moving any existing story address.

    Tail growth that would rebalance position keys is refused: moving accepted nodes would
    invalidate evidence spans and scheduled state behind the extension. Books created by the
    production CLI reserve ample key width up front, so ordinary endless growth stays cheap.
    """
    if count < 1:
        raise ValueError(f"an extension needs at least one scene; asked for {count}")
    roots = [node for node in revision.children_of(None) if node.kind is NodeKind.BOOK]
    if len(roots) != 1:
        raise ValueError(f"serial extension needs one book root; found {len(roots)}")
    parent = roots[0]
    children = revision.children_of(parent.logical_id)
    sibling_keys = [node.position_key for node in children]
    before = sibling_keys[-1] if sibling_keys else None
    existing_ids = {node.logical_id for node in revision.nodes}
    numeric = [
        int(node.logical_id.removeprefix("scene-"))
        for node in revision.nodes
        if node.logical_id.startswith("scene-") and node.logical_id.removeprefix("scene-").isdigit()
    ]
    scene_count = sum(1 for node in revision.nodes if node.kind is NodeKind.SCENE)
    next_number = max(numeric, default=scene_count) + 1
    added: list[Node] = []
    for _ in range(count):
        insertion = key_between(before, None, sibling_keys)
        if insertion.is_rebalance:
            raise ValueError(
                "the manuscript's position-key capacity is exhausted; extending would move "
                "existing scene addresses and invalidate evidence, so this revision is refused"
            )
        while f"scene-{next_number}" in existing_ids:
            next_number += 1
        logical_id = f"scene-{next_number}"
        node = Node(
            logical_id=logical_id,
            kind=NodeKind.SCENE,
            position_key=insertion.key,
            parent_logical_id=parent.logical_id,
            title=f"Scene {next_number}",
        )
        added.append(node)
        existing_ids.add(logical_id)
        sibling_keys.append(insertion.key)
        before = insertion.key
        next_number += 1
    return Revision(
        book_id=revision.book_id,
        branch_id=revision.branch_id,
        nodes=(*revision.nodes, *added),
        parent_revision_id=revision.revision_id,
    )
