"""What the pure core of `payoff_landing` pins, checked directly rather than run once.

These tests cover only the value-in, value-out surface of `research/quality-measurement/
payoff_landing.py`: the excerpt windows (`head`, `tail`), the decline detector (`says_none`),
the matcher adaptation (`_depunctuate`) and the shipped matcher it feeds (`matches_ledger`),
the diagnostic passage builder (`_constructed_payoff`), the pair/census builder `build_pairs`
over in-memory ledgers and scene maps, the two frozen record classes, and the blinded owner
sheet. Every expected value below is derived by hand from the function's code — most
critically from `summarize.check_open_threads`' rule that a thread matches when a **majority
of its words longer than four characters** appear in the answer, which is why each
`matches_ledger` case states how many distinctive words hit.

What they do not establish: that the instrument works on a model (nothing here calls one),
that the ledger or scenes load (`read_ledger`/`read_scenes` need a database), that any rate
in `score` means anything, or that the study's verdicts are correct. A passing run says the
arithmetic and string handling behave as written, nothing more.

Hermetic: no database, no corpus read, no subprocess, no network, no sleep.
"""

from __future__ import annotations

import dataclasses

import pytest

payoff_landing = pytest.importorskip(
    "payoff_landing",
    reason="research module; needs the quality-measurement directory on the path",
)


def _scenes(*keys: str) -> dict[str, str]:
    """One six-word scene per key, every word prefixed with its key so any excerpt betrays
    which scene it came from. Six words is far under the 450-word excerpt cap, so `head` and
    `tail` are the identity on these — which is what lets the build_pairs tests state which
    scene a pair shows without calling the windows themselves."""
    return {key: " ".join(f"{key}-word{index:03d}" for index in range(6)) for key in keys}


def _crate_promise() -> payoff_landing.LedgerPromise:
    """Five distinctive words (>4 chars): sealed, crate, opened, before, departs."""
    return payoff_landing.LedgerPromise(
        "prm-crate",
        "sealed_crate",
        "the sealed crate must be opened before the ship departs",
        "s01",
        "s03",
        "paid",
    )


# --- head ---------------------------------------------------------------------


def test_head_keeps_the_first_n_words():
    assert payoff_landing.head("alpha beta gamma delta", words=2) == "alpha beta"


def test_head_joins_the_kept_words_on_single_spaces():
    assert payoff_landing.head("alpha\n  beta\tgamma", words=2) == "alpha beta"


def test_head_of_a_text_shorter_than_the_cap_returns_every_word():
    assert payoff_landing.head("alpha beta", words=5) == "alpha beta"


def test_head_asked_for_zero_words_returns_an_empty_string():
    assert payoff_landing.head("alpha beta", words=0) == ""


def test_head_of_an_empty_string_returns_an_empty_string():
    assert payoff_landing.head("", words=4) == ""


def test_the_default_head_cap_keeps_the_first_450_of_451_words():
    text = " ".join(f"w{index:03d}" for index in range(451))
    cut = payoff_landing.head(text)
    words = cut.split()
    assert len(words) == 450
    assert words[0] == "w000"
    assert words[-1] == "w449"
    assert "w450" not in words


# --- tail ---------------------------------------------------------------------


def test_tail_keeps_the_last_n_words():
    assert payoff_landing.tail("alpha beta gamma delta", words=2) == "gamma delta"


def test_tail_of_a_text_shorter_than_the_cap_returns_every_word():
    assert payoff_landing.tail("alpha beta", words=5) == "alpha beta"


def test_tail_of_an_empty_string_returns_an_empty_string():
    assert payoff_landing.tail("", words=4) == ""


def test_the_default_tail_cap_keeps_the_last_450_of_451_words():
    text = " ".join(f"w{index:03d}" for index in range(451))
    cut = payoff_landing.tail(text)
    words = cut.split()
    assert len(words) == 450
    assert words[0] == "w001"
    assert words[-1] == "w450"
    assert "w000" not in words


# --- says_none ----------------------------------------------------------------


def test_an_empty_answer_counts_as_none():
    assert payoff_landing.says_none("") is True
    assert payoff_landing.says_none("   ") is True


def test_an_answer_opening_with_a_decline_marker_counts_as_none():
    assert payoff_landing.says_none("None.") is True
    assert payoff_landing.says_none("Nothing was settled by the second passage.") is True


