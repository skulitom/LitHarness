"""A cost that bites: does a costed reader's stop point move when the target's order is destroyed?

`cost-that-bites/PREREG.md` beside this module's arm directory is the registration; this
module carries the frozen constants, the two target manipulations, the paired plan, the session
runner with its ceiling, and the reading fixed before spend. It is `fcr.v0` pointed at the
shuffle: nothing in `feed_core`, `feed_session`, `feed_substrate` or `feed_controls` is edited,
because their bytes are the registered instrument (stage-0 §122) and the fitness shelf they fit
is the substrate. What is new is the *question*, and the plan that asks it.

**The question.** The readers' order control (§199.1) found both `readers` lanes carrying on
four of four whether the chapter was in order or not: continuing cost nothing, so nothing
stopped. `fcr.v0` is the one reader in this house whose continuing costs something it can run
out of — twenty-four minutes across four books, reads at three and skims at one, spending
forced. Here a feed's target book is shown three ways to the same reader at the same rotation:
as drafted (`intact`), with every paragraph of the book shuffled (`shuffled`), and with only its
whitespace re-flowed (`sham`, `ablate.rewhitespace` — the standing placebo that has killed
instruments before, §78, §81). The competitors are the same three intact books in all three.
The datum is `fcr.v0`'s own: the target's share of full reads, and the step after which the
target never got another full read.

**The reading, fixed before spend and repeated in the PREREG.** Per feed and rotation, the
paired differences `intact - shuffled` and `sham - shuffled`, each a cluster bootstrap over
feeds at the registered alpha. The stop point *moves with order* only if both intervals sit
strictly above zero — the shuffle has to move the reader further than the whitespace sham does,
per sham and never pooled (BRIEF §2 Pass 6). An `intact - shuffled` interval that contains
zero is the null the handoff names: the costed reader's stop point does not move under the
strongest order manipulation this house owns, and the direction closes for this reader at this
n. Preconditions, read first: `fp5` (a fixed pattern wearing a budget is not a reader) and the
scorable floor (a session with any unanswered step is reported, never scored, `fcr.v0`'s rule).

**What this refuses.** No bar over any effect size: the intervals are directional readings and
the attainability leg prints what a shift of one read in eight looks like at the real n before
anything is bought. No reader is retuned on the result (§89, §97.1). No skim-derived number is
read — the skim-price control (`fp6`) is not run here and the skim rate is a diagnostic. No
model ranks anything: the reader allocates minutes, code reads the allocation.

    uv run python research/quality-measurement/cost_that_bites.py --selftest
    uv run python research/quality-measurement/cost_that_bites.py --attainability
    uv run python research/quality-measurement/cost_that_bites.py --dry-run
    uv run python research/quality-measurement/cost_that_bites.py --screen --yes
    uv run python research/quality-measurement/cost_that_bites.py --arm --yes
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import threading
import time
from collections import Counter
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import ablate  # noqa: E402
import bcr  # noqa: E402
import feed_controls  # noqa: E402
import feed_core  # noqa: E402
import feed_session  # noqa: E402
import feed_substrate  # noqa: E402

ARM_DIR = HERE / "cost-that-bites"
FITNESS_DIR = HERE / "corpora" / "fitness"

# ---------------------------------------------------------------- the registration, frozen

VERSION = "cost-that-bites.v0"

#: The three ways the target is shown. `intact` is the book as drafted; `shuffled` is every
#: paragraph of the whole book in a seeded random order (a real shuffle, not `ablate`'s
#: rotation-derangement, which at strength 1.0 is a single cut); `sham` is the standing
#: whitespace placebo, not one character of any word moved.
VERSIONS: tuple[str, ...] = ("intact", "shuffled", "sham")

#: Salt of the shuffle's seed. The seed is derived from the text plus this salt
#: (`ablate._rng`'s discipline), so the shuffle is a function of the book and not of the run.
SHUFFLE_SALT = "cost-that-bites/shuffle"

#: The sham's strength: the whole edit, every paragraph re-flowed, the separator kept.
SHAM_STRENGTH = 1.0

#: The reader. The house's panel tier (`elicit.PANEL_MODEL`), through the `claude -p`
#: transport with the two hardening flags (§109). A different model is a different reader and
#: gets its own result file, labelled and never pooled.
READER_MODEL = "claude-haiku-4-5"
TRANSPORT = "cli"

#: Feeds the screen reads before the arm is bought: `fp5`, the scorable floor and the price
#: per session are what it buys, never the effect — the attainability leg says why.
SCREEN_FEEDS = 2

#: Sessions in flight at once. Three is what turned a 21-hour serial run into seven on this
#: transport (RUNBOOK); one CLI arm at a time across the box is the rule this runs under.
WORKERS = 3

#: Subscription-equivalent ceilings, refusals rather than notes. The screen prices the
#: session; the arm's ceiling is sized from the screen's price and is registered before the
#: screen runs. A run that reaches its ceiling stops between sessions, keeps every session
#: bought, and stamps `stopped_at_ceiling` into its result.
CEILING_SCREEN_USD = 10.0
CEILING_ARM_USD = 80.0

#: The registered alpha of every interval here: `feed_core.CONTROL_ALPHA`, two one-sided
#: tests at 5% each, a 90% interval. Imported rather than restated.
ALPHA = feed_core.CONTROL_ALPHA

#: Share of a version's sessions that must be scorable for that version to be read at all.
#: A version below it is UNREADABLE and nothing is substituted, retried or filled.
SCORABLE_FLOOR = 0.75

#: Seed of the attainability simulation, fixed so the sizing table cannot be re-rolled.
ATTAINABILITY_SEED = 20_260_903

#: Refuse above this many worst-case calls without `--yes`.
CALL_GUARD = 1_000

PRE_REGISTRATION: dict[str, Any] = {
    "version": VERSION,
    "instrument": feed_core.FCR_VERSION,
    "instrument_registration_digest": feed_core.registration_digest(),
    "versions": list(VERSIONS),
    "shuffle_salt": SHUFFLE_SALT,
    "sham": "ablate.rewhitespace",
    "sham_strength": SHAM_STRENGTH,
    "reader_model": READER_MODEL,
    "transport": TRANSPORT,
    "screen_feeds": SCREEN_FEEDS,
    "rotations": feed_core.FEED_SIZE,
    "replicates": 1,
    "workers": WORKERS,
    "ceiling_screen_usd": CEILING_SCREEN_USD,
    "ceiling_arm_usd": CEILING_ARM_USD,
    "alpha": ALPHA,
    "scorable_floor": SCORABLE_FLOOR,
    "attainability_seed": ATTAINABILITY_SEED,
    "primary": "target_read_share, paired per (feed, rotation): intact - shuffled",
    "sham_reading": "sham - shuffled, per sham and never pooled",
    "secondary": "abandonment_step, first full read on the target, paired the same way",
    "cluster": "feed",
    "decision": {
        "UNREADABLE": "fp5 not PASS, or a version under the scorable floor, or fewer than "
                      "two feeds with a complete scorable triple",
        "MOVES_WITH_ORDER": "the intact - shuffled interval and the sham - shuffled "
                            "interval both lie strictly above zero",
        "MOVES_WITH_EDITEDNESS": "intact - shuffled lies above zero and sham - shuffled "
                                 "does not: the reader moves for surface damage as much "
                                 "as for order",
        "NULL": "the intact - shuffled interval contains zero: the stop point does not "
                "move under the shuffle at this n; the direction closes for this reader",
        "INVERTED": "the intact - shuffled interval lies strictly below zero; reported as "
                    "what it is, never read as a preference for disorder",
    },
    "not_run": {
        "fp6": "the skim-price control is not run; no skim-derived number is read",
        "D1P": "the platform-prior families need a seated reader and $16 of generation "
               "before any dose exists; the shuffle is the owned manipulation",
    },
}


def registration_digest() -> str:
    """Content address of the registration, printed on every result file."""
    material = json.dumps(PRE_REGISTRATION, sort_keys=True, ensure_ascii=False)
    return sha256(material.encode("utf-8")).hexdigest()[:16]


# ------------------------------------------------------------------- the target's versions


def book_shuffle(text: str, *, index: int = 0) -> str:
    """Every paragraph of the book in a seeded random order. Word-preserving.

    A real shuffle, seeded from the text and the salt, so two runs shuffle one book the same
    way and two books never share an order. `ablate.paragraph_shuffle` is not used because at
    strength 1.0 it is a rotation by one offset — one cut in an otherwise ordered book — and the
    question here needs the order destroyed. If the draw happens to return the identity (it
    cannot for any real book, but a two-paragraph text can) the order is rotated by one, so a
    "shuffled" copy is never byte-identical to its intact copy.

    `index` selects one of several shuffles of the same book, for v2's three-seeds-per-book
    design. **Index 0 is byte-identical to what v1 bought** — it uses the bare salt — so every
    v1 record still replays and v1's committed numbers are untouched.
    """
    blocks = ablate.paragraphs(text)
    if len(blocks) < 2:
        raise ValueError("a book needs at least two paragraphs to shuffle")
    order = list(range(len(blocks)))
    salt = SHUFFLE_SALT if index == 0 else f"{SHUFFLE_SALT}/{index}"
    ablate._rng(text, salt).shuffle(order)
    if order == list(range(len(blocks))):
        order = order[1:] + order[:1]
    return "\n\n".join(blocks[index] for index in order)


def sham(text: str) -> str:
    """The standing whitespace placebo at the registered strength."""
    return ablate.rewhitespace(text, SHAM_STRENGTH)


def versions_of(text: str) -> dict[str, str]:
    """The three target texts, keyed by version name."""
    return {"intact": text, "shuffled": book_shuffle(text), "sham": sham(text)}


# ------------------------------------------------------------------------------- the plan


@dataclass(frozen=True, slots=True)
class Cell:
    """One session to buy: a feed, a target version, a rotation."""

    feed_index: int
    target_name: str
    version: str
    rotation: int
    spec: feed_core.FeedSpec
    chunk_counts: tuple[int, ...]
    #: v2's replicate index. v1 buys one session per (feed, version, rotation) and leaves it
    #: at 0, which is what `run_feed_session` was already being passed, so v1's cache keys and
    #: sampler indices are unchanged.
    replicate: int = 0

    @property
    def pair_key(self) -> str:
        """What the three versions of one session share: the feed and the rotation."""
        return f"{self.feed_index:02d}:{self.rotation}"

    @property
    def book_key(self) -> str:
        """v2's cluster: the book, whatever version or replicate this session carries."""
        return f"{self.feed_index:02d}"


