"""The game system a book runs on, one character's position in it, and what it offers them next.

**The fork arrived on 2026-08-30, and it is the object read 10 says was missing.** The operator,
on serial pilot 15b draw 4: a rendered status line arriving at a number-move reads as *noise*,
because the system is not a thing anybody in the book opens, reads or weighs. Their direction is
that inner deliberation over what to take next is a large part of the story, which
`plan/house-genre-constraint.md` had already queued as a schema note — a class concept, carrying
the operator's original awe direction (*"i wonder what I would get and pick"*) natively. So
`Choice` and `Option` join `Ability` and `Rank`, `CharacterSheet` gains the ways one person has
taken, and `legal_moves` will not offer what a fork gates until its fork is taken. The quotes live
in `plan/`; none of them is in any prompt (§97.1), and nothing in this module is rendered into a
call.

**Everything below is defaulted so that a system with no fork is the system it always was**: the
records are the same records, the digest is the same digest, and no book on disk moves.
`plan/diegetic-system-and-choice.md` is the design record and stage-0 §173 the decision.


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

**Layout since 2026-09-03 (stage-0 §216).** The definition, a position in it, the draw check and
how both are written down live in `domain/systems.py`; the arithmetic of advancing a sheet in
`domain/advancement.py`; this module keeps reading a system and a position back out of canon
(`systems_of`, `sheet_of`, `changes_of` and the growth readers) and re-exports every name the
other two define, so `gamesystem.legal_moves` is still where a caller reads it. Everything this
docstring says holds across the three, and `docs/system-model.md` says which is the home of
which fact.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import litharness_contracts as lc

from litharness.domain import state as state_mod
from litharness.domain import worlds as worlds_mod
from litharness.domain.advancement import (
    OFFER_TAG,
    advance,
    choose,
    deepen,
    gain,
    legal_moves,
    offer_line,
    offered_options,
    pending_choices,
    rise,
)
from litharness.domain.systems import (
    CONFIGURATION_PREDICATES,
    LABEL_CHARS,
    MAGNITUDE_SCALE,
    MAX_ABILITIES,
    MAX_OPTIONS,
    MAX_SCALE_MAXIMUM,
    MIN_ABILITIES,
    MIN_OPTIONS,
    MIN_RANKS,
    MIN_SCALE_MAXIMUM,
    RANK_KEY,
    REGISTRY_VERSION,
    SYSTEM_DIGEST,
    Ability,
    AdvanceKind,
    Advancement,
    Change,
    CharacterSheet,
    Choice,
    Column,
    Furniture,
    IllegalAdvance,
    MalformedSystem,
    Move,
    Need,
    Option,
    Rank,
    Scale,
    SystemDef,
    check_draw,
    records_for,
    records_for_sheet,
    starting_sheet,
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
        system = _assemble(records, system_id, Scale(label=label, maximum=maximum), names, governed)
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
            per_rung=_first_int(records, ability_id, worlds_mod.PER_RUNG),
            price=_price_of(records, ability_id),
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
        choices=_choices_of(records, system_id, governed, names, set(chain)),
    )

def _choices_of(
    records: Sequence[lc.StateRecord],
    system_id: str,
    governed: Mapping[str, str],
    names: Mapping[str, str],
    rank_ids: set[str],
) -> tuple[Choice, ...]:
    """The forks this system offers, read off its own edges.

    **A fork is found structurally and carries no `entity_role`**, which is a decision rather than
    an omission. `worlds.ENTITY_ROLES` tags subjects a *counter* has to find — the bestiary and
    the manifestation checks are what it was added for — and nothing counts forks; a role no
    reader reads is one more thing an Architect can get wrong, and one more line in the surface
    §163 measured an omission from as indistinguishable from a prohibition. So a fork is a subject
    `governed_by` this system carrying `offers` edges, the way a criterion is a subject carrying a
    comparator.

    A subject that is `governed_by` the system and offers nothing is not a fork here and is not
    complained about either: `_assemble` already skips it as an ability unless it is a declared
    capability, and `genre.system_gap` is where a half-built system is reported.
    """
    found: list[Choice] = []
    for subject in sorted(candidate for candidate, owner in governed.items() if owner == system_id):
        option_ids = worlds_mod.offered_by(records, subject)
        if not option_ids:
            continue
        opens = [
            record.object_ref
            for record in records
            if record.predicate == worlds_mod.REQUIRES
            and record.subject == subject
            and record.object_ref in rank_ids
        ]
        found.append(
            Choice(
                choice_id=subject,
                name=names.get(subject, subject),
                options=tuple(
                    Option(
                        option_id=option_id,
                        name=names.get(option_id, option_id),
                        grants=worlds_mod.granted_by(records, option_id),
                        costs=_first_value(records, option_id, worlds_mod.COSTS),
                        manifests_as=_first_value(
                            records, option_id, worlds_mod.MANIFESTS_PREDICATE
                        ),
                        needs=_needs_of(records, option_id),
                    )
                    for option_id in option_ids
                ),
                # Sorted rather than first-seen, for `_assemble`'s round-trip reason. A `Choice`
                # holds one opening rung so a *drawn* system can never write two, but a world
                # declared by hand can, and taking whichever record the store returned first
                # would make the same canon read back differently on two reads.
                opens_at=sorted(opens)[0] if opens else None,
            )
        )
    return tuple(found)

def drawn_digests(records: Sequence[lc.StateRecord]) -> dict[str, str]:
    """Each system's digest as it was drawn, off the `system_digest` record acceptance
    minted (§211): the string a seed wrote before §212.1, or the `digest` of the object a
    seed writes since. A system with none was never completed and is `unfinished_systems`'."""
    found: dict[str, str] = {}
    for record in records:
        if record.predicate != SYSTEM_DIGEST:
            continue
        if isinstance(record.value, str):
            found[record.subject] = record.value
        elif isinstance(record.value, Mapping) and isinstance(record.value.get("digest"), str):
            found[record.subject] = record.value["digest"]
    return found

