"""The return side of the machinery-word rail (stage-0 §178).

`tests/test_prompt_budget.py` keeps `house.MACHINERY_WORDS` out of the prompts that shape prose
a reader will read. These tests are the other direction: what comes back may not take one of
those words as a name. Serial Pilot 16 is the case that made the second half necessary — its
listing role passes the input rail and it minted *the Ladder* anyway.
"""

from __future__ import annotations

import litharness_contracts as lc
import pytest

from litharness.application import overview as overview_mod
from litharness.application import world as world_mod
from litharness.cli import EXIT_FAULT, EXIT_OK, main
from litharness.domain import house, schema_words, worlds


def _record(subject: str, predicate: str, value: object) -> lc.StateRecord:
    return worlds.world_record(subject, predicate, value=value)


def test_the_word_list_is_the_one_house_already_owns() -> None:
    """One home for the fact, and the input rail and this one cannot come to disagree.

    The repository's rule about counts is its rule about vocabulary: `house.MACHINERY_WORDS` is
    where the words live, `tests/test_prompt_budget.py` reads it for the prompts, and this
    module reads the same object for what comes back. A second list here would be §152's defect
    made on purpose.
    """
    assert schema_words.taken_as_a_name("Ladder")
    assert "ladder" in house.MACHINERY_WORDS
    for word in ("rung", "standing", "criterion"):
        assert schema_words.taken_as_a_name(word.title()) == (word,)


@pytest.mark.parametrize(
    "name",
    ["Ladder", "the Ladder", "[LADDER]", "Rung", "rungs", "standing", "Criteria"],
)
def test_a_name_that_is_one_of_our_words_is_named(name: str) -> None:
    assert schema_words.taken_as_a_name(name)


@pytest.mark.parametrize(
    "name",
    [
        "Seams standing in Ashfen",
        "the Keeping",
        "Seamwork",
        "Hold",
        "Card",
        "Share",
        "Depth",
        "Outstanding",
    ],
)
def test_an_ordinary_name_is_left_alone(name: str) -> None:
    """Identity and not containment, and the first case is why (§178).

    *"Seams standing in Ashfen"* is Serial Pilot 15's own printed column, where `standing` is an
    English participle inside a phrase and nothing has leaked. Run as containment this check
    refused it; run as identity it does not, and still catches every real one. `Outstanding` is
    the same failure one letter further in, which is why whole words are matched rather than
    substrings — the input rail matches substrings and is right to, because it reads text we
    wrote rather than a name somebody chose.
    """
    assert schema_words.taken_as_a_name(name) == ()


def test_prose_using_the_ordinary_word_is_left_alone() -> None:
    """`named_in` reads a capital, which is the only mechanical evidence of a proper noun."""
    assert schema_words.named_in("He climbed the ladder and counted the rungs.") == ()


def test_pilot_sixteens_listing_sentence_is_named() -> None:
    """The mint, verbatim, from `runs/pilots/pilot16/listing.txt`."""
    assert schema_words.named_in(
        "The message arrived on every screen at once, and nobody had asked for it. It called "
        "itself the Ladder."
    ) == ("ladder",)


def test_pilot_sixteens_title_is_named() -> None:
    """The surface the operator named: *"'Ladder' included in Title"*."""
    assert schema_words.named_in("Reading The Ladder Wrong") == ("ladder",)


@pytest.mark.parametrize(
    "title",
    [
        "The Unkillable Exploit",
        "Patch Notes For The Apocalypse",
        "What the Kettle Remembers",
        "Unlicensed Weather",
        "Copy Costs A Hand",
        "The Rainwright's Apprentice Has No Licence",
    ],
)
def test_the_titles_this_project_has_actually_drawn_are_left_alone(title: str) -> None:
    """Six of the nine titles on disk. Measured: one refusal across all nine, pilot 16's."""
    assert schema_words.named_in(title) == ()


def test_a_sentence_initial_capital_is_not_evidence() -> None:
    """Deliberately missed, and one-directional: it lets a name through, never invents one."""
    assert schema_words.named_in("Ladders are how this world counts.") == ()


