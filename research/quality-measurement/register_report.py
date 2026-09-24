"""An inert register report printed beside the chapter-one gates: it describes, decides nothing,
and sets no bar.

**Why it exists.** The operator's read 20 (`plan/reader-read-20.md`) named three things the gate
reads let through. The listing "reads like a list of facts". A rent payment sits in the first
paragraph of chapter one. And the chapter says "surviving tread". Every gate item passed
because nothing put a market number beside the coordinator's read, and the registered draw's
word lists had no money word at all (`restored-directions-draw-20260922/run.py`, ADMIN and
FRAME). This module puts our text beside the shelf's distribution. It is a description and
only a description:

- **No row decides anything.** There is no pass, fail, verdict, flag, colour or threshold. It
  exits 0 whatever the text holds, and exits 2 only when an input file is missing (or, for
  `--build-baseline`, when the box lock is not held for it). The gate items stay the
  coordinator's.
- **Every counter is reused except three word lists.** Sentences come from `overview.sentences`
  and `coordinator_density` from overview.py. Chapter prose comes from
  `chapter_measures.prose_only` with paragraphs normalised by `exemplars._paragraphed`, on
  both sides. Tells use `tells.density` and never its ceilings. Sentence shape comes from
  `chapter_measures.sentence_profile`, dialogue and paragraph length from
  `authorship_tells.features`, and proper nouns and friction from `register_census`. The
  three new lists are `MECHANIC_TERMS`, `HOUSEHOLD_MONEY` and `LOOT_CURRENCY`. The ADMIN and
  FRAME lists are copied verbatim from the registered runner, and a test pins the copy.
- **Families are never pooled.** Household money, loot currency, admin and frame are each
  reported separately. For each one the report gives the rate per thousand words, the count
  in the first `FIRST_WINDOW` words, and the number of words before its first hit. Read 20's
  rent line is a position fact: the whole-chapter rate sits inside the market range, while
  the first hit comes 32 words in.
- **Nothing here reaches generation.** The module lives under research/, so the RS1 test
  (`tests/test_corpus_leak_audit.py`) forbids any package import of it. The committed
  baseline holds sorted numbers only: no text, no title and no id. The word-keyed frequency
  table stays in the gitignored `derived/` folder. No row measures a hook or whether a reader
  reads on. Reappraisal's opening proper-noun count sat at the 68.5th percentile and did not
  discriminate the defect a reader named (`opening-counters-results.md`).

The `--draw DIR` provenance trace (read 20's item 3) is ours-only. Each scene-writer call a
draw recorded under `calls/` gives a scene label. For each label, every content word and every
two- or three-word sequence on the page is listed with the sections of the recorded request
that hold it: writer, instructions, world rules, premise, plan, cast and facts, hidden,
prior prose, scene brief. When no section holds it, its source is `none`, meaning the model
supplied it. This is a locating aid for a person. A word's source is not a verdict about the
word, and the rarest-words list is never a locator (§156.3, §156.5).

    uv run python research/quality-measurement/register_report.py \\
        --listing L.txt --chapter C.md [--draw DIR] [--json OUT]

The market half is built once, under the box lock, by `--build-baseline`. It is a sustained
CPU and memory job over the backtest's `fictions-v0.json`, so it never runs beside a model arm
(CLAUDE.md, "Share the box"), and it refuses to start unless `runs/box.lock/holder` begins
`register-baseline`:

    mkdir runs/box.lock && echo "register-baseline: <who>, <when>" > runs/box.lock/holder
    uv run python research/quality-measurement/register_report.py --build-baseline
    rm -f runs/box.lock/holder && rmdir runs/box.lock
"""

from __future__ import annotations

import argparse
import bisect
import codecs
import hashlib
import importlib.util
import json
import math
import re
import statistics
import sys
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))

import authorship_tells  # noqa: E402
import chapter_measures  # noqa: E402
import register_census  # noqa: E402

from litharness.application import exemplars, overview  # noqa: E402
from litharness.domain import tells, voice  # noqa: E402

HEADER = "register report: describes; decides nothing; no bar (stage-0 §61)"
SCOPE = (
    "Register distance from the shelf only. No row measures a hook or whether a reader reads "
    "on, and no row is a gate item."
)

BASELINE = HERE / "results" / "register-baseline.json"
FREQUENCY_TABLE = HERE / "derived" / "register-freq.json"
RIVALS = HERE / "derived" / "rivals-all.json"
FICTIONS = REPO / "research" / "sim-readership-backtest" / "fictions-v0.json"
BACKTEST_CORPUS = REPO / "research" / "sim-readership-backtest" / "corpus.py"
#: `--build-baseline` runs only while this holder names it (RUNBOOK.md, "guard and go").
BOX_LOCK_HOLDER = REPO / "runs" / "box.lock" / "holder"
BASELINE_HOLDER_PREFIX = "register-baseline"

#: Words at the start of a chapter that a position row looks at.
FIRST_WINDOW = 150
#: A sentence this short is one step of `short_run`: read 20's listing ran seven in a row.
SHORT_SENTENCE_WORDS = 12
#: Market populations below this size print "k of n" instead of percentiles.
SMALL_N = 20
#: Base chapters per fiction that feed the bigram table: a deterministic subsample, because a
#: full bigram table over the base does not fit in memory beside everything else.
BIGRAM_BASE_PER_FICTION = 5
#: `register_census`'s own default floors, stated here so the table is pruned to match them.
UNIGRAM_FLOOR_PER_MILLION = 1.0
BIGRAM_FLOOR_PER_MILLION = 0.1

# --------------------------------------------------------------------------- word lists

#: Game-mechanics terms, frozen before any number was read against them; the list's digest is
#: part of `registration_digest`. A term is counted, never judged: a listing may need several.
MECHANIC_TERMS: dict[str, str] = {
    "system": r"\bsystems?\b",
    "skill": r"\bskills?\b",
    "rank": r"\branks?\b",
    "level": r"\blevels?\b",
    "class": r"\bclass(?:es)?\b",
    "stat": r"\bstats?\b",
    "tier": r"\btiers?\b",
    "interface": r"\binterfaces?\b",
    "status": r"\bstatus\b",
    "xp": r"\bxp\b",
    "ability": r"\babilit(?:y|ies)\b",
    "quest": r"\bquests?\b",
    "attribute": r"\battributes?\b",
    "mana": r"\bmana\b",
}

#: Household money: the rent line read 20 named. Observation only, never a prompt word list
#: (§127, §187). The ADMIN and FRAME words (debt, account, fee, tax, owe) are not repeated here,
#: so the four families stay disjoint.
HOUSEHOLD_MONEY: dict[str, str] = {
    "rent": r"\brent(?:s|ed|al|ing)?\b",
    "landlord": r"\blandlords?\b",
    "bill": r"\bbills?\b",
    "wage": r"\bwages?\b",
    "salary": r"\bsalar(?:y|ies)\b",
    "payment": r"\bpayments?\b",
    "pay": r"\b(?:pay|pays|paid|paying)\b",
    "invoice": r"\binvoices?\b",
    "receipt": r"\breceipts?\b",
    "mortgage": r"\bmortgages?\b",
    "loan": r"\bloans?\b",
    "overdue": r"\boverdue\b",
    "deposit": r"\bdeposits?\b",
    "money": r"\bmoney\b",
    "cash": r"\bcash\b",
    "afford": r"\bafford(?:s|ed|able)?\b",
}

