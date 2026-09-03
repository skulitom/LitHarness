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
three.** Shown the line's own template with its `{subject}` slot intact, one local model wrote the
placeholder out verbatim — a line that matched the line's own pattern, named a subject canon has
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
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from hashlib import sha256

import litharness_contracts as lc

from litharness.domain import gamesystem as gamesystem_mod
from litharness.domain import house as house_mod
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
#: **§160's configuration predicates union in here rather than beside** (§161, and the ownership
#: was settled between the two tracks rather than assumed). Three consumers read this set —
#: `domain/context.py`, `application/model_context.py`, `domain/world_brief.py` — and all three
#: read it from this module, so a second set would be a second answer to "may this reach a
#: packet" and the two would eventually disagree about a record. A game system's magnitude scale
#: and its digest configure how a book is written down exactly as a sheet declaration does, so
#: they belong to the same one answer.
CONFIGURATION_PREDICATES = (
    frozenset({SHEET_PREDICATE, worlds_mod.GRAPH_LINE_PREDICATE})
    | gamesystem_mod.CONFIGURATION_PREDICATES
)

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
    #: What the column's value is (§204): a `number` (the default, and the only kind a
    #: sheet on disk has), an `ordinal` (a rung id, printing as the rung's name), a
    #: `name` (an entity id, printing as its name: a class, a title), `text` (a line as
    #: written), or a `set` (entity ids with an optional depth each: a skill list).
    kind: str = "number"

    def __post_init__(self) -> None:
        if self.kind not in FIELD_KINDS:
            raise MalformedSheet(f"field {self.name!r} has no kind {self.kind!r}")
        if self.paired and self.kind != "number":
            raise MalformedSheet(f"field {self.name!r}: only a number is paired")

    @property
    def numeric(self) -> bool:
        return self.kind == "number"


#: The kinds a column may declare. A number is what every sheet on disk has.
FIELD_KINDS: tuple[str, ...] = ("number", "ordinal", "name", "text", "set")


@dataclass(frozen=True, slots=True)
class Sheet:
    """The status line a book actually uses, as fields rather than as a hardcoded string.

    **The vocabulary was welded in, and that made the model a genre.** `Level | HP | MP | Gold`
    was a literal in three constants, so a world whose numbers are different ones — or whose
    progression is not numeric at all — could not speak system voice without a code change, and
    a book with no combat had to borrow a combat sheet to be read back at all. Declaring the
    sheet in canon moves that choice to where the rest of the book's facts live.

    The default sheet that used to stand in for an undeclared book is retired (§205): a book
    that declares nothing prints the columns its own snapshots hold, so both golden fixtures
    and every store written before this — whose snapshots imply exactly the old constants'
    columns — are untouched by
    construction rather than by a compatibility branch.

    The template and the pattern are derived from **one** field list, which is what keeps the
    instruction and the parser the same statement. They used to be two literals that a human
    had to keep in agreement; `test_a_declared_sheet_round_trips` now asserts the agreement for
    any sheet rather than for the one that happened to be written down.
    """

    fields: tuple[SheetField, ...]
    #: Whether a column standing at zero prints (§203). `True` is every sheet declared
    #: before the flag existed, so every book on disk renders exactly as it did; a
    #: drawn system declares `False`, after the market census found one window field in
    #: fifteen at zero and a row with six zeros a shape the genre's windows do not have.
    #: The first column always prints, so a line is never empty and a ladder's rung stays.
    show_unheld: bool = True
    #: Whose sheet this is (§206): a subject id, a role (`place`, `creature`, `cast`), or
    #: `None` for the book's own sheet, the one its protagonist prints. A book may declare
    #: one sheet per owner, so a place or a creature carries columns of its own beside
    #: the person's; `sheet_for(records, subject=...)` is how a line finds its columns.
    owner: str | None = None

    def __post_init__(self) -> None:
        if not self.fields:
            raise MalformedSheet("a sheet needs at least one field")
        seen = list(self.value_keys)
        if len(set(seen)) != len(seen):
            raise MalformedSheet(f"a sheet may not repeat a value key: {sorted(seen)}")

    def declaration(self) -> dict[str, object]:
        """This sheet as a `status_sheet` record's value."""
        fields: list[dict[str, object]] = []
        for field_ in self.fields:
            entry: dict[str, object] = {"name": field_.name, "label": field_.label}
            if field_.paired:
                entry["paired"] = True
            if field_.kind != "number":
                entry["kind"] = field_.kind
            fields.append(entry)
        declared: dict[str, object] = {"fields": fields}
        if not self.show_unheld:
            declared["show_unheld"] = False
        if self.owner is not None:
            declared["owner"] = self.owner
        return declared

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
        """The parser for the whole line, every column present. Compiled once per
        distinct sheet. `read` is the reader the extractor uses; this is the strict form
        the round-trip test and the renderer's docs speak of."""
        return _compile_pattern(self.fields)

    def shown(self, value: Mapping[str, object]) -> tuple[SheetField, ...]:
        """The columns the printed line carries for this snapshot (§203).

        Every column when the sheet shows unheld ones; otherwise the first column and
        every column whose value stands above zero (either half of a paired one). A
        column the snapshot does not hold at all is shown, so the `?` the renderer
        prints for it stays visible rather than being hidden as a zero.
        """
        if self.show_unheld:
            return self.fields
        kept: list[SheetField] = []
        for index, field_ in enumerate(self.fields):
            keys = [field_.name] + ([f"{field_.name}{MAX_SUFFIX}"] if field_.paired else [])
            held = any(value.get(key) is None or _held(value.get(key)) for key in keys)
            if index == 0 or held:
                kept.append(field_)
        return tuple(kept)

    def render(
        self,
        subject: str,
        value: Mapping[str, object],
        *,
        resolve: Callable[[str], str] | None = None,
    ) -> str:
        """The line for one snapshot, projected: label-value pairs in declared order.

        `resolve` turns an entity id into what the page prints for it (`display_name`
        over the book's records); without one an id prints as itself.
        """
        name = resolve or (lambda entity: entity)
        parts = []
        for field_ in self.shown(value):
            current = value.get(field_.name, "?")
            if field_.paired:
                ceiling = value.get(f"{field_.name}{MAX_SUFFIX}", "?")
                parts.append(f"{field_.label} {current}/{ceiling}")
            elif field_.numeric or current == "?":
                parts.append(f"{field_.label} {current}")
            else:
                parts.append(f"{field_.label} {_render_typed(field_, current, name)}")
        return f"[STATUS] {subject} — " + " | ".join(parts)

    def read(
        self, text: str, *, ids: Mapping[str, str] | None = None
    ) -> list[tuple[str, dict[str, object], tuple[int, int]]]:
        """Every status line in `text`, tolerant of omitted columns (§203).

        A line is the tag, a subject, an em dash and pairs separated by `|`. A pair is a
        declared label followed by its value: a number (or two, for a paired column)
        for a numeric column, and for a typed column (§204) a name the book knows,
        words, or a list. Pairs are split on the declared labels themselves, longest
        first, so a two-word label reads. Pairs whose label the sheet never declared
        are skipped, so a column the writer invented reaches no record; a name the
        book does not know is skipped the same way; a line with no readable pair is
        not a line. `ids` maps a printed name (casefolded) back to its entity id. The
        value is partial where columns were omitted, which the snapshot fold
        (`state_as_it_stands`) already expects (§161).
        """
        found: list[tuple[str, dict[str, object], tuple[int, int]]] = []
        labels = sorted(self.fields, key=lambda field_: -len(field_.label))
        for match in _LINE.finditer(text):
            value: dict[str, object] = {}
            for pair in match.group("pairs").split("|"):
                pair = pair.strip()
                field_ = next(
                    (
                        candidate
                        for candidate in labels
                        if pair[: len(candidate.label)].casefold() == candidate.label.casefold()
                        and pair[len(candidate.label) : len(candidate.label) + 1].isspace()
                    ),
                    None,
                )
                if field_ is None:
                    continue
                rest = pair[len(field_.label) :].strip()
                if field_.numeric:
                    numbers = _NUMBERS.match(rest)
                    if numbers is None:
                        continue
                    if field_.paired:
                        if numbers.group("ceiling") is None:
                            continue
                        value[field_.name] = int(numbers.group("current"))
                        value[f"{field_.name}{MAX_SUFFIX}"] = int(numbers.group("ceiling"))
                    elif numbers.group("ceiling") is None:
                        value[field_.name] = int(numbers.group("current"))
                    continue
                typed = _read_typed(field_, rest, ids or {})
                if typed is not None:
                    value[field_.name] = typed
            if value:
                found.append((match.group("subject"), value, match.span()))
        return found


