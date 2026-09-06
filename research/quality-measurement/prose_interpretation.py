"""Frozen brief ablation with identical staged actions; subscription-only diagnostic."""

from __future__ import annotations

import argparse
import runpy
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
ACTIONS = runpy.run_path(str(HERE / "prose_actions.py"))
CODEX = ACTIONS["CODEX"]
read, write_new, sha = (CODEX[k] for k in ("read", "write_new", "sha"))
REGISTRATION = HERE / "prose-interpretation/PREREG.md"
ORDER = ("full-1", "focused-1", "focused-2", "full-2")
TOKEN_STOP = 90_000


def action_lines(prompt: str) -> list[str]:
    if prompt.count("\nAction plan:\n") != 1 or prompt.count("\nEnding state:\n") != 1:
        raise ValueError("one action plan and ending required")
    before, ending = prompt.split("\nEnding state:\n")
    if "\nAction plan:\n" not in before or not ending.strip():
        raise ValueError("action plan must precede a nonempty ending")
    rows = before.split("\nAction plan:\n")[1].splitlines()
    actions = [r for r in rows if r.startswith("action: ")]
    if not actions or any(not r.removeprefix("action: ").strip() for r in actions):
        raise ValueError("nonempty staged actions required")
    return actions


def paired_requests(source: Any, amendment: Any) -> dict[str, Any]:
    if any(
        not isinstance(source.get(k), str) or not source[k].strip() for k in ("system", "prompt")
    ):
        raise ValueError("source system and prompt required")
    if source.get("allowed_tools") or source.get("schema"):
        raise ValueError("tool-free unstructured source required")
    base = {k: source[k] for k in ("system", "prompt")}
    treatment = ACTIONS["reconcile"](base, amendment)
    if action_lines(base["prompt"]) != action_lines(treatment["prompt"]):
        raise ValueError("staged actions changed")
    if treatment == base:
        raise ValueError("empty intervention")
    return {"full": base, "focused": treatment}


def prepare(out: Path, source: Path, amendment: Path, note: Path) -> None:
    if not out.is_relative_to(ROOT / "runs") or out == ROOT / "runs":
        raise ValueError("output must be beneath runs")
    requests = paired_requests(read(source), read(amendment))
    if not note.read_text(encoding="utf-8").strip():
        raise ValueError("source review required before drafting")
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
    for condition, request in requests.items():
        folder = out / condition
        (folder / "work").mkdir(parents=True)
        (folder / "system.txt").write_text(request["system"], encoding="utf-8", newline="\n")
    paths = [
        Path(__file__),
        REGISTRATION,
        REGISTRATION.with_name("RUNBOOK.md"),
        source,
        amendment,
        note,
        Path(prefix[1]),
        *(HERE / name for name in ("prose_actions.py", "prose_codex.py")),
        *(out / c / "system.txt" for c in requests),
    ]
    write_new(
        out / "manifest.json",
        {
            "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "cli_version": subprocess.check_output([*prefix, "--version"], text=True).strip(),
            "prefix": prefix,
            "requests": requests,
            "files": {str(p): sha(p) for p in paths},
            "order": list(ORDER),
            "token_stop": TOKEN_STOP,
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


def draft(out: Path) -> None:
    manifest = CODEX["validate"](out)
    for name in ORDER:
        quota(out)
        CODEX["validate"](out)
        condition = name.split("-")[0]
        # Each condition has its own hashed system file. Never reuse another arm's system.
        CODEX["complete_once"](out / condition, name, manifest)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("phase", choices=("prepare", "draft"))
    for flag in ("out", "source", "amendment", "note"):
        p.add_argument("--" + flag, type=Path, required=flag == "out")
    args = p.parse_args()
    if args.phase == "prepare":
        if not all((args.source, args.amendment, args.note)):
            p.error("prepare requires --source, --amendment and --note")
        prepare(
            args.out.resolve(), args.source.resolve(), args.amendment.resolve(), args.note.resolve()
        )
    else:
        draft(args.out.resolve())


if __name__ == "__main__":
    main()
