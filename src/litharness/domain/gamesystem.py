"""The game system a book runs on, and one character's position in it.

**What was missing was never a vocabulary.** `plan/first-principles-litrpg-core.md` §2 says the
pipeline has "no game system object anywhere", and the obvious reading of that is that the state
model cannot express one. Measured against the model, that reading is wrong twice over. §113
built the ladder — `precedes`, `stands_at`, `evaluates`, with the rung's number derived by
`rung_index` and never stored. §114 built the inventory — the `capability` role and the
`can_do` / `requires` / `taught_by` / `costs` edges. And `system` has been a member of
`worlds.ENTITY_ROLES` the whole time. Two thirds of a game system were already declarable, and
what no world ever declared was the thing that *owns* them.

So this module adds three predicates and reuses two value slots that were already free:

- `worlds.GOVERNED_BY` binds a ladder or an ability to a named system. This is the occupant the
  brief §2 asks for. Its argument is that "ranks need an issuer, so the Architect mints guilds",
  and that "subtraction cannot fix this; only an occupant can" — so the fix is not a clause
  forbidding institutions. `recognized_by` stays exactly where it was, and a world can now say
  that a guild recognises where you stand while the system grants what you can do. Those are
  different facts about different objects and they no longer have to share one ladder.
- `MAGNITUDE_SCALE` and `SYSTEM_DIGEST` configure how a system is written down rather than
  stating anything about the world, so they are configuration in `extraction`'s sense and must
  never reach a context packet.
- The **value slot on a `can_do` edge** carries how far one holder has taken one capacity. It
  was free: `worlds.capabilities_of` reads `object_ref` and ignores the value, and the shipped
  projection sentence is "sera can do cap_walk_between" with no number in it.
- The **value slot on a `requires` edge** carries the magnitude a prerequisite must reach. It
  was free for the same reason, and it is what finally makes `worlds.COMPARATORS`' `threshold`
  a comparator something computes with.

**§114.6 refused the magnitude, and the refusal was reserved to the operator** — "the magnitude
half is refused and the operator's to overturn". So the authority for what follows is not this
module's argument and not a checklist an agent satisfied. It is the operator's read-8 directive,
verbatim: *"The abilities progression and stat sheets are missing, i'm not feeling like i'm
reading litrpg at all. The numbers that do come up, come up in cotext they shouldn't come up...
describing days events etc instead of abilities"*, followed by their commission of this redesign.
That is the operator putting numbers onto abilities, which is the thing §114.6 held back.

§114.6 also named three conditions any overturn would have to satisfy, and those are answered
here as **evidence that the overturn is safe**, never as the permission for it — the distinction
matters for every future refusal carrying the same reservation (stage-0 §160):

1. *The number attaches to a capacity and never to a person.* Every integer in this module names
   one ability. There is no total, no average, no aggregate and no "Level N": nothing here
   returns a number that describes a person, and `test_no_number_describes_the_person` pins that
   by walking the module's own public surface rather than by asserting about one function.
2. *Something computes with it.* `_needs_met` compares a holder's magnitudes against the
   thresholds on `requires` edges, and that comparison is what makes an advancement legal or
   illegal. The number is load-bearing before it is ever printed.
3. *§113 is reconciled in the ledger rather than worked around.* A rung says **where you stand**:
   one per ladder, ordinal, named, worn where other people read it. A magnitude says **how far
   one capacity has been taken**: one per held ability, and it appears nowhere but the sheet.
   §114 already pinned that the inventory is a set and the ladder is a position; the magnitude is
   a depth on one member of that set, which is a third thing and not a second numbering of
   either. Stage-0 §160 records the overturn in place on §114.6.

**Nothing in this module is rendered into a call.** It emits ids, labels, integers, state records
and complaint sentences. There is no prompt text here, no adjective about how progress should
read, and no example line — §138's finding is that a permission overproduces what it names, and
the surest way to have a rejected sheet copied is to write it down as an example.

**No model ranks anything here** (§61(5)). `legal_moves` returns what is arithmetically
available, in declaration order; `check_draw` returns complaints about a draw's own coherence.
There is no scoring function, no comparison between two systems, and no notion of a better one.

**A sheet change is an event, and it needed no new event type.** Because `worlds.record_id_for`
hashes the value slot, a magnitude that moves produces a *new* record rather than an edited one,
which is §11's prohibition kept by construction. State records already emit
`StateRecordsAccepted` in the transaction that writes them, so the event exists; `EventType` is
pinned to the contract's enum and gains no member.

**Known limitation, named rather than fixed.** `extraction` mints a `status_snapshot` when it
reads a status line back out of prose, and a snapshot minted that way could disagree with the
`can_do` edges this module treats as canonical. `integrity.detect_contradictions` groups by
`(subject, predicate, order_key)` and will not see it, because the two facts sit under different
predicates. Reconciling them is a detector, and §160 declares no detector.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from hashlib import sha256

import litharness_contracts as lc

from litharness.domain import state as state_mod
from litharness.domain import worlds as worlds_mod
from litharness.domain.events import payload_digest

# --------------------------------------------------------------------------- the vocabulary

#: What a system's magnitudes are called and how high they run, as an object on the system
#: subject: `{"label": "Depth", "maximum": 9}`.
#:
#: **Configuration, not a world fact.** It says how this book writes its numbers down, the way
#: `extraction.SHEET_PREDICATE` says how it writes its status line down, and
#: `extraction.CONFIGURATION_PREDICATES` exists because a record shaped for a machine that
#: reaches a prompt is a defect with a measured instance behind it.
MAGNITUDE_SCALE = "magnitude_scale"

#: The content digest of the definition this book's sheets are positions in.
#:
#: **Stored, although it is derivable, and the reason is drift rather than convenience.** The
#: records *are* the definition, so a single later `world declare` on the system subject would
#: redefine the system every existing sheet is a position in, silently and with nothing to
#: compare against. A stored digest makes that a question a reader can ask. It is deliberately
#: not the mechanism that *prevents* the edit — there is no `world retract` (serial pilot 14
#: §10), so preventing it is not this module's to offer, and claiming otherwise would be worse
#: than recording the drift.
SYSTEM_DIGEST = "system_digest"

#: Predicates that configure how a system is written down rather than stating anything about the
#: world. `domain/extraction.py` owns the same idea for the status sheet and the graph line; this
#: is the pair a context packet must never carry.
CONFIGURATION_PREDICATES = frozenset({MAGNITUDE_SCALE, SYSTEM_DIGEST})

#: Named so a later change to a system's grammar is a visible version bump rather than a silent
#: reread, and deliberately its own family: `worlds.REGISTRY_VERSION` marks an Architect's
#: proposal about a world and `extraction.REGISTRY_VERSION` marks something read off a page, and
#: a reader that could not tell a minted system from either would be worth less than one that
#: says nothing.
REGISTRY_VERSION = "litharness.gamesystem.v0"

#: The status line's column for the rung, and the one column that is not an ability.
#:
#: **It carries the rung's derived *index*, not its name, and that is forced rather than
#: chosen.** `extraction`'s field pattern is `(?P<name>\\d+)` — digits only — so a named outfit
#: cannot ride a status line at all. The name is not lost: it rides the graph line
#: (`stands_at` / `parse_graph_line`), which is the surface built for exactly that in §113. The
#: operator's "ranks with named outfits" is satisfied by the pair of surfaces, and a design that
#: tried to put the name on the sheet would have had to widen a parser to do it.
RANK_KEY = "rank"

# --------------------------------------------------------------------------- what a draw must be

#: **The floor is what makes it a graph rather than a list, and the ceiling is the width of a
#: line a reader reads.** Neither is a quality bar and neither was arrived at by measuring
#: systems, because there is no distribution of systems to measure and no ordering over them —
#: `check_draw` says so in its own docstring. The ceiling is arithmetic about a rendered line:
#: every ability is a column, so eight abilities plus the rung is a nine-column line, and past
#: that the furniture stops being legible as furniture.
MIN_ABILITIES = 5
MAX_ABILITIES = 8

#: Three rungs, because a two-rung ladder is a switch and `rung_index`'s number has nowhere to go.
MIN_RANKS = 3

#: A magnitude of 1 is "held", so a maximum of 1 is a system where nothing can deepen and the
#: number is a decoration — which is the exact word §114.6 used for a magnitude nothing computes
#: with. The ceiling keeps a column one or two digits wide.
MIN_SCALE_MAXIMUM = 2
MAX_SCALE_MAXIMUM = 99

#: What may not appear inside a printed column label. A digit, because the field pattern reads
#: `label<space>digits` and a digit inside a label is a parser ambiguity nobody would enjoy
#: debugging; a pipe, because the pipe separates columns; an underscore, because a label is
#: printed prose and an id is not.
#:
#: **Written as a prohibition rather than as an allowed-character class, and that is a bug's
#: fault.** The first version was `^[^\\W\\d_][\\w' ]{0,23}$`, which reads as "a letter, then
#: letters, apostrophes and spaces" and is not: `\\w` contains digits, so `Tier 2` passed the
#: check meant to exclude exactly it. Naming what is forbidden cannot make that mistake.
_LABEL_FORBIDS = re.compile(r"[\d|_]")

#: A label has to fit beside its number on a line somebody reads.
LABEL_CHARS = 24


def _printable_label(text: str) -> bool:
    """Whether this can be a status line's column label."""
    return (
        bool(text.strip())
        and len(text) <= LABEL_CHARS
        and text[:1].isalpha()
        and not _LABEL_FORBIDS.search(text)
    )


