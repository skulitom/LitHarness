"""Reuse frozen provenance readers and locate the actual changed prompt contracts."""

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
    spec = importlib.util.spec_from_file_location("_scene_focus_" + name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for key in ("HERE", "ROOT", "RUN", "BOOK", "BASE", "load", "save", "sha"):
        setattr(module, key, RUNNER[key])
    module.RUNNER = RUNNER
    return module


def main():
    from litharness.application import outline
    from litharness.domain import house
    from litharness.domain.scene_brief import TREATMENT

    with contextlib.redirect_stdout(io.StringIO()):
        reader("audit").main()
        reader("readout").main()
    evidence, readout = load(HERE / "evidence.json"), load(HERE / "readout.json")
    contracts = []
    writers = 0
    for call in evidence["calls"]:
        request = load(ROOT / call["path"])["request"]
        if request["profile"] == outline.CONCEPT_PROFILE:
            rules = json.loads(request["prompt"])["rules"]
            controls = {
                "all_concept_handoff_rules_present": all(
                    rule in rules for rule in outline.SCENE_HANDOFF_RULES
                ),
                "prose_clarity_absent_from_planner": house.SCENE_CLARITY not in request["system"],
            }
        elif request["profile"] == "default" and "Now write " in request["prompt"]:
            writers += 1
            controls = {
                "named_viewpoint_clarity_present": house.SCENE_CLARITY in request["system"],
                "selective_treatment_present": TREATMENT in request["prompt"],
                "scene_offer_correctly_scoped": (
                    (house.SCENE_MAGICAL_OFFER in request["system"]) == (writers == 1)
                ),
                "old_magical_offer_absent": house._MAGICAL_OFFER not in request["system"],
                "planner_directions_absent_from_writer": all(
                    rule not in request["system"] + request["prompt"]
                    for rule in outline.SCENE_HANDOFF_RULES
                ),
            }
        else:
            continue
        contracts.append({"path": call["path"], "sha256": call["sha256"], "controls": controls})
    readout.update(
        analysis_stage="registered",
        analysis_scripts={
            p.relative_to(ROOT).as_posix(): sha(p)
            for p in (Path(__file__), RUNNER["PREVIOUS"].with_name("readout.py"))
        },
        prompt_contracts=contracts,
    )
    save(HERE / "readout.json", readout)
    print(
        json.dumps(
            {
                "status": evidence["status"],
                "fatal": evidence["fatal"],
                "native_tokens": evidence["native_tokens"],
                "profiles": evidence["profiles"],
                "contracts": contracts,
                "seed_preserved": all(
                    row["seed_preservation"]["all_preserved_with_expected_authority"]
                    for row in readout["checkpoints"]
                ),
                "mechanics_unchanged": all(
                    row["all_system_fields_except_manifestation_text_unchanged"]
                    for row in readout["checkpoints"]
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
