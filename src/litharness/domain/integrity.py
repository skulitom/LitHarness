"""§12 step 6: the integrity gate, and the one detector that is structurally LitHarness's.

Until this module existed the wired ladder was a single gate, `shape.draft.v0`, so *accepted*
meant "a string of plausible length" — §17's Stage 1 exit clause about planted defects being
caught by gates had nothing to be caught by. This is the gate. What it is not is a detector
suite: §8.4 puts the LitRPG rule and predicate vocabulary in ContinuityEvaluation's pack, and
§13 forbids depending on a sibling, so those findings arrive as an `EvaluationArtifact` and
are ingested (`adapters/evaluation_artifact.py`).

**The gate's job is the part that is genuinely policy**, and it is worth listing because it
looks trivial until each line is wrong once:

1. A finding blocks on **severity and status together**, never severity alone. Both fixtures
   ship negative controls — an intentional motif, a deliberate lie — which a *correct*
   detector emits and a correct policy must not refuse.
2. An **uncalibrated model critic may not block** (§10.4), so a finding whose
   `confidence_basis` is not `deterministic` annotates. This is the same invariant
   `PolicyDecision.__post_init__` enforces from the other end; enforcing it here as well means
   a non-deterministic finding cannot even reach the constructor that would raise on it.
3. The gate runs **over findings against this node**, not over the whole book. A defect in
   scene 2 must not park the job drafting scene 5 — §4.1's "a blocked item never stalls the
   queue" — and, more sharply, blocking every subsequent beat on an old finding would convert
   one defect into a stalled book.

**`state.contradiction.v0` is the one check implemented here, and it is here because no
sibling can do it.** It is a property of *this store's* records rather than of a fixture's
prose: two canon records asserting different values for the same subject and predicate at the
same story position, with no supersession between them. ContinuityEvaluation evaluates a
finished manuscript it is handed; it never sees a LitHarness store mid-run, and the corruption
this catches — §12 step 5's extraction writing a record that contradicts one already accepted
— can only happen inside the loop. It reads records and nothing else, so no amount of prose
phrasing satisfies or defeats it.

It emits **zero findings on both golden fixtures**, which is the negative-control leg §8.3
demands and the reason it can be turned on blocking without a calibration programme: a check
that fires on a conforming book is not a floor, it is a tax.

**It now has an in-process producer, and until it did, that silence proved nothing.**
`domain/extraction.py` reads state out of every accepted scene, so this detector's input is
no longer only what an operator imported — which is what the paragraph above always meant by
"can only happen inside the loop", and what nothing in `src/` could actually cause. The
mutation leg is in `tests/test_extraction.py`: perturb a conforming litrpg scene's status
line and exactly one MAJOR appears naming the position; restore it and the detector goes
quiet.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import litharness_contracts as lc

from litharness.domain import state as state_mod
from litharness.domain import worlds as worlds_mod
from litharness.domain.findings import (
    UNRESOLVED_STATUSES,
    DetectorInput,
    Finding,
    Severity,
    Status,
    finding_id_for,
    vetoes_for,
    worst,
)
from litharness.domain.policy import GateKind, GateOutcome, VerdictSource
from litharness.domain.promises import overdue_promises

#: This module's own rule id, in the vocabulary the fixtures use for theirs.
#:
#: **`v1` from 2026-08-21, because the grouping key is the arithmetic.** `DUPLICATE_RULE` states
#: the convention — "the threshold below is part of its arithmetic and a changed threshold is a
#: changed rule" — and adding `object_ref` to the key changes which inputs produce a finding, so
#: it is a changed rule by exactly that test. A finding recorded before today and one recorded
#: after are now distinguishable, which is the whole point of the version.
#:
#: Prose elsewhere in this repository that names `state.contradiction.v0` — `migrations/
#: 016_state_retraction.sql`, PLAN.md, README.md — is describing what happened under v0 and
#: stays as written; those are history, not a reference to the live rule.
CONTRADICTION_RULE = "state.contradiction.v1"

#: The gate's id in a recorded policy decision, alongside `shape.draft.v0`. Judges the
#: candidate, so its refusal is *about the work* and costs an attempt.
INTEGRITY_GATE = "integrity.findings.v0"

#: The pre-flight half, and the distinction is the whole of why it exists.
#:
#: A **standing** finding was in the store before this attempt began. The candidate cannot
#: have caused it and cannot clear it, so every retry is guaranteed to meet the same refusal
#: — which means it is a refusal reached *in front of* the work, exactly like a budget
#: ceiling. §19.1 states the rule after finding two instances of it: **a refusal reached
#: before the work must cost time, never the unit.** Checked before the provider call so it
#: costs no tokens either, and settled as a revivable PARK so that dismissing the finding
#: leaves work to resume. Charging it behind the generation is what made the operator's
#: correct action — dismiss the negative control — arrive three ticks too late to matter.
STANDING_GATE = "integrity.standing.v0"


# --- the duplicate-scene detector ------------------------------------------------------------
#
# **Moved here from `domain/craft.py` when that module was deleted (stage-0 §133).** It was
# always the odd one out there: `craft.py` measured properties of prose and this finds a scene
# the generator wrote twice, which is a story defect and a blocking one. Its own comment below
# said so — the metric beside it could not name *which* scene a run came from, and a gate has to
# name what it refuses. The metric is gone with its module; this is the half that gates.
#
# `craft.repeated_span.v0` and its calibration are not rehomed and are not coming back: §10.4
# refused an uncalibrated craft gate, nothing ever calibrated one, and §129 put every prose
# property below reader direction.

#: Edge punctuation folded off a word before comparison. Spelled with escapes because the
#: dashes and curly quotes are confusable with ASCII on sight.
_SPAN_TRIM = ".,;:!?\"'()[]\u2014\u2013\u2026\u201c\u201d\u2018\u2019"

_SYSTEM_BLOCK = re.compile(r"^\[(?:STATUS|INVENTORY|SKILLS|QUESTS)\].*$", re.MULTILINE)

#: didn't know what to say", "for the first time in his life" — and a metric that fires on
#: those is reporting English. Measured: published serials carry a *median* longest
#: cross-chapter span of 10-12 words, so eight sits just under the observed noise floor.
_MIN_SPAN = 8

#: Stop looking once a span is this long. The difference between "180 words repeated" and
#: "240 words repeated" changes no decision anyone would make, and the cap is what keeps a
#: wholly duplicated scene from costing quadratic time in the drafting loop.
_SPAN_CAP = 200


def _span_tokens(text: str) -> tuple[list[str], list[str]]:
    """Words as written and words folded for comparison, positionally aligned.

    Folding is case and edge punctuation only. Comparison is on whole words rather than
    characters so that a match cannot begin mid-word — the same reason `_identifier_words`
    exists in `domain/propagation.py`, arrived at there by the same bug.
    """
    original = _SYSTEM_BLOCK.sub("", text).split()
    folded = [word.lower().strip(_SPAN_TRIM) for word in original]
    return original, folded


@dataclass(frozen=True, slots=True)
class RepeatedSpan:
    """The longest verbatim run one unit shares with a *named* other, and where it sits."""

    words: int
    #: Word offset of the run within the candidate.
    at: int
    quote: str
    #: Which other unit the run also appears in. The half `repeated_span` cannot report.
    source_id: str


def longest_repeated_span(text: str, others: Mapping[str, str]) -> RepeatedSpan | None:
    """The longest run of words `text` repeats from any of `others`, and which one.

    **A second implementation beside `repeated_span`, and the duplication is deliberate.**
    Two things differ, and both matter to a caller that refuses prose rather than annotating
    it. It reports *which* unit the run came from, which a gate has to name in its refusal
    and the metric's `Sequence[str]` cannot express. And it does not stop early: the metric
    breaks at `_SPAN_CAP` because an annotation only needs to know the number is large, while
    a gate comparing against a threshold must not report a capped value as the true one.

    Folding `repeated_span` into this would have changed the shipped metric's arithmetic, and
    this project's own rule is that changed arithmetic is a new metric id — `scene_echo`
    moved to `.v1` for exactly that, because `promoted_gate` looks a calibration up by
    `metric_id` and evidence recorded against old values applied to new arithmetic is a
    silent inversion. `craft.repeated_span.v0` is left byte-identical.

    Returns None when nothing reaches `_MIN_SPAN`, which is "no run that long" and not "no
    repetition".
    """
    _, folded = _span_tokens(text)
    original = _SYSTEM_BLOCK.sub("", text).split()
    best = 0
    best_at = 0
    best_source = ""
    for source_id, other in others.items():
        _, other_folded = _span_tokens(other)
        index: dict[tuple[str, ...], list[int]] = {}
        for start in range(len(other_folded) - _MIN_SPAN + 1):
            index.setdefault(tuple(other_folded[start : start + _MIN_SPAN]), []).append(start)
        for position in range(len(folded) - _MIN_SPAN + 1):
            for start in index.get(tuple(folded[position : position + _MIN_SPAN]), ()):
                length = _MIN_SPAN
                while (
                    position + length < len(folded)
                    and start + length < len(other_folded)
                    and folded[position + length] == other_folded[start + length]
                ):
                    length += 1
                if length > best:
                    best, best_at, best_source = length, position, source_id
    if not best:
        return None
    return RepeatedSpan(
        words=best,
        at=best_at,
        quote=" ".join(original[best_at : best_at + best]),
        source_id=best_source,
    )

def _value_key(value: Any) -> str:
    """A stable comparison key for a record value, which the contract types as `Any`.

    JSON with sorted keys rather than `repr`, so `{"a": 1, "b": 2}` and `{"b": 2, "a": 1}` are
    the same value and not a contradiction. Getting this wrong would make the detector fire on
    two identical status snapshots whose keys were written in a different order — a finding
    about dict iteration order, reported as a continuity defect.
    """
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


#: Predicates whose values are a **set** and not a slot, so two of them are two facts rather
#: than a disagreement. One member, and it is the one `domain/worlds.py` documents as plural:
#: *"a subject may be two things at once — the System is an `agency` and a `system`, a guild is
#: an `institution` and, when it acts, `cast`. Forcing one would be the type hierarchy arriving
#: through a dictionary."*
#:
#: **Found by the first book ever drafted on a world that declares a protagonist**, 2026-08-22.
#: A protagonist is a second `entity_role` on a cast member, so `nella_scur` carried `cast` and
#: `protagonist`; this detector read that as `entity_role holds 2 different values`, MAJOR and
#: blocking, and two of the book's eight scenes went parked and poisoned before any prose was
#: judged. The defect is older than that change and the docstring above predicted it — no world
#: had happened to give one subject two roles until one did.
#:
#: Deliberately a **named set of one** rather than a rule about shapes. "Multi-valued" is a
#: property of a predicate's meaning and nothing in a record carries it, so the alternative is a
#: heuristic — and a heuristic that guesses which disagreements are allowed is the frozen arity
#: table `detect_cardinality_violations` refuses. A world that wants a second multi-valued
#: predicate declares a cardinality shape instead, which is checkable.
MULTI_VALUED: frozenset[str] = frozenset({worlds_mod.ENTITY_ROLE_PREDICATE})


def disagreement_key(record: lc.StateRecord) -> tuple[str, str, str, str]:
    """The slot a record fills: subject, predicate, edge, and story position.

    **One grouping with two callers, and they must never drift.** `detect_contradictions`
    reports two values in one slot as a defect; `superseded` decides, before anything is
    accepted, that a second declaration of one slot replaced the first. If those two disagreed
    about what a slot is, acceptance would leave behind exactly the pairs the detector fires
    on — which is the failure that made this function exist (§139).
    """
    return (
        record.subject,
        record.predicate,
        record.object_ref or "",
        state_mod.order_key_of(record) or "",
    )


def superseded(
    records: Sequence[lc.StateRecord], *, declared_at: Mapping[str, str]
) -> tuple[str, ...]:
    """Of these records, the ones a later declaration of the same slot replaced.

    **What this is for, and it is a blocker rather than a tidy-up.** `world declare` appends
    and has no retraction path, so an Architect that improves its own declaration writes a
    second record into the same slot. Accepting both makes them canon, `detect_contradictions`
    reads two values at one story position, and the finding is MAJOR and **blocking** — so
    every scene of the book is refused, three times each, and the unit poisons. Measured on
    Serial Pilot 7: four such pairs, three of them the agent's own scratch probes and one a
    criterion it rewrote, and not one word of the book could be drafted. `dismiss` does not
    help, because the pre-flight gate reads stored findings and the *integrity* gate re-derives
    them from canon on every attempt.

    **The rail this keeps is `promote_state_records`' "only ever upward".** Nothing here
    demotes anything: the replaced records simply are not carried, and stay the proposals they
    already were. So canon is never rewritten, the record of what was proposed is intact, and
    `world summary` still counts them.

    `declared_at` is when each record was written, keyed by record id — the store has it and
    `lc.StateRecord` does not, because declaration order is a fact about the writing and not
    about the world. Ties break on record id so the answer is deterministic.

    **Multi-valued predicates are skipped**, on `MULTI_VALUED`'s licence and for its reason: a
    subject carrying both `cast` and `protagonist` is two facts, and treating the second as
    replacing the first would silently delete the protagonist a world just declared.

    **Canon holds its slot against every proposal in it, and is never itself reported
    replaced.** Two rules, and each closes a hole the other cannot.

    - *A proposal loses to canon whatever the clock says.* Until 2026-08-29 this ordered a
      group by declaration time alone, and every caller passed only the proposals, so the
      question never arose. It arises on the **second** `world accept`: the proposals a first
      round left behind sit in slots canon now holds, nothing supersedes them among the
      proposals, they promote, and canon ends with two values in one slot — MAJOR, blocking,
      every scene of the book refused. That is §139's blocker reopening one round later, and
      it reproduces on Serial Pilot 13's accepted world, where a second accept turns 24
      leftovers into 24 blocking findings.
    - *Canon is never replaced, not even by later canon.* Two accepted records in one slot is
      a real contradiction and `detect_contradictions` exists to say so. Letting the older one
      drop out here would hide a canon defect from every caller that filters on this — which is
      the failure of a tidy-up wearing a repair's clothes.

    So the rail above holds in both directions: nothing is demoted, and nothing accepted is
    quietly dropped from what anybody reads.
    """
    groups: dict[tuple[str, str, str, str], list[lc.StateRecord]] = {}
    for record in records:
        if record.predicate in MULTI_VALUED:
            continue
        groups.setdefault(disagreement_key(record), []).append(record)

    replaced: list[str] = []
    for members in groups.values():
        if len({_value_key(record.value) for record in members}) < 2:
            continue
        canon = [record for record in members if state_mod.is_canon(record)]
        proposals = [record for record in members if not state_mod.is_canon(record)]
        if canon:
            replaced.extend(record.record_id for record in proposals)
            continue
        ordered = sorted(
            proposals,
            key=lambda record: (declared_at.get(record.record_id, ""), record.record_id),
        )
        replaced.extend(record.record_id for record in ordered[:-1])
    return tuple(sorted(replaced))


def in_force(
    records: Sequence[lc.StateRecord], *, declared_at: Mapping[str, str]
) -> tuple[lc.StateRecord, ...]:
    """The records that speak for this world: everything `superseded` did not replace.

    **The positive form of the same rule, because the read views needed one.** `world accept`
    asks which records to leave behind; every view that reports what a world *contains* is
    asking the complementary question and, until 2026-08-29, none of them asked it at all —
    they read the raw record list, strays included.

    What that cost is `world ladders` printing `[]` for a world whose three chains resolve.
    Serial Pilot 13's accepted world holds, for each rung edge, the criterion-less proposal the
    Architect wrote first and the corrected canon edge that replaced it. `worlds.rank_order`
    reads an edge with no criterion as belonging to **every** ladder, so the strays spliced all
    three chains, `ladder_of` returned empty for each, and the operator's view of a sound world
    was empty. `world check` disagreed with `world accept` about the same world for the same
    reason — one saying it contradicts itself, the other having accepted it without `--force`,
    which is two answers to one question.

    Order is preserved, so a caller that hands this to `state.in_story_order` gets what it got
    before. A world with nothing replaced comes back as the sequence it was given.
    """
    replaced = set(superseded(records, declared_at=declared_at))
    return tuple(record for record in records if record.record_id not in replaced)


def detect_contradictions(subject: DetectorInput) -> list[Finding]:
    """Canon records that disagree with each other at the same story position.

    Grouped on `(subject, predicate, object_ref, order_key)` — the position is part of the key
    on purpose. A stat that moves between scenes is a story; the same stat holding two values
    *at one moment* is a defect. Dropping the position from the key would report every ordinary
    change in the book, which on the litrpg fixture is every status snapshot after the first.

    **`object_ref` entered the key on 2026-08-21, and what it fixes is a detector that was
    reading the annotation.** Measured before the change, on the four spellings in
    `test_the_edge_cases_the_design_note_measured`: `card_of_ashes held_by → silas` beside
    `→ marta` produced **0** findings; the same pair with a different note on each edge produced
    **1, MAJOR, blocking**; `ash trait → keen_scent` beside `→ night_sight` — an ordinary
    creature with two traits — produced 0 as edges and 1 as values. So the thing that decided
    whether an impossibility was reported was whether the prose happened to annotate the two
    edges differently, and a perfectly ordinary two-valued relation was refused whenever it did.

    With the edge in the key, two edges are two facts and never contradict each other here.
    Exclusivity is not lost; it moves to where it can be *declared* —
    `detect_cardinality_violations` reads the world's own "at most one holder" shape. This is
    `plan/state-model-abilities.md` §5 item 1 and it is deliberately the pair of changes rather
    than either alone: adding the edge to the key without the cardinality detector would make
    one object in two hands permanently invisible.

    **Both golden fixtures hold zero records with `object_ref` set**, so their grouping is
    unchanged and their silence is untouched by construction rather than by a re-check.

    Only canon takes part. A `PROPOSED` record is a candidate no decision has accepted, and
    two proposals disagreeing is what proposals are for.

    **`MULTI_VALUED` predicates are skipped**, and there is exactly one of them. See the
    constant: a subject carrying both `cast` and `protagonist` is two facts about one person and
    not a disagreement, and reading it as one poisoned the first book ever drafted on a world
    that declared a protagonist.
    """
    canon = [record for record in subject.records if state_mod.is_canon(record)]
    groups: dict[tuple[str, str, str, str], list[lc.StateRecord]] = {}
    for record in canon:
        groups.setdefault(disagreement_key(record), []).append(record)

    findings: list[Finding] = []
    for (subject_id, predicate, object_ref, order_key), members in sorted(groups.items()):
        if predicate in MULTI_VALUED:
            continue
        distinct = {_value_key(record.value): record for record in members}
        if len(distinct) < 2:
            continue
        conflicting = state_mod.in_story_order(distinct.values())
        claim = {
            "subject": subject_id,
            "predicate": predicate,
            "object_ref": object_ref,
            "order_key": order_key,
            "values": sorted(distinct),
            "records": sorted(record.record_id for record in conflicting),
        }
        findings.append(
            Finding(
                finding_id=finding_id_for(CONTRADICTION_RULE, subject_id, claim),
                category=lc.FindingCategory.WORLD_RULE.value,
                severity=Severity.MAJOR,
                status=Status.OPEN,
                subtype="contradictory_records",
                rule_or_critic_id=CONTRADICTION_RULE,
                logical_id=subject.logical_id,
                confidence_basis=lc.ConfidenceBasis.DETERMINISTIC.value,
                message=(
                    f"{subject_id} {predicate} holds {len(distinct)} different values at "
                    f"story position {order_key or '(unplaced)'}: "
                    + ", ".join(sorted(distinct))
                ),
                source={"claim": claim},
            )
        )
    return findings


#: Rule id for the scoped-cardinality check. Versioned like every other; the grouping is the
#: rule, and a changed grouping is a changed rule.
CARDINALITY_RULE = "state.cardinality.v0"


def detect_cardinality_violations(subject: DetectorInput) -> list[Finding]:
    """More of a relation than the world said there could be, at one story position.

    **The half of `plan/state-model-abilities.md` §5 item 1 that makes the other half safe.**
    `detect_contradictions` now keys on `object_ref`, so two edges never contradict each other
    there. Exclusivity has to be *declared* instead, and this is what reads the declaration: a
    world says "at most one `possessed_by` per carrier at a time" as five ordinary records
    (`research/progression-generalization.md` §8.2's encoding, unchanged) and this counts.

    **A frozen arity table was the rejected alternative and the rejection is the design.**
    `held_by → functional` welds one world's physics into the engine: a workshop is jointly
    owned, shares are fractionally owned, a bond is unique in one world and plural in another.
    So an undeclared predicate stays untyped and non-blocking, and the cost of that is stated
    rather than hidden — a world that declares no shape is checked for nothing, which is the
    price of free-form predicates being free.

    **Maxima only.** Under open-world reading a missing value is unknown rather than false, so a
    minimum count is unsafe until a scope is explicitly closed and none can be. `domain/worlds.py`
    refuses to build a shape from a minimum, so there is nothing here to read one from.

    Blocking, MAJOR and `deterministic`, on the same licence `state.contradiction.v0` has: it
    reads records and nothing else, no phrasing satisfies or defeats it, and it emits **zero
    findings on both golden fixtures** — which hold no shapes at all, so the check is vacuous
    there by construction rather than by luck.
    """
    canon = [record for record in subject.records if state_mod.is_canon(record)]
    shapes = worlds_mod.cardinality_shapes(canon)
    if not shapes:
        return []
    roles = worlds_mod.entity_roles(canon)

    findings: list[Finding] = []
    for shape in sorted(shapes, key=lambda item: item.constraint_id):
        buckets: dict[str, list[lc.StateRecord]] = {}
        for record in canon:
            if record.predicate != shape.predicate or not record.object_ref:
                continue
            if not worlds_mod.in_scope(record, shape, roles):
                continue
            buckets.setdefault(worlds_mod.group_of(record, shape.group_key), []).append(record)
        for bucket in sorted(buckets):
            members = buckets[bucket]
            targets = sorted({record.object_ref or "" for record in members})
            if len(targets) <= shape.maximum:
                continue
            claim = {
                "constraint": shape.constraint_id,
                "predicate": shape.predicate,
                "group_key": shape.group_key,
                "group": bucket,
                "maximum": shape.maximum,
                "found": targets,
                "records": sorted(record.record_id for record in members),
            }
            findings.append(
                Finding(
                    finding_id=finding_id_for(CARDINALITY_RULE, shape.constraint_id, claim),
                    category=lc.FindingCategory.WORLD_RULE.value,
                    severity=Severity.MAJOR,
                    status=Status.OPEN,
                    subtype="cardinality_exceeded",
                    rule_or_critic_id=CARDINALITY_RULE,
                    logical_id=subject.logical_id,
                    confidence_basis=lc.ConfidenceBasis.DETERMINISTIC.value,
                    message=(
                        f"{shape.constraint_id} admits at most {shape.maximum} "
                        f"{shape.predicate} per {shape.group_key}; "
                        f"{bucket.replace(chr(0), ' at ')} has {len(targets)}: "
                        + ", ".join(targets)
                    ),
                    source={"claim": claim},
                )
            )
    return findings


#: Rule id for the duplication check. Versioned like every other, because the threshold below
#: is part of its arithmetic and a changed threshold is a changed rule.
DUPLICATE_RULE = "integrity.duplicate_scene.v0"

#: Words of verbatim overlap with an earlier accepted scene at which a candidate is refused.
#:
#: **Placed in an empty region of two independently measured distributions, which is the only
#: reason a number this consequential is defensible without a calibration.**
#:
#: *Above what published human prose does.* §49 measured the longest verbatim cross-chapter
#: span over 24 published RoyalRoad serials: **93 words** (undeclared 2025), 91 (declared-AI),
#: 70 (pre-2023). Human authors write recaps, epigraphs and quoted prophecies and repeat them
#: exactly, and that mechanism is what produces long *legitimate* spans — so the threshold
#: sits above the largest one anybody has observed, with headroom, rather than at it.
#:
#: *Inside a gap in this system's own output.* Across Book Zero's 30 scenes the longest span
#: each scene shares with any earlier one is bimodal with nothing in between: twenty-four
#: scenes score 0-47 words and five score 353, 431, 700, 737 and 872. **No scene falls between
#: 48 and 352**, so every threshold in that range separates the same five, and the choice is
#: not delicate. The golden fixtures — human-authored — reach 17 (mystery) and 0 (litrpg).
#:
#: And the two methods agree. Whole-scene `difflib` similarity above 0.5 selects scenes 8, 11,
#: 17, 18 and 22; this threshold selects scenes 8, 11, 17, 18 and 22. Two measures with
#: nothing in common but the input picked the identical set.
#:
#: **It is a deterministic threshold and therefore needs no calibration, which is the whole
#: reason this check lives here rather than in `craft`.** §10.4's bar governs claims about
#: *quality*, which is why `craft.repeated_span.v0` measured all five of these and could
#: refuse none of them. "These 872 words appear in scene 6 and again in scene 11" is not an
#: opinion about whether the prose is good; it is arithmetic over two strings, and
#: `craft.py`'s own defence of the metric says exactly that.
DUPLICATE_SPAN_WORDS = 120


def detect_duplicate_scene(subject: DetectorInput) -> list[Finding]:
    """A candidate that reproduces an earlier accepted scene verbatim, at length.

    **The defect Book Zero drove through five times while every gate said accept.** Thirty
    scenes, 31 decisions, all ACCEPT, zero findings — and five of those scenes were near-copies
    of an earlier one, the longest sharing 872 consecutive words with scene 6. Nothing in the
    ladder could see it: the shape gate counts characters, the contradiction detector reads
    state records, and `craft.repeated_span.v0` measured it exactly and is forbidden to block
    because §10.4 refuses an uncalibrated craft gate. The measurement was never the gap.

    **Why the refusal is a retry rather than an escalation, and why that only became true
    recently.** `vetoes_for` maps every blocking finding onto `CONTINUITY_BREACH`, which
    §4.2's ladder classifies `RETRYABLE` — the model wrote the wrong thing, so ask again. That
    was the wrong action as recently as the sampler fix: the prompt is frozen onto the job
    payload, so under greedy decoding a retry regenerated the identical duplicate and burned
    the attempt budget rediscovering it. With the seed derived from the attempt number, attempt
    *n* is a genuinely different draft, so a retry is now a real second chance rather than a
    slower way to reach the same refusal.

    **The false positive it can produce is a legitimate recap**, and it is left reachable
    rather than engineered away. The operator's remedy already exists and is the one slice 9
    built: dismiss the finding, revive the unit. Suppressing recaps by rule would need a
    definition of "recap" this project does not have, and would be a guess wearing the
    threshold's authority.
    """
    if not subject.candidate or not subject.prior_prose:
        return []
    span = longest_repeated_span(subject.candidate, dict(subject.prior_prose))
    if span is None or span.words < DUPLICATE_SPAN_WORDS:
        return []

    claim = {
        "words": span.words,
        "at": span.at,
        "source_logical_id": span.source_id,
        "threshold": DUPLICATE_SPAN_WORDS,
    }
    quote = span.quote if len(span.quote) <= 200 else span.quote[:200] + "…"
    return [
        Finding(
            finding_id=finding_id_for(DUPLICATE_RULE, subject.logical_id, claim),
            category=lc.FindingCategory.REPETITION.value,
            severity=Severity.MAJOR,
            status=Status.OPEN,
            subtype="duplicate_scene",
            rule_or_critic_id=DUPLICATE_RULE,
            logical_id=subject.logical_id,
            confidence_basis=lc.ConfidenceBasis.DETERMINISTIC.value,
            # The evidence travels with the refusal, for `repeated_span`'s reason: a number
            # that has to be interpreted gets interpreted, and a quote does not.
            message=(
                f"{span.words} words of this scene appear verbatim in {span.source_id}, "
                f"starting at word {span.at} (threshold {DUPLICATE_SPAN_WORDS}): {quote}"
            ),
            source={"claim": claim},
        )
    ]


#: Rule id for the overdue-promise check (§61 Add 2). Versioned like every other; the
#: comparison is the rule, and a changed comparison would be a changed rule.
OVERDUE_RULE = "promise.overdue.v0"


def detect_overdue_promises(subject: DetectorInput) -> list[Finding]:
    """A promise the book opened whose due position is behind the scene being drafted.

    **PLAN §1a.3 item 3's first instrument, and it is advisory by construction.** The
    arithmetic here is deterministic — `promises.overdue_promises` is string comparison over
    zero-padded story keys — but the ledger it reads is model-sourced: the promise rows come
    from the summary call's `promises_opened`/`promises_paid` answer, so the *inputs* carry a
    model's judgment and §10.4's bar applies to the whole chain. Severity is MINOR and the
    confidence basis is `heuristic`, which pins both halves of "never blocks, never parks":
    MINOR is below `BLOCKING_SEVERITIES`, so the finding annotates the decision rather than
    refusing it, and a MINOR finding recorded against the beat never trips the standing
    pre-flight — a MAJOR here would become standing and park the beat until dismissed, which
    for an uncalibrated instrument would be a park with no evidence behind it.

    **Abstains exactly where milestones abstain.** `story_order_key` is None when the
    template is not chronological — the sheet minted no position, so there is nothing to be
    overdue *relative to* — and the check returns nothing rather than comparing against a
    guessed coordinate. The evaluation lane assembles no promise input at all, so this
    detector is silent there by the same defaults `prior_prose` set the precedent for.
    """
    findings: list[Finding] = []
    for promise in overdue_promises(subject.open_promises, subject.story_order_key):
        claim = {
            "subject": promise.subject,
            "opened_at": promise.opened_at_key,
            "due": promise.due_key,
            "current": subject.story_order_key,
        }
        findings.append(
            Finding(
                finding_id=finding_id_for(OVERDUE_RULE, subject.logical_id, claim),
                category=lc.FindingCategory.PROMISE_PAYOFF.value,
                severity=Severity.MINOR,
                status=Status.OPEN,
                subtype="overdue_promise",
                rule_or_critic_id=OVERDUE_RULE,
                logical_id=subject.logical_id,
                # Not `deterministic`, although the comparison is: the basis describes the
                # verdict's whole provenance, and the rows compared are a model's claims.
                # This is the second guard against blocking — even a severity edit could
                # not make this finding refuse, because `Finding.deterministic` is false.
                confidence_basis=lc.ConfidenceBasis.HEURISTIC.value,
                message=(
                    f"promise {promise.subject!r} opened at {promise.opened_at_key} was due "
                    f"by {promise.due_key}; the book is at {subject.story_order_key} and it "
                    "is still open"
                ),
                source={"claim": claim},
            )
        )
    return findings


#: Detectors that run inside the loop. The tuple is the extension point: a further
#: in-process check is appended here, and an out-of-process pack arrives through `standing`
#: instead.
#:
#: `detect_duplicate_scene` was the second, and the first that reads prose rather than
#: state. `detect_overdue_promises` is the third, and the first whose *inputs* are
#: model-sourced — which is why it is the first that may only annotate. All are checks no
#: sibling can run: one needs the candidate's extracted records beside canon, one needs the
#: rest of the book this system wrote, one needs the promise ledger only this store keeps.
IN_PROCESS: tuple[Any, ...] = (
    detect_contradictions,
    detect_cardinality_violations,
    detect_duplicate_scene,
    detect_overdue_promises,
)


def run_detectors(subject: DetectorInput) -> list[Finding]:
    return [finding for detector in IN_PROCESS for finding in detector(subject)]


def gate_integrity(
    subject: DetectorInput, *, standing: Sequence[Finding] = ()
) -> tuple[GateOutcome, list[Finding]]:
    """§4.2 ladder step 2. Returns the gate result and every finding that informed it.

    PLAN.md §4.2 numbers the ladder shape, integrity, craft, budget; this module and the
    handler said "step 3" for the integrity gate until 2026-09-03, counting from somewhere
    the plan does not.

    `standing` is what an evaluator already recorded against this node — ContinuityEvaluation's
    pack, ingested as an artifact — and is filtered to this node by the caller. Passing it in
    rather than querying makes the gate a pure function of its inputs, which is what lets the
    defect-injection suite plant a finding without a store.

    Findings that do not block are still **returned and recorded**. §4.2's decision record
    lists the gates that ran including the passing ones, and a minor finding dropped on the
    floor because it was not fatal is exactly the annotation §10.2 says to instrument from
    Book Zero onward.
    """
    findings = [*run_detectors(subject), *standing]
    blocking = [item for item in findings if item.blocks and item.deterministic]

    # §10.4 from the other end: a finding a model produced annotates until calibration
    # promotes it. Recorded as a detail so the decision says the critic *ran* — a gate whose
    # output vanishes when it disagrees is worse than one that never ran.
    advisory = [item for item in findings if item.blocks and not item.deterministic]

    # Findings below the blocking bar, named for the same reason the uncalibrated ones are:
    # §10.2 wants the annotations instrumented from Book Zero onward, and an overdue-promise
    # or zero-delta flag that only lived in the findings table would be invisible on the
    # decision an operator actually reads. Scoped to unresolved statuses so a dismissed
    # negative control does not re-announce itself on every later decision.
    annotations = [
        item
        for item in findings
        if not item.blocks and item.status in UNRESOLVED_STATUSES
    ]

    detail_parts: list[str] = []
    if blocking:
        detail_parts.append(
            "; ".join(
                f"{item.rule_or_critic_id or item.category} [{item.severity.value}] "
                f"{item.message}"
                for item in blocking
            )
        )
    if advisory:
        detail_parts.append(
            f"{len(advisory)} uncalibrated finding(s) recorded but not blocking (§10.4): "
            + ", ".join(sorted({item.rule_or_critic_id or item.category for item in advisory}))
        )
    if annotations:
        detail_parts.append(
            f"{len(annotations)} advisory finding(s) recorded, not blocking: "
            + ", ".join(
                sorted({item.rule_or_critic_id or item.category for item in annotations})
            )
        )
    if not findings:
        detail_parts.append(f"{len(IN_PROCESS)} detector(s) ran, nothing found")

    gate = GateOutcome(
        gate=GateKind.INTEGRITY,
        rule_or_critic_id=INTEGRITY_GATE,
        passed=not blocking,
        verdict_source=VerdictSource.DETERMINISTIC,
        blocking=True,
        vetoes=vetoes_for(blocking),
        detail="; ".join(part for part in detail_parts if part) or None,
    )
    return gate, findings


def gate_standing(findings: Sequence[Finding]) -> GateOutcome:
    """§4.2 ladder step 2, run *before* the generation, over findings already on record.

    Same filter as `gate_integrity` — status over severity, deterministic only — because a
    negative control must not block in front of the work either, and an uncalibrated critic
    that could not refuse a finished candidate must certainly not refuse an unstarted one.

    Returns a *passing* gate when there is nothing standing, so the decision record shows the
    check ran. A gate that only appears on failure cannot be distinguished from a gate that
    was never wired in, which is the question an audit asks first.
    """
    blocking = [item for item in findings if item.blocks and item.deterministic]
    detail = (
        "; ".join(
            f"{item.finding_id} {item.rule_or_critic_id or item.category} "
            f"[{item.severity.value}] {item.message}"
            for item in blocking
        )
        or None
    )
    return GateOutcome(
        gate=GateKind.INTEGRITY,
        rule_or_critic_id=STANDING_GATE,
        passed=not blocking,
        verdict_source=VerdictSource.DETERMINISTIC,
        blocking=True,
        vetoes=vetoes_for(blocking),
        detail=detail,
    )


def summarise(findings: Sequence[Finding]) -> str:
    """One line for an operator. Worst severity first, because that is what gets read."""
    if not findings:
        return "no findings"
    top = worst(findings)
    blocking = sum(1 for item in findings if item.blocks)
    return (
        f"{len(findings)} finding(s), {blocking} blocking, worst "
        f"{top.value if top else 'unknown'}"
    )


__all__ = [
    "CARDINALITY_RULE",
    "CONTRADICTION_RULE",
    "DUPLICATE_RULE",
    "DUPLICATE_SPAN_WORDS",
    "INTEGRITY_GATE",
    "IN_PROCESS",
    "MULTI_VALUED",
    "OVERDUE_RULE",
    "STANDING_GATE",
    "detect_cardinality_violations",
    "detect_contradictions",
    "detect_duplicate_scene",
    "detect_overdue_promises",
    "disagreement_key",
    "gate_integrity",
    "gate_standing",
    "in_force",
    "run_detectors",
    "summarise",
    "superseded",
]
