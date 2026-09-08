"""A standalone, subscription-only first-chapter generator. Standard library only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

MODEL = "claude-opus-5"
SYSTEM = "Write original fiction. Return only the finished chapter, including its chapter heading."
DEFAULT_BRIEF = (
    "Write Chapter 1 of an original LitRPG adventure serial for Royal Road readers, choosing "
    "portal fantasy, isekai, or system apocalypse, or a combination of them. "
    "The reading experience should be a magical adventure: exploring an unfamiliar world, "
    "discovering usable magic, and becoming more capable. Give the protagonist something "
    "they actively want to pursue. Invent the characters, setting, and story. "
    "Use third-person past tense. Aim for about 2,000 words."
)

# Carry OS, locale and connection settings, never inherited model routes, keys or agent controls.
ENV_KEYS = frozenset(
    ["PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "COMSPEC", "TEMP", "TMP",
     "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "HOMEDRIVE", "HOMEPATH",
     "USERNAME", "USERDOMAIN", "LANG", "LC_ALL", "TZ", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
     "NO_PROXY", "SSL_CERT_FILE", "SSL_CERT_DIR", "NODE_EXTRA_CA_CERTS", "TERM"]
)


def subscription_environment(source: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in source.items() if key.upper() in ENV_KEYS}


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def now() -> str:
    return datetime.now(UTC).isoformat()


def invoke(
    argv: list[str], *, cwd: Path, env: dict[str, str], payload: str = "", timeout: int = 30
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        argv,
        input=payload.encode("utf-8"),
        capture_output=True,
        cwd=cwd,
        env=env,
        timeout=timeout,
        shell=False,
        check=False,
    )


def command(executable: Path) -> list[str]:
    return [
        str(executable), "--print", "--safe-mode", "--model", MODEL,
        "--output-format", "json", "--max-turns", "1", "--tools", "",
        "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
        "--setting-sources", "", "--no-session-persistence",
        "--permission-mode", "manual", "--permission-prompts", "none",
        "--system-prompt", SYSTEM,
    ]


def completed_chapter(response: subprocess.CompletedProcess[bytes]) -> tuple[str, dict]:
    if response.returncode:
        raise ValueError(f"Claude exited with code {response.returncode}; see saved output.")
    envelope = json.loads(response.stdout)
    if not isinstance(envelope, dict):
        raise ValueError("Claude did not return a result object.")
    if envelope.get("is_error") is not False or envelope.get("subtype") != "success":
        raise ValueError("Claude reported an unsuccessful result; see saved output.")
    if envelope.get("stop_reason") != "end_turn" or envelope.get("num_turns") != 1:
        raise ValueError("Expected a complete single-turn response; see saved output.")
    chapter = envelope.get("result")
    if not isinstance(chapter, str) or not chapter.strip():
        raise ValueError("Claude returned no chapter text.")
    usage = envelope.get("modelUsage", {})
    if not isinstance(usage, dict) or MODEL not in usage:
        raise ValueError("The response did not identify the requested model; see saved output.")
    return chapter, envelope


def generate(executable: Path, output: Path, brief: str, *, dry_run: bool = False) -> Path:
    if not brief.strip():
        raise ValueError("The brief must not be empty.")
    executable = executable.expanduser().resolve()
    if not executable.is_file() or executable.suffix.lower() in {".cmd", ".bat", ".ps1"}:
        raise ValueError("Choose the native Claude executable, not a shell wrapper.")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    argv = command(executable)
    request = {"system": SYSTEM, "brief": brief, "model": MODEL, "argv": argv}
    write_json(output / "request.json", request)
    digest = hashlib.sha256((output / "request.json").read_bytes()).hexdigest()
    result = {"started_at": now(), "request_sha256": digest, "status": "prepared"}
    write_json(output / "result.json", result)
    if dry_run:
        return output

    env = subscription_environment(dict(os.environ))
    try:
        # Neither the repository nor earlier chapters are available in the working directory.
        with tempfile.TemporaryDirectory(prefix="litharness-clean-") as directory:
            cwd = Path(directory)
            version = invoke([str(executable), "--version"], cwd=cwd, env=env)
            if version.returncode:
                raise ValueError("Could not read the Claude CLI version.")
            result["cli_version"] = version.stdout.decode("utf-8").strip()
            auth = invoke(
                [str(executable), "--safe-mode", "--setting-sources", "",
                 "auth", "status", "--json"], cwd=cwd, env=env,
            )
            if auth.returncode:
                raise ValueError("Subscription login check failed. No generation was attempted.")
            login = json.loads(auth.stdout)
            if not isinstance(login, dict) or not (
                login.get("loggedIn") is True and login.get("authMethod") == "claude.ai"
            ):
                raise ValueError(
                    "A claude.ai subscription login is required. No generation attempted."
                )
            # Do not persist account identifiers, email addresses or raw authentication output.
            result["auth_method"] = login["authMethod"]
            result["subscription_type"] = login.get("subscriptionType")
            result["status"] = "generating"
            write_json(output / "result.json", result)
            try:
                response = invoke(argv, cwd=cwd, env=env, payload=brief, timeout=900)
            except subprocess.TimeoutExpired as error:
                (output / "stdout.json").write_bytes(error.stdout or b"")
                (output / "stderr.txt").write_bytes(error.stderr or b"")
                raise ValueError(
                    "Generation timed out; partial output retained. No retry."
                ) from error
            (output / "stdout.json").write_bytes(response.stdout)
            (output / "stderr.txt").write_bytes(response.stderr)
            chapter, envelope = completed_chapter(response)
            # Exact response, including whitespace. No repair, selection or prose transformation.
            (output / "chapter.md").write_bytes(chapter.encode("utf-8"))
            result.update(
                status="complete", stop_reason=envelope["stop_reason"],
                model_usage=envelope["modelUsage"], usage=envelope.get("usage"),
                chapter_sha256=hashlib.sha256(chapter.encode("utf-8")).hexdigest(),
            )
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        result.update(status="failed", error=str(error))
        raise
    finally:
        result["finished_at"] = now()
        write_json(output / "result.json", result)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default_executable = Path.home() / ".local" / "bin" / (
        "claude.exe" if os.name == "nt" else "claude"
    )
    parser.add_argument("--claude", type=Path, default=default_executable)
    parser.add_argument("--out", type=Path, required=True, help="New directory; never overwritten")
    parser.add_argument(
        "--brief-file", type=Path, help="UTF-8 author brief; otherwise fresh adventure"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Save the request without calling Claude"
    )
    args = parser.parse_args()
    try:
        brief = args.brief_file.read_text(encoding="utf-8") if args.brief_file else DEFAULT_BRIEF
        output = generate(args.claude, args.out, brief, dry_run=args.dry_run)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Stopped: {error}", file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
