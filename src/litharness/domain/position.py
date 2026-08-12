"""Position keys: sortable sibling ordering that survives insertion without renumbering.

`litharness-contracts` pins `position_key` as a **string** and both golden fixtures
demonstrate zero-padded gap-10 keys (`"010"`, `"020"` ... `"060"`), so that format is a
compatibility requirement rather than a choice. What contracts does not pin — and what
this module decides — is how keys are allocated and what happens when a gap runs out.

**Gap-10 allocation, lexicographic comparison, fixed width.** Keys are compared as
strings, so every key in a sibling set must be the same width or `"100" < "20"` and the
order silently corrupts. Width is therefore a property of the sibling set, and inserting
a key that needs more digits widens the whole set (a rebalance).

**Insertion between neighbours takes the midpoint; a rebalance happens only when there
is no integer midpoint.** With gap 10 there are nine free slots between consecutive
keys, so the common case never rebalances. When it does, all siblings are renumbered to
fresh gap-10 keys at whatever width the new count needs.

**A rebalance is a visible, ordered event, not a silent fixup.** Renumbering changes
every sibling's `position_key`, and position keys appear in revisions, so callers need
to know it happened — `rebalance` returns the full mapping rather than mutating in
place.
"""

from __future__ import annotations

from dataclasses import dataclass

GAP = 10
MIN_WIDTH = 3


def _width_for(count: int) -> int:
    """Digits needed to hold ``count`` gap-10 keys, never below the fixture's 3."""
    highest = max(count, 1) * GAP
    return max(MIN_WIDTH, len(str(highest)))


def format_key(value: int, width: int = MIN_WIDTH) -> str:
    if value < 0:
        raise ValueError(f"position value must be non-negative, got {value}")
    return str(value).zfill(width)


def parse_key(key: str) -> int:
    if not key.isdigit():
        raise ValueError(f"position key must be all digits, got {key!r}")
    return int(key)


def initial_keys(count: int) -> list[str]:
    """Fresh gap-10 keys for ``count`` siblings, uniform width."""
    width = _width_for(count)
    return [format_key((index + 1) * GAP, width) for index in range(count)]


@dataclass(frozen=True, slots=True)
class Insertion:
    """The outcome of asking for a key between two siblings.

    ``rebalanced`` maps every sibling's old key to its new key when the insertion could
    not be satisfied in the existing key space. It is empty on the common path.
    """

    key: str
    rebalanced: dict[str, str]

    @property
    def is_rebalance(self) -> bool:
        return bool(self.rebalanced)


def key_between(before: str | None, after: str | None, siblings: list[str]) -> Insertion:
    """Allocate a key ordering strictly between ``before`` and ``after``.

    ``None`` means "no neighbour on that side" — i.e. insert at the head or the tail.
    ``siblings`` is the current ordered key set, used only if a rebalance is required.
    """
    ordered = sorted(siblings)
    width = max((len(key) for key in ordered), default=MIN_WIDTH)

    low = parse_key(before) if before is not None else 0
    high = parse_key(after) if after is not None else low + 2 * GAP
    if low >= high:
        raise ValueError(f"cannot insert between {before!r} and {after!r}: not in order")

    midpoint = (low + high) // 2
    if midpoint != low:
        candidate = format_key(midpoint, width)
        # Widening past the sibling width would break lexicographic comparison.
        if len(candidate) == width:
            return Insertion(candidate, {})

    # No room, or the key would not fit the sibling width: renumber the whole set and
    # place the new node in the requested slot.
    target_index = len([key for key in ordered if parse_key(key) <= low])
    with_hole = [*ordered[:target_index], None, *ordered[target_index:]]
    fresh = initial_keys(len(with_hole))
    mapping = {old: new for old, new in zip(with_hole, fresh, strict=True) if old is not None}
    return Insertion(fresh[target_index], mapping)
