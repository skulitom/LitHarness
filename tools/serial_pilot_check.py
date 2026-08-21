"""The gate between the loop and the acceptance read — `plan/serial-pilot-1.md` §6.

**Why this exists, measured rather than imagined.** A full rehearsal of the pilot's command
sequence on the deterministic fake (2026-08-21, scratch store, no paid call) drafted all eight
scenes to completion while *every* interpretive directive and the outline job had poisoned.
The loop printed nothing alarming, the library published a complete-looking two-chapter book,
and the tone note, the arc note and both chapter notes had reached no plan revision at all.
That is §4.1 working as designed — "a blocked or parked item never stalls the queue" — and it
is exactly the state in which reading the book would be worthless: the operator's taste never
reached the prose, and §6 spends the candidate's single consultation either way.

So the loop finishing is not the signal to read. This is. It answers one question — *is this
book fit to spend the one acceptance read on* — and exits non-zero when it is not.

Nothing here judges prose. Every check is structural: did the direction land, did the outline
cover the book, is anything stopped, does the store rebuild, is the reading copy whole. A
quality claim from a two-chapter run is forbidden by §0 of the package regardless of what any
of these say.

Usage (from the repository root):

    uv run python tools/serial_pilot_check.py --database serial.db
    uv run python tools/serial_pilot_check.py --database serial.db --phase directives

`--phase directives` is the earlier gate: run it after the first ~9 ticks, before the loop has
spent a paid call on prose. A directive that poisoned is cheap to fix then (re-issue it; a new
`received_at` mints a new directive id and a new job) and expensive to find afterwards.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import export as export_module
from litharness.domain.beats import scene_nodes
from litharness.domain.directives import DirectiveStatus
from litharness.domain.extraction import STATUS_PREDICATE, sheet_for
from litharness.domain.jobs import JobStatus
from litharness.domain.plans import scene_plan_for

#: What the pilot declared. Kept here so a drifted run is caught rather than described.
EXPECTED_SCENES = 8
EXPECTED_DIRECTIVES = 8

OK = "  ok   "
BAD = " FAIL  "
NOTE = " note  "


class Report:
    """Lines plus a verdict. Collected rather than printed as they are found, so the
    verdict can be stated before the detail an operator would otherwise scroll past."""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.failures: list[str] = []

    def check(self, passed: bool, headline: str, detail: str = "") -> bool:
        self.lines.append(f"{OK if passed else BAD}{headline}")
        if detail:
            self.lines.append(f"         {detail}")
        if not passed:
            self.failures.append(headline)
        return passed

    def note(self, headline: str, detail: str = "") -> None:
        self.lines.append(f"{NOTE}{headline}")
        if detail:
            self.lines.append(f"         {detail}")


def _one_branch(store: SqliteStore, report: Report) -> tuple[str, str] | None:
    """The store's single book, or None.

    **More than one branch is a failure, not a detail.** `planner._resolved_directive_scope`
    materialises an unscoped directive only when exactly one branch matches; a second book in
    this store would silently strand every directive the pilot issued without `--book`.
    """
    branches = store.branches()
    if not report.check(
        len(branches) == 1,
        f"store holds exactly one branch ({len(branches)} found)",
        "an unscoped directive is materialised only when its destination is unambiguous",
    ):
        return None
    book_id, branch_id, _ = branches[0]
    return book_id, branch_id


def _directives(store: SqliteStore, report: Report) -> None:
    counts = {status.value: len(store.directives_by_status(status)) for status in DirectiveStatus}
    total = sum(counts.values())
    report.check(
        total == EXPECTED_DIRECTIVES,
        f"{total} directive(s) in the inbox, expected {EXPECTED_DIRECTIVES}",
        "four constraints, one tone note, one arc note, two chapter notes (§4)",
    )
    received = store.directives_by_status(DirectiveStatus.RECEIVED)
    report.check(
        not received,
        f"{len(received)} directive(s) still unread",
        "a directive that never left `received` reached no plan revision and shaped no scene",
    )
    for directive in received:
        report.note(
            f"unread: {directive.kind.value} {directive.directive_id}",
            directive.body[:90] + ("..." if len(directive.body) > 90 else ""),
        )
    conflicted = store.directives_by_status(DirectiveStatus.CONFLICTED)
    report.check(not conflicted, f"{len(conflicted)} directive(s) conflicted")
    report.note("directive statuses", ", ".join(f"{k}={v}" for k, v in counts.items() if v))


def _jobs(store: SqliteStore, report: Report) -> None:
    counts = store.job_counts_by_status()
    parked = store.jobs_by_status(JobStatus.PARKED)
    poisoned = store.jobs_by_status(JobStatus.POISONED)
    report.check(
        not parked,
        f"{len(parked)} parked unit(s)",
        "parked is revivable: fix the cause, then `litharness revive <job_id>`",
    )
    for job in parked:
        report.note(f"parked: {job.job_kind} {job.job_id}", job.error or "")
    report.check(
        not poisoned,
        f"{len(poisoned)} poisoned unit(s)",
        "poisoned is NOT revivable — `revive` refuses it; re-issue the directive or "
        "let a plan-epoch bump re-mint the job",
    )
    for job in poisoned:
        report.note(f"poisoned: {job.job_kind} {job.job_id}", job.error or "")
    report.note("jobs", ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "none")


def _outline(store: SqliteStore, report: Report, book_id: str, branch_id: str) -> None:
    plan = store.plan_revision(book_id, branch_id)
    if not report.check(plan is not None, "the book has a plan revision"):
        return
    head = store.head(book_id, branch_id)
    if head is None:
        report.check(False, "the book has a head revision")
        return
    scenes = scene_nodes(head)
    stated = [sid for sid in scenes if scene_plan_for(plan.items, sid) is not None]
    report.check(
        len(stated) == len(scenes),
        f"outline covers {len(stated)} of {len(scenes)} scene(s)",
        "a scene with no statement drafts exactly as it did before outlines existed",
    )
    locked = sum(1 for item in plan.items if item.locked)
    report.note(f"plan holds {len(plan.items)} item(s), {locked} locked")


def _prose(store: SqliteStore, report: Report, book_id: str, branch_id: str) -> None:
    document = export_module.collect(
        store,
        book_id=book_id,
        branch_id=branch_id,
        generated_at=datetime.now(tz=UTC).isoformat(),
    )
    report.check(
        document.total == EXPECTED_SCENES,
        f"the book holds {document.total} scene(s), expected {EXPECTED_SCENES}",
    )
    report.check(
        document.drafted == document.total,
        f"{document.summary}",
        "a withheld chapter is one holding an undrafted scene; the library publishes neither",
    )
    for scene in document.scenes:
        if not scene.drafted:
            report.note(f"undrafted: {scene.logical_id} ({scene.label})")


def _state(store: SqliteStore, report: Report, book_id: str, branch_id: str) -> None:
    """Did the book's own prose ever speak system voice back?

    C2 asks for a `[STATUS]` line whenever a number changes, and `extract_state` reads it
    back. A book that wrote none, or wrote them in a form the parser does not accept, is
    indistinguishable from one that established no state — which is the failure
    `domain/extraction.py` names in its own docstring. The seed record is the one that was
    given; anything beyond it was read off the page.
    """
    records = store.state_records(book_id, branch_id)
    read_back = [r for r in records if r.evidence]
    seeded = len(records) - len(read_back)
    report.check(
        bool(read_back),
        f"{len(read_back)} state record(s) read off the book's own prose "
        f"({len(records)} total, {seeded} seeded)",
        "zero means no `[STATUS]` line the parser accepted — C2 did not take",
    )
    subjects = sorted({r.subject for r in records})
    report.note("state subjects", ", ".join(subjects) or "none")


def _sheet(store: SqliteStore, report: Report, book_id: str, branch_id: str) -> None:
    """Does the book's declared line match the numbers its canon holds?

    A mismatch has no symptom. `extract_state` would read the book with a line its own canon
    does not use, match nothing, and leave a book that established plenty looking exactly like
    one that established nothing — so this is checked in the *early* gate, before a paid call
    is spent on prose written against it.
    """
    records = store.state_records(book_id, branch_id)
    sheet = sheet_for(records)
    report.note("status sheet", " | ".join(field.label for field in sheet.fields))
    for snapshot in records:
        if snapshot.predicate != STATUS_PREDICATE or not isinstance(snapshot.value, Mapping):
            continue
        extra = sorted(set(snapshot.value) - set(sheet.value_keys))
        missing = sorted(set(sheet.value_keys) - set(snapshot.value))
        report.check(
            not extra and not missing,
            f"{snapshot.record_id}: snapshot keys match the declared sheet",
            f"extra={extra or 'none'} missing={missing or 'none'}",
        )




def _promises(store: SqliteStore, report: Report, book_id: str, branch_id: str) -> None:
    """The §5 read-back. Reported, never gated — §5 says divergence is pilot data.

    One caveat the pilot's table cannot see: `promise_id_for` keys a promise on
    `(book_id, subject)` and nothing else, deliberately, so two promises about the same
    subject are **one row**. §5's P1 and P4 are both plausibly subject `silas`.
    """
    rows = store.promises(book_id, branch_id)
    open_rows = [p for p in rows if p.status != "paid"]
    paid_rows = [p for p in rows if p.status == "paid"]
    report.note(
        f"promise ledger: {len(rows)} row(s), {len(open_rows)} open, {len(paid_rows)} paid",
        "the ledger is written by the scene_summary handler and nowhere else",
    )
    for promise in rows:
        report.note(
            f"  {promise.status:<6} {promise.subject:<16} "
            f"opened {promise.opened_at_key} due {promise.due_key}",
            promise.description[:80],
        )


def _spend(store: SqliteStore, report: Report) -> None:
    day = datetime.now(tz=UTC).date().isoformat()
    spend = store.spend_on(day)
    digest = store.digest(day)
    report.note(
        f"spend today: {spend.invocations} call(s), {spend.tokens} tokens"
        + (f", ${spend.cost_usd:.2f}" if spend.cost_usd else ""),
        "the per-process health probe is a real billed call and appears in none of these",
    )
    omitted = digest.get("context_omitted", 0)
    report.check(
        omitted == 0,
        f"context_omitted = {omitted}",
        "nonzero means a scene was drafted without part of the book behind it; "
        "raise --context-budget",
    )
    report.note("digest today", ", ".join(f"{k}={v}" for k, v in sorted(digest.items())))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="serial_pilot_check",
        description="Is this pilot fit to spend the one acceptance read on?",
    )
    parser.add_argument("--database", type=Path, default=Path("serial.db"))
    parser.add_argument(
        "--phase",
        choices=("directives", "full"),
        default="full",
        help="`directives` is the early gate, before the loop spends a call on prose",
    )
    args = parser.parse_args(argv)

    if not args.database.exists():
        print(f"serial_pilot_check: {args.database} does not exist", file=sys.stderr)
        return 2

    report = Report()
    store = SqliteStore.open(args.database)
    try:
        scope = _one_branch(store, report)
        _directives(store, report)
        _jobs(store, report)
        if scope is not None:
            book_id, branch_id = scope
            _outline(store, report, book_id, branch_id)
            _sheet(store, report, book_id, branch_id)
            if args.phase == "full":
                _prose(store, report, book_id, branch_id)
                _state(store, report, book_id, branch_id)
                _promises(store, report, book_id, branch_id)
        _spend(store, report)
        if args.phase == "full":
            rebuilt = store.verify_integrity()
            unattributed = store.unattributed_revisions()
            report.check(not unattributed, f"{len(unattributed)} revision(s) unattributed")
            report.note(f"{rebuilt} revision(s) rebuild cleanly")
    finally:
        store.close()

    verdict = "READ IT" if not report.failures else "DO NOT READ IT YET"
    print(f"=== serial pilot 1 · {args.phase} gate · {verdict} ===")
    for line in report.lines:
        print(line)
    if report.failures:
        print()
        print(f"{len(report.failures)} check(s) failed:")
        for failure in report.failures:
            print(f"  - {failure}")
        print()
        print("§6 spends this candidate's one consultation either way (cadence cap), so a")
        print("book in this state is not worth the bit. Fix, re-tick, re-run this.")
        return 1
    print()
    print("Read `book-library/reappraisal/` beside the database. Write the grab criterion")
    print("BEFORE reading a word (§6 step 1), then one bit at book grain and no riders.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
