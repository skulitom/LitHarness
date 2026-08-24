"""The backtest arms module: frozen turns, stimulus caps, session shape, stage-2 parsing.

What this file pins: the byte-frozen stage turns (each slot present exactly once, no verdict
vocabulary anywhere), the closed stage-2 schema over the documented enums, `ordered` as the
single place order is applied, the C-arm cap landing between paragraphs and under the 6,000
words, the P-arm extension past word 500 to the paragraph boundary (and its refusal when a
member's opening chapters cannot be identified), the session request's tag/sample arithmetic
across eight cells, `parse_stage2`'s one-outcome strictness, the sham windows' distinctness
and their None refusals, and byte determinism of every builder across two calls. Every
expectation below is hand-derived from the design: synthetic fictions carry globally
numbered tokens so the exact cut positions (paragraph 59 of the capped C-arm, paragraph 5 of
the P-arm opening) are stated before anything runs. What this file does not establish:
anything about real shard data — no parquet is read here, no model is called, and no
network is touched.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "research" / "sim-readership-backtest")
)
import pytest

module = pytest.importorskip("arms", reason="research module; imported by path")
corpus = pytest.importorskip("corpus", reason="research module; imported by path")
blinding = pytest.importorskip("blinding", reason="research module; imported by path")

#: The scope axiom's behavioural-only rule, as a scan: neither turn may carry a verdict word.
_VERDICT_VOCABULARY = re.compile(r"quality|good|bad|rate|score|judge", re.IGNORECASE)

_DATES = ("2025-03-01T00:00:00Z", "2025-03-02T00:00:00Z", "2025-03-03T00:00:00Z")

_DEFAULT_BLURB = "a short ordinary blurb"


def _token_chapters(
    *chapter_paragraph_counts: int, words: int, stem: str
) -> tuple[str, str, str]:
    """Three chapter texts of `words`-word paragraphs, tokens numbered across the whole book.

    Global numbering makes every cut position assertable by value: the token a window must
    end on is known before the module runs.
    """
    texts: list[str] = []
    counter = 0
    for count in chapter_paragraph_counts:
        chunk = []
        for _ in range(count):
            chunk.append(" ".join(f"{stem}{counter + k}" for k in range(words)))
            counter += words
        texts.append("\n\n".join(chunk))
    return (texts[0], texts[1], texts[2])


def _rows(
    fiction_id: str,
    *,
    title: str,
    chapters_texts: tuple[str, str, str],
    description: str = _DEFAULT_BLURB,
    chapter_titles: tuple[str, str, str] = ("Chapter 1", "Chapter 2", "Chapter 3"),
    average_views: float = 200.0,
) -> list[dict[str, Any]]:
    """Hand-built dump rows for one fiction; ordinals identify the opening by default."""
    return [
        {
            "fiction_id": fiction_id,
            "title": title,
            "author": "Rowan Alder",
            "tags": '["LitRPG"]',
            "warnings": "[]",
            "description": description,
            "status": None,
            "followers": 30.0,
            "total_views": 600.0,
            "average_views": average_views,
            "chapter_id": f"{fiction_id}-c{index + 1}",
            "chapter_title": chapter_titles[index],
            "release_datetime": _DATES[index],
            "text": text,
        }
        for index, text in enumerate(chapters_texts)
    ]


def _fiction(rows: list[dict[str, Any]]) -> Any:
    return corpus.fiction_from_rows(rows)


def _pair(high: str = "fh", low: str = "fl") -> Any:
    return corpus.Pair(
        pair_id=corpus._pair_id(high, low),
        high=high,
        low=low,
        cell=("undeclared_2025", "LitRPG", "short", ""),
        ratio=3.0,
    )


def _spec(pair_id: str, persona_id: str, order: int) -> Any:
    return module.SessionSpec(
        pair_id=pair_id,
        arm="C",
        persona_id=persona_id,
        order=order,
        excerpt_a_digest="aa" * 32,
        excerpt_b_digest="bb" * 32,
    )


# ------------------------------------------------------------------------------ frozen bytes


def test_the_stage_turns_are_pinned_byte_for_byte() -> None:
    """A reworded prompt is a different instrument; both turns are pinned literally."""
    assert module.STAGE1_TURN == (
        "Below are the openings of two serialised web fictions.\n\n"
        "Book A:\n\n{a}\n\n"
        "Book B:\n\n{b}\n\n"
        "In 2-3 sentences, name the concrete differences you noticed between these two "
        "openings: what happens, who is on the page, how the reading time is spent."
    )
    assert module.STAGE2_TURN == (
        "You have limited reading time and can keep going with only one of these openings - "
        "or with neither. Which would you continue reading: Book A, Book B, or neither?\n\n"
        'Answer as a single JSON object: {"continue": "A" | "B" | "neither", '
        '"reason": "<code>"} where <code> is one of slow-start, no-advancement, '
        'prose-friction, seen-it-before, confusing, wrong-genre-for-me, hooked-by-other, '
        'or "".'
    )


def test_stage1_turn_names_each_slot_exactly_once() -> None:
    """The {a} and {b} slots are the only places an excerpt enters stage 1."""
    assert module.STAGE1_TURN.count("{a}") == 1
    assert module.STAGE1_TURN.count("{b}") == 1


def test_neither_frozen_turn_carries_verdict_vocabulary() -> None:
    """Behavioural vocabulary only: no turn asks for or mentions a verdict."""
    for turn in (module.STAGE1_TURN, module.STAGE2_TURN):
        assert _VERDICT_VOCABULARY.search(turn) is None


def test_the_reason_codes_are_exactly_the_documented_closed_set() -> None:
    """One code per abandonment driver the population's axes cover, plus the empty code."""
    assert module.REASON_CODES == (
        "slow-start",
        "no-advancement",
        "prose-friction",
        "seen-it-before",
        "confusing",
        "wrong-genre-for-me",
        "hooked-by-other",
        "",
    )


