"""Stage-0 §167: the packet's half of §165, and the book whose every secret was already told.

§165 introduced the two order-key spaces and fixed the *fold* — what state stands at a scene.
§165.3 measured, registered and deliberately did not fix the other half: the packet's cutoff and
the disclosure schedule carried the identical `'0350' <= 's1'` defect. On serial15.db,
`state.records_before('s1')` admitted **18** records whose key is not comparable to `s1`, and
`worlds.undisclosed_claims` compared `key > at`, so **0 of that book's 8 claims were still hidden
at scene one** — every scheduled reveal handed to the writer of the chapter that introduces them,
which is the mystery-answer leak `plan/world-architect.md` already recorded once.

This file pins the fix at serial15.db's exact key set, values and claim ids. The disclosure
semantics it asserts are §110's, not new ones: **a position never discloses on its own, a record
does.** A claim is told when a `disclosed_to` record stands at a position the book has actually
reached — or carries no position at all, which is the one case a world has actually said "known
from the first page". Reading a schedule key as satisfied once the book passes the scene it
stands for would need a schedule→scene projection, which §165.3 refused by name, and §110.3
measured that inference wrong in both directions inside a single run.

The counterpart to `tests/test_order_key_spaces.py`, and deliberately its shape: the same
serial15 seed, the same sweep-across-both-spaces pattern, the same refusal to assert on prose the
defect produced. No model reads, ranks or judges anything here, and no bar is declared.
"""

from __future__ import annotations

import litharness_contracts as lc
import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.domain import context as context_mod
from litharness.domain import state, worlds

#: Serial Pilot 15's seven scheduled reveals, claim id → the key its `disclosed_to` states.
#: Verbatim from `serial15.db`; the Architect minted them at gap-10 from the beat sheet, so each
#: is ten times the `reveal_scene` ordinal the same world declares.
_SCHEDULED_REVEALS = {
    "claim_halla": "0060",
    "claim_nan": "0090",
    "claim_scrapbox": "0120",
    "claim_wedge": "0140",
    "claim_bez": "0170",
    "claim_piet": "0210",
    "claim_above": "0380",
}

#: The eighth claim. It carries no disclosure and is marked `claim.false`, so it is not hidden
#: and never was — the hidden heading says *true*, and a character's error under it would
#: instruct the writer to honour something the world denies.
_FALSE_CLAIM = "claim_past_saving"

#: The four scheduled standings and three scheduled abilities that ride the same defect, at
#: serial15's own keys. `mira` also holds an un-keyed opening standing.
_SCHEDULED_STANDINGS = {"0110": "rung_keeper", "0250": "rung_joiner", "0350": "rung_wright"}


def _claim(subject: str, *, false: bool = False) -> list[lc.StateRecord]:
    records = [
        worlds.world_record(
            subject,
            worlds.CLAIM_CONTENT,
            value=f"what {subject} is about",
            authority=lc.StateAuthority.ACCEPTED_CANON,
        )
    ]
    if false:
        records.append(
            worlds.world_record(
                subject,
                worlds.CLAIM_FALSE,
                value=True,
                authority=lc.StateAuthority.ACCEPTED_CANON,
            )
        )
    return records


def _disclosure(claim: str, order_key: str | None) -> lc.StateRecord:
    return worlds.world_record(
        claim,
        worlds.DISCLOSED_TO,
        object_ref=claim,
        value=worlds.READER,
        order_key=order_key,
        authority=lc.StateAuthority.ACCEPTED_CANON,
    )


def _seed() -> list[lc.StateRecord]:
    """Serial 15's claim half, as it stood when scene one was drafted."""
    records: list[lc.StateRecord] = []
    for claim, key in _SCHEDULED_REVEALS.items():
        records.extend(_claim(claim))
        records.append(_disclosure(claim, key))
    records.extend(_claim(_FALSE_CLAIM, false=True))
    return records