def plan(texts: Sequence[tuple[str, str]], *, feeds: int | None = None) -> list[Cell]:
    """Every feed's three versions across every rotation, in a fixed order.

    Feed `i` seats book `i` as the target against books `i+1..i+3` wrapping the pool —
    `feed_battery.seating_plan`'s seating, so the intact sessions here are the seating's own.
    A cap turns the plan into a screen and the caller stamps it; the plan itself never hides
    the cap.
    """
    if len(texts) < feed_core.FEED_SIZE:
        raise ValueError(
            f"{len(texts)} book(s) on the pool; a feed of {feed_core.FEED_SIZE} needs "
            f"{feed_core.FEED_SIZE}"
        )
    count = len(texts) if feeds is None else min(feeds, len(texts))
    cells: list[Cell] = []
    for index in range(count):
        target_name, target_text = texts[index]
        others = [texts[(index + offset) % len(texts)] for offset in range(1, feed_core.FEED_SIZE)]
        for version, target in versions_of(target_text).items():
            spec = feed_core.FeedSpec(
                feed_id=f"ctb-{index:02d}-{version}",
                arm=version,
                target=target,
                others=tuple(text for _, text in others),
                note=(
                    f"target={target_name} ({version}) "
                    f"others={','.join(name for name, _ in others)}"
                ),
            )
            counts = tuple(len(bcr.chunks(text)) for text in spec.texts())
            for rotation in range(feed_core.FEED_SIZE):
                cells.append(
                    Cell(
                        feed_index=index,
                        target_name=target_name,
                        version=version,
                        rotation=rotation,
                        spec=spec,
                        chunk_counts=counts,
                    )
                )
    return cells


def faults(cells: Sequence[Cell]) -> dict[str, str]:
    """Feed id to fault, for every cell whose feed cannot carry a session. Listed, never dropped.

    Two faults beyond `FeedSpec.fault`'s: a `shuffled` or `sham` target byte-identical to its
    `intact` target is not a manipulation — a sham that changed nothing would make its pair a
    replicate wearing a control's name — and is refused by name here rather than run.
    """
    out: dict[str, str] = {}
    intact_by_feed = {
        cell.feed_index: cell.spec.target for cell in cells if cell.version == "intact"
    }
    for cell in cells:
        fault = cell.spec.fault()
        if fault is None and cell.version != "intact":
            intact = intact_by_feed.get(cell.feed_index)
            if intact is not None and cell.spec.target == intact:
                fault = f"the {cell.version} target is byte-identical to the intact target"
        if fault is not None:
            out[cell.spec.feed_id] = fault
    return out


def planned_counts(cells: Sequence[Cell]) -> dict[str, int]:
    return {
        "feeds": len({cell.feed_index for cell in cells}),
        "sessions": len(cells),
        "max_calls": len(cells) * feed_core.MAX_STEPS,
    }


# ---------------------------------------------------------------------------- the runner


@dataclass(frozen=True, slots=True)
class Row:
    """One bought session beside the cell that asked for it."""

    feed_index: int
    target_name: str
    version: str
    rotation: int
    pair_key: str
    session: feed_core.FeedSession
    replicate: int = 0

    @property
    def book_key(self) -> str:
        return f"{self.feed_index:02d}"


def run_cells(
    elicitor: Any,
    cells: Sequence[Cell],
    *,
    model: str,
    ceiling_usd: float,
    workers: int,
    call_ceiling: int | None = None,
    log: Callable[[str], None] = print,
) -> tuple[list[Row], dict[str, Any]]:
    """Buy every cell, `workers` sessions at a time, stopping between sessions at the ceiling.

    Each session is sequential inside itself (`feed_session.run_feed_session`); the pool runs
    sessions beside each other. The ceiling is read from the elicitor's own cache before every
    session starts, so a run never starts a session it cannot afford and never abandons one it
    has started. Every session bought is in the cache whether or not the run finished, which
    is what makes a stopped run resumable for free.
    """
    rows: list[Row] = []
    lock = threading.Lock()
    stopped = threading.Event()
    started = time.monotonic()
    pending = list(cells)

    def next_cell() -> Cell | None:
        with lock:
            if stopped.is_set() or not pending:
                return None
            # **Priced only when a dollar ceiling can actually stop the run.** v2 and v3 stop on
            # a call ceiling and pass `inf` here, so this used to sum the whole cache about 180
            # times an arm purely to compare it against infinity — pure waste, and from this
            # side the sole trigger of §228's race, since `spend()` is what the scheduler read
            # while workers wrote. The lock on main fixes the race; this removes the reason to
            # take it. Both ceilings are still read **between sessions**, so a session that has
            # started always finishes, which is the property the registration depends on.
            if ceiling_usd != float("inf"):
                spent = float(elicitor.spend()["equivalent_usd"])
                if spent >= ceiling_usd:
                    stopped.set()
                    log(
                        f"ceiling: ${spent:.2f} of ${ceiling_usd:.2f} spent; "
                        "stopping between sessions"
                    )
                    return None
            # v2's stop condition is a call ceiling rather than a dollar one; both are read
            # between sessions, so a session that has started always finishes.
            bought = int(getattr(elicitor, "api_calls", 0) or 0)
            if call_ceiling is not None and bought >= call_ceiling:
                stopped.set()
                log(f"ceiling: {bought} of {call_ceiling} calls bought; stopping between sessions")
                return None
            return pending.pop(0)

    def worker() -> None:
        while (cell := next_cell()) is not None:
            session = feed_session.run_feed_session(
                elicitor, cell.spec, model=model, rotation=cell.rotation, replicate=cell.replicate
            )
            row = Row(
                feed_index=cell.feed_index,
                target_name=cell.target_name,
                version=cell.version,
                rotation=cell.rotation,
                pair_key=cell.pair_key,
                session=session,
                replicate=cell.replicate,
            )
            with lock:
                rows.append(row)
                done = len(rows)
            share = session.target_read_share if session.scorable else float("nan")
            log(
                f"  [{done}/{len(cells)}] {cell.spec.feed_id} r{cell.rotation}: "
                f"{'ok' if session.scorable else session.exit_note or 'unscorable'} "
                f"share={share:.3f} skims={session.skims_of(session.target_slot)} "
                f"steps={len(session.actions)} {time.monotonic() - started:.0f}s"
            )

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(worker) for _ in range(workers)]
        for future in futures:
            future.result()
    rows.sort(key=lambda row: (row.feed_index, row.version, row.rotation))
    ledger = {
        "spend": elicitor.spend(),
        "api_calls": getattr(elicitor, "api_calls", None),
        "replayed": getattr(elicitor, "replayed", None),
        "transport_failures": getattr(elicitor, "transport_failures", None),
        "failure_reasons": dict(getattr(elicitor, "failure_reasons", {}) or {}),
        "sessions_planned": len(cells),
        "sessions_run": len(rows),
        "stopped_at_ceiling": stopped.is_set(),
        "ceiling_usd": ceiling_usd,
        "seconds": round(time.monotonic() - started, 1),
    }
    return rows, ledger


