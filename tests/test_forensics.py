"""The provenance read side: one scene's dossier, and the log in write order.

The write side has been complete since Stage 1. The rendered prompt and system string are
frozen on the job payload at enqueue, every attempt gets a policy decision whether it
accepted or refused, and the event log is written in the same transaction as the state
change it describes. None of it was printed by any command — `read_log`,
`decision_for_revision` and `lineage` were called only by this suite — so the only way to
look at any of it was to open the SQLite file. That is the entry §31 closed for plans and
§39 closed for state.

These drive `main(argv)` rather than the functions underneath, for the reason
`tests/test_cli.py` states: the interface being asserted *is* the command line, including
its exit codes.

The seeding here runs the real drafting loop against the deterministic provider rather than
hand-writing rows, because the thing under test is a join across several tables and a
hand-set row would agree with the reader by construction.
"""

from __future__ import annotations

import json

import litharness_contracts as lc
import pytest

from litharness.adapters.contracts_fixtures import (
    fixture_manuscript,
    fixture_plans,
    fixture_state,
)
from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.conductor import Conductor
from litharness.application.handlers import SCENE_DRAFT, make_scene_draft_handler
from litharness.application.planner import make_plan_selector
from litharness.cli import EXIT_ATTENTION, EXIT_OK, main
from litharness.domain.generation import CompletionRequest, CompletionResult, Usage
from litharness.domain.nodes import Node, NodeKind
from litharness.domain.plans import import_plan, scene_plan_id_for
from litharness.domain.position import initial_keys
from litharness.domain.revision import build_revision, import_manuscript
from litharness.domain.state import import_state
from litharness.providers.fake import FakeProvider
from litharness.providers.registry import ProviderRegistry
from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID

START = 1_760_000_000.0
TICK = 300.0
STAMP = "2026-08-21T00:00:00Z"

#: Enough padding to clear the draft policy's floor without touching the gate — the same
#: number `tests/test_planner.py` runs its autonomous book at.
PAD = 400


@pytest.fixture
def db(tmp_path):
    return tmp_path / "forensics.db"


def run(db, *args: str) -> int:
    return main(["--database", str(db), *args])


def drafted(db, capsys, fixture: str = "mystery") -> tuple[str, str]:
    """A fixture book carried to six accepted scenes by the loop that drafts production books.

    The CLI cannot do this itself: `LITHARNESS_ENV=test` refuses a billing provider before
    any probe, so the composition root's registry is unreachable from `main`. Wiring the
    deterministic provider here is what makes the payloads, decisions and provenance rows
    under test the ones the real path writes.
    """
    assert run(db, "init") == EXIT_OK
    assert run(db, "import", "--fixture", fixture) == EXIT_OK
    capsys.readouterr()

    store = SqliteStore.open(db)
    try:
        book_id, branch_id, _ = store.branches()[0]
        registry = ProviderRegistry(FakeProvider(pad_to_chars=PAD))
        loop = Conductor(
            store=store,
            holder="worker-a",
            project_id=PROJECT_ID,
            registry=registry,
            select=make_plan_selector(),
            handlers={SCENE_DRAFT: make_scene_draft_handler(registry, store, PROJECT_ID)},
        )
        for index in range(8):
            loop.tick(START + index * TICK)
    finally:
        store.close()
    return book_id, branch_id


#: The statement `outlined` gives scene 3. Neither golden fixture carries one — `plans.py`
#: records that not one of their items is a `scene_plan` — so a book that has one has to be
#: built to test the join.
SCENE_STATEMENT = "Julian names the floorboard before anyone has mentioned it."


