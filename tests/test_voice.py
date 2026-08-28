"""Voice as a channel: the census that catches a demonstrated axis, and the descriptor's rails.

`plan/dossier-voice-direction.md`. Four properties are load-bearing here and, as with the Writer
record's, every one of them fails **silently** — by passing a gate, by minting an id, or by
returning a number:

1. **A registered axis cannot be registered without somebody saying whether demonstrating it is
   detectable.** The census is nearly vacuous today; the mechanism that survives that is a test
   which fails when a fourth axis appears in the naming vocabulary and in neither table.
2. **Naming an axis and carrying one are different acts.** A text that says *avoid em dashes*
   and a text written with them are caught by different functions, and conflating them is how
   the exhibition rule came to live inside a function called `prose_axes_named`.
3. **A descriptor carries numbers, closed labels, and no way back to a corpus.** RS1 has to hold
   by the shape of the record rather than by the care of whoever fills it in.
4. **One statistic, one implementation.** The market side and our side compute the same numbers
   or the descriptor is a target nothing can be read against.
"""

from __future__ import annotations

import math
from dataclasses import fields as dataclass_fields

import pytest

from litharness.domain import voice, writers
from litharness.domain.directors import (
    _CRAFT_INSTRUCTION,
    IllegalBrief,
    legal_brief,
    prose_axes_named,
)

# --------------------------------------------------------------- the registered-axis census


def test_every_registered_axis_is_placed() -> None:
    """A fourth registered axis must land in one of the two tables, and the suite says so.

    **This is the property the census is actually for.** `EXHIBITION_MARKERS` holds one mark
    today and `axes_exhibited` therefore catches one thing, which on its own would be a rule
    that reads as thorough and does nothing. What makes it load-bearing is that an axis added to
    `directors._CRAFT_INSTRUCTION` and to neither table fails here — so registering an axis
    forces a decision about whether a text can demonstrate it, at the moment the axis is
    registered rather than after a dossier has been riding one for a book.
    """
    placed = set(voice.EXHIBITION_MARKERS) | set(voice.UNMARKED_AXES)
    registered = set(_CRAFT_INSTRUCTION)
    assert registered - placed == set(), (
        "a registered prose axis is in neither voice.EXHIBITION_MARKERS nor voice.UNMARKED_AXES: "
        f"{sorted(registered - placed)}. Say whether a text can demonstrate it, and if no "
        "mechanical mark exists say that instead of inventing one"
    )
    assert placed - registered == set(), (
        "voice names an axis the naming vocabulary does not register: "
        f"{sorted(placed - registered)}"
    )


def test_no_axis_is_in_both_tables() -> None:
    """An axis with a mark and an excuse for having none is a table nobody can read."""
    assert not set(voice.EXHIBITION_MARKERS) & set(voice.UNMARKED_AXES)


def test_naming_an_axis_and_carrying_it_are_different_acts() -> None:
    """The split this module exists to make, in one assertion each way.

    Written as two texts that each trip exactly one of the two detectors: an instruction about
    the mark that contains no mark, and a mark with no instruction anywhere near it.
    """
    instruction = "Nothing here about punctuation, and no em dash anywhere."
    carried = "You write the hour the rules become visible, the first build — and it works."

    assert "em_dash" in prose_axes_named(instruction)
    assert voice.axes_exhibited(instruction) == ()

    assert voice.axes_exhibited(carried) == ("em_dash",)


def test_the_census_counts_rather_than_complains() -> None:
    """`exhibition_census` reports a number for every axis, including zero.

    A census that omitted the zeroes would make "this dossier was checked" and "this axis has no
    mark" look the same in a payload, which is `roster.check`'s own reason for reporting the
    markers a dossier lacks rather than only the ones it carries.
    """
    census = voice.exhibition_census("a — b — c")
    assert census == {"em_dash": 2}
    assert set(census) == set(voice.EXHIBITION_MARKERS)
    assert voice.exhibition_census("no marks here") == {"em_dash": 0}


