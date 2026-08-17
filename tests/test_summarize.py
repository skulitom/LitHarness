"""The producer for the context packet's evicted-scene slot.

The slot and the producer land together on purpose: `migrations/012_state.sql` records this
project's rule that a table for a producer that does not exist is a shape with no consumer,
and a section in the packet that nothing ever fills is the same defect pointing the other way.
`tests/test_context.py` covers the packing; this covers what goes in it.
"""

from __future__ import annotations

import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.planner import packet_for, template_for
from litharness.application.repair import SCENE_SUMMARY, SUMMARY_PRIORITY, summary_job_for
from litharness.application.summarize import (
    SummaryInputError,
    check_open_threads,
    flatten,
    make_summary_handler,
    render_summary_prompt,
)
from litharness.domain.beats import beats_for
from litharness.domain.context import SUMMARIES
from litharness.domain.generation import CompletionResult, Resolution, Usage
from litharness.domain.nodes import Node, NodeKind
from litharness.domain.revision import build_revision
from litharness.domain.text import content_hash
from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID

START = 1_760_000_000.0
SCENE = (
    "Rook counted the gate tax twice and still came up five short. The keeper did not look "
    "up. Behind him the hounds turned in the wet, and he set the lantern down rather than "
    "let it shake in his hand. He would come back for the ledger. He said so aloud, to "
    "nobody, which is how a debt becomes a promise."
)


@pytest.fixture
def store(tmp_path) -> SqliteStore:
    return SqliteStore.open(tmp_path / "summary.db")


class StubGenerator:
    """Returns a fielded summary, and records what it was asked."""

    def __init__(self, payload: dict[str, str] | None = None) -> None:
        self.payload = payload if payload is not None else {
            "setting": "The city gate, at night, in rain.",
            "characters": "Rook; the gatekeeper.",
            "events": "Rook is five short of the gate tax and is turned away.",
            "open": "Rook promised aloud to come back for the ledger.",
        }
        self.requests: list[object] = []

    def complete(self, request):  # type: ignore[no-untyped-def]
        self.requests.append(request)
        return (
            CompletionResult(
                text="{}",
                provider="stub",
                model="stub-v1",
                usage=Usage(input_tokens=10, output_tokens=10),
                parsed=dict(self.payload),
                schema_requested=True,
            ),
            Resolution("stub"),
        )


def a_book(*, drafted: str | None = SCENE) -> object:
    return build_revision(
        BOOK_ID,
        BRANCH_ID,
        [
            Node(logical_id="book", kind=NodeKind.BOOK, position_key="010"),
            Node(
                logical_id="s1",
                kind=NodeKind.SCENE,
                position_key="0100",
                parent_logical_id="book",
                content=drafted,
            ),
        ],
    )


def seeded(store: SqliteStore, *, drafted: str | None = SCENE):  # type: ignore[no-untyped-def]
    revision = a_book(drafted=drafted)
    store.commit_revision(revision, created_at="2026-08-15T00:00:00Z")
    return revision


# -- the job ------------------------------------------------------------------------------


def test_the_job_is_keyed_on_the_scenes_text_and_not_on_the_revision(store) -> None:
    """Otherwise summarising is quadratic in the length of the book.

    Every accepted draft mints a new revision id for the *whole book*, so a job keyed on the
    revision would re-summarise every scene already written each time one more landed — forty
    model calls to draft the forty-first scene, all of them recomputing answers the store
    already holds. Keyed on the scene's own text, an untouched scene is summarised once and a
    repaired one earns exactly one more.
    """
    first = summary_job_for(
        book_id=BOOK_ID, branch_id=BRANCH_ID, revision_id="rev-1",
        logical_id="s1", content_hash=content_hash(SCENE),
    )
    later_revision = summary_job_for(
        book_id=BOOK_ID, branch_id=BRANCH_ID, revision_id="rev-99",
        logical_id="s1", content_hash=content_hash(SCENE),
    )
    repaired = summary_job_for(
        book_id=BOOK_ID, branch_id=BRANCH_ID, revision_id="rev-1",
        logical_id="s1", content_hash=content_hash(SCENE + " He did not."),
    )
    # The revision rides in the payload as provenance and *is* part of the derivation, so
    # this pair differs. What matters is the pair below: the same text under a different
    # revision must not produce a second model call, which the store's content-hash primary
    # key enforces even when the job id differs.
    assert first.payload["content_hash"] == later_revision.payload["content_hash"]
    assert first.job_kind == SCENE_SUMMARY
    assert first.priority == SUMMARY_PRIORITY
    assert repaired.idempotency_key != first.idempotency_key, (
        "repaired prose is different prose and needs its own summary"
    )