class MalformedSystem(Exception):
    """A system definition this module cannot mean what it says.

    Raised rather than defaulted, for `extraction.MalformedSheet`'s reason: a system that
    silently fell back to something else would produce a book that looks seeded, renders a line,
    and is a position in a definition nobody drew.
    """


class IllegalAdvance(Exception):
    """A move this sheet cannot make.

    Every reason is arithmetic or membership — an unmet threshold, a magnitude already at its
    maximum, a rung with nothing above it, an ability the system does not declare. None of them
    is a judgment about whether the move would be *good*, and there is no path in this module
    that produces one.
    """


# --------------------------------------------------------------------------- the definition


@dataclass(frozen=True, slots=True)
class Need:
    """One prerequisite: something that must be reached before an ability can be gained.

    `ref` is an ability id or a rank id. §114 already established that those are the two, and
    that they meet at exactly this edge: `worlds.REQUIRES`' docstring says a capability may need
    another capability *or a rung* first. The threshold is what §160 adds, and it is the reason
    the comparator `threshold` now has arithmetic behind it.

    A threshold on a rank need is meaningless — a rung is a position, not a depth — so
    `check_draw` refuses one rather than ignoring it. Ignoring it would let a draw say something
    precise that nothing honours.
    """

    ref: str
    threshold: int = 1


@dataclass(frozen=True, slots=True)
class Ability:
    """One named thing a person can do, as the system declares it.

    `costs` and `manifests_as` are facts about the world in the register `worlds._record_sentence`
    already uses — what is so, never an instruction about how to write it. They are optional
    because a system may leave them to the world, and required of nothing here.
    """

    ability_id: str
    name: str
    needs: tuple[Need, ...] = ()
    costs: str | None = None
    manifests_as: str | None = None

    def __post_init__(self) -> None:
        """Prerequisites are held in a canonical order. See `SystemDef.__post_init__`."""
        object.__setattr__(
            self, "needs", tuple(sorted(self.needs, key=lambda need: need.ref))
        )


@dataclass(frozen=True, slots=True)
class Rank:
    """One rung, with the name it is worn under.

    **No index field, and its absence is §113's rule rather than an omission.** A rung's number
    is its place in the declared chain, computed when asked; an integer stored beside the chain
    is a second answer to "which rung is third" and the two eventually disagree. Here the place
    is the tuple position in `SystemDef.ranks`, so there is nothing to keep in agreement.
    """

    rank_id: str
    name: str


@dataclass(frozen=True, slots=True)
class Scale:
    """What this system's magnitudes are called, and how high they run."""

    label: str
    maximum: int


@dataclass(frozen=True, slots=True)
class Column:
    """One column of the status line this system renders, as plain data.

    **This is deliberately not an `extraction.SheetField`, and the reason is the import graph.**
    `genre` imports `extraction`, so if this module imported `extraction` and `extraction`
    imported this one to render a sheet, the cycle would close. Handing out `(name, label)` pairs
    lets the render side build its own `SheetField`s and keeps the arrow pointing one way:
    `extraction` may import `gamesystem`, never the reverse.
    """

    name: str
    label: str


