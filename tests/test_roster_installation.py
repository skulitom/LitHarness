"""The roster reaches a fresh book database: `--roster-database` and its environment half.

Serial pilot 13 measured the gap this closes, for free: a writer accepted in the roster store
could not be cast on a fresh book database — `listing --writer <name>` exited 2 with "no writer
named" — because `--writer` resolved through whatever `--database` was open while the parser
comment claimed a roster belongs to the installation. The interim bridge was cloning the whole
store through `litharness backup`, which drags every unrelated table along and forks the roster.

The sanctioned bridge is resolution, not copying, and the tests here hold both halves of that
choice: an accepted writer reaches any book database through the configured roster, and nothing
about acceptance, refusal or provenance moved — the decision rows stay in the one store beside
the writers they admitted. Stage-0 §151 records why export/import was refused.
"""

from __future__ import annotations

import json

import pytest

from litharness import cli
from litharness.adapters.sqlite_store import SqliteStore
from litharness.cli import EXIT_FAULT, EXIT_OK, main

LEGAL = (
    "You write the kind of fantasy where the stakes are a bakery, a bad harvest and "
    "somebody's estranged aunt. What you love is competence at low volume. You want a "
    "reader to close a chapter feeling like they could stay."
)


@pytest.fixture
def roster(tmp_path):
    return tmp_path / "roster.db"


@pytest.fixture
def book(tmp_path):
    return tmp_path / "book.db"


def staff(roster, name: str = "okafor") -> None:
    assert (
        main(
            [
                "--database", str(roster), "roster", "declare", name,
                "--dossier", LEGAL,
                "--specialization", "cozy-fantasy",
                "--shape", "several-no-beat",
                "--interest", "cozy fantasy",
            ]
        )
        == EXIT_OK
    )
    assert main(["--database", str(roster), "roster", "accept", name]) == EXIT_OK


def test_the_gap_pilot_13_hit_is_real_without_a_configured_roster(
    roster, book, capsys
) -> None:
    """The measured half of stage-0 §151, re-measured here so it cannot silently return: an
    accepted writer, a fresh book database, no configuration — and the cast is all there is."""
    staff(roster)
    assert main(["--database", str(book), "init"]) == EXIT_OK
    capsys.readouterr()
    assert main(["--database", str(book), "listing", "--writer", "okafor"]) == EXIT_FAULT
    err = capsys.readouterr().err
    assert "no writer named 'okafor'" in err
    assert "the cast is" in err


def test_an_accepted_writer_reaches_a_fresh_book_database_through_the_flag(
    roster, book, capsys
) -> None:
    """The bridge itself, on the exact prompt path a book run takes — and the book database is
    not even created by the lookup, which is what "resolution, not copying" buys."""
    staff(roster)
    capsys.readouterr()
    assert (
        main(
            [
                "--database", str(book), "--roster-database", str(roster),
                "prompts", "--writer", "okafor", "--role", "listing", "--json",
            ]
        )
        == EXIT_OK
    )
    assert "estranged aunt" in json.loads(capsys.readouterr().out)["system"]
    assert not book.exists()


def test_the_environment_variable_carries_the_roster_home(
    roster, book, capsys, monkeypatch
) -> None:
    """`DATABASE_ENV`'s argument, one door over: a cron entry and an agent allowance inherit an
    environment rather than a flag."""
    staff(roster)
    monkeypatch.setenv(cli.ROSTER_DATABASE_ENV, str(roster))
    capsys.readouterr()
    assert (
        main(
            ["--database", str(book), "prompts", "--writer", "okafor", "--role", "listing",
             "--json"]
        )
        == EXIT_OK
    )
    assert "estranged aunt" in json.loads(capsys.readouterr().out)["system"]


def test_a_configured_roster_replaces_the_open_databases_roster(
    roster, book, capsys
) -> None:
    """One source of truth, not two consulted in order. A book database holding its own stale
    accepted row must not shadow the installation's answer — a refusal is terminal (§149), and
    a shadowing copy is exactly how one would quietly stop having happened."""
    staff(book)  # the legacy per-database shape: the book file holds its own roster
    capsys.readouterr()
    assert (
        main(
            [
                "--database", str(book), "--roster-database", str(roster),
                "listing", "--writer", "okafor",
            ]
        )
        == EXIT_FAULT
    )
    assert "no writer named 'okafor'" in capsys.readouterr().err


def test_a_refusal_in_the_installation_roster_holds_on_every_book_database(
    roster, book, capsys
) -> None:
    """The property that killed export/import: refuse a writer once and no book database keeps
    a copy that still drafts. With copies, this test could not be written."""
    assert (
        main(
            [
                "--database", str(roster), "roster", "declare", "okafor",
                "--dossier", LEGAL,
                "--specialization", "cozy-fantasy",
                "--shape", "several-no-beat",
            ]
        )
        == EXIT_OK
    )
    assert (
        main(
            ["--database", str(roster), "roster", "refuse", "okafor", "--reason",
             "not wanted"]
        )
        == EXIT_OK
    )
    capsys.readouterr()
    assert (
        main(
            [
                "--database", str(book), "--roster-database", str(roster),
                "listing", "--writer", "okafor",
            ]
        )
        == EXIT_FAULT
    )
    assert "a refusal is terminal" in capsys.readouterr().err


def test_the_roster_suite_operates_on_the_installation_roster_and_provenance_stays_put(
    roster, book, capsys
) -> None:
    """`roster declare` and `roster accept` under a configured roster write the installation's
    store and never open the book database. The acceptance decision row lands in the same file
    as the writer it admitted, which is the whole of why nothing needs to travel."""
    argv = ["--database", str(book), "--roster-database", str(roster)]
    assert (
        main(
            [
                *argv,
                "roster", "declare", "okafor",
                "--dossier", LEGAL,
                "--specialization", "cozy-fantasy",
                "--shape", "several-no-beat",
            ]
        )
        == EXIT_OK
    )
    assert main([*argv, "roster", "accept", "okafor"]) == EXIT_OK
    capsys.readouterr()
    assert main([*argv, "roster", "show"]) == EXIT_OK
    (row,) = json.loads(capsys.readouterr().out)["writers"]
    assert row["status"] == "accepted"
    assert not book.exists()

    with SqliteStore.open(roster) as store:
        stored = store.roster_rows()[0]
        decision = store.load_decision(stored["decision_id"])
    assert decision.gates[0].rule_or_critic_id == "roster.accept.v0"


def test_recruit_hands_its_child_the_installation_roster(
    roster, book, capsys, monkeypatch
) -> None:
    """The Recruiter's declares belong in the installation's roster, and the child reads its
    database from the environment — so the handoff is what has to point there. The transport is
    stubbed at `_completion_call` because a recruit run is a paid agent; what is under test is
    only which store the run targets before and after that call."""
    seen: dict[str, str] = {}

    def refused(request, *, calls, spend):
        seen["database"] = cli.os.environ.get(cli.DATABASE_ENV, "")
        return None, "no transport in this test"

    monkeypatch.setattr(cli, "_completion_call", refused)
    capsys.readouterr()
    assert (
        main(
            [
                "--database", str(book), "--roster-database", str(roster),
                "recruit", "--specialization", "cozy-fantasy",
            ]
        )
        == EXIT_FAULT
    )
    assert seen["database"] == str(roster.resolve())
    assert roster.exists()
    assert not book.exists()
