"""Stage-0 §184: whether a scheduled progression beat landed, as a gate.

The defect this file pins is that there was no check at all. §155.3 scheduled a progression
beat, §157 made the schedule reach every book length, §161.4 made it name the book's own
quantity, §170 made it name the protagonist's — and nothing anywhere compared the ask against
the state the scene wrote down. Serial pilot 18's chapter 1 was told *cold seal moves here*,
staged the ability's first use, printed `cold seal 2` on both sides of the scene, and passed
the whole ladder; serial pilot 16 filed the same shape as a residual it owed.

Five things are asserted, and they fail for five different reasons.

**The comparison itself.** `test_a_scene_that_does_not_move_the_named_quantity_is_refused` is
the located defect, and `test_a_scene_that_moves_the_named_quantity_is_accepted` is the half
that has to keep working — three of the seven beats ever drafted did move their number, and a
gate that refused those would refuse the shelf.

**The three ways a scene can fail to say it moved**, which are one verdict and three refusal
sentences: the number is the same, the scene wrote nothing down, or it wrote somebody else's
line down. `extraction._already_canon` is why the first two are one fact.

**The abstention that keeps this a gate rather than an outage.**
`test_a_position_the_book_already_wrote_down_is_not_one_this_scene_moves` is the case running
the suite found: an imported book states a snapshot at every position, so a scene there has no
delta to produce and moving the number would mint the contradiction the integrity gate refuses.

**What the gate may never fire on.** Every scene whose plan asked for no move — unscheduled,
categorical, an interaction beat, an offer beat over a fork. §173 dropped `CHOOSE` from the
beat's vocabulary precisely because a fork moves no number, and a gate that then refused a
scene for not moving one would be that defect arriving through a third door.

**Where the ask is recorded.** `test_the_ask_is_recorded_where_it_is_composed` holds the
planner's half: both halves of the beat travel on the job payload beside `story_order_key`,
for that key's own stated reason, so nothing is re-derived after the draft comes back.

No model reads, ranks or judges anything here, and no bar is declared: every assertion is an
equality between two integers or an identity of a recorded string.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable

import litharness_contracts as lc

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.planner import make_plan_selector
from litharness.domain import gamesystem, genre, worlds
from litharness.domain.draft import DraftPolicy
from litharness.domain.extraction import (
    STATUS_PREDICATE,
    Movable,
    movable_names,
    movables,
)
from litharness.domain.jobs import Job
from litharness.domain.patch import Veto
from litharness.domain.policy import (
    PARKABLE,
    RETRYABLE,
    GateKind,
    Outcome,
    PolicyDecision,
    VerdictSource,
    decide,
    decision_id_for,
)
from litharness.domain.progression import (
    PROGRESSION_GATE,
    gate_progression,
    named_target,
)
from litharness.domain.revision import new_book
from litharness.domain.staging import with_bound

# --------------------------------------------------------------------------- the fixtures
#
# Serial pilot 18b's own shape, at the smallest draw `check_draw` accepts: a rung ladder and
# five abilities, a protagonist standing on the first rung holding two of them at 2, and one
# ability gated behind a third point of another. `cold seal` is the quantity the located beat
# named and `hold a room` is the one it cannot reach, which is what §161.4 credits the system
# arm with knowing that a column label cannot.


def _system(**overrides: object) -> gamesystem.SystemDef:
    base: dict[str, object] = {
        "system_id": "the_board",
        "name": "the board",
        "criterion": "yard_ticket",
        "rank_label": "Ticket",
        "ranks": (
            gamesystem.Rank("rung_hand", "hand"),
            gamesystem.Rank("rung_fitter", "fitter"),
            gamesystem.Rank("rung_shaper", "shaper"),
        ),
        "abilities": (
            gamesystem.Ability("cold_seal", "cold seal"),
            gamesystem.Ability("read_the_grain", "read the grain"),
            gamesystem.Ability(
                "hold_a_room", "hold a room", needs=(gamesystem.Need("cold_seal", 3),)
            ),
            gamesystem.Ability("stand_the_frame", "stand the frame"),
            gamesystem.Ability("call_the_plate", "call the plate"),
        ),
        "scale": gamesystem.Scale("the board", 5),
    }
    base.update(overrides)
    return gamesystem.SystemDef(**base)  # type: ignore[arg-type]


def _canonical(records: Iterable[lc.StateRecord]) -> list[lc.StateRecord]:
    """`records_for` mints proposals; a beat reads canon only (§161.4). This is `world accept`
    reduced to the one thing these assertions need from it."""
    return [
        dataclasses.replace(record, authority=lc.StateAuthority.ACCEPTED_CANON)
        for record in records
    ]


def _snapshot(
    subject: str, value: dict[str, object], *, order_key: str | None = None
) -> lc.StateRecord:
    """One printed line, at a position or as the opening state."""
    return worlds.world_record(
        subject,
        STATUS_PREDICATE,
        value=value,
        order_key=order_key,
        authority=lc.StateAuthority.ACCEPTED_CANON,
    )


def _sheet_of(system: gamesystem.SystemDef) -> gamesystem.CharacterSheet:
    return gamesystem.CharacterSheet(
        system=system,
        character="ines_barrow",
        rank_id="rung_hand",
        magnitudes=tuple(
            (
                ability.ability_id,
                2 if ability.ability_id in {"cold_seal", "read_the_grain"} else 0,
            )
            for ability in system.abilities
        ),
    )


def _canon(system: gamesystem.SystemDef | None = None) -> list[lc.StateRecord]:
    """The book as it stood entering scene 1: a declared system, its own sheet, a protagonist
    standing on the first rung holding two of its five abilities, and the opening line —
    which `records_for_sheet` writes beside the edges, because they are one fact.
    """
    system = system or _system()
    return [
        *_canonical(gamesystem.records_for(system)),
        *_canonical(gamesystem.records_for_sheet(_sheet_of(system))),
        worlds.world_record(
            "ines_barrow",
            worlds.ENTITY_ROLE_PREDICATE,
            value="protagonist",
            authority=lc.StateAuthority.ACCEPTED_CANON,
        ),
    ]


def _standing(system: gamesystem.SystemDef | None = None) -> dict[str, int]:
    """The numbers the opening line prints, which is what the packet shows the writer."""
    return _sheet_of(system or _system()).snapshot()


def _plan(name: str) -> str:
    """One scheduled scene's composed plan, through the two functions that compose it."""
    return with_bound(genre.with_beat("", 1, 6, counts=(name,)), 1)


