"""§12 step 5: reading state back out of accepted prose.

The gap this closes is structural rather than cosmetic. `domain/integrity.py` implements one
in-process detector, `state.contradiction.v0`, and its docstring names the corruption it
exists to catch: "§12 step 5's extraction writing a record that contradicts one already
accepted — can only happen inside the loop." That extraction did not exist. Records entered
the store only through `cli import`, `EventType.STATE_CANDIDATES_EXTRACTED` had no producer,
and **nothing anywhere in `src/` constructed a `StateRecord`** — so the detector could not
fire, and Stage 2's "repairs triggered by findings" had no in-process trigger to be built on.

**Extraction mints nothing, and that is the whole design.** Not the order key, not the
subject, not the value:

- The **order key** is read back out of the book's own imported evidence (`attested_position`)
  and abstains when the book has not answered. `domain/state.py` forbids deriving one, in
  terms worth repeating: `order_key` is opaque, its author chose it, and *nothing anywhere
  defines a mapping from a manuscript scene to one*. Measured, the obvious `f"s{ordinal}"`
  reproduces the litrpg fixture 19/19 and mis-slices the mystery 2 of 15 — it works on one of
  the two books in the project and fails the one whose genre (an analepsis: scene 5 is
  attested at `s1`) guarantees it. A scheme that is right on your test book and silently
  wrong on the next is worse than abstention.
- The **subject** must already name a subject some canon record uses. A new name is a fact
  about a character the store has never heard of, which is a proposal, not a reading.
- The **value** is the prose's, verbatim, never reconciled against canon. The litrpg fixture's
  scene 4 says `HP 34/30` because §8.3 planted `f-hp-over-max` there. An extractor that
  "corrected" it would erase the defect on the way in — the detector's own input, sanitised
  by its producer.

So the chain is **decision → prose → record**: a recorded policy decision accepted the prose,
and this is a mechanical restatement of that prose asserting nothing the decision did not.
That is why a record from here may carry `ACCEPTED_CANON` without violating §11's rule that
no proposal becomes canon merely because a model returned it — no model returned it. A model
leg would be a different question and is deliberately not built (see PLAN.md §17 Stage 1).

**Reach, stated plainly so a green Stage 1 is not read as more than it is.** This reads system
voice — the `[STATUS]` line LitRPG puts on the page — and nothing else. The mystery fixture
contains no such line and yields zero records; nothing here touches prose-semantic facts like
"Brandt knows about the letter", which need a model. What it does change is that the detector
goes from having no producer at all to one that runs on every accepted scene and demonstrably
fires.

**The generator is now asked for that line, and the gain is the gate rather than the
extraction.** `render_prompt` carries the book's own current status line
(`system_voice_example`) for any book whose canon already holds a snapshot. Before that, a
generated litrpg scene carried no game state at all, so `state.contradiction.v0` had nothing to
read and **every generated scene passed the integrity gate vacuously** — a scene claiming Rook
had forty gold where canon says forty-five was accepted, because it never said so on the page.
It says so now, and is refused. That is §8.3's fourth promotion clause and §17 Stage 1's
"validation on model-written rather than templated chapters", closed by making the prose speak
rather than by adding a detector.

**The instruction was measured against real models, and the first version failed one of
three.** Shown the line's own template with its `{subject}` slot intact, one local model wrote the
placeholder out verbatim — a line that matched the line's own pattern, named a subject canon has
never heard of, and extracted nothing. Showing the book's own line instead took it to three of
three. `tests/test_planner.py` keeps that measurement runnable; it is the only test in this
project that can check the instruction at all, because every other one runs on a provider that
ignores the prompt.

**What it is still not.** A redraft that *agrees* with canon extracts nothing new, because
`_already_canon` suppresses a fact the book has already accepted at that position — correct,
and it means the fixtures stay silent. And a book with no imported snapshot extracts nothing at
all, because `attested_position` has no evidence to read a position out of: Book Zero writes
system voice that nothing can yet place. Asking for the line is a precondition for that, not a
solution to it.

**Layout since 2026-09-03 (stage-0 §215).** This module kept what mints a record from prose
— `extract_state`, `extract_graph_facts`, `promotions`, record identity, and the position
readers `attested_position` and `stated_position` — and the rest moved, byte for byte, to
four modules below it: `domain/names.py` (what a subject is called), `domain/sheet.py` (the
sheet, the snapshot fold and the printed line), `domain/graphline.py` (the graph line's
declaration and grammar) and `domain/moves.py` (the move vocabulary and the example lines).
Every name is re-exported here, so `extraction.sheet_for` is still where a caller reads it,
and `docs/system-model.md` says which module is the home of which fact.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256

import litharness_contracts as lc

from litharness.domain import gamesystem as gamesystem_mod
from litharness.domain import state as state_mod
from litharness.domain import worlds as worlds_mod
from litharness.domain.events import payload_digest
from litharness.domain.graphline import (
    GRAPH_REGISTRY_VERSION,
    LABEL_CHARS,
    LABEL_WORDS,
    PHRASE_WORDS,
    GraphEdge,
    GraphLine,
    MalformedGraphLine,
    graph_line_fault,
    graph_line_for,
    parse_graph_line,
)
from litharness.domain.moves import (
    Movable,
    change_example,
    counted_names,
    gain_example,
    movable_names,
    movables,
    moved_to,
    moved_values,
    offered_choice,
    offered_line,
    progression_target,
    standing_example,
    standing_target,
)

# Two private readers that tests reach through this module (`tests/test_two_systems.py` reads
# `extraction._printing_system`, `tests/test_choice_points.py` reads `extraction._named_moves`);
# the redundant alias is the explicit re-export form, so an unused-import check leaves them.
from litharness.domain.moves import _named_moves as _named_moves
from litharness.domain.moves import _printing_system as _printing_system
from litharness.domain.names import display_name, humanise_subject, normalise_subject
from litharness.domain.sheet import (
    FIELD_KINDS,
    MAX_SUFFIX,
    SHEET_PREDICATE,
    STATUS_PREDICATE,
    MalformedSheet,
    Sheet,
    SheetField,
    _canon_of,
    _folds_into,
    _status_lines,
    declaration_from_snapshots,
    implied_sheet,
    impossible_fields,
    label_for,
    parse_sheet,
    render_status_line,
    sheet_for,
    sheet_from_line,
    sheet_from_value,
    snapshot_at,
    speaks_system_voice,
    state_as_it_stands,
    system_voice_example,
)
from litharness.domain.text import content_hash

#: Predicates that configure how a book is written down rather than stating anything about its
#: world. Canon, because the book declared them — and they must never reach a context packet.
#:
#: **Measured on the first reseeded rehearsal**: the sheet declaration arrived in the scene's
#: Established facts block as `silas status_sheet fields=[{'label': 'Loop', 'name': 'loop'}…]`,
#: which hands a writer a configuration blob and calls it a fact about the world. It is the
#: small instance of the general defect `plan/state-model-abilities.md` §2 names — a record
#: shaped for a machine, rendered into a prompt — and the general fix is a projection layer.
#: This is the narrow one: what configures the telling is not part of the told.
#: **§160's configuration predicates union in here rather than beside** (§161, and the ownership
#: was settled between the two tracks rather than assumed). Three consumers read this set —
#: `domain/context.py`, `application/model_context.py`, `domain/world_brief.py` — and all three
#: read it from this module, so a second set would be a second answer to "may this reach a
#: packet" and the two would eventually disagree about a record. A game system's magnitude scale
#: and its digest configure how a book is written down exactly as a sheet declaration does, so
#: they belong to the same one answer.
CONFIGURATION_PREDICATES = (
    frozenset({SHEET_PREDICATE, worlds_mod.GRAPH_LINE_PREDICATE})
    | gamesystem_mod.CONFIGURATION_PREDICATES
)

#: Named so a later registry change is a visible version bump rather than a silent reread.
#: Deliberately not the fixtures' `fixture.v1`: these records are this extractor's reading,
#: and borrowing the fixture's version would make them indistinguishable from authored ones.
REGISTRY_VERSION = "litharness.systemvoice.v0"
#: Declared on an **authored** record whose `story_position` is written in the planner's own
#: key namespace — the `s{n}` keys `beats_for` mints for this book — rather than in one
#: somebody else chose. It is a claim about where the key came from and nothing else: the
#: record is still given rather than read, and `cmd_state` still prints it as `given`.
#:
#: The namespace is not new and this is not the first thing to write in it. `Promise` already
#: stores `opened_at_key` "in `beats_for`'s padding", and the only reason that does not read
#: as a foreign vocabulary is that promises live in their own table — `PromiseRepository`
#: says so, naming `has_story_vocabulary`'s registry check as one of the three things folding
#: them into `StateRecord` would break. A seeded record dated at a beat is the same key with
#: nowhere to say so.
PLANNED_POSITION_VERSION = "litharness.planned-position.v0"
#: Registry versions whose order keys **this system's own planning** placed, and which are
#: therefore not evidence that the book has a story vocabulary of its own. See
#: `has_story_vocabulary`.
#:
#: **Two more members landed with the Architect, and both are the same case a third and fourth
#: time.** `GRAPH_REGISTRY_VERSION` is this module's own second family (the constant lives with
#: the line's grammar in `domain/graphline.py`), positioned at the key it
#: was handed. `worlds.REGISTRY_VERSION` is an Architect's proposal, and its only dated records
#: are the reveal positions the retired Forge minted **in `beats_for`'s own width, from the
#: book's own scene count** — that is what stage-0 §107.9.1 defect 10 was fixed to guarantee, and
#: it is exactly what makes them not somebody else's numbering. Left out, a forged world would
#: flip `has_story_vocabulary` to True on its own seed and §12 step 5 would extract nothing from
#: any scene, which is the silence measured for the seeded-interiority case arriving by a fourth
#: door. `test_an_architect_world_does_not_look_like_an_authors_vocabulary` pins it.
OWN_POSITION_VERSIONS = frozenset(
    {
        REGISTRY_VERSION,
        PLANNED_POSITION_VERSION,
        GRAPH_REGISTRY_VERSION,
        worlds_mod.REGISTRY_VERSION,
    }
)

def attested_position(records: Sequence[lc.StateRecord], logical_id: str) -> str | None:
    """The story position this scene is attested at, or None when the book has not said.

    Reads the answer out of the imported snapshot instead of computing it: a canon record
    whose evidence cites this scene is the book's own statement about where the scene sits in
    story time. Ambiguity abstains rather than picking — the mystery's scene 2 is cited by
    records at both `s1` and `s2`, and choosing either would be inventing the very mapping
    `domain/state.py` refuses to invent.

    **None means do not extract, never "extract unplaced".** `detect_contradictions` groups on
    `order_key_of(record) or ""`, so an unplaced record shares a bucket with every other
    unplaced record — the coarsest possible collision scheme wearing the costume of caution.
    """
    keys = {
        key
        for record in records
        if state_mod.is_canon(record) and (key := state_mod.order_key_of(record))
        if any(span.source.logical_id == logical_id for span in record.evidence)
    }
    return next(iter(keys)) if len(keys) == 1 else None

def has_story_vocabulary(known: Sequence[lc.StateRecord]) -> bool:
    """Whether this book already has story positions **somebody else** chose.

    One such canon record is enough: the vocabulary is that author's, its keys mean what they
    chose, and a position stated alongside them would be a second author writing in the same
    namespace. The mystery fixture is the case — scene 2 abstains while records at `s1` and
    `s2` exist, and filling that gap would insert a record into the middle of a numbering
    somebody else owns.

    **This extractor's own records are excluded, and leaving them in was a real defect** found
    by running Book Zero rather than by reasoning about it. Scene 1 was placed, its record
    became "a canon record with an order key", and every later scene therefore saw a book with
    a vocabulary and abstained — so a six-scene book extracted exactly one fact and looked, at
    every layer, like a book whose other five scenes established nothing. `REGISTRY_VERSION`
    is what tells the two apart, and it exists for precisely this: the module docstring
    records that it is deliberately not the fixtures' `fixture.v1`, so a record this extractor
    wrote is distinguishable from an authored one.

    **The exclusion is a set rather than that one version, and the second member was found the
    same way.** A seeded record dated at a beat — the interiority `plan/interiority-model.md`
    §1 asks for, `silas wants …` at `s1` — carries an order key in `beats_for`'s own
    namespace, which is not somebody else's numbering either. Measured on the Serial Pilot
    seed: adding one such record with no declaration flips this to True, `stated_position`
    then abstains for the whole book, and §12 step 5 extracts **nothing from any scene** —
    the same silence Book Zero produced, arriving by a different door. On the same seed and
    the same `Loop | Day` status line, `extract_state` returned 0 records with the declaration
    absent and 1 with it present.

    **The default direction is unchanged and is the safe one.** A dated canon record that
    declares nothing still counts as a foreign vocabulary, so forgetting the declaration
    loses coverage and can never mint a false order — the direction `BeatTemplate.chronological`
    defaults in, and for the same reason.
    """
    return any(
        state_mod.order_key_of(record)
        for record in known
        if state_mod.is_canon(record)
        and record.predicate_registry_version not in OWN_POSITION_VERSIONS
    )

def stated_position(known: Sequence[lc.StateRecord], stated: str | None) -> str | None:
    """A position the *planner* stated, usable only for a book with no vocabulary of its own.

    **This is the narrow opening in "extraction mints nothing", and the narrowness is the
    argument.** A book with no imported snapshot has no story-time vocabulary at all, so
    nothing here can conflict with an author's choices, contradict a record, or insert into
    a numbering somebody else owns — and the alternative is what the system had: a book it
    wrote entirely itself, whose every scene is unplaceable, so §12 step 5 extracts nothing
    from it forever. That is Book Zero.

    The claim is still not this module's. It comes from a `BeatTemplate` that declares itself
    chronological, which is a statement about the sheet the planner laid out rather than an
    inference about a book — see `domain/beats.py`, where the flag defaults to False so a
    template that forgets loses coverage instead of minting a false order.
    """
    if stated is None or has_story_vocabulary(known):
        return None
    return stated

def record_id_for(subject: str, predicate: str, order_key: str, value: Mapping[str, object]) -> str:
    """Content-derived, and **value-sensitive on purpose**.

    A replayed tick must converge rather than accumulate, so the id cannot carry the revision
    or the logical id. But keying on `(subject, predicate, order_key)` alone makes the
    detector permanently unreachable: `record_state_records` is `INSERT OR IGNORE`, so a
    contradicting record would collide with the one it contradicts, insert zero rows, leave
    the old value standing, and report success. Including the value means two disagreeing
    readings are two rows — which is exactly what the detector needs to see them.
    """
    material = payload_digest({"s": subject, "p": predicate, "k": order_key, "v": value})
    return f"rec-x{sha256(material.encode()).hexdigest()[:24]}"

def graph_record_id_for(subject: str, predicate: str, object_ref: str, order_key: str) -> str:
    """Content-derived, with the position in the material.

    `record_id_for` puts the *value* in so that two disagreeing readings are two rows the
    detector can see. An edge carries no value, so the equivalent question is different: the
    same edge re-established at a later position is what promotion is made of, and an id blind
    to the position would collapse the promoted canon row onto the proposal it promotes and
    `INSERT OR IGNORE` would keep the proposal.
    """
    material = payload_digest({"s": subject, "p": predicate, "o": object_ref, "k": order_key})
    return f"rec-g{sha256(material.encode()).hexdigest()[:24]}"

def _edge_key(record: lc.StateRecord) -> tuple[str, str, str]:
    return (record.subject, record.predicate, record.object_ref or "")

def extract_graph_facts(
    text: str,
    *,
    known: Sequence[lc.StateRecord],
    project_id: str,
    book_id: str,
    branch_id: str,
    logical_id: str,
    version_id: str,
    order_key: str,
) -> tuple[lc.StateRecord, ...]:
    """Graph edges read out of one scene's accepted prose, as **proposals**.

    The second extractor family (`plan/state-model-abilities.md` §5 item 9), and the one place
    this module is allowed to name something canon has never heard of.

    **Identity minting and factual promotion are separate decisions** (§6 item 1, and
    `research/progression-generalization.md` §14.3's three-way admission split). The page may
    *name* a new subject — that is what makes a graph that grows possible at all — and the claim
    it names arrives `PROPOSED`, so it reaches no context packet, takes no part in
    `detect_contradictions`, and launders nothing. `promotions` is the other half.

    Every record carries `GRAPH_REGISTRY_VERSION`, so a fact this family read is distinguishable
    from a status line's, from an author's snapshot, and from an Architect's proposal.

    **One edge is canon at the position, and the exception is the module docstring's own
    argument rather than a softening of the rule above.** A printed change of *standing* on a
    ladder this world declared is the book's own statement about a fact the world already
    holds — the same class as a `[STATUS]` line, whose records are `ACCEPTED_CANON` because *no
    model returned them*: a recorded policy decision accepted the prose, and this is a mechanical
    restatement of it. Nothing is minted. The subject must be one canon already uses, the rung
    must be a declared rank of a declared chain, and the criterion is derived from which chain
    holds the rung — so the three things `promotions` exists to guard against (a new name, a new
    claim, a fact the book never came back to) are all absent by construction.

    A rung the *page* minted is the general case and stays it: `[RANK] Kell now holds platinum`
    with no `platinum` on any chain arrives `PROPOSED` and is promoted only by later causal
    reuse, exactly as every other edge is.
    """
    line = graph_line_for(known)
    if line is None:
        return ()
    predicates = {edge.phrase: edge.predicate for edge in line.edges}
    # **A scheduled standing does not suppress the reading of the printed one.** `seen` exists
    # because repetition adds nothing, and it counts proposals as well as canon — but the
    # outline's own rung schedule is a `PROPOSED` `stands_at` edge at a future position, and
    # counting it here would mean the one scene that actually printed the rise read nothing,
    # because the plan for it was already on record. The plan and the page are different
    # claims: the schedule carries no registry version from this family, and the page's reading
    # is what makes the rise true.
    seen = {
        _edge_key(record)
        for record in known
        if not (
            record.predicate == worlds_mod.STANDS_AT_PREDICATE
            and record.authority is lc.StateAuthority.PROPOSED
            and record.predicate_registry_version != GRAPH_REGISTRY_VERSION
        )
    }
    canon_subjects = {record.subject for record in known if state_mod.is_canon(record)}
    declared_rungs = {
        rung
        for criterion in worlds_mod.criteria(_canon_of(known))
        for rung in worlds_mod.ladder_of(_canon_of(known), criterion)
    }

    extracted: list[lc.StateRecord] = []
    for match in line.pattern.finditer(text):
        predicate = predicates.get(match.group("phrase"))
        if predicate is None:  # pragma: no cover - the alternation cannot produce one
            continue
        subject = normalise_subject(match.group("subject"))
        target = normalise_subject(match.group("object"))
        if not subject or not target:
            continue
        key = (subject, predicate, target)
        # Repetition adds nothing. An edge already on record — proposal or canon — is the same
        # claim, and `plan/state-model-abilities.md` §6 item 1 rejects repetition as promotion
        # evidence explicitly, so writing a second proposal for it would be storing the evidence
        # the rule says is not evidence.
        if key in seen or key in {_edge_key(row) for row in extracted}:
            continue
        start, end = match.span()
        # The one canon-writable shape: a declared subject reaching a declared rung of a
        # declared chain. See the docstring — nothing is minted and no model returned it.
        stands = (
            predicate == worlds_mod.STANDS_AT_PREDICATE
            and subject in canon_subjects
            and target in declared_rungs
            and worlds_mod.criterion_of_rung(_canon_of(known), target) is not None
        )
        extracted.append(
            lc.StateRecord(
                record_id=graph_record_id_for(subject, predicate, target, order_key),
                kind=lc.StateRecordKind.RELATIONSHIP,
                subject=subject,
                predicate=predicate,
                object_ref=target,
                # The criterion rides on the edge so two ladders in
                # one world must not splice. Derived rather than printed — the page prints a
                # rung and a reader knows which ladder it is on.
                value=(worlds_mod.criterion_of_rung(_canon_of(known), target) if stands else None),
                story_position=lc.StoryPosition(order_key=order_key),
                authority=(
                    lc.StateAuthority.ACCEPTED_CANON if stands else lc.StateAuthority.PROPOSED
                ),
                pov_visibility=[],
                evidence=[
                    lc.EvidenceSpan(
                        source=lc.ResourceRef(
                            project_id=project_id,
                            book_id=book_id,
                            branch_id=branch_id,
                            logical_id=logical_id,
                            kind=lc.ResourceKind.MANUSCRIPT_SCENE,
                            version_id=version_id,
                        ),
                        start=start,
                        end=end,
                        content_sha256=content_hash(text[start:end]),
                    )
                ],
                predicate_registry_version=GRAPH_REGISTRY_VERSION,
                note=(
                    "read off the page: a declared subject at a declared rung of a declared "
                    "chain, which is the book stating a fact its world already holds"
                    if stands
                    else "named by the page; a proposal until the book uses it again"
                ),
            )
        )
    return tuple(extracted)

def promotions(
    known: Sequence[lc.StateRecord],
    extracted: Sequence[lc.StateRecord],
    *,
    order_key: str,
) -> tuple[lc.StateRecord, ...]:
    """Proposed edges this scene earned, as new canon records at this position.

    **The promotion rule, and it is deliberately the narrow one.**
    `plan/state-model-abilities.md` §6 item 1 rejects repetition as evidence and names *later
    causal reuse* as the strong signal: "an ability the book uses again to do something has
    earned more than one merely named twice." The checkable form of that, for a reader made of
    regexes, is: an earlier proposal `(s, p, o)` is promoted when **this** scene names `s` or
    `o` under a **different** predicate. The book came back to the thing and did something else
    with it.

    An identical repetition promotes nothing, by construction — `extract_graph_facts` never
    emits one, and the different-predicate test would refuse it anyway.

    **Promotion mints a new record rather than editing one**, because `record_state_records` is
    `INSERT OR IGNORE` and there is no update path — and because the new row is the truer
    statement: the proposal was made at s3 and the world accepted it at s7, and both of those
    happened. The proposal stays on record as the proposal it was.

    Honest about its reach: this cannot tell causal reuse from coincidental co-occurrence, and
    it does not claim to. What it buys is that a fact the page invented and then never touched
    again stays out of canon, which is the failure the rule exists to prevent.
    """
    if not extracted:
        return ()
    touched: dict[str, set[str]] = {}
    for record in extracted:
        for endpoint in (record.subject, record.object_ref or ""):
            if endpoint:
                touched.setdefault(endpoint, set()).add(record.predicate)

    promoted: list[lc.StateRecord] = []
    already = {_edge_key(record) for record in known if state_mod.is_canon(record)}
    for record in known:
        if record.authority is not lc.StateAuthority.PROPOSED:
            continue
        if record.predicate_registry_version != GRAPH_REGISTRY_VERSION:
            continue
        if not record.object_ref:
            continue
        earlier = state_mod.order_key_of(record)
        # **A proposal is promoted only from a position this scene can place** (§167). The old
        # test was `earlier >= order_key`, so a proposal keyed in the schedule space answered
        # `'0350' >= 's1'` with `False`, fell through the guard, and was minted as
        # `ACCEPTED_CANON` at scene one carrying the note `proposed at 0350` — a declaration
        # about the end of the book promoted into canon at the start of it. No store on disk
        # holds such a record today, so this reproduces nowhere and is fixed anyway: the guard
        # can only ever promote *fewer* edges than before, so it cannot invent a fact, and a
        # canon-minting path is the wrong place to leave a comparison that is wrong by spelling.
        if earlier is None or not state_mod.comparable(earlier, order_key):
            continue
        if earlier >= order_key:
            continue
        key = _edge_key(record)
        if key in already:
            continue
        reused = any(
            record.predicate not in touched.get(endpoint, set()) and endpoint in touched
            for endpoint in (record.subject, record.object_ref)
        )
        if not reused:
            continue
        already.add(key)
        promoted.append(
            lc.StateRecord(
                record_id=graph_record_id_for(
                    record.subject, record.predicate, record.object_ref, order_key
                ),
                kind=lc.StateRecordKind.RELATIONSHIP,
                subject=record.subject,
                predicate=record.predicate,
                object_ref=record.object_ref,
                story_position=lc.StoryPosition(order_key=order_key),
                authority=lc.StateAuthority.ACCEPTED_CANON,
                pov_visibility=list(record.pov_visibility),
                evidence=list(record.evidence),
                predicate_registry_version=GRAPH_REGISTRY_VERSION,
                note=f"promoted at {order_key}: the book used it again, proposed at {earlier}",
            )
        )
    return tuple(promoted)

def extract_state(
    text: str,
    *,
    known: Sequence[lc.StateRecord],
    project_id: str,
    book_id: str,
    branch_id: str,
    logical_id: str,
    version_id: str,
    replacing_logical_id: str | None = None,
    stated_order_key: str | None = None,
) -> tuple[lc.StateRecord, ...]:
    """State records read out of one scene's accepted prose.

    Pure: no store, no provider, no clock. `text` must be the **canonicalized** node content
    (`gate_draft` produces it), never the raw provider string — spans and `content_sha256`
    have to live in the NFC+LF coordinate space the contracts package resolves them in, and
    an offset measured against the raw text points at the wrong characters.

    Returns empty rather than raising on anything it cannot read. A scene with no system
    voice is the normal case, not an error.

    `stated_order_key` is a chronological template's answer for a book that has none of its
    own — see `stated_position`. **The book always wins:** an attested position is read first
    and a stated one is only consulted when the book is silent, so this can never override or
    interleave with an author's vocabulary.
    """
    order_key = attested_position(known, logical_id) or stated_position(known, stated_order_key)
    if order_key is None:
        return ()
    #: Recorded on every record whose position the planner supplied, because "the book said
    #: where this sits" and "the sheet we planned said so" are different provenance and an
    #: audit that could not tell them apart would be worth less than one that says nothing.
    minted = attested_position(known, logical_id) is None
    subjects = {record.subject for record in known if state_mod.is_canon(record)}
    # The book's own line, not this module's. A book that declared `Loop | Day` writes and is
    # read in `Loop | Day`; one that declared nothing gets exactly what it always got.
    # The book's own line: declared, implied by its snapshots, or taught by the first line
    # this scene prints (§205). A book with none of the three prints no status line and is
    # read for none; the graph line below is its own declaration and still runs.
    sheet = sheet_for(known)
    taught = sheet is None
    if taught:
        sheet = sheet_from_line(text)
    if sheet is None:
        return extract_graph_facts(
            text,
            known=known,
            project_id=project_id,
            book_id=book_id,
            branch_id=branch_id,
            logical_id=logical_id,
            version_id=version_id,
            order_key=order_key,
        )

    extracted: list[lc.StateRecord] = []
    # **Read tolerantly, so a projected line is a partial snapshot** (§203). The strict
    # `pattern` needs every column; a line printing only the held columns folds forward
    # onto the columns it left out, which is what `state_as_it_stands` already does.
    ids = {display_name(known, subject).casefold(): subject for subject in subjects}
    declared = False
    for read_subject, span in _status_lines(text):
        subject = normalise_subject(read_subject)
        # A name canon has never used is a claim about someone new, which is a proposal
        # rather than a reading of what the book already established.
        if subject not in subjects:
            continue
        # **Each line is read with its owner's columns** (§206): a place's line with the
        # place's sheet, the person's with the book's. A taught sheet is the book's.
        own = sheet if taught else (sheet_for(known, subject=subject) or sheet)
        found = own.read(text[span[0] : span[1]], ids=ids)
        if not found:
            continue
        read = found[0][1]
        # **The record is the whole state, the line is its projection.** A partial record at
        # a position where a fuller one stands reads as a contradiction to the integrity
        # detector (two values for one fact at one position), so the columns the line left
        # out are filled from the fold of this subject's own snapshots up to here, later
        # values winning: the writer's *carry these values forward unchanged* applied on this
        # side, and the same fold `state_as_it_stands` renders from.
        value = {**_folded_before(known, subject, order_key), **read}
        if taught and not declared:
            # **The first line an undeclared book prints is its declaration** (§205):
            # the columns in the order the page carries them, canon because the prose
            # was accepted, so every later scene is read against the book's own order
            # rather than the store's sorted keys.
            declared = True
            extracted.append(
                worlds_mod.world_record(
                    subject,
                    SHEET_PREDICATE,
                    value=sheet.declaration(),
                    authority=lc.StateAuthority.ACCEPTED_CANON,
                )
            )
        # Already established, identically, at this position: the record adds nothing, and
        # writing it anyway costs a permanent duplicate in every later context packet.
        if _already_canon(
            known,
            subject,
            order_key,
            value,
            replacing_logical_id=replacing_logical_id,
        ):
            continue
        start, end = span
        extracted.append(
            lc.StateRecord(
                record_id=record_id_for(subject, STATUS_PREDICATE, order_key, value),
                kind=lc.StateRecordKind.ASSERTION,
                subject=subject,
                predicate=STATUS_PREDICATE,
                value=value,
                story_position=lc.StoryPosition(order_key=order_key),
                authority=lc.StateAuthority.ACCEPTED_CANON,
                pov_visibility=[],
                evidence=[
                    lc.EvidenceSpan(
                        source=lc.ResourceRef(
                            project_id=project_id,
                            book_id=book_id,
                            branch_id=branch_id,
                            logical_id=logical_id,
                            kind=lc.ResourceKind.MANUSCRIPT_SCENE,
                            version_id=version_id,
                        ),
                        start=start,
                        end=end,
                        content_sha256=content_hash(text[start:end]),
                    )
                ],
                # No confidence. A regex match has no probability, and a fabricated 1.0 would
                # read downstream as a critic's score rather than as a parse.
                predicate_registry_version=REGISTRY_VERSION,
                note=(
                    f"story position {order_key} stated by the plan, not attested by the book"
                    if minted
                    else None
                ),
            )
        )
    # **The second family runs here rather than at both call sites.** `extract_state` is called
    # from the draft handler and the repair path, and a graph reader wired into one of them
    # would be a capability that works depending on which arm produced the scene. A book that
    # declares no graph line gets an empty tuple from both calls below, which is every book
    # written before this existed.
    graph = extract_graph_facts(
        text,
        known=known,
        project_id=project_id,
        book_id=book_id,
        branch_id=branch_id,
        logical_id=logical_id,
        version_id=version_id,
        order_key=order_key,
    )
    return (*extracted, *graph, *promotions(known, graph, order_key=order_key))

def _folded_before(
    known: Sequence[lc.StateRecord], subject: str, order_key: str
) -> dict[str, object]:
    """This subject's state as it stands at `order_key`, folded forward from its own canon
    snapshots (later values winning), for a projected line to be completed from (§203).

    The fold is `state_as_it_stands`'s, applied to a named subject: only canon, only this
    subject, only positions that fold into this one.
    """
    history = sorted(
        (
            record
            for record in known
            if record.predicate == STATUS_PREDICATE
            and state_mod.is_canon(record)
            and record.subject == subject
            and isinstance(record.value, Mapping)
            and _folds_into(state_mod.order_key_of(record), order_key)
        ),
        key=lambda record: state_mod.order_key_of(record) or "",
    )
    values: dict[str, object] = {}
    for record in history:
        assert isinstance(record.value, Mapping)
        values.update(record.value)
    return values

def _already_canon(
    known: Sequence[lc.StateRecord],
    subject: str,
    order_key: str,
    value: Mapping[str, object],
    *,
    replacing_logical_id: str | None = None,
) -> bool:
    return any(
        record.subject == subject
        and record.predicate == STATUS_PREDICATE
        and state_mod.order_key_of(record) == order_key
        and record.value == value
        for record in known
        if state_mod.is_canon(record)
        and not (
            replacing_logical_id is not None
            and any(span.source.logical_id == replacing_logical_id for span in record.evidence)
        )
    )


__all__ = [
    "CONFIGURATION_PREDICATES",
    "FIELD_KINDS",
    "GRAPH_REGISTRY_VERSION",
    "LABEL_CHARS",
    "LABEL_WORDS",
    "MAX_SUFFIX",
    "OWN_POSITION_VERSIONS",
    "PHRASE_WORDS",
    "PLANNED_POSITION_VERSION",
    "REGISTRY_VERSION",
    "SHEET_PREDICATE",
    "STATUS_PREDICATE",
    "GraphEdge",
    "GraphLine",
    "MalformedGraphLine",
    "MalformedSheet",
    "Movable",
    "Sheet",
    "SheetField",
    "attested_position",
    "change_example",
    "counted_names",
    "declaration_from_snapshots",
    "display_name",
    "extract_graph_facts",
    "extract_state",
    "gain_example",
    "graph_line_fault",
    "graph_line_for",
    "graph_record_id_for",
    "has_story_vocabulary",
    "humanise_subject",
    "implied_sheet",
    "impossible_fields",
    "label_for",
    "movable_names",
    "movables",
    "moved_to",
    "moved_values",
    "normalise_subject",
    "offered_choice",
    "offered_line",
    "parse_graph_line",
    "parse_sheet",
    "progression_target",
    "promotions",
    "record_id_for",
    "render_status_line",
    "sheet_for",
    "sheet_from_line",
    "sheet_from_value",
    "snapshot_at",
    "speaks_system_voice",
    "standing_example",
    "standing_target",
    "state_as_it_stands",
    "stated_position",
    "system_voice_example",
]
