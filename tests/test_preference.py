"""§61's pairwise preference engine: pair identity, the blinded queue, and the bound.

**What these tests do not establish.** Nothing here shows the system beats matched human
prose, because nothing can: the evidence is paid human judgment and none has been bought.
What they establish is the *spine* — that a pair is a fact about its members rather than
about when anyone drew it, that both orientations are first-class sibling rows, that a
verdict lands once and never twice, that recognition is stored and excluded rather than
dropped, and that preference evidence can never construct a blocking gate however sound it
is. Each pin is a way §61's bar could be passed without being met.

The tests worth reading are the refusals: the draw refusing to run under no stored
protocol, `win_rate_lower_bound` refusing fewer than two clusters of either dimension, and
`veto_for` raising on `PREFERENCE` — the zero-code enforcement that preference evidence
licenses selection between candidates (§61 Add 3) and never absolute refusal of one text.
"""

from __future__ import annotations

import json

import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.handlers import _craft_ladder
from litharness.cli import EXIT_ATTENTION, EXIT_FAULT, EXIT_OK, main
from litharness.domain.calibration import (
    MIN_HOLDOUT,
    EvidenceClass,
    NotPromotable,
    promoted_gate,
    verdicts_digest_for,
    veto_for,
)
from litharness.domain.craft import CraftMetric
from litharness.domain.preference import (
    INTERNAL_PROTOCOL,
    ComparisonExcerpt,
    Member,
    MemberKind,
    PairGrain,
    PairOutcome,
    PairSample,
    PairVerdict,
    PreferenceProtocol,
    TiePolicy,
    WinObservation,
    analysable_judgments,
    draw_pairs,
    excerpt_address,
    excerpt_id_for,
    is_machine_reader,
    machine_reader_id,
    observed_win_rate,
    pair_bucket,
    pair_id_for,
    pair_verdicts_digest_for,
    protocol_id_for,
    revision_address,
    sample_id_for,
    system_outcome,
    system_side,
    win_rate_lower_bound,
)
from tests.conftest import BOOK_ID, make_revision
from tests.test_calibration import TODAY, a_calibration, answered_holdout

FRAME = "against median tier-matched RoyalRoad LitRPG serials, 2019-2022, scene grain"

PROTOCOL = PreferenceProtocol(
    protocol_id=protocol_id_for(FRAME, tie_policy=TiePolicy.HALF_WIN, grain=PairGrain.SCENE),
    comparator_frame=FRAME,
    tie_policy=TiePolicy.HALF_WIN,
    grain=PairGrain.SCENE,
    declared_at=TODAY,
)


@pytest.fixture
def store(tmp_path) -> SqliteStore:
    return SqliteStore.open(tmp_path / "litharness.db")


@pytest.fixture
def db(tmp_path):
    return tmp_path / "cli.db"


def run(db, *args: str) -> int:
    return main(["--database", str(db), *args])


def a_pair_sample(
    index: int, *, protocol_id: str = PROTOCOL.protocol_id, orientation: int = 0
) -> PairSample:
    """One mixed (system vs corpus) sample with every derived field derived."""
    system = revision_address(f"rev-{index}", "scene-1")
    human = excerpt_address(f"exc-{index}")
    pair_id = pair_id_for(system, human)
    low, high = sorted((system, human))
    left, right = (low, high) if orientation == 0 else (high, low)
    return PairSample(
        sample_id=sample_id_for(pair_id, orientation, protocol_id),
        pair_id=pair_id,
        orientation=orientation,
        protocol_id=protocol_id,
        left_addr=left,
        right_addr=right,
        grain=PairGrain.SCENE,
        book_id=BOOK_ID,
        sampled_at=TODAY,
        rate=1.0,
        bucket=pair_bucket(pair_id),
    )


def answered_pair_holdout(store: SqliteStore, n: int = MIN_HOLDOUT) -> str:
    """Put `n` answered pair samples in the store and return their digest.

    The preference twin of `answered_holdout`: a preference calibration's holdout is pair
    verdicts, so the answered-count check and the staleness digest both read this table and
    not the audit queue — the wrong-population count the area map warns about.
    """
    store.record_protocol(PROTOCOL)
    for index in range(n):
        sample = a_pair_sample(index)
        store.record_pair_sample(sample)
        store.record_pair_verdict(
            sample.sample_id, PairVerdict.PREFER_FIRST, at=TODAY, by="reader",
            recognized=False,
        )
    return pair_verdicts_digest_for(store.pair_samples())


# -- pair identity is content, never chance (§67's inheritance) ---------------------------


def test_a_pair_is_the_same_pair_whichever_way_its_members_arrive() -> None:
    """The unordered pair is the identity; presentation is the orientation bit, elsewhere.
    An id that depended on listing order would let the same two texts be two pairs, and a
    re-listed draw would re-roll the queue."""
    a = revision_address("rev-1", "scene-1")
    b = excerpt_address("exc-1")
    assert pair_id_for(a, b) == pair_id_for(b, a)
    assert pair_id_for(a, b) != pair_id_for(a, excerpt_address("exc-2"))
    with pytest.raises(ValueError, match="not a pair"):
        pair_id_for(a, a)


def test_an_excerpt_is_addressed_by_its_canonical_text() -> None:
    """The same visible prose pasted from two editors is one excerpt: CRLF and decomposed
    unicode canonicalize before hashing, exactly like every other content hash here."""
    text = "The gate stood open.\nNo one watched it."
    assert excerpt_id_for(text) == excerpt_id_for("The gate stood open.\r\nNo one watched it.")
    assert excerpt_id_for(text) != excerpt_id_for(text + " Almost.")
    excerpt = ComparisonExcerpt.from_text(
        "The gate stood open.\r\nNo one watched it.",
        source="test-serial", genre="litrpg", era="pre-2023", added_at=TODAY,
    )
    assert excerpt.excerpt_id == excerpt_id_for(text)
    assert excerpt.words == 8


def test_both_orientations_are_distinct_samples_sharing_one_pair() -> None:
    """Position swap is the §61 design: each drawn pair yields two first-class sibling
    rows, one per presentation, so positional consistency is measurable — the RevisionBench
    43-65% positional artifact is the reason position is recorded, not just randomized."""
    candidate = (revision_address("rev-1", "scene-1"), BOOK_ID)
    corpus = [excerpt_address("exc-1")]
    samples = draw_pairs([candidate], corpus, PROTOCOL, 1.0, sampled_at=TODAY)
    assert len(samples) == 2
    first, second = samples
    assert first.pair_id == second.pair_id
    assert {first.orientation, second.orientation} == {0, 1}
    assert (first.left_addr, first.right_addr) == (second.right_addr, second.left_addr)
    assert first.sample_id != second.sample_id