def test_every_shipped_dossier_carries_no_registered_mark() -> None:
    """The fourteen compiled dossiers pass the census, so adding it as a gate refuses nobody.

    Stated as a test rather than as a claim in a decision entry, because "this would refuse a
    shipped fixture" is the objection that has retired two counters in this repository already
    (`roster.machinery_words` records one over `writers.BUILTIN["volcanology"]`).
    """
    for pool in (writers.CAST, writers.BUILTIN):
        for writer in pool.values():
            assert voice.axes_exhibited(writer.dossier) == (), writer.name


# ------------------------------------------------------------------------------ the exemplar


def test_an_exemplar_addresses_the_same_after_a_windows_checkout() -> None:
    """`core.autocrlf` is global on this box, so a digest over raw bytes is a latent break."""
    assert voice.exemplar_digest_for("one line\r\nand another") == voice.exemplar_digest_for(
        "one line\nand another"
    )


def test_an_empty_exemplar_is_refused() -> None:
    """A digest over whitespace is a writer minted from a draw that returned nothing."""
    with pytest.raises(ValueError):
        voice.exemplar_digest_for("   \n  ")


def test_populating_an_exemplar_mints_a_new_writer() -> None:
    """`plan/writer-roster.md` §3.1's whole reason for the socket, exercised end to end.

    Editing a dossier already mints a new writer; this is the other half — the same dossier with
    an exemplar behind it is a different writer, so a voice-rewritten recruit can never overwrite
    the house-voiced one it was drawn from.
    """
    dossier = "You write the kind of serial where the rules become visible all at once."
    before = writers.writer_id_for(name="x", dossier=dossier, interests=("a",))
    after = writers.writer_id_for(
        name="x",
        dossier=dossier,
        interests=("a",),
        exemplar_digest=voice.exemplar_digest_for("The message reached every screen at once."),
    )
    assert before != after


# ---------------------------------------------------------------------------- the descriptor


def _descriptor(**overrides: object) -> voice.StyleDescriptor:
    base: dict[str, object] = {
        "sentence_words_mean": 12.0,
        "sentence_words_sd": 5.0,
        "sentence_words_p10": 4.0,
        "sentence_words_p50": 11.0,
        "sentence_words_p90": 22.0,
        "paragraph_sentences_mean": 3.0,
        "connective_density": 6.5,
        "person": voice.Person.THIRD,
        "tense": voice.Tense.PAST,
    }
    base.update(overrides)
    return voice.StyleDescriptor(**base)  # type: ignore[arg-type]


def test_a_descriptor_carries_no_free_text() -> None:
    """Numbers and closed labels, structurally: there is nowhere for a phrase to ride.

    The rail is *measurement independence*, not copyright — `plan/dossier-voice-direction.md` §1
    carries the operator's correction on that point. A descriptor with one free-text field is a
    field somebody eventually pastes a sentence of market prose into, and the corpus-leak audit
    is a check on committed blobs rather than on what a running process assembles.
    """
    for field_ in dataclass_fields(voice.StyleDescriptor):
        assert field_.type in {"float", "Person", "Tense"}, field_.name


def test_a_descriptor_carries_no_corpus_identifier() -> None:
    """No shard, no story id, no cohort name: RS1 by the shape of the record.

    The map from a descriptor back to what it was distilled from lives on the measurement side,
    which is the side allowed to know. `descriptor_id_for` addresses the numbers alone, so the
    id cannot smuggle the provenance the fields refuse.
    """
    names = {field_.name for field_ in dataclass_fields(voice.StyleDescriptor)}
    for forbidden in ("corpus", "shard", "story", "cohort", "source", "book", "author", "url"):
        assert not any(forbidden in name for name in names), forbidden