def drawn_grants(records: Sequence[lc.StateRecord]) -> dict[str, tuple[str, ...]]:
    """Each system's grants as it was drawn (§212.1), off the `system_digest` record of a
    seed written since that entry; a seed that wrote the digest alone recorded no grant list
    and is absent here, so nothing is guessed about what it drew."""
    found: dict[str, tuple[str, ...]] = {}
    for record in records:
        if record.predicate != SYSTEM_DIGEST or not isinstance(record.value, Mapping):
            continue
        grants = record.value.get("grants")
        if isinstance(grants, list) and all(isinstance(item, str) for item in grants):
            found[record.subject] = tuple(sorted(grants))
    return found

def growth(
    records: Sequence[lc.StateRecord],
) -> tuple[tuple[SystemDef, tuple[str, ...], tuple[str, ...]], ...]:
    """Every system whose grants differ from the ones drawn, with the grants added since and
    what is wrong with it now, if anything (§211, corrected by §212.1).

    **Growth is a grant set and not a digest.** The first reading compared the live digest
    with the drawn one, and on pilot 25's stored book reported its fork system as grown with
    not one record declared since the seed: the digest's own material had moved with the
    code (a fork's ways joined it after that seed), so a digest identifies a system within
    one version and not across them. What growth is about is the grants, and the seed now
    writes the list it drew beside the digest; a system whose seed wrote the digest alone
    is left out rather than guessed at.

    **Reported, never refused, and the drawn record is left as it was.** A grant declared
    after the seed is what a book handing things out looks like, and a second
    `system_digest` record beside the first would be two canon values at one slot — the
    contradiction detector's own shape, with no retraction to clear it. The complaints are
    `check_draw`'s with the draw's count bound off, since the bound is on the draw; a grown
    system that runs its prerequisites in a cycle is still broken.
    """
    drawn = drawn_grants(records)
    found: list[tuple[SystemDef, tuple[str, ...], tuple[str, ...]]] = []
    for system in systems_of(records):
        was = drawn.get(system.system_id)
        if was is None or was == tuple(sorted(system.ability_ids)):
            continue
        added = tuple(sorted(set(system.ability_ids) - set(was)))
        found.append((system, added, check_draw(system, drawn=False)))
    return tuple(found)

