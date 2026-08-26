"""Narrative Planning v0: one statement per scene, so twenty-five beats stop being one beat.

**The measured defect this exists for.** `arc_template(30)` yields **25 `rising` beats out of
30**, and `render_prompt` puts the beat's title and its function word into the prompt and
nothing else from the plan — so twenty-five of the thirty (ordinals 3-17 and 19-28; the turn
sits at 18) are asked, from the planning side, *"Scene N — dramatic function: rising"* and
differ only in the integer. Book Zero's answer was five near-copies of an earlier scene and a ledger
that moved once in thirty, and §52 records both as the same root cause seen in two layers:
the book re-issues its own errand because nothing told it not to.

**A statement of what happens, not a richer function word.** Giving the rising span a longer
vocabulary — "complication", "setback", "reversal" — would differentiate the *label* and leave
the content mandate exactly as empty as before; two scenes labelled "complication" still have
no reason to differ. What stops scene 11 re-running scene 10's errand is scene 11 having its
own errand.

**One call for the whole book, and that is the design rather than a saving.** A per-scene call
would ask a model to invent scene 11 without having seen what scene 10 is for, which is the
condition that produces the duplication in the first place. Asked once, with the premise and
every beat's function in view, the model has to make the scenes differ from *each other* —
and `_statements` refuses the proposal if it did not, so the defect arrives as a
refused plan rather than as thirty scenes of prose nobody reads until later.

**It writes plan items and therefore inherits every property of the plan.** `PlanKind.SCENE_PLAN`
and `PlanItem.scope` have been in the contract with no producer since 1.0 — `domain/plans.py`
says so in its own docstring, "not one is a `scene_plan`; not one carries a `scope`". Going
through `PlanProposal` means the outline is versioned, attributable to a recorded decision,
rolled back by `revert-plan` like any other plan movement, and refused if the base moved under
it. None of that had to be built here.

What this is **not**, so the gap stays visible: it is not a foreshadow-payoff ledger and not a
progression schedule. §20.6's ordering trap still holds for the second — the schedule needs a
level curve the game-mechanics pack owns, and the litrpg fixture has no XP figure to build one
from. ~~`open_threads` already carries promises; nothing here schedules their payoff.~~

**W2 (§94) closes exactly the last sentence and nothing else.** The promise ledger (migration
023) now feeds this call and comes back with **payoff windows** — the scene range each open
debt should be paid inside — validated by `_payoff_windows` the way milestones are and stored
as PROPOSED-grade columns on the promise row. What is still not here: no progression schedule
against a game-system simulator, because there is none in this repository to schedule against
(§8.4 put that vocabulary in the game-mechanics pack), and no "missed its window" finding,
because a model-scheduled window missed by a model-reported payoff is two model claims
disagreeing and neither may raise a finding about the other. `promise.overdue.v0` remains the
whole evaluator side.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from itertools import pairwise
from typing import Any

import litharness_contracts as lc

from litharness.application.conductor import JobHandler
from litharness.application.plan_refinement import accept_plan_proposal
from litharness.application.policy_events import policy_decision_event
from litharness.application.ports import OutlineStore, TextGenerator
from litharness.domain import house, world_brief
from litharness.domain import state as state_mod
from litharness.domain import worlds as worlds_mod
from litharness.domain.beats import Beat, beats_for, template_for
from litharness.domain.budget import BudgetPolicy
from litharness.domain.budget import check as budget_check
from litharness.domain.events import Event, EventType, payload_digest
from litharness.domain.extraction import MAX_SUFFIX, impossible_fields
from litharness.domain.generation import CompletionRequest, CompletionResult, Resolution
from litharness.domain.jobs import Job
from litharness.domain.patch import Veto
from litharness.domain.plan_refinement import (
    PlanConflict,
    PlanEdit,
    PlanEditAction,
    PlanProposal,
    PlanProposalError,
    PlanRevision,
    apply_plan_proposal,
)
from litharness.domain.plans import premise_of, scene_plan_for, scene_plan_id_for
from litharness.domain.policy import (
    GateKind,
    GateOutcome,
    Outcome,
    PolicyDecision,
    VerdictSource,
    decide,
    decision_id_for,
)
from litharness.domain.promises import Promise, schedule_fault, window_fault
from litharness.domain.world_brief import WorldBrief

#: Job kind this handler answers to.
BOOK_OUTLINE = "book_outline"

#: Frozen generation profile, recorded in provenance like every other model call here.
PROFILE = "planner.outline.v0"

#: Ranks above scene drafting (0) and below director direction (500+). A scene drafted before
#: its statement exists would be drafted against the empty plan this module exists to fill, so
#: the outline has to be claimed first — and it is one call for the whole book, so it delays
#: the first scene by one tick and no more.
OUTLINE_PRIORITY = 300

#: Words per statement, asked for rather than enforced. A statement is an instruction to the
#: generator, not prose, and one that runs long starts writing the scene instead of placing it.
TARGET_WORDS = 25

#: Added to the request only when canon declares a protagonist. **Position and fact, and the
#: boundary is asserted rather than trusted**: whether the reader should like them, whether they
#: win, and whether they progress faster than anyone are the operator's to say and are said
#: through a directive, never from here (stage-0 §95, §97.1). The strings below are checked for
#: the vocabulary such an instruction would have to use by
#: `test_the_protagonist_rules_name_a_person_and_never_an_outcome`.
PROTAGONIST_RULES: tuple[str, ...] = (
    "The protagonist is {subject}. This is {subject}'s book, so each statement says what "
    "{subject} does in that scene, or what is done to {subject}.",
)


class OutlineOutputError(Exception):
    """The model's outline is not one this handler can turn into a plan."""


