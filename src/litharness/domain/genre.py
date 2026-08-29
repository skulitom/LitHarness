"""The house genre floor: a book that cannot speak system voice may not be drafted.

The operator, 2026-08-29, on first sight of pilot 13's book:

    "One big problem i noticed right away with the book. It's not litrpg... we shouldn't be
    writing any books that don't have litrpg as the genre"

**That quote lives here and may not travel.** §97.1: an operator's words are direction where
direction enters, and they are never prompt text. Nothing in this module is rendered into any
call; it decides, and the decision is a refusal with a reason.

**What the constraint names, precisely.** Pilot 13 had the whole progression *structure* —
three resolving ladders, ranks worn on the body, 316 countable skies, every piece of §113's
machinery — and no LitRPG *system*: no status furniture, no sheet, no interface the character
reads. A world can satisfy every progression check this project owns and still not be the genre
it publishes in. So the floor is not about ladders. It is about whether anybody in the book can
read a screen.

**Why this is a floor and not a message.** The pipeline already diagnosed the exact condition,
out loud, on two separate databases, and drafted the book anyway:

    0 seed state record(s)
    no state seeded — a LitRPG book needs a starting sheet to speak system voice

It observed the thing the operator later named and proceeded, because there was nothing for it
to fail against (`plan/serial-pilot-13.md` §8.2). This module is the thing to fail against. The
report stays where it was — `cmd_new` still prints at creation, when seeding is cheap — and the
gate is here, so the shape is report-then-gate rather than one or the other.

**The mechanism is the chain that was already broken at its first link.** A book whose canon
holds no `status_snapshot` is never *asked* for system voice, so it writes none, so the
extractor reads none back, so it never acquires one: `speaks_system_voice` is False forever and
the absence is self-sustaining. The seed is the only place the chain can start, which is why the
floor sits on the seed rather than on the prose. Nothing here reads a draft or judges one.

**Deliberately not here.** No claim that a seeded sheet makes a book good, no count of system
lines, no threshold on how much furniture is enough, and no opinion about any book's prose. This
answers one yes/no question about canon: can this book speak system voice at all.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import litharness_contracts as lc

from litharness.domain import gamesystem as gamesystem_mod
from litharness.domain import state as state_mod
from litharness.domain.extraction import (
    SHEET_PREDICATE,
    STATUS_PREDICATE,
    speaks_system_voice,
)

#: The genre every book this house publishes is in. A constant rather than a per-book setting,
#: because the operator's constraint is about the house and not about a shelf: a book's shelf
#: may be cozy, mystery or historical, and it carries the system furniture anyway.
HOUSE_GENRE = "LitRPG"

#: What `cmd_new` prints at creation, and what the floor refuses with, share this sentence so
#: an operator who ignored the first sees the same words in the second. One string, two
#: surfaces, no drift — `tests/test_genre_floor.py` pins that they are the same string.
NO_SHEET = (
    f"no state seeded — a {HOUSE_GENRE} book needs a starting sheet to speak system voice"
)


def has_starting_sheet(records: Sequence[lc.StateRecord]) -> bool:
    """Whether this book's canon can speak system voice at all.

    Delegates to `extraction.speaks_system_voice` rather than restating its predicate: a second
    definition of what a starting sheet is would be a second answer to the same question, and
    the one that matters is the one the *writer's* prompt already consults. If they disagreed,
    a book could pass this floor and still never be asked for a status line, which is exactly
    the silent condition the floor exists to end.

    **That disagreement happened anyway, and the delegation alone did not prevent it**
    (Serial Pilot 14 §2.2 and §7, corrected into §155.2 as §158). The writer's prompt asks
    through `system_voice_example`, which renders numbers out of a mapping, while
    `speaks_system_voice` counted any canon snapshot — so a prose-valued sheet, the only
    shape `world declare --value` could then carry, cleared the floor and the writer was
    never asked. The repair is in the delegate, where this docstring's own argument says it
    belongs: `speaks_system_voice` now requires the mapping the ask renders from, and the
    floor inherits the promise instead of restating it.

    A `PROPOSED` snapshot does not count, and that is `speaks_system_voice`'s rule rather than
    one added here: the outline's milestone schedule mints `PROPOSED` status records, so
    counting them would let a book satisfy the floor with its own plan for later instead of
    with a sheet that is true now.

    **§160 makes this a ratchet rather than a second tightening.** A book that declares no game
    system is answered exactly as before — the delegate's question and nothing else — so no book
    or fixture already on disk moves. A book that *does* declare one must hold a sheet that is a
    real position in it. The two halves are one rule stated once: the floor asks whether this
    book's sheet is the sheet its own canon implies, and for a book with no system the implied
    sheet is any renderable mapping.

    A flag would have been the obvious alternative and is the thing §155.2 argues against one
    door along: a switch somebody has to flip is a switch somebody forgets, and the moment seeds
    mint systems every new book is under the strict half automatically, with nothing to remember.
    """
    if not speaks_system_voice(records):
        return False
    declared = _declared_systems(records)
    if not declared:
        return True
    return any(_is_position_in(records, system) for system in declared)


def _declared_systems(
    records: Sequence[lc.StateRecord],
) -> tuple[gamesystem_mod.SystemDef, ...]:
    """The systems this book's **canon** declares.

    Canon-filtered, unlike `gamesystem.systems_of` itself, and the difference is the whole reason
    the ratchet is safe. That function deliberately reads proposals too, because the Architect
    builds a system before `world accept` and a reader that saw nothing until acceptance would
    report an empty world mid-build. The floor is the opposite case: a proposal is not yet this
    book's system, and tightening against one would refuse a book for a draw nobody accepted.
    """
    return gamesystem_mod.systems_of(
        [record for record in records if state_mod.is_canon(record)]
    )


def _canon_snapshots(records: Sequence[lc.StateRecord]) -> tuple[Mapping[str, object], ...]:
    return tuple(
        record.value
        for record in records
        if record.predicate == STATUS_PREDICATE
        and state_mod.is_canon(record)
        and isinstance(record.value, Mapping)
    )


def _is_position_in(
    records: Sequence[lc.StateRecord], system: gamesystem_mod.SystemDef
) -> bool:
    """Whether some canon snapshot is a position in this system.

    **Compared by value keys and not by numbers.** Which rung somebody stands on and how far
    they have taken a capacity are facts about the book that this module has no business
    checking; what it checks is that the sheet and the system are speaking about the same
    columns. A snapshot whose keys are the system's is renderable through the system's own line;
    one whose keys are not will render the wrong labels, or `?` where a value is missing, which
    is the defect Track 2 measured on the default sheet and the one this floor exists to catch a
    generation earlier.
    """
    wanted = set(system.value_keys)
    return any(set(snapshot) == wanted for snapshot in _canon_snapshots(records))


def system_gap(records: Sequence[lc.StateRecord]) -> str | None:
    """What stands between this book and a sheet its own system implies, or `None`.

    **A report and not a gate**, which is the shape `genre_block`'s docstring already argues for:
    the report belongs where seeding is cheap and the refusal belongs in front of the spend. A
    book can be perfectly draftable and still be reported on here — a book with no system clears
    the floor and is told what it is missing, because saying nothing is how §155.2's condition
    went unnamed on two databases while the pipeline drafted anyway.

    The first branch is the one that cost the most to find. `extraction.sheet_for` abstains to
    the default when a book declares more than one sheet, so a second declaration does not
    error — it silently restores a column set the book never chose, and a book that had seeded
    its own keys is then shown a line with placeholders where its numbers were.

    **The empty answer is two answers, and the split is the fix for Serial Pilots 15 §2.1 and
    15b §5.** `_declared_systems` is empty for a world that declared nothing and for a world
    one predicate short, and the second used to be told the first's sentence — three false
    clauses about a world holding the system role, a governed ladder and the Architect's own
    sheet, which is §155.2's operator hunting the wrong absence while `world accept` named the
    true one on a channel nobody watches. `gamesystem.unfinished_systems` tells the two apart
    in the reader's own terms, so `check` and `accept` now name the same missing piece.
    """
    sheets = sum(
        1
        for record in records
        if record.predicate == SHEET_PREDICATE and state_mod.is_canon(record)
    )
    if sheets > 1:
        return (
            f"this book declares {sheets} canon {SHEET_PREDICATE} records; the status line "
            "abstains to the default when there is more than one, so the book renders a line "
            "it never chose and its own values are lost. Retract all but one."
        )
    declared = _declared_systems(records)
    if not declared:
        # Canon-filtered for `_declared_systems`' reason: a proposal is not yet this book's
        # system, and telling a world mid-build it began one and stopped would report the
        # ordinary state of every seed as a fault.
        unfinished = gamesystem_mod.unfinished_systems(
            [record for record in records if state_mod.is_canon(record)]
        )
        if unfinished:
            return (
                "this book began a game system and did not finish it: "
                + "; ".join(unfinished)
                + ". An unfinished system reads back as no system at all, so the sheet is "
                "never checked as a position in it and no beat speaks its ranks or "
                "abilities."
            )
        return (
            "this book declares no game system: no subject holds the system role with a "
            "magnitude scale and a governed ordinal ladder. Its sheet is whatever was seeded "
            "by hand, its numbers have no home, and a progression beat has no vocabulary to "
            "land in."
        )
    for system in declared:
        if _is_position_in(records, system):
            return None
    system = declared[0]
    held = _canon_snapshots(records)
    if not held:
        return (
            f"this book declares the system {system.system_id} and holds no canon "
            f"{STATUS_PREDICATE}; nobody is anywhere in it yet."
        )
    return (
        f"this book declares the system {system.system_id}, whose columns are "
        f"{', '.join(system.value_keys)}, and no canon {STATUS_PREDICATE} carries those keys; "
        "the sheet and the system are describing different books."
    )


def genre_block(records: Sequence[lc.StateRecord]) -> str | None:
    """Why this book may not proceed to drafting, or `None` if it may.

    A reason string rather than a bool because `plan_progress` records one: *"A blocked book
    reports its reason rather than looking finished"* — the same argument the no-premise block
    is written under, one door along.
    """
    if has_starting_sheet(records):
        return None
    # **The system half fails with its own sentence**, because the sentences below diagnose the
    # absence of a renderable snapshot and this book may hold one. §155.2's whole complaint is a
    # book being told the wrong absence and its operator hunting it; a book whose sheet does not
    # match its declared system would be told it had seeded nothing, which is false and sends
    # somebody to reseed a sheet that is already there.
    if speaks_system_voice(records):
        return system_gap(records)
    # Every canon snapshot counted here is unrenderable — a renderable one would have cleared
    # the floor above — and telling a book that holds one "none of them a canon status_snapshot"
    # sends the operator hunting the wrong absence. Serial Pilot 14 §2.2's book is what this
    # sentence is for: canon held the sheet, as prose, and nothing could render numbers from it.
    prose_sheets = sum(
        1
        for record in records
        if record.predicate == STATUS_PREDICATE and state_mod.is_canon(record)
    )
    held = len(records)
    if prose_sheets:
        seeded = (
            f"{prose_sheets} canon {STATUS_PREDICATE} record(s) whose value is prose rather "
            "than a mapping, which the status-line machinery cannot render numbers from"
        )
    elif held:
        seeded = f"{held} state record(s) on this branch, none of them a canon {STATUS_PREDICATE}"
    else:
        seeded = "no state records on this branch at all"
    return (
        f"{NO_SHEET}; {seeded}. Seed one with `new --state` or `import --state` before "
        f"drafting — or, on a book that already exists, `world declare <subject> "
        f"{STATUS_PREDICATE} --value '{{...}}' --order-key <key>` with the value a JSON "
        "object, then `world accept` — or this book writes no system voice and never reads "
        "any back."
    )


# --------------------------------------------------------------------------- the timing half

#: The operator, minutes after the seventh read, and then again minutes after that:
#:
#:     "When i read litrpg, i want to feel progress and potential and i want to see it as soon
#:     as possible. I don't want to read to the end of chapter 1 to see interesting progress"
#:
#:     "not just progress inside the opening, readers expect constant and regular progress.
#:     Well whatever activates dopamine receptors"
#:
#: Same rule as the quote above: it lives here and it is never rendered into a call.
#:
#: **The census is what makes this a schedule rather than an adjective**
#: (`research/quality-measurement/results/progression-cadence.json`, digest 5d42f2065efb7e09,
#: 13,364 LitRPG chapters over 584 fictions, code-only counters, no bar declared). Three of its
#: numbers bear on the design and one of them refutes the obvious reading of the operator's own
#: words:
#:
#: 1. **The opening half is the half the market fails.** Only 22.5% of LitRPG chapters place a
#:    located progression event inside their first 500 words, and the median chapter's first
#:    one lands at word 585. The operator's complaint — reading to the end of chapter 1 to see
#:    progress — is one the market earns three times out of four, so scene 1 is where the
#:    strongest evidence points.
#: 2. **The market is not regular, so this is a departure and not an imitation.** Among market
#:    chapters carrying two or more events the gap CV is 0.96, which is essentially Poisson:
#:    progression arrives in bursts a median of 89 words apart with long dry stretches between,
#:    and 51% of LitRPG chapters carry no located event at all. The operator asked for
#:    "constant and regular"; the market they read is neither. Nothing here claims to copy it.
#: 3. **A Poisson market is also the argument for scheduling at all.** If regularity were
#:    something prompt text produced, some corner of a 584-fiction market would show it. None
#:    does. A schedule is the only mechanism that has ever made a rhythm regular.
#:
#: **No bar is declared, here or anywhere.** `EVERY` is a placement in a measured distribution
#: rather than a threshold anything must clear: at roughly 950 words a scene, a beat every
#: second scene puts a book near the market's 65th percentile by density — deliberately above
#: the median it sits at now and well below its p90 — and the four attainability checks that a
#: bar would need (§81, §85, §87, §89) were not run, because nothing here is a bar.
EVERY = 2

#: What a scheduled scene's plan gains. Written as **material and not as an adjective**: it
#: names a thing that happens in the scene, the way the rest of a scene plan does, and it is
#: composed in code rather than asked for in prompt text.
#:
#: `plan/house-genre-constraint.md` named the hazard before anyone drafted a clause — *"show
#: progress immediately" as prompt text is a §138 formula waiting to happen* — and named this
#: altitude as the one that avoids it. So there is no quality word in this sentence and no
#: instruction to make anything good, exciting or felt: it says something countable moves and
#: the character is present for it, which is a fact a scene either contains or does not.
#:
#: It carries none of `house.MACHINERY_WORDS`. This text reaches the writer inside the scene
#: plan and therefore shapes prose a reader reads, and §120 measured `standing` reaching a
#: chapter when repo vocabulary got that far.
#: **Pronoun-free on purpose.** The first draft of this sentence said *"something he has been
#: counting"*, which would have written a male protagonist into the plan of every scheduled
#: scene of every book this house drafts, whoever the book is actually about. A scheduled item
#: that reaches every book may not assume anything about who is in it.
#: What both forms of the beat end with, and therefore the one string that answers "did the
#: schedule fire here" without knowing which form fired. Broken out when §161 gave the beat a
#: second form: a caller asking whether a scene carries a beat is asking about the schedule,
#: not about whether this particular book had a vocabulary to name, and a test that matched on
#: `BEAT` whole would have gone red on every book that did.
BEAT_TAIL = "moves here, and the person it belongs to is there when it does."

BEAT = f"One of the numbers this book counts {BEAT_TAIL}"

#: The same beat with the book's own word for the thing that moves in it. **The one change
#: §161 makes to this schedule, and it is addressability rather than emphasis** (§154): `BEAT`
#: above names a *category* — "one of the numbers this book counts" — and read 8 §4.2 measured
#: what a category buys. §157's beats fired on schedule twice in pilot 14 and the writer put
#: the progression into guild paperwork ranks, because a scheduled item that does not name
#: which quantity moves is satisfied by whichever ladder the world declared loudest, and the
#: world's loudest ladder was a bureaucracy. The beat asked for progression and got a
#: promotion. Naming the quantity is what closes that: `Windread moves here` can be satisfied
#: by exactly one thing, and a guild glass is not it.
#:
#: **The name is book data and this module invents none of it.** `extraction.counted_names`
#: reads the labels off the sheet the book declared, filtered to the fields its current
#: snapshot actually holds — so the word in the plan is the same word on the status line the
#: writer is handed, and a book that counts nothing gets `BEAT` unchanged, which is the
#: control every book written before a sheet existed sits in.
#:
#: Held to `BEAT`'s two constraints, both of which were paid for: pronoun-free (§155.3's first
#: draft would have written a male protagonist into every scheduled scene of every book), and
#: no quality word anywhere — it says a named thing moves and the person it belongs to is
#: present, which is a fact a scene either contains or does not.
NAMED_BEAT = f"{{name}} {BEAT_TAIL}"


def beat_ordinals(total: int, *, every: int = EVERY) -> frozenset[int]:
    """The 1-based scene ordinals whose plan carries a progression beat.

    **Scene 1 always**, whatever `every` is and however short the book, because the opening is
    the operator's stated complaint and the census's strongest support at once. After that,
    every `every`-th scene.

    A pure function of the count so the schedule is the same on every replay, and separate from
    the text so a book can be asked which scenes are scheduled without rendering anything.
    """
    if total <= 0:
        return frozenset()
    if every < 1:
        raise ValueError(f"every must be at least 1, not {every}")
    return frozenset({1, *range(1 + every, total + 1, every)})


def beat_text(
    ordinal: int, total: int, *, counts: Sequence[str] = (), every: int = EVERY
) -> str:
    """The beat sentence a scheduled scene carries, in this book's own vocabulary.

    `counts` is what this book's system counts, in the order its sheet prints them —
    `extraction.counted_names` is the reader, and `()` is the control that yields `BEAT`
    unchanged.

    **Which name a given beat takes is a rotation through the schedule, and it is a schedule
    rather than a choice.** The index is the beat's position in `beat_ordinals`, not its scene
    ordinal: at `EVERY = 2` the scheduled ordinals are 1, 3, 5, 7, so indexing by ordinal on a
    four-column sheet would reach columns 0 and 2 only and never name the other two. Position
    cycles all of them. That this is arithmetic and not a preference matters under §61(5) — no
    model ranks the book's quantities, and nothing here decides which of them is the important
    one, because a schedule is the only mechanism this project has that makes a rhythm regular
    (§155.1's third reading) and it is the mechanism the caller already trusts for *when*.

    Callers pass a `counts` read at the position being drafted, so a book whose sheet grows a
    column mid-manuscript starts naming it from the scene it appears in and not before.
    """
    if not counts:
        return BEAT
    position = sorted(beat_ordinals(total, every=every)).index(ordinal)
    return NAMED_BEAT.format(name=counts[position % len(counts)])


def with_beat(
    statement: str,
    ordinal: int,
    total: int,
    *,
    counts: Sequence[str] = (),
    every: int = EVERY,
) -> str:
    """One scene's plan text, with the progression beat appended where it is scheduled.

    Appended rather than prepended: the outline's own statement is what this scene is *about*,
    and the beat is one more thing that happens in it. Leading with the beat would make every
    scheduled scene read as a progression scene first and its own story second.

    **An empty statement is a contract, not an edge case.** A scheduled scene with no
    statement gets the bare beat; an unscheduled one stays empty, which renders nothing.
    That pair is what lets the drafting path pass `""` for a book that never takes an
    outline — a six-scene book has six distinct dramatic functions, so `needs_outline`
    never holds and the fold in `outline_proposal` is unreachable there (pilot 14 §3
    measured the schedule dead at exactly the standard pilot length). Both call sites
    compose the sentence through this one function, so the two paths cannot drift.

    **`counts` defaults to empty so an unwired caller is byte-identical to what it was.** That
    is not politeness: `outline_proposal` and the drafting selector are two call sites for one
    schedule, and a default that changed behaviour would let them disagree about what a
    scheduled scene says while both looking correct.
    """
    if ordinal not in beat_ordinals(total, every=every):
        return statement
    beat = beat_text(ordinal, total, counts=counts, every=every)
    stripped = statement.strip()
    if not stripped:
        return beat
    joiner = " " if stripped.endswith((".", "!", "?")) else ". "
    return f"{stripped}{joiner}{beat}"


__all__ = [
    "BEAT",
    "BEAT_TAIL",
    "EVERY",
    "HOUSE_GENRE",
    "NAMED_BEAT",
    "NO_SHEET",
    "beat_ordinals",
    "beat_text",
    "genre_block",
    "has_starting_sheet",
    "system_gap",
    "with_beat",
]
