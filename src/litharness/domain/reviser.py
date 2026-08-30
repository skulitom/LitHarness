"""Containment for a revision: what a rewrite of an unaccepted draft may not change.

**This module exists because the reviser's promise had to stop being a promise.** The
operator's read-12 directive is that a stronger model rewrites the finished draft for
sentence and paragraph structure. Everything in the assembled scene prompt that keeps a
scene honest — the packet's facts, the status line's numbers, the plan's named beat — is
a sentence somebody wrote, and §138's whole record is that a sentence in a prompt is the
surface a clause reaches worst. A second call given the whole scene and told *keep the
story* would be that surface again, one call later and with nothing checking it.

So the reviser is told, and then the return is **measured against the draft it was given**.
Every predicate here is deterministic, reads two strings, and re-derives nothing. A return
that fails any of them is discarded and the draft stands: the book is never hostage to the
reviser, which is the property that makes the stage safe to leave on.

**What is deliberately not here.** No ordering, no score, no preference between the draft
and the revision — §61(5) and §105.1. `contain` answers *may this text stand in for that
one*, which is a mechanical yes or no, and when it says no the answer is not "the draft was
better", it is "the revision changed something it was not allowed to change". The two
readings are not the same and only the second one is claimed.

**And the gates that decide whether the scene is any good are not here either.** The
revision goes down the same ladder the draft would have — `gate_draft`, `gate_integrity`,
`gate_progression` — because `application/handlers.py` runs the reviser in front of that
ladder rather than behind it. Containment is what the ladder cannot see: the ladder reads
one candidate and has no idea a different one was drawn first.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass

#: A line the book prints as a machine rather than as prose. Read from the same shape
#: `domain/draft.py` uses for the em-dash strip's exemption, and deliberately the same
#: shape rather than a `[STATUS]`-only pattern: `extraction` parses the status line, and
#: the graph line and any later bracketed line are printed by the same book for the same
#: kind of reader. One home for "the book is speaking as a machine here" (§160.3's rule
#: that there is one parsed surface is about what is *read*, not about what is protected).
_MACHINE_LINE = re.compile(r"^\[[A-Z][A-Z ]*\]")

#: A run of letters. **Apostrophes and hyphens split a token rather than joining one**, which
#: is the cheap answer to a problem this module must not solve with a table of quotation
#: marks: a draft arrives with whichever apostrophe the model reached for, and a pattern
#: naming both is a pattern where a reader cannot tell two characters apart by looking. A
#: possessive splits into the name and a lowercase letter, and only the name is ever a
#: candidate, so nothing is lost by not knowing which apostrophe was used.
_WORD = re.compile(r"[A-Za-z]+")

#: A run of digits. Folded into the same check as a name because the two failures are one
#: failure: a fact the draft did not have, arriving in a call that was asked to change how
#: the draft reads.
_NUMBER = re.compile(r"\d+")

#: What ends a sentence. A newline counts: a paragraph break starts a sentence as surely as
#: a full stop does, and a heading or a line of dialogue on its own line has no stop at all.
_TERMINALS = ".!?\n"


class Breach(enum.StrEnum):
    """Which containment predicate refused, named so a decision row can say which.

    Values are read by an operator out of a `detail` string and never by code that
    branches on them, so they are words rather than codes.
    """

    EMPTY = "empty"
    MACHINE_LINE_CHANGED = "machine_line_changed"
    INTRODUCED = "introduced"
    LENGTH_MOVED = "length_moved"
    #: Not a breach of anything, and it is in this enum because the handler treats it the
    #: same way: the revision is not adopted and the draft stands. A reviser that returned
    #: its input changed nothing, so there is nothing to prefer and nothing to record
    #: beyond the fact that the call bought no movement.
    UNCHANGED = "unchanged"


@dataclass(frozen=True, slots=True)
class ReviserPolicy:
    """Mechanical limits on a revision. **Not a bar, and the distinction is the four checks.**

    A bar is a threshold a quantity has to clear before something is called good, and §81,
    §85, §87 and §89 are four entries about declaring one that could not do what it said.
    Neither number below judges prose. They bound how far a rewrite may move a length, in
    exactly the sense `PatchPolicy.min_length_ratio` already bounds one, and the failure
    they exist to catch is a revision that summarised the scene or wrote a new one.

    **The floor is where a summary starts and the ceiling is where new material does.**
    Splitting a chained sentence in two and subordinating a clause move a scene's length by
    a little in both directions; a rewrite that comes back at four fifths of the draft has
    dropped something, and one at a fifth again has added something. The band is wide enough
    that ordinary subordination, a varied opening and an observation moved into somebody's
    mouth all survive it — voicing costs attribution words, which is why the ceiling is
    further from 1.0 than the floor is.
    """

    min_word_ratio: float = 0.85
    max_word_ratio: float = 1.20

    def digest_material(self) -> dict[str, object]:
        return {
            "min_word_ratio": self.min_word_ratio,
            "max_word_ratio": self.max_word_ratio,
        }


@dataclass(frozen=True, slots=True)
class Containment:
    """Whether a returned revision may stand in for the draft it was drawn from."""

    held: bool
    breach: Breach | None = None
    detail: str | None = None


def machine_lines(text: str) -> tuple[str, ...]:
    """Every line the book prints as a machine, in order, exactly as written.

    Order and count are part of the value. `extraction.extract_state` mints one record per
    match of the sheet's pattern and places them all at one story position, so a revision
    that printed the line twice would write two canon snapshots that disagree at one key —
    which is precisely the shape `integrity.detect_contradictions` groups on and refuses.
    A tuple compares all three properties at once and no separate count check is needed.
    """
    return tuple(line for line in text.split("\n") if _MACHINE_LINE.match(line))


def _is_sentence_initial(text: str, index: int) -> bool:
    """Whether the token at ``index`` opens its sentence.

    Walks back over everything that is neither a letter or digit nor a sentence terminal —
    whitespace, quotation marks of either shape, brackets, a dash, a comma — and reports
    whether what is behind all of that is the start of the text or something that ended a
    sentence. **This is what keeps the introduced-token check off ordinary capitalisation**: a
    common word capitalised because it starts a sentence is not a name, and the alternative to
    detecting that structurally is a list of words that are allowed to be capitalised, which is
    the one thing `house` has deleted three clauses for.

    Written as *what it stops at* rather than as *what it skips*, so no table of punctuation
    has to be complete: a mark nobody thought of is skipped rather than mistaken for the end of
    a sentence, and the two things that genuinely end the walk are both one character wide.
    """
    cursor = index - 1
    while cursor >= 0 and not (text[cursor].isalnum() or text[cursor] in _TERMINALS):
        cursor -= 1
    return cursor < 0 or text[cursor] in _TERMINALS


def introduced(draft: str, revision: str) -> tuple[str, ...]:
    """Names and numbers the revision carries that the draft did not, sorted.

    **A name is a capitalised word that is not opening its sentence**, and a number is a run
    of digits anywhere. Both are compared case-folded against *every* token in the draft, not
    only against the draft's own capitalised ones: a word the draft used at the start of a
    sentence and the revision uses in the middle of one is the same word moved, and refusing
    that would refuse the rewrite for doing its job.

    The check is one-directional on purpose. A revision that *drops* a name has cut
    something, and what catches that is the length band plus the ladder below — dropping a
    name is not a thing this predicate can tell apart from a pronoun replacing it, and a
    predicate that guessed would be the second answer §184.4 refuses to invent.
    """
    held = {match.group().casefold() for match in _WORD.finditer(draft)}
    held |= {match.group() for match in _NUMBER.finditer(draft)}

    new: set[str] = set()
    for match in _WORD.finditer(revision):
        token = match.group()
        if not token[0].isupper():
            continue
        if _is_sentence_initial(revision, match.start()):
            continue
        if token.casefold() not in held:
            new.add(token)
    for match in _NUMBER.finditer(revision):
        if match.group() not in held:
            new.add(match.group())
    return tuple(sorted(new))


def contain(
    draft: str, revision: str, *, policy: ReviserPolicy | None = None
) -> Containment:
    """May ``revision`` stand in for ``draft``? Pure, total, and model-free.

    The order is cheapest-and-most-decisive first, so a return that is nothing like the
    draft is refused by the check that says so plainly rather than by a length ratio.
    """
    policy = policy or ReviserPolicy()
    text = revision.strip()
    if not text:
        return Containment(False, Breach.EMPTY, "the reviser returned nothing")

    if text == draft.strip():
        return Containment(
            False,
            Breach.UNCHANGED,
            "the reviser returned the draft unchanged; there is nothing to adopt",
        )

    drafted_lines, revised_lines = machine_lines(draft), machine_lines(revision)
    if drafted_lines != revised_lines:
        return Containment(
            False,
            Breach.MACHINE_LINE_CHANGED,
            f"the draft prints {len(drafted_lines)} machine line(s) and the revision "
            f"prints {len(revised_lines)}, or one of them differs; these are reproduced "
            "character for character or the revision is discarded",
        )

    added = introduced(draft, revision)
    if added:
        shown = ", ".join(added[:5])
        return Containment(
            False,
            Breach.INTRODUCED,
            f"the revision carries {len(added)} name(s) or number(s) the draft did not: "
            f"{shown}",
        )

    drafted_words = len(draft.split())
    revised_words = len(revision.split())
    ratio = revised_words / drafted_words if drafted_words else 0.0
    if not policy.min_word_ratio <= ratio <= policy.max_word_ratio:
        return Containment(
            False,
            Breach.LENGTH_MOVED,
            f"the revision is {revised_words} words against the draft's {drafted_words} "
            f"({ratio:.2f}), outside the band "
            f"[{policy.min_word_ratio}, {policy.max_word_ratio}]",
        )

    return Containment(True)


__all__ = [
    "Breach",
    "Containment",
    "ReviserPolicy",
    "contain",
    "introduced",
    "machine_lines",
]
