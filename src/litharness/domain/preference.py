"""§61's pairwise preference engine: the evidence source that makes superiority falsifiable.

"Superhuman" means the lower bound of a 95% confidence interval on blinded, position-swapped
pairwise win rate against matched published-human prose exceeds 0.5, judged by paid genre
readers (§61, PLAN §1a.5). Four evidence channels were tried and measured dead — unpaid
solicited judgment at two verdicts per 104 exported pairs, revealed labels on their own
controls, raw model judges at a 43-65% positional artifact, CDG to its own pre-registered
memorisation sham — and paid pairwise judgment is the one channel with no refutation against
it, because it is the one this project never funded. This module is that channel's spine:
what a pair *is*, how one is drawn, what a verdict means, and the clustered bound the
headline claim turns on.

**Everything here is derived from content, and that is the load-bearing inheritance.** The
audit queue was demoted (§67) and its draw was not: content-derived, replay-convergent,
non-re-rollable, auditable after the fact. An RNG anywhere in pair selection, position
assignment or ordering would break the convergence property every derived id in the store
shares — a replayed draw would mint different pairs, an operator could re-roll a queue they
did not like, and "why was this pair drawn" would stop being arithmetic anyone can repeat.
So pair identity hashes the unordered members, presentation order is the orientation bit and
nothing else, and even the bootstrap below seeds itself from the verdict set it resamples.

**Five pre-registrations (§61), and where each lands in code.** (1) The interval is
clustered over both readers and pairs — `win_rate_lower_bound` resamples the two dimensions
independently and refuses fewer than two clusters of either. (2) The tie policy is declared
before the first judgment — it is a field of `PreferenceProtocol`, which must be stored
before a pair may be drawn. (3) A judgment where the reader recognises either passage is
excluded from analysis — `recognized` is stored on the judgment row and `system_outcome`
returns nothing for it; the row itself is never dropped, because §58 measured familiarity
swinging a score several times harder than real damage and the exclusion count is itself a
finding. (4) The comparator sampling frame is declared before the first reader is paid —
`comparator_frame` is required prose on the protocol, and the protocol id is derived from
it: the frame *is* the claim. (5) The family correction over candidate books is the
caller's declared division of `alpha`, exposed as a parameter for the same reason
`selection_family_size` divides `PROMOTION_ALPHA` — a level is honest only at the family it
was earned against.

**Preference evidence licenses selection, never refusal.** The production loop runs with
zero verdicts; preference evidence gates promotions and future selection between candidates
(§61 Add 3), and `EvidenceClass.PREFERENCE` deliberately has no `veto_for` mapping — the
total-raise there refuses a blocking gate for it with zero code, which is the decided side,
not an omission.
"""

from __future__ import annotations

import enum
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from random import Random

# §67: the demoted audit queue's remaining job is to keep this sampling discipline alive.
# Sharing the bucket count keeps "a rate of 0.05" meaning the same thing in both draws.
from litharness.domain.audit import BUCKETS
from litharness.domain.calibration import verdicts_digest_for
from litharness.domain.events import payload_digest
from litharness.domain.text import canonicalize, content_hash

#: Bootstrap resamples behind `win_rate_lower_bound`. Fixed here rather than parameterised
#: because the resample count is part of what the pinned reference values in the tests mean:
#: a caller-supplied count would make the same verdict set produce a different bound in two
#: places while both cite the same evidence.
BOOTSTRAP_RESAMPLES = 2000

#: Cluster count per dimension below which the operator surface flags the bound as
#: descriptive rather than calibrated. A percentile cluster bootstrap earns its level only
#: as clusters grow; measured at the floor: two readers by two pairs, all wins — every
#: resample rates 1.0 and the "97.5% lower bound" prints 1.0 from four observations, an
#: interval with no width. Five is a flag threshold, not a refusal: the two-cluster
#: refusal in `win_rate_lower_bound` guards coherence, the promotion floors guard
#: decisions, and this constant names the stretch in between so the number cannot be
#: over-read in silence.
DESCRIPTIVE_CLUSTER_FLOOR = 5

#: The reader component of a `sample_id` minted before any reader is assigned. The draw does
#: not know who will answer — the operator queue is first-come — so drawn rows derive their
#: identity with this sentinel and `record_pair_verdict` stamps whoever answered onto the
#: row. A *pre-assigned* per-reader row (the paid-panel shape, where the same pair goes to
#: several readers) passes a real reader id instead and gets its own row per reader, which
#: is what makes "each (pair, orientation, protocol, reader) is one judgment" expressible.
UNASSIGNED_READER = ""