def test_stage2_schema_is_closed_with_both_fields_required_and_documented_enums() -> None:
    """The §69 lesson: absent fields defaulting benign is a known defect shape."""
    assert module.STAGE2_SCHEMA["type"] == "object"
    assert module.STAGE2_SCHEMA["required"] == ["continue", "reason"]
    assert module.STAGE2_SCHEMA["additionalProperties"] is False
    properties = module.STAGE2_SCHEMA["properties"]
    assert properties["continue"]["enum"] == ["A", "B", "neither"]
    assert properties["reason"]["enum"] == list(module.REASON_CODES)


def test_ordered_keeps_sides_at_order_zero_swaps_at_order_one_and_refuses_other_orders(
) -> None:
    """Order 0 puts the high outcome in slot A; order 1 swaps; nothing else is an order."""
    assert module.ordered("HIGH", "LOW", 0) == ("HIGH", "LOW")
    assert module.ordered("HIGH", "LOW", 1) == ("LOW", "HIGH")
    with pytest.raises(ValueError, match="order"):
        module.ordered("HIGH", "LOW", 2)
    with pytest.raises(ValueError, match="order"):
        module.ordered("HIGH", "LOW", -1)


# ---------------------------------------------------------------------------------- stimuli


def test_c_arm_texts_caps_a_long_member_between_paragraphs_and_under_the_word_cap() -> None:
    """75 x 101-word paragraphs (+ a two-word title) in; the cap keeps 59 whole paragraphs.

    Hand-derived: floor(6000 / 101) = 59, so the cut lands exactly between paragraph 59
    (ending at token fh5958) and paragraph 60, strictly under the cap, and blinding has
    stripped the member's title from the shown bytes.
    """
    high_texts = _token_chapters(25, 25, 25, words=101, stem="fh")
    low_texts = _token_chapters(2, 2, 2, words=50, stem="fl")
    # The member's title appears once in its own prose; blinding must strip it.
    titled_texts = ("Deep Depths " + high_texts[0], high_texts[1], high_texts[2])
    mapping = {
        "fh": _fiction(_rows("fh", title="Deep Depths", chapters_texts=titled_texts)),
        "fl": _fiction(_rows("fl", title="Quiet Quests", chapters_texts=low_texts)),
    }
    out_high, out_low = module.c_arm_texts(_pair(), mapping, blinding.blind)

    kept: list[str] = ["[redacted] " + " ".join(f"fh{k}" for k in range(101))]
    kept += [
        " ".join(f"fh{base + offset}" for offset in range(101))
        for base in range(101, 5959, 101)
    ]
    assert out_high == "\n\n".join(kept)
    # The cap ran on the raw bytes (59 paragraphs); blinding then turned the two-word
    # title into one token, so the shown excerpt holds 58 x 101 + 102 = 5,960 words.
    assert len(out_high.split()) == 5960 < module.EXCERPT_CAP_WORDS
    assert "Deep Depths" not in out_high
    assert "[redacted]" in out_high

    assert out_low == "\n\n".join(low_texts)
    assert len(out_low.split()) == 300


