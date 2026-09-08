"""The same clean-start writing request through the Codex subscription CLI."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from clean_start.chapter import (
    DEFAULT_BRIEF,
    SYSTEM,
    invoke,
    now,
    subscription_environment,
    write_json,
)

MODEL = "gpt-6-astra"
EFFORT = "medium"
BUILTIN_CONTROLS = "unused-builtins-disabled.v1"


def command(executable: Path, output: Path, working: Path) -> list[str]:
    argv = [
        str(executable), "exec", "--ignore-user-config", "--ignore-rules", "--ephemeral",
        "--skip-git-repo-check", "--sandbox", "read-only", "--cd", str(working),
        "--model", MODEL, "--json", "--color", "never",
        "--output-last-message", str(output / "response.txt"),
    ]
    settings = {
        "forced_login_method": "chatgpt", "model_provider": "openai",
        "model_instructions_file": (output / "system.txt").as_posix(),
        "model_reasoning_effort": EFFORT, "project_doc_max_bytes": 0,
        "web_search": "disabled", "hide_agent_reasoning": True,
        "features.shell_tool": False, "features.multi_agent": False, "features.apps": False,
        "features.plugins": False, "features.hooks": False, "features.memories": False,
        "features.code_mode": False, "features.view_image": False,
        "features.browser_use": False, "features.browser_use_external": False,
        "features.browser_use_full_cdp_access": False, "features.in_app_browser": False,
        "features.computer_use": False, "features.image_generation": False,
        "features.sleep_tool": False, "features.goals": False, "features.skill_search": False,
        "features.tool_suggest": False, "features.workspace_dependencies": False,
        "features.skill_mcp_dependency_install": False, "features.multi_agent_v2": False,
        "tools.update_plan.enabled": False, "tools.experimental_request_user_input.enabled": False,
        "skills.include_instructions": False, "skills.bundled.enabled": False,
        "history.persistence": "none",
    }
    for key, value in settings.items():
        argv.extend(["-c", f"{key}={json.dumps(value)}"])
    return [*argv, "-"]


def read_result(response: subprocess.CompletedProcess[bytes]) -> tuple[str, dict]:
    if response.returncode:
        raise ValueError(f"Codex exited with code {response.returncode}; see saved output.")
    events = [json.loads(line) for line in response.stdout.splitlines() if line.startswith(b"{")]
    completed = [event for event in events if event.get("type") == "turn.completed"]
    if len(completed) != 1 or any(
        event.get("type") in {"turn.failed", "error"} for event in events
    ):
        raise ValueError("Expected one complete Codex turn; see saved events.")
    items = [event["item"] for event in events if event.get("type") == "item.completed"]
    activity = [event["item"] for event in events if str(event.get("type", "")).startswith("item.")]
    if any(item.get("type") not in {"agent_message", "reasoning"} for item in activity):
        raise ValueError("Unexpected tool activity; see saved events.")
    messages = [item["text"] for item in items if item.get("type") == "agent_message"]
    if len(messages) != 1 or not messages[0].strip():
        raise ValueError("Expected one chapter message; see saved events.")
    return messages[0], completed[0].get("usage", {})


def generate(executable: Path, output: Path, brief: str) -> Path:
    executable = executable.expanduser().resolve()
    if not executable.is_file() or executable.suffix.lower() in {".cmd", ".bat", ".ps1"}:
        raise ValueError("Choose the native Codex executable, not a shell wrapper.")
    if not brief.strip():
        raise ValueError("The brief must not be empty.")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output / "system.txt").write_bytes(SYSTEM.encode("utf-8"))
    env = subscription_environment(dict(os.environ))
    if "CODEX_HOME" in os.environ:
        env["CODEX_HOME"] = os.environ["CODEX_HOME"]
    result = {"status": "prepared", "started_at": now()}
    try:
        with tempfile.TemporaryDirectory(prefix="litharness-clean-codex-") as directory:
            working = Path(directory)
            argv = command(executable, output, working)
            write_json(output / "request.json", {
                "system": SYSTEM, "brief": brief, "model": MODEL, "effort": EFFORT, "argv": argv,
                "builtin_controls": BUILTIN_CONTROLS,
            })
            result.update(
                request_sha256=hashlib.sha256((output / "request.json").read_bytes()).hexdigest(),
                executable_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
                code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                cwd=str(working), cwd_initially_empty=not any(working.iterdir()),
                environment_names=sorted(env),
            )
            write_json(output / "result.json", result)
            version = invoke([str(executable), "--version"], cwd=working, env=env)
            if version.returncode:
                raise ValueError("Could not read the Codex CLI version.")
            result["cli_version"] = version.stdout.decode("utf-8").strip()
            auth = invoke(
                [str(executable), "-c", 'forced_login_method="chatgpt"',
                 "-c", 'model_provider="openai"', "login", "status"], cwd=working, env=env,
            )
            if auth.returncode or b"Logged in using ChatGPT" not in auth.stdout + auth.stderr:
                raise ValueError("ChatGPT subscription login required. No generation attempted.")
            result.update(auth_method="chatgpt", status="generating")
            write_json(output / "result.json", result)
            try:
                response = invoke(argv, cwd=working, env=env, payload=brief, timeout=900)
            except subprocess.TimeoutExpired as error:
                (output / "events.jsonl").write_bytes(error.stdout or b"")
                (output / "stderr.txt").write_bytes(error.stderr or b"")
                raise ValueError("Codex timed out; partial output retained, no retry.") from error
            (output / "events.jsonl").write_bytes(response.stdout)
            (output / "stderr.txt").write_bytes(response.stderr)
            text, usage = read_result(response)
            saved = (output / "response.txt").read_text(encoding="utf-8")
            if saved.rstrip("\n") != text.rstrip("\n"):
                raise ValueError("Final output and recorded message disagree.")
            (output / "chapter.md").write_bytes(text.encode("utf-8"))
            result.update(
                status="complete", usage=usage,
                chapter_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            )
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        result.update(status="failed", error=str(error))
        raise
    finally:
        result["finished_at"] = now()
        write_json(output / "result.json", result)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex", type=Path, required=True, help="Native Codex executable")
    parser.add_argument("--out", type=Path, required=True, help="New output directory")
    parser.add_argument("--brief-file", type=Path)
    args = parser.parse_args()
    brief = args.brief_file.read_text(encoding="utf-8") if args.brief_file else DEFAULT_BRIEF
    print(generate(args.codex, args.out, brief))


if __name__ == "__main__":
    main()