def test_settles_nothing_anywhere_in_the_answer_counts_as_none():
    said = "The second passage settles nothing the first left open."
    assert payoff_landing.says_none(said) is True


def test_no_debt_anywhere_in_the_answer_counts_as_none():
    assert payoff_landing.says_none("There is no debt left open here.") is True


def test_does_not_settle_anywhere_in_the_answer_counts_as_none():
    assert payoff_landing.says_none("This scene does not settle anything at all.") is True


def test_an_answer_that_names_a_debt_is_not_none():
    assert payoff_landing.says_none("It settles who sent the crate.") is False
    assert payoff_landing.says_none("The crate's contents are revealed.") is False


def test_a_decline_marker_at_the_start_of_a_word_still_counts_as_none():
    # The rule is prefix-of-the-lowercased-answer, not word-boundary: "Nonetheless" begins
    # with "none", so the detector reads it as declining. This pins the actual rule.
    assert payoff_landing.says_none("Nonetheless the scene moves on.") is True


def test_none_appearing_mid_sentence_without_a_marker_phrase_is_not_none():
    assert payoff_landing.says_none("And then, none of it seemed to matter.") is False


# --- _depunctuate ---------------------------------------------------------------


def test_depunctuate_lowercases_and_turns_every_punctuation_character_into_a_space():
    assert payoff_landing._depunctuate("Hello, World!") == "hello  world "


def test_depunctuate_leaves_punctuation_free_input_unchanged():
    plain = "the sealed crate"
    assert payoff_landing._depunctuate(plain) == plain


def test_depunctuate_keeps_letters_and_digits():
    assert payoff_landing._depunctuate("Chapter 7 ends.") == "chapter 7 ends "


def test_depunctuate_of_an_empty_string_is_empty():
    assert payoff_landing._depunctuate("") == ""


# --- matches_ledger -------------------------------------------------------------

# For the crate promise the thread's distinctive words (len > 4) are exactly five:
# sealed, crate, opened, before, departs. `check_open_threads` matches when
# hits * 2 >= len(distinctive), i.e. three or more of the five.


def test_a_restatement_hitting_exactly_three_of_five_distinctive_words_matches():
    said = "The second passage shows the sealed crate opened at last."
    assert payoff_landing.matches_ledger(said, _crate_promise()) is True


def test_a_restatement_hitting_only_two_of_five_distinctive_words_does_not_match():
    said = "The sealed crate is carried aboard through the whole scene."
    assert payoff_landing.matches_ledger(said, _crate_promise()) is False


def test_an_answer_starting_with_a_decline_marker_does_not_match_even_on_full_overlap():
    said = "Nothing was left open: the sealed crate must be opened before the ship departs."
    assert payoff_landing.matches_ledger(said, _crate_promise()) is False


def test_an_unrelated_answer_does_not_match():
    said = "An argument about the weather closes the chapter."
    assert payoff_landing.matches_ledger(said, _crate_promise()) is False


def test_an_empty_answer_does_not_match_and_does_not_crash():
    assert payoff_landing.matches_ledger("", _crate_promise()) is False


def test_commas_in_the_ledgers_wording_do_not_block_a_comma_free_answer():
    # The recorded side carries commas, the answer carries none. Before `_depunctuate` the
    # thread's tokens would be "letter," and "ledger," — absent from the answer — so this
    # match exists only because both sides are depunctuated.
    promise = payoff_landing.LedgerPromise(
        "prm-letter", "will_reading", "the letter, the ledger, the lawyer", "s01", None, "open"
    )
    said = "it settles the letter the ledger and the lawyer"
    assert payoff_landing.matches_ledger(said, promise) is True


def test_the_constructed_positive_fires_the_matcher_for_its_own_promise():
    # The diagnostic's premise: a paying passage built from the ledger's own sentence must
    # match, because it contains every distinctive word of the debt.
    promise = _crate_promise()
    constructed = payoff_landing._constructed_payoff(promise)
    assert payoff_landing.matches_ledger(constructed, promise) is True


# --- _constructed_payoff --------------------------------------------------------


def test_the_constructed_payoff_wraps_the_description_in_the_fixed_frame():
    promise = payoff_landing.LedgerPromise(
        "prm-x", "sealed_crate", "the sealed crate must be opened.", "s01", "s05", "paid"
    )
    expected = (
        "The matter was settled that afternoon, in front of the whole depot. "
        "The sealed crate must be opened. "
        "It was done, and nobody had cause to raise it again."
    )
    assert payoff_landing._constructed_payoff(promise) == expected