#: The prize the genre hands out, kept apart from household money on purpose.
LOOT_CURRENCY: dict[str, str] = {
    "coin": r"\bcoins?\b",
    "gold": r"\bgold\b",
    "silver": r"\bsilver\b",
    "copper": r"\bcopper\b",
    "credit": r"\bcredits?\b",
}

#: Copied verbatim from research/quality-measurement/restored-directions-draw-20260922/run.py;
#: `tests/test_register_report.py` pins the copy against that frozen runner.
ADMIN_LEXICON: dict[str, str] = {
    "ledger": r"\bledgers?\b",
    "debt": r"\bdebt(?:s|ors?)?\b",
    "claim": r"\bclaim(?:s|ed|ing|ants?)?\b",
    "tenancy": r"\btenan(?:cy|cies|ts?)\b",
    "contract": r"\bcontract(?:s|ed|ual)?\b",
    "permission": r"\bpermissions?\b",
    "certify": r"\bcertif(?:y|ies|ied|ying|icates?|ication)\b",
    "inspect": r"\binspect(?:s|ed|ing|ions?|ors?)?\b",
    "compensation": r"\bcompensat(?:e|es|ed|ing|ion)\b",
    "account": r"\baccount(?:s|ed|ing|ants?)?\b",
}
FRAME_LEXICON: dict[str, str] = {
    "court": r"\bcourts?\b",
    "licence": r"\blicen[cs](?:e|es|ed|ing)\b",
    "permit": r"\bpermits?\b",
    "registry": r"\bregist(?:ry|ries|rars?|ration|ered)\b",
    "clerk": r"\bclerks?\b",
    "fee": r"\bfees?\b",
    "tax": r"\btax(?:es|ed)?\b",
    "owe": r"\bow(?:e|es|ed|ing)\b",
}

FAMILIES: dict[str, dict[str, str]] = {
    "household_money": HOUSEHOLD_MONEY,
    "loot_currency": LOOT_CURRENCY,
    "admin": ADMIN_LEXICON,
    "frame": FRAME_LEXICON,
}

#: Closed-class words: articles, pronouns, prepositions, conjunctions, auxiliaries. English
#: stopped minting these, so the list cannot rot. They decide which words the provenance trace
#: and the exception locator treat as content, and nothing else.
CLOSED_CLASS: frozenset[str] = frozenset(
    """a an the and or but nor so yet for of to in on at by with from into onto over under
    about above across after against along among around before behind below beneath beside
    between beyond down during except inside near off out outside past since through
    throughout till toward towards until up upon within without as than then there here
    is are was were be been being am do does did done have has had having will would shall
    should can could may might must not no
    i me my mine we us our ours you your yours he him his she her hers it its they them their
    theirs this that these those who whom whose which what when where why how all any both
    each either every few many more most much neither none one other some such own same
    if because while although though unless whether also just only even still very too""".split()  # noqa: SIM905
)
#: A curly apostrophe, written as an escape so no reader takes it for a straight one.
APOSTROPHE = "\u2019"
_CAPITAL_RUN = re.compile(r"\b[A-Z][A-Za-z\u2019']*(?: [A-Z][A-Za-z\u2019']*)*")
_LETTERS = re.compile(r"[a-z]+")


def _compiled(lexicon: Mapping[str, str]) -> dict[str, re.Pattern[str]]:
    return {name: re.compile(pattern, re.IGNORECASE) for name, pattern in lexicon.items()}


_MECHANIC_PATTERNS = _compiled(MECHANIC_TERMS)
_FAMILY_PATTERNS = {family: _compiled(words) for family, words in FAMILIES.items()}


def registration_digest() -> str:
    """The report's own word lists, windows, floors and row names, addressed by their bytes.

    It does not cover the code a row is computed with (among it `overview.sentences`,
    `tells.density`, `register_census`, `authorship_tells`, `chapter_measures` and
    `exemplars._paragraphed`), so a change there moves rows without moving this digest
    (stage-0 §262)."""
    material = json.dumps(
        {
            "mechanic_terms": MECHANIC_TERMS,
            "families": FAMILIES,
            "first_window": FIRST_WINDOW,
            "short_sentence_words": SHORT_SENTENCE_WORDS,
            "bigram_base_per_fiction": BIGRAM_BASE_PER_FICTION,
            "floors": [UNIGRAM_FLOOR_PER_MILLION, BIGRAM_FLOOR_PER_MILLION],
            "rows": [*LISTING_KEYS, *CHAPTER_KEYS],
        },
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:16]


def word_list_digests() -> dict[str, str]:
    """Each word list on its own, so a changed list is named rather than only noticed."""
    lists = {"mechanic_terms": MECHANIC_TERMS, **FAMILIES}
    return {
        name: hashlib.sha256(json.dumps(words, sort_keys=True).encode("utf-8")).hexdigest()[:16]
        for name, words in lists.items()
    }


# --------------------------------------------------------------------------- percentiles


def percentile(value: float, values: Sequence[float]) -> dict[str, float | int | None]:
    """Where `value` sits among `values`: the count below, the count equal, and the mid-rank.

    Mid-rank counts ties as half: `100 * (below + equal / 2) / n`. An empty population has
    no position (`mid_rank` None), and the caller prints "no reference" for it.
    """
    n = len(values)
    below = sum(1 for other in values if other < value)
    equal = sum(1 for other in values if other == value)
    return {
        "n": n,
        "below": below,
        "equal": equal,
        "mid_rank": round(100.0 * (below + 0.5 * equal) / n, 1) if n else None,
    }


def describe(value: float, values: Sequence[float]) -> str:
    """One market cell: quantiles and mid-rank at n >= SMALL_N, "k of n" below it."""
    n = len(values)
    if not n:
        return "no reference (empty population)"
    place = percentile(value, values)
    if n < SMALL_N:
        tied = f", {place['equal']} equal" if place["equal"] else ""
        return f"{place['below']} of {n} below{tied}"
    ordered = sorted(values)
    cuts = statistics.quantiles(ordered, n=10)
    return (
        f"n={n} p10 {cuts[0]:.2f} p50 {statistics.median(ordered):.2f} p90 {cuts[-1]:.2f}, "
        f"mid-rank {place['mid_rank']}"
    )


# --------------------------------------------------------------------------- listing rows

LISTING_KEYS: tuple[str, ...] = (
    "words",
    "sentences",
    "sentence_words_mean",
    "longest_sentence_words",
    "first_sentence_words",
    "short_run",
    "coordinator_density",
    "mechanic_terms_per_100_words",
    "capitalised_terms_per_100_words",
    "digits",
    "questions",
    *(f"{family}_hits" for family in FAMILIES),
)


def short_run(sentences: Sequence[str], *, max_words: int = SHORT_SENTENCE_WORDS) -> int:
    """The longest run of consecutive sentences of at most `max_words` words each."""
    best = run = 0
    for sentence in sentences:
        if len(sentence.split()) <= max_words:
            run += 1
            best = max(best, run)
        else:
            run = 0
    return best


def family_counts(text: str, family: str) -> dict[str, int]:
    """Each word of one family, counted over `text`; only words that occur."""
    counts = {
        name: len(pattern.findall(text)) for name, pattern in _FAMILY_PATTERNS[family].items()
    }
    return {name: count for name, count in counts.items() if count}


