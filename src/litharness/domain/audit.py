"""§10.5's standing audit: the only thing in this system that asks a human about the prose.

"Even at full autonomy, the policy engine routes a sample (e.g. 5% of accepted chapters) to
the digest for human spot-reading; audit disagreement re-opens calibration."

**Why this is the highest-leverage part of the craft programme, measured rather than
asserted.** §1a.4 states that human judgment is the only ground truth for §1a.3's six items.
The instrument for collecting it exists — RevisionJudge — and holds 104 exported pairs against
*two* collected verdicts, at roughly 57 seconds of attention each. Judgment is not scarce
because it is slow; it is scarce because nothing asks for it as a by-product of normal
operation, so collecting any requires a human to decide to sit down. A system drafting a book
around the clock and never surfacing a page of it is a system whose quality evidence will
always be a special project.

So the sampler is deliberately unglamorous: a fixed share of accepted scenes, drawn without
randomness, queued forever until someone answers.

**The draw is derived from content, never random, and this is the load-bearing decision.**
Three things follow from it and none would survive an RNG:

- A replayed tick converges. Every derived id in this store — revisions, jobs, decisions,
  findings — is content-addressed for this reason, and a sampler that re-rolled on replay
  would be the one component whose second run disagreed with its first.
- The sample cannot be re-rolled. An operator who does not like what came up cannot re-run to
  get a kinder draw, because the draw is a fact about the revision and the node rather than
  about when anyone looked.
- It is auditable after the fact. `bucket` and `rate` are stored, so "why was this scene
  chosen" is arithmetic anyone can repeat, which is what makes a 5% claim checkable rather
  than a number in a config file.

**Sampling is on acceptance, not on generation.** A refused candidate is not prose the book
contains, and asking a human to read one spends the scarcest input in the project on text
that has already been rejected by a cheaper mechanism.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from hashlib import sha256

#: §10.5's own example, and a default rather than a recommendation — nothing here has measured
#: what rate produces enough judgment to calibrate on without exhausting the reader. At six
#: scenes per fixture book it draws roughly one scene every three books, which is honest about
#: how little a small run yields and is the reason `--audit-rate` exists.
DEFAULT_RATE = 0.05

#: Buckets the hash is reduced to. Ten thousand, so a rate is expressible to one hundredth of
#: a percent and the modulo bias against a 256-bit hash is far below any rate anyone would set.
BUCKETS = 10_000


class Verdict(enum.StrEnum):
    """What a human says after reading one sampled scene.

    Deliberately coarse. §1a.5's bar is "a majority of sampled chapters earn *I would keep
    reading* from readers not told what produced them", so the primary axis is exactly that
    question and not a rubric — a five-dimension scoring form collects less judgment per
    minute and produces numbers whose agreement nobody has measured.

    `NOT_SURE` is a real answer and abstention is recorded rather than coerced: §10.4 asks for
    abstention to be measured, and a scale with no way to decline pushes a reader into a
    verdict they do not hold, which is the fastest way to calibrate against noise.
    """

    KEEP_READING = "keep_reading"
    WOULD_STOP = "would_stop"
    NOT_SURE = "not_sure"

    @property
    def is_negative(self) -> bool:
        return self is Verdict.WOULD_STOP


@dataclass(frozen=True, slots=True)
class AuditSample:
    """One scene drawn for human reading, and the answer when it arrives."""

    sample_id: str
    book_id: str
    branch_id: str
    revision_id: str
    logical_id: str
    sampled_at: str
    rate: float
    bucket: int
    verdict: Verdict | None = None
    note: str | None = None
    judged_at: str | None = None
    judged_by: str | None = None

    @property
    def pending(self) -> bool:
        return self.verdict is None


def bucket_for(revision_id: str, logical_id: str) -> int:
    """Which of `BUCKETS` this (revision, node) falls in. Pure and stable forever."""
    material = f"{revision_id}\x00{logical_id}".encode()
    return int.from_bytes(sha256(material).digest()[:8], "big") % BUCKETS


def sample_id_for(revision_id: str, logical_id: str) -> str:
    material = f"{revision_id}\x00{logical_id}".encode()
    return f"aud-{sha256(material).hexdigest()[:24]}"


def should_audit(revision_id: str, logical_id: str, rate: float = DEFAULT_RATE) -> bool:
    """Whether this accepted scene is drawn for human reading.

    A rate of 0 draws nothing and 1 draws everything, both without a special case — useful,
    because "audit everything" is what a director does for the first chapter of a new book and
    "audit nothing" is what a throwaway test run wants.
    """
    if rate <= 0.0:
        return False
    if rate >= 1.0:
        return True
    return bucket_for(revision_id, logical_id) < rate * BUCKETS


def draw(
    *,
    book_id: str,
    branch_id: str,
    revision_id: str,
    logical_id: str,
    sampled_at: str,
    rate: float = DEFAULT_RATE,
) -> AuditSample | None:
    """The sample for this acceptance, or None if it was not drawn."""
    if not should_audit(revision_id, logical_id, rate):
        return None
    return AuditSample(
        sample_id=sample_id_for(revision_id, logical_id),
        book_id=book_id,
        branch_id=branch_id,
        revision_id=revision_id,
        logical_id=logical_id,
        sampled_at=sampled_at,
        rate=rate,
        bucket=bucket_for(revision_id, logical_id),
    )


__all__ = [
    "BUCKETS",
    "DEFAULT_RATE",
    "AuditSample",
    "Verdict",
    "bucket_for",
    "draw",
    "sample_id_for",
    "should_audit",
]
