"""§12 step 5: state read back out of accepted prose.

The test worth reading first is `test_a_contradiction_fires_the_detector_and_a_repair_silences_it`.
Everything else here protects a property; that one establishes the point of the module —
before it, `state.contradiction.v0` had no in-process producer and could not fire at all, so
Stage 2's "repairs triggered by findings" had nothing to trigger on.

The second is `test_the_obvious_order_key_scheme_is_wrong_and_here_is_the_measurement`, which
exists because the tempting implementation is one line and this one is forty.
"""

from __future__ import annotations

import dataclasses
import json

import litharness_contracts as lc
import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from litharness.adapters.contracts_fixtures import fixture_manuscript, fixture_state
from litharness.domain import worlds
from litharness.domain.extraction import (
    MAX_SUFFIX,
    SHEET_PREDICATE,
    STATUS_PREDICATE,
    MalformedSheet,
    Sheet,
    SheetField,
    attested_position,
    counted_names,
    display_name,
    extract_graph_facts,
    extract_state,
    graph_line_for,
    normalise_subject,
    parse_sheet,
    record_id_for,
    render_status_line,
    sheet_for,
    speaks_system_voice,
    standing_target,
    stated_position,
)
from litharness.domain.findings import DetectorInput, Severity
from litharness.domain.integrity import detect_contradictions
from litharness.domain.text import content_hash
from tests.conftest import FIXTURE_SHEET
from tests.helpers import canon as _canon


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
    """The status records read out of `text`. Since §205 an undeclared book's first line also
    mints its sheet declaration; these tests read the snapshot, so the helper filters."""
    return _statuses(
        extract_state(
            text,
            known=known if known is not None else state_of(fixture_id).records,
            project_id="p",
            book_id="b",
            branch_id="br",
            logical_id=logical_id,
            version_id="v",
        )
    )


def _statuses(records):
    """The status records only: since §205 an undeclared book's first line also mints its
    sheet declaration, and these tests read the snapshot."""
    return tuple(record for record in records if record.predicate == STATUS_PREDICATE)


# -- the order key, which is the sharpest constraint -----------------------------------


def test_the_position_is_read_out_of_the_book_not_computed() -> None:
    """`domain/state.py` forbids deriving an order key from a scene, so this reads the answer
    the book's own imported evidence already gives."""
    records = state_of("litrpg").records
    assert {f"scene-{i}": attested_position(records, f"scene-{i}") for i in range(1, 7)} == {
        "scene-1": "s1",
        "scene-2": "s2",
        "scene-3": "s3",
        "scene-4": "s4",
        "scene-5": "s5",
        "scene-6": "s6",
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
            want.evidence[0].start,
            want.evidence[0].end,
        ), logical_id
        assert got.evidence[0].content_sha256 == want.evidence[0].content_sha256, logical_id