def _selected(path, *, drafted: int) -> Job:  # type: ignore[no-untyped-def]
    """The job the live drafting selector picks on a six-scene book with `drafted` scenes done.

    A fresh six-scene book rather than a golden fixture, for `tests/test_staging.py`'s reason:
    six distinct dramatic functions means `needs_outline` never holds, which is the shape every
    pilot runs in and the one where a beat is derived rather than stored.
    """
    store = SqliteStore.open(path)
    try:
        revision = new_book("book-ask", "main", title="The Ask", scenes=6)
        store.commit_revision(revision, created_at="2026-08-13T00:00:00Z")
        if drafted:
            store.commit_revision(
                revision.replacing(
                    node.with_content("Drafted scene. " * 40)
                    for node in revision.nodes
                    if node.logical_id in {f"scene-{index}" for index in range(1, drafted + 1)}
                ),
                created_at="2026-08-13T01:00:00Z",
            )
        store.record_state_records(
            revision.book_id,
            revision.branch_id,
            _canon(),
            created_at="2026-08-13T00:00:00Z",
            source_revision_id=revision.revision_id,
        )
        store.record_plan_items(
            revision.book_id,
            revision.branch_id,
            (
                lc.PlanItem(
                    logical_id="plan-premise",
                    kind=lc.PlanKind.PREMISE,
                    text="A fitter reads a station's grain and finds it grading her back.",
                    authority=lc.PlanAuthority.INTENDED,
                    locked=True,
                ),
            ),
            created_at="2026-08-13T00:00:00Z",
            source_revision_id=revision.revision_id,
        )
        job = make_plan_selector(outline=True, policy=DraftPolicy())(
            store, "worker", 1_770_000_000.0, 300.0
        )
        assert job is not None, f"no work selected with {drafted} scene(s) drafted"
        return job
    finally:
        store.close()


# --------------------------------------------------------------------------- the comparison


def test_a_scene_that_does_not_move_the_named_quantity_is_refused() -> None:
    """Serial pilot 18b chapter 1, scene 1, as the gate sees it.

    The stored line reads *"This scene: cold seal moves here, and the person it belongs to is
    there when it does"*; the drafted scene staged the ability's first use and printed
    `cold seal 2` at both ends. Every gate that ran passed. This is the one that does not.
    """
    before = _canon()
    target = named_target(_plan("cold seal"), before, character="ines_barrow", at="s1")
    assert target == Movable("cold seal", "cold_seal")

    extracted = [_snapshot("ines_barrow", _standing(), order_key="s1")]
    gate = gate_progression(
        target.name, target.key, before=before, extracted=extracted, at="s1"
    )

    assert gate is not None
    assert gate.passed is False
    assert gate.vetoes == (Veto.PROGRESSION_UNMOVED,)
    assert gate.detail == (
        "cold seal was named as moving here; cold_seal reads 2 at s1 before and after"
    )


