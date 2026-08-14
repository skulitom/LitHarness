"""The propagation engine's rules, on books built for the rule rather than on the fixtures.

`tests/test_impact.py` scores this engine against the gold suites, and that is the §17 Stage 2
number. It is also four cases over material generated from the same `def.json` that authors
the prose it grades, so a rule tested only there is a rule fitted to it. These tests are the
other half: each rule against a book constructed to exercise it, including the cases the gold
has none of — a rename whose old name survives only inside a preserved alias, a fact that
appears only *before* the change, a move that runs backwards, and a change kind no rule
understands.

The abstention tests are the ones that matter most. A propagation engine that guesses on a
change it cannot read rewrites conforming prose, which is the expensive error here: §17's own
exit clause makes `e3-typography-only` — no `must_update`, eight `safe_preserve` — the case an
engine optimised for recall fails.
"""

from __future__ import annotations

from typing import Any

import litharness_contracts as lc

from litharness.domain import propagation
from tests.conftest import meta, resource_ref

RENAME = lc.ExtractedChange(
    kind=lc.ExtractedChangeKind.ENTITY_RENAMED,
    subject="julian",
    before="Julian",
    after="Adrian",
)


def scene(ordinal: int, text: str) -> propagation.ProseNode:
    return propagation.ProseNode(f"scene-{ordinal}", f"{ordinal * 10:03d}", text)


def book(*texts: str, records: tuple[lc.StateRecord, ...] = ()) -> propagation.Book:
    return propagation.Book(
        nodes=tuple(scene(index + 1, text) for index, text in enumerate(texts)),
        records=records,
    )


def record(
    record_id: str,
    subject: str,
    predicate: str,
    value: Any,
    *,
    order_key: str | None = None,
    kind: lc.StateRecordKind = lc.StateRecordKind.ASSERTION,
) -> lc.StateRecord:
    return lc.StateRecord(
        record_id=record_id,
        kind=kind,
        subject=subject,
        predicate=predicate,
        value=value,
        story_position=lc.StoryPosition(order_key=order_key) if order_key else None,
        authority=lc.StateAuthority.ACCEPTED_CANON,
    )


def change_set(
    *,
    edits: tuple[str, ...] = (),
    changes: tuple[lc.ExtractedChange, ...] = (),
    detail: dict[str, Any] | None = None,
) -> lc.ChangeSet:
    return lc.ChangeSet(
        meta=meta("change_set", "cs-test"),
        change_set_id="cs-test",
        base_revision="rev-test",
        target_branch="branch-test",
        actor=lc.ChangeActor.AUTHOR,
        operations=[
            lc.ChangeOperation(
                kind=lc.ChangeOpKind.REPLACE_SPAN,
                logical_source_id=logical_id,
                detail=dict(detail or {}),
            )
            for logical_id in edits
        ],
        idempotency_key="idem-test",
        extracted_changes=list(changes),
    )


def reached(result: propagation.Propagation) -> set[str]:
    return result.logical_ids


# --- surface_only: the negative control ----------------------------------------------


def test_a_surface_only_change_reaches_nothing() -> None:
    """The whole shape of §17's `e3-typography-only`. A curly apostrophe changes a content
    hash and no referent; an engine that propagates on it rewrites six conforming scenes."""
    result = propagation.propagate(
        change_set(
            edits=("scene-1",),
            changes=(lc.ExtractedChange(kind=lc.ExtractedChangeKind.SURFACE_ONLY),),
        ),
        book("Julian at the window.", "Julian again.", "And Julian once more."),
    )

    assert reached(result) == set()
    assert result.complete, "surface_only is understood, not abstained on"


def test_surface_only_alongside_a_semantic_change_does_not_suppress_it() -> None:
    """`surface_only` says *this* change carries no meaning, not that the change set does.
    Treating it as a set-wide veto would let one reformatted sentence hide a rename."""
    result = propagation.propagate(
        change_set(
            edits=("scene-1",),
            changes=(
                lc.ExtractedChange(kind=lc.ExtractedChangeKind.SURFACE_ONLY),
                RENAME,
            ),
        ),
        book("Julian at the window.", "Nobody here.", "Julian again."),
    )

    assert reached(result) == {"scene-3"}


# --- entity_renamed ------------------------------------------------------------------


def test_a_rename_reaches_the_scenes_that_say_the_name() -> None:
    result = propagation.propagate(
        change_set(edits=("entity:julian",), changes=(RENAME,)),
        book("Edmund is dead.", "Julian arrived late.", "No one of that name.", "Julian again."),
    )

    assert reached(result) == {"scene-2", "scene-4"}
    assert all(target.rule == propagation.ENTITY_RENAMED for target in result.targets)


