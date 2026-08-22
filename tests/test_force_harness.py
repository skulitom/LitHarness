"""The rails under stage-0 §95's force programme, checked rather than asserted.

`force_harness.py` is the one place the force programme's standard lives, so every track inherits
whatever it gets wrong. Five of its claims are load-bearing enough that §95 cites them, and all
five are the kind that fail silently — they return a number, not an error:

1. **The attainability table reproduces §89.2's published one.** 85 of 144, 81 of 137, 43 of 68,
   44 of 69, interval binding at every n. If the Clopper-Pearson arithmetic drifted, every bar in
   the programme would move and nothing would raise.
2. **`MIN_REFUTING_N` is derived, not chosen.** It is the smallest n that is both *attainable* and
   demands 0.6000 or less. The first derivation omitted the attainable guard and returned 5 — an n
   at which no k clears the interval at all, so a stratum there is worse than excusable rather
   than better. That is the failure this test exists to keep caught.
3. **Refusals do not fold into verdicts.** `DEGRADED_STRATUM` and `INSUFFICIENT_N` are verdicts in
   their own right, including when two families are combined; `combine_families` folded the first
   into `FAIL` until a three-pair smoke run caught it, in the function whose entire job is to
   combine refusals.
4. **The placebo's exactness is a property of the seeding, not of luck.** `text_seed` is a pure
   function of the text, so byte-identical sides produce byte-identical everything downstream.
   Seeding on `(pair, side, replicate)` — the obvious choice — would give identical text different
   samples and the placebo could not play §89.4's arithmetic-check role.
5. **A sham that reads anything is VOID in either direction.** A control that only fails when it
   points one way is a control that has been given a preferred answer.

These run on constructed inputs and read nothing from `results/` or `corpora/`, so they are
hermetic and cost nothing. The GPU half of the programme (`force_gpu`) is not imported here: it
needs torch, which CI's environment does not have.
"""

from __future__ import annotations

import pytest

force_harness = pytest.importorskip(
    "force_harness",
    reason="research module; needs the quality-measurement directory on the path",
)


# §89.2's published table. The programme's bars are these numbers or they are wrong.
PUBLISHED = (
    (144, 75, 85),
    (137, 72, 81),
    (68, 36, 43),
    (69, 36, 44),
)


@pytest.mark.parametrize(("n", "k_point", "k_interval"), PUBLISHED)
def test_attainability_reproduces_the_published_table(n: int, k_point: int, k_interval: int):
    row = force_harness.attainability(n)
    assert row["k_point_0_52"] == k_point
    assert row["k_interval_cp_gt_0_50"] == k_interval
    assert row["binding"] == "interval"


def test_min_refuting_n_is_derived_and_needs_the_attainable_guard():
    """The smallest n that is *attainable* and demands <= 0.6000. Omitting the guard gives 5."""
    derived = min(
        n
        for n in range(2, 200)
        if force_harness.attainability(n)["attainable"]
        and not force_harness.attainability(n)["insufficient_n_available"]
    )
    assert derived == force_harness.MIN_REFUTING_N == 110

    # Without the guard the answer is an n where no k clears the interval at all.
    unguarded = min(
        n for n in range(2, 200)
        if not force_harness.attainability(n)["insufficient_n_available"]
    )
    assert unguarded < 10
    assert force_harness.attainability(unguarded)["k_interval_cp_gt_0_50"] is None


def test_insufficient_n_admits_the_small_strata_and_refuses_the_binding_ones():
    assert not force_harness.attainability(144)["insufficient_n_available"]
    assert not force_harness.attainability(137)["insufficient_n_available"]
    assert force_harness.attainability(68)["insufficient_n_available"]
    assert force_harness.attainability(20)["insufficient_n_available"]


def test_a_near_miss_fails_on_a_binding_stratum_and_is_excused_on_a_small_one():
    assert force_harness.verdict("aligned", 80, 144, 144)["status"] == "FAIL"
    assert force_harness.verdict("crossed_tight", 40, 68, 68)["status"] == "INSUFFICIENT_N"
    assert force_harness.verdict("aligned", 90, 144, 144)["status"] == "PASS"


def test_ties_are_not_evidence():
    """A statistic mostly made of ties has said nothing, and says so rather than
    reporting a rate."""
    row = force_harness.verdict("aligned", 60, 100, 144)
    assert row["status"] == "INERT_GENERATOR"
    assert "agreement" not in row


def test_drops_and_ties_are_different_states():
    """Attrition is a fact about the corpus; ties are a fact about the generator.

    Folding them together mislabels a truncated stratum as an inert one — and the other
    ordering published tie-driven inert readings as corpus-power complaints that explicitly
    acquit the force.
    """
    truncated = force_harness.verdict("crossed", 40, 76, 76, n_before_drops=137, binding=True)
    assert truncated["status"] == "DEGRADED_STRATUM"
    assert truncated["dropped_before_scoring"] == 61

    tied = force_harness.verdict("crossed", 40, 80, 137, n_before_drops=137, binding=True)
    assert tied["status"] == "INERT_GENERATOR"

    counted = force_harness.verdict("crossed", 70, 120, 120, n_before_drops=137, binding=True)
    assert counted["dropped_before_scoring"] == 17