#: Reader-id prefix reserved for rows a *machine* wrote. The §72 judge path records its
#: verdicts through this same pair table — same draw, same write-once discipline, the
#: licensing calibration id as provenance — and that sharing is deliberate: a judged
#: tournament is real selection evidence and belongs on the record beside the human rows it
#: imitates. What it must never be is *countable* as a human's judgment, and nothing marked
#: the difference before this prefix: `reader_id` was free text, and every consumer read the
#: verdict, the recognition flag and the abstention, never the author.
MACHINE_READER_PREFIX = "judge:"


def machine_reader_id(calibration_id: str) -> str:
    """The reader id a machine-written pair verdict is stamped with.

    The mint and the test (`is_machine_reader`) are named together, beside the prefix they
    share, because the mint is where the discipline actually lives: a machine row that
    forgets the prefix is indistinguishable from a person's, and no check downstream can
    recover an author the row never recorded.
    """
    return f"{MACHINE_READER_PREFIX}{calibration_id}"


def is_machine_reader(reader_id: str | None) -> bool:
    """Whether this row was written by a machine rather than answered by a person.

    `None` and `UNASSIGNED_READER` are both false: a drawn row awaiting a reader is a
    human row that has not been answered yet, not a machine one.
    """
    return (reader_id or "").startswith(MACHINE_READER_PREFIX)


class MemberKind(enum.StrEnum):
    """What one side of a pair is. The values are the address prefixes.

    Polymorphic on purpose: the superiority claim compares our prose against matched
    published-human excerpts, and the future selection judge (§61 Add 3) compares our prose
    against our prose. One address vocabulary serves both, so pair identity never depends on
    which comparison a protocol happens to make.
    """

    REVISION_NODE = "rev"
    CORPUS_EXCERPT = "exc"


@dataclass(frozen=True, slots=True)
class Member:
    """One side of a pair, parsed from or rendered to its address string.

    `rev:{revision_id}:{logical_id}` pins prose exactly: revision ids are content-addressed,
    so the address names the text a reader judged forever, not whatever the node holds now.
    `exc:{excerpt_id}` does the same for corpus excerpts, whose ids hash their own text.
    """

    kind: MemberKind
    revision_id: str | None = None
    logical_id: str | None = None
    excerpt_id: str | None = None

    def __post_init__(self) -> None:
        if self.kind is MemberKind.REVISION_NODE:
            if not self.revision_id or not self.logical_id or self.excerpt_id is not None:
                raise ValueError("a revision member is exactly a (revision_id, logical_id)")
        elif not self.excerpt_id or self.revision_id is not None or self.logical_id is not None:
            raise ValueError("an excerpt member is exactly an excerpt_id")

    @property
    def address(self) -> str:
        if self.kind is MemberKind.REVISION_NODE:
            return f"{MemberKind.REVISION_NODE.value}:{self.revision_id}:{self.logical_id}"
        return f"{MemberKind.CORPUS_EXCERPT.value}:{self.excerpt_id}"

    @classmethod
    def parse(cls, address: str) -> Member:
        prefix, _, rest = address.partition(":")
        if prefix == MemberKind.REVISION_NODE.value:
            revision_id, separator, logical_id = rest.partition(":")
            if revision_id and separator and logical_id:
                return cls(
                    kind=MemberKind.REVISION_NODE,
                    revision_id=revision_id,
                    logical_id=logical_id,
                )
        if prefix == MemberKind.CORPUS_EXCERPT.value and rest and ":" not in rest:
            return cls(kind=MemberKind.CORPUS_EXCERPT, excerpt_id=rest)
        raise ValueError(f"{address!r} is not a pair-member address")


def revision_address(revision_id: str, logical_id: str) -> str:
    """The member address of one node of one committed revision.

    Refuses ids carrying the separator, so an address never parses back into different
    parts than it was built from — the same reason hashes below join on NUL.
    """
    for part in (revision_id, logical_id):
        if not part or ":" in part:
            raise ValueError(f"{part!r} cannot form an unambiguous member address")
    return f"{MemberKind.REVISION_NODE.value}:{revision_id}:{logical_id}"


def excerpt_address(excerpt_id: str) -> str:
    if not excerpt_id or ":" in excerpt_id:
        raise ValueError(f"{excerpt_id!r} cannot form an unambiguous member address")
    return f"{MemberKind.CORPUS_EXCERPT.value}:{excerpt_id}"


