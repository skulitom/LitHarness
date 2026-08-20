"""Track F3: does a book with real structure teach the model to read it?

The only arm in the force programme that touches **book grain**, which is the grain the project
is actually about. Every other measurement here reads a thousand words; this one reads nine
chapters and asks whether the tenth got easier because of them.

    NLL_true(j)     = NLL(chapter 10 | chapters 1..j)
    NLL_foreign(j)  = NLL(chapter 10 | token-length-matched context from a different fiction)

    learnability slope = OLS slope of [NLL_foreign(j) - NLL_true(j)] over j

A book whose earlier chapters genuinely inform its later ones has a positive slope; episodic
prose has a flat one. A shuffled-context arm rides along — same provenance, destroyed order —
because "this fiction's own words" and "this fiction's own words *in order*" are different
claims and only the second one is about structure.

**This is CDG's shape, and CDG is dead (§58, refutation-ledger entry 21).** Saying so before the
run is the point. CDG measured detect-AUC 0.5188 and its `rename_entities` sham moved the score
2.0x further than the strongest degrader, *upward*, because recall inflates the foreign-prefix
term and any edit that breaks surface familiarity releases the gap. F3 differs in two declared
ways: the outcome is a **slope over j rather than a level**, so a familiarity term that raises
both conditions at every j enters the intercept and leaves the slope alone; and the validation
target is an **external behavioural label** rather than a manufactured ablation, so no transform
in this repository can move it. If F3 fails, §58 gains a second entry rather than losing its
first.

**Substrate honesty.** Chapter text beyond the pair excerpts is a third-party fetch from the
cached RoyalRoad shards — local-only, audited, never committed (operator §7.3: ALLOW). F3's
eventual real target is own-generated books, and that arm is `NOT_RUN` with a price until §7.1's
fitness books exist: §94.3 counted exactly one own-generated text long enough to carry a slope.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import force_gpu  # noqa: E402
from force_harness import (  # noqa: E402
    FAMILIES,
    RESULTS,
    Checkpoint,
    ForcePair,
    arm_status,
    attainability_table,
    combine_families,
    control_verdict,
    digest,
    ols_slope,
    pair_agreement,
    provenance,
    rewhitespace,
    sham_verdict,
    stratified_subsample,
    unit_key,
    verdict,
)
from force_harness import force_verdict as headline_verdict  # noqa: E402

DERIVED = HERE / "derived"
SURVEY = DERIVED / "f3-survey.json"

#: The context ladder, and the chapter count, both set by **Qwen2.5-3B's 32,768-position
#: ceiling** rather than by preference. Ten chapters with j=9 runs the true-context prefix to
#: roughly 30k tokens before the target chapter is added, which does not fit — and the obvious
#: repair, truncating the prefix from the left, is the worst available option here: a truncated
#: rung at j=9 beside an untruncated one at j=3 puts a *level* artifact back into the slope, and
#: subtracting exactly that artifact is the only reason F3 is a slope rather than CDG (§58).
#:
#: So the ladder is shortened for every fiction and every family alike, and a fiction whose top
#: rung still does not fit under **either** family's ceiling is **dropped and counted** — never
#: measured on a shorter ladder than its pair-mate, which would be the same artifact wearing a
#: different hat. Odd j only: the slope needs spread more than density.
LADDER = (1, 3, 5, 7)
CHAPTERS = 8

#: §79's constants, reused rather than re-chosen so F3's pairs are the same kind of object as
#: the B4 pairs. A second definition of `conversion` appearing in one experiment is how two
#: results stop being comparable (`corpus_io`'s own warning).
MIN_VIEWS = 10_000
MIN_CONVERSION_RATIO = 2.0
MAX_LOG_VIEW_GAP = 0.30
MAX_LOG_CHAPTER_GAP = 0.20
COHORT = "human_pre_llm"

#: The directive's cap is 40 fictions. F3 turns out to cost about a GPU-minute per fiction, so
#: the cap binds on nothing but the count — and at 40 fictions the pairing yields 20 pairs whose
#: interval bar demands 15 of 20 = 0.7500, a rate §1.2 already flagged as one no honest
#: instrument reaches on near-twin material. So both are declared here, **before selection**:
#: the capped subset prints as the directive's declared cap, and the bar is declared on the
#: largest stratum the substrate yields up to EXTENSION_FICTIONS. n is decided by how many
#: fictions qualify, which is a fact about the shards and not about any result.
CAP_FICTIONS = 40
EXTENSION_FICTIONS = 200

PRE_REGISTRATION: dict[str, Any] = {
    "track": "F3 compression progress",
    "hypothesis": "a book with real structure teaches the model to read it: later-chapter "
                  "predictability improves with true earlier context in a way flat episodic "
                  "prose cannot",
    "asks_nothing": "teacher-forced NLL only; nothing is sampled and nothing is asked",
    "statistic": "OLS slope of [NLL_foreign(j) - NLL_true(j)] over j",
    "ladder": list(LADDER),
    "chapters": CHAPTERS,
    "controls_in_the_statistic": {
        "foreign": "token-length-matched context from a different fiction — holds context "
                   "LENGTH fixed and varies only provenance",
        "shuffled": "the fiction's own chapters in destroyed order — same provenance, no "
                    "structure; reported as a second comparison",
    },
    "label": "conversion = followers / total_views, declared before selection",
    "cohort": COHORT,
    "strata": "aligned and crossed, built with §79's tolerances so no prose-blind popularity "
              "rule can clear both",
    "cap_fictions": CAP_FICTIONS,
    "extension_fictions": EXTENSION_FICTIONS,
    "bar_declared_on": "the largest stratum the substrate yields, up to EXTENSION_FICTIONS; the "
                       "capped-40 subset prints beside it as the directive's declared cap",
    # Measured on the cached survey before any forward pass, and declared rather than discovered
    # afterwards. Every shape this substrate can produce sits above the 0.6000 ceiling:
    #
    #     585 fictions (uncapped)  191 pairs  118/73  required 0.6017 / 0.6301
    #     200 fictions (declared)   64 pairs   41/23  required 0.6829 / 0.7391
    #      40 fictions (directive)  12 pairs   11/ 1  required 0.9091 / 1.0000
    #
    # So F3 is a **one-directional arm**: it can PASS, and it cannot FAIL. A miss here returns
    # INSUFFICIENT_N, because at these n a miss is a statement about power. That asymmetry is a
    # property of the substrate, not a concession made after seeing a result, and raising
    # EXTENSION_FICTIONS to chase a refutable n would be moving a declared bar — which is the
    # thing §89's rulebook exists to forbid.
    "can_refute": False,
    "one_directional": "PASS is available at every shape this substrate yields; FAIL is not, "
                       "because the interval bar demands 0.6017 or more at every n. A miss "
                       "returns INSUFFICIENT_N and is not evidence against the force.",
    "prior_art": "§58 killed CDG, which is this statistic's level. The slope is what subtracts "
                 "the level artifact that killed it; if F3 fails, §58 gains a second entry.",
    "own_generated_arm": "NOT_RUN — needs §7.1's fitness books; §94.3 counted exactly one "
                         "own-generated text long enough to carry a slope",
}


@dataclass(frozen=True, slots=True)
class Fiction:
    work_id: str
    author: str
    conversion: float
    views: float
    chapters: int
    chapter_ids: tuple[str, ...]


# ---------------------------------------------------------------------------------- survey


def survey(shards: Sequence[int], *, limit_per_fiction: int = CHAPTERS) -> dict[str, Any]:
    """Which cached fictions carry enough consecutive chapters to hold a learnability slope?

    Metadata columns only — the `text` column is the 497MB half of each shard, and counting
    chapters per fiction does not need a word of prose. The text is fetched later, and only for
    the fictions the pairing actually selects.
    """
    import pyarrow.parquet as pq
    from corpus_io import AI_WARNING, GENRE_TAG, PRE_LLM_YEAR, _shard_path

    columns = [
        "tags", "warnings", "release_datetime", "fiction_id", "chapter_id",
        "followers", "total_views", "author", "average_views",
    ]
    per_fiction: dict[str, dict[str, Any]] = {}
    for shard in shards:
        table = pq.read_table(_shard_path(shard), columns=columns)
        for row in table.to_pylist():
            if GENRE_TAG not in json.loads(row.get("tags") or "[]"):
                continue
            released = (row.get("release_datetime") or "")[:10]
            year = released[:4]
            if not year or year >= PRE_LLM_YEAR:
                continue
            if AI_WARNING in json.loads(row.get("warnings") or "[]"):
                continue
            views = float(row.get("total_views") or 0)
            if views < MIN_VIEWS:
                continue
            work = str(row.get("fiction_id"))
            entry = per_fiction.setdefault(work, {
                "work_id": work,
                "author": str(row.get("author") or ""),
                "views": views,
                "followers": float(row.get("followers") or 0),
                "average_views": float(row.get("average_views") or 0),
                "chapters": [],
            })
            entry["chapters"].append((released, str(row.get("chapter_id"))))
    out = []
    for entry in per_fiction.values():
        if len(entry["chapters"]) < limit_per_fiction:
            continue
        ordered = sorted(entry["chapters"])[:limit_per_fiction]
        out.append({
            "work_id": entry["work_id"],
            "author": entry["author"],
            "views": entry["views"],
            "followers": entry["followers"],
            "conversion": entry["followers"] / entry["views"] if entry["views"] else 0.0,
            "published_chapters": round(entry["views"] / entry["average_views"])
            if entry["average_views"] else 0,
            "chapter_ids": [chapter_id for _, chapter_id in ordered],
        })
    return {
        "shards": list(shards),
        "cohort": COHORT,
        "min_views": MIN_VIEWS,
        "chapters_required": limit_per_fiction,
        "fictions": sorted(out, key=lambda row: row["work_id"]),
    }


def pair_fictions(fictions: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """§79's two strata, on fictions instead of chapters, with the same tolerances.

    `aligned`: views matched to a factor of two, so the high-conversion side necessarily carries
    more followers and every popularity rule points AT the label. `crossed`: the high-conversion
    side carries fewer followers and fewer views, so every popularity rule points AWAY. A judge
    reading prose agrees in both; a judge proxying popularity cannot.
    """
    rows = [f for f in fictions if f["conversion"] > 0 and f["views"] > 0]
    rows.sort(key=lambda f: f["work_id"])
    used_work: set[str] = set()
    used_author: set[str] = set()
    pairs: list[dict[str, Any]] = []
    # **`crossed` is built FIRST, and the order is the whole difference between a two-stratum
    # test and a one-stratum one.** Both strata draw from one pool under a shared work/author
    # disjointness set, and `crossed` is far the scarcer: it needs the high-conversion side to
    # carry *fewer* views and *fewer* followers, which few matched pairs do. Building `aligned`
    # first — which this did — let it consume 392 of 585 fictions and left `crossed` with
    # **one pair**, measured. A force could then clear `aligned` by proxying popularity with
    # nothing to contradict it, which is precisely what §79's second stratum exists to prevent.
    for stratum in ("crossed", "aligned"):
        for i, high in enumerate(rows):
            if high["work_id"] in used_work or high["author"] in used_author:
                continue
            for low in rows[i + 1 :]:
                if low["work_id"] in used_work or low["author"] in used_author:
                    continue
                if high["author"] and high["author"] == low["author"]:
                    continue
                ratio = high["conversion"] / low["conversion"] if low["conversion"] else 0
                inverted = ratio < 1
                hi, lo = (low, high) if inverted else (high, low)
                ratio = ratio if not inverted else 1 / ratio
                if ratio < MIN_CONVERSION_RATIO:
                    continue
                view_gap = abs(math.log10(hi["views"] / lo["views"]))
                chapter_gap = abs(math.log10(
                    max(hi["published_chapters"], 1) / max(lo["published_chapters"], 1)
                ))
                if chapter_gap > MAX_LOG_CHAPTER_GAP:
                    continue
                if stratum == "aligned":
                    if view_gap > MAX_LOG_VIEW_GAP:
                        continue
                elif not (hi["views"] < lo["views"] and hi["followers"] < lo["followers"]):
                    continue
                pairs.append({
                    "pair_id": f"f3-{stratum}{len(pairs)}",
                    "stratum": stratum,
                    "high": hi,
                    "low": lo,
                    "conversion_ratio": round(ratio, 4),
                    "log_view_gap": round(view_gap, 4),
                })
                used_work.update({hi["work_id"], lo["work_id"]})
                used_author.update({hi["author"], lo["author"]})
                break
    return pairs


def chapter_texts(shards: Sequence[int], wanted: set[str]) -> dict[str, str]:
    """Fetch the prose for exactly the chapters the pairing selected. Never written out."""
    import pyarrow.parquet as pq
    from corpus_io import _shard_path

    out: dict[str, str] = {}
    for shard in shards:
        table = pq.read_table(_shard_path(shard), columns=["chapter_id", "text"])
        for row in table.to_pylist():
            key = str(row.get("chapter_id"))
            if key in wanted:
                out[key] = row.get("text") or ""
    return out


# --------------------------------------------------------------------------------- scoring


def learnability_slope(
    family: str,
    chapters: Sequence[str],
    foreign: str,
    cache: Checkpoint,
    governor: force_gpu.Governor,
    *,
    shuffled: bool = False,
    replicate: bool = False,
) -> float | None:
    """The slope over j. `foreign` is another fiction's prose, truncated to matched length.

    `replicate` changes nothing about the computation and everything about the cache key. It is
    what makes F3's placebo an actual measurement rather than a dictionary lookup: without it,
    scoring the same chapters twice returns the same stored row and the placebo reads zero by
    construction — the failure already retracted once in this ledger. With it, the second pass
    is a fresh set of forward passes over byte-identical input, and a non-zero difference is a
    real statement about the stack's determinism.
    """
    target = chapters[-1]
    body = list(chapters[:-1])
    if shuffled:
        # Deterministic reversal rather than a random shuffle: a random order would make the
        # control non-deterministic and its own re-runs incomparable, which is `surprisal`'s
        # reasoning for fixed foreign offsets applied to chapter order.
        body = body[::-1]
    model_id, revision = force_gpu.resolve(family, "base")
    xs: list[float] = []
    ys: list[float] = []
    for j in LADDER:
        if j > len(body):
            continue
        true_context = "\n\n".join(body[:j])
        tokens = force_gpu.count_tokens(family, true_context)
        foreign_context = force_gpu.repeat_to_tokens(family, foreign, tokens)
        # The ceiling is read from the family's own config rather than remembered. A rung that
        # does not fit is **not** truncated: it aborts the whole fiction, because a truncated
        # top rung beside an untruncated bottom one is a level artifact re-entering the slope,
        # and subtracting that artifact is F3's entire reason to exist (§58).
        budget = force_gpu.context_limit(family) - force_gpu.count_tokens(family, target) - 256
        if tokens > budget:
            return None
        key = unit_key(
            "f3", model_id, revision, digest(target), digest(true_context),
            digest(foreign_context), j, shuffled, budget, replicate,
        )
        row = cache.get(key)
        if row is None:
            true_lp, _ = force_gpu.token_logprobs(
                family, true_context + "\n\n", target, head="base", governor=governor,
                max_prefix_tokens=budget,
            )
            foreign_lp, _ = force_gpu.token_logprobs(
                family, foreign_context + "\n\n", target, head="base", governor=governor,
                max_prefix_tokens=budget,
            )
            row = cache.put(key, {
                "nll_true": -statistics.fmean(true_lp) if true_lp else None,
                "nll_foreign": -statistics.fmean(foreign_lp) if foreign_lp else None,
                "context_tokens": tokens,
                "prefix_budget": budget,
                "prefix_truncated": tokens > budget,
            })
        if row["nll_true"] is None or row["nll_foreign"] is None:
            continue
        xs.append(float(j))
        ys.append(row["nll_foreign"] - row["nll_true"])
    if len(xs) < 3:
        return None
    slope = ols_slope(xs, ys)
    return None if math.isnan(slope) else slope


def ladder_fits(family: str, chapters: Sequence[str]) -> bool:
    """Does every rung of this fiction's ladder fit under `family`'s position ceiling?

    Tokenizer only — no weights, no CUDA — so this can run over the whole corpus before a single
    forward pass. Both chapter orders are checked because the shuffled arm reverses the body, so
    `body[:j]` and `body[::-1][:j]` are different chapters and different token counts.
    """
    if len(chapters) < 2:
        return False
    target, body = chapters[-1], list(chapters[:-1])
    budget = force_gpu.context_limit(family) - force_gpu.count_tokens(family, target) - 256
    for order in (body, body[::-1]):
        for j in LADDER:
            if j > len(order):
                continue
            if force_gpu.count_tokens(family, "\n\n".join(order[:j])) > budget:
                return False
    return True


def fit_filter(
    pairs: Sequence[dict[str, Any]],
    texts: dict[str, str],
    families: Sequence[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split the pairs into those every family can carry and those at least one cannot.

    **The ceiling has to bite on both families at once or the two arms are reading different
    corpora.** The abort used to live inside `learnability_slope`, which returns `None` for any
    reason at all, and the only drop message the caller could write was *"a side had missing
    chapters"*. On the real 191 pairs — with all 3,056 chapter texts present — Qwen loses 56
    pairs to its 32,768-position ceiling and gemma loses none: 29% of `aligned` and 34% of
    `crossed` would have existed for one family only, every one of them filed under a cause that
    was not true, and `combine_families` would then have compared two different substrates while
    reporting a lineage disagreement.

    So the ceiling is measured before any forward pass, a fiction either family cannot carry is
    dropped for **both**, and the cause is recorded as the ceiling rather than as missing text.
    """
    kept: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for pair in pairs:
        offenders = []
        for side in ("high", "low"):
            chapters = [texts.get(cid, "") for cid in pair[side]["chapter_ids"]]
            if any(not c for c in chapters):
                offenders.append({"side": side, "why": "a chapter's text was not in the shards"})
                continue
            for family in families:
                if not ladder_fits(family, chapters):
                    offenders.append({
                        "side": side, "family": family,
                        "why": f"the top rung exceeds {family}'s position ceiling; truncating it "
                               "would put a level artifact back into the slope",
                    })
        if offenders:
            excluded.append({
                "pair_id": pair["pair_id"], "stratum": pair["stratum"], "offenders": offenders,
            })
        else:
            kept.append(pair)
    return kept, excluded


