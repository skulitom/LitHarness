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
CONFIGURATION_PREDICATES = frozenset({SHEET_PREDICATE})


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
        seen = [key for key in self.value_keys]
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
    """
    return any(
        state_mod.order_key_of(record)
        for record in known
        if state_mod.is_canon(record) and record.predicate_registry_version != REGISTRY_VERSION
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
    return tuple(extracted)


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
    "REGISTRY_VERSION",
    "SHEET_PREDICATE",
    "STATUS_PATTERN",
    "STATUS_PREDICATE",
    "MalformedSheet",
    "Sheet",
    "SheetField",
    "attested_position",
    "extract_state",
    "normalise_subject",
    "parse_sheet",
    "record_id_for",
    "sheet_for",
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
