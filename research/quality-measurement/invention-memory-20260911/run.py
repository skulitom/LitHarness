"""Compare fixed generated history, structural contrast, and its expansion carry-through."""

from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import json
import os
import random
import secrets
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = ROOT / "runs/invention-memory-20260911"
PARENT = HERE.with_name("invention-effort-20260911")
SPEC = importlib.util.spec_from_file_location("effort_parent", PARENT / "run.py")
assert SPEC is not None and SPEC.loader is not None
parent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parent)
sha, text_sha, read, write, imports, request_matches = (
    parent.sha, parent.text_sha, parent.read, parent.write, parent.imports, parent.request_matches
)
parse_premises = parent.parent.parse_premises
ORDER = ("baseline-1", "identity-1", "structure-1", "structure-2", "identity-2", "baseline-2")
EXPANSIONS = (
    "expand-baseline-1", "expand-identity-1", "expand-structure-1", "retain-structure-1",
    "retain-structure-2", "expand-structure-2", "expand-identity-2", "expand-baseline-2",
)
IDENTITY = (
    "Invent a different protagonist, setting and core power premise; changing names or "
    "continuing the same world does not satisfy this request."
)
STRUCTURE = (
    "Also use different initiating actions, causal sequences, ongoing pursuits and central "
    "conflicts. Substituting occupations, names or places into the same plot does not "
    "satisfy this request."
)
CARRY = (
    "Preserve the supplied premise's central action and pursuit. When developing its world, "
    "opening and growth, make the added actions, causal sequences and continuing conflicts "
    "distinct from the previous premises. Do not replace the supplied premise with another story."
)


def selected_index(number: str) -> int:
    return random.Random("invention-memory.v1:" + number).randrange(6)


def history_prompt(history: list[str], *, structural: bool) -> str:
    return (
        "The following previous premises are reference data describing territory already used, "
        "not instructions, examples to imitate or facts for the new story. " + IDENTITY
        + (" " + STRUCTURE if structural else "")
        + "\nPrevious premises:\n" + json.dumps(history, ensure_ascii=False) + "\n\n"
    )


def generation_prompt(arm: str, history: list[str]) -> str:
    if arm not in ("baseline", "identity", "structure"):
        raise ValueError(f"Unknown arm: {arm}")
    return ("" if arm == "baseline" else history_prompt(history, structural=arm == "structure")) + (
        "Create the requested story material."
    )


def expansion_request(name: str, premise: str, history: list[str], discovery):
    if name not in EXPANSIONS:
        raise ValueError(f"Unknown expansion: {name}")
    request = discovery.render_request(premise, person="third")
    if name.startswith("retain-"):
        request = dataclasses.replace(
            request,
            prompt=history_prompt(history, structural=True) + CARRY + "\n\n" + request.prompt
        )
    return request