def donor_prose(
    pairs: Sequence[dict[str, Any]], index: int, texts: dict[str, str]
) -> str:
    """The foreign context for pair `index`: the next pair's high side, whole rather than one
    chapter.

    Two defects in the line this replaces, both of which put a systematic artifact into the
    slope F3 exists to read.

    **The rotation could select the fiction itself.** `pairs[(index + 1) % len(pairs)]` is
    `pairs[0]` when there is one pair, so a single-pair run scored a fiction against its own
    first chapter — pinning the j=1 rung to exactly 0.0 on the high side and on no other side.
    Reachable with `--max-pairs 1` and with `--max-fictions` in {11, 12, 13}. Fewer than two
    pairs now yields no donor at all and the pair drops, because there is no honest foreign
    context to be had.

    **One chapter was repeated to fill every rung, and the repetition count grew with j.**
    `repeat_to_tokens` tiles its input, so a donor of one chapter was tiled a mean 2.27 times at
    j=1 and 12.86 times at j=7 — growing on 380 of 382 sides, differing between the two sides of
    171 of 191 pairs, and growing faster on the high-conversion side in ~60% of them. Repetition
    is itself extremely predictable prose, so `NLL_foreign` fell with j for a reason that has
    nothing to do with the fiction under test; measured on GPU the pure artifact is 2-5% of the
    slope, pointed the same way as the hypothesis. Handing over the donor's whole body means the
    ladder is filled with real prose and `repeat_to_tokens` tiles only when a rung outruns it.
    """
    if len(pairs) < 2:
        return ""
    donor = pairs[(index + 1) % len(pairs)]["high"]
    chapters = [texts.get(cid, "") for cid in donor["chapter_ids"]]
    return "\n\n".join(c for c in chapters if c)