def test_repair_reextracts_an_unchanged_fact_against_the_new_node_version() -> None:
    others = [
        record for record in state_of("litrpg").records if record.predicate != STATUS_PREDICATE
    ]
    text = scenes_of("litrpg")["scene-1"]
    [first] = extract("litrpg", "scene-1", text, known=others)

    [reanchored] = _statuses(
        extract_state(
            text,
            known=(*others, first),
            project_id="p",
            book_id="b",
            branch_id="br",
            logical_id="scene-1",
            version_id="v-after-repair",
            replacing_logical_id="scene-1",
        )
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
    assert (
        sum(
            len(extract(fixture_id, logical_id, text))
            for logical_id, text in scenes_of(fixture_id).items()
        )
        == 0
    )
    assert (
        detect_contradictions(
            DetectorInput(book_id="b", branch_id="br", logical_id="scene-1", records=tuple(records))
        )
        == []
    )


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
                book_id="b",
                branch_id="br",
                logical_id="scene-4",
                candidate=text,
                records=records + extracted,
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

    [record] = _statuses(
        extract_state(
            text,
            known=canon,
            project_id="p",
            book_id="b",
            branch_id="br",
            logical_id="scene-1",
            version_id="v",
            stated_order_key="s1",
        )
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

    [record] = _statuses(
        extract_state(
            scenes_of("litrpg")["scene-4"],
            known=others,
            project_id="p",
            book_id="b",
            branch_id="br",
            logical_id="scene-4",
            version_id="v",
            stated_order_key="s9",
        )
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
    [minted] = _statuses(
        extract_state(
            "[STATUS] Rook — Level 3 | HP 24/30 | MP 8/10 | Gold 45",
            known=canon,
            project_id="p",
            book_id="b",
            branch_id="br",
            logical_id="scene-1",
            version_id="v",
            stated_order_key="s1",
        )
    )
    others = [r for r in state_of("litrpg").records if r.predicate != STATUS_PREDICATE]
    [attested] = extract("litrpg", "scene-1", scenes_of("litrpg")["scene-1"], known=others)

    assert minted.note and "stated by the plan" in minted.note
    assert attested.note is None


# -- asking for what this module can actually read -------------------------------------


def test_the_shape_the_prompt_asks_for_is_the_shape_the_parser_accepts() -> None:
    """The test that makes the instruction safe to write, and the failure it rules out is
    silent: a prompt asking for a form the line's own pattern does not match produces prose that
    reads correctly to a human and extracts nothing — and a scene establishing no state is
    indistinguishable from a scene whose state nobody could read. No gate catches that.

    So the template is filled in and parsed back rather than eyeballed against the regex.
    """
    line = render_status_line(
        "Rook", {"level": 4, "hp": 27, "hp_max": 34, "mp": 6, "mp_max": 10, "gold": 33}
    )
    match = FIXTURE_SHEET.pattern.search(line)

    assert match is not None, f"the extractor cannot read the line it asks for: {line!r}"
    assert match.group("subject") == "Rook"
    assert [match.group(field) for field in FIXTURE_SHEET.value_keys] == [
        "4",
        "27",
        "34",
        "6",
        "10",
        "33",
    ]


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


# -- the sheet a book declares for itself ----------------------------------------------


def _sheet_record(fields: list[dict[str, object]]) -> lc.StateRecord:
    return lc.StateRecord(
        record_id="rec-sheet",
        kind=lc.StateRecordKind.WORLD_RULE,
        subject="silas",
        predicate=SHEET_PREDICATE,
        value={"fields": fields},
        authority=lc.StateAuthority.ACCEPTED_CANON,
        pov_visibility=[],
        evidence=[],
    )


def _subject_record() -> lc.StateRecord:
    return lc.StateRecord(
        record_id="rec-silas",
        kind=lc.StateRecordKind.ASSERTION,
        subject="silas",
        predicate="is_a",
        value="an appraiser",
        authority=lc.StateAuthority.ACCEPTED_CANON,
        pov_visibility=[],
        evidence=[],
    )


_NAMES = st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=8)
_LABELS = st.text(
    alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz", min_size=1, max_size=8
)


@given(
    st.lists(
        st.tuples(_NAMES, _LABELS, st.booleans()),
        min_size=1,
        max_size=5,
        unique_by=(
            lambda item: item[0],
            lambda item: item[1],
        ),
    ),
    st.data(),
)
def test_a_declared_sheet_round_trips(fields, data) -> None:
    """The property the two literals used to hold by hand.

    the line's own template and the line's own pattern were separate strings a human had to keep in
    agreement, and the failure when they drift is silent: a prompt asking for a form the parser
    does not accept yields prose that reads correctly and extracts nothing. Deriving both from
    one field list turns that from a discipline into a property, so this asserts it for *any*
    sheet rather than for the one that happened to be written down.
    """
    keys = [name for name, _, _ in fields]
    keys += [f"{name}{MAX_SUFFIX}" for name, _, paired in fields if paired]
    assume(len(set(keys)) == len(keys))
    sheet = Sheet(tuple(SheetField(name, label, paired) for name, label, paired in fields))
    value = {key: data.draw(st.integers(min_value=0, max_value=9999)) for key in sheet.value_keys}

    line = render_status_line("Silas", value, sheet=sheet)
    match = sheet.pattern.search(line)

    assert match is not None, f"the extractor cannot read the line it asks for: {line!r}"
    assert match.group("subject") == "Silas"
    assert {key: int(match.group(key)) for key in sheet.value_keys} == value


def test_the_default_sheet_reproduces_the_line_this_module_shipped_with() -> None:
    """Both golden fixtures and every store already on disk declare no sheet, so the default
    has to be the old constants exactly — untouched by construction rather than by a
    compatibility branch."""
    assert FIXTURE_SHEET.template == (
        "[STATUS] {subject} — Level {level} | HP {hp}/{hp_max} | MP {mp}/{mp_max} | Gold {gold}"
    )
    assert FIXTURE_SHEET.value_keys == ("level", "hp", "hp_max", "mp", "mp_max", "gold")
    assert sheet_for(state_of("litrpg").records) == FIXTURE_SHEET


def test_a_book_reads_the_sheet_it_declared_and_not_the_default_one() -> None:
    """A book whose progression is a loop counter and a day is read in *its* vocabulary. The
    defect this rules out is the one that has no symptom: the default pattern would match none
    of its lines, so every scene would extract nothing and look like a scene that established
    nothing."""
    known = [
        _subject_record(),
        _sheet_record([{"name": "loop", "label": "Loop"}, {"name": "day", "label": "Day"}]),
    ]
    sheet = sheet_for(known)
    line = render_status_line("Silas", {"loop": 2, "day": 1}, sheet=sheet)

    extracted = extract_state(
        f"He woke on the same morning.\n\n{line}\n",
        known=known,
        project_id="p",
        book_id="b",
        branch_id="br",
        logical_id="s1",
        version_id="v",
        stated_order_key="s1",
    )

    assert line == "[STATUS] Silas — Loop 2 | Day 1"
    assert [(r.subject, r.value) for r in extracted] == [("silas", {"loop": 2, "day": 1})]
    assert FIXTURE_SHEET.pattern.search(line) is None, "the default line must not read this book"


def test_two_sheet_declarations_fall_back_to_the_columns_the_snapshots_hold() -> None:
    """Two declarations are the book disagreeing with itself about its own vocabulary, and
    picking either would be this module choosing which of the author's answers is real — the
    same abstention `attested_position` makes. Since §205 the abstention is to the book's own
    snapshots (as an undeclared book reads), and to no line at all where there are none."""
    first = _sheet_record([{"name": "loop", "label": "Loop"}])
    second = lc.StateRecord(
        record_id="rec-sheet-2",
        kind=lc.StateRecordKind.WORLD_RULE,
        subject="silas",
        predicate=SHEET_PREDICATE,
        value={"fields": [{"name": "day", "label": "Day"}]},
        authority=lc.StateAuthority.ACCEPTED_CANON,
        pov_visibility=[],
        evidence=[],
    )

    assert sheet_for([first, second]) is None, "no snapshot, no line"
    held = worlds.world_record(
        "silas",
        STATUS_PREDICATE,
        value={"loop": 2, "day": 1},
        authority=lc.StateAuthority.ACCEPTED_CANON,
    )
    fallback = sheet_for([first, second, held])
    assert fallback is not None and fallback.value_keys == ("loop", "day")


@pytest.mark.parametrize(
    "value",
    [
        "Loop and Day",
        {},
        {"fields": []},
        {"fields": [{"label": "Loop"}]},
        {"fields": [{"name": "1loop", "label": "Loop"}]},
        {"fields": [{"name": "loop", "label": "  "}]},
        {
            "fields": [
                {"name": "hp", "label": "HP", "paired": True},
                {"name": "hp_max", "label": "Cap"},
            ]
        },
    ],
)
def test_a_malformed_sheet_declaration_is_refused_rather_than_defaulted(value) -> None:
    """Silently falling back would ask every scene for a form the book's own canon does not
    use. `cmd_new` calls this on the seed, so the refusal lands before the book exists."""
    with pytest.raises(MalformedSheet):
        parse_sheet(value)


# --- the number comes off the page (plan/stage-0-decisions.md §113) ---------------------------


def _ladder_world() -> list[lc.StateRecord]:
    """A three-rung ordinal chain, a graph line that prints a change on it, and a standing."""
    return [
        _canon("assay_grade", worlds.TYPE_PREDICATE, value=worlds.CRITERION),
        _canon("assay_grade", worlds.COMPARATOR_PREDICATE, value="ordinal"),
        *[
            _canon(rung, worlds.MANIFESTS_PREDICATE, value=form)
            for rung, form in (
                ("third_seal", "a lead seal that greens in a week"),
                ("second_seal", "a brass seal worn at the throat"),
                ("first_seal", "a silver seal nobody hands back"),
            )
        ],
        *[
            _canon(
                lower,
                worlds.PRECEDES_PREDICATE,
                object_ref=higher,
                value="assay_grade",
            )
            for lower, higher in (
                ("third_seal", "second_seal"),
                ("second_seal", "first_seal"),
            )
        ],
        _canon("silas", worlds.ENTITY_ROLE_PREDICATE, value="protagonist"),
        _canon(
            "silas",
            worlds.STANDS_AT_PREDICATE,
            object_ref="third_seal",
            value="assay_grade",
            order_key="s1",
        ),
        _canon(
            "book",
            worlds.GRAPH_LINE_PREDICATE,
            value={
                "label": "ASSAY",
                "edges": [
                    {"phrase": "now stands at", "predicate": worlds.STANDS_AT_PREDICATE},
                    {"phrase": "is bonded to", "predicate": "bonded_to"},
                ],
            },
        ),
    ]


def _read(text: str, known, order_key: str = "s3"):  # type: ignore[no-untyped-def]
    return extract_graph_facts(
        text,
        known=known,
        project_id="p",
        book_id="b",
        branch_id="br",
        logical_id="scene-3",
        version_id="v1",
        order_key=order_key,
    )


def test_a_printed_rung_on_a_declared_ladder_is_canon_at_that_position() -> None:
    """**The book's own statement, the same class as a `[STATUS]` line.**

    Nothing is minted: the subject is one canon already uses, the rung is a declared rank of a
    declared chain, and the criterion is derived from which chain holds it. No model returned
    it — a recorded policy decision accepted the prose and this is a mechanical restatement.
    """
    known = _ladder_world()
    [read] = _read("[ASSAY] silas now stands at second_seal", known)

    assert read.authority is lc.StateAuthority.ACCEPTED_CANON
    assert read.predicate == worlds.STANDS_AT_PREDICATE
    assert read.object_ref == "second_seal"
    # The criterion rides on the edge, so two ladders in one world cannot be spliced — and the
    # page never printed it, because a reader knows which ladder a rung is on.
    assert read.value == "assay_grade"
    assert read.evidence, "canon read off prose carries the span it was read from"

    after = [*known, read]
    assert worlds.standing_of(after, "silas") == {"assay_grade": "second_seal"}
    assert worlds.rung_index(after, "assay_grade", "second_seal") == 2
    # And it reads as a sentence with its number when the packet renders it.
    assert worlds.project(after)[read.record_id] == "silas stands at second_seal (2 of 3)"


def test_a_rung_the_page_minted_stays_a_proposal() -> None:
    """The general case, unchanged: identity minting and factual promotion stay separate."""
    known = _ladder_world()
    [minted] = _read("[ASSAY] silas now stands at platinum_seal", known)
    assert minted.authority is lc.StateAuthority.PROPOSED
    assert minted.value is None
    assert "a proposal until the book uses it again" in (minted.note or "")

    # A subject canon has never heard of, on a declared rung, is also a proposal: the exception
    # needs both halves.
    [stranger] = _read("[ASSAY] kell now stands at second_seal", known)
    assert stranger.authority is lc.StateAuthority.PROPOSED

    # And a declared rung under some other predicate is untouched by any of this.
    [other] = _read("[ASSAY] silas is bonded to second_seal", known)
    assert other.authority is lc.StateAuthority.PROPOSED


def test_a_scheduled_standing_does_not_suppress_the_printed_one() -> None:
    """The plan and the page are different claims, and only the page makes the rise true.

    `seen` counts proposals as well as canon because repetition adds nothing — but the
    outline's rung schedule is a `PROPOSED` `stands_at` edge at a future position, so counting
    it would mean the one scene that printed the rise read nothing.
    """
    scheduled = lc.StateRecord(
        record_id="standing-s3",
        kind=lc.StateRecordKind.RELATIONSHIP,
        subject="silas",
        predicate=worlds.STANDS_AT_PREDICATE,
        value="assay_grade",
        object_ref="second_seal",
        authority=lc.StateAuthority.PROPOSED,
        story_position=lc.StoryPosition(order_key="s3"),
    )
    known = [*_ladder_world(), scheduled]
    [read] = _read("[ASSAY] silas now stands at second_seal", known)
    assert read.authority is lc.StateAuthority.ACCEPTED_CANON

    # Once it *is* canon, printing it again adds nothing — the rule the `seen` set exists for.
    assert _read("[ASSAY] silas now stands at second_seal", [*known, read], "s4") == ()


def test_the_standing_target_aims_from_where_the_book_actually_is() -> None:
    """Canon read off the page moves the origin, which is why the schedule is aimed rather than
    replayed: a book that reached second_seal at s3 is aimed at first_seal, not at second."""
    schedule = [
        lc.StateRecord(
            record_id=f"standing-{key}",
            kind=lc.StateRecordKind.RELATIONSHIP,
            subject="silas",
            predicate=worlds.STANDS_AT_PREDICATE,
            value="assay_grade",
            object_ref=rung,
            authority=lc.StateAuthority.PROPOSED,
            story_position=lc.StoryPosition(order_key=key),
        )
        for key, rung in (("s3", "second_seal"), ("s5", "first_seal"))
    ]
    known = [*_ladder_world(), *schedule]
    assert "second_seal (2 of 3)" in (standing_target(known, at="s2") or "")

    [read] = _read("[ASSAY] silas now stands at second_seal", known)
    after = [*known, read]
    aimed = standing_target(after, at="s4") or ""
    assert "silas stands at second_seal (2 of 3)" in aimed
    assert "the book's plan has them at first_seal (3 of 3)" in aimed


def test_the_golden_fixtures_extract_exactly_what_they_extracted_before() -> None:
    """Absence is free, and it is asserted rather than intended. Neither fixture declares a
    graph line, so neither reads one — before this change or after it."""
    for fixture_id in ("litrpg", "mystery"):
        known = list(state_of(fixture_id).records)
        assert graph_line_for(known) is None
        for logical_id, text in scenes_of(fixture_id).items():
            assert (
                extract_graph_facts(
                    text,
                    known=known,
                    project_id="p",
                    book_id="b",
                    branch_id="br",
                    logical_id=logical_id,
                    version_id="v1",
                    order_key="s01",
                )
                == ()
            )


# -- §203: the line is a declared projection of the snapshot -----------------------------


def _held_sheet(show_unheld: bool) -> Sheet:
    return Sheet(
        (
            SheetField("rank", "Band"),
            SheetField("pace", "Pace"),
            SheetField("weight", "Weight"),
            SheetField("carry", "Carry", paired=True),
        ),
        show_unheld=show_unheld,
    )


def test_a_sheet_that_hides_unheld_prints_the_first_column_and_the_held_ones() -> None:
    """§203: six zeros on an eight-field row was a shape the market's windows do not have
    (one field in fifteen at zero); the first column always prints so a rung stays."""
    value = {"rank": 1, "pace": 2, "weight": 0, "carry": 0, "carry_max": 0}
    assert _held_sheet(False).render("Kellow", value) == "[STATUS] Kellow — Band 1 | Pace 2"
    assert _held_sheet(True).render("Kellow", value) == (
        "[STATUS] Kellow — Band 1 | Pace 2 | Weight 0 | Carry 0/0"
    )
    # A paired column prints when either half stands above zero, and a first column at zero
    # still prints.
    assert _held_sheet(False).render(
        "K", {"rank": 0, "pace": 0, "weight": 0, "carry": 0, "carry_max": 3}
    ) == ("[STATUS] K — Band 0 | Carry 0/3")
    # A column the snapshot never held is shown as `?`, not hidden as a zero.
    assert _held_sheet(False).render("K", {"rank": 1}) == (
        "[STATUS] K — Band 1 | Pace ? | Weight ? | Carry ?/?"
    )


def test_a_projected_line_reads_back_as_a_partial_snapshot_and_folds_forward() -> None:
    sheet = _held_sheet(False)
    line = sheet.render("Kellow", {"rank": 1, "pace": 2, "weight": 0, "carry": 0, "carry_max": 0})
    [(subject, value, span)] = sheet.read(f"He read it again.\n{line}\nThen he moved.")
    assert subject == "Kellow" and value == {"rank": 1, "pace": 2}
    assert line[: span[1] - span[0]] == line
    # The strict pattern, every column present, is what it always was.
    assert sheet.pattern.search(line) is None
    full = sheet.render("Kellow", {"rank": 1, "pace": 2, "weight": 3, "carry": 1, "carry_max": 2})
    assert sheet.pattern.search(full) is not None, "every column present is the strict form"
    assert sheet.read(full)[0][1] == {"rank": 1, "pace": 2, "weight": 3, "carry": 1, "carry_max": 2}


def test_a_column_the_sheet_never_declared_is_skipped_and_the_rest_still_read() -> None:
    sheet = _held_sheet(False)
    line = "[STATUS] Kellow — Band 1 | Pace 2 | Luck 7 | Carry 1/2"
    [(_, value, _)] = sheet.read(line)
    assert value == {"rank": 1, "pace": 2, "carry": 1, "carry_max": 2}
    assert sheet.read("[STATUS] Kellow — Luck 7") == [], "no declared pair, no line"
    assert sheet.read("[STATUS] Kellow — Carry 1") == [], "a paired column needs both halves"


def test_a_sheet_declared_without_the_flag_shows_every_column_as_it_always_did() -> None:
    """Every book on disk declared its sheet before the flag existed, and reads the same."""
    declared = parse_sheet(
        {"fields": [{"name": "loop", "label": "Loop"}, {"name": "day", "label": "Day"}]}
    )
    assert declared.show_unheld is True
    assert declared.render("Silas", {"loop": 2, "day": 0}) == "[STATUS] Silas — Loop 2 | Day 0"
    hidden = parse_sheet(
        {
            "fields": [{"name": "loop", "label": "Loop"}, {"name": "day", "label": "Day"}],
            "show_unheld": False,
        }
    )
    assert hidden.render("Silas", {"loop": 2, "day": 0}) == "[STATUS] Silas — Loop 2"
    with pytest.raises(MalformedSheet):
        parse_sheet({"fields": [{"name": "loop", "label": "Loop"}], "show_unheld": "no"})
    assert FIXTURE_SHEET.show_unheld is True
    assert render_status_line(
        "Mara", {"level": 1, "hp": 10, "hp_max": 10, "mp": 1, "mp_max": 1, "gold": 0}
    ) == ("[STATUS] Mara — Level 1 | HP 10/10 | MP 1/1 | Gold 0")


def test_a_projected_line_in_a_scene_becomes_a_record_completed_from_what_stood_before() -> None:
    """The extractor reads the projected line and mints the whole state: the columns the line
    left out are filled from the subject's own earlier snapshots (a partial record at a
    position where a fuller one stands would read as a contradiction), and with nothing
    standing before, the record is what the line carried."""
    sheet_record = worlds.world_record(
        "invigilation",
        SHEET_PREDICATE,
        value={
            "fields": [
                {"name": "rank", "label": "Band"},
                {"name": "pace", "label": "Pace"},
                {"name": "weight", "label": "Weight"},
            ],
            "show_unheld": False,
        },
        authority=lc.StateAuthority.ACCEPTED_CANON,
    )
    person = worlds.world_record(
        "kellow",
        worlds.ENTITY_ROLE_PREDICATE,
        value="cast",
        authority=lc.StateAuthority.ACCEPTED_CANON,
    )
    known = [*state_of("litrpg").records, sheet_record, person]
    [record] = _statuses(
        extract_state(
            "[STATUS] Kellow — Band 1 | Pace 2",
            known=known,
            project_id="p",
            book_id="b",
            branch_id="br",
            logical_id="scene-1",
            version_id="v",
        )
    )
    assert record.subject == "kellow" and record.value == {"rank": 1, "pace": 2}
    # With the opening state on record, the same line mints the whole state as it stands.
    opening = worlds.world_record(
        "kellow",
        STATUS_PREDICATE,
        value={"rank": 1, "pace": 0, "weight": 0},
        authority=lc.StateAuthority.ACCEPTED_CANON,
    )
    [completed] = extract_state(
        "[STATUS] Kellow — Band 1 | Pace 2",
        known=[*known, opening],
        project_id="p",
        book_id="b",
        branch_id="br",
        logical_id="scene-1",
        version_id="v",
    )
    assert completed.value == {"rank": 1, "pace": 2, "weight": 0}


# -- §204: typed columns, and a sheet on any owner ----------------------------------------


def _typed_sheet() -> Sheet:
    return Sheet(
        (
            SheetField("rank", "Band", kind="ordinal"),
            SheetField("role", "Class", kind="name"),
            SheetField("skills", "Skills", kind="set"),
            SheetField("pace", "Pace"),
            SheetField("note", "Note", kind="text"),
        ),
        show_unheld=False,
    )


def _named_canon() -> list[lc.StateRecord]:
    def named(subject: str, name: str, role: str = "cast") -> list[lc.StateRecord]:
        return [
            worlds.world_record(
                subject, "is_a", value=name, authority=lc.StateAuthority.ACCEPTED_CANON
            ),
            worlds.world_record(
                subject,
                worlds.ENTITY_ROLE_PREDICATE,
                value=role,
                authority=lc.StateAuthority.ACCEPTED_CANON,
            ),
        ]

    return [
        *named("kellow", "Kellow", "protagonist"),
        *named("band_two", "Band Two"),
        *named("marker", "Marker"),
        *named("cold_seal", "Cold Seal", "capability"),
        *named("seamsight", "Seamsight", "capability"),
        *named("hall_c", "Hall C", "place"),
    ]


def test_a_typed_column_is_declared_by_kind_and_a_number_is_the_kind_when_none_is_given() -> None:
    declared = parse_sheet(
        {
            "fields": [
                {"name": "rank", "label": "Band", "kind": "ordinal"},
                {"name": "role", "label": "Class", "kind": "name"},
                {"name": "pace", "label": "Pace"},
            ]
        }
    )
    assert [f.kind for f in declared.fields] == ["ordinal", "name", "number"]
    with pytest.raises(MalformedSheet):
        parse_sheet({"fields": [{"name": "x", "label": "X", "kind": "colour"}]})
    with pytest.raises(MalformedSheet):
        parse_sheet({"fields": [{"name": "x", "label": "X", "kind": "name", "paired": True}]})
    assert all(f.kind == "number" for f in FIXTURE_SHEET.fields)


def test_typed_values_print_as_the_book_names_them_and_read_back_as_ids() -> None:
    """§204: a rung and a class print as their names and read back as the ids canon holds;
    a set prints its members with their depths; words print as written."""
    canon = _named_canon()
    value = {
        "rank": "band_two",
        "role": "marker",
        "skills": [["cold_seal", 2], ["seamsight"]],
        "pace": 0,
        "note": "held over",
    }
    line = render_status_line("kellow", value, sheet=_typed_sheet(), records=canon)
    assert line == (
        "[STATUS] Kellow — Band Band Two | Class Marker | Skills Cold Seal 2, Seamsight | "
        "Note held over"
    )
    ids = {display_name(canon, s).casefold(): s for s in {r.subject for r in canon}}
    [(subject, read, _)] = _typed_sheet().read(line, ids=ids)
    assert subject == "Kellow"
    assert read == {
        "rank": "band_two",
        "role": "marker",
        "skills": [["cold_seal", 2], ["seamsight"]],
        "note": "held over",
    }
    # A name the book does not know reaches no record; the rest of the line still reads.
    [(_, partial, _)] = _typed_sheet().read("[STATUS] Kellow — Band Nine | Pace 3", ids=ids)
    assert partial == {"pace": 3}
    # An empty set is unheld and hidden; shown, it prints as none.
    empty = {**value, "skills": []}
    assert "Skills" not in _typed_sheet().render("Kellow", empty)
    shown = dataclasses.replace(_typed_sheet(), show_unheld=True)
    assert "Skills none" in shown.render("Kellow", empty)


def test_a_two_word_label_splits_its_pair_where_the_label_ends() -> None:
    sheet = Sheet(
        (SheetField("rank", "Band"), SheetField("cold_seal", "Cold Seal", kind="name")),
        show_unheld=True,
    )
    ids = {"warden": "warden"}
    [(_, read, _)] = sheet.read("[STATUS] K — Band 1 | Cold Seal Warden", ids=ids)
    assert read == {"rank": 1, "cold_seal": "warden"}
    assert sheet.pattern.search("[STATUS] K — Band 1 | Cold Seal Warden") is not None


def test_only_numeric_columns_are_counted_names_the_beat_may_move() -> None:
    canon = [
        *_named_canon(),
        worlds.world_record(
            "kellow",
            SHEET_PREDICATE,
            value={
                "fields": [
                    {"name": "rank", "label": "Band", "kind": "ordinal"},
                    {"name": "pace", "label": "Pace"},
                    {"name": "role", "label": "Class", "kind": "name"},
                ]
            },
            authority=lc.StateAuthority.ACCEPTED_CANON,
        ),
        worlds.world_record(
            "kellow",
            STATUS_PREDICATE,
            value={"rank": "band_two", "pace": 2, "role": "marker"},
            authority=lc.StateAuthority.ACCEPTED_CANON,
        ),
    ]
    assert counted_names(canon) == ("Pace",)


def test_a_sheet_may_belong_to_a_place_and_its_line_reads_back() -> None:
    """§204's owner half: nothing in the line or the reader asks that the subject be a person;
    a place's snapshot renders under the book's sheet and is read back onto the place."""
    canon = [
        *_named_canon(),
        worlds.world_record(
            "hall_c",
            SHEET_PREDICATE,
            value={
                "fields": [{"name": "held", "label": "Held"}, {"name": "open", "label": "Open"}]
            },
            authority=lc.StateAuthority.ACCEPTED_CANON,
        ),
    ]
    line = render_status_line(
        "hall_c", {"held": 41, "open": 0}, sheet=sheet_for(canon), records=canon
    )
    assert line == "[STATUS] Hall C — Held 41 | Open 0"
    [record] = _statuses(
        extract_state(
            line,
            known=[*state_of("litrpg").records, *canon],
            project_id="p",
            book_id="b",
            branch_id="br",
            logical_id="scene-1",
            version_id="v",
        )
    )
    assert record.subject == "hall_c" and record.value == {"held": 41, "open": 0}


# -- §205: no default vocabulary; an undeclared book's own evidence declares its sheet -----


def test_an_undeclared_book_s_first_line_declares_its_sheet_in_the_order_it_printed() -> None:
    """The store writes a snapshot's keys sorted, so the order a book prints its columns in
    would be lost without a declaration; the first line an undeclared book prints is read
    as its declaration, canon, in the page's own order."""
    canon = [
        worlds.world_record(
            "kellow",
            worlds.ENTITY_ROLE_PREDICATE,
            value="protagonist",
            authority=lc.StateAuthority.ACCEPTED_CANON,
        )
    ]
    records = extract_state(
        "[STATUS] Kellow — Reach 3 | Band 1 | Carry 2/5",
        known=canon,
        project_id="p",
        book_id="b",
        branch_id="br",
        logical_id="scene-1",
        version_id="v",
        stated_order_key="s1",
    )
    by_predicate = {record.predicate: record for record in records}
    assert set(by_predicate) == {STATUS_PREDICATE, SHEET_PREDICATE}
    assert by_predicate[STATUS_PREDICATE].value == {
        "reach": 3,
        "band": 1,
        "carry": 2,
        "carry_max": 5,
    }
    declared = parse_sheet(by_predicate[SHEET_PREDICATE].value)
    assert declared.value_keys == ("reach", "band", "carry", "carry_max")
    assert [f.label for f in declared.fields] == ["Reach", "Band", "Carry"]
    assert declared.fields[2].paired
    # Read against its own declaration, the next scene's line needs no teaching.
    later = extract_state(
        "[STATUS] Kellow — Reach 4 | Band 1 | Carry 2/5",
        known=[*canon, *records],
        project_id="p",
        book_id="b",
        branch_id="br",
        logical_id="scene-2",
        version_id="v",
        stated_order_key="s2",
    )
    assert [record.predicate for record in later] == [STATUS_PREDICATE]


def test_an_imported_book_with_snapshots_and_no_declaration_is_declared_from_its_first() -> None:
    from litharness.domain.extraction import declaration_from_snapshots

    records = state_of("litrpg").records
    declaration = declaration_from_snapshots(records)
    assert declaration is not None and declaration.predicate == SHEET_PREDICATE
    assert parse_sheet(declaration.value) == FIXTURE_SHEET, "the file's own order"
    assert declaration_from_snapshots([*records, declaration]) is None, "declared already"
    assert declaration_from_snapshots([]) is None


# -- §206: a sheet declaration names its owner ----------------------------------------------


def _owned_book() -> list[lc.StateRecord]:
    """The person's sheet (the book's own), a place's sheet by subject, and a creature's by role."""
    canon = _named_canon()
    return [
        *canon,
        worlds.world_record(
            "kellow",
            SHEET_PREDICATE,
            value={
                "fields": [{"name": "rank", "label": "Band"}, {"name": "pace", "label": "Pace"}]
            },
            authority=lc.StateAuthority.ACCEPTED_CANON,
        ),
        worlds.world_record(
            "hall_c",
            SHEET_PREDICATE,
            value={
                "fields": [{"name": "held", "label": "Held"}, {"name": "open", "label": "Open"}],
                "owner": "hall_c",
            },
            authority=lc.StateAuthority.ACCEPTED_CANON,
        ),
        worlds.world_record(
            "chaperone",
            SHEET_PREDICATE,
            value={"fields": [{"name": "reach", "label": "Reach"}], "owner": "creature"},
            authority=lc.StateAuthority.ACCEPTED_CANON,
        ),
        worlds.world_record(
            "chaperone", "is_a", value="Chaperone", authority=lc.StateAuthority.ACCEPTED_CANON
        ),
        worlds.world_record(
            "chaperone",
            worlds.ENTITY_ROLE_PREDICATE,
            value="creature",
            authority=lc.StateAuthority.ACCEPTED_CANON,
        ),
    ]


def test_a_sheet_with_an_owner_is_that_owner_s_and_the_book_s_own_is_untouched() -> None:
    """§206: asked for the book, only the sheets with no owner compete, so a place's columns
    never become the person's line; asked for a subject, its own declaration wins, then one
    naming its role, then the book's."""
    records = _owned_book()
    book = sheet_for(records)
    assert book is not None and book.value_keys == ("rank", "pace") and book.owner is None
    assert sheet_for(records, subject="kellow") == book
    place = sheet_for(records, subject="hall_c")
    assert place is not None and place.value_keys == ("held", "open") and place.owner == "hall_c"
    creature = sheet_for(records, subject="chaperone")
    assert creature is not None and creature.owner == "creature"
    assert sheet_for(records, subject="somebody_else") == book, "no owner of its own: the book's"
    assert parse_sheet(place.declaration()).owner == "hall_c", "the owner round-trips"


def test_each_line_is_read_with_its_owner_s_columns_and_printed_with_them() -> None:
    records = [*state_of("litrpg").records, *_owned_book()]
    place_line = render_status_line("hall_c", {"held": 41, "open": 0}, records=records)
    person_line = render_status_line("kellow", {"rank": 1, "pace": 2}, records=records)
    assert place_line == "[STATUS] Hall C — Held 41 | Open 0"
    assert person_line == "[STATUS] Kellow — Band 1 | Pace 2"
    scene = f"He counted the hall.\n{place_line}\nHe counted himself.\n{person_line}\n"
    minted = _statuses(
        extract_state(
            scene,
            known=records,
            project_id="p",
            book_id="b",
            branch_id="br",
            logical_id="scene-1",
            version_id="v",
        )
    )
    assert {record.subject: record.value for record in minted} == {
        "hall_c": {"held": 41, "open": 0},
        "kellow": {"rank": 1, "pace": 2},
    }
    # The place's columns do not read onto the person, and the person's not onto the place.
    crossed = _statuses(
        extract_state(
            "[STATUS] Kellow — Held 3",
            known=records,
            project_id="p",
            book_id="b",
            branch_id="br",
            logical_id="scene-1",
            version_id="v",
        )
    )
    assert crossed == ()


def test_the_creature_s_role_sheet_reads_a_creature_s_line() -> None:
    records = [*state_of("litrpg").records, *_owned_book()]
    [record] = _statuses(
        extract_state(
            "[STATUS] Chaperone — Reach 2",
            known=records,
            project_id="p",
            book_id="b",
            branch_id="br",
            logical_id="scene-1",
            version_id="v",
        )
    )
    assert record.subject == "chaperone" and record.value == {"reach": 2}


# -- §208: the notice -----------------------------------------------------------------------


def test_the_gain_line_is_the_graph_line_s_can_do_phrase_filled_with_the_book_s_names() -> None:
    """§208: a book may declare a phrase for a grant gained beside the one for a standing, and
    the writer is shown it filled, protagonist and grant in the names the book prints; a line
    with no such phrase yields nothing, and so does a grant the book never declared."""
    from litharness.domain.extraction import gain_example

    canon = [
        *_named_canon(),
        worlds.world_record(
            "book",
            worlds.GRAPH_LINE_PREDICATE,
            value={
                "label": "INVIGILATION",
                "edges": [
                    {"phrase": "IS NOW ASSESSED AT", "predicate": worlds.STANDS_AT_PREDICATE},
                    {"phrase": "HAS BEEN AWARDED", "predicate": worlds.CAN_DO},
                ],
            },
            authority=lc.StateAuthority.ACCEPTED_CANON,
        ),
    ]
    assert gain_example(canon, ability_id="cold_seal") == (
        "[INVIGILATION] Kellow HAS BEEN AWARDED Cold Seal"
    )
    assert gain_example(canon, ability_id="nothing_declared") is None
    standing_only = [
        record for record in canon if record.predicate != worlds.GRAPH_LINE_PREDICATE
    ] + [
        worlds.world_record(
            "book",
            worlds.GRAPH_LINE_PREDICATE,
            value={
                "label": "INVIGILATION",
                "edges": [
                    {"phrase": "IS NOW ASSESSED AT", "predicate": worlds.STANDS_AT_PREDICATE}
                ],
            },
            authority=lc.StateAuthority.ACCEPTED_CANON,
        )
    ]
    assert gain_example(standing_only, ability_id="cold_seal") is None


def test_a_sheet_naming_its_system_round_trips_the_name() -> None:
    """§211: a sheet may name the system whose columns it prints; a sheet naming none
    declares nothing about one, so every declaration written before this is unchanged."""
    named = Sheet((SheetField("rank", "Seal"),), show_unheld=False, system="the_weave")
    assert parse_sheet(named.declaration()) == named
    plain = Sheet((SheetField("rank", "Seal"),))
    assert "system" not in plain.declaration()
    assert parse_sheet(plain.declaration()).system is None
