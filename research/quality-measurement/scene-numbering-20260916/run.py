"""Isolated request transformation; production source and stored concepts stay frozen."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = ROOT / "runs/scene-numbering-20260916"
PARENT = ROOT / "runs/beat-labels-20260915"
SUPPORT = HERE.parent / "beat-labels-20260915/run.py"
RECIPE = ROOT / "runs/scene-numbering-recipe-20260916.json"
TEST = ROOT / "tests/test_scene_numbering_experiment.py"
REVISION = "7552d36"

spec = importlib.util.spec_from_file_location("numbering_support", SUPPORT)
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
base = previous.base


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def transform_prompt(prompt, recipe):
    """Apply only predeclared spans in generated arc fields and generated debt coordinates."""
    if digest(prompt) != recipe["source_prompt_sha256"]:
        raise ValueError("Outline input differs from the registered source")
    payload = json.loads(prompt)
    concept = payload["book_concept"]
    for edit in recipe["edits"]:
        field = edit["field"]
        if field not in {"middle", "closes"}:
            raise ValueError("Only generated arc middle/close spans may be changed")
        text = concept["first_arc"][field]
        if not edit["before"] or text.count(edit["before"]) != 1:
            raise ValueError("Registered span must occur exactly once")
        concept["first_arc"][field] = text.replace(edit["before"], edit["after"], 1)
    if [debt.get("due_scene") for debt in concept["debts"]] != recipe["due_scenes"]:
        raise ValueError("Generated debt coordinates differ from registration")
    for debt in concept["debts"]:
        debt["due_scene"] = None
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)


def request_control(control, treatment, original, recipes=None):
    if control != original:
        raise ValueError("Control differs from the previous frozen outline request")
    recipes = recipes if recipes is not None else base.read(RECIPE)
    matches = [value for value in recipes.values()
               if value["source_prompt_sha256"] == digest(control["prompt"])]
    if len(matches) != 1:
        raise ValueError("Expected one registered source recipe")
    expected = {**control, "prompt": transform_prompt(control["prompt"], matches[0])}
    if treatment != expected:
        raise ValueError("Treatment differs beyond the registered generated coordinates")
    return True


def install_transform(book):
    from litharness.application import outline

    if book not in {"A2", "B2", "A4", "B4"}:
        raise ValueError("Unregistered book")
    if book[0] == "A":
        return
    recipe = base.read(RECIPE)[book[1]]
    original = outline.render_outline_request

    def rendered(*args, **kwargs):
        request = original(*args, **kwargs)
        if request.profile != "planner.outline.v6":
            raise ValueError("Unexpected outline profile")
        return replace(request, prompt=transform_prompt(request.prompt, recipe))

    outline.render_outline_request = rendered


def configure():
    previous.HERE, previous.LOCAL, previous.PARENT = HERE, LOCAL, PARENT
    previous.__file__ = str(Path(__file__).resolve())
    previous.REVISIONS = {"A": REVISION, "B": REVISION}
    previous.configure()
    base.OWNER = "scene-numbering-20260916: root task;"
    previous.request_control = request_control
    previous.claim = base.claim = claim


def prepare():
    recipes = base.read(RECIPE)
    if set(recipes) != {"2", "4"} or any(
        len(value["edits"]) != 3 or len(value["due_scenes"]) != 4
        for value in recipes.values()
    ):
        raise ValueError("Expected three text spans and four debt coordinates per story")
    previous.prepare()
    manifest = base.read(LOCAL / "manifest.json")
    for path in (SUPPORT, TEST, RECIPE):
        manifest["files"][str(path)] = base.sha(path)
    manifest["contrast"] = {
        "kind": "research_only_outline_request_transform",
        "source_revision": REVISION,
        "recipe_sha256": base.sha(RECIPE),
        "text_spans_per_story": 3,
        "generated_deadlines_per_story": 4,
        "unchanged_profile": "planner.outline.v6",
    }
    base.write(LOCAL / "manifest.json", manifest)
    base.write(HERE / "registration.json", manifest | {
        "manifest_sha256": base.sha(LOCAL / "manifest.json"),
    })
    claim("registered")
    print("Both arms use the same production revision; exact scene-coordinate controls passed.")


def claim(status):
    files = [("registration", HERE / name) for name in ("RUNBOOK.md", "registration.json")]
    if status == "observed":
        files.append(("derived_result", HERE / "evidence.json"))
        if (HERE / "handoff-evidence.json").exists():
            files.append(("control_result", HERE / "handoff-evidence.json"))
    base.write(HERE / "claim.json", {
        "schema": "litharness.epistemic-claim.v1",
        "claim_id": "generated-scene-coordinates-20260916",
        "statement": "The fixed-story comparison records outlines and opening chapters with "
                     "generated arc scene references and generated debt scene coordinates "
                     "removed from the treatment outline request; no quality effect is licensed.",
        "status": status,
        "artifacts": [{"kind": kind, "path": p.relative_to(ROOT).as_posix(), "sha256": base.sha(p)}
                      for kind, p in files],
    })


def run():
    for path in (TEST, SUPPORT):
        committed = subprocess.check_output(
            ["git", "show", f"HEAD:{path.relative_to(ROOT).as_posix()}"], cwd=ROOT,
        )
        if committed != path.read_bytes():
            raise RuntimeError("Research runner support and tests must be committed")
    previous.run()


def audit():
    previous.audit()
    evidence = base.read(HERE / "evidence.json")
    state = base.read(LOCAL / "progress.json")
    rows = []
    for book in sorted(state["books"]):
        calls = [base.read(LOCAL / c["path"]) for c in state["calls"]
                 if c["book"] == book and c["profile"].startswith("planner.outline.")]
        source = base.read(PARENT / "preflight" / f"B{book[1]}-request.json")
        preflight = base.read(LOCAL / "preflight" / f"{book}-request.json")
        expected = source if book[0] == "A" else {
            **source, "prompt": transform_prompt(source["prompt"], base.read(RECIPE)[book[1]]),
        }
        rows.append({
            "book": book,
            "preflight_equals_registered_request": preflight == expected,
            "all_live_outlines_equal_registered_request": bool(calls)
                and all(c["request"] == expected for c in calls),
            "stored_concept_unchanged": base.sha(base.book_root(book) / "concept/concept.json")
                == base.sha(PARENT / "books" / f"B{book[1]}" / "concept/concept.json"),
        })
    evidence["coordinate_controls"] = rows
    base.write(HERE / "evidence.json", evidence)
    # The inherited handoff collector hashes evidence before these additional controls.
    handoff = base.read(HERE / "handoff-evidence.json")
    handoff["source_hashes"][(HERE / "evidence.json").relative_to(ROOT).as_posix()] = base.sha(
        HERE / "evidence.json",
    )
    handoff["source_hashes"][SUPPORT.relative_to(ROOT).as_posix()] = base.sha(SUPPORT)
    handoff["source_hashes"][RECIPE.relative_to(ROOT).as_posix()] = base.sha(RECIPE)
    base.write(HERE / "handoff-evidence.json", handoff)
    claim("observed")
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    configure()
    mode = sys.argv[1]
    if mode in {"step", "preflight"}:
        install_transform(sys.argv[2])
    if mode == "step":
        base.step(sys.argv[2], sys.argv[3], int(sys.argv[4]))
    elif mode == "preflight":
        previous.coverage.preflight(sys.argv[2])
    elif mode == "collect":
        base.collect(sys.argv[2])
    else:
        {"prepare": prepare, "run": run, "audit": audit}[mode]()
