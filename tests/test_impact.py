"""§17 Stage 2's exit, made computable — and narrowed to what the gold can actually grade.

The test worth reading first is `test_the_positional_heuristic_is_worse_than_guessing_everything`.
It refutes the propagation heuristic anyone would reach for, before it is built, which is this
project's cheapest kind of progress.

`test_a_typography_only_change_must_move_nothing` is the negative control and the one an
engine optimised for recall fails.
"""

from __future__ import annotations

import json

import litharness_contracts as lc
import pytest

from litharness.adapters import contracts_fixtures
from litharness.adapters.contracts_fixtures import fixture_impact_gold
from litharness.domain import impact, propagation


def suite(fixture_id: str) -> lc.GoldImpactSuite:
    return lc.parse_artifact(
        lc.GoldImpactSuite,
        json.loads(fixture_impact_gold(fixture_id).read_text(encoding="utf-8")),
    )


def all_cases() -> list[lc.GoldImpactCase]:
    return [case for fixture in ("litrpg", "mystery") for case in suite(fixture).cases]


def case(scenario_id: str) -> lc.GoldImpactCase:
    return next(c for c in all_cases() if c.scenario_id == scenario_id)


# -- what the suite actually contains ----------------------------------------------------


def test_the_suite_is_readable_and_this_is_its_size() -> None:
    """Recorded as an assertion because the size is the argument. 37 expectations across two
    fixtures, against this project's own MIN_HOLDOUT of 50 — before the fact that both suites
    are generated from the same def.json that authors the prose they grade."""
    cases = all_cases()
    assert len(cases) == 4
    assert sum(len(c.expected) for c in cases) == 37


def test_the_gold_carries_no_character_offsets() -> None:
    """The measurement that rewrote §17 Stage 2's exit clause. "Affected-span precision" is
    not computable against this: an expectation is (target, label, note), and the target is a
    ResourceRef. There are no offsets anywhere to be precise about."""
    import dataclasses

    fields = {f.name for f in dataclasses.fields(lc.GoldImpactExpectation)}
    assert fields == {"target", "label", "note"}
    assert not hasattr(all_cases()[0].expected[0], "start")


def test_the_edited_node_is_never_labelled() -> None:
    """So the suite cannot grade "did you fix the thing you changed" either — only where the
    change propagates to. `e1-lantern-price` edits scene-2 and labels scenes 1, 3, 4, 5, 6."""
    for item in all_cases():
        assert not (impact.edited_targets(item) & {e.target.logical_id for e in item.expected})


# -- the metric --------------------------------------------------------------------------


def test_predicting_the_edited_node_neither_helps_nor_hurts() -> None:
    item = case("e1-lantern-price")
    plain = impact.score_case(item, set())
    with_edit = impact.score_case(item, impact.edited_targets(item))
    assert plain == with_edit


def test_predicting_nothing_has_no_precision_rather_than_perfect_precision() -> None:
    """The vacuous 1.0 is how a do-nothing baseline comes top of a table."""
    score = impact.score_case(case("e1-lantern-price"), set())
    assert score.precision is None
    assert score.recall == 0.0


def test_inspect_is_counted_and_never_scored() -> None:
    """The gold says a human should look, not that the node must or must not change. Folding
    it into must_update would inflate recall by fiat."""
    item = case("e1-lantern-price")
    inspect_only = impact.targets_of(item, [lc.ImpactLabel.INSPECT])
    assert inspect_only, "the case must carry inspect targets for this to mean anything"
    score = impact.score_case(item, inspect_only)
    assert score.hits == 0 and score.false_touches == 0
    assert score.inspected == len(inspect_only)


def test_summaries_are_excluded_because_nothing_produces_them() -> None:
    """Every derived_only target is a `summary:*`, and LitHarness has no summary producer.
    Scoring them would measure the absence of a subsystem."""
    for item in all_cases():
        derived = {
            e.target.logical_id for e in item.expected if e.label is lc.ImpactLabel.DERIVED_ONLY
        }
        assert all(name.startswith("summary:") for name in derived), derived
        assert impact.score_case(item, derived).hits == 0


