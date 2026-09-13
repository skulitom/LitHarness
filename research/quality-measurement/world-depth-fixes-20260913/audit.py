"""Apply the registered readout without turning an incomplete case into a passing one."""

from __future__ import annotations

import json
from pathlib import Path

from replay import HERE, OLD, ROOT, RUN, load, sha


def audit():
    registration = load(HERE / "registration.json")
    before = load(RUN / "before.json")["results"]
    after = load(RUN / "after.json")["results"]
    controls = {
        "registered_inputs_unchanged": all(
            sha(ROOT / path) == digest for path, digest in registration["inputs"].items()
        ),
        "new_source_unchanged": all(
            sha(RUN / "source" / path) == digest
            for path, digest in registration["source_sha256"].items()
        ),
        "old_source_unchanged": all(
            sha(OLD / "source" / path) == digest
            for path, digest in load(OLD / "manifest.json")["source_sha256"].items()
        ),
        "captured_checks_reproduced": all(
            before[case]["saved_check_reproduced"] for case in ("wren", "opposing")
        ),
        "same_input_material": all(
            before[case]["input_sha256"] == after[case]["input_sha256"] for case in before
        ),
        "synthetic_control_differs": (
            after["wren"]["input_sha256"] != after["explicit_depth_control"]["input_sha256"]
        ),
    }
    cases = {}
    for case, result in after.items():
        maximum = 2 if case == "explicit_depth_control" else 1
        expected_deepening = case == "explicit_depth_control"
        success = (
            not result["completion_reasons"] and len(result["systems"]) == 1
            and result["minted_predicates"] == ["magnitude_scale", "system_digest"]
            and result["systems"][0]["maximum"] == maximum
            and result["systems"][0]["deepening_available"] == expected_deepening
        )
        cases[case] = {
            "input_sha256": result["input_sha256"], "records": result["records"],
            "before_check_ok": before[case]["check"]["ok"],
            "after_check_ok": result["check"]["ok"],
            "before_completion_refusals": len(before[case]["completion_reasons"]),
            "after_completion_refusals": len(result["completion_reasons"]),
            "minted_predicates": result["minted_predicates"], "systems": result["systems"],
            "registered_completion_condition_met": success,
        }
    evidence = {
        "schema": "litharness.world-depth-replay-evidence.v1",
        "audit_sha256": sha(Path(__file__)),
        "registration_sha256": sha(HERE / "registration.json"),
        "raw_sha256": {name: sha(RUN / name) for name in ("before.json", "after.json")},
        "provenance_controls": controls, "cases": cases,
        "all_registered_conditions_met": all(controls.values()) and all(
            case["registered_completion_condition_met"] for case in cases.values()
        ),
        "model_calls": 0,
    }
    (HERE / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n",
                                        encoding="utf-8", newline="\n")
    print(json.dumps({"controls": controls, "all_registered_conditions_met":
                      evidence["all_registered_conditions_met"]}, indent=2))


if __name__ == "__main__":
    audit()
