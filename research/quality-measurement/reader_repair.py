"""Does the panel share a human reader's taste, on the one defect that can be manufactured cleanly?

**The first run of this module is withdrawn; see §78.** `em_dash_strip` collapsed every blank line
in the passage it edited, so the arm compared a paragraphed text against an unparagraphed one and
its 0.0417 measured layout rather than punctuation. The transform is fixed and the arm re-elicits;
`results/reader-repair.json` and `results/reader-repair-opus.json` are frozen as the superseded
record and the corrected run writes `results/reader-repair-fixed.json`. Everything this docstring
says about the *design* stands — it is the two-sided pre-registration that made the withdrawal
legible instead of invisible, since a one-sided protocol would have banked the number as a finding.

A human read the first fully generated book on 2026-08-18 and named three defects. All three
measured true, and the important thing about them is what they are *not*: none is a degradation
of good prose. Every arm in `ablate.ALL` spoils something and the battery validates a panel on
telling the spoiled copy from the original — but a defect that sits in **both** copies is
invisible to that design however well the panel scores. The panel that cleared §70's detection
rung at 0.906 has never once been asked to find a defect a human actually found.

This module asks it. The em dash is the one named defect that can be manipulated in both
directions by a deterministic transform, so it is the only one that supports a clean single-
variable comparison, and this runs all three of its arms over the same ten scenes:

    em_dash_strip     the human's direction — 35 prose em dashes replaced by commas
    em_dash_inject    the opposite — the tell manufactured into text that lacked it
    rewhitespace      the sham floor — layout altered, not one character of any word

**The reading is two-sided and pre-registered, because every outcome here is informative.** It
would be easy to write this as "does the panel agree with the human", and then a disagreement
would read as a failed experiment rather than as the finding it would be. It is not a failed
experiment: a panel that prefers the em-dash-heavy text has the machine's taste, and that is the
single most consequential thing this project could learn about putting a simulated reader inside
the writing loop — it would mean the loop selects *for* the tell.

**The sham is not optional and the reason is measured.** §70's pairwise run reached detect 0.906
against a sham of 0.783, so most of what that panel separates is *edited-ness* rather than
damage. Both arms here are small edits to the same prose — 35 substitutions across 10,000
words, a length change of -0.30% — which is exactly the regime where an edited-ness detector
produces a confident number about nothing. `rewhitespace` bounds that, and any preference not
clearing it is not a preference about em dashes.

**System-voice spans are excluded from both arms, and that exclusion was measured rather than
assumed.** The first version turned `**TOLL PAID — 9 days**` into `**TOLL PAID, 9 days**` and
`[STATUS] wren — Level 2` into `[STATUS] wren, Level 2`, so a panel preferring the original would
have been reporting that it liked em dashes *or* that it liked unmangled stat blocks, with no way
to tell which. `ablate._PROTECTED` carries the fix; the human named a prose tell and those lines
are not prose.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from ablate import BY_KEY, em_dash_inject, em_dash_report, em_dash_strip  # noqa: E402
from corpus_io import generated_scenes  # noqa: E402
from elicit import PANEL_MODEL, Elicitor, positional_bias  # noqa: E402
from persona_battery import pairwise_interval  # noqa: E402

#: The three arms, each with the direction its win rate is read in. `expect` is what a panel
#: sharing the human's taste would do, written down before the run rather than after it.
ARMS: tuple[tuple[str, Any, str], ...] = (
    ("em_dash_strip", em_dash_strip, "above 0.5 — the human's direction"),
    ("em_dash_inject", em_dash_inject, "below 0.5 — the tell, added"),
    ("rewhitespace", BY_KEY["rewhitespace"].apply, "0.5 — the sham floor, layout only"),
)

#: Pre-registered before the first call. Every branch is named so that none of them can be
#: reported afterwards as the one that was expected.
PRE_REGISTRATION: dict[str, str] = {
    "precondition": (
        "positional bias within 0.40-0.60. Outside it the panel answered a side and the run "
        "says nothing about em dashes, exactly as gemma3:4b's two runs said nothing"
    ),
    "sham_floor": (
        "|rewhitespace rate - 0.5| must be smaller than |strip rate - 0.5|, or the preference "
        "is edited-ness detection and not a preference about the mark"
    ),
    "agrees": (
        "strip >= 0.60 and inject <= 0.40: the panel shares the human's taste and a reader "
        "model inside the writing loop would push against the tell"
    ),
    "opposes": (
        "strip <= 0.40 or inject >= 0.60: the panel has the machine's taste. This is the "
        "consequential branch — it would mean a reader in the loop selects FOR the tell, and "
        "the local-scale reading of §5a predicts exactly this (an em dash is the maximally "
        "locally-smooth punctuation, and the panel is sharp on local coherence)"
    ),
    "blind": (
        "both arms inside 0.40-0.60 with the sham floor cleared: the panel cannot see the "
        "defect at all, and the human read is doing work no instrument in this repo does"
    ),
}


def verdict(
    rates: dict[str, float],
    bias: dict[str, object],
    per_arm_bias: dict[str, dict[str, object]] | None = None,
) -> dict[str, object]:
    """The pre-registered branches, read in order. The precondition is read first, always.

    **The bias precondition is per-arm, and that is a correction made after the first run.** The
    pre-registration said "positional bias within 0.40-0.60" and the first implementation read it
    on the pooled comparisons, which is what §70's battery does. Pooling was wrong here and the
    first run showed why: the three arms differ enormously in how discriminable their pair is, so
    they carry wildly different bias — 0.486 on the strip, 0.857 on the inject, and 0.938 on a
    sham whose 79% tie rate leaves 16 decided comparisons to compute it from. The pooled 0.706
    voided a run in which the arm of interest was clean.

    **This change is post-hoc and it is recorded as post-hoc**, because that is the only thing
    that makes it readable. What licenses it is the direction: reading the precondition per arm
    *un-voids a result that goes against the instrument*, promoting an arm to a strong OPPOSES
    rather than rescuing a favourable number. A post-hoc rule that costs the panel its excuse is
    a different object from one that buys it a pass, and this ladder still refuses to call the
    result confirmed — `reader_repair` re-runs with the per-arm rule pre-registered, and the
    confirmation is that run rather than this reasoning.
    """
    per_arm_bias = per_arm_bias or {}

    def clean(arm: str) -> bool:
        value = per_arm_bias.get(arm, {}).get("chose_A_rate")
        return isinstance(value, float) and 0.40 <= value <= 0.60

    readable = [arm for arm, _, _ in ARMS if clean(arm)]
    if not readable:
        return {
            "verdict": "VOID",
            "why": "no arm cleared the per-arm positional-bias precondition",
            "per_arm_bias": {a: per_arm_bias.get(a, {}).get("chose_A_rate") for a, _, _ in ARMS},
            "conditions": PRE_REGISTRATION,
        }

    strip = rates.get("em_dash_strip", 0.5)
    inject = rates.get("em_dash_inject", 0.5)
    sham = rates.get("rewhitespace", 0.5)
    if abs(sham - 0.5) >= abs(strip - 0.5):
        return {
            "verdict": "VOID",
            "why": (
                f"sham moves {abs(sham - 0.5):.4f} from indifference and strip moves "
                f"{abs(strip - 0.5):.4f}; this is edited-ness, not em dashes"
            ),
            "conditions": PRE_REGISTRATION,
        }

    if "em_dash_strip" not in readable:
        return {
            "verdict": "VOID",
            "why": "the strip arm failed its own positional-bias precondition",
            "readable_arms": readable,
            "conditions": PRE_REGISTRATION,
        }

    if strip >= 0.60 and inject <= 0.40:
        outcome, why = "AGREES", "the panel shares the human's taste on the mark"
    elif strip <= 0.40 or inject >= 0.60:
        outcome, why = "OPPOSES", "the panel prefers the tell; a reader in the loop selects for it"
    elif 0.40 < strip < 0.60 and 0.40 < inject < 0.60:
        outcome, why = "BLIND", "the panel cannot see the defect a human found in one read"
    else:
        outcome, why = "SPLIT", "the two arms disagree; neither branch is supported"
    return {
        "verdict": outcome,
        "why": why,
        "readable_arms": readable,
        "voided_arms": [arm for arm, _, _ in ARMS if arm not in readable],
        "conditions": PRE_REGISTRATION,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    units = generated_scenes(args.book_db, book=args.book, min_words=args.min_words)
    units = units[: args.scenes]
    if len(units) < 2:
        raise SystemExit(f"need at least 2 scenes, got {len(units)}")

    planned = len(units) * len(ARMS) * 4 * 2
    if planned > args.guard and not args.yes:
        raise SystemExit(f"{planned} calls exceeds the {args.guard} guard; pass --yes")

    report: dict[str, Any] = {
        "book_db": str(args.book_db),
        "scenes": [unit.unit_id for unit in units],
        "panel_model": args.model,
        "transport": args.transport,
        "tie_policy": args.tie_policy,
        "planned_calls": planned,
        "protocol": "plan/stage-0-decisions.md §74",
    }

    # What the transform did to the prose, reported beside the preference so "the panel preferred
    # the repair" and "the panel preferred 0.3% less text" stay distinguishable.
    edits = [em_dash_report(unit.text, em_dash_strip(unit.text, 1.0)) for unit in units]
    report["transform"] = {
        "em_dashes_before": sum(e["em_dashes_before"] for e in edits),
        "em_dashes_after": sum(e["em_dashes_after"] for e in edits),
        "prose_dashes_replaced": sum(
            e["em_dashes_before"] - e["em_dashes_after"] for e in edits
        ),
        "word_delta_pct": round(statistics.fmean(e["word_delta_pct"] for e in edits), 3),
        "possible_comma_splices": sum(e["possible_comma_splices"] for e in edits),
        "note": "dashes remaining are inside protected system-voice spans; see ablate._PROTECTED",
    }

    every: list[Any] = []
    per_arm: dict[str, list[float]] = {key: [] for key, _, _ in ARMS}
    with Elicitor(
        Path(args.cache), model=args.model, spot_model=None, spot_fraction=0.0,
        transport=args.transport, pair_question=args.pair_question, dry_run=args.dry_run,
    ) as elicitor:
        for unit in units:
            for key, transform, _expect in ARMS:
                variant = transform(unit.text, 1.0)
                if variant.strip() == unit.text.strip():
                    # An unchanged variant would be the original compared with itself and score
                    # 0.5 by construction, which is a manufactured tie rather than a measurement.
                    continue
                pair_id = f"{unit.unit_id}|{key}"
                comparisons = elicitor.compare_pair(pair_id, unit.text, variant, n=1)
                every.extend(comparisons)
                scored = [c for c in comparisons if not c.refused]
                values = [
                    0.5 if c.choice == "neither" else float(c.chose_variant)
                    for c in scored
                    if not (c.choice == "neither" and args.tie_policy == "drop")
                ]
                if values:
                    per_arm[key].append(statistics.fmean(values))
            print(f"  {unit.unit_id}: {len(every)} comparisons", file=sys.stderr, flush=True)

        rates = {
            key: round(statistics.fmean(values), 4)
            for key, values in per_arm.items() if values
        }
        report["win_rates"] = rates
        report["expectations"] = {key: expect for key, _, expect in ARMS}
        report["positional_bias"] = positional_bias(every)
        report["intervals"] = {
            key: pairwise_interval(
                [c for c in every if c.pair_id.endswith(f"|{key}")], args.model, args.tie_policy
            )
            for key in rates
        }
        report["refused"] = sum(1 for c in every if c.refused)
        report["comparisons"] = len(every)
        report["per_arm_bias"] = {
            key: positional_bias([c for c in every if c.pair_id.endswith(f"|{key}")])
            for key, _, _ in ARMS
        }
        report["ladder"] = verdict(rates, report["positional_bias"], report["per_arm_bias"])
        report["spend"] = elicitor.spend()
        report["api_calls"] = elicitor.api_calls
        report["replayed"] = elicitor.replayed
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--book-db", default=str(HERE / "corpora" / "toll.db"))
    parser.add_argument("--book")
    parser.add_argument("--min-words", type=int, default=500)
    parser.add_argument("--scenes", type=int, default=10)
    parser.add_argument("--model", default=PANEL_MODEL)
    parser.add_argument("--transport", default="cli", choices=("cli", "sdk", "ollama"))
    parser.add_argument(
        "--pair-question", default="preference", choices=("preference", "intensity")
    )
    parser.add_argument("--tie-policy", default="half_win", choices=("half_win", "drop"))
    parser.add_argument("--guard", type=int, default=300)
    parser.add_argument("--cache", default=str(HERE / "results" / "reader-repair-raw.jsonl"))
    parser.add_argument("--out", default=str(HERE / "results" / "reader-repair.json"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)

    report = run(args)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report["win_rates"], indent=2))
    print(json.dumps(report["positional_bias"], indent=2))
    print(json.dumps({k: v for k, v in report["ladder"].items() if k != "conditions"}, indent=2))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
