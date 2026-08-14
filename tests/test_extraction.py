"""§12 step 5: state read back out of accepted prose.

The test worth reading first is `test_a_contradiction_fires_the_detector_and_a_repair_silences_it`.
Everything else here protects a property; that one establishes the point of the module —
before it, `state.contradiction.v0` had no in-process producer and could not fire at all, so
Stage 2's "repairs triggered by findings" had nothing to trigger on.

The second is `test_the_obvious_order_key_scheme_is_wrong_and_here_is_the_measurement`, which
exists because the tempting implementation is one line and this one is forty.
"""

from __future__ import annotations

import json

import litharness_contracts as lc
import pytest

from litharness.adapters.contracts_fixtures import fixture_manuscript, fixture_state
from litharness.domain.extraction import (
    STATUS_FIELDS,
    STATUS_PATTERN,
    STATUS_PREDICATE,
    attested_position,
    extract_state,
    normalise_subject,
    record_id_for,
    render_status_line,
    speaks_system_voice,
    stated_position,
)
from litharness.domain.findings import DetectorInput, Severity
from litharness.domain.integrity import detect_contradictions
from litharness.domain.text import content_hash


def state_of(fixture_id: str) -> lc.StateSnapshot:
    return lc.parse_artifact(
        lc.StateSnapshot, json.loads(fixture_state(fixture_id).read_text(encoding="utf-8"))
    )


def scenes_of(fixture_id: str) -> dict[str, str]:
    manuscript = json.loads(fixture_manuscript(fixture_id).read_text(encoding="utf-8"))
    return {
        node["logical_id"]: node.get("content") or ""
        for node in manuscript["nodes"]
        if node["logical_id"].startswith("scene-")
    }


def extract(fixture_id: str, logical_id: str, text: str, known=None):
    return extract_state(
        text,
        known=known if known is not None else state_of(fixture_id).records,
        project_id="p",
        book_id="b",
        branch_id="br",
        logical_id=logical_id,
        version_id="v",
    )


# -- the order key, which is the sharpest constraint -----------------------------------


def test_the_position_is_read_out_of_the_book_not_computed() -> None:
    """`domain/state.py` forbids deriving an order key from a scene, so this reads the answer
    the book's own imported evidence already gives."""
    records = state_of("litrpg").records
    assert {f"scene-{i}": attested_position(records, f"scene-{i}") for i in range(1, 7)} == {
        "scene-1": "s1", "scene-2": "s2", "scene-3": "s3",
        "scene-4": "s4", "scene-5": "s5", "scene-6": "s6",
    }


def test_an_ambiguous_or_unattested_scene_abstains() -> None:
    """The mystery is the book that settles this. Scene 2 is cited by records at both `s1`
    and `s2`; scene 6 is cited by none. Choosing for either would be inventing exactly the
    mapping this module refuses to invent."""
    records = state_of("mystery").records
    assert attested_position(records, "scene-2") is None, "ambiguous"
    assert attested_position(records, "scene-6") is None, "unattested"
    assert attested_position(records, "scene-5") == "s1", "the analepsis is honoured, not fixed"


def test_the_obvious_order_key_scheme_is_wrong_and_here_is_the_measurement() -> None:
    """`f"s{ordinal}"` is one line and reproduces the litrpg fixture perfectly, which is what
    makes it dangerous: it is right on one of the two books in the project and wrong on the
    one whose genre guarantees it. A scheme that passes your test book and silently
    mis-slices the next is worse than abstention, and this is the assertion that stops it
    being re-proposed."""
    records = state_of("mystery").records
    derived = {f"scene-{i}": f"s{i}" for i in range(1, 7)}
    attested = {f"scene-{i}": attested_position(records, f"scene-{i}") for i in range(1, 7)}
    disagreements = {k for k, v in attested.items() if v is not None and v != derived[k]}
    assert "scene-5" in disagreements, "scene 5 is an analepsis attested at s1, not s5"


def test_an_unattested_scene_extracts_nothing_rather_than_extracting_unplaced() -> None:
    """`detect_contradictions` groups on `order_key or ""`, so an unplaced record shares one
    bucket with every other unplaced record — the coarsest possible collision scheme."""
    text = "[STATUS] Mara — Level 1 | HP 10/10 | MP 1/1 | Gold 0"
    assert extract("mystery", "scene-6", text) == ()