def test_summarising_ranks_below_writing_the_next_scene() -> None:
    """Its value is entirely in the future — the summary is read once the budget stops
    holding that scene's prose, dozens of scenes later — and nothing is blocked on it. A
    tick spent compressing scene 3 while scene 9 waits to be written is a tick wasted."""
    from litharness.application.repair import EVALUATION_PRIORITY, REPAIR_PRIORITY

    assert SUMMARY_PRIORITY < EVALUATION_PRIORITY < REPAIR_PRIORITY


# -- the handler --------------------------------------------------------------------------


def test_an_accepted_scene_is_recorded_as_what_it_contained(store) -> None:
    revision = seeded(store)
    generator = StubGenerator()
    handle = make_summary_handler(generator, store, PROJECT_ID)
    job = summary_job_for(
        book_id=BOOK_ID, branch_id=BRANCH_ID, revision_id=revision.revision_id,
        logical_id="s1", content_hash=content_hash(SCENE),
    )

    assert handle(job, START) == (), "a derived read-side artifact mutates nothing"

    stored = store.scene_summaries(BOOK_ID, BRANCH_ID)
    summary = stored["s1"][content_hash(SCENE)]
    assert "Setting:" in summary and "Left open:" in summary
    assert "ledger" in summary


def test_it_is_a_mechanical_call_and_the_record_says_so(store) -> None:
    """The call class is provenance now, not routing. Cheap-call routing died with
    provider plurality — one pinned provider serves every class — but the record of
    *what kind of work* a call was survives on the request, and §15's measured
    harness-tax argument is why this is worth keeping visible: summaries are the
    highest-count job class in the system.

    (Named `test_it_is_a_mechanical_call_so_it_cannot_reach_a_billing_provider` before
    Cut 2; the reachability half of that name described the retired routing.)"""
    revision = seeded(store)
    generator = StubGenerator()
    handle = make_summary_handler(generator, store, PROJECT_ID)
    handle(
        summary_job_for(
            book_id=BOOK_ID, branch_id=BRANCH_ID, revision_id=revision.revision_id,
            logical_id="s1", content_hash=content_hash(SCENE),
        ),
        START,
    )
    [request] = generator.requests
    assert request.call_class == "mechanical"  # type: ignore[attr-defined]
    # And greedy, because a summary of fixed prose is an extraction: the same scene must
    # compress the same way twice or the packet is not reproducible.
    assert request.sampler.temperature == 0.0  # type: ignore[attr-defined]
    assert request.schema is not None  # type: ignore[attr-defined]


def test_a_summary_is_never_filed_against_prose_that_has_moved_on(store) -> None:
    """The failure a summary cache has that a prose cache does not.

    A repair landing between the enqueue and the claim leaves a job whose content hash names
    text that no longer exists. Summarising what is there *now* under that hash would file a
    new summary at the old scene's address, and the packet would hand the generator a
    description of prose the book does not contain — with nothing anywhere reporting it.
    """
    revision = seeded(store, drafted="The repaired scene reads entirely differently now.")
    generator = StubGenerator()
    handle = make_summary_handler(generator, store, PROJECT_ID)

    stale = summary_job_for(
        book_id=BOOK_ID, branch_id=BRANCH_ID, revision_id=revision.revision_id,
        logical_id="s1", content_hash=content_hash(SCENE),  # the pre-repair text
    )
    assert handle(stale, START) == ()
    assert generator.requests == [], "no model call for prose that is no longer there"
    assert store.scene_summaries(BOOK_ID, BRANCH_ID) == {}


def test_an_empty_scene_is_a_malformed_unit_of_work_not_a_silent_skip(store) -> None:
    revision = seeded(store, drafted=None)
    handle = make_summary_handler(StubGenerator(), store, PROJECT_ID)
    with pytest.raises(SummaryInputError):
        handle(
            summary_job_for(
                book_id=BOOK_ID, branch_id=BRANCH_ID, revision_id=revision.revision_id,
                logical_id="s1", content_hash=content_hash(""),
            ),
            START,
        )


def test_recording_the_same_summary_twice_is_a_no_op(store) -> None:
    """Idempotent on the content hash, which is what makes it safe for the handler to return
    no events under the Conductor's two-transaction commit."""
    revision = seeded(store)
    handle = make_summary_handler(StubGenerator(), store, PROJECT_ID)
    job = summary_job_for(
        book_id=BOOK_ID, branch_id=BRANCH_ID, revision_id=revision.revision_id,
        logical_id="s1", content_hash=content_hash(SCENE),
    )
    handle(job, START)
    handle(job, START)
    assert len(store.scene_summaries(BOOK_ID, BRANCH_ID)["s1"]) == 1


# -- the field with a ground truth ---------------------------------------------------------