def _hidden(records: list[lc.StateRecord], *, at: str | None) -> set[str]:
    return {record.subject for record in worlds.undisclosed_claims(records, at=at)}


# --- the repro -------------------------------------------------------------------------------


def test_the_pilot_fifteen_claims_are_all_still_hidden_at_scene_one() -> None:
    """The repro. Before §167 this set was empty, and that is the whole defect.

    Seven, not eight, and the eighth is the measurement's own correction: §165.3 counted the
    denominator as the book's 8 `claim.content` records, one of which is marked false and is
    therefore *correctly* never hidden. So the attainable maximum here is seven, and seven is
    what the un-positioned call has always returned — which is what makes `at='s1'` returning
    zero a defect in the comparison rather than a disagreement about the count.
    """
    records = _seed()
    assert _hidden(records, at="s1") == set(_SCHEDULED_REVEALS)
    assert len(_SCHEDULED_REVEALS) == 7
    assert _hidden(records, at="s1") == _hidden(records, at=None)


def test_the_false_claim_is_the_eighth_and_is_not_hidden_at_any_position() -> None:
    """Not hidden before the fix and not hidden after it. See `CLAIM_FALSE`."""
    records = _seed()
    for at in (None, "s1", "s2", "0060", "0380"):
        assert _FALSE_CLAIM not in _hidden(records, at=at)


@pytest.mark.parametrize("at", ["s1", "s2", "s3", "s4", "s5", "s6", "s01", "s000001"])
def test_no_scene_of_that_book_reads_a_scheduled_reveal_as_told(at: str) -> None:
    """Not scene one by luck of the sort: unreachable from every scene, at every scene width.

    The widths matter because `beats_for` derives them from the book's own length, so the same
    seed meets `s1` in a six-scene book and `s000001` in a serial. A schedule key is future
    relative to all of them.
    """
    assert _hidden(_seed(), at=at) == set(_SCHEDULED_REVEALS)


# --- what a disclosure still is ---------------------------------------------------------------


def test_a_disclosure_with_no_position_is_still_told_from_the_first_page() -> None:
    """The one case where the world has actually said "already told", and it still says it."""
    records = [*_claim("open_secret"), _disclosure("open_secret", None)]
    for at in (None, "s1", "0350"):
        assert _hidden(records, at=at) == set()


def test_a_disclosure_in_the_scenes_own_space_discloses_when_the_book_reaches_it() -> None:
    """The working case, unchanged — this is what the fix must not break.

    Fourteen of the disclosure positions across the pilot stores are scene keys, and every one of
    those books reads identically before and after §167. Only the schedule-keyed ones moved.
    """
    records = [*_claim("told_at_three"), _disclosure("told_at_three", "s3")]
    assert _hidden(records, at="s1") == {"told_at_three"}
    assert _hidden(records, at="s2") == {"told_at_three"}
    assert _hidden(records, at="s3") == set()
    assert _hidden(records, at="s4") == set()


def test_one_landed_disclosure_tells_a_claim_its_schedule_still_only_plans() -> None:
    """A claim carrying both a schedule and a realisation is told by the realisation.

    This is the shape a disclosure channel would produce if one is ever built, and the assertion
    says the semantics are already right for it: the scene-space record decides, and the
    schedule-space one beside it neither helps nor blocks.
    """
    records = [
        *_claim("claim_wedge"),
        _disclosure("claim_wedge", "0140"),
        _disclosure("claim_wedge", "s2"),
    ]
    assert _hidden(records, at="s1") == {"claim_wedge"}
    assert _hidden(records, at="s2") == set()


def test_a_position_alone_never_discloses_a_scheduled_claim() -> None:
    """§110's rule, and the one this file most exists to pin.

    A book that has run past every ordinal its schedule names still has not *told* anything: the
    schedule is a statement of intent and intent is not an event. Asserted at a scene key far
    past the last reveal so that no reading of "the book got there" could rescue it.
    """
    assert _hidden(_seed(), at="s999999") == set(_SCHEDULED_REVEALS)