def outlined(db, capsys, fixture: str = "mystery") -> tuple[str, str]:
    """A drafted book whose plan holds a per-scene statement for scene 3.

    Seeded through `record_plan_items` at import time rather than after it, because
    `plan_items` reads the plan *head revision* once one exists — a row written afterwards is
    invisible until a proposal mints a new head, which is the immutability the plan lineage
    is for.
    """
    assert run(db, "init") == EXIT_OK
    capsys.readouterr()
    store = SqliteStore.open(db)
    try:
        manuscript = lc.parse_artifact(
            lc.ManuscriptRevision,
            json.loads(fixture_manuscript(fixture).read_text(encoding="utf-8")),
        )
        revision = import_manuscript(manuscript).revision
        store.commit_revision(revision, created_at=STAMP)

        snapshot = lc.parse_artifact(
            lc.PlanSnapshot, json.loads(fixture_plans(fixture).read_text(encoding="utf-8"))
        )
        plan = import_plan(
            snapshot, book_id=revision.book_id, branch_id=revision.branch_id
        )
        store.record_plan_items(
            revision.book_id,
            revision.branch_id,
            [
                *plan.items,
                lc.PlanItem(
                    logical_id=scene_plan_id_for("scene-3"),
                    kind=lc.PlanKind.SCENE_PLAN,
                    text=SCENE_STATEMENT,
                    authority=lc.PlanAuthority.INTENDED,
                    locked=True,
                ),
            ],
            created_at=STAMP,
            source_revision_id=plan.source_revision_id,
        )

        state = import_state(
            lc.parse_artifact(
                lc.StateSnapshot, json.loads(fixture_state(fixture).read_text(encoding="utf-8"))
            ),
            book_id=revision.book_id,
            branch_id=revision.branch_id,
        )
        store.record_state_records(
            revision.book_id,
            revision.branch_id,
            state.records,
            created_at=STAMP,
            source_revision_id=state.source_revision_id,
        )

        registry = ProviderRegistry(FakeProvider(pad_to_chars=PAD))
        loop = Conductor(
            store=store,
            holder="worker-a",
            project_id=PROJECT_ID,
            registry=registry,
            select=make_plan_selector(),
            handlers={SCENE_DRAFT: make_scene_draft_handler(registry, store, PROJECT_ID)},
        )
        for index in range(8):
            loop.tick(START + index * TICK)
        return revision.book_id, revision.branch_id
    finally:
        store.close()


def stubbed(db, capsys, stub: str, fixture: str = "mystery") -> tuple[str, str]:
    """Draft a book whose *first* generation is a stub the shape gate refuses.

    The floor is 200 characters and it is a shape gate, not a quality one — so a stub is
    refused, the unit requeues, and the second attempt lands. That produces the ladder the
    dossier reports: a refusal and an acceptance on one job.
    """
    assert run(db, "init") == EXIT_OK
    assert run(db, "import", "--fixture", fixture) == EXIT_OK
    capsys.readouterr()

    provider = FakeProvider()
    texts = (stub, "The rain kept on against the study glass. " * 20)

    def complete(_: CompletionRequest) -> CompletionResult:
        text = texts[min(provider.calls, len(texts) - 1)]
        provider.calls += 1
        return CompletionResult(
            text=text, provider="fake", model="fake-deterministic-v1", usage=Usage(10, 20)
        )

    provider.complete = complete  # type: ignore[method-assign]
    registry = ProviderRegistry(provider)

    store = SqliteStore.open(db)
    try:
        book_id, branch_id, _ = store.branches()[0]
        loop = Conductor(
            store=store,
            holder="worker-a",
            project_id=PROJECT_ID,
            registry=registry,
            select=make_plan_selector(),
            handlers={SCENE_DRAFT: make_scene_draft_handler(registry, store, PROJECT_ID)},
        )
        for index in range(4):
            loop.tick(START + index * TICK)
    finally:
        store.close()
    return book_id, branch_id


