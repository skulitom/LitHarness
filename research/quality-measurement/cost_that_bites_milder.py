"""A cost that bites, milder (arm `milder-v4`): does the costed reader read a book less when a
seeded partial shuffle disorders it, with the whitespace sham controlled?

`cost-that-bites-milder-20260922/PREREG.md` is the registration; this module carries the frozen
constants, the new dose operator, the plan, the resource meter, the two reader profiles, the
prepare / run / analyse legs and the reading. It is the one further experiment stage-0 §230
licenses for `fcr.v0`. Nothing in `cost_that_bites`, `feed_core`, `feed_session`,
`feed_controls`, `bcr`, `ablate` or `elicit` is edited: their bytes are the registered instrument
and the statistic's lineage, and they are imported, content-addressed and reused.

**The dose.** `ablate.paragraph_shuffle` is the wrong operator for a dose: it rotates the picked
paragraphs by one offset (at strength 1.0 that is a single cut, 0.7% of adjacencies broken), its
damage is not monotone in the strength, and it is one fixed variant per text. `partial_shuffle`
here picks `round(s * n)` paragraph positions with a seeded draw and gives their contents a
uniformly random non-identity permutation among themselves, so every other paragraph stays
where it was. At s = 0.65 about 64% of paragraphs move and about 87% of adjacent pairs break
(the call-free power record, `cost-that-bites-milder-20260922/ATTAINABILITY.md`). Seeded from
the text and a dose-tagged salt, `ablate._rng`'s discipline, so it is a function of the book,
the dose and the seed index and never of the run.

**Two reader profiles, one arm each, never pooled.** `claude` is the seated reader §230 measured
(`claude-haiku-4-5` over `claude -p`, through `elicit`'s transport unchanged) and is the arm
this registration licenses. `codex` exists so the arm can be moved to the other subscription if
one account's limits are reached *before either arm has bought a cell*: it is a *different
reader*, gets its own registration, cache, ledger, result and claim, carries the full shuffle as
a positive control because it has never been seated, and needs its own operator approval and its
own attainability record before `prepare` will write it. Whichever reader buys first holds the
question; the other is refused in this folder (PREREG.md, "The Codex contingency").

**The ledger survives a kill.** A `started` line precedes the probes, a checkpoint line follows
every session, and a `finished` line ends the invocation; a resume takes the larger of the
ledger's totals and the raw cache's, and `analyse` refuses while the box lock names this arm or
the last invocation has no finished line (`close` records an operator's decision that a killed
invocation will not be resumed).

    uv run python research/quality-measurement/cost_that_bites_milder.py plan
    uv run python research/quality-measurement/cost_that_bites_milder.py prepare
    uv run python research/quality-measurement/cost_that_bites_milder.py run
    uv run python research/quality-measurement/cost_that_bites_milder.py close   # after a kill only
    uv run python research/quality-measurement/cost_that_bites_milder.py analyse
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import ablate  # noqa: E402
import bcr  # noqa: E402
import cost_that_bites as ctb  # noqa: E402
import elicit  # noqa: E402
import feed_controls  # noqa: E402
import feed_core  # noqa: E402
import feed_session  # noqa: E402
import feed_substrate  # noqa: E402

ROOT = HERE.parents[1]
ARM_DIR = HERE / "cost-that-bites-milder-20260922"
LOCAL = ROOT / "runs" / "cost-that-bites-milder-20260922"
FITNESS_DIR = HERE / "corpora" / "fitness"
LOCK_HOLDER = ROOT / "runs" / "box.lock" / "holder"
LOCK_PREFIX = "cost-that-bites-milder-20260922:"

#: v2's committed cache and result. Read-only inputs of the request-identity precondition and
#: the reader-drift diagnostic; never loaded into, and never served to, this arm's reader.
V2_DIR = HERE / "cost-that-bites"
V2_RAW = V2_DIR / "raw-v2.jsonl"
V2_RESULTS = V2_DIR / "results-arm-v2.json"

#: What an operator writes before the Codex profile may be prepared (PREREG.md).
CODEX_APPROVAL = "codex-approval.json"
CODEX_ATTAINABILITY = "ATTAINABILITY-codex.md"

# ---------------------------------------------------------------- the registration, frozen

VERSION = "cost-that-bites.milder-v4"

#: The dose. One strength, registered before spend; 0.35 is not attainable at twenty books
#: (ATTAINABILITY.md) and is not run.
DOSE = 0.65

#: Salt family of the partial shuffle. Deliberately a child of the full shuffle's salt and
#: tagged with the dose, so no partial permutation can coincide with a v1/v2/v3 draw.
PARTIAL_SALT = f"{ctb.SHUFFLE_SALT}/partial"

#: Sessions per version per book: six, the number the power record sized (three is v2's).
REPLICATES = 6

#: First seed index of the dose's seed rule. The partial salt is new, so 0 overlaps nothing.
SEED_START = 0

#: The target sits in slot A in every session, v2's capacity-licensed seat.
TARGET_ROTATION = ctb.TARGET_ROTATION_V2

#: Sessions in flight at once: v2/v3's three.
WORKERS = 3

ALPHA = ctb.ALPHA
SCORABLE_FLOOR = ctb.SCORABLE_FLOOR
CAPACITY_FLOOR = ctb.CAPACITY_FLOOR_V2
MIN_BOOKS = ctb.MIN_BOOKS_V2

#: The full-shuffle effect this dose is sized from: the mean of v2's +0.1640 and v3's +0.1890.
FULL_EFFECT = 0.1765

#: The shift the design is powered for (the linear-attenuation expectation, 0.65 x 0.1765) and
#: the one it cannot reliably find (the convex s-squared expectation, 0.4225 x 0.1765).
DECLARED_TARGET_SHIFT = 0.115
UNDERPOWERED_AT = 0.075

#: The attenuation bracket the power record could not narrow: A4 (s squared) to A2 (broken
#: adjacency ratio). Reported beside the point estimate; it decides nothing.
EXPECTED_BRACKET = (0.075, 0.155)

#: Consecutive sessions ending on a failed or undispatched call after which no further session
#: is admitted. Three is one per worker: a usage limit fails every session in flight at once.
TRANSPORT_CIRCUIT = 3

#: Seed rule search bound, `ctb.seeds_for`'s.
_SEED_SEARCH = 50

#: The stop reason of a call a replay-only reader could not serve. Not a transport-failure
#: prefix on purpose: it is never counted as a call, only as a missing measurement.
NOT_IN_CACHE = "not_in_cache"

#: What an undispatched call's record says. Never persisted anywhere.
NOT_DISPATCHED = "not_dispatched"

PROBE_SYSTEM = (
    "If your context contains a line beginning with MARKER-, return only the word after the "
    "hyphen. Otherwise return only NONE."
)
PROBE_PROMPT = "Answer now."
PROBE_MARKER = "MARKER-LEAKED\n"

#: The second leak path the house tests (`tests/test_providers.py`,
#: `test_live_claude_completion_does_not_inherit_git_status`): a repository's status reaching a
#: tool-free completion. Re-checked on the registered binary from a scratch git repository.
GIT_PROBE_SYSTEM = (
    "If your context contains a Git status entry whose filename starts with GIT_CONTEXT_, "
    "return only that whole filename. Otherwise return only NONE."
)
GIT_PROBE_FILE = "GIT_CONTEXT_LEAKED"

#: What a probe's answer must not contain, by probe. The comparison is the house's
#: (`"LEAKED" not in text and "NONE" in text`), so "NONE." passes and "LEAKED" never does.
PROBE_LEAK_MARKS = {"claude_md": "LEAKED", "git_status": "GIT_CONTEXT_", "agents_md": "LEAKED"}

#: Sessions of this arm whose requests are byte-identical to v2's: the intact and sham copies
#: at replicates 0 to 2 (same texts, same seat, same competitors, same sample indices).
IDENTITY_VERSIONS: tuple[str, ...] = ("intact", "sham")
IDENTITY_REPLICATES = ctb.REPLICATES_V2

#: The same reader against itself: v3 minus v2 on those same requests, computed call-free from
#: the committed `results-arm-v2.json` and `results-arm-v3.json` (per-book means over replicates
#: 0 to 2, `ctb.interval_block`), and the sessions whose action sequence repeated exactly. It is
#: the baseline the drift diagnostic is read beside. A level rule was not registered because
#: this baseline's own intact interval excludes zero: the rule would have called v3 a different
#: reader.
SAME_READER_BASELINE: dict[str, Any] = {
    "source": "v3 - v2, per-book means over replicates 0-2, cost_that_bites.interval_block",
    "intact": {"point": 0.0679, "low": 0.0134, "high": 0.1256},
    "sham": {"point": -0.0411, "low": -0.1250, "high": 0.0438},
    "identical_sequences": {"intact": "7 of 60", "sham": "8 of 60", "shuffled": "2 of 60"},
}


@dataclass(frozen=True, slots=True)
class Profile:
    """One reader, one arm. Two profiles are two experiments and never share a file."""

    name: str
    arm: str
    model: str
    transport: str
    versions: tuple[str, ...]
    positive_control: bool
    #: Hard ceilings, read before every call; `None` means the transport cannot report it.
    limits: dict[str, float | None]
    #: Worst-case reservation per admitted session, read before every session.
    reserve: dict[str, float]
    tag: str
    registration_name: str
    claim_name: str
    effort: str | None = None
    #: A fresh call that reports no price is unknown usage on a transport that prices calls.
    requires_price: bool = True


PROFILES: dict[str, Profile] = {
    "claude": Profile(
        name="claude",
        arm="milder-v4",
        model=ctb.READER_MODEL,
        transport=ctb.TRANSPORT,
        versions=("intact", "partial", "sham"),
        positive_control=False,
        limits={"calls": 4_400, "tokens": 190_000_000, "usd": 150.0, "seconds": 28_800},
        reserve={"calls": 24, "tokens": 1_500_000, "usd": 1.5, "seconds": 1_800},
        tag="ctbm4",
        registration_name="registration.json",
        claim_name="claim.json",
    ),
    "codex": Profile(
        name="codex",
        arm="milder-v4-codex",
        model="gpt-6-astra",
        transport="codex",
        versions=("intact", "partial", "sham", "shuffled"),
        positive_control=True,
        limits={"calls": 5_900, "tokens": 150_000_000, "usd": None, "seconds": 43_200},
        reserve={"calls": 24, "tokens": 1_500_000, "usd": 0.0, "seconds": 1_800},
        tag="ctbm4x",
        registration_name="registration-codex.json",
        claim_name="claim-codex.json",
        effort="low",
        requires_price=False,
    ),
}

#: The contrasts read over book means, left minus right. The first and third decide.
CONTRASTS: tuple[tuple[str, str, str], ...] = (
    ("intact_minus_partial", "intact", "partial"),
    ("intact_minus_sham", "intact", "sham"),
    ("sham_minus_partial", "sham", "partial"),
)
#: The Codex profile's positive control: v2's own two deciding contrasts at the full dose.
POSITIVE_CONTRASTS: tuple[tuple[str, str, str], ...] = (
    ("intact_minus_shuffled", "intact", "shuffled"),
    ("sham_minus_shuffled", "sham", "shuffled"),
)

#: Every clause that reaches back to §230 is conditional on this run's reader being the one
#: §230 measured. The request-identity precondition proves the texts, prompt and transport are
#: v2's; the served snapshot is unobserved; the drift diagnostic is reported beside its
#: same-reader baseline and decides nothing (PREREG.md, "Is it still §230's reader?").
_IF_SAME = "if this run's reader is the one §230 measured, "

LICENCE = {
    "MOVES_WITH_ORDER": (
        "the reader reads a book less when 65% of its paragraphs are reordered among "
        "themselves, beyond the whitespace sham, for a book in slot A, on this shelf and this "
        "reader. Inside the reader's window the dose breaks 87% of adjacent pairs against the "
        "full shuffle's 99% (a ratio of 0.88), so it is a short step from destroyed order and "
        "not a book that is merely worse; " + _IF_SAME + "§230's claim extends that step. Not "
        "a quality instrument, not QUALIFIED, no editorial intervention"
    ),
    "MOVES_WITH_EDITEDNESS": (
        "intact - partial is above zero and sham - partial is not: the reader moved, but no "
        "further than the sham lets an order claim be read at this dose; no extension of §230"
    ),
    "NULL": (
        "not detected at the declared 0.115 at s = 0.65, with power 0.69 to 0.90 by "
        "heterogeneity model before the resampling optimism; not evidence against a shift of "
        "0.075 or less; " + _IF_SAME + "the licence narrows and §230's claim stays at "
        "destroyed order. No further dose and no further reader is run on this question to find "
        "one that moves"
    ),
    "INVERTED": (
        "the partially disordered book drew more reads: the registered claim is refuted; "
        + _IF_SAME + "§230's order reading is put in question (it is not reversed into a "
        "preference for disorder); the mechanism class goes to BRIEF.md's ledger"
    ),
    "UNREADABLE": "a precondition failed; its measured value is the finding, no interval is read",
    "UNSEATED": (
        "Codex profile only: the positive control did not move at the full dose, so this reader "
        "was not shown to read order at all and no dose reading exists"
    ),
}

#: The Codex profile is a reader §230 never measured: no clause of its licence reaches §230.
LICENCE_CODEX = {
    "MOVES_WITH_ORDER": (
        "this reader (never seated before, positive control passed) reads a book less at "
        "s = 0.65 beyond the whitespace sham, for a book in slot A, on this shelf; a claim about "
        "this reader only, which neither extends nor narrows §230; not a quality instrument, "
        "not QUALIFIED, no editorial intervention"
    ),
    "MOVES_WITH_EDITEDNESS": (
        "intact - partial is above zero and sham - partial is not: this reader moved, but no "
        "further than the sham lets an order claim be read at this dose"
    ),
    "NULL": (
        "this reader, shown to read the full shuffle, was not seen to move by 0.115 at s = 0.65; "
        "no power record exists for it, so this is not evidence against any shift; it neither "
        "extends nor narrows §230"
    ),
    "INVERTED": (
        "the partially disordered book drew more reads from this reader: the registered claim "
        "about this reader is refuted; §230 is not touched"
    ),
    "UNREADABLE": LICENCE["UNREADABLE"],
    "UNSEATED": LICENCE["UNSEATED"],
}


def licence(profile: Profile) -> dict[str, str]:
    return LICENCE_CODEX if profile.positive_control else LICENCE


def pre_registration(profile: Profile) -> dict[str, Any]:
    """Everything the reading depends on, as data; its digest is printed on every result."""
    return {
        "version": VERSION,
        "arm": profile.arm,
        "profile": profile.name,
        "instrument": feed_core.FCR_VERSION,
        "instrument_registration_digest": feed_core.registration_digest(),
        "statistic_lineage": {
            "design": ctb.VERSION_V2,
            "registration_digest_v2": ctb.registration_digest_v2(),
        },
        "versions": list(profile.versions),
        "dose": {
            "operator": "partial_shuffle",
            "strength": DOSE,
            "salt": f"{PARTIAL_SALT}/<strength>/<seed index>",
            "rule": "pick round(s*n) paragraph positions by a seeded sample and give their "
            "contents a uniformly random non-identity permutation among themselves",
        },
        "positive_control": (
            "cost_that_bites.book_shuffle at cost_that_bites.seeds_for(start=0, count=6)"
            if profile.positive_control
            else None
        ),
        "sham": "ablate.rewhitespace",
        "sham_strength": ctb.SHAM_STRENGTH,
        "reader": {
            "model": profile.model,
            "transport": profile.transport,
            "effort": profile.effort,
        },
        "target_rotation": TARGET_ROTATION,
        "replicates": REPLICATES,
        "seed_start": SEED_START,
        "seed_rule": "per book, the six lowest seed indices at or above seed_start whose dosed "
        "copy chunks to at least feed_core.MIN_CHUNKS_FEED and whose opening differs from the "
        "intact copy's",
        "dispatch_order": "replicate-major: every book's versions at replicate 0, then 1, ...",
        "workers": WORKERS,
        "alpha": ALPHA,
        "resamples": bcr._resamples(),
        "scorable_floor": SCORABLE_FLOOR,
        "capacity_floor": CAPACITY_FLOOR,
        "min_books": MIN_BOOKS,
        "primary": "target_read_share, book mean over scorable sessions: intact - partial",
        "sham_reading": "sham - partial, per sham and never pooled",
        "scorable_floor_denominator": "dispatched sessions, v2's rule (run_cells returned a row "
        "only for a session it ran); never-dispatched sessions are coverage, stamped partial",
        "request_identity": (
            None
            if profile.positive_control
            else {
                "cells": f"{'/'.join(IDENTITY_VERSIONS)} at replicates 0-{IDENTITY_REPLICATES - 1}",
                "rule": "at prepare, every such cell replays completely from v2's committed "
                "cache, opened replay-only, and reproduces v2's committed book means",
            }
        ),
        "reader_drift": (
            None
            if profile.positive_control
            else {
                "reported": "this - v2 per-book intact and sham means over the identity cells, "
                "with the interval, and identical action sequences, beside the baseline",
                "same_reader_baseline": SAME_READER_BASELINE,
                "decides": "nothing",
            }
        ),
        "probes": sorted(
            ("agents_md",) if profile.transport == "codex" else ("claude_md", "git_status")
        ),
        "probe_rule": "an answer passes when it contains NONE and not the probe's leak mark",
        "binary_pin": (
            "run copies the registered binary once, hash-checked, into the ignored local folder "
            "and puts that folder first on PATH" if profile.transport == "cli" else None
        ),
        "ledger": "started line, a checkpoint after every session, finished line; prior usage "
        "is the larger of the ledger's and the raw cache's totals",
        "reader_fence": "whichever profile buys a cell first holds the question; the other is "
        "refused in this folder",
        "cluster": "the book",
        "full_effect_sized_from": FULL_EFFECT,
        "declared_target_shift": DECLARED_TARGET_SHIFT,
        "underpowered_at": UNDERPOWERED_AT,
        "expected_bracket": list(EXPECTED_BRACKET),
        "limits": dict(profile.limits),
        "reserve_per_session": dict(profile.reserve),
        "transport_circuit": TRANSPORT_CIRCUIT,
        "decision": dict(licence(profile)),
    }


def registration_digest(profile: Profile) -> str:
    material = json.dumps(pre_registration(profile), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


# ------------------------------------------------------------------------------- the dose


def partial_order(text: str, *, strength: float = DOSE, index: int = 0) -> list[int]:
    """The permutation `partial_shuffle` applies, as source paragraph indices by position.

    Identical in its draws to the power record's `perm_partial`: the same salt, the same
    `sample`, the same shuffle loop. The loop is bounded here (64 redraws, then a rotation of
    the picked set) so it provably terminates; at two picked positions a redraw is needed with
    probability 1/2, so the bound changes nothing any real book can reach.
    """
    if not 0.0 < strength <= 1.0:
        raise ValueError(f"strength must be in (0, 1], got {strength}")
    blocks = ablate.paragraphs(text)
    count_all = len(blocks)
    if count_all < 2:
        raise ValueError("a book needs at least two paragraphs to shuffle")
    rng = ablate._rng(text, f"{PARTIAL_SALT}/{strength}/{index}")
    count = min(count_all, max(2, round(strength * count_all)))
    picked = sorted(rng.sample(range(count_all), count))
    sources = picked[:]
    for _ in range(64):
        rng.shuffle(sources)
        if sources != picked:
            break
    else:
        sources = picked[1:] + picked[:1]
    order = list(range(count_all))
    for target, source in zip(picked, sources, strict=True):
        order[target] = source
    return order


def partial_shuffle(text: str, *, strength: float = DOSE, index: int = 0) -> str:
    """The dosed copy: the book with `round(s * n)` of its paragraphs reordered among themselves."""
    blocks = ablate.paragraphs(text)
    return "\n\n".join(blocks[source] for source in partial_order(text, strength=strength,
                                                                   index=index))


def dose_metrics(order: Sequence[int]) -> dict[str, float]:
    """Displaced paragraphs and broken adjacencies, as fractions. Code-computed; decides nothing."""
    count = len(order)
    displaced = sum(1 for position, source in enumerate(order) if position != source) / count
    pairs = count - 1
    broken = (
        sum(1 for left, right in itertools.pairwise(order) if right != left + 1) / pairs
        if pairs
        else 0.0
    )
    return {"displaced": displaced, "broken_adjacency": broken}


def opening_of(text: str) -> str:
    """What a session shows of this text before the first choice: its recap and first section."""
    return feed_core.opening_for_slot(feed_core.SLOTS[TARGET_ROTATION], bcr.chunks(text))


def seeds_for_partial(
    text: str, *, start: int = SEED_START, count: int = REPLICATES, strength: float = DOSE
) -> tuple[int, ...]:
    """The `count` lowest seed indices at or above `start` whose dosed copy can carry a session.

    `ctb.seeds_for`'s rule, declared for the replication, with one clause added: it reads only
    chunk counts and the opening's text, never a reader's behaviour. At s = 0.65 the power
    record found exactly one pair in seeds 0 to 9 below the floor, `fitness-08` at seed 1 (10
    chunks against 11).

    **The added clause: the dosed copy's opening must differ from the intact copy's.** The
    replay cache keys on the request, and a request carries the prose revealed so far, not the
    whole book, so a partial copy whose moved paragraphs all lie past the opening would send the
    intact session's first request byte for byte, at the same sample index, and be served the
    intact session's first answer from the cache: two versions coupled through the cache rather
    than measured apart. A full shuffle can never do this; a partial one can in principle. On
    the fitness shelf no seed from 0 to 9 does, so the clause changes no registered seed.
    """
    intact_opening = opening_of(text)
    chosen: list[int] = []
    index = start
    while len(chosen) < count:
        if index > start + _SEED_SEARCH:
            raise ValueError(f"no {count} usable partial-shuffle seeds at or above {start}")
        dosed = partial_shuffle(text, strength=strength, index=index)
        if (
            len(bcr.chunks(dosed)) >= feed_core.MIN_CHUNKS_FEED
            and opening_of(dosed) != intact_opening
        ):
            chosen.append(index)
        index += 1
    return tuple(chosen)


# ------------------------------------------------------------------------------- the plan


@dataclass(frozen=True, slots=True)
class Planned:
    """One cell and what the registration records about it."""

    position: int
    cell: ctb.Cell
    seed: int | None
    metrics: dict[str, float] | None


def version_texts(text: str, profile: Profile) -> dict[str, list[tuple[str, int | None]]]:
    """Per version, `(target text, seed index)` for each replicate."""
    partial_seeds = seeds_for_partial(text, start=SEED_START, count=REPLICATES)
    out: dict[str, list[tuple[str, int | None]]] = {
        "intact": [(text, None)] * REPLICATES,
        "partial": [(partial_shuffle(text, index=seed), seed) for seed in partial_seeds],
        "sham": [(ctb.sham(text), None)] * REPLICATES,
    }
    if profile.positive_control:
        out["shuffled"] = [
            (ctb.book_shuffle(text, index=seed), seed)
            for seed in ctb.seeds_for(text, start=0, count=REPLICATES)
        ]
    return {version: out[version] for version in profile.versions}


def plan(texts: Sequence[tuple[str, str]], profile: Profile) -> list[Planned]:
    """Every book's versions at six replicates, the target in slot A, replicate-major order.

    Seating is `ctb.plan_v2`'s: book `i` is the target against books `i+1..i+3` wrapping the
    pool. The dispatch order is replicate-major so a stopped run loses replicates evenly across
    books and versions instead of losing whole books, as v1's transport stop did.
    """
    if len(texts) < feed_core.FEED_SIZE:
        raise ValueError(
            f"{len(texts)} book(s) on the pool; a feed of {feed_core.FEED_SIZE} needs "
            f"{feed_core.FEED_SIZE}"
        )
    by_book: list[tuple[int, str, tuple[tuple[str, str], ...], dict[str, Any]]] = []
    for index, (name, text) in enumerate(texts):
        others = tuple(
            texts[(index + offset) % len(texts)] for offset in range(1, feed_core.FEED_SIZE)
        )
        by_book.append((index, name, others, version_texts(text, profile)))
    planned: list[Planned] = []
    for replicate in range(REPLICATES):
        for index, name, others, versions in by_book:
            for version in profile.versions:
                target, seed = versions[version][replicate]
                spec = feed_core.FeedSpec(
                    feed_id=f"{profile.tag}-{index:02d}-{version}-r{replicate}",
                    arm=version,
                    target=target,
                    others=tuple(other for _, other in others),
                    dose={"partial": DOSE, "shuffled": 1.0}.get(version, 0.0),
                    note=(
                        f"target={name} ({version}, replicate {replicate}"
                        + (f", seed {seed}" if seed is not None else "")
                        + f") others={','.join(other for other, _ in others)}"
                    ),
                )
                cell = ctb.Cell(
                    feed_index=index,
                    target_name=name,
                    version=version,
                    rotation=TARGET_ROTATION,
                    spec=spec,
                    chunk_counts=tuple(len(bcr.chunks(member)) for member in spec.texts()),
                    replicate=replicate,
                )
                metrics = None
                if version == "partial" and seed is not None:
                    metrics = dose_metrics(partial_order(texts[index][1], index=seed))
                planned.append(Planned(len(planned), cell, seed, metrics))
    return planned


def plan_faults(planned: Sequence[Planned]) -> dict[str, str]:
    """`ctb.faults`, plus the cache-coupling fault: two versions of one book at one replicate
    whose openings are byte-identical would share cache entries (see `seeds_for_partial`)."""
    out = ctb.faults([item.cell for item in planned])
    seen: dict[tuple[int, int, str], str] = {}
    for item in planned:
        cell = item.cell
        key = (cell.feed_index, cell.replicate, opening_of(cell.spec.target))
        if key in seen:
            out.setdefault(
                cell.spec.feed_id,
                f"its opening is byte-identical to {seen[key]}'s: one cache entry",
            )
        else:
            seen[key] = cell.spec.feed_id
    return out


def seeds_by_book(planned: Sequence[Planned]) -> dict[str, dict[str, list[int]]]:
    out: dict[str, dict[str, list[int]]] = {}
    for item in planned:
        if item.seed is not None:
            out.setdefault(item.cell.target_name, {}).setdefault(item.cell.version, []).append(
                item.seed
            )
    return out


def seed_deviations(planned: Sequence[Planned]) -> dict[str, dict[str, list[int]]]:
    """Books whose seed rule did not give `SEED_START .. SEED_START + 5`, flagged by name."""
    default = list(range(SEED_START, SEED_START + REPLICATES))
    return {
        book: {version: seeds for version, seeds in versions.items() if seeds != default}
        for book, versions in seeds_by_book(planned).items()
        if any(seeds != default for seeds in versions.values())
    }


def manifest(planned: Sequence[Planned]) -> list[dict[str, Any]]:
    """The content address of every session's target, in dispatch order."""
    return [
        {
            "position": item.position,
            "feed_id": item.cell.spec.feed_id,
            "book": item.cell.target_name,
            "version": item.cell.version,
            "replicate": item.cell.replicate,
            "seed": item.seed,
            "target_sha256": _sha_text(item.cell.spec.target),
            "chunk_counts": list(item.cell.chunk_counts),
            **({"dose_metrics": item.metrics} if item.metrics is not None else {}),
        }
        for item in planned
    ]


