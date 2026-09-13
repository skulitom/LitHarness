"""Reconstruct fixed pre-check worlds; compare the old and changed completion contracts."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUN = ROOT / "runs/world-depth-fixes-20260913"
OLD = ROOT / "runs/world-runtime-fixes-20260913"
CASES = (
    ("wren", "runs/world-runtime-fixes-20260913/book-1/calls/003.json",
     "f188a24f5ff6e61a536322e76508b5ede95480a412d22890b8e6bfc40e983765"),
    ("opposing", "runs/world-runtime-fixes-20260913/book-2/calls/002.json",
     "53cf54dd3884a151750dc2521a885478307b67fe3967bd2d0bda94b2b32c5193"),
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def material(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def reconstruct(relative):
    import litharness_contracts as lc

    from litharness.adapters.sqlite_store import SqliteStore
    from litharness.application.operations import WorldDeclaration
    from litharness.domain import integrity, worlds

    path = ROOT / relative
    receipt = load(path)
    ids = set()
    for line in receipt["result"]["raw"]["commands_jsonl"].splitlines():
        command = json.loads(line)
        if command["phase"] != "result":
            continue
        args = command.get("arguments", [])
        args = args.get("arguments", []) if isinstance(args, dict) else args
        if args[:2] == ["world", "check"]:
            saved_check = json.loads(command["stdout"])
            break
        if args[:2] == ["world", "declare"]:
            raise RuntimeError("Unregistered individual-write reconstruction")
        if args[:2] != ["world", "declare-batch"]:
            continue
        if command["returncode"] != 0 or "--records" not in args:
            raise RuntimeError("Cannot reconstruct a partial or failed write")
        for item in json.loads(args[args.index("--records") + 1]):
            declaration = WorldDeclaration.from_mapping(item)
            record = worlds.world_record(
                worlds.normalise_id(declaration.subject), declaration.predicate,
                value=declaration.value,
                object_ref=worlds.normalise_id(declaration.object) if declaration.object else None,
                order_key=declaration.order_key, note=declaration.note,
            )
            ids.add(record.record_id)
    else:
        raise RuntimeError("No explicit first check")
    with SqliteStore.open_read_only(path.parent.parent / "serial.db") as store:
        [(book, branch, _)] = store.branches()
        records = [dataclasses.replace(record, authority=lc.StateAuthority.PROPOSED)
                   for record in store.state_records(book, branch) if record.record_id in ids]
        times = store.state_record_times(book, branch)
    if {record.record_id for record in records} != ids:
        raise RuntimeError("A declared identity is missing from the retained store")
    return list(integrity.in_force(records, declared_at=times)), saved_check


def evaluate(records, saved_check=None):
    from litharness.application import world
    from litharness.domain import gamesystem as gs

    checked = world.check(records)
    minted, reasons = gs.completion_records(records)
    definitions = gs.systems_of([*records, *minted])
    return {
        "input_sha256": material([dataclasses.asdict(record) for record in records]),
        "records": len(records), "saved_check_reproduced": checked == saved_check,
        "check": checked, "completion_reasons": list(reasons),
        "minted_predicates": sorted({record.predicate for record in minted}),
        "systems": [{
            "id": system.system_id, "maximum": system.scale.maximum,
            "needs": {ability.ability_id: [[need.ref, need.threshold] for need in ability.needs]
                      for ability in system.abilities},
            "deepening_available": any(move.kind == gs.AdvanceKind.DEEPEN for move in
                                        gs.legal_moves(gs.starting_sheet(system, "probe"))),
        } for system in definitions],
    }


def capture(label):
    import litharness
    from litharness.domain import worlds

    registration = load(HERE / "registration.json")
    committed = subprocess.check_output(
        ["git", "show", "HEAD:" + (HERE / "registration.json").relative_to(ROOT).as_posix()],
        cwd=ROOT,
    )
    assert committed == (HERE / "registration.json").read_bytes()
    for name, digest in registration["inputs"].items():
        assert sha(ROOT / name) == digest, name
    expected = OLD / "source/src" if label == "before" else RUN / "source/src"
    assert Path(litharness.__file__).is_relative_to(expected)
    manifest = load(OLD / "manifest.json")
    source = OLD / "source" if label == "before" else RUN / "source"
    source_hashes = (manifest["source_sha256"] if label == "before"
                     else registration["source_sha256"])
    for name, digest in source_hashes.items():
        assert sha(source / name) == digest, name
    results = {}
    for case, relative, digest in CASES:
        assert sha(ROOT / relative) == digest
        records, saved = reconstruct(relative)
        results[case] = evaluate(records, saved)
        if case == "wren":
            control = []
            changed = 0
            for record in records:
                if (record.subject, record.predicate, record.object_ref) == (
                    "split", "requires", "loadstitch",
                ):
                    assert record.value == 1
                    record = worlds.world_record(
                        "split", "requires", object_ref="loadstitch", value=2,
                    )
                    changed += 1
                control.append(record)
            assert changed == 1
            results["explicit_depth_control"] = evaluate(control)
    for name, digest in registration["inputs"].items():
        assert sha(ROOT / name) == digest, name
    output = RUN / f"{label}.json"
    if output.exists():
        raise RuntimeError("Preserve the first replay output")
    output.write_text(json.dumps({"label": label, "results": results}, indent=2) + "\n",
                      encoding="utf-8", newline="\n")
    print(json.dumps({key: {"reproduced": value["saved_check_reproduced"],
                           "reasons": value["completion_reasons"], "systems": value["systems"]}
                      for key, value in results.items()}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("label", choices=("before", "after"))
    capture(parser.parse_args().label)
