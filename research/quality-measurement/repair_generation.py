"""The repair direction, generated: the first attempt to remove the defects a human named.

Everything before this ran in the damage direction. `ablate.py` manufactures defects into good
prose; §80's class-B pairs put manufactured damage to paid readers; §78's em-dash arms compared
the original against a comma *substitution* — and §78.2's OPPOSES branch names the problem with
that: a mechanical swap may itself degrade the sentence, so a preference for the original never
cleanly separates "likes the dash" from "dislikes the comma splice". Meanwhile `personas.py`'s
own reason-code contract has been waiting on this module since §70: *"a code is valid only if a
repair aimed at it moves the verdict."* No repair has ever existed to aim. The book still writes
exactly as it did when §74's reader put it down.

This module generates repairs — the author revising his own pages, one named defect per arm,
minimally:

    repair_emdash        every prose em dash removed by REWRITING the sentence so it no longer
                         needs one, never by swapping punctuation. §78.2's substitution artifact
                         is designed out rather than controlled for.
    repair_interiority   inner experience added where the prose reports a body without what it
                         is like from inside — §74's second defect, repaired in the register the
                         scene already has.
    repair_placebo       the floor: an inert revision instruction (fix any typos). Whatever a
                         minimal revision pass does on its own — drift, house-style creep,
                         unprompted "improvements" — shows up here, and no repair arm is read
                         except against it. §83's tea arm, rebuilt for the revision operation.
    exemplar             the register probe riding along: a retell conditioned on two
                         high-interiority human excerpts as VOICE, not instructions. §83 closed
                         the described-state channel; this opens the demonstrated-voice one.
                         Judged against §83's cached sober retell, which shares the retell
                         operation, with the cached tea arm as its draw-noise floor.

**The primary claims are mechanical, and the panel is explicitly secondary.** §83 measured that
near-twin pairs void this panel on positional bias, and minimal revisions are near-twins by
construction. So the pre-registration puts the burden on deterministic checks — compliance,
minimality, containment — and treats any panel arm that survives its bias precondition as a
bonus, not the result. The deliverable is a set of *validated repair variants*: §80's batch can
then ask paid humans the interventional question on pairs where the machine has already
certified that exactly one thing changed. That certification is what this module is for.

**Minimality is measured, not requested.** Each repair is scored for word-level similarity to
its original, for movement on the *other* arm's axis (a dash repair that also adds interiority
has changed two things and certifies nothing), for word growth, and for byte-survival of every
protected system-voice span. `similarity` uses `difflib` over word sequences; the placebo's
similarity is the ceiling any repair is read against.

Pre-registration in `PRE_REGISTRATION`, written before the first call. Point thresholds carry
per-scene sign counts beside them per §81's lesson: at n=8 nothing here can exclude a null by
interval, and the claims are sized accordingly — compliance claims, not preference claims.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import statistics
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from ablate import _EM, _is_protected, _protected_spans  # noqa: E402
from authorship_tells import features, strip_system  # noqa: E402
from corpus_io import generated_scenes  # noqa: E402
from elicit import PANEL_MODEL, Elicitor, positional_bias  # noqa: E402
from persona_battery import pairwise_interval  # noqa: E402
from writer_states import (  # noqa: E402
    CRAFT_RULES,
    SOBER,
    WRITER_MODEL,
    Generator,
    prose_report,
    system_voice_survival,
)

REPAIR_ARMS: tuple[str, ...] = ("repair_emdash", "repair_interiority", "repair_placebo")
PLACEBO = "repair_placebo"

#: The author's revision frame. An author revising is generation, not the §1a.2 critique frame —
#: nobody is asked what is wrong with the text, only to produce a version with one property.
REVISER_SYSTEM = (
    "You are the author of the scene below, midway through drafting a serialized LitRPG "
    "novel, returning tonight to revise your own pages."
)

#: Shared verbatim across the three revision arms; the task block is the single moving part.
REVISION_RULES = """\
Revise the scene below, changing as little as possible. Keep every plot fact, the same events
in the same order, the same point of view. Any line in the system voice — **bold**
announcements and [STATUS] blocks — is copied byte-for-byte, unchanged, where it stood.
Return only the revised scene text: no title, no preamble, no commentary.

