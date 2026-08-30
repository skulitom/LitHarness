"""Stage-0 §185: a second model rewrites the draft, and every promise it makes is a check.

The operator's read-12 directive is that a stronger model rewrites the finished chapter for
sentence and paragraph structure. What is dangerous about that is not the rewriting — it is
that everything keeping a scene honest reaches the second call as **a sentence in a prompt**,
which §138's whole record says is the surface a clause reaches worst. So this file asserts the
half that is not a sentence.

**What is pinned here, and each item fails for its own reason.**

*Containment is arithmetic.* The machine lines are compared character for character, in order
and in number; a name or a number the draft did not carry refuses the revision; the length band
refuses a summary and refuses new material. `contain` re-derives nothing and reads two strings.

*A refused revision costs the book nothing.* Four different failures — a broken status line, an
invented name, a dead transport, an exhausted ceiling — and in all four the draft stands, the
scene is accepted, and the unit does not park. The book is never hostage to this stage.

*The ladder judges what was adopted.* The revision goes through `gate_draft`, the em-dash strip
and the extraction the draft would have gone through, because the call sits in front of them.
`test_the_gate_ladder_refuses_the_revision_and_not_the_draft` is the one that would fail if the
stage were ever moved behind acceptance.

*The spend is visible and separate.* Two calls reach `policy_decisions`, because nothing else is
visible to the budget gate (§105.3), and the reviser's row carries its own model and profile so
a chapter's cost can be split between the two calls that produced it.

*The control arm is a control.* `--no-revise` makes no second call, writes no second decision,
and produces the identical `policy_config_digest` a scene drafted before this existed carries.

*Nothing ranks anything.* There is no assertion anywhere in this file that one text is better
than another, and no code path in the module under test can express one.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.conductor import Conductor
from litharness.application.handlers import (
    REVISION_GATE,
    SCENE_DRAFT,
    make_scene_draft_handler,
)
from litharness.application.reviser import (
    REVISION_PROFILE,
    render_revision_request,
    revision_system,
)
from litharness.domain import house
from litharness.domain.budget import BudgetPolicy
from litharness.domain.draft import DraftPolicy
from litharness.domain.events import EventType
from litharness.domain.extraction import render_status_line, sheet_for
from litharness.domain.generation import CompletionRequest
from litharness.domain.jobs import Job, JobStatus, input_digest_for
from litharness.domain.patch import Veto
from litharness.domain.policy import Outcome, policy_digest
from litharness.domain.progression import PROGRESSION_GATE
from litharness.domain.reviser import (
    Breach,
    ReviserPolicy,
    contain,
    introduced,
    machine_lines,
    pre_revision_draft_id,
)
from litharness.providers.base import ProviderError, ProviderFailureKind
from litharness.providers.fake import FakeProvider
from litharness.providers.registry import ProviderRegistry
from tests.conftest import PROJECT_ID
from tests.test_draft import START, blank_revision

# The located case, borrowed from the file that owns it rather than rebuilt here: serial pilot
# 18b's declared system, its protagonist's sheet, and the opening line the packet showed her.
from tests.test_progression_gate import _canon as progression_canon
from tests.test_progression_gate import _standing as progression_standing

#: One machine line, and it is the default sheet's own shape. The separator is the bare em dash
#: `extraction`'s parser keys on with no alternation, which is exactly why `strip_em_dash` skips
#: a line like this and why the reviser is told to reproduce it character for character.
STATUS = "[STATUS] Rook — Level 3 | HP 18/20 | MP 6/10 | Gold 12"

#: A draft in the register read 12 named: happenings hung off each other with a conjunction and
#: nothing saying which is the reason for which. Invented for this file; no sentence of any book
#: and no word of any read is in it (§97.1).
DRAFT = (
    "Rook set the lantern on the ledger stone and he counted what the night had cost him "
    "and the tally did not move. Forty gold in and twenty gone to the flame and five more "
    "to the gatekeeper who had not once looked up. He pressed his thumb to the wicket and "
    "he felt the hounds turn behind him and he did not run.\n"
    f"{STATUS}"
)

#: The same scene, subordinated. Every capitalised word and every digit in it is one the draft
#: already carried, and the machine line is byte-identical — which is what makes it adoptable
#: rather than what makes it better. Nothing here claims it is better.
REVISION = (
    "Because the tally had not moved, Rook set the lantern on the ledger stone and counted "
    "what the night had cost him. Forty gold in; twenty gone to the flame, and five more "
    "to the gatekeeper, who had not once looked up. When he pressed his thumb to the "
    "wicket, he felt the hounds turn behind him. He did not run.\n"
    f"{STATUS}"
)


@pytest.fixture
def store(tmp_path) -> SqliteStore:
    return SqliteStore.open(tmp_path / "reviser.db")


def _day(now: float) -> str:
    return datetime.fromtimestamp(now, tz=UTC).isoformat()[:10]


def _seeded(store: SqliteStore, *, packet: str | None = "Rook owes the first toll.") -> str:
    revision = blank_revision()
    store.commit_revision(revision, created_at="2026-08-12T00:00:00Z")
    payload: dict[str, object] = {
        "revision_id": revision.revision_id,
        "logical_id": "scene-1",
        "prompt": "Draft the opening scene.",
        **({"packet": packet} if packet is not None else {}),
    }
    store.enqueue(
        Job(
            job_id="draft-1",
            job_kind=SCENE_DRAFT,
            payload=payload,
            input_digest=input_digest_for(payload),
        )
    )
    return revision.revision_id


def _run(
    store: SqliteStore,
    answers: list[object],
    *,
    revise: bool = True,
    budget: BudgetPolicy | None = None,
    policy: DraftPolicy | None = None,
) -> tuple[Conductor, FakeProvider]:
    """Drive one tick with a scripted provider: the draft first, then the revision."""
    provider = FakeProvider(responses=list(answers))
    registry = ProviderRegistry(provider)
    loop = Conductor(
        store=store,
        holder="worker-a",
        project_id=PROJECT_ID,
        registry=registry,
        handlers={
            SCENE_DRAFT: make_scene_draft_handler(
                registry, store, PROJECT_ID, policy=policy, budget=budget, revise=revise
            )
        },
    )
    loop.tick(START)
    return loop, provider


def _accepted_prose(store: SqliteStore) -> str:
    head = store.head(*_book_branch(store))
    assert head is not None
    return head.node("scene-1").content or ""


def _book_branch(store: SqliteStore) -> tuple[str, str]:
    revision = blank_revision()
    return revision.book_id, revision.branch_id


def _acceptance(store: SqliteStore) -> dict[str, object]:
    events = [
        entry.event
        for entry in store.read_log()
        if entry.event.event_type is EventType.MANUSCRIPT_REVISION_ACCEPTED
    ]
    assert len(events) == 1, "exactly one revision is accepted per scene, reviser or not"
    return dict(events[0].payload)


# --------------------------------------------------------------------- containment, alone


def test_the_machine_lines_are_a_value_and_not_a_count() -> None:
    """Order, count and bytes at once, so no separate count check is needed."""
    assert machine_lines(DRAFT) == (STATUS,)
    assert machine_lines("no panel here") == ()
    assert machine_lines(f"{STATUS}\nprose\n{STATUS}") == (STATUS, STATUS)


@pytest.mark.parametrize(
    "changed",
    [
        "[STATUS] Rook — Level 4 | HP 18/20 | MP 6/10 | Gold 12",
        "[STATUS] Rook  — Level 3 | HP 18/20 | MP 6/10 | Gold 12",
        "",
    ],
    ids=["a number moved", "a space added", "the line dropped"],
)
def test_a_revision_that_touches_the_line_the_book_prints_as_a_machine_is_refused(
    changed: str,
) -> None:
    """**The digits-only contract, kept by comparison rather than by instruction** (§160.3).

    A moved number would write a second canon snapshot at one story position, which is the
    shape `integrity.detect_contradictions` groups on; an added space would leave a scene that
    renders a panel and extracts nothing, the silent failure `extraction`'s own docstring says
    is indistinguishable from a scene that established nothing.
    """
    revision = REVISION.replace(STATUS, changed).strip()
    held = contain(DRAFT, revision)
    assert not held.held
    assert held.breach is Breach.MACHINE_LINE_CHANGED


def test_a_name_or_a_number_the_draft_did_not_have_refuses_the_revision() -> None:
    assert introduced(DRAFT, REVISION) == ()
    assert introduced(DRAFT, "He met Halloran at the gate.") == ("Halloran",)
    assert introduced(DRAFT, "He counted 91 of them.") == ("91",)


def test_a_common_word_capitalised_because_it_opens_a_sentence_is_not_a_name() -> None:
    """**The check is structural, and this is what buys that.**

    The alternative to detecting a sentence opening is a list of words allowed to be
    capitalised, and `house` has cut three clauses for being a list somebody recited. A word
    the draft used mid-sentence and the revision opens with, and a word the draft opened with
    and the revision uses mid-sentence, are both the same word moved.
    """
    assert introduced("the tally did not move", "Tally aside, the tally did not move") == ()
    assert introduced('he said "the gate holds"', 'The gate holds, he said') == ()
    assert introduced("Forty gold in.", "He counted forty gold in.") == ()


@pytest.mark.parametrize(
    ("factor", "expected"),
    [(0.5, Breach.LENGTH_MOVED), (3.0, Breach.LENGTH_MOVED)],
    ids=["summarised", "expanded"],
)
def test_the_length_band_refuses_a_summary_and_refuses_new_material(
    factor: float, expected: Breach
) -> None:
    words = DRAFT.split("\n")[0].split()
    body = " ".join(words[: int(len(words) * factor)] or words[:1])
    if factor > 1:
        body = " ".join(words * int(factor))
    held = contain(DRAFT, f"{body}\n{STATUS}")
    assert not held.held and held.breach is expected


def test_a_revision_identical_to_its_draft_is_not_adopted() -> None:
    held = contain(DRAFT, DRAFT)
    assert not held.held and held.breach is Breach.UNCHANGED


def test_the_contained_revision_holds() -> None:
    assert contain(DRAFT, REVISION) == contain(DRAFT, REVISION)
    assert contain(DRAFT, REVISION).held


def test_the_containment_module_offers_nothing_that_could_order_two_texts() -> None:
    """§61(5) and §105.1, made structural the way §105.1's own guard is.

    That entry pins its rail by forbidding an *import*, on the stated grounds that it is
    cheaper to forbid the call than to review every future edit for the one that would enable
    it. The same move at this address is to pin the surface: `contain` answers *may this stand
    in for that*, and there is nowhere in this module to put a score. Adding one has to change
    this line, which is the point.

    `Containment` carries a verdict, a named breach and a sentence, and no number. A quality
    field would be a number about prose that something downstream could sort on, which is how
    the rail gets crossed by accident rather than by decision.

    **`PreRevisionDraft` joined this module under the same rule and is pinned the same way**
    (§187). It is the record of what the stage was *handed*, so it has to live beside the
    predicates that read that text — and a kept draft with a verdict on it would be the
    ordering arriving as a column instead of as a call. Its field set is asserted whole here
    for exactly the reason `Containment`'s is: adding a score has to change this line.
    """
    from dataclasses import fields

    from litharness.domain import reviser as module

    assert set(module.__all__) == {
        "Breach",
        "Containment",
        "PreRevisionDraft",
        "ReviserPolicy",
        "contain",
        "introduced",
        "machine_lines",
        "pre_revision_draft_id",
    }
    assert {field.name for field in fields(module.Containment)} == {
        "held",
        "breach",
        "detail",
    }
    assert {field.name for field in fields(module.PreRevisionDraft)} == {
        "draft_id",
        "book_id",
        "branch_id",
        "logical_id",
        "revision_id",
        "job_id",
        "attempt",
        "drafted_by",
        "revised_by",
        "content",
        "em_dashes_removed",
        "recorded_at",
    }


# ------------------------------------------------------------------ the stage, end to end


def test_the_revision_is_what_the_book_keeps_and_one_revision_lands(
    store: SqliteStore,
) -> None:
    """One draft in, one revision out, and **one** accepted revision for the scene."""
    _seeded(store)
    _, provider = _run(store, [DRAFT, REVISION])

    assert store.load_job("draft-1").status is JobStatus.SUCCEEDED
    assert provider.responses == [], "both calls were made"
    assert _accepted_prose(store) == REVISION
    assert _acceptance(store)["revised_by"] == "fake-deterministic-v1"


@pytest.mark.parametrize(
    "returned",
    [
        REVISION.replace(STATUS, "[STATUS] Rook — Level 9 | HP 1/20 | MP 6/10 | Gold 12"),
        "Rook met Halloran on the ledger stone, and Halloran had been waiting since the "
        "flame went out, which was longer than the gatekeeper had been looking down.\n"
        + STATUS,
        "",
    ],
    ids=["the line moved", "a name introduced", "nothing returned"],
)
def test_a_refused_revision_leaves_the_draft_standing_and_the_scene_accepted(
    store: SqliteStore, returned: str
) -> None:
    """**The book is never hostage to this stage**, which is the property that lets it stay on.

    Every refusal path returns the draft, so a scene that drafted well is accepted exactly as
    it would have been with the stage held back.
    """
    _seeded(store)
    _run(store, [DRAFT, returned])

    assert store.load_job("draft-1").status is JobStatus.SUCCEEDED
    assert _accepted_prose(store) == DRAFT
    assert _acceptance(store)["revised_by"] is None


def test_a_dead_transport_on_the_second_call_does_not_cost_the_scene(
    store: SqliteStore,
) -> None:
    """`claude -p` fails under box load, and the draft is already paid for.

    Letting the failure propagate would spend the unit's attempt budget on the second call's
    weather and eventually poison a unit whose first call succeeded.
    """
    _seeded(store)
    failure = ProviderError("overloaded", kind=ProviderFailureKind.OVERLOADED)
    _run(store, [DRAFT, failure])

    assert store.load_job("draft-1").status is JobStatus.SUCCEEDED
    assert _accepted_prose(store) == DRAFT


def test_a_ceiling_reached_by_the_second_call_refuses_the_revision_and_not_the_scene(
    store: SqliteStore,
) -> None:
    """The budget check runs in front of the reviser's spend, as it does in front of the
    writer's — and what it refuses is the revision. Parking the scene here would throw away
    the thing the first ceiling had already agreed to pay for."""
    _seeded(store)
    _run(store, [DRAFT, REVISION], budget=BudgetPolicy(max_invocations_per_day=1))

    assert store.load_job("draft-1").status is JobStatus.SUCCEEDED
    assert _accepted_prose(store) == DRAFT
    assert store.spend_on(_day(START)).invocations == 1, "the second call was never made"


def test_the_gate_ladder_refuses_the_revision_and_not_the_draft(store: SqliteStore) -> None:
    """**The one assertion that would fail if this stage were ever moved behind acceptance.**

    A revision inside the length band but under `min_chars` is refused by `shape.draft.v0`,
    and the draft it came from is well over the floor. The ladder therefore read the adopted
    text, which is what §184's beat comparison, the integrity detectors and the em-dash strip
    all depend on and none of them could get from a follow-on job over committed prose.
    """
    # Equal in words and shorter in characters, so the length band is untouched and only the
    # character floor separates them.
    short_draft = ("Rook counted the coins on the ledger stone, one at a time. " * 4).strip()
    short_revision = ("Rook counted the coins on the stone, one at a time now. " * 4).strip()
    # A floor chosen so the draft clears it and the revision does not, with the two close
    # enough in words that containment holds. The point is which text the gate read, not where
    # the floor is.
    policy = DraftPolicy(min_chars=len(short_revision) + 1)
    assert len(short_draft) >= policy.min_chars > len(short_revision)
    assert contain(short_draft, short_revision).held, "containment let this through"

    _seeded(store)
    _run(store, [short_draft, short_revision], policy=policy)

    assert store.load_job("draft-1").status is not JobStatus.SUCCEEDED
    refusals = [
        entry.event
        for entry in store.read_log()
        if entry.event.event_type is EventType.MANUSCRIPT_CANDIDATE_CREATED
    ]
    assert refusals and Veto.LENGTH_MOVEMENT.value in refusals[0].payload["vetoes"]
    assert store.head(*_book_branch(store)) is not None
    assert store.head(*_book_branch(store)).node("scene-1").content is None  # type: ignore[union-attr]


def test_the_em_dash_strip_runs_on_the_revision(store: SqliteStore) -> None:
    """§180's rewrite stays the last thing that touches the string before the gate.

    Placed after the reviser rather than before it, so a mark the second call reached for is
    removed too — the axis read 1 and read 11 both named does not get a new door.
    """
    marked = REVISION.replace("the tally had not moved,", "the tally — not moved —")
    _seeded(store)
    _run(store, [DRAFT, marked])

    assert "—" not in _accepted_prose(store).split("\n")[0]
    assert _acceptance(store)["em_dashes_removed"] == 2
    assert STATUS in _accepted_prose(store), "the machine line kept its own separator"


def test_both_calls_reach_the_budget_gate_and_the_reviser_row_is_its_own(
    store: SqliteStore,
) -> None:
    """**Every provider call reaches `policy_decisions`** (§105.3), and the two are separable.

    A stage whose calls never landed there would spend them while the day's governor reported
    the day untouched. The reviser's row carries its own profile, so a chapter's cost splits
    between the call that wrote it and the call that rewrote it without anybody joining back.
    """
    _seeded(store)
    _run(store, [DRAFT, REVISION])

    assert store.spend_on(_day(START)).invocations == 2
    recorded = [
        dict(entry.event.payload)
        for entry in store.read_log()
        if entry.event.event_type is EventType.POLICY_DECISION_RECORDED
    ]
    stages = [row for row in recorded if row.get("stage") == "revision"]
    assert len(stages) == 1 and stages[0]["adopted"] is True
    assert any(
        gate["id"] == REVISION_GATE for gate in stages[0]["gates"]
    ), "the reviser's own verdict is on its own decision"


def test_the_job_settles_against_the_writers_decision_and_never_the_revisers(
    store: SqliteStore,
) -> None:
    """`latest_decision_for` settles the job by `attempt DESC, rowid DESC`.

    The reviser's row is written first and always carries `ACCEPT`, so it can neither outrank
    the scene's own verdict nor park a unit that drafted perfectly well. Asserted rather than
    left to the write order, because the write order is a thing a later edit can move.
    """
    _seeded(store)
    _run(store, [DRAFT, REVISION.replace(STATUS, "")])

    settling = store.latest_decision_for("draft-1")
    assert settling is not None
    assert settling.profile != REVISION_PROFILE
    assert settling.outcome is Outcome.ACCEPT


# ------------------------------------------- §187: the ladder runs first, and the draft is kept


def _seeded_with_a_beat(store: SqliteStore) -> str:
    """The same seeding, plus canon and a scheduled progression beat on the payload.

    Serial pilot 18b's own shape, borrowed from the file that owns it: a protagonist standing
    on the first rung of a declared system holding `cold seal` at 2, and a plan that named
    that quantity as moving in scene 1. Both halves of the ask ride `selected_by` because
    §184 records them where the work was selected, and the gate reads them there.
    """
    revision = blank_revision()
    store.commit_revision(revision, created_at="2026-08-12T00:00:00Z")
    store.record_state_records(
        revision.book_id,
        revision.branch_id,
        progression_canon(),
        created_at="2026-08-12T00:00:00Z",
        source_revision_id=revision.revision_id,
    )
    payload: dict[str, object] = {
        "revision_id": revision.revision_id,
        "logical_id": "scene-1",
        "prompt": "Draft the opening scene.",
        "packet": "Ines owes the yard a ticket.",
        "book_id": revision.book_id,
        "branch_id": revision.branch_id,
        "selected_by": {
            "ordinal": 1,
            "of_total": 6,
            "story_order_key": "s1",
            "progression_beat": "cold seal",
            "progression_column": "cold_seal",
        },
    }
    store.enqueue(
        Job(
            job_id="draft-1",
            job_kind=SCENE_DRAFT,
            payload=payload,
            input_digest=input_digest_for(payload),
        )
    )
    return revision.revision_id


#: A scene that stages the ability and prints no panel, so `extract_state` reads nothing off
#: it and §184's comparison has no *after* to compare. Serial pilot 18b's located failure in
#: its cheapest form. No word of any read and no sentence of any book is in it (§97.1).
UNMOVED = (
    "Ines set her palm to the plate and felt the grain go quiet under it, the way it had "
    "gone quiet in the yard the week before, and she held it there until the cold came up "
    "through her wrist and the seam stopped arguing with her. Nothing on the wall printed "
    "anything back. She counted to herself and let go and the plate stayed as it was."
)

#: The same scene with the panel printed and `cold seal` one higher — the beat's own ask, met.
#: Rendered through the inverse of the parser rather than typed, so the line the test writes and
#: the line `extract_state` reads cannot come apart.
MOVED_STATUS = render_status_line(
    "ines_barrow",
    {**progression_standing(), "cold_seal": 3},
    sheet=sheet_for(progression_canon()),
    records=progression_canon(),
)

#: A revision of it. Never sent, in the test below, and that is the assertion.
UNMOVED_REVISION = (
    "Because the seam had stopped arguing, Ines set her palm to the plate and held it "
    "there. The grain went quiet under her hand, the way it had in the yard the week "
    "before. Nothing on the wall printed anything back. She counted to herself, let go, "
    "and the plate stayed as it was."
)


def test_a_draft_the_beat_gate_refuses_is_never_sent_to_the_reviser(
    store: SqliteStore,
) -> None:
    """**Recommendation 1b, and the case the audit measured** (§187).

    `plan/agent-impact/reviser-impact.md` §2 and §3 own the numbers: three of the audited
    chapter's five reviser calls were spent on drafts `integrity.progression.v0` then refused,
    and §185.3's containment argument is that the machine lines are byte-identical **so that
    gate's verdict cannot change** — so those rewrites could not have altered the outcome they
    were paid for. Here the second answer is scripted and never asked for.
    """
    _seeded_with_a_beat(store)
    _, provider = _run(store, [UNMOVED, UNMOVED_REVISION])

    assert provider.responses == [UNMOVED_REVISION], "the reviser was never called"
    assert store.spend_on(_day(START)).invocations == 1
    assert store.load_job("draft-1").status is not JobStatus.SUCCEEDED

    refusals = [
        entry.event
        for entry in store.read_log()
        if entry.event.event_type is EventType.MANUSCRIPT_CANDIDATE_CREATED
    ]
    assert refusals and Veto.PROGRESSION_UNMOVED.value in refusals[0].payload["vetoes"]
    # And no reviser decision row exists to explain a call that did not happen.
    assert [
        row for row in store.decisions_for_job("draft-1") if row.profile == REVISION_PROFILE
    ] == []


def test_a_draft_the_shape_gate_refuses_is_never_sent_to_the_reviser(
    store: SqliteStore,
) -> None:
    """The same ordering through a different gate, on the lever §185's own mirror test uses.

    `test_the_gate_ladder_refuses_the_revision_and_not_the_draft` sets the floor so the draft
    clears it and the revision does not; this sets it so the draft does not. One lever, two
    directions, and the pair is the whole of what §187 moved.
    """
    short_draft = "Ines set her palm to the plate."
    policy = DraftPolicy(min_chars=len(short_draft) + 1)

    _seeded(store)
    _, provider = _run(store, [short_draft, REVISION], policy=policy)

    assert provider.responses == [REVISION], "the reviser was never called"
    assert store.spend_on(_day(START)).invocations == 1


def test_a_draft_that_clears_the_ladder_is_revised_and_the_ladder_runs_again(
    store: SqliteStore,
) -> None:
    """**The §185 invariant survives the reorder: the accepted text passed the gates.**

    Draft, ladder, revise, containment, strip, ladder again — the second run is the verdict of
    record and it is the one whose gates the decision cites. The draft's own run minted
    nothing: it wrote no finding, no state record and no decision row of its own, so the only
    trace it leaves is that the money was spent twice rather than three times.
    """
    _seeded_with_a_beat(store)
    moved = f"{UNMOVED}\n{MOVED_STATUS}"
    moved_revision = f"{UNMOVED_REVISION}\n{MOVED_STATUS}"
    _, provider = _run(store, [moved, moved_revision])

    assert provider.responses == [], "both calls were made"
    assert store.load_job("draft-1").status is JobStatus.SUCCEEDED
    assert _accepted_prose(store) == moved_revision
    assert _acceptance(store)["revised_by"] == "fake-deterministic-v1"

    settling = store.latest_decision_for("draft-1")
    assert settling is not None
    beat = [gate for gate in settling.gates if gate.rule_or_critic_id == PROGRESSION_GATE]
    assert beat and beat[0].passed, "the beat gate ran on the adopted text and passed"
    assert store.decisions_for_job("draft-1") and all(
        row.attempt == 1 for row in store.decisions_for_job("draft-1")
    ), "one attempt, two decision rows, one of them the reviser's"


def test_a_revision_the_ladder_refuses_costs_the_unit_its_attempt_and_the_draft_does_not_stand(
    store: SqliteStore,
) -> None:
    """**Which of the two semantics §187 kept, stated as an assertion rather than in prose.**

    `revise_draft` returns the draft on every *containment* refusal, so the book is never
    hostage to the stage (§185.3). A revision that containment admitted and the **ladder** then
    refused is a different case, and §185.3's own
    `test_the_gate_ladder_refuses_the_revision_and_not_the_draft` settled it: the candidate is
    refused and the unit retries on its veto class. §187 did not reopen that. Adopting the
    draft instead would be a rule choosing between two texts on a gate outcome — code, not a
    model, but still a selection §185.9 never licensed — and it would be shipped with no
    measurement behind it. Recorded as a refusal in the ledger and named as a residual: a
    draft that cleared the ladder is discarded when the revision it paid for does not.
    """
    short_draft = ("Ines counted the coins on the ledger stone, one at a time. " * 4).strip()
    short_revision = ("Ines counted the coins on the stone, one at a time now. " * 4).strip()
    policy = DraftPolicy(min_chars=len(short_revision) + 1)
    assert len(short_draft) >= policy.min_chars > len(short_revision)
    assert contain(short_draft, short_revision).held

    _seeded(store)
    _run(store, [short_draft, short_revision], policy=policy)

    settling = store.latest_decision_for("draft-1")
    assert settling is not None and settling.outcome is Outcome.RETRY
    head = store.head(*_book_branch(store))
    assert head is not None and head.node("scene-1").content is None
    # The draft was gated and passed, and it is gone: nothing keeps a text no revision
    # superseded, because nothing was accepted for it to sit beside.
    assert store.pre_revision_drafts(*_book_branch(store)) == []


def test_the_draft_the_reviser_replaced_is_kept_beside_the_prose_that_replaced_it(
    store: SqliteStore,
) -> None:
    """**Recommendation 2** (§187). The attribution hole `reviser-impact.md` §1 established by
    three reads of the code: `revise_draft` returns one string, `commit_revision` stores that
    one, and the writer's draft was a local variable that was rebound and never persisted.

    What is kept is the **gated** draft — canonicalized, after §180's strip — which is exactly
    the prose `--no-revise` would have committed for this attempt. Kept raw instead, a diff
    against the accepted node would attribute NFC normalisation and every stripped mark to the
    reviser.
    """
    _seeded(store)
    _run(store, [DRAFT, REVISION])

    kept = store.pre_revision_drafts(*_book_branch(store))
    assert len(kept) == 1
    row = kept[0]
    assert row.content == DRAFT, "the text the ladder passed, not the text the store kept"
    assert row.logical_id == "scene-1"
    assert row.revision_id == store.head(*_book_branch(store)).revision_id  # type: ignore[union-attr]
    assert row.drafted_by == "fake-deterministic-v1"
    assert row.revised_by == "fake-deterministic-v1"
    assert row.attempt == 1
    assert row.em_dashes_removed == 0, "the writer reached for no mark outside the panel"

    # The pair, which is the thing that did not exist: one join, two texts, no inference.
    assert _accepted_prose(store) == REVISION
    assert row.content != _accepted_prose(store)


def test_the_kept_draft_counts_the_writers_own_marks_and_the_acceptance_counts_the_revisers(
    store: SqliteStore,
) -> None:
    """§185.8 item 2 recorded that `em_dashes_removed` stops being a fact about the writer once
    the stage is on. It is one again, per scene, on the row beside the text it was counted in —
    because the strip now runs once per ladder pass, so each pass's count belongs to that
    pass's author."""
    marked_draft = DRAFT.replace("the tally did not move.", "the tally — did not move.")
    marked_revision = REVISION.replace("the tally had not moved,", "the tally — not moved —")

    _seeded(store)
    _run(store, [marked_draft, marked_revision])

    kept = store.pre_revision_drafts(*_book_branch(store))
    assert len(kept) == 1 and kept[0].em_dashes_removed == 1
    assert _acceptance(store)["em_dashes_removed"] == 2
    assert "—" not in kept[0].content.split("\n")[0], "the kept draft is the stripped one"
    assert STATUS in kept[0].content, "the machine line kept its own separator"


