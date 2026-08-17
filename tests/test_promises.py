"""§61 Add 2: the promise/payoff ledger, the overdue check, and the scene-delta annotation.

The design under test is shaped by two refutations. scene_change_profile died because LEDGER
delta is not DRAMATIC delta — the confession scene carried zero state records — so both
features take a model leg, folded into the existing per-scene summary call (§15: asks fold
into one invocation). And a model leg may never block: everything asserted here about the
overdue and zero-delta findings is that they annotate — MINOR/INFO, heuristic basis — and
that no code path lets them refuse, park, or stand in front of a beat.

The ledger is deliberately NOT a THREAD state record. `open_threads` tests
`value == "open"` by exact equality and both golden fixtures author it; the contradiction
detector groups every canon record on (subject, predicate, order_key); and
`has_story_vocabulary` freezes extraction for unrecognised registry versions. A separate
table (migration 023) sidesteps all three, and `test_the_thread_vocabulary_is_untouched`
pins the seam this suite must not have moved.
"""

from __future__ import annotations

import json

import litharness_contracts as lc
import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.planner import packet_for, template_for
from litharness.application.repair import summary_job_for
from litharness.application.summarize import (
    SCENE_DELTA_RULE,
    SUMMARY_SCHEMA,
    extract_delta,
    make_summary_handler,
    render_summary_prompt,
)
from litharness.domain import state as state_mod
from litharness.domain.beats import beats_for
from litharness.domain.context import THREADS, assemble
from litharness.domain.findings import DetectorInput, Severity, Status
from litharness.domain.generation import CompletionResult, Resolution, Usage
from litharness.domain.integrity import (
    IN_PROCESS,
    OVERDUE_RULE,
    detect_overdue_promises,
    gate_integrity,
    gate_standing,
)
from litharness.domain.nodes import Node, NodeKind
from litharness.domain.policy import Outcome, decide
from litharness.domain.promises import (
    PROMISE_OPEN,
    PROMISE_PAID,
    Promise,
    describe_owed,
    overdue_promises,
    parse_due_hint,
    promise_id_for,
)
from litharness.domain.revision import Revision, build_revision
from litharness.domain.text import content_hash
from litharness.providers.base import parse_schema_payload
from litharness.providers.fake import FakeProvider
from litharness.providers.registry import ProviderRegistry
from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID

START = 1_760_000_000.0


@pytest.fixture
def store(tmp_path) -> SqliteStore:
    return SqliteStore.open(tmp_path / "promises.db")


def a_book(scenes: int = 12) -> Revision:
    """A drafted book long enough that its story keys need padding (width 2 at 12)."""
    nodes = [Node(logical_id="book", kind=NodeKind.BOOK, position_key="010")]
    for index in range(1, scenes + 1):
        nodes.append(
            Node(
                logical_id=f"sc{index}",
                kind=NodeKind.SCENE,
                position_key=f"{index:03d}0",
                parent_logical_id="book",
                content=(
                    f"Scene {index}. Rook set the lantern down and counted what the day "
                    "had cost him, and the ledger did not blink."
                ),
            )
        )
    return build_revision(BOOK_ID, BRANCH_ID, nodes)


def a_promise(
    subject: str = "gate_ledger",
    *,
    due_key: str | None = "s05",
    opened_at_key: str = "s02",
    status: str = PROMISE_OPEN,
) -> Promise:
    return Promise(
        promise_id=promise_id_for(BOOK_ID, subject),
        subject=subject,
        description="the gate ledger must be read back before the toll is settled",
        opened_at_key=opened_at_key,
        due_key=due_key,
        opened_by_revision="rev-1",
        status=status,
        model="stub-v1",
    )


class ExtendedStub:
    """A generator answering the extended schema with a scripted structural payload."""

    def __init__(self, payload: dict[str, object] | None = None) -> None:
        base: dict[str, object] = {
            "setting": "The city gate, at night.",
            "characters": "Rook; the gatekeeper.",
            "events": "Rook is turned away and swears to return.",
            "open": "The ledger is still owed a reading.",
            "delta": {
                "who": "Rook",
                "what_changed": "standing with the gate",
                "from": "tolerated",
                "to": "barred",
            },
            "promises_opened": [],
            "promises_paid": [],
        }
        if payload:
            base.update(payload)
        self.payload = base
        self.requests: list[object] = []

    def complete(self, request):  # type: ignore[no-untyped-def]
        self.requests.append(request)
        return (
            CompletionResult(
                text=json.dumps(self.payload),
                provider="stub",
                model="stub-v1",
                usage=Usage(input_tokens=10, output_tokens=10),
                parsed=json.loads(json.dumps(self.payload)),
                schema_requested=True,
            ),
            Resolution("stub"),
        )


