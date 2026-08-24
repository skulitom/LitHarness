"""One costed-continuation session of the feed continuation reader, run without any call.

`run_feed_session` is the sequential, replayable half of `fcr.v0`, and everything that could
go wrong with it goes wrong quietly: two replicates collapsing onto one sample index, a skim
that silently consumes the section it previewed, a budget that ends with units unspent because
the loop asked instead of charged, an unaffordable answer retried into a cheaper one. So this
file runs whole sessions against a scripted elicitor whose correct transcript is stated before
anything executes, and pins what came back:

1. **The budget is spent exactly and the reveals are the right sections in order.** Eight full
   reads at registered prices consume `BUDGET_UNITS` and serve sections 4 through 11 — section
   3 was the opening's entry reveal, so 4 is where reads begin.
2. **A skim previews; only a read consumes.** The same display index appears in both, the skim
   text is the deterministic extract, and a second skim buys the same preview again.
3. **Every failure mode exits under its own name** — `invalid_action`, `unaffordable_action`,
   `slot_exhausted` — with the partial record kept and the session not scorable.

No record here involves a model: the scripted elicitor pops pre-written raw records and never
instantiates `elicit.Elicitor`.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

bcr = pytest.importorskip(
    "bcr",
    reason="research module; imported by path, skipped where research/ is unavailable",
)
feed_core = pytest.importorskip(
    "feed_core",
    reason="research module; imported by path, skipped where research/ is unavailable",
)
feed_session = pytest.importorskip(
    "feed_session",
    reason="research module; imported by path, skipped where research/ is unavailable",
)


# ------------------------------------------------------------------------- the scripted reader


class ScriptedElicitor:
    """Pops pre-written raw records and remembers every request it was handed.

    The records are exactly what `elicit.Elicitor.ask_raw` returns — `{"refused": True}` or
    `{"text": ...}` — so the session code exercises the same seam a real transport fills.
    """

    def __init__(self, records: list[dict[str, Any]]) -> None:
        self._records = list(records)
        self.requests: list[dict[str, Any]] = []

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
    ) -> dict[str, Any]:
        # Snapshot the turn list rather than holding a reference: the loop appends to it
        # between calls, and a recorded list that keeps growing would lie about history.
        self.requests.append(
            {
                "system": system,
                "turns": [dict(turn) for turn in turns],
                "schema": schema,
                "max_tokens": max_tokens,
                "tag": dict(tag),
                "sample": sample,
                "model": model,
            }
        )
        if not self._records:
            raise AssertionError("script ran dry: the session asked more than it was given")
        return self._records.pop(0)


def _action(action: str, book: str) -> dict[str, Any]:
    return {"refused": False, "text": json.dumps({"action": action, "book": book})}


# ---------------------------------------------------------------------- the synthetic substrate

_WORDS_PER_PARAGRAPH = feed_core.CHUNK_WORDS + 5


def _member_text(marker: str) -> str:
    """One feed member: MIN_CHUNKS_FEED paragraphs, each just over CHUNK_WORDS.

    One paragraph per chunk at `bcr.chunks`' granularity, so every member holds exactly
    `MIN_CHUNKS_FEED` chunks — legal at registered prices by zero slack, which is what makes
    the non-default refit check below able to refuse it. The words carry no sentence-ending
    punctuation, so `skim_extract`'s fragment rule applies deterministically.
    """
    paragraphs = [
        " ".join(f"{marker}c{number}w{word}" for word in range(_WORDS_PER_PARAGRAPH))
        for number in range(feed_core.MIN_CHUNKS_FEED)
    ]
    return "\n\n".join(paragraphs)


def _texts() -> tuple[str, ...]:
    """The four feed texts; text 0 is the target, each with a unique marker prefix."""
    return (
        _member_text("target"),
        _member_text("otherone"),
        _member_text("othertwo"),
        _member_text("otherthree"),
    )


def _feed() -> feed_core.FeedSpec:
    target, other_one, other_two, other_three = _texts()
    return feed_core.FeedSpec(
        feed_id="feed-1", arm="intact", target=target, others=(other_one, other_two, other_three)
    )


def _full_script(prefix: list[tuple[str, str]]) -> list[dict[str, Any]]:
    """Records for `prefix` followed by enough skims to spend the whole registered budget."""
    spent = sum(
        feed_core.READ_COST if action == "read" else feed_core.SKIM_COST for action, _ in prefix
    )
    filler = [("skim", "D")] * (feed_core.BUDGET_UNITS - spent)
    return [_action(action, book) for action, book in prefix + filler]


def _run(
    records: list[dict[str, Any]], *, rotation: int = 0, replicate: int = 0
) -> tuple[feed_core.FeedSession, ScriptedElicitor]:
    """One session over `_feed()` with the given script, at registered prices."""
    fake = ScriptedElicitor(records)
    session = feed_session.run_feed_session(
        fake, _feed(), model="fake-model", rotation=rotation, replicate=replicate
    )
    return session, fake


# ------------------------------------------------------------------- budget and reveal sequence


def test_eight_reads_spend_the_whole_budget_and_reveal_sections_four_through_eleven() -> None:
    """At registered prices eight reads cost BUDGET_UNITS exactly: the loop must stop on
    remaining == 0 after eight actions, neither asking a ninth time nor stopping early."""
    records = [_action("read", "A")] * (feed_core.BUDGET_UNITS // feed_core.READ_COST)
    session, fake = _run(records)
    assert session.actions == (("read", "A"),) * 8
    assert session.spent_units == feed_core.BUDGET_UNITS
    assert len(fake.requests) == 8, "the loop stopped before the budget was spent"
    assert session.unanswered == 0
    assert session.exit_note == ""
    assert session.scorable
    # Request s carries as its last turn the reveal produced by action s-1. The opening showed
    # section MIDSTREAM_CHUNK in full, so the first read serves section 4 and the eighth serves
    # 11 — whose own reveal is never sent, because by then the budget is gone.
    for request_number in range(1, 8):
        content = fake.requests[request_number]["turns"][-1]["content"]
        assert f"Book A, section {feed_core.MIDSTREAM_CHUNK + request_number}:" in content


def test_a_read_serves_the_full_section_and_a_skim_only_the_deterministic_extract() -> None:
    """Skim then read of one slot: same display index both times, extract versus full chunk."""
    session, fake = _run(_full_script([("skim", "B"), ("read", "B")]))
    assert session.actions[0] == ("skim", "B")
    assert session.actions[1] == ("read", "B")
    # Under rotation 0 slot B holds feed text 1.
    entry = bcr.chunks(_texts()[1])[feed_core.MIDSTREAM_CHUNK]
    skim_turn = fake.requests[1]["turns"][-1]["content"]
    read_turn = fake.requests[2]["turns"][-1]["content"]
    expected_extract = feed_core.skim_extract(entry)
    section = feed_core.MIDSTREAM_CHUNK + 1
    assert f"Book B, section {section}, skimmed:\n\n{expected_extract}" in skim_turn
    assert f"Book B, section {section}:\n\n{entry}" in read_turn
    assert expected_extract != entry, "a skim that served the whole section would be a read"


def test_two_skims_of_one_slot_preview_the_same_section_twice_and_are_counted() -> None:
    """Skims never advance the position: the second preview repeats the first, and the record
    reports the repetition through `repeat_skims` rather than hiding it."""
    # Fill the remaining 22 units with alternating skim/read of D, then one skim each of B
    # and C — no slot is skimmed twice in a row there, so the only repeated preview in the
    # session is the one under test, and the total is exactly the 24-unit budget.
    records = [_action("skim", "A"), _action("skim", "A")]
    for _ in range(5):
        records.append(_action("skim", "D"))
        records.append(_action("read", "D"))
    records.append(_action("skim", "B"))
    records.append(_action("skim", "C"))
    session, fake = _run(records)
    assert session.spent_units == feed_core.BUDGET_UNITS
    # Each turn is reveal + "\n\n" + the budget turn; strip the tail, which differs by the
    # charge, and compare only what was revealed.
    first_preview = fake.requests[1]["turns"][-1]["content"].rsplit("\n\n", 1)[0]
    second_preview = fake.requests[2]["turns"][-1]["content"].rsplit("\n\n", 1)[0]
    assert first_preview == second_preview
    assert f"Book A, section {feed_core.MIDSTREAM_CHUNK + 1}, skimmed:" in first_preview
    assert session.skims_of("A") == 2
    assert session.reads_of("A") == 0
    assert session.repeat_skims == 1


def test_a_read_below_the_read_price_is_refused_as_unaffordable_with_one_unanswered() -> None:
    """Seven reads and two skims leave remaining == 1 at registered prices: a scripted read
    there ends the session as `unaffordable_action`, unanswered and not scorable. The boundary
    itself — remaining == READ_COST admitting a read — is what the eight-read session pins."""
    prefix = [("read", "A")] * 7 + [("skim", "A"), ("skim", "A")]
    records = [_action(action, book) for action, book in prefix]
    records.append(_action("read", "A"))
    session, fake = _run(records)
    assert session.exit_note == "unaffordable_action"
    assert session.unanswered == 1
    assert not session.scorable
    assert len(session.actions) == 9
    # The ask that drew the refusal showed the true remainder: one minute left, three needed.
    final_turn = fake.requests[-1]["turns"][-1]["content"]
    assert final_turn.endswith(feed_core.TURN.format(left=1))


# ------------------------------------------------------------------- rotation, sample, failures


def test_rotation_two_puts_the_targets_entry_in_slot_c_and_reads_it_there() -> None:
    """`slot_of(0, 2)` is C: the target's entry section appears in the opening under Book C,
    and a read of C serves the target's next section — not any competitor's."""
    session, fake = _run(_full_script([("read", "C")]), rotation=2)
    assert session.target_slot == "C"
    opening = fake.requests[0]["turns"][0]["content"][0]["text"]
    assert "Book C, section 3:" in opening
    texts = _texts()
    target_entry = bcr.chunks(texts[0])[feed_core.MIDSTREAM_CHUNK - 1]
    assert target_entry in opening
    # The read of C then serves the target's section 5, and no other book's prose does.
    first_read_turn = fake.requests[1]["turns"][-1]["content"]
    assert bcr.chunks(texts[0])[feed_core.MIDSTREAM_CHUNK] in first_read_turn
    assert "otherthreec4w" not in first_read_turn


def test_step_s_of_replicate_r_is_sampled_at_r_times_max_steps_plus_s() -> None:
    """The cache key and the sampler seed both come from `sample`, and at step 0 every
    replicate's request is byte-identical — so a step-only index would make replicate 1 a
    replay of replicate 0. Asserted on the recorded requests of two replicates."""
    all_samples: list[int] = []
    for replicate in (0, 1):
        _, fake = _run(_full_script([("read", "A")]), replicate=replicate)
        samples = [request["sample"] for request in fake.requests]
        assert samples == [replicate * feed_core.MAX_STEPS + step for step in range(len(samples))]
        all_samples.extend(samples)
    assert len(all_samples) == len(set(all_samples)), (
        "two calls shared a sample index, so they share a cache entry and a seed"
    )


@pytest.mark.parametrize(
    ("record", "why"),
    [
        ({"refused": True}, "refused"),
        ({"refused": False}, "empty"),
        ({"refused": False, "text": "continue with book A please"}, "non-JSON"),
        ({"refused": False, "text": '["read", "A"]'}, "JSON but not an object"),
        ({"refused": False, "text": '{"action": "read"}'}, "missing book"),
    ],
)
def test_every_unusable_record_ends_as_invalid_action_without_a_retry(
    record: dict[str, Any], why: str
) -> None:
    """Refused, empty, non-JSON, non-object, and incomplete are all one outcome: one ask, one
    unanswered step, `invalid_action`, partial record kept. No baseline, no second chance."""
    del why
    session, fake = _run([record])
    assert session.exit_note == "invalid_action"
    assert session.unanswered == 1
    assert session.actions == ()
    assert not session.scorable
    assert len(fake.requests) == 1


def test_an_unknown_action_name_ends_the_session_as_invalid_action() -> None:
    """An action outside the schema's enums is not a creative reading; it is no answer."""
    session, fake = _run([_action("fetch", "A")])
    assert session.exit_note == "invalid_action"
    assert session.unanswered == 1
    assert len(fake.requests) == 1