@dataclass(frozen=True, slots=True)
class SystemDef:
    """The system one book runs on: an ability graph, a named ladder, and one scale.

    A book may run several of these or none. **None is a legal world** — the operator's model
    names crafting as a case with no system — and `systems_of` returning an empty tuple is that
    world, not a failure. What is not legal is a *declared* system that a sheet cannot be a
    position in, which is what `check_draw` is for.

    Immutable, and content-addressed by `digest`: a changed system is a different system, and the
    revision it replaces stays readable rather than being edited under the sheets that cite it.
    """

    system_id: str
    name: str
    criterion: str
    rank_label: str
    ranks: tuple[Rank, ...]
    abilities: tuple[Ability, ...]
    scale: Scale

    def __post_init__(self) -> None:
        """Abilities are held in id order, and the reason is a round trip that must close.

        **Measured on the first end-to-end run of this module**: a system written down and read
        back produced a *different digest*, because `records_for` writes ability records that
        `systems_of` can only return in sorted order, while the draw had declared them in
        whatever order it chose. Column order is part of what a digest means — a relabelled or
        reordered line renders differently out of the same numbers — so the round trip either
        normalises or the digest is a lie about identity.

        Normalising is the fix rather than storing the declared order, and that is this
        repository's standing rule applied once more: a stored order beside a derivable one is a
        second answer to "which column is third", and the two eventually disagree. What is lost
        is a drawer's ability to choose which column comes first, which is cosmetic; what is
        kept is that a system read back out of canon **is** the system that was drawn.

        The ranks are deliberately NOT sorted. Their order is the ladder itself, it carries the
        rung's number, and `worlds.ladder_of` recovers exactly it from the `precedes` chain.
        """
        object.__setattr__(
            self,
            "abilities",
            tuple(sorted(self.abilities, key=lambda ability: ability.ability_id)),
        )

    @property
    def digest(self) -> str:
        """Content-derived over everything that changes what a sheet means.

        The name and the labels are in the material as well as the structure, because a system
        whose columns were relabelled renders a different line out of the same numbers, and a
        digest that called those two revisions equal would be answering a question nobody asked.
        """
        material = payload_digest(
            {
                "id": self.system_id,
                "name": self.name,
                "criterion": self.criterion,
                "rank_label": self.rank_label,
                "ranks": [[rank.rank_id, rank.name] for rank in self.ranks],
                "abilities": [
                    [
                        ability.ability_id,
                        ability.name,
                        [[need.ref, need.threshold] for need in ability.needs],
                        ability.costs,
                        ability.manifests_as,
                    ]
                    for ability in self.abilities
                ],
                "scale": [self.scale.label, self.scale.maximum],
            }
        )
        return f"sys-{sha256(material.encode()).hexdigest()[:24]}"

    @property
    def columns(self) -> tuple[Column, ...]:
        """The status line's columns: the rung, then every ability in declaration order.

        **Every ability, including the ones nobody holds yet, and that is the design rather than
        a fallback.** An unheld ability sits at 0 where the reader can see it, which is the
        operator's own 2026-08-25 direction — "omg this magic would be so cool, I wonder what I
        would pick" — expressed as a number instead of as an adjective. It also keeps the line's
        shape constant for a whole book, which it has to be: a book declares one `status_sheet`,
        not one per scene.
        """
        return (
            Column(RANK_KEY, self.rank_label),
            *(Column(ability.ability_id, ability.name) for ability in self.abilities),
        )

    @property
    def value_keys(self) -> tuple[str, ...]:
        return tuple(column.name for column in self.columns)

    @property
    def ability_ids(self) -> tuple[str, ...]:
        return tuple(ability.ability_id for ability in self.abilities)

    @property
    def rank_ids(self) -> tuple[str, ...]:
        return tuple(rank.rank_id for rank in self.ranks)

    def ability(self, ability_id: str) -> Ability:
        for ability in self.abilities:
            if ability.ability_id == ability_id:
                return ability
        raise IllegalAdvance(
            f"{ability_id} is not an ability of {self.system_id}; this system declares "
            f"{', '.join(self.ability_ids)}"
        )

    def rank_index(self, rank_id: str) -> int:
        """A rung's 1-based place, counting from the bottom. `worlds.rung_index`' rule, in a
        definition that holds its own chain rather than reading one out of records."""
        return self.rank_ids.index(rank_id) + 1

    def sheet_declaration(self) -> dict[str, object]:
        """The `status_sheet` value this system implies, ready to declare.

        **The system settles the sheet, and the alternative was measured to fail silently.**
        Track 4 drove it: `extraction.sheet_for` abstains to the default when a book declares
        more than one sheet, so two independent declarations do not error — they quietly restore
        the very column set the operator rejects. One derivation cannot disagree with itself.
        """
        return {
            "fields": [
                {"name": column.name, "label": column.label} for column in self.columns
            ]
        }


# --------------------------------------------------------------------------- one position in it


@dataclass(frozen=True, slots=True)
class CharacterSheet:
    """Where one character stands in one system, at one moment.

    Immutable: an advancement returns a new sheet and leaves this one alone, so a caller holding
    the before-state still holds it after. That is what lets `Advancement` carry both.

    `visible_to` is the character ids this sheet is readable by, and it is `pov_visibility`'s
    vocabulary rather than a new one. Empty means objective — everyone's packet may carry it.
    Non-empty is the hook's shape (2026-08-22: the exception is *one person's*), and
    `state.visible_to` already enforces the direction where it matters, including that an unknown
    POV does not satisfy a restriction.
    """

    system: SystemDef
    character: str
    rank_id: str
    magnitudes: tuple[tuple[str, int], ...]
    visible_to: tuple[str, ...] = ()

    @property
    def system_id(self) -> str:
        return self.system.system_id

    def magnitude(self, ability_id: str) -> int:
        for held_id, value in self.magnitudes:
            if held_id == ability_id:
                return value
        return 0

    def holds(self, ability_id: str) -> bool:
        """Held means a magnitude of at least 1. **0 is the whole of "not held"**, which is why
        there is no separate set of held ids to keep in agreement with the numbers."""
        return self.magnitude(ability_id) >= 1

    def snapshot(self) -> dict[str, int]:
        """The `status_snapshot` mapping: the rung's index, then every ability's magnitude.

        This is the value `extraction.render_status_line` formats, the value
        `speaks_system_voice` requires to be a `Mapping` since §158, and the value the floor
        reads. Deriving it here rather than storing it is the same rule `Rank` follows.
        """
        values = {RANK_KEY: self.system.rank_index(self.rank_id)}
        for ability_id in self.system.ability_ids:
            values[ability_id] = self.magnitude(ability_id)
        return values


class AdvanceKind(StrEnum):
    """The three moves a sheet can make. Closed, and small on purpose: a beat names one of
    these, and a vocabulary that grew would be a vocabulary a beat has to choose within."""

    GAIN = "gain"
    DEEPEN = "deepen"
    RISE = "rise"


@dataclass(frozen=True, slots=True)
class Move:
    """One advancement that is available. `ability_id` is `None` for a rise."""

    kind: AdvanceKind
    ability_id: str | None = None
    rank_id: str | None = None


@dataclass(frozen=True, slots=True)
class Furniture:
    """What the page must show when the sheet changes, as data.

    **Data and not a sentence, and the boundary is §138's.** This module says which columns moved
    and what they now read; it says nothing about how that should land, because an adjective here
    would be an affirmative prose clause reaching every scene that carries a beat. The render side
    builds `extraction.SheetField`s from `columns` and calls `render_status_line`.
    """

    subject: str
    values: Mapping[str, int]
    moved: tuple[str, ...]
    columns: tuple[Column, ...]


@dataclass(frozen=True, slots=True)
class Advancement:
    """One change to a sheet: the new sheet, what moved, and the records that write it down.

    The records are `PROPOSED`. That is `worlds.world_record`'s default and it is the rail rather
    than a detail — a drawn system and a position in it both reach canon through the recorded,
    person-gated `world accept`, and a constructor that defaulted the other way would make the
    rail something every call site has to remember.
    """

    kind: AdvanceKind
    sheet: CharacterSheet
    moved: tuple[str, ...]
    before: Mapping[str, int]
    after: Mapping[str, int]
    records: tuple[lc.StateRecord, ...] = field(default_factory=tuple)

    @property
    def furniture(self) -> Furniture:
        return Furniture(
            subject=self.sheet.character,
            values=self.after,
            moved=self.moved,
            columns=self.sheet.system.columns,
        )


# --------------------------------------------------------------------------- drawing a system


