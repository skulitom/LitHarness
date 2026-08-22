"""Re-materialise a `litharness forge --pick` bundle from the committed world package.

**Why this exists.** `pilot2/` was gitignored and is gone from this machine, and with it the
`seed.json` / `directives.json` / `promises.json` that `tools/serial-pilot-2-setup.ps1`
refuses to run without. What is committed is the *source*: the Architect's own answer
(`plan/serial-pilot-2-world.json`), and the two files `--pick` wrote out of it. Re-forging
would cost $1.53, produce a different world, and need a person to choose again — so a rerun
on the same world has to re-materialise the bundle rather than re-make it.

**It does not re-make the operator's choice, and that is the whole rail.** The pick is
recorded — `picked` in the world package, taken on 2026-08-22 and written to the store as its
own `architect.pick.v0` policy decision with `VerdictSource.HUMAN`. This tool reads that
number and reproduces the files that choice produced. It touches no database, records no
decision, ranks nothing and calls no model: a second `HUMAN`-sourced decision row minted by a
script would be a machine wearing a person's authority, which is the one thing
`plan/world-architect.md` §2 splits `forge` into two commands to prevent.

**What is derived and what has to be supplied.** Everything `cmd_forge` puts in a bundle is a
pure function of the world and the architect id — including the three uuids, which are
`uuid5` over `litharness://forge/{architect_id}/{index}/{book,branch,revision}` and therefore
reproduce exactly. The one input that is not recoverable is `meta.created_at`, the forge run's
wall-clock stamp. It is minted fresh, printed, and named in the run record; no record depends
on it (`records_for` does not take it), so the seed's 329 records are byte-identical either
way, and `litharness new --state` re-keys the snapshot onto the book it creates in any case.

    uv run python tools/rematerialise_forge_bundle.py --out pilot2/direct2c

Then the ordinary path, unchanged:

    .\\tools\\serial-pilot-2-setup.ps1 -Forge pilot2\\direct2c -Scenes 8 -Database serial2c.db
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import litharness_contracts as lc  # noqa: E402

from litharness.application import architect  # noqa: E402
from litharness.domain import worlds  # noqa: E402

#: The committed source, and the two files `--pick` wrote from it. Defaults rather than
#: constants: the tool is about the shape of a forge bundle, and Serial Pilot 2 is the one
#: package that currently has this shape committed.
DEFAULT_WORLD = REPO / "plan" / "serial-pilot-2-world.json"
DEFAULT_DIRECTIVES = REPO / "plan" / "serial-pilot-2-directives.json"
DEFAULT_PROMISES = REPO / "plan" / "serial-pilot-2-promises.json"


class BundleFault(Exception):
    """The committed files do not describe the bundle they are being asked to rebuild."""


def _forge_uuid(architect_id: str, index: int, part: str) -> str:
    """`cmd_forge`'s own id derivation, reproduced rather than re-minted.

    The ids are `uuid5` over a namespaced url, so they are a function of the architect id and
    the candidate's place in the answer — which means a re-materialised bundle carries the
    same ids the original did, and "mint fresh ids only where the snapshot demands them"
    demands none of these.
    """
    return str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"litharness://forge/{architect_id}/{index}/{part}")
    )


def bundle_files(
    *,
    world_path: Path,
    directives_path: Path,
    promises_path: Path,
    scenes: int,
    created_at: str,
) -> dict[str, str]:
    """`{filename: text}` for the three files `forge --pick` writes. Pure; writes nothing.

    Every consistency check the committed pair can be given is made here rather than left to
    the run: the directives and promises files must be the ones **this** world produces, or
    the bundle would stand a book up on one world's canon and another world's debts, and
    nothing downstream would notice — `new --state` imports whatever snapshot it is handed.
    """
    package = json.loads(world_path.read_text(encoding="utf-8"))
    picked = package.get("picked")
    if not isinstance(picked, int) or isinstance(picked, bool) or picked < 1:
        raise BundleFault(
            f"{world_path} records no operator pick ({picked!r}); this tool re-materialises a "
            "choice that was made, and cannot make one"
        )
    architect_id = str(package["architect_id"])
    candidate = architect.Candidate(picked - 1, package["world"])

    complaints = architect.gate_candidate(candidate, scenes=scenes)
    if complaints:
        raise BundleFault(
            f"the picked world no longer clears its own gates at {scenes} scenes: "
            + "; ".join(complaints)
        )

    directives = json.loads(directives_path.read_text(encoding="utf-8"))
    promises = json.loads(promises_path.read_text(encoding="utf-8"))
    if [dict(item) for item in architect.directives_for(candidate)] != directives["directives"]:
        raise BundleFault(f"{directives_path} is not the directive set this world produces")
    if [dict(item) for item in architect.promises_for(candidate)] != promises:
        raise BundleFault(f"{promises_path} is not the promise set this world produces")
    if directives.get("scenes") != scenes:
        raise BundleFault(
            f"{directives_path} was written for {directives.get('scenes')} scenes, not {scenes}; "
            "a story key minted at one length is not comparable to a beat key minted at another"
        )

    snapshot = architect.snapshot_for(
        candidate,
        book_id=_forge_uuid(architect_id, candidate.index, "book"),
        branch_id=_forge_uuid(architect_id, candidate.index, "branch"),
        revision_id=_forge_uuid(architect_id, candidate.index, "revision"),
        architect_id=architect_id,
        created_at=created_at,
        # The one place a forged world becomes canon, and it is the operator's recorded choice
        # that carries it — `cmd_forge --pick`'s comment, and the reason this tool refuses a
        # package with no `picked`.
        authority=lc.StateAuthority.ACCEPTED_CANON,
        scenes=scenes,
    )
    faults = worlds.validate(snapshot.records)
    if faults:
        raise BundleFault("the regenerated snapshot does not validate: " + "; ".join(faults))

    return {
        "seed.json": json.dumps(lc.to_jsonable(snapshot), ensure_ascii=False, indent=2),
        "directives.json": json.dumps(directives, ensure_ascii=False, indent=2),
        "promises.json": json.dumps(promises, ensure_ascii=False, indent=2),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, help="directory to write the bundle into")
    parser.add_argument("--world", type=Path, default=DEFAULT_WORLD)
    parser.add_argument("--directives", type=Path, default=DEFAULT_DIRECTIVES)
    parser.add_argument("--promises", type=Path, default=DEFAULT_PROMISES)
    parser.add_argument("--scenes", type=int, default=8)
    parser.add_argument(
        "--created-at",
        default=None,
        help="ISO-8601 stamp for the snapshot's ArtifactMeta. Defaults to now; no record "
        "depends on it, and it is the one field the committed package cannot recover.",
    )
    args = parser.parse_args(argv)

    created_at = args.created_at or (
        datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    )
    try:
        files = bundle_files(
            world_path=args.world,
            directives_path=args.directives,
            promises_path=args.promises,
            scenes=args.scenes,
            created_at=created_at,
        )
    except BundleFault as error:
        print(f"rematerialise: REFUSED - {error}", file=sys.stderr)
        return 2

    out = Path(args.out)
    # **Refuses rather than overwrites**, for `serial-pilot-2-setup.ps1`'s reason one step
    # earlier: a bundle silently replaced under a directory a run already used is a book whose
    # canon nobody can name afterwards.
    existing = [name for name in files if (out / name).exists()]
    if existing:
        print(
            f"rematerialise: REFUSED - {out} already holds {', '.join(sorted(existing))}. "
            "Pass a fresh --out.",
            file=sys.stderr,
        )
        return 2
    out.mkdir(parents=True, exist_ok=True)

    package = json.loads(args.world.read_text(encoding="utf-8"))
    print(f"rematerialise: {args.world}")
    print(
        f"  world {package['picked']} of {package['k']}, {package['world']['title']!r}: the "
        "operator's recorded pick, re-materialised and not re-made"
    )
    print(f"  created_at  {created_at}  (minted here; no record depends on it)")
    for name, text in files.items():
        path = out / name
        path.write_text(text, encoding="utf-8")
        digest = sha256(text.encode("utf-8")).hexdigest()[:16]
        print(f"  {name:<16} {path}  sha256:{digest}")
    snapshot = json.loads(files["seed.json"])
    print(f"  {len(snapshot['records'])} records, validate clean")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