def excerpt_id_for(text: str) -> str:
    """Content address of one comparison excerpt — the same canonical form every hash uses.

    `content_hash` canonicalizes (LF + NFC) before hashing, so the same visible prose pasted
    from two editors is one excerpt rather than two, and a CRLF checkout cannot fork the
    corpus.
    """
    return f"exc-{content_hash(text)[:24]}"


@dataclass(frozen=True, slots=True)
class ComparisonExcerpt:
    """One matched published-human excerpt: the other side of the superiority claim.

    `source`, `genre` and `era` are the matching covariates the craft corpus's standing
    demand requires recorded — §56.3 measured revealed labels selecting story size and era
    rather than prose, so a comparison that cannot say what it was matched on is a
    comparison against a confound. They are required and refused blank rather than
    defaulted, on §59's discipline: the permissive answer must be said, not inherited.
    """

    excerpt_id: str
    text: str
    source: str
    genre: str
    era: str
    words: int
    added_at: str

    def __post_init__(self) -> None:
        if canonicalize(self.text) != self.text:
            raise ValueError("excerpt text is not canonical; build via from_text")
        if not self.text.strip():
            raise ValueError("an empty excerpt is not prose anyone can prefer")
        expected = excerpt_id_for(self.text)
        if self.excerpt_id != expected:
            raise ValueError(f"excerpt_id {self.excerpt_id} does not address this text")
        if self.words != len(self.text.split()):
            raise ValueError(f"words {self.words} does not count this text")
        for name, value in (("source", self.source), ("genre", self.genre), ("era", self.era)):
            if not value.strip():
                raise ValueError(f"an excerpt with no {name} cannot claim to be matched")

    @classmethod
    def from_text(
        cls, text: str, *, source: str, genre: str, era: str, added_at: str
    ) -> ComparisonExcerpt:
        canonical = canonicalize(text)
        return cls(
            excerpt_id=excerpt_id_for(canonical),
            text=canonical,
            source=source,
            genre=genre,
            era=era,
            words=len(canonical.split()),
            added_at=added_at,
        )


class TiePolicy(enum.StrEnum):
    """How a tie enters the win rate. Declared on the protocol — §61 pre-registration (2).

    Declared before the first judgment because the two policies move the number in opposite
    directions and choosing after seeing the ties is choosing the answer: `HALF_WIN` counts
    a tie as half a win (a reader who cannot separate the prose is evidence of parity),
    `DROP` excludes ties from the denominator (only expressed preference counts).
    """

    HALF_WIN = "half_win"
    DROP = "drop"


class PairGrain(enum.StrEnum):
    """The unit each side of a pair is: one scene, or one contiguous chapter (§61).

    Distinct from `calibration.Grain`, which ranks the referent of *metric* evidence; this
    names what a reader is handed. Chapter-grain system text awaits an assembly decision —
    production books hold no chapter nodes — so drawing at that grain is refused rather than
    improvised, and the enum member exists so the protocol table does not need a migration
    when assembly lands.
    """

    SCENE = "scene"
    CHAPTER = "chapter"


def protocol_id_for(comparator_frame: str, *, tie_policy: TiePolicy, grain: PairGrain) -> str:
    """Derived from what the protocol declares, and from nothing else.

    `declared_at` is deliberately outside the id: a protocol is a pre-registration, and
    re-declaring the same frame later must collide with the original (INSERT OR IGNORE, then
    an explicit refusal) rather than mint a fresh-looking sibling with a newer timestamp —
    the re-stamp would be exactly the quiet re-registration the record exists to prevent.
    """
    material = payload_digest(
        {
            "comparator_frame": comparator_frame,
            "tie_policy": tie_policy.value,
            "grain": grain.value,
        }
    )
    return f"prot-{material[:24]}"


@dataclass(frozen=True, slots=True)
class PreferenceProtocol:
    """One pre-registered comparison frame — §61 pre-registration (4): the frame *is* the
    claim.

    Beating median tier-matched serials and beating the genre's best are different claims,
    and a win rate reported without its frame is a number that can be read as either. So the
    frame is required prose, the protocol must be on record before a pair may be drawn or
    judged, and every sample row names the protocol it was drawn under.
    """

    protocol_id: str
    comparator_frame: str
    tie_policy: TiePolicy
    grain: PairGrain
    declared_at: str

    def __post_init__(self) -> None:
        if not self.comparator_frame.strip():
            raise ValueError("a protocol with no comparator frame declares no claim")
        expected = protocol_id_for(
            self.comparator_frame, tie_policy=self.tie_policy, grain=self.grain
        )
        if self.protocol_id != expected:
            raise ValueError(f"protocol_id {self.protocol_id} does not address this protocol")


