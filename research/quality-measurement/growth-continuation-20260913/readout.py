"""Post-observation correction for superseded seed proposals and context locators."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import runpy
from pathlib import Path

import litharness_contracts as lc

from litharness.domain import integrity, sheet, state

RUNNER = runpy.run_path(str(Path(__file__).with_name("run.py")))
HERE, ROOT, RUN, BOOK, load, save, sha = (
    RUNNER[k] for k in ("HERE", "ROOT", "RUN", "BOOK", "load", "save", "sha")
)


def seed_preservation(original, current, declared_at):
    """Leave replaced proposals proposed; require every other original to be accepted."""
    replaced = set(integrity.superseded(original, declared_at=declared_at))
    by_id = {r.record_id: r for r in current}
    problems = []
    for record in original:
        actual = by_id.get(record.record_id)
        if actual is None:
            problems.append({"record_id": record.record_id, "reason": "missing"})
            continue
        expected = (
            record.authority if record.record_id in replaced else lc.StateAuthority.ACCEPTED_CANON
        )
        if actual.authority is not expected:
            problems.append(
                {
                    "record_id": record.record_id,
                    "reason": "authority",
                    "expected": expected.value,
                    "actual": actual.authority.value,
                }
            )
        before, after = dataclasses.asdict(record), dataclasses.asdict(actual)
        before.pop("authority")
        after.pop("authority")
        if before != after:
            problems.append({"record_id": record.record_id, "reason": "data_changed"})
    return {
        "original_count": len(original),
        "superseded_ids": sorted(replaced),
        "expected_accepted_count": len(original) - len(replaced),
        "all_preserved_with_expected_authority": not problems,
        "problems": problems,
    }


def mechanics(system):
    value = dataclasses.asdict(system)
    for ability in value["abilities"]:
        ability.pop("manifests_as")
    return value


def snapshot_readout(records):
    """Read at the last attested scene snapshot, never the default opening position."""
    snapshots = [
        r for r in records if r.subject == "wren" and r.predicate == sheet.STATUS_PREDICATE
    ]
    keys = {
        state.order_key_of(r)
        for r in snapshots
        if state.is_canon(r) and state.order_key_of(r) is not None
    }
    if any(state.key_space(k) != state.SCENE_KEYS for k in keys):
        raise RuntimeError("Unexpected snapshot coordinate space; do not guess a cutoff")
    at = max(keys) if keys else None
    folded = sheet.state_as_it_stands(records, at=at)
    return {
        "at": at,
        "subject": None if folded is None else folded[0],
        "values": None if folded is None else folded[1],
        "snapshots": [
            {
                "record_id": r.record_id,
                "order_key": state.order_key_of(r),
                "authority": r.authority.value,
                "value": r.value,
            }
            for r in snapshots
        ],
    }


def main():
    if load(RUN / "progress.json")["status"] == "running":
        raise RuntimeError("Wait until the live run ends")
    RUNNER["validate"](load(RUN / "manifest.json"))
    from litharness.adapters.sqlite_store import SqliteStore
    from litharness.domain import gamesystem as gs

    source = ROOT / "runs/growth-declarations-20260913/wren-seed/serial.db"
    with SqliteStore.open_read_only(source) as store:
        [(book, branch, _)] = store.branches()
        original = store.state_records(book, branch)
        declared_at = store.state_record_times(book, branch)
    evidence = load(HERE / "evidence.json")
    checkpoints = []
    baseline = None
    for checkpoint in evidence["checkpoints"]:
        if not checkpoint["complete"]:
            continue
        folder = BOOK / checkpoint["label"]
        database = folder / "serial.db"
        if sha(database) != checkpoint["database_sha256"]:
            raise RuntimeError("Checkpoint changed since registered audit")
        with SqliteStore.open_read_only(database) as store:
            [(book, branch, _)] = store.branches()
            records = store.state_records(book, branch)
            canon = [r for r in records if state.is_canon(r)]
        [system] = gs.systems_of(canon)
        definition = mechanics(system)
        if baseline is None:
            baseline = definition
        audit = load(folder / "audit.json")
        diagnostic = audit["result"]
        checkpoints.append(
            {
                "label": checkpoint["label"],
                "seed_preservation": seed_preservation(original, records, declared_at),
                "all_system_fields_except_manifestation_text_unchanged": definition == baseline,
                "folded_state": snapshot_readout(records),
                "diagnostic": {
                    "sha256": sha(folder / "audit.json"),
                    "exit_code": audit["exit_code"],
                    "words": diagnostic["words"],
                    "status_column_sets": len(diagnostic["status"]["column_sets"]),
                    "sheet_mismatches": len(diagnostic["sheet"]["mismatches"]),
                    "unresolved_sheet_comparisons": sum(
                        "why" in row for row in diagnostic["sheet"]["scenes"]
                    ),
                },
                "database_unchanged": sha(database) == checkpoint["database_sha256"],
            }
        )
    requests = []
    needles = (
        "load can be gained or deepened repeatedly; no cap is declared",
        "duration can be gained or deepened repeatedly; no cap is declared",
        "loadstitch is held or unheld; it does not deepen",
        "wren can do load at 1",
        "wren stands at rank_1",
    )
    for call in evidence["calls"]:
        path = ROOT / call["path"]
        if sha(path) != call["sha256"]:
            raise RuntimeError("Receipt changed since registered audit")
        row = load(path)
        if row["request"]["profile"] not in {"default", "planner.outline.v1"}:
            continue
        request = row["request"]
        locations = []
        for field in ("system", "prompt"):
            text = request.get(field) or ""
            for needle in needles:
                position = text.find(needle)
                if position >= 0:
                    locations.append(
                        {
                            "text_sha256": hashlib.sha256(needle.encode()).hexdigest(),
                            "field": field,
                            "start": position,
                            "end": position + len(needle),
                        }
                    )
        requests.append(
            {
                "path": call["path"],
                "sha256": call["sha256"],
                "profile": request["profile"],
                "locations": locations,
            }
        )
    result = {
        "schema": "litharness.growth-continuation-readout.v1",
        "analysis_stage": "post-observation",
        "script_sha256": sha(Path(__file__)),
        "registered_evidence_sha256": sha(HERE / "evidence.json"),
        "source_seed_sha256": sha(source),
        "final_database_sha256": sha(BOOK / "serial.db"),
        "seed_acceptance_receipt_sha256": sha(BOOK / "commands/005-seed-accept.json"),
        "checkpoints": checkpoints,
        "request_phrase_hashes": {
            str(i): hashlib.sha256(s.encode()).hexdigest() for i, s in enumerate(needles, 1)
        },
        "requests": requests,
    }
    save(HERE / "readout.json", result)
    print(json.dumps(checkpoints, indent=2))


if __name__ == "__main__":
    main()
