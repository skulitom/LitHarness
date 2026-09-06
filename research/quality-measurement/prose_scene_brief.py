"""Cross background exposure with fixed-plan exposure on a fresh scene; no selection."""

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
read, write_new, sha = (CODEX[k] for k in ("read", "write_new", "sha"))
REGISTRATION = HERE / "prose-scene-brief/PREREG.md"
ORDER = (
    ("planned", "full-1"),
    ("free", "full-1"),
    ("free", "focused-1"),
    ("planned", "focused-1"),
    ("planned", "focused-2"),
    ("free", "focused-2"),
    ("free", "full-2"),
    ("planned", "full-2"),
)
TOKEN_STOP = 75_000
PLANNER_SYSTEM = """Plan the supplied opening scene. Return JSON with exactly steps and
conflicts. Steps is an array of one to eight nonempty strings, each describing an action
and its immediate result in at most two sentences. Conflicts is an array of strings,
empty if none. Choose one coherent course of action within the supplied situation,
abilities and endpoint. Work out physical positions, elapsed time and consumed resources.
Do not supply alternative plans, finished dialogue, literary prose or thematic conclusions.
Incidental physical staging may be invented. Report an unresolved source conflict rather
than inventing a rule or silently resolving it. The source describes what will be drafted;
do not write the scene now."""


def validate_source(source: Any) -> None:
    if not isinstance(source, dict) or set(source) != {"system", "scene", "background"}:
        raise ValueError("source requires system, scene and background")
    if any(not isinstance(v, str) or not v.strip() for v in source.values()):
        raise ValueError("nonempty source fields required")
    if len((source["system"] + " " + source["scene"]).split()) > 450:
        raise ValueError("compact source exceeds 450 words")
    if len(source["background"].split()) < 600:
        raise ValueError("extended reference must contain at least 600 words")


def validate_plan(plan: Any) -> None:
    if not isinstance(plan, dict) or set(plan) != {"steps", "conflicts"}:
        raise ValueError("malformed plan")
    if plan["conflicts"] != []:
        raise ValueError("unresolved source conflict")
    steps = plan["steps"]
    if not isinstance(steps, list) or not 1 <= len(steps) <= 8:
        raise ValueError("one to eight steps required")
    if any(not isinstance(s, str) or not s.strip() for s in steps):
        raise ValueError("nonempty action steps required")


def compose(source: Any, plan: Any) -> dict[str, Any]:
    validate_source(source)
    validate_plan(plan)
    core = source["scene"]
    background = "\n\nAdditional reference; not required on-page content:\n" + source["background"]
    actions = "\n\nFollow this action plan:\n" + "\n".join(
        f"{i}. {step}" for i, step in enumerate(plan["steps"], 1)
    )
    return {
        mode: {
            condition: {
                "system": source["system"],
                "prompt": core
                + (background if condition == "full" else "")
                + (actions if mode == "planned" else ""),
            }
            for condition in ("full", "focused")
        }
        for mode in ("free", "planned")
    }


def prepare(out: Path, source_path: Path, note: Path) -> None:
    if not out.is_relative_to(ROOT / "runs") or out == ROOT / "runs":
        raise ValueError("output must be beneath runs")
    source = read(source_path)
    validate_source(source)
    if not note.read_text(encoding="utf-8").strip():
        raise ValueError("pre-call source review required")
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
    for mode in ("planner", "planned", "free"):
        (out / mode / "work").mkdir(parents=True)
        (out / mode / "system.txt").write_text(
            PLANNER_SYSTEM if mode == "planner" else source["system"],
            encoding="utf-8",
            newline="\n",
        )
    paths = [
        Path(__file__),
        HERE / "prose_codex.py",
        REGISTRATION,
        REGISTRATION.with_name("RUNBOOK.md"),
        source_path,
        note,
        Path(prefix[1]),
        *(out / mode / "system.txt" for mode in ("planner", "planned", "free")),
    ]
    write_new(
        out / "manifest.json",
        {
            "source": source,
            "prefix": prefix,
            "order": ORDER,
            "token_stop": TOKEN_STOP,
            "files": {str(p): sha(p) for p in paths},
            "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "cli_version": subprocess.check_output([*prefix, "--version"], text=True).strip(),
            "authentication": "chatgpt",
        },
    )


def quota(out: Path) -> None:
    total = 0
    for path in out.glob("*/*.result.json"):
        result = read(path)
        if result["status"] != "completed":
            raise RuntimeError("previous invocation failed")
        usage = result.get("usage", {})
        for key in ("input_tokens", "output_tokens", "reasoning_output_tokens"):
            value = usage.get(key, 0 if key == "reasoning_output_tokens" else None)
            if type(value) is not int or value < 0:
                raise ValueError("invalid quota usage")
            total += value
    if total >= TOKEN_STOP:
        raise RuntimeError("subscription token stop reached")


def plan_scene(out: Path, m: Any) -> None:
    quota(out)
    request = {"system": PLANNER_SYSTEM, "prompt": json.dumps(m["source"], ensure_ascii=False)}
    CODEX["complete_once"](
        out / "planner", "full-1", {"prefix": m["prefix"], "requests": {"full": request}}
    )


def freeze(out: Path, m: Any, reviewed: Path, note: Path) -> None:
    if any(list((out / mode).glob("*.request.json")) for mode in ("planned", "free")):
        raise RuntimeError("drafting already started")
    plan = read(reviewed)
    requests = compose(m["source"], plan)
    if not note.read_text(encoding="utf-8").strip():
        raise ValueError("plan source review required")
    write_new(
        out / "frozen.json",
        {
            "plan": plan,
            "requests": requests,
            "manifest_sha256": sha(out / "manifest.json"),
            "files": {str(p): sha(p) for p in (reviewed, note, out / "planner/full-1.result.json")},
        },
    )


def draft(out: Path, m: Any) -> None:
    f = read(out / "frozen.json")
    if f["manifest_sha256"] != sha(out / "manifest.json") or f["requests"] != compose(
        m["source"], f["plan"]
    ):
        raise ValueError("frozen requests changed")
    if any(sha(Path(p)) != h for p, h in f["files"].items()):
        raise ValueError("frozen plan review changed")
    for mode, name in ORDER:
        CODEX["validate"](out)
        quota(out)
        CODEX["complete_once"](
            out / mode, name, {"prefix": m["prefix"], "requests": f["requests"][mode]}
        )


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("phase", choices=("prepare", "plan", "freeze", "draft"))
    for name in ("out", "source", "reviewed", "note"):
        p.add_argument("--" + name, type=Path, required=name == "out")
    a = p.parse_args()
    out = a.out.resolve()
    if a.phase == "prepare":
        if not a.source or not a.note:
            p.error("prepare requires --source and --note")
        prepare(out, a.source.resolve(), a.note.resolve())
    else:
        m = CODEX["validate"](out)
        if a.phase == "plan":
            plan_scene(out, m)
        elif a.phase == "freeze":
            if not a.reviewed or not a.note:
                p.error("freeze requires --reviewed and --note")
            freeze(out, m, a.reviewed.resolve(), a.note.resolve())
        else:
            draft(out, m)


if __name__ == "__main__":
    main()