Tonight's revision has one purpose:
{task}"""

TASKS: dict[str, str] = {
    "repair_emdash": (
        "Remove every em dash from the prose. Do not simply swap a dash for a comma or a "
        "period — rewrite each sentence that contains one so the sentence no longer needs "
        "it. A sentence with no em dash is left exactly as it is."
    ),
    "repair_interiority": (
        "Wherever the prose reports what his body does or what happens around him without "
        "what it is like from inside — what he feels, thinks, wants, or refuses to think — "
        "add that inner report, in his register. A sentence that already carries inner "
        "experience is left exactly as it is. Grow the scene by at most ten percent."
    ),
    "repair_placebo": (
        "Correct any spelling or typographical errors you find. A sentence that contains "
        "none is left exactly as it is. There may be nothing to correct, in which case the "
        "scene comes back unchanged."
    ),
}


def reviser_turn(arm: str, scene: str) -> str:
    return REVISION_RULES.format(task=TASKS[arm]) + f"\n\n---\n\n{scene}"


def exemplar_system(passages: list[str]) -> str:
    """The voice-demonstration frame. The excerpts are the instruction; nothing names a style.

    §83's craft rules follow in the user turn unchanged, so against the cached sober retell the
    exemplar block is the only moving part besides the missing state sentence — and the cached
    tea arm already prices what an inert system-prompt difference plus a fresh draw is worth.
    """
    shown = "\n\n".join(
        f"VOICE PASSAGE {index + 1}\n\n{passage}" for index, passage in enumerate(passages)
    )
    return (
        "You are a novelist midway through drafting a serialized LitRPG novel, working alone "
        "at night on tonight's pages.\n\nTonight you are writing in the voice of the passages "
        "below — their way of moving through a scene, not their story and not their "
        "characters.\n\n" + shown
    )


def pick_exemplars(pool: list[str], count: int = 2) -> list[int]:
    """Indices of the most interiority-dense excerpts. Deterministic, so the choice is a rule.

    Interiority density because it is §74's named defect: if voice demonstration works at all,
    the demonstration should carry the property the register lacks.
    """
    scored = sorted(
        range(len(pool)),
        key=lambda index: features(strip_system(pool[index]))["interior_per_1k"],
        reverse=True,
    )
    return scored[:count]


#: Written before the first call. Compliance claims, not preference claims — the panel section
#: says so explicitly rather than leaving it to be discovered from the verdicts.
PRE_REGISTRATION: dict[str, str] = {
    "floor": (
        "no repair arm is read except against repair_placebo: its similarity is the "
        "minimality ceiling and its per-axis drift is the band any repair's off-axis "
        "movement must stay inside"
    ),
    "repair_emdash": (
        "COMPLIES if prose em dashes (outside protected spans) fall to <=10% of the "
        "original's count, word-level similarity >=0.80, interiority delta inside the "
        "placebo band, and every protected span survives byte-for-byte. A repair that "
        "moves the other axis certifies nothing"
    ),
    "repair_interiority": (
        "COMPLIES if interior_per_1k rises by at least 2x the placebo's absolute drift and "
        "at least +0.5, word growth <=12%, prose em dashes inside the placebo band, "
        "similarity >=0.60 (added sentences lower it by construction), protected spans "
        "byte-for-byte"
    ),
    "exemplar": (
        "MOVES if the exemplar retell's z-scored feature distance from its original exceeds "
        "the cached sober retell's, AND lands nearer the exemplar centroid than the sober "
        "retell does. The first condition says the voice moved; the second says it moved "
        "toward the demonstration rather than merely away from the original"
    ),
    "panel": (
        "secondary by pre-registration: repair pairs are near-twins and §83 measured that "
        "near-twin pairs void this panel on positional bias, so VOID is the expected "
        "outcome and is not a failure of the repairs. Per-arm bias 0.40-0.60 precondition "
        "as always. If an arm survives it: >=0.60 means the panel shares the human's "
        "direction on a generative repair — the first evidence on an axis §78.3 left empty; "
        "<=0.40 means the panel prefers the defect, §78.2's OPPOSES branch resurrected on "
        "substitution-free evidence. Intervals reported; at n=8 they will span 0.5 and the "
        "claims are sized accordingly"
    ),
}


# ----------------------------------------------------------------------------- mechanics


def prose_em_count(text: str) -> int:
    """Em dashes outside protected system-voice spans — the only ones the repair may touch."""
    spans = _protected_spans(text)
    return sum(
        1 for match in re.finditer(_EM, text) if not _is_protected(match.start(), spans)
    )


def word_similarity(original: str, variant: str) -> float:
    """Word-sequence similarity, the minimality number. 1.0 is byte-faithful."""
    return round(
        difflib.SequenceMatcher(None, original.split(), variant.split()).ratio(), 4
    )


def z_distance(
    row: dict[str, float], anchor: dict[str, float], scale: dict[str, float]
) -> float:
    """L2 over per-feature z-deltas, features with zero spread skipped."""
    total = 0.0
    for name, sd in scale.items():
        if sd > 0:
            total += ((row[name] - anchor[name]) / sd) ** 2
    # `float ** float` is typed Any in typeshed; the result is a float by construction.
    magnitude: float = total ** 0.5
    return round(magnitude, 4)


def feature_scale(rows: list[dict[str, float]]) -> dict[str, float]:
    """Per-feature population sd over every text in the run — the run's own unit system."""
    return {
        name: statistics.pstdev([row[name] for row in rows]) if len(rows) > 1 else 0.0
        for name in rows[0]
    }