#: The one comparison frame that ships built in: system prose against system prose, judged
#: for selection between candidates. Not the superiority frame — no human comparator is
#: present, so a win here licenses choosing, never the headline claim. The external frame
#: must be declared by the operator before the first reader is paid (§61 pre-registration
#: 4); this one is code because internal K-sibling pairs (§61 Add 3) need a frame before any
#: operator exists to type one, and `DROP` because a tie between two of our own candidates
#: selects nothing.
INTERNAL_FRAME = (
    "internal-v0: both passages were written by this system for the same book. Which would "
    "you rather keep reading? Judged for selection between candidates, not against any "
    "human comparator."
)

INTERNAL_PROTOCOL = PreferenceProtocol(
    protocol_id=protocol_id_for(
        INTERNAL_FRAME, tie_policy=TiePolicy.DROP, grain=PairGrain.SCENE
    ),
    comparator_frame=INTERNAL_FRAME,
    tie_policy=TiePolicy.DROP,
    grain=PairGrain.SCENE,
    # The day the frame landed in code. Fixed rather than stamped at first use, because the
    # declaration is the module's, not the first caller's, and a replayed first draw must
    # not disagree with itself about when the built-in was declared.
    declared_at="2026-08-17T00:00:00Z",
)


class PairVerdict(enum.StrEnum):
    """What a reader says about one presented pair — relative to PRESENTED position.

    Recorded as the reader spoke it, because position is the measurement RevisionBench made
    unavoidable: raw model judges carried a 43-65% positional artifact, and there is no
    reason to assume human readers are exempt. Storing the presented-frame verdict beside
    the orientation bit is what makes positional consistency *measurable* — a canonical-only
    record would randomize the artifact away instead of seeing it.

    `NOT_SURE` is abstention and is recorded rather than coerced, for the reason the audit
    verdict gives: a scale with no way to decline pushes a reader into a verdict they do not
    hold, which calibrates against noise.
    """

    PREFER_FIRST = "prefer_first"
    PREFER_SECOND = "prefer_second"
    TIE = "tie"
    NOT_SURE = "not_sure"

    @property
    def decisive(self) -> bool:
        return self in {PairVerdict.PREFER_FIRST, PairVerdict.PREFER_SECOND}

    def canonical(self, orientation: int) -> PairVerdict:
        """This verdict re-expressed over the canonical (min, max) presentation.

        Derived, never stored twice: two columns encoding one judgment is a disagreement
        waiting to happen, which is the argument that deleted the stored `precision` float
        (§59). Orientation 0 presented (min, max) already; orientation 1 presented
        (max, min), so the two preferences swap and ties and abstentions stand.
        """
        if orientation not in (0, 1):
            raise ValueError(f"orientation {orientation} is not a bit")
        if orientation == 0 or not self.decisive:
            return self
        if self is PairVerdict.PREFER_FIRST:
            return PairVerdict.PREFER_SECOND
        return PairVerdict.PREFER_FIRST


def pair_id_for(addr_a: str, addr_b: str) -> str:
    """Identity of the *unordered* pair, so both presentations share one pair.

    Hashing min-then-max joined on NUL means `pair_id_for(a, b) == pair_id_for(b, a)` by
    construction — the position swap is a property of the sample, never of the pair — and a
    pair cannot be re-rolled into a different identity by listing its members differently.
    """
    if addr_a == addr_b:
        raise ValueError(f"{addr_a!r} against itself is not a pair")
    for address in (addr_a, addr_b):
        # The NUL join below is only unambiguous while no component can carry a NUL.
        # The address constructors never emit one, but an identity function guarded by
        # somebody else's discipline is a collision waiting for a new caller — refused
        # here, so the ambiguity is unrepresentable rather than merely unreached.
        if "\x00" in address:
            raise ValueError("a member address may not carry the NUL join separator")
    low, high = sorted((addr_a, addr_b))
    material = f"{low}\x00{high}".encode()
    return f"pair-{sha256(material).hexdigest()[:24]}"