def mechanic_terms(text: str) -> dict[str, int]:
    counts = {name: len(pattern.findall(text)) for name, pattern in _MECHANIC_PATTERNS.items()}
    return {name: count for name, count in counts.items() if count}


def listing_measures(text: str) -> dict[str, float | int]:
    """The listing numbers that have a market column. Same function on both sides."""
    text = text.replace("\r\n", "\n").strip()
    words = len(text.split())
    per_100 = 100.0 / words if words else 0.0
    parts = overview.sentences(text)
    lengths = [len(part.split()) for part in parts]
    row: dict[str, float | int] = {
        "words": words,
        "sentences": len(parts),
        "sentence_words_mean": round(statistics.fmean(lengths), 2) if lengths else 0.0,
        "longest_sentence_words": overview.longest_sentence(text),
        "first_sentence_words": lengths[0] if lengths else 0,
        "short_run": short_run(parts),
        "coordinator_density": round(overview.coordinator_density(text), 2),
        "mechanic_terms_per_100_words": round(sum(mechanic_terms(text).values()) * per_100, 2),
        "capitalised_terms_per_100_words": round(
            len(register_census.proper_nouns(text)) * per_100, 2
        ),
        "digits": len(re.findall(r"\d+", text)),
        "questions": text.count("?"),
    }
    for family in FAMILIES:
        row[f"{family}_hits"] = sum(family_counts(text, family).values())
    return row


def _strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _system_blocks(concept: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        block
        for block in (concept.get("system"), concept.get("second_system"))
        if isinstance(block, Mapping)
    ]


def _system_text(concept: Mapping[str, Any]) -> str:
    """What the system description says, under its stored or its presented key names."""
    keys = ("look", "manner", "pays", "what_rising_gives")
    return "\n".join(
        str(block[key]) for block in _system_blocks(concept) for key in keys if block.get(key)
    )


def _capitalised(word: str, text: str) -> bool:
    return re.search(rf"\b{re.escape(word.capitalize())}\b", text) is not None


def mechanic_vocabulary(concept: Mapping[str, Any]) -> frozenset[str]:
    """The book's own mechanic names, lowercased, as the concept writes them.

    A word qualifies when `register_census.proper_nouns` reads it as a name across the whole
    concept, and the system description or the exception capitalises it. Two exclusions
    apply. The person's own name, from `person_before`, is never a mechanic. A name the
    author's brief supplies (Earth) is excluded unless the system description itself uses it:
    Slot stays, because the system text names it.
    """
    skip = {"author_brief", "invention_seed"}
    whole = "\n".join(
        text for key, value in concept.items() if key not in skip for text in _strings(value)
    )
    names = register_census.proper_nouns(whole)
    system = _system_text(concept)
    source = f"{system}\n{concept.get('exception') or ''}"
    person = str(concept.get("person_before") or "")
    brief = str(concept.get("author_brief") or "")
    return frozenset(
        word
        for word in names
        if _capitalised(word, source)
        and not _capitalised(word, person)
        and (not _capitalised(word, brief) or _capitalised(word, system))
    )


def _system_name_words(concept: Mapping[str, Any]) -> set[str]:
    return {
        word.lower()
        for block in _system_blocks(concept)
        for word in re.findall(r"[A-Za-z]+", str(block.get("name") or ""))
        if word.lower() != "the"
    }


def mechanic_names(listing: str, concept: Mapping[str, Any]) -> list[str]:
    """Distinct mechanic names the listing uses, as the listing writes them.

    Each maximal run of capitalised words is trimmed of the words the concept never
    capitalises in its system text or exception. It is kept when a word in it is in
    `mechanic_vocabulary`. The system's own name is reported by `system_named`, not here.
    """
    vocabulary = mechanic_vocabulary(concept)
    source = f"{_system_text(concept)}\n{concept.get('exception') or ''}"
    system_words = _system_name_words(concept)
    found: set[str] = set()
    for run in _CAPITAL_RUN.findall(listing):
        words = run.split()
        keep = [
            _capitalised(word.split(APOSTROPHE)[0].split("'")[0].lower(), source) for word in words
        ]
        while words and not keep[0]:
            words, keep = words[1:], keep[1:]
        while words and not keep[-1]:
            words, keep = words[:-1], keep[:-1]
        lowered = [_LETTERS.match(word.lower()) for word in words]
        stems = [match.group(0) for match in lowered if match]
        if not any(stem in vocabulary for stem in stems):
            continue
        if all(stem in system_words for stem in stems):
            continue
        found.add(" ".join(words))
    return sorted(found)


def system_named(listing: str, concept: Mapping[str, Any]) -> bool | None:
    """Whether the listing names the system as the concept names it; None with no name."""
    names = [str(block.get("name") or "").strip() for block in _system_blocks(concept)]
    names = [re.sub(r"^the\s+", "", name, flags=re.IGNORECASE) for name in names if name]
    if not names:
        return None
    return any(re.search(rf"\b{re.escape(name)}\b", listing) for name in names)


def exception_at(sentences: Sequence[str], concept: Mapping[str, Any]) -> dict[str, Any] | None:
    """The first sentence sharing two content stems with the exception that the person's own
    before-and-want text does not hold: where the one-person power first shows. None if none.
    """
    exception = str(concept.get("exception") or "").lower()
    context = " ".join(str(concept.get(key) or "") for key in ("person_before", "want")).lower()
    context_words = set(_LETTERS.findall(context))
    stems = {
        word[:5]
        for word in _LETTERS.findall(exception)
        if len(word) > 3 and word not in CLOSED_CLASS and word not in context_words
    }
    for index, sentence in enumerate(sentences, start=1):
        shared = {word[:5] for word in _LETTERS.findall(sentence.lower()) if len(word) > 3}
        shared &= stems
        if len(shared) >= 2:
            return {"sentence": index, "text": sentence, "shared_stems": sorted(shared)}
    return None


def live_listing_task() -> str:
    """The supplied-concept listing task as the code sends it today, with no writer."""
    return overview.render_overview_request("", concept="-").system or ""


def listing_rows(
    text: str,
    *,
    concept: Mapping[str, Any] | None = None,
    task: str | None = None,
    task_source: str = "supplied task",
) -> dict[str, Any]:
    """The market-comparable measures, plus the ours-only shape and hit rows.

    Without a recorded task the echo row reads against the live listing task, and says so.
    """
    text = text.replace("\r\n", "\n").strip()
    if task is None:
        task, task_source = live_listing_task(), "live concept listing task"
    parts = overview.sentences(text)
    shape: dict[str, Any] = {
        "first_sentence": parts[0] if parts else "",
        "last_sentence": parts[-1] if parts else "",
        "mechanic_terms": mechanic_terms(text),
        "task_echo": {
            "longest_shared_run_words": voice.longest_shared_run(text, task),
            "against": task_source,
        },
    }
    if concept is not None:
        shape["mechanic_names"] = mechanic_names(text, concept)
        shape["system_named"] = system_named(text, concept)
        shape["exception_at"] = exception_at(parts, concept)
    return {
        "measures": listing_measures(text),
        "shape": shape,
        "family_hits": {family: family_counts(text, family) for family in FAMILIES},
    }