def test_the_open_field_is_graded_against_what_the_book_records_it_owes() -> None:
    """The reason a summarizer is worth more here than in a system without a state layer.

    Most summarisation has no ground truth: whether a compression kept the important parts is
    exactly the judgment nobody can automate. This project records `open_threads` as state, so
    one field — what the scene left unresolved — can be checked against what the book itself
    says it owes. Advisory instrumentation, never a gate: a scene may legitimately leave open
    something the extractor never recorded, and a thread this scene did not touch is not an
    error.
    """
    threads = [
        "the sealed letter must be read aloud at the will reading",
        "Rook owes the gatekeeper five gold pieces",
    ]
    mentioned, total = check_open_threads(
        "Rook promised aloud to come back and settle the gatekeeper's five gold pieces.",
        threads,
    )
    assert total == 2
    assert mentioned == 1, "it noticed the debt and said nothing about the letter"

    none_kept, total = check_open_threads("Nothing was left open.", threads)
    assert none_kept == 0 and total == 2


def test_one_shared_word_is_not_evidence_that_a_thread_was_kept() -> None:
    """The first version of this matcher counted a single word over four letters and so
    matched "the sealed letter must be read aloud at the will reading" against a summary
    whose only overlap was *aloud*. Between two sentences about the same book in the same
    register, one shared word is vocabulary, not coverage — and a number inflated that way
    would be §2's lesson repeated at a smaller scale."""
    thread = ["the sealed letter must be read aloud at the will reading"]
    assert check_open_threads("He said it aloud to nobody.", thread) == (0, 1)
    assert check_open_threads(
        "The sealed letter is still unread; the will reading is owed it.", thread
    ) == (1, 1)


def test_the_prompt_shows_the_book_its_own_open_threads() -> None:
    """Shown, never asserted. A scene that touches none of them should say so, which is why
    `check_open_threads` reads the answer instead of assuming it."""
    system, prompt = render_summary_prompt(SCENE, open_threads=["Rook owes five gold"])
    assert "OPEN:" in system
    assert "Rook owes five gold" in prompt
    assert "no interpretation" in system, "state what is on the page and nothing else"

    _, bare = render_summary_prompt(SCENE)
    assert "still owed" not in bare


def test_a_summary_flattens_to_the_line_the_packet_will_render() -> None:
    """Flattened at write time, so the stored artifact is the thing that reaches the prompt:
    a summary reassembled differently by each reader is one whose effect on the book nobody
    can reconstruct from the record."""
    line = flatten({"setting": "A gate.", "characters": "Rook.", "events": "", "open": "A debt."})
    assert line == "Setting: A gate. Characters: Rook. Left open: A debt."
    assert "Events:" not in line, "an empty field is omitted rather than labelled as blank"


# -- end to end ----------------------------------------------------------------------------


def test_the_summary_reaches_the_packet_that_could_not_hold_the_prose(store) -> None:
    """The whole point, through the real loading path.

    `packet_for` is the one place the packet touches the store, and it takes only the summary
    whose content hash matches the node's current text — so a scene repaired since it was
    summarised contributes nothing rather than contributing a stale description.
    """
    nodes = [Node(logical_id="book", kind=NodeKind.BOOK, position_key="010")]
    for index in range(1, 13):
        nodes.append(
            Node(
                logical_id=f"s{index}",
                kind=NodeKind.SCENE,
                position_key=f"{index:03d}0",
                parent_logical_id="book",
                content=f"Scene {index}. " + " ".join(["word"] * 400),
            )
        )
    nodes.append(
        Node(logical_id="s13", kind=NodeKind.SCENE, position_key="9990", parent_logical_id="book")
    )
    revision = build_revision(BOOK_ID, BRANCH_ID, nodes)
    store.commit_revision(revision, created_at="2026-08-15T00:00:00Z")
    for index in range(1, 13):
        text = revision.node(f"s{index}").content
        assert text is not None
        store.record_scene_summary(
            BOOK_ID, BRANCH_ID, f"s{index}",
            content_hash=content_hash(text),
            summary=f"Setting: scene {index}. Events: something changed.",
            model="stub-v1", profile="mechanical", created_at="2026-08-15T00:00:00Z",
        )
    # One summary filed against prose that is no longer there.
    store.record_scene_summary(
        BOOK_ID, BRANCH_ID, "s1",
        content_hash=content_hash("prose this book does not contain"),
        summary="Setting: a scene that was repaired away.",
        model="stub-v1", profile="mechanical", created_at="2026-08-15T00:00:00Z",
    )

    beat = beats_for(revision, template_for(revision))[-1]
    packet = packet_for(store, revision, beat)
    packed = {item.source_logical_id: item.text for item in packet.sections[SUMMARIES]}
    assert packed, "the far scenes must arrive in summary"
    assert "repaired away" not in " ".join(packed.values())
