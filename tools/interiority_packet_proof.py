"""What the Serial Pilot's seeded interiority puts in each scene's packet, and when.

Two claims, and the whole of this script is that they are printed rather than asserted in
prose:

1. a `wants` or `fears` record dated at or before the scene being drafted **is** in that
   scene's context packet;
2. the same record dated later **is not**.

Both are properties of `application/planner.py::packet_for`, which passes the beat's
`story_order_key` through `extraction.stated_position` as the packet's `story_time_cutoff`.
Before that, `plan/interiority-model.md` §1 measured the failing case: two wants at `s1` and
`s5`, and both arrived while drafting scene 1.

**No provider, no prose, no cost.** The book is `new_book` at the pilot's declared scene count
with every scene empty, seeded from `plan/serial-pilot-seed.json` and nothing else, so the
packet this prints is the state half of what scene N would actually be handed — the premise,
the directives and the prior prose of a real run sit beside it and are not what is under test.

It also runs the contradiction detector over the seed, because several dated `wants` records
for one subject is exactly the shape `plan/state-model-abilities.md` §2 says is reported as a
blocking contradiction, and the reason it is not here — `detect_contradictions` groups on
`(subject, predicate, order_key)`, so distinct positions are distinct groups — is a property
worth measuring rather than reasoning about.

Usage (from the repository root):

    uv run python tools/interiority_packet_proof.py
    uv run python tools/interiority_packet_proof.py --seed plan/serial-pilot-seed.json
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

import litharness_contracts as lc

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.planner import packet_for
from litharness.domain import state as state_mod
from litharness.domain.beats import Beat, beats_for, template_for
from litharness.domain.context import FACTS, assemble, count_tokens
from litharness.domain.extraction import has_story_vocabulary, stated_position
from litharness.domain.findings import DetectorInput, Severity
from litharness.domain.integrity import detect_contradictions
from litharness.domain.revision import Revision, new_book
from litharness.domain.state import import_state

REPO = Path(__file__).resolve().parent.parent
SEED = REPO / "plan" / "serial-pilot-seed.json"
SPEC = REPO / "plan" / "serial-pilot-directives.json"

#: The predicates this script reports on. Not a vocabulary the system enforces — `predicate`
#: is a free-form string and nothing anywhere validates it — only the two the pilot seeds.
INTERIOR_PREDICATES = ("wants", "fears")

BOOK_ID = "00000000-0000-5000-8000-000000000001"
BRANCH_ID = "00000000-0000-5000-8000-000000000002"
CREATED = "2026-08-22T00:00:00Z"

#: Matches the pilot's `--context-budget`, so the token figures below are the run's own.
TOKEN_BUDGET = 16000


def declared_scenes() -> int:
    try:
        return int(json.loads(SPEC.read_text(encoding="utf-8"))["scenes"])
    except (OSError, ValueError, KeyError):
        return 8


def load_seed(path: Path) -> list[lc.StateRecord]:
    snapshot = lc.parse_artifact(
        lc.StateSnapshot, json.loads(path.read_text(encoding="utf-8"))
    )
    return list(import_state(snapshot, book_id=BOOK_ID, branch_id=BRANCH_ID).records)


def interior(records: list[lc.StateRecord]) -> list[lc.StateRecord]:
    return [
        record for record in records if record.predicate in INTERIOR_PREDICATES
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, default=SEED)
    args = parser.parse_args(argv)

    records = load_seed(args.seed)
    seeded = interior(records)
    scenes = declared_scenes()

    print(f"seed: {args.seed.relative_to(REPO).as_posix()} - {len(records)} record(s), "
          f"{len(seeded)} of them interiority")
    print(f"book: {scenes} empty scenes, no prose, no provider\n")

    if not seeded:
        print("no `wants` or `fears` records in this seed; nothing to prove")
        return 1

    print("the seeded interiority, as canon holds it")
    print("-" * 78)
    for record in state_mod.in_story_order(seeded):
        key = state_mod.order_key_of(record) or "(unplaced)"
        print(f"  {key:<6} {state_mod.describe(record)}")
    cost = sum(count_tokens(state_mod.describe(record)) for record in seeded)
    print(f"\n  {cost} tokens for all {len(seeded)}, against a {TOKEN_BUDGET}-token packet budget")

    with tempfile.TemporaryDirectory() as tmp:
        store = SqliteStore.open(Path(tmp) / "interiority-proof.db")
        try:
            revision = new_book(BOOK_ID, BRANCH_ID, title="Reappraisal", scenes=scenes)
            store.commit_revision(revision, created_at=CREATED)
            store.record_state_records(BOOK_ID, BRANCH_ID, records, created_at=CREATED)
            head = store.head(BOOK_ID, BRANCH_ID)
            assert head is not None

            stored = store.state_records(BOOK_ID, BRANCH_ID)
            beats = beats_for(head, template_for(head))
            print("\nthe cutoff each beat is entitled to")
            print("-" * 78)
            print(f"  has_story_vocabulary(seed) = {has_story_vocabulary(stored)}  "
                  "(False means no vocabulary somebody else chose, so a cutoff applies)")
            for beat in beats:
                cutoff = stated_position(stored, beat.story_order_key)
                print(f"  {beat.logical_id:<10} beat key {beat.story_order_key!r:<6} "
                      f"cutoff {cutoff!r}")

            failures = _report_packets(store, head, beats, seeded)
            failures += _report_before_and_after(store, head, beats, records, seeded)
            failures += _report_contradictions(records)
        finally:
            store.close()

    print()
    if failures:
        print(f"FAILED: {failures} claim(s) did not hold")
        return 1
    print("both claims hold: dated at or before is carried, dated later is not")
    return 0


def _report_packets(
    store: SqliteStore, head: Revision, beats: Sequence[Beat], seeded: list[lc.StateRecord]
) -> int:
    """Which interiority record reaches which scene — the two claims, as a grid."""
    print("\nwhat each scene's packet carries")
    print("-" * 78)
    header = "  scene      " + "  ".join(
        f"{(state_mod.order_key_of(r) or '-'):>4}" for r in state_mod.in_story_order(seeded)
    )
    print(header)
    failures = 0
    ordered = state_mod.in_story_order(seeded)
    for beat in beats:
        packet = packet_for(store, head, beat, token_budget=TOKEN_BUDGET)
        cells = []
        for record in ordered:
            present = packet.contains_ref(record.record_id)
            due = (state_mod.order_key_of(record) or "") <= (beat.story_order_key or "")
            cells.append("  yes" if present else "   . ")
            if present is not due:
                failures += 1
        print(f"  {beat.logical_id:<10} " + "  ".join(cells))
    print("\n  a column turns on at the scene its record is dated at and stays on; "
          "`.` is absent")
    return failures


def _report_before_and_after(
    store: SqliteStore,
    head: Revision,
    beats: Sequence[Beat],
    records: list[lc.StateRecord],
    seeded: list[lc.StateRecord],
) -> int:
    """Scene 1's Established facts block with and without the cutoff.

    The "before" is not a reconstruction: it is `assemble` called the way `packet_for` called
    it until the cutoff landed — same records, same budget, `story_time_cutoff=None`.
    """
    beat = beats[0]
    after = packet_for(store, head, beat, token_budget=TOKEN_BUDGET)
    before = assemble(
        head,
        beat.logical_id,
        plan_items=store.plan_items(head.book_id, head.branch_id),
        state_records=store.state_records(head.book_id, head.branch_id),
        query_id=f"beat:{beat.logical_id}",
        token_budget=TOKEN_BUDGET,
    )
    print("\nscene 1's Established facts, interiority only - before and after the cutoff")
    print("-" * 78)
    for label, packet in (("before", before), ("after ", after)):
        lines = [
            item.text
            for item in packet.sections.get(FACTS, ())
            if any(f" {predicate} " in item.text for predicate in INTERIOR_PREDICATES)
        ]
        print(f"  {label}: {len(lines)} line(s)")
        for line in lines:
            print(f"          - {line}")
    print(f"\n  every other fact is unchanged: {len(before.sections.get(FACTS, ()))} facts "
          f"before, {len(after.sections.get(FACTS, ()))} after, "
          f"{len(before.items) - len(after.items)} item(s) fewer in total")
    leaked = [
        record.record_id
        for record in seeded
        if (state_mod.order_key_of(record) or "") > (beat.story_order_key or "")
        and after.contains_ref(record.record_id)
    ]
    return len(leaked)


def _report_contradictions(records: list[lc.StateRecord]) -> int:
    """Several dated `wants` for one subject, against the detector that would block them."""
    findings = detect_contradictions(
        DetectorInput(
            book_id=BOOK_ID,
            branch_id=BRANCH_ID,
            logical_id="scene-1",
            records=tuple(records),
        )
    )
    blocking = [f for f in findings if f.severity in (Severity.MAJOR, Severity.CRITICAL)]
    print("\nthe contradiction detector over the whole seed")
    print("-" * 78)
    groups: dict[tuple[str, str, str], list[str]] = {}
    for record in records:
        if not state_mod.is_canon(record):
            continue
        key = (record.subject, record.predicate, state_mod.order_key_of(record) or "")
        groups.setdefault(key, []).append(record.record_id)
    repeated = {key: ids for key, ids in groups.items() if len(ids) > 1}
    print(f"  {len(groups)} distinct (subject, predicate, order_key) group(s) over "
          f"{len(records)} record(s)")
    print(f"  groups holding more than one record: {repeated or 'none'}")
    print(f"  findings: {len(findings)} ({len(blocking)} blocking)")
    for finding in findings:
        print(f"    {finding.severity.value}: {finding.message}")
    return len(blocking)


if __name__ == "__main__":
    sys.exit(main())