def _above_zero(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and value > 0


def _held(value: object) -> bool:
    """Whether a column has something in it: a number above zero, a name, words, or a
    set with a member (§204)."""
    if isinstance(value, str | list | tuple):
        return bool(value)
    return _above_zero(value)


def _render_typed(field_: SheetField, value: object, name: Callable[[str], str]) -> str:
    if field_.kind == "text":
        return str(value)
    if field_.kind == "set":
        members = value if isinstance(value, list | tuple) else [value]
        printed = []
        for member in members:
            if isinstance(member, list | tuple) and member:
                entity, depth = str(member[0]), (member[1] if len(member) > 1 else None)
                printed.append(f"{name(entity)} {depth}" if depth is not None else name(entity))
            else:
                printed.append(name(str(member)))
        return ", ".join(printed) if printed else "none"
    return name(str(value))


def _read_typed(field_: SheetField, rest: str, ids: Mapping[str, str]) -> object | None:
    """A typed column's value read off the page: an id the book knows for a name or a rung
    (else nothing), the words for text, and for a set each member resolved the same way
    with its depth kept."""
    if not rest:
        return None
    if field_.kind == "text":
        return rest
    if field_.kind == "set":
        if rest.casefold() == "none":
            return []
        members: list[object] = []
        for item in rest.split(","):
            item = item.strip()
            depth_match = _TRAILING_NUMBER.match(item)
            depth = int(depth_match.group("depth")) if depth_match else None
            printed = depth_match.group("name") if depth_match else item
            entity = ids.get(printed.strip().casefold())
            if entity is None:
                continue
            members.append([entity, depth] if depth is not None else [entity])
        return members
    return ids.get(rest.casefold())


def _status_lines(text: str) -> list[tuple[str, tuple[int, int]]]:
    """Every status line in `text`, as its printed subject and its span."""
    return [(match.group("subject"), match.span()) for match in _LINE.finditer(text)]


#: A status line's frame: the tag, the subject up to the em dash, and the rest as pairs.
_LINE = re.compile(
    r"^\[STATUS\][^\S\n]*(?P<subject>[^\n|]+?)[^\S\n]*—[^\S\n]*(?P<pairs>[^\n]+)$", re.MULTILINE
)
#: A numeric column's value: a number, then optionally a slash and its ceiling.
_NUMBERS = re.compile(r"^(?P<current>\d+)(?:/(?P<ceiling>\d+))?$")
#: A set member with a depth after its name: *Seamsight 2*.
_TRAILING_NUMBER = re.compile(r"^(?P<name>.+?)[^\S\n]+(?P<depth>\d+)$")


@cache
def _compile_pattern(fields: tuple[SheetField, ...]) -> re.Pattern[str]:
    """Anchored at the start of a line so it cannot match prose that merely mentions a
    bracket. The name runs to an em dash, which is how both the fixture and the genre write
    it; `[^\\S\\n]` rather than `\\s` keeps the match on one line."""
    columns = [
        rf"{re.escape(field_.label)}[^\S\n]+(?P<{field_.name}>\d+)"
        + (rf"/(?P<{field_.name}{MAX_SUFFIX}>\d+)" if field_.paired else "")
        if field_.numeric
        else rf"{re.escape(field_.label)}[^\S\n]+(?P<{field_.name}>[^|\n]+?)"
        for field_ in fields
    ]
    return re.compile(
        r"^\[STATUS\][^\S\n]*(?P<subject>[^\n|]+?)[^\S\n]*—[^\S\n]*"
        + r"[^\S\n]*\|[^\S\n]*".join(columns),
        re.MULTILINE,
    )


def sheet_from_line(text: str) -> Sheet | None:
    """The sheet the first status line in `text` teaches: its labels become keys (lowercased,
    spaces to underscores), a slash makes a column paired. `None` with no readable line.

    **An undeclared book's first line is its declaration** (§205). Before the default
    retired, a book with no declared sheet and no snapshot yet was read against the shipped
    vocabulary and a first line in any other words read as nothing; now the line's own words
    are the columns, which is what `implied_sheet` already does once a snapshot stands. The
    key rule is `label_for`'s inverse for the labels that rule produces.
    """
    for match in _LINE.finditer(text):
        fields: list[SheetField] = []
        seen: set[str] = set()
        for pair in match.group("pairs").split("|"):
            pair = pair.strip()
            read = _LOOSE_PAIR.match(pair)
            if read is None:
                continue
            key = re.sub(r"[^a-z0-9_]+", "_", read.group("label").strip().casefold()).strip("_")
            if not key or not key.isidentifier() or key in seen:
                continue
            seen.add(key)
            fields.append(
                SheetField(
                    key, read.group("label").strip(), paired=read.group("ceiling") is not None
                )
            )
        if fields:
            return Sheet(tuple(fields))
    return None


#: A pair as a first line writes it: words, then a number, optionally over a ceiling.
_LOOSE_PAIR = re.compile(r"^(?P<label>[^\d|]+?)[^\S\n]+(?P<current>\d+)(?:/(?P<ceiling>\d+))?$")


def declaration_from_snapshots(
    records: Sequence[lc.StateRecord],
) -> lc.StateRecord | None:
    """A `status_sheet` declaration for a book that holds snapshots and declares none: the
    first canon snapshot's columns, in the order that snapshot holds them. `None` where a
    declaration already stands or nothing implies one.

    **Why the order has to be declared** (§205). The store writes a snapshot's value with
    its keys sorted, so a book that never declared its sheet reads back with its columns
    in alphabetical order rather than the order it printed them in; the retired default
    used to fix the order for the one vocabulary it knew. An imported book's first
    snapshot, as the file holds it, is the book's own order, and this turns it into the
    declaration `sheet_for` reads first. Canon, because the snapshot it is derived from
    is; the subject is the snapshot's.
    """
    if any(
        record.predicate == SHEET_PREDICATE and state_mod.is_canon(record) for record in records
    ):
        return None
    for record in records:
        if (
            record.predicate == STATUS_PREDICATE
            and state_mod.is_canon(record)
            and isinstance(record.value, Mapping)
        ):
            sheet = sheet_from_value(record.value)
            if sheet is None:
                continue
            return worlds_mod.world_record(
                record.subject,
                SHEET_PREDICATE,
                value=sheet.declaration(),
                authority=lc.StateAuthority.ACCEPTED_CANON,
            )
    return None


def sheet_from_value(value: Mapping[str, object]) -> Sheet | None:
    """The sheet one snapshot implies on its own: its numeric keys in order, a `_max` key
    pairing its column, labels by `label_for`. `None` for a snapshot with no numeric key.

    **No default vocabulary** (§205). The line this module shipped with, `Level | HP |
    MP | Gold`, was a vocabulary welded in, and three of its four words are barely used
    in the genre; a book that declares nothing and holds nothing prints nothing, and a
    book that holds a snapshot prints the columns that snapshot holds.
    """
    keys = [
        key
        for key, held in value.items()
        if isinstance(key, str)
        and key.isidentifier()
        and isinstance(held, int)
        and not isinstance(held, bool)
    ]
    known = set(keys)
    fields = tuple(
        SheetField(key, label_for(key), paired=f"{key}{MAX_SUFFIX}" in known)
        for key in keys
        if not (key.endswith(MAX_SUFFIX) and key[: -len(MAX_SUFFIX)] in known)
    )
    return Sheet(fields) if fields else None


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
        kind = entry.get("kind", "number")
        if not isinstance(kind, str):
            raise MalformedSheet(f"field {name!r}: kind must be one of {FIELD_KINDS}")
        fields.append(SheetField(name, label.strip(), bool(entry.get("paired", False)), kind))
    show_unheld = value.get("show_unheld", True)
    if not isinstance(show_unheld, bool):
        raise MalformedSheet("show_unheld must be true or false when given")
    owner = value.get("owner")
    if owner is not None and (not isinstance(owner, str) or not owner.strip()):
        raise MalformedSheet("owner must be a subject id or a role when given")
    return Sheet(tuple(fields), show_unheld=show_unheld, owner=owner.strip() if owner else None)


def label_for(key: str) -> str:
    """A column label for a snapshot key the book never labelled.

    Short keys uppercase and longer ones title-case, which is a rule rather than a lookup and
    happens to be the genre's own convention: `hp` and `mp` are initialisms and so are `str`,
    `dex` and `int`, while `attunement` and `soul_thread` are words. It reproduces
    the retired default sheet's four labels exactly from its four keys, which is what lets a derived
    sheet be the same object for a book that used the default.
    """
    return key.upper() if len(key) <= 3 else key.replace("_", " ").title()


def implied_sheet(records: Sequence[lc.StateRecord]) -> Sheet | None:
    """The column form this book's own snapshots imply, or `None` where they imply none.

    **This exists because the fallback was printing the operator's explicit not-this into
    every book's drafting prompt** (§161). The retired default was `Level | HP | MP | Gold`, and
    the progression direction of 2026-08-21 is explicit that the model is abilities in a
    graph and ranks with names and **not** HP/MP/Gold. A book that seeds
    `{"attunement": 1, "threads": 2, "threads_max": 3}` and declares no sheet was shown
    `[STATUS] sera — Level ? | HP ?/? | MP ?/? | Gold ?`: its own three quantities erased, four
    clichés put in their place, and a question mark where every number should have been. Since
    the declaring vocabulary was undocumented, that was every book.

    So the columns are read off the book's own snapshots instead. Keys the parser cannot use
    are dropped rather than guessed at — a key that is not an identifier cannot be a regex
    group, and a value that is not a plain integer cannot be matched by `\\d+` — and `None` for
    a book with nothing readable, which is the only case left where a caller falls back.

    **The union across snapshots, in order of first appearance, and monotone on purpose.** A
    system that grants a new quantity mid-book adds a column, and a sheet that could lose one
    would stop parsing lines the book had already printed. Taking the union means the shape
    only ever grows, which is the safe direction for a parser reading back prose that is
    already on disk — and it is the genre's own direction, since what this reader collects is
    what the person keeps.
    """
    snapshots = sorted(
        (
            record
            for record in records
            if record.predicate == STATUS_PREDICATE
            and state_mod.is_canon(record)
            and isinstance(record.value, Mapping)
        ),
        key=lambda record: state_mod.order_key_of(record) or "",
    )
    keys: list[str] = []
    for record in snapshots:
        assert isinstance(record.value, Mapping)
        for key, value in record.value.items():
            if not isinstance(key, str) or not key.isidentifier() or key in keys:
                continue
            if isinstance(value, bool) or not isinstance(value, int):
                continue
            keys.append(key)
    known = set(keys)
    fields = tuple(
        SheetField(key, label_for(key), paired=f"{key}{MAX_SUFFIX}" in known)
        for key in keys
        if not (key.endswith(MAX_SUFFIX) and key[: -len(MAX_SUFFIX)] in known)
    )
    return Sheet(fields) if fields else None


def sheet_for(records: Sequence[lc.StateRecord], *, subject: str | None = None) -> Sheet | None:
    """The sheet this book declared, the one its own snapshots imply, or the default.

    **Abstains when the book says more than one thing**, exactly as `attested_position` does:
    two declarations are a disagreement about the book's own vocabulary, and picking either
    would be this module choosing which of the author's answers is real.

    **A book that declared nothing is now read rather than assumed** (§161, and
    `implied_sheet` carries the measurement). The old fallback was the retired default sheet
    unconditionally, which imposed `Level | HP | MP | Gold` on every book that had not
    declared — and since the declaring vocabulary was undocumented, that was all of them. The
    columns come off the book's own snapshots instead, so the line a writer is shown is the
    line their book actually counts by.

    **No default survives (§205).** A book with one declaration prints that; a book with none
    prints the columns its own snapshots imply (`implied_sheet`), which for both golden
    fixtures and every store written before this function read anything is exactly the
    `Level | HP | MP | Gold` the retired default carried, in the same canonical order; a book
    with no readable snapshot at all has no sheet and prints no line, which is a book
    `speaks_system_voice` refuses and the genre floor blocks, so nothing is ever asked to
    print it.
    """
    parsed = [
        parse_sheet(record.value)
        for record in records
        if record.predicate == SHEET_PREDICATE and state_mod.is_canon(record)
    ]
    # **A sheet with an owner is that owner's and nobody else's** (§206). Asked for a
    # subject, the declaration naming that subject wins, then one naming one of its
    # roles, then the book's own sheet; asked for the book, only the sheets with no
    # owner compete, so a place's columns never become the person's line.
    if subject is not None:
        for sheet in parsed:
            if sheet.owner == subject:
                return sheet
        roles = set(worlds_mod.entity_roles(_canon_of(records)).get(subject, ()))
        for sheet in parsed:
            if sheet.owner is not None and sheet.owner in roles:
                return sheet
    declared = [sheet for sheet in parsed if sheet.owner is None]
    if len(declared) == 1:
        return declared[0]
    # Two declarations are a disagreement about the book's own vocabulary, which
    # `genre.system_gap` reports for the Architect to settle. Until it is, the book's own
    # snapshots settle which one is live (§205): the declaration whose every column the
    # snapshots hold prints, when exactly one does; otherwise the columns the snapshots
    # hold print, as an undeclared book's do. The retired default used to stand here.
    implied = implied_sheet(records)
    if implied is None:
        return None
    held = set(implied.value_keys)
    live = [sheet for sheet in declared if set(sheet.value_keys) <= held]
    return live[0] if len(live) == 1 else implied


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
    subject: str,
    value: Mapping[str, object],
    *,
    sheet: Sheet | None = None,
    records: Sequence[lc.StateRecord] = (),
) -> str:
    """A status line for a subject and a snapshot value — the inverse of `sheet.pattern`.

    **The subject is written display-formed, and this reverses what stood here.** It used to
    read "the subject is written as the book's records hold it", on the argument that
    `normalise_subject` is not invertible and that title-casing an id would mint a fact no
    canon record states. The first half is true and is why `display_name` asks canon before it
    humanises; the second was wrong twice over — the fact is usually on record (`is_a`), and
    the alternative was not neutrality but a machine id on a reader's page, which pilot 15's
    draw 3 printed twice in one chapter. `display_name` carries the reasoning and the guard
    that keeps the printed name reading back to this same subject.

    `sheet` defaults to the LitRPG line rather than to the caller's book, so a caller that has
    records in hand must pass `sheet_for(records)` — the default is for callers that have none.
    `records` is the same story for the name: a caller holding the book's records passes them
    and gets the book's own spelling; one holding none gets the humanised id, which is still
    never the id.
    """
    # **No default** (§205): the sheet is the one given, the book's own, or the one this
    # snapshot implies; a value with no numeric key renders the tag and the subject alone.
    chosen = (
        sheet
        or (sheet_for(records, subject=subject) if records else None)
        or sheet_from_value(value)
    )
    if chosen is None:
        return f"[STATUS] {display_name(records, subject)} — "
    return chosen.render(
        display_name(records, subject),
        value,
        resolve=lambda entity: display_name(records, entity),
    )


