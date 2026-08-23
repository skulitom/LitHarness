"""The world a serial runs on: record patterns, the counters over them, and the projection back.

**Record patterns, not schema classes.** Everything here is
`(subject, predicate, value, object_ref, story_position, authority, pov_visibility)` — the shape
`lc.StateRecord` already has, which `record_json` already carries whole. There is no new record
kind, no migration and no contracts bump. `research/progression-generalization.md` §14.1 item 2
says this in as many words and §8.5 gives the reason: "N-ary relations fit through reification;
no new tuple field is required."

**What this module is for.** `plan/world-architect.md` §0 records the measurement that motivates
it: the live serial holds 23 canon records — 15 typed by the operator into
`plan/serial-pilot-seed.json` and 8 readings of one `[STATUS]` line — for a nine-scene book whose
prose contains an Advent, a tier system, a tide, an assay house and a cast. The world is in the
text and not in the store. This is the vocabulary the store needs before an Architect can put one
there, plus the three things that vocabulary is worthless without:

1. **counters**, so a generated world can be gated deterministically rather than admired;
2. **a projection**, so reified records reach a drafting prompt as English rather than as
   notation — `plan/state-model-abilities.md` §2 names this the blocker that would otherwise make
   canon checkable and the prompt worse;
3. **disclosure**, so "true, and nobody has been told" is expressible without overloading
   `pov_visibility`, which is packet access control and must stay that (§0.1 row 2).

**Absence is free, and that is enforced rather than intended.** Nothing here requires a world to
declare a system, a ladder, a sheet, a number, or combat. `project` returns an empty mapping for
records it does not recognise, so a book that declares none of this is untouched by construction
rather than by a compatibility branch — the idiom `domain/extraction.py`'s `DEFAULT_SHEET` states
and `test_a_world_that_declares_nothing_projects_nothing` pins.

**The vocabulary is the research's, spelled as it spells it.** `evaluation.subject`,
`claim.content`, `disclosed_to`, `precedes`, `group_key` and the rest come from
`research/progression-generalization.md` §6.2 and §8, and are not renamed on the way in. Where
this module adds a predicate the research does not name — `entity_role`, `consequence`,
`manifests_as` — it is because a counter has to find the thing, and each is noted below with the
counter it exists for.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256

import litharness_contracts as lc

from litharness.domain import state as state_mod
from litharness.domain.events import payload_digest
from litharness.domain.text import canonicalize

#: Prefix reserved for an author that is an Architect. Restated rather than shared with
#: `directors.DIRECTOR_AUTHOR_PREFIX` for the reason that constant gives for not being shared:
#: the two mark different roles in different tables, and unifying the constant invites unifying
#: the semantics.
ARCHITECT_AUTHOR_PREFIX = "architect:"

#: Content address prefix for a world-building personality. `arch-` rather than `dtor-` or
#: `wtr-`, same argument.
ARCHITECT_ID_PREFIX = "arch-"

#: Stamped on every record this vocabulary mints, so a record an Architect proposed is
#: distinguishable from one an author typed and from one `extraction.REGISTRY_VERSION` read off
#: a status line. `domain/extraction.py` needs exactly this distinction already, and having it
#: here means a later reader never has to guess which of three producers wrote a row.
REGISTRY_VERSION = "litharness.world.v0"

# --- the four patterns, and the predicate that names one -----------------------------------

#: The predicate that says a subject is a reified node rather than a thing in the world.
TYPE_PREDICATE = "type"

CRITERION = "criterion"
CONSTRAINT = "constraint"
CARDINALITY_CONSTRAINT = "cardinality_constraint"
CHANGE = "change"
VIEW = "view"

#: Closed, because these four (plus the cardinality shape, which is a constraint with a fixed
#: five-record form) are the whole of `research/progression-generalization.md` §5. Everything
#: else a world contains is an ordinary subject. Keeping this closed is what stops the palette
#: growing back into the type hierarchy §5.1 cut.
NODE_TYPES: frozenset[str] = frozenset(
    {CRITERION, CONSTRAINT, CARDINALITY_CONSTRAINT, CHANGE, VIEW}
)

# --- entities ------------------------------------------------------------------------------

#: Added by this module rather than taken from the research, and the reason is a counter: the
#: manifestation and bestiary checks have to be able to *find* the creatures. A role is a tag on
#: an ordinary subject, never a type — §5.1 cuts agency, carrier, collection and bond as
#: primitives and this does not reinstate them.
ENTITY_ROLE_PREDICATE = "entity_role"

ENTITY_ROLES: tuple[str, ...] = (
    "cast",
    "creature",
    "place",
    "institution",
    "carrier",
    "agency",
    "system",
    # **A second role on a cast member, never a role of its own.** `entity_roles` returns the
    # roles a subject carries because a subject may be two things at once, and the protagonist
    # is the case that argument was written for: they are a member of the cast and they are
    # additionally the one this book is about. A separate role list would make "protagonist"
    # and "cast" alternatives, and a world would have to choose.
    "protagonist",
    # **A thing a person can do, as a subject in its own right.** Until 2026-08-22 the nearest
    # role was `carrier`, which means an *object* whose possession changes a precondition — so a
    # ring and the sense the ring grants were the same kind of thing and neither counter could
    # tell them apart. Measured over the 24 worlds forged to that date: 135 of 156 criterion
    # rungs are an insignia and every capability-shaped field in the forge schema is a single
    # string, so a world could name one thing a person can do and never a set of them
    # (`research/quality-measurement/mother-of-learning-model-fit.md`).
    "capability",
)

# --- the one member of the cast this book is about -------------------------------------------

#: What the exception lets them do that nobody else can, in the `manifests_as` register: how it
#: shows on the page. A fact about the world, exactly as a rule is — never an instruction about
#: how to write them. `plan/reader-read-3.md` note 1 is why the field exists at all.
EDGE_PREDICATE = "edge"

#: What the exception costs them, payable on the page. The counterpart of `cost_to_reach` on a
#: rank: a gain declared with no price is the thing `_RULES` already refuses everywhere else.
PRICE_PREDICATE = "price"

#: The rule or cardinality shape this subject is the exception to, **by id**. An edge, because
#: the second extractor family reads edges and because an exception that names its rule in prose
#: is an exception nothing can check.
EXCEPTION_PREDICATE = "exception_to"

# --- what a person can do ---------------------------------------------------------------------

#: A person holds a capability. An edge, so `state.cardinality.v0` can count how many one subject
#: has — which is what makes "everyone has one, this person has three" a checkable declaration
#: rather than a sentence. `EXCEPTS_PREDICATE`'s docstring names that example as its own reason
#: for existing, and this is the predicate it was waiting for.
CAN_DO = "can_do"

#: A capability needs another capability, or a rung, first. An edge, and deliberately **not** a
#: `precondition` role: `precondition` belongs to a reified `change` — one occurrence with many
#: roles — and a prerequisite is a standing fact about the capability rather than about any
#: occasion of acquiring it. The two coexist: a world may declare that walking between rooms
#: `requires` seeing the seam, and separately record the morning somebody learned it.
REQUIRES = "requires"

#: Who allows or teaches a capability. Separate from `RECOGNIZED_BY`, which is about a rank: an
#: institution recognises where you *stand*, a person teaches what you can *do*, and collapsing
#: them is how a ladder of permissions eats an inventory of abilities.
TAUGHT_BY = "taught_by"

#: What a capability costs its holder, as prose. **The same predicate a rank's price already
#: uses**, deliberately: it is the same fact about a different subject, and a legible twin would
#: be two names for one thing. It has no projection sentence for the reason the branch beside
#: `CAN_DO` gives — every world forged so far emits `costs` for its ranks, so adding one would
#: change their packets.
COSTS = "costs"



# --- rules and their consequences ----------------------------------------------------------

#: The predicate the pilot seed already uses for a world rule (`rec-seed-provenance`), kept
#: rather than replaced.
WORLD_RULE_PREDICATE = "world_rule"

#: One second-order consequence of a rule, with the domain of life it lands in as the edge.
#: Added by this module. **Uniqueness lives in consequences more than in names**, so this is the
#: predicate the distinctness argument actually rests on, and `consequence_domains` is its
#: counter.
CONSEQUENCE_PREDICATE = "consequence"

CONSEQUENCE_DOMAINS: tuple[str, ...] = (
    "economy",
    "law",
    "religion",
    "crime",
    "daily_life",
    "politics",
    "craft",
    "war",
)

#: How a feature shows on the page: a status-line form, a price, a mark, a sound. Added by this
#: module, and it is the one predicate that exists purely for the register — a world whose ranks
#: have no visible form is a world the reader is told about instead of shown.
MANIFESTS_PREDICATE = "manifests_as"

# --- criteria ------------------------------------------------------------------------------

COMPARATOR_PREDICATE = "comparator"

#: `plan/state-model-abilities.md` §5 item 7's registry, and deliberately not a formula
#: language: "arbitrary executable rules would turn the state store into an unsafe and
#: untestable simulation language".
COMPARATORS: tuple[str, ...] = (
    "ordinal",
    "numeric",
    "threshold",
    "equality",
    "set_inclusion",
    "pareto",
    "replacement_equivalence",
)

#: The ordinal domain, as edges between named results rather than as integers:
#: `(third_seal, precedes, → second_seal)` with the criterion in the value slot. The criterion
#: is on the edge because a world may run several ladders at once — magic and body cultivation
#: side by side — and an unscoped chain would splice them into one order nobody declared.
PRECEDES_PREDICATE = "precedes"

#: Which criterion judges which kind of subject.
EVALUATES_PREDICATE = "evaluates"

#: Where one subject stands on one declared ladder: `(kell, stands_at, → two_wood)` with the
#: criterion in the value slot, exactly as `precedes` carries it.
#:
#: **A flat edge, and the flatness is the whole argument** (`plan/handoff-numbers-go-up.md`
#: boundary 9). The page can only print a flat edge — `[ASSIZE] Kell now stands at two wood` is
#: what a scene writes and what `parse_graph_line` reads back — so the forge's copy of the same
#: fact has to be readable by the same function. The reified `EVALUATION_*` triple stays for the
#: case it was built for, a world that reifies an evaluation with an authority that performed it
#: (`research/progression-generalization.md` §8.3); a standing is not that case and writing both
#: would be two answers to "which rung is this person on".
#:
#: **The number is derived and never stored.** `rung_index` counts the rung's place in
#: `ladder_of`'s chain when asked. An integer stored beside the chain would be a second answer
#: to "which rung is third", and `domain/beats.py`'s rule is that the two eventually disagree.
STANDS_AT_PREDICATE = "stands_at"

#: The three-record evaluation shape of §8.3, plus the institutional role that makes rank and
#: capability separable.
EVALUATION_SUBJECT = "evaluation.subject"
EVALUATION_CRITERION = "evaluation.criterion"
EVALUATION_RESULT = "evaluation.result"
RECOGNIZED_BY = "recognized_by"

# --- claims, belief, disclosure -------------------------------------------------------------

CLAIM_CONTENT = "claim.content"
BELIEVES = "believes"
DISCLOSED_TO = "disclosed_to"

#: The claim is **not** true in this world. Required rather than invented: the research is
#: explicit that a claim's content "need not be substrate truth", so with no marker there is no
#: way to tell a recorded answer from a recorded error — and the packet's hidden section is a
#: heading that says *true*. A character's false belief written under it would be the writer
#: instructed to honour something the world denies.
#:
#: Found by `test_a_clear_world_has_nothing_to_complain_about`, which is worth recording: the
#: first version of this vocabulary had cast beliefs and mystery answers sharing one predicate,
#: and the validator caught it by demanding a reveal for a belief that must never have one.
CLAIM_FALSE = "claim.false"

#: What a mystery asks. A claim that asks something owes a declared reveal scene; a claim that
#: merely *is* something — a secret somebody keeps, a fact nobody has needed yet — does not, and
#: conflating the two would make every private fact in a world a scheduled reveal.
QUESTION_PREDICATE = "asks"

#: The scene ordinal a world means to answer a mystery at, as an integer. **Separate from the
#: `disclosed_to` record's story position, and the separation is a defect's fault.**
#:
#: An open-ended serial schedules most of its answers past the chapters being written now, and a
#: story `order_key` is an opaque string whose ordering is only meaningful inside one book's
#: vocabulary. `beats_for` mints `s1…s8` for an eight-scene book — width one — so a reveal
#: written as `s41` compares **below** `s1` lexicographically, and the two secrets an opening
#: exists to keep were the two handed to the writer as established fact. So an ordinal is stored
#: as an ordinal, and a *position* is minted only for a scene the book actually has.
REVEAL_SCENE = "reveal_scene"

#: The audience a disclosure names when it is the reader being told rather than a character.
#: A claim with content and no reader disclosure at or before the current position is what the
#: packet's hidden section carries.
READER = "reader"

# --- cardinality ----------------------------------------------------------------------------

SCOPE_PREDICATE = "scope"
GROUP_KEY_PREDICATE = "group_key"
MAXIMUM_PREDICATE = "maximum"
PREDICATE_PREDICATE = "predicate"

#: The scope value that means "every subject", for a predicate whose exclusivity is a property
#: of the predicate rather than of a kind of thing.
ANY_SCOPE = "*"

#: One subject this shape does not govern, as an edge from the shape to the subject.
#:
#: **Scope stays a role and this is why it can.** `in_scope`'s docstring records the reason a
#: scope is an `entity_role` and not a subject id: a shape is a rule about a *kind* of thing, and
#: a shape that named one carrier would be a fact about that carrier wearing a rule's clothes.
#: An exception is the other object — a declared fact about *one* subject, which is what the word
#: means — so it is declared as one and read beside the shape rather than inside it. Without it
#: the hook `plan/reader-read-3.md` note 1 asks for is undeclarable: the operator's own example
#: is "everyone in the world has one cuff, the main character broke the system and can have as
#: many as they like", which is exactly a cardinality maximum that does not hold for one person.
EXCEPTS_PREDICATE = "excepts"

#: Group keys a shape may declare. Deliberately three, and deliberately not an expression
#: language: `research/progression-generalization.md` §15.7 refuses a comparator DSL for the
#: same reason a grouping DSL is refused here.
GROUP_KEYS: tuple[str, ...] = ("subject", "subject,order_key", "object")

# --- reified change roles -------------------------------------------------------------------

#: §6.2's role vocabulary. They must not collapse into one edge (§14.1 item 4), which is why
#: `authorized_by`, `validated_by` and `recognized_by` are three constants and not one.
CHANGE_ROLES: tuple[str, ...] = (
    "actor",
    "participant",
    "precondition",
    "caused_by",
    "performed_by",
    "authorized_by",
    "validated_by",
    "recognized_by",
    "effect",
    "consumes",
    "produces",
)

#: Composite subjects and what they make reachable. A bond's abilities need not be the union of
#: its members' — `permits` is where that is said.
MEMBER = "member"
PERMITS = "permits"

#: Which analytic bundle a rule belongs to. §6.2 lists it as multi-valued and gives the reason:
#: "regimes contain many rules and a record can belong to several analytic bundles". A rule that
#: belongs to two colliding systems is the interesting case rather than an error.
BUNDLE_MEMBER = "bundle_member"

#: What a view shows, what it withholds, and what it is a view *of*. §7.9: a lying System is a
#: view over another regime, not a second causal engine.
VIEW_SUBSTRATE = "view.substrate"
VIEW_MAPPING = "view.mapping"
VIEW_WITHHOLDS = "view.withholds"

#: Predicates that configure how a book is written down rather than stating anything about its
#: world, and which must therefore never reach a context packet. `domain/extraction.py` owns the
#: same idea for the status sheet; this module's contribution is the graph-line declaration,
#: which is a parser configuration wearing a world fact's clothes.
GRAPH_LINE_PREDICATE = "graph_line"


class IllegalWorld(Exception):
    """A world record set that this vocabulary cannot mean what it says."""


# --- identity -------------------------------------------------------------------------------


def architect_id_for(brief: str) -> str:
    """Content address over the brief the world was built from.

    So a brief cannot drift under the worlds it forged: editing one word mints a different
    Architect, and "which brief produced this world" stays answerable. `directors.director_id_for`
    is the same construction for the same reason.
    """
    material = canonicalize(brief).encode()
    return f"{ARCHITECT_ID_PREFIX}{sha256(material).hexdigest()[:24]}"


def machine_author(architect_id: str) -> str:
    """The author string a machine-proposed world record or directive is stamped with."""
    return f"{ARCHITECT_AUTHOR_PREFIX}{architect_id}"


def is_machine_author(author: str | None) -> bool:
    """Whether this was proposed by an Architect rather than typed by a person.

    `None` and the empty string are both false, exactly as `directors.is_machine_author` decides
    it: "unrecorded" is not "machine".
    """
    return (author or "").startswith(ARCHITECT_AUTHOR_PREFIX)


def record_id_for(
    subject: str, predicate: str, object_ref: str | None, value: object
) -> str:
    """Content-derived, and **edge-sensitive as well as value-sensitive**.

    `extraction.record_id_for` keys on `(subject, predicate, order_key, value)` and its docstring
    explains why the value is in there: `record_state_records` is `INSERT OR IGNORE`, so a
    contradicting record that collided with the record it contradicts would insert zero rows and
    report success. The same argument applies one step further out here. Two edges from one
    subject under one predicate — `ash trait → keen_scent` and `→ night_sight` — are two facts,
    and an id blind to `object_ref` would silently keep only the first.
    """
    material = payload_digest(
        {"s": subject, "p": predicate, "o": object_ref, "v": value}
    )
    return f"rec-w{sha256(material.encode()).hexdigest()[:24]}"


def world_record(
    subject: str,
    predicate: str,
    *,
    value: object = None,
    object_ref: str | None = None,
    order_key: str | None = None,
    authority: lc.StateAuthority = lc.StateAuthority.PROPOSED,
    pov_visibility: Sequence[str] = (),
    note: str | None = None,
) -> lc.StateRecord:
    """One record in this vocabulary, with its id derived rather than supplied.

    **`PROPOSED` by default, and the default is the rail.** `plan/world-architect.md` §2 states
    it: Architect output is a proposal and reaches canon only through a recorded policy decision.
    A constructor that defaulted the other way would make the rail a thing every call site has to
    remember, which is the shape of a rail that gets forgotten once.

    The `kind` is derived from the shape rather than passed: an edge is a `relationship`, a rule
    is a `world_rule`, everything else is an `assertion`. Three kinds is what the contract's
    vocabulary supports and what `state.RESOURCE_KIND` already maps; asking a caller to choose
    would be a fourth place for the choice to be made differently.
    """
    if predicate == WORLD_RULE_PREDICATE:
        kind = lc.StateRecordKind.WORLD_RULE
    elif object_ref is not None:
        kind = lc.StateRecordKind.RELATIONSHIP
    else:
        kind = lc.StateRecordKind.ASSERTION
    return lc.StateRecord(
        record_id=record_id_for(subject, predicate, object_ref, value),
        kind=kind,
        subject=subject,
        predicate=predicate,
        value=value,
        object_ref=object_ref,
        story_position=(
            lc.StoryPosition(order_key=order_key) if order_key is not None else None
        ),
        authority=authority,
        pov_visibility=list(pov_visibility),
        predicate_registry_version=REGISTRY_VERSION,
        note=note,
    )


def normalise_id(name: str) -> str:
    """A subject id from a name a model wrote. NFC, casefolded, non-word runs to underscores.

    `extraction.normalise_subject` is the same idea for prose names and is deliberately not
    reused: that one collapses whitespace only, because it reads a name the prose printed and
    must not alter it further. This one is normalising an identifier a model invented, where
    punctuation is noise rather than evidence.
    """
    folded = unicodedata.normalize("NFC", name).strip().casefold()
    return re.sub(r"[^\w]+", "_", folded).strip("_")


# --- reading the vocabulary back -------------------------------------------------------------


def _canon(records: Sequence[lc.StateRecord]) -> tuple[lc.StateRecord, ...]:
    return tuple(record for record in records if state_mod.is_canon(record))


def entity_roles(records: Sequence[lc.StateRecord]) -> dict[str, tuple[str, ...]]:
    """Every subject that carries a role tag, and the roles it carries.

    Plural because a subject may be two things at once — the System is an `agency` and a
    `system`, a guild is an `institution` and, when it acts, `cast`. Forcing one would be the
    type hierarchy arriving through a dictionary.
    """
    found: dict[str, list[str]] = {}
    for record in records:
        if record.predicate != ENTITY_ROLE_PREDICATE:
            continue
        role = str(record.value or "").strip()
        if role in ENTITY_ROLES:
            found.setdefault(record.subject, []).append(role)
    return {subject: tuple(sorted(set(roles))) for subject, roles in found.items()}


def entities_with_role(records: Sequence[lc.StateRecord], role: str) -> tuple[str, ...]:
    return tuple(
        sorted(
            subject for subject, roles in entity_roles(records).items() if role in roles
        )
    )


def capabilities(records: Sequence[lc.StateRecord]) -> tuple[str, ...]:
    """Every subject this world declares as a thing a person can do. Sorted.

    **Canon is not filtered here, and that is deliberate rather than an oversight.**
    `entities_with_role` does not filter either, and `architect.report` counts a *candidate* —
    every record of which is `PROPOSED`, because a forged world is a proposal until `--pick`. A
    reader that filtered would report 0 capabilities for every world the forge has ever produced,
    which is what the first version of this function did. Callers that need canon filter first,
    as `world_brief.brief_for` and `context.assemble` already do.
    """
    return entities_with_role(records, "capability")


def capabilities_of(records: Sequence[lc.StateRecord], subject: str) -> tuple[str, ...]:
    """What this subject can do, sorted. Empty for a subject that holds none.

    **The inventory, and it is a set rather than a rung.** A ladder answers *where does this
    person stand*; this answers *what can they do*, and the two are different questions about
    different objects — `research/progression-generalization.md` §5.1 reduces an ability to "a
    named affordance **or set of reachable actions**" and this is that set, read back.
    """
    return tuple(
        sorted(
            {
                record.object_ref
                for record in records
                if record.predicate == CAN_DO and record.object_ref
                and record.subject == subject
            }
        )
    )


def requirement_depth(records: Sequence[lc.StateRecord]) -> int:
    """How many prerequisites deep this world's inventory runs: edges in the longest chain.

    A counter and never a bar. It says how deep the world's own prerequisite structure runs,
    which is the thing that distinguishes an inventory somebody built from a list somebody
    typed — and `plan/handoff-ability-inventory.md` boundary 3 forbids gating on it.

    A cycle is not an error here and is not resolved here: the walk simply refuses to revisit a
    subject, so a cyclic declaration reports the longest acyclic path through it and
    `validate` is where a world that declared one would be complained about if that is ever
    wanted. Guessing which edge of a cycle to cut would be this module inventing a fact.
    """
    edges: dict[str, list[str]] = {}
    for record in records:
        if record.predicate == REQUIRES and record.object_ref:
            edges.setdefault(record.subject, []).append(record.object_ref)
    if not edges:
        return 0

    def depth(node: str, seen: frozenset[str]) -> int:
        if node in seen:
            return 0
        onward = edges.get(node, ())
        if not onward:
            return 0
        return 1 + max(depth(nxt, seen | {node}) for nxt in onward)

    return max(depth(node, frozenset()) for node in edges)


def nodes_of_type(records: Sequence[lc.StateRecord], node_type: str) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                record.subject
                for record in records
                if record.predicate == TYPE_PREDICATE
                and str(record.value or "").strip() == node_type
            }
        )
    )


def rules(records: Sequence[lc.StateRecord]) -> tuple[str, ...]:
    """Subjects that state a world rule."""
    return tuple(
        sorted(
            {
                record.subject
                for record in records
                if record.predicate == WORLD_RULE_PREDICATE
            }
        )
    )


def consequence_domains(
    records: Sequence[lc.StateRecord],
) -> dict[str, tuple[str, ...]]:
    """Per rule, the distinct domains of life its consequences land in.

    **Distinct domains rather than a count of consequences**, because three consequences all in
    the economy are one consequence with three faces, and the thing being counted is how far a
    rule reaches into the world. The gate in `application/architect.py` reads this.
    """
    found: dict[str, set[str]] = {subject: set() for subject in rules(records)}
    for record in records:
        if record.predicate != CONSEQUENCE_PREDICATE:
            continue
        domain = (record.object_ref or "").strip()
        if domain in CONSEQUENCE_DOMAINS:
            found.setdefault(record.subject, set()).add(domain)
    return {subject: tuple(sorted(domains)) for subject, domains in found.items()}


@dataclass(frozen=True, slots=True)
class Coverage:
    """What had to be shown on the page, and what says how."""

    features: tuple[str, ...]
    covered: tuple[str, ...]

    @property
    def missing(self) -> tuple[str, ...]:
        return tuple(f for f in self.features if f not in set(self.covered))

    @property
    def share(self) -> float:
        """1.0 for a world with no features, and that is the honest reading.

        A world that declares nothing has nothing unmanifested. Returning 0.0 would make
        "declared nothing" and "declared everything and showed none of it" the same number,
        which is the failure mode `plan/world-architect.md` §6 calls a bar that cannot fail
        wearing a bar that cannot pass.
        """
        if not self.features:
            return 1.0
        return len(set(self.covered)) / len(set(self.features))


def features(records: Sequence[lc.StateRecord]) -> tuple[str, ...]:
    """Everything a world declared that a reader has to be able to see.

    Rules, the results of ordinal criteria (the ranks), and the entities whose whole point is
    being encountered: creatures, carriers and systems. Cast, places and institutions are
    deliberately absent — a person does not need a declared visible form to appear in a scene,
    and requiring one would be the checklist this design refuses.
    """
    found: set[str] = set(rules(records))
    for record in records:
        if record.predicate == PRECEDES_PREDICATE:
            found.add(record.subject)
            if record.object_ref:
                found.add(record.object_ref)
    for role in ("creature", "carrier", "system"):
        found.update(entities_with_role(records, role))
    return tuple(sorted(found))


def manifestation_coverage(records: Sequence[lc.StateRecord]) -> Coverage:
    """Which declared features say how they show on the page."""
    declared = features(records)
    shown = {
        record.subject
        for record in records
        if record.predicate == MANIFESTS_PREDICATE and str(record.value or "").strip()
    }
    return Coverage(declared, tuple(sorted(shown & set(declared))))


def criteria(records: Sequence[lc.StateRecord]) -> dict[str, str]:
    """Every criterion node and its comparator. A criterion with no comparator is absent here."""
    declared = set(nodes_of_type(records, CRITERION))
    found: dict[str, str] = {}
    for record in records:
        if record.predicate != COMPARATOR_PREDICATE or record.subject not in declared:
            continue
        comparator = str(record.value or "").strip()
        if comparator in COMPARATORS:
            found[record.subject] = comparator
    return found


def rank_order(
    records: Sequence[lc.StateRecord], *, criterion: str | None = None
) -> tuple[tuple[str, str], ...]:
    """The `precedes` edges, sorted. A partial order, never flattened into a list.

    Comparison is partial by default — a system where specialising forecloses has no total
    order, and forcing one would be the ladder assumption returning in disguise. So this returns
    the edges and lets the caller decide what it can say about them.

    `criterion` filters to the ladder that criterion runs. An edge with no criterion in its
    value belongs to every ladder, which is right for the common world with one.
    """
    edges = [
        (record.subject, record.object_ref, str(record.value or "").strip())
        for record in records
        if record.predicate == PRECEDES_PREDICATE and record.object_ref
    ]
    return tuple(
        sorted(
            (lower, higher)
            for lower, higher, owner in edges
            if criterion is None or not owner or owner == criterion
        )
    )


def claims(records: Sequence[lc.StateRecord]) -> dict[str, str]:
    """Claim id → its content. Every claim, true or not; `false_claims` is the partition."""
    return {
        record.subject: str(record.value)
        for record in records
        if record.predicate == CLAIM_CONTENT and str(record.value or "").strip()
    }


def false_claims(records: Sequence[lc.StateRecord]) -> frozenset[str]:
    """Claims this world says are wrong — a character's error rather than a recorded answer."""
    return frozenset(
        record.subject
        for record in records
        if record.predicate == CLAIM_FALSE and record.value is True
    )