def sample_id_for(
    pair_id: str,
    orientation: int,
    protocol_id: str,
    *,
    reader_id: str = UNASSIGNED_READER,
) -> str:
    """One judgment row's identity: (pair, orientation, protocol, reader), hashed.

    Orientation is inside the id so the swapped complement is a *sibling row of the same
    pair* rather than a second answer to one row — which is what lets positional
    consistency be measured instead of assumed away. Protocol is inside it because the same
    pair under two frames is two different questions. The reader component is
    `UNASSIGNED_READER` for a queue row anyone may answer, and a real id for a pre-assigned
    panel row; see that constant.
    """
    if orientation not in (0, 1):
        raise ValueError(f"orientation {orientation} is not a bit")
    for component in (pair_id, protocol_id, reader_id):
        # Same rule as `pair_id_for`: the NUL join is the identity's structure, so no
        # component may carry it — otherwise two different (protocol, reader) splits
        # could hash to one sample.
        if "\x00" in component:
            raise ValueError("a sample id component may not carry the NUL join separator")
    material = f"{pair_id}\x00{orientation}\x00{protocol_id}\x00{reader_id}".encode()
    return f"pj-{sha256(material).hexdigest()[:24]}"


def pair_bucket(pair_id: str) -> int:
    """Which of `BUCKETS` this pair falls in. Pure and stable forever, like `bucket_for`."""
    return int.from_bytes(sha256(pair_id.encode()).digest()[:8], "big") % BUCKETS


def should_draw(pair_id: str, rate: float) -> bool:
    """Whether this pair is drawn at `rate`. The audit draw's arithmetic, on pair identity.

    0 draws nothing and 1 draws everything without a special case, and because the bucket is
    a fact about the pair, raising the rate later draws a *superset* of every earlier draw —
    an operator can widen the queue but never quietly swap it.
    """
    if rate <= 0.0:
        return False
    if rate >= 1.0:
        return True
    return pair_bucket(pair_id) < rate * BUCKETS


@dataclass(frozen=True, slots=True)
class PairSample:
    """One presented pair awaiting (or holding) one reader's verdict.

    `left_addr`/`right_addr` are the PRESENTED order — first and second as the reader saw
    them — and `__post_init__` refuses a row whose presentation disagrees with its
    orientation bit or whose `pair_id`/`bucket` disagree with its members, so an incoherent
    sample is unrepresentable rather than merely unlikely (§59's move, applied here).

    `recognized` is §61 pre-registration (3): required on every answered row, excluded from
    analysis when set, and never a reason to drop the row — the exclusion count is itself a
    measurement, because the matched corpus includes some of the genre's most-read serials
    and recognition is the expected case, not an edge case.
    """

    sample_id: str
    pair_id: str
    orientation: int
    protocol_id: str
    left_addr: str
    right_addr: str
    grain: PairGrain
    book_id: str | None
    sampled_at: str
    rate: float
    bucket: int
    reader_id: str | None = None
    verdict: PairVerdict | None = None
    recognized: bool | None = None
    note: str | None = None
    judged_at: str | None = None

    def __post_init__(self) -> None:
        if self.orientation not in (0, 1):
            raise ValueError(f"orientation {self.orientation} is not a bit")
        if self.pair_id != pair_id_for(self.left_addr, self.right_addr):
            raise ValueError(f"pair_id {self.pair_id} does not address these members")
        presented_canonically = self.left_addr < self.right_addr
        if presented_canonically != (self.orientation == 0):
            raise ValueError(
                f"orientation {self.orientation} disagrees with the presented order; the "
                "swap is the orientation bit and nothing else"
            )
        if self.bucket != pair_bucket(self.pair_id):
            raise ValueError(f"bucket {self.bucket} is not this pair's bucket")
        if self.verdict is not None and self.recognized is None:
            raise ValueError(
                "an answered row must carry its recognition flag; §61 pre-registration (3) "
                "excludes recognised judgments, and an unknown flag cannot be excluded"
            )

    @property
    def pending(self) -> bool:
        return self.verdict is None

    @property
    def canonical_verdict(self) -> PairVerdict | None:
        """The verdict over (min, max), derived through the orientation bit."""
        if self.verdict is None:
            return None
        return self.verdict.canonical(self.orientation)