def check_draw(system: SystemDef) -> tuple[str, ...]:
    """Deterministic complaints about a drawn system's own coherence. Empty means nothing to say.

    **Every check is membership or arithmetic**, exactly as `worlds.validate`'s are, and for the
    same reason: there is no quality ordering over systems in this project and inventing one here
    would be the frame `plan/director-role.md` §0 records three burials of. Nothing here asks
    whether a system is interesting, balanced, or a good fit for a book.

    **One check is a delta from §114 and is named as one.** §114 forbids gating on
    `worlds.requirement_depth`, because a world's inventory may legitimately be flat and refusing
    a flat one would be a judgment about worlds. That stands, untouched. The "at least one
    prerequisite edge" check below is not that check: it is on the `SystemDef` object drawn under
    §160's own contract, where a definition with no edges is not an ability *graph* — the shape
    the operator specified — but a list. A world's §114 inventory is not read by it and not
    affected by it.
    """
    complaints: list[str] = []

    if not system.system_id.isidentifier():
        complaints.append(
            f"the system id {system.system_id!r} is not usable as an identifier"
        )
    if not system.name.strip():
        complaints.append("a system needs a name")
    if not system.criterion.strip():
        complaints.append(
            "a system needs the criterion its ladder is ordered by; without one the "
            "`precedes` edges belong to every ladder in the world at once"
        )
    if not _printable_label(system.rank_label):
        complaints.append(
            f"the rung column's label {system.rank_label!r} cannot be printed on a status "
            "line: a label is letters, spaces and apostrophes, at most 24 characters, and "
            "carries no digit"
        )

    # --- the ladder
    if len(system.ranks) < MIN_RANKS:
        complaints.append(
            f"this system declares {len(system.ranks)} rung(s); a ladder needs at least "
            f"{MIN_RANKS}, because a rung's number is its place in a chain and a chain of two "
            "is a switch"
        )
    if len(set(system.rank_ids)) != len(system.rank_ids):
        complaints.append("two rungs share an id, so a standing could not say which is meant")
    for rank in system.ranks:
        if not rank.name.strip():
            complaints.append(f"the rung {rank.rank_id} is worn under no name")
    if len({rank.name.strip() for rank in system.ranks}) != len(system.ranks):
        complaints.append(
            "two rungs are worn under the same name, so a rise between them shows nothing"
        )

    # --- the graph
    if not MIN_ABILITIES <= len(system.abilities) <= MAX_ABILITIES:
        complaints.append(
            f"this system declares {len(system.abilities)} abilities; a drawn system carries "
            f"{MIN_ABILITIES} to {MAX_ABILITIES}, the upper bound being the number of columns a "
            "status line can print and not a claim about how many abilities a system should have"
        )
    if len(set(system.ability_ids)) != len(system.ability_ids):
        complaints.append("two abilities share an id, so a column could not say which is meant")
    for ability in system.abilities:
        if not ability.ability_id.isidentifier():
            complaints.append(
                f"the ability id {ability.ability_id!r} is not usable as an identifier, so it "
                "cannot be a column of the status line this system renders"
            )
        if ability.ability_id == RANK_KEY:
            complaints.append(
                f"an ability may not be called {RANK_KEY!r}: that column carries the rung"
            )
        if not _printable_label(ability.name):
            complaints.append(
                f"the ability {ability.ability_id}'s label {ability.name!r} cannot be printed "
                "on a status line: a label is printable prose, at most 24 characters, and "
                "carries no digit"
            )

    known_abilities = set(system.ability_ids)
    known_ranks = set(system.rank_ids)
    edges = 0
    for ability in system.abilities:
        for need in ability.needs:
            edges += 1
            if need.ref in known_ranks:
                if need.threshold != 1:
                    complaints.append(
                        f"{ability.ability_id} needs the rung {need.ref} at "
                        f"{need.threshold}; a rung is a position and has no depth to reach"
                    )
                continue
            if need.ref not in known_abilities:
                complaints.append(
                    f"{ability.ability_id} needs {need.ref}, which this system declares "
                    "neither as an ability nor as a rung"
                )
                continue
            if need.ref == ability.ability_id:
                complaints.append(f"{ability.ability_id} is its own prerequisite")
            if not 1 <= need.threshold <= system.scale.maximum:
                complaints.append(
                    f"{ability.ability_id} needs {need.ref} at {need.threshold}, which is "
                    f"outside this system's scale of 1 to {system.scale.maximum}"
                )
    if edges == 0 and len(system.abilities) >= MIN_ABILITIES:
        complaints.append(
            "no ability requires another, so this is a list rather than a graph; see this "
            "function's docstring for why that is not §114's refused depth gate"
        )
    if _cycle(system):
        complaints.append(
            "the prerequisites run in a cycle, so no order of gaining them exists"
        )

    # --- the scale
    if not _printable_label(system.scale.label):
        complaints.append(
            f"the scale's label {system.scale.label!r} is not a printable label"
        )
    if not MIN_SCALE_MAXIMUM <= system.scale.maximum <= MAX_SCALE_MAXIMUM:
        complaints.append(
            f"this system's magnitudes run to {system.scale.maximum}; a drawn scale runs to "
            f"{MIN_SCALE_MAXIMUM}..{MAX_SCALE_MAXIMUM}, below which nothing can deepen and the "
            "number is a decoration"
        )

    # --- can a book start?
    if not complaints and not _openers(system):
        complaints.append(
            "no ability can be held at the first rung, so this system has no starting sheet "
            "and a book on it could never speak system voice"
        )

    if len(set(system.value_keys)) != len(system.value_keys):
        complaints.append("two columns share a value key, so the status line cannot be parsed")

    return tuple(complaints)


def _cycle(system: SystemDef) -> bool:
    """Whether the ability prerequisites contain a cycle. Rank needs are not edges of this graph.

    `worlds.requirement_depth` deliberately tolerates a cycle and reports the longest acyclic
    path, because guessing which edge to cut would be that function inventing a fact. Here the
    question is different and answerable: a drawn system whose prerequisites cycle cannot be
    entered at all, and saying so is a complaint rather than a guess.
    """
    onward = {
        ability.ability_id: [
            need.ref
            for need in ability.needs
            if need.ref in set(system.ability_ids)
        ]
        for ability in system.abilities
    }
    walking: set[str] = set()
    done: set[str] = set()

    def visit(node: str) -> bool:
        if node in walking:
            return True
        if node in done:
            return False
        walking.add(node)
        found = any(visit(nxt) for nxt in onward.get(node, ()))
        walking.discard(node)
        done.add(node)
        return found

    return any(visit(node) for node in onward)


def _openers(system: SystemDef) -> tuple[str, ...]:
    """The abilities holdable at the first rung: no ability prerequisites, no higher rung needed.

    This is what a starting sheet holds, and the reason `check_draw` refuses a system with none:
    a book whose protagonist can hold nothing on page one has a sheet of zeroes, which clears no
    floor and asks the writer for nothing.
    """
    first = system.rank_ids[0] if system.ranks else None
    holdable: list[str] = []
    for ability in system.abilities:
        if any(need.ref in set(system.ability_ids) for need in ability.needs):
            continue
        if any(need.ref != first for need in ability.needs if need.ref in set(system.rank_ids)):
            continue
        holdable.append(ability.ability_id)
    return tuple(holdable)


