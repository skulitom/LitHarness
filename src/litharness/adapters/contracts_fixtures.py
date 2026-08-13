"""Finding the golden fixtures, which live in the contracts *checkout* and not in its wheel.

`litharness-contracts` ships schemas and dataclasses as a package, but the mystery and
litrpg fixture books sit under `fixtures/golden/` at the repository root — outside the
importable package, so `importlib.resources` cannot reach them and a wheel install does not
carry them. They still have to be findable, because §17's Stage 1 exit criterion names
those two books by name.

**Discovery is a chain, and every link is checked against the artifact rather than the
directory.** A path that exists but has no `manuscript.json` in it is not the contracts
checkout, and treating it as one produces a confusing failure three layers down.
`LITHARNESS_CONTRACTS_ROOT` comes first because LongRangeContext already established that
variable for the same question, and a second name for one setting is how two checkouts end
up configured differently. Hard-coding an absolute path is deliberately not in the chain:
PLAN.md §20.2 records a machine-bound `samefile("C:/DEV/litharness-contracts/schemas")` as
a defect worth fixing in a sibling, and reintroducing it here would be the same bug.
"""

from __future__ import annotations

import os
from pathlib import Path

import litharness_contracts as lc

#: The books §17 Stage 1 is graded against.
FIXTURE_IDS = ("mystery", "litrpg")

#: Where a checkout keeps them, relative to its root.
GOLDEN = Path("fixtures") / "golden"


class FixturesUnavailable(FileNotFoundError):
    """The contracts checkout, or the fixture inside it, could not be found.

    A `FileNotFoundError` so `cli.main` reports it as an operational fault (exit 2) — a
    missing checkout is the system failing to start, not the system reporting on its work.
    """


def _candidate_roots() -> list[Path]:
    configured = os.environ.get("LITHARNESS_CONTRACTS_ROOT")
    roots = [Path(configured)] if configured else []
    # An installed-from-source path dependency, which is what `pyproject.toml` declares:
    # `<root>/src/litharness_contracts/__init__.py` is three levels below the checkout.
    package = Path(lc.__file__).resolve()
    if len(package.parents) >= 3:
        roots.append(package.parents[2])
    # A sibling checkout, for the case where contracts is installed as a built wheel and
    # the package path lands in site-packages instead.
    roots.append(Path(__file__).resolve().parents[4] / "litharness-contracts")
    return roots


def _fixture_file(fixture_id: str, filename: str) -> Path:
    """Locate one artifact of a golden fixture, or say exactly how to fix it."""
    if fixture_id not in FIXTURE_IDS:
        raise FixturesUnavailable(
            f"unknown fixture {fixture_id!r}; the golden books are {', '.join(FIXTURE_IDS)}"
        )
    tried: list[Path] = []
    for root in _candidate_roots():
        candidate = root / GOLDEN / fixture_id / filename
        if candidate.is_file():
            return candidate
        tried.append(candidate)
    raise FixturesUnavailable(
        f"no {fixture_id} {filename} in any known contracts checkout (tried "
        + ", ".join(str(path) for path in tried)
        + "); set LITHARNESS_CONTRACTS_ROOT to the litharness-contracts checkout"
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
    "fixture_manuscript",
    "fixture_plans",
    "fixture_state",
]
