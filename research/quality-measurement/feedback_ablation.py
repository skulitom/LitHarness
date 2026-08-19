"""The reader → writer loop's own ablation: same beats, same seeds, feedback on versus off.

**Stated before it runs, and sized to the n that exists rather than the n we would like.**
`PRE_REGISTRATION` below is committed before any arm is generated. The comparison, the arms,
the direction each counter is expected to move and the conditions under which the whole thing
is reported dead are all written down first, because the alternative is choosing the reading
after seeing the numbers — which is the failure `plan/stage-0-decisions.md` catalogues more
often than any other.

**Four arms, because two would not say which half did the work.**

    off           no feedback in the system message. The control.
    reader_only   standing directions only. No located judge items.
    judge_only    located items only, on axes whose direction exists but is not stated.
    both          the full loop.

Ablating the two sources separately is invariant I6 and it is not optional: with only `off`
against `both`, a separation says the loop does something and nothing about which half, and
the two halves have very different prices — a reader verdict is bought and a judge call is not.

**Two readouts, and only one of them is runnable today.**

- **Machine-side, at zero readers and zero spend.** The deterministic counter on each target
  axis, per arm, with the direction of expected movement pre-registered; plus every *other*
  registered counter, which is the single-variable check; plus word-count ratio and layout
  identity, which is §78's confound — a 96-100% preference produced by layout alone. An
  on-target move that rides a drifted certificate is reported as **drift, never as effect**,
  and the two are never summed into one number. This half can falsify the wiring on its own:
  if feedback-on does not move the counter, the feedback never reached the prose and the
  reader-side arm is not worth buying.
- **Reader-side, blocked.** Blinded, position-swapped pairs between arms, under a declared
  steering protocol. `audit_samples` is at 0 rows and no reader has been paid, so this reads
  **UNDECIDABLE — awaiting N verdicts** and prints the attainability table beside it. It is
  not sized for a hoped-for n; it says what n it has.

**What a `--wiring` run is and is not.** It drives the real loop through the padded fake
provider with a *synthetic* direction, so it can show that the feedback text reached the frozen
payload and that the counters moved or did not. It is a wiring pilot and not a test, which is
§61's own distinction for Add 2: twenty-four scenes can show effect direction and cannot show
prediction at any confidence worth recording. Nothing it prints is evidence about prose.

Local, deterministic, no quota unless `--live` is passed. Runs under `uv run python`.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))

from litharness.domain import axes as axes_mod  # noqa: E402
from litharness.domain.directions import (  # noqa: E402
    DIRECTION_BAR,
    MIN_CELLS,
    MIN_PAIR_CLUSTERS,
    MIN_READER_CLUSTERS,
    TARGET_POWER,
    attainability,
)

RESULTS = HERE / "results"

ARMS: tuple[str, ...] = ("off", "reader_only", "judge_only", "both")

#: How far a counter has to move, in ratio terms, before the run calls it movement rather than
#: noise. A placed number and labelled as one — nothing has measured a generator's counter noise
#: across seeds, and `--wiring` is what measures it. It exists so the reading is declared before
#: the numbers rather than chosen after them.
MOVEMENT_RATIO = 0.15

#: Word-count and layout drift beyond which an on-target move is reported as drift instead.
#: §78 measured a 96-100% preference produced by layout alone, and §85's certificates put the
#: same guard on a single-variable operator; this is that guard moved one instrument over.
DRIFT_WORD_RATIO = 0.10

PRE_REGISTRATION: dict[str, Any] = {
    "written": (
        "2026-08-19, before any arm was generated and before any counter was read"
    ),
    "question": (
        "Does feedback materialised into the draft prompt move the prose on the axis it "
        "names, and which of the two sources does the moving?"
    ),
    "arms": list(ARMS),
    "held_fixed": [
        "the beat sheet and the book premise",
        "the sampler seed, which is derived from the job's input digest and attempt",
        "the provider and the model",
        "the context packet's token budget",
    ],
    "machine_side": {
        "primary": (
            "the target axis's counter, per arm, against the `off` arm. Movement is a ratio "
            f"of at least {MOVEMENT_RATIO} toward the direction the feedback names."
        ),
        "off_target": (
            "every other registered counter, reported beside the primary. A feedback item "
            "names one axis; a move on the others is the loop doing something it did not say."
        ),
        "drift": (
            "word-count ratio and layout identity. An on-target move that rides a drifted "
            f"certificate (word ratio beyond {DRIFT_WORD_RATIO}) is reported as DRIFT and "
            "never as effect — §78's confound, which produced a 96-100% preference from "
            "layout alone."
        ),
        "reads": [
            "MOVED — the target counter moved past the ratio, in the named direction, with "
            "no drift and no larger off-target move",
            "DRIFT — it moved and so did length or layout; the gain is not attributable",
            "OFF_TARGET — another counter moved further than the target one",
            "NULL — no arm moved its target counter past the ratio",
            "INERT_GENERATOR — every arm's counters are identical to the control's on every "
            "axis. The generator did not respond to any instruction, so the run says nothing "
            "about the loop and its NULL must not be read as one. §57's lesson: a run sized "
            "for the wrong question does not get a second chance to answer the right one.",
        ],
    },
    "reader_side": {
        "protocol": (
            "blinded, position-swapped pairs between arms under a declared steering "
            "protocol, judged by steering-pool readers only"
        ),
        "bar": (
            f"the clustered lower bound on the arm's win rate exceeds {DIRECTION_BAR} at the "
            "declared floors"
        ),
        "state": (
            "UNDECIDABLE until the floors are met. `audit_samples` is at 0 rows and no reader "
            "has been paid, so this arm has no n and says so rather than reporting a number "
            "from what it has."
        ),
    },
    "kill_conditions": [
        "The machine side reads NULL on every arm: the feedback never reached the prose, and "
        "the reader-side arm is not worth buying. Archive beside refuted_metrics.py.",
        "The machine side reads DRIFT: the loop moves length or layout rather than the axis, "
        "which is §78's finding recurring and is reported as such.",
        "The reader side, once it has n, shows no separation between `off` and `both`: the "
        "loop does not work and the entry says so.",
        "The reader side separates `off` from `both` but not `off` from `judge_only` once "
        "`reader_only` is held fixed: that is a finding about JUDGES and belongs in "
        "plan/judge-validity-program.md, not here.",
    ],
    "not_claimed": (
        "Nothing here is evidence that revised prose is better prose. The counters are "
        "surface proxies and a move on one is a move on a proxy; §61's paid pairwise "
        "judgment is the only instrument that can say better, and it is not this."
    ),
}


# --------------------------------------------------------------------------- scoring


def counters(text: str) -> dict[str, float]:
    return axes_mod.counts(text)


def layout_signature(text: str) -> tuple[int, int, int]:
    """Paragraph count, line count, and trailing-whitespace count.

    The cheapest thing that changes when a generator reformats rather than rewrites, which is
    the confound §78 measured at a 96-100% preference produced by layout alone.
    """
    return (
        len([block for block in text.split("\n\n") if block.strip()]),
        len(text.splitlines()),
        sum(1 for line in text.splitlines() if line != line.rstrip()),
    )


def arm_profile(texts: list[str]) -> dict[str, Any]:
    """One arm's measured profile: every counter, its length, and its layout."""
    joined = "\n\n".join(texts)
    return {
        "scenes": len(texts),
        "words": sum(len(text.split()) for text in texts),
        "counters": counters(joined),
        "layout": list(layout_signature(joined)),
    }