def test_the_draw_is_derived_from_content_and_converges_on_replay(store: SqliteStore) -> None:
    """The audit draw's replay-convergence property, inherited whole: the same inputs draw
    the same pairs onto the same rows, so a replayed draw grows nothing."""
    candidates = [(revision_address(f"rev-{i}", "scene-1"), BOOK_ID) for i in range(3)]
    corpus = [excerpt_address(f"exc-{i}") for i in range(3)]
    once = draw_pairs(candidates, corpus, PROTOCOL, 1.0, sampled_at=TODAY)
    again = draw_pairs(candidates, corpus, PROTOCOL, 1.0, sampled_at=TODAY)
    assert once == again
    store.record_protocol(PROTOCOL)
    assert all(store.record_pair_sample(sample) for sample in once)
    assert not any(store.record_pair_sample(sample) for sample in again)
    assert len(store.pair_samples()) == len(once)


def test_a_higher_rate_draws_a_superset_never_a_reshuffle() -> None:
    """The bucket is a fact about the pair, so widening the rate widens the queue and an
    operator can never re-roll their way to a kinder sample."""
    candidates = [(revision_address(f"rev-{i}", "scene-1"), BOOK_ID) for i in range(6)]
    corpus = [excerpt_address(f"exc-{i}") for i in range(6)]

    def pair_ids(rate: float) -> set[str]:
        return {
            sample.pair_id
            for sample in draw_pairs(candidates, corpus, PROTOCOL, rate, sampled_at=TODAY)
        }

    assert pair_ids(0.0) == set()
    low, mid, everything = pair_ids(0.3), pair_ids(0.7), pair_ids(1.0)
    assert low <= mid <= everything
    assert len(everything) == 36


def test_an_incoherent_sample_is_unrepresentable() -> None:
    """§59's move applied here: the invalid states are refused by the constructor, so a
    row whose presentation, identity or bucket disagrees with its members cannot exist."""
    good = a_pair_sample(1)
    with pytest.raises(ValueError, match="does not address"):
        PairSample(**{**_fields(good), "pair_id": "pair-000000000000000000000000"})
    with pytest.raises(ValueError, match="orientation"):
        PairSample(**{**_fields(good), "orientation": 1})
    with pytest.raises(ValueError, match="bucket"):
        PairSample(**{**_fields(good), "bucket": good.bucket + 1})
    with pytest.raises(ValueError, match="recognition flag"):
        PairSample(**{**_fields(good), "verdict": PairVerdict.TIE})


def _fields(sample: PairSample) -> dict:
    return {
        name: getattr(sample, name)
        for name in (
            "sample_id", "pair_id", "orientation", "protocol_id", "left_addr",
            "right_addr", "grain", "book_id", "sampled_at", "rate", "bucket",
            "reader_id", "verdict", "recognized", "note", "judged_at",
        )
    }


def test_a_member_address_round_trips_and_refuses_ambiguity() -> None:
    member = Member.parse(revision_address("rev-1", "scene-1"))
    assert member.kind is MemberKind.REVISION_NODE
    assert (member.revision_id, member.logical_id) == ("rev-1", "scene-1")
    assert member.address == "rev:rev-1:scene-1"
    excerpt = Member.parse(excerpt_address("exc-1"))
    assert excerpt.kind is MemberKind.CORPUS_EXCERPT and excerpt.excerpt_id == "exc-1"
    with pytest.raises(ValueError, match="unambiguous"):
        revision_address("rev:1", "scene-1")
    with pytest.raises(ValueError, match="not a pair-member address"):
        Member.parse("who:knows")
    # The NUL join is the identity's structure, refused at the hash rather than trusted
    # to constructor discipline: two different splits must never collide to one id.
    with pytest.raises(ValueError, match="NUL"):
        pair_id_for("rev:a\x00b:scene-1", excerpt_address("exc-1"))
    with pytest.raises(ValueError, match="NUL"):
        sample_id_for("pair-1", 0, "prot-1", reader_id="reader\x00imposter")


# -- verdicts: presented position, canonical mapping, write-once --------------------------


def test_canonical_maps_correctly_under_both_orientations() -> None:
    """The canonical frame is (min, max); orientation 1 presented (max, min), so the two
    preferences swap and ties and abstentions stand. Derived, never stored twice."""
    assert PairVerdict.PREFER_FIRST.canonical(0) is PairVerdict.PREFER_FIRST
    assert PairVerdict.PREFER_FIRST.canonical(1) is PairVerdict.PREFER_SECOND
    assert PairVerdict.PREFER_SECOND.canonical(1) is PairVerdict.PREFER_FIRST
    assert PairVerdict.TIE.canonical(1) is PairVerdict.TIE
    assert PairVerdict.NOT_SURE.canonical(1) is PairVerdict.NOT_SURE
    with pytest.raises(ValueError, match="not a bit"):
        PairVerdict.TIE.canonical(2)

    swapped = a_pair_sample(1, orientation=1)
    judged = PairSample(**{
        **_fields(swapped), "verdict": PairVerdict.PREFER_FIRST, "recognized": False,
    })
    assert judged.canonical_verdict is PairVerdict.PREFER_SECOND


def test_a_pair_verdict_is_recorded_once_and_never_overwritten(store: SqliteStore) -> None:
    """`record_verdict`'s pattern exactly: the first reading is the blind one, and a
    second answer is a no-op rather than a replacement."""
    store.record_protocol(PROTOCOL)
    sample = a_pair_sample(1)
    store.record_pair_sample(sample)
    assert store.record_pair_verdict(
        sample.sample_id, PairVerdict.PREFER_SECOND, at=TODAY, by="reader-a",
        recognized=False, note="the second had a pulse",
    )
    assert not store.record_pair_verdict(
        sample.sample_id, PairVerdict.PREFER_FIRST, at=TODAY, by="reader-b",
        recognized=False,
    )
    [stored] = store.pair_samples()
    assert stored.verdict is PairVerdict.PREFER_SECOND
    assert stored.reader_id == "reader-a"
    assert stored.recognized is False
    assert stored.note == "the second had a pulse"
    assert not stored.pending


def test_recognition_is_stored_and_excluded_never_dropped(store: SqliteStore) -> None:
    """§61 pre-registration (3): §58 measured familiarity with published text swinging a
    score several times harder than real damage. The flag rides the row, the row stays on
    record, and analysis skips it — the exclusion count is itself a finding."""
    store.record_protocol(PROTOCOL)
    sample = a_pair_sample(1)
    store.record_pair_sample(sample)
    store.record_pair_verdict(
        sample.sample_id, PairVerdict.PREFER_FIRST, at=TODAY, by="reader",
        recognized=True,
    )
    [stored] = store.pair_samples()
    assert stored.recognized is True
    assert stored.verdict is PairVerdict.PREFER_FIRST, "stored, not dropped"
    assert system_outcome(stored) is None, "and excluded from analysis"


# -- protocols: the frame is the claim (§61 pre-registration 4) ---------------------------