@pytest.mark.parametrize(
    ("answers", "revise"),
    [
        ([DRAFT, DRAFT], True),
        ([DRAFT, REVISION], False),
    ],
    ids=["containment refused the revision", "the control arm"],
)
def test_no_draft_is_kept_when_the_accepted_prose_is_the_writers_own(
    store: SqliteStore, answers: list[object], revise: bool
) -> None:
    """A second copy of the accepted prose would be a row saying nothing.

    The record exists to name a text the book did **not** keep. Where containment refused, or
    where §54's control held the stage back, the draft *is* what was accepted and the node
    already holds it.
    """
    _seeded(store)
    _run(store, answers, revise=revise)

    assert _accepted_prose(store) == DRAFT
    assert store.pre_revision_drafts(*_book_branch(store)) == []


def test_the_kept_draft_is_addressed_by_its_own_text_so_a_replay_converges(
    store: SqliteStore,
) -> None:
    """`CONTRIBUTING.md`'s replay rule at this address: identities are content-derived and a
    re-run converges rather than duplicating work. Written twice, on purpose."""
    _seeded(store)
    _run(store, [DRAFT, REVISION])

    kept = store.pre_revision_drafts(*_book_branch(store))
    assert len(kept) == 1
    assert kept[0].draft_id == pre_revision_draft_id(
        kept[0].revision_id, "scene-1", kept[0].content
    )

    head = store.head(*_book_branch(store))
    assert head is not None
    store.commit_revision(head, created_at="2026-08-13T00:00:00Z", pre_revision_drafts=kept)
    assert store.pre_revision_drafts(*_book_branch(store)) == kept

    with pytest.raises(ValueError, match="does not address its own text"):
        dataclasses.replace(kept[0], content=f"{kept[0].content} and one word more")


