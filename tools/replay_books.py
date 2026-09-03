"""Replay the stored books: read every accepted scene the way the draft handler read it, and
compare what `extract_state` mints today with what the store holds.

This is the check every phase of the system-generality plan ran by hand (stage-0 §203 to
§212: "the four stored books replay identically, eight of eight") and the pruning and
maintainability briefs run before and after every cut or split. It reads a book, it never
writes one, and it decides nothing about prose.

    uv run python tools/replay_books.py
    uv run python tools/replay_books.py --store runs/ab/pilot25/draw1b --out before.json
    uv run python tools/replay_books.py --baseline before.json

Without `--store` the four stores the generality track replayed are used, resolved against
the primary checkout (`git rev-parse --git-common-dir`), since `runs/` is gitignored and a
linked worktree has none. A store that is absent is reported and skipped rather than failed:
the books are local artifacts and a fresh clone has no books to replay.

**Three rules, each bought by a way the check could have passed for nothing.**

1. **The store is never opened in place.** `SqliteStore.open` runs the migrations and sets
   `journal_mode=WAL`, both of which write. Each store is copied first through SQLite's
   backup API from a `mode=ro` URI connection (`SqliteStore.backup_to` gives the reason a
   file copy is not a backup of a WAL database), and every read is against the copy.
2. **`known` is what the handler saw, not the whole store.** `extract_state` leaves out any
   snapshot already canon at that position (`_already_canon`), so handing it the finished
   book returns nothing for every scene, and nothing compared with nothing is green. The
   handler read `store.state_records(...)` as it stood before the scene was accepted; here
   that is every live record whose accepting revision precedes the scene's in the head's
   lineage, plus the seed records (no accepting revision) written before that revision. The
   one approximation is a seed proposal accepted after the scene: the handler saw it as a
   proposal, and this sees nothing, because promotion rewrites `created_at`.
3. **Identity is the record id, and then the whole record.** `record_id_for` derives an id
   from subject, predicate, position and value, so an equal id set is the byte test on what
   was read; the JSON forms are then compared field by field so a changed evidence span or
   note is reported and not hidden behind an unchanged id.

A scene whose current version sits in the root revision (imported, or seeded by `new
--state`) was never drafted through the handler and is reported as skipped; a scene drafted
here needs the `scene_draft` job that drafted it, for the plan-stated position the handler
passed as `stated_order_key`, and is reported as skipped without one.

Beside the minted records the report carries, per scene position, the derived lines every
later reader renders off the finished store — `system_voice_example`, `state_as_it_stands`,
`snapshot_at`, `standing_example`, `change_example`, `offered_choice`, `offered_line`,
`counted_names`, `movable_names`, `movables`, `moved_values` and `gain_example`, all in
`domain/extraction.py` — so a split that moves a reader can be checked against `--baseline`
without a second model call anywhere. The exit status is 0 when every replayed scene is
identical and the baseline, when given, matches; 1 otherwise.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sqlite3
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import litharness_contracts as lc

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.handlers import SCENE_DRAFT
from litharness.domain import extraction, gamesystem, worlds
from litharness.domain import state as state_mod
from litharness.domain.nodes import NodeKind
from litharness.domain.revision import node_version_id

#: The stores the generality track replayed after every phase (stage-0 §203, §205, §206,
#: §212), relative to the primary checkout. `draw4` of pilot 25 is not here: it is the arm
#: still being drawn while this was written, and a live store is never opened.
DEFAULT_STORES: tuple[str, ...] = (
    "runs/ab/pilot25/draw1b",
    "runs/ab/pilot25/draw2",
    "runs/ab/pilot25/draw3",
    "runs/ab/pilot24-third/draw3",
)

DATABASE_NAME = "serial.db"


def default_root() -> Path:
    """The primary checkout, where `runs/` lives: a linked worktree's `git-common-dir` is
    the primary's `.git`, and the primary's own is `.git` relative to itself."""
    try:
        common = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return Path.cwd()
    return Path(common).resolve().parent


def snapshot_copy(source: Path, scratch: Path) -> Path:
    """A consistent copy of `source` taken read-only through the backup API (rule 1)."""
    scratch.mkdir(parents=True, exist_ok=True)
    target = scratch / f"{source.parent.name}-{source.stem}.db"
    if target.exists():
        target.unlink()
    origin = sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        copy = sqlite3.connect(str(target))
        try:
            origin.backup(copy)
        finally:
            copy.close()
    finally:
        origin.close()
    return target


@dataclasses.dataclass(frozen=True)
class Provenance:
    """The three columns the store facade does not expose and the replay needs: when each
    revision was made, which revision wrote each live record, and the draft jobs' payloads."""

    revision_created_at: dict[str, str]
    record_source: dict[str, tuple[str | None, str]]
    draft_payloads: list[dict[str, Any]]
    project_ids: list[str]

    @classmethod
    def read(cls, path: Path, book_id: str, branch_id: str) -> Provenance:
        connection = sqlite3.connect(str(path))
        connection.row_factory = sqlite3.Row
        try:
            revisions = {
                row["revision_id"]: row["created_at"]
                for row in connection.execute(
                    "SELECT revision_id, created_at FROM revisions "
                    "WHERE book_id = ? AND branch_id = ?",
                    (book_id, branch_id),
                )
            }
            sources = {
                row["record_id"]: (row["source_revision_id"], row["created_at"])
                for row in connection.execute(
                    "SELECT record_id, source_revision_id, created_at FROM state_records "
                    "WHERE book_id = ? AND branch_id = ? AND retracted_by_revision_id IS NULL",
                    (book_id, branch_id),
                )
            }
            payloads = [
                json.loads(row["payload"])
                for row in connection.execute(
                    "SELECT payload FROM jobs WHERE job_kind = ? ORDER BY rowid", (SCENE_DRAFT,)
                )
            ]
            projects = [
                row["project_id"]
                for row in connection.execute(
                    "SELECT DISTINCT project_id FROM events "
                    "WHERE book_id = ? AND project_id IS NOT NULL ORDER BY sequence",
                    (book_id,),
                )
            ]
        finally:
            connection.close()
        return cls(revisions, sources, payloads, projects)