def test_a_protocol_is_declared_once_and_redeclaration_collides(store: SqliteStore) -> None:
    """`declared_at` is outside the id on purpose: re-declaring the same frame later must
    collide with the original pre-registration, not mint a fresh-looking sibling."""
    assert PROTOCOL.protocol_id == protocol_id_for(
        FRAME, tie_policy=TiePolicy.HALF_WIN, grain=PairGrain.SCENE
    )
    assert store.record_protocol(PROTOCOL)
    restamped = PreferenceProtocol(
        protocol_id=PROTOCOL.protocol_id,
        comparator_frame=FRAME,
        tie_policy=TiePolicy.HALF_WIN,
        grain=PairGrain.SCENE,
        declared_at="2027-01-01T00:00:00Z",
    )
    assert not store.record_protocol(restamped)
    [stored] = store.protocols()
    assert stored.declared_at == TODAY, "the original declaration stands"
    with pytest.raises(ValueError, match="no comparator frame"):
        PreferenceProtocol(
            protocol_id=protocol_id_for(" ", tie_policy=TiePolicy.DROP, grain=PairGrain.SCENE),
            comparator_frame=" ",
            tie_policy=TiePolicy.DROP,
            grain=PairGrain.SCENE,
            declared_at=TODAY,
        )


def test_the_internal_protocol_is_a_stored_record_like_any_other(store: SqliteStore) -> None:
    """Built in, not exempt: internal pairs still reference a stored protocol row, so the
    no-stored-protocol refusal has no carve-out to grow through."""
    assert store.record_protocol(INTERNAL_PROTOCOL)
    assert not store.record_protocol(INTERNAL_PROTOCOL)
    [stored] = store.protocols()
    assert stored == INTERNAL_PROTOCOL
    assert stored.tie_policy is TiePolicy.DROP, "a tie between our own candidates selects nothing"


# -- the win-rate bound (§61 pre-registrations 1, 2, 5) -----------------------------------


def _mixed_observations() -> list[WinObservation]:
    """4 readers x 5 pairs: 10 wins, 5 losses, 5 ties, in a fixed crossing pattern."""
    outcomes = {0: PairOutcome.LOSS, 2: PairOutcome.TIE}
    return [
        WinObservation(
            pair_id=f"pair-{pair}", reader_id=f"reader-{reader}",
            outcome=outcomes.get((reader + pair) % 4, PairOutcome.WIN),
        )
        for reader in range(4)
        for pair in range(5)
    ]


def test_the_bound_is_exact_on_degenerate_evidence() -> None:
    """Cases whose bootstrap distribution is a point, so the bound is hand-derivable: every
    resample of an all-win set rates 1.0, of an all-loss set 0.0, and of an all-tie set
    under half_win exactly 0.5."""
    def uniform(outcome: PairOutcome) -> list[WinObservation]:
        return [
            WinObservation(pair_id=f"p{pair}", reader_id=f"r{reader}", outcome=outcome)
            for reader in range(2)
            for pair in range(2)
        ]

    assert win_rate_lower_bound(
        uniform(PairOutcome.WIN), alpha=0.05, tie_policy=TiePolicy.DROP
    ) == 1.0
    assert win_rate_lower_bound(
        uniform(PairOutcome.LOSS), alpha=0.05, tie_policy=TiePolicy.DROP
    ) == 0.0
    assert win_rate_lower_bound(
        uniform(PairOutcome.TIE), alpha=0.05, tie_policy=TiePolicy.HALF_WIN
    ) == 0.5


def test_one_bad_cell_collapses_a_minimum_cluster_bound_and_that_is_the_point() -> None:
    """Hand-derived, the way §59 pinned `exact_lower_bound`. Two readers, two pairs, one
    loss: a resample rates 0.0 exactly when the losing reader and the losing pair are both
    drawn twice, probability 1/16 — comfortably above the 2.5% quantile, so the lower
    bound is 0.0. Three wins of four reads as 0.75 and bounds at nothing, which is what
    an interval over two clusters of each dimension is worth: §61 sizing says 100-150
    decisive judgments, and this is why."""
    one_loss = [
        WinObservation(
            pair_id=f"p{pair}", reader_id=f"r{reader}",
            outcome=PairOutcome.LOSS if (reader, pair) == (1, 1) else PairOutcome.WIN,
        )
        for reader in range(2)
        for pair in range(2)
    ]
    assert observed_win_rate(one_loss, tie_policy=TiePolicy.DROP) == 0.75
    assert win_rate_lower_bound(one_loss, alpha=0.05, tie_policy=TiePolicy.DROP) == 0.0


def test_the_bound_is_deterministic_and_pinned() -> None:
    """Frozen against the implementation at landing, the way §59 pinned the exact bound —
    with the honest difference stated: no published table exists for a two-way cluster
    bootstrap of this data, so these values freeze the algorithm (resample count, seed
    derivation, quantile convention) rather than checking it against outside arithmetic.
    A change to any of those moves these numbers and must be a decision, not drift.

    The quantile rank is the conservative convention — the k-th smallest resampled rate
    with k = ceil((alpha/2) * n). The truncation it replaced took k+1 at integer
    products, one rank anti-conservative, and re-pinning the drop-policy values here
    (0.35 -> 1/3 at alpha 0.05, 0.25 -> 0.2 at 0.01) is that correction landing.

    The seed derives from the verdict-set digest, so the same evidence bounds identically
    on every machine and every replay — no wall-clock RNG anywhere in the engine.
    """
    observations = _mixed_observations()
    assert observed_win_rate(observations, tie_policy=TiePolicy.HALF_WIN) == 0.625
    assert observed_win_rate(
        observations, tie_policy=TiePolicy.DROP
    ) == pytest.approx(2 / 3)

    half_win = win_rate_lower_bound(
        observations, alpha=0.05, tie_policy=TiePolicy.HALF_WIN
    )
    assert half_win == win_rate_lower_bound(
        observations, alpha=0.05, tie_policy=TiePolicy.HALF_WIN
    ), "the same evidence yields the same bound, every run"
    assert half_win == pytest.approx(0.4, abs=1e-12)
    assert win_rate_lower_bound(
        observations, alpha=0.05, tie_policy=TiePolicy.DROP
    ) == pytest.approx(1 / 3, abs=1e-12)
    assert win_rate_lower_bound(
        observations, alpha=0.01, tie_policy=TiePolicy.DROP
    ) == pytest.approx(0.2, abs=1e-12)
    assert half_win <= 0.625, "a lower bound below the estimate, always"


def test_a_tighter_level_never_raises_the_bound() -> None:
    observations = _mixed_observations()
    bounds = [
        win_rate_lower_bound(observations, alpha=alpha, tie_policy=TiePolicy.HALF_WIN)
        for alpha in (0.2, 0.05, 0.01)
    ]
    assert bounds == [0.5, 0.4, 0.25]
    assert bounds == sorted(bounds, reverse=True), "decreasing as the level tightens"