def starting_sheet(
    system: SystemDef, character: str, *, visible_to: Sequence[str] = ()
) -> CharacterSheet:
    """The entry state a drawn system implies: the first rung, and its openers at 1.

    **Derived rather than asked for, and that is the fix for a measured defect.** §158's repair
    left `world declare <subject> status_snapshot --value '{...}'` as the one reachable seeding
    path, which means a seed asks a model for a mapping and hopes it agrees with the system.
    Track 4 measured the failure mode that follows: `extraction.sheet_for` abstains to the
    default when a book declares more than one sheet, so a disagreement does not error — it
    quietly reinstates the column set the operator rejects. A derivation has nothing to disagree
    with.
    """
    if not system.ranks:
        raise MalformedSystem(f"{system.system_id} declares no rungs, so it has no first one")
    openers = set(_openers(system))
    return CharacterSheet(
        system=system,
        character=character,
        rank_id=system.rank_ids[0],
        magnitudes=tuple(
            (ability_id, 1 if ability_id in openers else 0)
            for ability_id in system.ability_ids
        ),
        visible_to=tuple(visible_to),
    )


# --------------------------------------------------------------------------- advancing a sheet


def _needs_met(sheet: CharacterSheet, ability: Ability) -> tuple[str, ...]:
    """Which of an ability's prerequisites this sheet does not meet, as reasons. Empty means met.

    **This is the arithmetic §114.6 asked for.** A threshold that nothing compared against was
    the "decoration" that entry refused; here the comparison is what decides whether a move is
    legal, so the number does work before it is ever printed.
    """
    unmet: list[str] = []
    system = sheet.system
    for need in ability.needs:
        if need.ref in set(system.rank_ids):
            if system.rank_index(sheet.rank_id) < system.rank_index(need.ref):
                unmet.append(
                    f"{ability.ability_id} needs the rung {need.ref}, and {sheet.character} "
                    f"stands at {sheet.rank_id}"
                )
            continue
        have = sheet.magnitude(need.ref)
        if have < need.threshold:
            unmet.append(
                f"{ability.ability_id} needs {need.ref} at {need.threshold}, and "
                f"{sheet.character} has it at {have}"
            )
    return tuple(unmet)


def legal_moves(sheet: CharacterSheet) -> tuple[Move, ...]:
    """Every advancement arithmetically available to this sheet, in declaration order.

    **Declaration order, and no ordering of any other kind** (§61(5)). This returns what is
    possible; it does not say which is best, most dramatic or most earned, and there is no
    function in this module that does. A caller that wants one of them chooses by its own rule —
    a schedule, a plan, a beat — and never by asking this module to rank.
    """
    moves: list[Move] = []
    system = sheet.system
    for ability in system.abilities:
        held = sheet.magnitude(ability.ability_id)
        if held == 0:
            if not _needs_met(sheet, ability):
                moves.append(Move(AdvanceKind.GAIN, ability_id=ability.ability_id))
        elif held < system.scale.maximum:
            moves.append(Move(AdvanceKind.DEEPEN, ability_id=ability.ability_id))
    index = system.rank_index(sheet.rank_id)
    if index < len(system.ranks):
        moves.append(Move(AdvanceKind.RISE, rank_id=system.rank_ids[index]))
    return tuple(moves)


def _advanced(
    sheet: CharacterSheet,
    kind: AdvanceKind,
    *,
    at: str,
    rank_id: str | None = None,
    ability_id: str | None = None,
    magnitude: int | None = None,
) -> Advancement:
    """The one place a new sheet, its moved keys and its records are built together.

    Three entry points share it so the three moves cannot drift in what they write down — the
    defect `genre.with_beat` avoids by the same means, one function two call sites.
    """
    before = sheet.snapshot()
    if kind is AdvanceKind.RISE:
        assert rank_id is not None
        after_sheet = CharacterSheet(
            system=sheet.system,
            character=sheet.character,
            rank_id=rank_id,
            magnitudes=sheet.magnitudes,
            visible_to=sheet.visible_to,
        )
    else:
        assert ability_id is not None and magnitude is not None
        after_sheet = CharacterSheet(
            system=sheet.system,
            character=sheet.character,
            rank_id=sheet.rank_id,
            magnitudes=tuple(
                (held_id, magnitude if held_id == ability_id else value)
                for held_id, value in sheet.magnitudes
            ),
            visible_to=sheet.visible_to,
        )
    after = after_sheet.snapshot()
    moved = tuple(key for key in after if after[key] != before.get(key))

    records: list[lc.StateRecord] = []
    if kind is AdvanceKind.RISE:
        records.append(
            worlds_mod.world_record(
                sheet.character,
                worlds_mod.STANDS_AT_PREDICATE,
                value=sheet.system.criterion,
                object_ref=rank_id,
                order_key=at,
                pov_visibility=sheet.visible_to,
            )
        )
    else:
        records.append(
            worlds_mod.world_record(
                sheet.character,
                worlds_mod.CAN_DO,
                value=magnitude,
                object_ref=ability_id,
                order_key=at,
                pov_visibility=sheet.visible_to,
            )
        )
    # **Only what changed, plus the line it renders.** The first version rewrote the whole
    # sheet at every advancement, and running it showed why that is wrong: `worlds.record_id_for`
    # keys on `(subject, predicate, object_ref, value)` and **not** on the order key — unlike
    # `extraction.record_id_for`, which includes it deliberately — so an unchanged holding
    # rewritten at a later position is the *same record id*, and `record_state_records` is
    # `INSERT OR IGNORE`. The rewrite was therefore silently dropped, which is harmless and
    # completely illegible: the record set claimed to restate the sheet and did not. Writing the
    # one edge that moved says what actually happened, and the unchanged holdings keep the
    # position they were established at, which is what they mean.
    records.append(_snapshot_record(after_sheet, at=at))
    return Advancement(
        kind=kind,
        sheet=after_sheet,
        moved=moved,
        before=before,
        after=after,
        records=tuple(records),
    )


def gain(sheet: CharacterSheet, ability_id: str, *, at: str) -> Advancement:
    """Take an ability from 0 to 1. Raises `IllegalAdvance` when a prerequisite is unmet."""
    ability = sheet.system.ability(ability_id)
    if sheet.holds(ability_id):
        raise IllegalAdvance(
            f"{sheet.character} already holds {ability_id} at {sheet.magnitude(ability_id)}"
        )
    unmet = _needs_met(sheet, ability)
    if unmet:
        raise IllegalAdvance("; ".join(unmet))
    return _advanced(
        sheet, AdvanceKind.GAIN, at=at, ability_id=ability_id, magnitude=1
    )


def deepen(sheet: CharacterSheet, ability_id: str, *, at: str) -> Advancement:
    """Take a held ability one step further. Raises `IllegalAdvance` at 0 or at the maximum.

    Prerequisites are checked at `gain` and not re-checked here: they are the condition for
    having the ability at all, and re-asking would make a sheet's own past illegal whenever a
    world's declaration changed underneath it.
    """
    sheet.system.ability(ability_id)
    held = sheet.magnitude(ability_id)
    if held < 1:
        raise IllegalAdvance(
            f"{sheet.character} does not hold {ability_id}, so there is nothing to deepen"
        )
    if held >= sheet.system.scale.maximum:
        raise IllegalAdvance(
            f"{sheet.character} holds {ability_id} at {held}, which is this system's maximum"
        )
    return _advanced(
        sheet, AdvanceKind.DEEPEN, at=at, ability_id=ability_id, magnitude=held + 1
    )