def test_combine_families_never_folds_a_refusal_into_a_failure():
    degraded = {
        "a": {"aligned": {"status": "DEGRADED_STRATUM"}},
        "b": {"aligned": {"status": "FAIL"}},
    }
    assert force_harness.combine_families(degraded, "aligned")["status"] == "DEGRADED_STRATUM"

    split = {"a": {"aligned": {"status": "PASS"}}, "b": {"aligned": {"status": "FAIL"}}}
    assert force_harness.combine_families(split, "aligned")["status"] == "SPLIT_FAMILY"

    both = {"a": {"aligned": {"status": "PASS"}}, "b": {"aligned": {"status": "PASS"}}}
    assert force_harness.combine_families(both, "aligned")["status"] == "PASS"


def test_the_seed_is_a_pure_function_of_the_text():
    assert force_harness.text_seed("abc", 3) == force_harness.text_seed("abc", 3)
    assert force_harness.text_seed("abc", 3) != force_harness.text_seed("abd", 3)
    assert force_harness.text_seed("abc", 3) != force_harness.text_seed("abc", 4)
    # Identity of value, not of object: the placebo builds its second side separately.
    assert force_harness.text_seed("abc") == force_harness.text_seed("".join(list("abc")))


def test_a_sham_that_reads_anything_is_void_in_either_direction():
    assert force_harness.sham_verdict("s", 50, 100, 100)["status"] == "PASS"
    assert force_harness.sham_verdict("s", 90, 100, 100)["status"] == "VOID"
    assert force_harness.sham_verdict("s", 10, 100, 100)["status"] == "VOID"
    assert force_harness.sham_verdict("s", 0, 0, 0)["status"] == "NOT_SCREENABLE"


def test_the_placebo_tolerance_is_applied_rather_than_assumed():
    assert force_harness.control_verdict("p", 0.0, tolerance=0.0, kind="exact")["status"] == "PASS"
    assert force_harness.control_verdict("p", 1e-9, tolerance=0.0, kind="exact")["status"] == "VOID"


def test_the_sham_transform_changes_layout_and_not_one_character_of_any_word():
    sample = "One line.  Two line.\n\nThree line. Four line."
    assert sample.split() == force_harness.rewhitespace(sample, 1.0).split()


def test_pairing_direction_is_stated_at_the_call_site():
    scores = {
        "a": {"high": 2.0, "low": 1.0},
        "b": {"high": 1.0, "low": 2.0},
        "c": {"high": 1.0, "low": 1.0},
    }
    pairs = [
        force_harness.ForcePair(pair_id=key, stratum="aligned", high="x", low="y")
        for key in scores
    ]
    assert force_harness.pair_agreement(scores, pairs) == (1, 2, 3)
    assert force_harness.pair_agreement(scores, pairs, higher_wins=False) == (1, 2, 3)


def test_the_nuisance_regression_removes_what_it_is_given_and_nothing_else():
    covariate = {f"k{i}": float(i) for i in range(10)}
    values = {f"k{i}": 3.0 * i + 1.0 for i in range(10)}
    residuals = force_harness.residualise(values, covariate)
    assert max(abs(v) for v in residuals.values()) < 1e-9


def test_control_subsamples_span_both_strata():
    """`load_pairs` returns aligned then crossed, so a head slice draws from one stratum only.

    A sham that only ever sees `aligned` certifies that a force ignores formatting on half the
    corpus and is silent about the half §79 built to be adversarial.
    """
    corpus = (
        [force_harness.ForcePair(pair_id=f"a{i}", stratum="aligned", high="x", low="y")
         for i in range(144)]
        + [force_harness.ForcePair(pair_id=f"c{i}", stratum="crossed", high="x", low="y")
           for i in range(137)]
    )
    picked = force_harness.stratified_subsample(corpus, 60)
    assert len(picked) == 60
    assert {pair.stratum for pair in picked} == {"aligned", "crossed"}
    assert force_harness.stratified_subsample(corpus, 60) == picked
    assert len(force_harness.stratified_subsample(corpus, 999)) == len(corpus)


def test_one_family_cannot_report_a_pass():
    """§1.4's minimum is enforced in `combine_families` or nowhere.

    With a single family `all(status == "PASS")` is trivially true, so a single-lineage arm that
    cleared its strata would have reported PASS — the exact claim §94.5 says cannot be made, in
    the function written to prevent it.
    """
    solo = {"haiku-4-5": {"aligned": {"status": "PASS"}}}
    combined = force_harness.combine_families(solo, "aligned")
    assert combined["status"] == "NOT_SCREENABLE"
    assert "two-family minimum" in combined["why"]