def questions(records: Sequence[lc.StateRecord]) -> dict[str, str]:
    """Claim id → the question it answers, for the claims that are mysteries."""
    return {
        record.subject: str(record.value)
        for record in records
        if record.predicate == QUESTION_PREDICATE and str(record.value or "").strip()
    }


def reveal_scenes(records: Sequence[lc.StateRecord]) -> dict[str, int]:
    """Claim id → the scene ordinal the world means to answer it at. See `REVEAL_SCENE`."""
    return {
        record.subject: record.value
        for record in records
        if record.predicate == REVEAL_SCENE
        and isinstance(record.value, int)
        and not isinstance(record.value, bool)
        and record.value >= 1
    }


def disclosures(records: Sequence[lc.StateRecord]) -> dict[str, tuple[str | None, ...]]:
    """Claim id → the story positions at which it is disclosed to the reader.

    `None` in the tuple means a disclosure with no position: the claim is open from the start,
    which is a legitimate thing for a world to say and is not the same as never disclosed.
    """
    found: dict[str, list[str | None]] = {}
    for record in records:
        if record.predicate != DISCLOSED_TO:
            continue
        if str(record.value or "").strip() != READER or not record.object_ref:
            continue
        found.setdefault(record.object_ref, []).append(state_mod.order_key_of(record))
    return {
        claim: tuple(sorted(keys, key=lambda key: (key is None, key or "")))
        for claim, keys in found.items()
    }


