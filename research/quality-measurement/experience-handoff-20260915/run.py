"""Registered shared-parent experience-handoff experiment; no production mutations.

Freeze and sequential dispatch mechanics derive from experience-first-20260914/run.py.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import secrets
import subprocess
import sys
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = ROOT / "runs/experience-handoff-20260915"
SOURCE_REVISION = "01deb0c"
BINARY = Path("C:/Users/artem/AppData/Local/OpenAI/Codex/bin/bffc5354119c8421/codex.exe")
INPUTS = json.loads((HERE / "inputs.json").read_text(encoding="utf-8"))
BRIEFS = {i: value["premise"] for i, value in INPUTS.items()}
ORDER = tuple(f"{stage}-S-{i}" for stage in ("discovery", "concept") for i in BRIEFS) + tuple(
    f"{stage}-{arm}-{i}"
    for step, stage in enumerate(("outline", "chapter1", "chapter2"))
    for i in BRIEFS
    for arm in ("AB" if (int(i) + step) % 2 else "BA")
)
HANDOFF_NOTE = (
    "These are original prospective creative instructions, not accepted past events. "
    "Plan their specified chapter coverage while respecting the locked premise. "
    "These instructions do not override author locks."
)
DRAFT_TASK = (
    "Write the current chapter of this proposed LitRPG as finished fiction in third person, "
    "past tense, using 1200-1600 words. Develop the supplied current scene handoff. The "
    "original short premise remains binding. Prior narrative, when supplied, contains what "
    "has actually happened in this research episode; continue from it without replaying it. "
    "A planned event missing from that narrative has not already happened merely because "
    "the plan expected it. Future dependencies are future constraints, not events to insert "
    "now. Return only chapter prose in the requested JSON, without a title or commentary."
)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def serial(value):
    return json.loads(json.dumps(dataclasses.asdict(value)))


def schema(field):
    return {"type": "object", "additionalProperties": False, "required": [field],
            "properties": {field: {"type": "string", "minLength": 1}}}


def use_source():
    source = LOCAL / "source/src"
    if not source.is_dir():
        raise RuntimeError("Prepare archived source first")
    if any(key == "litharness" or key.startswith("litharness.") for key in sys.modules):
        raise RuntimeError("Source must be selected before importing litharness")
    sys.path.insert(0, str(source))


def lock():
    if not (ROOT / "runs/box.lock/holder").read_text(encoding="utf-8-sig").startswith(
        "experience-handoff-20260915: root task;"
    ):
        raise RuntimeError("This task does not own the shared-machine lock")


def inputs(index):
    from litharness.domain.invention import InventionSeed

    return BRIEFS[index], InventionSeed.from_payload(read(LOCAL / f"seeds/{index}.json"))


def specification(index):
    return {"instruction": HANDOFF_NOTE, "experience": INPUTS[index]["experience"]}


def valid(stage, payload):
    from jsonschema import validate

    from litharness.application.concept import CONCEPT_SCHEMA, Concept
    from litharness.application.discovery import SCHEMA, Discovery
    from litharness.application.outline import CONCEPT_OUTLINE_SCHEMA, _statements

    shape = {"discovery": SCHEMA, "concept": CONCEPT_SCHEMA,
             "outline": CONCEPT_OUTLINE_SCHEMA}.get(stage, schema("story"))
    validate(payload, shape)
    if stage == "discovery":
        Discovery.from_invention(payload)
    elif stage == "concept":
        Concept.from_payload(payload)
    elif stage == "outline":
        _statements(payload, 2, structured=True)
    elif not payload["story"].strip():
        raise ValueError("Empty output")


def conforms(stage, payload):
    from jsonschema.exceptions import ValidationError

    from litharness.application.outline import OutlineOutputError

    try:
        valid(stage, payload)
    except (ValueError, TypeError, AttributeError, ValidationError, OutlineOutputError):
        return False
    return True


def parent_slots(name):
    if name not in ORDER:
        raise ValueError(name)
    stage, arm, index = name.split("-")
    return {
        "discovery": [],
        "concept": [f"discovery-S-{index}"],
        "outline": [f"discovery-S-{index}", f"concept-S-{index}"],
        "chapter1": [f"outline-{arm}-{index}"],
        "chapter2": [f"outline-{arm}-{index}", f"chapter1-{arm}-{index}"],
    }[stage]


def slot_request(name):
    import litharness_contracts as lc

    from litharness.application.concept import Concept, render_concept_request
    from litharness.application.discovery import Discovery, render_request
    from litharness.application.outline import _statements, render_outline_request
    from litharness.domain.beats import Beat
    from litharness.domain.generation import CompletionRequest
    from litharness.domain.plan_refinement import PlanRevision
    from litharness.domain.scene_brief import render_plan

    names = parent_slots(name)
    stage, arm, index = name.split("-")
    brief, seed = inputs(index)
    parents, lineage, invalid = {}, [], False
    for parent in names:
        path = LOCAL / f"calls/{parent}.json"
        receipt = read(path)
        lineage.append({"slot": parent, "receipt_sha256": sha(path)})
        if receipt["status"] == "skipped":
            invalid = True
            continue
        if receipt["status"] != "completed":
            raise RuntimeError("Designated parent is not complete")
        payload = receipt["result"]["parsed"]
        parent_stage = parent.split("-")[0]
        invalid |= not conforms(parent_stage, payload)
        parents[parent_stage] = payload
    if invalid:
        return None, lineage
    if stage == "discovery":
        full_brief = brief + "\n\nOriginal episode specification:\n" + json.dumps(
            specification(index), ensure_ascii=False, sort_keys=True, indent=2)
        return render_request(full_brief, person="third", seed=seed), lineage
    if stage == "concept":
        return render_concept_request(
            brief, scenes=2, person="third",
            discovery=Discovery.from_invention(parents["discovery"]),
        ), lineage
    if stage == "outline":
        concept = Concept.from_development(
            parents["concept"], Discovery.from_invention(parents["discovery"]),
            author_brief=brief, invention_seed=seed,
        )
        beats = tuple(Beat(f"scene-{i}", i, 2, None, function, "experience.two-episode.v1")
                      for i, function in enumerate(("initial local episode",
                                                    "subsequent local episode"), 1))
        premise = lc.PlanItem(logical_id="premise", kind=lc.PlanKind.PREMISE,
                              text=brief, authority=lc.PlanAuthority.INTENDED, locked=True)
        request = render_outline_request(
            brief, beats, base=PlanRevision("handoff-pilot", "proposed", (premise,)),
            concept=concept, serial_arc_index=1,
            chapter_by_scene={b.logical_id: b.ordinal for b in beats}, target_scene_words=1400,
        )
        if arm == "B":
            payload = json.loads(request.prompt)
            payload["original_episode_specification"] = specification(index)
            request = dataclasses.replace(
                request, prompt=json.dumps(payload, ensure_ascii=False, indent=2))
        return request, lineage
    ordinal = 1 if stage == "chapter1" else 2
    scene = _statements(parents["outline"], 2, structured=True)[ordinal - 1]
    payload = {"original_premise": brief, "chapter": ordinal, "current_scene": render_plan(scene),
               "prior_narrative": None if ordinal == 1 else parents["chapter1"]["story"]}
    return CompletionRequest(
        system=seed.brief + "\n\n" + DRAFT_TASK,
        prompt=json.dumps(payload, ensure_ascii=False, indent=2),
        schema=schema("story"), max_output_tokens=4200, timeout_seconds=600,
    ), lineage


def schema_controls(raw, requested):
    from litharness.providers.codex_schema import prepare_codex_schema

    native, reason, variant = None, None, None
    if requested is not None:
        try:
            native = prepare_codex_schema(requested)
        except ValueError as error:
            reason = str(error)
        variant = ("strict-nullable-optionals.v1" if native is not None
                   else "prompt-only-original.v1")
    return {
        "original_schema": raw.get("schema") == requested,
        "native_schema": raw.get("native_schema") == native,
        "native_schema_reason": raw.get("native_schema_omission_reason") == reason,
        "schema_variant": raw.get("schema_variant") == variant,
        "native_schema_argument": (("--output-schema" in raw.get("argv", []))
                                   == (native is not None)),
    }


def transport_controls(raw, request):
    return {
        "captured_prompt": raw.get("prompt") == request.prompt,
        "captured_system": raw.get("system") == request.effective_system,
        "returncode": raw.get("returncode") == 0,
        "requested_model": raw.get("requested_model") == "gpt-6-astra",
        "effort": raw.get("settings", {}).get("model_reasoning_effort") == "medium",
        "ephemeral": "--ephemeral" in raw.get("argv", []),
        "config_off": "--ignore-user-config" in raw.get("argv", []),
        "rules_off": "--ignore-rules" in raw.get("argv", []),
        "docs_off": "project_doc_max_bytes=0" in raw.get("argv", []),
        "memory_off": "features.memories=false" in raw.get("argv", []),
        "no_tools_allowed": not request.allowed_tools,
        "completion_mode": raw.get("mode") == "completion",
        "no_tool_events": not any(
            event.get("item", {}).get("type") in (
                "command_execution", "mcp_tool_call", "web_search", "file_change")
            for event in raw.get("events", [])
        ),
        **schema_controls(raw, request.schema),
    }

def prepare():
    lock()
    if (LOCAL / "manifest.json").exists() or (LOCAL / "source").exists():
        raise RuntimeError("Already prepared; no input redraw")
    LOCAL.mkdir(parents=True, exist_ok=True)
    source_revision = subprocess.check_output(
        ["git", "rev-parse", SOURCE_REVISION], cwd=ROOT, text=True).strip()
    archive = LOCAL / "source.zip"
    subprocess.run(["git", "archive", "--format=zip", f"--output={archive}", source_revision],
                   cwd=ROOT, check=True)
    target = (LOCAL / "source").resolve()
    with zipfile.ZipFile(archive) as zipped:
        if any(not (target / n).resolve().is_relative_to(target) for n in zipped.namelist()):
            raise RuntimeError("Unsafe archive member")
        zipped.extractall(target)
    use_source()
    from litharness.domain.invention import make_seed

    files = [*target.joinpath("src").rglob("*.py"), target / "uv.lock", BINARY,
             Path(__file__), HERE / "RUNBOOK.md", HERE / "inputs.json",
             ROOT / "tests/test_experience_handoff.py"]
    for index in BRIEFS:
        path = LOCAL / f"seeds/{index}.json"
        write(path, make_seed(str(secrets.randbits(2048))).to_jsonable())
        files.append(path)
    static = [n for n in ORDER if n.startswith("discovery-")]
    for name in static:
        request, lineage = slot_request(name)
        assert not lineage
        path = LOCAL / f"requests/{name}.json"
        write(path, serial(request))
        files.append(path)
    manifest = {"files": {str(p.resolve()): sha(p) for p in files}, "order": ORDER,
                "binary": str(BINARY), "attempt_stop": 32, "token_stop": 1000000,
                "admission_seconds": 7200, "source_revision": source_revision}
    write(LOCAL / "manifest.json", manifest)
    registration = {"schema": "experience-handoff.registration.v1", "order": ORDER,
                    "manifest_sha256": sha(LOCAL / "manifest.json"),
                    "source_revision": source_revision, "archive_sha256": sha(archive),
                    "files": {str(p.relative_to(ROOT)): sha(p)
                              for p in files if p.is_relative_to(ROOT)},
                    "binary_sha256": sha(BINARY), "call_limit": 32,
                    "token_admission_limit": 1000000, "time_admission_seconds": 7200,
                    "static_requests": {n: sha(LOCAL / f"requests/{n}.json") for n in static}}
    write(HERE / "registration.json", registration)
    write(HERE / "claim.json", {
        "schema": "litharness.epistemic-claim.v1",
        "claim_id": "experience-handoff-feasibility-20260915",
        "status": "registered", "statement":
        "Carrying an original episode specification into the outline may change "
        "its transmission into a two-chapter episode from shared discovery and concept parents.",
        "artifacts": [{"kind": "registration",
                       "path": (HERE / "registration.json").relative_to(ROOT).as_posix(),
                       "sha256": sha(HERE / "registration.json")}],
    })
    print("Prepared 4 static requests and 28 dependent slots; zero generation calls.")


def verify_frozen():
    registration = read(HERE / "registration.json")
    if sha(LOCAL / "manifest.json") != registration["manifest_sha256"]:
        raise RuntimeError("Manifest changed")
    manifest = read(LOCAL / "manifest.json")
    changed = [p for p, digest in manifest["files"].items() if sha(p) != digest]
    if changed:
        raise RuntimeError("Frozen-file drift: " + ", ".join(changed))
    return manifest


def run():
    lock()
    if (LOCAL / "progress.json").exists():
        raise RuntimeError("Already dispatched; no implicit resume")
    if os.environ.get("LITHARNESS_ENV") == "test":
        raise RuntimeError("Generation disabled in tests")
    relative = (HERE / "registration.json").relative_to(ROOT).as_posix()
    for ref in ("HEAD", "origin/main"):
        committed = subprocess.check_output(["git", "show", f"{ref}:{relative}"], cwd=ROOT)
        if json.loads(committed) != read(HERE / "registration.json"):
            raise RuntimeError("Commit and push registration before dispatch")
    manifest = verify_frozen()
    use_source()
    from litharness.providers.codex_cli import CodexCliProvider

    provider = CodexCliProvider(binary=manifest["binary"], trace_directory=LOCAL / "transport")
    progress = {"attempts": 0, "tokens": 0, "status": "running", "slots": [],
                "started_at": datetime.now(UTC).isoformat()}
    started = time.monotonic()
    write(LOCAL / "progress.json", progress)
    try:
        for name in ORDER:
            lock()
            verify_frozen()
            request, lineage = slot_request(name)
            if request is None:
                row = {"name": name, "status": "skipped", "lineage": lineage,
                       "reason": "Invalid designated parent; no substitution"}
                write(LOCAL / f"calls/{name}.json", row)
                progress["slots"].append({"name": name, "status": "skipped"})
                write(LOCAL / "progress.json", progress)
                continue
            if (progress["attempts"] >= manifest["attempt_stop"]
                    or progress["tokens"] >= manifest["token_stop"]
                    or time.monotonic() - started >= manifest["admission_seconds"]):
                raise RuntimeError("Registered new-call limit reached")
            path = LOCAL / f"requests/{name}.json"
            prepared = serial(request)
            if path.exists() and read(path) != prepared:
                raise RuntimeError("Frozen request changed")
            if not path.exists():
                write(path, prepared)
            row = {"name": name, "status": "started", "lineage": lineage, "request": prepared,
                   "request_sha256": sha(path), "started_at": datetime.now(UTC).isoformat()}
            write(LOCAL / f"calls/{name}.json", row)
            progress["attempts"] += 1
            progress["active"] = name
            write(LOCAL / "progress.json", progress)
            print(f"Starting {name}", flush=True)
            try:
                result = provider.complete(request)
                row.update(status="completed", result=serial(result))
                if result.usage.total <= 0:
                    raise RuntimeError("Unknown usage; stop")
                progress["tokens"] += result.usage.total
                if not all(transport_controls(result.raw, request).values()):
                    raise RuntimeError("Transport containment or request audit failed")
            except Exception as error:
                row.update(status="failed", error=str(error), raw=provider.last_attempt)
                raise
            finally:
                row["finished_at"] = datetime.now(UTC).isoformat()
                write(LOCAL / f"calls/{name}.json", row)
                progress["slots"].append({"name": name, "status": row["status"]})
                progress["elapsed_seconds"] = round(time.monotonic() - started, 2)
                write(LOCAL / "progress.json", progress)
            print(f"Completed {name}; cumulative tokens {progress['tokens']}", flush=True)
        progress["status"] = "complete"
    except Exception as error:
        progress.update(status="stopped", error=str(error))
        raise
    finally:
        progress["finished_at"] = datetime.now(UTC).isoformat()
        write(LOCAL / "progress.json", progress)


def audit():
    verify_frozen()
    if read(LOCAL / "progress.json")["status"] == "running":
        raise RuntimeError("No reading or audit until dispatch stops")
    use_source()
    controls, outputs, sessions, reading = {}, [], [], []
    for name in ORDER:
        path = LOCAL / f"calls/{name}.json"
        if not path.exists():
            outputs.append({"name": name, "status": "not_reached"})
            continue
        row = read(path)
        request, lineage = slot_request(name)
        entry = {"name": name, "status": row["status"], "receipt_sha256": sha(path),
                 "lineage": lineage}
        if "result" in row:
            entry["usage"] = row["result"]["usage"]
        controls[name] = {"lineage": lineage == row["lineage"]}
        if row["status"] == "skipped":
            controls[name]["invalid_parent"] = request is None
        elif row["status"] == "completed":
            result, raw = row["result"], row["result"]["raw"]
            prepared = read(LOCAL / f"requests/{name}.json")
            controls[name].update({
                "renderer": prepared == serial(request) == row["request"],
                "request_hash": row["request_sha256"] == sha(LOCAL / f"requests/{name}.json"),
                **transport_controls(raw, request),
            })
            ids = [e["thread_id"] for e in raw["events"] if e.get("type") == "thread.started"]
            sessions.extend(ids)
            entry["valid"] = conforms(name.split("-")[0], result["parsed"])
            entry.update(usage=result["usage"], session_ids=ids,
                         started_at=row["started_at"], finished_at=row["finished_at"])
            payload = result["parsed"]
            prose = (payload["story"] if name.startswith("chapter") and entry["valid"]
                     else result["text"] if payload is None
                     else json.dumps(payload, ensure_ascii=False, indent=2))
            entry["rendered_words"] = len(prose.split())
            entry["text_sha256"] = hashlib.sha256(prose.encode()).hexdigest()
            copy = LOCAL / f"reading/{name}.md"
            copy.parent.mkdir(parents=True, exist_ok=True)
            copy.write_text(prose + "\n", encoding="utf-8", newline="\n")
            reading.append(f"- [{name}](reading/{name}.md)")
        outputs.append(entry)
    completed = sum(o["status"] == "completed" for o in outputs)
    controls["sessions"] = {"distinct_completed": len(sessions) == len(set(sessions)) == completed}
    controls["seeds"] = {"distinct": len({inputs(i)[1].brief for i in BRIEFS}) == 4}
    for index in BRIEFS:
        paths = [LOCAL / f"calls/outline-{arm}-{index}.json" for arm in "AB"]
        if all(p.exists() and read(p)["status"] == "completed" for p in paths):
            a, b = (read(p) for p in paths)
            ra, rb = dict(a["request"]), dict(b["request"])
            pa, pb = json.loads(ra.pop("prompt")), json.loads(rb.pop("prompt"))
            added = pb.pop("original_episode_specification", None)
            controls[f"pair-{index}"] = {
                "shared_parents": a["lineage"] == b["lineage"],
                "same_nonprompt_request": ra == rb,
                "one_added_field": pa == pb,
                "original_specification": added == specification(index),
            }
    progress = read(LOCAL / "progress.json")
    controls["accounting"] = {
        "attempts": progress["attempts"] == sum(o["status"] != "skipped" and
            o["status"] != "not_reached" for o in outputs),
        "known_tokens": progress["tokens"] == sum(
            sum(o.get("usage", {}).values()) for o in outputs),
    }
    evidence = {"registration_sha256": sha(HERE / "registration.json"), "outputs": outputs,
                "controls": controls,
                "all_controls_pass": all(all(v.values()) for v in controls.values()),
                "progress": progress}
    write(HERE / "evidence.json", evidence)
    (LOCAL / "READING.md").write_text(
        "# All reached outputs\n\n" + "\n".join(reading) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"completed": completed, "controls_pass": evidence["all_controls_pass"],
                      "run_status": progress["status"]}))
    if not evidence["all_controls_pass"]:
        raise RuntimeError("Audit failed; preserve outputs")


if __name__ == "__main__":
    {"prepare": prepare, "run": run, "audit": audit}[sys.argv[1]]()
