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

from collections.abc import Sequence

import litharness_contracts as lc

from litharness.domain.extraction import STATUS_PREDICATE, speaks_system_voice

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

    A `PROPOSED` snapshot does not count, and that is `speaks_system_voice`'s rule rather than
    one added here: the outline's milestone schedule mints `PROPOSED` status records, so
    counting them would let a book satisfy the floor with its own plan for later instead of
    with a sheet that is true now.
    """
    return speaks_system_voice(records)


def genre_block(records: Sequence[lc.StateRecord]) -> str | None:
    """Why this book may not proceed to drafting, or `None` if it may.

    A reason string rather than a bool because `plan_progress` records one: *"A blocked book
    reports its reason rather than looking finished"* — the same argument the no-premise block
    is written under, one door along.
    """
    if has_starting_sheet(records):
        return None
    held = len(records)
    seeded = (
        f"{held} state record(s) on this branch, none of them a canon {STATUS_PREDICATE}"
        if held
        else "no state records on this branch at all"
    )
    return (
        f"{NO_SHEET}; {seeded}. Seed one with `new --state` or `import --state` before "
        "drafting, or this book writes no system voice and never reads any back."
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
BEAT = (
    "One of the numbers this book counts moves here, and the person it belongs to is there "
    "when it does."
)


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


def with_beat(statement: str, ordinal: int, total: int, *, every: int = EVERY) -> str:
    """One scene's plan text, with the progression beat appended where it is scheduled.

    Appended rather than prepended: the outline's own statement is what this scene is *about*,
    and the beat is one more thing that happens in it. Leading with the beat would make every
    scheduled scene read as a progression scene first and its own story second.
    """
    if ordinal not in beat_ordinals(total, every=every):
        return statement
    stripped = statement.strip()
    if not stripped:
        return BEAT
    joiner = " " if stripped.endswith((".", "!", "?")) else ". "
    return f"{stripped}{joiner}{BEAT}"


__all__ = [
    "BEAT",
    "EVERY",
    "HOUSE_GENRE",
    "NO_SHEET",
    "beat_ordinals",
    "genre_block",
    "has_starting_sheet",
    "with_beat",
]