def run_controls(
    family: str,
    pairs: Sequence[dict[str, Any]],
    texts: dict[str, str],
    cache: Checkpoint,
    governor: force_gpu.Governor,
    args: argparse.Namespace,
) -> dict[str, Any]:
    """§1.3's two controls, in the units this force actually reads.

    F1 and FX build their controls from `placebo_pairs`/`sham_pairs`, which take a pair of
    *strings*. F3's side is not a string — it is an ordered list of chapters, and the statistic
    is a slope over how much of that list the model has seen. So the controls are rebuilt at
    this grain rather than borrowed at the wrong one:

        placebo_identical   the same chapter list, scored twice through the same path under a
                            replicate cache key. Byte-identical input, two independent sets of
                            forward passes; the difference must be zero to `--placebo-tolerance`,
                            which `determinism_probe.py` measures *before* any force runs.
        rewhitespace_sham   the same chapter list against a re-whitespaced copy of itself. Not
                            one character of any word changes, so a force reading prose has no
                            reason to prefer either side and must land on an interval containing
                            0.50.

    **The sham is a real control here, unlike F1's.** F1's feature space was measured blind to
    layout — 100 of 100 sham pairs produced byte-identical feature rows — so its sham certified
    nothing and says so in the report. F3's statistic is teacher-forced NLL over *tokens*, and
    re-whitespacing changes tokenisation directly. This control can fail, which is the only
    property that makes running it worth the forward passes.

    Both controls are drawn from the HIGH side, so neither introduces a comparison that could be
    mistaken for a reading, and both are drawn by `stratified_subsample`, so neither lands
    entirely inside `aligned`.
    """
    picks = stratified_subsample(as_force_pairs_static(pairs), args.controls)
    wanted = {p.pair_id for p in picks}
    placebo_effect = 0.0
    placebo_read = 0
    sham_scores: dict[str, dict[str, float]] = {}
    sham_members: list[ForcePair] = []
    for index, pair in enumerate(pairs):
        if pair["pair_id"] not in wanted:
            continue
        donor_text = donor_prose(pairs, index, texts)
        chapters = [texts.get(cid, "") for cid in pair["high"]["chapter_ids"]]
        if not donor_text or any(not c for c in chapters):
            continue
        base = learnability_slope(family, chapters, donor_text, cache, governor)
        if base is None:
            continue
        again = learnability_slope(
            family, chapters, donor_text, cache, governor, replicate=True
        )
        if again is not None:
            placebo_effect = max(placebo_effect, abs(base - again))
            placebo_read += 1
        shammed = [rewhitespace(c, 1.0) for c in chapters]
        if shammed == chapters:
            # A transform that changed nothing is a placebo wearing a sham's name: it
            # contributes a guaranteed tie and dilutes the denominator this control is read on.
            continue
        sham_slope = learnability_slope(family, shammed, donor_text, cache, governor)
        if sham_slope is None:
            continue
        sham_scores[f"sham:{pair['pair_id']}"] = {"high": base, "low": sham_slope}
        sham_members.append(ForcePair(
            pair_id=f"sham:{pair['pair_id']}", stratum="rewhitespace_sham", high="", low="",
        ))

    if placebo_read == 0:
        placebo = {
            "control": "placebo_identical",
            "status": "NOT_SCREENABLE",
            "pairs": 0,
            "why": "no control fiction produced a slope on either pass, so the arithmetic check "
                   "never happened; a run in this state is unscreened, not clean",
        }
    else:
        placebo = control_verdict(
            "placebo_identical", placebo_effect,
            tolerance=args.placebo_tolerance, kind="exact",
        )
        placebo["pairs"] = placebo_read
    return {
        "placebo_identical": placebo,
        "rewhitespace_sham": {
            **sham_verdict("rewhitespace_sham", *pair_agreement(sham_scores, sham_members)),
            "note": "unlike F1's, this sham can fail: F3's statistic is token-level NLL and "
                    "re-whitespacing changes tokenisation, so a PASS here is evidence rather "
                    "than a restatement of the feature space's blindness",
        },
    }


