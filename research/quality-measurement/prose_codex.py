"""Subscription-only Codex drafting diagnostic; no production adapter or selection."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REGISTRATION = Path(__file__).with_name("prose-codex") / "PREREG.md"
MODEL = "gpt-6-astra"
EFFORT = "high"
ORDER = ("full-1", "focused-1", "focused-2", "full-2")
TOKEN_STOP = 120_000
DISABLED = (
    "apps",
    "plugins",
    "remote_plugin",
    "hooks",
    "shell_tool",
    "unified_exec",
    "code_mode",
    "code_mode_host",
    "multi_agent",
    "multi_agent_v2",
    "memories",
    "browser_use",
    "computer_use",
    "image_generation",
    "view_image",
    "skill_search",
    "skill_mcp_dependency_install",
    "tool_suggest",
    "goals",
    "sleep_tool",
    "workspace_dependencies",
    "unbounded_connection_retries",
)
REMOVED_ENV = (
    "OPENAI_API_KEY",
    "CODEX_API_KEY",
    "CODEX_CI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_ORG_ID",
    "OPENAI_PROJECT_ID",
)


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_new(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def subscription_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k.upper() not in REMOVED_ENV}


def command_prefix() -> list[str]:
    # Invoke the installed npm entry point without sending prose through cmd/PowerShell.
    shim = shutil.which("codex")
    node = shutil.which("node")
    if not shim or not node:
        raise RuntimeError("installed Codex CLI and Node are required")
    entry = Path(shim).parent / "node_modules/@openai/codex/bin/codex.js"
    if not entry.is_file():
        raise RuntimeError("Codex npm entry point unavailable; no transport fallback")
    return [node, str(entry)]


def argv(prefix: list[str], system_file: Path, work: Path) -> list[str]:
    result = [
        *prefix,
        "exec",
        "--ignore-user-config",
        "--strict-config",
        "--ephemeral",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "--json",
        "--color",
        "never",
        "--cd",
        str(work),
        "--model",
        MODEL,
    ]
    settings = {
        "forced_login_method": "chatgpt",
        "model_provider": "openai",
        "model_instructions_file": str(system_file),
        "model_reasoning_effort": EFFORT,
        "project_doc_max_bytes": 0,
        "personality": "none",
        "web_search": "disabled",
        "developer_instructions": "",
        "approval_policy": "never",
        "features.skip_host_skill_discovery": True,
    }
    for key, value in settings.items():
        result += ["-c", f"{key}={json.dumps(value)}"]
    for feature in DISABLED:
        result += ["--disable", feature]
    return [*result, "-"]


def parse_events(stdout: str) -> dict[str, Any]:
    events = [json.loads(line) for line in stdout.splitlines() if line.strip()]
    if any(e.get("type") in {"error", "turn.failed"} for e in events):
        raise ValueError("Codex reported an error or failed turn")
    completed = [e for e in events if e.get("type") == "turn.completed"]
    if len(completed) != 1:
        raise ValueError("expected exactly one completed turn")
    items, notices = [], []
    turn_started = False
    for event in events:
        if event.get("type") == "turn.started":
            turn_started = True
        if event.get("type") != "item.completed":
            continue
        item = event["item"]
        message = item.get("message", "")
        configuration_notice = message == (
            "Code Mode is unavailable because code-mode host is disabled. Code mode will "
            "fail closed; enable `features.code_mode_host` and install `codex-code-mode-host`."
        ) or re.fullmatch(
            r"Under-development features enabled: skip_host_skill_discovery\. "
            r"Under-development features are incomplete and may behave unpredictably\. "
            r"To suppress this warning, set `suppress_unstable_features_warning = true` "
            r"in [^\r\n]+config\.toml\.",
            message,
        )
        if item.get("type") == "error" and not turn_started and configuration_notice:
            notices.append(message)
        else:
            items.append(item)
    if any(i.get("type") not in {"reasoning", "agent_message"} for i in items):
        raise ValueError("unexpected tool or non-prose item")
    # A started tool is a failure even if it never completed.
    if any(
        e.get("type") == "item.started"
        and e.get("item", {}).get("type") not in {"reasoning", "agent_message"}
        for e in events
    ):
        raise ValueError("unexpected tool start")
    messages = [i["text"] for i in items if i.get("type") == "agent_message"]
    if len(messages) != 1 or not messages[0].strip():
        raise ValueError("expected one nonempty final prose message")
    usage = completed[0].get("usage")
    keys = ("input_tokens", "cached_input_tokens", "output_tokens")
    if not isinstance(usage, dict) or any(
        type(usage.get(k)) is not int or usage[k] < 0 for k in keys
    ):
        raise ValueError("missing or invalid quota usage")
    if usage["cached_input_tokens"] > usage["input_tokens"]:
        raise ValueError("cached input exceeds total input")
    return {
        "text": messages[0],
        "usage": usage,
        "event_types": [e["type"] for e in events],
        "configuration_notices": notices,
    }


def validate(out: Path) -> dict[str, Any]:
    manifest = read(out / "manifest.json")
    if any(sha(Path(p)) != digest for p, digest in manifest["files"].items()):
        raise ValueError("frozen input, code or registration changed")
    return manifest


def complete_once(out: Path, name: str, manifest: dict[str, Any]) -> dict[str, Any]:
    if name not in ORDER:
        raise ValueError("unregistered condition")
    base = manifest["requests"][name.split("-")[0]]
    arguments = argv(manifest["prefix"], out / "system.txt", out / "work")
    frozen = {
        "system": base["system"],
        "prompt": base["prompt"],
        "argv": arguments,
        "requested_model": MODEL,
        "reasoning_effort": EFFORT,
        "authentication": "chatgpt",
        "removed_environment_keys": list(REMOVED_ENV),
    }
    request_path, result_path = out / f"{name}.request.json", out / f"{name}.result.json"
    if request_path.exists():
        if read(request_path) != frozen:
            raise ValueError("request identity changed")
        if not result_path.exists():
            raise RuntimeError("request has no result; no automatic retry")
        result = read(result_path)
        if result["status"] != "completed":
            raise RuntimeError("recorded failure; no automatic retry")
        return result
    if os.environ.get("LITHARNESS_ENV") == "test":
        raise RuntimeError("live trial is disabled in tests")
    previous = [read(p) for p in out.glob("*.result.json")]
    if any(r["status"] != "completed" for r in previous):
        raise RuntimeError("a previous invocation failed")
    if len(list(out.glob("*.request.json"))) >= len(ORDER):
        raise RuntimeError("four-invocation limit reached")
    tokens = sum(r["usage"]["input_tokens"] + r["usage"]["output_tokens"] for r in previous)
    if tokens >= TOKEN_STOP:
        raise RuntimeError("quota token stop reached")
    write_new(request_path, frozen)
    print(f"START {name}", flush=True)
    started = time.monotonic()
    raw: dict[str, Any] = {}
    try:
        process = subprocess.run(
            arguments,
            input=base["prompt"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=out / "work",
            env=subscription_env(),
            check=False,
            timeout=900,
        )
        raw = {"stdout": process.stdout, "stderr": process.stderr, "exit_code": process.returncode}
        write_new(out / f"{name}.raw.json", raw)
        if process.returncode:
            raise RuntimeError(f"Codex exited {process.returncode}; see retained raw response")
        parsed = parse_events(process.stdout)
        result = {
            "status": "completed",
            **parsed,
            "requested_model": MODEL,
            "resolved_model": None,
            "cost_usd": None,
            "authentication": "chatgpt",
        }
    except Exception as error:
        result = {"status": "failed", "error_type": type(error).__name__, "error": str(error)}
        if isinstance(error, subprocess.TimeoutExpired):
            # Preserve captured diagnostics without assuming TimeoutExpired decoded bytes.
            for key in ("stdout", "stderr"):
                value = getattr(error, key) or b""
                raw[key] = (
                    value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
                )
            write_new(out / f"{name}.raw.json", raw)
    result["wall_ms"] = round(1000 * (time.monotonic() - started))
    write_new(result_path, result)
    if result["status"] != "completed":
        raise RuntimeError(f"{name} failed; retained, no retry")
    (out / f"{name}.txt").write_text(result["text"] + "\n", encoding="utf-8", newline="\n")
    print(f"DONE {name}: {result['wall_ms'] / 1000:.1f}s, {result['usage']}", flush=True)
    return result


def prepare(out: Path, full: Path, focused: Path) -> None:
    if not out.is_relative_to(ROOT / "runs") or out == ROOT / "runs":
        raise ValueError("output must be a new directory beneath runs")
    requests = {k: read(p)["request"] for k, p in (("full", full), ("focused", focused))}
    if requests["full"]["system"] != requests["focused"]["system"]:
        raise ValueError("systems differ")
    if any(r.get("allowed_tools") or r.get("schema") for r in requests.values()):
        raise ValueError("this trial requires tool-free unstructured source requests")
    prefix = command_prefix()
    auth = subprocess.run(
        [*prefix, "login", "status"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=subscription_env(),
        check=False,
    )
    if auth.returncode or (auth.stdout + auth.stderr).strip() != "Logged in using ChatGPT":
        raise RuntimeError("subscription login not confirmed; no API or login fallback")
    version = subprocess.check_output([*prefix, "--version"], text=True).strip()
    out.mkdir(parents=True, exist_ok=False)
    (out / "work").mkdir()
    (out / "system.txt").write_text(requests["full"]["system"], encoding="utf-8", newline="\n")
    paths = (Path(__file__), REGISTRATION, full, focused, out / "system.txt", Path(prefix[1]))
    write_new(
        out / "manifest.json",
        {
            "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "cli_version": version,
            "prefix": prefix,
            "requests": requests,
            "files": {str(p): sha(p) for p in paths},
            "order": list(ORDER),
            "authentication": "chatgpt",
            "token_stop": TOKEN_STOP,
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "draft"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--full", type=Path)
    parser.add_argument("--focused", type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    if args.phase == "prepare":
        if not args.full or not args.focused:
            parser.error("prepare requires --full and --focused")
        prepare(out, args.full.resolve(), args.focused.resolve())
    else:
        manifest = validate(out)
        for name in ORDER:
            complete_once(out, name, manifest)


if __name__ == "__main__":
    main()
