"""Frozen minimal-invention model/transport comparison; no production mutations."""

from __future__ import annotations

import argparse
import dataclasses
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from run import BASELINE, HERE, LOCAL, lock, read, sha, write

DEST = LOCAL / "phase2"
ORDER = (
    "astra-1", "gpt55-1", "opus-1", "gpt55-2", "opus-2",
    "astra-2", "opus-3", "astra-3", "gpt55-3",
)
MODELS = {"astra": "gpt-6-astra", "gpt55": "gpt-5.5", "opus": "claude-opus-5"}
CLAUDE = Path(r"C:\Users\artem\.local\bin\claude.exe")


def prepare() -> None:
    lock()
    if (DEST / "manifest.json").exists():
        raise RuntimeError("Already prepared")
    original = read(LOCAL / "manifest.json")
    if any(sha(Path(p)) != h for p, h in original["files"].items()):
        raise RuntimeError("Phase 1 frozen inputs changed")
    files = dict(original["files"])
    files.update({str(p): sha(p) for p in (HERE / "PHASE2.md", Path(__file__), CLAUDE)})
    write(DEST / "request.json", read(LOCAL / "requests/minimal-1.json"))
    files[str(DEST / "request.json")] = sha(DEST / "request.json")
    manifest = {
        "order": ORDER, "models": MODELS, "files": files, "token_stop": 180000,
        "codex_binary": original["binary"], "claude_binary": str(CLAUDE),
    }
    write(DEST / "manifest.json", manifest)
    write(HERE / "phase2-registration.json", {
        "manifest_sha256": sha(DEST / "manifest.json"),
        "phase1_manifest_sha256": sha(LOCAL / "manifest.json"),
        "request_sha256": sha(DEST / "request.json"),
        "runner_sha256": sha(Path(__file__)), "runbook_sha256": sha(HERE / "PHASE2.md"),
        "models": MODELS, "order": ORDER,
        "binary_sha256": {p: sha(Path(p)) for p in (original["binary"], str(CLAUDE))},
    })
    print("Prepared nine slots; no model calls")


def run() -> None:
    lock()
    if (DEST / "progress.json").exists():
        raise RuntimeError("Already started; no implicit resume")
    from litharness.application import discovery
    from litharness.domain.generation import CompletionRequest
    from litharness.providers.cli import ClaudeCodeProvider, CommandResult
    from litharness.providers.codex_cli import CodexCliProvider, subscription_environment

    if not Path(discovery.__file__).is_relative_to(BASELINE / "source"):
        raise RuntimeError("Use the baseline's frozen interpreter")
    manifest = read(DEST / "manifest.json")
    if sha(DEST / "manifest.json") != read(HERE / "phase2-registration.json")["manifest_sha256"]:
        raise RuntimeError("Prepared manifest changed")
    environment = subscription_environment(dict(os.environ))
    os.environ.clear()
    os.environ.update(environment)
    request = CompletionRequest(**read(DEST / "request.json"))
    progress = {"status": "running", "attempts": 0, "tokens": 0, "slots": [], "stop": None}
    write(DEST / "progress.json", progress)
    try:
        for name in manifest["order"]:
            lock()
            if any(sha(Path(p)) != h for p, h in manifest["files"].items()):
                raise RuntimeError("Frozen input/source/binary drift")
            if progress["tokens"] >= manifest["token_stop"]:
                raise RuntimeError("Registered token bound reached")
            arm = name.split("-")[0]
            model = manifest["models"][arm]
            row = {
                "request": dataclasses.asdict(request), "requested_model": model,
                "started_at": datetime.now(UTC).isoformat(), "status": "started",
            }
            if arm == "opus":
                import json

                binary = manifest["claude_binary"]
                auth = subprocess.run(
                    [binary, "auth", "status", "--json"], env=environment,
                    capture_output=True, text=True, encoding="utf-8", timeout=30, check=True,
                )
                info = json.loads(auth.stdout)
                if not (info.get("loggedIn") and info.get("authMethod") == "claude.ai"
                        and info.get("apiProvider") == "firstParty"):
                    raise RuntimeError("Claude subscription authentication required")
                version = subprocess.run(
                    [binary, "--version"], env=environment, capture_output=True,
                    text=True, encoding="utf-8", timeout=30, check=True,
                ).stdout.strip()

                def capture(
                    argv, *, timeout, cwd=None, stdin=None,
                    row=row, model=model, name=name, version=version,
                ):
                    row["transport"] = {
                        "provider": "claude_code", "requested_model": model,
                        "cli_version": version, "argv": list(argv), "prompt": stdin,
                        "system": argv[argv.index("--system-prompt") + 1],
                        "native_schema": json.loads(argv[argv.index("--json-schema") + 1]),
                        "working_directory": cwd, "environment_keys": sorted(environment),
                        "auth_method": "claude.ai", "mode": "completion",
                    }
                    write(DEST / "calls" / f"{name}.json", row)
                    outcome = subprocess.run(
                        list(argv), env=environment, cwd=cwd, input=stdin or "",
                        capture_output=True, text=True, encoding="utf-8", errors="replace",
                        timeout=timeout, check=False,
                    )
                    row["transport"].update(
                        stdout=outcome.stdout, stderr=outcome.stderr, returncode=outcome.returncode,
                    )
                    return CommandResult(outcome.returncode, outcome.stdout, outcome.stderr)

                provider = ClaudeCodeProvider(binary=binary, model=model, runner=capture)
            else:
                provider = CodexCliProvider(
                    binary=manifest["codex_binary"], model=model,
                    trace_directory=DEST / "transport" / name,
                )
            progress["attempts"] += 1
            write(DEST / "calls" / f"{name}.json", row)
            write(DEST / "progress.json", progress)
            print(f"Starting {name}", flush=True)
            try:
                result = provider.complete(request)
                row.update(result=dataclasses.asdict(result), status="completed")
                if result.usage.total <= 0:
                    raise RuntimeError("Unknown usage")
                progress["tokens"] += result.usage.total
                try:
                    if not isinstance(result.parsed, dict):
                        raise ValueError("No structured invention returned")
                    discovery.Discovery.from_invention(result.parsed)
                    row["validation"] = "passed"
                except (TypeError, ValueError) as error:
                    row["validation"] = str(error)
            except Exception as error:
                row.update(status="failed", error=f"{type(error).__name__}: {error}")
                raise
            finally:
                row["finished_at"] = datetime.now(UTC).isoformat()
                write(DEST / "calls" / f"{name}.json", row)
                progress["slots"].append({"name": name, "status": row["status"]})
                write(DEST / "progress.json", progress)
            print(f"Finished {name}; tokens={progress['tokens']}", flush=True)
    except Exception as error:
        progress["stop"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        progress["status"] = "finished"
        write(DEST / "progress.json", progress)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "run"))
    args = parser.parse_args()
    (prepare if args.mode == "prepare" else run)()