# --------------------------------------------------------------------------- the reading


def _first_read_on_target(session: feed_core.FeedSession) -> float:
    """1.0 if the first full read of the session went to the target, else 0.0 (no reads: 0.0)."""
    for action, where in session.actions:
        if action == "read":
            return 1.0 if where == session.target_slot else 0.0
    return 0.0


def triples(rows: Sequence[Row]) -> dict[str, dict[str, Row]]:
    """Pair key to version to row, for pair keys whose three versions are all scorable."""
    by_key: dict[str, dict[str, Row]] = {}
    for row in rows:
        by_key.setdefault(row.pair_key, {})[row.version] = row
    return {
        key: versions
        for key, versions in by_key.items()
        if all(
            version in versions and versions[version].session.scorable for version in VERSIONS
        )
    }


def paired(
    complete: dict[str, dict[str, Row]], measure: Callable[[feed_core.FeedSession], float]
) -> dict[str, list[tuple[str, float]]]:
    """The three paired differences of one measure, each as `(feed cluster, value)` pairs."""
    out: dict[str, list[tuple[str, float]]] = {
        "intact_minus_shuffled": [],
        "intact_minus_sham": [],
        "sham_minus_shuffled": [],
    }
    for key in sorted(complete):
        versions = complete[key]
        cluster = key.split(":")[0]
        intact = measure(versions["intact"].session)
        shuffled = measure(versions["shuffled"].session)
        placebo = measure(versions["sham"].session)
        out["intact_minus_shuffled"].append((cluster, intact - shuffled))
        out["intact_minus_sham"].append((cluster, intact - placebo))
        out["sham_minus_shuffled"].append((cluster, placebo - shuffled))
    return out


def interval_block(values: Sequence[tuple[str, float]]) -> dict[str, Any]:
    """`bcr.cluster_interval` at the registered alpha, as a JSON block; None below two clusters."""
    interval = bcr.cluster_interval(values, alpha=ALPHA) if values else None
    if interval is None:
        return {
            "observations": len(values),
            "clusters": len({key for key, _ in values}),
            "interval": None,
            "why": "fewer than two clusters; no interval",
        }
    return {
        "observations": interval.observations,
        "clusters": interval.clusters,
        "point": interval.point,
        "low": interval.low,
        "high": interval.high,
        "alpha": interval.alpha,
        "above_zero": interval.low > 0.0,
        "below_zero": interval.high < 0.0,
    }


def decide(
    *,
    fp5_verdict: str,
    readable_versions: bool,
    complete_clusters: int,
    shuffle: dict[str, Any],
    order: dict[str, Any],
) -> str:
    """The decision table, assembled in one place and nowhere else."""
    if fp5_verdict != "PASS" or not readable_versions or complete_clusters < 2:
        return "UNREADABLE"
    if "above_zero" not in shuffle or "above_zero" not in order:
        return "UNREADABLE"
    if shuffle["above_zero"] and order["above_zero"]:
        return "MOVES_WITH_ORDER"
    if shuffle["above_zero"]:
        return "MOVES_WITH_EDITEDNESS"
    if shuffle["below_zero"]:
        return "INVERTED"
    return "NULL"


def reading(rows: Sequence[Row]) -> dict[str, Any]:
    """Everything the PREREG says is read, computed once, over the rows as they are."""
    sessions = [row.session for row in rows]
    per_version: dict[str, Any] = {}
    for version in VERSIONS:
        mine = [row.session for row in rows if row.version == version]
        usable = [session for session in mine if session.scorable]
        per_version[version] = {
            "sessions": len(mine),
            "scorable": len(usable),
            "scorable_share": (len(usable) / len(mine)) if mine else None,
            "exit_notes": dict(Counter(s.exit_note for s in mine if not s.scorable)),
            "mean_target_read_share": (
                statistics.fmean(s.target_read_share for s in usable) if usable else None
            ),
            "mean_abandonment_step": (
                statistics.fmean(s.abandonment_step for s in usable) if usable else None
            ),
            "first_read_on_target_share": (
                statistics.fmean(_first_read_on_target(s) for s in usable) if usable else None
            ),
            "mean_skim_rate": statistics.fmean(s.skim_rate for s in usable) if usable else None,
            "all_skim_sessions": sum(1 for s in usable if s.total_reads == 0),
            "target_never_read": sum(1 for s in usable if s.abandonment_step < 0),
        }
    readable = all(
        block["sessions"] > 0
        and block["scorable_share"] is not None
        and block["scorable_share"] >= SCORABLE_FLOOR
        for block in per_version.values()
    )
    complete = triples(rows)
    share_pairs = paired(complete, lambda s: s.target_read_share)
    step_pairs = paired(complete, lambda s: float(s.abandonment_step))
    first_pairs = paired(complete, _first_read_on_target)
    fp5 = feed_controls.fp5_non_degenerate(sessions)
    shuffle_block = interval_block(share_pairs["intact_minus_shuffled"])
    order_block = interval_block(share_pairs["sham_minus_shuffled"])
    complete_clusters = len({key.split(":")[0] for key in complete})
    decision = decide(
        fp5_verdict=str(fp5["verdict"]),
        readable_versions=readable,
        complete_clusters=complete_clusters,
        shuffle=shuffle_block,
        order=order_block,
    )
    return {
        "decision": decision,
        "fp5": fp5,
        "readable_versions": readable,
        "scorable_floor": SCORABLE_FLOOR,
        "per_version": per_version,
        "complete_triples": len(complete),
        "complete_clusters": complete_clusters,
        "target_read_share": {
            name: interval_block(values) for name, values in share_pairs.items()
        },
        "abandonment_step": {name: interval_block(values) for name, values in step_pairs.items()},
        "first_read_on_target": {
            name: interval_block(values) for name, values in first_pairs.items()
        },
        "positional": feed_controls.slot_share_table(sessions)["slots"],
    }


# ------------------------------------------------------- v2: the book is the unit (§222)

#: **v2's design, registered in `cost-that-bites/PREREG-v2.md` and separate from v1's above.**
#: v1's constants and `registration_digest()` are untouched so its committed numbers stay
#: reproducible (§120.5); everything here is additive and carries its own digest.
VERSION_V2 = "cost-that-bites.v2"

#: The slot the target occupies in every v2 session. Chosen because the reader *reads* there —
#: 0.622 of its reads against 0.190, 0.105 and 0.082 (§222), a property of the reader measured
#: from every session's slot-share vector and independent of any version contrast. That the
#: effect was also largest there is recorded and is **not** the reason.
TARGET_ROTATION_V2 = 0

#: Replicates per version per book. Three is the knee: 69% of a paired difference's variance is
#: within-cell noise (intact-versus-sham, the same book undamaged twice, sd 0.345 against the
#: difference's 0.414), so replicates divide the dominant term until the between-book component
#: at 0.230 takes over, and a fourth buys 0.023 of power at a one-read shift.
REPLICATES_V2 = 3

#: Floor on the reader's slot-A share for the design's premise to hold. Below it the reader is
#: no longer attending to the position the target occupies and the arm is UNREADABLE whatever
#: the intervals say — the assumption checked in the same pass that uses it.
CAPACITY_FLOOR_V2 = 0.40

#: Books needed with a complete scorable set before any interval is computed.
MIN_BOOKS_V2 = 10

#: The shuffle seed indices each book's three shuffled replicates use. **v3's replication moves
#: only this**: v2 bought 0/1/2, v3 buys 3/4/5, and nothing else about the design changes
#: (`PREREG-v3-replication.md`). It is a parameter rather than a constant because the whole
#: point of the replication is to redraw the permutation luck v2's own seed spread — 0.1804
#: against an effect of 0.1640 — says is the size of the effect.
SHUFFLE_SEED_START_V2 = 0
SHUFFLE_SEED_START_V3 = 3

