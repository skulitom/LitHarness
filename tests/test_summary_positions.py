"""The summary ledger shares serial coordinates with the writer and outline."""

from __future__ import annotations

import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.repair import summary_job_for
from litharness.application.summarize import make_summary_handler
from litharness.domain.beats import beats_for, template_for
from litharness.domain.promises import Promise, promise_id_for
from litharness.domain.serials import SerialShape, beats_for_serial
from litharness.domain.text import content_hash
from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID
from tests.test_outline import START, a_book
from tests.test_summarize import SCENE, StubGenerator

STAMP = "2026-09-09T00:00:00Z"


@pytest.mark.parametrize("shape", [None, SerialShape(1, 24), SerialShape(1, 6)])
@pytest.mark.parametrize("hint", [5, None])
def test_summary_opening_due_and_payment_use_the_configured_coordinate_scheme(
    tmp_path, shape, hint,
):
    with SqliteStore.open(tmp_path / "positions.db") as store:
        head = a_book(store, scenes=12, sheet=False)
        head = head.replacing([head.node("scene-2").with_content(SCENE)])
        store.commit_revision(head, created_at=STAMP)
        serial = shape == SerialShape(1, 6)
        beats = (beats_for_serial(head, shape) if serial
                 else beats_for(head, template_for(head)))
        debt = Promise(
            promise_id=promise_id_for(BOOK_ID, "gate_ledger"), subject="gate_ledger",
            description="Read the gate ledger.", opened_at_key=beats[0].story_order_key,
            due_key=beats[-1].story_order_key, opened_by_revision=head.revision_id,
        )
        store.record_promise(BOOK_ID, BRANCH_ID, debt)
        source = StubGenerator({
            "setting": "The gate.", "characters": "Rook.", "events": "Rook returned.",
            "open": "Pay the toll.", "promises_opened": [{
                "subject": "pay_toll", "description": "Pay what is owed.", "due_hint": hint,
                "evidence_quote": "He would come back for the ledger.",
            }], "promises_paid": [{
                "subject": "gate_ledger", "evidence_quote": "He said so aloud",
            }],
        })
        job = summary_job_for(
            book_id=BOOK_ID, branch_id=BRANCH_ID, revision_id=head.revision_id,
            logical_id="scene-2", content_hash=content_hash(SCENE),
        )
        handler = make_summary_handler(source, store, PROJECT_ID, serial_shape=shape)
        handler(job, START)
        promises = {p.subject: p for p in store.promises(BOOK_ID, BRANCH_ID)}
        opened = promises["pay_toll"]
        paid = promises["gate_ledger"]
        assert opened.opened_at_key == paid.paid_at_key == beats[1].story_order_key
        assert opened.due_key == beats[(hint or len(beats)) - 1].story_order_key
        assert opened.opened_logical_id == paid.paid_logical_id == "scene-2"
        assert opened.opened_content_hash == paid.paid_content_hash == content_hash(SCENE)
        assert paid.status == "paid"
        before = promises
        handler(job, START + 1)
        assert {p.subject: p for p in store.promises(BOOK_ID, BRANCH_ID)} == before


def test_an_accepted_scene_in_an_open_serial_tail_does_not_mint_book_width_promises(tmp_path):
    with SqliteStore.open(tmp_path / "tail.db") as store:
        head = a_book(store, scenes=13, sheet=False)
        head = head.replacing([head.node("scene-13").with_content(SCENE)])
        store.commit_revision(head, created_at=STAMP)
        source = StubGenerator({
            "setting": "The gate.", "characters": "Rook.", "events": "Rook returned.",
            "open": "Pay the toll.", "promises_opened": [{
                "subject": "pay_toll", "description": "Pay what is owed.", "due_hint": None,
            }],
        })
        job = summary_job_for(
            book_id=BOOK_ID, branch_id=BRANCH_ID, revision_id=head.revision_id,
            logical_id="scene-13", content_hash=content_hash(SCENE),
        )
        make_summary_handler(source, store, PROJECT_ID, serial_shape=SerialShape(1, 6))(job, START)
        assert store.promises(BOOK_ID, BRANCH_ID) == []
        assert store.scene_summaries(BOOK_ID, BRANCH_ID)["scene-13"][content_hash(SCENE)]