# ---------------------------------------------------------------------------- the readers


class ReaderHalt(RuntimeError):
    """A reader found the transport changed under the run; no further call may be dispatched."""


class ClaudeReader(elicit.Elicitor):
    """`elicit`'s `claude -p` transport, byte-for-byte v2/v3's, plus two seams.

    Constructed exactly as `ctb._run_v2` constructs its Elicitor (`spot_model=None`, transport
    `cli`, the panel effort), so the request, its digest key, the §109 hardening and the
    never-cache-a-failure rule (§224, §235) are elicit's own. Added: `request_key`, the key
    `Elicitor._call` computes, so the meter can tell a free replay from a paid call before it
    is made; and a replay-only mode for the analysis, which serves the cache and makes no call.
    """

    def __init__(self, cache_path: Path, *, model: str, replay_only: bool = False) -> None:
        super().__init__(cache_path, model=model, spot_model=None, transport=ctb.TRANSPORT)
        self.replay_only = replay_only

    def request_key(
        self,
        system: str,
        turns: list[dict[str, Any]],
        *,
        schema: dict[str, object] | None,
        max_tokens: int,
        sample: int,
        model: str | None = None,
    ) -> str:
        params = self._params_for_system(
            system, turns, model=model or self.model, effort=self.effort,
            max_tokens=max_tokens, schema=schema,
        )
        return f"{elicit.digest({'params': params, 'transport': self.transport})}:{sample}"

    def cached_keys(self) -> frozenset[str]:
        with self._lock:
            return frozenset(self._cache)

    def _open(self) -> Any:
        # A replay-only reader serves other arms' committed caches (the identity check reads
        # v2's): it must be unable to write to any file it was pointed at.
        if self.replay_only:
            raise RuntimeError(f"a replay-only reader never writes {self.cache_path.name}")
        if self._handle is None:
            # elicit tolerates a torn last line on load; this keeps the next answer off it.
            self._handle = open_append(self.cache_path)
        return self._handle

    def _call_cli(self, params: dict[str, Any], *, key: str, tag: dict[str, Any]) -> dict[str, Any]:
        if self.replay_only:
            return {**tag, "key": key, "model": params["model"], "text": "", "refused": True,
                    "stop_reason": NOT_IN_CACHE, "usage": {}}
        return super()._call_cli(params, key=key, tag=tag)


