"""§10.2 to §10.5: craft instrumentation, the standing audit, and the promotion bar.

**What these tests do not establish.** Nothing here shows that any metric predicts human
judgment, because nothing can: §10.6 recorded that eight of nine candidate proxies were
refuted and that §1a.3 items 1 to 4 are unreachable from defect fixtures, and §1a.4 states
that human judgment is the only ground truth. These tests establish the *spine* — that
measurements accumulate, that a sample is drawn without randomness, that a verdict is
recorded once and never overwritten, and that a craft metric cannot become a gate without
evidence attached. The evidence is the missing part and it is human work.

The tests worth reading are the ones that assert a **refusal**: `promoted_gate` raising on
thin evidence, `PolicyDecision` raising on an uncited blocking craft gate, and the audit
sampler producing the identical draw on a replay. Each is a way the bar could be passed
without being met.
"""

from __future__ import annotations

import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.domain.audit import BUCKETS, AuditSample, Verdict, bucket_for, draw, should_audit
from litharness.domain.calibration import (
    MIN_HOLDOUT,
    MIN_PRECISION,
    Calibration,
    Direction,
    NotPromotable,
    calibration_id_for,
    promoted_gate,
    verdicts_digest_for,
)
from litharness.domain.craft import (
    METRICS,
    craft_gates,
    dialogue_ratio,
    measure,
    opening_shape_repetition,
    sentence_length_variation,
    sentences,
    tricolon_rate,
)
from litharness.domain.policy import GateKind, Outcome, PolicyDecision, UntrustedVerdict
from tests.conftest import BOOK_ID, BRANCH_ID

TODAY = "2026-08-13"


@pytest.fixture
def store(tmp_path) -> SqliteStore:
    return SqliteStore.open(tmp_path / "litharness.db")


def a_calibration(**kwargs) -> Calibration:
    fields = {
        "metric_id": "craft.tricolon_rate.v0",
        "holdout_size": MIN_HOLDOUT,
        "precision": MIN_PRECISION,
        "threshold": 4.0,
        "direction": Direction.ABOVE,
        "verdicts_digest": "digest-1",
        "measured_at": "2026-08-01T00:00:00Z",
    }
    fields.update(kwargs)
    fields["calibration_id"] = calibration_id_for(
        str(fields["metric_id"]), float(fields["threshold"]), str(fields["verdicts_digest"])
    )
    return Calibration(**fields)  # type: ignore[arg-type]


# -- craft instrumentation (§10.2) -------------------------------------------------------


def test_every_metric_carries_the_reason_it_cannot_be_trusted() -> None:
    """`caveat` is a required field rather than a docstring, because a metric travelling
    without the reason it cannot be trusted is a metric that will be trusted."""
    for metric in measure("The room was cold. Rain fell. She waited a long time by the door."):
        assert metric.caveat
        assert "§1a.3" in metric.caveat or "§10.2" in metric.caveat


def test_no_metric_can_block(store: SqliteStore) -> None:
    """§10.4: "until then the Conductor treats it as annotation". `craft_gates` has no branch
    that could set `blocking`, so this cannot regress by a threshold being filled in."""
    gates = craft_gates(measure("A sentence. Another one, longer than the first by some way."))
    assert gates
    assert all(gate.gate is GateKind.CRAFT for gate in gates)
    assert not any(gate.blocking for gate in gates)
    assert all(gate.calibration_id is None for gate in gates)
    # And a decision carrying them constructs, which is the invariant that matters: the same
    # gates marked blocking would raise.
    PolicyDecision(decision_id="d", outcome=Outcome.ACCEPT, gates=gates)


def test_an_uncalibrated_craft_gate_cannot_be_made_blocking() -> None:
    """The structural bar, from the decision's end. It has held perfectly since slice 5 for
    the uninteresting reason that no craft gate existed; now one does."""
    advisory = craft_gates(measure("Short. Also short. Third."))[0]
    blocking = type(advisory)(**{**{f: getattr(advisory, f) for f in advisory.__slots__},
                                 "blocking": True})
    with pytest.raises(UntrustedVerdict, match="calibration"):
        PolicyDecision(decision_id="d", outcome=Outcome.ACCEPT, gates=(blocking,))