# --------------------------------------------------------------------------- chapter rows

TELLS_KEYS = tuple(f"tells_{family}_per_1k" for family in tells.FAMILIES)
CHAPTER_KEYS: tuple[str, ...] = (
    "prose_words",
    *(f"{family}_per_1k" for family in FAMILIES),
    *(f"{family}_first{FIRST_WINDOW}" for family in FAMILIES),
    *(f"{family}_first_hit_at_word" for family in FAMILIES),
    "friction_rare_per_1k",
    "bigram_friction_rare_per_1k",
    *TELLS_KEYS,
    "sentence_words_mean",
    "sentence_words_median",
    "sentence_over_30_share",
    "dialogue_ratio",
    "paragraph_words_mean",
    "proper_nouns_per_1k",
    "first_sentence_words",
    "first_paragraph_words",
)
_SEPARATORS = frozenset({"* * *", "***", "---", "~~~"})


def chapter_prose(text: str) -> str:
    """The chapter's prose, normalised the same way on our side and the market's.

    Line ends are unified, a one-newline-per-paragraph file is re-paragraphed
    (`exemplars._paragraphed`), `[STATUS]` lines go (`chapter_measures.prose_only`), and
    headings, scene separators and the System's own lines (`tells.is_machine_line`) are dropped.
    """
    text = exemplars._paragraphed(text.replace("\r\n", "\n"))
    text = chapter_measures.prose_only(text)
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    kept = [
        " ".join(part.split())
        for part in paragraphs
        if not part.startswith("#") and part not in _SEPARATORS and not tells.is_machine_line(part)
    ]
    return "\n\n".join(kept)


def family_positions(prose: str, family: str) -> dict[str, Any]:
    """Rate per 1k words, count in the first window, words before the first hit, every hit.

    Every count comes from the one list of matches, each placed at the whitespace word it
    starts in, so the rate, the window and the hit list always agree.
    """
    starts = [match.start() for match in re.finditer(r"\S+", prose)]
    hits = sorted(
        (bisect.bisect_right(starts, match.start()) - 1, match.group(0).lower())
        for pattern in _FAMILY_PATTERNS[family].values()
        for match in pattern.finditer(prose)
    )
    return {
        "per_1k": round(1000.0 * len(hits) / len(starts), 2) if starts else 0.0,
        "first_window": sum(1 for index, _ in hits if index < FIRST_WINDOW),
        "first_hit_at_word": hits[0][0] if hits else None,
        "hits": [[index, word] for index, word in hits],
    }


def chapter_measures_row(
    text: str, table: Mapping[str, Any] | None = None
) -> dict[str, float | int | None]:
    """The chapter numbers that have a market column. Same function on both sides."""
    prose = chapter_prose(text)
    words = prose.split()
    n = len(words)
    row: dict[str, float | int | None] = {"prose_words": n}
    for family in FAMILIES:
        found = family_positions(prose, family)
        row[f"{family}_per_1k"] = found["per_1k"]
        row[f"{family}_first{FIRST_WINDOW}"] = found["first_window"]
        row[f"{family}_first_hit_at_word"] = found["first_hit_at_word"]
    row.update(friction_row(prose, table))
    density = tells.density(prose)
    for family in tells.FAMILIES:
        row[f"tells_{family}_per_1k"] = round(density[family], 2)
    profile = chapter_measures.sentence_profile(prose)
    row["sentence_words_mean"] = profile.get("words_mean")
    row["sentence_words_median"] = profile.get("words_median")
    row["sentence_over_30_share"] = profile.get("over_30_share")
    features = authorship_tells.features(prose)
    row["dialogue_ratio"] = round(features["dialogue_ratio"], 4)
    row["paragraph_words_mean"] = round(features["paragraph_len_mean"], 2)
    row["proper_nouns_per_1k"] = (
        round(1000.0 * len(register_census.proper_nouns(prose)) / n, 2) if n else 0.0
    )
    paragraphs = prose.split("\n\n")
    first = tells.sentences_of(paragraphs[0]) if paragraphs and paragraphs[0] else []
    row["first_sentence_words"] = len(first[0].split()) if first else 0
    row["first_paragraph_words"] = len(paragraphs[0].split()) if paragraphs else 0
    return row


@dataclass
class OwnCounts:
    """What one market fiction put into the frequency base, restricted to its chapter one's
    own words and word pairs, which are the only entries its friction reads."""

    unigrams: Counter[str] = field(default_factory=Counter)
    unigram_total: int = 0
    bigrams: Counter[str] = field(default_factory=Counter)
    bigram_total: int = 0


class _Without:
    """A count table less one fiction's own counts: what the rest of the shelf holds."""

    def __init__(self, table: Mapping[str, int], own: Mapping[str, int]) -> None:
        self.table = table
        self.own = own

    def get(self, key: str, default: int = 0) -> int:
        return max(0, self.table.get(key, default) - self.own.get(key, 0))


def friction_row(
    prose: str, table: Mapping[str, Any] | None, own: OwnCounts | None = None
) -> dict[str, float | None]:
    """`register_census` friction against the derived base, or None without one.

    Our book is never in the base. A market chapter one is read the same way: `own`, its
    fiction's later chapters, comes out of the base first, so a word the book coined and
    kept using does not make its own opening read as common.
    """
    if table is None:
        return {"friction_rare_per_1k": None, "bigram_friction_rare_per_1k": None}
    unigrams: Any = table["unigrams"]
    bigrams: Any = table["bigrams"]
    unigram_total = int(table["unigram_total"])
    bigram_total = int(table["bigram_total"])
    if own is not None:
        unigrams, unigram_total = (
            _Without(unigrams, own.unigrams),
            unigram_total - own.unigram_total,
        )
        bigrams, bigram_total = _Without(bigrams, own.bigrams), bigram_total - own.bigram_total
    unigram = register_census.friction(
        prose, unigrams, total=unigram_total, per_million_floor=UNIGRAM_FLOOR_PER_MILLION
    )
    bigram = register_census.bigram_friction(
        prose, bigrams, total=bigram_total, per_million_floor=BIGRAM_FLOOR_PER_MILLION
    )
    return {
        "friction_rare_per_1k": round(unigram["rare_rate"], 2),
        "bigram_friction_rare_per_1k": round(bigram["rare_bigram_rate"], 2),
    }


def rarest_words(prose: str, table: Mapping[str, Any], *, limit: int = 10) -> list[dict[str, Any]]:
    """Our own rarest non-name words, with their frequency in the base. Never a locator."""
    names = register_census.proper_nouns(prose)
    unigrams: Mapping[str, int] = table["unigrams"]
    total = int(table["unigram_total"]) or 1
    order: dict[str, int] = {}
    for index, token in enumerate(register_census.tokens(prose)):
        if token not in names and token not in CLOSED_CLASS:
            order.setdefault(token, index)
    ranked = sorted(order, key=lambda word: (unigrams.get(word, 0), order[word]))[:limit]
    return [
        {"word": word, "per_million": round(unigrams.get(word, 0) * 1e6 / total, 3)}
        for word in ranked
    ]


