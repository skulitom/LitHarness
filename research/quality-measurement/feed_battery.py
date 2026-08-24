"""The feed continuation reader's driver: free legs first, then the paid screen.

This module is deliberately thin. Every methodological choice was made somewhere else and is
imported, never restated: `feed_core` owns the registration, the byte-frozen prompts and the
shared records; `feed_substrate` builds the feeds; `feed_session` runs one session; and
`feed_controls` owns the control arithmetic and the patterned-reader attainability table. What
lives here is only wiring — which feeds, how many sessions, and the refusals that stand between
an operator and a wasted batch:

    uv run python research/quality-measurement/feed_battery.py --selftest
    uv run python research/quality-measurement/feed_battery.py --attainability
    uv run python research/quality-measurement/feed_battery.py --dry-run --yes

Two refusals are structural, and each is a lesson from stage-0 encoded rather than remembered.
While `feed_core.CONTROL_MIN_SESSIONS` is None — its state until the sizing table has been
read — `--seat` refuses immediately: the number must be read off the attainability table and
set in a commit that cites it (done: `results/fcr-attainability.json`), and a driver happy to
bill before that reading is how §94.7 happened. And any
plan above `feed_core.CALL_GUARD` refuses without `--yes`, naming both numbers, because a pilot
that quietly became a battery is a spend nobody approved.

The seating itself: intact feeds over the fitness pool (each book against the next three,
wrapping), the fp1/fp3/fp4 control feeds on the pool's first member, sessions across all four
rotations, and fp6's flat-price block riding along at the same counts. Results go through
`feed_controls` and carry `PRE_REGISTRATION` verbatim plus its digest; a session set in which
nothing is scorable reports `"UNREADABLE"` and nothing is substituted, retried, or filled.
Published prose rides only behind `--published`, which stamps `PUBLISHED_WARNING` into the
result under `"warnings"` — no code path removes it.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bcr  # noqa: E402
import feed_controls  # noqa: E402
import feed_core  # noqa: E402
import feed_session  # noqa: E402
import feed_substrate  # noqa: E402
from elicit import Elicitor  # noqa: E402

RESULTS = HERE / "results"

#: Where the licensed substrate lives: the drafted fitness books, read through
#: `corpus_io.generated_scenes` via `feed_substrate.fitness_texts`. BRIEF §2 Pass 6's
#: un-memorised prose; published text enters only behind `--published`.
FITNESS_DIR = HERE / "corpora" / "fitness"

#: Fixed seed and trial count of the attainability table. A sizing table someone could re-seed
#: until it named the batch they wanted is not a sizing table, so both are constants like fp6's
#: bootstrap seed; the leg prints the trial count it ran beside the table. The seed is the
#: one the committed sizing table ran (`results/fcr-attainability.json`, 200 trials), so
#: this leg reprints a cheaper cut of the same seeded world.
_ATTAINABILITY_SEED = 20_260_824
_ATTAINABILITY_TRIALS = 40


# ------------------------------------------------------------------------------- the selftest leg


class _ScriptedElicitor:
    """Pops one pre-written raw record per ask; the seam `elicit.Elicitor.ask_raw` fills."""

    def __init__(self, records: Sequence[dict[str, Any]]) -> None:
        self._records = list(records)

    def ask_raw(
        self,
        system: str,
        turns: list[dict[str, Any]],
        *,
        schema: dict[str, object] | None,
        max_tokens: int,
        tag: dict[str, Any],
        sample: int = 0,
        model: str | None = None,
    ) -> dict[str, Any]:
        del system, turns, schema, max_tokens, tag, model
        return self._records.pop(0)


def _member_text(marker: str) -> str:
    """One synthetic feed member holding exactly `feed_core.MIN_CHUNKS_FEED` chunks.

    One paragraph per chunk, each just over `CHUNK_WORDS`, so `bcr.chunks` cannot merge
    paragraphs and the count is known before anything runs.
    """
    return "\n\n".join(
        " ".join(f"{marker}p{paragraph}w{word}" for word in range(feed_core.CHUNK_WORDS + 5))
        for paragraph in range(feed_core.MIN_CHUNKS_FEED)
    )


def selftest() -> int:
    """Prove the guards and the arithmetic before a call is bought. Free: no model, no GPU."""
    failures: list[str] = []

    # The registration is content-addressed, and every result file will carry this digest;
    # a digest that moved between two calls in one process would stamp nothing.
    if feed_core.registration_digest() != feed_core.registration_digest():
        failures.append("the registration digest is not stable")

    # fp5's operating characteristic, both documented halves: fixed patterns score exactly
    # 0.0 and FAIL by construction, and the content-driven allocator clears the floor.
    try:
        characteristic = feed_controls.fp5_operating_characteristic()
    except AssertionError as exc:
        failures.append(f"fp5's operating characteristic did not hold: {exc}")
    else:
        broken = [
            pattern
            for pattern, block in characteristic["fixed_patterns"].items()
            if block["statistic"] != 0.0 or block["verdict"] != "FAIL"
        ]
        if broken:
            failures.append(f"fixed patterns did not score 0.0 and FAIL on fp5: {broken}")
        if characteristic["dirichlet_clear_rate"] < characteristic["required_clear_rate"]:
            failures.append(
                f"the dirichlet allocator cleared fp5's floor in only "
                f"{characteristic['dirichlet_clear_rate']:.0%} of trials"
            )

    # One deterministic session, run twice through the real loop: same script, same bytes out.
    # A loop that hid state between sessions would make replicates lie about being replicates.
    text = _member_text("selftest")
    feed = feed_core.FeedSpec(
        feed_id="selftest", arm="selftest", target=text, others=(text, text, text)
    )
    script = [
        {
            "refused": False,
            "text": json.dumps(
                {"action": "skim", "book": feed_core.SLOTS[step % feed_core.FEED_SIZE]}
            ),
        }
        # Skims price at 1, so exhausting the 27-unit budget takes every one of MAX_STEPS
        # steps: the longest session the instrument allows.
        for step in range(feed_core.MAX_STEPS)
    ]
    # Identical arguments and fresh scripts: the only difference allowed between the records
    # is none. (The record carries `replicate`, so replicates 0 and 1 are not byte-equal by
    # design; determinism is asserted at fixed rotation and replicate.)
    runs = [
        feed_session.run_feed_session(
            _ScriptedElicitor(script), feed, model="selftest", rotation=0, replicate=0
        )
        for _ in (0, 1)
    ]
    if runs[0] != runs[1]:
        failures.append("two identical scripted sessions produced different records")
    if not runs[0].scorable or runs[0].spent_units != feed_core.BUDGET_UNITS:
        failures.append("the nine-skim script did not come back scorable with the budget spent")

    # The worst-case chunk arithmetic, checked against a synthetic full-length member: a
    # budget spent entirely on one slot consumes MIDSTREAM_CHUNK + BUDGET_UNITS//READ_COST
    # sections, so that is the floor, and a member one under it must fault.
    if feed_core.MIN_CHUNKS_FEED != (
        feed_core.MIDSTREAM_CHUNK + feed_core.BUDGET_UNITS // feed_core.READ_COST
    ):
        failures.append("MIN_CHUNKS_FEED is not the mid-stream entry plus the worst-case reads")
    if len(bcr.chunks(text)) < feed_core.MIN_CHUNKS_FEED:
        failures.append("the synthetic full-length member held fewer chunks than it was built for")
    if feed.fault() is not None:
        failures.append(f"a full-length synthetic member faulted: {feed.fault()}")
    short = "\n\n".join(text.split("\n\n")[:-1])
    short_feed = feed_core.FeedSpec(
        feed_id="short", arm="selftest", target=short, others=(text, text, text)
    )
    if short_feed.fault() is None:
        failures.append("a member one chunk short of the worst case was accepted")

    for line in failures:
        print(f"FAIL {line}", file=sys.stderr)
    print("selftest: " + ("FAILED" if failures else "passed"), file=sys.stderr)
    return 1 if failures else 0


# -------------------------------------------------------------------------- the attainability leg


def attainability_leg() -> int:
    """Print `feed_controls.sessions_needed` as an aligned table plus the paragraph that gates.

    Counts are rows; reader models and biases are columns. The table runs at
    `_ATTAINABILITY_TRIALS` under `_ATTAINABILITY_SEED`, both fixed and both printed — a sizing
    number that moved with a seed or a trial count someone could shrink silently would not be
    a sizing number. The paragraph names what `feed_core.CONTROL_MIN_SESSIONS` must be read off
    this table, and that this driver refuses every paid run while the constant is None.
    """
    report = feed_controls.sessions_needed(seed=_ATTAINABILITY_SEED, trials=_ATTAINABILITY_TRIALS)
    models = report["models"]
    roles = list(next(iter(models.values()))["bias_used"])
    print(f"trials={report['trials']}  band={report['band']}  alpha={report['alpha']}")
    header = " | ".join(f"{model}.{role}" for model in models for role in roles)
    print(f"{'sessions':>8} | {header}")
    for size in report["candidates"]:
        cells: list[float] = []
        for model in models:
            by_size = models[model]["by_sessions"][str(size)]
            cells.extend(
                by_size["pass_at_uniform" if role == "uniform" else f"pass_{role}"]
                for role in roles
            )
        row = " | ".join(f"{cell:>13.3f}" for cell in cells)
        print(f"{size:>8} | {row}")
    print(
        "\nfeed_core.CONTROL_MIN_SESSIONS must be read off this table — from the first row "
        "whose uniform column is high while its biased-reader columns stay low, per reader "
        "model — and set in a commit that cites the table. It starts as None, and this "
        "driver refuses every paid run (--seat) while it is None."
    )
    return 0


# ------------------------------------------------------------------------------------ the seating


@dataclass(frozen=True, slots=True)
class PlannedFeed:
    """One seating entry: the member names in pool order, their chunk counts, and the spec."""

    names: tuple[str, ...]
    chunk_counts: tuple[int, ...]
    spec: feed_core.FeedSpec


def seating_plan(texts: Sequence[tuple[str, str]]) -> list[PlannedFeed]:
    """Intact feeds over the whole pool, plus the fp1/fp3/fp4 controls on its first member.

    Deterministic, no sampling: intact feed `i` seats book `i` as target against books
    `i+1..i+3` wrapping the pool, so every book is measured against every neighbour and the
    seating policy lives in exactly one place. Refuses a pool smaller than the registered feed
    size here rather than letting `intact_feed` discover it mid-build.
    """
    if len(texts) < feed_core.FEED_SIZE:
        raise ValueError(
            f"{len(texts)} book(s) on the pool; seating an intact feed of "
            f"{feed_core.FEED_SIZE} needs {feed_core.FEED_SIZE}"
        )
    plan: list[PlannedFeed] = []
    for index in range(len(texts)):
        pool = [texts[(index + offset) % len(texts)] for offset in range(feed_core.FEED_SIZE)]
        plan.append(
            PlannedFeed(
                names=tuple(name for name, _ in pool),
                chunk_counts=tuple(len(bcr.chunks(member)) for _, member in pool),
                spec=feed_substrate.intact_feed(f"intact-{index:02d}", pool[0], pool[1:]),
            )
        )
    first_name, first_text = texts[0]
    controls = (
        (f"fp1-{first_name}", feed_substrate.placebo_feed),
        (f"fp3-{first_name}", feed_substrate.whitespace_feed),
        (f"fp4-{first_name}", feed_substrate.rename_feed),
    )
    for feed_id, build in controls:
        plan.append(
            PlannedFeed(
                names=(first_name,) * feed_core.FEED_SIZE,
                chunk_counts=(len(bcr.chunks(first_text)),) * feed_core.FEED_SIZE,
                spec=build(feed_id, first_text),
            )
        )
    return plan


def planned_counts(feeds: int, replicates: int) -> dict[str, int]:
    """Sessions and worst-case calls for a seat of `feeds` x `replicates`, derived, not guessed.

    Every feed runs once per rotation (`feed_core.FEED_SIZE` of them), and fp6's flat-price
    block rides along at the same counts. Worst-case calls assume every action is its own
    request: `feed_core.MAX_STEPS` skims drain the budget one call at a time.
    """
    cheap = feeds * feed_core.FEED_SIZE * replicates
    flat = cheap
    sessions = cheap + flat
    return {
        "feeds": feeds,
        "cheap_sessions": cheap,
        "flat_sessions": flat,
        "sessions": sessions,
        "max_calls": sessions * feed_core.MAX_STEPS,
    }


def run_block(
    elicitor: feed_session.SupportsAskRaw,
    plan: Sequence[PlannedFeed],
    *,
    model: str,
    replicates: int,
    skim_cost: int,
) -> list[feed_core.FeedSession]:
    """Every planned feed across every rotation and replicate, at the given skim price.

    `skim_cost` is `feed_core.SKIM_COST` for the registered block and `feed_core.READ_COST`
    for the fp6 flat-price block — the one override `feed_session` documents.
    """
    sessions: list[feed_core.FeedSession] = []
    for planned in plan:
        for rotation in range(feed_core.FEED_SIZE):
            for replicate in range(replicates):
                sessions.append(
                    feed_session.run_feed_session(
                        elicitor,
                        planned.spec,
                        model=model,
                        rotation=rotation,
                        replicate=replicate,
                        skim_cost=skim_cost,
                    )
                )
    return sessions


def controls_block(
    cheap: Sequence[feed_core.FeedSession], flat: Sequence[feed_core.FeedSession]
) -> dict[str, Any]:
    """Results through `feed_controls`, with the no-fallback rule applied at the top.

    An arm with nothing scorable reports verdict `"UNREADABLE"` and stops there: no
    substitution, no retry, no filling. `fp5` and `fp6` already refuse thin data themselves
    and are called as they are.
    """
    everything = [*cheap, *flat]
    blocks: dict[str, Any] = {"fp5_non_degenerate": feed_controls.fp5_non_degenerate(everything)}
    for arm in dict.fromkeys(session.arm for session in everything):
        arm_sessions = [session for session in everything if session.arm == arm]
        usable = feed_controls.scorable(arm_sessions)
        if not usable:
            blocks[f"{arm}:target_share"] = {
                "control": f"{arm}:target_share",
                "verdict": "UNREADABLE",
                "why": f"0 of {len(arm_sessions)} session(s) scorable; nothing substituted",
                "observations": 0,
            }
            continue
        blocks[f"{arm}:target_share"] = {
            "scorable": len(usable),
            **feed_controls.equivalence_control(
                f"{arm}:target_share",
                [session.target_read_share for session in usable],
                centre=feed_controls.CENTRE,
            ),
        }
    blocks["fp6_skim_price"] = feed_controls.fp6_skim_price(cheap, flat)
    return blocks


def write_result(result: dict[str, Any], path: Path) -> None:
    """The one writer: sorted keys, indented, one trailing newline, LF endings."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")