def progression_target(records: Sequence[lc.StateRecord], *, at: str | None = None) -> str | None:
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
    return render_status_line(target.subject, target.value, records=records)


def standing_target(records: Sequence[lc.StateRecord], *, at: str | None = None) -> str | None:
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
    (`plan/stage-0-decisions.md` §113).
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
        record for record in scheduled if at is None or (state_mod.order_key_of(record) or "") >= at
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


def standing_example(records: Sequence[lc.StateRecord], *, at: str | None = None) -> str | None:
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
        (edge.phrase for edge in line.edges if edge.predicate == worlds_mod.STANDS_AT_PREDICATE),
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

    **The value must be a mapping, because "speaks" is a promise about the chain and not
    about one record's existence** (§158). Everything that answers True here reads fields
    out of the snapshot: `render_status_line` formats them, `system_voice_example` fills the
    line the writer is shown, the outline reads the seed it schedules milestones from — and
    extraction itself only ever mints mappings. Serial Pilot 14 seeded a prose-valued
    snapshot, the only shape `world declare --value` could then carry, and measured the
    split this clause closes: the floor built on this predicate passed, the sheet reached
    the packet as fact, and the book was never asked to end a scene with a status line,
    because `system_voice_example` had nothing to render numbers from. A predicate that
    answers True while the ask stays silent is the exact disagreement
    `genre.has_starting_sheet` delegates here to rule out.
    """
    return sheet_for(records) is not None and any(
        record.predicate == STATUS_PREDICATE
        and state_mod.is_canon(record)
        and isinstance(record.value, Mapping)
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
#: are the reveal positions the retired Forge minted **in `beats_for`'s own width, from the
#: book's own scene count** — that is what stage-0 §107.9.1 defect 10 was fixed to guarantee, and
#: it is exactly what makes them not somebody else's numbering. Left out, a forged world would
#: flip `has_story_vocabulary` to True on its own seed and §12 step 5 would extract nothing from
#: any scene, which is the silence measured for the seeded-interiority case arriving by a fourth
#: door. `test_an_architect_world_does_not_look_like_an_authors_vocabulary` pins it.
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


def humanise_subject(subject: str) -> str:
    """`normalise_subject`'s two moves undone: underscores back to spaces, words capitalised.

    Lossy in the direction that matters least. `mckay` comes back `Mckay`, because casefolding
    threw away the capital and nothing here can know it was there — which is exactly why
    `display_name` asks canon first and reaches this only when the book stated no name.
    """
    return " ".join(part.title() for part in subject.split("_") if part)


def display_name(records: Sequence[lc.StateRecord], subject: str) -> str:
    """What a book prints where it names `subject` on the page — never the id itself.

    **The defect: a snake_case subject id reached a reader.** Pilot 15's draw 3 printed
    `[STATUS] tam_cawl — Keeping 1 | …` twice in one chapter while its column labels arrived
    display-formed, because the labels come off a declared `Sheet` and the subject was written
    out as the records hold it. Draw 2 of the same book printed `[STATUS] Mira Kell — …` from
    the *same* code and the same shape of prompt: the writer there substituted the name the
    instruction asks for ("write the character's name as your prose spells it") and draw 3's
    copied the example verbatim. So the raw id was in both prompts and both draws, and what
    stood between it and the page was a model choosing to paraphrase. That is the placement
    `system_voice_example` already refused to make for `{subject}`, arriving with an id in the
    slot instead of a brace.

    **Canon first.** `is_a` is where this vocabulary keeps names — `application/world.py`
    documents it to the Architect as *what a thing is called, in this world's own words*, and
    `gamesystem` already reads system, rung and ability names out of it. Both draws held one:
    `tam_cawl is_a Tam Cawl`, `mira_kell is_a Mira Kell`. Nothing was missing; nothing looked.

    **A name is used only when it normalises back to the subject**, and that guard is the whole
    of what makes the lookup safe. `extract_state` reads the printed line back through
    `normalise_subject` and skips any subject canon has not already used, so printing a name
    that lands on a different id would not split the book's state — it would stop reading it,
    scene after scene, while every line still looked right on the page. That is the silence
    this module's own docstring says no gate catches. The guard also settles the other reading
    of `is_a` for free: a book that files `mira_kell is_a mender` has stated a kind rather than
    a name, `mender` does not normalise to `mira_kell`, and the humanised id is printed instead.

    A subject that is not already its own normalised form is a prose name a caller passed in
    (`Rook`, `Silas`), and it is returned untouched — title-casing it would damage a `McKay`
    that arrived spelled correctly.

    **What this cannot promise.** An id no display form normalises back to — a doubled or
    leading underscore — humanises to something that reads back as a different id. It is
    printed anyway: `humanise_subject` is not conditional, because a machine id on the page is
    the defect and there is no third form to fall to. Such an id is already unreachable from
    the Architect's vocabulary and `test_a_subject_id_that_cannot_round_trip_is_still_never_raw`
    pins the choice rather than hiding it.

    The first canon `is_a` that passes the guard wins. A book stating two names for one subject
    has contradicted itself somewhere this function has no standing to adjudicate.
    """
    if subject != normalise_subject(subject):
        return subject
    for record in records:
        if (
            record.subject == subject
            and record.predicate == "is_a"
            and state_mod.is_canon(record)
            and isinstance(record.value, str)
            and normalise_subject(record.value) == subject
        ):
            return record.value.strip()
    return humanise_subject(subject)


def attested_position(records: Sequence[lc.StateRecord], logical_id: str) -> str | None:
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


def record_id_for(subject: str, predicate: str, order_key: str, value: Mapping[str, object]) -> str:
    """Content-derived, and **value-sensitive on purpose**.

    A replayed tick must converge rather than accumulate, so the id cannot carry the revision
    or the logical id. But keying on `(subject, predicate, order_key)` alone makes the
    detector permanently unreachable: `record_state_records` is `INSERT OR IGNORE`, so a
    contradicting record would collide with the one it contradicts, insert zero rows, leave
    the old value standing, and report success. Including the value means two disagreeing
    readings are two rows — which is exactly what the detector needs to see them.
    """
    material = payload_digest({"s": subject, "p": predicate, "k": order_key, "v": value})
    return f"rec-x{sha256(material.encode()).hexdigest()[:24]}"


def graph_record_id_for(subject: str, predicate: str, object_ref: str, order_key: str) -> str:
    """Content-derived, with the position in the material.

    `record_id_for` puts the *value* in so that two disagreeing readings are two rows the
    detector can see. An edge carries no value, so the equivalent question is different: the
    same edge re-established at a later position is what promotion is made of, and an id blind
    to the position would collapse the promoted canon row onto the proposal it promotes and
    `INSERT OR IGNORE` would keep the proposal.
    """
    material = payload_digest({"s": subject, "p": predicate, "o": object_ref, "k": order_key})
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
                # The criterion rides on the edge so two ladders in
                # one world must not splice. Derived rather than printed — the page prints a
                # rung and a reader knows which ladder it is on.
                value=(worlds_mod.criterion_of_rung(_canon_of(known), target) if stands else None),
                story_position=lc.StoryPosition(order_key=order_key),
                authority=(
                    lc.StateAuthority.ACCEPTED_CANON if stands else lc.StateAuthority.PROPOSED
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
        # **A proposal is promoted only from a position this scene can place** (§167). The old
        # test was `earlier >= order_key`, so a proposal keyed in the schedule space answered
        # `'0350' >= 's1'` with `False`, fell through the guard, and was minted as
        # `ACCEPTED_CANON` at scene one carrying the note `proposed at 0350` — a declaration
        # about the end of the book promoted into canon at the start of it. No store on disk
        # holds such a record today, so this reproduces nowhere and is fixed anyway: the guard
        # can only ever promote *fewer* edges than before, so it cannot invent a fact, and a
        # canon-minting path is the wrong place to leave a comparison that is wrong by spelling.
        if earlier is None or not state_mod.comparable(earlier, order_key):
            continue
        if earlier >= order_key:
            continue
        key = _edge_key(record)
        if key in already:
            continue
        reused = any(
            record.predicate not in touched.get(endpoint, set()) and endpoint in touched
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
    order_key = attested_position(known, logical_id) or stated_position(known, stated_order_key)
    if order_key is None:
        return ()
    #: Recorded on every record whose position the planner supplied, because "the book said
    #: where this sits" and "the sheet we planned said so" are different provenance and an
    #: audit that could not tell them apart would be worth less than one that says nothing.
    minted = attested_position(known, logical_id) is None
    subjects = {record.subject for record in known if state_mod.is_canon(record)}
    # The book's own line, not this module's. A book that declared `Loop | Day` writes and is
    # read in `Loop | Day`; one that declared nothing gets exactly what it always got.
    # The book's own line: declared, implied by its snapshots, or taught by the first line
    # this scene prints (§205). A book with none of the three prints no status line and is
    # read for none; the graph line below is its own declaration and still runs.
    sheet = sheet_for(known)
    taught = sheet is None
    if taught:
        sheet = sheet_from_line(text)
    if sheet is None:
        return extract_graph_facts(
            text,
            known=known,
            project_id=project_id,
            book_id=book_id,
            branch_id=branch_id,
            logical_id=logical_id,
            version_id=version_id,
            order_key=order_key,
        )

    extracted: list[lc.StateRecord] = []
    # **Read tolerantly, so a projected line is a partial snapshot** (§203). The strict
    # `pattern` needs every column; a line printing only the held columns folds forward
    # onto the columns it left out, which is what `state_as_it_stands` already does.
    ids = {display_name(known, subject).casefold(): subject for subject in subjects}
    declared = False
    for read_subject, span in _status_lines(text):
        subject = normalise_subject(read_subject)
        # A name canon has never used is a claim about someone new, which is a proposal
        # rather than a reading of what the book already established.
        if subject not in subjects:
            continue
        # **Each line is read with its owner's columns** (§206): a place's line with the
        # place's sheet, the person's with the book's. A taught sheet is the book's.
        own = sheet if taught else (sheet_for(known, subject=subject) or sheet)
        found = own.read(text[span[0] : span[1]], ids=ids)
        if not found:
            continue
        read = found[0][1]
        # **The record is the whole state, the line is its projection.** A partial record at
        # a position where a fuller one stands reads as a contradiction to the integrity
        # detector (two values for one fact at one position), so the columns the line left
        # out are filled from the fold of this subject's own snapshots up to here, later
        # values winning: the writer's *carry these values forward unchanged* applied on this
        # side, and the same fold `state_as_it_stands` renders from.
        value = {**_folded_before(known, subject, order_key), **read}
        if taught and not declared:
            # **The first line an undeclared book prints is its declaration** (§205):
            # the columns in the order the page carries them, canon because the prose
            # was accepted, so every later scene is read against the book's own order
            # rather than the store's sorted keys.
            declared = True
            extracted.append(
                worlds_mod.world_record(
                    subject,
                    SHEET_PREDICATE,
                    value=sheet.declaration(),
                    authority=lc.StateAuthority.ACCEPTED_CANON,
                )
            )
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
        start, end = span
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


def _folded_before(
    known: Sequence[lc.StateRecord], subject: str, order_key: str
) -> dict[str, object]:
    """This subject's state as it stands at `order_key`, folded forward from its own canon
    snapshots (later values winning), for a projected line to be completed from (§203).

    The fold is `state_as_it_stands`'s, applied to a named subject: only canon, only this
    subject, only positions that fold into this one.
    """
    history = sorted(
        (
            record
            for record in known
            if record.predicate == STATUS_PREDICATE
            and state_mod.is_canon(record)
            and record.subject == subject
            and isinstance(record.value, Mapping)
            and _folds_into(state_mod.order_key_of(record), order_key)
        ),
        key=lambda record: state_mod.order_key_of(record) or "",
    )
    values: dict[str, object] = {}
    for record in history:
        assert isinstance(record.value, Mapping)
        values.update(record.value)
    return values


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
            and any(span.source.logical_id == replacing_logical_id for span in record.evidence)
        )
    )


__all__ = [
    "CONFIGURATION_PREDICATES",
    "GRAPH_REGISTRY_VERSION",
    "LABEL_CHARS",
    "LABEL_WORDS",
    "OWN_POSITION_VERSIONS",
    "PHRASE_WORDS",
    "PLANNED_POSITION_VERSION",
    "REGISTRY_VERSION",
    "SHEET_PREDICATE",
    "STATUS_PREDICATE",
    "GraphEdge",
    "GraphLine",
    "MalformedGraphLine",
    "MalformedSheet",
    "Movable",
    "Sheet",
    "SheetField",
    "attested_position",
    "counted_names",
    "declaration_from_snapshots",
    "display_name",
    "extract_graph_facts",
    "extract_state",
    "graph_line_fault",
    "graph_line_for",
    "graph_record_id_for",
    "humanise_subject",
    "implied_sheet",
    "label_for",
    "movable_names",
    "movables",
    "moved_to",
    "normalise_subject",
    "offered_choice",
    "offered_line",
    "parse_graph_line",
    "parse_sheet",
    "promotions",
    "record_id_for",
    "sheet_for",
    "sheet_from_line",
    "sheet_from_value",
    "snapshot_at",
    "standing_example",
    "standing_target",
    "state_as_it_stands",
]


def system_voice_example(
    records: Sequence[lc.StateRecord], *, at: str | None = None, include_at: bool = True
) -> str | None:
    """The book's own current status line, to show a generator what to write — or None.

    **A filled example rather than the line's own template, and that is a measurement rather than a
    preference.** The instruction first showed the template with its `{subject}` placeholder
    intact, and three local models were asked to draft against it: two substituted the
    character's name and one wrote `[STATUS] {subject} — Level 3 | ...` verbatim. That line
    *matches* the line's own pattern — a brace-wrapped word is a perfectly good subject — so nothing
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
    standing = state_as_it_stands(records, at=at, include_at=include_at)
    if standing is None:
        return None
    subject, values = standing
    return render_status_line(subject, values, sheet=sheet_for(records), records=records)


