"""§17 Stage 1's fourth exit clause: planted-defect injection is caught by gates, not luck.

Before this slice the wired ladder was one gate, `shape.draft.v0`, so *accepted* meant "a
string of plausible length" — nothing injected a planted defect and nothing would have caught
one. These tests are the clause, stated as assertions.

**What is being graded, and what is not.** §8.4 assigns the LitRPG rule and predicate
vocabulary to ContinuityEvaluation's game-mechanics pack, because §7 and §8 once assigned the
identical invariants over the identical fixture to two projects and that would produce "two
divergent predicate vocabularies over one fixture and a permanent reconciliation tax". So the
six litrpg detectors are *not* reimplemented here and these tests do not claim to grade them.
What is graded is everything LitHarness owns: that a blocking finding refuses a candidate,
that a negative control does not, that an uncalibrated critic cannot block, that the refusal
carries a veto the retry ladder can act on, that the unit parks and escalates after its
budget, and that a defect planted in the store is caught by the one detector no sibling can
run.

**Mutation testing, not negative controls, for the record-based check.** §8.3 records why:
both fixtures' controls are prose-only phenomena with prose-only rule ids and no backing state
records, so a record-only engine cannot fire on them at all and "zero findings on the negative
controls" is vacuous. The replacement is to perturb the fixture and require the detector to
move — silent on a conforming book, loud on a broken one, and each assertion failing if the
detector is stubbed.

**The answer key is never read.** §8.3: five of six planted litrpg defects carry their own
finding id in `StateRecord.note` (*"...See f-gold-ledger."*), so a 6/6 gate is reachable by
regexing for `See f-`. `test_no_module_reads_the_note_field` scans this package's source and
fails if any module names it.
"""

from __future__ import annotations

import ast
import json
from dataclasses import replace
from pathlib import Path

import litharness_contracts as lc
import pytest

import litharness.domain as domain_package
from litharness.adapters.contracts_fixtures import fixture_findings, fixture_manuscript
from litharness.adapters.evaluation_artifact import (
    EvaluationArtifactUnreadable,
    load_findings,
)
from litharness.adapters.sqlite_store import SqliteStore
from litharness.domain.findings import (
    BLOCKING_SEVERITIES,
    DetectorInput,
    Finding,
    Severity,
    Status,
    finding_id_for,
    vetoes_for,
)
from litharness.domain.integrity import (
    CONTRADICTION_RULE,
    DUPLICATE_RULE,
    DUPLICATE_SPAN_WORDS,
    IN_PROCESS,
    detect_contradictions,
    detect_duplicate_scene,
    gate_integrity,
    summarise,
)
from litharness.domain.patch import Veto
from litharness.domain.policy import REGENERABLE, RETRYABLE, GateKind, Outcome, decide
from tests.conftest import BOOK_ID, BRANCH_ID
from tests.test_state import load_state, record


@pytest.fixture
def store(tmp_path) -> SqliteStore:
    return SqliteStore.open(tmp_path / "litharness.db")


def subject_for(fixture_id: str, **kwargs) -> DetectorInput:
    return DetectorInput(
        book_id=BOOK_ID,
        branch_id=BRANCH_ID,
        logical_id=kwargs.pop("logical_id", "scene-6"),
        records=tuple(kwargs.pop("records", load_state(fixture_id).records)),
        **kwargs,
    )


def finding(
    *,
    severity: Severity = Severity.MAJOR,
    status: Status = Status.OPEN,
    deterministic: bool = True,
    logical_id: str = "scene-6",
    rule: str = "ledger.gold.v0",
) -> Finding:
    return Finding(
        finding_id=finding_id_for(rule, logical_id, {"severity": severity.value}),
        category="world_rule",
        severity=severity,
        message=f"planted {rule}",
        status=status,
        rule_or_critic_id=rule,
        logical_id=logical_id,
        confidence_basis=(
            lc.ConfidenceBasis.DETERMINISTIC.value
            if deterministic
            else lc.ConfidenceBasis.CALIBRATED_MODEL.value
        ),
    )