def draw_pairs(
    candidates: Sequence[tuple[str, str | None]],
    corpus: Sequence[str],
    protocol: PreferenceProtocol,
    rate: float,
    *,
    sampled_at: str,
) -> tuple[PairSample, ...]:
    """Every drawn pair between `candidates` and `corpus`, both orientations, in order.

    `candidates` are (member address, book id) for the system side; `corpus` are member
    addresses for the other side. Passing the candidate addresses as `corpus` is the
    system-vs-system draw: the pair space is the cross product minus self-pairs, deduplicated
    on unordered pair identity, so (a, b) and (b, a) are one pair however they arrive.

    Selection is `should_draw` on the pair id — bucket arithmetic, no RNG — and *both*
    orientations of a drawn pair are emitted as first-class sibling samples. Position swap
    is the §61 design, not a randomisation: presenting each pair both ways is what turns the
    RevisionBench positional artifact from a contaminant into a measurement.

    The book id recorded on a sample is the one book its members belong to, or None when
    the members disagree — a cross-book pair is nobody's row, and inventing an owner would
    poison the per-book slice §61 pre-registration (5) divides the family over.
    """
    books = dict(candidates)
    drawn: dict[str, tuple[str, str]] = {}
    for address, _ in candidates:
        for other in corpus:
            if other == address:
                continue
            pair_id = pair_id_for(address, other)
            if pair_id in drawn or not should_draw(pair_id, rate):
                continue
            drawn[pair_id] = (address, other)
    samples: list[PairSample] = []
    for pair_id in sorted(drawn):
        one, other = drawn[pair_id]
        low, high = sorted((one, other))
        book_one, book_other = books.get(one), books.get(other)
        if book_one is not None and book_other is not None and book_one != book_other:
            book_id = None
        else:
            book_id = book_one if book_one is not None else book_other
        for orientation, (left, right) in enumerate(((low, high), (high, low))):
            samples.append(
                PairSample(
                    sample_id=sample_id_for(pair_id, orientation, protocol.protocol_id),
                    pair_id=pair_id,
                    orientation=orientation,
                    protocol_id=protocol.protocol_id,
                    left_addr=left,
                    right_addr=right,
                    grain=protocol.grain,
                    book_id=book_id,
                    sampled_at=sampled_at,
                    rate=rate,
                    bucket=pair_bucket(pair_id),
                )
            )
    return tuple(samples)


class PairOutcome(enum.StrEnum):
    """One judgment resolved to the system side: it won, it lost, or the reader tied."""

    WIN = "win"
    LOSS = "loss"
    TIE = "tie"


def system_side(left_addr: str, right_addr: str) -> str | None:
    """The revision-side member of a mixed pair, or None when the pair has no single one.

    Win rate is denominated against the matched human corpus, so it is defined exactly when
    one member is ours and one is not. An internal pair has no human side and no win rate —
    it selects between candidates, which is a different question with a different consumer.
    """
    kinds = (Member.parse(left_addr).kind, Member.parse(right_addr).kind)
    if kinds[0] is kinds[1]:
        return None
    return left_addr if kinds[0] is MemberKind.REVISION_NODE else right_addr


def system_outcome(sample: PairSample) -> PairOutcome | None:
    """The answered judgment as an outcome for the system side, or None when excluded.

    None for: a pending row; an abstention (`NOT_SURE` is an answer about the reader, not
    the prose); a recognised passage (§61 pre-registration (3) — §58 measured familiarity
    moving a score several times harder than real damage, and exclusion at analysis is how
    the flag is honoured without dropping the row); and a pair with no single system side.
    """
    if sample.verdict is None or sample.recognized:
        return None
    side = system_side(sample.left_addr, sample.right_addr)
    if side is None or sample.verdict is PairVerdict.NOT_SURE:
        return None
    if sample.verdict is PairVerdict.TIE:
        return PairOutcome.TIE
    preferred = (
        sample.left_addr
        if sample.verdict is PairVerdict.PREFER_FIRST
        else sample.right_addr
    )
    return PairOutcome.WIN if preferred == side else PairOutcome.LOSS


@dataclass(frozen=True, slots=True)
class WinObservation:
    """One analysable judgment, keyed by its two cluster dimensions.

    The pair and the reader are the §61 pre-registration (1) clusters: fifty judgments from
    one reader are one reader's taste wearing a sample size, and fifty readers on one pair
    are one pair's luck wearing one. Both orientations of a pair judged by one reader share
    both keys and therefore resample together, which is the point — they are not
    independent trials and the interval must not pretend they are.
    """

    pair_id: str
    reader_id: str
    outcome: PairOutcome


_SCORE: Mapping[PairOutcome, float] = {
    PairOutcome.WIN: 1.0,
    PairOutcome.TIE: 0.5,
    PairOutcome.LOSS: 0.0,
}


def _analysis_set(
    judgments: Sequence[WinObservation], tie_policy: TiePolicy
) -> tuple[WinObservation, ...]:
    """Ties in or out per the declared policy — §61 pre-registration (2), applied once."""
    if tie_policy is TiePolicy.HALF_WIN:
        return tuple(judgments)
    return tuple(j for j in judgments if j.outcome is not PairOutcome.TIE)


