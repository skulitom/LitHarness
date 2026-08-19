"""The reader → writer loop: what a reader's verdict reaches, and what a judge may say.

**What these tests do not establish.** Nothing here shows that feedback improves prose,
because nothing can yet: `audit_samples` is at 0 rows, no reader has been paid, and the
ablation that would answer it is `research/quality-measurement/feedback_ablation.py`, whose
reader-side arm reads UNDECIDABLE by design. What they establish is that the machinery cannot
do the things it is forbidden to do.

The tests worth reading are the refusals — a judge speaking on an axis no reader pointed, a
reader answering across the measurement firewall, a located item spent twice, a human reader id
wearing the machine prefix, and a bar checked against its own operating characteristic before
anything is bought.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import judge_panel
from litharness.application.feedback_loop import (
    payload_fields,
    readings,
    record_provenance,
    resolve,
)
from litharness.application.planner import render_prompt
from litharness.cli import EXIT_FAULT, EXIT_OK, main
from litharness.domain import axes as axes_mod
from litharness.domain import discrimination as e6
from litharness.domain.axes import Pole
from litharness.domain.beats import SIX_BEAT, beats_for
from litharness.domain.candidates import SpanCandidate, candidate_id_for, sibling_samples
from litharness.domain.context import assemble
from litharness.domain.directions import (
    DIRECTION_BAR,
    MIN_CELLS,
    MIN_PAIR_CLUSTERS,
    MIN_READER_CLUSTERS,
    AxisDirection,
    WhyNot,
    attainability,
    observations_digest,
    read_direction,
)
from litharness.domain.feedback import (
    EMPTY,
    MAX_FEEDBACK_ITEMS,
    DifferenceStatus,
    DiscardReason,
    FeedbackItem,
    FeedbackSet,
    LocatedDifference,
    Role,
    compose,
    difference_id_for,
    satisfied,
)
from litharness.domain.generation import CompletionResult
from litharness.domain.pools import (
    Pool,
    PoolRegistration,
    PoolsNotRegistered,
    passage_pool,
    reader_pool,
    registration_id_for,
)
from litharness.domain.preference import (
    MACHINE_READER_PREFIX,
    ComparisonExcerpt,
    PairVerdict,
    excerpt_id_for,
)
from tests.conftest import BOOK_ID, BRANCH_ID, make_revision

RESEARCH = Path(__file__).parents[1] / "research" / "quality-measurement"
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

TODAY = "2026-08-19"

#: Two scenes differing on exactly one registered counter each, and nothing else. Built by
#: hand rather than generated, because "exactly one counter separates them" is the property
#: the direction path rests on and a generated fixture would make it accidental.
INTERIOR_HIGH = (
    "Rook counted the coins twice. He knew the lantern cost twenty.\n\n"
    "[STATUS] Rook - Level 2, HP 19/22"
)
INTERIOR_LOW = (
    "Rook counted the coins twice. The lantern cost twenty at the stall.\n\n"
    "[STATUS] Rook - Level 2, HP 19/22"
)
EM_LOW = (
    "Rook counted the coins twice-all of them. He knew the lantern cost twenty.\n\n"
    "[STATUS] Rook - Level 2, HP 19/22"
)
EM_HIGH = EM_LOW.replace("twice-all", "twice—all")
STAT_LOW = INTERIOR_HIGH.replace("Level 2, HP 19/22", "Level ?, HP ?/?")


def a_registration(reader_share: float = 0.5, passage_share: float = 0.5) -> PoolRegistration:
    return PoolRegistration(
        registration_id=registration_id_for(
            reader_salt="r", reader_steering_share=reader_share,
            passage_salt="p", passage_steering_share=passage_share,
        ),
        registered_at=TODAY,
        reader_salt="r",
        reader_steering_share=reader_share,
        passage_salt="p",
        passage_steering_share=passage_share,
    )


def readers_in(registration: PoolRegistration, pool: Pool, count: int) -> list[str]:
    found: list[str] = []
    index = 0
    while len(found) < count:
        candidate = f"who-{index}"
        if reader_pool(candidate, registration) is pool:
            found.append(candidate)
        index += 1
        assert index < 10_000
    return found


def a_direction(axis_id: str, preferred: Pole, digest: str = "d0") -> AxisDirection:
    return AxisDirection(
        axis_id=axis_id,
        preferred=preferred,
        high_win_rate=0.7 if preferred is Pole.HIGH else 0.3,
        lower_bound=0.61,
        alpha=0.05,
        cells=MIN_CELLS,
        readers=MIN_READER_CLUSTERS,
        pairs=MIN_PAIR_CLUSTERS,
        verdicts_digest=digest,
        established_at=TODAY,
    )


def a_candidate(text: str, index: int, *, logical_id: str = "scene-1") -> SpanCandidate:
    return SpanCandidate(
        candidate_id=candidate_id_for(
            text=text, statement=f"alt {index}", alternative_index=index,
            base_revision_id="rev-base", job_id="job-1",
        ),
        job_id="job-1",
        book_id=BOOK_ID,
        branch_id=BRANCH_ID,
        logical_id=logical_id,
        alternative_index=index,
        statement=f"alt {index}",
        text=text,
        base_revision_id="rev-base",
        plan_epoch=0,
        created_at=TODAY,
    )


def a_located(axis_id: str, *, span: str = "He knew the lantern cost twenty.") -> LocatedDifference:
    return LocatedDifference(
        difference_id=difference_id_for(
            batch_id="jb-1", axis_id=axis_id, high_address="exc:a", low_address="exc:b"
        ),
        batch_id="jb-1",
        book_id=BOOK_ID,
        branch_id=BRANCH_ID,
        logical_id="scene-1",
        axis_id=axis_id,
        high_address="exc:a",
        low_address="exc:b",
        span=span,
        sentence="Passage A names what the character knew; Passage B does not.",
        judge_id="judge:stub",
        pool=Pool.STEERING,
        created_at=TODAY,
    )


# -- the prerequisite: the laundering path, and the two holes the split reopened -----------


def test_a_human_reader_id_may_not_wear_the_machine_prefix(tmp_path, capsys) -> None:
    """`analysable_judgments` cuts `judge:` rows from every PREFERENCE denominator, so a
    *human* judgment wearing that prefix would be silently uncounted — and nothing owned the
    namespace in the other direction either. Separating the roles makes this worse rather than
    better: the whole point of the split is to run judges at volume, and volume is what turns
    an open path into a laundered pool."""
    db = tmp_path / "cli.db"
    assert main(["--database", str(db), "init"]) == EXIT_OK
    capsys.readouterr()
    assert main([
        "--database", str(db), "pair-judge", "pj-nothing", "tie",
        "--reader", f"{MACHINE_READER_PREFIX}someone", "--recognized", "no",
    ]) == EXIT_FAULT
    assert "reserved machine prefix" in capsys.readouterr().err


def test_an_import_declares_its_source_because_no_predicate_can_check_one(tmp_path) -> None:
    """Provenance of an imported row is a claim by the importer and nothing can verify it.
    Requiring the claim is the only honest thing this seam can do, and it is more than it did
    before: `--source` is required, so a bulk dump cannot arrive anonymously."""
    db = tmp_path / "cli.db"
    main(["--database", str(db), "init"])
    empty = tmp_path / "verdicts.jsonl"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(SystemExit):
        main(["--database", str(db), "pair-import", str(empty)])


# -- I1: the measurement firewall ---------------------------------------------------------


def test_nothing_routes_before_the_split_is_declared() -> None:
    """"Before the first verdict is routed" is only meaningful if nothing can be routed
    first, so the absence of a registration raises rather than defaulting. A default split
    would be a firewall nobody declared, which is §61 pre-registration (4)'s own failure: the
    frame IS the claim."""
    with pytest.raises(PoolsNotRegistered):
        reader_pool("alice", None)
    with pytest.raises(PoolsNotRegistered):
        passage_pool("rev-1", "scene-1", None)


def test_a_split_with_one_empty_side_is_refused() -> None:
    """At 1.0 §61 has no readers left and at 0.0 nothing can ever steer. Both are
    declarations that cannot do what they say — the failure §89's rulebook catalogues seven
    times, checked here before any spend rather than after."""
    for share in (0.0, 1.0):
        with pytest.raises(ValueError, match="not a split"):
            PoolRegistration(
                registration_id="pool-x", registered_at=TODAY, reader_salt="r",
                reader_steering_share=share, passage_salt="p", passage_steering_share=0.5,
            )


def test_the_pool_draw_is_content_derived_and_converges() -> None:
    """The audit draw's discipline inherited whole: a replayed assignment converges, an
    operator who dislikes one cannot re-roll it, and "why is this reader here" is arithmetic
    anyone can repeat."""
    registration = a_registration()
    assert reader_pool("alice", registration) is reader_pool("alice", registration)
    both = {reader_pool(f"r{i}", registration) for i in range(200)}
    assert both == {Pool.STEERING, Pool.MEASUREMENT}, "a split that never splits is not one"


def test_the_firewall_refuses_a_cross_pool_verdict(tmp_path, capsys) -> None:
    """§61's claim dies if the prose was shaped by the readers who later judge it, so the two
    pools are answered by disjoint sets of people — enforced at the write site, because once a
    steering reader has answered a measurement pair no later filter can un-shape the prose
    that reader's verdicts went on to influence."""
    db = tmp_path / "cli.db"
    main(["--database", str(db), "init"])
    store = SqliteStore.open(db)
    try:
        store.commit_revision(make_revision(), created_at=TODAY)
    finally:
        store.close()
    assert main([
        "--database", str(db), "pools", "--register", "--reader-salt", "r",
        "--passage-salt", "p",
    ]) == EXIT_OK
    excerpt = tmp_path / "one.txt"
    excerpt.write_text("Nobody crossed the ford after dark.", encoding="utf-8")
    main([
        "--database", str(db), "corpus-add", str(excerpt), "--source", "s",
        "--genre", "litrpg", "--era", "pre-2023",
    ])
    frame = "against median tier-matched serials, scene grain"
    main([
        "--database", str(db), "protocol", "--frame", frame,
        "--tie-policy", "drop", "--grain", "scene",
    ])
    store = SqliteStore.open(db)
    try:
        [protocol] = store.protocols()
    finally:
        store.close()
    main(["--database", str(db), "pair-draw", "--protocol", protocol.protocol_id])
    store = SqliteStore.open(db)
    try:
        registration = store.pool_registration()
        [sample, *_] = store.pair_samples(pending_only=True)
    finally:
        store.close()
    assert registration is not None
    wrong = readers_in(registration, Pool.STEERING, 1)[0]
    capsys.readouterr()
    assert main([
        "--database", str(db), "pair-judge", sample.sample_id, "prefer_first",
        "--reader", wrong, "--recognized", "no",
    ]) == EXIT_FAULT
    complaint = capsys.readouterr().err
    assert "steering pool and this pair is measurement" in complaint

    right = readers_in(registration, Pool.MEASUREMENT, 1)[0]
    assert main([
        "--database", str(db), "pair-judge", sample.sample_id, "prefer_first",
        "--reader", right, "--recognized", "no",
    ]) == EXIT_OK