# -- the clause: a planted defect is refused -------------------------------------------------


def test_a_blocking_finding_refuses_the_candidate() -> None:
    gate, findings = gate_integrity(subject_for("litrpg"), standing=[finding()])
    assert not gate.passed
    assert gate.blocking
    assert gate.gate is GateKind.INTEGRITY
    assert Veto.CONTINUITY_BREACH in gate.vetoes
    assert "ledger.gold.v0" in (gate.detail or "")
    assert len(findings) == 1


def test_the_refusal_reaches_a_retry_rather_than_an_escalation() -> None:
    """A veto nobody classified escalates on attempt 1 — `decide`'s deliberate default. So a
    new veto that is *not* in the retry table would send a human every scene the model
    fumbled once, and this is what pins that `CONTINUITY_BREACH` was classified."""
    assert Veto.CONTINUITY_BREACH in RETRYABLE
    assert Veto.CONTINUITY_BREACH not in REGENERABLE
    gate, _ = gate_integrity(subject_for("litrpg"), standing=[finding()])
    verdict, reason = decide((gate,), job_id="j", attempt=1, max_attempts=3)
    assert verdict is Outcome.RETRY
    assert "continuity_breach" in (reason or "")


def test_a_defect_the_model_cannot_write_out_of_parks_rather_than_retrying_forever() -> None:
    """After the attempt budget the unit parks and files an exception, which is where a
    defect three regenerations could not clear belongs."""
    gate, _ = gate_integrity(subject_for("litrpg"), standing=[finding()])
    verdict, reason = decide((gate,), job_id="j", attempt=3, max_attempts=3)
    assert verdict is Outcome.PARK
    assert "attempt budget exhausted" in (reason or "")


@pytest.mark.parametrize("severity", sorted(BLOCKING_SEVERITIES, key=lambda s: s.value))
def test_every_blocking_severity_blocks(severity: Severity) -> None:
    gate, _ = gate_integrity(subject_for("litrpg"), standing=[finding(severity=severity)])
    assert not gate.passed


@pytest.mark.parametrize("severity", [Severity.INFO, Severity.MINOR, Severity.UNKNOWN])
def test_a_finding_below_the_bar_annotates_rather_than_blocking(severity: Severity) -> None:
    """The line sits between minor and major because a blocking failure costs a generation.
    A finding not worth a second model call is not worth blocking on — it is worth recording,
    which happens either way."""
    gate, findings = gate_integrity(subject_for("litrpg"), standing=[finding(severity=severity)])
    assert gate.passed
    assert len(findings) == 1


# -- what must NOT be refused ------------------------------------------------------------------


def test_the_golden_books_produce_no_findings_of_their_own() -> None:
    """The negative-control leg that is not vacuous: a check that fires on a conforming book
    is not a floor, it is a tax. Both fixtures pass every in-process detector."""
    for fixture_id in ("mystery", "litrpg"):
        gate, findings = gate_integrity(subject_for(fixture_id))
        assert findings == [], (fixture_id, [item.message for item in findings])
        assert gate.passed
        assert "nothing found" in (gate.detail or "")


def test_an_intentional_device_does_not_block() -> None:
    """Both fixtures ship negative controls a *correct* detector emits — the rain-on-glass
    motif, Julian's alibi. A gate that blocked on every finding would refuse a book for its
    deliberate devices, and the only way past would be to weaken the detector."""
    control = finding(status=Status.ACCEPTED_INTENTIONAL, severity=Severity.CRITICAL)
    gate, findings = gate_integrity(subject_for("mystery"), standing=[control])
    assert gate.passed
    assert findings == [control]


@pytest.mark.parametrize(
    "status",
    [Status.FALSE_POSITIVE, Status.FIXED, Status.SUPERSEDED, Status.DEFERRED],
)
def test_a_settled_finding_does_not_block(status: Status) -> None:
    gate, _ = gate_integrity(
        subject_for("mystery"), standing=[finding(status=status, severity=Severity.CRITICAL)]
    )
    assert gate.passed