def undisclosed_claims(
    records: Sequence[lc.StateRecord], *, at: str | None = None
) -> tuple[lc.StateRecord, ...]:
    """The `claim.content` records the reader has not been given yet, in story order.

    **This is the iceberg, and it is deliberately not `pov_visibility`.**
    `plan/state-model-abilities.md` §0.1 row 2 forbids the overload, and the reason is exactly
    this function: a secret written into `pov_visibility` reaches no packet at all, so the one
    thing the writer most needs to honour would be the one thing it is never told.

    `at` is where the book currently stands. A claim whose every reader-disclosure is scheduled
    strictly after it is still hidden; one disclosed at or before it is an ordinary fact.

    **With no `at`, a scheduled claim stays hidden, and the asymmetry is the argument.** The two
    errors are not the same size. Handing a writer a secret the reader already has, under an
    instruction not to state it, costs one scene some material it could have used. Handing a
    writer nothing, so it states a secret the book has not yet revealed, destroys the spine the
    reveal was built on and no later scene repairs it. So an unlocatable position reads as *not
    yet*, and a disclosure with **no** position at all — a claim open from the start — reads as
    already told, which is the only case where the world has actually said so.

    Found by `test_a_forged_bundle_seeds_a_book_with_no_provider_call`, and it mattered: the live
    drafting path passes no story-time cutoff at all, so the first version of this function put
    every scheduled answer into the *facts* and the hidden section held only the secrets nobody
    ever reveals — which is the exact inverse of what a mystery is for.

    **A false claim is never hidden, because it is not true.** The heading this feeds says *true,
    and the reader has not been told*; a character's error under it would instruct the writer to
    honour something the world denies. See `CLAIM_FALSE`.
    """
    schedule = disclosures(records)
    wrong = false_claims(records)
    hidden: list[lc.StateRecord] = []
    for record in records:
        if record.predicate != CLAIM_CONTENT or not str(record.value or "").strip():
            continue
        if record.subject in wrong:
            continue
        keys = schedule.get(record.subject)
        if keys is None:
            hidden.append(record)
            continue
        if any(key is None for key in keys):
            continue
        if at is None or all(key is not None and key > at for key in keys):
            hidden.append(record)
    return state_mod.in_story_order(hidden)


