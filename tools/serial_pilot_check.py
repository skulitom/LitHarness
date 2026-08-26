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
import json
import re
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import export as export_module
from litharness.application import library as library_module
from litharness.domain import worlds
from litharness.domain.beats import beats_for, scene_nodes, template_for
from litharness.domain.directives import DirectiveStatus
from litharness.domain.extraction import (
    STATUS_PREDICATE,
    graph_line_for,
    sheet_for,
    speaks_system_voice,
)
from litharness.domain.jobs import JobStatus
from litharness.domain.nodes import NodeKind
from litharness.domain.plans import scene_plan_for

#: What the pilot declared. Read from the extracted spec rather than hardcoded, so adding a
#: directive to the package cannot leave this gate quietly checking an older number.
SPEC = Path(__file__).resolve().parent.parent / "plan" / "serial-pilot-directives.json"


def declared(specs: Sequence[Path]) -> tuple[int, int]:
    """Scene count and directive count, summed across every spec the run was set up from.

    **Summed, because historical Serial Pilot 2 has two.** Its preserved world directives and
    `plan/serial-pilot-2-craft.json` are separate specs, and a gate that
    read only one of them would report the inbox short by the size of the other — which is
    exactly the false alarm this file exists to prevent the operator from learning to ignore.
    The scene count is the largest any spec declares; a spec that omits it contributes none.
    """
    scenes = 0
    directives = 0
    for path in specs:
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        scenes = max(scenes, int(spec.get("scenes") or 0))
        directives += len(spec.get("directives") or ())
    return (scenes or 8, directives or 8)

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


