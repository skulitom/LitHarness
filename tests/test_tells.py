"""The regular tells: found by code, held to the shelf's own rate, and never judged.

The fixtures are sentences the operator named in reads 15 to 19 (`plan/reader-read-19.md`
§2.2); they are test data and reach no prompt (§97.1). No model call, no store, no corpus.
"""

from __future__ import annotations

from litharness.domain import tells

NAMED = {
    tells.ABSENCE: (
        "He stocked shelves on the night shift and mapped the storm drains for a hobby nobody "
        "understood."
    ),
    tells.PARADOX: (
        "He said it gentler now, which was his way of taking it back without taking it back."
    ),
    tells.THE_WAY: "Tull stopped anyway and looked, the way he always stopped and looked.",
    tells.CHAINED_AND: (
        "I had one resit left, sports science, and I kept not sitting it, and she kept telling "
        "her sister I'd graduated, and that's about the size of me."
    ),
}

PLAIN = (
    "Ryan drove because Nick was still shaking. The plate came up with the bar. He went down "
    "the rungs and the run was low for the first forty feet."
)


def test_each_named_family_is_found_on_the_sentence_the_operator_named() -> None:
    for family, sentence in NAMED.items():
        found = {item.family for item in tells.locate(sentence)}
        assert family in found, (family, found)


def test_the_echo_is_a_phrase_repeated_inside_one_sentence() -> None:
    found = {item.family for item in tells.locate(NAMED[tells.THE_WAY])}
    assert tells.ECHO in found, "stopped and looked ... stopped and looked"
    assert tells.ECHO not in {item.family for item in tells.locate(PLAIN)}


def test_the_contrast_form_of_the_paradox_is_found() -> None:
    assert tells.PARADOX in {item.family for item in tells.locate("Not a pause, a stop.")}
    assert tells.PARADOX in {
        item.family for item in tells.locate("That's not a name, that's a shelf.")
    }


def test_plain_prose_carries_none_of_them() -> None:
    assert tells.locate(PLAIN) == ()
    assert all(rate == 0.0 for rate in tells.density(PLAIN).values())


def test_a_machine_line_is_never_counted() -> None:
    text = (
        "[STATUS] Eddie — CLICK 1 | GROUND HELD 0 | HOLLOWS SURVEYED 0/4118\n\n"
        "NO CLASS. GROUND. NOTHING WAS ISSUED.\n\n"
        "He read it twice."
    )
    assert tells.locate(text) == ()
    assert tells.word_count(text) == 4


def test_density_is_per_thousand_counted_words_and_ceilings_are_the_shelf_s_highest() -> None:
    page = "\n\n".join([NAMED[tells.ABSENCE], PLAIN])
    words = tells.word_count(page)
    assert tells.density(page)[tells.ABSENCE] == 1000.0 / words
    shelf = [PLAIN, page, PLAIN]
    limits = tells.ceilings(shelf)
    assert limits is not None
    assert limits[tells.ABSENCE] == 1000.0 / words
    assert limits[tells.THE_WAY] == 0.0
    assert tells.ceilings([]) is None
    assert tells.ceilings(["", "  "]) is None


def test_over_names_only_the_families_past_the_shelf_and_nothing_with_no_shelf() -> None:
    page = "\n\n".join(NAMED.values())
    assert tells.over(page, None) == ()
    # Every family: the paradox and the located habit both carry an echo as well.
    assert set(tells.over(page, dict.fromkeys(tells.FAMILIES, 0.0))) == set(tells.FAMILIES)
    generous = dict.fromkeys(tells.FAMILIES, 1000.0)
    assert tells.over(page, generous) == ()


def test_a_located_sentence_is_replaced_where_it_was_and_the_rest_is_untouched() -> None:
    text = f"{PLAIN}\n\n{NAMED[tells.ABSENCE]} It was late."
    located = next(item for item in tells.locate(text) if item.family == tells.ABSENCE)
    assert located.paragraph == 1 and located.sentence == 0
    replaced = tells.replace_sentence(text, located, "He mapped the storm drains for a hobby.")
    assert replaced == f"{PLAIN}\n\nHe mapped the storm drains for a hobby. It was late."
    stale = tells.Located(tells.ABSENCE, 1, 0, "not the sentence that is there")
    assert tells.replace_sentence(text, stale, "anything") == text