def test_an_already_capitalised_description_is_embedded_verbatim():
    promise = payoff_landing.LedgerPromise(
        "prm-x", "burned_letter", "The letter burns unread.", "s01", "s05", "paid"
    )
    payoff = payoff_landing._constructed_payoff(promise)
    assert "The letter burns unread." in payoff


def test_a_one_character_description_is_embedded_capitalised_and_does_not_crash():
    promise = payoff_landing.LedgerPromise("prm-x", "debt", "x", "s01", "s05", "paid")
    payoff = payoff_landing._constructed_payoff(promise)
    assert " X " in payoff


# --- LedgerPromise and LandingPair ----------------------------------------------


def test_a_ledger_promise_rejects_field_assignment():
    promise = _crate_promise()
    with pytest.raises(dataclasses.FrozenInstanceError):
        promise.status = "open"  # type: ignore[misc]


def test_a_landing_pair_rejects_field_assignment():
    promise = _crate_promise()
    pair = payoff_landing.LandingPair("pair-1", "paid", promise, "one", "two")
    with pytest.raises(dataclasses.FrozenInstanceError):
        pair.later = "three"  # type: ignore[misc]


def test_landing_pairs_with_identical_fields_are_equal():
    promise = _crate_promise()
    first = payoff_landing.LandingPair("pair-1", "paid", promise, "one", "two")
    second = payoff_landing.LandingPair("pair-1", "paid", promise, "one", "two")
    assert first == second


# --- build_pairs ----------------------------------------------------------------


def _open_promise(pid: str, opened: str) -> payoff_landing.LedgerPromise:
    return payoff_landing.LedgerPromise(
        pid, f"subject_{pid}", f"a debt about {pid}", opened, None, "open"
    )


def _paid_promise(pid: str, opened: str, paid: str) -> payoff_landing.LedgerPromise:
    return payoff_landing.LedgerPromise(
        pid, f"subject_{pid}", f"a debt about {pid}", opened, paid, "paid"
    )


def _by_arm(pairs: list[payoff_landing.LandingPair]) -> dict[str, list]:
    arms: dict[str, list[payoff_landing.LandingPair]] = {}
    for pair in pairs:
        arms.setdefault(pair.arm, []).append(pair)
    return arms


def test_an_all_open_ledger_produces_no_paid_or_mismatched_pairs_and_reports_both_unrunnable():
    scenes = _scenes("s01", "s02", "s03", "s04")
    promises = [_open_promise("prm-1", "s01"), _open_promise("prm-2", "s02")]
    pairs, census = payoff_landing.build_pairs(promises, scenes)
    arms = _by_arm(pairs)
    assert "paid" not in arms
    assert "mismatched" not in arms
    assert census["unrunnable"] == ["paid", "mismatched"]


def test_an_unpaid_pair_shows_the_opening_scene_then_the_middle_later_scene():
    # Promise opens at s01; the strictly later scenes are [s02, s03, s04, s05] and
    # later[len(later)//2] picks index 2, which is the third of the four: s04. Each scene is
    # under the excerpt cap, so head and tail of it are the scene itself.
    scenes = _scenes("s01", "s02", "s03", "s04", "s05")
    pairs, _ = payoff_landing.build_pairs([_open_promise("prm-1", "s01")], scenes)
    (unpaid,) = _by_arm(pairs)["unpaid"]
    assert unpaid.pair_id == "unpaid-prm-1"
    assert unpaid.promise.promise_id == "prm-1"
    assert unpaid.opened == scenes["s01"]
    assert unpaid.later == scenes["s04"]


def test_an_unpaid_pair_for_a_mid_book_promise_only_considers_strictly_later_scenes():
    # Opening at s02 leaves [s03, s04, s05] as candidates; index 3 // 2 = 1 picks s04.
    scenes = _scenes("s01", "s02", "s03", "s04", "s05")
    pairs, _ = payoff_landing.build_pairs([_open_promise("prm-2", "s02")], scenes)
    (unpaid,) = _by_arm(pairs)["unpaid"]
    assert unpaid.opened == scenes["s02"]
    assert unpaid.later == scenes["s04"]


