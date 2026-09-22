"""The milder-dose arm (`milder-v4`), checked without a call.

What this file pins: the partial shuffle is deterministic per (text, seed), differs across seeds
and from every full-shuffle draw, moves at most the registered fraction and close to it, breaks
most adjacencies, keeps the paragraph multiset and is never the identity; the seed rule skips
exactly the seeds whose dosed copy falls under the chunk floor; the plan seats six replicates in
slot A, replicate-major; the reading is v2's own on relabelled rows and reads each registered
outcome; the meter refuses a paid call past a ceiling, drains before a session that could cross
one, on a transport circuit and on unknown usage, halts on a changed binary, and never counts a
replay; a transport failure is never cached; a stopped run resumes by buying only what never
answered; the analysis replays offline, reads the transport first and refuses a cached failure;
and every refusal of prepare, run and analyse fires before anything is bought.

Also pinned since review: the registered operator is the power record's `perm_partial`, loaded
by path; the licensed Claude arm runs end to end through `elicit`'s own `claude -p` transport
(scripted envelopes, real record shapes, the probes' directories, the pin, the auto-updater
setting, the stat guard, the `cli_error:rc=` circuit); the ledger survives a kill and a resume
takes the larger of the ledger's and the cache's totals; the scorable floor counts dispatched
sessions, v2's rule; the request-identity check replays v2-shaped cells through a reader that
cannot write; the reader fence holds between profiles; and the same-reader baseline is what the
committed v2 and v3 results say.

What it does not establish: anything about any reader's allocation. No call happens here; the
Codex adapter is driven by a scripted runner, `claude -p` by scripted envelopes, and every other
reader is a fake.
"""

from __future__ import annotations

import functools
import importlib.util
import json
import os
import random
import re
import subprocess
import sys
import threading
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pytest

milder = pytest.importorskip(
    "cost_that_bites_milder",
    reason="research module; imported by path, skipped where research/ is unavailable",
)
ctb = pytest.importorskip("cost_that_bites")
ablate = pytest.importorskip("ablate")
bcr = pytest.importorskip("bcr")
elicit = pytest.importorskip("elicit")
feed_core = pytest.importorskip("feed_core")
feed_session = pytest.importorskip("feed_session")
governance = pytest.importorskip("epistemic_governance")

from litharness.domain.generation import CompletionResult, Usage  # noqa: E402
from litharness.providers.base import ProviderError, ProviderFailureKind  # noqa: E402
from litharness.providers.cli import CommandResult  # noqa: E402

CLAUDE = milder.PROFILES["claude"]
CODEX = milder.PROFILES["codex"]


def _prose(paragraphs: int, *, words: int = 12, marker: str = "q") -> str:
    """Short capitalised paragraphs, so the sham has sentence ends to re-flow."""
    stem = marker.capitalize()
    return "\n\n".join(
        " ".join(f"{stem}p{p}w{w}." if w % 6 == 5 else f"{stem}p{p}w{w}" for w in range(words))
        for p in range(paragraphs)
    )


def _alternating(pairs: int) -> str:
    """Long and short paragraphs in turn: 290 + 10 words close a chunk exactly, in this order."""
    parts = []
    for k in range(pairs):
        parts.append(" ".join(f"Zl{k}w{w}." if w % 8 == 7 else f"Zl{k}w{w}" for w in range(290)))
        parts.append(" ".join(f"Zs{k}w{w}" for w in range(10)))
    return "\n\n".join(parts)


def _books(count: int) -> list[tuple[str, str]]:
    """Full-length synthetic members: one 305-word paragraph per chunk, thirteen chunks."""
    return [(f"book-{index:02d}", ctb._member_text(f"b{index}")) for index in range(count)]


# ------------------------------------------------------------------------------- the dose


def test_the_partial_shuffle_is_deterministic_per_seed_and_differs_across_seeds() -> None:
    text = _prose(60)
    assert milder.partial_shuffle(text, index=3) == milder.partial_shuffle(text, index=3)
    orders = {tuple(milder.partial_order(text, index=index)) for index in range(10)}
    assert len(orders) == 10
    other = _prose(60, marker="r")
    assert milder.partial_order(text, index=0) != milder.partial_order(other, index=0)


def test_the_partial_shuffle_keeps_every_paragraph_and_every_word() -> None:
    text = _prose(80)
    dosed = milder.partial_shuffle(text, index=1)
    assert sorted(ablate.paragraphs(dosed)) == sorted(ablate.paragraphs(text))
    assert sorted(dosed.split()) == sorted(text.split())
    assert ablate.paragraphs(dosed) != ablate.paragraphs(text)


def test_the_fraction_moved_is_at_most_the_dose_and_close_to_it() -> None:
    text = _prose(200)
    ceiling = round(milder.DOSE * 200) / 200
    for index in range(10):
        metrics = milder.dose_metrics(milder.partial_order(text, index=index))
        assert 0.60 <= metrics["displaced"] <= ceiling
        # Most adjacencies break: a moved paragraph breaks both of its joins.
        assert 0.80 <= metrics["broken_adjacency"] <= 0.93


def test_only_picked_positions_move_and_the_rest_stay_in_place() -> None:
    text = _prose(40)
    order = milder.partial_order(text, strength=0.25, index=2)
    moved = [position for position, source in enumerate(order) if position != source]
    assert 0 < len(moved) <= round(0.25 * 40)
    assert sorted(order) == list(range(40))


def test_a_two_paragraph_text_is_never_returned_in_its_own_order() -> None:
    for index in range(8):
        assert milder.partial_order(_prose(2), index=index) == [1, 0]


def test_the_dose_salt_never_reproduces_a_full_shuffle_draw() -> None:
    text = _prose(30)
    assert milder.partial_shuffle(text, strength=1.0, index=0) != ctb.book_shuffle(text, index=0)


def test_a_strength_outside_the_unit_interval_is_refused() -> None:
    for strength in (0.0, -0.1, 1.5):
        with pytest.raises(ValueError, match="strength"):
            milder.partial_order(_prose(10), strength=strength)
    with pytest.raises(ValueError, match="two paragraphs"):
        milder.partial_order("One paragraph only.")


def test_the_seed_rule_skips_exactly_the_seeds_under_the_chunk_floor() -> None:
    text = _alternating(13)
    assert len(bcr.chunks(text)) == 13
    passing = [
        index
        for index in range(40)
        if len(bcr.chunks(milder.partial_shuffle(text, index=index))) >= feed_core.MIN_CHUNKS_FEED
    ]
    assert milder.seeds_for_partial(text, start=2, count=6) == tuple(
        index for index in passing if index >= 2
    )[:6]
    # Seeds 6 and 7 chunk to 10 here, so the rule skips them, as it skips fitness-08's seed 1.
    assert milder.seeds_for_partial(text, start=2, count=6) == (2, 3, 4, 5, 8, 9)


def test_the_seed_rule_skips_a_dosed_copy_whose_opening_is_intact() -> None:
    # A request carries the prose revealed so far, so a copy with an intact opening would send
    # the intact session's first request and be served its cached answer.
    text = ctb._member_text("b5")
    assert milder.opening_of(milder.partial_shuffle(text, index=0)) == milder.opening_of(text)
    assert milder.partial_shuffle(text, index=0) != text
    assert milder.seeds_for_partial(text, count=3) == (1, 2, 4)


def test_two_versions_sharing_an_opening_are_a_named_plan_fault() -> None:
    planned = milder.plan(_books(4), CLAUDE)
    intact = planned[0].cell.spec.target
    blocks = ablate.paragraphs(intact)
    late_swap = "\n\n".join([*blocks[:-2], blocks[-1], blocks[-2]])
    partial = planned[1]
    coupled = replace(partial, cell=replace(partial.cell,
                                            spec=replace(partial.cell.spec, target=late_swap)))
    faults = milder.plan_faults([planned[0], coupled, *planned[2:]])
    assert faults == {"ctbm4-00-partial-r0": "its opening is byte-identical to "
                                             "ctbm4-00-intact-r0's: one cache entry"}


def test_the_seed_rule_refuses_a_book_no_dose_can_seat() -> None:
    short = ctb._member_text("s", paragraphs=feed_core.MIN_CHUNKS_FEED - 1)
    with pytest.raises(ValueError, match="no 6 usable"):
        milder.seeds_for_partial(short)


# ------------------------------------------------------------------------------- the plan


def test_the_plan_seats_six_replicates_in_slot_a_replicate_major() -> None:
    books = _books(4)
    planned = milder.plan(books, CLAUDE)
    assert len(planned) == 4 * 3 * milder.REPLICATES
    assert [item.position for item in planned] == list(range(len(planned)))
    assert {item.cell.rotation for item in planned} == {milder.TARGET_ROTATION}
    assert [item.cell.replicate for item in planned[:12]] == [0] * 12
    assert planned[12].cell.replicate == 1
    ids = [item.cell.spec.feed_id for item in planned]
    assert len(set(ids)) == len(ids)
    assert ids[:3] == ["ctbm4-00-intact-r0", "ctbm4-00-partial-r0", "ctbm4-00-sham-r0"]
    by_version: dict[str, list[str]] = {}
    for item in planned:
        if item.cell.feed_index == 0:
            by_version.setdefault(item.cell.version, []).append(item.cell.spec.target)
    assert len(set(by_version["intact"])) == 1
    assert len(set(by_version["sham"])) == 1
    assert len(set(by_version["partial"])) == milder.REPLICATES
    assert milder.plan_faults(planned) == {}
    # book-03's seeds 5 and 8 leave its opening intact, so the rule takes 6 in place of 5.
    assert milder.seed_deviations(planned) == {"book-03": {"partial": [0, 1, 2, 3, 4, 6]}}
    others = planned[0].cell.spec.others
    assert others == tuple(text for _, text in books[1:4])


def test_the_codex_plan_carries_the_full_shuffle_as_its_positive_control() -> None:
    planned = milder.plan(_books(4), CODEX)
    assert len(planned) == 4 * 4 * milder.REPLICATES
    full = [item for item in planned if item.cell.version == "shuffled"]
    assert {item.cell.spec.dose for item in full} == {1.0}
    first = next(item for item in full if item.cell.feed_index == 0 and item.cell.replicate == 0)
    assert first.cell.spec.target == ctb.book_shuffle(_books(4)[0][1], index=first.seed)


