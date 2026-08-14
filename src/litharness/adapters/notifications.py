"""Notification delivery: a real sink for the transactional outbox.

The outbox was built in slice 2 and has been correct and unreachable ever since.
Send-then-mark, content-derived idempotency keys, capped exponential backoff, a FAILED
terminal state, and a spin fix measured over 2,016 ticks — and the only dispatcher was one
that returned False for every entry, which no caller ever replaced. So every
`EvaluationCompleted`, `FindingStatusChanged`, `PlanChanged` and acceptance the system has
written sat pending forever, `tick`'s printed `dispatched=` count was **structurally** zero
rather than usually zero, and the one part of §4.3 that reaches an operator who is not
looking at a terminal did not exist. The machinery was honest about delivering nothing;
what it lacked was somewhere to deliver.

**JSON Lines to a file, because it is the smallest thing that is genuinely a sink.** It is
append-only, so it is crash-shaped like the log it carries; it needs no network, no
credentials and no dependency in a repo whose only runtime dependency is its own contracts
package; and `tail -f` is a working notification consumer on both platforms this project
supports. Anything richer — webhook, mail, a queue — is a different adapter behind the same
`Dispatcher` protocol, and can be added without touching the loop.

Four decisions are worth stating, because each is the difference between a sink and the
appearance of one.

**One line is exactly one `EventEnvelope`.** §13 keeps every integration on the shared
contract rather than on a shape invented at the boundary, so a consumer reads these lines
with `lc.parse_artifact` and gets the same object the store holds. Delivery bookkeeping —
attempt counts, backoff — is deliberately *not* written: it is this system's business, not
the consumer's, and mixing it in would make the line something no schema describes.

**The write is flushed and fsynced before delivery is claimed.** Send-then-mark is only
at-least-once if the send is durable before the mark. The store commits with
`synchronous=FULL`; a buffered line still in the OS cache when the machine loses power
would be marked sent and gone — silent loss, wearing the costume of success, which is the
exact failure the null dispatcher refused to commit by pretending. One fsync per event is
the price, and the outbox drains at most fifty per tick.

**A write that fails returns False; it does not raise.** `_drain_outbox` runs *before* work
selection, so an exception here would abort the tick before a single scene was drafted — an
unwritable notification path would stop the book. Refusing instead leaves the entry pending,
backs it off, and lets the tick get on with the work. The refusal is counted and its reason
kept, because a sink that fails quietly is only marginally better than one that discards.

**The file is opened per delivery rather than held open.** A cron tick is a fresh process,
so there is no handle worth reusing and one worth leaking — and CI treats a leaked resource
as a test error.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import litharness_contracts as lc

from litharness.domain.events import OutboxEntry


@dataclass
class JsonlDispatcher:
    """Append one `EventEnvelope` per line to `destination`, durably.

    Satisfies `application.conductor.Dispatcher` structurally; it is not imported from
    there, because an adapter must not depend on the workflow that uses it.
    """

    destination: Path
    #: Deliveries refused since this dispatcher was built, and why the last one was. One
    #: dispatcher is one tick, so an operator surface can report the tick's undelivered
    #: count without printing the same OSError once per entry.
    failures: int = field(default=0, init=False)
    last_error: str | None = field(default=None, init=False)

    def __call__(self, entry: OutboxEntry) -> bool:
        # Serialised before the file is touched, so a payload that cannot be represented
        # cannot leave a half-written line behind. `ensure_ascii=False` with an explicit
        # UTF-8 encoding keeps an em-dash an em-dash rather than six escape characters;
        # `json.dumps` escapes the newlines in prose, which is what keeps the framing.
        line = json.dumps(
            lc.to_jsonable(entry.event.to_contract()),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        try:
            self.destination.parent.mkdir(parents=True, exist_ok=True)
            # `newline="\n"` because the platform default here translates to CRLF, and a
            # notification file that changes shape depending on which host drained the
            # outbox is a file two consumers disagree about.
            with self.destination.open("a", encoding="utf-8", newline="\n") as sink:
                sink.write(f"{line}\n")
                sink.flush()
                os.fsync(sink.fileno())
        except OSError as error:
            self.failures += 1
            self.last_error = f"{type(error).__name__}: {error}"
            return False
        return True


__all__ = ["JsonlDispatcher"]
