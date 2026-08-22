"""A located census of the register a chapter reaches for, paragraph by paragraph, and the
shape of the sequence that makes. It scores nothing and admits nothing.

**Measurement only.** Nothing here feeds a prompt, a directive, a Director brief, a persona
reason code, a writer dossier or any generation path; nothing here admits an axis or a counter;
nothing under `src/` moves. It produces distributions and stops. Admission is an operator act
over a measured distribution (`plan/reader-read-2.md`), and this is the distribution.

**Two words that mean something else in this repository, fixed here before they mislead.**
*Valence* in stage-0 \u00a790\u2013\u00a797 means **reader preference** \u2014 would I keep
reading \u2014 the channel the Reader role owns and every verdict protocol died in. In this
module the word appears only inside `LEXICON`, where it means the ordinary
positive/negative polarity of a word, and it is never a preference. *Flat* in
`domain/axes.py` is `stat_flatten`, the digits in a status block. This module's `flatten` arm
is a rewrite of prose into plain statement and has nothing to do with either.

**Why a trajectory and not a level.** A density of "affect words" is the fourteenth proxy of the
shape `BRIEF.md` \u00a73 diagnoses \u2014 static, absolute, correlational \u2014 and a word list
is exactly that. The thing being measured is the *sequence*: which register, where, how often it
turns, and whether a pressure the text sets up is let go before the chapter ends. So the unit the
module reasons about is the ordered series of labels down a chapter, and **every statistic is a
deterministic function of that series** computed after the model has placed the labels. The model
locates; arithmetic does the rest. `trajectory` is that arithmetic and it is frozen beside the
prompt, because a statistic re-defined after the answers are in is a rubric fitted to them.

**Why a model locator is allowed here.** A model may not be asked for a *verdict* (\u00a789.4
puts position over text at 4,676-to-1 at the token a verdict is generated from) and may be asked
to **locate** (\u00a796.2: a part may locate, it may not prefer; \u00a797.4: the "why" is located,
not narrated). So the asking is *which register does this paragraph reach for*, never *does it
work*. The forbidden-vocabulary check in `--selftest` enforces that as a property of the rendered
asking rather than as an intention, and `emotion` is on the forbidden list on purpose: the word
invites the model to report what it imagines somebody undergoing, which \u00a797.4 forbids as
signal.

**There is no intensity slot and there must not be one.** A 1\u20135 rating is the
narrated-judgment channel this repository has measured drifting (\u00a794.5: a difference
confabulated between byte-identical texts). Amplitude here is emergent and deterministic \u2014 how
many words carry a non-`none` label, how long a run holds, how soon a release follows a set-up.

**What the echo is for.** The comic census's largest unmodelled variance was granularity: a run of
banter can be marked once or three times. Here the grid is fixed by the text (`ablate.paragraphs`)
and the model decides only the kind. Its one alignment check is deterministic: every entry carries
the paragraph's first four words copied exactly, and an entry whose echo does not match its
paragraph is a **misalignment** \u2014 dropped from the series, never padded over, and reported as
a rate on every arm.

**Four inherited lessons, not re-derived** (`comic-beats-results.md`): a one-draw locator over a
whole chapter is worth about 0.54 and needs four draws for 0.8, so `own` runs at K=4 up front; the
grid replaces free anchors; the layout sham is kept and expected to pass; and the primary reading
and the multiplicity policy are **named before the first call**, which the comic census had to
record as a declared defect.

**Familiarity is a named confound.** RoyalRoad may be memorised (BRIEF \u00a72 Pass 6); own
prose is the clean arm; the `flatten` differential on one unit partially cancels the term; the
two substrates are never pooled.

**Two interpreters, split by what the run reads.** The RoyalRoad shards are parquet and only
`C:/DEV/MirrorBench/.venv` reads them, so `--dump` runs there and writes a gitignored JSONL under
`derived/`; every arm then runs under `uv run python` reading that file. Committed results carry
ids and numbers only \u2014 a RoyalRoad label is stored by paragraph index with a hash of its echo
and never as a quoted string; our own chapters store echoes verbatim, because we own that prose.
Module scope imports stdlib only and everything else lazily, which is what lets one implementation
serve both interpreters.

    AT=research/quality-measurement/affect_trajectory.py
    MB=C:/DEV/MirrorBench/.venv/Scripts/python.exe

    $MB $AT --dump                                        # the census draw, gitignored
    uv run python $AT --selftest                          # free, and it gates every run below
    uv run python $AT --substrate royalroad --arm census --dry-run
    uv run python $AT --substrate royalroad --arm census --price 10 --yes
    uv run python $AT --substrate royalroad --arm census  --yes
    uv run python $AT --substrate royalroad --arm repeat  --yes
    uv run python $AT --substrate royalroad --arm sham    --yes
    uv run python $AT --substrate royalroad --arm flatten --yes
    uv run python $AT --substrate local     --arm own     --yes
    uv run python $AT --substrate local     --arm sham    --yes
    uv run python $AT --substrate local     --arm flatten --yes
    uv run python $AT --substrate report                  # merges; spends nothing

One CLI arm at a time on this box (\u00a789.5: 390 transport failures from two `claude -p` jobs
beside each other), a dedicated `--cache` per arm, and a PID lock so a second launch refuses.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import math
import random
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
#: both the ignore and the absence of tracked files). Everything carrying third-party prose or a
#: derived work of it lives here: the chapter dump, the RoyalRoad raw caches, and **every**
#: revision this module generates on either substrate.
DERIVED = HERE / "derived"


# ============================================================================ the instrument
#
# Everything between this banner and the next is **byte-frozen at the first paid call** and
# covered by `registration_digest()`, which `--selftest` compares against `FROZEN_DIGEST`.
# `llm-reader-engagement.md` \u00a7A1's rule: T0's A4 put about fourteen points of a verdict on
# wording, so a reworded prompt is a different instrument with no evidence behind it. The
# trajectory statistics are inside the freeze too, because a statistic re-defined after the
# answers are in is a rubric fitted to them.

#: The closed set. Closed because an open set cannot be falsified (`personas.py`'s reason-code
#: argument). Ten including `none`, which is the handoff's ceiling. Extending it after the first
#: paid call would mean the counts before and after were of different things, so `--selftest`
#: fails on any change.
KINDS: tuple[str, ...] = (
    "tension",
    "unease",
    "anticipation",
    "momentum",
    "relief",
    "triumph",
    "loss",
    "ease",
    "wonder",
    "none",
)

#: One line each, rendered into the system block in this order. Every definition describes the
#: **register the text reaches for** and never its effect on anybody. The handoff's draft said
#: `triumph` was "a win ... landing on the page"; "landing" is the verdict verb this repository
#: uses for whether a beat works, so it is "arriving" here and `land` is on the forbidden list.
#: That is the only departure from the handoff's table and it is the point of the instrument.
KIND_DEFINITIONS: dict[str, str] = {
    "tension": "a threat, deadline, risk or unknown being pressed, the outcome still open",
    "unease": "something off, wrong or foreboding, before any threat is named",
    "anticipation": "a reward, reveal, arrival or confrontation being promised as near",
    "momentum": "action or events arriving faster than they can be weighed",
    "relief": "a pressure set up earlier being let go, or a threat passing",
    "triumph": "a win, a gain, a level, a skill or a recognition arriving on the page",
    "loss": "a cost paid, a defeat, a death, a thing given up",
    "ease": "rest, care or lightness between characters or in the narration; the pressure is off",
    "wonder": "a thing of the world shown for its own strangeness or scale",
    "none": "the paragraph reaches for none of these: logistics, transition, plain statement",
}

#: The set-up kinds and the release kinds, named here because the pairing statistic is a claim
#: about *which* kinds pay off *which*, and a claim made in a function body is a claim nobody can
#: find. `loss` is deliberately not a release: a cost paid is not a pressure let go, and counting
#: it as one would make every downbeat chapter read as resolved.
SETUP_KINDS: tuple[str, ...] = ("tension", "unease", "anticipation")
RELEASE_KINDS: tuple[str, ...] = ("relief", "triumph")

#: How many words of a paragraph the model copies back so the entry can be matched to it. Four
#: is enough to be unique inside a chapter and short enough that copying it is not a task.
ECHO_WORDS = 4

#: How many of those words an entry must actually carry to be matchable, or the whole paragraph
#: when it is shorter than this. **Measured, not assumed** -- see `ECHO_DEFECTS_FOUND_AT_PRICING`.
#: Three tokens is the floor at which a prefix identifies one paragraph of a chapter rather than
#: a class of them; below it the entry is unverifiable and is dropped like any misalignment.
ECHO_MIN_TOKENS = 3

#: The three defects the pricing batch found in the first version of this contract, recorded
#: here because a rule that changed between a pre-registration and a run has to say when it
#: changed, why, and on what evidence. All three were found on **six pricing calls, before the
#: census**, which is what a pricing batch is for; none of them was found after reading a result.
#:
#: 1. **A quotation mark at the start of a paragraph broke the answer.** The first contract asked
#:    for the opening words "copied EXACTLY, character for character", so a paragraph beginning a
#:    line of dialogue produced an echo beginning with a double quote, which the model emitted
#:    unescaped: 1 of 6 answers was unparseable JSON at the first such paragraph. In this genre a
#:    paragraph opening on dialogue is ordinary, so this would have voided a large share of the
#:    census for a reason that has nothing to do with affect.
#: 2. **"The first four words" was scored as instruction-following, not as alignment.** On one
#:    chapter 86 of 93 echoes carried three words rather than four. Every one of them was a
#:    correct prefix of its own paragraph -- the entry identified its paragraph unambiguously --
#:    and the exact-four rule rejected all of them. Measured over the six pricing answers, the
#:    strict rule aligned about 30% of entries and the prefix rule below aligns **90.3%**, with
#:    the difference being entirely the model's word count and not its placement.
#: 3. **A short paragraph cannot carry four words.** Paragraphs of one to three words are common
#:    in this genre and the rule now asks for the whole of one.
#:
#: What did NOT change: an entry whose echo is not its paragraph's opening is still a
#: misalignment, still dropped from the series, and still reported as a rate on every arm. On the
#: same six answers 24 entries stay misaligned and 23 of them are one chapter where the model
#: read a different paragraph grid -- which is the failure the echo exists to catch, caught.
#: The second pricing batch, twelve calls under the fixed echo contract, found the defect that
#: the echo contract could not fix and that this instrument was designed around: **the model does
#: not hold a one-to-one correspondence with an unnumbered paragraph grid.** Measured over those
#: twelve chapters, the per-chapter misalignment rate ran the whole range from 0.00 to 1.00, and
#: the shapes were not one failure but three: entries that SKIP a paragraph and then run two
#: ahead of it for the rest of the chapter; entries whose echo is of no paragraph in the chapter
#: at all; and a 114-paragraph chapter answered with 144 entries. The count instruction was
#: followed and the correspondence was not, which is exactly the failure the echo was put there
#: to expose -- without it the census would have printed a hundred confident labels per chapter
#: and nobody would have known which paragraph any of them was about.
#:
#: The fix is to stop asking the model to keep count. The chapter is rendered with each paragraph
#: numbered, the model returns that number beside the kind, and the echo is then a CHECK on the
#: number rather than the only thing carrying the correspondence. The grid is still the text's,
#: the model still decides only the kind, and a label whose echo does not match the paragraph its
#: own number names is still a misalignment, dropped and counted.
#:
#: What this costs, stated rather than buried: the model now reads a marked-up document rather
#: than a chapter, and the `sham` arm's reflow of the paragraph SEPARATOR is normalised away by
#: the numbering render (the separator convention of the shown text is preserved, but the blocks
#: are rejoined). What survives the render is every intra-paragraph whitespace change, which is
#: the larger part of `rewhitespace`'s footprint, and `sham_grid_survives` still refuses any unit
#: whose grid moved.
#: The third pricing batch, twelve calls under the numbered grid, and what it left.
#:
#: The numbering worked on the thing it was for: **the length dependence is gone** -- Spearman of
#: per-chapter misalignment against paragraph count moved from +0.50 to -0.02 -- and no answer
#: was unparseable, where two of twelve had been. `bad_index`, `duplicate_index` and
#: `out_of_order` were all zero: every entry named a real paragraph, once, in order. What
#: remained was 204 misaligned entries of 763, and classifying them found two mechanics and no
#: third:
#:
#: 1. **68 echoes came back as one run-together word** and 15 came back empty, all inside two
#:    chapters that failed almost entirely (0.97 and 0.96). The asking said the echo was that
#:    paragraph's first four words "letters and numbers only", and the model read that as an
#:    instruction to drop the spaces as well. That is this instrument's wording, not the model's
#:    failure, and the asking now says "as words separated by single spaces, with the punctuation
#:    left out ... keep the spaces between them".
#: 2. **112 echoes were of no paragraph at all** and were a tokenisation artefact of the same
#:    instruction: told to leave punctuation out, the model wrote `dont` where the page has
#:    `don't`, and a tokeniser that split on the apostrophe compared `dont` against `don`, `t`
#:    and failed at the second token. Folding the apostrophe took ten of the twelve chapters to a
#:    median misalignment of **0.03**, and left the two run-together chapters exactly where they
#:    were -- which is what says the two mechanics are separate rather than one counted twice.
NUMBERED_GRID_THIRD_BATCH = (
    "2026-08-22, twelve calls under the numbered grid: the length dependence is gone (Spearman "
    "+0.50 to -0.02), no answer was unparseable, and every entry named a real paragraph once and "
    "in order. The 204 misaligned entries of 763 were two mechanics of one wording defect in this "
    "instrument: 'letters and numbers only' made the model drop the spaces between the words "
    "(two chapters lost almost entirely), and made it write `dont` where the page has `don't`, "
    "which a tokeniser splitting on the apostrophe scored as a mismatch (112 entries). The asking "
    "now asks for words separated by spaces and the tokeniser folds the apostrophe; on the same "
    "answers that takes ten of twelve chapters to a median misalignment of 0.03."
)

NUMBERED_GRID_FOUND_AT_PRICING = (
    "2026-08-22, on twelve pricing calls under the fixed echo contract and before the census: "
    "asked to return one entry per paragraph of an unnumbered chapter, the model returned the "
    "right COUNT and the wrong correspondence -- per-chapter misalignment ran 0.00 to 1.00, with "
    "entries skipping a paragraph and running two ahead of it, echoes of no paragraph in the "
    "chapter, and 144 entries for 114 paragraphs. The chapter is now rendered with numbered "
    "paragraphs and the model returns the number beside the kind; the echo checks the number "
    "instead of carrying the correspondence alone. Cost of the change: the model reads a "
    "marked-up document, and the sham's separator reflow is normalised away by the render."
)

ECHO_DEFECTS_FOUND_AT_PRICING = (
    "2026-08-22, on six pricing calls and before the census: an unescaped quote in a "
    "character-for-character echo made 1 of 6 answers unparseable; an exact-four-words rule "
    "rejected 3-word echoes that correctly identified their paragraphs, aligning 30% of entries "
    "where a token-prefix rule aligns 90.3%; and paragraphs shorter than four words cannot "
    "satisfy either. The echo is now the opening words with punctuation left out, matched as a "
    "token prefix at the entry's own index. A shifted entry is still a misalignment."
)

SYSTEM = (
    "You are marking up one chapter of a web serial.\n\n"
    "The chapter below is written as numbered paragraphs: each one begins with its own "
    "number in square brackets, like [7]. For EVERY numbered paragraph, in order, from "
    "the first to the last, record three things:\n\n"
    "  n      that paragraph's number, exactly as it is printed\n"
    "  kind   whichever one of these ten fits the register that paragraph reaches for\n"
    f"  echo   that paragraph's first {ECHO_WORDS} words after the number, as words "
    "separated by single spaces, with the punctuation left out: no quotation mark, dash, "
    "asterisk or bracket. Keep the words themselves whole and keep the spaces between "
    f"them. A paragraph shorter than {ECHO_WORDS} words gives all of it.\n\n"
    + "\n".join(f"    {name:14s}{KIND_DEFINITIONS[name]}" for name in KINDS)
    + "\n\nRules:\n"
    "  - Return exactly one entry per numbered paragraph, in order, including the ones you "
    "would otherwise pass over. The number of entries must equal the number of paragraphs.\n"
    "  - `n` is the number printed at the start of the paragraph. Do not renumber, do not "
    "skip a number, and do not use a number twice.\n"
    "  - The echo is checked against the paragraph `n` names, so it has to be that "
    "paragraph's own opening words in their own order. Do not paraphrase them and do "
    "not start part-way in.\n"
    "  - A paragraph that reaches for none of the ten is `none`. Most chapters carry many of "
    "them and a long run of `none` is an ordinary answer.\n"
    "  - Decide the kind from what is on the page, not from what anybody would undergo reading "
    "it. There is no scale here and nothing to rate: record which one, never how much.\n"
    "  - A [STATUS] block or a **bold** announcement is a paragraph like any other and takes its "
    "own entry.\n"
    "  - Return only the JSON object."
)

#: Rendered per call with the paragraph count of the chapter that call was shown. The count is in
#: the asking because the schema cannot express "as many entries as there are paragraphs", and a
#: list that is short by nine is a different failure from one that is misaligned by nine \u2014
#: both are counted separately and neither is padded.
QUESTION_TEMPLATE = (
    "The chapter is above, in {count} numbered paragraphs, [1] to [{count}]. Return one entry "
    "for each of them, in order, from [1] to [{count}]."
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "paragraphs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "n": {"type": "integer"},
                    "kind": {"type": "string", "enum": list(KINDS)},
                    "echo": {"type": "string"},
                },
                "required": ["n", "kind", "echo"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["paragraphs"],
    "additionalProperties": False,
}

#: Room for roughly two hundred paragraphs at an entry apiece. Inert on the `cli` transport,
#: which takes no max-tokens flag, and still in the request because it is in the cache key: a run
#: that later moves to the SDK must miss the cache rather than silently change instruments. A
#: truncated answer does not parse and is recorded as `unparseable`, never as a short series.
LABELS_MAX_TOKENS = 8000

#: The words the rendered asking may not contain, checked by `--selftest` over the system block,
#: the question template, the schema and the kind definitions. The handoff named the first
#: sixteen; `land`, `landing`, `intensity`, `strongly` and the rest are added because they are
#: the words a builder reaches for when adding the rating slot this design refuses.
FORBIDDEN_IN_ASKING: tuple[str, ...] = (
    "effective", "works", "gripping", "moving", "boring", "flat", "good", "better", "quality",
    "successful", "lands", "land", "landing", "reader", "readers", "feel", "feels", "feeling",
    "emotion", "emotional", "emotions", "mood", "intensity", "intense", "strongly", "powerful",
    "compelling", "engaging", "enjoy", "succeed", "impact", "funny", "humour", "humor",
)


# ------------------------------------------------- the trajectory, and the constants it needs

#: The word-windowed series' window, in words. Declared before the run and **not tuned**: the
#: paragraph sequence is the raw series and this is the same series read at a grain that does not
#: change when a writer breaks one paragraph into two. 200 words is about two paragraphs of this
#: genre (RoyalRoad LitRPG paragraphs run near 40 words), which is the coarsest grain at which a
#: turn is still a turn rather than a chapter summary.
TURN_WINDOW_WORDS = 200

#: How far back a set-up may sit and still be paired with a release, in words. 400 is two
#: windows, chosen before the run and frozen. It is not a claim about how far a pressure carries;
#: it is the one number a pairing statistic cannot avoid naming, and it is named before the data.
PAIRING_WINDOW_WORDS = 400

#: The tail whose register is reported as the chapter's end state, in words. Reported by cohort
#: with no bar. Naming a hook *shape* from it is \u00a7104.4's gated mining property and is out of
#: scope here \u2014 `chapter_endings.py`'s docstring records the same refusal.
END_STATE_WORDS = 150

#: Shuffles for the pairing null. The pairing rate of a chapter with no sequence at all: the same
#: multiset of paragraph labels in a permuted order, so anything the observed rate has above this
#: is a property of the *order* rather than of the mix. 1,000 is the smallest count at which the
#: null's own standard error is small beside the spread it is subtracted from.
PERMUTATIONS = 1000

#: Deciles for the position profile. Ten because a chapter of forty paragraphs gives four per
#: decile and a finer grid would report single paragraphs as a population.
POSITION_BINS = 10

#: The census window, in words, applied to **every** unit on every substrate. Not chosen here:
#: it is `comic_beats.MIN_CHAPTER_WORDS`/`MAX_CHAPTER_WORDS`, reused so the two censuses share a
#: population and any later cross-reading costs nothing. Over the 14,363 LitRPG chapters in the
#: two cached shards it keeps 92.9% of them.
MIN_CHAPTER_WORDS = 800
MAX_CHAPTER_WORDS = 6000

#: Chapters per cohort in the census draw, one chapter per story, by the same rule and the same
#: digest as the comic census, so `--dump` reproduces **the same chapters**. `dump` asserts the
#: drawn id set against `results/comic-beats-royalroad-census.json` and refuses on a mismatch.
PER_COHORT_TARGET = 100

#: Draws per unit on our own prose. Four, because the comic census measured a one-draw locator at
#: reliability 0.537 and computed that four independent draws are what reaches 0.8. This design
#: budgets them up front instead of discovering the noise afterwards. Scenes get two: they are
#: secondary colour at a grain a reader does not receive, and there are far more of them.
OWN_DRAWS = 4
OWN_SCENE_DRAWS = 2

#: The test-retest subset on RoyalRoad, and its second draw. Declared here rather than found:
#: the comic census used 40 and lost some to the transport, so this is 40 with the losses
#: expected and printed.
REPEAT_SUBSET = 40

#: The damage arm's subset: the top decile of the census by **coverage**, because a flatten arm
#: needs text that has something to flatten, plus every own chapter. Selecting on the outcome is
#: deliberate and is why the arm is read against a placebo rather than against the population.
FLATTEN_TOP_FRACTION = 0.10

#: Certification thresholds for the flatten arm, direction and unit stated where they are used.
#: `similarity` is `difflib` over word sequences, 1.0 byte-faithful; the floor is `comic_beats`'
#: 0.70 for the same reason \u2014 rewriting a reach into plain statement rewrites whole clauses.
#: `growth` is signed percent of the original word count and is two-sided, because a revision
#: that shortens the chapter has deleted sentences rather than rewritten them.
FLATTEN_MIN_SIMILARITY = 0.70
FLATTEN_MAX_GROWTH_PCT = 12.0

#: The paragraph grid must survive the revision or the two series are not comparable. A revision
#: that returns a different number of paragraphs certifies nothing and is excluded with its
#: reason named, exactly like a similarity failure.
FLATTEN_REQUIRE_SAME_GRID = True

#: The `cli` transport's own ceiling, in characters of rendered command line, and a property of
#: the platform rather than of the question: Windows `CreateProcess` refuses at 32,767 with
#: WinError 206 and `elicit._call_cli` passes the whole chapter as an argument. A unit over the
#: budget is excluded **before** the call, counted and printed, rather than sent and allowed to
#: fail \u2014 a transport error is indistinguishable in a log from a broken install, and
#: \u00a787.3's `NOT_SCREENABLE` lesson is that a unit the instrument could not reach is its own
#: state. The exclusion is length-correlated by construction and is named beside the length
#: residual it belongs to.
CLI_COMMAND_BUDGET = 32000

#: Alpha for every declared statistic in this module. One level, stated once.
ALPHA = 0.05

#: The smallest number of pairs at which a one-sided exact sign test can reach ALPHA at all: its
#: floor is 1/2**G, so G=5 gives 0.03125 and G=4 gives 0.0625. Below it the outcome is
#: INSUFFICIENT_N, a different outcome from a failure, and it is never converted into one.
MIN_PAIRS = 5

#: The two readings the `flatten` arm is judged by, in order, and the correction across them.
#: **Named before the first call.** The comic census's declared defect was that it named no
#: primary reading and no multiplicity policy and then had three readings to choose between;
#: this is that defect closed. Everything else in Q3 is descriptive and says so.
PRIMARY_READING = "coverage"
SECONDARY_READING = "turn_rate_windowed_per_1k"
MULTIPLICITY = "Holm across exactly two readings, primary then secondary, at alpha 0.05"

#: The band above which the model is declared redundant with the word list, chosen and frozen
#: before the run. Unitless Spearman on ranks, range [-1, 1], direction higher-is-more-redundant.
#: 0.60 is the level at which the two series share more than a third of their rank variance; it
#: is a threshold on the *instrument*, not a bar for admission of anything.
LEXICON_REDUNDANCY_BAND = 0.60


# ------------------------------------------------------------------- the incumbent word list

#: Where this list came from, printed in every result file. **Read it before reading any
#: redundancy number.**
#:
#: The handoff asked for a published valence/arousal norm set if one was on this machine under
#: the research corpora. Checked on 2026-08-22: there is none. `research/quality-measurement/
#: corpora/` holds `human-excerpts.json`, `taste-benchmark.json`, `toll-scenes.json`, `toll.db`
#: and the fitness databases and no norm set at all; no `nltk`, `vaderSentiment`, `textblob` or
#: `afinn` is installed in either interpreter; and nothing here fetches from the network, which
#: is not a substrate this directory uses. So this is the handoff's stated fallback — a
#: small in-module list — and the handoff also states which way that biases the reading:
#: **a weak list biases the redundancy check toward NOT_REDUNDANT, which is the flattering
#: direction for the model.** Any `NOT_REDUNDANT` outcome from this list is therefore the weakest
#: result this arm can produce and is reported as such; a `REDUNDANT_WITH_LEXICON` outcome from a
#: list this crude would be a strong result against the model.
LEXICON_PROVENANCE = (
    "in-module, assembled for this instrument from the register vocabulary of the genre; NOT a "
    "published or validated norm set. No norm set (ANEW, Warriner et al., NRC-VAD) is present on "
    "this machine under research/quality-measurement/corpora/, none of nltk, vaderSentiment, "
    "textblob or afinn is installed in either interpreter, and nothing here fetches from the "
    "network. A weak list biases the redundancy check toward NOT_REDUNDANT, which is the "
    "flattering direction for the model, so NOT_REDUNDANT is this arm's weakest outcome."
)

#: word -> (valence, arousal). Valence is ordinary positive/negative polarity in [-1, 1] —
#: **not** §90's reader preference — and arousal is activation in [0, 1]. Matching is
#: on a casefolded alphabetic token with a short suffix fold, so `screamed` finds `scream`.
LEXICON: dict[str, tuple[float, float]] = {
    # threat, pressure, alarm: negative and high
    "afraid": (-0.7, 0.8), "alarm": (-0.7, 0.9), "ambush": (-0.7, 0.9), "attack": (-0.6, 0.9),
    "blade": (-0.3, 0.7), "bleed": (-0.7, 0.8), "blood": (-0.5, 0.7), "burn": (-0.5, 0.8),
    "chase": (-0.3, 0.9), "claw": (-0.5, 0.8), "crack": (-0.4, 0.7), "crash": (-0.5, 0.8),
    "danger": (-0.8, 0.9), "dead": (-0.8, 0.6), "death": (-0.8, 0.7), "desperate": (-0.7, 0.9),
    "die": (-0.8, 0.8), "dread": (-0.8, 0.7), "enemy": (-0.6, 0.7), "explode": (-0.4, 0.9),
    "fear": (-0.8, 0.8), "fight": (-0.3, 0.9), "flee": (-0.5, 0.9), "frantic": (-0.6, 0.9),
    "fury": (-0.5, 0.9), "hunt": (-0.3, 0.8), "hurt": (-0.7, 0.7), "kill": (-0.7, 0.9),
    "knife": (-0.4, 0.7), "panic": (-0.8, 0.9), "pain": (-0.8, 0.7), "poison": (-0.7, 0.7),
    "rage": (-0.5, 0.9), "scream": (-0.6, 0.9), "shout": (-0.2, 0.8), "slam": (-0.3, 0.8),
    "snarl": (-0.5, 0.8), "stab": (-0.7, 0.9), "strike": (-0.2, 0.8), "terror": (-0.9, 0.9),
    "threat": (-0.7, 0.8), "trap": (-0.6, 0.8), "urgent": (-0.3, 0.9), "violent": (-0.7, 0.9),
    "war": (-0.6, 0.8), "wound": (-0.7, 0.7), "wrong": (-0.6, 0.5), "scramble": (-0.2, 0.8),
    "shatter": (-0.5, 0.8), "rush": (-0.1, 0.8), "sprint": (0.0, 0.9), "lunge": (-0.2, 0.9),
    "roar": (-0.2, 0.9), "howl": (-0.4, 0.8), "burst": (0.0, 0.8), "collapse": (-0.7, 0.7),
    # foreboding, wrongness: negative and low
    "ache": (-0.5, 0.4), "ash": (-0.4, 0.3), "bleak": (-0.6, 0.3), "cold": (-0.3, 0.3),
    "dark": (-0.4, 0.4), "dust": (-0.2, 0.2), "empty": (-0.5, 0.2), "grim": (-0.6, 0.4),
    "grey": (-0.2, 0.2), "hollow": (-0.5, 0.3), "quiet": (0.0, 0.1), "rot": (-0.7, 0.3),
    "shadow": (-0.4, 0.4), "silence": (-0.1, 0.2), "sick": (-0.7, 0.5), "stale": (-0.4, 0.2),
    "still": (0.0, 0.1), "strange": (-0.1, 0.5), "uneasy": (-0.6, 0.5), "wary": (-0.4, 0.5),
    "watchful": (-0.2, 0.5), "wrongness": (-0.6, 0.5), "creep": (-0.5, 0.5),
    "murmur": (-0.1, 0.3), "whisper": (-0.1, 0.4), "linger": (-0.1, 0.2), "shiver": (-0.4, 0.6),
    "prickle": (-0.3, 0.5), "unsettle": (-0.5, 0.5), "ominous": (-0.7, 0.6),
    # loss and cost: negative, mid-low
    "alone": (-0.6, 0.3), "betray": (-0.8, 0.7), "bury": (-0.6, 0.3), "cost": (-0.4, 0.4),
    "debt": (-0.5, 0.4), "defeat": (-0.8, 0.6), "fail": (-0.8, 0.5), "grief": (-0.9, 0.5),
    "lose": (-0.7, 0.5), "loss": (-0.8, 0.4), "mourn": (-0.8, 0.4), "regret": (-0.7, 0.4),
    "ruin": (-0.8, 0.5), "sacrifice": (-0.4, 0.6), "sorrow": (-0.8, 0.4),
    "surrender": (-0.5, 0.5), "grave": (-0.7, 0.4), "broken": (-0.7, 0.5),
    "ashamed": (-0.7, 0.5), "guilt": (-0.7, 0.5), "gone": (-0.5, 0.3), "never": (-0.3, 0.3),
    "farewell": (-0.4, 0.4), "funeral": (-0.7, 0.3),
    # win, gain, recognition: positive and high
    "ascend": (0.6, 0.7), "award": (0.7, 0.6), "beat": (0.4, 0.8), "breakthrough": (0.8, 0.8),
    "celebrate": (0.8, 0.8), "cheer": (0.8, 0.8), "conquer": (0.7, 0.8), "gain": (0.6, 0.6),
    "grin": (0.6, 0.6), "laugh": (0.7, 0.7), "level": (0.5, 0.6), "master": (0.6, 0.6),
    "prize": (0.7, 0.6), "reward": (0.8, 0.6), "rise": (0.5, 0.6), "succeed": (0.8, 0.7),
    "triumph": (0.9, 0.8), "unlock": (0.7, 0.7), "upgrade": (0.7, 0.6), "victory": (0.9, 0.8),
    "win": (0.8, 0.8), "achievement": (0.8, 0.7), "rank": (0.4, 0.5), "skill": (0.4, 0.5),
    "power": (0.5, 0.7), "strength": (0.5, 0.6), "prove": (0.6, 0.6), "earn": (0.6, 0.5),
    "praise": (0.8, 0.6), "applaud": (0.8, 0.7), "surge": (0.3, 0.8), "blaze": (0.2, 0.8),
    # promise, approach, expectation: mid valence and high arousal
    "almost": (0.0, 0.6), "await": (0.2, 0.6), "close": (0.1, 0.5), "coming": (0.1, 0.6),
    "countdown": (-0.1, 0.8), "eager": (0.6, 0.8), "edge": (-0.1, 0.7), "hope": (0.7, 0.6),
    "imminent": (-0.1, 0.8), "nearly": (0.0, 0.6), "promise": (0.6, 0.5), "soon": (0.1, 0.6),
    "tomorrow": (0.1, 0.4), "wait": (0.0, 0.5), "watch": (0.0, 0.5), "ready": (0.4, 0.7),
    "brace": (-0.2, 0.8), "gather": (0.1, 0.5), "approach": (0.0, 0.6),
    # release, rest, care: positive and low
    "breathe": (0.4, 0.3), "calm": (0.6, 0.2), "comfort": (0.8, 0.3), "ease": (0.7, 0.2),
    "gentle": (0.7, 0.2), "kind": (0.8, 0.3), "peace": (0.8, 0.2), "relax": (0.7, 0.2),
    "relief": (0.8, 0.4), "rest": (0.6, 0.2), "safe": (0.8, 0.3), "settle": (0.5, 0.2),
    "smile": (0.7, 0.4), "soft": (0.5, 0.2), "steady": (0.4, 0.3), "warm": (0.7, 0.3),
    "welcome": (0.8, 0.4), "friend": (0.8, 0.4), "home": (0.7, 0.3), "trust": (0.8, 0.4),
    "thank": (0.7, 0.4), "sleep": (0.4, 0.1), "quietly": (0.1, 0.2), "unclench": (0.5, 0.3),
    "loosen": (0.4, 0.3), "sag": (-0.1, 0.2), "slump": (-0.3, 0.2), "sigh": (0.0, 0.3),
    # scale, strangeness, awe: positive and mid-high
    "ancient": (0.2, 0.5), "awe": (0.7, 0.7), "beautiful": (0.9, 0.5), "endless": (0.2, 0.5),
    "enormous": (0.2, 0.6), "gleam": (0.5, 0.5), "glow": (0.5, 0.4), "immense": (0.2, 0.6),
    "impossible": (0.0, 0.7), "marvel": (0.8, 0.7), "shimmer": (0.5, 0.5), "sky": (0.3, 0.4),
    "star": (0.5, 0.4), "strangely": (0.0, 0.5), "vast": (0.2, 0.5), "wonder": (0.7, 0.6),
    "radiant": (0.7, 0.6), "towering": (0.1, 0.6), "silver": (0.3, 0.3), "golden": (0.5, 0.4),
    "crystal": (0.4, 0.4), "cathedral": (0.3, 0.4), "horizon": (0.3, 0.4),
    # everyday polarity that carries no register on its own but moves a paragraph mean
    "angry": (-0.6, 0.8), "annoyed": (-0.4, 0.5), "bitter": (-0.6, 0.5), "cruel": (-0.8, 0.6),
    "curse": (-0.5, 0.6), "disgust": (-0.7, 0.6), "hate": (-0.8, 0.7), "hostile": (-0.6, 0.6),
    "jealous": (-0.5, 0.6), "nasty": (-0.6, 0.5), "sneer": (-0.5, 0.5), "spite": (-0.6, 0.6),
    "delight": (0.9, 0.7), "glad": (0.7, 0.5), "happy": (0.9, 0.6), "joy": (0.9, 0.7),
    "love": (0.9, 0.6), "pleased": (0.7, 0.4), "proud": (0.7, 0.6), "relieved": (0.7, 0.4),
}

#: Below both of these a paragraph's lexicon label is `none`: the words that matched carry no
#: polarity and no activation worth naming. Frozen before the run with the rest of the block.
LEXICON_VALENCE_FLOOR = 0.20
LEXICON_AROUSAL_FLOOR = 0.45

#: The frozen mapping from (valence, arousal) onto a **coarsening** of the same closed set. Four
#: kinds of the nine, not because the word list is shy but because a word list cannot tell
#: `tension` from `momentum` or `triumph` from `wonder`, and pretending otherwise would flatter
#: it. Two set-up kinds and one release kind appear, which is what the pairing statistic needs to
#: be computable on both series. The coarsening is reported wherever a lexicon kind mix is.
LEXICON_COARSENING: dict[str, str] = {
    "negative_high": "tension",
    "negative_low": "unease",
    "positive_high": "triumph",
    "positive_low": "ease",
}


# ---------------------------------------------------------------------- the pre-registration

PRE_REGISTRATION: dict[str, Any] = {
    "written": (
        "2026-08-22, before the first paid call of any arm in this module, and byte-frozen "
        "with the system block, the question, the schema, the kinds, the word list and the "
        "trajectory statistics under FROZEN_DIGEST"
    ),
    "question": (
        "Where does a chapter reach for tension, relief, excitement and the rest; how often "
        "does that register turn; does a pressure the text sets up get released within the "
        "chapter -- in the genre's published chapters and in ours -- and can a located "
        "instrument see any of it at a reliability that makes the answer worth having? Q1 is "
        "the RoyalRoad LitRPG baseline by era cohort, Q2 is where our own chapters sit in it at "
        "K=4 draws each, Q3 is whether the locator is an instrument. Reported separately and in "
        "that order, and all three even if Q3 kills the instrument."
    ),
    "what_is_measured": (
        "The register a paragraph REACHES FOR, on a grid the text defines, and deterministic "
        "properties of the resulting sequence. It is not a quality, a craft claim, an effect or "
        "a success rate: a chapter that turns more often is not better, a chapter that is 80% "
        "`none` is not worse, and whether any of it moves anybody is not asked, not schema'd "
        "and not derivable from anything here. Whether a passage moves a reader is valence, "
        "valence is behavioural or it is nothing (S97.4), and this instrument has no valence "
        "channel."
    ),
    "unit_of_analysis": (
        "The chapter, as published -- the unit a reader receives. The paragraph is the grid "
        "inside it, never a unit of its own. `generated_scenes` units are scene grain, reported "
        "as secondary colour and NEVER pooled with chapters."
    ),
    "grid": (
        "`ablate.paragraphs` over the text THAT CALL WAS SHOWN, rendered back with each paragraph "
        "behind its own number and the shown text's own separator convention preserved. The model "
        "decides the kind; the text decides the positions and the numbering makes them sayable. "
        "One whole chapter per call: chunking changes the series, so a chapter outside the window "
        "is excluded and the exclusion is counted and printed. The numbering was added at the "
        "pricing stage and why is recorded in NUMBERED_GRID_FOUND_AT_PRICING; its cost is that "
        "the model reads a marked-up document rather than a chapter."
    ),
    "counting_rule": (
        "An entry is seated at the paragraph its own `n` names, and it counts only if its `echo` "
        "identifies THAT paragraph -- the paragraph's alphanumeric tokens, normalised (NFKC, "
        "punctuation folded then dropped, whitespace collapsed, casefolded), BEGIN with the "
        "echo's tokens, and the echo carries at least three of them or the whole of a paragraph "
        "shorter than three -- and only if its kind is one of the ten frozen kinds and no earlier "
        "entry has already taken that paragraph. Anything else is a MISALIGNMENT: the label is "
        "dropped from the series, its paragraph's words leave every denominator, and the rate is "
        "reported on every arm, split into `bad_index`, `duplicate_index`, `bad_kind` and the "
        "echo mismatches that are the rest. The number is the model's claim and the echo is the "
        "check on it: an entry whose echo is of some OTHER paragraph is a misalignment and is "
        "never searched for or re-seated, because the model having lost the correspondence is "
        "the failure this check exists to catch. `out_of_order` counts entries whose position in "
        "the returned list is not their own number, and is descriptive: a list returned out of "
        "order still seats every label correctly. Paragraphs no entry claimed are counted as "
        "`missing` and the series is NEVER padded."
    ),
    "no_post_hoc_leniency": (
        "The rule above is the counting rule and it was fixed BEFORE the census, on the six "
        "pricing calls, for the three measured defects recorded in "
        "ECHO_DEFECTS_FOUND_AT_PRICING -- not after reading a result. A deliberately STRICTER "
        "one -- the echo is exactly the paragraph's first four tokens -- is computed and "
        "reported as `echo_exactly_four` so the model's instruction-following is visible beside "
        "its placement, and it never enters a count. Loosening the rule after reading the "
        "answers would be a rubric fitted to them; the reported strict variant is what makes "
        "the difference between the two auditable rather than argued about."
    ),
    "no_intensity_slot": (
        "The model is never asked how much of a register a paragraph carries. A 1-5 rating is "
        "the narrated-judgment channel S94.5 measured drifting between byte-identical texts. "
        "Amplitude here is emergent and deterministic: words under a non-`none` label, run "
        "length, and how soon a release follows a set-up. If that proves too coarse the honest "
        "next step is a second closed label with its own validation, not a number the model "
        "makes up."
    ),
    "window": (
        f"[{MIN_CHAPTER_WORDS}, {MAX_CHAPTER_WORDS}] words, one whole chapter per call. Reused "
        "from `comic_beats.py` rather than chosen here, so the two censuses share a population; "
        "it keeps 92.9% of the 14,363 LitRPG chapters in the two cached shards."
    ),
    "transport_exclusion": (
        f"A unit whose rendered `claude -p` command line reaches {CLI_COMMAND_BUDGET} characters "
        "cannot be sent by this transport (Windows refuses at 32,767) and is excluded before the "
        "call, counted and printed. It is not sent and allowed to fail: a transport error is "
        "indistinguishable from a broken install. The exclusion is length-correlated by "
        "construction and is reported beside the length residual."
    ),
    "sampling": (
        f"{PER_COHORT_TARGET} chapters per era cohort, ONE CHAPTER PER STORY, chosen "
        "deterministically by digest -- the same rule, the same digest and therefore the same "
        "chapters as the comic-beat census, which `--dump` asserts against that census's "
        "committed id set and refuses on a mismatch. The substrate caps `declared_ai_2025` "
        "below the target and the cap is reported rather than filled by taking a second chapter "
        "from a story already in the pool."
    ),
    "substrates_are_never_pooled": (
        "RoyalRoad text may be memorised by the locator (BRIEF S2 Pass 6), so it is the baseline "
        "arm with the confound named; own-generated prose is the clean arm; the `flatten` "
        "differential on one unit partially cancels the term; and no statistic in this module "
        "averages the two."
    ),
    "statistics": {
        "coverage": (
            "share of ALIGNED words carrying a non-`none` label. Unitless, range [0, 1], no "
            "direction and no bar. Per-kind coverage beside it."
        ),
        "turn_rate": (
            "kind changes per 1,000 aligned words, computed twice: on the raw paragraph "
            f"sequence, and on a {TURN_WINDOW_WORDS}-word windowed series whose window was "
            "declared before the run and not tuned. A `none` to `none` pair is not a turn. "
            "Range [0, inf), no direction and no bar."
        ),
        "run_length": (
            "median aligned words per run of one kind, reported over all kinds and over "
            "non-`none` kinds. Words, range [1, inf), no direction and no bar."
        ),
        "pairing": (
            "a run of `relief` or `triumph` is PAIRED if a run of `tension`, `unease` or "
            f"`anticipation` ended within {PAIRING_WINDOW_WORDS} words before it began. "
            "`pairing_rate` = paired releases / releases; `unreleased_setup_share` = set-up runs "
            "with no release beginning within that window after them. Both unitless in [0, 1], "
            "both undefined and reported as null when the chapter has no release or no set-up. "
            f"The null is computed in the same pass: {PERMUTATIONS} within-chapter permutations "
            "of the paragraph labels with the multiset preserved, and the reading is OBSERVED "
            "MINUS NULL. This is the wave reading and it is a property of the sequence that a "
            "shuffled chapter does not have."
        ),
        "position_profile": (
            f"kind share by chapter decile of word position ({POSITION_BINS} bins). Averaged per "
            "cohort it is the population's mean wave. Unitless shares, no direction, no bar."
        ),
        "end_state": (
            f"the kind holding the most of the last {END_STATE_WORDS} aligned words. Reported by "
            "cohort with no bar. Naming a hook SHAPE from it is S104.4's gated mining property "
            "and is out of scope."
        ),
        "label_entropy": (
            "Shannon entropy in bits of the word-weighted kind distribution over aligned words. "
            f"Range [0, log2({len(KINDS)})], no direction and no bar."
        ),
        "system_voice": (
            "paragraphs carrying `axes._SYSTEM_LINE` or a bold announcement are flagged "
            "deterministically and EVERY statistic is reported with and without them. A [STATUS] "
            "block can itself be a `triumph` paragraph and the model is shown it, so the flag is "
            "a covariate and not an exclusion."
        ),
    },
    "arms": {
        "census": "RoyalRoad, one chapter per story, ONE draw. Q1 is read from this arm alone.",
        "own": (
            f"the published chapters at K={OWN_DRAWS} independent draws (distinct sample index, "
            "byte-identical request) so each placement carries its own interval, and "
            f"`generated_scenes` units at K={OWN_SCENE_DRAWS} as secondary colour. Q2 is read "
            "here and no per-chapter claim is made from a single draw anywhere."
        ),
        "repeat": (
            f"RoyalRoad, a digest-chosen subset of {REPEAT_SUBSET} chapters plus the flatten "
            "subset, a second byte-identical request at a distinct sample index. Reports Cohen's "
            "kappa per paragraph pair, the ICC of every trajectory statistic across draws, and "
            "the variance decomposition. This is the noise floor every other arm is read "
            "against. On `local` it does not run: the `own` arm already carries K=4 draws per "
            "unit and its within-unit spread IS the noise floor there."
        ),
        "sham": (
            "`ablate.rewhitespace` at full strength. Not one character of any word changes. The "
            "selftest asserts the paragraph count and every echo survive it, and a unit whose "
            "grid does not survive on the real text is excluded and counted. The statistics must "
            "not move beyond the `repeat` spread; if they do, the model is reading layout and "
            "the entry says so (S78)."
        ),
        "flatten": (
            "a certified minimal revision that rewrites every reach for these registers into "
            "plain statement of the same events -- order, point of view, typography, protected "
            "system spans, paragraph grid and length preserved -- with `flatten_placebo`, the "
            "same revision contract carrying an inert task, beside it. One dose; no ladder and "
            "no inject arm. Run on text that HAS coverage: the top decile of the census by "
            "coverage plus every own chapter."
        ),
        "lexicon": (
            "free, computed in the same pass on the same grid. Within-chapter Spearman between "
            "the model's windowed coverage series and the word list's arousal series, agreement "
            "on every trajectory statistic, and whether the word list sees the `flatten` drop as "
            "well as the model does."
        ),
        "era_table": (
            "every statistic by cohort, always. The control that killed `tricolon_rate` (BRIEF "
            "S2): if `human_pre_llm` and `declared_ai_2025` separate on a statistic more than "
            "`undeclared_2025` does from either, the statistic is reading the year."
        ),
    },
    "why_there_is_a_flatten_placebo": (
        "`repair_generation.PRE_REGISTRATION`'s first line makes it mandatory: no repair or "
        "damage arm is read except against its placebo. Without it a drop in coverage is equally "
        "well explained by the fact of a rewrite, and there is no way to tell the two apart "
        "afterwards. It is one more arm, not a dose ladder."
    ),
    "primary_reading_and_multiplicity": (
        f"PRIMARY: the `{PRIMARY_READING}` drop on `flatten` against `flatten_placebo`, paired "
        f"by unit, one-sided exact sign test. SECONDARY: the `{SECONDARY_READING}` drop, the "
        f"same way. {MULTIPLICITY}. Everything else in Q3 is descriptive and says so. Both are "
        "read against the `repeat` spread. NAMED HERE BEFORE THE FIRST CALL, because the comic "
        "census named neither and had to record that as a declared defect."
    ),
    "declared_quantities": {
        "misalignment_rate": (
            "misaligned entries / entries compared, unitless, range [0, 1], direction lower. "
            "Printed on every arm. REFUSAL STATE: if the median misalignment rate over the "
            "`flatten` subset is at least half the median coverage drop -- both unitless shares, "
            "so the comparison is in one unit -- the flatten reading is VOID rather than weak. "
            "An effect the instrument's own noise could manufacture is not an effect."
        ),
        "repeat_kappa": (
            "Cohen's kappa over the ten kinds between two draws on the same chapter's "
            "paragraphs, unitless, range [-1, 1], higher is more stable. No bar: it is the "
            "ruler. Attainable at any chapter with at least two aligned paragraphs in both "
            "draws; reported per unit and pooled over the subset."
        ),
        "statistic_icc": (
            "one-way random-effects ICC(1,1) of each trajectory statistic across draws, "
            "unitless, range [0, 1] after truncation at zero, higher is more reliable. Printed "
            "on every arm that has repeated draws, with the Spearman-Brown draws-to-0.8 beside "
            "it. A statistic whose ICC would need more than four draws for 0.8 has that stated "
            "as the cost of any per-chapter claim made from it."
        ),
        "sham_delta": (
            "|statistic(census) - statistic(sham)| per chapter, read against the same chapter's "
            "`repeat` spread by a one-sided exact sign test that the sham delta exceeds the "
            "repeat delta. Outcomes: LAYOUT_SENSITIVE at p <= alpha; INSIDE_NOISE only with the "
            "distribution-free 90% interval on the median difference printed beside it, never as "
            "a pass by silence (S101.1); INSUFFICIENT_N below the attainable floor."
        ),
        "flatten_drop": (
            "statistic(original) - statistic(flattened), paired by unit. Direction: positive for "
            "coverage and for turn rate. Read against the placebo's own drift by a one-sided "
            "exact sign test and against the noise floor by the share of pairs whose flatten "
            "drop exceeds that unit's repeat spread. Outcomes SEES / DOES_NOT_SEE / "
            "INSUFFICIENT_N / VOID."
        ),
        "lexicon_redundancy": (
            "median within-chapter Spearman between the model's windowed coverage series and the "
            f"word list's arousal series, unitless, range [-1, 1]. Above "
            f"{LEXICON_REDUNDANCY_BAND} AND with the word list seeing the flatten drop, the "
            "outcome is REDUNDANT_WITH_LEXICON and the word list ships instead of the model. "
            "Below it the outcome is NOT_REDUNDANT, which is the weakest result this arm can "
            "produce because the list is in-module rather than published (see "
            "LEXICON_PROVENANCE) and a weak list biases the reading that way."
        ),
    },
    "attainability": (
        "Declared at the n actually available, before the first call, per S87/S89's rulebook -- "
        "range, direction, independent unit and a non-empty subgroup for every quantity above. "
        "Every declared reading is an exact one-sided sign test whose smallest attainable p at G "
        f"pairs is 1/2**G, so alpha {ALPHA} is unreachable below G={MIN_PAIRS} and every G below "
        "that reports INSUFFICIENT_N rather than FAILS. The independent unit is the CHAPTER "
        "everywhere; the paragraph is a grid inside a chapter and is never treated as an "
        "independent draw. Non-emptiness: the `own` arm has 4 chapters at K=4, which is 4 "
        "independent units and NOT 16 -- every own-substrate reading below G=5 is "
        "INSUFFICIENT_N by construction and is declared so here rather than discovered later. "
        "The RoyalRoad flatten subset is the census top decile, which at a 245-chapter draw is "
        "about 24 units and is attainable."
    ),
    "no_inherited_figures": (
        "S79.1's rule. Every spread, rate and cost reported here is measured on these chapters "
        "by this instrument in these runs. The comic census's $68.99 is used only as an order of "
        "magnitude for what a refusal-worthy projection would exceed, never as a projection: the "
        "answer here is a label per paragraph, which is a longer output than a list of beats."
    ),
    "no_bar_for_admission": (
        "None is declared, and that is the point. Nothing here enters `AXES` or `COUNTERS`, "
        "reaches a prompt, a directive, a Director brief, a persona reason code or a writer "
        "dossier. Admission is an operator act over the measured distribution."
    ),
    "anti_scope": (
        "No arc archetypes and no clustering of the series into shapes -- that is selection "
        "among candidates with no containment (S61(5), S105.1) and would be read as a bar the "
        "moment it printed. No intensity or arousal rating from the model. No emotional-EFFECT "
        "measurement and no reader-sim self-report. No conversion arm: `results/conversion.json` "
        "records SEPARATION IS PROSE-BLIND, so no statistic here is correlated with that label. "
        "No chapter-hook-shape classification from the end state. No book-level arc on own prose. "
        "No inject arm, no dose ladder, no second model family at census grain, no RoyalRoad "
        "fetching. Nothing under `src/` moves and no ledger number is claimed."
    ),
}


# ------------------------------------------------------- the trajectory statistics, in-module
#
# Still inside the freeze. These are pure functions of `(labels, word_counts)` and nothing
# else: no text, no model, no arm. That is what makes them re-runnable over the committed
# result files for free, and what makes "the statistic was re-defined afterwards" a check
# rather than a promise.

#: A label of `None` is a paragraph whose entry misaligned. It breaks adjacency, leaves every
#: denominator, and is never filled in. Named so the three places that check for it agree.
GAP = None


def _aligned_spans(
    labels: list[str | None], words: list[int]
) -> list[tuple[int, str, int]]:
    """`(paragraph_index, kind, words)` for every aligned paragraph, in order."""
    return [
        (index, str(kind), int(count))
        for index, (kind, count) in enumerate(zip(labels, words, strict=True))
        if kind is not GAP
    ]


def _runs(labels: list[str | None], words: list[int]) -> list[dict[str, Any]]:
    """Maximal runs of one kind over *adjacent aligned* paragraphs.

    A gap ends a run rather than being spanned: two `tension` paragraphs either side of a
    misaligned one are two runs, not one, because the design has no evidence about what sat
    between them. `start_word` and `end_word` are cumulative word offsets over the whole
    chapter, so the pairing window is measured in the reader's words rather than in paragraphs.
    """
    runs: list[dict[str, Any]] = []
    offset = 0
    current: dict[str, Any] | None = None
    previous_index = -2
    for index, (kind, count) in enumerate(zip(labels, words, strict=True)):
        start = offset
        offset += count
        if kind is GAP:
            current = None
            continue
        if current is not None and current["kind"] == kind and previous_index == index - 1:
            current["end_word"] = offset
            current["words"] += count
            current["paragraphs"] += 1
        else:
            current = {
                "kind": str(kind),
                "start_word": start,
                "end_word": offset,
                "words": int(count),
                "paragraphs": 1,
            }
            runs.append(current)
        previous_index = index
    return runs


def _turns(labels: list[str | None]) -> int:
    """Kind changes between *adjacent aligned* paragraphs.

    A `none` to `none` pair is not a turn, which is true by construction since the kinds are
    equal; the pre-registration states it anyway because "excluded" could otherwise be read as
    "every pair touching `none` is excluded", and it is not: the register switching on and
    switching off are both turns.
    """
    changes = 0
    for index in range(len(labels) - 1):
        left, right = labels[index], labels[index + 1]
        if left is GAP or right is GAP:
            continue
        if left != right:
            changes += 1
    return changes


def windowed_series(
    labels: list[str | None], words: list[int], window: int = TURN_WINDOW_WORDS
) -> list[str | None]:
    """The same series read on a fixed word grid rather than on the writer's paragraphing.

    Each window takes the kind holding the most of its aligned words, ties broken by `KINDS`
    order so the function is a function. A window with no aligned words at all is a `GAP` and
    stays in its place: dropping it and then comparing its neighbours would count a turn across
    a hole the design has no evidence about, which is exactly what `_turns` refuses to do at
    paragraph grain. The series is always one entry per window, so anything else read on the
    same grid lines up with it index for index.
    """
    total = sum(words)
    if total <= 0 or window <= 0:
        return []
    series: list[str | None] = []
    for start in range(0, total, window):
        stop = min(start + window, total)
        weights: dict[str, int] = {}
        offset = 0
        for kind, count in zip(labels, words, strict=True):
            low, high = offset, offset + count
            offset = high
            if kind is GAP:
                continue
            overlap = min(high, stop) - max(low, start)
            if overlap > 0:
                weights[str(kind)] = weights.get(str(kind), 0) + overlap
        if not weights:
            series.append(GAP)
            continue
        series.append(max(weights, key=lambda kind: (weights[kind], -KINDS.index(kind))))
    return series


def _pairing(runs: list[dict[str, Any]], window: int = PAIRING_WINDOW_WORDS) -> dict[str, Any]:
    """Set-up to release pairing over one chapter's runs.

    A release is paired when a set-up run ENDED at most `window` words before it BEGAN, which
    includes the adjacent case (zero words between them). A set-up is unreleased when no release
    BEGINS within `window` words after it ends, chapter end included -- so a pressure set up in
    the last paragraph and never let go counts as unreleased rather than as unmeasurable.
    """
    setups = [run for run in runs if run["kind"] in SETUP_KINDS]
    releases = [run for run in runs if run["kind"] in RELEASE_KINDS]
    paired = 0
    for release in releases:
        if any(
            0 <= release["start_word"] - setup["end_word"] <= window
            for setup in setups
        ):
            paired += 1
    unreleased = 0
    for setup in setups:
        if not any(
            0 <= release["start_word"] - setup["end_word"] <= window
            for release in releases
        ):
            unreleased += 1
    return {
        "setup_runs": len(setups),
        "release_runs": len(releases),
        "paired_releases": paired,
        "pairing_rate": round(paired / len(releases), 4) if releases else None,
        "unreleased_setups": unreleased,
        "unreleased_setup_share": round(unreleased / len(setups), 4) if setups else None,
    }


def _permutation_null(
    labels: list[str | None], words: list[int], *, seed: str, shuffles: int = PERMUTATIONS
) -> dict[str, Any]:
    """What the pairing rates would be with the same labels in no particular order.

    The multiset of aligned labels is preserved and its ORDER is destroyed, `shuffles` times,
    seeded from the chapter so the null is a function of the chapter and not of the run. What
    the observed rate has above this is a property of the sequence; a chapter whose observed
    rate equals its null has a mix and not a wave. Gaps stay where they are: shuffling them
    would change how many words the denominators see.
    """
    positions = [index for index, kind in enumerate(labels) if kind is not GAP]
    pool = [labels[index] for index in positions]
    if len(pool) < 2:
        return {"shuffles": 0, "pairing_rate": None, "unreleased_setup_share": None}
    rng = random.Random(int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16], 16))
    pairing: list[float] = []
    unreleased: list[float] = []
    for _ in range(shuffles):
        shuffled = list(pool)
        rng.shuffle(shuffled)
        permuted: list[str | None] = list(labels)
        for slot, kind in zip(positions, shuffled, strict=True):
            permuted[slot] = kind
        stats = _pairing(_runs(permuted, words))
        if stats["pairing_rate"] is not None:
            pairing.append(float(stats["pairing_rate"]))
        if stats["unreleased_setup_share"] is not None:
            unreleased.append(float(stats["unreleased_setup_share"]))
    return {
        "shuffles": shuffles,
        "pairing_rate": round(statistics.fmean(pairing), 4) if pairing else None,
        "unreleased_setup_share": (
            round(statistics.fmean(unreleased), 4) if unreleased else None
        ),
    }


def _position_profile(
    labels: list[str | None], words: list[int], bins: int = POSITION_BINS
) -> list[dict[str, float]]:
    """Kind share by decile of word position, over aligned words only.

    A paragraph straddling a bin boundary contributes its words to both bins in proportion,
    which is why this walks the word axis rather than the paragraph index: a chapter of eleven
    paragraphs would otherwise put its deciles wherever its paragraph breaks happened to be.
    """
    total = sum(words)
    if total <= 0:
        return []
    edges = [round(index * total / bins) for index in range(bins + 1)]
    profile: list[dict[str, float]] = []
    for index in range(bins):
        start, stop = edges[index], edges[index + 1]
        weights: dict[str, int] = {}
        offset = 0
        for kind, count in zip(labels, words, strict=True):
            low, high = offset, offset + count
            offset = high
            if kind is GAP:
                continue
            overlap = min(high, stop) - max(low, start)
            if overlap > 0:
                weights[str(kind)] = weights.get(str(kind), 0) + overlap
        seen = sum(weights.values())
        profile.append(
            {kind: round(weights.get(kind, 0) / seen, 4) for kind in KINDS} if seen
            else dict.fromkeys(KINDS, 0.0)
        )
    return profile


def _end_state(
    labels: list[str | None], words: list[int], tail: int = END_STATE_WORDS
) -> str | None:
    """The kind holding the most of the last `tail` aligned words, or None if none is aligned."""
    total = sum(words)
    if total <= 0:
        return None
    start = max(0, total - tail)
    weights: dict[str, int] = {}
    offset = 0
    for kind, count in zip(labels, words, strict=True):
        low, high = offset, offset + count
        offset = high
        if kind is GAP:
            continue
        overlap = min(high, total) - max(low, start)
        if overlap > 0:
            weights[str(kind)] = weights.get(str(kind), 0) + overlap
    if not weights:
        return None
    return max(weights, key=lambda kind: (weights[kind], -KINDS.index(kind)))


def _entropy(weights: dict[str, int]) -> float:
    """Shannon entropy of a word-weighted kind distribution, in bits."""
    total = sum(weights.values())
    if total <= 0:
        return 0.0
    return round(
        -sum(
            (count / total) * math.log2(count / total)
            for count in weights.values()
            if count > 0
        ),
        4,
    )


def trajectory(labels: list[str | None], words: list[int]) -> dict[str, Any]:
    """Every statistic this module reports about one series. Pure, frozen, and the whole point.

    `labels` and `words` are the same length: one entry per paragraph of the grid, with `None`
    where the entry misaligned. Aligned words are the denominator everywhere, so two chapters
    with different misalignment rates are still comparable on rates -- and the rate itself is
    printed beside them so a chapter carried by four aligned paragraphs cannot look like one
    carried by forty.
    """
    spans = _aligned_spans(labels, words)
    aligned_words = sum(count for _, _, count in spans)
    by_kind: dict[str, int] = dict.fromkeys(KINDS, 0)
    for _, kind, count in spans:
        by_kind[kind] = by_kind.get(kind, 0) + count
    non_none = aligned_words - by_kind.get("none", 0)
    runs = _runs(labels, words)
    non_none_runs = [run for run in runs if run["kind"] != "none"]
    windowed = windowed_series(labels, words)
    windowed_turns = sum(
        1 for index in range(len(windowed) - 1)
        if windowed[index] is not GAP and windowed[index + 1] is not GAP
        and windowed[index] != windowed[index + 1]
    )
    per_1k = 1000.0 / aligned_words if aligned_words else 0.0
    return {
        "paragraphs": len(labels),
        "paragraphs_aligned": len(spans),
        "words_total": sum(words),
        "words_aligned": aligned_words,
        "aligned_word_share": round(aligned_words / sum(words), 4) if sum(words) else None,
        "coverage": round(non_none / aligned_words, 4) if aligned_words else None,
        "coverage_by_kind": {
            kind: round(by_kind.get(kind, 0) / aligned_words, 4) if aligned_words else None
            for kind in KINDS
        },
        "turn_rate_paragraph_per_1k": round(_turns(labels) * per_1k, 4) if aligned_words
        else None,
        "turns_paragraph": _turns(labels),
        "turn_rate_windowed_per_1k": round(windowed_turns * per_1k, 4) if aligned_words
        else None,
        "turns_windowed": windowed_turns,
        "windows": len(windowed),
        "windows_aligned": sum(1 for kind in windowed if kind is not GAP),
        "runs": len(runs),
        "run_length_median_words": (
            round(statistics.median([run["words"] for run in runs]), 4) if runs else None
        ),
        "run_length_median_words_non_none": (
            round(statistics.median([run["words"] for run in non_none_runs]), 4)
            if non_none_runs else None
        ),
        "pairing": _pairing(runs),
        "position_profile": _position_profile(labels, words),
        "end_state": _end_state(labels, words),
        "label_entropy_bits": _entropy(by_kind),
    }


#: The statistics a paired reading, an ICC or a cohort table may be computed over: scalars, in
#: one unit each, and nothing whose "difference" would be undefined. `pairing_rate` and
#: `unreleased_setup_share` are lifted out of the nested `pairing` block by `scalars`.
SCALAR_STATISTICS: tuple[str, ...] = (
    "coverage",
    "turn_rate_paragraph_per_1k",
    "turn_rate_windowed_per_1k",
    "run_length_median_words",
    "run_length_median_words_non_none",
    "label_entropy_bits",
    "pairing_rate",
    "unreleased_setup_share",
    "pairing_rate_minus_null",
    "unreleased_setup_share_minus_null",
)


def scalars(stats: dict[str, Any], null: dict[str, Any] | None = None) -> dict[str, float | None]:
    """One series' scalar statistics, flattened, with the permutation contrasts folded in.

    The two `_minus_null` entries are the wave reading: a chapter whose observed pairing equals
    its own shuffled null has a mix of registers and not a sequence of them, and the difference
    is the only form of the pairing statistic that a chapter's own label mix cannot manufacture.
    """
    pairing = stats.get("pairing") or {}
    out: dict[str, float | None] = {}
    for name in SCALAR_STATISTICS:
        if name in ("pairing_rate", "unreleased_setup_share"):
            value = pairing.get(name)
        elif name.endswith("_minus_null"):
            base = name[: -len("_minus_null")]
            observed = pairing.get(base)
            expected = (null or {}).get(base)
            value = (
                round(float(observed) - float(expected), 4)
                if observed is not None and expected is not None else None
            )
        else:
            value = stats.get(name)
        out[name] = float(value) if isinstance(value, int | float) else None
    return out


# ---------------------------------------------------------------- the flatten arm's contract

#: An author revising his own pages, which is generation rather than the critique frame S1a.2
#: exists to avoid. Copied in shape from `repair_generation.REVISER_SYSTEM` at chapter grain,
#: which is where `comic_beats.STRIP_SYSTEM` took it from.
FLATTEN_SYSTEM = (
    "You are the author of the chapter below, midway through drafting a serialized web novel, "
    "returning tonight to revise your own pages."
)

#: Shared verbatim across the flatten arm and its placebo; the task block is the single moving
#: part. The paragraph and system-voice contract is `repair_generation.REVISION_RULES`', with the
#: paragraph clause load-bearing here rather than decorative: this instrument's grid IS the
#: paragraphs, so a revision that re-broke them would produce a series that could not be paired
#: with the original at all. `certify` enforces it and refuses the pair when it moves.
FLATTEN_RULES = """\
Revise the chapter below, changing as little as possible. Keep every plot fact, the same events
in the same order, the same point of view, and THE SAME PARAGRAPH BREAKS -- the revision must
have exactly as many paragraphs as the original, in the same order. Any line in the system voice
-- **bold** announcements and [STATUS] blocks -- is copied byte-for-byte, unchanged, where it
stood. Do not shorten the chapter and do not pad it.
Return only the revised chapter text: no title, no preamble, no commentary.