# --- the 18 incomparable records ---------------------------------------------------------------


def _positioned_seed() -> list[lc.StateRecord]:
    """serial15's schedule half: the shapes that made up the 18, at their own keys."""
    records = [
        worlds.world_record(
            "mira",
            worlds.STANDS_AT_PREDICATE,
            object_ref="rung_seamer",
            value="seamwork_rank",
            authority=lc.StateAuthority.ACCEPTED_CANON,
        )
    ]
    for key, rung in _SCHEDULED_STANDINGS.items():
        records.append(
            worlds.world_record(
                "mira",
                worlds.STANDS_AT_PREDICATE,
                object_ref=rung,
                value="seamwork_rank",
                order_key=key,
                authority=lc.StateAuthority.ACCEPTED_CANON,
            )
        )
    return records


def test_a_scheduled_record_does_not_pass_a_scene_cutoff() -> None:
    """The 18, as a rule rather than a count. Before §167 every one of them passed.

    The un-keyed record still passes, and the difference between it and a scheduled one is the
    whole design: un-keyed asserts no position and so belongs at every one, while a schedule key
    asserts a position the book has not reached and so belongs at none of them yet.
    """
    records = _positioned_seed()
    kept = state.records_before(records, "s1")
    assert [record.object_ref for record in kept] == ["rung_seamer"]
    assert len(records) - len(kept) == len(_SCHEDULED_STANDINGS)


def test_the_schedule_stays_canon_and_readable_in_its_own_space() -> None:
    """Excluded from a scene's packet is not discarded — §165's rule, carried to the cutoff.

    A fix that dropped these records would teach the next seed to stop scheduling, which is the
    behaviour §165 exists to protect.
    """
    records = _positioned_seed()
    assert len(state.records_before(records, "0250")) == 3
    assert worlds.standing_of(records, "mira", at="0250") == {"seamwork_rank": "rung_joiner"}


def test_scene_one_reads_the_opening_standing_not_the_end_of_the_arc() -> None:
    """§165's leak arriving through `stands_at`, which is a second door on the same book.

    Measured on serial15.db and serial14b.db before the fix; the packet's own status line takes
    its rung from here.
    """
    records = _positioned_seed()
    assert worlds.standing_of(records, "mira", at="s1") == {"seamwork_rank": "rung_seamer"}
    assert worlds.standing_of(records, "mira", at="s6") == {"seamwork_rank": "rung_seamer"}


def test_a_subject_whose_only_standing_is_scheduled_has_none_yet() -> None:
    """serial15's `bez`, and the deliberate half of the choice.

    Returning the scheduled rung would be this function answering "where does he stand when the
    book opens" with a position the world declared about somewhere else. An empty answer is the
    world declining to say, which it did.
    """
    records = [
        worlds.world_record(
            "bez",
            worlds.STANDS_AT_PREDICATE,
            object_ref="rung_tacker",
            value="seamwork_rank",
            order_key="0300",
            authority=lc.StateAuthority.ACCEPTED_CANON,
        )
    ]
    assert worlds.standing_of(records, "bez", at="s1") == {}
    assert worlds.standing_of(records, "bez", at="0300") == {"seamwork_rank": "rung_tacker"}


def test_the_packet_says_which_records_it_could_not_place_and_why() -> None:
    """Excluded *and* complained about, which is the third option §167 chose deliberately.

    A record dropped for standing later in the book will arrive; one dropped because its
    position is in another space will be dropped at every scene. Reporting both as "not yet
    established" would make a permanent exclusion look like a temporary one.
    """
    boundary = state.StoryBoundary("s1")
    scheduled = _positioned_seed()[1]
    assert not state.reached_boundary(scheduled, boundary)
    assert state.key_space(state.order_key_of(scheduled)) == state.SCHEDULE_KEYS
    assert context_mod is not None  # the reason lives on the packet path; see `assemble`


# --- the sweep across both spaces ---------------------------------------------------------------


