"""The operator dashboard generates a readable page from whatever is on disk.

The two failures worth a regression test are the ones this host actually produces: a page
written through the console's cp1252 codec instead of UTF-8, which mangles every em dash and
kills the *Chinese Cultivation (in English)* shelf outright; and a roster read that raises
instead of degrading when the schema moves under it.

The fixture writes only `roster_writers`, deliberately: a dashboard that needs the whole
migrated store to render one list is a dashboard that breaks whenever the store gains a table.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from tools import dashboard

#: An em dash and CJK characters, the two things cp1252 cannot carry.
DOSSIER_ONE = (
    "You write the long climb out of mortality — sect gates, heavenly tribulations, "
    "and the word 修真 for what the climb is called at home."
)
DOSSIER_TWO = "You write villages, trades, and the seasons they turn on."


def _roster_db(path: Path) -> Path:
    database = path / "roster.db"
    with closing(sqlite3.connect(database)) as con:
        con.execute(
            """
            CREATE TABLE roster_writers (
                writer_id TEXT PRIMARY KEY, name TEXT NOT NULL, dossier TEXT NOT NULL,
                interests_json TEXT NOT NULL DEFAULT '[]', exemplar_digest TEXT,
                note TEXT NOT NULL DEFAULT '', specialization TEXT NOT NULL,
                shape TEXT NOT NULL, status TEXT NOT NULL, proposed_at TEXT NOT NULL,
                accepted_at TEXT, decision_id TEXT
            )
            """
        )
        con.executemany(
            "INSERT INTO roster_writers (writer_id, name, dossier, interests_json, "
            "specialization, shape, status, proposed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "wtr-aaaa1111", "yuen", DOSSIER_ONE,
                    '["chinese cultivation", "heavenly tribulations"]',
                    "chinese-cultivation", "several-with-beat", "proposed",
                    "2026-08-28T19:49:44.823303Z",
                ),
                (
                    "wtr-bbbb2222", "penhale", DOSSIER_TWO, '["cozy fantasy"]',
                    "cozy-fantasy", "several-no-beat", "proposed",
                    "2026-08-28T19:42:51.958431Z",
                ),
            ],
        )
        con.commit()
    return database


def _library(path: Path) -> Path:
    library = path / "book-library"
    shelf = library / "what-takes"
    (shelf / "chapters").mkdir(parents=True)
    (shelf / "covers").mkdir()
    (shelf / "what-takes.md").write_text(
        "# What Takes\n\n*2 of 2 chapter(s) complete · 7,704 word(s) · 2026-08-22*\n",
        encoding="utf-8",
    )
    (shelf / "what-takes.html").write_text("<html></html>", encoding="utf-8")
    (shelf / "chapters" / "Chapter1.txt").write_text("one", encoding="utf-8")
    (shelf / "covers" / "cover-01.art.png").write_bytes(b"\x89PNG-art")
    (shelf / "covers" / "cover-01.png").write_bytes(b"\x89PNG")
    return library


def _generate(tmp_path: Path) -> str:
    output = tmp_path / "dashboard.html"
    exit_code = dashboard.main(
        [
            "--no-cli",
            "--database", str(_roster_db(tmp_path)),
            "--library", str(_library(tmp_path)),
            "--output", str(output),
        ]
    )

    assert exit_code == 0
    return output.read_text(encoding="utf-8")


def test_the_page_is_utf8_and_declares_it(tmp_path: Path) -> None:
    """Read back as UTF-8 with no `errors=` escape: cp1252 output would raise here."""
    page = _generate(tmp_path)

    assert '<meta charset="utf-8">' in page
    assert page.startswith("<!DOCTYPE html>")
    assert "修真" in page
    assert "—" in page


def test_every_proposed_writer_arrives_with_its_dossier(tmp_path: Path) -> None:
    page = _generate(tmp_path)

    assert "yuen" in page
    assert "penhale" in page
    assert "chinese-cultivation" in page
    assert "several-with-beat" in page
    assert "2026-08-28" in page
    assert "heavenly tribulations" in page
    assert DOSSIER_TWO in page
    assert "Job applications &mdash; 2" in page


def test_each_application_carries_the_command_that_signs_it(tmp_path: Path) -> None:
    """The page never accepts; the command is the whole mechanism, so it must be exact."""
    page = _generate(tmp_path)

    assert "roster accept yuen" in page
    assert "roster accept penhale" in page
    assert "uv run litharness --database" in page
    # `--database` is a global flag and has to precede the subcommand to be parsed at all.
    assert "litharness roster accept" not in page


def test_a_contested_name_is_addressed_by_id_instead(tmp_path: Path) -> None:
    database = _roster_db(tmp_path)
    with closing(sqlite3.connect(database)) as con:
        con.execute(
            "INSERT INTO roster_writers (writer_id, name, dossier, interests_json, "
            "specialization, shape, status, proposed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("wtr-cccc3333", "yuen", DOSSIER_ONE, "[]", "chinese-cultivation",
             "single-image", "proposed", "2026-08-28T20:00:00Z"),
        )
        con.commit()
    output = tmp_path / "out.html"
    dashboard.main(
        ["--no-cli", "--database", str(database), "--library", str(_library(tmp_path)),
         "--output", str(output)]
    )
    page = output.read_text(encoding="utf-8")

    assert "roster accept wtr-aaaa1111" in page
    assert "roster accept wtr-cccc3333" in page
    assert "roster accept yuen" not in page
    assert "roster accept penhale" in page


def test_a_book_card_links_and_shows_its_cover_by_relative_path(tmp_path: Path) -> None:
    page = _generate(tmp_path)

    assert "What Takes" in page
    assert "2 of 2 chapters" in page
    assert "7,704" in page
    assert "book-library/what-takes/what-takes.html" in page
    # The plain cover wins over the `.art` variant, and it is a path rather than a data URI.
    assert "book-library/what-takes/covers/cover-01.png" in page
    assert "data:image" not in page


def test_an_unreadable_roster_degrades_to_a_note(tmp_path: Path) -> None:
    """A schema that moved is a visible note on the page, never a traceback."""
    broken = tmp_path / "roster.db"
    with closing(sqlite3.connect(broken)) as con:
        con.execute("CREATE TABLE something_else (id TEXT)")
        con.commit()
    output = tmp_path / "out.html"

    assert dashboard.main(
        ["--no-cli", "--database", str(broken), "--library", str(tmp_path / "nothing"),
         "--output", str(output)]
    ) == 0
    page = output.read_text(encoding="utf-8")

    assert "could not be read" in page
    assert "No library on disk yet." in page


def test_the_compiled_cast_is_on_the_same_page_as_the_applications(tmp_path: Path) -> None:
    page = _generate(tmp_path)

    assert "Roster &mdash; 0 signed, 4 compiled" in page
    for name in ("ferreira", "halloran", "vance", "okonjo"):
        assert name in page