def test_a_direction_counts_steering_readers_only() -> None:
    """Calibrating a judge on measurement-pool verdicts and then steering with that judge is
    the same contamination with one extra hop, so the filter is in `axis_observations` rather
    than in a caller that might forget."""
    registration = a_registration()
    steering = readers_in(registration, Pool.STEERING, 1)[0]
    measurement = readers_in(registration, Pool.MEASUREMENT, 1)[0]
    high, low = INTERIOR_HIGH, INTERIOR_LOW
    texts = {"exc:h": high, "exc:l": low}
    samples = _pair_rows(texts, [(steering, PairVerdict.PREFER_FIRST)])
    seen, _ = _observe(samples, texts, "interiority", registration)
    assert len(seen) == 1
    samples = _pair_rows(texts, [(measurement, PairVerdict.PREFER_FIRST)])
    seen, _ = _observe(samples, texts, "interiority", registration)
    assert seen == (), "a measurement-pool verdict may not establish a steering direction"


def _pair_rows(texts, answers):
    """Both orientations of one pair, answered by each `(reader, verdict)` in `answers`."""
    from litharness.domain.preference import PairSample, pair_bucket, pair_id_for, sample_id_for

    left, right = sorted(texts)
    pair_id = pair_id_for(left, right)
    rows = []
    for reader, verdict in answers:
        for orientation in (0, 1):
            first, second = (left, right) if orientation == 0 else (right, left)
            answered = (
                verdict
                if orientation == 0 or not verdict.decisive
                else (
                    PairVerdict.PREFER_SECOND
                    if verdict is PairVerdict.PREFER_FIRST
                    else PairVerdict.PREFER_FIRST
                )
            )
            rows.append(
                PairSample(
                    sample_id=sample_id_for(
                        pair_id, orientation, INTERNAL_PROTOCOL_ID
                    ) + f"-{reader}",
                    pair_id=pair_id,
                    orientation=orientation,
                    protocol_id=INTERNAL_PROTOCOL_ID,
                    left_addr=first,
                    right_addr=second,
                    grain=GRAIN,
                    book_id=BOOK_ID,
                    sampled_at=TODAY,
                    rate=1.0,
                    bucket=pair_bucket(pair_id),
                    reader_id=reader,
                    verdict=answered,
                    recognized=False,
                )
            )
    return rows


