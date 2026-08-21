"""The named axes feedback is allowed to be about, and the deterministic counters that own them.

An **axis** is a property of prose that (a) a human read has named as a defect, (b) a
deterministic counter orders without any model in the loop, and (c) the one surviving
elicitation protocol has been measured able to name. All three, or it is not here.

**Three axes, and the shortlist is not a design choice — it is the intersection of two
measurements.** The first human read of a generated book named three defects: flat stats, no
interiority, em dashes (`plan/stage-0-decisions.md` §74). Those are the same three families
stage-0 §89's E6 clears on — 40/40, 18/36 and 30/32 against measured nulls of 0.21, 0.26 and
0.36. A fourth axis would need a fourth human read and a fourth measured family, and adding one
because it seemed plausible is how twenty-one proxies died
(`research/quality-measurement/BRIEF.md` §2).

**The counter decides which side; nothing else may.** This is the load-bearing division of
labour in the whole loop. A counter measures that two texts differ on a named axis and *which of
them is higher*; it says nothing about which is better. Supplying that valence would assert craft
doctrine — "told feeling is worse", "em dashes are a tell" — as a premise, when §87.1 and §87.3
record it as the hypothesis under test. So the direction of an axis comes from readers
(`domain/directions.py`) and never from here, and the pre-registered hypotheses below are
recorded so they can be *refuted*, never emitted.

**Why the counters are restated rather than imported.** They are the definitions
`research/quality-measurement/authorship_tells.py` and `latent_fixtures.py` measured B6 with, and
that is the ground truth E6 was scored against. `domain` may not import `research`
(`tests/test_architecture.py` enforces the layering), so they are ported with their provenance
and `tests/test_reader_judge_loop.py` pins all three against the research implementations on
shared text. A drifted counter would silently redefine what §89's numbers were about.

**How this registry grows, and it is the only way it grows.** An axis enters by one of exactly
two doors and never by speculation about what ought to matter to readers:

1. **A named defect from a human read.** All three incumbents came through this door — §74 read
   one generated book and named flat stats, no interiority, em dashes. That makes every future
   human read a *defect harvest* with a defined product: each named defect is a candidate axis
   with its provenance attached.
2. **A nomination from the discard corpus** — the E6 sentences that named no registered axis
   (`domain/feedback.py`'s `JudgeDiscard`). A nomination is a *hypothesis*, never a finding: a
   matcher drafted from those sentences and then scored against them is a rubric fitted to its
   own answers, which is exactly what freezing `AXIS_MATCHERS` exists to prevent. So a nominated
   axis takes the full path — a deterministic counter, an E6-family validation on **fresh pairs
   the nomination corpus never touched**, and a reader-established direction — before it emits
   anything.

**Once admitted, an axis and its E6 family stay in the battery permanently**, the way a compiler
never deletes the regression test for a fixed miscompile. `admitted_via` records which read or
which nomination each one came from, so the registry carries its own history rather than a
docstring elsewhere carrying it.

There is no enforcement machinery for this and there deliberately is none: admission is an
operator act (§84), and a rule the code could apply is a rule somebody could satisfy without
having done the work.
"""

from __future__ import annotations

import enum
import re
from collections.abc import Mapping
from dataclasses import dataclass

#: The em dash itself. Named rather than inlined for the reason `ablate` names it: the ASCII
#: source is easier to read than a bare glyph, and every arm has to agree exactly.
_EM = "—"

#: System voice: bolded headers and any line carrying a bracketed all-caps tag. Copied from
#: `authorship_tells.strip_system`, which is the form `p0_features` measured B6 with — wider than
#: `ablate`'s STATUS-only guard, and the wider one is the one the numbers were taken under.
_SYSTEM = re.compile(r"\*\*[^*\n]*\*\*|^.*\[[A-Z][A-Z ]+\].*$", re.MULTILINE)

#: A system-voice *line*, for the digit counter, which measures the unstripped text's system
#: lines rather than its prose. `stat_flatten` edits that line and nothing else.
_SYSTEM_LINE = re.compile(r"\[[A-Z][A-Z ]+\]")

_DIGIT = re.compile(r"\d")

#: Verbs that report an inner state rather than an observable one. `authorship_tells`'s list,
#: which is three verbs longer than `ablate`'s — believed, suspected, expected — and is the one
#: `interior_per_1k` was computed with everywhere the number is quoted.
_INTERIOR = re.compile(
    r"\b(?:thought|realised|realized|wondered|remembered|felt|knew|hoped|feared|wanted|"
    r"decided|understood|noticed|hated|loved|regretted|believed|suspected|expected)\b",
    re.IGNORECASE,
)

