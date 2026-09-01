"""The code-only per-chapter battery, in one place so two runners cannot drift apart.

Every function here was **lifted verbatim** from `plan/agent-impact/scripts/draw_battery.py`,
which computed the numbers `plan/agent-impact/draw-battery.md` publishes. That runner now
imports this module instead of defining them, so there is exactly one definition of each
quantity and `plan/agent-impact/scripts/battery.json` still validates byte-for-byte. A second
caller — `scorecard.py`, the per-draw scorecard — reads the same functions.

**No new metric is minted here.** Every counter is imported from where it already lives:

| quantity | reused from |
| --- | --- |
| words | `len(text.split())`, the pipeline's own idiom (`application/export.py`) |
| inference-gloss tiers | `register_census.gloss_counts` |
| proper nouns | `register_census.proper_nouns` |
| progression events | `progression_cadence.measure` (v0 and v2) |
| number families | `number_context.measure` (v0 and v2) |
| em dashes | `voice.exhibition_census` |
| sentences | `voice.sentences`, `voice._WORD` |
| `[STATUS]` lines | `statusline.parse_status_line` |
| machinery names in prose | `schema_words.named_in` |

Two quantities have no instrument in the repo and carry a flag in their own key name:

- **`chains_REIMPLEMENTED`.** §180.1 ran its census with "a crude script that is not kept", so
  there is no §180 counter to reuse. The definition below is transcribed from §180.1's own
  sentence — sentences split on terminal punctuation, and per sentence a count of coordinated
  joins (commas plus free-standing *and*) — and the bound is §180.3's fourth action. Because
  the original script is gone, **these levels are not comparable with §180.1's published
  distribution**; only columns computed by this module are comparable with each other.
- **`proper_nouns_NOT_CAST`.** §175 shipped a prompt bound and `domain/staging.py` says in its
  own docstring that no count of drafted prose was built. The proper-noun counter reused here
  is a strict superset of named characters — it also catches places, institutions and system
  names — so it is reported as proper nouns and never as cast.

**No model reads anything here.** Regex and arithmetic over text, end to end. No corpus is
opened, so RS1 is untouched, and nothing under `src/litharness/` imports this file.
"""

from __future__ import annotations

import re
import statistics
import sys
from itertools import pairwise
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))

import number_context  # noqa: E402
import progression_cadence  # noqa: E402
import register_census  # noqa: E402

from litharness.application import statusline  # noqa: E402
from litharness.domain import draft as draft_mod  # noqa: E402
from litharness.domain import schema_words, voice  # noqa: E402

__all__ = [
    "battery",
    "chain_profile",
    "prose_only",
    "sentence_profile",
    "status_profile",
]

# --------------------------------------------------------------------------- prose vs system

#: The published chapter file interleaves prose with the book's own `[STATUS]` furniture and a
#: `* * *` scene separator. Three of the counters below are contaminated by that if it is left
#: in, each in a way that was measured rather than assumed:
#:
#: - **em dashes (large).** The `[STATUS]` line's subject separator IS U+2014, so a chapter with
#:   two prints scores 2 before a single dash appears in a sentence -- and three draws whose
#:   prose carries none scored 2 on the raw file. `draft.strip_em_dash` protects exactly these
#:   lines in production, so the production boundary is the right one here.
#: - **proper nouns (large).** Sheet labels are capitalised mid-line, so
#:   `register_census.proper_nouns` reads `Carried`, `Hearing`, `Piecing` as names: p15-d4 falls
#:   from 31 distinct to 25 once the furniture is dropped, p16 from 21 to 18.
#: - **sentence length (small, and measured rather than assumed).** A status line carries no
#:   terminal punctuation, so `voice.sentences` folds it into its neighbour. On this shelf that
#:   moves the sentence COUNT by at most one (p15-d1 140 -> 139, p15-d3 141 -> 140) and changes
#:   **no** chapter's longest sentence. p15-d2's 98-word maximum is a real prose sentence and
#:   not an artifact of the furniture, which is the check that corrected this note.
#:
#: The boundary is `draft._SYSTEM_LINE`, the pipeline's own definition of a system line, so no
#: second rule is invented here.
_SEPARATOR = "* * *"