def test_ties_enter_per_the_declared_policy_and_nowhere_else() -> None:
    """§61 pre-registration (2): the policy is declared on the protocol before the first
    judgment, because half_win and drop move the number in opposite directions and choosing
    after seeing the ties is choosing the answer."""
    observations = _mixed_observations()
    assert observed_win_rate(observations, tie_policy=TiePolicy.HALF_WIN) == 0.625
    assert observed_win_rate(observations, tie_policy=TiePolicy.DROP) == pytest.approx(2 / 3)
    all_ties = [
        WinObservation(pair_id=f"p{pair}", reader_id=f"r{reader}", outcome=PairOutcome.TIE)
        for reader in range(2)
        for pair in range(2)
    ]
    with pytest.raises(ValueError, match="no decisive judgment"):
        win_rate_lower_bound(all_ties, alpha=0.05, tie_policy=TiePolicy.DROP)


def test_fewer_than_two_clusters_of_either_dimension_is_refused() -> None:
    """§61 pre-registration (1), bought by §59 from both sides: fifty judgments from one
    reader are one reader's taste wearing a sample size, and fifty readers on one pair are
    one pair's luck wearing one. Below two of either, the interval is one observation
    wearing an interval and is refused rather than computed."""
    one_reader = [
        WinObservation(pair_id=f"p{pair}", reader_id="r0", outcome=PairOutcome.WIN)
        for pair in range(10)
    ]
    with pytest.raises(ValueError, match="reader cluster"):
        win_rate_lower_bound(one_reader, alpha=0.05, tie_policy=TiePolicy.DROP)
    one_pair = [
        WinObservation(pair_id="p0", reader_id=f"r{reader}", outcome=PairOutcome.WIN)
        for reader in range(10)
    ]
    with pytest.raises(ValueError, match="pair cluster"):
        win_rate_lower_bound(one_pair, alpha=0.05, tie_policy=TiePolicy.DROP)
    with pytest.raises(ValueError, match="not a confidence level"):
        win_rate_lower_bound(one_reader, alpha=0.0, tie_policy=TiePolicy.DROP)


def test_the_system_side_is_the_revision_member_and_internal_pairs_have_none() -> None:
    system = revision_address("rev-1", "scene-1")
    human = excerpt_address("exc-1")
    assert system_side(system, human) == system
    assert system_side(human, system) == system
    assert system_side(system, revision_address("rev-2", "scene-1")) is None
    assert system_side(human, excerpt_address("exc-2")) is None


def test_a_judgment_resolves_to_the_system_outcome_under_both_orientations() -> None:
    """Whatever way the pair was presented, preferring the system member is a win: the
    resolution reads the presented addresses, so the orientation bit cannot invert it."""
    for orientation in (0, 1):
        sample = a_pair_sample(1, orientation=orientation)
        system = system_side(sample.left_addr, sample.right_addr)
        prefer_left = PairSample(**{
            **_fields(sample), "verdict": PairVerdict.PREFER_FIRST, "recognized": False,
        })
        expected = PairOutcome.WIN if system == sample.left_addr else PairOutcome.LOSS
        assert system_outcome(prefer_left) is expected
        tied = PairSample(**{
            **_fields(sample), "verdict": PairVerdict.TIE, "recognized": False,
        })
        assert system_outcome(tied) is PairOutcome.TIE
        abstained = PairSample(**{
            **_fields(sample), "verdict": PairVerdict.NOT_SURE, "recognized": False,
        })
        assert system_outcome(abstained) is None, "abstention is about the reader"


# -- the evidence class: selection, never refusal (§61 Add 3) -----------------------------


def test_preference_evidence_cannot_produce_a_blocking_gate(store: SqliteStore) -> None:
    """The map's rationale, asserted: preference evidence licenses selection between
    candidates, not absolute refusal of one text, so `EvidenceClass.PREFERENCE` has no
    `veto_for` mapping — and the total-raise there refuses the blocking gate with zero
    code. The dangerous alternative was never a crash; it was a fallback handing
    `CRAFT_BELOW_BAR` — a quality claim — to evidence that measured a relative choice.

    The calibration itself is *sound*: every evidence check passes, which is exactly why
    the refusal must live in the veto and not in the arithmetic — the same row is the
    future selection judge's license (§61 Add 3), and evidence checks that lied about its
    soundness would poison that consumer too.
    """
    digest = answered_pair_holdout(store)
    row = a_calibration(evidence_class=EvidenceClass.PREFERENCE, verdicts_digest=digest)
    assert row.why_not_promotable(TODAY, digest, answered=MIN_HOLDOUT) is None, (
        "sound, current evidence — the refusal is not an evidence defect"
    )
    with pytest.raises(NotPromotable, match="licenses no refusal"):
        veto_for(EvidenceClass.PREFERENCE)
    with pytest.raises(NotPromotable, match="licenses no refusal"):
        promoted_gate(row, 6.0, today=TODAY, verdicts_digest=digest, answered=MIN_HOLDOUT)


def test_a_preference_calibration_degrades_to_annotation_in_the_ladder(
    store: SqliteStore,
) -> None:
    """Through the wired path: the craft ladder catches `NotPromotable` per metric, so a
    preference row annotates loudly instead of blocking — and instead of failing the
    draft."""
    digest = answered_pair_holdout(store)
    store.record_calibration(
        a_calibration(evidence_class=EvidenceClass.PREFERENCE, verdicts_digest=digest)
    )
    [gate] = _craft_ladder(
        store, (CraftMetric(metric_id="craft.tricolon_rate.v0", value=6.0, caveat="t"),),
        today=TODAY,
    )
    assert not gate.blocking
    assert "licenses no refusal" in (gate.detail or "")


def test_a_new_pair_verdict_re_opens_preference_calibrations_not_judgment_ones(
    store: SqliteStore,
) -> None:
    """The per-class digest dispatch, exercised in both directions. The silent hole it
    closes: `digests.get` returns None for an unmapped class and a None digest reads as
    "no staleness check requested" — so a preference class without its own digest entry
    would never re-open when the pair verdicts moved, the promoted-by-omission bug wearing
    a new class. And the dispatch must not conflate the tables either way: a pair verdict
    is not audit disagreement, so it must not re-open the judgment gate."""
    judgment_digest = answered_holdout(store)
    pair_digest = answered_pair_holdout(store)
    store.record_calibration(a_calibration(verdicts_digest=judgment_digest))
    preference_row = a_calibration(
        evidence_class=EvidenceClass.PREFERENCE, verdicts_digest=pair_digest
    )

    metric = (CraftMetric(metric_id="craft.tricolon_rate.v0", value=6.0, caveat="t"),)
    assert _craft_ladder(store, metric, today=TODAY)[0].blocking

    extra = a_pair_sample(MIN_HOLDOUT + 1)
    store.record_pair_sample(extra)
    store.record_pair_verdict(
        extra.sample_id, PairVerdict.TIE, at=TODAY, by="reader", recognized=False
    )
    moved = pair_verdicts_digest_for(store.pair_samples())
    assert moved != pair_digest, "one pair verdict moves the preference digest"
    assert _craft_ladder(store, metric, today=TODAY)[0].blocking, (
        "and re-opens nothing in the judgment class: a pair verdict is not audit "
        "disagreement"
    )
    why = preference_row.why_not_promotable(TODAY, moved, answered=MIN_HOLDOUT + 1)
    assert why is not None and "verdict set has changed" in why

    audit_extra_digest = answered_holdout(store, n=MIN_HOLDOUT + 1)
    assert audit_extra_digest != judgment_digest
    [gate] = _craft_ladder(store, metric, today=TODAY)
    assert not gate.blocking, "a new audit verdict re-opens the judgment gate (§10.5)"
    assert "verdict set has changed" in (gate.detail or "")
    assert preference_row.why_not_promotable(TODAY, moved, answered=MIN_HOLDOUT + 1) == why, (
        "and leaves the preference row exactly as stale as its own table says"
    )