def test_a_promise_opened_in_the_last_scene_gets_no_unpaid_pair():
    # No scene sorts strictly after s05, so the unpaid arm has nothing to face it with.
    scenes = _scenes("s01", "s05")
    pairs, census = payoff_landing.build_pairs([_open_promise("prm-9", "s05")], scenes)
    assert "unpaid" not in _by_arm(pairs)
    assert census["arms"]["unpaid"] == 0
    assert census["promises"] == 1
    assert census["open"] == 1


def test_a_promise_with_no_later_scene_still_yields_placebo_and_constructed_positive_pairs():
    # Those two arms need only the opening scene itself, so a promise the unpaid arm skipped
    # still feeds both of them.
    scenes = _scenes("s01", "s05")
    promise = _open_promise("prm-9", "s05")
    pairs, census = payoff_landing.build_pairs([promise], scenes)
    arms = _by_arm(pairs)
    (placebo,) = arms["placebo"]
    (positive,) = arms["constructed_positive"]
    assert placebo.opened == placebo.later == scenes["s05"]
    assert positive.later == payoff_landing._constructed_payoff(promise)
    assert census["arms"]["placebo"] == 1
    assert census["arms"]["constructed_positive"] == 1


def test_the_constructed_positive_arm_shows_the_built_passage_as_the_later_side():
    scenes = _scenes("s01", "s02")
    promise = _open_promise("prm-1", "s01")
    pairs, _ = payoff_landing.build_pairs([promise], scenes)
    (positive,) = _by_arm(pairs)["constructed_positive"]
    assert positive.later == payoff_landing._constructed_payoff(promise)
    assert positive.opened == scenes["s01"]


def test_the_placebo_arm_shows_the_opening_excerpt_twice():
    scenes = _scenes("s01", "s02")
    pairs, census = payoff_landing.build_pairs([_open_promise("prm-1", "s01")], scenes)
    (placebo,) = _by_arm(pairs)["placebo"]
    assert placebo.opened == placebo.later == scenes["s01"]
    assert census["arms"]["placebo"] == 1


def test_non_placebo_pairs_never_show_the_same_excerpt_twice():
    scenes = _scenes("s01", "s02", "s03", "s04", "s05")
    promises = [
        _paid_promise("prm-a", "s01", "s03"),
        _paid_promise("prm-b", "s02", "s05"),
        _open_promise("prm-c", "s02"),
        _open_promise("prm-d", "s04"),
    ]
    pairs, _ = payoff_landing.build_pairs(promises, scenes)
    repeats = [p for p in pairs if p.arm != "placebo" and p.opened == p.later]
    assert repeats == []


def test_two_paid_promises_mismatch_each_against_the_other_promises_payoff_scene():
    # The rotation: promise prm-a's opening faces prm-b's payoff scene and vice versa, so
    # each paid promise yields exactly one mismatched pair and none is paired with itself.
    scenes = _scenes("s01", "s02", "s03", "s05")
    promises = [
        _paid_promise("prm-a", "s01", "s03"),
        _paid_promise("prm-b", "s02", "s05"),
    ]
    pairs, census = payoff_landing.build_pairs(promises, scenes)
    mismatches = {p.promise.promise_id: p for p in _by_arm(pairs)["mismatched"]}
    assert set(mismatches) == {"prm-a", "prm-b"}
    assert mismatches["prm-a"].opened == scenes["s01"]
    assert mismatches["prm-a"].later == scenes["s05"]
    assert mismatches["prm-b"].opened == scenes["s02"]
    assert mismatches["prm-b"].later == scenes["s03"]
    assert census["arms"]["paid"] == 2
    assert census["arms"]["mismatched"] == 2
    assert census["unrunnable"] == []


def test_a_paid_pair_shows_the_opening_scene_then_the_recorded_payoff_scene():
    scenes = _scenes("s01", "s03")
    pairs, _ = payoff_landing.build_pairs([_paid_promise("prm-a", "s01", "s03")], scenes)
    (paid,) = _by_arm(pairs)["paid"]
    assert paid.opened == scenes["s01"]
    assert paid.later == scenes["s03"]


def test_a_single_paid_promise_gets_no_mismatched_pair_but_paid_itself_still_runs():
    # One paid promise has no *other* to rotate against, so only the mismatched arm starves.
    scenes = _scenes("s01", "s03")
    pairs, census = payoff_landing.build_pairs([_paid_promise("prm-a", "s01", "s03")], scenes)
    arms = _by_arm(pairs)
    assert arms["paid"]
    assert "mismatched" not in arms
    assert census["unrunnable"] == ["mismatched"]


