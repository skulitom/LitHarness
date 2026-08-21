"""`opening_proper_nouns`: the counter nominated by the 2026-08-21 human read.

**What these tests do not establish.** Nothing here shows that fewer names in an opening is
better, or that readers mind. That is a preference measurement and it has not been made: the
counter is registered in `COUNTERS` and deliberately absent from `AXES`, so it carries no pole
and no bar. `test_the_counter_is_not_an_axis` is the one that pins that, and it is the most
important test in the file.

The test worth reading second is `test_the_counter_recovers_the_names_the_human_named`, which
is the acceptance anchor: the read hand-counted the names on Reappraisal's first page, and a
counter blind to the one instance a human actually pointed at would be measuring something
else and calling it that.
"""

from __future__ import annotations

from litharness.domain import axes as axes_mod
from litharness.domain.axes import (
    OPENING_WINDOW_WORDS,
    opening_proper_noun_names,
    opening_proper_nouns,
)

#: The opening of Serial Pilot 1 chapter 1 as published, trimmed to the counted window. Held
#: here rather than read from `book-library/`, which is derived output and not in git: a test
#: that depended on it would pass or fail according to whether somebody had run a tick.
ANCHOR = (
    "Weigh Street took its light late. The sun had to climb the mill lofts on the east side "
    "before it reached the assay house door, so the first hour of business ran in a grey that "
    "made every metal look like every other metal, which was, Silas had long thought, a joke "
    "at somebody's expense.\n\n"
    "The porters were already stacked three deep on the outer scales, sacks of foundry "
    "sweepings on their shoulders, arguing the way men argue when they have agreed on "
    "everything and are only killing time. Beside the door the fee schedule stood chalked "
    "fresh: WEIGHT & PURITY, ONE MARK. VALUATION WITH CERTIFICATE, ONE AND A HALF. Marta had "
    "written it at dawn with her left hand cupped under the chalk to catch the dust, because "
    "she hated dust on the step.\n\n"
    "Inside, she was counting the float. Her thumb walked the coin stacks with a sound like a "
    "cricket, and she did not look up when Silas hung his coat.\n\n"
    '"Vance is in," she said. "He wants the Kelling ledger closed today."\n\n'
    '"It\'ll close."\n\n'
    '"Then close it before somebody gives you something shiny."\n\n'
    "The eighth man in the queue gave him something shiny at twenty past the hour.\n\n"
    "He came to the counter out of turn and nobody stopped him, which told Silas his coat was "
    "worth more than the queue's patience. He introduced himself as Hesk Turrow, factor for "
    "the Bellow and Sons hauling concern, and he set down a ring on the felt as though setting "
    "down a sleeping bird.\n\n"
    '"Signet," Turrow said. "Vessil workshop, crown-and-hook mark, struck in eleven '
    "thirty-eight. Family piece. I want it certified at nine marks for a surety pledge and I "
    'want it done this morning."\n\n'
    "\"I can do it this morning,\" Silas said. \"I can't promise you nine.\"\n\n"
    "\"It's a Vessil.\"\n\n"
    "\"That's one of the things I'll be finding out.\"\n\n"
    # Past the three-hundredth word, and load-bearing. A capital that only ever opens a
    # sentence is indistinguishable from `Inside`, so the counter believes one only when the
    # book also writes it mid-sentence somewhere. These are the chapter's own later uses of
    # Marta and Vance — real clauses rather than invented ones, so the anchor stays the anchor
    # — and they are outside the window, so they supply evidence without being introductions.
    "He pressed the house seal into the wax and told Marta to take the mark. "
    "Master Ottil Vance came out of the back. "
    "He did not see what came up Weigh Street from the harbour."
)

#: What the counter recovers from `ANCHOR`, in order of introduction.
ANCHOR_NAMES = (
    "Weigh Street",
    "Silas",
    "Marta",
    "Vance",
    "Kelling",
    "Hesk Turrow",
    "Bellow and Sons",
    "Vessil",
)


