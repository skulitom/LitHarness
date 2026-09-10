"""Call-free census on isolated backup copies; original books and prose stay untouched."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RESEARCH = HERE.parent
LOCAL = ROOT / "runs/causal-reader-admission-20260910"
sys.path.insert(0, str(RESEARCH))

import bcr  # noqa: E402
import corpus_io  # noqa: E402

from litharness import cli  # noqa: E402
from litharness.adapters.sqlite_store import SqliteStore  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    holder = ROOT / "runs/box.lock/holder"
    if not holder.read_text(encoding="utf-8-sig").startswith("continuation-baseline-20260910:"):
        raise RuntimeError("Task does not own the shared-machine lock")
    progress = json.loads(
        (ROOT / "runs/continuation-baseline-20260910/progress.json").read_text(encoding="utf-8")
    )
    if progress["status"] != "finished":
        raise RuntimeError("Generation must finish before the census")
    if LOCAL.exists():
        raise RuntimeError("Census already exists; do not overwrite source snapshots")
    sources = [RESEARCH / f"corpora/fitness/fitness-{index:02d}.db" for index in range(20)]
    sources += [
        ROOT / f"runs/continuation-baseline-20260910/book-{index}/serial.db"
        for index in range(1, 4)
    ]
    sources += [ROOT / "runs/volume1/serial.db", ROOT / "runs/ab/pilot25/draw6/serial.db"]
    report = {
        "schema": "litharness.causal-reader-admission.v1",
        "model_calls": 0,
        "driver_sha256": sha(Path(__file__)),
        "runbook_sha256": sha(HERE / "RUNBOOK.md"),
        "pipeline_source": str(Path(cli.__file__).parents[2].relative_to(ROOT)),
        "salience_sha256": sha(Path(cli.__file__).parent / "domain/salience.py"),
        "loader_sha256": sha(RESEARCH / "corpus_io.py"),
        "chunker_sha256": sha(RESEARCH / "bcr.py"),
        "sources": [],
        "limitations": [
            "An admitted relation is not a validated reader or a literary quality label.",
            "Only state continuity currently has a deterministic ecological sibling generator.",
            "Current copies are not a reconstruction of the historical volume-screen inputs.",
            "Multiple revisions or branches of one book do not create independent books.",
            "Legacy stores may lack the evidence captured by newer production versions.",
        ],
    }
    for index, source in enumerate(sources):
        entry = {"path": source.relative_to(ROOT).as_posix(), "branches": []}
        report["sources"].append(entry)
        if not source.is_file():
            entry["unavailable"] = "source store missing"
            continue
        entry["sha256_before"] = sha(source)
        destination = LOCAL / f"source-{index:02d}"
        destination.mkdir(parents=True)
        backup = destination / "serial.db"
        # SQLite's backup API includes committed WAL state without modifying source records.
        with (
            contextlib.closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as origin,
            contextlib.closing(sqlite3.connect(backup)) as copied,
        ):
            origin.backup(copied)
        entry["backup_sha256_before_migration"] = sha(backup)
        try:
            # Migrate only the disposable copy; the source store is never opened writable.
            with SqliteStore.open(backup) as copied_store:
                branches = copied_store.branches()
            for book, branch, _head in branches:
                out = destination / book / branch
                output = io.StringIO()
                shape = (
                    ["--chapter-scenes", "1", "--arc-chapters", "6"]
                    if ("continuation-baseline-20260910" in source.parts)
                    else []
                )
                argv = [
                    "--database",
                    str(backup),
                    *shape,
                    "reader-evidence-audit",
                    "--book",
                    book,
                    "--branch",
                    branch,
                    "--out",
                    str(out),
                    "--json",
                ]
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                    code = cli.main(argv)
                branch_result = {"book_id": book, "branch_id": branch, "audit_exit": code}
                entry["branches"].append(branch_result)
                out.mkdir(parents=True, exist_ok=True)
                (out / "command.txt").write_text(output.getvalue(), encoding="utf-8", newline="\n")
                if code:
                    branch_result["error_kind"] = "cli_audit_failed"
                    branch_result["error_sha256"] = hashlib.sha256(
                        output.getvalue().encode()
                    ).hexdigest()
                    continue
                evidence = json.loads((out / "evidence-audit.json").read_text(encoding="utf-8"))
                units = corpus_io.generated_scenes(backup, book=book, branch=branch)
                text = "\n\n".join(unit.text for unit in units)
                (out / "manuscript.txt").write_text(text, encoding="utf-8", newline="\n")
                branch_result.update(
                    evidence=evidence,
                    exported_scenes=len(units),
                    exported_words=len(text.split()),
                    chunks=len(bcr.chunks(text)),
                    manuscript_sha256=hashlib.sha256(text.encode()).hexdigest(),
                    report_sha256=sha(out / "evidence-audit.json"),
                    public_sha256=sha(out / "battery.public.json"),
                    private_sha256=sha(out / "battery.private.json"),
                )
        except (OSError, ValueError, sqlite3.Error) as error:
            entry["error_kind"] = type(error).__name__
            error_path = destination / "error.txt"
            error_path.write_text(str(error), encoding="utf-8", newline="\n")
            entry["error_sha256"] = sha(error_path)
        entry["sha256_after"] = sha(source)
        entry["original_unchanged"] = entry["sha256_before"] == entry["sha256_after"]
        if not entry["original_unchanged"]:
            raise RuntimeError("A source database changed during the census")
        write(LOCAL / "progress.json", report)
        print(f"audited {entry['path']}: {len(entry['branches'])} branches", flush=True)
    write(HERE / "results.json", report)
    print(f"Census saved to {HERE / 'results.json'}; zero model calls")


if __name__ == "__main__":
    main()
