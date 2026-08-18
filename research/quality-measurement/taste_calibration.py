"""Does the panel have taste, or does it only detect who wrote the text?

Every comparison this project has run put our prose against *our own prose*, so the panel has
never been asked to judge our work against anyone else's. §74's human read makes that gap the
important one: the three defects he named are properties of our baseline, and a panel that only
ever sees our baseline on both sides cannot have an opinion about it.

**The naive version of this experiment cannot be read, and that is why it is not the experiment.**
Ask the panel to choose between our scene and a fan-acclaimed human serial, and a preference for
the human is uninterpretable three ways over: RevisionBench already measured that order-consistent
model judges prefer human originals ~80% of the time (§2 Pass 4), *Mother of Learning* is famous
enough that recognition is a live term, and "prefers the human" is what an authorship detector and
a critic both do. So the run is built around separating those.

    ours_vs_mol       our scene against Mother of Learning — the headline
    ours_vs_rr        our scene against an obscure pre-LLM RoyalRoad chapter
    mol_vs_rr         acclaimed against median, both human — can it rank at all?
    rr_high_vs_low    high-conversion against low-conversion RoyalRoad, same era, same
                      obscurity — the only arm where a measured human label does the ranking
    mol_vs_mol        two chapters of one book — the indifference floor

**`rr_high_vs_low` is the arm that makes the rest readable.** `conversion = followers /
total_views` is the one measured human label BRIEF §4 leaves standing, with a 9x spread p10 to
p90 and rho 0.44 against raw followers, so it is not popularity restated. Both sides are the same
platform, the same era and equally obscure, which controls the fame term that `mol_vs_rr` cannot.
A panel that cannot separate high-conversion from low-conversion prose has no taste to bring, and
then any preference it shows for humans over us is authorship detection wearing a critic's voice.

**Read the arms together, because the pattern is the finding rather than any single rate:**

- ours loses to *both* humans by similar margins while `mol_vs_rr` and `rr_high_vs_low` sit near
  0.5 — the panel detects authorship and has no quality ranking. Its em-dash preference then says
  nothing about em dashes and everything about which text was touched.
- ours loses and the two human-vs-human arms separate — the panel has real taste and our prose is
  genuinely behind it, which is the most useful outcome for the book and the worst for our pride.
- **ours wins against either human** — the panel's taste is machine taste, measured directly. That
  reading is the one the confounds cannot manufacture: recognition and the RevisionBench prior
  both push toward the human, so a win for us survives them rather than being produced by them.

**Memorisation is a term here and it is asymmetric.** BRIEF §2 Pass 6's rule is that a
model-based measure over published fiction either runs on text the scoring model provably has not
memorised or measures its familiarity term explicitly. Nothing here is un-memorised — MoL is
famous, RoyalRoad is public — so this measure does not clear that bar and does not claim to. What
saves the headline is direction: every familiarity term pushes toward the human side, so a
human-preferring result is confounded and a *ours*-preferring result is not.
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

#: Words per excerpt. Our scenes run 912-1,070, so the human side is cut to the same band rather
#: than the panel being asked to compare a scene with a 7,500-word chapter.
EXCERPT_WORDS = 1_000

#: The five arms, each naming which side counts as the "variant" in `variant_win_rate` terms.
#: `left` is the original slot and `right` the variant slot, so a rate above 0.5 means the panel
#: preferred `right`.
#: Controls added after the first run, which found ours beating both humans at 0.98 and 1.00
#: while `stakes-real` carried 38 of 63 and 43 of 64 of those wins. Two confounds explain that
#: without any claim about prose: our units are **complete scenes** while the human side is an
#: arbitrary window cut 20% into a chapter (the first MoL excerpt opens on a mother offering
#: porridge), and our book is premised on a man paying tolls in days of his remaining life, so
#: it is stakes-dense by construction. `ours_win_*` windows our side the same way theirs is
#: windowed so both start and end mid-flow; `*_stakes` matches the human side on the very
#: dimension the panel named. The second is covariate matching, not a quality selection — it
#: uses our own stake lexicon, and its only claim is that the comparison is no longer decided
#: by stake density.
CONTROL_ARMS: tuple[tuple[str, str, str], ...] = (
    ("ours_win_vs_mol_win", "mol_win", "ours_win"),
    ("ours_vs_mol_stakes", "mol_stakes", "ours"),
    ("ours_win_vs_mol_stakes", "mol_stakes_win", "ours_win"),
)

ARMS: tuple[tuple[str, str, str], ...] = (
    ("ours_vs_mol", "mol", "ours"),
    ("ours_vs_rr", "rr_mid", "ours"),
    ("mol_vs_rr", "rr_mid", "mol"),
    ("rr_high_vs_low", "rr_low", "rr_high"),
    ("mol_vs_mol", "mol", "mol_b"),
)


def excerpt(text: str, words: int = EXCERPT_WORDS, *, start_fraction: float = 0.2) -> str:
    """A paragraph-aligned window of about `words` words, taken from inside the text.

    Started a fifth of the way in rather than at the top: a chapter opening has a different
    rhetorical job from a mid-chapter scene, and our units are mid-book scenes. Aligned to
    paragraph boundaries so no excerpt begins mid-sentence, which would be a defect the panel
    could read as one.
    """
    blocks = [block for block in text.split("\n\n") if block.strip()]
    # **Fall back to single newlines when double-newline splitting yields almost nothing.**
    # Mother of Learning's captured chapter files separate paragraphs with one newline, so the
    # first version found a single block and returned the *entire* 7,600-word chapter as an
    # "excerpt" — the panel would have been asked to compare a 1,000-word scene against a whole
    # chapter, a length contrast dwarfing every effect being measured.
    if len(blocks) < 4:
        blocks = [block for block in text.split("\n") if block.strip()]
    if not blocks:
        return text[: words * 6]
    total = sum(len(block.split()) for block in blocks)
    if total <= words:
        return "\n\n".join(blocks)
    target = int(start_fraction * total)
    seen, start = 0, 0
    for index, block in enumerate(blocks):
        if seen >= target:
            start = index
            break
        seen += len(block.split())
    picked: list[str] = []
    count = 0
    for block in blocks[start:]:
        picked.append(block)
        count += len(block.split())
        if count >= words:
            break
    return "\n\n".join(picked)


def window(text: str, words: int = 700) -> str:
    """A slice with both ends mid-flow, so a complete scene and a chapter cutting are alike.

    The first run compared our complete scenes against mid-chapter windows, which hands our side
    a beginning and an ending the human side does not have. Applying the same cut to both is what
    makes the contrast about prose rather than about completeness.
    """
    return excerpt(text, words, start_fraction=0.3)


def stakes_window(text: str, words: int = 1_000) -> str:
    """The window of roughly `words` with the highest stake-vocabulary density.

    Matching, not selection: `ablate.stake_score` is our own lexical proxy and it identifies
    stake *vocabulary* rather than stakes, as its own docstring insists. Using it to choose the
    human excerpt makes no claim that the chosen passage is good — only that the comparison is no
    longer decided by whichever side happened to be about something costly.
    """
    from ablate import stake_score

    blocks = [block for block in text.split("\n\n") if block.strip()]
    if len(blocks) < 4:
        blocks = [block for block in text.split("\n") if block.strip()]
    if not blocks:
        return text[: words * 6]
    scores = [sum(stake_score(part) for part in block.split(". ")) for block in blocks]
    best, best_score = 0, -1.0
    for start in range(len(blocks)):
        count, total = 0, 0.0
        for index in range(start, len(blocks)):
            count += len(blocks[index].split())
            total += scores[index]
            if count >= words:
                break
        if count < words * 0.6:
            break
        density = total / max(count, 1)
        if density > best_score:
            best, best_score = start, density
    picked, count = [], 0
    for block in blocks[best:]:
        picked.append(block)
        count += len(block.split())
        if count >= words:
            break
    return "\n\n".join(picked)


def dump(args: argparse.Namespace) -> int:
    """Write every excerpt to JSON from the interpreter that can read the corpora.

    Two interpreters, no overlap — `royalroad_chapters` needs pyarrow and the panel transport
    lives with the package. Same bridge `authorship_tells` uses, and the same reason.
    """
    from corpus_io import mol_chapters, royalroad_chapters

    mol = [excerpt(unit.text) for unit in mol_chapters()]
    chapters = list(royalroad_chapters(shards=(30,), min_words=1500, limit=args.limit))
    # **One chapter per story.** The first draw put eight chapters at conversion 0.000293 in the
    # low pool — the same value eight times, because they were eight chapters of one fiction. A
    # "low quality" stratum that is really one author is a stratum of one, and the arm would have
    # measured that author rather than the label.
    seen_works: set[str] = set()
    scored = []
    for unit in chapters:
        conversion = float(unit.meta.get("conversion") or 0.0)
        if not conversion or unit.work_id in seen_works:
            continue
        seen_works.add(unit.work_id)
        scored.append((unit, conversion))
    scored.sort(key=lambda pair: pair[1])
    take = max(args.pairs, 10)
    payload = {
        "excerpt_words": EXCERPT_WORDS,
        "mol": mol,
        "mol_win": [window(unit.text) for unit in mol_chapters()],
        "mol_stakes": [stakes_window(unit.text) for unit in mol_chapters()[:40]],
        "mol_stakes_win": [stakes_window(unit.text, 700) for unit in mol_chapters()[:40]],
        "mol_titles": [unit.meta.get("title", "") for unit in mol_chapters()],
        "rr_low": [excerpt(unit.text) for unit, _ in scored[:take]],
        "rr_mid": [
            excerpt(unit.text)
            for unit, _ in scored[len(scored) // 2 - take // 2 : len(scored) // 2 + take]
        ],
        "rr_high": [excerpt(unit.text) for unit, _ in scored[-take:]],
        "conversion_low": [round(value, 6) for _, value in scored[:take]],
        "conversion_high": [round(value, 6) for _, value in scored[-take:]],
        "rr_stories_scored": len(scored),
        "distinct_stories": {"low": take, "high": take},
    }
    Path(args.human_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.human_json).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(
        f"wrote {len(mol)} MoL excerpts and {len(scored)} conversion-scored RoyalRoad chapters "
        f"to {args.human_json}"
    )
    return 0


def run(args: argparse.Namespace) -> dict[str, Any]:
    from elicit import Elicitor, positional_bias

    human = json.loads(Path(args.human_json).read_text(encoding="utf-8"))
    ours_payload = json.loads(Path(args.ours_json).read_text(encoding="utf-8"))
    ours = [excerpt(entry["text"]) for entry in ours_payload["scenes"]]

    pools: dict[str, list[str]] = {
        "ours": ours,
        "mol": human["mol"][: args.pairs],
        # A disjoint slice, so the indifference arm never compares a chapter with itself.
        "mol_b": human["mol"][args.pairs : 2 * args.pairs],
        "rr_mid": human["rr_mid"],
        "rr_low": human["rr_low"],
        "rr_high": human["rr_high"],
    }
    pools["ours_win"] = [window(entry) for entry in ours]
    for name in ("mol_win", "mol_stakes", "mol_stakes_win"):
        pools[name] = human.get(name, [])[: args.pairs]

    schedule = ARMS + CONTROL_ARMS if args.controls else ARMS
    usable = [
        (key, left, right) for key, left, right in schedule
        if len(pools[left]) >= args.pairs and len(pools[right]) >= args.pairs
    ]
    planned = len(usable) * args.pairs * 4 * 2
    if planned > args.guard and not args.yes:
        raise SystemExit(f"{planned} calls exceeds the {args.guard} guard; pass --yes")

    report: dict[str, Any] = {
        "protocol": "plan/stage-0-decisions.md §77",
        "excerpt_words": EXCERPT_WORDS,
        "pairs_per_arm": args.pairs,
        "panel_model": args.model,
        "arms": [key for key, _, _ in usable],
        "skipped_arms": [
            key for key, _, _ in schedule if key not in {k for k, _, _ in usable}
        ],
        "planned_calls": planned,
        "rr_conversion": {
            "low": human.get("conversion_low", [])[: args.pairs],
            "high": human.get("conversion_high", [])[: args.pairs],
        },
    }

    every: list[Any] = []
    per_arm: dict[str, list[float]] = {}
    with Elicitor(
        Path(args.cache), model=args.model, spot_model=None, spot_fraction=0.0,
        transport=args.transport, pair_question=args.pair_question, dry_run=args.dry_run,
    ) as elicitor:
        for key, left_pool, right_pool in usable:
            rates: list[float] = []
            for index in range(args.pairs):
                left = pools[left_pool][index]
                right = pools[right_pool][index]
                if not left.strip() or not right.strip() or left.strip() == right.strip():
                    continue
                comparisons = elicitor.compare_pair(f"pair{index}|{key}", left, right, n=1)
                every.extend(comparisons)
                values = [
                    0.5 if c.choice == "neither" else float(c.chose_variant)
                    for c in comparisons if not c.refused
                    and not (c.choice == "neither" and args.tie_policy == "drop")
                ]
                if values:
                    rates.append(statistics.fmean(values))
            if rates:
                per_arm[key] = rates
            print(f"  {key}: {len(every)} comparisons", file=sys.stderr, flush=True)

        report["win_rates"] = {
            key: round(statistics.fmean(values), 4) for key, values in per_arm.items()
        }
        report["per_arm_bias"] = {
            key: positional_bias([c for c in every if c.pair_id.endswith(f"|{key}")])
            for key in per_arm
        }
        report["positional_bias"] = positional_bias(every)
        report["comparisons"] = len(every)
        report["refused"] = sum(1 for c in every if c.refused)
        report["reading"] = _read(report["win_rates"], report["per_arm_bias"])
        report["spend"] = elicitor.spend()
    return report


def _read(rates: dict[str, float], bias: dict[str, dict[str, Any]]) -> dict[str, object]:
    """The pattern across arms, with each arm's own positional precondition read first.

    Per-arm rather than pooled, which §74's run earned the hard way: pooling bias across arms of
    very different discriminability voided a run whose arm of interest was clean.
    """
    def clean(arm: str) -> bool:
        value = bias.get(arm, {}).get("chose_A_rate")
        return isinstance(value, float) and 0.40 <= value <= 0.60

    readable = [arm for arm in rates if clean(arm)]
    notes: list[str] = []
    calibration = [rates[a] for a in ("mol_vs_rr", "rr_high_vs_low") if a in readable]
    ranks = bool(calibration) and max(abs(value - 0.5) for value in calibration) >= 0.10

    if "ours_vs_mol" in readable and rates["ours_vs_mol"] > 0.5:
        notes.append(
            f"OURS PREFERRED over Mother of Learning at {rates['ours_vs_mol']} — the machine-taste "
            "reading, and the one the confounds cannot manufacture, since recognition and the "
            "RevisionBench prior both push toward the human"
        )
    if not ranks and calibration:
        notes.append(
            "NO TASTE: the human-vs-human arms sit within 0.10 of indifference, so the panel "
            "cannot rank prose whose quality differs by a measured label. Any preference it "
            "shows for humans over us is authorship detection rather than judgement."
        )
    elif ranks:
        notes.append(
            "the panel ranks human prose by quality, so its verdict on our prose is a verdict"
        )
    if not readable:
        notes.append("VOID: no arm cleared its own positional-bias precondition")
    return {"readable_arms": readable, "voided_arms": [a for a in rates if a not in readable],
            "notes": notes}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dump", action="store_true", help="write human excerpts and exit")
    parser.add_argument("--controls", action="store_true",
                        help="add the completeness and stakes-matched control arms")
    parser.add_argument("--human-json", default=str(HERE / "corpora" / "human-excerpts.json"))
    parser.add_argument("--ours-json", default=str(HERE / "corpora" / "toll-scenes.json"))
    parser.add_argument("--pairs", type=int, default=8)
    parser.add_argument("--limit", type=int, default=4000)
    parser.add_argument("--model", default="claude-haiku-4-5")
    parser.add_argument("--transport", default="cli", choices=("cli", "sdk", "ollama"))
    parser.add_argument(
        "--pair-question", default="preference", choices=("preference", "intensity")
    )
    parser.add_argument("--tie-policy", default="half_win", choices=("half_win", "drop"))
    parser.add_argument("--guard", type=int, default=400)
    parser.add_argument("--cache", default=str(HERE / "results" / "taste-calibration-raw.jsonl"))
    parser.add_argument("--out", default=str(HERE / "results" / "taste-calibration.json"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)

    if args.dump:
        return dump(args)

    report = run(args)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report["win_rates"], indent=2))
    print(json.dumps({k: v.get("chose_A_rate") for k, v in report["per_arm_bias"].items()},
                     indent=2))
    print(json.dumps(report["reading"], indent=2))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