Tonight's revision has one purpose:
{task}"""

#: The task is written in the same located vocabulary the kinds are defined in and deliberately
#: does not name the kind labels. Describing the target in *other* terms would remove something
#: other than what the census counts; naming the labels would make this a keyword hunt fitted to
#: its own scorer. `momentum` and `wonder` are described rather than named for the same reason.
#:
#: Protected spans are copied byte-for-byte by the contract above, so a [STATUS] block the model
#: marked `triumph` **cannot** be flattened -- which turns the system-voice paragraphs into this
#: arm's own internal control: prose paragraphs must lose coverage and system-voice paragraphs
#: must not. A run where both fall is a locator responding to the fact of a rewrite.
FLATTEN_TASKS: dict[str, str] = {
    "flatten": (
        "Wherever the writing presses a threat, a deadline or an open outcome; holds something "
        "as off or foreboding; promises a reward, a reveal or a confrontation as near; runs "
        "events faster than they can be weighed; lets an earlier pressure go; puts a win, a "
        "gain or a cost on the page; rests between characters; or shows a thing of the world "
        "for its strangeness or its scale -- rewrite those sentences so that they state the "
        "same events plainly and directly, at about the same length, reaching for none of that. "
        "A sentence that already states its events plainly is left exactly as it is."
    ),
    "flatten_placebo": (
        "Correct any spelling or typographical errors you find. A sentence that contains none "
        "is left exactly as it is. There may be nothing to correct, in which case the chapter "
        "comes back unchanged."
    ),
}


# ------------------------------------------------------ the lexicon series, on the same grid

_WORD = re.compile(r"[a-z]+")

#: Suffixes stripped, longest first, when a token misses the list. Deliberately crude: this is
#: the incumbent and dressing it up would make the comparison a comparison with something else.
_SUFFIXES = ("ingly", "edly", "ing", "ies", "ied", "es", "ed", "ly", "s")


def lexicon_value(paragraph: str) -> dict[str, Any]:
    """One paragraph's mean valence and arousal from `LEXICON`, and how many words carried them.

    `matched` is reported because a mean over one word and a mean over nine are different
    quantities, and a word list whose coverage is two per cent is answering a different question
    from the model it is being compared with.
    """
    values: list[tuple[float, float]] = []
    for token in _WORD.findall(paragraph.casefold()):
        entry = LEXICON.get(token)
        if entry is None:
            for suffix in _SUFFIXES:
                if token.endswith(suffix) and len(token) > len(suffix) + 2:
                    entry = LEXICON.get(token[: -len(suffix)])
                    if entry is not None:
                        break
        if entry is not None:
            values.append(entry)
    if not values:
        return {"matched": 0, "valence": 0.0, "arousal": 0.0}
    return {
        "matched": len(values),
        "valence": round(statistics.fmean(value for value, _ in values), 4),
        "arousal": round(statistics.fmean(arousal for _, arousal in values), 4),
    }


def lexicon_kind(value: dict[str, Any]) -> str:
    """The frozen coarsening of (valence, arousal) onto four of the ten kinds, or `none`.

    The rule is a rule and not a fit: it was written before any answer existed and it is inside
    the digest. It cannot produce `anticipation`, `momentum`, `relief`, `loss` or `wonder`, and
    that limit is the honest shape of what a word list knows -- reported wherever a lexicon kind
    mix is printed rather than hidden by mapping everything onto something.
    """
    if not value["matched"]:
        return "none"
    valence = float(value["valence"])
    arousal = float(value["arousal"])
    if abs(valence) < LEXICON_VALENCE_FLOOR and arousal < LEXICON_AROUSAL_FLOOR:
        return "none"
    polarity = "negative" if valence < 0 else "positive"
    activation = "high" if arousal >= LEXICON_AROUSAL_FLOOR else "low"
    return LEXICON_COARSENING[f"{polarity}_{activation}"]


def lexicon_series(grid: list[str]) -> dict[str, Any]:
    """The word list's whole answer for one chapter: per-paragraph values and its label series.

    Costs nothing, has zero test-retest noise, and is the thing the model has to be shown to
    beat. Every statistic below it is computed by the SAME `trajectory` function the model's
    series goes through, so a difference between the two is a difference between the series and
    not between two implementations of a mean.
    """
    values = [lexicon_value(paragraph) for paragraph in grid]
    labels: list[str | None] = [lexicon_kind(value) for value in values]
    words = [len(paragraph.split()) for paragraph in grid]
    stats = trajectory(labels, words)
    return {
        "provenance": LEXICON_PROVENANCE,
        "entries": len(LEXICON),
        "labels": [str(label) for label in labels],
        "valence": [value["valence"] for value in values],
        "arousal": [value["arousal"] for value in values],
        "matched": [value["matched"] for value in values],
        "match_rate": round(
            sum(value["matched"] for value in values) / max(sum(words), 1), 4
        ),
        "trajectory": stats,
    }


# =========================================================================== end of the freeze


def digest(payload: object) -> str:
    """Stable digest of a payload. Sorted keys so dict order is never in the key.

    Restated from `elicit.digest` rather than imported, for `comic_beats.digest`'s reason:
    `--dump` runs under the MirrorBench interpreter, which does not have this repository
    installed and cannot import `elicit` (it reaches `personas`). The implementation is
    byte-identical on purpose -- a chapter id picked by this function on one interpreter has to
    be the same chapter on the other, and it has to be the same chapter the comic census drew.
    """
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:20]


#: The functions whose SOURCE is inside the freeze, not merely whose constants are. The handoff
#: asked for the trajectory statistics to be frozen under the same digest as the prompt, and
#: freezing the window sizes alone would not do it: a `coverage` that counted paragraphs before
#: the run and words after it is two numbers wearing one name, and no constant would have moved.
#: The cost is deliberate and is stated so nobody is surprised by it -- reformatting one of these
#: functions, or editing a comment inside one, changes the digest and every arm then refuses the
#: result files written before the edit. That is the intended behaviour: it is the same
#: instrument or it is a different one.
FROZEN_FUNCTIONS = (
    "normalise", "echo_tokens", "echo_matches", "echo_is_exactly_four", "align",
    "numbered", "render_turn",
    "_aligned_spans", "_runs", "_turns", "windowed_series", "_pairing", "_permutation_null",
    "_position_profile", "_end_state", "_entropy", "trajectory", "scalars",
    "lexicon_value", "lexicon_kind", "lexicon_series",
)


#: Computed once, on the first call, and held. **This cache is not an optimisation.**
#: `inspect.getsource` re-reads the file from disk every time, so an edit to this module while a
#: run is in flight would change the digest under the run and, if the file were mid-write, crash
#: it in `tokenize`. That happened once, at the pricing stage, and cost the write of a batch
#: whose calls had all returned. A run now holds the digest it started with.
_STATISTICS_SOURCE_DIGEST: str | None = None


def statistics_source_digest() -> str:
    """Content address of the frozen functions' source text, module order preserved."""
    global _STATISTICS_SOURCE_DIGEST
    if _STATISTICS_SOURCE_DIGEST is None:
        import inspect

        module = sys.modules[__name__]
        _STATISTICS_SOURCE_DIGEST = digest([
            inspect.getsource(getattr(module, name)) for name in FROZEN_FUNCTIONS
        ])
    return _STATISTICS_SOURCE_DIGEST


