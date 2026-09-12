"""Isolated genre-cue timing contrast, with preselected adaptation, planning and prose."""

from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import json
import os
import random
import secrets
import subprocess
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = ROOT / "runs/invention-genre-deferral-20260912"
PARENT = HERE.with_name("invention-active-seed-20260912")
SPEC = importlib.util.spec_from_file_location("genre_deferral_parent", PARENT / "run.py")
assert SPEC is not None and SPEC.loader is not None
parent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parent)
sha, text_sha, read, write, imports = (
    parent.sha, parent.text_sha, parent.read, parent.write, parent.imports
)
core = parent.parent.parent
ARMS = ("early", "late")
ORDER = (
    "early-1-1", "late-1-1", "late-2-1", "early-2-1",
    "late-1-2", "early-1-2", "early-2-2", "late-2-2",
)
CHAINS = tuple(reversed(ORDER[:4]))
STAGES = ("adapt", "plan", "draft")
EARLY = "Invent original LitRPG story premises in portal fantasy, isekai, or system apocalypse."
LATE = "Invent original story premises."
TASK = (
    "Write 80-120 words per premise. Each premise must identify its protagonist, setting, "
    "what the protagonist wants, what stands in the way, a consequential action the "
    "protagonist chooses, its result, and the further pursuit that follows. "
    "Return exactly 6 premises. Return story material rather than advice."
)
ADAPT = (
    "Develop the supplied premise into an original LitRPG premise in portal fantasy, "
    "isekai, or system apocalypse. Preserve the protagonist's central desire, relationships, "
    "chosen action and its consequence as the basis of the story. Integrate a first "
    "consequential use of a power and show how growing personal capabilities drive the "
    "further pursuit. Adapt particulars where the genre requires it. "
    "Write 80-120 words of story material, with no advice or explanation of the adaptation."
)
DRAFT = (
    "Write the opening chapter of the supplied LitRPG story proposal as finished fiction "
    "in third person, past tense. Dramatize the connected action described in opening, "
    "using world and growth as background constraints. Write 1200-1600 words. "
    "Return only the chapter prose, without a title, outline or commentary."
)
TEXT_SCHEMA = {
    "type": "object", "properties": {"story": {"type": "string"}},
    "required": ["story"], "additionalProperties": False,
}


def selected_index(number: str) -> int:
    return random.Random("invention-genre-deferral.v1:" + number).randrange(6)


def invention_request(arm: str, prefix: str, request_type):
    if arm not in ARMS:
        raise ValueError(f"Unknown arm: {arm}")
    return request_type(
        prompt="Create the requested story material.",
        system=prefix + "\n\n" + (EARLY if arm == "early" else LATE) + "\n\n" + TASK,
        schema=core.SCHEMA, max_output_tokens=3200, timeout_seconds=600,
        profile="experiment.invention-contrast.v1",
    )


def parse_story(payload: object) -> str:
    if (not isinstance(payload, dict) or set(payload) != {"story"}
            or not isinstance(payload["story"], str) or not payload["story"].strip()):
        raise ValueError("Expected one nonempty story string")
    return payload["story"]


def dependent_request(stage: str, source: object, discovery, request_type):
    if stage == "plan":
        if not isinstance(source, str):
            raise TypeError("Planning requires the exact adapted premise")
        return discovery.render_request(source, person="third")
    if stage == "adapt":
        if not isinstance(source, str):
            raise TypeError("Adaptation requires the exact selected premise")
        system, prompt, limit = ADAPT, "Story premise:\n" + source, 1000
    elif stage == "draft":
        discovery.Discovery.from_invention(source)
        system, prompt, limit = DRAFT, "Story proposal:\n" + json.dumps(
            source, ensure_ascii=False, sort_keys=True
        ), 4200
    else:
        raise ValueError(f"Unknown stage: {stage}")
    return request_type(
        system=system, prompt=prompt, schema=TEXT_SCHEMA, max_output_tokens=limit,
        timeout_seconds=600, profile="experiment.invention-contrast.v1",
    )


