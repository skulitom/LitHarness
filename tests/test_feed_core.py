"""The feed continuation reader's frozen core, checked without calls.

What this file pins: the reader-facing bytes (a reworded prompt is a different instrument with
no evidence — T0's A4), the agreement between the prose costs and the registered costs, the
worst-case chunk arithmetic that lets the fitness shelf carry the feed, the deterministic skim
extract, and the session record's derived quantities on hand-built action sequences whose
correct answers are stated before anything runs. What it does not establish: anything about any
reader model — no session here involves a call, and the controls' arithmetic lives with
`feed_controls`.
"""

from __future__ import annotations

import pytest

feed_core = pytest.importorskip(
    "feed_core",
    reason="research module; imported by path, skipped where research/ is unavailable",
)


# ------------------------------------------------------------------------- the frozen bytes


def test_the_reader_prompt_is_byte_frozen() -> None:
    """Forced spending, a priced skim, no evaluation framing — pinned literally."""
    assert feed_core.SYSTEM == (
        "You are reading for pleasure. You are partway through four books and have a fixed "
        "amount of reading time left, measured in minutes.\n"
        "Each time you are asked, choose one action: read the next section of one book, which "
        "costs 3 minutes, or skim a short summary of the next section of one book, which "
        "costs 1 minute. Skimming does not use the section up; reading always shows the full "
        "section.\n"
        "You must spend all your reading time; there is no option to stop.\n"
        'Answer with a single JSON object, for example {"action": "read", "book": "A"} or '
        '{"action": "skim", "book": "C"}. The books are A, B, C and D.'
    )
    assert feed_core.TURN == "{left} minute(s) of reading time left. What do you do?"


def test_the_prose_costs_agree_with_the_registered_costs() -> None:
    """The prompt states prices in words; the loop charges them in constants. They must agree."""
    assert f"costs {feed_core.READ_COST} minutes" in feed_core.SYSTEM
    assert f"costs {feed_core.SKIM_COST} minute" in feed_core.SYSTEM


def test_the_action_schema_is_closed_over_the_registered_slots() -> None:
    properties = feed_core.ACTION_SCHEMA["properties"]
    assert properties["book"]["enum"] == list(feed_core.SLOTS)
    assert properties["action"]["enum"] == ["read", "skim"]
    assert feed_core.ACTION_SCHEMA["additionalProperties"] is False


def test_the_registration_is_content_addressed() -> None:
    digest = feed_core.registration_digest()
    assert len(digest) == 16
    assert digest == feed_core.registration_digest()
    int(digest, 16)


def test_the_worst_case_budget_cannot_exhaust_a_minimal_feed_member() -> None:
    """Mid-stream entry plus every read on one slot needs exactly MIN_CHUNKS_FEED chunks.

    The registered relationship, asserted so a budget or entry-point edit that breaks the
    fitness shelf's 13-chunk fit fails here before a call is bought.
    """
    worst_case_reads = feed_core.BUDGET_UNITS // feed_core.READ_COST
    assert feed_core.MIDSTREAM_CHUNK + worst_case_reads == feed_core.MIN_CHUNKS_FEED
    assert feed_core.BUDGET_UNITS // feed_core.SKIM_COST == feed_core.MAX_STEPS


# ------------------------------------------------------------------------------ skim extract


def test_skim_extract_takes_the_first_sentence_of_each_paragraph() -> None:
    text = (
        "Ada opened the gate. The hinge complained about it.\n\n"
        "Rain arrived sideways! Nobody had asked it to.\n\n"
        "The ledger stayed shut."
    )
    assert feed_core.skim_extract(text) == (
        "Ada opened the gate. Rain arrived sideways! The ledger stayed shut."
    )


def test_skim_extract_truncates_at_the_word_cap() -> None:
    text = "one two three four five six seven eight nine ten.\n\nsecond paragraph never seen."
    out = feed_core.skim_extract(text, words=4)
    assert out == "one two three four"


def test_skim_extract_handles_a_paragraph_with_no_sentence_ending() -> None:
    fragment = " ".join(f"w{i}" for i in range(40))
    out = feed_core.skim_extract(fragment, words=60)
    assert out.split() == [f"w{i}" for i in range(feed_core._FRAGMENT_WORDS)]


def test_skim_extract_of_empty_text_is_empty() -> None:
    assert feed_core.skim_extract("") == ""


# -------------------------------------------------------------------------- feed and rotation


def _member_text(chunks: int, word: str = "steady") -> str:
    """A text of exactly `chunks` chunks: paragraphs of exactly CHUNK_WORDS words each."""
    paragraph = " ".join([word] * feed_core.CHUNK_WORDS)
    return "\n\n".join([paragraph] * chunks)


def test_a_full_length_feed_has_no_fault() -> None:
    spec = feed_core.FeedSpec(
        feed_id="f1",
        arm="intact",
        target=_member_text(feed_core.MIN_CHUNKS_FEED),
        others=tuple(_member_text(feed_core.MIN_CHUNKS_FEED, f"o{i}") for i in range(3)),
    )
    assert spec.fault() is None


def test_a_short_member_is_named_in_the_fault() -> None:
    spec = feed_core.FeedSpec(
        feed_id="f2",
        arm="intact",
        target=_member_text(feed_core.MIN_CHUNKS_FEED),
        others=(
            _member_text(feed_core.MIN_CHUNKS_FEED, "o0"),
            _member_text(feed_core.MIN_CHUNKS_FEED - 1, "o1"),
            _member_text(feed_core.MIN_CHUNKS_FEED, "o2"),
        ),
    )
    fault = spec.fault()
    assert fault is not None
    assert "other2" in fault
    assert str(feed_core.MIN_CHUNKS_FEED) in fault