#: Sentence boundary. `authorship_tells._SENT`, with the two curly quotes written as `\N{...}`
#: escapes rather than as glyphs: they are the characters a linter flags as ambiguous and an
#: editor's smart-quote handling silently rewrites, and this pattern has to keep matching what
#: the research module matched or the counters stop being the ones B6 was measured with.
_CLOSERS = "\"'\N{RIGHT DOUBLE QUOTATION MARK}\N{RIGHT SINGLE QUOTATION MARK}"
_SENTENCE = re.compile(f"(?<=[.!?])[{_CLOSERS}]*\\s+")


def strip_system(text: str) -> str:
    """Prose with the system voice removed. `authorship_tells.strip_system`, verbatim."""
    return _SYSTEM.sub(" ", text)


def _words(text: str) -> int:
    return max(len(text.split()), 1)


class Pole(enum.StrEnum):
    """Which end of an axis. `HIGH` is always *more of the counted thing*.

    Deliberately not named "good" and "bad": which pole is preferred is a reader measurement
    (`domain/directions.py`), and a pole whose name carried the answer would make the
    measurement unfalsifiable.
    """

    HIGH = "high"
    LOW = "low"

    @property
    def other(self) -> Pole:
        return Pole.LOW if self is Pole.HIGH else Pole.HIGH


@dataclass(frozen=True, slots=True)
class Axis:
    """One named axis: its counter, its words, and the hypothesis it exists to test."""

    axis_id: str
    counter_id: str
    #: The pre-registered guess at which pole readers prefer, from the §74 human read. **Never
    #: emitted and never consulted by anything that shapes a prompt.** It is here so that when
    #: readers answer, the answer can be reported as confirming or refuting something written
    #: down first — which is the difference between a prediction and a rationalisation. §78.3's
    #: em-dash arm is VOID with its point estimate leaning *toward* the mark, so at least one of
    #: these three may well be wrong.
    hypothesis: Pole
    #: How the axis is said to a generator, one phrase per pole. Named and located, never
    #: scalar: there is no rating on this dataclass and none may be added.
    high_phrase: str
    low_phrase: str
    provenance: str
    #: Which door this axis came through — a named defect from a human read, or a nomination
    #: from the discard corpus. Recorded on the registration rather than in prose elsewhere,
    #: because the admission path is the only thing standing between this registry and the
    #: twenty-one proxies that entered on plausibility.
    admitted_via: str = "human read"

    def phrase(self, pole: Pole) -> str:
        return self.high_phrase if pole is Pole.HIGH else self.low_phrase


AXES: Mapping[str, Axis] = {
    axis.axis_id: axis
    for axis in (
        Axis(
            axis_id="stat_flatten",
            counter_id="system_digit_count",
            hypothesis=Pole.HIGH,
            high_phrase="concrete numbers on the page where the game state is stated",
            low_phrase="game state stated without concrete numbers",
            provenance=(
                "§74 defect 1 (flat stats); §81 measured the panel BLIND on it at 0.5437; "
                "§89 E6 named it 40 of 40"
            ),
            admitted_via="human read, §74 defect 1 (2026-08-18)",
        ),
        Axis(
            axis_id="interiority",
            counter_id="interior_per_1k",
            hypothesis=Pole.HIGH,
            high_phrase="what the viewpoint character thought, felt, feared or wanted",
            low_phrase="only what could be observed from outside the viewpoint character",
            provenance=(
                "§74 defect 2 (no interiority); §85's certified repair moves this counter; "
                "§89 E6 named it 18 of 36 against a null of 0.2569, which is a fixture ceiling "
                "rather than a perception limit"
            ),
            admitted_via="human read, §74 defect 2 (2026-08-18)",
        ),
        Axis(
            axis_id="em_dash",
            counter_id="em_per_1k",
            hypothesis=Pole.LOW,
            high_phrase="em dashes setting off phrases in the prose",
            low_phrase="sentence breaks and commas instead of em dashes in the prose",
            provenance=(
                "§74 defect 3 (em dashes); §75 measured us at 5.50/1k against a pre-LLM human "
                "median of 0.00 (p90 1.91); §89 E6 named it 30 of 32"
            ),
            admitted_via="human read, §74 defect 3 (2026-08-18)",
        ),
    )
}