# ------------------------------------------------------------------------------- verdict


def compliance(
    arm: str,
    original: str,
    variant: str,
    placebo_band: dict[str, float],
) -> dict[str, Any]:
    """One scene's deterministic checks for one repair arm. The certifying record."""
    orig_f = features(strip_system(original))
    var_f = features(strip_system(variant))
    survival = system_voice_survival(original, variant)
    row: dict[str, Any] = {
        "similarity": word_similarity(original, variant),
        "prose_em_before": prose_em_count(original),
        "prose_em_after": prose_em_count(variant),
        "interior_delta": round(var_f["interior_per_1k"] - orig_f["interior_per_1k"], 3),
        "word_growth_pct": round(
            100.0 * (len(variant.split()) - len(original.split()))
            / max(len(original.split()), 1), 2,
        ),
        "system_voice_ok": survival["kept"] == survival["spans"],
    }
    if arm == "repair_emdash":
        row["complies"] = bool(
            row["prose_em_after"] <= 0.10 * max(row["prose_em_before"], 1)
            and row["similarity"] >= 0.80
            and abs(row["interior_delta"]) <= placebo_band["interior"]
            and row["system_voice_ok"]
        )
    elif arm == "repair_interiority":
        em_drift = abs(row["prose_em_after"] - row["prose_em_before"])
        row["complies"] = bool(
            row["interior_delta"] >= max(2 * placebo_band["interior_drift"], 0.5)
            and row["word_growth_pct"] <= 12.0
            and em_drift <= placebo_band["em"]
            and row["similarity"] >= 0.60
            and row["system_voice_ok"]
        )
    else:
        row["complies"] = None  # the placebo is the ruler, not a subject
    return row


# ----------------------------------------------------------------------------------- run


