"""Registered, first-output-only experience-before-discovery feasibility pilot."""

from __future__ import annotations

import dataclasses
import hashlib
import itertools
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
LOCAL = ROOT / "runs/experience-first-20260914"
SOURCE_REVISION = "78dfe30"
BINARY = Path("C:/Users/artem/AppData/Local/OpenAI/Codex/bin/bffc5354119c8421/codex.exe")
BRIEFS = {
    "1": "A LitRPG about the satisfaction of becoming able to perform a difficult physical "
         "activity with growing control, and wanting to try it again for its own sake.",
    "2": "A LitRPG about the satisfaction of learning to make something personally desired, "
         "with acquired skill allowing the protagonist to make choices previously beyond them.",
    "3": "A LitRPG about the pleasure of trying a magical possibility, discovering an "
         "unexpected result, and wanting to investigate what else it permits.",
    "4": "A LitRPG about the pleasure of understanding a puzzling place through exploration, "
         "with each discovery making another personally interesting question approachable.",
    "5": "A LitRPG about the pleasure of finding companions who enjoy a shared pursuit, "
         "with improving abilities creating new things they want to attempt together.",
    "6": "A LitRPG about the pleasure of becoming part of a place and its people, with "
         "growing magical ability giving the protagonist a personally meaningful role there.",
}
PERMUTATIONS = list(itertools.permutations("ABC"))
BLOCKS = [(str(i), arms) for i, arms in enumerate(PERMUTATIONS, 1)]
ORDER = tuple(
    f"{stage}-{arm}-{index}"
    for stage in ("pre", "discovery", "concept", "outline", "draft")
    for index, arms in BLOCKS for arm in arms if stage != "pre" or arm != "A"
)
COMMON = (
    "Invent an original possibility for the supplied LitRPG brief. Use 450-650 words. "
    "Choose a particular person with an immediate desire, a concrete situation in which "
    "they attempt something, what happens, their response, and a next possibility that "
    "attracts them. Make the intended experience available through these particulars. "
    "Choose stakes and difficulty that suit this experience. This is revisable material "
    "for a future story, not accepted history or an instruction that all of it happens in "
    "the opening chapter. Return only the requested JSON. "
)
REPRESENTATION = {
    "B": "Describe this possibility in planning language, without finished fictional "
         "narration or dialogue.",
    "C": "Write this possibility as a fictional scene in third person, past tense, "
         "without a planning explanation or commentary.",
}
WRAPPER = (
    "\n\nAdditional revisable story proposal:\n{artifact}\n\n"
    "This proposal describes possible future story material. Its events have not happened "
    "and its later capabilities are not the protagonist's starting state. It creates no "
    "author locks or deadlines. Develop the discovery treatment from the original author "
    "brief and this proposal, preserving what serves that brief and revising as needed."
)
DRAFT_TASK = (
    "Write the first chapter of this proposed LitRPG as finished fiction in third person, "
    "past tense. Develop the supplied first scene handoff in 1200-1600 words. The original "
    "author brief remains binding. There is no accepted prose yet. Later-story dependencies "
    "are future constraints, not events or explanations to insert now. Return only the "
    "chapter prose in the requested JSON, without a title, outline or commentary."
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
        "experience-first-20260914: root task;"
    ):
        raise RuntimeError("This task does not own the shared-machine lock")


def inputs(index):
    from litharness.domain.invention import InventionSeed

    return BRIEFS[index], InventionSeed.from_payload(read(LOCAL / f"seeds/{index}.json"))


def pre_request(index, arm):
    from litharness.domain.generation import CompletionRequest

    if arm not in REPRESENTATION:
        raise ValueError("Only B and C have a preliminary proposal")
    brief, seed = inputs(index)
    return CompletionRequest(
        system=seed.brief + "\n\n" + COMMON + REPRESENTATION[arm], prompt=brief,
        schema=schema("artifact"), max_output_tokens=1800, timeout_seconds=600,
    )


def discovery_request(index, artifact=None):
    from litharness.application.discovery import render_request

    brief, seed = inputs(index)
    request = render_request(brief, person="third", seed=seed)
    return request if artifact is None else dataclasses.replace(
        request, prompt=request.prompt + WRAPPER.format(artifact=artifact)
    )


