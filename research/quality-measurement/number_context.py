"""The number-context census: what a chapter's exact quantities are *attached to*.

Research code, outside `src/`: nothing here is imported by the package and nothing
generation-side may read it. It answers one operator sentence, emphasised in read 8 §4.1 and
again in the first-principles diagnosis:

> *"Useless numbers unrelated to anything keep coming up ... describing days events etc instead
> of abilities."*

`progression_cadence.py` is the neighbour and the method precedent. It asks **how often a
progression event happens**; this asks **where a number lands when one is written**. The two
partition the same page: its four families are the SYSTEM side of the operator's sentence, this
one builds the MUNDANE side and the contrast between them.

**This census is code-only. No model is called, nothing is ranked, and no bar is declared.**
The error profile is `progression_cadence`'s and must be read the same way: **reliability is 1.0
by construction and precision is measured by hand, not by a model.** The same chapter always
returns the same counts. Whether a located number really belongs to the family it was assigned
is checked by the exhaustive hand-count of read 8 §4.1 on one chapter, the pinned cases in
`tests/test_number_context.py`, and the market hit samples this module retains for the same
check on the other half — never by anything automatic.

**Density is a density of located SURFACES, not of harm.** A chapter with more mundane-anchored
numbers is not worse. Nothing here asks whether any number bothered a reader, and nothing here
may gate, rank or steer a draft.

**Corpus rule (RS1, and `corpus_io`'s own):** market text lives only in the gitignored
intermediate under `derived/`. The committed results file carries ids and numbers. The one
exception is the hand-check sample, which is the same exception `register_census.py` takes and
for the same reason — a precision claim about the market half that cannot be re-checked is not a
precision claim — and it is kept to short spans in a *local* sidecar, never in the committed
artifact.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

# --------------------------------------------------------------------------- the frozen block

#: Everything that defines what a numeric mention IS and which family it lands in. Changing any
#: of it changes the instrument, so it is content-addressed and `selftest` refuses a drift.
#:
#: **Frozen before the market half was opened, and iterated on our own shelf before that.**
#: `register_census.PRE_REGISTRATION` is the shape and the precedent. Every narrowing below came
#: from a hand-check against text on disk — read 8 §4.1's exhaustive list for one chapter, and
#: read 4's whole-book count — and each one is recorded here with the case that forced it.
PRE_REGISTRATION: dict[str, Any] = {
    "instrument": "number_context.v0",
    "question": (
        "when a chapter writes an exact quantity, what is the quantity attached to: a system "
        "the character interacts with, or a mundane surface (a calendar, an age, a price, a "
        "measure, a count of objects)?"
    ),
    "predicted": (
        "REGISTERED DIRECTION, fixed before the market half was opened. The first-principles "
        "diagnosis predicts that the market's LitRPG-tagged chapters carry a HIGHER "
        "system-to-mundane ratio than our own shelf does, and that our shelf sits near the "
        "floor of the system distribution. Two named ways this can come out the other way, "
        "both of which are results and not failures: (a) the market's LitRPG may itself be "
        "mundane-heavy in absolute terms, in which case the diagnosis's implicit picture of "
        "the genre is wrong and only the RATIO can carry it; (b) our own mundane density may "
        "be ORDINARY for published fiction, in which case what the operator noticed is the "
        "absence of the system half and not an excess of the mundane half. The census reports "
        "both halves separately so either reading is legible."
    ),
    "primary": (
        "per-chapter density distributions (p50/p75/p90 and coverage) for system-anchored and "
        "for mundane-core-anchored numeric mentions, ours against market-LitRPG against "
        "market-not-LitRPG, plus the per-chapter system share of anchored mentions"
    ),
    "unit": (
        "one NUMERIC MENTION. Adjacent numerals are one mention -- `twenty-two`, `one hundred "
        "and fifty` and `two or three` each count once -- because a merged numeral is one act "
        "of precision by the writer. This is the unit rule `progression_cadence` states for "
        "furniture runs, applied to numerals."
    ),
    "families": {
        "system_magnitude": (
            "A CARDINAL quantity attached to a system anchor: `level 12`, `300 experience`, "
            "`Strength 14`, `+5`, `240 -> 300`. Also every cardinal inside a system furniture "
            "LINE, by location rather than by lexicon. This is the LitRPG sheet's own number."
        ),
        "system_ordinal": (
            "An ORDINAL attached to the same anchors: `fourth grade`, `THIRD TIER`, `second "
            "rank`. **The split from `system_magnitude` was forced by our own shelf and is the "
            "sharpest thing this instrument does.** Every one of the eleven system-anchored "
            "numbers on our shelf is an ordinal on a ladder word and not one is a magnitude, "
            "which is read 8 §4.2's finding -- the progression beats fired into a guild "
            "bureaucracy's ordinal titles -- arriving as a count. A ladder position and a "
            "quantity on a sheet are different objects and a single `system` column would have "
            "hidden the difference."
        ),
        "calendar_duration": (
            "The quantity is time: days, weeks, months, years, hours, minutes, nights, "
            "o'clock. The operator's own list is mostly this family."
        ),
        "age": "The quantity is somebody's age.",
        "money": "The quantity is a price or a purse.",
        "measure": (
            "The quantity is a distance, a weight, a volume or a percentage -- a unit of "
            "measurement that is not time and not money."
        ),
        "object_count": (
            "The quantity counts things: thirty jars, two women, four of the guild's jars. "
            "REPORTED SEPARATELY AND NEVER SUMMED INTO `mundane_core`, because its head noun is "
            "found by a stopword rule rather than a closed lexicon and its precision is "
            "therefore the lowest in the table."
        ),
        "ordinal_enumeration": (
            "An ordinal that resolves to no closed-lexicon family: `the second jar`, `the "
            "twenty-second`, `first glass`. Reported separately and never pooled -- see "
            "`refused` for why an ordinal date cannot be separated from an ordinal enumeration "
            "here."
        ),
        "multiplicative": "`three times`, `four times over`. Counted, never pooled.",
        "unanchored": (
            "A numeral with no head at all: `the condemned one`, `Eight more`. Counted so the "
            "total is honest, and excluded from every headline."
        ),
    },
    "priority": [
        "furniture_line_location",
        "shape_system",
        "age",
        "system",
        "calendar_duration",
        "money",
        "measure",
        "multiplicative",
        "object_count",
        "ordinal_enumeration",
        "unanchored",
    ],
    "never_summed": (
        "`mundane_core` is calendar_duration + age + money + measure -- the four closed-lexicon "
        "families. `object_count`, `ordinal_enumeration`, `multiplicative` and `unanchored` are "
        "each reported on their own line and none is added into it. A count named for one "
        "defect that measures another is the lying column stage-0 §150.4 deleted a field for, "
        "and `register_census`'s tier A / tier B split is the same rule."
    ),
    "summed_and_why": (
        "`system_any` IS the sum of `system_magnitude` and `system_ordinal`, and it is the one "
        "sum this instrument allows. The two are the same assertion -- a number attached to a "
        "system anchor -- differing only in the number's grammatical form, unlike the tier A / "
        "tier B split, which is two different assertions about the narrator. Both components "
        "are always printed beside the sum so a reader can refuse the pooling; the magnitude "
        "column alone is the one to read when the question is whether a sheet exists."
    ),
    "normalisation": (
        "NFKC; curly quotes and dashes folded to ASCII; horizontal whitespace collapsed WITHIN "
        "a line; line structure preserved, because a system furniture line is recognised by "
        "being a whole line."
    ),
    "line_shapes_copied_deliberately": (
        "The furniture line shapes are a COPY of `progression_cadence.v0`'s, not an import. A "
        "registration that is content-addressed must be self-contained: importing the "
        "neighbour's frozen block would let its digest change this instrument silently. The "
        "copy is stated here so the duplication is a decision on the record rather than drift, "
        "and `selftest` pins the shapes that matter."
    ),
    "control_same_pass": [
        "LitRPG against not-LitRPG on the same counters, inside the market half. The system "
        "counter MUST separate them -- a genre whose defining artifact is a system carries more "
        "system numbers or this instrument is measuring something else. This is the validity "
        "arm, computed in the same pass (BRIEF.md §5).",
        "chapter length is reported beside every density, because both are per-1,000-words and "
        "a length difference between halves would move them together.",
        "spelled against digit mentions are reported separately for every population. Our own "
        "prose has been measured at ZERO digits in a whole book (read 4), so a counter that saw "
        "only digits would report our shelf's mundane precision as absent when it is 165 "
        "instances.",
        "the per-fiction collapse is reported beside the per-chapter one, because fifty "
        "chapters of one serial share an author and a tic (BRIEF.md §6(5)).",
    ],
    "quarantine": (
        "the 26 descriptor-half fiction ids of stage-0 §150.1 are subtracted from the market "
        "half before any ours-versus-market number, and the pre-subtraction and "
        "post-subtraction row counts are both reported."
    ),
    "declares_no_bar": (
        "No target density, ratio or floor is declared here, for any family, for either half. A "
        "bar needs §81/§85/§87/§89's four attainability checks -- range at the real n, "
        "direction, independent unit, non-empty subgroup -- and this file runs none of them. It "
        "names distributions and stops."
    ),
    "narrowings_from_the_market_half": (
        "THREE PRECISION FIXES MADE AFTER THE MARKET HALF WAS OPENED, and the disclosure is "
        "part of the record. The frozen pre-market registration is committed at 96b622f under "
        "digest 134ae6f2a80bd274, so the drift is auditable rather than hidden, and the "
        "pre-narrowing full-corpus numbers are kept at "
        "`results/number-context.pre-narrowing.json`. **The aggregate of a 2,000-row smoke pass "
        "had been seen before these were written**, so each is named with the direction it "
        "moves this census's own headline. `register_census` is the precedent -- its narrowings "
        "3 and 4 also came from the market half -- and BRIEF.md §5's rule requires it: a "
        "detector exact on the half that motivated it and loose on the half it is compared "
        "against manufactures the comparison out of its own error rate. (1) A determiner after "
        "a head ends the noun phrase; `one more thing-your abilities` was a stat. Direction: "
        "lowers the market's system and mundane columns slightly, which FAVOURS the headline. "
        "(2) `one` leaves the copula-age pattern and a following `of` ends it; `he is one of "
        "the people in this town` was an age. Direction: lowers the mundane column on both "
        "halves. (3) Structural headings in any of the shards' languages are skipped, and an "
        "`english_share` control is reported so non-English rows are visible; `Capitulo 6` and "
        "`Cena 1` were object counts, and a non-English chapter scores near zero on every "
        "English lexicon here. Direction: RAISES the market's mundane density and CUTS AGAINST "
        "the headline, which is why it is the one of the three that had to be built rather "
        "than noted."
    ),
    "refused": {
        "indefinite_article_durations": (
            "`an hour of rain` -- the operator's own item -- is NOT counted. `a` and `an` are "
            "not numerals, and admitting them would sweep in `a moment`, `a second`, `a while` "
            "and every indefinite noun phrase in the language, which is not precision. The "
            "operator's list therefore has one member this instrument cannot see, and that is "
            "stated rather than patched."
        ),
        "ordinal_dates": (
            "`the fifteenth in the spring almanac` is a date and `the twenty-second jar` is an "
            "enumeration, and no closed rule here separates them: the distinguishing evidence "
            "is a governing noun phrase that needs a parser. Both land in "
            "`ordinal_enumeration`, which is why that family is never pooled into "
            "`mundane_core`. Attempted and rejected: treating a bare high ordinal as a date "
            "(fitted to one instance), and treating a season word within four tokens as a date "
            "context (drew `the spring almanac`, which is a book and not a date)."
        ),
        "twice_thrice_dozen": (
            "`twice`, `thrice`, `once` and `dozen` are not in the numeral lexicon. The first "
            "three are adverbs whose head is a verb rather than a quantity, and `dozen` "
            "collides with `dozens of`, which is vagueness rather than precision. A known "
            "recall hole, named."
        ),
        "spelled_out_ages_without_a_trigger": (
            "`she was nine` is caught by the copula trigger; `nine, and never once expecting "
            "it` is not. The age family is the smallest in the table and is not load-bearing "
            "for any headline."
        ),
        "a_harm_claim": (
            "Nothing here claims a mundane-anchored number harms a reader. The operator said "
            "one did; that is a defect harvest and not data (§95, §97.1), and this instrument "
            "converts it into a count and no further."
        ),
    },
    "residuals": [
        "PRECISION IS HAND-MEASURED, NOT MODEL-MEASURED, and the hand-check is exhaustive on "
        "exactly one chapter -- read 8 §4.1's own list for Unlicensed Weather chapter 1. Every "
        "other precision statement rests on a sample.",
        "RECALL IS UNMEASURED against any exhaustive market count. A chapter whose quantities "
        "are all written as indefinite articles or as `twice` scores zero.",
        "`object_count` finds its head by a stopword rule, so a numeral followed by an adverb "
        "can take an adverb as its head. The family decision survives that (the mention is "
        "still a count) but the recorded head is then wrong, which is why heads are reported "
        "for hand-check and never aggregated.",
        "A single large stat table contributes as many system mentions as it holds numbers. "
        "That is the honest reading of the question -- those numbers ARE on the page -- but it "
        "makes the system density heavy-tailed, so coverage is the statistic to believe, as "
        "`progression_cadence`'s validity arm already argues.",
        "`gold`, `silver` and `copper` are money here and never system, although in this genre "
        "they are frequently both. Money is reported on its own line so the choice is visible.",
        "Chapter text is whatever the shard holds, including front matter the reject list "
        "misses.",
    ],
}


def registration_digest() -> str:
    """Address the registration by its bytes, so a later edit cannot pass as the original."""
    material = json.dumps(PRE_REGISTRATION, sort_keys=True, ensure_ascii=False)
    return sha256(material.encode("utf-8")).hexdigest()[:16]


REGISTRATION_DIGEST = registration_digest()


# --------------------------------------------------------------------------- normalisation

# Every key here is an "ambiguous" character on purpose -- folding them to ASCII is the whole
# job, so the lint that flags them is flagging the intent.
_FOLD = {
    "‘": "'", "’": "'", "“": '"', "”": '"',  # noqa: RUF001
    "–": "-", "—": "-", "−": "-", " ": " ",  # noqa: RUF001
}


def normalise(text: str) -> str:
    """NFKC, folded punctuation, horizontal whitespace collapsed inside lines.

    Line structure survives on purpose: a system furniture line is recognised by being a whole
    line, so a normaliser that reflowed paragraphs would delete the signal it preserves.
    """
    text = unicodedata.normalize("NFKC", text)
    for bad, good in _FOLD.items():
        text = text.replace(bad, good)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n"))


# --------------------------------------------------------------------------- furniture lines

# Copied from `progression_cadence.v0` on purpose; see `line_shapes_copied_deliberately`.
_RE_BRACKETED = re.compile(r"^\**\[[^\]]{1,200}\]\**[.!?]?$", re.IGNORECASE)
_RE_ANGLED = re.compile(r"^\**<[^>]{1,200}>\**[.!?]?$", re.IGNORECASE)
_RE_FRAME = re.compile(r"^[=\-_~*—─-╿\s]{3,}$", re.IGNORECASE)
_RE_STATLINE = re.compile(
    r"^\**[A-Za-z][A-Za-z '/()-]{0,28}\**\s*[:：]\s*"  # noqa: RUF001
    r"\**[^.!?\n]{0,40}\d[^.!?\n]{0,40}\**$",
    re.IGNORECASE,
)
_RE_REJECT = re.compile(
    r"^\**[\[<]?\s*(?:a/?n|author'?s? note|t/?n|translator|tl|edit|note|p\.?s\.?|"
    r"prev(?:ious)?|next|table of contents|toc|index|chapter\s+\d|patreon|discord|"
    r"advance chapters?|support|donate|vote|rating|spoiler|image|img|picture)\b",
    re.IGNORECASE,
)
_EDGE = "|*=-_~+ ─-╿│┃"


def is_furniture_line(line: str) -> bool:
    """True for an interface line the character reads rather than the narrator speaks.

    A bare rule of frame characters is a scene divider and is NOT furniture -- the correction
    `progression_cadence` records having made before it published a reading, kept here because
    the same `***` would otherwise put every fiction on the platform inside a status block.
    """
    if not line or _RE_REJECT.match(line) or _RE_FRAME.match(line):
        return False
    inner = line.strip(_EDGE).strip()
    if not inner or _RE_REJECT.match(inner):
        return False
    return bool(
        _RE_BRACKETED.match(inner) or _RE_ANGLED.match(inner) or _RE_STATLINE.match(inner)
    )


# --------------------------------------------------------------------------- the numeral class


def lexicon(source: str) -> frozenset[str]:
    """A closed word class, written as one space-separated string and frozen here.

    Every lexicon in this module is a *closed* list a reader has to be able to audit in one
    glance, which is what the string form buys over a list of quoted items three to a line. The
    frozenset is what the classifier uses; the string is what a reviewer reads.
    """
    return frozenset(source.split())


CARDINAL_WORDS = lexicon(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
    "fifteen sixteen seventeen eighteen nineteen twenty thirty forty fourty fifty sixty "
    "seventy eighty ninety hundred thousand million billion"
)
ORDINAL_WORDS = lexicon(
    "first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth "
    "thirteenth fourteenth fifteenth sixteenth seventeenth eighteenth nineteenth twentieth "
    "thirtieth fortieth fiftieth sixtieth seventieth eightieth ninetieth hundredth thousandth"
)
NUMERAL_WORDS = CARDINAL_WORDS | ORDINAL_WORDS

#: Words that may sit between two numerals without ending the mention. `two or three days` is
#: one act of precision, not two.
_LINKERS = frozenset({"and", "or", "to"})


# --------------------------------------------------------------------------- the lexicons

CALENDAR_WORDS = lexicon(
    "second seconds minute minutes hour hours day days week weeks fortnight fortnights month "
    "months year years yr yrs decade decades century centuries millennium millennia night "
    "nights morning mornings afternoon afternoons evening evenings winters summers springs "
    "autumns seasons weekdays weekends weekend o'clock oclock"
)
MONEY_WORDS = lexicon(
    "coin coins copper coppers silver silvers gold penny pennies pence shilling shillings "
    "crown crowns dollar dollars cent cents credit credits sovereign sovereigns florin florins "
    "ducat ducats yen euro euros"
)
MEASURE_WORDS = lexicon(
    "mile miles yard yards foot feet inch inches pace paces step steps league leagues metre "
    "metres meter meters kilometre kilometres kilometer kilometers centimetre centimetres "
    "acre acres hectare hectares stone stones ounce ounces gram grams kilo kilos kilogram "
    "kilograms gallon gallons pint pints litre litres liter liters quart quarts bushel bushels "
    "fathom fathoms furlong furlongs cubit cubits percent percentage"
)
#: Both directions: `Level 5` and `5 levels` are the same anchor from opposite sides.
SYSTEM_WORDS = lexicon(
    "level levels lvl rank ranks tier tiers grade grades stage stages skill skills ability "
    "abilities spell spells technique techniques title titles perk perks trait traits stat "
    "stats attribute attributes hp mp sp health mana stamina strength dexterity agility "
    "endurance vitality intelligence wisdom constitution charisma xp exp experience damage "
    "defense defence attack armor armour cooldown cooldowns affinity aura qi mastery "
    "proficiency hitpoints"
)
#: `points` earns its own note: generic in ordinary prose (`three points of order`) and central
#: in this genre (`five stat points`). It is kept in the system lexicon and the validity arm is
#: what says whether keeping it was right -- if it were carrying the separation on its own, the
#: not-LitRPG control would not sit below.
SYSTEM_WORDS = SYSTEM_WORDS | lexicon("point points")

_MULTIPLICATIVE = lexicon("time times")

#: Determiners and possessive-shaped tokens a head search steps over.
_SKIP = lexicon("the a an his her its their my our your this that these those")
#: `of` is the partitive that makes `four of the guild's jars` a count of jars -- but only
#: BEFORE a head has been found. After one, `of` opens a modifier of that head and the noun
#: phrase the numeral governs has already ended. **This distinction is the fix for a measured
#: false positive**: `the first surprise of the morning` was reaching `morning` and being
#: reported as a duration, when the numeral is enumerating surprises.
_PARTITIVE = lexicon("of")
#: Quantity modifiers that sit between a numeral and its head without being the head. `three
#: more days` is a duration; without this the search stops on `more` and the mention is lost.
_SOFT_SKIP = lexicon("more other same own all some no very just most each every both either")
#: A head must be a content word. These are the function words a numeral can be followed by when
#: its head noun is elided (`Eight more, and ...`), and taking one as a head would invent a
#: count that the sentence does not make.
_STOP = lexicon(
    "and or but so as at in on to for from with by into onto upon about after before again "
    "still only even back away here there now if because while until since though although "
    "like than when where which who what was were is are be been being had has have do does "
    "did more most other others same own all some any no not very just then out up down over "
    "under off never else too also both each every either neither it he she they them him us "
    "we you i me my mine yours theirs ours himself herself themselves itself myself would "
    "could should will shall may might must can"
)

_FAMILY_LEXICONS: tuple[tuple[str, frozenset[str]], ...] = (
    ("system", SYSTEM_WORDS),
    ("calendar_duration", CALENDAR_WORDS),
    ("money", MONEY_WORDS),
    ("measure", MEASURE_WORDS),
    ("multiplicative", _MULTIPLICATIVE),
)

FAMILIES = (
    "system_magnitude",
    "system_ordinal",
    "calendar_duration",
    "age",
    "money",
    "measure",
    "object_count",
    "ordinal_enumeration",
    "multiplicative",
    "unanchored",
)
#: The four closed-lexicon families, and the only ones `mundane_core` sums.
MUNDANE_CORE = ("calendar_duration", "age", "money", "measure")
#: The two halves of `system_any`, which is the one sum this instrument allows.
_SYSTEM = ("system_magnitude", "system_ordinal")


# --------------------------------------------------------------------------- tokenisation

_TOKEN = re.compile(r"\d[\d,]*(?:\.\d+)?(?:st|nd|rd|th)?|[A-Za-z]+(?:'[A-Za-z]+)?")
#: A numeral carrying a `+` or an arrow is a system quantity by SHAPE, whatever follows it.
#: Copied in spirit from `progression_cadence`'s `stat_delta`; `-5` is deliberately absent
#: because a hyphen before a number is a dash far more often than a negative sign.
_SHAPE_SIGNED = re.compile(r"(?<![\w.])\+\s?\d[\d,]*")
_SHAPE_ARROW = re.compile(r"\d[\d,]*\s*(?:->|=>)\s*\d[\d,]*")
#: `NUM years old`, `NUM-year-old`, `aged NUM`, `she was nineteen`. The copula form requires a
#: person subject and a bare numeral, and 2..120 keeps `there was one` out.
_NUM_WORD_ALT = "|".join(sorted(NUMERAL_WORDS, key=len, reverse=True))
_AGE_UNIT = re.compile(
    rf"\b(?:{_NUM_WORD_ALT}|\d{{1,3}})[\s-]+years?[\s-]?old\b", re.IGNORECASE
)
_AGE_TRIGGER = re.compile(
    rf"\b(?:aged|turn(?:ed|s|ing)?)\s+(?:{_NUM_WORD_ALT}|\d{{1,3}})\b", re.IGNORECASE
)
#: **`one` is not an age and the market half proved it.** `he is one of the people in this town`
#: was being reported as somebody's age. A bare `one` after a copula is a pronoun essentially
#: always, so it is out of the copula alternation entirely, and a following partitive `of` ends
#: the match whatever the numeral.
_COPULA_NUM_ALT = "|".join(sorted(NUMERAL_WORDS - {"one"}, key=len, reverse=True))
_AGE_COPULA = re.compile(
    r"\b(?:i|he|she|you|they|we)\s*(?:'m|'re|'s|\s+(?:am|is|are|was|were))\s+"
    rf"(?:{_COPULA_NUM_ALT}|\d{{1,3}})\b(?!\s+of\b)",
    re.IGNORECASE,
)

#: A structural heading is not prose and its number counts nothing. `progression_cadence`'s
#: furniture reject already carries `chapter \d`; this is the same exclusion widened to the
#: languages actually present in the shards, which an English-only pattern was letting through
#: as object counts -- `Capitulo 6`, `Cena 1`, `Cena 3` in one Portuguese chapter.
_RE_HEADING = re.compile(
    r"^\**\s*(?:chapter|chapitre|cap[ií]tulo|capitolo|kapitel|hoofdstuk|b[öo]l[üu]m|глава|"
    r"scene|cena|escena|sc[eè]ne|szene|part|book|volume|arc|episode|interlude|prologue|"
    r"epilogue|act)\b[\s:.\-#]*\d",
    re.IGNORECASE,
)
#: A heading is short. Without the bound, prose ABOUT a chapter -- `Chapter 6 had taught him
#: that eight days was a long time to wait for a letter` -- would be dropped along with the
#: headings. **The bound admits a small false negative and it is measured, not assumed away**: a
#: prose sentence that opens `Chapter N` and runs to twelve words or fewer is still swallowed.
#: Prose almost never opens that way, and a heading can be long, so the cost is paid here rather
#: than in the recall of the heading rule.
_HEADING_MAX_WORDS = 12


def is_heading_line(line: str) -> bool:
    """True for a structural heading whose number is navigation rather than narration."""
    return bool(_RE_HEADING.match(line)) and len(line.split()) <= _HEADING_MAX_WORDS


#: Common English function words. Used for one thing only: saying how English a chapter is, so
#: the market half's non-English rows are visible instead of silently scoring zero on every
#: English lexicon.
#:
#: **`a` and `as` were in this set and were removed on a measured collision.** Both are also
#: high-frequency function words in Portuguese, which is present in the shards, and on a short
#: Portuguese sample they alone lifted the score to 0.14 -- above the floor the set exists to
#: sit below. Every remaining word is one whose spelling does not carry that frequency in the
#: other languages the shards hold.
ENGLISH_FUNCTION_WORDS = lexicon(
    "the of and to in that it is was he she for on with his her they be at by not this "
    "but from or had have you all were are so if there what when which who been would could"
)


def english_share(text: str) -> float:
    """Share of tokens among the commonest English function words.

    **This is a control, not a filter, and it exists because the market half is not all in
    English.** A Portuguese chapter scores near zero on every English lexicon in this module,
    which drags the market's mundane density DOWN and therefore INFLATES any ours-versus-market
    gap. That is a bias in favour of this census's own headline, so it is measured rather than
    assumed away, and the census reports the market both with and without the rows below a
    stated share. Real English prose runs about 0.35-0.45 here.
    """
    words = [token.lower for token in tokenise(text)]
    if not words:
        return 0.0
    return sum(1 for word in words if word in ENGLISH_FUNCTION_WORDS) / len(words)


@dataclass(frozen=True, slots=True)
class Token:
    text: str
    lower: str
    start: int
    numeral: str  # "", "cardinal" or "ordinal"


def _numeral_kind(lower: str) -> str:
    if lower in ORDINAL_WORDS:
        return "ordinal"
    if lower in CARDINAL_WORDS:
        return "cardinal"
    if lower[0].isdigit():
        return "ordinal" if lower[-2:] in {"st", "nd", "rd", "th"} else "cardinal"
    return ""


def tokenise(line: str) -> list[Token]:
    return [
        Token(m.group(0), m.group(0).lower(), m.start(), _numeral_kind(m.group(0).lower()))
        for m in _TOKEN.finditer(line)
    ]


# --------------------------------------------------------------------------- classification


@dataclass(frozen=True, slots=True)
class Mention:
    """One located numeric mention: where it is, what it says, and what it is attached to."""

    word_offset: int
    family: str
    surface: str
    head: str
    spelled: bool


#: How many tokens the head search may walk, and how many CONTENT words it may collect. Six and
#: two: `four of the guild's jars` needs four steps of skipping to reach its head, and two
#: content words is enough for `two long days` and `nine years old` without letting the search
#: wander into the next clause.
_HEAD_WALK = 6
_HEAD_CONTENT = 2


def _head_window(tokens: Sequence[Token], after: int) -> list[Token]:
    """The content words the numeral governs, in order. Empty when the head is elided.

    The walk is the whole classifier and every stopping rule in it came from a hand-check
    against text on disk. It steps over determiners and possessives, steps over a *leading*
    partitive `of`, stops dead at a second numeral or at any function word that ends a noun
    phrase, and stops at `of` once a head has already been seen.
    """
    window: list[Token] = []
    seen_content = False
    for token in tokens[after : after + _HEAD_WALK]:
        low = token.lower
        if low in _SKIP or low.endswith("'s"):
            # A determiner AFTER a head opens a new noun phrase, and the numeral does not
            # govern it. Measured on the market half: `one more thing-your abilities` reached
            # `abilities` and reported a stat where the numeral counts things.
            if seen_content:
                break
            continue
        if low in _PARTITIVE:
            if seen_content:
                break
            continue
        if low in _SOFT_SKIP and not seen_content:
            continue
        if token.numeral or low in _STOP or len(low) < 3:
            break
        window.append(token)
        seen_content = True
        if len(window) >= _HEAD_CONTENT:
            break
    return window


def _head_family(tokens: Sequence[Token], after: int) -> tuple[str, str]:
    """Resolve the family from the tokens FOLLOWING a mention. `("", "")` when nothing anchors.

    A closed lexicon wins wherever it appears among the governed content words, because `two
    long days` has to reach `days` past an adjective. Only when no lexicon word appears at all
    does the first content word become an `object_count` head -- the one family whose head is
    guessed rather than known.
    """
    window = _head_window(tokens, after)
    for index, token in enumerate(window):
        for family, words in _FAMILY_LEXICONS:
            if token.lower in words:
                # `nine years old` is an age, not a duration. The unit word is the same.
                nxt = window[index + 1].lower if index + 1 < len(window) else ""
                if family == "calendar_duration" and nxt == "old":
                    return "age", token.lower
                return family, token.lower
    return ("object_count", window[0].lower) if window else ("", "")


def _system_family(is_ordinal: bool) -> str:
    """`fourth grade` and `Strength 14` share an anchor and are not the same object."""
    return "system_ordinal" if is_ordinal else "system_magnitude"


#: The system anchors that take a number AFTER them -- a labelled slot. **Deliberately much
#: narrower than `SYSTEM_WORDS`, and the narrowing is a measured one.** `point` and `stage` are
#: the cases: `at that point three days later` and `at this stage three of them` put a system
#: word immediately before a mundane numeral, and admitting them would have made a duration a
#: stat. `skill`, `spell`, `ability`, `title` and `perk` are absent for a different reason --
#: they are followed by a NAME rather than a number in this genre's own furniture.
_PRECEDING_SYSTEM = lexicon(
    "level levels lvl rank ranks tier tiers grade grades hp mp sp health mana stamina strength "
    "dexterity agility endurance vitality intelligence wisdom constitution charisma damage "
    "defense defence attack armor armour"
)


def _preceding_system(tokens: Sequence[Token], before: int) -> str:
    """`Level 5`, `Strength 14`, `at rank 3` -- the anchor on the other side of the numeral.

    Adjacency is one token and not two. A window of two admitted `at that point three days`,
    where the system word governs nothing and the numeral belongs to the days.
    """
    if before and tokens[before - 1].lower in _PRECEDING_SYSTEM:
        return tokens[before - 1].lower
    return ""


#: Two numerals are one mention only when nothing but space or a hyphen separates them.
#: **This is the rule the first version got wrong and a status block caught.** Adjacency in the
#: token list is not adjacency on the line: the tokeniser does not emit `->` or `/`, so
#: `Strength 14 -> 17` and `Mana: 240/300` were each merged into a single mention and a
#: five-number status block reported three. An arrow between two numbers is two quantities and
#: the whole point of the shape.
_JOINABLE = re.compile(r"^[\s-]*$")


def _merge_runs(line: str, tokens: Sequence[Token]) -> list[tuple[int, int]]:
    """Index spans of adjacent numerals. `twenty-two` and `two or three` are one mention each."""

    def gap(left: int, right: int) -> str:
        return line[tokens[left].start + len(tokens[left].text) : tokens[right].start]

    spans: list[tuple[int, int]] = []
    index = 0
    while index < len(tokens):
        if not tokens[index].numeral:
            index += 1
            continue
        end = index + 1
        while end < len(tokens):
            if tokens[end].numeral and _JOINABLE.match(gap(end - 1, end)):
                end += 1
            elif (
                tokens[end].lower in _LINKERS
                and end + 1 < len(tokens)
                and tokens[end + 1].numeral
                and _JOINABLE.match(gap(end - 1, end))
                and _JOINABLE.match(gap(end, end + 1))
            ):
                end += 2
            else:
                break
        spans.append((index, end))
        index = end
    return spans


def _pronoun_one(tokens: Sequence[Token], start: int, end: int) -> bool:
    """`no one`, `any one`, `one another` -- the word is a pronoun and not a quantity.

    `one` is the single largest false-positive source in this class and the head rule already
    disposes of most of it (`the condemned one` reaches no head and lands in `unanchored`).
    These three shapes are the ones the head rule cannot see, because they DO have a following
    word.
    """
    if end - start != 1 or tokens[start].lower != "one":
        return False
    previous = tokens[start - 1].lower if start else ""
    following = tokens[end].lower if end < len(tokens) else ""
    return previous in {"no", "any", "every", "some"} or following == "another"


def locate(text: str) -> list[Mention]:
    """Every numeric mention in one chapter, classified, in text order."""
    mentions: list[Mention] = []
    lines = normalise(text).split("\n")

    words_before: list[int] = []
    running = 0
    for line in lines:
        words_before.append(running)
        running += len(line.split())

    for index, line in enumerate(lines):
        if not line or is_heading_line(line):
            continue
        tokens = tokenise(line)
        base = words_before[index]
        furniture = is_furniture_line(line)

        # Shape-system and age spans are resolved on the raw line, then matched to mentions by
        # character offset, because both are multi-token patterns a per-token rule cannot see.
        shaped = [m.span() for m in _SHAPE_SIGNED.finditer(line)]
        shaped += [m.span() for m in _SHAPE_ARROW.finditer(line)]
        aged = [m.span() for m in _AGE_UNIT.finditer(line)]
        aged += [m.span() for m in _AGE_TRIGGER.finditer(line)]
        aged += [m.span() for m in _AGE_COPULA.finditer(line)]

        for start, end in _merge_runs(line, tokens):
            if _pronoun_one(tokens, start, end):
                continue
            first = tokens[start]
            surface = line[first.start : tokens[end - 1].start + len(tokens[end - 1].text)]
            offset = base + len(line[: first.start].split())
            spelled = not first.lower[0].isdigit()
            at = first.start

            # Ordinality lives on the LAST token of a merged run, not the first: in
            # `twenty-second` the head word is `second` and the run opens on a cardinal. A
            # first version read `tokens[start]` and filed `the twenty-second jar` as an
            # object count.
            ordinal = tokens[end - 1].numeral == "ordinal"
            as_system = _system_family(ordinal)

            if furniture:
                family, head = as_system, "furniture_line"
            elif any(lo <= at < hi for lo, hi in shaped):
                family, head = "system_magnitude", "shape"
            elif any(lo <= at < hi for lo, hi in aged):
                family, head = "age", "age_pattern"
            elif preceding := _preceding_system(tokens, start):
                # A labelled slot governs its number: `level 12 that morning` is a level, and
                # a first version let the following `morning` win and called it a duration.
                family, head = as_system, preceding
            else:
                family, head = _head_family(tokens, end)
                if family == "system":
                    family = as_system
                elif not family:
                    family, head = "unanchored", ""
                if ordinal and family in {"object_count", "unanchored"}:
                    family = "ordinal_enumeration"

            mentions.append(Mention(offset, family, surface, head, spelled))

    mentions.sort(key=lambda m: m.word_offset)
    return mentions


# --------------------------------------------------------------------------- per chapter


@dataclass(frozen=True, slots=True)
class ChapterNumbers:
    """One chapter's number-context profile, reduced to what the census aggregates."""

    words: int
    mentions: int
    spelled: int
    digits: int
    by_family: dict[str, int]
    furniture_lines: int
    english_share: float

    @property
    def mundane_core(self) -> int:
        return sum(self.by_family[family] for family in MUNDANE_CORE)

    @property
    def system_any(self) -> int:
        """The one sum this instrument allows; both components are always reported beside it."""
        return self.by_family["system_magnitude"] + self.by_family["system_ordinal"]

    @property
    def anchored(self) -> int:
        """System plus every mundane family the census is willing to call an anchor."""
        return self.system_any + self.mundane_core + self.by_family["object_count"]

    def per_1k(self, count: int) -> float:
        return (count * 1000 / self.words) if self.words else 0.0

    @property
    def system_share_of_anchored(self) -> float | None:
        """The per-chapter form of the headline ratio, bounded in [0, 1].

        A ratio of two densities is undefined whenever the denominator is zero, and neither
        half's mundane density is reliably non-zero at chapter grain. A share is defined
        whenever anything at all is anchored, which is what makes it distributable.
        """
        return (self.system_any / self.anchored) if self.anchored else None

    @property
    def magnitude_share_of_anchored(self) -> float | None:
        """The same share with ordinal ladder positions removed from the numerator.

        Our own shelf's entire system column is ordinals, so this is the statistic on which
        ours and a book with a sheet actually differ.
        """
        return (
            (self.by_family["system_magnitude"] / self.anchored) if self.anchored else None
        )