def test_a_descriptor_carries_no_registered_axis_statistic() -> None:
    """The rail that keeps the crossing legal, and it is the sharpest edge in this file.

    A descriptor is a prose-craft statement by construction: sentence length and fragment rate
    are what `directors._PROSE_STYLE` refuses in a brief. What makes it legal is where it is
    allowed to land — it aims one draw and never enters a dossier. A descriptor carrying a
    *registered measured axis*' own statistic would break that, because the number would aim the
    draw, the draw would demonstrate the axis, and the rewritten dossier would carry it into
    every scene call. That is the em-dash loop being answered by the output of its own
    instrument.
    """
    names = {field_.name for field_ in dataclass_fields(voice.StyleDescriptor)}
    assert set(voice.REFUSED_DESCRIPTOR_STATISTICS) == set(_CRAFT_INSTRUCTION)
    for axis in voice.REFUSED_DESCRIPTOR_STATISTICS:
        assert not any(axis in name for name in names), axis
    for forbidden in ("dash", "punctuation", "interior", "stat", "status"):
        assert not any(forbidden in name for name in names), forbidden


def test_two_agreeing_distillations_address_the_same_descriptor() -> None:
    assert _descriptor().descriptor_id == _descriptor().descriptor_id


def test_moving_one_number_mints_a_different_descriptor() -> None:
    """A descriptor is content-addressed for `director_id_for`'s reason: it aims a paid draw, and
    "which descriptor aimed this writer" has to stay answerable after somebody re-distils."""
    assert _descriptor().descriptor_id != _descriptor(connective_density=6.6).descriptor_id


def test_a_descriptor_id_is_stable_across_a_label_change() -> None:
    """Only in the sense that it must not be: person is addressed material like everything else."""
    assert (
        _descriptor(person=voice.Person.FIRST).descriptor_id
        != _descriptor(person=voice.Person.THIRD).descriptor_id
    )


def test_a_distillation_that_found_nothing_cannot_call_itself_a_voice() -> None:
    """NaN is what an empty distillation returns from a mean, and it addresses like any float."""
    with pytest.raises(voice.MalformedDescriptor):
        _descriptor(sentence_words_mean=math.nan)


def test_a_negative_statistic_is_refused() -> None:
    with pytest.raises(voice.MalformedDescriptor):
        _descriptor(connective_density=-1.0)


def test_the_descriptor_holds_no_statistic_a_word_list_would_be_needed_for() -> None:
    """A fragment rate was a field here and this suite deleted it, cause recorded in place.

    The detector approximated a finite verb as the closed auxiliaries plus `\\w+ed` and `\\w+s`
    and called *"The floor gave way beneath him"* a fragment — an irregular past tense is
    neither auxiliary nor regular. The only fix was a verb list, which is §127's shape, and a
    field named `fragment_rate` that is not a fragment rate is the lying column
    `migrations/036`'s header names. This test is the deletion's receipt: the statistic does not
    come back without somebody deleting the test that says it left.
    """
    names = {field_.name for field_ in dataclass_fields(voice.StyleDescriptor)}
    assert "fragment_rate" not in names
    assert "_FINITE" not in voice.__dict__


def test_reversed_quantiles_are_refused() -> None:
    with pytest.raises(voice.MalformedDescriptor):
        _descriptor(
            sentence_words_p10=22.0, sentence_words_p50=11.0, sentence_words_p90=4.0
        )


# --------------------------------------------------------------------------- the arithmetic


def test_distill_reads_the_text_it_is_handed() -> None:
    """One passage with numbers a person can check by counting, so the statistic is legible.

    Three sentences of five, two and ten words; one connective (`and`) in seventeen words.
    Nearest-rank quantiles over three values put p10 on the shortest and p90 on the longest, so
    p50 is the middle sentence's length exactly and no interpolation scheme has to be agreed
    between two implementations.
    """
    descriptor = voice.distill(
        ["The ship smelled of diesel. Nobody spoke. He counted the tags again and wrote the "
         "number down."],
        person=voice.Person.THIRD,
        tense=voice.Tense.PAST,
    )
    assert descriptor.sentence_words_p10 == 2.0
    assert descriptor.sentence_words_p50 == 5.0
    assert descriptor.sentence_words_p90 == 10.0
    assert descriptor.sentence_words_mean == pytest.approx(17.0 / 3.0)
    assert descriptor.connective_density == pytest.approx(100.0 / 17.0)