def observed_win_rate(
    judgments: Sequence[WinObservation], *, tie_policy: TiePolicy
) -> float:
    """The point estimate, for reporting beside the bound — never in place of it.

    §59's lesson verbatim: 14 of 17 reads as a confident 0.82 and bounds at 0.566. The
    estimate is printed second and the bound is what any claim turns on.
    """
    observations = _analysis_set(judgments, tie_policy)
    if not observations:
        raise ValueError("no decisive judgment to estimate a rate over")
    return sum(_SCORE[j.outcome] for j in observations) / len(observations)


def win_rate_lower_bound(
    judgments: Sequence[WinObservation], *, alpha: float, tie_policy: TiePolicy
) -> float:
    """Two-way cluster-bootstrap lower confidence bound on the system's win rate.

    **Clustered over readers and pairs independently, because §61 pre-registration (1) is
    bought by two measurements from opposite sides**: §59 added `clusters` because a
    binomial interval over fifty scenes of one book is one observation wearing an interval,
    and the same readers judging many pairs is the same failure in the other dimension. The
    §58 addendum replaced a Wilson interval that treated 720 clustered pairs as independent
    with a chapter-resampled bootstrap; this extends that pattern to both dimensions at
    once: each resample redraws readers with replacement and pairs with replacement,
    weights every judgment by how often its reader and its pair were both drawn, and the
    bound is the `alpha/2` quantile of the resampled rates — two-sided, keeping
    `PROMOTION_ALPHA`'s declared lineage, where a silent switch to one-sided would loosen
    the bar while looking like a refactor.

    **Deterministic, with no wall-clock RNG.** The generator is seeded from a content
    digest of the judgment set itself, so the same evidence yields the same bound on every
    machine and every replay, and nobody can re-run the bootstrap hoping for a kinder
    quantile. Changing one verdict changes the seed — which is a feature: the bound is a
    fact about the verdict set, not about a session.

    `alpha` is exposed rather than pinned because the headline claim owes a further
    division: §61 pre-registration (5) divides the level by the candidate-book count when
    more than one book could have been reported — §6.4's selection family applied to the
    claim itself. Refuses fewer than two reader clusters or two pair clusters: below that
    the interval is one observation wearing an interval (§59).

    **Measured under-coverage at small cluster counts, stated so the number is not
    over-read.** A percentile bootstrap earns its nominal level only as clusters grow; at
    the floor it can have no width at all — verified: two readers by two pairs, all wins,
    every resample rates 1.0 and the "97.5% lower bound" is 1.0 from four observations.
    Below roughly `DESCRIPTIVE_CLUSTER_FLOOR` clusters per dimension the bound is
    descriptive, not calibrated, and the promotion floors are the real gate; the operator
    surface prints exactly that caveat rather than this function refusing, because a
    descriptive number honestly labelled is still worth reading.

    Ties enter per the declared `tie_policy`. A resample in which no drawn reader ever met
    a drawn pair estimates nothing and is skipped rather than scored.
    """
    if not 0.0 < alpha < 1.0:
        raise ValueError(f"alpha {alpha} is not a confidence level")
    observations = _analysis_set(judgments, tie_policy)
    if not observations:
        raise ValueError("no decisive judgment to bound a rate over")
    readers = sorted({j.reader_id for j in observations})
    pairs = sorted({j.pair_id for j in observations})
    if len(readers) < 2 or len(pairs) < 2:
        raise ValueError(
            f"{len(readers)} reader cluster(s) and {len(pairs)} pair cluster(s); an "
            "interval clustered over fewer than two of either is one observation wearing "
            "an interval"
        )
    reader_index = {reader: index for index, reader in enumerate(readers)}
    pair_index = {pair: index for index, pair in enumerate(pairs)}
    scored = [
        (reader_index[j.reader_id], pair_index[j.pair_id], _SCORE[j.outcome])
        for j in observations
    ]
    seed_material = payload_digest(
        {
            "judgments": sorted(
                (j.pair_id, j.reader_id, j.outcome.value) for j in observations
            )
        }
    )
    rng = Random(int(seed_material[:16], 16))
    rates: list[float] = []
    for _ in range(BOOTSTRAP_RESAMPLES):
        reader_weights = [0] * len(readers)
        for _ in readers:
            reader_weights[rng.randrange(len(readers))] += 1
        pair_weights = [0] * len(pairs)
        for _ in pairs:
            pair_weights[rng.randrange(len(pairs))] += 1
        total = 0.0
        won = 0.0
        for reader, pair, score in scored:
            weight = reader_weights[reader] * pair_weights[pair]
            total += weight
            won += weight * score
        if total:
            rates.append(won / total)
    if not rates:
        raise ValueError(
            "every bootstrap resample was empty; the judgments are too sparsely crossed "
            "over readers and pairs to bound"
        )
    rates.sort()
    # The k-th smallest resampled rate with k = ceil((alpha/2) * n): the conservative
    # rank convention. Truncation took k+1 whenever the product was an integer — at 2000
    # resamples and alpha 0.05 that read the 51st smallest where the 2.5% point is the
    # 50th, one rank anti-conservative, which is the direction a bar must never lean.
    index = max(0, math.ceil((alpha / 2.0) * len(rates)) - 1)
    return rates[min(index, len(rates) - 1)]


