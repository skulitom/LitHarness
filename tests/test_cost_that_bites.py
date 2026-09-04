"""The cost-that-bites arm's frozen definitions, checked without a call.

What this file pins: the shuffle is a word-preserving reordering that is deterministic in the
text and never the identity; the sham moves no word; the plan seats three versions of every
target across every rotation and counts its own sessions; the paired reading is assembled from
complete scorable triples only; the decision table reads each registered outcome from
constructed intervals; the runner stops between sessions at the ceiling and reports it; and a
reader that never moves fails `fp5` and reads UNREADABLE before any interval is looked at.
What it does not establish: anything about any model's allocation — no call happens here.
"""

from __future__ import annotations

import json

import pytest

ctb = pytest.importorskip(
    "cost_that_bites",
    reason="research module; imported by path, skipped where research/ is unavailable",
)
feed_core = pytest.importorskip("feed_core")
ablate = pytest.importorskip("ablate")


def _member(marker: str) -> str:
    """A synthetic full-length member, the module's own shape (capitalised sentences)."""
    return ctb._member_text(marker)


def test_a_sham_or_shuffle_that_changes_nothing_is_a_named_fault() -> None:
    # Lowercase tokens with no sentence end give the whitespace sham nothing to re-flow.
    inert = "\n\n".join(
        " ".join(f"p{paragraph}w{word}" for word in range(feed_core.CHUNK_WORDS + 5))
        for paragraph in range(feed_core.MIN_CHUNKS_FEED + 2)
    )
    pool = [("inert", inert)] + [(f"book-{index}", _member(f"b{index}")) for index in range(3)]
    broken = ctb.faults(ctb.plan(pool, feeds=1))
    assert broken == {"ctb-00-sham": "the sham target is byte-identical to the intact target"}


# ------------------------------------------------------------------ the target's versions


def test_the_shuffle_reorders_every_paragraph_and_keeps_every_word() -> None:
    text = _member("a")
    shuffled = ctb.book_shuffle(text)
    assert sorted(ablate.paragraphs(shuffled)) == sorted(ablate.paragraphs(text))
    assert ablate.paragraphs(shuffled) != ablate.paragraphs(text)
    assert sorted(shuffled.split()) == sorted(text.split())


def _order(text: str) -> list[int]:
    """The permutation the shuffle applied to `text`, as original paragraph indices."""
    original = ablate.paragraphs(text)
    return [original.index(part) for part in ablate.paragraphs(ctb.book_shuffle(text))]


def test_the_shuffle_is_deterministic_in_the_text_and_differs_between_books() -> None:
    assert ctb.book_shuffle(_member("a")) == ctb.book_shuffle(_member("a"))
    assert _order(_member("a")) != _order(_member("b"))


def test_a_two_paragraph_text_is_never_returned_in_its_own_order() -> None:
    two = "first paragraph of words.\n\nsecond paragraph of words."
    assert ctb.book_shuffle(two) == "second paragraph of words.\n\nfirst paragraph of words."
    with pytest.raises(ValueError, match="two paragraphs"):
        ctb.book_shuffle("one paragraph only")


def test_the_sham_moves_no_word_and_the_versions_are_three_distinct_texts() -> None:
    text = _member("s")
    versions = ctb.versions_of(text)
    assert list(versions) == ["intact", "shuffled", "sham"]
    assert versions["intact"] == text
    assert versions["sham"].split() == text.split()
    assert len({versions[name] for name in versions}) == 3


# ---------------------------------------------------------------------------- the plan


