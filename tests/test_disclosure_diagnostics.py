"""Disclosure diagnostics explain existing visibility rules without deciding new reveals."""

from __future__ import annotations

import litharness_contracts as lc
import pytest

from litharness.domain import state, worlds
from litharness.domain.context import HIDDEN, assemble
from litharness.domain.revision import new_book


def _claim(
    subject: str,
    *,
    value: str = "A private fact.",
    order_key: str | None = None,
    authority: lc.StateAuthority = lc.StateAuthority.ACCEPTED_CANON,
) -> lc.StateRecord:
    return worlds.world_record(
        subject,
        worlds.CLAIM_CONTENT,
        value=value,
        order_key=order_key,
        authority=authority,
    )


def _disclosure(
    claim: str,
    key: str | None,
    *,
    audience: object = worlds.READER,
    subject: str = "disclosure",
) -> lc.StateRecord:
    return worlds.world_record(
        subject,
        worlds.DISCLOSED_TO,
        object_ref=claim,
        value=audience,
        order_key=key,
        authority=lc.StateAuthority.ACCEPTED_CANON,
        note="An explicit disclosure record.",
    )


@pytest.mark.parametrize(
    ("key", "at", "comparison", "hidden"),
    [
        (None, None, "unpositioned", False),
        (None, "s3", "unpositioned", False),
        ("s2", "s3", "reached", False),
        ("s3", "s3", "reached", False),
        ("s4", "s3", "future", True),
        ("0030", "0040", "reached", False),
        ("0050", "0040", "future", True),
        ("0030", "s3", "incomparable", True),
        ("s3", "0030", "incomparable", True),
        ("chapter-three", "chapter-three", "incomparable", True),
        (" s3 ", "s3", "incomparable", True),
        ("s3", None, "missing_cutoff", True),
    ],
)
def test_each_position_outcome_explains_the_existing_hidden_consumer(
    key: str | None, at: str | None, comparison: str, hidden: bool
) -> None:
    claim = _claim("secret")
    disclosure = _disclosure("secret", key)
    records = (claim, disclosure)

    (row,) = worlds.disclosure_diagnostics(records, at=at)

    assert row.record is claim
    assert row.hidden is hidden
    assert not row.false_claim
    assert row.reason == ("reader_not_disclosed" if hidden else "reader_disclosed")
    assert row.other_disclosures == ()
    (evidence,) = row.reader_disclosures
    assert evidence.record is disclosure
    assert evidence.position == key
    assert evidence.comparison == comparison
    assert (claim in worlds.undisclosed_claims(records, at=at)) is hidden
    assert (claim.record_id in worlds.hidden_record_ids(records, at=at)) is hidden


def test_missing_reader_disclosure_keeps_character_and_blank_audiences_separate() -> None:
    claim = _claim("secret")
    character = _disclosure("secret", None, audience="mara", subject="told-mara")
    blank = _disclosure("secret", "s1", audience="", subject="unknown-audience")
    other_claim = _disclosure("different-secret", None)
    no_object = worlds.world_record("secret", worlds.DISCLOSED_TO, value=worlds.READER)

    (row,) = worlds.disclosure_diagnostics(
        (claim, character, blank, other_claim, no_object), at="s2"
    )

    assert row.hidden
    assert row.reason == "no_reader_disclosure"
    assert row.reader_disclosures == ()
    assert [evidence.record for evidence in row.other_disclosures] == [character, blank]
    assert [evidence.comparison for evidence in row.other_disclosures] == [
        "unpositioned",
        "reached",
    ]
    assert row.other_disclosures[0].record.value == "mara"
    assert row.other_disclosures[1].record.value == ""


def test_reader_audience_uses_existing_trim_rule_and_preserves_original_record() -> None:
    disclosure = _disclosure("secret", "s1", audience=" reader ")

    (row,) = worlds.disclosure_diagnostics((_claim("secret"), disclosure), at="s1")

    assert not row.hidden
    assert row.reader_disclosures[0].record is disclosure
    assert row.reader_disclosures[0].record.value == " reader "
    assert row.reader_disclosures[0].record.note == "An explicit disclosure record."
    assert row.reader_disclosures[0].record.record_id == disclosure.record_id
    assert row.other_disclosures == ()


@pytest.mark.parametrize("flag", [True, False, "true", 1])
def test_only_a_literal_true_false_claim_flag_excludes_hidden_truth(flag: object) -> None:
    claim = _claim("mistake")
    false_flag = worlds.world_record("mistake", worlds.CLAIM_FALSE, value=flag)
    records = (claim, false_flag)

    (row,) = worlds.disclosure_diagnostics(records)

    assert row.false_claim is (flag is True)
    assert row.hidden is (flag is not True)
    assert row.reason == ("false_claim" if flag is True else "no_reader_disclosure")
    assert bool(worlds.undisclosed_claims(records)) is row.hidden