# -- the baselines, which are the point --------------------------------------------------


def measured(predict) -> impact.ImpactScore:
    return impact.totals([impact.score_case(c, predict(c)) for c in all_cases()])


def test_the_base_rate_an_engine_must_beat() -> None:
    """Predicting every labelled target buys recall 1.0 by construction, so its *precision*
    is the floor. An engine at or below 0.481 has learned nothing about propagation."""
    score = measured(impact.predict_everything)
    assert score.recall == 1.0
    assert score.precision is not None
    assert round(score.precision, 3) == 0.481
    assert (score.hits, score.false_touches) == (13, 14)


def test_the_positional_heuristic_is_worse_than_guessing_everything() -> None:
    """Refuted before it is built, which is the cheapest kind of progress here.

    "Everything after the edited scene" is what a propagation engine looks like before it
    reads anything, and it scores precision 0.333 against predict_everything's 0.481 — it
    buys *worse* precision while giving up most of the recall. The mystery's `e2-rename-julian`
    is why: renaming a character must update scenes 3, 5 and 6 while preserving 1, 2 and 4,
    and position predicts none of that.
    """
    positional = measured(impact.predict_downstream_scenes)
    everything = measured(impact.predict_everything)
    assert positional.precision is not None and everything.precision is not None
    assert round(positional.precision, 3) == 0.333
    assert positional.precision < everything.precision
    assert positional.recall is not None and positional.recall < 0.25


def test_predicting_nothing_scores_zero_recall_across_the_suite() -> None:
    score = measured(impact.predict_nothing)
    assert score.recall == 0.0
    assert score.misses == 13


@pytest.mark.parametrize(
    "scenario_id,expected_precision",
    [
        ("e1-lantern-price", 0.714),
        ("e1-move-key-discovery", 0.600),
        ("e2-rename-julian", 0.625),
        ("e3-typography-only", 0.0),
    ],
)
def test_the_per_case_base_rate_is_recorded(scenario_id: str, expected_precision: float) -> None:
    """Pinned per case, because pooling hides that one case is a pure negative control."""
    score = impact.score_case(case(scenario_id), impact.predict_everything(case(scenario_id)))
    assert score.precision is not None
    assert round(score.precision, 3) == expected_precision


def test_a_typography_only_change_must_move_nothing() -> None:
    """The negative control, and the failure mode an engine optimised for recall arrives at
    naturally: eight safe_preserve targets, no must_update at all. Touch anything and the
    case scores zero precision with no recall available to compensate."""
    item = case("e3-typography-only")
    assert impact.targets_of(item, [lc.ImpactLabel.MUST_UPDATE]) == set()
    assert len(impact.targets_of(item, [lc.ImpactLabel.SAFE_PRESERVE])) == 7

    perfect = impact.score_case(item, set())
    assert perfect.false_touches == 0 and perfect.recall is None

    greedy = impact.score_case(item, impact.predict_everything(item))
    assert greedy.precision == 0.0


def test_every_score_carries_what_it_is_not() -> None:
    """A number from an in-sample, node-granular suite must not travel as span precision."""
    caveat = measured(impact.predict_everything).caveat
    assert "not span precision" in caveat
    assert "in-sample" in caveat


# -- the engine, which is what the baselines were for -------------------------------------