def test_a_scene_that_moves_the_named_quantity_is_accepted() -> None:
    """The half that has to keep working. Three of the seven beats ever drafted moved their
    number, and any deepen or rise satisfies this — the beat's sentence says *moves*, so the
    gate asks for a change and never for a direction or a size."""
    before = _canon()
    extracted = [_snapshot("ines_barrow", {**_standing(), "cold_seal": 3}, order_key="s1")]

    gate = gate_progression(
        "cold seal", "cold_seal", before=before, extracted=extracted, at="s1"
    )

    assert gate is not None
    assert gate.passed is True
    assert gate.vetoes == ()
    assert gate.detail == "cold seal moved: cold_seal 2 to 3 at s1"


def test_the_gate_asks_for_a_change_and_never_for_a_direction() -> None:
    """A number that falls is a number that moved. Requiring it to rise would enforce
    something the writer was never told — the beat says *moves here* — and requiring a size
    would be a bar, which §61's four attainability checks would then have to be run for over a
    distribution of number-moves that does not exist."""
    before = _canon()
    fell = [_snapshot("ines_barrow", {**_standing(), "cold_seal": 1}, order_key="s1")]

    gate = gate_progression("cold seal", "cold_seal", before=before, extracted=fell, at="s1")

    assert gate is not None and gate.passed is True


def test_a_position_the_book_already_wrote_down_is_not_one_this_scene_moves() -> None:
    """The abstention that keeps this a gate rather than an outage, found by running the suite.

    An imported book arrives holding a snapshot for every story position at once — both golden
    fixtures do — and `application/planner.py` records what such a record means where it selects
    it: *"a status snapshot is the value entering its keyed scene"*. So the numbers such a scene
    is shown at `s1` are the numbers its own author stated for `s1`, and writing different ones
    mints a second canon snapshot at one key, which `integrity.detect_contradictions` groups on
    and refuses. Refusing here as well would leave the book unable to pass either gate.

    The books this gate was built for have no record at their own position until they draft
    one: they carry the un-keyed opening state, which is what the fall-through below reads.
    """
    authored = [*_canon(), _snapshot("ines_barrow", _standing(), order_key="s1")]

    gate = gate_progression("cold seal", "cold_seal", before=authored, extracted=[], at="s1")

    assert gate is not None
    assert gate.passed is True
    assert gate.vetoes == ()
    assert gate.detail is not None and "canon already states" in gate.detail

    # The same records without that one line: an un-keyed opening, and the gate bites.
    biting = gate_progression("cold seal", "cold_seal", before=_canon(), extracted=[], at="s1")
    assert biting is not None and biting.passed is False


# --------------------------------------------------------------------------- three refusals


def test_a_scene_that_writes_down_no_state_is_refused_and_says_so() -> None:
    """A scene that never prints the line asserts nothing, and a scene that prints it with
    every number unchanged asserts nothing either — `extraction._already_canon` drops a
    snapshot identical to one canon already holds at this position. One verdict, and a refusal
    sentence that names which of the two happened."""
    before = _canon()

    gate = gate_progression("cold seal", "cold_seal", before=before, extracted=[], at="s1")

    assert gate is not None
    assert gate.passed is False
    assert gate.vetoes == (Veto.PROGRESSION_UNMOVED,)
    assert gate.detail == (
        "cold seal was named as moving here; this scene wrote down no state for "
        "ines_barrow at s1, and cold_seal stands at 2"
    )


def test_somebody_elses_line_is_not_the_line_the_beat_named() -> None:
    """§170's lesson through the other door. The quantity belongs to whoever holds the line the
    writer was handed, so a snapshot extracted for a different subject at the same position
    does not discharge the ask — a side character progressing is not forbidden and is not this.
    """
    before = _canon()
    apprentice = _snapshot(
        "sunny_pell", {**_standing(), "cold_seal": 4}, order_key="s1"
    )

    gate = gate_progression(
        "cold seal", "cold_seal", before=before, extracted=[apprentice], at="s1"
    )

    assert gate is not None and gate.passed is False


