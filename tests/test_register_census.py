"""Pins for the pure counters of research/quality-measurement/register_census.py.

Every case here is hand-derived from text on disk. The two fixture instances are the operator's
own quotes from read 7 §4.3, held as detector material and nothing else (§97.1); the refused
cases are hits a first version of the pattern actually drew and a hand-check rejected, so each
narrowing has a receipt that fails if it is ever loosened back.
"""

from __future__ import annotations

import pytest

register_census = pytest.importorskip(
    "register_census",
    reason="research module; needs the quality-measurement directory on the path",
)


def test_both_operator_named_instances_are_caught_by_tier_a() -> None:
    """The two books, two writers instances are what the counter exists for."""
    for text in register_census.GLOSS_FIXTURE:
        counts = register_census.gloss_counts(text)
        assert counts["tier_a"] >= 1, text


def test_every_hand_checked_false_positive_stays_refused() -> None:
    """Four measured false positives, each of which narrowed the pattern once.

    Two narrowings and one distinction: a located quantifier is not generic, `they` is anaphoric
    in narrative prose, and `which told <somebody>` attributes the inference to a character,
    which is point of view rather than a narratorial gloss.
    """
    for text in register_census.GLOSS_REFUSED:
        counts = register_census.gloss_counts(text)
        assert counts["tier_a"] == 0, text
        assert counts["tier_b"] == 0, text


def test_tier_a_and_tier_b_are_never_summed() -> None:
    """A manner gloss is a different assertion from an inference gloss.

    `gloss_counts` reports them under separate keys and `tier_a` excludes tier B, because a
    count named for one defect that measures another is the lying column §150.4 deleted a field
    for.
    """
    manner = "He said it the way you say a price."
    counts = register_census.gloss_counts(manner)
    assert counts["tier_b"] >= 1
    assert counts["tier_a"] == 0
    assert "tier_a" in counts and "tier_b" in counts
    assert counts["tier_a"] == counts["a1"] + counts["a2"]


def test_which_meant_is_counted_and_which_told_somebody_is_not() -> None:
    """The A2 recall hole and the distinction that keeps it honest."""
    gloss = "They gave Kell the good chair, which meant somebody wanted something."
    interiority = "He came out of turn, which told Silas his coat was worth more."
    assert register_census.gloss_counts(gloss)["a2"] == 1
    assert register_census.gloss_counts(interiority)["a2"] == 0


def test_proper_nouns_ignore_sentence_initial_capitals() -> None:
    """A name is found by capitalisation away from sentence start, never at it."""
    text = "Corin walked to Ambry. The market was open. He waited for Nessa by the stall."
    found = register_census.proper_nouns(text)
    assert "ambry" in found
    assert "nessa" in found
    # `The` opens a sentence and is not a name; `Corin` opens one too, so the check is
    # deliberately conservative and misses a name in that position rather than admitting `The`.
    assert "the" not in found
    assert "corin" not in found


def test_friction_excludes_names_and_reports_the_exclusion_size() -> None:
    """The proper-noun control is the load-bearing choice, so its size stays visible."""
    table = register_census.frequency_table(["the market was open and the cart was full"] * 100)
    total = sum(table.values())
    text = "The cart passed Ambry. Corin saw awnings above the trestle."
    out = register_census.friction(text, table, total=total, per_million_floor=1.0)
    assert out["rare_rate"] < out["rare_rate_with_names"]
    assert out["name_rate"] > 0.0
    assert out["tokens"] > 0


def test_the_rare_word_fixture_scores_rarer_than_ordinary_words() -> None:
    """`awnings` and `trestle` are what the unigram floor exists to find."""
    common = "the market was open and the cart was full of bread and the man was there"
    table = register_census.frequency_table([common] * 200)
    total = sum(table.values())
    ordinary = register_census.friction(
        "the man was there with the bread", table, total=total, per_million_floor=1.0
    )
    rare = register_census.friction(
        "the awnings above the trestle", table, total=total, per_million_floor=1.0
    )
    assert rare["rare_rate"] > ordinary["rare_rate"]


