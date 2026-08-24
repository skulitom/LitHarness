"""Blinding for the simulated-readership backtest: identity out, craft untouched.

PREREG.md §4 is the contract. The blinding function strips identity and popularity markers
-- the fiction's title and the author's name wherever they appear (exact and normalised
forms), chapter-title lines, URLs, platform self-references, and author's-note blocks -- and
never touches the prose otherwise. It does not rename characters (renaming is §120's sham
arm, not blinding) and does not reflow or merge paragraphs, so the paragraphing confound
stays measurable rather than laundered away. The blinded text is what gets cached, and the
digest is computed on that final text: it is the content address the whole programme cites,
so it must be stable across runs and platforms. It is -- hashlib and the `re` module are
locale-independent and nothing here consults the environment.

One recorded limit: a title that is a single common English word of five letters or fewer
(e.g. "Rise") is matched only when it carries distinguishing typography -- quoted,
italic-marked, or title-case mid-sentence. A blanket replace would mangle every ordinary
sentence containing the word, and mangling prose is the one thing blinding must not do.
Multi-word and longer titles match everywhere, case-insensitively. The same guard applies
to a one-word short author name; the `by <author>` / `<author> presents` handle forms carry
their own disambiguating context and always match.
"""

from __future__ import annotations

import functools
import hashlib
import re
from dataclasses import dataclass

__all__ = ["STRIPPED_CLASSES", "Blinded", "blind", "first_words"]

#: The literal replacement token. Bracketed and lowercase so a redaction can never be
#: mistaken for surviving prose, and so re-blinding an already-blind text finds nothing.
REDACTED = "[redacted]"

#: One count key per stripped class. Every call reports all of them, zero included.
STRIPPED_CLASSES: tuple[str, ...] = (
    "title",
    "author",
    "chapter_heading",
    "url",
    "platform",
    "author_note",
)

#: A candidate chapter-heading line longer than this is presumed prose that merely opens
#: with a heading word ("Book club met on Thursday..." stretched across a wrapped line).
_LINE_LIMIT = 80

#: A single alphabetic token of this many letters or fewer is treated as possibly-common
#: and stripped only with distinguishing typography. See the module docstring.
_MAX_SHORT_WORD = 5

_CHAPTER_HEADING = re.compile(r"\s*(?:chapter|ch\.?|episode|part|book)\b.*", re.IGNORECASE)
_AUTHOR_NOTE = re.compile(r"\s*\[?\s*author'?s? note\b.*", re.IGNORECASE)
_PLATFORM = re.compile(
    r"royal ?road|rising stars|trending|patreon|ko-fi|discord", re.IGNORECASE
)
_URL = re.compile(r"(?<![\w.])(?:https?://|www\.)\S+", re.IGNORECASE)

_DOUBLE_QUOTES = '["\u201c\u201d]'
_SINGLE_QUOTES = "['\u2018\u2019\u02bc]"
#: Horizontal whitespace only: a phrase match must not reach across a line break.
_HORIZONTAL = r"[^\S\n]"


@dataclass(frozen=True, slots=True)
class Blinded:
    """A blinded text, its content address, and how much of each class was stripped.

    `digest` is the full-length sha256 hex of `text.encode("utf-8")` -- the hash of the
    blinded output, not of the input, because the blinded output is what every downstream
    cache and reported number is addressed by.
    """

    text: str
    digest: str
    removed: dict[str, int]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _phrase_core(phrase: str) -> str:
    """Build a regex body matching `phrase` in its normalised forms.

    Case is handled by the IGNORECASE flag on the compiled pattern; straight and curly
    quotes/apostrophes are unified into character classes, and whitespace runs collapse to
    horizontal whitespace (never a line break, so a match cannot span paragraphs).
    """
    parts: list[str] = []
    for char in phrase.casefold():
        if char == '"':
            parts.append(_DOUBLE_QUOTES)
        elif char in "'\u2018\u2019\u02bc":
            parts.append(_SINGLE_QUOTES)
        elif char.isspace():
            parts.append(_HORIZONTAL + "+")
        else:
            parts.append(re.escape(char))
    return "".join(parts)


def _guarded_patterns(phrase: str) -> tuple[re.Pattern[str], ...]:
    """Patterns for a short common word: only with distinguishing typography.

    The title-case alternative must sit mid-sentence: not at a string or line start, and
    not directly after a sentence terminator (+ optional closing quote + one space), which
    is exactly where an ordinary capitalised common word is indistinguishable from a title.
    Each lookbehind is deliberately fixed-width; Python requires it.
    """
    core = _phrase_core(phrase)
    gap = _HORIZONTAL + "*"
    display = phrase.strip()
    title_case = re.escape(display[0].upper() + display[1:])
    return (
        re.compile(rf"{_DOUBLE_QUOTES}{gap}{core}{gap}{_DOUBLE_QUOTES}", re.IGNORECASE),
        re.compile(rf"{_SINGLE_QUOTES}{gap}{core}{gap}{_SINGLE_QUOTES}", re.IGNORECASE),
        re.compile(rf"[*_]{core}[*_]", re.IGNORECASE),
        re.compile(
            r"(?<!^)(?<!\n)"
            rf"(?<![.!?\u2026\u201d\u2019\"]{_HORIZONTAL})"
            rf"(?<!\w){title_case}(?!\w)"
        ),
    )