def measure(text: str) -> ChapterNumbers:
    mentions = locate(text)
    lines = normalise(text).split("\n")
    return ChapterNumbers(
        words=len(text.split()),
        mentions=len(mentions),
        spelled=sum(1 for m in mentions if m.spelled),
        digits=sum(1 for m in mentions if not m.spelled),
        by_family={f: sum(1 for m in mentions if m.family == f) for f in FAMILIES},
        furniture_lines=sum(1 for line in lines if is_furniture_line(line)),
        english_share=english_share(text),
    )


def family_of(text: str) -> list[tuple[str, str]]:
    """`(surface, family)` for every mention -- the shape a hand-check reads."""
    return [(m.surface, m.family) for m in locate(text)]


# --------------------------------------------------------------------------- selftest

#: Read 8 §4.1's exhaustive list for *Unlicensed Weather* chapter 1, as the operator's own
#: sentences. Fixture material for a detector and nothing else: no line here reaches a prompt
#: (§97.1). Each is paired with the family the hand-count assigns it.
FIXTURE_MUNDANE: tuple[tuple[str, str], ...] = (
    ("\"Eight days,\" Dov said, reading. \"Shower. Full weight.\"", "calendar_duration"),
    ("A shower, ten days caught, and he matched the number.", "calendar_duration"),
    ("Nine days. It's lost about a finger.", "calendar_duration"),
    ("That one's older than its neighbours. Twelve days and a bit.", "calendar_duration"),
    ("The row was thirty jars long and it went away from her like a street.", "object_count"),
    ("You're nineteen and you're the colour of a dishcloth.", "age"),
    ("waiting eleven years for a morning like this one", "calendar_duration"),
    ("Four of the guild's jars rode in a padded frame on her back.", "object_count"),
)