def test_the_plan_seats_three_versions_of_every_target_across_every_rotation() -> None:
    pool = [(f"book-{index}", _member(f"b{index}")) for index in range(5)]
    cells = ctb.plan(pool)
    assert ctb.planned_counts(cells) == {
        "feeds": 5,
        "sessions": 5 * 3 * feed_core.FEED_SIZE,
        "max_calls": 5 * 3 * feed_core.FEED_SIZE * feed_core.MAX_STEPS,
    }
    assert ctb.faults(cells) == {}
    first = [cell for cell in cells if cell.feed_index == 0]
    assert {cell.version for cell in first} == set(ctb.VERSIONS)
    assert {cell.rotation for cell in first} == set(range(feed_core.FEED_SIZE))
    # The three versions of one (feed, rotation) share their pair key and their competitors.
    keyed = {(cell.version, cell.rotation): cell for cell in first}
    for rotation in range(feed_core.FEED_SIZE):
        intact, shuffled, sham = (keyed[(v, rotation)] for v in ctb.VERSIONS)
        assert intact.pair_key == shuffled.pair_key == sham.pair_key
        assert intact.spec.others == shuffled.spec.others == sham.spec.others
    # The intact target is the pool's own book against its next three neighbours.
    assert keyed[("intact", 0)].spec.target == pool[0][1]
    assert keyed[("intact", 0)].spec.others == tuple(text for _, text in pool[1:4])


def test_a_capped_plan_is_the_first_feeds_only() -> None:
    pool = [(f"book-{index}", _member(f"b{index}")) for index in range(6)]
    cells = ctb.plan(pool, feeds=2)
    assert {cell.feed_index for cell in cells} == {0, 1}
    assert len(cells) == 2 * 3 * feed_core.FEED_SIZE


def test_a_pool_smaller_than_a_feed_is_refused() -> None:
    with pytest.raises(ValueError, match="feed of"):
        ctb.plan([("only", _member("o"))])


def test_the_registration_is_content_addressed_and_names_the_instrument() -> None:
    assert ctb.registration_digest() == ctb.registration_digest()
    assert ctb.PRE_REGISTRATION["instrument"] == feed_core.FCR_VERSION
    assert ctb.PRE_REGISTRATION["instrument_registration_digest"] == feed_core.registration_digest()
    assert ctb.PRE_REGISTRATION["alpha"] == feed_core.CONTROL_ALPHA


# ------------------------------------------------------------------- the paired reading


def _session(version: str, rotation: int, actions: tuple[tuple[str, str], ...], **kw: object):
    return feed_core.FeedSession(
        feed_id=f"ctb-00-{version}",
        arm=version,
        model="test",
        rotation=rotation,
        replicate=0,
        dose=0.0,
        actions=actions,
        **kw,
    )


def _row(
    version: str, rotation: int, actions: tuple[tuple[str, str], ...], **kw: object
) -> ctb.Row:
    session = _session(version, rotation, actions, **kw)
    return ctb.Row(
        feed_index=0,
        target_name="book-0",
        version=version,
        rotation=rotation,
        pair_key=f"00:{rotation}",
        session=session,
    )


def test_a_triple_with_an_unscorable_member_is_left_out_of_the_pairs() -> None:
    reads = tuple(("read", "A") for _ in range(8))
    rows = [
        _row("intact", 0, reads),
        _row("shuffled", 0, reads),
        _row("sham", 0, reads),
        _row("intact", 1, reads),
        _row("shuffled", 1, reads[:3], unanswered=1, exit_note="invalid_action"),
        _row("sham", 1, reads),
    ]
    complete = ctb.triples(rows)
    assert list(complete) == ["00:0"]
    pairs = ctb.paired(complete, lambda s: s.target_read_share)
    assert pairs["intact_minus_shuffled"] == [("00", 0.0)]


def test_the_paired_differences_are_intact_minus_shuffled_and_sham_minus_shuffled() -> None:
    target_reads = tuple(("read", "A") for _ in range(8))
    away = tuple(("read", "B") for _ in range(8))
    half = tuple(("read", "A") if i % 2 == 0 else ("read", "B") for i in range(8))
    rows = [_row("intact", 0, target_reads), _row("shuffled", 0, away), _row("sham", 0, half)]
    pairs = ctb.paired(ctb.triples(rows), lambda s: s.target_read_share)
    assert pairs["intact_minus_shuffled"] == [("00", 1.0)]
    assert pairs["intact_minus_sham"] == [("00", 0.5)]
    assert pairs["sham_minus_shuffled"] == [("00", 0.5)]


