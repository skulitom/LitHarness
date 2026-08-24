"""Finding the golden fixtures, which ship inside the contracts wheel.

As of `litharness-contracts` 0.2.0 the mystery and litrpg fixture books live at
`src/litharness_contracts/fixtures/golden/` — *inside* the importable package — and the
package exposes `litharness_contracts.fixtures.golden_path` as the one canonical lookup.
This module is a thin translation over it: it keeps the names and the failure type the rest
of this repository already depends on, and adds one link in front.

**What used to be here, and why it is gone.** The books sat outside the package, so no wheel
carried them and this module had to find a *checkout* — an environment variable, then a walk
up from the installed package's own `__file__` (which only worked because the dependency was
an editable path install), then a guess at a sibling directory beside this repository. Each
link existed because the one before it could fail, and together they meant a clone of this
repository on its own could not run its own suite. The dependency is now a git rev pinned in
`uv.lock`, so `import litharness_contracts` is the whole of discovery and both heuristics are
deleted rather than merely unused.

**`LITHARNESS_CONTRACTS_ROOT` survives, with a narrower job.** It is the escape hatch for
work-in-progress fixtures: point it at a contracts checkout and the books there win over the
installed ones, without reinstalling. It still names a checkout *root* — the path beneath it
changed with the move, and `GOLDEN` records that — and it is still the variable
LongRangeContext uses, because a second name for one setting is how two checkouts end up
configured differently. It is checked against the artifact rather than the directory: a root
that does not hold the file falls through to the installed package instead of failing three
layers down. Hard-coding an absolute path is deliberately still not in the chain; PLAN.md
§20.2 records a machine-bound `samefile("C:/DEV/litharness-contracts/schemas")` as a defect
worth fixing in a sibling, and reintroducing it here would be the same bug.
"""

from __future__ import annotations

import os
from pathlib import Path

# `FIXTURE_IDS` names the books §17 Stage 1 is graded against. It is re-exported here (via
# `__all__`) rather than restated, so this repository cannot come to disagree with the
# contracts package about which books exist.
from litharness_contracts.fixtures import FIXTURE_IDS, golden_root

#: Where a contracts *checkout* keeps them, relative to its root. Only
#: `LITHARNESS_CONTRACTS_ROOT` needs this: an installed package is located by the accessor.
GOLDEN = Path("src") / "litharness_contracts" / "fixtures" / "golden"

#: The one setting that redirects fixture reads, named in every failure this module raises.
CONTRACTS_ROOT_ENV = "LITHARNESS_CONTRACTS_ROOT"


class FixturesUnavailable(FileNotFoundError):
    """The fixture could not be found in the installed contracts package or the override.

    A `FileNotFoundError` so `cli.main` reports it as an operational fault (exit 2) — a
    broken install is the system failing to start, not the system reporting on its work.
    """


def _golden_roots() -> list[Path]:
    """Directories that may hold `<fixture_id>/<filename>`, most specific first."""
    configured = os.environ.get(CONTRACTS_ROOT_ENV)
    roots = [Path(configured) / GOLDEN] if configured else []
    roots.append(golden_root())
    return roots


def _fixture_file(fixture_id: str, filename: str) -> Path:
    """Locate one artifact of a golden fixture, or say exactly how to fix it."""
    if fixture_id not in FIXTURE_IDS:
        raise FixturesUnavailable(
            f"unknown fixture {fixture_id!r}; the golden books are {', '.join(FIXTURE_IDS)}"
        )
    tried: list[Path] = []
    for root in _golden_roots():
        candidate = root / fixture_id / filename
        if candidate.is_file():
            return candidate
        tried.append(candidate)
    raise FixturesUnavailable(
        f"no {fixture_id} {filename} in the installed litharness-contracts (tried "
        + ", ".join(str(path) for path in tried)
        + f"); reinstall the dependency, or set {CONTRACTS_ROOT_ENV} to a contracts checkout"
    )


def fixture_manuscript(fixture_id: str) -> Path:
    """The `manuscript.json` of one golden fixture."""
    return _fixture_file(fixture_id, "manuscript.json")


def fixture_plans(fixture_id: str) -> Path:
    """The `plans.json` beside it — the premise and locked constraints a planner needs."""
    return _fixture_file(fixture_id, "plans.json")


def fixture_state(fixture_id: str) -> Path:
    """The `state.json` beside those two — objective story state (§11).

    The third of the three artifacts a golden book ships, and the last to get a reader: it
    carries the open threads and the POV-restricted knowledge a context packet is graded on.
    """
    return _fixture_file(fixture_id, "state.json")


def fixture_findings(fixture_id: str) -> Path:
    """The `findings.json` beside them — an `EvaluationArtifact` of planted defects.

    Gold labels, not input: §17 Stage 1 is graded on planted-defect injection being caught by
    gates, and this is the artifact the injection uses. It doubles as the worked example of
    §8.4's integration shape, since it is exactly what ContinuityEvaluation's pack emits.
    """
    return _fixture_file(fixture_id, "findings.json")


def fixture_context_gold(fixture_id: str) -> Path:
    """The `GoldContextSuite` that grades a packet — mandatory and forbidden items per query.

    Used by the suite rather than by the system: it is ground truth, not input. It is the
    reason context assembly can be tested for correctness at all instead of eyeballed, and
    nothing in this repository referenced it until there was a packet to grade.
    """
    return _fixture_file(fixture_id, "context_gold.json")


__all__ = [
    "FIXTURE_IDS",
    "FixturesUnavailable",
    "fixture_context_gold",
    "fixture_findings",
    "fixture_impact_gold",
    "fixture_manuscript",
    "fixture_plans",
    "fixture_state",
]


def fixture_impact_gold(fixture_id: str) -> Path:
    """The `GoldImpactSuite` beside them — which nodes a change must reach, and must not.

    The sixth artifact each golden book ships, and the last with no reader: `context_gold.json`
    went unreferenced until there was a packet to grade, and this went unreferenced until
    there was a propagation prediction to score. `plan/stage-0-decisions.md` records that
    pattern as the strongest form of consumer-first sequencing — the shape was not guessed.

    Ground truth, not input. Node granularity, no character offsets, and in-sample by
    construction.
    """
    return _fixture_file(fixture_id, "impact_gold.json")
