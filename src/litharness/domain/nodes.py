"""The manuscript IR: a typed ordered tree of immutable node versions.

Mirrors `litharness_contracts.ManuscriptNode` and projects onto it losslessly, with two
additions carried in the contract's `metadata` dict rather than as new schema fields.
That is deliberate sequencing: PLAN.md §20.3 wants these promoted to real 1.x members,
and shaping a wire format before a consumer exists is how you ship a field nobody can
use. They live in `metadata` until this module has proven what they need to hold.

**Addition 1: a lock taxonomy, not a boolean.** The contract carries `locked: bool`,
which cannot distinguish "the director vetoed this sentence" from "this chapter is
published and a retcon needs an erratum policy" (§16). Four kinds:

* `NONE` — ordinary text, freely revisable within a licensed complaint.
* `CONTENT` — text frozen; structure (children, ordering) may still change.
* `STRUCTURE` — children and their order frozen; text may still change.
* `PUBLISHED` — highest preservation. Both frozen, and a change requires an explicit
  publication-policy decision rather than an ordinary patch.

`locked` projects as `kind is not NONE`, so a contracts consumer that only understands
the boolean still sees every lock.

**Addition 2: structured block payloads.** §11 requires game-system displays (status
windows, level-up notices, quest text) to be data rather than decoration, so a `BLOCK`
node carries both a `block_kind` and a machine payload alongside its rendered text.
`NodeKind.BLOCK` exists in the contract with no payload field; neither golden fixture
contains a single block node, so this module is the first thing to say what one is.

**Tombstones, not deletion.** Removing a node sets `tombstoned` with a reason. Nothing
is ever physically deleted, because a revision that dropped a node would make its
predecessor unreconstructible and break the restore guarantee (§19).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field, replace
from typing import Any

import litharness_contracts as lc

from litharness.domain.text import canonicalize, content_hash


class NodeKind(enum.StrEnum):
    BOOK = "book"
    PART = "part"
    CHAPTER = "chapter"
    SCENE = "scene"
    BLOCK = "block"

    def to_contract(self) -> lc.NodeKind:
        return lc.NodeKind(self.value)


class LockKind(enum.StrEnum):
    NONE = "none"
    CONTENT = "content"
    STRUCTURE = "structure"
    PUBLISHED = "published"

    @property
    def freezes_content(self) -> bool:
        return self in {LockKind.CONTENT, LockKind.PUBLISHED}

    @property
    def freezes_structure(self) -> bool:
        return self in {LockKind.STRUCTURE, LockKind.PUBLISHED}


class BlockKind(enum.StrEnum):
    """Game-system display kinds. `PROSE` is the escape hatch for a non-system block."""

    PROSE = "prose"
    STATUS_WINDOW = "status_window"
    LEVEL_UP = "level_up"
    QUEST_LOG = "quest_log"
    SYSTEM_MESSAGE = "system_message"


@dataclass(frozen=True, slots=True)
class Node:
    """One immutable node version.

    ``content`` is always canonical (see `domain.text`) and ``content_sha256`` is always
    its hash — enforced in `__post_init__` rather than trusted, because a node whose
    hash does not match its text makes every span citing it unresolvable.
    """

    logical_id: str
    kind: NodeKind
    position_key: str
    parent_logical_id: str | None = None
    title: str | None = None
    content: str | None = None
    content_sha256: str | None = None
    lock: LockKind = LockKind.NONE
    tombstoned: bool = False
    tombstone_reason: str | None = None
    block_kind: BlockKind | None = None
    block_payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.content is not None:
            if not canonicalize(self.content) == self.content:
                raise ValueError(
                    f"node {self.logical_id} content is not canonical; "
                    "call domain.text.canonicalize before constructing"
                )
            expected = content_hash(self.content)
            if self.content_sha256 is None:
                object.__setattr__(self, "content_sha256", expected)
            elif self.content_sha256 != expected:
                raise ValueError(
                    f"node {self.logical_id} content_sha256 does not match its content"
                )
        elif self.content_sha256 is not None:
            raise ValueError(f"node {self.logical_id} has a hash but no content")

        if self.kind is NodeKind.BLOCK and self.block_kind is None:
            object.__setattr__(self, "block_kind", BlockKind.PROSE)
        if self.kind is not NodeKind.BLOCK and self.block_kind is not None:
            raise ValueError(f"node {self.logical_id} is not a block but carries a block_kind")
        if self.tombstoned and not self.tombstone_reason:
            raise ValueError(f"node {self.logical_id} is tombstoned without a reason")

    @classmethod
    def text_node(
        cls, logical_id: str, kind: NodeKind, position_key: str, content: str, **kwargs: Any
    ) -> Node:
        """Construct from possibly non-canonical text, canonicalizing on the way in."""
        return cls(
            logical_id=logical_id,
            kind=kind,
            position_key=position_key,
            content=canonicalize(content),
            **kwargs,
        )

    def with_content(self, content: str) -> Node:
        """A new version of this node carrying ``content``. Rejects a content lock."""
        if self.lock.freezes_content:
            raise LockViolation(
                f"node {self.logical_id} is {self.lock.value}-locked and its content is frozen"
            )
        canonical = canonicalize(content)
        return replace(self, content=canonical, content_sha256=content_hash(canonical))

    def tombstone(self, reason: str) -> Node:
        if self.lock.freezes_structure:
            raise LockViolation(
                f"node {self.logical_id} is {self.lock.value}-locked and cannot be removed"
            )
        return replace(self, tombstoned=True, tombstone_reason=reason)

    def to_contract(self, version_id: str) -> lc.ManuscriptNode:
        """Project onto the contract using the real 1.1 fields.

        These five rode in `metadata` until contracts 1.1.0 gave them homes — deliberate
        sequencing, so the wire shape was proven by this consumer before being frozen
        upstream. `locked` stays populated alongside `lock_kind` because a reader that only
        understands the boolean must still see every lock.
        """
        return lc.ManuscriptNode(
            logical_id=self.logical_id,
            kind=self.kind.to_contract(),
            position_key=self.position_key,
            parent_logical_id=self.parent_logical_id,
            title=self.title,
            content=self.content,
            content_sha256=self.content_sha256,
            version_id=version_id,
            locked=self.lock is not LockKind.NONE,
            lock_kind=lc.LockKind(self.lock.value),
            block_kind=lc.BlockKind(self.block_kind.value) if self.block_kind else None,
            block_payload=dict(self.block_payload) if self.block_kind else None,
            tombstoned=True if self.tombstoned else None,
            tombstone_reason=self.tombstone_reason,
        )

    @classmethod
    def from_contract(cls, node: lc.ManuscriptNode) -> Node:
        """Read the 1.1 fields, falling back to `metadata` for artifacts written before
        they existed. The fallback is not dead code: revisions are immutable and content
        addressed, so 1.0-era nodes stay readable forever by design."""
        metadata = dict(node.metadata or {})
        raw_lock = node.lock_kind.value if node.lock_kind else metadata.get("lock_kind")
        lock = LockKind(raw_lock or ("content" if node.locked else "none"))
        raw_block = node.block_kind.value if node.block_kind else metadata.get("block_kind")
        payload = node.block_payload
        if payload is None:
            payload = metadata.get("block_payload", {})
        tombstoned = node.tombstoned
        if tombstoned is None:
            tombstoned = bool(metadata.get("tombstoned", False))
        return cls(
            logical_id=node.logical_id,
            kind=NodeKind(node.kind.value),
            position_key=node.position_key,
            parent_logical_id=node.parent_logical_id,
            title=node.title,
            content=node.content,
            content_sha256=node.content_sha256,
            lock=lock,
            tombstoned=bool(tombstoned),
            tombstone_reason=node.tombstone_reason or metadata.get("tombstone_reason"),
            block_kind=BlockKind(raw_block) if raw_block is not None else None,
            block_payload=dict(payload),
        )


class LockViolation(Exception):
    """A change was attempted against a lock. Never downgraded to a warning."""
