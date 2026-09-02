"""The regular tells: sentence shapes a counter can find, and the shelf's own rate as the ceiling.

**Nineteen operator reads named the same shapes under four writers and both persons**
(`plan/reader-read-19.md` §2.2): a clause built on *nobody / nothing / never*; a sentence that
turns on itself, the same word repeated around *without* or *not*; *the way* somebody *always*
does a thing, told where an act would show; a phrase repeated inside one sentence; three *and*s
chaining one sentence. Every prompt-side lever was pulled at them — five clauses on the house
floor (§176 to §181), measured by the agent-impact audit as moving no sentence metric and
removed in §187; three exemplars (§196), which moved the system's voice and the similes and
not these; four dossiers, which moved the frame and not these; the person flip, which removed
the first-person families and not these. They are the model's defaults and they survive
instruction. What has removed a tell in this house is code: the em-dash strip and the markup
strip took two off every page deterministically, and the listing's two rails redraw on a
counter.

**This module is the counter, and it judges nothing.** Each family is a frozen pattern over one
sentence; `locate` says which sentences carry which shape; `density` says how often per
thousand words; `ceilings` reads the same densities off the shelf's own chapters, the openings
the operator placed by hand (§196), so the number a page is held to is the market's and moves
when the shelf does. A page under every ceiling is not good, it is merely not that. The rewrite
that follows (`application/tells_pass.py`) is a model asked to say one located sentence again;
whether the shape is gone is this module's answer and never the model's.

Machine lines are never counted: the status line, the offer line, and a system's own
capitals (*NO CLASS. GROUND.*) are the book speaking as a machine, and *nothing* in a notice is
the notice's word.

**The sixth family is a length, and its threshold is the shelf's** (§199.4). A census of
sentence lengths on the three placed openings the ladder is shown found no sentence over
thirty-five words and a median of ten to sixteen; ours ran to fifty and ninety words at the
top with a median of seven, five to eight sentences per thousand words over the shelf's
longest, and the pass's own residue was the long compound sentence carrying three or four
families at once. A sentence longer than the longest the shelf writes is located like the
rest; the threshold travels in the limits under `LONG_WORDS`, is read off the shelf by
`ceilings`, and with no threshold the family locates nothing.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

#: The families, by name, in the order the reads named them.
ABSENCE = "absence"
PARADOX = "paradox"
THE_WAY = "the_way"
ECHO = "echo"
CHAINED_AND = "chained_and"
LONG = "long"
FAMILIES: tuple[str, ...] = (ABSENCE, PARADOX, THE_WAY, ECHO, CHAINED_AND, LONG)
#: The limits key carrying the long family's threshold in words: the shelf's longest sentence.
LONG_WORDS = "long_words"

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[A-Za-z][A-Za-z']*")

#: A clause built on an absence: *nobody understood*, *nothing came*, *never once*, and the
#: sentence that opens by saying what a thing is not (*Not a scream.* / *No name on it.*).
_ABSENCE = re.compile(
    r"\b(?:nobody|no one|no-one|nothing|never)\b|^(?:not|no)\s+\w", re.IGNORECASE
)
#: The same word repeated around *without*, *not* or *than*: *taking it back without taking it
#: back*. Four letters or more so *a ... a* and *it ... it* do not count.
_PARADOX_TURN = re.compile(
    r"\b(\w{4,})\b[^.;:]{0,40}\b(?:without|not|than)\b[^.;:]{0,25}\b\1\b", re.IGNORECASE
)
#: *Not a pause, a stop*; *not a name, that's a shelf*: the definition by contrast.
_PARADOX_CONTRAST = re.compile(
    r"\bnot (?:a|an|the) \w+(?:'s)?[,;] (?:a|an|the|that's|it's|just|but) \w+", re.IGNORECASE
)
#: *The way he always stopped and looked*; *the way you do when you already know*.
_THE_WAY = re.compile(
    r"\bthe way (?:he|she|they|you|i|we|it|a|an|the|somebody|people|everybody|nobody)\b",
    re.IGNORECASE,
)
#: Three or more *and*s chaining one sentence: read 19's *and then and then and then*.
_AND = re.compile(r"\band\b", re.IGNORECASE)
CHAIN_ANDS = 3

#: A line the book prints as a machine, never counted (`draft.strip_em_dash` keeps them too).
_MACHINE_LINE = re.compile(r"^\s*\[[A-Z]+\]")


@dataclass(frozen=True, slots=True)
class Located:
    """One sentence carrying one family, addressable enough to be put back."""

    family: str
    paragraph: int
    sentence: int
    text: str


def is_machine_line(paragraph: str) -> bool:
    """A status or offer line, or a system's own capitals: the book speaking as a machine."""
    if _MACHINE_LINE.match(paragraph):
        return True
    letters = [char for char in paragraph if char.isalpha()]
    return len(letters) >= 12 and sum(char.isupper() for char in letters) / len(letters) > 0.8


def sentences_of(paragraph: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_END.split(paragraph.strip()) if part.strip()]


