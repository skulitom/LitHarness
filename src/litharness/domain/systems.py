"""The game system a book runs on: what a system is, what a legal draw is, where a person
starts, and how both are written down as records.

Split out of `domain/gamesystem.py` on 2026-09-03 (stage-0 §216) with every definition
byte-identical; `gamesystem` re-exports every name here, so `gamesystem.SystemDef` is still
where a caller reads it, and its module docstring carries the reasons for the whole design
(the fork, a magnitude on a capacity and never on a person, no prompt text, no ranking). This
module is the bottom of that chain: it imports neither `advancement` nor `gamesystem`, and
nothing in it reads a record back out of canon.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from hashlib import sha256

import litharness_contracts as lc

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
#: How many ways a fork may offer. **Neither is a bar and neither was arrived at by measuring
#: systems**, on `MIN_ABILITIES`' argument unchanged: the floor is what makes the thing a fork
#: rather than a step — one way forecloses nothing, and foreclosure is the whole of what a choice
#: is — and the ceiling is arithmetic about a menu somebody reads on a page inside a scene, the
#: way `MAX_ABILITIES` is arithmetic about the width of a printed line.
MIN_OPTIONS = 2
MAX_OPTIONS = 4
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
    #: How much of this grant every rung hands out (§210). A grant with it is a **stock**: it
    #: opens at nothing, is never gained or deepened, rises by this much at every rise, and is
    #: what other grants are paid in. Zero, the default, is every grant written before this.
    per_rung: int = 0
    #: What taking this grant is paid in, as `(stock id, amount)` pairs (§210): paid at every
    #: gain and every deepen, and a move that cannot be paid is not offered. Empty is every
    #: grant written before this; prose about a price stays in `costs`, which is a fact about
    #: the world and not arithmetic.
    price: tuple[tuple[str, int], ...] = ()

    def __post_init__(self) -> None:
        """Prerequisites and prices are held in a canonical order. See
        `SystemDef.__post_init__`."""
        object.__setattr__(self, "needs", tuple(sorted(self.needs, key=lambda need: need.ref)))
        object.__setattr__(self, "price", tuple(sorted(self.price)))

    @property
    def is_stock(self) -> bool:
        """Handed out by the rungs, and so never a move of its own (§210)."""
        return self.per_rung > 0

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
class Option:
    """One way a fork can be taken: a name, and the capabilities taking it opens.

    `costs` is a fact about the world in the register `worlds._record_sentence` already uses —
    what taking this way charges, never an instruction about how to write it. Optional, because a
    system may leave the price to the world.

    **`grants` is what makes an option load-bearing.** Every id in it is a declared ability of the
    same system, and `legal_moves` will not offer any of them until this option is the one taken.
    An option that granted nothing would foreclose nothing and be a label on a preference;
    `check_draw` refuses one.
    """

    option_id: str
    name: str
    grants: tuple[str, ...] = ()
    costs: str | None = None
    #: What taking this way looks like or does, one line in the world's register (§207):
    #: the market's advancement screens describe each way, and a way with no line is a
    #: name. Optional, so every fork written before this reads as it did.
    manifests_as: str | None = None
    #: What a person must hold for this way to be offered to them at all (§207): the
    #: same `Need` an ability carries, so a way conditioned on what the person has done
    #: is declared with the vocabulary the graph already has. Empty is offered to all.
    needs: tuple[Need, ...] = ()

    def __post_init__(self) -> None:
        """Grants and needs are held in a canonical order. See `SystemDef.__post_init__`."""
        object.__setattr__(self, "grants", tuple(sorted(self.grants)))
        object.__setattr__(self, "needs", tuple(sorted(self.needs, key=lambda need: need.ref)))

@dataclass(frozen=True, slots=True)
class Choice:
    """One fork: a moment the system offers several ways on and the same person takes one.

    **The object §160 had no name for, and the operator specified the effect before the
    schema.** *"i wonder what I would get and pick"* is a choosing-among-options effect;
    `plan/house-genre-constraint.md` queued the concept as a schema extension and read 10 is where
    it stopped being queued — a rendered line arriving at a number-move reads as a narrator's
    overlay precisely because there is nothing for a character to weigh.

    `opens_at` is a rung id, or `None` for a fork open from the first rung. It is a **position on
    the ladder and never a story position**: a fork opens because the person got there, which is
    §110's rule that a schedule is a statement of intent and intent is not an event, reached
    without a second mechanism.

    **Nothing here records who took what, and there is no default way.** Who took which is one
    person's fact and lives on their sheet; a default would be this module deciding which way a
    character would have gone, which is exactly the ranking §61(5) forbids.
    """

    choice_id: str
    name: str
    options: tuple[Option, ...] = ()
    opens_at: str | None = None

    def __post_init__(self) -> None:
        """Options are held in id order, for `SystemDef.__post_init__`'s round-trip reason: a
        fork written to records and read back can only return them sorted, and a digest that
        called those two revisions different would be a lie about identity."""
        object.__setattr__(
            self, "options", tuple(sorted(self.options, key=lambda one: one.option_id))
        )

    @property
    def option_ids(self) -> tuple[str, ...]:
        return tuple(option.option_id for option in self.options)

    def option(self, option_id: str) -> Option:
        for option in self.options:
            if option.option_id == option_id:
                return option
        raise IllegalAdvance(
            f"{option_id} is not a way of taking {self.choice_id}; this fork offers "
            f"{', '.join(self.option_ids)}"
        )

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
    #: The forks this system offers, `()` for a system with none. **Defaulted so that every
    #: construction written before this field existed is unchanged and every book on disk reads
    #: identically** — §160's ratchet, one field along: a system with no fork is the system it
    #: always was, and `digest` below is careful to agree.
    choices: tuple[Choice, ...] = ()

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
        object.__setattr__(
            self,
            "choices",
            tuple(sorted(self.choices, key=lambda choice: choice.choice_id)),
        )

    @property
    def digest(self) -> str:
        """Content-derived over everything that changes what a sheet means.

        The name and the labels are in the material as well as the structure, because a system
        whose columns were relabelled renders a different line out of the same numbers, and a
        digest that called those two revisions equal would be answering a question nobody asked.

        **The forks join the material only when there are any, and that is a rail rather than a
        micro-optimisation.** This value exists so drift is a question a reader can ask; a schema
        addition that moved every existing system's digest would report a redefinition that did
        not happen, on every sheet that cites one — the digest lying in the one direction it was
        built to make impossible. §160's byte-identity rail
        (`test_a_holding_with_no_number_reads_exactly_as_it_always_did`) is the same argument about
        a sentence, and `test_a_system_with_no_fork_digests_exactly_as_it_always_did` is this one.
        """
        forks = (
            {
                "choices": [
                    [
                        choice.choice_id,
                        choice.name,
                        choice.opens_at,
                        [_option_material(option) for option in choice.options],
                    ]
                    for choice in self.choices
                ]
            }
            if self.choices
            else {}
        )
        # **The stocks join the material only when there are any** (§210), for the forks'
        # reason above: a system with none digests as it always did.
        stocks = (
            {
                "stocks": [
                    [ability.ability_id, ability.per_rung, [list(pair) for pair in ability.price]]
                    for ability in self.abilities
                    if ability.per_rung or ability.price
                ]
            }
            if any(ability.per_rung or ability.price for ability in self.abilities)
            else {}
        )
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
                **forks,
                **stocks,
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
    def stocks(self) -> tuple[str, ...]:
        """The grants the rungs hand out, in id order (§210)."""
        return tuple(ability.ability_id for ability in self.abilities if ability.is_stock)

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

    @property
    def choice_ids(self) -> tuple[str, ...]:
        return tuple(choice.choice_id for choice in self.choices)

    def choice(self, choice_id: str) -> Choice:
        for choice in self.choices:
            if choice.choice_id == choice_id:
                return choice
        raise IllegalAdvance(
            f"{choice_id} is not a fork of {self.system_id}; this system offers "
            f"{', '.join(self.choice_ids) or 'none'}"
        )

    @property
    def gates(self) -> Mapping[str, tuple[str, str]]:
        """Every gated ability, and the `(choice_id, option_id)` that opens it.

        **One entry per ability, and `check_draw` is what guarantees that.** An ability granted by
        two options would have two answers to "is this locked", and a mapping that silently kept
        the last one would decide which fork owned it — the shape `sheet_for` abstains on rather
        than choosing. Here the draw is refused instead, so by the time anything reads this the
        question has one answer.
        """
        found: dict[str, tuple[str, str]] = {}
        for choice in self.choices:
            for option in choice.options:
                for ability_id in option.grants:
                    found.setdefault(ability_id, (choice.choice_id, option.option_id))
        return found

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
            "fields": [{"name": column.name, "label": column.label} for column in self.columns],
            # **The unheld columns do not print** (§203): the snapshot still carries every
            # ability at 0, so the arithmetic and the digest are what they were, and the
            # line the reader sees is the rung and what is held. The market's windows carry
            # one field in fifteen at zero (the system-displays census); the wanting §160
            # put on the line as zeros rides the `[OFFER]` line instead.
            "show_unheld": False,
            # **The sheet names its system and follows it** (§211): a grant declared after
            # the seed is a column the moment it is declared, read by `extraction.sheet_for`
            # off the system as it stands rather than off this record's fields.
            "system": self.system_id,
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
    #: Which way this person took at each fork they have reached, as `(choice_id, option_id)`.
    #: `()` by default, so every construction written before forks existed is unchanged.
    #:
    #: **It does not reach `snapshot`, and that is §160.3's split rather than an omission.**
    #: `extraction`'s field pattern is digits only, so a taken way can no more ride a status
    #: column than a rung's name can. §166.3 already settled where it goes instead: the licence
    #: reaches numerals, "so a class *name* is governed by nothing in it". A pick is spoken in
    #: prose, carried into the packet as a world fact, and read back off its own edge.
    picks: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        """Picks are held in fork order, for `SystemDef.__post_init__`'s round-trip reason."""
        object.__setattr__(self, "picks", tuple(sorted(self.picks)))

    @property
    def system_id(self) -> str:
        return self.system.system_id

    def took(self, choice_id: str) -> str | None:
        """Which way this person took at that fork, or `None` for one still open to them."""
        for held_choice, option_id in self.picks:
            if held_choice == choice_id:
                return option_id
        return None

    def unlocked(self, ability_id: str) -> bool:
        """Whether this person may reach for that capability at all.

        An ungated capability is always reachable — most of them are, and a system with no fork
        answers `True` here for everything, which is what keeps every book on disk unchanged. A
        gated one is reachable only by whoever took the way that opens it. This is the arithmetic
        that makes a fork a fork rather than a label; `legal_moves` is the only caller, and it
        stops offering what the character foreclosed.
        """
        gate = self.system.gates.get(ability_id)
        if gate is None:
            return True
        choice_id, option_id = gate
        return self.took(choice_id) == option_id

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
    """The moves a sheet can make. Small on purpose: a beat names one of these, and a vocabulary
    that grew would be a vocabulary a beat has to choose within.

    **`CHOOSE` is the fourth, and the closure argument above survives it rather than being
    waived.** The progression beat does not choose within this enum — `genre.beat_text` rotates
    by schedule position, which §161.4 records as arithmetic and not a preference — so a fourth
    member is one more position in a cycle rather than one more decision. And it never reaches
    that beat at all: `extraction._named_moves` drops a `CHOOSE`, because a fork is not a quantity
    that moves and naming one there would tell the scene a number moved when none did. A fork is
    the interaction beat's business (`genre.interaction_text`), which is a different schedule.

    It is also the only move that **forecloses**: a gain and a deepen add, a rise climbs, and a
    choice shuts three doors to open one. That is why it could not be modelled as either of the
    other three.
    """

    GAIN = "gain"
    DEEPEN = "deepen"
    RISE = "rise"
    CHOOSE = "choose"

