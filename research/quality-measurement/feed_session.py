"""One costed-continuation session of the feed continuation reader: sequential and replayable.

`run_feed_session` is `bcr.run_session`'s four-slot, two-action generalisation, and it keeps
that function's discipline everywhere: the fault check runs before any call, the opening turn
is the longest shared prefix and so carries the one ephemeral cache breakpoint, an action that
cannot be parsed or cannot be afforded ends the session with its partial record rather than
being retried, and the sample index folds the replicate in as well as the step so replicates
never collapse onto one cache entry or one sampler seed.

The registered economics are the instrument: `budget_units`, `read_cost` and `skim_cost`
default to the frozen core's constants, and the keyword overrides exist for exactly one caller
— the `fp6` skim-price control, which runs sessions with `skim_cost == read_cost`. Anything
else passing them is running an unregistered variant of `fcr.v0`.

This module does no I/O, never constructs an `Elicitor`, and makes no baseline or fallback
decision of any kind; `feed_battery.py` decides what runs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Protocol, cast

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bcr  # noqa: E402
import feed_core  # noqa: E402


class SupportsAskRaw(Protocol):
    """Anything exposing `elicit.Elicitor.ask_raw`'s seam; tests pass a scripted fake."""

    def ask_raw(
        self,
        system: str,
        turns: list[dict[str, Any]],
        *,
        schema: dict[str, object] | None,
        max_tokens: int,
        tag: dict[str, Any],
        sample: int = 0,
        model: str | None = None,
    ) -> dict[str, Any]: ...


def _schema_enum(field: str) -> tuple[str, ...]:
    """The enum `field` carries in the frozen `ACTION_SCHEMA`, so validation cannot drift."""
    properties = cast("dict[str, Any]", feed_core.ACTION_SCHEMA["properties"])
    return tuple(properties[field]["enum"])


_VALID_ACTIONS = _schema_enum("action")
_VALID_BOOKS = _schema_enum("book")


def _parse_choice(record: dict[str, Any]) -> tuple[str, str] | None:
    """`(action, book)` out of one raw record, or None when anything disqualifies it.

    Refused, empty, non-JSON, or outside the schema's enums are all the same outcome: there is
    no partial credit on an action, because half an allocation is not an allocation and folding
    a malformed answer into the record would put a format failure into a behavioural
    distribution.
    """
    if record.get("refused"):
        return None
    text = record.get("text")
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    action = parsed.get("action")
    book = parsed.get("book")
    if (
        isinstance(action, str)
        and action in _VALID_ACTIONS
        and isinstance(book, str)
        and book in _VALID_BOOKS
    ):
        return action, book
    return None