OUTLINE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "summary",
        "rationale",
        "expected_outcome",
        "scenes",
        "milestones",
        "payoff_windows",
    ],
    "properties": {
        "summary": {"type": "string"},
        "rationale": {"type": "string"},
        "expected_outcome": {"type": "string"},
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["ordinal", "statement"],
                "properties": {
                    "ordinal": {"type": "integer"},
                    "statement": {"type": "string"},
                },
            },
        },
        # The progression schedule, asked for in the same call. §15: the per-invocation
        # harness tax is larger than the payload, so multiple asks fold into one invocation
        # rather than chaining calls that each re-pay it — and the model is already holding
        # the premise and the whole beat sheet, which is what a schedule must be consistent
        # with.
        "milestones": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["ordinal", "state"],
                "properties": {
                    "ordinal": {"type": "integer"},
                    "state": {"type": "object"},
                },
            },
        },
        # W2 (§94): milestones schedule *state*; nothing scheduled *payment*. Same call, for
        # the same §15 reason, and the same reason the milestone ask lives here rather than in
        # a call of its own — the model is already holding the premise and the whole beat
        # sheet, which is exactly what a payoff schedule has to be consistent with.
        #
        # Required by the schema and legitimately empty: a book with no open promises has
        # nothing to schedule, and `[]` says that where an absent key would be
        # indistinguishable from a model that ignored the question.
        "payoff_windows": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["subject", "first_scene", "last_scene"],
                "properties": {
                    "subject": {"type": "string"},
                    "first_scene": {"type": "integer"},
                    "last_scene": {"type": "integer"},
                },
            },
        },
        # The rung schedule (`plan/handoff-numbers-go-up.md` Task 2), asked for in the same call
        # for the same §15 reason the other two are: the model is already holding the premise
        # and the whole beat sheet, and a schedule of standings has to be consistent with both.
        #
        # **Optional rather than required, unlike `milestones` and `payoff_windows`.** Those two
        # arrived when every book in the store was a book the schema could describe; this one
        # arrives against `plan/serial-pilot-2-world.json` and `serial3.db`, which declare no
        # ladder and would have to answer `[]` to a question nobody put to them. Required here
        # would make the answer to "does this book have a ladder" a thing the *model* says, and
        # it is a thing canon says.
        "standing_milestones": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["ordinal", "rung"],
                "properties": {
                    "ordinal": {"type": "integer"},
                    "rung": {"type": "string"},
                },
            },
        },
    },
}


def outline_job_id(book_id: str, branch_id: str, epoch: int) -> str:
    """Derived, and epoch-versioned for `beat_job_id`'s reason.

    `idempotency_key` is UNIQUE, so a poisoned outline would burn its id forever and "plan
    this book again" would be inexpressible. `replan` bumps the epoch and this follows it.
    """
    material = payload_digest(
        {"book_id": book_id, "branch_id": branch_id, "plan_epoch": epoch}
    )
    return f"outline-{material[:24]}"


def _ordinal_of(beats: Sequence[Beat]) -> dict[str, int]:
    """`{story_order_key: ordinal}` for the beats that have a position.

    The ledger speaks in `beats_for`'s zero-padded keys and a model speaks in scene numbers,
    so exactly one translation exists and it is this one — built from the sheet rather than by
    parsing a key, because parsing the padding back out would be a second implementation of
    the thing the padding exists to make unnecessary.
    """
    return {
        beat.story_order_key: beat.ordinal
        for beat in beats
        if beat.story_order_key is not None
    }


def render_outline_request(
    premise: str,
    beats: Sequence[Beat],
    *,
    base: PlanRevision,
    seed: Mapping[str, Any] | None = None,
    promises: Sequence[Promise] = (),
    world: WorldBrief | None = None,
    protagonist: worlds_mod.Protagonist | None = None,
) -> CompletionRequest:
    """Freeze the premise and the whole beat sheet into one structured-output request.

    The *entire* sheet goes in, not a window: the model is being asked to make thirty scenes
    differ from one another, and it cannot do that against a sheet it can only see part of.

    **The world goes in when the book has one, and the field is absent when it does not.**
    Absent rather than null: `json.dumps` writes `null` for a value that is not there, so a
    key that is always present is a payload that always changed. `test_world_brief.py` asserts
    the no-world payload byte-for-byte against what it was before this parameter existed.
    `domain/world_brief.py` owns what a planner may be told and what it may not — the answers
    reach a statement only where the world scheduled them.

    **`protagonist` says whose book it is, which is the one thing the world brief cannot say**
    (`plan/reader-read-3.md` notes 1 and 3). The brief carries every declared person under
    `cast`, in the packet's own phrasing; what a flat list of people cannot carry is *which of
    them this book is about*. Until 2026-08-22 nothing did, and on Serial Pilot 3 this call
    invented a protagonist who occurs nowhere in the forged world — while four of that world's
    five declared cast members never reached either chapter. The writer had them all along:
    328 established facts, `context_omitted = 0`.

    **Two branches met here and one input was collapsed rather than kept.** This call briefly
    took a `cast` argument of its own beside `world`; the world brief already renders every
    declared person from the same projection, and a request carrying the same people twice is a
    request spending its budget saying one thing. Stage-0 §112.7 named that debt at the merge
    and this is it being paid. `protagonist` survives because the brief has no way to express
    it: it groups facts by kind, and "which of these people is the one the book is about" is
    not a fact about a kind.

    **Open promises go in as debts, and the register is `describe_owed`'s** (W2). They are
    shown so the schedule can be about the book's actual debts rather than about debts the
    model invents while answering, and they are shown as *owed* rather than as established
    fact for the same reason the packet shows them that way — a model-reported promise
    rendered in the indicative would be laundered into premise by register alone. A book with
    no open promises is asked for no windows at all, exactly as a book with no starting sheet
    is asked for no milestones: an empty ask produces an empty answer to validate, which is
    worse than not asking.
    """
    ordinals = _ordinal_of(beats)
    owed = [
        {
            "subject": promise.subject,
            "owed": promise.description,
            "opened_at_scene": ordinals.get(promise.opened_at_key),
            "due_by_scene": ordinals.get(promise.due_key or ""),
        }
        for promise in promises
        if promise.opened_at_key in ordinals
    ]
    prompt = json.dumps(
        {
            "premise": premise,
            "base_plan_revision_id": base.plan_revision_id,
            # The world this book runs on, and the one member of its cast this book is
            # about, when it has them. Spread rather than assigned so that a book without one
            # has no key at all — see the docstring.
            **({"world": world.to_jsonable()} if world is not None else {}),
            **(
                {"protagonist": protagonist.to_jsonable()}
                if protagonist is not None
                else {}
            ),
            # The debts this book has already opened, for the payoff schedule. Absent for a
            # book that owes nothing — which is every book at its first outline, since
            # promises are written by the summary handler after a scene is accepted.
            "open_promises": owed or None,
            # The book's own starting numbers, so the schedule is expressed in the game
            # system this book actually has rather than one the model invents. Absent for a
            # book that does not speak system voice, and then no schedule is asked for — a
            # stat block in a locked-room mystery is not a smaller error than a missing one.
            "starting_state": dict(seed) if seed else None,
            "scenes": [
                {
                    "ordinal": beat.ordinal,
                    "of_total": beat.of_total,
                    "dramatic_function": beat.function,
                }
                for beat in beats
            ],
            "rules": [
                f"Return exactly {len(beats)} scenes, ordinals 1 to {len(beats)}, each once.",
                f"Each statement is about {TARGET_WORDS} words.",
                "State what happens in that scene: who acts, what they do, what changes.",
                "Every statement must be different from every other. Two scenes that could "
                "be swapped without the book noticing are one scene written twice.",
                "Do not write prose, dialogue, or description; this is an instruction to a "
                "writer, not the scene itself.",
                "Respect the dramatic function given for each scene.",
                "Later scenes must build on earlier ones rather than repeat them: nothing may "
                "be obtained, revealed, or resolved twice.",
            ]
            + (
                [
                    "Also return milestones: what starting_state should have become by the "
                    "end of certain scenes.",
                    "Use only the keys starting_state already has. Do not invent statistics.",
                    "The numbers must actually move. A schedule where every milestone "
                    "repeats the starting values plans a book in which nothing changes.",
                    "Place four to eight milestones, spread across the book, at scenes where "
                    "the statement you wrote would plausibly change them.",
                    "Costs as well as gains: spending and losing are progression "
                    "too.",
                ]
                if seed
                else []
            )
            + (
                [
                    "Also return payoff_windows: for each open promise, the scene range in "
                    "which the book should pay it off.",
                    "Use the subject names given in open_promises. Do not invent promises.",
                    "A window may not open before the scene that opened the promise, and may "
                    "not close after the scene it is due by.",
                    "Spread the payments out. A schedule that pays every debt in the last "
                    "third of the book, or every debt in one place, is the thing a reader "
                    "feels as nothing happening and then everything happening.",
                ]
                if owed
                else []
            )
            + (list(world_brief.WORLD_RULES) if world is not None else [])
            # The rung schedule, asked for only where canon declares a chain to schedule on —
            # the same guard the milestone ask runs under, and for the same reason: an empty ask
            # produces an empty answer to validate, which is worse than not asking.
            + (
                [
                    rule.format(protagonist=world.ladder.protagonist)
                    for rule in world_brief.LADDER_RULES
                ]
                if world is not None and world.ladder is not None
                else []
            )
            + (
                [rule.format(subject=protagonist.subject) for rule in PROTAGONIST_RULES]
                if protagonist is not None
                else []
            ),
        },
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )
    return CompletionRequest(
        prompt=prompt,
        # The scene statements are what the writer is told a scene is *for*, so a statement
        # that spends a scene on procedure buys the whole scene before a word is drafted.
        system=house.with_house_rules(
            "You are the Narrative Planner for a novel. Given a premise and a beat sheet, "
            "say in one sentence what happens in each scene, so that a writer drafting any "
            "one scene knows what that scene is for and what the others are for. Return "
            "only the requested JSON."
        ),
        schema=OUTLINE_SCHEMA,
        max_output_tokens=8192,
        profile=PROFILE,
        call_class="generation",
    )