def test_the_jargon_fixture_is_invisible_to_the_unigram_floor() -> None:
    """The stated limitation, pinned as a test rather than left in a docstring.

    `live` and `build` are both ordinary words, so no unigram commonness floor can find
    `live build`. This is why `bigram_friction` exists and why the two are never summed.
    """
    corpus = ["a live wire and a build of the same kind"] * 200
    table = register_census.frequency_table(corpus)
    total = sum(table.values())
    # Every word of the probe is in the corpus, so the unigram floor sees nothing at all —
    # which is exactly the blindness being pinned, isolated from corpus-coverage noise.
    probe = "a live build of the same kind"
    out = register_census.friction(probe, table, total=total, per_million_floor=1.0)
    assert out["rare_rate"] == 0.0

    bigram_table: object = register_census.frequency_table([])
    for text in corpus:
        bigram_table.update(register_census.bigrams(register_census.tokens(text)))
    bigram_total = sum(bigram_table.values())
    caught = register_census.bigram_friction(
        probe, bigram_table, total=bigram_total, per_million_floor=0.1
    )
    # `live build` never occurs in the corpus though both its words do: the bigram floor is
    # the only one of the two that can reach the operator's jargon half.
    assert caught["rare_bigram_rate"] > 0.0


def test_a_gloss_shape_inside_dialogue_is_not_counted() -> None:
    """The class is a narratorial gloss, so speech is not eligible.

    Both cases are market hits a hand-check refused: a discourse marker and one character
    telling another what to do. Neither is a narrator performing the reader's deduction.
    """
    for speech in (
        'He shrugged. "Just so you know."',
        '"I let him off early, so you\'ll have to finish his shift."',
    ):
        counts = register_census.gloss_counts(speech)
        assert counts["tier_a"] == 0, speech
        assert counts["tier_b"] == 0, speech


def test_masking_speech_keeps_a_gloss_that_follows_a_quotation() -> None:
    """The second fixture is exactly this shape, so the mask must not eat it."""
    text = 'Terry said, "What," in the way people say it when they mean nothing.'
    assert register_census.gloss_counts(text)["tier_a"] >= 1
    masked = register_census.narration_only(text)
    assert len(masked) == len(text), "offsets must survive masking"
    assert "in the way people say" in masked


def test_the_like_trigger_was_removed_and_ordinary_similes_are_refused() -> None:
    """Three of ten sampled market hits were similes, which is what removed the trigger."""
    for simile in (
        "It is not like anyone had ever actually asked her for an apprenticeship before.",
        "It is kind of funny and a bit off, kind of like someone we both know.",
        "You looked like you needed one.",
    ):
        assert register_census.gloss_counts(simile)["tier_a"] == 0, simile


def test_generic_you_is_countable_for_manner_and_not_for_inference() -> None:
    """The fourth narrowing, and the one with a cost worth stating.

    Generic `you` and second-person `you` are the same word, and this corpus defeats every
    mechanical separation: quote counts are unbalanced (so positional pairing mispairs), and at
    least one sampled story is written in second person throughout. All five sampled market
    tier-A false positives came from `you`, so tier A gives the word up. Tier B keeps it because
    `the way you say a price` *is* the manner class — and tier B therefore inherits the
    imprecision, which is why the two are never summed.
    """
    second_person = "You can't think straight, so you don't have to think anymore."
    assert register_census.gloss_counts(second_person)["tier_a"] == 0
    # The manner shape still counts, which is the whole of tier B's job.
    assert register_census.gloss_counts("He said it the way you say a price.")["tier_b"] >= 1


def test_dropping_you_from_tier_a_kept_both_operator_instances() -> None:
    """A narrowing that removed a fixture would be a different instrument, not a better one."""
    for text in register_census.GLOSS_FIXTURE:
        assert register_census.gloss_counts(text)["tier_a"] >= 1, text


def test_the_registration_is_addressed_by_its_bytes() -> None:
    """A later edit to the registration cannot pass as the one the run was read under."""
    first = register_census.registration_digest()
    assert len(first) == 16
    assert first == register_census.registration_digest()


def test_the_registration_declares_no_bar() -> None:
    """No quantity here has had the four attainability checks run on it."""
    assert "no_bar" in register_census.PRE_REGISTRATION
    assert "quarantine" in register_census.PRE_REGISTRATION
    assert "control_same_pass" in register_census.PRE_REGISTRATION