@functools.cache
def _bare_patterns(phrase: str) -> tuple[re.Pattern[str], ...]:
    """Patterns for a bare occurrence of `phrase` in running prose."""
    stripped = phrase.strip()
    if not stripped:
        return ()
    if len(stripped) <= _MAX_SHORT_WORD and stripped.isalpha():
        return _guarded_patterns(phrase)
    return (re.compile(rf"(?<!\w)(?:{_phrase_core(phrase)})(?!\w)", re.IGNORECASE),)


@functools.cache
def _author_handle_patterns(phrase: str) -> tuple[re.Pattern[str], ...]:
    """`by <author>` and `<author> presents` -- context disambiguates, so always match."""
    core = _phrase_core(phrase)
    gap = _HORIZONTAL + "+"
    by_form = re.compile(rf"(?<!\w)by(?:\s*:\s*|\s+)(?:{core})(?!\w)", re.IGNORECASE)
    presents_form = re.compile(rf"(?<!\w)(?:{core}){gap}presents(?!\w)", re.IGNORECASE)
    return (by_form, presents_form)


def _apply(
    text: str,
    phrase: str,
    key: str,
    patterns: tuple[re.Pattern[str], ...],
    removed: dict[str, int],
) -> str:
    if not phrase.strip():
        return text
    for pattern in patterns:
        text, count = pattern.subn(REDACTED, text)
        removed[key] += count
    return text


def _blind_paragraph(
    paragraph: str, *, title: str, author: str, removed: dict[str, int]
) -> str:
    """Strip one paragraph, preserving the single-newline structure of surviving lines.

    An author's-note opening line consumes the rest of its paragraph, because the block
    runs through the next blank line and the next blank line is exactly the paragraph
    boundary. A paragraph left blank by all this stripping returns blank and is dropped
    by the caller.
    """
    kept_lines: list[str] = []
    for line in paragraph.split("\n"):
        if _AUTHOR_NOTE.match(line):
            removed["author_note"] += 1
            break
        if len(line) <= _LINE_LIMIT and _CHAPTER_HEADING.match(line):
            removed["chapter_heading"] += 1
            continue
        if _PLATFORM.search(line):
            removed["platform"] += 1
            continue
        kept_lines.append(line)
    survivor = "\n".join(kept_lines)
    survivor, urls = _URL.subn("", survivor)
    removed["url"] += urls
    survivor = _apply(survivor, author, "author", _author_handle_patterns(author), removed)
    survivor = _apply(survivor, author, "author", _bare_patterns(author), removed)
    return _apply(survivor, title, "title", _bare_patterns(title), removed)


def blind(text: str, *, title: str, author: str) -> Blinded:
    """Strip identity and popularity markers from `text`; never touch the craft.

    Strips the fiction's `title` and the `author`'s name/handle forms (exact and
    normalised: case-insensitive, quote glyphs unified, whitespace runs collapsed),
    chapter-heading lines of at most 80 characters, URL tokens, support-plug platform
    lines, and author's-note blocks. Paragraph boundaries between surviving paragraphs are
    preserved exactly; a fully-stripped paragraph leaves no double-blank residue. Empty
    input yields an empty `Blinded` with all-zero counts. Deterministic by construction.
    """
    removed: dict[str, int] = dict.fromkeys(STRIPPED_CLASSES, 0)
    if not text:
        return Blinded(text="", digest=_sha256(""), removed=removed)
    survivors = [
        cleaned
        for paragraph in text.split("\n\n")
        if (cleaned := _blind_paragraph(paragraph, title=title, author=author, removed=removed))
        .strip()
    ]
    blinded = "\n\n".join(survivors)
    return Blinded(text=blinded, digest=_sha256(blinded), removed=removed)


def first_words(text: str, n: int) -> str:
    """The first `n` words extended forward to the next paragraph boundary.

    For the P-arm's "first ~500 words": the excerpt never cuts a paragraph in half, so the
    paragraph holding word `n` is shown whole. Text with fewer than `n` words returns
    whole; non-positive `n` returns the empty string.
    """
    if n <= 0:
        return ""
    paragraphs = text.split("\n\n")
    seen = 0
    for index, paragraph in enumerate(paragraphs):
        seen += len(paragraph.split())
        if seen >= n:
            return "\n\n".join(paragraphs[: index + 1])
    return text
