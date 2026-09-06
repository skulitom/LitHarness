"""Paired scene plans with different event dependencies; subscription-only diagnostic."""

from __future__ import annotations

import argparse
import json
import runpy
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
ACTIONS = runpy.run_path(str(HERE / "prose_actions.py"))
CODEX = ACTIONS["CODEX"]
read, write_new, sha = (CODEX[k] for k in ("read", "write_new", "sha"))
REGISTRATION = HERE / "prose-order/PREREG.md"
ORDER = ("full-1", "focused-1", "focused-2", "full-2")
TOKEN_STOP = 140_000
PLANNER_SYSTEM = ACTIONS["PLANNER_SYSTEM"].replace(
    "Cover every supplied source action in its first-occurrence order;",
    "Cover every supplied source action. IDs are identifiers, not a total chronology. "
    "Respect the supplied precedes pairs: the first ID's event must occur before the second. "
    "Construct other ordering from the character's attempts and their consequences;",
)


def validate_contract(contract: Any) -> None:
    if not isinstance(contract, dict) or set(contract) != {"actions", "common_edges", "conditions"}:
        raise ValueError("malformed dependency contract")
    actions = contract["actions"]
    if (
        not isinstance(actions, list)
        or not actions
        or any(
            not isinstance(a, dict)
            or set(a) != {"id", "text"}
            or a["id"] != f"a{i}"
            or not isinstance(a["text"], str)
            or not a["text"].strip()
            for i, a in enumerate(actions, 1)
        )
    ):
        raise ValueError("invalid required outcomes")
    if not isinstance(contract["conditions"], dict) or set(contract["conditions"]) != {
        "full",
        "focused",
    }:
        raise ValueError("two registered conditions required")
    ids = {a["id"] for a in actions}
    for condition in ("full", "focused"):
        groups = (contract["common_edges"], contract["conditions"][condition])
        if any(not isinstance(g, list) for g in groups):
            raise ValueError("invalid dependency list")
        edges = groups[0] + groups[1]
        if any(
            not isinstance(e, list) or len(e) != 2 or any(x not in ids for x in e) for e in edges
        ):
            raise ValueError("unknown dependency endpoint")
        remaining = set(ids)
        while remaining:
            ready = {x for x in remaining if not any(b == x and a in remaining for a, b in edges)}
            if not ready:
                raise ValueError("cyclic event dependencies")
            remaining -= ready


def validate_plan(plan: Any, contract: Any, condition: str) -> None:
    validate_contract(contract)
    if condition not in contract["conditions"]:
        raise ValueError("unregistered condition")
    # Reuse the shape/coverage validator while allowing the contract to define chronology.
    if not isinstance(plan, dict) or not isinstance(plan.get("steps"), list):
        raise ValueError("malformed plan")
    seen: list[str] = []
    for step in plan["steps"]:
        if not isinstance(step, dict) or not isinstance(step.get("source_actions"), list):
            raise ValueError("malformed source references")
        for ref in step["source_actions"]:
            if not isinstance(ref, str):
                raise ValueError("invalid source reference")
            if ref not in seen:
                seen.append(ref)
    by_id = {a["id"]: a for a in contract["actions"]}
    if set(seen) != set(by_id):
        raise ValueError("missing or unknown source actions")
    ACTIONS["validate_plan"](plan, [by_id[x] for x in seen])
    for before, after in contract["common_edges"] + contract["conditions"][condition]:
        if seen.index(before) >= seen.index(after):
            raise ValueError("required event dependency violated")


def scene_parts(prompt: str) -> tuple[str, str]:
    if prompt.count("\nOrdered actions:\n") != 1 or prompt.count("\nEnding state:\n") != 1:
        raise ValueError("one scene action section required")
    before, rest = prompt.split("\nOrdered actions:\n")
    _, after = rest.split("\nEnding state:\n")
    return before, after


def render(base: Any, plan: Any, contract: Any, condition: str) -> dict[str, Any]:
    validate_plan(plan, contract, condition)
    before, after = scene_parts(base["prompt"])
    rows = ["Immediate objective: " + plan["objective"]]
    rows += ["\n".join(f"{k}: {s[k]}" for k in ACTIONS["FIELDS"] if s[k]) for s in plan["steps"]]
    return {
        **base,
        "prompt": before + "\nAction plan:\n" + "\n\n".join(rows) + "\nEnding state:\n" + after,
    }