def test_p_arm_texts_extends_past_word_five_hundred_to_the_paragraph_boundary() -> None:
    """Word 500 falls inside paragraph 5 of 120-word paragraphs, so all five are shown.

    Hand-derived: cumulative counts are 120/240/360/480/600, so `first_words` extends to
    600; the excerpt is the 10-word blurb plus those five whole paragraphs (610 words).
    The short member's chapter 1 holds 180 words, under 500, and is shown whole.
    """
    blurb = " ".join(f"blurb{n}" for n in range(10))
    mapping = {
        "fp": _fiction(
            _rows(
                "fp",
                title="Far Peaks",
                description=blurb,
                chapters_texts=_token_chapters(5, 1, 1, words=120, stem="pm"),
            )
        ),
        "fq": _fiction(
            _rows(
                "fq",
                title="Mist Moors",
                description=blurb,
                chapters_texts=_token_chapters(2, 1, 1, words=90, stem="qn"),
            )
        ),
    }
    out_high, out_low = module.p_arm_texts(_pair("fp", "fq"), mapping, blinding.blind)

    expected_opening = [
        " ".join(f"pm{base + offset}" for offset in range(120)) for base in range(0, 600, 120)
    ]
    assert out_high == "\n\n".join([blurb, *expected_opening])
    assert len(out_high.split()) == 610
    assert "Far Peaks" not in out_high

    expected_short = [
        " ".join(f"qn{base + offset}" for offset in range(90)) for base in range(0, 180, 90)
    ]
    assert out_low == "\n\n".join([blurb, *expected_short])
    assert len(out_low.split()) == 190


def test_p_arm_texts_shows_a_first_chapter_shorter_than_the_premise_window_whole() -> None:
    """A 40-word chapter 1 is under 500 words; nothing is invented to pad it."""
    blurb = " ".join(f"blurb{n}" for n in range(10))
    fiction = _fiction(
        _rows(
            "fs",
            title="Tiny Tales",
            description=blurb,
            chapters_texts=_token_chapters(1, 1, 1, words=40, stem="ts"),
        )
    )
    out_high, _ = module.p_arm_texts(_pair("fs", "fs"), {"fs": fiction}, blinding.blind)
    paragraph = " ".join(f"ts{n}" for n in range(40))
    assert out_high == "\n\n".join([blurb, paragraph])
    assert len(out_high.split()) == 50


def test_p_arm_texts_refuses_a_fiction_whose_opening_chapters_are_unidentifiable() -> None:
    """No ordinals and a recovered count above the cached count leave chapter 1 unknown.

    A premise session without its chapter text would be a different instrument wearing the
    same tag, so the refusal is a ValueError, not a blurb-only excerpt.
    """
    rows = _rows(
        "fx",
        title="Lost Larches",
        chapters_texts=_token_chapters(1, 1, 1, words=40, stem="lx"),
        chapter_titles=("Prologue", "Opening", "Aftermath"),
        average_views=100.0,  # recovered count 6 > 3 cached: release-order fallback dies
    )
    with pytest.raises(ValueError, match="unidentifiable"):
        module.p_arm_texts(_pair("fx", "fx"), {"fx": _fiction(rows)}, blinding.blind)


# --------------------------------------------------------------------------- session requests


def test_build_session_tag_carries_every_spec_field_and_the_stage_one_request() -> None:
    """The tag round-trips all six SessionSpec fields; top level mirrors plan[0]."""
    spec = _spec("pair-one", "grinder", 1)
    session = module.build_session(spec, "SYSTEM", "TEXT-A", "TEXT-B")

    assert session["tag"] == {
        "pair_id": "pair-one",
        "arm": "C",
        "persona_id": "grinder",
        "order": 1,
        "excerpt_a_digest": "aa" * 32,
        "excerpt_b_digest": "bb" * 32,
    }
    assert session["system"] == "SYSTEM"
    assert session["schema"] is None
    assert session["turns"][0]["content"] == module.STAGE1_TURN.format(
        a="TEXT-A", b="TEXT-B"
    )


def test_build_session_plan_holds_both_stages_with_the_registered_token_limits() -> None:
    """Stage 1 free text at 300 tokens; stage 2 under the closed schema at 60."""
    plan = module.build_session(_spec("pair-one", "grinder", 0), "S", "A", "B")["plan"]

    assert len(plan) == 2
    assert plan[0]["schema"] is None
    assert plan[0]["max_tokens"] == 300
    assert plan[0]["turns"][0]["content"] == module.STAGE1_TURN.format(a="A", b="B")
    assert plan[1]["schema"] == module.STAGE2_SCHEMA
    assert plan[1]["max_tokens"] == 60
    assert plan[1]["turns"][0]["content"] == module.STAGE2_TURN


def test_sample_indices_are_distinct_across_all_eight_pair_persona_order_cells() -> None:
    """Two pairs x two personas x both orders: eight cells, eight distinct indices."""
    specs = [
        _spec(pair_id, persona_id, order)
        for pair_id in ("pair-a", "pair-b")
        for persona_id in ("grinder", "stylist")
        for order in (0, 1)
    ]
    samples = [module.build_session(spec, "S", "A", "B")["sample"] for spec in specs]
    assert len(set(samples)) == len(samples) == 8