def test_an_evaluator_that_crashed_does_not_punish_the_draft() -> None:
    """`EVALUATION_ERROR` is the detector reporting its own failure, not the manuscript's."""
    gate, _ = gate_integrity(
        subject_for("mystery"),
        standing=[finding(status=Status.EVALUATION_ERROR, severity=Severity.CRITICAL)],
    )
    assert gate.passed


def test_an_uncalibrated_critic_cannot_block_but_is_still_recorded() -> None:
    """§10.4 from the gate's end. `PolicyDecision` enforces the same invariant at
    construction; enforcing it here too means a non-deterministic verdict never reaches the
    constructor that would raise on it — and the gate still *says* the critic ran, because a
    gate whose output vanishes when it disagrees is worse than one that never ran."""
    critic = finding(deterministic=False, severity=Severity.CRITICAL)
    gate, findings = gate_integrity(subject_for("mystery"), standing=[critic])
    assert gate.passed
    assert findings == [critic]
    assert "uncalibrated" in (gate.detail or "")
    assert "§10.4" in (gate.detail or "")


# -- the detector LitHarness owns, and its mutation tests ---------------------------------------


def test_contradictory_records_at_one_story_position_are_a_finding() -> None:
    """The corruption only this system can see: §12 step 5's extraction writing a record that
    contradicts one already accepted. ContinuityEvaluation evaluates a manuscript it is handed
    and never sees a LitHarness store mid-run."""
    records = [
        record("rec-a", subject="rook", predicate="level", value=3, order_key="s4"),
        record("rec-b", subject="rook", predicate="level", value=4, order_key="s4"),
    ]
    [found] = detect_contradictions(subject_for("litrpg", records=records))
    assert found.rule_or_critic_id == CONTRADICTION_RULE
    assert found.severity is Severity.MAJOR
    assert found.blocks
    assert found.deterministic
    assert "rook level holds 2 different values" in found.message


def test_the_same_value_twice_is_not_a_contradiction() -> None:
    records = [
        record("rec-a", subject="rook", predicate="level", value=3, order_key="s4"),
        record("rec-b", subject="rook", predicate="level", value=3, order_key="s4"),
    ]
    assert detect_contradictions(subject_for("litrpg", records=records)) == []


def test_a_value_that_changes_between_scenes_is_a_story_not_a_defect() -> None:
    """Story position is part of the grouping key on purpose. Dropping it would report every
    ordinary change in the book — on the litrpg fixture, every status snapshot after the
    first."""
    records = [
        record("rec-a", subject="rook", predicate="level", value=3, order_key="s3"),
        record("rec-b", subject="rook", predicate="level", value=4, order_key="s4"),
    ]
    assert detect_contradictions(subject_for("litrpg", records=records)) == []


def test_dict_values_compare_by_content_not_by_key_order() -> None:
    """Otherwise the detector reports dict iteration order as a continuity defect."""
    records = [
        record("rec-a", subject="rook", predicate="status", value={"hp": 24, "gold": 45}),
        record("rec-b", subject="rook", predicate="status", value={"gold": 45, "hp": 24}),
    ]
    assert detect_contradictions(subject_for("litrpg", records=records)) == []


def test_two_proposals_disagreeing_is_what_proposals_are_for() -> None:
    records = [
        record("rec-a", subject="rook", predicate="level", value=3,
               authority=lc.StateAuthority.PROPOSED),
        record("rec-b", subject="rook", predicate="level", value=4,
               authority=lc.StateAuthority.PROPOSED),
    ]
    assert detect_contradictions(subject_for("litrpg", records=records)) == []


@pytest.mark.parametrize("fixture_id", ["mystery", "litrpg"])
def test_mutating_a_conforming_book_makes_the_detector_fire(fixture_id: str) -> None:
    """§8.3's replacement for the vacuous negative-control leg: perturb a conforming step and
    require a *new* finding. Without this the detector's silence on both fixtures would be
    indistinguishable from the detector being stubbed out."""
    records = list(load_state(fixture_id).records)
    assert detect_contradictions(subject_for(fixture_id, records=records)) == []

    original = records[0]
    conflicting = replace(
        original,
        record_id=original.record_id + "-conflict",
        value="a value the book does not hold",
    )
    found = detect_contradictions(subject_for(fixture_id, records=[*records, conflicting]))
    assert len(found) == 1
    assert original.subject in found[0].message