def test_a_refused_record_ends_the_session_as_invalid_action() -> None:
    """A refusal is a transport-class failure for `_parse_choice`, not an allocation of zero."""
    session, fake = _run([{"refused": True}])
    assert session.exit_note == "invalid_action"
    assert session.unanswered == 1
    assert len(fake.requests) == 1


def test_two_runs_over_one_script_return_equal_session_records() -> None:
    """Same script, same record: nothing in the loop draws on time, randomness, or identity,
    so a replay of the same transport answers reproduces the session exactly."""
    records = _full_script([("read", "A"), ("skim", "B")])
    first, _ = _run(list(records))
    second, _ = _run(list(records))
    assert first == second


# --------------------------------------------------------------------------- guards and fp6


def test_a_feed_with_a_fault_raises_before_any_request_is_made() -> None:
    """Both fault shapes — wrong member count, member too short to enter mid-stream — refuse
    before the first call; the scripted elicitor saw zero requests either way."""
    too_few = feed_core.FeedSpec(feed_id="bad", arm="x", target="t", others=("a", "b"))
    too_short = feed_core.FeedSpec(
        feed_id="bad2", arm="x", target=_member_text("tgt"), others=("a", "b", "c")
    )
    for feed in (too_few, too_short):
        fake = ScriptedElicitor([])
        with pytest.raises(ValueError, match=r"feed holds|chunk\(s\)"):
            feed_session.run_feed_session(fake, feed, model="m", rotation=0, replicate=0)
        assert fake.requests == []


