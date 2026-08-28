"""`litharness revoice` as an operator meets it, and the exemplar store underneath it.

A separate file from `tests/test_revoice.py` for `tests/test_roster_cli.py`'s reason: that file
asserts the two prompts and the gates, and this one asserts the interface and the storage. The
split matters here because **every refusal below happens before the first paid call**. A command
that spends and then discovers the operator's flags were wrong has spent; the tests that matter
most are the ones proving it does not get that far.

Three properties, and each fails silently in this subsystem's usual way:

1. **A stored passage always addresses itself.** The digest is addressed material in a writer id,
   so a row whose passage and digest disagree makes "which passage minted this writer" answerable
   two ways.
2. **The parent is never edited.** Content addressing makes that structural; a test says so
   because "nothing was mutated" is invisible in a diff of one command's output.
3. **Nothing spends before the flags are settled.** `LITHARNESS_ENV=test` means the registry
   refuses every billing provider, so a call that got as far as the transport would raise here
   rather than charge — which is what makes these assertions cheap and also what makes them
   necessary, since in production it would not.
"""

from __future__ import annotations

import pytest

from litharness.adapters.sqlite_errors import IntegrityFailure
from litharness.adapters.sqlite_store import SqliteStore
from litharness.cli import EXIT_FAULT, build_parser, main
from litharness.domain import voice, writers

DESCRIPTOR = voice.StyleDescriptor(
    sentence_words_mean=13.0,
    sentence_words_sd=7.0,
    sentence_words_p10=4.0,
    sentence_words_p50=11.0,
    sentence_words_p90=24.0,
    paragraph_sentences_mean=3.0,
    connective_density=6.0,
    person=voice.Person.THIRD,
    tense=voice.Tense.PAST,
)

PASSAGE = (
    "The lift stopped between floors and the dust came down in a sheet. Somebody two decks up "
    "was shouting a number, over and over, and the number kept going up."
)

LEGAL = (
    "You write the kind of fantasy where the stakes are a bakery, a bad harvest and "
    "somebody's estranged aunt. What you love is competence at low volume. You want a "
    "reader to close a chapter feeling like they could stay."
)


@pytest.fixture
def db(tmp_path):
    return tmp_path / "roster.db"


@pytest.fixture
def store(tmp_path):
    with SqliteStore.open(tmp_path / "voice.db") as opened:
        yield opened


def _descriptor_file(tmp_path, descriptor: voice.StyleDescriptor = DESCRIPTOR):
    import json

    path = tmp_path / "descriptor.json"
    payload = {
        name: getattr(descriptor, name)
        for name in (
            "sentence_words_mean",
            "sentence_words_sd",
            "sentence_words_p10",
            "sentence_words_p50",
            "sentence_words_p90",
            "paragraph_sentences_mean",
            "connective_density",
        )
    }
    payload["person"] = str(descriptor.person)
    payload["tense"] = str(descriptor.tense)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


# ------------------------------------------------------------------------- the exemplar store


def test_a_stored_passage_addresses_itself(store) -> None:
    digest = store.record_exemplar(
        passage=PASSAGE,
        drawn_by="wtr-parent",
        descriptor=DESCRIPTOR,
        profile="revoice.exemplar.v0",
        drawn_at="2026-08-28T00:00:00Z",
    )
    assert digest == voice.exemplar_digest_for(PASSAGE)
    kept = store.exemplar(digest)
    assert kept is not None
    assert kept["passage"] == PASSAGE
    assert kept["descriptor_id"] == DESCRIPTOR.descriptor_id
    assert kept["drawn_by"] == "wtr-parent"


def test_recording_one_passage_twice_converges(store) -> None:
    """A second draw that happened to return byte-identical prose is one row, not two.

    And it does not rewrite the descriptor that aimed the first, which is why the insert ignores
    rather than replaces: the row records what actually aimed the passage that exists.
    """
    common = {
        "passage": PASSAGE,
        "drawn_by": "wtr-parent",
        "profile": "p",
        "drawn_at": "2026-08-28T00:00:00Z",
    }
    first = store.record_exemplar(descriptor=DESCRIPTOR, **common)
    fields = {
        name: getattr(DESCRIPTOR, name) for name in DESCRIPTOR.__dataclass_fields__
    }
    other = voice.StyleDescriptor(**{**fields, "connective_density": 9.0})
    second = store.record_exemplar(descriptor=other, **common)
    assert first == second
    kept = store.exemplar(first)
    assert kept is not None
    assert kept["descriptor_id"] == DESCRIPTOR.descriptor_id


def test_a_passage_edited_underneath_the_table_is_found_on_read(store) -> None:
    """The one way a row here can go wrong, and it is found by whoever next asks what minted a
    writer rather than by whoever made the edit."""
    digest = store.record_exemplar(
        passage=PASSAGE,
        drawn_by="wtr-parent",
        descriptor=DESCRIPTOR,
        profile="p",
        drawn_at="2026-08-28T00:00:00Z",
    )
    store._connection.execute(
        "UPDATE voice_exemplars SET passage = ? WHERE exemplar_digest = ?",
        ("Something else entirely.", digest),
    )
    with pytest.raises(IntegrityFailure, match="does not address its own passage"):
        store.exemplar(digest)


def test_an_unknown_digest_is_none_rather_than_a_raise(store) -> None:
    assert store.exemplar("exm-" + "0" * 64) is None


