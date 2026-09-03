"""The graph line: the bracketed line a world prints when its graph changes, in its own words.

Split out of `domain/extraction.py` on 2026-09-03 (stage-0 §215) with every definition
byte-identical, and re-exported from there. This is the declaration and its grammar
(`GraphLine`, `parse_graph_line`, `graph_line_for`); the reader that turns a printed line into
records, `extract_graph_facts`, stays in `extraction` beside the status line's, because
minting a record is that module's one subject. A book that declares no graph line has none,
and nothing here invents one for it.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache

import litharness_contracts as lc

from litharness.domain import state as state_mod
from litharness.domain import worlds as worlds_mod
from litharness.domain.sheet import MalformedSheet

#: Named so a later change to the graph line's grammar is a visible version bump. Deliberately
#: neither `REGISTRY_VERSION` nor `worlds.REGISTRY_VERSION`: three producers now write records —
#: an author's snapshot, `extraction` reading a status line, `extraction` reading a graph line, and
#: an Architect proposing a world — and an audit that could not tell them apart would be worth
#: less than one that says nothing. `has_story_vocabulary` is the function that already depends
#: on exactly this distinction.
GRAPH_REGISTRY_VERSION = "litharness.graphline.v0"

#: What a bracket tag can be. Placed numbers, stated as placed — see `GraphLine.__post_init__`
#: for what bounds them and for the declaration that made them necessary.
LABEL_WORDS = 3
LABEL_CHARS = 24
#: What a printed verb phrase can be, between a name and a thing on one line.
PHRASE_WORDS = 6

class MalformedGraphLine(MalformedSheet):
    """A book declared a graph line this module cannot build a parser from.

    Subclasses `MalformedSheet` so `cmd_new`'s single refusal covers both declarations without a
    second `except` that somebody has to remember to add. The two are the same kind of mistake —
    a book saying how it will be written down, in a form the parser cannot read — and the failure
    they share is the one `MalformedSheet` names: a declaration that silently falls back looks
    exactly like a book that established nothing.
    """

@dataclass(frozen=True, slots=True)
class GraphEdge:
    """One printed phrase and the predicate it means."""

    phrase: str
    predicate: str

@dataclass(frozen=True, slots=True)
class GraphLine:
    """The line a book prints when the world's *graph* changes, as the book's own words.

    **Why a declaration and not a constant.** `research/progression-generalization.md` §14.3 is
    explicit that "a rigid hidden extraction response format is useful; a rigid in-story status
    line is not the general abstraction", and §13's rejection list names "a printed stat line as
    the canonical extraction surface". A second hardcoded bracket form would be the sheet's
    mistake committed twice. So the label and every phrase are declared per book, the printed
    line is written in the book's own vocabulary, and **a book that declares nothing extracts no
    graph facts at all** — which is both golden fixtures, untouched by construction.

    **Why it prints at all, given that the register forbids exposition.** It does not have to.
    A world declares this only if its manifestations say the world announces itself — which in
    the target genre is ordinary and is the one place a bracketed line is native rather than
    intrusive. A world whose systems are quiet declares no graph line and grows its canon
    through the operator instead.

    The template and the pattern derive from one edge list, which is what keeps the instruction
    and the parser the same statement — `Sheet`'s argument, applied to the second family.
    `test_a_declared_graph_line_round_trips` asserts the agreement for any declaration rather
    than for the one that happened to be written down.
    """

    label: str
    edges: tuple[GraphEdge, ...]

    def __post_init__(self) -> None:
        if not self.edges:
            raise MalformedGraphLine("a graph line needs at least one edge phrase")
        phrases = [edge.phrase for edge in self.edges]
        if len(set(phrases)) != len(phrases):
            raise MalformedGraphLine(f"a graph line may not repeat a phrase: {sorted(phrases)}")
        # **Shape, because the first forged declaration was a paragraph.** Asked for a printed
        # line form, one world returned `label` = "one dry season in the Kettle Basin" and eight
        # "phrases" that were clauses of a story — well-formed JSON, accepted by every type
        # check, and a parser that could never match anything a scene would print. That is the
        # silent failure `MalformedSheet` exists to prevent, one family over: a declaration that
        # looks like a declaration and reads nothing.
        #
        # The bounds are placed rather than measured, and they are bounded by what a printed
        # bracket tag *is* rather than tuned to that answer: a tag a reader's eye skips over,
        # and a verb phrase short enough to sit between a name and a thing on one line.
        if len(self.label) > LABEL_CHARS or len(self.label.split()) > LABEL_WORDS:
            raise MalformedGraphLine(
                f"graph-line label {self.label!r} is a sentence rather than a bracket tag "
                f"(at most {LABEL_WORDS} word(s) and {LABEL_CHARS} characters); it is printed "
                "as [LABEL] at the head of a line and a reader's eye has to skip it"
            )
        for edge in self.edges:
            if len(edge.phrase.split()) > PHRASE_WORDS:
                raise MalformedGraphLine(
                    f"edge phrase {edge.phrase!r} is a clause rather than a verb phrase (at "
                    f"most {PHRASE_WORDS} words); it has to sit between a name and a thing on "
                    "one printed line"
                )

    def render(self, subject: str, phrase: str, target: str) -> str:
        """One line, as the book would print it."""
        return f"[{self.label}] {subject} {phrase} {target}"

    @property
    def template(self) -> str:
        """The shape, for asking a generator to write one this module can read."""
        options = " / ".join(edge.phrase for edge in self.edges)
        return f"[{self.label}] " + "{who} <" + options + "> {what}"

    @property
    def pattern(self) -> re.Pattern[str]:
        return _compile_graph_pattern(self.label, self.edges)

@cache
def _compile_graph_pattern(label: str, edges: tuple[GraphEdge, ...]) -> re.Pattern[str]:
    """Anchored at the start of a line, like the status pattern and for the same reason.

    Phrases are alternated **longest first** so that a book declaring both "holds" and "no
    longer holds" cannot have the shorter one win inside the longer one. The subject is
    non-greedy and the object greedy-to-end-of-line, so a phrase occurring inside a name loses
    to the first phrase boundary — which is the direction that under-reads rather than
    mis-reads.
    """
    alternates = "|".join(
        re.escape(edge.phrase)
        for edge in sorted(edges, key=lambda edge: (-len(edge.phrase), edge.phrase))
    )
    return re.compile(
        r"^\[" + re.escape(label) + r"\][^\S\n]*(?P<subject>[^\n]+?)"
        r"[^\S\n]+(?P<phrase>" + alternates + r")[^\S\n]+(?P<object>[^\n]+?)[^\S\n]*$",
        re.MULTILINE,
    )

def parse_graph_line(value: object) -> GraphLine:
    """A `graph_line` record's value as a `GraphLine`, or `MalformedGraphLine`.

    Closed in every direction that matters, exactly as `parse_sheet` is: a phrase the line can
    print and a predicate the store can group on, and no guessing between them. A predicate that
    is not a usable identifier is refused rather than normalised, because a predicate this module
    invented would be a second vocabulary beside the world's own.
    """
    if not isinstance(value, Mapping):
        raise MalformedGraphLine(
            f"a graph-line declaration must be an object, got {type(value).__name__}"
        )
    label = value.get("label")
    if not isinstance(label, str) or not label.strip() or "]" in label:
        raise MalformedGraphLine(f"graph-line label {label!r} is not usable as a bracket tag")
    raw = value.get("edges")
    if not isinstance(raw, list) or not raw:
        raise MalformedGraphLine("a graph-line declaration needs a non-empty 'edges' list")
    edges: list[GraphEdge] = []
    for entry in raw:
        if not isinstance(entry, Mapping):
            raise MalformedGraphLine(f"each edge must be an object, got {entry!r}")
        phrase = entry.get("phrase")
        predicate = entry.get("predicate")
        if not isinstance(phrase, str) or not phrase.strip():
            raise MalformedGraphLine(f"edge phrase {phrase!r} is not printable")
        if not isinstance(predicate, str) or not predicate.isidentifier():
            raise MalformedGraphLine(
                f"edge predicate {predicate!r} is not usable as a store predicate"
            )
        edges.append(GraphEdge(phrase.strip(), predicate))
    return GraphLine(label.strip(), tuple(edges))

def graph_line_fault(records: Sequence[lc.StateRecord]) -> str | None:
    """Why this book's graph-line declaration is unusable, or `None` if it is fine or absent."""
    declared = [
        record
        for record in records
        if record.predicate == worlds_mod.GRAPH_LINE_PREDICATE and state_mod.is_canon(record)
    ]
    if len(declared) != 1:
        return None
    try:
        parse_graph_line(declared[0].value)
    except MalformedGraphLine as error:
        return str(error)
    return None