def hidden_record_ids(
    records: Sequence[lc.StateRecord], *, at: str | None = None
) -> frozenset[str]:
    """Record ids the packet must carry under "true, not yet disclosed" rather than as fact."""
    return frozenset(record.record_id for record in undisclosed_claims(records, at=at))


@dataclass(frozen=True, slots=True)
class CardinalityShape:
    """One world-declared "at most m of these, grouped this way".

    Five records, exactly `research/progression-generalization.md` §8.2's encoding. A shape is a
    *declaration*, so it is author-locked or accepted canon like any other fact, and an
    undeclared predicate stays untyped and non-blocking — which is what keeps free-form
    predicates cheap.
    """

    constraint_id: str
    predicate: str
    scope: str
    group_key: str
    maximum: int
    #: Subjects this shape does not govern. Empty for every shape declared before
    #: `EXCEPTS_PREDICATE` existed, and a shape with an empty tuple behaves exactly as it did.
    except_subjects: tuple[str, ...] = ()


def cardinality_shapes(
    records: Sequence[lc.StateRecord],
) -> tuple[CardinalityShape, ...]:
    """Every complete, well-formed shape in canon. Incomplete ones are silently absent.

    Silently, because a half-written shape is a world that has not finished saying something,
    and refusing the whole book over it would make declaring cardinality riskier than not
    declaring it. `validate` is where an incomplete shape is reported, at forge time, where the
    cost of the complaint is a candidate rather than a serial.
    """
    parts: dict[str, dict[str, lc.StateRecord]] = {}
    #: Collected in its own pass because `parts` keeps one record per predicate and a shape may
    #: except more than one subject. Keying the last one would silently drop the rest, which is
    #: the failure `record_id_for`'s docstring records for edges generally.
    excepted: dict[str, set[str]] = {}
    for record in records:
        parts.setdefault(record.subject, {})[record.predicate] = record
        if record.predicate == EXCEPTS_PREDICATE and record.object_ref:
            excepted.setdefault(record.subject, set()).add(record.object_ref)
    shapes: list[CardinalityShape] = []
    for subject in sorted(parts):
        rows = parts[subject]
        typed = rows.get(TYPE_PREDICATE)
        if typed is None or str(typed.value or "").strip() != CARDINALITY_CONSTRAINT:
            continue
        predicate = rows.get(PREDICATE_PREDICATE)
        scope = rows.get(SCOPE_PREDICATE)
        group_key = rows.get(GROUP_KEY_PREDICATE)
        maximum = rows.get(MAXIMUM_PREDICATE)
        if predicate is None or group_key is None or maximum is None:
            continue
        predicate_name = str(predicate.value or predicate.object_ref or "").strip()
        group = str(group_key.value or "").strip()
        scope_name = (
            str(scope.object_ref or scope.value or ANY_SCOPE).strip()
            if scope is not None
            else ANY_SCOPE
        )
        if not predicate_name or group not in GROUP_KEYS:
            continue
        if not isinstance(maximum.value, int) or isinstance(maximum.value, bool):
            continue
        if maximum.value < 1:
            continue
        shapes.append(
            CardinalityShape(
                subject,
                predicate_name,
                scope_name,
                group,
                maximum.value,
                tuple(sorted(excepted.get(subject, ()))),
            )
        )
    return tuple(shapes)