def _jsonable(value: object) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {k: _jsonable(v) for k, v in dataclasses.asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(v) for v in value]
    return str(value)


def derived_lines(
    records: Sequence[lc.StateRecord], *, at: str | None, character: str | None
) -> dict[str, Any]:
    """Every line a later reader renders off the finished store at this position."""
    stands = extraction.state_as_it_stands(records, at=at)
    snapshot = extraction.snapshot_at(records, at=at)
    movables = extraction.movables(records, character=character, at=at)
    canon = [record for record in records if state_mod.is_canon(record)]
    return {
        "system_voice_example": extraction.system_voice_example(records, at=at),
        "state_as_it_stands": _jsonable(stands),
        "snapshot_at": None if snapshot is None else lc.to_jsonable(snapshot),
        "standing_example": extraction.standing_example(records, at=at),
        "change_example": extraction.change_example(records, character=character, at=at),
        "offered_choice": _jsonable(extraction.offered_choice(records, character=character, at=at)),
        "offered_line": extraction.offered_line(records, character=character, at=at),
        "counted_names": list(extraction.counted_names(records, at=at)),
        "movable_names": list(extraction.movable_names(records, character=character, at=at)),
        "movables": [_jsonable(movable) for movable in movables],
        "moved_values": {
            movable.name: _jsonable(
                extraction.moved_values(records, movable, character=character, at=at)
            )
            for movable in movables
        },
        "gain_example": {
            ability_id: extraction.gain_example(records, at=at, ability_id=ability_id)
            for system in gamesystem.systems_of(canon)
            for ability_id in system.ability_ids
        },
    }


def compare_records(
    expected: Sequence[lc.StateRecord], replayed: Sequence[lc.StateRecord]
) -> list[str]:
    """Every way the replayed records differ from the stored ones (rule 3), as sentences."""
    stored = {record.record_id: record for record in expected}
    minted = {record.record_id: record for record in replayed}
    differences: list[str] = []
    for record_id in sorted(set(stored) - set(minted)):
        record = stored[record_id]
        differences.append(
            f"stored but not re-minted: {record_id} "
            f"({record.subject} {record.predicate} at {state_mod.order_key_of(record)})"
        )
    for record_id in sorted(set(minted) - set(stored)):
        record = minted[record_id]
        differences.append(
            f"re-minted but not stored: {record_id} "
            f"({record.subject} {record.predicate} at {state_mod.order_key_of(record)})"
        )
    for record_id in sorted(set(stored) & set(minted)):
        before = lc.to_jsonable(stored[record_id])
        after = lc.to_jsonable(minted[record_id])
        if before == after:
            continue
        assert isinstance(before, dict) and isinstance(after, dict)
        for key in sorted(set(before) | set(after)):
            if before.get(key) != after.get(key):
                differences.append(
                    f"{record_id} field {key}: stored={before.get(key)!r} "
                    f"replayed={after.get(key)!r}"
                )
    return differences