def test_an_interval_needs_two_clusters_and_names_its_direction() -> None:
    assert ctb.interval_block([("00", 0.5)])["interval"] is None
    block = ctb.interval_block([(f"{i:02d}", 0.5) for i in range(6)])
    assert block["clusters"] == 6
    assert block["above_zero"] is True and block["below_zero"] is False
    below = ctb.interval_block([(f"{i:02d}", -0.5) for i in range(6)])
    assert below["below_zero"] is True and below["above_zero"] is False


@pytest.mark.parametrize(
    ("shuffle_up", "shuffle_down", "order_up", "expected"),
    [
        (True, False, True, "MOVES_WITH_ORDER"),
        (True, False, False, "MOVES_WITH_EDITEDNESS"),
        (False, False, False, "NULL"),
        (False, False, True, "NULL"),
        (False, True, False, "INVERTED"),
    ],
)
def test_the_decision_table_reads_each_registered_outcome(
    shuffle_up: bool, shuffle_down: bool, order_up: bool, expected: str
) -> None:
    decision = ctb.decide(
        fp5_verdict="PASS",
        readable_versions=True,
        complete_clusters=20,
        shuffle={"above_zero": shuffle_up, "below_zero": shuffle_down},
        order={"above_zero": order_up, "below_zero": False},
    )
    assert decision == expected


def test_the_preconditions_read_unreadable_before_any_interval() -> None:
    moving = {"above_zero": True, "below_zero": False}
    assert (
        ctb.decide(
            fp5_verdict="FAIL", readable_versions=True, complete_clusters=20,
            shuffle=moving, order=moving,
        )
        == "UNREADABLE"
    )
    assert (
        ctb.decide(
            fp5_verdict="PASS", readable_versions=False, complete_clusters=20,
            shuffle=moving, order=moving,
        )
        == "UNREADABLE"
    )
    assert (
        ctb.decide(
            fp5_verdict="PASS", readable_versions=True, complete_clusters=1,
            shuffle=moving, order=moving,
        )
        == "UNREADABLE"
    )


# ---------------------------------------------------------------------------- the runner


def _target_slot(tag: dict) -> str:
    return feed_core.SLOTS[int(tag["rotation"]) % feed_core.FEED_SIZE]


def test_the_runner_stops_between_sessions_at_the_ceiling_and_says_so() -> None:
    pool = [(f"book-{index}", _member(f"b{index}")) for index in range(4)]
    cells = ctb.plan(pool, feeds=1)
    elicitor = ctb._ScriptedElicitor(
        lambda tag: json.dumps({"action": "read", "book": _target_slot(tag)}), usd_per_call=0.1
    )
    rows, ledger = ctb.run_cells(
        elicitor, cells, model="test", ceiling_usd=1.0, workers=1, log=lambda _: None
    )
    assert ledger["stopped_at_ceiling"] is True
    assert 0 < len(rows) < len(cells)
    assert ledger["sessions_run"] == len(rows)
    assert ledger["sessions_planned"] == len(cells)


def test_a_run_under_the_ceiling_buys_every_cell_and_reads_a_scripted_mover() -> None:
    pool = [(f"book-{index}", _member(f"b{index}")) for index in range(4)]
    cells = ctb.plan(pool)
    elicitor = ctb._ScriptedElicitor(ctb._reads_target_by_version, usd_per_call=0.001)
    rows, ledger = ctb.run_cells(
        elicitor, cells, model="test", ceiling_usd=10.0, workers=3, log=lambda _: None
    )
    assert len(rows) == len(cells) and not ledger["stopped_at_ceiling"]
    read = ctb.reading(rows)
    assert read["decision"] == "MOVES_WITH_ORDER"
    assert read["complete_triples"] == 4 * feed_core.FEED_SIZE
    assert read["per_version"]["shuffled"]["mean_target_read_share"] == 0.0
    assert read["per_version"]["intact"]["mean_target_read_share"] == 1.0


def test_a_reader_that_never_moves_fails_fp5_and_reads_unreadable() -> None:
    pool = [(f"book-{index}", _member(f"b{index}")) for index in range(4)]
    cells = ctb.plan(pool)
    elicitor = ctb._ScriptedElicitor(
        lambda tag: json.dumps({"action": "read", "book": "A"}), usd_per_call=0.001
    )
    rows, _ = ctb.run_cells(
        elicitor, cells, model="test", ceiling_usd=10.0, workers=2, log=lambda _: None
    )
    read = ctb.reading(rows)
    assert read["fp5"]["verdict"] == "FAIL"
    assert read["decision"] == "UNREADABLE"


