"""The memorisation screen's scoring: frozen probe bytes and deterministic, call-free scoring.

PREREG.md §3 is the contract here. Every candidate book is probed with its blinded excerpt
before any main-arm call — title, author, continuation — and any hit on any probe excludes the
book into the labelled `recognised` stratum. This module owns the frozen probe turns and the
deterministic scoring of the responses; the calls themselves happen elsewhere. Nothing in this
file performs or simulates a model call, touches the network, or reads the corpus.

Scoring is deliberately blunt. A screen that sometimes lets a recognised book through
contaminates the confirmatory set; a screen that sometimes excludes a clean book only shrinks
N, which §3 already prices as INSUFFICIENT_N rather than as a smaller floor. Where a judgment
call arises, this code therefore errs toward calling a hit.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

#: Byte-frozen probe turns; `{excerpt}` is the blinded excerpt. Three probes, exactly — the
#: recognition screen is an instrument, and a reworded prompt is a different instrument. Each
#: asks only for recall or behaviour; none solicits or even mentions a verdict.
PROBE_TITLE: str = (
    "Below is an excerpt from a serialised web fiction. If you recognise this passage and can "
    "name the work's title, reply with just the title. If you do not recognise it, reply "
    '"unknown".\n\n{excerpt}'
)
PROBE_AUTHOR: str = (
    "Below is an excerpt from a serialised web fiction. If you recognise this passage and can "
    "name its author, reply with just the author's name. If you do not recognise it, reply "
    '"unknown".\n\n{excerpt}'
)
PROBE_CONTINUATION: str = (
    "Below is an excerpt from a serialised web fiction. Continue the excerpt's final sentence "
    "for about 50 words, picking up exactly where the text stops. Reply with only the "
    "continuation.\n\n{excerpt}"
)

PROBES: tuple[tuple[str, str], ...] = (
    ("title", PROBE_TITLE),
    ("author", PROBE_AUTHOR),
    ("continuation", PROBE_CONTINUATION),
)

#: The closed probe-name set `score_probe` dispatches over.
KNOWN_PROBES: frozenset[str] = frozenset(name for name, _ in PROBES)


# ------------------------------------------------------------------------------ normalisation

#: Curly punctuation unified to its straight ASCII form before anything else looks at the
#: text. Single quotes and apostrophes are deleted rather than spaced: they live inside words
#: ("it's", "King's"), so spacing them would split one word into two junk tokens.
_UNIFY: dict[str, str | None] = {
    "\u2018": None,  # left single quotation mark
    "\u2019": None,  # right single quotation mark (apostrophe)
    "'": None,
    "\u201c": '"',  # left double quotation mark
    "\u201d": '"',  # right double quotation mark
    "\u2010": "-",
    "\u2011": "-",
    "\u2012": "-",
    "\u2013": "-",  # en dash
    "\u2014": "-",  # em dash
    "\u2212": "-",
    "\u00a0": " ",  # no-break space
}

#: Anything not a letter, digit, or space is dropped to a space, so that punctuation at a
#: token boundary splits words instead of fusing them ("odd--job" -> "odd job").
_PUNCTUATION = re.compile(r"[^0-9a-z\s]")
_WHITESPACE = re.compile(r"\s+")

#: Leading English articles, longest first so "an" is tested before "a".
_ARTICLES: tuple[str, ...] = ("the ", "an ", "a ")

_UNKNOWN = "unknown"


def normalise(s: str) -> str:
    """Case-fold, unify quote/dash variants, drop punctuation, strip a leading article.

    The one normaliser every scorer uses, so a title scored against two responses is scored
    the same way both times. A leading article is stripped because a model asked to name
    "The Wandering Inn" may reply "Wandering Inn" and both answers are the same memory; an
    article anywhere else stays, since removing it would fuse distinct word sequences.
    """
    folded = s.casefold().translate({ord(k): v for k, v in _UNIFY.items()})
    text = _WHITESPACE.sub(" ", _PUNCTUATION.sub(" ", folded)).strip()
    for article in _ARTICLES:
        if text.startswith(article):
            return text[len(article):]
    return text


def _tokens(s: str) -> list[str]:
    return normalise(s).split()


# ----------------------------------------------------------------------------------- matching


def _containment_span(haystack: list[str], needle: list[str]) -> str | None:
    """The matched needle span as a space-joined string, or None if absent contiguously."""
    width = len(needle)
    if width == 0 or len(haystack) < width:
        return None
    for start in range(len(haystack) - width + 1):
        if haystack[start : start + width] == needle:
            return " ".join(needle)
    return None


_QUOTED_DOUBLE = re.compile('["\u201c]([^"\u201d]+)["\u201d]')
_QUOTED_SINGLE = re.compile("['\u2018]([^'\u2019]+)['\u2019]")
_RAW_WORD = re.compile(r"\S+")


def _quoted_and_capitalised_spans(raw_response: str) -> list[str]:
    """Spans of the raw response that read as names: quoted strings and capitalised runs.

    Capitalised runs include sentence-initial words. That widens the hit side on purpose: a
    false exclusion only shrinks N, which §3 prices honestly, while a missed recognition
    contaminates the confirmatory set.
    """
    spans = [match.group(1) for match in _QUOTED_DOUBLE.finditer(raw_response)]
    spans.extend(match.group(1) for match in _QUOTED_SINGLE.finditer(raw_response))
    run: list[str] = []
    for raw_word in _RAW_WORD.findall(raw_response):
        if raw_word[:1].isupper():
            run.append(raw_word)
        elif run:
            spans.append(" ".join(run))
            run = []
    if run:
        spans.append(" ".join(run))
    return spans


def title_hit(response: str, title: str) -> bool:
    """True when the normalised title appears as a contiguous token subsequence.

    Titles whose normalised form is a single token of <= 4 characters are too generic for bare
    containment -- "unknown, but it mentions a road" must not confirm the title "Road" -- so
    such a title only hits through exact token equality with a quoted or capitalised span of
    the raw response, evidence the responder treated the word as a name.
    """
    return _title_span(response, title) is not None


def author_hit(response: str, author: str) -> bool:
    """True on normalised containment of the author name, or on its distinctive token.

    An author of the form "First Last" also hits on the rarer token alone -- the longer of
    the two -- when it runs at least 5 characters, so "sounds like Martha" confirms
    "Martha Wells" while "by John" does not confirm "John Smith": "john" is 4 characters and
    also the shorter token, so neither escape hatch opens.
    """
    return _author_span(response, author) is not None


def continuation_hit(response: str, truth: str, *, n: int = 8) -> bool:
    """True when any n-gram of the response appears verbatim as an n-gram of the truth.

    Eight tokens of verbatim continuation is memory, not style; seven shared tokens can still
    be the register carrying a fluent writer. `n` is keyword-only so call sites state the
    boundary they are running at.
    """
    if n <= 0:
        raise ValueError(f"n must be positive, got {n}")
    truth_grams = set(_ngrams(_tokens(truth), n))
    if not truth_grams:
        return False
    return any(gram in truth_grams for gram in _ngrams(_tokens(response), n))


def _ngrams(tokens: list[str], n: int) -> list[tuple[str, ...]]:
    if len(tokens) < n:
        return []
    return [tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


# ----------------------------------------------------------------------------------- records


@dataclass(frozen=True, slots=True)
class ProbeResult:
    """One scored probe: which probe ran, whether it hit, and what the match was."""

    probe: str  # "title" | "author" | "continuation"
    hit: bool
    detail: str  # the matched span for a hit, "" otherwise


def score_probe(
    probe: str,
    response: str,
    *,
    title: str,
    author: str,
    truth_continuation: str,
) -> ProbeResult:
    """Score one probe response against one book's identity, deterministically.

    A response that is empty, whitespace, or "unknown" once normalised scores no hit on any
    probe -- declining to answer is the honest negative this screen exists to hear. An unknown
    probe name is a programming error, not a miss, and raises naming the three known probes.
    """
    if probe not in KNOWN_PROBES:
        known = ", ".join(sorted(KNOWN_PROBES))
        raise ValueError(f"unknown probe {probe!r}; known probes are {known}")
    if normalise(response) in ("", _UNKNOWN):
        return ProbeResult(probe=probe, hit=False, detail="")
    span: str | None = None
    if probe == "title":
        span = _title_span(response, title)
    elif probe == "author":
        span = _author_span(response, author)
    else:
        span = _continuation_span(response, truth_continuation, 8)
    if span is None:
        return ProbeResult(probe=probe, hit=False, detail="")
    return ProbeResult(probe=probe, hit=True, detail=span)


def classify(results: Sequence[ProbeResult]) -> str:
    """`recognised` if any probe hit on any turn, else `clean`.

    The disjunction is the whole screen: §3 excludes a book on any hit on any probe, on either
    model, so there is no per-probe weighting to argue about.
    """
    return "recognised" if any(result.hit for result in results) else "clean"


# ------------------------------------------------------------------------ span-level helpers


def _title_span(response: str, title: str) -> str | None:
    title_tokens = _tokens(title)
    if not title_tokens:
        return None
    response_tokens = _tokens(response)
    if len(title_tokens) == 1 and len(title_tokens[0]) <= 4:
        for span in _quoted_and_capitalised_spans(response):
            if _tokens(span) == title_tokens:
                return title_tokens[0]
        return None
    return _containment_span(response_tokens, title_tokens)


def _author_span(response: str, author: str) -> str | None:
    response_tokens = _tokens(response)
    author_tokens = _tokens(author)
    full = _containment_span(response_tokens, author_tokens)
    if full is not None:
        return full
    if len(author_tokens) == 2:
        distinctive = max(author_tokens, key=len)
        if len(distinctive) >= 5 and distinctive in response_tokens:
            return distinctive
    return None


def _continuation_span(response: str, truth: str, n: int) -> str | None:
    truth_grams = set(_ngrams(_tokens(truth), n))
    for gram in _ngrams(_tokens(response), n):
        if gram in truth_grams:
            return " ".join(gram)
    return None