def graph_line_for(records: Sequence[lc.StateRecord]) -> GraphLine | None:
    """The graph line this book declared, or `None`.

    **`None` rather than a default, and that is the difference from `sheet_for`.** A sheet has a
    default because every book written before per-book sheets existed had one implicitly; a
    graph line has never existed, so a book that declares none is a book whose world does not
    announce itself, and inventing a form for it would put a bracketed line into a book that
    never asked for one. Abstains on more than one declaration for `sheet_for`'s reason.

    **A malformed declaration degrades to absence rather than raising, and the asymmetry with
    `sheet_for` is the argument.** A sheet that cannot be parsed is dangerous because there is a
    *default* waiting behind it, so the book would be read in a form its own canon does not use
    — `MalformedSheet`'s whole reason for existing. A graph line has no default: the fallback is
    "this book has no graph line", which is a legitimate state a great many books are in. So the
    failure here is loss of a capability rather than silent use of the wrong one, and raising it
    into the draft handler would turn a bad declaration into a stalled book. `graph_line_fault`
    is how `cmd_new` says so at creation, where the cost of the complaint is a print.
    """
    declared = [
        record
        for record in records
        if record.predicate == worlds_mod.GRAPH_LINE_PREDICATE and state_mod.is_canon(record)
    ]
    if len(declared) != 1:
        return None
    try:
        return parse_graph_line(declared[0].value)
    except MalformedGraphLine:
        return None