def _folds_into(key: str | None, ceiling: str | None) -> bool:
    """Whether a snapshot at `key` is part of the state standing at `ceiling`.

    The un-keyed snapshot folds at every position — `status_snapshot`'s documented line calls it
    *the state the book opens in* — and a positioned one folds only when its key is in the
    ceiling's own space and at or before it. A ceiling that is itself un-keyed admits only the
    un-keyed, which is what the old `or ""` arithmetic already did and the one case it got right.
    """
    if key is None:
        return True
    if ceiling is None:
        return False
    return state_mod.comparable(key, ceiling) and key <= ceiling


def state_as_it_stands(
    records: Sequence[lc.StateRecord], *, at: str | None = None, include_at: bool = True
) -> tuple[str, dict[str, object]] | None:
    """The subject and its whole state at `at`, folded forward across snapshots.

    **A snapshot is not required to restate the sheet, and assuming it did was a live
    exposure** (§161). `render_status_line` fills an absent key with `?`, so rendering one
    partial snapshot puts a question mark on every column that scene did not touch — the same
    defect `implied_sheet` was written against, arriving by a different door. The game system's
    advancement records the edge that moved plus the snapshot it renders, and world-vocabulary
    record ids are position-blind under an `INSERT OR IGNORE` store, so an unchanged holding
    keeps the position where it was established rather than being rewritten at the new one.
    Reading one record would therefore have shown the writer a sheet with holes in it wherever
    the system worked correctly.

    So the values are folded: every canon snapshot up to and including `at`, in order, later
    values winning. That is not a new rule — it is the writer's own instruction (*"carry these
    values forward unchanged unless this scene changes them"*) applied on this side, so the
    line a writer is shown and the line a writer is asked to write are the same statement.

    **Folded within one subject only.** The fold takes the subject of the snapshot that stands
    at `at` and merges only that subject's snapshots; a book with two characters holding sheets
    would otherwise have one of them shown the other's numbers. `snapshot_at` picks which
    record stands, and its selection rule is unchanged.

    A book whose snapshots each restate everything folds to exactly the latest one, which is
    every store written before this and both golden fixtures.

    **The fold reads one order-key space, and reading two was Serial Pilot 15's finding**
    (§165). `state_mod.comparable` is what says so: an un-keyed snapshot is the state the book
    opens in and folds at every position, a snapshot in the ceiling's own space folds when it
    is at or before it, and a snapshot in the *other* space is a declared schedule that this
    book has not reached — canon, readable, and never folded as past. Before that rule the
    ceiling itself could be a scheduled key, because `max` over mixed spaces picks by spelling.
    """
    latest = snapshot_at(records, at=at, include_at=include_at)
    if latest is None or not isinstance(latest.value, Mapping):
        return None
    ceiling = state_mod.order_key_of(latest)
    history = sorted(
        (
            record
            for record in records
            if record.predicate == STATUS_PREDICATE
            and state_mod.is_canon(record)
            and record.subject == latest.subject
            and isinstance(record.value, Mapping)
            and _folds_into(state_mod.order_key_of(record), ceiling)
        ),
        key=lambda record: state_mod.order_key_of(record) or "",
    )
    values: dict[str, object] = {}
    for record in history:
        assert isinstance(record.value, Mapping)
        values.update(record.value)
    return latest.subject, values