#: Bought calls after which the run stops between sessions. No dollar ceiling: the operator's
#: direction of 2026-09-04 is that this is subscription quota. 180 sessions ran at 8.1 calls a
#: session in v1, so the plan is about 1,460 and this covers a skim-heavy run with margin.
CALL_CEILING_V2 = 2_200

PRE_REGISTRATION_V2: dict[str, Any] = {
    "version": VERSION_V2,
    "amends": VERSION,
    "instrument": feed_core.FCR_VERSION,
    "instrument_registration_digest": feed_core.registration_digest(),
    "versions": list(VERSIONS),
    "shuffle_salt": SHUFFLE_SALT,
    "shuffle_seeds_per_book": REPLICATES_V2,
    "sham": "ablate.rewhitespace",
    "sham_strength": SHAM_STRENGTH,
    "reader_model": READER_MODEL,
    "transport": TRANSPORT,
    "target_rotation": TARGET_ROTATION_V2,
    "replicates": REPLICATES_V2,
    "alpha": ALPHA,
    "scorable_floor": SCORABLE_FLOOR,
    "capacity_floor": CAPACITY_FLOOR_V2,
    "min_books": MIN_BOOKS_V2,
    "call_ceiling": CALL_CEILING_V2,
    "primary": "target_read_share, averaged within book over replicates: intact - shuffled",
    "sham_reading": "sham - shuffled, per sham and never pooled",
    "cluster": "the book",
    "declared_target_shift": 0.1875,
    "underpowered_at": 0.125,
    "decision": {
        "UNREADABLE": "fp5 not PASS, a version under the scorable floor, the slot-A share "
                      "no longer the largest or under the capacity floor, or fewer than "
                      "MIN_BOOKS_V2 books with a complete scorable set",
        "MOVES_WITH_ORDER": "both intervals strictly above zero, for a book in the position "
                            "this reader attends to",
        "MOVES_WITH_EDITEDNESS": "intact - shuffled above zero and sham - shuffled not",
        "NULL": "intact - shuffled contains zero: no movement at the declared 0.1875 shift; "
                "not a null at 0.125, which this design cannot reach",
        "INVERTED": "intact - shuffled strictly below zero",
    },
}


def registration_digest_v2() -> str:
    material = json.dumps(PRE_REGISTRATION_V2, sort_keys=True, ensure_ascii=False)
    return sha256(material.encode("utf-8")).hexdigest()[:16]


def seeds_for(text: str, *, start: int, count: int = REPLICATES_V2) -> tuple[int, ...]:
    """The `count` lowest seed indices at or above `start` whose shuffle can carry a session.

    **A rule and not a choice, declared before spend.** A shuffle reorders paragraphs, and
    `bcr.chunks` closes a chunk once it passes the word target, so a permutation can leave a
    book one chunk short of the floor a feed member needs — measured across seeds 0 to 9 over
    the twenty books, exactly one pair does: `fitness-08` at seed 4, which chunks to 10 against
    a floor of 11. Picking a seed triple *because* it happens to clear would be choosing the
    nuisance parameter to fit; skipping a seed the instrument cannot carry, by a rule that reads
    only chunk counts and never a reader's behaviour, is the same species as the reassembly
    instrument repairing an answer that omits a label. Deviations are flagged in the result.

    v2's `(0, 1, 2)` satisfies this rule at `start=0`, so the rule describes what v2 did rather
    than changing it.
    """
    chosen: list[int] = []
    index = start
    while len(chosen) < count:
        if index > start + 50:
            raise ValueError(f"no {count} usable shuffle seeds at or above {start}")
        if len(bcr.chunks(book_shuffle(text, index=index))) >= feed_core.MIN_CHUNKS_FEED:
            chosen.append(index)
        index += 1
    return tuple(chosen)


def versions_v2(
    text: str, *, seeds: tuple[int, ...] | None = None
) -> dict[str, list[str]]:
    """Per version, the text each replicate is shown.

    `intact` and `sham` repeat one text — the replicates are independent draws from the reader,
    separated by the sample index `feed_session` folds the replicate into. `shuffled` carries a
    **different shuffle per replicate**, so the estimate is about disorder rather than about one
    permutation, which is what v1's single seed per book confounded.
    """
    chosen = seeds_for(text, start=SHUFFLE_SEED_START_V2) if seeds is None else seeds
    return {
        "intact": [text] * REPLICATES_V2,
        "shuffled": [book_shuffle(text, index=index) for index in chosen],
        "sham": [sham(text)] * REPLICATES_V2,
    }


def plan_v2(
    texts: Sequence[tuple[str, str]],
    *,
    books: int | None = None,
    seed_start: int = SHUFFLE_SEED_START_V2,
    tag: str = "ctb2",
) -> list[Cell]:
    """Every book's three versions at three replicates, the target always in slot A."""
    if len(texts) < feed_core.FEED_SIZE:
        raise ValueError(
            f"{len(texts)} book(s) on the pool; a feed of {feed_core.FEED_SIZE} needs "
            f"{feed_core.FEED_SIZE}"
        )
    count = len(texts) if books is None else min(books, len(texts))
    cells: list[Cell] = []
    for index in range(count):
        target_name, target_text = texts[index]
        others = [texts[(index + offset) % len(texts)] for offset in range(1, feed_core.FEED_SIZE)]
        chosen = seeds_for(target_text, start=seed_start)
        for version, per_replicate in versions_v2(target_text, seeds=chosen).items():
            for replicate, target in enumerate(per_replicate):
                spec = feed_core.FeedSpec(
                    feed_id=f"{tag}-{index:02d}-{version}-r{replicate}",
                    arm=version,
                    target=target,
                    others=tuple(text for _, text in others),
                    note=(
                        f"target={target_name} ({version}, replicate {replicate}) "
                        f"others={','.join(name for name, _ in others)}"
                    ),
                )
                cells.append(
                    Cell(
                        feed_index=index,
                        target_name=target_name,
                        version=version,
                        rotation=TARGET_ROTATION_V2,
                        spec=spec,
                        chunk_counts=tuple(len(bcr.chunks(text)) for text in spec.texts()),
                        replicate=replicate,
                    )
                )
    return cells


def by_book(rows: Sequence[Row]) -> dict[str, dict[str, float]]:
    """Per book, each version's mean target read share over its scorable replicates.

    A book contributes only when all three versions have at least one scorable session; a book
    missing a version is dropped whole rather than compared against a partial sibling.
    """
    collected: dict[str, dict[str, list[float]]] = {}
    for row in rows:
        if row.session.scorable:
            collected.setdefault(row.book_key, {}).setdefault(row.version, []).append(
                row.session.target_read_share
            )
    return {
        book: {version: statistics.fmean(shares) for version, shares in versions.items()}
        for book, versions in collected.items()
        if all(version in versions for version in VERSIONS)
    }


def paired_v2(means: dict[str, dict[str, float]]) -> dict[str, list[tuple[str, float]]]:
    """The three paired differences, one observation per book, the book as the cluster."""
    out: dict[str, list[tuple[str, float]]] = {
        "intact_minus_shuffled": [],
        "intact_minus_sham": [],
        "sham_minus_shuffled": [],
    }
    for book in sorted(means):
        row = means[book]
        out["intact_minus_shuffled"].append((book, row["intact"] - row["shuffled"]))
        out["intact_minus_sham"].append((book, row["intact"] - row["sham"]))
        out["sham_minus_shuffled"].append((book, row["sham"] - row["shuffled"]))
    return out


def capacity_v2(sessions: Sequence[feed_core.FeedSession]) -> dict[str, Any]:
    """Precondition 3: is the reader still reading the slot the target sits in?"""
    usable = [session for session in sessions if session.scorable]
    if not usable:
        return {"verdict": "UNREADABLE", "why": "no scorable session", "shares": {}}
    shares = {
        slot: statistics.fmean(session.read_share_of(slot) for session in usable)
        for slot in feed_core.SLOTS
    }
    target_slot = feed_core.SLOTS[TARGET_ROTATION_V2]
    held = shares[target_slot] >= CAPACITY_FLOOR_V2 and shares[target_slot] == max(shares.values())
    return {
        "verdict": "PASS" if held else "FAIL",
        "shares": shares,
        "target_slot": target_slot,
        "floor": CAPACITY_FLOOR_V2,
        "why": (
            ""
            if held
            else "the reader no longer attends to the slot the target occupies; the design's "
            "premise has gone and no interval from it is read"
        ),
    }