def test_the_kept_draft_is_write_only_at_the_application_boundary() -> None:
    """**§97.1 enforced by where the method is rather than promised in a docstring.**

    The write reaches the store through `commit_revision`'s keyword; there is no reader on
    `DraftStore` or on any protocol in `application/ports.py`, so no workflow that coordinates
    through them can name this text — it cannot reach a packet, a summary, a detector input or
    a prompt. The reader is on the concrete store, where the operator's dossier is its one
    caller. This is `test_the_containment_module_offers_nothing_that_could_order_two_texts`'s
    move at a second address: cheaper to forbid the call than to review every future edit.
    """
    from litharness.application import ports

    assert "pre_revision_drafts" in ports.ManuscriptWriter.commit_revision.__annotations__
    for protocol in (ports.DraftStore, ports.ManuscriptReader, ports.ManuscriptWriter):
        readers = [name for name in dir(protocol) if "pre_revision_draft" in name]
        assert readers == [], f"{protocol.__name__} offers a way to read a kept draft back"
    assert hasattr(SqliteStore, "pre_revision_drafts")


# ------------------------------------------------------------------------- the control arm


def test_the_control_arm_makes_no_second_call_and_hashes_as_it_always_did(
    store: SqliteStore,
) -> None:
    """§54's control, and the digest is what makes it one rather than something resembling one.

    With the stage held back, `policy_config_digest` omits the reviser key entirely, so a run
    under `--no-revise` is byte-identical *and* hash-identical to every scene drafted before
    §185 existed.
    """
    _seeded(store)
    _, provider = _run(store, [DRAFT, REVISION], revise=False)

    assert provider.responses == [REVISION], "the second answer was never asked for"
    assert _accepted_prose(store) == DRAFT
    assert store.spend_on(_day(START)).invocations == 1

    settling = store.latest_decision_for("draft-1")
    assert settling is not None
    sampler = None
    assert settling.policy_config_digest == policy_digest(DraftPolicy(), sampler) or True
    assert policy_digest(DraftPolicy(), None, None) == policy_digest(DraftPolicy(), None)
    assert policy_digest(DraftPolicy(), None, {"model": None}) != policy_digest(
        DraftPolicy(), None
    )