def system_digit_count(text: str) -> float:
    """Digits on the system-voice lines of the **unstripped** text.

    `latent_fixtures.p0_features`'s steelman counter, which is what makes `stat_flatten`
    counter-decidable: the transform replaces the numbers in the status block with `?`, so a
    counter over stripped prose would see nothing and a probe beating it would be beating an
    omission of ours rather than a limit of surface measurement.
    """
    lines = [line for line in text.splitlines() if _SYSTEM_LINE.search(line)]
    return float(len(_DIGIT.findall("\n".join(lines))))


def interior_per_1k(text: str) -> float:
    """Interiority verbs per thousand words of prose, system voice removed."""
    prose = strip_system(text)
    return 1000.0 * len(_INTERIOR.findall(prose)) / _words(prose)


def em_per_1k(text: str) -> float:
    """Em dashes per thousand words of prose, system voice removed.

    The exclusion is measured rather than fastidious: without it, stripping turns
    `**TOLL PAID — 9 days**` into `**TOLL PAID, 9 days**`, so a reader preferring the original
    would be telling us it liked em dashes *or* that it liked unmangled stat blocks, with no way
    to separate the two. The human named a prose tell; these lines are not prose.
    """
    prose = strip_system(text)
    return 1000.0 * prose.count(_EM) / _words(prose)


#: How much of a scene counts as its opening, for `opening_proper_nouns`. Three hundred words
#: is the operator's own figure from the 2026-08-21 read ("in the first three hundred words"),
#: kept rather than tuned: a window chosen to make a number come out is a window that has
#: stopped measuring the thing the reader named.
OPENING_WINDOW_WORDS = 300

#: Lowercase words that may sit *inside* a multi-word name — "Bellow and Sons", "Duchy of
#: Reln". Kept short and closed. A longer list starts absorbing ordinary prose between two
#: unrelated names into one invented name.
_NAME_CONNECTORS = frozenset({"and", "of", "the", "de", "du", "von", "van", "della", "di"})

#: Trailing and leading characters stripped off a token before it is judged. Hyphens and
#: apostrophes stay: "crown-and-hook" and "Sons'" are one token each, and splitting them would
#: manufacture names out of their halves.
_EDGE_PUNCT = (
    "\"'()[]{}.,;:!?"
    "\N{EM DASH}\N{EN DASH}"
    "\N{LEFT DOUBLE QUOTATION MARK}\N{RIGHT DOUBLE QUOTATION MARK}"
    "\N{LEFT SINGLE QUOTATION MARK}\N{RIGHT SINGLE QUOTATION MARK}"
)

#: A token that ends a sentence, allowing for closing quotes and emphasis after the stop.
#:
#: **The emphasis marks are measured, not defensive.** Without them the anchor text yields two
#: false names: a scene break written `* * *` leaves the next word looking mid-sentence, and a
#: free-indirect question set in italics — `*what are you?*` — ends in `?*`, so `He` after it
#: was read as a proper noun the book had used mid-sentence. Both are markdown the prose
#: actually carries, so the pattern has to know about them.
#: The characters that may follow a full stop and still be the end of the sentence.
_END_CLOSERS = "\"'\N{RIGHT DOUBLE QUOTATION MARK}\N{RIGHT SINGLE QUOTATION MARK}"

#: An utterance cut off by a dash ends too, but only when a quote closes it.
#:
#: Measured on chapter 2 of the anchor book. One interrupted line of dialogue — a question
#: broken off mid-word and closed — left the next word in mid-sentence position, so the counter
#: believed in a person called "Ask Vance" standing beside the Vance it already knew. The
#: closing quote is required: a dash *inside* a sentence is an aside, not an ending, and
#: treating those as boundaries would lose real names to buy this one back.
_SENTENCE_END = re.compile(
    "(?:[.!?][" + _END_CLOSERS + ")\\]*_]*"
    "|[\N{EM DASH}\N{EN DASH}-][" + _END_CLOSERS + "]+)$"
)

#: A token made only of emphasis or break characters — `*`, `* * *`. Not a word, and it ends
#: whatever preceded it.
_BREAK_TOKEN = re.compile(r"^[*_-]+$")


def _tokens(text: str) -> list[tuple[str, bool, bool]]:
    """`(word, starts_a_sentence, joins_the_next_token)` for each whitespace-delimited token.

    Sentence-initial position is tracked rather than inferred later because it is the whole
    difficulty of counting names without a tagger: English capitalises the first word of every
    sentence, so "Inside" and "Marta" look identical at position zero and are not.

    `joins_the_next_token` is true only when nothing was stripped from the token's right edge.
    It is what stops a speech tag becoming a surname: in `"Signet," Turrow said`, the raw token
    ends `,"`, so the two capitals either side of that punctuation are two things and not one
    name. Without it the anchor text reports a person called "Signet Turrow".
    """
    out: list[tuple[str, bool, bool]] = []
    starts = True
    for raw in text.split():
        if _BREAK_TOKEN.match(raw):
            starts = True
            continue
        word = raw.strip(_EDGE_PUNCT)
        if word:
            out.append((word, starts, raw.rstrip(_EDGE_PUNCT) == raw))
        starts = bool(_SENTENCE_END.search(raw))
    return out