def _shuffle_seed_spread(rows: Sequence[Row]) -> dict[str, float]:
    """Per book, the spread of its three shuffles' shares: disorder, or one permutation?"""
    spread: dict[str, float] = {}
    for book in sorted({row.book_key for row in rows}):
        shares = [
            row.session.target_read_share
            for row in rows
            if row.book_key == book and row.version == "shuffled" and row.session.scorable
        ]
        if len(shares) > 1:
            spread[book] = statistics.pstdev(shares)
    return spread


def reading_v2(rows: Sequence[Row]) -> dict[str, Any]:
    """v2's reading: the preconditions in order, then one decision over the book means."""
    sessions = [row.session for row in rows]
    per_version: dict[str, Any] = {}
    for version in VERSIONS:
        mine = [row.session for row in rows if row.version == version]
        usable = [session for session in mine if session.scorable]
        per_version[version] = {
            "sessions": len(mine),
            "scorable": len(usable),
            "scorable_share": (len(usable) / len(mine)) if mine else None,
            "exit_notes": dict(Counter(s.exit_note for s in mine if not s.scorable)),
            "mean_target_read_share": (
                statistics.fmean(s.target_read_share for s in usable) if usable else None
            ),
            "mean_abandonment_step": (
                statistics.fmean(s.abandonment_step for s in usable) if usable else None
            ),
            "mean_skim_rate": statistics.fmean(s.skim_rate for s in usable) if usable else None,
            "target_never_read": sum(1 for s in usable if s.abandonment_step < 0),
        }
    readable = all(
        block["sessions"] > 0
        and block["scorable_share"] is not None
        and block["scorable_share"] >= SCORABLE_FLOOR
        for block in per_version.values()
    )
    fp5 = feed_controls.fp5_non_degenerate(sessions)
    capacity = capacity_v2(sessions)
    means = by_book(rows)
    pairs = paired_v2(means)
    shuffle_block = interval_block(pairs["intact_minus_shuffled"])
    order_block = interval_block(pairs["sham_minus_shuffled"])
    if (
        str(fp5["verdict"]) != "PASS"
        or not readable
        or capacity["verdict"] != "PASS"
        or len(means) < MIN_BOOKS_V2
    ):
        decision = "UNREADABLE"
    else:
        decision = decide(
            fp5_verdict="PASS",
            readable_versions=True,
            complete_clusters=len(means),
            shuffle=shuffle_block,
            order=order_block,
        )
    return {
        "decision": decision,
        "fp5": fp5,
        "capacity": capacity,
        "readable_versions": readable,
        "scorable_floor": SCORABLE_FLOOR,
        "per_version": per_version,
        "books_complete": len(means),
        "min_books": MIN_BOOKS_V2,
        "book_means": means,
        "target_read_share": {name: interval_block(values) for name, values in pairs.items()},
        "shuffle_seed_spread": _shuffle_seed_spread(rows),
        "declared_target_shift": PRE_REGISTRATION_V2["declared_target_shift"],
        "underpowered_at": PRE_REGISTRATION_V2["underpowered_at"],
    }


# ------------------------------------------------------------------------- attainability


def _simulated_pair(
    rng: random.Random, *, downweight: float, content_driven: bool
) -> tuple[float, float]:
    """One (intact share, manipulated share) pair under a patterned reader.

    A content-driven reader draws one allocation over the four slots (Dirichlet(1,1,1,1)) and
    reads eight times on it; the manipulated session keeps the same allocation with the
    target's weight scaled by `1 - downweight` and renormalised, which is the smallest model of
    "this book got less interesting". A fixed-pattern reader returns the same share both ways:
    it has no free minute to move, which is why `fp5` is read before anything else.
    """
    reads = feed_controls.READS_PER_SESSION
    if not content_driven:
        share = rng.choice([0.0, 0.25, 0.5, 1.0])
        return share, share
    raw = [rng.gammavariate(1.0, 1.0) for _ in range(feed_core.FEED_SIZE)]
    total = sum(raw)
    weights = [value / total for value in raw]

    def draw(target_weight: float) -> float:
        rest = 1.0 - weights[0]
        scaled = [target_weight] + [
            value * ((1.0 - target_weight) / rest) if rest > 0 else 0.0 for value in weights[1:]
        ]
        hits = 0
        for _ in range(reads):
            u = rng.random()
            cumulative = 0.0
            for index, weight in enumerate(scaled):
                cumulative += weight
                if u < cumulative:
                    hits += 1 if index == 0 else 0
                    break
        return hits / reads

    intact = draw(weights[0])
    manipulated = draw(weights[0] * (1.0 - downweight))
    return intact, manipulated


def attainability(*, seed: int = ATTAINABILITY_SEED, trials: int = 200) -> dict[str, Any]:
    """How often the registered interval excludes zero, at the real n, for named shifts.

    Two reader worlds — every session content-driven, and `feed_controls`' mixture with six
    fixed patterns in eight sessions — at the arm's 20 feeds x 4 rotations and the screen's
    2 x 4. `downweight` 0.0 is the null (the rate printed there is the false-positive rate);
    the observed mean paired difference is printed beside every rate so a downweight can be
    read in share units — 0.125 is one read in eight.
    """
    downweights = (0.0, 0.25, 0.5, 0.75, 1.0)
    shapes = {"arm": 20, "screen": SCREEN_FEEDS}
    worlds = {"content_driven": 1.0, "mixture": 2.0 / len(feed_controls.PATTERNS)}
    table: dict[str, Any] = {}
    for world, content_share in worlds.items():
        table[world] = {}
        for shape, feeds in shapes.items():
            rows_out: dict[str, Any] = {}
            for downweight in downweights:
                excluded = 0
                means: list[float] = []
                for trial in range(trials):
                    rng = random.Random(f"{seed}:{world}:{shape}:{downweight}:{trial}")
                    values: list[tuple[str, float]] = []
                    for feed in range(feeds):
                        for _rotation in range(feed_core.FEED_SIZE):
                            content = rng.random() < content_share
                            intact, manipulated = _simulated_pair(
                                rng, downweight=downweight, content_driven=content
                            )
                            values.append((f"{feed:02d}", intact - manipulated))
                    means.append(statistics.fmean(value for _, value in values))
                    interval = bcr.cluster_interval(values, alpha=ALPHA)
                    if interval is not None and interval.low > 0.0:
                        excluded += 1
                rows_out[str(downweight)] = {
                    "interval_above_zero": excluded / trials,
                    "mean_paired_difference": statistics.fmean(means),
                }
            table[world][shape] = rows_out
    return {
        "seed": seed,
        "trials": trials,
        "alpha": ALPHA,
        "reads_per_session": feed_controls.READS_PER_SESSION,
        "shapes": {name: feeds * feed_core.FEED_SIZE for name, feeds in shapes.items()},
        "table": table,
        "reading": (
            "the downweight 0.0 row is the false-positive rate of the registered reading; a "
            "shift is attainable at the arm's n where its row clears the null's by a wide "
            "margin; the screen's rows show why the screen reads fp5 and the price and "
            "never the effect"
        ),
    }


# ------------------------------------------------------------------------------ selftest


class _ScriptedElicitor:
    """A scripted `ask_raw`: one record per call from a rule, with a priced usage block."""

    def __init__(self, rule: Callable[[dict[str, Any]], str], *, usd_per_call: float) -> None:
        self._rule = rule
        self._usd = usd_per_call
        # **The double is driven by the same pool as the real elicitor** (§227), so it needs
        # the same lock: `run_cells` asks a worker to price the ceiling while its siblings
        # are recording calls, and an unguarded dict raised out of `future.result()`.
        self._lock = threading.Lock()
        self._records: dict[str, dict[str, Any]] = {}
        self.api_calls = 0
        self.replayed = 0
        self.transport_failures = 0
        self.failure_reasons: Counter[str] = Counter()

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
        del system, turns, schema, max_tokens, model
        key = f"{tag['feed']}:{tag['rotation']}:{sample}"
        record = {
            "key": key,
            "text": self._rule(tag),
            "refused": False,
            "usage": {"equivalent_usd": self._usd},
        }
        with self._lock:
            self._records[key] = record
            self.api_calls += 1
        return record

    def spend(self) -> dict[str, int | float]:
        with self._lock:
            records = list(self._records.values())
        total = sum(record["usage"]["equivalent_usd"] for record in records)
        return {"equivalent_usd": round(total, 6)}