@dataclass(frozen=True, slots=True)
class Move:
    """One advancement that is available. `ability_id` is `None` for a rise or a choice.

    A `CHOOSE` carries the fork and **not** a way of taking it. Returning one move per option
    would be handing a caller a menu this module had enumerated in some order, and the caller's
    next act is to pick from it — which is §61(5)'s ranking arriving through the shape of a return
    value rather than through a score. The fork is what is available; which way is the drafting
    call's, under whatever constraint it is already working to.
    """

    kind: AdvanceKind
    ability_id: str | None = None
    rank_id: str | None = None
    choice_id: str | None = None

@dataclass(frozen=True, slots=True)
class Change:
    """One declared change of kind (§212): what happened to whom, where, and what each grant
    stands at for them afterwards.

    **Absolute values, never deltas.** *Seamsight 0, Windread 1* is what an evolution leaves,
    a merge retires two and grants one, a curse puts a grant lower than it stood; each is a
    statement about the sheet afterwards, which is the one shape `sheet_of` can fold beside a
    `can_do` edge without a second arithmetic. `at` is the change's position, the `type`
    record's order key; `None` is a change already true when the book opens.
    """

    change_id: str
    participant: str
    at: str | None
    effects: tuple[tuple[str, int], ...]

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


def _option_material(option: Option) -> list[object]:
    """A way's digest material: the four fields every way has, then what it looks like and
    needs only where a way has them, so a fork written before §207 keeps its digest."""
    material: list[object] = [option.option_id, option.name, list(option.grants), option.costs]
    if option.manifests_as or option.needs:
        material.append(option.manifests_as)
        material.append([[need.ref, need.threshold] for need in option.needs])
    return material