# -- parity with the fixture the project did not author for this ------------------------


def test_extraction_reproduces_the_fixtures_own_records_exactly() -> None:
    """Value, span offsets and content hash, against `state.json` — an artifact written long
    before this module and not for it. `known` deliberately excludes the status records so
    the suppression rule does not hide the comparison."""
    snapshot = state_of("litrpg")
    authored = {record.record_id: record for record in snapshot.records}
    others = [r for r in snapshot.records if r.predicate != STATUS_PREDICATE]
    scenes = scenes_of("litrpg")

    for index in range(1, 7):
        logical_id = f"scene-{index}"
        [got] = extract("litrpg", logical_id, scenes[logical_id], known=others)
        want = authored[f"rec-s{index}-status"]
        assert got.value == want.value, logical_id
        assert (got.evidence[0].start, got.evidence[0].end) == (
            want.evidence[0].start, want.evidence[0].end
        ), logical_id
        assert got.evidence[0].content_sha256 == want.evidence[0].content_sha256, logical_id


def test_repair_reextracts_an_unchanged_fact_against_the_new_node_version() -> None:
    others = [
        record
        for record in state_of("litrpg").records
        if record.predicate != STATUS_PREDICATE
    ]
    text = scenes_of("litrpg")["scene-1"]
    [first] = extract("litrpg", "scene-1", text, known=others)

    [reanchored] = extract_state(
        text,
        known=(*others, first),
        project_id="p",
        book_id="b",
        branch_id="br",
        logical_id="scene-1",
        version_id="v-after-repair",
        replacing_logical_id="scene-1",
    )

    assert reanchored.record_id == first.record_id
    assert reanchored.evidence[0].source.version_id == "v-after-repair"


def test_a_planted_defect_survives_extraction_uncorrected() -> None:
    """The litrpg fixture's scene 4 reads `HP 34/30` because §8.3 planted `f-hp-over-max`
    there. An extractor that reconciled values against canon would sanitise the detector's
    own input on the way in."""
    others = [r for r in state_of("litrpg").records if r.predicate != STATUS_PREDICATE]
    [record] = extract("litrpg", "scene-4", scenes_of("litrpg")["scene-4"], known=others)
    assert record.value["hp"] == 34
    assert record.value["hp_max"] == 30


# -- the fixtures stay silent -----------------------------------------------------------


@pytest.mark.parametrize("fixture_id", ["litrpg", "mystery"])
def test_a_conforming_fixture_extracts_nothing(fixture_id: str) -> None:
    """Both legs of §8.3's negative control. The litrpg book's facts are already canon at
    those positions, so the suppression rule drops them; the mystery book has no system voice
    at all. A check that fires on a conforming book is not a floor, it is a tax."""
    records = state_of(fixture_id).records
    assert sum(
        len(extract(fixture_id, logical_id, text))
        for logical_id, text in scenes_of(fixture_id).items()
    ) == 0
    assert detect_contradictions(
        DetectorInput(book_id="b", branch_id="br", logical_id="scene-1", records=tuple(records))
    ) == []


# -- the point of the module ------------------------------------------------------------


def test_a_contradiction_fires_the_detector_and_a_repair_silences_it() -> None:
    """§8.3's mutation leg, over the loop this module closes.

    Before extraction existed the detector had no in-process producer — nothing in `src/`
    constructed a `StateRecord` — so it emitted zero findings on every input and its silence
    proved nothing. Perturb the prose and it fires; restore it and it goes quiet.
    """
    records = tuple(state_of("litrpg").records)
    pristine = scenes_of("litrpg")["scene-4"]
    mutated = pristine.replace("Gold 15", "Gold 14")
    assert mutated != pristine, "the fixture must still contain the line this perturbs"

    def findings_for(text: str):
        extracted = extract("litrpg", "scene-4", text)
        return detect_contradictions(
            DetectorInput(
                book_id="b", branch_id="br", logical_id="scene-4",
                candidate=text, records=records + extracted,
            )
        )

    assert findings_for(pristine) == []
    [finding] = findings_for(mutated)
    assert finding.severity is Severity.MAJOR
    assert "status position s4" in finding.message or "position s4" in finding.message
    assert findings_for(mutated.replace("Gold 14", "Gold 15")) == []