def test_a_wrongly_sized_feed_is_refused_before_its_texts_are_measured() -> None:
    spec = feed_core.FeedSpec(feed_id="f3", arm="intact", target="short", others=("a", "b"))
    fault = spec.fault()
    assert fault is not None
    assert str(feed_core.FEED_SIZE) in fault


def test_rotation_moves_the_target_through_every_slot() -> None:
    assert [feed_core.slot_of(0, r) for r in range(4)] == ["A", "B", "C", "D"]
    # Under rotation 2 the four texts occupy C, D, A, B in feed order.
    assert [feed_core.slot_of(i, 2) for i in range(4)] == ["C", "D", "A", "B"]


def test_the_opening_block_recaps_then_reveals_the_entry_section() -> None:
    slot_chunks = [f"Chunk {i} happened here. More of chunk {i} follows." for i in range(1, 6)]
    block = feed_core.opening_for_slot("B", slot_chunks)
    assert block.startswith("Book B, the story so far, skimmed:")
    assert f"Book B, section {feed_core.MIDSTREAM_CHUNK}:" in block
    # The recap covers the pre-entry chunks only; the entry section appears in full.
    assert "Chunk 3 happened here. More of chunk 3 follows." in block
    assert "More of chunk 1 follows." not in block


def test_a_slot_too_short_to_enter_midstream_is_refused() -> None:
    with pytest.raises(ValueError, match="mid-stream"):
        feed_core.opening_for_slot("A", ["one", "two"])


# ---------------------------------------------------------------------------- session record


def _session(actions: tuple[tuple[str, str], ...], rotation: int = 0) -> object:
    return feed_core.FeedSession(
        feed_id="f1",
        arm="intact",
        model="fake",
        rotation=rotation,
        replicate=0,
        dose=0.0,
        actions=actions,
    )


def test_spent_units_price_reads_and_skims_differently() -> None:
    session = _session((("read", "A"), ("skim", "B"), ("read", "A"), ("skim", "B")))
    assert session.spent_units == 2 * feed_core.READ_COST + 2 * feed_core.SKIM_COST


def test_the_target_read_share_counts_full_reads_only() -> None:
    # Rotation 1 puts the target (feed text 0) in slot B.
    session = _session(
        (("read", "B"), ("read", "C"), ("skim", "B"), ("read", "B"), ("skim", "D")),
        rotation=1,
    )
    assert session.target_slot == "B"
    assert session.target_read_share == pytest.approx(2 / 3)
    assert session.slot_read_shares["C"] == pytest.approx(1 / 3)
    assert session.slot_read_shares["D"] == 0.0


def test_a_session_of_pure_skims_reports_the_neutral_share() -> None:
    session = _session((("skim", "A"), ("skim", "B")))
    assert session.total_reads == 0
    assert session.target_read_share == pytest.approx(1 / feed_core.FEED_SIZE)
    assert session.skim_rate == 1.0


def test_abandonment_step_is_the_last_full_read_of_the_target() -> None:
    session = _session(
        (("read", "A"), ("skim", "A"), ("read", "B"), ("read", "A"), ("read", "C"), ("skim", "A"))
    )
    assert session.target_slot == "A"
    assert session.abandonment_step == 3
    never = _session((("read", "B"), ("skim", "A")))
    assert never.abandonment_step == -1


def test_read_switch_rate_ignores_skims() -> None:
    session = _session(
        (("read", "A"), ("skim", "D"), ("read", "A"), ("read", "B"), ("skim", "C"), ("read", "B"))
    )
    # Read sequence A, A, B, B: one change over three adjacent pairs.
    assert session.read_switch_rate == pytest.approx(1 / 3)
    assert _session((("read", "A"),)).read_switch_rate == 0.0


def test_repeat_skims_count_previews_bought_twice() -> None:
    session = _session(
        (("skim", "A"), ("skim", "A"), ("read", "A"), ("skim", "A"), ("skim", "B"), ("skim", "B"))
    )
    # A skimmed twice in a row (1 repeat), then read resets it; B skimmed twice (1 repeat).
    assert session.repeat_skims == 2


def test_an_unanswered_session_is_not_scorable() -> None:
    assert not _session(()).scorable
    broken = feed_core.FeedSession(
        feed_id="f1",
        arm="intact",
        model="fake",
        rotation=0,
        replicate=0,
        dose=0.0,
        actions=(("read", "A"),),
        unanswered=1,
    )
    assert not broken.scorable
    assert _session((("read", "A"),)).scorable


def test_a_session_records_the_prices_it_ran_at_and_charges_them() -> None:
    """The fp6 override runs skims at the read price; the record must say so itself."""
    flat = feed_core.FeedSession(
        feed_id="f1",
        arm="fp6",
        model="fake",
        rotation=0,
        replicate=0,
        dose=0.0,
        actions=(("skim", "A"), ("skim", "B")),
        skim_cost=feed_core.READ_COST,
    )
    assert flat.spent_units == 2 * feed_core.READ_COST
    registered = _session((("skim", "A"), ("skim", "B")))
    assert registered.read_cost == feed_core.READ_COST
    assert registered.skim_cost == feed_core.SKIM_COST
    assert registered.spent_units == 2 * feed_core.SKIM_COST
