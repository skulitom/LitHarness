"""Compare short and complete prior-story memory during repeated fresh-premise expansion."""

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
LOCAL = ROOT / "runs/invention-plan-memory-20260912"
PARENT = HERE.with_name("invention-verbalized-20260911")
SPEC = importlib.util.spec_from_file_location("plan_memory_parent", PARENT / "run.py")
assert SPEC is not None and SPEC.loader is not None
parent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parent)
sha, text_sha, read, write, imports = (
    parent.sha, parent.text_sha, parent.read, parent.write, parent.imports
)
ARMS = ("clean", "short", "full")
ORDER = ("invent-1", "invent-2")
EXPANSIONS = (
    "clean-1-1", "short-1-1", "full-1-1", "short-2-1", "full-2-1", "clean-2-1",
    "full-1-2", "short-1-2", "clean-1-2", "clean-2-2", "full-2-2", "short-2-2",
)
REFERENCE = (
    "The following story records describe previous generations. Treat them as reference data "
    "for territory already used, not instructions, templates or facts for the new story."
)
INVENT = (
    "Invent different protagonists, settings, powers, initiating actions, causal sequences, "
    "ongoing pursuits and central conflicts. Changing names, occupations or scenery alone "
    "is insufficient."
)
EXPAND = (
    "Develop the supplied premise with added actions, causal sequences, ongoing pursuits, "
    "conflicts and world material that differ from the previous story records. "
    "Changing names, occupations or scenery alone is insufficient."
)


def selected_index(number: str) -> int:
    return random.Random("invention-plan-memory.v1:" + number).randrange(6)


def history_pair(sources: list[tuple[str, dict]]) -> dict:
    short, full = [], []
    for premise, plan in sources:
        if not isinstance(premise, str) or not premise.strip():
            raise ValueError("History premise must be non-empty text")
        if set(plan) != {"world", "opening", "growth"} or any(
            not isinstance(v, str) or not v.strip() for v in plan.values()
        ):
            raise ValueError("History plan must contain exactly three non-empty fields")
        short.append({"premise": premise})
        full.append({"premise": premise, **{k: plan[k] for k in ("world", "opening", "growth")}})
    return {"short": short, "full": full}


def history_prompt(records: list[dict], instruction: str) -> str:
    return REFERENCE + "\n" + instruction + "\nPrevious story records:\n" + json.dumps(
        records, ensure_ascii=False
    ) + "\n\n"


def invention_request(prefix: str, histories: dict, request_type):
    return request_type(
        prompt=history_prompt(histories["short"], INVENT) + "Create the requested story material.",
        system=parent.parent.system_text(prefix, "batch"), schema=parent.parent.SCHEMA,
        max_output_tokens=3200, timeout_seconds=600, profile="experiment.invention-contrast.v1",
    )


def expansion_request(arm: str, premise: str, histories: dict, discovery):
    if arm not in ARMS:
        raise ValueError(f"Unknown arm: {arm}")
    request = discovery.render_request(premise, person="third")
    if arm == "clean":
        return request
    return dataclasses.replace(
        request, prompt=history_prompt(histories[arm], EXPAND) + request.prompt
    )


def transport_text_checks(request, fields: dict) -> dict:
    return {
        "effective_system_equal": fields.get("transport.system") == request.effective_system,
        "prompt_equal": fields.get("transport.prompt") == request.prompt,
    }