def summarise_scene(store: SqliteStore, revision: Revision, logical_id: str, generator) -> None:  # type: ignore[no-untyped-def]
    handle = make_summary_handler(generator, store, PROJECT_ID)
    text = revision.node(logical_id).content
    assert text is not None
    handle(
        summary_job_for(
            book_id=BOOK_ID,
            branch_id=BRANCH_ID,
            revision_id=revision.revision_id,
            logical_id=logical_id,
            content_hash=content_hash(text),
        ),
        START,
    )


# -- the extended schema ------------------------------------------------------------------


def test_the_extended_summary_round_trips_with_a_delta_and_without_one() -> None:
    """The shape gate the live call answers through. `delta`'s union is expressed as
    `anyOf` because the shallow validator reads one top-level type per property — a
    `["object", "null"]` list there would make every answer, null or not, unparseable."""
    answer = {
        "setting": "s",
        "characters": "c",
        "events": "e",
        "open": "o",
        "delta": {"who": "Rook", "what_changed": "debt", "from": "40", "to": "45"},
        "promises_opened": [
            {"subject": "gate ledger", "description": "a reading is owed", "due_hint": 5}
        ],
        "promises_paid": ["silver key"],
    }
    parsed = parse_schema_payload(json.dumps(answer), SUMMARY_SCHEMA)
    assert parsed is not None
    assert parsed["delta"]["who"] == "Rook"

    answer["delta"] = None
    null_delta = parse_schema_payload(json.dumps(answer), SUMMARY_SCHEMA)
    assert null_delta is not None
    assert null_delta["delta"] is None, "null is the schema's own answer for a still scene"


def test_a_missing_structural_field_is_a_malformed_answer() -> None:
    answer = {"setting": "s", "characters": "c", "events": "e", "open": "o"}
    assert parse_schema_payload(json.dumps(answer), SUMMARY_SCHEMA) is None


def test_the_prompt_asks_the_delta_question_without_hedging() -> None:
    """§55.1's measured lesson, applied at the wording level this time on purpose: the
    progression clause's three defensible hedges summed to an instruction to change
    nothing. The delta ask is a direct imperative with a null escape, and nothing in it
    says "if any" or "where appropriate"."""
    system, _ = render_summary_prompt("The scene text.")
    assert "DELTA:" in system
    assert "state the one thing that changed" in system
    assert "PROMISES_OPENED:" in system
    assert "PROMISES_PAID:" in system
    lowered = system.lower()
    assert "if any" not in lowered
    assert "where appropriate" not in lowered


def test_extract_delta_reads_only_a_usable_shape() -> None:
    assert extract_delta(None) is None
    assert extract_delta("delta-3f9a12") is None, "a synthesised string is not a shift"
    assert extract_delta({"who": "Rook"}) is None
    assert extract_delta({"who": "Rook", "what_changed": "x", "from": " ", "to": "y"}) is None
    full = {"who": "Rook", "what_changed": "debt", "from": "40", "to": "45"}
    assert extract_delta(full) == full


# -- the ledger ---------------------------------------------------------------------------


def test_a_promise_opens_once_and_reopening_is_a_no_op(store: SqliteStore) -> None:
    """record-id discipline: `promise_id` derives from (book, subject) alone, so a
    re-summarised scene re-reporting the same subject converges on one row."""
    assert store.record_promise(BOOK_ID, BRANCH_ID, a_promise())
    assert not store.record_promise(BOOK_ID, BRANCH_ID, a_promise())
    rewritten = a_promise()
    assert not store.record_promise(
        BOOK_ID, BRANCH_ID, rewritten
    ), "a changed description under the same subject is the same promise"
    [row] = store.promises(BOOK_ID, BRANCH_ID)
    assert row.status == PROMISE_OPEN