def _families_of(sentence: str, long_words: float | None = None) -> tuple[str, ...]:
    found: list[str] = []
    if _ABSENCE.search(sentence):
        found.append(ABSENCE)
    if _PARADOX_TURN.search(sentence) or _PARADOX_CONTRAST.search(sentence):
        found.append(PARADOX)
    if _THE_WAY.search(sentence):
        found.append(THE_WAY)
    if _has_echo(sentence):
        found.append(ECHO)
    if len(_AND.findall(sentence)) >= CHAIN_ANDS:
        found.append(CHAINED_AND)
    if long_words is not None and len(sentence.split()) > long_words:
        found.append(LONG)
    return tuple(found)


def _has_echo(sentence: str) -> bool:
    """Two different content words each said twice inside one sentence.

    *Stopped anyway and looked, the way he always stopped and looked*: the phrase comes back
    with a word dropped, so a repeated run would miss it; two content words (*stopped*,
    *looked*) each repeated is the shape, and a sentence that repeats one word is left alone.
    """
    words = [word.lower() for word in _WORD.findall(sentence)]
    if len(words) < 6:
        return False
    counts: dict[str, int] = {}
    for word in words:
        if len(word) >= 4 and word not in _STOPWORDS:
            counts[word] = counts.get(word, 0) + 1
    return sum(1 for count in counts.values() if count >= 2) >= 2


_STOPWORDS = frozenset(
    (
        "that", "this", "with", "from", "they", "them", "their", "there", "then", "than",
        "were", "when", "what", "have", "been", "into", "over", "your", "will", "would",
        "could", "about", "which", "where", "while", "after", "before", "because",
    )
)


def locate(text: str, *, long_words: float | None = None) -> tuple[Located, ...]:
    """Every sentence carrying a family, in reading order; one entry per family it carries.

    `long_words` is the long family's threshold; without one the family locates nothing.
    """
    located: list[Located] = []
    for p_index, paragraph in enumerate(text.split("\n\n")):
        if not paragraph.strip() or is_machine_line(paragraph):
            continue
        for s_index, sentence in enumerate(sentences_of(paragraph)):
            for family in _families_of(sentence, long_words):
                located.append(Located(family, p_index, s_index, sentence))
    return tuple(located)


def longest_sentence(text: str) -> int:
    """The longest counted sentence on the page, in words; zero with none."""
    return max(
        (
            len(sentence.split())
            for paragraph in text.split("\n\n")
            if paragraph.strip() and not is_machine_line(paragraph)
            for sentence in sentences_of(paragraph)
        ),
        default=0,
    )


def word_count(text: str) -> int:
    return sum(
        len(paragraph.split())
        for paragraph in text.split("\n\n")
        if paragraph.strip() and not is_machine_line(paragraph)
    )


def density(
    text: str,
    located: Sequence[Located] | None = None,
    *,
    long_words: float | None = None,
) -> dict[str, float]:
    """Located sentences per thousand counted words, by family; every family present, zero
    where none."""
    found = locate(text, long_words=long_words) if located is None else located
    words = word_count(text) or 1
    counts = dict.fromkeys(FAMILIES, 0)
    for item in found:
        counts[item.family] += 1
    return {family: 1000.0 * count / words for family, count in counts.items()}


def ceilings(chapters: Iterable[str]) -> dict[str, float] | None:
    """The highest density each family reaches on the shelf's own chapters, or `None` with none.

    The market's number, never ours: `application/exemplars.load_shelf` hands over the
    operator's hand-placed openings, and a page is held to the rate the shelf's most
    tell-heavy chapter runs at, family by family. `None` is no shelf, no ceiling, the ladder as
    it was.
    """
    pages = [chapter for chapter in chapters if chapter.strip()]
    if not pages:
        return None
    # The long family's threshold is the shelf's own longest sentence, so the shelf's rate
    # for it is zero by construction and every sentence past it on a page is over.
    longest = float(max(longest_sentence(page) for page in pages))
    rates = [density(page, long_words=longest) for page in pages]
    limits = {family: max(rate[family] for rate in rates) for family in FAMILIES}
    limits[LONG_WORDS] = longest
    return limits


def over(text: str, limits: Mapping[str, float] | None) -> tuple[str, ...]:
    """The families whose density on this page outruns the shelf's; empty with no shelf."""
    if limits is None:
        return ()
    rate = density(text, long_words=limits.get(LONG_WORDS))
    return tuple(family for family in FAMILIES if rate[family] > limits.get(family, 0.0))


def replace_sentence(text: str, located: Located, replacement: str) -> str:
    """The text with one located sentence said again, and nothing else touched.

    Addressed by paragraph and sentence index rather than by string search, so a sentence that
    occurs twice on the page (the echo family's own habit) is replaced where it was located.
    """
    paragraphs = text.split("\n\n")
    parts = sentences_of(paragraphs[located.paragraph])
    if located.sentence >= len(parts) or parts[located.sentence] != located.text:
        return text
    parts[located.sentence] = replacement.strip()
    paragraphs[located.paragraph] = " ".join(parts)
    return "\n\n".join(paragraphs)


__all__ = [
    "ABSENCE",
    "CHAINED_AND",
    "CHAIN_ANDS",
    "ECHO",
    "FAMILIES",
    "LONG",
    "LONG_WORDS",
    "PARADOX",
    "THE_WAY",
    "Located",
    "ceilings",
    "density",
    "is_machine_line",
    "locate",
    "longest_sentence",
    "over",
    "replace_sentence",
    "sentences_of",
    "word_count",
]
