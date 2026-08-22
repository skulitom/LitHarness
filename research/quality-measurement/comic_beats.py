"""A located census of attempted humor, by kind and by position, and never by verdict.

**Measurement only.** Nothing here feeds a prompt, a directive, or any generation path; nothing
here admits an axis; nothing under `src/` moves. It produces a distribution and stops. The
shape is `opening_counters.py`'s (2026-08-21): measure the population, place our own chapters in
it, state the unflattering reading first, declare no bar for admission. Admission is an operator
act over a measured distribution (`plan/reader-read-2.md`), and this is the distribution.

**Why it is a model report rather than a counter, and why that is allowed.** There is no
deterministic counter for a joke, and a regex for one would be the fourteenth proxy of the shape
`BRIEF.md` §3 diagnoses. What this repository has measured is that a model cannot be asked for a
*verdict* — stage-0 §89.4 puts position over text at 4,676-to-1 at the token a verdict is
generated from — and **can** be asked to *locate*: E6, "name the single most salient difference",
clears all three registered defect families. §97.4 licenses exactly this shape: the "why" is
located, not narrated, and each property enters with its counter or locator committed first. So
the question here is **where and what**, never whether it is funny. The words "funny", "good",
"works", "successful" and "lands" do not appear in the system block, the question, or the schema.

**The one advantage this locator has over E6's matchers is deterministic.** Every beat carries an
anchor of at most twelve words that must be *findable in the text it was shown* (normalised
substring match). An unfindable anchor is a confabulation; it is excluded from every count and
reported as a rate on every arm. E6 could only score its own vocabulary against a frozen matcher.
This can check the model against the page.

**Three questions, reported in this order and separately.** Q1, the RoyalRoad LitRPG baseline by
cohort. Q2, where our own published chapters sit in it. Q3, whether the locator sees a
manufactured removal, what its test-retest spread is, and whether it moves on layout alone. Q2 is
worthless without Q1 and both are worthless without Q3; all three are reported even if Q3 kills
the instrument, because a mapped hole is a result (§74's logic).

**Familiarity is a named confound and the two substrates are never pooled.** BRIEF §2 Pass 6
measured a scoring model's familiarity with published text swinging a score further than real
damage did, and the locator is model-based. So RoyalRoad is the baseline arm with the confound
named, own-generated chapters are the clean arm, the `strip` differential on the same chapter
partially cancels it, and no number in this module averages the two.

**Two interpreters, split by what the run reads.** The RoyalRoad shards are parquet and only
`C:/DEV/MirrorBench/.venv` can read them, so `--dump` runs there and writes a **local-only,
gitignored** JSONL under `derived/`; every arm then runs under `uv run python` reading that file.
Committed results carry ids and numbers only — for RoyalRoad chapters an anchor is stored as an
offset and a hash and never as a quoted string, and for our own chapters it is stored verbatim,
because we own that prose. Module scope imports stdlib only and everything else is imported
lazily, which is what lets one implementation serve both interpreters.

    CB=research/quality-measurement/comic_beats.py
    MB=C:/DEV/MirrorBench/.venv/Scripts/python.exe

    $MB $CB --dump                                       # the census draw, gitignored
    uv run python $CB --selftest                         # free, and it gates every run below
    uv run python $CB --substrate local --arm census --dry-run
    uv run python $CB --substrate local     --arm census --yes
    uv run python $CB --substrate royalroad --arm census --yes
    uv run python $CB --substrate royalroad --arm repeat --yes
    uv run python $CB --substrate royalroad --arm sham   --yes
    uv run python $CB --substrate royalroad --arm strip  --yes
    uv run python $CB --substrate report                 # merges; spends nothing

`--arm repeat|sham|strip` read the census arm's result file for their subsets and refuse without
it. One CLI arm at a time on this box (§89.5: 390 transport failures from two `claude -p` jobs
beside each other), a dedicated `--cache` per arm, and a PID lock so a second launch refuses.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import math
import re
import statistics
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
REPO = HERE.parent.parent

RESULTS = HERE / "results"
#: Local-only and gitignored (`.gitignore`, and `corpus_leak_audit.DERIVED_TEXT_ROOTS` asserts
#: both the ignore and the absence of tracked files). Everything that carries third-party prose
#: or a derived work of it lives here: the chapter dump, the RoyalRoad raw caches, and **every**
#: revision this module generates on either substrate. A revision of our own chapter is prose
#: rather than a number, and "commit numbers, never prose" does not have a size exemption.
DERIVED = HERE / "derived"


# ============================================================================ the instrument
#
# Everything between this banner and the next is **byte-frozen at the first paid call** and
# covered by `registration_digest()`, which `--selftest` compares against `FROZEN_DIGEST`.
# `llm-reader-engagement.md` §A1's rule: T0's A4 put about fourteen points of a verdict on
# wording, so a reworded prompt is a different instrument with no evidence behind it.

#: The closed set. Closed because an open set cannot be falsified — `personas.py`'s reason-code
#: argument, one instrument over. Extending it after the first paid call would mean the counts
#: before and after were of different things, so `--selftest` fails on any change.
KINDS: tuple[str, ...] = (
    "quip",
    "deadpan",
    "absurd",
    "undercut",
    "callback",
    "system_voice",
    "banter",
)

#: One line each, rendered into the system block in this order. Descriptive of register and
#: **never of effect**: the handoff's draft said the System voice could be "arch, petty, or
#: funny" and the last word is a verdict, so it is "theatrical" here. That is the only departure
#: from the handoff's table and it is the whole point of the instrument.
KIND_DEFINITIONS: dict[str, str] = {
    "quip": "a character's or narrator's aside whose point is to be dry or sharp",
    "deadpan": "understatement, or a flat delivery of something outsized",
    "absurd": "an incongruous juxtaposition put there on purpose",
    "undercut": "a build-up deflated in the next clause or line",
    "callback": "a return to an earlier bit",
    "system_voice": "the System or status voice itself being arch, petty, or theatrical",
    "banter": "a dialogue exchange whose energy is the back-and-forth rather than its content",
}

#: Anchors longer than this are an instruction-following failure, counted and reported. They are
#: **not** excluded from the census on length alone: the counting rule is findability, and adding
#: a second exclusion criterion after the fact is how a rate becomes a rubric.
ANCHOR_MAX_WORDS = 12

SYSTEM = (
    "You are marking up one chapter of a web serial.\n\n"
    "Your task is to LOCATE every place where the writing reaches for levity \u2014 a lighter "
    "register: dry, sharp, arch, wry, absurd, or playful \u2014 rather than playing the moment "
    "straight. You are recording that the reach is there and where it is. Mark every one you "
    "find, including the ones you would otherwise pass over.\n\n"
    "For each place, record two things:\n\n"
    "  anchor  a span copied EXACTLY from the chapter, character for character, at most "
    f"{ANCHOR_MAX_WORDS} words long, that a reader could find by searching the text\n"
    "  kind    whichever one of these seven fits it best\n\n"
    + "\n".join(f"    {name:14s}{KIND_DEFINITIONS[name]}" for name in KINDS)
    + "\n\nRules:\n"
    "  - The anchor must be present in the chapter. Do not paraphrase it, do not tidy it, do "
    "not stitch two separated pieces together. If you cannot copy a span exactly, leave that "
    "place out.\n"
    "  - One entry per place, in the order the places appear. Never enter the same span twice.\n"
    "  - If the chapter reaches for levity nowhere, return an empty list. An empty list is an "
    "ordinary answer and is not a failure to look.\n"
    "  - Return only the JSON object."
)

QUESTION = (
    "The chapter is above. List every place in it that reaches for levity, in the order they "
    "appear."
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "beats": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "anchor": {"type": "string"},
                    "kind": {"type": "string", "enum": list(KINDS)},
                },
                "required": ["anchor", "kind"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["beats"],
    "additionalProperties": False,
}

#: Room for roughly eighty beats at an anchor apiece. Inert on the `cli` transport, which takes
#: no max-tokens flag, and it is still in the request because it is in the cache key and a run
#: that later moves to the SDK must miss the cache rather than silently change instruments. A
#: truncated answer does not parse and is recorded as `unparseable`, never as a low count.
BEATS_MAX_TOKENS = 2000

# ------------------------------------------------------------------ the strip arm's contract

#: An author revising his own pages, which is generation rather than the critique frame §1a.2
#: exists to avoid. Copied in shape from `repair_generation.REVISER_SYSTEM`, at chapter grain.
STRIP_SYSTEM = (
    "You are the author of the chapter below, midway through drafting a serialized web novel, "
    "returning tonight to revise your own pages."
)

#: Shared verbatim across the strip arm and its placebo; the task block is the single moving
#: part. The paragraph and system-voice contract is `repair_generation.REVISION_RULES`', because
#: §74's lesson is that a panel shown a mangled stat block reports on the stat block.
STRIP_RULES = """\
Revise the chapter below, changing as little as possible. Keep every plot fact, the same events
in the same order, the same point of view, and the same paragraph breaks. Any line in the system
voice \u2014 **bold** announcements and [STATUS] blocks \u2014 is copied byte-for-byte, unchanged,
where it stood. Do not shorten the chapter and do not pad it.
Return only the revised chapter text: no title, no preamble, no commentary.