def _statements(payload: Mapping[str, Any], expected: int) -> list[str]:
    """The model's scenes as an ordinal-ordered list, or a refusal naming what was wrong.

    **Distinctness is checked here rather than hoped for**, and it is the one validation that
    is about the defect instead of about the schema. An outline whose statements repeat is the
    same failure this module exists to end, arriving one layer earlier — and one layer earlier
    is where it is cheap, because a refused proposal costs one call and a repeated scene costs
    a generation plus everything downstream of accepting it.
    """
    raw = payload.get("scenes")
    if not isinstance(raw, list):
        raise OutlineOutputError("outline must carry a list of scenes")
    if len(raw) != expected:
        raise OutlineOutputError(
            f"outline covers {len(raw)} scene(s); the book has {expected}"
        )

    by_ordinal: dict[int, str] = {}
    for entry in raw:
        if not isinstance(entry, Mapping):
            raise OutlineOutputError("each scene must be an object")
        ordinal = entry.get("ordinal")
        statement = entry.get("statement")
        if not isinstance(ordinal, int) or isinstance(ordinal, bool):
            raise OutlineOutputError(f"scene ordinal {ordinal!r} is not an integer")
        if not 1 <= ordinal <= expected:
            raise OutlineOutputError(
                f"scene ordinal {ordinal} is outside 1..{expected}"
            )
        if ordinal in by_ordinal:
            raise OutlineOutputError(f"scene {ordinal} is described more than once")
        if not isinstance(statement, str) or not statement.strip():
            raise OutlineOutputError(f"scene {ordinal} has no statement")
        by_ordinal[ordinal] = statement.strip()

    missing = sorted(set(range(1, expected + 1)) - set(by_ordinal))
    if missing:
        raise OutlineOutputError(f"outline says nothing about scene(s) {missing}")

    ordered = [by_ordinal[ordinal] for ordinal in range(1, expected + 1)]
    folded = [" ".join(statement.lower().split()) for statement in ordered]
    duplicates = sorted({value for value in folded if folded.count(value) > 1})
    if duplicates:
        raise OutlineOutputError(
            f"{len(duplicates)} statement(s) appear on more than one scene; an outline that "
            "repeats itself plans the duplication it exists to prevent"
        )
    return ordered