def test_at_the_fp6_skim_price_each_skim_charges_a_full_reads_worth_of_budget() -> None:
    """fp6 runs sessions at skim_cost == read_cost == 3: eight skims, not twenty-four, consume
    BUDGET_UNITS — visible as the action count, the per-skim charge on the clock, and the
    zero-left tail. The session record carries the prices it ran at, so `spent_units`
    reports the full charge. The refit check must also stay silent here: equal
    prices do not change the worst case."""
    records = [_action("skim", "A")] * (feed_core.BUDGET_UNITS // 3)
    fake = ScriptedElicitor(records)
    session = feed_session.run_feed_session(
        fake,
        _feed(),
        model="m",
        rotation=0,
        replicate=0,
        read_cost=feed_core.READ_COST,
        skim_cost=feed_core.READ_COST,
    )
    assert len(session.actions) == 8
    assert session.spent_units == feed_core.BUDGET_UNITS
    # After the first skim, three minutes are gone from the reader's clock.
    after_first_skim = fake.requests[1]["turns"][-1]["content"]
    assert after_first_skim.endswith(
        feed_core.TURN.format(left=feed_core.BUDGET_UNITS - feed_core.READ_COST)
    )
    assert session.scorable


def test_non_default_prices_refuse_a_member_too_short_for_the_new_worst_case() -> None:
    """At read_cost == 1 the worst case needs MIDSTREAM_CHUNK + budget_units // 1 chunks per
    member; members legal at registered prices fail that refit and the session refuses before
    any call, because a slot the new budget could exhaust would record the corpus."""
    fake = ScriptedElicitor([])
    with pytest.raises(
        ValueError,
        match=f"needs {feed_core.MIDSTREAM_CHUNK + feed_core.BUDGET_UNITS} chunks",
    ):
        feed_session.run_feed_session(
            fake, _feed(), model="m", rotation=0, replicate=0, read_cost=1, skim_cost=1
        )
    assert fake.requests == []


def test_the_first_request_carries_the_frozen_seam_and_the_cache_breakpoint() -> None:
    """The opening turn is the shared prefix, so it — and only it — carries the ephemeral
    cache_control block; system, schema, max_tokens, model and the full step-0 tag are the
    frozen seam `bcr.run_session` keeps."""
    _, fake = _run(_full_script([("read", "A")]))
    request = fake.requests[0]
    assert request["system"] == feed_core.SYSTEM
    assert request["schema"] is feed_core.ACTION_SCHEMA
    assert request["max_tokens"] == feed_core.ACTION_MAX_TOKENS
    assert request["model"] == "fake-model"
    assert request["tag"] == {
        "feed": "feed-1",
        "arm": "intact",
        "stage": "action",
        "rotation": 0,
        "replicate": 0,
        "step": 0,
        "budget": feed_core.BUDGET_UNITS,
        "read_cost": feed_core.READ_COST,
        "skim_cost": feed_core.SKIM_COST,
    }
    opening_turn = request["turns"][0]
    assert opening_turn["role"] == "user"
    opening_block = opening_turn["content"][0]
    assert opening_block["cache_control"] == {"type": "ephemeral"}
    assert opening_block["text"].endswith(feed_core.TURN.format(left=feed_core.BUDGET_UNITS))