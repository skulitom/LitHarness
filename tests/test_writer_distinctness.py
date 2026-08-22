"""What the pure core of `writer_distinctness` pins, and what it does not.

Pinned: `scramble_dossier` holds vocabulary, length, determinism and the sentence
inventory fixed while destroying sentence order, and passes degenerate dossiers
through untouched; the prompt builders (`_beat`, `_packet`, `prompts_for`) render
and carry exactly the pieces they are given, with the writer's dossier reaching
the system message and never the user prompt; `report` buckets constructed draft
sets into the three verdicts the rail names, refusing a verdict whenever any pair
is unreadable or byte-identical, and clearing the shuffle control only when a
twin comparison actually reads comparable.

Not established: anything about a model, a roster's real distinctness, or whether
the shuffle control clears on live prose — everything that needs `elicit.Elicitor`,
a database, a corpus or a results file is out of scope, as is `draw` and `main`.
"""

from __future__ import annotations

import pytest

writer_distinctness = pytest.importorskip(
    "writer_distinctness",
    reason="research module; needs the quality-measurement directory on the path",
)

#: Three draws each side is the floor below which `distinctness` refuses to read.
READABLE_A = [
    "alpha beta gamma delta",
    "alpha beta gamma epsilon",
    "alpha beta gamma zeta",
]
READABLE_B = [
    "omega psi chi phi",
    "omega psi chi upsilon",
    "omega psi chi tau",
]

#: Legal under `writers.legal_dossier`: what this writer knows the inside of, and
#: nothing about how prose ought to be written.
TIDE_DOSSIER = "You have pulled nets out of cold water all your life."

EIGHT_SENTENCES = (
    "One crew hauled the seine at dawn. "
    "A second gutted mackerel by noon. "
    "The third mended nets until dark. "
    "Salt stiffened every rope aboard. "
    "Nobody spoke during the haul. "
    "Gulls took the discards offshore. "
    "The tide turned before the last lift. "
    "Everyone counted the boxes twice."
)


def test_scrambling_many_sentences_keeps_the_exact_word_multiset():
    scrambled = writer_distinctness.scramble_dossier(EIGHT_SENTENCES)
    assert sorted(scrambled.split()) == sorted(EIGHT_SENTENCES.split())
    assert len(scrambled.split()) == len(EIGHT_SENTENCES.split())


def test_scrambling_many_sentences_changes_the_sentence_order():
    assert writer_distinctness.scramble_dossier(EIGHT_SENTENCES) != EIGHT_SENTENCES


def test_scrambling_preserves_every_whole_sentence():
    first = "One crew hauled the seine at dawn."
    second = "A second gutted mackerel by noon."
    third = "The third mended nets until dark."
    fourth = "Salt stiffened every rope aboard."
    dossier = f"{first} {second} {third} {fourth}"
    scrambled = writer_distinctness.scramble_dossier(dossier)
    for sentence in (first, second, third, fourth):
        assert sentence in scrambled


def test_the_same_dossier_scrambles_to_the_same_order_twice():
    dossier = (
        "First sentence stands here. "
        "Second sentence follows it. "
        "Third sentence closes the file. "
        "Fourth sentence pads the seed."
    )
    assert (
        writer_distinctness.scramble_dossier(dossier)
        == writer_distinctness.scramble_dossier(dossier)
    )


def test_a_single_sentence_dossier_is_returned_unchanged():
    dossier = "Only one sentence lives here."
    assert writer_distinctness.scramble_dossier(dossier) == dossier


def test_an_empty_dossier_is_returned_unchanged():
    assert writer_distinctness.scramble_dossier("") == ""


def test_a_dossier_without_terminal_punctuation_is_returned_unchanged():
    dossier = "just some words with no full stop"
    assert writer_distinctness.scramble_dossier(dossier) == dossier


def test_a_two_sentence_dossier_keeps_both_sentences():
    first = "The bow line parted first."
    second = "The stern followed within minutes."
    dossier = f"{first} {second}"
    scrambled = writer_distinctness.scramble_dossier(dossier)
    assert first in scrambled
    assert second in scrambled
    assert sorted(scrambled.split()) == sorted(dossier.split())


def test_scrambled_output_carries_no_double_spaces_or_newlines_and_no_trim():
    dossier = (
        "  One crew hauled the seine.\n  A second gutted mackerel.  "
        "The third mended nets.\n  Salt stiffened every rope.  "
    )
    scrambled = writer_distinctness.scramble_dossier(dossier)
    assert "  " not in scrambled
    assert "\n" not in scrambled
    assert scrambled == scrambled.strip()
    assert sorted(scrambled.split()) == sorted(dossier.split())



def test_prompts_for_returns_a_nonempty_system_and_prompt_pair():
    system, prompt = writer_distinctness.prompts_for(None)
    assert isinstance(system, str) and system
    assert isinstance(prompt, str) and prompt


def test_a_writer_dossier_opens_the_system_message():
    from litharness.domain import writers

    writer = writers.build("tide", TIDE_DOSSIER)
    system, _ = writer_distinctness.prompts_for(writer)
    assert system.startswith(TIDE_DOSSIER)


def test_the_user_prompt_is_identical_with_and_without_a_writer():
    from litharness.domain import writers

    writer = writers.build("tide", TIDE_DOSSIER)
    anonymous_system, anonymous_prompt = writer_distinctness.prompts_for(None)
    _, writer_prompt = writer_distinctness.prompts_for(writer)
    assert writer_prompt == anonymous_prompt
    assert TIDE_DOSSIER not in anonymous_system


