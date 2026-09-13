"""Post-observation, call-free ceiling diagnosis on immutable in-memory sheets."""

from __future__ import annotations

import dataclasses
import json
import os
import runpy
from pathlib import Path

_RUNNER = runpy.run_path(str(Path(__file__).with_name("run.py")))
HERE, RUN, load, save, sha = (_RUNNER[key] for key in ("HERE", "RUN", "load", "save", "sha"))


def main():
    _RUNNER["lock"]()
    if load(RUN / "progress.json")["status"] == "running":
        raise RuntimeError("Wait for the live continuation to finish")
    os.environ["LITHARNESS_ENV"] = "test"
    from litharness.adapters.sqlite_store import SqliteStore
    from litharness.domain import gamesystem as gs

    database = RUN / "continuation/serial.db"
    before = sha(database)
    with SqliteStore.open_read_only(database) as store:
        [(book, branch, _)] = store.branches()
        records = store.state_records(book, branch)
    sheet = gs.sheet_of(records, "wren", at="s000004")
    if sheet is None or sheet.magnitude("load") != 1:
        raise RuntimeError("Chapter 4 does not provide the expected held Load control")
    rise = next(move for move in gs.legal_moves(sheet) if move.kind is gs.AdvanceKind.RISE)
    funded = gs.advance(sheet, rise, at="s000006").sheet
    raised = dataclasses.replace(
        funded,
        system=dataclasses.replace(
            funded.system,
            scale=dataclasses.replace(funded.system.scale, maximum=2),
        ),
    )

    def describe(item):
        moves = gs.legal_moves(item)
        deepen = [
            move
            for move in moves
            if move.kind is gs.AdvanceKind.DEEPEN and move.ability_id == "load"
        ]
        spent = gs.advance(item, deepen[0], at="s000006") if deepen else None
        return {
            "scale_maximum": item.system.scale.maximum,
            "rank_id": item.rank_id,
            "magnitudes": dict(item.magnitudes),
            "load_deepening_available": bool(deepen),
            "duration_gain_available": any(
                move.kind is gs.AdvanceKind.GAIN and move.ability_id == "duration" for move in moves
            ),
            "after_load_deepening": dict(spent.sheet.magnitudes) if spent else None,
        }

    result = {
        "schema": "litharness.next-priorities-ceiling-diagnostic.v1",
        "model_calls": 0,
        "design_timing": "post-observation: designed after reading the accepted Chapter 4",
        "script_sha256": sha(Path(__file__)),
        "database_sha256": before,
        "actual_chapter_four": describe(sheet),
        "funded_current_ceiling": describe(funded),
        "funded_ceiling_two_control": describe(raised),
        "database_unchanged": sha(database) == before,
        "limitation": (
            "The in-memory rank grant and raised ceiling are controls, not accepted story "
            "events or a production fix. They test a second Load investment, not an unbounded "
            "progression representation."
        ),
    }
    save(HERE / "progression-probe.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
