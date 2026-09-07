"""Cross source annotation placement with a length aim; subscription research only."""

from __future__ import annotations

import argparse
import json
import os
import runpy
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = runpy.run_path(str(HERE / "prose_prospective_attention.py"))
CODEX = BASE["CODEX"]
read, write_new, sha = (CODEX[k] for k in ("read", "write_new", "sha"))
REG = HERE / "prose-source-contract"
ORDER = (
    "embedded-target-1",
    "separated-target-1",
    "separated-free-1",
    "embedded-free-1",
    "embedded-free-2",
    "separated-free-2",
    "separated-target-2",
    "embedded-target-2",
)
TOKEN_STOP = 125_000
EFFORT = "high"
LENGTH_AIM = "Aim for 1500-1800 words. "
EDITORIAL_INSTRUCTION = (
    "When supplied, editorial_constraints are preservation instructions with the same "
    "authority as instructions embedded in source_units, but are not events or thoughts "
    "required to narrate."
)
TARGET_SYSTEM = BASE["WRITER_SYSTEM"] + "\n" + EDITORIAL_INSTRUCTION
FREE_SYSTEM = TARGET_SYSTEM.replace(LENGTH_AIM, "", 1)
CODE_FILES = (
    "prose_source_contract.py",
    "prose_prospective_attention.py",
    "prose_attention_events.py",
    "prose_attention.py",
    "prose_constraint_levels.py",
    "prose_narration_obligations.py",
    "prose_protected_reconstruction.py",
    "prose_paragraph_revision.py",
    "prose_codex.py",
)


def payloads(source: Any) -> dict[str, Any]:
    """Move exact editorial spans without altering the source's other fields."""
    if not isinstance(source, dict) or set(source) != {"source", "partitions"}:
        raise ValueError("invalid source-contract wrapper")
    common = BASE["payload"](source["source"])
    units = {u["id"]: u for u in common["source_units"]}
    partitions = source["partitions"]
    if not isinstance(partitions, list) or not partitions:
        raise ValueError("nonempty partitions required")
    splits: dict[str, list[dict[str, str]]] = {}
    for partition in partitions:
        if (
            not isinstance(partition, dict)
            or set(partition) != {"id", "segments"}
            or not isinstance(partition["id"], str)
            or partition["id"] not in units
            or partition["id"] in splits
        ):
            raise ValueError("duplicate, unknown or malformed partition id")
        segments = partition["segments"]
        if not isinstance(segments, list) or not segments:
            raise ValueError("nonempty partition segments required")
        if any(
            not isinstance(s, dict)
            or set(s) != {"role", "text"}
            or s["role"] not in ("story", "editorial")
            or not isinstance(s["text"], str)
            or not s["text"].strip()
            for s in segments
        ):
            raise ValueError("invalid or blank partition segment")
        if {s["role"] for s in segments} != {"story", "editorial"}:
            raise ValueError("both story and editorial roles required")
        if "".join(s["text"] for s in segments) != units[partition["id"]]["text"]:
            raise ValueError("partition is not an exact lossless split")
        splits[partition["id"]] = segments

    separated_units, editorial = [], []
    # Source order, then segment order, determines the constraints' order even if
    # the reviewed partition list was entered in a different order.
    for unit in common["source_units"]:
        segments = splits.get(unit["id"])
        if segments is None:
            separated_units.append(dict(unit))
            continue
        story = "".join(s["text"] for s in segments if s["role"] == "story")
        if not story.strip():
            raise ValueError("partition leaves empty story text")
        separated_units.append({**unit, "text": story})
        editorial.extend(
            {"source_id": unit["id"], "text": s["text"]}
            for s in segments
            if s["role"] == "editorial"
        )
    return {
        "embedded": common,
        "separated": {
            **common,
            "source_units": separated_units,
            "editorial_constraints": editorial,
        },
    }


def compose(source: Any) -> dict[str, dict[str, str]]:
    if TARGET_SYSTEM.count(LENGTH_AIM) != 1:
        raise ValueError("registered length instruction changed")
    views = payloads(source)
    return {
        f"{representation}-{length}": {
            "system": TARGET_SYSTEM if length == "target" else FREE_SYSTEM,
            "prompt": json.dumps(payload, ensure_ascii=False),
        }
        for representation, payload in views.items()
        for length in ("target", "free")
    }


def _test_guard() -> None:
    if os.environ.get("LITHARNESS_ENV", "").strip().lower() == "test":
        raise RuntimeError("live trial is disabled in tests")


def _record(out: Path, name: str, request: Any, prefix: list[str]) -> dict[str, Any]:
    folder = out / name
    return {
        **request,
        "argv": CODEX["argv"](prefix, folder / "system.txt", folder / "work", effort=EFFORT),
        "requested_model": CODEX["MODEL"],
        "reasoning_effort": EFFORT,
        "authentication": "chatgpt",
        "removed_environment_keys": list(CODEX["REMOVED_ENV"]),
    }


def _files(out: Path, source_path: Path, prefix: list[str]) -> list[Path]:
    return [
        *(HERE / name for name in CODE_FILES),
        REG / "PREREG.md",
        REG / "RUNBOOK.md",
        REG / "LITERATURE.md",
        source_path,
        source_path.with_name("prepare_source.py"),
        source_path.with_name("source-review.md"),
        Path(prefix[1]),
        *(out / name / "system.txt" for name in ORDER),
    ]