def _directives(
    store: SqliteStore, report: Report, expected_directives: int, specs: Sequence[Path]
) -> None:
    counts = {status.value: len(store.directives_by_status(status)) for status in DirectiveStatus}
    total = sum(counts.values())
    report.check(
        total == expected_directives,
        f"{total} directive(s) in the inbox, expected {expected_directives}",
        "as extracted from " + ", ".join(path.name for path in specs),
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


def _prose(
    store: SqliteStore, report: Report, book_id: str, branch_id: str, expected_scenes: int
) -> None:
    document = export_module.collect(
        store,
        book_id=book_id,
        branch_id=branch_id,
        generated_at=datetime.now(tz=UTC).isoformat(),
    )
    report.check(
        document.total == expected_scenes,
        f"the book holds {document.total} scene(s), expected {expected_scenes}",
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
    # **A book that speaks neither line form has nothing to read back, and refusing it would be
    # this gate asserting that every world is a LitRPG one.** Pilot 1 declared a status sheet, so
    # zero read-back meant its C2 had not taken. A world may declare no sheet and no graph
    # line at all — absence is free — and then zero is the correct number rather than a failure.
    # Reported either way; checked only where there was something to read.
    speaks = speaks_system_voice(records) or graph_line_for(records) is not None
    headline = (
        f"{len(read_back)} state record(s) read off the book's own prose "
        f"({len(records)} total, {seeded} seeded)"
    )
    if not speaks:
        report.note(
            headline,
            "this book declares neither a status sheet nor a usable graph line, so there is no "
            "in-story form to read back and zero is what that looks like",
        )
    else:
        report.check(
            bool(read_back),
            headline,
            "zero means no in-story line the parser accepted — the world's own form did not take",
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
    # **A world that declares no sheet is not a world with the default one.** `sheet_for`
    # returns `DEFAULT_SHEET` when nothing is declared, which is right for the parser and wrong
    # for this line: printing `Level | HP | MP | Gold` under a book that declares no numbers at
    # all reads as a finding about the book rather than about the fallback. `speaks_system_voice`
    # is the question that actually matters — a book whose canon holds no snapshot is never asked
    # for a status line, so there is nothing here to check and saying so is the honest report.
    if not speaks_system_voice(records):
        report.note(
            "status sheet: none declared, and this book never speaks system voice",
            "absence is free — no line is asked for and none is read back; the graph line, if "
            "the world declared one, is the other family",
        )
        return
    report.note("status sheet", " | ".join(field.label for field in sheet.fields))
    line = graph_line_for(records)
    if line is not None:
        report.note(f"graph line: {line.template}", "the second extractor family's in-story form")
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




def _disclosure(store: SqliteStore, report: Report, book_id: str, branch_id: str) -> None:
    """The iceberg, reported and never gated — Serial Pilot 2's S2 and S3.

    **Nothing here is a check, and the reason is that neither question has a deterministic
    form.** S2 asks whether the writer stated a secret it was told to honour and not state; S3
    asks whether a scheduled reveal landed. Deciding from prose that a hint has gone too far, or
    that an answer has genuinely been given rather than gestured at, is exactly the judgment
    this project has no instrument for — so this prints numbers an operator reads beside the
    prose and refuses nothing.

    **The counter is the world's own coined vocabulary, not content words.** The first version
    of this probe compared the answer's content words against the prose and reported shares of
    0.20 to 0.59 — every one of them driven by `because`, `being`, `every`, `water` and `basin`.
    A number that high on a book that leaked nothing is a shallow metric wearing a finding, and
    `plan/reader-read-2.md`'s `opening_proper_nouns` is the case this repository already owns.
    What can give a secret away is the world's *invented* nouns, so that is what is counted, and
    even then a name on the page is not the secret being told.
    """
    records = store.state_records(book_id, branch_id)
    answers = worlds.claims(records)
    schedule = worlds.disclosures(records)
    if not answers:
        return
    coined = set(worlds.key_nouns(records))
    head = store.head(book_id, branch_id)
    if head is None:
        return
    scenes = [
        (node.logical_id, node.content)
        for node in head.in_reading_order()
        if node.kind is NodeKind.SCENE and node.content
    ]
    keys = {
        beat.logical_id: beat.story_order_key
        for beat in beats_for(head, template_for(head))
    }
    drafted = {logical_id for logical_id, _ in scenes}
    last_key = max(
        (keys[logical_id] for logical_id in drafted if keys.get(logical_id)), default=None
    )
    hidden = {record.subject for record in worlds.undisclosed_claims(records, at=last_key)}

    report.note(
        f"{len(answers)} recorded answer(s), {len(schedule)} scheduled, "
        f"{len(hidden)} still hidden at {last_key or 'the end of what is drafted'}",
        "reported, never gated — no deterministic reading decides whether a secret was told",
    )
    # **Over the declared ordinals, not the positions.** A reveal past the end of this book has
    # an ordinal and deliberately no `order_key`, so a loop over the positions would silently
    # omit exactly the debts a serial carries forward — the ones an operator most wants counted.
    ordinals = worlds.reveal_scenes(records)
    for claim_id in sorted(set(ordinals) | set(schedule)):
        when = schedule[claim_id][0] if claim_id in schedule else None
        ordinal = ordinals.get(claim_id)
        answer = answers.get(claim_id, "")
        words = {
            word
            for word in re.findall(r"[a-z][a-z'-]{3,}", answer.casefold())
            if word in coined
        }
        reached = "not in this book"
        if when is not None:
            at_or_after = [
                text for logical_id, text in scenes if (keys.get(logical_id) or "") >= when
            ]
            reached = "yes" if at_or_after else "not yet drafted"
        seen_before = sorted(
            word
            for word in words
            if any(
                word in (text or "").casefold()
                for logical_id, text in scenes
                if when is None or (keys.get(logical_id) or "") < when
            )
        )
        state = "hidden" if claim_id in hidden else "disclosed"
        report.note(
            f"  {state:<9} {claim_id:<26} scene {ordinal or '?'} "
            f"({when or 'outside this book'}) · scenes at or past it: {reached}",
            f"coined nouns in the answer seen earlier: {', '.join(seen_before) or 'none'}"
            + (f" (of {len(words)})" if words else " (the answer coins none)"),
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
        "--spec",
        type=Path,
        action="append",
        help="a package spec whose scene and directive counts this gate checks against. "
        "Repeatable; historical Serial Pilot 2 needs its world directives and "
        "plan/serial-pilot-2-craft.json. Defaults to Serial Pilot 1's single spec",
    )
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

    specs = list(args.spec or [SPEC])
    expected_scenes, expected_directives = declared(specs)

    report = Report()
    shelf = ""
    store = SqliteStore.open(args.database)
    try:
        scope = _one_branch(store, report)
        _directives(store, report, expected_directives, specs)
        _jobs(store, report)
        if scope is not None:
            book_id, branch_id = scope
            head = store.head(book_id, branch_id)
            if head is not None:
                shelf = library_module.slugify(
                    export_module.collect(
                        store,
                        book_id=book_id,
                        branch_id=branch_id,
                        generated_at=datetime.now(tz=UTC).isoformat(),
                    ).title,
                    book_id,
                )
            _outline(store, report, book_id, branch_id)
            _sheet(store, report, book_id, branch_id)
            if args.phase == "full":
                _prose(store, report, book_id, branch_id, expected_scenes)
                _state(store, report, book_id, branch_id)
                _promises(store, report, book_id, branch_id)
                _disclosure(store, report, book_id, branch_id)
        _spend(store, report)
        if args.phase == "full":
            rebuilt = store.verify_integrity()
            unattributed = store.unattributed_revisions()
            report.check(not unattributed, f"{len(unattributed)} revision(s) unattributed")
            report.note(f"{rebuilt} revision(s) rebuild cleanly")
    finally:
        store.close()

    verdict = "READ IT" if not report.failures else "DO NOT READ IT YET"
    # **Which pilot, from the specs it was pointed at.** The header said "serial pilot 1"
    # unconditionally, which on Serial Pilot 2 is a label reporting the wrong book — the
    # exact class of quiet wrongness the rest of this file exists to catch.
    label = "serial pilot 2" if any("pilot-2" in path.name for path in specs) else "serial pilot 1"
    print(f"=== {label} · {args.phase} gate · {verdict} ===")
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
    # **The shelf, by name.** This line named `reappraisal/` unconditionally, which on any
    # second pilot points an operator at the previous book — and the one thing this gate exists
    # to protect is the single acceptance read, so sending it to the wrong shelf is the most
    # expensive small wrongness in the file.
    print(f"Read `book-library/{shelf or '<slug>'}/` beside the database. Write the grab criterion")
    print("BEFORE reading a word (§6 step 1), then one bit at book grain and no riders.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