def test_a_column_the_standing_line_does_not_print_abstains_rather_than_refusing() -> None:
    """An abstention is not a refusal, and it says which it is. The gate compares two integers;
    where the line standing here holds no such column there is nothing to compare, and refusing
    would blame a scene for a book's own declaration."""
    before = _canon()

    gate = gate_progression("Warmth", "warmth", before=before, extracted=[], at="s1")

    assert gate is not None
    assert gate.passed is True
    assert gate.vetoes == ()
    assert gate.detail is not None and "prints no warmth column" in gate.detail


def test_a_scene_with_no_position_abstains(
) -> None:
    before = _canon()

    gate = gate_progression("cold seal", "cold_seal", before=before, extracted=[], at=None)

    assert gate is not None
    assert gate.passed is True
    assert gate.detail is not None and "no position to place a state at" in gate.detail


# --------------------------------------------------------------- what it may never fire on


def test_an_unscheduled_scene_is_untouched() -> None:
    """`beat_ordinals(6)` is `{1, 3, 5}`, so scene 2's plan carries no progression beat at all
    and the ladder is byte-identical to what it was before this gate existed."""
    plan = with_bound(genre.with_beat("", 2, 6, counts=("cold seal",)), 2)

    assert genre.beat_name_in(plan) is None
    assert named_target(plan, _canon(), character="ines_barrow", at="s2") is None
    assert gate_progression(None, None, before=_canon(), extracted=[], at="s2") is None


def test_the_categorical_beat_names_no_quantity_so_there_is_nothing_to_check() -> None:
    """§161.4's control: a book that counts nothing gets `BEAT` unchanged, which names a
    category. A gate cannot ask whether *one of the numbers this book counts* moved."""
    assert genre.beat_name_in(genre.BEAT) is None
    assert named_target(genre.BEAT, [], at="s1") is None


def test_the_gate_cannot_fire_on_a_scene_whose_beat_asked_for_no_move() -> None:
    """§173's two interaction forms. Neither ends in `BEAT_TAIL` — an offer says a fork *stands
    open*, and a fork moves no number, which is exactly why `_named_moves` drops a `CHOOSE`.
    A gate reading either as a request to move something would be §161.4's own defect (a beat
    satisfied by the wrong thing) arriving through a third door."""
    assert genre.beat_name_in(genre.INTERACTION_BEAT) is None
    assert genre.beat_name_in(genre.OFFER_BEAT.format(name="the Turn", options="hand")) is None

    both = genre.with_interaction("", 1, 6, reads=True)
    assert genre.beat_name_in(both) is None


def test_a_fork_is_never_a_named_quantity_even_beside_a_beat_that_did_fire() -> None:
    """The fork's name is not in `movables` at all, so even a plan that carries a progression
    beat *and* an open fork can only ever be checked against the quantity the progression beat
    named. Asserted over the vocabulary rather than over one sentence, because the guarantee is
    that a fork never enters it."""
    system = _system(
        choices=(
            gamesystem.Choice(
                "the_turn",
                "the Turn",
                options=(
                    gamesystem.Option("through_the_hand", "hand", grants=("hold_a_room",)),
                    gamesystem.Option(
                        "through_the_keel", "keel", grants=("stand_the_frame",)
                    ),
                ),
            ),
        )
    )
    kinds = {move.kind for move in gamesystem.legal_moves(_sheet_of(system))}
    assert gamesystem.AdvanceKind.CHOOSE in kinds

    offered = movables(_canon(system), character="ines_barrow")
    assert "the Turn" not in {item.name for item in offered}
    assert {"hand", "keel"}.isdisjoint({item.name for item in offered})


# ------------------------------------------------------------------ one answer, two halves


def test_the_names_a_beat_may_use_are_a_projection_of_the_columns_they_move() -> None:
    """`movable_names` is `movables`' names and nothing else, so the word the plan carries and
    the number a later check reads cannot come apart. A rise is the one place the two halves
    differ: it is named by the rung it reaches and moves the rung column."""
    records = _canon()

    offered = movables(records, character="ines_barrow", at="s1")
    assert movable_names(records, character="ines_barrow", at="s1") == tuple(
        item.name for item in offered
    )
    assert Movable("cold seal", "cold_seal") in offered
    assert Movable("fitter", gamesystem.RANK_KEY) in offered


def test_a_name_this_book_no_longer_offers_abstains_rather_than_being_mapped_anyway() -> None:
    """`named_target` maps a word to a column only through the arm that minted the word. A
    fall-back mapping invented at check time would be the second answer `Movable` exists to
    prevent, so an unrecognised name is an abstention and never a guess."""
    assert named_target(_plan("Windread"), _canon(), character="ines_barrow", at="s1") is None