def _is_candidate(word: str) -> bool:
    """Could this token be part of a name at all?

    All-caps tokens are excluded, and that exclusion is measured rather than tidy. The anchor
    text's first page carries a chalked fee schedule — `WEIGHT & PURITY, ONE MARK. VALUATION
    WITH CERTIFICATE, ONE AND A HALF` — and a rule that only asked "is it capitalised" reads
    seven proper nouns off a price list. Signage and stat blocks are shouted, not named.
    """
    if len(word) < 2 or not word[0].isupper():
        return False
    if word.isupper():
        return False
    return any(character.isalpha() for character in word)


def _bare(word: str) -> str:
    """A token with its possessive removed, so `Vance's` and `Vance` are one person.

    Measured on chapter 2 of the anchor book, which reported `Vance`, `Master Vance` and
    `Vance's` as three of its seven introductions.
    """
    for suffix in ("\N{RIGHT SINGLE QUOTATION MARK}s", "'s"):
        if word.endswith(suffix) and len(word) > len(suffix):
            return word[: -len(suffix)]
    return word


def _proven_names(tokens: list[tuple[str, bool, bool]]) -> set[str]:
    """Tokens that appear capitalised somewhere a sentence did not force it.

    **This is the whole trick, and it reads the entire text to answer a question about the
    opening.** Whether a word is a name is a property of the book; when it is first introduced
    is a property of the window. `Marta` opens a sentence on the first page and would be
    invisible to any rule that only looked there — she is recoverable because the book later
    writes her name mid-sentence, and nothing else in English does that to `Inside` or `Beside`.
    """
    return {word for word, starts, _ in tokens if not starts and _is_candidate(word)}


def opening_proper_noun_names(text: str, window: int = OPENING_WINDOW_WORDS) -> tuple[str, ...]:
    """The distinct names a reader is asked to hold in the first `window` words, in order.

    Multi-word names are joined, including across the closed set of lowercase connectors, so
    "Hesk Turrow" and "Bellow and Sons" are one apiece rather than two and three. A bare
    surname later in the window folds into the full name it belongs to: a reader introduced to
    Hesk Turrow does not meet a second person when the next line says "Turrow said".

    Returned as names rather than as a number because the number is not reviewable. The 2026
    read named its nine; a counter that could only answer "eight" would have been impossible
    to check against it.
    """
    tokens = [(_bare(word), starts, joins) for word, starts, joins in _tokens(strip_system(text))]
    proven = _proven_names(tokens)
    opening = tokens[:window]

    names: list[str] = []
    seen: set[str] = set()
    index = 0
    while index < len(opening):
        word, starts, joins = opening[index]
        if not _is_candidate(word):
            index += 1
            continue
        # **A sentence-opening capital is a name only if the book capitalises it elsewhere
        # too.** An earlier version also accepted one whose next token was capitalised, on the
        # theory that "Weigh Street" announces itself — and it does, but so does "Ask Vance",
        # and chapter 2 duly reported a person called Ask Vance beside the Vance it already
        # knew. `Weigh` survives the stricter rule because the book writes "on Weigh Street"
        # mid-sentence; `Ask` does not, because nothing capitalises it except a full stop.
        if starts and word not in proven:
            index += 1
            continue

        parts = [word]
        cursor = index + 1
        attached = joins
        while cursor < len(opening) and attached:
            nxt, _, nxt_joins = opening[cursor]
            if _is_candidate(nxt):
                parts.append(nxt)
                cursor += 1
                attached = nxt_joins
                continue
            after = opening[cursor + 1][0] if cursor + 1 < len(opening) else ""
            if nxt.lower() in _NAME_CONNECTORS and nxt_joins and _is_candidate(after):
                parts.extend([nxt, after])
                attached = opening[cursor + 1][2]
                cursor += 2
                continue
            break

        name = " ".join(parts)
        components = {part for part in parts if _is_candidate(part)}
        # Already met, either as this exact name or as a component of a fuller one.
        if name not in seen and not (len(components) == 1 and components & seen):
            names.append(name)
            seen.add(name)
            seen |= components
        index = cursor
    return tuple(names)


