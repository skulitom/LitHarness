"""The return side of the machinery-word rail: whether a book took one of our words as a name.

**`house.MACHINERY_WORDS` already exists, and this module adds no second list.** That constant
is the vocabulary this system uses for its own machinery, and `tests/test_prompt_budget.py`
already keeps every word of it *out of* the prompts that shape prose a reader will read. This
module asks the other half of the same question, of the text that comes back.

**Serial Pilot 16 is why the other half is needed: the input rail held and the leak happened
anyway.** Its listing ran under an empty brief, and the listing role passes
`test_a_reader_facing_prompt_never_speaks_in_this_system_s_own_vocabulary` — the word `ladder`
is in neither `overview._TASK` nor `domain/writers.py`, which `litharness prompts --role
listing` is where anyone can check. The model coined *the Ladder* on its own, reaching the same
English metaphor for a progression system that §113 reached for the schema. Everything
downstream then behaved correctly and carried it: the title is drawn from the listing
(*Reading The Ladder Wrong*), and the Architect is told the world has to keep what the listing
promised, so the world came back with `ladder is_a Ladder` and `rung is_a Rung` — and `Rung`
is a printed column, on the page twice in chapter one as `[STATUS] Theo — Rung 1 | Depth 0/0`.
Read 11, the operator: *"'Ladder' included in Title perhaps the biggest unecessary leak of
internal architechture to date."*

**So the fix is a check and not a prompt edit, and the measurement is what says so.** Taking
`ladder` out of the Architect's ask would not have prevented pilot 16, because the word did not
come from there; and the operator's own suggestion — rotate the internal word, *"eg ranks"* —
would move our schema onto a word the genre owns outright, which is the form §138 measures
being used most. Both are recorded as refused in stage-0 §178 rather than as untried.

**This is not a style rule and it ranks nothing.** A world may name what it likes. The question
asked here is membership in one frozen set of strings, the answer is the same every time it is
asked, and no model is consulted about any of it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence

import litharness_contracts as lc

from litharness.domain import worlds as worlds_mod
from litharness.domain.extraction import SHEET_PREDICATE
from litharness.domain.house import MACHINERY_WORDS

_WORD = re.compile(r"[A-Za-z][A-Za-z']*")

#: What ends a sentence, so that a capital following one carries no information about whether
#: the word after it is being used as a name.
_SENTENCE_END = frozenset(".!?:\n")


def _machinery(word: str) -> str | None:
    """The machinery word this token is, or `None`.

    **Whole words, and one plural fold.** The input rail matches on substrings, which is the
    conservative direction for text we write: a prompt should not contain the letters at all.
    A *name* is the other direction, where a substring match invents refusals — `Outstanding`
    contains `standing` and is an ordinary word for a rank. So the token is matched whole, and
    a trailing `s` is folded so that `Ladders` is the same leak as `Ladder` without
    `MACHINERY_WORDS` having to carry every plural for the sake of this caller.

    The underscored entries (`manifests_as`, `order_key`, `graph_line` and the rest) can never
    match a whole word here. That is harmless: nothing has ever named a world after them, and
    the set stays one set.
    """
    folded = word.casefold()
    if folded in MACHINERY_WORDS:
        return folded
    stem = folded[:-1] if folded.endswith("s") else ""
    return stem if stem in MACHINERY_WORDS else None


def _canonical(matches: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({match for match in matches if match}))


#: Dropped before a declared name is compared, so that `the Ladder` and `Ladder` are one answer.
_ARTICLES = frozenset({"a", "an", "the"})


def taken_as_a_name(name: str) -> tuple[str, ...]:
    """Whether this declared name simply **is** one of our words, ignoring case and decoration.

    For a **declared display name** — a system's, a criterion's, a rung's, a printed column's.
    The question is deliberately identity and not containment, and one measurement is why: run
    as containment over the 173 world-facing names the pilot databases hold, this refused pilot
    15's column *"Seams standing in Ashfen"*, where `standing` is an ordinary participle inside a
    phrase and nothing has leaked. Identity refuses that name and still catches all four of
    pilot 16's (`Ladder`, `Rung` twice, `[LADDER]`) and pilot 15c's criterion `standing` — six
    refusals, no false ones, on every world on disk.

    That is also the honest form of the complaint. What the operator objected to is that the
    *thing is called the Ladder*, not that a label somewhere contains a word; a check that
    cannot tell those apart would grow into the style rule this is not.

    Articles, brackets, digits and punctuation come off first, so `[LADDER]` and `the Ladder`
    answer the same as `Ladder`. Case is ignored because a name is a name however it is typed:
    pilot 15c's lowercase criterion `standing` is §120's measured defect exactly.
    """
    words = [word.casefold() for word in _WORD.findall(name)]
    kept = [word for word in words if word not in _ARTICLES] or words
    if len(kept) != 1:
        return ()
    machinery = _machinery(kept[0])
    return (machinery,) if machinery else ()


def named_in(prose: str) -> tuple[str, ...]:
    """Which of our words this prose uses **as a name**: capitalised, and not opening a sentence.

    This distinction is the whole reason the check is not a style rule. *"he climbed the
    ladder"* is the English word and is left alone; *"It called itself the Ladder"* — pilot 16's
    listing, verbatim — is a proper noun, and a proper noun is what ends up on a cover and in a
    world. A capital is the only mechanical evidence free prose offers for that difference, so
    it is the only thing read here, and nothing looks at what the sentence means.

    **A sentence-initial capital is not evidence, and is deliberately missed.** *"Ladders are
    how this world counts"* opens a sentence, so its capital says nothing, and refusing it would
    refuse the ordinary word on punctuation alone. The miss is small and one-directional: it can
    let a name through, it can never invent one.

    **A title is read by this function too, and its title case is why it works.** *Reading The
    Ladder Wrong* capitalises every word, so the capital carries no information — but a leaked
    word is essentially never the title's first word, and the leading position is the only one
    the sentence-start rule gives away. Measured over the nine listings and nine titles on disk:
    one refusal, pilot 16's, on both surfaces, and no other listing or title touched.
    """
    found: list[str] = []
    for match in _WORD.finditer(prose):
        word = match.group(0)
        if not word[:1].isupper():
            continue
        machinery = _machinery(word)
        if machinery is None:
            continue
        before = prose[: match.start()].rstrip()
        if not before or before[-1] in _SENTENCE_END:
            continue
        found.append(machinery)
    return _canonical(found)


def complaint(where: str, name: str, words: Iterable[str]) -> str:
    """One sentence naming what was taken and where, in the same voice for every caller.

    Written once so that `world check`, `world accept` and the listing loop cannot drift into
    three descriptions of one refusal. It says what to do instead, because the addressee at two
    of those three call sites is an agent holding `world declare` and able to act on it.
    """
    taken = ", ".join(sorted(words))
    return (
        f"{where} {name!r} is built out of this system's own machinery vocabulary ({taken}): "
        "those are the words the tooling uses for the parts, not words this book has to borrow. "
        "Call it what the world would call it."
    )


def world_names(records: Sequence[lc.StateRecord]) -> tuple[tuple[str, str], ...]:
    """Every name this world shows a reader, as `(where, name)` pairs, in a stable order.

    **Three record shapes, and they are the three that reach a page.** `is_a` is the display
    name of anything the world declares — the system, the criterion, a rung, an ability, a
    person — and it is what pilot 16 put `Ladder` and `Rung` into. `graph_line`'s `label` names
    the line itself. `status_sheet`'s field labels are the printed columns, which is how `Rung`
    got onto the page twice in that book's first chapter without ever being written by a writer.

    Ids are deliberately not read. `ladder` was also pilot 16's *subject id*, and an id is the
    Architect's handle on its own records rather than something a reader meets — refusing one
    would be refusing a variable name. Every id that matters is carried by an `is_a` anyway,
    which is why the leak is catchable without reading them.
    """
    names: list[tuple[str, str]] = []
    for record in records:
        if record.predicate == "is_a":
            name = str(record.value or "").strip()
            if name:
                names.append((f"the name of {record.subject}", name))
        elif record.predicate == worlds_mod.GRAPH_LINE_PREDICATE:
            value = record.value
            label = str(value.get("label", "")).strip() if isinstance(value, Mapping) else ""
            if label:
                names.append((f"{record.subject}'s status line label", label))
        elif record.predicate == SHEET_PREDICATE:
            value = record.value
            fields = value.get("fields") if isinstance(value, Mapping) else None
            for entry in fields if isinstance(fields, list) else ():
                if not isinstance(entry, Mapping):
                    continue
                label = str(entry.get("label", "")).strip()
                if label:
                    names.append((f"{record.subject}'s printed column", label))
    return tuple(names)


def world_complaints(records: Sequence[lc.StateRecord]) -> tuple[str, ...]:
    """One complaint per world-facing name built out of our own machinery vocabulary.

    Membership over a frozen set, the way `worlds.validate`'s checks are membership or
    arithmetic, and for the same stated reason: there is no quality ordering over world names
    here and inventing one would be a judgment about worlds rather than about this repository's
    vocabulary. A world may name what it likes; these fourteen strings are the exception,
    because they are ours.
    """
    return tuple(
        complaint(where, name, words)
        for where, name in world_names(records)
        if (words := taken_as_a_name(name))
    )


__all__ = [
    "complaint",
    "named_in",
    "taken_as_a_name",
    "world_complaints",
    "world_names",
]