# -------------------------------------------------------------------- the ladder's contract


def test_the_gate_is_deterministic_and_therefore_may_block() -> None:
    """The whole §138 licence, asserted rather than asserted about. `PolicyDecision` raises on a
    blocking gate that sources its verdict from the generating model; this one's verdict is
    arithmetic over two stored integers, so the decision constructs."""
    before = _canon()
    gate = gate_progression(
        "cold seal", "cold_seal", before=before, extracted=[], at="s1"
    )
    assert gate is not None
    assert gate.gate is GateKind.INTEGRITY
    assert gate.rule_or_critic_id == PROGRESSION_GATE
    assert gate.verdict_source is VerdictSource.DETERMINISTIC
    assert gate.blocking is True

    decision = PolicyDecision(
        decision_id=decision_id_for("job", 1, (gate,)),
        outcome=Outcome.RETRY,
        gates=(gate,),
    )
    assert decision.parked_by_veto is False
    assert decision.refused_before_work is False


def test_the_refusal_earns_another_attempt_rather_than_parking_the_unit() -> None:
    """Classified beside `LENGTH_MOVEMENT`, not beside the craft vetoes. `PARKABLE` exists
    because retrying against a *calibrated proxy* is rejection sampling; this gate reads no
    proxy, so a second attempt is asking again for a thing the prompt already asked for."""
    assert Veto.PROGRESSION_UNMOVED in RETRYABLE
    assert Veto.PROGRESSION_UNMOVED not in PARKABLE

    gate = gate_progression(
        "cold seal", "cold_seal", before=_canon(), extracted=[], at="s1"
    )
    assert gate is not None
    outcome, reason = decide((gate,), job_id="job", attempt=1, max_attempts=3)
    assert outcome is Outcome.RETRY
    assert reason is not None and Veto.PROGRESSION_UNMOVED.value in reason

    # And it is the attempt budget, not this veto, that ends the unit.
    spent, _ = decide((gate,), job_id="job", attempt=3, max_attempts=3)
    assert spent is Outcome.PARK


def test_the_ask_is_recorded_where_it_is_composed(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The planner's half, on the live drafting path.

    Both halves of the ask travel on the job payload beside `story_order_key`, and for that
    key's own recorded reason: what the plan held when the work was selected is what the scene
    was written against, and a handler re-deriving either half after the draft comes back would
    be checking today's answer. The prompt carries the sentence and the payload carries what it
    named, and this asserts the two agree.

    Scene 2 is the control. `beat_ordinals(6)` is `{1, 3, 5}`, so its plan carries no
    progression beat, and its payload is expected to carry neither key rather than a null —
    absence is what the gate reads as nothing to check.
    """
    job = _selected(tmp_path / "opening.db", drafted=0)
    selected = job.payload["selected_by"]
    assert selected["ordinal"] == 1
    recorded = Movable(selected["progression_beat"], selected["progression_column"])
    # The sentence in the prompt names it, and the pair is one this book's own system offers
    # here. Which of them the rotation reached is `beat_text`'s arithmetic and not this
    # assertion's business (§161.4).
    assert genre.NAMED_BEAT.format(name=recorded.name) in str(job.payload["prompt"])
    assert recorded in movables(_canon(), character="ines_barrow", at="s1")

    # A second store rather than a second call: the selector keeps one draft in flight per
    # book, so draining a queue would report no work instead of the next scene.
    second = _selected(tmp_path / "second.db", drafted=1)
    assert second.payload["selected_by"]["ordinal"] == 2
    assert "progression_beat" not in second.payload["selected_by"]
    assert "progression_column" not in second.payload["selected_by"]
    assert genre.BEAT_TAIL not in str(second.payload["prompt"])


def test_no_refusal_of_this_gate_reaches_the_next_attempts_prompt() -> None:
    """§97.1, as a property of the text rather than a promise about it. The detail is written
    for an operator reading a decision record; the prompt is frozen at enqueue and the retry
    re-sends it unchanged. So the sentence names the missing fact and carries no instruction,
    no adjective and no word of the house's own machinery vocabulary."""
    from litharness.domain import house

    gate = gate_progression(
        "cold seal", "cold_seal", before=_canon(), extracted=[], at="s1"
    )
    assert gate is not None and gate.detail is not None
    words = {word.strip(".,;:").casefold() for word in gate.detail.split()}
    assert not (words & house.MACHINERY_WORDS)