def test_the_prompt_names_the_book_the_beat_and_its_place_in_the_book():
    _, prompt = writer_distinctness.prompts_for(None)
    assert "Now write The Toll Road: The Archive — scene 1 of 30." in prompt


def test_the_target_word_count_reaches_the_system_message():
    system, _ = writer_distinctness.prompts_for(None)
    assert f"Write approximately {writer_distinctness.TARGET_WORDS} words" in system


def test_the_beat_carries_the_first_setup_scene_of_thirty():
    beat = writer_distinctness._beat()
    assert beat.logical_id == "s1"
    assert beat.ordinal == 1
    assert beat.of_total == 30
    assert beat.title == "The Archive"
    assert beat.function == "setup"
    assert beat.story_order_key == "s1"


def test_the_beat_rides_the_shared_six_beat_template():
    from litharness.domain.beats import SIX_BEAT

    assert writer_distinctness._beat().template_id == SIX_BEAT.template_id


def test_the_packet_addresses_the_beat_it_was_built_for():
    packet = writer_distinctness._packet()
    assert packet.query_id == "beat:s1"
    assert packet.target_logical_id == "s1"
    assert packet.book_id == "bk"
    assert packet.branch_id == "br"
    assert packet.base_revision_id == "rev"


def test_the_packet_carries_no_sections_of_its_own():
    assert writer_distinctness._packet().sections == {}


def test_report_reads_distinct_pairs_and_a_clearing_twin_as_comparable():
    built = writer_distinctness.report({"x": READABLE_A, "y": READABLE_B}, {"x": READABLE_B}, [])
    assert built["every_pair_distinct"] is True
    assert built["shuffle_control_clears"] is True
    assert built["verdict"] == "COMPARABLE"


def test_report_reads_a_roster_without_twins_as_distinct_but_order_blind():
    built = writer_distinctness.report({"x": READABLE_A, "y": READABLE_B}, {}, [])
    assert built["every_pair_distinct"] is True
    assert built["shuffle_control_clears"] is False
    assert built["verdict"] == "DISTINCT_BUT_ORDER_BLIND"


def test_report_does_not_claim_the_shuffle_control_cleared_on_an_unreadable_twin():
    built = writer_distinctness.report(
        {"x": READABLE_A, "y": READABLE_B}, {"x": READABLE_A[:2]}, []
    )
    assert built["every_pair_distinct"] is True
    row = built["shuffle_control"][0]
    assert row["writer"] == "x"
    assert row["reading"] == "unreadable"
    assert row["order_carries_something"] is False
    assert built["shuffle_control_clears"] is False
    assert built["verdict"] == "DISTINCT_BUT_ORDER_BLIND"


def test_report_refuses_a_verdict_when_a_pair_has_too_few_draws_to_read():
    built = writer_distinctness.report({"x": READABLE_A[:2], "y": READABLE_B}, {}, [])
    pair = built["pairs"][0]
    assert pair["left"] == "x"
    assert pair["right"] == "y"
    assert pair["reading"] == "unreadable"
    assert pair["draws"] == 2
    assert pair["comparable"] is False
    assert built["verdict"] == "NOT_COMPARABLE"


def test_report_refuses_a_verdict_when_a_pair_is_byte_identical():
    built = writer_distinctness.report({"x": READABLE_A, "y": list(READABLE_A)}, {}, [])
    pair = built["pairs"][0]
    assert pair["reading"] == "identical"
    assert pair["comparable"] is False
    assert built["every_pair_distinct"] is False
    assert built["verdict"] == "NOT_COMPARABLE"


def test_report_reads_an_empty_roster_as_not_comparable():
    built = writer_distinctness.report({}, {}, [])
    assert built["writers"] == []
    assert built["pairs"] == []
    assert built["verdict"] == "NOT_COMPARABLE"


def test_report_reads_a_lone_readable_writer_as_not_comparable():
    built = writer_distinctness.report({"x": READABLE_A}, {}, [])
    assert built["pairs"] == []
    assert built["verdict"] == "NOT_COMPARABLE"


def test_report_pairs_each_writer_once_in_sorted_name_order():
    built = writer_distinctness.report(
        {"z": READABLE_A, "x": READABLE_B, "y": READABLE_A}, {}, []
    )
    assert built["writers"] == ["x", "y", "z"]
    assert [(pair["left"], pair["right"]) for pair in built["pairs"]] == [
        ("x", "y"),
        ("x", "z"),
        ("y", "z"),
    ]


def test_report_records_three_draws_and_a_distinct_reading_for_separated_sets():
    built = writer_distinctness.report({"x": READABLE_A, "y": READABLE_B}, {}, [])
    pair = built["pairs"][0]
    assert pair["left"] == "x"
    assert pair["right"] == "y"
    assert pair["reading"] == "distinct"
    assert pair["draws"] == 3
    assert pair["comparable"] is True
    assert pair["within"] is not None
    assert pair["between"] is not None


def test_report_lists_no_anonymous_rows_without_an_anonymous_draft_set():
    built = writer_distinctness.report({"x": READABLE_A}, {}, [])
    assert built["against_anonymous_drafter"] == []


def test_report_compares_every_writer_against_a_nonempty_anonymous_set():
    built = writer_distinctness.report({"x": READABLE_A}, {}, READABLE_B)
    assert built["against_anonymous_drafter"] == [{"writer": "x", "reading": "distinct"}]


def test_the_module_selftest_passes():
    assert writer_distinctness.selftest() == 0
