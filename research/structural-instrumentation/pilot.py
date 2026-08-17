"""§61 Add 2's wiring pilot: the extended summary call over the two frontier-arm books.

**A wiring validation, NOT a significance test — §61 said so before this file existed.**
"Add 2's acceptance is a wiring pilot, not a test: twenty-four frontier-arm scenes can show
effect direction for overdue-promise and zero-delta flags, and cannot show prediction at any
confidence worth recording." §57 already wrote down what happens when a run is sized for the
wrong question, and that entry does not need a sequel. What this run can say: the fold-in
schema parses on a live model, promises open and pay through the ledger, due-key defaulting
lands on the final scene key, and the zero-delta rate has a direction. What it cannot say:
whether either flag predicts anything a reader feels.

**Run it on a COPY of the book database.** With `--reset` (the default) it deletes the
book's existing `scene_summaries` and `promises` rows first, because migration 019's rows
predate the delta/promise columns and `record_scene_summary` is `INSERT OR IGNORE` on the
content hash — without the reset, every already-summarised scene keeps its pre-Add-2 row and
the model is never asked the new questions. `--keep` skips the reset for a database that has
never been summarised.

Spends live provider quota: one summary call per accepted scene, on the pinned frontier
provider (§64 — summaries route there now; the call class rides along as provenance). The
orchestrator decides when that spend happens; nothing here is invoked by the suite.

Usage:
    python research/structural-instrumentation/pilot.py path/to/book-copy.db
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from litharness.adapters.sqlite_store import SqliteStore  # noqa: E402
from litharness.application.repair import summary_job_for  # noqa: E402
from litharness.application.summarize import make_summary_handler  # noqa: E402
from litharness.domain.beats import TemplateMismatch, beats_for, template_for  # noqa: E402
from litharness.domain.nodes import NodeKind  # noqa: E402
from litharness.domain.promises import PROMISE_OPEN  # noqa: E402
from litharness.domain.text import content_hash  # noqa: E402
from litharness.providers import build_default_registry  # noqa: E402


def _reset(store: SqliteStore, book_id: str, branch_id: str) -> None:
    """Drop the book's pre-Add-2 summary rows and any prior pilot's ledger.

    Research-only surgery, which is why it lives here and not on the store: the production
    rule is that a summary under an unchanged hash is never recomputed, and this pilot's
    whole point is to recompute it under the extended schema. Run on a copy.
    """
    with store.transaction() as connection:
        connection.execute(
            "DELETE FROM scene_summaries WHERE book_id = ? AND branch_id = ?",
            (book_id, branch_id),
        )
        connection.execute(
            "DELETE FROM promises WHERE book_id = ? AND branch_id = ?",
            (book_id, branch_id),
        )


def run_book(store: SqliteStore, book_id: str, branch_id: str, *, reset: bool) -> dict[str, object]:
    head = store.head(book_id, branch_id)
    if head is None:
        return {"book_id": book_id, "branch_id": branch_id, "error": "no head revision"}
    if reset:
        _reset(store, book_id, branch_id)

    registry = build_default_registry()
    handle = make_summary_handler(registry, store, "pilot")

    scenes = [
        node
        for node in head.in_reading_order()
        if node.kind is NodeKind.SCENE and node.content
    ]
    for count, node in enumerate(scenes, start=1):
        assert node.content is not None
        job = summary_job_for(
            book_id=book_id,
            branch_id=branch_id,
            revision_id=head.revision_id,
            logical_id=node.logical_id,
            content_hash=content_hash(node.content),
        )
        handle(job, time.time())
        print(f"  summarised {node.logical_id} ({count}/{len(scenes)})", flush=True)

    ledger = store.promises(book_id, branch_id)
    opened = len(ledger)
    paid = sum(1 for promise in ledger if promise.status != PROMISE_OPEN)
    # At the end of the book, every still-open promise is overdue: due keys default to the
    # final scene key, so a promise the book ended without paying missed its latest date.
    final_key = None
    try:
        beats = beats_for(head, template_for(head))
        final_key = beats[-1].story_order_key
    except TemplateMismatch:
        pass
    overdue_at_end = [
        {"subject": promise.subject, "due": promise.due_key, "opened_at": promise.opened_at_key}
        for promise in ledger
        if promise.status == PROMISE_OPEN
    ]
    return {
        "book_id": book_id,
        "branch_id": branch_id,
        "scenes": len(scenes),
        "final_key": final_key,
        "promises_opened": opened,
        "promises_paid": paid,
        "overdue_at_end": overdue_at_end,
    }


def zero_delta_scenes(db_path: Path, book_id: str, branch_id: str) -> list[str]:
    """Scenes whose stored summary reported no extractable value shift."""
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        return [
            row["logical_id"]
            for row in connection.execute(
                "SELECT logical_id FROM scene_summaries WHERE book_id = ? AND branch_id = ? "
                "AND delta_json IS NULL ORDER BY logical_id",
                (book_id, branch_id),
            )
        ]
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("database", type=Path, help="a COPY of the book database")
    parser.add_argument(
        "--keep",
        action="store_true",
        help="do not delete existing scene_summaries/promises rows first",
    )
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    args = parser.parse_args()

    store = SqliteStore.open(args.database)
    try:
        reports = []
        for book_id, branch_id, _ in store.branches():
            print(f"book {book_id[:12]} / {branch_id[:12]}", flush=True)
            report = run_book(store, book_id, branch_id, reset=not args.keep)
            report["zero_delta_scenes"] = zero_delta_scenes(
                args.database, book_id, branch_id
            )
            reports.append(report)
    finally:
        store.close()

    if args.json:
        print(json.dumps(reports, indent=2, ensure_ascii=False))
        return 0
    for report in reports:
        if "error" in report:
            print(f"{report['book_id']}: {report['error']}")
            continue
        overdue = list(report["overdue_at_end"])
        zero = list(report["zero_delta_scenes"])
        print(
            f"\nbook {report['book_id']}: {report['scenes']} scene(s), "
            f"{report['promises_opened']} promise(s) opened, "
            f"{report['promises_paid']} paid, {len(overdue)} overdue at end"
        )
        for item in overdue:
            print(f"  overdue: {item['subject']} (opened {item['opened_at']}, due {item['due']})")
        print(f"  zero-delta scenes ({len(zero)}): {', '.join(zero) or '(none)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