def _stated_order_key(
    payloads: Sequence[dict[str, Any]], *, logical_id: str, base_revision_id: str
) -> tuple[str | None, bool]:
    """The plan-stated position the handler passed, from the job that drafted this version;
    the flag says whether any such job exists at all."""
    found = False
    stated: str | None = None
    for payload in payloads:
        if payload.get("logical_id") != logical_id:
            continue
        if payload.get("revision_id") != base_revision_id:
            continue
        found = True
        selected = payload.get("selected_by") or {}
        if isinstance(selected, dict) and selected.get("story_order_key"):
            stated = str(selected["story_order_key"])
    return stated, found


def replay_store(path: Path, *, scratch: Path) -> dict[str, Any]:
    """Replay every book in one store and report per accepted scene."""
    database = path / DATABASE_NAME if path.is_dir() else path
    report: dict[str, Any] = {"store": database.as_posix(), "books": []}
    if not database.exists():
        report["missing"] = True
        return report
    copy = snapshot_copy(database, scratch)
    with SqliteStore.open(copy) as store:
        for book_id, branch_id, head_id in store.branches():
            report["books"].append(_replay_book(store, copy, book_id, branch_id, head_id))
    return report


def _replay_book(
    store: SqliteStore, copy: Path, book_id: str, branch_id: str, head_id: str
) -> dict[str, Any]:
    provenance = Provenance.read(copy, book_id, branch_id)
    chain = list(reversed(store.lineage(head_id)))  # root first
    first_seen: dict[tuple[str, str], int] = {}
    for index, revision_id in enumerate(chain):
        for node in store.load_revision(revision_id).nodes:
            if node.kind is NodeKind.SCENE and node.content:
                first_seen.setdefault((node.logical_id, node_version_id(node)), index)
    head = store.load_revision(head_id)
    everything = store.state_records(book_id, branch_id)
    canon = [record for record in everything if state_mod.is_canon(record)]
    protagonists = worlds.entities_with_role(canon, "protagonist")
    character = protagonists[0] if protagonists else None
    project_id = provenance.project_ids[0] if provenance.project_ids else None

    scenes: list[dict[str, Any]] = []
    for node in head.in_reading_order():
        if node.kind is not NodeKind.SCENE or not node.content:
            continue
        version_id = node_version_id(node)
        index = first_seen[(node.logical_id, version_id)]
        entry: dict[str, Any] = {
            "logical_id": node.logical_id,
            "version_id": version_id,
            "accepting_revision": chain[index],
            "skipped": None,
        }
        if index == 0:
            entry["skipped"] = "in the root revision (imported or seeded), never drafted here"
            scenes.append(entry)
            continue
        accepting = chain[index]
        stated, drafted = _stated_order_key(
            provenance.draft_payloads,
            logical_id=node.logical_id,
            base_revision_id=chain[index - 1],
        )
        if not drafted:
            entry["skipped"] = (
                "no scene_draft job drafted this version, so its stated position is unknown"
            )
            scenes.append(entry)
            continue
        ancestors = set(chain[:index])
        accepted_at = provenance.revision_created_at[accepting]
        known_ids = {
            record_id
            for record_id, (source, created_at) in provenance.record_source.items()
            if (source in ancestors) or (source is None and created_at < accepted_at)
        }
        known = [record for record in everything if record.record_id in known_ids]
        expected = [
            record
            for record in everything
            if provenance.record_source[record.record_id][0] == accepting
        ]
        evidence_project = next(
            (span.source.project_id for record in expected for span in record.evidence), None
        )
        replayed = extraction.extract_state(
            node.content,
            known=known,
            project_id=evidence_project or project_id or "",
            book_id=book_id,
            branch_id=branch_id,
            logical_id=node.logical_id,
            version_id=version_id,
            stated_order_key=stated,
        )
        position = extraction.attested_position(everything, node.logical_id) or stated
        differences = compare_records(expected, replayed)
        entry.update(
            {
                "position": position,
                "stated_order_key": stated,
                "known": len(known),
                "expected": sorted(record.record_id for record in expected),
                "replayed": sorted(record.record_id for record in replayed),
                "identical": not differences,
                "differences": differences,
                "derived": derived_lines(everything, at=position, character=character),
            }
        )
        scenes.append(entry)
    return {
        "book_id": book_id,
        "branch_id": branch_id,
        "head": head_id,
        "revisions": len(chain),
        "records": len(everything),
        "scenes": scenes,
    }