def chapter_rows(text: str, table: Mapping[str, Any] | None = None) -> dict[str, Any]:
    prose = chapter_prose(text)
    opening = tells.sentences_of(prose.split("\n\n")[0]) if prose else []
    rows: dict[str, Any] = {
        "measures": chapter_measures_row(text, table),
        "family_hits": {family: family_positions(prose, family)["hits"] for family in FAMILIES},
        "first_sentence": opening[0] if opening else "",
    }
    if table is not None:
        rows["rarest_words"] = rarest_words(prose, table)
    return rows


# --------------------------------------------------------------------------- provenance

#: Where each section of a recorded scene-writer request starts, by the text the code renders
#: (`planner.render_scene_request`, `domain/context.py`). Text before the first marker is the
#: writer's dossier in the system message and unlabelled material in the prompt.
SYSTEM_MARKERS: tuple[tuple[str, str], ...] = (
    ("system:instructions", "You are drafting one scene of a novel."),
    ("system:constraints", "Locked constraints and promises"),
    ("system:world_rules", "This world judges people by"),
    ("system:world_rules", "World rules and limits —"),
)
PROMPT_MARKERS: tuple[tuple[str, str], ...] = (
    ("prompt:premise", "Premise: "),
    ("prompt:plan", "Planned story — "),
    ("prompt:world_rules", "World rules and limits —"),
    ("prompt:plan", "Open threads the book has not yet resolved:"),
    ("prompt:cast_facts", "Who is in this story:"),
    ("prompt:cast_facts", "Established facts"),
    ("prompt:hidden", "True, and the reader has not been told"),
    ("prompt:cast_facts", "Earlier states — "),
    ("prompt:summaries", "Earlier scenes, in summary"),
    ("prompt:prior_prose", "The story so far, in full:"),
    ("prompt:scene_brief", "\n\nNow write "),
)
SCENE_TASK = "\n\nNow write "
SCENE_SYSTEM = "You are drafting one scene of a novel."
MODEL_SUPPLIED = "none"


def sections(text: str, markers: Sequence[tuple[str, str]], lead: str) -> list[tuple[str, str]]:
    """Cut `text` at each marker it holds, in the order they occur; `lead` names the start."""
    starts: list[tuple[int, str]] = []
    for label, marker in markers:
        at = text.rfind(marker) if marker == SCENE_TASK else text.find(marker)
        if at >= 0:
            starts.append((at, label))
    starts.sort()
    if not starts or starts[0][0] > 0:
        starts.insert(0, (0, lead))
    bounds = [*(at for at, _ in starts[1:]), len(text)]
    return [(label, text[at:end]) for (at, label), end in zip(starts, bounds, strict=True)]


def _trace_tokens(text: str) -> list[str]:
    """`register_census.tokens` with a curly apostrophe read as a straight one and a
    possessive read as its noun, so "Nessa's" on the page is found as "Nessa" in the cast.
    Other contractions stay whole and are never content words."""
    return [
        token[:-2] if token.endswith("'s") else token
        for token in register_census.tokens(text.replace(APOSTROPHE, "'"))
    ]


def _grams(tokens: Sequence[str], size: int) -> list[str]:
    return [" ".join(tokens[i : i + size]) for i in range(len(tokens) - size + 1)]


def scene_label(prompt: str, fallback: str) -> str:
    at = prompt.rfind(SCENE_TASK)
    if at < 0:
        return fallback
    head = prompt[at + len(SCENE_TASK) :].split(" — ", 1)[0]
    return head.rsplit(": ", 1)[-1].strip() or fallback


def trace_call(receipt: Mapping[str, Any], name: str) -> dict[str, Any] | None:
    """Every content word and 2-3 word sequence on one scene's page, with its sources."""
    request = receipt.get("request") or {}
    system = str(request.get("system") or "")
    prompt = str(request.get("prompt") or "")
    page = str((receipt.get("result") or {}).get("text") or "")
    if SCENE_SYSTEM not in system or SCENE_TASK not in prompt or not page:
        return None
    parts = [
        *sections(system, SYSTEM_MARKERS, "system:writer"),
        *sections(prompt, PROMPT_MARKERS, "prompt:other"),
    ]
    labels: list[str] = []
    for label, _ in parts:
        if label not in labels:
            labels.append(label)
    words: dict[str, set[str]] = {label: set() for label in labels}
    grams: dict[str, set[str]] = {label: set() for label in labels}
    for label, text in parts:
        tokens = _trace_tokens(text)
        words[label].update(tokens)
        grams[label].update(_grams(tokens, 2))
        grams[label].update(_grams(tokens, 3))
    page_tokens = _trace_tokens(chapter_measures.prose_only(page))

    def sources(item: str, index: Mapping[str, set[str]]) -> list[str]:
        return [label for label in labels if item in index[label]]

    word_rows: dict[str, dict[str, Any]] = {}
    for token in page_tokens:
        if token in CLOSED_CLASS or len(token) < 3 or "'" in token:
            continue
        row = word_rows.get(token)
        if row is None:
            found = sources(token, words)
            row = word_rows[token] = {
                "count": 0,
                "first_source": found[0] if found else MODEL_SUPPLIED,
                "sources": found,
            }
        row["count"] += 1
    sequences: dict[str, dict[str, Any]] = {}
    for size in (2, 3):
        for gram in _grams(page_tokens, size):
            if gram in sequences or all(part in CLOSED_CLASS for part in gram.split()):
                continue
            found = sources(gram, grams)
            sequences[gram] = {
                "first_source": found[0] if found else MODEL_SUPPLIED,
                "sources": found,
            }
    by_source = Counter(row["first_source"] for row in word_rows.values())
    echoed = sum(1 for row in sequences.values() if row["first_source"] != MODEL_SUPPLIED)
    return {
        "call": name,
        "scene": scene_label(prompt, name),
        "sections": labels,
        "content_words": len(word_rows),
        "words_by_first_source": dict(sorted(by_source.items())),
        "model_supplied_words": [
            w for w, r in word_rows.items() if r["first_source"] == MODEL_SUPPLIED
        ],
        "words": word_rows,
        "sequences": sequences,
        "echoed_sequences": echoed,
        "model_supplied_sequences": len(sequences) - echoed,
    }


def provenance(draw: Path) -> list[dict[str, Any]]:
    """The trace for every scene-writer call a draw folder recorded, in call order."""
    traced: list[dict[str, Any]] = []
    for path in sorted((draw / "calls").glob("*.json")):
        receipt = json.loads(path.read_text(encoding="utf-8"))
        row = trace_call(receipt, path.name)
        if row is not None:
            traced.append(row)
    return traced


def recorded_listing_task(draw: Path, listing: str) -> str | None:
    """The system text of the recorded request that produced this listing, if the draw has it."""
    candidates: list[Mapping[str, Any]] = []
    for path in sorted((draw / "calls").glob("*.json")):
        receipt = json.loads(path.read_text(encoding="utf-8"))
        if str(receipt.get("profile") or "").startswith("writer.overview"):
            candidates.append(receipt)
    for receipt in candidates:
        if str((receipt.get("result") or {}).get("text") or "").strip() == listing.strip():
            return str((receipt.get("request") or {}).get("system") or "")
    if candidates:
        return str((candidates[-1].get("request") or {}).get("system") or "")
    return None


# --------------------------------------------------------------------------- market baseline