def test_removing_the_conflict_makes_the_detector_go_silent_again() -> None:
    """The other half of the mutation leg: a repaired book produces no finding, so the
    detector is measuring the defect rather than the fixture's shape."""
    records = list(load_state("litrpg").records)
    broken = replace(records[3], record_id="rec-dupe", value={"level": 99})
    assert detect_contradictions(subject_for("litrpg", records=[*records, broken]))
    assert detect_contradictions(subject_for("litrpg", records=records)) == []


def test_a_finding_id_is_derived_so_a_rerun_converges() -> None:
    """A detector that re-ran on an unchanged revision must produce one row, not two — the
    outbox spin migration 006 had to fix, refused here in advance."""
    records = [
        record("rec-a", subject="rook", predicate="level", value=3, order_key="s4"),
        record("rec-b", subject="rook", predicate="level", value=4, order_key="s4"),
    ]
    first = detect_contradictions(subject_for("litrpg", records=records))
    second = detect_contradictions(subject_for("litrpg", records=list(reversed(records))))
    assert [item.finding_id for item in first] == [item.finding_id for item in second]


# -- the answer key ------------------------------------------------------------------------------


def test_no_module_reads_the_note_field() -> None:
    """§8.3: five of six planted litrpg defects carry their own finding id in
    `StateRecord.note` — "Gold 15 is what the prose says... See f-gold-ledger." — so a 6/6
    gate is reachable by regexing for `See f-`. Asserted by scanning the source rather than
    promised in a docstring, because the promise is what would rot."""
    # Scoped to the modules that see a `StateRecord`, which is what §8.3 asks for verbatim:
    # "assert the detector modules never reference the field". A whole-package scan was the
    # first attempt and it is wrong in both directions — it cannot tell `record.note` from
    # `calibration.note` (§10.4's own column, and the audit reader's free-text note, which is
    # the most valuable field in the calibration schema), so it would either fail on
    # legitimate reads or be relaxed until it caught nothing.
    root = Path(domain_package.__file__).parent
    watched = ("state.py", "integrity.py", "findings.py", "context.py", "extraction.py")
    offenders: list[str] = []
    for path in sorted(p for p in root.rglob("*.py") if p.name in watched):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            # Parsed rather than grepped: `note` appears legitimately in prose throughout
            # this package and as `DirectiveKind.ARC_NOTE`, and a substring scan flags both.
            # What must not exist is a *read* — `record.note` or `record["note"]`.
            reads = isinstance(node, ast.Attribute) and node.attr == "note"
            subscript = (
                isinstance(node, ast.Subscript)
                and isinstance(node.slice, ast.Constant)
                and node.slice.value == "note"
            )
            if reads or subscript:
                offenders.append(f"{path.relative_to(root).as_posix()}:{node.lineno}")
    assert offenders == []
    # And the scan is looking at files that exist, so a rename cannot silently empty it.
    assert sorted(p.name for p in root.rglob("*.py") if p.name in watched) == sorted(watched)


def test_the_fixture_really_does_carry_the_answer_key() -> None:
    """A guard on the guard above: if the fixture stopped annotating its defects, the scan
    would keep passing for the wrong reason and the property it protects would be gone."""
    notes = [
        item.note
        for item in load_state("litrpg").records
        if item.note and "See f-" in item.note
    ]
    assert len(notes) >= 5


# -- ingestion, which is how a sibling's detectors reach the gate ----------------------------------