def test_metrics_are_deterministic() -> None:
    text = "She ran. The long road bent away east, and the light went with it."
    assert measure(text) == measure(text)


def test_sentence_variation_separates_uniform_prose_from_varied_prose() -> None:
    """The metric measures what it claims to, which is separate from whether that matters."""
    uniform = "He went out. She came in. They sat down. It grew dark. The fire died."
    varied = (
        "He went out. She came in through the side door with the rain still on her coat and "
        "did not look at him once. They sat. It grew dark."
    )
    assert sentence_length_variation(varied).value > sentence_length_variation(uniform).value


def test_the_tricolon_habit_is_detected_and_named() -> None:
    plain = "The room was cold and the window was open."
    habit = "The room was cold, dark, and silent. He was tired, hungry, and afraid."
    assert tricolon_rate(plain).value == 0.0
    assert tricolon_rate(habit).value > 0.0


def test_repeated_openings_are_detected() -> None:
    same = "The door opened. The door closed. The door opened again."
    mixed = "A door opened. Rain fell. She waited."
    assert opening_shape_repetition(same).value > opening_shape_repetition(mixed).value


def test_dialogue_ratio_sees_both_quote_styles() -> None:
    """Canonicalization is NFC and does not unify quotes, so a metric reading only straight
    quotes would report zero dialogue for every scene the fixtures actually contain."""
    straight = dialogue_ratio('He said, "I was in the city all week."')
    curly = dialogue_ratio("He said, “I was in the city all week.”")
    assert straight.value > 0.0
    assert curly.value > 0.0


def test_a_metric_survives_prose_it_cannot_parse() -> None:
    """Empty, whitespace and single-sentence text all reach these functions in normal
    operation — a gate refusal path is not a reason for a measurement to raise."""
    for text in ("", "   ", "One.", "No terminator at all"):
        assert len(measure(text)) == len(METRICS)


def test_sentence_splitting_is_crude_and_says_so() -> None:
    assert len(sentences("Mr. Vane died.")) == 2, "the docstring claims crude; keep it honest"


def test_metrics_are_stored_per_accepted_revision(store: SqliteStore) -> None:
    """A metric whose history begins on the day it is promoted has no held-out data to be
    promoted on, which is the whole reason these are logged before anything reads them."""
    metrics = measure("The room was cold, dark, and silent. She waited by the door.")
    assert store.record_craft_metrics("rev-1", "scene-1", metrics, measured_at=TODAY) == len(
        METRICS
    )
    # Immutable revision, so a re-measure can only produce the same numbers.
    assert store.record_craft_metrics("rev-1", "scene-1", metrics, measured_at=TODAY) == 0
    rows = store.craft_metrics(metric_id="craft.tricolon_rate.v0")
    assert [(r[0], r[1]) for r in rows] == [("rev-1", "scene-1")]


# -- the standing audit (§10.5) -----------------------------------------------------------


def test_the_draw_is_derived_from_content_not_random() -> None:
    """The load-bearing decision. A random sampler would make a replayed tick select a
    different scene — the one component in this store whose second run disagreed with its
    first — and would let a re-run quietly reshape which prose a human ever sees."""
    first = bucket_for("rev-1", "scene-3")
    assert first == bucket_for("rev-1", "scene-3")
    assert first != bucket_for("rev-1", "scene-4")
    assert first != bucket_for("rev-2", "scene-3")


def test_a_replayed_acceptance_draws_the_same_sample(store: SqliteStore) -> None:
    sample = draw(
        book_id=BOOK_ID, branch_id=BRANCH_ID, revision_id="rev-1",
        logical_id="scene-1", sampled_at=TODAY, rate=1.0,
    )
    assert sample is not None
    assert store.record_audit_sample(sample) is True
    assert store.record_audit_sample(sample) is False, "a human would be asked to read it twice"
    assert len(store.audit_samples()) == 1