def test_a_rename_reaches_backwards_as_well_as_forwards() -> None:
    """Unlike a ledger value, a name is not carried forward — it is simply spelled, and every
    place it is spelled is wrong the moment it changes. A position filter here would leave
    the earlier half of the book saying the old name."""
    result = propagation.propagate(
        change_set(edits=("scene-3",), changes=(RENAME,)),
        book("Julian first.", "Nothing.", "the edited scene", "Julian last."),
    )

    assert reached(result) == {"scene-1", "scene-4"}


def test_a_name_inside_a_preserved_alias_is_not_a_mention() -> None:
    """The gold's own case: renaming Julian must not reach the scene that says only "the
    nephew". Generalised here to the harder version the fixtures have none of — an alias that
    *contains* the old name, where a plain search would touch a scene the change preserves."""
    preserving = lc.ExtractedChange(
        kind=lc.ExtractedChangeKind.ENTITY_RENAMED,
        subject="julian",
        before="Julian",
        after="Adrian",
    )
    result = propagation.propagate(
        change_set(
            edits=("entity:julian",),
            changes=(preserving,),
            detail={"from": "Julian", "to": "Adrian", "preserve_aliases": ["Julian's man"]},
        ),
        book("Julian's man waited outside.", "Julian waited outside."),
    )

    assert reached(result) == {"scene-2"}


def test_a_rename_reaches_the_records_whose_subject_it_is() -> None:
    result = propagation.propagate(
        change_set(edits=("entity:julian",), changes=(RENAME,)),
        book(
            "Nothing here.",
            records=(
                record("rec-julian-claim", "julian", "claims", "was_in_city"),
                record("rec-will", "new_will", "disinherits", "julian"),
                record("rec-edmund", "edmund", "life_status", "dead"),
            ),
        ),
    )

    assert reached(result) == {"rec-julian-claim", "rec-will"}


def test_a_substring_of_a_longer_word_is_not_a_mention() -> None:
    """"Vane" must not match "Vanessa". Word boundaries are the whole of the rule's
    precision, and without them a short name reaches the entire book."""
    result = propagation.propagate(
        change_set(
            edits=("entity:vane",),
            changes=(
                lc.ExtractedChange(
                    kind=lc.ExtractedChangeKind.ENTITY_RENAMED,
                    subject="vane",
                    before="Vane",
                    after="Vayne",
                ),
            ),
        ),
        book("Vanessa poured the tea.", "Vane poured the tea."),
    )

    assert reached(result) == {"scene-2"}


def test_a_rename_with_no_old_name_abstains_rather_than_reaching_everything() -> None:
    """An `entity_renamed` with no `before` value cannot be searched for. Predicting the whole
    book is the recall-optimal answer and the one that damages it."""
    result = propagation.propagate(
        change_set(
            edits=("entity:x",),
            changes=(
                lc.ExtractedChange(
                    kind=lc.ExtractedChangeKind.ENTITY_RENAMED, subject="x", after="Y"
                ),
            ),
        ),
        book("Anything.", "Anything else."),
    )

    assert reached(result) == set()
    assert not result.complete
    assert result.unhandled == ("entity_renamed",)


# --- fact_changed --------------------------------------------------------------------


GOLD = lc.ExtractedChange(
    kind=lc.ExtractedChangeKind.FACT_CHANGED,
    subject="rook",
    predicate="gold",
    before=25,
    after=33,
)


def test_a_changed_fact_reaches_the_later_scenes_that_carry_it() -> None:
    """A running total is the case: the price changes in scene 2 and every later balance is
    wrong, whether or not it repeats the number that changed."""
    result = propagation.propagate(
        change_set(edits=("scene-2",), changes=(GOLD,)),
        book(
            "Rook had forty-five gold.",
            "Rook counted twelve gold onto the barrel.",
            "Rook had thirty-three gold left.",
            "Rook drank the potion.",
            "Rook paid the last fifteen gold.",
        ),
    )

    assert reached(result) == {"scene-3", "scene-5"}


def test_a_changed_fact_does_not_reach_backwards() -> None:
    """Scene 1's balance was true before the purchase and stays true after it. This is the
    difference between a fact that propagates and a name that is simply spelled."""
    result = propagation.propagate(
        change_set(edits=("scene-2",), changes=(GOLD,)),
        book("Rook had forty-five gold.", "Rook counted twelve gold.", "Rook slept."),
    )

    assert "scene-1" not in reached(result)