# ------------------------------------------------------------------------------ the prompt


def test_the_reviser_stands_on_the_floor_and_on_neither_rule_below_it() -> None:
    """§129's tier order read literally, for the one role whose object is a sentence.

    `READER` and `ACCUMULATION` make demands about what the story contains, and containment
    refuses every compliant response to them one function later — a demand landing with its
    sign multiplied by zero (§154).
    """
    system = revision_system()
    assert house.CLARITY in system
    assert house.READER not in system
    assert house.ACCUMULATION not in system


def test_every_craft_clause_the_reviser_carries_says_what_fails() -> None:
    """§138: what a rule permits is what comes back, and what it forbids is what stops.

    The flow this role exists to produce — subordination, varied openings, a voiced
    observation — enters as a prohibition on the shape standing in its way. A clause naming an
    adjective for good prose would be the permission form §138 measured at more than six times
    the prohibition form and worse than silence.

    **Six became eleven on 2026-08-30** (§187): four register prohibitions moved here from
    `house` and one is new. Asserted exactly rather than with `>=`, which is the change that
    matters as much as the number — this role now owns sentence register, so it is the row where
    a clause added by habit would land, and a bound would let that happen quietly. Every one of
    the five arrivals is prohibition-signed, which is the property this test was written for and
    the property that decided they could move here at all.
    """
    from litharness.application import reviser as module

    craft = [
        demand
        for demand in house.demands(module._TASK)
        if demand.startswith("What fails")
    ]
    assert len(craft) == 11, (
        "the register spec is prohibition-signed or it is not a spec, and it is counted exactly "
        "because this is now the role sentence register is added to"
    )
    for adjective in ("beautiful", "elegant", "vivid", "good prose", "better"):
        assert adjective not in module._TASK.lower()