def prose_only(text: str) -> str:
    """The chapter with its system lines and scene separator dropped, nothing else changed."""
    return "\n".join(
        line
        for line in text.splitlines()
        if not draft_mod._SYSTEM_LINE.match(line.strip()) and line.strip() != _SEPARATOR
    )


# --------------------------------------------------------------------------- the two flagged

#: §180.1's stated object: "commas plus free-standing *and*". Free-standing means the word, not
#: the substring, so `\band\b` and never `handle`.
_JOIN = re.compile(r",|\band\b", re.IGNORECASE)
#: §180.3's bound: "a fourth thing happens after three already have".
_CHAIN_BOUND = 4
#: The draw battery's own second sentence bound, kept separate from the chain bound.
_LONG_SENTENCE = 30


def chain_profile(text: str) -> dict[str, Any]:
    """§180.1's census definition, REIMPLEMENTED because its script was not kept.

    Splitting is `voice.sentences`, which is the repo's one shipped splitter, rather than a
    second one written here -- so only the per-sentence join count is new.
    """
    sents = voice.sentences(text)
    joins = [len(_JOIN.findall(s)) for s in sents]
    n = len(joins)
    return {
        "sentences": n,
        "joins_mean": round(statistics.fmean(joins), 3) if joins else None,
        "joins_max": max(joins) if joins else None,
        "chained_4plus": sum(1 for j in joins if j >= _CHAIN_BOUND),
        "chained_4plus_share": round(sum(1 for j in joins if j >= _CHAIN_BOUND) / n, 4)
        if n
        else None,
        "chained_6plus": sum(1 for j in joins if j >= 6),
    }


def sentence_profile(text: str) -> dict[str, Any]:
    """Mean, median and the over-30 share, over `voice.sentences` and `voice._WORD`."""
    sents = voice.sentences(text)
    lengths = [len(voice._WORD.findall(s)) for s in sents]
    lengths = [n for n in lengths if n]
    if not lengths:
        return {"sentences": 0}
    over = sum(1 for n in lengths if n > _LONG_SENTENCE)
    return {
        "sentences": len(lengths),
        "words_mean": round(statistics.fmean(lengths), 2),
        "words_median": round(statistics.median(lengths), 1),
        "words_max": max(lengths),
        "over_30": over,
        "over_30_share": round(over / len(lengths), 4),
    }


# --------------------------------------------------------------------------- status lines


def status_profile(text: str) -> dict[str, Any]:
    """Every `[STATUS]` line, and whether any subject's own number changes across them.

    `statusline.parse_status_line` is the renderer's shape-only parser -- it does not require
    the book's declared labels or numeric values, which is what makes it the one that runs on
    bare prose. A cell is "moved" when the same subject's same-labelled cell differs between
    two consecutive prints. Comparison is on the raw cell string, so `2/4` -> `3/4` counts and
    no arithmetic is attempted on a paired cell.
    """
    lines = [
        parsed
        for raw in text.splitlines()
        if (parsed := statusline.parse_status_line(raw.strip())) is not None
    ]
    subjects = sorted({line.subject for line in lines})
    moved: list[str] = []
    for subject in subjects:
        prints = [dict(line.cells) for line in lines if line.subject == subject]
        for before, after in pairwise(prints):
            for label, value in after.items():
                if label in before and before[label] != value:
                    moved.append(f"{subject}:{label} {before[label]}->{value}")
    return {
        "status_lines": len(lines),
        "subjects": subjects,
        # §169's defect is a subject rendered as the records hold it rather than as the book
        # displays it. Snake_case is the instance §169 was written on (`tam_cawl`); an
        # all-lowercase bare id is the same defect without an underscore (`mira`), so the test
        # is "carries no capital", not "contains an underscore".
        "raw_id_subject": [s for s in subjects if s == s.lower()],
        "cells_moved": moved,
        "any_number_moved": bool(moved),
        "lines": [f"[STATUS] {line.subject} — " + " | ".join(
            f"{label} {value}" for label, value in line.cells
        ) for line in lines],
    }


