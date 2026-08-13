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

import json

import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.handlers import _craft_ladder
from litharness.domain.audit import BUCKETS, AuditSample, Verdict, bucket_for, draw, should_audit
from litharness.domain.calibration import (
    MIN_FLAGGED,
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
    CraftMetric,
    craft_gates,
    dialogue_ratio,
    measure,
    opening_shape_repetition,
    sentence_length_variation,
    sentences,
    tricolon_rate,
)
from litharness.domain.patch import Veto
from litharness.domain.policy import (
    GateKind,
    Outcome,
    PolicyDecision,
    UntrustedVerdict,
    decide,
)
from tests.conftest import BOOK_ID, BRANCH_ID

TODAY = "2026-08-13"


@pytest.fixture
def store(tmp_path) -> SqliteStore:
    return SqliteStore.open(tmp_path / "litharness.db")


def a_calibration(**kwargs) -> Calibration:
    fields = {
        "metric_id": "craft.tricolon_rate.v0",
        "holdout_size": MIN_HOLDOUT,
        "flagged": MIN_FLAGGED,
        "precision": MIN_PRECISION,
        "threshold": 4.0,
        "direction": Direction.ABOVE,
        "verdicts_digest": "digest-1",
        "measured_at": "2026-08-01T00:00:00Z",
    }
    fields.update(kwargs)
    flagged = fields["flagged"]
    fields["calibration_id"] = calibration_id_for(
        str(fields["metric_id"]),
        float(fields["threshold"]),
        str(fields["verdicts_digest"]),
        direction=Direction(fields["direction"]),
        precision=float(fields["precision"]),
        holdout_size=int(fields["holdout_size"]),  # type: ignore[arg-type]
        flagged=None if flagged is None else int(flagged),  # type: ignore[arg-type]
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


def test_a_metric_that_fired_almost_never_cannot_promote() -> None:
    """The hole `MIN_HOLDOUT` alone leaves open, and it is not a corner case.

    Precision is computed over the *flagged* set. A metric that flags one scene in fifty and
    happens to be right scores precision 1.00 on a holdout of 50 — clearing both of the
    floors §10.4 established — while having demonstrated nothing at all. `recall` would have
    exposed it and is optional, so it cannot be what catches this.
    """
    with pytest.raises(NotPromotable, match="fired on 1 of"):
        promoted_gate(
            a_calibration(flagged=1, precision=1.0), 6.0, today=TODAY
        )
    # And the floor is where the arithmetic puts it, not near it.
    with pytest.raises(NotPromotable, match="fired on"):
        promoted_gate(a_calibration(flagged=MIN_FLAGGED - 1), 6.0, today=TODAY)
    promoted_gate(a_calibration(flagged=MIN_FLAGGED), 6.0, today=TODAY)


def test_an_unrecorded_flagged_count_cannot_promote() -> None:
    """`None` is not zero and not "fine": a calibration written before the count existed is
    indistinguishable from one that fired once, so it is refused rather than assumed. The
    same direction the ladder takes with an unclassified veto."""
    with pytest.raises(NotPromotable, match="does not record"):
        promoted_gate(a_calibration(flagged=None), 6.0, today=TODAY)


def test_more_flags_than_judgments_is_not_a_measurement_of_this_holdout() -> None:
    with pytest.raises(NotPromotable, match="more flags than judgments"):
        promoted_gate(
            a_calibration(flagged=MIN_HOLDOUT + 1, holdout_size=MIN_HOLDOUT), 6.0, today=TODAY
        )


def test_a_failing_promoted_gate_names_its_veto() -> None:
    """The fix at the source. `decide` acts on the veto, so a blocking gate that fails
    without one lands on "a blocking gate failed without naming a veto" and escalates —
    which sends a human every scene a craft gate stops."""
    failing = promoted_gate(a_calibration(), 6.0, today=TODAY)
    assert not failing.passed
    assert failing.vetoes == (Veto.CRAFT_BELOW_BAR,)

    passing = promoted_gate(a_calibration(), 1.0, today=TODAY)
    assert passing.passed
    assert passing.vetoes == (), "a gate that passed refuses nothing"


def test_a_failing_promoted_gate_parks_the_unit() -> None:
    """End to end through the ladder: the veto the gate names is classified, and the
    classification is PARK. This is the assertion that would fail if `CRAFT_BELOW_BAR` were
    ever quietly moved into `RETRYABLE`."""
    gate = promoted_gate(a_calibration(), 6.0, today=TODAY)
    outcome, reason = decide((gate,), job_id="j", attempt=1, max_attempts=3)
    assert outcome is Outcome.PARK
    assert "craft_below_bar" in (reason or "")


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


def test_a_corrected_measurement_is_a_different_calibration() -> None:
    """The measured numbers are part of the identity, and the bug that proves why: the id
    once ignored them, on the reading that a re-measurement moves the verdict digest. It
    does not have to — re-measuring the same metric at the same threshold over the same
    holdout is exactly what a correction is. The two rows collided, `record_calibration` is
    INSERT OR IGNORE, and the correction vanished while the first row kept gating."""
    original = a_calibration(precision=0.81, flagged=MIN_FLAGGED)
    corrected = a_calibration(precision=0.94, flagged=MIN_FLAGGED)
    assert original.verdicts_digest == corrected.verdicts_digest
    assert original.calibration_id != corrected.calibration_id


def test_a_correction_reaches_the_store_instead_of_being_ignored(store: SqliteStore) -> None:
    """The bite of the collision, at the layer that felt it."""
    assert store.record_calibration(a_calibration(precision=0.81)) is True
    assert store.record_calibration(a_calibration(precision=0.94)) is True
    assert {row.precision for row in store.calibrations()} == {0.81, 0.94}


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


def test_the_flagged_count_survives_the_round_trip(store: SqliteStore) -> None:
    """Migration 015's column. It is the denominator `precision` was computed over, so a
    store that dropped it would turn a checkable number back into an unreadable one."""
    store.record_calibration(a_calibration(flagged=23))
    assert store.calibrations()[0].flagged == 23


def test_a_calibration_written_before_the_column_existed_is_advisory(
    store: SqliteStore,
) -> None:
    """015 made the column nullable rather than backfilling it, because a row written before
    it existed genuinely does not know its flagged count. `None` round-trips as `None` and
    refuses promotion — the safe direction, and the reason the migration did not invent a
    default."""
    store.record_calibration(a_calibration(flagged=None))
    restored = store.calibrations()[0]
    assert restored.flagged is None
    assert restored.why_not_promotable(TODAY, restored.verdicts_digest) is not None


# -- the wired path (§10.2 step 7) ----------------------------------------------------------


def a_metric(value: float, metric_id: str = "craft.tricolon_rate.v0") -> CraftMetric:
    return CraftMetric(metric_id=metric_id, value=value, caveat="under test")


def test_an_empty_calibration_table_produces_no_blocking_gate(store: SqliteStore) -> None:
    """What makes wiring the promoted path safe to do before any evidence exists: with
    nothing recorded there is no branch that can construct a blocking gate, so turning it on
    does not turn anything on. The annotation is still produced, because §10.2 wants the
    measurement logged whether or not anything acts on it."""
    gates = _craft_ladder(store, (a_metric(6.0),), today=TODAY)
    assert len(gates) == 1
    assert not gates[0].blocking
    assert gates[0].calibration_id is None


def test_a_recorded_calibration_gates_the_metric_it_names(store: SqliteStore) -> None:
    store.record_calibration(a_calibration(verdicts_digest=verdicts_digest_for([])))
    gates = _craft_ladder(store, (a_metric(6.0),), today=TODAY)
    assert len(gates) == 1, "one gate per metric — the promoted one replaces its annotation"
    assert gates[0].blocking and not gates[0].passed
    assert gates[0].vetoes == (Veto.CRAFT_BELOW_BAR,)


def test_a_calibration_for_a_metric_this_draft_did_not_measure_is_skipped(
    store: SqliteStore,
) -> None:
    store.record_calibration(a_calibration(verdicts_digest=verdicts_digest_for([])))
    other = (a_metric(6.0, "craft.dialogue_ratio.v0"),)
    [gate] = _craft_ladder(store, other, today=TODAY)
    assert not gate.blocking, "a calibration for another metric cannot gate this one"


def test_stale_evidence_falls_back_to_annotation_rather_than_failing_the_job(
    store: SqliteStore,
) -> None:
    """§10.5 re-opens calibration when the verdict set moves; it does not stop the book.

    `NotPromotable` is swallowed per metric here rather than raised, because raising would
    turn "the evidence about prose quality went stale" into "this scene cannot be drafted at
    all". The metric falls back to the annotation `craft_gates` already produced, and
    `litharness calibrations` prints the reason.
    """
    store.record_calibration(a_calibration(expires_at="2026-01-01"))
    [gate] = _craft_ladder(store, (a_metric(6.0),), today=TODAY)
    assert not gate.blocking
    # And never silently. A gate that quietly stops blocking is the failure `promoted_gate`
    # refuses by name, so the reason travels on the annotation into the decision record.
    assert "not blocking" in (gate.detail or "")
    assert "expired" in (gate.detail or "")


def test_only_the_newest_measurement_for_a_metric_gates(store: SqliteStore) -> None:
    """A superseded measurement is history, not a second gate. Two rows for one metric would
    otherwise refuse a scene twice for the same reason under two thresholds."""
    digest = verdicts_digest_for([])
    store.record_calibration(
        a_calibration(threshold=4.0, verdicts_digest=digest, measured_at="2026-08-01T00:00:00Z")
    )
    store.record_calibration(
        a_calibration(threshold=99.0, verdicts_digest=digest, measured_at="2026-08-05T00:00:00Z")
    )
    gates = _craft_ladder(store, (a_metric(6.0),), today=TODAY)
    assert len(gates) == 1
    assert gates[0].passed, "6.0 is below the newest threshold of 99.0"


def test_no_calibration_exists_yet_and_that_is_the_honest_state(store: SqliteStore) -> None:
    """The state §19.1 records as Quality: not started, blocked on §10.6's corpus. An empty
    table here is the measure of the gap, in the same way the unread directive count measures
    direction the planner cannot read."""
    assert store.calibrations() == []
    assert store.audit_samples() == []


# -- the published-LitRPG reference profile (§10.6, partially) ----------------------------


def test_the_profile_exists_and_names_what_it_is_not() -> None:
    """The profile is evidence, and evidence that overstates itself is worse than none. It
    carries its own disclaimer so a reader who opens the JSON and not the docstring still
    learns that the dataset's five score columns are null and that engagement is not a label.
    """
    from litharness.domain.craft import load_profile

    profile = load_profile()
    assert profile, "plan/craft-profile.json is missing; tools/build_craft_profile.py builds it"
    assert profile["source"]["dataset"] == "OmniAICreator/RoyalRoad-1.61M"
    assert profile["source"]["genre_tag"] == "LitRPG"
    assert "null" in profile["disclaimer"]
    assert "never used as a label" in profile["disclaimer"]


def test_no_prose_is_stored_in_the_profile() -> None:
    """The corpus is other people's copyrighted fiction. Only statistics are committed, which
    is what lets the profile live in a public repository at all."""
    from litharness.domain.craft import PROFILE_PATH

    raw = PROFILE_PATH.read_text(encoding="utf-8")
    assert len(raw) < 100_000, "a profile this large is storing more than statistics"
    assert "text" not in json.loads(raw)["cohorts"]["human_pre_llm"]


def test_every_metric_was_measured_against_the_corpus() -> None:
    """A metric added later without being profiled would silently have no anchor and no
    separation number — it would look measured because its neighbours are."""
    from litharness.domain.craft import METRICS, load_profile

    profile = load_profile()
    ids = {fn("x. y.").metric_id for fn in METRICS}
    assert set(profile["separation"]) == ids
    assert set(profile["cohorts"]["human_pre_llm"]["metrics"]) == ids


def test_all_four_metrics_failed_to_separate_declared_ai_from_undeclared() -> None:
    """**The measured refutation, pinned so it cannot be quietly forgotten.**

    Holding the era fixed, every metric lands within 0.06 of chance. If a future change makes
    one of them separate, this test fails and the claim in `domain/craft.py` has to be
    rewritten — which is the point: the docstring says these are not AI-tell detectors, and a
    docstring is what rots.
    """
    from litharness.domain.craft import load_profile

    for metric_id, seps in load_profile()["separation"].items():
        auc = seps["declared_ai_vs_undeclared_2025"]
        assert abs(auc - 0.5) < 0.06, f"{metric_id} now separates at {auc}; update the claim"


def test_the_era_control_catches_the_confound() -> None:
    """`tricolon_rate` looks like a result against pre-2023 prose (0.63) until the control is
    read: undeclared 2025 chapters separate almost as strongly (0.61). The metric is detecting
    the year. This asserts the control still shows it, because the control is the only reason
    that number was not reported as a success."""
    from litharness.domain.craft import load_profile

    seps = load_profile()["separation"]["craft.tricolon_rate.v0"]
    era_gap = abs(
        seps["declared_ai_2025_vs_human_pre_llm"] - seps["undeclared_2025_vs_human_pre_llm"]
    )
    assert era_gap < 0.1, "the era comparisons diverged; the confound analysis needs redoing"


def test_a_scene_can_be_placed_against_published_litrpg() -> None:
    """What survives the refutation: the metrics do not sort machine from human, but an
    outlier against the published distribution is still a fact."""
    from litharness.domain.craft import measure, percentile_of

    tell = (
        "The room was cold, dark, and silent. He was tired, hungry, and afraid. "
        "She was calm, sure, and ready."
    )
    metrics = {m.metric_id: m for m in measure(tell)}
    assert percentile_of(metrics["craft.tricolon_rate.v0"]) == 0.99


def test_a_checkout_without_a_profile_still_works() -> None:
    """The profile is built by an offline tool against a 12.5GB corpus behind an optional
    extra. A checkout that has not run it must still draft, gate and tick."""
    from litharness.domain.craft import measure, percentile_of

    metric = measure("A sentence here. And another one, rather longer than that.")[0]
    assert percentile_of(metric, profile={}) is None


def test_a_corrected_direction_is_a_different_calibration(store: SqliteStore) -> None:
    """`direction` was the field the first correction left out, and it is the worst one to
    leave out: `Direction`'s own docstring says guessing it "inverts the gate silently".
    A row recorded with the wrong direction is exactly the one someone re-records to fix,
    and with direction outside the id the fix collides with the inverted original, is
    dropped by INSERT OR IGNORE, and leaves the backwards gate live."""
    inverted = a_calibration(direction=Direction.BELOW)
    corrected = a_calibration(direction=Direction.ABOVE)
    assert inverted.calibration_id != corrected.calibration_id
    assert store.record_calibration(inverted) is True
    assert store.record_calibration(corrected) is True
    assert {row.direction for row in store.calibrations()} == {
        Direction.BELOW,
        Direction.ABOVE,
    }


def test_a_promoted_metric_reports_once_not_twice(store: SqliteStore) -> None:
    """Two gates for one measurement is a contradiction on the record. An earlier version
    appended the promoted gate beside the advisory one, so a refused scene's decision carried
    the same `rule_or_critic_id` twice — `passed=True, blocking=False` and
    `passed=False, blocking=True` — and `decision_id_for` hashed both. An audit asking what
    the craft ladder said got two contradictory answers about one number."""
    store.record_calibration(a_calibration(verdicts_digest=verdicts_digest_for([])))
    gates = _craft_ladder(
        store,
        (a_metric(6.0), a_metric(0.1, "craft.dialogue_ratio.v0")),
        today=TODAY,
    )
    ids = [gate.rule_or_critic_id for gate in gates]
    assert len(ids) == len(set(ids)), "one gate per metric"
    assert {g.rule_or_critic_id for g in gates if g.blocking} == {"craft.tricolon_rate.v0"}


def test_one_new_verdict_re_opens_every_calibration_and_says_so(store: SqliteStore) -> None:
    """The consequence worth knowing before the first promotion, because it is invisible
    otherwise: `verdicts_digest` covers *every* answered audit sample, so a single new
    `judge` verdict makes every recorded calibration stale at once. That is correct under
    §10.5 — audit disagreement re-opens calibration — and it must be legible when it
    happens, which is what the annotation's detail is for."""
    store.record_calibration(a_calibration(verdicts_digest=verdicts_digest_for([])))
    assert _craft_ladder(store, (a_metric(6.0),), today=TODAY)[0].blocking

    # Through the real path: `record_audit_sample` deliberately stores no verdict — the
    # first reading is the blind one — so a judgment only ever enters via `record_verdict`.
    store.record_audit_sample(
        AuditSample(
            sample_id="aud-later", book_id=BOOK_ID, branch_id=BRANCH_ID,
            revision_id="rev-9", logical_id="scene-9", sampled_at=TODAY, bucket=1, rate=1.0,
        )
    )
    assert store.record_verdict(
        "aud-later", Verdict.KEEP_READING, at=TODAY, by="the director"
    )
    [gate] = _craft_ladder(store, (a_metric(6.0),), today=TODAY)
    assert not gate.blocking, "the gate stops blocking"
    assert "verdict set has changed" in (gate.detail or ""), "and the record says why"