#: Shapes a first version drew and a hand-check refused. Each stays as a pin so the narrowing
#: cannot be lost. The last two are the head-window overreach and the merged-ordinal miss, both
#: found by dumping every mention in the fixture chapter and reading them against the page.
FIXTURE_REFUSED: tuple[str, ...] = (
    "The condemned one's gone to the seal-house.",
    "It was not a question; no one had ever asked her.",
    "They looked at one another and said nothing.",
    "An hour of rain on your table by noon.",
)

#: Cases whose family a hand-check fixed, held as pins in the direction they were fixed to.
FIXTURE_CLASSIFIED: tuple[tuple[str, str], ...] = (
    # The head window reached past `surprise` to `morning` and reported a duration.
    ("That was the first surprise of the morning.", "ordinal_enumeration"),
    # From the MARKET half: a determiner after a head opens a new noun phrase.
    ("Oh, and one more thing-your abilities do not stay with you.", "object_count"),
    # From the MARKET half: a bare `one` after a copula is a pronoun, never an age.
    ("That's Pete, he is one of the people in this town.", "object_count"),
    # Ordinality was read off the first token of the merged run, which is a cardinal.
    ("At the twenty-second jar she stopped.", "ordinal_enumeration"),
    # Adjectives and quantity modifiers must not hide a closed-lexicon head.
    ("He waited two long days and three more nights.", "calendar_duration"),
    # Our own shelf's whole system column has this shape, and it is not a magnitude.
    ("You'll want the fourth-grade price.", "system_ordinal"),
    ("He reached level 12 that morning.", "system_magnitude"),
)