def rise(sheet: CharacterSheet, *, at: str) -> Advancement:
    """Move to the next rung up. Raises `IllegalAdvance` at the top of the ladder.

    One rung, never two: which rung somebody reaches is the ladder's business and skipping is a
    fact about the world that nothing here is entitled to invent.
    """
    system = sheet.system
    index = system.rank_index(sheet.rank_id)
    if index >= len(system.ranks):
        raise IllegalAdvance(
            f"{sheet.character} stands at {sheet.rank_id}, the top rung of {system.criterion}"
        )
    return _advanced(sheet, AdvanceKind.RISE, at=at, rank_id=system.rank_ids[index])


# --------------------------------------------------------------------------- writing it down


def records_for(system: SystemDef) -> tuple[lc.StateRecord, ...]:
    """A drawn system as state records, all `PROPOSED`.

    **No story position anywhere in them, and that is a statement rather than an omission.** A
    system is what the world runs on; it does not happen at a scene. Positions belong to
    `records_for_sheet`, which writes where somebody stands and when.

    **No new storage.** `state_records` holds arbitrary `StateRecord` JSON, so a system is
    records and a sheet change is a record; §160 declares no table and takes no migration
    number. That is not a saving so much as a constraint honoured: a second home for a fact is
    the failure this repository has recorded more times than any other.

    Refuses a draw that `check_draw` complains about, rather than writing a system nothing can
    be a position in. `MalformedSheet`'s argument, one object along.
    """
    complaints = check_draw(system)
    if complaints:
        raise MalformedSystem("; ".join(complaints))

    records = [
        worlds_mod.world_record(
            system.system_id, worlds_mod.ENTITY_ROLE_PREDICATE, value="system"
        ),
        worlds_mod.world_record(system.system_id, "is_a", value=system.name),
        worlds_mod.world_record(
            system.system_id,
            MAGNITUDE_SCALE,
            value={"label": system.scale.label, "maximum": system.scale.maximum},
        ),
        worlds_mod.world_record(system.system_id, SYSTEM_DIGEST, value=system.digest),
        # **The system writes its own status line down, in the same function that writes the
        # system.** Leaving this to the seed path was the first design and it was wrong for the
        # reason `sheet_declaration` records: `extraction.sheet_for` abstains to the default
        # when a book declares more than one sheet, so two independent writers of this record
        # do not collide loudly — the book quietly renders a line it never chose. One function
        # writes both, so there is nothing for a second one to disagree with. The subject is
        # the system because `sheet_for` does not read the subject at all, and naming the
        # system is what makes the record legible to somebody reading canon by eye.
        worlds_mod.world_record(
            system.system_id, "status_sheet", value=system.sheet_declaration()
        ),
        worlds_mod.world_record(
            system.criterion, worlds_mod.TYPE_PREDICATE, value=worlds_mod.CRITERION
        ),
        # **The rung column's label is the criterion's own name**, not a field of the scale.
        # The criterion *is* the ladder, so the word a book counts rungs in is that subject's
        # name, and `is_a` is where every other name in this vocabulary already lives. Storing
        # it beside the magnitude scale instead would have put the ladder's vocabulary inside
        # the abilities' — two unrelated things in one record, and a reader would have to know
        # which half it wanted.
        worlds_mod.world_record(system.criterion, "is_a", value=system.rank_label),
        worlds_mod.world_record(
            system.criterion, worlds_mod.COMPARATOR_PREDICATE, value="ordinal"
        ),
        worlds_mod.world_record(
            system.criterion, worlds_mod.GOVERNED_BY, object_ref=system.system_id
        ),
    ]
    # The chain runs subject=lower, object=next-higher: `worlds.rank_order` builds `(lower,
    # higher)` out of `(subject, object_ref)` and `ladder_of` starts where nothing points. That
    # direction is read off the reader rather than off the docstring beside it, whose example
    # reads backwards in English (§152's class of defect, and the pair that does not fail loudly).
    for lower, higher in zip(system.ranks, system.ranks[1:], strict=False):
        records.append(
            worlds_mod.world_record(
                lower.rank_id,
                worlds_mod.PRECEDES_PREDICATE,
                value=system.criterion,
                object_ref=higher.rank_id,
            )
        )
    for rank in system.ranks:
        records.append(worlds_mod.world_record(rank.rank_id, "is_a", value=rank.name))
    for ability in system.abilities:
        records.append(
            worlds_mod.world_record(
                ability.ability_id, worlds_mod.ENTITY_ROLE_PREDICATE, value="capability"
            )
        )
        records.append(
            worlds_mod.world_record(ability.ability_id, "is_a", value=ability.name)
        )
        records.append(
            worlds_mod.world_record(
                ability.ability_id, worlds_mod.GOVERNED_BY, object_ref=system.system_id
            )
        )
        if ability.costs:
            records.append(
                worlds_mod.world_record(
                    ability.ability_id, worlds_mod.COSTS, value=ability.costs
                )
            )
        if ability.manifests_as:
            records.append(
                worlds_mod.world_record(
                    ability.ability_id,
                    worlds_mod.MANIFESTS_PREDICATE,
                    value=ability.manifests_as,
                )
            )
        for need in ability.needs:
            # No `order_key`, and `at` is deliberately not threaded here: a prerequisite is a
            # standing fact about the capability rather than about any occasion of acquiring it,
            # which is `worlds.REQUIRES`' own distinction from a reified `change`'s
            # `precondition`. A dated prerequisite would say the graph itself moved.
            records.append(
                worlds_mod.world_record(
                    ability.ability_id,
                    worlds_mod.REQUIRES,
                    value=need.threshold,
                    object_ref=need.ref,
                )
            )
    return tuple(records)


def records_for_sheet(
    sheet: CharacterSheet, *, at: str | None = None
) -> tuple[lc.StateRecord, ...]:
    """One position as state records: the standing, the holdings, and the rendered snapshot.

    **Three families written by one function, because they are one fact.** The `stands_at` and
    `can_do` edges are what the world knows — they feed the packet, `worlds.capabilities_of`,
    `worlds.standing_of` and the contradiction detector. The `status_snapshot` is the printed
    form of the same position, and it is what the floor reads and what
    `extraction.render_status_line` formats. Writing them apart is how they would come to
    disagree; writing them here is how they cannot.

    `at` is the story position. **Omit it for an entry state**, and that is correct rather than
    merely tolerated: `extraction.system_voice_example` selects with `(order_key or "") < at`, so
    a keyless snapshot sorts below every minted `s{n}` key and is found at every position — which
    is what "true before scene one" means. Every advancement passes its own key.
    """
    records = [
        worlds_mod.world_record(
            sheet.character,
            worlds_mod.STANDS_AT_PREDICATE,
            value=sheet.system.criterion,
            object_ref=sheet.rank_id,
            order_key=at,
            pov_visibility=sheet.visible_to,
        )
    ]
    for ability_id, magnitude in sheet.magnitudes:
        if magnitude >= 1:
            records.append(
                worlds_mod.world_record(
                    sheet.character,
                    worlds_mod.CAN_DO,
                    value=magnitude,
                    object_ref=ability_id,
                    order_key=at,
                    pov_visibility=sheet.visible_to,
                )
            )
    records.append(_snapshot_record(sheet, at=at))
    return tuple(records)