#: Lead-tag families kept from the backtest's fictions (`corpus.LEAD_TAGS`), and the rival
#: pool's genre labels for the same three shelves.
KEPT_FAMILIES = frozenset({"LitRPG", "Progression", "Portal Fantasy / Isekai"})
KEPT_RIVAL_GENRES = frozenset({"litrpg", "progression fantasy", "isekai"})
#: Every file the builder opens. book-library is not among them: its placed openings were shown
#: to books this report would then describe (opening-parity PREREG §5f).
BUILDER_INPUTS: tuple[Path, ...] = (RIVALS, FICTIONS)


def backtest_corpus() -> ModuleType:
    """The sim-readership backtest's `corpus` module, loaded by path under its own name.

    It is registered in `sys.modules` before it runs, because its frozen dataclasses resolve
    their annotations through the module they were defined in.
    """
    name = "sim_backtest_corpus"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, BACKTEST_CORPUS)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {BACKTEST_CORPUS}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[name]
        raise
    return module


def iter_fiction_rows(
    path: Path, *, chunk_chars: int = 1 << 24
) -> Iterator[tuple[str, list[dict[str, Any]]]]:
    """Stream `{fiction_id: [row, ...]}` one fiction at a time, never the whole file.

    The backtest file is about 2 GB of JSON. Reading it whole with `json.loads` holds the text
    and every parsed row at once; this holds one buffer and one fiction.
    """
    with path.open("rb") as handle:
        reader = _ChunkedJson(handle, chunk_chars, str(path))
        if reader.peek() != "{":
            raise ValueError(f"{path}: expected a JSON object of fictions")
        reader.pos += 1
        while True:
            mark = reader.peek()
            if mark == "}":
                return
            if mark == ",":
                reader.pos += 1
                reader.peek()
            key = reader.value()
            if reader.peek() != ":":
                raise ValueError(f"{path}: expected ':' after key {key!r}")
            reader.pos += 1
            reader.peek()
            yield str(key), list(reader.value())


class _ChunkedJson:
    """A decoded text buffer over a binary file, refilled only when a value runs past its end.

    Every value this reads is a string key or a list, and neither decodes until its closing
    character is in the buffer, so a value cut at a chunk boundary fails and is retried after
    one more chunk rather than decoding short.
    """

    def __init__(self, handle: Any, chunk_chars: int, name: str) -> None:
        self.handle = handle
        self.chunk_chars = chunk_chars
        self.name = name
        self.utf8 = codecs.getincrementaldecoder("utf-8")()
        self.decoder = json.JSONDecoder()
        self.buf = ""
        self.pos = 0
        self.eof = False
        self.fill()

    def fill(self) -> None:
        chunk = self.handle.read(self.chunk_chars)
        self.buf = self.buf[self.pos :] + self.utf8.decode(chunk, final=not chunk)
        self.pos = 0
        self.eof = not chunk

    def peek(self) -> str:
        """Skip whitespace and return the next character, reading on as needed."""
        while True:
            while self.pos < len(self.buf) and self.buf[self.pos] in " \t\r\n":
                self.pos += 1
            if self.pos < len(self.buf):
                return self.buf[self.pos]
            if self.eof:
                raise ValueError(f"{self.name}: the JSON object ends early")
            self.fill()

    def value(self) -> Any:
        while True:
            try:
                decoded, end = self.decoder.raw_decode(self.buf, self.pos)
            except json.JSONDecodeError:
                if self.eof:
                    raise
                self.fill()
                continue
            self.pos = end
            return decoded


def population_refusal(fiction: Any, corpus: ModuleType, quarantined: frozenset[int]) -> str | None:
    """None when a backtest fiction enters the market population; else the first reason.

    Quarantine first (§150.1's 26 descriptor-half ids aimed our own voice), then the lead tag,
    then the backtest's own eligibility, which refuses declared-AI books and any fiction whose
    chapter one cannot be identified.
    """
    fiction_id = str(fiction.fiction_id)
    if fiction_id.isdigit() and int(fiction_id) in quarantined:
        return "quarantined"
    family = next((tag for tag in corpus.LEAD_TAGS if tag in fiction.tags), "other")
    if family not in KEPT_FAMILIES:
        return "genre"
    reason = corpus.eligibility(fiction)
    return str(reason) if reason is not None else None


def rival_refusal(rival: Mapping[str, Any], quarantined: frozenset[int]) -> str | None:
    """None when an admitted rival listing enters the listing population; else the reason."""
    source = str(rival.get("source") or "")
    fiction_id = source.rsplit(":", 1)[-1]
    if fiction_id.isdigit() and int(fiction_id) in quarantined:
        return "quarantined"
    if str(rival.get("genre") or "").lower() not in KEPT_RIVAL_GENRES:
        return "genre"
    if not str(rival.get("listing") or "").strip():
        return "no_listing"
    return None


def later_chapters(fiction: Any, opening: Sequence[Any]) -> list[Any]:
    """The chapters released after the identified chapter three: the frequency base.

    Chapters one to three are held out, and so is anything released before chapter three (a
    prologue, a stray first post), so no text a scored opening could hold is in its own base.
    """
    held_out = {chapter.chapter_id for chapter in opening}
    order = [chapter.chapter_id for chapter in fiction.chapters]
    last = max(order.index(chapter_id) for chapter_id in held_out)
    return [
        chapter for chapter in fiction.chapters[last + 1 :] if chapter.chapter_id not in held_out
    ]


def _column(rows: Iterable[Mapping[str, Any]], key: str) -> list[float]:
    return sorted(
        round(float(row[key]), 4) for row in rows if isinstance(row.get(key), int | float)
    )


def metric_columns(rows: Sequence[Mapping[str, Any]], keys: Sequence[str]) -> dict[str, Any]:
    """Sorted numbers per metric. A row with no value (no hit at all) is left out of `values`
    and still counted in `population`, so "n of population have one" stays readable."""
    columns: dict[str, Any] = {}
    for key in keys:
        values = _column(rows, key)
        columns[key] = {"population": len(rows), "n": len(values), "values": values}
    return columns


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 22), b""):
            digest.update(block)
    return digest.hexdigest()


def _pruned(table: Counter[str], total: int, floor: float, *, keep_rare: bool) -> dict[str, int]:
    """Drop entries the floor calls rare anyway, so the stored table stays small and exact.

    A count below `floor * total / 1e6` is rare whether it is stored or not. With `keep_rare`,
    counts of two and up are kept regardless, so the rarest-words list can still order them.
    """
    clearing = max(1, math.ceil(floor * total / 1_000_000))
    least = min(2, clearing) if keep_rare else clearing
    return {word: count for word, count in sorted(table.items()) if count >= least}


