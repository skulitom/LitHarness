"""§12 step 5: reading state back out of accepted prose.

The gap this closes is structural rather than cosmetic. `domain/integrity.py` implements one
in-process detector, `state.contradiction.v0`, and its docstring names the corruption it
exists to catch: "§12 step 5's extraction writing a record that contradicts one already
accepted — can only happen inside the loop." That extraction did not exist. Records entered
the store only through `cli import`, `EventType.STATE_CANDIDATES_EXTRACTED` had no producer,
and **nothing anywhere in `src/` constructed a `StateRecord`** — so the detector could not
fire, and Stage 2's "repairs triggered by findings" had no in-process trigger to be built on.

**Extraction mints nothing, and that is the whole design.** Not the order key, not the
subject, not the value:

- The **order key** is read back out of the book's own imported evidence (`attested_position`)
  and abstains when the book has not answered. `domain/state.py` forbids deriving one, in
  terms worth repeating: `order_key` is opaque, its author chose it, and *nothing anywhere
  defines a mapping from a manuscript scene to one*. Measured, the obvious `f"s{ordinal}"`
  reproduces the litrpg fixture 19/19 and mis-slices the mystery 2 of 15 — it works on one of
  the two books in the project and fails the one whose genre (an analepsis: scene 5 is
  attested at `s1`) guarantees it. A scheme that is right on your test book and silently
  wrong on the next is worse than abstention.
- The **subject** must already name a subject some canon record uses. A new name is a fact
  about a character the store has never heard of, which is a proposal, not a reading.
- The **value** is the prose's, verbatim, never reconciled against canon. The litrpg fixture's
  scene 4 says `HP 34/30` because §8.3 planted `f-hp-over-max` there. An extractor that
  "corrected" it would erase the defect on the way in — the detector's own input, sanitised
  by its producer.

So the chain is **decision → prose → record**: a recorded policy decision accepted the prose,
and this is a mechanical restatement of that prose asserting nothing the decision did not.
That is why a record from here may carry `ACCEPTED_CANON` without violating §11's rule that
no proposal becomes canon merely because a model returned it — no model returned it. A model
leg would be a different question and is deliberately not built (see PLAN.md §17 Stage 1).

**Reach, stated plainly so a green Stage 1 is not read as more than it is.** This reads system
voice — the `[STATUS]` line LitRPG puts on the page — and nothing else. The mystery fixture
contains no such line and yields zero records; nothing here touches prose-semantic facts like
"Brandt knows about the letter", which need a model. What it does change is that the detector
goes from having no producer at all to one that runs on every accepted scene and demonstrably
fires.

**The generator is now asked for that line, and the gain is the gate rather than the
extraction.** `render_prompt` carries the book's own current status line
(`system_voice_example`) for any book whose canon already holds a snapshot. Before that, a
generated litrpg scene carried no game state at all, so `state.contradiction.v0` had nothing to
read and **every generated scene passed the integrity gate vacuously** — a scene claiming Rook
had forty gold where canon says forty-five was accepted, because it never said so on the page.
It says so now, and is refused. That is §8.3's fourth promotion clause and §17 Stage 1's
"validation on model-written rather than templated chapters", closed by making the prose speak
rather than by adding a detector.

**The instruction was measured against real models, and the first version failed one of
three.** Shown `STATUS_TEMPLATE` with its `{subject}` slot intact, one local model wrote the
placeholder out verbatim — a line that matched `STATUS_PATTERN`, named a subject canon has
never heard of, and extracted nothing. Showing the book's own line instead took it to three of
three. `tests/test_planner.py` keeps that measurement runnable; it is the only test in this
project that can check the instruction at all, because every other one runs on a provider that
ignores the prompt.

**What it is still not.** A redraft that *agrees* with canon extracts nothing new, because
`_already_canon` suppresses a fact the book has already accepted at that position — correct,
and it means the fixtures stay silent. And a book with no imported snapshot extracts nothing at
all, because `attested_position` has no evidence to read a position out of: Book Zero writes
system voice that nothing can yet place. Asking for the line is a precondition for that, not a
solution to it.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from hashlib import sha256

import litharness_contracts as lc

from litharness.domain import state as state_mod
from litharness.domain import worlds as worlds_mod
from litharness.domain.events import payload_digest
from litharness.domain.text import content_hash

#: The suffix that makes one field another's ceiling. Derived from the pair rather than
#: hardcoding `hp`/`mp`, so a sheet that grows a `stamina_max` is covered without an edit.
MAX_SUFFIX = "_max"


#: The predicate every record from this module carries. One predicate, because the detector
#: groups on it and a vocabulary invented here would be a second answer to a question §8.4
#: gives ContinuityEvaluation.
STATUS_PREDICATE = "status_snapshot"

#: The predicate a book declares its own sheet under. Canon, and read rather than configured:
#: a flag would be a second source of truth for something the records already answer.
SHEET_PREDICATE = "status_sheet"

#: Predicates that configure how a book is written down rather than stating anything about its
#: world. Canon, because the book declared them — and they must never reach a context packet.
#:
#: **Measured on the first reseeded rehearsal**: the sheet declaration arrived in the scene's
#: Established facts block as `silas status_sheet fields=[{'label': 'Loop', 'name': 'loop'}…]`,
#: which hands a writer a configuration blob and calls it a fact about the world. It is the
#: small instance of the general defect `plan/state-model-abilities.md` §2 names — a record
#: shaped for a machine, rendered into a prompt — and the general fix is a projection layer.
#: This is the narrow one: what configures the telling is not part of the told.
CONFIGURATION_PREDICATES = frozenset({SHEET_PREDICATE, worlds_mod.GRAPH_LINE_PREDICATE})

#: Named so a later change to the graph line's grammar is a visible version bump. Deliberately
#: neither `REGISTRY_VERSION` nor `worlds.REGISTRY_VERSION`: three producers now write records —
#: an author's snapshot, this module reading a status line, this module reading a graph line, and
#: an Architect proposing a world — and an audit that could not tell them apart would be worth
#: less than one that says nothing. `has_story_vocabulary` is the function that already depends
#: on exactly this distinction.
GRAPH_REGISTRY_VERSION = "litharness.graphline.v0"


class MalformedSheet(Exception):
    """A book declared a sheet this module cannot build a line from.

    Raised rather than defaulted, and the difference is the whole point. A book that declared
    `Loop | Day` and silently got `Level | HP | MP | Gold` would ask every scene for a form
    its own canon does not use, extract nothing, and look exactly like a book that established
    no state — the silence this module's docstring says no gate catches. `cmd_new` calls
    `sheet_for` on the seed, so a malformed declaration is refused before the book exists.
    """


@dataclass(frozen=True, slots=True)
class SheetField:
    """One column of a status line: a canon value key and how the line writes it.

    `paired` is the `current/maximum` shape — `HP 27/34` — which also gives
    `impossible_fields` the `_max` key it derives ceilings from.
    """

    name: str
    label: str
    paired: bool = False


@dataclass(frozen=True, slots=True)
class Sheet:
    """The status line a book actually uses, as fields rather than as a hardcoded string.

    **The vocabulary was welded in, and that made the model a genre.** `Level | HP | MP | Gold`
    was a literal in three constants, so a world whose numbers are different ones — or whose
    progression is not numeric at all — could not speak system voice without a code change, and
    a book with no combat had to borrow a combat sheet to be read back at all. Declaring the
    sheet in canon moves that choice to where the rest of the book's facts live.

    `DEFAULT_SHEET` reproduces the old constants exactly, so a book that declares nothing —
    which is both golden fixtures and every store written before this — is untouched by
    construction rather than by a compatibility branch.

    The template and the pattern are derived from **one** field list, which is what keeps the
    instruction and the parser the same statement. They used to be two literals that a human
    had to keep in agreement; `test_a_declared_sheet_round_trips` now asserts the agreement for
    any sheet rather than for the one that happened to be written down.
    """

    fields: tuple[SheetField, ...]

    def __post_init__(self) -> None:
        if not self.fields:
            raise MalformedSheet("a sheet needs at least one field")
        seen = list(self.value_keys)
        if len(set(seen)) != len(seen):
            raise MalformedSheet(f"a sheet may not repeat a value key: {sorted(seen)}")

    @property
    def value_keys(self) -> tuple[str, ...]:
        """The canon value keys this line writes, in the order it writes them."""
        keys: list[str] = []
        for field_ in self.fields:
            keys.append(field_.name)
            if field_.paired:
                keys.append(f"{field_.name}{MAX_SUFFIX}")
        return tuple(keys)

    @property
    def template(self) -> str:
        """The line as a shape, for asking a generator to write one this module can read."""
        parts = [
            f"{field_.label} {{{field_.name}}}/{{{field_.name}{MAX_SUFFIX}}}"
            if field_.paired
            else f"{field_.label} {{{field_.name}}}"
            for field_ in self.fields
        ]
        return "[STATUS] {subject} — " + " | ".join(parts)

    @property
    def pattern(self) -> re.Pattern[str]:
        """The parser for this line. Compiled once per distinct sheet."""
        return _compile_pattern(self.fields)


@cache
def _compile_pattern(fields: tuple[SheetField, ...]) -> re.Pattern[str]:
    """Anchored at the start of a line so it cannot match prose that merely mentions a
    bracket. The name runs to an em dash, which is how both the fixture and the genre write
    it; `[^\\S\\n]` rather than `\\s` keeps the match on one line."""
    columns = [
        rf"{re.escape(field_.label)}[^\S\n]+(?P<{field_.name}>\d+)"
        + (rf"/(?P<{field_.name}{MAX_SUFFIX}>\d+)" if field_.paired else "")
        for field_ in fields
    ]
    return re.compile(
        r"^\[STATUS\][^\S\n]*(?P<subject>[^\n|]+?)[^\S\n]*—[^\S\n]*"
        + r"[^\S\n]*\|[^\S\n]*".join(columns),
        re.MULTILINE,
    )


#: The sheet a book gets when it declares none: the LitRPG line this module shipped with.
#: Kept as the default because changing what an undeclared book means would rewrite the
#: reading of every store already on disk.
DEFAULT_SHEET = Sheet(
    (
        SheetField("level", "Level"),
        SheetField("hp", "HP", paired=True),
        SheetField("mp", "MP", paired=True),
        SheetField("gold", "Gold"),
    )
)

#: Back-compatible names for the default sheet's three parts. Every caller that predates
#: per-book sheets keeps working, and the round-trip test still pins them.
STATUS_PATTERN = DEFAULT_SHEET.pattern
STATUS_TEMPLATE = DEFAULT_SHEET.template
STATUS_FIELDS = DEFAULT_SHEET.value_keys


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
            raise MalformedGraphLine(
                f"a graph line may not repeat a phrase: {sorted(phrases)}"
            )
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
def _compile_graph_pattern(
    label: str, edges: tuple[GraphEdge, ...]
) -> re.Pattern[str]:
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
        if record.predicate == worlds_mod.GRAPH_LINE_PREDICATE
        and state_mod.is_canon(record)
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
        if record.predicate == worlds_mod.GRAPH_LINE_PREDICATE
        and state_mod.is_canon(record)
    ]
    if len(declared) != 1:
        return None
    try:
        return parse_graph_line(declared[0].value)
    except MalformedGraphLine:
        return None


def parse_sheet(value: object) -> Sheet:
    """A `status_sheet` record's value as a `Sheet`, or `MalformedSheet`.

    Closed in every direction that matters. A field needs a `name` the extractor can use as a
    regex group and a `label` the line can print; anything else is a declaration this module
    would have to guess at, and guessing is what produces a line the parser cannot read.
    """
    if not isinstance(value, Mapping):
        raise MalformedSheet(f"a sheet declaration must be an object, got {type(value).__name__}")
    raw = value.get("fields")
    if not isinstance(raw, list) or not raw:
        raise MalformedSheet("a sheet declaration needs a non-empty 'fields' list")
    fields: list[SheetField] = []
    for entry in raw:
        if not isinstance(entry, Mapping):
            raise MalformedSheet(f"each field must be an object, got {entry!r}")
        name = entry.get("name")
        label = entry.get("label")
        if not isinstance(name, str) or not name.isidentifier():
            raise MalformedSheet(f"field name {name!r} is not usable as a value key")
        if not isinstance(label, str) or not label.strip():
            raise MalformedSheet(f"field {name!r} needs a label the line can print")
        fields.append(SheetField(name, label.strip(), bool(entry.get("paired", False))))
    return Sheet(tuple(fields))


def sheet_for(records: Sequence[lc.StateRecord]) -> Sheet:
    """The sheet this book declared, or the default.

    **Abstains when the book says more than one thing**, exactly as `attested_position` does:
    two declarations are a disagreement about the book's own vocabulary, and picking either
    would be this module choosing which of the author's answers is real.
    """
    declared = [
        record
        for record in records
        if record.predicate == SHEET_PREDICATE and state_mod.is_canon(record)
    ]
    if len(declared) != 1:
        return DEFAULT_SHEET
    return parse_sheet(declared[0].value)


def impossible_fields(value: Mapping[str, object]) -> tuple[str, ...]:
    """Fields standing above their own ceiling in one snapshot — `mp 6` against `mp_max 4`.

    **A snapshot can be impossible without contradicting anything, which is why this is
    separate from `integrity.detect_contradictions`.** That detector groups on `(subject,
    predicate, order_key)` and fires when two canon records disagree *at one position*; a
    single internally incoherent record is invisible to it by construction. §56.5 measured the
    consequence: `MP 6/4` reached accepted canon twice across twelve ACCEPT decisions and zero
    findings, and `system_voice_example` then rendered it into every later prompt as "the state
    as it stands", with an instruction to carry it forward.

    **This is a reading, not a detector, and deliberately so.** `stats.ceiling.v0` is built and
    green in ContinuityEvaluation as one of the six-rule pack, and PLAN.md §8.4 gives that
    sibling the game-system vocabulary. A second in-process implementation of the same rule
    would be two sources of truth for one claim. What this supports is the check the pack
    cannot make — a milestone is a *proposal*, refused before it is written, and never reaches
    the evaluator at all.

    Comparison is `>` on the pair, so a field with no ceiling, a non-numeric value, and a bool
    are all silently not-impossible: this answers only the question it can answer.
    """
    impossible: list[str] = []
    for key, ceiling in value.items():
        if not key.endswith(MAX_SUFFIX):
            continue
        current = value.get(key[: -len(MAX_SUFFIX)])
        if isinstance(current, bool) or isinstance(ceiling, bool):
            continue
        if (
            isinstance(current, int | float)
            and isinstance(ceiling, int | float)
            and current > ceiling
        ):
            impossible.append(key[: -len(MAX_SUFFIX)])
    return tuple(sorted(impossible))


def render_status_line(
    subject: str, value: Mapping[str, object], *, sheet: Sheet = DEFAULT_SHEET
) -> str:
    """A status line for a subject and a snapshot value — the inverse of `sheet.pattern`.

    The subject is written as the book's records hold it. `normalise_subject` is not
    invertible (it casefolds and collapses whitespace), and inventing a display name by
    title-casing would be this module minting the one thing it is most careful not to: a fact
    about a character that no canon record states.

    `sheet` defaults to the LitRPG line rather than to the caller's book, so a caller that has
    records in hand must pass `sheet_for(records)` — the default is for callers that have none.
    """
    return sheet.template.format(
        subject=subject, **{field: value.get(field, "?") for field in sheet.value_keys}
    )


def progression_target(
    records: Sequence[lc.StateRecord], *, at: str | None = None
) -> str | None:
    """The next milestone a progression schedule asks this book to reach, or None.

    **The defect this addresses is that the ledger never moves.** Measured over a 24-scene
    Book Zero and a six-scene one before it: every scene reported the seed values unchanged,
    so the book had no economy, no progression and no stakes. Nothing objected, because each
    scene agreed with canon at its own position and the contradiction detector asks only
    that. §17 Stage 3 names a "progression schedule" as Narrative Planner v0 work; this reads
    one.

    **A schedule is a state record that is not canon**, which is the shape the system already
    has and the reason this needs no new storage, no contract field and no prose to parse. A
    milestone is a claim about what the state *should become* at a future story position —
    `PROPOSED` says exactly that, `is_canon` excludes it, and so the context packet does not
    hand it to a scene as an established fact and `detect_contradictions` does not weigh it
    against what the prose says. It informs generation and contaminates nothing.

    Returns the **nearest milestone at or after** `at`, so a book aims at its next target
    rather than its last one. Never interpolates between milestones: a level curve's shape is
    a modelling choice the author made when they wrote the schedule, and inventing points on
    it here would be this module deriving the one kind of thing it is most careful not to.
    """
    milestones = [
        record
        for record in records
        if record.predicate == STATUS_PREDICATE
        and not state_mod.is_canon(record)
        and isinstance(record.value, Mapping)
        and state_mod.order_key_of(record) is not None
    ]
    ahead = [
        record
        for record in milestones
        if at is None or (state_mod.order_key_of(record) or "") >= at
    ]
    if not ahead:
        return None
    target = min(ahead, key=lambda record: state_mod.order_key_of(record) or "")
    return render_status_line(target.subject, target.value)


def standing_target(
    records: Sequence[lc.StateRecord], *, at: str | None = None
) -> str | None:
    """The next rung a standing schedule asks this book to reach, as one line of facts. Or None.

    **`progression_target`'s twin, and every one of that function's arguments applies here.**
    A scheduled standing is a `PROPOSED` `stands_at` edge, so `is_canon` excludes it, the
    context packet never hands it to a scene as established fact, and `detect_contradictions`
    never weighs it against what the prose says. It informs generation and contaminates nothing.

    Returns the **nearest scheduled standing at or after** `at`, so a book aims at its next rung
    rather than its last one, and never interpolates: which scene a rise lands at is the
    schedule's choice and inventing one between two milestones would be this module deriving the
    thing it is most careful not to.

    The line carries the *live* rung as well as the scheduled one, and both with their number,
    because the number is the whole point of the ladder and a target with no origin is a
    destination with no distance. Where the live standing is unknown — a book being drafted from
    a schedule whose opening standing is not canon — the line says only where the plan has them.

    **Facts and positions, no verb about the rise.** Whether the rung is earned, felt, or
    celebrated is not said here and is not said anywhere in this package
    (`plan/handoff-numbers-go-up.md` boundary 1).
    """
    scheduled = [
        record
        for record in records
        if record.predicate == worlds_mod.STANDS_AT_PREDICATE
        and record.object_ref
        and not state_mod.is_canon(record)
        and state_mod.order_key_of(record) is not None
    ]
    ahead = [
        record
        for record in scheduled
        if at is None or (state_mod.order_key_of(record) or "") >= at
    ]
    if not ahead:
        return None
    target = min(ahead, key=lambda record: state_mod.order_key_of(record) or "")
    criterion = str(target.value or "").strip() or worlds_mod.criterion_of_rung(
        records, target.object_ref or ""
    )
    if not criterion:
        return None
    chain = worlds_mod.ladder_of(records, criterion)
    if not chain or target.object_ref not in chain:
        return None
    total = len(chain)
    aimed = chain.index(target.object_ref or "") + 1
    forms = {
        record.subject: str(record.value or "").strip()
        for record in records
        if record.predicate == worlds_mod.MANIFESTS_PREDICATE
    }
    here = worlds_mod.standing_of(records, target.subject, at=at).get(criterion)
    ahead_of = f"{target.object_ref} ({aimed} of {total})"
    aimed_form = forms.get(target.object_ref or "")
    if here is None or here not in chain:
        plan = f"the book's plan has {target.subject} at {ahead_of}"
        return f"{plan}: {aimed_form}" if aimed_form else plan
    now = chain.index(here) + 1
    line = (
        f"{target.subject} stands at {here} ({now} of {total})"
        f"{': ' + forms[here] if forms.get(here) else ''}; "
        f"the book's plan has them at {ahead_of}"
    )
    return f"{line}: {aimed_form}" if aimed_form else line


def standing_example(
    records: Sequence[lc.StateRecord], *, at: str | None = None
) -> str | None:
    """One graph line, filled with this book's own words and its live rung, or `None`.

    **`system_voice_example` for the second extractor family, and it exists for that
    function's measured reason.** Shown a template with a `{subject}` slot intact, a model
    wrote the placeholder out verbatim: the line matched the pattern, named a subject canon has
    never heard of, and extraction yielded nothing — a scene that looks right, parses right, and
    establishes nothing. So what a generator is shown is a *filled* line, never a form with
    braces in it, and the fill comes from records rather than from anything this module invents.

    `None` for a book that declares no graph line, whose declaration carries no phrase meaning
    "stands at", or whose protagonist stands nowhere countable. Each is a book the chain
    *declare → ask → print → read* never starts on, which is a legitimate state and the control
    every fixture in this project sits in.
    """
    line = graph_line_for(records)
    if line is None:
        return None
    phrase = next(
        (
            edge.phrase
            for edge in line.edges
            if edge.predicate == worlds_mod.STANDS_AT_PREDICATE
        ),
        None,
    )
    if phrase is None:
        return None
    subjects = worlds_mod.entities_with_role(_canon_of(records), "protagonist")
    if not subjects:
        return None
    standing = worlds_mod.standing_of(records, subjects[0], at=at)
    if len(standing) != 1:
        return None
    [(_, rung)] = standing.items()
    return line.render(subjects[0], phrase, rung)


def _canon_of(records: Sequence[lc.StateRecord]) -> list[lc.StateRecord]:
    return [record for record in records if state_mod.is_canon(record)]


def speaks_system_voice(records: Sequence[lc.StateRecord]) -> bool:
    """Whether this book states its game state on the page.

    Read out of the book's own canon rather than declared by a genre flag, for the reason
    `attested_position` reads the order key rather than deriving it: a flag is a second
    source of truth for something the records already answer, and the two would eventually
    disagree. A book whose canon holds a status snapshot has spoken system voice at least
    once; one whose canon holds none has not, and asking its generator for a status line
    would put a LitRPG stat block in a locked-room mystery.
    """
    return any(
        record.predicate == STATUS_PREDICATE and state_mod.is_canon(record)
        for record in records
    )

#: Named so a later registry change is a visible version bump rather than a silent reread.
#: Deliberately not the fixtures' `fixture.v1`: these records are this extractor's reading,
#: and borrowing the fixture's version would make them indistinguishable from authored ones.
REGISTRY_VERSION = "litharness.systemvoice.v0"

#: Declared on an **authored** record whose `story_position` is written in the planner's own
#: key namespace — the `s{n}` keys `beats_for` mints for this book — rather than in one
#: somebody else chose. It is a claim about where the key came from and nothing else: the
#: record is still given rather than read, and `cmd_state` still prints it as `given`.
#:
#: The namespace is not new and this is not the first thing to write in it. `Promise` already
#: stores `opened_at_key` "in `beats_for`'s padding", and the only reason that does not read
#: as a foreign vocabulary is that promises live in their own table — `PromiseRepository`
#: says so, naming `has_story_vocabulary`'s registry check as one of the three things folding
#: them into `StateRecord` would break. A seeded record dated at a beat is the same key with
#: nowhere to say so.
PLANNED_POSITION_VERSION = "litharness.planned-position.v0"

#: Registry versions whose order keys **this system's own planning** placed, and which are
#: therefore not evidence that the book has a story vocabulary of its own. See
#: `has_story_vocabulary`.
#:
#: **Two more members landed with the Architect, and both are the same case a third and fourth
#: time.** `GRAPH_REGISTRY_VERSION` is this module's own second family, positioned at the key it
#: was handed. `worlds.REGISTRY_VERSION` is an Architect's proposal, and its only dated records
#: are the reveal positions `architect.story_key` mints **in `beats_for`'s own width, from the
#: book's own scene count** — that is what stage-0 §107.9.1 defect 10 was fixed to guarantee, and
#: it is exactly what makes them not somebody else's numbering. Left out, a forged world would
#: flip `has_story_vocabulary` to True on its own seed and §12 step 5 would extract nothing from
#: any scene, which is the silence measured for the seeded-interiority case arriving by a fourth
#: door. `test_a_forged_world_does_not_look_like_an_authors_vocabulary` pins it.
OWN_POSITION_VERSIONS = frozenset(
    {
        REGISTRY_VERSION,
        PLANNED_POSITION_VERSION,
        GRAPH_REGISTRY_VERSION,
        worlds_mod.REGISTRY_VERSION,
    }
)


def normalise_subject(name: str) -> str:
    """A subject id from a prose name. NFC, casefolded, whitespace collapsed to underscores."""
    folded = unicodedata.normalize("NFC", name).strip().casefold()
    return re.sub(r"\s+", "_", folded)


def attested_position(
    records: Sequence[lc.StateRecord], logical_id: str
) -> str | None:
    """The story position this scene is attested at, or None when the book has not said.

    Reads the answer out of the imported snapshot instead of computing it: a canon record
    whose evidence cites this scene is the book's own statement about where the scene sits in
    story time. Ambiguity abstains rather than picking — the mystery's scene 2 is cited by
    records at both `s1` and `s2`, and choosing either would be inventing the very mapping
    `domain/state.py` refuses to invent.

    **None means do not extract, never "extract unplaced".** `detect_contradictions` groups on
    `order_key_of(record) or ""`, so an unplaced record shares a bucket with every other
    unplaced record — the coarsest possible collision scheme wearing the costume of caution.
    """
    keys = {
        key
        for record in records
        if state_mod.is_canon(record) and (key := state_mod.order_key_of(record))
        if any(span.source.logical_id == logical_id for span in record.evidence)
    }
    return next(iter(keys)) if len(keys) == 1 else None


def has_story_vocabulary(known: Sequence[lc.StateRecord]) -> bool:
    """Whether this book already has story positions **somebody else** chose.

    One such canon record is enough: the vocabulary is that author's, its keys mean what they
    chose, and a position stated alongside them would be a second author writing in the same
    namespace. The mystery fixture is the case — scene 2 abstains while records at `s1` and
    `s2` exist, and filling that gap would insert a record into the middle of a numbering
    somebody else owns.

    **This extractor's own records are excluded, and leaving them in was a real defect** found
    by running Book Zero rather than by reasoning about it. Scene 1 was placed, its record
    became "a canon record with an order key", and every later scene therefore saw a book with
    a vocabulary and abstained — so a six-scene book extracted exactly one fact and looked, at
    every layer, like a book whose other five scenes established nothing. `REGISTRY_VERSION`
    is what tells the two apart, and it exists for precisely this: the module docstring
    records that it is deliberately not the fixtures' `fixture.v1`, so a record this extractor
    wrote is distinguishable from an authored one.

    **The exclusion is a set rather than that one version, and the second member was found the
    same way.** A seeded record dated at a beat — the interiority `plan/interiority-model.md`
    §1 asks for, `silas wants …` at `s1` — carries an order key in `beats_for`'s own
    namespace, which is not somebody else's numbering either. Measured on the Serial Pilot
    seed: adding one such record with no declaration flips this to True, `stated_position`
    then abstains for the whole book, and §12 step 5 extracts **nothing from any scene** —
    the same silence Book Zero produced, arriving by a different door. On the same seed and
    the same `Loop | Day` status line, `extract_state` returned 0 records with the declaration
    absent and 1 with it present.

    **The default direction is unchanged and is the safe one.** A dated canon record that
    declares nothing still counts as a foreign vocabulary, so forgetting the declaration
    loses coverage and can never mint a false order — the direction `BeatTemplate.chronological`
    defaults in, and for the same reason.
    """
    return any(
        state_mod.order_key_of(record)
        for record in known
        if state_mod.is_canon(record)
        and record.predicate_registry_version not in OWN_POSITION_VERSIONS
    )


def stated_position(known: Sequence[lc.StateRecord], stated: str | None) -> str | None:
    """A position the *planner* stated, usable only for a book with no vocabulary of its own.

    **This is the narrow opening in "extraction mints nothing", and the narrowness is the
    argument.** A book with no imported snapshot has no story-time vocabulary at all, so
    nothing here can conflict with an author's choices, contradict a record, or insert into
    a numbering somebody else owns — and the alternative is what the system had: a book it
    wrote entirely itself, whose every scene is unplaceable, so §12 step 5 extracts nothing
    from it forever. That is Book Zero.

    The claim is still not this module's. It comes from a `BeatTemplate` that declares itself
    chronological, which is a statement about the sheet the planner laid out rather than an
    inference about a book — see `domain/beats.py`, where the flag defaults to False so a
    template that forgets loses coverage instead of minting a false order.
    """
    if stated is None or has_story_vocabulary(known):
        return None
    return stated


def record_id_for(
    subject: str, predicate: str, order_key: str, value: Mapping[str, object]
) -> str:
    """Content-derived, and **value-sensitive on purpose**.

    A replayed tick must converge rather than accumulate, so the id cannot carry the revision
    or the logical id. But keying on `(subject, predicate, order_key)` alone makes the
    detector permanently unreachable: `record_state_records` is `INSERT OR IGNORE`, so a
    contradicting record would collide with the one it contradicts, insert zero rows, leave
    the old value standing, and report success. Including the value means two disagreeing
    readings are two rows — which is exactly what the detector needs to see them.
    """
    material = payload_digest(
        {"s": subject, "p": predicate, "k": order_key, "v": value}
    )
    return f"rec-x{sha256(material.encode()).hexdigest()[:24]}"


def graph_record_id_for(
    subject: str, predicate: str, object_ref: str, order_key: str
) -> str:
    """Content-derived, with the position in the material.

    `record_id_for` puts the *value* in so that two disagreeing readings are two rows the
    detector can see. An edge carries no value, so the equivalent question is different: the
    same edge re-established at a later position is what promotion is made of, and an id blind
    to the position would collapse the promoted canon row onto the proposal it promotes and
    `INSERT OR IGNORE` would keep the proposal.
    """
    material = payload_digest(
        {"s": subject, "p": predicate, "o": object_ref, "k": order_key}
    )
    return f"rec-g{sha256(material.encode()).hexdigest()[:24]}"


def _edge_key(record: lc.StateRecord) -> tuple[str, str, str]:
    return (record.subject, record.predicate, record.object_ref or "")


def extract_graph_facts(
    text: str,
    *,
    known: Sequence[lc.StateRecord],
    project_id: str,
    book_id: str,
    branch_id: str,
    logical_id: str,
    version_id: str,
    order_key: str,
) -> tuple[lc.StateRecord, ...]:
    """Graph edges read out of one scene's accepted prose, as **proposals**.

    The second extractor family (`plan/state-model-abilities.md` §5 item 9), and the one place
    this module is allowed to name something canon has never heard of.

    **Identity minting and factual promotion are separate decisions** (§6 item 1, and
    `research/progression-generalization.md` §14.3's three-way admission split). The page may
    *name* a new subject — that is what makes a graph that grows possible at all — and the claim
    it names arrives `PROPOSED`, so it reaches no context packet, takes no part in
    `detect_contradictions`, and launders nothing. `promotions` is the other half.

    Every record carries `GRAPH_REGISTRY_VERSION`, so a fact this family read is distinguishable
    from a status line's, from an author's snapshot, and from an Architect's proposal.

    **One edge is canon at the position, and the exception is the module docstring's own
    argument rather than a softening of the rule above.** A printed change of *standing* on a
    ladder this world declared is the book's own statement about a fact the world already
    holds — the same class as a `[STATUS]` line, whose records are `ACCEPTED_CANON` because *no
    model returned them*: a recorded policy decision accepted the prose, and this is a mechanical
    restatement of it. Nothing is minted. The subject must be one canon already uses, the rung
    must be a declared rank of a declared chain, and the criterion is derived from which chain
    holds the rung — so the three things `promotions` exists to guard against (a new name, a new
    claim, a fact the book never came back to) are all absent by construction.

    A rung the *page* minted is the general case and stays it: `[RANK] Kell now holds platinum`
    with no `platinum` on any chain arrives `PROPOSED` and is promoted only by later causal
    reuse, exactly as every other edge is.
    """
    line = graph_line_for(known)
    if line is None:
        return ()
    predicates = {edge.phrase: edge.predicate for edge in line.edges}
    # **A scheduled standing does not suppress the reading of the printed one.** `seen` exists
    # because repetition adds nothing, and it counts proposals as well as canon — but the
    # outline's own rung schedule is a `PROPOSED` `stands_at` edge at a future position, and
    # counting it here would mean the one scene that actually printed the rise read nothing,
    # because the plan for it was already on record. The plan and the page are different
    # claims: the schedule carries no registry version from this family, and the page's reading
    # is what makes the rise true.
    seen = {
        _edge_key(record)
        for record in known
        if not (
            record.predicate == worlds_mod.STANDS_AT_PREDICATE
            and record.authority is lc.StateAuthority.PROPOSED
            and record.predicate_registry_version != GRAPH_REGISTRY_VERSION
        )
    }
    canon_subjects = {record.subject for record in known if state_mod.is_canon(record)}
    declared_rungs = {
        rung
        for criterion in worlds_mod.criteria(_canon_of(known))
        for rung in worlds_mod.ladder_of(_canon_of(known), criterion)
    }

    extracted: list[lc.StateRecord] = []
    for match in line.pattern.finditer(text):
        predicate = predicates.get(match.group("phrase"))
        if predicate is None:  # pragma: no cover - the alternation cannot produce one
            continue
        subject = normalise_subject(match.group("subject"))
        target = normalise_subject(match.group("object"))
        if not subject or not target:
            continue
        key = (subject, predicate, target)
        # Repetition adds nothing. An edge already on record — proposal or canon — is the same
        # claim, and `plan/state-model-abilities.md` §6 item 1 rejects repetition as promotion
        # evidence explicitly, so writing a second proposal for it would be storing the evidence
        # the rule says is not evidence.
        if key in seen or key in {_edge_key(row) for row in extracted}:
            continue
        start, end = match.span()
        # The one canon-writable shape: a declared subject reaching a declared rung of a
        # declared chain. See the docstring — nothing is minted and no model returned it.
        stands = (
            predicate == worlds_mod.STANDS_AT_PREDICATE
            and subject in canon_subjects
            and target in declared_rungs
            and worlds_mod.criterion_of_rung(_canon_of(known), target) is not None
        )
        extracted.append(
            lc.StateRecord(
                record_id=graph_record_id_for(subject, predicate, target, order_key),
                kind=lc.StateRecordKind.RELATIONSHIP,
                subject=subject,
                predicate=predicate,
                object_ref=target,
                # The criterion rides on the edge for the forge's own reason: two ladders in
                # one world must not splice. Derived rather than printed — the page prints a
                # rung and a reader knows which ladder it is on.
                value=(
                    worlds_mod.criterion_of_rung(_canon_of(known), target)
                    if stands
                    else None
                ),
                story_position=lc.StoryPosition(order_key=order_key),
                authority=(
                    lc.StateAuthority.ACCEPTED_CANON
                    if stands
                    else lc.StateAuthority.PROPOSED
                ),
                pov_visibility=[],
                evidence=[
                    lc.EvidenceSpan(
                        source=lc.ResourceRef(
                            project_id=project_id,
                            book_id=book_id,
                            branch_id=branch_id,
                            logical_id=logical_id,
                            kind=lc.ResourceKind.MANUSCRIPT_SCENE,
                            version_id=version_id,
                        ),
                        start=start,
                        end=end,
                        content_sha256=content_hash(text[start:end]),
                    )
                ],
                predicate_registry_version=GRAPH_REGISTRY_VERSION,
                note=(
                    "read off the page: a declared subject at a declared rung of a declared "
                    "chain, which is the book stating a fact its world already holds"
                    if stands
                    else "named by the page; a proposal until the book uses it again"
                ),
            )
        )
    return tuple(extracted)


def promotions(
    known: Sequence[lc.StateRecord],
    extracted: Sequence[lc.StateRecord],
    *,
    order_key: str,
) -> tuple[lc.StateRecord, ...]:
    """Proposed edges this scene earned, as new canon records at this position.

    **The promotion rule, and it is deliberately the narrow one.**
    `plan/state-model-abilities.md` §6 item 1 rejects repetition as evidence and names *later
    causal reuse* as the strong signal: "an ability the book uses again to do something has
    earned more than one merely named twice." The checkable form of that, for a reader made of
    regexes, is: an earlier proposal `(s, p, o)` is promoted when **this** scene names `s` or
    `o` under a **different** predicate. The book came back to the thing and did something else
    with it.

    An identical repetition promotes nothing, by construction — `extract_graph_facts` never
    emits one, and the different-predicate test would refuse it anyway.

    **Promotion mints a new record rather than editing one**, because `record_state_records` is
    `INSERT OR IGNORE` and there is no update path — and because the new row is the truer
    statement: the proposal was made at s3 and the world accepted it at s7, and both of those
    happened. The proposal stays on record as the proposal it was.

    Honest about its reach: this cannot tell causal reuse from coincidental co-occurrence, and
    it does not claim to. What it buys is that a fact the page invented and then never touched
    again stays out of canon, which is the failure the rule exists to prevent.
    """
    if not extracted:
        return ()
    touched: dict[str, set[str]] = {}
    for record in extracted:
        for endpoint in (record.subject, record.object_ref or ""):
            if endpoint:
                touched.setdefault(endpoint, set()).add(record.predicate)

    promoted: list[lc.StateRecord] = []
    already = {_edge_key(record) for record in known if state_mod.is_canon(record)}
    for record in known:
        if record.authority is not lc.StateAuthority.PROPOSED:
            continue
        if record.predicate_registry_version != GRAPH_REGISTRY_VERSION:
            continue
        if not record.object_ref:
            continue
        earlier = state_mod.order_key_of(record)
        if earlier is None or earlier >= order_key:
            continue
        key = _edge_key(record)
        if key in already:
            continue
        reused = any(
            record.predicate not in touched.get(endpoint, set())
            and endpoint in touched
            for endpoint in (record.subject, record.object_ref)
        )
        if not reused:
            continue
        already.add(key)
        promoted.append(
            lc.StateRecord(
                record_id=graph_record_id_for(
                    record.subject, record.predicate, record.object_ref, order_key
                ),
                kind=lc.StateRecordKind.RELATIONSHIP,
                subject=record.subject,
                predicate=record.predicate,
                object_ref=record.object_ref,
                story_position=lc.StoryPosition(order_key=order_key),
                authority=lc.StateAuthority.ACCEPTED_CANON,
                pov_visibility=list(record.pov_visibility),
                evidence=list(record.evidence),
                predicate_registry_version=GRAPH_REGISTRY_VERSION,
                note=f"promoted at {order_key}: the book used it again, proposed at {earlier}",
            )
        )
    return tuple(promoted)


def extract_state(
    text: str,
    *,
    known: Sequence[lc.StateRecord],
    project_id: str,
    book_id: str,
    branch_id: str,
    logical_id: str,
    version_id: str,
    replacing_logical_id: str | None = None,
    stated_order_key: str | None = None,
) -> tuple[lc.StateRecord, ...]:
    """State records read out of one scene's accepted prose.

    Pure: no store, no provider, no clock. `text` must be the **canonicalized** node content
    (`gate_draft` produces it), never the raw provider string — spans and `content_sha256`
    have to live in the NFC+LF coordinate space the contracts package resolves them in, and
    an offset measured against the raw text points at the wrong characters.

    Returns empty rather than raising on anything it cannot read. A scene with no system
    voice is the normal case, not an error.

    `stated_order_key` is a chronological template's answer for a book that has none of its
    own — see `stated_position`. **The book always wins:** an attested position is read first
    and a stated one is only consulted when the book is silent, so this can never override or
    interleave with an author's vocabulary.
    """
    order_key = attested_position(known, logical_id) or stated_position(
        known, stated_order_key
    )
    if order_key is None:
        return ()
    #: Recorded on every record whose position the planner supplied, because "the book said
    #: where this sits" and "the sheet we planned said so" are different provenance and an
    #: audit that could not tell them apart would be worth less than one that says nothing.
    minted = attested_position(known, logical_id) is None
    subjects = {record.subject for record in known if state_mod.is_canon(record)}
    # The book's own line, not this module's. A book that declared `Loop | Day` writes and is
    # read in `Loop | Day`; one that declared nothing gets exactly what it always got.
    sheet = sheet_for(known)

    extracted: list[lc.StateRecord] = []
    for match in sheet.pattern.finditer(text):
        subject = normalise_subject(match.group("subject"))
        # A name canon has never used is a claim about someone new, which is a proposal
        # rather than a reading of what the book already established.
        if subject not in subjects:
            continue
        value = {key: int(match.group(key)) for key in sheet.value_keys}
        # Already established, identically, at this position: the record adds nothing, and
        # writing it anyway costs a permanent duplicate in every later context packet.
        if _already_canon(
            known,
            subject,
            order_key,
            value,
            replacing_logical_id=replacing_logical_id,
        ):
            continue
        start, end = match.span()
        extracted.append(
            lc.StateRecord(
                record_id=record_id_for(subject, STATUS_PREDICATE, order_key, value),
                kind=lc.StateRecordKind.ASSERTION,
                subject=subject,
                predicate=STATUS_PREDICATE,
                value=value,
                story_position=lc.StoryPosition(order_key=order_key),
                authority=lc.StateAuthority.ACCEPTED_CANON,
                pov_visibility=[],
                evidence=[
                    lc.EvidenceSpan(
                        source=lc.ResourceRef(
                            project_id=project_id,
                            book_id=book_id,
                            branch_id=branch_id,
                            logical_id=logical_id,
                            kind=lc.ResourceKind.MANUSCRIPT_SCENE,
                            version_id=version_id,
                        ),
                        start=start,
                        end=end,
                        content_sha256=content_hash(text[start:end]),
                    )
                ],
                # No confidence. A regex match has no probability, and a fabricated 1.0 would
                # read downstream as a critic's score rather than as a parse.
                predicate_registry_version=REGISTRY_VERSION,
                note=(
                    f"story position {order_key} stated by the plan, not attested by the book"
                    if minted
                    else None
                ),
            )
        )
    # **The second family runs here rather than at both call sites.** `extract_state` is called
    # from the draft handler and the repair path, and a graph reader wired into one of them
    # would be a capability that works depending on which arm produced the scene. A book that
    # declares no graph line gets an empty tuple from both calls below, which is every book
    # written before this existed.
    graph = extract_graph_facts(
        text,
        known=known,
        project_id=project_id,
        book_id=book_id,
        branch_id=branch_id,
        logical_id=logical_id,
        version_id=version_id,
        order_key=order_key,
    )
    return (*extracted, *graph, *promotions(known, graph, order_key=order_key))


def _already_canon(
    known: Sequence[lc.StateRecord],
    subject: str,
    order_key: str,
    value: Mapping[str, object],
    *,
    replacing_logical_id: str | None = None,
) -> bool:
    return any(
        record.subject == subject
        and record.predicate == STATUS_PREDICATE
        and state_mod.order_key_of(record) == order_key
        and record.value == value
        for record in known
        if state_mod.is_canon(record)
        and not (
            replacing_logical_id is not None
            and any(
                span.source.logical_id == replacing_logical_id
                for span in record.evidence
            )
        )
    )


__all__ = [
    "CONFIGURATION_PREDICATES",
    "DEFAULT_SHEET",
    "GRAPH_REGISTRY_VERSION",
    "LABEL_CHARS",
    "LABEL_WORDS",
    "OWN_POSITION_VERSIONS",
    "PHRASE_WORDS",
    "PLANNED_POSITION_VERSION",
    "REGISTRY_VERSION",
    "SHEET_PREDICATE",
    "STATUS_PATTERN",
    "STATUS_PREDICATE",
    "GraphEdge",
    "GraphLine",
    "MalformedGraphLine",
    "MalformedSheet",
    "Sheet",
    "SheetField",
    "attested_position",
    "extract_graph_facts",
    "extract_state",
    "graph_line_fault",
    "graph_line_for",
    "graph_record_id_for",
    "normalise_subject",
    "parse_graph_line",
    "parse_sheet",
    "promotions",
    "record_id_for",
    "sheet_for",
    "standing_example",
    "standing_target",
]


def system_voice_example(
    records: Sequence[lc.StateRecord], *, at: str | None = None
) -> str | None:
    """The book's own current status line, to show a generator what to write — or None.

    **A filled example rather than `STATUS_TEMPLATE`, and that is a measurement rather than a
    preference.** The instruction first showed the template with its `{subject}` placeholder
    intact, and three local models were asked to draft against it: two substituted the
    character's name and one wrote `[STATUS] {subject} — Level 3 | ...` verbatim. That line
    *matches* `STATUS_PATTERN` — a brace-wrapped word is a perfectly good subject — so nothing
    rejected it, and `{subject}` is not a name canon knows, so extraction yielded nothing. A
    scene that looks right, parses right, and establishes nothing: the exact silence this
    module's docstring says no gate catches.

    Built from canon, so it mints nothing: the subject is the id the records hold and the
    numbers are the ones already established.

    **`at` is the position being drafted, and it is not decoration.** A model shown a line
    will use its numbers, so the wrong line is worse than none: an imported book holds a
    snapshot for every position at once, and picking the newest would show scene six's balance
    while asking for scene one — an invented state the integrity gate then refuses, and a
    refusal caused by the instruction rather than by the prose. So the snapshot *at* the
    position wins; otherwise the latest one before it, which for a book still being written is
    the state the next scene continues from, and for a book with nothing placed yet is the
    starting sheet.
    """
    if not speaks_system_voice(records):
        return None
    snapshots = [
        record
        for record in records
        if record.predicate == STATUS_PREDICATE
        and state_mod.is_canon(record)
        and isinstance(record.value, Mapping)
    ]
    if not snapshots:
        # It speaks, but no snapshot carries a value this can render from. Abstaining is the
        # same answer as not speaking: an example is what makes the instruction unambiguous,
        # and there is nothing to build one out of.
        return None
    exact = [record for record in snapshots if state_mod.order_key_of(record) == at]
    earlier = [
        record
        for record in snapshots
        if at is None or (state_mod.order_key_of(record) or "") < at
    ]
    chosen = exact or earlier or snapshots
    latest = max(chosen, key=lambda record: state_mod.order_key_of(record) or "")
    return render_status_line(latest.subject, latest.value, sheet=sheet_for(records))