def test_the_rate_is_honoured_across_the_bucket_space() -> None:
    """Not a distribution test — the hash's uniformity is SHA-256's problem. This asserts the
    two ends behave without a special case, because "audit everything" is what a director does
    for a new book and "audit nothing" is what a throwaway run wants."""
    assert should_audit("rev", "scene", rate=0.0) is False
    assert should_audit("rev", "scene", rate=1.0) is True


def test_the_sample_records_why_it_was_drawn() -> None:
    """"Why was this scene chosen" has to be arithmetic anyone can repeat, or a 5% claim is a
    number in a config file rather than a property of the run."""
    sample = draw(
        book_id=BOOK_ID, branch_id=BRANCH_ID, revision_id="rev-1",
        logical_id="scene-1", sampled_at=TODAY, rate=1.0,
    )
    assert sample is not None
    assert sample.bucket == bucket_for("rev-1", "scene-1")
    assert sample.rate == 1.0
    assert sample.bucket < BUCKETS


def test_a_verdict_is_recorded_once_and_never_overwritten(store: SqliteStore) -> None:
    """§10.3 wants blinded judgments. The first reading is the blind one; a reader who has
    since seen the provenance is a different instrument, so changing a mind is a new sample
    rather than an edit."""
    sample = draw(
        book_id=BOOK_ID, branch_id=BRANCH_ID, revision_id="rev-1",
        logical_id="scene-1", sampled_at=TODAY, rate=1.0,
    )
    assert sample is not None
    store.record_audit_sample(sample)

    assert store.record_verdict(sample.sample_id, Verdict.KEEP_READING, at=TODAY, by="reader")
    assert not store.record_verdict(sample.sample_id, Verdict.WOULD_STOP, at=TODAY, by="reader")
    [stored] = store.audit_samples()
    assert stored.verdict is Verdict.KEEP_READING


def test_abstention_is_a_real_answer(store: SqliteStore) -> None:
    """§10.4 asks for abstention to be measured. A scale with no way to decline pushes a
    reader into a verdict they do not hold, which calibrates against noise."""
    sample = draw(
        book_id=BOOK_ID, branch_id=BRANCH_ID, revision_id="rev-1",
        logical_id="scene-1", sampled_at=TODAY, rate=1.0,
    )
    assert sample is not None
    store.record_audit_sample(sample)
    assert store.record_verdict(sample.sample_id, Verdict.NOT_SURE, at=TODAY, by="reader")
    assert store.audit_counts() == {"not_sure": 1}


def test_pending_samples_are_the_measure_of_missing_judgment(store: SqliteStore) -> None:
    for index in range(3):
        sample = draw(
            book_id=BOOK_ID, branch_id=BRANCH_ID, revision_id=f"rev-{index}",
            logical_id="scene-1", sampled_at=TODAY, rate=1.0,
        )
        assert sample is not None
        store.record_audit_sample(sample)
    assert len(store.audit_samples(pending_only=True)) == 3
    assert all(item.pending for item in store.audit_samples(pending_only=True))


def test_the_readers_note_survives(store: SqliteStore) -> None:
    """The single most valuable column in the schema: §1a.3 items 1 to 4 are what a human
    notices and no proxy here reaches."""
    sample = AuditSample(
        sample_id="aud-1", book_id=BOOK_ID, branch_id=BRANCH_ID, revision_id="rev-1",
        logical_id="scene-1", sampled_at=TODAY, rate=1.0, bucket=1,
    )
    store.record_audit_sample(sample)
    store.record_verdict(
        "aud-1", Verdict.WOULD_STOP, at=TODAY, by="reader",
        note="nothing changes; it is all setup",
    )
    [stored] = store.audit_samples()
    assert stored.note == "nothing changes; it is all setup"


# -- the promotion bar (§10.4) --------------------------------------------------------------