def registration_digest() -> str:
    """Content address of everything inside the freeze banner, prompt and arithmetic alike.

    Printed on every artifact. A result file whose digest differs from the module's came from a
    different instrument, and the check is one comparison rather than a diff of prose. The
    statistics are in the digest because a coverage computed one way before the run and another
    way after it is two numbers wearing one name.
    """
    return digest(
        {
            "pre_registration": PRE_REGISTRATION,
            "kinds": list(KINDS),
            "kind_definitions": KIND_DEFINITIONS,
            "setup_kinds": list(SETUP_KINDS),
            "release_kinds": list(RELEASE_KINDS),
            "system": SYSTEM,
            "question_template": QUESTION_TEMPLATE,
            "schema": SCHEMA,
            "max_tokens": LABELS_MAX_TOKENS,
            "echo_words": ECHO_WORDS,
            "echo_min_tokens": ECHO_MIN_TOKENS,
            "echo_defects_found_at_pricing": ECHO_DEFECTS_FOUND_AT_PRICING,
            "numbered_grid_found_at_pricing": NUMBERED_GRID_FOUND_AT_PRICING,
            "numbered_grid_third_batch": NUMBERED_GRID_THIRD_BATCH,
            "forbidden": list(FORBIDDEN_IN_ASKING),
            "statistics": [
                TURN_WINDOW_WORDS, PAIRING_WINDOW_WORDS, END_STATE_WORDS, PERMUTATIONS,
                POSITION_BINS, list(SCALAR_STATISTICS),
            ],
            "statistics_source": statistics_source_digest(),
            "lexicon": sorted(LEXICON.items()),
            "lexicon_floors": [LEXICON_VALENCE_FLOOR, LEXICON_AROUSAL_FLOOR],
            "lexicon_coarsening": LEXICON_COARSENING,
            "lexicon_redundancy_band": LEXICON_REDUNDANCY_BAND,
            "flatten_system": FLATTEN_SYSTEM,
            "flatten_rules": FLATTEN_RULES,
            "flatten_tasks": FLATTEN_TASKS,
            "window": [MIN_CHAPTER_WORDS, MAX_CHAPTER_WORDS],
            "sampling": [PER_COHORT_TARGET, OWN_DRAWS, OWN_SCENE_DRAWS, REPEAT_SUBSET,
                         FLATTEN_TOP_FRACTION],
            "certification": [FLATTEN_MIN_SIMILARITY, FLATTEN_MAX_GROWTH_PCT,
                              FLATTEN_REQUIRE_SAME_GRID],
            "readings": [PRIMARY_READING, SECONDARY_READING, MULTIPLICITY],
            "alpha": ALPHA,
            "min_pairs": MIN_PAIRS,
        }
    )


