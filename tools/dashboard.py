"""The operator's mini dashboard: one local page for reading applications and signing them.

Double-click `dashboard.cmd` at the repository root. It starts a small server on 127.0.0.1,
opens the browser at it, and that is the whole launch story. Double-click it twice and the
second one finds the port taken, opens the browser at the server already running, and exits.
Closing the console window stops the server; so does the Quit button on the page.

**No model is anywhere in this file.** Nothing here generates, ranks, judges or summarises.

**Every write goes through the real CLI, and that is the point of the architecture.** The
Accept and Reject buttons do not touch SQLite. They shell out to `litharness roster accept`
and `litharness roster refuse`, which mint the same `PolicyDecision` rows those commands
always mint. The operator clicking IS the operator signing — one act, one decision row, the
same one a typed command produces. Reads stay read-only: `litharness roster show` first, a
`mode=ro` SQLite open as the fallback, and a note on the page rather than a traceback when
neither answers.

**Refusal is terminal, so the button asks for a reason before it posts** (stage-0 §149).
`roster refuse` requires one, a refused row is never deleted, and refused applications stay on
this page in their own section with the reason the decision row carries.

**Dossiers are shown in the writer's own voice, and the stored text is shown underneath.** The
flip is a deterministic person swap at render time — no model, no rewrite, nothing stored. A
dossier is written in the second person, addressed to the writer, so first person reads as the
cover letter it effectively is. The operator signs containment text that rides in every scene
prompt for a whole book, so the exact stored bytes are always one click away, and it is the
stored bytes that the content-addressed `writer_id` is computed over.

**Nothing dossier-shaped is ever printed to stdout.** One shelf is *Chinese Cultivation (in
English)* and a refusal reason is free text; this host's console codec is cp1252, which can
encode neither, and a print statement is how that class of defect has cost this project a
sixteen-minute run before. Console lines here are ASCII. The page is UTF-8 with a meta charset.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import secrets
import sqlite3
import subprocess
import threading
import webbrowser
from contextlib import closing
from datetime import UTC, datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

REPO = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO / "runs" / "roster" / "roster.db"
DEFAULT_LIBRARY = REPO / "book-library"
DEFAULT_OUTPUT = REPO / "dashboard.html"
DEFAULT_PORT = 8765

#: The stat line every reading copy's Markdown carries, written by the library publisher.
_STATS = re.compile(r"^\*(\d+) of (\d+) chapter\(s\) complete .* ([\d,]+) word\(s\)", re.M)
_TITLE = re.compile(r"^#\s+(.+?)\s*$", re.M)


# ---------------------------------------------------------------- the writer's own voice

#: Ordered, and the order is the whole correctness argument: `you are` has to be consumed
#: before the bare `you` rule turns it into "I are". Each entry is (pattern, replacement),
#: applied in sequence over the whole text.
#:
#: **Calibrated against the corpus rather than against English.** Every second-person token in
#: the sixteen dossiers on this installation is `you` followed by a plain present-tense verb —
#: love, write, want, read, can, think, have — plus two `you are`. Those need no verb repair at
#: all beyond `are -> am`, because English conjugates the first and second person identically
#: everywhere else. The contraction and possessive rules below are unexercised by the current
#: corpus and are here for the dossier that has not been written yet.
#:
#: **An object-position `you` becomes `me`, and it is handled first because the corpus survey
#: missed it and the rendered page did not.** Two of the sixteen have one — *"the rank that
#: changes how strangers speak to you"*, and *"the people around you are counting every one of
#: them"*, where the naive rules produced "speak to I" and, worse, "the people around I am
#: counting": `you are` matched across a preposition boundary and swallowed a verb belonging to
#: a different subject. A preposition in front is a high-precision signal for the object case,
#: and running it before every other rule is what stops that miscombination.
#:
#: The residual limit, stated rather than papered over: a `you` in object position after a bare
#: verb ("hands you a title") would still become `I`. No dossier has one, and the verbatim text
#: sits one click below every flip, so a wrong pronoun is visible rather than silent.
_OBJECT = re.compile(
    r"\b(to|for|at|with|from|about|around|near|beside|behind|before|after|between|against"
    r"|on|in|of|by|like|than|toward|towards|into|onto|upon|under|over|through|past)"
    r"\s+you\b",
    re.I,
)

_FLIPS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\byou're\b", re.I), "I'm"),
    (re.compile(r"\byou've\b", re.I), "I've"),
    (re.compile(r"\byou'll\b", re.I), "I'll"),
    (re.compile(r"\byou'd\b", re.I), "I'd"),
    (re.compile(r"\byou are\b", re.I), "I am"),
    (re.compile(r"\byou were\b", re.I), "I was"),
    (re.compile(r"\byou aren't\b", re.I), "I'm not"),
    (re.compile(r"\byourself\b", re.I), "myself"),
    (re.compile(r"\byours\b", re.I), "mine"),
    (re.compile(r"\byour\b", re.I), "my"),
    (re.compile(r"\byou\b", re.I), "I"),
)


def first_person(text: str) -> str:
    """A second-person dossier read back in the writer's own voice. Display only.

    **Nothing stored changes and nothing may.** `writer_id` is a content address computed over
    the dossier bytes, so a flip written back to the row would make every writer stop addressing
    its own id — the exact corruption `roster check` exists to detect.
    """
    text = _OBJECT.sub(lambda m: f"{m.group(1)} me", text)
    for pattern, replacement in _FLIPS:
        text = pattern.sub(lambda m, r=replacement: _match_case(m.group(0), r), text)
    return text


def _match_case(original: str, replacement: str) -> str:
    """Carry the original's capitalisation onto the replacement.

    `I` and its contractions are capital in every position, so they are returned as written;
    only the possessives (`Your` -> `My`) actually need this.
    """
    if replacement.startswith("I"):
        return replacement
    if original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


# ---------------------------------------------------------------- reading the roster


def _cli_roster(database: Path) -> dict[str, Any] | None:
    """`litharness roster show --dossier`, or None if that view cannot be had.

    Captured as bytes and decoded here: the child writes UTF-8 through `cli._say` regardless of
    what the console codec claims, so decoding it as anything else is how the dossiers break.
    """
    ok, out = _run_cli(database, "roster", "show", "--dossier")
    if not ok:
        return None
    try:
        payload = json.loads(out)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) and "writers" in payload else None


def _sqlite_roster(database: Path) -> dict[str, Any] | None:
    """The same rows straight from the file, opened `mode=ro` so no write is even possible.

    Defensive by column name rather than by position: a migration that adds a column must not
    turn the dashboard into a traceback, and one that drops a column should cost that field
    only. `refused_at` arrived in 036 and is read with a default for exactly that reason.
    """
    rows = _read_only(database, f"SELECT * FROM roster_writers{_ORDER}")
    if rows is None:
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
                "refused_at": row.get("refused_at"),
                "dossier": row.get("dossier", ""),
            }
        )
    return {"writers": writers, "cast": [], "source": "sqlite (read-only)"}


_ORDER = " ORDER BY name, writer_id"


def _read_only(database: Path, sql: str) -> list[dict[str, Any]] | None:
    """Run one SELECT against the store without any possibility of writing to it."""
    if not database.exists():
        return None
    uri = f"file:{quote(database.as_posix())}?mode=ro"
    try:
        # `closing`, not a bare `with`: a connection context manager commits and leaves the
        # handle open, and this repository counts a leaked resource as a test error.
        with closing(sqlite3.connect(uri, uri=True, timeout=5)) as con:
            con.row_factory = sqlite3.Row
            return [dict(row) for row in con.execute(sql)]
    except sqlite3.Error:
        return None


def refusal_reasons(database: Path) -> dict[str, str]:
    """`writer_id -> the reason on its refusal decision`, for the refused section.

    **Read here rather than added to `roster show`, and the rail is `show`'s own.** That view
    withholds `note` because a view a generative agent holds is where an operator's preference
    would reach another generative agent; a refusal reason is that same sentence — *"too grim,
    go lighter"* — with a decision row under it. It belongs to the operator's surface, so it is
    read through the store, exactly as `show`'s docstring says a note must be.
    """
    rows = _read_only(
        database,
        "SELECT w.writer_id AS writer_id, d.reason AS reason FROM roster_writers w "
        "JOIN policy_decisions d ON d.decision_id = w.decision_id "
        "WHERE w.status = 'refused'",
    )
    return {r["writer_id"]: r["reason"] or "" for r in rows or []}


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
    and the import gets the dossier the CLI's `cast` summary leaves out. An environment without
    the package installed loses this section and nothing else.
    """
    try:
        from litharness.domain import writers as writers_domain
    except Exception:
        # A missing or unimportable package costs this one section and nothing else.
        return []
    return [
        {
            "writer_id": writer.writer_id,
            "name": writer.name,
            "dossier": writer.dossier,
            "interests": list(writer.interests),
        }
        for writer in writers_domain.CAST.values()
    ]