_SCENE = ("s1", "s6", "s01", "s000001")
_SCHEDULE = ("0060", "0110", "0350", "22")


@pytest.mark.parametrize("key", _SCHEDULE)
@pytest.mark.parametrize("at", _SCENE)
def test_no_schedule_key_passes_any_scene_threshold_in_either_direction(key: str, at: str) -> None:
    """The sweep. Every packet-side threshold, over both spaces, at every width in use.

    "Either direction" is the load-bearing half: a schedule key must not read as *past* a scene
    (which leaked the end of the book into its opening) and must not read as *told* (which
    leaked every mystery answer). Both are the same string comparison and both are asserted.
    """
    record = worlds.world_record(
        "mira", worlds.STANDS_AT_PREDICATE, object_ref="r", order_key=key,
        authority=lc.StateAuthority.ACCEPTED_CANON,
    )
    assert not state.comparable(key, at)
    assert state.records_before([record], at) == ()
    assert not state.reached_boundary(record, state.StoryBoundary(at))
    assert _hidden([*_claim("c"), _disclosure("c", key)], at=at) == {"c"}


@pytest.mark.parametrize("at", _SCENE)
def test_a_key_in_neither_space_passes_no_threshold_either(at: str) -> None:
    """§152's `--order-key`/`--value` trap, which sorts by spelling and so leaks by spelling.

    `clearance` is permanently past and `zz_c` permanently future against the same cutoff. Both
    are unplaceable, and unplaceable now means the same thing on both sides of the alphabet.
    """
    for key in ("clearance", "zz_c", "cuff", "reckoning"):
        record = worlds.world_record(
            "mira", worlds.STANDS_AT_PREDICATE, object_ref="r", order_key=key,
            authority=lc.StateAuthority.ACCEPTED_CANON,
        )
        assert state.records_before([record], at) == ()
        assert not state.reached_boundary(record, state.StoryBoundary(at))
        assert _hidden([*_claim("c"), _disclosure("c", key)], at=at) == {"c"}


@pytest.mark.parametrize("at", _SCHEDULE)
def test_a_scene_key_is_no_more_comparable_to_a_schedule_cutoff_than_the_reverse(at: str) -> None:
    """Symmetry, because a rule that only runs one way is a rule with a second defect in it."""
    for key in _SCENE:
        record = worlds.world_record(
            "mira", worlds.STANDS_AT_PREDICATE, object_ref="r", order_key=key,
            authority=lc.StateAuthority.ACCEPTED_CANON,
        )
        assert state.records_before([record], at) == ()
        assert _hidden([*_claim("c"), _disclosure("c", key)], at=at) == {"c"}


# --- the SQL twin -------------------------------------------------------------------------------


def test_the_store_and_the_domain_slice_both_spaces_identically(tmp_path) -> None:
    """§165.3 named the twin's existence; this is it, at both spaces and the un-keyed.

    `state_records`' `before` and `records_before` are one question with two implementations, and
    SQLite compares strings exactly the way Python does — `'0350' <= 's1'` is true in both. The
    store now calls the domain's own `key_space` through a registered function rather than
    spelling the two spaces in SQL a second time, so this asserts they cannot drift.
    """
    store = SqliteStore.open(tmp_path / "spaces.db")
    records = [
        worlds.world_record(
            "mira", worlds.STANDS_AT_PREDICATE, object_ref=f"r{index}", order_key=key,
            authority=lc.StateAuthority.ACCEPTED_CANON,
        )
        for index, key in enumerate(["s1", "s6", "0110", "0350", "clearance", None])
    ]
    store.record_state_records("book", "branch", records, created_at="t")
    for cutoff in (None, "s1", "s2", "s6", "0110", "0350", "clearance", "zz_c"):
        from_store = {
            item.record_id for item in store.state_records("book", "branch", before=cutoff)
        }
        in_memory = {item.record_id for item in state.records_before(records, cutoff)}
        assert from_store == in_memory, cutoff
