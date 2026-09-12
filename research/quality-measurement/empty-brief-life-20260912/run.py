"""A six-call empty-brief ablation using the registered continuation dispatcher."""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import secrets
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = ROOT / "runs/empty-brief-life-20260912"
PARENT = HERE.with_name("past-action-continuity-20260912")
SPEC = importlib.util.spec_from_file_location("empty_brief_dispatch", PARENT / "run.py")
assert SPEC is not None and SPEC.loader is not None
engine = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(engine)
sha, text_sha, read, write = engine.sha, engine.text_sha, engine.read, engine.write
ORDER = ("control-1", "omit-1", "omit-2", "control-2", "control-3", "omit-3")
SENTENCE = (
    "If the author's brief introduces unfamiliar life or intelligence, develop its own "
    "pursuits, relationships and history, with tangible traces inviting contact and "
    "investigation. "
)


def request_for(seed, arm: str):
    from litharness.application import discovery

    request = discovery.render_request("", person="third", seed=seed)
    if arm not in ("control", "omit") or request.system.count(SENTENCE) != 1:
        raise ValueError("Unexpected arm or source sentence")
    return request if arm == "control" else dataclasses.replace(
        request, system=request.system.replace(SENTENCE, "", 1),
    )


def prepare() -> None:
    from litharness.domain.invention import InventionSeed, make_seed

    engine.lock()
    if (LOCAL / "manifest.json").exists():
        raise RuntimeError("Prepared already; never refresh registration")
    original = ROOT / "runs/fresh-chapter-review-20260912/invention-seed.json"
    seeds = [InventionSeed.from_payload(read(original)),
             make_seed(str(secrets.randbits(2048))), make_seed(str(secrets.randbits(2048)))]
    files = {str(p.resolve()): sha(p) for p in (ROOT / "src").rglob("*.py")}
    for p in (original, engine.BINARY, PARENT / "run.py", Path(__file__), HERE / "RUNBOOK.md",
              ROOT / "tests/test_empty_brief_life_experiment.py"):
        files[str(p.resolve())] = sha(p)
    for index, seed in enumerate(seeds, 1):
        path = LOCAL / "seeds" / f"{index}.json"
        write(path, seed.to_jsonable())
        files[str(path.resolve())] = sha(path)
    for name in ORDER:
        arm, index = name.split("-")
        path = LOCAL / "requests" / f"{name}.json"
        write(path, dataclasses.asdict(request_for(seeds[int(index) - 1], arm)))
        files[str(path.resolve())] = sha(path)
    write(LOCAL / "manifest.json", {"files": files, "order": ORDER,
          "binary": str(engine.BINARY), "attempt_stop": 6, "token_stop": 150000})
    write(HERE / "registration.json", {
        "manifest_sha256": sha(LOCAL / "manifest.json"), "order": ORDER,
        "runner_sha256": sha(Path(__file__)), "runbook_sha256": sha(HERE / "RUNBOOK.md"),
        "dispatcher_sha256": sha(PARENT / "run.py"), "source_seed_sha256": sha(original),
        "binary_sha256": sha(engine.BINARY), "sentence_sha256": text_sha(SENTENCE),
        "seeds": {str(i): sha(LOCAL / "seeds" / f"{i}.json") for i in (1, 2, 3)},
        "requests": {n: sha(LOCAL / "requests" / f"{n}.json") for n in ORDER},
        "source_revision": subprocess.check_output(["git", "rev-parse", "HEAD"],
                                                   cwd=ROOT, text=True).strip(),
    })
    print("Prepared six discovery requests; no model calls.")


def run() -> None:
    engine.HERE, engine.LOCAL, engine.ORDER = HERE, LOCAL, ORDER
    engine.run()


def audit() -> None:
    from litharness.application.discovery import Discovery
    from litharness.domain.generation import CompletionRequest

    registration = read(HERE / "registration.json")
    controls, outputs = [], []
    for name in ORDER:
        request = read(LOCAL / "requests" / f"{name}.json")
        row = read(LOCAL / "calls" / f"{name}.json")
        result = row["result"]
        raw = result["raw"]
        controls.extend([
            sha(LOCAL / "requests" / f"{name}.json") == registration["requests"][name],
            raw["prompt"] == request["prompt"], raw["schema"] == request["schema"],
            raw["system"] == CompletionRequest(**request).effective_system,
            raw["returncode"] == 0,
            raw["requested_model"] == "gpt-6-astra",
            raw["settings"]["model_reasoning_effort"] == "medium",
        ])
        try:
            Discovery.from_invention(result["parsed"])
            valid = True
        except (ValueError, TypeError, AttributeError):
            valid = False
        fields = result["parsed"] or {}
        outputs.append({"name": name, "receipt_sha256": sha(LOCAL / "calls" / f"{name}.json"),
                        "valid": valid, "usage": result["usage"],
                        "fields": {k: {"sha256": text_sha(v), "words": len(v.split())}
                                   for k, v in fields.items() if isinstance(v, str)}})
    for index in (1, 2, 3):
        full = read(LOCAL / "requests" / f"control-{index}.json")
        omit = read(LOCAL / "requests" / f"omit-{index}.json")
        controls.append({**full, "system": full["system"].replace(SENTENCE, "", 1)} == omit)
    report = {"all_transport_controls_pass": all(controls), "controls": len(controls),
              "outputs": outputs, "progress": read(LOCAL / "progress.json"),
              "registration_sha256": sha(HERE / "registration.json")}
    write(HERE / "evidence.json", report)
    print(json.dumps(report, indent=2))
    if not all(controls):
        raise RuntimeError("Audit failed")


if __name__ == "__main__":
    {"prepare": prepare, "run": run, "audit": audit}[sys.argv[1]]()