def test_distill_refuses_a_voice_with_no_sentences() -> None:
    with pytest.raises(voice.MalformedDescriptor):
        voice.distill([""], person=voice.Person.THIRD, tense=voice.Tense.PAST)


def test_paragraphs_split_on_a_blank_line_and_fall_back_to_one() -> None:
    assert len(voice.paragraphs("a b.\n\nc d.")) == 2
    assert len(voice.paragraphs("a b.\nc d.")) == 2
    assert len(voice.paragraphs("a b. c d.")) == 1


def test_the_same_statistic_has_one_implementation() -> None:
    """The market side and our side call `voice.distill`, and nothing else computes these.

    Asserted as a repository property rather than argued in a docstring, because *a second home*
    is the defect shape this project keeps finding — `statistics.fmean` over sentence lengths
    written twice is two voices that disagree by a rounding rule.

    **Both sides, and the marker is the computation rather than the constructor**, which is this
    test's own correction twice over. It scanned the package alone, so it could never have seen
    the measurement side it makes a claim about; and it matched `sentence_words_mean=` anywhere,
    which is also how a caller writes a literal — `cli._SPECIMEN_DESCRIPTOR` tripped it while
    computing nothing. What a second implementation looks like is a statistic derived from text
    at the point of construction, so that is what is matched.

    `voice_descriptors.serial_descriptors` builds a descriptor from `statistics.median` over
    *descriptors already distilled by this module* and is an aggregation rather than a second
    distillation, which is why the marker names the function this module uses and not every use
    of `statistics`.
    """
    from pathlib import Path

    repo = Path(voice.__file__).resolve().parents[3]
    roots = (repo / "src" / "litharness", repo / "research" / "quality-measurement")
    offenders = [
        path.relative_to(repo).as_posix()
        for root in roots
        if root.exists()
        for path in root.rglob("*.py")
        if path.name != "voice.py"
        and "sentence_words_mean=statistics." in path.read_text(encoding="utf-8")
    ]
    assert not offenders, f"a second distillation lives in {offenders}"


# --------------------------------------------------------- the split, and what it did not change


def test_the_em_dash_refusal_survived_its_own_split() -> None:
    """**The refactor's whole obligation: every text refused before is refused after.**

    The bare mark used to be the last alternative of `directors._CRAFT_INSTRUCTION["em_dash"]`,
    so `legal_brief` and `legal_dossier` refused a carried mark through the *naming* pattern.
    Moving it to `voice.EXHIBITION_MARKERS` is a relocation and not a widening, and a relocation
    that dropped a refusal on the way would be the worst possible outcome — the guard would read
    as intact and the four dossiers it once refused would mint.

    Both gates and both directions, in one place, so a later edit to either cannot quietly take
    the mark out of only one of them.
    """
    carried = "You write the hour the rules become visible — and somebody notices."
    with pytest.raises(writers.IllegalDossier):
        writers.legal_dossier(carried)
    with pytest.raises(IllegalBrief):
        legal_brief(carried)

    # And the naming half is untouched: an instruction about the mark still refuses without one.
    with pytest.raises(writers.IllegalDossier):
        writers.legal_dossier("You write about tides. Nothing about punctuation.")
    with pytest.raises(IllegalBrief):
        legal_brief("A book about tides. Nothing about punctuation.")


def test_the_mark_now_refuses_under_the_reason_that_is_true() -> None:
    """An agent told a dossier *named* an axis it never mentioned learns the wrong rule.

    That is the whole cost the split pays for, and it is small and real: the recruiter reads
    `roster check --dossier` and the roster vocabulary already explains the em dash as a
    demonstration rather than as a statement, so the payload disagreed with the documentation.
    """
    with pytest.raises(writers.IllegalDossier, match="carries the mark"):
        writers.legal_dossier("You write tides — and what they take.")
    with pytest.raises(writers.IllegalDossier, match="names the registered"):
        writers.legal_dossier("You write tides. Say nothing of punctuation.")