def valid(stage, payload):
    from jsonschema import validate

    from litharness.application.concept import CONCEPT_SCHEMA, Concept
    from litharness.application.discovery import SCHEMA, Discovery
    from litharness.application.outline import CONCEPT_OUTLINE_SCHEMA, _statements

    shape = {"pre": schema("artifact"), "discovery": SCHEMA, "concept": CONCEPT_SCHEMA,
             "outline": CONCEPT_OUTLINE_SCHEMA, "draft": schema("story")}[stage]
    validate(payload, shape)
    if stage == "discovery":
        Discovery.from_invention(payload)
    elif stage == "concept":
        Concept.from_payload(payload)
    elif stage == "outline":
        _statements(payload, 6, structured=True)
    elif not payload["artifact" if stage == "pre" else "story"].strip():
        raise ValueError("Empty output")


def conforms(stage, payload):
    from jsonschema.exceptions import ValidationError

    from litharness.application.outline import OutlineOutputError

    try:
        valid(stage, payload)
    except (ValueError, TypeError, AttributeError, ValidationError, OutlineOutputError):
        return False
    return True


def slot_request(name):
    import litharness_contracts as lc

    from litharness.application.concept import Concept, render_concept_request
    from litharness.application.discovery import Discovery
    from litharness.application.outline import _statements, render_outline_request
    from litharness.domain.beats import SIX_BEAT, Beat
    from litharness.domain.generation import CompletionRequest
    from litharness.domain.plan_refinement import PlanRevision
    from litharness.domain.scene_brief import render_plan

    if name not in ORDER:
        raise ValueError(name)
    stage, arm, index = name.split("-")
    brief, seed = inputs(index)
    if stage == "pre":
        return pre_request(index, arm), []
    if stage == "discovery" and arm == "A":
        return discovery_request(index), []
    stages = {"discovery": ["pre"], "concept": ["discovery"],
              "outline": ["discovery", "concept"], "draft": ["outline"]}[stage]
    parents, lineage, invalid = {}, [], False
    for parent_stage in stages:
        path = LOCAL / f"calls/{parent_stage}-{arm}-{index}.json"
        receipt = read(path)
        lineage.append({"slot": path.stem, "receipt_sha256": sha(path)})
        if receipt["status"] == "skipped":
            invalid = True
            continue
        if receipt["status"] != "completed":
            raise RuntimeError("Designated parent is not complete")
        payload = receipt["result"]["parsed"]
        if not conforms(parent_stage, payload):
            invalid = True
        parents[parent_stage] = payload
    if invalid:
        return None, lineage
    if stage == "discovery":
        return discovery_request(index, parents["pre"]["artifact"]), lineage
    if stage == "concept":
        request = render_concept_request(
            brief, scenes=6, person="third",
            discovery=Discovery.from_invention(parents["discovery"]),
        )
        return request, lineage
    if stage == "outline":
        concept = Concept.from_development(
            parents["concept"], Discovery.from_invention(parents["discovery"]),
            author_brief=brief, invention_seed=seed,
        )
        beats = tuple(Beat(f"scene-{i}", i, 6, None, function, SIX_BEAT.template_id)
                      for i, function in enumerate(SIX_BEAT.functions, 1))
        premise = lc.PlanItem(logical_id="premise", kind=lc.PlanKind.PREMISE,
                              text=brief, authority=lc.PlanAuthority.INTENDED, locked=True)
        return render_outline_request(
            brief, beats, base=PlanRevision("pilot", "proposed", (premise,)), concept=concept,
            serial_arc_index=1, chapter_by_scene={b.logical_id: b.ordinal for b in beats},
            target_scene_words=1400,
        ), lineage
    first_scene = _statements(parents["outline"], 6, structured=True)[0]
    return CompletionRequest(
        system=seed.brief + "\n\n" + DRAFT_TASK,
        prompt="Original author brief:\n" + brief + "\n\n" + render_plan(first_scene),
        schema=schema("story"), max_output_tokens=4200, timeout_seconds=600,
    ), lineage


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
             Path(__file__), HERE / "RUNBOOK.md", ROOT / "tests/test_experience_first.py"]
    for index in BRIEFS:
        path = LOCAL / f"seeds/{index}.json"
        write(path, make_seed(str(secrets.randbits(2048))).to_jsonable())
        files.append(path)
    static = [n for n in ORDER if n.startswith(("pre-", "discovery-A-"))]
    for name in static:
        request, lineage = slot_request(name)
        assert not lineage
        path = LOCAL / f"requests/{name}.json"
        write(path, serial(request))
        files.append(path)
    manifest = {"files": {str(p.resolve()): sha(p) for p in files}, "order": ORDER,
                "binary": str(BINARY), "attempt_stop": 84, "token_stop": 2500000,
                "admission_seconds": 10800, "source_revision": source_revision}
    write(LOCAL / "manifest.json", manifest)
    registration = {"schema": "experience-first.registration.v1", "order": ORDER,
                    "manifest_sha256": sha(LOCAL / "manifest.json"),
                    "source_revision": source_revision, "archive_sha256": sha(archive),
                    "files": {str(p.relative_to(ROOT)): sha(p)
                              for p in files if p.is_relative_to(ROOT)},
                    "binary_sha256": sha(BINARY), "call_limit": 84,
                    "token_admission_limit": 2500000, "time_admission_seconds": 10800,
                    "static_requests": {n: sha(LOCAL / f"requests/{n}.json") for n in static}}
    write(HERE / "registration.json", registration)
    write(HERE / "claim.json", {
        "schema": "litharness.epistemic-claim.v1",
        "claim_id": "experience-first-feasibility-20260914",
        "status": "registered", "statement": "A prospective scene before discovery may change "
        "how an intended experience survives into a plan and chapter, beyond extra planning.",
        "artifacts": [{"kind": "registration",
                       "path": (HERE / "registration.json").relative_to(ROOT).as_posix(),
                       "sha256": sha(HERE / "registration.json")}],
    })
    print("Prepared 18 static requests and 66 dependent slots; zero generation calls.")


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
    from litharness.providers.codex_schema import prepare_codex_schema

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
        controls[name] = {"lineage": lineage == row["lineage"]}
        if row["status"] == "skipped":
            controls[name]["invalid_parent"] = request is None
        elif row["status"] == "completed":
            result, raw = row["result"], row["result"]["raw"]
            prepared = read(LOCAL / f"requests/{name}.json")
            controls[name].update({
                "renderer": prepared == serial(request) == row["request"],
                "request_hash": row["request_sha256"] == sha(LOCAL / f"requests/{name}.json"),
                "captured_prompt": raw["prompt"] == request.prompt,
                "captured_system": raw["system"] == request.effective_system,
                "schema": raw["schema"] == request.schema,
                "native_schema": raw["native_schema"] == prepare_codex_schema(request.schema),
                "returncode": raw["returncode"] == 0,
                "model": raw["requested_model"] == "gpt-6-astra",
                "effort": raw["settings"]["model_reasoning_effort"] == "medium",
                "ephemeral": "--ephemeral" in raw["argv"],
                "config_off": "--ignore-user-config" in raw["argv"],
                "rules_off": "--ignore-rules" in raw["argv"],
                "docs_off": "project_doc_max_bytes=0" in raw["argv"],
                "memory_off": "features.memories=false" in raw["argv"],
            })
            ids = [e["thread_id"] for e in raw["events"] if e.get("type") == "thread.started"]
            sessions.extend(ids)
            entry["valid"] = conforms(name.split("-")[0], result["parsed"])
            entry.update(usage=result["usage"], session_ids=ids)
            payload = result["parsed"]
            text = (payload["story"] if name.startswith("draft-") and entry["valid"]
                    else result["text"] if payload is None
                    else json.dumps(payload, ensure_ascii=False, indent=2))
            entry["words"] = len(text.split())
            entry["text_sha256"] = hashlib.sha256(text.encode()).hexdigest()
            copy = LOCAL / f"reading/{name}.md"
            copy.parent.mkdir(parents=True, exist_ok=True)
            copy.write_text(text + "\n", encoding="utf-8", newline="\n")
            reading.append(f"- [{name}](reading/{name}.md)")
        outputs.append(entry)
    completed = sum(o["status"] == "completed" for o in outputs)
    controls["sessions"] = {"distinct": len(sessions) == len(set(sessions)) == completed}
    controls["seeds"] = {"distinct": len({inputs(i)[1].brief for i in BRIEFS}) == 6}
    evidence = {"registration_sha256": sha(HERE / "registration.json"), "outputs": outputs,
                "controls": controls,
                "all_controls_pass": all(all(v.values()) for v in controls.values()),
                "progress": read(LOCAL / "progress.json")}
    write(HERE / "evidence.json", evidence)
    (LOCAL / "READING.md").write_text("# All reached outputs\n\n" + "\n".join(reading) + "\n",
                                      encoding="utf-8", newline="\n")
    print(json.dumps({"completed": completed, "controls_pass": evidence["all_controls_pass"],
                      "run_status": evidence["progress"]["status"]}))
    if not evidence["all_controls_pass"]:
        raise RuntimeError("Audit failed; preserve outputs")


if __name__ == "__main__":
    {"prepare": prepare, "run": run, "audit": audit}[sys.argv[1]]()