def _milestones(
    payload: Mapping[str, Any], beats: Sequence[Beat], seed: Mapping[str, Any]
) -> list[tuple[Beat, dict[str, float]]]:
    """The schedule as (beat, state) pairs, or a refusal naming what was wrong.

    **The check that is about the defect: a schedule may not schedule stasis.** §52 measured
    31 extracted status records across thirty scenes holding **two** distinct ledger states —
    gold moved once in scene 1 and nothing moved again. A schedule whose milestones all equal
    the seed would reproduce that exactly while looking like a fix, so at least one milestone
    has to differ from the starting sheet and consecutive milestones may not be identical.
    This is `_statements`' distinctness rule applied to the numbers.

    **The keys are the seed's and no others.** A model free to invent stats would add an `xp`
    or a `stamina` the book's canon has never held, and `render_status_line` would then ask
    every scene for a field the extractor cannot read back — inventing a game system rather
    than scheduling the one the book has. `progression_target` refuses to interpolate a curve
    for the same reason: its shape is the author's choice, not this module's.

    Milestones are placed at beats, so a template that cannot say where its scenes sit in
    story time gets no schedule rather than an invented one — `story_order_key` is `None`
    exactly when the sheet is not entitled to answer.
    """
    raw = payload.get("milestones")
    if not isinstance(raw, list) or not raw:
        raise OutlineOutputError("outline carries no progression schedule")
    by_ordinal = {beat.ordinal: beat for beat in beats}
    numeric_seed = {
        key: value for key, value in seed.items() if isinstance(value, int | float)
    }
    if not numeric_seed:
        raise OutlineOutputError(
            "the starting sheet holds no numeric state to schedule"
        )

    out: list[tuple[Beat, dict[str, float]]] = []
    seen: set[int] = set()
    for entry in raw:
        if not isinstance(entry, Mapping):
            raise OutlineOutputError("each milestone must be an object")
        ordinal = entry.get("ordinal")
        state = entry.get("state")
        if not isinstance(ordinal, int) or isinstance(ordinal, bool):
            raise OutlineOutputError(f"milestone ordinal {ordinal!r} is not an integer")
        if ordinal not in by_ordinal:
            raise OutlineOutputError(
                f"milestone names scene {ordinal}, which does not exist"
            )
        if ordinal in seen:
            raise OutlineOutputError(f"scene {ordinal} carries more than one milestone")
        if not isinstance(state, Mapping) or not state:
            raise OutlineOutputError(f"milestone at scene {ordinal} carries no state")
        unknown = sorted(set(state) - set(numeric_seed))
        if unknown:
            raise OutlineOutputError(
                f"milestone at scene {ordinal} invents {unknown}; the sheet holds "
                f"{sorted(numeric_seed)} and a schedule may not add to it"
            )
        values: dict[str, float] = {}
        for key, value in state.items():
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise OutlineOutputError(
                    f"milestone at scene {ordinal} sets {key} to {value!r}, "
                    "which is not a number"
                )
            # **The number's own type is kept.** Coercing to float put `Gold 4.0` into the
            # rendered status line, and the line is what the generator is asked to write and
            # the extractor reads back — so a float here would have every scene writing a
            # decimal into a ledger whose canon holds integers.
            values[str(key)] = value
        beat = by_ordinal[ordinal]
        if beat.story_order_key is None:
            raise OutlineOutputError(
                f"scene {ordinal} has no story position, so a milestone cannot be placed "
                "there; the beat sheet does not claim to run forwards"
            )
        seen.add(ordinal)
        out.append((beat, values))

    out.sort(key=lambda pair: pair[0].ordinal)
    merged = [{**numeric_seed, **values} for _, values in out]
    if all(state == dict(numeric_seed) for state in merged):
        raise OutlineOutputError(
            "every milestone restates the starting sheet; a schedule that schedules stasis "
            "is the frozen ledger it exists to end"
        )
    for earlier, later in pairwise(merged):
        if earlier == later:
            raise OutlineOutputError(
                "two consecutive milestones are identical; a schedule with a flat stretch "
                "tells those scenes to change nothing"
            )
    # **A schedule may not schedule an impossible state**, and this is the check the other
    # three did not make. §56.5 measured it: an outline placed `mp 6` against the seed's
    # `mp_max 4`, `milestone_records` wrote it as `PROPOSED`, and from then on every scene at
    # or before that position was handed it by `progression_target` as the state to move
    # toward. The merge above is what makes the check meaningful — a milestone that sets only
    # `mp` inherits `mp_max` from the seed, which is exactly the state it is proposing.
    #
    # Refused with the whole outline rather than dropped, for the reason §55 gives for asking
    # in one call: a schedule that fails validation refuses the outline too, rather than
    # landing beside a good one.
    for (beat, _), state in zip(out, merged, strict=True):
        impossible = impossible_fields(state)
        if impossible:
            offending = ", ".join(
                f"{field} {state[field]} against {field}{MAX_SUFFIX} "
                f"{state[f'{field}{MAX_SUFFIX}']}"
                for field in impossible
            )
            raise OutlineOutputError(
                f"milestone at scene {beat.ordinal} schedules a state the sheet forbids "
                f"({offending}); a ceiling is not a target"
            )
    return out