def unattributed_scene(db, logical_id: str = "scene-1") -> str:
    """Commit new prose for one scene with no policy decision behind it, and return its id.

    `commit_revision` takes the decision as an optional argument, so this is the shape a
    caller that forgets attribution produces — the shape `unattributed_revisions` exists to
    find, and the one `revert` had for as long as it wrote no decision of its own.
    """
    store = SqliteStore.open(db)
    try:
        book_id, branch_id, _ = store.branches()[0]
        head = store.head(book_id, branch_id)
        assert head is not None
        node = head.node(logical_id)
        edited = head.replacing(
            [node.with_content("A hand-committed rewrite that no decision explains. " * 8)]
        )
        store.commit_revision(edited, created_at=STAMP)
        return edited.revision_id
    finally:
        store.close()


# --- the dossier ---------------------------------------------------------------------


def test_the_dossier_prints_the_prompt_that_was_actually_sent(db, capsys) -> None:
    """**The gap this closes.** The rendered prompt and system string are frozen on the job
    payload at enqueue precisely so a replay reads the same bytes the generator saw, and no
    command printed either of them. A prompt nobody can read is a prompt nobody can debug.
    """
    drafted(db, capsys)

    assert run(db, "why", "--scene", "3") == EXIT_OK

    out = capsys.readouterr().out
    assert "--- system (" in out and "--- prompt (" in out
    # Not a re-render: these are the fixture's own locked constraints, which reach the
    # prompt through the context packet and appear nowhere else in this verb's output.
    assert "Locked constraints and promises" in out
    assert "Established facts" in out


def test_the_dossier_joins_the_decision_the_job_and_the_gate_ladder(db, capsys) -> None:
    """Every piece lives in a different table and the operator's question spans all of them:
    which model, on which attempt, past which gates, at what cost."""
    drafted(db, capsys)

    assert run(db, "why", "--scene", "3") == EXIT_OK

    out = capsys.readouterr().out
    assert "dec-" in out and "accept" in out
    assert "fake/fake-deterministic-v1" in out
    assert "shape.draft.v0" in out, "the gate ladder is what refused or did not"
    assert "scene_draft" in out and "succeeded" in out
    assert "beat 3/6" in out, "why this beat was selected, off the payload's own record"
    assert "context item(s) the packet could not hold" in out


def test_a_scene_no_decision_explains_says_so_and_exits_non_zero(db, capsys) -> None:
    """**The `verify` idiom, per scene.** `unattributed_revisions` exists because §19's
    integrity clause was asserted rather than checked; a dossier printing a blank where the
    decision belongs would reintroduce exactly that silence one scene at a time.
    """
    drafted(db, capsys)
    revision_id = unattributed_scene(db, "scene-1")

    assert run(db, "why", "--scene", "1") == EXIT_ATTENTION

    out = capsys.readouterr().out
    assert "ABSENT" in out
    assert "no policy decision explains this revision" in out

    # The same fact the store-wide check reports, arrived at from the other end.
    store = SqliteStore.open(db)
    try:
        assert revision_id in store.unattributed_revisions()
    finally:
        store.close()
    capsys.readouterr()
    assert run(db, "verify") == EXIT_ATTENTION


def test_the_dossier_json_names_every_absence_in_a_list(db, capsys) -> None:
    """The shape an agent chains on, following the `status --json` precedent: one object,
    stable keys, and every absence named in a list rather than implied by a missing key."""
    drafted(db, capsys)
    unattributed_scene(db, "scene-1")
    capsys.readouterr()

    assert run(db, "why", "--scene", "3", "--json") == EXIT_OK
    dossier = json.loads(capsys.readouterr().out)

    assert set(dossier) == {
        "book_id",
        "branch_id",
        "logical_id",
        "scene",
        "decision",
        "attempts",
        "job",
        "prompt",
        "selected_by",
        "context",
        "context_omitted",
        "plan_item",
        "findings",
        "absent",
    }
    assert dossier["prompt"]["prompt"].startswith("Premise:")
    assert dossier["decision"]["outcome"] == "accept"
    assert dossier["decision"]["gates"], "the ladder rides in the object, not just the text"
    # The mystery fixture carries no per-scene statement, and saying so is the point.
    assert dossier["plan_item"] is None
    assert dossier["absent"] == ["plan_item"]

    run(db, "why", "--scene", "1", "--json")
    unattributed = json.loads(capsys.readouterr().out)
    assert unattributed["decision"] is None, "no row is null, never an empty object"
    assert "decision" in unattributed["absent"]