def _observe(samples, texts, axis_id, registration):
    from litharness.domain.directions import axis_observations

    return axis_observations(
        samples, texts, axis_id, reader_pool=lambda r: reader_pool(r, registration)
    )


from litharness.domain.preference import INTERNAL_PROTOCOL, PairGrain  # noqa: E402

INTERNAL_PROTOCOL_ID = INTERNAL_PROTOCOL.protocol_id
GRAIN = PairGrain.SCENE


# -- I7: the bar can do what it says ------------------------------------------------------


def test_the_direction_bar_is_attainable_and_its_power_is_measured() -> None:
    """I7's two halves. A bar no evidence can clear is a declaration that cannot do what it
    says; a bar that rejects a *true* effect most of the time is wrong in the other direction,
    which is what T0's own registered bar did to a good judge 82-100% of the time until its
    operating characteristic was measured."""
    report = attainability(size=False)
    assert report.attainable, "no win count at the declared shape clears the bar"
    assert report.smallest_clearing_k is not None
    assert 0 < report.smallest_clearing_k <= report.cells
    assert report.power[0.80] > report.power[0.55], "power must rise with the true rate"
    assert report.power[0.55] < 0.5, (
        "a bar that fires half the time on a barely-real effect is not a bar"
    )


def test_a_bar_passable_on_four_judgments_is_refused_by_the_cluster_floors() -> None:
    """`win_rate_lower_bound`'s own docstring records that at two readers by two pairs, all
    wins, the "97.5% lower bound" is 1.0 from four observations. The floors exist so that
    number can never be a direction."""
    registration = a_registration()
    two = readers_in(registration, Pool.STEERING, 2)
    texts = {"exc:h": INTERIOR_HIGH, "exc:l": INTERIOR_LOW}
    samples = _pair_rows(texts, [(who, PairVerdict.PREFER_FIRST) for who in two])
    reading = read_direction(
        "interiority", samples, texts,
        reader_pool=lambda r: reader_pool(r, registration), established_at=TODAY,
    )
    assert reading.direction is None
    assert reading.why_not in {WhyNot.TOO_FEW_CELLS, WhyNot.TOO_FEW_PAIRS}


def test_an_axis_with_no_evidence_says_so_by_name() -> None:
    """A named refusal, never a silent absence: five of §89's seven bad quantities were caught
    by a dry run printing *which* precondition was unmet."""
    reading = read_direction(
        "em_dash", [], {}, reader_pool=lambda r: Pool.STEERING, established_at=TODAY
    )
    assert reading.direction is None and reading.why_not is WhyNot.NO_EVIDENCE


