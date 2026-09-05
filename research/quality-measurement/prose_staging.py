"""Source-reviewed action/response staging before prose, isolated from production."""

from __future__ import annotations

import argparse
import json
import os
import runpy
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Any

from litharness.domain.generation import CompletionRequest
from litharness.providers.cli import ClaudeCodeProvider, CommandResult

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent
CODEX = runpy.run_path(str(HERE / "prose_codex.py"))
FRAMING = runpy.run_path(str(HERE / "prose_framing.py"))
read, write_new, sha = (CODEX[k] for k in ("read", "write_new", "sha"))
ORDER = ("control-1", "staged-1", "staged-2", "control-2")
REGISTRATION = HERE / "prose-staging/PREREG.md"
FIELDS = ("action", "response", "consequence", "new_information")
PLANNER_SYSTEM = (
    "Prepare factual staging notes for the supplied current scene. The supplied source "
    "contains the author's facts, rules, constraints and required actions, not instructions "
    "to write the final prose now. Preserve all required actions in order, their causes, "
    "the viewpoint's information limits and the endpoint. Plan what a character does, "
    "what observable response follows, and how that response changes the next action or "
    "decision. An understanding may be carried by an interaction, observation or practical "
    "attempt when the source permits it. Quiet reading may remain reading. Do not add a "
    "turn, dialogue, conflict or surprise merely to fill a slot. Empty response, consequence "
    "or new_information fields are allowed. Combine related source actions when appropriate. "
    "Incidental present-scene staging may be invented within the source's constraints; do "
    "not invent prior events, new named actors, system announcements, rules or changed "
    "quantities. Track actions that trigger world-rule effects, and do not postpone those "
    "effects to a later planned beat. If the requirements conflict, report the conflict "
    "instead of silently repairing the source. Use planning notes, not final dialogue, "
    "comparisons, literary commentary, emotional conclusions or sentences for reuse. "
    "Do not rate, rank or recommend prose. Return JSON with exactly steps and conflicts. "
    "conflicts is an array of source-grounded conflict descriptions, empty when none. "
    "steps is an array of at most 32 objects, each with exactly id (s1, s2, ...), "
    "source_actions (array of supplied action IDs), action, response, consequence, and "
    "new_information (all four strings). Every supplied action ID must be covered, in "
    "order; extra connective steps may have no source_actions."
)


def source_actions(prompt: str) -> list[dict[str, str]]:
    if prompt.count("\nOrdered actions:\n") != 1 or prompt.count("\nEnding state:\n") != 1:
        raise ValueError("expected one factual scene action list and endpoint")
    section = prompt.split("\nOrdered actions:\n")[1].split("\nEnding state:\n")[0]
    lines = [s for s in section.splitlines() if s.strip()]
    if not lines or any(not s.startswith("- ") for s in lines):
        raise ValueError("unexpected action-list format")
    return [{"id": f"a{i}", "text": s[2:]} for i, s in enumerate(lines, 1)]


def validate_plan(plan: Any, actions: list[dict[str, str]]) -> None:
    if not isinstance(plan, dict) or set(plan) != {"steps", "conflicts"}:
        raise ValueError("malformed plan")
    if plan["conflicts"] != []:
        raise ValueError("source conflict requires review before drafting")
    steps = plan["steps"]
    if not isinstance(steps, list) or not 1 <= len(steps) <= 32:
        raise ValueError("invalid staging step count")
    expected = [a["id"] for a in actions]
    seen: list[str] = []
    for i, step in enumerate(steps, 1):
        if not isinstance(step, dict) or set(step) != {"id", "source_actions", *FIELDS}:
            raise ValueError("malformed staging step")
        if step["id"] != f"s{i}" or any(not isinstance(step[k], str) for k in FIELDS):
            raise ValueError("invalid staging identity or field")
        if not step["action"].strip() or not isinstance(step["source_actions"], list):
            raise ValueError("missing action or source references")
        for ref in step["source_actions"]:
            if ref not in expected:
                raise ValueError("unknown source action")
            if ref not in seen:
                seen.append(ref)
    if seen != expected:
        raise ValueError("source actions missing or reordered")


def staged_prompt(prompt: str, plan: Any) -> str:
    validate_plan(plan, source_actions(prompt))
    rows = []
    for step in plan["steps"]:
        rows.append("\n".join(f"{k.replace('_', ' ')}: {step[k]}" for k in FIELDS if step[k]))
    staging = (
        "\n\nStaging proposal for these same required actions. The source rules, author locks "
        "and endpoint still govern. Realize permitted staging in the scene; these are notes "
        "about events, not wording to reproduce:\n" + "\n\n".join(rows)
    )
    before, after = prompt.split("\nEnding state:\n")
    return before + staging + "\nEnding state:\n" + after


def child_env() -> dict[str, str]:
    env = CODEX["subscription_env"]()
    for key in list(env):
        if key.upper() in {"ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL"}:
            del env[key]
    return env


