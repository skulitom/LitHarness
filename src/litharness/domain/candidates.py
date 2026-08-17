"""Span candidates: the tournament's vocabulary, and the arithmetic that picks a winner.

§61 Add 3 applies selection pressure at the structure level: K alternative beat-plans for
one span, each drafted, the drafts judged pairwise, exactly one committed. This module is
the pure half of that — what a candidate *is*, how the sibling pairs over a tournament are
minted, when the evidence is complete, and which candidate won. Everything here is
arithmetic over values; the provider calls and the store live in
`application/plan_search.py`.

**A candidate is a draft that must never reach `commit_revision`.** §21's invariant (one
draft in flight per book) holds under K-way drafting only because `gate_draft` is pure and
returns an un-persisted Revision — so K candidates are generated and gated off one frozen
base inside one job, and the store's history sees exactly the winner. What persists per
candidate is the text and its plan-alternative provenance, from which the winning Revision
is *rebuilt* deterministically at selection time: re-gating the stored text against the
stored base reproduces the same content-addressed revision id, so nothing needs to store a
revision that was deliberately not committed.

**Candidates-as-corpus is the sibling mechanism, not a new member kind.** Add 1's engine
already serves system-vs-system comparison: `MemberKind.CORPUS_EXCERPT` addresses hash
their own text, `draw_pairs` documents "passing the candidate addresses as `corpus` is the
system-vs-system draw", and `INTERNAL_PROTOCOL` is the built-in frame that exists precisely
because internal K-sibling pairs need one before any operator has typed a frame. So a
candidate's pair-member address is `exc:{excerpt_id_for(text)}` and the tournament's rows
ride the same table, the same digests and the same verdict machinery as every other pair.

**Everything is content-derived, inheriting the engine's discipline.** The candidate id
hashes the text plus its provenance; the tie-break is by candidate id; pair identity and
sample identity come from `preference`'s own derivations. No RNG anywhere means a replayed
tournament converges onto the same rows and "why did this candidate win" stays arithmetic
anyone can repeat.
"""

from __future__ import annotations

import enum
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from litharness.domain.events import payload_digest
from litharness.domain.preference import (
    INTERNAL_PROTOCOL,
    PairSample,
    PairVerdict,
    draw_pairs,
    excerpt_address,
    excerpt_id_for,
    pair_id_for,
    sample_id_for,
)
from litharness.domain.text import canonicalize


class CandidateStatus(enum.StrEnum):
    """Where one candidate stands. Exactly three states, and no path back.

    `CANDIDATE` awaits selection; `SELECTED` is the one winner, committed through the
    normal accept path; `DISCARDED` is a loser or a stale tournament's remnant, kept as a
    record — deleting refused work is how a selection stops being auditable.
    """

    CANDIDATE = "candidate"
    SELECTED = "selected"
    DISCARDED = "discarded"


def candidate_id_for(
    *,
    text: str,
    statement: str,
    alternative_index: int,
    base_revision_id: str,
    job_id: str,
) -> str:
    """Content address of one candidate: the text plus its plan-alternative provenance.

    The provenance is in the hash because the same prose drafted under two different
    alternatives is two different claims about the plan — the statement is what the
    tournament is actually selecting between, and the text is only its evidence. The job id
    is in it so two tournaments over one span (different epochs, therefore different derived
    job ids) cannot collide on a coincidentally identical draft, and a *replayed* tournament
    that reproduces its texts converges onto the same rows.
    """
    material = payload_digest(
        {
            "text": text,
            "statement": statement,
            "alternative_index": alternative_index,
            "base_revision_id": base_revision_id,
            "job_id": job_id,
        }
    )
    return f"cand-{material[:24]}"


@dataclass(frozen=True, slots=True)
class SpanCandidate:
    """One surviving candidate draft of one tournament, awaiting (or past) selection.

    `text` is canonical (the shape `gate_draft` committed to when it built the un-persisted
    Revision), and `__post_init__` refuses a row whose id disagrees with its content —
    incoherence made unrepresentable, the §59 move every derived id in this store makes.
    """

    candidate_id: str
    job_id: str
    book_id: str
    branch_id: str
    logical_id: str
    alternative_index: int
    statement: str
    text: str
    base_revision_id: str
    plan_epoch: int
    created_at: str
    status: CandidateStatus = CandidateStatus.CANDIDATE

    def __post_init__(self) -> None:
        if canonicalize(self.text) != self.text:
            raise ValueError("candidate text is not canonical; store what gate_draft gated")
        if not self.text.strip():
            raise ValueError("an empty candidate is not prose anyone can select")
        if not self.statement.strip():
            raise ValueError("a candidate with no statement is not a plan alternative")
        expected = candidate_id_for(
            text=self.text,
            statement=self.statement,
            alternative_index=self.alternative_index,
            base_revision_id=self.base_revision_id,
            job_id=self.job_id,
        )
        if self.candidate_id != expected:
            raise ValueError(
                f"candidate_id {self.candidate_id} does not address this candidate"
            )

    @property
    def address(self) -> str:
        """The pair-member address of this candidate's text: candidates-as-corpus."""
        return excerpt_address(excerpt_id_for(self.text))