def test_both_orientations_from_one_reader_are_one_cell() -> None:
    """§89 item 6 from the other side: a floor counted in comparisons would read a
    position-swapped pair as twice the evidence it is, and a reader who flips with position
    has said nothing."""
    registration = a_registration()
    who = readers_in(registration, Pool.STEERING, 1)[0]
    texts = {"exc:h": INTERIOR_HIGH, "exc:l": INTERIOR_LOW}
    observations, _ = _observe(
        _pair_rows(texts, [(who, PairVerdict.PREFER_FIRST)]), texts, "interiority", registration
    )
    assert len(observations) == 1, "two orientations, one reader, one decision"


# -- the reader path: verdicts to a direction ---------------------------------------------


def _direction_evidence(registration, axis_id, high_text, low_text, *, prefer_high: bool):
    """Enough steering cells, over enough readers and pairs, to clear every floor."""
    from litharness.domain.preference import PairSample, pair_bucket, pair_id_for, sample_id_for

    who = readers_in(registration, Pool.STEERING, MIN_READER_CLUSTERS)
    texts: dict[str, str] = {}
    rows: list[PairSample] = []
    for pair_index in range(MIN_PAIR_CLUSTERS + 4):
        # Distinct pairs by padding the same one-axis difference with a distinct prefix, so
        # the counter separation stays single-axis while the pair identities differ.
        prefix = "The road was long. " * (pair_index + 1)
        high = prefix + high_text
        low = prefix + low_text
        high_addr = f"exc:{excerpt_id_for(high)}"
        low_addr = f"exc:{excerpt_id_for(low)}"
        texts[high_addr] = high
        texts[low_addr] = low
        left, right = sorted((high_addr, low_addr))
        pair_id = pair_id_for(left, right)
        for reader in who:
            for orientation in (0, 1):
                first, second = (left, right) if orientation == 0 else (right, left)
                wanted = high_addr if prefer_high else low_addr
                verdict = (
                    PairVerdict.PREFER_FIRST if first == wanted else PairVerdict.PREFER_SECOND
                )
                rows.append(
                    PairSample(
                        sample_id=sample_id_for(pair_id, orientation, INTERNAL_PROTOCOL_ID),
                        pair_id=pair_id,
                        orientation=orientation,
                        protocol_id=INTERNAL_PROTOCOL_ID,
                        left_addr=first,
                        right_addr=second,
                        grain=GRAIN,
                        book_id=BOOK_ID,
                        sampled_at=TODAY,
                        rate=1.0,
                        bucket=pair_bucket(pair_id),
                        reader_id=reader,
                        verdict=verdict,
                        recognized=False,
                    )
                )
    return rows, texts


def test_a_reader_verdict_becomes_a_direction_on_a_named_axis() -> None:
    """The reader half, end to end and in the unit it is denominated in. The hypothesis is
    reported as confirmed or refuted against something written down first, which is the
    difference between a prediction and a rationalisation."""
    registration = a_registration()
    rows, texts = _direction_evidence(
        registration, "interiority", INTERIOR_HIGH, INTERIOR_LOW, prefer_high=True
    )
    reading = read_direction(
        "interiority", rows, texts,
        reader_pool=lambda r: reader_pool(r, registration), established_at=TODAY,
    )
    assert reading.direction is not None, reading.why_not
    assert reading.direction.preferred is Pole.HIGH
    assert reading.direction.lower_bound > DIRECTION_BAR
    assert reading.hypothesis_status == "confirmed"
    assert reading.direction.verdicts_digest == observations_digest(
        _observe(rows, texts, "interiority", registration)[0]
    )


def test_readers_preferring_the_low_side_read_low_and_refute_the_hypothesis() -> None:
    """Only one of the two one-sided checks can fire, so the pair is exactly one two-sided
    test — and the pre-registered guess is allowed to be wrong. §78.3's em-dash arm is VOID
    with its estimate leaning *toward* the mark, so at least one of the three may well be."""
    registration = a_registration()
    rows, texts = _direction_evidence(
        registration, "interiority", INTERIOR_HIGH, INTERIOR_LOW, prefer_high=False
    )
    reading = read_direction(
        "interiority", rows, texts,
        reader_pool=lambda r: reader_pool(r, registration), established_at=TODAY,
    )
    assert reading.direction is not None and reading.direction.preferred is Pole.LOW
    assert reading.hypothesis_status == "refuted"


# -- I2 and the composition rule ----------------------------------------------------------


def test_a_judge_may_not_speak_on_an_axis_no_reader_has_pointed() -> None:
    """The composition rule as a constructor precondition rather than a convention.
    Discrimination without direction cannot say which way to move."""
    composed = compose([], [a_located("interiority")], verdicts_digest="d0")
    assert composed.empty
    with pytest.raises(TypeError):
        FeedbackItem(role=Role.JUDGE)  # type: ignore[call-arg]


def test_a_judge_item_without_a_span_is_a_preference_and_is_refused() -> None:
    """A judge item is a *located* difference. Without a span it is a verdict, which is the
    frame this project has measured dead three times."""
    with pytest.raises(ValueError, match="measured dead three times"):
        FeedbackItem(role=Role.JUDGE, direction=a_direction("em_dash", Pole.LOW))