def test_a_scene_can_be_named_by_reading_order_as_well_as_by_id(db, capsys) -> None:
    """A logical id is what an agent chains from and an ordinal is what a human reading the
    book has. Both resolve, and the id wins where they disagree."""
    drafted(db, capsys)
    capsys.readouterr()

    run(db, "why", "--scene", "scene-4", "--json")
    by_id = json.loads(capsys.readouterr().out)
    run(db, "why", "--scene", "4", "--json")
    by_ordinal = json.loads(capsys.readouterr().out)

    assert by_id["logical_id"] == by_ordinal["logical_id"] == "scene-4"


def test_reading_order_reaches_a_book_that_does_not_name_its_scenes_scene_n(db, capsys) -> None:
    """The ordinal falls back to counting, which is the case that makes it worth having.

    `new_book` mints `scene-3` and a digit resolves through that id first, so on a fixture
    book the two paths are indistinguishable. An imported book naming its scenes anything
    else is the one where the fallback is the only thing that answers.
    """
    assert run(db, "init") == EXIT_OK
    store = SqliteStore.open(db)
    try:
        keys = initial_keys(2)
        store.commit_revision(
            build_revision(
                BOOK_ID,
                BRANCH_ID,
                [
                    Node(logical_id="book", kind=NodeKind.BOOK, position_key="010"),
                    Node.text_node(
                        "opening", NodeKind.SCENE, keys[0], "Rain on the study glass.",
                        parent_logical_id="book",
                    ),
                    Node.text_node(
                        "closing", NodeKind.SCENE, keys[1], "The ledger closed at fifteen.",
                        parent_logical_id="book",
                    ),
                ],
            ),
            created_at=STAMP,
        )
    finally:
        store.close()
    capsys.readouterr()

    run(db, "why", "--book", BOOK_ID, "--branch", BRANCH_ID, "--scene", "2", "--json")

    assert json.loads(capsys.readouterr().out)["logical_id"] == "closing"


def test_the_statement_that_steered_the_draft_prints_verbatim(db, capsys) -> None:
    """**The plan item was unreadable from the CLI**, and it is the one line of the prompt
    that says what *this* scene is for. Neither golden fixture carries a scene plan — they
    hold book-wide statements only — so a book that has one is what proves the join.
    """
    outlined(db, capsys)
    capsys.readouterr()

    assert run(db, "why", "--scene", "3") == EXIT_OK

    out = capsys.readouterr().out
    assert SCENE_STATEMENT in out
    assert "scene-3-plan" in out and "locked" in out
    assert "ABSENT - the plan holds no statement" not in out

    run(db, "why", "--scene", "3", "--json")
    dossier = json.loads(capsys.readouterr().out)
    assert dossier["plan_item"]["text"] == SCENE_STATEMENT
    assert dossier["plan_item"]["locked"] is True
    assert dossier["plan_item"]["authority"] == "intended", "the value, not the enum's repr"
    assert dossier["absent"] == [], "nothing is missing for this scene now"


def test_the_attempts_ladder_shows_the_refusals_the_acceptance_followed(db, capsys) -> None:
    """**Refusals are recorded as fully as acceptances, and this is where that pays.** A scene
    accepted on the second try was refused on the first, and "which gate refused it, and what
    changed" is unanswerable from the accepting decision alone.
    """
    stubbed(db, capsys, "too short to be a scene.")

    assert run(db, "why", "--scene", "1") == EXIT_OK

    out = capsys.readouterr().out
    assert "accept  attempt 2" in out
    assert "2 decision(s) on this job - 1:retry, 2:accept" in out
    # The deterministic provider reports no dollars, which is a value and not a zero.
    assert "cost not reported" in out