def test_passages_are_listed_by_when_they_were_drawn_and_never_ranked(store) -> None:
    for index, passage in enumerate((PASSAGE, PASSAGE + " And then it stopped.")):
        store.record_exemplar(
            passage=passage,
            drawn_by="wtr-parent",
            descriptor=DESCRIPTOR,
            profile="p",
            drawn_at=f"2026-08-28T0{index}:00:00Z",
        )
    drawn = store.exemplars_drawn_by("wtr-parent")
    assert [row["drawn_at"] for row in drawn] == [
        "2026-08-28T00:00:00Z",
        "2026-08-28T01:00:00Z",
    ]
    assert store.exemplars_drawn_by("wtr-nobody") == []


# ---------------------------------------------------------------------------- the command line


def test_the_command_takes_no_exemplar_flag() -> None:
    """The socket is filled by a draw and never by a paste, which is the rail
    `test_the_exemplar_socket_is_not_reachable_from_the_recruiter_path` has held since §146 and
    which this command had to be designed around rather than through.

    An operator who could hand in a passage could hand in somebody else's, and the most-repeated
    text in the system is the wrong place to find out that they did.
    """
    parser = build_parser()
    flags = {
        option
        for action in parser._subparsers._group_actions[0].choices["revoice"]._actions
        for option in action.option_strings
    }
    assert "--exemplar" not in flags
    assert "--descriptor" in flags


def test_a_missing_descriptor_is_refused_before_anything_opens(db, capsys) -> None:
    """And before a store exists: `SqliteStore.open` creates and migrates a file, so a command
    that validated its flags after opening one would leave a database behind for a typo."""
    assert main(["--database", str(db), "init"]) == 0
    capsys.readouterr()
    code = main(
        [
            "--database",
            str(db),
            "revoice",
            "--writer",
            "ferreira",
            "--descriptor",
            str(db.parent / "nothing.json"),
        ]
    )
    assert code == EXIT_FAULT
    assert "nothing.json" in capsys.readouterr().err


def test_a_descriptor_that_is_not_one_names_what_is_wrong(tmp_path, db) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text('{"sentence_words_mean": 3.0}', encoding="utf-8")
    with pytest.raises(SystemExit, match="not a usable descriptor"):
        main(
            [
                "--database",
                str(db),
                "revoice",
                "--writer",
                "ferreira",
                "--descriptor",
                str(broken),
            ]
        )


def test_a_compiled_cast_writer_cannot_be_re_minted_under_its_own_name(
    tmp_path, db, capsys
) -> None:
    """`refuse_reserved_name` protects the controls the roster is read against, and the refusal
    arrives before the draw rather than after it.

    The message has to say *what to do*, because an operator who reads only "reserved" concludes
    the command does not work on the cast at all, and it does: it needs a name of its own.
    """
    assert main(["--database", str(db), "init"]) == 0
    capsys.readouterr()
    code = main(
        [
            "--database",
            str(db),
            "revoice",
            "--writer",
            "ferreira",
            "--descriptor",
            str(_descriptor_file(tmp_path)),
        ]
    )
    assert code == EXIT_FAULT
    err = capsys.readouterr().err
    assert "compiled writer's name" in err
    assert "--name" in err


def test_a_cast_writer_with_a_fresh_name_still_needs_a_shelf_and_a_form(
    tmp_path, db, capsys
) -> None:
    """A compiled writer carries neither, and an unlabelled row drops out of §146's registered
    arm with nothing saying so."""
    assert main(["--database", str(db), "init"]) == 0
    capsys.readouterr()
    code = main(
        [
            "--database",
            str(db),
            "revoice",
            "--writer",
            "ferreira",
            "--name",
            "ferreira-voiced",
            "--descriptor",
            str(_descriptor_file(tmp_path)),
        ]
    )
    assert code == EXIT_FAULT
    assert "--specialization and --shape" in capsys.readouterr().err


def test_an_unknown_writer_is_refused_by_name(tmp_path, db, capsys) -> None:
    assert main(["--database", str(db), "init"]) == 0
    capsys.readouterr()
    code = main(
        [
            "--database",
            str(db),
            "revoice",
            "--writer",
            "nobody",
            "--descriptor",
            str(_descriptor_file(tmp_path)),
        ]
    )
    assert code == EXIT_FAULT
    assert "nobody" in capsys.readouterr().err


def test_a_proposed_writer_cannot_be_revoiced(tmp_path, db, capsys) -> None:
    """`_resolve_writer`'s rail reaches this command unchanged: a proposal is not castable, and
    drawing as one would be drafting with a writer nobody admitted."""
    assert main(["--database", str(db), "init"]) == 0
    assert (
        main(
            [
                "--database",
                str(db),
                "roster",
                "declare",
                "okafor",
                "--dossier",
                LEGAL,
                "--specialization",
                "cozy-fantasy",
                "--shape",
                "single-image",
            ]
        )
        == 0
    )
    capsys.readouterr()
    code = main(
        [
            "--database",
            str(db),
            "revoice",
            "--writer",
            "okafor",
            "--descriptor",
            str(_descriptor_file(tmp_path)),
        ]
    )
    assert code == EXIT_FAULT
    assert "proposed but not accepted" in capsys.readouterr().err


def test_a_re_mint_would_be_a_new_writer_rather_than_an_edit() -> None:
    """The anti-scope of `plan/dossier-voice-direction.md`, as arithmetic rather than as care.

    Asserted on the addressing rather than through the command, because the command's own proof
    costs two paid calls: a child carrying an exemplar digest cannot collide with its parent,
    whatever the rewrite returned, because the digest is in the address.
    """
    parent = writers.CAST["ferreira"]
    child = writers.build(
        "ferreira-voiced",
        parent.dossier,
        interests=parent.interests,
        exemplar_digest=voice.exemplar_digest_for(PASSAGE),
    )
    assert child.writer_id != parent.writer_id
    same_words = writers.build(
        "ferreira-voiced", parent.dossier, interests=parent.interests
    )
    assert child.writer_id != same_words.writer_id