class CodexReader:
    """The Codex subscription CLI as a feed reader, with elicit's cache rules re-stated.

    The request is the same flattened transcript `claude -p` is sent (`elicit._flatten_turns`),
    and the adapter's schema sentence makes the system block byte-identical to the one
    `elicit._call_cli` sends; the schema also goes down the adapter's native `--output-schema`
    path. The cache is append-only JSONL keyed
    by a digest of the request plus the sample index; a call that obtained no answer
    (`ProviderError`) is counted under a `transport_error:` reason and never persisted, and an
    old record carrying one is left aside on load, which is §235's rule. The adapter reports no
    price and no resolved model, and both are recorded as such.

    **One `MALFORMED_RESPONSE` is the reader's own answer and is cached as one.** The adapter
    raises that kind for a garbled or incomplete event stream, which is a transport failure by
    §235 and stays one, and also for a turn in which the model itself attempted an activity the
    tool-free profile forbids (`READER_ACTS`). That second case is behaviour, like a reply that
    does not parse; re-issuing it on a resume would re-roll a measurement, so it is persisted as
    an unusable answer (`reader_unusable:` stop reason, empty text) with the usage the stream
    reported, read from this thread's own attempt record.
    """

    transport = "codex"

    def __init__(
        self,
        cache_path: Path,
        *,
        provider: Any,
        model: str,
        effort: str | None,
        cli_version: str | None,
        replay_only: bool = False,
    ) -> None:
        self.cache_path = cache_path
        self.provider = provider
        self.model = model
        self.effort = effort
        self.cli_version = cli_version
        self.replay_only = replay_only
        self._lock = threading.Lock()
        self._cache: dict[str, dict[str, Any]] = {}
        self._handle: Any = None
        self.api_calls = 0
        self.replayed = 0
        self.transport_failures = 0
        self.failure_reasons: Counter[str] = Counter()
        self.left_aside = 0
        if cache_path.is_file():
            for line in cache_path.read_text(encoding="utf-8").splitlines():
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                key = record.get("key")
                if not isinstance(key, str):
                    continue
                if elicit._is_transport_failure(str(record.get("stop_reason") or "")):
                    self.left_aside += 1
                    continue
                self._cache[key] = record

    def __enter__(self) -> CodexReader:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None

    def _params(
        self,
        system: str,
        turns: list[dict[str, Any]],
        *,
        schema: dict[str, object] | None,
        max_tokens: int,
        model: str | None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": model or self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": turns,
            "effort": self.effort,
        }
        if schema is not None:
            params["output_config"] = {"format": {"type": "json_schema", "schema": schema}}
        return params

    def request_key(
        self,
        system: str,
        turns: list[dict[str, Any]],
        *,
        schema: dict[str, object] | None,
        max_tokens: int,
        sample: int,
        model: str | None = None,
    ) -> str:
        params = self._params(system, turns, schema=schema, max_tokens=max_tokens, model=model)
        return f"{elicit.digest({'params': params, 'transport': self.transport})}:{sample}"

    def cached_keys(self) -> frozenset[str]:
        with self._lock:
            return frozenset(self._cache)

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
        from litharness.domain.generation import CompletionRequest
        from litharness.providers.base import ProviderError

        chosen = model or self.model
        key = self.request_key(
            system, turns, schema=schema, max_tokens=max_tokens, sample=sample, model=model
        )
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                self.replayed += 1
                return cached
        if self.replay_only:
            return {**tag, "key": key, "model": chosen, "text": "", "refused": True,
                    "stop_reason": NOT_IN_CACHE, "usage": {}}
        request = CompletionRequest(
            prompt=elicit._flatten_turns(turns),
            system=system,
            schema=schema,
            model=chosen,
            max_output_tokens=max_tokens,
            timeout_seconds=elicit.CLI_TIMEOUT_SECONDS,
        )
        try:
            result = self.provider.complete(request)
        except ProviderError as error:
            snippet = " ".join(str(error).split())[:60]
            if _is_reader_act(error):
                act: dict[str, Any] = {
                    **tag, "key": key, "model": chosen, "text": "", "refused": True,
                    "stop_reason": f"reader_unusable:codex:{error.kind}:{snippet}",
                    "usage": _attempt_usage(getattr(self.provider, "last_attempt", None)),
                }
                self._persist(key, act)
                return act
            reason = f"transport_error:codex:{error.kind}:{snippet}"
            with self._lock:
                self.api_calls += 1
                self.transport_failures += 1
                self.failure_reasons[reason] += 1
            return {**tag, "key": key, "model": chosen, "text": "", "refused": True,
                    "stop_reason": reason, "usage": {}}
        version = (result.raw or {}).get("cli_version")
        if self.cli_version is not None and version != self.cli_version:
            raise ReaderHalt(f"codex CLI reported {version!r}, registered {self.cli_version!r}")
        usage = result.usage
        text = elicit._strip_fence(result.text)
        record = {
            **tag,
            "key": key,
            "model": chosen,
            "model_attribution": "requested; the Codex CLI reports no resolved model",
            "text": text,
            "refused": not text,
            "stop_reason": "end_turn",
            "cli_version": version,
            "usage": {
                "input": usage.input_tokens,
                "output": usage.output_tokens,
                "cache_read": usage.cache_read_tokens,
                "cache_write": usage.cache_write_tokens,
                "reasoning": usage.reasoning_tokens,
                "equivalent_usd": result.cost_usd,
            },
        }
        self._persist(key, record)
        return record

    def _persist(self, key: str, record: dict[str, Any]) -> None:
        with self._lock:
            self.api_calls += 1
            self._cache[key] = record
            if self._handle is None:
                self._handle = open_append(self.cache_path)
            self._handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            self._handle.flush()

    def spend(self) -> dict[str, int | float]:
        with self._lock:
            records = list(self._cache.values())
        return {
            key: sum(int((record.get("usage") or {}).get(key) or 0) for record in records)
            for key in ("input", "output", "cache_read", "cache_write", "reasoning")
        }


#: The adapter's messages that name the model's own act rather than the stream's condition.
READER_ACTS = ("attempted an unpermitted activity",)


def _is_reader_act(error: Any) -> bool:
    kind = str(getattr(error, "kind", ""))
    return kind == "malformed_response" and any(mark in str(error) for mark in READER_ACTS)


def _attempt_usage(attempt: Any) -> dict[str, Any]:
    """The `turn.completed` usage in an attempt's stdout, mapped as the adapter maps it; {} if
    none can be read (and the meter then drains on unknown usage, its registered rule)."""
    if not isinstance(attempt, dict):
        return {}
    for line in str(attempt.get("stdout") or "").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or event.get("type") != "turn.completed":
            continue
        usage = event.get("usage") or {}
        try:
            inputs = int(usage["input_tokens"])
            outputs = int(usage["output_tokens"])
            cached = int(usage.get("cached_input_tokens", 0))
            reasoning = int(usage.get("reasoning_output_tokens", 0))
        except (KeyError, TypeError, ValueError):
            return {}
        return {"input": inputs - cached, "output": outputs - reasoning, "cache_read": cached,
                "cache_write": 0, "reasoning": reasoning, "equivalent_usd": None}
    return {}


class PerThreadProvider:
    """One Codex adapter per worker thread, so `last_attempt` is this thread's own attempt."""

    def __init__(self, factory: Callable[[], Any]) -> None:
        self._factory = factory
        self._local = threading.local()

    def _mine(self) -> Any:
        provider = getattr(self._local, "provider", None)
        if provider is None:
            provider = self._local.provider = self._factory()
        return provider

    def complete(self, request: Any) -> Any:
        return self._mine().complete(request)

    @property
    def last_attempt(self) -> Any:
        return getattr(self._mine(), "last_attempt", None)


# ------------------------------------------------------------------------------ the meter


def _tokens(usage: dict[str, Any]) -> int:
    return sum(
        int(usage.get(key) or 0)
        for key in ("input", "output", "cache_read", "cache_write", "reasoning")
    )