def test_no_unit_of_feedback_carries_a_score() -> None:
    """I2. There is no rating, no star, no 1-5 and no aggregate quality number anywhere in the
    payload or the rendered text — enforced by there being no field to put one in, and checked
    here because a number attached to a scene is one refactor away from a threshold."""
    item = FeedbackItem(role=Role.READER, direction=a_direction("interiority", Pole.HIGH))
    assert set(item.to_payload()) == {
        "role", "axis_id", "preferred_pole", "direction_digest",
        "direction_lower_bound", "span", "origin_id", "origin_logical_id",
    }
    rendered = FeedbackSet(items=(item,)).render()
    assert "0.61" not in rendered and "score" not in rendered.lower()
    assert axes_mod.AXES["interiority"].high_phrase in rendered


def test_an_empty_feedback_set_is_a_real_object_with_a_real_digest() -> None:
    """I4's negative case. "This scene had no feedback" and "nobody recorded whether this
    scene had feedback" are different facts, and a nullable column cannot tell them apart."""
    fields = payload_fields(EMPTY)
    assert fields["feedback"] == []
    assert isinstance(fields["feedback_digest"], str) and fields["feedback_digest"]
    assert fields["feedback_digest"] != FeedbackSet(
        items=(FeedbackItem(role=Role.READER, direction=a_direction("em_dash", Pole.LOW)),)
    ).digest


def test_the_cap_is_reported_rather_than_silent() -> None:
    """A bound coverage that says nothing reads as "covered everything" when it did not."""
    directions = [
        a_direction(axis_id, Pole.HIGH) for axis_id in axes_mod.AXES
    ]
    composed = compose(directions, [], verdicts_digest="d0", max_items=1)
    assert len(composed.items) == 1
    assert composed.dropped == len(directions) - 1
    assert len(axes_mod.AXES) == MAX_FEEDBACK_ITEMS


# -- retirement ----------------------------------------------------------------------------


def test_a_direction_whose_verdicts_moved_emits_nothing() -> None:
    """§72's expiry-on-use pattern moved one instrument over: evidence moving under a claim
    retires the claim, and re-deriving it silently would make the loop's own evidence
    unfalsifiable."""
    direction = a_direction("interiority", Pole.HIGH, digest="d0")
    assert compose([direction], [], verdicts_digest="d0").items
    assert compose([direction], [], verdicts_digest="d1").empty


def test_a_satisfied_axis_stops_locating_and_keeps_its_standing_sentence() -> None:
    """The mechanism that lets the system show improvement rather than repeating an
    instruction the prose already follows."""
    direction = a_direction("interiority", Pole.HIGH)
    recent = [INTERIOR_HIGH] * 5
    assert satisfied("interiority", direction, recent)
    composed = compose(
        [direction], [a_located("interiority")], verdicts_digest="d0",
        recent_scenes={BOOK_ID: recent},
    )
    assert composed.items and composed.items[0].role is Role.READER, (
        "the direction is still true; only the located item retires"
    )
    assert not satisfied("interiority", direction, recent[:2]), (
        "a book with too little prose is never satisfied — there is not enough of it to say"
    )


def test_a_located_item_is_spent_once(tmp_path) -> None:
    """One-shot, enforced at the store by the `status = 'minted'` clause rather than by the
    caller: feedback that only accumulates becomes an unreadable prompt."""
    store = SqliteStore.open(tmp_path / "s.db")
    try:
        difference = a_located("interiority")
        assert store.record_located_differences([difference]) == 1
        assert store.spend_located_difference(difference.difference_id)
        assert not store.spend_located_difference(difference.difference_id)
        [row] = store.located_differences()
        assert row.status is DifferenceStatus.SPENT
    finally:
        store.close()


# -- I3: nothing here can block ------------------------------------------------------------


LOOP_MODULES = (
    "src/litharness/domain/axes.py",
    "src/litharness/domain/directions.py",
    "src/litharness/domain/feedback.py",
    "src/litharness/domain/pools.py",
    "src/litharness/domain/discrimination.py",
    "src/litharness/application/feedback_loop.py",
    "src/litharness/application/judge_panel.py",
)


def test_no_module_on_the_feedback_path_can_construct_a_gate() -> None:
    """§10.4 stands, and a reader-derived gate is still a gate. Enforced by the absence of the
    *capability* rather than by the absence of a caller: a module that cannot name
    `GateOutcome` cannot grow one in a refactor."""
    root = Path(__file__).parents[1]
    offenders: list[str] = []
    for relative in LOOP_MODULES:
        source = (root / relative).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=relative)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.endswith("domain.policy")
            ):
                offenders.append(f"{relative} imports {node.module}")
            if isinstance(node, ast.Name) and node.id in {"GateOutcome", "PolicyDecision"}:
                offenders.append(f"{relative} names {node.id}")
    assert not offenders, "the feedback path can reach a gate:\n" + "\n".join(offenders)


# -- I5: the frozen prompt -----------------------------------------------------------------


def _premise_items():
    """The one plan item a packet may not omit: `assemble` refuses a book with no premise."""
    import litharness_contracts as lc

    return [
        lc.PlanItem(
            logical_id="plan-premise",
            kind=lc.PlanKind.PREMISE,
            text="A debtor works off an impossible debt along a System-governed road.",
            authority=lc.PlanAuthority.INTENDED,
        )
    ]