def _member_text(marker: str, paragraphs: int = feed_core.MIN_CHUNKS_FEED + 2) -> str:
    """A synthetic member: one paragraph per chunk, each just over the chunk target.

    Written as capitalised sentences, because the whitespace sham re-flows the space after a
    sentence end only before a capital — a synthetic text of lowercase tokens would leave the
    sham byte-identical to the original and `faults` would rightly refuse the plan.
    """
    stem = marker.capitalize()
    return "\n\n".join(
        " ".join(
            f"{stem}p{paragraph}w{word}." if word % 8 == 7 else f"{stem}p{paragraph}w{word}"
            for word in range(feed_core.CHUNK_WORDS + 5)
        )
        for paragraph in range(paragraphs)
    )


def _reads_target_by_version(tag: dict[str, Any]) -> str:
    """A scripted reader that reads the intact target, skims the shuffled one, reads the sham."""
    feed_id = str(tag["feed"])
    rotation = int(tag["rotation"])
    target_slot = feed_core.SLOTS[rotation % feed_core.FEED_SIZE]
    other = feed_core.SLOTS[(rotation + 1) % feed_core.FEED_SIZE]
    if feed_id.endswith("shuffled"):
        return json.dumps({"action": "read", "book": other})
    return json.dumps({"action": "read", "book": target_slot})


def selftest() -> int:
    """The free leg: every registered definition on inputs whose answers are hand-stated."""
    failures: list[str] = []
    text = _member_text("selftest")
    shuffled = book_shuffle(text)
    if sorted(ablate.paragraphs(shuffled)) != sorted(ablate.paragraphs(text)):
        failures.append("the shuffle changed the multiset of paragraphs")
    if ablate.paragraphs(shuffled) == ablate.paragraphs(text):
        failures.append("the shuffle left the order intact")
    if book_shuffle(text) != shuffled:
        failures.append("the shuffle is not deterministic in the text")
    if len(shuffled.split()) != len(text.split()):
        failures.append("the shuffle changed the word count")
    if sham(text).split() != text.split():
        failures.append("the sham moved a word")
    pool = [(f"book-{index}", _member_text(f"b{index}")) for index in range(4)]
    cells = plan(pool)
    counts = planned_counts(cells)
    if counts != {"feeds": 4, "sessions": 48, "max_calls": 48 * feed_core.MAX_STEPS}:
        failures.append(f"the plan counted wrong: {counts}")
    if faults(cells):
        failures.append(f"a synthetic full-length feed faulted: {faults(cells)}")
    if planned_counts(plan(pool, feeds=SCREEN_FEEDS))["sessions"] != SCREEN_FEEDS * 3 * 4:
        failures.append("the screen cap did not produce three versions x four rotations per feed")
    if registration_digest() != registration_digest():
        failures.append("the registration digest is not stable")

    scripted = _ScriptedElicitor(_reads_target_by_version, usd_per_call=0.01)
    rows, ledger = run_cells(
        scripted, cells, model="selftest", ceiling_usd=100.0, workers=2, log=lambda _: None
    )
    if len(rows) != len(cells) or ledger["stopped_at_ceiling"]:
        failures.append("a run under the ceiling did not buy every cell")
    read = reading(rows)
    shuffle = read["target_read_share"]["intact_minus_shuffled"]
    order = read["target_read_share"]["sham_minus_shuffled"]
    if read["complete_triples"] != 16 or read["complete_clusters"] != 4:
        failures.append(f"paired triples miscounted: {read['complete_triples']}")
    if not (shuffle.get("above_zero") and order.get("above_zero")):
        failures.append("a reader scripted to abandon the shuffled target did not read as moving")
    if read["decision"] != "MOVES_WITH_ORDER":
        failures.append(f"the scripted mover decided {read['decision']}")

    # A reader that follows the target through the rotations and reads it every time: its
    # slot shares move (fp5 passes) and every paired difference is exactly zero, which is
    # the registered null and nothing else.
    follower = _ScriptedElicitor(
        lambda tag: json.dumps(
            {"action": "read", "book": feed_core.SLOTS[int(tag["rotation"]) % feed_core.FEED_SIZE]}
        ),
        usd_per_call=0.01,
    )
    rows_follow, _ = run_cells(
        follower, cells, model="selftest", ceiling_usd=100.0, workers=2, log=lambda _: None
    )
    read_follow = reading(rows_follow)
    if read_follow["fp5"]["verdict"] != "PASS" or read_follow["decision"] != "NULL":
        failures.append(
            "a reader that reads the target whatever its version must read NULL, got "
            f"fp5={read_follow['fp5']['verdict']} decision={read_follow['decision']}"
        )
    # A reader that reads slot A whatever sits in it is a fixed pattern wearing a budget:
    # fp5 fails and nothing downstream is read.
    fixed = _ScriptedElicitor(
        lambda tag: json.dumps({"action": "read", "book": "A"}), usd_per_call=0.01
    )
    rows_fixed, _ = run_cells(
        fixed, cells, model="selftest", ceiling_usd=100.0, workers=2, log=lambda _: None
    )
    read_fixed = reading(rows_fixed)
    if read_fixed["fp5"]["verdict"] != "FAIL" or read_fixed["decision"] != "UNREADABLE":
        failures.append(
            "a reader that always reads slot A must fail fp5 and read UNREADABLE, got "
            f"fp5={read_fixed['fp5']['verdict']} decision={read_fixed['decision']}"
        )

    capped = _ScriptedElicitor(_reads_target_by_version, usd_per_call=0.05)
    rows_capped, ledger_capped = run_cells(
        capped, cells, model="selftest", ceiling_usd=0.5, workers=1, log=lambda _: None
    )
    if not ledger_capped["stopped_at_ceiling"] or len(rows_capped) >= len(cells):
        failures.append("a ceiling below the plan did not stop the run between sessions")
    if ledger_capped["sessions_run"] != len(rows_capped):
        failures.append("the ledger's session count disagrees with the rows")

    verdicts = {
        (True, True): "MOVES_WITH_ORDER",
        (True, False): "MOVES_WITH_EDITEDNESS",
        (False, False): "NULL",
    }
    for (shuffle_up, order_up), expected in verdicts.items():
        got = decide(
            fp5_verdict="PASS",
            readable_versions=True,
            complete_clusters=20,
            shuffle={"above_zero": shuffle_up, "below_zero": False},
            order={"above_zero": order_up, "below_zero": False},
        )
        if got != expected:
            failures.append(f"decision table: {(shuffle_up, order_up)} read {got}")
    inverted = decide(
        fp5_verdict="PASS",
        readable_versions=True,
        complete_clusters=20,
        shuffle={"above_zero": False, "below_zero": True},
        order={"above_zero": False, "below_zero": False},
    )
    if inverted != "INVERTED":
        failures.append(f"decision table: an interval below zero read {inverted}")

    for line in failures:
        print(f"FAIL {line}", file=sys.stderr)
    print("selftest: " + ("FAILED" if failures else "passed"), file=sys.stderr)
    return 1 if failures else 0


# ----------------------------------------------------------------------------- the CLI