def test_a_changed_fact_needs_both_its_subject_and_its_predicate() -> None:
    """A scene about somebody else's gold is not about Rook's."""
    result = propagation.propagate(
        change_set(edits=("scene-1",), changes=(GOLD,)),
        book(
            "Rook counted twelve gold.",
            "Marrow counted his own gold.",
            "Rook slept without dreaming.",
            "Rook still had gold.",
        ),
    )

    assert reached(result) == {"scene-4"}


def test_a_changed_fact_reaches_the_records_that_state_it_from_there_on() -> None:
    """Filtered on the story position the *records themselves* attest for the edited scene —
    never on a mapping from `position_key` to `order_key`, which this project deliberately
    refuses to invent (`domain/extraction.attested_position`)."""
    records = (
        record("rec-s1", "rook", "status_snapshot", {"gold": 45}, order_key="s1"),
        record("rec-s2", "rook", "status_snapshot", {"gold": 25}, order_key="s2"),
        record(
            "rec-buy",
            "rook",
            "purchased",
            {"item": "lantern", "cost_gold": 20},
            order_key="s2",
        ),
        record("rec-skill", "rook", "used_skill", {"skill": "shadowstep"}, order_key="s3"),
        record("rec-rule", "system", "rule_hp_ceiling", "hp <= hp_max", order_key="s1"),
    )
    attesting = lc.StateRecord(
        record_id="rec-s2-evidence",
        kind=lc.StateRecordKind.ASSERTION,
        subject="rook",
        predicate="status_snapshot",
        value={"gold": 25},
        story_position=lc.StoryPosition(order_key="s2"),
        authority=lc.StateAuthority.ACCEPTED_CANON,
        evidence=[
            lc.EvidenceSpan(
                source=resource_ref("scene-2"), start=0, end=1, content_sha256="0" * 64
            )
        ],
    )
    result = propagation.propagate(
        change_set(edits=("scene-2",), changes=(GOLD,)),
        book("one", "two", "three", records=(*records, attesting)),
    )

    assert "rec-s2" in reached(result) and "rec-buy" in reached(result)
    assert "rec-s1" not in reached(result), "a balance before the change is still true"
    assert "rec-rule" not in reached(result), "an HP rule is not a gold fact"
    assert "rec-skill" not in reached(result), "the record must state the changed predicate"


def test_an_unattested_scene_widens_the_record_filter_and_says_so() -> None:
    """`attested_position` abstains where the book's own evidence is ambiguous — the mystery
    fixture's scene 2 is cited by records at two positions. Abstaining must widen the search
    rather than silently drop every record, and the widening is recorded on the reason so a
    reader is not left to infer it."""
    records = (
        record("rec-early", "rook", "status_snapshot", {"gold": 45}, order_key="s1"),
        record("rec-late", "rook", "status_snapshot", {"gold": 25}, order_key="s9"),
    )
    result = propagation.propagate(
        change_set(edits=("scene-2",), changes=(GOLD,)),
        book("one", "two", records=records),
    )

    assert reached(result) >= {"rec-early", "rec-late"}
    assert any("unplaced" in target.reason for target in result.targets)


def test_a_fact_change_with_no_predicate_abstains() -> None:
    result = propagation.propagate(
        change_set(
            edits=("scene-1",),
            changes=(
                lc.ExtractedChange(
                    kind=lc.ExtractedChangeKind.FACT_CHANGED, subject="rook", after=1
                ),
            ),
        ),
        book("Rook had gold.", "Rook had more gold."),
    )

    assert reached(result) == set()
    assert result.unhandled == ("fact_changed",)


# --- event_moved ---------------------------------------------------------------------


MOVED = lc.ExtractedChange(
    kind=lc.ExtractedChangeKind.EVENT_MOVED,
    subject="rec-key-discovered",
    before="s2",
    after="s5",
)


def test_a_moved_event_reaches_the_scenes_between_where_it_was_and_where_it_goes() -> None:
    """Only the window breaks. Before the origin the event had not happened either way;
    after the destination it has happened either way. That is why position predicts this one
    and predicts `e2-rename-julian` not at all."""
    result = propagation.propagate(
        change_set(edits=("scene-2", "scene-5"), changes=(MOVED,)),
        book("one", "two", "three", "four", "five", "six"),
    )

    assert reached(result) == {"scene-3", "scene-4"}