@pytest.mark.parametrize("fixture_id", ["mystery", "litrpg"])
def test_the_golden_findings_ingest_as_an_evaluation_artifact(fixture_id: str) -> None:
    """§8.4's integration shape, exercised on the real artifact: an evaluator writes an
    `EvaluationArtifact`, LitHarness reads it, and the only thing either project knows about
    the other is a schema they both already depend on. No import of a sibling package."""
    evaluation = load_findings(fixture_findings(fixture_id))
    run_id, findings = evaluation.run_id, evaluation.findings
    assert evaluation.complete, "the golden artifacts record a finished run"
    assert run_id
    assert findings
    assert all(item.rule_or_critic_id for item in findings)
    assert all(item.deterministic for item in findings)
    # Every planted defect is severe enough to block; every negative control is a real
    # finding that needs a human to say it is intentional.
    blocking = [item for item in findings if item.blocks]
    controls = [item for item in findings if item.finding_id.startswith("f-control-")]
    assert blocking
    assert controls


def test_an_ingested_planted_defect_refuses_the_candidate_for_its_node(store: SqliteStore) -> None:
    """The clause end to end, at the store level: a real planted defect from the fixture's
    own findings artifact is ingested, and the gate for the node it lands on refuses."""
    findings = load_findings(fixture_findings("litrpg")).findings
    store.record_findings(BOOK_ID, BRANCH_ID, findings, created_at="t")

    planted = next(item for item in findings if item.finding_id == "f-gold-ledger")
    assert planted.logical_id
    standing = store.findings(BOOK_ID, BRANCH_ID, logical_id=planted.logical_id, open_only=True)
    gate, _ = gate_integrity(
        subject_for("litrpg", logical_id=planted.logical_id), standing=standing
    )
    assert not gate.passed
    assert Veto.CONTINUITY_BREACH in gate.vetoes


def test_a_defect_on_another_scene_does_not_block_this_one(store: SqliteStore) -> None:
    """§4.1: a blocked item never stalls the queue. Blocking every later beat on one old
    finding would turn a single defect into a stalled book."""
    findings = load_findings(fixture_findings("litrpg")).findings
    store.record_findings(BOOK_ID, BRANCH_ID, findings, created_at="t")
    planted = next(item for item in findings if item.finding_id == "f-gold-ledger")

    elsewhere = [
        item.logical_id
        for item in findings
        if item.logical_id and item.logical_id != planted.logical_id
    ]
    clean_node = next(
        node for node in ("scene-1", "scene-2", "scene-3", "scene-4", "scene-5", "scene-6")
        if node != planted.logical_id and node not in elsewhere
    )
    standing = store.findings(BOOK_ID, BRANCH_ID, logical_id=clean_node, open_only=True)
    gate, _ = gate_integrity(subject_for("litrpg", logical_id=clean_node), standing=standing)
    assert gate.passed


def test_reingesting_the_same_artifact_writes_nothing(store: SqliteStore) -> None:
    findings = load_findings(fixture_findings("mystery")).findings
    first = store.record_findings(BOOK_ID, BRANCH_ID, findings, created_at="t")
    assert first == len(findings)
    assert store.record_findings(BOOK_ID, BRANCH_ID, findings, created_at="t") == 0


def test_a_rerun_does_not_reopen_what_a_human_closed(store: SqliteStore) -> None:
    """`INSERT OR IGNORE` gives this for free, and an upsert would take it away: every
    evaluation would re-raise every negative control, which is the fastest way to make an
    operator stop reading the queue."""
    findings = load_findings(fixture_findings("mystery")).findings
    store.record_findings(BOOK_ID, BRANCH_ID, findings, created_at="t")
    control = "f-control-motif-rain"
    assert store.set_finding_status(control, Status.ACCEPTED_INTENTIONAL)

    store.record_findings(BOOK_ID, BRANCH_ID, findings, created_at="t")
    stored = {item.finding_id: item for item in store.findings(BOOK_ID, BRANCH_ID)}
    assert stored[control].status is Status.ACCEPTED_INTENTIONAL
    assert not stored[control].blocks


