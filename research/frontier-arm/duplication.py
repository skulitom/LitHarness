"""Does whole-scene duplication survive the generator swap? §54.1's metric, frontier arm.

**The claim under test is Narrative Planning v0's entire justification.** §54.1 measured
duplicate findings per book at **11, 8, 1, 2, 6 without an outline against 0, 0, 0, 1, 1 with
one** — mean 5.6 against 0.4, permutation p = 0.0238 — and §52's taxonomy put Narrative
Planning first on the strength of it. Every one of those ten books was drafted on
`phi4:latest`, and §56 then measured that same generator reproducing whichever status line was
nearest to hand in 49 of 49 draws. Duplication and number-copying are plausibly one behaviour,
and if they are, the outline is fixing a `phi4` artifact.

**So the arm to run is the control arm, not the treatment.** §54.1's *without-outline*
condition is the one that produced 1 to 11 duplicate findings a book. If a frontier generator
run in exactly that condition produces none, the comparison §54 rests on does not transfer and
Stage 5's ordering is aimed at the wrong taxonomy entry. If it duplicates, the outline is
earning its call and the treatment arm is worth its cost too. Running the control first is
half the quota and answers the question either way.

**Two books, and §54.1 is why two is the floor.** That section's own control arm ranged 1 to
11, and it says outright that a condition this noisy cannot be characterised by one run. Two
is not enough to characterise it either; it is enough to distinguish "none at all" from "the
`phi4` range", which is the only distinction this experiment needs to make.

**Twelve scenes, not thirty.** `arc_template(12)` still repeats its `rising` function, so the
condition §52 blames — many scenes asked the same question — is present; and duplication is a
property of pairs, so twelve scenes offer 66 of them. Thirty would cost 2.5x for a difference
this measurement does not need.

**One process, not one process per tick.** `Conductor.tick` clears the health cache every
tick, and `ClaudeCodeProvider.health()` is a real billed round trip that passes no budget
check (§56.2). Driving the loop in a single process pays that probe once instead of once per
generating tick — roughly 26 calls saved on this run, and it is also what a daemon deployment
actually does.

The conductor is built through `cli._conductor` rather than reconstructed here, so what is
measured is the shipped configuration and not this file's idea of it.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))


from litharness import cli  # noqa: E402
from litharness.adapters.sqlite_store import SqliteStore  # noqa: E402
from litharness.domain.beats import arc_template, beats_for  # noqa: E402
from litharness.domain.draft import DraftPolicy, is_draftable  # noqa: E402
from litharness.domain.integrity import DUPLICATE_RULE  # noqa: E402

#: §56's premise, so the two experiments share a book and the ledger findings stay comparable.
PREMISE = (
    "Rook owes the Vane House forty gold he does not have, and the interest is a level of "
    "his own he cannot afford to lose. He takes contracts in the underlevels to clear it: "
    "each one pays, each one costs him blood or mana he has no way to replace quickly, and "
    "the House keeps moving the number. He can clear the debt or he can stay whole."
)

SEED_VALUES = {"level": 1, "hp": 18, "hp_max": 18, "mp": 4, "mp_max": 4, "gold": 12}


def seed_snapshot(book_id: str, branch_id: str) -> dict[str, Any]:
    return {
        "meta": {
            "schema_version": "1.2.0",
            "artifact_id": "00000000-0000-5000-8000-000000000011",
            "artifact_kind": "state_snapshot",
            "created_at": "2026-08-17T00:00:00Z",
            "actor": "frontier-duplication",
            "tool": {"name": "litharness-research", "version": "0.1.0"},
            "source_revisions": [],
            "dependencies": [],
            "warnings": [],
        },
        "book_id": book_id,
        "branch_id": branch_id,
        "revision_id": "00000000-0000-5000-8000-000000000012",
        "records": [
            {
                "record_id": "rec-seed-rook",
                "kind": "assertion",
                "subject": "rook",
                "predicate": "status_snapshot",
                "value": dict(SEED_VALUES),
                "authority": "accepted_canon",
                "pov_visibility": [],
                "evidence": [],
                "predicate_registry_version": "fixture.v1",
            }
        ],
    }


def make_args(db: Path, *, outline: bool, ceiling: float) -> argparse.Namespace:
    """The shipped defaults, with only the two levers this experiment sets.

    `prefer` is left `None` on purpose: `DEFAULT_ORDER` already puts `claude_code` first for
    the `generation` call class, so naming it would suggest the arm needed a flag when §56.1's
    point is that it is the default. `no_billing` stays False, which is what makes the arm the
    arm.
    """
    return argparse.Namespace(
        database=str(db),
        holder="frontier-dup",
        project="00000000-0000-5000-8000-000000000000",
        prefer=None,
        model=None,
        no_billing=False,
        no_outline=not outline,
        continuity_evaluator_command=None,
        context_budget=None,
        target_words=900,
        notify_file=None,
        max_tokens_per_operation=None,
        max_tokens_per_day=None,
        max_invocations_per_day=None,
        max_cost_usd_per_day=ceiling,
    )


def drafted(store: SqliteStore, book_id: str, branch_id: str, scenes: int) -> int:
    head = store.head(book_id, branch_id)
    if head is None:
        return 0
    return sum(
        1
        for beat in beats_for(head, arc_template(scenes))
        if not is_draftable(head, beat.logical_id, policy=DraftPolicy())
    )


def run_book(
    out: Path, index: int, *, scenes: int, outline: bool, ceiling: float, max_ticks: int
) -> dict[str, Any]:
    db = out / f"book{index}.db"
    book_id = f"33333333-3333-5333-8333-{index:012d}"
    branch_id = f"44444444-4444-5444-8444-{index:012d}"

    args = make_args(db, outline=outline, ceiling=ceiling)
    if not db.exists():
        cli.main(["--database", str(db), "init"])
        seed = out / f"seed{index}.json"
        seed.write_text(
            json.dumps(seed_snapshot(book_id, branch_id), indent=2), encoding="utf-8"
        )
        cli.main(
            [
                "--database", str(db), "new", f"The Vane Ledger {index}",
                "--premise", PREMISE, "--scenes", str(scenes),
                "--state", str(seed), "--book", book_id, "--branch", branch_id,
            ]
        )

    store = SqliteStore.open(db)
    loop = cli._conductor(store, args)
    started = time.monotonic()
    ticks = 0
    try:
        for ticks in range(1, max_ticks + 1):
            done = drafted(store, book_id, branch_id, scenes)
            if done >= scenes:
                break
            loop.tick(time.time())
            if ticks % 5 == 0:
                print(
                    f"  book{index} tick {ticks}: {done}/{scenes} scenes "
                    f"({time.monotonic() - started:.0f}s)",
                    flush=True,
                )
        findings = store.findings(book_id, branch_id)
        duplicates = [f for f in findings if f.rule_or_critic_id == DUPLICATE_RULE]
        head = store.head(book_id, branch_id)
        words = sum(
            len(node.content.split())
            for node in (head.in_reading_order() if head else [])
            if node.content
        )
        result = {
            "book": index,
            "outline": outline,
            "scenes_drafted": drafted(store, book_id, branch_id, scenes),
            "scenes_total": scenes,
            "duplicate_findings": len(duplicates),
            "all_findings": len(findings),
            "words": words,
            "ticks": ticks,
            "wall_s": round(time.monotonic() - started),
        }
    finally:
        store.close()
    print(f"  book{index} done: {result}", flush=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--books", type=int, default=2)
    parser.add_argument("--scenes", type=int, default=12)
    parser.add_argument(
        "--outline",
        action="store_true",
        help="run the treatment arm instead; the control arm (no outline) is the one that "
        "answers whether duplication transfers at all",
    )
    parser.add_argument(
        "--max-cost-usd-per-day",
        type=float,
        default=30.0,
        help="a governor, because the default is None and §56.2 measured what an unbounded "
        "run can spend on probes alone",
    )
    parser.add_argument("--max-ticks", type=int, default=400)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    results = [
        run_book(
            args.out,
            index,
            scenes=args.scenes,
            outline=args.outline,
            ceiling=args.max_cost_usd_per_day,
            max_ticks=args.max_ticks,
        )
        for index in range(1, args.books + 1)
    ]

    arm = "outline" if args.outline else "no-outline"
    destination = args.out / f"results-{arm}.json"
    destination.write_text(
        json.dumps({"arm": arm, "books": results}, indent=2), encoding="utf-8"
    )
    print(f"\n{'book':>5} {'scenes':>7} {'words':>7} {'duplicate findings':>19}")
    for row in results:
        print(
            f"{row['book']:>5} {row['scenes_drafted']:>7} {row['words']:>7} "
            f"{row['duplicate_findings']:>19}"
        )
    print(
        "\n§54.1 on phi4, this same no-outline condition, five books: 11, 8, 1, 2, 6 "
        "(mean 5.6).\nCompare against that range, not against zero."
    )
    print(f"wrote {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