def test_an_undrafted_scene_is_not_reported_as_an_attribution_gap(db, capsys) -> None:
    """A scene with no revision has nothing to attribute, and saying "no policy decision
    explains this revision" of it would send a reader hunting a §19 failure that is not there.

    Both cases exit 1 and both name what is absent; they are not the same finding, and the
    renderer has to draw the line the `absent` list already draws.
    """
    assert run(db, "init") == EXIT_OK
    assert run(db, "import", "--fixture", "litrpg") == EXIT_OK
    capsys.readouterr()

    assert run(db, "why", "--scene", "2") == EXIT_ATTENTION

    out = capsys.readouterr().out
    assert "no accepted revision carries this scene yet" in out
    assert "no policy decision explains this revision" not in out

    run(db, "why", "--scene", "2", "--json")
    dossier = json.loads(capsys.readouterr().out)
    assert dossier["absent"] == ["prose", "prompt", "plan_item"]
    assert "decision" not in dossier["absent"], "no revision here can be unattributed"


def test_a_scene_that_is_not_there_is_refused_with_the_ones_that_are(db, capsys) -> None:
    """A typo should cost one command, not a session spent guessing at logical ids."""
    drafted(db, capsys)
    capsys.readouterr()

    assert run(db, "why", "--scene", "scene-99") == EXIT_ATTENTION

    err = capsys.readouterr().err
    assert "no scene scene-99" in err
    assert "scene-1" in err and "scene-6" in err


# --- the event log -------------------------------------------------------------------


def test_the_event_log_reads_back_in_the_order_it_was_written(db, capsys) -> None:
    """`migrations/021_foreground_loop.sql` calls this table the provenance record and it had
    no reader at all: `read_log` was called only by this suite."""
    drafted(db, capsys)
    capsys.readouterr()

    assert run(db, "events") == EXIT_OK

    out = capsys.readouterr().out
    sequences = [
        int(line.split()[0])
        for line in out.splitlines()
        if line[:6].strip().isdigit()
    ]
    assert sequences == sorted(sequences), "write order is the only order this log has"
    assert "ManuscriptRevisionAccepted" in out
    assert "PolicyDecisionRecorded" in out
    assert "matching event(s); next --since" in out


def test_events_narrows_by_type_and_resumes_from_the_cursor_it_printed(db, capsys) -> None:
    """An agent reconstructing a run reads it in bounded passes, so the verb has to say where
    it stopped rather than making the caller count lines."""
    drafted(db, capsys)
    capsys.readouterr()

    run(db, "events", "--type", "PolicyDecisionRecorded", "--limit", "2")
    first = capsys.readouterr().out
    assert "ManuscriptRevisionAccepted" not in first
    cursor = first.rsplit("--since ", 1)[1].strip().rstrip(")")

    run(db, "events", "--since", cursor, "--type", "PolicyDecisionRecorded", "--json")
    resumed = json.loads(capsys.readouterr().out)
    assert resumed["events"], "the cursor resumed past the end of a log that has more"
    assert all(item["sequence"] > int(cursor) for item in resumed["events"])
    assert all(item["event_type"] == "PolicyDecisionRecorded" for item in resumed["events"])


def test_events_json_carries_the_payload_the_text_had_to_truncate(db, capsys) -> None:
    drafted(db, capsys)
    capsys.readouterr()

    assert run(db, "events", "--type", "PolicyDecisionRecorded", "--json") == EXIT_OK

    payload = json.loads(capsys.readouterr().out)["events"][0]["payload"]
    assert payload["gates"], "a truncated line is a pointer; this is the record"
    assert payload["decision_id"].startswith("dec-")


