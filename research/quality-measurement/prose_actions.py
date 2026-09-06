"""Replace an interpretive beat list with source-reviewed actions; subscription diagnostic."""

from __future__ import annotations

import argparse
import json
import runpy
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
CODEX = runpy.run_path(str(HERE / "prose_codex.py"))
STAGING = runpy.run_path(str(HERE / "prose_staging.py"))
read, write_new, sha = (CODEX[k] for k in ("read", "write_new", "sha"))
REGISTRATION = HERE / "prose-actions/PREREG.md"
ORDER = ("full-1", "focused-1", "focused-2", "full-2")
FIELDS = ("intention", "action", "response", "consequence")
TOKEN_STOP = 120_000
PLANNER_SYSTEM = """Design one scene from the supplied author source. Return a single plan,
not prose, criticism, alternatives, or a recommendation between candidates. The source's
drafting instructions describe the eventual scene; do not draft it now.

Work out what the viewpoint character is trying to accomplish in the immediate situation,
what they attempt, what another person or the environment actually does in response, and
how that response changes their next action. Build a connected sequence of these events.
Do not merely split the old list into new labels. Preserve its required events, knowledge
changes, causal dependencies and endpoint. Events described as overlapping may overlap;
interactions may occur between required events. Quiet observation and reading are permitted.
There is no requirement to insert dialogue, a reversal or an obstacle into every step.
The character can make a mistaken inference; distinguish that belief from a new world fact.

Keep background available without turning it into an introductory inventory. Include it in
the plan only when it affects a present choice or interaction. Do not supply literary
sentences, finished dialogue, metaphors, thematic explanations, emotional summaries or
wording for the writer to reuse. Describe observable actions precisely enough to stage.
Incidental staging within this scene may be invented. Do not invent prior events, new named
actors, rules, system messages or facts reserved for later scenes. Check physical positions,
elapsed time and action-triggered payments: an eligible attempt takes effect when attempted,
not at a convenient later beat. Preserve author locks and the explicitly reconciled source.
Report any remaining source conflict instead of silently resolving it.

Return JSON with exactly objective (a string), steps (1 to 32 objects), conflicts (array of
strings, empty if none). Each step has exactly id (s1, s2, ...), source_actions (array of
supplied IDs), intention, action, response, consequence (four strings). Action is required;
other fields can be empty. A consequence should explain why the next action follows when
there is such a link. Cover every supplied source action in its first-occurrence order;
connective steps may have an empty ID array, and overlapping actions may share steps.
The output is planning material to replace the original action list, not notes appended to it.
"""


def reconcile(base: dict[str, Any], amendment: Any) -> dict[str, Any]:
    if not isinstance(amendment, dict) or set(amendment) != {
        "edits",
        "clarifications",
        "rationale",
    }:
        raise ValueError("invalid source amendment")
    if not amendment["rationale"] or not isinstance(amendment["clarifications"], str):
        raise ValueError("source amendment requires rationale and clarifications")
    result = dict(base)
    for edit in amendment["edits"]:
        if set(edit) != {"field", "old", "new", "count", "reason"}:
            raise ValueError("invalid source edit")
        field = edit["field"]
        if field not in {"prompt", "system"} or not edit["old"] or not edit["reason"]:
            raise ValueError("invalid source edit target")
        if type(edit["count"]) is not int or edit["count"] < 1:
            raise ValueError("invalid source edit count")
        if result[field].count(edit["old"]) != edit["count"]:
            raise ValueError("source edit occurrence count changed")
        result[field] = result[field].replace(edit["old"], edit["new"])
    if amendment["clarifications"].strip():
        result["system"] += (
            "\n\nAgreed source resolutions for this diagnostic:\n" + amendment["clarifications"]
        )
    return result


def validate_plan(plan: Any, actions: list[dict[str, str]]) -> None:
    if not isinstance(plan, dict) or set(plan) != {"objective", "steps", "conflicts"}:
        raise ValueError("malformed action plan")
    if not isinstance(plan["objective"], str) or not plan["objective"].strip():
        raise ValueError("missing immediate objective")
    if plan["conflicts"] != []:
        raise ValueError("unresolved source conflicts")
    steps = plan["steps"]
    if not isinstance(steps, list) or not 1 <= len(steps) <= 32:
        raise ValueError("invalid step count")
    expected, seen = [a["id"] for a in actions], []
    for i, step in enumerate(steps, 1):
        if not isinstance(step, dict) or set(step) != {"id", "source_actions", *FIELDS}:
            raise ValueError("malformed action step")
        if step["id"] != f"s{i}" or any(not isinstance(step[k], str) for k in FIELDS):
            raise ValueError("invalid action identity or field")
        if not step["action"].strip() or not isinstance(step["source_actions"], list):
            raise ValueError("missing action or source references")
        for ref in step["source_actions"]:
            if ref not in expected:
                raise ValueError("unknown source action")
            if ref not in seen:
                seen.append(ref)
    if seen != expected:
        raise ValueError("missing or reordered source actions")


