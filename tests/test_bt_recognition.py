"""The recognition screen's scoring, checked without calls.

Every expected value here is derived by hand from PREREG.md §3's contract before anything
runs: containment through case/quote/article variation, the short-title guard on both sides of
its 4-character boundary, the author rare-token rule with a common-token negative, and the
8-gram continuation boundary with a 7-token verbatim overlap that must miss. What this file
does not establish: anything about any model — no test here performs or simulates a call, and
the probes are only ever scored against strings written into this file.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "research" / "sim-readership-backtest")
)
import pytest

module = pytest.importorskip("recognition", reason="research module; imported by path")

#: Hand-built truth continuation. Tokens (14): the old bridge groaned under his weight and
#: the river swallowed the sound whole.
TRUTH = "the old bridge groaned under his weight and the river swallowed the sound whole"

#: Seven consecutive truth tokens ("and the river swallowed the sound whole") plus five new
#: ones. No 8-gram of this response occurs in TRUTH: the longest verbatim run is 7 tokens.
SEVEN_TOKEN_OVERLAP = "and the river swallowed the sound whole again though nobody heard it now"

#: Eight consecutive truth tokens ("weight ... whole") plus more text. The response's first
#: 8-gram is exactly TRUTH's tokens 7-14, so this hits at the boundary itself.
EIGHT_TOKEN_OVERLAP = "weight and the river swallowed the sound whole again though nobody heard"

#: Same 14-token run as TRUTH, but with curly quotes around "goodbye", an em dash inside the
#: run, and extra words after it. Normalisation must erase all three differences.
PUNCTUATED_OVERLAP = (
    'She said "goodbye" to the harbour lights\u2014and walked home through the rain alone '
    "that night."
)
HARBOUR_TRUTH = "she said goodbye to the harbour lights and walked home through the rain alone"

BANNED_WORDS = re.compile(r"\b(quality|good|rate)\b")


# ------------------------------------------------------------------------- the frozen probes


def test_probes_is_exactly_the_three_named_pairs_in_order() -> None:
    assert module.PROBES == (
        ("title", module.PROBE_TITLE),
        ("author", module.PROBE_AUTHOR),
        ("continuation", module.PROBE_CONTINUATION),
    )
    assert set(module.KNOWN_PROBES) == {"title", "author", "continuation"}


def test_each_probe_asks_for_the_blinded_excerpt_exactly_once() -> None:
    for _name, prompt in module.PROBES:
        assert prompt.count("{excerpt}") == 1
        rendered = prompt.format(excerpt="THE EXCERPT BODY")
        assert rendered.endswith("THE EXCERPT BODY")


def test_no_probe_contains_a_quality_verdict_word() -> None:
    """The no-verdict rail reaches even the probes: behavioural vocabulary only."""
    for name, prompt in module.PROBES:
        assert BANNED_WORDS.search(prompt) is None, f"probe {name} contains a verdict word"
        assert prompt.lower().count("quality") == 0


def test_the_three_probe_prompts_are_distinct_instruments() -> None:
    assert len({prompt for _name, prompt in module.PROBES}) == 3


# --------------------------------------------------------------------------------- normalise


def test_normalise_strips_the_leading_article_case_and_punctuation() -> None:
    assert module.normalise("The Wandering Inn") == "wandering inn"


def test_normalise_unifies_curly_quotes_dashes_and_collapses_whitespace() -> None:
    assert module.normalise("\u201cAn Odd\u2014Job!\u201d") == "odd job"
    assert module.normalise("  IT'S   a TEST. ") == "its a test"
    assert module.normalise("\u2019Twas the Night") == "twas the night"


def test_normalise_of_empty_and_whitespace_is_empty_without_crashing() -> None:
    assert module.normalise("") == ""
    assert module.normalise("   \n\t  ") == ""


# --------------------------------------------------------------------------------- title_hit


def test_title_hit_survives_case_quote_and_article_variation() -> None:
    assert module.title_hit("it's wandering inn, I think", "The Wandering Inn")
    assert module.title_hit("THIS IS THE KING'S AVATAR!!!", "The King\u2019s Avatar")
    assert module.title_hit("definitely ember in the ashes", "An Ember in the Ashes")


def test_title_hit_requires_a_contiguous_subsequence_not_scattered_words() -> None:
    """'wandering ... the ... inn' is not the title; only adjacent tokens confirm memory."""
    assert not module.title_hit("wandering somewhere near the inn", "The Wandering Inn")


def test_title_hit_rejects_an_unrelated_response() -> None:
    assert not module.title_hit("no idea what this one is, sorry", "The Wandering Inn")


def test_a_lowercase_mention_does_not_confirm_a_four_character_title() -> None:
    assert not module.title_hit("unknown, but it mentions a road", "Road")


def test_a_quoted_span_confirms_a_four_character_title() -> None:
    assert module.title_hit('might be "Road", not sure', "Road")
    assert module.title_hit("\u201cRoad\u201d maybe?", "Road")


def test_a_capitalised_span_confirms_a_four_character_title() -> None:
    assert module.title_hit("Pretty sure it's Road", "Road")


def test_the_short_title_guard_stops_at_five_characters() -> None:
    """'Dungeon' is one character past the guard: bare lowercase containment confirms it."""
    assert module.title_hit("a long dungeon sequence", "Dungeon")
    assert module.title_hit("a long ink sequence", "Ink") is False
    assert module.title_hit('the one called "Ink"', "Ink") is True


def test_title_hit_on_empty_title_or_empty_response_is_false_without_crashing() -> None:
    assert not module.title_hit("", "The Wandering Inn")
    assert not module.title_hit("some response", "")
    assert not module.title_hit("", "")


# --------------------------------------------------------------------------------- author_hit


def test_author_hit_confirms_the_full_name_through_case_variation() -> None:
    assert module.author_hit("pretty sure this is MARTHA WELLS", "Martha Wells")
    assert module.author_hit("that's John Smith alright", "John Smith")


def test_author_hit_confirms_on_the_longer_token_when_it_is_at_least_five_characters() -> None:
    assert module.author_hit("sounds like Martha to me", "Martha Wells")


def test_author_hit_rejects_the_shorter_token_alone() -> None:
    """Only 'martha' is distinctive; 'wells' alone is not evidence of the name."""
    assert not module.author_hit("reads more like Wells to me", "Martha Wells")


def test_a_four_character_first_name_alone_never_confirms_the_author() -> None:
    assert not module.author_hit("by John", "John Smith")


def test_a_three_character_distinctive_token_is_below_the_rare_token_floor() -> None:
    assert not module.author_hit("by Ana", "Ana Du")
    assert module.author_hit("by Ana Du", "Ana Du")


def test_author_hit_confirms_a_single_token_author_and_handles_empty_inputs() -> None:
    assert module.author_hit("probably Sanderson honestly", "Sanderson")
    assert not module.author_hit("", "Martha Wells")
    assert not module.author_hit("some response", "")
    assert not module.author_hit("", "")


# ---------------------------------------------------------------------------- continuation_hit


def test_seven_verbatim_tokens_miss_the_eight_gram_boundary() -> None:
    assert not module.continuation_hit(SEVEN_TOKEN_OVERLAP, TRUTH)


def test_eight_verbatim_tokens_hit_exactly_at_the_boundary() -> None:
    assert module.continuation_hit(EIGHT_TOKEN_OVERLAP, TRUTH)


def test_punctuation_and_quote_variation_inside_the_run_still_hits() -> None:
    """Curly quotes and an em dash inside the shared run must not break the 8-gram."""
    assert module.continuation_hit(PUNCTUATED_OVERLAP, HARBOUR_TRUTH)
    # A response carrying the same punctuation but sharing only the first seven tokens --
    # "she said goodbye to the harbour lights" -- then diverging must miss: seven shared
    # tokens is style territory, and the quotes prove punctuation was not doing the work.
    divergent = (
        'She said "goodbye" to the harbour lights before wandering off into a '
        "completely different book."
    )
    assert not module.continuation_hit(divergent, HARBOUR_TRUTH)


def test_a_response_shorter_than_n_cannot_form_a_boundary_gram() -> None:
    """Four verbatim tokens cannot form an 8-gram, or even a 5-gram."""
    short = "the old bridge groaned"
    assert not module.continuation_hit(short, TRUTH)
    assert not module.continuation_hit(short, TRUTH, n=5)


def test_continuation_hits_when_the_requested_n_shrinks_to_meet_the_overlap() -> None:
    assert module.continuation_hit(SEVEN_TOKEN_OVERLAP, TRUTH, n=7)
    assert not module.continuation_hit(SEVEN_TOKEN_OVERLAP, TRUTH, n=8)


def test_continuation_hit_on_empty_inputs_is_false_without_crashing() -> None:
    assert not module.continuation_hit("", TRUTH)
    assert not module.continuation_hit(EIGHT_TOKEN_OVERLAP, "")
    assert not module.continuation_hit(EIGHT_TOKEN_OVERLAP, "", n=8)


# -------------------------------------------------------------------------------- score_probe


def _score(probe: str, response: str) -> module.ProbeResult:
    return module.score_probe(
        probe,
        response,
        title="The Wandering Inn",
        author="Pirateaba",
        truth_continuation=TRUTH,
    )


def test_score_probe_reports_the_matched_span_for_a_title_hit() -> None:
    result = _score("title", "it's wandering inn, I think")
    assert result == module.ProbeResult(probe="title", hit=True, detail="wandering inn")


def test_score_probe_reports_the_matched_8_gram_for_a_continuation_hit() -> None:
    result = _score("continuation", EIGHT_TOKEN_OVERLAP)
    assert result == module.ProbeResult(
        probe="continuation", hit=True, detail="weight and the river swallowed the sound whole"
    )


def test_score_probe_scores_a_clean_wrong_answer_as_a_miss_with_no_detail() -> None:
    for probe in ("title", "author", "continuation"):
        result = _score(probe, "no idea, honestly")
        assert result == module.ProbeResult(probe=probe, hit=False, detail="")


def test_empty_whitespace_and_unknown_responses_are_clean_on_every_probe() -> None:
    """Declining to answer -- explicitly or by sending nothing -- is the honest negative."""
    for response in ("", "   \n\t ", "unknown", "Unknown.", "UNKNOWN"):
        for probe in ("title", "author", "continuation"):
            assert not _score(probe, response).hit, f"{response!r} on {probe} must be clean"


def test_an_unknown_probe_name_raises_naming_the_three_known_probes() -> None:
    with pytest.raises(ValueError, match="author, continuation, title"):
        _score("rating", "anything at all")


def test_score_probe_is_deterministic_across_identical_responses() -> None:
    response = 'might be "Wandering Inn", not sure'
    assert _score("title", response) == _score("title", response)


# ----------------------------------------------------------------------------------- classify


def test_classify_calls_any_single_hit_recognised() -> None:
    mixed = (
        module.ProbeResult(probe="title", hit=False, detail=""),
        module.ProbeResult(probe="author", hit=True, detail="pirateaba"),
        module.ProbeResult(probe="continuation", hit=False, detail=""),
    )
    assert module.classify(mixed) == "recognised"


def test_classify_keeps_all_miss_results_clean() -> None:
    clean = tuple(
        module.ProbeResult(probe=name, hit=False, detail="")
        for name in ("title", "author", "continuation")
    )
    assert module.classify(clean) == "clean"


def test_classify_of_no_results_at_all_is_clean() -> None:
    assert module.classify(()) == "clean"


# ------------------------------------------------------------------------------- the no-call rail


def test_the_module_declares_no_transport_and_imports_nothing_that_calls() -> None:
    source = Path(module.__file__).resolve().read_text(encoding="utf-8")
    for banned in ("requests", "urllib", "httpx", "openai", "socket", "pyarrow", "subprocess"):
        assert f"import {banned}" not in source, f"recognition.py imports {banned}"