def _ratio(after: float, before: float) -> float:
    """Signed movement of `after` against `before`, normalised by `before`.

    A `before` of zero is the common case for `em_per_1k` on prose that has none, so the
    normaliser falls back to 1.0 rather than dividing by zero — which makes the ratio an
    absolute difference exactly where a relative one is undefined, and the reading says so.
    """
    base = abs(before) if before else 1.0
    return (after - before) / base


def compare(profiles: dict[str, dict[str, Any]], axis_id: str, toward: str) -> dict[str, Any]:
    """One axis's reading across the arms, against `off`, with the confound in the same pass."""
    control = profiles.get("off")
    if control is None:
        return {"axis": axis_id, "read": "NO_CONTROL"}
    sign = 1.0 if toward == "high" else -1.0
    rows: dict[str, Any] = {}
    for arm, profile in profiles.items():
        if arm == "off":
            continue
        target = sign * _ratio(
            profile["counters"][axis_id], control["counters"][axis_id]
        )
        off_target = {
            other: _ratio(profile["counters"][other], control["counters"][other])
            for other in profiles[arm]["counters"]
            if other != axis_id
        }
        word_drift = _ratio(profile["words"], control["words"])
        layout_moved = profile["layout"] != control["layout"]
        if abs(word_drift) > DRIFT_WORD_RATIO or layout_moved:
            read = "DRIFT"
        elif target < MOVEMENT_RATIO:
            read = "NULL"
        elif any(abs(value) > abs(target) for value in off_target.values()):
            read = "OFF_TARGET"
        else:
            read = "MOVED"
        rows[arm] = {
            "target_ratio": round(target, 4),
            "off_target": {k: round(v, 4) for k, v in off_target.items()},
            "word_drift": round(word_drift, 4),
            "layout_moved": layout_moved,
            "read": read,
        }
    inert = all(
        profile["counters"] == control["counters"]
        for arm, profile in profiles.items()
        if arm != "off"
    )
    overall = (
        "INERT_GENERATOR"
        if inert
        else "MOVED"
        if any(row["read"] == "MOVED" for row in rows.values())
        else "DRIFT"
        if any(row["read"] == "DRIFT" for row in rows.values())
        else "OFF_TARGET"
        if any(row["read"] == "OFF_TARGET" for row in rows.values())
        else "NULL"
    )
    return {"axis": axis_id, "toward": toward, "arms": rows, "read": overall}


