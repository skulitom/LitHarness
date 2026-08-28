"""The operator dashboard: what it renders, what it flips, and what it refuses to do itself.

Four failures worth pinning, and each has already happened somewhere in this repository:

* a page written through the console's cp1252 codec instead of UTF-8, which mangles every em
  dash and kills the *Chinese Cultivation (in English)* shelf outright;
* a roster read that raises instead of degrading when the schema moves under it;
* a person-flip that produces "the people around I am counting" — `you are` matching across a
  preposition boundary and swallowing a verb belonging to another subject (stage-0 §149);
* a write path that bypasses the CLI, which would make the dashboard the signer rather than
  the operator. `test_no_write_path_bypasses_the_cli` is the structural guard for that one.

The fixture writes only `roster_writers` and a stub `policy_decisions`, deliberately: a
dashboard that needs the whole migrated store to render one list is a dashboard that breaks
whenever the store gains a table.
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
                accepted_at TEXT, refused_at TEXT, decision_id TEXT
            )
            """
        )
        con.execute(
            "CREATE TABLE policy_decisions (decision_id TEXT PRIMARY KEY, reason TEXT)"
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


def _refuse_in_fixture(database: Path, writer_id: str, reason: str) -> None:
    """What `roster refuse` leaves behind, written straight into the fixture."""
    with closing(sqlite3.connect(database)) as con:
        con.execute(
            "INSERT INTO policy_decisions (decision_id, reason) VALUES (?, ?)",
            ("dec-1", reason),
        )
        con.execute(
            "UPDATE roster_writers SET status = 'refused', refused_at = ?, decision_id = ? "
            "WHERE writer_id = ?",
            ("2026-08-28T21:00:00Z", "dec-1", writer_id),
        )
        con.commit()


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


def _generate(tmp_path: Path, database: Path | None = None) -> str:
    output = tmp_path / "dashboard.html"
    exit_code = dashboard.main(
        [
            "--once", "--no-cli", "--no-browser",
            "--database", str(database or _roster_db(tmp_path)),
            "--library", str(_library(tmp_path)),
            "--output", str(output),
        ]
    )

    assert exit_code == 0
    return output.read_text(encoding="utf-8")


# ---------------------------------------------------------------- the writer's own voice


def test_the_dossier_is_flipped_into_the_writers_own_voice() -> None:
    assert dashboard.first_person("You write cozy fantasy.") == "I write cozy fantasy."
    assert dashboard.first_person("What you love is a price.") == "What I love is a price."
    assert dashboard.first_person("You are patient.") == "I am patient."
    assert dashboard.first_person("Your rivals.") == "My rivals."
    assert dashboard.first_person("you'd know yourself") == "I'd know myself"


def test_an_object_you_becomes_me_rather_than_i() -> None:
    """The two the corpus survey missed and the rendered page caught (stage-0 §149)."""
    assert (
        dashboard.first_person("how strangers speak to you")
        == "how strangers speak to me"
    )
    # The bad one: `you are` must not match across the preposition and steal `are counting`.
    assert (
        dashboard.first_person("the people around you are counting every one")
        == "the people around me are counting every one"
    )


def test_the_flip_never_touches_the_stored_text(tmp_path: Path) -> None:
    """Display only. A flip written back would break every content-addressed `writer_id`."""
    database = _roster_db(tmp_path)
    _generate(tmp_path, database)
    with closing(sqlite3.connect(database)) as con:
        stored = list(con.execute("SELECT dossier FROM roster_writers ORDER BY name"))

    assert {row[0] for row in stored} == {DOSSIER_ONE, DOSSIER_TWO}


# ---------------------------------------------------------------- the page


def test_the_page_is_utf8_and_declares_it(tmp_path: Path) -> None:
    """Read back as UTF-8 with no `errors=` escape: cp1252 output would raise here."""
    page = _generate(tmp_path)

    assert '<meta charset="utf-8">' in page
    assert page.startswith("<!DOCTYPE html>")
    assert "修真" in page
    assert "—" in page


def test_every_proposed_writer_arrives_in_both_voices(tmp_path: Path) -> None:
    page = _generate(tmp_path)

    assert "yuen" in page
    assert "penhale" in page
    assert "chinese-cultivation" in page
    assert "Job applications &mdash; 2" in page
    # The flipped reading is the primary presentation...
    assert "I write villages, trades, and the seasons they turn on." in page
    # ...and the exact stored bytes are underneath it, which is what the operator signs.
    assert DOSSIER_TWO in page
    assert "the text that rides the prompt, verbatim" in page


def test_a_saved_copy_says_its_buttons_cannot_act(tmp_path: Path) -> None:
    page = _generate(tmp_path)

    assert "saved copy" in page
    # The handlers are always in the script; what a saved copy must not have is a button for
    # them to bind to. Asserting on the bare class name matches `wire('.js-accept', ...)`.
    assert '<button class="yes js-accept">' not in page
    assert '<button class="no js-refuse">' not in page


def test_a_live_page_carries_buttons_and_a_token() -> None:
    page = dashboard.render(
        {
            "writers": [
                {
                    "writer_id": "w1", "name": "yuen", "status": "proposed",
                    "specialization": "s", "shape": "x", "interests": [],
                    "proposed_at": "2026-08-28", "dossier": DOSSIER_ONE,
                }
            ],
            "source": "test",
        },
        [],
        [],
        token="tok-123",
        live=True,
    )

    assert 'data-token="tok-123"' in page
    assert "js-accept" in page
    assert "js-refuse" in page
    assert "server running" in page


def test_a_refused_writer_stays_on_the_page_with_its_reason(tmp_path: Path) -> None:
    """Refusal is a status transition, never a deletion, so the record stays readable."""
    database = _roster_db(tmp_path)
    _refuse_in_fixture(database, "wtr-aaaa1111", "machinery vocabulary leaks into the dossier")
    page = _generate(tmp_path, database)

    assert "Refused &mdash; 1" in page
    assert "machinery vocabulary leaks into the dossier" in page
    assert "never deleted" in page
    # It has left the applications, and it is not on the roster either.
    assert "Job applications &mdash; 1" in page
    assert "Roster &mdash; 0 signed" in page


def test_a_book_card_links_and_shows_its_cover_by_relative_path(tmp_path: Path) -> None:
    page = _generate(tmp_path)

    assert "What Takes" in page
    assert "2 of 2 chapters" in page
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
        ["--once", "--no-cli", "--no-browser", "--database", str(broken),
         "--library", str(tmp_path / "nothing"), "--output", str(output)]
    ) == 0
    page = output.read_text(encoding="utf-8")

    assert "could not be read" in page
    assert "No library on disk yet." in page