def test_payment_is_a_single_write_once_transition(store: SqliteStore) -> None:
    store.record_promise(BOOK_ID, BRANCH_ID, a_promise())
    assert store.pay_promise(
        BOOK_ID,
        BRANCH_ID,
        promise_id_for(BOOK_ID, "gate_ledger"),
        paid_at_key="s04",
        paid_by_revision="rev-2",
    )
    # The second payment finds nothing open: the first reading wins, a replay is a no-op.
    assert not store.pay_promise(
        BOOK_ID,
        BRANCH_ID,
        promise_id_for(BOOK_ID, "gate_ledger"),
        paid_at_key="s09",
        paid_by_revision="rev-3",
    )
    [row] = store.promises(BOOK_ID, BRANCH_ID)
    assert row.status == PROMISE_PAID
    assert row.paid_at_key == "s04"
    assert store.promises(BOOK_ID, BRANCH_ID, open_only=True) == []


def test_paying_a_promise_nobody_opened_writes_nothing(store: SqliteStore) -> None:
    """A payoff with no recorded promise is not a debt this ledger can attest was owed."""
    assert not store.pay_promise(
        BOOK_ID,
        BRANCH_ID,
        promise_id_for(BOOK_ID, "unheard_of"),
        paid_at_key="s03",
        paid_by_revision="rev-2",
    )
    assert store.promises(BOOK_ID, BRANCH_ID) == []


def test_the_handler_maintains_the_ledger_from_the_summary_answer(store: SqliteStore) -> None:
    """Open in one scene's summary, pay in a later one's; both keys are `beats_for`'s own."""
    revision = a_book()
    store.commit_revision(revision, created_at="2026-08-17T00:00:00Z")
    opener = ExtendedStub(
        {
            "promises_opened": [
                {
                    "subject": "Gate Ledger",
                    "description": "the toll ledger must be read back",
                    "due_hint": 10,
                }
            ]
        }
    )
    summarise_scene(store, revision, "sc2", opener)
    [promise] = store.promises(BOOK_ID, BRANCH_ID, open_only=True)
    assert promise.subject == "gate_ledger", "subjects normalise via extraction's rule"
    assert promise.opened_at_key == "s02", "the scene's own beat key, padded to the book"
    assert promise.due_key == "s10"
    assert promise.model == "stub-v1", "provenance travels on the row"

    payer = ExtendedStub({"promises_paid": ["Gate Ledger"]})
    summarise_scene(store, revision, "sc5", payer)
    [paid] = store.promises(BOOK_ID, BRANCH_ID)
    assert paid.status == PROMISE_PAID
    assert paid.paid_at_key == "s05"
    assert store.promises(BOOK_ID, BRANCH_ID, open_only=True) == []


def test_replaying_the_summary_job_converges_on_one_ledger_row(store: SqliteStore) -> None:
    revision = a_book()
    store.commit_revision(revision, created_at="2026-08-17T00:00:00Z")
    generator = ExtendedStub(
        {
            "promises_opened": [
                {"subject": "gate ledger", "description": "a reading is owed", "due_hint": None}
            ]
        }
    )
    summarise_scene(store, revision, "sc2", generator)
    summarise_scene(store, revision, "sc2", generator)
    assert len(store.promises(BOOK_ID, BRANCH_ID)) == 1


# -- due-key defaulting -------------------------------------------------------------------


@pytest.mark.parametrize("hint", [None, "before the rains end", 0, 99])
def test_an_absent_or_unparseable_due_hint_defaults_to_the_final_scene_key(
    store: SqliteStore, hint: object
) -> None:
    """A promise is at latest overdue if the book ends unpaid. No hint, prose with no
    number, and an out-of-range scene number all land on the last scene's key rather than
    on a guessed one."""
    revision = a_book()
    store.commit_revision(revision, created_at="2026-08-17T00:00:00Z")
    generator = ExtendedStub(
        {
            "promises_opened": [
                {"subject": "gate ledger", "description": "a reading is owed", "due_hint": hint}
            ]
        }
    )
    summarise_scene(store, revision, "sc3", generator)
    [promise] = store.promises(BOOK_ID, BRANCH_ID)
    final = beats_for(revision, template_for(revision))[-1].story_order_key
    assert promise.due_key == final == "s12"


def test_a_scene_number_hint_lands_on_that_scenes_minted_key(store: SqliteStore) -> None:
    """The due key is read off `beats_for`'s own beat, not formatted here — one padding
    implementation in the project, and "scene 7" in prose parses the same as 7."""
    revision = a_book()
    store.commit_revision(revision, created_at="2026-08-17T00:00:00Z")
    generator = ExtendedStub(
        {
            "promises_opened": [
                {
                    "subject": "gate ledger",
                    "description": "a reading is owed",
                    "due_hint": "by scene 7",
                }
            ]
        }
    )
    summarise_scene(store, revision, "sc2", generator)
    [promise] = store.promises(BOOK_ID, BRANCH_ID)
    assert promise.due_key == "s07"


