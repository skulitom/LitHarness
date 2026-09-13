"""Two fixed crossed plans, one common writer; reuse the frozen sequential runner."""

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
LOCAL = ROOT / "runs/planner-chapter-transfer-20260913"
PREVIOUS = ROOT / "runs/invention-boundaries-20260912"
PRIOR_RECORDS = HERE.with_name("invention-boundaries-20260912")
DRIVER = HERE.with_name("mechanics-fresh-transfer-20260912") / "run.py"
SPEC = importlib.util.spec_from_file_location("chapter_transfer_driver", DRIVER)
assert SPEC is not None and SPEC.loader is not None
driver = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(driver)
sha, read, write = driver.sha, driver.read, driver.write
BINARY = Path(r"C:\Users\artem\AppData\Local\OpenAI\Codex\bin\bffc5354119c8421\codex.exe")
ORDER = ("draft-astra-1", "draft-opus-1")


def normalized(request):
    return json.loads(json.dumps(dataclasses.asdict(request)))


def lock():
    value = (ROOT / "runs/box.lock/holder").read_text(encoding="utf-8-sig")
    if not value.startswith("planner-chapter-transfer-20260913: root task;"):
        raise RuntimeError("Task does not own shared-machine lock")


def verified_parent(arm):
    from litharness.application.discovery import Discovery
    from litharness.domain.invention import InventionSeed

    if arm not in ("astra", "opus"):
        raise ValueError(arm)
    evidence = read(PRIOR_RECORDS / "evidence.json")
    if not evidence["all_controls_pass"]:
        raise RuntimeError("Previous provenance controls did not pass")
    inventory = {o["name"]: o for o in evidence["outputs"]}
    magic_path = PREVIOUS / "calls/magic-astra-1.json"
    path = PREVIOUS / "calls" / f"plan-astra-{arm}-1.json"
    for p in (magic_path, path):
        if sha(p) != inventory[p.stem]["receipt_sha256"] or not inventory[p.stem]["valid"]:
            raise RuntimeError("Designated source differs from previous evidence")
    row, magic = read(path), read(magic_path)
    lineage = {"slot": magic_path.stem, "receipt_sha256": sha(magic_path)}
    old_seed = InventionSeed.from_payload(read(PREVIOUS / "seeds/1.json"))
    expected = normalized(driver.plan_request(old_seed, magic["result"]["parsed"]))
    if row["status"] != "completed" or row["lineage"] != lineage or row["request"] != expected:
        raise RuntimeError("Designated source lineage or request mismatch")
    Discovery.from_invention(row["result"]["parsed"])
    return {
        "plan": row["result"]["parsed"],
        "source_path": path.relative_to(ROOT).as_posix(),
        "receipt_sha256": sha(path),
        "mechanics_receipt_sha256": sha(magic_path),
    }


def slot_request(name):
    from litharness.domain.invention import InventionSeed

    if name not in ORDER:
        raise ValueError(name)
    arm = name.split("-")[1]
    path = LOCAL / "parents" / f"{arm}.json"
    source = read(path)
    seed = InventionSeed.from_payload(read(LOCAL / "seed.json"))
    lineage = {k: v for k, v in source.items() if k != "plan"}
    lineage["snapshot_sha256"] = sha(path)
    return driver.draft_request(seed, source["plan"]), lineage


def prepare():
    from litharness.domain.invention import make_seed

    lock()
    if (LOCAL / "manifest.json").exists():
        raise RuntimeError("Already prepared; never redraw")
    # Verify both known parents before drawing the new shared seed.
    sources = {arm: verified_parent(arm) for arm in ("astra", "opus")}
    for arm, source in sources.items():
        write(LOCAL / "parents" / f"{arm}.json", source)
    write(LOCAL / "seed.json", make_seed(str(secrets.randbits(2048))).to_jsonable())
    files = {str(p.resolve()): sha(p) for p in (ROOT / "src").rglob("*.py")}
    dependencies = (
        Path(__file__),
        HERE / "RUNBOOK.md",
        DRIVER,
        driver.UTILITIES,
        BINARY,
        ROOT / "tests/test_planner_chapter_transfer_experiment.py",
        PRIOR_RECORDS / "evidence.json",
        PRIOR_RECORDS / "registration.json",
        PREVIOUS / "calls/magic-astra-1.json",
        PREVIOUS / "seeds/1.json",
        LOCAL / "seed.json",
    )
    for p in dependencies:
        files[str(p.resolve())] = sha(p)
    for arm, source in sources.items():
        for p in (ROOT / source["source_path"], LOCAL / "parents" / f"{arm}.json"):
            files[str(p.resolve())] = sha(p)
    for name in ORDER:
        request, _ = slot_request(name)
        p = LOCAL / "requests" / f"{name}.json"
        write(p, normalized(request))
        files[str(p.resolve())] = sha(p)
    write(
        LOCAL / "manifest.json",
        {
            "files": files,
            "order": ORDER,
            "binary": str(BINARY),
            "attempt_stop": 2,
            "token_stop": 30000,
        },
    )
    write(
        HERE / "registration.json",
        {
            "manifest_sha256": sha(LOCAL / "manifest.json"),
            "order": ORDER,
            "source_revision": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "seed_sha256": sha(LOCAL / "seed.json"),
            "binary_sha256": sha(BINARY),
            "binary_version": subprocess.check_output(
                [str(BINARY), "--version"], text=True
            ).strip(),
            "static_requests": {n: sha(LOCAL / "requests" / f"{n}.json") for n in ORDER},
            "parents": {
                arm: {k: v for k, v in s.items() if k != "plan"} for arm, s in sources.items()
            },
        },
    )
    print("Prepared both fixed chapter requests; no generation calls.")