def test_the_pair_digest_is_order_independent_and_shape_agnostic(store: SqliteStore) -> None:
    """`pair_verdicts_digest_for` delegates to `verdicts_digest_for` verbatim — it hashes
    sorted (sample_id, verdict) string pairs and never inspects what a sample is."""
    digest = answered_pair_holdout(store, n=3)
    samples = store.pair_samples()
    assert pair_verdicts_digest_for(reversed(samples)) == digest
    assert digest == verdicts_digest_for(
        (sample.sample_id, sample.verdict.value)
        for sample in samples
        if sample.verdict is not None
    )
    assert pair_verdicts_digest_for([]) == verdicts_digest_for([])


# -- the evidence class is constituted as human (§86.1) -----------------------------------


def _machine_pair_verdict(store: SqliteStore, index: int, calibration_id: str) -> PairSample:
    """One row exactly as the §72 judge path writes it: same table, same write-once call,
    unrecognised, stamped with the reserved machine reader id."""
    sample = a_pair_sample(index)
    store.record_pair_sample(sample)
    store.record_pair_verdict(
        sample.sample_id,
        PairVerdict.PREFER_FIRST,
        at=TODAY,
        by=machine_reader_id(calibration_id),
        recognized=False,
        note=f"model judge under {calibration_id}",
    )
    return sample


def test_a_machine_written_row_can_never_denominate_a_preference_holdout(
    store: SqliteStore,
) -> None:
    """The laundering path, closed at the denominator. `EvidenceClass.PREFERENCE` is
    defined as "a human's blinded, position-swapped choice between two texts" and nothing
    enforced that: no source column, no CHECK, no predicate — while the §72 judge records
    through this same pair table with the licensing calibration id as its reader. So one
    human-anchored calibration licensing one judged tournament put the judge's own verdicts
    into the pool the NEXT preference calibration is measured against, and nothing counted
    them separately. Inert while the calibrations table is empty; live the day a paid batch
    is funded, which is the wrong day to discover it."""
    store.record_protocol(PROTOCOL)
    human = [a_pair_sample(index) for index in range(MIN_HOLDOUT)]
    for sample in human:
        store.record_pair_sample(sample)
        store.record_pair_verdict(
            sample.sample_id, PairVerdict.PREFER_FIRST, at=TODAY, by="reader",
            recognized=False,
        )
    assert len(analysable_judgments(store.pair_samples())) == MIN_HOLDOUT

    for index in range(MIN_HOLDOUT, MIN_HOLDOUT + 20):
        _machine_pair_verdict(store, index, "cal-judge-1")

    samples = store.pair_samples()
    assert len(samples) == MIN_HOLDOUT + 20, "the rows are kept, as recognised rows are"
    counted = analysable_judgments(samples)
    assert len(counted) == MIN_HOLDOUT, "20 machine verdicts inflated a human holdout"
    assert not any(is_machine_reader(sample.reader_id) for sample in counted)

    # And the arithmetic that consumes the count agrees: a calibration claiming a holdout
    # the machine rows would have covered is refused for its size, not quietly promoted.
    row = a_calibration(
        evidence_class=EvidenceClass.PREFERENCE,
        verdicts_digest=pair_verdicts_digest_for(samples),
        holdout_size=MIN_HOLDOUT + 20,
    )
    why = row.why_not_promotable(TODAY, row.verdicts_digest, answered=len(counted))
    assert why is not None
    assert (
        f"claims {MIN_HOLDOUT + 20} held-out judgment(s) against a store holding "
        f"{MIN_HOLDOUT} answered"
    ) in why


def test_machine_rows_still_stale_the_licence_that_bought_them(store: SqliteStore) -> None:
    """The half of §86.1 that is deliberately NOT changed. §72: "judge verdicts move the
    answered-verdict digest and stale the calibration that licensed them — one calibration
    buys roughly one judged tournament before re-measurement". That expiry is the price of
    the judge path, and the holdout fix must not quietly refund it: cutting machine rows
    from the digest as well as from the count would turn one licence into unlimited judged
    tournaments. Over-invalidation is the safe direction; under-invalidation buys free
    selection pressure with human evidence."""
    before = answered_pair_holdout(store)
    row = a_calibration(evidence_class=EvidenceClass.PREFERENCE, verdicts_digest=before)
    assert row.why_not_promotable(TODAY, before, answered=MIN_HOLDOUT) is None

    _machine_pair_verdict(store, MIN_HOLDOUT + 1, "cal-judge-1")
    after = pair_verdicts_digest_for(store.pair_samples())
    assert after != before, "a machine verdict must still move the staleness address"
    assert len(analysable_judgments(store.pair_samples())) == MIN_HOLDOUT, (
        "and must still not be counted: the digest and the denominator are two questions"
    )

    why = row.why_not_promotable(TODAY, after, answered=MIN_HOLDOUT)
    assert why is not None and "verdict set has changed" in why


# -- the operator surface -----------------------------------------------------------------


def _seed_book(db) -> None:
    store = SqliteStore.open(db)
    try:
        store.commit_revision(make_revision(), created_at="2026-08-13T00:00:00Z")
    finally:
        store.close()


