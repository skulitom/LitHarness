"""Ingesting an evaluator's findings, which is how a sibling's detectors reach the gate.

§8.4 puts the LitRPG rule and predicate vocabulary in ContinuityEvaluation's game-mechanics
pack, and §13's consumption rule is that siblings depend on contracts and never on each other.
That leaves exactly one shape for the integration, and this module is it: the evaluator writes
an `EvaluationArtifact`, LitHarness reads it, and the only thing either project knows about
the other is a schema they both already depend on.

**This is deliberately not a plugin loader.** No import of a sibling package, no entry point,
no subprocess contract — a file of a known schema, produced by whatever ran, read by whatever
needs it. That is what makes ContinuityEvaluation's pack usable from here today while §8.4's
ownership stays where it is, and it is why swapping the evaluator later is a configuration
change rather than a port.

**Re-anchoring, for the third artifact in a row.** A foreign artifact's `scope.book_id` is
the *producer's* book id, and for the golden fixtures that is the contracts UUID5 rather than
the sha256 address this store minted on import — the same mismatch `import_manuscript`,
`import_plan` and `import_state` each had to handle. So the local book and branch are supplied
by the caller and the artifact's own scope is kept inside `finding_json` as provenance.

**Findings are ingested, never trusted as canon.** An artifact says a detector found
something; it does not say the finding is right, and `status` is what carries that
distinction. Nothing here promotes `OPEN` to `CONFIRMED` — that is a decision, and decisions
are recorded by the policy engine.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import litharness_contracts as lc

from litharness.domain.findings import Finding


class EvaluationArtifactUnreadable(ValueError):
    """The file is not an evaluation artifact this version can read.

    A `ValueError` so `cli.main` reports it as an operational fault (exit 2): a malformed
    artifact is the system failing to read its input, not the system reporting on the book.
    """


def parse_artifact(payload: object) -> lc.EvaluationArtifact:
    """Parse, converting every failure mode into one this package's exit codes understand.

    Broad on purpose: `lc.parse_artifact` raises `KeyError`, `TypeError` and `ValueError`
    depending on which layer of the artifact is malformed, and a caller that had to know which
    would be coupled to the contract's internals rather than to its schema.
    """
    try:
        artifact: lc.EvaluationArtifact = lc.parse_artifact(lc.EvaluationArtifact, payload)
    except Exception as error:
        raise EvaluationArtifactUnreadable(
            f"not a readable EvaluationArtifact: {type(error).__name__}: {error}"
        ) from error
    return artifact


@dataclass(frozen=True, slots=True)
class Evaluation:
    """One evaluator run: what it found, and whether it finished.

    The second half is the point. `EvaluationArtifact` has carried `errors` since 1.0 and this
    adapter read only `findings`, so a run in which **every detector failed** was ingested as
    a clean book: zero findings, zero blocking, exit 0. Reproduced against the real litrpg
    artifact with six `evidence_resolution` errors substituted for its eight findings —
    `ingest` printed "0 finding(s), 0 new, 0 blocking" and `findings` printed
    "(0 shown, 0 blocking)", both exit 0, over a book carrying six planted defects.

    That is not a corner case, and §17 Stage 2 is where it bites: "repairs verified by
    re-detection" means re-running an evaluator over prose a repair has just changed, and a
    repair invalidates the `version_id` every downstream evidence span cites **by
    construction**. So an errored run is the *expected* post-repair state, and reading it as a
    clean bill would score a repair that fixed nothing as perfect.

    An incomplete evaluation is not a passing one. `errors` travels with the findings so no
    caller can spend the second without noticing the first.
    """

    run_id: str
    findings: list[Finding]
    errors: tuple[lc.EvaluationError, ...] = ()

    @property
    def complete(self) -> bool:
        return not self.errors

    def summarise_errors(self) -> str:
        """One line per distinct stage and reason, with a count — an evaluator that failed
        the same way six times is one problem, not six."""
        seen: dict[tuple[str, str], int] = {}
        for error in self.errors:
            seen[(error.stage, error.reason)] = seen.get((error.stage, error.reason), 0) + 1
        return "; ".join(
            f"{stage}: {reason} (x{count})" if count > 1 else f"{stage}: {reason}"
            for (stage, reason), count in sorted(seen.items())
        )


def load_findings(path: str | Path) -> Evaluation:
    """Read an evaluation artifact from disk.

    Explicit UTF-8, for the reason `cli import` records: the default codec on this platform is
    cp1252, and a finding message quoting an em-dash from the manuscript would decode into
    three characters — silently, because nothing downstream hashes a message.
    """
    artifact = parse_artifact(
        json.loads(Path(path).read_text(encoding="utf-8"))
    )
    return Evaluation(
        run_id=artifact.run_id,
        findings=[
            Finding.from_contract(finding, run_id=artifact.run_id)
            for finding in artifact.findings
        ],
        errors=tuple(artifact.errors),
    )


__all__ = [
    "Evaluation",
    "EvaluationArtifactUnreadable",
    "load_findings",
    "parse_artifact",
]
