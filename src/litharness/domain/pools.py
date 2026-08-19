"""The measurement firewall: which readers and which passages may steer, and which may measure.

§61's claim — that the lower bound of a clustered interval on blinded, position-swapped pairwise
win rate against matched published prose exceeds 0.5 — **dies if the prose was shaped by the
readers who later judge it**. Once reader verdicts reach a draft prompt, that is no longer a
hypothetical: it is the default, and it happens silently, because nothing in the pair engine
records what a verdict was *used for*.

So readers and comparison passages are split into a **steering** pool and a **measurement** pool
before the first verdict is routed, and the split is a stored, write-once pre-registration rather
than a convention. `plan/reader-judge-loop.md` §1 is that pre-registration in prose; this module
is the same thing in code.

**The draw is content-derived, never random, inheriting `domain/audit.py`'s discipline verbatim**
— and for the same three reasons, which are worth restating because none of them survives an RNG.
A replayed assignment converges. An operator who dislikes an assignment cannot re-roll it. And
"why is this reader in this pool" is arithmetic anyone can repeat rather than a fact about when
somebody looked.

**What each half of the split actually buys, because they are not equal.** The *reader* split is
the lock: a reader is in exactly one pool for life, so steering verdicts and §61 measurement
verdicts are answered by disjoint sets of people. The *passage* split is a weaker second lock and
saying otherwise would be dishonest — if the loop works at all, every scene of a steered book is
shaped by steering feedback and no passage-level split undoes that. What it buys is narrower and
still worth having: a passage's own reader verdicts never feed back into the prose that passage
is later compared as, and the §61 comparison set is derivable before any verdict exists rather
than by post-hoc exclusion.

**What cannot be enforced, stated here rather than discovered later.** Nothing stops an operator
from giving one physical person two reader ids that land in different pools. The firewall is over
reader *identifiers*. `litharness pools` prints that sentence in its own output, because a
limitation only recorded in a design document is a limitation nobody reads.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from hashlib import sha256

#: Buckets a hash is reduced to. Ten thousand, matching `audit.BUCKETS`, so a share is
#: expressible to one hundredth of a percent and modulo bias against a 256-bit hash is far below
#: any share anyone would set.
BUCKETS = 10_000


class PoolsNotRegistered(Exception):
    """No pre-registration exists, so nothing may be routed.

    Raised rather than defaulted. A default split would be a firewall nobody declared, which is
    exactly the shape §61 pre-registration (4) refuses: the frame *is* the claim, and a frame
    chosen by a constant in a source file was not declared by anyone.
    """


class Pool(enum.StrEnum):
    """Which side of the firewall something is on."""

    STEERING = "steering"
    MEASUREMENT = "measurement"


def registration_id_for(
    *,
    reader_salt: str,
    reader_steering_share: float,
    passage_salt: str,
    passage_steering_share: float,
) -> str:
    """Content address over the split's own parameters.

    So a second registration that differs in any parameter is a *different* row rather than an
    overwrite, and re-registering the identical split is idempotent rather than a conflict —
    the same property every derived id in this store has.
    """
    material = "\x00".join(
        (
            reader_salt,
            f"{reader_steering_share:.6f}",
            passage_salt,
            f"{passage_steering_share:.6f}",
        )
    ).encode()
    return f"pool-{sha256(material).hexdigest()[:24]}"


@dataclass(frozen=True, slots=True)
class PoolRegistration:
    """The split, declared once, before any verdict is routed."""

    registration_id: str
    registered_at: str
    reader_salt: str
    reader_steering_share: float
    passage_salt: str
    passage_steering_share: float
    note: str = ""

    def __post_init__(self) -> None:
        for name, share in (
            ("reader_steering_share", self.reader_steering_share),
            ("passage_steering_share", self.passage_steering_share),
        ):
            # **A share of 0 or 1 is refused, and this is an I7 check rather than fastidiousness.**
            # At 1.0 every reader steers and the measurement pool is empty, so §61 has no readers
            # and the firewall is a table with no effect; at 0.0 the loop can never be fed. Both
            # are declarations that cannot do what they say, which is the failure mode §89's
            # rulebook catalogues seven times.
            if not 0.0 < share < 1.0:
                raise ValueError(
                    f"{name} is {share}; a split with one empty side is not a split — "
                    "at 1.0 §61 has no readers left and at 0.0 nothing can ever steer"
                )
        if not self.reader_salt.strip() or not self.passage_salt.strip():
            raise ValueError("a salt that is blank makes the split guessable and unstated")
        expected = registration_id_for(
            reader_salt=self.reader_salt,
            reader_steering_share=self.reader_steering_share,
            passage_salt=self.passage_salt,
            passage_steering_share=self.passage_steering_share,
        )
        if self.registration_id != expected:
            raise ValueError(
                f"registration_id {self.registration_id} does not address this split"
            )


def _bucket(salt: str, *parts: str) -> int:
    material = "\x00".join((salt, *parts)).encode()
    return int.from_bytes(sha256(material).digest()[:8], "big") % BUCKETS


def reader_pool(reader_id: str, registration: PoolRegistration | None) -> Pool:
    """Which pool this reader answers in, for life.

    Raises when nothing is registered: an unrouted verdict is recoverable, a verdict routed
    under a split nobody declared is not.
    """
    if registration is None:
        raise PoolsNotRegistered(
            "no pool registration; run `litharness pools register` before any verdict is "
            "routed (plan/reader-judge-loop.md §1)"
        )
    steering = _bucket(registration.reader_salt, reader_id) < (
        registration.reader_steering_share * BUCKETS
    )
    return Pool.STEERING if steering else Pool.MEASUREMENT


def passage_pool(
    revision_id: str, logical_id: str, registration: PoolRegistration | None
) -> Pool:
    """Which pool this span is on, for life.

    Keyed on `(revision_id, logical_id)` exactly as `audit.bucket_for` is, so the two draws are
    the same arithmetic over the same material and a reader can check either by hand. For a
    tournament the revision is the frozen base every candidate was drafted against, so all K
    siblings of one span share one pool — a span cannot be half-steering.
    """
    if registration is None:
        raise PoolsNotRegistered(
            "no pool registration; run `litharness pools register` before any pair is drawn "
            "(plan/reader-judge-loop.md §1)"
        )
    steering = _bucket(registration.passage_salt, revision_id, logical_id) < (
        registration.passage_steering_share * BUCKETS
    )
    return Pool.STEERING if steering else Pool.MEASUREMENT


#: The one sentence `litharness pools` prints beneath the split, and the reason it is a constant
#: rather than a line in the command: a residual that lives only in a design document is a
#: residual nobody reads.
RESIDUAL = (
    "The firewall is over reader identifiers. Nothing here can stop one person holding two "
    "reader ids in different pools; that is the operator's discipline, not the code's."
)


__all__ = [
    "BUCKETS",
    "RESIDUAL",
    "Pool",
    "PoolRegistration",
    "PoolsNotRegistered",
    "passage_pool",
    "reader_pool",
    "registration_id_for",
]