def test_feedback_reaches_the_system_message_and_nothing_else_moves() -> None:
    """The seam. Feedback is an instruction about *how* to write, so it sits beside
    `target_words` in the system message rather than in the packet, whose own contract is
    "established and may be relied on; do not contradict it"."""
    revision = make_revision()
    beat = beats_for(revision, SIX_BEAT)[0]
    packet = assemble(revision, beat.logical_id, plan_items=_premise_items())
    bare_system, bare_prompt = render_prompt(beat, book_title=None, packet=packet)
    item = FeedbackItem(role=Role.READER, direction=a_direction("interiority", Pole.HIGH))
    with_feedback, prompt = render_prompt(
        beat, book_title=None, packet=packet, feedback=FeedbackSet(items=(item,))
    )
    assert prompt == bare_prompt, "the packet and the instruction are untouched"
    assert with_feedback != bare_system
    assert axes_mod.AXES["interiority"].high_phrase in with_feedback
    empty_system, _ = render_prompt(beat, book_title=None, packet=packet, feedback=EMPTY)
    assert empty_system == bare_system, "an empty set renders nothing at all"


def test_provenance_is_recorded_for_a_scene_drafted_with_no_feedback(tmp_path) -> None:
    """I4, including the negative case: an explicit empty set, not a missing field."""
    store = SqliteStore.open(tmp_path / "s.db")
    try:
        assert record_provenance(
            store, revision_id="rev-1", logical_id="scene-1", job_id="job-1",
            payload=payload_fields(EMPTY), recorded_at=TODAY,
        )
        [row] = store.scene_feedback()
        assert row.items == () and row.digest == EMPTY.digest and row.empty
    finally:
        store.close()


def test_a_tick_records_provenance_for_every_drafted_scene(tmp_path, monkeypatch) -> None:
    """End to end through the real loop: `tick` drafts, and the scene that lands carries the
    feedback set it was drafted under — empty, because no direction exists, which is the
    normal state and is recorded rather than omitted."""
    monkeypatch.setenv("LITHARNESS_FAKE_PAD_CHARS", "400")
    db = tmp_path / "cli.db"
    assert main(["--database", str(db), "init"]) == EXIT_OK
    assert main([
        "--database", str(db), "new", "The Toll Road",
        "--premise", "A debtor works off an impossible debt.", "--scenes", "6",
    ]) == EXIT_OK
    assert main(["--database", str(db), "tick"]) in {EXIT_OK, 1}
    store = SqliteStore.open(db)
    try:
        rows = store.scene_feedback()
    finally:
        store.close()
    assert rows, "a drafted scene with no feedback still records an empty set"
    assert all(row.items == () for row in rows)
    assert all(row.digest == EMPTY.digest for row in rows)


# -- the judge path -------------------------------------------------------------------------


class _Judge:
    """A scripted E6 judge. Answers by request order so a batch's controls can be scripted."""

    def __init__(self, answers: list[str]) -> None:
        self.answers = list(answers)
        self.requests: list[object] = []

    def resolve(self, call_class: str = "generation"):  # type: ignore[no-untyped-def]
        class _N:
            name = "stub"

        class _R:
            provider = "stub"

        return _N(), _R()

    def reset_health(self) -> None:  # pragma: no cover
        return None

    def complete(self, request):  # type: ignore[no-untyped-def]
        self.requests.append(request)
        said = self.answers.pop(0) if self.answers else "The passages are identical."
        return (
            CompletionResult(
                text="{}", provider="stub", model="stub-v1",
                parsed={"difference": said}, schema_requested=True,
            ),
            None,
        )


def _judge_store(tmp_path, *, direction: AxisDirection | None, texts) -> SqliteStore:
    store = SqliteStore.open(tmp_path / "judge.db")
    registration = a_registration(passage_share=0.999)
    store.record_pool_registration(registration)
    for text in texts:
        store.record_excerpt(
            ComparisonExcerpt.from_text(
                text, source="plan-search", genre="litrpg", era="ours", added_at=TODAY
            )
        )
    if direction is not None:
        store.record_axis_direction(direction)
    return store


def test_the_judge_locates_a_difference_and_the_counter_decides_which_side(tmp_path) -> None:
    """The judge names which axis is salient; the deterministic layer decides which text is
    higher and where. So a judge cannot invert a direction — only fail to be useful."""
    texts = [INTERIOR_HIGH, INTERIOR_LOW]
    store = _judge_store(tmp_path, direction=None, texts=texts)
    try:
        from litharness.application.feedback_loop import current_digests

        direction = a_direction(
            "interiority", Pole.HIGH, digest=current_digests(store)["interiority"]
        )
        store.record_axis_direction(direction)
        candidates = [a_candidate(texts[0], 0), a_candidate(texts[1], 1)]
        registry = _Judge([
            "The passages are identical.",
            "Passage A uses single spaces after periods; B uses double spaces.",
            "Passage A reports what the character thought; Passage B reports only actions.",
            "Passage A reports what the character thought; Passage B reports only actions.",
        ])
        result = judge_panel.run_batch(
            registry, store, candidates, judge_id="judge:stub", created_at=TODAY
        )
        assert result.verdict is judge_panel.BatchVerdict.OK, result.verdict
        assert len(result.differences) == 1
        [difference] = result.differences
        assert difference.axis_id == "interiority"
        assert difference.high_address == candidates[0].address
        assert "knew" in difference.span
    finally:
        store.close()