def _standing_milestones(
    payload: Mapping[str, Any], beats: Sequence[Beat], ladder: world_brief.Ladder
) -> list[tuple[Beat, str]]:
    """The rung schedule as (beat, rung) pairs, or a refusal naming what was wrong.

    **`_milestones` for the ladder, with one check `_milestones` does not make: direction.**
    A numeric schedule may legitimately go down — spending is progression in a debt story, and
    that rule is written into the milestone ask beside it. A standing on this brief may not,
    and the reason is a genre contract the *directed brief* declares rather than a property of
    the ontology: `research/progression-generalization.md`'s closing list refuses "monotone
    power as the definition of progression", and nothing here adopts it — comparators, partial
    orders and revocable rank all stay exactly as they were. What is checked is the narrower
    thing `plan/state-model-abilities.md` §4 says an *ordinal* comparator is checked for:
    "the result moved up the order", over the arc being written now. A world that wants a fall
    writes it in later by directive, and a directive is the operator's.

    The four refusals are `_milestones`' own, transposed:

    1. an ordinal that does not exist, or two milestones at one scene;
    2. a rung the world never declared — the ladder's ids and no others, exactly as the
       numeric schedule may use only the seed's keys;
    3. **stasis**: every milestone repeating the opening rung plans a book in which nothing
       rises, which is the defect this whole slice exists for, arriving as a schedule;
    4. **a flat stretch**: two consecutive milestones on the same rung tell those scenes to
       change nothing.

    And then direction, which is two statements over the positions: the sequence never
    decreases and never opens below the opening rung, and at least one milestone is strictly
    above it.

    Refused with the whole outline rather than dropped, for §55's reason: a schedule that fails
    validation refuses the outline too, rather than landing beside a good one.
    """
    raw = payload.get("standing_milestones")
    if not isinstance(raw, list) or not raw:
        raise OutlineOutputError("outline carries no standing schedule")
    by_ordinal = {beat.ordinal: beat for beat in beats}
    chain = [rung for rung, _, _ in ladder.rungs]
    opening = chain.index(ladder.opening_rung) + 1

    out: list[tuple[Beat, str]] = []
    seen: set[int] = set()
    for entry in raw:
        if not isinstance(entry, Mapping):
            raise OutlineOutputError("each standing milestone must be an object")
        ordinal = entry.get("ordinal")
        rung = entry.get("rung")
        if not isinstance(ordinal, int) or isinstance(ordinal, bool):
            raise OutlineOutputError(
                f"standing milestone ordinal {ordinal!r} is not an integer"
            )
        if ordinal not in by_ordinal:
            raise OutlineOutputError(
                f"standing milestone names scene {ordinal}, which does not exist"
            )
        if ordinal in seen:
            raise OutlineOutputError(
                f"scene {ordinal} carries more than one standing milestone"
            )
        if not isinstance(rung, str) or rung not in chain:
            raise OutlineOutputError(
                f"standing milestone at scene {ordinal} names {rung!r}; the ladder holds "
                f"{chain} and a schedule may not add to it"
            )
        beat = by_ordinal[ordinal]
        if beat.story_order_key is None:
            raise OutlineOutputError(
                f"scene {ordinal} has no story position, so a standing milestone cannot be "
                "placed there; the beat sheet does not claim to run forwards"
            )
        seen.add(ordinal)
        out.append((beat, rung))

    out.sort(key=lambda pair: pair[0].ordinal)
    indices = [chain.index(rung) + 1 for _, rung in out]
    if all(index == opening for index in indices):
        raise OutlineOutputError(
            f"every standing milestone repeats the opening rung {ladder.opening_rung!r}; a "
            "schedule where nothing rises plans the book this schedule exists to end"
        )
    for (earlier_beat, earlier), (later_beat, later) in pairwise(out):
        if earlier == later:
            raise OutlineOutputError(
                f"scenes {earlier_beat.ordinal} and {later_beat.ordinal} both stand at "
                f"{earlier!r}; a schedule with a flat stretch tells those scenes to change "
                "nothing"
            )
    for lower, higher in pairwise([opening, *indices]):
        if higher < lower:
            raise OutlineOutputError(
                f"the standing schedule goes down ({indices} from an opening rung of "
                f"{opening} of {len(chain)}); on this brief {ladder.protagonist}'s standing "
                "does not fall inside the arc being written, and a world that wants a fall "
                "writes it in later by directive"
            )
    if max(indices) <= opening:
        raise OutlineOutputError(
            f"no standing milestone is above the opening rung ({indices} against {opening}); a "
            "schedule that never rises is the defect rather than a plan for it"
        )
    return out


def standing_milestone_records(
    schedule: Sequence[tuple[Beat, str]], *, subject: str, criterion: str
) -> list[lc.StateRecord]:
    """The rung schedule as `PROPOSED` `stands_at` edges — `milestone_records`' argument exactly.

    `PROPOSED` is what makes this safe and is why no new storage was needed: `state.is_canon`
    excludes it, so the context packet never hands a scheduled standing to a scene as
    established fact and `detect_contradictions` never weighs one against what the prose says.
    It informs generation and contaminates nothing.

    The criterion rides in the value slot, exactly as a declared world standing does, so
    `worlds.standing_of` reads a scheduled edge and a declared one the same way and
    two ladders cannot be spliced.

    Record ids are derived from the story position, so a re-run converges instead of
    accumulating a second schedule beside the first.
    """
    return [
        lc.StateRecord(
            record_id=f"standing-{beat.story_order_key}",
            kind=lc.StateRecordKind.RELATIONSHIP,
            subject=subject,
            predicate=worlds_mod.STANDS_AT_PREDICATE,
            value=criterion,
            object_ref=rung,
            authority=lc.StateAuthority.PROPOSED,
            story_position=lc.StoryPosition(order_key=str(beat.story_order_key)),
        )
        for beat, rung in schedule
    ]


def _payoff_windows(
    payload: Mapping[str, Any],
    beats: Sequence[Beat],
    promises: Sequence[Promise],
) -> list[tuple[Promise, str, str]]:
    """The payoff schedule as (promise, first_key, last_key), or a refusal naming what broke.

    **The same three-part shape `_milestones` has, because the failure modes are the same
    three.** A window may name a scene that does not exist (unsatisfiable), may be about a
    promise the ledger never opened (an invented debt), or may be individually valid while the
    *set* schedules the defect it was asked to plan around. `domain/promises.py` owns the last
    two checks — `window_fault` per promise, `schedule_fault` over the set — because they are
    arithmetic over story keys and this module owns none of that arithmetic.

    **Refused with the whole outline rather than dropped**, for the reason §55 gives for asking
    in one call: a schedule that fails validation refuses the outline too, rather than landing
    beside a good one. And an *absent* schedule is not a refusal — a book with no open
    promises was asked for none, so an empty list is the correct answer and validates as one.

    Windows are placed at beats, so a template that cannot say where its scenes sit in story
    time gets no schedule rather than an invented one. `story_order_key` is None exactly when
    the sheet is not entitled to answer, and `by_ordinal` below simply has no entry for it.
    """
    raw = payload.get("payoff_windows")
    if raw is None or (isinstance(raw, list) and not raw):
        return []
    if not isinstance(raw, list):
        raise OutlineOutputError("payoff_windows must be a list")
    by_ordinal = {
        beat.ordinal: beat.story_order_key
        for beat in beats
        if beat.story_order_key is not None
    }
    by_subject = {promise.subject: promise for promise in promises}
    keys = [key for _, key in sorted(by_ordinal.items())]

    out: list[tuple[Promise, str, str]] = []
    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, Mapping):
            raise OutlineOutputError("each payoff window must be an object")
        subject = entry.get("subject")
        first = entry.get("first_scene")
        last = entry.get("last_scene")
        if not isinstance(subject, str) or subject not in by_subject:
            raise OutlineOutputError(
                f"payoff window names promise {subject!r}, which this book has not opened; "
                "a schedule may not invent a debt"
            )
        if subject in seen:
            raise OutlineOutputError(f"promise {subject!r} carries more than one window")
        bounds: list[str] = []
        for name, ordinal in (("first_scene", first), ("last_scene", last)):
            if not isinstance(ordinal, int) or isinstance(ordinal, bool):
                raise OutlineOutputError(
                    f"payoff window for {subject!r} has {name} {ordinal!r}, "
                    "which is not a scene number"
                )
            if ordinal not in by_ordinal:
                raise OutlineOutputError(
                    f"payoff window for {subject!r} names scene {ordinal}, which either does "
                    "not exist or has no story position"
                )
            bounds.append(by_ordinal[ordinal])
        promise = by_subject[subject]
        start_key, end_key = bounds
        fault = window_fault(promise, start_key, end_key, keys=keys)
        if fault is not None:
            raise OutlineOutputError(f"payoff window for {subject!r}: {fault}")
        seen.add(subject)
        out.append((promise, start_key, end_key))

    fault = schedule_fault([(start, end) for _, start, end in out], keys=keys)
    if fault is not None:
        raise OutlineOutputError(fault)
    return out


