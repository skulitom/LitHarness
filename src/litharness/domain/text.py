"""Canonical manuscript text: one normal form, one hash, one offset space.

Every content hash, evidence span and patch offset in this system is defined against
the *canonical* form of a text, never against whatever bytes arrived. Three decisions,
each recorded because getting one wrong is a silent corruption rather than an error.

**Line endings normalize to LF.** CRLF and lone CR both become LF before hashing. This
is not a style preference: `litharness-contracts` verifies evidence spans by SHA-256
over byte ranges of scene text, and a sibling repository in this project was one commit
away from having every one of those hashes invalidated by a Windows checkout, because
`core.autocrlf=true` rewrites LF to CRLF on the way out of git. A hash taken over
un-normalized text is a latent platform bug that shows up as "the fixture broke on
someone else's machine".

**Unicode normalizes to NFC.** Editors, clipboards and macOS filesystems disagree about
composed versus decomposed forms, so the same visible text can carry two different byte
sequences. NFC is the web-and-git default and the one Python's `unicodedata` produces
most cheaply.

**Offsets are character offsets into the canonical string, and hashes are over its
UTF-8 encoding.** This matches how contracts' consumers already resolve evidence —
`text[start:end]` on a Python `str`, then `.encode("utf-8")` before hashing — so a span
produced here resolves there without a coordinate conversion. Byte offsets would be the
other defensible choice; they are *not* interchangeable, and mixing the two silently
mis-slices any text containing a non-ASCII character.

Canonicalization is applied on ingest, so what is stored is what was hashed. Hashing a
canonical form while storing a raw one would make every stored hash unverifiable on
re-read.
"""

from __future__ import annotations

import unicodedata
from hashlib import sha256


def canonicalize(text: str) -> str:
    """Return the canonical form of a manuscript text.

    Idempotent: ``canonicalize(canonicalize(t)) == canonicalize(t)`` for all ``t``.
    """
    # Order matters: normalize line endings first so that NFC never sees a CR, and
    # handle CRLF before lone CR so a CRLF does not become two newlines.
    unified = text.replace("\r\n", "\n").replace("\r", "\n")
    return unicodedata.normalize("NFC", unified)


def is_canonical(text: str) -> bool:
    return canonicalize(text) == text


def content_hash(text: str) -> str:
    """SHA-256 over the UTF-8 encoding of the canonical form, as lowercase hex."""
    return sha256(canonicalize(text).encode("utf-8")).hexdigest()


def excerpt_hash(text: str, start: int, end: int) -> str:
    """Content hash of ``text[start:end]``, with the text canonicalized first.

    Slicing a non-canonical text would produce offsets that do not survive a round
    trip through storage, so the canonical form is taken before slicing rather than
    after.
    """
    canonical = canonicalize(text)
    if not 0 <= start <= end <= len(canonical):
        raise ValueError(
            f"span {start}..{end} is outside the canonical text of length {len(canonical)}"
        )
    return content_hash(canonical[start:end])


def slice_canonical(text: str, start: int, end: int) -> str:
    canonical = canonicalize(text)
    if not 0 <= start <= end <= len(canonical):
        raise ValueError(
            f"span {start}..{end} is outside the canonical text of length {len(canonical)}"
        )
    return canonical[start:end]


#: Fraction of a passage's words behind the stop point. **Frozen at §124's value and it is the
#: same number for the same reason**: `research/quality-measurement/anticipation.py` registered
#: 0.6 before any call was made, and a reader stopped at a different place is a reader answering
#: a different question. `tests/test_reader_futures.py` pins the two implementations against each
#: other — the research module cannot be imported from inside the package (CONTRIBUTING's
#: dependency direction), so one rule has two homes and a test is what keeps them one rule.
STOP_FRACTION = 0.6


def stop_point(text: str, fraction: float = STOP_FRACTION) -> str:
    """The passage-so-far: the paragraph boundary nearest `fraction` of the words.

    **Why a reader is stopped at all**, and it is the operator's direction of 2026-08-25:
    *"The readers should be fed text only up until a point and then the rest left out. The
    readers have to predict what happens next."* A reader shown a whole chapter has no future
    to predict and nothing left to want; what it can do instead is review, which is the one
    thing this project has no use for from a reader (`plan/reader-judge-loop.md`, and §89's
    verdict channel).

    **The boundary snaps to a paragraph so the instrument never stops anybody mid-thought.**
    Deterministic, always at least one paragraph, and never the whole text — a probe after the
    final paragraph asks about a future the passage no longer holds. A single-paragraph text
    raises rather than silently returning everything, because "there was no future to ask
    about" and "the reader saw it all" must not print the same.
    """
    paragraphs = [part for part in text.split("\n\n") if part.strip()]
    if len(paragraphs) < 2:
        raise ValueError("a passage needs at least two paragraphs to leave a future")
    total = sum(len(part.split()) for part in paragraphs)
    target = fraction * total
    best_index, best_gap, seen = 1, float("inf"), 0
    for index, paragraph in enumerate(paragraphs[:-1], start=1):
        seen += len(paragraph.split())
        if (gap := abs(seen - target)) < best_gap:
            best_gap, best_index = gap, index
    return "\n\n".join(paragraphs[:best_index])