def test_a_move_that_runs_backwards_reaches_the_same_window() -> None:
    """The window is between the two edited scenes, not after the first of them. A rule
    written as "everything after the origin" gets this one exactly backwards."""
    result = propagation.propagate(
        change_set(edits=("scene-5", "scene-2"), changes=(MOVED,)),
        book("one", "two", "three", "four", "five", "six"),
    )

    assert reached(result) == {"scene-3", "scene-4"}


def test_a_moved_event_takes_the_records_at_its_origin_that_share_its_subject() -> None:
    """Knowledge acquired at the event moves with it. A record at the same position about
    somebody else does not — which is the difference between a subject filter and a position
    filter, and the gold's `e1-move-key-discovery` grades exactly that distinction."""
    records = (
        record(
            "rec-key-discovered",
            "mara",
            "discovered_item",
            {"item": "brass_key"},
            order_key="s2",
            kind=lc.StateRecordKind.EVENT,
        ),
        record(
            "rec-mara-knows",
            "mara",
            "knows",
            "key_under_floorboard",
            order_key="s2",
            kind=lc.StateRecordKind.KNOWLEDGE,
        ),
        record("rec-tomas", "tomas", "located_in", {"place": "conservatory"}, order_key="s2"),
        record("rec-mara-later", "mara", "knows", "the_will", order_key="s4"),
    )
    result = propagation.propagate(
        change_set(edits=("scene-2", "scene-5"), changes=(MOVED,)),
        book("one", "two", "three", "four", "five", records=records),
    )

    assert {"rec-key-discovered", "rec-mara-knows"} <= reached(result)
    assert "rec-tomas" not in reached(result)
    assert "rec-mara-later" not in reached(result)


def test_a_move_naming_a_record_that_is_not_there_still_moves_the_scenes() -> None:
    """The two halves are independent evidence. Losing the record half must not cost the
    node half, and the missing record is reported rather than assumed absent."""
    result = propagation.propagate(
        change_set(edits=("scene-2", "scene-4"), changes=(MOVED,)),
        book("one", "two", "three", "four"),
    )

    assert reached(result) == {"scene-3"}


def test_a_move_within_one_scene_reaches_nothing() -> None:
    """Origin and destination in the same node leaves no window, and no scene between them
    is wrong. Predicting the rest of the book would be the recall-optimal wrong answer."""
    result = propagation.propagate(
        change_set(edits=("scene-2",), changes=(MOVED,)),
        book("one", "two", "three", "four"),
    )

    assert reached(result) == set()


# --- abstention ----------------------------------------------------------------------


def test_a_change_kind_no_rule_understands_is_reported_not_guessed() -> None:
    """The property this engine most needs. `plan_changed`, `pov_changed`, `rule_changed`,
    `event_added` and `event_removed` are all in the contract's vocabulary and none has a
    rule here. Returning "nothing propagates" for them *silently* is how a caller comes to
    believe a change was analysed when it was skipped — the same defect as an evaluation
    that did not finish reporting a clean book."""
    result = propagation.propagate(
        change_set(
            edits=("scene-1",),
            changes=(lc.ExtractedChange(kind=lc.ExtractedChangeKind.POV_CHANGED, subject="mara"),),
        ),
        book("one", "two"),
    )

    assert reached(result) == set()
    assert not result.complete
    assert result.unhandled == ("pov_changed",)


def test_a_change_set_that_extracted_nothing_is_incomplete_rather_than_clean() -> None:
    """No extracted changes is not "no propagation" — it is "nobody looked". A change set
    whose producer emitted no semantic reading has told this engine nothing at all."""
    result = propagation.propagate(change_set(edits=("scene-1",)), book("one", "two"))

    assert reached(result) == set()
    assert not result.complete


def test_every_target_carries_the_rule_that_reached_it_and_why() -> None:
    """The output is read by an operator deciding whether to enqueue work over their book.
    A bare list of ids asks them to take it on trust; §19's audit story does not work that
    way anywhere else either."""
    result = propagation.propagate(
        change_set(edits=("entity:julian",), changes=(RENAME,)),
        book("Nothing.", "Julian arrived."),
    )

    [target] = result.targets
    assert target.logical_id == "scene-2"
    assert target.rule == propagation.ENTITY_RENAMED
    assert "Julian" in target.reason


def test_one_node_reached_by_two_rules_is_reported_once_per_rule() -> None:
    """Deduplicated by id for the caller, and kept per rule for the reader: two independent
    reasons to re-check a scene is a stronger signal than one, and collapsing them loses it.
    """
    result = propagation.propagate(
        change_set(edits=("scene-1",), changes=(RENAME, GOLD)),
        book("the edited scene", "Julian counted Rook's gold."),
    )

    assert reached(result) == {"scene-2"}
    assert {target.rule for target in result.targets} == {
        propagation.ENTITY_RENAMED,
        propagation.FACT_CHANGED,
    }