def test_a_confabulating_placebo_voids_the_batch_and_keeps_the_sentence(tmp_path) -> None:
    """§89's placebo, moved in-loop. A judge that invents a prose difference between two
    byte-identical passages is not measuring the material — and its own sentence is the
    evidence, so the row is retained and marked rather than dropped."""
    texts = [INTERIOR_HIGH, INTERIOR_LOW]
    store = _judge_store(tmp_path, direction=None, texts=texts)
    try:
        from litharness.application.feedback_loop import current_digests

        store.record_axis_direction(
            a_direction("interiority", Pole.HIGH, digest=current_digests(store)["interiority"])
        )
        registry = _Judge([
            "Passage A shows what the character felt and Passage B does not.",
        ])
        result = judge_panel.run_batch(
            registry, store, [a_candidate(texts[0], 0), a_candidate(texts[1], 1)],
            judge_id="judge:stub", created_at=TODAY,
        )
        assert result.verdict is judge_panel.BatchVerdict.PLACEBO_CONFABULATED
        assert result.differences == ()
        assert result.discards and all(not row.batch_ok for row in result.discards)
        assert result.discards[0].reason is DiscardReason.CONTROL
    finally:
        store.close()


def test_the_judge_refuses_before_spending_when_no_axis_is_directed(tmp_path) -> None:
    """Discrimination without direction cannot say which way to move, so paying for it would
    be paying for half a signal. Refused before the first call, not after."""
    texts = [INTERIOR_HIGH, INTERIOR_LOW]
    store = _judge_store(tmp_path, direction=None, texts=texts)
    try:
        registry = _Judge([])
        result = judge_panel.run_batch(
            registry, store, [a_candidate(texts[0], 0), a_candidate(texts[1], 1)],
            judge_id="judge:stub", created_at=TODAY,
        )
        assert result.verdict is judge_panel.BatchVerdict.NO_DIRECTION
        assert registry.requests == [], "not one call was made"
    finally:
        store.close()


def test_an_unmatched_sentence_is_retained_verbatim_as_the_discovery_corpus(tmp_path) -> None:
    """Counting these is not enough. A sentence the matchers miss is a field report about a
    salient difference the axis registry cannot yet name — the same object §74's human read
    produced, from a channel that runs at volume — and a corpus not persisted from the first
    batch is gone."""
    texts = [INTERIOR_HIGH, INTERIOR_LOW]
    store = _judge_store(tmp_path, direction=None, texts=texts)
    try:
        from litharness.application.feedback_loop import current_digests

        store.record_axis_direction(
            a_direction("interiority", Pole.HIGH, digest=current_digests(store)["interiority"])
        )
        novel = "Passage A ends on a beat of rising tension where Passage B trails off."
        registry = _Judge([
            "The passages are identical.",
            "Passage A uses single spaces after periods; B uses double spaces.",
            novel,
            novel,
        ])
        result = judge_panel.run_batch(
            registry, store, [a_candidate(texts[0], 0), a_candidate(texts[1], 1)],
            judge_id="judge:stub", created_at=TODAY,
        )
        assert result.differences == ()
        assert result.unnamed == 2
        kept = [row for row in result.discards if row.reason is DiscardReason.UNMATCHED]
        assert len(kept) == 2
        assert all(row.sentence == novel for row in kept)
        assert {row.orientation for row in kept} == {0, 1}
        assert all(row.separating == "interiority" for row in kept)
        assert store.record_judge_discards(result.discards) == len(result.discards)
        assert store.record_judge_discards(result.discards) == 0, "content-addressed"
    finally:
        store.close()


# -- the frozen protocol --------------------------------------------------------------------


def test_the_judge_question_and_its_matchers_are_e6_verbatim() -> None:
    """A reworded question is a different protocol with no validity evidence behind it, and a
    matcher edited after reading responses is a rubric fitted to its own answers. §89's E6
    cleared 3 of 3 families with *these* strings."""
    import elicitation_study

    assert e6.E6_QUESTION == elicitation_study.E6_QUESTION
    assert e6.E6_SCHEMA == elicitation_study.E6_SCHEMA
    assert e6.AXIS_MATCHERS == elicitation_study.AXIS_MATCHERS
    assert e6.ANSWER_MAX_TOKENS == elicitation_study.ANSWER_MAX_TOKENS
    assert set(e6.FAMILY_FOR_AXIS.values()) == set(elicitation_study.AXIS_MATCHERS)


def test_the_counters_are_the_ones_b6_was_measured_with() -> None:
    """`domain` may not import `research`, so the three counters are restated — and a drifted
    counter would silently redefine what §89's numbers were about."""
    import authorship_tells
    import latent_fixtures

    for text in (INTERIOR_HIGH, INTERIOR_LOW, EM_HIGH, EM_LOW, STAT_LOW):
        reference = latent_fixtures.p0_features(text, steelman=True)
        assert axes_mod.system_digit_count(text) == reference["system_digit_count"]
        assert axes_mod.interior_per_1k(text) == pytest.approx(reference["interior_per_1k"])
        assert axes_mod.em_per_1k(text) == pytest.approx(reference["em_per_1k"])
        assert axes_mod.strip_system(text) == authorship_tells.strip_system(text)