def gold_book(fixture_id: str) -> propagation.Book:
    """The fixture's prose and state records, as the engine reads them.

    Built from the contracts artifacts rather than from an imported `Revision`, because the
    gold cases are authored against the fixture's own node ids and `import_manuscript`
    re-addresses every node — the join is on `logical_id`, never on `version_id`, for exactly
    the reason `impact.targets_of` records.
    """
    manuscript = json.loads(
        contracts_fixtures.fixture_manuscript(fixture_id).read_text(encoding="utf-8")
    )
    state = lc.parse_artifact(
        lc.StateSnapshot,
        json.loads(contracts_fixtures.fixture_state(fixture_id).read_text(encoding="utf-8")),
    )
    return propagation.Book(
        nodes=tuple(
            propagation.ProseNode(
                node["logical_id"], node.get("position_key", ""), node.get("content") or ""
            )
            for node in manuscript["nodes"]
            if node.get("content")
        ),
        records=tuple(state.records),
    )


BOOKS = {"litrpg": None, "mystery": None}


def book_for(scenario_id: str) -> propagation.Book:
    fixture_id = "litrpg" if scenario_id == "e1-lantern-price" else "mystery"
    if BOOKS[fixture_id] is None:
        BOOKS[fixture_id] = gold_book(fixture_id)
    book = BOOKS[fixture_id]
    assert book is not None
    return book


def engine(item: lc.GoldImpactCase) -> set[str]:
    return propagation.propagate(item.change_set, book_for(item.scenario_id)).logical_ids


def test_the_engine_beats_the_base_rate_it_had_to_beat() -> None:
    """§17 Stage 2's exit item 2, executable at last — the clause had a scorer, three
    baselines and nothing to score. Precision above `predict_everything`'s 0.481 at
    comparable recall.

    **This is a dev-set number and does not generalise.** Four cases, 37 expectations, both
    suites generated from the same `def.json` that authors the prose they grade, against this
    project's own MIN_HOLDOUT of 50. What it rules out is an engine that is obviously wrong;
    it cannot rule in one that is right. Held-out material is Stage 3's to supply.
    """
    score = measured(engine)
    everything = measured(impact.predict_everything)

    assert score.precision is not None and everything.precision is not None
    assert score.precision > everything.precision
    assert score.recall is not None and score.recall >= everything.recall
    assert (score.hits, score.misses, score.false_touches) == (13, 0, 0)


def test_the_engine_leaves_the_typography_case_untouched() -> None:
    """The other half of the exit clause, and the failure mode recall optimises into: eight
    safe_preserve targets, no must_update, and every scene in the book still mentioning
    everything it mentioned before."""
    item = case("e3-typography-only")

    assert engine(item) == set()
    assert impact.score_case(item, engine(item)).false_touches == 0


def test_the_engine_beats_the_heuristic_that_was_refuted_before_it_was_built() -> None:
    positional = measured(impact.predict_downstream_scenes)
    score = measured(engine)

    assert score.precision is not None and positional.precision is not None
    assert score.precision > positional.precision
    assert score.recall is not None and positional.recall is not None
    assert score.recall > positional.recall


@pytest.mark.parametrize(
    "scenario_id,hits,misses,false_touches",
    [
        ("e1-lantern-price", 5, 0, 0),
        ("e1-move-key-discovery", 3, 0, 0),
        ("e2-rename-julian", 5, 0, 0),
        ("e3-typography-only", 0, 0, 0),
    ],
)
def test_the_engine_is_pinned_per_case(
    scenario_id: str, hits: int, misses: int, false_touches: int
) -> None:
    """Pinned per case because the pooled number hides which rule is carrying it — and
    because a rule regression that trades a hit in one case for a hit in another is invisible
    in the total."""
    score = impact.score_case(case(scenario_id), engine(case(scenario_id)))
    assert (score.hits, score.misses, score.false_touches) == (hits, misses, false_touches)


def test_every_case_in_the_suite_is_one_the_engine_claims_to_have_read() -> None:
    """A perfect score over cases the engine abstained on would be a scoring artefact: an
    abstention predicts nothing, and predicting nothing scores no false touches. The number
    above means something only because no case in the suite is unread."""
    for item in all_cases():
        result = propagation.propagate(item.change_set, book_for(item.scenario_id))
        assert result.complete, f"{item.scenario_id}: {result.unhandled}"