def unfinished_systems(records: Sequence[lc.StateRecord]) -> tuple[str, ...]:
    """Each system these records began and `systems_of` cannot read back, with what it lacks.

    **Empty is a legal answer for `systems_of`, and it is two different answers** (Serial
    Pilots 15 §2.1 and 15b §5): a world that declared nothing and a world one predicate short
    both read back as no system, and a caller that cannot tell them apart tells the second the
    first's sentence — three false clauses, §155.2's operator sent hunting the wrong absence,
    while `world accept` names the true one on a channel nobody watches. This is the teller.

    A candidate is a subject holding the system role, or one a governed criterion answers to;
    what each lacks is measured against `systems_of`'s own requirements, in this module rather
    than at the report's, for `_assemble`'s reason — a second reading of what a declared system
    is would eventually disagree with the reader it describes. Complete systems contribute
    nothing here, so on a finished world this is empty and the report side stays silent.
    """
    scales = {
        record.subject: record.value
        for record in records
        if record.predicate == MAGNITUDE_SCALE and isinstance(record.value, Mapping)
    }
    governed: dict[str, str] = {}
    for record in records:
        if record.predicate == worlds_mod.GOVERNED_BY and record.object_ref:
            governed[record.subject] = record.object_ref
    criterion_nodes = worlds_mod.criteria(records)
    holders = set(worlds_mod.entities_with_role(records, "system"))
    owners = {owner for subject, owner in governed.items() if subject in criterion_nodes}

    unfinished: list[str] = []
    for system_id in sorted(holders | owners):
        missing: list[str] = []
        if system_id not in holders:
            missing.append(
                f"the system {worlds_mod.ENTITY_ROLE_PREDICATE} (a governed ladder answers "
                "to it and nothing declares it a system)"
            )
        scale_value = scales.get(system_id)
        maximum = scale_value.get("maximum") if isinstance(scale_value, Mapping) else None
        if not isinstance(maximum, int) or isinstance(maximum, bool):
            missing.append(
                f"a {MAGNITUDE_SCALE} (minted at `world accept`, never declared by hand)"
            )
        owned = sorted(
            subject
            for subject, owner in governed.items()
            if owner == system_id and subject in criterion_nodes
        )
        if not owned:
            missing.append(
                f"a governed ordinal ladder (no criterion is {worlds_mod.GOVERNED_BY} it)"
            )
        elif len(owned) > 1:
            missing.append(
                f"a single ladder ({len(owned)} criteria are {worlds_mod.GOVERNED_BY} it, "
                "and a reader that chose between them would be inventing which one the "
                "world meant)"
            )
        elif not worlds_mod.ladder_of(records, owned[0]):
            missing.append(
                f"a {worlds_mod.PRECEDES_PREDICATE} chain ({owned[0]}'s results do not "
                "form one ladder)"
            )
        if missing:
            unfinished.append(f"{system_id} lacks {' and '.join(missing)}")
    return tuple(unfinished)

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
        skeleton = _assemble(records, system_id, Scale(label="", maximum=0), names, governed)
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
        minted.extend(record for record in drawn if record.predicate in CONFIGURATION_PREDICATES)
    return tuple(minted), tuple(reasons)

def _declared_depth(records: Sequence[lc.StateRecord], ability_ids: Sequence[str]) -> int | None:
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

def _first_value(records: Sequence[lc.StateRecord], subject: str, predicate: str) -> str | None:
    for record in records:
        if (
            record.subject == subject
            and record.predicate == predicate
            and isinstance(record.value, str)
            and record.value.strip()
        ):
            return record.value
    return None

def _first_int(records: Sequence[lc.StateRecord], subject: str, predicate: str) -> int:
    """The first whole number a subject's records give the predicate, or 0 for none (§210)."""
    for record in records:
        if (
            record.subject == subject
            and record.predicate == predicate
            and isinstance(record.value, int)
            and not isinstance(record.value, bool)
        ):
            return record.value
    return 0

def _price_of(records: Sequence[lc.StateRecord], ability_id: str) -> tuple[tuple[str, int], ...]:
    """What a grant is paid in: every `costs` record with a stock in the object slot and a
    whole number in the value slot (§210). Prose about a price fills the value slot alone and
    is `_first_value`'s, so the two shapes cannot be mistaken for one another."""
    return tuple(
        sorted(
            (record.object_ref, record.value)
            for record in records
            if record.subject == ability_id
            and record.predicate == worlds_mod.COSTS
            and record.object_ref
            and isinstance(record.value, int)
            and not isinstance(record.value, bool)
        )
    )

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

