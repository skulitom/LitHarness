"""A text under test is identified by its name, so two texts may never share one.

Every instrument that takes `--texts` keys its per-text results by `load_texts`' name —
`blurb_tribunal.run` keys both its reports and its raw sidecar, `blurb_rewrite` keys its
pool means. A shared name therefore does not merge two texts, it silently replaces one with
the other, and every call made for the loser has already been paid for. `blurb_tribunal.v0`'s
first run lost two of three `ours` targets exactly that way, because every book's reading copy
is `book-library/<slug>/overview.txt` and the name was the bare stem (stage-0 §145).

No model call, no network, no database: this is path and dictionary handling.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent.parent / "research" / "quality-measurement"
if str(_HERE) not in sys.path:  # house pattern; conftest inserts it too, this is defensive
    sys.path.insert(0, str(_HERE))

listing_arena = pytest.importorskip(
    "listing_arena",
    reason="research module; imported by path, skipped where research/ is unavailable",
)


def _overview(root: Path, slug: str, text: str) -> Path:
    path = root / slug / "overview.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_a_txt_entry_is_named_by_its_directory_and_its_stem(tmp_path: Path) -> None:
    path = _overview(tmp_path, "patch-notes-for-earth", "a listing.")
    (entry,) = listing_arena.load_texts([str(path)])
    assert entry["name"] == "patch-notes-for-earth:overview"
    assert entry["listing"] == "a listing."


def test_two_books_overview_files_never_share_a_name(tmp_path: Path) -> None:
    """The exact shape that cost the tribunal's first run two of its three ours targets."""
    paths = [
        str(_overview(tmp_path, "a-good-take", "first listing.")),
        str(_overview(tmp_path, "copy-costs-a-hand", "second listing.")),
        str(_overview(tmp_path, "patch-notes-for-earth", "third listing.")),
    ]
    entries = listing_arena.load_texts(paths)
    names = [entry["name"] for entry in entries]
    assert len(set(names)) == len(names) == 3
    # And the loser of the old collision is still carried, not overwritten by the survivor.
    assert entries[0]["listing"] == "first listing."


def test_a_bare_txt_path_with_no_directory_keeps_its_stem() -> None:
    assert listing_arena.text_name(Path("overview.txt")) == "overview"


def test_text_names_are_exactly_the_names_load_texts_produces(tmp_path: Path) -> None:
    """A rehearsal that names or counts differently from the paid run is not a rehearsal."""
    bundle = tmp_path / "pilot11" / "listing.json"
    bundle.parent.mkdir(parents=True, exist_ok=True)
    bundle.write_text(
        json.dumps({"title": "T", "draft": "the draft.", "listing": "the revision."}),
        encoding="utf-8",
    )
    paths = [str(_overview(tmp_path, "a-good-take", "a listing.")), str(bundle)]

    loaded = [entry["name"] for entry in listing_arena.load_texts(paths)]
    assert listing_arena.text_names(paths) == loaded
    # A bundle is two entries, not one: the count a dry run prints has to be this one.
    assert listing_arena.text_names(paths) == [
        "a-good-take:overview",
        "pilot11:draft",
        "pilot11:revised",
    ]