def test_a_paid_promise_whose_payoff_scene_is_absent_from_the_scenes_map_contributes_no_pairs():
    scenes = _scenes("s01", "s02")
    ghost = payoff_landing.LedgerPromise(
        "prm-g", "subject_g", "a debt about prm-g", "s01", "s99", "paid"
    )
    pairs, census = payoff_landing.build_pairs([ghost], scenes)
    assert pairs == []
    assert census["promises"] == 1
    assert census["paid"] == 0
    assert census["open"] == 0
    assert census["unrunnable"] == ["paid", "mismatched"]


def test_an_open_promise_whose_opening_scene_is_absent_from_the_scenes_map_contributes_no_pairs():
    scenes = _scenes("s01", "s02")
    ghost = payoff_landing.LedgerPromise(
        "prm-g", "subject_g", "a debt about prm-g", "s99", None, "open"
    )
    pairs, census = payoff_landing.build_pairs([ghost], scenes)
    assert pairs == []
    assert census["promises"] == 1
    assert census["open"] == 1
    assert all(count == 0 for count in census["arms"].values())


def test_an_empty_ledger_against_empty_scenes_yields_no_pairs_and_a_zero_census():
    pairs, census = payoff_landing.build_pairs([], {})
    assert pairs == []
    assert census["promises"] == 0
    assert census["paid"] == 0
    assert census["open"] == 0
    assert census["scenes"] == 0
    assert all(count == 0 for count in census["arms"].values())
    assert census["unrunnable"] == ["paid", "mismatched"]


def test_the_census_reports_scene_count_and_per_arm_pair_counts():
    # prm-a is paid; prm-b opens at s02 with s03 strictly later, so it gets an unpaid pair;
    # prm-c opens at s03, the last scene, so only its placebo and constructed-positive pairs
    # exist. The positive arm therefore has one pair more than the unpaid arm.
    scenes = _scenes("s01", "s02", "s03")
    promises = [
        _paid_promise("prm-a", "s01", "s02"),
        _open_promise("prm-b", "s02"),
        _open_promise("prm-c", "s03"),
    ]
    _, census = payoff_landing.build_pairs(promises, scenes)
    assert census["scenes"] == 3
    assert census["promises"] == 3
    assert census["paid"] == 1
    assert census["open"] == 2
    assert census["arms"]["paid"] == 1
    assert census["arms"]["mismatched"] == 0
    assert census["arms"]["unpaid"] == 1
    # The placebo arm takes only unpaid[:max(len(unpaid)//4, 1)] — the first promise, prm-b.
    assert census["arms"]["placebo"] == 1
    assert census["arms"]["constructed_positive"] == 2


# --- owner_sheet ----------------------------------------------------------------


def _one_pair() -> payoff_landing.LandingPair:
    promise = payoff_landing.LedgerPromise(
        "prm-1",
        "secret_subject_name",
        "a very distinctive ledger wording about the crate",
        "s01",
        "s03",
        "paid",
    )
    return payoff_landing.LandingPair("paid-prm-1", "paid", promise, "first passage", "second")


def test_the_owner_sheet_lists_both_passages_and_mark_lines_under_each_pair_heading():
    sheet = payoff_landing.owner_sheet([_one_pair()])
    assert sheet.startswith("# Payoff landing — owner sheet")
    assert "## paid-prm-1" in sheet
    assert "PASSAGE ONE:\nfirst passage" in sheet
    assert "PASSAGE TWO:\nsecond" in sheet
    assert "\nmark:\nwhat:\n" in sheet


def test_the_owner_sheet_withholds_the_ledgers_subject_and_wording():
    sheet = payoff_landing.owner_sheet([_one_pair()])
    assert "secret_subject_name" not in sheet
    assert "a very distinctive ledger wording about the crate" not in sheet


def test_the_owner_sheet_for_no_pairs_carries_the_instructions_and_no_headings():
    sheet = payoff_landing.owner_sheet([])
    assert "mark:" in sheet
    assert "what:" in sheet
    assert "## " not in sheet


def test_the_owner_sheet_emits_one_heading_per_pair():
    first = _one_pair()
    second = payoff_landing.LandingPair("unpaid-prm-2", "unpaid", first.promise, "a", "b")
    sheet = payoff_landing.owner_sheet([first, second])
    assert sheet.count("## ") == 2


# --- selftest -------------------------------------------------------------------


def test_the_module_selftest_passes():
    assert payoff_landing.selftest() == 0