# ---------------------------------------------------------------- the only writes


def _run_cli(database: Path, *arguments: str) -> tuple[bool, str]:
    """Run one `litharness` command and hand back its UTF-8 output.

    The single choke point for everything this tool does to the store, read or write. Output is
    captured as bytes and decoded UTF-8 here because the child writes UTF-8 deliberately
    (`cli._say`) past a cp1252 console, and it is **returned rather than printed** because a
    dossier or a refusal reason in it would then hit that codec on the way out.
    """
    try:
        done = subprocess.run(
            ["uv", "run", "litharness", "--database", str(database), *arguments],
            capture_output=True,
            cwd=REPO,
            timeout=180,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return False, f"the litharness command could not be run: {error}"
    text = (done.stdout + b"\n" + done.stderr).decode("utf-8", errors="replace").strip()
    return done.returncode == 0, text


def accept_writer(database: Path, writer_id: str) -> tuple[bool, str]:
    """Sign one application. Addressed by id, never by name.

    An id cannot be ambiguous, and two proposals sharing a name is a case the roster allows on
    purpose — an edited dossier is a different writer — so the button that a person clicks next
    to one specific card must address that exact row.
    """
    return _run_cli(database, "roster", "accept", writer_id)


def refuse_writer(database: Path, writer_id: str, reason: str) -> tuple[bool, str]:
    """Turn one application down, with the operator's stated reason on the decision row."""
    return _run_cli(database, "roster", "refuse", writer_id, "--reason", reason)


# ---------------------------------------------------------------- reading the bookshelf


def read_books(library: Path) -> list[dict[str, Any]]:
    """One record per `book-library/<slug>/`, from the reading copy the publisher wrote."""
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
    """A relative href that works both under the server and from the file on disk."""
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
        --accent:#8a3d22; --chip:#efe9e0; --yes:#2f6b46; --no:#8f2f2f; --live:#2f6b46; }
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
.card.gone { opacity:.55; }
.who { display:flex; flex-wrap:wrap; align-items:baseline; gap:.5rem; }
.who strong { font-size:1.15rem; }
.chip { background:var(--chip); border-radius:20px; padding:.1rem .6rem; font-size:.76rem;
        color:var(--faint); white-space:nowrap; }
.chip.shape { background:#e7eef0; }
.dossier { margin:.7rem 0; font-size:.94rem; }
.interests { color:var(--faint); font-size:.83rem; margin:.4rem 0 .7rem;
             display:flex; flex-wrap:wrap; align-items:center; gap:.3rem; }
details { margin:.5rem 0 .2rem; }
summary { cursor:pointer; color:var(--faint); font-size:.82rem; }
details p { font-size:.88rem; background:var(--chip); padding:.6rem .75rem; border-radius:4px;
            margin:.5rem 0 0; white-space:pre-wrap; }
.actions { display:flex; gap:.5rem; margin-top:.8rem; align-items:center; flex-wrap:wrap; }
button { font:inherit; font-size:.88rem; font-weight:600; border:0; border-radius:5px;
         padding:.42rem 1rem; cursor:pointer; color:#fff; }
button:disabled { opacity:.5; cursor:progress; }
.yes { background:var(--yes); } .no { background:var(--no); }
.ghost { background:transparent; color:var(--faint); border:1px solid var(--rule); }
.said { font-size:.85rem; color:var(--faint); }
.said.bad { color:var(--no); }
.why { color:var(--no); font-size:.86rem; margin:.5rem 0 0; }
.why b { color:var(--ink); }
.shelf { display:grid; grid-template-columns:repeat(auto-fill,minmax(15rem,1fr)); gap:.85rem; }
.book { background:var(--card); border:1px solid var(--rule); border-radius:6px; overflow:hidden;
        display:flex; flex-direction:column; }
.book img { width:100%; height:11rem; object-fit:cover; display:block; background:var(--chip); }
.book .body { padding:.75rem .9rem; }
.book a { color:var(--accent); text-decoration:none; font-weight:600; }
.book a:hover { text-decoration:underline; }
.empty { color:var(--faint); font-style:italic; }
.bar { display:flex; align-items:center; gap:.6rem; flex-wrap:wrap; margin-top:.6rem; }
.dot { width:.55rem; height:.55rem; border-radius:50%; background:var(--live);
       display:inline-block; }
.dot.off { background:var(--no); }
@media (prefers-color-scheme:dark) {
  :root { --ink:#e8e2d9; --faint:#9a9086; --rule:#3a342d; --card:#232019; --page:#191712;
          --accent:#d98a63; --chip:#332d26; --yes:#3d8a5c; --no:#c0564f; --live:#3d8a5c; }
  .note { background:#2a2419; }
}
"""

JS = """
const TOKEN = document.body.dataset.token;

async function post(path, body) {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(Object.assign({ token: TOKEN }, body || {}))
  });
  return res.json();
}

function wire(selector, handler) {
  document.querySelectorAll(selector).forEach(function (el) {
    el.addEventListener('click', function () { handler(el); });
  });
}

function say(card, text, bad) {
  const out = card.querySelector('.said');
  out.textContent = text;
  out.classList.toggle('bad', !!bad);
}

function busy(card, on) {
  card.querySelectorAll('button').forEach(function (b) { b.disabled = on; });
}

wire('.js-accept', async function (el) {
  const card = el.closest('.card');
  const name = card.dataset.name;
  const ask = 'Sign ' + name + ' onto the roster?\\n\\nThis writes a decision row in your name.';
  if (!confirm(ask)) return;
  busy(card, true);
  say(card, 'signing...');
  const out = await post('/api/accept', { writer_id: card.dataset.id });
  if (out.ok) { say(card, 'signed. reloading...'); location.reload(); }
  else { say(card, out.detail || 'refused', true); busy(card, false); }
});

wire('.js-refuse', async function (el) {
  const card = el.closest('.card');
  const name = card.dataset.name;
  const reason = prompt('Turn ' + name + ' down. Why? (one line, recorded on the decision row)');
  if (reason === null) return;
  if (!reason.trim()) { say(card, 'a reason is required; nothing was recorded', true); return; }
  busy(card, true);
  say(card, 'recording...');
  const out = await post('/api/refuse', { writer_id: card.dataset.id, reason: reason });
  if (out.ok) { say(card, 'refused. reloading...'); location.reload(); }
  else { say(card, out.detail || 'refused', true); busy(card, false); }
});

wire('.js-quit', async function () {
  if (!confirm('Stop the dashboard server?')) return;
  await post('/api/quit', {});
  stopped();
});

function stopped() {
  document.querySelectorAll('.dot').forEach(function (d) { d.classList.add('off'); });
  const label = document.getElementById('serverstate');
  if (label) label.textContent = 'server stopped - double-click dashboard.cmd to start it again';
  document.querySelectorAll('button').forEach(function (b) { b.disabled = true; });
}

setInterval(async function () {
  try {
    const res = await fetch('/api/ping', { cache: 'no-store' });
    if (!res.ok) throw new Error('down');
  } catch (e) { stopped(); }
}, 4000);
"""


def _e(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _chips(values: list[Any]) -> str:
    return "".join(f'<span class="chip">{_e(v)}</span>' for v in values)


def _voice(dossier: str) -> str:
    """The flipped dossier, then the stored bytes behind a disclosure."""
    return (
        f'<p class="dossier">{_e(first_person(dossier))}</p>'
        "<details><summary>the text that rides the prompt, verbatim</summary>"
        f"<p>{_e(dossier)}</p></details>"
    )


def _applications(writers: list[dict[str, Any]], unreadable: bool, live: bool) -> str:
    proposed = [w for w in writers if w.get("status") == "proposed"]
    out = [f"<h2>Job applications &mdash; {len(proposed)}</h2>"]
    if unreadable:
        out.append(
            '<p class="card empty">The roster could not be read. Neither '
            "<code>litharness roster show</code> nor a read-only open of the database "
            "answered.</p>"
        )
        return "\n".join(out)
    out.append(
        '<p class="note">Each dossier is shown in the writer\'s own voice; the exact stored '
        "text is one click below it, and that is the text that rides in every scene prompt. "
        "<b>Accept</b> and <b>Reject</b> run the real <code>litharness</code> commands, so a "
        "click here writes the same decision row a typed command writes &mdash; it is your "
        "signature either way. Rejecting is terminal and asks for a reason; nothing is ever "
        "deleted.</p>"
    )
    if not live:
        out.append(
            '<p class="note">This is a saved copy of the page, so the buttons cannot act. '
            "Double-click <code>dashboard.cmd</code> for the live one.</p>"
        )
    if not proposed:
        out.append(
            '<p class="card empty">Nothing proposed. Every declared writer has been decided.</p>'
        )
        return "\n".join(out)

    for writer in proposed:
        out.append(
            f'<div class="card" data-id="{_e(writer.get("writer_id"))}" '
            f'data-name="{_e(writer.get("name"))}">'
            '<div class="who">'
            f'<strong>{_e(writer.get("name"))}</strong>'
            f'<span class="chip">{_e(writer.get("specialization"))}</span>'
            f'<span class="chip shape">{_e(writer.get("shape"))}</span>'
            f'<span class="chip">declared {_e((writer.get("proposed_at") or "")[:10])}</span>'
            f'<span class="chip">{_e(writer.get("writer_id"))}</span>'
            "</div>"
            + _voice(str(writer.get("dossier") or ""))
            + (
                f'<div class="interests">Knows: {_chips(writer["interests"])}</div>'
                if isinstance(writer.get("interests"), list) and writer.get("interests")
                else ""
            )
            + '<div class="actions">'
            + (
                '<button class="yes js-accept">Accept</button>'
                '<button class="no js-refuse">Reject</button>'
                if live
                else ""
            )
            + '<span class="said"></span></div></div>'
        )
    return "\n".join(out)


def _refused(writers: list[dict[str, Any]], reasons: dict[str, str]) -> str:
    gone = [w for w in writers if w.get("status") == "refused"]
    if not gone:
        return ""
    cards = []
    for writer in gone:
        said = reasons.get(str(writer.get("writer_id")), "")
        cards.append(
            '<div class="card gone"><div class="who">'
            f'<strong>{_e(writer.get("name"))}</strong>'
            f'<span class="chip">{_e(writer.get("specialization"))}</span>'
            f'<span class="chip">refused {_e((writer.get("refused_at") or "")[:10])}</span>'
            f'<span class="chip">{_e(writer.get("writer_id"))}</span></div>'
            + (f'<p class="why"><b>Reason.</b> {_e(said)}</p>' if said else "")
            + _voice(str(writer.get("dossier") or ""))
            + "</div>"
        )
    return (
        f"<h2>Refused &mdash; {len(gone)}</h2>"
        "<details><summary>show the applications that were turned down "
        "(kept on the record, never deleted)</summary>"
        + "".join(cards)
        + "</details>"
    )


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
            f'<span class="chip">{_e(writer.get("writer_id"))}</span></div>'
            + _voice(str(writer.get("dossier") or ""))
            + "</div>"
        )
    for writer in cast:
        interests = writer.get("interests") or []
        out.append(
            '<div class="card"><div class="who">'
            f'<strong>{_e(writer.get("name"))}</strong>'
            '<span class="chip">compiled cast</span>'
            f'<span class="chip">{_e(writer.get("writer_id"))}</span></div>'
            + _voice(str(writer.get("dossier") or ""))
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
    roster: dict[str, Any],
    cast: list[dict[str, Any]],
    books: list[dict[str, Any]],
    *,
    reasons: dict[str, str] | None = None,
    token: str = "",
    live: bool = False,
) -> str:
    writers = roster.get("writers") or []
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    source = roster.get("source") or "nothing"
    state = (
        '<span class="dot"></span><span id="serverstate">server running</span>'
        '<button class="ghost js-quit">Quit</button>'
        if live
        else '<span class="dot off"></span><span id="serverstate">saved copy - '
        "buttons need the server</span>"
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LitHarness</title>
<style>{CSS}</style>
</head>
<body data-token="{_e(token)}">
<main>
<h1>LitHarness</h1>
<p class="meta">Generated {_e(generated)} &middot; main at <code>{_e(git_sha())}</code>
&middot; roster read through <code>{_e(source)}</code><br>
Double-click <code>dashboard.cmd</code> again any time; closing its window stops the server.</p>
<div class="bar">{state}</div>
{_applications(writers, bool(roster.get("unreadable")), live)}
{_roster(writers, cast)}
{_refused(writers, reasons or {})}
{_bookshelf(books)}
</main>
<script>{JS}</script>
</body>
</html>
"""


def build_page(database: Path, library: Path, *, token: str = "", live: bool = False) -> str:
    roster = read_roster(database)
    return render(
        roster,
        cast_writers(),
        read_books(library),
        reasons=refusal_reasons(database),
        token=token,
        live=live,
    )


# ---------------------------------------------------------------- the server


class Dashboard(SimpleHTTPRequestHandler):
    """One page, three actions, and the static files the page links to.

    **Bound to 127.0.0.1 and gated on a per-run token.** Any page in the operator's browser can
    POST to a localhost port; this one shells out to a command that writes decision rows, so a
    cross-site form would be able to sign writers onto the roster. The token is minted per run
    and rendered into the page, and the same-origin policy stops any other site reading it.

    Static serving is restricted to `book-library/` rather than handed the repository root, so
    the covers and reading copies the page links to resolve and nothing else is exposed.
    """

    database: Path
    library: Path
    token: str
    server_version = "LitHarnessDashboard/2"

    def log_message(self, fmt: str, *args: Any) -> None:
        """Method and path only, ASCII, and never a request body.

        A refusal reason is free text an operator typed and arrives in a POST body; this
        console is cp1252 and the default handler logging is one of the three surfaces that
        has already killed a run on an unencodable character.
        """
        print(f"dashboard: {self.command} {urlparse(self.path).path}", flush=True)

    def do_GET(self) -> None:  # BaseHTTPRequestHandler's spelling, not ours
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send(
                200,
                build_page(self.database, self.library, token=self.token, live=True).encode(
                    "utf-8"
                ),
                "text/html; charset=utf-8",
            )
            return
        if path == "/api/ping":
            self._json(200, {"ok": True})
            return
        if path.startswith("/book-library/"):
            super().do_GET()
            return
        self._send(404, b"not found", "text/plain; charset=utf-8")

    def do_POST(self) -> None:  # BaseHTTPRequestHandler's spelling, not ours
        path = urlparse(self.path).path
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"ok": False, "detail": "unreadable request"})
            return
        if not isinstance(payload, dict) or not secrets.compare_digest(
            str(payload.get("token", "")), self.token
        ):
            self._json(403, {"ok": False, "detail": "stale page; reload it"})
            return

        if path == "/api/quit":
            self._json(200, {"ok": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        writer_id = str(payload.get("writer_id", ""))
        if path == "/api/accept":
            ok, detail = accept_writer(self.database, writer_id)
        elif path == "/api/refuse":
            reason = str(payload.get("reason", "")).strip()
            if not reason:
                self._json(400, {"ok": False, "detail": "a reason is required"})
                return
            ok, detail = refuse_writer(self.database, writer_id, reason)
        else:
            self._json(404, {"ok": False, "detail": "no such action"})
            return
        # `detail` can carry a dossier or a reason, so it goes to the browser and never to the
        # console. `_json` writes UTF-8 bytes; `print` would write cp1252.
        self._json(200 if ok else 500, {"ok": ok, "detail": detail[-400:]})

    def _json(self, code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(code, body, "application/json; charset=utf-8")

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


class _OneServer(ThreadingHTTPServer):
    """A server that refuses to share its port, which on Windows has to be said explicitly.

    **`allow_reuse_address` defaults to true up in `socketserver.TCPServer`, and on Windows
    `SO_REUSEADDR` does not mean what it means on Unix**: it lets a second socket bind a port
    another socket is already listening on, rather than only reclaiming one in `TIME_WAIT`.
    The second double-click therefore bound 8765 a second time and announced itself as serving,
    leaving two servers racing for the same connections and the port-in-use path — the whole
    mechanism that makes a second launch harmless — permanently unreachable. Turning it off is
    what makes `bind` fail honestly so `serve` can open the browser at the first one instead.
    """

    allow_reuse_address = False


def _open_browser(url: str) -> None:
    """Open the operator's browser without letting it hold this process open.

    **`webbrowser.open` can block, and it did.** It delegates to a handler — `$BROWSER` when
    that is set — and waits on it. Testing the second double-click caught it: the launch that
    should have said "port already in use" and exited sat there indefinitely with a browser
    helper as its child, so the operator would get a console window that never closes. A daemon
    thread with a bounded join costs a slow browser a few seconds instead of the process.
    """
    thread = threading.Thread(target=webbrowser.open, args=(url,), daemon=True)
    thread.start()
    thread.join(timeout=5)


def serve(database: Path, library: Path, port: int, *, open_browser: bool = True) -> int:
    """Hold the port and the page until the operator quits. Returns a process exit code.

    **A second double-click is not an error.** The port is fixed so that the second launch can
    recognise the first: it fails to bind, opens the browser at the server already running, and
    exits cleanly. An operator who double-clicks twice gets one server and two tabs, which is
    what they meant.
    """
    url = f"http://127.0.0.1:{port}/"
    handler = partial(Dashboard, directory=str(REPO))
    Dashboard.database = database
    Dashboard.library = library
    Dashboard.token = secrets.token_urlsafe(24)
    try:
        server = _OneServer(("127.0.0.1", port), handler)
    except OSError:
        # `flush`, because stdout is block-buffered when the console is redirected and an
        # unflushed line is one the operator never sees.
        print(
            f"dashboard: port {port} already in use; opening the one already there",
            flush=True,
        )
        if open_browser:
            _open_browser(url)
        return 0
    print(f"dashboard: serving {url} - close this window or click Quit to stop", flush=True)
    if open_browser:
        _open_browser(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    print("dashboard: stopped", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="The operator's dashboard.")
    parser.add_argument("--database", type=Path, default=DEFAULT_DB)
    parser.add_argument("--library", type=Path, default=DEFAULT_LIBRARY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--once",
        action="store_true",
        help="write the page to --output and exit, without serving. The buttons are inert in "
        "a saved copy, and it says so",
    )
    parser.add_argument(
        "--no-cli",
        action="store_true",
        help="skip `litharness roster show` and read the database directly",
    )
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser")
    args = parser.parse_args(argv)

    if args.once:
        if args.no_cli:
            roster = _sqlite_roster(args.database) or {
                "writers": [], "cast": [], "source": "", "unreadable": True
            }
        else:
            roster = read_roster(args.database)
        books = read_books(args.library)
        page = render(
            roster,
            cast_writers(),
            books,
            reasons=refusal_reasons(args.database),
            live=False,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(page, encoding="utf-8", newline="\n")
        # ASCII counts only. Dossier text never reaches this stream; the codec is cp1252.
        writers = roster.get("writers") or []
        proposed = sum(1 for w in writers if w.get("status") == "proposed")
        print(
            f"dashboard: {proposed} application(s), {len(books)} book(s) -> {args.output}",
            flush=True,
        )
        return 0

    return serve(args.database, args.library, args.port, open_browser=not args.no_browser)


if __name__ == "__main__":
    raise SystemExit(main())
