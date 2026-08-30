"""Whether a scheduled progression beat landed: the ask, recorded, and the state, compared.

**The gap this closes, third sighting of its class.** §155.3 put a progression beat on a
schedule, §157 made the schedule reach every book length, §161.4 made the beat name the
book's own quantity rather than a category, and §170 made it name the protagonist's. Every
one of those aims the ask. **Nothing anywhere asked whether the ask was met.** The beat rides
the prompt, `extraction.extract_state` reads a snapshot off the drafted prose, and the gate
ladder in `application/handlers.py` never put the two beside each other — so a scene could be
told *cold seal moves here* and come back with cold seal at the value it started on, and pass
every gate that ran.

Measured before this existed, over the pilot shelf (`plan/stage-0-decisions.md` §184): seven
scheduled beats have ever been drafted, six of them naming a quantity, and three of those six
left the named column where it stood. Two of the three had already been named by a human read
— serial pilot 16 filed one as a residual it owed, serial pilot 18 filed the other as the
failure that commissioned this — and the third had been named by nobody.

**The whole check is a comparison of two integers**, and that is what makes it a gate rather
than a critic. No model is asked anything; no proxy is read; no threshold is crossed. The two
integers are the one the packet showed the writer and the one the scene's own extracted state
holds afterwards, and `VerdictSource.DETERMINISTIC` is the literal truth about where the
verdict comes from rather than a label chosen for it.

**Any change, and never a direction.** The beat's sentence is *"{name} moves here"*. A gate
requiring the number to rise would be enforcing something the writer was never told, and a
gate requiring a magnitude would be a bar — which §61's four attainability checks would then
have to be run for, over a distribution that does not exist. Moved is the whole contract.

**Nothing this gate says reaches the writer.** A refusal is recorded on the policy decision
and read by an operator; the prompt is frozen at enqueue and the retry re-sends it unchanged.
That is §97.1's rule, not an omission: a rejection carries no explanation back into
generation, and a gate that wrote its complaint into the next attempt would be the feedback
channel the `debug-book` rule exists to keep shut.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import litharness_contracts as lc

from litharness.domain import extraction as extraction_mod
from litharness.domain import genre as genre_mod
from litharness.domain import state as state_mod
from litharness.domain.patch import Veto
from litharness.domain.policy import GateKind, GateOutcome, VerdictSource

#: The gate's own id, in the ladder's `<kind>.<what>.v0` form.
PROGRESSION_GATE = "integrity.progression.v0"


def named_target(
    plan: str,
    records: Sequence[lc.StateRecord],
    *,
    character: str | None = None,
    at: str | None = None,
) -> extraction_mod.Movable | None:
    """What this scene's composed plan named as moving, and the column it moves — or `None`.

    **Answered where the plan is composed, never where the draft comes back.** The name is
    read out of the plan text itself (`genre.beat_name_in`) and the column comes from the same
    function that supplied the vocabulary the beat was built from (`extraction.movables`), read
    against the records as they stood when the work was selected. `application/planner.py`
    calls this and puts both halves on the job payload, beside `story_order_key`, which travels
    there for the identical reason: *"the position a scene was extracted under is the one the
    plan held when the work was selected"*. A handler that re-derived either half would be
    checking today's answer against yesterday's ask.

    `None` where the plan named no quantity — every case `beat_name_in` documents — and also
    where the name is one this book's vocabulary no longer offers here. The second is an
    abstention rather than a guess: the mapping from a word to a column belongs to the arm that
    minted the word, and a fall-back mapping invented here would be the second answer `Movable`
    exists to prevent.
    """
    name = genre_mod.beat_name_in(plan)
    if name is None:
        return None
    offered = extraction_mod.movables(records, character=character, at=at)
    return next((item for item in offered if item.name == name), None)


def gate_progression(
    name: str | None,
    column: str | None,
    *,
    before: Sequence[lc.StateRecord],
    extracted: Sequence[lc.StateRecord],
    at: str | None = None,
) -> GateOutcome | None:
    """§4.2's ladder, one rung further: did the quantity the plan named actually move?

    `name` and `column` are the halves `named_target` recorded at selection time, off the job
    payload. `before` is the book's canon as the packet was built from it and `extracted` is
    what `extraction.extract_state` read out of this candidate — the same two values the
    integrity gate is handed one line above, so this costs no store read of its own.

    **Returns `None` where there is nothing to check**, and the handler then appends no gate
    row at all. That is a departure from `gate_standing`'s rule of returning a passing gate so
    an audit can tell "ran and found nothing" from "never wired", and it is a departure for a
    stated reason: whether a beat was scheduled here is already on the record independently,
    since `beat_ordinals` is a pure function of the ordinal and the total and both sit in
    `selected_by`. A row saying *no beat fired* would restate a fact the dossier already
    carries. Where a beat **did** name a quantity, the row is written whether it passed or
    failed, which is the half of `gate_standing`'s argument that does bind.

    **Abstentions pass and are said out loud.** A book whose line does not print the named
    column, and a scene with no position to place its state at, are cases where this gate has
    nothing to compare — not cases where the scene did the wrong thing. Each carries its reason
    in `detail`, so an abstention is legible as one rather than as a silent success.
    """
    if not name or not column:
        return None
    if at is None:
        return _outcome(
            True, f"{name} was named as moving here; this scene has no position to place a "
            "state at, so nothing it wrote down can be compared"
        )
    standing = extraction_mod.snapshot_at(before, at=at)
    if standing is None or not isinstance(standing.value, Mapping):
        return _outcome(
            True, f"{name} was named as moving here; no line stands at {at} to read it off"
        )
    if state_mod.order_key_of(standing) == at:
        # **A position the book already wrote down is not one this scene moves anything at**,
        # and this abstention is the difference between a gate and an outage. An imported book
        # arrives holding a snapshot for every position at once — both golden fixtures do —
        # and `application/planner.py` records what such a record means where it selects it:
        # *"a status snapshot is the value entering its keyed scene"*. So the numbers the
        # writer is shown at `at` are the numbers its own author stated for `at`, and there is
        # no delta for a scene to produce: writing different ones would mint a second canon
        # snapshot at one key, which is exactly the shape `integrity.detect_contradictions`
        # groups on and refuses. Refusing here as well would leave such a book unable to pass
        # either gate — move the number and it contradicts, leave it and it stalls.
        #
        # A book being written rather than imported has no record at its own position until
        # it drafts one: it carries the un-keyed opening state, and `stands_at`-space records
        # the Architect scheduled are in another key space and unreachable from here (§165).
        # Which is every serial pilot, and every book this gate was commissioned for.
        return _outcome(
            True,
            f"{name} was named as moving here; canon already states {standing.subject}'s "
            f"state at {at}, so this scene is not the record of it",
        )
    was = standing.value.get(column)
    if not isinstance(was, int) or isinstance(was, bool):
        return _outcome(
            True,
            f"{name} was named as moving here; the line standing at {at} prints no "
            f"{column} column",
        )
    now = _asserted(extracted, subject=standing.subject, at=at, column=column)
    if now is None:
        return _outcome(
            False,
            f"{name} was named as moving here; this scene wrote down no state for "
            f"{standing.subject} at {at}, and {column} stands at {was}",
        )
    if now == was:
        return _outcome(
            False,
            f"{name} was named as moving here; {column} reads {was} at {at} before and after",
        )
    return _outcome(True, f"{name} moved: {column} {was} to {now} at {at}")


def _asserted(
    extracted: Sequence[lc.StateRecord], *, subject: str, at: str, column: str
) -> int | None:
    """What this scene's own extracted state says the column reads, or `None` where it is silent.

    **Read off `extracted` rather than off the two sides of `snapshot_at`**, and the reason is a
    tie. A book whose seed sits at the drafted scene's own key would put the opening snapshot
    and the extracted one at one order key, where `snapshot_at`'s `max` returns whichever the
    caller listed first — so "the state after" would silently be the state before. Reading the
    assertion directly has no tie to lose: this scene either wrote a snapshot down at its own
    position or it did not.

    Silence is not the same fact as an unchanged number, and the caller keeps them apart in the
    refusal it writes. It is the same verdict either way, because `extraction._already_canon`
    drops a snapshot identical to one canon already holds at this position — so a scene that
    prints the line with every number unchanged is a scene that asserts nothing new, and both
    roads lead to a column that did not move.
    """
    for record in extracted:
        if record.predicate != extraction_mod.STATUS_PREDICATE:
            continue
        if record.subject != subject or not state_mod.is_canon(record):
            continue
        if state_mod.order_key_of(record) != at:
            continue
        if not isinstance(record.value, Mapping):
            continue
        value = record.value.get(column)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def _outcome(passed: bool, detail: str) -> GateOutcome:
    """One `GateOutcome` shape, so a pass and a refusal cannot drift in how they are recorded.

    `GateKind.INTEGRITY` because the question is about the book's state rather than about the
    string — the same line `handlers` draws when it puts the integrity gate behind the shape
    one. `VerdictSource.DETERMINISTIC` and `blocking=True` are the whole of the §138 licence:
    every deterministic gate on the drafting ladder blocks, and the gates that only annotate
    here are the ones whose verdict comes from a model or from a mechanism nothing has
    qualified. This one's verdict is arithmetic over two stored integers.
    """
    return GateOutcome(
        gate=GateKind.INTEGRITY,
        rule_or_critic_id=PROGRESSION_GATE,
        passed=passed,
        verdict_source=VerdictSource.DETERMINISTIC,
        blocking=True,
        vetoes=() if passed else (Veto.PROGRESSION_UNMOVED,),
        detail=detail,
    )


__all__ = ["PROGRESSION_GATE", "gate_progression", "named_target"]