def write_result(result: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")


def _rows_json(rows: Sequence[Row]) -> list[dict[str, Any]]:
    return [
        {
            "feed_index": row.feed_index,
            "target_name": row.target_name,
            "version": row.version,
            "rotation": row.rotation,
            "pair_key": row.pair_key,
            "session": asdict(row.session),
        }
        for row in rows
    ]


def volume_text(book_dir: Path) -> tuple[str, int, int]:
    """One drafted book's chapters as a single text, in reading order: (text, chapters, words)."""
    chapters = sorted((book_dir / "chapters").glob("Chapter*.txt"), key=lambda p: p.name)
    if not chapters:
        raise ValueError(f"no chapters under {book_dir / 'chapters'}")
    text = "\n\n".join(path.read_text(encoding="utf-8").strip() for path in chapters)
    return text, len(chapters), len(text.split())


def _run_volume_screen(args: argparse.Namespace) -> int:
    """Three sessions on one drafted book: does it carry, does the reader answer, what does it cost?

    `PREREG-volume-screen.md` owns the design and states, before any spend, that **no effect is
    read under any outcome**: at one book `bcr.cluster_interval` returns None, and the forty
    book-level contrasts are a fitness book's reference class rather than a shelf book's. The
    three target read shares are recorded because they are what the sessions produce, and this
    function computes no difference between them.
    """
    book_dir = Path(args.volume_screen)
    text, chapters, words = volume_text(book_dir)
    pool = feed_substrate.fitness_texts(Path(args.fitness_dir))
    competitors = pool[: feed_core.FEED_SIZE - 1]
    # **The intact book is checked before a shuffle is even sought.** `seeds_for` searches for a
    # permutation that clears the floor and raises when none does — which is what a book far
    # under the floor produces, and a raise is the wrong shape for the answer this screen
    # exists to give. A book that cannot carry a session intact is TOO_SHORT, reported with
    # its count, before anything is shuffled or bought.
    held_intact = len(bcr.chunks(text))
    if held_intact < feed_core.MIN_CHUNKS_FEED:
        print(f"volume screen: {book_dir.name} — {chapters} chapter(s), {words} words")
        print(f"  intact    {held_intact:2d} chunk(s) against a floor of "
              f"{feed_core.MIN_CHUNKS_FEED}  FAULT")
        result = {
            "study": "cost-that-bites.volume-screen",
            "book": book_dir.name,
            "chapters": chapters,
            "words": words,
            "chunks": {"intact": held_intact},
            "floor": feed_core.MIN_CHUNKS_FEED,
            "reading": "TOO_SHORT",
            "faults": {
                "intact": (
                    f"the book holds {held_intact} chunk(s) intact; a feed member needs "
                    f"{feed_core.MIN_CHUNKS_FEED}, so no shuffle of it can clear either"
                )
            },
        }
        write_result(result, ARM_DIR / f"results-volume-screen-{book_dir.name}.json")
        print("TOO_SHORT: nothing bought", file=sys.stderr)
        return 0
    seeds = seeds_for(text, start=SHUFFLE_SEED_START_V2, count=1)
    versions = {
        "intact": text,
        "shuffled": book_shuffle(text, index=seeds[0]),
        "sham": sham(text),
    }
    print(f"volume screen: {book_dir.name} — {chapters} chapter(s), {words} words")
    faults_found: dict[str, str] = {}
    cells: list[Cell] = []
    for version, target in versions.items():
        spec = feed_core.FeedSpec(
            feed_id=f"vol-{book_dir.name[:20]}-{version}",
            arm=version,
            target=target,
            others=tuple(t for _, t in competitors),
            note=f"target={book_dir.name} ({version}) others={','.join(n for n, _ in competitors)}",
        )
        held = len(bcr.chunks(target))
        fault = spec.fault()
        print(f"  {version:9s} {held:2d} chunk(s) against a floor of {feed_core.MIN_CHUNKS_FEED}"
              f"  {'ok' if fault is None else 'FAULT'}")
        if fault is not None:
            faults_found[version] = fault
        cells.append(
            Cell(
                feed_index=0,
                target_name=book_dir.name,
                version=version,
                rotation=TARGET_ROTATION_V2,
                spec=spec,
                chunk_counts=tuple(len(bcr.chunks(t)) for t in spec.texts()),
            )
        )
    if faults_found:
        # A fault is a **result of this screen**, not an error: it says three chapters is not
        # enough for this instrument. Recorded and reported without buying a call.
        result = {
            "study": "cost-that-bites.volume-screen",
            "book": book_dir.name,
            "chapters": chapters,
            "words": words,
            "chunks": {v: len(bcr.chunks(t)) for v, t in versions.items()},
            "floor": feed_core.MIN_CHUNKS_FEED,
            "reading": "TOO_SHORT",
            "faults": faults_found,
        }
        write_result(result, ARM_DIR / f"results-volume-screen-{book_dir.name}.json")
        print(json.dumps(result["faults"], indent=2))
        print("TOO_SHORT: nothing bought", file=sys.stderr)
        return 0
    if not args.yes:
        print("pass --yes to spend (three sessions)", file=sys.stderr)
        return 1

    from elicit import Elicitor

    cache = ARM_DIR / f"raw-volume-screen-{book_dir.name}.jsonl"
    with Elicitor(cache, model=args.model, spot_model=None, transport=TRANSPORT) as elicitor:
        rows, ledger = run_cells(
            elicitor, cells, model=args.model, ceiling_usd=float("inf"), workers=1
        )
    scorable = [row for row in rows if row.session.scorable]
    exits = dict(Counter(row.session.exit_note for row in rows if not row.session.scorable))
    reading = "CARRIES" if len(scorable) == len(cells) else "DOES_NOT_CARRY"
    result = {
        "study": "cost-that-bites.volume-screen",
        "book": book_dir.name,
        "chapters": chapters,
        "words": words,
        "chunks": {v: len(bcr.chunks(t)) for v, t in versions.items()},
        "floor": feed_core.MIN_CHUNKS_FEED,
        "reading": reading,
        "exit_notes": exits,
        "sessions": len(rows),
        "scorable": len(scorable),
        "usd_per_session": (
            round(float(ledger["spend"]["equivalent_usd"]) / len(rows), 4) if rows else None
        ),
        "slot_shares": feed_controls.slot_share_table([r.session for r in rows])["slots"],
        # Recorded because they are what the sessions produce. **Not compared**: at one book
        # there is no interval and no reference class (PREREG-volume-screen.md §2).
        "target_read_share_per_version": {
            row.version: row.session.target_read_share for row in scorable
        },
        "no_effect_is_read": (
            "one book yields no interval (cluster_interval returns None below two clusters) and "
            "the forty fitness-book contrasts are not this book's reference class"
        ),
        "ledger": ledger,
        "rows": _rows_json(rows),
    }
    write_result(result, ARM_DIR / f"results-volume-screen-{book_dir.name}.json")
    print(f"{reading}: {len(scorable)}/{len(cells)} scorable, "
          f"${result['usd_per_session']} a session, exits {exits or 'none'}")
    return 0


def _run_v2(
    args: argparse.Namespace,
    *,
    seed_start: int = SHUFFLE_SEED_START_V2,
    tag: str = "ctb2",
    label: str = "arm-v2",
) -> int:
    """v2's run: the same runner and the same ledger, its own plan, reading and ceiling.

    The stop condition is a **call ceiling** rather than a dollar one (PREREG-v2), so the
    runner's dollar ceiling is set out of the way and the loop is bounded by
    `CALL_CEILING_V2` bought calls, read between sessions. `equivalent_usd` is still reported,
    because quota burn belongs on the record even when it is not the limit.
    """
    texts = feed_substrate.fitness_texts(Path(args.fitness_dir))
    cells = plan_v2(texts, books=args.books, seed_start=seed_start, tag=tag)
    used = {name: list(seeds_for(text, start=seed_start)) for name, text in texts[: args.books]}
    default = list(range(seed_start, seed_start + REPLICATES_V2))
    deviating = {name: got for name, got in used.items() if got != default}
    books = len({cell.feed_index for cell in cells})
    print(
        f"{label}: {books} book(s), {len(cells)} session(s), at most "
        f"{len(cells) * feed_core.MAX_STEPS} call(s) on {args.model} via {TRANSPORT}; "
        f"call ceiling {CALL_CEILING_V2}"
    )
    broken = faults(cells)
    if broken:
        for feed_id, fault in sorted(broken.items()):
            print(f"  {feed_id:24s} FAULT: {fault}", file=sys.stderr)
        print("nothing runs until the plan is fault-free", file=sys.stderr)
        return 1
    if not args.yes:
        print("pass --yes to spend", file=sys.stderr)
        return 1

    from elicit import Elicitor

    # v2 gets its own cache: its sessions are a different design and pooling them into v1's
    # raw records would make one file two experiments.
    default_cache = args.cache == str(ARM_DIR / "raw.jsonl")
    suffix = label.replace("arm-", "")
    cache = ARM_DIR / f"raw-{suffix}.jsonl" if default_cache else Path(args.cache)
    with Elicitor(cache, model=args.model, spot_model=None, transport=TRANSPORT) as elicitor:
        rows, ledger = run_cells(
            elicitor,
            cells,
            model=args.model,
            ceiling_usd=float("inf"),
            workers=args.workers,
            call_ceiling=CALL_CEILING_V2,
        )
    read = reading_v2(rows)
    result = {
        "study": f"{VERSION_V2}/{label}",
        "shuffle_seed_start": seed_start,
        "shuffle_seeds_per_book": used,
        "shuffle_seeds_deviating": deviating,
        "registration": PRE_REGISTRATION_V2,
        "registration_digest": registration_digest_v2(),
        "supersedes_nothing": (
            "v1's registration, digest and findings are untouched; this is a different design "
            "and no number crosses between them except the reader properties §222 measured"
        ),
        "model": args.model,
        "transport": TRANSPORT,
        "plan": {"books": books, "sessions": len(cells)},
        "ledger": ledger,
        "reading": read,
        "rows": _rows_json(rows),
        "warnings": (
            ["stopped at the call ceiling: the plan is not covered and the reading is partial"]
            if ledger["stopped_at_ceiling"]
            else []
        ),
    }
    out = Path(args.out) if args.out else ARM_DIR / f"results-{label}.json"
    write_result(result, out)
    headline = {
        key: read[key]
        for key in ("decision", "fp5", "capacity", "books_complete", "target_read_share")
    }
    print(json.dumps(headline, indent=2))
    print(f"ledger: {json.dumps(ledger)}")
    print(f"wrote {out}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true", help="free: prove the arithmetic")
    parser.add_argument("--attainability", action="store_true", help="free: the sizing table")
    parser.add_argument(
        "--trials",
        type=int,
        default=40,
        help="attainability trials per cell; the committed table names the count it ran",
    )
    parser.add_argument("--dry-run", action="store_true", help="build the plan; no call")
    parser.add_argument("--screen", action="store_true", help="paid: the first feeds only")
    parser.add_argument("--arm", action="store_true", help="paid: every feed")
    parser.add_argument(
        "--arm-v3",
        action="store_true",
        help="paid: the replication (PREREG-v3-replication.md) — v2's design entire with only "
        "the three shuffle seeds redrawn, so the permutation luck is a fresh draw",
    )
    parser.add_argument(
        "--volume-screen",
        default=None,
        metavar="BOOK_DIR",
        help="paid, three sessions: can a multi-chapter book of ours carry a session at all? "
        "(PREREG-volume-screen.md). Buys feasibility and price and never an effect",
    )
    parser.add_argument(
        "--arm-v2",
        action="store_true",
        help="paid: v2's design (PREREG-v2.md) — the target in slot A, the book as the unit, "
        "three replicates and three shuffle seeds per book, a call ceiling and no dollar cap",
    )
    parser.add_argument(
        "--dry-elicitor",
        action="store_true",
        help="free: the screen's plan through a real Elicitor in dry-run mode (synthetic "
        "answers, no call); exercises the transport plumbing and writes beside --out",
    )
    parser.add_argument("--model", default=READER_MODEL)
    parser.add_argument("--workers", type=int, default=WORKERS)
    parser.add_argument("--fitness-dir", default=str(FITNESS_DIR))
    parser.add_argument(
        "--books",
        type=int,
        default=None,
        help="arm-v2: limit the plan to its first N books; the result records the count",
    )
    parser.add_argument("--cache", default=str(ARM_DIR / "raw.jsonl"))
    parser.add_argument("--out", default=None)
    parser.add_argument(
        "--ceiling-usd",
        type=float,
        default=None,
        help="lower the registered ceiling for this run; a higher one refuses",
    )
    parser.add_argument("--yes", action="store_true", help="consent to spend")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.attainability:
        table = attainability(trials=args.trials)
        write_result(table, ARM_DIR / "attainability.json")
        for world, shapes in table["table"].items():
            for shape, rows_out in shapes.items():
                print(f"{world} / {shape} ({table['shapes'][shape]} paired sessions)")
                for downweight, block in rows_out.items():
                    print(
                        f"  downweight {downweight:>4}: interval above zero "
                        f"{block['interval_above_zero']:.3f}, mean paired difference "
                        f"{block['mean_paired_difference']:+.3f}"
                    )
        print(f"wrote {ARM_DIR / 'attainability.json'}")
        return 0
    if not (
        args.dry_run
        or args.screen
        or args.arm
        or args.dry_elicitor
        or args.arm_v2
        or args.arm_v3
        or args.volume_screen
    ):
        parser.error(
            "pass one of --selftest, --attainability, --dry-run, --dry-elicitor, --screen, "
            "--arm, --arm-v2, --arm-v3"
        )
    if sum((bool(args.screen), bool(args.arm), bool(args.arm_v2), bool(args.arm_v3))) > 1:
        parser.error("--screen, --arm, --arm-v2 and --arm-v3 are separate runs; pass one")
    if args.arm_v2:
        return _run_v2(args)
    if args.volume_screen:
        return _run_volume_screen(args)
    if args.arm_v3:
        # The replication: v2's design entire, only the shuffle seeds redrawn
        # (`PREREG-v3-replication.md`).
        return _run_v2(
            args, seed_start=SHUFFLE_SEED_START_V3, tag="ctb3", label="arm-v3"
        )
    screen_sized = args.screen or args.dry_elicitor

    texts = feed_substrate.fitness_texts(Path(args.fitness_dir))
    cells = plan(texts, feeds=SCREEN_FEEDS if screen_sized else None)
    counts = planned_counts(cells)
    kind = "screen" if screen_sized else "arm"
    registered_ceiling = CEILING_SCREEN_USD if screen_sized else CEILING_ARM_USD
    ceiling = registered_ceiling if args.ceiling_usd is None else args.ceiling_usd
    if ceiling > registered_ceiling:
        parser.error(
            f"--ceiling-usd {ceiling} is above the registered {kind} ceiling {registered_ceiling}"
        )
    print(
        f"{kind}: {counts['feeds']} feed(s), {counts['sessions']} session(s), at most "
        f"{counts['max_calls']} call(s) on {args.model} via {TRANSPORT}; ceiling ${ceiling:.2f}"
    )
    broken = faults(cells)
    seen: set[str] = set()
    for cell in cells:
        if cell.spec.feed_id in seen:
            continue
        seen.add(cell.spec.feed_id)
        fault = broken.get(cell.spec.feed_id)
        status = "ok" if fault is None else f"FAULT: {fault}"
        print(f"  {cell.spec.feed_id:18s} [{status}] chunks={cell.chunk_counts} {cell.spec.note}")
    if broken:
        print(
            f"{len(broken)} feed(s) fault; nothing runs until the plan is fault-free",
            file=sys.stderr,
        )
        return 1
    if args.dry_run:
        print("dry run; nothing bought")
        return 0
    if args.dry_elicitor:
        # A real Elicitor with synthetic answers: the params, the digest keys, the pool and
        # the result writer all run; the answers are not actions, so every session ends
        # `invalid_action` and the reading is UNREADABLE by construction. Nothing is bought
        # and nothing lands in the arm's cache.
        import tempfile

        from elicit import Elicitor

        scratch = Path(args.out) if args.out else Path(tempfile.gettempdir())
        scratch.mkdir(parents=True, exist_ok=True)
        with Elicitor(
            scratch / "cost-that-bites-dry.jsonl",
            model=args.model,
            spot_model=None,
            transport=TRANSPORT,
            dry_run=True,
        ) as elicitor:
            rows, ledger = run_cells(
                elicitor, cells, model=args.model, ceiling_usd=ceiling, workers=args.workers
            )
        read = reading(rows)
        write_result(
            {"study": f"{VERSION}/dry-elicitor", "ledger": ledger, "reading": read,
             "rows": _rows_json(rows)},
            scratch / "cost-that-bites-dry.json",
        )
        print(f"dry elicitor: {ledger['sessions_run']} session(s), decision {read['decision']}")
        print(f"wrote {scratch / 'cost-that-bites-dry.json'}; nothing bought")
        return 0
    if counts["max_calls"] > CALL_GUARD and not args.yes:
        print(f"{counts['max_calls']} worst-case calls is above the {CALL_GUARD} guard; pass --yes")
        return 1
    if not args.yes:
        print("pass --yes to spend, or --dry-run to see the plan", file=sys.stderr)
        return 1

    from elicit import Elicitor  # imported here so the free legs never touch it

    cache = Path(args.cache)
    with Elicitor(cache, model=args.model, spot_model=None, transport=TRANSPORT) as elicitor:
        rows, ledger = run_cells(
            elicitor, cells, model=args.model, ceiling_usd=ceiling, workers=args.workers
        )
    read = reading(rows)
    result: dict[str, Any] = {
        "study": f"{VERSION}/{kind}",
        "registration": PRE_REGISTRATION,
        "registration_digest": registration_digest(),
        "model": args.model,
        "transport": TRANSPORT,
        "plan": counts,
        "ledger": ledger,
        "reading": read,
        "rows": _rows_json(rows),
        "warnings": (
            ["stopped at the ceiling: the plan is not covered and the reading is partial"]
            if ledger["stopped_at_ceiling"]
            else []
        ),
    }
    out = Path(args.out) if args.out else ARM_DIR / f"results-{kind}.json"
    write_result(result, out)
    headline = {key: read[key] for key in ("decision", "fp5", "per_version", "target_read_share")}
    print(json.dumps(headline, indent=2))
    print(f"ledger: {json.dumps(ledger)}")
    print(f"wrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
