"""One isolated author-directed allocation trial, using unchanged production source."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUN = ROOT / "runs/opening-consequence-20260914"
BOOK = RUN / "book"
PREVIOUS = HERE.with_name("growth-continuation-20260913") / "run.py"
SPEC = importlib.util.spec_from_file_location("_opening_consequence_runner", PREVIOUS)
assert SPEC is not None and SPEC.loader is not None
DRIVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DRIVER)
BASE = DRIVER.BASE
for key, value in {"HERE": HERE, "ROOT": ROOT, "RUN": RUN, "BOOK": BOOK}.items():
    setattr(DRIVER, key, value)
for key, value in {
    "HERE": HERE, "ROOT": ROOT, "RUN": RUN,
    "OWNER": "opening-consequence-20260914:", "REVISION": "14fd7fb",
    "MAX_CALLS": 32, "MAX_TOKENS": 2_200_000, "MAX_SECONDS": 5400,
}.items():
    setattr(BASE, key, value)
sha, load, save = BASE.sha, BASE.load, BASE.save
CHAPTERS = DRIVER.CHAPTERS
validate, live = DRIVER.validate, DRIVER.live


def install_directions(database, directions):
    """Apply delegated research authoring through the existing policy-recorded lane."""
    import hashlib
    import os

    from litharness import cli
    from litharness.adapters.sqlite_store import SqliteStore
    from litharness.application.conductor import TickOutcome
    from litharness.application.directive_planner import DIRECTIVE_PLAN
    from litharness.domain.directives import Directive, DirectiveKind, DirectiveStatus

    if os.environ.get("LITHARNESS_ENV") != "test":
        raise RuntimeError("Direction installation requires the non-billing test registry")
    stamp, now = "2026-09-14T00:00:00Z", 1_789_344_000.0
    installed = []
    with SqliteStore.open(database) as store:
        [(book, branch, _)] = store.branches()
        args = cli.build_parser().parse_args(["--no-library", "tick"])
        conductor = cli._conductor(store, args)
        for index, (name, body) in enumerate(directions.items()):
            digest = hashlib.sha256(body.encode()).hexdigest()
            directive = Directive(
                directive_id=f"opening-consequence-{name}-{digest[:20]}",
                kind=DirectiveKind.CONSTRAINT, body=body, book_id=book, branch_id=branch,
                received_at=stamp, author="operator-delegated:opening-consequence-20260914",
                metadata={
                    "scope": "isolated registered authoring experiment",
                    "formulated_by": "Codex under the operator's continuation request",
                    "literal_user_quotation": False,
                },
            )
            if not store.submit_directive(directive, received_at=stamp):
                raise RuntimeError("Directions have already been installed")
            store.mark_directive_ingested(directive.directive_id, ingested_at=stamp)
            result = conductor.tick(now + index)
            if result.outcome is not TickOutcome.RAN_JOB or result.job_id is None:
                raise RuntimeError("The explicit direction did not run")
            if store.load_job(result.job_id).job_kind != DIRECTIVE_PLAN:
                raise RuntimeError("Preparation ran unexpected work")
            applied = store.load_directive(directive.directive_id)
            if applied.status is not DirectiveStatus.APPLIED:
                raise RuntimeError("Direction was not accepted through the verbatim lane")
            [logical_id] = applied.produced_constraint_ids
            decision = store.latest_decision_for(result.job_id)
            if decision is None or decision.profile != "directive.verbatim.v0":
                raise RuntimeError("Missing recorded direction policy")
            installed.append({
                "name": name, "directive_id": directive.directive_id,
                "logical_id": logical_id, "body_sha256": digest,
                "decision_id": decision.decision_id,
            })
    return installed


def prepare_inputs():
    DRIVER.prepare_inputs()
    directions = load(HERE / "directions.json")["pre_registration"]
    installed = install_directions(BOOK / "serial.db", directions)
    manifest = load(RUN / "manifest.json")
    if load(BOOK / "initial-world.json") != json.loads(
        DRIVER.must(["world", "show"], "directed-world")
    ):
        raise RuntimeError("Installing directions changed the seed world")
    manifest["fixtures"]["book"] = sha(BOOK / "serial.db")
    manifest["directions"] = installed
    scripts = [
        PREVIOUS, PREVIOUS.with_name("audit.py"), PREVIOUS.with_name("readout.py"),
        HERE / "directions.json", ROOT / "tests/test_opening_consequence_experiment.py",
    ]
    manifest["scripts"].update({p.relative_to(ROOT).as_posix(): sha(p) for p in scripts})
    baseline = ROOT / "runs/scene-focus-20260913"
    protected = [baseline / "progress.json", baseline / "book/serial.db"]
    protected += [HERE.with_name("scene-focus-20260913") / name
                  for name in ("evidence.json", "readout.json", "REPORT.md")]
    protected += sorted((baseline / "book/calls").glob("*.json"))
    protected += sorted((baseline / "book/library").glob("*/chapters/Chapter*.txt"))
    manifest["protected_inputs"].update({p.relative_to(ROOT).as_posix(): sha(p) for p in protected})
    save(RUN / "manifest.json", manifest)
    registration = load(HERE / "registration.json")
    registration.update(
        manifest_sha256=sha(RUN / "manifest.json"), directions=installed,
        direction_file_sha256=sha(HERE / "directions.json"),
        source_overrides={},
        contrast="historical opening versus first output with two delegated story constraints",
    )
    save(HERE / "registration.json", registration)
    print("Applied two recorded research directions; production source and seed are unchanged.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "inputs", "live"))
    {"prepare": BASE.prepare, "inputs": prepare_inputs, "live": live}[parser.parse_args().mode]()