def test_the_edited_nodes_are_never_targets() -> None:
    """An engine gets no credit for the node it was told to edit, and enqueueing work to
    re-check the scene that was just written is how a repair loop cycles."""
    result = propagation.propagate(
        change_set(edits=("scene-1", "scene-2"), changes=(RENAME,)),
        book("Julian here.", "Julian there.", "Julian everywhere."),
    )

    assert reached(result) == {"scene-3"}


# --- the in-repo producer ------------------------------------------------------------


def test_a_changed_field_becomes_a_fact_change_named_by_the_field() -> None:
    """`status_snapshot` is not a word any book contains; `gold` is both the changed field and
    the token the prose carries. Diffing a mapping to the field is what makes a produced
    change the same shape as the hand-authored gold — and what lets the node rule fire at all
    rather than reaching records only."""
    known = (record("rec-s2", "rook", "status_snapshot", {"gold": 25, "hp": 24}, order_key="s2"),)
    extracted = (
        record("rec-s2b", "rook", "status_snapshot", {"gold": 33, "hp": 24}, order_key="s2"),
    )

    [change] = propagation.changes_between(known, extracted)

    assert change.kind is lc.ExtractedChangeKind.FACT_CHANGED
    assert (change.subject, change.predicate) == ("rook", "gold")
    assert (change.before, change.after) == (25, 33)


def test_the_same_fact_at_another_position_is_the_ledger_advancing_not_a_change() -> None:
    """The correctness of the whole producer. A running balance differs at every position by
    design, so matching on `(subject, predicate)` alone would report the book working as a
    contradiction — and then propagate from it."""
    known = (record("rec-s2", "rook", "status_snapshot", {"gold": 25}, order_key="s2"),)
    extracted = (record("rec-s3", "rook", "status_snapshot", {"gold": 15}, order_key="s3"),)

    assert propagation.changes_between(known, extracted) == ()


def test_a_newly_stated_fact_is_not_a_change() -> None:
    """It invalidates no earlier prose. A candidate contradicting standing canon is refused by
    the integrity gate before it can commit, so this is not the place to catch that."""
    extracted = (record("rec-new", "mara", "knows", "the_will", order_key="s4"),)

    assert propagation.changes_between((), extracted) == ()


def test_an_unchanged_value_produces_no_change() -> None:
    """Re-extraction after a repair that touched something else must stay quiet, or every
    repair propagates to the whole book."""
    same = {"gold": 25, "hp": 24}
    known = (record("rec-a", "rook", "status_snapshot", same, order_key="s2"),)
    extracted = (record("rec-b", "rook", "status_snapshot", dict(same), order_key="s2"),)

    assert propagation.changes_between(known, extracted) == ()


def test_a_scalar_value_changes_under_its_own_predicate() -> None:
    known = (record("rec-a", "edmund", "life_status", "dead", order_key="s1"),)
    extracted = (record("rec-b", "edmund", "life_status", "missing", order_key="s1"),)

    [change] = propagation.changes_between(known, extracted)

    assert (change.predicate, change.before, change.after) == ("life_status", "dead", "missing")


def test_an_unplaced_record_is_not_compared() -> None:
    """`order_key` is the match key, so a record the book has not placed cannot be matched
    against anything — and treating None as a position would collide every unplaced record
    with every other, which `extraction.attested_position` refuses for the same reason."""
    known = (record("rec-a", "rook", "status_snapshot", {"gold": 25}),)
    extracted = (record("rec-b", "rook", "status_snapshot", {"gold": 33}),)

    assert propagation.changes_between(known, extracted) == ()


def test_a_produced_change_drives_the_engine_end_to_end() -> None:
    """The producer and the rules meet here: the change a repair makes to a status line is
    the change that reaches the later scenes carrying that balance."""
    known = (record("rec-s2", "rook", "status_snapshot", {"gold": 25}, order_key="s2"),)
    extracted = (record("rec-s2b", "rook", "status_snapshot", {"gold": 33}, order_key="s2"),)

    result = propagation.propagate_changes(
        propagation.changes_between(known, extracted),
        edited=("scene-2",),
        book=book(
            "Rook had forty-five gold.",
            "Rook counted twelve gold onto the barrel.",
            "Rook had thirty-three gold left.",
            "Rook slept.",
        ),
    )

    assert reached(result) == {"scene-3"}
    assert result.complete