def source_for(stage: str, receipt: dict, index: int):
    payload = receipt["result"]["parsed"]
    if stage == "adapt":
        return core.parse_premises(payload, 6)[index]
    if stage == "plan":
        return parse_story(payload)
    if stage == "draft":
        return payload
    raise ValueError(f"Unknown stage: {stage}")


def source_hash(source: object) -> str:
    return text_sha(source if isinstance(source, str) else json.dumps(
        source, ensure_ascii=False, sort_keys=True
    ))


def lock() -> None:
    holder = (ROOT / "runs/box.lock/holder").read_text(encoding="utf-8-sig")
    if not holder.startswith("invention-genre-deferral-20260912: root task;"):
        raise RuntimeError("This task does not own the shared-machine lock")


def prepare() -> None:
    lock()
    if (LOCAL / "progress.json").exists():
        raise RuntimeError("Already started; never refresh after dispatch")
    old_path = parent.LOCAL / "manifest.json"
    old = read(old_path)
    if sha(old_path) != read(PARENT / "registration.json")["manifest_sha256"]:
        raise RuntimeError("Parent manifest changed")
    files = dict(old["files"])
    if any(sha(Path(p)) != h for p, h in files.items()):
        raise RuntimeError("Parent frozen-file drift")
    _, invention, request_type, _ = imports()
    draws = LOCAL / "draws.json"
    if not draws.exists():
        write(draws, {kind: {str(b): str(secrets.randbits(2048)) for b in (1, 2)}
                      for kind in ("prefix", "selection")})
    numbers = read(draws)
    selections = {b: selected_index(n) for b, n in numbers["selection"].items()}
    for source in read(HERE / "sources.json"):
        if sha(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError("Reference snapshot differs from the source record")
    for path in (
        Path(__file__), HERE / "audit.py", HERE / "RUNBOOK.md", HERE / "SOURCES.md",
        HERE / "sources.json", ROOT / "tests/test_invention_genre_deferral_experiment.py",
        old_path, PARENT / "run.py", PARENT / "registration.json", draws,
        *(ROOT / row["path"] for row in read(HERE / "sources.json")),
    ):
        files[str(path.resolve())] = sha(path)
    for name in ORDER:
        arm, block, _ = name.split("-")
        seed = invention.make_seed(numbers["prefix"][block])
        request = invention_request(arm, seed.brief, request_type)
        for path, data in (
            (LOCAL / "requests" / f"{name}.json", dataclasses.asdict(request)),
            (LOCAL / "seeds" / f"{block}.json", seed.to_jsonable()),
        ):
            write(path, data)
            files[str(path.resolve())] = sha(path)
    write(LOCAL / "manifest.json", {
        "order": ORDER, "chains": CHAINS, "stages": STAGES, "files": files,
        "binary": old["binary"], "token_stop": 150000, "attempt_stop": 20,
        "selections": selections,
    })
    write(HERE / "registration.json", {
        "manifest_sha256": sha(LOCAL / "manifest.json"), "source_revision": "d4ebdb5",
        "parent_manifest_sha256": sha(old_path), "numbers": numbers, "selections": selections,
        "order": ORDER, "chains": CHAINS, "stages": STAGES,
        "requested_model": "gpt-6-astra", "effort": "medium",
        "runbook_sha256": sha(HERE / "RUNBOOK.md"), "runner_sha256": sha(Path(__file__)),
        "audit_sha256": sha(HERE / "audit.py"), "sources_sha256": sha(HERE / "sources.json"),
        "binary_sha256": sha(Path(old["binary"])),
        "request_sha256": {n: sha(LOCAL / "requests" / f"{n}.json") for n in ORDER},
        "attempt_stop": 20, "token_stop": 150000,
    })
    print({"model_calls": 0, "selections_zero_based": selections, "attempt_ceiling": 20})


def run() -> None:
    lock()
    if (LOCAL / "progress.json").exists():
        raise RuntimeError("Already started; no implicit resume")
    if os.environ.get("LITHARNESS_ENV") == "test":
        raise RuntimeError("Provider experiment cannot run in the test environment")
    committed = subprocess.check_output(
        ["git", "show", "HEAD:" + (HERE / "registration.json").relative_to(ROOT).as_posix()],
        cwd=ROOT,
    )
    if json.loads(committed) != read(HERE / "registration.json"):
        raise RuntimeError("Registration must be committed before dispatch")
    discovery, _, request_type, provider_type = imports()
    manifest = read(LOCAL / "manifest.json")
    if sha(LOCAL / "manifest.json") != read(HERE / "registration.json")["manifest_sha256"]:
        raise RuntimeError("Manifest changed")
    progress = {"status": "running", "attempts": 0, "tokens": 0, "slots": [], "stop": None}
    write(LOCAL / "progress.json", progress)
    provider = provider_type(binary=manifest["binary"], trace_directory=LOCAL / "transport")

    def complete(name: str, request, stage: str | None = None, source: dict | None = None):
        lock()
        if any(sha(Path(p)) != h for p, h in manifest["files"].items()):
            raise RuntimeError("Frozen-file drift")
        if (progress["tokens"] >= manifest["token_stop"]
                or progress["attempts"] >= manifest["attempt_stop"]):
            raise RuntimeError("Registered bound reached")
        path = LOCAL / "requests" / f"{name}.json"
        if stage is not None:
            write(path, dataclasses.asdict(request))
        elif read(path) != json.loads(json.dumps(dataclasses.asdict(request))):
            raise RuntimeError("Prepared request changed")
        row = {"request": dataclasses.asdict(request), "request_sha256": sha(path),
               "source": source, "status": "started", "started_at": datetime.now(UTC).isoformat()}
        progress["attempts"] += 1
        write(LOCAL / "calls" / f"{name}.json", row)
        write(LOCAL / "progress.json", progress)
        print(f"Starting {name}", flush=True)
        try:
            result = provider.complete(request)
            row.update(result=dataclasses.asdict(result), status="completed")
            if result.usage.total <= 0:
                raise RuntimeError("Unknown usage")
            progress["tokens"] += result.usage.total
            try:
                if stage == "plan":
                    discovery.Discovery.from_invention(result.parsed)
                elif stage is not None:
                    parse_story(result.parsed)
                else:
                    core.parse_premises(result.parsed, 6)
                row["validation"] = "passed"
            except (TypeError, ValueError, AttributeError) as error:
                row["validation"] = str(error)
        except Exception as error:
            row.update(status="failed", error=f"{type(error).__name__}: {error}",
                       raw=provider.last_attempt)
            raise
        finally:
            row["finished_at"] = datetime.now(UTC).isoformat()
            write(LOCAL / "calls" / f"{name}.json", row)
            progress["slots"].append({"name": name, "status": row["status"]})
            write(LOCAL / "progress.json", progress)
        print(f"Finished {name}; tokens={progress['tokens']}", flush=True)

    try:
        for name in ORDER:
            complete(name, request_type(**read(LOCAL / "requests" / f"{name}.json")))
        for stage_index, stage in enumerate(STAGES):
            for chain in CHAINS:
                name = stage + "-" + chain
                source_name = chain if stage_index == 0 else STAGES[stage_index - 1] + "-" + chain
                path = LOCAL / "calls" / f"{source_name}.json"
                if not path.exists() or read(path).get("validation") != "passed":
                    progress["slots"].append({"name": name, "status": "skipped_invalid_parent"})
                    write(LOCAL / "progress.json", progress)
                    continue
                index = manifest["selections"][chain.split("-")[1]]
                source = source_for(stage, read(path), index)
                complete(name, dependent_request(stage, source, discovery, request_type), stage, {
                    "parent": source_name, "receipt_sha256": sha(path),
                    "index": index if stage == "adapt" else None,
                    "text_sha256": source_hash(source),
                })
    except Exception as error:
        progress["stop"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        progress["status"] = "finished"
        write(LOCAL / "progress.json", progress)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "run"))
    (prepare if parser.parse_args().mode == "prepare" else run)()