#: **A measured false positive with no mechanical fix, kept visible rather than quietly borne.**
#: `three levels of it below the lobby` is a parking structure, and `levels` is the anchor word
#: this genre's own sheet uses. Nothing short of a sense disambiguator separates them, so the
#: system column carries a small architectural contamination on both halves of every comparison
#: and this constant is the receipt.
MEASURED_FALSE_POSITIVES: tuple[tuple[str, str], ...] = (
    ("from the parking structure, three levels of it below the lobby", "system_magnitude"),
)

_SELFTEST_FURNITURE = """He opened the door.

[Level Up! You are now Level 12]
[Strength 14 -> 17]
[Mana: 240/300]

The room was cold.
"""


def selftest() -> list[str]:
    """Every failure this instrument can find in itself, as a list of messages."""
    failures: list[str] = []

    if registration_digest() != REGISTRATION_DIGEST:
        failures.append("the frozen block moved; this is a different instrument")

    for text, expected in FIXTURE_MUNDANE:
        families = [family for _surface, family in family_of(text)]
        if expected not in families:
            failures.append(
                f"the operator's own item was not located as {expected}: {text!r} -> {families}"
            )
        if any(f in _SYSTEM for f in families):
            failures.append(f"a mundane fixture located a SYSTEM number: {text!r}")

    for text in FIXTURE_REFUSED:
        located = [
            (s, f)
            for s, f in family_of(text)
            if f in {*MUNDANE_CORE, "object_count", *_SYSTEM}
        ]
        if located:
            failures.append(f"a refused shape was counted: {text!r} -> {located}")

    for text, expected in FIXTURE_CLASSIFIED:
        families = [family for _surface, family in family_of(text)]
        if expected not in families:
            failures.append(f"a fixed classification regressed: {text!r} -> {families}")

    furniture = [f for _s, f in family_of(_SELFTEST_FURNITURE)]
    located_system = sum(1 for f in furniture if f in _SYSTEM)
    if located_system < 5:
        failures.append(
            f"a status block located {located_system} system numbers, expected >= 5"
        )
    if any(f in MUNDANE_CORE for f in furniture):
        failures.append(f"a status block leaked a mundane family: {furniture}")

    for divider in ("He stopped.\n\n***\n\nShe did not.", "One.\n\n---\n\nTwo."):
        if any(f in _SYSTEM for _s, f in family_of(divider)):
            failures.append(f"a scene divider made a number system: {divider!r}")

    for text, family in MEASURED_FALSE_POSITIVES:
        if family not in [f for _s, f in family_of(text)]:
            failures.append(
                f"a recorded false positive stopped firing without its note being removed: "
                f"{text!r}"
            )

    merged = family_of("She counted twenty-two jars, then two or three more.")
    if len(merged) != 2:
        failures.append(f"the merge rule located {len(merged)} mentions, expected 2: {merged}")

    system_prose = family_of("He reached level 5 and gained 300 experience, then rank 3.")
    if sum(1 for _s, fam in system_prose if fam in _SYSTEM) < 3:
        failures.append(f"inline system anchors under-counted: {system_prose}")

    if family_of("Nothing happens here at all."):
        failures.append("inert prose located a mention")

    return failures


__all__ = [
    "CALENDAR_WORDS",
    "ENGLISH_FUNCTION_WORDS",
    "FAMILIES",
    "FIXTURE_CLASSIFIED",
    "FIXTURE_MUNDANE",
    "FIXTURE_REFUSED",
    "MEASURED_FALSE_POSITIVES",
    "MEASURE_WORDS",
    "MONEY_WORDS",
    "MUNDANE_CORE",
    "PRE_REGISTRATION",
    "REGISTRATION_DIGEST",
    "SYSTEM_WORDS",
    "ChapterNumbers",
    "Mention",
    "english_share",
    "family_of",
    "is_furniture_line",
    "is_heading_line",
    "locate",
    "measure",
    "normalise",
    "registration_digest",
    "selftest",
    "tokenise",
]


def _main(argv: Sequence[str] | None = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="selftest the number-context counters")
    parser.add_argument("command", choices=("selftest",))
    parser.parse_args(argv)
    failures = selftest()
    for failure in failures:
        print(f"FAIL: {failure}", file=sys.stderr)
    if failures:
        return 1
    print(f"selftest OK - registration_digest {REGISTRATION_DIGEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