def test_events_narrows_by_instant_and_by_book(db, capsys) -> None:
    """`--since` takes a sequence *or* an instant, because an agent arriving at a store mid-run
    has a timestamp from somewhere else and no cursor of its own. The stamps are Z-normalised,
    so a date prefix compares correctly against them."""
    book_id, _ = drafted(db, capsys)
    capsys.readouterr()

    run(db, "events", "--since", "1970-01-01", "--json")
    everything = json.loads(capsys.readouterr().out)
    run(db, "events", "--since", "2999-01-01", "--json")
    nothing = json.loads(capsys.readouterr().out)

    assert everything["matched"] > 0 and nothing["matched"] == 0

    run(db, "events", "--book", book_id, "--json")
    scoped = json.loads(capsys.readouterr().out)
    assert scoped["events"] and all(item["book_id"] == book_id for item in scoped["events"])

    run(db, "events", "--book", "no-such-book", "--json")
    assert json.loads(capsys.readouterr().out)["matched"] == 0


def test_an_empty_log_says_so_rather_than_printing_nothing(db, capsys) -> None:
    """Silence reads as success. An empty result and a filter that matched nothing are
    different answers to "what happened" and neither of them is no answer."""
    assert run(db, "init") == EXIT_OK
    capsys.readouterr()

    assert run(db, "events") == EXIT_OK
    assert "no event matches" in capsys.readouterr().out


# --- the verbs an agent chains -------------------------------------------------------


def test_findings_json_reports_blocking_and_still_exits_on_it(db, capsys) -> None:
    drafted(db, capsys)
    capsys.readouterr()

    assert run(db, "findings", "--json") == EXIT_OK

    report = json.loads(capsys.readouterr().out)
    assert report["findings"] == []
    assert report["blocking"] == 0
    assert report["open_only"] is True


def test_plans_json_distinguishes_the_imported_root_from_a_proposed_step(db, capsys) -> None:
    drafted(db, capsys)
    capsys.readouterr()

    assert run(db, "plans", "--json") == EXIT_OK

    report = json.loads(capsys.readouterr().out)
    assert report["revisions"][0]["head"] is True
    assert report["revisions"][0]["proposal"] is None, "the imported root, said rather than blank"
    assert report["revisions"][0]["items"] == 5


# --- the rail ------------------------------------------------------------------------


def test_no_forensic_verb_writes_a_row(db, capsys) -> None:
    """**The constraint, as a test.** `plan/serial-pilot-1.md` §6 fences diagnostics to the
    operator's side of the loop: a rejection carries no explanation back into the system
    (§97.1). These verbs answer questions and must never become a channel that answers back,
    and the cheapest guarantee of that is that reading changes nothing at all.
    """
    drafted(db, capsys)
    capsys.readouterr()

    def snapshot() -> dict[str, int]:
        store = SqliteStore.open(db)
        try:
            names = [
                row["name"]
                for row in store._connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
                )
            ]
            return {
                name: store._connection.execute(
                    # The names come from `sqlite_master`, not from anything a caller typed.
                    f"SELECT COUNT(*) AS n FROM {name}"
                ).fetchone()["n"]
                for name in names
            }
        finally:
            store.close()

    before = snapshot()
    for argv in (
        ("why", "--scene", "2"),
        ("why", "--scene", "2", "--json"),
        ("events",),
        ("events", "--json"),
        ("findings", "--json"),
        ("plans", "--json"),
    ):
        run(db, *argv)
    capsys.readouterr()

    assert snapshot() == before


def test_every_new_verb_is_reachable_from_the_parser(db) -> None:
    """A verb wired into no subparser is a function with a docstring. Both of these are new
    surface and the wiring is one line each."""
    from litharness.cli import build_parser

    actions = build_parser()._subparsers._actions[-1]  # type: ignore[union-attr]
    assert {"why", "events"} <= set(actions.choices)