# -- ids, suppression, minting ----------------------------------------------------------


def test_the_record_id_is_value_sensitive_so_a_contradiction_is_a_second_row() -> None:
    """Keying on `(subject, predicate, order_key)` alone would make the detector permanently
    unreachable: `record_state_records` is INSERT OR IGNORE, so a contradicting record would
    collide with the one it contradicts, insert nothing, and report success."""
    base = {"level": 3, "hp": 24, "hp_max": 30, "mp": 8, "mp_max": 10, "gold": 45}
    other = {**base, "gold": 44}
    assert record_id_for("rook", STATUS_PREDICATE, "s1", base) == record_id_for(
        "rook", STATUS_PREDICATE, "s1", dict(reversed(list(base.items())))
    ), "key order is not identity"
    assert record_id_for("rook", STATUS_PREDICATE, "s1", base) != record_id_for(
        "rook", STATUS_PREDICATE, "s1", other
    )


def test_a_subject_canon_has_never_heard_of_is_not_extracted() -> None:
    """A new name is a claim about someone the book has not established, which is a proposal
    rather than a reading of what it already said."""
    text = "[STATUS] Someone Else — Level 3 | HP 24/30 | MP 8/10 | Gold 45"
    assert extract("litrpg", "scene-1", text) == ()


def test_prose_that_merely_mentions_a_bracket_is_not_system_voice() -> None:
    others = [r for r in state_of("litrpg").records if r.predicate != STATUS_PREDICATE]
    text = 'He read it aloud: "[STATUS] Rook — Level 9 | HP 1/1 | MP 1/1 | Gold 999".'
    assert extract("litrpg", "scene-1", text, known=others) == ()


def test_the_span_resolves_against_the_text_it_was_read_from() -> None:
    others = [r for r in state_of("litrpg").records if r.predicate != STATUS_PREDICATE]
    text = scenes_of("litrpg")["scene-1"]
    [record] = extract("litrpg", "scene-1", text, known=others)
    span = record.evidence[0]
    assert content_hash(text[span.start : span.end]) == span.content_sha256
    assert text[span.start : span.end].startswith("[STATUS]")


def test_the_subject_id_is_normalised_not_invented() -> None:
    assert normalise_subject("  Rook  ") == "rook"
    assert normalise_subject("Mara Vane") == "mara_vane"


# -- a book with no vocabulary of its own ----------------------------------------------


def test_a_book_with_no_snapshot_extracts_nothing_until_the_plan_says_where() -> None:
    """Book Zero, stated as the defect it is. A book this system wrote entirely itself has no
    imported record to attest a position, so every scene is unplaceable and §12 step 5
    extracts nothing from it — forever, and silently, because a scene with no extractable
    state looks exactly like one that established none."""
    canon = (
        lc.StateRecord(
            record_id="rec-rook",
            kind=lc.StateRecordKind.ASSERTION,
            subject="rook",
            predicate="life_status",
            value="alive",
            authority=lc.StateAuthority.ACCEPTED_CANON,
        ),
    )
    text = "[STATUS] Rook — Level 3 | HP 24/30 | MP 8/10 | Gold 45"

    assert extract("litrpg", "scene-1", text, known=canon) == ()

    [record] = extract_state(
        text,
        known=canon,
        project_id="p",
        book_id="b",
        branch_id="br",
        logical_id="scene-1",
        version_id="v",
        stated_order_key="s1",
    )
    assert record.story_position.order_key == "s1"
    assert record.value["gold"] == 45


def test_the_plans_answer_is_refused_where_the_book_has_its_own_vocabulary() -> None:
    """The guard that keeps this from being the refuted scheme. The mystery has records at
    `s1` and `s2` and abstains on scene 2 — filling that gap with the plan's `s2` would insert
    a record into the middle of somebody else's numbering, which is worse than abstaining and
    is exactly what `attested_position` refuses to do."""
    known = state_of("mystery").records
    assert attested_position(known, "scene-2") is None

    assert stated_position(known, "s2") is None
    assert (
        extract(
            "mystery",
            "scene-2",
            "[STATUS] Mara — Level 1 | HP 10/10 | MP 1/1 | Gold 0",
            known=known,
        )
        == ()
    )


