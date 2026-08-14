"""The outbox's first real sink (§4.1 step 5).

The transactional outbox has been correct and unreachable since slice 2. Send-then-mark,
content-derived idempotency keys, capped exponential backoff, a FAILED terminal state, and
a spin fix measured over 2,016 ticks — all of it draining into a dispatcher that returned
False for every entry, with no caller passing `dispatch=` at all. Every
`EvaluationCompleted`, `FindingStatusChanged`, `PlanChanged` and acceptance the system has
ever written therefore sat pending forever, and `tick`'s printed `dispatched=` count was
structurally zero rather than merely usually zero.

Two properties are what a sink owes the loop above it, and they are what these tests
measure: what it writes is parseable by the same contract every other integration in this
project speaks, and what it fails to write stays pending — not lost, and not taking the
tick down with it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import litharness_contracts as lc

from litharness.adapters.notifications import JsonlDispatcher
from litharness.domain.events import Event, EventType, OutboxEntry
from tests.conftest import PROJECT_ID


def entry(
    payload: dict[str, Any] | None = None,
    *,
    event_type: EventType = EventType.EVALUATION_COMPLETED,
) -> OutboxEntry:
    event = Event(
        event_type=event_type,
        project_id=PROJECT_ID,
        created_at="2026-08-12T00:00:00Z",
        payload=payload if payload is not None else {"findings": 3},
    )
    return OutboxEntry(idempotency_key=event.idempotency_key, event=event)


def lines(destination: Path) -> list[dict[str, Any]]:
    text = destination.read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines()]


# --- what a consumer receives --------------------------------------------------------


def test_a_delivered_event_is_one_envelope_the_contract_can_parse(tmp_path) -> None:
    """Not an ad-hoc shape. §13 keeps every integration on the shared schema, and a sink
    that invented its own would be the one boundary a consumer could not use contracts to
    read."""
    destination = tmp_path / "notifications.jsonl"
    delivered = entry()

    assert JsonlDispatcher(destination)(delivered) is True

    [envelope] = [lc.parse_artifact(lc.EventEnvelope, item) for item in lines(destination)]
    assert envelope.idempotency_key == delivered.idempotency_key
    assert envelope.event_type is lc.EventType.EVALUATION_COMPLETED
    assert envelope.payload == {"findings": 3}


def test_a_later_tick_appends_rather_than_replacing(tmp_path) -> None:
    """A cron tick is a fresh process, so the second delivery is a new dispatcher over the
    same file — the case a truncating open would destroy silently and completely."""
    destination = tmp_path / "notifications.jsonl"

    assert JsonlDispatcher(destination)(entry({"findings": 1}))
    assert JsonlDispatcher(destination)(entry({"findings": 2}))

    assert [item["payload"] for item in lines(destination)] == [{"findings": 1}, {"findings": 2}]


def test_a_redelivered_entry_is_written_again_under_the_key_that_dedupes_it(tmp_path) -> None:
    """Delivery is at-least-once by design: a crash between the write and `mark_sent`
    redelivers. A sink that deduped would be claiming a guarantee the loop does not make;
    the consumer dedupes, on the key every line carries."""
    destination = tmp_path / "notifications.jsonl"
    sink = JsonlDispatcher(destination)
    duplicate = entry()

    assert sink(duplicate) and sink(duplicate)

    written = lines(destination)
    assert len(written) == 2
    assert {item["idempotency_key"] for item in written} == {duplicate.idempotency_key}


def test_a_payload_with_a_newline_is_still_one_line(tmp_path) -> None:
    """JSON Lines has exactly one framing rule, and prose is made of newlines. `json.dumps`
    escapes them; a raw write would split one event into two unparseable halves and the
    consumer would report a corruption in a file that is not corrupt."""
    destination = tmp_path / "notifications.jsonl"

    assert JsonlDispatcher(destination)(entry({"prose": "first line\nsecond line"}))

    assert len(destination.read_text(encoding="utf-8").splitlines()) == 1
    assert lines(destination)[0]["payload"]["prose"] == "first line\nsecond line"


def test_an_em_dash_survives_the_sink(tmp_path) -> None:
    """The default encoding on this platform is cp1252, which cannot represent one — and a
    book is made of them. `import` and `export` were each bitten by this once; the sink
    writes UTF-8 explicitly for the same reason."""
    destination = tmp_path / "notifications.jsonl"

    assert JsonlDispatcher(destination)(entry({"summary": "the gate stood open — and shut"}))

    assert lines(destination)[0]["payload"]["summary"].endswith("— and shut")


def test_the_sink_creates_the_directory_it_was_pointed_at(tmp_path) -> None:
    """An operator naming `var/notifications.jsonl` means the file, and refusing until they
    also ran `mkdir` would spend eleven backed-off attempts before parking the entry as
    FAILED — a lost notification over a directory."""
    destination = tmp_path / "var" / "notifications.jsonl"

    assert JsonlDispatcher(destination)(entry()) is True

    assert len(lines(destination)) == 1


# --- what a failure must not do ------------------------------------------------------


def test_a_sink_that_cannot_be_written_refuses_instead_of_raising(tmp_path) -> None:
    """Refusing leaves the entry pending and backs it off, which is the outbox's own
    contract. Raising would propagate out of `_drain_outbox` — which runs *before* work
    selection — so an unwritable notification file would stop the book being written at
    all, and a misconfigured `--notify-file` would be indistinguishable from a dead system.
    """
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("", encoding="utf-8")
    destination = blocker / "notifications.jsonl"
    sink = JsonlDispatcher(destination)

    assert sink(entry()) is False
    assert sink.failures == 1
    assert sink.last_error, "a refusal with no reason leaves the operator nothing to fix"
    assert not destination.exists()


def test_failures_accumulate_so_one_tick_reports_one_diagnostic(tmp_path) -> None:
    """`_drain_outbox` hands over up to fifty entries per tick. Counting them means the
    operator surface can say how much went undelivered without printing fifty lines of the
    same OSError."""
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("", encoding="utf-8")
    sink = JsonlDispatcher(blocker / "notifications.jsonl")

    assert not sink(entry({"findings": 1}))
    assert not sink(entry({"findings": 2}))

    assert sink.failures == 2