#: The digest as it stood when the first paid call was made. `--selftest` fails on divergence,
#: which is the whole mechanism: a reworded prompt or a re-defined statistic is a different
#: instrument, and every number in `affect-trajectory-results.md` is attributable to this exact
#: content or it is attributable to nothing.
FROZEN_DIGEST = "6bf5297e4ea3a7016e0a"


# ------------------------------------------------------------------------- the echo alignment

#: Characters a model retypes rather than copies. Folded on BOTH sides of the comparison, so the
#: check forgives a straightened quote and forgives nothing else. Written as escapes because
#: ruff's RUF rules reject literal curly quotes in Python source, which is why `ablate._EM` names
#: its glyph instead of inlining it.
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


def normalise(text: str) -> str:
    """The counting rule's normalisation: NFKC, folded punctuation, collapsed whitespace, cased.

    Whitespace collapse is what makes the `sham` arm scoreable at all -- `rewhitespace` changes
    only whitespace, so an echo that matches in the reflowed text matches in the original by the
    same rule and the two arms' series are comparable rather than incidentally different.
    """
    folded = unicodedata.normalize("NFKC", text).translate(_FOLD)
    return " ".join(folded.split()).casefold()


_TOKEN = re.compile(r"[0-9a-z]+")


def echo_tokens(text: str) -> list[str]:
    """The counting rule's tokens: alphanumeric runs of the normalised text, in order.

    Punctuation is dropped rather than forgiven. `normalise` already folds a retyped quote or
    dash to its ASCII cousin; this goes one step further and removes the mark, which is what
    makes the rule immune to the failure that broke 1 of 6 pricing answers -- a paragraph
    opening on dialogue produced an echo opening on a double quote and the model emitted it
    unescaped, so the whole answer was unparseable JSON. See `ECHO_DEFECTS_FOUND_AT_PRICING`.

    **The apostrophe is deleted before the split, not treated as a boundary**, so `don't` is one
    token and not two. That is a fix to this tokeniser and not a leniency toward the model: the
    rule says "the paragraph's opening words" and `don't` is one word. Splitting it made the
    paragraph's tokens `don`, `t` while the model, told to leave punctuation out, wrote `dont`,
    and the prefix comparison failed at the second token on every line of contracted dialogue.
    Measured on the third pricing batch: folding it took ten of twelve chapters from a median
    misalignment of 0.17 to 0.03, and changed no other verdict.
    """
    return _TOKEN.findall(normalise(text).replace("'", ""))


def echo_matches(paragraph: str, echo: str) -> bool:
    """Whether an entry's echo identifies this paragraph: a token prefix of its opening.

    A PREFIX and not an equality, because "the first four words" turned out to be a test of
    counting to four rather than of alignment: on one pricing chapter 86 of 93 echoes carried
    three words, every one of them the correct opening of its own paragraph. The prefix has to
    carry `ECHO_MIN_TOKENS` tokens, or the whole paragraph when the paragraph is shorter than
    that -- a two-word paragraph cannot give four words and is not thereby unverifiable.

    An echo that identifies some OTHER paragraph is not matched here and never searched for.
    That is the failure this check exists to catch (the model read a different grid), and
    re-seating a label onto the paragraph its echo names would be a repair, not a measurement.
    """
    paragraph_tokens = echo_tokens(paragraph)
    candidate = echo_tokens(echo)
    need = min(ECHO_MIN_TOKENS, len(paragraph_tokens))
    if not candidate or len(candidate) < need:
        return False
    return paragraph_tokens[: len(candidate)] == candidate


def echo_is_exactly_four(paragraph: str, echo: str) -> bool:
    """The stricter rule, computed and reported and never counted. See `no_post_hoc_leniency`."""
    return echo_tokens(echo) == echo_tokens(paragraph)[:ECHO_WORDS]


def grid_of(text: str) -> list[str]:
    """The paragraph grid of the text THAT CALL WAS SHOWN.

    `ablate.paragraphs`, imported lazily so module scope stays stdlib-only and one implementation
    serves both interpreters. It adapts to which separator convention the source uses, which is
    the property that lets the sham arm reflow paragraph separators without inventing paragraphs
    -- and where it does not hold, `sham_grid_survives` catches it per unit rather than the
    series being silently re-cut.
    """
    from ablate import paragraphs

    return paragraphs(text)


def sham_grid_survives(original: str, reflowed: str) -> bool:
    """Whether a reflow left the grid alone: same paragraph count, same openings, in order."""
    left, right = grid_of(original), grid_of(reflowed)
    if len(left) != len(right):
        return False
    return all(
        echo_tokens(a)[:ECHO_WORDS] == echo_tokens(b)[:ECHO_WORDS]
        for a, b in zip(left, right, strict=True)
    )


def align(grid: list[str], payload: object) -> dict[str, Any]:
    """One call's answer turned into a label series, with the hygiene the series is read through.

    Every drop is a named category with a count beside it, because the failure this shape exists
    to avoid is a low coverage that is really a parse failure. The series is `labels`; `aligned`,
    `misaligned`, `extra`, `missing` and `bad_kind` are what the series is read through, and
    **nothing is padded**: a paragraph whose entry did not arrive or did not match stays `None`
    and leaves every denominator.
    """
    entries = payload.get("paragraphs") if isinstance(payload, dict) else None
    empty = {
        "unparseable": True,
        "labels": [None] * len(grid),
        "returned": 0, "compared": 0, "aligned": 0, "misaligned": 0,
        "extra": 0, "missing": len(grid), "bad_kind": 0, "bad_index": 0,
        "duplicate_index": 0, "out_of_order": 0, "echo_exactly_four": 0,
        "misalignment_rate": None,
        "echo_hashes": [None] * len(grid),
        "echoes": [None] * len(grid),
    }
    if not isinstance(entries, list):
        return empty
    labels: list[str | None] = [None] * len(grid)
    echoes: list[str | None] = [None] * len(grid)
    hashes: list[str | None] = [None] * len(grid)
    compared = len(entries)
    aligned = misaligned = bad_kind = bad_index = duplicate = exactly_four = out_of_order = 0
    for position, entry in enumerate(entries):
        if not isinstance(entry, dict):
            bad_kind += 1
            misaligned += 1
            continue
        kind = str(entry.get("kind") or "")
        echo = str(entry.get("echo") or "")
        raw = entry.get("n")
        index = int(raw) - 1 if isinstance(raw, int) and not isinstance(raw, bool) else -1
        if index != position:
            out_of_order += 1
        if not 0 <= index < len(grid):
            bad_index += 1
            misaligned += 1
            continue
        matched = echo_matches(grid[index], echo)
        if matched and echo_is_exactly_four(grid[index], echo):
            exactly_four += 1
        if kind not in KINDS:
            bad_kind += 1
            misaligned += 1
            continue
        if not matched:
            misaligned += 1
            continue
        if labels[index] is not None:
            duplicate += 1
            misaligned += 1
            continue
        labels[index] = kind
        echoes[index] = echo
        hashes[index] = hashlib.sha256(
            " ".join(echo_tokens(echo)).encode("utf-8")
        ).hexdigest()[:16]
        aligned += 1
    return {
        "unparseable": False,
        "labels": labels,
        "returned": len(entries),
        "compared": compared,
        "aligned": aligned,
        "misaligned": misaligned,
        "extra": max(0, len(entries) - len(grid)),
        "missing": sum(1 for label in labels if label is None),
        "bad_kind": bad_kind,
        "bad_index": bad_index,
        "duplicate_index": duplicate,
        "out_of_order": out_of_order,
        "echo_exactly_four": exactly_four,
        "misalignment_rate": round(misaligned / compared, 4) if compared else None,
        "echo_hashes": hashes,
        "echoes": echoes,
    }


def public_series(
    scored: dict[str, Any], grid: list[str], *, quote: bool
) -> list[dict[str, Any]]:
    """The committed form of one answer's series.

    `quote=False` is the RoyalRoad rule and it is not a courtesy: an echo there is four words of
    somebody else's novel and a public git history is exactly where that must never land
    (`corpus_leak_audit.py`'s whole subject). The paragraph index and a hash of the echo
    reproduce it from the pinned shard for anyone who has the shard and carry no expression for
    anyone who does not. `quote=True` is our own prose, where the series printed in full **is**
    the acceptance artifact.
    """
    return [
        {
            "i": index,
            "kind": scored["labels"][index],
            "words": len(grid[index].split()),
            "hash": scored["echo_hashes"][index],
            **({"echo": scored["echoes"][index]} if quote else {}),
        }
        for index in range(len(grid))
    ]


# ---------------------------------------------------------------------------- the arithmetic
#
# Restated in-module rather than imported from `comic_beats`, for the reason `corpus_io.
# era_cohort` restates `build_craft_profile.cohort_of`: two instruments each owning their own
# frozen arithmetic can disagree, and a disagreement is a finding, where a shared import would
# hide one. It also keeps the statistics inside this module's digest, which is the whole
# mechanism by which a number here is attributable to a particular instrument.


def one_sided_sign_p(k: int, n: int) -> float:
    """P(X >= k) for X ~ Bin(n, 1/2), enumerated rather than approximated.

    One-sided because every alternative here is directional and declared as such before the run:
    a sham that moves a statistic more than a re-ask does, a flatten that drops coverage further
    than its placebo does. S89's two-sided reasoning does not apply -- that was invariance under
    a sign flip of a *fitted* direction, and nothing here is fitted.
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

    S101.1's fix: a control that does not fire must publish what magnitude it could not exclude,
    or it is a pass by silence -- and a noisy instrument passes a null automatically. The
    interval is exact under the sign test and assumes nothing about the shape of the differences.
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
    counting it as evidence for the null is the shape S101.1 refuses. `pairs_undecided` prints
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


def holm(readings: list[tuple[str, float]], alpha: float = ALPHA) -> dict[str, Any]:
    """Holm-Bonferroni over the declared family, in the order it was declared.

    The family is exactly two -- `PRIMARY_READING` then `SECONDARY_READING` -- and it was named
    before the first call. The comic census's declared defect was that it named neither and then
    had three readings to pick from; this is that defect closed, and closing it means the
    correction applies whether or not it changes an outcome.
    """
    ordered = sorted(readings, key=lambda item: item[1])
    out: list[dict[str, Any]] = []
    still = True
    for rank, (name, p) in enumerate(ordered):
        threshold = alpha / (len(ordered) - rank)
        clears = still and p <= threshold
        still = clears
        out.append({
            "reading": name,
            "p_one_sided": round(p, 8),
            "holm_threshold": round(threshold, 8),
            "clears": clears,
        })
    return {
        "policy": MULTIPLICITY,
        "family_size": len(ordered),
        "steps": out,
        "any_clears": any(step["clears"] for step in out),
    }


def cohens_kappa(left: list[str | None], right: list[str | None]) -> float | None:
    """Agreement over the ten kinds between two draws on one chapter's paragraphs.

    Computed over paragraphs aligned in BOTH draws, which is the only place the two series are
    talking about the same thing. None when fewer than two such paragraphs exist, or when the
    expected agreement is 1 and kappa is undefined -- a chapter both draws called `none`
    throughout agrees perfectly and carries no information about agreement, and reporting 0.0
    for it would drag a pooled median toward a failure that did not happen.
    """
    pairs = [
        (a, b) for a, b in zip(left, right, strict=True) if a is not GAP and b is not GAP
    ]
    if len(pairs) < 2:
        return None
    total = len(pairs)
    observed = sum(1 for a, b in pairs if a == b) / total
    left_marginal: dict[str, int] = {}
    right_marginal: dict[str, int] = {}
    for a, b in pairs:
        left_marginal[str(a)] = left_marginal.get(str(a), 0) + 1
        right_marginal[str(b)] = right_marginal.get(str(b), 0) + 1
    expected = sum(
        (left_marginal.get(kind, 0) / total) * (right_marginal.get(kind, 0) / total)
        for kind in KINDS
    )
    if expected >= 1.0:
        return None
    return round((observed - expected) / (1.0 - expected), 4)


def icc(groups: list[list[float]]) -> dict[str, Any]:
    """One-way random-effects ICC(1,1) over units with repeated draws, and its cost in draws.

    The quantity a per-chapter claim needs and the quantity the comic census had to compute
    afterwards from a difference: how much of the spread across units is the units and how much
    is the instrument. `draws_to_0.8` is Spearman-Brown -- averaging k independent draws divides
    the noise variance by k -- and a statistic needing more than four is stated as the cost of
    any per-chapter claim made from it rather than left for a reader to work out.
    """
    usable = [values for values in groups if len(values) >= 2]
    if len(usable) < 2:
        return {"verdict": "INSUFFICIENT_N", "units": len(usable)}
    k = min(len(values) for values in usable)
    trimmed = [values[:k] for values in usable]
    n = len(trimmed)
    flat = [value for values in trimmed for value in values]
    grand = statistics.fmean(flat)
    means = [statistics.fmean(values) for values in trimmed]
    ms_between = (
        k * sum((mean - grand) ** 2 for mean in means) / (n - 1) if n > 1 else 0.0
    )
    within = sum(
        (value - mean) ** 2 for values, mean in zip(trimmed, means, strict=True)
        for value in values
    )
    ms_within = within / (n * (k - 1)) if n * (k - 1) > 0 else 0.0
    denominator = ms_between + (k - 1) * ms_within
    value = (ms_between - ms_within) / denominator if denominator > 0 else 0.0
    value = max(0.0, min(1.0, value))
    return {
        "units": n,
        "draws_per_unit": k,
        "ms_between": round(ms_between, 6),
        "ms_within": round(ms_within, 6),
        "icc": round(value, 4),
        "correlation_ceiling": round(value ** 0.5, 4),
        "draws_to_0.8": (
            None if value <= 0 or value >= 0.8
            else math.ceil((0.8 * (1 - value)) / (value * (1 - 0.8)))
        ),
        "assumes": ("draws exchangeable within a unit and the error homoscedastic across units; "
                    "neither is checked here"),
    }


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
    """Rank correlation. Two jobs here: the length residual, and the lexicon redundancy reading."""
    if len(xs) < 3 or len(xs) != len(ys):
        return None
    rx, ry = _ranks(xs), _ranks(ys)
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    numerator = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    denominator = math.sqrt(
        sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)
    )
    return round(numerator / denominator, 4) if denominator else None


def describe(values: list[float]) -> dict[str, Any]:
    """Quantiles and moments for one population, in `opening_counters.describe`'s exact shape.

    Imported from there rather than restated, so the quantile convention (nearest-rank, so every
    printed value is one a text actually scored) is literally the same convention the counter
    census reports. Imported inside the function because that module reaches
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
    return (root or DERIVED) / "affect-trajectory-royalroad.jsonl"


#: The comic census's committed draw, ids only. `dump` asserts against it: the handoff's rule is
#: to reuse that census's chapters so the two share a population and a later cross-reading costs
#: nothing, and an assertion is the only form of "the same chapters" that survives a re-run.
COMIC_CENSUS = RESULTS / "comic-beats-royalroad-census.json"


def comic_draw_ids() -> set[str] | None:
    """Every unit id the comic census DREW, kept and excluded alike, or None if it is not here.

    Kept **and** excluded: the four chapters that census could not send were drawn by the same
    rule and dropped by a transport budget, so the draw is the union. Comparing against the kept
    set alone would report a mismatch on every re-run of a rule that had not changed.
    """
    if not COMIC_CENSUS.is_file():
        return None
    payload = json.loads(COMIC_CENSUS.read_text(encoding="utf-8"))
    ids = {str(row["unit_id"]) for row in payload.get("rows", [])}
    ids |= {
        str(row["unit_id"]) for row in (payload.get("exclusions") or {}).get("excluded", [])
    }
    return ids


def dump(limit_per_cohort: int = PER_COHORT_TARGET) -> int:
    """Write the census draw to a local-only JSONL. **MirrorBench interpreter only.**

    The bridge `taste_calibration --dump` established and `comic_beats --dump` reused: the
    interpreter that can read 497MB of parquet is not the interpreter that can drive the
    transport, so the sampled chapters cross between them as a gitignored file rather than as a
    shared import. Ids, cohort, covariates and text; the text never leaves `derived/` and no
    committed artifact carries a word of it.

    **The draw is `comic_beats.dump`'s draw, character for character.** Same window, same
    one-chapter-per-story rule, same digest ordering, same per-cohort cap -- and then asserted
    against the comic census's committed id set, refusing rather than proceeding on a mismatch.
    A census run on a different 245 chapters would be a different population wearing the same
    name, and the whole reason to reuse the draw is that the two censuses can then be read
    together for free.
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
                    "average_views": unit.meta.get("average_views"),
                    "shard": unit.meta.get("shard"),
                    "snapshot": corpus_io.SNAPSHOT_REVISION,
                    "text": unit.text,
                }
            )

    drawn = {str(row["unit_id"]) for row in rows}
    expected = comic_draw_ids()
    if expected is None:
        print("  NOTE: comic-beats-royalroad-census.json is not present, so the draw could not "
              "be asserted against it", file=sys.stderr, flush=True)
    elif drawn != expected:
        raise SystemExit(
            f"the draw does not match the comic census: {len(drawn)} here against "
            f"{len(expected)} there, {len(drawn - expected)} extra and "
            f"{len(expected - drawn)} missing. The two censuses are supposed to share a "
            "population; refusing rather than measuring a different one under the same name."
        )
    else:
        print(f"  draw asserted: the same {len(drawn)} chapters as the comic-beat census",
              file=sys.stderr, flush=True)

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
            "python.exe research/quality-measurement/affect_trajectory.py --dump"
        )
    units = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            units.append({**row, "substrate": "royalroad"})
    return units


def own_units(
    library: Path, databases: list[Path], scene_min_words: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Our own prose: the published chapters, then every drafted scene, kept apart.

    **The published chapter is the unit, not the scene** -- `opening_counters.
    reappraisal_chapters` and `chapter_endings.published_chapters` make the same choice for the
    same reason, and this reads the same folder rather than reassembling scenes here. Scenes are
    returned in a separate list so nothing downstream can pool a scene statistic with a chapter
    statistic by accident.

    Both paths are arguments because `book-library/` and the book databases are gitignored build
    products that live in the primary checkout: a linked worktree does not have them, and a
    loader that silently found nothing would report a census of zero chapters as a measurement.
    """
    chapters: list[dict[str, Any]] = []
    for path in sorted(library.glob("*/chapters/Chapter*.txt")):
        text = path.read_text(encoding="utf-8")
        chapters.append(
            {
                "unit_id": f"{path.parent.parent.name}:{path.stem}",
                "substrate": "local",
                "cohort": "own_chapter",
                "work_id": path.parent.parent.name,
                "words": len(text.split()),
                "source_path": str(path),
                "text": text,
            }
        )
    scenes: list[dict[str, Any]] = []
    if databases:
        import corpus_io

        from litharness.adapters.sqlite_store import SqliteStore

        for path in databases:
            store = SqliteStore.open(str(path))
            try:
                branches = [(book, branch) for book, branch, _ in store.branches()]
            finally:
                store.close()
            for book_id, branch_id in branches:
                for unit in corpus_io.generated_scenes(
                    path, book=book_id, branch=branch_id, min_words=scene_min_words
                ):
                    title = str(unit.meta.get("book_title") or book_id[:8])
                    scenes.append(
                        {
                            "unit_id": f"{path.stem}:{unit.unit_id}",
                            "substrate": "local",
                            "cohort": "own_scene",
                            "work_id": f"{path.stem}:{title}",
                            "words": unit.words,
                            "source_path": str(path),
                            "text": unit.text,
                        }
                    )
    return chapters, scenes


def default_databases() -> list[Path]:
    """Every own-generated book database on this machine, in a fixed order, existence-filtered.

    `chapter_endings._databases`' list and its reason: each of these is gitignored or untracked
    and lives in the primary checkout only, so a linked worktree finds none of them and the arm
    records which were read rather than reporting a census of zero as a measurement.
    """
    found = [
        REPO / "serial.db",
        REPO / "serial3.db",
        REPO / "exports" / "book-snapshots.db",
        HERE / "corpora" / "toll.db",
    ]
    found += sorted((HERE / "corpora" / "fitness").glob("fitness-*.db"))
    return [path for path in found if path.exists()]


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
        "else \u2014 no prose, no code fence:\n" + json.dumps(SCHEMA, sort_keys=True)
    )
    argv = [
        "claude", "-p", prompt,
        "--output-format", "json",
        "--model", model,
        "--system-prompt", full_system,
        *CLI_HARDENING,
    ]
    return len(subprocess.list2cmdline(argv))


def numbered(text: str) -> str:
    """The chapter as the model is shown it: every paragraph of the grid behind its own number.

    The numbers are what let the model stop keeping count, which is the defect the second
    pricing batch measured (`NUMBERED_GRID_FOUND_AT_PRICING`). The grid is unchanged -- the
    blocks are `grid_of`'s blocks, in order -- and the separator convention of the text THIS
    CALL WAS SHOWN is preserved, so `rewhitespace`'s choice of separator survives the render
    instead of being normalised away with it.
    """
    separator = "\n\n" if re.search(r"\n\s*\n", text) else "\n"
    return separator.join(
        f"[{index + 1}] {block}" for index, block in enumerate(grid_of(text))
    )


def render_turn(text: str) -> str:
    """The one user turn: the numbered chapter, then the question carrying its count."""
    count = len(grid_of(text))
    return f"{numbered(text)}\n\n---\n\n{QUESTION_TEMPLATE.format(count=count)}"