def group_of(record: lc.StateRecord, group_key: str) -> str:
    """The bucket a record falls in under a declared grouping key."""
    if group_key == "subject":
        return record.subject
    if group_key == "object":
        return record.object_ref or ""
    return f"{record.subject}\x00{state_mod.order_key_of(record) or ''}"


def in_scope(
    record: lc.StateRecord,
    shape: CardinalityShape,
    roles: Mapping[str, tuple[str, ...]],
) -> bool:
    """Whether a record's subject is one this shape governs.

    Scope is an `entity_role`, or `*`. Not a subject id: a shape that named one carrier would be
    a fact about that carrier, and the thing being declared is a rule about a *kind* of thing.

    **An exception is the other object, and it is checked first.** A subject the shape declares
    it does not govern (`EXCEPTS_PREDICATE`) is out of scope whatever its roles are — which is
    what makes the hook of `plan/reader-read-3.md` note 1 declarable without putting a hole in
    the shape: the maximum still binds on every other subject of the same kind, and
    `tests/test_integrity.py` pins all three of those cases against each other.
    """
    if record.subject in shape.except_subjects:
        return False
    if shape.scope == ANY_SCOPE:
        return True
    return shape.scope in roles.get(record.subject, ())


# --- counters the measurement side reads ------------------------------------------------------

#: **`is_a` is deliberately NOT projected**, and the reason is the property this module's
#: docstring claims. It is an ordinary predicate that predates this vocabulary — Serial Pilot 1's
#: operator-typed seed uses it, and so may any book — so rendering it would change the packet of
#: a book that declares no world at all, which is exactly what "untouched by construction" says
#: cannot happen. `subject is_a value` reads acceptably flat; that is the price and it is small.
#:
#: Predicates whose values are prose the world invented rather than machine vocabulary. The
#: genre-lexicon overlap counter reads names out of these and out of subject ids; reading them
#: out of every predicate would count `economy` and `ordinal` as names the world coined.
_NAME_BEARING = frozenset({WORLD_RULE_PREDICATE, "is_a", MANIFESTS_PREDICATE})

#: A capitalised word that is **not** the first word of a sentence. The lookbehind is what makes
#: it a name rather than a position: without it "Not the city" contributes `not`, which is what
#: the first live run of this counter actually did.
_INNER_CAPITAL = re.compile(r"(?<![.!?]\s)(?<!^)(?<![.!?]\s\s)\b([A-Z][A-Za-z'-]{2,})\b")

#: Connective and structural words that appear inside a snake_case id and name nothing.
_ID_NOISE = frozenset({"the", "and", "for", "of", "house", "a", "an", "to", "in", "on"})


def key_nouns(records: Sequence[lc.StateRecord]) -> tuple[str, ...]:
    """The names a world coined, lower-cased and deduplicated.

    Subject ids of everything that carries a role tag or states a rule, plus the capitalised
    words inside the prose those subjects carry. **Deliberately crude and named as crude**: this
    feeds a distribution report, not a bar, and `plan/world-architect.md` §6 records why M2 has
    no bar — `opening_proper_nouns` is the case where a counter nominated for a named defect
    placed the complained-about chapter at the 68.5th percentile of published openings.

    **Corrected after its first live run, and both numbers are on the record.** The first version
    took every capitalised word, so a sentence-initial `Not`, `From`, `One` and `Read` all entered
    a world's list of coined names; and it split subject ids on `_` at a three-character floor, so
    `mour` and `ise` arrived out of the middle of longer ids. Fixing a counter *after* seeing its
    answer is the failure `platform_priors.py` freezes its matchers to avoid, so the pre-fix
    figures stay reported in stage-0 §107.6 beside the post-fix ones rather than being replaced.
    What licenses the fix is that these are implementation errors and not threshold choices: no
    reading of this counter ever wanted `not` to be a name.
    """
    names: set[str] = set()
    for subject in (*entity_roles(records), *rules(records)):
        for part in subject.split("_"):
            if len(part) > 3 and part not in _ID_NOISE:
                names.add(part.casefold())
    for record in records:
        if record.predicate not in _NAME_BEARING:
            continue
        text = record.value if isinstance(record.value, str) else ""
        for word in _INNER_CAPITAL.findall(text):
            names.add(word.casefold())
    return tuple(sorted(names))