def _scene_key(store: str, book: dict[str, Any], scene: dict[str, Any]) -> str:
    return f"{store} {book['book_id']} {scene['logical_id']}"


def compare_with_baseline(report: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    """What moved since the baseline: minted ids, identity, or any derived line."""
    current = {
        _scene_key(store["store"], book, scene): scene
        for store in report["stores"]
        for book in store.get("books", [])
        for scene in book["scenes"]
    }
    previous = {
        _scene_key(store["store"], book, scene): scene
        for store in baseline["stores"]
        for book in store.get("books", [])
        for scene in book["scenes"]
    }
    moved: list[str] = []
    for key in sorted(set(previous) - set(current)):
        moved.append(f"{key}: in the baseline, not replayed now")
    for key in sorted(set(current) - set(previous)):
        moved.append(f"{key}: replayed now, not in the baseline")
    for key in sorted(set(current) & set(previous)):
        now = json.loads(json.dumps(current[key]))
        then = previous[key]
        for field in ("skipped", "expected", "replayed", "identical", "position"):
            if now.get(field) != then.get(field):
                moved.append(f"{key} {field}: baseline={then.get(field)!r} now={now.get(field)!r}")
        for line, value in (now.get("derived") or {}).items():
            if (then.get("derived") or {}).get(line) != value:
                moved.append(
                    f"{key} derived {line}: baseline={(then.get('derived') or {}).get(line)!r} "
                    f"now={value!r}"
                )
    return moved


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--store",
        action="append",
        type=Path,
        help="a store directory holding serial.db, or the database file; repeatable "
        "(default: the four stores the generality track replayed, under --root)",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="where runs/ lives (default: the primary checkout, via git rev-parse)",
    )
    parser.add_argument("--out", type=Path, help="write the full report as JSON here")
    parser.add_argument(
        "--baseline", type=Path, help="a report written by --out earlier, to compare against"
    )
    parser.add_argument(
        "--scratch",
        type=Path,
        default=None,
        help="where the read-only copies go (default: a temporary directory, removed after)",
    )
    args = parser.parse_args(argv)

    root = args.root or default_root()
    stores = args.store or [root / name for name in DEFAULT_STORES]

    with tempfile.TemporaryDirectory(prefix="replay-books-") as temporary:
        scratch = args.scratch or Path(temporary)
        report: dict[str, Any] = {"root": root.as_posix(), "stores": []}
        for store_path in stores:
            report["stores"].append(replay_store(store_path, scratch=scratch))

    replayed = identical = skipped = 0
    for store in report["stores"]:
        if store.get("missing"):
            print(f"{store['store']}: missing, skipped")
            continue
        for book in store["books"]:
            drafted = [scene for scene in book["scenes"] if scene["skipped"] is None]
            held = [scene for scene in drafted if scene["identical"]]
            replayed += len(drafted)
            identical += len(held)
            skipped += len(book["scenes"]) - len(drafted)
            print(
                f"{store['store']}: {len(drafted)} scenes replayed, {len(held)} identical, "
                f"{len(book['scenes']) - len(drafted)} skipped "
                f"({book['revisions']} revisions, {book['records']} live records)"
            )
            for scene in book["scenes"]:
                if scene["skipped"]:
                    print(f"  {scene['logical_id']}: skipped, {scene['skipped']}")
                    continue
                if not scene["identical"]:
                    print(f"  {scene['logical_id']} at {scene['position']}: DIFFERS")
                    for line in scene["differences"]:
                        print(f"    {line}")
    print(f"replay: {identical}/{replayed} identical, {skipped} skipped")

    status = 0 if identical == replayed else 1
    if args.baseline is not None:
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        moved = compare_with_baseline(report, baseline)
        if moved:
            status = 1
            print(f"baseline {args.baseline}: {len(moved)} lines moved")
            for line in moved:
                print(f"  {line}")
        else:
            print(f"baseline {args.baseline}: nothing moved")
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"report written to {args.out}")
    return status


if __name__ == "__main__":
    sys.exit(main())
