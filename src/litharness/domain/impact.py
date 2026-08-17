"""Scoring a propagation prediction against the gold impact suite.

§17 Stage 2's exit clause reads: *"detect-then-repair beats revise-then-gate on affected-span
precision and preservation on held-out material (RevisionBench's own promotion gate)."* Three
things in that sentence do not exist, and this module is what does.

**"Affected-span precision" is not measurable against anything this project has.**
`GoldImpactExpectation` is `(target, label, note)` — **no character offsets anywhere**. The
suite also never labels the node the change edits: `e1-lantern-price` edits `scene-2` and
labels scenes 1, 3, 4, 5, 6. So what the gold actually encodes is *blast radius at node
granularity* — given this change, which other nodes must move, which must not. That is a real
and useful thing to measure. It is not span precision, and calling it that would be the
project reporting a number for a quantity it never computed.

**"RevisionBench's own promotion gate" does not exist.** Four prose hits for "promot" in that
repo, and its one standing rule is a *blocker* — no threshold ships until replicated on a
second model family. There is nothing to defer to.

**And the material is in-sample.** Both suites are generated from the same `def.json` that
authors the prose they grade, and ship inside the contracts package, which six test modules
already read. 37 expectations across two fixtures, against this project's own
`MIN_HOLDOUT = 50`. So a number from here is a **dev-set** number and every caller is made to
say so — see `ImpactScore.caveat`.

What is worth having anyway: the metric becomes executable, and the baselines below say what
"beating" would have to mean. `e3-typography-only` is the one to keep in view — a
typography-only change with **eight** `safe_preserve` targets and no `must_update` at all. A
propagation engine that touches anything fails it, which is the failure mode an engine
optimised for recall arrives at naturally.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

import litharness_contracts as lc

#: Labels that carry a scoring obligation, and the two that do not.
#:
#: `INSPECT` is genuinely ambiguous — the gold says a human should look, not that the node
#: must or must not change — so it is counted and reported but scored neither way. Folding it
#: into `MUST_UPDATE` would inflate recall by fiat; folding it into `SAFE_PRESERVE` would
#: penalise an engine for doing what the label asks.
#:
#: `DERIVED_ONLY` is every `summary:*` target in both suites, and **LitHarness has no summary
#: producer at all**, so scoring it would measure the absence of a subsystem rather than the
#: quality of a prediction. Excluded, and named here so its return is a deliberate act.
SCORED = frozenset({lc.ImpactLabel.MUST_UPDATE, lc.ImpactLabel.SAFE_PRESERVE})

#: Anything mapping a case to the `logical_id`s it claims the change reaches.
Predictor = Callable[[lc.GoldImpactCase], set[str]]

#: What every number from this module is, and is not. Defined once because it travels: the
#: score carries it, and so does `litharness propagate`, which reports a prediction from the
#: engine these baselines exist to grade. A caveat that lives at one call site is one the
#: other call site quietly drops.
CAVEAT = (
    "dev-set propagation scope at node granularity; the gold carries no character "
    "offsets, so this is not span precision, and both suites are in-sample"
)


@dataclass(frozen=True, slots=True)
class ImpactScore:
    """One case's blast-radius prediction, scored."""

    scenario_id: str
    #: Correctly predicted `MUST_UPDATE` targets.
    hits: int
    #: `MUST_UPDATE` targets the prediction missed.
    misses: int
    #: `SAFE_PRESERVE` targets the prediction would have touched. The expensive error: a
    #: propagation engine that rewrites a conforming scene has damaged the book.
    false_touches: int
    #: `INSPECT` targets predicted. Reported, never scored — see `SCORED`.
    inspected: int
    inspect_total: int
    excluded: int

    @property
    def precision(self) -> float | None:
        """None rather than 1.0 when nothing was predicted. A prediction of nothing has no
        precision, and reporting the vacuous 1.0 is how a do-nothing baseline comes top."""
        touched = self.hits + self.false_touches
        return self.hits / touched if touched else None

    @property
    def recall(self) -> float | None:
        required = self.hits + self.misses
        return self.hits / required if required else None

    @property
    def caveat(self) -> str:
        return CAVEAT