def run(args: argparse.Namespace) -> dict[str, Any]:
    units = generated_scenes(args.book_db, book=args.book, min_words=args.min_words)
    units = units[: args.scenes]
    if len(units) < 2:
        raise SystemExit(f"need at least 2 scenes, got {len(units)}")

    # §83's retells, replayed from their own cache file — never re-elicited. The exemplar arm
    # has no anchor without them, so their absence is an error rather than a silent skip.
    states_cache = Path(args.states_cache)
    cached_retells: dict[tuple[str, str], str] = {}
    if states_cache.is_file():
        for line in states_cache.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not record.get("refused") and record.get("scene") and record.get("state"):
                cached_retells[(record["scene"], record["state"])] = record["text"]
    missing = [u.unit_id for u in units if (u.unit_id, SOBER) not in cached_retells]
    if missing and not args.dry_run:
        raise SystemExit(
            f"no cached sober retell for {missing}; run writer_states.py first — the "
            "exemplar arm is judged against that anchor and re-eliciting it here would "
            "fork the anchor across two cache files"
        )

    human = json.loads(Path(args.human_json).read_text(encoding="utf-8"))
    exemplar_indices = pick_exemplars(human["rr_high"])
    exemplars = [human["rr_high"][index] for index in exemplar_indices]

    planned_gen = len(units) * (len(REPAIR_ARMS) + 1)
    planned_panel = len(units) * 4 * 4 * 2
    if planned_gen + planned_panel > args.guard and not args.yes:
        raise SystemExit(
            f"{planned_gen} generations + {planned_panel} comparisons exceeds the "
            f"{args.guard} guard; pass --yes"
        )

    report: dict[str, Any] = {
        "book_db": str(args.book_db),
        "scenes": [unit.unit_id for unit in units],
        "writer_model": args.writer_model,
        "panel_model": args.model,
        "tie_policy": args.tie_policy,
        "exemplar_indices": exemplar_indices,
        "exemplar_interior_per_1k": [
            round(features(strip_system(text))["interior_per_1k"], 3) for text in exemplars
        ],
        "planned_generations": planned_gen,
        "planned_comparisons": planned_panel,
        "protocol": "pre-registered in this module's PRE_REGISTRATION before first elicitation",
    }

    # ---- generation: three revisions of each original, one exemplar retell.
    outputs: dict[tuple[str, str], dict[str, Any]] = {}
    with Generator(Path(args.gen_cache), model=args.writer_model,
                   dry_run=args.dry_run) as generator:
        jobs: list[tuple[Any, str]] = [
            (unit, arm) for unit in units for arm in (*REPAIR_ARMS, "exemplar")
        ]

        def produce(job: tuple[Any, str]) -> tuple[str, str, dict[str, Any]]:
            unit, arm = job
            if arm == "exemplar":
                record = generator.generate(
                    {"scene": unit.unit_id, "arm": arm},
                    exemplar_system(exemplars), f"{CRAFT_RULES}\n\n---\n\n{unit.text}",
                    dry_text=f"[dry:{arm}] {unit.text}",
                )
            else:
                record = generator.generate(
                    {"scene": unit.unit_id, "arm": arm},
                    REVISER_SYSTEM, reviser_turn(arm, unit.text),
                    dry_text=f"[dry:{arm}] {unit.text}",
                )
            return unit.unit_id, arm, record

        with ThreadPoolExecutor(max_workers=3) as pool:
            for scene_id, arm, record in pool.map(produce, jobs):
                outputs[(scene_id, arm)] = record
                status = "refused" if record["refused"] else f"{len(record['text'].split())}w"
                print(f"  {scene_id} [{arm}]: {status}", file=sys.stderr, flush=True)
        report["gen_spend"] = generator.spend()
        report["gen_api_calls"] = generator.api_calls
        report["gen_replayed"] = generator.replayed
    report["gen_failures"] = [
        f"{scene}|{arm}" for (scene, arm), r in outputs.items() if r["refused"]
    ]

    # ---- the placebo band: what an inert revision drifts, measured before any arm is read.
    placebo_interior, placebo_em = [], []
    for unit in units:
        record = outputs.get((unit.unit_id, PLACEBO))
        if record is None or record["refused"]:
            continue
        orig_f = features(strip_system(unit.text))
        var_f = features(strip_system(record["text"]))
        placebo_interior.append(abs(var_f["interior_per_1k"] - orig_f["interior_per_1k"]))
        placebo_em.append(abs(prose_em_count(record["text"]) - prose_em_count(unit.text)))
    band = {
        "interior_drift": statistics.fmean(placebo_interior) if placebo_interior else 0.0,
        "interior": max(placebo_interior) if placebo_interior else 0.5,
        "em": max(placebo_em) if placebo_em else 1.0,
    }
    report["placebo_band"] = {key: round(value, 3) for key, value in band.items()}

    # ---- compliance, per scene per repair arm; the placebo rides along as the ruler.
    checks: dict[str, list[dict[str, Any]]] = {arm: [] for arm in REPAIR_ARMS}
    for unit in units:
        for arm in REPAIR_ARMS:
            record = outputs.get((unit.unit_id, arm))
            if record is None or record["refused"]:
                continue
            checks[arm].append(
                {"scene": unit.unit_id,
                 **compliance(arm, unit.text, record["text"], band)}
            )
    report["compliance"] = checks
    report["complies"] = {
        arm: f"{sum(1 for row in rows if row['complies'])}/{len(rows)}"
        for arm, rows in checks.items() if arm != PLACEBO
    }

    # ---- the exemplar's register movement, in the run's own units.
    all_rows: list[dict[str, float]] = []
    per_text_features: dict[str, dict[str, float]] = {}

    def remember(name: str, text: str) -> dict[str, float]:
        row = features(strip_system(text))
        all_rows.append(row)
        per_text_features[name] = row
        return row

    for index, text in enumerate(exemplars):
        remember(f"exemplar_source_{index}", text)
    for unit in units:
        remember(f"{unit.unit_id}|original", unit.text)
        # One local, two payloads: the cached retell text here, a feature row after the loop
        # below; a union cannot survive the shared truthiness guards, so this stays open.
        sober: Any = cached_retells.get((unit.unit_id, SOBER))
        if sober:
            remember(f"{unit.unit_id}|sober", sober)
        for arm in (*REPAIR_ARMS, "exemplar"):
            record = outputs.get((unit.unit_id, arm))
            if record is not None and not record["refused"]:
                remember(f"{unit.unit_id}|{arm}", record["text"])
    scale = feature_scale(all_rows)
    centroid = {
        name: statistics.fmean(
            per_text_features[f"exemplar_source_{index}"][name]
            for index in range(len(exemplars))
        )
        for name in all_rows[0]
    }

    moved: list[dict[str, Any]] = []
    toward: list[dict[str, Any]] = []
    for unit in units:
        original = per_text_features.get(f"{unit.unit_id}|original")
        sober = per_text_features.get(f"{unit.unit_id}|sober")
        styled = per_text_features.get(f"{unit.unit_id}|exemplar")
        if not (original and sober and styled):
            continue
        moved.append(
            {"scene": unit.unit_id,
             "sober_from_original": z_distance(sober, original, scale),
             "exemplar_from_original": z_distance(styled, original, scale)}
        )
        toward.append(
            {"scene": unit.unit_id,
             "sober_to_centroid": z_distance(sober, centroid, scale),
             "exemplar_to_centroid": z_distance(styled, centroid, scale)}
        )
    report["exemplar_movement"] = {
        "per_scene": moved,
        "moved_more_than_sober": sum(
            1 for row in moved if row["exemplar_from_original"] > row["sober_from_original"]
        ),
        "toward_centroid": toward,
        "nearer_centroid_than_sober": sum(
            1 for row in toward if row["exemplar_to_centroid"] < row["sober_to_centroid"]
        ),
        "scenes": len(moved),
    }
    report["prose_stats"] = {
        arm: [
            prose_report(outputs[(unit.unit_id, arm)]["text"])
            for unit in units
            if (unit.unit_id, arm) in outputs and not outputs[(unit.unit_id, arm)]["refused"]
        ][:1]
        for arm in ("exemplar",)
    }

    if args.generate_only:
        return report

    # ---- the panel, pre-registered as secondary. Repairs against their originals; the
    # exemplar retell against the cached sober retell.
    every: list[Any] = []
    per_arm: dict[str, list[float]] = {arm: [] for arm in (*REPAIR_ARMS, "exemplar")}
    with Elicitor(
        Path(args.cache), model=args.model, spot_model=None, spot_fraction=0.0,
        transport=args.transport, pair_question=args.pair_question, dry_run=args.dry_run,
    ) as elicitor:
        for unit in units:
            for arm in (*REPAIR_ARMS, "exemplar"):
                record = outputs.get((unit.unit_id, arm))
                if record is None or record["refused"]:
                    continue
                if arm == "exemplar":
                    anchor = cached_retells.get((unit.unit_id, SOBER), "")
                else:
                    anchor = unit.text
                if not anchor or record["text"].strip() == anchor.strip():
                    continue
                pair_id = f"{unit.unit_id}|{arm}"
                comparisons = elicitor.compare_pair(pair_id, anchor, record["text"], n=1)
                every.extend(comparisons)
                values = [
                    0.5 if c.choice == "neither" else float(c.chose_variant)
                    for c in comparisons if not c.refused
                    and not (c.choice == "neither" and args.tie_policy == "drop")
                ]
                if values:
                    per_arm[arm].append(statistics.fmean(values))
            print(f"  {unit.unit_id}: {len(every)} comparisons", file=sys.stderr, flush=True)

        rates = {
            arm: round(statistics.fmean(values), 4)
            for arm, values in per_arm.items() if values
        }
        report["win_rates"] = rates
        report["per_arm_bias"] = {
            arm: positional_bias([c for c in every if c.pair_id.endswith(f"|{arm}")])
            for arm in per_arm
        }
        report["intervals"] = {
            arm: pairwise_interval(
                [c for c in every if c.pair_id.endswith(f"|{arm}")],
                args.model, args.tie_policy,
            )
            for arm in rates
        }
        report["positional_bias"] = positional_bias(every)
        report["comparisons"] = len(every)
        report["refused"] = sum(1 for c in every if c.refused)
        report["panel_spend"] = elicitor.spend()
        report["panel_api_calls"] = elicitor.api_calls
        report["panel_replayed"] = elicitor.replayed
    report["pre_registration"] = PRE_REGISTRATION
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--book-db", default=str(HERE / "corpora" / "toll.db"))
    parser.add_argument("--book")
    parser.add_argument("--min-words", type=int, default=500)
    parser.add_argument("--scenes", type=int, default=8)
    parser.add_argument("--writer-model", default=WRITER_MODEL)
    parser.add_argument("--model", default=PANEL_MODEL)
    parser.add_argument("--transport", default="cli", choices=("cli", "sdk", "ollama"))
    parser.add_argument(
        "--pair-question", default="preference", choices=("preference", "intensity")
    )
    parser.add_argument("--tie-policy", default="half_win", choices=("half_win", "drop"))
    parser.add_argument("--guard", type=int, default=300)
    parser.add_argument("--generate-only", action="store_true")
    parser.add_argument("--human-json", default=str(HERE / "corpora" / "human-excerpts.json"))
    parser.add_argument("--states-cache",
                        default=str(HERE / "results" / "writer-states-gen-raw.jsonl"))
    parser.add_argument("--gen-cache",
                        default=str(HERE / "results" / "repair-gen-raw.jsonl"))
    parser.add_argument("--cache", default=str(HERE / "results" / "repair-panel-raw.jsonl"))
    parser.add_argument("--out", default=str(HERE / "results" / "repair-generation.json"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)

    report = run(args)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report.get("complies", {}), indent=2))
    print(json.dumps(report.get("placebo_band", {}), indent=2))
    movement = report.get("exemplar_movement", {})
    print(json.dumps({k: movement.get(k) for k in
                      ("moved_more_than_sober", "nearer_centroid_than_sober", "scenes")},
                     indent=2))
    print(json.dumps(report.get("win_rates", {}), indent=2))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
