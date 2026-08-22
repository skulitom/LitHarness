"""The Budgeted Continuation Reader's pre-registration and its refusals, checked without calls.

§94's instrument is behavioural, so almost everything that could go wrong with it goes wrong
silently: a chunker that lets length masquerade as interest, a control that certifies the
absence of a bias from four observations, a seating that grants itself on arms it never ran.
None of those produce an error — they produce a number. So this file pins the properties that
would otherwise only be visible by reading a result file carefully:

1. **The prompt is byte-frozen and the registration is content-addressed.** T0's A4 put roughly
   fourteen points of a verdict on wording; a reworded prompt is a different instrument with no
   evidence, and the digest is what makes an edit visible as a changed number rather than as an
   unchanged-looking run.
2. **Every control fails in the direction that matters.** An equivalence check is only a control
   if thin data fails it, and `--selftest` asserts the operating characteristic at the declared
   floor rather than asserting that a band exists.
3. **A model is never seated on arms that did not run.** V1 and D2 have no substrate in this
   repository, and a battery reporting four of six with two absences unmarked would read as a
   seated model — §89's no-silent-caps rail.
"""

from __future__ import annotations

import pytest

bcr = pytest.importorskip(
    "bcr",
    reason="research module; imported by path, skipped where research/ is unavailable",
)


def test_the_instruments_own_selftest_passes() -> None:
    """The free leg that must pass before any call is bought, run here so CI owns it too."""
    assert bcr.selftest() == 0


def test_the_reader_prompt_is_byte_frozen() -> None:
    """A reworded prompt is a different instrument with no evidence behind it.

    Pinned literally rather than by digest so a diff of this file shows what changed. The
    properties being pinned are the ones the design argues for: forced spending, no option to
    stop, and no evaluation framing anywhere — nothing that suggests either text is under
    assessment or that one of them is supposed to win.
    """
    assert bcr.SYSTEM == (
        "You are reading for pleasure. You have two books on the go and a fixed amount of "
        "reading time left, measured in sections.\n"
        "Each time you are asked, choose which book to read the next section of. You must "
        "spend every section of reading time; there is no option to stop.\n"
        'Answer with a single JSON object naming the book you continue: {"continue": "A"} or '
        '{"continue": "B"}.'
    )
    assert bcr.FETCH_TURN == (
        "{left} section(s) of reading time left. Which book do you continue?"
    )
    lowered = bcr.SYSTEM.lower()
    for word in ("better", "prefer", "quality", "rate", "judge", "evaluate", "which is"):
        assert word not in lowered, f"the prompt frames an evaluation with {word!r}"


def test_the_registration_digest_moves_with_the_registration() -> None:
    """An edited constant must be visible as a changed number in every result file."""
    before = bcr.registration_digest()
    original = bcr.PRE_REGISTRATION["budget"]
    bcr.PRE_REGISTRATION["budget"] = original + 1
    try:
        assert bcr.registration_digest() != before
    finally:
        bcr.PRE_REGISTRATION["budget"] = original
    assert bcr.registration_digest() == before


def test_a_text_the_budget_could_exhaust_is_not_a_shelf_member() -> None:
    """The substrate check that produced §94.3's finding, as a refusal rather than a note."""
    text, _ = bcr.load_text(None)
    assert bcr.Shelf("ok", "T", text, text).fault() is None
    fault = bcr.Shelf("short", "T", "one paragraph.", text).fault()
    assert fault is not None and "budget" in fault


def test_a_session_with_an_unanswered_fetch_is_not_scored() -> None:
    """An unanswered fetch is not an allocation, and folding it into one would put transport
    failures into a behavioural distribution — `_is_transport_failure`'s rule, one level up."""
    partial = bcr.Session("s", "T", "m", 0, 0, 0.0, ("A", "B"), unanswered=1)
    assert not partial.scorable
    whole = bcr.Session("s", "T", "m", 0, 0, 0.0, tuple("ABABABABABAB"))
    assert whole.scorable and whole.target_share == 0.5


def test_orientation_moves_the_target_and_not_the_slot() -> None:
    """Position-swapped replicates are the whole reason a slot share is readable at all."""
    spent = tuple("AAAAAAAAAAAA")
    assert bcr.Session("s", "T", "m", 0, 0, 0.0, spent).target_share == 1.0
    assert bcr.Session("s", "T", "m", 1, 0, 0.0, spent).target_share == 0.0
    assert bcr.Session("s", "T", "m", 1, 0, 0.0, spent).slot_a_share == 1.0


def test_a_control_cannot_pass_on_thin_data() -> None:
    """The direction a control has to fail in.

    Two sessions that both allocate exactly evenly produce a bootstrap whose every resample is
    0.5, so a zero-width interval sits inside any band. That is §85's zero-width defect in an
    equivalence test, where it is worse than in a bound: a bound with no width over-claims a
    direction, and this would certify the absence of one.
    """
    assert bcr.equivalence([("shelf-0", 0.5), ("shelf-1", 0.5)])["verdict"] == "UNREADABLE"
    assert bcr.equivalence([("shelf-0", 0.5)])["verdict"] == "UNREADABLE"
    balanced = [(f"shelf-{index % 8}", 0.5) for index in range(48)]
    assert bcr.equivalence(balanced)["verdict"] == "PASS"
    assert bcr.equivalence([(f"shelf-{i % 8}", 0.95) for i in range(48)])["verdict"] == "FAIL"


def test_a_descriptive_interval_is_labelled_and_cannot_seat() -> None:
    """`DESCRIPTIVE_CLUSTER_FLOOR`'s lesson: below it a percentile bootstrap has not earned its
    level, so the interval is printed and is not evidence anybody may be seated on."""
    thin = bcr.equivalence([(f"shelf-{index % 3}", 0.5) for index in range(48)])
    assert thin["verdict"] == "PASS" and thin["calibrated"] is False


