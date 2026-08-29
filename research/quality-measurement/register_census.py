"""Two code-only register counters, and the honest limits of each.

**What this is for.** Read 7 §4.3 and §4.4 route two defect classes to the instrument side, and
both are register rather than story: a *narrating-the-inference* tell the operator named in two
books by two writers, and a *vocabulary friction* class now at its third sighting. Neither has a
counter. This module is the counter, and the comparison that makes it mean anything: a tell only
matters if we do it more than the genre does, so every number here is reported ours-beside-market
or not at all.

**No model reads anything here.** Both counters are regex and arithmetic over text. That is the
`BRIEF.md` §2 lesson applied before the fact: the ledger's twenty-one dead proxies died to
controls, and Pass 4's model judges died to positional artifacts, so a defect class that *can* be
counted mechanically is counted mechanically or left alone.

**The operator's quotes are fixtures and never prompt text** (§97.1). `GLOSS_FIXTURE` below holds
the two instances the operator named, as test material for a detector. Nothing in this module is
read by any generation surface, and nothing under `src/litharness/` imports it.

## What each counter can and cannot do, measured before the market half was opened

**The gloss counter splits into two tiers, and the split is forced by the fixtures themselves.**
Tier A is the operator's exact class — a narratorial clause stating what was *understood*, *meant*
or did not need *asking*. Tier B is the syntactic cousin that states *manner* by generic
comparison (*"the way you say a price"*). They are reported separately and never summed, because
a count that pooled them would be a number named for a defect it does not measure — the
`fragment_rate` failure §150.4 deleted a field for.

**Tier A is scarce in our own prose and that is the first result, not a bug.** Over the shelf's
chapters the generic-human shape (A1) fires exactly on its own two fixture instances and nowhere
else. What rescued the counter from being a lookup of its own fixture was a measured recall hole:
the `which meant …` shape (A2) does the same job with no generic subject at all, and hand-check
found it doing it five more times. A1 and A2 are both reported, and their sum is what "tier A"
means.

**Four narrowings, each from a measured false positive**, which is the discipline §116.5 and
§116.8 record three times over for word guards:

1. a generic quantifier post-modified into a specific referent is not generic — *"the way people
   **at the Stairhead** said the word fire"* names an in-world group and is doing real work;
2. `they` is out of the generic class entirely: in narrative prose it is anaphoric, and the
   instance that taught this had it pointing at two named women;
3. `like` is not a trigger. It is a general simile marker and drew three ordinary similes in ten
   sampled market hits;
4. speech is masked before scanning, because the class is a *narratorial* gloss and inside
   dialogue these shapes are ordinary talk.

And one exclusion that is a distinction rather than a narrowing: `which told <somebody>` attributes
the inference to a **character**, which is point-of-view interiority and not a narratorial gloss.
Three instances are excluded on this rule and five kept.

**Narrowings 3 and 4 came from the market half and could not have come from ours**, which is the
transferable lesson of this module. Precision was hand-checked on our own chapters, looked clean,
and was not: our prose simply carries less dialogue of the shape that breaks it. A detector that
is exact on the half that motivated it and loose on the half it is compared against manufactures
the comparison out of its own error rate. Both halves get hand-checked, and the run keeps a sample
of market hits (`market_tier_a_hits_for_hand_check`) so the check is repeatable rather than
remembered. Neither narrowing removed a single hit from our own shelf — tier A stayed at 7 — which
is what a precision fix rather than a shrink looks like.

**The friction counter cannot catch half of what the operator named, and says so.** The four
quoted words are two different things. *awnings* and *trestle* are rare words, and a corpus-derived
commonness floor finds them. *triage meetings* and *live build* are **common words in an uncommon
combination**, and no unigram floor can reach them — so a bigram floor is computed beside the
unigram one and reported separately. Neither is claimed to cover the other.

**Proper nouns are excluded and this is the control that matters.** Invented names are rare by
construction — *Ambry*, *Corin*, *Nessa* would each score as maximum friction — and a reader
accepts a character's name. Counting them would make the census a measure of how many names a
book coins. `proper_nouns` finds them by capitalisation away from sentence start, which is
mechanical, and the rate is reported both ways so the exclusion's size is visible.

**No bar is declared over anything here.** Both counters emit distributions. The four
attainability checks have not been run on any quantity in this module and no threshold is
proposed; §81, §85, §87 and §89 are the four entries on what declaring one costs.

    uv run python research/quality-measurement/register_census.py --ours

reads the shelf only and needs no corpus. The market half reads the derived intermediate and is
a separate invocation; one sustained job at a time on this box, CPU jobs included (CLAUDE.md).
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Iterable
from hashlib import sha256
from itertools import pairwise

#: Frozen before the market half was opened. The reading of every number below is fixed here so
#: it cannot be arranged around what the shards turn out to say. `voice_descriptors` is the shape.
PRE_REGISTRATION: dict[str, str] = {
    "question": (
        "do our chapters narrate the reader's inference, and use rarer words, at a higher rate "
        "than the genre's own chapters do"
    ),
    "predicted": (
        "no direction is predicted for either counter. This is a census: the operator named "
        "both classes from two books, and whether either is OURS rather than the genre's is "
        "exactly what is unknown. A market rate at or above ours is a real result and the "
        "cheap one, because it dissolves the instrument question rather than funding it"
    ),
    "primary": (
        "per-chapter rate distributions, ours against market, reported as median and the p10-p90 "
        "range at the real n. Tier A and tier B of the gloss counter are never summed; unigram "
        "and bigram friction are never summed"
    ),
    "unreadable": (
        "fewer than 500 market chapters clear the pool after quarantine subtraction, or our own "
        "half holds fewer than 15 chapters. The first leaves a frequency table whose tail is "
        "noise, and the tail is where awnings and trestle live; the second leaves a distribution "
        "with no p10-p90 worth printing"
    ),
    "control_same_pass": (
        "chapter length is reported beside every rate, because type variety rises with length "
        "and both counters are per-token. Proper-noun rate is reported beside friction, because "
        "excluding names is the load-bearing choice and its size has to be visible. BRIEF.md "
        "section 5: the control is computed in the same pass or the headline means nothing"
    ),
    "held_out_base": (
        "the frequency base excludes every chapter it scores, on both sides. A market chapter "
        "left in the base supplies its own rare words a floor-clearing count from itself while "
        "our chapters get no such contribution, so the comparison would read out in-base versus "
        "out-of-base rather than common versus rare. This was not foreseen: a smoke run over 800 "
        "rows returned a bigram rate of 0.000 for every market chapter and 344.9 for every one "
        "of ours, which is that artifact at full strength, and it is the coverage failure "
        "BRIEF.md section 2 pass 5 records for minimum cross-paragraph NCD. Ours and the scored "
        "market sample are both wholly outside the base that scores them"
    ),
    "quarantine": (
        "the 26 descriptor-half fiction ids of stage-0 150.1 are subtracted from the market half "
        "before any comparison, and the pre-subtraction and post-subtraction row counts are both "
        "reported. They aimed something, so an ours-versus-market number including them is partly "
        "our own aim measured against itself"
    ),
    "locating_control": (
        "both counters are reported LitRPG against non-LitRPG inside the market half, which the "
        "intermediate's `litrpg` boolean supplies for free. This is a locating check rather than "
        "a hypothesis: if a counter scores the same on both, it is measuring something general "
        "about published prose rather than anything about this genre's register, and an "
        "ours-versus-market gap on it would be the harder to read for it. Added before the market "
        "half was opened and with our own half unmeasured against it"
    ),
    "no_bar": (
        "nothing here declares a bar, a floor or a threshold. No quantity in this module has had "
        "the four attainability checks run on it, and none is proposed for a gate"
    ),
    "no_model": (
        "no model call at any point, in either counter, for either half. Regex and arithmetic "
        "only, so the whole census is free and rerunnable"
    ),
}


def registration_digest() -> str:
    """Address the registration by its bytes, so a later edit cannot pass as the original."""
    material = json.dumps(PRE_REGISTRATION, sort_keys=True).encode()
    return sha256(material).hexdigest()[:16]


# --------------------------------------------------------------------------------------------
# Counter 1: narrating the inference
# --------------------------------------------------------------------------------------------

#: The two instances the operator named, in two books by two writers. Fixture material for a
#: detector and nothing else: no line here reaches a prompt (§97.1).
GLOSS_FIXTURE: tuple[str, ...] = (
    "each lid stamped, each stamp turned to face the aisle so nobody had to ask.",
    'Terry said, "What," in the way people say it when they mean nothing.',
)

#: Hits that a first version drew and a hand-check refused. Each one narrowed the pattern, and
#: each stays here as a test so the narrowing cannot be lost.
GLOSS_REFUSED: tuple[str, ...] = (
    # `they` is anaphoric here: it points at the two women, not at people in general.
    "A boy was wringing straw out on a step in front of two women who had come to watch him "
    "do it, so they could say afterwards that they had.",
    # A generic quantifier located into a specific in-world group is not generic.
    "She said it the way people at the Stairhead said the word fire.",
    "Ilke had known Nessa Ashe's trees the way everyone at the weigh-house had known them.",
    # The inference is attributed to a character: point of view, not a narratorial gloss.
    "He came to the counter out of turn and nobody stopped him, which told Silas his coat was "
    "worth more than the queue's patience.",
)

#: **`you` is countable for tier B and not for tier A, and the split is measured rather than
#: tidy.** Generic `you` (*"the way you say a price"*) and second-person `you` are the same word,
#: and this corpus defeats every mechanical way of telling them apart: chapters carry unbalanced
#: quotes (one sampled chapter has 133 straight quotes, another 75 `“` against 71 `”`), so
#: positional quote-pairing mispairs everything after the first stray and masks the gaps between
#: dialogue instead of the dialogue; and at least one sampled story is written in **second
#: person** throughout, where no quote mask can help at all. Every one of five sampled market
#: tier-A false positives came from `you`. Dropping it from tier A costs our own shelf nothing —
#: both operator-named instances use `nobody` and `people` — so tier A keeps the class the
#: operator actually named and gives up a word it cannot count.
_GENERIC_CORE = (
    r"(?:nobody|no one|no-one|anybody|anyone|everybody|everyone|somebody|someone|people|"
    r"a person|most people)"
)
_GENERIC_A = _GENERIC_CORE
_GENERIC_B = _GENERIC_CORE[:-1] + r"|you)"
#: A locating phrase after the quantifier makes it specific. Two measured false positives.
_SPECIFIER = (
    r"(?:\s+(?:at|in|on|from|of|around|near|by|with|under|above)\s+"
    r"(?:the|a|an|his|her|their|this|that)\b)"
)
#: Tier A verbs: the gloss claims something about understanding, meaning, or needing to ask.
_PRAG_A = (
    r"(?:ask(?:s|ed)?|mean(?:s|t|ing)?|know(?:s|n)?|knew|need(?:s|ed)?|understand(?:s)?|"
    r"understood|realis(?:e|es|ed)|realiz(?:e|es|ed)|notice(?:s|d)?|has to|have to|had to|"
    r"would have to)"
)
#: Tier B verbs: the gloss claims manner. Same syntax, a different assertion.
_PRAG_B = r"(?:say(?:s|ing)?|said|do(?:es)?|did|talk(?:s|ed)?|speak(?:s)?|spoke|hold(?:s)?|held)"

#: One alternation rather than several compiled patterns per tier. The census runs over tens of
#: thousands of chapters and one pass per tier is the difference.
#:
#: **`like` was a trigger and was removed on a market hand-check, which is the third narrowing.**
#: It is a general simile marker and cannot tell a gloss from a comparison: over a sample of
#: market hits it drew *"it's not like anyone had ever asked her"*, *"kind of like someone we both
#: know"* and *"You looked like you needed one"* — three ordinary similes in ten sampled hits.
#: Our own chapters had not exposed this because they carry less dialogue of that shape, which is
#: the reason precision has to be hand-checked on **both** halves of a comparison and not just the
#: half that motivated the instrument.
_TRIGGERS: tuple[tuple[str, str], ...] = (
    (r"so\s+", "so"),
    (r"(?:in\s+)?the\s+way\s+", "way"),
    (r"which\s+is\s+(?:what|how|why)\s+", "which_is"),
    (r"enough\s+(?:that|for)\s+", "enough"),
    (r"as\s+(?:if|though)\s+", "as_if"),
)
_TRIGGER_ALT = "|".join(pattern for pattern, _ in _TRIGGERS)


def _generic_patterns(verbs: str, generic: str) -> tuple[tuple[str, re.Pattern[str]], ...]:
    return (
        ("generic", re.compile(
            rf"\b(?:{_TRIGGER_ALT}){generic}(?!{_SPECIFIER})\b[^.?!;]{{0,40}}?\b{verbs}\b",
            re.IGNORECASE,
        )),
    )


_TIER_A1 = _generic_patterns(_PRAG_A, _GENERIC_A)
_TIER_B = _generic_patterns(_PRAG_B, _GENERIC_B)

#: A2: the import gloss with a propositional complement and no subject at all. `which told
#: <somebody>` is simply not matched: that attributes the inference to a character, which is
#: interiority. `which meant` carries no such attribution.
#:
#: **The trailing context is a lookahead and not consumed, which is a counting decision.** A
#: consuming window merged *"which meant it was a job, which meant somebody would make it a
#: job"* into one hit, and the merge was an artifact of the window's length rather than a claim
#: that a gloss chain is one gloss. Each clause now counts once.
_TIER_A2 = (
    ("which_meant", re.compile(r"\bwhich\s+(?:meant|means)\b(?=[^.?!;]{0,60})", re.IGNORECASE)),
)


_DIALOGUE = re.compile(r"[\"“”][^\"“”]{0,600}?[\"“”]")


def narration_only(text: str) -> str:
    """Blank out double-quoted speech, preserving offsets so hit positions stay true.

    **The class is a *narratorial* gloss, so speech is not eligible, and a market hand-check is
    what made this non-optional.** Inside dialogue the same shapes are ordinary talk: *"Just so
    you know"* is a discourse marker and *"so you'll have to finish his shift"* is one character
    telling another what to do. Neither is a narrator performing the reader's deduction, and both
    were being counted. Our own chapters carry less dialogue of that shape, so the defect was
    invisible until the market half was sampled.

    Only double quotes are masked. Single quotes are ambiguous against the apostrophe in English
    and masking them would eat contractions, which is a larger error than the one being fixed.
    """
    return _DIALOGUE.sub(lambda m: " " * len(m.group(0)), text)


def _scan(text: str, patterns: Iterable[tuple[str, re.Pattern[str]]]) -> list[tuple[str, str, int]]:
    """Non-overlapping hits, earliest pattern winning, so one clause counts once.

    The offset is returned because a hit string is not enough to locate itself: the A2 pattern
    matches only its trigger, so several hits in one chapter share a spelling and searching for
    the text would resolve every one of them to the first. Masking preserves offsets, so these
    index the original chapter.
    """
    hits: list[tuple[str, str, int]] = []
    spans: list[tuple[int, int]] = []
    for name, pattern in patterns:
        for match in pattern.finditer(text):
            if any(start <= match.start() < end for start, end in spans):
                continue
            spans.append((match.start(), match.end()))
            hits.append((name, match.group(0).strip(), match.start()))
    return hits


def gloss_hits(text: str) -> dict[str, list[tuple[str, str, int]]]:
    """Tier A1, A2 and B hits for one text, each list kept separate on purpose.

    Speech is masked first: every tier here claims something about the *narrator*.
    """
    prose = narration_only(text)
    return {"a1": _scan(prose, _TIER_A1), "a2": _scan(prose, _TIER_A2), "b": _scan(prose, _TIER_B)}


def gloss_counts(text: str) -> dict[str, int]:
    """Counts only. `tier_a` is A1 + A2; tier B is never folded into it."""
    hits = gloss_hits(text)
    return {
        "a1": len(hits["a1"]),
        "a2": len(hits["a2"]),
        "tier_a": len(hits["a1"]) + len(hits["a2"]),
        "tier_b": len(hits["b"]),
    }


# --------------------------------------------------------------------------------------------
# Counter 2: vocabulary friction
# --------------------------------------------------------------------------------------------

#: The operator's four, third sighting of the class. The first two are rare words; the second
#: two are common words in a rare combination, which is why there are two counters below.
FRICTION_FIXTURE_UNIGRAM: tuple[str, ...] = ("awnings", "trestle")
FRICTION_FIXTURE_BIGRAM: tuple[str, ...] = ("triage meetings", "live build")

_WORD = re.compile(r"[a-z]+(?:'[a-z]+)?")
_SENTENCE_START = re.compile(r"(?:^|[.!?\"']\s+|\n)\s*")


def tokens(text: str) -> list[str]:
    """Lowercase alphabetic tokens. One tokenizer for both halves of every comparison."""
    return _WORD.findall(text.lower())


def bigrams(toks: list[str]) -> list[str]:
    return [f"{a} {b}" for a, b in pairwise(toks)]


def proper_nouns(text: str) -> set[str]:
    """Words capitalised away from sentence start, lowercased.

    Invented names are rare by construction and a reader accepts them, so counting them would
    make the friction census a count of how many names a book coins. Sentence-initial capitals
    are excluded because every sentence starts with one; a word that is *only* ever
    sentence-initial therefore does not qualify, which is the intended conservatism.

    **A word must be capitalised in the majority of its appearances to count, and that rule
    came from a measured failure.** Taking any once-capitalised token made the name set collide
    with ordinary homographs — one character called *Will* or *Mark* or *May* turned every
    modal, every verb and every month in the chapter into a name, and the measured proper-noun
    rate came back at 18-22% of all tokens. Requiring the majority is what separates a name from
    a sentence that happened to start with a common word.
    """
    starts = {m.end() for m in _SENTENCE_START.finditer(text)}
    capital: Counter[str] = Counter()
    for match in re.finditer(r"\b[A-Z][a-z]+\b", text):
        if match.start() not in starts:
            capital[match.group(0).lower()] += 1
    if not capital:
        return set()
    lower = Counter(tokens(text))
    return {word for word, n in capital.items() if n * 2 > lower.get(word, 0)}


def frequency_table(texts: Iterable[str]) -> Counter[str]:
    """Corpus word counts. Derived data: numbers keyed by word, and no corpus text retained."""
    table: Counter[str] = Counter()
    for text in texts:
        table.update(tokens(text))
    return table


def friction(
    text: str, table: Counter[str], *, total: int, per_million_floor: float = 1.0
) -> dict[str, float]:
    """Rate of tokens rarer than the floor, with the proper-noun control reported beside it.

    `per_million_floor` is a reporting parameter, not a bar: the caller sweeps it and the
    distribution is what gets read. Nothing in this module declares a value for it.
    """
    toks = tokens(text)
    names = proper_nouns(text)
    if not toks or total <= 0:
        return {"tokens": 0, "rare_rate": 0.0, "rare_rate_with_names": 0.0, "name_rate": 0.0}
    scale = 1_000_000.0 / total

    def is_rare(word: str) -> bool:
        return table.get(word, 0) * scale < per_million_floor

    rare_all = [w for w in toks if is_rare(w)]
    rare_no_names = [w for w in rare_all if w not in names]
    return {
        "tokens": len(toks),
        "rare_rate": 1000.0 * len(rare_no_names) / len(toks),
        "rare_rate_with_names": 1000.0 * len(rare_all) / len(toks),
        "name_rate": 1000.0 * sum(1 for w in toks if w in names) / len(toks),
        "per_million_floor": per_million_floor,
    }


def bigram_friction(
    text: str, table: Counter[str], *, total: int, per_million_floor: float = 0.1
) -> dict[str, float]:
    """The jargon half: common words in an uncommon combination.

    A unigram floor cannot reach `live build` or `triage meetings` because every word in them is
    ordinary. This is the counter for that half, and it is never summed with the unigram one.
    """
    grams = bigrams(tokens(text))
    if not grams or total <= 0:
        return {"bigrams": 0, "rare_bigram_rate": 0.0}
    scale = 1_000_000.0 / total
    rare = [g for g in grams if table.get(g, 0) * scale < per_million_floor]
    return {
        "bigrams": len(grams),
        "rare_bigram_rate": 1000.0 * len(rare) / len(grams),
        "per_million_floor": per_million_floor,
    }


__all__ = [
    "FRICTION_FIXTURE_BIGRAM",
    "FRICTION_FIXTURE_UNIGRAM",
    "GLOSS_FIXTURE",
    "GLOSS_REFUSED",
    "PRE_REGISTRATION",
    "bigram_friction",
    "bigrams",
    "frequency_table",
    "friction",
    "gloss_counts",
    "gloss_hits",
    "proper_nouns",
    "registration_digest",
    "tokens",
]
