"""The bounded variation session against the fixed repair path, on the golden repair cases.

**What this measures, and the thing it deliberately cannot.** Both arms run the *same*
generator: one ordered ladder of replacement strings, handed out in the same order to
whichever harness asks. So nothing here compares models, prose, or judgment — it compares two
harnesses spending the same generator's output. That is the only comparison the deterministic
fake supports, and claiming more from it would be inventing a capability result out of a
mechanism benchmark.

The ladder's rungs are mechanical stand-ins, not prose. A failing rung is a replacement long
enough to move the node past `PatchPolicy.max_length_ratio`; the passing rung is the cited span
with its case changed, which is the same length and therefore clears every mechanical gate by
construction. Nothing in this file knows what good writing is and nothing in it should.

**The one asymmetry that is the point.** The fixed path cannot tell the model why a patch was
refused: `make_repair_handler` spends one call, records the decision, and the Conductor's retry
ladder re-runs the same prompt. The session path hands the refusal back as the exact gate
vector. The scripted agent uses only the *fact* of a refusal to decide its next action — it
never reads an oracle — so the arms differ in harness and in nothing else.

Usage, from the repository root:

    uv run python tools/variation_repair_comparison.py
    uv run python tools/variation_repair_comparison.py --json out.json

It writes no database anybody keeps and makes no paid call: `LITHARNESS_ENV=test` is set before
the registry is built, and the scripted provider declares `bills = False`.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

os.environ.setdefault("LITHARNESS_ENV", "test")

import litharness_contracts as lc

from litharness.adapters.contracts_fixtures import fixture_manuscript
from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.conductor import Conductor
from litharness.application.repair import (
    REPAIR_FINDING,
    make_repair_handler,
    repair_job_for,
)
from litharness.application.variation import (
    VARIATION_STEP,
    make_variation_repair_handler,
    make_variation_step_handler,
)
from litharness.domain.budget import BudgetPolicy
from litharness.domain.findings import Finding, Severity
from litharness.domain.generation import (
    CompletionRequest,
    CompletionResult,
    Usage,
)
from litharness.domain.jobs import JobStatus
from litharness.domain.revision import (
    Revision,
    import_manuscript,
    node_version_id,
)
from litharness.domain.text import content_hash
from litharness.domain.variation import VariationObjective, session_id_for
from litharness.providers.base import parse_schema_payload
from litharness.providers.registry import ProviderRegistry

PROJECT_ID = "11111111-1111-5111-8111-111111111111"
#: The same injected instant the suite uses, so a rerun is byte-identical.
START = 1_760_000_000.0
#: Ticks one case may take before the driver gives up. Above anything either arm can reach:
#: the fixed path stops at `Job.max_attempts` = 3 and the session at its own step ceiling of
#: 12, so a case that hits this cap is a defect in the driver, not a result.
MAX_TICKS = 60
#: How far a failing rung overshoots the node's length. Three times the whole node guarantees
#: the result exceeds `PatchPolicy.max_length_ratio` of 2.0 whatever the scene's length is.
OVERSHOOT = 3


def _day(now: float) -> str:
    """The day key `spend_on` reads, derived the way every handler derives it."""
    return datetime.fromtimestamp(now, tz=UTC).date().isoformat()


@dataclass
class LadderProvider:
    """One generator, two harnesses. Deterministic, free, and identical across arms.

    It answers both schemas the comparison needs. Asked for a bare replacement — the fixed
    path's shape — it hands out the next rung. Asked for a mediated action, it runs the minimal
    loop the session's surface allows: evaluate what was proposed, commit what evaluated
    cleanly, otherwise propose the next rung. The branch reads the prompt's own status line
    rather than any state the harness did not show it, which is what keeps the arms comparable.
    """

    rungs: list[str]
    name: str = "ladder"
    bills: bool = False
    model: str = "ladder-v1"
    calls: int = 0
    handed_out: int = 0

    def health(self) -> bool:
        return True

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.calls += 1
        properties = (request.schema or {}).get("properties", {})
        if "action" in properties:
            payload = self._action(request.prompt)
        else:
            payload = {"replacement": self._next()}
        text = json.dumps(payload, sort_keys=True)
        return CompletionResult(
            text=text,
            provider=self.name,
            model=self.model,
            usage=Usage(
                input_tokens=len(request.prompt) // 4, output_tokens=len(text) // 4
            ),
            parsed=parse_schema_payload(text, request.schema),
            schema_requested=True,
            cost_usd=0.0,
            wall_ms=0,
            raw={},
        )

    def _next(self) -> str:
        rung = self.rungs[min(self.handed_out, len(self.rungs) - 1)]
        self.handed_out += 1
        return rung

    def _action(self, prompt: str) -> dict[str, str]:
        if "(proposed)" in prompt:
            return {"action": "evaluate_candidate"}
        if "(evaluated)" in prompt:
            return {"action": "commit"}
        if self.handed_out >= len(self.rungs):
            return {"action": "stop", "reason": "the ladder is exhausted"}
        return {
            "action": "propose_candidate",
            "replacement": self._next(),
            "strategy": "local_patch",
        }


@dataclass(frozen=True)
class Case:
    """One book, one located complaint, and the rung at which the ladder starts working."""

    book: str
    logical_id: str
    good_at: int | None
    rungs: int = 5

    @property
    def name(self) -> str:
        where = "never" if self.good_at is None else f"rung{self.good_at}"
        return f"{self.book}:{where}"


def sample_revision() -> Revision:
    """The six-scene book the repair tests are written against.

    Imported from the suite rather than restated, because the point of a golden case is that it
    is the *same* case the tests exercise; a second copy would drift on the first edit to either.
    """
    from tests.conftest import make_revision

    return make_revision()


def fixture_revision(fixture_id: str) -> Revision:
    source = lc.parse_artifact(
        lc.ManuscriptRevision,
        json.loads(fixture_manuscript(fixture_id).read_text(encoding="utf-8")),
    )
    return import_manuscript(source, preserve_content=True).revision


def revision_for(book: str) -> Revision:
    return sample_revision() if book == "sample" else fixture_revision(book)


def planted_finding(revision: Revision, logical_id: str) -> tuple[Finding, str]:
    """A blocking, deterministic complaint over the first twenty characters of a scene.

    Twenty characters keeps the cited fraction far below `PatchPolicy.max_cited_fraction` on
    every book here, so the only mechanical veto a replacement string can provoke is the length
    one — which is stated in the report, because it is why every failure in this benchmark
    carries the same signature.
    """
    node = revision.node(logical_id)
    text = node.content or ""
    start, end = 0, 20
    span = lc.EvidenceSpan(
        source=lc.ResourceRef(
            project_id=PROJECT_ID,
            book_id=revision.book_id,
            branch_id=revision.branch_id,
            logical_id=logical_id,
            kind=lc.ResourceKind.MANUSCRIPT_SCENE,
            version_id=node_version_id(node),
        ),
        start=start,
        end=end,
        content_sha256=content_hash(text[start:end]),
    )
    finding = Finding(
        finding_id="f-comparison",
        category="continuity",
        severity=Severity.MAJOR,
        message="This passage contradicts established canon and must be restated.",
        rule_or_critic_id="comparison.planted.v0",
        logical_id=logical_id,
        confidence_basis=lc.ConfidenceBasis.DETERMINISTIC.value,
        run_id="run-comparison",
        source={"primary_span": lc.to_jsonable(span)},
    )
    return finding, text[start:end]


def ladder_for(case: Case, revision: Revision, span_text: str) -> list[str]:
    """The rungs, in the order both arms receive them.

    Every failing rung is a distinct length, so a repeat of the *same* patch never happens by
    accident and the repeat-patch stall predicate measures what it is for rather than an
    artefact of the fixture.
    """
    node_length = len(revision.node(case.logical_id).content or "")
    good = span_text.upper()
    rungs: list[str] = []
    for index in range(case.rungs):
        if case.good_at is not None and index + 1 == case.good_at:
            rungs.append(good)
        else:
            rungs.append("x" * (node_length * OVERSHOOT + index))
    return rungs


def seed(store: SqliteStore, revision: Revision, finding: Finding) -> None:
    store.commit_revision(revision, created_at="2026-08-21T00:00:00Z")
    store.record_findings(
        revision.book_id,
        revision.branch_id,
        (finding,),
        created_at="2026-08-21T00:00:00Z",
        revision_id=revision.revision_id,
    )


@dataclass
class Result:
    case: str
    arm: str
    committed: bool
    provider_calls: int
    actions: int
    tokens: int
    gate_runs: int
    gate_passes: int
    repeated_failures: int
    failures: int
    outcome: str
    signatures: list[str] = field(default_factory=list)


def _signature(gates: Sequence[Any]) -> str | None:
    """The failing (rule, vetoes) signature of one gate run, or None when it passed."""
    parts = [
        f"{gate['rule_or_critic_id']}:{','.join(sorted(gate.get('vetoes') or []))}"
        for gate in gates
        if gate.get("gate") == "shape" and not gate.get("passed")
    ]
    return "; ".join(sorted(parts)) or None


def _gate_runs(store: SqliteStore, session_id: str | None) -> list[list[dict[str, Any]]]:
    """Every `shape.patch.v0` run this case performed, in the order it performed them.

    Read out of storage rather than counted in the driver, because a metric computed from a
    counter the driver kept would be measuring the driver. Decisions carry the fixed path's
    runs and the session's commit re-gate; attempt rows carry the session's evaluations.
    """
    runs: list[tuple[int, list[dict[str, Any]]]] = []
    for order, row in enumerate(
        store._connection.execute(
            "SELECT gates FROM policy_decisions ORDER BY rowid"
        )
    ):
        gates = [
            gate
            for gate in json.loads(row["gates"])
            if gate.get("rule_or_critic_id") == "shape.patch.v0"
        ]
        if gates:
            runs.append((order, gates))
    if session_id is not None:
        for order, row in enumerate(
            store._connection.execute(
                "SELECT evaluation FROM variation_attempts WHERE session_id = ? "
                "ORDER BY ordinal",
                (session_id,),
            )
        ):
            gates = [
                gate
                for gate in json.loads(row["evaluation"])
                if gate.get("rule_or_critic_id") == "shape.patch.v0"
            ]
            if gates:
                runs.append((order - 1000, gates))
    return [gates for _, gates in sorted(runs, key=lambda item: item[0])]


def run_case(case: Case, arm: str, *, budget: BudgetPolicy) -> Result:
    revision = revision_for(case.book)
    finding, span_text = planted_finding(revision, case.logical_id)
    provider = LadderProvider(ladder_for(case, revision, span_text))
    registry = ProviderRegistry(provider)

    with tempfile.TemporaryDirectory() as directory:
        store = SqliteStore.open(Path(directory) / "comparison.db")
        try:
            seed(store, revision, finding)
            job = repair_job_for(
                finding,
                book_id=revision.book_id,
                branch_id=revision.branch_id,
                revision_id=revision.revision_id,
                repair_depth=1,
            )
            assert job is not None
            store.enqueue(job)

            if arm == "fixed":
                handlers = {
                    REPAIR_FINDING: make_repair_handler(
                        registry, store, PROJECT_ID, budget=budget
                    )
                }
            else:
                handlers = {
                    REPAIR_FINDING: make_variation_repair_handler(
                        registry, store, PROJECT_ID, budget=budget
                    ),
                    VARIATION_STEP: make_variation_step_handler(
                        registry, store, PROJECT_ID, budget=budget
                    ),
                }
            conductor = Conductor(
                store=store,
                holder="comparison",
                project_id=PROJECT_ID,
                registry=registry,
                handlers=handlers,
            )

            ticks = 0
            while ticks < MAX_TICKS:
                # QUEUED *and* FAILED, because the fixed path's retry is the Conductor's:
                # a refused patch fails the unit and `requeue_failed` revives it at the top of
                # the next tick. A driver watching only the queue would stop after one attempt
                # and report the control arm as a single-shot path it is not.
                pending = [
                    unit
                    for status in (JobStatus.QUEUED, JobStatus.FAILED)
                    for unit in store.jobs_by_status(status)
                    if unit.job_kind in {REPAIR_FINDING, VARIATION_STEP}
                ]
                if not pending:
                    break
                conductor.tick(START + ticks)
                ticks += 1

            head = store.head(revision.book_id, revision.branch_id)
            committed = head is not None and head.revision_id != revision.revision_id

            session_id: str | None = None
            outcome = "poisoned_or_parked"
            actions = provider.calls
            if arm == "session":
                session_id = session_id_for(
                    job.job_id, VariationObjective.CANDIDATE_REPAIR
                )
                session = store.variation_session(session_id)
                assert session is not None
                outcome = (
                    session.outcome.value if session.outcome else session.status.value
                )
                actions = session.steps
            elif committed:
                outcome = "committed"

            runs = _gate_runs(store, session_id)
            signatures = [_signature(gates) for gates in runs]
            failures = [signature for signature in signatures if signature]
            repeated = sum(
                1
                for index in range(1, len(signatures))
                if signatures[index] and signatures[index] == signatures[index - 1]
            )
            spend = store.spend_on(_day(START))
            return Result(
                case=case.name,
                arm=arm,
                committed=committed,
                provider_calls=provider.calls,
                actions=actions,
                tokens=spend.tokens,
                gate_runs=len(runs),
                gate_passes=sum(1 for signature in signatures if signature is None),
                repeated_failures=repeated,
                failures=len(failures),
                outcome=outcome,
                signatures=[signature or "pass" for signature in signatures],
            )
        finally:
            store.close()


CASES = [
    Case(book, logical_id, good_at)
    for book, logical_id in (("sample", "scene-1"), ("mystery", "scene-1"), ("litrpg", "scene-1"))
    for good_at in (1, 2, 3, 4, None)
]


def summarise(results: Sequence[Result]) -> dict[str, Any]:
    commits = sum(1 for result in results if result.committed)
    gate_runs = sum(result.gate_runs for result in results)
    gate_passes = sum(result.gate_passes for result in results)
    failures = sum(result.failures for result in results)
    return {
        "cases": len(results),
        "commits": commits,
        "gate_runs": gate_runs,
        "gate_pass_rate": (gate_passes / gate_runs) if gate_runs else None,
        "provider_calls": sum(result.provider_calls for result in results),
        "tokens": sum(result.tokens for result in results),
        "calls_per_commit": (
            sum(result.provider_calls for result in results) / commits if commits else None
        ),
        "tokens_per_commit": (
            sum(result.tokens for result in results) / commits if commits else None
        ),
        "actions_per_commit": (
            sum(result.actions for result in results) / commits if commits else None
        ),
        "repeated_failure_rate": (
            sum(result.repeated_failures for result in results) / failures
            if failures
            else None
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, help="write the full result set here")
    args = parser.parse_args()

    budget = BudgetPolicy()
    results = [
        run_case(case, arm, budget=budget) for case in CASES for arm in ("fixed", "session")
    ]

    print(f"{'case':<20}{'arm':<10}{'commit':<8}{'calls':<7}{'acts':<6}{'gates':<7}{'outcome'}")
    for result in results:
        print(
            f"{result.case:<20}{result.arm:<10}"
            f"{'yes' if result.committed else 'no':<8}"
            f"{result.provider_calls:<7}{result.actions:<6}"
            f"{result.gate_passes}/{result.gate_runs:<4} {result.outcome}"
        )

    report: dict[str, Any] = {}
    for arm in ("fixed", "session"):
        arm_results = [result for result in results if result.arm == arm]
        report[arm] = summarise(arm_results)
        print(f"\n{arm}: {json.dumps(report[arm], indent=2)}")

    if args.json:
        args.json.write_text(
            json.dumps(
                {
                    "summary": report,
                    "results": [vars(result) for result in results],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