def run():
    # This module has its own imported instance; the previous frozen file is untouched.
    driver.HERE, driver.LOCAL, driver.ORDER = HERE, LOCAL, ORDER
    driver.lock, driver.slot_request = lock, slot_request
    driver.run()


def audit():
    from litharness.providers.codex_schema import prepare_codex_schema

    registration = read(HERE / "registration.json")
    manifest = read(LOCAL / "manifest.json")
    controls = {
        "frozen": {p: sha(Path(p)) == h for p, h in manifest["files"].items()},
        "manifest": {"hash": sha(LOCAL / "manifest.json") == registration["manifest_sha256"]},
    }
    outputs, sessions, reading = [], [], []
    requests = [normalized(slot_request(n)[0]) for n in ORDER]
    controls["contrast"] = {
        "only_plan_differs": [k for k in requests[0] if requests[0][k] != requests[1][k]]
        == ["prompt"],
        "parents": all(
            read(LOCAL / "parents" / f"{a}.json") == verified_parent(a) for a in ("astra", "opus")
        ),
    }
    for name in ORDER:
        path = LOCAL / "calls" / f"{name}.json"
        if not path.exists():
            controls[name] = {"reached": False}
            outputs.append({"name": name, "status": "not_reached"})
            continue
        row = read(path)
        if row["status"] != "completed":
            controls[name] = {"completed": False}
            outputs.append({"name": name, "status": row["status"], "receipt_sha256": sha(path)})
            continue
        request, lineage = slot_request(name)
        result, raw = row["result"], row["result"]["raw"]
        request_path = LOCAL / "requests" / f"{name}.json"
        controls[name] = {
            "request": normalized(request) == row["request"] == read(request_path),
            "hash": sha(request_path)
            == row["request_sha256"]
            == registration["static_requests"][name],
            "lineage": lineage == row["lineage"],
            "prompt": raw["prompt"] == request.prompt,
            "system": raw["system"] == request.effective_system,
            "schema": raw["native_schema"] == prepare_codex_schema(request.schema),
            "returncode": raw["returncode"] == 0,
            "model": raw["requested_model"] == "gpt-6-astra",
            "effort": raw["settings"]["model_reasoning_effort"] == "medium",
            "ephemeral": "--ephemeral" in raw["argv"],
            "memory_off": "features.memories=false" in raw["argv"],
            "docs_off": "project_doc_max_bytes=0" in raw["argv"],
        }
        ids = [e["thread_id"] for e in raw["events"] if e.get("type") == "thread.started"]
        sessions.extend(ids)
        valid = driver.valid_fields(result["parsed"], ("story",))
        story = result["parsed"]["story"] if valid else result["text"]
        outputs.append(
            {
                "name": name,
                "status": row["status"],
                "valid": valid,
                "lineage": lineage,
                "receipt_sha256": sha(path),
                "story_sha256": driver.text_sha(story),
                "words": len(story.split()),
                "usage": result["usage"],
                "session_ids": ids,
            }
        )
        reading.append("# " + name + "\n\n" + story)
        if valid:
            (LOCAL / f"{name}.md").write_text(story + "\n", encoding="utf-8", newline="\n")
    old_ids = {
        s
        for o in read(PRIOR_RECORDS / "evidence.json")["outputs"]
        for s in o.get("session_ids", [])
    }
    completed = sum(o["status"] == "completed" for o in outputs)
    controls["sessions"] = {
        "distinct": len(sessions) == len(set(sessions)) == completed,
        "fresh": not old_ids.intersection(sessions),
    }
    report = {
        "all_controls_pass": all(all(c.values()) for c in controls.values()),
        "controls": controls,
        "outputs": outputs,
        "progress": read(LOCAL / "progress.json"),
        "registration_sha256": sha(HERE / "registration.json"),
    }
    write(HERE / "evidence.json", report)
    (LOCAL / "reading.md").write_text("\n\n".join(reading) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"controls_pass": report["all_controls_pass"], "outputs": outputs}, indent=2))
    if not report["all_controls_pass"]:
        raise RuntimeError("Audit failed; retain first outputs")


if __name__ == "__main__":
    {"prepare": prepare, "run": run, "audit": audit}[sys.argv[1]]()