# --------------------------------------------------------------------------- the battery


def battery(text: str) -> dict[str, Any]:
    """Every code-only measure this project has, for one chapter's text.

    **Two instruments are read at TWO VERSIONS each, and both versions are reported.** The
    first battery found `progression_cadence` and `number_context`'s system half blind to this
    project's own `[STATUS]` page contract, so their v0 rows are zeros that mean *unmeasured*.
    The answer shipped as a second registered version rather than an edit (stage-0 §189):
    `cadence_v2` and `numbers_v2` carry their own registration digests, the v0 keys beside them
    are unchanged and still the only ones any market number may be read against, and nothing
    pools the two. A v2 count is not a better book; it is the same page seen by a detector that
    can read one of its lines.
    """
    prose = prose_only(text)
    words = len(text.split())
    prose_words = len(prose.split())

    def per_1k(n: int) -> float | None:
        return round(n * 1000 / prose_words, 3) if prose_words else None

    gloss = register_census.gloss_counts(prose)
    cadence = progression_cadence.measure(
        text,
        fiction_id=0,
        chapter_id=0,
        litrpg=True,
        quarantined=False,
        cohort=None,
    )
    cadence_v2 = progression_cadence.measure(
        text,
        fiction_id=0,
        chapter_id=0,
        litrpg=True,
        quarantined=False,
        cohort=None,
        version="v2",
    )
    numbers = number_context.measure(prose)
    numbers_v2 = number_context.measure(text, version="v2")
    em_file = voice.exhibition_census(text)["em_dash"]
    em = voice.exhibition_census(prose)["em_dash"]
    nouns = register_census.proper_nouns(prose)

    return {
        "words": words,
        "prose_words": prose_words,
        "separator_and_furniture_words": words - prose_words,
        # register_census -- the gloss tiers. The friction half is NOT here: it needs a corpus
        # frequency table (`friction(text, table, total=...)`) and there is no per-chapter form.
        "gloss": {
            "a1": gloss["a1"],
            "a2": gloss["a2"],
            "tier_a": gloss["tier_a"],
            "tier_b": gloss["tier_b"],
            "tier_a_per_1k": per_1k(gloss["tier_a"]),
            "tier_b_per_1k": per_1k(gloss["tier_b"]),
        },
        # progression_cadence -- runs on one chapter; the gap statistics need >=2 and >=3 events
        # respectively and return None below that, which is the instrument declining, not a zero.
        "cadence": {
            "events": cadence.events,
            "per_1k": round(cadence.per_1k, 3),
            "first_event_words": cadence.first_event_words,
            "first_event_fraction": round(cadence.first_event_fraction, 4)
            if cadence.first_event_fraction is not None
            else None,
            "median_gap": cadence.median_gap,
            "gap_cv": round(cadence.gap_cv, 3) if cadence.gap_cv is not None else None,
            "by_family": cadence.by_family,
        },
        # number_context -- the system/mundane split, per 1k.
        "numbers": {
            "mentions": numbers.mentions,
            "mentions_per_1k": per_1k(numbers.mentions),
            "system_any": numbers.system_any,
            "system_per_1k": per_1k(numbers.system_any),
            "system_magnitude": numbers.by_family["system_magnitude"],
            "system_ordinal": numbers.by_family["system_ordinal"],
            "mundane_core": numbers.mundane_core,
            "mundane_per_1k": per_1k(numbers.mundane_core),
            "anchored": numbers.anchored,
            "system_share_of_anchored": round(numbers.system_share_of_anchored, 4)
            if numbers.system_share_of_anchored is not None
            else None,
            "furniture_lines": numbers.furniture_lines,
            "english_share": round(numbers.english_share, 3),
            "by_family": numbers.by_family,
        },
        "em_dash": {
            "in_file": em_file,
            "in_prose": em,
            "on_status_lines": em_file - em,
            "prose_per_1k": per_1k(em),
        },
        "sentences": sentence_profile(prose),
        "chains_REIMPLEMENTED": chain_profile(prose),
        "proper_nouns_NOT_CAST": {
            "distinct": len(nouns),
            "per_1k": per_1k(len(nouns)),
            "names": sorted(nouns),
        },
        "status": status_profile(text),
        "machinery_names_in_prose": list(schema_words.named_in(prose)),
        # Recorded per row so the zero is never read as "no furniture in this chapter". Both
        # market-derived detectors require a whole-line bracketed span (`_RE_BRACKETED`), an
        # angled span, or a COLON-separated stat line (`_RE_STATLINE`). The house format is
        # `[STATUS] Subject — Label N | Label N`, which is none of the three: the bracket
        # closes after STATUS and the columns carry no colon. So `is_furniture_line` is False
        # on every line of every draw, and the sheet's own values fall through to the ordinary
        # prose families -- which is why the numbers above are measured on `prose` instead.
        #
        # **`v2` is the answer to that row and it is a SECOND instrument, not a repair of the
        # first.** Both v0 blocks are byte-identical and every number published under their
        # digests still validates; v2 adds one line shape and a published mask. The v2 numbers
        # live in their own keys below and are never pooled with v0's.
        "furniture_detected_by_market_instruments": {
            "number_context": numbers.furniture_lines,
            "progression_cadence": sum(
                1 for line in text.splitlines() if progression_cadence._is_furniture(line)
            ),
            "number_context_v2": numbers_v2.furniture_lines,
            "progression_cadence_v2": sum(
                1
                for line in text.splitlines()
                if progression_cadence._is_furniture(line, version="v2")
            ),
            "actually_present": len(status_profile(text)["lines"]),
        },
        # progression_cadence.v2 -- the same counters over the same chapter, by a detector that
        # can see our page contract. A count moving from 0 to 2 here is the DETECTOR changing
        # and not the book: nothing about these chapters is different from the v0 rows above.
        "cadence_v2": {
            "registration_digest": progression_cadence.REGISTRATION_DIGEST_V2,
            "events": cadence_v2.events,
            "per_1k": round(cadence_v2.per_1k, 3),
            "first_event_words": cadence_v2.first_event_words,
            "first_event_fraction": round(cadence_v2.first_event_fraction, 4)
            if cadence_v2.first_event_fraction is not None
            else None,
            "median_gap": cadence_v2.median_gap,
            "gap_cv": round(cadence_v2.gap_cv, 3) if cadence_v2.gap_cv is not None else None,
            "by_family": cadence_v2.by_family,
        },
        # number_context.v2 -- run over the WHOLE file rather than over `prose`, which is the
        # point: under v2 a sheet's cells are system numbers by location, so they no longer
        # have to be deleted to stop them contaminating the mundane half.
        "numbers_v2": {
            "registration_digest": number_context.REGISTRATION_DIGEST_V2,
            "mentions": numbers_v2.mentions,
            "system_any": numbers_v2.system_any,
            "system_magnitude": numbers_v2.by_family["system_magnitude"],
            "system_ordinal": numbers_v2.by_family["system_ordinal"],
            "mundane_core": numbers_v2.mundane_core,
            "mundane_per_1k": per_1k(numbers_v2.mundane_core),
            "object_count": numbers_v2.by_family["object_count"],
            "furniture_lines": numbers_v2.furniture_lines,
            "system_share_of_anchored": round(numbers_v2.system_share_of_anchored, 4)
            if numbers_v2.system_share_of_anchored is not None
            else None,
            "by_family": numbers_v2.by_family,
            # The v0-on-prose reading of the same page, for the one comparison that IS legible:
            # both are our own chapters, and the mundane half should barely move because v2
            # takes cells OUT of the prose families rather than adding to them.
            "mundane_core_v0_on_prose": numbers.mundane_core,
        },
        # Does the research-side mask agree with the pipeline's own definition of a system
        # line? `draft._SYSTEM_LINE` cannot be imported by a research module -- those run under
        # an interpreter where the package is absent -- so v2 transcribes the shape instead,
        # and this row is the check that the transcription did not drift.
        "v2_mask_matches_pipeline": progression_cadence.prose_only(text, version="v2")
        == prose_only(text),
    }