def render(base: dict[str, Any], plan: Any) -> dict[str, Any]:
    validate_plan(plan, STAGING["source_actions"](base["prompt"]))
    before, rest = base["prompt"].split("\nOrdered actions:\n")
    _, after = rest.split("\nEnding state:\n")
    rows = ["Immediate objective: " + plan["objective"]]
    rows += ["\n".join(f"{k}: {step[k]}" for k in FIELDS if step[k]) for step in plan["steps"]]
    return {
        **base,
        "prompt": before + "\nAction plan:\n" + "\n\n".join(rows) + "\nEnding state:\n" + after,
    }


def prepare(out: Path, source: Path, amendment: Path) -> None:
    if not out.is_relative_to(ROOT / "runs") or out == ROOT / "runs":
        raise ValueError("output must be beneath runs")
    original = read(source)["request"]
    base = reconcile(original, read(amendment))
    actions = STAGING["source_actions"](base["prompt"])
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
        HERE / "prose_codex.py",
        HERE / "prose_staging.py",
        HERE / "prose_framing.py",
        source,
        amendment,
        Path(prefix[1]),
        out / "planner/system.txt",
        out / "drafts/system.txt",
    ]
    write_new(
        out / "manifest.json",
        {
            "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "cli_version": subprocess.check_output([*prefix, "--version"], text=True).strip(),
            "files": {str(p): sha(p) for p in paths},
            "original": original,
            "base": base,
            "amendment": read(amendment),
            "actions": actions,
            "prefix": prefix,
            "order": list(ORDER),
            "token_stop": TOKEN_STOP,
            "authentication": "chatgpt",
        },
    )


def load(out: Path) -> dict[str, Any]:
    m = read(out / "manifest.json")
    if any(sha(Path(p)) != h for p, h in m["files"].items()):
        raise ValueError("frozen source or implementation changed")
    return m


def quota(out: Path) -> None:
    results = [read(p) for p in out.glob("*/*.result.json")]
    if any(r["status"] != "completed" for r in results):
        raise RuntimeError("previous invocation failed")
    tokens = sum(
        sum(
            r["usage"].get(k, 0)
            for k in ("input_tokens", "output_tokens", "reasoning_output_tokens")
        )
        for r in results
    )
    if tokens >= TOKEN_STOP:
        raise RuntimeError("subscription token stop reached")


def plan_scene(out: Path, m: dict[str, Any]) -> None:
    quota(out)
    request = {
        "system": PLANNER_SYSTEM,
        "prompt": json.dumps(
            {
                "source_system": m["base"]["system"],
                "source_context_and_plan": m["base"]["prompt"],
                "required_actions": m["actions"],
            },
            ensure_ascii=False,
        ),
    }
    CODEX["complete_once"](
        out / "planner", "full-1", {"prefix": m["prefix"], "requests": {"full": request}}
    )


def freeze(out: Path, m: dict[str, Any], reviewed: Path, note: Path) -> None:
    if list((out / "drafts").glob("*.request.json")):
        raise RuntimeError("drafting already started")
    plan = read(reviewed)
    validate_plan(plan, m["actions"])
    review = note.read_text(encoding="utf-8")
    if not review.strip():
        raise ValueError("source review required")
    if not (out / "planner/full-1.result.json").is_file():
        raise ValueError("planner result required")
    write_new(
        out / "plan.reviewed.json",
        {
            "payload": plan,
            "review": review,
            "manifest_sha256": sha(out / "manifest.json"),
            "proposal_sha256": sha(out / "planner/full-1.result.json"),
            "reviewed_file_sha256": sha(reviewed),
        },
    )
    write_new(
        out / "drafts/manifest.json",
        {
            "prefix": m["prefix"],
            "requests": {"full": m["base"], "focused": render(m["base"], plan)},
            "review_sha256": sha(out / "plan.reviewed.json"),
        },
    )


def draft(out: Path, m: dict[str, Any]) -> None:
    review = read(out / "plan.reviewed.json")
    frozen = read(out / "drafts/manifest.json")
    expected = {"full": m["base"], "focused": render(m["base"], review["payload"])}
    if (
        review["manifest_sha256"] != sha(out / "manifest.json")
        or frozen["review_sha256"] != sha(out / "plan.reviewed.json")
        or frozen["requests"] != expected
        or frozen["prefix"] != m["prefix"]
        or review["proposal_sha256"] != sha(out / "planner/full-1.result.json")
    ):
        raise ValueError("frozen review or requests changed")
    for name in ORDER:
        quota(out)
        CODEX["complete_once"](out / "drafts", name, frozen)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("phase", choices=("prepare", "plan", "freeze", "draft"))
    for flag in ("out", "source", "amendment", "reviewed", "note"):
        p.add_argument("--" + flag, type=Path, required=flag == "out")
    args = p.parse_args()
    out = args.out.resolve()
    if args.phase == "prepare":
        if not args.source or not args.amendment:
            p.error("prepare requires --source and --amendment")
        prepare(out, args.source.resolve(), args.amendment.resolve())
        return
    m = load(out)
    if args.phase == "plan":
        plan_scene(out, m)
    elif args.phase == "freeze":
        if not args.reviewed or not args.note:
            p.error("freeze requires --reviewed and --note")
        freeze(out, m, args.reviewed, args.note)
    else:
        draft(out, m)


if __name__ == "__main__":
    main()
