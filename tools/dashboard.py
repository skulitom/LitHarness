"""The operator's mini dashboard: one HTML page, generated, read-only, no model calls.

Double-click `dashboard.cmd` at the repository root. It regenerates `dashboard.html` and opens
it. That is the whole launch story; there is no server, no build step, and nothing to install
beyond the environment `uv run` already provides.

**This file never writes to a database and never accepts a writer.** Acceptance mints a
`PolicyDecision` row and is the operator's recorded act (`cli.cmd_roster`, the `accept` view:
*"a person put these writers on the roster"*). A dashboard button would make that act the
dashboard's, which is the one thing the roster is built to prevent. So every application here
carries the exact command instead, and the operator runs it.

**Reads go through `litharness roster show` first**, the repository's own machine-readable view,
which already writes UTF-8 bytes past this host's cp1252 console codec (`cli._say`). Direct
read-only SQLite is the fallback for when that command is unavailable or its shape has moved,
and every read degrades to a visible note on the page rather than a traceback.

**Nothing dossier-shaped is ever printed to stdout.** One shelf is *Chinese Cultivation (in
English)* and the dossiers carry em dashes; cp1252 cannot encode either, and a print statement
is how that class of defect has cost this project a sixteen-minute run before. Progress lines
here are ASCII counts. The page is written as UTF-8 with an explicit meta charset.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sqlite3
import subprocess
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

REPO = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO / "runs" / "roster" / "roster.db"
DEFAULT_LIBRARY = REPO / "book-library"
DEFAULT_OUTPUT = REPO / "dashboard.html"

#: The stat line every reading copy's Markdown carries, written by the library publisher.
_STATS = re.compile(r"^\*(\d+) of (\d+) chapter\(s\) complete .* ([\d,]+) word\(s\)", re.M)
_TITLE = re.compile(r"^#\s+(.+?)\s*$", re.M)


# ---------------------------------------------------------------- reading the roster


def _cli_roster(database: Path) -> dict[str, Any] | None:
    """`litharness roster show --dossier`, or None if that view cannot be had.

    Captured as bytes and decoded here: the child writes UTF-8 through `cli._say` regardless of
    what the console codec claims, so decoding it as anything else is how the dossiers break.
    """
    try:
        done = subprocess.run(
            [
                "uv", "run", "litharness",
                "--database", str(database),
                "roster", "show", "--dossier",
            ],
            capture_output=True,
            cwd=REPO,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    try:
        payload = json.loads(done.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) and "writers" in payload else None


def _sqlite_roster(database: Path) -> dict[str, Any] | None:
    """The same rows straight from the file, opened `mode=ro` so no write is even possible.

    Defensive by column name rather than by position: a migration that adds a column must not
    turn the dashboard into a traceback, and one that drops a column should cost that field
    only.
    """
    if not database.exists():
        return None
    uri = f"file:{quote(database.as_posix())}?mode=ro"
    try:
        # `closing`, not a bare `with`: a connection context manager commits and leaves the
        # handle open, and this repository counts a leaked resource as a test error.
        with closing(sqlite3.connect(uri, uri=True, timeout=5)) as con:
            con.row_factory = sqlite3.Row
            rows = [dict(row) for row in con.execute("SELECT * FROM roster_writers")]
    except sqlite3.Error:
        return None
    writers = []
    for row in rows:
        try:
            interests = json.loads(row.get("interests_json") or "[]")
        except json.JSONDecodeError:
            interests = []
        writers.append(
            {
                "writer_id": row.get("writer_id", ""),
                "name": row.get("name", ""),
                "status": row.get("status", ""),
                "specialization": row.get("specialization", ""),
                "shape": row.get("shape", ""),
                "interests": interests if isinstance(interests, list) else [],
                "proposed_at": row.get("proposed_at", ""),
                "accepted_at": row.get("accepted_at"),
                "dossier": row.get("dossier", ""),
                "note": row.get("note", ""),
            }
        )
    return {"writers": writers, "cast": [], "source": "sqlite"}


def read_roster(database: Path) -> dict[str, Any]:
    """Whichever read view answers, with a `source` recording which one did."""
    payload = _cli_roster(database)
    if payload is not None:
        payload.setdefault("source", "litharness roster show")
        return payload
    payload = _sqlite_roster(database)
    if payload is not None:
        return payload
    return {"writers": [], "cast": [], "source": "", "unreadable": True}


def cast_writers() -> list[dict[str, Any]]:
    """The four compiled controls, imported rather than parsed.

    `tools/` carries no architecture constraint (`tests/test_architecture.py` does not scan it),
    and the import gets the dossier and the note that the CLI's `cast` summary leaves out. An
    environment without the package installed loses this section and nothing else.
    """
    try:
        from litharness.domain import writers as writers_domain
    except Exception:
        # A missing or unimportable package costs this one section and nothing else.
        return []
    out = []
    for writer in writers_domain.CAST.values():
        out.append(
            {
                "writer_id": writer.writer_id,
                "name": writer.name,
                "dossier": writer.dossier,
                "interests": list(writer.interests),
                "note": writer.note,
            }
        )
    return out


def accept_command(writer: dict[str, Any], database: Path, contested: set[str]) -> str:
    """The command that signs this application, addressed the way the CLI can answer.

    `--database` is a global flag and sits between the binary and the subcommand. The name is
    the ordinary address; a name two proposals share cannot be resolved by name at all, so those
    are addressed by writer id — the escape hatch `cmd_roster` documents for an edited dossier.
    """
    name = writer.get("name", "")
    address = writer.get("writer_id", "") if name in contested else name
    return f"uv run litharness --database {_db_arg(database)} roster accept {address}"


def _db_arg(database: Path) -> str:
    """The database as the operator would type it: relative to the repository root when it is
    inside it, because `dashboard.cmd` puts the shell there and a long absolute path is a
    command nobody copies twice."""
    try:
        return database.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return str(database)


# ---------------------------------------------------------------- reading the bookshelf


def read_books(library: Path) -> list[dict[str, Any]]:
    """One record per `book-library/<slug>/`, from the reading copy the publisher already wrote."""
    if not library.is_dir():
        return []
    books = []
    for shelf in sorted(p for p in library.iterdir() if p.is_dir()):
        slug = shelf.name
        markdown = shelf / f"{slug}.md"
        reading_copy = shelf / f"{slug}.html"
        text = ""
        if markdown.is_file():
            try:
                text = markdown.read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = ""
        title_match = _TITLE.search(text)
        stats = _STATS.search(text)
        chapters = shelf / "chapters"
        chapter_files = sorted(chapters.glob("*.txt")) if chapters.is_dir() else []
        books.append(
            {
                "slug": slug,
                "title": title_match.group(1) if title_match else slug.replace("-", " ").title(),
                "complete": int(stats.group(1)) if stats else len(chapter_files),
                "planned": int(stats.group(2)) if stats else len(chapter_files),
                "words": stats.group(3) if stats else "",
                "link": _relative(reading_copy, library) if reading_copy.is_file() else "",
                "cover": _cover(shelf, library),
            }
        )
    return books


def _cover(shelf: Path, library: Path) -> str:
    """The first cover, by relative path. Never inlined - a data URI is the bloat we refused."""
    covers = shelf / "covers"
    if not covers.is_dir():
        return ""
    images = sorted(p for p in covers.glob("cover-*.png") if p.is_file())
    if not images:
        return ""
    plain = [p for p in images if not p.name.endswith(".art.png")]
    return _relative((plain or images)[0], library)


def _relative(target: Path, library: Path) -> str:
    """A `file://`-safe relative href from the generated page to something in the library."""
    try:
        rel = target.resolve().relative_to(REPO)
    except ValueError:
        rel = Path(library.name) / target.resolve().relative_to(library.resolve())
    return "/".join(quote(part) for part in rel.as_posix().split("/"))


def git_sha() -> str:
    try:
        done = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, cwd=REPO, timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return done.stdout.strip() if done.returncode == 0 else "unknown"


# ---------------------------------------------------------------- the page

CSS = """
:root { --ink:#1b1815; --faint:#6f665b; --rule:#e2dbd1; --card:#fff; --page:#f6f3ee;
        --accent:#8a3d22; --chip:#efe9e0; }
* { box-sizing:border-box; }
body { margin:0; background:var(--page); color:var(--ink); padding:2rem 1.5rem 4rem;
       font:15px/1.55 "Segoe UI", system-ui, -apple-system, sans-serif; }
main { max-width:62rem; margin:0 auto; }
h1 { font-size:1.6rem; margin:0 0 .3rem; letter-spacing:-.01em; }
h2 { font-size:1.05rem; text-transform:uppercase; letter-spacing:.09em; color:var(--faint);
     margin:2.6rem 0 .9rem; border-bottom:1px solid var(--rule); padding-bottom:.4rem; }
.meta { color:var(--faint); font-size:.85rem; }
.meta code { background:var(--chip); padding:.1rem .35rem; border-radius:3px; }
.note { background:#fdf6e6; border-left:3px solid var(--accent); padding:.6rem .85rem;
        border-radius:0 4px 4px 0; font-size:.88rem; margin:0 0 1.1rem; }
.card { background:var(--card); border:1px solid var(--rule); border-radius:6px;
        padding:1rem 1.15rem; margin-bottom:.85rem; }
.who { display:flex; flex-wrap:wrap; align-items:baseline; gap:.5rem; }
.who strong { font-size:1.15rem; }
.chip { background:var(--chip); border-radius:20px; padding:.1rem .6rem; font-size:.76rem;
        color:var(--faint); white-space:nowrap; }
.chip.shape { background:#e7eef0; }
.dossier { margin:.7rem 0; font-size:.94rem; }
/* The chips are joined without whitespace, so only flex-wrap can break the line; without it
   a writer with four interests pushes a horizontal scrollbar onto the whole page. */
.interests { color:var(--faint); font-size:.83rem; margin:.4rem 0 .7rem;
             display:flex; flex-wrap:wrap; align-items:center; gap:.3rem; }
.cmd { display:block; background:#211d19; color:#f0e7da; padding:.55rem .7rem; border-radius:4px;
       font:12.5px/1.5 Consolas, "SF Mono", monospace; overflow-x:auto; cursor:pointer;
       white-space:pre; user-select:all; }
.cmd:hover { background:#2c2621; }
.cmd[data-copied] { outline:2px solid var(--accent); }
.why { color:var(--accent); font-size:.8rem; margin:.35rem 0 0; }
.shelf { display:grid; grid-template-columns:repeat(auto-fill,minmax(15rem,1fr)); gap:.85rem; }
.book { background:var(--card); border:1px solid var(--rule); border-radius:6px; overflow:hidden;
        display:flex; flex-direction:column; }
.book img { width:100%; height:11rem; object-fit:cover; display:block; background:var(--chip); }
.book .body { padding:.75rem .9rem; }
.book a { color:var(--accent); text-decoration:none; font-weight:600; }
.book a:hover { text-decoration:underline; }
.empty { color:var(--faint); font-style:italic; }
@media (prefers-color-scheme:dark) {
  :root { --ink:#e8e2d9; --faint:#9a9086; --rule:#3a342d; --card:#232019; --page:#191712;
          --accent:#d98a63; --chip:#332d26; }
  .note { background:#2a2419; }
  .cmd { background:#0f0d0b; }
}
"""

JS = """
document.querySelectorAll('.cmd').forEach(function (el) {
  el.addEventListener('click', function () {
    var range = document.createRange();
    range.selectNodeContents(el);
    var sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    try {
      document.execCommand('copy');
      el.dataset.copied = '1';
      setTimeout(function () { delete el.dataset.copied; }, 1200);
    } catch (e) { /* selection alone is the fallback */ }
  });
});
"""


def _e(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _chips(values: list[Any]) -> str:
    return "".join(f'<span class="chip">{_e(v)}</span>' for v in values)


def _applications(writers: list[dict[str, Any]], database: Path, unreadable: bool) -> str:
    proposed = [w for w in writers if w.get("status") == "proposed"]
    where = _db_arg(database)
    out = [f"<h2>Job applications &mdash; {len(proposed)}</h2>"]
    out.append(
        '<p class="note">This page never accepts anybody. Acceptance writes a decision row and '
        "is your recorded act, so the command is here to copy rather than a button to press "
        "(click a command to select and copy it). A bare "
        f"<code>uv run litharness --database {_e(where)} roster accept</code> takes every "
        "proposal below in one decision.</p>"
    )
    if unreadable:
        out.append(
            '<p class="card empty">The roster could not be read. Neither '
            "<code>litharness roster show</code> nor a read-only open of "
            f"<code>{_e(where)}</code> answered.</p>"
        )
        return "\n".join(out)
    if not proposed:
        out.append(
            '<p class="card empty">Nothing proposed. Every declared writer has been signed.</p>'
        )
        return "\n".join(out)

    seen: dict[str, int] = {}
    for writer in proposed:
        seen[writer.get("name", "")] = seen.get(writer.get("name", ""), 0) + 1
    accepted = {w.get("name") for w in writers if w.get("status") == "accepted"}
    contested = {name for name, count in seen.items() if count > 1} | (set(seen) & accepted)

    for writer in proposed:
        name = writer.get("name", "")
        card = [
            '<div class="card">',
            '<div class="who">',
            f"<strong>{_e(name)}</strong>",
            f'<span class="chip">{_e(writer.get("specialization"))}</span>',
            f'<span class="chip shape">{_e(writer.get("shape"))}</span>',
            f'<span class="chip">declared {_e((writer.get("proposed_at") or "")[:10])}</span>',
            f'<span class="chip">{_e(writer.get("writer_id"))}</span>',
            "</div>",
            f'<p class="dossier">{_e(writer.get("dossier"))}</p>',
        ]
        interests = writer.get("interests") or []
        if isinstance(interests, list) and interests:
            card.append(f'<div class="interests">Knows: {_chips(interests)}</div>')
        card.append(f'<code class="cmd">{_e(accept_command(writer, database, contested))}</code>')
        if name in contested:
            card.append(
                '<p class="why">Addressed by id: more than one proposal answers to this name, '
                "so a name cannot pick between them.</p>"
            )
        card.append("</div>")
        out.append("".join(card))
    return "\n".join(out)


def _roster(writers: list[dict[str, Any]], cast: list[dict[str, Any]]) -> str:
    signed = [w for w in writers if w.get("status") == "accepted"]
    out = [f"<h2>Roster &mdash; {len(signed)} signed, {len(cast)} compiled</h2>"]
    if not signed:
        out.append(
            '<p class="card empty">Nobody has been signed yet. The four below are compiled into '
            "the package and are the controls the roster is read against.</p>"
        )
    for writer in signed:
        out.append(
            '<div class="card"><div class="who">'
            f'<strong>{_e(writer.get("name"))}</strong>'
            f'<span class="chip">{_e(writer.get("specialization"))}</span>'
            f'<span class="chip shape">{_e(writer.get("shape"))}</span>'
            f'<span class="chip">signed {_e((writer.get("accepted_at") or "")[:10])}</span>'
            f'<span class="chip">{_e(writer.get("writer_id"))}</span>'
            f'</div><p class="dossier">{_e(writer.get("dossier"))}</p></div>'
        )
    for writer in cast:
        interests = writer.get("interests") or []
        out.append(
            '<div class="card"><div class="who">'
            f'<strong>{_e(writer.get("name"))}</strong>'
            '<span class="chip">compiled cast</span>'
            f'<span class="chip">{_e(writer.get("writer_id"))}</span>'
            f'</div><p class="dossier">{_e(writer.get("dossier"))}</p>'
            + (f'<div class="interests">Knows: {_chips(interests)}</div>' if interests else "")
            + "</div>"
        )
    return "\n".join(out)


def _bookshelf(books: list[dict[str, Any]]) -> str:
    out = [f"<h2>Bookshelf &mdash; {len(books)}</h2>"]
    if not books:
        out.append('<p class="card empty">No library on disk yet.</p>')
        return "\n".join(out)
    out.append('<div class="shelf">')
    for book in books:
        cover = f'<img src="{_e(book["cover"])}" alt="">' if book["cover"] else ""
        chapters = f'{book["complete"]} of {book["planned"]} chapters'
        words = f' &middot; {_e(book["words"])} words' if book["words"] else ""
        title = (
            f'<a href="{_e(book["link"])}">{_e(book["title"])}</a>'
            if book["link"]
            else _e(book["title"])
        )
        out.append(
            f'<div class="book">{cover}<div class="body">{title}'
            f'<div class="meta">{chapters}{words}</div></div></div>'
        )
    out.append("</div>")
    return "\n".join(out)


def render(
    roster: dict[str, Any], cast: list[dict[str, Any]], books: list[dict[str, Any]], database: Path
) -> str:
    writers = roster.get("writers") or []
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    source = roster.get("source") or "nothing"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LitHarness</title>
<style>{CSS}</style>
</head>
<body>
<main>
<h1>LitHarness</h1>
<p class="meta">Generated {_e(generated)} &middot; main at <code>{_e(git_sha())}</code>
&middot; roster read through <code>{_e(source)}</code><br>
Double-click <code>dashboard.cmd</code> again to refresh everything on this page.</p>
{_applications(writers, database, bool(roster.get("unreadable")))}
{_roster(writers, cast)}
{_bookshelf(books)}
</main>
<script>{JS}</script>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the operator's dashboard.")
    parser.add_argument("--database", type=Path, default=DEFAULT_DB)
    parser.add_argument("--library", type=Path, default=DEFAULT_LIBRARY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--no-cli",
        action="store_true",
        help="skip `litharness roster show` and read the database directly",
    )
    args = parser.parse_args(argv)

    if args.no_cli:
        roster = _sqlite_roster(args.database) or {
            "writers": [], "cast": [], "source": "", "unreadable": True
        }
        roster.setdefault("source", "sqlite (read-only)")
    else:
        roster = read_roster(args.database)
    books = read_books(args.library)
    page = render(roster, cast_writers(), books, args.database)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(page, encoding="utf-8", newline="\n")

    # ASCII counts only. Dossier text never reaches this stream; the console codec is cp1252.
    proposed = sum(1 for w in (roster.get("writers") or []) if w.get("status") == "proposed")
    print(f"dashboard: {proposed} application(s), {len(books)} book(s) -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