def test_dismissing_a_control_unblocks_the_node_it_landed_on(store: SqliteStore) -> None:
    """The operator verb behind a negative control, end to end."""
    findings = load_findings(fixture_findings("mystery")).findings
    store.record_findings(BOOK_ID, BRANCH_ID, findings, created_at="t")
    blocking = [item for item in store.findings(BOOK_ID, BRANCH_ID, open_only=True) if item.blocks]
    assert blocking

    for item in blocking:
        store.set_finding_status(item.finding_id, Status.ACCEPTED_INTENTIONAL)
    remaining = [
        item for item in store.findings(BOOK_ID, BRANCH_ID, open_only=True) if item.blocks
    ]
    assert remaining == []


def test_findings_are_returned_worst_first(store: SqliteStore) -> None:
    store.record_findings(
        BOOK_ID,
        BRANCH_ID,
        [
            finding(severity=Severity.MINOR, rule="a"),
            finding(severity=Severity.CRITICAL, rule="b"),
            finding(severity=Severity.MAJOR, rule="c"),
        ],
        created_at="t",
    )
    got = [item.severity for item in store.findings(BOOK_ID, BRANCH_ID)]
    assert got == [Severity.CRITICAL, Severity.MAJOR, Severity.MINOR]


def test_a_confirmed_finding_is_still_unresolved(store: SqliteStore) -> None:
    """`open_only` is not `status = 'open'`. `CONFIRMED` means a human agreed the defect is
    real, which is the last status a gate should treat as settled."""
    item = finding()
    store.record_findings(BOOK_ID, BRANCH_ID, [item], created_at="t")
    store.set_finding_status(item.finding_id, Status.CONFIRMED)
    still = store.findings(BOOK_ID, BRANCH_ID, open_only=True)
    assert [entry.finding_id for entry in still] == [item.finding_id]
    assert still[0].blocks


def test_a_finding_round_trips_through_the_store(store: SqliteStore) -> None:
    findings = load_findings(fixture_findings("mystery")).findings
    store.record_findings(BOOK_ID, BRANCH_ID, findings, created_at="t")
    stored = {item.finding_id: item for item in store.findings(BOOK_ID, BRANCH_ID)}
    promise = stored["f-promise-letter"]
    assert promise.rule_or_critic_id == "promise.resolution.v0"
    assert promise.severity is Severity.MAJOR
    assert promise.logical_id == "scene-6"
    # The whole contract artifact survives, including the claim the projection never reads.
    assert promise.source["claim"] == {
        "thread": "sealed_letter_reading",
        "expected": "resolved",
        "observed": "open_at_end",
    }


def test_a_malformed_artifact_is_an_operational_fault_not_a_crash(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"not": "an artifact"}), encoding="utf-8")
    with pytest.raises(EvaluationArtifactUnreadable):
        load_findings(path)


def test_the_findings_artifact_is_not_confused_with_the_manuscript(tmp_path) -> None:
    """A real file of the wrong schema, which is the mistake an operator actually makes."""
    with pytest.raises(EvaluationArtifactUnreadable):
        load_findings(fixture_manuscript("mystery"))


# -- vocabulary ------------------------------------------------------------------------------------


def test_no_blocking_finding_means_no_veto() -> None:
    assert vetoes_for([]) == ()
    assert vetoes_for([finding(severity=Severity.MINOR)]) == ()
    assert vetoes_for([finding()]) == (Veto.CONTINUITY_BREACH,)


def test_summarise_leads_with_the_worst() -> None:
    assert summarise([]) == "no findings"
    text = summarise([finding(severity=Severity.MINOR), finding(severity=Severity.CRITICAL)])
    assert "worst critical" in text
    assert "1 blocking" in text


# -- an incomplete evaluation is not a passing one --------------------------------------