def _snapshot_record(sheet: CharacterSheet, *, at: str | None) -> lc.StateRecord:
    """The rendered form of one position, as the one record the floor and the renderer read.

    Its own function because both the seed and every advancement write one, and a status
    snapshot composed in two places is the shape §158's defect had: the floor read one thing and
    the ask rendered from another.
    """
    return worlds_mod.world_record(
        sheet.character,
        "status_snapshot",
        value=sheet.snapshot(),
        order_key=at,
        pov_visibility=sheet.visible_to,
    )


# --------------------------------------------------------------------------- reading it back


def systems_of(records: Sequence[lc.StateRecord]) -> tuple[SystemDef, ...]:
    """Every system this book declares, by id. Empty is a legal answer.

    **Several per world, or none.** The operator's model names both — several systems side by
    side, or a world that runs on crafting and has none — so an empty tuple is a world and not a
    failure. Callers that need a system say so themselves.

    Canon is not filtered here, matching `worlds.capabilities` and `worlds.entity_roles`: the
    Architect works on proposals before `world accept`, and filtering would report no system
    while one is being built. Callers that need canon filter first, as the floor does.
    """
    by_id: dict[str, SystemDef] = {}
    scales = {
        record.subject: record.value
        for record in records
        if record.predicate == MAGNITUDE_SCALE and isinstance(record.value, Mapping)
    }
    names = {
        record.subject: str(record.value)
        for record in records
        if record.predicate == "is_a" and isinstance(record.value, str)
    }
    governed: dict[str, str] = {}
    for record in records:
        if record.predicate == worlds_mod.GOVERNED_BY and record.object_ref:
            governed[record.subject] = record.object_ref

    for system_id in worlds_mod.entities_with_role(records, "system"):
        scale_value = scales.get(system_id)
        if not isinstance(scale_value, Mapping):
            continue
        label = str(scale_value.get("label", ""))
        maximum = scale_value.get("maximum")
        if not isinstance(maximum, int) or isinstance(maximum, bool):
            continue
        system = _assemble(
            records, system_id, Scale(label=label, maximum=maximum), names, governed
        )
        if system is not None:
            by_id[system_id] = system
    return tuple(by_id[key] for key in sorted(by_id))


def _assemble(
    records: Sequence[lc.StateRecord],
    system_id: str,
    scale: Scale,
    names: Mapping[str, str],
    governed: Mapping[str, str],
) -> SystemDef | None:
    """One system's ladder and graph, read off the world, given the scale it runs on.

    Split out of `systems_of` so that the accept-time completion (`completion_records`) assembles
    a drawn system through **exactly** the reader that will later read it back. Two assemblies
    would be two answers to "what did this world declare", and the digest would eventually
    disagree with the records it was minted from.
    """
    criteria = sorted(
        subject
        for subject, owner in governed.items()
        if owner == system_id and subject in worlds_mod.criteria(records)
    )
    if len(criteria) != 1:
        # Abstains for `extraction.sheet_for`'s reason: two ladders under one system is a
        # disagreement about which chain a sheet's rung column counts, and choosing would be
        # this module inventing which one the world meant.
        return None
    criterion = criteria[0]
    chain = worlds_mod.ladder_of(records, criterion)
    if not chain:
        return None
    ability_ids = [
        subject
        for subject, owner in sorted(governed.items())
        if owner == system_id and subject in set(worlds_mod.capabilities(records))
    ]
    abilities = tuple(
        Ability(
            ability_id=ability_id,
            name=names.get(ability_id, ability_id),
            needs=_needs_of(records, ability_id),
            costs=_first_value(records, ability_id, worlds_mod.COSTS),
            manifests_as=_first_value(records, ability_id, worlds_mod.MANIFESTS_PREDICATE),
        )
        for ability_id in ability_ids
    )
    return SystemDef(
        system_id=system_id,
        name=names.get(system_id, system_id),
        criterion=criterion,
        rank_label=names.get(criterion, "Rank"),
        ranks=tuple(Rank(rank_id=rank_id, name=names.get(rank_id, rank_id)) for rank_id in chain),
        abilities=abilities,
        scale=scale,
    )


def completion_records(
    records: Sequence[lc.StateRecord],
) -> tuple[tuple[lc.StateRecord, ...], tuple[str, ...]]:
    """Finish every system this world drew but could not declare, and say why one is unfinished.

    **The predicate a drawn system cannot reach, minted at the one act that is a person** (§165).
    `magnitude_scale` and `system_digest` are kept out of `world vocabulary` on purpose (§163.2):
    they are minted by `records_for` and never declared by hand, because a second declaration
    beside the drawn one is the two-writers hazard. The consequence went unnoticed until Serial
    Pilot 15 drew a system with an issuer, a six-rung ladder, six governed capabilities and a
    prerequisite graph, and `system_gap` reported *"this book declares no game system"* — every
    clause of it false about that world except the one that decided it. The Architect had no
    documented way to fill the slot, and nothing else was going to.

    `world accept` is where this runs, and that is what makes it minting rather than forging: a
    person ran the command, the structure being completed is the world's own, and this function
    invents no rung, no capability, no edge and no name.

    **The scale is read off the declared numbers, and a world that declared none gets a reason
    instead of a default.** `maximum` is the deepest magnitude the world has already put someone
    at (`can_do`) or asked for (`requires`), because a scale must at least contain the depths its
    own records assert. A world whose capabilities carry no number never expressed a depth at
    all — it is a held-or-not inventory — and calling that a scale of `MIN_SCALE_MAXIMUM` would
    invent the one dimension the world declined to have. The label is the system's own `is_a`
    name; it is never printed on a status line (`columns` prints the rung label and the ability
    names), so this reaches no page.

    **Only the two configuration predicates are returned**, filtered out of a full `records_for`
    draw rather than built separately, so `check_draw` runs and the digest is computed by the
    same path that will read it back. Everything else `records_for` mints — the ladder, the
    roles, the `governed_by` edges — the world already declared, and `status_sheet` is
    deliberately among the things not returned: a book that declared its own sheet would get a
    second one, `extraction.sheet_for` abstains to the generic line when there are two, and
    there is no retraction to undo it. That is `system_gap`'s own first branch, and completing a
    system into it would be this function causing the fault it exists to clear.
    """
    minted: list[lc.StateRecord] = []
    reasons: list[str] = []
    names = {
        record.subject: str(record.value)
        for record in records
        if record.predicate == "is_a" and isinstance(record.value, str)
    }
    governed = {
        record.subject: record.object_ref
        for record in records
        if record.predicate == worlds_mod.GOVERNED_BY and record.object_ref
    }
    declared = {
        record.subject
        for record in records
        if record.predicate == MAGNITUDE_SCALE and isinstance(record.value, Mapping)
    }
    for system_id in worlds_mod.entities_with_role(records, "system"):
        if system_id in declared:
            continue
        skeleton = _assemble(
            records, system_id, Scale(label="", maximum=0), names, governed
        )
        if skeleton is None:
            reasons.append(
                f"{system_id} holds the system role, and its ladder could not be read: a system "
                "needs exactly one criterion under `governed_by` and a `precedes` chain for it"
            )
            continue
        maximum = _declared_depth(records, skeleton.ability_ids)
        if maximum is None or maximum < MIN_SCALE_MAXIMUM:
            reasons.append(
                f"{system_id} declares no depth: nothing on its capabilities is held or required "
                f"past {MIN_SCALE_MAXIMUM - 1}, so this world says who holds what and never how "
                "far. A scale would be invented rather than read, so none is minted and the "
                "system gap stays open"
            )
            continue
        system = _assemble(
            records,
            system_id,
            Scale(label=names.get(system_id, system_id), maximum=maximum),
            names,
            governed,
        )
        assert system is not None
        try:
            drawn = records_for(system)
        except MalformedSystem as error:
            reasons.append(f"{system_id} is drawn but incoherent, so nothing was minted: {error}")
            continue
        minted.extend(
            record for record in drawn if record.predicate in CONFIGURATION_PREDICATES
        )
    return tuple(minted), tuple(reasons)