# --------------------------------------------------------------------------------------- the CLI


def main(argv: list[str] | None = None) -> int:
    """Compose the legs. Tests call this in-process; no sys.exit outside `__main__`."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true", help="free: prove the guards")
    parser.add_argument(
        "--attainability", action="store_true", help="free: the patterned-reader sizing table"
    )
    parser.add_argument("--dry-run", action="store_true", help="build the seating; no call")
    parser.add_argument("--seat", action="store_true", help="paid: the screen, all four rotations")
    parser.add_argument(
        "--feeds",
        type=int,
        default=None,
        help="screen: limit the plan to its first N feeds; the result is stamped a screen",
    )
    parser.add_argument("--model", default="qwen3:14b")
    parser.add_argument("--replicates", type=int, default=3)
    parser.add_argument("--cache", default="fcr-raw.jsonl", help="replay cache file for --seat")
    parser.add_argument(
        "--out", default=None, help="result file for --seat; default under results/"
    )
    parser.add_argument("--yes", action="store_true", help="consent to spend above the guard")
    parser.add_argument(
        "--published",
        action="store_true",
        help="published prose in the feed; stamps PUBLISHED_WARNING onto the result",
    )
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.attainability:
        return attainability_leg()
    if not (args.dry_run or args.seat):
        parser.error("pass one of --selftest, --attainability, --dry-run, --seat")

    # The sizing gate, before anything else touches the corpus: a paid run while
    # CONTROL_MIN_SESSIONS is unset is the exact failure stage-0 §94.7 recorded.
    if args.seat and feed_core.CONTROL_MIN_SESSIONS is None:
        print(
            "refusing --seat: feed_core.CONTROL_MIN_SESSIONS is None; read the "
            "patterned-reader attainability table (--attainability), set the number in a "
            "commit that cites it, and re-run",
            file=sys.stderr,
        )
        return 1

    if args.feeds is not None and args.feeds < 1:
        parser.error("--feeds must be at least 1")

    plan = seating_plan(feed_substrate.fitness_texts(FITNESS_DIR))
    pool_feeds = len(plan)
    if args.feeds is not None:
        # A capped plan is a screen, never a seat — §89's no-silent-caps rail: the cap
        # is printed here and stamped into the result, so a limited run can never read
        # as a covered pool. §94.6 is why the knob exists at all: a six-session screen
        # killed two of four BCR readers before a seating budget was spent on them.
        plan = plan[: args.feeds]
        print(f"screen: first {len(plan)} of {pool_feeds} planned feed(s)")
    counts = planned_counts(len(plan), args.replicates)
    # The plan report is the dry-run leg's product, so it goes to stdout; refusals go to
    # stderr below.
    print(
        f"{counts['feeds']} feed(s); {counts['sessions']} session(s) "
        f"({counts['cheap_sessions']} at registered prices + {counts['flat_sessions']} "
        f"flat-price fp6); at most {counts['max_calls']} call(s) on {args.model}"
    )
    for planned in plan:
        fault = planned.spec.fault()
        status = "ok" if fault is None else f"FAULT: {fault}"
        members = ", ".join(
            f"{name}={held}" for name, held in zip(planned.names, planned.chunk_counts, strict=True)
        )
        print(f"  {planned.spec.feed_id:16s} {planned.spec.arm:14s} [{status}] {members}")

    if counts["max_calls"] > feed_core.CALL_GUARD and not args.yes:
        print(
            f"{counts['max_calls']} planned calls is above the {feed_core.CALL_GUARD} guard; "
            "pass --yes to proceed",
            file=sys.stderr,
        )
        return 1
    if args.dry_run:
        return 0
    if not args.yes:
        print(
            "pass --yes to spend, or --dry-run to exercise the arithmetic without spending",
            file=sys.stderr,
        )
        return 1

    warnings = [feed_core.PUBLISHED_WARNING] if args.published else []
    with Elicitor(
        Path(args.cache),
        model=args.model,
        spot_model=None,
        transport="ollama",
        dry_run=False,
    ) as elicitor:
        cheap = run_block(
            elicitor,
            plan,
            model=args.model,
            replicates=args.replicates,
            skim_cost=feed_core.SKIM_COST,
        )
        flat = run_block(
            elicitor,
            plan,
            model=args.model,
            replicates=args.replicates,
            skim_cost=feed_core.READ_COST,
        )
        spend = elicitor.spend()

    result: dict[str, Any] = {
        "study": "fcr_screen" if args.feeds is not None else "fcr_seat",
        "plan_cap": (
            None if args.feeds is None else {"feeds": len(plan), "of_pool": pool_feeds}
        ),
        "registration": feed_core.PRE_REGISTRATION,
        "registration_digest": feed_core.registration_digest(),
        "model": args.model,
        "replicates": args.replicates,
        "planned": counts,
        "spend": spend,
        "warnings": warnings,
        "sessions_cheap": [asdict(session) for session in cheap],
        "sessions_flat": [asdict(session) for session in flat],
        "controls": controls_block(cheap, flat),
    }
    kind = "screen" if args.feeds is not None else "seat"
    out = (
        Path(args.out)
        if args.out
        else RESULTS / f"fcr-{kind}-{args.model.replace(':', '-')}.json"
    )
    write_result(result, out)
    print(f"wrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