def test_the_selftest_passes() -> None:
    assert ctb.selftest() == 0


# ------------------------------------------------------------ v2: the book is the unit


def test_v1s_registration_digest_is_untouched_by_v2_existing() -> None:
    """The digest stamped on v1's committed result files, so its numbers stay reproducible."""
    assert ctb.registration_digest() == "2659023acf6197e3"
    assert ctb.registration_digest_v2() != ctb.registration_digest()
    assert ctb.PRE_REGISTRATION_V2["amends"] == ctb.VERSION


def test_v1s_shuffle_is_byte_identical_under_the_new_seed_parameter() -> None:
    text = _member("s")
    assert ctb.book_shuffle(text) == ctb.book_shuffle(text, index=0)


def test_three_seeds_give_one_book_three_different_shuffles() -> None:
    text = _member("s")
    versions = ctb.versions_v2(text)
    assert list(versions) == ["intact", "shuffled", "sham"]
    shuffles = versions["shuffled"]
    assert len(shuffles) == ctb.REPLICATES_V2 == len(set(shuffles))
    for shuffled in shuffles:
        assert shuffled != text
        assert sorted(shuffled.split()) == sorted(text.split())
    # intact and sham repeat one text; their replicates differ only by the sample index.
    assert len(set(versions["intact"])) == 1
    assert len(set(versions["sham"])) == 1


def test_the_v2_plan_seats_every_book_in_slot_a_at_three_replicates() -> None:
    pool = [(f"book-{index}", _member(f"b{index}")) for index in range(5)]
    cells = ctb.plan_v2(pool)
    assert len(cells) == 5 * 3 * ctb.REPLICATES_V2
    assert {cell.rotation for cell in cells} == {ctb.TARGET_ROTATION_V2}
    assert {cell.replicate for cell in cells} == set(range(ctb.REPLICATES_V2))
    assert ctb.faults(cells) == {}
    assert {cell.book_key for cell in cells} == {f"{i:02d}" for i in range(5)}


def _book_rows(book: str, shares: dict[str, list[float]]) -> list[ctb.Row]:
    """Rows whose sessions realise the given per-version target shares (eight reads each)."""
    rows: list[ctb.Row] = []
    for version, values in shares.items():
        for replicate, share in enumerate(values):
            hits = round(share * 8)
            actions = tuple(
                ("read", "A" if index < hits else "B") for index in range(8)
            )
            session = feed_core.FeedSession(
                feed_id=f"ctb2-{book}-{version}-r{replicate}",
                arm=version,
                model="test",
                rotation=0,
                replicate=replicate,
                dose=0.0,
                actions=actions,
            )
            rows.append(
                ctb.Row(
                    feed_index=int(book),
                    target_name=f"book-{book}",
                    version=version,
                    rotation=0,
                    pair_key=f"{book}:0",
                    session=session,
                    replicate=replicate,
                )
            )
    return rows


def test_a_book_is_one_observation_averaged_over_its_replicates() -> None:
    rows = _book_rows("00", {"intact": [1.0, 0.75, 0.875], "shuffled": [0.25, 0.25, 0.25],
                             "sham": [0.875, 0.875, 0.875]})
    means = ctb.by_book(rows)
    assert set(means) == {"00"}
    assert means["00"]["intact"] == pytest.approx(0.875)
    assert means["00"]["shuffled"] == pytest.approx(0.25)
    pairs = ctb.paired_v2(means)
    assert pairs["intact_minus_shuffled"] == [("00", pytest.approx(0.625))]
    assert pairs["sham_minus_shuffled"] == [("00", pytest.approx(0.625))]


def test_a_book_missing_a_version_is_dropped_whole() -> None:
    rows = _book_rows("00", {"intact": [1.0], "shuffled": [0.25]})
    assert ctb.by_book(rows) == {}