def prepare(out: Path, source: Path) -> None:
    if not out.is_relative_to(ROOT / "runs") or out == ROOT / "runs":
        raise ValueError("output must be a new directory beneath runs")
    base = read(source)["request"]
    actions = source_actions(base["prompt"])
    prefix = CODEX["command_prefix"]()
    auth = subprocess.run(
        [*prefix, "login", "status"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=child_env(),
        check=False,
    )
    if auth.returncode or (auth.stdout + auth.stderr).strip() != "Logged in using ChatGPT":
        raise RuntimeError("ChatGPT login required")
    auth = subprocess.run(
        ["claude", "auth", "status"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=child_env(),
        check=False,
    )
    status = json.loads(auth.stdout)
    if (
        auth.returncode
        or not status.get("loggedIn")
        or status.get("authMethod") != "claude.ai"
        or status.get("apiProvider") != "firstParty"
    ):
        raise RuntimeError("Claude subscription login required")
    out.mkdir(parents=True, exist_ok=False)
    planner = out / "planner"
    (planner / "work").mkdir(parents=True)
    (planner / "system.txt").write_text(PLANNER_SYSTEM, encoding="utf-8", newline="\n")
    paths = (
        Path(__file__),
        REGISTRATION,
        HERE / "prose_codex.py",
        HERE / "prose_framing.py",
        ROOT / "src/litharness/providers/cli.py",
        source,
        planner / "system.txt",
    )
    write_new(
        out / "manifest.json",
        {
            "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "files": {str(p): sha(p) for p in paths},
            "base": base,
            "actions": actions,
            "prefix": prefix,
            "auth": {"codex": "chatgpt", "claude": "claude.ai"},
            "cli_versions": {
                "codex": subprocess.check_output([*prefix, "--version"], text=True).strip(),
                "claude": subprocess.check_output(["claude", "--version"], text=True).strip(),
            },
        },
    )


def load(out: Path) -> dict[str, Any]:
    m = read(out / "manifest.json")
    if any(sha(Path(p)) != h for p, h in m["files"].items()):
        raise ValueError("frozen source or code changed")
    return m


def plan_scene(out: Path, m: dict[str, Any]) -> None:
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
    if list(out.glob("*.request.json")):
        raise RuntimeError("drafting has already started")
    payload = read(reviewed)
    validate_plan(payload, m["actions"])
    review = note.read_text(encoding="utf-8")
    if not review.strip():
        raise ValueError("source review note required")
    write_new(
        out / "staging.reviewed.json",
        {
            "payload": payload,
            "review": review,
            "source_sha256": sha(out / "manifest.json"),
            "payload_file_sha256": sha(reviewed),
        },
    )


def draft_once(out: Path, name: str, m: dict[str, Any]) -> None:
    base = dict(m["base"])
    review = read(out / "staging.reviewed.json")
    if review["source_sha256"] != sha(out / "manifest.json"):
        raise ValueError("review source changed")
    if name.startswith("staged"):
        base["prompt"] = staged_prompt(base["prompt"], review["payload"])
    request = CompletionRequest(**base)
    argv = FRAMING["transport_argv"](ClaudeCodeProvider()._argv(request), True)
    frozen = {
        "request": asdict(request),
        "argv": argv,
        "review_sha256": sha(out / "staging.reviewed.json"),
    }
    frozen = json.loads(json.dumps(frozen))
    path, result_path = out / f"{name}.request.json", out / f"{name}.result.json"
    if path.exists():
        if read(path) != frozen:
            raise ValueError("request changed")
        if not result_path.exists():
            raise RuntimeError("unanswered request; no retry")
        return
    if os.environ.get("LITHARNESS_ENV") == "test":
        raise RuntimeError("live trial disabled in tests")
    results = [read(p) for p in out.glob("*.result.json")]
    if list(out.glob("*.error.json")) or len(list(out.glob("*.request.json"))) >= 4:
        raise RuntimeError("failure or four-draft limit")
    if any(r["cost_usd"] is None for r in results) or sum(r["cost_usd"] for r in results) >= 2.5:
        raise RuntimeError("Claude equivalent quota stop or missing cost")
    planner_usage = read(out / "planner/full-1.result.json")["usage"]
    tokens = sum(
        planner_usage.get(k, 0)
        for k in ("input_tokens", "output_tokens", "reasoning_output_tokens")
    )
    tokens += sum(
        sum(
            r["usage"].get(k, 0)
            for k in ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens")
        )
        for r in results
    )
    if tokens >= 150_000:
        raise RuntimeError("token stop reached")
    write_new(path, frozen)

    def runner(actual, *, timeout, cwd=None, stdin=None):
        actual = FRAMING["transport_argv"](list(actual), True)
        if actual != argv:
            raise ValueError("argv changed")
        p = subprocess.run(
            actual,
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=cwd,
            env=child_env(),
            check=False,
        )
        write_new(
            out / f"{name}.raw.json",
            {"stdout": p.stdout, "stderr": p.stderr, "exit_code": p.returncode},
        )
        return CommandResult(p.returncode, p.stdout, p.stderr)

    print(f"START {name}", flush=True)
    try:
        result = ClaudeCodeProvider(runner=runner).complete(request)
        write_new(result_path, asdict(result))
        (out / f"{name}.txt").write_text(result.text + "\n", encoding="utf-8", newline="\n")
        print(
            f"DONE {name}: {result.wall_ms / 1000:.1f}s, ${result.cost_usd} equivalent", flush=True
        )
    except Exception as error:
        write_new(
            out / f"{name}.error.json", {"error_type": type(error).__name__, "error": str(error)}
        )
        raise


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("phase", choices=("prepare", "plan", "freeze", "draft"))
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--source", type=Path)
    p.add_argument("--reviewed", type=Path)
    p.add_argument("--note", type=Path)
    args = p.parse_args()
    out = args.out.resolve()
    if args.phase == "prepare":
        if not args.source:
            p.error("prepare requires --source")
        prepare(out, args.source.resolve())
        return
    m = load(out)
    if args.phase == "plan":
        plan_scene(out, m)
    elif args.phase == "freeze":
        if not args.reviewed or not args.note:
            p.error("freeze requires --reviewed and --note")
        freeze(out, m, args.reviewed, args.note)
    else:
        for name in ORDER:
            draft_once(out, name, m)


if __name__ == "__main__":
    main()