def errored_artifact(tmp_path: Path, *, findings: int = 0, errors: int = 6) -> Path:
    """The real litrpg artifact with its findings replaced by detector errors.

    Not hand-built from nothing: this is the shape ContinuityEvaluation actually produces
    when evidence spans fail to resolve, which is the *expected* state after a repair — a
    repair changes prose, and every downstream span cites the version_id it just invalidated.
    """
    payload = json.loads(fixture_findings("litrpg").read_text(encoding="utf-8"))
    payload["findings"] = payload["findings"][:findings]
    payload["errors"] = [
        {
            "stage": "evidence_resolution",
            "reason": "EvidenceResolutionError",
            "detail": "version_id not found in revision",
        }
        for _ in range(errors)
    ]
    path = tmp_path / "errored.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_a_run_whose_detectors_failed_is_not_a_clean_book(tmp_path: Path) -> None:
    """The defect this replaces, reproduced before it was fixed: an artifact carrying six
    `evidence_resolution` errors and zero findings ingested as "0 finding(s), 0 new, 0
    blocking", exit 0, over a book with six planted defects. The adapter read `findings` and
    nothing else, so a completed evaluation and a failed one were indistinguishable."""
    evaluation = load_findings(errored_artifact(tmp_path))
    assert evaluation.findings == []
    assert not evaluation.complete, "six detectors failed; that is not a clean result"
    assert len(evaluation.errors) == 6
    assert "evidence_resolution" in evaluation.summarise_errors()


def test_findings_that_did_arrive_survive_a_partial_failure(tmp_path: Path) -> None:
    """Dropping them would trade one silent gap for another. A partial run reports both."""
    evaluation = load_findings(errored_artifact(tmp_path, findings=3, errors=2))
    assert len(evaluation.findings) == 3
    assert not evaluation.complete


def test_the_error_summary_collapses_one_problem_reported_six_times(tmp_path: Path) -> None:
    assert load_findings(errored_artifact(tmp_path)).summarise_errors().count(";") == 0
    assert "(x6)" in load_findings(errored_artifact(tmp_path)).summarise_errors()


# -- duplicate scenes (the defect Book Zero drove through five times) ----------------------


def _scene_text(seed: str, words: int = 200) -> str:
    """Distinct prose of a given length, sharing no long run with another seed."""
    return " ".join(f"{seed}{index}" for index in range(words))


def test_a_scene_that_reproduces_an_earlier_one_is_refused() -> None:
    """The failure the whole ladder missed.

    Book Zero accepted thirty scenes with 31 ACCEPT decisions and zero findings, and five of
    them were near-copies of an earlier scene — the longest sharing **872 consecutive words**
    with scene 6. The shape gate counts characters; `detect_contradictions` reads state
    records; `craft.repeated_span.v0` measured all five exactly and is forbidden to block
    because §10.4 refuses an uncalibrated craft gate. The measurement was never the gap.
    """
    earlier = _scene_text("alpha", 400)
    duplicate = _scene_text("alpha", 400)  # byte-identical

    found = detect_duplicate_scene(
        subject_for("litrpg", candidate=duplicate, prior_prose=(("scene-1", earlier),))
    )
    assert len(found) == 1
    assert found[0].blocks and found[0].deterministic
    assert found[0].rule_or_critic_id == DUPLICATE_RULE
    # The evidence travels with the refusal — `repeated_span`'s rule, for its reason: a
    # number that has to be interpreted gets interpreted, and a quote does not.
    assert "scene-1" in found[0].message
    assert "alpha0" in found[0].message


def test_a_scene_that_merely_shares_a_phrase_is_not_refused() -> None:
    """The other half of the mutation leg. A detector that fires on ordinary prose is not a
    floor, it is a tax — §8.3's own words about the contradiction check, applied here."""
    earlier = _scene_text("alpha", 400)
    borrowed = " ".join(earlier.split()[:40])
    fresh = f"{_scene_text('beta', 300)} {borrowed}"

    assert (
        detect_duplicate_scene(
            subject_for("litrpg", candidate=fresh, prior_prose=(("scene-1", earlier),))
        )
        == []
    ), "40 shared words is under the threshold and well under what published serials repeat"


def test_the_threshold_sits_above_what_published_human_prose_does() -> None:
    """§49 measured the longest verbatim cross-chapter span over 24 published RoyalRoad
    serials: 93 words (undeclared 2025), 91 (declared-AI), 70 (pre-2023). Human authors write
    recaps, epigraphs and quoted prophecies and repeat them exactly, so the threshold sits
    above the largest span anybody has observed rather than at it. Pinned as a number because
    lowering it below 93 would start refusing the mechanism that produces legitimate long
    spans in human books."""
    assert DUPLICATE_SPAN_WORDS > 93


