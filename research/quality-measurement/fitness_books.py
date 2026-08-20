"""Draft the fitness books: the own-generated shelf every instrument in this directory needs.

**Operator decision §7.1: FUND** (~$81 of frontier drafting). This module is the driver, and the
substrate it produces is not for this programme's headline — it is for the three measurements
§94.3 priced and could not run:

- the **BCR variance floor**, which needs twenty own-generated texts and had one;
- the **BCR transplant check**, which needs a second own-generated book as donor and had none —
  and the design calls transplant-blindness a *kill*, so a model that has not been asked cannot
  be seated however the other five legs read;
- **F3's own-generated arm**, whose eventual real target is books this system wrote rather than
  books it scraped.

§94.3's sentence stands until this finishes: *until roughly $81 of frontier drafting buys the
fitness books, every BCR number in this repository is a statement about the instrument's own
controls and about no book.*

**Why twenty and why 3,600 words.** Twenty is the variance floor's own requirement. 3,600 words
is the Budgeted Continuation Reader's registered shelf shape — long enough that the budget cannot
exhaust a shelf member. At the measured ~1,000 words a drafted scene, five scenes clears it with
margin, and a book that lands short is recorded short rather than padded.

**Twenty premises, not one premise twenty times.** A shelf whose members share a premise is a
shelf that measures how well an instrument recognises one story. They are LitRPG because that is
the genre every corpus in this directory is matched on, and they are deliberately plain: this is
substrate, not a demonstration.

**One book first, then the rest.** The first book runs alone and its cost is measured before the
other nineteen are bought — the pilot-then-batch discipline this repository keeps having to
relearn, and the reason §94.6 spent a seating budget on one family instead of four.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SHELF = HERE / "corpora" / "fitness"

#: The shelf's shape, from `bcr.py`'s registered constants rather than re-chosen here.
TARGET_WORDS = 3_600
#: **Six, not five, and the floor is the arc's rather than the shelf's.** `domain/beats.py`
#: refuses an arc below six scenes — *"an arc needs at least 6 scenes to carry its named beats"* —
#: so five would have produced twenty `TemplateMismatch` failures and no books. Six at the
#: measured ~1,000 words a scene clears 3,600 with margin, which is the right direction to be
#: wrong in for a shelf whose whole requirement is that the budget cannot exhaust a member.
SCENES = 6

#: Per-book ceiling. A book that has not reached prose after this many ticks is recorded as
#: incomplete with its tick count, never retried into an unbounded spend.
MAX_TICKS = 60

#: **Cumulative ceiling across the whole shelf**, read from each book's own `policy_decisions`
#: rows rather than estimated. §7.1 funded ~$81 for twenty books; a per-book cap alone cannot
#: bound the total, and twenty books each allowed $8 is $160. This is the number that stops the
#: run, checked after every book.
SHELF_CEILING_USD = 81.0

#: Dollar ceiling per book per day, as a stop rather than a target. Twenty books at this ceiling
#: is above §94.3's ~$81 estimate on purpose: the ceiling is what stops a runaway, not what the
#: run is expected to cost, and a ceiling set at the estimate would abort a book that merely ran
#: a little long.
MAX_COST_USD_PER_BOOK = 8.0

PREMISES: tuple[tuple[str, str], ...] = (
    ("The Tollkeeper's Ledger",
     "A bridge tollkeeper discovers the toll he collects is measured in memories, and the "
     "system that tracks it will not let him stop."),
    ("Salvage Rites",
     "A scavenger on a drowned coast levels by repairing what others abandoned, and the "
     "salvage system starts assigning her debts that are not hers."),
    ("The Understudy",
     "A theatre apprentice inherits a class that only advances when someone else believes "
     "his performance, and his rival is the only audience left."),
    ("Kiln",
     "A potter's guild runs on a crafting system that grades intent as well as output, and "
     "the newest apprentice cannot lie to it."),
    ("Nightsoil",
     "A city's sewer crew are the only class whose skills work below ground, and something "
     "down there has started levelling too."),
    ("The Quiet Tier",
     "A duellist who has never spoken finds her class advances on silence, in a tournament "
     "that rewards taunting."),
    ("Fenceline",
     "A border surveyor's map updates itself faster than the border moves, and the system "
     "pays him for territory nobody has claimed yet."),
    ("The Long Count",
     "A tally clerk in a siege discovers that what he records becomes true, and the siege "
     "has three weeks of food."),
    ("Understory",
     "A forester whose skills read as farming discovers the trees have been assigned levels, "
     "and someone is harvesting them in order."),
    ("Glasswright",
     "A window-maker's craft system rewards flaws, and the cathedral commission demands "
     "perfection."),
    ("The Debt Collector's Apprentice",
     "A collector's ledger shows every debt as a quest, and the first one she inherits is "
     "owed by her own house."),
    ("Rope and Ash",
     "A mountain guide's route-finding class levels only on paths nobody has taken, and the "
     "last unclimbed face has killed four parties."),
    ("The Sixth Bell",
     "A monastery's bell-ringer finds the schedule is a spellform, and one hour has gone "
     "missing from it."),
    ("Cold Forge",
     "A smith who works only in winter discovers her class is seasonal by design, and the "
     "winter is ending early."),
    ("The Inheritor's Rate",
     "A tax assessor inherits a class that values things at what they will be worth, and the "
     "province is about to be worth nothing."),
    ("Wick",
     "A candlemaker's light reveals system text nobody else can read, and the town council "
     "has ordered the candles put out."),
    ("The Draft Horse",
     "A carter whose class levels on cargo delivered intact takes a contract that requires "
     "him to lose it."),
    ("Stormglass",
     "A weather-reader's forecasts become binding once spoken, and a fleet is waiting on her "
     "word."),
    ("The Second Signature",
     "A forger's skill tree branches on whose hand she copies, and the one she is asked for "
     "belongs to someone still alive."),
    ("Downriver",
     "A ferryman's class advances only on passengers who never return, and his sister has "
     "booked passage."),
)


def run_cli(
    args: list[str], *, database: Path, globals_: list[str] | None = None, timeout: int = 1800
) -> tuple[int, str]:
    """`--target-words` and the budget ceilings are **top-level** args, before the subcommand.

    Checked in `cli.py` rather than assumed: they are attached to the root parser at :3288-3325,
    not to `tick`, so passing them after the subcommand is an argparse error and not a policy.
    """
    command = [
        sys.executable, "-m", "litharness",
        "--database", str(database), *(globals_ or []), *args,
    ]
    # utf-8 explicitly: `text=True` alone decodes with the Windows console codepage and dies on
    # the first curly quote the drafter writes. See `force_remote._call`.
    finished = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout, check=False, cwd=str(HERE.parent.parent),
    )
    return finished.returncode, (finished.stdout or "") + (finished.stderr or "")


def book_cost(database: Path) -> float:
    """What this book actually cost, from its own decision rows.

    `policy_decisions.cost_usd` is what the store already records per decision, so the shelf's
    spend is a query rather than an estimate — the same move that let F1's overspend be measured
    instead of guessed (§95.10). On a Claude subscription these are equivalent-quota figures and
    not billed dollars, which is `providers/cli.py`'s position.
    """
    import sqlite3

    if not database.is_file():
        return 0.0
    try:
        with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
            row = connection.execute(
                "SELECT COALESCE(SUM(cost_usd), 0.0) FROM policy_decisions"
            ).fetchone()
        return float(row[0] or 0.0)
    except sqlite3.Error:
        return 0.0


def word_count(database: Path) -> tuple[int, str]:
    """Words of drafted prose, and *why* if the answer is zero.

    A bare `0` is the shape of failure this whole directory keeps building rails against: the
    first shelf book reported `0 words` after 36 ticks and $2.79, and the zero looked exactly
    like "the drafter produced nothing". It was not. Two failed driver attempts had each left a
    book behind in that database, and `export` refuses without `--book` once a store holds more
    than one — so the count was a *reporting* failure wearing a drafting failure's clothes.
    Returning the reason with the number is what stops that being invisible.
    """
    code, out = run_cli(["export", "--format", "markdown"], database=database)
    if code == 0:
        words = len(out.split())
        return words, "" if words else "export succeeded and returned no prose"

    # A store holding more than one book refuses and *names* them. Measured on the first shelf
    # slot: two books of 4,047 and 4,028 words, both clearing the shelf shape, reported as a
    # flat zero. The prose was there the whole time; only the count had failed. A shelf member
    # is one book, so the number that matters is the largest single one.
    ids = re.findall(r"--book ([0-9a-f-]{36})", out)
    if ids:
        counts = []
        for book_id in ids:
            book_code, book_out = run_cli(
                ["export", "--format", "markdown", "--book", book_id], database=database
            )
            counts.append(len(book_out.split()) if book_code == 0 else 0)
        if counts:
            return max(counts), (
                f"store holds {len(ids)} books ({', '.join(str(c) for c in counts)} words); "
                "reporting the largest, since a shelf member is one book"
            )
    detail = out.strip().splitlines()[-1][:120] if out.strip() else ""
    return 0, f"export failed rc={code}: {detail}"


def draft_one(index: int, title: str, premise: str, args: argparse.Namespace) -> dict[str, Any]:
    SHELF.mkdir(parents=True, exist_ok=True)
    database = SHELF / f"fitness-{index:02d}.db"
    # **A shelf slot must start empty.** `init` is safe to re-run and `new` is not: a database
    # left behind by a failed attempt gets a *second* book, and from then on every export refuses
    # and every word count reads zero. Recreating the slot costs nothing before any call is
    # bought and prevents a book whose prose exists but cannot be read.
    if database.is_file() and not args.resume:
        database.unlink()
    started = time.time()
    log: list[str] = []

    code, out = run_cli(["init"], database=database)
    log.append(f"init rc={code}")
    if code != 0:
        return {"index": index, "title": title, "status": "INIT_FAILED", "words": 0,
                "ticks": 0, "seconds": round(time.time() - started, 1), "log": log,
                "out": out[-400:]}

    code, out = run_cli(
        ["new", title, "--premise", premise, "--scenes", str(args.scenes)], database=database
    )
    log.append(f"new rc={code} {out.strip()[:120]}")
    if code != 0:
        return {"index": index, "title": title, "status": "NEW_FAILED", "words": 0,
                "ticks": 0, "seconds": round(time.time() - started, 1), "log": log,
                "out": out[-400:]}

    ticks = 0
    attention = 0
    parked = 0
    words = 0
    while ticks < args.max_ticks:
        # `--no-library` is a TOP-LEVEL flag too — `tick` itself takes no arguments at all,
        # which the first run found by way of three argparse errors that the driver counted as
        # ticks. Checked in `cli.py:3362` rather than guessed the second time.
        code, out = run_cli(
            ["tick"],
            database=database,
            globals_=[
                "--no-library",
                "--target-words", str(args.target_words // args.scenes),
                "--max-cost-usd-per-day", str(args.max_cost),
            ],
        )
        ticks += 1
        line = out.strip().splitlines()[0] if out.strip() else ""
        if line.startswith("usage: litharness"):
            log.append(f"tick{ticks} ARGPARSE-ERROR — driver bug, not a book failure")
            break
        log.append(f"tick{ticks} rc={code} {line[:110]}")
        if code != 0:
            attention += 1
            # Three consecutive attention outcomes is a stuck book, not a transient. §64
            # reclassified provider fallback as a defect; retrying past it would spend money
            # discovering the same defect repeatedly.
            if attention >= 3:
                break
        else:
            attention = 0
        # `TickOutcome` is a StrEnum and the CLI prints its value first: `no_work`, `ran_job`,
        # `job_failed`, `job_parked`, `replayed`. The first draft broke on "IDLE"/"NOTHING",
        # neither of which the conductor has ever emitted — so a finished book would have spun
        # the full tick budget doing nothing. Checked in `application/conductor.py:51`.
        if line.startswith("no_work"):
            log.append(f"tick{ticks} no_work - the conductor has nothing left to do")
            break
        if line.startswith("job_parked"):
            parked += 1
            # Parked is terminal by policy (§4.2), not an error to retry into.
            if parked >= 2:
                log.append(f"tick{ticks} job_parked twice - stopping rather than retrying")
                break
        if ticks % 5 == 0:
            words, _ = word_count(database)
            if words >= args.target_words:
                break

    words, why_zero = word_count(database)
    # A zero that comes from an unreadable store is a different fact from a zero that comes from
    # a drafter producing nothing, and the status has to say which. `word_count` already resolves
    # the multi-book case by exporting each book, so a remaining zero with an export failure
    # behind it is the genuinely unreadable one.
    unreadable = words == 0 and why_zero.startswith("export failed")
    return {
        "index": index,
        "title": title,
        "database": str(database),
        "ticks": ticks,
        "words": words,
        "meets_shelf_shape": words >= args.target_words,
        "status": (
            "UNREADABLE" if unreadable
            else "DRAFTED" if words >= args.target_words
            else "SHORT"
        ),
        "why_zero": why_zero,
        "seconds": round(time.time() - started, 1),
        "log": log[-12:],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--books", type=int, default=len(PREMISES))
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--scenes", type=int, default=SCENES)
    parser.add_argument("--target-words", type=int, default=TARGET_WORDS)
    parser.add_argument("--max-ticks", type=int, default=MAX_TICKS)
    parser.add_argument("--max-cost", type=float, default=MAX_COST_USD_PER_BOOK)
    parser.add_argument("--shelf-ceiling", type=float, default=SHELF_CEILING_USD,
                        help="cumulative stop across the whole shelf, read from each book's "
                             "own policy_decisions rows")
    parser.add_argument("--resume", action="store_true",
                        help="keep an existing database for a slot instead of recreating it; "
                             "off by default because a slot left behind by a failed attempt "
                             "gets a second book and every export after that refuses")
    parser.add_argument("--out", default=str(HERE / "results" / "fitness-books.json"))
    args = parser.parse_args(argv)

    rows: list[dict[str, Any]] = []
    out_path = Path(args.out)
    for index in range(args.start, min(args.start + args.books, len(PREMISES))):
        title, premise = PREMISES[index]
        row = draft_one(index, title, premise, args)
        row["cost_usd"] = round(book_cost(SHELF / f"fitness-{index:02d}.db"), 4)
        rows.append(row)
        spent = sum(r.get("cost_usd", 0.0) for r in rows)
        print(
            f"[{index:02d}] {row['status']:<12} {row['words']:>6} words  "
            f"{row['ticks']:>3} ticks  {row['seconds']:>7.1f}s  "
            f"${row['cost_usd']:>6.2f}  (shelf ${spent:.2f}/{args.shelf_ceiling:.0f})  {title}",
            flush=True,
        )
        # Written after every book, not at the end: a run that dies at book seventeen must not
        # lose the record of sixteen books that cost real money.
        out_path.parent.mkdir(parents=True, exist_ok=True)
        existing = (
            json.loads(out_path.read_text(encoding="utf-8")) if out_path.is_file() else {}
        )
        by_index = {r["index"]: r for r in existing.get("books", [])}
        by_index.update({r["index"]: r for r in rows})
        out_path.write_text(
            json.dumps(
                {
                    "purpose": "the own-generated shelf §94.3 priced; operator §7.1 FUND",
                    "target_words": args.target_words,
                    "scenes_per_book": args.scenes,
                    "max_cost_usd_per_book": args.max_cost,
                    "books": [by_index[k] for k in sorted(by_index)],
                    "shelf_members": sum(
                        1 for r in by_index.values() if r.get("meets_shelf_shape")
                    ),
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        if spent >= args.shelf_ceiling:
            print(
                f"STOP: shelf ceiling reached, ${spent:.2f} of ${args.shelf_ceiling:.2f} after "
                f"{len(rows)} book(s). Every book already drafted is on disk and a resumed run "
                "starts from --start.",
                flush=True,
            )
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