# --------------------------------------------------------------------------- reader side


def reader_side(decided_cells: int, readers: int, pairs: int) -> dict[str, Any]:
    """The reader-side reading at the n that exists, with the attainability beside it.

    **This is the half that is honest about being blocked.** It reports the floors it has not
    met rather than a number computed from what it has, because a bound over four judgments is
    the thing §59 measured reading as a confident 0.82 and bounding at 0.566.
    """
    report = attainability()
    unmet = []
    if decided_cells < MIN_CELLS:
        unmet.append(f"decided cells {decided_cells} < {MIN_CELLS}")
    if readers < MIN_READER_CLUSTERS:
        unmet.append(f"reader clusters {readers} < {MIN_READER_CLUSTERS}")
    if pairs < MIN_PAIR_CLUSTERS:
        unmet.append(f"pair clusters {pairs} < {MIN_PAIR_CLUSTERS}")
    return {
        "verdict": "UNDECIDABLE" if unmet else "READABLE",
        "unmet": unmet,
        "have": {"cells": decided_cells, "readers": readers, "pairs": pairs},
        "attainability": {
            "smallest_clearing_k": report.smallest_clearing_k,
            "cells": report.cells,
            "power": {str(k): round(v, 4) for k, v in report.power.items()},
            "cells_for_power": {
                str(k): v for k, v in report.cells_for_power.items()
            },
            "target_power": TARGET_POWER,
        },
        "note": (
            "The floor is a coherence floor, not a sample size. At a true win rate of 0.60 "
            "the floor fires under a tenth of the time, so a null from thirty judgments would "
            "say nothing about the loop."
        ),
    }


# --------------------------------------------------------------------------- the wiring pilot


BOOK_PREMISE = "A debtor works off an impossible debt along a System-governed road."
SEED_STATE = {
    "records": [
        {
            "subject": "wren",
            "predicate": "level",
            "value": "2",
            "story_position": "s0",
        }
    ]
}


def _cli(database: Path, *args: str) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["LITHARNESS_ENV"] = "test"
    environment["LITHARNESS_FAKE_PAD_CHARS"] = "600"
    return subprocess.run(
        [sys.executable, "-m", "litharness", "--database", str(database), *args],
        capture_output=True,
        text=True,
        cwd=str(REPO),
        env=environment,
        check=False,
    )


def _seed_direction(database: Path, axis_id: str, toward: str) -> None:
    """Put one synthetic direction in the store so the judge half is not inert.

    **Synthetic, and that is why this is a wiring pilot rather than a test.** A real direction
    comes from steering-pool readers and there are none; this one is written directly so the
    plumbing downstream of a direction can be exercised at all. Nothing measured here is
    evidence about readers, and the arm labels say so.
    """
    from litharness.adapters.sqlite_store import SqliteStore
    from litharness.application.feedback_loop import current_digests
    from litharness.domain.axes import Pole
    from litharness.domain.directions import AxisDirection

    store = SqliteStore.open(database)
    try:
        # The digest of the verdict set *as it stands*, so the seeded direction is live rather
        # than stale on arrival. A direction whose evidence has moved emits nothing (§72's
        # expiry-on-use), and with no verdicts at all "as it stands" is the digest of nothing —
        # which is exactly what a real direction established from an empty pool would carry.
        digest = current_digests(store)[axis_id]
        store.record_axis_direction(
            AxisDirection(
                axis_id=axis_id,
                preferred=Pole(toward),
                high_win_rate=0.7 if toward == "high" else 0.3,
                lower_bound=0.61,
                alpha=0.05,
                cells=MIN_CELLS,
                readers=MIN_READER_CLUSTERS,
                pairs=MIN_PAIR_CLUSTERS,
                verdicts_digest=digest,
                established_at="2026-08-19",
                note="SYNTHETIC: a wiring pilot's direction, not a reader measurement",
            )
        )
    finally:
        store.close()


