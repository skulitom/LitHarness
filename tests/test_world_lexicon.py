"""Arithmetic for `research/quality-measurement/world_lexicon.py`, and the counter it reads.

**Why research code has tests in this suite**, for `test_platform_priors.py`'s reason: the
properties below are the ones a reader cannot check by eye, and a substrate run over three
gigabytes of parquet would discover them only after it had run. The corpus is not touched here —
the point is the algebra and the noun extraction, and a test that only passes where a gitignored
corpus happens to sit is not a guard.

**M2 has no bar, so nothing here asserts one.** `plan/world-architect.md` §6 registers the
genre-lexicon overlap as a reported distribution and says why: `opening_proper_nouns` was
nominated for a named reader defect and then placed the complained-about chapter at the 68.5th
percentile of published openings. These tests pin what the number *is*, never what it should be.
"""

from __future__ import annotations

import sys
from pathlib import Path

RESEARCH = Path(__file__).resolve().parents[1] / "research" / "quality-measurement"
if str(RESEARCH) not in sys.path:  # pragma: no cover - import plumbing
    sys.path.insert(0, str(RESEARCH))

import world_lexicon  # noqa: E402

from litharness.domain import worlds  # noqa: E402


def test_the_selftest_passes() -> None:
    assert world_lexicon.selftest() == 0


def test_overlap_partitions_the_nouns_it_was_given() -> None:
    """Shared plus coined is the whole list, and nothing is counted twice."""
    nouns = ["assay", "corvessa", "seal", "dunnel"]
    measured = world_lexicon.overlap(nouns, {"assay", "seal"}, {"dunnel"})
    assert measured["n"] == 4
    assert measured["shared"] == ["assay", "dunnel", "seal"]
    assert measured["coined"] == ["corvessa"]
    assert measured["share_in_either"] == 0.75
    assert set(measured["shared"]) | set(measured["coined"]) == set(nouns)


def test_an_empty_world_reports_that_rather_than_a_zero() -> None:
    """A substrate that could not be read must not look like a measurement of nothing."""
    assert world_lexicon.overlap([], {"assay"}, set()) == {"n": 0}


def test_key_nouns_does_not_count_the_first_word_of_a_sentence() -> None:
    """The correction the first live run forced, kept runnable.

    Before it, `Not the city.` contributed `not` to a world's list of coined names, and so did
    `From`, `One` and `Read`. The pre-fix figures stay reported in stage-0 §107.6 beside the
    post-fix ones; this is the guard against the bug returning.
    """
    records = [
        worlds.world_record("tide_rule", worlds.WORLD_RULE_PREDICATE,
                            value="Not the city. From here on Marnhal pays the Assay House."),
        worlds.world_record("house_of_marnhal", worlds.ENTITY_ROLE_PREDICATE,
                            value="institution"),
    ]
    nouns = set(worlds.key_nouns(records))
    assert {"marnhal", "assay", "house"} <= nouns
    assert not ({"not", "from", "one", "read"} & nouns)


def test_key_nouns_drops_the_connectives_inside_an_id() -> None:
    records = [worlds.world_record("house_of_the_bare_wrist", worlds.ENTITY_ROLE_PREDICATE,
                                   value="institution")]
    nouns = set(worlds.key_nouns(records))
    assert "wrist" in nouns and "bare" in nouns
    assert "the" not in nouns and "house" not in nouns