def test_every_world_facing_name_shape_is_read() -> None:
    """The three record shapes that reach a page, all four of pilot 16's leaks among them."""
    records = [
        _record("ladder", "is_a", "Ladder"),
        _record("rung", "is_a", "Rung"),
        _record("theo", "is_a", "Theo Marsh"),
        _record("ladder", "graph_line", {"label": "[LADDER]", "edges": []}),
        _record(
            "ladder",
            "status_sheet",
            {"fields": [{"label": "Rung", "name": "rung"}, {"label": "Sight", "name": "sight"}]},
        ),
    ]
    complaints = schema_words.world_complaints(records)
    assert len(complaints) == 4
    assert not any("Theo Marsh" in complaint for complaint in complaints)
    assert any("[LADDER]" in complaint for complaint in complaints)
    assert any("printed column" in complaint for complaint in complaints)


def test_an_id_is_not_a_world_facing_name() -> None:
    """`ladder` was pilot 16's subject id too, and an id is a handle rather than something read.

    Refusing one would be refusing a variable name. Every id that matters carries an `is_a`
    anyway, which is why the leak is catchable without reading them.
    """
    assert schema_words.world_complaints([_record("ladder", "is_a", "the Long Count")]) == ()


def test_world_check_reports_the_names_without_moving_ok() -> None:
    """`ok` stays `validate`'s, which is `application/world.py`'s documented invariant.

    The Architect is told to run `world check` as it goes, so the complaint reaches the one
    addressee that can fix it for nothing — `world accept` is where it refuses.
    """
    payload = world_mod.check([_record("ladder", "is_a", "Ladder")])
    assert payload["machinery_names"]
    assert payload["ok"] is True


def test_a_clean_world_reports_no_names() -> None:
    payload = world_mod.check([_record("keeping", "is_a", "the Keeping")])
    assert payload["machinery_names"] == []


def test_the_title_prohibition_names_only_the_word_that_was_reached_for() -> None:
    """Not the whole of `MACHINERY_WORDS`: a menu gets recited, one prohibition does not (§138)."""
    request = overview_mod.render_title_request("a listing", machinery=("ladder",))
    assert "ladder" in request.prompt
    assert "rung" not in request.prompt


def test_the_title_prompt_is_unchanged_when_nothing_leaked() -> None:
    """Which is why the title role's ceiling in `tests/test_prompt_budget.py` does not move."""
    plain = overview_mod.render_title_request("a listing")
    assert "machinery" not in plain.prompt
    assert plain.prompt == overview_mod.render_title_request("a listing", machinery=()).prompt


# --- the same refusal through the command an Architect's operator actually runs -------------


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> None:
    """The one road to a model-free run. Setting it *is* the statement that the fake is on."""
    monkeypatch.setenv("LITHARNESS_FAKE_PAD_CHARS", "400")


def _seeded(tmp_path) -> str:  # type: ignore[no-untyped-def]
    db = tmp_path / "world.db"
    assert main(["--database", str(db), "init"]) == EXIT_OK
    assert (
        main(["--database", str(db), "listing", "--writer", "vance", "--scenes", "24"]) == EXIT_OK
    )
    return str(db)


def test_world_accept_refuses_a_system_named_out_of_our_vocabulary(fake, tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    """Serial Pilot 16's `ladder is_a Ladder`, through the command that accepted it cleanly.

    The refusal is its own branch beside `validate`'s, so the sentence that prints is about a
    name and not about a world contradicting itself.
    """
    db = _seeded(tmp_path)
    assert main(["--database", db, "world", "declare", "ladder", "is_a", "--value", "Ladder"]) == (
        EXIT_OK
    )
    capsys.readouterr()
    assert main(["--database", db, "world", "accept"]) == EXIT_FAULT
    printed = capsys.readouterr().err
    assert "machinery vocabulary" in printed
    assert "contradicts itself" not in printed


def test_force_accepts_it_anyway(fake, tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    """A person is allowed to decide a name is what the book wants — the same escape `validate`
    has, for the same reason, and there is no `world retract` to undo it with afterwards."""
    db = _seeded(tmp_path)
    assert main(["--database", db, "world", "declare", "ladder", "is_a", "--value", "Ladder"]) == (
        EXIT_OK
    )
    capsys.readouterr()
    assert main(["--database", db, "world", "accept", "--force"]) == EXIT_OK


def test_an_ordinary_system_name_accepts(fake, tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    """Pilot 15b's own name, so the gate is shown letting a real world through."""
    db = _seeded(tmp_path)
    assert main(
        ["--database", db, "world", "declare", "keeping", "is_a", "--value", "the Keeping"]
    ) == EXIT_OK
    capsys.readouterr()
    assert main(["--database", db, "world", "accept"]) == EXIT_OK