def milestone_records(
    schedule: Sequence[tuple[Beat, Mapping[str, float]]],
    *,
    subject: str,
    seed: Mapping[str, Any],
) -> list[lc.StateRecord]:
    """The schedule as `PROPOSED` state records — the shape the system already has.

    `PROPOSED` is what makes this safe and is why no new storage was needed: `state.is_canon`
    excludes it, so the context packet never hands a milestone to a scene as established fact
    and `detect_contradictions` never weighs one against what the prose says. It informs
    generation and contaminates nothing — which is the property `progression_target` was
    written against and had no producer to exercise.

    Record ids are derived from the story position, so a re-run converges instead of
    accumulating a second schedule beside the first.
    """
    numeric_seed = {
        key: value for key, value in seed.items() if isinstance(value, int | float)
    }
    return [
        lc.StateRecord(
            record_id=f"milestone-{beat.story_order_key}",
            kind=lc.StateRecordKind.ASSERTION,
            subject=subject,
            predicate="status_snapshot",
            value={**numeric_seed, **dict(values)},
            authority=lc.StateAuthority.PROPOSED,
            story_position=lc.StoryPosition(order_key=str(beat.story_order_key)),
        )
        for beat, values in schedule
    ]

def outline_proposal(
    payload: Mapping[str, Any],
    *,
    base: PlanRevision,
    beats: Sequence[Beat],
    project_id: str,
    book_id: str,
    branch_id: str,
    result: CompletionResult,
) -> PlanProposal:
    """The model's outline as plan edits, one `SCENE_PLAN` item per beat.

    `scope` names the scene the statement is about, which is what makes the item reachable by
    `scene_plan_for` and keeps it out of every *other* scene's packet. `constraints_of` selects
    only locked constraints and promises, so a scene plan cannot leak into the constraint block
    of a scene it does not describe.

    `INTENDED` rather than `AUTHOR_LOCKED`: a model wrote it. Locking it would give a
    generated statement the standing of the director's own word, and `apply_plan_proposal`
    refuses to touch a locked item — so a wrong outline would be unfixable by the same
    machinery that produced it.
    """
    statements = _statements(payload, len(beats))
    # **CREATE where the statement is absent, UPDATE where it is already there.** A
    # create-only proposal cannot outline a *partially* outlined book, and partial is a state
    # the system reaches on its own: a manuscript that gains a scene keeps the statements for
    # the ones it had, and `narrative_planner`'s directive lane can delete a single scene plan
    # because they are deliberately unlocked. Measured before this branch existed — the
    # selector fired on the one missing beat, the handler's guard did not (it wanted *all*
    # present), and `apply_plan_proposal` raised `plan item 'scene-1-plan' already exists`
    # after the whole-book call had already been paid for, three times per plan epoch, with
    # nothing in the exception queue to show for it.
    present = {
        item.logical_id
        for item in base.items
        if item.kind is lc.PlanKind.SCENE_PLAN
    }
    edits = tuple(
        PlanEdit(
            action=(
                PlanEditAction.UPDATE
                if scene_plan_id_for(beat.logical_id) in present
                else PlanEditAction.CREATE
            ),
            logical_id=scene_plan_id_for(beat.logical_id),
            item=lc.PlanItem(
                logical_id=scene_plan_id_for(beat.logical_id),
                kind=lc.PlanKind.SCENE_PLAN,
                text=statement,
                authority=lc.PlanAuthority.INTENDED,
                locked=False,
                scope=lc.ResourceRef(
                    project_id=project_id,
                    book_id=book_id,
                    branch_id=branch_id,
                    logical_id=beat.logical_id,
                    kind=lc.ResourceKind.MANUSCRIPT_SCENE,
                ),
            ),
            reason=f"outline for scene {beat.ordinal} of {beat.of_total}",
        )
        for beat, statement in zip(beats, statements, strict=True)
    )
    return PlanProposal(
        base_plan_revision_id=base.plan_revision_id,
        summary=str(payload.get("summary") or f"outline for {len(beats)} scenes"),
        rationale=str(payload.get("rationale") or "every scene needs its own errand"),
        expected_outcome=str(
            payload.get("expected_outcome") or "each scene is planned distinctly"
        ),
        edits=edits,
        provider=result.provider,
        model=result.model,
        profile=PROFILE,
    )


def _policy_digest() -> str:
    """Content address of what shaped this outline, so a change to it reads as a change.

    The request is built from constants — the schema, the target length, the rules — none of
    which appear in the plan item the operator sees. Without this, editing them would leave
    every recorded decision byte-identical while every outline produced after it came from a
    different question.
    """
    return payload_digest(
        {
            "profile": PROFILE,
            "target_words": TARGET_WORDS,
            "schema": OUTLINE_SCHEMA,
        }
    )