Tonight's revision has one purpose:
{task}"""

#: The strip's task is written in the same located vocabulary the kinds are defined in, and
#: deliberately does not name the kind labels. Describing the target in *other* terms would
#: remove something other than what the census counts; naming the labels would make this a
#: keyword hunt fitted to its own scorer.
#:
#: `system_voice` is absent on purpose. Protected spans are copied byte-for-byte by the contract
#: above, so a System-voice beat **cannot** be stripped — which turns it into this arm's own
#: internal control: prose kinds must fall and `system_voice` must not. A run where both fall is
#: a locator responding to the fact of a rewrite rather than to the levity removed from it.
STRIP_TASKS: dict[str, str] = {
    "strip": (
        "Wherever the writing reaches for a lighter register \u2014 a dry or sharp aside, an "
        "understatement played flat, an incongruous pairing, a build-up deflated in the next "
        "line, a return to an earlier bit, a back-and-forth whose energy is the exchange \u2014 "
        "rewrite that sentence so it states the same thing plainly and straight, at about the "
        "same length. A sentence that already plays it straight is left exactly as it is."
    ),
    "strip_placebo": (
        "Correct any spelling or typographical errors you find. A sentence that contains none "
        "is left exactly as it is. There may be nothing to correct, in which case the chapter "
        "comes back unchanged."
    ),
}

# ---------------------------------------------------- windows, and where the numbers came from

#: The census window, in words, applied to **every** unit on every substrate. Measured before it
#: was chosen, which is the §101.4 order: over the 14,363 LitRPG chapters in the two cached
#: shards the word distribution is p5 780, p50 2,073, p95 4,394, max 27,666, and [800, 6000]
#: keeps 92.9% of them. The floor is where a per-1k density stops being quantisation noise (one
#: beat in an 800-word chapter is 1.25/1k); the ceiling is one whole chapter per call, since
#: chunking changes counts and a chapter that does not fit is excluded rather than split. Both
#: our own published chapters (4,151 and 4,252 words) sit inside it. Exclusions are counted and
#: printed, never silent.
MIN_CHAPTER_WORDS = 800
MAX_CHAPTER_WORDS = 6000

#: Chapters per cohort in the census draw, **one chapter per story**. The one-per-story rule is
#: `taste_calibration.dump`'s measured lesson: its first draw put eight chapters of one fiction
#: into a stratum, and a stratum that is really one author is a stratum of one. It also sets the
#: ceiling this number cannot pass — inside the window the shards hold 279 / 255 / **49** distinct
#: stories for `human_pre_llm` / `undeclared_2025` / `declared_ai_2025`, so the third cohort is
#: capped by the substrate at 49 and the draw is 100 / 100 / 49 = **249**, not the 300 the
#: handoff sketched. That is the substrate's ceiling reported as one, not a target that crept.
PER_COHORT_TARGET = 100

#: The test-retest and layout subsets, drawn deterministically from the census and reported with
#: the strip subset folded in, so every strip pair has its own noise floor rather than borrowing
#: the population's. Own-generated units are **all** in both subsets; there are only twelve.
REPEAT_SUBSET = 40

#: The strip subset: the top decile of the census arm by located density, because the arm is a
#: damage direction and damage needs something to remove. Plus every own unit with at least
#: `STRIP_OWN_MIN_BEATS` beats, on the same reasoning.
STRIP_TOP_FRACTION = 0.10
STRIP_OWN_MIN_BEATS = 3

#: Certification thresholds for the strip arm, each with its direction and unit stated where it
#: is used. `similarity` is `difflib` over word sequences, 1.0 byte-faithful, and the floor is
#: looser than `repair_emdash`'s 0.80 because a levity strip rewrites whole clauses rather than
#: removing a mark; `growth` is signed percent of the original word count and is two-sided
#: because a strip that shortens the chapter has removed sentences rather than rewritten them.
STRIP_MIN_SIMILARITY = 0.70
STRIP_MAX_GROWTH_PCT = 12.0

#: The `cli` transport's own ceiling, in characters of rendered command line, and it is a
#: property of the platform rather than of the question. Windows `CreateProcess` refuses a
#: command line at or above 32,767 characters with WinError 206, and `elicit._call_cli` passes
#: the whole chapter as an argument — so a long enough chapter cannot be sent at all. Measured
#: rather than assumed: `subprocess.list2cmdline` is exactly what `subprocess` renders on this
#: platform, and over the 249-chapter draw it gives p50 13,069, p90 22,653 and max 36,852
#: characters. At the 32,000 budget below, **4 of 249 chapters cannot be sent**.
#:
#: They are excluded and counted, never sent and allowed to fail: an over-long call comes back as
#: `transport_error:FileNotFoundError`, which is indistinguishable in a log from a broken install,
#: and §87.3's `NOT_SCREENABLE` lesson is that a unit the instrument could not reach is its own
#: state rather than a missing datum. The exclusion is length-correlated by construction, so it is
#: named in the results document beside the length residual it belongs to.
CLI_COMMAND_BUDGET = 32000

#: Alpha for every declared statistic in this module. One level, stated once.
ALPHA = 0.05

#: The smallest number of pairs at which a one-sided exact sign test can reach ALPHA at all:
#: its floor is 1/2**G, so G=5 gives 0.03125 and G=4 gives 0.0625. Below it the outcome is
#: INSUFFICIENT_N, which is a different outcome from a failure and is never converted into one.
MIN_PAIRS = 5

PRE_REGISTRATION: dict[str, Any] = {
    "written": (
        "2026-08-21, before the first paid call of any arm in this module, and byte-frozen "
        "with the system block, the question, the schema and the kinds under FROZEN_DIGEST"
    ),
    "question": (
        "Do this project's published chapters attempt humor at the density the genre's readers "
        "select for, and can a located instrument see the difference at all? Q1 is the "
        "RoyalRoad LitRPG baseline by cohort, Q2 is where our own chapters sit in it, Q3 is "
        "whether the locator is an instrument. Reported separately and in that order."
    ),
    "what_is_measured": (
        "The density of located ATTEMPTS at levity, in beats per 1,000 words. It is not a "
        "quality, a craft claim or a success rate: a chapter with more attempts is not better, "
        "and no arrangement of these numbers says whether a beat lands. Landing is valence, "
        "valence is behavioural or it is nothing (§97.4), and W4 is NOT VALIDATED for want of "
        "substrate."
    ),
    "unit_of_analysis": (
        "The chapter, as published \u2014 the unit a reader receives. Own-generated scenes from "
        "The Toll Road are reported as secondary colour and never pooled with chapters."
    ),
    "counting_rule": (
        "A beat is counted only if its anchor is findable in the text THAT CALL WAS SHOWN, by "
        "normalised substring match (NFKC, curly quotes and dashes folded to ASCII, whitespace "
        "collapsed, casefolded), and only if its kind is one of the seven frozen kinds. Repeated "
        "anchors within one answer collapse to one beat. Unfindable anchors are confabulations: "
        "excluded from every count and reported as a rate on every arm."
    ),
    "no_post_hoc_leniency": (
        "The strict normalisation above is the counting rule. A second, deliberately looser "
        "match \u2014 all non-alphanumeric characters dropped \u2014 is computed and reported as "
        "`relaxed_findable` so the size of what strictness costs is visible, and it never enters "
        "a count. Loosening the rule after reading the answers would be a rubric fitted to them."
    ),
    "window": (
        f"[{MIN_CHAPTER_WORDS}, {MAX_CHAPTER_WORDS}] words, one whole chapter per call. "
        "Chunking changes counts, so a chapter outside the window is excluded and the exclusion "
        "is counted and printed. Measured on the substrate before it was chosen: the window "
        "keeps 92.9% of the 14,363 LitRPG chapters in the two cached shards."
    ),
    "transport_exclusion": (
        f"A unit whose rendered `claude -p` command line reaches {CLI_COMMAND_BUDGET} characters "
        "cannot be sent by this transport (Windows refuses at 32,767) and is excluded before the "
        "call, counted, and printed. It is not sent and allowed to fail: a transport error is "
        "indistinguishable from a broken install. Measured over the draw, this is 4 of 249 "
        "chapters, and because it is length-correlated it is reported beside the length residual."
    ),
    "sampling": (
        f"{PER_COHORT_TARGET} chapters per era cohort, ONE CHAPTER PER STORY, chosen "
        "deterministically by digest so the draw is a rule and not a draw. The substrate caps "
        "`declared_ai_2025` at 49 distinct stories inside the window, so the census is "
        "100/100/49 = 249 and the cap is reported rather than filled by taking a second chapter "
        "from a story already in the pool."
    ),
    "substrates_are_never_pooled": (
        "RoyalRoad text may be memorised by the locator (BRIEF §2 Pass 6), so it is the "
        "baseline arm with the confound named; own-generated chapters are the clean arm; the "
        "`strip` differential on one chapter partially cancels the term; and no statistic in "
        "this module averages the two."
    ),
    "arms": {
        "census": "the chapter as published. Q1 and Q2 are read from this arm alone",
        "repeat": (
            "the same chapter, the same request, a distinct sample index \u2014 `n` "
            "byte-identical requests, so the variation is the model's own sampling and not a "
            "perturbed prompt (`elicit.py`'s rule). Reports the per-chapter spread of counts and "
            "the anchor overlap between the two lists. This is the noise floor every other arm "
            "is read against"
        ),
        "sham": (
            "`ablate.rewhitespace` at full strength. Not one character of any word changes. The "
            "count must not move beyond the `repeat` spread; if it does, the locator is "
            "responding to layout and the entry says so (§78)"
        ),
        "strip": (
            "a certified minimal revision that rewrites every reach for levity plainly, with "
            "`strip_placebo` \u2014 the same revision contract with an inert task \u2014 beside "
            "it as the floor. One dose; no ladder, no inject arm"
        ),
    },
    "why_there_is_a_strip_placebo": (
        "The handoff did not ask for one and `repair_generation.PRE_REGISTRATION`'s first line "
        "makes it mandatory: no repair arm is read except against its placebo. Without it a drop "
        "in located beats is equally well explained by the fact of a rewrite, and there is no "
        "way to tell the two apart afterwards. It is one more arm, not a dose ladder."
    ),
    "strip_internal_control": (
        "Protected spans (**bold** lines and [STATUS] lines) are copied byte-for-byte by the "
        "revision contract, so a `system_voice` beat cannot be stripped. Pre-registered: prose "
        "kinds fall and `system_voice` does not. If `system_voice` falls with them the locator "
        "is reading the fact of a rewrite. Four outcomes, none of them a pass by silence: "
        "CONTROL_HOLDS when no pair lost a system-voice beat, CONTROL_FAILS when the sign test "
        "says they fell, CONTROL_UNDECIDED with its interval printed in between, and EMPTY where "
        "the subset carries no protected span at all — which is most of RoyalRoad, whose "
        "system voice is not written in this project's typography."
    ),
    "declared_quantities": {
        "repeat_spread": (
            "|count(sample 0) - count(sample 1)| per chapter, in beats; range [0, inf), no "
            "direction and no bar \u2014 it is the ruler. Reported as median, p90 and max, in "
            "beats and in beats/1k, on both substrates separately. Attainable at any n >= 1; the "
            "subset is 40 RoyalRoad chapters plus the strip subset plus every own unit"
        ),
        "anchor_overlap": (
            "|A n B| / |A u B| over the two samples' normalised anchor sets, unitless, range "
            "[0, 1], higher is more stable. No bar: it is reported so a count that is stable "
            "while its locations are not cannot pass unnoticed"
        ),
        "sham_delta": (
            "|count(census) - count(sham)| per chapter, in beats, read against `repeat_spread` "
            "on the SAME chapters by a one-sided exact sign test that the sham delta exceeds the "
            "repeat delta. Outcomes: LAYOUT_SENSITIVE if p <= 0.05; INSIDE_NOISE only with the "
            "equivalence bound printed beside it, never as a pass by silence (§101.1); "
            "INSUFFICIENT_N below the attainable floor. The bound is the distribution-free 90% "
            "confidence interval on the median of (sham delta - repeat delta), in beats, so the "
            "reading states what magnitude of layout sensitivity it could not exclude"
        ),
        "strip_drop": (
            "count(original) - count(stripped), in beats, paired by chapter. Direction: "
            "positive. Read twice, and both readings print: against the placebo's own drift by a "
            "one-sided exact sign test on (strip drop > placebo drop), and against the noise "
            "floor by the share of pairs whose strip drop exceeds that chapter's repeat spread, "
            "sign-tested. Outcomes SEES / DOES_NOT_SEE / INSUFFICIENT_N / VOID"
        ),
        "confabulation_rate": (
            "unfindable anchors / anchors returned, unitless, range [0, 1], direction lower. "
            "Printed on every arm. REFUSAL STATE: if the mean confabulated beats per chapter on "
            "the strip subset is at least half the median strip drop in beats, the strip reading "
            "is VOID rather than weak \u2014 an effect the instrument's own noise could "
            "manufacture is not an effect"
        ),
    },
    "attainability": (
        "Declared at the n actually available, before the first call, per §87/§89's rulebook. "
        "Every statistic here is an exact one-sided sign test whose smallest attainable p at G "
        f"pairs is 1/2**G, so alpha {ALPHA} is unreachable below G={MIN_PAIRS} and every G below "
        "that reports INSUFFICIENT_N rather than FAILS. The sham subset is G=40+ RoyalRoad "
        "chapters and G=12 own units, both attainable. The strip subset is the census top "
        "decile, G=24 at n=249, plus own units with >= 3 beats; if fewer than 5 pairs certify, "
        "the arm reports INSUFFICIENT_N and no drop is read. None of these is a bar for "
        "admission: no bar for admission is declared anywhere in this module."
    ),
    "no_inherited_figures": (
        "§79.1's rule. Every spread, rate and cost reported here is measured on these chapters "
        "by this instrument in these runs. §85's per-comparison price is not used to project "
        "this one, because a whole-chapter input is several times a §85 pair."
    ),
    "no_bar_for_admission": (
        "None is declared, and that is the point. Nothing here enters `AXES` or `COUNTERS`, "
        "reaches a prompt, a directive, a Director brief, a persona reason code or a writer "
        "dossier. Admission is an operator act over the measured distribution, exactly as for "
        "`opening_proper_nouns`."
    ),
    "no_landing_measurement": (
        "Whether a beat lands is not asked, not schema'd and not derivable from anything here. "
        "The nearest shape is W4 (`payoff_landing.py`), which is NOT VALIDATED for want of "
        "substrate, and it stays that way."
    ),
}

# =========================================================================== end of the freeze


def digest(payload: object) -> str:
    """Stable digest of a payload. Sorted keys so dict order is never in the key.

    Restated from `elicit.digest` rather than imported, because `--dump` runs under the
    MirrorBench interpreter, which does not have this repository installed and cannot import
    `elicit` (it reaches `personas`). The implementation is byte-identical on purpose: a chapter
    id picked by this function on one interpreter has to be the same chapter on the other.
    """
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:20]


def registration_digest() -> str:
    """Content address of everything inside the freeze banner.

    Printed on every artifact. A result file whose digest differs from the module's came from a
    different instrument, and the check is one comparison rather than a diff of prose.
    """
    return digest(
        {
            "pre_registration": PRE_REGISTRATION,
            "kinds": list(KINDS),
            "kind_definitions": KIND_DEFINITIONS,
            "system": SYSTEM,
            "question": QUESTION,
            "schema": SCHEMA,
            "max_tokens": BEATS_MAX_TOKENS,
            "anchor_max_words": ANCHOR_MAX_WORDS,
            "strip_system": STRIP_SYSTEM,
            "strip_rules": STRIP_RULES,
            "strip_tasks": STRIP_TASKS,
            "window": [MIN_CHAPTER_WORDS, MAX_CHAPTER_WORDS],
            "sampling": [PER_COHORT_TARGET, REPEAT_SUBSET, STRIP_TOP_FRACTION,
                         STRIP_OWN_MIN_BEATS],
            "certification": [STRIP_MIN_SIMILARITY, STRIP_MAX_GROWTH_PCT],
            "alpha": ALPHA,
            "min_pairs": MIN_PAIRS,
        }
    )


#: The digest as it stood when the first paid call was made. `--selftest` fails on divergence,
#: which is the whole mechanism: a reworded prompt is a different instrument, and every number in
#: `comic-beats-results.md` is attributable to this exact string or it is attributable to nothing.
FROZEN_DIGEST = "d3200ddad172e4854b70"


# ------------------------------------------------------------------------- anchor findability

#: Characters a model retypes rather than copies. Folded on BOTH sides of the match, so the check
#: forgives a straightened quote and forgives nothing else. Written as escapes because ruff (the
#: RUF rules) rejects literal curly quotes in Python source, which is the same reason
#: `ablate._EM` names its glyph instead of inlining it.
_FOLD = str.maketrans(
    {
        "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
        "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u2032": "'",
        "\u2033": '"', "\u2010": '-', "\u2011": '-', "\u2012": '-',
        "\u2013": '-', "\u2014": '-', "\u2015": '-', "\u2212": '-',
        "\u00a0": ' ', "\u2007": ' ', "\u2009": ' ', "\u202f": ' ',
        "\u2026": '...',
    }
)

_NON_ALNUM = re.compile(r"[^0-9a-z]+")


def normalise(text: str) -> str:
    """The counting rule's normalisation: NFKC, folded punctuation, collapsed whitespace, cased.

    Whitespace collapse is what makes the `sham` arm scoreable at all — `rewhitespace` changes
    only whitespace, so an anchor found in the reflowed text is findable in the original by the
    same rule and the two arms' counts are comparable rather than incidentally different.
    """
    folded = unicodedata.normalize("NFKC", text).translate(_FOLD)
    return " ".join(folded.split()).casefold()


def relaxed(text: str) -> str:
    """The deliberately looser match, reported and never counted. See `no_post_hoc_leniency`."""
    return _NON_ALNUM.sub("", normalise(text))


def locate(anchor: str, haystack_norm: str, haystack_relaxed: str) -> dict[str, Any]:
    """Where an anchor sits in the text it was shown, or the fact that it does not.

    `offset` is an index into the **normalised** text and is what a RoyalRoad result file stores
    instead of the string, together with a hash of the anchor: reproducible from the same shard
    at the same pinned snapshot, and not an excerpt.
    """
    needle = normalise(anchor)
    offset = haystack_norm.find(needle) if needle else -1
    loose = relaxed(anchor)
    return {
        "offset": offset,
        "findable": offset >= 0,
        "relaxed_findable": bool(loose) and loose in haystack_relaxed,
        "words": len(anchor.split()),
        "over_length": len(anchor.split()) > ANCHOR_MAX_WORDS,
        "hash": hashlib.sha256(needle.encode("utf-8")).hexdigest()[:16],
    }


def score_answer(text_shown: str, payload: object) -> dict[str, Any]:
    """One call's answer, turned into a count and the hygiene rates that qualify it.

    Every drop is a named category with a count beside it, because the failure this shape exists
    to avoid is a low number that is really a parse failure. `counted` is the datum; `returned`,
    `confabulated`, `bad_kind`, `duplicate` and `over_length` are what the datum is read through.
    """
    haystack_norm = normalise(text_shown)
    haystack_relaxed = relaxed(text_shown)
    entries = payload.get("beats") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return {
            "unparseable": True, "beats": [], "returned": 0, "counted": 0,
            "confabulated": 0, "bad_kind": 0, "duplicate": 0, "over_length": 0,
            "relaxed_only": 0, "by_kind": {},
        }
    beats: list[dict[str, Any]] = []
    seen: set[str] = set()
    confabulated = bad_kind = duplicate = over_length = relaxed_only = 0
    for entry in entries:
        if not isinstance(entry, dict):
            bad_kind += 1
            continue
        anchor = str(entry.get("anchor") or "")
        kind = str(entry.get("kind") or "")
        if kind not in KINDS:
            bad_kind += 1
            continue
        found = locate(anchor, haystack_norm, haystack_relaxed)
        if found["over_length"]:
            over_length += 1
        if not found["findable"]:
            confabulated += 1
            if found["relaxed_findable"]:
                relaxed_only += 1
            continue
        if found["hash"] in seen:
            duplicate += 1
            continue
        seen.add(found["hash"])
        beats.append({"kind": kind, "anchor": anchor, **found})
    by_kind: dict[str, int] = {}
    for beat in beats:
        by_kind[beat["kind"]] = by_kind.get(beat["kind"], 0) + 1
    return {
        "unparseable": False,
        "beats": beats,
        "returned": len(entries),
        "counted": len(beats),
        "confabulated": confabulated,
        "bad_kind": bad_kind,
        "duplicate": duplicate,
        "over_length": over_length,
        "relaxed_only": relaxed_only,
        "by_kind": by_kind,
    }


def public_beats(scored: dict[str, Any], *, quote: bool) -> list[dict[str, Any]]:
    """The committed form of one answer's beats.

    `quote=False` is the RoyalRoad rule and it is not a courtesy: an anchor there is a quoted run
    of somebody else's novel, and a public git history is exactly where that must never land
    (`corpus_leak_audit.py`'s whole subject). Offset and hash reproduce it from the pinned shard
    for anyone who has the shard, and carry no expression for anyone who does not. `quote=True`
    is our own prose, where the located list printed in full **is** the acceptance artifact.
    """
    return [
        {
            "kind": beat["kind"],
            "offset": beat["offset"],
            "words": beat["words"],
            "hash": beat["hash"],
            **({"anchor": beat["anchor"]} if quote else {}),
        }
        for beat in scored["beats"]
    ]


# ---------------------------------------------------------------------------- the arithmetic


def one_sided_sign_p(k: int, n: int) -> float:
    """P(X >= k) for X ~ Bin(n, 1/2), enumerated rather than approximated.

    The whole module's statistic. One-sided because every alternative here is directional and
    declared as such before the run: a sham that moves the count more than a re-ask does, a strip
    that removes more beats than its placebo does. §89's two-sided reasoning does not apply —
    that was invariance under a sign flip of a *fitted* direction, and nothing here is fitted.
    """
    if n <= 0:
        return 1.0
    k = max(0, min(k, n))
    return min(1.0, sum(math.comb(n, i) for i in range(k, n + 1)) / (2 ** n))


def attainable_p(n: int) -> float:
    """The smallest p this statistic can produce at `n` pairs. Printed beside every p."""
    return 1.0 / (2 ** n) if n > 0 else 1.0


def required_k(n: int, alpha: float = ALPHA) -> int | None:
    """Aligned pairs needed to clear `alpha` at `n`, or None when `alpha` is unreachable."""
    for k in range(n + 1):
        if one_sided_sign_p(k, n) <= alpha:
            return k
    return None


def median_ci(values: list[float], confidence: float = 0.90) -> dict[str, Any]:
    """Distribution-free confidence interval for a median, from the order statistics.

    §101.1's fix, in the one form this module needs: a control that does not fire must publish
    what magnitude it could not exclude, or it is a pass by silence. The interval is exact under
    the sign test and assumes nothing about the shape of the differences.
    """
    n = len(values)
    if n == 0:
        return {"n": 0, "median": None, "lo": None, "hi": None, "confidence": confidence}
    ordered = sorted(values)
    tail = (1.0 - confidence) / 2.0
    cumulative = 0.0
    k = -1
    for index in range(n + 1):
        cumulative += math.comb(n, index) / (2 ** n)
        if cumulative > tail:
            break
        k = index
    low_index = min(max(k + 1, 0), n - 1)
    high_index = min(max(n - k - 2, 0), n - 1)
    return {
        "n": n,
        "median": round(statistics.median(ordered), 4),
        "lo": round(min(ordered[low_index], ordered[high_index]), 4),
        "hi": round(max(ordered[low_index], ordered[high_index]), 4),
        "confidence": confidence,
        "note": "exact under the sign test; assumes nothing about the shape of the differences",
    }


def paired_reading(
    deltas: list[float], *, name: str, positive_verdict: str, null_verdict: str,
) -> dict[str, Any]:
    """One declared one-sided sign test, with its floor, its required k and its refusal state.

    A zero difference leaves the denominator: it is a pair the design could not decide, and
    counting it as evidence for the null is the shape §101.1 refuses. `pairs_undecided` prints
    beside the count so a reading resting on three decided pairs cannot look like one resting on
    thirty.
    """
    decided = [value for value in deltas if value != 0]
    n = len(decided)
    k = sum(1 for value in decided if value > 0)
    p = one_sided_sign_p(k, n)
    needed = required_k(n)
    if n < MIN_PAIRS or needed is None:
        verdict = "INSUFFICIENT_N"
    elif p <= ALPHA:
        verdict = positive_verdict
    else:
        verdict = null_verdict
    return {
        "statistic": name,
        "pairs_total": len(deltas),
        "pairs_decided": n,
        "pairs_undecided": len(deltas) - n,
        "aligned": k,
        "p_one_sided": round(p, 8),
        "attainable_floor": round(attainable_p(n), 8),
        "k_required": needed,
        "alpha": ALPHA,
        "verdict": verdict,
        "equivalence_bound": median_ci(deltas),
    }


def jaccard(left: list[str], right: list[str]) -> float | None:
    """Anchor-set overlap between two samples of one chapter. None when both are empty."""
    a, b = set(left), set(right)
    if not a and not b:
        return None
    return round(len(a & b) / len(a | b), 4)


def describe(values: list[float]) -> dict[str, Any]:
    """Quantiles and moments for one population, in `opening_counters.describe`'s exact shape.

    Imported from there rather than restated, so the quantile convention (nearest-rank, so every
    printed value is one a text actually scored) is literally the same convention the names
    counter's results document reports. Imported inside the function because that module reaches
    `litharness.domain.axes`, which the MirrorBench interpreter cannot import.
    """
    from opening_counters import describe as _describe

    return dict(_describe(values))


def percentile_of(value: float, population: list[float]) -> float | None:
    """Share of the population at or below `value`, as a percentage. Same source, same reason."""
    from opening_counters import percentile_of as _percentile_of

    return _percentile_of(value, population)


# ------------------------------------------------------------------------------- substrates


def dump_path(root: Path | None = None) -> Path:
    return (root or DERIVED) / "comic-beats-royalroad.jsonl"


def dump(limit_per_cohort: int = PER_COHORT_TARGET) -> int:
    """Write the census draw to a local-only JSONL. **MirrorBench interpreter only.**

    The bridge `taste_calibration --dump` established: the interpreter that can read 497MB of
    parquet is not the interpreter that can drive the transport, so the sampled chapters cross
    between them as a gitignored file rather than as a shared import. Ids, cohort, covariates and
    text; the text never leaves `derived/` and no committed artifact carries a word of it.

    The draw is a rule, not a draw: one chapter per story (`taste_calibration`'s measured
    lesson), the chapter chosen by the smallest digest of its own id, the stories ordered by the
    digest of theirs. Re-running reproduces the same 249 chapters from the same pinned snapshot.
    """
    import corpus_io

    per_story: dict[tuple[str, str], Any] = {}
    seen = excluded_short = excluded_long = 0
    for unit in corpus_io.royalroad_chapters(genre_tag="LitRPG", min_words=1, limit=0):
        seen += 1
        if unit.words < MIN_CHAPTER_WORDS:
            excluded_short += 1
            continue
        if unit.words > MAX_CHAPTER_WORDS:
            excluded_long += 1
            continue
        key = (str(unit.meta["cohort"]), str(unit.work_id))
        current = per_story.get(key)
        if current is None or digest(unit.unit_id) < digest(current.unit_id):
            per_story[key] = unit

    by_cohort: dict[str, list[Any]] = {}
    for (cohort, _work), unit in per_story.items():
        by_cohort.setdefault(cohort, []).append(unit)

    rows: list[dict[str, Any]] = []
    caps: dict[str, dict[str, int]] = {}
    for cohort in sorted(by_cohort):
        stories = sorted(by_cohort[cohort], key=lambda unit: digest(unit.work_id))
        taken = stories[:limit_per_cohort]
        caps[cohort] = {"available_stories": len(stories), "taken": len(taken)}
        for unit in taken:
            rows.append(
                {
                    "unit_id": unit.unit_id,
                    "cohort": cohort,
                    "work_id": unit.work_id,
                    "author_id": unit.meta.get("author"),
                    "released_at": unit.released_at,
                    "words": unit.words,
                    "followers": unit.meta.get("followers"),
                    "total_views": unit.meta.get("total_views"),
                    "conversion": unit.meta.get("conversion"),
                    "average_views": unit.meta.get("average_views"),
                    "shard": unit.meta.get("shard"),
                    "snapshot": corpus_io.SNAPSHOT_REVISION,
                    "text": unit.text,
                }
            )

    target = dump_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    for cohort, cap in sorted(caps.items()):
        if cap["taken"] < limit_per_cohort:
            print(
                f"  CAP {cohort}: {cap['available_stories']} distinct stories inside the window, "
                f"below the {limit_per_cohort} target; taking all of them rather than drawing a "
                "second chapter from a story already in the pool",
                file=sys.stderr, flush=True,
            )
    print(
        f"wrote {len(rows)} chapters to {target} "
        f"({ {c: v['taken'] for c, v in sorted(caps.items())} }); "
        f"{seen} LitRPG chapters seen, {excluded_short} below {MIN_CHAPTER_WORDS} words and "
        f"{excluded_long} above {MAX_CHAPTER_WORDS} excluded by the window",
        file=sys.stderr, flush=True,
    )
    return 0


def load_royalroad() -> list[dict[str, Any]]:
    """The dumped census draw, under the interpreter that drives the transport."""
    path = dump_path()
    if not path.is_file():
        raise SystemExit(
            f"{path} is missing. It is written by the MirrorBench interpreter, which is the only "
            "one that can read the parquet shards:\n  C:/DEV/MirrorBench/.venv/Scripts/"
            "python.exe research/quality-measurement/comic_beats.py --dump"
        )
    units = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            units.append({**row, "substrate": "royalroad"})
    return units


_SCENE_HEADING = re.compile(r"^## .*$", re.MULTILINE)


def own_units(library: Path, toll: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Our own published prose: Reappraisal chapters, then The Toll Road's scenes.

    **The published chapter is the unit, not the scene** — `opening_counters.reappraisal_chapters`
    makes the same choice for the same reason, and this reads the same folder rather than
    reassembling scenes here. The Toll Road's per-scene rows are secondary colour and are kept in
    a separate list so that nothing downstream can pool a scene density with a chapter density by
    accident.

    Both paths are arguments because `book-library/` and `exports/` are gitignored build products
    that live in the primary checkout: a linked worktree does not have them, and a loader that
    silently found nothing would report a census of zero chapters as a measurement.
    """
    chapters: list[dict[str, Any]] = []
    for path in sorted(library.glob("Chapter*.txt")):
        text = path.read_text(encoding="utf-8")
        chapters.append(
            {
                "unit_id": f"reappraisal:{path.stem}",
                "substrate": "local",
                "cohort": "own_chapter",
                "words": len(text.split()),
                "source_path": str(path),
                "text": text,
            }
        )
    scenes: list[dict[str, Any]] = []
    if toll.is_file():
        parts = _SCENE_HEADING.split(toll.read_text(encoding="utf-8"))
        for index, part in enumerate(parts[1:], start=1):
            body = part.strip()
            scenes.append(
                {
                    "unit_id": f"toll-road:scene-{index}",
                    "substrate": "local",
                    "cohort": "own_scene",
                    "words": len(body.split()),
                    "source_path": str(toll),
                    "text": body,
                }
            )
    return chapters, scenes


def cli_command_chars(system: str, prompt: str, model: str) -> int:
    """The rendered command line `elicit._call_cli` would build, measured the way Windows will.

    Replicated here rather than imported because `_call_cli` builds and spends in one step and
    there is no seam between them; `CLI_HARDENING` and the schema-append are imported so the two
    cannot drift on the parts that matter. `subprocess.list2cmdline` is the exact renderer
    `subprocess` uses on this platform, quoting and escaping included, so this is a measurement
    of the thing rather than an estimate of it.
    """
    import subprocess

    from elicit import CLI_HARDENING

    full_system = system + (
        "\n\nReply with a single JSON object conforming to this schema and nothing "
        "else — no prose, no code fence:\n" + json.dumps(SCHEMA, sort_keys=True)
    )
    argv = [
        "claude", "-p", prompt,
        "--output-format", "json",
        "--model", model,
        "--system-prompt", full_system,
        *CLI_HARDENING,
    ]
    return len(subprocess.list2cmdline(argv))


def census_command_chars(text: str, model: str) -> int:
    """The census call's rendered length for one chapter."""
    return cli_command_chars(SYSTEM, f"{text}\n\n---\n\n{QUESTION}", model)


def apply_window(units: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The window, applied to every unit on every substrate, with the drops returned not dropped."""
    kept, excluded = [], []
    for unit in units:
        if MIN_CHAPTER_WORDS <= unit["words"] <= MAX_CHAPTER_WORDS:
            kept.append(unit)
        else:
            excluded.append(
                {
                    "unit_id": unit["unit_id"],
                    "words": unit["words"],
                    "reason": "below_min" if unit["words"] < MIN_CHAPTER_WORDS else "above_max",
                }
            )
    return kept, excluded


def load_units(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Every unit for one substrate, windowed, with the exclusion ledger beside them."""
    if args.substrate == "royalroad":
        candidates = load_royalroad()
    else:
        chapters, scenes = own_units(Path(args.library), Path(args.toll))
        if not chapters:
            raise SystemExit(
                f"no Chapter*.txt under {args.library}. `book-library/` is a gitignored build "
                "product that lives in the primary checkout; pass --library and --toll if this "
                "is a linked worktree."
            )
        candidates = chapters + scenes
    kept, excluded = apply_window(candidates)
    if args.transport == "cli":
        from elicit import PANEL_MODEL

        model = args.model or PANEL_MODEL
        sendable = []
        for unit in kept:
            chars = census_command_chars(unit["text"], model)
            if chars >= CLI_COMMAND_BUDGET:
                excluded.append({
                    "unit_id": unit["unit_id"], "words": unit["words"],
                    "reason": "over_cli_command_budget", "command_chars": chars,
                })
            else:
                sendable.append(unit)
        kept = sendable
    for row in excluded:
        print(f"  EXCLUDED {row['unit_id']}: {row['words']} words, {row['reason']}",
              file=sys.stderr, flush=True)
    return kept, {
        "seen": len(candidates),
        "kept": len(kept),
        "excluded": excluded,
        "by_reason": {
            reason: sum(1 for row in excluded if row["reason"] == reason)
            for reason in sorted({row["reason"] for row in excluded})
        },
    }


# ------------------------------------------------------------------------------ the calling


def _synthetic_answer(key: str, text: str) -> str:
    """A dry run's stand-in answer: deterministic, and deliberately carrying **no signal**.

    §89.4's lesson, which cost a dry run that exercised none of the paths it existed to check:
    `elicit._synthetic_text` knew none of the new stages, so every answer came back refused and
    the scorers never ran. This module answers its own dry calls rather than editing that shared
    function, and the answer is drawn from a hash of the request and **never from the arm** — so
    a dry `strip` is a draw from the null and every reading of it should come back
    INSUFFICIENT_N or a coin.

    About half the anchors are real spans of the text and half are invented, so a dry run
    exercises findability, the confabulation rate, the duplicate collapse and the kind check. The
    resulting confabulation rate near 0.5 is implausible on purpose: nobody can mistake a dry
    number here for a measurement.
    """
    marker = int(key[:8], 16)
    words = text.split()
    span = max(len(words) - 8, 1)
    beats = []
    for index in range(marker % 9):
        start = (marker + index * 7919) % span
        if (marker >> index) & 1:
            anchor = " ".join(words[start : start + 6])
        else:
            anchor = f"(dry run) no such span at {start}"
        beats.append({"anchor": anchor, "kind": KINDS[(marker + index) % len(KINDS)]})
    return json.dumps({"beats": beats})


def ask_beats(
    elicitor: Any, unit: dict[str, Any], text_shown: str, *,
    sample: int, arm: str, dry_run: bool,
) -> dict[str, Any]:
    """One census call on one chapter, scored. The only place a beat count is produced.

    The turn is the whole chapter and then the frozen question, which is `elicitation_study`'s
    shape. One chapter per call: chunking changes counts, so a chapter that does not fit the
    window never reaches here.
    """
    from elicit import _strip_fence

    turn = [{"role": "user", "content": f"{text_shown}\n\n---\n\n{QUESTION}"}]
    tag = {"unit": unit["unit_id"], "arm": arm, "stage": "comic_beats", "sample": sample}
    if dry_run:
        key = digest({"system": SYSTEM, "text": text_shown, "sample": sample})
        record: dict[str, Any] = {
            **tag, "key": key, "model": "(dry)", "usage": {}, "dry_run": True,
            "text": _synthetic_answer(key, text_shown), "refused": False,
        }
    else:
        record = elicitor.ask_raw(
            SYSTEM, turn, schema=SCHEMA, max_tokens=BEATS_MAX_TOKENS, tag=tag, sample=sample,
        )
    if record.get("refused"):
        return {"refused": True, "stop_reason": record.get("stop_reason", ""), "counted": 0,
                "beats": [], "returned": 0, "confabulated": 0, "bad_kind": 0, "duplicate": 0,
                "over_length": 0, "relaxed_only": 0, "by_kind": {}, "unparseable": False,
                "usage": record.get("usage", {})}
    try:
        payload = json.loads(_strip_fence(str(record.get("text", ""))))
    except json.JSONDecodeError:
        payload = None
    scored = score_answer(text_shown, payload)
    return {**scored, "refused": False, "usage": record.get("usage", {})}


def _row(unit: dict[str, Any], scored: dict[str, Any], *, quote: bool) -> dict[str, Any]:
    """One unit's committed record. Ids and numbers, plus anchors only where we own the prose."""
    words = max(unit["words"], 1)
    return {
        "unit_id": unit["unit_id"],
        "cohort": unit.get("cohort"),
        "work_id": unit.get("work_id"),
        "words": unit["words"],
        "counted": scored["counted"],
        "density_per_1k": round(1000.0 * scored["counted"] / words, 4),
        "by_kind": scored["by_kind"],
        "returned": scored["returned"],
        "confabulated": scored["confabulated"],
        "bad_kind": scored["bad_kind"],
        "duplicate": scored["duplicate"],
        "over_length": scored["over_length"],
        "relaxed_only": scored["relaxed_only"],
        "unparseable": scored["unparseable"],
        "refused": scored["refused"],
        "beats": public_beats(scored, quote=quote),
    }


def hygiene(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """The rates every arm prints, whatever else it says. A count with no hygiene beside it is
    a count nobody can tell from a parse failure."""
    returned = sum(row["returned"] for row in rows)
    confabulated = sum(row["confabulated"] for row in rows)
    return {
        "units": len(rows),
        "anchors_returned": returned,
        "confabulated": confabulated,
        "confabulation_rate": round(confabulated / returned, 4) if returned else None,
        "confabulated_per_unit": round(confabulated / len(rows), 4) if rows else None,
        "relaxed_only": sum(row["relaxed_only"] for row in rows),
        "bad_kind": sum(row["bad_kind"] for row in rows),
        "duplicate": sum(row["duplicate"] for row in rows),
        "over_length": sum(row["over_length"] for row in rows),
        "unparseable_units": sum(1 for row in rows if row["unparseable"]),
        "refused_units": sum(1 for row in rows if row["refused"]),
    }


def spend_of(usages: list[dict[str, Any]]) -> dict[str, Any]:
    """What the arm cost, from the transport's own envelopes. Never projected from another arm.

    Takes the usage envelopes rather than the committed rows, because a row is the artifact and
    a row carries no usage: on a subscription the `equivalent_usd` field is an equivalent API
    price for quota already paid for (`elicit._call_cli` argues that at length), and it is
    operational rather than evidential. §79.1 also applies in the other direction: this is the
    only price this module reports, and it is measured here rather than inherited from §85.
    """
    total = 0.0
    tokens = {"input": 0.0, "output": 0.0, "cache_read": 0.0, "cache_write": 0.0}
    for usage in usages:
        total += float((usage or {}).get("equivalent_usd") or 0.0)
        for name in tokens:
            tokens[name] += float((usage or {}).get(name) or 0.0)
    return {"equivalent_usd": round(total, 4), **{k: int(v) for k, v in tokens.items()}}


# ----------------------------------------------------------------------------- the subsets


def result_path(substrate: str, arm: str, dry: bool = False) -> Path:
    """Where an arm's committed record lands. A dry run gets its own suffix and cannot touch a
    paid arm's file — the class of accident the runbook's "five ways to waste a paid run" is
    a list of, closed structurally rather than by remembering."""
    return RESULTS / f"comic-beats-{substrate}-{arm}{'-dry' if dry else ''}.json"


def cache_path(substrate: str, arm: str, dry: bool = False) -> Path:
    """A dedicated cache per arm, and RoyalRoad's under `derived/`.

    Two rules meeting. `Elicitor`'s write lock is per process, so two runs sharing one JSONL
    interleave and corrupt each other's records (RUNBOOK, "five ways to waste a paid run"). And a
    RoyalRoad raw cache holds the model's answer verbatim, which is quoted runs of somebody
    else's novel, so it belongs where the leak audit already guards — `derived/`, gitignored,
    untracked, and never a committed artifact.
    """
    root = DERIVED if substrate == "royalroad" else RESULTS
    return root / f"comic-beats-{substrate}-{arm}{'-dry' if dry else ''}-raw.jsonl"


def load_result(substrate: str, arm: str, dry: bool = False) -> dict[str, Any]:
    path = result_path(substrate, arm, dry)
    if not path.is_file():
        raise SystemExit(
            f"{path} is missing, and this arm is read against it. The order is census, then "
            "repeat, then sham, then strip: the strip subset is the census's own top decile and "
            "the noise floor has to cover it."
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("registration_digest") != registration_digest():
        raise SystemExit(
            f"{path} carries registration digest {payload.get('registration_digest')} and this "
            f"module is {registration_digest()}. That is a different instrument; re-run the "
            "earlier arm or restore the frozen block."
        )
    return payload


def scoreable(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in result["rows"] if not row["refused"] and not row["unparseable"]]


def strip_subset(census: dict[str, Any]) -> list[str]:
    """The units the damage arm runs on: text that **has** beats to remove.

    The top decile by located density on RoyalRoad, every own unit at or above
    `STRIP_OWN_MIN_BEATS` on ours. Selecting on the outcome is deliberate and is why the arm is
    read against a placebo rather than against the population: a top-decile chapter regresses
    toward the mean on a re-ask whether or not anything was removed from it, and the placebo
    carries exactly that regression.
    """
    rows = scoreable(census)
    if census["substrate"] == "royalroad":
        ordered = sorted(rows, key=lambda row: (-row["density_per_1k"], row["unit_id"]))
        take = round(STRIP_TOP_FRACTION * len(rows))
        return sorted(row["unit_id"] for row in ordered[:take])
    return sorted(row["unit_id"] for row in rows if row["counted"] >= STRIP_OWN_MIN_BEATS)


def noise_subset(census: dict[str, Any]) -> list[str]:
    """The units the `repeat` and `sham` arms run on: a stratified draw **plus** the strip subset.

    Folding the strip subset in is not tidiness. The strip drop is read against the noise floor
    *per chapter*, and a floor measured on other chapters would be a population statistic
    standing in for a chapter's own — which is the substitution §79.1 exists to refuse.
    """
    rows = scoreable(census)
    if census["substrate"] != "royalroad":
        return sorted(row["unit_id"] for row in rows)
    by_cohort: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_cohort.setdefault(str(row["cohort"]), []).append(row)
    draw: set[str] = set()
    for _cohort, members in sorted(by_cohort.items()):
        share = round(REPEAT_SUBSET * len(members) / max(len(rows), 1))
        ordered = sorted(members, key=lambda row: digest(row["unit_id"]))
        draw.update(row["unit_id"] for row in ordered[:share])
    return sorted(draw | set(strip_subset(census)))


# -------------------------------------------------------------------------------- the arms


def _elicitor(args: argparse.Namespace, arm: str) -> Any:
    from elicit import PANEL_MODEL, Elicitor

    return Elicitor(
        cache_path=Path(args.cache) if args.cache else cache_path(
            args.substrate, arm, bool(args.dry_run)
        ),
        model=args.model or PANEL_MODEL,
        spot_model=None,
        spot_fraction=0.0,
        transport=args.transport,
        max_workers=args.workers,
        dry_run=False,
    )


def _progress(arm: str, done: int, total: int) -> None:
    if done == total or done % 10 == 0:
        print(f"  {arm}: {done}/{total}", file=sys.stderr, flush=True)


def _sweep(
    elicitor: Any, jobs: list[tuple[dict[str, Any], str, int]], *,
    arm: str, dry_run: bool, workers: int, quote: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Every (unit, text, sample) through the locator, concurrently. Rows out, usage beside them."""
    results: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
    done = 0

    def one(index: int) -> tuple[int, dict[str, Any], dict[str, Any]]:
        unit, text_shown, sample = jobs[index]
        return index, unit, ask_beats(
            elicitor, unit, text_shown, sample=sample, arm=arm, dry_run=dry_run
        )

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for index, unit, scored in pool.map(one, range(len(jobs))):
            results.append((index, unit, scored))
            done += 1
            _progress(arm, done, len(jobs))
    results.sort(key=lambda item: item[0])
    rows = [_row(unit, scored, quote=quote) for _, unit, scored in results]
    usages = [scored.get("usage") or {} for _, _, scored in results]
    return rows, usages


def _envelope(args: argparse.Namespace, arm: str, extra: dict[str, Any]) -> dict[str, Any]:
    return {
        "arm": arm,
        "substrate": args.substrate,
        "model": args.model,
        "transport": args.transport,
        "dry_run": bool(args.dry_run),
        "registration_digest": registration_digest(),
        "pre_registration": PRE_REGISTRATION,
        **extra,
    }


def run_census(args: argparse.Namespace) -> dict[str, Any]:
    units, ledger = load_units(args)
    quote = args.substrate != "royalroad"
    elicitor = _elicitor(args, "census")
    jobs = [(unit, unit["text"], 0) for unit in units]
    with elicitor:
        rows, usages = _sweep(elicitor, jobs, arm="census", dry_run=args.dry_run,
                              workers=elicitor.max_workers, quote=quote)
    return _envelope(args, "census", {
        "window": [MIN_CHAPTER_WORDS, MAX_CHAPTER_WORDS],
        "exclusions": ledger,
        "rows": rows,
        "hygiene": hygiene(rows),
        "spend": spend_of(usages),
        "transport_failures": elicitor.transport_failures,
        "failure_reasons": dict(elicitor.failure_reasons),
        "api_calls": elicitor.api_calls,
        "replayed": elicitor.replayed,
    })


def _paired_arm(args: argparse.Namespace, arm: str, transform: Any, sample: int) -> dict[str, Any]:
    """`repeat` and `sham` are one function: same subset, same pairing, one different text."""
    census = load_result(args.substrate, "census", bool(args.dry_run))
    wanted = set(noise_subset(census))
    units = [unit for unit in load_units(args)[0] if unit["unit_id"] in wanted]
    missing = wanted - {unit["unit_id"] for unit in units}
    if missing:
        raise SystemExit(f"{len(missing)} unit(s) in the subset are not in the substrate: "
                         f"{sorted(missing)[:5]}")
    quote = args.substrate != "royalroad"
    elicitor = _elicitor(args, arm)
    jobs = [(unit, transform(unit["text"]), sample) for unit in units]
    with elicitor:
        rows, usages = _sweep(elicitor, jobs, arm=arm, dry_run=args.dry_run,
                              workers=elicitor.max_workers, quote=quote)
    base = {row["unit_id"]: row for row in census["rows"]}
    pairs = []
    for row in rows:
        first = base.get(row["unit_id"])
        if first is None or first["refused"] or first["unparseable"] or row["refused"] \
                or row["unparseable"]:
            continue
        pairs.append({
            "unit_id": row["unit_id"],
            "cohort": row["cohort"],
            "words": row["words"],
            "census_counted": first["counted"],
            f"{arm}_counted": row["counted"],
            "abs_delta": abs(first["counted"] - row["counted"]),
            "signed_delta": row["counted"] - first["counted"],
            "abs_delta_per_1k": round(
                1000.0 * abs(first["counted"] - row["counted"]) / max(row["words"], 1), 4
            ),
            "anchor_overlap": jaccard(
                [beat["hash"] for beat in first["beats"]],
                [beat["hash"] for beat in row["beats"]],
            ),
        })
    return _envelope(args, arm, {
        "subset": sorted(wanted),
        "rows": rows,
        "pairs": pairs,
        "hygiene": hygiene(rows),
        "spend": spend_of(usages),
        "transport_failures": elicitor.transport_failures,
        "failure_reasons": dict(elicitor.failure_reasons),
        "api_calls": elicitor.api_calls,
        "replayed": elicitor.replayed,
        "summary": _spread_summary(pairs, arm),
    })


def _spread_summary(pairs: list[dict[str, Any]], arm: str) -> dict[str, Any]:
    """The ruler, or the thing read against it. No verdict here: `sham` is judged in the report,
    where the repeat spread it is read against is available."""
    deltas = [float(pair["abs_delta"]) for pair in pairs]
    overlaps = [pair["anchor_overlap"] for pair in pairs if pair["anchor_overlap"] is not None]
    return {
        "arm": arm,
        "pairs": len(pairs),
        "abs_delta_beats": describe(deltas) if deltas else {"n": 0},
        "abs_delta_per_1k": describe(
            [float(pair["abs_delta_per_1k"]) for pair in pairs]
        ) if pairs else {"n": 0},
        "signed_delta_mean": round(
            statistics.fmean([float(pair["signed_delta"]) for pair in pairs]), 4
        ) if pairs else None,
        "anchor_overlap": describe(overlaps) if overlaps else {"n": 0},
    }


def run_repeat(args: argparse.Namespace) -> dict[str, Any]:
    """Sample 1 of a byte-identical request. The variation is the model's own sampling."""
    return _paired_arm(args, "repeat", lambda text: text, 1)


def run_sham(args: argparse.Namespace) -> dict[str, Any]:
    """`ablate.rewhitespace` at full strength: not one character of any word changes."""
    from ablate import rewhitespace

    return _paired_arm(args, "sham", lambda text: rewhitespace(text, 1.0), 0)


# ----------------------------------------------------------------------------- the strip arm


def prose_beats(row: dict[str, Any]) -> int:
    """Located beats excluding `system_voice`, which the revision contract cannot touch.

    The strip arm's target and its internal control are the two halves of one count, so the
    split is a named function rather than an expression repeated six times inside the pairing.
    """
    return row["counted"] - row["by_kind"].get("system_voice", 0)


def certify(original: str, variant: str) -> dict[str, Any]:
    """The deterministic checks that make a revision a certified minimal one.

    `repair_generation.compliance`'s pattern at chapter grain: word-level similarity, a two-sided
    growth bound, and byte-survival of every protected span. A revision that fails any of them
    certifies nothing and is excluded from the pairing with its reason named.
    """
    from writer_states import system_voice_survival

    similarity = round(
        difflib.SequenceMatcher(None, original.split(), variant.split()).ratio(), 4
    )
    growth = round(
        100.0 * (len(variant.split()) - len(original.split())) / max(len(original.split()), 1), 2
    )
    survival = system_voice_survival(original, variant)
    reasons = []
    if similarity < STRIP_MIN_SIMILARITY:
        reasons.append(f"similarity {similarity} < {STRIP_MIN_SIMILARITY}")
    if abs(growth) > STRIP_MAX_GROWTH_PCT:
        reasons.append(f"word growth {growth}% outside +-{STRIP_MAX_GROWTH_PCT}%")
    if survival["kept"] != survival["spans"]:
        reasons.append(f"protected spans {survival['kept']}/{survival['spans']} survived")
    return {
        "similarity": similarity,
        "word_growth_pct": growth,
        "protected_spans": survival["spans"],
        "protected_kept": survival["kept"],
        "certified": not reasons,
        "reasons": reasons,
    }


def run_strip(args: argparse.Namespace) -> dict[str, Any]:
    """The damage direction, with its placebo beside it and its own internal control inside it."""
    from writer_states import GEN_MAX_WORKERS, WRITER_MODEL, Generator

    census = load_result(args.substrate, "census", bool(args.dry_run))
    wanted = set(strip_subset(census))
    units = {unit["unit_id"]: unit for unit in load_units(args)[0] if unit["unit_id"] in wanted}
    if len(units) < len(wanted):
        raise SystemExit(f"{len(wanted) - len(units)} strip-subset unit(s) missing from the "
                         "substrate; the census and the substrate have diverged")
    rule = ("top decile by located density" if args.substrate == "royalroad"
            else f"own units with at least {STRIP_OWN_MIN_BEATS} beats")
    print(f"  strip subset: {len(units)} unit(s), {rule}", file=sys.stderr, flush=True)

    generations: dict[tuple[str, str], str] = {}
    gen_cache = DERIVED / (
        f"comic-beats-{args.substrate}-strip-gen{'-dry' if args.dry_run else ''}.jsonl"
    )
    with Generator(gen_cache, model=args.writer_model or WRITER_MODEL,
                   dry_run=bool(args.dry_run)) as generator:
        jobs = [(unit_id, task) for unit_id in sorted(units) for task in sorted(STRIP_TASKS)]

        def _generate(index: int) -> tuple[tuple[str, str], dict[str, Any]]:
            unit_id, task = jobs[index]
            text = units[unit_id]["text"]
            return (unit_id, task), generator.generate(
                {"unit": unit_id, "task": task},
                STRIP_SYSTEM,
                STRIP_RULES.format(task=STRIP_TASKS[task]) + f"\n\n---\n\n{text}",
                dry_text=text,
            )

        # `writer_states.GEN_MAX_WORKERS`, which is that module's own declared concurrency for
        # exactly this call shape (a whole scene generated over `claude -p`), rather than a
        # number chosen here. Measured beside it: one whole-chapter revision runs about two and a
        # half minutes, so a sequential loop over a top-decile subset is hours of wall clock for
        # no reason. `Generator`'s write lock covers the shared cache and its digest keying makes
        # an interruption lossless, which is the checkpoint-per-unit property this box needs.
        done = 0
        with ThreadPoolExecutor(max_workers=GEN_MAX_WORKERS) as pool:
            for label, record in pool.map(_generate, range(len(jobs))):
                if not record.get("refused"):
                    generations[label] = str(record.get("text") or "")
                done += 1
                _progress("generate", done, len(jobs))
        gen_calls, gen_replayed = generator.api_calls, generator.replayed

    certificates: dict[tuple[str, str], dict[str, Any]] = {}
    for (unit_id, task), variant in generations.items():
        certificates[(unit_id, task)] = certify(units[unit_id]["text"], variant)

    elicitor = _elicitor(args, "strip")
    jobs2: list[tuple[dict[str, Any], str, int]] = []
    labels: list[tuple[str, str]] = []
    for (unit_id, task), variant in sorted(generations.items()):
        jobs2.append(({**units[unit_id], "unit_id": f"{unit_id}|{task}",
                       "words": len(variant.split())}, variant, 0))
        labels.append((unit_id, task))
    quote = args.substrate != "royalroad"
    with elicitor:
        rows, usages = _sweep(elicitor, jobs2, arm="strip", dry_run=args.dry_run,
                              workers=elicitor.max_workers, quote=quote)
    scored = dict(zip(labels, rows, strict=True))

    base = {row["unit_id"]: row for row in census["rows"]}
    spread = {}
    repeat_path = result_path(args.substrate, "repeat", bool(args.dry_run))
    if repeat_path.is_file():
        for pair in load_result(args.substrate, "repeat", bool(args.dry_run))["pairs"]:
            spread[pair["unit_id"]] = float(pair["abs_delta"])

    pairs: list[dict[str, Any]] = []
    uncertified: list[dict[str, Any]] = []
    for unit_id in sorted(units):
        original = base.get(unit_id)
        stripped = scored.get((unit_id, "strip"))
        placebo = scored.get((unit_id, "strip_placebo"))
        if original is None or stripped is None or placebo is None:
            uncertified.append({"unit_id": unit_id, "reasons": ["a call did not return"]})
            continue
        certs = {task: certificates[(unit_id, task)] for task in ("strip", "strip_placebo")}
        changed_more = certs["strip"]["similarity"] < certs["strip_placebo"]["similarity"]
        reasons = [f"{task}: {reason}" for task, cert in certs.items() for reason in
                   cert["reasons"]]
        if not changed_more:
            reasons.append(
                f"strip similarity {certs['strip']['similarity']} is not below the placebo's "
                f"{certs['strip_placebo']['similarity']}: it did not change more than the floor"
            )
        if stripped["refused"] or placebo["refused"] or stripped["unparseable"] \
                or placebo["unparseable"]:
            reasons.append("a census call on a revision refused or did not parse")
        if reasons:
            uncertified.append({"unit_id": unit_id, "reasons": reasons,
                                "certificates": certs})
            continue
        pairs.append({
            "unit_id": unit_id,
            "cohort": original["cohort"],
            "words": original["words"],
            "original_counted": original["counted"],
            "strip_counted": stripped["counted"],
            "placebo_counted": placebo["counted"],
            "drop_strip": original["counted"] - stripped["counted"],
            "drop_placebo": original["counted"] - placebo["counted"],
            "prose_original": prose_beats(original),
            "prose_strip": prose_beats(stripped),
            "prose_placebo": prose_beats(placebo),
            "system_voice_original": original["by_kind"].get("system_voice", 0),
            "system_voice_strip": stripped["by_kind"].get("system_voice", 0),
            "protected_spans": certs["strip"]["protected_spans"],
            "repeat_spread": spread.get(unit_id),
            "certificates": certs,
        })

    readings = strip_readings(pairs, hygiene([scored[label] for label in labels]))
    return _envelope(args, "strip", {
        "writer_model": args.writer_model or WRITER_MODEL,
        "subset": sorted(wanted),
        "generation_calls": gen_calls,
        "generation_replayed": gen_replayed,
        "rows": rows,
        "pairs": pairs,
        "uncertified": uncertified,
        "hygiene": hygiene(rows),
        "spend": spend_of(usages),
        "transport_failures": elicitor.transport_failures,
        "failure_reasons": dict(elicitor.failure_reasons),
        "api_calls": elicitor.api_calls,
        "replayed": elicitor.replayed,
        "readings": readings,
    })


def system_voice_control(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    """The strip arm's own internal control, read on its own terms and not through the sign test.

    The revision contract copies protected spans byte-for-byte, so a `system_voice` beat cannot
    be stripped and the pre-registered expectation is that its count does not move. **The shared
    sign test cannot express that**: a zero difference leaves the denominator by design, so a
    control that moved on nothing at all reads INSUFFICIENT_N, which is the exact opposite of
    what happened. So the three outcomes are named here — nothing fell is CONTROL_HOLDS,
    a significant fall is CONTROL_FAILS, and anything between is CONTROL_UNDECIDED with the
    interval printed — and EMPTY stays a fourth, for a subset with no protected span to
    preserve. None of the four is a pass by silence.
    """
    with_spans = [pair for pair in pairs if pair["protected_spans"] > 0]
    if not with_spans:
        return {
            "verdict": "EMPTY",
            "because": ("no unit in the subset carries a protected system-voice span, so the arm "
                        "has no line the revision was forbidden to touch"),
            "pairs": 0,
        }
    deltas = [
        float(pair["system_voice_original"] - pair["system_voice_strip"]) for pair in with_spans
    ]
    fell = sum(1 for delta in deltas if delta > 0)
    rose = sum(1 for delta in deltas if delta < 0)
    test = paired_reading(
        deltas, name="system_voice beats fall too, which the contract forbids",
        positive_verdict="CONTROL_FAILS", null_verdict="CONTROL_UNDECIDED",
    )
    if test["verdict"] == "CONTROL_FAILS":
        verdict = "CONTROL_FAILS"
    elif fell == 0:
        verdict = "CONTROL_HOLDS"
    else:
        verdict = "CONTROL_UNDECIDED"
    return {
        "verdict": verdict,
        "pairs": len(with_spans),
        "fell": fell,
        "rose": rose,
        "unchanged": len(with_spans) - fell - rose,
        "sign_test": test,
        "equivalence_bound": median_ci(deltas),
    }


def strip_readings(pairs: list[dict[str, Any]], strip_hygiene: dict[str, Any]) -> dict[str, Any]:
    """Both declared readings, the internal control, and the refusal state, all printed.

    Nothing here reads as a pass by silence: each reading carries its decided-pair count, its
    attainable floor, the k it needed and a distribution-free interval on the median it did or
    did not move.
    """
    against_placebo = paired_reading(
        [float(pair["drop_strip"] - pair["drop_placebo"]) for pair in pairs],
        name="strip drop exceeds its placebo's drop, in beats",
        positive_verdict="SEES", null_verdict="DOES_NOT_SEE",
    )
    floored = [pair for pair in pairs if pair["repeat_spread"] is not None]
    if floored or not pairs:
        # No certified pairs is INSUFFICIENT_N and not a missing arm: the two are different
        # facts and reporting one as the other is how a mapped hole turns into a shrug.
        against_noise = paired_reading(
            [float(pair["drop_strip"] - pair["repeat_spread"]) for pair in floored],
            name="strip drop exceeds this chapter's own repeat spread, in beats",
            positive_verdict="SEES", null_verdict="DOES_NOT_SEE",
        )
    else:
        against_noise = {
            "statistic": "strip drop exceeds this chapter's own repeat spread, in beats",
            "verdict": "NOT_RUN",
            "because": ("the repeat arm has not run on this substrate, so no chapter has a "
                        "noise floor of its own to be read against"),
        }
    control = system_voice_control(pairs)
    drops = [float(pair["drop_strip"]) for pair in pairs]
    median_drop = statistics.median(drops) if drops else 0.0
    confab = strip_hygiene.get("confabulated_per_unit") or 0.0
    if not drops:
        refusal = "NOT_APPLICABLE"
    elif confab >= 0.5 * median_drop:
        refusal = "VOID"
    else:
        refusal = "READABLE"
    return {
        "pairs_certified": len(pairs),
        "against_placebo": against_placebo,
        "against_noise_floor": against_noise,
        "internal_control_system_voice": control,
        "prose_kinds_only": paired_reading(
            [float((pair["prose_original"] - pair["prose_strip"])
                   - (pair["prose_original"] - pair["prose_placebo"])) for pair in pairs],
            name="prose-kind drop exceeds the placebo's, in beats",
            positive_verdict="SEES", null_verdict="DOES_NOT_SEE",
        ),
        "median_drop_beats": round(median_drop, 4),
        "confabulated_per_unit": round(confab, 4),
        "refusal_state": {
            "rule": ("VOID if confabulated beats per unit >= half the median strip drop: an "
                     "effect the instrument's own noise could manufacture is not an effect"),
            "verdict": refusal,
        },
    }


# --------------------------------------------------------------------------------- the price


def run_price(args: argparse.Namespace) -> dict[str, Any]:
    """A declared pricing batch, and it writes a price rather than a census.

    The handoff's rule: dry-run, then ten live calls, then **report the projected cost before
    the main arm runs**. Two things make this an arm of its own rather than a truncated census.
    It writes to its own file, because a partial census committed under the census's name is the
    silent-cap failure in a different costume. And it draws its units **spread across the
    word-count range** rather than from the front, because the price of one call is dominated by
    what the model writes about a chapter and that scales with the chapter.

    The calls land in the census arm's own cache, so nothing here is bought twice: the census
    replays every one of them for free.

    §79.1 in the cost direction. No figure from §85 or §104 projects this run; the projection is
    a least-squares fit of measured equivalent price against chapter length, on these calls, on
    this transport, this week.
    """
    from elicit import PANEL_MODEL

    units, ledger = load_units(args)
    count = max(2, min(args.price, len(units)))
    ordered = sorted(units, key=lambda unit: (unit["words"], unit["unit_id"]))
    picked: list[dict[str, Any]] = []
    for index in range(count):
        candidate = ordered[round(index * (len(ordered) - 1) / max(count - 1, 1))]
        if candidate["unit_id"] not in {unit["unit_id"] for unit in picked}:
            picked.append(candidate)

    elicitor = _elicitor(args, "census")
    jobs = [(unit, unit["text"], 0) for unit in picked]
    with elicitor:
        rows, usages = _sweep(elicitor, jobs, arm="price", dry_run=args.dry_run,
                              workers=elicitor.max_workers,
                              quote=args.substrate != "royalroad")
    priced = [
        {"unit_id": unit["unit_id"], "words": unit["words"],
         "usd": round(float((usage or {}).get("equivalent_usd") or 0.0), 6),
         "output_tokens": int((usage or {}).get("output") or 0),
         "counted": row["counted"]}
        for unit, usage, row in zip(picked, usages, rows, strict=True)
    ]
    fit = _fit_cost(priced)
    return _envelope(args, "price", {
        "model": args.model or PANEL_MODEL,
        "sampled": priced,
        "fit": fit,
        "projection": _project(fit, units, args),
        "exclusions": ledger,
        "hygiene": hygiene(rows),
        "spend": spend_of(usages),
        "transport_failures": elicitor.transport_failures,
        "failure_reasons": dict(elicitor.failure_reasons),
        "api_calls": elicitor.api_calls,
        "replayed": elicitor.replayed,
        "note": ("Deliberation depth is whatever the local `claude` install applies. It is not a "
                 "parameter of this instrument, it is constant across every arm, and it is the "
                 "dominant term in this price: the transport reports most of each answer's "
                 "output tokens as thinking."),
    })


def _fit_cost(priced: list[dict[str, Any]]) -> dict[str, Any]:
    """Least squares of equivalent price against chapter length. Two numbers and their residual."""
    if len(priced) < 2:
        return {"n": len(priced), "intercept_usd": None, "slope_usd_per_1k_words": None}
    xs = [row["words"] / 1000.0 for row in priced]
    ys = [row["usd"] for row in priced]
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    denominator = sum((x - mx) ** 2 for x in xs)
    slope = (sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / denominator
             if denominator else 0.0)
    intercept = my - slope * mx
    residuals = [y - (intercept + slope * x) for x, y in zip(xs, ys, strict=True)]
    return {
        "n": len(priced),
        "intercept_usd": round(intercept, 6),
        "slope_usd_per_1k_words": round(slope, 6),
        "mean_usd": round(my, 6),
        "residual_sd_usd": round(statistics.pstdev(residuals), 6) if len(residuals) > 1 else 0.0,
        "note": ("the intercept is the transport's own per-call overhead, since the CLI sends its "
                 "base prompt on every call, and the slope is what the chapter itself costs"),
    }


def _project(
    fit: dict[str, Any], units: list[dict[str, Any]], args: argparse.Namespace
) -> dict[str, Any]:
    """What every remaining arm on this substrate would cost at the measured rate.

    The call counts are exact: they come from the same subset functions the arms use, so the only
    estimated quantity is the price of one call. The strip arm's revisions are **not** projected
    from this fit and say so instead of carrying a number: they run on a different model at a
    different tier, and their output is a whole chapter rather than a list of anchors.
    """
    intercept = fit.get("intercept_usd")
    slope = fit.get("slope_usd_per_1k_words")
    if intercept is None or slope is None:
        return {"projected": None, "because": "fewer than two priced calls"}

    def cost(rows: list[dict[str, Any]]) -> float:
        return round(
            sum(max(intercept + slope * unit["words"] / 1000.0, 0.0) for unit in rows), 2
        )

    census_path = result_path(args.substrate, "census", bool(args.dry_run))
    by_id = {unit["unit_id"]: unit for unit in units}
    plan: dict[str, Any] = {"census": {"calls": len(units), "usd": cost(units)}}
    if census_path.is_file():
        census = json.loads(census_path.read_text(encoding="utf-8"))
        noise = [by_id[uid] for uid in noise_subset(census) if uid in by_id]
        strip = [by_id[uid] for uid in strip_subset(census) if uid in by_id]
        plan["repeat"] = {"calls": len(noise), "usd": cost(noise)}
        plan["sham"] = {"calls": len(noise), "usd": cost(noise)}
        plan["strip_census_calls"] = {"calls": 2 * len(strip), "usd": cost(strip + strip)}
        plan["strip_revisions"] = {
            "calls": 2 * len(strip),
            "usd": None,
            "because": ("a whole-chapter revision on the writer tier is a different price and is "
                        "not projected from a locator fit; it is measured on its own first calls"),
        }
    else:
        plan["note"] = ("the census has not run, so the repeat, sham and strip subsets do not "
                        "exist yet and only the census leg is projected")
    plan["total_projected_usd"] = round(
        sum(float(entry["usd"]) for entry in plan.values()
            if isinstance(entry, dict) and isinstance(entry.get("usd"), int | float)), 2
    )
    return plan


# --------------------------------------------------------------------------------- the report


def _ranks(values: list[float]) -> list[float]:
    """Average ranks, so ties do not manufacture a correlation."""
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    position = 0
    while position < len(order):
        end = position
        while end + 1 < len(order) and values[order[end + 1]] == values[order[position]]:
            end += 1
        shared = (position + end) / 2.0 + 1.0
        for index in range(position, end + 1):
            ranks[order[index]] = shared
        position = end + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> float | None:
    """Rank correlation. Here for one job: is the located density a function of chapter length?

    A model reading a longer chapter has more to hold, and if density falls with length then our
    own 4,200-word chapters are being compared against a population whose median chapter is half
    that. The residual is named and measured rather than assumed away.
    """
    if len(xs) < 3 or len(xs) != len(ys):
        return None
    rx, ry = _ranks(xs), _ranks(ys)
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    numerator = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    denominator = math.sqrt(
        sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)
    )
    return round(numerator / denominator, 4) if denominator else None


#: How wide a length-matched comparison band is, as a fraction of the own chapter's word count.
#: Wide enough to keep an n worth quoting at 249 chapters, narrow enough that the matched
#: population is not the whole population wearing a label.
LENGTH_BAND = 0.30


def run_report(args: argparse.Namespace) -> dict[str, Any]:
    """Merge the arms into the numbers `comic-beats-results.md` quotes. Spends nothing."""
    dry = bool(args.dry_run)
    _load_texts(args)
    rr = load_result("royalroad", "census", dry)
    local = load_result("local", "census", dry)

    rr_rows = scoreable(rr)
    densities = [float(row["density_per_1k"]) for row in rr_rows]
    by_cohort: dict[str, list[dict[str, Any]]] = {}
    for row in rr_rows:
        by_cohort.setdefault(str(row["cohort"]), []).append(row)

    q1 = {
        "pooled": describe(densities),
        "by_cohort": {
            cohort: describe([float(row["density_per_1k"]) for row in members])
            for cohort, members in sorted(by_cohort.items())
        },
        "counts_pooled": describe([float(row["counted"]) for row in rr_rows]),
        "zero_beat_share": round(
            sum(1 for row in rr_rows if row["counted"] == 0) / max(len(rr_rows), 1), 4
        ),
        "kind_mix": _kind_mix(rr_rows),
        "words": describe([float(row["words"]) for row in rr_rows]),
        "length_residual": {
            "spearman_density_vs_words": spearman(
                [float(row["words"]) for row in rr_rows], densities
            ),
            "note": ("negative means longer chapters yield fewer located beats per 1k, which "
                     "would confound a placement of our own longer chapters"),
        },
        "familiarity_confound": (
            "RoyalRoad text may be memorised by the locator (BRIEF §2 Pass 6). This baseline "
            "carries that term and our own chapters do not; the two are never pooled and this "
            "percentile is read with the term named."
        ),
    }

    local_rows = scoreable(local)
    chapters = [row for row in local_rows if row["cohort"] == "own_chapter"]
    scenes = [row for row in local_rows if row["cohort"] == "own_scene"]
    q2 = {
        "chapters": [
            {
                "unit_id": row["unit_id"],
                "words": row["words"],
                "counted": row["counted"],
                "density_per_1k": row["density_per_1k"],
                "by_kind": row["by_kind"],
                "percentile_pooled": percentile_of(float(row["density_per_1k"]), densities),
                "percentile_by_cohort": {
                    cohort: percentile_of(
                        float(row["density_per_1k"]),
                        [float(other["density_per_1k"]) for other in members],
                    )
                    for cohort, members in sorted(by_cohort.items())
                },
                "length_matched": _length_matched(row, rr_rows),
            }
            for row in chapters
        ],
        "toll_road_scenes": {
            "per_scene_density": [row["density_per_1k"] for row in scenes],
            "summary": describe([float(row["density_per_1k"]) for row in scenes])
            if scenes else {"n": 0},
            "median_percentile_pooled": percentile_of(
                statistics.median([float(row["density_per_1k"]) for row in scenes]), densities
            ) if scenes else None,
            "note": ("secondary colour only: a scene is internal structure and the unit a reader "
                     "receives is the chapter"),
        },
        "kind_mix": _kind_mix(chapters),
    }

    q3 = {substrate: _q3(substrate, dry) for substrate in ("royalroad", "local")}

    spend = {}
    total = 0.0
    for substrate in ("royalroad", "local"):
        for arm in ("census", "repeat", "sham", "strip"):
            path = result_path(substrate, arm, dry)
            if not path.is_file():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            usd = float((payload.get("spend") or {}).get("equivalent_usd") or 0.0)
            spend[f"{substrate}/{arm}"] = round(usd, 4)
            total += usd
        # The strip arm's own `spend` covers its locator calls and not the revisions that
        # produced the text they read: those go through `writer_states.Generator`, on a different
        # model, into a different cache. Counting only the locator would report a third of what
        # the arm cost.
        generations = DERIVED / f"comic-beats-{substrate}-strip-gen.jsonl"
        if generations.is_file():
            spent = 0.0
            calls = 0
            for line in generations.read_text(encoding="utf-8").splitlines():
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                spent += float((record.get("usage") or {}).get("equivalent_usd") or 0.0)
                calls += 1
            spend[f"{substrate}/strip_revisions"] = round(spent, 4)
            spend[f"{substrate}/strip_revision_calls"] = calls
            total += spent
    spend["total_equivalent_usd"] = round(total, 4)
    spend["note"] = ("equivalent price for quota already paid for on a subscription, from the "
                     "transport's own envelopes; measured, never projected from another entry")

    return {
        "registration_digest": registration_digest(),
        "pre_registration": PRE_REGISTRATION,
        "q1_royalroad_baseline": q1,
        "q2_placement": q2,
        "q3_validity": q3,
        "spend": spend,
        "reading": _headline(q1, q2, q3),
    }


def _kind_mix(rows: list[dict[str, Any]]) -> dict[str, Any]:
    totals = dict.fromkeys(KINDS, 0)
    for row in rows:
        for kind, count in row["by_kind"].items():
            totals[kind] = totals.get(kind, 0) + count
    grand = sum(totals.values())
    return {
        "counts": totals,
        "share": {kind: round(value / grand, 4) for kind, value in totals.items()}
        if grand else {},
        "total": grand,
    }


def _length_matched(row: dict[str, Any], population: list[dict[str, Any]]) -> dict[str, Any]:
    """The same percentile against chapters of comparable length. The length residual, controlled.

    Reported with its `n` in front of it: at 249 chapters a +-30% band around a 4,200-word
    chapter is a few dozen, and a percentile on a few dozen is a coarse instrument that says so.
    """
    low, high = row["words"] * (1 - LENGTH_BAND), row["words"] * (1 + LENGTH_BAND)
    matched = [
        float(other["density_per_1k"]) for other in population if low <= other["words"] <= high
    ]
    return {
        "band_words": [round(low), round(high)],
        "n": len(matched),
        "percentile": percentile_of(float(row["density_per_1k"]), matched) if matched else None,
        "summary": describe(matched) if matched else {"n": 0},
    }


def reliability(census: dict[str, Any], repeat: dict[str, Any] | None) -> dict[str, Any]:
    """How much of Q1's spread is between chapters and how much is the instrument.

    The `repeat` arm measures one thing directly: the sd of the difference between two draws on
    the same chapter. Under the usual decomposition that is `sqrt(2)` times the sd of a single
    measurement's error, so the population's observed variance splits into a true between-chapter
    part and an instrument part with no free parameters.

    **This is what the repeat arm is for**, and it is the difference between "the distribution is
    noise" and "the distribution is real and wider than the truth". It assumes the error is
    homoscedastic across chapters and independent between draws; neither is checked here, and
    both are stated rather than assumed silently. The reliability's square root is the ceiling on
    any correlation this measure could ever show with anything, which is the number a later
    programme should be told before it tries to correlate it with a reader.
    """
    rows = scoreable(census)
    densities = [float(row["density_per_1k"]) for row in rows]
    if len(densities) < 2 or not repeat or not repeat.get("pairs"):
        return {"verdict": "NOT_COMPUTED",
                "because": "needs a census distribution and a repeat arm on the same substrate"}
    signed = [
        1000.0 * (pair[f"{repeat['arm']}_counted"] - pair["census_counted"])
        / max(pair["words"], 1)
        for pair in repeat["pairs"]
    ]
    if len(signed) < 2:
        return {"verdict": "NOT_COMPUTED", "because": "fewer than two repeat pairs"}
    sd_difference = statistics.pstdev(signed)
    sd_noise = sd_difference / math.sqrt(2.0)
    sd_observed = statistics.pstdev(densities)
    variance_true = sd_observed ** 2 - sd_noise ** 2
    reliable = variance_true / sd_observed ** 2 if sd_observed else None
    return {
        "unit": "beats per 1,000 words",
        "repeat_pairs": len(signed),
        "sd_of_paired_difference": round(sd_difference, 4),
        "sd_single_measurement_noise": round(sd_noise, 4),
        "sd_population_observed": round(sd_observed, 4),
        "sd_population_implied_true": round(max(variance_true, 0.0) ** 0.5, 4),
        "reliability": round(reliable, 4) if reliable is not None else None,
        "correlation_ceiling": round(max(reliable, 0.0) ** 0.5, 4) if reliable is not None
        else None,
        "assumes": ("error homoscedastic across chapters and independent between draws; neither "
                    "is checked here"),
        "note": ("draws_to_reach(r) below is what it would cost to fix: averaging k independent "
                 "draws per chapter divides the noise variance by k"),
        "draws_to_reach": {
            str(target): (
                None if reliable is None or reliable <= 0 or reliable >= target
                else math.ceil(
                    (target * (1 - reliable)) / (reliable * (1 - target))
                )
            )
            for target in (0.8, 0.9)
        },
    }


def same_text_control(substrate: str, strip: dict[str, Any] | None,
                      texts: dict[str, str]) -> dict[str, Any]:
    """An **unregistered** control that the design produced by accident, reported as one.

    `strip_placebo` asks for an inert revision (fix any typos), and on most units the writer
    returned the chapter unchanged. Because each arm holds its own cache file, that call was
    re-issued rather than replayed \u2014 so on every unit whose placebo normalises identically to
    the original, the placebo count is a second draw on **the same text**.

    It was not declared before the run and it does not stand in for the `repeat` arm; both print,
    and the pre-registered one is the one the strip arm is read against. It is here because it is
    the least deniable form of the same measurement: not a byte-identical *request*, but a
    byte-identical *chapter*, arrived at through a different arm.
    """
    if not strip or not strip.get("pairs"):
        return {"verdict": "NOT_RUN", "because": "no certified strip pairs on this substrate"}
    if not texts:
        return {"verdict": "NOT_COMPUTED",
                "because": ("the substrate's text is not available to this run; for `local` pass "
                            "--library and --toll, which are gitignored build products")}
    cache = DERIVED / f"comic-beats-{substrate}-strip-gen.jsonl"
    if not cache.is_file():
        return {"verdict": "NOT_COMPUTED", "because": f"{cache.name} is not present"}
    placebo: dict[str, str] = {}
    for line in cache.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("task") == "strip_placebo" and not record.get("refused"):
            placebo[str(record.get("unit"))] = str(record.get("text") or "")
    deltas: list[float] = []
    identical_bytes = 0
    for pair in strip["pairs"]:
        unit_id = pair["unit_id"]
        original, variant = texts.get(unit_id), placebo.get(unit_id)
        if original is None or variant is None:
            continue
        if normalise(original) != normalise(variant):
            continue
        identical_bytes += int(original == variant)
        deltas.append(float(abs(pair["original_counted"] - pair["placebo_counted"])))
    if not deltas:
        return {"verdict": "NOT_COMPUTED",
                "because": "no placebo revision came back identical to its original"}
    return {
        "status": "UNREGISTERED: not declared before the run; reported beside the repeat arm, "
                  "never instead of it",
        "units_same_after_normalisation": len(deltas),
        "units_byte_identical": identical_bytes,
        "abs_delta_beats": describe(deltas),
        "note": ("each arm holds its own cache file, so a byte-identical text was re-issued "
                 "rather than replayed and the placebo count is a second independent draw"),
    }


def _q3(substrate: str, dry: bool = False) -> dict[str, Any]:
    """Every control's number for one substrate, or the fact that an arm has not run."""
    out: dict[str, Any] = {}
    repeat_path = result_path(substrate, "repeat", dry)
    sham_path = result_path(substrate, "sham", dry)
    repeat = json.loads(repeat_path.read_text(encoding="utf-8")) if repeat_path.is_file() else None
    sham = json.loads(sham_path.read_text(encoding="utf-8")) if sham_path.is_file() else None
    out["repeat"] = repeat["summary"] if repeat else {"verdict": "NOT_RUN"}
    out["sham"] = sham["summary"] if sham else {"verdict": "NOT_RUN"}
    if repeat and sham:
        floor = {pair["unit_id"]: float(pair["abs_delta"]) for pair in repeat["pairs"]}
        deltas = [
            float(pair["abs_delta"]) - floor[pair["unit_id"]]
            for pair in sham["pairs"] if pair["unit_id"] in floor
        ]
        out["sham_vs_repeat"] = paired_reading(
            deltas,
            name="the layout sham moves the count further than a re-ask does, in beats",
            positive_verdict="LAYOUT_SENSITIVE", null_verdict="INSIDE_NOISE",
        )
        out["sham_vs_repeat"]["reading_note"] = (
            "INSIDE_NOISE is read only with the equivalence bound beside it (§101.1): the "
            "interval is the layout sensitivity this design could not exclude, in beats."
        )
    else:
        out["sham_vs_repeat"] = {"verdict": "NOT_RUN"}
    strip_path = result_path(substrate, "strip", dry)
    strip = json.loads(strip_path.read_text(encoding="utf-8")) if strip_path.is_file() else None
    if strip:
        out["strip"] = strip["readings"]
        out["strip"]["uncertified"] = len(strip["uncertified"])
        out["strip"]["writer_model"] = strip.get("writer_model")
        out["strip"]["certificates"] = _certificate_summary(strip)
    else:
        out["strip"] = {"verdict": "NOT_RUN"}
    census_path = result_path(substrate, "census", dry)
    if census_path.is_file():
        out["reliability"] = reliability(
            json.loads(census_path.read_text(encoding="utf-8")), repeat
        )
    out["same_text_control"] = same_text_control(substrate, strip, _TEXTS.get(substrate, {}))
    return out


def _certificate_summary(strip: dict[str, Any]) -> dict[str, Any]:
    """What the revisions actually were, so a null cannot be blamed on a manipulation nobody
    checked. A strip that changed nothing and a locator that cannot see are different findings."""
    rows = [pair["certificates"] for pair in strip["pairs"]]
    if not rows:
        return {"pairs": 0}
    return {
        "pairs": len(rows),
        "strip_similarity": describe([float(row["strip"]["similarity"]) for row in rows]),
        "placebo_similarity": describe(
            [float(row["strip_placebo"]["similarity"]) for row in rows]
        ),
        "strip_word_growth_pct": describe(
            [float(row["strip"]["word_growth_pct"]) for row in rows]
        ),
        "protected_spans_total": sum(int(row["strip"]["protected_spans"]) for row in rows),
        "protected_spans_kept": sum(int(row["strip"]["protected_kept"]) for row in rows),
    }


#: Substrate texts, loaded once by `run_report` so `_q3` can reach them without threading `args`
#: through every reading. Empty for a substrate whose text this run cannot read, which is a
#: `NOT_COMPUTED` rather than a silent zero.
_TEXTS: dict[str, dict[str, str]] = {}


def _load_texts(args: argparse.Namespace) -> None:
    """Best-effort text for both substrates. A missing one degrades to NOT_COMPUTED, never to a
    number: `book-library/` and `exports/` are gitignored build products and a linked worktree
    does not have them."""
    try:
        _TEXTS["royalroad"] = {row["unit_id"]: row["text"] for row in load_royalroad()}
    except SystemExit:
        _TEXTS["royalroad"] = {}
    try:
        chapters, scenes = own_units(Path(args.library), Path(args.toll))
        _TEXTS["local"] = {unit["unit_id"]: unit["text"] for unit in chapters + scenes}
    except OSError:
        _TEXTS["local"] = {}


def _headline(q1: dict[str, Any], q2: dict[str, Any], q3: dict[str, Any]) -> dict[str, Any]:
    """One machine-readable sentence per question. The prose version lives in the results doc,
    and it is written from these fields rather than beside them."""
    pooled = q1["pooled"]
    chapters = q2["chapters"]
    return {
        "q1": (
            f"RoyalRoad LitRPG located levity runs at a median of "
            f"{pooled.get('quantiles', {}).get('0.5')} beats per 1,000 words over "
            f"{pooled.get('n')} chapters (mean {pooled.get('mean')}, p95 "
            f"{pooled.get('quantiles', {}).get('0.95')}, max {pooled.get('max')})."
        ),
        "q2": [
            f"{row['unit_id']}: {row['density_per_1k']}/1k, "
            f"{row['percentile_pooled']}th percentile pooled, "
            f"{row['length_matched']['percentile']}th among chapters of comparable length "
            f"(n={row['length_matched']['n']})."
            for row in chapters
        ],
        "q3": {
            substrate: {
                "sham": entry["sham_vs_repeat"].get("verdict"),
                "strip_vs_placebo": entry["strip"].get("against_placebo", {}).get("verdict")
                if isinstance(entry["strip"], dict) else None,
                "strip_refusal": entry["strip"].get("refusal_state", {}).get("verdict")
                if isinstance(entry["strip"], dict) else None,
            }
            for substrate, entry in q3.items()
        },
        "what_this_is_not": (
            "a quality claim. Beats per 1k words is a density of ATTEMPTS; a chapter with more "
            "of them is not better, and whether any of them lands is not measured here."
        ),
    }


# ------------------------------------------------------------------------------- the selftest


def selftest() -> int:
    """Schema shape, closed kinds, findability on synthetic text, arithmetic, and the freeze.

    Run before anything expensive, and re-run after every edit: the last check is the byte-freeze
    and it is the one that makes every committed number attributable to a particular instrument.
    """
    failures: list[str] = []

    def check(claim: str, ok: bool) -> None:
        if not ok:
            failures.append(claim)

    # -- the frozen block
    check("seven kinds, no duplicates", len(KINDS) == 7 == len(set(KINDS)))
    check("every kind has a definition", set(KIND_DEFINITIONS) == set(KINDS))
    check("the schema's enum is the closed set",
          SCHEMA["properties"]["beats"]["items"]["properties"]["kind"]["enum"] == list(KINDS))
    check("the schema is closed at both levels",
          SCHEMA["additionalProperties"] is False
          and SCHEMA["properties"]["beats"]["items"]["additionalProperties"] is False)
    check("both fields are required",
          SCHEMA["properties"]["beats"]["items"]["required"] == ["anchor", "kind"])
    quality_words = ("funny", "humour", "humor", "comedy", "joke", "good", "well", "succeed",
                     "successful", "works", "land", "lands", "effective", "quality", "better")
    asked = f"{SYSTEM}\n{QUESTION}\n{json.dumps(SCHEMA)}\n{json.dumps(KIND_DEFINITIONS)}".lower()
    for word in quality_words:
        check(f"the asking carries no quality vocabulary: {word!r}",
              not re.search(rf"\b{word}\b", asked))
    check("every kind is named in the system block",
          all(kind in SYSTEM for kind in KINDS))
    check("the anchor limit is stated in the asking", str(ANCHOR_MAX_WORDS) in SYSTEM)

    # -- findability, on synthetic text
    page = ("Weigh Street took its light late, which was, Silas had long thought, a joke at "
            "somebody's expense.\n\n**TOLL PAID — 9 days**\n\nHe said nothing.")
    scored = score_answer(page, {"beats": [
        {"anchor": "a joke at somebody's expense", "kind": "deadpan"},
        {"anchor": "a joke at somebody\u2019s expense", "kind": "quip"},
        {"anchor": "a wholly invented clause", "kind": "quip"},
        {"anchor": "TOLL PAID — 9 days", "kind": "system_voice"},
        {"anchor": "He said nothing.", "kind": "not_a_kind"},
    ]})
    check("a findable anchor counts", scored["counted"] == 2)
    check("a curly-quoted retype of the same span is a duplicate, not a second beat",
          scored["duplicate"] == 1)
    check("an invented anchor is a confabulation", scored["confabulated"] == 1)
    check("an em dash retyped as an em dash still matches",
          any(beat["kind"] == "system_voice" for beat in scored["beats"]))
    check("a kind outside the closed set is dropped", scored["bad_kind"] == 1)
    check("the confabulation is not in the count", scored["returned"] == 5)
    check("an over-long anchor is reported",
          score_answer(page, {"beats": [{"anchor": " ".join(page.split()[:20]),
                                         "kind": "quip"}]})["over_length"] == 1)
    check("an unparseable answer is unparseable and not a zero",
          score_answer(page, None)["unparseable"] is True)
    check("an empty list is a zero and not an error",
          score_answer(page, {"beats": []})["counted"] == 0
          and score_answer(page, {"beats": []})["unparseable"] is False)

    # -- the sham cannot change findability, which is what makes the arm comparable
    from ablate import rewhitespace

    reflowed = rewhitespace(page, 1.0)
    check("whitespace reflow changes no word", normalise(reflowed) == normalise(page))
    check("an anchor found in the reflowed text is findable in the original",
          score_answer(reflowed, {"beats": [{"anchor": "a joke at somebody's expense",
                                             "kind": "quip"}]})["counted"] == 1)

    # -- the arithmetic
    check("a perfect run hits exactly 1/2**G", one_sided_sign_p(8, 8) == 1 / 256)
    check("alpha is unreachable below the declared floor", required_k(4) is None)
    check("the declared floor is exactly reachable", required_k(MIN_PAIRS) == MIN_PAIRS)
    check("an even split is not evidence", one_sided_sign_p(5, 10) > ALPHA)
    check("k=0 is p=1", one_sided_sign_p(0, 10) == 1.0)
    check("no pairs is p=1", one_sided_sign_p(0, 0) == 1.0)
    check("a zero difference leaves the denominator",
          paired_reading([0.0, 0.0, 1.0], name="t", positive_verdict="A",
                         null_verdict="B")["pairs_decided"] == 1)
    check("too few decided pairs report INSUFFICIENT_N rather than a failure",
          paired_reading([1.0, 1.0], name="t", positive_verdict="A",
                         null_verdict="B")["verdict"] == "INSUFFICIENT_N")
    check("an unmoved control publishes an interval rather than a silence",
          paired_reading([0.5, -0.5, 0.5, -0.5, 0.5, -0.5, 0.5, -0.5], name="t",
                         positive_verdict="A", null_verdict="B")["equivalence_bound"]["n"] == 8)
    check("the median interval brackets the median",
          median_ci([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])["lo"] <= 4.0
          <= median_ci([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])["hi"])
    check("rank correlation finds a monotone relation",
          spearman([1.0, 2.0, 3.0, 4.0], [1.0, 2.0, 3.0, 4.0]) == 1.0)
    check("rank correlation finds its inverse",
          spearman([1.0, 2.0, 3.0, 4.0], [4.0, 3.0, 2.0, 1.0]) == -1.0)
    check("overlap of identical anchor sets is 1", jaccard(["a", "b"], ["b", "a"]) == 1.0)
    check("overlap of disjoint sets is 0", jaccard(["a"], ["b"]) == 0.0)
    check("two empty lists have no overlap to report", jaccard([], []) is None)

    # -- the window and the certification
    check("both own chapters fit the window",
          MIN_CHAPTER_WORDS <= 4151 <= MAX_CHAPTER_WORDS
          and MIN_CHAPTER_WORDS <= 4252 <= MAX_CHAPTER_WORDS)
    check("an unchanged revision certifies",
          certify("a b c d e f g h", "a b c d e f g h")["certified"] is True)
    check("a wholesale rewrite does not certify",
          certify("a b c d e f g h", "z y x w v u t s")["certified"] is False)
    check("a revision that grew past the bound does not certify",
          certify("a b c d e f g h", "a b c d e f g h i j k")["certified"] is False)
    check("a mangled protected span does not certify",
          certify("**TOLL PAID — 9 days**\n\nHe left.",
                  "**TOLL PAID, 9 days**\n\nHe left.")["certified"] is False)

    # -- the strip arm's readings, on synthetic pairs. The dry run cannot reach these: its
    # generator returns the chapter unchanged, which is the correct null and certifies nothing,
    # so without this block the reading arithmetic would run for the first time on paid data.
    def _pair(drop_strip: int, drop_placebo: int, spread: float | None, spans: int = 1,
              sv_before: int = 2, sv_after: int = 2) -> dict[str, Any]:
        return {
            "drop_strip": drop_strip, "drop_placebo": drop_placebo, "repeat_spread": spread,
            "protected_spans": spans,
            "system_voice_original": sv_before, "system_voice_strip": sv_after,
            "prose_original": 10, "prose_strip": 10 - drop_strip,
            "prose_placebo": 10 - drop_placebo,
        }

    clean = [_pair(4, 0, 1.0) for _ in range(6)]
    reading = strip_readings(clean, {"confabulated_per_unit": 0.1})
    check("a clean strip reads SEES against its placebo",
          reading["against_placebo"]["verdict"] == "SEES")
    check("a clean strip reads SEES against the noise floor",
          reading["against_noise_floor"]["verdict"] == "SEES")
    check("an untouched system voice holds the internal control",
          reading["internal_control_system_voice"]["verdict"] == "CONTROL_HOLDS")
    check("a clean strip is readable", reading["refusal_state"]["verdict"] == "READABLE")
    noisy = strip_readings(clean, {"confabulated_per_unit": 2.0})
    check("confabulation at half the drop voids the reading",
          noisy["refusal_state"]["verdict"] == "VOID")
    flat = strip_readings([_pair(1, 1, 1.0) for _ in range(6)], {"confabulated_per_unit": 0.0})
    check("a strip that ties its placebo on every pair decides nothing, and says so",
          flat["against_placebo"]["verdict"] == "INSUFFICIENT_N")
    check("and the tie publishes an interval of zero rather than a silence",
          flat["against_placebo"]["equivalence_bound"]["lo"] == 0.0
          and flat["against_placebo"]["equivalence_bound"]["hi"] == 0.0)
    backwards = strip_readings(
        [_pair(1, 4, 1.0) for _ in range(6)], {"confabulated_per_unit": 0.0}
    )
    check("a placebo that removes more than the strip reads DOES_NOT_SEE",
          backwards["against_placebo"]["verdict"] == "DOES_NOT_SEE")
    sunk = strip_readings(
        [_pair(4, 0, 1.0, sv_before=2, sv_after=0) for _ in range(6)],
        {"confabulated_per_unit": 0.1},
    )
    check("a system voice that fell with the prose fails the internal control",
          sunk["internal_control_system_voice"]["verdict"] == "CONTROL_FAILS")
    nospans = strip_readings(
        [_pair(4, 0, 1.0, spans=0) for _ in range(6)], {"confabulated_per_unit": 0.1}
    )
    check("no protected span means the control is EMPTY, not a pass",
          nospans["internal_control_system_voice"]["verdict"] == "EMPTY")
    wobble = strip_readings(
        [_pair(4, 0, 1.0, sv_before=2, sv_after=1), *[_pair(4, 0, 1.0) for _ in range(5)]],
        {"confabulated_per_unit": 0.1},
    )
    check("one system-voice beat lost is undecided rather than held or failed",
          wobble["internal_control_system_voice"]["verdict"] == "CONTROL_UNDECIDED")
    check("no certified pair means the refusal state does not apply",
          strip_readings([], {})["refusal_state"]["verdict"] == "NOT_APPLICABLE")
    check("no repeat arm means the noise-floor reading says so, not a verdict",
          strip_readings([_pair(4, 0, None) for _ in range(6)],
                         {"confabulated_per_unit": 0.1})["against_noise_floor"]["verdict"]
          == "NOT_RUN")

    # -- the freeze
    computed = registration_digest()
    check(f"the frozen block still digests to {FROZEN_DIGEST} (computed {computed})",
          computed == FROZEN_DIGEST)

    for message in failures:
        print(f"  FAIL {message}", file=sys.stderr)
    print(f"selftest: {'PASS' if not failures else str(len(failures)) + ' FAILURES'} "
          f"(registration digest {computed})", file=sys.stderr)
    return 1 if failures else 0


# ------------------------------------------------------------------------------------- main


ARMS = ("census", "repeat", "sham", "strip")
RUNNERS = {"census": run_census, "repeat": run_repeat, "sham": run_sham, "strip": run_strip}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--substrate", choices=("royalroad", "local", "report"))
    parser.add_argument("--arm", choices=ARMS, default="census")
    parser.add_argument("--dump", action="store_true",
                        help="MirrorBench interpreter only: write the census draw to derived/")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--price", type=int, default=0, metavar="N",
                        help="price the arm from N calls spread across the length range "
                             "and stop; writes a price file, never a census")
    parser.add_argument("--yes", action="store_true", help="required for a run that spends")
    parser.add_argument("--model", default=None,
                        help="the locator; defaults to elicit.PANEL_MODEL")
    parser.add_argument("--writer-model", default=None,
                        help="the strip arm's reviser; defaults to writer_states.WRITER_MODEL")
    parser.add_argument("--transport", default="cli", choices=("cli", "sdk", "ollama"))
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--cache", default=None, help="override the per-arm raw JSONL")
    parser.add_argument("--out", default=None, help="override the results JSON")
    parser.add_argument(
        "--library", default=str(REPO / "book-library" / "reappraisal" / "chapters")
    )
    parser.add_argument("--toll", default=str(REPO / "exports" / "the-toll-road.md"))
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.dump:
        return dump()
    if not args.substrate:
        parser.error("--substrate is required (royalroad, local, or report)")
    if selftest():
        print("refusing to run: the selftest failed", file=sys.stderr)
        return 1

    if args.substrate == "report":
        payload = run_report(args)
        out = Path(args.out) if args.out else RESULTS / (
            "comic-beats-report" + ("-dry" if args.dry_run else "") + ".json"
        )
        out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps(payload["reading"], indent=2))
        print(f"\nwrote {out}", file=sys.stderr)
        return 0

    if not args.dry_run and not args.yes:
        print("this run spends; pass --yes", file=sys.stderr)
        return 2

    if args.price:
        payload = run_price(args)
        out = Path(args.out) if args.out else RESULTS / (
            f"comic-beats-{args.substrate}-price{'-dry' if args.dry_run else ''}.json"
        )
        out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps({"fit": payload["fit"], "projection": payload["projection"],
                          "measured_usd": payload["spend"]["equivalent_usd"]}, indent=2))
        print(f"\nwrote {out}", file=sys.stderr)
        return 0

    from force_remote import AlreadyRunning, SingleRun

    lock = RESULTS / f".comic-beats-{args.substrate}-{args.arm}.pid"
    print(f"  results -> {result_path(args.substrate, args.arm, bool(args.dry_run)).name}",
          file=sys.stderr, flush=True)
    started = time.time()
    try:
        with SingleRun(lock, f"comic_beats {args.substrate}/{args.arm}"):
            payload = RUNNERS[args.arm](args)
    except AlreadyRunning as error:
        print(str(error), file=sys.stderr)
        return 3
    payload["seconds"] = round(time.time() - started, 1)

    out = Path(args.out) if args.out else result_path(
        args.substrate, args.arm, bool(args.dry_run)
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    render(payload)
    print(f"\nwrote {out}", file=sys.stderr)
    return 0


def render(payload: dict[str, Any]) -> None:
    """The lines a ledger entry would be written from. Transport failures first, per the runbook:
    read `transport_failures` before reading any number."""
    print(f"\narm {payload['arm']} on {payload['substrate']} "
          f"({payload['model'] or 'default'} via {payload['transport']}"
          f"{', DRY RUN' if payload['dry_run'] else ''})")
    print(f"  transport failures {payload.get('transport_failures')}  "
          f"{payload.get('failure_reasons') or ''}")
    print(f"  calls {payload.get('api_calls')}  replayed {payload.get('replayed')}  "
          f"equivalent ${(payload.get('spend') or {}).get('equivalent_usd')}")
    print(f"  hygiene {json.dumps(payload.get('hygiene'), sort_keys=True)}")
    if payload.get("summary"):
        print(f"  summary {json.dumps(payload['summary'], sort_keys=True)}")
    if payload.get("readings"):
        print(f"  readings {json.dumps(payload['readings'], indent=2, sort_keys=True)}")
    rows = payload.get("rows") or []
    counted = [row["density_per_1k"] for row in rows if not row["refused"]]
    if counted:
        print(f"  density/1k {json.dumps(describe([float(v) for v in counted]), sort_keys=True)}")


if __name__ == "__main__":
    raise SystemExit(main())