def apply_window(
    units: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The window, applied to every unit on every substrate, with the drops returned not dropped.

    Scene-grain units are exempt: the window is a chapter window, drawn on the chapter
    distribution, and applying it to scenes would silently delete the secondary arm rather than
    measure it. They carry their own floor through `--scene-min-words`.
    """
    kept, excluded = [], []
    for unit in units:
        exempt = unit.get("cohort") == "own_scene"
        if exempt or MIN_CHAPTER_WORDS <= unit["words"] <= MAX_CHAPTER_WORDS:
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
        databases = (
            [Path(item) for item in args.databases.split(";") if item]
            if args.databases else default_databases()
        )
        chapters, scenes = own_units(
            Path(args.library), [] if args.no_scenes else databases, args.scene_min_words
        )
        if not chapters:
            raise SystemExit(
                f"no */chapters/Chapter*.txt under {args.library}. `book-library/` is a "
                "gitignored build product that lives in the primary checkout; pass --library "
                "and --databases if this is a linked worktree."
            )
        print(f"  own substrate: {len(chapters)} published chapter(s), {len(scenes)} drafted "
              f"scene(s) from {len(databases)} database(s)", file=sys.stderr, flush=True)
        candidates = chapters + scenes
    kept, excluded = apply_window(candidates)
    if args.transport == "cli":
        from elicit import PANEL_MODEL

        model = args.model or PANEL_MODEL
        sendable = []
        for unit in kept:
            chars = cli_command_chars(SYSTEM, render_turn(unit["text"]), model)
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


def _synthetic_answer(key: str, grid: list[str]) -> str:
    """A dry run's stand-in answer: deterministic, and deliberately carrying **no signal**.

    S89.4's lesson, which cost a dry run that exercised none of the paths it existed to check:
    `elicit._synthetic_text` knew none of the new stages, so every answer came back refused and
    the scorers never ran. This module answers its own dry calls rather than editing that shared
    function, and the answer is drawn from a hash of the request and **never from the arm** -- so
    a dry `flatten` is a draw from the null and every reading of it should come back
    INSUFFICIENT_N or a coin.

    Roughly one entry in eight carries a deliberately wrong echo, so a dry run exercises the
    misalignment path, the rate, the gap handling in every statistic and the permutation null.
    The resulting misalignment rate near 0.12 is arbitrary on purpose: nobody can mistake a dry
    number here for a measurement.
    """
    marker = int(key[:8], 16)
    entries = []
    for index, paragraph in enumerate(grid):
        kind = KINDS[(marker + index * 7) % len(KINDS)]
        if (marker >> (index % 32)) & 7 == 0:
            echo = f"(dry run) not paragraph {index}"
        else:
            echo = " ".join(paragraph.split()[:ECHO_WORDS])
        entries.append({"n": index + 1, "kind": kind, "echo": echo})
    return json.dumps({"paragraphs": entries})


def ask_series(
    elicitor: Any, unit: dict[str, Any], text_shown: str, *,
    sample: int, arm: str, dry_run: bool,
) -> dict[str, Any]:
    """One locator call on one chapter, aligned and turned into a trajectory.

    The turn is the whole chapter and then the frozen question carrying that chapter's paragraph
    count, which is `elicitation_study`'s shape with the one thing the schema cannot express
    added to it. One chapter per call: chunking changes the series, so a chapter that does not
    fit the window never reaches here.
    """
    from elicit import _strip_fence

    grid = grid_of(text_shown)
    words = [len(paragraph.split()) for paragraph in grid]
    turn = [{"role": "user", "content": render_turn(text_shown)}]
    tag = {"unit": unit["unit_id"], "arm": arm, "stage": "affect_trajectory", "sample": sample}
    if dry_run:
        key = digest({"system": SYSTEM, "text": text_shown, "sample": sample})
        record: dict[str, Any] = {
            **tag, "key": key, "model": "(dry)", "usage": {}, "dry_run": True,
            "text": _synthetic_answer(key, grid), "refused": False,
        }
    else:
        record = elicitor.ask_raw(
            SYSTEM, turn, schema=SCHEMA, max_tokens=LABELS_MAX_TOKENS, tag=tag, sample=sample,
        )
    if record.get("refused"):
        scored = align(grid, None)
        scored["refused"] = True
        scored["stop_reason"] = record.get("stop_reason", "")
    else:
        try:
            payload = json.loads(_strip_fence(str(record.get("text", ""))))
        except json.JSONDecodeError:
            payload = None
        scored = align(grid, payload)
        scored["refused"] = False
    labels = scored["labels"]
    stats = trajectory(labels, words)
    null = _permutation_null(labels, words, seed=f"{unit['unit_id']}|{arm}|{sample}")
    return {
        **scored,
        "grid": grid,
        "words": words,
        "trajectory": stats,
        "pairing_null": null,
        "scalars": scalars(stats, null),
        "usage": record.get("usage", {}),
    }


def system_voice_flags(grid: list[str]) -> list[bool]:
    """Which paragraphs are system voice, deterministically and as a covariate.

    `axes._SYSTEM`'s pattern -- a bolded run or any line carrying a bracketed all-caps tag --
    imported rather than restated so this agrees with every counter that has ever used it. A
    [STATUS] block can itself be the paragraph a chapter's win arrives in, and the model is shown
    it, so this flag never excludes anything: every statistic is reported with and without.
    """
    from litharness.domain.axes import _SYSTEM

    return [bool(_SYSTEM.search(paragraph)) for paragraph in grid]


def _row(
    unit: dict[str, Any], scored: dict[str, Any], *, sample: int, quote: bool
) -> dict[str, Any]:
    """One call's committed record. Ids and numbers, plus echoes only where we own the prose."""
    grid = scored["grid"]
    words = scored["words"]
    try:
        flags = system_voice_flags(grid)
    except ImportError:
        flags = [False] * len(grid)
    prose_labels: list[str | None] = [
        None if flag else label
        for label, flag in zip(scored["labels"], flags, strict=True)
    ]
    prose_stats = trajectory(prose_labels, words)
    prose_null = _permutation_null(
        prose_labels, words, seed=f"{unit['unit_id']}|prose|{sample}"
    )
    return {
        "unit_id": unit["unit_id"],
        "sample": sample,
        "cohort": unit.get("cohort"),
        "work_id": unit.get("work_id"),
        "words": unit["words"],
        "paragraphs": len(grid),
        "system_voice_paragraphs": sum(flags),
        "returned": scored["returned"],
        "compared": scored["compared"],
        "aligned": scored["aligned"],
        "misaligned": scored["misaligned"],
        "extra": scored["extra"],
        "missing": scored["missing"],
        "bad_kind": scored["bad_kind"],
        "bad_index": scored["bad_index"],
        "duplicate_index": scored["duplicate_index"],
        "out_of_order": scored["out_of_order"],
        "echo_exactly_four": scored["echo_exactly_four"],
        "misalignment_rate": scored["misalignment_rate"],
        "unparseable": scored["unparseable"],
        "refused": scored["refused"],
        "trajectory": scored["trajectory"],
        "pairing_null": scored["pairing_null"],
        "scalars": scored["scalars"],
        "trajectory_without_system_voice": prose_stats,
        "scalars_without_system_voice": scalars(prose_stats, prose_null),
        "lexicon": lexicon_series(grid),
        "series": public_series(scored, grid, quote=quote),
    }


def hygiene(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """The rates every arm prints, whatever else it says. A coverage with no hygiene beside it
    is a coverage nobody can tell from a parse failure."""
    compared = sum(row["compared"] for row in rows)
    misaligned = sum(row["misaligned"] for row in rows)
    return {
        "calls": len(rows),
        "entries_compared": compared,
        "misaligned": misaligned,
        "misalignment_rate": round(misaligned / compared, 4) if compared else None,
        "extra_entries": sum(row["extra"] for row in rows),
        "missing_entries": sum(row["missing"] for row in rows),
        "bad_kind": sum(row["bad_kind"] for row in rows),
        "bad_index": sum(row["bad_index"] for row in rows),
        "duplicate_index": sum(row["duplicate_index"] for row in rows),
        "out_of_order": sum(row["out_of_order"] for row in rows),
        "echo_exactly_four": sum(row["echo_exactly_four"] for row in rows),
        "unparseable_calls": sum(1 for row in rows if row["unparseable"]),
        "refused_calls": sum(1 for row in rows if row["refused"]),
        "median_aligned_word_share": round(statistics.median(
            [float(row["trajectory"]["aligned_word_share"] or 0.0) for row in rows]
        ), 4) if rows else None,
    }


def spend_of(usages: list[dict[str, Any]]) -> dict[str, Any]:
    """What the arm cost, from the transport's own envelopes. Never projected from another arm.

    On a subscription the `equivalent_usd` field is an equivalent API price for quota already
    paid for (`elicit._call_cli` argues that at length), so it is operational rather than
    evidential. S79.1 also applies in the other direction: this is the only price this module
    reports, and it is measured here rather than inherited from the comic census.
    """
    total = 0.0
    tokens = {"input": 0.0, "output": 0.0, "cache_read": 0.0, "cache_write": 0.0}
    for usage in usages:
        total += float((usage or {}).get("equivalent_usd") or 0.0)
        for name in tokens:
            tokens[name] += float((usage or {}).get(name) or 0.0)
    return {"equivalent_usd": round(total, 4), **{k: int(v) for k, v in tokens.items()}}


# ----------------------------------------------------------------------------- the plumbing


def base_arm(substrate: str) -> str:
    """Which arm the downstream arms read their subsets from. `census` there, `own` here."""
    return "census" if substrate == "royalroad" else "own"


def result_path(substrate: str, arm: str, dry: bool = False) -> Path:
    """Where an arm's committed record lands. A dry run gets its own suffix and cannot touch a
    paid arm's file -- the class of accident the runbook's "five ways to waste a paid run" is a
    list of, closed structurally rather than by remembering."""
    return RESULTS / f"affect-trajectory-{substrate}-{arm}{'-dry' if dry else ''}.json"


def cache_path(substrate: str, arm: str, dry: bool = False) -> Path:
    """A dedicated cache per arm, and RoyalRoad's under `derived/`.

    Two rules meeting. `Elicitor`'s write lock is per process, so two runs sharing one JSONL
    interleave and corrupt each other's records (RUNBOOK, "five ways to waste a paid run"). And a
    RoyalRoad raw cache holds the model's answer verbatim, whose echoes are quoted words of
    somebody else's novel, so it belongs where the leak audit already guards -- `derived/`,
    gitignored, untracked, and never a committed artifact.
    """
    root = DERIVED if substrate == "royalroad" else RESULTS
    return root / f"affect-trajectory-{substrate}-{arm}{'-dry' if dry else ''}-raw.jsonl"


def load_result(substrate: str, arm: str, dry: bool = False) -> dict[str, Any]:
    path = result_path(substrate, arm, dry)
    if not path.is_file():
        raise SystemExit(
            f"{path} is missing, and this arm is read against it. The order is "
            f"{base_arm(substrate)}, then repeat, then sham, then flatten: the flatten "
            "subset is the base arm's own top "
            "decile by coverage and the noise floor has to cover it."
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


def _by_unit(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Rows grouped by unit, in sample order. K draws of one chapter are one unit, not K."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["unit_id"]), []).append(row)
    for values in grouped.values():
        values.sort(key=lambda row: int(row["sample"]))
    return grouped


def unit_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """One unit's K draws collapsed to a value and the interval those draws give it.

    **This is the only form in which a per-unit number leaves this module.** The comic census
    could place a chapter from one draw and did, and its own reliability arm then said the
    placement was worth thirty percentile points; here a placement carries its draws or it is not
    reported. `n_draws` prints beside every one of them.
    """
    values: dict[str, Any] = {}
    for name in SCALAR_STATISTICS:
        drawn = [
            float(row["scalars"][name]) for row in rows if row["scalars"].get(name) is not None
        ]
        values[name] = {
            "n_draws": len(drawn),
            "median": round(statistics.median(drawn), 4) if drawn else None,
            "mean": round(statistics.fmean(drawn), 4) if drawn else None,
            "min": round(min(drawn), 4) if drawn else None,
            "max": round(max(drawn), 4) if drawn else None,
            "sd": round(statistics.pstdev(drawn), 4) if len(drawn) > 1 else 0.0,
            "draws": [round(value, 4) for value in drawn],
        }
    return values


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
    results: list[tuple[int, dict[str, Any], int, dict[str, Any]]] = []
    done = 0

    def one(index: int) -> tuple[int, dict[str, Any], int, dict[str, Any]]:
        unit, text_shown, sample = jobs[index]
        return index, unit, sample, ask_series(
            elicitor, unit, text_shown, sample=sample, arm=arm, dry_run=dry_run
        )

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for index, unit, sample, scored in pool.map(one, range(len(jobs))):
            results.append((index, unit, sample, scored))
            done += 1
            _progress(arm, done, len(jobs))
    results.sort(key=lambda item: item[0])
    rows = [
        _row(unit, scored, sample=sample, quote=quote) for _, unit, sample, scored in results
    ]
    usages = [scored.get("usage") or {} for _, _, _, scored in results]
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


def _tail(elicitor: Any) -> dict[str, Any]:
    return {
        "transport_failures": elicitor.transport_failures,
        "failure_reasons": dict(elicitor.failure_reasons),
        "api_calls": elicitor.api_calls,
        "replayed": elicitor.replayed,
    }


def run_census(args: argparse.Namespace) -> dict[str, Any]:
    """RoyalRoad, one chapter per story, ONE draw. Q1 is read from this arm alone."""
    if args.substrate != "royalroad":
        raise SystemExit("--arm census is the RoyalRoad arm; our own prose runs --arm own at K="
                         f"{OWN_DRAWS}, because a placement from a single draw is not a placement")
    units, ledger = load_units(args)
    elicitor = _elicitor(args, "census")
    jobs = [(unit, unit["text"], 0) for unit in units]
    with elicitor:
        rows, usages = _sweep(elicitor, jobs, arm="census", dry_run=args.dry_run,
                              workers=elicitor.max_workers, quote=False)
    return _envelope(args, "census", {
        "window": [MIN_CHAPTER_WORDS, MAX_CHAPTER_WORDS],
        "draws_per_unit": 1,
        "exclusions": ledger,
        "rows": rows,
        "hygiene": hygiene(rows),
        "spend": spend_of(usages),
        **_tail(elicitor),
    })


def run_own(args: argparse.Namespace) -> dict[str, Any]:
    """Our own prose at K draws per unit, so every placement carries its own interval.

    The comic census placed a chapter from one draw and its own reliability arm then priced that
    placement at thirty percentile points of slop. Four draws is what its variance decomposition
    computed would reach reliability 0.8, and this arm buys them before rather than after.
    Sixteen calls on four chapters is not where the money goes.
    """
    if args.substrate != "local":
        raise SystemExit("--arm own is the local arm; RoyalRoad runs --arm census")
    units, ledger = load_units(args)
    elicitor = _elicitor(args, "own")
    jobs: list[tuple[dict[str, Any], str, int]] = []
    for unit in units:
        draws = OWN_SCENE_DRAWS if unit.get("cohort") == "own_scene" else OWN_DRAWS
        jobs.extend((unit, unit["text"], sample) for sample in range(draws))
    print(f"  own arm: {len(units)} unit(s), {len(jobs)} call(s) "
          f"(chapters at K={OWN_DRAWS}, scenes at K={OWN_SCENE_DRAWS})",
          file=sys.stderr, flush=True)
    with elicitor:
        rows, usages = _sweep(elicitor, jobs, arm="own", dry_run=args.dry_run,
                              workers=elicitor.max_workers, quote=True)
    grouped = _by_unit(scoreable({"rows": rows}))
    return _envelope(args, "own", {
        "window": [MIN_CHAPTER_WORDS, MAX_CHAPTER_WORDS],
        "draws_per_unit": {"own_chapter": OWN_DRAWS, "own_scene": OWN_SCENE_DRAWS},
        "exclusions": ledger,
        "rows": rows,
        "per_unit": {unit_id: unit_summary(draws) for unit_id, draws in sorted(grouped.items())},
        "within_unit": within_unit_reliability(rows),
        "hygiene": hygiene(rows),
        "spend": spend_of(usages),
        **_tail(elicitor),
    })


def within_unit_reliability(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Kappa across every pair of draws on one unit, and the ICC of every statistic across them.

    On `local` this **is** the noise floor: the `own` arm already carries K draws per unit, so a
    separate `repeat` arm there would buy a second copy of a measurement already made. On
    RoyalRoad the same function reads the `repeat` arm's second draw beside the census's first.
    """
    usable = [row for row in rows if not row["refused"] and not row["unparseable"]]
    grouped = _by_unit(usable)
    kappas: list[float] = []
    per_unit: dict[str, Any] = {}
    for unit_id, draws in sorted(grouped.items()):
        if len(draws) < 2:
            continue
        values: list[float] = []
        for left in range(len(draws)):
            for right in range(left + 1, len(draws)):
                value = cohens_kappa(
                    [entry["kind"] for entry in draws[left]["series"]],
                    [entry["kind"] for entry in draws[right]["series"]],
                )
                if value is not None:
                    values.append(value)
        if values:
            per_unit[unit_id] = round(statistics.fmean(values), 4)
            kappas.extend(values)
    iccs = {
        name: icc([
            [float(row["scalars"][name]) for row in draws
             if row["scalars"].get(name) is not None]
            for draws in grouped.values()
        ])
        for name in SCALAR_STATISTICS
    }
    return {
        "units_with_repeats": len(per_unit),
        "paragraph_kappa": {
            "pairs": len(kappas),
            "summary": describe(kappas) if kappas else {"n": 0},
            "per_unit": per_unit,
            "note": ("Cohen's kappa over the ten kinds, computed only on paragraphs aligned in "
                     "both draws; a chapter both draws labelled one kind throughout is "
                     "undefined and is dropped rather than scored 0"),
        },
        "statistic_icc": iccs,
    }


def _paired_arm(
    args: argparse.Namespace, arm: str, transform: Any, sample: int
) -> dict[str, Any]:
    """`repeat` and `sham` are one function: same subset, same pairing, one different text."""
    base = load_result(args.substrate, base_arm(args.substrate), bool(args.dry_run))
    wanted = set(noise_subset(base))
    units = [unit for unit in load_units(args)[0] if unit["unit_id"] in wanted]
    missing = wanted - {unit["unit_id"] for unit in units}
    if missing:
        raise SystemExit(f"{len(missing)} unit(s) in the subset are not in the substrate: "
                         f"{sorted(missing)[:5]}")
    quote = args.substrate != "royalroad"
    grid_losses: list[dict[str, Any]] = []
    jobs: list[tuple[dict[str, Any], str, int]] = []
    for unit in units:
        shown = transform(unit["text"])
        if arm == "sham" and not sham_grid_survives(unit["text"], shown):
            grid_losses.append({
                "unit_id": unit["unit_id"],
                "paragraphs_before": len(grid_of(unit["text"])),
                "paragraphs_after": len(grid_of(shown)),
                "reason": "the reflow re-cut the paragraph grid, so the two series are not "
                          "comparable; excluded and counted rather than re-cut silently",
            })
            continue
        jobs.append((unit, shown, sample))
    for loss in grid_losses:
        print(f"  EXCLUDED {loss['unit_id']}: {loss['reason']}", file=sys.stderr, flush=True)
    elicitor = _elicitor(args, arm)
    with elicitor:
        rows, usages = _sweep(elicitor, jobs, arm=arm, dry_run=args.dry_run,
                              workers=elicitor.max_workers, quote=quote)
    pairs = _pair_against_base(base, rows, arm)
    return _envelope(args, arm, {
        "subset": sorted(wanted),
        "grid_losses": grid_losses,
        "rows": rows,
        "pairs": pairs,
        "hygiene": hygiene(rows),
        "spend": spend_of(usages),
        **_tail(elicitor),
        "summary": _spread_summary(pairs, arm),
    })


def _pair_against_base(
    base: dict[str, Any], rows: list[dict[str, Any]], arm: str
) -> list[dict[str, Any]]:
    """One row per unit: the base arm's first draw beside this arm's, on every statistic.

    The base arm's draw is sample 0 explicitly rather than "whichever came first": on `local` the
    base arm is `own` with K draws and pairing against the median of them would compare a mean
    with a single draw, which understates the spread by exactly the thing being measured.
    """
    first = {
        str(row["unit_id"]): row
        for row in scoreable(base)
        if int(row.get("sample", 0)) == 0
    }
    pairs = []
    for row in rows:
        left = first.get(str(row["unit_id"]))
        if left is None or row["refused"] or row["unparseable"]:
            continue
        deltas: dict[str, Any] = {}
        for name in SCALAR_STATISTICS:
            a, b = left["scalars"].get(name), row["scalars"].get(name)
            deltas[name] = {
                "base": a,
                arm: b,
                "abs_delta": round(abs(float(a) - float(b)), 6)
                if a is not None and b is not None else None,
                "signed_delta": round(float(b) - float(a), 6)
                if a is not None and b is not None else None,
            }
        pairs.append({
            "unit_id": row["unit_id"],
            "cohort": row["cohort"],
            "words": row["words"],
            "paragraph_kappa": cohens_kappa(
                [entry["kind"] for entry in left["series"]],
                [entry["kind"] for entry in row["series"]],
            ),
            "deltas": deltas,
        })
    return pairs


def _spread_summary(pairs: list[dict[str, Any]], arm: str) -> dict[str, Any]:
    """The ruler, or the thing read against it. No verdict here: `sham` is judged in the report,
    where the repeat spread it is read against is available."""
    kappas = [
        float(pair["paragraph_kappa"]) for pair in pairs if pair["paragraph_kappa"] is not None
    ]
    return {
        "arm": arm,
        "pairs": len(pairs),
        "paragraph_kappa": describe(kappas) if kappas else {"n": 0},
        "abs_delta": {
            name: describe([
                float(pair["deltas"][name]["abs_delta"]) for pair in pairs
                if pair["deltas"][name]["abs_delta"] is not None
            ])
            for name in SCALAR_STATISTICS
        },
        "signed_delta_mean": {
            name: (
                round(statistics.fmean([
                    float(pair["deltas"][name]["signed_delta"]) for pair in pairs
                    if pair["deltas"][name]["signed_delta"] is not None
                ]), 6)
                if any(pair["deltas"][name]["signed_delta"] is not None for pair in pairs)
                else None
            )
            for name in SCALAR_STATISTICS
        },
    }


def run_repeat(args: argparse.Namespace) -> dict[str, Any]:
    """Sample 1 of a byte-identical request. The variation is the model's own sampling."""
    if args.substrate == "local":
        raise SystemExit(
            f"--arm repeat does not run on `local`: the `own` arm already carries K={OWN_DRAWS} "
            "draws per chapter and its within-unit spread IS the noise floor there. Buying a "
            "second copy of a measurement already made is one of the five ways to waste a paid "
            "run."
        )
    return _paired_arm(args, "repeat", lambda text: text, 1)


def run_sham(args: argparse.Namespace) -> dict[str, Any]:
    """`ablate.rewhitespace` at full strength: not one character of any word changes."""
    from ablate import rewhitespace

    return _paired_arm(args, "sham", lambda text: rewhitespace(text, 1.0), 0)


# ------------------------------------------------------------------------------ the subsets


def flatten_subset(base: dict[str, Any]) -> list[str]:
    """The units the damage arm runs on: text that HAS coverage to flatten.

    The top decile by located coverage on RoyalRoad, every published chapter on ours. Selecting
    on the outcome is deliberate and is why the arm is read against a placebo rather than against
    the population: a top-decile chapter regresses toward the mean on any re-ask whether or not
    anything was removed from it, and the placebo carries exactly that regression.
    """
    rows = scoreable(base)
    if base["substrate"] == "royalroad":
        ranked = [row for row in rows if row["scalars"].get("coverage") is not None]
        ordered = sorted(
            ranked, key=lambda row: (-float(row["scalars"]["coverage"]), row["unit_id"])
        )
        take = round(FLATTEN_TOP_FRACTION * len(ranked))
        return sorted({row["unit_id"] for row in ordered[:take]})
    return sorted({row["unit_id"] for row in rows if row["cohort"] == "own_chapter"})


def noise_subset(base: dict[str, Any]) -> list[str]:
    """The units the `repeat` and `sham` arms run on: a stratified draw **plus** the flatten set.

    Folding the flatten subset in is not tidiness. The flatten drop is read against the noise
    floor *per unit*, and a floor measured on other units would be a population statistic
    standing in for a unit's own -- the substitution S79.1 exists to refuse.
    """
    rows = scoreable(base)
    if base["substrate"] != "royalroad":
        # Chapters only, and the reason is a cost one stated rather than a cap applied quietly:
        # the layout sham exists to qualify the readings, every reading on this substrate is
        # made at chapter grain, and the scenes already carry their own within-unit spread from
        # the `own` arm's K draws. Running the sham over 150-odd scenes would buy a second
        # opinion about units no reading rests on.
        return sorted({row["unit_id"] for row in rows if row["cohort"] == "own_chapter"})
    by_cohort: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_cohort.setdefault(str(row["cohort"]), []).append(row)
    draw: set[str] = set()
    for _cohort, members in sorted(by_cohort.items()):
        share = round(REPEAT_SUBSET * len(members) / max(len(rows), 1))
        ordered = sorted(members, key=lambda row: digest(row["unit_id"]))
        draw.update(row["unit_id"] for row in ordered[:share])
    return sorted(draw | set(flatten_subset(base)))


# ---------------------------------------------------------------------------- the flatten arm


def certify(original: str, variant: str) -> dict[str, Any]:
    """The deterministic checks that make a revision a certified minimal one.

    `repair_generation.compliance`'s pattern at chapter grain: word-level similarity, a two-sided
    growth bound, byte-survival of every protected span, **and the paragraph grid**, which is
    this instrument's own addition and is load-bearing rather than fastidious. The grid is the
    unit of measurement here: a revision that returned 41 paragraphs where the original had 44
    would produce a series that cannot be paired with the original at all, and pairing it by
    index would silently compare paragraph 30 with paragraph 33. A revision failing any of these
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
    before, after = len(grid_of(original)), len(grid_of(variant))
    reasons = []
    if similarity < FLATTEN_MIN_SIMILARITY:
        reasons.append(f"similarity {similarity} < {FLATTEN_MIN_SIMILARITY}")
    if abs(growth) > FLATTEN_MAX_GROWTH_PCT:
        reasons.append(f"word growth {growth}% outside +-{FLATTEN_MAX_GROWTH_PCT}%")
    if survival["kept"] != survival["spans"]:
        reasons.append(f"protected spans {survival['kept']}/{survival['spans']} survived")
    if FLATTEN_REQUIRE_SAME_GRID and before != after:
        reasons.append(f"paragraph grid moved: {before} -> {after}")
    return {
        "similarity": similarity,
        "word_growth_pct": growth,
        "protected_spans": survival["spans"],
        "protected_kept": survival["kept"],
        "paragraphs_before": before,
        "paragraphs_after": after,
        "certified": not reasons,
        "reasons": reasons,
    }


def run_flatten(args: argparse.Namespace) -> dict[str, Any]:
    """The damage direction, with its placebo beside it and its own internal control inside it."""
    from writer_states import GEN_MAX_WORKERS, WRITER_MODEL, Generator

    base = load_result(args.substrate, base_arm(args.substrate), bool(args.dry_run))
    wanted = set(flatten_subset(base))
    units = {unit["unit_id"]: unit for unit in load_units(args)[0] if unit["unit_id"] in wanted}
    if len(units) < len(wanted):
        raise SystemExit(f"{len(wanted) - len(units)} flatten-subset unit(s) missing from the "
                         "substrate; the base arm and the substrate have diverged")
    rule = ("top decile by located coverage" if args.substrate == "royalroad"
            else "every published chapter")
    print(f"  flatten subset: {len(units)} unit(s), {rule}", file=sys.stderr, flush=True)

    generations: dict[tuple[str, str], str] = {}
    gen_cache = DERIVED / (
        f"affect-trajectory-{args.substrate}-flatten-gen{'-dry' if args.dry_run else ''}.jsonl"
    )
    gen_cache.parent.mkdir(parents=True, exist_ok=True)
    with Generator(gen_cache, model=args.writer_model or WRITER_MODEL,
                   dry_run=bool(args.dry_run)) as generator:
        jobs = [(unit_id, task) for unit_id in sorted(units) for task in sorted(FLATTEN_TASKS)]

        def _generate(index: int) -> tuple[tuple[str, str], dict[str, Any]]:
            unit_id, task = jobs[index]
            text = units[unit_id]["text"]
            return (unit_id, task), generator.generate(
                {"unit": unit_id, "task": task},
                FLATTEN_SYSTEM,
                FLATTEN_RULES.format(task=FLATTEN_TASKS[task]) + f"\n\n---\n\n{text}",
                dry_text=text,
            )

        # `writer_states.GEN_MAX_WORKERS`, that module's own declared concurrency for exactly
        # this call shape (a whole chapter generated over `claude -p`), rather than a number
        # chosen here. Its write lock covers the shared cache and its digest keying makes an
        # interruption lossless, which is the checkpoint-per-unit property this box needs.
        done = 0
        with ThreadPoolExecutor(max_workers=GEN_MAX_WORKERS) as pool:
            for label, record in pool.map(_generate, range(len(jobs))):
                if not record.get("refused"):
                    generations[label] = str(record.get("text") or "")
                done += 1
                _progress("generate", done, len(jobs))
        gen_calls, gen_replayed = generator.api_calls, generator.replayed

    certificates = {
        label: certify(units[label[0]]["text"], variant)
        for label, variant in generations.items()
    }

    elicitor = _elicitor(args, "flatten")
    revision_jobs: list[tuple[dict[str, Any], str, int]] = []
    labels: list[tuple[str, str]] = []
    for (unit_id, task), variant in sorted(generations.items()):
        revision_jobs.append(({**units[unit_id], "unit_id": f"{unit_id}|{task}",
                               "words": len(variant.split())}, variant, 0))
        labels.append((unit_id, task))
    quote = args.substrate != "royalroad"
    with elicitor:
        rows, usages = _sweep(elicitor, revision_jobs, arm="flatten", dry_run=args.dry_run,
                              workers=elicitor.max_workers, quote=quote)
    scored = dict(zip(labels, rows, strict=True))

    first = {
        str(row["unit_id"]): row for row in scoreable(base) if int(row.get("sample", 0)) == 0
    }
    spread = _noise_floor(args)

    pairs: list[dict[str, Any]] = []
    uncertified: list[dict[str, Any]] = []
    for unit_id in sorted(units):
        original = first.get(unit_id)
        flattened = scored.get((unit_id, "flatten"))
        placebo = scored.get((unit_id, "flatten_placebo"))
        if original is None or flattened is None or placebo is None:
            uncertified.append({"unit_id": unit_id, "reasons": ["a call did not return"]})
            continue
        certs = {task: certificates[(unit_id, task)] for task in ("flatten", "flatten_placebo")}
        reasons = [
            f"{task}: {reason}" for task, cert in certs.items() for reason in cert["reasons"]
        ]
        if certs["flatten"]["similarity"] >= certs["flatten_placebo"]["similarity"]:
            reasons.append(
                f"flatten similarity {certs['flatten']['similarity']} is not below the placebo's "
                f"{certs['flatten_placebo']['similarity']}: it did not change more than the floor"
            )
        if flattened["refused"] or placebo["refused"] or flattened["unparseable"] \
                or placebo["unparseable"]:
            reasons.append("a locator call on a revision refused or did not parse")
        if reasons:
            uncertified.append({"unit_id": unit_id, "reasons": reasons, "certificates": certs})
            continue
        drops: dict[str, Any] = {}
        for name in SCALAR_STATISTICS:
            base_value = original["scalars"].get(name)
            flat_value = flattened["scalars"].get(name)
            placebo_value = placebo["scalars"].get(name)
            drops[name] = {
                "original": base_value,
                "flatten": flat_value,
                "placebo": placebo_value,
                "drop_flatten": round(float(base_value) - float(flat_value), 6)
                if base_value is not None and flat_value is not None else None,
                "drop_placebo": round(float(base_value) - float(placebo_value), 6)
                if base_value is not None and placebo_value is not None else None,
            }
        pairs.append({
            "unit_id": unit_id,
            "cohort": original["cohort"],
            "words": original["words"],
            "protected_spans": certs["flatten"]["protected_spans"],
            "system_voice_paragraphs": original["system_voice_paragraphs"],
            "prose_only": {
                "original": original["scalars_without_system_voice"].get(PRIMARY_READING),
                "flatten": flattened["scalars_without_system_voice"].get(PRIMARY_READING),
                "placebo": placebo["scalars_without_system_voice"].get(PRIMARY_READING),
            },
            "system_voice_only": _system_voice_coverage(original, flattened, placebo),
            "lexicon": {
                "original": original["lexicon"]["trajectory"].get(PRIMARY_READING),
                "flatten": flattened["lexicon"]["trajectory"].get(PRIMARY_READING),
                "placebo": placebo["lexicon"]["trajectory"].get(PRIMARY_READING),
            },
            "repeat_spread": spread.get(unit_id),
            "misalignment_rate_flatten": flattened["misalignment_rate"],
            "drops": drops,
            "certificates": certs,
        })

    readings = flatten_readings(pairs, hygiene([scored[label] for label in labels]))
    return _envelope(args, "flatten", {
        "writer_model": args.writer_model or WRITER_MODEL,
        "subset": sorted(wanted),
        "generation_calls": gen_calls,
        "generation_replayed": gen_replayed,
        "rows": rows,
        "pairs": pairs,
        "uncertified": uncertified,
        "hygiene": hygiene(rows),
        "spend": spend_of(usages),
        **_tail(elicitor),
        "readings": readings,
    })


def _system_voice_coverage(
    original: dict[str, Any], flattened: dict[str, Any], placebo: dict[str, Any]
) -> dict[str, Any]:
    """Coverage over system-voice paragraphs alone, which the revision contract cannot touch.

    Protected spans are copied byte-for-byte, so a [STATUS] paragraph the locator called
    `triumph` **cannot** be flattened. Recovered by subtraction rather than by a second pass: the
    whole-text coverage and the prose-only coverage are both computed, and their difference is
    what the system voice contributed. A run where the system-voice contribution falls with the
    prose is a locator responding to the fact of a rewrite.
    """
    def contribution(row: dict[str, Any]) -> float | None:
        whole = row["scalars"].get(PRIMARY_READING)
        prose = row["scalars_without_system_voice"].get(PRIMARY_READING)
        if whole is None or prose is None:
            return None
        return round(float(whole) - float(prose), 6)

    return {
        "original": contribution(original),
        "flatten": contribution(flattened),
        "placebo": contribution(placebo),
    }


def _noise_floor(args: argparse.Namespace) -> dict[str, float]:
    """Each unit's own repeat spread on the primary reading, or nothing if no arm measured one.

    On RoyalRoad that is the `repeat` arm's absolute delta; on `local` it is the spread across
    the `own` arm's K draws, which is the same quantity bought a different way. Missing rather
    than zero when neither exists: a floor nobody measured is not a floor of zero.
    """
    spread: dict[str, float] = {}
    if args.substrate == "royalroad":
        path = result_path(args.substrate, "repeat", bool(args.dry_run))
        if path.is_file():
            for pair in load_result(args.substrate, "repeat", bool(args.dry_run))["pairs"]:
                value = pair["deltas"][PRIMARY_READING]["abs_delta"]
                if value is not None:
                    spread[str(pair["unit_id"])] = float(value)
        return spread
    path = result_path(args.substrate, "own", bool(args.dry_run))
    if not path.is_file():
        return spread
    own = load_result(args.substrate, "own", bool(args.dry_run))
    for unit_id, values in (own.get("per_unit") or {}).items():
        entry = values.get(PRIMARY_READING) or {}
        if entry.get("n_draws", 0) >= 2 and entry.get("max") is not None:
            spread[str(unit_id)] = round(float(entry["max"]) - float(entry["min"]), 6)
    return spread


def flatten_readings(
    pairs: list[dict[str, Any]], flatten_hygiene: dict[str, Any]
) -> dict[str, Any]:
    """The two declared readings under Holm, the internal control, and the refusal state.

    Nothing here reads as a pass by silence: each reading carries its decided-pair count, its
    attainable floor, the k it needed and a distribution-free interval on the median it did or
    did not move. The primary and the secondary were named in `PRE_REGISTRATION` before the first
    call and the family is exactly those two; every other number below is descriptive and says so
    in `descriptive`.
    """
    def against_placebo(name: str) -> dict[str, Any]:
        return paired_reading(
            [
                float(pair["drops"][name]["drop_flatten"]) - float(
                    pair["drops"][name]["drop_placebo"]
                )
                for pair in pairs
                if pair["drops"][name]["drop_flatten"] is not None
                and pair["drops"][name]["drop_placebo"] is not None
            ],
            name=f"the flatten drop in {name} exceeds its placebo's drop",
            positive_verdict="SEES", null_verdict="DOES_NOT_SEE",
        )

    primary = against_placebo(PRIMARY_READING)
    secondary = against_placebo(SECONDARY_READING)
    family = holm([
        (PRIMARY_READING, float(primary["p_one_sided"])),
        (SECONDARY_READING, float(secondary["p_one_sided"])),
    ])

    floored = [pair for pair in pairs if pair["repeat_spread"] is not None]
    if floored:
        against_noise = paired_reading(
            [
                float(pair["drops"][PRIMARY_READING]["drop_flatten"])
                - float(pair["repeat_spread"])
                for pair in floored
                if pair["drops"][PRIMARY_READING]["drop_flatten"] is not None
            ],
            name="the flatten drop in coverage exceeds this unit's own noise floor",
            positive_verdict="SEES", null_verdict="DOES_NOT_SEE",
        )
    else:
        against_noise = {
            "statistic": "the flatten drop in coverage exceeds this unit's own noise floor",
            "verdict": "NOT_RUN",
            "because": ("no arm has measured a noise floor on this substrate, so no unit has one "
                        "of its own to be read against"),
        }

    prose_only = paired_reading(
        [
            (float(pair["prose_only"]["original"]) - float(pair["prose_only"]["flatten"]))
            - (float(pair["prose_only"]["original"]) - float(pair["prose_only"]["placebo"]))
            for pair in pairs
            if None not in (pair["prose_only"]["original"], pair["prose_only"]["flatten"],
                            pair["prose_only"]["placebo"])
        ],
        name="prose paragraphs only: the flatten drop exceeds its placebo's",
        positive_verdict="SEES", null_verdict="DOES_NOT_SEE",
    )
    control = _system_voice_control(pairs)
    lexicon_sees = paired_reading(
        [
            (float(pair["lexicon"]["original"]) - float(pair["lexicon"]["flatten"]))
            - (float(pair["lexicon"]["original"]) - float(pair["lexicon"]["placebo"]))
            for pair in pairs
            if None not in (pair["lexicon"]["original"], pair["lexicon"]["flatten"],
                            pair["lexicon"]["placebo"])
        ],
        name="the word list sees the flatten drop in coverage too",
        positive_verdict="LEXICON_SEES", null_verdict="LEXICON_DOES_NOT_SEE",
    )

    drops = [
        float(pair["drops"][PRIMARY_READING]["drop_flatten"]) for pair in pairs
        if pair["drops"][PRIMARY_READING]["drop_flatten"] is not None
    ]
    median_drop = statistics.median(drops) if drops else 0.0
    misalign = [
        float(pair["misalignment_rate_flatten"]) for pair in pairs
        if pair["misalignment_rate_flatten"] is not None
    ]
    median_misalign = statistics.median(misalign) if misalign else 0.0
    if not drops:
        refusal = "NOT_APPLICABLE"
    elif median_misalign >= 0.5 * median_drop:
        refusal = "VOID"
    else:
        refusal = "READABLE"
    return {
        "pairs_certified": len(pairs),
        "primary": {"reading": PRIMARY_READING, **primary},
        "secondary": {"reading": SECONDARY_READING, **secondary},
        "multiplicity": family,
        "against_noise_floor": against_noise,
        "descriptive": {
            "note": ("everything in this block is descriptive and carries no multiplicity "
                     "correction; the declared family is `primary` and `secondary` above"),
            "prose_paragraphs_only": prose_only,
            "internal_control_system_voice": control,
            "lexicon_sees_the_damage": lexicon_sees,
            "all_statistics_vs_placebo": {
                name: against_placebo(name) for name in SCALAR_STATISTICS
            },
        },
        "median_drop_primary": round(median_drop, 6),
        "median_misalignment_rate": round(median_misalign, 6),
        "refusal_state": {
            "rule": ("VOID if the median misalignment rate over the subset is at least half the "
                     "median coverage drop -- both unitless shares, so the comparison is in one "
                     "unit. An effect the instrument's own noise could manufacture is not an "
                     "effect."),
            "verdict": refusal,
        },
        "hygiene_on_revisions": flatten_hygiene,
    }


def _system_voice_control(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    """The flatten arm's internal control, read on its own terms and not through the sign test.

    The revision contract copies protected spans byte-for-byte, so the system voice's
    contribution to coverage cannot be flattened and the pre-registered expectation is that it
    does not move. **The shared sign test cannot express that**: a zero difference leaves the
    denominator by design, so a control that moved on nothing at all would read INSUFFICIENT_N,
    the exact opposite of what happened. So the outcomes are named here -- nothing fell is
    CONTROL_HOLDS, a significant fall is CONTROL_FAILS, anything between is CONTROL_UNDECIDED
    with its interval printed -- and EMPTY stays a fourth, for a subset with no protected span at
    all, which is most of RoyalRoad, whose system voice is not written in this project's
    typography. None of the four is a pass by silence.
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
        float(pair["system_voice_only"]["original"]) - float(pair["system_voice_only"]["flatten"])
        for pair in with_spans
        if pair["system_voice_only"]["original"] is not None
        and pair["system_voice_only"]["flatten"] is not None
    ]
    fell = sum(1 for delta in deltas if delta > 0)
    rose = sum(1 for delta in deltas if delta < 0)
    test = paired_reading(
        deltas,
        name="the system voice's contribution to coverage falls too, which the contract forbids",
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
        "unchanged": len(deltas) - fell - rose,
        "sign_test": test,
        "equivalence_bound": median_ci(deltas),
    }


# --------------------------------------------------------------------------------- the price


def run_price(args: argparse.Namespace) -> dict[str, Any]:
    """A declared pricing batch, and it writes a price rather than a census.

    The handoff's rule: dry-run, then ten live calls, then **report the projected cost before the
    main arm runs**. Two things make this an arm of its own rather than a truncated census. It
    writes to its own file, because a partial census committed under the census's name is the
    silent-cap failure in a different costume. And it draws units **spread across the word-count
    range** rather than from the front, because the price of one call is dominated by what the
    model writes about a chapter and that scales with the chapter -- here more sharply than for
    the comic census, since the answer is one entry per paragraph rather than a list of beats.

    The calls land in the base arm's own cache, so nothing here is bought twice: that arm replays
    every one of them for free.

    S79.1 in the cost direction. No figure from the comic census projects this run; the
    projection is a least-squares fit of measured equivalent price against chapter length, on
    these calls, on this transport, this week.
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

    elicitor = _elicitor(args, base_arm(args.substrate))
    jobs = [(unit, unit["text"], 0) for unit in picked]
    with elicitor:
        rows, usages = _sweep(elicitor, jobs, arm="price", dry_run=args.dry_run,
                              workers=elicitor.max_workers,
                              quote=args.substrate != "royalroad")
    # The alignment fields are here because the pricing batch is also the first look at whether
    # the instrument works at all, and it earned that role the expensive way: the first batch
    # found three defects in the echo contract and one in the locator (see
    # ECHO_DEFECTS_FOUND_AT_PRICING). A price with no misalignment rate beside it would price a
    # census nobody had checked could be read.
    priced = [
        {"unit_id": unit["unit_id"], "words": unit["words"],
         "paragraphs": row["paragraphs"],
         "usd": round(float((usage or {}).get("equivalent_usd") or 0.0), 6),
         "output_tokens": int((usage or {}).get("output") or 0),
         "aligned": row["aligned"],
         "misaligned": row["misaligned"],
         "misalignment_rate": row["misalignment_rate"],
         "echo_exactly_four": row["echo_exactly_four"],
         "unparseable": row["unparseable"],
         "coverage": row["scalars"].get("coverage")}
        for unit, usage, row in zip(picked, usages, rows, strict=True)
    ]
    readable = [row for row in priced if not row["unparseable"]]
    fit = _fit_cost(priced)
    return _envelope(args, "price", {
        "model": args.model or PANEL_MODEL,
        "sampled": priced,
        "alignment_vs_length": {
            "spearman_misalignment_vs_paragraphs": spearman(
                [float(row["paragraphs"]) for row in readable],
                [float(row["misalignment_rate"] or 0.0) for row in readable],
            ),
            "unparseable_calls": sum(1 for row in priced if row["unparseable"]),
            "misalignment_rate": describe(
                [float(row["misalignment_rate"] or 0.0) for row in readable]
            ) if readable else {"n": 0},
            "note": ("a positive rank correlation means the locator drifts on longer chapters, "
                     "which would make every census statistic length-censored; it is measured "
                     "here rather than discovered after the census"),
        },
        "fit": fit,
        "projection": _project(fit, units, args),
        "exclusions": ledger,
        "hygiene": hygiene(rows),
        "spend": spend_of(usages),
        **_tail(elicitor),
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
    estimated quantity is the price of one call. The flatten arm's revisions are **not** projected
    from this fit and say so instead of carrying a number: they run on a different model at a
    different tier, and their output is a whole chapter rather than a list of labels.
    """
    intercept = fit.get("intercept_usd")
    slope = fit.get("slope_usd_per_1k_words")
    if intercept is None or slope is None:
        return {"projected": None, "because": "fewer than two priced calls"}

    def cost(rows: list[dict[str, Any]]) -> float:
        return round(
            sum(max(intercept + slope * unit["words"] / 1000.0, 0.0) for unit in rows), 2
        )

    by_id = {unit["unit_id"]: unit for unit in units}
    plan: dict[str, Any] = {}
    if args.substrate == "royalroad":
        plan["census"] = {"calls": len(units), "usd": cost(units)}
    else:
        chapters = [unit for unit in units if unit.get("cohort") == "own_chapter"]
        scenes = [unit for unit in units if unit.get("cohort") == "own_scene"]
        plan["own_chapters"] = {
            "calls": OWN_DRAWS * len(chapters),
            "usd": round(OWN_DRAWS * cost(chapters), 2),
        }
        plan["own_scenes"] = {
            "calls": OWN_SCENE_DRAWS * len(scenes),
            "usd": round(OWN_SCENE_DRAWS * cost(scenes), 2),
            "units": len(scenes),
            "note": ("secondary colour at scene grain, and the larger half of this substrate's "
                     "bill. `--no-scenes` runs the chapter arm alone; the count is printed here "
                     "so dropping it is a decision somebody made rather than a cap that crept"),
        }
    base_path = result_path(args.substrate, base_arm(args.substrate), bool(args.dry_run))
    if base_path.is_file():
        base = json.loads(base_path.read_text(encoding="utf-8"))
        noise = [by_id[uid] for uid in noise_subset(base) if uid in by_id]
        flat = [by_id[uid] for uid in flatten_subset(base) if uid in by_id]
        if args.substrate == "royalroad":
            plan["repeat"] = {"calls": len(noise), "usd": cost(noise)}
        plan["sham"] = {"calls": len(noise), "usd": cost(noise)}
        plan["flatten_locator_calls"] = {"calls": 2 * len(flat), "usd": cost(flat + flat)}
        plan["flatten_revisions"] = {
            "calls": 2 * len(flat),
            "usd": None,
            "because": ("a whole-chapter revision on the writer tier is a different price and is "
                        "not projected from a locator fit; it is measured on its own first calls"),
        }
    else:
        plan["note"] = ("the base arm has not run, so the repeat, sham and flatten subsets do "
                        "not exist yet and only the base leg is projected")
    plan["total_projected_usd"] = round(
        sum(float(entry["usd"]) for entry in plan.values()
            if isinstance(entry, dict) and isinstance(entry.get("usd"), int | float)), 2
    )
    plan["excludes"] = ("the flatten arm's revisions on the writer tier, which carry no number "
                        "here by design")
    return plan


# --------------------------------------------------------------------------------- the report

#: How wide a length-matched comparison band is, as a fraction of the own chapter's word count.
#: `comic_beats.LENGTH_BAND`'s value for its reason: wide enough to keep an n worth quoting at a
#: 245-chapter draw, narrow enough that the matched population is not the whole population
#: wearing a label.
LENGTH_BAND = 0.30


def _cohort_table(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Every scalar statistic by era cohort, plus the reading that killed `tricolon_rate`.

    The era control is not a footnote here: if `human_pre_llm` and `declared_ai_2025` separate on
    a statistic further than `undeclared_2025` does from either, the statistic is reading the year
    and not the register (BRIEF S2). `separation` prints the three gaps so the comparison is on
    the page rather than in a sentence about it.
    """
    by_cohort: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_cohort.setdefault(str(row["cohort"]), []).append(row)

    def column(members: list[dict[str, Any]], name: str) -> list[float]:
        return [
            float(row["scalars"][name]) for row in members
            if row["scalars"].get(name) is not None
        ]

    table = {
        cohort: {
            name: describe(column(members, name)) for name in SCALAR_STATISTICS
        }
        for cohort, members in sorted(by_cohort.items())
    }
    separation: dict[str, Any] = {}
    for name in SCALAR_STATISTICS:
        means = {
            cohort: table[cohort][name].get("mean") for cohort in table
            if table[cohort][name].get("n")
        }
        if len(means) < 3 or any(value is None for value in means.values()):
            separation[name] = {"verdict": "INSUFFICIENT_N", "means": means}
            continue
        human = float(means.get("human_pre_llm", 0.0))
        undeclared = float(means.get("undeclared_2025", 0.0))
        declared = float(means.get("declared_ai_2025", 0.0))
        era_gap = abs(human - declared)
        within = max(abs(human - undeclared), abs(undeclared - declared))
        separation[name] = {
            "means": means,
            "human_vs_declared_ai": round(era_gap, 6),
            "largest_gap_involving_undeclared": round(within, 6),
            "verdict": "READS_THE_YEAR" if era_gap > within else "NOT_AN_AUTHORSHIP_SPLIT",
            "note": ("READS_THE_YEAR means the declared-AI split is wider than any split "
                     "involving the undeclared 2025 cohort, which is the shape that killed "
                     "`tricolon_rate`; it is a warning about the statistic, never a claim about "
                     "authorship"),
        }
    return {"by_cohort": table, "era_control": separation}


def _mean_position_profile(rows: list[dict[str, Any]]) -> list[dict[str, float]]:
    """The population's mean wave: kind share by decile, averaged over units.

    Averaged over UNITS rather than pooled over words, so one 6,000-word chapter does not carry
    three times the vote of a 2,000-word one. That is a choice and it is stated: a word-pooled
    profile is a different quantity and this module does not print both.
    """
    profiles = [
        row["trajectory"]["position_profile"] for row in rows
        if row["trajectory"].get("position_profile")
    ]
    if not profiles:
        return []
    return [
        {
            kind: round(statistics.fmean([profile[index].get(kind, 0.0) for profile in profiles]),
                        4)
            for kind in KINDS
        }
        for index in range(POSITION_BINS)
    ]


def _end_state_mix(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = dict.fromkeys(KINDS, 0)
    for row in rows:
        state = row["trajectory"].get("end_state")
        if state:
            counts[str(state)] = counts.get(str(state), 0) + 1
    total = sum(counts.values())
    return {
        "counts": counts,
        "share": {kind: round(value / total, 4) for kind, value in counts.items()}
        if total else {},
        "units": total,
        "note": ("reported with no bar. Naming a hook SHAPE from this is S104.4's gated mining "
                 "property and is out of scope, exactly as `chapter_endings.py` records"),
    }


def _lexicon_reading(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Whether a free word list reproduces the model's series, and by how much.

    Two comparisons, both within-chapter so nothing is confounded by chapter length. The
    correlation is between the model's windowed non-`none` indicator and the word list's windowed
    arousal, on the same word grid. The agreement is statistic by statistic.
    """
    correlations: list[float] = []
    agreements: dict[str, list[float]] = {name: [] for name in SCALAR_STATISTICS}
    match_rates: list[float] = []
    for row in rows:
        lex = row.get("lexicon") or {}
        match_rates.append(float(lex.get("match_rate") or 0.0))
        model_labels: list[str | None] = [entry["kind"] for entry in row["series"]]
        words = [int(entry["words"]) for entry in row["series"]]
        arousal = [float(value) for value in lex.get("arousal", [])]
        if len(arousal) != len(words):
            continue
        model_windows = windowed_series(model_labels, words)
        lex_windows = _windowed_mean(arousal, words)
        # Both series are one entry per window over the same word grid, so they line up by
        # index; the windows the model could not label are dropped from BOTH sides rather than
        # from one, which is the alignment bug a shorter series would have hidden.
        usable = [
            index for index in range(min(len(model_windows), len(lex_windows)))
            if model_windows[index] is not GAP
        ]
        if len(usable) >= 3:
            value = spearman(
                [0.0 if model_windows[index] == "none" else 1.0 for index in usable],
                [lex_windows[index] for index in usable],
            )
            if value is not None:
                correlations.append(value)
        for name in SCALAR_STATISTICS:
            model_value = row["scalars"].get(name)
            lex_value = scalars(lex.get("trajectory") or {}).get(name)
            if model_value is not None and lex_value is not None:
                agreements[name].append(float(model_value) - float(lex_value))
    median_r = statistics.median(correlations) if correlations else None
    return {
        "provenance": LEXICON_PROVENANCE,
        "band": LEXICON_REDUNDANCY_BAND,
        "units": len(rows),
        "within_chapter_spearman": describe(correlations) if correlations else {"n": 0},
        "median_within_chapter_spearman": round(median_r, 4) if median_r is not None else None,
        "word_match_rate": describe(match_rates) if match_rates else {"n": 0},
        "model_minus_lexicon": {
            name: describe(values) if values else {"n": 0}
            for name, values in agreements.items()
        },
        "coarsening": LEXICON_COARSENING,
        "verdict": (
            "INSUFFICIENT_N" if median_r is None
            else "ABOVE_BAND" if median_r >= LEXICON_REDUNDANCY_BAND
            else "BELOW_BAND"
        ),
        "note": ("ABOVE_BAND is only half of REDUNDANT_WITH_LEXICON: the other half is the word "
                 "list seeing the flatten drop, which is read in Q3's flatten block. BELOW_BAND "
                 "is the weakest outcome this arm can produce, because the list is in-module "
                 "rather than published and a weak list biases the reading that way."),
    }


def _windowed_mean(
    values: list[float], words: list[int], window: int = TURN_WINDOW_WORDS
) -> list[float]:
    """A per-paragraph quantity read on the same fixed word grid the label series uses."""
    total = sum(words)
    if total <= 0:
        return []
    series: list[float] = []
    for start in range(0, total, window):
        stop = min(start + window, total)
        weighted = 0.0
        seen = 0
        offset = 0
        for value, count in zip(values, words, strict=True):
            low, high = offset, offset + count
            offset = high
            overlap = min(high, stop) - max(low, start)
            if overlap > 0:
                weighted += value * overlap
                seen += overlap
        series.append(weighted / seen if seen else 0.0)
    return series


def _granularity_residual(
    rows: list[dict[str, Any]], population: dict[str, list[float]]
) -> dict[str, Any]:
    """How much of each statistic is the writer's paragraphing rather than the writing.

    **The confound this design's own grid creates.** The unit of labelling is the paragraph, so a
    chapter written in many short paragraphs hands the model more and smaller decisions than one
    written in a few long ones. Coverage is a share of WORDS and is partly protected by that;
    turn rate and run length are not protected at all, since both are counted over runs of
    paragraphs. Our own published chapters run 19 to 34 words a paragraph against a RoyalRoad
    draw that runs wider, so this is measured rather than assumed away before any placement is
    read.

    Reported for every statistic, with no bar and no correction applied: a correlation here does
    not invalidate a placement, it says which part of a placement a length-matched comparison has
    to control for.
    """
    lengths = [
        float(row["words"]) / max(int(row["paragraphs"]), 1) for row in rows
    ]
    return {
        "mean_words_per_paragraph": describe(lengths) if lengths else {"n": 0},
        "spearman_vs_statistic": {
            name: spearman(lengths, population[name])
            for name in SCALAR_STATISTICS
            if len(population[name]) == len(rows)
        },
        "note": ("the paragraph is the unit of labelling, so a chapter written in short "
                 "paragraphs hands the model more and smaller decisions. Coverage is a share of "
                 "words and is partly protected; turn rate and run length are counted over runs "
                 "of paragraphs and are not. No correction is applied and none is implied"),
    }


def run_report(args: argparse.Namespace) -> dict[str, Any]:
    """Merge the arms into the numbers `affect-trajectory-results.md` quotes. Spends nothing."""
    dry = bool(args.dry_run)
    rr = load_result("royalroad", "census", dry)
    rr_rows = scoreable(rr)
    local_path = result_path("local", "own", dry)
    local = load_result("local", "own", dry) if local_path.is_file() else None

    population: dict[str, list[float]] = {
        name: [
            float(row["scalars"][name]) for row in rr_rows
            if row["scalars"].get(name) is not None
        ]
        for name in SCALAR_STATISTICS
    }
    q1 = {
        "n": len(rr_rows),
        "pooled": {name: describe(values) for name, values in population.items()},
        **_cohort_table(rr_rows),
        "mean_position_profile": _mean_position_profile(rr_rows),
        "mean_position_profile_by_cohort": {
            cohort: _mean_position_profile(
                [row for row in rr_rows if str(row["cohort"]) == cohort]
            )
            for cohort in sorted({str(row["cohort"]) for row in rr_rows})
        },
        "end_state": _end_state_mix(rr_rows),
        "words": describe([float(row["words"]) for row in rr_rows]),
        "paragraphs": describe([float(row["paragraphs"]) for row in rr_rows]),
        "words_per_paragraph": describe([
            float(row["words"]) / max(int(row["paragraphs"]), 1) for row in rr_rows
        ]),
        "length_residual": {
            name: spearman([float(row["words"]) for row in rr_rows], population[name])
            for name in SCALAR_STATISTICS
            if len(population[name]) == len(rr_rows)
        },
        "granularity_residual": _granularity_residual(rr_rows, population),
        "hygiene": rr["hygiene"],
        "familiarity_confound": (
            "RoyalRoad text may be memorised by the locator (BRIEF S2 Pass 6). This baseline "
            "carries that term and our own chapters do not; the two are never pooled and every "
            "percentile below is read with the term named."
        ),
    }

    q2: dict[str, Any] = {"verdict": "NOT_RUN"}
    if local is not None:
        local_rows = scoreable(local)
        chapters = _by_unit([row for row in local_rows if row["cohort"] == "own_chapter"])
        scenes = _by_unit([row for row in local_rows if row["cohort"] == "own_scene"])
        q2 = {
            "chapters": [
                _placement(unit_id, draws, rr_rows, population)
                for unit_id, draws in sorted(chapters.items())
            ],
            "scenes": {
                "units": len(scenes),
                "note": ("secondary colour only: a scene is internal structure and the unit a "
                         "reader receives is the chapter. Never pooled with the chapter rows."),
                "per_unit": {
                    unit_id: unit_summary(draws) for unit_id, draws in sorted(scenes.items())
                },
                "summary": {
                    name: describe([
                        float(unit_summary(draws)[name]["median"])
                        for draws in scenes.values()
                        if unit_summary(draws)[name]["median"] is not None
                    ])
                    for name in SCALAR_STATISTICS
                } if scenes else {},
            },
            "within_unit": local["within_unit"],
            "hygiene": local["hygiene"],
        }

    q3 = {
        substrate: _q3(substrate, dry)
        for substrate in ("royalroad", "local")
    }
    q3["lexicon"] = {
        "royalroad": _lexicon_reading(rr_rows),
        "local": _lexicon_reading(
            [row for row in scoreable(local) if row["cohort"] == "own_chapter"]
        ) if local is not None else {"verdict": "NOT_RUN"},
    }

    spend: dict[str, Any] = {}
    total = 0.0
    for substrate in ("royalroad", "local"):
        for arm in ("census", "own", "repeat", "sham", "flatten", "price"):
            path = result_path(substrate, arm, dry)
            if not path.is_file():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            usd = float((payload.get("spend") or {}).get("equivalent_usd") or 0.0)
            spend[f"{substrate}/{arm}"] = round(usd, 4)
            total += usd
        # The flatten arm's own `spend` covers its locator calls and not the revisions that
        # produced the text they read: those go through `writer_states.Generator`, on a different
        # model, into a different cache. Counting only the locator would report a fraction of
        # what the arm cost.
        generations = DERIVED / f"affect-trajectory-{substrate}-flatten-gen.jsonl"
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
            spend[f"{substrate}/flatten_revisions"] = round(spent, 4)
            spend[f"{substrate}/flatten_revision_calls"] = calls
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


def _placement(
    unit_id: str, draws: list[dict[str, Any]], population_rows: list[dict[str, Any]],
    population: dict[str, list[float]],
) -> dict[str, Any]:
    """One own chapter placed in the population, with the interval its K draws give it.

    **No per-chapter number leaves here from a single draw.** The percentile is taken at the
    median of the draws and at the extremes of them, so the row shows where the chapter sits and
    how far a re-ask could move it -- which is the thing the comic census could only report after
    the fact, and only as a population number.
    """
    summary = unit_summary(draws)
    words = float(draws[0]["words"])
    low, high = words * (1 - LENGTH_BAND), words * (1 + LENGTH_BAND)
    matched = [row for row in population_rows if low <= row["words"] <= high]
    out: dict[str, Any] = {
        "unit_id": unit_id,
        "words": draws[0]["words"],
        "paragraphs": draws[0]["paragraphs"],
        "words_per_paragraph": round(
            draws[0]["words"] / max(int(draws[0]["paragraphs"]), 1), 2
        ),
        "draws": len(draws),
        "length_band_words": [round(low), round(high)],
        "length_matched_n": len(matched),
        "statistics": {},
    }
    for name in SCALAR_STATISTICS:
        entry = summary[name]
        matched_values = [
            float(row["scalars"][name]) for row in matched
            if row["scalars"].get(name) is not None
        ]
        out["statistics"][name] = {
            **entry,
            "percentile_pooled": percentile_of(float(entry["median"]), population[name])
            if entry["median"] is not None else None,
            "percentile_pooled_range": [
                percentile_of(float(entry["min"]), population[name]),
                percentile_of(float(entry["max"]), population[name]),
            ] if entry["min"] is not None else None,
            "percentile_length_matched": percentile_of(float(entry["median"]), matched_values)
            if entry["median"] is not None and matched_values else None,
        }
    return out


def _q3(substrate: str, dry: bool = False) -> dict[str, Any]:
    """Every control's number for one substrate, or the fact that an arm has not run."""
    out: dict[str, Any] = {}
    base = base_arm(substrate)
    base_path = result_path(substrate, base, dry)
    if not base_path.is_file():
        return {"verdict": "NOT_RUN", "because": f"the {base} arm has not run on {substrate}"}
    base_payload = json.loads(base_path.read_text(encoding="utf-8"))

    repeat_path = result_path(substrate, "repeat", dry)
    sham_path = result_path(substrate, "sham", dry)
    repeat = json.loads(repeat_path.read_text(encoding="utf-8")) if repeat_path.is_file() else None
    sham = json.loads(sham_path.read_text(encoding="utf-8")) if sham_path.is_file() else None

    if repeat is not None:
        out["repeat"] = repeat["summary"]
        out["reliability"] = _reliability_from_pairs(base_payload, repeat)
    elif substrate == "local":
        out["repeat"] = {
            "verdict": "BY_DESIGN_NOT_RUN",
            "because": (f"the `own` arm carries K={OWN_DRAWS} draws per chapter and its "
                        "within-unit spread is the noise floor on this substrate"),
        }
        out["reliability"] = base_payload.get("within_unit", {"verdict": "NOT_RUN"})
    else:
        out["repeat"] = {"verdict": "NOT_RUN"}
        out["reliability"] = {"verdict": "NOT_RUN"}

    out["sham"] = sham["summary"] if sham else {"verdict": "NOT_RUN"}
    if sham is not None:
        floor = _floor_map(substrate, base_payload, repeat)
        if floor:
            deltas = [
                float(pair["deltas"][PRIMARY_READING]["abs_delta"]) - floor[pair["unit_id"]]
                for pair in sham["pairs"]
                if pair["unit_id"] in floor
                and pair["deltas"][PRIMARY_READING]["abs_delta"] is not None
            ]
            out["sham_vs_noise"] = paired_reading(
                deltas,
                name="the layout sham moves coverage further than a re-ask does",
                positive_verdict="LAYOUT_SENSITIVE", null_verdict="INSIDE_NOISE",
            )
            out["sham_vs_noise"]["reading_note"] = (
                "INSIDE_NOISE is read only with the equivalence bound beside it (S101.1): the "
                "interval is the layout sensitivity this design could not exclude, in coverage."
            )
        else:
            out["sham_vs_noise"] = {
                "verdict": "NOT_RUN",
                "because": "no noise floor exists on this substrate yet",
            }
        out["sham_grid_losses"] = len(sham.get("grid_losses") or [])
    else:
        out["sham_vs_noise"] = {"verdict": "NOT_RUN"}

    flatten_path = result_path(substrate, "flatten", dry)
    if flatten_path.is_file():
        flatten = json.loads(flatten_path.read_text(encoding="utf-8"))
        out["flatten"] = flatten["readings"]
        out["flatten"]["uncertified"] = len(flatten["uncertified"])
        out["flatten"]["writer_model"] = flatten.get("writer_model")
        out["flatten"]["certificates"] = _certificate_summary(flatten)
    else:
        out["flatten"] = {"verdict": "NOT_RUN"}
    return out


def _floor_map(
    substrate: str, base_payload: dict[str, Any], repeat: dict[str, Any] | None
) -> dict[str, float]:
    """Each unit's own noise floor on the primary reading, from whichever arm measured it."""
    floor: dict[str, float] = {}
    if repeat is not None:
        for pair in repeat["pairs"]:
            value = pair["deltas"][PRIMARY_READING]["abs_delta"]
            if value is not None:
                floor[str(pair["unit_id"])] = float(value)
        return floor
    if substrate == "local":
        for unit_id, values in (base_payload.get("per_unit") or {}).items():
            entry = values.get(PRIMARY_READING) or {}
            if entry.get("n_draws", 0) >= 2 and entry.get("max") is not None:
                floor[str(unit_id)] = round(float(entry["max"]) - float(entry["min"]), 6)
    return floor


def _reliability_from_pairs(base: dict[str, Any], repeat: dict[str, Any]) -> dict[str, Any]:
    """How much of Q1's spread is between chapters and how much is the instrument.

    The `repeat` arm measures the sd of the difference between two draws on the same chapter,
    which is `sqrt(2)` times the sd of a single measurement's error, so the population's observed
    variance splits with no free parameters. It assumes the error is homoscedastic across
    chapters and independent between draws; neither is checked and both are stated rather than
    assumed silently. The reliability's square root is the ceiling on any correlation the measure
    could ever show with anything, which is the number a later programme should be told before it
    tries to relate this to a reader.
    """
    rows = scoreable(base)
    out: dict[str, Any] = {
        "assumes": ("error homoscedastic across chapters and independent between draws; neither "
                    "is checked here"),
        "note": ("draws_to_0.8 is Spearman-Brown: averaging k independent draws divides the "
                 "noise variance by k"),
    }
    kappas = [
        float(pair["paragraph_kappa"]) for pair in repeat["pairs"]
        if pair["paragraph_kappa"] is not None
    ]
    out["paragraph_kappa"] = describe(kappas) if kappas else {"n": 0}
    for name in SCALAR_STATISTICS:
        observed = [
            float(row["scalars"][name]) for row in rows if row["scalars"].get(name) is not None
        ]
        signed = [
            float(pair["deltas"][name]["signed_delta"]) for pair in repeat["pairs"]
            if pair["deltas"][name]["signed_delta"] is not None
        ]
        if len(observed) < 2 or len(signed) < 2:
            out[name] = {"verdict": "INSUFFICIENT_N"}
            continue
        sd_difference = statistics.pstdev(signed)
        sd_noise = sd_difference / math.sqrt(2.0)
        sd_observed = statistics.pstdev(observed)
        variance_true = sd_observed ** 2 - sd_noise ** 2
        reliable = variance_true / sd_observed ** 2 if sd_observed else None
        out[name] = {
            "repeat_pairs": len(signed),
            "sd_of_paired_difference": round(sd_difference, 6),
            "sd_single_measurement_noise": round(sd_noise, 6),
            "sd_population_observed": round(sd_observed, 6),
            "sd_population_implied_true": round(max(variance_true, 0.0) ** 0.5, 6),
            "reliability": round(reliable, 4) if reliable is not None else None,
            "correlation_ceiling": round(max(reliable, 0.0) ** 0.5, 4)
            if reliable is not None else None,
            "draws_to_0.8": (
                None if reliable is None or reliable <= 0 or reliable >= 0.8
                else math.ceil((0.8 * (1 - reliable)) / (reliable * (1 - 0.8)))
            ),
        }
    return out


def _certificate_summary(flatten: dict[str, Any]) -> dict[str, Any]:
    """What the revisions actually were, so a null cannot be blamed on a manipulation nobody
    checked. A flatten that changed nothing and a locator that cannot see are different
    findings."""
    rows = [pair["certificates"] for pair in flatten["pairs"]]
    if not rows:
        return {"pairs": 0}
    return {
        "pairs": len(rows),
        "flatten_similarity": describe([float(row["flatten"]["similarity"]) for row in rows]),
        "placebo_similarity": describe(
            [float(row["flatten_placebo"]["similarity"]) for row in rows]
        ),
        "flatten_word_growth_pct": describe(
            [float(row["flatten"]["word_growth_pct"]) for row in rows]
        ),
        "protected_spans_total": sum(int(row["flatten"]["protected_spans"]) for row in rows),
        "protected_spans_kept": sum(int(row["flatten"]["protected_kept"]) for row in rows),
        "grids_preserved": sum(
            1 for row in rows
            if row["flatten"]["paragraphs_before"] == row["flatten"]["paragraphs_after"]
        ),
    }


def _headline(q1: dict[str, Any], q2: dict[str, Any], q3: dict[str, Any]) -> dict[str, Any]:
    """One machine-readable sentence per question. The prose version lives in the results doc and
    is written from these fields rather than beside them."""
    coverage = q1["pooled"].get("coverage", {})
    turns = q1["pooled"].get("turn_rate_windowed_per_1k", {})
    pairing = q1["pooled"].get("pairing_rate_minus_null", {})
    chapters = q2.get("chapters") or []
    return {
        "q1": (
            f"Over {q1['n']} RoyalRoad LitRPG chapters, located coverage runs at a median of "
            f"{coverage.get('quantiles', {}).get('0.5')} of words under a non-`none` label "
            f"(mean {coverage.get('mean')}, p95 {coverage.get('quantiles', {}).get('0.95')}); "
            f"the windowed register turns {turns.get('quantiles', {}).get('0.5')} times per "
            f"1,000 words at the median; and observed set-up-to-release pairing sits "
            f"{pairing.get('mean')} above its own within-chapter permutation null on average."
        ),
        "q2": [
            f"{row['unit_id']}: coverage "
            f"{row['statistics']['coverage']['median']} over {row['draws']} draws "
            f"(range {row['statistics']['coverage']['min']}-"
            f"{row['statistics']['coverage']['max']}), "
            f"{row['statistics']['coverage']['percentile_pooled']}th percentile pooled, "
            f"{row['statistics']['coverage']['percentile_length_matched']}th among chapters of "
            f"comparable length (n={row['length_matched_n']})."
            for row in chapters
        ],
        "q3": {
            substrate: {
                "sham": (entry.get("sham_vs_noise") or {}).get("verdict"),
                "flatten_primary": (
                    (entry.get("flatten") or {}).get("primary", {}).get("verdict")
                ),
                "flatten_holm_any_clears": (
                    (entry.get("flatten") or {}).get("multiplicity", {}).get("any_clears")
                ),
                "flatten_refusal": (
                    (entry.get("flatten") or {}).get("refusal_state", {}).get("verdict")
                ),
            }
            for substrate, entry in q3.items() if substrate in ("royalroad", "local")
        },
        "lexicon": {
            substrate: (q3["lexicon"][substrate] or {}).get("verdict")
            for substrate in ("royalroad", "local")
        },
        "what_this_is_not": (
            "a quality claim. Coverage, turn rate and pairing are properties of REACHES. A "
            "chapter that turns more often is not better, a chapter that is 80% `none` is not "
            "worse, and whether any of it moves anybody is not measured here."
        ),
    }


# ------------------------------------------------------------------------------- the selftest

#: A synthetic chapter with a known label sequence: eight paragraphs, a protected system line,
#: a set-up run and a release close enough behind it to pair. Written here rather than drawn
#: from a corpus so the selftest costs nothing and asserts against a sequence somebody chose.
_FIXTURE = (
    "The gate would not hold past the third bell and everybody on the wall knew it.\n\n"
    "Something under the stone had been wrong since the thaw, and nobody would say what.\n\n"
    "**BREACH IMMINENT — 3 minutes**\n\n"
    "He counted the arrows twice and both counts came out short.\n\n"
    "Then the buttress took the weight, and the stone held, and the bell rang four.\n\n"
    "[STATUS] Wall Integrity 61%\n\n"
    "Marta laughed once, badly, and passed the flask along the line.\n\n"
    "The ledger said what it always said, in the same hand, in the same ink.\n"
)

_FIXTURE_LABELS = [
    "tension", "unease", "tension", "tension", "relief", "triumph", "ease", "none",
]


def _fixture_answer(labels: list[str], grid: list[str]) -> dict[str, Any]:
    return {
        "paragraphs": [
            {"n": index + 1, "kind": kind,
             "echo": " ".join(paragraph.split()[:ECHO_WORDS])}
            for index, (kind, paragraph) in enumerate(zip(labels, grid, strict=True))
        ]
    }


def selftest() -> int:
    """Schema shape, closed kinds, forbidden vocabulary, echo alignment, the statistics, the
    sham's grid survival, the permutation null, the arithmetic, and last the byte-freeze.

    Run before anything expensive, and re-run after every edit: the last check is what makes
    every committed number attributable to a particular instrument.
    """
    failures: list[str] = []

    def check(claim: str, ok: bool) -> None:
        if not ok:
            failures.append(claim)

    # -- the frozen asking
    check("ten kinds, no duplicates", len(KINDS) == 10 == len(set(KINDS)))
    check("`none` is one of them and is last", KINDS[-1] == "none")
    check("every kind has a definition", set(KIND_DEFINITIONS) == set(KINDS))
    check("the set-up and release kinds are kinds",
          set(SETUP_KINDS) <= set(KINDS) and set(RELEASE_KINDS) <= set(KINDS))
    check("no kind is both a set-up and a release",
          not set(SETUP_KINDS) & set(RELEASE_KINDS))
    check("`loss` is not counted as a release", "loss" not in RELEASE_KINDS)
    check("the schema's enum is the closed set",
          SCHEMA["properties"]["paragraphs"]["items"]["properties"]["kind"]["enum"]
          == list(KINDS))
    check("the schema is closed at both levels",
          SCHEMA["additionalProperties"] is False
          and SCHEMA["properties"]["paragraphs"]["items"]["additionalProperties"] is False)
    check("all three fields are required",
          SCHEMA["properties"]["paragraphs"]["items"]["required"] == ["n", "kind", "echo"])
    check("the number is an integer, so a renumbering cannot arrive as prose",
          SCHEMA["properties"]["paragraphs"]["items"]["properties"]["n"]["type"] == "integer")
    check("the schema has no intensity, score or rating field",
          not {"intensity", "score", "rating", "strength", "degree"}
          & set(SCHEMA["properties"]["paragraphs"]["items"]["properties"]))
    asked = "\n".join([
        SYSTEM, QUESTION_TEMPLATE, json.dumps(SCHEMA), json.dumps(KIND_DEFINITIONS),
    ]).lower()
    for word in FORBIDDEN_IN_ASKING:
        check(f"the asking carries no quality or effect vocabulary: {word!r}",
              not re.search(rf"\b{re.escape(word)}\b", asked))
    check("every kind is named in the system block", all(kind in SYSTEM for kind in KINDS))
    check("the echo length is stated in the asking", str(ECHO_WORDS) in SYSTEM)
    check("the question template carries the paragraph count", "{count}" in QUESTION_TEMPLATE)

    # -- echo alignment, on the fixture
    grid = grid_of(_FIXTURE)
    check("the fixture splits into the eight paragraphs its labels assume", len(grid) == 8)
    scored = align(grid, _fixture_answer(_FIXTURE_LABELS, grid))
    check("a clean answer aligns every paragraph", scored["aligned"] == 8)
    check("and misaligns none", scored["misaligned"] == 0)
    check("and the series is the sequence that was sent",
          [str(label) for label in scored["labels"]] == _FIXTURE_LABELS)
    check("the misalignment rate of a clean answer is zero", scored["misalignment_rate"] == 0.0)

    numbering = numbered(_FIXTURE)
    check("the render numbers every paragraph of the grid and no more",
          len(grid_of(numbering)) == len(grid)
          and numbering.startswith("[1] ") and "[8] " in numbering)
    check("and it keeps the separator convention the shown text used",
          numbered("a b c\nd e f").count("\n") == 1)

    misnumbered = _fixture_answer(_FIXTURE_LABELS, grid)
    misnumbered["paragraphs"][3]["n"] = 99
    off = align(grid, misnumbered)
    check("an entry naming a paragraph that does not exist is a misalignment",
          off["bad_index"] == 1 and off["misaligned"] == 1 and off["labels"][3] is None)
    twice = _fixture_answer(_FIXTURE_LABELS, grid)
    twice["paragraphs"][4] = dict(twice["paragraphs"][3])
    repeated = align(grid, twice)
    check("a number used twice keeps the first entry and drops the second",
          repeated["duplicate_index"] == 1 and repeated["labels"][3] == "tension"
          and repeated["labels"][4] is None)
    scrambled = _fixture_answer(_FIXTURE_LABELS, grid)
    scrambled["paragraphs"].reverse()
    reversed_answer = align(grid, scrambled)
    check("a list returned out of order still seats every label by its own number",
          reversed_answer["aligned"] == 8
          and [str(label) for label in reversed_answer["labels"]] == _FIXTURE_LABELS)
    check("and the disorder is reported rather than forgiven",
          reversed_answer["out_of_order"] == 8)

    shifted = _fixture_answer(_FIXTURE_LABELS, grid)
    shifted["paragraphs"][3]["echo"] = "a wholly invented opening"
    drift = align(grid, shifted)
    check("an echo that is not its paragraph's is a misalignment", drift["misaligned"] == 1)
    check("and its label leaves the series", drift["labels"][3] is None)
    check("and the paragraphs around it are untouched",
          drift["labels"][2] == "tension" and drift["labels"][4] == "relief")

    curly = _fixture_answer(_FIXTURE_LABELS, grid)
    curly["paragraphs"][2]["echo"] = "**BREACH IMMINENT \u2013 3"
    check("a retyped dash is dropped rather than forgiven, so the stat line still matches",
          align(grid, curly)["aligned"] == 8)

    short = _fixture_answer(_FIXTURE_LABELS, grid)
    short["paragraphs"] = short["paragraphs"][:5]
    trimmed = align(grid, short)
    check("a short list leaves paragraphs unlabelled rather than misaligned",
          trimmed["missing"] == 3 and trimmed["misaligned"] == 0)
    check("and the series is not padded",
          all(label is None for label in trimmed["labels"][5:]))
    long_answer = _fixture_answer(_FIXTURE_LABELS, grid)
    long_answer["paragraphs"] = long_answer["paragraphs"] + [
        {"n": 9, "kind": "none", "echo": "extra entry here"}
    ]
    check("a long list reports its extras", align(grid, long_answer)["extra"] == 1)
    check("and the extra entry is a bad index, not a label anywhere",
          align(grid, long_answer)["bad_index"] == 1)
    bad = _fixture_answer(_FIXTURE_LABELS, grid)
    bad["paragraphs"][0]["kind"] = "not_a_kind"
    check("a kind outside the closed set is dropped and counted",
          align(grid, bad)["bad_kind"] == 1 and align(grid, bad)["labels"][0] is None)
    three = _fixture_answer(_FIXTURE_LABELS, grid)
    three["paragraphs"][0]["echo"] = "The gate would"
    check("a three-word echo of the right paragraph aligns", align(grid, three)["aligned"] == 8)
    check("and is not counted as an exactly-four echo",
          align(grid, three)["echo_exactly_four"]
          == align(grid, _fixture_answer(_FIXTURE_LABELS, grid))["echo_exactly_four"] - 1)
    longer = _fixture_answer(_FIXTURE_LABELS, grid)
    longer["paragraphs"][0]["echo"] = "The gate would not hold past"
    check("an echo longer than four words still identifies its paragraph",
          align(grid, longer)["aligned"] == 8)
    two = _fixture_answer(_FIXTURE_LABELS, grid)
    two["paragraphs"][0]["echo"] = "The gate"
    check("a two-word echo of a long paragraph is unverifiable and is dropped",
          align(grid, two)["misaligned"] == 1)
    quoted = _fixture_answer(_FIXTURE_LABELS, grid)
    quoted["paragraphs"][2]["echo"] = "BREACH IMMINENT 3 minutes"
    check("punctuation is dropped rather than forgiven, so a stripped stat line matches",
          align(grid, quoted)["aligned"] == 8)
    check("a contraction is one word on both sides of the comparison",
          echo_tokens("I don't know") == ["i", "dont", "know"])
    check("so an echo that dropped the apostrophe still identifies its paragraph",
          echo_matches('"I don\'t know," he said.', "I dont know he") is True)
    check("and one that kept it does too",
          echo_matches('"I don\'t know," he said.', "I don't know he") is True)
    check("words run together are not an identification and are not forgiven",
          echo_matches("The gate would not hold", "Thegatewouldnot") is False)
    check("a short paragraph is identified by the whole of itself",
          echo_matches("Right.", "Right") is True)
    check("and not by something that is not its opening",
          echo_matches("Right.", "Wrong") is False)
    check("an echo naming a different paragraph is a misalignment, not a re-seat",
          echo_matches(grid[4], " ".join(grid[5].split()[:4])) is False)
    check("an unparseable answer is unparseable and not an all-`none` series",
          align(grid, None)["unparseable"] is True)
    check("and its series is all gaps rather than all `none`",
          all(label is None for label in align(grid, None)["labels"]))

    # -- the sham cannot re-cut the grid, which is what makes the arm comparable
    from ablate import rewhitespace

    reflowed = rewhitespace(_FIXTURE, 1.0)
    check("whitespace reflow changes no word", normalise(reflowed) == normalise(_FIXTURE))
    check("whitespace reflow leaves the paragraph count alone",
          len(grid_of(reflowed)) == len(grid))
    check("whitespace reflow leaves every echo alone",
          sham_grid_survives(_FIXTURE, reflowed))
    check("an answer scored on the reflowed text aligns the same way",
          align(grid_of(reflowed),
                _fixture_answer(_FIXTURE_LABELS, grid))["aligned"] == 8)

    # -- the trajectory statistics, on a sequence somebody chose
    words = [len(paragraph.split()) for paragraph in grid]
    stats = trajectory(list(_FIXTURE_LABELS), words)
    check("coverage counts every word not under `none`",
          stats["coverage"] is not None and 0.8 < stats["coverage"] < 1.0)
    check("a series with one `none` paragraph is not fully covered", stats["coverage"] < 1.0)
    check("every adjacent pair of differing kinds is a turn, and the repeated one is not",
          stats["turns_paragraph"] == 6)
    check("runs collapse the adjacent tension pair",
          stats["runs"] == 7 and _runs(list(_FIXTURE_LABELS), words)[0]["paragraphs"] == 1)
    check("the release is paired with the set-up behind it",
          stats["pairing"]["paired_releases"] == 2 and stats["pairing"]["pairing_rate"] == 1.0)
    check("and every set-up is released", stats["pairing"]["unreleased_setup_share"] == 0.0)
    check("the end state is the tail's register, not the last paragraph's label",
          stats["end_state"] == "tension" and _FIXTURE_LABELS[-1] == "none")
    check("and it is the last paragraph's kind once that paragraph fills the tail",
          trajectory(["tension", "tension", "relief"],
                     [100, 100, END_STATE_WORDS + 50])["end_state"] == "relief")
    check("entropy is positive on a mixed series", stats["label_entropy_bits"] > 1.0)
    check("entropy is zero on a series of one kind",
          trajectory(["none"] * 8, words)["label_entropy_bits"] == 0.0)
    check("an all-`none` series has zero coverage",
          trajectory(["none"] * 8, words)["coverage"] == 0.0)
    check("a gap leaves the denominators",
          trajectory([None, *list(_FIXTURE_LABELS[1:])], words)["words_aligned"]
          == sum(words) - words[0])
    check("a gap breaks a run rather than being spanned",
          len(_runs(["tension", None, "tension"], [10, 10, 10])) == 2)
    check("a series with no aligned paragraph reports nulls rather than zeros",
          trajectory([None] * 8, words)["coverage"] is None)

    lonely = trajectory(["tension", "none", "none", "none", "none", "none", "none", "none"],
                        [100] * 8)
    check("a set-up with no release anywhere is unreleased",
          lonely["pairing"]["unreleased_setup_share"] == 1.0)
    check("and a chapter with no release has no pairing rate to report",
          lonely["pairing"]["pairing_rate"] is None)
    far = trajectory(
        ["tension", "none", "none", "none", "none", "relief"], [100, 200, 200, 200, 200, 100]
    )
    check("a release beyond the pairing window is not paired",
          far["pairing"]["pairing_rate"] == 0.0)

    # -- the windowed series
    check("the windowed series covers the chapter's words",
          len(windowed_series(["tension"] * 4, [100] * 4)) == 2)
    check("a window with no aligned word is a gap in place, not a shorter series",
          windowed_series([None, "tension"], [TURN_WINDOW_WORDS, TURN_WINDOW_WORDS])
          == [None, "tension"])
    check("and no turn is counted across that gap",
          trajectory(["relief", None, "tension"], [TURN_WINDOW_WORDS] * 3)["turns_windowed"] == 0)
    check("a uniform series never turns",
          trajectory(["tension"] * 8, [100] * 8)["turns_windowed"] == 0)
    check("an alternating series turns in the windowed view too",
          trajectory(["tension", "relief"] * 4,
                     [TURN_WINDOW_WORDS] * 8)["turns_windowed"] == 7)

    # -- the permutation null
    ordered_null = _permutation_null(list(_FIXTURE_LABELS), words, seed="fixture", shuffles=200)
    check("the null is computed on a real sequence", ordered_null["pairing_rate"] is not None)
    check("the null is deterministic given a seed",
          _permutation_null(list(_FIXTURE_LABELS), words, seed="fixture", shuffles=200)
          == ordered_null)
    check("a different seed gives a different draw, not the same one",
          _permutation_null(list(_FIXTURE_LABELS), words, seed="other", shuffles=200)
          != ordered_null)
    flat_labels = ["none"] * 8
    check("a series with no set-up and no release has no null to report",
          _permutation_null(flat_labels, words, seed="flat", shuffles=50)["pairing_rate"] is None)
    shuffled_stats = trajectory(list(_FIXTURE_LABELS), words)
    contrast = scalars(shuffled_stats, ordered_null)
    check("the wave reading is the observed minus its own null",
          contrast["pairing_rate_minus_null"] is not None
          and abs(
              contrast["pairing_rate_minus_null"]
              - (shuffled_stats["pairing"]["pairing_rate"] - ordered_null["pairing_rate"])
          ) < 1e-6)

    # -- the lexicon
    values = lexicon_series(grid)
    check("the word list labels every paragraph", len(values["labels"]) == len(grid))
    check("the word list is deterministic", lexicon_series(grid) == values)
    check("a paragraph with no listed word is `none`",
          lexicon_kind(lexicon_value("the ledger said what it always said")) == "none")
    check("a threat paragraph reads negative and activated",
          lexicon_kind(lexicon_value("terror and danger and blood")) == "tension")
    check("a rest paragraph reads positive and unactivated",
          lexicon_kind(lexicon_value("calm peace rest safe warm")) == "ease")
    check("the coarsening cannot invent a kind outside the closed set",
          set(LEXICON_COARSENING.values()) <= set(KINDS))
    check("the suffix fold finds an inflected form",
          lexicon_value("screamed")["matched"] == 1)

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
          paired_reading([0.5, -0.5] * 4, name="t", positive_verdict="A",
                         null_verdict="B")["equivalence_bound"]["n"] == 8)
    check("the median interval brackets the median",
          median_ci([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])["lo"] <= 4.0
          <= median_ci([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])["hi"])
    check("rank correlation finds a monotone relation",
          spearman([1.0, 2.0, 3.0, 4.0], [1.0, 2.0, 3.0, 4.0]) == 1.0)
    check("rank correlation finds its inverse",
          spearman([1.0, 2.0, 3.0, 4.0], [4.0, 3.0, 2.0, 1.0]) == -1.0)

    # -- Holm, which is the comic census's declared defect closed
    strict = holm([("primary", 0.02), ("secondary", 0.04)])
    check("Holm holds the smaller p to alpha/2", strict["steps"][0]["clears"] is True)
    check("and lets the second through at alpha once the first cleared",
          strict["steps"][1]["clears"] is True)
    check("Holm stops the family when the smallest p misses its threshold",
          holm([("primary", 0.04), ("secondary", 0.045)])["any_clears"] is False)
    check("the declared family is exactly two",
          holm([("a", 0.01), ("b", 0.02)])["family_size"] == 2)

    # -- kappa and ICC
    check("identical label series agree perfectly",
          cohens_kappa(["tension", "relief", "none"], ["tension", "relief", "none"]) == 1.0)
    check("a series both draws called one kind is undefined rather than zero",
          cohens_kappa(["none", "none"], ["none", "none"]) is None)
    check("disagreement on every paragraph is at or below zero",
          (cohens_kappa(["tension", "relief"], ["relief", "tension"]) or 0.0) <= 0.0)
    check("a gap in either draw drops that paragraph from kappa",
          cohens_kappa(["tension", None, "relief"], ["tension", "loss", "relief"]) == 1.0)
    identical = icc([[1.0, 1.0], [5.0, 5.0], [9.0, 9.0]])
    check("perfectly repeatable draws give ICC 1", identical["icc"] == 1.0)
    noisy = icc([[1.0, 9.0], [5.0, 5.0], [9.0, 1.0]])
    check("draws that disagree more than the units do give ICC 0", noisy["icc"] == 0.0)
    check("and an ICC of zero has no finite draw count that fixes it",
          noisy["draws_to_0.8"] is None)
    check("one unit is not a reliability", icc([[1.0, 2.0]])["verdict"] == "INSUFFICIENT_N")

    # -- the flatten readings, on synthetic pairs. The dry run cannot reach these: its generator
    # returns the chapter unchanged, which is the correct null and certifies nothing, so without
    # this block the reading arithmetic would run for the first time on paid data.
    def _pair(drop: float, placebo: float, spread: float | None, spans: int = 1,
              sv_before: float = 0.2, sv_after: float = 0.2,
              misalign: float = 0.01) -> dict[str, Any]:
        return {
            "unit_id": f"u{drop}{placebo}{spread}{sv_after}",
            "protected_spans": spans,
            "repeat_spread": spread,
            "misalignment_rate_flatten": misalign,
            "prose_only": {"original": 0.8, "flatten": 0.8 - drop, "placebo": 0.8 - placebo},
            "system_voice_only": {"original": sv_before, "flatten": sv_after,
                                  "placebo": sv_before},
            "lexicon": {"original": 0.5, "flatten": 0.5, "placebo": 0.5},
            "drops": {
                name: {
                    "original": 0.8, "flatten": 0.8 - drop, "placebo": 0.8 - placebo,
                    "drop_flatten": drop, "drop_placebo": placebo,
                }
                for name in SCALAR_STATISTICS
            },
        }

    clean = [_pair(0.20, 0.0, 0.02) for _ in range(6)]
    reading = flatten_readings(clean, {"misalignment_rate": 0.01})
    check("a clean flatten reads SEES on the primary",
          reading["primary"]["verdict"] == "SEES")
    check("and clears Holm", reading["multiplicity"]["any_clears"] is True)
    check("and reads SEES against the noise floor",
          reading["against_noise_floor"]["verdict"] == "SEES")
    check("an untouched system voice holds the internal control",
          reading["descriptive"]["internal_control_system_voice"]["verdict"] == "CONTROL_HOLDS")
    check("a word list that saw nothing reads LEXICON_DOES_NOT_SEE",
          reading["descriptive"]["lexicon_sees_the_damage"]["verdict"] == "INSUFFICIENT_N")
    check("a clean flatten is readable", reading["refusal_state"]["verdict"] == "READABLE")
    noisy_reading = flatten_readings(
        [_pair(0.20, 0.0, 0.02, misalign=0.4) for _ in range(6)], {"misalignment_rate": 0.4}
    )
    check("misalignment at half the drop voids the reading",
          noisy_reading["refusal_state"]["verdict"] == "VOID")
    flat_reading = flatten_readings(
        [_pair(0.05, 0.05, 0.02) for _ in range(6)], {"misalignment_rate": 0.0}
    )
    check("a flatten that ties its placebo on every pair decides nothing, and says so",
          flat_reading["primary"]["verdict"] == "INSUFFICIENT_N")
    check("and the tie publishes an interval of zero rather than a silence",
          flat_reading["primary"]["equivalence_bound"]["lo"] == 0.0
          and flat_reading["primary"]["equivalence_bound"]["hi"] == 0.0)
    backwards = flatten_readings(
        [_pair(0.02, 0.20, 0.02) for _ in range(6)], {"misalignment_rate": 0.0}
    )
    check("a placebo that removes more than the flatten reads DOES_NOT_SEE",
          backwards["primary"]["verdict"] == "DOES_NOT_SEE")
    sunk = flatten_readings(
        [_pair(0.20, 0.0, 0.02, sv_before=0.2, sv_after=0.0) for _ in range(6)],
        {"misalignment_rate": 0.01},
    )
    check("a system voice that fell with the prose fails the internal control",
          sunk["descriptive"]["internal_control_system_voice"]["verdict"] == "CONTROL_FAILS")
    nospans = flatten_readings(
        [_pair(0.20, 0.0, 0.02, spans=0) for _ in range(6)], {"misalignment_rate": 0.01}
    )
    check("no protected span means the control is EMPTY, not a pass",
          nospans["descriptive"]["internal_control_system_voice"]["verdict"] == "EMPTY")
    check("no certified pair means the refusal state does not apply",
          flatten_readings([], {})["refusal_state"]["verdict"] == "NOT_APPLICABLE")
    check("no noise floor means the floor reading says so, not a verdict",
          flatten_readings([_pair(0.2, 0.0, None) for _ in range(6)],
                           {"misalignment_rate": 0.01})["against_noise_floor"]["verdict"]
          == "NOT_RUN")

    # -- certification
    check("an unchanged revision certifies",
          certify("a b c\n\nd e f", "a b c\n\nd e f")["certified"] is True)
    check("a wholesale rewrite does not certify",
          certify("a b c d e f g h", "z y x w v u t s")["certified"] is False)
    check("a revision that grew past the bound does not certify",
          certify("a b c d e f g h", "a b c d e f g h i j k")["certified"] is False)
    check("a mangled protected span does not certify",
          certify("**BREACH IMMINENT \u2014 3 minutes**\n\nHe left.",
                  "**BREACH IMMINENT, 3 minutes**\n\nHe left.")["certified"] is False)
    check("a revision that re-cut the paragraph grid does not certify",
          certify("a b c\n\nd e f", "a b c d e f")["certified"] is False)

    # -- the window
    check("the window is the comic census's window, so the two share a population",
          (MIN_CHAPTER_WORDS, MAX_CHAPTER_WORDS) == (800, 6000))

    # -- the freeze
    check("every frozen function still exists to be frozen",
          all(hasattr(sys.modules[__name__], name) for name in FROZEN_FUNCTIONS))
    check("the statistics' source is inside the registration digest",
          statistics_source_digest() in json.dumps(
              {"probe": statistics_source_digest()}, sort_keys=True))
    computed = registration_digest()
    if FROZEN_DIGEST == "PENDING":
        failures.append(
            f"FROZEN_DIGEST is still PENDING. Set it to {computed} before the first paid call; "
            "an unfrozen instrument can be reworded between arms and nothing would notice."
        )
    else:
        check(f"the frozen block still digests to {FROZEN_DIGEST} (computed {computed})",
              computed == FROZEN_DIGEST)

    for message in failures:
        print(f"  FAIL {message}", file=sys.stderr)
    print(f"selftest: {'PASS' if not failures else str(len(failures)) + ' FAILURES'} "
          f"(registration digest {computed})", file=sys.stderr)
    return 1 if failures else 0


# ------------------------------------------------------------------ the acceptance artifact


def acceptance(unit_id: str, dry: bool = False) -> int:
    """Print one own chapter's labelled series in full, as the results document carries it.

    **A transparency artifact, not a solicited read.** Nobody is asked to rate, label or confirm
    anything; the point is that a reader who disagrees with a label can see exactly what they
    are disagreeing with, paragraph by paragraph, against the page. It is generated from the
    committed result file rather than transcribed into the document by hand, because a table
    somebody retyped is a second instrument nobody validated.

    Own prose only, and the guard is structural: RoyalRoad echoes are stored as hashes and there
    is nothing here to print for them, which is the leak rule holding rather than being obeyed.
    """
    own = load_result("local", "own", dry)
    draws = [row for row in scoreable(own) if str(row["unit_id"]) == unit_id]
    if not draws:
        available = sorted({str(row["unit_id"]) for row in scoreable(own)})
        raise SystemExit(
            f"{unit_id} is not in the own arm's scoreable rows. Available: "
            + ", ".join(available)
        )
    draws.sort(key=lambda row: int(row["sample"]))
    lexicon = draws[0]["lexicon"]
    print(f"### {unit_id} - {draws[0]['words']} words, {draws[0]['paragraphs']} paragraphs, "
          f"{len(draws)} draws")
    print()
    header = "| # | echo | " + " | ".join(f"draw {row['sample']}" for row in draws)
    print(header + " | lexicon | valence | arousal |")
    print("|--:|---|" + "---|" * len(draws) + "---|--:|--:|")
    for index in range(draws[0]["paragraphs"]):
        echo = draws[0]["series"][index].get("echo") or "(misaligned in draw 0)"
        cells = [
            (f"`{row['series'][index]['kind']}`" if row["series"][index]["kind"] else "-")
            for row in draws
        ]
        print(
            f"| {index} | {echo} | " + " | ".join(cells)
            + f" | `{lexicon['labels'][index]}` | {lexicon['valence'][index]} "
            f"| {lexicon['arousal'][index]} |"
        )
    print()
    print("`-` is a paragraph whose entry misaligned in that draw: its label is dropped from "
          "the series and its words leave every denominator, never padded over.")
    return 0


# ------------------------------------------------------------------------------------- main


ARMS = ("census", "own", "repeat", "sham", "flatten", "report")
RUNNERS = {
    "census": run_census,
    "own": run_own,
    "repeat": run_repeat,
    "sham": run_sham,
    "flatten": run_flatten,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--substrate", choices=("royalroad", "local", "report"))
    parser.add_argument("--arm", choices=ARMS, default=None)
    parser.add_argument("--dump", action="store_true",
                        help="MirrorBench interpreter only: write the census draw to derived/")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--acceptance", default=None, metavar="UNIT_ID",
                        help="print one own chapter's labelled series in full and stop; the "
                             "results document's acceptance artifact, generated not transcribed")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--price", type=int, default=0, metavar="N",
                        help="price the arm from N calls spread across the length range and "
                             "stop; writes a price file, never a census")
    parser.add_argument("--yes", action="store_true", help="required for a run that spends")
    parser.add_argument("--model", default=None,
                        help="the locator; defaults to elicit.PANEL_MODEL")
    parser.add_argument("--writer-model", default=None,
                        help="the flatten arm's reviser; defaults to writer_states.WRITER_MODEL")
    parser.add_argument("--transport", default="cli", choices=("cli", "sdk", "ollama"))
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--cache", default=None, help="override the per-arm raw JSONL")
    parser.add_argument("--out", default=None, help="override the results JSON")
    parser.add_argument("--library", default=str(REPO / "book-library"),
                        help="the published shelf; */chapters/Chapter*.txt beneath it")
    parser.add_argument("--databases", default=None,
                        help="semicolon-separated book databases for the scene-grain arm; "
                             "defaults to every one on this machine")
    parser.add_argument("--scene-min-words", type=int, default=200,
                        help="corpus_io.generated_scenes' own default")
    parser.add_argument("--no-scenes", action="store_true",
                        help="run the chapter arm alone. The scene arm is secondary colour and "
                             "the larger half of this substrate's bill; dropping it is a "
                             "decision, and the units dropped are printed either way")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.dump:
        return dump()
    if args.acceptance:
        return acceptance(args.acceptance, bool(args.dry_run))
    if not args.substrate and not args.arm:
        parser.error("--substrate is required (royalroad, local, or report)")
    if args.substrate == "report" or args.arm == "report":
        args.substrate = args.substrate or "report"
        args.arm = "report"
    if not args.arm:
        args.arm = base_arm(args.substrate)
    if selftest():
        print("refusing to run: the selftest failed", file=sys.stderr)
        return 1

    if args.arm == "report":
        payload = run_report(args)
        out = Path(args.out) if args.out else RESULTS / (
            "affect-trajectory-report" + ("-dry" if args.dry_run else "") + ".json"
        )
        out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8",
                       newline="\n")
        print(json.dumps(payload["reading"], indent=2))
        print(f"\nwrote {out}", file=sys.stderr)
        return 0

    if not args.dry_run and not args.yes:
        print("this run spends; pass --yes", file=sys.stderr)
        return 2

    if args.price:
        payload = run_price(args)
        out = Path(args.out) if args.out else RESULTS / (
            f"affect-trajectory-{args.substrate}-price{'-dry' if args.dry_run else ''}.json"
        )
        out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8",
                       newline="\n")
        print(json.dumps({"fit": payload["fit"], "projection": payload["projection"],
                          "measured_usd": payload["spend"]["equivalent_usd"]}, indent=2))
        print(f"\nwrote {out}", file=sys.stderr)
        return 0

    from force_remote import AlreadyRunning, SingleRun

    # The dry suffix is in the lock name, not only in the file names. A dry run issues no call,
    # writes to its own `-dry` files and cannot touch a paid arm's results, so a paid arm holding
    # the lock must not stop somebody checking the arithmetic beside it -- which is exactly when
    # somebody wants to.
    lock = RESULTS / (
        f".affect-trajectory-{args.substrate}-{args.arm}"
        f"{'-dry' if args.dry_run else ''}.pid"
    )
    print(f"  results -> {result_path(args.substrate, args.arm, bool(args.dry_run)).name}",
          file=sys.stderr, flush=True)
    started = time.time()
    try:
        with SingleRun(lock, f"affect_trajectory {args.substrate}/{args.arm}"):
            payload = RUNNERS[args.arm](args)
    except AlreadyRunning as error:
        print(str(error), file=sys.stderr)
        return 3
    payload["seconds"] = round(time.time() - started, 1)

    out = Path(args.out) if args.out else result_path(
        args.substrate, args.arm, bool(args.dry_run)
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8",
                   newline="\n")
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
        print(f"  kappa {json.dumps(payload['summary']['paragraph_kappa'], sort_keys=True)}")
        print("  |delta| coverage "
              f"{json.dumps(payload['summary']['abs_delta']['coverage'], sort_keys=True)}")
    if payload.get("within_unit"):
        print("  within-unit kappa "
              f"{json.dumps(payload['within_unit']['paragraph_kappa']['summary'], sort_keys=True)}")
        print("  coverage ICC "
              f"{json.dumps(payload['within_unit']['statistic_icc']['coverage'], sort_keys=True)}")
    if payload.get("readings"):
        headline = {
            key: value for key, value in payload['readings'].items()
            if key != 'descriptive'
        }
        print(f"  readings {json.dumps(headline, indent=2, sort_keys=True)}")
    rows = [row for row in (payload.get("rows") or []) if not row["refused"]]
    values = [
        float(row["scalars"]["coverage"]) for row in rows
        if row["scalars"].get("coverage") is not None
    ]
    if values:
        print(f"  coverage {json.dumps(describe(values), sort_keys=True)}")


if __name__ == "__main__":
    raise SystemExit(main())
