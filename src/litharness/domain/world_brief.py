"""The world, as a planner may be told it: everything the packet says, minus every answer.

`domain/worlds.py` builds a world and `domain/context.py` hands it to the *writer*. Until this
module existed, the sentence the writer is told to execute — `This scene: {plan}` — was written
by a model that had seen the premise and the beat sheet and nothing else. Measured on
`main` at `83de11c` and pinned by
`test_neither_scene_plan_author_is_told_the_world_the_writer_is_handed`: of a 329-record world
with 7 rules, 21 consequences, 28 claims and 42 manifestations, **zero values reached either
planner payload**. So the rules, the consequence cascades the design calls "each a plot engine",
the cast with their wants and ties, and every hidden answer with its reveal scene arrived at the
writer under "Established facts", and the plan the writer was told to execute was written
against none of it.

**This is the packet's own rendering, regrouped and cut short of the secrets.** Every sentence
here comes from `worlds.project` with `state.describe` as the fallback — the same two calls
`context._state_item` makes, in the same order — so a fact reads to a planner exactly as it
reads to a writer. What differs is the grouping, which exists because a planner has to be able
to *find* a rule to put it to work, and the exclusions, which are the leak rail.

**The leak rail, and it is on the input rather than on the output.**
`worlds.hidden_record_ids(records, at=None)` is the maximal hidden set: with no coordinate every
scheduled claim reads as *not yet told*, which is the asymmetry `undisclosed_claims` documents
and exactly the conservative direction a brief wants. Every one of those records is dropped from
the facts. An answer re-enters in one place only — the `reveals` entry for the scene the world
scheduled it at — and an answer the book has no scene for never re-enters at all. So a planner
is told *what is asked* and *when it is answered* for every mystery, and *what the answer is*
only where the answer is due.

**A world that declares nothing is nothing.** `brief_for` returns `None` for records this
vocabulary does not recognise, so a book with no world hands its planners no field and the
payload is byte-identical to what it was — the additivity discipline `tests/test_worlds.py`
established for the packet, one layer up, and asserted rather than argued in
`tests/test_world_brief.py`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import litharness_contracts as lc

from litharness.domain import extraction as extraction_mod
from litharness.domain import state as state_mod
from litharness.domain import worlds as worlds_mod

#: The groups a brief sorts its facts into, in the order a planner reads them. **Rules first,
#: and the order is the argument**: a statement that puts the world to work is a statement about
#: a rule's consequence, so the rules and their cascades are what a planner needs before it
#: needs to know who is in the book. `other` is last and is never empty by design — a world's
#: history, bonds and cardinality shapes land there rather than being dropped.
GROUPS: tuple[str, ...] = (
    "rules",
    "cast",
    # **Straight after the people, because it is a fact about them.** A statement that puts a
    # capability to work is a statement about what somebody can do, so a planner needs the
    # inventory next to the person and before the machinery. Until 2026-08-22 there was no group
    # for it and a declared capability fell into `other` — measured, and the reason this line
    # exists (`research/quality-measurement/mother-of-learning-model-fit.md`).
    "capabilities",
    "systems",
    "institutions",
    "places",
    "creatures",
    "carriers",
    "agencies",
    "other",
)

#: Entity roles, in the group they belong to. `worlds.ENTITY_ROLES` is the source; the mapping
#: exists because two of the seven roles are plural-irregular and one subject may carry both.
_ROLE_GROUP: Mapping[str, str] = {
    "cast": "cast",
    "capability": "capabilities",
    "system": "systems",
    "institution": "institutions",
    "place": "places",
    "creature": "creatures",
    "carrier": "carriers",
    "agency": "agencies",
}


@dataclass(frozen=True, slots=True)
class Reveal:
    """One mystery: what it asks, when the world means to answer it, and — only then — how."""

    claim_id: str
    question: str
    #: The scene ordinal the world scheduled, or `None` for an answer this book has no scene
    #: for. `None` is not a missing value: it is the world saying *later than this book*, and
    #: `application/architect.py::story_key` mints no position for one on purpose.
    scene: int | None
    #: The recorded answer, present **only** when `scene` is inside this book. See the module
    #: docstring: this is the whole of the leak rail's input side.
    answer: str | None

    def to_jsonable(self) -> dict[str, Any]:
        if self.scene is None:
            return {
                "question": self.question,
                "answered_in_this_book": False,
                # Said rather than left blank. A planner handed a question with no window and
                # no note writes a scene that answers it, which is the failure this field
                # exists to refuse.
                "note": "this book does not answer this; do not answer it",
            }
        return {
            "question": self.question,
            "answered_in_this_book": True,
            "scene": self.scene,
            "answer": self.answer,
        }


@dataclass(frozen=True, slots=True)
class Ladder:
    """The one ordinal chain this book's protagonist stands on, and where they start on it.

    **The rungs carry their visible form and their price, and that is the whole of what a
    planner needs to place one.** `plan/handoff-numbers-go-up.md` Task 2: a milestone at a scene
    has to be a scene whose statement would plausibly change a standing, and a planner that was
    handed four bare ids could only guess which. The forms are the world's own `manifests_as`
    and `costs` values, unchanged — `criterion_brief` already hands the *writer* the chain as
    ids, and this is the same chain with the two facts a schedule is written against.

    The number is not carried. A rung's place in `rungs` is its number, counting from one; a
    stored integer beside the list would be a second answer to the same question, which is the
    rule `worlds.rung_index` states.
    """

    protagonist: str
    criterion: str
    #: `(rung_id, visible_form, cost_to_reach)`, lowest first. The chain, so index + 1 is the
    #: number a reader counts.
    rungs: tuple[tuple[str, str, str], ...]
    opening_rung: str

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "protagonist": self.protagonist,
            "criterion": self.criterion,
            "rungs": [
                {
                    "id": rung,
                    **({"visible_form": form} if form else {}),
                    **({"cost_to_reach": cost} if cost else {}),
                }
                for rung, form, cost in self.rungs
            ],
            "opening_rung": self.opening_rung,
        }


@dataclass(frozen=True, slots=True)
class WorldBrief:
    """What a scene planner may be told about the world its book runs on."""

    groups: tuple[tuple[str, tuple[str, ...]], ...]
    criteria: str | None
    reveals: tuple[Reveal, ...]
    #: The one ordinal chain this book's protagonist stands on, when canon declares one.
    #: `None` for every book written before 2026-08-22 and for every world that declares a
    #: partial order rather than a chain — see `ladder_for`.
    ladder: Ladder | None = None

    @property
    def facts(self) -> int:
        return sum(len(lines) for _, lines in self.groups)

    def to_jsonable(self) -> dict[str, Any]:
        payload: dict[str, Any] = {name: list(lines) for name, lines in self.groups if lines}
        if self.criteria:
            payload["how_this_world_ranks_people"] = self.criteria
        if self.reveals:
            payload["mysteries"] = [reveal.to_jsonable() for reveal in self.reveals]
        if self.ladder is not None:
            payload["ladder"] = self.ladder.to_jsonable()
        return payload


def brief_for(records: Sequence[lc.StateRecord]) -> WorldBrief | None:
    """The world a planner may see, or `None` when there is no world to see.

    **`None` and not an empty brief**, because the two mean different things to the caller and
    only one of them keeps a no-world payload byte-identical: an empty mapping rendered into a
    request is still a key, and `json.dumps` writes `null` for a value that is not there. The
    caller omits the field entirely when this returns `None`.

    The filters are `context.assemble`'s, minus the story-time cutoff and with no POV. There is
    no cutoff because a plan is written for a whole book before any of it exists, so slicing at
    a scene would hand the planner a world that has not finished arriving; there is no POV
    because a planner is not a character, and `state.visible_to(record, None)` therefore drops
    every record restricted to one. Both are the conservative direction.
    """
    canon = [
        record
        for record in records
        if state_mod.is_canon(record)
        and record.predicate not in extraction_mod.CONFIGURATION_PREDICATES
        and state_mod.visible_to(record, None)
    ]
    if not canon:
        return None
    projection = worlds_mod.project(canon)
    if not projection:
        # Nothing this vocabulary recognises. A book with an operator's own flat seed reaches
        # here and gets no brief, which is right: `state.describe` output is notation, and the
        # projection is what makes a record readable as an instruction.
        return None

    hidden = worlds_mod.hidden_record_ids(canon, at=None)
    rules = set(worlds_mod.rules(canon))
    roles = worlds_mod.entity_roles(canon)
    buckets: dict[str, list[str]] = {name: [] for name in GROUPS}
    for record in state_mod.in_story_order(canon):
        if record.record_id in hidden:
            continue
        line = projection.get(record.record_id)
        if line == "":
            continue  # folded into its node's own sentence, exactly as the packet folds it
        text = line or state_mod.describe(record)
        if not text.strip():
            continue
        buckets[_group_of(record.subject, rules, roles)].append(text)

    reveals = _reveals(canon)
    groups = tuple((name, tuple(buckets[name])) for name in GROUPS if buckets[name])
    criteria = worlds_mod.criterion_brief(canon)
    ladder = ladder_for(canon)
    if not groups and not criteria and not reveals:
        return None
    return WorldBrief(
        groups=groups, criteria=criteria, reveals=reveals, ladder=ladder
    )


def ladder_for(records: Sequence[lc.StateRecord]) -> Ladder | None:
    """The chain this book's protagonist stands on, or `None` when there is not exactly one.

    **`None` in four cases, and every one of them is a book that had no ladder to schedule
    against**: no declared protagonist, no standing, a standing whose criterion declares a
    partial order rather than a chain, and a protagonist standing on two ladders at once. The
    last is the only one that is a *choice*, and it is `worlds.criterion_of_rung`'s: which chain
    a schedule counts on has to be one answer, and a brief that picked would be inventing which
    ladder the world meant. Such a book gets today's outline request, which is the control this
    whole slice is measured against.

    Reads the standing off canon at no coordinate, so it is the *opening* rung for a book being
    outlined before any of it exists and the *live* rung for one being replanned mid-book —
    which is the behaviour a re-outline wants: the schedule is written from where the book
    actually is. `worlds.standing_of` owns that rule.
    """
    subjects = worlds_mod.entities_with_role(records, "protagonist")
    if not subjects:
        return None
    protagonist = subjects[0]
    standing = worlds_mod.standing_of(records, protagonist)
    if len(standing) != 1:
        return None
    [(criterion, rung)] = standing.items()
    chain = worlds_mod.ladder_of(records, criterion)
    if rung not in chain:
        return None
    forms = {
        record.subject: str(record.value or "").strip()
        for record in records
        if record.predicate == worlds_mod.MANIFESTS_PREDICATE
    }
    costs = {
        record.subject: str(record.value or "").strip()
        for record in records
        if record.predicate == "costs"
    }
    return Ladder(
        protagonist=protagonist,
        criterion=criterion,
        rungs=tuple((step, forms.get(step, ""), costs.get(step, "")) for step in chain),
        opening_rung=rung,
    )


def _group_of(
    subject: str, rules: set[str], roles: Mapping[str, tuple[str, ...]]
) -> str:
    """A rule beats a role, and the first role in `GROUPS` order beats the rest.

    A subject may be two things at once — the System is an `agency` and a `system` — and
    `worlds.entity_roles` refuses to pick one because forcing it would be the type hierarchy
    arriving through a dictionary. A *printed* brief has to pick one anyway, so it picks by the
    reading order above and the fact is printed once rather than twice.
    """
    if subject in rules:
        return "rules"
    for name in GROUPS:
        if any(_ROLE_GROUP.get(role) == name for role in roles.get(subject, ())):
            return name
    return "other"


def _reveals(records: Sequence[lc.StateRecord]) -> tuple[Reveal, ...]:
    """Every mystery, with its window; the answer only where the window is inside this book.

    **Keyed on `asks` rather than on `claim.content`**, and the distinction is the vocabulary's
    own: a claim that asks something owes a declared reveal, and a claim that merely *is*
    something — a character's secret, a fact nobody has needed yet — does not and is never
    owed one. Conflating them would make every private fact in a world a scheduled reveal and
    would put a cast member's secret in front of a planner as something to plan a scene around.
    """
    questions = worlds_mod.questions(records)
    if not questions:
        return ()
    answers = worlds_mod.claims(records)
    wrong = worlds_mod.false_claims(records)
    ordinals = worlds_mod.reveal_scenes(records)
    scheduled = worlds_mod.disclosures(records)
    found: list[Reveal] = []
    for claim_id in sorted(questions):
        if claim_id in wrong:
            continue  # a recorded error is not a mystery; its holder carries it
        positions = scheduled.get(claim_id, ())
        in_book = any(key is not None for key in positions)
        ordinal = ordinals.get(claim_id)
        found.append(
            Reveal(
                claim_id=claim_id,
                question=questions[claim_id],
                scene=ordinal if in_book and ordinal is not None else None,
                answer=answers.get(claim_id) if in_book and ordinal is not None else None,
            )
        )
    return tuple(found)


#: Instructions to a planner, in the register the existing outline rules already use: what to
#: do, never how to write, and never prose. **Nothing here asks for a name to be used.** A rule
#: that said "name the world's features" would make `research/quality-measurement/world_uptake.py`
#: a target rather than a counter, which is the shallow-because-easy failure the project refuses.
WORLD_RULES: tuple[str, ...] = (
    "Put the world's rules and their consequences to work. What happens in a scene should be "
    "something only this world could make happen: a rule biting somebody, a consequence "
    "landing, a price being paid in the currency this world actually charges in.",
    "Do not explain the world. A statement says what happens, and a scene where somebody "
    "explains how the world works is a scene where nothing happens.",
    "For a mystery answered in this book, the scene named as its window is where that answer "
    "lands, and it lands as an event somebody does or discovers rather than as an explanation.",
    "A statement for any scene before that window may carry the question and may never carry "
    "the answer. A mystery this book does not answer may appear as a question and never as an "
    "answer in any scene.",
)


#: The schedule ask, added only for a book whose canon declares a ladder. In the register the
#: milestone rules beside them already use — shape and fact, what to return and what a returned
#: schedule may not be — and deliberately **not one word about how a rise should read**.
#:
#: `plan/handoff-numbers-go-up.md` boundary 1: no "earn it", no "make the reader feel it", no
#: "triumphant", no "pay it off". A rung and its price are declared facts of the world, the same
#: class as the numbers the milestone rules already schedule; how a scene handles reaching one
#: is the writer's and the operator's, and a rule here that reached for a verb about it would be
#: this system's taste arriving in every outline. `tests/test_outline.py` checks the text.
#:
#: `{protagonist}` is filled by the caller with the declared id, exactly as `PROTAGONIST_RULES`
#: fills its own.
LADDER_RULES: tuple[str, ...] = (
    "Also return standing_milestones: the rung ladder.protagonist stands at by the end of "
    "certain scenes, as {{ordinal, rung}}.",
    "Use only the rung ids given in ladder.rungs. Do not invent rungs and do not rename them.",
    "The standing must actually move. A schedule where every milestone repeats the opening "
    "rung plans a book in which nothing rises.",
    "The standing never moves down: each milestone's rung is at or above the one before it, "
    "starting from the opening rung, and at least one milestone is above the opening rung.",
    "No two milestones in a row name the same rung.",
    "Place them at scenes whose statement, as you wrote it, would plausibly change what "
    "{protagonist} counts as.",
    "Every rung carries a cost_to_reach. The statement at a milestone scene says what is paid.",
)


__all__ = [
    "GROUPS",
    "LADDER_RULES",
    "WORLD_RULES",
    "Ladder",
    "Reveal",
    "WorldBrief",
    "brief_for",
    "ladder_for",
]
