"""What a scene may be asked to move or print: the move vocabulary and the example lines.

Split out of `domain/extraction.py` on 2026-09-03 (stage-0 §215) with every definition
byte-identical, and re-exported from there. `movables` is the one source of beat vocabulary
and `movable_names`, `moved_values` and `moved_to` are its projections; `offered_choice` and
`offered_line` are the fork; `progression_target`, `standing_target`, `standing_example`,
`change_example` and `gain_example` are the lines a writer is shown, filled with the book's
own words. Everything here reads canon and mints none of the book's vocabulary: a name comes
from the sheet, the system or the graph line the world declared, a number from the arithmetic
that would record the move, a position from the records; deriving any of them here would be
this module deriving the one kind of thing the extractor is most careful not to
(`extraction`'s module docstring).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import litharness_contracts as lc

from litharness.domain import gamesystem as gamesystem_mod
from litharness.domain import house as house_mod
from litharness.domain import state as state_mod
from litharness.domain import worlds as worlds_mod
from litharness.domain.graphline import graph_line_for
from litharness.domain.names import display_name
from litharness.domain.sheet import (
    MAX_SUFFIX,
    SHEET_PREDICATE,
    STATUS_PREDICATE,
    _canon_of,
    _folded_before,
    readable,
    render_status_line,
    sheet_for,
    snapshot_at,
    state_as_it_stands,
)


def progression_target(records: Sequence[lc.StateRecord], *, at: str | None = None) -> str | None:
    """The next milestone a progression schedule asks this book to reach, or None.

    **The defect this addresses is that the ledger never moves.** Measured over a 24-scene
    Book Zero and a six-scene one before it: every scene reported the seed values unchanged,
    so the book had no economy, no progression and no stakes. Nothing objected, because each
    scene agreed with canon at its own position and the contradiction detector asks only
    that. §17 Stage 3 names a "progression schedule" as Narrative Planner v0 work; this reads
    one.

    **A schedule is a state record that is not canon**, which is the shape the system already
    has and the reason this needs no new storage, no contract field and no prose to parse. A
    milestone is a claim about what the state *should become* at a future story position —
    `PROPOSED` says exactly that, `is_canon` excludes it, and so the context packet does not
    hand it to a scene as an established fact and `detect_contradictions` does not weigh it
    against what the prose says. It informs generation and contaminates nothing.

    Returns the **nearest milestone at or after** `at`, so a book aims at its next target
    rather than its last one. Never interpolates between milestones: a level curve's shape is
    a modelling choice the author made when they wrote the schedule, and inventing points on
    it here would be this module deriving the one kind of thing it is most careful not to.
    """
    milestones = [
        record
        for record in records
        if record.predicate == STATUS_PREDICATE
        and not state_mod.is_canon(record)
        and isinstance(record.value, Mapping)
        and state_mod.order_key_of(record) is not None
    ]
    ahead = [
        record
        for record in milestones
        if at is None or (state_mod.order_key_of(record) or "") >= at
    ]
    if not ahead:
        return None
    target = min(ahead, key=lambda record: state_mod.order_key_of(record) or "")
    return render_status_line(target.subject, target.value, records=records)


def standing_target(records: Sequence[lc.StateRecord], *, at: str | None = None) -> str | None:
    """The next rung a standing schedule asks this book to reach, as one line of facts. Or None.

    **`progression_target`'s twin, and every one of that function's arguments applies here.**
    A scheduled standing is a `PROPOSED` `stands_at` edge, so `is_canon` excludes it, the
    context packet never hands it to a scene as established fact, and `detect_contradictions`
    never weighs it against what the prose says. It informs generation and contaminates nothing.

    Returns the **nearest scheduled standing at or after** `at`, so a book aims at its next rung
    rather than its last one, and never interpolates: which scene a rise lands at is the
    schedule's choice and inventing one between two milestones would be this module deriving the
    thing it is most careful not to.

    The line carries the *live* rung as well as the scheduled one, and both with their number,
    because the number is the whole point of the ladder and a target with no origin is a
    destination with no distance. Where the live standing is unknown — a book being drafted from
    a schedule whose opening standing is not canon — the line says only where the plan has them.

    **Facts and positions, no verb about the rise.** Whether the rung is earned, felt, or
    celebrated is not said here and is not said anywhere in this package
    (`plan/stage-0-decisions.md` §113).
    """
    scheduled = [
        record
        for record in records
        if record.predicate == worlds_mod.STANDS_AT_PREDICATE
        and record.object_ref
        and not state_mod.is_canon(record)
        and state_mod.order_key_of(record) is not None
    ]
    ahead = [
        record for record in scheduled if at is None or (state_mod.order_key_of(record) or "") >= at
    ]
    if not ahead:
        return None
    target = min(ahead, key=lambda record: state_mod.order_key_of(record) or "")
    criterion = str(target.value or "").strip() or worlds_mod.criterion_of_rung(
        records, target.object_ref or ""
    )
    if not criterion:
        return None
    chain = worlds_mod.ladder_of(records, criterion)
    if not chain or target.object_ref not in chain:
        return None
    total = len(chain)
    aimed = chain.index(target.object_ref or "") + 1
    forms = {
        record.subject: str(record.value or "").strip()
        for record in records
        if record.predicate == worlds_mod.MANIFESTS_PREDICATE
    }
    here = worlds_mod.standing_of(records, target.subject, at=at).get(criterion)
    ahead_of = f"{target.object_ref} ({aimed} of {total})"
    aimed_form = forms.get(target.object_ref or "")
    if here is None or here not in chain:
        plan = f"the book's plan has {target.subject} at {ahead_of}"
        return f"{plan}: {aimed_form}" if aimed_form else plan
    now = chain.index(here) + 1
    line = (
        f"{target.subject} stands at {here} ({now} of {total})"
        f"{': ' + forms[here] if forms.get(here) else ''}; "
        f"the book's plan has them at {ahead_of}"
    )
    return f"{line}: {aimed_form}" if aimed_form else line


def standing_example(records: Sequence[lc.StateRecord], *, at: str | None = None) -> str | None:
    """One graph line, filled with this book's own words and its live rung, or `None`.

    **`system_voice_example` for the second extractor family, and it exists for that
    function's measured reason.** Shown a template with a `{subject}` slot intact, a model
    wrote the placeholder out verbatim: the line matched the pattern, named a subject canon has
    never heard of, and extraction yielded nothing — a scene that looks right, parses right, and
    establishes nothing. So what a generator is shown is a *filled* line, never a form with
    braces in it, and the fill comes from records rather than from anything this module invents.

    `None` for a book that declares no graph line, whose declaration carries no phrase meaning
    "stands at", or whose protagonist stands nowhere countable. Each is a book the chain
    *declare → ask → print → read* never starts on, which is a legitimate state and the control
    every fixture in this project sits in.
    """
    line = graph_line_for(records)
    if line is None:
        return None
    phrase = next(
        (edge.phrase for edge in line.edges if edge.predicate == worlds_mod.STANDS_AT_PREDICATE),
        None,
    )
    if phrase is None:
        return None
    subjects = worlds_mod.entities_with_role(_canon_of(records), "protagonist")
    if not subjects:
        return None
    standing = worlds_mod.standing_of(records, subjects[0], at=at)
    if len(standing) != 1:
        return None
    [(_, rung)] = standing.items()
    return line.render(subjects[0], phrase, rung)


def change_example(
    records: Sequence[lc.StateRecord], *, character: str | None, at: str | None
) -> str | None:
    """The line the book prints where a declared change lands on this person, or `None`.

    **The ask for a change of kind** (§212): a change declared at a scene position, with an
    effect on a grant of the system this person stands in, and not yet printed — no canon
    snapshot at or after it — is shown to that scene as the line after it, rendered off the
    sheet `sheet_of` already folds the change into. `None` where no system prints the line,
    where nothing stands declared here, and where the book has already printed a state at or
    past the change; a change in the scheduled key space (`0350`) never lands in a scene,
    which is §165's rule for every scheduled record and is not changed here.
    """
    if character is None or at is None:
        return None
    standing = _standing_sheet(records, character=character, at=at)
    if standing is None:
        return None
    system, sheet = standing
    printed = snapshot_at(records, at=at)
    last = state_mod.order_key_of(printed) if printed is not None else None
    pending = [
        change
        for change in gamesystem_mod.changes_of(_canon_of(records), character, system=system)
        if change.at is not None
        and state_mod.comparable(change.at, at)
        and change.at <= at
        and (last is None or (state_mod.comparable(last, change.at) and last < change.at))
    ]
    if not pending:
        return None
    return render_status_line(
        character, sheet.snapshot(), sheet=sheet_for(records), records=records
    )


def gain_example(
    records: Sequence[lc.StateRecord], *, at: str | None = None, ability_id: str
) -> str | None:
    """The graph line filled for a grant gained: the protagonist, the book's phrase for
    `can_do`, and the grant, all in the names the book prints (§208). `None` for a book
    whose line declares no such phrase, that has no protagonist, or that declares no
    such grant.

    `standing_example`'s twin for the second thing the genre prints a line for. The
    market's notices (*you have learned*, *skill gained*) run at half a line per
    thousand words in its early chapters (the system-displays census), and until now
    a book could declare the phrase and never be asked to print it. The reader reads
    it back as a proposed `can_do` edge (`extract_graph_facts`), which the sheet's own
    record of the gain already makes canon, so the line is furniture the reader
    watches and never the record of truth.
    """
    line = graph_line_for(records)
    if line is None:
        return None
    phrase = next(
        (edge.phrase for edge in line.edges if edge.predicate == worlds_mod.CAN_DO),
        None,
    )
    if phrase is None:
        return None
    canon = _canon_of(records)
    subjects = worlds_mod.entities_with_role(canon, "protagonist")
    if not subjects or ability_id not in {record.subject for record in canon}:
        return None
    del at  # The line names no position; the gain is the scene's.
    return line.render(
        display_name(records, subjects[0]), phrase, display_name(records, ability_id)
    )


def notice_lines(
    records: Sequence[lc.StateRecord], *, character: str | None, at: str | None
) -> tuple[str, ...]:
    """The lines the System prints where a declared change lands on this person at this
    scene, in the book's own bracket (§218).

    **The gap the fit census ranked first** (`research/quality-measurement/system-fit/`,
    §217): four market stories in five print a bracketed line for something other than a
    gain or a rise — the System speaking, a welcome, a warning, a quest given, a title, a
    zone entered — and this house printed a line for a gain (§208) and a line for a rise
    (§113) and nothing else. The declared shape already existed: a `change` node with a
    `manifests_as` line, which the Architect has written as story beats since the research
    ontology (§212 found eight stores holding them). What was missing was the ask.

    A change keyed at `at` (a scene key; a scheduled key never lands, §165), with a
    `participant` edge to `character` and a `manifests_as` line, renders as `[LABEL] line`
    under the label of the book's graph line, in id order. `()` where the book declares no
    graph line (its System is quiet, §208's rule), where nothing is keyed here, and for a
    change with no participant or no line — which is every change the stored books hold, so
    every prompt drafted before this is the prompt it was. No default phrase and no default
    bracket: the words and the tag are the book's own.
    """
    if character is None or at is None:
        return ()
    line = graph_line_for(records)
    if line is None:
        return ()
    canon = _canon_of(records)
    anchors = sorted(
        record.subject
        for record in canon
        if record.predicate == worlds_mod.TYPE_PREDICATE
        and str(record.value or "").strip() == worlds_mod.CHANGE
        and state_mod.order_key_of(record) == at
    )
    found: list[str] = []
    for change_id in anchors:
        rows = [record for record in canon if record.subject == change_id]
        if not any(
            record.predicate == worlds_mod.PARTICIPANT_ROLE and record.object_ref == character
            for record in rows
        ):
            continue
        said = next(
            (
                record.value.strip()
                for record in rows
                if record.predicate == worlds_mod.MANIFESTS_PREDICATE
                and isinstance(record.value, str)
                and record.value.strip()
            ),
            None,
        )
        if said is None:
            continue
        found.append(f"[{line.label}] {said}")
    return tuple(found)


def readout_lines(
    records: Sequence[lc.StateRecord],
    *,
    plan: str | None,
    at: str | None,
    protagonist: str | None,
) -> tuple[str, ...]:
    """Another owner's line, where the scene's plan names the owner (§220).

    **§209's owed item, and the fit census's fourth gap** (§217): twenty-three of sixty market
    stories print another subject's sheet where the protagonist reads it — a creature's level
    and health, an appraisal of a rival, a follower's standing — and since §206 every such
    sheet is declarable and none was ever asked for. The ask needs a trigger that is the
    book's and not a model's (§61(5)): the scene's plan names who is in it, so an owner named
    in the plan is an owner whose line the scene prints, once, where the protagonist reads it.

    An owner is a subject named by a canon `status_sheet`'s `owner`, or every subject of the
    role it names; the protagonist is never a readout (their line is the status line). The
    owner's state is folded at `at` from their own canon snapshots (`_folded_before`), and
    rendered through their own sheet. `()` for a scene with no plan text or no position, and
    for every book whose plans name no owner, which is every book on disk.
    """
    if not plan or at is None:
        return ()
    known = readable(records)
    canon = _canon_of(known)
    roles = worlds_mod.entity_roles(canon)
    owners: set[str] = set()
    for record in canon:
        if record.predicate != SHEET_PREDICATE or not isinstance(record.value, Mapping):
            continue
        owner = record.value.get("owner")
        if not isinstance(owner, str) or not owner.strip():
            continue
        owner = owner.strip()
        if owner in worlds_mod.ENTITY_ROLES:
            owners.update(subject for subject, held in roles.items() if owner in held)
        else:
            owners.add(owner)
    text = plan.casefold()
    found: list[str] = []
    for subject in sorted(owners):
        if subject == protagonist:
            continue
        name = display_name(known, subject).casefold()
        if not re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", text):
            continue
        value = _folded_before(known, subject, at)
        if not value:
            continue
        found.append(render_status_line(subject, value, records=known))
    return tuple(found)


@dataclass(frozen=True, slots=True)
class Movable:
    """One quantity a scheduled beat may name, and the snapshot key that quantity moves.

    **The pair exists because the beat and the check read the same answer from two ends.** The
    plan carries the `name` — the book's own word, which is the whole of §161.4's argument for
    naming a quantity rather than a category — and the only thing that can afterwards say
    whether it moved is the `key` it occupies in the `status_snapshot` this book prints. A
    function returning names alone forces whoever verifies the ask to map a label back onto a
    column by its own rule, and a second mapping is a second answer to "which number is this".

    The mapping is never invented here. In the legacy arm the pair is a `SheetField`'s own
    `(label, name)`; in the system arm it is a `gamesystem.Column`'s `(label, name)`, except
    for a rise, which is named by the rung it reaches and moves `gamesystem.RANK_KEY` — the one
    place the two differ, and it differs because a rank has a name of its own while the column
    carrying it does not.
    """

    name: str
    key: str


def counted_names(records: Sequence[lc.StateRecord], *, at: str | None = None) -> tuple[str, ...]:
    """The names this book's own system counts by, in the order its sheet prints them.

    **This is the book's vocabulary, read off canon, and this module mints none of it.** The
    labels come from the sheet the book declared (or, for a book that declared none, from the
    default line `extraction` shipped with, retired since §205), filtered to the fields the book's
    *current* snapshot actually holds a value for. A book whose sheet declares a column it never
    fills does not get that column named, because a beat naming a quantity the writer cannot see on
    the line handed to it is a beat asking for a number out of nowhere.

    **Empty is the control and it is the common case for everything written before a sheet
    existed.** A book that speaks no system voice returns `()`, and every caller composes the
    unnamed form it composed before this function existed.

    **`MACHINERY_WORDS` are dropped, and the reason is `genre.BEAT`'s own** (§155.3): this
    vocabulary is composed into a scene plan, the scene plan reaches the writer, and §120
    measured `standing` reaching a chapter as prose when repo vocabulary got that far. A label
    is book data rather than house text, so no ceiling test covers it; the filter is where the
    guarantee has to live. A book whose every label collides falls back to the unnamed form,
    which is the correct failure — the schedule still fires and names nothing.
    """
    return tuple(item.name for item in _counted(records, at=at))


def _counted(records: Sequence[lc.StateRecord], *, at: str | None = None) -> tuple[Movable, ...]:
    """`counted_names` with the column each name moves still attached. See `Movable`."""
    standing = state_as_it_stands(records, at=at)
    if standing is None:
        return ()
    held = set(standing[1])
    sheet = sheet_for(records)
    if sheet is None:
        return ()
    return tuple(
        Movable(field_.label, field_.name)
        for field_ in sheet.fields
        if field_.numeric
        and field_.name in held
        and field_.label.casefold() not in house_mod.MACHINERY_WORDS
    )


def movable_names(
    records: Sequence[lc.StateRecord], *, character: str | None = None, at: str | None = None
) -> tuple[str, ...]:
    """What the scheduled progression beat may name as moving here, in declaration order.

    **The one source of beat vocabulary, and it has two arms with no mode flag** — the
    recognition ratchet is the mode, which is the shape Track 1's game system and §158's
    status-snapshot recognition already share. Every caller asks this one question; nothing
    downstream branches on what kind of book it got.

    *The legacy arm*, live and below: a book with no game system is named by the columns its
    own status line prints (`counted_names`). It is a superset — a label is a quantity that
    exists, which is not the same claim as a quantity that may move next — and a superset is
    the right error for a book whose system was never modelled, because the alternative for
    such a book is the categorical `genre.BEAT` and read 8 §4.2 measured what a category buys.

    *The system arm*, where this book declares exactly one system and the character stands
    somewhere in it: `gamesystem.legal_moves` over that sheet, named in the declaration order
    that accessor already returns them in. It is strictly better and not merely different —
    it knows an ability whose prerequisite is unmet is **not** offered, which a label cannot
    know, so it stops the schedule naming a move the book cannot make. It ranks nothing and
    this function must not make it rank anything (§61(5)): declaration order is the book's own
    order, and `genre.beat_text` rotates through it by schedule position for that reason.

    **An empty answer from the system arm is an answer**, not a reason to fall through. A sheet
    with no legal move left is a character who cannot advance, and naming a column they hold
    would tell the scene something moves when the system says nothing can. The fall-through is
    for the cases where the system arm *cannot answer at all* — no system declared, more than
    one, or no canon position for this character.

    Two systems is an abstention rather than a choice, on `sheet_for`'s own precedent: two
    declarations are a disagreement about the book's own vocabulary, and picking either would
    be this module deciding which of the author's answers is real. Such a book falls to the
    legacy arm, which is a description of what it prints rather than a claim about what it
    can do.

    **Canon only**, which is `genre._declared_systems`' rule for `genre`'s reason: `systems_of`
    deliberately reads proposals too, because the Architect builds a system before `world
    accept` and a reader that saw nothing until acceptance would report an empty world
    mid-build. A beat is not that reader — a proposed system is a plan for later, and
    scheduling a scene around one would put an unaccepted draw on the page.

    **The names alone**, because a plan carries words. `movables` is the same answer with the
    column each name moves still attached, and it is the one this function projects — so the
    quantity a beat asks for and the number a later check reads cannot come apart.
    """
    return tuple(item.name for item in movables(records, character=character, at=at))


def movables(
    records: Sequence[lc.StateRecord], *, character: str | None = None, at: str | None = None
) -> tuple[Movable, ...]:
    """`movable_names` with the column each name moves still attached. See `Movable`.

    Every rule, arm and abstention is `movable_names`' own and is documented there; this holds
    the body because the pair is the fuller answer and the names are a projection of it. Kept
    as one function for the reason that docstring gives for having one source of beat
    vocabulary at all: a second reader of "what may move here" is a second answer to it.
    """
    standing = _standing_sheet(records, character=character, at=at)
    if standing is not None:
        system, sheet = standing
        return _named_moves(system, gamesystem_mod.legal_moves(sheet))
    return _counted(records, at=at)


def _standing_sheet(
    records: Sequence[lc.StateRecord], *, character: str | None = None, at: str | None = None
) -> tuple[gamesystem_mod.SystemDef, gamesystem_mod.CharacterSheet] | None:
    """The one system this book declares and this character's position in it — or `None`.

    **The arm selection, factored, so two readers of it cannot become two answers.** This is
    the condition `movables` documents in full: exactly one declared system, its columns the
    columns this book actually prints, and a canon position for this character in it. `None` is
    the fall-through to the legacy arm and is the ordinary case for every book whose world
    declared no system.

    Extracted when `moved_to` needed the same three facts to say what a move would leave. A
    second copy of the condition would have let the vocabulary a beat is composed from and the
    number that beat's example prints come from different arms of the same question — which is
    the pairing `Movable` exists to hold together, one step further along.
    """
    if character is None:
        return None
    canon = [record for record in records if state_mod.is_canon(record)]
    system = _printing_system(canon, records)
    if system is None:
        return None
    sheet = gamesystem_mod.sheet_of(canon, character, system=system, at=at)
    return None if sheet is None else (system, sheet)


def moved_to(
    records: Sequence[lc.StateRecord],
    movable: Movable,
    *,
    character: str | None = None,
    at: str | None = None,
) -> int | None:
    """What `movable`'s column reads once the move that offered it has been made — or `None`.

    **The third projection of one question**, beside `movables` and `movable_names`: which
    quantities may move here, which column each one occupies, and what that column reads
    afterwards. All three read the same arm, so the word a beat carries, the number a gate
    checks and the number an example prints cannot come apart.

    *The system arm* answers by taking the move. `gamesystem.advance` is called on the sheet
    this character stands at and the value is read off `Advancement.after` — **the same
    arithmetic that would record the advancement if the book took it**, rather than an
    increment reproduced here. A system that ever declares a different step is therefore
    authoritative for free, and there is no second place to update.

    *The legacy arm* has no system to ask, so the answer is one step: a sheet declares columns
    and, where it pairs them, a ceiling, and it declares no step size. One is the smallest
    change an integer column can make, and the smallest change is the honest reading of a beat
    whose whole sentence is *moves here*. **It is not a magnitude anything is held to**: the
    gate this feeds refuses only a column that did not move at all (§184), so a scene whose
    events warrant more is refused by nothing.

    **`None` where the column has no room**, and that is the one case this refuses to answer
    rather than guessing at. A paired column standing at its own ceiling — `Warmth 6/6` — has
    no next value that is not `impossible_fields`' own defect, and rendering `Warmth 7/6` into
    a prompt as the state a scene leaves would ask the writer for a line the book may not
    print. The system arm needs no such guard because `legal_moves` already withholds a deepen
    at the scale's maximum and a rise at the top rung: there, having been offered is the proof
    that there is room.
    """
    changed = moved_values(records, movable, character=character, at=at)
    if changed is None:
        return None
    after = changed.get(movable.key)
    return after if isinstance(after, int) and not isinstance(after, bool) else None


def moved_values(
    records: Sequence[lc.StateRecord],
    movable: Movable,
    *,
    character: str | None = None,
    at: str | None = None,
) -> Mapping[str, int] | None:
    """Every column the move that offered `movable` leaves changed, with what each then reads.

    **`moved_to` for the whole line** (§210). A move that is paid in a stock the rungs hand
    out changes two columns, and a rise that hands one out changes two; the writer copies the
    line it is shown, so the line has to carry every number the move changes and not the one
    the beat named. The named column is still the one the ask states and the gate checks. The
    arms, the abstentions and the ceiling are `moved_to`'s, which reads its answer off this.
    """
    standing = _standing_sheet(records, character=character, at=at)
    if standing is not None and at is not None:
        system, sheet = standing
        for move in gamesystem_mod.legal_moves(sheet):
            if _named_moves(system, (move,)) != (movable,):
                continue
            try:
                advanced = gamesystem_mod.advance(sheet, move, at=at)
            except gamesystem_mod.IllegalAdvance:
                # `legal_moves` offered it, so this is unreachable rather than tolerated —
                # caught because composing a prompt is not the place to discover that the two
                # disagree, and a book that hits it draws the entering line it drew before.
                return None
            return {
                key: value
                for key, value in advanced.after.items()
                if value != advanced.before.get(key)
                and isinstance(value, int)
                and not isinstance(value, bool)
            }
        return None
    folded = state_as_it_stands(records, at=at)
    if folded is None:
        return None
    was = folded[1].get(movable.key)
    if not isinstance(was, int) or isinstance(was, bool):
        return None
    ceiling = folded[1].get(f"{movable.key}{MAX_SUFFIX}")
    if isinstance(ceiling, int) and not isinstance(ceiling, bool) and was + 1 > ceiling:
        return None
    return {movable.key: was + 1}


def _printing_system(
    canon: Sequence[lc.StateRecord], records: Sequence[lc.StateRecord]
) -> gamesystem_mod.SystemDef | None:
    """The one declared system whose columns are the line this book prints, or `None`.

    **Two systems, one at a time** (§197). Until the concept stage a book's canon declared one
    system or none, and every arm here asked for exactly one. A book whose person comes under a
    second system after a turn declares two, and the one they stand in is the one whose columns
    the printed line has — `_system_prints_the_line`'s own test, applied to each. That is a fact
    about the book's line and not a preference among candidates (§61(5)); two systems that both
    print it are two answers, and the arms abstain as they always did.
    """
    printing = [
        system
        for system in gamesystem_mod.systems_of(canon)
        if _system_prints_the_line(system, records)
    ]
    return printing[0] if len(printing) == 1 else None


def _system_prints_the_line(
    system: gamesystem_mod.SystemDef, records: Sequence[lc.StateRecord]
) -> bool:
    """Whether the declared system's columns are the columns this book actually prints.

    **The system arm may only name what the writer can see** (§165). `counted_names` filters the
    legacy arm to the fields the current snapshot fills, for the stated reason that a beat naming
    a quantity absent from the line handed to the writer is a beat asking for a number out of
    nowhere. The system arm had no matching guard because, until a drawn system could exist
    beside a hand-declared sheet, the two could not disagree.

    Serial Pilot 15 is the book where they do: its seed declared a sheet of `rung`, `reach`,
    `carried` and `standing` **and** a system whose columns are the rung plus six capability ids,
    and completing the system (`gamesystem.completion_records`) would otherwise have switched its
    beats to naming abilities its status line does not print. `system_gap` reports exactly that
    disagreement, so this guard and that gap close together: the beats come from the system
    precisely when the book is a position in it.
    """
    # **The system's columns among the printed ones, not the whole of them** (§219): a line
    # that prints a pool or a currency beside the grants still prints the grants, and the
    # beats come from the system precisely when the line carries its columns.
    sheet = sheet_for(records)
    return sheet is not None and set(system.value_keys) <= {field_.name for field_ in sheet.fields}


def _named_moves(
    system: gamesystem_mod.SystemDef, moves: Sequence[gamesystem_mod.Move]
) -> tuple[Movable, ...]:
    """One name per available move, in the order they were offered, with the column it moves.

    A `RISE` is named by the rung it reaches and everything else by the ability that moves,
    which is the name the system itself declared — nothing here mints a word. **The column is
    the ability's own** (`SystemDef.columns` prints one per ability, keyed by `ability_id`),
    and a rise moves `RANK_KEY`, because the rung it reaches is a name and the rung column is
    the one number carrying it. `MACHINERY_WORDS`
    are dropped for `counted_names`' reason: this vocabulary reaches the writer inside a scene
    plan and therefore shapes prose a reader reads, and a declared name is book data that no
    ceiling test can cover.

    **A `CHOOSE` is dropped, and it is the one move this function refuses to name.** The
    progression beat's sentence is that a named quantity *moves*, and taking a fork moves no
    number — `gamesystem.choose` records the pick and changes not one column, because what a fork
    changes is which gains become legal. Naming a fork here would tell the scene something moved
    when nothing did, which is §161.4's own defect (a beat satisfied by the wrong thing) arriving
    through the other door. A fork belongs to `genre.interaction_text`, on its own schedule.
    """
    abilities = {ability.ability_id: ability.name for ability in system.abilities}
    ranks = {rank.rank_id: rank.name for rank in system.ranks}
    named: list[Movable] = []
    for move in moves:
        if move.kind is gamesystem_mod.AdvanceKind.CHOOSE:
            continue
        if move.kind is gamesystem_mod.AdvanceKind.RISE:
            name, key = ranks.get(move.rank_id or ""), gamesystem_mod.RANK_KEY
        else:
            name, key = abilities.get(move.ability_id or ""), move.ability_id or ""
        if name and key and name.casefold() not in house_mod.MACHINERY_WORDS:
            named.append(Movable(name, key))
    return tuple(named)


def offered_choice(
    records: Sequence[lc.StateRecord], *, character: str | None = None, at: str | None = None
) -> tuple[str, tuple[str, ...]] | None:
    """The fork standing open in front of this character here, in the book's own words.

    Returns `(the fork's name, the names of its ways)`, or `None` where no fork stands open —
    which is every book on disk today, every book whose world declares no system, and every
    position before the rung a fork opens at. `genre.interaction_text` is the caller and `None`
    is what makes its beat take the reading form or none at all.

    **Every guard here is `movable_names`' guard, deliberately, because the two answer one
    question about one book and a second set of rules would be a second answer.** Canon only,
    because a proposed system is a plan for later and scheduling a scene around one would put an
    unaccepted draw on the page. One declared system printing the line (`_printing_system`):
    a book may declare two (§197), and the one whose columns the printed line has is the one
    the person stands in, which is a fact about the book and not a choice between the
    author's answers; two that both print it are two answers and abstain.
    `_system_prints_the_line`, because a fork whose abilities are not columns of the line the
    writer was handed is a fork the reader cannot watch resolve.

    **The first fork in declaration order, and no ordering of any other kind** (§61(5)).
    Declaration order is the book's own order; nothing here asks which fork is the interesting
    one, and `gamesystem.pending_choices` is explicit that it ranks nothing.

    **A name colliding with `house.MACHINERY_WORDS` abstains the whole fork rather than dropping
    one way.** `counted_names` drops the offending label because its list is a rotation and a
    short rotation still works; a fork named with one of its ways missing is a menu that lies
    about what is on offer. The correct failure is the beat falling back to the reading form,
    which is what `None` here produces.

    **The position gate is the sheet's, and it cannot leak a schedule** (§165, §167).
    `gamesystem.sheet_of` applies `state.comparable` before its cutoff, so a `chose` or a
    `stands_at` written in the schedule space is canon, readable and never read as already
    reached; and a fork opens off the rung the sheet carries rather than off any story position,
    which is §110's rule that intent is not an event.
    """
    if character is None:
        return None
    canon = [record for record in records if state_mod.is_canon(record)]
    system = _printing_system(canon, records)
    if system is None:
        return None
    sheet = gamesystem_mod.sheet_of(canon, character, system=system, at=at)
    if sheet is None:
        return None
    pending = gamesystem_mod.pending_choices(sheet)
    if not pending:
        return None
    choice = pending[0]
    # The ways this person is offered (§207), not every way the fork has.
    options = gamesystem_mod.offered_options(sheet, choice)
    names = (choice.name, *(option.name for option in options))
    if any(not name.strip() or name.casefold() in house_mod.MACHINERY_WORDS for name in names):
        return None
    return choice.name, tuple(option.name for option in options)


def offered_line(
    records: Sequence[lc.StateRecord], *, character: str | None = None, at: str | None = None
) -> str | None:
    """The `[OFFER]` line the book prints for the fork standing open here, or `None`.

    Every guard is `offered_choice`'s, by calling it: a fork that function abstains on is a
    fork this line does not print. What this adds is only the rendering, `gamesystem.offer_line`,
    so the writer is handed the fork as furniture rather than as a sentence about a fork — the
    operator's read-10 item was a system that only reports, and a fork the reader cannot see
    the ways of is a fork the reader cannot want one of.
    """
    if offered_choice(records, character=character, at=at) is None or character is None:
        return None
    canon = [record for record in records if state_mod.is_canon(record)]
    system = _printing_system(canon, records)
    if system is None:
        return None
    sheet = gamesystem_mod.sheet_of(canon, character, system=system, at=at)
    if sheet is None:
        return None
    pending = gamesystem_mod.pending_choices(sheet)
    if not pending:
        return None
    return gamesystem_mod.offer_line(system, pending[0], sheet=sheet)