def test_the_manifest_content_addresses_every_target() -> None:
    planned = milder.plan(_books(4), CLAUDE)
    rows = milder.manifest(planned)
    assert len(rows) == len(planned)
    partial = [row for row in rows if row["version"] == "partial"]
    assert all("dose_metrics" in row and row["seed"] is not None for row in partial)
    assert all(len(row["target_sha256"]) == 64 for row in rows)


def test_the_registration_names_its_instrument_and_lineage_and_is_stable() -> None:
    reg = milder.pre_registration(CLAUDE)
    assert reg["instrument_registration_digest"] == feed_core.registration_digest()
    assert reg["statistic_lineage"]["registration_digest_v2"] == ctb.registration_digest_v2()
    assert reg["reader"] == {"model": "claude-haiku-4-5", "transport": "cli", "effort": None}
    assert reg["alpha"] == 0.10 and reg["resamples"] == 2000
    assert milder.registration_digest(CLAUDE) == milder.registration_digest(CLAUDE)
    assert milder.registration_digest(CLAUDE) != milder.registration_digest(CODEX)


def test_the_ceilings_cover_the_measured_rate_and_bind_below_the_worst_case() -> None:
    # v2 and v3 measured 8.07 and 8.14 calls, $0.277 and $0.280 and ~42,400 reported tokens a
    # call, and 2h04 for 180 sessions at three workers.
    sessions = 20 * 3 * milder.REPLICATES
    limits = CLAUDE.limits
    expected_calls = sessions * 8.14
    assert expected_calls * 1.4 < limits["calls"] < sessions * feed_core.MAX_STEPS
    assert sessions * 0.280 * 1.4 < limits["usd"]
    assert expected_calls * 42_400 * 1.4 < limits["tokens"]
    assert 2 * (sessions / 180) * 7_452 * 0.9 < limits["seconds"]


# ----------------------------------------------------------------------------- the reading


def _row(book: int, version: str, replicate: int, reads: list[str]) -> Any:
    session = feed_core.FeedSession(
        feed_id=f"t-{book:02d}-{version}-r{replicate}", arm=version, model="m", rotation=0,
        replicate=replicate, dose=0.0, actions=tuple(("read", slot) for slot in reads),
    )
    return ctb.Row(
        feed_index=book, target_name=f"b{book:02d}", version=version, rotation=0,
        pair_key=f"{book:02d}:0", session=session, replicate=replicate,
    )


def _reads(rng: random.Random, share_a: float) -> list[str]:
    return ["A" if rng.random() < share_a else rng.choice("BCD") for _ in range(8)]


def _rows(shares: dict[str, float], *, books: int = 12, replicates: int = 3, seed: str = "x"):
    rows = []
    for book in range(books):
        for version, share in shares.items():
            for replicate in range(replicates):
                rng = random.Random(f"{seed}:{book}:{version}:{replicate}")
                rows.append(_row(book, version, replicate, _reads(rng, share)))
    return rows


def test_the_reading_is_v2s_own_on_relabelled_rows() -> None:
    rows = _rows({"intact": 0.7, "shuffled": 0.45, "sham": 0.65}, replicates=3)
    v2 = ctb.reading_v2(rows)
    relabelled = [
        replace(row, version="partial") if row.version == "shuffled" else row for row in rows
    ]
    mine = milder.reading(relabelled, CLAUDE)
    assert mine["decision"] == v2["decision"]
    for theirs, ours in (
        ("intact_minus_shuffled", "intact_minus_partial"),
        ("sham_minus_shuffled", "sham_minus_partial"),
        ("intact_minus_sham", "intact_minus_sham"),
    ):
        assert mine["target_read_share"][ours] == v2["target_read_share"][theirs]
    assert mine["fp5"] == v2["fp5"]
    assert mine["capacity"] == v2["capacity"]
    assert mine["books_complete"] == v2["books_complete"]


def _deterministic(book_share: dict[str, list[str]], books: int = 12) -> list[Any]:
    """Every session of a version reads the same slots, so each contrast is exact."""
    return [
        _row(book, version, replicate, reads)
        for book in range(books)
        for version, reads in book_share.items()
        for replicate in range(2)
    ]


A8 = ["A"] * 8
A4 = ["A", "B", "A", "C", "A", "D", "A", "B"]
B8 = ["B"] * 4 + ["C"] * 2 + ["D"] * 2


@pytest.mark.parametrize(
    ("versions", "expected"),
    [
        ({"intact": A8, "partial": A4, "sham": A8}, "MOVES_WITH_ORDER"),
        ({"intact": A8, "partial": A4, "sham": A4}, "MOVES_WITH_EDITEDNESS"),
        ({"intact": A4, "partial": A8, "sham": A4}, "INVERTED"),
    ],
)
def test_the_decision_table_reads_each_registered_outcome(versions, expected) -> None:
    read = milder.reading(_deterministic(versions), CLAUDE)
    assert [p["verdict"] for p in read["preconditions"]] == ["PASS"] * 4
    assert read["decision"] == expected
    assert read["licence"] == milder.LICENCE[expected]


def test_a_contrast_that_straddles_zero_reads_null() -> None:
    rows = []
    for book in range(12):
        partial = A4 if book % 2 else A8
        intact = A8 if book % 2 else A4
        for version, reads in (("intact", intact), ("partial", partial), ("sham", A8)):
            rows += [_row(book, version, replicate, reads) for replicate in range(2)]
    read = milder.reading(rows, CLAUDE)
    assert read["decision"] == "NULL"
    assert read["target_read_share"]["intact_minus_partial"]["point"] == 0.0


def test_fewer_than_ten_books_reads_unreadable_with_the_count_printed() -> None:
    read = milder.reading(_deterministic({"intact": A8, "partial": A4, "sham": A8}, books=9),
                          CLAUDE)
    assert read["decision"] == "UNREADABLE"
    books = next(p for p in read["preconditions"] if p["name"] == "books_complete")
    assert books == {"name": "books_complete", "measured": 9, "floor": 10, "verdict": "FAIL"}


def test_a_reader_that_left_slot_a_fails_capacity_whatever_the_intervals() -> None:
    read = milder.reading(_deterministic({"intact": A4, "partial": B8, "sham": A4}), CLAUDE)
    capacity = next(p for p in read["preconditions"] if p["name"] == "capacity")
    assert capacity["verdict"] == "FAIL"
    assert read["decision"] == "UNREADABLE"


def test_an_unscorable_share_under_the_floor_reads_unreadable() -> None:
    rows = _deterministic({"intact": A8, "partial": A4, "sham": A8})
    broken = [
        replace(row, session=replace(row.session, unanswered=1, exit_note="invalid_action"))
        if row.version == "partial" and row.feed_index < 8
        else row
        for row in rows
    ]
    read = milder.reading(broken, CLAUDE)
    assert read["per_version"]["partial"]["scorable_share"] < milder.SCORABLE_FLOOR
    assert read["decision"] == "UNREADABLE"


def test_the_codex_profile_reads_unseated_when_its_positive_control_does_not_move() -> None:
    rows = _deterministic({"intact": A8, "partial": A4, "sham": A8, "shuffled": A8})
    read = milder.reading(rows, CODEX)
    assert read["decision"] == "UNSEATED"
    seated = _deterministic({"intact": A8, "partial": A4, "sham": A8, "shuffled": A4})
    assert milder.reading(seated, CODEX)["decision"] == "MOVES_WITH_ORDER"


# ------------------------------------------------------------------------------ the meter


class FakeReader:
    """A scripted reader behind the meter's seam; counts what it was actually asked."""

    def __init__(self, *, cached: tuple[str, ...] = (), usage: dict[str, Any] | None = None,
                 stop: str = "end_turn") -> None:
        self.keys = set(cached)
        self.asked = 0
        self.usage = {"input": 10, "output": 2, "equivalent_usd": 0.03} if usage is None else usage
        self.stop = stop

    def request_key(self, system, turns, *, schema, max_tokens, sample, model=None) -> str:
        return f"{system}:{sample}"

    def cached_keys(self) -> frozenset[str]:
        return frozenset(self.keys)

    def ask_raw(self, system, turns, *, schema, max_tokens, tag, sample=0, model=None):
        self.asked += 1
        key = self.request_key(system, turns, schema=schema, max_tokens=max_tokens,
                               sample=sample)
        text = "" if self.stop != "end_turn" else json.dumps({"action": "read", "book": "A"})
        return {**tag, "key": key, "text": text, "refused": not text, "stop_reason": self.stop,
                "usage": dict(self.usage) if self.stop == "end_turn" else {}}


def _ask(meter, *, sample: int = 0, feed: str = "f") -> dict[str, Any]:
    return meter.ask_raw("s", [], schema=None, max_tokens=8, tag={"feed": feed}, sample=sample)


def _profile(**limits: float) -> Any:
    merged = {**CLAUDE.limits, **limits}
    return replace(CLAUDE, limits=merged)


def test_a_paid_call_past_a_ceiling_is_refused_before_it_is_made_and_halts() -> None:
    reader = FakeReader()
    meter = milder.Meter(reader, profile=_profile(calls=5), prior={"calls": 5})
    record = _ask(meter)
    assert record["stop_reason"] == "not_dispatched:ceiling:calls"
    assert reader.asked == 0
    assert meter.halted == "ceiling:calls"
    assert not meter.admit()


def test_a_replay_is_free_and_is_served_even_past_a_ceiling() -> None:
    reader = FakeReader(cached=("s:0",))
    meter = milder.Meter(reader, profile=_profile(calls=5), prior={"calls": 5})
    record = _ask(meter, sample=0)
    assert record["stop_reason"] == "end_turn"
    assert meter.used["calls"] == 5 and meter.replays == 1 and meter.fresh_calls == 0


