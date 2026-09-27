"""The only module that spawns a CLI: an isolated, receipted `codex exec` from an empty directory."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from . import files

# The child sees only these variables: no API keys, and none of git's GIT_* location variables.
ENV_KEYS = {
    "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "COMSPEC", "TEMP", "TMP",
    "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "HOMEDRIVE",
    "HOMEPATH", "USERNAME", "USERDOMAIN", "LANG", "LC_ALL", "TZ", "HTTP_PROXY",
    "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "SSL_CERT_FILE", "SSL_CERT_DIR",
    "NODE_EXTRA_CA_CERTS", "TERM", "CODEX_HOME", "CODEX_CA_CERTIFICATE",
}
DISABLED = (
    "shell_tool", "multi_agent", "multi_agent_v2", "apps", "plugins", "hooks", "memories",
    "code_mode", "view_image", "browser_use", "browser_use_external",
    "browser_use_full_cdp_access", "in_app_browser", "computer_use", "image_generation",
    "sleep_tool", "goals", "skill_search", "tool_suggest", "workspace_dependencies",
    "skill_mcp_dependency_install",
)
BUNDLED = ("node_modules/@openai/codex/node_modules/@openai/codex-win32-x64/vendor/"
           "x86_64-pc-windows-msvc/bin/codex.exe")


class Fault(ValueError):
    """The CLI did not return one clean answer; the caller may retry, and a retry is never a draw."""


def native_binary(explicit: str | None = None) -> Path:
    candidate = explicit or os.environ.get("LITHARNESS_CODEX") or shutil.which("codex")
    if not candidate:
        raise ValueError("Codex CLI is missing; set LITHARNESS_CODEX to its native executable.")
    path = Path(candidate).resolve()
    if path.suffix.lower() in {".cmd", ".bat", ".ps1"} or (os.name == "nt" and not path.suffix):
        # npm's Windows launcher points at this native package; never execute a shell wrapper.
        bundled = path.parent / BUNDLED
        if explicit or not bundled.is_file():
            raise ValueError("Pass a native codex executable, not a shell wrapper.")
        path = bundled
    if not path.is_file():
        raise ValueError(f"Codex executable does not exist: {path}")
    return path


def parse_result(stdout: str, final: str) -> dict:
    events = [json.loads(line) for line in stdout.splitlines() if line.strip()]
    if any(not isinstance(e, dict) for e in events):
        raise Fault("Provider returned a non-object event")
    turns = [e for e in events if e.get("type") == "turn.completed"]
    if len(turns) != 1 or any(e.get("type") in {"turn.failed", "error"} for e in events):
        raise Fault("Provider did not complete one clean turn; inspect events.jsonl")
    messages = []
    for e in events:
        if e.get("type", "").startswith("item."):
            item = e.get("item", {})
            if item.get("type") not in {"agent_message", "reasoning"}:
                raise Fault(f"Unexpected provider tool activity: {item.get('type')}")
            if e["type"] == "item.completed" and item.get("type") == "agent_message":
                messages.append(item.get("text", ""))
    if not final.strip() or not messages or messages[-1].rstrip() != final.rstrip():
        raise Fault("Final artifact does not match the provider's last message")
    usage = turns[0].get("usage", {})
    for key in ("input_tokens", "output_tokens", "cached_input_tokens"):
        value = usage.get(key, 0 if key == "cached_input_tokens" else None)
        if type(value) is not int or value < 0:
            raise Fault("Missing or invalid token usage")
    if usage.get("cached_input_tokens", 0) > usage["input_tokens"]:
        raise Fault("Cached tokens exceed input tokens")
    return usage


def no_git(path: Path) -> Path:
    for folder in (path, *path.parents):
        if (folder / ".git").exists():
            raise Fault(f"Working directory is inside a git tree: {folder}")
    return path


def argv(binary: Path, work: Path, final: Path, system: Path, model: str, effort: str) -> list[str]:
    settings = {"forced_login_method": "chatgpt", "model_provider": "openai",
                "model_instructions_file": system.as_posix(), "model_reasoning_effort": effort,
                "project_doc_max_bytes": 0, "web_search": "disabled", "hide_agent_reasoning": True,
                "tools.update_plan.enabled": False,
                "tools.experimental_request_user_input.enabled": False,
                "skills.include_instructions": False, "skills.bundled.enabled": False,
                "history.persistence": "none"}
    settings.update({f"features.{name}": False for name in DISABLED})
    command = [str(binary), "exec", "--ignore-user-config", "--ignore-rules", "--ephemeral",
               "--skip-git-repo-check", "--sandbox", "read-only", "--cd", str(work),
               "--model", model, "--json", "--color", "never", "--output-last-message", str(final)]
    for key, value in settings.items():
        command.extend(["-c", f"{key}={json.dumps(value)}"])
    return command + ["-"]


def codex(prompt: str, directory: Path, *, system: str, model: str, effort: str, binary: Path,
          runner=subprocess.run, cwd: Path | None = None, timeout: int = 900) -> tuple[str, dict]:
    """One call into a new directory. Only the canary passes cwd; everyone else runs outside git."""
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    final_path = directory / "final.md"
    receipt = {"model": model, "effort": effort, "status": "running", "usage": None,
               "prompt_sha256": files.write(directory / "prompt.txt", prompt),
               "system_sha256": files.write(directory / "system.txt", system),
               "started_utc": files.utc()}
    start = time.monotonic()
    files.save(directory / "receipt.json", receipt)
    try:
        with tempfile.TemporaryDirectory(prefix="litharness-empty-") as empty:
            work = Path(cwd) if cwd else no_git(Path(empty).resolve())
            receipt["argv"] = argv(binary, work, final_path, directory / "system.txt", model, effort)
            files.save(directory / "receipt.json", receipt)
            env = {k: v for k, v in os.environ.items() if k.upper() in ENV_KEYS}
            try:
                result = runner(receipt["argv"], input=prompt.encode("utf-8"), capture_output=True,
                                cwd=str(work), env=env, timeout=timeout, shell=False)
            except subprocess.TimeoutExpired as error:
                for name, output in (("events.jsonl", error.stdout), ("stderr.txt", error.stderr)):
                    files.write(directory / name, output if isinstance(output, bytes) else (output or ""))
                raise Fault("Provider timeout; usage unknown") from error
            files.write(directory / "events.jsonl", result.stdout)
            files.write(directory / "stderr.txt", result.stderr)
            receipt["returncode"] = result.returncode
            if result.returncode:
                raise Fault(f"Provider exited {result.returncode}; see {directory}")
            final = files.read(final_path) if final_path.is_file() else ""
            receipt["usage"] = parse_result(result.stdout.decode("utf-8", "replace"), final)
            receipt.update(status="completed", output_sha256=files.digest(final_path))
            return final, receipt
    except Exception as error:
        receipt.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        receipt["seconds"] = round(time.monotonic() - start, 3)
        files.save(directory / "receipt.json", receipt)