def _excerpt_file(tmp_path, name: str, text: str):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_the_corpus_to_win_rate_round_trip(db, tmp_path, capsys) -> None:
    """Every verb once, in the order an operator would run them, with the bound at the
    end. All wins from two readers over the drawn pairs, so the pinned degenerate bound
    (1.0) is the expected print — the plumbing is under test here, not the statistics."""
    run(db, "init")
    _seed_book(db)
    for index, text in enumerate(
        ("The lantern held its breath while the toll was counted twice.",
         "Nobody crossed the ford after dark, and the ferryman knew why."),
    ):
        assert run(
            db, "corpus-add", str(_excerpt_file(tmp_path, f"excerpt-{index}.txt", text)),
            "--source", "test-serial", "--genre", "litrpg", "--era", "pre-2023",
        ) == EXIT_OK
        assert "exc-" in capsys.readouterr().out

    assert run(
        db, "protocol", "--frame", FRAME, "--tie-policy", "half_win", "--grain", "scene",
    ) == EXIT_OK
    declared = capsys.readouterr().out
    protocol_id = declared.split()[0]
    assert protocol_id == PROTOCOL.protocol_id, "the id derives from the declaration"

    assert run(
        db, "protocol", "--frame", FRAME, "--tie-policy", "half_win", "--grain", "scene",
    ) == EXIT_ATTENTION
    assert "already declared" in capsys.readouterr().err

    assert run(db, "pair-draw", "--protocol", protocol_id) == EXIT_OK
    drawn = capsys.readouterr().out
    assert "12 pair(s) drawn" in drawn, "6 scenes x 2 excerpts"
    assert "24 presented sample(s)" in drawn

    assert run(db, "pairs", "--pending", "--quiet") == EXIT_OK
    assert "24 sample(s), 24 awaiting a reader" in capsys.readouterr().out

    store = SqliteStore.open(db)
    try:
        pending = store.pair_samples(pending_only=True)
        by_pair: dict[str, list] = {}
        for sample in pending:
            by_pair.setdefault(sample.pair_id, []).append(sample)
        chosen = sorted(by_pair)[:2]
    finally:
        store.close()
    for pair_index, pair_id in enumerate(chosen):
        for sample in by_pair[pair_id]:
            system_first = sample.left_addr.startswith("rev:")
            verdict = "prefer_first" if system_first else "prefer_second"
            assert run(
                db, "pair-judge", sample.sample_id, verdict,
                "--reader", f"reader-{pair_index}", "--recognized", "no",
            ) == EXIT_OK
            capsys.readouterr()

    assert run(db, "win-rate", "--protocol", protocol_id) == EXIT_OK
    reported = capsys.readouterr().out
    assert "4 decisive" in reported
    assert "orientation 0: 2 decisive" in reported, "the positional split is reported"
    assert "orientation 1: 2 decisive" in reported
    assert "win rate at least 1.000 (observed 1.000)" in reported
    assert "the bound is descriptive" in reported, (
        "two reader clusters is under the descriptive floor, and the caveat says so"
    )
    assert "candidate-book count" in reported, "the §61 family correction travels with it"


def test_the_pair_queue_is_blinded(db, tmp_path, capsys) -> None:
    """cmd_audit's discipline, doubled: both texts, no provenance, no indication which
    side is which — a reader told which side is the system is not blind in any sense
    worth recording, and RevisionBench's 43-65% positional artifact is what contamination
    measures as."""
    run(db, "init")
    _seed_book(db)
    excerpt_text = "Nobody crossed the ford after dark, and the ferryman knew why."
    run(
        db, "corpus-add", str(_excerpt_file(tmp_path, "one.txt", excerpt_text)),
        "--source", "test-serial", "--genre", "litrpg", "--era", "pre-2023",
    )
    run(db, "protocol", "--frame", FRAME, "--tie-policy", "half_win", "--grain", "scene")
    run(db, "pair-draw", "--protocol", PROTOCOL.protocol_id)
    capsys.readouterr()

    assert run(db, "pairs", "--pending") == EXIT_OK
    out = capsys.readouterr().out
    assert "FIRST:" in out and "SECOND:" in out
    assert excerpt_text in out, "the prose itself is presented"
    assert "rev:" not in out and "exc:" not in out, "the addresses are provenance"
    assert "test-serial" not in out and "protocol" not in out
    assert "pair-judge" in out, "and the queue says how to answer"


def test_a_draw_needs_a_stored_protocol_and_scene_grain(db, capsys) -> None:
    """Required-no-default (§59): a pair drawn under no declared frame is a number whose
    claim gets chosen after the fact. And chapter grain is a recorded refusal, not an
    improvised assembly: production books hold no chapter nodes."""
    run(db, "init")
    _seed_book(db)
    capsys.readouterr()
    assert run(db, "pair-draw") == EXIT_FAULT
    assert "needs --protocol" in capsys.readouterr().err
    assert run(db, "pair-draw", "--protocol", "prot-nobody") == EXIT_FAULT
    assert "no protocol prot-nobody" in capsys.readouterr().err

    chapter_frame = "against serialized chapters, chapter grain"
    run(db, "protocol", "--frame", chapter_frame, "--tie-policy", "drop", "--grain", "chapter")
    capsys.readouterr()
    chapter_id = protocol_id_for(
        chapter_frame, tie_policy=TiePolicy.DROP, grain=PairGrain.CHAPTER
    )
    assert run(db, "pair-draw", "--protocol", chapter_id) == EXIT_FAULT
    assert "chapter-grain drawing is not built" in capsys.readouterr().err


def test_the_sibling_draw_runs_under_the_built_in_internal_protocol(db, capsys) -> None:
    """System-vs-system pairs select between candidates and never feed the win rate: the
    internal frame has no human side, and `win-rate` says so instead of counting them."""
    run(db, "init")
    _seed_book(db)
    capsys.readouterr()
    assert run(db, "pair-draw", "--siblings") == EXIT_OK
    drawn = capsys.readouterr().out
    assert "15 pair(s) drawn" in drawn, "6 scenes choose 2"
    assert INTERNAL_PROTOCOL.protocol_id in drawn

    store = SqliteStore.open(db)
    try:
        [sample, *_] = store.pair_samples(pending_only=True)
    finally:
        store.close()
    run(
        db, "pair-judge", sample.sample_id, "prefer_first",
        "--reader", "reader-a", "--recognized", "no",
    )
    capsys.readouterr()
    assert run(db, "win-rate", "--protocol", INTERNAL_PROTOCOL.protocol_id) == EXIT_OK
    reported = capsys.readouterr().out
    assert "1 system-vs-system (no human side)" in reported
    assert "no analysable judgment yet" in reported


def test_a_judgment_records_once_from_the_command_line(db, tmp_path, capsys) -> None:
    run(db, "init")
    _seed_book(db)
    run(
        db, "corpus-add", str(_excerpt_file(tmp_path, "one.txt", "A ford, unwatched.")),
        "--source", "test-serial", "--genre", "litrpg", "--era", "pre-2023",
    )
    run(db, "protocol", "--frame", FRAME, "--tie-policy", "half_win", "--grain", "scene")
    run(db, "pair-draw", "--protocol", PROTOCOL.protocol_id)
    store = SqliteStore.open(db)
    try:
        [sample, *_] = store.pair_samples(pending_only=True)
    finally:
        store.close()
    capsys.readouterr()

    assert run(
        db, "pair-judge", sample.sample_id, "tie", "--reader", " ", "--recognized", "yes",
    ) == EXIT_FAULT
    assert "cannot cluster" in capsys.readouterr().err, "an anonymous judgment is refused"
    assert run(
        db, "pair-judge", sample.sample_id, "tie",
        "--reader", "reader-a", "--recognized", "yes",
    ) == EXIT_OK
    assert "excluded from analysis" in capsys.readouterr().out
    assert run(
        db, "pair-judge", sample.sample_id, "prefer_first",
        "--reader", "reader-b", "--recognized", "no",
    ) == EXIT_ATTENTION
    assert "never overwritten" in capsys.readouterr().err

    assert run(db, "win-rate", "--protocol", PROTOCOL.protocol_id) == EXIT_OK
    assert "1 excluded by recognition" in capsys.readouterr().out