def _decision(
    job: Job,
    base: PlanRevision,
    result: CompletionResult,
    resolution: Resolution,
    *,
    passed: bool,
    detail: str | None,
    resulting_revision_id: str | None = None,
) -> PolicyDecision:
    gate = GateOutcome(
        gate=GateKind.SHAPE,
        rule_or_critic_id="shape.outline.v0",
        passed=passed,
        # The model proposed the plan; a *deterministic* check over its shape and
        # distinctness is what passed or failed it. Never `MODEL_SELF_REPORT`, which
        # `PolicyDecision` refuses on a blocking gate anyway.
        verdict_source=VerdictSource.DETERMINISTIC,
        # Named, so `decide` can classify the refusal. A blocking gate that fails without a
        # veto escalates as "a blocking gate failed without naming a veto", and
        # `SHAPE_NOT_CONFORMING` is what a malformed structured answer already is elsewhere.
        vetoes=() if passed else (Veto.SHAPE_NOT_CONFORMING,),
        detail=detail,
    )
    # **`decide` rather than a hand-written RETRY, which is what this did and it was the only
    # handler in `application` that minted a failing outcome without consulting the ladder.**
    # The difference shows at the ceiling: a hard-coded RETRY on the third attempt requeues a
    # job the queue then poisons, and the POISONED path files no exception — so an outline
    # that could never conform went quiet and the book drafted every scene with no statement,
    # forever, with nothing in the operator's queue. `decide` escalates on exhaustion, which
    # is what puts it in front of a human.
    verdict, reason = decide(
        (gate,),
        job_id=job.job_id,
        attempt=job.attempts,
        max_attempts=job.max_attempts,
    )
    return PolicyDecision(
        decision_id=decision_id_for(job.job_id, job.attempts, (gate,)),
        outcome=verdict,
        gates=(gate,),
        job_id=job.job_id,
        base_revision_id=base.plan_revision_id,
        resulting_revision_id=resulting_revision_id,
        attempt=job.attempts,
        provider=result.provider,
        model=result.model,
        profile=PROFILE,
        fell_back_from=tuple(resolution.fell_back_from),
        invocations=result.invocations,
        total_tokens=result.usage.total,
        cost_usd=result.cost_usd,
        # The frozen configuration this outline was produced under. Omitted at first, which
        # is the same defect the sampler commit had just fixed one layer over: a schema or
        # target-length change would have left every stored digest identical while every
        # outline after it came from a different request.
        policy_config_digest=_policy_digest(),
        reason=detail if passed else (detail or reason),
    )