# ----------------------------------------------------------------------------------- parsing


def test_parse_stage2_reads_both_books_neither_and_every_reason_code_shape() -> None:
    """Each valid answer parses to exactly its choice and reason; "" is a valid reason."""
    assert module.parse_stage2('{"continue": "A", "reason": ""}') == ("A", "")
    assert module.parse_stage2('{"continue": "B", "reason": "slow-start"}') == (
        "B",
        "slow-start",
    )
    assert module.parse_stage2(
        '{"continue": "neither", "reason": "wrong-genre-for-me"}'
    ) == ("neither", "wrong-genre-for-me")


def test_parse_stage2_gives_one_none_for_every_malformed_shape() -> None:
    """No partial credit: out-of-enum, missing or extra keys, junk, and empty are all None."""
    assert module.parse_stage2('{"continue": "C", "reason": ""}') is None
    assert module.parse_stage2('{"continue": "A"}') is None
    assert module.parse_stage2("") is None
    assert module.parse_stage2('{"continue":"A","reason":"","extra":1}') is None
    assert module.parse_stage2("not json at all") is None
    assert module.parse_stage2('["A", ""]') is None
    assert module.parse_stage2('{"continue": "A", "reason": "masterpiece"}') is None


# -------------------------------------------------------------------------------------- shams


def test_sham_windows_returns_two_distinct_windows_of_the_same_book() -> None:
    """Nine 60-word paragraphs in; window two drops two leading paragraphs, same tail.

    Hand-derived: window one holds all nine paragraphs (sh0..sh539), window two seven
    (sh120..sh539); different bytes, identical final paragraph — same book, and a control
    that can move.
    """
    fiction = _fiction(
        _rows(
            "fsh",
            title="Same Saga",
            chapters_texts=_token_chapters(3, 3, 3, words=60, stem="sh"),
        )
    )
    windows = module.sham_windows(fiction, blinding.blind)
    assert windows is not None
    first, second = windows
    paragraphs = [
        " ".join(f"sh{base + offset}" for offset in range(60)) for base in range(0, 540, 60)
    ]
    assert first == "\n\n".join(paragraphs)
    assert second == "\n\n".join(paragraphs[2:])
    assert first != second
    assert first.endswith(paragraphs[-1])
    assert second.endswith(paragraphs[-1])


def test_sham_windows_returns_none_when_the_offset_leaves_no_second_window() -> None:
    """Text too short for a second distinct window refuses rather than shipping a flat sham."""
    fiction = _fiction(
        _rows("fsh2", title="Slim Scroll", chapters_texts=("one\n\nlone paragraph", "", ""))
    )
    assert module.sham_windows(fiction, blinding.blind) is None


def test_sham_windows_returns_none_when_the_opening_chapters_are_unidentifiable() -> None:
    """No identifiable opening means nothing to window; the sham arm gets None, not bytes."""
    rows = _rows(
        "fsh3",
        title="No Numbers",
        chapters_texts=_token_chapters(1, 1, 1, words=40, stem="nn"),
        chapter_titles=("Prologue", "Opening", "Aftermath"),
        average_views=100.0,
    )
    assert module.sham_windows(_fiction(rows), blinding.blind) is None


# -------------------------------------------------------------------------------- determinism


def test_every_builder_is_byte_deterministic_across_two_calls() -> None:
    """Two calls, equal bytes: stimulus builders, shams, and the full request alike."""
    mapping = {
        "fh": _fiction(
            _rows(
                "fh",
                title="Deep Depths",
                chapters_texts=_token_chapters(2, 2, 2, words=50, stem="dh"),
            )
        ),
        "fl": _fiction(
            _rows(
                "fl",
                title="Quiet Quests",
                chapters_texts=_token_chapters(2, 2, 2, words=50, stem="dl"),
            )
        ),
    }
    pair = _pair()
    spec = _spec("pair-det", "grinder", 0)

    assert module.c_arm_texts(pair, mapping, blinding.blind) == module.c_arm_texts(
        pair, mapping, blinding.blind
    )
    assert module.p_arm_texts(pair, mapping, blinding.blind) == module.p_arm_texts(
        pair, mapping, blinding.blind
    )
    assert module.sham_windows(mapping["fh"], blinding.blind) == module.sham_windows(
        mapping["fh"], blinding.blind
    )
    assert module.build_session(spec, "SYS", "A", "B") == module.build_session(
        spec, "SYS", "A", "B"
    )
