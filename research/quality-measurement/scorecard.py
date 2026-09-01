"""The per-draw scorecard: one book's published chapters, every code-only row, beside its market
reference where one is recorded and a stated reason where none is.

    uv run python research/quality-measurement/scorecard.py book-library/what-the-kettle-remembers
    uv run python research/quality-measurement/scorecard.py <a chapter>.txt --out card.json

**It describes and it does not judge.** There is no aggregate score, no pass/fail column, no
threshold and no bar anywhere in this file, and that is a governance line rather than a
simplification: stage-0 §61's four attainability checks — range at the real n, direction,
independent unit, non-empty subgroup — stand between any row here and a bar, and none of them
has been run for any of these quantities. §81, §85, §87 and §89 each declared a bar over a
quantity that could not carry one. A row saying *0.16 against a market mean of 0.03* is a
description of two numbers; it is not a verdict, and nothing downstream may read it as one.
§61(5) holds too: no model ranks anything here, because no model runs here at all.

**No new metric is minted.** Every counter comes from `chapter_measures.battery`, which lifted
them verbatim from the draw-battery runner. This file adds the reference column and the table.

**No model reads anything.** Regex and arithmetic, end to end. No corpus is opened — the market
figures below are transcribed constants from results files already committed to this repo — so
RS1 is untouched, and nothing under `src/litharness/` imports this module (CONTRIBUTING's
dependency direction; the research side may read the package, never the other way).

## The reference column, and the four reasons a row does not get one

1. **A recorded market half exists** — the row carries it, with the population, the n, the
   results file it was read out of and the instrument digest it was computed under.
2. **`v2 incomparable`** — stage-0 §189.3: *"No v2 number may be placed beside any market
   number, and none is."* Every published market figure for `progression_cadence` and
   `number_context` is v0's; neither market half has been re-run under v2. v2 adds an accepted
   line shape and removes none, so it can only ever find *more* furniture — a v2 house count
   against a v0 market distribution overstates our position by an amount nobody has measured.
   The invalidity runs in the direction that flatters us, which is why it is refused outright
   rather than caveated. The v0 rows beside them are the ones the market numbers belong to.
3. **No market half was recorded** — §180.1's sentence, join and em-dash census ran on this
   shelf only. The row is real; there is simply nothing on the other side of it.
4. **The counter is a reimplementation** — §180.1's chain script "is not kept", so the chain
   rows are not comparable with §180.1's own published levels either, only with each other.

One reference carries a limitation instead of a refusal, and it is stated in the row: the
system-line market figures were computed by `research/quality-measurement/system_lines.py` over
`domain/axes._SYSTEM_LINE`, and **neither file is in the tree any more**. This module counts
`[STATUS]` lines with `statusline.parse_status_line`, the renderer's own parser, which is the
stricter of the two — it demands a subject and at least one labelled cell where the market
counter demanded only a leading bracketed token. Stricter on our side understates us against a
reference we already sit far above, so the row is printed with the mismatch named rather than
dropped. Re-deriving it would cost a market pass with a counter that no longer exists.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import textwrap
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import chapter_measures  # noqa: E402

# --------------------------------------------------------------------------------- references

#: Instrument digests, so a reference names the counter that produced it and not just a number.
#: A later edit to any of these modules rotates its digest and the mismatch is visible here.
DIGEST_CADENCE_V0 = "5d42f2065efb7e09"
DIGEST_CADENCE_V2 = "f1a205af2cd3d718"
DIGEST_NUMBERS_V0 = "8e10ac598828d404"
DIGEST_NUMBERS_V2 = "6c007094f6159474"
DIGEST_REGISTER_V0 = "2029fc350b1e6684"

#: The §61 line, carried in the JSON so a consumer that never reads this docstring still gets it.
NO_BAR = (
    "Descriptive only. No aggregate score, no pass/fail, no threshold, no bar: stage-0 §61's "
    "four attainability checks (range at the real n, direction, independent unit, non-empty "
    "subgroup) stand between any row here and a bar, and none has been run for any of these "
    "quantities. No model ranked, selected or judged anything (§61(5)); no model ran at all."
)

NO_REF_V2 = (
    "no market reference (v2 incomparable with the v0 census — stage-0 §189.3: every published "
    "market figure for this instrument is v0's, and v2 can only ever find more furniture)"
)
NO_REF_OURS_ONLY = (
    "no market reference (§180.1's census covered this shelf only; no market half was recorded)"
)
NO_REF_REIMPLEMENTED = (
    "no market reference (§180.1's chain script was not kept, so this counter is a "
    "REIMPLEMENTATION and is not comparable with §180.1's own published levels either)"
)
NO_REF_HOUSE = "no market reference (a house rail; nothing in the market corresponds to it)"
NO_REF_UNIT = (
    "no market reference (the recorded market half for this counter is a rate per 1,000 words, "
    "not a per-chapter count; see the per-1k row beside this one)"
)


@dataclass(frozen=True)
class Reference:
    """One recorded market number, addressed by where it was recorded and what computed it."""

    value: float
    unit: str
    population: str
    n: int
    source: str
    digest: str = ""
    spread: str = ""
    caveat: str = ""

    def render(self) -> str:
        parts = [f"{self.value:g} {self.unit}"]
        if self.spread:
            parts.append(f"({self.spread})")
        parts.append(f"[{self.population}, n={self.n}]")
        return " ".join(parts)


#: Every market reference this scorecard can print, transcribed from committed results files.
#: The key is the scorecard row it belongs to. Each was read back out of its source file during
#: the build; `tests/test_scorecard.py` re-reads the two that live in machine-readable JSON.
REFERENCES: dict[str, Reference] = {
    "prose_words": Reference(
        value=2053,
        unit="words",
        population="market LitRPG chapters",
        n=13364,
        source="stage-0 §155.1 length control; research/quality-measurement/"
        "progression-cadence-results.md",
        digest=DIGEST_CADENCE_V0,
        spread="median chapter length",
    ),
    # ---- register census, the gloss half (G1, narrating the inference)
    "gloss_tier_a_per_1k": Reference(
        value=0.0344,
        unit="hits/1k words",
        population="market LitRPG chapters",
        n=13364,
        source="research/quality-measurement/results/register-census.json "
        "gloss_per_1k['market_litrpg|tier_a']; read in stage-0 §156.2",
        digest=DIGEST_REGISTER_V0,
        spread="mean; median 0.0, 93.3% of chapters at zero",
    ),
    "gloss_tier_b_per_1k": Reference(
        value=0.0027,
        unit="hits/1k words",
        population="market LitRPG chapters",
        n=13364,
        source="research/quality-measurement/results/register-census.json "
        "gloss_per_1k['market_litrpg|tier_b']; read in stage-0 §156.2",
        digest=DIGEST_REGISTER_V0,
        spread="mean; median 0.0, 99.4% of chapters at zero",
    ),
    # ---- register census, the proper-noun half (C4, too many names / cast)
    "proper_nouns_per_1k": Reference(
        value=37.8184,
        unit="distinct/1k words",
        population="market LitRPG chapters, friction sample",
        n=496,
        source="research/quality-measurement/results/register-census.json "
        "proper_noun_per_1k['market_litrpg']; read in stage-0 §156.3",
        digest=DIGEST_REGISTER_V0,
        spread="median; p10 11.68, p90 79.86",
        caveat="the counter is a strict superset of cast — it also catches places, "
        "institutions and system names — so this is proper nouns on both sides and cast on "
        "neither (§175 shipped a prompt bound and built no count of drafted prose)",
    ),
    # ---- progression cadence v0 (A1 flat/absent system numbers, C2 nothing happens)
    "cadence_v0_events_per_1k": Reference(
        value=0.0,
        unit="events/1k words",
        population="market LitRPG chapters",
        n=13364,
        source="stage-0 §155.1; research/quality-measurement/progression-cadence-results.md",
        digest=DIGEST_CADENCE_V0,
        spread="median; mean 1.224, p75 1.26, p90 3.60, p95 5.53",
    ),
    "cadence_v0_carries_any_event": Reference(
        value=0.490,
        unit="share of chapters",
        population="market LitRPG chapters",
        n=13364,
        source="stage-0 §155.1 coverage; 51.0% carry none, 6.50x the non-LitRPG control",
        digest=DIGEST_CADENCE_V0,
        spread="non-LitRPG control 0.128",
        caveat="§155.1 records this as a joint claim about the market and about the "
        "instrument's recall, and says that caveat travels with it wherever it is quoted",
    ),
    "cadence_v0_first_event_words": Reference(
        value=585,
        unit="words into the chapter",
        population="market LitRPG chapters carrying an event",
        n=13364,
        source="stage-0 §155.1; progression-cadence-results.md",
        digest=DIGEST_CADENCE_V0,
        spread="median; 22.5% of chapters have one inside the first 500 words",
    ),
    "cadence_v0_first_event_fraction": Reference(
        value=0.29,
        unit="fraction of the chapter",
        population="market LitRPG chapters carrying an event",
        n=13364,
        source="research/quality-measurement/progression-cadence-results.md",
        digest=DIGEST_CADENCE_V0,
        spread="median; p25 0.10, p75 0.56",
    ),
    "cadence_v0_gap_cv": Reference(
        value=0.96,
        unit="coefficient of variation",
        population="market LitRPG chapters with two or more events",
        n=4496,
        source="stage-0 §155.1; median gap 89 words (p25 31, p75 276)",
        digest=DIGEST_CADENCE_V0,
        spread="essentially Poisson",
    ),
    # ---- number context v0 (A1, A3 numbers on the wrong referent)
    "numbers_v0_mentions_per_1k": Reference(
        value=12.831,
        unit="mentions/1k words",
        population="market LitRPG chapters, pooled",
        n=13364,
        source="stage-0 §162.3; research/quality-measurement/number-context-results.md",
        digest=DIGEST_NUMBERS_V0,
    ),
    "numbers_v0_system_magnitude_per_1k": Reference(
        value=2.632,
        unit="per 1k words",
        population="market LitRPG chapters, pooled",
        n=13364,
        source="stage-0 §162.1; number-context-results.md",
        digest=DIGEST_NUMBERS_V0,
        spread="10.7x the non-LitRPG control (0.246); 55.5% of chapters carry one",
    ),
    "numbers_v0_system_ordinal_per_1k": Reference(
        value=0.104,
        unit="per 1k words",
        population="market LitRPG chapters, pooled",
        n=13364,
        source="stage-0 §162.2; number-context-results.md",
        digest=DIGEST_NUMBERS_V0,
        spread="non-genre 0.068; §162 records this as the one column our shelf was above",
    ),
    "numbers_v0_magnitude_share_of_anchored": Reference(
        value=0.2002,
        unit="share of anchored mentions",
        population="market LitRPG chapters",
        n=13364,
        source="stage-0 §162.2; the bounded genre reference (our shelf then read 0.0029)",
        digest=DIGEST_NUMBERS_V0,
        spread="non-genre 0.0323",
    ),
    "numbers_v0_mundane_core_per_1k": Reference(
        value=1.236,
        unit="per 1k words",
        population="market LitRPG chapters, pooled",
        n=13364,
        source="stage-0 §162.1/§162.3; number-context-results.md",
        digest=DIGEST_NUMBERS_V0,
        spread="non-LitRPG 1.121 (1.10x — §162 kept it as the non-discrimination check); "
        "25.4% of market chapters carry no mundane number at all",
    ),
    "numbers_v0_object_count_per_1k": Reference(
        value=4.113,
        unit="per 1k words",
        population="market LitRPG chapters, pooled",
        n=13364,
        source="stage-0 §162.3; number-context-results.md",
        digest=DIGEST_NUMBERS_V0,
    ),
    "numbers_v0_calendar_duration_per_1k": Reference(
        value=0.718,
        unit="per 1k words",
        population="market LitRPG chapters, pooled",
        n=13364,
        source="stage-0 §162.3; number-context-results.md — §162's concentrated excess",
        digest=DIGEST_NUMBERS_V0,
        spread="non-genre 0.724",
    ),
    # ---- the page contract (A1). Both carry the detector-mismatch limitation.
    "status_lines_per_1k": Reference(
        value=0.3181,
        unit="lines/1k words",
        population="RoyalRoad LitRPG chapters, shards 3+30",
        n=14156,
        source="research/quality-measurement/numbers-go-up-results.md §4 (Task 6)",
        spread="mean; median 0.0 — 97.7% of market chapters carry no system line at all",
        caveat="DETECTOR MISMATCH: the market half was counted by system_lines.py over "
        "domain/axes._SYSTEM_LINE, and neither file is in the tree any more",
    ),
    "carries_status_line": Reference(
        value=0.0232,
        unit="share of chapters with at least one",
        population="RoyalRoad LitRPG chapters, shards 3+30",
        n=14156,
        source="research/quality-measurement/numbers-go-up-results.md §4 (Task 6); "
        "within-story control 2.59% over 394 stories",
        spread="era split 8.29% declared-AI-2025 / 2.66% undeclared-2025 / 1.16% human-pre-LLM, "
        "from which that results file concludes nothing",
        caveat="DETECTOR MISMATCH: the market half was counted by system_lines.py over "
        "domain/axes._SYSTEM_LINE, and neither file is in the tree any more. This side uses "
        "statusline.parse_status_line, which is the stricter counter (it demands a subject and "
        "a labelled cell). Stricter on our side understates us against a reference we already "
        "sit far above, so the row is printed with the mismatch named rather than dropped",
    ),
    "status_number_moved": Reference(
        value=0.4375,
        unit="share of such chapters whose digits differ",
        population="RoyalRoad LitRPG chapters carrying two or more system lines",
        n=144,
        source="research/quality-measurement/numbers-go-up-results.md §4 (Task 6)",
        caveat="DETECTOR MISMATCH, as above; and the market counter compared digit sets on the "
        "line where this one compares the same subject's same-labelled cell between "
        "consecutive prints. The two ask nearly the same question and are not the same test",
    ),
}


# ------------------------------------------------------------------------------------- rows

#: How a row's per-chapter values become the book's value. Named per row so no column is
#: silently averaged when it should have been summed.
AGGREGATORS: dict[str, Callable[[Sequence[Any]], Any]] = {
    "sum": lambda xs: sum(x for x in xs if x is not None)
    if any(x is not None for x in xs)
    else None,
    "mean": lambda xs: round(statistics.fmean([x for x in xs if x is not None]), 4)
    if any(x is not None for x in xs)
    else None,
    "median": lambda xs: round(statistics.median([x for x in xs if x is not None]), 4)
    if any(x is not None for x in xs)
    else None,
    "max": lambda xs: max([x for x in xs if x is not None], default=None),
    "share": lambda xs: round(sum(1 for x in xs if x) / len(xs), 4) if xs else None,
    "any": lambda xs: any(bool(x) for x in xs),
    "union": lambda xs: sorted({item for x in xs for item in (x or [])}),
}


@dataclass(frozen=True)
class Row:
    """One measured quantity, its aggregation rule, its checklist family and where it came from."""

    key: str
    label: str
    unit: str
    instrument: str
    #: Path into `chapter_measures.battery`'s dict, dotted. Empty when `compute` is given.
    path: str
    agg: str
    #: For the four `number_context` families whose recorded market half is a **pooled rate per
    #: 1,000 words** while `battery` reports the family as a count. Putting the count beside the
    #: rate would be the unit mismatch §89 was written about, so the row converts instead. The
    #: conversion is `n * 1000 / prose_words` — the same one `battery` already applies to every
    #: other per-1k column, and no new quantity.
    compute: Callable[[dict[str, Any]], Any] | None = None
    #: The read-recurrence-map family code(s) this row bears on, or `()` for a context row.
    #: `plan/agent-impact/read-recurrence-map.md` §3 owns the family list and its counts.
    checklist: tuple[str, ...] = ()
    #: Filled from `REFERENCES` when a market half exists; otherwise one of the `NO_REF_*` reasons.
    no_reference: str = ""
    note: str = ""


def _family_per_1k(version: str, family: str) -> Callable[[dict[str, Any]], float | None]:
    """`family`'s count as a rate per 1,000 prose words, which is the unit its market half is in.

    The denominator is `prose_words` — the chapter with its `[STATUS]` lines and `* * *`
    separators dropped — because that is the text the v0 counter was run over. The market side
    pooled over whole market chapters, which carry no such furniture in 97.7% of cases
    (`numbers-go-up-results.md`), so the two denominators are close but not identical, and the
    difference is stated here rather than hidden in a ratio.
    """

    def measure(blob: dict[str, Any]) -> float | None:
        words = blob["prose_words"]
        if not words:
            return None
        return round(blob[version]["by_family"][family] * 1000 / words, 4)

    return measure


#: Every row this scorecard prints, in printing order. Each `path` names a key
#: `chapter_measures.battery` already produces; the four `compute` rows do the unit conversion
#: documented on `Row.compute` and nothing else.
ROWS: tuple[Row, ...] = (
    # ------------------------------------------------------------------ scale (context only)
    Row("prose_words", "prose words (system lines and separators dropped)", "words",
        "len(text.split()) on chapter_measures.prose_only", "prose_words", "median"),
    Row("file_words", "words in the published file", "words",
        "len(text.split())", "words", "median",
        no_reference="no market reference (the market length reference is measured on prose; "
        "see the prose_words row)"),
    # ------------------------------------------------------------------ G1 gloss
    Row("gloss_tier_a_per_1k", "narratorial gloss, tier A (understanding/meaning/asking)",
        "hits/1k prose words", f"register_census.gloss_counts v0 {DIGEST_REGISTER_V0}",
        "gloss.tier_a_per_1k", "mean", checklist=("G1",)),
    Row("gloss_tier_b_per_1k", "narratorial gloss, tier B (manner)", "hits/1k prose words",
        f"register_census.gloss_counts v0 {DIGEST_REGISTER_V0}", "gloss.tier_b_per_1k", "mean",
        checklist=("G1",)),
    Row("gloss_tier_a", "narratorial gloss, tier A, absolute", "hits",
        f"register_census.gloss_counts v0 {DIGEST_REGISTER_V0}", "gloss.tier_a", "sum",
        checklist=("G1",), no_reference=NO_REF_UNIT),
    Row("gloss_tier_b", "narratorial gloss, tier B, absolute", "hits",
        f"register_census.gloss_counts v0 {DIGEST_REGISTER_V0}", "gloss.tier_b", "sum",
        checklist=("G1",), no_reference=NO_REF_UNIT),
    # ------------------------------------------------------------------ C4 cast
    Row("proper_nouns_per_1k", "distinct proper nouns (NOT cast size)", "distinct/1k prose words",
        f"register_census.proper_nouns v0 {DIGEST_REGISTER_V0}", "proper_nouns_NOT_CAST.per_1k",
        "mean", checklist=("C4",)),
    Row("proper_nouns_distinct", "distinct proper nouns, absolute (NOT cast size)", "distinct",
        f"register_census.proper_nouns v0 {DIGEST_REGISTER_V0}", "proper_nouns_NOT_CAST.distinct",
        "max", checklist=("C4",), no_reference=NO_REF_UNIT),
    # ------------------------------------------------------------------ A1/C2 cadence, v0
    Row("cadence_v0_events", "progression events located, v0", "events",
        f"progression_cadence.measure v0 {DIGEST_CADENCE_V0}", "cadence.events", "sum",
        checklist=("A1", "C2"), no_reference=NO_REF_UNIT),
    Row("cadence_v0_events_per_1k", "progression events, v0", "events/1k file words",
        f"progression_cadence.measure v0 {DIGEST_CADENCE_V0}", "cadence.per_1k", "mean",
        checklist=("A1", "C2")),
    Row("cadence_v0_carries_any_event", "chapters carrying at least one located event, v0",
        "share of this book's chapters", f"progression_cadence.measure v0 {DIGEST_CADENCE_V0}",
        "cadence.events", "share", checklist=("A1", "C2")),
    Row("cadence_v0_first_event_words", "first located event, v0", "words into the chapter",
        f"progression_cadence.measure v0 {DIGEST_CADENCE_V0}", "cadence.first_event_words",
        "median", checklist=("A1", "B1")),
    Row("cadence_v0_first_event_fraction", "first located event, v0", "fraction of the chapter",
        f"progression_cadence.measure v0 {DIGEST_CADENCE_V0}", "cadence.first_event_fraction",
        "median", checklist=("A1", "B1")),
    Row("cadence_v0_gap_cv", "spacing of events, v0", "coefficient of variation",
        f"progression_cadence.measure v0 {DIGEST_CADENCE_V0}", "cadence.gap_cv", "median",
        checklist=("A1",),
        note="the instrument declines below three events and returns null; that is not a zero"),
    # ------------------------------------------------------------------ A1 cadence, v2
    Row("cadence_v2_events", "progression events located, v2", "events",
        f"progression_cadence.measure v2 {DIGEST_CADENCE_V2}", "cadence_v2.events", "sum",
        checklist=("A1", "C2"), no_reference=NO_REF_V2),
    Row("cadence_v2_events_per_1k", "progression events, v2", "events/1k file words",
        f"progression_cadence.measure v2 {DIGEST_CADENCE_V2}", "cadence_v2.per_1k", "mean",
        checklist=("A1", "C2"), no_reference=NO_REF_V2),
    Row("cadence_v2_first_event_fraction", "first located event, v2", "fraction of the chapter",
        f"progression_cadence.measure v2 {DIGEST_CADENCE_V2}", "cadence_v2.first_event_fraction",
        "median", checklist=("A1", "B1"), no_reference=NO_REF_V2),
    # ------------------------------------------------------------------ A1/A3 numbers, v0
    Row("numbers_v0_mentions_per_1k", "all numeric mentions, v0", "mentions/1k prose words",
        f"number_context.measure v0 {DIGEST_NUMBERS_V0} on prose", "numbers.mentions_per_1k",
        "mean", checklist=("A3",)),
    Row("numbers_v0_system_magnitude_per_1k", "system magnitude numbers, v0", "per 1k prose words",
        f"number_context.measure v0 {DIGEST_NUMBERS_V0} on prose", "", "mean",
        compute=_family_per_1k("numbers", "system_magnitude"), checklist=("A1",)),
    Row("numbers_v0_system_ordinal_per_1k", "system ordinal numbers, v0", "per 1k prose words",
        f"number_context.measure v0 {DIGEST_NUMBERS_V0} on prose", "", "mean",
        compute=_family_per_1k("numbers", "system_ordinal"), checklist=("A1",)),
    Row("numbers_v0_magnitude_share_of_anchored", "system share of anchored mentions, v0",
        "share", f"number_context.measure v0 {DIGEST_NUMBERS_V0} on prose",
        "numbers.system_share_of_anchored", "mean", checklist=("A1", "A3")),
    Row("numbers_v0_mundane_core_per_1k", "mundane core numbers, v0", "per 1k prose words",
        f"number_context.measure v0 {DIGEST_NUMBERS_V0} on prose", "numbers.mundane_per_1k",
        "mean", checklist=("A3",)),
    Row("numbers_v0_object_count_per_1k", "object counts, v0", "per 1k prose words",
        f"number_context.measure v0 {DIGEST_NUMBERS_V0} on prose", "", "mean",
        compute=_family_per_1k("numbers", "object_count"), checklist=("A3",)),
    Row("numbers_v0_calendar_duration_per_1k", "calendar and duration numbers, v0",
        "per 1k prose words", f"number_context.measure v0 {DIGEST_NUMBERS_V0} on prose", "",
        "mean", compute=_family_per_1k("numbers", "calendar_duration"), checklist=("A3",),
        note="§162.3 recorded this family as our shelf's concentrated numeric excess"),
    # ------------------------------------------------------------------ A1 numbers, v2
    Row("numbers_v2_system_any", "system numbers located, v2 (whole file)", "count",
        f"number_context.measure v2 {DIGEST_NUMBERS_V2}", "numbers_v2.system_any", "sum",
        checklist=("A1",), no_reference=NO_REF_V2),
    Row("numbers_v2_system_share_of_anchored", "system share of anchored mentions, v2", "share",
        f"number_context.measure v2 {DIGEST_NUMBERS_V2}", "numbers_v2.system_share_of_anchored",
        "mean", checklist=("A1", "A3"), no_reference=NO_REF_V2),
    Row("numbers_v2_mundane_core_per_1k", "mundane core numbers, v2", "per 1k prose words",
        f"number_context.measure v2 {DIGEST_NUMBERS_V2}", "numbers_v2.mundane_per_1k", "mean",
        checklist=("A3",), no_reference=NO_REF_V2,
        note="§189.2 records mundane_core, object_count and unanchored as byte-identical between "
        "v0-on-prose and v2-on-whole-file on all ten draws of the first battery, so the v0 row "
        "above is the one that carries the market comparison"),
    # ------------------------------------------------------------------ A1 the page contract
    Row("status_lines", "[STATUS] lines on the page", "lines",
        "statusline.parse_status_line", "status.status_lines", "sum", checklist=("A1",),
        no_reference=NO_REF_UNIT),
    Row("status_lines_per_1k", "[STATUS] lines on the page", "lines/1k prose words",
        "statusline.parse_status_line", "", "mean", checklist=("A1",),
        compute=lambda b: round(b["status"]["status_lines"] * 1000 / b["prose_words"], 4)
        if b["prose_words"]
        else None),
    Row("carries_status_line", "chapters carrying at least one [STATUS] line",
        "share of this book's chapters", "statusline.parse_status_line", "status.status_lines",
        "share", checklist=("A1",)),
    Row("status_number_moved", "a subject's own number changes between two prints",
        "true/false per chapter", "statusline.parse_status_line, same subject and same label "
        "compared between consecutive prints", "status.any_number_moved", "any",
        checklist=("A1",)),
    Row("status_cells_moved", "which cells moved", "list",
        "statusline.parse_status_line", "status.cells_moved", "union", checklist=("A1",),
        no_reference=NO_REF_HOUSE),
    Row("status_raw_id_subject", "a [STATUS] subject rendered as a raw record id", "list",
        "statusline.parse_status_line; the §169 defect is a subject carrying no capital",
        "status.raw_id_subject", "union", checklist=("A1",), no_reference=NO_REF_HOUSE),
    # ------------------------------------------------------------------ D2 sentence structure
    Row("sentence_words_median", "sentence length", "words",
        "voice.sentences + voice._WORD", "sentences.words_median", "median", checklist=("D2",),
        no_reference=NO_REF_OURS_ONLY),
    Row("sentence_words_max", "longest sentence", "words",
        "voice.sentences + voice._WORD", "sentences.words_max", "max", checklist=("D2",),
        no_reference=NO_REF_OURS_ONLY),
    Row("sentence_over_30_share", "sentences over 30 words", "share",
        "voice.sentences + voice._WORD", "sentences.over_30_share", "mean", checklist=("D2",),
        no_reference=NO_REF_OURS_ONLY),
    # ------------------------------------------------------------------ D1 and-chains
    Row("chain_joins_mean", "coordinated joins per sentence (commas plus free-standing 'and')",
        "joins/sentence", "REIMPLEMENTED from §180.1's own sentence; splitter is voice.sentences",
        "chains_REIMPLEMENTED.joins_mean", "mean", checklist=("D1",),
        no_reference=NO_REF_REIMPLEMENTED),
    Row("chain_4plus_share", "sentences carrying four or more joins", "share",
        "REIMPLEMENTED; the bound is §180.3's fourth action",
        "chains_REIMPLEMENTED.chained_4plus_share", "mean", checklist=("D1",),
        no_reference=NO_REF_REIMPLEMENTED),
    Row("chain_6plus", "sentences carrying six or more joins", "sentences",
        "REIMPLEMENTED", "chains_REIMPLEMENTED.chained_6plus", "sum", checklist=("D1",),
        no_reference=NO_REF_REIMPLEMENTED),
    # ------------------------------------------------------------------ D4 em dashes
    Row("em_dash_prose_per_1k", "em dashes in prose", "per 1k prose words",
        "voice.exhibition_census on chapter_measures.prose_only", "em_dash.prose_per_1k", "mean",
        checklist=("D4",), no_reference=NO_REF_OURS_ONLY),
    Row("em_dash_in_prose", "em dashes in prose, absolute", "dashes",
        "voice.exhibition_census on chapter_measures.prose_only", "em_dash.in_prose", "sum",
        checklist=("D4",), no_reference=NO_REF_OURS_ONLY,
        note="the [STATUS] line's own subject separator IS U+2014, so the file count is not this "
        "number; draft.strip_em_dash protects exactly those lines in production"),
    # ------------------------------------------------------------------ L1 schema leak
    Row("machinery_names_in_prose", "our own machinery vocabulary used as a proper noun", "list",
        "schema_words.named_in on prose", "machinery_names_in_prose", "union", checklist=("L1",),
        no_reference=NO_REF_HOUSE),
    # ------------------------------------------------------------------ instrument health
    Row("v2_mask_matches_pipeline", "the v2 furniture mask agrees with draft._SYSTEM_LINE",
        "true/false per chapter", "progression_cadence.prose_only v2 vs the pipeline's own rule",
        "v2_mask_matches_pipeline", "share",
        no_reference="no market reference (an instrument-health row, not a property of the book)",
        note="the research modules transcribe the pipeline's system-line shape rather than "
        "importing it; a value below 1.0 means the transcription has drifted"),
)


def _dig(blob: dict[str, Any], path: str) -> Any:
    cursor: Any = blob
    for part in path.split("."):
        cursor = cursor[part]
    return cursor


# ------------------------------------------------------------------------------------ inputs


def chapter_paths(target: Path) -> list[Path]:
    """The chapter files for a book directory, or the one file that was named.

    A book on the shelf is a directory with a `chapters/` folder of `ChapterN.txt`. Sorting is
    numeric on the trailing digits so `Chapter10` follows `Chapter9` rather than `Chapter1`.
    """
    if target.is_file():
        return [target]
    chapters = target / "chapters"
    if not chapters.is_dir():
        raise SystemExit(
            f"{target} is neither a chapter file nor a book directory with a chapters/ folder"
        )
    found = sorted(
        chapters.glob("*.txt"),
        key=lambda p: (int("".join(c for c in p.stem if c.isdigit()) or 0), p.stem),
    )
    if not found:
        raise SystemExit(f"no .txt chapters under {chapters}")
    return found


# ------------------------------------------------------------------------------------ build


@dataclass
class Scorecard:
    book: str
    path: str
    chapters: list[str]
    no_bar: str = NO_BAR
    rows: list[dict[str, Any]] = field(default_factory=list)
    per_chapter: dict[str, dict[str, Any]] = field(default_factory=dict)


def build(target: Path) -> Scorecard:
    """Measure every chapter, then lay each row beside its reference. No number is combined
    across rows and nothing is scored."""
    paths = chapter_paths(target)
    book_dir = target.parent if target.is_file() else target
    batteries = {
        path.stem: chapter_measures.battery(path.read_text(encoding="utf-8")) for path in paths
    }

    card = Scorecard(
        book=book_dir.name,
        path=str(target).replace("\\", "/"),
        chapters=[p.name for p in paths],
        per_chapter=batteries,
    )
    for row in ROWS:
        read = row.compute if row.compute is not None else (lambda b, p=row.path: _dig(b, p))
        values = [read(blob) for blob in batteries.values()]
        aggregated = AGGREGATORS[row.agg](values)
        record: dict[str, Any] = {
            "key": row.key,
            "label": row.label,
            "value": aggregated,
            "unit": row.unit,
            "aggregation": f"{row.agg} over {len(paths)} chapter(s)",
            "per_chapter": dict(zip(batteries, values, strict=True)),
            "instrument": row.instrument,
        }
        if row.checklist:
            record["checklist"] = list(row.checklist)
        reference = REFERENCES.get(row.key)
        if reference is not None:
            record["market_reference"] = asdict(reference)
            record["market_reference_rendered"] = reference.render()
        else:
            record["market_reference"] = None
            record["market_reference_rendered"] = row.no_reference or NO_REF_HOUSE
        if row.note:
            record["note"] = row.note
        card.rows.append(record)
    return card


# ----------------------------------------------------------------------------------- render


def _cell(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) if value else "(none)"
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


#: Widest a value may be before it moves to its own continuation line. A list of moved cells is
#: the case this exists for: it is the most interesting value on the card and the longest, and
#: letting it set the column width squashes everything else.
_VALUE_WIDTH = 12


def render(card: Scorecard, width: int = 52) -> str:
    """A plain table. The reference column wraps on word boundaries rather than truncating: a
    refusal reason cut in half would read as a shorter claim than it is."""
    lines = [
        f"scorecard: {card.book}",
        f"  path      {card.path}",
        f"  chapters  {len(card.chapters)}: {', '.join(card.chapters)}",
        "",
        *textwrap.wrap(NO_BAR, 96, initial_indent="  ", subsequent_indent="  "),
        "",
    ]
    keyw = max(len(r["key"]) for r in card.rows)
    valw = max(
        min(max(len(_cell(r["value"])) for r in card.rows), _VALUE_WIDTH),
        5,
    )
    head = f"  {'row'.ljust(keyw)}  {'value'.rjust(valw)}  {'chk'.ljust(6)}  market reference"
    lines += [head, "  " + "-" * (len(head) - 2)]
    pad = " " * (keyw + valw + 14)
    for record in card.rows:
        checklist = ",".join(record.get("checklist", [])) or "-"
        value = record["value"]
        rendered = _cell(value)
        overflow = len(rendered) > valw
        shown = rendered
        if overflow:
            shown = (
                f"{len(value)} listed"
                if isinstance(value, list)
                else rendered[: valw - 1] + "*"
            )
        wrapped = textwrap.wrap(record["market_reference_rendered"], width) or [""]
        lines.append(
            f"  {record['key'].ljust(keyw)}  {shown.rjust(valw)}  "
            f"{checklist.ljust(6)}  {wrapped[0]}"
        )
        lines += [pad + chunk for chunk in wrapped[1:]]
        if overflow:
            lines += textwrap.wrap(
                f"= {rendered}", width + len(pad), initial_indent=pad, subsequent_indent=pad + "  "
            )
        # A caveat qualifies the comparison the row is inviting, so it belongs beside the row
        # and not only in the JSON. The detector-mismatch note on the two system-line rows is
        # the case this exists for.
        caveat = (record["market_reference"] or {}).get("caveat", "")
        if caveat:
            lines += textwrap.wrap(
                f"caveat: {caveat}",
                width + len(pad),
                initial_indent=pad,
                subsequent_indent=pad + "  ",
            )
    lines += [
        "",
        "  chk = the read-recurrence-map family this row bears on "
        "(plan/agent-impact/read-recurrence-map.md §3 owns the list).",
        "  Every row is a description. Nothing here is a bar, a target or a verdict.",
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Per-draw code-only scorecard for one book, beside its market references."
    )
    parser.add_argument("target", help="a book-library directory, or one chapter .txt file")
    parser.add_argument(
        "--out",
        default="",
        help="write the JSON here; the default is scorecard.json beside the book. UTF-8 with "
        "LF, because a stdout redirect uses the console codepage on this box and mangles the "
        "em dash in the recorded [STATUS] lines",
    )
    parser.add_argument(
        "--no-json", action="store_true", help="print the table and write no file"
    )
    args = parser.parse_args(argv)

    card = build(Path(args.target))
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    sys.stdout.write(render(card) + "\n")

    if not args.no_json:
        target = Path(args.target)
        default = (target.parent if target.is_file() else target) / "scorecard.json"
        out = Path(args.out) if args.out else default
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(asdict(card), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        sys.stdout.write(f"\n  json: {out}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
