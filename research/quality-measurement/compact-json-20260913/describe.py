"""Post-observation command and world differences; never an input to the live run."""

from __future__ import annotations

import json
import runpy
from collections import Counter
from pathlib import Path

RUNNER = runpy.run_path(str(Path(__file__).with_name("run.py")))
HERE, ROOT, RUN, ORDER, BASE, load, save, sha = (
    RUNNER[k] for k in ("HERE", "ROOT", "RUN", "ORDER", "BASE", "load", "save", "sha")
)


def main():
    if load(RUN / "progress.json")["status"] != "completed":
        raise RuntimeError("Describe only the completed fixed comparison")
    BASE.validate(load(RUN / "manifest.json"))
    evidence = load(HERE / "evidence.json")
    cells = []
    for name in ORDER:
        folder = RUN / name
        initial_path, world_path = folder / "initial-world.json", folder / "result-world.json"
        initial = {r["record_id"] for r in load(initial_path)}
        additions = [r for r in load(world_path)["result"] if r["record_id"] not in initial]
        call = next(c for c in evidence["calls"] if c["cell"] == name
                    and c["profile"].startswith("architect.grow"))
        receipt_path = ROOT / call["path"]
        if sha(receipt_path) != call["sha256"]:
            raise RuntimeError("Receipt changed after the registered audit")
        raw = load(receipt_path)["result"]["raw"]
        commands = [row for line in raw["commands_jsonl"].splitlines()
                    if (row := json.loads(line))["phase"] == "result"]
        counts = Counter(" ".join(c["arguments"][:2]) if isinstance(c["arguments"], list)
                         else "invalid tool request" for c in commands)
        cells.append({"name": name, "world_sha256": sha(world_path),
            "initial_world_sha256": sha(initial_path),
            "verify_sha256": sha(folder / "result-verify.json"),
            "added_record_count": len(additions),
            "added_positions": dict(Counter(r["order_key"] or "timeless" for r in additions)),
            "added_predicates": dict(Counter(r["predicate"] for r in additions)),
            "growth_declarations": [{k: r[k] for k in ("record_id", "subject", "value")}
                                    for r in additions if r["predicate"] == "growth_limit"],
            "commands_by_verb": dict(counts),
            "command_failures": [{"call": c["call"], "error_kind": c.get("error_kind"),
                                  "returncode": c.get("returncode")} for c in commands
                                 if c.get("error") or c.get("returncode") != 0],
            "uncached_input_tokens": call["native_usage"]["input_tokens"]
                                     - call["native_usage"]["cached_input_tokens"]})
    result = {"schema": "litharness.compact-json-description.v1",
        "analysis_stage": "post-observation", "script_sha256": sha(Path(__file__)),
        "evidence_sha256": sha(HERE / "evidence.json"), "cells": cells}
    save(HERE / "trace-summary.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