def validate(records: Sequence[lc.StateRecord]) -> tuple[str, ...]:
    """Deterministic complaints about a world's own coherence. Empty means nothing to say.

    **Every check here is arithmetic or membership over the records**, never a judgment about
    whether the world is any good. There is no quality ordering over worlds in this project and
    inventing one here would be the frame `plan/director-role.md` §0 records three burials of.
    """
    complaints: list[str] = []
    roles = entity_roles(records)

    for record in records:
        if record.predicate == ENTITY_ROLE_PREDICATE:
            role = str(record.value or "").strip()
            if role not in ENTITY_ROLES:
                complaints.append(
                    f"{record.subject} claims the role {role!r}, which is not one of "
                    f"{', '.join(ENTITY_ROLES)}"
                )
        if record.predicate == TYPE_PREDICATE:
            node_type = str(record.value or "").strip()
            if node_type not in NODE_TYPES:
                complaints.append(
                    f"{record.subject} is typed {node_type!r}; the reified node types are "
                    f"{', '.join(sorted(NODE_TYPES))} and everything else is an ordinary subject"
                )
        if record.predicate == CONSEQUENCE_PREDICATE:
            domain = (record.object_ref or "").strip()
            if domain not in CONSEQUENCE_DOMAINS:
                complaints.append(
                    f"{record.subject} names a consequence in {domain!r}, which is not one of "
                    f"{', '.join(CONSEQUENCE_DOMAINS)}"
                )
        if record.predicate == COMPARATOR_PREDICATE:
            comparator = str(record.value or "").strip()
            if comparator not in COMPARATORS:
                complaints.append(
                    f"{record.subject} declares the comparator {comparator!r}; the registry is "
                    f"{', '.join(COMPARATORS)}"
                )

    for subject in nodes_of_type(records, CRITERION):
        if subject not in criteria(records):
            complaints.append(f"criterion {subject} declares no comparator from the registry")

    # **Three checks on a standing, all membership.** A rung this world never declared, a rung
    # that two chains both claim, and a standing on a criterion that is not ordinal. Nothing here
    # asks whether the rung is the right one for this person — that is a judgment, and
    # `plan/world-architect.md` §2 keeps the channel that would answer it shut.
    declared_comparators = criteria(records)
    declared_ranks = {
        rung
        for criterion in declared_comparators
        for rung in ladder_of(records, criterion)
    }
    for record in records:
        if record.predicate != STANDS_AT_PREDICATE or not record.object_ref:
            continue
        rung = record.object_ref
        if rung not in declared_ranks:
            complaints.append(
                f"{record.subject} stands at {rung}, which is not a declared rank of any "
                "chain in this world; a standing on a rung nobody declared is a number with "
                "nothing to count it against"
            )
            continue
        owners = [
            criterion
            for criterion in sorted(declared_comparators)
            if rung in ladder_of(records, criterion)
        ]
        if len(owners) > 1:
            complaints.append(
                f"rung {rung} sits in {len(owners)} chains ({', '.join(owners)}); which ladder "
                "a standing counts on has to be one answer, and `criterion_of_rung` abstains "
                "rather than choosing"
            )
        criterion = str(record.value or "").strip() or (owners[0] if owners else "")
        if criterion and declared_comparators.get(criterion) != "ordinal":
            complaints.append(
                f"{record.subject} stands on {criterion}, whose comparator is "
                f"{declared_comparators.get(criterion)!r} rather than 'ordinal'; a standing is a "
                "position in an order and a comparator that declares no order has no positions"
            )

    known = (
        set(roles)
        | set(rules(records))
        | {record.subject for record in records if record.predicate == TYPE_PREDICATE}
        | set(claims(records))
    )
    for record in records:
        if record.predicate not in CHANGE_ROLES or not record.object_ref:
            continue
        if record.object_ref not in known:
            complaints.append(
                f"{record.subject} {record.predicate} points at {record.object_ref}, which "
                "this world never declares"
            )

    # **Only a claim that asks something owes a reveal.** A secret somebody keeps and a belief
    # somebody holds are claims too, and demanding a disclosure position for them would turn
    # every private fact in a world into a scheduled reveal — which is the checklist this design
    # refuses, arriving through the validator.
    scheduled = reveal_scenes(records)
    for claim_id in questions(records):
        if claim_id not in claims(records):
            complaints.append(f"claim {claim_id} asks a question and records no answer")
        elif claim_id not in scheduled:
            # **A reveal *scene*, not a reveal *position*.** Most of a serial's answers land
            # past the chapters being written, and those get no `disclosed_to` record at all —
            # the reader is not told in this book, so the claim stays hidden throughout, which
            # is exactly right. What every mystery owes is the ordinal.
            complaints.append(
                f"claim {claim_id} records an answer and no reveal scene; a mystery with no "
                "reveal is a promise the ledger can never pay"
            )

    for record in records:
        if record.predicate != DISCLOSED_TO:
            continue
        if record.object_ref and record.object_ref not in claims(records):
            complaints.append(
                f"{record.subject} discloses {record.object_ref}, which records no answer"
            )

    for subject, parts in _cardinality_parts(records).items():
        missing = sorted(
            {PREDICATE_PREDICATE, GROUP_KEY_PREDICATE, MAXIMUM_PREDICATE} - parts
        )
        if missing:
            complaints.append(
                f"cardinality shape {subject} is missing {', '.join(missing)}; an incomplete "
                "shape checks nothing and reads as if it did"
            )

    return tuple(complaints)


def _cardinality_parts(records: Sequence[lc.StateRecord]) -> dict[str, set[str]]:
    declared = {
        record.subject
        for record in records
        if record.predicate == TYPE_PREDICATE
        and str(record.value or "").strip() == CARDINALITY_CONSTRAINT
    }
    parts: dict[str, set[str]] = {subject: set() for subject in declared}
    for record in records:
        if record.subject in parts:
            parts[record.subject].add(record.predicate)
    return parts


# --- the projection ----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Protagonist:
    """The one member of the cast this book is about, as canon declares them."""

    subject: str
    exception: str
    edge: str
    wants: str
    price: str

    def to_jsonable(self) -> dict[str, object]:
        return {
            "id": self.subject,
            **({"exception": self.exception} if self.exception else {}),
            **({"edge": self.edge} if self.edge else {}),
            **({"wants": self.wants} if self.wants else {}),
            **({"price": self.price} if self.price else {}),
        }


def protagonist_brief(records: Sequence[lc.StateRecord]) -> Protagonist | None:
    """The declared protagonist, or `None` for a book whose canon names none.

    **`None` is every book written before 2026-08-22 and it is the control.** A caller that gets
    `None` must render exactly the bytes it rendered before this function existed; a key that is
    always present carrying `null` is a payload that always changed, and `input_digest_for`
    covers the prompt and seeds the sampler.

    More than one declared protagonist is not an error here and is not resolved here either: the
    first by subject id is returned, deterministically, and `validate` is where a world that
    declares two would be complained about if the operator ever wants that complaint. Nothing in
    this project ranks people.
    """
    canon = _canon(records)
    subjects = entities_with_role(canon, "protagonist")
    if not subjects:
        return None
    subject = subjects[0]
    values: dict[str, str] = {}
    exception = ""
    for record in canon:
        if record.subject != subject:
            continue
        if record.predicate == EXCEPTION_PREDICATE and record.object_ref:
            exception = record.object_ref
        elif record.object_ref is None:
            values[record.predicate] = str(record.value or "").strip()
    return Protagonist(
        subject,
        exception,
        values.get(EDGE_PREDICATE, ""),
        values.get("wants", ""),
        values.get(PRICE_PREDICATE, ""),
    )


def criterion_brief(records: Sequence[lc.StateRecord]) -> str | None:
    """One line per criterion, for the drafting system message. `None` when a world declares none.

    `plan/state-model-abilities.md` §5 item 11: *show the generator the criterion it is writing
    against*. It goes in the system message rather than in the packet because a criterion is a
    rule about how the world judges, which is closer to "how to write this book" than to "what
    happened" — the boundary `feedback` and the writer dossier already observe.
    """
    canon = _canon(records)
    declared = criteria(canon)
    if not declared:
        return None
    lines: list[str] = []
    for subject in sorted(declared):
        comparator = declared[subject].replace("_", " ")
        ladder = ladder_of(canon, subject)
        if ladder:
            lines.append(f"- {subject}: {comparator} — {' then '.join(ladder)}")
        else:
            lines.append(f"- {subject}: {comparator}")
    return "\n".join(lines)


def ladder_of(records: Sequence[lc.StateRecord], criterion: str) -> tuple[str, ...]:
    """This criterion's results in `precedes` order, or empty when they do not form a chain.

    **Empty rather than a guess.** A criterion whose results branch has no ladder to print, and
    printing one anyway would be the total order this model refuses to assume. Two edges out of
    one result, a cycle, or more than one starting point all return empty.

    Public since 2026-08-22 under the name the callers outside this module wanted, and it is one
    function rather than two: `criterion_brief` and `_node_sentence` call this, and so do
    `rung_index`, `standing_of`'s validator and the outline's schedule. A public wrapper around a
    private chain-walker would be a second place for the chain rule to live.
    """
    edges = rank_order(records, criterion=criterion)
    if not edges:
        return ()
    successors = dict(edges)
    if len(successors) != len(edges):
        return ()
    starts = set(successors) - set(successors.values())
    if len(starts) != 1:
        return ()
    chain = [starts.pop()]
    seen = set(chain)
    while chain[-1] in successors:
        following = successors[chain[-1]]
        if following in seen:
            return ()
        chain.append(following)
        seen.add(following)
    return tuple(chain)


def rung_index(
    records: Sequence[lc.StateRecord], criterion: str, rung: str
) -> int | None:
    """This rung's 1-based place in its criterion's chain, counting from the bottom.

    **This is the number.** The operator's direction is that a rank ladder *is* the number a
    genre reader counts — "bronze to gold rank advance is the same as the number going up; say
    bronze is 1 and gold is 3" — so the quantity is the rung's position in the declared chain and
    nothing else. It is computed here rather than stored, for the reason
    `STANDS_AT_PREDICATE` gives: a stored integer beside the chain is a second answer to the same
    question and the two would drift.

    `None` when the criterion's results do not form a chain, or when the rung is not on it —
    empty rather than a guess, the rule `ladder_of` already follows. A caller that gets `None`
    has a world that declared a partial order and a subject standing somewhere in it, which is a
    legitimate world; what it does not have is a number, and inventing one would be the total
    order this model refuses to assume.
    """
    chain = ladder_of(records, criterion)
    if rung not in chain:
        return None
    return chain.index(rung) + 1