def run_feed_session(
    elicitor: SupportsAskRaw,
    feed: feed_core.FeedSpec,
    *,
    model: str,
    rotation: int,
    replicate: int,
    budget_units: int = feed_core.BUDGET_UNITS,
    read_cost: int = feed_core.READ_COST,
    skim_cost: int = feed_core.SKIM_COST,
) -> feed_core.FeedSession:
    """One FCR session: four mid-stream openings, then spend the budget one action at a time.

    **Sequential by necessity**, for `bcr.run_session`'s reason: each choice is conditioned on
    everything read so far, which is what makes the budget scarce the way a reader experiences
    it. A full read costs `read_cost` and consumes the next section of its slot; a skim costs
    `skim_cost`, reveals a deterministic extract, and consumes nothing. Spending is forced —
    the loop runs while anything is affordable — so stopping cannot be performed as free
    diligence and abandonment is a revealed preference.

    The cost overrides exist for exactly one caller: the `fp6` skim-price control, which runs
    sessions with `skim_cost == read_cost`. The registered defaults **are** the instrument;
    any other override is an unregistered variant and is checked against the worst case it
    creates, because a member the registered fault check cleared can still be exhaustible at a
    cheaper read price — and a session that ran out of prose would record the corpus rather
    than the reader.

    No baseline, no fallback, no retry inside the loop: an unusable record, an unaffordable
    action, or a read past a slot's last section sets `unanswered`, names the exit in
    `exit_note`, and returns the partial record.
    """
    fault = feed.fault()
    if fault is not None:
        raise ValueError(fault)
    if (budget_units, read_cost, skim_cost) != (
        feed_core.BUDGET_UNITS,
        feed_core.READ_COST,
        feed_core.SKIM_COST,
    ):
        # Non-default economics change the worst case. At the registered prices the frozen
        # core's own fault check already guarantees MIDSTREAM_CHUNK + BUDGET_UNITS // READ_COST;
        # at other prices it does not, so the guarantee is re-derived here or refused.
        needed = feed_core.MIDSTREAM_CHUNK + budget_units // read_cost
        for index, text in enumerate(feed.texts()):
            held = len(bcr.chunks(text))
            if held < needed:
                name = "target" if index == 0 else f"other{index}"
                raise ValueError(
                    f"{name} holds {held} chunk(s); at read_cost={read_cost} and "
                    f"budget_units={budget_units} a feed member needs {needed} chunks"
                )
    chunks_by_slot: dict[str, tuple[str, ...]] = {}
    position: dict[str, int] = {}
    for index, text in enumerate(feed.texts()):
        slot = feed_core.slot_of(index, rotation)
        chunks_by_slot[slot] = bcr.chunks(text)
        # The 0-based index of the next unread chunk: the opening recapped chunks
        # 0..MIDSTREAM_CHUNK-2 and revealed chunk MIDSTREAM_CHUNK-1 in full as section 4.
        position[slot] = feed_core.MIDSTREAM_CHUNK
    opening = "\n\n".join(
        feed_core.opening_for_slot(slot, chunks_by_slot[slot]) for slot in feed_core.SLOTS
    )
    turns: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": opening + "\n\n" + feed_core.TURN.format(left=budget_units),
                    # The opening is the longest prefix every later turn in this session
                    # shares, so it is where a cache breakpoint can do anything at all;
                    # whether it engages is the transport's business and nothing here depends
                    # on it. Mirrors `bcr.run_session`.
                    "cache_control": {"type": "ephemeral"},
                }
            ],
        }
    ]

    actions: list[tuple[str, str]] = []
    unanswered = 0
    exit_note = ""
    remaining = budget_units
    step = 0
    while remaining >= min(read_cost, skim_cost):
        record = elicitor.ask_raw(
            feed_core.SYSTEM,
            turns,
            schema=feed_core.ACTION_SCHEMA,
            max_tokens=feed_core.ACTION_MAX_TOKENS,
            tag={
                "feed": feed.feed_id,
                "arm": feed.arm,
                "stage": "action",
                "rotation": rotation,
                "replicate": replicate,
                "step": step,
                "budget": budget_units,
                "read_cost": read_cost,
                "skim_cost": skim_cost,
            },
            # **The sample index carries the replicate as well as the step, and leaving the
            # replicate out was a real defect in the sibling instrument rather than a tidiness
            # point.** The replay cache keys on a digest of the request plus this index, and
            # at step 0 the request is byte-identical across every replicate of a feed — same
            # system, same openings, same budget — so `sample=step` would make replicate 1 a
            # cache hit on replicate 0 and every "replicate" one draw repeated. On ollama the
            # index is also the sampler seed, so the collapse survives a cleared cache.
            # `MAX_STEPS` bounds one session's calls, so replicate blocks never overlap.
            sample=replicate * feed_core.MAX_STEPS + step,
            model=model,
        )
        choice = _parse_choice(record)
        if choice is None:
            unanswered += 1
            exit_note = "invalid_action"
            break
        action, book = choice
        cost = read_cost if action == "read" else skim_cost
        if cost > remaining:
            # The affordable set shrank faster than the reader adapted. No re-ask, no
            # substitution: the record is the record, and inventing a cheaper action would be
            # this module allocating instead of the reader.
            unanswered += 1
            exit_note = "unaffordable_action"
            break
        served = position[book]
        available = chunks_by_slot[book]
        if action == "read":
            # Guarded away at registered prices by the checks above; reaching here anyway
            # would mean a guard was skipped, and continuing would silently record a forced
            # stop as a chosen one, so the session stops instead. Mirrors `bcr.run_session`.
            if served >= len(available):
                unanswered += 1
                exit_note = "slot_exhausted"
                break
            reveal = feed_core.REVEAL_READ.format(
                label=book, index=served + 1, text=available[served]
            )
            position[book] = served + 1
        else:
            # A skim previews the section a later read would serve and consumes nothing: the
            # position does not advance, so a later read of this slot shows the same section
            # in full — and a second skim buys the same preview again, which is why
            # `repeat_skims` exists as a diagnostic.
            reveal = feed_core.REVEAL_SKIM.format(
                label=book, index=served + 1, text=feed_core.skim_extract(available[served])
            )
        remaining -= cost
        turns.append(
            {"role": "assistant", "content": json.dumps({"action": action, "book": book})}
        )
        turns.append(
            {"role": "user", "content": reveal + "\n\n" + feed_core.TURN.format(left=remaining)}
        )
        actions.append((action, book))
        step += 1
    return feed_core.FeedSession(
        feed_id=feed.feed_id,
        arm=feed.arm,
        model=model,
        rotation=rotation,
        replicate=replicate,
        dose=feed.dose,
        actions=tuple(actions),
        unanswered=unanswered,
        exit_note=exit_note,
        read_cost=read_cost,
        skim_cost=skim_cost,
    )