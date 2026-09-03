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
A rejection carries no explanation back into generation, and a gate that wrote its complaint
into the next attempt would be a channel from a check to a prompt that nothing licenses.
**§97.1 is the wrong citation for that and this module used to make it** (§186): that rule
governs the operator's own diagnostics and the reader channel — a *human* read, and the
`debug-book` verbs — and a deterministic comparison of two stored integers is neither. What
holds the door is the retry's own classification: `RETRYABLE` earns bounded attempts because
asking again is asking for the thing the prompt already asked for, and a retry told what the
check found is no longer that. The correction is recorded rather than acted on, because the
question the retry existed to answer is now asked in the first prompt.

**Which is the other half of this module** (§186). `moved_example` composes what the furniture
ask hands a writer on a scheduled scene: the line the book prints *after* the named quantity
has moved, rather than the line it printed entering. The two halves are here together on
purpose — every abstention in the composer is an abstention in the gate, read off the same
records in the same order, so the scene that is shown a moved line is exactly the scene whose
state gets checked, and neither can drift into asking for what the other does not check.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import litharness_contracts as lc

from litharness.domain import extraction as extraction_mod
from litharness.domain import genre as genre_mod
from litharness.domain import state as state_mod
from litharness.domain.patch import Veto
from litharness.domain.policy import GateKind, GateOutcome, VerdictSource

#: The gate's own id, in the ladder's `<kind>.<what>.v0` form.
PROGRESSION_GATE = "integrity.progression.v0"


@dataclass(frozen=True, slots=True)
class MovedLine:
    """The status line a scene leaves once the quantity its beat named has moved.

    `line` is the exact string to print — §154's addressable token, rendered by
    `extraction.render_status_line` from the book's own sheet, its own spelling of the name and
    its own numbers, with one column changed and every other column the one the writer was
    already being shown. `name` is the book's word for what moved and `was` is what that column
    read entering the scene, both of which the ask states in words so the line is legible as a
    move rather than as a restatement.
    """

    line: str
    name: str
    was: int
    now: int


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


def moved_example(
    records: Sequence[lc.StateRecord],
    target: extraction_mod.Movable | None,
    *,
    character: str | None = None,
    at: str | None = None,
) -> MovedLine | None:
    """The line to show a writer whose beat names a move — or `None`, meaning show the old one.

    **This is the defect §184 measured, closed at the surface that caused it.** The furniture
    ask hands the writer one concrete artifact and calls it *the state as it stands*, and §169
    measured what a model does with a filled example: it copies it character for character —
    that is why the example is filled rather than a template, and it is the behaviour the whole
    ask depends on. So on a scheduled scene the prompt asked for a move in the plan and handed
    over a line proving the numbers had not moved, and the one thing in the prompt that could
    be copied carried the entering values. Pilot 18 draw 3 spent two attempts on it: the beat
    read *Rating moves here*, the example read `Rating 2`, both drafts printed `Rating 2`, and
    the gate refused both. The ask and the check disagreed and the writer obeyed the concrete
    half.

    **What the writer is handed is the line after the move, and nothing else changes.** One
    number differs from the line an unscheduled scene would have been shown; the subject, the
    sheet, the labels and every other column are the same string. Two lines in one prompt was
    the alternative and it was refused: §161.3's cardinality is load-bearing — `extract_state`
    mints one canon record per match at one order key, so a scene printing two lines writes the
    exact shape `integrity.detect_contradictions` groups on — and a prompt holding two
    printable lines, shown to a model measured to copy them verbatim, is how that gets printed.
    One artifact in, one line out.

    **Every abstention here is the gate's own, and that is the point rather than a coincidence.**
    Where this returns `None` the writer sees the entering line exactly as before, byte for
    byte:

    - no position to place a state at (`at is None`);
    - no line standing at that position to read a number off;
    - **canon already states this subject's state at `at`** — §184.4's abstention, and the one
      that would otherwise turn this into an outage. An imported book holds a snapshot at every
      position, so the numbers such a scene is shown are the ones its own author stated for it;
      asking that scene to print different ones would mint a second snapshot at one key and be
      refused by the contradiction detector. Both golden fixtures are that book;
    - the named column reads no integer on the line standing there;
    - the column has no room to move (`extraction.moved_to`'s ceiling).

    The first four are `gate_progression`'s list read in the same order against the same
    records, and `test_the_prompt_abstains_wherever_the_gate_abstains` holds the pairing on the
    one that matters. The fifth is this function's alone and is a **named residual**: the gate
    still fires on a beat naming a column at its own ceiling, so such a scene is asked for a
    move, shown the unmoved line, and refused. Closing it means the beat vocabulary declining
    to name a maxed column, which re-rotates `beat_text` for every scheduled scene on the shelf
    — a second finding, and not this one's to land.
    """
    if target is None or at is None:
        return None
    standing = extraction_mod.snapshot_at(records, at=at)
    if standing is None or not isinstance(standing.value, Mapping):
        return None
    if state_mod.order_key_of(standing) == at:
        return None
    folded = extraction_mod.state_as_it_stands(records, at=at)
    if folded is None:
        return None
    subject, values = folded
    was = values.get(target.key)
    if not isinstance(was, int) or isinstance(was, bool):
        return None
    # **Every column the move changes is shown moved** (§210): a rise that hands out a
    # stock and a deepen that is paid in one each leave two numbers different, and the
    # writer copies the line, so the line carries both. `name`, `was` and `now` stay the
    # named column's, which is the one the ask states and the gate checks.
    changed = extraction_mod.moved_values(records, target, character=character, at=at)
    now = None if changed is None else changed.get(target.key)
    if changed is None or now is None or now == was:
        return None
    return MovedLine(
        line=extraction_mod.render_status_line(
            subject,
            {**values, **changed},
            sheet=extraction_mod.sheet_for(records),
            records=records,
        ),
        name=target.name,
        was=was,
        now=now,
    )


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


__all__ = [
    "PROGRESSION_GATE",
    "MovedLine",
    "gate_progression",
    "moved_example",
    "named_target",
]