def test_the_counter_is_not_an_axis() -> None:
    """The fence, and the reason this file exists at all.

    An axis carries a preferred pole; a pole is a claim about what readers want; that claim
    needs a measured distribution and an operator act (`plan/reader-read-2.md`). The counter is
    callable and testable without any of that having happened, and `counts()` — which is what
    the off-target check and the feedback loop read — must not see it until it does.
    """
    assert "opening_proper_nouns" in axes_mod.COUNTERS
    assert "opening_proper_nouns" not in axes_mod.AXES
    assert all(axis.counter_id != "opening_proper_nouns" for axis in axes_mod.AXES.values())
    assert "opening_proper_nouns" not in axes_mod.counts(ANCHOR)


def test_the_counter_recovers_the_names_the_human_named() -> None:
    """The acceptance anchor. See `research/quality-measurement/opening-counters-results.md`
    for the full agreement report, including the two disagreements and which of them is the
    human's error rather than the counter's."""
    assert opening_proper_noun_names(ANCHOR) == ANCHOR_NAMES
    assert opening_proper_nouns(ANCHOR) == float(len(ANCHOR_NAMES))


def test_shouted_signage_is_not_a_cast_of_characters() -> None:
    """`WEIGHT & PURITY, ONE MARK` is a chalked price list. A rule that only asked whether a
    word was capitalised read seven proper nouns off it."""
    for shouted in ("WEIGHT", "PURITY", "VALUATION", "CERTIFICATE", "MARK", "HALF"):
        assert shouted not in " ".join(ANCHOR_NAMES)


def test_a_sentence_opening_capital_is_not_a_name() -> None:
    """English capitalises the first word of every sentence, so the counter needs some other
    reason to believe one. `The` and `Beside` open sentences here and are not people."""
    assert opening_proper_noun_names("The door was shut. Beside it, nothing. Inside, less.") == ()


def test_emphasis_does_not_end_a_name_hunt_mid_sentence() -> None:
    """Measured on the anchor text: a scene break written `* * *` and an italicised question
    ending `?*` both left the next word looking mid-sentence, so `The` and `He` were read as
    proper nouns the book had used elsewhere. Both are markdown the prose actually carries."""
    text = "He weighed it. *What are you?* The answer came back. * * * The room was cold."
    assert opening_proper_noun_names(text) == ()


def test_a_speech_tag_does_not_become_a_surname() -> None:
    """`"Signet," Turrow said` is two things with punctuation between them. Without that
    boundary the counter reported a person called Signet Turrow."""
    names = opening_proper_noun_names('He spoke. "Signet," Turrow said. Turrow waited.')
    assert names == ("Turrow",)


def test_a_multi_word_name_is_one_name_and_a_bare_surname_folds_into_it() -> None:
    """A reader introduced to Hesk Turrow does not meet a second person when the next line
    says "Turrow said", and "Bellow and Sons" is one concern rather than two."""
    text = "He met Hesk Turrow of the Bellow and Sons concern. Turrow paid Bellow and Sons."
    assert opening_proper_noun_names(text) == ("Hesk Turrow", "Bellow and Sons")


def test_only_the_opening_is_counted() -> None:
    """The window is the measurement. A name introduced after it is a name the opening did not
    ask the reader to hold."""
    filler = " ".join(["the porters waited"] * (OPENING_WINDOW_WORDS // 3 + 5))
    assert opening_proper_noun_names(f"He waited. {filler} Then he met Marta.") == ()
    assert opening_proper_noun_names(f"He met Marta. {filler} Then he met Vance.") == ("Marta",)


def test_the_counter_is_total_and_deterministic() -> None:
    """Every counter in this module answers for any text, including empty and system-only
    input, and answers the same way twice."""
    for text in ("", "   ", "[STATUS] Silas \N{EM DASH} Loop 1 | Day 1", ANCHOR):
        first = opening_proper_nouns(text)
        assert first == opening_proper_nouns(text)
        assert isinstance(first, float)