def build_baseline(
    *,
    fictions: Path = FICTIONS,
    rivals: Path = RIVALS,
    out: Path = BASELINE,
    table_out: Path = FREQUENCY_TABLE,
    quarantined: frozenset[int] | None = None,
    corpus: ModuleType | None = None,
) -> dict[str, Any]:
    """Build the numbers-only market baseline and the gitignored frequency table.

    Listings come from the admitted rival pool and from the backtest fictions' own blurbs, as
    two populations that are never pooled. Chapter ones are the backtest fictions' identified
    chapter one (`corpus.chapters_1_to_3`). The frequency base is the same fictions' chapters
    after chapter three (`later_chapters`), and each chapter one's friction is read with its
    own fiction's share taken out (`OwnCounts`), as ours is read against a base without it.
    """
    if quarantined is None:
        import progression_cadence

        quarantined = progression_cadence.quarantined_ids()
    corpus = corpus or backtest_corpus()

    rival_rows: list[dict[str, float | int]] = []
    rival_refused: Counter[str] = Counter()
    loaded = json.loads(rivals.read_text(encoding="utf-8"))
    for rival in loaded:
        reason = rival_refusal(rival, quarantined)
        if reason:
            rival_refused[reason] += 1
            continue
        rival_rows.append(listing_measures(str(rival["listing"])))

    blurb_rows: list[dict[str, float | int]] = []
    chapter_one_rows: list[dict[str, float | int | None]] = []
    chapter_one_prose: list[str] = []
    chapter_one_own: list[OwnCounts] = []
    refused: Counter[str] = Counter()
    unigrams: Counter[str] = Counter()
    bigrams: Counter[str] = Counter()
    base_chapters = bigram_chapters = fictions_read = not_first_released = 0
    for _, rows in iter_fiction_rows(fictions):
        fictions_read += 1
        fiction = corpus.fiction_from_rows(rows)
        reason = population_refusal(fiction, corpus, quarantined)
        if reason:
            refused[reason] += 1
            continue
        opening = corpus.chapters_1_to_3(fiction)
        if opening[0] is not fiction.chapters[0]:
            # The backtest's identification, reused as registered: say how often its chapter
            # one is not the first chapter the fiction released.
            not_first_released += 1
        chapter_one = opening[0].text
        prose = chapter_prose(chapter_one)
        chapter_one_rows.append(chapter_measures_row(chapter_one))
        chapter_one_prose.append(prose)
        blurb_rows.append(listing_measures(fiction.description))
        opening_words = set(register_census.tokens(prose))
        opening_pairs = set(register_census.bigrams(register_census.tokens(prose)))
        own = OwnCounts()
        for position, chapter in enumerate(later_chapters(fiction, opening)):
            # The base is a word count, not a scored text: raw tokens, no paragraph work.
            tokens = register_census.tokens(chapter.text)
            unigrams.update(tokens)
            own.unigrams.update(token for token in tokens if token in opening_words)
            own.unigram_total += len(tokens)
            base_chapters += 1
            if position < BIGRAM_BASE_PER_FICTION:
                pairs = register_census.bigrams(tokens)
                bigrams.update(pairs)
                own.bigrams.update(pair for pair in pairs if pair in opening_pairs)
                own.bigram_total += len(pairs)
                bigram_chapters += 1
        chapter_one_own.append(own)
    unigram_total = sum(unigrams.values())
    bigram_total = sum(bigrams.values())
    table = {
        "note": "derived word counts, gitignored; numbers keyed by word, no corpus text",
        "registration_digest": registration_digest(),
        "unigram_total": unigram_total,
        "bigram_total": bigram_total,
        "unigrams": _pruned(unigrams, unigram_total, UNIGRAM_FLOOR_PER_MILLION, keep_rare=True),
        "bigrams": _pruned(bigrams, bigram_total, BIGRAM_FLOOR_PER_MILLION, keep_rare=False),
    }
    del unigrams, bigrams
    for row, prose, own in zip(chapter_one_rows, chapter_one_prose, chapter_one_own, strict=True):
        row.update(friction_row(prose, table, own))

    table_out.parent.mkdir(parents=True, exist_ok=True)
    table_out.write_text(json.dumps(table, sort_keys=True), encoding="utf-8", newline="\n")
    baseline = {
        "instrument": "register_report.baseline.v1",
        "header": HEADER,
        "registration_digest": registration_digest(),
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "sources": [
            {
                "path": rivals.relative_to(REPO).as_posix()
                if rivals.is_relative_to(REPO)
                else rivals.name,
                "sha256": _sha256(rivals),
                "rows": len(loaded),
                "kept": len(rival_rows),
                "refused": dict(sorted(rival_refused.items())),
                "filter": "genre in litrpg, progression fantasy, isekai; 150.1 quarantine out",
            },
            {
                "path": fictions.relative_to(REPO).as_posix()
                if fictions.is_relative_to(REPO)
                else fictions.name,
                "sha256": _sha256(fictions),
                "rows": fictions_read,
                "kept": len(chapter_one_rows),
                "chapter_one_not_first_released": not_first_released,
                "refused": dict(sorted(refused.items())),
                "filter": "lead tag LitRPG, Progression or Isekai; 150.1 quarantine out; "
                "the backtest's own eligibility (refusal reasons counted above)",
            },
        ],
        "frequency_base": {
            "chapters": base_chapters,
            "unigram_tokens": unigram_total,
            "bigram_chapters": bigram_chapters,
            "bigram_tokens": bigram_total,
            "held_out": "chapters 1-3 and anything released before chapter 3 are outside",
            "own_fiction": "a market chapter one is read with its own fiction taken out",
            "table_sha256": _sha256(table_out),
        },
        "metrics": {
            "listing_rivals": metric_columns(rival_rows, LISTING_KEYS),
            "listing_blurbs": metric_columns(blurb_rows, LISTING_KEYS),
            "chapter_one": metric_columns(chapter_one_rows, CHAPTER_KEYS),
        },
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(baseline, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    return baseline


# --------------------------------------------------------------------------- the report

POPULATION_NAMES = {
    "listing_rivals": "admitted rival listings",
    "listing_blurbs": "backtest blurbs",
    "chapter_one": "market chapter ones",
}


def load_baseline(path: Path) -> tuple[dict[str, Any] | None, str]:
    """The baseline and why it is usable, or None and the reason every market cell gives."""
    if not path.is_file():
        return None, "no reference (baseline not built)"
    baseline = json.loads(path.read_text(encoding="utf-8"))
    built = baseline.get("registration_digest")
    if built != registration_digest():
        return (
            None,
            f"no reference (baseline digest {built} is not the live {registration_digest()})",
        )
    return baseline, ""


def load_table(path: Path) -> tuple[dict[str, Any] | None, str]:
    """The derived frequency table, or None and the reason the friction rows have none."""
    if not path.is_file():
        return None, "no reference (derived frequency base absent)"
    table: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    built = table.get("registration_digest")
    if built != registration_digest():
        return None, f"no reference (frequency base digest {built} is not the live one)"
    return table, "derived table present"


def market_cells(
    measures: Mapping[str, Any],
    baseline: Mapping[str, Any] | None,
    reason: str,
    populations: Sequence[str],
) -> dict[str, dict[str, Any]]:
    """Per metric and population: n, the ours-below/equal counts and the printed cell."""
    cells: dict[str, dict[str, Any]] = {}
    for key, value in measures.items():
        cells[key] = {}
        for population in populations:
            if baseline is None:
                cells[key][population] = {"cell": reason}
                continue
            column = baseline["metrics"].get(population, {}).get(key)
            if column is None:
                cells[key][population] = {"cell": "no reference (not in baseline)"}
            elif value is None:
                with_value = column["n"]
                cells[key][population] = {
                    "cell": f"ours has none; {with_value} of {column['population']} market have one"
                }
            else:
                values = column["values"]
                cell = describe(float(value), values)
                if column["n"] < column["population"]:
                    cell += f" (among the {column['n']} of {column['population']} with one)"
                cells[key][population] = {"cell": cell, **percentile(float(value), values)}
    return cells


def report(
    *,
    listing: str | None = None,
    chapter: str | None = None,
    concept: Mapping[str, Any] | None = None,
    task: str | None = None,
    task_source: str = "supplied task",
    draw: Path | None = None,
    baseline_path: Path = BASELINE,
    table_path: Path = FREQUENCY_TABLE,
) -> dict[str, Any]:
    baseline, reason = load_baseline(baseline_path)
    out: dict[str, Any] = {
        "header": HEADER,
        "scope": SCOPE,
        "registration_digest": registration_digest(),
        "word_list_digests": word_list_digests(),
        "baseline": reason
        or f"{baseline_path.name} built {baseline.get('built_at') if baseline else ''}",
    }
    if listing is not None:
        rows = listing_rows(listing, concept=concept, task=task, task_source=task_source)
        rows["market"] = market_cells(
            rows["measures"], baseline, reason, ("listing_rivals", "listing_blurbs")
        )
        out["listing"] = rows
    if chapter is not None:
        table, table_reason = load_table(table_path)
        rows = chapter_rows(chapter, table)
        rows["frequency_base"] = table_reason
        rows["market"] = market_cells(rows["measures"], baseline, reason, ("chapter_one",))
        out["chapter"] = rows
    if draw is not None:
        out["provenance"] = provenance(draw)
    return out


def _fmt(value: Any) -> str:
    if value is None:
        return "none"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def render(result: Mapping[str, Any], *, trace_words: Sequence[str] = ()) -> str:
    lines = [
        result["header"],
        result["scope"],
        f"digest {result['registration_digest']}; baseline: {result['baseline']}",
        f"word lists: {json.dumps(result['word_list_digests'])}",
    ]
    for part in ("listing", "chapter"):
        if part not in result:
            continue
        rows = result[part]
        lines.append("")
        lines.append(f"== {part}")
        for key, value in rows["measures"].items():
            cells = " | ".join(
                f"{POPULATION_NAMES[population]}: {cell['cell']}"
                for population, cell in rows["market"][key].items()
            )
            lines.append(f"  {key:34} {_fmt(value):>8}  {cells}")
        if part == "listing":
            shape = rows["shape"]
            lines.append("  -- shape (ours only)")
            for key, value in shape.items():
                lines.append(f"  {key}: {json.dumps(value, ensure_ascii=False)}")
        else:
            lines.append(f"  -- frequency base: {rows['frequency_base']}")
            lines.append(f"  first sentence: {rows['first_sentence']}")
            if "rarest_words" in rows:
                shown = ", ".join(f"{r['word']} {r['per_million']}/M" for r in rows["rarest_words"])
                lines.append(f"  rarest words (ours; not a locator): {shown}")
        lines.append("  -- hits (word index in prose, token)" if part == "chapter" else "  -- hits")
        for family, hits in rows["family_hits"].items():
            lines.append(f"  {family}: {json.dumps(hits, ensure_ascii=False)}")
    if "provenance" in result:
        lines.append("")
        lines.append("== provenance (ours only): first source of each content word on the page")
        if not result["provenance"]:
            lines.append("  no scene-writer calls recorded in this draw")
        for scene in result["provenance"]:
            lines.append(
                f"  {scene['scene']} ({scene['call']}): {scene['content_words']} content words; "
                f"by first source {json.dumps(scene['words_by_first_source'])}; "
                f"{scene['echoed_sequences']} 2-3 word sequences found in the request, "
                f"{scene['model_supplied_sequences']} supplied by the model"
            )
            lines.append(f"    model-supplied words: {', '.join(scene['model_supplied_words'])}")
            for word in trace_words:
                row = scene["words"].get(word.lower())
                if row is None:
                    continue
                grams = sorted(
                    f"{gram} <- {info['first_source']}"
                    for gram, info in scene["sequences"].items()
                    if word.lower() in gram.split()
                )
                lines.append(
                    f"    {word}: count {row['count']}, first source {row['first_source']}, "
                    f"sources {row['sources']}; sequences: {'; '.join(grams) or 'none'}"
                )
    return "\n".join(lines)


def _read(path: Path | None) -> str | None:
    return None if path is None else path.read_text(encoding="utf-8")


def baseline_lock_refusal(holder: Path | None = None) -> str | None:
    """Why the baseline may not be built now, or None. The build is a sustained CPU and memory
    job over the 1.96 GB fictions file, so it runs only under the box lock with its own
    holder line, taken as the RUNBOOK says; this checks the lock, it never takes it."""
    holder = holder or BOX_LOCK_HOLDER
    try:
        line = holder.read_text(encoding="utf-8-sig")
    except OSError:
        line = None
    if line is not None and line.startswith(BASELINE_HOLDER_PREFIX):
        return None
    held = "absent" if line is None else f"held by: {line.strip()}"
    return (
        f"refused: --build-baseline runs only under the box lock, with {holder} starting "
        f"{BASELINE_HOLDER_PREFIX!r} ({held}). Check the process list, then: "
        f'mkdir runs/box.lock && echo "{BASELINE_HOLDER_PREFIX}: <who>, <when>" '
        "> runs/box.lock/holder"
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=HEADER)
    parser.add_argument("--listing", type=Path)
    parser.add_argument("--chapter", type=Path)
    parser.add_argument("--draw", type=Path, help="a draw folder: concept, calls/*.json")
    parser.add_argument("--concept", type=Path, help="default: DRAW/concept/concept.json")
    parser.add_argument("--trace", action="append", default=[], help="print a word's provenance")
    parser.add_argument("--json", type=Path, dest="json_out")
    parser.add_argument("--baseline", type=Path, default=BASELINE)
    parser.add_argument("--table", type=Path, default=FREQUENCY_TABLE)
    parser.add_argument("--build-baseline", action="store_true")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if args.build_baseline:
        refusal = baseline_lock_refusal()
        if refusal:
            print(refusal, file=sys.stderr)
            return 2
        missing = [path for path in BUILDER_INPUTS if not path.is_file()]
        if missing:
            print(f"missing input: {', '.join(str(path) for path in missing)}", file=sys.stderr)
            return 2
        built = build_baseline(out=args.baseline, table_out=args.table)
        print(HEADER)
        print(json.dumps(built["sources"], indent=1))
        print(json.dumps(built["frequency_base"], indent=1))
        return 0

    concept_path = args.concept
    if concept_path is None and args.draw is not None:
        candidate = args.draw / "concept" / "concept.json"
        concept_path = candidate if candidate.is_file() else None
    inputs = [path for path in (args.listing, args.chapter, args.draw, concept_path) if path]
    missing = [path for path in inputs if not path.exists()]
    if missing or not (args.listing or args.chapter or args.draw):
        print(
            f"missing input: {', '.join(map(str, missing)) or 'no --listing, --chapter or --draw'}",
            file=sys.stderr,
        )
        return 2
    listing = _read(args.listing)
    concept = json.loads(concept_path.read_text(encoding="utf-8")) if concept_path else None
    task = recorded_listing_task(args.draw, listing) if args.draw and listing is not None else None
    result = report(
        listing=listing,
        chapter=_read(args.chapter),
        concept=concept,
        task=task,
        task_source="recorded listing request's system text",
        draw=args.draw,
        baseline_path=args.baseline,
        table_path=args.table,
    )
    print(render(result, trace_words=args.trace))
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