def test_fresh_calls_are_tallied_in_calls_tokens_and_price() -> None:
    meter = milder.Meter(FakeReader(), profile=CLAUDE)
    _ask(meter, sample=0)
    _ask(meter, sample=1)
    assert meter.used == {"calls": 2.0, "tokens": 24.0, "usd": pytest.approx(0.06)}


def test_a_session_that_could_cross_a_ceiling_is_not_admitted_and_the_run_drains() -> None:
    meter = milder.Meter(FakeReader(), profile=_profile(calls=60), prior={"calls": 13})
    assert meter.admit()  # 13 + 24 <= 60
    assert not meter.admit()  # 13 + 2 x 24 > 60: the reservation covers the one in flight
    assert meter.draining == "ceiling:calls"
    assert meter.halted is None


def test_the_wall_clock_ceiling_is_read_before_each_session() -> None:
    clock = iter([0.0, 28_000.0, 28_000.0])
    meter = milder.Meter(FakeReader(), profile=CLAUDE, clock=lambda: next(clock))
    assert not meter.admit()
    assert meter.draining == "ceiling:seconds"


def test_three_consecutive_sessions_ending_on_a_failure_drain_the_run() -> None:
    failing = FakeReader(stop="cli_error:rc=1:You've hit your usage limit")
    meter = milder.Meter(failing, profile=CLAUDE)
    for index in range(2):
        assert meter.admit()
        _ask(meter, sample=index, feed=f"f{index}")
        assert meter.release(f"f{index}", scorable=False).startswith("cli_error")
    assert meter.draining is None
    assert meter.admit()
    _ask(meter, sample=9, feed="f9")
    meter.release("f9", scorable=False)
    assert meter.draining == "transport_circuit"
    assert meter.transport_failures == 3
    assert meter.failure_reasons == {"cli_error:rc=1:You've hit your usage limit": 3}


def test_a_session_ending_on_the_readers_own_answer_resets_the_circuit() -> None:
    meter = milder.Meter(FakeReader(stop="cli_error:rc=1:x"), profile=CLAUDE)
    for name in ("a", "b"):
        meter.admit()
        _ask(meter, feed=name, sample=ord(name))
        meter.release(name, scorable=False)
    meter.admit()
    meter.release("answered-but-invalid", scorable=False)  # no failed call: an answer
    assert meter.consecutive_failed == 0


def test_a_fresh_call_that_reports_no_usage_drains_the_run() -> None:
    meter = milder.Meter(FakeReader(usage={}), profile=CLAUDE)
    _ask(meter)
    assert meter.draining == "unknown_usage"
    unpriced = milder.Meter(FakeReader(usage={"input": 5, "output": 1}), profile=CLAUDE)
    _ask(unpriced)
    assert unpriced.draining == "unknown_usage"
    codex = milder.Meter(FakeReader(usage={"input": 5, "output": 1}), profile=CODEX)
    _ask(codex)
    assert codex.draining is None  # the Codex transport reports no price by construction


def test_a_changed_binary_halts_before_the_next_session() -> None:
    meter = milder.Meter(FakeReader(), profile=CLAUDE, binary_guard=lambda: "binary_changed")
    assert not meter.admit()
    assert meter.halted == "halt:binary_changed"


def test_a_reader_halt_refuses_the_call_and_every_later_one() -> None:
    class Halting(FakeReader):
        def ask_raw(self, *args, **kwargs):
            raise milder.ReaderHalt("codex CLI changed")

    meter = milder.Meter(Halting(), profile=CODEX)
    assert _ask(meter)["stop_reason"] == "not_dispatched:halt"
    assert meter.halted == "halt:codex CLI changed"
    assert _ask(meter, sample=1)["stop_reason"].startswith("not_dispatched:halt:codex")


# ---------------------------------------------------------------------------- the readers


SYSTEM = feed_core.SYSTEM
TURNS = [{"role": "user", "content": "Book A, section 4:\n\nText."}]


def test_the_claude_readers_key_is_the_key_elicit_caches_under(tmp_path) -> None:
    with milder.ClaudeReader(tmp_path / "raw.jsonl", model="claude-haiku-4-5") as reader:
        reader.dry_run = True  # elicit's synthetic answer, which carries the key it computed
        record = reader.ask_raw(SYSTEM, TURNS, schema=feed_core.ACTION_SCHEMA, max_tokens=48,
                                tag={"feed": "x"}, sample=29)
        assert record["key"] == reader.request_key(
            SYSTEM, TURNS, schema=feed_core.ACTION_SCHEMA, max_tokens=48, sample=29
        )
    assert not (tmp_path / "raw.jsonl").exists()