def test_the_book_wins_wherever_it_has_spoken() -> None:
    """An attested position is read first, so a stated one can never override the book — it
    fills silence and nothing else. The litrpg fixture attests `s4` for scene 4; a plan
    claiming `s9` must not move it."""
    known = state_of("litrpg").records
    others = [record for record in known if record.predicate != STATUS_PREDICATE]

    [record] = extract_state(
        scenes_of("litrpg")["scene-4"],
        known=others,
        project_id="p",
        book_id="b",
        branch_id="br",
        logical_id="scene-4",
        version_id="v",
        stated_order_key="s9",
    )

    assert record.story_position.order_key == "s4"


def test_a_record_says_whether_the_book_or_the_plan_placed_it() -> None:
    """Different provenance, and an audit that could not tell them apart would be worth less
    than one that said nothing. `litharness verify` and every later reader can see which
    records rest on the plan's word."""
    canon = (
        lc.StateRecord(
            record_id="rec-rook",
            kind=lc.StateRecordKind.ASSERTION,
            subject="rook",
            predicate="life_status",
            value="alive",
            authority=lc.StateAuthority.ACCEPTED_CANON,
        ),
    )
    [minted] = extract_state(
        "[STATUS] Rook — Level 3 | HP 24/30 | MP 8/10 | Gold 45",
        known=canon,
        project_id="p",
        book_id="b",
        branch_id="br",
        logical_id="scene-1",
        version_id="v",
        stated_order_key="s1",
    )
    others = [r for r in state_of("litrpg").records if r.predicate != STATUS_PREDICATE]
    [attested] = extract("litrpg", "scene-1", scenes_of("litrpg")["scene-1"], known=others)

    assert minted.note and "stated by the plan" in minted.note
    assert attested.note is None


# -- asking for what this module can actually read -------------------------------------


def test_the_shape_the_prompt_asks_for_is_the_shape_the_parser_accepts() -> None:
    """The test that makes the instruction safe to write, and the failure it rules out is
    silent: a prompt asking for a form `STATUS_PATTERN` does not match produces prose that
    reads correctly to a human and extracts nothing — and a scene establishing no state is
    indistinguishable from a scene whose state nobody could read. No gate catches that.

    So the template is filled in and parsed back rather than eyeballed against the regex.
    """
    line = render_status_line(
        "Rook", {"level": 4, "hp": 27, "hp_max": 34, "mp": 6, "mp_max": 10, "gold": 33}
    )
    match = STATUS_PATTERN.search(line)

    assert match is not None, f"the extractor cannot read the line it asks for: {line!r}"
    assert match.group("subject") == "Rook"
    assert [match.group(field) for field in STATUS_FIELDS] == ["4", "27", "34", "6", "10", "33"]


def test_a_rendered_line_round_trips_through_extraction_itself() -> None:
    """One step further than the regex: the whole extractor, against canon that names the
    subject, must produce a record whose value is the one the line was rendered from."""
    known = state_of("litrpg").records
    value = {"level": 4, "hp": 27, "hp_max": 34, "mp": 6, "mp_max": 10, "gold": 33}
    text = f"He caught his breath.\n\n{render_status_line('Rook', value)}\n"

    [extracted] = extract("litrpg", "scene-4", text, known=known)

    assert extracted.value == value
    assert extracted.subject == "rook"
    assert extracted.predicate == STATUS_PREDICATE


def test_a_book_that_states_its_game_state_is_recognised_from_its_own_canon() -> None:
    """Read out of the records rather than declared by a genre flag, for the reason the order
    key is read rather than derived: a flag is a second source of truth for something the
    records already answer, and the two eventually disagree."""
    assert speaks_system_voice(state_of("litrpg").records)
    assert not speaks_system_voice(state_of("mystery").records)


def test_a_proposed_status_record_does_not_make_a_book_speak_system_voice() -> None:
    """Canon only. A proposal is something the book has been *offered*, and drafting against
    it would let an unaccepted record change how every later scene is written."""
    proposed = lc.StateRecord(
        record_id="rec-proposed",
        kind=lc.StateRecordKind.ASSERTION,
        subject="rook",
        predicate=STATUS_PREDICATE,
        value={"gold": 1},
        authority=lc.StateAuthority.PROPOSED,
    )

    assert not speaks_system_voice([proposed])