def prepare(out: Path, source: Path, amendment: Path, contract_path: Path) -> None:
    if not out.is_relative_to(ROOT / "runs") or out == ROOT / "runs":
        raise ValueError("output must be beneath runs")
    base = ACTIONS["reconcile"](read(source)["request"], read(amendment))
    contract = read(contract_path)
    validate_contract(contract)
    before, after = scene_parts(base["prompt"])
    context = (
        before
        + "\nRequired outcomes:\n"
        + "\n".join("- " + a["text"] for a in contract["actions"])
        + "\nEnding state:\n"
        + after
    )
    if base.get("allowed_tools") or base.get("schema"):
        raise ValueError("tool-free unstructured source required")
    prefix = CODEX["command_prefix"]()
    auth = subprocess.run(
        [*prefix, "login", "status"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=CODEX["subscription_env"](),
        check=False,
    )
    if auth.returncode or (auth.stdout + auth.stderr).strip() != "Logged in using ChatGPT":
        raise RuntimeError("ChatGPT subscription required; no fallback")
    out.mkdir(parents=True, exist_ok=False)
    for directory, system in ((out / "planner", PLANNER_SYSTEM), (out / "drafts", base["system"])):
        (directory / "work").mkdir(parents=True)
        (directory / "system.txt").write_text(system, encoding="utf-8", newline="\n")
    paths = [
        Path(__file__),
        REGISTRATION,
        source,
        amendment,
        contract_path,
        Path(prefix[1]),
        *(
            HERE / name
            for name in (
                "prose_actions.py",
                "prose_codex.py",
                "prose_staging.py",
                "prose_framing.py",
            )
        ),
        out / "planner/system.txt",
        out / "drafts/system.txt",
    ]
    write_new(
        out / "manifest.json",
        {
            "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "cli_version": subprocess.check_output([*prefix, "--version"], text=True).strip(),
            "files": {str(p): sha(p) for p in paths},
            "base": base,
            "contract": contract,
            "amendment": read(amendment),
            "planning_context": context,
            "prefix": prefix,
            "order": list(ORDER),
            "token_stop": TOKEN_STOP,
            "authentication": "chatgpt",
        },
    )


def load(out: Path) -> dict[str, Any]:
    return ACTIONS["load"](out)


def quota(out: Path) -> None:
    results = [read(p) for p in out.glob("*/*.result.json")]
    if any(r["status"] != "completed" for r in results):
        raise RuntimeError("previous model invocation failed")
    total = 0
    for result in results:
        usage = result.get("usage", {})
        for key in ("input_tokens", "output_tokens"):
            if type(usage.get(key)) is not int or usage[key] < 0:
                raise ValueError("invalid quota usage")
        reasoning = usage.get("reasoning_output_tokens", 0)
        if type(reasoning) is not int or reasoning < 0:
            raise ValueError("invalid reasoning usage")
        total += usage["input_tokens"] + usage["output_tokens"] + reasoning
    if total >= TOKEN_STOP:
        raise RuntimeError("subscription token stop reached")


def plan_scenes(out: Path, m: Any) -> None:
    requests = {}
    for condition in ("full", "focused"):
        requests[condition] = {
            "system": PLANNER_SYSTEM,
            "prompt": json.dumps(
                {
                    "source_system": m["base"]["system"],
                    "source_context": m["planning_context"],
                    "required_actions": m["contract"]["actions"],
                    "precedes": m["contract"]["common_edges"]
                    + m["contract"]["conditions"][condition],
                },
                ensure_ascii=False,
            ),
        }
    for name in ("full-1", "focused-1"):
        quota(out)
        CODEX["complete_once"](out / "planner", name, {"prefix": m["prefix"], "requests": requests})


def freeze(out: Path, m: Any, reviewed: Path, note: Path) -> None:
    if list((out / "drafts").glob("*.request.json")):
        raise RuntimeError("drafting already started")
    plans = read(reviewed)
    if not isinstance(plans, dict) or set(plans) != {"full", "focused"}:
        raise ValueError("two source-reviewed plans required")
    requests = {c: render(m["base"], plans[c], m["contract"], c) for c in plans}
    review = note.read_text(encoding="utf-8")
    if not review.strip():
        raise ValueError("source review required")
    proposals = {c: sha(out / "planner" / f"{c}-1.result.json") for c in plans}
    write_new(
        out / "plans.reviewed.json",
        {
            "payload": plans,
            "review": review,
            "manifest_sha256": sha(out / "manifest.json"),
            "proposals": proposals,
            "reviewed_file_sha256": sha(reviewed),
        },
    )
    write_new(
        out / "drafts/manifest.json",
        {
            "prefix": m["prefix"],
            "requests": requests,
            "review_sha256": sha(out / "plans.reviewed.json"),
        },
    )


def draft(out: Path, m: Any) -> None:
    review = read(out / "plans.reviewed.json")
    frozen = read(out / "drafts/manifest.json")
    expected = {
        c: render(m["base"], review["payload"][c], m["contract"], c) for c in ("full", "focused")
    }
    if (
        review["manifest_sha256"] != sha(out / "manifest.json")
        or frozen["review_sha256"] != sha(out / "plans.reviewed.json")
        or frozen["prefix"] != m["prefix"]
        or frozen["requests"] != expected
        or any(
            h != sha(out / "planner" / f"{c}-1.result.json") for c, h in review["proposals"].items()
        )
    ):
        raise ValueError("frozen plans or requests changed")
    for name in ORDER:
        quota(out)
        CODEX["complete_once"](out / "drafts", name, frozen)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("phase", choices=("prepare", "plan", "freeze", "draft"))
    for flag in ("out", "source", "amendment", "contract", "reviewed", "note"):
        p.add_argument("--" + flag, type=Path, required=flag == "out")
    args = p.parse_args()
    out = args.out.resolve()
    if args.phase == "prepare":
        if not args.source or not args.amendment or not args.contract:
            p.error("prepare requires --source, --amendment and --contract")
        prepare(out, args.source.resolve(), args.amendment.resolve(), args.contract.resolve())
        return
    m = load(out)
    if args.phase == "plan":
        plan_scenes(out, m)
    elif args.phase == "freeze":
        if not args.reviewed or not args.note:
            p.error("freeze requires --reviewed and --note")
        freeze(out, m, args.reviewed, args.note)
    else:
        draft(out, m)


if __name__ == "__main__":
    main()