def analysable_judgments(samples: Iterable[PairSample]) -> tuple[PairSample, ...]:
    """The answered rows a preference holdout can be denominated in.

    Excludes recognised judgments (§61 pre-registration (3)) and abstentions: a row the
    analysis must skip cannot be part of the count a claimed holdout is checked against,
    or fifty recognised abstentions would license a fifty-judgment claim. Ties stay —
    whether they enter is the protocol's declared tie policy, applied at analysis, and a
    count that guessed the policy here would disagree with the one that applied it there.

    Protocols pool deliberately, as `pair_verdicts_digest_for` pools too: a holdout check
    and a staleness digest that over-invalidate are the safe direction, and per-protocol
    slicing belongs to the consumer that knows which protocol a calibration was measured
    under.

    **Machine-written rows are excluded, because the class is constituted as human.**
    `EvidenceClass.PREFERENCE` *is* "a human's blinded, position-swapped choice between two
    texts", and that property had no enforcement anywhere — no source column, no CHECK, no
    predicate — while the §72 judge writes its verdicts through this very table. So one
    human-anchored calibration licensing one judged tournament put the judge's own verdicts
    into the pool the NEXT preference calibration's holdout is denominated in, with nothing
    counting them separately: the class laundering itself one licence at a time. The
    exclusion is of the *count* only. The rows stay on record and stay in the staleness
    digest below — the same shape recognition already has, and for the same reason: a row
    the analysis must skip is still a fact about the verdict set.
    """
    return tuple(
        sample
        for sample in samples
        if sample.verdict is not None
        and not sample.recognized
        and sample.verdict is not PairVerdict.NOT_SURE
        and not is_machine_reader(sample.reader_id)
    )


def pair_verdicts_digest_for(samples: Iterable[PairSample]) -> str:
    """Content address over the answered pair-verdict set.

    Delegates to `verdicts_digest_for` verbatim — it hashes sorted (sample_id, verdict)
    string pairs and never inspects what a sample is — and exists as a named function so
    the per-class digest dispatch has a `PREFERENCE` entry to cite. The silent hole this
    closes: an `EvidenceClass` with no digest entry gets None from the dispatch, and
    `why_not_promotable` reads a None digest as "no staleness check requested", not as
    stale — so preference calibrations would never re-open when the pair verdicts moved.

    **Machine-written rows move this digest, and that is the decided side.** They are cut
    from `analysable_judgments` above and kept here on purpose: §72 states that "judge
    verdicts move the answered-verdict digest and stale the calibration that licensed them
    — one calibration buys roughly one judged tournament before re-measurement", and that
    expiry is the whole price of the judge path. The laundering fix is about the holdout
    *denominator*, not the staleness *address*; reading the exclusion into this function
    would quietly turn one licence into unlimited judged tournaments, which is a far more
    expensive direction than over-invalidation.
    """
    return verdicts_digest_for(
        (sample.sample_id, sample.verdict.value)
        for sample in samples
        if sample.verdict is not None
    )


__all__ = [
    "BOOTSTRAP_RESAMPLES",
    "DESCRIPTIVE_CLUSTER_FLOOR",
    "INTERNAL_FRAME",
    "INTERNAL_PROTOCOL",
    "MACHINE_READER_PREFIX",
    "UNASSIGNED_READER",
    "ComparisonExcerpt",
    "Member",
    "MemberKind",
    "PairGrain",
    "PairOutcome",
    "PairSample",
    "PairVerdict",
    "PreferenceProtocol",
    "TiePolicy",
    "WinObservation",
    "analysable_judgments",
    "draw_pairs",
    "excerpt_address",
    "excerpt_id_for",
    "is_machine_reader",
    "machine_reader_id",
    "observed_win_rate",
    "pair_bucket",
    "pair_id_for",
    "pair_verdicts_digest_for",
    "protocol_id_for",
    "revision_address",
    "sample_id_for",
    "should_draw",
    "system_outcome",
    "system_side",
    "win_rate_lower_bound",
]