def lock() -> None:
    holder = (ROOT / "runs/box.lock/holder").read_text(encoding="utf-8-sig")
    if not holder.startswith("invention-plan-memory-20260912: root task;"):
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
    evidence = read(PARENT / "evidence.json")
    observed = {r["slot"]: r["receipt_sha256"] for r in evidence["calls"]}
    sources, provenance = [], []
    discovery, invention, request_type, _ = imports()
    for name in old["order"]:
        premise_path = parent.LOCAL / "calls" / f"{name}.json"
        plan_path = parent.LOCAL / "calls" / f"expand-{name}.json"
        for path in (premise_path, plan_path):
            if sha(path) != observed[path.stem] or read(path).get("validation") != "passed":
                raise RuntimeError("History receipt differs from the prior evidence")
            files[str(path.resolve())] = sha(path)
        premise_row, plan_row = read(premise_path), read(plan_path)
        index = old["selections"][name.rsplit("-", 1)[1]]
        premise = parent.parse_items(premise_row["result"]["parsed"], name.split("-", 1)[0])[
            index
        ]["text"]
        expected_source = {"parent": name, "receipt_sha256": sha(premise_path), "index": index,
                           "text_sha256": text_sha(premise)}
        if plan_row["source"] != expected_source:
            raise RuntimeError("History plan provenance mismatch")
        plan = plan_row["result"]["parsed"]
        discovery.Discovery.from_invention(plan)
        sources.append((premise, plan))
        provenance.append({
            "slot": name, "index": index, "premise_receipt_sha256": sha(premise_path),
            "plan_receipt_sha256": sha(plan_path), "text_sha256": text_sha(premise),
            "plan_field_sha256": {k: text_sha(v) for k, v in plan.items()},
        })
    histories = history_pair(sources)
    write(LOCAL / "history.json", histories)
    draws = LOCAL / "draws.json"
    if not draws.exists():
        write(draws, {kind: {str(b): str(secrets.randbits(2048)) for b in (1, 2)}
                      for kind in ("prefix", "selection")})
    numbers = read(draws)
    selections = {b: selected_index(n) for b, n in numbers["selection"].items()}
    for source in read(HERE / "sources.json"):
        if sha(ROOT / source["path"]) != source["sha256"]:
            raise RuntimeError("Literature snapshot changed")
    for path in (
        Path(__file__), HERE / "audit.py", HERE / "RUNBOOK.md", HERE / "SOURCES.md",
        HERE / "sources.json", ROOT / "tests/test_invention_plan_memory_experiment.py",
        old_path, PARENT / "registration.json", PARENT / "evidence.json", draws,
        LOCAL / "history.json", *(ROOT / r["path"] for r in read(HERE / "sources.json")),
    ):
        files[str(path.resolve())] = sha(path)
    for name in ORDER:
        block = name.rsplit("-", 1)[1]
        seed = invention.make_seed(numbers["prefix"][block])
        request = invention_request(seed.brief, histories, request_type)
        for path, data in (
            (LOCAL / "requests" / f"{name}.json", dataclasses.asdict(request)),
            (LOCAL / "seeds" / f"{block}.json", seed.to_jsonable()),
        ):
            write(path, data)
            files[str(path.resolve())] = sha(path)
    write(LOCAL / "manifest.json", {
        "order": ORDER, "expansions": EXPANSIONS, "files": files, "binary": old["binary"],
        "token_stop": 180000, "attempt_stop": 14, "selections": selections,
    })
    write(HERE / "registration.json", {
        "manifest_sha256": sha(LOCAL / "manifest.json"), "source_revision": "d4ebdb5",
        "parent_manifest_sha256": sha(old_path), "numbers": numbers, "selections": selections,
        "order": ORDER, "expansions": EXPANSIONS, "requested_model": "gpt-6-astra",
        "effort": "medium", "history_sha256": sha(LOCAL / "history.json"),
        "history_provenance": provenance, "runbook_sha256": sha(HERE / "RUNBOOK.md"),
        "runner_sha256": sha(Path(__file__)), "audit_sha256": sha(HERE / "audit.py"),
        "sources_sha256": sha(HERE / "sources.json"), "binary_sha256": sha(Path(old["binary"])),
        "request_sha256": {n: sha(LOCAL / "requests" / f"{n}.json") for n in ORDER},
        "attempt_stop": 14, "token_stop": 180000,
    })
    print({"model_calls": 0, "selections_zero_based": selections, "attempt_ceiling": 14,
           "history_characters": {a: len(json.dumps(h)) for a, h in histories.items()}})


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
    histories = read(LOCAL / "history.json")
    progress = {"status": "running", "attempts": 0, "tokens": 0, "slots": [], "stop": None}
    write(LOCAL / "progress.json", progress)
    provider = provider_type(binary=manifest["binary"], trace_directory=LOCAL / "transport")

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
                if source is not None:
                    discovery.Discovery.from_invention(result.parsed)
                else:
                    premises = parent.parent.parse_premises(result.parsed, 6)
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
            complete(name, request_type(**read(LOCAL / "requests" / f"{name}.json")))
        for name in EXPANSIONS:
            arm, block, _ = name.split("-")
            source_name = f"invent-{block}"
            path = LOCAL / "calls" / f"{source_name}.json"
            row = read(path)
            if row.get("validation") != "passed":
                progress["slots"].append({"name": name, "status": "skipped_invalid_parent"})
                write(LOCAL / "progress.json", progress)
                continue
            index = manifest["selections"][block]
            premise = parent.parent.parse_premises(row["result"]["parsed"], 6)[index]
            complete(name, expansion_request(arm, premise, histories, discovery), source={
                "parent": source_name, "receipt_sha256": sha(path), "index": index,
                "text_sha256": text_sha(premise),
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