class Meter:
    """The reader every session talks to: ceilings before each call and each session.

    **Before each call**, a call that would be fresh (its key is not a replay) is refused if any
    hard ceiling is already reached; the refusal is a `not_dispatched` record that goes nowhere,
    ends that session unscorable and halts the run. **Before each session**, a session is
    admitted only if every used total plus the worst-case reservation of every session in
    flight, this one included, stays under its ceiling; otherwise the run drains: no new
    session, the ones in flight finish. With the reservations sized to a worst-case session the
    per-call refusal is a backstop that should never fire, and the ledger says if it did.

    The run also drains on `TRANSPORT_CIRCUIT` consecutive sessions ending on a failed or
    undispatched call (a usage limit fails every session in flight at once), and on a fresh
    call that reports no usage (a ceiling that cannot be read cannot be enforced). It halts on
    a changed binary. Replays are free and are not counted against anything.
    """

    def __init__(
        self,
        reader: Any,
        *,
        profile: Profile,
        prior: dict[str, float] | None = None,
        clock: Callable[[], float] = time.monotonic,
        binary_guard: Callable[[], str | None] | None = None,
    ) -> None:
        self.reader = reader
        self.profile = profile
        self.limits = profile.limits
        self.reserve = profile.reserve
        prior = prior or {}
        self.used: dict[str, float] = {
            "calls": float(prior.get("calls", 0)),
            "tokens": float(prior.get("tokens", 0)),
            "usd": float(prior.get("usd", 0.0)),
        }
        self._prior_seconds = float(prior.get("seconds", 0.0))
        self._clock = clock
        self._started = clock()
        self._binary_guard = binary_guard
        self._replay = reader.cached_keys()
        self._lock = threading.Lock()
        self.in_flight = 0
        self.halted: str | None = None
        self.draining: str | None = None
        self.consecutive_failed = 0
        self.session_failure: dict[str, str] = {}
        self.fresh_calls = 0
        self.replays = 0
        self.transport_failures = 0
        self.failure_reasons: Counter[str] = Counter()
        self.not_dispatched = 0
        self.unknown_usage = 0
        self.sessions_ended_on_failure = 0

    def elapsed(self) -> float:
        return self._prior_seconds + self._clock() - self._started

    def _reached(self) -> str | None:
        for name in ("calls", "tokens", "usd"):
            limit = self.limits.get(name)
            if limit is not None and self.used[name] >= limit:
                return f"ceiling:{name}"
        limit = self.limits.get("seconds")
        if limit is not None and self.elapsed() >= limit:
            return "ceiling:seconds"
        return None

    def admit(self) -> bool:
        """Between sessions: may one more session start? False drains the run."""
        with self._lock:
            if self.halted is not None or self.draining is not None:
                return False
            if self._binary_guard is not None:
                changed = self._binary_guard()
                if changed is not None:
                    self.halted = f"halt:{changed}"
                    return False
            for name in ("calls", "tokens", "usd"):
                limit = self.limits.get(name)
                if limit is None:
                    continue
                if self.used[name] + (self.in_flight + 1) * self.reserve[name] > limit:
                    self.draining = f"ceiling:{name}"
                    return False
            limit = self.limits.get("seconds")
            if limit is not None and self.elapsed() + self.reserve["seconds"] > limit:
                self.draining = "ceiling:seconds"
                return False
            self.in_flight += 1
            return True

    def drain(self, reason: str) -> None:
        """No new session from now on; the ones in flight finish. The first reason is kept."""
        with self._lock:
            self.draining = self.draining or reason

    def release(self, feed_id: str, *, scorable: bool) -> str | None:
        """A session finished; returns the failure it ended on, if any, and trips the circuit."""
        with self._lock:
            self.in_flight -= 1
            failure = self.session_failure.get(feed_id)
            if failure is not None and not scorable:
                self.sessions_ended_on_failure += 1
                self.consecutive_failed += 1
                if self.consecutive_failed >= TRANSPORT_CIRCUIT and self.draining is None:
                    self.draining = "transport_circuit"
            else:
                self.consecutive_failed = 0
            return failure if not scorable else None

    def _refusal(self, tag: dict[str, Any], key: str, reason: str) -> dict[str, Any]:
        self.not_dispatched += 1
        stop = f"{NOT_DISPATCHED}:{reason}"
        self.session_failure[str(tag.get("feed"))] = stop
        return {**tag, "key": key, "text": "", "refused": True, "stop_reason": stop, "usage": {}}

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
        key = self.reader.request_key(
            system, turns, schema=schema, max_tokens=max_tokens, sample=sample, model=model
        )
        replay = key in self._replay
        if not replay:
            with self._lock:
                reason = self.halted or self._reached()
                if reason is not None:
                    self.halted = self.halted or reason
                    return self._refusal(tag, key, reason)
        try:
            record: dict[str, Any] = self.reader.ask_raw(
                system, turns, schema=schema, max_tokens=max_tokens, tag=tag, sample=sample,
                model=model,
            )
        except ReaderHalt as error:
            with self._lock:
                self.halted = f"halt:{error}"
                return self._refusal(tag, key, "halt")
        with self._lock:
            if replay:
                self.replays += 1
                return record
            self.used["calls"] += 1
            self.fresh_calls += 1
            stop = str(record.get("stop_reason") or "")
            if elicit._is_transport_failure(stop):
                self.transport_failures += 1
                self.failure_reasons[stop] += 1
                self.session_failure[str(tag.get("feed"))] = stop
                return record
            usage = record.get("usage") or {}
            tokens = _tokens(usage)
            price = usage.get("equivalent_usd")
            self.used["tokens"] += tokens
            if price is not None:
                self.used["usd"] += float(price)
            if tokens <= 0 or (self.profile.requires_price and not price):
                self.unknown_usage += 1
                self.draining = self.draining or "unknown_usage"
        return record

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "used_cumulative": dict(self.used),
                "seconds_cumulative": round(self.elapsed(), 1),
                "fresh_calls": self.fresh_calls,
                "replays": self.replays,
                "transport_failures": self.transport_failures,
                "failure_reasons": dict(self.failure_reasons),
                "not_dispatched": self.not_dispatched,
                "unknown_usage": self.unknown_usage,
                "sessions_ended_on_failure": self.sessions_ended_on_failure,
                "halted": self.halted,
                "draining": self.draining,
            }