def snapshot_at(
    records: Sequence[lc.StateRecord], *, at: str | None = None, include_at: bool = True
) -> lc.StateRecord | None:
    """The canon status snapshot that stands at `at`, or `None`.

    **Extracted from `system_voice_example` so a second reader of the same sheet cannot pick a
    different one.** `counted_names` names the quantities the writer's scheduled beat may move,
    and `system_voice_example` renders the line the writer is shown; a beat naming a quantity
    that is not on the line the writer was handed would be this module answering one question
    twice. The selection rule and its measured reason both live here now, once.

    The rule is `system_voice_example`'s, unchanged: the snapshot *at* the position wins,
    because a model shown a line will use its numbers and an imported book holds a snapshot for
    every position at once — showing scene six's balance while asking for scene one invents a
    state the integrity gate then refuses, and a refusal caused by the instruction rather than
    by the prose. Failing that, the latest one before it, which for a book still being written
    is the state the next scene continues from and for a book with nothing placed yet is the
    starting sheet.

    **"Before it" is asked within one order-key space** (§165). A snapshot the Architect
    scheduled at `0350` is not earlier than scene one because `'0350' < 's1'`; it is a position
    in the other space, and the book has not reached it. `state_mod.comparable` decides, the
    un-keyed snapshot stays eligible everywhere, and the schedule stays canon and unread here.

    **Whose sheet is asked before which of theirs stands** (§170). Every rule above answers
    *when*; none of them answered *whose*, and until a second member of the cast held a sheet
    the two questions could not come apart. Serial Pilot 15's third draw is where they did:
    the Architect gave the protagonist and a thirteen-year-old apprentice an opening snapshot
    each, both un-keyed, and the tie fell out of `max` over two empty strings — which is store
    row order, and it went to the apprentice. The chapter then printed the apprentice's line
    twice and the protagonist's declared opening position (*mender, keeping three, nineteen
    marks*) never reached the page at all. Nothing was blocked and nothing was wrong with her
    records; the selection simply had no opinion.

    So the protagonist's own snapshots are taken first where she holds any, and the position
    rules below run inside them. `worlds.protagonist_brief` is the source and it is the same
    one `application/planner.py` already reads for point of view a line above this call, so
    the line the writer is shown and the person the packet is built for cannot disagree. It is
    a derivation and never a choice (§61(5)): the role is declared in the book's own canon, and
    two declared protagonists resolve first-by-subject-id there rather than here.

    **A book whose protagonist holds no sheet falls through unchanged**, which is every book
    written before a protagonist role existed, both golden fixtures, and every store holding
    exactly one sheet-holder — including Serial Pilot 15's second draw, where this filter is a
    no-op because the mender was the only subject with a snapshot at all. The fall-through
    matters beyond compatibility: `genre.has_starting_sheet` reads this chain, so a filter that
    could empty it would newly refuse to draft books that draft today.

    **The filter also closes a ratchet.** Extraction writes a snapshot at the scene's own key
    for whoever the prose printed, and a keyed snapshot outranks an un-keyed opening — so one
    arbitrary tie at scene 1 aimed every later scene at the same subject for the rest of the
    book. Taking the protagonist first is asked before the ordering, so a side character's
    extracted line can no longer capture the furniture. A side character *progressing* is
    untouched: their snapshots stay canon, stay extracted and stay in the packet. What they no
    longer own is the one line the reader reads as the interface.
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
        # Unreachable since §158: `speaks_system_voice` itself now requires a renderable
        # mapping, so the guard above and this filter agree by construction. Kept so a future
        # loosening of the predicate fails toward abstaining rather than toward `str.get`.
        return None
    snapshots = _the_protagonists(snapshots, records)
    exact = (
        [record for record in snapshots if state_mod.order_key_of(record) == at]
        if include_at
        else []
    )
    earlier = [
        record
        for record in snapshots
        if at is None or _stands_before(state_mod.order_key_of(record), at)
    ]
    fallback = [record for record in snapshots if at is None] if not include_at else snapshots
    chosen = exact or earlier or fallback
    if not chosen:
        return None
    return max(chosen, key=lambda record: state_mod.order_key_of(record) or "")


def _the_protagonists(
    snapshots: Sequence[lc.StateRecord], records: Sequence[lc.StateRecord]
) -> list[lc.StateRecord]:
    """The protagonist's snapshots, or all of them where she holds none.

    Narrowing rather than selecting: this returns a subset of what it was given and decides
    nothing about which member of that subset stands. `snapshot_at` owns that, unchanged.

    The empty case is the whole reason this is a function and not two lines inline. A book with
    no declared protagonist and a book whose declared protagonist has no sheet are different
    facts with the same right answer — leave the set alone — and both are ordinary rather than
    exceptional: the first is every book written before 2026-08-22, and the second is any book
    whose sheet-holder is somebody the world did not name as its own.
    """
    brief = worlds_mod.protagonist_brief(records)
    if brief is None:
        return list(snapshots)
    owned = [record for record in snapshots if record.subject == brief.subject]
    return owned or list(snapshots)


def _stands_before(key: str | None, at: str) -> bool:
    """Whether a snapshot at `key` is one the book had already reached by `at`.

    Un-keyed is the opening state and precedes every position. A positioned snapshot has to be
    in `at`'s own space to be anywhere relative to it at all.
    """
    if key is None:
        return True
    return state_mod.comparable(key, at) and key < at


@dataclass(frozen=True, slots=True)
class Movable:
    """One quantity a scheduled beat may name, and the snapshot key that quantity moves.

    **The pair exists because the beat and the check read the same answer from two ends.** The
    plan carries the `name` — the book's own word, which is the whole of §161.4's argument for
    naming a quantity rather than a category — and the only thing that can afterwards say
    whether it moved is the `key` it occupies in the `status_snapshot` this book prints. A
    function returning names alone forces whoever verifies the ask to map a label back onto a
    column by its own rule, and a second mapping is a second answer to "which number is this".

    The mapping is never invented here. In the legacy arm the pair is a `SheetField`'s own
    `(label, name)`; in the system arm it is a `gamesystem.Column`'s `(label, name)`, except
    for a rise, which is named by the rung it reaches and moves `gamesystem.RANK_KEY` — the one
    place the two differ, and it differs because a rank has a name of its own while the column
    carrying it does not.
    """

    name: str
    key: str


def counted_names(records: Sequence[lc.StateRecord], *, at: str | None = None) -> tuple[str, ...]:
    """The names this book's own system counts by, in the order its sheet prints them.

    **This is the book's vocabulary, read off canon, and this module mints none of it.** The
    labels come from the sheet the book declared (or, for a book that declared none, from the
    default line this module shipped with), filtered to the fields the book's *current*
    snapshot actually holds a value for. A book whose sheet declares a column it never fills
    does not get that column named, because a beat naming a quantity the writer cannot see on
    the line handed to it is a beat asking for a number out of nowhere.

    **Empty is the control and it is the common case for everything written before a sheet
    existed.** A book that speaks no system voice returns `()`, and every caller composes the
    unnamed form it composed before this function existed.

    **`MACHINERY_WORDS` are dropped, and the reason is `genre.BEAT`'s own** (§155.3): this
    vocabulary is composed into a scene plan, the scene plan reaches the writer, and §120
    measured `standing` reaching a chapter as prose when repo vocabulary got that far. A label
    is book data rather than house text, so no ceiling test covers it; the filter is where the
    guarantee has to live. A book whose every label collides falls back to the unnamed form,
    which is the correct failure — the schedule still fires and names nothing.
    """
    return tuple(item.name for item in _counted(records, at=at))


def _counted(records: Sequence[lc.StateRecord], *, at: str | None = None) -> tuple[Movable, ...]:
    """`counted_names` with the column each name moves still attached. See `Movable`."""
    standing = state_as_it_stands(records, at=at)
    if standing is None:
        return ()
    held = set(standing[1])
    sheet = sheet_for(records)
    if sheet is None:
        return ()
    return tuple(
        Movable(field_.label, field_.name)
        for field_ in sheet.fields
        if field_.numeric
        and field_.name in held
        and field_.label.casefold() not in house_mod.MACHINERY_WORDS
    )


def movable_names(
    records: Sequence[lc.StateRecord], *, character: str | None = None, at: str | None = None
) -> tuple[str, ...]:
    """What the scheduled progression beat may name as moving here, in declaration order.

    **The one source of beat vocabulary, and it has two arms with no mode flag** — the
    recognition ratchet is the mode, which is the shape Track 1's game system and §158's
    status-snapshot recognition already share. Every caller asks this one question; nothing
    downstream branches on what kind of book it got.

    *The legacy arm*, live and below: a book with no game system is named by the columns its
    own status line prints (`counted_names`). It is a superset — a label is a quantity that
    exists, which is not the same claim as a quantity that may move next — and a superset is
    the right error for a book whose system was never modelled, because the alternative for
    such a book is the categorical `genre.BEAT` and read 8 §4.2 measured what a category buys.

    *The system arm*, where this book declares exactly one system and the character stands
    somewhere in it: `gamesystem.legal_moves` over that sheet, named in the declaration order
    that accessor already returns them in. It is strictly better and not merely different —
    it knows an ability whose prerequisite is unmet is **not** offered, which a label cannot
    know, so it stops the schedule naming a move the book cannot make. It ranks nothing and
    this function must not make it rank anything (§61(5)): declaration order is the book's own
    order, and `genre.beat_text` rotates through it by schedule position for that reason.

    **An empty answer from the system arm is an answer**, not a reason to fall through. A sheet
    with no legal move left is a character who cannot advance, and naming a column they hold
    would tell the scene something moves when the system says nothing can. The fall-through is
    for the cases where the system arm *cannot answer at all* — no system declared, more than
    one, or no canon position for this character.

    Two systems is an abstention rather than a choice, on `sheet_for`'s own precedent: two
    declarations are a disagreement about the book's own vocabulary, and picking either would
    be this module deciding which of the author's answers is real. Such a book falls to the
    legacy arm, which is a description of what it prints rather than a claim about what it
    can do.

    **Canon only**, which is `genre._declared_systems`' rule for `genre`'s reason: `systems_of`
    deliberately reads proposals too, because the Architect builds a system before `world
    accept` and a reader that saw nothing until acceptance would report an empty world
    mid-build. A beat is not that reader — a proposed system is a plan for later, and
    scheduling a scene around one would put an unaccepted draw on the page.

    **The names alone**, because a plan carries words. `movables` is the same answer with the
    column each name moves still attached, and it is the one this function projects — so the
    quantity a beat asks for and the number a later check reads cannot come apart.
    """
    return tuple(item.name for item in movables(records, character=character, at=at))


def movables(
    records: Sequence[lc.StateRecord], *, character: str | None = None, at: str | None = None
) -> tuple[Movable, ...]:
    """`movable_names` with the column each name moves still attached. See `Movable`.

    Every rule, arm and abstention is `movable_names`' own and is documented there; this holds
    the body because the pair is the fuller answer and the names are a projection of it. Kept
    as one function for the reason that docstring gives for having one source of beat
    vocabulary at all: a second reader of "what may move here" is a second answer to it.
    """
    standing = _standing_sheet(records, character=character, at=at)
    if standing is not None:
        system, sheet = standing
        return _named_moves(system, gamesystem_mod.legal_moves(sheet))
    return _counted(records, at=at)


def _standing_sheet(
    records: Sequence[lc.StateRecord], *, character: str | None = None, at: str | None = None
) -> tuple[gamesystem_mod.SystemDef, gamesystem_mod.CharacterSheet] | None:
    """The one system this book declares and this character's position in it — or `None`.

    **The arm selection, factored, so two readers of it cannot become two answers.** This is
    the condition `movables` documents in full: exactly one declared system, its columns the
    columns this book actually prints, and a canon position for this character in it. `None` is
    the fall-through to the legacy arm and is the ordinary case for every book whose world
    declared no system.

    Extracted when `moved_to` needed the same three facts to say what a move would leave. A
    second copy of the condition would have let the vocabulary a beat is composed from and the
    number that beat's example prints come from different arms of the same question — which is
    the pairing `Movable` exists to hold together, one step further along.
    """
    if character is None:
        return None
    canon = [record for record in records if state_mod.is_canon(record)]
    system = _printing_system(canon, records)
    if system is None:
        return None
    sheet = gamesystem_mod.sheet_of(canon, character, system=system, at=at)
    return None if sheet is None else (system, sheet)


def moved_to(
    records: Sequence[lc.StateRecord],
    movable: Movable,
    *,
    character: str | None = None,
    at: str | None = None,
) -> int | None:
    """What `movable`'s column reads once the move that offered it has been made — or `None`.

    **The third projection of one question**, beside `movables` and `movable_names`: which
    quantities may move here, which column each one occupies, and what that column reads
    afterwards. All three read the same arm, so the word a beat carries, the number a gate
    checks and the number an example prints cannot come apart.

    *The system arm* answers by taking the move. `gamesystem.advance` is called on the sheet
    this character stands at and the value is read off `Advancement.after` — **the same
    arithmetic that would record the advancement if the book took it**, rather than an
    increment reproduced here. A system that ever declares a different step is therefore
    authoritative for free, and there is no second place to update.

    *The legacy arm* has no system to ask, so the answer is one step: a sheet declares columns
    and, where it pairs them, a ceiling, and it declares no step size. One is the smallest
    change an integer column can make, and the smallest change is the honest reading of a beat
    whose whole sentence is *moves here*. **It is not a magnitude anything is held to**: the
    gate this feeds refuses only a column that did not move at all (§184), so a scene whose
    events warrant more is refused by nothing.

    **`None` where the column has no room**, and that is the one case this refuses to answer
    rather than guessing at. A paired column standing at its own ceiling — `Warmth 6/6` — has
    no next value that is not `impossible_fields`' own defect, and rendering `Warmth 7/6` into
    a prompt as the state a scene leaves would ask the writer for a line the book may not
    print. The system arm needs no such guard because `legal_moves` already withholds a deepen
    at the scale's maximum and a rise at the top rung: there, having been offered is the proof
    that there is room.
    """
    standing = _standing_sheet(records, character=character, at=at)
    if standing is not None and at is not None:
        system, sheet = standing
        for move in gamesystem_mod.legal_moves(sheet):
            if _named_moves(system, (move,)) != (movable,):
                continue
            try:
                advanced = gamesystem_mod.advance(sheet, move, at=at)
            except gamesystem_mod.IllegalAdvance:
                # `legal_moves` offered it, so this is unreachable rather than tolerated —
                # caught because composing a prompt is not the place to discover that the two
                # disagree, and a book that hits it draws the entering line it drew before.
                return None
            after = advanced.after.get(movable.key)
            return after if isinstance(after, int) and not isinstance(after, bool) else None
        return None
    folded = state_as_it_stands(records, at=at)
    if folded is None:
        return None
    was = folded[1].get(movable.key)
    if not isinstance(was, int) or isinstance(was, bool):
        return None
    ceiling = folded[1].get(f"{movable.key}{MAX_SUFFIX}")
    if isinstance(ceiling, int) and not isinstance(ceiling, bool) and was + 1 > ceiling:
        return None
    return was + 1


def _printing_system(
    canon: Sequence[lc.StateRecord], records: Sequence[lc.StateRecord]
) -> gamesystem_mod.SystemDef | None:
    """The one declared system whose columns are the line this book prints, or `None`.

    **Two systems, one at a time** (§197). Until the concept stage a book's canon declared one
    system or none, and every arm here asked for exactly one. A book whose person comes under a
    second system after a turn declares two, and the one they stand in is the one whose columns
    the printed line has — `_system_prints_the_line`'s own test, applied to each. That is a fact
    about the book's line and not a preference among candidates (§61(5)); two systems that both
    print it are two answers, and the arms abstain as they always did.
    """
    printing = [
        system
        for system in gamesystem_mod.systems_of(canon)
        if _system_prints_the_line(system, records)
    ]
    return printing[0] if len(printing) == 1 else None


def _system_prints_the_line(
    system: gamesystem_mod.SystemDef, records: Sequence[lc.StateRecord]
) -> bool:
    """Whether the declared system's columns are the columns this book actually prints.

    **The system arm may only name what the writer can see** (§165). `counted_names` filters the
    legacy arm to the fields the current snapshot fills, for the stated reason that a beat naming
    a quantity absent from the line handed to the writer is a beat asking for a number out of
    nowhere. The system arm had no matching guard because, until a drawn system could exist
    beside a hand-declared sheet, the two could not disagree.

    Serial Pilot 15 is the book where they do: its seed declared a sheet of `rung`, `reach`,
    `carried` and `standing` **and** a system whose columns are the rung plus six capability ids,
    and completing the system (`gamesystem.completion_records`) would otherwise have switched its
    beats to naming abilities its status line does not print. `system_gap` reports exactly that
    disagreement, so this guard and that gap close together: the beats come from the system
    precisely when the book is a position in it.
    """
    sheet = sheet_for(records)
    return sheet is not None and {field_.name for field_ in sheet.fields} == set(system.value_keys)


def _named_moves(
    system: gamesystem_mod.SystemDef, moves: Sequence[gamesystem_mod.Move]
) -> tuple[Movable, ...]:
    """One name per available move, in the order they were offered, with the column it moves.

    A `RISE` is named by the rung it reaches and everything else by the ability that moves,
    which is the name the system itself declared — nothing here mints a word. **The column is
    the ability's own** (`SystemDef.columns` prints one per ability, keyed by `ability_id`),
    and a rise moves `RANK_KEY`, because the rung it reaches is a name and the rung column is
    the one number carrying it. `MACHINERY_WORDS`
    are dropped for `counted_names`' reason: this vocabulary reaches the writer inside a scene
    plan and therefore shapes prose a reader reads, and a declared name is book data that no
    ceiling test can cover.

    **A `CHOOSE` is dropped, and it is the one move this function refuses to name.** The
    progression beat's sentence is that a named quantity *moves*, and taking a fork moves no
    number — `gamesystem.choose` records the pick and changes not one column, because what a fork
    changes is which gains become legal. Naming a fork here would tell the scene something moved
    when nothing did, which is §161.4's own defect (a beat satisfied by the wrong thing) arriving
    through the other door. A fork belongs to `genre.interaction_text`, on its own schedule.
    """
    abilities = {ability.ability_id: ability.name for ability in system.abilities}
    ranks = {rank.rank_id: rank.name for rank in system.ranks}
    named: list[Movable] = []
    for move in moves:
        if move.kind is gamesystem_mod.AdvanceKind.CHOOSE:
            continue
        if move.kind is gamesystem_mod.AdvanceKind.RISE:
            name, key = ranks.get(move.rank_id or ""), gamesystem_mod.RANK_KEY
        else:
            name, key = abilities.get(move.ability_id or ""), move.ability_id or ""
        if name and key and name.casefold() not in house_mod.MACHINERY_WORDS:
            named.append(Movable(name, key))
    return tuple(named)


def offered_choice(
    records: Sequence[lc.StateRecord], *, character: str | None = None, at: str | None = None
) -> tuple[str, tuple[str, ...]] | None:
    """The fork standing open in front of this character here, in the book's own words.

    Returns `(the fork's name, the names of its ways)`, or `None` where no fork stands open —
    which is every book on disk today, every book whose world declares no system, and every
    position before the rung a fork opens at. `genre.interaction_text` is the caller and `None`
    is what makes its beat take the reading form or none at all.

    **Every guard here is `movable_names`' guard, deliberately, because the two answer one
    question about one book and a second set of rules would be a second answer.** Canon only,
    because a proposed system is a plan for later and scheduling a scene around one would put an
    unaccepted draw on the page. One declared system printing the line (`_printing_system`):
    a book may declare two (§197), and the one whose columns the printed line has is the one
    the person stands in, which is a fact about the book and not a choice between the
    author's answers; two that both print it are two answers and abstain.
    `_system_prints_the_line`, because a fork whose abilities are not columns of the line the
    writer was handed is a fork the reader cannot watch resolve.

    **The first fork in declaration order, and no ordering of any other kind** (§61(5)).
    Declaration order is the book's own order; nothing here asks which fork is the interesting
    one, and `gamesystem.pending_choices` is explicit that it ranks nothing.

    **A name colliding with `house.MACHINERY_WORDS` abstains the whole fork rather than dropping
    one way.** `counted_names` drops the offending label because its list is a rotation and a
    short rotation still works; a fork named with one of its ways missing is a menu that lies
    about what is on offer. The correct failure is the beat falling back to the reading form,
    which is what `None` here produces.

    **The position gate is the sheet's, and it cannot leak a schedule** (§165, §167).
    `gamesystem.sheet_of` applies `state.comparable` before its cutoff, so a `chose` or a
    `stands_at` written in the schedule space is canon, readable and never read as already
    reached; and a fork opens off the rung the sheet carries rather than off any story position,
    which is §110's rule that intent is not an event.
    """
    if character is None:
        return None
    canon = [record for record in records if state_mod.is_canon(record)]
    system = _printing_system(canon, records)
    if system is None:
        return None
    sheet = gamesystem_mod.sheet_of(canon, character, system=system, at=at)
    if sheet is None:
        return None
    pending = gamesystem_mod.pending_choices(sheet)
    if not pending:
        return None
    choice = pending[0]
    names = (choice.name, *(option.name for option in choice.options))
    if any(not name.strip() or name.casefold() in house_mod.MACHINERY_WORDS for name in names):
        return None
    return choice.name, tuple(option.name for option in choice.options)


def offered_line(
    records: Sequence[lc.StateRecord], *, character: str | None = None, at: str | None = None
) -> str | None:
    """The `[OFFER]` line the book prints for the fork standing open here, or `None`.

    Every guard is `offered_choice`'s, by calling it: a fork that function abstains on is a
    fork this line does not print. What this adds is only the rendering, `gamesystem.offer_line`,
    so the writer is handed the fork as furniture rather than as a sentence about a fork — the
    operator's read-10 item was a system that only reports, and a fork the reader cannot see
    the ways of is a fork the reader cannot want one of.
    """
    if offered_choice(records, character=character, at=at) is None or character is None:
        return None
    canon = [record for record in records if state_mod.is_canon(record)]
    system = _printing_system(canon, records)
    if system is None:
        return None
    sheet = gamesystem_mod.sheet_of(canon, character, system=system, at=at)
    if sheet is None:
        return None
    pending = gamesystem_mod.pending_choices(sheet)
    if not pending:
        return None
    return gamesystem_mod.offer_line(system, pending[0])