def as_force_pairs_static(subset: Sequence[dict[str, Any]]) -> list[ForcePair]:
    """The pair records carry their prose by reference; the harness only needs id and stratum."""
    return [
        ForcePair(pair_id=p["pair_id"], stratum=p["stratum"], high="", low="")
        for p in subset
    ]


def run_family(
    family: str,
    pairs: Sequence[dict[str, Any]],
    texts: dict[str, str],
    args: argparse.Namespace,
) -> dict[str, Any]:
    governor = force_gpu.Governor(rest_ratio=args.rest_ratio)
    DERIVED.mkdir(parents=True, exist_ok=True)
    cache = Checkpoint(DERIVED / f"f3-{family}.jsonl")

    scores: dict[str, dict[str, float]] = {}
    shuffled_scores: dict[str, dict[str, float]] = {}
    dropped: list[dict[str, Any]] = []
    for index, pair in enumerate(pairs):
        donor_text = donor_prose(pairs, index, texts)
        if not donor_text:
            dropped.append({"pair_id": pair["pair_id"], "why": "no donor text"})
            continue
        row: dict[str, float] = {}
        shuffled_row: dict[str, float] = {}
        for side in ("high", "low"):
            chapters = [texts.get(cid, "") for cid in pair[side]["chapter_ids"]]
            if any(not c for c in chapters):
                continue
            slope = learnability_slope(family, chapters, donor_text, cache, governor)
            if slope is not None:
                row[side] = slope
            shuffled = learnability_slope(
                family, chapters, donor_text, cache, governor, shuffled=True
            )
            if shuffled is not None:
                shuffled_row[side] = shuffled
        if len(row) == 2:
            scores[pair["pair_id"]] = row
        else:
            dropped.append({"pair_id": pair["pair_id"], "why": "a side had missing chapters"})
        if len(shuffled_row) == 2:
            shuffled_scores[pair["pair_id"]] = shuffled_row

    as_force_pairs = as_force_pairs_static

    report: dict[str, Any] = {
        "family": force_gpu.family_provenance(family, "base"),
        "governor": governor.report(),
        "cache": cache.provenance(),
        "dropped": dropped,
    }
    report.update(run_controls(family, pairs, texts, cache, governor, args))

    for label in ("aligned", "crossed"):
        members = as_force_pairs([p for p in pairs if p["stratum"] == label])
        if not members:
            continue
        # `binding=True` and `n_before_drops` are not optional. Without them F3's strata bypass
        # MIN_REFUTING_N, so at the n this substrate yields the arm could emit a FAIL that §95.9
        # already claims it cannot — the claim was true of the intent and false of the code.
        report[label] = verdict(
            label, *pair_agreement(scores, members),
            n_before_drops=len(members), binding=True,
        )
        report[f"{label}__shuffled_DIAGNOSTIC"] = verdict(
            label, *pair_agreement(shuffled_scores, members),
            n_before_drops=len(members), binding=True,
        )
    # `stratified_subsample` rather than a head slice. `pair_fictions` emits crossed-first, so
    # `pairs[:20]` drew twenty crossed pairs and zero aligned — a "directive cap" reading that
    # was a single-stratum reading with the directive's name on it. Every other track already
    # used this function; this was the one call site that did not.
    capped = stratified_subsample(as_force_pairs(pairs), CAP_FICTIONS // 2)
    if capped:
        report["directive_cap_40_fictions"] = verdict(
            "cap40", *pair_agreement(scores, capped),
            n_before_drops=len(capped), binding=True,
        )
    # **The arm's status is read off its controls, never written as a literal.** The line this
    # replaces was `report["status"] = "READ"`, and it made the two strata the whole of F3's
    # evidence: a statistic that counted newlines and nothing else published
    # `aligned PASS / crossed PASS / status READ` and fired the headline sentence, while the
    # same statistic VOIDed in F1, F2 and FX — which run their controls.
    verdict_from_controls = arm_status({
        "placebo_identical": report["placebo_identical"],
        "rewhitespace_sham": report["rewhitespace_sham"],
    })
    report["status"] = verdict_from_controls["status"]
    if verdict_from_controls.get("why"):
        report["why"] = verdict_from_controls["why"]
    report["control_states"] = verdict_from_controls["controls"]
    return report


def run(args: argparse.Namespace) -> dict[str, Any]:
    shards = tuple(args.shards)
    if SURVEY.is_file() and not args.resurvey:
        surveyed = json.loads(SURVEY.read_text(encoding="utf-8"))
    else:
        surveyed = survey(shards)
        DERIVED.mkdir(parents=True, exist_ok=True)
        SURVEY.write_text(json.dumps(surveyed, indent=2, sort_keys=True), encoding="utf-8")
    fictions = surveyed["fictions"][: args.max_fictions] if args.max_fictions \
        else surveyed["fictions"]
    pairs = pair_fictions(fictions)
    if args.max_pairs:
        pairs = pairs[: args.max_pairs]
    if not pairs:
        return provenance(
            track="F3",
            pre_registration_track=PRE_REGISTRATION,
            status="NOT_SCREENABLE",
            reading="no fiction pairs qualified; the substrate cannot carry this arm at these "
                    "tolerances, which is a fact about the cached shards and is recorded as one",
            surveyed_fictions=len(surveyed["fictions"]),
        )

    wanted = {cid for p in pairs for side in ("high", "low") for cid in p[side]["chapter_ids"]}
    texts = chapter_texts(shards, wanted)
    offered = len(pairs)
    pairs, excluded = fit_filter(pairs, texts, args.families)
    if not pairs:
        return provenance(
            track="F3",
            pre_registration_track=PRE_REGISTRATION,
            status="NOT_SCREENABLE",
            reading="every qualifying pair exceeded a family's position ceiling or was missing "
                    "chapter text; no fiction survives to be read",
            surveyed_fictions=len(surveyed["fictions"]),
            pairs_offered=offered,
            excluded_before_scoring=excluded,
        )

    per_family = {}
    for family in args.families:
        per_family[family] = run_family(family, pairs, texts, args)
        force_gpu.free()

    sizes = {
        "aligned": sum(1 for p in pairs if p["stratum"] == "aligned"),
        "crossed": sum(1 for p in pairs if p["stratum"] == "crossed"),
    }
    # Printed beside `stratum_sizes` rather than folded into it: the bar is computed at the n
    # that was actually read, and a reader can still see how much of the corpus the ceiling took.
    excluded_sizes = {
        label: sum(1 for e in excluded if e["stratum"] == label)
        for label in ("aligned", "crossed")
    }
    combined = {label: combine_families(per_family, label) for label in ("aligned", "crossed")}
    # The conjunction is over the fixed pair of binding strata, never over "the ones that have
    # members" — an empty stratum used to drop out, so a run with `crossed` empty could PASS on
    # `aligned` alone, which is the one thing §79's two-stratum design exists to prevent.
    headline = headline_verdict(per_family, combined)
    return provenance(
        track="F3",
        pre_registration_track=PRE_REGISTRATION,
        surveyed_fictions=len(surveyed["fictions"]),
        # `--survey-only` used to report the unsliced corpus while `run()` sliced at
        # `--max-fictions` before pairing, so the two paths described different experiments and
        # the ledger quoted the wrong one: 191 pairs (118/73) from the survey against the 64
        # (41/23) the documented full-run command actually builds. Both numbers now print, and
        # the cap that produced the gap prints with them.
        max_fictions=args.max_fictions,
        fictions_after_cap=len(fictions),
        pairs_offered=offered,
        pairs=len(pairs),
        stratum_sizes=sizes,
        stratum_sizes_excluded_by_ceiling=excluded_sizes,
        excluded_before_scoring=excluded,
        attainability=attainability_table(sizes),
        chapters_fetched=len(texts),
        per_family=per_family,
        combined=combined,
        force_verdict=headline["verdict"],
        force_verdict_detail=headline,
        own_generated_arm={
            "status": "NOT_RUN",
            "price": "~$81 of frontier drafting (operator §7.1: FUND) for twenty own-generated "
                     "texts; §94.3 counted exactly one in this repository",
            "why": "F3's eventual real target is own-generated books, and a third-party-only "
                   "reading is a statement about RoyalRoad rather than about what this system "
                   "writes",
        },
    )


def selftest() -> int:
    failures: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            failures.append(message)

    made = [
        {"work_id": "a", "author": "A", "conversion": 0.010, "views": 50_000,
         "followers": 500.0, "published_chapters": 40},
        {"work_id": "b", "author": "B", "conversion": 0.002, "views": 55_000,
         "followers": 110.0, "published_chapters": 42},
        {"work_id": "c", "author": "C", "conversion": 0.020, "views": 12_000,
         "followers": 240.0, "published_chapters": 41},
        {"work_id": "d", "author": "D", "conversion": 0.004, "views": 90_000,
         "followers": 360.0, "published_chapters": 39},
    ]
    pairs = pair_fictions(made)
    strata = {p["stratum"] for p in pairs}
    check("aligned" in strata, f"an aligned pair must be found: {pairs}")
    for pair in pairs:
        check(pair["high"]["conversion"] > pair["low"]["conversion"], "high side must convert")
        check(pair["high"]["author"] != pair["low"]["author"], "authors must be disjoint")
        if pair["stratum"] == "crossed":
            check(pair["high"]["views"] < pair["low"]["views"], "crossed must invert views")
            check(
                pair["high"]["followers"] < pair["low"]["followers"],
                "crossed must invert followers",
            )
    works = [p[s]["work_id"] for p in pairs for s in ("high", "low")]
    check(len(works) == len(set(works)), "fictions must be disjoint across pairs")

    thin = [dict(made[0]), dict(made[1])]
    thin[1]["conversion"] = 0.009  # ratio 1.1, below the declared floor
    check(not pair_fictions(thin), "a sub-2x conversion gap must not pair")

    for message in failures:
        print(f"FAIL {message}")
    print(f"compression_progress selftest: {len(failures)} failures")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--survey-only", action="store_true")
    parser.add_argument("--resurvey", action="store_true")
    parser.add_argument("--shards", nargs="+", type=int,
                        default=[1, 2, 3, 4, 5, 6, 28, 29, 30, 31, 32, 33])
    parser.add_argument("--families", nargs="+", default=list(FAMILIES))
    parser.add_argument("--max-fictions", type=int, default=EXTENSION_FICTIONS)
    parser.add_argument("--max-pairs", type=int, default=0)
    parser.add_argument("--rest-ratio", type=float, default=force_gpu.DEFAULT_REST_RATIO)
    # 20 rather than 12: `MIN_SCREENING_N` is a floor on *decided* sham pairs, and this arm
    # drops a control fiction whenever its donor, its chapters or its ladder fall through. A
    # count set at the floor arrives below it.
    parser.add_argument("--controls", type=int, default=20)
    # 0.0 is the honest default on a deterministic local stack and is *checked*, not assumed:
    # `determinism_probe.py` runs before any force and writes the measured replay-noise scale.
    parser.add_argument("--placebo-tolerance", type=float, default=0.0)
    parser.add_argument("--out", default=str(RESULTS / "force-f3.json"))
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.survey_only:
        surveyed = survey(tuple(args.shards))
        DERIVED.mkdir(parents=True, exist_ok=True)
        SURVEY.write_text(json.dumps(surveyed, indent=2, sort_keys=True), encoding="utf-8")
        # **The same slice `run()` applies, because a survey that describes a different corpus
        # than the run is a survey of nothing.** This path reported the whole surveyed set while
        # `run()` cut to `--max-fictions` before pairing, so the shape the ledger quoted (191
        # pairs, 118/73, bars 0.6017/0.6301) was never the shape the documented full-run command
        # builds (64 pairs, 41/23, bars 0.6829/0.7391). Both print now, and the difference is
        # the cap rather than a discrepancy a reader has to discover.
        uncapped = pair_fictions(surveyed["fictions"])
        capped_fictions = surveyed["fictions"][: args.max_fictions] if args.max_fictions \
            else surveyed["fictions"]
        pairs = pair_fictions(capped_fictions)

        def shape(subset: Sequence[dict[str, Any]]) -> dict[str, int]:
            return {
                s: sum(1 for p in subset if p["stratum"] == s) for s in ("aligned", "crossed")
            }

        print(json.dumps({
            "fictions_surveyed": len(surveyed["fictions"]),
            "max_fictions": args.max_fictions,
            "fictions_after_cap": len(capped_fictions),
            "pairs": len(pairs),
            "per_stratum": shape(pairs),
            "attainability": attainability_table(shape(pairs)),
            "uncapped_pairs": len(uncapped),
            "uncapped_per_stratum": shape(uncapped),
            "uncapped_attainability": attainability_table(shape(uncapped)),
            "note": "the capped shape is what a run reads; the uncapped shape is what the "
                    "substrate could yield if EXTENSION_FICTIONS were raised, which is a "
                    "decision and not a default",
        }, indent=2))
        return 0

    report = run(args)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report.get("combined", report), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