def test_the_compiled_cast_is_on_the_same_page_as_the_applications(tmp_path: Path) -> None:
    page = _generate(tmp_path)

    assert "Roster &mdash; 0 signed, 4 compiled" in page
    for name in ("ferreira", "halloran", "vance", "okonjo"):
        assert name in page


# ---------------------------------------------------------------- the rail


def test_the_server_refuses_to_share_its_port() -> None:
    """One line, and a second double-click is why (stage-0 §149).

    `socketserver.TCPServer.allow_reuse_address` is true by default, and on Windows
    `SO_REUSEADDR` lets a second socket bind a port that is already being listened on rather
    than only reclaiming one in `TIME_WAIT`. The second launch therefore bound 8765 again and
    announced itself as serving, leaving two servers racing for the same connections. Turning
    it off is what makes the port-in-use path reachable at all.
    """
    assert dashboard._OneServer.allow_reuse_address is False


def test_no_write_path_bypasses_the_cli() -> None:
    """The structural guard: the dashboard may never write to the store itself.

    Accepting and refusing mint decision rows, and the whole architecture rests on those rows
    being the operator's — produced by the same commands a typed invocation produces. A direct
    INSERT or UPDATE here would make the dashboard the signer, silently. Every read opens
    `mode=ro`, so such a statement could not even execute today; this test exists so that a
    future edit which opens a writable connection has to argue with a test first.
    """
    source = Path(dashboard.__file__).read_text(encoding="utf-8")
    quoted = source.replace('"', "'")

    assert "'roster', 'accept'" in quoted
    assert "'roster', 'refuse'" in quoted
    assert "mode=ro" in source
    for statement in ("INSERT INTO", "UPDATE ROSTER", "DELETE FROM"):
        assert statement not in source.upper(), statement