def run_plan(
    meter: Meter,
    planned: Sequence[Planned],
    *,
    model: str,
    workers: int = WORKERS,
    log: Callable[[str], None] = print,
    on_session: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[list[ctb.Row], dict[str, Any]]:
    """Buy every planned session through the meter, `workers` at a time, in dispatch order.

    The live log names each session's outcome and step count and **never a target share**, so
    no reading can be watched forming while the arm is bought. `on_session` is called after
    every session (the ledger's checkpoint). **Any exception drains the run**: a worker that
    raises, or an interrupt in the waiting thread, stops every other worker from admitting a
    new session, so a crash never lets the rest of the plan be bought behind it.
    """
    rows: list[ctb.Row] = []
    lock = threading.Lock()
    pending = list(planned)
    started = time.monotonic()
    admitted = 0

    def next_item() -> Planned | None:
        nonlocal admitted
        with lock:
            if not pending or not meter.admit():
                return None
            admitted += 1
            return pending.pop(0)

    def one(item: Planned) -> None:
        cell = item.cell
        scorable = False
        try:
            session = feed_session.run_feed_session(
                meter, cell.spec, model=model, rotation=cell.rotation,
                replicate=cell.replicate,
            )
            scorable = session.scorable
        finally:
            failure = meter.release(cell.spec.feed_id, scorable=scorable)
        row = ctb.Row(
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
        outcome = "ok" if scorable else (failure or session.exit_note or "unscorable")
        if on_session is not None:
            on_session({"feed_id": cell.spec.feed_id, "position": item.position,
                        "outcome": outcome, "steps": len(session.actions),
                        "sessions_completed": done})
        log(
            f"  [{done}/{len(planned)}] {cell.spec.feed_id}: {outcome} "
            f"steps={len(session.actions)} {time.monotonic() - started:.0f}s"
        )

    def worker() -> None:
        try:
            while (item := next_item()) is not None:
                one(item)
        except BaseException as error:
            meter.drain(f"error:{type(error).__name__}")
            raise

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(worker) for _ in range(workers)]
        try:
            # Waited on with a timeout so an interrupt reaches this thread on Windows too.
            while wait(futures, timeout=1.0).not_done:
                pass
            for future in futures:
                future.result()
        except BaseException as error:
            meter.drain(f"error:{type(error).__name__}")
            raise
    snapshot = meter.snapshot()
    stop = snapshot["halted"] or snapshot["draining"]
    ledger = {
        **snapshot,
        "sessions_planned": len(planned),
        "sessions_admitted": admitted,
        "sessions_completed": len(rows),
        "sessions_not_admitted": len(pending),
        "stop": stop,
        #: Every planned session was dispatched and none ended on a call that obtained no
        #: answer. Anything else is resumable: bought calls replay free (RUNBOOK).
        "complete": not pending and stop is None and not snapshot["sessions_ended_on_failure"],
        "seconds_this_invocation": round(time.monotonic() - started, 1),
    }
    return rows, ledger


# ----------------------------------------------------------------------------- the reading


def book_means(rows: Sequence[ctb.Row], versions: Sequence[str]) -> dict[str, dict[str, float]]:
    """`ctb.by_book` over any version set: a book counts only with every version scorable once."""
    collected: dict[str, dict[str, list[float]]] = {}
    for row in rows:
        if row.session.scorable:
            collected.setdefault(row.book_key, {}).setdefault(row.version, []).append(
                row.session.target_read_share
            )
    return {
        book: {version: statistics.fmean(shares) for version, shares in present.items()}
        for book, present in collected.items()
        if all(version in present for version in versions)
    }


def paired(
    means: dict[str, dict[str, float]], contrasts: Sequence[tuple[str, str, str]]
) -> dict[str, list[tuple[str, float]]]:
    """`ctb.paired_v2` over named contrasts: one observation per book, the book the cluster."""
    return {
        name: [(book, means[book][left] - means[book][right]) for book in sorted(means)]
        for name, left, right in contrasts
    }


def _measure_means(
    rows: Sequence[ctb.Row], versions: Sequence[str], measure: Callable[[Any], float]
) -> dict[str, dict[str, float]]:
    collected: dict[str, dict[str, list[float]]] = {}
    for row in rows:
        if row.session.scorable:
            collected.setdefault(row.book_key, {}).setdefault(row.version, []).append(
                measure(row.session)
            )
    return {
        book: {version: statistics.fmean(values) for version, values in present.items()}
        for book, present in collected.items()
        if all(version in present for version in versions)
    }


def _seed_spread(rows: Sequence[ctb.Row], version: str) -> dict[str, float]:
    spread: dict[str, float] = {}
    for book in sorted({row.book_key for row in rows}):
        shares = [
            row.session.target_read_share
            for row in rows
            if row.book_key == book and row.version == version and row.session.scorable
        ]
        if len(shares) > 1:
            spread[book] = statistics.pstdev(shares)
    return spread


def reading(
    rows: Sequence[ctb.Row], profile: Profile, *, identity: dict[str, Any] | None = None
) -> dict[str, Any]:
    """v2's reading, over this arm's versions: preconditions in order, then one decision.

    Every precondition reports its measured value beside its floor and its verdict, pass or
    fail, which is v2's rule. The statistic, the interval and the decision table are v2's
    functions (`ctb.interval_block`, `ctb.decide`, `ctb.capacity_v2`, `feed_controls`' `fp5`);
    only the version names and the replicate count differ.

    **`rows` are the dispatched sessions**, v2's denominator: `ctb.run_cells` returned a row
    only for a session it ran, so a session never dispatched was coverage, not an unscorable
    session. `analyse` passes exactly those and stamps coverage separately. `identity` is the
    registration's request-identity record; `analyse` always passes it for the Claude profile,
    and it is then the first precondition.
    """
    sessions = [row.session for row in rows]
    versions = profile.versions
    per_version: dict[str, Any] = {}
    for version in versions:
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
    capacity = ctb.capacity_v2(sessions)
    means = book_means(rows, versions)
    contrasts = CONTRASTS + (POSITIVE_CONTRASTS if profile.positive_control else ())
    pairs = paired(means, contrasts)
    blocks = {name: ctb.interval_block(values) for name, values in pairs.items()}
    preconditions = [
        {
            "name": "scorable_floor",
            "measured": {v: block["scorable_share"] for v, block in per_version.items()},
            "floor": SCORABLE_FLOOR,
            "verdict": "PASS" if readable else "FAIL",
        },
        {
            "name": "fp5",
            "measured": fp5.get("statistic"),
            "floor": fp5.get("floor"),
            "verdict": str(fp5["verdict"]),
        },
        {
            "name": "capacity",
            "measured": capacity.get("shares"),
            "floor": CAPACITY_FLOOR,
            "verdict": capacity["verdict"],
        },
        {
            "name": "books_complete",
            "measured": len(means),
            "floor": MIN_BOOKS,
            "verdict": "PASS" if len(means) >= MIN_BOOKS else "FAIL",
        },
    ]
    if identity is not None:
        preconditions.insert(
            0,
            {
                "name": "request_identity",
                "measured": {
                    "cells": identity.get("cells"),
                    "replayed_complete": identity.get("replayed_complete"),
                    "max_abs_book_mean_diff": identity.get("max_abs_book_mean_diff"),
                },
                "floor": "every identity cell replays from v2's cache and reproduces its means",
                "verdict": "PASS" if identity.get("passed") is True else "FAIL",
            },
        )
    if profile.positive_control:
        full = blocks["intact_minus_shuffled"]
        full_order = blocks["sham_minus_shuffled"]
        seated = bool(full.get("above_zero")) and bool(full_order.get("above_zero"))
        preconditions.append(
            {
                "name": "positive_control",
                "measured": {
                    "intact_minus_shuffled": full.get("low"),
                    "sham_minus_shuffled": full_order.get("low"),
                },
                "floor": "both lower bounds above 0",
                "verdict": "PASS" if seated else "FAIL",
            }
        )
    failed = [p["name"] for p in preconditions if p["verdict"] != "PASS"]
    if [name for name in failed if name != "positive_control"]:
        decision = "UNREADABLE"
    elif failed:
        decision = "UNSEATED"
    else:
        decision = ctb.decide(
            fp5_verdict="PASS",
            readable_versions=True,
            complete_clusters=len(means),
            shuffle=blocks["intact_minus_partial"],
            order=blocks["sham_minus_partial"],
        )
    primary = blocks["intact_minus_partial"]
    point = primary.get("point")
    step_pairs = paired(
        _measure_means(rows, versions, lambda s: float(s.abandonment_step)), contrasts
    )
    first_pairs = paired(
        _measure_means(rows, versions, ctb._first_read_on_target), contrasts
    )
    return {
        "decision": decision,
        "licence": licence(profile)[decision],
        "preconditions": preconditions,
        "fp5": fp5,
        "capacity": capacity,
        "readable_versions": readable,
        "per_version": per_version,
        "books_complete": len(means),
        "book_means": means,
        "target_read_share": blocks,
        "declared_target_shift": DECLARED_TARGET_SHIFT,
        "underpowered_at": UNDERPOWERED_AT,
        "expected_bracket": {
            "bracket": list(EXPECTED_BRACKET),
            "point": point,
            "inside": (
                None
                if point is None
                else EXPECTED_BRACKET[0] <= point <= EXPECTED_BRACKET[1]
            ),
            "decides": "nothing",
        },
        "diagnostics": {
            "abandonment_step": {n: ctb.interval_block(v) for n, v in step_pairs.items()},
            "first_read_on_target": {n: ctb.interval_block(v) for n, v in first_pairs.items()},
            "partial_seed_spread": _seed_spread(rows, "partial"),
            "positional": feed_controls.slot_share_table(sessions)["slots"],
        },
    }


def reader_drift(rows: Sequence[ctb.Row], v2_results: Path) -> dict[str, Any]:
    """This arm against v2 on byte-identical requests, beside the same-reader baseline.

    Per book, this arm's intact and sham means over replicates 0 to 2 minus v2's committed
    means, with v2's interval; and the sessions whose action sequence repeats v2's exactly.
    **It decides nothing**: the same reader against itself (v3 - v2) already shows an intact
    difference whose interval excludes zero, so no level rule this record could write would
    separate a changed reader from a second run of the same one.
    """
    v2 = json.loads(v2_results.read_text(encoding="utf-8"))
    committed = v2["reading"]["book_means"]
    theirs = {
        (int(row["feed_index"]), str(row["version"]), int(row["session"]["replicate"])):
        tuple(tuple(step) for step in row["session"]["actions"])
        for row in v2["rows"]
        if row["version"] in IDENTITY_VERSIONS
    }
    mine = [
        row for row in rows
        if row.version in IDENTITY_VERSIONS and row.replicate < IDENTITY_REPLICATES
    ]
    means = book_means(mine, IDENTITY_VERSIONS)
    differences = {
        version: ctb.interval_block(
            [(book, means[book][version] - committed[book][version])
             for book in sorted(means) if book in committed]
        )
        for version in IDENTITY_VERSIONS
    }
    identical: dict[str, str] = {}
    for version in IDENTITY_VERSIONS:
        compared = [
            row for row in mine
            if row.version == version and row.session.scorable
            and (row.feed_index, version, row.replicate) in theirs
        ]
        same = sum(
            1 for row in compared
            if tuple(row.session.actions) == theirs[(row.feed_index, version, row.replicate)]
        )
        identical[version] = f"{same} of {len(compared)}"
    return {
        "this_minus_v2": differences,
        "identical_sequences": identical,
        "same_reader_baseline": SAME_READER_BASELINE,
        "decides": "nothing",
    }


# ----------------------------------------------------------------------- files and hashes


@dataclass(frozen=True, slots=True)
class Paths:
    """Where one registration's files live. Tests point every one of them at a scratch root."""

    root: Path
    arm_dir: Path
    local: Path
    fitness_dir: Path
    lock_holder: Path
    v2_raw: Path = V2_RAW
    v2_results: Path = V2_RESULTS

    def registration(self, profile: Profile) -> Path:
        return self.arm_dir / profile.registration_name

    def claim(self, profile: Profile) -> Path:
        return self.arm_dir / profile.claim_name

    def raw(self, profile: Profile) -> Path:
        return self.arm_dir / f"raw-{profile.arm}.jsonl"

    def ledger(self, profile: Profile) -> Path:
        return self.arm_dir / f"runs-{profile.arm}.jsonl"

    def results(self, profile: Profile) -> Path:
        return self.arm_dir / f"results-{profile.arm}.json"

    def texts(self, profile: Profile) -> Path:
        return self.local / profile.arm / "texts.json"

    def pin_dir(self, profile: Profile, sha256: str) -> Path:
        """The ignored folder holding the pinned copy of one registered binary."""
        return self.local / profile.arm / "bin" / sha256[:16]

    @property
    def codex_approval(self) -> Path:
        return self.arm_dir / CODEX_APPROVAL

    @property
    def codex_attainability(self) -> Path:
        return self.arm_dir / CODEX_ATTAINABILITY


DEFAULT_PATHS = Paths(
    root=ROOT, arm_dir=ARM_DIR, local=LOCAL, fitness_dir=FITNESS_DIR, lock_holder=LOCK_HOLDER,
    v2_raw=V2_RAW, v2_results=V2_RESULTS,
)


def _sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def write_new(path: Path, value: Any) -> None:
    """Exclusive create: an existing result is never overwritten."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")


def sources(profile: Profile, paths: Paths = DEFAULT_PATHS) -> list[Path]:
    """Every file whose bytes the run depends on, content-addressed in the registration."""
    root = paths.root
    qm = root / "research" / "quality-measurement"
    arm = paths.arm_dir
    files = [
        qm / "cost_that_bites_milder.py",
        arm / "PREREG.md",
        arm / "RUNBOOK.md",
        arm / "ATTAINABILITY.md",
        arm / "attainability" / "milder_dose_power.py",
        arm / "attainability" / "results.json",
        arm / "attainability" / "noise_check.py",
        arm / "attainability" / "noise_check.json",
        arm / "attainability" / "export_texts.py",
        arm / "attainability" / "run.log",
        root / "tests" / "test_cost_that_bites_milder.py",
        qm / "cost_that_bites.py",
        qm / "feed_core.py",
        qm / "feed_session.py",
        qm / "feed_controls.py",
        qm / "feed_substrate.py",
        qm / "bcr.py",
        qm / "ablate.py",
        qm / "elicit.py",
        qm / "personas.py",
        qm / "corpus_io.py",
        root / "src" / "litharness" / "domain" / "events.py",
        root / "uv.lock",
    ]
    if not profile.positive_control:
        # The request-identity precondition and the drift diagnostic read these.
        files += [paths.v2_raw, paths.v2_results]
    if profile.transport == "codex":
        files += [paths.codex_approval, paths.codex_attainability]
        provider = root / "src" / "litharness" / "providers"
        files += [
            provider / "codex_cli.py",
            provider / "codex_schema.py",
            provider / "base.py",
            provider / "cli.py",
            root / "src" / "litharness" / "domain" / "generation.py",
            root / "src" / "litharness" / "domain" / "failures.py",
        ]
    return files


# ----------------------------------------------------------------------------- the binary


def resolve_cli(name: str = "claude") -> Path:
    """The executable `subprocess.run([name, ...])` starts, found the way CreateProcess finds it.

    `elicit._call_cli` runs a bare `claude`. On Windows CreateProcess appends `.exe` and searches
    the loading application's directory, the current directory, the system directories and the
    Windows directory before PATH, and ignores PATHEXT; so `shutil.which('claude')` can name a
    `.CMD` shim the transport never runs. This returns what the transport will run.
    """
    if os.name != "nt":
        found = shutil.which(name)
        if found is None:
            raise FileNotFoundError(f"no {name} on PATH")
        return Path(found).resolve()
    executable = name if name.lower().endswith(".exe") else f"{name}.exe"
    system_root = Path(os.environ.get("SYSTEMROOT", "C:/Windows"))
    candidates = [
        Path(sys.executable).parent,
        Path(getattr(sys, "_base_executable", sys.executable)).parent,
        Path.cwd(),
        system_root / "System32",
        system_root / "System",
        system_root,
        *(Path(entry) for entry in os.environ.get("PATH", "").split(os.pathsep) if entry),
    ]
    for directory in candidates:
        path = directory / executable
        if path.is_file():
            return path.resolve()
    raise FileNotFoundError(f"no {executable} where CreateProcess looks")


def binary_version(path: Path) -> str:
    """`<binary> --version`. Prints a version; makes no model call."""
    completed = subprocess.run(
        [str(path), "--version"], capture_output=True, text=True, timeout=60, check=True
    )
    return completed.stdout.strip()


def binary_info(profile: Profile, codex_binary: Path | None) -> dict[str, Any]:
    if profile.transport == "codex":
        if codex_binary is None:
            raise ValueError("the codex profile needs --codex-binary: the native codex.exe")
        path = codex_binary.resolve()
        if path.suffix.lower() in {".cmd", ".bat", ".ps1"}:
            raise ValueError("the codex profile needs the native executable, not a shell shim")
    else:
        path = resolve_cli("claude")
    return {"binary": str(path), "binary_sha256": file_sha(path),
            "binary_version": binary_version(path)}


def pin_cli(
    profile: Profile,
    paths: Paths,
    reg: dict[str, Any],
    *,
    version_reader: Callable[[Path], str] = binary_version,
) -> Path:
    """Run on a private, hash-checked copy of the registered binary, whatever updates the original.

    Interactive sessions on this box update `~/.local/bin/claude.exe` in place, and a setting in
    this process cannot stop them. So the first invocation copies the registered binary, only if
    it still hashes to the registration, into the ignored local folder (named by its hash), and
    every invocation checks the copy's hash and version and puts its folder first on PATH, then
    confirms with `resolve_cli` that CreateProcess will start the copy and nothing ahead of it.
    Once pinned, a later update of the original changes nothing this arm runs.
    """
    registered = Path(reg["reader"]["binary"])
    expected = str(reg["reader"]["binary_sha256"])
    folder = paths.pin_dir(profile, expected)
    pinned = folder / registered.name
    if not pinned.is_file():
        if not registered.is_file() or file_sha(registered) != expected:
            raise RuntimeError(
                f"{registered} no longer hashes to the registration and no pinned copy exists; "
                "nothing was bought, so prepare again, review, commit and push"
            )
        folder.mkdir(parents=True, exist_ok=True)
        partial = folder / (registered.name + ".partial")
        shutil.copy2(registered, partial)  # the mode too: POSIX needs the exec bit
        partial.replace(pinned)
    if file_sha(pinned) != expected:
        raise RuntimeError(f"the pinned copy {pinned} does not hash to the registration")
    if version_reader(pinned) != reg["reader"]["binary_version"]:
        raise RuntimeError(f"the pinned copy {pinned} reports another version")
    os.environ["PATH"] = str(folder) + os.pathsep + os.environ.get("PATH", "")
    started = resolve_cli(Path(registered.name).stem)
    if started != pinned.resolve():
        raise RuntimeError(f"CreateProcess would start {started}, not the pinned copy {pinned}")
    return pinned


def disclosed_changes(profile: Profile, version: str) -> list[str]:
    if profile.transport == "codex":
        return [
            "a different reader from the one §230 seated: its own arm, never pooled",
            f"Codex CLI {version}; the adapter reports no price and no resolved model",
        ]
    return [
        f"Claude CLI {version}; v2 and v3 recorded no CLI version (nearest records: 2.1.236 "
        "measured in §109 before them, 2.1.263 recorded 2026-09-08 after them), so the binary "
        "is a disclosed, uncontrolled change; the isolation probes re-check CLAUDE.md exclusion "
        "and the git-status path on it, and the run is on a pinned, hash-checked copy",
        "the transport records the requested alias claude-haiku-4-5, not the served snapshot, "
        "exactly as v2 and v3 did",
    ]


# -------------------------------------------------------------------------------- ledger


def read_ledgers(path: Path) -> list[dict[str, Any]]:
    """Every ledger line. A truncated last line (a kill mid-append) is skipped, not fatal."""
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            out.append(record)
    return out


def _torn(path: Path) -> bool:
    """Does the file end mid-line, as a kill during an append leaves it?"""
    if not path.is_file() or not path.stat().st_size:
        return False
    with path.open("rb") as handle:
        handle.seek(-1, os.SEEK_END)
        return handle.read(1) != b"\n"


def open_append(path: Path) -> Any:
    """An append handle that first closes a torn last line, so the next record is not glued to
    the fragment (and lost with it when the file is read back)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    torn = _torn(path)
    handle = path.open("a", encoding="utf-8", newline="\n")
    if torn:
        handle.write("\n")
    return handle


def append_ledger(path: Path, ledger: dict[str, Any]) -> None:
    with open_append(path) as handle:
        handle.write(json.dumps(ledger, sort_keys=True, ensure_ascii=False) + "\n")
        handle.flush()


_SESSION_KEYS = ("event", "feed_id", "position", "outcome", "steps")


def invocations(ledgers: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """One summary per invocation: its lines overlaid in order, the last one winning.

    An invocation whose last line has no `finished_at` was killed (or is still running): its
    summary is its last checkpoint, so what it bought and why its calls failed survive.
    """
    grouped: dict[int, list[dict[str, Any]]] = {}
    for index, line in enumerate(ledgers):
        number = line.get("invocation")
        grouped.setdefault(int(number) if number is not None else -1 - index, []).append(line)
    summaries = []
    for number, lines in grouped.items():
        summary: dict[str, Any] = {}
        for line in lines:
            summary.update(line)
        for key in _SESSION_KEYS:
            summary.pop(key, None)
        summary["invocation"] = number
        summary["finished"] = "finished_at" in lines[-1]
        summaries.append(summary)
    return summaries


def finished(ledgers: Sequence[dict[str, Any]]) -> bool:
    """Did the last invocation end on a finished (or operator-closed) line?"""
    return bool(ledgers) and "finished_at" in ledgers[-1]


def raw_totals(raw: Path) -> dict[str, Any]:
    """What the raw cache says was bought: answered calls, their usage, the sessions named."""
    totals: dict[str, Any] = {"records": 0, "calls": 0.0, "tokens": 0.0, "usd": 0.0,
                              "feeds": set()}
    if not raw.is_file():
        return totals
    for line in raw.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict) or not isinstance(record.get("key"), str):
            continue
        totals["records"] += 1
        if elicit._is_transport_failure(str(record.get("stop_reason") or "")):
            continue
        usage = record.get("usage") or {}
        totals["calls"] += 1
        totals["tokens"] += _tokens(usage)
        totals["usd"] += float(usage.get("equivalent_usd") or 0.0)
        if record.get("feed"):
            totals["feeds"].add(str(record["feed"]))
    return totals


def prior_usage(ledgers: Sequence[dict[str, Any]], raw: Path | None = None) -> dict[str, float]:
    """The cumulative totals a resume starts from: the ledger's latest, or the raw cache's if
    larger (a kill loses at most the calls after the last checkpoint, and those are cached)."""
    used: dict[str, float] = {}
    for line in reversed(ledgers):
        if "used_cumulative" in line:
            used = {k: float(v) for k, v in (line.get("used_cumulative") or {}).items()}
            used["seconds"] = float(line.get("seconds_cumulative") or 0.0)
            break
    if raw is not None:
        totals = raw_totals(raw)
        for name in ("calls", "tokens", "usd"):
            used[name] = max(float(used.get(name, 0.0)), float(totals[name]))
    return used


def dispatched_feeds(ledgers: Sequence[dict[str, Any]], raw: Path) -> set[str]:
    """Sessions known to have been dispatched: checkpointed, or holding a cached answer."""
    feeds = {
        str(line["feed_id"]) for line in ledgers
        if line.get("event") == "session" and line.get("feed_id")
    }
    return feeds | set(raw_totals(raw)["feeds"])


def purchases(profile: Profile, paths: Paths) -> dict[str, Any]:
    """Has this profile's arm bought a cell? Probe-only invocations are not purchases."""
    records = raw_totals(paths.raw(profile))["records"]
    fresh = sum(
        int(summary.get("fresh_calls") or 0)
        for summary in invocations(read_ledgers(paths.ledger(profile)))
    )
    reading_exists = paths.results(profile).exists()
    return {
        "raw_records": records,
        "fresh_calls": fresh,
        "reading": reading_exists,
        "any": bool(records or fresh or reading_exists),
    }


def other_profile(profile: Profile) -> Profile:
    return next(other for other in PROFILES.values() if other.name != profile.name)


def fence(profile: Profile, paths: Paths) -> None:
    """Whichever reader buys a cell first holds the question; the other is refused here."""
    other = other_profile(profile)
    if purchases(other, paths)["any"]:
        raise RuntimeError(
            f"the {other.arm} arm has bought cells: this question is held by that reader, and "
            f"a {profile.name} arm now is a new experiment with its own stage-0 entry, which "
            "neither extends nor narrows §230"
        )


# ------------------------------------------------------------------------------- prepare


def extract_texts(fitness_dir: Path) -> tuple[list[tuple[str, str]], dict[str, str]]:
    """The shelf's texts, read from temporary COPIES of the stores (an open may migrate them)."""
    stores = sorted(fitness_dir.glob("fitness-*.db"))
    if not stores:
        raise FileNotFoundError(f"no fitness stores under {fitness_dir}")
    hashes = {path.name: file_sha(path) for path in stores}
    with tempfile.TemporaryDirectory(prefix="ctbm-fitness-", ignore_cleanup_errors=True) as tmp:
        for path in stores:
            shutil.copy2(path, Path(tmp) / path.name)
            wal = path.with_name(path.name + "-wal")
            if wal.is_file() and wal.stat().st_size:
                shutil.copy2(wal, Path(tmp) / wal.name)
        texts = feed_substrate.fitness_texts(Path(tmp))
    return texts, hashes


def build_registration(
    profile: Profile,
    texts: Sequence[tuple[str, str]],
    store_hashes: dict[str, str],
    binary: dict[str, Any],
    paths: Paths,
    texts_sha256: str,
    identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    planned = plan(texts, profile)
    broken = plan_faults(planned)
    if broken:
        raise ValueError(f"the plan faults; nothing is registered: {broken}")
    partial = [item.metrics for item in planned if item.metrics is not None]
    return {
        "version": VERSION,
        "arm": profile.arm,
        "profile": profile.name,
        "pre_registration": pre_registration(profile),
        "registration_digest": registration_digest(profile),
        "request_identity": identity,
        "reader": {
            "model": profile.model,
            "transport": profile.transport,
            "effort": profile.effort,
            **binary,
            "hardening": list(elicit.CLI_HARDENING) if profile.transport == "cli" else None,
            "disclosed_changes": disclosed_changes(profile, binary["binary_version"]),
        },
        "inputs": {
            "fitness_dir": _rel(paths.fitness_dir, paths.root),
            "stores_sha256": store_hashes,
            "texts_file": _rel(paths.texts(profile), paths.root),
            "texts_sha256": texts_sha256,
            "books": {
                name: {
                    "text_sha256": _sha_text(text),
                    "words": len(text.split()),
                    "paragraphs": len(ablate.paragraphs(text)),
                    "chunks": len(bcr.chunks(text)),
                }
                for name, text in texts
            },
        },
        "plan": {
            "books": len(texts),
            "sessions": len(planned),
            "max_calls": len(planned) * feed_core.MAX_STEPS,
            "seeds": seeds_by_book(planned),
            "seed_deviations": seed_deviations(planned),
            "dose_metrics_mean": {
                key: statistics.fmean(m[key] for m in partial) for key in partial[0]
            },
        },
        "cells": manifest(planned),
        "source_hashes": {
            _rel(path, paths.root): file_sha(path) for path in sources(profile, paths)
        },
    }


def claim_statement(profile: Profile) -> str:
    reader = f"{profile.model} over " + ("claude -p" if profile.transport == "cli" else "codex")
    return (
        f"fcr.v0's costed reader ({reader}) reads a fitness book in slot A less when a seeded "
        "partial shuffle reorders 65% of its paragraphs among themselves, beyond a whitespace "
        "sham, at twenty books and six sessions per version; not a quality instrument and not "
        "a qualification."
    )


def write_claim(profile: Profile, paths: Paths, status: str) -> None:
    files = [("registration", paths.arm_dir / "PREREG.md")]
    if paths.registration(profile).is_file():
        files.append(("registration", paths.registration(profile)))
    if status == "observed":
        files += [
            ("raw_result", paths.raw(profile)),
            ("raw_result", paths.ledger(profile)),
            ("derived_result", paths.results(profile)),
            ("control_result", paths.results(profile)),
        ]
    write_json(
        paths.claim(profile),
        {
            "schema": "litharness.epistemic-claim.v1",
            "claim_id": f"{VERSION}.{profile.name}",
            "statement": claim_statement(profile),
            "status": status,
            "artifacts": [
                {"kind": kind, "path": _rel(path, paths.root), "sha256": file_sha(path)}
                for kind, path in files
            ],
        },
    )


def request_identity(
    profile: Profile,
    planned: Sequence[Planned],
    paths: Paths,
    *,
    reader_factory: Callable[[Path], Any] | None = None,
) -> dict[str, Any] | None:
    """Call-free proof that this arm's v2-identical requests are v2's, byte for byte.

    The intact and sham cells at replicates 0 to 2 are replayed from v2's committed cache
    through a replay-only reader that cannot write, and must replay completely and reproduce
    v2's committed book means. That pins the extracted texts (whose path runs through
    `corpus_io` and `src/litharness/application/export.py`, not content-addressed), the seat,
    the competitors, the prompt, the sample indices and the transport's key to v2's. The cache
    is never loaded into this arm's reader. None for the Codex profile, whose keys differ.
    """
    if profile.positive_control:
        return None
    cells = [
        item for item in planned
        if item.cell.version in IDENTITY_VERSIONS and item.cell.replicate < IDENTITY_REPLICATES
    ]

    def replay_only(path: Path) -> Any:
        return ClaudeReader(path, model=profile.model, replay_only=True)

    with (reader_factory or replay_only)(paths.v2_raw) as reader:
        rows, status, _used = replay(profile, cells, reader)
    committed = json.loads(paths.v2_results.read_text(encoding="utf-8"))["reading"]["book_means"]
    means = book_means(rows, IDENTITY_VERSIONS)
    missing = sorted(feed for feed, state in status.items() if state == "missing")
    books = {item.cell.feed_index for item in cells}
    differences = [
        abs(means[book][version] - committed[book][version])
        for book in means for version in IDENTITY_VERSIONS
        if book in committed and version in committed[book]
    ]
    compared = len(differences) == len(means) * len(IDENTITY_VERSIONS)
    worst = max(differences) if differences else None
    return {
        "cells": len(cells),
        "replayed_complete": len(cells) - len(missing),
        "missing": missing[:12],
        "books": len(means),
        "max_abs_book_mean_diff": worst,
        "v2_raw_sha256": file_sha(paths.v2_raw),
        "v2_results_sha256": file_sha(paths.v2_results),
        "passed": bool(cells) and not missing and len(means) == len(books) and compared
        and worst is not None and worst <= 1e-12,
    }


def prepare(
    profile: Profile,
    *,
    paths: Paths = DEFAULT_PATHS,
    codex_binary: Path | None = None,
    texts_loader: Callable[[Path], tuple[list[tuple[str, str]], dict[str, str]]] = extract_texts,
    binary_reader: Callable[[Profile, Path | None], dict[str, Any]] = binary_info,
    identity_check: Callable[..., dict[str, Any] | None] = request_identity,
) -> dict[str, Any]:
    """Freeze the plan: texts (local), registration and claim.

    Refused once this arm has **bought** a cell (a cached answer, a fresh call in the ledger,
    or a reading): a probe-only invocation buys nothing, so a probe that failed, or a binary
    that updated while the arm waited for a usage window, can still be re-registered. Refused
    while the other profile holds the question, and for the Codex profile until the operator's
    approval record and a Codex attainability record exist.
    """
    bought = purchases(profile, paths)
    if bought["any"]:
        raise RuntimeError(
            f"{profile.arm} has bought cells ({bought}): a registration is never refreshed "
            "after a cell was bought"
        )
    fence(profile, paths)
    if profile.transport == "codex":
        for path in (paths.codex_approval, paths.codex_attainability):
            if not path.is_file():
                raise RuntimeError(
                    f"{_rel(path, paths.root)} is missing: the Codex arm is registered only "
                    "with the operator's approval record and its own attainability record "
                    "(BRIEF.md §5: size the batch against the reader you will seat)"
                )
    texts, store_hashes = texts_loader(paths.fitness_dir)
    identity = identity_check(profile, plan(texts, profile), paths)
    if identity is not None and not identity["passed"]:
        raise RuntimeError(
            f"request identity failed: {identity}; the texts, prompt or transport are not v2's, "
            "so nothing is registered"
        )
    texts_path = paths.texts(profile)
    write_json(texts_path, {"fitness": [list(pair) for pair in texts]})
    registration = build_registration(
        profile, texts, store_hashes, binary_reader(profile, codex_binary), paths,
        file_sha(texts_path), identity,
    )
    write_json(paths.registration(profile), registration)
    write_claim(profile, paths, "registered")
    return registration


# ----------------------------------------------------------------------------- verify


def _git(args: Sequence[str], root: Path) -> bytes:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, check=True
    ).stdout


def load_texts(profile: Profile, paths: Paths) -> list[tuple[str, str]]:
    payload = json.loads(paths.texts(profile).read_text(encoding="utf-8"))
    return [(str(name), str(text)) for name, text in payload["fitness"]]


def verify(
    profile: Profile,
    *,
    paths: Paths = DEFAULT_PATHS,
    git: Callable[[Sequence[str], Path], bytes] = _git,
    binary_reader: Callable[[Profile, Path | None], dict[str, Any]] | None = binary_info,
    check_lock: bool = False,
) -> tuple[dict[str, Any], list[Planned]]:
    """Refuse unless every frozen byte, the committed and pushed state and the binary match."""
    reg_path = paths.registration(profile)
    if not reg_path.is_file():
        raise RuntimeError(f"no registration at {_rel(reg_path, paths.root)}; run prepare")
    reg = json.loads(reg_path.read_text(encoding="utf-8"))
    if reg.get("registration_digest") != registration_digest(profile):
        raise RuntimeError("the registered constants differ from this module's")
    if not profile.positive_control and not (reg.get("request_identity") or {}).get("passed"):
        raise RuntimeError("the registration carries no passed request-identity check")
    for name, expected in reg["source_hashes"].items():
        path = paths.root / name
        if not path.is_file() or file_sha(path) != expected:
            raise RuntimeError(f"changed frozen file: {name}")
    texts_path = paths.texts(profile)
    if not texts_path.is_file() or file_sha(texts_path) != reg["inputs"]["texts_sha256"]:
        raise RuntimeError("the prepared texts are missing or changed")
    texts = load_texts(profile, paths)
    planned = plan(texts, profile)
    if manifest(planned) != reg["cells"]:
        raise RuntimeError("the rebuilt plan differs from the registered cells")
    for name in [_rel(reg_path, paths.root), *reg["source_hashes"]]:
        try:
            committed = git(["show", f"HEAD:{name}"], paths.root)
        except subprocess.CalledProcessError as error:
            raise RuntimeError(f"not committed: {name}") from error
        if committed != (paths.root / name).read_bytes():
            raise RuntimeError(f"not committed as registered: {name}")
    try:
        remote = git(["branch", "-r", "--contains", "HEAD"], paths.root)
    except subprocess.CalledProcessError as error:
        raise RuntimeError("cannot tell whether HEAD is pushed") from error
    if not remote.strip():
        raise RuntimeError("the registration commit is on no remote branch; push it first")
    if binary_reader is not None:
        codex = Path(reg["reader"]["binary"]) if profile.transport == "codex" else None
        now = binary_reader(profile, codex)
        for key in ("binary", "binary_sha256", "binary_version"):
            if now[key] != reg["reader"][key]:
                raise RuntimeError(f"the reader binary changed: {key}")
    if check_lock:
        holder = paths.lock_holder
        if not holder.is_file():
            raise RuntimeError("runs/box.lock is not held; take it (RUNBOOK) before a run")
        if not holder.read_text(encoding="utf-8-sig").startswith(LOCK_PREFIX):
            raise RuntimeError(f"runs/box.lock is held by someone else, not {LOCK_PREFIX}")
    return reg, planned


# --------------------------------------------------------------------------------- run


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def probe_names(profile: Profile) -> tuple[str, ...]:
    return ("agents_md",) if profile.transport == "codex" else ("claude_md", "git_status")


def probe_passed(name: str, record: dict[str, Any]) -> bool:
    """The house's comparison: the answer says NONE and does not carry the probe's leak mark."""
    text = str(record.get("text", ""))
    return "NONE" in text and PROBE_LEAK_MARKS[name] not in text


def _probe_in(directory: Path, system: str, model: str, cache: Path) -> dict[str, Any]:
    previous = Path.cwd()
    os.chdir(directory)
    try:
        with ClaudeReader(cache, model=model) as reader:
            record: dict[str, Any] = reader.ask_raw(
                system, [{"role": "user", "content": PROBE_PROMPT}], schema=None,
                max_tokens=16, tag={"stage": "isolation_probe"},
            )
            return record
    finally:
        os.chdir(previous)


def claude_probe(model: str) -> dict[str, dict[str, Any]]:
    """Two calls through the arm's own transport, one per leak path the house tests.

    `claude_md` asks from a directory holding a marker CLAUDE.md. `git_status` asks from a
    scratch git repository holding an untracked file named for the marker: the arm runs from
    the repository root, and a repository's status is the other context a tool-free completion
    must not inherit (`tests/test_providers.py`). Both run after the pin, on the copy the arm
    will run.
    """
    with tempfile.TemporaryDirectory(prefix="ctbm-probe-", ignore_cleanup_errors=True) as tmp:
        base = Path(tmp)
        marker = base / "claude_md"
        marker.mkdir()
        (marker / "CLAUDE.md").write_text(PROBE_MARKER, encoding="utf-8")
        repository = base / "git_status"
        repository.mkdir()
        subprocess.run(["git", "init", "--quiet", str(repository)], check=True,
                       capture_output=True)
        (repository / GIT_PROBE_FILE).write_text("context probe\n", encoding="utf-8")
        cache = base / "probe.jsonl"
        return {
            "claude_md": _probe_in(marker, PROBE_SYSTEM, model, cache),
            "git_status": _probe_in(repository, GIT_PROBE_SYSTEM, model, cache),
        }


def codex_provider(profile: Profile, binary: str, *, runner: Any = None) -> Any:
    from litharness.providers.codex_cli import CodexCliProvider, subprocess_runner

    return CodexCliProvider(
        model=profile.model,
        reasoning_effort=profile.effort or "low",
        binary=binary,
        runner=runner or subprocess_runner,
    )


def codex_probe(profile: Profile, binary: str, version: str) -> dict[str, dict[str, Any]]:
    """The same probe through the Codex adapter, with marker AGENTS.md and CLAUDE.md in its cwd."""
    from litharness.providers.codex_cli import subprocess_runner

    def marker_runner(argv: Sequence[str], **kwargs: Any) -> Any:
        if "exec" in argv:
            for name in ("AGENTS.md", "CLAUDE.md"):
                Path(kwargs["cwd"], name).write_text(PROBE_MARKER, encoding="utf-8")
        return subprocess_runner(argv, **kwargs)

    with tempfile.TemporaryDirectory(prefix="ctbm-probe-", ignore_cleanup_errors=True) as tmp:
        provider = codex_provider(profile, binary, runner=marker_runner)
        with CodexReader(Path(tmp) / "probe.jsonl", provider=provider, model=profile.model,
                         effort=profile.effort, cli_version=version) as reader:
            return {
                "agents_md": reader.ask_raw(
                    PROBE_SYSTEM, [{"role": "user", "content": PROBE_PROMPT}], schema=None,
                    max_tokens=16, tag={"stage": "isolation_probe"},
                )
            }


def open_reader(profile: Profile, paths: Paths, reg: dict[str, Any], *, replay_only: bool) -> Any:
    if profile.transport == "codex":
        binary = reg["reader"]["binary"]
        return CodexReader(
            paths.raw(profile),
            provider=PerThreadProvider(lambda: codex_provider(profile, binary)),
            model=profile.model,
            effort=profile.effort,
            cli_version=reg["reader"]["binary_version"],
            replay_only=replay_only,
        )
    return ClaudeReader(paths.raw(profile), model=profile.model, replay_only=replay_only)


def _stat_guard(path: Path) -> Callable[[], str | None]:
    """Between sessions: a stat, not a hash, of a 200 MB binary. A change halts the run."""
    first = path.stat()
    signature = (first.st_size, first.st_mtime_ns)

    def guard() -> str | None:
        now = path.stat()
        return None if (now.st_size, now.st_mtime_ns) == signature else "binary_changed"

    return guard


def _run_guard(pinned: Path | None, results: Path) -> Callable[[], str | None]:
    """Between sessions: halt on a changed binary, or on a reading written while buying."""
    binary = _stat_guard(pinned) if pinned is not None else None

    def guard() -> str | None:
        if results.exists():
            return "reading_exists"
        return binary() if binary is not None else None

    return guard


def run(
    profile: Profile,
    *,
    paths: Paths = DEFAULT_PATHS,
    verifier: Callable[..., tuple[dict[str, Any], list[Planned]]] = verify,
    reader_factory: Callable[..., Any] = open_reader,
    probe: Callable[[Profile, dict[str, Any]], dict[str, dict[str, Any]]] | None = None,
    guard: Callable[[], str | None] | None = None,
    pinner: Callable[[Profile, Paths, dict[str, Any]], Path] = pin_cli,
    workers: int = WORKERS,
    log: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Buy the plan under the lock. Refused once a reading exists.

    A second call resumes, **including after a kill**: bought calls replay free, only calls
    that obtained no answer are issued again, and the ceilings start from the larger of the
    ledger's totals and the raw cache's. The ledger gets a `started` line before the probes, a
    `probed` line, a `session` checkpoint after every session and a `finished` line; a process
    killed by PID or a shutdown loses at most the sessions in flight from the ledger, and none
    of their cached answers.
    """
    if paths.results(profile).exists():
        raise RuntimeError("a reading exists; no session is bought after it has been seen")
    reg, planned = verifier(
        profile, paths=paths, check_lock=True,
        # The Claude binary is checked through its pinned copy below, not where it was found:
        # once pinned, an update of the original changes nothing this arm runs.
        binary_reader=None if profile.transport == "cli" else binary_info,
    )
    fence(profile, paths)
    ledger_path = paths.ledger(profile)
    ledgers = read_ledgers(ledger_path)
    summaries = invocations(ledgers)
    raw = paths.raw(profile)
    if raw_totals(raw)["records"] and not any(s.get("started_at") for s in summaries):
        raise RuntimeError(f"{raw.name} holds answers but no invocation of this arm started")
    foreign = foreign_records(raw, profile)
    if foreign:
        raise RuntimeError(f"{foreign} record(s) in {raw.name} belong to no session of this arm")
    registration_sha = file_sha(paths.registration(profile))
    stale = [
        s["invocation"] for s in summaries
        if int(s.get("fresh_calls") or 0) and s.get("registration_sha256") != registration_sha
    ]
    if stale:
        raise RuntimeError(f"invocation(s) {stale} bought cells under another registration")
    prior = prior_usage(ledgers, raw)
    for name in ("calls", "tokens", "usd", "seconds"):
        limit = profile.limits.get(name)
        if limit is not None and float(prior.get(name, 0.0)) >= limit:
            raise RuntimeError(f"the {name} ceiling is already reached by earlier invocations")
    pinned: Path | None = None
    if profile.transport == "cli":
        # Belt and braces: the pinned copy is what runs, and this keeps it from updating itself.
        os.environ["DISABLE_AUTOUPDATER"] = "1"
        pinned = pinner(profile, paths, reg)
    number = max((int(s["invocation"]) for s in summaries if int(s["invocation"]) > 0),
                 default=0) + 1
    base = {
        "invocation": number,
        "registration_sha256": registration_sha,
        "binary_version": reg["reader"]["binary_version"],
    }
    append_ledger(ledger_path, {
        **base, "event": "started", "started_at": _now(), "pid": os.getpid(),
        "binary_pinned": str(pinned) if pinned is not None else None, "prior_usage": prior,
    })

    def used_now() -> dict[str, Any]:
        return {
            "used_cumulative": {k: float(prior.get(k, 0.0)) for k in ("calls", "tokens", "usd")},
            "seconds_cumulative": float(prior.get("seconds", 0.0)),
        }

    def finish(fields: dict[str, Any]) -> dict[str, Any]:
        line = {**base, "event": "finished", "finished_at": _now(), **fields}
        append_ledger(ledger_path, line)
        return line

    probe_fn = probe or _default_probe
    try:
        records = probe_fn(profile, reg)
    except ReaderHalt as error:
        records = {
            name: {"text": "", "stop_reason": f"{NOT_DISPATCHED}:halt:{error}", "usage": {}}
            for name in probe_names(profile)
        }
    except Exception as error:
        finish({"stop": f"probe_error:{type(error).__name__}", "complete": False,
                "fresh_calls": 0, **used_now()})
        raise
    probes: dict[str, dict[str, Any]] = {}
    for name, record in records.items():
        usage = record.get("usage") or {}
        stop = str(record.get("stop_reason") or "")
        probes[name] = {"text": str(record.get("text", ""))[:80], "stop_reason": stop,
                        "passed": probe_passed(name, record)}
        if not stop.startswith(NOT_DISPATCHED):
            prior["calls"] = float(prior.get("calls", 0.0)) + 1
        prior["tokens"] = float(prior.get("tokens", 0.0)) + _tokens(usage)
        prior["usd"] = float(prior.get("usd", 0.0)) + float(usage.get("equivalent_usd") or 0.0)
    failed = {name: p for name, p in probes.items() if not p["passed"]}
    if failed:
        # A probe that obtained no answer says nothing about isolation; one that answered
        # anything but NONE says the marker, or something else, reached the reader.
        leaked = any(
            not elicit._is_transport_failure(p["stop_reason"])
            and not p["stop_reason"].startswith(NOT_DISPATCHED)
            for p in failed.values()
        )
        why = "isolation_probe_failed" if leaked else "probe_transport_failure"
        finish({"probes": probes, "stop": why, "complete": False, "fresh_calls": 0,
                **used_now()})
        raise RuntimeError(f"{why.replace('_', ' ')}: {probes}; nothing bought")
    append_ledger(ledger_path, {**base, "event": "probed", "probes": probes, **used_now()})
    binary_guard = guard or _run_guard(pinned, paths.results(profile))
    ledger_lock = threading.Lock()
    with reader_factory(profile, paths, reg, replay_only=False) as reader:
        meter = Meter(reader, profile=profile, prior=prior, binary_guard=binary_guard)

        def checkpoint(session: dict[str, Any]) -> None:
            line = {**base, "event": "session", **session, **meter.snapshot()}
            with ledger_lock:
                append_ledger(ledger_path, line)

        log(
            f"{profile.arm}: {len(planned)} session(s), up to {len(planned) * feed_core.MAX_STEPS}"
            f" call(s) on {profile.model} via {profile.transport}; ceilings {profile.limits}"
        )
        try:
            _rows, outcome = run_plan(meter, planned, model=profile.model, workers=workers,
                                      log=log, on_session=checkpoint)
        except BaseException as error:
            finish({"probes": probes, **meter.snapshot(),
                    "stop": f"error:{type(error).__name__}", "complete": False})
            raise
    fields: dict[str, Any] = {"probes": probes, **outcome}
    if pinned is not None:
        fields["binary_sha256_at_end"] = file_sha(pinned)
    line = finish(fields)
    log(f"ledger: {json.dumps({k: v for k, v in line.items() if k != 'probes'})}")
    return line


def _default_probe(profile: Profile, reg: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if profile.transport == "codex":
        return codex_probe(profile, reg["reader"]["binary"], reg["reader"]["binary_version"])
    return claude_probe(profile.model)


def _refuse_while_held(paths: Paths) -> None:
    """A reading, or a close, never happens while this arm holds the box: a run may be live."""
    try:
        text = paths.lock_holder.read_text(encoding="utf-8-sig")
    except OSError:
        return
    if text.startswith(LOCK_PREFIX):
        raise RuntimeError(
            "runs/box.lock names this arm, so a run may be live; release the lock once the run "
            "process has ended (check it by PID), then try again"
        )


def close(profile: Profile, *, paths: Paths = DEFAULT_PATHS) -> dict[str, Any]:
    """Record the operator's decision that a killed invocation will not be resumed.

    Refused while the box lock names this arm, when the last invocation already finished, and
    once a reading exists. The closing line carries the larger of the ledger's and the raw
    cache's totals. A later `run` may still resume; only `analyse` is final.
    """
    if paths.results(profile).exists():
        raise RuntimeError("a reading exists; nothing is closed after it")
    _refuse_while_held(paths)
    ledgers = read_ledgers(paths.ledger(profile))
    if not ledgers:
        raise RuntimeError("no ledger: nothing to close")
    if finished(ledgers):
        raise RuntimeError("the last invocation finished: nothing to close")
    last = ledgers[-1]
    prior = prior_usage(ledgers, paths.raw(profile))
    line = {
        "event": "closed",
        "invocation": last.get("invocation"),
        "registration_sha256": last.get("registration_sha256"),
        "finished_at": _now(),
        "stop": "closed_after_interruption",
        "complete": False,
        "used_cumulative": {k: float(prior.get(k, 0.0)) for k in ("calls", "tokens", "usd")},
        "seconds_cumulative": float(prior.get("seconds", 0.0)),
    }
    append_ledger(paths.ledger(profile), line)
    return line


# ------------------------------------------------------------------------------ analyse


class _ReplayRecorder:
    """A replay-only reader that remembers which sessions asked for a call it did not hold."""

    def __init__(self, reader: Any) -> None:
        self.reader = reader
        self.missing: set[str] = set()
        self.used_keys: set[str] = set()

    def ask_raw(self, system: str, turns: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        record: dict[str, Any] = self.reader.ask_raw(system, turns, **kwargs)
        if record.get("stop_reason") == NOT_IN_CACHE:
            self.missing.add(str(kwargs["tag"]["feed"]))
        else:
            self.used_keys.add(str(record.get("key")))
        return record


def foreign_records(raw: Path, profile: Profile) -> int:
    """Records in this arm's cache that no session of this arm could have written.

    This arm's intact and sham requests are byte-identical to v2's at replicates 0 to 2, so a
    cache seeded from another arm's file would replay that arm's sessions as this one's. Every
    record here carries its session's feed id, so the check is exact.
    """
    if not raw.is_file():
        return 0
    prefix = f"{profile.tag}-"
    count = 0
    for line in raw.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not str(record.get("feed", "")).startswith(prefix):
            count += 1
    return count


def cached_failures(raw: Path) -> int:
    """Records in the cache that say no answer was obtained. §235: there must be none."""
    if not raw.is_file():
        return 0
    count = 0
    for line in raw.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if elicit._is_transport_failure(str(record.get("stop_reason") or "")):
            count += 1
    return count


def replay(
    profile: Profile, planned: Sequence[Planned], reader: Any
) -> tuple[list[ctb.Row], dict[str, str], set[str]]:
    """Every planned session rebuilt offline from the cache; no call can be made from here."""
    recorder = _ReplayRecorder(reader)
    rows: list[ctb.Row] = []
    status: dict[str, str] = {}
    for item in planned:
        cell = item.cell
        session = feed_session.run_feed_session(
            recorder, cell.spec, model=profile.model, rotation=cell.rotation,
            replicate=cell.replicate,
        )
        feed_id = cell.spec.feed_id
        if session.scorable:
            status[feed_id] = "scorable"
        elif feed_id in recorder.missing:
            status[feed_id] = "missing"
        else:
            status[feed_id] = "answered_unusable"
        rows.append(
            ctb.Row(
                feed_index=cell.feed_index,
                target_name=cell.target_name,
                version=cell.version,
                rotation=cell.rotation,
                pair_key=cell.pair_key,
                session=session,
                replicate=cell.replicate,
            )
        )
    return rows, status, recorder.used_keys


def transport_block(
    planned: Sequence[Planned],
    status: dict[str, str],
    ledgers: Sequence[dict[str, Any]],
    cached_failure_count: int,
    dispatched: set[str] | None = None,
) -> dict[str, Any]:
    """Read first, before any interval: what the transport did and what is missing.

    A missing session (a call the cache does not hold) is split by whether it was dispatched:
    one that was dispatched and ended on a failed call counts as unscorable in the scorable
    floor, v2's rule; one never dispatched is coverage and only stamps the reading partial.
    """
    dispatched = dispatched or set()
    summaries = invocations(ledgers)
    missing = [item.position for item in planned if status[item.cell.spec.feed_id] == "missing"]
    total = len(planned)
    tail = bool(missing) and missing == list(range(total - len(missing), total))
    never = [p for p in missing if planned[p].cell.spec.feed_id not in dispatched]
    reasons: Counter[str] = Counter()
    for summary in summaries:
        reasons.update(summary.get("failure_reasons") or {})
    counts = Counter(status.values())
    kept = ("invocation", "registration_sha256", "binary_version", "binary_pinned", "stop",
            "finished", "complete", "fresh_calls", "transport_failures", "not_dispatched",
            "sessions_completed", "used_cumulative", "seconds_cumulative")
    return {
        "invocations": len(summaries),
        "invocation_summaries": [{k: s.get(k) for k in kept} for s in summaries],
        "stops": [s.get("stop") if s["finished"] else "interrupted" for s in summaries],
        "fresh_calls_total": sum(int(s.get("fresh_calls") or 0) for s in summaries),
        "transport_failures_total": sum(int(s.get("transport_failures") or 0) for s in summaries),
        "not_dispatched_total": sum(int(s.get("not_dispatched") or 0) for s in summaries),
        "failure_reasons": dict(reasons),
        "cached_transport_failures": cached_failure_count,
        "sessions_planned": total,
        "sessions_dispatched": total - len(never),
        "sessions_scorable": counts.get("scorable", 0),
        "sessions_answered_unusable": counts.get("answered_unusable", 0),
        "sessions_missing": len(missing),
        "sessions_never_dispatched": len(never),
        "sessions_failed_in_flight": len(missing) - len(never),
        "missing_feed_ids": [planned[p].cell.spec.feed_id for p in missing],
        "missing_is_tail_block": tail,
        "coverage": "complete" if not missing else "partial",
        "probes": [s.get("probes") for s in summaries],
    }


def analyse(
    profile: Profile,
    *,
    paths: Paths = DEFAULT_PATHS,
    verifier: Callable[..., tuple[dict[str, Any], list[Planned]]] = verify,
    reader_factory: Callable[..., Any] = open_reader,
) -> dict[str, Any]:
    """The reading, once: transport first, then the preconditions, then the decision.

    Refused while the box lock names this arm or the last invocation has no finished line
    (it is running, or it was killed and neither resumed nor closed): no number is written
    while a run could still buy a cell (§222).
    """
    out = paths.results(profile)
    if out.exists():
        raise RuntimeError(f"{_rel(out, paths.root)} exists; a reading is written once")
    _refuse_while_held(paths)
    reg, planned = verifier(profile, paths=paths, binary_reader=None)
    raw = paths.raw(profile)
    if not raw.is_file():
        raise RuntimeError("no raw cache: nothing was bought")
    failures = cached_failures(raw)
    if failures:
        raise RuntimeError(
            f"{failures} transport failure(s) sit in the cache as answers (§235); no reading"
        )
    foreign = foreign_records(raw, profile)
    if foreign:
        raise RuntimeError(f"{foreign} record(s) in {raw.name} belong to no session of this arm")
    ledgers = read_ledgers(paths.ledger(profile))
    if not ledgers:
        raise RuntimeError("a raw cache with no ledger of this arm's invocations; no reading")
    if not finished(ledgers):
        raise RuntimeError(
            "the last invocation has no finished line: it is running, or it was killed; resume "
            "it with run, or record that it will not be resumed with close"
        )
    with reader_factory(profile, paths, reg, replay_only=True) as reader:
        rows, status, used = replay(profile, planned, reader)
        unused = len(reader.cached_keys() - used)
    dispatched = dispatched_feeds(ledgers, raw)
    counted = [
        row for row in rows
        if status[row.session.feed_id] != "missing" or row.session.feed_id in dispatched
    ]
    transport = transport_block(planned, status, ledgers, failures, dispatched)
    identity = None if profile.positive_control else (
        reg.get("request_identity") or {"passed": False}
    )
    read = reading(counted, profile, identity=identity)
    drift = None if profile.positive_control else reader_drift(rows, paths.v2_results)
    warnings = []
    if transport["coverage"] == "partial":
        warnings.append(
            f"partial: {transport['sessions_missing']} planned session(s) never answered "
            f"({transport['sessions_never_dispatched']} never dispatched); the reading is not a "
            "covered shelf"
        )
    if unused:
        warnings.append(f"{unused} cached record(s) no planned session asked for")
    pinned_hash = reg["reader"]["binary_sha256"]
    if any(s.get("binary_sha256_at_end") not in (None, pinned_hash)
           for s in invocations(ledgers)):
        warnings.append("the reader binary changed during a run")
    if any(s.get("halted") for s in invocations(ledgers)):
        warnings.append("an invocation halted: a call was refused mid-session")
    by_feed = {item.cell.spec.feed_id: item for item in planned}
    result = {
        "study": f"{VERSION}/{profile.arm}",
        "arm": profile.arm,
        "reader": reg["reader"],
        "registration_sha256": file_sha(paths.registration(profile)),
        "registration_digest": reg["registration_digest"],
        "raw_sha256": file_sha(raw),
        "ledger_sha256": file_sha(paths.ledger(profile)),
        "transport": transport,
        "reader_identity": {"request_identity": identity, "drift": drift},
        "reading": read,
        "warnings": warnings,
        "rows": [
            {
                "feed_id": row.session.feed_id,
                "book": row.target_name,
                "version": row.version,
                "replicate": row.replicate,
                "seed": by_feed[row.session.feed_id].seed,
                "status": status[row.session.feed_id],
                "dispatched": row.session.feed_id in dispatched
                or status[row.session.feed_id] != "missing",
                "session": asdict(row.session),
            }
            for row in rows
        ],
        "not_established": [
            "a quality instrument: the arm measures how a reader spends minutes",
            "QUALIFIED or any production authority",
            "any reader but this one model",
            "that this run's reader is the snapshot §230 measured: the requests are proven "
            "identical, the served model is not observed",
            "any shelf but twenty old house fitness books",
        ],
    }
    write_new(out, result)
    write_claim(profile, paths, "observed")
    return result


# ----------------------------------------------------------------------------- the CLI


def _print_plan(profile: Profile, planned: Sequence[Planned]) -> None:
    deviations = seed_deviations(planned)
    broken = plan_faults(planned)
    partial = [item.metrics for item in planned if item.metrics is not None]
    print(
        f"{profile.arm}: {len({item.cell.feed_index for item in planned})} book(s), "
        f"{len(planned)} session(s), at most {len(planned) * feed_core.MAX_STEPS} call(s)"
    )
    print(f"  seed deviations: {deviations or 'none'}")
    if partial:
        print(
            "  dose, mean over dosed copies: "
            + ", ".join(f"{k} {statistics.fmean(m[k] for m in partial):.4f}" for k in partial[0])
        )
    print(f"  faults: {broken or 'none'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "prepare", "run", "close", "analyse"))
    parser.add_argument("--reader", choices=tuple(PROFILES), default="claude")
    parser.add_argument("--codex-binary", type=Path, default=None,
                        help="codex profile: the native codex.exe, recorded and hashed")
    parser.add_argument("--workers", type=int, default=WORKERS)
    args = parser.parse_args(argv)
    profile = PROFILES[args.reader]
    if args.workers < 1 or args.workers > WORKERS:
        parser.error(f"--workers must be 1..{WORKERS}")
    if args.mode == "plan":
        texts, _ = extract_texts(FITNESS_DIR)
        _print_plan(profile, plan(texts, profile))
        return 0
    if args.mode == "prepare":
        registration = prepare(profile, codex_binary=args.codex_binary)
        print(json.dumps({k: registration["plan"][k] for k in ("books", "sessions", "max_calls",
                                                                 "seed_deviations")}, indent=2))
        print(f"request identity: {json.dumps(registration['request_identity'])}")
        print(f"wrote {_rel(DEFAULT_PATHS.registration(profile), ROOT)} and the claim; commit "
              "and push them before run")
        return 0
    if args.mode == "run":
        ledger = run(profile, workers=args.workers)
        return 0 if ledger.get("complete") else 2
    if args.mode == "close":
        print(json.dumps(close(profile), indent=2))
        return 0
    result = analyse(profile)
    print(json.dumps({"transport": result["transport"],
                      "decision": result["reading"]["decision"],
                      "preconditions": result["reading"]["preconditions"],
                      "target_read_share": result["reading"]["target_read_share"],
                      "warnings": result["warnings"]}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