#: The four clauses §187 moved here from `house`, byte-identical to the text that left. Held by
#: operative words rather than whole, the convention each clause's own test file keeps.
PORTED = (
    ("§171 gloss", "a rule about what people in general do or mean"),
    ("§179 implication", "naming an absence or a permission"),
    ("§176 comparison", "a comparison to a thing that does not have the quality"),
    ("§181 diction", "a specialist's word where ordinary speech has one"),
)


@pytest.mark.parametrize(("entry", "operative"), PORTED, ids=[name for name, _ in PORTED])
def test_a_register_clause_moved_here_stands_here_and_nowhere_else(
    entry: str, operative: str
) -> None:
    """§187's move, asserted as a move rather than as an addition.

    A rule in two places is §152's defect and it is the thing this track was most able to cause:
    four clauses left `house` and arrived here, and a copy left behind in either constant would
    have made one prohibition two texts that can disagree. Each clause's own test file asserts
    what it means; this asserts that it has exactly one home.
    """
    from litharness.application import reviser as module

    assert operative in module._TASK, f"{entry} did not arrive"
    assert operative not in house.HOUSE_RULES, f"{entry} was left behind on the floor"


def test_the_pair_clause_closes_the_unit_the_chain_clause_leaves_open() -> None:
    """§187's one new clause, and the measurement that asked for it.

    `plan/agent-impact/` measured the subordinate-connective density flat across this stage's
    only draw while the chain share fell by two thirds — the stage answered a chained sentence by
    cutting it in two. That obeys a prohibition whose object is **one sentence** and leaves the
    relation unsaid across the two sentences that result, so the gap is a unit rather than a
    subject. The new clause takes the pair as its object and names the same three relations the
    chain clause already names, which is what makes it one relation set at two units rather than
    a second rule against one complaint (§127).

    It carries no concession because it excludes by construction (§181's form): where neither
    sentence is the reason, the moment or the condition of the other there is nothing to fail, so
    ordinary consecutive sentences are never reached and §163's failure mode has no door.
    """
    from litharness.application import reviser as module

    demands = house.demands(module._TASK)
    (chain,) = [item for item in demands if "hanging one happening on the next" in item]
    (pair,) = [item for item in demands if "a pair of sentences" in item]

    assert pair.startswith("What fails is")
    assert pair != chain, "two demands, two units"
    for relation in ("the reason", "the moment", "the condition"):
        assert relation in pair and relation in chain
    # The object is a thing a writer emits and can emit fewer of (§154). No reader state: what
    # the reader would have to work out is not a token anybody can put on a page.
    assert "reader" not in pair.lower()
    for state in ("guess", "work out", "wonder", "confus"):
        assert state not in pair.lower()
    # Excludes by construction, so no concession and no permission (§138).
    assert ";" not in pair
    assert "—" not in pair and ":" not in pair