def test_export_and_import_round_trip_for_external_readers(db, tmp_path, capsys) -> None:
    """The paid-reader loop: blinded JSONL out, verdicts back in, at-least-once friendly —
    re-importing skips answered rows with a count, and a verdict for a sample this store
    never drew is refused rather than adopted."""
    run(db, "init")
    _seed_book(db)
    run(
        db, "corpus-add", str(_excerpt_file(tmp_path, "one.txt", "A ford, unwatched.")),
        "--source", "test-serial", "--genre", "litrpg", "--era", "pre-2023",
    )
    run(db, "protocol", "--frame", FRAME, "--tie-policy", "half_win", "--grain", "scene")
    run(db, "pair-draw", "--protocol", PROTOCOL.protocol_id)
    capsys.readouterr()

    export_path = tmp_path / "pairs.jsonl"
    assert run(db, "pair-export", str(export_path)) == EXIT_OK
    assert "12 pending sample(s) exported" in capsys.readouterr().out
    lines = [json.loads(line) for line in export_path.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 12
    for line in lines:
        assert set(line) == {
            "sample_id", "frame", "grain", "first", "second", "verdicts", "recognized",
        }
        assert line["frame"] == FRAME, "the frame travels with the pair; provenance does not"
        assert line["recognized"] is None, (
            "the recognition question ships unanswered, so reader tooling must answer it"
        )
        assert "rev:" not in json.dumps(line)

    verdicts_path = tmp_path / "verdicts.jsonl"
    answered = [
        {"sample_id": lines[0]["sample_id"], "verdict": "prefer_first", "reader": "paid-1",
         "recognized": False},
        {"sample_id": lines[1]["sample_id"], "verdict": "tie", "reader": "paid-2",
         "recognized": True, "note": "I have read this serial"},
    ]
    verdicts_path.write_text(
        "\n".join(json.dumps(entry) for entry in answered) + "\n", encoding="utf-8"
    )
    assert run(db, "pair-import", str(verdicts_path)) == EXIT_OK
    assert "2 verdict(s) recorded, 0 already answered" in capsys.readouterr().out

    assert run(db, "pair-import", str(verdicts_path)) == EXIT_OK
    assert "0 verdict(s) recorded, 2 already answered" in capsys.readouterr().out

    with_unknown = [
        *answered,
        {"sample_id": "pj-000000000000000000000000", "verdict": "tie", "reader": "paid-3",
         "recognized": False},
    ]
    verdicts_path.write_text(
        "\n".join(json.dumps(entry) for entry in with_unknown) + "\n", encoding="utf-8"
    )
    assert run(db, "pair-import", str(verdicts_path)) == EXIT_ATTENTION
    output = capsys.readouterr()
    assert "1 unknown sample id(s) refused" in output.out
    assert "never drew" in output.err

    store = SqliteStore.open(db)
    try:
        recognized_rows = [s for s in store.pair_samples() if s.recognized]
    finally:
        store.close()
    assert len(recognized_rows) == 1
    assert recognized_rows[0].note == "I have read this serial"


def test_an_import_without_an_explicit_recognition_answer_is_refused(
    db, tmp_path, capsys
) -> None:
    """The paid seam is where recognition bypass-by-omission would happen: reader tooling
    that never asked the question would default every row to "did not recognise", and §58
    measured exactly that familiarity swinging a score harder than real damage. So the
    export packet ships the slot null and import refuses anything that is not an explicit
    boolean — an absent answer is not "no"."""
    run(db, "init")
    _seed_book(db)
    run(
        db, "corpus-add", str(_excerpt_file(tmp_path, "one.txt", "A ford, unwatched.")),
        "--source", "test-serial", "--genre", "litrpg", "--era", "pre-2023",
    )
    run(db, "protocol", "--frame", FRAME, "--tie-policy", "half_win", "--grain", "scene")
    run(db, "pair-draw", "--protocol", PROTOCOL.protocol_id)
    store = SqliteStore.open(db)
    try:
        first, second, *_ = store.pair_samples(pending_only=True)
    finally:
        store.close()
    capsys.readouterr()

    verdicts_path = tmp_path / "verdicts.jsonl"
    entries = [
        # Absent entirely, and present but stringly typed: both are non-answers.
        {"sample_id": first.sample_id, "verdict": "prefer_first", "reader": "paid-1"},
        {"sample_id": second.sample_id, "verdict": "tie", "reader": "paid-1",
         "recognized": "false"},
    ]
    verdicts_path.write_text(
        "\n".join(json.dumps(entry) for entry in entries) + "\n", encoding="utf-8"
    )
    assert run(db, "pair-import", str(verdicts_path)) == EXIT_ATTENTION
    output = capsys.readouterr()
    assert "0 verdict(s) recorded" in output.out
    assert "2 refused without an explicit recognition answer" in output.out
    assert first.sample_id in output.err and second.sample_id in output.err, (
        "refused entries are named, so the reader tooling defect is findable"
    )
    store = SqliteStore.open(db)
    try:
        assert all(sample.pending for sample in store.pair_samples()), "nothing landed"
    finally:
        store.close()


def test_a_single_presented_order_is_refused_and_an_imbalance_is_warned(
    db, tmp_path, capsys
) -> None:
    """Position is recorded so it can be *checked*: for mixed pairs the canonical order is
    always human-first (the address prefixes sort that way), so a queue judged at one
    orientation only measures preference confounded with the RevisionBench positional
    artifact. All-one-orientation refuses the bound; worse than 2:1 warns and computes."""
    run(db, "init")
    _seed_book(db)
    run(
        db, "corpus-add", str(_excerpt_file(tmp_path, "one.txt", "A ford, unwatched.")),
        "--source", "test-serial", "--genre", "litrpg", "--era", "pre-2023",
    )
    run(db, "protocol", "--frame", FRAME, "--tie-policy", "half_win", "--grain", "scene")
    run(db, "pair-draw", "--protocol", PROTOCOL.protocol_id)
    store = SqliteStore.open(db)
    try:
        pending = store.pair_samples(pending_only=True)
    finally:
        store.close()
    by_orientation: dict[int, list[PairSample]] = {0: [], 1: []}
    for sample in pending:
        by_orientation[sample.orientation].append(sample)
    capsys.readouterr()

    for reader, sample in zip(("r0", "r1"), by_orientation[0][:2], strict=True):
        run(db, "pair-judge", sample.sample_id, "prefer_first",
            "--reader", reader, "--recognized", "no")
    capsys.readouterr()
    assert run(db, "win-rate", "--protocol", PROTOCOL.protocol_id) == EXIT_ATTENTION
    output = capsys.readouterr()
    assert "orientation 1: 0 decisive" in output.out
    assert "positional artifact" in output.err, "the refusal names what it guards against"

    run(db, "pair-judge", by_orientation[0][2].sample_id, "prefer_first",
        "--reader", "r0", "--recognized", "no")
    run(db, "pair-judge", by_orientation[1][0].sample_id, "prefer_first",
        "--reader", "r1", "--recognized", "no")
    capsys.readouterr()
    assert run(db, "win-rate", "--protocol", PROTOCOL.protocol_id) == EXIT_OK
    reported = capsys.readouterr().out
    assert "positional imbalance: 3 vs 1" in reported
    assert "win rate at least" in reported, "worse than 2:1 warns; it does not refuse"


def test_duplicate_reader_pair_orientation_rows_count_once_earliest_first(
    db, capsys
) -> None:
    """The sample identity supports a pre-assigned per-reader row beside the unassigned
    queue row; if one reader answers both, that is one opinion wearing two rows. Win rate
    keeps the earliest judged row per (pair, orientation, protocol, reader) — the blind
    first reading, the one this engine trusts everywhere else."""
    run(db, "init")
    store = SqliteStore.open(db)
    try:
        store.record_protocol(PROTOCOL)
        queue_row = a_pair_sample(1)
        assigned_row = PairSample(**{
            **_fields(queue_row),
            "sample_id": sample_id_for(
                queue_row.pair_id, 0, PROTOCOL.protocol_id, reader_id="paid-1"
            ),
        })
        swapped_row = a_pair_sample(1, orientation=1)
        for row in (queue_row, assigned_row, swapped_row):
            store.record_pair_sample(row)
        # The pre-assigned row is judged first (system preferred: the system member sorts
        # after the excerpt, so it is presented second at orientation 0); the queue row is
        # the same reader's later, contradictory second look.
        store.record_pair_verdict(
            assigned_row.sample_id, PairVerdict.PREFER_SECOND,
            at="2026-08-13T00:00:00Z", by="paid-1", recognized=False,
        )
        store.record_pair_verdict(
            queue_row.sample_id, PairVerdict.PREFER_FIRST,
            at="2026-08-14T00:00:00Z", by="paid-1", recognized=False,
        )
        store.record_pair_verdict(
            swapped_row.sample_id, PairVerdict.PREFER_FIRST,
            at="2026-08-14T00:00:00Z", by="paid-2", recognized=False,
        )
    finally:
        store.close()
    capsys.readouterr()

    # One pair cluster, so no bound — the counts are what is under test.
    assert run(db, "win-rate", "--protocol", PROTOCOL.protocol_id) == EXIT_ATTENTION
    output = capsys.readouterr()
    assert "2 decisive" in output.out, "three answered rows, two distinct opinions"
    assert "orientation 0: 1 decisive, observed 1.000" in output.out, (
        "and the earliest (blind) reading is the one kept"
    )
    assert "pair cluster" in output.err


def test_the_zero_verdict_world_degrades_to_informative_emptiness(db, capsys) -> None:
    """§61: the production loop must run with zero verdicts, and every preference verb on
    an empty store reports the gap instead of failing — emptiness is the honest measure,
    the same way the unread directive count is."""
    run(db, "init")
    capsys.readouterr()
    assert run(db, "pairs") == EXIT_OK
    assert "(0 sample(s), 0 awaiting a reader)" in capsys.readouterr().out
    assert run(db, "pair-export") == EXIT_OK
    assert "0 pending sample(s) exported" in capsys.readouterr().err

    run(db, "protocol", "--frame", FRAME, "--tie-policy", "half_win", "--grain", "scene")
    capsys.readouterr()
    assert run(db, "win-rate", "--protocol", PROTOCOL.protocol_id) == EXIT_OK
    assert "no analysable judgment yet" in capsys.readouterr().out
    assert run(db, "pair-draw", "--protocol", PROTOCOL.protocol_id) == EXIT_OK
    assert "no accepted scene holds prose yet" in capsys.readouterr().out

    _seed_book(db)
    assert run(db, "pair-draw", "--protocol", PROTOCOL.protocol_id) == EXIT_OK
    assert "the comparison corpus is empty" in capsys.readouterr().out

    assert run(db, "tick") == EXIT_OK, "and the production loop never noticed any of it"


def test_the_pairwise_engine_never_touches_a_provider(db, tmp_path, monkeypatch, capsys) -> None:
    """§61: preference evidence gates promotions, never ticks — and no provider is
    involved anywhere in the feature. Every verb runs with the registry constructor
    booby-trapped, so a future wiring that reached for a model would fail here first."""
    import litharness.cli as cli_module

    def explode(*args: object, **kwargs: object) -> object:
        raise AssertionError("the pairwise engine must not construct a provider registry")

    monkeypatch.setattr(cli_module, "build_default_registry", explode)
    run(db, "init")
    _seed_book(db)
    run(
        db, "corpus-add", str(_excerpt_file(tmp_path, "one.txt", "A ford, unwatched.")),
        "--source", "test-serial", "--genre", "litrpg", "--era", "pre-2023",
    )
    run(db, "protocol", "--frame", FRAME, "--tie-policy", "half_win", "--grain", "scene")
    run(db, "pair-draw", "--protocol", PROTOCOL.protocol_id)
    store = SqliteStore.open(db)
    try:
        [sample, *_] = store.pair_samples(pending_only=True)
    finally:
        store.close()
    assert run(
        db, "pair-judge", sample.sample_id, "tie", "--reader", "r", "--recognized", "no",
    ) == EXIT_OK
    assert run(db, "pairs", "--quiet") == EXIT_OK
    # One judged tie cannot clear the two-cluster floor, and the refusal itself must run
    # provider-free like everything else here.
    assert run(db, "win-rate", "--protocol", PROTOCOL.protocol_id) == EXIT_ATTENTION
    capsys.readouterr()


# -- store round trips --------------------------------------------------------------------


def test_an_excerpt_round_trips_with_its_matching_covariates(store: SqliteStore) -> None:
    """Source, genre and era are what make the comparison *matched* — §56.3 measured
    revealed labels selecting story size and era rather than prose — so the store must
    hand them back exactly, and the domain refuses an excerpt without them."""
    excerpt = ComparisonExcerpt.from_text(
        "The gate stood open. No one watched it.",
        source="test-serial", genre="litrpg", era="pre-2023", added_at=TODAY,
    )
    assert store.record_excerpt(excerpt)
    assert not store.record_excerpt(excerpt), "content-addressed: added twice is one row"
    [stored] = store.excerpts()
    assert stored == excerpt
    with pytest.raises(ValueError, match="matched"):
        ComparisonExcerpt.from_text(
            "Prose.", source=" ", genre="litrpg", era="pre-2023", added_at=TODAY
        )


def test_pending_pairs_are_the_measure_of_missing_judgment(store: SqliteStore) -> None:
    store.record_protocol(PROTOCOL)
    for index in range(3):
        store.record_pair_sample(a_pair_sample(index))
    assert len(store.pair_samples(pending_only=True)) == 3
    assert all(sample.pending for sample in store.pair_samples(pending_only=True))
    sample = store.pair_samples()[0]
    store.record_pair_verdict(
        sample.sample_id, PairVerdict.NOT_SURE, at=TODAY, by="reader", recognized=False
    )
    assert len(store.pair_samples(pending_only=True)) == 2, "abstention is an answer"