def sibling_samples(
    candidates: Sequence[SpanCandidate], *, sampled_at: str
) -> tuple[PairSample, ...]:
    """All C(K,2) sibling pairs over a tournament, both orientations, rate 1.0.

    Rate 1.0 rather than the audit's default because the tournament is not a sample of a
    stream — every pair *is* the evidence the selection turns on, and drawing a subset
    would leave the human path waiting forever on rows that were never minted.
    `draw_pairs` dedupes on unordered pair identity, so K candidates yield exactly
    K*(K-1)/2 pairs as 2x that many presented sibling rows.
    """
    addressed = [(candidate.address, candidate.book_id) for candidate in candidates]
    return draw_pairs(
        addressed,
        [address for address, _ in addressed],
        INTERNAL_PROTOCOL,
        1.0,
        sampled_at=sampled_at,
    )


def required_sample_ids(candidates: Sequence[SpanCandidate]) -> frozenset[str]:
    """The sample ids a completed tournament must have answers for.

    Derived rather than stored: pair and sample identity are content addresses over the
    candidate texts and `INTERNAL_PROTOCOL`, so the evidence a tournament awaits can be
    recomputed from its candidate rows on any machine — no join table, nothing to drift.
    """
    addresses = sorted({candidate.address for candidate in candidates})
    ids = set()
    for index, one in enumerate(addresses):
        for other in addresses[index + 1 :]:
            pair_id = pair_id_for(one, other)
            for orientation in (0, 1):
                ids.add(
                    sample_id_for(pair_id, orientation, INTERNAL_PROTOCOL.protocol_id)
                )
    return frozenset(ids)


def tournament_samples(
    candidates: Sequence[SpanCandidate], samples: Iterable[PairSample]
) -> tuple[PairSample, ...]:
    """The rows of `samples` that belong to this tournament, in sample-id order.

    Filtered by derived identity rather than by a stored tournament key, so audit rows,
    external-frame pairs and other spans' tournaments can share the table without any of
    them leaking into this selection.
    """
    required = required_sample_ids(candidates)
    return tuple(
        sorted(
            (sample for sample in samples if sample.sample_id in required),
            key=lambda sample: sample.sample_id,
        )
    )


def evidence_complete(
    candidates: Sequence[SpanCandidate], samples: Iterable[PairSample]
) -> bool:
    """Whether every sibling sample of this tournament carries an answered verdict.

    Both orientations of every pair, because the position swap is the §61 design: a
    selection licensed by one presented order would inherit exactly the 43-65% positional
    artifact the swap exists to measure out. A single-candidate tournament has no pairs and
    is vacuously complete — selection there is deterministic.
    """
    required = required_sample_ids(candidates)
    answered = {
        sample.sample_id for sample in samples if sample.verdict is not None
    }
    return required <= answered


def canonical_win_counts(
    candidates: Sequence[SpanCandidate], samples: Iterable[PairSample]
) -> dict[str, int]:
    """Decisive canonical wins per candidate id, over this tournament's answered rows.

    The verdict is re-expressed over the canonical (min, max) presentation through the
    orientation bit — `PairVerdict.canonical` — so both sibling rows of one pair count in
    one frame and a judge's positional bias shows up as disagreement between siblings
    rather than as a silent thumb on the scale. Ties and abstentions count nothing:
    `INTERNAL_PROTOCOL` declares `DROP`, because a tie between two of our own candidates
    selects nothing.
    """
    by_address = {candidate.address: candidate.candidate_id for candidate in candidates}
    counts = {candidate.candidate_id: 0 for candidate in candidates}
    for sample in tournament_samples(candidates, samples):
        verdict = sample.canonical_verdict
        if verdict is None or not verdict.decisive:
            continue
        low, high = sorted((sample.left_addr, sample.right_addr))
        preferred = low if verdict is PairVerdict.PREFER_FIRST else high
        winner = by_address.get(preferred)
        if winner is not None:
            counts[winner] += 1
    return counts


def select_winner(
    candidates: Sequence[SpanCandidate], samples: Iterable[PairSample]
) -> tuple[SpanCandidate, Mapping[str, int]]:
    """The tournament's winner and the counts that chose it. Pure, total, deterministic.

    Highest canonical win count over decisive judgments; ties broken by candidate id
    ascending — content-derived, so the tie-break is a fact about the candidates rather
    than about insertion order or a re-rollable draw. A tournament with no decisive
    judgment at all (every reader tied or abstained) resolves entirely by the tie-break,
    which is stated here because it is the honest reading of "the readers could not
    separate them": some candidate must be committed, and the arbitrary choice is at least
    a *repeatable* arbitrary choice.
    """
    if not candidates:
        raise ValueError("a tournament with no candidates selects nothing")
    counts = canonical_win_counts(candidates, samples)
    ranked = sorted(
        candidates, key=lambda item: (-counts[item.candidate_id], item.candidate_id)
    )
    return ranked[0], counts


__all__ = [
    "CandidateStatus",
    "SpanCandidate",
    "candidate_id_for",
    "canonical_win_counts",
    "evidence_complete",
    "required_sample_ids",
    "select_winner",
    "sibling_samples",
    "tournament_samples",
]