def make_outline_handler(
    registry: TextGenerator,
    store: OutlineStore,
    project_id: str,
    *,
    budget: BudgetPolicy | None = None,
    actor: str = "litharness",
) -> JobHandler:
    """Build the premise → outline → immutable plan handler."""
    budget_policy = budget or BudgetPolicy()

    def handle(job: Job, now: float) -> Sequence[Event]:
        book_id = job.payload.get("book_id")
        branch_id = job.payload.get("branch_id")
        if not isinstance(book_id, str) or not isinstance(branch_id, str):
            raise OutlineOutputError(f"job {job.job_id} lacks book_id/branch_id")

        stamp = datetime.fromtimestamp(now, tz=UTC).isoformat().replace("+00:00", "Z")
        base = store.plan_revision(book_id, branch_id)
        if base is None:
            raise OutlineOutputError(f"book {book_id} has no plan to outline against")
        premise = premise_of(base.items)
        if premise is None:
            raise OutlineOutputError(
                f"book {book_id} has no single premise; an outline of nothing is thirty "
                "scenes of plausible prose about nothing"
            )

        head = store.head(book_id, branch_id)
        if head is None:
            raise OutlineOutputError(f"book {book_id} has no manuscript to outline")
        beats = beats_for(head, template_for(head))

        # Already outlined: every beat has a statement. A no-op rather than a second call,
        # because a replayed job must converge and an outline is a whole-book generation.
        #
        # **`scene_plan_for` and not derived-id membership**, because the selector asks the
        # same question with the same function and the two must be complements. They were
        # not: the selector matched on scope-then-id while this matched on id alone, so a
        # statement scoped to a scene under a foreign id read *present* to one and *absent*
        # to the other — which spends a call and writes a second statement for a scene that
        # already had one.
        if all(
            scene_plan_for(base.items, beat.logical_id) is not None for beat in beats
        ):
            # Recorded rather than silent. A handler that returns no events *and* no decision
            # leaves the Conductor settling this attempt against whatever decision the job
            # last produced — which after a refused attempt is that refusal, so a job that
            # has nothing left to do settles as though it had failed.
            store.record_decision(
                PolicyDecision(
                    decision_id=decision_id_for(job.job_id, job.attempts, ()),
                    outcome=Outcome.ACCEPT,
                    gates=(),
                    job_id=job.job_id,
                    base_revision_id=base.plan_revision_id,
                    attempt=job.attempts,
                    profile=PROFILE,
                    policy_config_digest=_policy_digest(),
                    reason="every beat already carries a statement",
                ),
                decided_at=stamp,
            )
            return ()

        # The book's canon starting sheet, if it has one. `speaks_system_voice` is the same
        # question `render_prompt` asks before requesting a status line, and asking it the
        # same way here is what keeps a mystery from being given a level curve.
        canon = list(store.state_records(book_id, branch_id))
        seed_record = next(
            (
                record
                for record in canon
                if record.predicate == "status_snapshot"
                and state_mod.is_canon(record)
                and isinstance(record.value, Mapping)
            ),
            None,
        )
        seed = dict(seed_record.value) if seed_record is not None else {}
        # W2: the debts this book has already opened. Empty at a book's first outline —
        # promises are written by the summary handler after a scene is accepted — so the
        # payoff ask is silent there and this feature costs an un-replanned book nothing.
        open_promises = store.promises(book_id, branch_id, open_only=True)
        # The ladder this book's protagonist stands on, read off the same `canon` and carried
        # inside the world brief rather than beside it. `None` for every book whose canon
        # declares no chain, and then no standing schedule is asked for — exactly as a book
        # with no status sheet is asked for no milestones.
        world = world_brief.brief_for(canon)
        ladder = world.ladder if world is not None else None
        # **The world and its protagonist, off the `canon` already read two statements
        # above.** A second query would be a second answer to the same question, and the
        # drafting side's habit of calling `state_records` three times is the pattern this
        # deliberately does not copy. `brief_for` returns None for a book whose records this
        # vocabulary does not recognise and `protagonist_brief` returns None for one that names
        # nobody, and the request then carries neither field at all.
        request = render_outline_request(
            premise,
            beats,
            base=base,
            seed=seed or None,
            promises=open_promises,
            world=world,
            protagonist=worlds_mod.protagonist_brief(canon),
        )
        day = stamp[:10]
        provider, _ = registry.resolve(request.call_class)
        verdict = budget_check(
            budget_policy,
            store.spend_on(day),
            provider=provider.name,
            prompt_chars=len(request.prompt),
            max_output_tokens=request.max_output_tokens,
        )
        if not verdict.allowed:
            gate = GateOutcome(
                gate=GateKind.BUDGET,
                rule_or_critic_id=f"budget.{verdict.ceiling}.v0",
                passed=False,
                detail=verdict.reason,
            )
            refusal = PolicyDecision(
                decision_id=decision_id_for(job.job_id, job.attempts, (gate,)),
                outcome=Outcome.PARK,
                gates=(gate,),
                job_id=job.job_id,
                base_revision_id=base.plan_revision_id,
                attempt=job.attempts,
                profile=PROFILE,
                reason=verdict.reason,
            )
            store.record_decision(refusal, decided_at=stamp)
            return (
                Event(
                    event_type=EventType.BUDGET_EXHAUSTED,
                    project_id=project_id,
                    created_at=stamp,
                    actor=actor,
                    book_id=book_id,
                    branch_id=branch_id,
                    revision_id=base.plan_revision_id,
                    payload={
                        "decision_id": refusal.decision_id,
                        "job_id": job.job_id,
                        "ceiling": verdict.ceiling,
                        "reason": verdict.reason,
                    },
                ),
            )

        result, resolution = registry.complete(request)
        try:
            if not result.conforms or result.parsed is None:
                raise OutlineOutputError(
                    "provider response did not conform to the outline schema"
                )
            proposal = outline_proposal(
                result.parsed,
                base=base,
                beats=beats,
                project_id=project_id,
                book_id=book_id,
                branch_id=branch_id,
                result=result,
            )
            # Validated with the outline, so a schedule that plans stasis refuses the whole
            # answer rather than landing beside a good outline. One call, one verdict.
            schedule = (
                _milestones(result.parsed, beats, seed) if seed else []
            )
            # **Guarded exactly as the milestone schedule is, and for the same reason.** The
            # prompt asks for payoff windows only when the ledger has open rows, so a book that
            # owes nothing was asked for none — and validating an answer to a question that was
            # not put refuses the whole outline over a field the model volunteered and this
            # book could never use. Measured on Serial Pilot 1's first outline: the ledger is
            # empty at every book's *first* outline, because promises are written by the
            # summary handler after a scene is accepted, so this refused a good outline twice
            # before landing. §19.1: a refusal reached before the work costs time, never the
            # unit.
            windows = (
                _payoff_windows(result.parsed, beats, open_promises) if open_promises else []
            )
            # Guarded by canon rather than by the answer, exactly as the other two are: the
            # ask went out only for a book whose world declares a chain, so only such a book
            # has its answer validated. A book with no ladder that volunteered one is a field
            # this book could never use, and refusing a good outline over it is the failure
            # `windows` records above.
            rising = (
                _standing_milestones(result.parsed, beats, ladder)
                if ladder is not None
                else []
            )
            preview = apply_plan_proposal(base, proposal)
        except (OutlineOutputError, PlanProposalError, TypeError, ValueError) as error:
            # RETRY rather than escalate: the request is unchanged and a second draw of a
            # structured answer is a fair second try, exactly as a malformed scene draft is.
            refusal = _decision(
                job, base, result, resolution,
                passed=False, detail=f"{type(error).__name__}: {error}",
            )
            store.record_decision(refusal, decided_at=stamp)
            return (
                policy_decision_event(
                    refusal,
                    project_id=project_id,
                    created_at=stamp,
                    book_id=book_id,
                    branch_id=branch_id,
                    revision_id=base.plan_revision_id,
                    actor=result.provider,
                ),
            )

        decision = _decision(
            job, base, result, resolution,
            passed=True, detail=None,
            resulting_revision_id=preview.after.plan_revision_id,
        )
        try:
            accept_plan_proposal(
                store,
                proposal,
                project_id=project_id,
                created_at=stamp,
                actor=result.provider,
                decision=decision,
            )
        except PlanConflict as error:
            stale = _decision(
                job, base, result, resolution, passed=False, detail=str(error)
            )
            store.record_decision(stale, decided_at=stamp)
            return (
                policy_decision_event(
                    stale,
                    project_id=project_id,
                    created_at=stamp,
                    book_id=book_id,
                    branch_id=branch_id,
                    revision_id=base.plan_revision_id,
                    actor=result.provider,
                ),
            )

        # **After the plan, never before.** A refused outline must leave nothing behind, and
        # a schedule without the statements it was written against is a book planned twice
        # over by two different answers. `record_state_records` is INSERT OR IGNORE on the
        # derived record id, so a replayed job converges rather than accumulating a second
        # schedule beside the first.
        if schedule and seed_record is not None:
            store.record_state_records(
                book_id,
                branch_id,
                milestone_records(
                    schedule, subject=seed_record.subject, seed=seed
                ),
                created_at=stamp,
            )
        # The rung schedule lands under the same rule and for the same reason, and its record
        # ids are derived from the story position so a replay converges.
        if rising and ladder is not None:
            store.record_state_records(
                book_id,
                branch_id,
                standing_milestone_records(
                    rising, subject=ladder.protagonist, criterion=ladder.criterion
                ),
                created_at=stamp,
            )
        # The payoff schedule lands under the same rule and for the same reason: after the
        # plan, never before, so a refused outline leaves no windows behind. The write is an
        # UPDATE restricted to open rows and idempotent in its values, so a replayed job
        # converges rather than accumulating anything — there is nothing here to accumulate.
        for promise, start_key, end_key in windows:
            store.schedule_payoff_window(
                book_id,
                branch_id,
                promise.promise_id,
                window_start_key=start_key,
                window_end_key=end_key,
                plan_revision_id=preview.after.plan_revision_id,
            )
        return ()

    return handle


__all__ = [
    "BOOK_OUTLINE",
    "OUTLINE_PRIORITY",
    "OUTLINE_SCHEMA",
    "PROFILE",
    "TARGET_WORDS",
    "OutlineOutputError",
    "make_outline_handler",
    "milestone_records",
    "outline_job_id",
    "outline_proposal",
    "render_outline_request",
    "standing_milestone_records",
]