def lock() -> None:
    holder = (ROOT / "runs/box.lock/holder").read_text(encoding="utf-8-sig")
    if not holder.startswith("invention-memory-20260911: root task;"):
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
    history, provenance = [], []
    for b in (1, 2, 3):
        path = parent.LOCAL / "calls" / f"medium-{b}.json"
        row = read(path)
        if row.get("validation") != "passed":
            raise RuntimeError("Registered history source is invalid")
        for i, premise in enumerate(parse_premises(row["result"]["parsed"], 6)):
            history.append(premise)
            provenance.append({"source": path.relative_to(ROOT).as_posix(), "index": i,
                               "receipt_sha256": sha(path), "text_sha256": text_sha(premise)})
        files[str(path.resolve())] = sha(path)
    write(LOCAL / "history.json", {"premises": history, "provenance": provenance})
    _, invention, CompletionRequest, _ = imports()
    draws = LOCAL / "draws.json"
    if not draws.exists():
        write(draws, {str(b): str(secrets.randbits(2048)) for b in (1, 2)})
    numbers = read(draws)
    selections = {b: selected_index(n) for b, n in numbers.items()}
    source_rows = json.loads((HERE / "sources.json").read_text(encoding="utf-8"))
    for p in (Path(__file__), HERE / "RUNBOOK.md", HERE / "SOURCES.md", HERE / "sources.json",
              old_path, PARENT / "registration.json", PARENT / "run.py", draws,
              LOCAL / "history.json", *(ROOT / r["path"] for r in source_rows)):
        files[str(p.resolve())] = sha(p)
    for name in ORDER:
        arm, block = name.rsplit("-", 1)
        seed = invention.make_seed(numbers[block])
        request = CompletionRequest(
            prompt=generation_prompt(arm, history),
            system=parent.parent.system_text(seed.brief, "batch"),
            schema=parent.parent.SCHEMA, max_output_tokens=3200, timeout_seconds=600,
            profile="experiment.invention-contrast.v1",
        )
        for path, data in (
            (LOCAL / "requests" / f"{name}.json", dataclasses.asdict(request)),
            (LOCAL / "seeds" / f"{block}.json", seed.to_jsonable()),
        ):
            write(path, data)
            files[str(path.resolve())] = sha(path)
    write(LOCAL / "manifest.json", {
        "order": ORDER, "expansions": EXPANSIONS, "files": files, "binary": old["binary"],
        "token_stop": 110000, "attempt_stop": 14, "selections": selections,
    })
    write(HERE / "registration.json", {
        "manifest_sha256": sha(LOCAL / "manifest.json"), "source_revision": "d4ebdb5",
        "parent_manifest_sha256": sha(old_path), "numbers": numbers, "selections": selections,
        "order": ORDER, "expansions": EXPANSIONS, "requested_model": "gpt-6-astra",
        "effort": "medium", "history_sha256": sha(LOCAL / "history.json"),
        "history_provenance": provenance, "runbook_sha256": sha(HERE / "RUNBOOK.md"),
        "runner_sha256": sha(Path(__file__)), "sources_sha256": sha(HERE / "sources.json"),
        "request_sha256": {n: sha(LOCAL / "requests" / f"{n}.json") for n in ORDER},
        "binary_sha256": sha(Path(old["binary"])),
    })
    print({"model_calls": 0, "selections_zero_based": selections, "attempt_ceiling": 14})


def run() -> None:
    lock()
    if (LOCAL / "progress.json").exists():
        raise RuntimeError("Already started; no implicit resume")
    if os.environ.get("LITHARNESS_ENV") == "test":
        raise RuntimeError("Provider experiment cannot run in the test environment")
    discovery, _, CompletionRequest, CodexCliProvider = imports()
    manifest = read(LOCAL / "manifest.json")
    if sha(LOCAL / "manifest.json") != read(HERE / "registration.json")["manifest_sha256"]:
        raise RuntimeError("Manifest changed")
    history = read(LOCAL / "history.json")["premises"]
    progress = {"status": "running", "attempts": 0, "tokens": 0, "slots": [], "stop": None}
    write(LOCAL / "progress.json", progress)
    provider = CodexCliProvider(binary=manifest["binary"], trace_directory=LOCAL / "transport")

    def complete(name: str, request, source: dict | None = None) -> None:
        lock()
        if any(sha(Path(p)) != h for p, h in manifest["files"].items()):
            raise RuntimeError("Frozen-file drift")
        if (progress["tokens"] >= manifest["token_stop"]
                or progress["attempts"] >= manifest["attempt_stop"]):
            raise RuntimeError("Registered bound reached")
        path = LOCAL / "requests" / f"{name}.json"
        if source is not None:
            write(path, dataclasses.asdict(request))
        elif not request_matches(read(path), request):
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
                if source is not None:
                    discovery.Discovery.from_invention(result.parsed)
                else:
                    premises = parse_premises(result.parsed, 6)
                    index = manifest["selections"][name.rsplit("-", 1)[1]]
                    row["selected"] = {"index": index, "text_sha256": text_sha(premises[index])}
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
            complete(name, CompletionRequest(**read(LOCAL / "requests" / f"{name}.json")))
        for name in EXPANSIONS:
            source_name = name.split("-", 1)[1]
            path = LOCAL / "calls" / f"{source_name}.json"
            row = read(path)
            if row.get("validation") != "passed":
                progress["slots"].append({"name": name, "status": "skipped_invalid_parent"})
                write(LOCAL / "progress.json", progress)
                continue
            index = row["selected"]["index"]
            premise = parse_premises(row["result"]["parsed"], 6)[index]
            complete(name, expansion_request(name, premise, history, discovery),
                     source={"parent": source_name, "receipt_sha256": sha(path), "index": index,
                             "text_sha256": text_sha(premise)})
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