def test_parse_due_hint_reads_numbers_and_refuses_everything_else() -> None:
    assert parse_due_hint(12) == 12
    assert parse_due_hint("12") == 12
    assert parse_due_hint("scene 12") == 12
    assert parse_due_hint(None) is None
    assert parse_due_hint("soon") is None
    assert parse_due_hint(True) is None, "a bool is not a scene number"
    assert parse_due_hint(0) is None
    assert parse_due_hint(-3) is None


def test_a_book_whose_template_is_not_chronological_gets_no_promise_rows(
    store: SqliteStore,
) -> None:
    """The milestone abstention, inherited whole: no story key, no ledger entry — a
    promise placed at a guessed position would be this feature minting the one thing
    `beats_for` refused to. A three-scene book fits no template at all, which is the same
    abstention one step earlier."""
    revision = a_book(scenes=3)
    store.commit_revision(revision, created_at="2026-08-17T00:00:00Z")
    generator = ExtendedStub(
        {
            "promises_opened": [
                {"subject": "gate ledger", "description": "a reading is owed", "due_hint": 2}
            ]
        }
    )
    summarise_scene(store, revision, "sc2", generator)
    assert store.promises(BOOK_ID, BRANCH_ID) == []
    assert store.scene_summaries(BOOK_ID, BRANCH_ID), "the summary itself still lands"


# -- overdue arithmetic -------------------------------------------------------------------


def test_overdue_is_a_strict_comparison_over_padded_keys() -> None:
    due_s05 = a_promise(due_key="s05")
    assert overdue_promises([due_s05], "s06") == (due_s05,)
    assert overdue_promises([due_s05], "s05") == (), "the due scene may still pay"
    assert overdue_promises([due_s05], "s04") == ()


def test_padding_keeps_scene_ten_after_scene_two() -> None:
    """The s10<s2 lexicographic bug, pinned from this side: both keys come from
    `beats_for`'s zero-padded minting, so s02 < s10 compares in story order. An unpadded
    ledger would report a promise due at scene 10 as overdue at scene 2."""
    due_s10 = a_promise(due_key="s10")
    assert overdue_promises([due_s10], "s02") == ()
    assert overdue_promises([due_s10], "s11") == (due_s10,)


def test_the_check_abstains_where_milestones_abstain() -> None:
    """No current key — a non-chronological template — returns nothing, and a promise
    with no due key is skipped rather than treated as always due."""
    assert overdue_promises([a_promise()], None) == ()
    assert overdue_promises([a_promise(due_key=None)], "s09") == ()


def test_a_paid_promise_is_never_overdue() -> None:
    assert overdue_promises([a_promise(status=PROMISE_PAID)], "s09") == ()


# -- the detector: advisory by construction ------------------------------------------------


def subject_with(promises: tuple[Promise, ...], current: str | None) -> DetectorInput:
    return DetectorInput(
        book_id=BOOK_ID,
        branch_id=BRANCH_ID,
        logical_id="sc9",
        open_promises=promises,
        story_order_key=current,
    )


def test_the_detector_is_in_the_loop_and_not_merely_written() -> None:
    """`IN_PROCESS` is the extension point and the only thing that runs a detector — the
    promise-with-no-caller shape §19.1 catalogues, refused the same way the duplicate
    detector refused it."""
    assert detect_overdue_promises in IN_PROCESS


def test_an_overdue_promise_is_a_minor_heuristic_finding() -> None:
    [found] = detect_overdue_promises(subject_with((a_promise(due_key="s05"),), "s09"))
    assert found.rule_or_critic_id == OVERDUE_RULE
    assert found.category == "promise_payoff", "the contract already had the category"
    assert found.severity is Severity.MINOR
    assert not found.blocks
    assert not found.deterministic, "model-sourced inputs; §10.4 owns the promotion"
    assert "gate_ledger" in found.message
    assert "s02" in found.message and "s05" in found.message and "s09" in found.message


def test_the_gate_passes_and_names_the_advisory_result_in_its_detail() -> None:
    """Through `gate_integrity`, which is the wired path: the finding is returned,
    recorded, and named on the decision — and the gate still passes, so `decide` accepts."""
    gate, findings = gate_integrity(subject_with((a_promise(due_key="s05"),), "s09"))
    assert gate.passed
    assert gate.vetoes == ()
    assert OVERDUE_RULE in (gate.detail or "")
    assert "advisory" in (gate.detail or "")
    assert [item.rule_or_critic_id for item in findings] == [OVERDUE_RULE]

    verdict, _ = decide((gate,), job_id="j", attempt=1, max_attempts=3)
    assert verdict is Outcome.ACCEPT, "decision accepted with the finding recorded"