def wiring_run(scenes: int, axis_id: str) -> dict[str, Any]:
    """Drive the real loop once per arm and report what reached the payload and the prose.

    Same beats and same premise in every arm; the sampler seed is derived from the job's input
    digest, so the arms differ exactly where the prompt differs — which is the point, and also
    the caveat: a changed prompt changes the seed, so "same seed" here means "same derivation",
    not "same sample path". That is stated rather than glossed, because it is the one thing an
    ablation over a seeded generator cannot hold fixed while changing the prompt.
    """
    from litharness.adapters.sqlite_store import SqliteStore
    from litharness.domain.nodes import NodeKind

    axis = axes_mod.AXES[axis_id]
    toward = axis.hypothesis.value
    out: dict[str, Any] = {"axis": axis_id, "toward": toward, "arms": {}}
    profiles: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory() as workspace:
        for arm in ARMS:
            database = Path(workspace) / f"{arm}.db"
            _cli(database, "init")
            _cli(
                database, "new", "The Toll Road", "--premise", BOOK_PREMISE,
                "--scenes", str(scenes),
            )
            _cli(database, "pools", "--register", "--note", f"ablation arm {arm}")
            if arm in {"reader_only", "both"}:
                _seed_direction(database, axis_id, toward)
            for _ in range(scenes * 6):
                result = _cli(database, "tick")
                if "no_work" in result.stdout:
                    break
            store = SqliteStore.open(database)
            try:
                branches = store.branches()
                texts: list[str] = []
                carried = 0
                if branches:
                    revision = store.load_revision(branches[0][2])
                    texts = [
                        node.content
                        for node in revision.in_reading_order()
                        if node.kind is NodeKind.SCENE and node.content
                    ]
                    carried = sum(
                        1 for row in store.scene_feedback() if row.items
                    )
            finally:
                store.close()
            profiles[arm] = arm_profile(texts)
            out["arms"][arm] = {
                "profile": profiles[arm],
                "scenes_with_feedback": carried,
            }
    out["comparison"] = compare(profiles, axis_id, toward)
    out["reader_side"] = reader_side(0, 0, 0)
    # **What the `judge_only` arm carried, said out loud.** A judge batch needs a tournament
    # (`--plan-search`) and a licensed judge call; this pilot runs neither, so that arm is
    # currently identical to the control by construction rather than by measurement. Reporting
    # it as a plain NULL would let a reader take "the judge half does nothing" from a run that
    # never asked the judge anything.
    out["judge_arm"] = (
        "NOT_EXERCISED: this pilot runs no tournament, so `judge_only` carried no located "
        "difference and is the control under another name. Exercising it needs --plan-search "
        "and a judge batch, which is a live run."
    )
    return out


# --------------------------------------------------------------------------- selftest


