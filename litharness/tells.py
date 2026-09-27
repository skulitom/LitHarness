"""Narration-only AI-tell counter, ported from the incumbent's domain/tells.py: sentence shapes the operator's
reads named, held to the highest rate per 1,000 words a shelf opening reaches. It has no ear: a rewrite can read
worse and carry no family ("like a bar of soap goes"). Speech, italics and System lines are never counted."""
from __future__ import annotations

import re
from collections import Counter
from statistics import median

WORD = re.compile(r"\b\w+(?:['’\-]\w+)*\b")
LONG_WORDS, SHORT_WORDS, CHAIN_ANDS = 35, 4, 3  # the shelf's longest sentences ran 35, 30 and 33 words
# The shelf's ceilings per 1,000 words; sentences over 35 words are located as "long" beside them, never a family.
CEILINGS: dict[str, float] = {"absence": 2.6, "paradox": 0.0, "the_way": 0.6, "echo": 1.0, "chained_and": 0.5}
# Narration only: an absence or an opening "not"; a word turned back on itself; the way somebody always does it.
PATTERNS: dict[str, re.Pattern[str]] = {
    "absence": re.compile(r"\b(?:nobody|no one|no-one|nothing|never)\b|^(?:not|no)\s+\w", re.I),
    "paradox": re.compile(
        r"\b(\w{4,})\b[^.;:]{0,40}\b(?:without|not|than)\b[^.;:]{0,25}\b\1\b|\bnot (?:a|an|the) "
        r"\w+(?:['’]s)?[,;] (?:a|an|the|that['’]s|it['’]s|just|but) \w+", re.I),
    "the_way": re.compile(
        r"\bthe way (?:he|she|they|you|i|we|it|a|an|the|somebody|people|everybody|nobody)\b", re.I),
}
#: Echo: two different content words (4+ letters, not these) each said twice in one sentence.
_TOKEN = re.compile(r"[A-Za-z][A-Za-z'’]*")
_STOP = frozenset(
    "that this with from they them their there then than were when what have been into over your "
    "will would could about which where while after before because".split())
_SENTENCE = re.compile(r"\S.*?(?:[.!?](?=\s)|\Z)", re.S)  # split after . ! ? and whitespace
_PARAGRAPH = re.compile(r"\n[ \t]*\n")
_MACHINE = re.compile(r"[ \t]*\[(?:.*\][ \t]*$|[A-Z]+\])")  # a [Label: value] or [TAG] line
# Speech is double quotes (a single one is often an apostrophe); an open mark runs to its end.
_SPEECH = re.compile(r'["“”][^"“”]*(?:["“”]|$)')
_ITALIC = re.compile(r"\*{1,2}[^*\n]+?\*{1,2}|(?<!\w)_[^_\n]+?_(?!\w)")


def words(text: str) -> int:
    return len(WORD.findall(text))


def _paragraphs(text: str) -> list[str]:
    """Non-empty paragraphs, System lines cut: brackets, or 12+ letters over 80% capitals."""
    def machine(line: str) -> bool:
        caps = [c.isupper() for c in line if c.isalpha()]
        return len(caps) >= 12 and sum(caps) > 0.8 * len(caps) or bool(_MACHINE.match(line))

    page = "\n".join("" if machine(line) else line for line in text.splitlines())
    return [part.strip() for part in _PARAGRAPH.split(page) if part.strip()]


def sentences(text: str) -> list[str]:
    """Sentences in reading order: paragraphs on blank lines, then after . ! or ? and a space."""
    return [m.group() for p in _paragraphs(text) for m in _SENTENCE.finditer(p) if words(m.group())]


def _cut(match: re.Match[str]) -> str:
    """A cut span that ended a sentence leaves a paragraph break; one inside a sentence, a space."""
    rest = match.string[match.end() :].lstrip()
    ended = match.group().rstrip("\"“”*_ ")[-1:] in (".", "!", "?")
    return "\n\n" if ended and (not rest or rest[0].isupper()) else " "


def narration(text: str) -> str:
    """The text without speech, italics or System lines; a cut sentence end stays a boundary."""
    kept: list[str] = []
    for paragraph in _paragraphs(text):
        cut = _ITALIC.sub(_cut, _SPEECH.sub(_cut, paragraph))
        kept += [" ".join(part.split()) for part in _PARAGRAPH.split(cut) if part.strip()]
    return "\n\n".join(kept)


def _hide(match: re.Match[str]) -> str: return "\0" * len(match.group())


def locate(text: str) -> dict[str, list[str]]:
    """Family -> sentences carrying it, verbatim, in order. Word families read narration only;
    echo, chained and, long read the whole sentence, if at most half is speech or italics."""
    found: dict[str, list[str]] = {family: [] for family in (*CEILINGS, "long")}
    for paragraph in _paragraphs(text):
        masked = _ITALIC.sub(_hide, _SPEECH.sub(_hide, paragraph))
        for match in _SENTENCE.finditer(paragraph):
            (a, b), sentence = match.span(), match.group()
            told = " ".join(masked[a:b].replace("\0", " ").split())
            hits = [family for family, pattern in PATTERNS.items() if pattern.search(told)]
            if masked[a:b].count("\0") * 2 <= b - a:
                tokens = [token.lower() for token in _TOKEN.findall(sentence)]
                content = Counter(t for t in tokens if len(t) >= 4 and t not in _STOP)
                whole = {"echo": len(tokens) >= 6 and sum(n >= 2 for n in content.values()) >= 2,
                         "chained_and": tokens.count("and") >= CHAIN_ANDS,
                         "long": words(sentence) > LONG_WORDS}
                hits += [family for family, hit in whole.items() if hit]
            for family in hits:
                found[family].append(sentence)
    return found


def rates(text: str) -> dict[str, float]:
    """Located sentences per 1,000 words outside System lines, speech kept: the shelf's measure."""
    total, found = max(words(" ".join(_paragraphs(text))), 1), locate(text)
    return {family: 1000.0 * len(found[family]) / total for family in CEILINGS}


def over(text: str) -> list[str]:
    """The families whose rate on this page runs past the shelf's ceiling."""
    return [family for family, rate in rates(text).items() if rate > CEILINGS[family]]


def shape(text: str) -> dict:
    """The long sentences as located; the median length and the share under four words over
    every sentence outside System lines, speech kept, as the shelf's census read them."""
    lengths = [words(sentence) for sentence in sentences(text)]
    return {"long": locate(text)["long"], "median": float(median(lengths)) if lengths else 0.0,
            "short_share": sum(n < SHORT_WORDS for n in lengths) / (len(lengths) or 1)}