def criterion_of_rung(records: Sequence[lc.StateRecord], rung: str) -> str | None:
    """Which declared chain this rung sits in, or `None` when that is not one answer.

    The criterion a standing belongs to is **derived** rather than declared twice: a
    `stands_at` edge carries the criterion in its value slot exactly as `precedes` does, and this
    is how a reader of the *page* — where the criterion is not printed — recovers it.

    `None` both when no chain holds the rung and when two do. A rung in two chains is a
    `validate` complaint rather than a tie broken here (`plan/handoff-numbers-go-up.md`
    boundary 9): picking one would be this function inventing which ladder a world meant.
    """
    owners = [
        criterion
        for criterion in sorted(criteria(records))
        if rung in ladder_of(records, criterion)
    ]
    return owners[0] if len(owners) == 1 else None


def standing_of(
    records: Sequence[lc.StateRecord], subject: str, *, at: str | None = None
) -> dict[str, str]:
    """Where this subject stands on each ladder, as of `at`. Empty for a subject on none.

    Canon only, and the latest standing at or before `at` per criterion — a standing is a fact
    that *changes*, so the packet's rule for a fact with a story position applies: the one in
    force is the last one the book has reached. `at=None` means "wherever the book is now", which
    reads every canon standing including the unplaced.

    **A dict per criterion rather than one rung, because a subject may be on two ladders.**
    Magic and body cultivation side by side is the world `PRECEDES_PREDICATE` puts the criterion
    on the edge for, and collapsing the two here would splice an order nobody declared. The
    criterion is read from the edge's value slot, falling back to `criterion_of_rung` for a
    standing whose value slot is empty — the page prints a rung and not a criterion, so the edge
    an extractor reads back off prose has to be resolvable without one.
    """
    latest: dict[str, tuple[str, str]] = {}
    for record in _canon(records):
        if record.predicate != STANDS_AT_PREDICATE or not record.object_ref:
            continue
        if record.subject != subject:
            continue
        key = state_mod.order_key_of(record) or ""
        if at is not None and key > at:
            continue
        criterion = str(record.value or "").strip() or criterion_of_rung(
            records, record.object_ref
        )
        if not criterion:
            continue
        held = latest.get(criterion)
        if held is None or key >= held[0]:
            latest[criterion] = (key, record.object_ref)
    return {criterion: rung for criterion, (_, rung) in sorted(latest.items())}


#: Records that belong to a reified node and say nothing on their own. Folded into the node's
#: one sentence by `project`, and dropped from the packet — the same information under a
#: different id, which is why it is not an omission any more than a `status_sheet` is.
_SATELLITE = frozenset(
    {
        *CHANGE_ROLES,
        COMPARATOR_PREDICATE,
        EVALUATES_PREDICATE,
        EVALUATION_SUBJECT,
        EVALUATION_CRITERION,
        EVALUATION_RESULT,
        VIEW_SUBSTRATE,
        VIEW_MAPPING,
        VIEW_WITHHOLDS,
        SCOPE_PREDICATE,
        GROUP_KEY_PREDICATE,
        MAXIMUM_PREDICATE,
        PREDICATE_PREDICATE,
        EXCEPTS_PREDICATE,
        MEMBER,
        PERMITS,
    }
)

_ROLE_PHRASE: Mapping[str, str] = {
    "actor": "done by",
    "participant": "with",
    "precondition": "needs",
    "caused_by": "caused by",
    "performed_by": "performed by",
    "authorized_by": "authorised by",
    "validated_by": "validated by",
    "recognized_by": "recognised by",
    "effect": "results in",
    "consumes": "costs",
    "produces": "produces",
}


def project(records: Sequence[lc.StateRecord]) -> dict[str, str]:
    """Reified records as sentences, keyed by record id. `""` means "folded away, do not pack".

    **This is the gate on the model being usable at all**, and
    `plan/state-model-abilities.md` §2 says why: the flat graph reads almost like prose, the
    reified form is machine notation, and this project's quality runs entirely through what the
    generator is handed. A model that is checkable and illegible to the writer trades the stated
    priority for the instrumentation.

    Records this vocabulary does not recognise are absent from the result, and the caller falls
    back to `state.describe` — so a book that declares no world is byte-identical to what it was.

    **A node is folded only when every one of its records is objective.** A satellite with a
    `pov_visibility` of its own is a fact about who knows what, and collapsing it into a sentence
    written for everybody would leak it. Those nodes project per-record instead.
    """
    projected: dict[str, str] = {}
    by_subject: dict[str, list[lc.StateRecord]] = {}
    for record in records:
        by_subject.setdefault(record.subject, []).append(record)

    typed: dict[str, str] = {}
    for record in records:
        if record.predicate == TYPE_PREDICATE:
            node_type = str(record.value or "").strip()
            if node_type in NODE_TYPES:
                typed[record.subject] = node_type

    foldable = {
        subject
        for subject, node_type in typed.items()
        if node_type in {CHANGE, VIEW, CRITERION, CARDINALITY_CONSTRAINT}
        and not any(row.pov_visibility for row in by_subject.get(subject, ()))
    }

    for subject in sorted(foldable):
        rows = by_subject.get(subject, ())
        sentence = _node_sentence(subject, typed[subject], rows, records)
        anchor = next(row for row in rows if row.predicate == TYPE_PREDICATE)
        projected[anchor.record_id] = sentence
        for row in rows:
            if row.record_id != anchor.record_id and row.predicate in _SATELLITE:
                projected[row.record_id] = ""

    held = claims(records)
    wrong = false_claims(records)
    believed = {
        record.object_ref
        for record in records
        if record.predicate == BELIEVES and record.object_ref
    }
    for record in records:
        if record.record_id in projected:
            continue
        plain = _record_sentence(record, held, wrong, believed, records)
        if plain is not None:
            projected[record.record_id] = plain
    return projected


def _node_sentence(
    subject: str,
    node_type: str,
    rows: Sequence[lc.StateRecord],
    records: Sequence[lc.StateRecord],
) -> str:
    parts: dict[str, list[lc.StateRecord]] = {}
    for row in rows:
        parts.setdefault(row.predicate, []).append(row)

    def one(predicate: str) -> lc.StateRecord | None:
        found = parts.get(predicate)
        return found[0] if found else None

    if node_type == CRITERION:
        comparator = one(COMPARATOR_PREDICATE)
        judged = one(EVALUATES_PREDICATE)
        ladder = ladder_of(records, subject)
        whom = judged.object_ref if judged is not None and judged.object_ref else "a subject"
        text = f"{subject} is how {whom} is judged"
        if comparator is not None:
            text += f", on a {str(comparator.value).replace('_', ' ')} scale"
        if ladder:
            text += f": {' then '.join(ladder)}"
        return text

    if node_type == CARDINALITY_CONSTRAINT:
        predicate = one(PREDICATE_PREDICATE)
        maximum = one(MAXIMUM_PREDICATE)
        scope = one(SCOPE_PREDICATE)
        name = str(predicate.value or predicate.object_ref or "?") if predicate else "?"
        limit = maximum.value if maximum is not None else "?"
        where = (
            f" for anything that is a {scope.object_ref or scope.value}"
            if scope is not None and (scope.object_ref or scope.value) not in (None, ANY_SCOPE)
            else ""
        )
        # **The exception is rendered with the rule or it is not a fact the writer has.** A
        # packet that carried "at most one owner per trait" and, separately, "kell is the
        # exception to c_one_owner_per_trait" would hand the writer a rule and an id, and the
        # scene that has to show the difference would be written against the rule. Absent for
        # every shape that excepts nobody, which is every shape forged before this existed.
        excepted = sorted(
            {
                row.object_ref
                for row in parts.get(EXCEPTS_PREDICATE, ())
                if row.object_ref
            }
        )
        unless = f", except for {', '.join(excepted)}" if excepted else ""
        return f"at most {limit} {name.replace('_', ' ')}{where} at one time{unless}"

    if node_type == VIEW:
        substrate = one(VIEW_SUBSTRATE)
        mapping = one(VIEW_MAPPING)
        withholds = one(VIEW_WITHHOLDS)
        text = f"{subject} is what the world shows"
        if substrate is not None and substrate.object_ref:
            text += f" of {substrate.object_ref}"
        if mapping is not None and mapping.value:
            text += f": {mapping.value}"
        if withholds is not None and withholds.value:
            text += f". It does not show: {withholds.value}"
        return text

    # A change. One occurrence with many roles, which is the whole reason it is reified.
    clauses: list[str] = []
    for role in CHANGE_ROLES:
        for row in parts.get(role, ()):
            target = row.object_ref or (str(row.value) if row.value is not None else "")
            if not target:
                continue
            detail = (
                f" ({row.value})" if row.object_ref and row.value is not None else ""
            )
            clauses.append(f"{_ROLE_PHRASE[role]} {target}{detail}")
    body = "; ".join(clauses) if clauses else "no roles recorded"
    return f"{subject} happened — {body}"