def test_no_model_is_seated_on_arms_that_did_not_run() -> None:
    """§89's no-silent-caps rail: an absence is reported, never counted as a pass."""
    seating = bcr.seat(bcr.Run(), model="none")
    assert seating["seated"] is False
    assert seating["controls"]["v1_variance"]["verdict"] == "NOT RUN"
    assert "v1_variance" in seating["unseated_by"]
    battery = bcr.battery(bcr.Run(), model="none")
    assert battery["D2_transplant"]["verdict"] == "NOT RUN"
    assert "kill" in battery["D2_transplant"]["consequence"]


def test_a_strict_alternator_fails_seating_while_passing_every_other_control() -> None:
    """P5, and the reason it exists is the first six sessions this instrument ever ran.

    All six came back `ABABABABABAB` on `qwen3:14b` — three shelves, both orientations. A strict
    alternator allocates exactly half its budget to each side of every shelf, so the placebo,
    both shams and the positional check all pass *perfectly* and none of them measures anything.
    That is the 195/196 constant function wearing a budget, and the whole seating turns on
    catching it.
    """
    alternating = bcr.Run(
        sessions=[
            bcr.Session(f"shelf-{index % 3}", "P1", "m", index % 2, index // 2, 0.0,
                        tuple("ABABABABABAB"))
            for index in range(24)
        ]
    )
    seating = bcr.seat(alternating, model="alternator")
    assert seating["controls"]["p1_placebo"]["verdict"] == "PASS", (
        "the placebo passes a strict alternator, which is exactly the problem"
    )
    assert seating["controls"]["p5_non_degenerate"]["verdict"] == "FAIL"
    assert seating["controls"]["p5_non_degenerate"]["mean_switch_rate"] == 1.0
    assert seating["seated"] is False
    assert "p5_non_degenerate" in seating["unseated_by"]


def test_a_reader_that_never_leaves_slot_a_also_fails_p5() -> None:
    """The other degeneracy, and the one that broke P5's first formulation.

    `gemma3:12b`'s pilot answered `A` twelve times in every session on every shelf. Because the
    orientation swap moves the target between slots, that reader's *target* share alternates
    1.00 / 0.00 and its standard deviation is maximal — so a check on the target share reports
    the most rigidly positional reader available as the most discriminating one. The slot share
    is the quantity that is constant for a fixed-pattern reader and variable for a content-driven
    one.
    """
    always_a = bcr.Run(
        sessions=[
            bcr.Session(f"shelf-{index % 3}", "P1", "m", index % 2, index // 2, 0.0,
                        tuple("AAAAAAAAAAAA"))
            for index in range(24)
        ]
    )
    seating = bcr.seat(always_a, model="positional")
    check = seating["controls"]["p5_non_degenerate"]
    assert check["verdict"] == "FAIL"
    assert check["slot_share_sd"] == 0.0
    assert check["mean_switch_rate"] == 0.0
    assert "never leaves" in check["why"]
    assert seating["seated"] is False


def test_the_dose_response_kill_is_an_inversion_and_not_a_flat_line() -> None:
    """D1's kill condition is A2's inversion — strongest at the smallest dose — and a reader
    that cannot see the damage at all is a different finding from one that sees it backwards."""
    doses = [0.15, 0.35, 0.65, 1.0]
    assert bcr.isotonic(doses, [0.5, 0.6, 0.55, 0.8]) == sorted(
        bcr.isotonic(doses, [0.5, 0.6, 0.55, 0.8])
    )
    rising = bcr.isotonic(doses, [0.50, 0.55, 0.65, 0.80])
    assert rising[-1] > rising[0]


def test_two_replicates_of_one_shelf_are_two_draws_and_not_one() -> None:
    """The defect this pins is silent and would have wasted a whole battery.

    The replay cache is keyed by a digest of the request plus the sample index, and at step 0
    the request is byte-identical across every replicate of a shelf — same system prompt, same
    opening chunks, same budget. With the step alone as the index, replicate 1 would be a cache
    hit on replicate 0 and every "replicate" would be one draw repeated; on ollama the index is
    also the sampler seed, so the collapse would happen even with the cache cleared.
    """

    class _Recorder:
        def __init__(self) -> None:
            self.samples: list[int] = []

        def ask_raw(self, system, turns, *, schema, max_tokens, tag, sample=0, model=None):  # type: ignore[no-untyped-def]
            del system, turns, schema, max_tokens, tag, model
            self.samples.append(sample)
            return {"refused": False, "text": '{"continue": "A"}'}

    text, _ = bcr.load_text(None)
    shelf = bcr.Shelf("s", "T", text, text)
    recorder = _Recorder()
    for replicate in range(3):
        bcr.run_session(
            recorder, shelf, model="m", orientation=0, replicate=replicate, budget=4
        )
    assert len(recorder.samples) == len(set(recorder.samples)), (
        "two fetches shared a sample index, so they share a cache entry and a seed"
    )


def test_chunking_never_splits_a_paragraph_or_loses_a_word() -> None:
    """A chunk that ended mid-sentence would make a fetch an interruption rather than a
    section, and a reader's allocation would then partly measure where the cuts fell."""
    text, _ = bcr.load_text(None)
    pieces = bcr.chunks(text)
    assert "\n\n".join(pieces).split() == text.split()
    assert len(pieces) >= bcr.MIN_CHUNKS
    assert all(len(piece.split()) >= bcr.CHUNK_WORDS * 0.5 for piece in pieces)