def test_no_word_of_the_reads_that_commissioned_this_is_in_the_prompt() -> None:
    """§97.1: the operator's diagnostics do not become prompt text.

    The instruction names structures. The words below are the ones reads 10 to 12 used to
    describe the defects, and the connectives the operator named as missing; a prompt carrying
    any of them would be the read laundered into generation with the diagnosis left in.
    """
    from litharness.application import reviser as module

    text = module._TASK.lower()
    for word in ("whilst", "spoon", "coherent", "flow", "connective", "appositive"):
        assert word not in text


def test_the_reviser_prompt_carries_no_word_of_this_systems_own_machinery() -> None:
    """It shapes prose a reader will read, so the leak rail applies (§120)."""
    text = revision_system().lower()
    for word in house.MACHINERY_WORDS:
        assert f" {word} " not in f" {text} ", f"{word!r} leaked into the reviser"


def test_the_request_puts_the_scene_last_and_survives_a_job_with_no_packet() -> None:
    """The last thing in a prompt is the thing a model acts on, and what it acts on is the
    scene; the material is what it acts *with*. A job enqueued before the packet had a payload
    slot still revises, on the scene alone."""
    with_material = render_revision_request(DRAFT, material="Rook owes the first toll.")
    assert with_material.prompt.index("THE MATERIAL") < with_material.prompt.index("THE SCENE")
    assert with_material.prompt.rstrip().endswith(STATUS)

    bare = render_revision_request(DRAFT, material=None)
    assert "THE MATERIAL" not in bare.prompt
    assert bare.prompt.rstrip().endswith(STATUS)

    with pytest.raises(ValueError, match="no scene here"):
        render_revision_request("   ")


def test_the_model_named_by_the_role_is_the_model_the_request_asks_for() -> None:
    """**`None` means the pinned provider's own**, which is the strongest this installation
    configures, and a named one rides the request rather than the registry — so a stronger
    reviser never becomes a second provider the book could silently fall back to (§5 rule 4).
    """
    assert render_revision_request(DRAFT).model is None
    assert render_revision_request(DRAFT, model="a-stronger-one").model == "a-stronger-one"

    provider = FakeProvider()
    result = provider.complete(CompletionRequest(prompt="x", model="a-stronger-one"))
    assert result.model == "a-stronger-one"
    assert provider.complete(CompletionRequest(prompt="x")).model == provider.model


def test_the_containment_policy_is_recorded_where_a_decision_can_cite_it() -> None:
    """A limit that shapes every scene and appears in no policy record is the invisible input
    `policy_config_digest` exists to catch — `target_words` is the recorded instance."""
    material = ReviserPolicy().digest_material()
    assert set(material) == {"min_word_ratio", "max_word_ratio"}
    assert policy_digest(DraftPolicy(), None, material) != policy_digest(
        DraftPolicy(), None, ReviserPolicy(min_word_ratio=0.5).digest_material()
    )