def test_an_overdue_finding_never_parks_anything(store: SqliteStore) -> None:
    """The binding constraint stated as an assertion. A MAJOR finding recorded against a
    beat becomes standing and parks it pre-flight until dismissed; the spec forbids this
    feature that power, so the overdue finding is MINOR **and** heuristic — either alone
    keeps `gate_standing` passing, and this pins both ends: recorded in the store, read
    back the way the draft handler reads standing findings, and the pre-flight gate still
    passes."""
    [found] = detect_overdue_promises(subject_with((a_promise(due_key="s05"),), "s09"))
    store.record_findings(BOOK_ID, BRANCH_ID, [found], created_at="t")
    standing = store.findings(BOOK_ID, BRANCH_ID, logical_id="sc9", open_only=True)
    assert [item.finding_id for item in standing] == [found.finding_id]

    pre_flight = gate_standing(standing)
    assert pre_flight.passed, "an advisory instrument must never park the beat"
    assert pre_flight.vetoes == ()


def test_no_position_or_no_promises_means_silence() -> None:
    assert detect_overdue_promises(subject_with((a_promise(due_key="s05"),), None)) == []
    assert detect_overdue_promises(subject_with((), "s09")) == []


def test_a_rerun_converges_on_one_finding_id() -> None:
    first = detect_overdue_promises(subject_with((a_promise(due_key="s05"),), "s09"))
    second = detect_overdue_promises(subject_with((a_promise(due_key="s05"),), "s09"))
    assert [f.finding_id for f in first] == [f.finding_id for f in second]


# -- the zero-delta annotation -------------------------------------------------------------


def test_a_null_delta_mints_an_info_finding_against_the_scene(store: SqliteStore) -> None:
    revision = a_book()
    store.commit_revision(revision, created_at="2026-08-17T00:00:00Z")
    summarise_scene(store, revision, "sc4", ExtendedStub({"delta": None}))

    [found] = store.findings(BOOK_ID, BRANCH_ID, logical_id="sc4")
    assert found.rule_or_critic_id == SCENE_DELTA_RULE
    assert found.severity is Severity.INFO
    assert found.status is Status.OPEN
    assert not found.blocks
    assert not found.deterministic
    assert found.message == "no extractable value shift; dramatic_function unverified"
    standing = store.findings(BOOK_ID, BRANCH_ID, logical_id="sc4", open_only=True)
    assert gate_standing(standing).passed


def test_a_present_delta_lives_on_the_summary_row_and_mints_nothing(
    store: SqliteStore,
) -> None:
    revision = a_book()
    store.commit_revision(revision, created_at="2026-08-17T00:00:00Z")
    summarise_scene(store, revision, "sc4", ExtendedStub())

    assert store.findings(BOOK_ID, BRANCH_ID, logical_id="sc4") == []
    text = revision.node("sc4").content
    assert text is not None
    row = store._connection.execute(
        "SELECT delta_json FROM scene_summaries WHERE logical_id = ? AND content_hash = ?",
        ("sc4", content_hash(text)),
    ).fetchone()
    assert row is not None and row["delta_json"] is not None
    assert json.loads(row["delta_json"])["who"] == "Rook"


# -- surfacing: generation gets to SEE the ledger ------------------------------------------


def test_open_promises_render_in_the_packets_threads_section(store: SqliteStore) -> None:
    revision = a_book()
    store.commit_revision(revision, created_at="2026-08-17T00:00:00Z")
    store.record_promise(BOOK_ID, BRANCH_ID, a_promise())
    # A plan item so `packet_for`'s assembled packet has a premise to hold.
    store.record_plan_items(
        BOOK_ID,
        BRANCH_ID,
        [
            lc.PlanItem(
                logical_id="premise",
                kind=lc.PlanKind.PREMISE,
                text="Rook owes the Vane House forty gold he does not have.",
                authority=lc.PlanAuthority.INTENDED,
            )
        ],
        created_at="2026-08-17T00:00:00Z",
    )
    beat = beats_for(revision, template_for(revision))[8]
    packet = packet_for(store, revision, beat)
    [item] = packet.sections[THREADS]
    assert item.text == describe_owed(a_promise())
    assert "owes:" in item.text and "(due by s05)" in item.text
    assert item.authority.value == "derived", "a model's claim never enters as canon"
    assert "Open threads the book still owes" in packet.render()