def test_an_unscreened_control_cannot_read_as_a_clean_arm():
    """§1.3 rides the controls on every force; a control that could not be read certifies nothing.

    The case that matters is a run whose budget or substrate ran out before the sham. Without
    this, the arm reports READ beside strata that look fine and a reader has no way to tell the
    formatting control never happened.
    """
    clean = force_harness.arm_status({
        "placebo_identical": {"status": "PASS"},
        "rewhitespace_sham": {"status": "PASS"},
    })
    assert clean["status"] == "READ"

    unscreened = force_harness.arm_status({
        "placebo_identical": {"status": "PASS"},
        "rewhitespace_sham": {"status": "NOT_SCREENABLE"},
    })
    assert unscreened["status"] == "NOT_SCREENABLE"

    moved = force_harness.arm_status({
        "placebo_identical": {"status": "PASS"},
        "rewhitespace_sham": {"status": "VOID"},
    })
    assert moved["status"] == "VOID"

    # A moved control outranks an unscreened one: disqualification beats "we could not tell".
    both = force_harness.arm_status({
        "placebo_identical": {"status": "NOT_SCREENABLE"},
        "rewhitespace_sham": {"status": "VOID"},
    })
    assert both["status"] == "VOID"


def test_the_refuting_floor_is_a_predicate_at_n_not_a_threshold_on_n():
    """`required_rate` is sawtoothed, so `decided >= 110` did not mean "can refute".

    n ∈ {111, 113, 116, 118} each demand 0.6017 to 0.6036 — above the declared 0.6000 ceiling for
    calling a miss a refutation — and each clears the `MIN_REFUTING_N = 110` floor the guard
    compared against. F3's `aligned` stratum is exactly 118: the arm with the least power was
    the one the threshold waved through, and it could have published a FAIL it had no standing
    to publish.
    """
    sawtooth = {n: force_harness.attainability(n)["required_rate"] for n in (111, 113, 116, 118)}
    assert all(rate > force_harness.INSUFFICIENT_N_ABOVE for rate in sawtooth.values()), sawtooth
    assert all(n > force_harness.MIN_REFUTING_N for n in sawtooth)

    for n in sawtooth:
        missed = force_harness.verdict("aligned", n // 2, n, n, n_before_drops=n, binding=True)
        assert missed["status"] == "INSUFFICIENT_N", (n, missed["status"])

    # The two strata the programme actually binds on can still refute, or §61 has no teeth.
    for n in (137, 144):
        missed = force_harness.verdict("aligned", n // 2, n, n, n_before_drops=n, binding=True)
        assert missed["status"] == "FAIL", (n, missed["status"])


def test_a_power_guard_never_overrides_a_stratum_that_cleared_both_bars():
    """The guards say a *FAIL* here would be about power. That is silent about a PASS.

    Running them before the bars meant decisive agreement on a small stratum was published as a
    corpus-power complaint: 95 of 100 gives a Clopper-Pearson lower bound of 0.887, and the arm
    reported DEGRADED_STRATUM with prose explaining it could not refute.
    """
    strong = force_harness.verdict("aligned", 95, 100, 100, n_before_drops=140, binding=True)
    assert strong["status"] == "PASS"
    assert strong["clopper_pearson"][0] > 0.50

    # Same n, same drops, a miss instead of a win: now the guard is the one with something to say.
    weak = force_harness.verdict("aligned", 55, 100, 100, n_before_drops=140, binding=True)
    assert weak["status"] == "DEGRADED_STRATUM"
    assert "40 of 140" in weak["why"]


def test_an_arm_that_ran_no_controls_is_not_a_screened_arm():
    """`arm_status({})` returned READ, and an arm certified itself by running nothing.

    The loop over an empty dict finds no VOID and no unscreened name, so absence read as
    cleanliness — the one shape this function most needed to catch, since a *missing* control
    leaves no trace in the report while a failing one does. F3 is the demonstration: it skipped
    both controls, wrote `status = "READ"` as a literal, and a statistic reading only newline
    counts published PASS on both strata underneath it.
    """
    assert force_harness.arm_status({})["status"] == "NOT_SCREENABLE"
    assert force_harness.arm_status({})["missing_controls"] == list(
        force_harness.REQUIRED_CONTROLS
    )

    # One control present is not half-screened, it is unscreened: the placebo checks arithmetic
    # and the sham checks layout-blindness, and neither stands in for the other.
    half = force_harness.arm_status({"placebo_identical": {"status": "PASS"}})
    assert half["status"] == "NOT_SCREENABLE"
    assert half["missing_controls"] == ["rewhitespace_sham"]

    # An extra name alongside the two required ones is still screened, and still binding.
    extra = force_harness.arm_status({
        "placebo_identical": {"status": "PASS"},
        "rewhitespace_sham": {"status": "PASS"},
        "shuffled_diagnostic": {"status": "PASS"},
    })
    assert extra["status"] == "READ"


def test_the_module_selftest_passes():
    assert force_harness.selftest() == 0