def test_false_claim_keeps_its_disclosure_evidence_without_becoming_hidden_truth() -> None:
    disclosure = _disclosure("mistake", "s9")
    records = (
        _claim("mistake"),
        worlds.world_record("mistake", worlds.CLAIM_FALSE, value=True),
        disclosure,
    )

    (row,) = worlds.disclosure_diagnostics(records, at="s1")

    assert row.false_claim
    assert not row.hidden
    assert row.reason == "false_claim"
    assert row.reader_disclosures[0].record is disclosure
    assert row.reader_disclosures[0].comparison == "future"


def test_one_reached_reader_record_suffices_without_discarding_other_evidence() -> None:
    claim = _claim("secret")
    future = _disclosure("secret", "s9", subject="future")
    incomparable = _disclosure("secret", "0050", subject="schedule")
    reached = _disclosure("secret", "s2", subject="landed")
    records = (claim, future, incomparable, reached)

    (row,) = worlds.disclosure_diagnostics(records, at="s3")

    assert not row.hidden
    assert row.reason == "reader_disclosed"
    assert [evidence.record for evidence in row.reader_disclosures] == [
        future,
        incomparable,
        reached,
    ]
    assert [evidence.comparison for evidence in row.reader_disclosures] == [
        "future",
        "incomparable",
        "reached",
    ]
    assert worlds.undisclosed_claims(records, at="s3") == ()


def test_reveal_intent_and_character_belief_do_not_substitute_for_reader_disclosure() -> None:
    claim = _claim("secret")
    records = (
        claim,
        worlds.world_record("secret", worlds.QUESTION_PREDICATE, value="What happened?"),
        worlds.world_record("secret", worlds.REVEAL_SCENE, value=1),
        worlds.world_record("mara", worlds.BELIEVES, object_ref="secret"),
    )

    (row,) = worlds.disclosure_diagnostics(records, at="s9")

    assert worlds.reveal_scenes(records) == {"secret": 1}
    assert row.hidden
    assert row.reason == "no_reader_disclosure"
    assert row.reader_disclosures == row.other_disclosures == ()
    assert worlds.undisclosed_claims(records, at="s9") == (claim,)


def test_each_nonblank_claim_record_is_reported_in_story_order_without_authority_filter() -> None:
    unplaced = _claim("same", value="One private fact.")
    positioned = _claim("same", value="A second fact.", order_key="s2")
    proposed = _claim("proposal", order_key="s1", authority=lc.StateAuthority.PROPOSED)
    blank = _claim("blank", value="  ")
    records = (unplaced, blank, positioned, proposed)

    rows = worlds.disclosure_diagnostics(records)

    assert tuple(row.record for row in rows) == state.in_story_order(
        (unplaced, positioned, proposed)
    )
    assert all(row.hidden for row in rows)
    assert rows[0].record.authority is lc.StateAuthority.PROPOSED
    assert tuple(row.record for row in rows) == worlds.undisclosed_claims(records)


@pytest.mark.parametrize("at", [None, "s1", "s3", "s9", "0040"])
def test_diagnostic_hidden_rows_match_context_for_the_same_supplied_canon(at: str | None) -> None:
    claims = tuple(
        _claim(subject)
        for subject in ("missing", "open", "scene", "schedule", "character", "mistake")
    )
    records = (
        *claims,
        _disclosure("open", None),
        _disclosure("scene", "s3"),
        _disclosure("schedule", "0040"),
        _disclosure("character", None, audience="mara"),
        worlds.world_record(
            "mistake",
            worlds.CLAIM_FALSE,
            value=True,
            authority=lc.StateAuthority.ACCEPTED_CANON,
        ),
    )
    revision = new_book("book", "branch", title="Disclosure fixture", scenes=1)
    packet = assemble(
        revision,
        "scene-1",
        state_records=records,
        disclosure_at=at,
    )

    diagnostics = worlds.disclosure_diagnostics(records, at=at)

    assert tuple(row.record for row in diagnostics if row.hidden) == worlds.undisclosed_claims(
        records, at=at
    )
    assert {row.record.record_id for row in diagnostics if row.hidden} == {
        item.source_logical_id for item in packet.sections.get(HIDDEN, ())
    }


def test_a_diagnostic_is_not_a_claim_that_a_packet_contains_a_proposed_record() -> None:
    proposed = _claim("proposal", authority=lc.StateAuthority.PROPOSED)
    revision = new_book("book", "branch", title="Disclosure fixture", scenes=1)

    (row,) = worlds.disclosure_diagnostics((proposed,), at="s1")
    packet = assemble(revision, "scene-1", state_records=(proposed,), disclosure_at="s1")

    assert row.hidden
    assert row.record.authority is lc.StateAuthority.PROPOSED
    assert packet.sections.get(HIDDEN, ()) == ()


def test_empty_input_has_no_diagnostic_rows() -> None:
    assert worlds.disclosure_diagnostics(()) == ()