def test_each_fixture_pair_separates_on_exactly_one_registered_axis() -> None:
    """The admission rule for direction evidence, checked on the fixtures the rest of this
    module rests on. Single-axis by *measurement* rather than by construction is weaker than a
    certified transform, and it is only worth anything if the measurement is actually made."""
    assert axes_mod.separating(INTERIOR_HIGH, INTERIOR_LOW) == ("interiority",)
    assert axes_mod.separating(EM_HIGH, EM_LOW) == ("em_dash",)
    assert axes_mod.separating(INTERIOR_HIGH, STAT_LOW) == ("stat_flatten",)
    assert axes_mod.higher("em_dash", EM_HIGH, EM_LOW) == EM_HIGH
    assert axes_mod.higher("interiority", INTERIOR_HIGH, INTERIOR_HIGH) is None


def test_the_controls_read_the_way_eighty_nine_measured_them() -> None:
    """The placebo clears on "identical" and the sham clears on formatting; both fail only on
    a *prose* axis that is not there. §89's own quoted responses are the fixtures."""
    assert e6.placebo_verdict(
        "The passages are identical; there is no discernible difference between them."
    ) is e6.ControlVerdict.CLEAR
    assert e6.sham_verdict(
        "Passage A uses single spaces after periods; Passage B uses double spaces."
    ) is e6.ControlVerdict.CLEAR
    assert e6.placebo_verdict(
        "Passage A gives the character's inner thoughts and Passage B does not."
    ) is e6.ControlVerdict.CONFABULATED
    assert e6.whitespace_sham("One. Two.") == "One.  Two."


def test_the_orientation_check_is_unreadable_before_it_can_bind() -> None:
    """E6 asks for no choice, so `positional_bias` would be a precondition that cannot fail.
    Below the floor this says UNREADABLE rather than passing — which is what §89 item 7 caught
    a withholding gate doing in the other direction."""
    assert e6.orientation_check([(0, True)] * 5).reading is e6.OrientationReading.UNREADABLE
    balanced = [(0, True)] * 20 + [(1, True)] * 20
    assert e6.orientation_check(balanced).reading is e6.OrientationReading.SYMMETRIC
    skewed = [(0, True)] * 20 + [(1, False)] * 20
    assert e6.orientation_check(skewed).reading is e6.OrientationReading.ASYMMETRIC


# -- the operator surface ---------------------------------------------------------------------


def test_the_directions_listing_names_every_axis_including_the_silent_ones(
    tmp_path, capsys
) -> None:
    """A listing that omitted the axes with no evidence would hide exactly the failures §89's
    rulebook says a dry run is for."""
    db = tmp_path / "cli.db"
    main(["--database", str(db), "init"])
    assert main(["--database", str(db), "directions"]) == EXIT_FAULT
    assert "no pool registration" in capsys.readouterr().err
    main(["--database", str(db), "pools", "--register"])
    capsys.readouterr()
    assert main(["--database", str(db), "directions"]) == EXIT_OK
    out = capsys.readouterr().out
    for axis_id in axes_mod.AXES:
        assert axis_id in out
    assert WhyNot.NO_EVIDENCE.value in out


def test_the_attainability_report_prints_the_bar_and_its_power(tmp_path, capsys) -> None:
    db = tmp_path / "cli.db"
    main(["--database", str(db), "init"])
    capsys.readouterr()
    assert main(["--database", str(db), "directions", "--attainability"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "smallest clearing k" in out and "power" in out
    assert "false failure" in out, "the report names the direction a bar is usually wrong in"


def test_feedback_reports_why_nothing_would_reach_the_prompt(tmp_path, capsys) -> None:
    db = tmp_path / "cli.db"
    main(["--database", str(db), "init"])
    capsys.readouterr()
    assert main([
        "--database", str(db), "feedback", "--book", BOOK_ID, "--branch", BRANCH_ID,
    ]) == EXIT_OK
    assert "no pool registration" in capsys.readouterr().out


def test_resolve_is_empty_and_costs_nothing_when_the_loop_is_not_running(tmp_path) -> None:
    """§61's autonomy constraint in one call: the production loop requires no human input, so
    an unfed loop returns an empty set and the book drafts exactly as it did before."""
    store = SqliteStore.open(tmp_path / "s.db")
    try:
        assert resolve(store, book_id=BOOK_ID, branch_id=BRANCH_ID, head=None).feedback.empty
        store.record_pool_registration(a_registration())
        assert resolve(store, book_id=BOOK_ID, branch_id=BRANCH_ID, head=None).feedback.empty
        assert all(row.direction is None for row in readings(store, at=TODAY))
    finally:
        store.close()


def test_the_sibling_draw_and_the_judge_share_one_contrast_surface() -> None:
    """The judge is built on the tournament rather than on a second comparison surface, and it
    never touches §61's pairing: spending the matched-published comparison on steering would
    destroy the measurement it exists for."""
    candidates = [a_candidate(INTERIOR_HIGH, 0), a_candidate(INTERIOR_LOW, 1)]
    samples = sibling_samples(candidates, sampled_at=TODAY)
    assert {sample.protocol_id for sample in samples} == {INTERNAL_PROTOCOL_ID}
    assert {candidate.address for candidate in candidates} == {
        sample.left_addr for sample in samples
    } | {sample.right_addr for sample in samples}
