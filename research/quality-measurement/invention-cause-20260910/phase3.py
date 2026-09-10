"""Remove native catalog prose while preserving the invention request and model routes."""

from __future__ import annotations

import argparse
import dataclasses
import json
from datetime import UTC, datetime
from pathlib import Path

from run import BASELINE, HERE, LOCAL, lock, read, sha, write

DEST = LOCAL / "phase3"
ORDER = (
    "astra-control-1", "gpt55-blank-1", "astra-blank-1", "gpt55-control-1",
    "gpt55-control-2", "astra-blank-2", "gpt55-blank-2", "astra-control-2",
)
MODELS = {"astra": "gpt-6-astra", "gpt55": "gpt-5.5"}


def blank(value):
    if isinstance(value, str):
        return ""
    if isinstance(value, list):
        return [blank(v) for v in value]
    if isinstance(value, dict):
        return {k: blank(v) for k, v in value.items()}
    return value


def prepare() -> None:
    lock()
    if (DEST / "manifest.json").exists():
        raise RuntimeError("Already prepared")
    prior = read(LOCAL / "phase2/manifest.json")
    if any(sha(Path(p)) != h for p, h in prior["files"].items()):
        raise RuntimeError("Prior frozen inputs changed")
    cache = Path(r"C:\Users\artem\.codex\models_cache.json")
    catalog = {"models": read(cache)["models"]}
    write(DEST / "control-catalog.json", catalog)
    for model in catalog["models"]:
        if model.get("slug") in MODELS.values():
            model["model_messages"] = blank(model["model_messages"])
    write(DEST / "blank-catalog.json", catalog)
    write(DEST / "request.json", read(LOCAL / "requests/minimal-1.json"))
    files = dict(prior["files"])
    files.update({str(p): sha(p) for p in (
        HERE / "PHASE3.md", Path(__file__), DEST / "control-catalog.json",
        DEST / "blank-catalog.json", DEST / "request.json",
    )})
    manifest = {
        "order": ORDER, "models": MODELS, "files": files,
        "binary": prior["codex_binary"], "token_stop": 120000,
        "source_catalog_sha256": sha(cache),
    }
    write(DEST / "manifest.json", manifest)
    write(HERE / "phase3-registration.json", {
        "manifest_sha256": sha(DEST / "manifest.json"), "order": ORDER, "models": MODELS,
        "request_sha256": sha(DEST / "request.json"),
        "runner_sha256": sha(Path(__file__)), "runbook_sha256": sha(HERE / "PHASE3.md"),
        "catalog_sha256": {arm: sha(DEST / f"{arm}-catalog.json") for arm in ("control", "blank")},
    })
    print("Prepared eight slots; no model calls")


def run() -> None:
    lock()
    if (DEST / "progress.json").exists():
        raise RuntimeError("Already started; no implicit resume")
    from litharness.application import discovery
    from litharness.domain.generation import CompletionRequest
    from litharness.providers.codex_cli import CodexCliProvider, subprocess_runner

    if not Path(discovery.__file__).is_relative_to(BASELINE / "source"):
        raise RuntimeError("Use the frozen baseline interpreter")
    manifest = read(DEST / "manifest.json")
    if sha(DEST / "manifest.json") != read(HERE / "phase3-registration.json")["manifest_sha256"]:
        raise RuntimeError("Prepared manifest changed")
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
            model_key, arm, _ = name.split("-")
            model = manifest["models"][model_key]
            catalog = DEST / f"{arm}-catalog.json"
            row = {
                "request": dataclasses.asdict(request), "requested_model": model,
                "catalog_sha256": sha(catalog), "started_at": datetime.now(UTC).isoformat(),
                "status": "started",
            }

            def capture(argv, *, timeout, cwd, env, stdin="", row=row, catalog=catalog, name=name):
                if len(argv) > 1 and argv[1] == "exec":
                    argv = [
                        *argv[:-1], "-c",
                        f"model_catalog_json={json.dumps(catalog.as_posix())}", argv[-1],
                    ]
                    row["transport"] = {"argv": argv, "prompt": stdin, "working_directory": cwd}
                    write(DEST / "calls" / f"{name}.json", row)
                return subprocess_runner(argv, timeout=timeout, cwd=cwd, env=env, stdin=stdin)

            provider = CodexCliProvider(
                binary=manifest["binary"], model=model, runner=capture,
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
                if "transport" in row:
                    row["transport"] = {**provider.last_attempt, **row["transport"]}
                    row["transport"]["settings"] = {
                        **provider.last_attempt.get("settings", {}),
                        "model_catalog_json": catalog.as_posix(),
                    }
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
