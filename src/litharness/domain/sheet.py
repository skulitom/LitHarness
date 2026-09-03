"""The status line: the columns a book declares, the snapshot that fills them, the line it prints.

Split out of `domain/extraction.py` on 2026-09-03 (stage-0 §215) with every definition
byte-identical, and re-exported from there so `extraction.sheet_for` is still the one import
site. Three things live here because they are one fact read three ways: the `Sheet` a book
declares under `status_sheet` and the readers that find it (`sheet_for` is the one reader;
`parse_sheet`, `implied_sheet`, `sheet_from_line` and `sheet_from_value` are the forms it
reads); the `status_snapshot` that stands at a position and the fold that completes it
(`snapshot_at`, `state_as_it_stands`); and the printed line (`render_status_line`,
`Sheet.render`, `system_voice_example`), a projection of the snapshot and never a second
record of it.

The silence the docstrings below keep pointing at: a book that declared one sheet and was
silently read with another would ask every scene for a form its own canon does not use,
extract nothing, and look exactly like a book that established no state, which no gate
catches. `MalformedSheet` refuses rather than defaults for that reason, and every abstention
below is the same choice made again.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import cache

import litharness_contracts as lc

from litharness.domain import gamesystem as gamesystem_mod
from litharness.domain import state as state_mod
from litharness.domain import worlds as worlds_mod
from litharness.domain.names import display_name

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
    #: The system whose columns this sheet prints (§211). A sheet that names one is a
    #: projection of that system's columns as they stand, so a grant declared after the seed
    #: is a column the moment the world declares it, and the seed's declaration is not a
    #: second answer to which columns the book has. `None`, the default, is every sheet
    #: written before this: its fields are its own and stay as declared.
    system: str | None = None

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
        # **The flag is written when it differs from what reading it back would assume**
        # (§223). `parse_sheet` defaults an omitted `show_unheld` to `True` for a sheet whose
        # columns are its own and to `False` for one that names its system, so writing the key
        # only when it is `False` lost an explicit `True` on a following sheet's round trip.
        # A sheet whose columns are its own still omits a `True` and still writes a `False`,
        # which is every declaration on disk unchanged.
        if self.show_unheld != (self.system is None):
            declared["show_unheld"] = self.show_unheld
        if self.owner is not None:
            declared["owner"] = self.owner
        if self.system is not None:
            declared["system"] = self.system
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
            # A column the snapshot never held stays visible as `?` on a sheet whose
            # columns are its own; on a sheet that follows its system (§211) such a
            # column is a grant declared after the snapshot, which nobody holds yet, and
            # it is hidden like any unheld one. The fit census's probes found the line
            # printing `?` for every grant a system had grown by.
            held = any(
                (value.get(key) is None and self.system is None) or _held(value.get(key))
                for key in keys
            )
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

    **No default vocabulary** (§205). The line `extraction` shipped with, `Level | HP |
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
    owner = value.get("owner")
    if owner is not None and (not isinstance(owner, str) or not owner.strip()):
        raise MalformedSheet("owner must be a subject id or a role when given")
    system = value.get("system")
    if system is not None and (not isinstance(system, str) or not system.strip()):
        raise MalformedSheet("system must be a subject id when given")
    # **What an omitted `show_unheld` means depends on whose the columns are** (§223, from
    # pilot 25 draw 5). `True` is the flag's documented default and is every sheet written
    # before it existed, so a book whose columns are its own is unchanged. A sheet that
    # *names its system* (§211) has the system's grants for columns, and a drawn system's
    # own declaration has said `False` since §203 for the reason the market census gave —
    # the genre's windows do not print a row of zeros. Draw 5's Architect declared a
    # following sheet by hand, omitted the flag, and the opening line handed to its writer
    # read `Gloves ? | Held Time ? | Red Line ? | Second Reading ? | Standing Order ?`:
    # five of eight columns unanswered on the first line a reader meets, because the
    # opening snapshot holds three grants and the system declares eight. A hand-declared
    # following sheet now defaults the way the minted one does, and a declaration that
    # says `true` is still obeyed exactly (`test_a_sheet_following_its_system_hides_a_column
    # _the_snapshot_never_held` pins that).
    show_unheld = value.get("show_unheld", system is None)
    if not isinstance(show_unheld, bool):
        raise MalformedSheet("show_unheld must be true or false when given")
    return Sheet(
        tuple(fields),
        show_unheld=show_unheld,
        owner=owner.strip() if owner else None,
        system=system.strip() if system else None,
    )


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


def unreadable_sheets(records: Sequence[lc.StateRecord]) -> dict[str, str]:
    """Every `status_sheet` declaration this module cannot build a line from, by record id,
    with the sentence that says why.

    **Found by the fit census (`research/quality-measurement/system-fit/`), which declared a
    sheet repeating a value key through `world declare`:** `world accept` read it through
    `sheet_for` and fell over with a traceback, on the §213.1 preview and again at the
    floor, and `world check` would have done the same once the sheet was canon. `MalformedSheet`
    is raised on purpose (its docstring: a declaration that silently fell back looked like a
    book that established nothing), and `cmd_new` catches it; the declare path had no catch.
    This names the records so `check` can complain, `accept` can refuse, and every reader can
    leave them aside rather than crash. A later declaration in the same slot replaces one.
    """
    found: dict[str, str] = {}
    for record in records:
        if record.predicate != SHEET_PREDICATE:
            continue
        try:
            parse_sheet(record.value)
        except MalformedSheet as error:
            found[record.record_id] = (
                f"{record.subject}'s {SHEET_PREDICATE} cannot be read, so no line can be "
                f"rendered or read back from it: {error}. Declare the sheet again to replace it"
            )
    return found


def readable(records: Sequence[lc.StateRecord]) -> list[lc.StateRecord]:
    """`records` without the sheet declarations `unreadable_sheets` names."""
    unreadable = unreadable_sheets(records)
    return [record for record in records if record.record_id not in unreadable]


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
        _following(parse_sheet(record.value), records)
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


def _following(sheet: Sheet, records: Sequence[lc.StateRecord]) -> Sheet:
    """A sheet that names its system, with that system's columns as they stand (§211) and the
    book's own columns around them (§219).

    **The seed's declaration is not a second answer to which columns the book has.** A drawn
    system writes its own `status_sheet` (`gamesystem.records_for`), and until §211 the
    fields in that record were fixed at the seed while the system could go on being declared
    into: a grant `governed_by` the system after the seed joined `systems_of` and not the
    sheet, the two disagreed, `_system_prints_the_line` abstained, and the book's beats fell
    silently to the legacy arm. A sheet that names its system is a projection of the system's
    columns, so the one place a grant is declared is the one place a column comes from.

    **A column the system does not have is the book's own and stays where the sheet declares
    it** (§219, the fit census's second gap): the system's columns, in the system's order,
    take the place of the first declared field that is one of them, every other declared field
    that is one of them is dropped (the system is the one answer to those), and every field
    that is not is kept with its kind and its place. A sheet declaring exactly the system's
    columns, which is every drawn seed, resolves to the system's columns as it did.

    Canon only, for `sheet_of`'s reason; a system the world began and cannot read back leaves
    the declared fields as they are, so an unfinished system is reported and not guessed at.
    A sheet naming no system is returned untouched, which is every sheet written before this.
    """
    if sheet.system is None:
        return sheet
    for system in gamesystem_mod.systems_of(_canon_of(records)):
        if system.system_id != sheet.system:
            continue
        keys = set(system.value_keys)
        block = [SheetField(column.name, column.label) for column in system.columns]
        fields: list[SheetField] = []
        placed = False
        for field_ in sheet.fields:
            if field_.name in keys:
                if not placed:
                    fields.extend(block)
                    placed = True
                continue
            fields.append(field_)
        if not placed:
            fields.extend(block)
        return Sheet(
            tuple(fields),
            show_unheld=sheet.show_unheld,
            owner=sheet.owner,
            system=sheet.system,
        )
    return sheet


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
    that is not on the line the writer was handed would be this package answering one question
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