def test_a_replay_only_claude_reader_serves_the_cache_and_makes_no_call(tmp_path, monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("a replay-only reader started a process")

    monkeypatch.setattr(elicit.subprocess, "run", refuse)
    with milder.ClaudeReader(tmp_path / "raw.jsonl", model="claude-haiku-4-5",
                             replay_only=True) as reader:
        record = reader.ask_raw(SYSTEM, TURNS, schema=None, max_tokens=48, tag={"feed": "x"})
        assert record["stop_reason"] == milder.NOT_IN_CACHE
        assert reader.transport_failures == 0 and reader.api_calls == 0
    assert not (tmp_path / "raw.jsonl").exists()


class FakeProvider:
    """`CodexCliProvider.complete`'s seam with scripted answers or failures."""

    def __init__(self, answer: Any = None, *, version: str = "codex-cli test",
                 fail_after: int | None = None) -> None:
        self.answer = answer or (lambda prompt: {"action": "read", "book": "A"})
        self.version = version
        self.fail_after = fail_after
        self.calls = 0

    def complete(self, request):
        self.calls += 1
        if self.fail_after is not None and self.calls > self.fail_after:
            raise ProviderError("usage limit reached for this plan",
                                kind=ProviderFailureKind.RATE_LIMIT)
        return CompletionResult(
            text=json.dumps(self.answer(request.prompt)), provider="codex", model=request.model,
            usage=Usage(input_tokens=90, output_tokens=6, cache_read_tokens=30),
            raw={"cli_version": self.version},
        )


def _codex_reader(path: Path, provider: Any, **kwargs: Any) -> Any:
    return milder.CodexReader(path, provider=provider, model=CODEX.model, effort=CODEX.effort,
                              cli_version="codex-cli test", **kwargs)


def test_a_codex_transport_failure_is_counted_and_never_cached(tmp_path) -> None:
    provider = FakeProvider(fail_after=0)
    with _codex_reader(tmp_path / "raw.jsonl", provider) as reader:
        record = reader.ask_raw(SYSTEM, TURNS, schema=feed_core.ACTION_SCHEMA, max_tokens=48,
                                tag={"feed": "x"})
        assert record["stop_reason"].startswith("transport_error:codex:rate_limit")
        assert elicit._is_transport_failure(record["stop_reason"])
        assert reader.transport_failures == 1
    assert not (tmp_path / "raw.jsonl").exists()


def test_a_codex_answer_is_cached_and_replays_without_a_call(tmp_path) -> None:
    provider = FakeProvider()
    kwargs = {"schema": feed_core.ACTION_SCHEMA, "max_tokens": 48, "tag": {"feed": "x"},
              "sample": 3}
    with _codex_reader(tmp_path / "raw.jsonl", provider) as reader:
        first = reader.ask_raw(SYSTEM, TURNS, **kwargs)
    assert first["usage"]["equivalent_usd"] is None
    with _codex_reader(tmp_path / "raw.jsonl", provider) as again:
        assert again.ask_raw(SYSTEM, TURNS, **kwargs)["key"] == first["key"]
        assert again.replayed == 1
    assert provider.calls == 1


def test_an_old_cached_failure_is_left_aside_to_re_issue(tmp_path) -> None:
    raw = tmp_path / "raw.jsonl"
    raw.write_text(json.dumps({"key": "k:0", "stop_reason": "transport_error:codex:x"}) + "\n",
                   encoding="utf-8")
    with _codex_reader(raw, FakeProvider()) as reader:
        assert reader.left_aside == 1 and "k:0" not in reader.cached_keys()


def test_a_changed_codex_cli_version_halts(tmp_path) -> None:
    with (
        _codex_reader(tmp_path / "raw.jsonl", FakeProvider(version="codex-cli 9")) as reader,
        pytest.raises(milder.ReaderHalt, match="codex-cli 9"),
    ):
        reader.ask_raw(SYSTEM, TURNS, schema=feed_core.ACTION_SCHEMA, max_tokens=48,
                       tag={"feed": "x"})


class ScriptedCodexRunner:
    """The subprocess seam of the production Codex adapter, answering one action."""

    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.systems: list[str] = []

    def __call__(self, argv, *, timeout, cwd, env, stdin=""):
        if "login" in argv:
            return CommandResult(0, "", "Logged in using ChatGPT")
        if "--version" in argv:
            return CommandResult(0, "codex-cli test\n", "")
        self.prompts.append(stdin)
        for index, arg in enumerate(argv):
            if arg == "-c" and argv[index + 1].startswith("model_instructions_file="):
                path = json.loads(argv[index + 1].split("=", 1)[1])
                self.systems.append(Path(path).read_text(encoding="utf-8"))
        text = json.dumps({"action": "skim", "book": "C"})
        Path(argv[argv.index("--output-last-message") + 1]).write_text(text, encoding="utf-8")
        events = [
            {"type": "thread.started", "thread_id": "t"},
            {"type": "turn.started"},
            {"type": "item.completed", "item": {"type": "agent_message", "text": text}},
            {"type": "turn.completed", "usage": {"input_tokens": 50, "cached_input_tokens": 10,
                                                 "output_tokens": 5,
                                                 "reasoning_output_tokens": 1}},
        ]
        return CommandResult(0, "\n".join(json.dumps(event) for event in events), "")


def test_the_production_codex_adapter_carries_the_feed_request_and_its_schema(tmp_path):
    runner = ScriptedCodexRunner()
    provider = milder.codex_provider(CODEX, "codex.exe", runner=runner)
    turns = [{"role": "user", "content": "opening"}, {"role": "assistant", "content": "{}"},
             {"role": "user", "content": "next"}]
    with _codex_reader(tmp_path / "raw.jsonl", provider) as reader:
        record = reader.ask_raw(SYSTEM, turns, schema=feed_core.ACTION_SCHEMA, max_tokens=48,
                                tag={"feed": "x"})
    assert json.loads(record["text"]) == {"action": "skim", "book": "C"}
    assert runner.prompts == [elicit._flatten_turns(turns)]
    # The system block `elicit._call_cli` sends `claude -p`, schema sentence included.
    assert runner.systems == [
        SYSTEM + "\n\nReply with a single JSON object conforming to this schema and nothing "
        "else — no prose, no code fence:\n" + json.dumps(feed_core.ACTION_SCHEMA,
                                                              sort_keys=True)
    ]
    assert record["usage"] == {"input": 40, "output": 4, "cache_read": 10, "cache_write": 0,
                               "reasoning": 1, "equivalent_usd": None}


def test_the_codex_profile_refuses_a_shell_shim_for_its_binary(tmp_path) -> None:
    shim = tmp_path / "codex.CMD"
    shim.write_text("@echo off\n", encoding="utf-8")
    with pytest.raises(ValueError, match="native executable"):
        milder.binary_info(CODEX, shim)
    with pytest.raises(ValueError, match="--codex-binary"):
        milder.binary_info(CODEX, None)


# --------------------------------------------------------- run and analyse, end to end


_LABEL = re.compile(r"B(\d+)p(\d+)w0\b")


def _order_reader(prompt: str) -> dict[str, str]:
    """Reads slot A when its opening paragraphs are in order, else a competitor."""
    opening = prompt.split("Book B, the story so far", 1)[0]
    labels = [int(p) for _, p in _LABEL.findall(opening)]
    book = int(_LABEL.findall(opening)[0][0])
    if labels[:3] == [0, 1, 2]:
        return {"action": "read", "book": "A"}
    return {"action": "read", "book": "BCD"[book % 3]}


def _harness(tmp_path, monkeypatch, provider, *, books: int = 10):
    monkeypatch.setattr(milder, "REPLICATES", 1)
    paths = milder.Paths(root=tmp_path, arm_dir=tmp_path / "arm", local=tmp_path / "local",
                         fitness_dir=tmp_path / "fit", lock_holder=tmp_path / "lock" / "holder")
    paths.arm_dir.mkdir()
    (paths.arm_dir / "PREREG.md").write_text("registration\n", encoding="utf-8")
    planned = milder.plan(_books(books), CODEX)
    reg = {"registration_digest": milder.registration_digest(CODEX),
           "reader": {"binary": "codex.exe", "binary_sha256": "0" * 64,
                      "binary_version": "codex-cli test"}}
    paths.registration(CODEX).write_text(json.dumps(reg), encoding="utf-8")

    def verifier(profile, **kwargs):
        return reg, planned

    def factory(profile, paths_, reg_, *, replay_only):
        return _codex_reader(paths.raw(CODEX), provider, replay_only=replay_only)

    return paths, planned, verifier, factory


def _probe_ok(profile, reg):
    return {"agents_md": {"text": "NONE", "stop_reason": "end_turn",
                          "usage": {"input": 3, "output": 1}}}


def test_a_run_then_its_analysis_read_the_transport_first_and_decide(tmp_path, monkeypatch):
    provider = FakeProvider(_order_reader)
    paths, planned, verifier, factory = _harness(tmp_path, monkeypatch, provider)
    lines: list[str] = []
    ledger = milder.run(CODEX, paths=paths, verifier=verifier, reader_factory=factory,
                        probe=_probe_ok, workers=2, log=lines.append)
    assert ledger["complete"] and ledger["stop"] is None
    assert ledger["sessions_completed"] == len(planned) == 40
    assert not any("share" in line for line in lines)  # no reading can be watched forming
    calls = provider.calls
    result = milder.analyse(CODEX, paths=paths, verifier=verifier, reader_factory=factory)
    assert provider.calls == calls  # the analysis made no call
    transport = result["transport"]
    assert transport["coverage"] == "complete" and transport["sessions_missing"] == 0
    assert transport["cached_transport_failures"] == 0
    assert transport["probes"][0]["agents_md"]["passed"] is True
    assert transport["sessions_dispatched"] == len(planned)
    read = result["reading"]
    assert read["decision"] == "MOVES_WITH_ORDER"
    assert {p["name"]: p["verdict"] for p in read["preconditions"]}["positive_control"] == "PASS"
    claim = json.loads(paths.claim(CODEX).read_text(encoding="utf-8"))
    record = governance.parse_claim(claim)
    assert record.status.value == "observed"
    assert {ref.kind.value for ref in record.artifacts} >= {"registration", "raw_result",
                                                            "derived_result", "control_result"}
    with pytest.raises(RuntimeError, match="written once"):
        milder.analyse(CODEX, paths=paths, verifier=verifier, reader_factory=factory)
    with pytest.raises(RuntimeError, match="no session is bought after"):
        milder.run(CODEX, paths=paths, verifier=verifier, reader_factory=factory,
                   probe=_probe_ok)


def test_a_usage_limit_drains_the_run_and_a_resume_buys_only_what_never_answered(
    tmp_path, monkeypatch
):
    flaky = FakeProvider(_order_reader, fail_after=100)
    paths, planned, verifier, factory = _harness(tmp_path, monkeypatch, flaky)
    first = milder.run(CODEX, paths=paths, verifier=verifier, reader_factory=factory,
                       probe=_probe_ok, workers=1, log=lambda _: None)
    assert first["stop"] == "transport_circuit" and not first["complete"]
    assert first["transport_failures"] == milder.TRANSPORT_CIRCUIT
    assert first["failure_reasons"]
    assert milder.cached_failures(paths.raw(CODEX)) == 0
    healthy = FakeProvider(_order_reader)

    def factory_again(profile, paths_, reg_, *, replay_only):
        return _codex_reader(paths.raw(CODEX), healthy, replay_only=replay_only)

    second = milder.run(CODEX, paths=paths, verifier=verifier, reader_factory=factory_again,
                        probe=_probe_ok, workers=1, log=lambda _: None)
    assert second["complete"] and second["invocation"] == 2
    assert healthy.calls == len(planned) * 8 - 100  # nothing bought twice
    assert second["used_cumulative"]["calls"] == 2 + len(planned) * 8 + 3
    ledgers = milder.read_ledgers(paths.ledger(CODEX))
    assert [entry["stop"] for entry in milder.invocations(ledgers)] == ["transport_circuit", None]
    # Every session left a checkpoint, so a kill would have lost none of this from the ledger:
    # twelve bought whole, the thirteenth failed at its fifth call, two more failed at once.
    assert [
        sum(1 for line in ledgers if line["event"] == "session" and line["invocation"] == n)
        for n in (1, 2)
    ] == [15, len(planned)]


def test_an_analysis_of_a_stopped_run_is_partial_and_names_the_tail_block(
    tmp_path, monkeypatch
):
    paths, planned, verifier, factory = _harness(tmp_path, monkeypatch,
                                                 FakeProvider(_order_reader, fail_after=120))
    milder.run(CODEX, paths=paths, verifier=verifier, reader_factory=factory,
               probe=_probe_ok, workers=1, log=lambda _: None)
    result = milder.analyse(CODEX, paths=paths, verifier=verifier, reader_factory=factory)
    transport = result["transport"]
    assert transport["coverage"] == "partial"
    assert transport["missing_is_tail_block"] is True
    assert transport["missing_feed_ids"][-1] == planned[-1].cell.spec.feed_id
    assert any(warning.startswith("partial") for warning in result["warnings"])


def test_a_failed_isolation_probe_buys_nothing(tmp_path, monkeypatch) -> None:
    provider = FakeProvider(_order_reader)
    paths, _, verifier, _ = _harness(tmp_path, monkeypatch, provider)
    opened = []

    def factory(*args, **kwargs):
        opened.append(True)
        raise AssertionError("the arm reader was opened after a failed probe")

    with pytest.raises(RuntimeError, match="isolation probe failed"):
        milder.run(CODEX, paths=paths, verifier=verifier, reader_factory=factory,
                   probe=lambda profile, reg: {"agents_md": {"text": "LEAKED", "usage": {}}})
    assert not opened and provider.calls == 0
    lines = milder.read_ledgers(paths.ledger(CODEX))
    assert [line["event"] for line in lines] == ["started", "finished"]
    assert milder.invocations(lines)[0]["stop"] == "isolation_probe_failed"
    # A probe-only invocation bought nothing, so the registration may still be refreshed.
    assert milder.purchases(CODEX, paths)["any"] is False


def test_a_probe_that_obtains_no_answer_is_a_transport_failure_not_a_leak(
    tmp_path, monkeypatch
) -> None:
    paths, _, verifier, factory = _harness(tmp_path, monkeypatch, FakeProvider())
    with pytest.raises(RuntimeError, match="probe transport failure"):
        milder.run(CODEX, paths=paths, verifier=verifier, reader_factory=factory,
                   probe=lambda profile, reg: {"agents_md": {
                       "text": "", "usage": {}, "stop_reason": "cli_error:rc=1:usage limit"}})
    ledger = milder.invocations(milder.read_ledgers(paths.ledger(CODEX)))[0]
    assert ledger["stop"] == "probe_transport_failure"
    assert ledger["used_cumulative"]["calls"] == 1  # the probe was dispatched and counts


def test_a_ceiling_reached_by_earlier_invocations_buys_nothing_not_even_a_probe(
    tmp_path, monkeypatch
) -> None:
    paths, _, verifier, factory = _harness(tmp_path, monkeypatch, FakeProvider())
    milder.append_ledger(paths.ledger(CODEX), {
        "used_cumulative": {"calls": CODEX.limits["calls"], "tokens": 0, "usd": 0.0},
        "seconds_cumulative": 10.0,
    })

    def probe(profile, reg):
        raise AssertionError("a probe was bought past a ceiling")

    with pytest.raises(RuntimeError, match="calls ceiling is already reached"):
        milder.run(CODEX, paths=paths, verifier=verifier, reader_factory=factory, probe=probe)


def test_a_cache_this_arm_did_not_write_is_refused_before_anything_is_bought(
    tmp_path, monkeypatch
) -> None:
    paths, _, verifier, factory = _harness(tmp_path, monkeypatch, FakeProvider())

    def probe(profile, reg):
        raise AssertionError("a probe was bought over a foreign cache")

    # v2's intact requests are byte-identical to this arm's: its records must never be served.
    paths.raw(CODEX).write_text(
        json.dumps({"feed": "ctb2-00-intact-r0", "key": "k:0", "stop_reason": "end_turn"}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="no invocation of this arm started"):
        milder.run(CODEX, paths=paths, verifier=verifier, reader_factory=factory, probe=probe)
    milder.append_ledger(paths.ledger(CODEX), {"event": "started", "invocation": 1,
                                                "started_at": "t", "used_cumulative": {},
                                                "seconds_cumulative": 0})
    with pytest.raises(RuntimeError, match="belong to no session of this arm"):
        milder.run(CODEX, paths=paths, verifier=verifier, reader_factory=factory, probe=probe)
    with pytest.raises(RuntimeError, match="belong to no session of this arm"):
        milder.analyse(CODEX, paths=paths, verifier=verifier, reader_factory=factory)


def test_a_cached_transport_failure_refuses_the_reading(tmp_path, monkeypatch) -> None:
    paths, _, verifier, factory = _harness(tmp_path, monkeypatch, FakeProvider())
    paths.raw(CODEX).write_text(
        json.dumps({"key": "k:0", "stop_reason": "cli_error:rc=1:boom", "text": ""}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="§235"):
        milder.analyse(CODEX, paths=paths, verifier=verifier, reader_factory=factory)
    assert not paths.results(CODEX).exists()


def test_an_analysis_with_nothing_bought_is_refused(tmp_path, monkeypatch) -> None:
    paths, _, verifier, factory = _harness(tmp_path, monkeypatch, FakeProvider())
    with pytest.raises(RuntimeError, match="nothing was bought"):
        milder.analyse(CODEX, paths=paths, verifier=verifier, reader_factory=factory)


# ------------------------------------------------------------- prepare and verify refusals


def _identity_ok(profile, planned, paths):
    return {"cells": 24, "replayed_complete": 24, "max_abs_book_mean_diff": 0.0, "passed": True}


class Frozen:
    """A scratch repository: sources, a prepared registration, a fake git and binary."""

    def __init__(self, tmp_path: Path, monkeypatch) -> None:
        self.root = tmp_path
        self.paths = milder.Paths(root=tmp_path, arm_dir=tmp_path / "arm",
                                  local=tmp_path / "runs" / "arm", fitness_dir=tmp_path / "fit",
                                  lock_holder=tmp_path / "runs" / "box.lock" / "holder")
        self.paths.arm_dir.mkdir(parents=True)
        (self.paths.arm_dir / "PREREG.md").write_text("the registration\n", encoding="utf-8")
        self.source = tmp_path / "module.py"
        self.source.write_text("frozen = True\n", encoding="utf-8")
        monkeypatch.setattr(milder, "sources",
                            lambda profile, paths: [self.source, paths.arm_dir / "PREREG.md"])
        self.binary = {"binary": "claude.exe", "binary_sha256": "a" * 64,
                       "binary_version": "2.1.280 (Claude Code)"}
        self.committed: dict[str, bytes] = {}
        self.pushed = b"  origin/main\n"
        self.registration = self.prepare()
        self.commit()

    def prepare(self, **kwargs: Any) -> dict[str, Any]:
        options: dict[str, Any] = {
            "texts_loader": lambda d: (_books(4), {"x.db": "b" * 64}),
            "binary_reader": lambda profile, codex: dict(self.binary),
            "identity_check": _identity_ok,
        }
        return milder.prepare(CLAUDE, paths=self.paths, **{**options, **kwargs})

    def commit(self) -> None:
        names = [milder._rel(self.paths.registration(CLAUDE), self.root),
                 *self.registration["source_hashes"]]
        self.committed = {name: (self.root / name).read_bytes() for name in names}

    def git(self, args, root):
        if args[0] == "show":
            name = args[1].removeprefix("HEAD:")
            if name not in self.committed:
                raise subprocess.CalledProcessError(128, ["git", *args])
            return self.committed[name]
        return self.pushed

    def verify(self, **kwargs):
        return milder.verify(CLAUDE, paths=self.paths, git=self.git,
                             binary_reader=lambda profile, codex: dict(self.binary), **kwargs)


def test_a_prepared_committed_pushed_registration_verifies(tmp_path, monkeypatch) -> None:
    frozen = Frozen(tmp_path, monkeypatch)
    reg, planned = frozen.verify()
    assert len(planned) == reg["plan"]["sessions"] == 72
    assert reg["reader"]["disclosed_changes"][0].startswith("Claude CLI 2.1.280")
    claim = json.loads(frozen.paths.claim(CLAUDE).read_text(encoding="utf-8"))
    assert governance.parse_claim(claim).status.value == "registered"
    assert {a["path"] for a in claim["artifacts"]} == {"arm/PREREG.md", "arm/registration.json"}


def test_verify_refuses_a_changed_frozen_file(tmp_path, monkeypatch) -> None:
    frozen = Frozen(tmp_path, monkeypatch)
    frozen.source.write_text("frozen = False\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match=re.escape("changed frozen file: module.py")):
        frozen.verify()


def test_verify_refuses_changed_texts(tmp_path, monkeypatch) -> None:
    frozen = Frozen(tmp_path, monkeypatch)
    frozen.paths.texts(CLAUDE).write_text('{"fitness": []}\n', encoding="utf-8")
    with pytest.raises(RuntimeError, match="prepared texts"):
        frozen.verify()


def test_verify_refuses_an_uncommitted_or_differently_committed_file(tmp_path, monkeypatch):
    frozen = Frozen(tmp_path, monkeypatch)
    del frozen.committed["arm/registration.json"]
    with pytest.raises(RuntimeError, match=re.escape("not committed: arm/registration.json")):
        frozen.verify()
    frozen.commit()
    frozen.committed["module.py"] = b"frozen = 'other'\n"
    with pytest.raises(RuntimeError, match=re.escape("not committed as registered: module.py")):
        frozen.verify()


def test_verify_refuses_an_unpushed_commit(tmp_path, monkeypatch) -> None:
    frozen = Frozen(tmp_path, monkeypatch)
    frozen.pushed = b""
    with pytest.raises(RuntimeError, match="push it first"):
        frozen.verify()


def test_verify_refuses_a_changed_binary(tmp_path, monkeypatch) -> None:
    frozen = Frozen(tmp_path, monkeypatch)
    frozen.binary["binary_version"] = "2.1.281 (Claude Code)"
    with pytest.raises(RuntimeError, match="binary changed: binary_version"):
        frozen.verify()


def test_verify_refuses_changed_constants(tmp_path, monkeypatch) -> None:
    frozen = Frozen(tmp_path, monkeypatch)
    monkeypatch.setattr(milder, "DOSE", 0.35)
    with pytest.raises(RuntimeError, match="registered constants differ"):
        frozen.verify()


def test_a_run_needs_the_box_lock_held_by_this_task(tmp_path, monkeypatch) -> None:
    frozen = Frozen(tmp_path, monkeypatch)
    with pytest.raises(RuntimeError, match="not held"):
        frozen.verify(check_lock=True)
    holder = frozen.paths.lock_holder
    holder.parent.mkdir(parents=True)
    holder.write_text("promise-payoff-challenge-20260922: other\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="held by someone else"):
        frozen.verify(check_lock=True)
    holder.write_text("﻿cost-that-bites-milder-20260922: milder-v4, 12:00\n",
                      encoding="utf-8")
    frozen.verify(check_lock=True)


def test_prepare_is_refused_once_a_cell_was_bought_and_not_after_a_probe_only_invocation(
    tmp_path, monkeypatch
) -> None:
    frozen = Frozen(tmp_path, monkeypatch)
    ledger = frozen.paths.ledger(CLAUDE)
    # A probe that failed (or a usage window waited out) bought nothing: re-registering after a
    # binary update must stay possible, or the arm would be stranded with nothing bought.
    milder.append_ledger(ledger, {"event": "started", "invocation": 1, "started_at": "t"})
    milder.append_ledger(ledger, {"event": "finished", "invocation": 1, "finished_at": "t",
                                  "stop": "probe_transport_failure", "fresh_calls": 0})
    frozen.binary["binary_version"] = "2.1.281 (Claude Code)"
    assert frozen.prepare()["reader"]["binary_version"] == "2.1.281 (Claude Code)"
    milder.append_ledger(ledger, {"event": "session", "invocation": 2, "fresh_calls": 5})
    with pytest.raises(RuntimeError, match="never refreshed after a cell was bought"):
        frozen.prepare()
    ledger.unlink()
    frozen.paths.raw(CLAUDE).write_text(
        json.dumps({"feed": "ctbm4-00-intact-r0", "key": "k:0", "stop_reason": "end_turn"})
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="never refreshed after a cell was bought"):
        frozen.prepare()


def test_prepare_refuses_when_the_request_identity_check_fails(tmp_path, monkeypatch) -> None:
    frozen = Frozen(tmp_path, monkeypatch)
    frozen.paths.registration(CLAUDE).unlink()
    with pytest.raises(RuntimeError, match="request identity failed"):
        frozen.prepare(identity_check=lambda profile, planned, paths: {
            "cells": 24, "replayed_complete": 23, "passed": False})
    assert not frozen.paths.registration(CLAUDE).exists()


def test_verify_refuses_a_registration_without_a_passed_identity_check(tmp_path, monkeypatch):
    frozen = Frozen(tmp_path, monkeypatch)
    reg = json.loads(frozen.paths.registration(CLAUDE).read_text(encoding="utf-8"))
    reg["request_identity"] = None
    frozen.paths.registration(CLAUDE).write_text(json.dumps(reg), encoding="utf-8")
    with pytest.raises(RuntimeError, match="no passed request-identity check"):
        frozen.verify()


# ----------------------------------------------------------------- the committed record


def test_the_committed_claim_validates_and_claims_no_more_than_its_artifacts_allow() -> None:
    path = milder.ARM_DIR / "claim.json"
    record = governance.load_and_verify(path)
    assert record.claim_id == "cost-that-bites.milder-v4.claude"
    if record.status.value == "registered":
        assert {ref.kind.value for ref in record.artifacts} == {"registration"}
    else:
        assert record.status.value == "observed"


def test_the_power_record_is_in_the_repository_and_cited_by_hash() -> None:
    text = (milder.ARM_DIR / "ATTAINABILITY.md").read_text(encoding="utf-8")
    registered = {
        milder._rel(path, milder.ROOT) for path in milder.sources(CLAUDE)
    }
    for name in ("milder_dose_power.py", "results.json", "noise_check.py", "noise_check.json",
                 "export_texts.py", "run.log"):
        path = milder.ARM_DIR / "attainability" / name
        assert milder.file_sha(path) in text, name
        # Cited by hash in prose and content-addressed by the registration, so verify checks it.
        assert milder._rel(path, milder.ROOT) in registered, name


# ------------------------------------------------------------- since review: the operator


def _power_record() -> Any:
    """The power record's own script, loaded by path; its import defines and computes nothing."""
    pytest.importorskip("numpy")
    path = milder.ARM_DIR / "attainability" / "milder_dose_power.py"
    spec = importlib.util.spec_from_file_location("milder_dose_power_record", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    before = sys.dont_write_bytecode
    sys.dont_write_bytecode = True  # a committed record gets no __pycache__ beside it
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = before
    return module


def test_the_registered_operator_is_the_power_records_perm_partial() -> None:
    record = _power_record()
    texts = [_prose(count, marker=marker)
             for count, marker in ((5, "a"), (12, "b"), (37, "c"), (58, "d"), (90, "e"))]
    texts += [ctb._member_text("b7"), _alternating(13)]
    for text in texts:
        for index in range(10):
            for strength in (0.35, 0.65):
                assert milder.partial_order(text, strength=strength, index=index) == (
                    record.perm_partial(text, strength, index)
                ), (len(ablate.paragraphs(text)), index, strength)


def test_every_licence_clause_that_reaches_section_230_is_conditional_on_the_reader() -> None:
    for decision in ("MOVES_WITH_ORDER", "NULL", "INVERTED"):
        text = milder.LICENCE[decision]
        assert milder._IF_SAME in text
        assert text.index(milder._IF_SAME) < text.index("§230's"), decision
    assert "0.88" in milder.LICENCE["MOVES_WITH_ORDER"]
    assert "0.69 to 0.90" in milder.LICENCE["NULL"]
    for text in milder.LICENCE_CODEX.values():
        assert "§230" not in text or "neither extends nor narrows" in text or "not touched" in text
    assert milder.licence(CODEX) is milder.LICENCE_CODEX
    assert milder.pre_registration(CODEX)["decision"] == milder.LICENCE_CODEX


def test_the_same_reader_baseline_is_what_the_committed_v2_and_v3_results_say() -> None:
    v2 = json.loads(milder.V2_RESULTS.read_text(encoding="utf-8"))
    v3 = json.loads((milder.V2_DIR / "results-arm-v3.json").read_text(encoding="utf-8"))
    baseline = milder.SAME_READER_BASELINE
    for version in milder.IDENTITY_VERSIONS:
        block = ctb.interval_block([
            (book, v3["reading"]["book_means"][book][version]
             - v2["reading"]["book_means"][book][version])
            for book in sorted(v2["reading"]["book_means"])
        ])
        assert {key: round(block[key], 4) for key in ("point", "low", "high")} == (
            baseline[version]
        )
    # Why no level rule is registered: the same reader, run twice, already excludes zero.
    assert baseline["intact"]["low"] > 0

    def actions(result: dict[str, Any]) -> dict[tuple[int, str, int], Any]:
        return {(row["feed_index"], row["version"], row["session"]["replicate"]):
                row["session"]["actions"] for row in result["rows"]}

    theirs, ours = actions(v2), actions(v3)
    for version, stated in baseline["identical_sequences"].items():
        keys = [key for key in theirs if key[1] == version and key in ours]
        same = sum(1 for key in keys if theirs[key] == ours[key])
        assert f"{same} of {len(keys)}" == stated


def test_a_probe_passes_on_the_house_comparison() -> None:
    assert milder.probe_passed("claude_md", {"text": "NONE."})
    assert not milder.probe_passed("claude_md", {"text": "LEAKED"})
    assert not milder.probe_passed("claude_md", {"text": "NONE, or LEAKED"})
    assert not milder.probe_passed("claude_md", {"text": ""})
    assert milder.probe_passed("git_status", {"text": "NONE"})
    assert not milder.probe_passed("git_status", {"text": "GIT_CONTEXT_LEAKED"})
    assert milder.probe_names(CLAUDE) == ("claude_md", "git_status")
    assert milder.probe_names(CODEX) == ("agents_md",)


# ------------------------------------------------------------------ since review: the pin


def _binary(tmp_path: Path, content: bytes = b"a scripted claude\n") -> Path:
    path = tmp_path / "install" / ("claude.exe" if os.name == "nt" else "claude")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    path.chmod(0o755)
    return path


def _reg_for(binary: Path) -> dict[str, Any]:
    return {
        "registration_digest": milder.registration_digest(CLAUDE),
        "request_identity": {"passed": True},
        "reader": {"binary": str(binary), "binary_sha256": milder.file_sha(binary),
                   "binary_version": "2.1.280 (Claude Code)"},
    }


def _version(path: Path) -> str:
    return "2.1.280 (Claude Code)"


def _scratch_paths(tmp_path: Path, **kwargs: Any) -> Any:
    return milder.Paths(root=tmp_path, arm_dir=tmp_path / "arm", local=tmp_path / "local",
                        fitness_dir=tmp_path / "fit", lock_holder=tmp_path / "lock" / "holder",
                        **kwargs)


def test_the_binary_is_pinned_once_and_an_update_of_the_original_changes_nothing(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("PATH", os.environ.get("PATH", ""))  # restored after the pin prepends
    paths = _scratch_paths(tmp_path)
    original = _binary(tmp_path)
    reg = _reg_for(original)
    pinned = milder.pin_cli(CLAUDE, paths, reg, version_reader=_version)
    assert pinned.parent == paths.pin_dir(CLAUDE, reg["reader"]["binary_sha256"])
    assert milder.file_sha(pinned) == reg["reader"]["binary_sha256"]
    assert milder.resolve_cli("claude") == pinned.resolve()
    # An interactive session updates the install in place; the arm keeps its registered copy.
    original.write_bytes(b"claude 2.1.281, installed by an interactive session\n")
    assert milder.pin_cli(CLAUDE, paths, reg, version_reader=_version) == pinned
    with pytest.raises(RuntimeError, match="reports another version"):
        milder.pin_cli(CLAUDE, paths, reg, version_reader=lambda path: "2.1.281 (Claude Code)")
    pinned.write_bytes(b"tampered\n")
    with pytest.raises(RuntimeError, match="does not hash to the registration"):
        milder.pin_cli(CLAUDE, paths, reg, version_reader=_version)


def test_a_binary_that_changed_before_it_was_pinned_is_refused(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PATH", os.environ.get("PATH", ""))
    original = _binary(tmp_path)
    reg = _reg_for(original)
    original.write_bytes(b"updated before the first run\n")
    with pytest.raises(RuntimeError, match="no longer hashes to the registration"):
        milder.pin_cli(CLAUDE, _scratch_paths(tmp_path), reg, version_reader=_version)


# ------------------------------------------- since review: the Claude arm, end to end


def _envelope(text: str) -> str:
    """The `claude -p --output-format json` envelope `elicit._call_cli` parses."""
    return json.dumps({
        "type": "result", "subtype": "success", "is_error": False, "result": text,
        "stop_reason": "end_turn", "total_cost_usd": 0.0021,
        "modelUsage": {"claude-haiku-4-5": {"inputTokens": 120, "outputTokens": 6,
                                            "cacheReadInputTokens": 40,
                                            "cacheCreationInputTokens": 0}},
    })


class ScriptedClaude:
    """`subprocess.run` as `elicit._call_cli` and the probes call it.

    `claude -p` answers from a script (the probes NONE., the arm by `_order_reader`), after
    checking the §109 flags ride on every call; `git`, which the git-status probe runs, is the
    real one. Records what each probe's directory held and the auto-updater setting each call
    inherited.
    """

    def __init__(self, real: Any, *, fail_after: int | None = None, on_arm_call: Any = None):
        self.real = real
        self.fail_after = fail_after
        self.on_arm_call = on_arm_call
        self.arm_calls = 0
        self.probe_dirs: list[dict[str, bool]] = []
        self.updater: set[str | None] = set()

    def __call__(self, argv: list[str], *args: Any, **kwargs: Any) -> Any:
        if argv[0] == "git":
            return self.real(argv, *args, **kwargs)
        assert argv[0] == "claude" and "-p" in argv
        assert {"--setting-sources", "--exclude-dynamic-system-prompt-sections"} <= set(argv)
        self.updater.add(os.environ.get("DISABLE_AUTOUPDATER"))
        system = argv[argv.index("--system-prompt") + 1]
        if system in (milder.PROBE_SYSTEM, milder.GIT_PROBE_SYSTEM):
            here = Path.cwd()
            self.probe_dirs.append({
                "claude_md": (here / "CLAUDE.md").is_file(),
                "git": (here / ".git").is_dir(),
                "git_marker": (here / milder.GIT_PROBE_FILE).is_file(),
            })
            return subprocess.CompletedProcess(argv, 0, stdout=_envelope("NONE."), stderr="")
        self.arm_calls += 1
        if self.on_arm_call is not None:
            self.on_arm_call(self.arm_calls)
        if self.fail_after is not None and self.arm_calls > self.fail_after:
            return subprocess.CompletedProcess(
                argv, 1, stdout="", stderr="You've hit your usage limit · resets 5pm\n"
            )
        answer = _order_reader(kwargs["input"])
        return subprocess.CompletedProcess(argv, 0, stdout=_envelope(json.dumps(answer)),
                                           stderr="")


def _claude_harness(tmp_path, monkeypatch, scripted: ScriptedClaude, *, books: int = 10):
    monkeypatch.setattr(milder, "REPLICATES", 1)
    monkeypatch.setattr(elicit.subprocess, "run", scripted)
    monkeypatch.setenv("PATH", os.environ.get("PATH", ""))
    monkeypatch.delenv("DISABLE_AUTOUPDATER", raising=False)
    paths = _scratch_paths(tmp_path, v2_raw=tmp_path / "v2" / "raw-v2.jsonl",
                           v2_results=tmp_path / "v2" / "results-arm-v2.json")
    paths.arm_dir.mkdir()
    (paths.arm_dir / "PREREG.md").write_text("registration\n", encoding="utf-8")
    planned = milder.plan(_books(books), CLAUDE)
    reg = _reg_for(_binary(tmp_path))
    paths.registration(CLAUDE).write_text(json.dumps(reg), encoding="utf-8")

    def verifier(profile, **kwargs):
        return reg, planned

    pinner = functools.partial(milder.pin_cli, version_reader=_version)
    return paths, planned, reg, verifier, pinner


def _v2_like(paths: Any, planned: list[Any]) -> list[Any]:
    """What a v2 run of the identity cells leaves behind: its cache and its committed result."""
    cells = [
        item for item in planned
        if item.cell.version in milder.IDENTITY_VERSIONS
        and item.cell.replicate < milder.IDENTITY_REPLICATES
    ]
    rows = []
    with milder.ClaudeReader(paths.v2_raw, model=CLAUDE.model) as reader:
        for item in cells:
            cell = item.cell
            session = feed_session.run_feed_session(
                reader, cell.spec, model=CLAUDE.model, rotation=cell.rotation,
                replicate=cell.replicate,
            )
            rows.append(ctb.Row(feed_index=cell.feed_index, target_name=cell.target_name,
                                version=cell.version, rotation=cell.rotation,
                                pair_key=cell.pair_key, session=session,
                                replicate=cell.replicate))
    paths.v2_results.write_text(json.dumps({
        "reading": {"book_means": milder.book_means(rows, milder.IDENTITY_VERSIONS)},
        "rows": [{"feed_index": row.feed_index, "version": row.version,
                  "session": asdict(row.session)} for row in rows],
    }), encoding="utf-8")
    return cells


def test_the_licensed_claude_arm_runs_end_to_end_through_elicits_own_transport(
    tmp_path, monkeypatch
) -> None:
    scripted = ScriptedClaude(subprocess.run)
    paths, planned, reg, verifier, pinner = _claude_harness(tmp_path, monkeypatch, scripted)
    cells = _v2_like(paths, planned)
    v2_bytes = paths.v2_raw.read_bytes()
    identity = milder.request_identity(CLAUDE, planned, paths)
    assert identity is not None and identity["passed"] is True
    assert identity["replayed_complete"] == identity["cells"] == len(cells) == 20
    assert identity["max_abs_book_mean_diff"] == 0.0
    assert paths.v2_raw.read_bytes() == v2_bytes  # read, never written
    reg["request_identity"] = identity
    before = scripted.arm_calls
    scripted.updater.clear()  # the v2-shaped cache above was built before any run
    ledger = milder.run(CLAUDE, paths=paths, verifier=verifier, pinner=pinner, workers=2,
                        log=lambda _: None)
    assert ledger["complete"] and ledger["sessions_completed"] == len(planned) == 30
    assert scripted.updater == {"1"}  # every call inherited the auto-updater setting
    assert scripted.probe_dirs == [
        {"claude_md": True, "git": False, "git_marker": False},
        {"claude_md": False, "git": True, "git_marker": True},
    ]
    assert {name: probe["passed"] for name, probe in ledger["probes"].items()} == {
        "claude_md": True, "git_status": True}
    assert ledger["binary_sha256_at_end"] == reg["reader"]["binary_sha256"]
    started = milder.read_ledgers(paths.ledger(CLAUDE))[0]
    assert started["binary_pinned"] == str(
        paths.pin_dir(CLAUDE, reg["reader"]["binary_sha256"]) / Path(reg["reader"]["binary"]).name
    )
    records = [json.loads(line)
               for line in paths.raw(CLAUDE).read_text(encoding="utf-8").splitlines()]
    assert len(records) == scripted.arm_calls - before == len(planned) * 8  # eight reads each
    assert records[0]["usage"] == {"input": 120, "output": 6, "cache_read": 40,
                                   "cache_write": 0, "equivalent_usd": 0.0021}
    assert ledger["used_cumulative"]["calls"] == len(records) + 2  # two probes
    assert ledger["used_cumulative"]["usd"] == pytest.approx(0.0021 * (len(records) + 2))
    assert ledger["used_cumulative"]["tokens"] == 166 * (len(records) + 2)
    result = milder.analyse(CLAUDE, paths=paths, verifier=verifier)
    read = result["reading"]
    assert read["preconditions"][0]["name"] == "request_identity"
    assert [p["verdict"] for p in read["preconditions"]] == ["PASS"] * 5
    assert read["decision"] == "MOVES_WITH_ORDER"
    assert read["licence"] == milder.LICENCE["MOVES_WITH_ORDER"]
    drift = result["reader_identity"]["drift"]
    assert drift["decides"] == "nothing"
    assert drift["this_minus_v2"]["intact"]["point"] == 0.0  # the scripted reader is fixed
    assert drift["identical_sequences"] == {"intact": "10 of 10", "sham": "10 of 10"}
    # A missing v2 record is a failed identity check, and prepare would refuse on it.
    lines = paths.v2_raw.read_text(encoding="utf-8").splitlines()
    paths.v2_raw.write_text("\n".join(lines[1:]) + "\n", encoding="utf-8")
    broken = milder.request_identity(CLAUDE, planned, paths)
    assert broken is not None and broken["passed"] is False and broken["missing"]


def test_a_claude_usage_limit_trips_the_circuit_on_elicits_own_failure_reasons(
    tmp_path, monkeypatch
) -> None:
    scripted = ScriptedClaude(subprocess.run, fail_after=60)
    paths, planned, _reg, verifier, pinner = _claude_harness(tmp_path, monkeypatch, scripted)
    first = milder.run(CLAUDE, paths=paths, verifier=verifier, pinner=pinner, workers=1,
                       log=lambda _: None)
    assert first["stop"] == "transport_circuit" and not first["complete"]
    assert first["failure_reasons"] == {
        "cli_error:rc=1:You've hit your usage limit · resets 5pm": milder.TRANSPORT_CIRCUIT}
    assert milder.cached_failures(paths.raw(CLAUDE)) == 0
    scripted.fail_after = None
    second = milder.run(CLAUDE, paths=paths, verifier=verifier, pinner=pinner, workers=1,
                        log=lambda _: None)
    assert second["complete"] and second["invocation"] == 2
    assert scripted.arm_calls == 60 + milder.TRANSPORT_CIRCUIT + (len(planned) * 8 - 60)
    assert second["used_cumulative"]["calls"] == 4 + len(planned) * 8 + milder.TRANSPORT_CIRCUIT


def test_a_pinned_binary_that_changes_mid_run_halts_before_the_next_session(
    tmp_path, monkeypatch
) -> None:
    held: dict[str, Path] = {}

    def update_in_place(calls: int) -> None:
        if calls == 20:  # inside the third session
            held["pinned"].write_bytes(held["pinned"].read_bytes() + b"patched\n")

    scripted = ScriptedClaude(subprocess.run, on_arm_call=update_in_place)
    paths, _planned, reg, verifier, pinner = _claude_harness(tmp_path, monkeypatch, scripted)

    def pin_and_hold(profile, paths_, reg_):
        held["pinned"] = pinner(profile, paths_, reg_)
        return held["pinned"]

    ledger = milder.run(CLAUDE, paths=paths, verifier=verifier, pinner=pin_and_hold, workers=1,
                        log=lambda _: None)
    assert ledger["stop"] == "halt:binary_changed" and not ledger["complete"]
    assert ledger["sessions_completed"] == 3  # the session in flight finished; none started
    assert ledger["binary_sha256_at_end"] != reg["reader"]["binary_sha256"]


# ------------------------------------------------ since review: the ledger survives a kill


def _killed(tmp_path, monkeypatch) -> tuple[Any, list[Any], Any, Any, FakeProvider]:
    """A whole run whose process was killed after session 30's checkpoint: no finished line,
    ten sessions' answers only in the cache, and a torn last append."""
    provider = FakeProvider(_order_reader)
    paths, planned, verifier, factory = _harness(tmp_path, monkeypatch, provider)
    milder.run(CODEX, paths=paths, verifier=verifier, reader_factory=factory, probe=_probe_ok,
               workers=1, log=lambda _: None)
    ledger = paths.ledger(CODEX)
    lines = [line for line in ledger.read_text(encoding="utf-8").splitlines()
             if json.loads(line)["event"] != "finished"]
    sessions = [i for i, line in enumerate(lines) if json.loads(line)["event"] == "session"]
    lines = lines[: sessions[29] + 1]
    ledger.write_text("\n".join(lines) + "\n" + lines[-1][:40], encoding="utf-8")
    return paths, planned, verifier, factory, provider


def test_a_killed_invocation_resumes_from_the_larger_of_ledger_and_cache(
    tmp_path, monkeypatch
) -> None:
    paths, planned, verifier, factory, provider = _killed(tmp_path, monkeypatch)
    ledgers = milder.read_ledgers(paths.ledger(CODEX))
    assert not milder.finished(ledgers)
    assert ledgers[-1]["used_cumulative"]["calls"] == 1 + 30 * 8
    assert milder.prior_usage(ledgers, paths.raw(CODEX))["calls"] == len(planned) * 8
    with pytest.raises(RuntimeError, match="no finished line"):
        milder.analyse(CODEX, paths=paths, verifier=verifier, reader_factory=factory)
    paths.lock_holder.parent.mkdir(parents=True)
    paths.lock_holder.write_text(f"{milder.LOCK_PREFIX} milder-v4, 12:00\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="names this arm"):
        milder.analyse(CODEX, paths=paths, verifier=verifier, reader_factory=factory)
    paths.lock_holder.unlink()
    calls = provider.calls
    resumed = milder.run(CODEX, paths=paths, verifier=verifier, reader_factory=factory,
                         probe=_probe_ok, workers=1, log=lambda _: None)
    assert resumed["complete"] and resumed["invocation"] == 2
    assert provider.calls == calls  # everything the killed process bought replayed free
    # The cache's total, which the killed ledger undercounted, plus this invocation's probe.
    assert resumed["used_cumulative"]["calls"] == len(planned) * 8 + 1
    result = milder.analyse(CODEX, paths=paths, verifier=verifier, reader_factory=factory)
    assert result["transport"]["stops"] == ["interrupted", None]
    assert result["transport"]["coverage"] == "complete"


def test_a_killed_invocation_the_operator_will_not_resume_is_closed_then_read(
    tmp_path, monkeypatch
) -> None:
    paths, planned, verifier, factory, _ = _killed(tmp_path, monkeypatch)
    paths.lock_holder.parent.mkdir(parents=True)
    paths.lock_holder.write_text(f"{milder.LOCK_PREFIX} milder-v4\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="names this arm"):
        milder.close(CODEX, paths=paths)
    paths.lock_holder.write_text("another-session: a suite\n", encoding="utf-8")
    line = milder.close(CODEX, paths=paths)
    assert line["stop"] == "closed_after_interruption"
    assert line["used_cumulative"]["calls"] == len(planned) * 8
    with pytest.raises(RuntimeError, match="nothing to close"):
        milder.close(CODEX, paths=paths)
    result = milder.analyse(CODEX, paths=paths, verifier=verifier, reader_factory=factory)
    assert result["transport"]["stops"] == ["closed_after_interruption"]
    assert result["transport"]["sessions_dispatched"] == len(planned)


def test_a_worker_that_raises_drains_the_run_so_nothing_is_bought_behind_it(
    tmp_path, monkeypatch
) -> None:
    class CrashesOnce(FakeProvider):
        def complete(self, request):
            if self.calls == 20:
                self.calls += 1
                raise RuntimeError("boom")
            return super().complete(request)

    provider = CrashesOnce(_order_reader)
    paths, planned, verifier, factory = _harness(tmp_path, monkeypatch, provider)
    with pytest.raises(RuntimeError, match="boom"):
        milder.run(CODEX, paths=paths, verifier=verifier, reader_factory=factory,
                   probe=_probe_ok, workers=2, log=lambda _: None)
    lines = milder.read_ledgers(paths.ledger(CODEX))
    assert lines[-1]["event"] == "finished" and lines[-1]["stop"] == "error:RuntimeError"
    assert lines[-1]["draining"] == "error:RuntimeError"
    # One worker crashed; the other finished the session it held and admitted no other.
    assert provider.calls <= 21 + feed_core.MAX_STEPS
    assert sum(1 for line in lines if line["event"] == "session") < len(planned)


# ----------------------------------------- since review: the scorable floor's denominator


def test_the_scorable_floor_counts_dispatched_sessions_as_v2_did(tmp_path, monkeypatch) -> None:
    provider = FakeProvider(_order_reader, fail_after=44 * 8)
    paths, planned, verifier, factory = _harness(tmp_path, monkeypatch, provider, books=16)
    first = milder.run(CODEX, paths=paths, verifier=verifier, reader_factory=factory,
                       probe=_probe_ok, workers=1, log=lambda _: None)
    assert first["stop"] == "transport_circuit" and first["sessions_completed"] == 47
    result = milder.analyse(CODEX, paths=paths, verifier=verifier, reader_factory=factory)
    transport = result["transport"]
    assert transport["coverage"] == "partial" and transport["missing_is_tail_block"] is True
    assert transport["sessions_dispatched"] == 47
    assert transport["sessions_never_dispatched"] == len(planned) - 47 == 17
    assert transport["sessions_failed_in_flight"] == milder.TRANSPORT_CIRCUIT
    read = result["reading"]
    assert {v: block["sessions"] for v, block in read["per_version"].items()} == {
        "intact": 12, "partial": 12, "sham": 12, "shuffled": 11}
    floor = next(p for p in read["preconditions"] if p["name"] == "scorable_floor")
    assert floor["verdict"] == "PASS" and read["decision"] != "UNREADABLE"
    # Over every planned session the floor would read a stopped transport as an unscorable
    # reader: 11 of 16 intact sessions is under 0.75, where v2's own rule saw 11 of 12.
    with factory(CODEX, paths, None, replay_only=True) as reader:
        every, _status, _used = milder.replay(CODEX, planned, reader)
    everything = milder.reading(every, CODEX)
    assert next(p for p in everything["preconditions"]
                if p["name"] == "scorable_floor")["verdict"] == "FAIL"


# ------------------------------------------------------ since review: the reader fence


def test_the_codex_profile_is_registered_only_with_approval_and_before_any_claude_cell(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(milder, "sources", lambda profile, paths: [paths.arm_dir / "PREREG.md"])
    paths = _scratch_paths(tmp_path)
    paths.arm_dir.mkdir()
    (paths.arm_dir / "PREREG.md").write_text("registration\n", encoding="utf-8")
    kwargs = {
        "texts_loader": lambda d: (_books(4), {}),
        "binary_reader": lambda profile, codex: {"binary": "codex.exe", "binary_sha256": "c" * 64,
                                                 "binary_version": "codex-cli test"},
    }
    with pytest.raises(RuntimeError, match=r"codex-approval\.json is missing"):
        milder.prepare(CODEX, paths=paths, **kwargs)
    paths.codex_approval.write_text('{"approved": "by the operator"}\n', encoding="utf-8")
    with pytest.raises(RuntimeError, match=r"ATTAINABILITY-codex\.md is missing"):
        milder.prepare(CODEX, paths=paths, **kwargs)
    paths.codex_attainability.write_text("# Codex attainability\n", encoding="utf-8")
    # A Claude cell bought first holds the question: Codex would be a second look at it.
    paths.raw(CLAUDE).write_text(
        json.dumps({"feed": "ctbm4-00-intact-r0", "key": "k:0", "stop_reason": "end_turn"})
        + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="held by that reader"):
        milder.prepare(CODEX, paths=paths, **kwargs)
    paths.raw(CLAUDE).unlink()
    registration = milder.prepare(CODEX, paths=paths, **kwargs)
    assert registration["request_identity"] is None
    claim = json.loads(paths.claim(CODEX).read_text(encoding="utf-8"))
    assert claim["status"] == "registered" and claim["claim_id"].endswith(".codex")


def test_a_claude_run_is_refused_once_the_codex_arm_has_bought(tmp_path, monkeypatch) -> None:
    paths, _planned, verifier, factory = _harness(tmp_path, monkeypatch,
                                                  FakeProvider(_order_reader))
    milder.run(CODEX, paths=paths, verifier=verifier, reader_factory=factory, probe=_probe_ok,
               workers=1, log=lambda _: None)

    def probe(profile, reg):
        raise AssertionError("a Claude probe was bought over a question Codex holds")

    with pytest.raises(RuntimeError, match="held by that reader"):
        milder.run(CLAUDE, paths=paths, verifier=lambda profile, **kwargs: ({}, []),
                   probe=probe)


# ---------------------------------------------- since review: the Codex reader's own acts


class ActingProvider:
    """A Codex adapter whose turn ends in a `MALFORMED_RESPONSE` with the given message."""

    def __init__(self, message: str) -> None:
        self.message = message
        self.calls = 0
        self.last_attempt: dict[str, Any] = {}

    def complete(self, request):
        self.calls += 1
        events = [
            {"type": "turn.started"},
            {"type": "item.completed", "item": {"type": "command_execution"}},
            {"type": "turn.completed", "usage": {"input_tokens": 70, "cached_input_tokens": 20,
                                                 "output_tokens": 9,
                                                 "reasoning_output_tokens": 2}},
        ]
        self.last_attempt = {"stdout": "\n".join(json.dumps(event) for event in events)}
        raise ProviderError(f"Codex request or response was unusable: {self.message}",
                            kind=ProviderFailureKind.MALFORMED_RESPONSE)


def test_a_codex_readers_own_act_is_cached_as_an_answer_and_a_garbled_stream_is_not(tmp_path):
    kwargs = {"schema": feed_core.ACTION_SCHEMA, "max_tokens": 48, "tag": {"feed": "x"}}
    acting = ActingProvider("Codex attempted an unpermitted activity: command_execution")
    with _codex_reader(tmp_path / "raw.jsonl", acting) as reader:
        record = reader.ask_raw(SYSTEM, TURNS, **kwargs)
    assert record["stop_reason"].startswith("reader_unusable:codex:malformed_response:")
    assert not elicit._is_transport_failure(record["stop_reason"])
    assert record["usage"] == {"input": 50, "output": 7, "cache_read": 20, "cache_write": 0,
                               "reasoning": 2, "equivalent_usd": None}
    with _codex_reader(tmp_path / "raw.jsonl", acting) as again:
        assert again.ask_raw(SYSTEM, TURNS, **kwargs)["stop_reason"] == record["stop_reason"]
    assert acting.calls == 1  # a resume replays the reader's act; it never re-rolls it
    garbled = ActingProvider("Codex did not report exactly one successful turn")
    with _codex_reader(tmp_path / "other.jsonl", garbled) as reader:
        failure = reader.ask_raw(SYSTEM, TURNS, **kwargs)
    assert elicit._is_transport_failure(failure["stop_reason"])
    assert not (tmp_path / "other.jsonl").exists()  # §235: a garbled stream is not an answer


def test_each_worker_thread_reads_its_own_codex_attempt() -> None:
    made: list[Any] = []

    def factory() -> Any:
        provider = type("Adapter", (), {})()
        provider.last_attempt = {"thread": len(made)}
        made.append(provider)
        return provider

    shared = milder.PerThreadProvider(factory)
    seen: list[int] = []
    threads = [threading.Thread(target=lambda: seen.append(shared.last_attempt["thread"]))
               for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(seen) == [0, 1, 2] and len(made) == 3
