"""The shelf instrument's frozen bytes and registered definitions, checked without calls.

What this file pins: the ask and schema are the registered bytes (detection task, closed
fields), the rendering numbers six blocks and embeds no digest text, the seeded shuffle is
deterministic and digest-sensitive, detection counting separates hit / miss / zero on
hand-built answers, a sham floor comes from one sham's rows alone (the pooling function does
not exist), the truncation builder cuts whole sentences under the target length, a market-slot
phrase row carries token offsets and no text while an ours slot carries verbatim, and the paid
run refuses without the undocumented gated-run flag.
What it does not establish: anything about any reader's detection — no model call happens here,
and nothing under `derived/`, `results/` or `corpora/` is read.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

blurb_shelf = pytest.importorskip(
    "blurb_shelf",
    reason="research module; imported by path, skipped where research/ is unavailable",
)


def _row(index: int, words: int) -> dict[str, object]:
    return {
        "title": f"Title {index}",
        "listing": " ".join(f"w{index}t{n}" for n in range(words)) + ".",
        "followers": 1000 - index,
        "source": f"high{index}",
    }


HIGH = [_row(i, 30 + i) for i in range(24)]
DIGESTS = [blurb_shelf.digest_of(blurb_shelf.page(row)) for row in HIGH[:6]]


# ------------------------------------------------------------------------- the frozen bytes


def test_the_ask_and_schema_are_the_registered_bytes() -> None:
    assert blurb_shelf.SYSTEM == "You have read serial fiction on this market for years."
    assert "not written by this market's writers" in blurb_shelf.ASK
    assert "quote the exact phrase" in blurb_shelf.ASK
    assert "If none does, answer 0." in blurb_shelf.ASK
    schema = blurb_shelf.ANSWER_SCHEMA
    assert schema["required"] == ["off_shelf", "phrase"]
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == {"off_shelf", "phrase"}
    assert schema["properties"]["off_shelf"]["minimum"] == 0
    assert schema["properties"]["off_shelf"]["maximum"] == blurb_shelf.SHELF_SIZE == 6


# ------------------------------------------------------------------------------- the shelf


def test_shelf_rendering_numbers_six_blocks_and_embeds_no_digest_text() -> None:
    rendered = blurb_shelf.render_shelf(HIGH[:6])
    for number in range(1, 7):
        block = rendered.split("\n\n===\n\n")[number - 1]
        assert block.startswith(f"{number}. "), f"slot {number} unnumbered"
    assert rendered.endswith(blurb_shelf.ASK)
    assert all(digest not in rendered for digest in DIGESTS)


def test_the_seeded_shuffle_is_deterministic_and_changes_with_the_digest() -> None:
    first = blurb_shelf.seeded_order(HIGH, blurb_shelf.seed_of("shelf-digest-a"))
    again = blurb_shelf.seeded_order(HIGH, blurb_shelf.seed_of("shelf-digest-a"))
    other = blurb_shelf.seeded_order(HIGH, blurb_shelf.seed_of("shelf-digest-b"))
    assert first == again, "same inputs must give the same order"
    assert first != other, "a different digest must give a different order"
    assert sorted(row["source"] for row in first) == sorted(  # type: ignore[arg-type]
        row["source"] for row in HIGH  # type: ignore[arg-type]
    )


# ------------------------------------------------------------------------ detection counting


def _record(target_slot: int | None, named_slot: int | None) -> dict[str, int | None]:
    return {"target_slot": target_slot, "named_slot": named_slot}


def test_detection_counting_separates_target_hit_miss_and_zero_answer() -> None:
    tally = blurb_shelf.tally_draws(
        [
            _record(3, 3),  # hit: the draw names the target's own slot
            _record(5, 2),  # miss: the draw names something real
            _record(1, 0),  # zero-answer: the draw names nothing
            _record(2, None),  # refused: no answer at all
        ]
    )
    assert tally["hits"] == 1
    assert tally["zeros"] == 1
    assert tally["answered"] == 3
    assert tally["refused"] == 1
    assert tally["detection"] == pytest.approx(1 / 3)
    assert tally["by_slot"]["3"] == {"draws": 1, "hits": 1}


# --------------------------------------------------------------------------- the sham floors


def test_a_sham_floor_is_read_from_one_shams_rows_and_no_pooling_function_exists() -> None:
    tracked = [_record(None, 4), _record(None, 4), _record(None, 0), _record(None, 0)]
    quiet = [
        _record(None, 1),
        _record(None, 2),
        _record(None, 3),
        _record(None, 0),
        _record(None, 0),
        _record(None, 0),
    ]
    floor = blurb_shelf.sham_floor(tracked)
    assert floor["named"] == 2 and floor["false_alarm"] == pytest.approx(0.5)
    assert floor["modal_slot"] == 4 and floor["by_slot"] == {4: 2}
    assert floor["position_kill"] is True, "false alarms tracking one slot is the kill"
    other = blurb_shelf.sham_floor(quiet)
    assert other["modal_share"] == pytest.approx(1 / 3)
    assert other["position_kill"] is False
    assert floor != other, "two shams' floors must stay two floors"
    # A function that would pool must not exist: the reader of a leg takes ONE sham's rows —
    # exactly one parameter — and its own docstring forbids the second shelf.
    assert list(inspect.signature(blurb_shelf.sham_floor).parameters) == ["records"]
    assert "NEVER pooled" in (blurb_shelf.sham_floor.__doc__ or "")


# ------------------------------------------------------------------------ surface truncation


def test_the_truncation_builder_cuts_whole_sentences_to_the_target_length() -> None:
    text = " ".join(f"Sentence number {i} marches steadily onward." for i in range(10))
    cut = blurb_shelf.truncate_to_word_count(text, 12)
    words = cut.split()
    sentences = [s for s in cut.split(". ") if s]
    assert len(words) <= 12
    assert cut.endswith("."), "the last kept sentence must survive whole"
    assert all(sentence in text for sentence in sentences), "no partial sentence"
    next_sentence = "Sentence number 2 marches steadily onward."
    assert next_sentence not in cut, "a whole further sentence would exceed the target"


# --------------------------------------------------------------------- the quoted phrase rule


MARKET_LISTING = (
    "The wards held through the night. His mana was a patch of notes by the third gate."
)


def test_a_market_slot_phrase_row_carries_offsets_and_no_text_while_ours_is_verbatim() -> None:
    theirs = blurb_shelf.phrase_record("patch of notes", MARKET_LISTING, is_ours=False)
    assert "verbatim" not in theirs
    assert theirs["token_offsets"] == [10, 13] and theirs["located"] is True
    dumped = json.dumps(theirs)
    assert "patch" not in dumped and "notes" not in dumped
    ours = blurb_shelf.phrase_record("patch of notes", MARKET_LISTING, is_ours=True)
    assert ours["verbatim"] == "patch of notes"
    assert ours["token_offsets"] == [10, 13] and ours["located"] is True
    absent = blurb_shelf.phrase_record("never present anywhere", MARKET_LISTING, is_ours=False)
    assert absent == {"located": False}


# ------------------------------------------------------------------------------- the refusal


def test_run_refuses_to_spend_without_the_gated_run_flag(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert blurb_shelf.main(["--run", "--yes"]) == 1
    err = capsys.readouterr().err
    assert "--i-am-the-gated-run" in err


def test_dry_run_prints_the_exact_call_count_without_touching_derived(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    text = tmp_path / "listing.txt"
    text.write_text("Title\n\nOne short listing body.", encoding="utf-8")
    assert blurb_shelf.main(["--dry-run", "--texts", str(text)]) == 0
    out = capsys.readouterr().out
    # K=4 draws x (6 shams + 8 gradient + 4 surface + 1 ours) shelves.
    assert "76 calls exactly" in out


def test_the_selftest_passes() -> None:
    assert blurb_shelf.selftest() == 0