def prepare(out: Path, source_path: Path) -> None:
    _test_guard()
    out, source_path = out.resolve(), source_path.resolve()
    if not out.is_relative_to(ROOT / "runs") or out == ROOT / "runs":
        raise ValueError("output must be beneath runs")
    if out.exists():
        raise FileExistsError("output directory must be new")
    source = read(source_path)
    requests = compose(source)
    prefix = CODEX["command_prefix"]()
    # Fail before auth checks when registration or reviewed source material is absent.
    systems = {out / name / "system.txt" for name in ORDER}
    paths = _files(out, source_path, prefix)
    if any(not p.is_file() for p in paths if p not in systems):
        raise ValueError("missing code, registration or reviewed source file")
    auth = subprocess.run(
        [*prefix, "login", "status"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=CODEX["subscription_env"](),
        check=False,
    )
    if auth.returncode or (auth.stdout + auth.stderr).strip() != "Logged in using ChatGPT":
        raise RuntimeError("ChatGPT subscription required; no API or login fallback")
    out.mkdir(parents=True, exist_ok=False)
    for name in ORDER:
        folder = out / name
        (folder / "work").mkdir(parents=True)
        (folder / "system.txt").write_text(
            requests[name.rsplit("-", 1)[0]]["system"], encoding="utf-8", newline="\n"
        )
    write_new(
        out / "manifest.json",
        {
            "source": source,
            "source_path": str(source_path),
            "requests": requests,
            "slot_requests": {
                name: _record(out, name, requests[name.rsplit("-", 1)[0]], prefix) for name in ORDER
            },
            "prefix": prefix,
            "order": list(ORDER),
            "token_stop": TOKEN_STOP,
            "files": {str(p): sha(p) for p in paths},
            "authentication": "chatgpt",
            "reasoning_effort": EFFORT,
            "transport_slot_per_logical_call": "full-1",
            "code_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True, cwd=ROOT
            ).strip(),
            "cli_version": subprocess.check_output(
                [*prefix, "--version"], text=True, env=CODEX["subscription_env"]()
            ).strip(),
        },
    )


def validate(out: Path) -> dict[str, Any]:
    manifest = CODEX["validate"](out)
    source_path, prefix = Path(manifest["source_path"]), manifest["prefix"]
    if set(manifest["files"]) != {str(p) for p in _files(out, source_path, prefix)}:
        raise ValueError("frozen file inventory changed")
    if (
        manifest["order"] != list(ORDER)
        or manifest["token_stop"] != TOKEN_STOP
        or manifest["authentication"] != "chatgpt"
        or manifest["reasoning_effort"] != EFFORT
        or manifest["transport_slot_per_logical_call"] != "full-1"
    ):
        raise ValueError("registered dispatch settings changed")
    if manifest["source"] != read(source_path):
        raise ValueError("frozen source identity changed")
    requests = compose(manifest["source"])
    if manifest["requests"] != requests or manifest["slot_requests"] != {
        name: _record(out, name, requests[name.rsplit("-", 1)[0]], prefix) for name in ORDER
    }:
        raise ValueError("frozen request identity changed")
    for name in ORDER:
        if (out / name / "system.txt").read_text(encoding="utf-8") != requests[
            name.rsplit("-", 1)[0]
        ]["system"]:
            raise ValueError("system file differs from frozen request")
        path = out / name / "full-1.request.json"
        if path.exists() and read(path) != manifest["slot_requests"][name]:
            raise ValueError("recorded request identity changed")
    return manifest


def quota(out: Path) -> int:
    requests = list(out.glob("*/*.request.json"))
    results = list(out.glob("*/*.result.json"))
    if any(p.parent.name not in ORDER or p.name != "full-1.request.json" for p in requests):
        raise ValueError("unregistered invocation")
    if any(p.parent.name not in ORDER or p.name != "full-1.result.json" for p in results):
        raise ValueError("unregistered result")
    names = {p.parent.name for p in requests}
    if names != set(ORDER[: len(names)]):
        raise ValueError("invocation slot order changed")
    completed = {p.parent.name for p in results}
    if completed - names:
        raise ValueError("result has no recorded request")
    if names - completed:
        raise RuntimeError("request has no result; no retry")
    total = 0
    for path in results:
        result = read(path)
        if result.get("status") != "completed":
            raise RuntimeError("previous failure; no retry")
        usage = result.get("usage")
        if not isinstance(usage, dict):
            raise ValueError("invalid quota usage")
        for key in ("input_tokens", "output_tokens", "reasoning_output_tokens"):
            value = usage.get(key, 0 if key == "reasoning_output_tokens" else None)
            if type(value) is not int or value < 0:
                raise ValueError("invalid quota usage")
            total += value
    if total >= TOKEN_STOP:
        raise RuntimeError("subscription token stop reached")
    return total


def call(out: Path, name: str, request: Any, manifest: Any) -> dict[str, Any]:
    _test_guard()
    if name not in ORDER:
        raise ValueError("unregistered invocation")
    frozen = validate(out)
    if manifest != frozen or request != frozen["requests"][name.rsplit("-", 1)[0]]:
        raise ValueError("dispatch request identity changed")
    quota(out)
    if any(not (out / n / "full-1.result.json").exists() for n in ORDER[: ORDER.index(name)]):
        raise ValueError("prior invocation missing")
    print(f"LOGICAL CALL {name}", flush=True)
    return CODEX["complete_once"](
        out / name,
        "full-1",
        {"prefix": frozen["prefix"], "requests": {"full": request}},
        effort=EFFORT,
    )


def draft(out: Path) -> None:
    _test_guard()
    out = out.resolve()
    for name in ORDER:
        manifest = read(out / "manifest.json")
        call(out, name, manifest["requests"][name.rsplit("-", 1)[0]], manifest)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "draft"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    if args.phase == "prepare":
        if not args.source:
            parser.error("prepare requires --source")
        prepare(args.out, args.source)
    else:
        draft(args.out)


if __name__ == "__main__":
    main()