def _record_sentence(
    record: lc.StateRecord,
    held: Mapping[str, str],
    wrong: frozenset[str],
    believed: set[str],
    records: Sequence[lc.StateRecord] = (),
) -> str | None:
    """English for one record, or `None` to leave it to `state.describe`."""
    value = record.value if isinstance(record.value, str) else None
    if record.predicate == WORLD_RULE_PREDICATE and value:
        return f"Rule — {value}"
    if record.predicate == CONSEQUENCE_PREDICATE and value:
        domain = (record.object_ref or "").replace("_", " ")
        return f"Because of {record.subject}, in {domain}: {value}"
    if record.predicate == MANIFESTS_PREDICATE and value:
        return f"{record.subject} shows on the page as: {value}"
    # **The exception, its edge and its price, as three facts and no instruction.** The register
    # is the one the rules and manifestations already use: what is so, never what to do about it.
    # A sentence here that said "open on them" or "make the reader like them" would be this
    # system's own taste arriving in every packet, which is the boundary stage-0 §95 draws and
    # `plan/handoff-protagonist.md` boundary 1 restates for this field in particular.
    if record.predicate == EXCEPTION_PREDICATE and record.object_ref:
        return f"{record.subject} is the one the rule {record.object_ref} does not hold for"
    if record.predicate == EDGE_PREDICATE and value:
        return f"{record.subject} alone can: {value}"
    # **The inventory, in English.** Until these four branches existed a person's abilities
    # reached the writer as `state.describe`'s flat fallback — `sera can_do (cap_walk_between)` —
    # and landed in the world brief's `other` bucket, which is the failure `worlds.py`'s own
    # docstring calls the gate on the model being usable at all. Facts, in the register the
    # branches above use: what is so, never an instruction to show it off.
    # **Exactly the three predicates no world has ever emitted**, and that is the constraint
    # rather than an accident. `costs`, `permits` and `member` are also illegible today and also
    # wanted a sentence — and every one of them is already written by `records_for` for ranks and
    # bonds, so giving them one would change the packet of all thirteen worlds forged before this
    # and break the byte-identity rail. They keep `state.describe`'s flat form until somebody
    # pays for that change deliberately; `costs` reads acceptably flat, which is why a
    # capability's price reuses it rather than inventing a legible twin.
    if record.predicate == CAN_DO and record.object_ref:
        return f"{record.subject} can do {record.object_ref}"
    if record.predicate == REQUIRES and record.object_ref:
        return f"{record.subject} needs {record.object_ref} first"
    if record.predicate == TAUGHT_BY and record.object_ref:
        return f"{record.subject} is taught by {record.object_ref}"
    if record.predicate == PRICE_PREDICATE and value:
        return f"It costs {record.subject}: {value}"
    if record.predicate == ENTITY_ROLE_PREDICATE:
        return ""
    if record.predicate == PRECEDES_PREDICATE and record.object_ref:
        return f"{record.subject} ranks below {record.object_ref}"
    # **The standing reads as a fact and carries its number**, because the packet is where the
    # writer meets it and "kell stands_at two_wood" is notation. The count is
    # `rung_index`'s and is rendered only when the chain gives one — a partial order reaches the
    # writer as a position with no number, which is what it is. No verb about rising and no
    # adjective: where somebody stands is the same class of fact as what a rule costs.
    if record.predicate == STANDS_AT_PREDICATE and record.object_ref:
        criterion = str(record.value or "").strip() or criterion_of_rung(
            records, record.object_ref
        )
        chain = ladder_of(records, criterion) if criterion else ()
        index = chain.index(record.object_ref) + 1 if record.object_ref in chain else None
        where = f" ({index} of {len(chain)})" if index is not None else ""
        return f"{record.subject} stands at {record.object_ref}{where}"
    if record.predicate == CLAIM_CONTENT and value:
        # **A false claim's content is folded and a true one's is not**, and the asymmetry is
        # the point. A world's error belongs to whoever holds it, so the `believes` edge below
        # carries it with the holder attached; standing alone under "established facts" it would
        # read as one. A true claim stands on its own — in the hidden section when nobody has
        # been told, in the facts once they have.
        if record.subject in wrong:
            return ""
        return value
    if record.predicate == BELIEVES and record.object_ref:
        content = held.get(record.object_ref)
        if content is None:
            return f"{record.subject} believes {record.object_ref}"
        # **Believes, never knows**, and the qualifier when the world says the belief is wrong.
        # The distinction is the one §3.4 exists to keep: truth, belief and disclosure are three
        # things, and a writer handed "Silas knows X" about a false belief writes a different
        # scene from one handed "Silas believes X, and it is not so".
        #
        # A colon rather than "that", because half these claims are written starting with
        # "That …" and the first live world produced "believes, wrongly, that That the register
        # is honest bookkeeping". A joiner that depends on the next word's grammar is a joiner
        # that will be wrong on some of them.
        if record.object_ref in wrong:
            return f"{record.subject} believes, wrongly: {content}"
        return f"{record.subject} believes: {content}"
    if record.predicate in (DISCLOSED_TO, CLAIM_FALSE, QUESTION_PREDICATE, REVEAL_SCENE):
        return ""
    if record.predicate == GRAPH_LINE_PREDICATE:
        return ""
    return None


__all__ = [
    "ANY_SCOPE",
    "ARCHITECT_AUTHOR_PREFIX",
    "ARCHITECT_ID_PREFIX",
    "BELIEVES",
    "BUNDLE_MEMBER",
    "CAN_DO",
    "CARDINALITY_CONSTRAINT",
    "CHANGE",
    "CHANGE_ROLES",
    "CLAIM_CONTENT",
    "CLAIM_FALSE",
    "COMPARATORS",
    "COMPARATOR_PREDICATE",
    "CONSEQUENCE_DOMAINS",
    "CONSEQUENCE_PREDICATE",
    "CONSTRAINT",
    "COSTS",
    "CRITERION",
    "DISCLOSED_TO",
    "EDGE_PREDICATE",
    "ENTITY_ROLES",
    "ENTITY_ROLE_PREDICATE",
    "EVALUATES_PREDICATE",
    "EVALUATION_CRITERION",
    "EVALUATION_RESULT",
    "EVALUATION_SUBJECT",
    "EXCEPTION_PREDICATE",
    "EXCEPTS_PREDICATE",
    "GRAPH_LINE_PREDICATE",
    "GROUP_KEYS",
    "GROUP_KEY_PREDICATE",
    "MANIFESTS_PREDICATE",
    "MAXIMUM_PREDICATE",
    "MEMBER",
    "NODE_TYPES",
    "PERMITS",
    "PRECEDES_PREDICATE",
    "PREDICATE_PREDICATE",
    "PRICE_PREDICATE",
    "QUESTION_PREDICATE",
    "READER",
    "RECOGNIZED_BY",
    "REGISTRY_VERSION",
    "REQUIRES",
    "REVEAL_SCENE",
    "SCOPE_PREDICATE",
    "STANDS_AT_PREDICATE",
    "TAUGHT_BY",
    "TYPE_PREDICATE",
    "VIEW",
    "VIEW_MAPPING",
    "VIEW_SUBSTRATE",
    "VIEW_WITHHOLDS",
    "WORLD_RULE_PREDICATE",
    "CardinalityShape",
    "Coverage",
    "IllegalWorld",
    "Protagonist",
    "architect_id_for",
    "capabilities",
    "capabilities_of",
    "cardinality_shapes",
    "claims",
    "consequence_domains",
    "criteria",
    "criterion_brief",
    "criterion_of_rung",
    "disclosures",
    "entities_with_role",
    "entity_roles",
    "false_claims",
    "features",
    "group_of",
    "hidden_record_ids",
    "in_scope",
    "is_machine_author",
    "key_nouns",
    "ladder_of",
    "machine_author",
    "manifestation_coverage",
    "nodes_of_type",
    "normalise_id",
    "project",
    "protagonist_brief",
    "questions",
    "rank_order",
    "record_id_for",
    "requirement_depth",
    "reveal_scenes",
    "rules",
    "rung_index",
    "standing_of",
    "undisclosed_claims",
    "validate",
    "world_record",
]