def test_no_shipped_writer_stopped_being_legal() -> None:
    """The fourteen compiled dossiers pass both halves of the gate after the move."""
    for pool in (writers.CAST, writers.BUILTIN):
        for writer in pool.values():
            writers.legal_dossier(writer.dossier)


# ------------------------------------------------ what an adversarial review found uncovered


def test_the_median_does_not_move_with_the_parity_of_the_sentence_count() -> None:
    """**The defect an adversarial review found, pinned so it cannot come back.**

    `_quantile` used `round`, which is half-to-even *on the index*, and `share * (len - 1)` is an
    exact `.5` for `share=0.50` at every even count. So `p50` alternated between the lower-middle
    and the upper-middle rank with the count's parity: on a passage of alternating two-word and
    ten-word sentences it returned 10.0 at four sentences and 2.0 at six, which is two aims and
    two descriptor ids for one voice. The tie rule is now named and the estimator is stable.
    """
    short, long_ = "aa bb.", "cc cc cc cc cc cc cc cc cc cc."
    seen = set()
    for pairs in range(1, 8):
        passage = " ".join([short] * pairs + [long_] * pairs)
        seen.add(
            voice.distill(
                [passage], person=voice.Person.THIRD, tense=voice.Tense.PAST
            ).sentence_words_p50
        )
    assert len(seen) == 1, f"p50 moved with the sentence count: {sorted(seen)}"


def test_the_quantile_tie_goes_to_the_higher_rank() -> None:
    """The convention the docstring now names, asserted so a second implementation has a target."""
    assert voice._quantile([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], 0.10) == 2.0
    assert voice._quantile([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], 0.50) == 4.0
    assert voice._quantile([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], 0.90) == 6.0


def test_a_descriptor_addresses_what_a_model_was_shown() -> None:
    """`as_labels` renders to two decimals and the address is taken over that, on purpose.

    Two descriptors that render identically *are* the same descriptor for every purpose here —
    they aim the same draw — and addressing the raw floats would mint a second id for a
    difference in the seventh decimal that no prompt can express. Uncovered until an adversarial
    review pointed out that addressing the raw floats passed every id test in this file.
    """
    coarse = _descriptor(connective_density=6.5)
    finer = _descriptor(connective_density=6.5004)
    assert coarse.as_labels() == finer.as_labels()
    assert coarse.descriptor_id == finer.descriptor_id
    assert _descriptor(connective_density=6.51).descriptor_id != coarse.descriptor_id


def test_the_spread_and_the_paragraph_shape_are_read_from_the_text() -> None:
    """Two fields nothing asserted from an actual distillation, so nothing would have caught a
    constant returned in their place."""
    flat = voice.distill(
        ["aa bb cc. dd ee ff. gg hh ii."], person=voice.Person.THIRD, tense=voice.Tense.PAST
    )
    varied = voice.distill(
        ["aa. bb cc dd ee ff gg hh ii jj kk. ll mm."],
        person=voice.Person.THIRD,
        tense=voice.Tense.PAST,
    )
    assert flat.sentence_words_sd == 0.0
    assert varied.sentence_words_sd > 3.0

    assert flat.paragraph_sentences_mean == 3.0
    two_blocks = voice.distill(
        ["aa bb. cc dd.\n\nee ff. gg hh. ii jj. kk ll."],
        person=voice.Person.THIRD,
        tense=voice.Tense.PAST,
    )
    assert two_blocks.paragraph_sentences_mean == 3.0


def test_person_is_read_from_pronouns_rather_than_asserted() -> None:
    first = "I went down. I counted them. My hands were shaking."
    third = "He went down. He counted them. His hands shook."
    assert voice.person_of(first) is voice.Person.FIRST
    assert voice.person_of(third) is voice.Person.THIRD
    assert voice.person_of("I went down and he counted them.") is voice.Person.MIXED
    assert voice.person_of("The lift stopped between floors.") is voice.Person.MIXED
