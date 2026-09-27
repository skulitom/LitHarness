"""Build the scoped synthetic prerequisite probe and record the natural-text boundary."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent
ROOT = RESEARCH.parents[1]
SOURCE_REVISION = "0c1b306d3d401eda38cec60067d131ec6ab4a313367fdcf95c719baf303892a8"
sys.path.insert(0, str(RESEARCH))

import corpus_io  # noqa: E402
import prerequisite_certificate as probe  # noqa: E402


def write(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def attacks(bundle: probe.Bundle) -> dict[str, object]:
    core = [clause for clause in bundle.contradiction.clauses
            if clause.identity in bundle.contradiction.core]
    statements = [bundle.damaged[clause.start:clause.end] for clause in core]
    dark = "At noon during trial zero, the coral lamp was dark."
    return {
        "minimal_core": not probe.solve("\n".join(statements)).consistent and all(
            probe.solve("\n".join(statements[:i] + statements[i + 1:])).consistent
            for i in range(len(statements))
        ),
        "other_instant_has_consistent_witness": probe.solve(bundle.damaged.replace(
            dark, "At dusk during trial zero, the coral lamp was dark.",
        )).consistent,
        "other_trial_has_consistent_witness": probe.solve(bundle.damaged.replace(
            dark, "At noon during trial one, the coral lamp was dark.",
        )).consistent,
        "lit_does_not_force_open": probe.solve(bundle.original).consistent,
    }


def natural_boundary(
    database: Path, out: Path, *, expected_revision: str | None = None,
) -> dict[str, object]:
    from litharness.adapters.sqlite_store import SqliteStore
    from litharness.application.export import resolve_branch

    original_digest = file_hash(database)
    snapshot = out / "source.db"
    with SqliteStore.open_read_only(database) as original:
        book, branch = resolve_branch(original, None, None)
        original.backup_to(snapshot)
    # The shared loader may open a store writable. It receives only this disposable snapshot,
    # after an explicit read-only schema check, never the original book.
    with SqliteStore.open_read_only(snapshot) as store:
        head = store.head(book, branch)
        if head is None:
            raise ValueError("missing manuscript head")
        revision_id = head.revision_id
        if expected_revision is not None and revision_id != expected_revision:
            raise ValueError("manuscript head differs from the runbook's source")
    units = corpus_io.generated_scenes(snapshot, book=book, branch=branch, min_words=0)
    if not units:
        raise ValueError("source has no readable scenes")
    write(out / "natural-scenes.private.json", [asdict(unit) for unit in units])
    observations = []
    for unit in units:
        try:
            result = probe.solve(unit.text)
            disposition = (
                "closed_language_consistent" if result.consistent else "closed_language_conflict"
            )
            failure = None
        except probe.Refused as error:
            disposition = "unsupported_source"
            failure = {"reason": error.reason, "start": error.start, "end": error.end}
        observations.append({
            "unit_id": unit.unit_id, "source_sha256": probe.digest(unit.text),
            "characters": len(unit.text), "disposition": disposition, "refusal": failure,
        })
    after = file_hash(database)
    if after != original_digest:
        raise RuntimeError("original database bytes changed during the boundary check")
    return {
        "book_id": book, "branch_id": branch, "revision_id": revision_id,
        "original_sha256_before": original_digest, "original_sha256_after": after,
        "snapshot_sha256": file_hash(snapshot),
        "source_access": "read-only original; consistent backup; shared export loader on backup",
        "role": "inspected development book; no holdout or prevalence claim",
        "scenes": observations,
        "ecological_admission": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError("preserve the existing run")
    args.out.mkdir(parents=True)
    bundles = probe.fixture_bundles()
    public, private = probe.packets(bundles)
    write(args.out / "packets.public.json", public)
    write(args.out / "keys.private.json", private)
    boundary = natural_boundary(args.database, args.out, expected_revision=SOURCE_REVISION)
    sources = (
        Path(probe.__file__), Path(corpus_io.__file__), Path(__file__), HERE / "RUNBOOK.md",
        ROOT / "tests/test_prerequisite_certificate.py", ROOT / "uv.lock",
        ROOT / "src/litharness/adapters/sqlite_store.py",
        ROOT / "src/litharness/application/export.py",
    )
    report = {
        "schema": "litharness.scoped-prerequisite-construction.v1",
        "model_calls": 0, "synthetic_cases": [bundle.manifest() for bundle in bundles],
        "controlled_family_count": 1,
        "attacks": attacks(bundles[0]),
        "natural_text_boundary": boundary,
        "source_digests": {path.relative_to(ROOT).as_posix(): file_hash(path) for path in sources},
        "artifact_sha256": {name: file_hash(args.out / name) for name in (
            "packets.public.json", "keys.private.json", "natural-scenes.private.json",
        )},
        "decision": "LOGIC_CERTIFIED_FOR_CLOSED_LANGUAGE_ONLY",
        "ecological_admission": False,
        "eligible_for_model_run": False,
        "production_authority": False,
    }
    write(args.out / "report.json", report)
    print(json.dumps({
        "synthetic_cases": len(bundles), "attacks": report["attacks"],
        "natural_scenes": len(boundary["scenes"]), "decision": report["decision"],
        "ecological_admission": False, "report": str(args.out / "report.json"),
    }, indent=2))


if __name__ == "__main__":
    main()