def selftest() -> int:
    """The arithmetic, offline, on synthetic profiles. Ten claims, each able to fail.

    Every research module here that skipped this shipped a defect its dry run would have
    caught, so the scorer is exercised on constructed inputs before it is pointed at prose.
    """
    failures: list[str] = []

    def check(claim: str, ok: bool) -> None:
        if not ok:
            failures.append(claim)

    base = {
        "scenes": 3,
        "words": 300,
        "counters": {"stat_flatten": 10.0, "interiority": 20.0, "em_dash": 5.0},
        "layout": [3, 6, 0],
    }

    def variant(**counter_moves: float) -> dict[str, Any]:
        row = json.loads(json.dumps(base))
        row["counters"].update(counter_moves)
        return row

    moved = compare({"off": base, "both": variant(interiority=30.0)}, "interiority", "high")
    check("a clean on-target move reads MOVED", moved["read"] == "MOVED")

    wrong_way = compare({"off": base, "both": variant(interiority=10.0)}, "interiority", "high")
    check("a move the wrong way is not a move", wrong_way["read"] == "NULL")

    low = compare({"off": base, "both": variant(em_dash=1.0)}, "em_dash", "low")
    check("a LOW axis reads its own direction", low["read"] == "MOVED")

    off_target = compare(
        {"off": base, "both": variant(interiority=24.0, em_dash=40.0)},
        "interiority",
        "high",
    )
    check("a bigger off-target move reads OFF_TARGET", off_target["read"] == "OFF_TARGET")

    drifted = variant(interiority=30.0)
    drifted["words"] = 400
    drift = compare({"off": base, "both": drifted}, "interiority", "high")
    check("length drift is reported as drift, never as effect", drift["read"] == "DRIFT")

    relaid = variant(interiority=30.0)
    relaid["layout"] = [4, 8, 0]
    layout = compare({"off": base, "both": relaid}, "interiority", "high")
    check("layout drift is reported as drift too (§78)", layout["read"] == "DRIFT")

    flat = compare({"off": base, "both": variant()}, "interiority", "high")
    check(
        "a generator that produced identical counters everywhere reads INERT_GENERATOR "
        "rather than NULL, so a fake provider's flat run is not mistaken for a finding",
        flat["read"] == "INERT_GENERATOR",
    )
    half_flat = compare(
        {"off": base, "reader_only": variant(), "both": variant(em_dash=9.0)},
        "interiority",
        "high",
    )
    check("one arm moving somewhere is not inert", half_flat["read"] != "INERT_GENERATOR")

    zero_base = dict(base, counters={"stat_flatten": 0.0, "interiority": 0.0, "em_dash": 0.0})
    from_zero = compare(
        {"off": zero_base, "both": dict(zero_base, counters={
            "stat_flatten": 0.0, "interiority": 1.0, "em_dash": 0.0,
        })},
        "interiority",
        "high",
    )
    check("a zero baseline does not divide by zero", from_zero["read"] in {"MOVED", "NULL"})

    blocked = reader_side(0, 0, 0)
    check("with no verdicts the reader side is UNDECIDABLE", blocked["verdict"] == "UNDECIDABLE")
    check("and it names every floor it has not met", len(blocked["unmet"]) == 3)

    check(
        "the pre-registration names a kill condition for the judge half specifically",
        any("judge_only" in line for line in PRE_REGISTRATION["kill_conditions"]),
    )
    check(
        "and the arms ablate the two sources separately",
        set(ARMS) == {"off", "reader_only", "judge_only", "both"},
    )

    for line in failures:
        print(f"FAIL  {line}")
    print(f"selftest: {'PASS' if not failures else 'FAIL'} ({len(failures)} failure(s))")
    return 1 if failures else 0


# --------------------------------------------------------------------------- entry point


def render(report: dict[str, Any]) -> None:
    comparison = report.get("comparison", {})
    print(f"axis {comparison.get('axis')}  toward {comparison.get('toward')}")
    print(f"{'arm':<12} {'target':>9} {'words':>8} {'layout':>7}  read")
    for arm, row in comparison.get("arms", {}).items():
        print(
            f"{arm:<12} {row['target_ratio']:>9.4f} {row['word_drift']:>8.4f} "
            f"{row['layout_moved']!s:>7}  {row['read']}"
        )
    print(f"overall: {comparison.get('read')}")
    for arm, row in report.get("arms", {}).items():
        print(f"  {arm:<12} {row['scenes_with_feedback']} scene(s) carried feedback")
    if report.get("judge_arm"):
        print(f"  judge arm: {report['judge_arm']}")
    reader = report.get("reader_side", {})
    print(f"reader side: {reader.get('verdict')}  unmet: {', '.join(reader.get('unmet', []))}")
    sizing = reader.get("attainability", {}).get("cells_for_power", {})
    if sizing:
        print(
            "  cells for "
            f"{reader['attainability']['target_power']:.0%} power: "
            + "  ".join(f"{rate}->{cells}" for rate, cells in sizing.items())
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true", help="the arithmetic, offline")
    parser.add_argument(
        "--plan", action="store_true", help="print the pre-registration and stop"
    )
    parser.add_argument(
        "--wiring",
        action="store_true",
        help="drive the real loop through the padded fake provider: a wiring pilot, not a test",
    )
    parser.add_argument(
        "--scenes",
        type=int,
        default=6,
        help="six is the floor: `arc_template` refuses to name its beats on fewer",
    )
    parser.add_argument("--axis", default="interiority", choices=sorted(axes_mod.AXES))
    parser.add_argument("--out", type=Path, default=RESULTS / "feedback-ablation.json")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.plan or not args.wiring:
        print(json.dumps(PRE_REGISTRATION, indent=2))
        blocked = reader_side(0, 0, 0)
        print(json.dumps(blocked, indent=2))
        return 0

    report = wiring_run(args.scenes, args.axis)
    report["pre_registration"] = PRE_REGISTRATION
    report["kind"] = "wiring pilot, not a test: synthetic direction, fake provider"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    render(report)
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