def test_a_paid_promise_leaves_the_packet(store: SqliteStore) -> None:
    revision = a_book()
    store.commit_revision(revision, created_at="2026-08-17T00:00:00Z")
    store.record_promise(BOOK_ID, BRANCH_ID, a_promise())
    store.pay_promise(
        BOOK_ID,
        BRANCH_ID,
        promise_id_for(BOOK_ID, "gate_ledger"),
        paid_at_key="s04",
        paid_by_revision="rev-2",
    )
    packet = assemble(
        revision,
        "sc9",
        promises=tuple(store.promises(BOOK_ID, BRANCH_ID, open_only=True)),
    )
    assert packet.sections[THREADS] == ()
    assert "owes:" not in packet.render()


def test_a_packet_with_no_promises_is_byte_identical_to_before(store: SqliteStore) -> None:
    """The default path is unchanged: no ledger rows, no THREADS lines, no render drift."""
    revision = a_book()
    with_param = assemble(revision, "sc9", promises=())
    without_param = assemble(revision, "sc9")
    assert with_param.render() == without_param.render()
    assert with_param.sections[THREADS] == ()


def test_the_thread_vocabulary_is_untouched() -> None:
    """The map's first removal risk, pinned: promises are a separate home, and THREAD
    records still open on exact string equality — the comparator the packet, the
    summarizer's ground truth, and the status counts all share."""
    assert state_mod.THREAD_OPEN == "open"
    thread = lc.StateRecord(
        record_id="rec-t",
        kind=lc.StateRecordKind.THREAD,
        subject="sealed_letter",
        predicate="thread",
        value="open",
        story_position=lc.StoryPosition(order_key="s1"),
        authority=lc.StateAuthority.ACCEPTED_CANON,
        pov_visibility=[],
    )
    assert state_mod.open_threads([thread]) == (thread,)


# -- end to end on the deterministic provider ----------------------------------------------


def test_fake_provider_end_to_end_through_the_summary_handler(store: SqliteStore) -> None:
    """The whole wiring on the model-free provider, through the real registry.

    The fake synthesises a string where the schema wants an object-or-null, which is
    exactly the malformed-shape case: the summary lands, the delta reads as "no
    extractable value shift", the INFO finding is minted, and no promise row appears —
    the same behaviour a live model produces for a scene it reports nothing for.
    """
    revision = a_book()
    store.commit_revision(revision, created_at="2026-08-17T00:00:00Z")
    registry = ProviderRegistry(FakeProvider())
    summarise_scene(store, revision, "sc6", registry)

    text = revision.node("sc6").content
    assert text is not None
    assert store.scene_summaries(BOOK_ID, BRANCH_ID)["sc6"][content_hash(text)]
    [found] = store.findings(BOOK_ID, BRANCH_ID, logical_id="sc6")
    assert found.rule_or_critic_id == SCENE_DELTA_RULE
    assert store.promises(BOOK_ID, BRANCH_ID) == []


def test_a_scripted_fake_answer_drives_the_ledger_end_to_end(store: SqliteStore) -> None:
    """The same registry path with a conforming scripted answer: the text is parsed by the
    real `parse_schema_payload` against the extended schema, and the ledger moves."""
    revision = a_book()
    store.commit_revision(revision, created_at="2026-08-17T00:00:00Z")
    answer = {
        "setting": "The gate.",
        "characters": "Rook.",
        "events": "Rook swears to return for the ledger.",
        "open": "The ledger reading is owed.",
        "delta": {
            "who": "Rook",
            "what_changed": "obligation",
            "from": "none",
            "to": "sworn",
        },
        "promises_opened": [
            {"subject": "gate ledger", "description": "a reading is owed", "due_hint": 10}
        ],
        "promises_paid": [],
    }
    provider = FakeProvider()
    provider.set_responses([json.dumps(answer)])
    summarise_scene(store, revision, "sc2", ProviderRegistry(provider))

    [promise] = store.promises(BOOK_ID, BRANCH_ID, open_only=True)
    assert promise.subject == "gate_ledger"
    assert promise.due_key == "s10"
    assert store.findings(BOOK_ID, BRANCH_ID, logical_id="sc2") == [], "a delta was reported"
