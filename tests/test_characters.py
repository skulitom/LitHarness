"""Character sheets expose explicit causes without inferring motives from wants."""

from __future__ import annotations

import litharness_contracts as lc

from litharness.domain.characters import sheet


def _record(
    record_id: str,
    subject: str,
    predicate: str,
    *,
    value: str | None = None,
    object_ref: str | None = None,
    evidenced: bool = False,
) -> lc.StateRecord:
    evidence = []
    if evidenced:
        evidence.append(
            lc.EvidenceSpan(
                source=lc.ResourceRef(
                    project_id="project-test",
                    book_id="book-test",
                    branch_id="main",
                    logical_id="scene-1",
                    kind=lc.ResourceKind.MANUSCRIPT_SCENE,
                ),
                start=0,
                end=4,
                content_sha256="digest",
            )
        )
    return lc.StateRecord(
        record_id=record_id,
        kind=lc.StateRecordKind.RELATIONSHIP,
        subject=subject,
        predicate=predicate,
        value=value,
        object_ref=object_ref,
        authority=lc.StateAuthority.ACCEPTED_CANON,
        evidence=evidence,
    )


def test_explicit_reified_character_causes_reach_the_sheet_with_evidence_status() -> None:
    records = [
        _record("role", "rook", "entity_role", value="protagonist"),
        _record("want", "rook", "wants", value="clear the debt"),
        _record("actor", "change-1", "actor", object_ref="rook", evidenced=True),
        _record("cause", "change-1", "caused_by", object_ref="goal-clear-debt", evidenced=True),
        _record("effect", "change-1", "effect", object_ref="gate-open", evidenced=True),
    ]

    character = sheet(records, "rook")

    assert character.wants == "clear the debt"
    assert len(character.causes) == 1
    assert character.causes[0].motives == ("goal-clear-debt",)
    assert character.causes[0].effects == ("gate-open",)
    assert character.causes[0].evidence_complete
    assert "span-backed" in character.render()


def test_a_free_text_want_is_not_inferred_to_have_caused_any_action() -> None:
    character = sheet([_record("want", "rook", "wants", value="clear the debt")], "rook")

    assert character.causes == ()
