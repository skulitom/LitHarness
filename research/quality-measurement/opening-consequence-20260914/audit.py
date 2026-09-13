"""Frozen provenance readers plus exact author-direction delivery and preservation."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import runpy
from pathlib import Path

RUNNER = runpy.run_path(str(Path(__file__).with_name("run.py")))
HERE, ROOT, RUN, BOOK, BASE, load, save, sha = (
    RUNNER[k] for k in ("HERE", "ROOT", "RUN", "BOOK", "BASE", "load", "save", "sha")
)


def reader(name):
    path = RUNNER["PREVIOUS"].with_name(name + ".py")
    spec = importlib.util.spec_from_file_location("_opening_consequence_" + name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for key in ("HERE", "ROOT", "RUN", "BOOK", "BASE", "load", "save", "sha"):
        setattr(module, key, RUNNER[key])
    module.RUNNER = RUNNER
    return module


def main():
    from litharness.adapters.sqlite_store import SqliteStore
    from litharness.application import outline
    from litharness.domain import house
    from litharness.domain.scene_brief import TREATMENT

    with contextlib.redirect_stdout(io.StringIO()):
        reader("audit").main()
        reader("readout").main()
    evidence, readout = load(HERE / "evidence.json"), load(HERE / "readout.json")
    directions = load(HERE / "directions.json")["pre_registration"]
    contracts, writers = [], 0
    for call in evidence["calls"]:
        request = load(ROOT / call["path"])["request"]
        if request["profile"] == outline.CONCEPT_PROFILE:
            payload = json.loads(request["prompt"])
            actual = {item["text"] for item in payload.get("author_locks", [])}
            controls = {
                "all_directions_in_outline_locks": set(directions.values()) <= actual,
                "same_six_chapter_allocation": (
                    [item.get("chapter") for item in payload["scenes"]] == list(range(1, 7))
                ),
                "same_target_words": payload.get("target_scene_words") == 1800,
                "same_concept_handoff_rules": all(
                    rule in payload["rules"] for rule in outline.SCENE_HANDOFF_RULES
                ),
            }
        elif request["profile"] == "default" and "Now write " in request["prompt"]:
            writers += 1
            controls = {
                "all_directions_in_writer_system": all(
                    body in request["system"] for body in directions.values()
                ),
                "same_named_viewpoint_clarity": house.SCENE_CLARITY in request["system"],
                "same_selective_treatment": TREATMENT in request["prompt"],
                "scene_offer_correctly_scoped": (
                    (house.SCENE_MAGICAL_OFFER in request["system"]) == (writers == 1)
                ),
                "old_magical_offer_absent": house._MAGICAL_OFFER not in request["system"],
            }
        else:
            continue
        contracts.append({"path": call["path"], "sha256": call["sha256"], "controls": controls})
    lock_checks = []
    for database in sorted(BOOK.glob("*/serial.db")):
        before = sha(database)
        with SqliteStore.open_read_only(database) as store:
            [(book, branch, _)] = store.branches()
            actual = {item.text for item in store.plan_items(book, branch) if item.locked}
        lock_checks.append({
            "database": database.relative_to(ROOT).as_posix(), "sha256": before,
            "all_directions_preserved": set(directions.values()) <= actual,
            "database_unchanged": sha(database) == before,
        })
    readout.update(
        analysis_stage="registered",
        analysis_scripts={
            p.relative_to(ROOT).as_posix(): sha(p)
            for p in (Path(__file__), RUNNER["PREVIOUS"].with_name("readout.py"))
        },
        direction_file_sha256=sha(HERE / "directions.json"),
        prompt_contracts=contracts, direction_preservation=lock_checks,
    )
    save(HERE / "readout.json", readout)
    print(json.dumps({
        "status": evidence["status"], "fatal": evidence["fatal"],
        "native_tokens": evidence["native_tokens"], "profiles": evidence["profiles"],
        "prompt_contracts": contracts, "direction_preservation": lock_checks,
    }, indent=2))


if __name__ == "__main__":
    main()