def check_draw(system: SystemDef, *, drawn: bool = True) -> tuple[str, ...]:
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
        complaints.append(f"the system id {system.system_id!r} is not usable as an identifier")
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
    #
    # **The count is a bound on the draw and not on the book** (§211). A system is drawn once,
    # with five to eight grants, and then grows as the book hands things out: the market's
    # bracketing stories carry more than eight named things in a quarter of cases on a sample
    # of their chapters alone (the system-displays growth census). Everything else here holds
    # at every size, because a cycle or a duplicate is as broken at twenty grants as at six.
    if drawn and not MIN_ABILITIES <= len(system.abilities) <= MAX_ABILITIES:
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
        complaints.append("the prerequisites run in a cycle, so no order of gaining them exists")

    # --- the stocks (§210)
    #
    # Membership and arithmetic, like everything above: a price in a grant no rung hands out
    # could never be paid, a stock nobody gains has no prerequisite to meet and no fork to be
    # opened by, and a rung hands out nothing or more. Nothing here asks whether a price is
    # fair or a stock is generous.
    stocks = set(system.stocks)
    gates = system.gates
    for ability in system.abilities:
        if ability.per_rung < 0:
            complaints.append(
                f"{ability.ability_id} says every rung hands out {ability.per_rung} of it; a "
                "rung hands out nothing or more"
            )
        if ability.is_stock:
            if ability.needs:
                complaints.append(
                    f"{ability.ability_id} is handed out by the rungs and needs "
                    f"{', '.join(need.ref for need in ability.needs)} first; a grant nobody "
                    "gains has no prerequisite to meet"
                )
            if ability.ability_id in gates:
                complaints.append(
                    f"{ability.ability_id} is handed out by the rungs and sits behind the fork "
                    f"{gates[ability.ability_id][0]}; a grant nobody gains cannot be opened by "
                    "a way"
                )
            if ability.price:
                complaints.append(
                    f"{ability.ability_id} is handed out by the rungs and is priced; a grant "
                    "nobody gains or deepens is never paid for"
                )
        for stock, amount in ability.price:
            if stock not in known_abilities:
                complaints.append(
                    f"{ability.ability_id} is paid in {stock}, which this system declares as "
                    "no grant"
                )
            elif stock not in stocks:
                complaints.append(
                    f"{ability.ability_id} is paid in {stock}, which no rung hands out, so it "
                    "could never be paid"
                )
            if amount < 1:
                complaints.append(
                    f"{ability.ability_id} is paid {amount} {stock}; a price is one or more"
                )

    # --- the forks
    #
    # **Every check is membership or arithmetic**, exactly as the ones above are. Nothing here asks
    # whether a fork is interesting, whether its ways are balanced, or which of them a character
    # ought to take: there is no ordering over options in this module and `legal_moves` is
    # explicit that it mints none.
    seen_options: dict[str, str] = {}
    granted_by_option: dict[str, str] = {}
    for choice in system.choices:
        if not choice.choice_id.isidentifier():
            complaints.append(f"the fork id {choice.choice_id!r} is not usable as an identifier")
        if not _printable_label(choice.name):
            complaints.append(
                f"the fork {choice.choice_id}'s name {choice.name!r} cannot be put in a scene "
                "plan: a name is printable prose, at most 24 characters, and carries no digit"
            )
        if not MIN_OPTIONS <= len(choice.options) <= MAX_OPTIONS:
            complaints.append(
                f"the fork {choice.choice_id} offers {len(choice.options)} way(s); a fork offers "
                f"{MIN_OPTIONS} to {MAX_OPTIONS}, the floor being that one way forecloses "
                "nothing and the ceiling being how long a menu somebody reads inside a scene"
            )
        if choice.opens_at is not None and choice.opens_at not in known_ranks:
            complaints.append(
                f"the fork {choice.choice_id} opens at {choice.opens_at}, which this system "
                "declares as no rung"
            )
        if len({option.name.strip() for option in choice.options}) != len(choice.options):
            complaints.append(
                f"two ways of taking {choice.choice_id} are named the same, so taking one "
                "shows nothing"
            )
        for option in choice.options:
            if not option.option_id.isidentifier():
                complaints.append(
                    f"the option id {option.option_id!r} is not usable as an identifier"
                )
            if not _printable_label(option.name):
                complaints.append(
                    f"the option {option.option_id}'s name {option.name!r} cannot be put in a "
                    "scene plan: a name is printable prose, at most 24 characters, and carries "
                    "no digit"
                )
            if option.option_id in seen_options:
                complaints.append(
                    f"{option.option_id} is offered by {seen_options[option.option_id]} and by "
                    f"{choice.choice_id}; one way belongs to one fork, or taking it forecloses "
                    "in two places at once"
                )
            seen_options[option.option_id] = choice.choice_id
            for need in option.needs:
                if need.ref in known_ranks:
                    if need.threshold != 1:
                        complaints.append(
                            f"the way {option.option_id} needs the rung {need.ref} at "
                            f"{need.threshold}; a rung is a position and has no depth to reach"
                        )
                elif need.ref not in known_abilities:
                    complaints.append(
                        f"the way {option.option_id} needs {need.ref}, which this system "
                        "declares neither as an ability nor as a rung"
                    )
            if not option.grants:
                complaints.append(
                    f"{option.option_id} opens nothing, so taking it forecloses nothing and the "
                    f"fork {choice.choice_id} is a label rather than a choice"
                )
            for ability_id in option.grants:
                if ability_id not in known_abilities:
                    complaints.append(
                        f"{option.option_id} opens {ability_id}, which this system does not "
                        "declare as an ability"
                    )
                    continue
                if ability_id in granted_by_option:
                    complaints.append(
                        f"{ability_id} is opened by {granted_by_option[ability_id]} and by "
                        f"{option.option_id}; an ability behind two gates has two answers to "
                        "whether it is locked"
                    )
                granted_by_option[ability_id] = option.option_id
    if len(set(system.choice_ids)) != len(system.choice_ids):
        complaints.append("two forks share an id, so a pick could not say which is meant")

    # --- the scale
    if not _printable_label(system.scale.label):
        complaints.append(f"the scale's label {system.scale.label!r} is not a printable label")
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
            need.ref for need in ability.needs if need.ref in set(system.ability_ids)
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

    **A gated ability is never an opener**, and that is the fork working rather than an extra
    rule: a starting sheet holding what a fork was declared to gate would hand the character a
    branch they never took, and the reader a column that lit up before the choice existed. So a
    system whose every ability sits behind a fork has no starting sheet, and the complaint
    `check_draw` already carries — *"no ability can be held at the first rung"* — is the one that
    fires, which is the right sentence for that draw.
    """
    first = system.rank_ids[0] if system.ranks else None
    gated = set(system.gates)
    holdable: list[str] = []
    for ability in system.abilities:
        if ability.ability_id in gated:
            continue
        if ability.is_stock:
            # Handed out by the rungs, and the first rung is stood on rather than risen to
            # (§210): a stock opens at nothing and the first rise is the first hand-out.
            continue
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
            (ability_id, 1 if ability_id in openers else 0) for ability_id in system.ability_ids
        ),
        visible_to=tuple(visible_to),
    )

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
        worlds_mod.world_record(system.system_id, worlds_mod.ENTITY_ROLE_PREDICATE, value="system"),
        worlds_mod.world_record(system.system_id, "is_a", value=system.name),
        worlds_mod.world_record(
            system.system_id,
            MAGNITUDE_SCALE,
            value={"label": system.scale.label, "maximum": system.scale.maximum},
        ),
        # **The digest and the grants it was drawn with** (§212.1). The digest alone was
        # the record until pilot 25's fork system reported as grown with nothing declared
        # since its seed: the digest's own material had moved with the code, so a digest
        # is not an identity across versions and growth is a question about grants.
        worlds_mod.world_record(
            system.system_id,
            SYSTEM_DIGEST,
            value={"digest": system.digest, "grants": list(system.ability_ids)},
        ),
        # **The system writes its own status line down, in the same function that writes the
        # system.** Leaving this to the seed path was the first design and it was wrong for the
        # reason `sheet_declaration` records: `extraction.sheet_for` abstains to the default
        # when a book declares more than one sheet, so two independent writers of this record
        # do not collide loudly — the book quietly renders a line it never chose. One function
        # writes both, so there is nothing for a second one to disagree with. The subject is
        # the system because `sheet_for` does not read the subject at all, and naming the
        # system is what makes the record legible to somebody reading canon by eye.
        worlds_mod.world_record(system.system_id, "status_sheet", value=system.sheet_declaration()),
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
        worlds_mod.world_record(system.criterion, worlds_mod.COMPARATOR_PREDICATE, value="ordinal"),
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
        records.append(worlds_mod.world_record(ability.ability_id, "is_a", value=ability.name))
        records.append(
            worlds_mod.world_record(
                ability.ability_id, worlds_mod.GOVERNED_BY, object_ref=system.system_id
            )
        )
        if ability.costs:
            records.append(
                worlds_mod.world_record(ability.ability_id, worlds_mod.COSTS, value=ability.costs)
            )
        # **The stock and the price, as records the vocabulary names** (§210): `per_rung` on
        # the stock, and a `costs` whose object is the stock and whose value is the amount on
        # the grant paid in it. A grant with neither writes nothing here.
        if ability.is_stock:
            records.append(
                worlds_mod.world_record(
                    ability.ability_id, worlds_mod.PER_RUNG, value=ability.per_rung
                )
            )
        for stock, amount in ability.price:
            records.append(
                worlds_mod.world_record(
                    ability.ability_id, worlds_mod.COSTS, value=amount, object_ref=stock
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
    # **The forks, and a system with none writes nothing here** — which is what keeps every
    # record set this function has ever produced byte-identical.
    for choice in system.choices:
        records.append(
            worlds_mod.world_record(
                choice.choice_id, worlds_mod.GOVERNED_BY, object_ref=system.system_id
            )
        )
        records.append(worlds_mod.world_record(choice.choice_id, "is_a", value=choice.name))
        if choice.opens_at is not None:
            # **`requires` and not a predicate of its own**, because that predicate already
            # means "this cannot be had before that" and a second one saying it would be a
            # second answer to the same question. No `order_key`: which rung a fork opens at is
            # a standing fact about the fork, exactly as a prerequisite is a standing fact about
            # the capability (`REQUIRES`' own distinction from a reified change's precondition).
            records.append(
                worlds_mod.world_record(
                    choice.choice_id, worlds_mod.REQUIRES, object_ref=choice.opens_at
                )
            )
        for option in choice.options:
            records.append(
                worlds_mod.world_record(
                    choice.choice_id, worlds_mod.OFFERS, object_ref=option.option_id
                )
            )
            records.append(worlds_mod.world_record(option.option_id, "is_a", value=option.name))
            if option.manifests_as:
                records.append(
                    worlds_mod.world_record(
                        option.option_id,
                        worlds_mod.MANIFESTS_PREDICATE,
                        value=option.manifests_as,
                    )
                )
            for need in option.needs:
                records.append(
                    worlds_mod.world_record(
                        option.option_id,
                        worlds_mod.REQUIRES,
                        object_ref=need.ref,
                        value=need.threshold if need.threshold != 1 else None,
                    )
                )
            if option.costs:
                records.append(
                    worlds_mod.world_record(option.option_id, worlds_mod.COSTS, value=option.costs)
                )
            for ability_id in option.grants:
                records.append(
                    worlds_mod.world_record(
                        option.option_id, worlds_mod.GRANTS, object_ref=ability_id
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
    for choice_id, option_id in sheet.picks:
        records.append(
            worlds_mod.world_record(
                sheet.character,
                worlds_mod.CHOSE,
                value=choice_id,
                object_ref=option_id,
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
