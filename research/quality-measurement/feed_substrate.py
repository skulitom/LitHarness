"""The feed continuation reader's substrate: feed builders and the corpus report.

What sits under a session before any reader is seated. `feed_core` registers the shape (four
books entered mid-stream, a 27-minute budget of reads at 3 and skims at 1); this module builds
`feed_core.FeedSpec` objects at that shape and answers what a corpus can carry. Three concerns,
kept apart:

1. **Loading.** `load_scene_texts` reads a scenes JSON of the same shape `bcr.load_text` reads;
   `fitness_texts` reads drafted prose out of book databases through `corpus_io.generated_scenes`
   — BRIEF §2 Pass 6's un-memorised substrate, which is the licensed feed.
2. **Arms.** `intact_feed` seats a target against three competitors in caller-chosen order (the
   caller owns any rotation of the pool; nothing here samples). The three control arms reuse
   `ablate`'s standing placebo pair — persona work's placebos, called by their exact names:
   `fp1_placebo` removes contrast altogether (four byte-identical copies), `fp3_whitespace` and
   `fp4_rename` damage the competitors' surface and nothing else (`rewhitespace`,
   `rename_entities`). Every builder hands back a spec whose `fault()` the **caller** checks:
   shortness is surfaced by the report below and by `fault()`, never silently dropped, but a
   structurally wrong input — wrong competitor count, empty text — refuses here.
3. **The report.** `substrate_report` is pure arithmetic over `{name: text}`: per member, the
   chunk count and whether it clears `feed_core.MIN_CHUNKS_FEED`; totals, with the short names
   **listed**. A report that said "20 members" when 3 cannot carry a session would be §89's
   no-silent-caps failure in miniature.

No model call anywhere, and no read of `results/` or `derived/`. The driver (`feed_battery.py`)
is the composition root; nothing here decides what runs.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import ablate  # noqa: E402
import bcr  # noqa: E402
import corpus_io  # noqa: E402
import feed_core  # noqa: E402

#: Strength the placebo pair runs at. Both transforms take `strength` and are deterministic
#: given the text (each seeds its rng from the text), so 1.0 is the whole edit and a repeatable
#: one — a control whose bytes moved between runs would not be a control.
PLACEBO_STRENGTH = 1.0


def _require_prose(text: str, what: str) -> None:
    """Refuse an empty member here, so `fault()` is reserved for the shortness question."""
    if not text.strip():
        raise ValueError(f"{what} is empty; a feed member must carry prose")


# ----------------------------------------------------------------------------------- loading


def load_scene_texts(path: Path) -> dict[str, str]:
    """A scenes JSON in the shape `bcr.load_text` reads, as `{unit_id: text}`.

    Mirrors bcr's parsing exactly — `payload["scenes"]`, each scene's `"text"` — keyed by the
    scene's `"unit_id"` rather than joined into one text, because a feed wants per-book members,
    not one shelf-length string.
    """
    if not path.is_file():
        raise FileNotFoundError(f"no scenes JSON at {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {str(scene["unit_id"]): str(scene["text"]) for scene in payload["scenes"]}


_BOOK_BRANCH = re.compile(r"--book ([0-9a-f-]{36}) --branch ([0-9a-f-]{36})")


def _member_units(path: Path) -> list[corpus_io.Unit]:
    """One book's scenes from a database that may hold more than one book.

    Measured on the delivered shelf (`fitness_books.word_count`'s docstring records it first):
    a failed driver attempt can leave a second book behind in a store, and the export layer
    then refuses without `--book`, naming the candidates. A shelf member is one book, so the
    member is the **largest single one** — the same rule the delivery driver used to count
    words, applied here to the prose itself. Deterministic for a fixed store; the bare-call
    fast path stays exactly `generated_scenes(path)` for the nineteen single-book stores.
    """
    try:
        return corpus_io.generated_scenes(path)
    except ValueError as error:
        pairs = _BOOK_BRANCH.findall(str(error))
        if not pairs:
            raise
        candidates = [
            corpus_io.generated_scenes(path, book=book, branch=branch)
            for book, branch in pairs
        ]
        return max(candidates, key=lambda units: sum(len(unit.text.split()) for unit in units))


def fitness_texts(directory: Path) -> list[tuple[str, str]]:
    """One `(name, text)` per `fitness-*.db`, sorted by filename; text is the joined draft.

    Reads through `corpus_io.generated_scenes`, so each book arrives exactly as the export path
    would show a reader — one revision, live nodes, reading order, stubs dropped. Sorted by
    filename rather than discovered order so a feed built from this list is reproducible across
    platforms and directory-walk orders.
    """
    if not directory.is_dir():
        raise FileNotFoundError(f"no fitness database directory at {directory}")
    out: list[tuple[str, str]] = []
    for path in sorted(directory.glob("fitness-*.db")):
        units = _member_units(path)
        out.append((path.stem, "\n\n".join(unit.text for unit in units)))
    return out


# -------------------------------------------------------------------------------------- arms


def intact_feed(
    feed_id: str, target: tuple[str, str], competitors: Sequence[tuple[str, str]]
) -> feed_core.FeedSpec:
    """Arm `"intact"`: the target against the first `FEED_SIZE - 1` competitors, in order.

    Deterministic on purpose — no sampling here. Any rotation of the competitor pool is the
    caller's decision, so a battery's seating policy lives in exactly one place. The note records
    the names in order (`"target=fitness-00 others=fitness-01,fitness-02,fitness-03"`) because a
    result file that cannot say which books were on the feed is not an experiment record.
    """
    needed = feed_core.FEED_SIZE - 1
    if len(competitors) < needed:
        raise ValueError(
            f"{len(competitors)} competitor(s) supplied; an intact feed of "
            f"{feed_core.FEED_SIZE} books needs {needed}"
        )
    _require_prose(target[1], f"intact feed {feed_id}: target text")
    taken = competitors[:needed]
    for name, text in taken:
        _require_prose(text, f"intact feed {feed_id}: competitor {name}")
    note = f"target={target[0]} others={','.join(name for name, _ in taken)}"
    return feed_core.FeedSpec(
        feed_id=feed_id,
        arm="intact",
        target=target[1],
        others=tuple(text for _, text in taken),
        note=note,
    )


def placebo_feed(feed_id: str, text: str) -> feed_core.FeedSpec:
    """Arm `"fp1_placebo"`: four byte-identical copies of one text.

    The control reading is allocation across slots near `1 / FEED_SIZE`. With no contrast on the
    feed at all, a reader that concentrates on one slot is following position or habit, not text
    — the same slot-share logic `fp5` checks, isolated from content.
    """
    _require_prose(text, f"placebo feed {feed_id}")
    return feed_core.FeedSpec(
        feed_id=feed_id,
        arm="fp1_placebo",
        target=text,
        others=(text, text, text),
        note=(
            "four byte-identical copies of one text; control reads allocation near "
            f"1/{feed_core.FEED_SIZE}"
        ),
    )


def whitespace_feed(feed_id: str, text: str) -> feed_core.FeedSpec:
    """Arm `"fp3_whitespace"`: intact target, competitors re-whitespaced via `ablate`.

    The competitors are `ablate.rewhitespace(text, PLACEBO_STRENGTH)` — the standing placebo,
    not a new transform, so this arm inherits the sham's measured contract: not one character of
    any word moves. If the transform is deterministic the three competitors are identical
    copies; that is accepted because the reading is the **target share against `1/FEED_SIZE`**,
    not competitor identity — the question is whether layout alone pulls reads off the intact
    text, and three equal copies answer it as well as three variants would.
    """
    _require_prose(text, f"whitespace feed {feed_id}")
    damaged = ablate.rewhitespace(text, PLACEBO_STRENGTH)
    return feed_core.FeedSpec(
        feed_id=feed_id,
        arm="fp3_whitespace",
        target=text,
        others=(damaged, damaged, damaged),
        note=(
            f"target intact; competitors are ablate.rewhitespace(text, {PLACEBO_STRENGTH}); "
            "identical copies accepted — the datum is target share against "
            f"1/{feed_core.FEED_SIZE}"
        ),
    )


def rename_feed(feed_id: str, text: str) -> feed_core.FeedSpec:
    """Arm `"fp4_rename"`: intact target, competitors entity-renamed via `ablate`.

    The competitors are `ablate.rename_entities(text, PLACEBO_STRENGTH)` — the standing rename
    sham, which consistently renames the most frequent capitalised tokens and changes no craft.
    As in `whitespace_feed`, identical copies are accepted: the reading is target share against
    `1/FEED_SIZE`, and renaming is a surface change a content-driven allocator should not see at
    all — a drop in target share here would mean the reader tracks familiarity, not story.
    """
    _require_prose(text, f"rename feed {feed_id}")
    damaged = ablate.rename_entities(text, PLACEBO_STRENGTH)
    return feed_core.FeedSpec(
        feed_id=feed_id,
        arm="fp4_rename",
        target=text,
        others=(damaged, damaged, damaged),
        note=(
            f"target intact; competitors are ablate.rename_entities(text, {PLACEBO_STRENGTH}); "
            "identical copies accepted — the datum is target share against "
            f"1/{feed_core.FEED_SIZE}"
        ),
    )


# ------------------------------------------------------------------------------------ report


def substrate_report(texts: Mapping[str, str]) -> dict[str, Any]:
    """Pure, no-I/O: which members can carry a session, and which cannot.

    Per name, the `bcr.chunks` count and whether it clears `feed_core.MIN_CHUNKS_FEED`; totals
    for members, clearing and short. The short names are listed, never dropped — the report is
    how a corpus that cannot carry the instrument says so.
    """
    per_member: dict[str, dict[str, Any]] = {}
    short_names: list[str] = []
    clearing = 0
    for name, text in texts.items():
        held = len(bcr.chunks(text))
        clears = held >= feed_core.MIN_CHUNKS_FEED
        per_member[name] = {"chunks": held, "clears": clears}
        if clears:
            clearing += 1
        else:
            short_names.append(name)
    return {
        "members": len(texts),
        "clearing": clearing,
        "short": len(short_names),
        "short_names": short_names,
        "per_member": per_member,
    }

