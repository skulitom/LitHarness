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
    MAX_SUFFIX,
    SHEET_PREDICATE,
    STATUS_PREDICATE,
    speaks_system_voice,
    standing_example,
)

#: The genre every book this house publishes is in. A constant rather than a per-book setting,
#: because the operator's constraint is about the house and not about a shelf: a book's shelf
#: may be cozy, mystery or historical, and it carries the system furniture anyway.
HOUSE_GENRE = "LitRPG"

#: What `cmd_new` prints at creation, and what the floor refuses with, share this sentence so
#: an operator who ignored the first sees the same words in the second. One string, two
#: surfaces, no drift — `tests/test_genre_floor.py` pins that they are the same string.
NO_SHEET = (
    f"no display seeded — a {HOUSE_GENRE} book needs something it can print: a starting "
    "sheet to speak system voice, or a standing on a declared ladder with the line that "
    "prints it"
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
    # **A display, not a numeric sheet** (§209). A book whose progression has no numbers,
    # a named ladder and the line the book prints when a standing changes, is a book
    # this house can ask for its furniture; the sheet was the only display the floor
    # knew. `extraction.standing_example` is the same question the writer's prompt asks,
    # so the floor and the ask cannot disagree.
    if standing_example(records) is not None:
        return True
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
    return gamesystem_mod.systems_of([record for record in records if state_mod.is_canon(record)])


def _canon_snapshots(records: Sequence[lc.StateRecord]) -> tuple[Mapping[str, object], ...]:
    return tuple(
        record.value
        for record in records
        if record.predicate == STATUS_PREDICATE
        and state_mod.is_canon(record)
        and isinstance(record.value, Mapping)
    )


def _is_position_in(records: Sequence[lc.StateRecord], system: gamesystem_mod.SystemDef) -> bool:
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
    # **A ceiling is a column's ceiling and not a column** (§197.2). Pilot 22's seed put
    # a bearing_max key beside bearing — the printed form of *Bearing 0/1*, which the declared
    # sheet's own `paired` flag renders — and an exact key comparison read that sheet as a
    # different book's, so `world accept` refused to finish both drawn systems and the
    # chapter drafted with no system read back. A ceiling for a column the system does not
    # have is still a different sheet.
    for snapshot in _canon_snapshots(records):
        keys = {
            key
            for key in snapshot
            if not (key.endswith(MAX_SUFFIX) and key[: -len(MAX_SUFFIX)] in wanted)
        }
        if keys == wanted:
            return True
    return False


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
        canon = [record for record in records if state_mod.is_canon(record)]
        unfinished = gamesystem_mod.unfinished_systems(canon)
        if unfinished:
            # **The symptom and the reason, both** (Serial Pilot 19 §4). `unfinished_systems`
            # says what the system lacks — a scale, most often — and the scale is minted at
            # acceptance by `completion_records`, which can refuse: eleven abilities against a
            # bound of eight, a ladder it cannot read. The refusal's own sentence was printed
            # once, at `world accept`, on a channel nobody re-reads; a check that names only
            # the missing scale sends the operator to declare a thing that cannot be declared
            # (§163.2). So the completion is asked again here, purely, and its reasons ride
            # beside the symptom.
            _minted, reasons = gamesystem_mod.completion_records(canon)
            because = (
                " Acceptance would not finish it either, and says why: " + "; ".join(reasons)
                if reasons
                else ""
            )
            return (
                "this book began a game system and did not finish it: "
                + "; ".join(unfinished)
                + ". An unfinished system reads back as no system at all, so the sheet is "
                "never checked as a position in it and no beat speaks its ranks or "
                "abilities." + because
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


def beat_text(ordinal: int, total: int, *, counts: Sequence[str] = (), every: int = EVERY) -> str:
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


#: `BEAT` with its tail taken off: what the categorical form puts where a name would go.
_BEAT_HEAD = BEAT[: -len(BEAT_TAIL)].strip()


def beat_name_in(statement: str) -> str | None:
    """The quantity a composed scene plan names as moving, or `None` where it names none.

    **The inverse of `beat_text`'s naming half, and it reads the composed plan rather than
    recomputing one.** Two paths fold a beat into a plan — `outline_proposal` writes it into a
    stored statement, and the drafting selector derives one for a scene that has no statement —
    and the two use different records at different times. Asking either what it *would* name
    now is a re-derivation; asking the text what it *did* name is a reading. §170's rule that
    two readers of one sheet must not pick different ones applies here through the other door:
    this is the only reader, and its subject is the string that went to the writer.

    `None` covers three cases with one right answer — nothing to verify:

    - no beat fired here (an unscheduled scene, whose plan is untouched by this schedule);
    - the categorical `BEAT` fired, which names a category and not a quantity, and is what
      every book with no sheet gets (§161.4's control);
    - the interaction and offer beats, which end in their own words rather than in `BEAT_TAIL`
      — an offer says a fork *stands open* and a `CHOOSE` moves no number at all, which is why
      `extraction._named_moves` drops it. A beat that asked for no move cannot be read as
      having asked for one.

    Both fold sites append after the beat (`with_bound`, `with_interaction`), so what precedes
    `BEAT_TAIL` is the name whatever else the plan went on to say.
    """
    at = statement.find(BEAT_TAIL)
    if at < 0:
        return None
    head = statement[:at].rstrip()
    start = 0
    for terminator in (". ", "! ", "? ", "\n"):
        found = head.rfind(terminator)
        if found >= 0:
            start = max(start, found + len(terminator))
    name = head[start:].strip()
    if not name or name == _BEAT_HEAD:
        return None
    return name


# --------------------------------------------------------------------------- the reading half

#: **The operator, read 10 on serial pilot 15b draw 4, 2026-08-30** — recorded in
#: `plan/serial-pilot-15b.md`, which owns the quote, and never rendered into any call (§97.1):
#: a status line arriving at a number-move reads as *noise*, because the system is not a thing
#: anybody in the book opens, reads or deals with. Their direction is that it has to be part of
#: the world the characters are interacting with, and that weighing what to take next is a large
#: part of the story.
#:
#: **Why this is a scheduled beat and not a clause.** `plan/house-genre-constraint.md` named the
#: hazard before anybody drafted one: an instruction to make the system feel present is a §138
#: formula waiting to happen, and the altitude that avoids it is the plan. §157 proved that a
#: schedule moves behaviour with no adjective in it, and §161.4 sharpened it from a category to a
#: named quantity. There is a second reason and it is arithmetic: a scene plan rides in the user
#: prompt as book material, so it costs no demand in any row of `tests/test_prompt_budget.py`,
#: while the house floor and three of the roles standing on it sit exactly at their ceilings
#: (§171.4). The beat is free where a clause is not.
#:
#: Held to `BEAT`'s two constraints, both already paid for: **pronoun-free** (§155.3's first draft
#: would have written a male protagonist into every scheduled scene of every book) and **no
#: quality word anywhere** — it says a thing is opened and read and that what it says is dealt
#: with in the scene, which is a fact a scene either contains or does not.
INTERACTION_BEAT = (
    "The state this book prints is opened and read here by the person it belongs to, and what "
    "it says is business in the scene."
)

#: The same beat where a fork stands open, naming it and the ways on offer in the book's own
#: words. **`{options}` is book data and this module invents none of it**:
#: `extraction.offered_choice` reads the names off the system the world declared and drops any
#: colliding with `house.MACHINERY_WORDS`, which is `counted_names`' rule for `counted_names`'
#: reason — a declared name is book data that no ceiling test can reach, so the filter is where
#: the guarantee has to live.
#:
#: **It says weighs and not picks, and the difference is the operator's direction.** What they
#: asked to read is the deliberation — *"as a reader i want to deliberate class options and what i
#: would have chosen"* — and the pick is a separate act with its own record
#: (`gamesystem.choose`). A beat that told the scene to settle the fork would spend the fork on
#: the scene that introduces it.
OFFER_BEAT = (
    "{name} stands open here, and the person it belongs to weighs {options} against each other "
    "on the page."
)


def interaction_ordinals(total: int, *, every: int = EVERY) -> frozenset[int]:
    """The scene ordinals whose plan may carry an interaction beat.

    **The progression schedule, deliberately, rather than a second cadence of its own.** Two
    schedules over one book would be two rhythms nobody had measured against each other, and
    §155.1's census supports one placement claim only — that the opening is where the market
    fails. Sharing `beat_ordinals` also means a book that changes `every` changes both together.
    """
    return beat_ordinals(total, every=every)


def interaction_text(
    ordinal: int,
    total: int,
    *,
    reads: bool = False,
    offer: tuple[str, Sequence[str]] | None = None,
    every: int = EVERY,
) -> str | None:
    """The interaction beat this scene carries, or `None` for a scene that carries none.

    `reads` is whether this book prints a line the character could open at this position — the
    caller passes the same value it computes for the furniture ask, so the beat cannot ask
    somebody to read an interface the writer was never handed. `offer` is `(fork name, way
    names)` where one stands open, from `extraction.offered_choice`.

    **The rule, and the small book is the point.** A book with no fork gains exactly one
    interaction beat, in its opening, which is the smallest thing that answers read 10's
    standalone-comprehension item: a character who opens their own state teaches its labels and
    its numbers by using them. A book with forks deliberates for as long as a fork stands open,
    on the cadence the progression beat already runs at — so *how much* deliberation a book
    carries is a fact its own world declares, and not a number this module picked.

    The offer form wins at the opening where both could fire: it names the fork and its ways,
    which teaches the interface by using more of it.
    """
    if not reads:
        return None
    if ordinal not in interaction_ordinals(total, every=every):
        return None
    if offer is not None:
        name, options = offer
        return OFFER_BEAT.format(name=name, options=_and_list(options))
    return INTERACTION_BEAT if ordinal == 1 else None


def _and_list(names: Sequence[str]) -> str:
    """`a`, `a and b`, `a, b and c`. Book data joined by grammar and nothing else."""
    items = [name for name in names if name]
    if len(items) <= 1:
        return items[0] if items else ""
    return f"{', '.join(items[:-1])} and {items[-1]}"


def with_interaction(
    statement: str,
    ordinal: int,
    total: int,
    *,
    reads: bool = False,
    offer: tuple[str, Sequence[str]] | None = None,
    every: int = EVERY,
) -> str:
    """One scene's plan text, with the interaction beat appended where it is scheduled.

    Appended for `with_beat`'s reason and after it, so a scheduled scene reads: what this scene
    is about, what moves in it, and that the interface is opened in it. **`reads=False` and
    `offer=None` render nothing at all**, which is every book that speaks no system voice and
    every scene of every book written before this existed — the control this whole slice is
    measured against, byte-identical.
    """
    beat = interaction_text(ordinal, total, reads=reads, offer=offer, every=every)
    if beat is None:
        return statement
    stripped = statement.strip()
    if not stripped:
        return beat
    joiner = " " if stripped.endswith((".", "!", "?")) else ". "
    return f"{stripped}{joiner}{beat}"


#: The opening's two beats, and where they come from is a measurement rather than a taste.
#: The market's summits open the same way: who this person is and what their days were is on
#: the page before the system is, the system arrives inside that, and the chapter ends on a
#: thing the person has read or been offered and has not answered. Measured 2026-09-01 on the
#: two anchors the operator placed on the shelf and the four highest-follower local LitRPG
#: openings (`research/opening-parity/PREREG.md` §2); our four newest openings did none of
#: it. Written as material, like every beat above: a thing that happens in the scene, never an
#: adjective about it, and each names a token the writer can put on the page (§154) — the
#: person's days before, the first printed line, the unanswered thing at the end.
OPENING_FIRST = (
    "Who this person is and what their days were before any of this is on the page before the "
    "first line the book prints, and the first line the book prints lands inside that."
)

OPENING_HOOK = (
    "The scene ends on something the person has just read or been offered and has not yet answered."
)


def opening_text(
    ordinal: int,
    *,
    reads: bool = False,
    arc_index: int | None = None,
    chapter_scene: int | None = None,
    scenes_in_chapter: int | None = None,
    opening: int = 2,
) -> str | None:
    """The opening beat this scene carries, or `None` for a scene that carries none.

    `reads` is the same gate `interaction_text` takes: a book that prints no line has no
    first printed line for the first beat to land inside, so neither beat fires and every
    book that speaks no system voice renders byte-identically to what it did before this
    existed. `arc_index` keeps a serial's later arcs from opening the book again, exactly as
    `staging.bounds_opening` does.

    **Which scene is the chapter's last is the chapter's to say.** Where the caller knows the
    chapter shape it passes `chapter_scene` and `scenes_in_chapter`, and the hook lands on the
    last scene of the first chapter whatever its length; a caller without a shape falls back
    to `opening`, the same placed number `staging.OPENING` carries, so the two modules agree
    about which span is the opening on the shape the house actually runs.
    """
    if not reads:
        return None
    if arc_index is not None and arc_index > 1:
        return None
    if ordinal == 1:
        return OPENING_FIRST
    if chapter_scene is not None and scenes_in_chapter is not None:
        last_of_first_chapter = ordinal == scenes_in_chapter and chapter_scene == scenes_in_chapter
        return OPENING_HOOK if last_of_first_chapter and ordinal > 1 else None
    return OPENING_HOOK if ordinal == opening else None


def with_opening(
    statement: str,
    ordinal: int,
    *,
    reads: bool = False,
    arc_index: int | None = None,
    chapter_scene: int | None = None,
    scenes_in_chapter: int | None = None,
    opening: int = 2,
) -> str:
    """One scene's plan text, with the opening beat appended where it is scheduled.

    Appended after the statement and after the progression and interaction beats, so an
    opening scene reads: what it is about, what moves in it, that the interface is opened in
    it, and then what the opening asks of it. `reads=False` renders nothing at all, which is
    the control.
    """
    beat = opening_text(
        ordinal,
        reads=reads,
        arc_index=arc_index,
        chapter_scene=chapter_scene,
        scenes_in_chapter=scenes_in_chapter,
        opening=opening,
    )
    if beat is None:
        return statement
    stripped = statement.strip()
    if not stripped:
        return beat
    joiner = " " if stripped.endswith((".", "!", "?")) else ". "
    return f"{stripped}{joiner}{beat}"


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
    "INTERACTION_BEAT",
    "NAMED_BEAT",
    "NO_SHEET",
    "OFFER_BEAT",
    "OPENING_FIRST",
    "OPENING_HOOK",
    "beat_name_in",
    "beat_ordinals",
    "beat_text",
    "genre_block",
    "has_starting_sheet",
    "interaction_ordinals",
    "interaction_text",
    "opening_text",
    "system_gap",
    "with_beat",
    "with_interaction",
    "with_opening",
]