def opening_proper_nouns(text: str) -> float:
    """Distinct proper nouns introduced in the first `OPENING_WINDOW_WORDS` words of prose.

    **Nominated by a human read, and not admitted to anything.** The 2026-08-21 read of Serial
    Pilot 1 named "too many names right at the start" as one of five prose defects
    (`plan/reader-read-2.md`), and per stage-0 §87 a deterministic counter is the one instrument
    class that works where the judge panel is blind. It is registered in `COUNTERS` and
    deliberately **absent from `AXES`**: an axis carries a preferred pole, a pole is a claim
    about what readers want, and that claim needs a measured distribution and an operator act.
    The distribution is in `research/quality-measurement/opening-counters-results.md`; the
    admission is not this module's to make.

    Nothing in any generation path reads this. It measures; it does not steer.
    """
    return float(len(opening_proper_noun_names(text)))


COUNTERS: Mapping[str, object] = {
    "system_digit_count": system_digit_count,
    "interior_per_1k": interior_per_1k,
    "em_per_1k": em_per_1k,
    # Registered so it can be called and tested; deliberately absent from `AXES`, which is
    # where a preferred pole would live. See the function's docstring.
    "opening_proper_nouns": opening_proper_nouns,
}


def count(axis_id: str, text: str) -> float:
    """This axis's counter over this text. Deterministic, model-free, total."""
    axis = AXES[axis_id]
    counter = COUNTERS[axis.counter_id]
    return float(counter(text))  # type: ignore[operator]


def counts(text: str) -> dict[str, float]:
    """Every registered axis's counter over one text, for the off-target check."""
    return {axis_id: count(axis_id, text) for axis_id in AXES}


def higher(axis_id: str, left: str, right: str) -> str | None:
    """Which of two texts sits at `Pole.HIGH` on this axis, or None if the counter ties them.

    A tie is not a failure and is not rounded away: a pair the counter does not separate
    carries no evidence about this axis, and treating "equal" as "left" is how a null becomes a
    finding.
    """
    delta = count(axis_id, left) - count(axis_id, right)
    if delta == 0.0:
        return None
    return left if delta > 0.0 else right


def separating(left: str, right: str) -> tuple[str, ...]:
    """The registered axes whose counter separates this pair, in registry order.

    **A pair is admitted as evidence for exactly one axis when this returns exactly one.**
    Single-axis by *measurement* rather than by construction, which is weaker than a certified
    transform and is the honest description: two drafts of one beat differ on everything
    unregistered as well, so a direction estimated from them is confounded with whatever else
    covaries with the counter in this generator's output
    (`plan/reader-judge-loop.md` §3.1 states the cost and names the successor).
    """
    return tuple(axis_id for axis_id in AXES if count(axis_id, left) != count(axis_id, right))


def _first_sentence_matching(text: str, pattern: re.Pattern[str]) -> str | None:
    for sentence in _SENTENCE.split(strip_system(text)):
        stripped = sentence.strip()
        if stripped and pattern.search(stripped):
            return stripped
    return None


def locate(axis_id: str, text: str) -> str | None:
    """A span of `text` where this axis is *present*, or None.

    **Always located on the `HIGH` side, whichever pole readers turn out to prefer**, because
    absence has no span. A missing interiority verb cannot be quoted; the sentence that has one
    can. So a feedback item quoting a `HIGH`-side span reads as an exemplar when `HIGH` is
    preferred and as a specimen when it is not, and the phrasing carries which
    (`domain/feedback.py`).

    Located by the counter's own definition rather than by the judge, so a judge cannot
    mislocate what it named.
    """
    if axis_id == "stat_flatten":
        lines = [line.strip() for line in text.splitlines() if _SYSTEM_LINE.search(line)]
        best = max(lines, key=lambda line: len(_DIGIT.findall(line)), default=None)
        return best if best and _DIGIT.search(best) else None
    if axis_id == "interiority":
        return _first_sentence_matching(text, _INTERIOR)
    if axis_id == "em_dash":
        return _first_sentence_matching(text, re.compile(re.escape(_EM)))
    raise KeyError(axis_id)


__all__ = [
    "AXES",
    "COUNTERS",
    "Axis",
    "Pole",
    "count",
    "counts",
    "em_per_1k",
    "higher",
    "interior_per_1k",
    "locate",
    "opening_proper_noun_names",
    "opening_proper_nouns",
    "separating",
    "strip_system",
    "system_digit_count",
]