def changes_of(
    records: Sequence[lc.StateRecord], character: str, *, system: SystemDef
) -> tuple[Change, ...]:
    """Every canon change declared as happening to `character` with an effect on one of this
    system's grants, in position order (§212).

    A change is a subject of `type change` (the node the vocabulary has carried since the
    research ontology, and the Architect has used as a story event with no roles); one with a
    `participant` edge to this person and an `effect` edge naming a grant of this system with
    a whole number is one the sheet reads. Effects on grants this system does not declare are
    left to `worlds.validate`, which complains about a role pointing at an undeclared
    subject; a value that is not a whole number is `slot_warnings`' to name.
    """
    canon = [record for record in records if state_mod.is_canon(record)]
    anchors = {
        record.subject: record
        for record in canon
        if record.predicate == worlds_mod.TYPE_PREDICATE
        and str(record.value or "").strip() == worlds_mod.CHANGE
    }
    grants = set(system.ability_ids)
    found: list[Change] = []
    for change_id in sorted(anchors):
        rows = [record for record in canon if record.subject == change_id]
        if not any(
            record.predicate == worlds_mod.PARTICIPANT_ROLE and record.object_ref == character
            for record in rows
        ):
            continue
        effects = tuple(
            sorted(
                (record.object_ref, record.value)
                for record in rows
                if record.predicate == worlds_mod.EFFECT_ROLE
                and record.object_ref in grants
                and isinstance(record.value, int)
                and not isinstance(record.value, bool)
            )
        )
        if not effects:
            continue
        found.append(
            Change(change_id, character, state_mod.order_key_of(anchors[change_id]), effects)
        )
    return tuple(sorted(found, key=lambda change: change.at or ""))

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
    rank_id = max(standings, key=lambda record: state_mod.order_key_of(record) or "").object_ref
    assert rank_id is not None

    # **A declared change is read beside the edges, and the latest statement wins** (§212).
    # A `can_do` edge and a change's effect are both statements of what a grant stands at
    # from a position on; folding them into one timeline keyed by position is what keeps the
    # sheet one arithmetic. At one position the change wins, because it is the reified
    # occurrence and the edge is its bare consequence.
    declared = [
        (change.at, ability_id, magnitude)
        for change in changes_of(records, character, system=system)
        for ability_id, magnitude in change.effects
        if at is None
        or change.at is None
        or (state_mod.comparable(change.at, at) and change.at <= at)
    ]
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
        changed = [
            (key or "", magnitude)
            for key, changed_id, magnitude in declared
            if changed_id == ability_id
        ]
        if not holdings and not changed:
            magnitudes.append((ability_id, 0))
            continue
        magnitude = 0
        if holdings:
            latest = max(holdings, key=lambda record: state_mod.order_key_of(record) or "")
            visible.update(latest.pov_visibility)
            value = latest.value
            magnitude = value if isinstance(value, int) and not isinstance(value, bool) else 1
        if changed:
            change_key, change_magnitude = max(changed, key=lambda item: item[0])
            edge_key = state_mod.order_key_of(latest) or "" if holdings else ""
            if not holdings or change_key >= edge_key:
                magnitude = change_magnitude
        magnitudes.append((ability_id, max(0, magnitude)))

    # **The picks, read off the same edges under the same cutoff.** A `chose` is a fact about the
    # book at a position, exactly as a `stands_at` is, so `within` decides it: a scheduled pick in
    # the other order-key space is canon, readable, and never read as already taken (§165, §167).
    # A pick naming a fork or a way this system does not declare is dropped rather than guessed
    # at — the world said something this reader cannot place, and `worlds.slot_warnings` is where
    # a declaration is told so.
    taken: list[tuple[str, str, str]] = []
    for record in records:
        if record.predicate != worlds_mod.CHOSE or record.subject != character:
            continue
        if not record.object_ref or not state_mod.is_canon(record) or not within(record):
            continue
        choice_id = str(record.value or "").strip()
        if choice_id not in set(system.choice_ids):
            continue
        if record.object_ref not in set(system.choice(choice_id).option_ids):
            continue
        taken.append((choice_id, state_mod.order_key_of(record) or "", record.object_ref))
    # **The earliest pick wins, and it is a fork's own rule rather than a tie-break.** A fork is
    # taken once; a second `chose` on one fork is the world contradicting itself, and keeping the
    # later one would let a redeclaration quietly un-take a branch nothing can retract. Ties at
    # one position resolve by option id, because the alternative is store row order — which is
    # what §170 measured deciding whose interface a whole chapter printed.
    picks: dict[str, str] = {}
    for choice_id, _key, option_id in sorted(taken):
        picks.setdefault(choice_id, option_id)

    return CharacterSheet(
        system=system,
        character=character,
        rank_id=rank_id,
        magnitudes=tuple(magnitudes),
        visible_to=tuple(sorted(visible)),
        picks=tuple(sorted(picks.items())),
    )


__all__ = [
    "CONFIGURATION_PREDICATES",
    "LABEL_CHARS",
    "MAGNITUDE_SCALE",
    "MAX_ABILITIES",
    "MAX_OPTIONS",
    "MAX_SCALE_MAXIMUM",
    "MIN_ABILITIES",
    "MIN_OPTIONS",
    "MIN_RANKS",
    "MIN_SCALE_MAXIMUM",
    "OFFER_TAG",
    "RANK_KEY",
    "REGISTRY_VERSION",
    "SYSTEM_DIGEST",
    "Ability",
    "AdvanceKind",
    "Advancement",
    "Change",
    "CharacterSheet",
    "Choice",
    "Column",
    "Furniture",
    "IllegalAdvance",
    "MalformedSystem",
    "Move",
    "Need",
    "Option",
    "Rank",
    "Scale",
    "SystemDef",
    "advance",
    "changes_of",
    "check_draw",
    "choose",
    "completion_records",
    "deepen",
    "drawn_digests",
    "drawn_grants",
    "gain",
    "growth",
    "legal_moves",
    "offer_line",
    "offered_options",
    "pending_choices",
    "records_for",
    "records_for_sheet",
    "rise",
    "sheet_of",
    "starting_sheet",
    "systems_of",
    "unfinished_systems",
]