def targets_of(case: lc.GoldImpactCase, labels: Iterable[lc.ImpactLabel]) -> set[str]:
    """The case's targets carrying any of these labels, by `logical_id`.

    **Joined on `logical_id`, never on `version_id`.** The contracts package mints UUID5
    addresses and `import_manuscript` re-addresses every node by sha256, so not one of the
    suite's version ids survives import — a join on them silently matches nothing and scores
    a perfect zero.
    """
    wanted = set(labels)
    return {
        expectation.target.logical_id
        for expectation in case.expected
        if expectation.label in wanted
    }


def edited_targets(case: lc.GoldImpactCase) -> set[str]:
    """What the change itself touches. Never in `expected`, and never scored: an engine gets
    no credit for the node it was told to edit."""
    return {op.logical_source_id for op in case.change_set.operations}


def score_case(case: lc.GoldImpactCase, predicted: Iterable[str]) -> ImpactScore:
    """Score a set of predicted-affected `logical_id`s against one case.

    `predicted` is what a propagation engine says the change reaches. The edited nodes are
    removed first, so predicting them neither helps nor hurts.
    """
    prediction = set(predicted) - edited_targets(case)
    must = targets_of(case, [lc.ImpactLabel.MUST_UPDATE])
    preserve = targets_of(case, [lc.ImpactLabel.SAFE_PRESERVE])
    inspect = targets_of(case, [lc.ImpactLabel.INSPECT])
    return ImpactScore(
        scenario_id=case.scenario_id,
        hits=len(prediction & must),
        misses=len(must - prediction),
        false_touches=len(prediction & preserve),
        inspected=len(prediction & inspect),
        inspect_total=len(inspect),
        excluded=len(case.expected) - len(must) - len(preserve) - len(inspect),
    )


def score_suite(
    suite: lc.GoldImpactSuite, predict: Predictor
) -> tuple[ImpactScore, ...]:
    return tuple(score_case(case, predict(case)) for case in suite.cases)


def totals(scores: Sequence[ImpactScore]) -> ImpactScore:
    """Pooled across cases. Micro-averaged deliberately: with four cases of 8-11 expectations
    a macro average lets the smallest case swing the headline."""
    return ImpactScore(
        scenario_id=f"({len(scores)} case(s) pooled)",
        hits=sum(s.hits for s in scores),
        misses=sum(s.misses for s in scores),
        false_touches=sum(s.false_touches for s in scores),
        inspected=sum(s.inspected for s in scores),
        inspect_total=sum(s.inspect_total for s in scores),
        excluded=sum(s.excluded for s in scores),
    )


# -- baselines ---------------------------------------------------------------------------
#
# What any propagation engine has to beat. They exist because a number with nothing beside it
# is unreadable: "recall 0.85" is excellent against `predict_nothing` and a catastrophe
# against `predict_everything`, and §10.6's whole lesson is that the control belongs in the
# same pass as the headline.


def predict_nothing(case: lc.GoldImpactCase) -> set[str]:
    """The do-nothing floor. Recall 0, and precision `None` rather than a vacuous 1.0."""
    return set()


def predict_everything(case: lc.GoldImpactCase) -> set[str]:
    """The other floor: touch every labelled target. Recall 1.0 by construction, so its
    *precision* is the number that matters — it is the base rate an engine must beat, and
    anything at or below it has learned nothing about propagation."""
    return {expectation.target.logical_id for expectation in case.expected}


def predict_downstream_scenes(case: lc.GoldImpactCase) -> set[str]:
    """The cheapest heuristic worth refuting: every scene positioned after an edited one.

    Included because it is what a propagation engine looks like before it reads anything —
    and because the mystery's `e2-rename-julian` shows why that fails. Renaming a character
    must update scenes 3, 5 and 6 while preserving 1, 2 and 4; position predicts none of that.
    """
    edited = edited_targets(case)
    ordinals = [
        int(name.split("-")[1])
        for name in edited
        if name.startswith("scene-") and name.split("-")[1].isdigit()
    ]
    if not ordinals:
        return set()
    first = min(ordinals)
    return {
        expectation.target.logical_id
        for expectation in case.expected
        if expectation.target.logical_id.startswith("scene-")
        and expectation.target.logical_id.split("-")[1].isdigit()
        and int(expectation.target.logical_id.split("-")[1]) > first
    }


__all__ = [
    "CAVEAT",
    "SCORED",
    "ImpactScore",
    "Predictor",
    "edited_targets",
    "predict_downstream_scenes",
    "predict_everything",
    "predict_nothing",
    "score_case",
    "score_suite",
    "targets_of",
    "totals",
]