def test_the_golden_fixtures_produce_no_duplicate_finding() -> None:
    """The negative-control leg, on human-authored books this system did not write.

    Measured: the mystery fixture's worst cross-scene span is 17 words and the litrpg
    fixture's is 0, against a threshold of 120. A check that fired on a conforming book could
    not be turned on blocking without a calibration programme, which is exactly the argument
    `state.contradiction.v0` had to make first.
    """
    for fixture_id in ("mystery", "litrpg"):
        manuscript = lc.parse_artifact(
            lc.ManuscriptRevision,
            json.loads(fixture_manuscript(fixture_id).read_text(encoding="utf-8")),
        )
        scenes = [(node.logical_id, node.content) for node in manuscript.nodes if node.content]
        for index, (logical_id, text) in enumerate(scenes):
            found = detect_duplicate_scene(
                subject_for(
                    fixture_id,
                    logical_id=logical_id,
                    candidate=text,
                    prior_prose=tuple(scenes[:index]),
                )
            )
            assert found == [], f"{fixture_id} {logical_id}: {found and found[0].message}"


def test_a_detector_with_no_book_to_compare_against_finds_nothing() -> None:
    """The first scene of every book, and any caller that supplies no prior prose. Silence
    here is correct rather than a miss, and it is asserted so that `prior_prose` defaulting
    to empty cannot quietly make the detector inert everywhere."""
    assert detect_duplicate_scene(subject_for("litrpg", candidate=_scene_text("solo"))) == []
    assert detect_duplicate_scene(subject_for("litrpg", prior_prose=(("s1", "x"),))) == []


def test_a_scene_is_never_compared_against_itself() -> None:
    """Through the gate rather than the detector, because the exclusion lives at both call
    sites and an evaluator judges a revision the scene is already *in* — so a missing
    exclusion would report a 900-word self-overlap on every scene in the book."""
    text = _scene_text("alpha", 400)
    subject = subject_for(
        "litrpg",
        logical_id="scene-1",
        candidate=text,
        prior_prose=(("scene-2", _scene_text("beta", 400)),),
    )
    assert detect_duplicate_scene(subject) == []


def test_the_duplicate_finding_maps_onto_a_retryable_veto() -> None:
    """And the action is only correct because the sampler moved.

    `vetoes_for` maps every blocking finding onto `CONTINUITY_BREACH`, which §4.2 classifies
    `RETRYABLE`. That was the *wrong* action until recently: the prompt is frozen onto the job
    payload, so under greedy decoding a retry regenerated the identical duplicate and spent
    the attempt budget rediscovering it. With the seed derived from the attempt number a retry
    is a genuinely different draft, so the refusal now buys a second chance rather than a
    slower route to the same refusal.
    """
    earlier = _scene_text("alpha", 400)
    found = detect_duplicate_scene(
        subject_for("litrpg", candidate=earlier, prior_prose=(("scene-1", earlier),))
    )
    assert vetoes_for(found) == (Veto.CONTINUITY_BREACH,)
    assert Veto.CONTINUITY_BREACH in RETRYABLE


def test_a_rerun_over_the_same_duplicate_converges_to_one_finding() -> None:
    """Content-derived ids, so the evaluation lane re-checking an accepted scene does not
    grow the findings queue every tick."""
    earlier = _scene_text("alpha", 400)
    subject = subject_for("litrpg", candidate=earlier, prior_prose=(("scene-1", earlier),))
    assert detect_duplicate_scene(subject)[0].finding_id == (
        detect_duplicate_scene(subject)[0].finding_id
    )


def test_the_detector_is_in_the_loop_and_not_merely_written() -> None:
    """`IN_PROCESS` is the extension point and the only thing that runs a detector.

    This project's most repeated defect is a promise whose only caller is a test — §19.1
    lists eleven of them and names the search term. A detector absent from this tuple is
    exactly that shape, and would be invisible to every test that calls it directly.
    """
    assert detect_duplicate_scene in IN_PROCESS