def test_a_qualifying_calibration_produces_a_blocking_gate() -> None:
    gate = promoted_gate(a_calibration(), 6.0, today=TODAY)
    assert gate.blocking
    assert gate.gate is GateKind.CRAFT
    assert not gate.passed, "6.0 is above the 4.0 threshold and ABOVE is the failing side"
    assert gate.calibration_id
    # And the decision accepts it, which the same gate without a calibration would not.
    PolicyDecision(decision_id="d", outcome=Outcome.ACCEPT, gates=(gate,))


def test_the_direction_decides_which_side_fails() -> None:
    """A metric is not inherently directional and guessing inverts the gate silently, which
    produces a confidently backwards quality signal."""
    above = promoted_gate(a_calibration(direction=Direction.ABOVE), 6.0, today=TODAY)
    below = promoted_gate(a_calibration(direction=Direction.BELOW), 6.0, today=TODAY)
    assert not above.passed
    assert below.passed


def test_thin_evidence_cannot_promote() -> None:
    with pytest.raises(NotPromotable, match="precision"):
        promoted_gate(a_calibration(precision=MIN_PRECISION - 0.01), 6.0, today=TODAY)
    with pytest.raises(NotPromotable, match="held-out"):
        promoted_gate(a_calibration(holdout_size=MIN_HOLDOUT - 1), 6.0, today=TODAY)


def test_expired_evidence_cannot_promote() -> None:
    """§19's Trust clause requires *current* evidence. Output changes as the planner, the
    packet and the model change, so a threshold measured against last quarter's prose is a
    statement about prose the system no longer writes."""
    with pytest.raises(NotPromotable, match="expired"):
        promoted_gate(a_calibration(expires_at="2026-01-01"), 6.0, today=TODAY)


def test_a_changed_verdict_set_cannot_promote() -> None:
    """§10.5: audit disagreement re-opens calibration. A calibration is a claim about a
    specific set of judgments; if the set moved, the claim is about something else."""
    with pytest.raises(NotPromotable, match="verdict set has changed"):
        promoted_gate(a_calibration(), 6.0, today=TODAY, verdicts_digest="digest-2")


def test_an_expired_calibration_does_not_quietly_degrade_to_advisory() -> None:
    """It raises. A gate that silently stops blocking is worse than one that visibly cannot
    be built, because nothing downstream reports the difference."""
    with pytest.raises(NotPromotable):
        promoted_gate(a_calibration(expires_at="2026-01-01"), 6.0, today=TODAY)


def test_the_verdict_digest_is_order_independent() -> None:
    first = verdicts_digest_for([("a", "keep_reading"), ("b", "would_stop")])
    second = verdicts_digest_for([("b", "would_stop"), ("a", "keep_reading")])
    assert first == second
    assert first != verdicts_digest_for([("a", "would_stop"), ("b", "would_stop")])


def test_a_calibration_id_is_derived_from_what_was_measured() -> None:
    assert a_calibration().calibration_id == a_calibration().calibration_id
    assert a_calibration().calibration_id != a_calibration(threshold=9.0).calibration_id


def test_calibrations_round_trip_and_are_never_overwritten(store: SqliteStore) -> None:
    """A second measurement is a second row with its own evidence digest. Overwriting would
    delete the trail that makes "why did this threshold change" answerable."""
    first = a_calibration()
    assert store.record_calibration(first) is True
    assert store.record_calibration(first) is False
    store.record_calibration(a_calibration(threshold=9.0, measured_at="2026-08-05T00:00:00Z"))

    stored = store.calibrations(metric_id="craft.tricolon_rate.v0")
    assert len(stored) == 2
    assert stored[0].measured_at > stored[1].measured_at, "newest evidence first"
    assert stored[0].direction is Direction.ABOVE


def test_no_calibration_exists_yet_and_that_is_the_honest_state(store: SqliteStore) -> None:
    """The state §19.1 records as Quality: not started, blocked on §10.6's corpus. An empty
    table here is the measure of the gap, in the same way the unread directive count measures
    direction the planner cannot read."""
    assert store.calibrations() == []
    assert store.audit_samples() == []