def test_the_capacity_precondition_fails_when_the_reader_leaves_slot_a() -> None:
    elsewhere = [
        row.session
        for row in _book_rows("00", {"intact": [0.0], "shuffled": [0.0], "sham": [0.0]})
    ]
    verdict = ctb.capacity_v2(elsewhere)
    assert verdict["verdict"] == "FAIL"
    assert verdict["shares"]["A"] == 0.0
    assert "premise" in verdict["why"]
    attending = [
        row.session
        for row in _book_rows("00", {"intact": [1.0], "shuffled": [0.75], "sham": [1.0]})
    ]
    assert ctb.capacity_v2(attending)["verdict"] == "PASS"


def test_v2_reads_unreadable_below_the_book_floor_however_the_intervals_look() -> None:
    rows: list[ctb.Row] = []
    for book in range(ctb.MIN_BOOKS_V2 - 1):
        rows += _book_rows(
            f"{book:02d}",
            {"intact": [1.0, 1.0, 1.0], "shuffled": [0.25, 0.25, 0.25], "sham": [1.0, 1.0, 1.0]},
        )
    read = ctb.reading_v2(rows)
    assert read["books_complete"] == ctb.MIN_BOOKS_V2 - 1
    assert read["decision"] == "UNREADABLE"


def test_v2_reads_moves_with_order_when_every_precondition_holds() -> None:
    rows: list[ctb.Row] = []
    for book in range(ctb.MIN_BOOKS_V2 + 2):
        # A little variation per book so fp5 sees movement across sessions.
        high = 1.0 if book % 2 else 0.875
        rows += _book_rows(
            f"{book:02d}",
            {
                "intact": [high, high, 0.75],
                "shuffled": [0.25, 0.375, 0.25],
                "sham": [high, 0.75, high],
            },
        )
    read = ctb.reading_v2(rows)
    assert read["capacity"]["verdict"] == "PASS"
    assert read["fp5"]["verdict"] == "PASS"
    assert read["decision"] == "MOVES_WITH_ORDER"
    assert read["declared_target_shift"] == 0.1875
    assert read["underpowered_at"] == 0.125
    # The seed spread says whether the number is about disorder or about one permutation.
    assert read["shuffle_seed_spread"]
def test_the_ceiling_can_be_priced_while_the_pool_is_still_recording() -> None:
    """§227: `spend` is read by one worker while its siblings write, which is what
    `run_cells` does between cells, and an unguarded dict raised `RuntimeError: dictionary
    changed size during iteration` out of `future.result()` and stopped the run.

    **The reader iterates a cache that is already large**, because that is what makes the
    window wide enough to land on every run rather than on a lucky one: a first draft of this
    test summed a dict of a few dozen records and passed against the unfixed code, which
    would have shipped a guard that cannot fail. It is checked the other way — with the lock
    removed this fails, with it in place it does not.
    """
    import threading

    scripted = ctb._ScriptedElicitor(lambda tag: "x", usd_per_call=0.01)
    for seed in range(4000):
        scripted.ask_raw(
            "", [], schema=None, max_tokens=1, tag={"feed": f"seed{seed}", "rotation": 0},
            sample=seed,
        )

    done = threading.Event()
    failures: list[BaseException] = []

    def write(worker: int) -> None:
        try:
            for call in range(1500):
                scripted.ask_raw(
                    "", [], schema=None, max_tokens=1,
                    tag={"feed": f"w{worker}-{call}", "rotation": worker}, sample=call,
                )
        except BaseException as error:
            failures.append(error)

    def read() -> None:
        try:
            while not done.is_set():
                scripted.spend()
        except BaseException as error:
            failures.append(error)

    reader = threading.Thread(target=read)
    writers = [threading.Thread(target=write, args=(worker,)) for worker in range(3)]
    reader.start()
    for thread in writers:
        thread.start()
    for thread in writers:
        thread.join(timeout=60)
    done.set()
    reader.join(timeout=60)

    assert not failures, f"the pool raced: {failures[0]!r}"
    assert scripted.api_calls == 4000 + 3 * 1500
    assert scripted.spend()["equivalent_usd"] == round(scripted.api_calls * 0.01, 6)