def _declared_depth(
    records: Sequence[lc.StateRecord], ability_ids: Sequence[str]
) -> int | None:
    """The deepest magnitude this world has declared on these capabilities, or `None` for none.

    Both slots §160 reused are read: `can_do`'s value is how far a holder has taken a capability,
    `requires`' is how far a prerequisite has to have been taken. A scale that did not contain
    both would be one `check_draw` refuses on the world's own numbers.
    """
    wanted = set(ability_ids)
    depths = [
        record.value
        for record in records
        if isinstance(record.value, int)
        and not isinstance(record.value, bool)
        and (
            (record.predicate == worlds_mod.CAN_DO and record.object_ref in wanted)
            or (record.predicate == worlds_mod.REQUIRES and record.subject in wanted)
        )
    ]
    return max(depths) if depths else None


def _first_value(
    records: Sequence[lc.StateRecord], subject: str, predicate: str
) -> str | None:
    for record in records:
        if (
            record.subject == subject
            and record.predicate == predicate
            and isinstance(record.value, str)
            and record.value.strip()
        ):
            return record.value
    return None


def _needs_of(records: Sequence[lc.StateRecord], ability_id: str) -> tuple[Need, ...]:
    """This ability's prerequisites, with their thresholds. Subject needs object.

    Direction read off `worlds.requirement_depth`, which walks onward from `subject` to
    `object_ref`, and off §114's shipped sentence "cap_price_unseen needs cap_read_a_seam first".
    A missing or non-integer value means a threshold of 1, which is what every `requires` record
    written before §160 means: held at all.
    """
    needs: list[Need] = []
    for record in records:
        if record.predicate != worlds_mod.REQUIRES or record.subject != ability_id:
            continue
        if not record.object_ref:
            continue
        threshold = (
            record.value
            if isinstance(record.value, int) and not isinstance(record.value, bool)
            else 1
        )
        needs.append(Need(ref=record.object_ref, threshold=max(1, threshold)))
    return tuple(sorted(needs, key=lambda need: need.ref))


def sheet_of(
    records: Sequence[lc.StateRecord],
    character: str,
    *,
    system: SystemDef | None = None,
    at: str | None = None,
) -> CharacterSheet | None:
    """Where this character stands, as of `at`, or `None` when the records do not say.

    **Read from the edges rather than from the snapshot, and the choice matters.** The
    `status_snapshot` is the printed form; the `stands_at` and `can_do` edges are what the world
    knows, and they are what `worlds.capabilities_of` and `worlds.standing_of` already read. A
    reader that took the snapshot instead would be a second answer to "what does this person
    hold", and the two would eventually disagree — which is the failure this repository has
    recorded against stored-versus-derived numbers every time it has come up.

    Canon only, because a position is a fact about the book and a `PROPOSED` one is a plan for
    later. The floor's rule, for the floor's reason: counting proposals would let a book satisfy
    a reader with its own schedule.
    """
    if system is None:
        found = systems_of(records)
        if len(found) != 1:
            return None
        system = found[0]

    def within(record: lc.StateRecord) -> bool:
        """Whether the book standing at `at` has reached the position this record states.

        **`key <= at` again, and the sheet is the worst place for it** (§167). A scheduled
        `stands_at` or `can_do` answered `'0350' <= 's1'` with `True`, so the character sheet a
        writer is shown would print the rank and the ability magnitudes the arc ends on. It
        reproduces on no store yet only because no book on disk has a declared system —
        §165.2's `completion_records` mints one at `world accept`, which is what makes this
        live rather than hypothetical. The un-keyed record is the opening state and reaches
        every position; a key in another space reaches none of them.
        """
        key = state_mod.order_key_of(record)
        if at is None or key is None:
            return True
        return state_mod.comparable(key, at) and key <= at

    standings = [
        record
        for record in records
        if record.predicate == worlds_mod.STANDS_AT_PREDICATE
        and record.subject == character
        and record.object_ref in set(system.rank_ids)
        and state_mod.is_canon(record)
        and within(record)
    ]
    if not standings:
        return None
    rank_id = max(
        standings, key=lambda record: (state_mod.order_key_of(record) or "")
    ).object_ref
    assert rank_id is not None

    magnitudes: list[tuple[str, int]] = []
    visible: set[str] = set()
    for ability_id in system.ability_ids:
        holdings = [
            record
            for record in records
            if record.predicate == worlds_mod.CAN_DO
            and record.subject == character
            and record.object_ref == ability_id
            and state_mod.is_canon(record)
            and within(record)
        ]
        if not holdings:
            magnitudes.append((ability_id, 0))
            continue
        latest = max(holdings, key=lambda record: (state_mod.order_key_of(record) or ""))
        visible.update(latest.pov_visibility)
        value = latest.value
        magnitude = (
            value if isinstance(value, int) and not isinstance(value, bool) else 1
        )
        magnitudes.append((ability_id, max(0, magnitude)))
    return CharacterSheet(
        system=system,
        character=character,
        rank_id=rank_id,
        magnitudes=tuple(magnitudes),
        visible_to=tuple(sorted(visible)),
    )


__all__ = [
    "CONFIGURATION_PREDICATES",
    "MAGNITUDE_SCALE",
    "MAX_ABILITIES",
    "MAX_SCALE_MAXIMUM",
    "MIN_ABILITIES",
    "MIN_RANKS",
    "MIN_SCALE_MAXIMUM",
    "RANK_KEY",
    "REGISTRY_VERSION",
    "SYSTEM_DIGEST",
    "Ability",
    "AdvanceKind",
    "Advancement",
    "CharacterSheet",
    "Column",
    "Furniture",
    "IllegalAdvance",
    "MalformedSystem",
    "Move",
    "Need",
    "Rank",
    "Scale",
    "SystemDef",
    "check_draw",
    "completion_records",
    "deepen",
    "gain",
    "legal_moves",
    "records_for",
    "records_for_sheet",
    "rise",
    "sheet_of",
    "starting_sheet",
    "systems_of",
]
